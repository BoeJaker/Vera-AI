"""
CognitionManager — the central orchestrator.

This is the single entry point for the cognition subsystem. It:
  - Owns and coordinates the Background and Focused loops
  - Routes tasks through the scheduler
  - Handles non-blocking question/answer flow
  - Manages task lifecycle transitions
  - Provides an API surface for external systems (FastAPI, CLI, etc.)

Usage:
    manager = CognitionManager(
        llm=my_llm_backend,
        memory=my_memory_store,
        messaging=my_messaging_gateway,
        tools=my_tool_router,
        event_bus=my_event_bus,
    )
    await manager.start()

    # submit work
    task = await manager.create_task("Analyse BTC volatility spike")

    # answer a question
    await manager.answer_question(question_id, "Yes, go ahead")

    # shut down
    await manager.shutdown()
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .interfaces import EventBus, LLMBackend, MemoryStore, MessagingGateway, ToolRouter
from .models import (
    IngestedEvent, Insight, LogEntry, Question, QuestionStatus,
    Task, TaskPriority, TaskStatus,
)
from .scheduler import Scheduler
from .loops.background import BackgroundConfig, BackgroundLoop
from .loops.focused import FocusedLoop

logger = logging.getLogger(__name__)


# ── Configuration ─────────────────────────────────────────────

@dataclass
class CognitionConfig:
    max_workers: int = 3
    background: BackgroundConfig = field(default_factory=BackgroundConfig)
    max_concurrent_tasks: int = 10          # hard cap on open tasks
    question_timeout_s: float = 3600.0
    enable_background_loop: bool = True
    task_requeue_delay_s: float = 2.0       # delay before re-queuing a progressing task


# ── Manager ───────────────────────────────────────────────────

class CognitionManager:
    """
    Central orchestrator for the dual-loop cognition system.
    """

    def __init__(
        self,
        llm: LLMBackend,
        memory: MemoryStore,
        messaging: MessagingGateway,
        tools: ToolRouter,
        event_bus: Optional[EventBus] = None,
        config: Optional[CognitionConfig] = None,
    ):
        self.llm = llm
        self.memory = memory
        self.messaging = messaging
        self.tools = tools
        self.bus = event_bus
        self.config = config or CognitionConfig()

        # scheduler
        self.scheduler = Scheduler(max_workers=self.config.max_workers)
        self.scheduler.set_handler(self._task_handler)

        # focused loop (stateless — the scheduler calls it)
        self.focused = FocusedLoop(
            llm=llm,
            memory=memory,
            messaging=messaging,
            tools=tools,
            on_task_proposed=self._on_task_proposed,
        )

        # background loop
        self.background = BackgroundLoop(
            llm=llm,
            memory=memory,
            messaging=messaging,
            config=self.config.background,
            on_task_proposed=self._on_task_proposed,
        )

        self._running = False
        self._housekeeping_task: Optional[asyncio.Task] = None

    # ══════════════════════════════════════════════════════════
    #  LIFECYCLE
    # ══════════════════════════════════════════════════════════

    async def start(self):
        """Boot the cognition system."""
        if self._running:
            return

        logger.info("CognitionManager starting...")

        # wire up event bus subscriptions
        if self.bus:
            await self.bus.subscribe("feed.*", self._on_feed_event)
            await self.bus.subscribe("user.reply", self._on_user_reply)
            await self.bus.subscribe("user.task_request", self._on_user_task_request)

        await self.scheduler.start()

        if self.config.enable_background_loop:
            await self.background.start()

        self._housekeeping_task = asyncio.create_task(
            self._housekeeping_loop(), name="housekeeping"
        )

        self._running = True
        logger.info("CognitionManager running (%d workers, bg=%s)",
                     self.config.max_workers, self.config.enable_background_loop)

    async def shutdown(self, timeout: float = 30.0):
        """Gracefully stop everything."""
        logger.info("CognitionManager shutting down...")
        self._running = False

        await self.background.stop()
        await self.scheduler.shutdown(timeout=timeout)

        if self._housekeeping_task:
            self._housekeeping_task.cancel()
            try:
                await self._housekeeping_task
            except asyncio.CancelledError:
                pass

        logger.info("CognitionManager stopped")

    # ══════════════════════════════════════════════════════════
    #  PUBLIC API — for FastAPI routes, CLI, tests
    # ══════════════════════════════════════════════════════════

    async def create_task(
        self,
        goal: str,
        priority: TaskPriority = TaskPriority.NORMAL,
        channel: Optional[str] = None,
    ) -> Task:
        """Create and schedule a new task."""
        active = await self.memory.get_active_tasks()
        if len(active) >= self.config.max_concurrent_tasks:
            await self.messaging.send_message(
                f"⚠️ Task limit reached ({self.config.max_concurrent_tasks}). "
                f"Finish or cancel a task first."
            )
            raise RuntimeError("Max concurrent task limit reached")

        task = Task(
            goal=goal,
            priority=priority,
            origin="manual",
            update_channel=channel,
        )
        await self.memory.save_task(task)
        self.scheduler.submit(task)

        logger.info("Created task %s: %s", task.id, goal[:60])
        if self.bus:
            await self.bus.publish("cognition.task.created", {
                "task_id": task.id, "goal": goal
            })
        return task

    async def cancel_task(self, task_id: str) -> Optional[Task]:
        """Cancel a running or queued task."""
        task = await self.memory.get_task(task_id)
        if not task or task.is_terminal():
            return task

        task.status = TaskStatus.CANCELLED
        task.touch()
        await self.memory.save_task(task)
        await self.messaging.send_message(f"🚫 Cancelled: {task.goal}")

        logger.info("Cancelled task %s", task_id)
        return task

    async def answer_question(self, question_id: str, answer: str) -> Optional[Task]:
        """
        Provide an answer to a pending question, unblocking the associated task.
        """
        # find the question across all tasks
        all_tasks = await self.memory.get_active_tasks()
        target_question = None
        target_task = None

        for task in all_tasks:
            questions = await self.memory.get_pending_questions(task.id)
            for q in questions:
                if q.id == question_id:
                    target_question = q
                    target_task = task
                    break
            if target_question:
                break

        if not target_question or not target_task:
            logger.warning("Question %s not found", question_id)
            return None

        # record the answer
        target_question.status = QuestionStatus.ANSWERED
        target_question.answer = answer
        target_question.answered_at = time.time()
        await self.memory.save_question(target_question)

        # unblock the task with elevated priority (user is waiting)
        if target_task.status == TaskStatus.BLOCKED:
            target_task.status = TaskStatus.EXECUTION
            target_task.priority = TaskPriority.CRITICAL
            target_task.progress_log.append(
                LogEntry(message=f"Unblocked: answer received — '{answer[:80]}'")
            )
            target_task.touch()
            await self.memory.save_task(target_task)
            self.scheduler.requeue(target_task)

            logger.info("Task %s unblocked by answer to Q %s",
                        target_task.id, question_id)

        return target_task

    async def get_status(self) -> Dict[str, Any]:
        """System-wide status snapshot."""
        active = await self.memory.get_active_tasks()
        return {
            "running": self._running,
            "scheduler": {
                "queue_depth": self.scheduler.queue_depth,
                "active_workers": self.scheduler.active_count,
                "max_workers": self.config.max_workers,
            },
            "background_loop": {
                "running": self.background.is_running,
                "cycles": self.background._cycle_count,
            },
            "tasks": {
                "active": len([t for t in active if not t.is_terminal()]),
                "blocked": len([t for t in active if t.status == TaskStatus.BLOCKED]),
                "by_status": _count_by(active, lambda t: t.status.value),
            },
        }

    async def list_tasks(
        self, include_terminal: bool = False
    ) -> List[Task]:
        tasks = await self.memory.get_active_tasks()
        if include_terminal:
            return tasks
        return [t for t in tasks if not t.is_terminal()]

    async def get_task(self, task_id: str) -> Optional[Task]:
        return await self.memory.get_task(task_id)

    async def trigger_background_cycle(self):
        """Manually trigger one background analysis cycle."""
        await self.background.trigger_cycle()

    # ══════════════════════════════════════════════════════════
    #  INTERNAL — task handler called by the scheduler
    # ══════════════════════════════════════════════════════════

    async def _task_handler(self, task: Task):
        """
        The scheduler calls this for each task it dequeues.
        Advances the task one step, then decides whether to re-queue.
        """
        if task.is_terminal():
            return

        # check time budget
        if task.time_budget_s and (time.time() - task.created_at) > task.time_budget_s:
            task.status = TaskStatus.FAILED
            task.error = "Time budget exceeded"
            task.touch()
            await self.memory.save_task(task)
            await self.messaging.send_message(
                f"⏰ Task timed out: {task.goal}"
            )
            return

        # execute one transition
        task = await self.focused.execute(task)

        # publish event
        if self.bus:
            await self.bus.publish("cognition.task.updated", {
                "task_id": task.id,
                "status": task.status.value,
            })

        # decide what to do next
        if task.is_terminal():
            logger.info("Task %s reached terminal state: %s", task.id, task.status.value)
            return

        if task.status == TaskStatus.BLOCKED:
            # don't re-queue — it'll be requeued when the answer arrives
            logger.info("Task %s blocked, waiting for human input", task.id)
            return

        # still progressing — re-queue with a small delay to be fair to other tasks
        await asyncio.sleep(self.config.task_requeue_delay_s)
        self.scheduler.requeue(task)

    # ══════════════════════════════════════════════════════════
    #  INTERNAL — event bus handlers
    # ══════════════════════════════════════════════════════════

    async def _on_feed_event(self, payload: Dict[str, Any]):
        """Ingest a feed event into episodic memory."""
        event = IngestedEvent(
            topic=payload.get("topic", "unknown"),
            summary=payload.get("summary", ""),
            raw=payload,
        )
        await self.memory.store_event(event)

    async def _on_user_reply(self, payload: Dict[str, Any]):
        """Handle a user reply to a question."""
        qid = payload.get("question_id")
        answer = payload.get("answer", "")
        if qid:
            await self.answer_question(qid, answer)

    async def _on_user_task_request(self, payload: Dict[str, Any]):
        """Handle a user requesting a new task via messaging."""
        goal = payload.get("goal", "")
        if goal:
            await self.create_task(goal)

    async def _on_task_proposed(self, task: Task):
        """Callback from background loop or focused loop when they want to spawn a task."""
        await self.memory.save_task(task)
        self.scheduler.submit(task)
        logger.info("Auto-spawned task %s: %s (origin=%s)", task.id, task.goal[:60], task.origin)

    # ══════════════════════════════════════════════════════════
    #  INTERNAL — housekeeping
    # ══════════════════════════════════════════════════════════

    async def _housekeeping_loop(self):
        """Periodic cleanup: expire questions, detect stuck tasks."""
        while self._running:
            try:
                await self._expire_questions()
                await self._detect_stuck_tasks()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Housekeeping error")
            await asyncio.sleep(60.0)

    async def _expire_questions(self):
        now = time.time()
        active_tasks = await self.memory.get_active_tasks()
        for task in active_tasks:
            if task.status != TaskStatus.BLOCKED:
                continue
            questions = await self.memory.get_pending_questions(task.id)
            for q in questions:
                if q.status == QuestionStatus.PENDING and (now - q.asked_at) > q.timeout_s:
                    q.status = QuestionStatus.EXPIRED
                    await self.memory.save_question(q)
                    # unblock with a default
                    task.status = TaskStatus.EXECUTION
                    task.progress_log.append(
                        LogEntry(message="Question expired, continuing with best effort", level="warn")
                    )
                    task.touch()
                    await self.memory.save_task(task)
                    self.scheduler.requeue(task)
                    logger.info("Question %s expired, task %s unblocked", q.id, task.id)

    async def _detect_stuck_tasks(self):
        """Flag tasks that haven't been updated in a long time."""
        now = time.time()
        stuck_threshold = 1800.0  # 30 min with no progress
        active_tasks = await self.memory.get_active_tasks()
        for task in active_tasks:
            if task.is_terminal() or task.status == TaskStatus.BLOCKED:
                continue
            if (now - task.updated_at) > stuck_threshold:
                task.progress_log.append(
                    LogEntry(message="Task appears stuck — no progress for 30min", level="warn")
                )
                task.touch()
                await self.memory.save_task(task)
                logger.warning("Task %s may be stuck (last update %.0fs ago)",
                               task.id, now - task.updated_at)


# ── helpers ───────────────────────────────────────────────────

def _count_by(items, key_fn) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for item in items:
        k = key_fn(item)
        counts[k] = counts.get(k, 0) + 1
    return counts