"""
Vera EventBus — Memory Promoter
================================

Subscribes to the bus with pattern ``*`` and scores every incoming event.
Events that clear the promotion threshold are written into HybridMemory
as session memories, and the promotion is recorded in Postgres.

Promotion scoring rules
-----------------------
Each rule is a callable ``(event) -> float`` returning 0.0–1.0.
The final score is the *maximum* across all matching rules (not the sum),
so a single strong signal is enough.

Rules are additive by design — add domain-specific rules in
``Vera/EventBus/promotion_rules.py`` and register them via
``MemoryPromoter.add_rule()``.

Events never promoted
---------------------
* log.*       — raw log records (stored in vera_event_logs, not memory)
* health.*    — heartbeats / liveness probes
* redis.*     — internal bus plumbing

All memory writes flow back through the bus as ``memory.written`` events
so the rest of the system can react.
"""

from __future__ import annotations

import asyncio
import fnmatch
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from Vera.EventBus.event_model import Event
from Vera.EventBus.config import (
    MEMORY_CANDIDATE_PATTERNS,
    MEMORY_PROMOTION_THRESHOLD,
)

logger = logging.getLogger("vera.eventbus.memory_promoter")

# ---------------------------------------------------------------------------
# Event types that are NEVER promoted regardless of score
# ---------------------------------------------------------------------------
NEVER_PROMOTE = {
    "log.*",
    "health.*",
    "redis.*",
    "memory.written",      # avoid re-promoting our own promotions
    "memory.promotion.*",
}


def _never_promote(event_type: str) -> bool:
    return any(fnmatch.fnmatch(event_type, p) for p in NEVER_PROMOTE)


# ---------------------------------------------------------------------------
# Built-in scoring rules
# ---------------------------------------------------------------------------

def _rule_task_complete(event: Event) -> float:
    """Completed tasks with results are valuable memories."""
    if event.type in ("task.complete", "orchestrator.task.complete", "tool.complete"):
        payload = event.payload
        # Higher score if there's a meaningful result
        has_result = bool(payload.get("result") or payload.get("output"))
        duration = float(payload.get("duration", 0))
        base = 0.7 if has_result else 0.4
        # Long-running tasks are more significant
        if duration > 10:
            base = min(base + 0.15, 1.0)
        return base
    return 0.0


def _rule_llm_complete(event: Event) -> float:
    """LLM completions are memories if they have meaningful token counts."""
    if event.type == "llm.complete":
        tokens = event.payload.get("output_tokens", 0)
        if tokens > 200:
            return 0.8
        if tokens > 50:
            return 0.55
        return 0.3
    return 0.0


def _rule_agent_decision(event: Event) -> float:
    """Agent decisions and focus changes are always worth keeping."""
    if fnmatch.fnmatch(event.type, "agent.*") or fnmatch.fnmatch(event.type, "focus.*"):
        return 0.75
    return 0.0


def _rule_error(event: Event) -> float:
    """Errors are worth remembering so the system can learn."""
    if event.type.endswith(".error") or event.type.endswith(".failed"):
        return 0.6
    return 0.0


def _rule_memory_explicit(event: Event) -> float:
    """Anything published as a memory.* event should always promote."""
    if fnmatch.fnmatch(event.type, "memory.*"):
        return 0.9
    return 0.0


def _rule_system_alert(event: Event) -> float:
    if fnmatch.fnmatch(event.type, "system.alert.*"):
        return 0.65
    return 0.0


DEFAULT_RULES: List[Callable[[Event], float]] = [
    _rule_task_complete,
    _rule_llm_complete,
    _rule_agent_decision,
    _rule_error,
    _rule_memory_explicit,
    _rule_system_alert,
]


# ---------------------------------------------------------------------------
# MemoryPromoter
# ---------------------------------------------------------------------------

class MemoryPromoter:
    """
    Bus subscriber that selectively promotes events into HybridMemory.

    Parameters
    ----------
    hybrid_memory : HybridMemory
        The live memory instance to write into.
    bus : RedisEventBus
        Used to publish ``memory.written`` and ``memory.promotion.skipped`` events.
    event_logger : EventLogger
        Postgres handle for recording promotions.
    session_resolver : Callable[[Event], Optional[str]]
        Returns the session_id to associate with the memory, or None to use
        the event's ``meta.session_id`` field.
    threshold : float
        Minimum score to trigger promotion (default from config).
    """

    def __init__(
        self,
        hybrid_memory,
        bus,
        event_logger,
        session_resolver: Optional[Callable[[Event], Optional[str]]] = None,
        threshold: float = MEMORY_PROMOTION_THRESHOLD,
    ):
        self.mem = hybrid_memory
        self.bus = bus
        self.event_logger = event_logger
        self.threshold = threshold
        self._session_resolver = session_resolver
        self._rules: List[Callable[[Event], float]] = list(DEFAULT_RULES)

    # ------------------------------------------------------------------
    # Rule management
    # ------------------------------------------------------------------

    def add_rule(self, rule: Callable[[Event], float]):
        """Register an additional scoring rule."""
        self._rules.append(rule)

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _score(self, event: Event) -> Tuple[float, str]:
        """
        Return (score, reason) for the event.
        score is the max across all rules.
        reason identifies which rule fired highest.
        """
        best_score = 0.0
        best_rule = "none"
        for rule in self._rules:
            try:
                s = rule(event)
                if s > best_score:
                    best_score = s
                    best_rule = rule.__name__
            except Exception as exc:
                logger.debug(f"[MemoryPromoter] Rule {rule.__name__} raised: {exc}")
        return best_score, best_rule

    def _is_candidate(self, event: Event) -> bool:
        return any(fnmatch.fnmatch(event.type, p) for p in MEMORY_CANDIDATE_PATTERNS)

    # ------------------------------------------------------------------
    # Handler (subscribe to "*")
    # ------------------------------------------------------------------

    async def handle(self, event: Event):
        """Main bus handler — called for every event."""
        if _never_promote(event.type):
            return

        if not self._is_candidate(event):
            return

        score, reason = self._score(event)

        if score < self.threshold:
            logger.debug(
                f"[MemoryPromoter] Skip {event.type} score={score:.2f} < {self.threshold}"
            )
            return

        await self._promote(event, score, reason)

    # ------------------------------------------------------------------
    # Promotion
    # ------------------------------------------------------------------

    async def _promote(self, event: Event, score: float, reason: str):
        session_id = self._resolve_session(event)
        if not session_id:
            logger.debug(f"[MemoryPromoter] No session_id for {event.type}, skipping.")
            return

        text = self._event_to_text(event)
        node_type = self._node_type_for(event)
        metadata = {
            "event_id": event.id,
            "event_type": event.type,
            "event_source": event.source,
            "promotion_score": score,
            "promotion_rule": reason,
            **{k: v for k, v in event.meta.items() if isinstance(v, (str, int, float, bool))},
        }

        try:
            # Write to HybridMemory — this itself publishes memory.* events
            mem_item = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.mem.add_session_memory(
                    session_id,
                    text,
                    node_type,
                    metadata,
                    auto_extract=len(text) > 40,
                ),
            )

            logger.info(
                f"[MemoryPromoter] Promoted {event.type} → memory:{mem_item.id} "
                f"(score={score:.2f}, rule={reason})"
            )

            # Record in Postgres
            if self.event_logger:
                await self.event_logger.record_memory_promotion(
                    event_id=event.id,
                    memory_node_id=mem_item.id,
                    session_id=session_id,
                    score=score,
                    reason=reason,
                )

            # Publish confirmation event
            await self.bus.publish(Event(
                type="memory.written",
                source="memory_promoter",
                payload={
                    "memory_node_id": mem_item.id,
                    "event_id": event.id,
                    "event_type": event.type,
                    "score": score,
                    "rule": reason,
                },
                meta={"session_id": session_id, "correlation_id": event.id},
            ))

        except Exception as exc:
            logger.error(
                f"[MemoryPromoter] Failed to promote {event.type}: {exc}", exc_info=True
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_session(self, event: Event) -> Optional[str]:
        if self._session_resolver:
            resolved = self._session_resolver(event)
            if resolved:
                return resolved
        return event.meta.get("session_id") or event.payload.get("session_id")

    def _node_type_for(self, event: Event) -> str:
        mapping = {
            "llm.complete": "LLMOutput",
            "tool.complete": "ToolResult",
            "task.complete": "TaskResult",
            "orchestrator.task.complete": "TaskResult",
            "agent.decision": "Decision",
            "focus.changed": "FocusChange",
        }
        return mapping.get(event.type, "Event")

    def _event_to_text(self, event: Event) -> str:
        """Convert an event to a human-readable memory text."""
        payload = event.payload

        # Common patterns
        if "result" in payload:
            result = str(payload["result"])[:2000]
            return f"[{event.type}] from {event.source}: {result}"

        if "output" in payload:
            output = str(payload["output"])[:2000]
            return f"[{event.type}] from {event.source}: {output}"

        if "message" in payload:
            return f"[{event.type}] {payload['message']}"

        if "tool_name" in payload:
            args_str = str(payload.get("args", ""))[:300]
            return (
                f"Tool execution: {payload['tool_name']}({args_str}) "
                f"→ {str(payload.get('result', ''))[:500]}"
            )

        # Fallback: serialise meaningful payload keys
        summary_keys = ["error", "status", "focus", "agent", "model", "task_name", "duration"]
        parts = [f"{k}={payload[k]}" for k in summary_keys if k in payload]
        base = f"[{event.type}] from {event.source}"
        return f"{base}: {', '.join(parts)}" if parts else base