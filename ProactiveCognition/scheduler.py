"""
Priority-based async task scheduler.

Manages a bounded pool of workers, each processing tasks from a
priority queue. Handles concurrency limits, time budgets, and
graceful shutdown.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Callable, Awaitable, Dict, Optional

from .models import Task, TaskPriority, TaskStatus

logger = logging.getLogger(__name__)


class PriorityEntry:
    """Wrapper so Tasks are comparable for heapq via priority."""

    __slots__ = ("priority", "seq", "task")

    _counter = 0

    def __init__(self, task: Task):
        self.priority = task.priority.value
        PriorityEntry._counter += 1
        self.seq = PriorityEntry._counter
        self.task = task

    def __lt__(self, other: PriorityEntry) -> bool:
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.seq < other.seq              # FIFO within same priority


class Scheduler:
    """
    Async priority scheduler with bounded concurrency.

    Usage:
        scheduler = Scheduler(max_workers=3)
        scheduler.set_handler(my_async_task_handler)
        await scheduler.start()

        scheduler.submit(task)          # non-blocking
        await scheduler.drain()         # wait for empty queue
        await scheduler.shutdown()
    """

    def __init__(self, max_workers: int = 3):
        self.max_workers = max_workers
        self._queue: asyncio.PriorityQueue[PriorityEntry] = asyncio.PriorityQueue()
        self._handler: Optional[Callable[[Task], Awaitable[None]]] = None
        self._workers: list[asyncio.Task] = []
        self._running = False
        self._active_tasks: Dict[str, Task] = {}     # task_id → task (currently executing)
        self._semaphore = asyncio.Semaphore(max_workers)

    def set_handler(self, handler: Callable[[Task], Awaitable[None]]):
        self._handler = handler

    # ── lifecycle ──

    async def start(self):
        if self._running:
            return
        if self._handler is None:
            raise RuntimeError("No handler set — call set_handler() first")
        self._running = True
        for i in range(self.max_workers):
            w = asyncio.create_task(self._worker_loop(i), name=f"worker-{i}")
            self._workers.append(w)
        logger.info("Scheduler started with %d workers", self.max_workers)

    async def shutdown(self, timeout: float = 30.0):
        self._running = False
        # inject poison pills so workers wake up and exit
        for _ in self._workers:
            sentinel = Task(goal="__shutdown__")
            sentinel.status = TaskStatus.CANCELLED
            sentinel.priority = TaskPriority.IDLE
            await self._queue.put(PriorityEntry(sentinel))

        done, pending = await asyncio.wait(
            self._workers, timeout=timeout
        )
        for t in pending:
            t.cancel()
        self._workers.clear()
        logger.info("Scheduler shut down")

    async def drain(self):
        """Block until the queue is empty and all workers are idle."""
        await self._queue.join()

    # ── submit ──

    def submit(self, task: Task):
        if not self._running:
            raise RuntimeError("Scheduler not running")
        self._queue.put_nowait(PriorityEntry(task))
        logger.debug("Submitted task %s [%s] pri=%s",
                      task.id, task.goal[:40], task.priority.name)

    def requeue(self, task: Task):
        """Re-enqueue a task (e.g. after BLOCKED → answered)."""
        self._queue.put_nowait(PriorityEntry(task))
        logger.debug("Requeued task %s", task.id)

    # ── introspection ──

    @property
    def queue_depth(self) -> int:
        return self._queue.qsize()

    @property
    def active_count(self) -> int:
        return len(self._active_tasks)

    @property
    def active_tasks(self) -> Dict[str, Task]:
        return dict(self._active_tasks)

    # ── worker loop ──

    async def _worker_loop(self, worker_id: int):
        logger.debug("Worker %d started", worker_id)
        while self._running:
            try:
                entry: PriorityEntry = await asyncio.wait_for(
                    self._queue.get(), timeout=5.0
                )
            except asyncio.TimeoutError:
                continue

            task = entry.task

            # poison pill
            if task.goal == "__shutdown__":
                self._queue.task_done()
                break

            # skip terminal tasks that somehow got queued
            if task.is_terminal():
                self._queue.task_done()
                continue

            async with self._semaphore:
                self._active_tasks[task.id] = task
                try:
                    logger.info(
                        "Worker %d processing task %s [%s]",
                        worker_id, task.id, task.status.value,
                    )
                    await self._handler(task)
                except Exception:
                    logger.exception(
                        "Worker %d: unhandled error on task %s", worker_id, task.id
                    )
                    task.status = TaskStatus.FAILED
                    task.error = "Unhandled worker exception"
                    task.touch()
                finally:
                    self._active_tasks.pop(task.id, None)
                    self._queue.task_done()