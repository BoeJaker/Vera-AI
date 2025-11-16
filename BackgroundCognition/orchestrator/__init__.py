"""
Vera-AI Unified Orchestration Backend

Manages all compute tasks with intelligent routing, resource management,
and worker pool orchestration.
"""

from .core import UnifiedOrchestrator
from .workers import (
    WorkerRegistry,
    BaseWorker,
    DockerWorker,
    RemoteWorker,
    OllamaWorker,
    LLMAPIWorker,
)
from .resources import ResourceManager, LLMAPIPool
from .router import TaskRouter
from .tasks import Task, TaskType, TaskStatus, TaskPriority

__all__ = [
    'UnifiedOrchestrator',
    'WorkerRegistry',
    'BaseWorker',
    'DockerWorker',
    'RemoteWorker',
    'OllamaWorker',
    'LLMAPIWorker',
    'ResourceManager',
    'LLMAPIPool',
    'TaskRouter',
    'Task',
    'TaskType',
    'TaskStatus',
    'TaskPriority',
]
