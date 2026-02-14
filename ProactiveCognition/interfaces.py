"""
Abstract interfaces for subsystems the cognition manager depends on.

Implement these to plug in your actual infrastructure (Neo4j, ChromaDB,
Telegram, Ollama, etc.). The manager only talks through these contracts.
"""

from __future__ import annotations

import abc
from typing import Any, Dict, List, Optional

from .models import IngestedEvent, Insight, Question, Task


# ── Memory ────────────────────────────────────────────────────

class MemoryStore(abc.ABC):
    """Unified interface over episodic + semantic + working memory."""

    # ── episodic (timeline) ──

    @abc.abstractmethod
    async def store_event(self, event: IngestedEvent) -> None: ...

    @abc.abstractmethod
    async def get_recent_events(
        self, seconds: float = 3600, limit: int = 100
    ) -> List[IngestedEvent]: ...

    # ── insights ──

    @abc.abstractmethod
    async def store_insight(self, insight: Insight) -> None: ...

    @abc.abstractmethod
    async def get_recent_insights(
        self, seconds: float = 86400, limit: int = 50
    ) -> List[Insight]: ...

    # ── tasks ──

    @abc.abstractmethod
    async def save_task(self, task: Task) -> None: ...

    @abc.abstractmethod
    async def get_task(self, task_id: str) -> Optional[Task]: ...

    @abc.abstractmethod
    async def get_active_tasks(self) -> List[Task]: ...

    # ── questions ──

    @abc.abstractmethod
    async def save_question(self, question: Question) -> None: ...

    @abc.abstractmethod
    async def get_pending_questions(self, task_id: str) -> List[Question]: ...

    # ── semantic search (vector) ──

    @abc.abstractmethod
    async def semantic_search(
        self, query: str, top_k: int = 5
    ) -> List[Dict[str, Any]]: ...


# ── Messaging ─────────────────────────────────────────────────

class MessagingGateway(abc.ABC):
    """Platform-agnostic outbound messaging."""

    @abc.abstractmethod
    async def send_message(
        self, text: str, channel: Optional[str] = None
    ) -> None: ...

    @abc.abstractmethod
    async def ask_question(self, question: Question) -> None: ...

    @abc.abstractmethod
    async def send_progress(
        self, task: Task, update: str
    ) -> None: ...


# ── Tool execution ────────────────────────────────────────────

class ToolRouter(abc.ABC):
    """Dispatch tool calls to your existing toolchain."""

    @abc.abstractmethod
    async def run_tool(
        self, name: str, args: Dict[str, Any]
    ) -> Dict[str, Any]: ...

    @abc.abstractmethod
    async def list_tools(self) -> List[str]: ...


# ── LLM backend ──────────────────────────────────────────────

class LLMBackend(abc.ABC):
    """
    Thin wrapper around your LLM inference layer (Ollama, vLLM, etc.).
    
    The cognition manager never constructs raw HTTP calls — it asks
    this interface for completions, and the backend handles model
    selection, routing, retries, and token accounting.
    """

    @abc.abstractmethod
    async def complete(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        temperature: float = 0.4,
        max_tokens: int = 2048,
        stop: Optional[List[str]] = None,
    ) -> str: ...

    @abc.abstractmethod
    async def complete_structured(
        self,
        messages: List[Dict[str, str]],
        schema: Dict[str, Any],
        system: Optional[str] = None,
        temperature: float = 0.2,
    ) -> Dict[str, Any]:
        """Return a JSON-parseable dict conforming to `schema`."""
        ...


# ── Event bus ─────────────────────────────────────────────────

class EventBus(abc.ABC):
    """Pub/sub interface — adapt to Redis, NATS, ZMQ, or in-process."""

    @abc.abstractmethod
    async def publish(self, topic: str, payload: Dict[str, Any]) -> None: ...

    @abc.abstractmethod
    async def subscribe(
        self, topic: str, handler
    ) -> None: ...