"""
Vera EventBus — Standalone Runner
===================================

Runs the enhanced event bus in standalone mode (without a full Vera instance).
Useful for testing, monitoring dashboards, or multi-process deployments where
the bus runs as a separate service.

For integrated use inside Vera, see:
    Vera/EventBus/integration.py  →  setup_event_bus_sync(vera_instance)

Quick start
-----------
    # Ensure Redis and Postgres are running, then:
    python -m Vera.EventBus.run_event_bus

Environment variables (override config.py defaults)
----------------------------------------------------
    REDIS_URL      redis://localhost:6379
    POSTGRES_DSN   postgresql://postgres:password@localhost:5432/vera
"""

from __future__ import annotations

import asyncio
import logging
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)-30s %(levelname)-8s %(message)s",
)

from Vera.EventBus.redis_bus import EnhancedRedisEventBus
from Vera.EventBus.event_model import Event
from Vera.EventBus.config import POSTGRES_DSN, REDIS_URL


# ---------------------------------------------------------------------------
# Example consumers — replace / extend with real handlers
# ---------------------------------------------------------------------------

async def anomaly_detector(event: Event):
    """Example: detect anomalies in system.* events."""
    cpu = event.payload.get("cpu", 0)
    if cpu and float(cpu) > 85:
        print(f"[AnomalyDetector] HIGH CPU: {cpu}%  source={event.source}")


async def console_notifier(event: Event):
    """Example: print any event that ends with .detected or .alert.*"""
    print(f"[ALERT] {event.type} | {event.payload}")


# ---------------------------------------------------------------------------
# Example sensors — replace with real data sources
# ---------------------------------------------------------------------------

async def test_sensor(bus: EnhancedRedisEventBus):
    import psutil
    while True:
        await asyncio.sleep(5)
        cpu = psutil.cpu_percent()
        await bus.publish(Event(
            type="system.cpu.sample",
            source="sensor.cpu",
            payload={"cpu": cpu, "unit": "%"},
        ))
        if cpu > 70:
            await bus.publish(Event(
                type="system.alert.high_cpu",
                source="sensor.cpu",
                payload={"cpu": cpu},
            ), priority=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    print("🚀 Starting Vera Enhanced Event Bus (standalone)")

    dsn = os.getenv("POSTGRES_DSN", POSTGRES_DSN)
    redis_url = os.getenv("REDIS_URL", REDIS_URL)

    bus = EnhancedRedisEventBus(
        consumer_name="standalone-node-1",
        postgres_dsn=dsn,
        # No hybrid_memory or vera_logger in standalone mode
        redis_url=redis_url,
    )

    await bus.connect()

    # -----------------------------------------------------------------------
    # Wire up your consumers here
    # -----------------------------------------------------------------------
    bus.subscribe("system.*",   anomaly_detector)
    bus.subscribe("*.alert.*",  console_notifier)

    # -----------------------------------------------------------------------
    # Start background sensors / producers
    # -----------------------------------------------------------------------
    asyncio.create_task(test_sensor(bus))

    print("✅ Event bus running.  Press Ctrl-C to stop.")
    print("   Redis:    ", redis_url)
    print("   Postgres: ", dsn)

    try:
        await bus.start()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        await bus.close()
        print("✅ Shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())