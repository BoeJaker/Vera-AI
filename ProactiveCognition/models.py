"""
Core data models for the cognition system.

These are plain data containers — no business logic, no I/O.
Serialisable to/from dict for storage layer flexibility.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional


# ── Task lifecycle ────────────────────────────────────────────

class TaskStatus(str, Enum):
    NEW        = "new"
    SCOPING    = "scoping"
    PLANNING   = "planning"
    EXECUTION  = "execution"
    BLOCKED    = "blocked"
    REVIEW     = "review"
    COMPLETE   = "complete"
    FAILED     = "failed"
    CANCELLED  = "cancelled"


class TaskPriority(int, Enum):
    """Lower number = higher priority (matches typical PQ semantics)."""
    CRITICAL   = 0   # user-reply unblocking a task
    HIGH       = 1   # active focused work
    NORMAL     = 2   # background-spawned tasks
    LOW        = 3   # summarisation, housekeeping
    IDLE       = 4   # speculative / exploratory


@dataclass
class TaskStep:
    """A single planned step inside a task."""
    description: str
    tool: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    result: Optional[Any] = None
    completed: bool = False
    started_at: Optional[float] = None
    finished_at: Optional[float] = None


@dataclass
class Task:
    goal: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    status: TaskStatus = TaskStatus.NEW
    priority: TaskPriority = TaskPriority.NORMAL
    origin: str = "manual"                        # "background", "manual", "user_request"

    # plan
    plan: List[TaskStep] = field(default_factory=list)
    current_step_idx: int = 0

    # execution bookkeeping
    progress_log: List[LogEntry] = field(default_factory=list)
    artifacts: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    retries: int = 0
    max_retries: int = 2

    # timing
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    deadline: Optional[float] = None              # optional wall-clock deadline
    time_budget_s: Optional[float] = None         # max cumulative LLM-time

    # communication policy
    update_channel: Optional[str] = None
    update_frequency: str = "milestone"           # "step", "milestone", "completion"
    verbosity: str = "normal"                     # "brief", "normal", "detailed"

    # relationships
    parent_task_id: Optional[str] = None
    spawned_task_ids: List[str] = field(default_factory=list)

    def touch(self):
        self.updated_at = time.time()

    def current_step(self) -> Optional[TaskStep]:
        if 0 <= self.current_step_idx < len(self.plan):
            return self.plan[self.current_step_idx]
        return None

    def advance(self):
        step = self.current_step()
        if step:
            step.completed = True
            step.finished_at = time.time()
        self.current_step_idx += 1
        self.touch()

    def is_terminal(self) -> bool:
        return self.status in (
            TaskStatus.COMPLETE,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        )

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        d["priority"] = self.priority.value
        return d


# ── Log entry ─────────────────────────────────────────────────

@dataclass
class LogEntry:
    message: str
    level: str = "info"             # "debug", "info", "warn", "error"
    timestamp: float = field(default_factory=time.time)
    meta: Optional[Dict[str, Any]] = None


# ── Questions (non-blocking human interaction) ────────────────

class QuestionStatus(str, Enum):
    PENDING   = "pending"
    ANSWERED  = "answered"
    EXPIRED   = "expired"
    CANCELLED = "cancelled"


@dataclass
class Question:
    task_id: str
    text: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    status: QuestionStatus = QuestionStatus.PENDING
    options: Optional[List[str]] = None           # optional multiple-choice
    answer: Optional[str] = None
    asked_at: float = field(default_factory=time.time)
    answered_at: Optional[float] = None
    timeout_s: float = 3600.0                     # default 1h expiry


# ── Insights (background loop output) ────────────────────────

@dataclass
class Insight:
    text: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    source: str = "background"                    # which sub-agent produced it
    confidence: float = 0.5
    tags: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    spawned_task_id: Optional[str] = None         # if it led to a task


# ── Ingested event (what memory stores from feeds) ────────────

@dataclass
class IngestedEvent:
    topic: str
    summary: str
    raw: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: float = field(default_factory=time.time)
    processed: bool = False