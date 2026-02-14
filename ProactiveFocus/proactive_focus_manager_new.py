"""
ProactiveFocusManager v2 — Modular Iterative Workflow Engine
=============================================================

Drop-in replacement for the original ProactiveFocusManager.
Designed for LLMs to work on problems iteratively: discovering, creating,
refining resources, steering future tasks, and reviewing progress.

Architecture
------------
    ProactiveFocusManager
    ├── StageRegistry        — modular stage add/remove
    │   ├── ThoughtStage     — inspect memory, reflect, write analysis
    │   ├── PlanningStage    — produce structured plans
    │   ├── ActionStage      — decompose & execute via toolchain
    │   ├── InterviewStage   — ask the human, non-blocking
    │   ├── DiscoveryStage   — use tools to research
    │   └── ReviewStage      — evaluate progress, steer direction
    ├── SteeringEngine       — LLM picks next stage dynamically
    ├── ProjectManager       — structured file output per focus
    ├── HumanBridge          — async question queue (Telegram/WS)
    └── WorkflowEngine       — runs the iteration loop

Backward-compatible with the existing FastAPI router (focus.py).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import threading
import time
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import (
    Any, Callable, Dict, Generator, Iterator, List, Optional, Set, Tuple, Union,
)

import psutil

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def extract_chunk_text(chunk) -> str:
    """Pull text from any chunk format."""
    if isinstance(chunk, str):
        return chunk
    if hasattr(chunk, "content"):
        return chunk.content
    if hasattr(chunk, "text"):
        return chunk.text
    if isinstance(chunk, dict):
        return chunk.get("content", chunk.get("text", str(chunk)))
    return str(chunk)


def _sanitize_filename(text: str, max_len: int = 80) -> str:
    """Make text safe for use as a filename component."""
    safe = re.sub(r"[^\w\-]", "_", text)
    return safe[:max_len].rstrip("_")


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _now_stamp() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


# ===================================================================
# DATA CLASSES
# ===================================================================

@dataclass
class StageResult:
    """What a stage returns after execution."""
    content: str = ""                       # Markdown narrative / main output
    artifacts: List[str] = field(default_factory=list)  # File paths created
    board_updates: Dict[str, List[str]] = field(default_factory=dict)  # category -> notes
    questions: List[str] = field(default_factory=list)  # Questions for the human
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StageContext:
    """Everything a stage needs to do its job."""
    focus: str
    project_id: Optional[str]
    project_path: Path
    focus_board: Dict[str, list]
    iteration: int
    previous_stage_name: Optional[str]
    previous_result: Optional[StageResult]
    human_answers: Dict[str, str]           # question_id -> answer
    agent: Any                              # Vera instance
    hybrid_memory: Any
    broadcast: Callable                     # _broadcast_sync
    stream_output: Callable                 # _stream_output
    extra: Dict[str, Any] = field(default_factory=dict)


class QuestionStatus(Enum):
    PENDING = "pending"
    ANSWERED = "answered"
    SKIPPED = "skipped"
    EXPIRED = "expired"


@dataclass
class HumanQuestion:
    """A question queued for the human."""
    question_id: str
    text: str
    context: str = ""
    status: QuestionStatus = QuestionStatus.PENDING
    answer: Optional[str] = None
    asked_at: str = field(default_factory=_now_iso)
    answered_at: Optional[str] = None
    stage: str = ""
    iteration: int = 0


# ===================================================================
# STAGE BASE CLASS
# ===================================================================

class Stage(ABC):
    """
    Base class for all workflow stages.

    Subclass this and implement ``execute()`` to create a new stage.
    Register it with ``manager.register_stage(MyStage())``.
    """

    name: str = "unnamed"
    description: str = ""
    icon: str = "▶️"
    # If True, the stage can be skipped when no useful work is expected
    skippable: bool = True

    @abstractmethod
    def execute(self, ctx: StageContext) -> StageResult:
        """Run the stage and return a StageResult with real content."""
        ...

    def should_run(self, ctx: StageContext) -> Tuple[bool, str]:
        """Optional pre-check. Return (should_run, reason)."""
        return True, ""

    # Convenience helpers available to all stages ----------------------

    @staticmethod
    def _llm_generate(agent, prompt: str, *, use_deep: bool = False) -> str:
        """Blocking full-text generation from an LLM."""
        llm = agent.deep_llm if use_deep else agent.fast_llm
        chunks = []
        for chunk in llm.stream(prompt):
            chunks.append(extract_chunk_text(chunk))
        return "".join(chunks)

    @staticmethod
    def _llm_stream(agent, prompt: str, *, use_deep: bool = False) -> Generator[str, None, None]:
        """Streaming generation, yields text chunks."""
        llm = agent.deep_llm if use_deep else agent.fast_llm
        for chunk in llm.stream(prompt):
            yield extract_chunk_text(chunk)

    @staticmethod
    def _query_memory_graph(hybrid_memory, cypher: str, params: dict = None) -> list:
        """Run a Cypher query and return list of record dicts."""
        if not hybrid_memory:
            return []
        try:
            with hybrid_memory.graph._driver.session() as sess:
                result = sess.run(cypher, params or {})
                return [dict(record) for record in result]
        except Exception as e:
            print(f"[Stage] Graph query error: {e}")
            return []

    @staticmethod
    def _search_vectors(hybrid_memory, query: str, limit: int = 10,
                        project_id: str = None) -> List[str]:
        """Semantic search in vector store."""
        if not hybrid_memory:
            return []
        try:
            filter_dict = {"project_id": project_id} if project_id else None
            results = hybrid_memory.vec.search(
                collection="long_term_docs",
                query=query,
                limit=limit,
                filter_dict=filter_dict,
            )
            return [doc.get("text", "") for doc in results if doc.get("text")]
        except Exception:
            return []

    @staticmethod
    def _write_artifact(project_path: Path, category: str, filename: str,
                        content: str) -> str:
        """Write content to project directory and return the path."""
        dest = project_path / category
        dest.mkdir(parents=True, exist_ok=True)
        filepath = dest / filename
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return str(filepath)


# ===================================================================
# CONCRETE STAGES
# ===================================================================

class ThoughtStage(Stage):
    """
    Introspective thinking — the LLM inspects its own memory, the focus
    board, recent context, and writes a narrative reflection/analysis.

    Produces: thoughts/<timestamp>.md
    """
    name = "thought"
    description = "Reflect on current state, inspect memory, identify patterns"
    icon = "🧠"

    def execute(self, ctx: StageContext) -> StageResult:
        ctx.stream_output(f"{self.icon} Starting thought stage…", "info")

        # Gather context from memory
        graph_context = self._query_memory_graph(ctx.hybrid_memory, """
            MATCH (p:Project {id: $pid})-[r]->(n)
            RETURN labels(n) AS labels, n.id AS id,
                   coalesce(n.text, n.note, n.name, '') AS text
            ORDER BY n.created_at DESC LIMIT 20
        """, {"pid": ctx.project_id or ""})

        vector_context = self._search_vectors(
            ctx.hybrid_memory, ctx.focus, limit=8, project_id=ctx.project_id
        )

        # Summarise focus board compactly
        board_summary = ""
        for cat, items in ctx.focus_board.items():
            if items:
                notes = [i.get("note", str(i))[:120] if isinstance(i, dict) else str(i)[:120]
                         for i in items[-5:]]
                board_summary += f"\n### {cat} ({len(items)} items)\n"
                board_summary += "\n".join(f"- {n}" for n in notes) + "\n"

        prompt = f"""You are a senior analyst working on: **{ctx.focus}**

Iteration {ctx.iteration}.  Your job is to THINK deeply about the project.
Write a narrative analysis (not bullet lists). Cover:

1. What do we know so far? What progress has been made?
2. What patterns or connections do you see?
3. What assumptions might be wrong?
4. What blind spots or risks exist?
5. What would a domain expert focus on next?

--- MEMORY CONTEXT (graph entities) ---
{json.dumps(graph_context[:10], indent=2, default=str)[:3000]}

--- VECTOR SEARCH (related documents) ---
{chr(10).join(v[:400] for v in vector_context[:5])}

--- FOCUS BOARD ---
{board_summary}

--- PREVIOUS STAGE ---
{ctx.previous_stage_name or 'None'}: {(ctx.previous_result.content[:600] if ctx.previous_result else 'N/A')}

Write 300-800 words of genuine analytical narrative. End with 2-3 concrete
observations that should inform the next stage.
"""
        ctx.stream_output("Generating reflective analysis…", "info")
        content = self._llm_generate(ctx.agent, prompt, use_deep=True)

        # Save artifact
        filename = f"thought_{_now_stamp()}.md"
        header = f"# Thought — Iteration {ctx.iteration}\n\n"
        header += f"**Focus:** {ctx.focus}\n**Time:** {_now_iso()}\n\n---\n\n"
        filepath = self._write_artifact(ctx.project_path, "thoughts", filename,
                                        header + content)

        ctx.stream_output(f"📝 Wrote {filepath}", "success")

        return StageResult(
            content=content,
            artifacts=[filepath],
            board_updates={"progress": [f"Thought analysis completed (iter {ctx.iteration})"]},
        )


class PlanningStage(Stage):
    """
    Given the current state, produce a structured plan with priorities
    and concrete next steps.

    Produces: plans/<timestamp>.md
    """
    name = "planning"
    description = "Create or refine a structured project plan"
    icon = "📋"

    def execute(self, ctx: StageContext) -> StageResult:
        ctx.stream_output(f"{self.icon} Planning stage…", "info")

        # Gather what we already have
        existing_steps = [
            i.get("note", str(i)) if isinstance(i, dict) else str(i)
            for i in ctx.focus_board.get("next_steps", [])[-10:]
        ]
        existing_issues = [
            i.get("note", str(i)) if isinstance(i, dict) else str(i)
            for i in ctx.focus_board.get("issues", [])[-10:]
        ]
        prev_content = ctx.previous_result.content[:1500] if ctx.previous_result else ""

        # Available tools for context
        tool_names = [t.name for t in ctx.agent.tools] if hasattr(ctx.agent, "tools") else []

        prompt = f"""You are planning the next actions for project: **{ctx.focus}**

PREVIOUS ANALYSIS:
{prev_content}

EXISTING NEXT STEPS: {json.dumps(existing_steps, indent=2)}
KNOWN ISSUES: {json.dumps(existing_issues, indent=2)}

AVAILABLE TOOLS: {tool_names[:20]}

Write a structured plan as a markdown document with:

## Objective
One paragraph on what we're trying to achieve right now.

## Priority Actions (do first)
For each action, write:
- **Action name**: Full description of what to do and why
- Expected outcome
- Whether it needs tools, human input, or just reasoning

## Secondary Actions (do if time permits)
Same format.

## Open Questions
Questions that need answering (these may be asked to the human).

## Risks & Mitigations
What could go wrong and how to handle it.

Be SPECIFIC and DETAILED. Each action should be clear enough that someone
(or an AI) could execute it without further clarification.
Write 400-1000 words.
"""
        content = self._llm_generate(ctx.agent, prompt, use_deep=True)

        filename = f"plan_{_now_stamp()}.md"
        header = f"# Plan — Iteration {ctx.iteration}\n\n"
        header += f"**Focus:** {ctx.focus}\n**Time:** {_now_iso()}\n\n---\n\n"
        filepath = self._write_artifact(ctx.project_path, "plans", filename,
                                        header + content)

        # Extract actionable items for the board
        board_updates: Dict[str, List[str]] = {"next_steps": [], "issues": []}

        # Quick LLM extraction of concrete steps
        extract_prompt = f"""From this plan, extract 3-5 concrete next steps as a JSON array of strings.
Each step should be one sentence, actionable and specific.
Plan:
{content[:2000]}

Respond ONLY with a JSON array like: ["step 1", "step 2", ...]
"""
        try:
            raw = self._llm_generate(ctx.agent, extract_prompt)
            steps = json.loads(raw.strip().strip("`").strip("json").strip())
            if isinstance(steps, list):
                board_updates["next_steps"] = [str(s) for s in steps[:5]]
        except Exception:
            pass

        # Extract questions
        questions = []
        q_prompt = f"""From this plan, extract any open questions for the user as a JSON array.
If none, return [].
Plan:
{content[:2000]}

JSON array only:
"""
        try:
            raw = self._llm_generate(ctx.agent, q_prompt)
            qs = json.loads(raw.strip().strip("`").strip("json").strip())
            if isinstance(qs, list):
                questions = [str(q) for q in qs[:5]]
        except Exception:
            pass

        ctx.stream_output(f"📝 Wrote {filepath}", "success")
        ctx.stream_output(f"Extracted {len(board_updates['next_steps'])} steps, "
                          f"{len(questions)} questions", "info")

        return StageResult(
            content=content,
            artifacts=[filepath],
            board_updates=board_updates,
            questions=questions,
        )


class ActionStage(Stage):
    """
    Takes planned steps and executes them through the toolchain.
    Uses the MonitoredToolChainPlanner pattern for proper multi-param support.

    Produces: actions/<timestamp>.md (execution report)
    """
    name = "action"
    description = "Execute planned actions using tools"
    icon = "⚡"
    skippable = True

    def should_run(self, ctx: StageContext) -> Tuple[bool, str]:
        steps = ctx.focus_board.get("next_steps", [])
        if not steps:
            return False, "No next_steps on focus board"
        return True, ""

    def execute(self, ctx: StageContext) -> StageResult:
        ctx.stream_output(f"{self.icon} Action stage — executing planned steps…", "info")

        steps = ctx.focus_board.get("next_steps", [])[-5:]
        if not steps:
            return StageResult(content="No actions to execute.", board_updates={})

        tool_names = [t.name for t in ctx.agent.tools] if hasattr(ctx.agent, "tools") else []
        all_results = []
        executed = 0
        max_executions = 3

        report_lines = [
            f"# Action Execution Report — Iteration {ctx.iteration}\n",
            f"**Focus:** {ctx.focus}\n**Time:** {_now_iso()}\n\n---\n",
        ]

        for idx, step_item in enumerate(steps):
            if executed >= max_executions:
                break

            # Check CPU before each execution
            cpu = psutil.cpu_percent(interval=0.1)
            if cpu > 80.0:
                ctx.stream_output(f"⚠️ CPU at {cpu:.0f}%, pausing actions", "warning")
                break

            step_text = step_item.get("note", str(step_item)) if isinstance(step_item, dict) else str(step_item)
            ctx.stream_output(f"\n▶️ [{idx+1}] {step_text[:120]}", "info")

            # Ask the LLM to decompose into a toolchain plan
            decompose_prompt = f"""You need to execute this action step using available tools.

ACTION: {step_text}
PROJECT: {ctx.focus}

AVAILABLE TOOLS:
{json.dumps(tool_names[:30])}

If this action can be accomplished with tools, respond with a JSON array of steps:
[
  {{"tool": "tool_name", "input": "input string or JSON object"}},
  ...
]

If this action is purely analytical/writing (no tools needed), respond with:
[{{"tool": "NONE", "input": "This action requires reasoning, not tools"}}]

Rules:
- Use {{prev}} to reference the previous step's output
- For tools needing multiple params, use a JSON object as input
- Keep the chain to 1-4 steps maximum
- Only use tools from the list above

JSON array only:
"""
            try:
                raw_plan = self._llm_generate(ctx.agent, decompose_prompt)
                plan = json.loads(
                    raw_plan.strip().strip("`").lstrip("json").strip()
                )
                if not isinstance(plan, list):
                    plan = [plan]
            except (json.JSONDecodeError, ValueError):
                ctx.stream_output(f"  ⚠️ Could not decompose into tool plan", "warning")
                report_lines.append(f"\n## Step {idx+1}: {step_text}\n\n"
                                    f"Could not decompose into tool plan.\n")
                continue

            # Check if it's a no-tool action
            if len(plan) == 1 and plan[0].get("tool") == "NONE":
                ctx.stream_output(f"  ℹ️ No tools needed, skipping execution", "info")
                report_lines.append(f"\n## Step {idx+1}: {step_text}\n\n"
                                    f"Analysis/reasoning step — no tool execution.\n")
                continue

            # Execute the tool chain
            report_lines.append(f"\n## Step {idx+1}: {step_text}\n\n")
            report_lines.append(f"**Plan:** {len(plan)} tool steps\n\n")

            step_result = self._execute_tool_plan(
                ctx, plan, step_text, report_lines
            )
            all_results.append(step_result)
            executed += 1

        # Build report
        report_content = "\n".join(report_lines)
        filename = f"actions_{_now_stamp()}.md"
        filepath = self._write_artifact(ctx.project_path, "actions", filename,
                                        report_content)

        ctx.stream_output(f"📝 Wrote execution report: {filepath}", "success")
        ctx.stream_output(f"Executed {executed}/{len(steps)} steps", "info")

        board_updates: Dict[str, List[str]] = {
            "progress": [f"Executed {executed} action steps (iter {ctx.iteration})"],
            "completed": [],
        }
        # Move executed steps to completed
        for i in range(min(executed, len(steps))):
            step_text = steps[i].get("note", str(steps[i])) if isinstance(steps[i], dict) else str(steps[i])
            board_updates["completed"].append(step_text)

        return StageResult(
            content=report_content,
            artifacts=[filepath],
            board_updates=board_updates,
            tool_results=all_results,
        )

    def _execute_tool_plan(self, ctx: StageContext, plan: list,
                           goal: str, report_lines: list) -> Dict[str, Any]:
        """Execute a decomposed tool plan, matching Document 5's pattern."""
        tool_outputs: Dict[str, str] = {}
        final_output = ""

        for step_num, step in enumerate(plan, 1):
            tool_name = step.get("tool", "")
            raw_input = step.get("input", "")

            # Parse input (JSON string → dict if applicable)
            parsed = self._parse_tool_input(raw_input)

            # Resolve placeholders
            resolved = self._resolve_placeholders(parsed, step_num, tool_outputs)

            ctx.stream_output(f"  🔧 [{step_num}] {tool_name}", "info")

            # Find the tool
            tool = next((t for t in ctx.agent.tools if t.name == tool_name), None)
            if not tool:
                msg = f"Tool not found: {tool_name}"
                ctx.stream_output(f"  ❌ {msg}", "error")
                report_lines.append(f"### Tool step {step_num}: {tool_name}\n❌ {msg}\n\n")
                continue

            try:
                result = self._run_tool(tool, tool_name, resolved)

                # Collect streaming or direct result
                result_str = ""
                try:
                    for chunk in result:
                        result_str += str(chunk)
                except TypeError:
                    result_str = str(result)

                tool_outputs[f"step_{step_num}"] = result_str
                tool_outputs[tool_name] = result_str
                final_output = result_str

                preview = result_str[:300]
                ctx.stream_output(f"  ✅ {tool_name} → {len(result_str)} chars", "success")
                report_lines.append(
                    f"### Tool step {step_num}: {tool_name}\n\n"
                    f"**Input:** `{json.dumps(resolved) if isinstance(resolved, dict) else resolved[:200]}`\n\n"
                    f"**Output:**\n```\n{preview}\n```\n\n"
                )

            except Exception as e:
                msg = f"Error executing {tool_name}: {e}"
                ctx.stream_output(f"  ❌ {msg}", "error")
                report_lines.append(f"### Tool step {step_num}: {tool_name}\n❌ {msg}\n\n")

        return {"goal": goal, "output": final_output, "steps": len(plan)}

    @staticmethod
    def _parse_tool_input(raw_input: Any) -> Any:
        if isinstance(raw_input, dict):
            return raw_input
        if not isinstance(raw_input, str):
            return str(raw_input)
        stripped = raw_input.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                pass
        return raw_input

    @staticmethod
    def _resolve_placeholders(value: Any, step_num: int,
                              outputs: Dict[str, str]) -> Any:
        if isinstance(value, dict):
            return {k: ActionStage._resolve_placeholders(v, step_num, outputs)
                    for k, v in value.items()}
        if isinstance(value, list):
            return [ActionStage._resolve_placeholders(v, step_num, outputs)
                    for v in value]
        if isinstance(value, str):
            if "{prev}" in value:
                value = value.replace("{prev}", outputs.get(f"step_{step_num-1}", ""))
            for i in range(1, step_num):
                ph = f"{{step_{i}}}"
                if ph in value:
                    value = value.replace(ph, outputs.get(f"step_{i}", ""))
            return value
        return value

    @staticmethod
    def _run_tool(tool, tool_name: str, tool_input: Any) -> Any:
        """Execute tool with proper argument handling."""
        if hasattr(tool, "run") and callable(tool.run):
            return tool.run(tool_input)
        if hasattr(tool, "invoke") and callable(tool.invoke):
            return tool.invoke(tool_input)
        func = getattr(tool, "func", tool)
        if isinstance(tool_input, dict):
            return func(**tool_input)
        return func(tool_input)


class InterviewStage(Stage):
    """
    Formulates questions for the human and sends them (via Telegram / WS).
    Non-blocking — checks for any pending answers and incorporates them,
    but does NOT halt if the human hasn't responded.

    Produces: interviews/<timestamp>.md
    """
    name = "interview"
    description = "Ask the human clarifying questions (non-blocking)"
    icon = "💬"

    def execute(self, ctx: StageContext) -> StageResult:
        ctx.stream_output(f"{self.icon} Interview stage…", "info")

        # 1. Check for answers to previously asked questions
        answered = {qid: ans for qid, ans in ctx.human_answers.items() if ans}
        if answered:
            ctx.stream_output(f"📬 Received {len(answered)} answers from human", "success")

        # 2. Determine what we need to ask
        prev_content = ctx.previous_result.content[:2000] if ctx.previous_result else ""
        prev_questions = ctx.previous_result.questions if ctx.previous_result else []

        # Include previously answered Q&A for context
        qa_context = ""
        if answered:
            qa_context = "\n\nPREVIOUSLY ANSWERED:\n"
            for qid, ans in answered.items():
                qa_context += f"Q: {qid}\nA: {ans}\n\n"

        prompt = f"""You are working on: **{ctx.focus}**

Recent work:
{prev_content[:1500]}

{qa_context}

Previous unanswered questions:
{json.dumps(prev_questions, indent=2)}

Focus board issues:
{json.dumps([i.get('note', str(i)) if isinstance(i, dict) else str(i) for i in ctx.focus_board.get('issues', [])[-5:]], indent=2)}

Generate 2-4 specific, useful questions to ask the human that would help
advance the project. Questions should be:
- Actionable (the answer directly helps move forward)
- Specific (not vague "what do you think?")
- Non-blocking (work can continue without answers)

Also write a brief summary of what we learned from any answered questions.

Format your response as:

## Answers Summary
(what we learned from answered questions, or "No new answers" if none)

## New Questions
1. [question]
2. [question]
...

## Working Assumptions
(what we'll assume if the human doesn't answer)
"""
        content = self._llm_generate(ctx.agent, prompt)

        # Extract questions
        questions: List[str] = []
        for line in content.split("\n"):
            line = line.strip()
            if re.match(r"^\d+\.\s+", line):
                q = re.sub(r"^\d+\.\s+", "", line).strip()
                if q and len(q) > 10:
                    questions.append(q)

        filename = f"interview_{_now_stamp()}.md"
        header = f"# Interview — Iteration {ctx.iteration}\n\n"
        header += f"**Focus:** {ctx.focus}\n**Time:** {_now_iso()}\n\n---\n\n"
        filepath = self._write_artifact(ctx.project_path, "interviews", filename,
                                        header + content)

        ctx.stream_output(f"📝 {len(questions)} questions prepared", "info")

        return StageResult(
            content=content,
            artifacts=[filepath],
            questions=questions,
            board_updates={"progress": [f"Interview: {len(questions)} questions asked (iter {ctx.iteration})"]}
            if questions else {},
        )


class DiscoveryStage(Stage):
    """
    Uses tools to research and gather information about the project.
    Actually runs tools (web search, file reading, etc.) and writes
    a research report with findings.

    Produces: research/<timestamp>.md
    """
    name = "discovery"
    description = "Use tools to research and gather information"
    icon = "🔍"

    def execute(self, ctx: StageContext) -> StageResult:
        ctx.stream_output(f"{self.icon} Discovery stage — researching…", "info")

        tool_names = [t.name for t in ctx.agent.tools] if hasattr(ctx.agent, "tools") else []
        prev_content = ctx.previous_result.content[:2000] if ctx.previous_result else ""

        # Ask LLM what to research and which tools to use
        prompt = f"""You are researching for project: **{ctx.focus}**

Recent analysis:
{prev_content}

Known issues: {json.dumps([i.get('note', str(i)) if isinstance(i, dict) else str(i) for i in ctx.focus_board.get('issues', [])[-5:]], indent=2)}

Available tools: {tool_names[:25]}

Identify 2-4 specific research tasks. For each, create a tool execution plan.

Respond with a JSON array:
[
  {{
    "topic": "What we're investigating",
    "why": "Why this matters",
    "steps": [
      {{"tool": "tool_name", "input": "input"}},
      ...
    ]
  }},
  ...
]

Focus on tasks that will produce USEFUL INFORMATION, not just metadata.
If no relevant tools exist, use "NONE" as tool and explain what we'd need.

JSON only:
"""
        try:
            raw = self._llm_generate(ctx.agent, prompt)
            tasks = json.loads(raw.strip().strip("`").lstrip("json").strip())
            if not isinstance(tasks, list):
                tasks = [tasks]
        except (json.JSONDecodeError, ValueError):
            ctx.stream_output("⚠️ Could not parse research plan", "warning")
            tasks = []

        report_lines = [
            f"# Discovery Report — Iteration {ctx.iteration}\n",
            f"**Focus:** {ctx.focus}\n**Time:** {_now_iso()}\n\n---\n",
        ]
        all_findings: List[str] = []

        for task_idx, task in enumerate(tasks[:4], 1):
            topic = task.get("topic", f"Research task {task_idx}")
            why = task.get("why", "")
            steps = task.get("steps", [])

            ctx.stream_output(f"\n🔎 [{task_idx}] {topic}", "info")
            report_lines.append(f"\n## {task_idx}. {topic}\n\n**Why:** {why}\n\n")

            if not steps or (len(steps) == 1 and steps[0].get("tool") == "NONE"):
                report_lines.append("*No applicable tools — noted for future investigation.*\n")
                continue

            # Execute tool steps
            tool_outputs: Dict[str, str] = {}
            for step_num, step in enumerate(steps[:3], 1):
                tool_name = step.get("tool", "")
                raw_input = step.get("input", "")

                tool = next((t for t in ctx.agent.tools if t.name == tool_name), None)
                if not tool:
                    report_lines.append(f"- ❌ Tool not found: {tool_name}\n")
                    continue

                try:
                    parsed = ActionStage._parse_tool_input(raw_input)
                    resolved = ActionStage._resolve_placeholders(
                        parsed, step_num, tool_outputs
                    )
                    result = ActionStage._run_tool(tool, tool_name, resolved)

                    result_str = ""
                    try:
                        for chunk in result:
                            result_str += str(chunk)
                    except TypeError:
                        result_str = str(result)

                    tool_outputs[f"step_{step_num}"] = result_str
                    ctx.stream_output(f"  ✅ {tool_name} → {len(result_str)} chars", "success")

                    # Truncate very long results for the report
                    display = result_str[:2000]
                    report_lines.append(
                        f"### {tool_name}\n```\n{display}\n```\n\n"
                    )
                    all_findings.append(f"[{topic}] {result_str[:500]}")

                except Exception as e:
                    report_lines.append(f"- ❌ {tool_name}: {e}\n")

        # Synthesise findings
        if all_findings:
            synth_prompt = f"""Summarise these research findings for project "{ctx.focus}":

{chr(10).join(all_findings[:5])}

Write a 200-400 word synthesis. What did we learn? What are the key takeaways?
What should we do with this information?
"""
            synthesis = self._llm_generate(ctx.agent, synth_prompt)
            report_lines.append(f"\n## Synthesis\n\n{synthesis}\n")
        else:
            report_lines.append("\n## Synthesis\n\n*No tool results to synthesise.*\n")

        report_content = "\n".join(report_lines)
        filename = f"research_{_now_stamp()}.md"
        filepath = self._write_artifact(ctx.project_path, "research", filename,
                                        report_content)

        ctx.stream_output(f"📝 Wrote research report: {filepath}", "success")

        board_updates: Dict[str, List[str]] = {"progress": [], "ideas": []}
        if all_findings:
            board_updates["progress"].append(
                f"Discovery: researched {len(tasks)} topics, {len(all_findings)} findings"
            )

        return StageResult(
            content=report_content,
            artifacts=[filepath],
            board_updates=board_updates,
        )


class ReviewStage(Stage):
    """
    Reviews all work done so far, evaluates progress, identifies gaps,
    and produces a progress report. Used by steering to redirect.

    Produces: reviews/<timestamp>.md
    """
    name = "review"
    description = "Evaluate progress, identify gaps, produce a status report"
    icon = "📊"

    def execute(self, ctx: StageContext) -> StageResult:
        ctx.stream_output(f"{self.icon} Review stage…", "info")

        # Read recent artifacts
        recent_files = []
        for category in ["thoughts", "plans", "actions", "research"]:
            cat_dir = ctx.project_path / category
            if cat_dir.exists():
                files = sorted(cat_dir.iterdir(), key=lambda f: f.stat().st_mtime,
                               reverse=True)[:2]
                for f in files:
                    try:
                        content = f.read_text(encoding="utf-8")[:1500]
                        recent_files.append(f"--- {f.name} ---\n{content}\n")
                    except Exception:
                        pass

        board_json = json.dumps(
            {k: [i.get("note", str(i))[:100] if isinstance(i, dict) else str(i)[:100]
                 for i in v[-5:]]
             for k, v in ctx.focus_board.items() if v},
            indent=2
        )

        prompt = f"""You are reviewing the project: **{ctx.focus}**

Iteration {ctx.iteration}.

RECENT WORK:
{chr(10).join(recent_files[:6])[:4000]}

FOCUS BOARD:
{board_json}

Write a thorough progress review covering:

## Progress Summary
What has been accomplished? Be specific.

## Quality Assessment
Is the work so far good quality? What's strong, what's weak?

## Gaps & Missing Pieces
What hasn't been addressed? What's incomplete?

## Recommendations
Concrete recommendations for the next iteration.
Should we continue the current direction or pivot?

## Board Cleanup
List any focus board items that should be:
- Moved to completed
- Removed (no longer relevant)
- Added (new items)

Write 400-800 words. Be honest and critical.
"""
        content = self._llm_generate(ctx.agent, prompt, use_deep=True)

        filename = f"review_{_now_stamp()}.md"
        header = f"# Review — Iteration {ctx.iteration}\n\n"
        header += f"**Focus:** {ctx.focus}\n**Time:** {_now_iso()}\n\n---\n\n"
        filepath = self._write_artifact(ctx.project_path, "reviews", filename,
                                        header + content)

        ctx.stream_output(f"📝 Wrote review: {filepath}", "success")

        return StageResult(
            content=content,
            artifacts=[filepath],
            board_updates={"progress": [f"Review completed (iter {ctx.iteration})"]},
        )


# ===================================================================
# STEERING ENGINE
# ===================================================================

class SteeringEngine:
    """
    After each stage, an LLM decides what to do next.
    This replaces the rigid stage ordering with dynamic routing.
    """

    def __init__(self, agent):
        self.agent = agent

    def decide_next(self, ctx: StageContext,
                    available_stages: List[str],
                    completed_in_iteration: List[str],
                    max_stages_per_iteration: int = 6) -> Optional[str]:
        """
        Decide the next stage to run, or None to end the iteration.
        Uses the fast LLM for quick decisions.
        """
        if len(completed_in_iteration) >= max_stages_per_iteration:
            return None

        prev_name = ctx.previous_stage_name or "none"
        prev_summary = ""
        if ctx.previous_result:
            prev_summary = ctx.previous_result.content[:500]

        board_summary = {k: len(v) for k, v in ctx.focus_board.items() if v}

        prompt = f"""You are steering an iterative AI workflow for: {ctx.focus}

Iteration {ctx.iteration}. Stages completed this iteration: {completed_in_iteration}
Max stages per iteration: {max_stages_per_iteration}

Last stage: {prev_name}
Last output summary: {prev_summary[:400]}

Focus board sizes: {board_summary}

Available stages: {available_stages}

Stage descriptions:
- thought: Reflect, analyse memory, identify patterns (good early in iteration)
- planning: Create structured plans with priorities (good after thought)
- action: Execute plans using tools (good after planning, needs next_steps on board)
- interview: Ask the human questions, non-blocking (good when stuck or need clarity)
- discovery: Research using tools (good when lacking information)
- review: Evaluate progress, identify gaps (good at end of iteration)

Choose the BEST next stage, or "done" to end this iteration.
Consider:
1. Don't repeat a stage unnecessarily
2. After thought → planning or discovery usually
3. After planning → action if steps exist, or interview if questions
4. After action → review or thought
5. After interview → planning (incorporate answers)
6. End with review if enough work has been done

Respond with ONLY the stage name (one word) or "done":
"""
        try:
            raw = ""
            for chunk in self.agent.fast_llm.stream(prompt):
                raw += extract_chunk_text(chunk)

            decision = raw.strip().lower().split()[0].strip(".,!\"'")

            if decision == "done" or decision not in available_stages:
                if decision != "done":
                    # Try to find a partial match
                    for s in available_stages:
                        if s.startswith(decision[:4]):
                            return s
                return None

            return decision

        except Exception as e:
            print(f"[Steering] Error: {e}")
            # Fallback: cycle through stages in order
            for s in available_stages:
                if s not in completed_in_iteration:
                    return s
            return None


# ===================================================================
# HUMAN BRIDGE — non-blocking question queue
# ===================================================================

class HumanBridge:
    """
    Manages questions to/from the human. Non-blocking: stages can ask
    questions and check for answers, but never wait synchronously.
    """

    def __init__(self):
        self.questions: Dict[str, HumanQuestion] = {}
        self._send_callback: Optional[Callable] = None  # Set to telegram/WS sender
        self._lock = threading.Lock()

    def set_sender(self, callback: Callable[[str, str], None]):
        """Set callback: callback(question_id, question_text)"""
        self._send_callback = callback

    def ask(self, text: str, context: str = "", stage: str = "",
            iteration: int = 0) -> str:
        """Queue a question. Returns question_id."""
        qid = f"q_{int(time.time()*1000)}_{hashlib.md5(text.encode()).hexdigest()[:6]}"
        q = HumanQuestion(
            question_id=qid, text=text, context=context,
            stage=stage, iteration=iteration,
        )
        with self._lock:
            self.questions[qid] = q

        # Try to send via callback
        if self._send_callback:
            try:
                self._send_callback(qid, text)
            except Exception as e:
                print(f"[HumanBridge] Send failed: {e}")

        return qid

    def answer(self, question_id: str, answer_text: str):
        """Provide an answer to a question."""
        with self._lock:
            if question_id in self.questions:
                q = self.questions[question_id]
                q.answer = answer_text
                q.status = QuestionStatus.ANSWERED
                q.answered_at = _now_iso()

    def get_answers(self) -> Dict[str, str]:
        """Get all answered questions as {question_id: answer}."""
        with self._lock:
            return {
                qid: q.answer
                for qid, q in self.questions.items()
                if q.status == QuestionStatus.ANSWERED and q.answer
            }

    def get_pending(self) -> List[HumanQuestion]:
        """Get unanswered questions."""
        with self._lock:
            return [q for q in self.questions.values()
                    if q.status == QuestionStatus.PENDING]

    def get_all(self) -> List[Dict[str, Any]]:
        """Get all questions as dicts (for API responses)."""
        with self._lock:
            return [
                {
                    "question_id": q.question_id,
                    "text": q.text,
                    "context": q.context,
                    "status": q.status.value,
                    "answer": q.answer,
                    "asked_at": q.asked_at,
                    "answered_at": q.answered_at,
                    "stage": q.stage,
                    "iteration": q.iteration,
                }
                for q in self.questions.values()
            ]


# ===================================================================
# PROJECT MANAGER
# ===================================================================

class ProjectManager:
    """Manages the project directory structure for a focus."""

    SUBDIRS = [
        "thoughts", "plans", "actions", "research",
        "interviews", "reviews", "artifacts", "focus_boards",
    ]

    def __init__(self, base_dir: str = "./Output/projects"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def get_project_path(self, focus: str) -> Path:
        safe = _sanitize_filename(focus, 100)
        return self.base_dir / safe

    def ensure_structure(self, focus: str) -> Path:
        root = self.get_project_path(focus)
        for sub in self.SUBDIRS:
            (root / sub).mkdir(parents=True, exist_ok=True)

        meta_file = root / "project.json"
        if not meta_file.exists():
            meta = {
                "focus": focus,
                "created_at": _now_iso(),
                "iteration_count": 0,
            }
            meta_file.write_text(json.dumps(meta, indent=2))
        return root

    def update_metadata(self, focus: str, updates: dict):
        root = self.get_project_path(focus)
        meta_file = root / "project.json"
        try:
            meta = json.loads(meta_file.read_text())
        except Exception:
            meta = {"focus": focus}
        meta.update(updates)
        meta["last_updated"] = _now_iso()
        meta_file.write_text(json.dumps(meta, indent=2))


# ===================================================================
# MAIN CLASS — ProactiveFocusManager v2
# ===================================================================

class ProactiveFocusManager:
    """
    Modular iterative workflow engine for LLM-driven project work.

    Drop-in replacement: preserves all API-facing attributes and methods
    used by the FastAPI router (focus.py).
    """

    def __init__(
        self,
        agent,
        hybrid_memory=None,
        proactive_interval: int = 60 * 10,
        cpu_threshold: float = 70.0,
        focus_boards_dir: str = "./Output/projects/focus_boards",
        auto_restore: bool = True,
    ):
        self.agent = agent
        self.hybrid_memory = hybrid_memory

        # Core state
        self.focus: Optional[str] = None
        self.project_id: Optional[str] = None
        self.focus_board: Dict[str, list] = self._empty_board()

        # Config
        self.proactive_interval = proactive_interval
        self.cpu_threshold = cpu_threshold
        self.focus_boards_dir = focus_boards_dir
        os.makedirs(focus_boards_dir, exist_ok=True)

        # Iteration tracking
        self.iteration_count: int = 0
        self.workflow_active: bool = False
        self.running: bool = False

        # Thread management
        self.thread: Optional[threading.Thread] = None
        self.workflow_thread: Optional[threading.Thread] = None
        self.pause_event = threading.Event()
        self.pause_event.set()

        # WebSocket / broadcast
        self._websockets: list = []
        self.proactive_callback: Optional[Callable[[str], None]] = None
        self.latest_conversation: str = ""

        # Stage tracking for WebSocket UI (backward compat)
        self.current_stage: Optional[str] = None
        self.current_activity: Optional[str] = None
        self.stage_progress: int = 0
        self.stage_total: int = 0

        # Streaming state
        self.current_thought: str = ""
        self.thought_streaming: bool = False

        # --- New modular components ---
        self.project_manager = ProjectManager()
        self.human_bridge = HumanBridge()
        self.steering = SteeringEngine(agent)

        # Stage registry — users can add/remove
        self._stages: Dict[str, Stage] = {}
        self._stage_order: List[str] = []  # default pipeline order
        self._register_default_stages()

        # Workflow config
        self.max_stages_per_iteration: int = 6
        self.iteration_interval: int = 300

        # Auto-restore
        if auto_restore and hybrid_memory:
            self._restore_last_focus()

    # ------------------------------------------------------------------
    # Stage Registry
    # ------------------------------------------------------------------

    def _register_default_stages(self):
        """Register the built-in stages."""
        defaults = [
            ThoughtStage(),
            PlanningStage(),
            ActionStage(),
            InterviewStage(),
            DiscoveryStage(),
            ReviewStage(),
        ]
        for s in defaults:
            self._stages[s.name] = s
        self._stage_order = [s.name for s in defaults]

    def register_stage(self, stage: Stage):
        """Add a custom stage to the registry."""
        self._stages[stage.name] = stage
        if stage.name not in self._stage_order:
            self._stage_order.append(stage.name)
        print(f"[FocusManager] Registered stage: {stage.name}")

    def unregister_stage(self, name: str):
        """Remove a stage from the registry."""
        self._stages.pop(name, None)
        if name in self._stage_order:
            self._stage_order.remove(name)

    def get_available_stages(self) -> List[Dict[str, str]]:
        """List available stages with metadata."""
        return [
            {"name": s.name, "description": s.description, "icon": s.icon}
            for s in self._stages.values()
        ]

    def set_stage_order(self, order: List[str]):
        """Set the default stage pipeline order."""
        valid = [n for n in order if n in self._stages]
        self._stage_order = valid

    # ------------------------------------------------------------------
    # Focus Management (backward compatible)
    # ------------------------------------------------------------------

    @staticmethod
    def _empty_board() -> Dict[str, list]:
        return {
            "progress": [], "next_steps": [], "issues": [],
            "ideas": [], "actions": [], "completed": [],
        }

    def set_focus(self, focus: str, project_name: Optional[str] = None,
                  create_project: bool = True):
        """Set focus and prepare project directory."""
        # Check for existing board
        existing = self._find_matching_focus_board(focus)
        if existing:
            if self.load_focus_board(existing["filename"]):
                self._broadcast_sync("focus_changed", {
                    "focus": focus, "project_id": self.project_id,
                    "loaded_existing": True,
                })
                return

        # Save current board if switching
        old = self.focus
        if old and old != focus:
            self.save_focus_board()

        self.focus = focus
        self.focus_board = self._empty_board()
        self.iteration_count = 0

        # Ensure project directory
        self.project_manager.ensure_structure(focus)

        # Link to graph memory
        if self.hybrid_memory and (project_name or create_project):
            pname = project_name or focus
            self.project_id = self._ensure_project(pname, focus)

        # Save initial empty board
        self.save_focus_board()

        # Memory record
        if hasattr(self.agent, "mem") and hasattr(self.agent, "sess"):
            meta = {"topic": "focus"}
            if self.project_id:
                meta["project_id"] = self.project_id
            self.agent.mem.add_session_memory(
                self.agent.sess.id,
                f"[FocusManager] Focus set to: {focus}",
                "Thought", meta,
            )

        self._broadcast_sync("focus_changed", {
            "focus": focus, "project_id": self.project_id,
            "loaded_existing": False,
        })
        print(f"[FocusManager] Focus set to: {focus}")

    def clear_focus(self):
        if self.focus:
            self.save_focus_board()
        self.focus = None
        self.project_id = None
        self.workflow_active = False
        self.stop()
        self._broadcast_sync("focus_cleared", {})

    def update_latest_conversation(self, conversation: str):
        self.latest_conversation = conversation

    # ------------------------------------------------------------------
    # Focus Board Operations (backward compatible)
    # ------------------------------------------------------------------

    def add_to_focus_board(self, category: str, note: str,
                           metadata: Optional[Dict[str, Any]] = None):
        if category not in self.focus_board:
            self.focus_board[category] = []
        item = {
            "note": note,
            "timestamp": _now_iso(),
            "metadata": metadata or {},
        }
        self.focus_board[category].append(item)
        self._broadcast_sync("board_updated", {
            "category": category, "item": item,
        })

    def update_focus_board_item(self, category: str, index: int,
                                new_note: str, new_metadata=None):
        if category in self.focus_board and 0 <= index < len(self.focus_board[category]):
            old = self.focus_board[category][index]
            self.focus_board[category][index] = {
                "note": new_note,
                "timestamp": _now_iso(),
                "metadata": new_metadata or old.get("metadata", {}),
                "previous_note": old.get("note"),
            }

    def move_to_completed(self, category: str, index: int):
        if category in self.focus_board and 0 <= index < len(self.focus_board[category]):
            item = self.focus_board[category].pop(index)
            item["completed_at"] = _now_iso()
            item["original_category"] = category
            self.focus_board["completed"].append(item)

    # ------------------------------------------------------------------
    # Save / Load / List Boards (backward compatible)
    # ------------------------------------------------------------------

    def save_focus_board(self, filename: Optional[str] = None) -> Optional[str]:
        if not self.focus:
            return None
        if not filename:
            safe = _sanitize_filename(self.focus, 50)
            filename = f"{safe}_{_now_stamp()}.json"
        filepath = os.path.join(self.focus_boards_dir, filename)

        data = {
            "focus": self.focus,
            "project_id": self.project_id,
            "created_at": _now_iso(),
            "iteration_count": self.iteration_count,
            "board": self.focus_board,
            "metadata": {
                "session_id": self.agent.sess.id
                if hasattr(self.agent, "sess") else None,
            },
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        # Also save snapshot to project dir
        try:
            proj = self.project_manager.get_project_path(self.focus)
            snap = proj / "focus_boards" / filename
            snap.parent.mkdir(parents=True, exist_ok=True)
            with open(snap, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

        self._broadcast_sync("board_saved", {"filepath": filepath})
        return filepath

    def load_focus_board(self, filename: str) -> bool:
        filepath = os.path.join(self.focus_boards_dir, filename)
        if not os.path.exists(filepath):
            return False
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.focus = data.get("focus")
        self.project_id = data.get("project_id")
        self.focus_board = data.get("board", self._empty_board())
        self.iteration_count = data.get("iteration_count", 0)
        if self.focus:
            self.project_manager.ensure_structure(self.focus)
        self._broadcast_sync("board_loaded", {"filepath": filepath, "focus": self.focus})
        return True

    def list_saved_boards(self) -> List[Dict[str, Any]]:
        boards = []
        for fn in os.listdir(self.focus_boards_dir):
            if fn.endswith(".json"):
                fp = os.path.join(self.focus_boards_dir, fn)
                try:
                    with open(fp, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    boards.append({
                        "filename": fn,
                        "focus": data.get("focus"),
                        "created_at": data.get("created_at"),
                        "project_id": data.get("project_id"),
                        "iteration_count": data.get("iteration_count", 0),
                    })
                except Exception:
                    pass
        return sorted(boards, key=lambda x: x.get("created_at", ""), reverse=True)

    def _find_matching_focus_board(self, focus: str) -> Optional[Dict[str, Any]]:
        fl = focus.lower().strip()
        for board in self.list_saved_boards():
            sf = (board.get("focus") or "").lower().strip()
            if sf == fl:
                return board
            if fl in sf or sf in fl:
                return board
        return None

    # ------------------------------------------------------------------
    # Graph Memory Helpers
    # ------------------------------------------------------------------

    def _ensure_project(self, name: str, description: str) -> str:
        pid = f"project_{_sanitize_filename(name.lower(), 60)}"
        if self.hybrid_memory:
            self.hybrid_memory.upsert_entity(
                entity_id=pid, etype="project", labels=["Project"],
                properties={
                    "name": name, "description": description,
                    "created_at": _now_iso(), "status": "active",
                },
            )
            if hasattr(self.agent, "sess") and self.agent.sess:
                self.hybrid_memory.link_session_focus(self.agent.sess.id, [pid])
        return pid

    def _restore_last_focus(self):
        """Restore most recent focus from saved boards."""
        boards = self.list_saved_boards()
        if boards:
            latest = boards[0]
            self.load_focus_board(latest["filename"])
            print(f"[FocusManager] Restored: {self.focus}")

    # ------------------------------------------------------------------
    # Broadcasting (backward compatible)
    # ------------------------------------------------------------------

    async def broadcast_to_websockets(self, event_type: str, data: dict):
        if not self._websockets:
            return
        msg = {"type": event_type, "data": data, "timestamp": _now_iso()}
        dead = []
        for ws in self._websockets:
            try:
                await ws.send_json(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._websockets.remove(ws)

    def _broadcast_sync(self, event_type: str, data: dict):
        if not self._websockets:
            return
        try:
            try:
                loop = asyncio.get_running_loop()
                asyncio.ensure_future(self.broadcast_to_websockets(event_type, data))
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.broadcast_to_websockets(event_type, data))
                loop.close()
        except Exception:
            pass

    def _stream_output(self, text: str, category: str = "info"):
        self._broadcast_sync("stream_output", {
            "text": text, "category": category, "timestamp": _now_iso(),
        })
        # Also print for server logs
        prefix = {"success": "✅", "warning": "⚠️", "error": "❌"}.get(category, "ℹ️")
        print(f"[FocusManager] {prefix} {text}")

    def _set_stage(self, stage: str, activity: str = "", total: int = 0):
        self.current_stage = stage
        self.current_activity = activity
        self.stage_progress = 0
        self.stage_total = total
        self._broadcast_sync("stage_update", {
            "stage": stage, "activity": activity,
            "progress": 0, "total": total,
        })

    def _update_progress(self, inc: int = 1):
        self.stage_progress += inc
        self._broadcast_sync("stage_progress", {
            "stage": self.current_stage,
            "progress": self.stage_progress,
            "total": self.stage_total,
        })

    def _clear_stage(self):
        self.current_stage = None
        self.current_activity = None
        self.stage_progress = 0
        self.stage_total = 0
        self._broadcast_sync("stage_cleared", {})

    # ------------------------------------------------------------------
    # CORE WORKFLOW ENGINE
    # ------------------------------------------------------------------

    def iterative_workflow(
        self,
        max_iterations: Optional[int] = None,
        iteration_interval: int = 300,
        auto_execute: bool = True,
        stages: Optional[List[str]] = None,
        use_steering: bool = True,
        max_stages_per_iteration: int = 6,
        **kwargs,  # absorb legacy kwargs
    ):
        """
        Main iterative workflow loop.

        Args:
            max_iterations: Stop after N iterations (None = infinite)
            iteration_interval: Seconds between iterations
            auto_execute: Whether to include action stage
            stages: Explicit stage list per iteration (overrides steering)
            use_steering: Let LLM decide stage order dynamically
            max_stages_per_iteration: Cap on stages per iteration
        """
        if not self.focus:
            self._stream_output("❌ No focus set — cannot start workflow", "error")
            return

        self.workflow_active = True
        self.iteration_interval = iteration_interval
        self.max_stages_per_iteration = max_stages_per_iteration
        iteration = 0

        # Determine available stages
        available = stages or list(self._stages.keys())
        if not auto_execute and "action" in available:
            available.remove("action")

        project_path = self.project_manager.ensure_structure(self.focus)

        self._stream_output("=" * 60, "info")
        self._stream_output("🚀 WORKFLOW STARTED", "success")
        self._stream_output(f"Focus: {self.focus}", "info")
        self._stream_output(f"Stages: {available}", "info")
        self._stream_output(f"Steering: {'LLM' if use_steering else 'sequential'}", "info")
        self._stream_output(f"Interval: {iteration_interval}s", "info")
        self._stream_output("=" * 60, "info")

        while (max_iterations is None or iteration < max_iterations) and self.workflow_active:
            iteration += 1
            self.iteration_count = iteration

            self._stream_output(f"\n{'='*60}", "info")
            self._stream_output(f"🔄 ITERATION {iteration}", "info")
            self._stream_output(f"{'='*60}", "info")

            self.project_manager.update_metadata(self.focus, {
                "iteration_count": iteration,
            })

            completed_stages: List[str] = []
            last_result: Optional[StageResult] = None
            last_stage_name: Optional[str] = None

            try:
                if use_steering:
                    # LLM-steered: pick stages dynamically
                    while len(completed_stages) < max_stages_per_iteration and self.workflow_active:
                        # Build context for steering
                        ctx = self._build_context(
                            project_path, iteration, last_stage_name, last_result,
                        )

                        next_stage = self.steering.decide_next(
                            ctx, available, completed_stages, max_stages_per_iteration,
                        )

                        if next_stage is None:
                            self._stream_output("🏁 Steering: iteration complete", "info")
                            break

                        result = self._run_stage(next_stage, project_path, iteration,
                                                 last_stage_name, last_result)
                        if result:
                            last_result = result
                            last_stage_name = next_stage
                            completed_stages.append(next_stage)
                            self._apply_board_updates(result)
                            self._dispatch_questions(result, next_stage, iteration)

                        time.sleep(1)  # brief pause between stages

                else:
                    # Sequential: run stages in order
                    for stage_name in available:
                        if not self.workflow_active:
                            break

                        result = self._run_stage(
                            stage_name, project_path, iteration,
                            last_stage_name, last_result,
                        )
                        if result:
                            last_result = result
                            last_stage_name = stage_name
                            completed_stages.append(stage_name)
                            self._apply_board_updates(result)
                            self._dispatch_questions(result, stage_name, iteration)

                        time.sleep(1)

                # Save checkpoint
                self.save_focus_board()
                self._stream_output(f"💾 Checkpoint saved", "success")
                self._stream_output(f"Completed stages: {completed_stages}", "info")

                self._broadcast_sync("iteration_complete", {
                    "iteration": iteration,
                    "stages": completed_stages,
                })

                # Wait
                if self.workflow_active and (max_iterations is None or iteration < max_iterations):
                    self._stream_output(f"⏳ Waiting {iteration_interval}s…", "info")
                    for _ in range(iteration_interval):
                        if not self.workflow_active:
                            break
                        time.sleep(1)

            except Exception as e:
                self._stream_output(f"❌ Error in iteration {iteration}: {e}", "error")
                traceback.print_exc()
                time.sleep(30)

        self.workflow_active = False
        self._stream_output(f"\n{'='*60}", "info")
        self._stream_output(f"✅ WORKFLOW COMPLETE — {iteration} iterations", "success")
        self._stream_output(f"{'='*60}", "info")

    def _build_context(self, project_path: Path, iteration: int,
                       prev_stage: Optional[str],
                       prev_result: Optional[StageResult]) -> StageContext:
        return StageContext(
            focus=self.focus,
            project_id=self.project_id,
            project_path=project_path,
            focus_board=self.focus_board,
            iteration=iteration,
            previous_stage_name=prev_stage,
            previous_result=prev_result,
            human_answers=self.human_bridge.get_answers(),
            agent=self.agent,
            hybrid_memory=self.hybrid_memory,
            broadcast=self._broadcast_sync,
            stream_output=self._stream_output,
        )

    def _run_stage(self, stage_name: str, project_path: Path,
                   iteration: int, prev_stage: Optional[str],
                   prev_result: Optional[StageResult]) -> Optional[StageResult]:
        """Execute a single stage with full broadcasting."""
        stage = self._stages.get(stage_name)
        if not stage:
            self._stream_output(f"⚠️ Unknown stage: {stage_name}", "warning")
            return None

        ctx = self._build_context(project_path, iteration, prev_stage, prev_result)

        # Pre-check
        should, reason = stage.should_run(ctx)
        if not should and stage.skippable:
            self._stream_output(f"⏭️ Skipping {stage_name}: {reason}", "info")
            return None

        self._set_stage(stage_name, stage.description, 3)
        self._stream_output(f"\n{stage.icon} STAGE: {stage.name.upper()}", "info")
        self._stream_output(f"  {stage.description}", "info")

        self._broadcast_sync("stage_started", {"stage": stage_name})

        try:
            result = stage.execute(ctx)
            self._update_progress()

            # Summary
            artifact_count = len(result.artifacts)
            content_len = len(result.content)
            q_count = len(result.questions)
            self._stream_output(
                f"✅ {stage_name} complete: {content_len} chars, "
                f"{artifact_count} artifacts, {q_count} questions",
                "success",
            )

            self._broadcast_sync("stage_completed", {
                "stage": stage_name,
                "content_length": content_len,
                "artifacts": result.artifacts,
                "questions": result.questions,
            })

        except Exception as e:
            self._stream_output(f"❌ {stage_name} failed: {e}", "error")
            traceback.print_exc()
            self._broadcast_sync("stage_error", {
                "stage": stage_name, "error": str(e),
            })
            result = None

        self._clear_stage()
        return result

    def _apply_board_updates(self, result: StageResult):
        """Apply a stage's board updates to the focus board."""
        for category, notes in result.board_updates.items():
            for note in notes:
                self.add_to_focus_board(category, note)

        # Move completed items
        if "completed" in result.board_updates:
            for note in result.board_updates["completed"]:
                # Find and move matching items from next_steps
                for i, item in enumerate(self.focus_board.get("next_steps", [])):
                    item_note = item.get("note", "") if isinstance(item, dict) else str(item)
                    if item_note == note:
                        self.move_to_completed("next_steps", i)
                        break

    def _dispatch_questions(self, result: StageResult, stage: str, iteration: int):
        """Send any questions from the stage result to the human bridge."""
        for q_text in result.questions:
            qid = self.human_bridge.ask(
                q_text, context=self.focus, stage=stage, iteration=iteration,
            )
            self._broadcast_sync("question_asked", {
                "question_id": qid, "text": q_text,
                "stage": stage, "iteration": iteration,
            })

            # Also try Telegram if available
            if hasattr(self.agent, "telegram_notify"):
                try:
                    self.agent.telegram_notify(
                        f"❓ <b>Question from Vera</b>\n\n"
                        f"<i>Project: {self.focus}</i>\n\n"
                        f"{q_text}\n\n"
                        f"<code>Reply with: /answer {qid} your answer</code>"
                    )
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Individual Stage Triggers (backward compatible API)
    # ------------------------------------------------------------------

    def generate_ideas_stage(self, context=None) -> List[str]:
        return self._run_individual_stage("thought", context)

    def generate_next_steps_stage(self, context=None) -> List[str]:
        return self._run_individual_stage("planning", context)

    def generate_actions_stage(self, context=None) -> List[str]:
        return self._run_individual_stage("action", context)

    def execute_actions_stage(self, max_executions=2, priority_filter="high") -> int:
        """Backward-compatible action execution."""
        if not self.focus:
            return 0
        project_path = self.project_manager.ensure_structure(self.focus)
        result = self._run_stage("action", project_path, self.iteration_count, None, None)
        return len(result.tool_results) if result else 0

    def _run_individual_stage(self, stage_name: str, context=None) -> list:
        """Run a single stage and return board updates as a list."""
        if not self.focus:
            return []
        project_path = self.project_manager.ensure_structure(self.focus)
        result = self._run_stage(stage_name, project_path, self.iteration_count, None, None)
        if result:
            self._apply_board_updates(result)
            self._dispatch_questions(result, stage_name, self.iteration_count)
            # Return all new notes
            all_notes = []
            for notes in result.board_updates.values():
                all_notes.extend(notes)
            return all_notes
        return []

    # Backward compat aliases
    def generate_ideas(self, context=None) -> List[str]:
        return self.generate_ideas_stage(context)

    def generate_next_steps(self, context=None) -> List[str]:
        return self.generate_next_steps_stage(context)

    def generate_actions(self, context=None) -> list:
        return self.generate_actions_stage(context)

    def handoff_to_toolchain(self, action: Dict[str, Any]) -> Optional[str]:
        """Execute a single action through the toolchain."""
        if not self.focus:
            return None
        project_path = self.project_manager.ensure_structure(self.focus)
        goal = action.get("goal", action.get("description", str(action)))

        # Build a minimal plan and execute via ActionStage
        stage = self._stages.get("action")
        if not stage:
            return None

        ctx = self._build_context(project_path, self.iteration_count, None, None)
        # Temporarily add goal to next_steps
        self.add_to_focus_board("next_steps", goal)
        result = stage.execute(ctx)
        if result:
            self._apply_board_updates(result)
            return result.content
        return None

    # ------------------------------------------------------------------
    # Proactive Thought (backward compatible)
    # ------------------------------------------------------------------

    def trigger_proactive_thought(self) -> Optional[str]:
        if not self.focus:
            return None
        project_path = self.project_manager.ensure_structure(self.focus)
        result = self._run_stage("thought", project_path, self.iteration_count, None, None)
        if result:
            self._apply_board_updates(result)
            if self.proactive_callback:
                self.proactive_callback(result.content)
            return result.content
        return None

    def trigger_proactive_thought_async(self):
        t = threading.Thread(target=self.trigger_proactive_thought, daemon=True)
        t.start()

    # ------------------------------------------------------------------
    # Start / Stop (backward compatible)
    # ------------------------------------------------------------------

    def start(self):
        if not self.running and self.focus:
            self.running = True
            self.thread = threading.Thread(
                target=self._proactive_loop, daemon=True,
            )
            self.thread.start()
            self._broadcast_sync("focus_started", {"focus": self.focus})

    def stop(self):
        self.running = False
        self.workflow_active = False
        if self.thread:
            self.thread.join(timeout=2)
            self.thread = None
        self._broadcast_sync("focus_stopped", {})

    def start_workflow_thread(self, max_iterations=None, iteration_interval=300,
                              auto_execute=True, **kwargs):
        if hasattr(self, "workflow_thread") and self.workflow_thread and self.workflow_thread.is_alive():
            print("[FocusManager] Workflow already running")
            return
        self.workflow_thread = threading.Thread(
            target=self.iterative_workflow,
            kwargs={
                "max_iterations": max_iterations,
                "iteration_interval": iteration_interval,
                "auto_execute": auto_execute,
                **kwargs,
            },
            daemon=True,
        )
        self.workflow_thread.start()

    def _proactive_loop(self):
        """Background proactive thought loop."""
        while self.running:
            cpu = psutil.cpu_percent(interval=0.1)
            if cpu >= self.cpu_threshold:
                time.sleep(5)
                continue
            self.trigger_proactive_thought()
            time.sleep(self.proactive_interval)

    # ------------------------------------------------------------------
    # Human Bridge API
    # ------------------------------------------------------------------

    def answer_question(self, question_id: str, answer: str):
        """Provide an answer to a pending question."""
        self.human_bridge.answer(question_id, answer)
        self._broadcast_sync("question_answered", {
            "question_id": question_id, "answer": answer,
        })

    def get_pending_questions(self) -> List[Dict[str, Any]]:
        return [
            {"question_id": q.question_id, "text": q.text,
             "stage": q.stage, "iteration": q.iteration, "asked_at": q.asked_at}
            for q in self.human_bridge.get_pending()
        ]

    def get_all_questions(self) -> List[Dict[str, Any]]:
        return self.human_bridge.get_all()

    # ------------------------------------------------------------------
    # Consolidation
    # ------------------------------------------------------------------

    def _consolidate_focus_board(self):
        """Remove duplicates and archive old completed items."""
        for cat in self.focus_board:
            if not self.focus_board[cat]:
                continue
            seen = set()
            unique = []
            for item in reversed(self.focus_board[cat]):
                note = item.get("note", "") if isinstance(item, dict) else str(item)
                if note not in seen:
                    seen.add(note)
                    unique.append(item)
            self.focus_board[cat] = list(reversed(unique))

        # Keep completed manageable
        completed = self.focus_board.get("completed", [])
        if len(completed) > 30:
            self.focus_board["completed"] = completed[-30:]

    # ------------------------------------------------------------------
    # Exploration / Synthesis (backward compat stubs → route to stages)
    # ------------------------------------------------------------------

    def explore_and_discover(self, context=None, exploration_depth="deep"):
        return self._run_individual_stage("discovery", context)

    def synthesize_learnings(self, lookback_iterations=5):
        return self._run_individual_stage("review", None)