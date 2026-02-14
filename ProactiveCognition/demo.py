"""
Demo: boot the cognition system with in-memory adapters and run a task
through the full lifecycle.

    python -m cognition.demo

This uses the EchoLLM stub so no external services are needed.
"""

import asyncio
import logging

from ProactiveCognition import CognitionManager, CognitionConfig, TaskPriority
from ProactiveCognition.adapters_memory import (
    InMemoryStore, ConsoleMessaging, StubToolRouter, EchoLLM, InMemoryEventBus,
)
from ProactiveCognition.loops.background import BackgroundConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)-25s] %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("demo")


async def main():
    # ── assemble ──
    memory = InMemoryStore()
    messaging = ConsoleMessaging()
    tools = StubToolRouter()
    llm = EchoLLM()
    bus = InMemoryEventBus()

    config = CognitionConfig(
        max_workers=3,
        max_concurrent_tasks=10,
        task_requeue_delay_s=0.5,          # fast for demo
        enable_background_loop=True,
        background=BackgroundConfig(
            cycle_interval_s=10.0,          # fast for demo
            event_lookback_s=300.0,
            min_events_for_analysis=1,
        ),
    )

    manager = CognitionManager(
        llm=llm, memory=memory, messaging=messaging,
        tools=tools, event_bus=bus, config=config,
    )

    await manager.start()

    # ── simulate some feed events ──
    logger.info("Publishing feed events...")
    for i in range(5):
        await bus.publish("feed.news", {
            "topic": "feed.news",
            "summary": f"Market update #{i}: BTC moved significantly",
        })

    # ── create a manual task ──
    logger.info("Creating manual task...")
    task = await manager.create_task(
        "Analyse BTC volatility over the last 24 hours",
        priority=TaskPriority.HIGH,
    )
    logger.info("Task created: %s (id=%s)", task.goal, task.id)

    # ── let the system run ──
    logger.info("Letting the system work...")
    await asyncio.sleep(8.0)

    # ── check status ──
    status = await manager.get_status()
    logger.info("System status: %s", status)

    # ── check task result ──
    result = await manager.get_task(task.id)
    if result:
        logger.info("Task %s final status: %s", result.id, result.status.value)
        logger.info("Progress log:")
        for entry in result.progress_log:
            logger.info("  [%s] %s", entry.level, entry.message)
        if result.artifacts.get("summary"):
            logger.info("Summary: %s", result.artifacts["summary"])

    # ── shutdown ──
    await manager.shutdown()
    logger.info("Done.")


if __name__ == "__main__":
    asyncio.run(main())