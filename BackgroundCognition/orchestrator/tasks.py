"""
Task definitions for the unified orchestrator
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
import uuid


class TaskType(Enum):
    """Types of tasks the orchestrator can handle"""
    TOOL_CALL = "tool_call"
    LLM_REQUEST = "llm_request"
    OLLAMA_REQUEST = "ollama_request"
    CODE_EXECUTION = "code_execution"
    BACKGROUND_COGNITION = "background_cognition"
    API_REQUEST = "api_request"
    DOCKER_TASK = "docker_task"
    REMOTE_COMPUTE = "remote_compute"
    PARALLEL_BATCH = "parallel_batch"
    CUSTOM = "custom"


class TaskStatus(Enum):
    """Task execution status"""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RATE_LIMITED = "rate_limited"
    WAITING_RESOURCES = "waiting_resources"


class TaskPriority(Enum):
    """Task priority levels"""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BACKGROUND = 4


@dataclass
class TaskRequirements:
    """Resource requirements for a task"""
    cpu_cores: Optional[float] = None
    memory_mb: Optional[int] = None
    gpu: bool = False
    network: bool = True
    worker_capabilities: List[str] = field(default_factory=list)
    max_runtime_seconds: Optional[int] = None


@dataclass
class TaskResult:
    """Result of task execution"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    execution_time_ms: float = 0
    worker_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Task:
    """
    Unified task representation for all compute operations
    """
    # Identity
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: TaskType = TaskType.CUSTOM

    # Scheduling
    priority: TaskPriority = TaskPriority.NORMAL
    scheduled_at: datetime = field(default_factory=datetime.utcnow)

    # Payload
    payload: Dict[str, Any] = field(default_factory=dict)

    # Requirements
    requirements: TaskRequirements = field(default_factory=TaskRequirements)

    # State
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[TaskResult] = None

    # Execution tracking
    submitted_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Retry policy
    max_retries: int = 3
    retry_count: int = 0
    retry_delay_seconds: float = 1.0

    # Callbacks
    on_complete: Optional[Callable[[TaskResult], None]] = None
    on_error: Optional[Callable[[Exception], None]] = None
    on_progress: Optional[Callable[[float], None]] = None

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)

    # Parallelization
    can_parallelize: bool = True
    depends_on: List[str] = field(default_factory=list)  # Task IDs

    def __lt__(self, other):
        """For priority queue sorting"""
        if self.priority.value != other.priority.value:
            return self.priority.value < other.priority.value
        return self.scheduled_at < other.scheduled_at

    def mark_started(self):
        """Mark task as started"""
        self.status = TaskStatus.RUNNING
        self.started_at = datetime.utcnow()

    def mark_completed(self, result: TaskResult):
        """Mark task as completed"""
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.result = result
        if self.on_complete:
            try:
                self.on_complete(result)
            except Exception as e:
                print(f"Error in completion callback: {e}")

    def mark_failed(self, error: str, retry: bool = True):
        """Mark task as failed"""
        if retry and self.retry_count < self.max_retries:
            self.retry_count += 1
            self.status = TaskStatus.QUEUED
            return False  # Will retry

        self.status = TaskStatus.FAILED
        self.completed_at = datetime.utcnow()
        self.result = TaskResult(success=False, error=error)
        if self.on_error:
            try:
                self.on_error(Exception(error))
            except Exception as e:
                print(f"Error in error callback: {e}")
        return True  # Failed permanently

    def is_ready(self, completed_task_ids: set) -> bool:
        """Check if task dependencies are met"""
        return all(dep_id in completed_task_ids for dep_id in self.depends_on)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'id': self.id,
            'type': self.type.value,
            'priority': self.priority.value,
            'status': self.status.value,
            'payload': self.payload,
            'submitted_at': self.submitted_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'retry_count': self.retry_count,
            'tags': self.tags,
            'metadata': self.metadata,
            'result': {
                'success': self.result.success,
                'data': str(self.result.data)[:200] if self.result.data else None,
                'error': self.result.error,
                'metrics': self.result.metrics,
                'execution_time_ms': self.result.execution_time_ms,
                'worker_id': self.result.worker_id,
            } if self.result else None
        }


@dataclass
class ParallelBatch:
    """A batch of tasks that can be executed in parallel"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tasks: List[Task] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def add_task(self, task: Task):
        """Add task to batch"""
        self.tasks.append(task)

    def all_completed(self) -> bool:
        """Check if all tasks are completed"""
        return all(
            task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]
            for task in self.tasks
        )

    def get_results(self) -> List[TaskResult]:
        """Get all task results"""
        return [task.result for task in self.tasks if task.result]
