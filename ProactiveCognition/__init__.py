"""
Cognition System — dual-loop cognitive architecture for distributed LLM agents.

    from cognition import CognitionManager, CognitionConfig
"""

from .manager import CognitionManager, CognitionConfig
from .models import (
    Task, TaskStatus, TaskPriority, TaskStep,
    Question, QuestionStatus,
    Insight, IngestedEvent, LogEntry,
)
from .interfaces import (
    MemoryStore, MessagingGateway, ToolRouter, LLMBackend, EventBus,
)
from .scheduler import Scheduler
from .loops import BackgroundLoop, FocusedLoop
from .loops.background import BackgroundConfig

__all__ = [
    "CognitionManager", "CognitionConfig",
    "Task", "TaskStatus", "TaskPriority", "TaskStep",
    "Question", "QuestionStatus",
    "Insight", "IngestedEvent", "LogEntry",
    "MemoryStore", "MessagingGateway", "ToolRouter", "LLMBackend", "EventBus",
    "Scheduler",
    "BackgroundLoop", "FocusedLoop", "BackgroundConfig",
]