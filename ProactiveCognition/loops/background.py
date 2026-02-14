"""
Background Cognition Loop — the "always-on" situational awareness layer.

Runs on a configurable interval. Each cycle:
  1. Pulls recent events from memory
  2. Asks the LLM to summarise / detect patterns / generate insights
  3. Stores insights
  4. Optionally proposes new tasks for the focused loop

This is intentionally low-intensity — it should use a small, fast model
and short prompts. Heavy analysis belongs in focused tasks.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import List, Optional

from ..interfaces import LLMBackend, MemoryStore, MessagingGateway
from ..models import Insight, IngestedEvent, Task, TaskPriority, TaskStatus

logger = logging.getLogger(__name__)


# ── Configuration ─────────────────────────────────────────────

@dataclass
class BackgroundConfig:
    cycle_interval_s: float = 120.0       # seconds between cycles
    event_lookback_s: float = 600.0       # how far back to scan
    max_events_per_cycle: int = 50
    min_events_for_analysis: int = 2      # don't burn tokens on 1 event
    max_insights_per_cycle: int = 5
    auto_spawn_tasks: bool = True         # create tasks from insights
    notify_new_insights: bool = False     # message the user on insight


# ── Prompts ───────────────────────────────────────────────────

SUMMARISE_SYSTEM = (
    "You are a background intelligence analyst for a personal AI system.\n"
    "You receive batches of recent events ingested from feeds (news, social, sensors, market data, etc.).\n\n"
    "Your job:\n"
    "1. Identify what changed or what's notable.\n"
    "2. Detect any patterns across events.\n"
    "3. Produce concise insights (1-2 sentences each).\n"
    "4. If an insight warrants deeper investigation, mark it as actionable.\n\n"
    "Respond ONLY with valid JSON:\n"
    '{\n'
    '  "insights": [\n'
    '    {"text": "...", "confidence": 0.0-1.0, "tags": ["..."], "actionable": false}\n'
    '  ],\n'
    '  "proposed_tasks": [\n'
    '    {"goal": "...", "priority": "normal|high|low", "reason": "..."}\n'
    '  ]\n'
    '}'
)


def _build_event_digest(events: List[IngestedEvent]) -> str:
    lines = []
    for e in events:
        lines.append(f"[{e.topic}] {e.summary}")
    return "\n".join(lines)


# ── Loop ──────────────────────────────────────────────────────

class BackgroundLoop:
    """
    Runs as a long-lived asyncio task. Call `start()` to begin,
    `stop()` to gracefully halt.
    """

    def __init__(
        self,
        llm: LLMBackend,
        memory: MemoryStore,
        messaging: MessagingGateway,
        config: Optional[BackgroundConfig] = None,
        on_task_proposed=None,         # async callback(Task)
    ):
        self.llm = llm
        self.memory = memory
        self.messaging = messaging
        self.config = config or BackgroundConfig()
        self._on_task_proposed = on_task_proposed
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._cycle_count = 0
        self._last_cycle_at: Optional[float] = None

    # ── lifecycle ──

    async def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="background-loop")
        logger.info("Background loop started (interval=%ss)", self.config.cycle_interval_s)

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Background loop stopped after %d cycles", self._cycle_count)

    @property
    def is_running(self) -> bool:
        return self._running

    # ── main loop ──

    async def _loop(self):
        while self._running:
            try:
                await self._run_cycle()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Background cycle failed")

            await asyncio.sleep(self.config.cycle_interval_s)

    async def _run_cycle(self):
        t0 = time.time()
        self._cycle_count += 1

        # 1. gather recent events
        events = await self.memory.get_recent_events(
            seconds=self.config.event_lookback_s,
            limit=self.config.max_events_per_cycle,
        )

        if len(events) < self.config.min_events_for_analysis:
            logger.debug("Cycle %d: only %d events, skipping", self._cycle_count, len(events))
            return

        # 2. build digest and ask the LLM
        digest = _build_event_digest(events)
        messages = [{"role": "user", "content": digest}]

        raw_response = await self.llm.complete(
            messages=messages,
            system=SUMMARISE_SYSTEM,
            temperature=0.3,
            max_tokens=1024,
        )

        # 3. parse structured output
        try:
            result = json.loads(raw_response)
        except json.JSONDecodeError:
            logger.warning("Background LLM returned non-JSON, skipping cycle")
            return

        # 4. store insights
        insights_data = result.get("insights", [])
        stored = 0
        for item in insights_data[: self.config.max_insights_per_cycle]:
            insight = Insight(
                text=item["text"],
                confidence=item.get("confidence", 0.5),
                tags=item.get("tags", []),
                source="background",
            )
            await self.memory.store_insight(insight)
            stored += 1

            if self.config.notify_new_insights and insight.confidence >= 0.7:
                await self.messaging.send_message(
                    f"💡 Insight: {insight.text}"
                )

        # 5. propose tasks
        proposed = result.get("proposed_tasks", [])
        if self.config.auto_spawn_tasks and self._on_task_proposed:
            for item in proposed:
                pri_map = {
                    "critical": TaskPriority.CRITICAL,
                    "high": TaskPriority.HIGH,
                    "normal": TaskPriority.NORMAL,
                    "low": TaskPriority.LOW,
                }
                task = Task(
                    goal=item["goal"],
                    priority=pri_map.get(item.get("priority", "normal"), TaskPriority.NORMAL),
                    origin="background",
                )
                await self._on_task_proposed(task)

        elapsed = time.time() - t0
        self._last_cycle_at = time.time()
        logger.info(
            "Cycle %d: %d events → %d insights, %d tasks proposed (%.2fs)",
            self._cycle_count, len(events), stored, len(proposed), elapsed,
        )

    # ── manual trigger ──

    async def trigger_cycle(self):
        """Run a cycle on demand (e.g. from an API endpoint)."""
        await self._run_cycle()