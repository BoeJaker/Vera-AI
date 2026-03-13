"""
Vera EventBus — Postgres Persistence Layer
==========================================

Responsibilities
----------------
* DDL bootstrap  : Creates tables on first run (idempotent).
* EventLogger    : Async handler that writes every bus event to `vera_events`.
* LogBridge      : Adapts VeraLogger log records into bus events so that all
                   structured log output is also stored in Postgres alongside
                   the event stream.

Schema
------
vera_events          — canonical event log (one row per bus event)
vera_event_logs      — structured log records forwarded from VeraLogger
vera_memory_events   — events that were promoted to HybridMemory (FK → vera_events)

All writes are async via asyncpg.  A synchronous helper (SyncEventLogger) is
provided for code paths that cannot use async (e.g. VeraLogger callbacks).
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, Optional

try:
    import asyncpg
    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False
    logging.warning("[EventPostgres] asyncpg not installed — Postgres logging disabled. "
                    "Install with: pip install asyncpg")

from Vera.EventBus.event_model import Event

logger = logging.getLogger("vera.eventbus.postgres")


# ---------------------------------------------------------------------------
# DDL — run once at startup
# ---------------------------------------------------------------------------

DDL = """
-- Main event store: one row per published bus event
CREATE TABLE IF NOT EXISTS vera_events (
    id            TEXT        PRIMARY KEY,
    type          TEXT        NOT NULL,
    source        TEXT        NOT NULL,
    payload       JSONB       NOT NULL DEFAULT '{}',
    meta          JSONB       NOT NULL DEFAULT '{}',
    timestamp     TIMESTAMPTZ NOT NULL,
    retries       INTEGER     NOT NULL DEFAULT 0,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vera_events_type      ON vera_events (type);
CREATE INDEX IF NOT EXISTS idx_vera_events_source    ON vera_events (source);
CREATE INDEX IF NOT EXISTS idx_vera_events_timestamp ON vera_events (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_vera_events_payload   ON vera_events USING gin (payload);

-- Structured log records emitted by VeraLogger and forwarded to the bus
CREATE TABLE IF NOT EXISTS vera_event_logs (
    id            BIGSERIAL   PRIMARY KEY,
    event_id      TEXT        REFERENCES vera_events(id) ON DELETE SET NULL,
    level         TEXT        NOT NULL,
    component     TEXT,
    message       TEXT        NOT NULL,
    session_id    TEXT,
    agent         TEXT,
    model         TEXT,
    task_id       TEXT,
    provenance    JSONB,
    extra         JSONB       NOT NULL DEFAULT '{}',
    logged_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vera_event_logs_level     ON vera_event_logs (level);
CREATE INDEX IF NOT EXISTS idx_vera_event_logs_session   ON vera_event_logs (session_id);
CREATE INDEX IF NOT EXISTS idx_vera_event_logs_event_id  ON vera_event_logs (event_id);
CREATE INDEX IF NOT EXISTS idx_vera_event_logs_logged_at ON vera_event_logs (logged_at DESC);

-- Events that were promoted to HybridMemory
CREATE TABLE IF NOT EXISTS vera_memory_events (
    id            BIGSERIAL   PRIMARY KEY,
    event_id      TEXT        REFERENCES vera_events(id) ON DELETE CASCADE,
    memory_node_id TEXT,
    session_id    TEXT,
    promotion_score FLOAT,
    promotion_reason TEXT,
    promoted_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vera_memory_events_event    ON vera_memory_events (event_id);
CREATE INDEX IF NOT EXISTS idx_vera_memory_events_session  ON vera_memory_events (session_id);
CREATE INDEX IF NOT EXISTS idx_vera_memory_events_score    ON vera_memory_events (promotion_score DESC);
"""


# ---------------------------------------------------------------------------
# Connection pool wrapper
# ---------------------------------------------------------------------------

class PostgresPool:
    """Thin async wrapper around asyncpg connection pool."""

    def __init__(self, dsn: str, min_size: int = 2, max_size: int = 10):
        self.dsn = dsn
        self.min_size = min_size
        self.max_size = max_size
        self._pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        if not HAS_ASYNCPG:
            return
        self._pool = await asyncpg.create_pool(
            self.dsn,
            min_size=self.min_size,
            max_size=self.max_size,
        )
        await self._bootstrap()
        logger.info("[PostgresPool] Connected and schema bootstrapped.")

    async def _bootstrap(self):
        async with self._pool.acquire() as conn:
            await conn.execute(DDL)

    @asynccontextmanager
    async def acquire(self):
        if not self._pool:
            raise RuntimeError("PostgresPool not connected. Call await pool.connect() first.")
        async with self._pool.acquire() as conn:
            yield conn

    async def close(self):
        if self._pool:
            await self._pool.close()
            logger.info("[PostgresPool] Pool closed.")


# ---------------------------------------------------------------------------
# Async event logger
# ---------------------------------------------------------------------------

class EventLogger:
    """
    Async handler that persists every Event to `vera_events`.

    Attach to the bus:
        bus.subscribe("*", event_logger.handle)
    """

    def __init__(self, pool: PostgresPool):
        self.pool = pool

    async def handle(self, event: Event):
        """Subscribe handler — called for every event on the bus."""
        await self._write_event(event)

    async def _write_event(self, event: Event):
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO vera_events (id, type, source, payload, meta, timestamp, retries)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (id) DO UPDATE
                        SET retries = EXCLUDED.retries,
                            meta    = EXCLUDED.meta
                    """,
                    event.id,
                    event.type,
                    event.source,
                    json.dumps(event.payload),
                    json.dumps(event.meta),
                    datetime.fromisoformat(event.timestamp),
                    event.retries,
                )
        except Exception as exc:
            logger.error(f"[EventLogger] Failed to persist event {event.id}: {exc}")

    async def write_log_record(
        self,
        *,
        event_id: Optional[str] = None,
        level: str,
        component: str,
        message: str,
        session_id: Optional[str] = None,
        agent: Optional[str] = None,
        model: Optional[str] = None,
        task_id: Optional[str] = None,
        provenance: Optional[Dict[str, Any]] = None,
        extra: Optional[Dict[str, Any]] = None,
    ):
        """Write a structured log record from VeraLogger."""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO vera_event_logs
                        (event_id, level, component, message, session_id, agent,
                         model, task_id, provenance, extra)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                    """,
                    event_id,
                    level,
                    component,
                    message,
                    session_id,
                    agent,
                    model,
                    task_id,
                    json.dumps(provenance) if provenance else None,
                    json.dumps(extra or {}),
                )
        except Exception as exc:
            logger.error(f"[EventLogger] Failed to write log record: {exc}")

    async def record_memory_promotion(
        self,
        *,
        event_id: str,
        memory_node_id: str,
        session_id: Optional[str],
        score: float,
        reason: str,
    ):
        """Record that an event was promoted into HybridMemory."""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO vera_memory_events
                        (event_id, memory_node_id, session_id, promotion_score, promotion_reason)
                    VALUES ($1,$2,$3,$4,$5)
                    """,
                    event_id,
                    memory_node_id,
                    session_id,
                    score,
                    reason,
                )
        except Exception as exc:
            logger.error(f"[EventLogger] Failed to record memory promotion: {exc}")


# ---------------------------------------------------------------------------
# Synchronous bridge for VeraLogger
# ---------------------------------------------------------------------------

class SyncLogBridge:
    """
    Bridges the synchronous VeraLogger into the async EventBus + Postgres.

    Usage:
        bridge = SyncLogBridge(bus, pool, loop)
        # Patch into VeraLogger:
        vera_logger._postgres_bridge = bridge

        # In VeraLogger.info / .error / .debug — add at the end:
        vera_logger._postgres_bridge.emit(level, message, context)
    """

    def __init__(self, bus, pool: PostgresPool, loop: asyncio.AbstractEventLoop):
        self._bus = bus
        self._pool = pool
        self._loop = loop
        self._event_logger = EventLogger(pool)

    def emit(
        self,
        level: str,
        message: str,
        component: str = "vera",
        session_id: Optional[str] = None,
        agent: Optional[str] = None,
        model: Optional[str] = None,
        task_id: Optional[str] = None,
        provenance: Optional[Dict] = None,
        extra: Optional[Dict] = None,
        publish_as_event: bool = False,
    ):
        """
        Called from synchronous VeraLogger methods.
        Schedules async Postgres write + optional bus publish on the event loop.
        """
        if not HAS_ASYNCPG or not self._pool._pool:
            return

        coro = self._event_logger.write_log_record(
            level=level,
            component=component,
            message=message,
            session_id=session_id,
            agent=agent,
            model=model,
            task_id=task_id,
            provenance=provenance,
            extra=extra or {},
        )
        asyncio.run_coroutine_threadsafe(coro, self._loop)

        if publish_as_event and level in ("ERROR", "CRITICAL", "WARNING"):
            from Vera.EventBus.event_model import Event as BusEvent
            evt = BusEvent(
                type=f"log.{level.lower()}",
                source=component,
                payload={"message": message, "level": level},
                meta={
                    "session_id": session_id,
                    "agent": agent,
                    "model": model,
                    "task_id": task_id,
                },
            )
            asyncio.run_coroutine_threadsafe(self._bus.publish(evt), self._loop)