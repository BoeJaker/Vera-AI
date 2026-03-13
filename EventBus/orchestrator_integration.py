"""
Vera EventBus — Orchestrator Integration
=========================================

Wires the task Orchestrator's EventBus (local pub/sub) into the global
EnhancedRedisEventBus so that every task lifecycle event is:

  1. Published to the Redis stream  (→ all bus subscribers see it)
  2. Persisted to Postgres          (→ ``vera_events`` table)
  3. Scored for memory promotion    (→ ``MemoryPromoter`` picks up significant results)

Mapping: Orchestrator local channels → bus event types
-------------------------------------------------------
  task.started         → orchestrator.task.started
  task.completed       → orchestrator.task.complete
  task.failed          → orchestrator.task.failed

Usage
-----
Call ``wire_orchestrator_to_bus(orchestrator, bus, session_id_fn)`` after
both are initialised:

    from Vera.EventBus.orchestrator_integration import wire_orchestrator_to_bus
    wire_orchestrator_to_bus(vera.orchestrator, vera.bus, lambda: vera.sess.id)

The original Orchestrator.event_bus (local EventBus) keeps working normally.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Dict, Optional

log = logging.getLogger("vera.eventbus.orchestrator_integration")


def wire_orchestrator_to_bus(
    orchestrator,
    bus,
    session_id_fn: Optional[Callable[[], Optional[str]]] = None,
    loop: Optional[asyncio.AbstractEventLoop] = None,
):
    """
    Subscribe to the Orchestrator's local EventBus and forward all task
    lifecycle events to the global Redis bus.

    Parameters
    ----------
    orchestrator   : Orchestrator instance (from vera_tasks.py)
    bus            : EnhancedRedisEventBus instance
    session_id_fn  : callable returning the current session_id or None
    loop           : running event loop (auto-detected if None)
    """
    _loop = loop or asyncio.get_event_loop()

    def _publish(event_type: str, payload: Dict[str, Any]):
        from Vera.EventBus.event_model import Event
        sid = session_id_fn() if session_id_fn else None
        meta: Dict[str, Any] = {}
        if sid:
            meta["session_id"] = sid

        evt = Event(type=event_type, source="orchestrator", payload=payload, meta=meta)
        asyncio.run_coroutine_threadsafe(bus.publish(evt), _loop)

    # ------------------------------------------------------------------
    # Subscribe to local Orchestrator EventBus channels
    # ------------------------------------------------------------------

    def _on_task_started(message: Dict[str, Any]):
        _publish("orchestrator.task.started", {
            "task_id":   message.get("task_id", "")[:8],
            "task_name": message.get("task_name"),
            "worker_id": message.get("worker_id"),
            "started_at": message.get("started_at"),
        })

    def _on_task_completed(message: Dict[str, Any]):
        _publish("orchestrator.task.complete", {
            "task_id":    message.get("task_id", "")[:8],
            "task_name":  message.get("task_name"),
            "worker_id":  message.get("worker_id"),
            "duration":   message.get("duration"),
            "is_streaming": message.get("is_streaming", False),
        })

    def _on_task_failed(message: Dict[str, Any]):
        _publish("orchestrator.task.failed", {
            "task_id":   message.get("task_id", "")[:8],
            "task_name": message.get("task_name"),
            "worker_id": message.get("worker_id"),
            "error":     message.get("error"),
            "duration":  message.get("duration"),
        })

    orchestrator.event_bus.subscribe("task.started",   _on_task_started)
    orchestrator.event_bus.subscribe("task.completed", _on_task_completed)
    orchestrator.event_bus.subscribe("task.failed",    _on_task_failed)

    log.info(
        "[OrchestratorIntegration] Orchestrator wired to EventBus — "
        "task lifecycle events will be published."
    )


def wire_llm_metrics_to_bus(
    vera_logger,
    bus,
    session_id_fn: Optional[Callable[[], Optional[str]]] = None,
    loop: Optional[asyncio.AbstractEventLoop] = None,
):
    """
    Patch VeraLogger.end_llm_operation to also publish llm.complete events.

    This is separate from _patch_vera_logger in redis_bus.py, which handles
    text log records.  This patch handles the structured LLM metrics.
    """
    _loop = loop or asyncio.get_event_loop()
    _orig = vera_logger.end_llm_operation

    def _end_llm_operation(input_tokens, output_tokens, model=None, provider=None, cache_hit=False):
        metrics = _orig(input_tokens, output_tokens, model=model, provider=provider, cache_hit=cache_hit)
        if metrics:
            from Vera.EventBus.event_model import Event
            sid = session_id_fn() if session_id_fn else None
            evt = Event(
                type="llm.complete",
                source=f"llm.{model or 'unknown'}",
                payload={
                    "model":          model,
                    "provider":       provider,
                    "input_tokens":   input_tokens,
                    "output_tokens":  output_tokens,
                    "total_tokens":   metrics.total_tokens,
                    "tokens_per_sec": round(metrics.tokens_per_second, 2),
                    "duration":       round(metrics.duration, 3),
                    "cache_hit":      cache_hit,
                    "ttft":           round(metrics.first_token_latency, 3) if metrics.first_token_latency else None,
                },
                meta={"session_id": sid} if sid else {},
            )
            asyncio.run_coroutine_threadsafe(bus.publish(evt), _loop)
        return metrics

    vera_logger.end_llm_operation = _end_llm_operation
    log.info("[LLMMetricsIntegration] VeraLogger.end_llm_operation wired to EventBus.")