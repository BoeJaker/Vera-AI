"""
Focused Cognition Loop — the "deep work" task execution engine.

Each task is driven through its state machine by the FocusedLoop.
This class is the handler that the Scheduler calls for each task.

State machine:
    NEW → SCOPING → PLANNING → EXECUTION → REVIEW → COMPLETE
                                   ↓
                               BLOCKED (waiting on human)
                                   ↓
                               (answer arrives → resume EXECUTION)

A single call to `execute(task)` advances the task by one state
transition. The scheduler re-queues tasks that aren't terminal,
so the loop is inherently incremental and non-blocking.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Dict, List, Optional

from ..interfaces import LLMBackend, MemoryStore, MessagingGateway, ToolRouter
from ..models import (
    LogEntry, Question, Task, TaskPriority, TaskStatus, TaskStep,
)

logger = logging.getLogger(__name__)


# ── Prompts ───────────────────────────────────────────────────

SCOPING_SYSTEM = (
    "You are a task scoping agent. Given a goal, determine:\n"
    "1. Whether this task is clear enough to plan (scope: \"ready\") or needs clarification (scope: \"needs_input\").\n"
    "2. If needs_input, formulate a clear question for the human.\n"
    "3. Estimate complexity: \"trivial\" (1 step), \"simple\" (2-3 steps), \"moderate\" (4-6), \"complex\" (7+).\n\n"
    'Respond ONLY with JSON:\n'
    '{"scope": "ready|needs_input", "question": "...", "complexity": "...", "refined_goal": "..."}'
)

PLANNING_SYSTEM = (
    "You are a task planning agent. Given a goal and available tools, produce a concrete step-by-step plan.\n\n"
    "Available tools: {tools}\n\n"
    "Each step should specify:\n"
    "- description: what to do\n"
    "- tool: tool name if needed (null for pure reasoning steps)\n"
    "- tool_args: dict of arguments if tool is used\n\n"
    'Respond ONLY with JSON:\n'
    '{{"steps": [{{"description": "...", "tool": null, "tool_args": null}}]}}'
)

EXECUTION_SYSTEM = (
    "You are a task execution agent working through a plan step by step.\n\n"
    "Current task: {goal}\n"
    "Current step: {step_description}\n"
    "Previous results: {context}\n\n"
    "{tool_instruction}\n\n"
    'Respond ONLY with JSON:\n'
    '{{"reasoning": "...", "action": "execute_tool|think|ask_human|skip", "tool_args": {{}}, "result_summary": "...", "question": ""}}'
)

REVIEW_SYSTEM = (
    "You are a task review agent. Given the goal, plan, and execution log, determine:\n"
    "1. Whether the task is complete and the goal is satisfied.\n"
    "2. A final summary of results.\n"
    "3. Any follow-up tasks worth proposing.\n\n"
    'Respond ONLY with JSON:\n'
    '{"complete": true, "summary": "...", "follow_up_tasks": [{"goal": "...", "priority": "normal"}]}'
)


# ── Focused Loop (task handler) ───────────────────────────────

class FocusedLoop:
    """
    Stateless task handler — the Scheduler calls `execute(task)` and
    this advances the task one step through its lifecycle.

    After each call, the caller (CognitionManager) decides whether
    to re-queue, block, or finalise the task.
    """

    def __init__(
        self,
        llm: LLMBackend,
        memory: MemoryStore,
        messaging: MessagingGateway,
        tools: ToolRouter,
        on_task_proposed=None,          # async callback(Task) for follow-ups
    ):
        self.llm = llm
        self.memory = memory
        self.messaging = messaging
        self.tools = tools
        self._on_task_proposed = on_task_proposed

    async def execute(self, task: Task) -> Task:
        """
        Advance the task by one state transition.
        Returns the (mutated) task — check task.status to decide next action.
        """
        logger.info("Focused: task %s [%s] → %s", task.id, task.goal[:40], task.status.value)

        handlers = {
            TaskStatus.NEW:       self._handle_new,
            TaskStatus.SCOPING:   self._handle_scoping,
            TaskStatus.PLANNING:  self._handle_planning,
            TaskStatus.EXECUTION: self._handle_execution,
            TaskStatus.REVIEW:    self._handle_review,
        }

        handler = handlers.get(task.status)
        if handler is None:
            logger.warning("No handler for status %s, skipping", task.status.value)
            return task

        try:
            await handler(task)
        except Exception as e:
            task.retries += 1
            if task.retries > task.max_retries:
                task.status = TaskStatus.FAILED
                task.error = str(e)
                await self._notify(task, f"Task failed: {e}")
            else:
                task.progress_log.append(
                    LogEntry(message=f"Retry {task.retries}: {e}", level="warn")
                )
            logger.exception("Error executing task %s step", task.id)

        task.touch()
        await self.memory.save_task(task)
        return task

    # ── state handlers ──

    async def _handle_new(self, task: Task):
        task.status = TaskStatus.SCOPING
        task.progress_log.append(LogEntry(message="Task received, scoping..."))

    async def _handle_scoping(self, task: Task):
        messages = [{"role": "user", "content": f"Goal: {task.goal}"}]
        raw = await self.llm.complete(
            messages=messages, system=SCOPING_SYSTEM, temperature=0.2
        )
        result = _parse_json(raw)
        if not result:
            task.status = TaskStatus.PLANNING
            return

        if result.get("scope") == "needs_input":
            question = Question(
                task_id=task.id,
                text=result.get("question", "Could you clarify the goal?"),
            )
            await self.memory.save_question(question)
            await self.messaging.ask_question(question)
            task.status = TaskStatus.BLOCKED
            task.progress_log.append(
                LogEntry(message=f"Blocked: asked '{question.text}'")
            )
        else:
            refined = result.get("refined_goal")
            if refined:
                task.progress_log.append(
                    LogEntry(message=f"Refined goal: {refined}")
                )
            task.status = TaskStatus.PLANNING

    async def _handle_planning(self, task: Task):
        available_tools = await self.tools.list_tools()
        system = PLANNING_SYSTEM.format(tools=", ".join(available_tools))
        messages = [{"role": "user", "content": f"Goal: {task.goal}"}]

        raw = await self.llm.complete(
            messages=messages, system=system, temperature=0.3
        )
        result = _parse_json(raw)
        if not result or "steps" not in result:
            # fallback: single-step plan
            task.plan = [TaskStep(description=f"Execute: {task.goal}")]
        else:
            task.plan = [
                TaskStep(
                    description=s["description"],
                    tool=s.get("tool"),
                    tool_args=s.get("tool_args"),
                )
                for s in result["steps"]
            ]

        task.current_step_idx = 0
        task.status = TaskStatus.EXECUTION
        task.progress_log.append(
            LogEntry(message=f"Plan created: {len(task.plan)} steps")
        )
        await self._notify(task, f"📋 Plan for '{task.goal}': {len(task.plan)} steps")

    async def _handle_execution(self, task: Task):
        step = task.current_step()
        if step is None:
            task.status = TaskStatus.REVIEW
            return

        step.started_at = time.time()

        # build context from previous step results
        context_parts = []
        for prev in task.plan[: task.current_step_idx]:
            if prev.result:
                context_parts.append(f"Step '{prev.description}': {prev.result}")
        context = "\n".join(context_parts) if context_parts else "(first step)"

        tool_instruction = ""
        if step.tool:
            tool_instruction = f"This step uses tool '{step.tool}'. Execute it with the provided args, or adjust if needed."

        system = EXECUTION_SYSTEM.format(
            goal=task.goal,
            step_description=step.description,
            context=context,
            tool_instruction=tool_instruction,
        )
        messages = [{"role": "user", "content": f"Execute step {task.current_step_idx + 1}: {step.description}"}]

        raw = await self.llm.complete(
            messages=messages, system=system, temperature=0.3
        )
        result = _parse_json(raw)

        if result:
            action = result.get("action", "think")

            if action == "ask_human":
                question = Question(
                    task_id=task.id,
                    text=result.get("question", "Need clarification to proceed."),
                )
                await self.memory.save_question(question)
                await self.messaging.ask_question(question)
                task.status = TaskStatus.BLOCKED
                return

            if action == "execute_tool" and step.tool:
                tool_args = result.get("tool_args") or step.tool_args or {}
                try:
                    tool_result = await self.tools.run_tool(step.tool, tool_args)
                    step.result = tool_result
                except Exception as e:
                    step.result = {"error": str(e)}
                    task.progress_log.append(
                        LogEntry(message=f"Tool '{step.tool}' failed: {e}", level="error")
                    )
            else:
                step.result = result.get("result_summary", "completed")
        else:
            step.result = raw[:200]   # store raw LLM output as fallback

        task.advance()

        # milestone notification
        if task.update_frequency == "step" or (
            task.update_frequency == "milestone"
            and task.current_step_idx == len(task.plan)
        ):
            await self._notify(
                task,
                f"✅ Step {task.current_step_idx}/{len(task.plan)}: {step.description}",
            )

    async def _handle_review(self, task: Task):
        # build execution summary
        exec_log = []
        for i, s in enumerate(task.plan):
            status = "✅" if s.completed else "❌"
            exec_log.append(f"{status} Step {i+1}: {s.description} → {s.result}")

        messages = [{
            "role": "user",
            "content": f"Goal: {task.goal}\n\nExecution log:\n" + "\n".join(exec_log),
        }]

        raw = await self.llm.complete(
            messages=messages, system=REVIEW_SYSTEM, temperature=0.3
        )
        result = _parse_json(raw)

        if result:
            task.artifacts["summary"] = result.get("summary", "")
            is_complete = result.get("complete", True)

            if not is_complete:
                # re-enter execution with extended plan
                task.status = TaskStatus.EXECUTION
                task.progress_log.append(LogEntry(message="Review: incomplete, continuing"))
                return

            # propose follow-up tasks
            for ft in result.get("follow_up_tasks", []):
                if self._on_task_proposed:
                    follow = Task(
                        goal=ft["goal"],
                        priority=TaskPriority.LOW,
                        origin="follow_up",
                        parent_task_id=task.id,
                    )
                    task.spawned_task_ids.append(follow.id)
                    await self._on_task_proposed(follow)

        task.status = TaskStatus.COMPLETE
        task.progress_log.append(LogEntry(message="Task complete"))
        await self._notify(
            task,
            f"🏁 Completed: {task.goal}\n{task.artifacts.get('summary', '')}",
        )

    # ── helpers ──

    async def _notify(self, task: Task, text: str):
        try:
            await self.messaging.send_progress(task, text)
        except Exception:
            logger.warning("Failed to send notification for task %s", task.id)


def _parse_json(raw: str) -> Optional[Dict]:
    """Best-effort JSON extraction from LLM output."""
    raw = raw.strip()
    # strip markdown fences
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:])
        if raw.endswith("```"):
            raw = raw[:-3]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # try to find JSON object in the string
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start:end])
            except json.JSONDecodeError:
                pass
    return None