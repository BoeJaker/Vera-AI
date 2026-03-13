"""
Vera EventBus — Integration Bootstrap
=======================================

Single entry point that wires the entire event bus system into a live
Vera instance.  Call this from ``Vera.__init__`` after the orchestrator,
memory, and logger are all initialised.

Usage in Vera.__init__ (add near the end, after all subsystems are up):
-----------------------------------------------------------------------
    from Vera.EventBus.integration import setup_event_bus
    self.bus = await setup_event_bus(self)

Or if Vera.__init__ is synchronous (it currently is), use the sync shim:
    from Vera.EventBus.integration import setup_event_bus_sync
    self.bus = setup_event_bus_sync(self)

What gets wired
---------------
1. EnhancedRedisEventBus — connects to Redis + Postgres, starts consumer loop
   in the background.
2. HybridMemory   — all memory operations emit bus events.
3. Orchestrator   — task lifecycle events forwarded to the bus.
4. VeraLogger     — log records forwarded to Postgres; errors/warnings
   also become bus events.
5. LLM metrics    — end_llm_operation publishes llm.complete events.

The consumer loop is started as a background asyncio task, so the bus
runs concurrently with the rest of Vera without blocking.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Optional

log = logging.getLogger("vera.eventbus.integration")


async def setup_event_bus(vera_instance) -> "EnhancedRedisEventBus":
    """
    Async version — call from an async context or run via asyncio.run().
    """
    from Vera.EventBus.redis_bus import EnhancedRedisEventBus
    from Vera.EventBus.memory_integration import wire_memory_to_bus
    from Vera.EventBus.orchestrator_integration import (
        wire_orchestrator_to_bus,
        wire_llm_metrics_to_bus,
    )
    from Vera.EventBus.config import POSTGRES_DSN

    # Session ID resolver — always returns the current session, even if it
    # changes later (closures capture the vera_instance, not the session).
    def _session_id():
        sess = getattr(vera_instance, "sess", None)
        return sess.id if sess else None

    bus = EnhancedRedisEventBus(
        consumer_name="vera-main",
        postgres_dsn=POSTGRES_DSN,
        hybrid_memory=getattr(vera_instance, "mem", None),
        vera_logger=getattr(vera_instance, "logger", None),
        session_resolver=lambda event: _session_id(),
    )

    await bus.connect()

    loop = asyncio.get_event_loop()

    # Wire HybridMemory
    if hasattr(vera_instance, "mem") and vera_instance.mem:
        wire_memory_to_bus(vera_instance.mem, bus, session_id_fn=_session_id, loop=loop)
        log.info("[EventBusIntegration] HybridMemory wired.")

    # Wire Orchestrator
    if hasattr(vera_instance, "orchestrator") and vera_instance.orchestrator:
        wire_orchestrator_to_bus(vera_instance.orchestrator, bus, session_id_fn=_session_id, loop=loop)
        log.info("[EventBusIntegration] Orchestrator wired.")

    # Wire LLM metrics
    if hasattr(vera_instance, "logger") and vera_instance.logger:
        wire_llm_metrics_to_bus(vera_instance.logger, bus, session_id_fn=_session_id, loop=loop)
        log.info("[EventBusIntegration] LLM metrics wired.")

    # Start consumer loop as background task
    asyncio.create_task(bus.start(), name="vera-event-bus")
    log.info("[EventBusIntegration] Event bus consumer task started.")

    return bus


def setup_event_bus_sync(vera_instance) -> Optional["EnhancedRedisEventBus"]:
    """
    Synchronous shim for use inside Vera.__init__ (which is not async).

    Spins up a dedicated event loop thread that owns the bus and all async
    I/O.  The bus is then accessible from Vera via vera.bus.

    The consumer loop runs in that thread for the lifetime of the process.
    """
    import concurrent.futures

    result_future: concurrent.futures.Future = concurrent.futures.Future()

    def _run_loop():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def _inner():
            bus = await setup_event_bus(vera_instance)
            result_future.set_result(bus)
            # Keep loop alive — bus.start() is already a background task
            # but we need the loop to stay running for all async bus ops.
            while True:
                await asyncio.sleep(3600)

        try:
            loop.run_until_complete(_inner())
        except Exception as exc:
            if not result_future.done():
                result_future.set_exception(exc)

    thread = threading.Thread(target=_run_loop, daemon=True, name="VeraEventBusLoop")
    thread.start()

    try:
        bus = result_future.result(timeout=15)
        log.info("[EventBusIntegration] Bus loop started in background thread.")
        return bus
    except Exception as exc:
        log.error(f"[EventBusIntegration] Failed to start event bus: {exc}", exc_info=True)
        return None