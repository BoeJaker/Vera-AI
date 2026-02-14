"""
In-memory implementations of all abstract interfaces.

Use these for:
  - Local development and testing
  - Bootstrapping before real backends are wired in
  - Unit tests

NOT for production — no persistence, no concurrency safety.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional

from .interfaces import EventBus, LLMBackend, MemoryStore, MessagingGateway, ToolRouter
from .models import IngestedEvent, Insight, Question, QuestionStatus, Task, TaskStatus

logger = logging.getLogger(__name__)


# ── Memory ────────────────────────────────────────────────────

class InMemoryStore(MemoryStore):
    def __init__(self):
        self._events: List[IngestedEvent] = []
        self._insights: List[Insight] = []
        self._tasks: Dict[str, Task] = {}
        self._questions: Dict[str, Question] = {}

    async def store_event(self, event: IngestedEvent) -> None:
        self._events.append(event)

    async def get_recent_events(self, seconds=3600, limit=100) -> List[IngestedEvent]:
        cutoff = time.time() - seconds
        return [e for e in self._events if e.timestamp > cutoff][:limit]

    async def store_insight(self, insight: Insight) -> None:
        self._insights.append(insight)

    async def get_recent_insights(self, seconds=86400, limit=50) -> List[Insight]:
        cutoff = time.time() - seconds
        return [i for i in self._insights if i.created_at > cutoff][:limit]

    async def save_task(self, task: Task) -> None:
        self._tasks[task.id] = task

    async def get_task(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    async def get_active_tasks(self) -> List[Task]:
        return list(self._tasks.values())

    async def save_question(self, question: Question) -> None:
        self._questions[question.id] = question

    async def get_pending_questions(self, task_id: str) -> List[Question]:
        return [
            q for q in self._questions.values()
            if q.task_id == task_id and q.status == QuestionStatus.PENDING
        ]

    async def semantic_search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        # stub — return recent insights as a rough approximation
        return [{"text": i.text, "score": i.confidence} for i in self._insights[-top_k:]]


# ── Messaging ─────────────────────────────────────────────────

class ConsoleMessaging(MessagingGateway):
    """Prints messages to stdout — swap for Telegram/Slack later."""

    async def send_message(self, text: str, channel: Optional[str] = None) -> None:
        prefix = f"[{channel}]" if channel else "[MSG]"
        print(f"  {prefix} {text}")

    async def ask_question(self, question: Question) -> None:
        print(f"  [Q:{question.id}] {question.text}")

    async def send_progress(self, task: Task, update: str) -> None:
        print(f"  [PROGRESS:{task.id[:8]}] {update}")


# ── Tools ─────────────────────────────────────────────────────

class StubToolRouter(ToolRouter):
    """Returns stubs — register real tool handlers via `register()`."""

    def __init__(self):
        self._tools: Dict[str, Callable] = {}

    def register(self, name: str, handler: Callable):
        self._tools[name] = handler

    async def run_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if name in self._tools:
            result = self._tools[name](**args)
            if asyncio.iscoroutine(result):
                result = await result
            return {"result": result}
        logger.debug("Tool '%s' not registered, returning stub", name)
        return {"result": f"stub:{name}", "args": args}

    async def list_tools(self) -> List[str]:
        return list(self._tools.keys()) or [
            "web_search", "code_execute", "file_read", "file_write", "shell",
        ]


# ── LLM ───────────────────────────────────────────────────────

class EchoLLM(LLMBackend):
    """
    Deterministic stub that returns canned JSON responses
    matching the prompts' expected schemas. Useful for
    testing the state machine without burning tokens.
    """

    async def complete(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        temperature: float = 0.4,
        max_tokens: int = 2048,
        stop: Optional[List[str]] = None,
    ) -> str:
        sys_lower = (system or "").lower()

        if "scoping" in sys_lower:
            return json.dumps({
                "scope": "ready",
                "complexity": "simple",
                "refined_goal": messages[-1]["content"] if messages else "",
            })

        if "planning" in sys_lower:
            return json.dumps({
                "steps": [
                    {"description": "Research the topic", "tool": "web_search", "tool_args": {"query": "topic"}},
                    {"description": "Analyse findings", "tool": None, "tool_args": None},
                    {"description": "Produce summary", "tool": None, "tool_args": None},
                ]
            })

        if "execution" in sys_lower:
            return json.dumps({
                "reasoning": "Executing step as planned",
                "action": "think",
                "result_summary": "Step completed successfully",
            })

        if "review" in sys_lower:
            return json.dumps({
                "complete": True,
                "summary": "Task completed. Results synthesised.",
                "follow_up_tasks": [],
            })

        if "background" in sys_lower or "analyst" in sys_lower:
            return json.dumps({
                "insights": [
                    {"text": "Detected activity pattern", "confidence": 0.7, "tags": ["system"], "actionable": False}
                ],
                "proposed_tasks": [],
            })

        # fallback
        return json.dumps({"response": "acknowledged"})

    async def complete_structured(
        self,
        messages: List[Dict[str, str]],
        schema: Dict[str, Any],
        system: Optional[str] = None,
        temperature: float = 0.2,
    ) -> Dict[str, Any]:
        raw = await self.complete(messages, system, temperature)
        return json.loads(raw)


# ── Event Bus ─────────────────────────────────────────────────

class InMemoryEventBus(EventBus):
    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = {}

    async def publish(self, topic: str, payload: Dict[str, Any]) -> None:
        for pattern, handlers in self._handlers.items():
            if self._matches(pattern, topic):
                for h in handlers:
                    try:
                        result = h(payload)
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception:
                        logger.exception("Event handler error on %s", topic)

    async def subscribe(self, topic: str, handler) -> None:
        self._handlers.setdefault(topic, []).append(handler)

    @staticmethod
    def _matches(pattern: str, topic: str) -> bool:
        if pattern == topic:
            return True
        if pattern.endswith(".*"):
            prefix = pattern[:-2]
            return topic.startswith(prefix + ".") or topic == prefix
        return False