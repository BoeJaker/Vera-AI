"""
Vera EventBus — Enhanced RedisEventBus
=======================================

Drop-in replacement for the original RedisEventBus that adds:

  1. Postgres persistence  — every event is written to ``vera_events`` via
     ``EventLogger`` before dispatching to subscribers.

  2. VeraLogger bridge    — publishes structured log records to the bus so
     they land in ``vera_event_logs`` in Postgres (errors/warnings also
     appear as ``log.*`` bus events).

  3. Memory promotion     — ``MemoryPromoter`` is wired as an internal
     subscriber and selectively promotes events into ``HybridMemory``.

  4. Graceful degradation — if Postgres is unavailable the bus still works;
     if Redis is unavailable the bus raises on ``connect()``.

Wire-up (in run_event_bus.py or Vera.__init__):
    bus = EnhancedRedisEventBus(
        consumer_name="node-1",
        postgres_dsn=POSTGRES_DSN,
        hybrid_memory=vera.mem,
        vera_logger=vera.logger,
        session_resolver=lambda event: vera.sess.id,
    )
    await bus.connect()          # connects Redis + Postgres, starts promoter
    bus.subscribe("system.*", anomaly_detector)
    asyncio.create_task(bus.start())
"""

from __future__ import annotations

import asyncio
import fnmatch
import json
import logging
from typing import Any, Callable, Dict, List, Optional

import redis.asyncio as aioredis

from Vera.EventBus.event_model import Event
from Vera.EventBus.config import (
    REDIS_URL,
    STREAM_EVENTS,
    STREAM_PRIORITY,
    STREAM_DLQ,
    CONSUMER_GROUP,
    MAX_RETRIES,
    RETRY_DELAY_SEC,
    POSTGRES_DSN,
)
from Vera.EventBus.postgres import PostgresPool, EventLogger, SyncLogBridge
from Vera.EventBus.promoter import MemoryPromoter

log = logging.getLogger("vera.eventbus")


class EnhancedRedisEventBus:
    """
    Redis Streams event bus with integrated Postgres logging and
    selective memory promotion.

    Parameters
    ----------
    consumer_name : str
        Unique name for this consumer within the consumer group.
    postgres_dsn : str
        asyncpg-compatible DSN, e.g. ``postgresql://user:pw@host/db``.
    hybrid_memory : HybridMemory | None
        If provided, a MemoryPromoter is attached automatically.
    vera_logger : VeraLogger | None
        If provided, a SyncLogBridge is installed so VeraLogger output
        flows into Postgres.
    session_resolver : Callable[[Event], str | None] | None
        Called during memory promotion to find the current session_id.
    redis_url : str
        Redis connection string (defaults to config.REDIS_URL).
    """

    def __init__(
        self,
        consumer_name: str,
        postgres_dsn: str = POSTGRES_DSN,
        hybrid_memory=None,
        vera_logger=None,
        session_resolver: Optional[Callable[[Event], Optional[str]]] = None,
        redis_url: str = REDIS_URL,
    ):
        self.consumer_name = consumer_name
        self._redis_url = redis_url
        self.redis: Optional[aioredis.Redis] = None
        self.subscribers: Dict[str, List[Callable]] = {}

        # Postgres
        self._pg_pool = PostgresPool(postgres_dsn)
        self._event_logger = EventLogger(self._pg_pool)

        # Memory promoter (wired after connect)
        self._hybrid_memory = hybrid_memory
        self._promoter: Optional[MemoryPromoter] = None
        self._session_resolver = session_resolver

        # VeraLogger bridge
        self._vera_logger = vera_logger
        self._sync_bridge: Optional[SyncLogBridge] = None

        # Internal flag so VeraLogger patching only happens once
        self._logger_patched = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self):
        """Connect to Redis + Postgres and bootstrap all subsystems."""
        # Redis
        self.redis = aioredis.from_url(self._redis_url, decode_responses=True)
        await self._create_group(STREAM_EVENTS)
        await self._create_group(STREAM_PRIORITY)
        log.info("[EventBus] Redis connected.")

        # Postgres
        await self._pg_pool.connect()

        # Memory promoter
        if self._hybrid_memory:
            self._promoter = MemoryPromoter(
                hybrid_memory=self._hybrid_memory,
                bus=self,
                event_logger=self._event_logger,
                session_resolver=self._session_resolver,
            )
            # Subscribe with lowest-priority wildcard so every event is seen
            self.subscribe("*", self._promoter.handle)
            log.info("[EventBus] MemoryPromoter attached.")

        # VeraLogger bridge — patch into the running logger
        if self._vera_logger and not self._logger_patched:
            loop = asyncio.get_event_loop()
            self._sync_bridge = SyncLogBridge(self, self._pg_pool, loop)
            self._patch_vera_logger(self._vera_logger)
            self._logger_patched = True
            log.info("[EventBus] VeraLogger bridge installed.")

        # Subscribe the Postgres event logger to every event
        self.subscribe("*", self._event_logger.handle)
        log.info("[EventBus] Postgres EventLogger attached.")

    async def close(self):
        if self.redis:
            await self.redis.close()
        await self._pg_pool.close()
        log.info("[EventBus] Shutdown complete.")

    # ------------------------------------------------------------------
    # Pub / Sub
    # ------------------------------------------------------------------

    def subscribe(self, topic_pattern: str, handler: Callable):
        self.subscribers.setdefault(topic_pattern, []).append(handler)

    async def publish(self, event: Event, priority: bool = False):
        """Publish an event to Redis Streams."""
        stream = STREAM_PRIORITY if priority else STREAM_EVENTS
        await self.redis.xadd(stream, {"event": event.model_dump_json()})

    # ------------------------------------------------------------------
    # Convenience publishers — used by Vera subsystems
    # ------------------------------------------------------------------

    async def publish_memory_event(
        self,
        operation: str,
        details: Dict[str, Any],
        session_id: Optional[str] = None,
    ):
        """Publish a memory.* event (every memory op flows through the bus)."""
        await self.publish(Event(
            type=f"memory.{operation}",
            source="hybrid_memory",
            payload=details,
            meta={"session_id": session_id} if session_id else {},
        ))

    async def publish_task_event(
        self,
        task_name: str,
        status: str,
        details: Dict[str, Any],
        session_id: Optional[str] = None,
    ):
        """Publish an orchestrator task lifecycle event."""
        await self.publish(Event(
            type=f"orchestrator.task.{status}",
            source="orchestrator",
            payload={"task_name": task_name, **details},
            meta={"session_id": session_id} if session_id else {},
        ))

    async def publish_llm_event(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        duration: float,
        session_id: Optional[str] = None,
        agent: Optional[str] = None,
    ):
        """Publish an llm.complete event for every LLM call."""
        await self.publish(Event(
            type="llm.complete",
            source=f"llm.{model}",
            payload={
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "duration": duration,
            },
            meta={
                "session_id": session_id,
                "agent": agent,
            },
        ))

    async def publish_tool_event(
        self,
        tool_name: str,
        args: Dict[str, Any],
        result: Any,
        duration: float,
        success: bool = True,
        session_id: Optional[str] = None,
    ):
        """Publish a tool.complete (or tool.error) event."""
        event_type = "tool.complete" if success else "tool.error"
        result_str = str(result)[:1000] if result is not None else None
        await self.publish(Event(
            type=event_type,
            source=f"tool.{tool_name}",
            payload={
                "tool_name": tool_name,
                "args": {k: str(v)[:200] for k, v in args.items()},
                "result": result_str,
                "duration": duration,
                "success": success,
            },
            meta={"session_id": session_id} if session_id else {},
        ))

    # ------------------------------------------------------------------
    # Consumer loop
    # ------------------------------------------------------------------

    async def start(self):
        """Main consumer loop — reads from both streams round-robin."""
        log.info("[EventBus] Consumer loop started.")
        while True:
            await self._consume_stream(STREAM_PRIORITY)
            await self._consume_stream(STREAM_EVENTS)

    async def _consume_stream(self, stream: str):
        response = await self.redis.xreadgroup(
            groupname=CONSUMER_GROUP,
            consumername=self.consumer_name,
            streams={stream: ">"},
            count=10,
            block=100,          # short block so priority stream is checked often
        )
        if not response:
            return

        for _, messages in response:
            for message_id, data in messages:
                event = Event.model_validate_json(data["event"])
                try:
                    await self._dispatch(event)
                    await self.redis.xack(stream, CONSUMER_GROUP, message_id)
                except Exception as exc:
                    await self._handle_failure(event, message_id, stream, exc)

    async def _dispatch(self, event: Event):
        tasks = []
        for pattern, handlers in self.subscribers.items():
            if fnmatch.fnmatch(event.type, pattern):
                for handler in handlers:
                    tasks.append(asyncio.create_task(handler(event)))
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, Exception):
                    log.error(f"[EventBus] Subscriber error for {event.type}: {r}")

    async def _handle_failure(
        self, event: Event, message_id: str, stream: str, error: Exception
    ):
        log.error(f"[EventBus] Dispatch failed for {event.type}: {error}")
        event.retries += 1
        event.meta["last_error"] = str(error)

        if event.retries >= MAX_RETRIES:
            log.error(f"[EventBus] DLQ: {event.type} after {event.retries} retries")
            await self.redis.xadd(STREAM_DLQ, {"event": event.model_dump_json()})
            await self.redis.xack(stream, CONSUMER_GROUP, message_id)
        else:
            log.warning(f"[EventBus] Retry {event.retries}/{MAX_RETRIES}: {event.type}")
            await asyncio.sleep(RETRY_DELAY_SEC)
            await self.publish(event)
            await self.redis.xack(stream, CONSUMER_GROUP, message_id)

    # ------------------------------------------------------------------
    # Redis group helpers
    # ------------------------------------------------------------------

    async def _create_group(self, stream: str):
        try:
            await self.redis.xgroup_create(stream, CONSUMER_GROUP, id="0", mkstream=True)
        except aioredis.ResponseError:
            pass  # group already exists

    # ------------------------------------------------------------------
    # VeraLogger patching
    # ------------------------------------------------------------------

    def _patch_vera_logger(self, vera_logger):
        """
        Monkey-patch VeraLogger methods to also emit to Postgres.

        We wrap the key public methods (info, debug, warning, error, critical)
        so that every structured log call is forwarded to the SyncLogBridge
        without breaking any existing behaviour.
        """
        bridge = self._sync_bridge

        def _wrap(original_fn, level: str):
            def wrapped(message: str, context=None, **kwargs):
                original_fn(message, context=context, **kwargs)
                session_id = None
                agent = None
                model = None
                task_id = None
                provenance = None
                if context:
                    session_id = getattr(context, "session_id", None)
                    agent = getattr(context, "agent", None)
                    model = getattr(context, "model", None)
                    task_id = getattr(context, "task_id", None)
                    prov = getattr(context, "provenance", None)
                    if prov:
                        provenance = prov.to_dict()

                # publish errors/warnings as bus events too
                publish = level in ("ERROR", "CRITICAL", "WARNING")
                bridge.emit(
                    level=level,
                    message=message,
                    component=vera_logger.component,
                    session_id=session_id,
                    agent=agent,
                    model=model,
                    task_id=task_id,
                    provenance=provenance,
                    publish_as_event=publish,
                )
            return wrapped

        vera_logger.info     = _wrap(vera_logger.info,     "INFO")
        vera_logger.debug    = _wrap(vera_logger.debug,    "DEBUG")
        vera_logger.warning  = _wrap(vera_logger.warning,  "WARNING")
        vera_logger.error    = _wrap(vera_logger.error,    "ERROR")
        vera_logger.critical = _wrap(vera_logger.critical, "CRITICAL")
        vera_logger.success  = _wrap(vera_logger.success,  "SUCCESS")