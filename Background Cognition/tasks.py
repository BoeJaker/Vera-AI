#!/usr/bin/env python3
"""
Task definitions and scheduling primitives for the orchestrator
"""

from __future__ import annotations
import enum
import random
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Tuple


class Priority(enum.IntEnum):
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


@dataclass(order=True)
class ScheduledTask:
    """PriorityQueue envelope.
    Sorted by (priority, scheduled_at, seq). Tasks carry labels & retry policy.
    """
    # sort keys
    priority: Priority
    scheduled_at: float
    seq: int

    # payload
    func: Callable[..., Any] = field(compare=False)
    args: Tuple[Any, ...] = field(default_factory=tuple, compare=False)
    kwargs: Dict[str, Any] = field(default_factory=dict, compare=False)

    # meta
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()), compare=False)
    name: str = field(default="task", compare=False)
    retries: int = field(default=0, compare=False)
    max_retries: int = field(default=2, compare=False)
    backoff_base: float = field(default=1.5, compare=False)
    backoff_cap: float = field(default=60.0, compare=False)
    jitter: float = field(default=0.2, compare=False)
    deadline_ts: Optional[float] = field(default=None, compare=False)
    labels: Tuple[str, ...] = field(default_factory=tuple, compare=False)
    context: Dict[str, Any] = field(default_factory=dict, compare=False)

    def next_retry_delay(self) -> float:
        exp = self.backoff_base ** max(0, self.retries)
        delay = min(self.backoff_cap, exp)
        if self.jitter:
            span = delay * self.jitter
            delay = delay + random.uniform(-span, span)
        return max(0.05, delay)

    def with_retry(self, now: Optional[float] = None) -> "ScheduledTask":
        now = now or time.time()
        return ScheduledTask(
            priority=self.priority,
            scheduled_at=now + self.next_retry_delay(),
            seq=self.seq + 100000,
            func=self.func,
            args=self.args,
            kwargs=self.kwargs,
            task_id=self.task_id,
            name=self.name,
            retries=self.retries + 1,
            max_retries=self.max_retries,
            backoff_base=self.backoff_base,
            backoff_cap=self.backoff_cap,
            jitter=self.jitter,
            deadline_ts=self.deadline_ts,
            labels=self.labels,
            context=self.context,
        )


class CancelToken:
    __slots__ = ("_cancelled",)
    def __init__(self) -> None:
        self._cancelled = False
    def cancel(self) -> None:
        self._cancelled = True
    @property
    def cancelled(self) -> bool:
        return self._cancelled