"""
Base worker interface for the unified orchestrator
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from datetime import datetime
import uuid

from ..tasks import Task, TaskResult, TaskType


class WorkerStatus(Enum):
    """Worker operational status"""
    OFFLINE = "offline"
    STARTING = "starting"
    IDLE = "idle"
    BUSY = "busy"
    OVERLOADED = "overloaded"
    MAINTENANCE = "maintenance"
    ERROR = "error"


class WorkerCapability(Enum):
    """Worker capabilities/specializations"""
    # Execution types
    CODE_EXECUTION = "code_execution"
    PYTHON = "python"
    BASH = "bash"
    DOCKER = "docker"

    # LLM capabilities
    LLM_INFERENCE = "llm_inference"
    OLLAMA = "ollama"
    OPENAI_API = "openai_api"
    ANTHROPIC_API = "anthropic_api"
    GEMINI_API = "gemini_api"

    # Tool capabilities
    TOOL_EXECUTION = "tool_execution"
    WEB_BROWSING = "web_browsing"
    FILE_OPERATIONS = "file_operations"

    # Compute capabilities
    GPU = "gpu"
    HIGH_MEMORY = "high_memory"
    HIGH_CPU = "high_cpu"

    # Specialized
    BACKGROUND_COGNITION = "background_cognition"
    API_REQUESTS = "api_requests"
    REMOTE_COMPUTE = "remote_compute"


@dataclass
class WorkerMetrics:
    """Metrics for worker performance tracking"""
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_execution_time_ms: float = 0
    avg_execution_time_ms: float = 0
    cpu_usage_percent: float = 0
    memory_usage_mb: float = 0
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)
    uptime_seconds: float = 0


@dataclass
class WorkerConfig:
    """Configuration for a worker"""
    max_concurrent_tasks: int = 1
    rate_limit_per_minute: Optional[int] = None
    timeout_seconds: int = 300
    auto_restart: bool = True
    health_check_interval_seconds: int = 30
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseWorker(ABC):
    """
    Base class for all worker types in the orchestration backend
    """

    def __init__(
        self,
        worker_id: Optional[str] = None,
        capabilities: Optional[List[WorkerCapability]] = None,
        config: Optional[WorkerConfig] = None,
    ):
        self.id = worker_id or str(uuid.uuid4())
        self.capabilities: Set[WorkerCapability] = set(capabilities or [])
        self.config = config or WorkerConfig()

        self.status = WorkerStatus.OFFLINE
        self.metrics = WorkerMetrics()

        self.current_tasks: Dict[str, Task] = {}
        self.task_history: List[str] = []

        self._last_health_check = datetime.utcnow()

    @abstractmethod
    async def start(self) -> bool:
        """
        Start the worker

        Returns:
            bool: True if started successfully
        """
        pass

    @abstractmethod
    async def stop(self) -> bool:
        """
        Stop the worker gracefully

        Returns:
            bool: True if stopped successfully
        """
        pass

    @abstractmethod
    async def execute_task(self, task: Task) -> TaskResult:
        """
        Execute a task

        Args:
            task: Task to execute

        Returns:
            TaskResult: Result of task execution
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if worker is healthy

        Returns:
            bool: True if healthy
        """
        pass

    def can_handle(self, task: Task) -> bool:
        """
        Check if this worker can handle the given task

        Args:
            task: Task to check

        Returns:
            bool: True if worker can handle this task
        """
        # Check if worker has required capabilities
        required_caps = set(task.requirements.worker_capabilities)
        if required_caps and not required_caps.intersection(self.capabilities):
            return False

        # Check if worker is available
        if self.status not in [WorkerStatus.IDLE, WorkerStatus.BUSY]:
            return False

        # Check concurrent task limit
        if len(self.current_tasks) >= self.config.max_concurrent_tasks:
            return False

        return True

    def get_load(self) -> float:
        """
        Get current load factor (0.0 to 1.0+)

        Returns:
            float: Load factor
        """
        if self.status == WorkerStatus.OFFLINE:
            return float('inf')

        base_load = len(self.current_tasks) / max(self.config.max_concurrent_tasks, 1)

        # Adjust based on status
        if self.status == WorkerStatus.OVERLOADED:
            base_load *= 2.0
        elif self.status == WorkerStatus.ERROR:
            base_load = float('inf')

        return base_load

    async def submit_task(self, task: Task) -> TaskResult:
        """
        Submit and execute a task

        Args:
            task: Task to execute

        Returns:
            TaskResult: Result of execution
        """
        if not self.can_handle(task):
            return TaskResult(
                success=False,
                error=f"Worker {self.id} cannot handle task {task.id}",
            )

        try:
            # Track task
            self.current_tasks[task.id] = task
            task.mark_started()

            # Update status
            if len(self.current_tasks) >= self.config.max_concurrent_tasks:
                self.status = WorkerStatus.BUSY
            else:
                self.status = WorkerStatus.BUSY

            # Execute
            start_time = datetime.utcnow()
            result = await self.execute_task(task)
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            # Update metrics
            result.execution_time_ms = execution_time
            result.worker_id = self.id
            self.metrics.tasks_completed += 1 if result.success else 0
            self.metrics.tasks_failed += 0 if result.success else 1
            self.metrics.total_execution_time_ms += execution_time
            self.metrics.avg_execution_time_ms = (
                self.metrics.total_execution_time_ms /
                (self.metrics.tasks_completed + self.metrics.tasks_failed)
            )

            # Mark complete
            task.mark_completed(result)

            return result

        except Exception as e:
            error_msg = f"Worker {self.id} error executing task {task.id}: {e}"
            result = TaskResult(success=False, error=error_msg)
            task.mark_failed(error_msg)
            self.metrics.tasks_failed += 1
            return result

        finally:
            # Clean up
            if task.id in self.current_tasks:
                del self.current_tasks[task.id]
            self.task_history.append(task.id)

            # Update status
            if len(self.current_tasks) == 0:
                self.status = WorkerStatus.IDLE

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'id': self.id,
            'status': self.status.value,
            'capabilities': [cap.value for cap in self.capabilities],
            'current_tasks': len(self.current_tasks),
            'max_concurrent_tasks': self.config.max_concurrent_tasks,
            'load': self.get_load(),
            'metrics': {
                'tasks_completed': self.metrics.tasks_completed,
                'tasks_failed': self.metrics.tasks_failed,
                'avg_execution_time_ms': self.metrics.avg_execution_time_ms,
                'cpu_usage_percent': self.metrics.cpu_usage_percent,
                'memory_usage_mb': self.metrics.memory_usage_mb,
                'uptime_seconds': self.metrics.uptime_seconds,
            },
            'config': {
                'max_concurrent_tasks': self.config.max_concurrent_tasks,
                'rate_limit_per_minute': self.config.rate_limit_per_minute,
                'timeout_seconds': self.config.timeout_seconds,
            }
        }
