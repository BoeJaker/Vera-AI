"""
Vera Runner Registry
====================
Manages dynamic registration of Ollama (and other) LLM runners as first-class
citizens in the orchestration system.

Runners register themselves with capabilities (gpu, models, concurrency limits).
The orchestrator uses the registry for capability-based task routing, health
monitoring, and automatic failover — replacing the split logic that previously
lived partly in MultiInstanceOllamaManager and partly in WorkerPool.
"""

import threading
import time
import logging
import requests
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set
from enum import Enum, auto


class RunnerStatus(Enum):
    HEALTHY    = auto()
    DEGRADED   = auto()   # Responding but slow / high load
    UNHEALTHY  = auto()
    DRAINING   = auto()   # Graceful shutdown in progress
    OFFLINE    = auto()


@dataclass
class RunnerCapabilities:
    """
    Static + dynamic capabilities for a runner.
    Static ones are declared at registration; dynamic ones (loaded_models)
    are refreshed periodically by the health-check loop.
    """
    # Static — set at registration time
    gpu:              bool       = False
    max_concurrent:   int        = 2
    priority:         int        = 0          # Higher = preferred
    api_url:          str        = ""
    tags:             Set[str]   = field(default_factory=set)   # e.g. {"local", "fast"}

    # Dynamic — updated by health checks
    loaded_models:    Set[str]   = field(default_factory=set)
    active_requests:  int        = 0
    total_requests:   int        = 0
    total_failures:   int        = 0
    total_duration:   float      = 0.0
    last_seen:        float      = 0.0
    status:           RunnerStatus = RunnerStatus.OFFLINE

    @property
    def load_factor(self) -> float:
        """0.0 (idle) → 1.0 (at capacity)"""
        if self.max_concurrent == 0:
            return 1.0
        return self.active_requests / self.max_concurrent

    @property
    def avg_duration(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.total_duration / self.total_requests

    def has_model(self, model: str) -> bool:
        """Check if runner has a model (normalises :latest suffix)."""
        normalised = model if ":" in model else f"{model}:latest"
        return normalised in self.loaded_models or model in self.loaded_models

    def has_capacity(self) -> bool:
        return (
            self.status in (RunnerStatus.HEALTHY, RunnerStatus.DEGRADED)
            and self.active_requests < self.max_concurrent
        )


class RunnerRegistry:
    """
    Central registry for all execution runners.

    Runners can be:
      - Ollama instances (registered by MultiInstanceOllamaManager)
      - Future: vLLM endpoints, OpenAI-compatible APIs, local GPU processes, …

    Responsibilities
    ----------------
    * Register / deregister runners at runtime
    * Maintain live capability snapshots via background health checks
    * Provide capability-based runner selection (with GPU-preference logic)
    * Emit events via the shared EventBus on status transitions
    * Expose acquire / release primitives used by OllamaRunnerWorker
    """

    # How often to poll runner health (seconds)
    HEALTH_CHECK_INTERVAL = 30.0
    # Consider a runner DEGRADED if it hasn't responded within this window
    STALE_THRESHOLD = 90.0

    def __init__(self, event_bus=None):
        self._runners:  Dict[str, RunnerCapabilities] = {}
        self._locks:    Dict[str, threading.Lock]     = {}
        self._registry_lock = threading.RLock()

        self._event_bus = event_bus
        self._callbacks: Dict[str, List[Callable]] = {
            "runner.registered":  [],
            "runner.deregistered":[],
            "runner.recovered":   [],
            "runner.unavailable": [],
        }

        self._running = False
        self._health_thread: Optional[threading.Thread] = None
        self.logger = logging.getLogger("RunnerRegistry")

    # ------------------------------------------------------------------ #
    # Lifecycle                                                            #
    # ------------------------------------------------------------------ #

    def start(self):
        if self._running:
            return
        self._running = True
        self._health_thread = threading.Thread(
            target=self._health_check_loop,
            name="RunnerRegistry-HealthCheck",
            daemon=True,
        )
        self._health_thread.start()
        self.logger.info("RunnerRegistry started")

    def stop(self):
        self._running = False
        if self._health_thread:
            self._health_thread.join(timeout=5.0)
        self.logger.info("RunnerRegistry stopped")

    # ------------------------------------------------------------------ #
    # Registration                                                         #
    # ------------------------------------------------------------------ #

    def register(
        self,
        runner_id:      str,
        api_url:        str,
        *,
        gpu:            bool       = False,
        max_concurrent: int        = 2,
        priority:       int        = 0,
        tags:           Optional[Set[str]] = None,
        probe:          bool       = True,     # Do an immediate health probe
    ) -> RunnerCapabilities:
        """
        Register a runner.  Safe to call multiple times (idempotent update).
        """
        with self._registry_lock:
            existing = self._runners.get(runner_id)
            caps = existing or RunnerCapabilities()

            caps.api_url        = api_url
            caps.gpu            = gpu
            caps.max_concurrent = max_concurrent
            caps.priority       = priority
            caps.tags           = tags or set()

            if runner_id not in self._runners:
                self._runners[runner_id] = caps
                self._locks[runner_id]   = threading.Lock()
                self.logger.info(
                    f"Runner registered: {runner_id!r} @ {api_url} "
                    f"(gpu={gpu}, max_concurrent={max_concurrent}, priority={priority})"
                )
                self._emit("runner.registered", runner_id, caps)
            else:
                self.logger.debug(f"Runner updated: {runner_id!r}")

        if probe:
            self._probe_runner(runner_id)

        return caps

    def deregister(self, runner_id: str, drain: bool = True):
        """
        Remove a runner.  If drain=True, marks it DRAINING first so
        in-flight tasks can complete before it disappears.
        """
        with self._registry_lock:
            if runner_id not in self._runners:
                return

            caps = self._runners[runner_id]

            if drain and caps.active_requests > 0:
                caps.status = RunnerStatus.DRAINING
                self.logger.info(
                    f"Runner {runner_id!r} draining "
                    f"({caps.active_requests} active requests)"
                )
                # Don't remove yet — the acquire loop will skip DRAINING runners
                return

            del self._runners[runner_id]
            del self._locks[runner_id]
            self.logger.info(f"Runner deregistered: {runner_id!r}")
            self._emit("runner.deregistered", runner_id, caps)

    # ------------------------------------------------------------------ #
    # Acquire / Release                                                    #
    # ------------------------------------------------------------------ #

    def acquire(
        self,
        model:              Optional[str]        = None,
        require_gpu:        bool                 = False,
        allowed_runners:    Optional[List[str]]  = None,
        excluded_runners:   Optional[Set[str]]   = None,
        strategy:           str                  = "least_loaded",  # or "priority", "round_robin"
        timeout:            float                = 30.0,
    ) -> Optional[tuple]:
        """
        Acquire a runner slot.

        Returns (runner_id, caps, release_fn) or None on timeout.
        The caller MUST call release_fn() when the request finishes.
        """
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            candidate = self._select(
                model=model,
                require_gpu=require_gpu,
                allowed_runners=allowed_runners,
                excluded_runners=excluded_runners or set(),
                strategy=strategy,
            )

            if candidate is None:
                time.sleep(0.1)
                continue

            runner_id, caps = candidate
            lock = self._locks[runner_id]

            with lock:
                # Re-check capacity under lock (another thread may have taken the slot)
                if not caps.has_capacity():
                    continue

                caps.active_requests += 1
                caps.total_requests  += 1
                caps.last_seen        = time.monotonic()

            self.logger.debug(
                f"Acquired {runner_id!r}: "
                f"{caps.active_requests}/{caps.max_concurrent} active"
            )

            def _release(rid=runner_id, c=caps, lk=lock, start=time.monotonic()):
                with lk:
                    c.active_requests = max(0, c.active_requests - 1)
                    c.total_duration += time.monotonic() - start
                self.logger.debug(
                    f"Released {rid!r}: "
                    f"{c.active_requests}/{c.max_concurrent} active"
                )

            return runner_id, caps, _release

        self.logger.warning(
            f"acquire() timed out after {timeout:.1f}s "
            f"(model={model!r}, gpu={require_gpu}, allowed={allowed_runners})"
        )
        return None

    # ------------------------------------------------------------------ #
    # Querying                                                             #
    # ------------------------------------------------------------------ #

    def get(self, runner_id: str) -> Optional[RunnerCapabilities]:
        return self._runners.get(runner_id)

    def list_runners(
        self,
        *,
        healthy_only:    bool = True,
        has_model:       Optional[str]  = None,
        require_gpu:     bool = False,
        tags:            Optional[Set[str]] = None,
    ) -> List[str]:
        """Return runner IDs matching the given filters."""
        with self._registry_lock:
            runners = list(self._runners.items())

        result = []
        for rid, caps in runners:
            if healthy_only and caps.status not in (
                RunnerStatus.HEALTHY, RunnerStatus.DEGRADED
            ):
                continue
            if has_model and not caps.has_model(has_model):
                continue
            if require_gpu and not caps.gpu:
                continue
            if tags and not tags.issubset(caps.tags):
                continue
            result.append(rid)

        return result

    def get_stats(self) -> Dict[str, Dict]:
        with self._registry_lock:
            return {
                rid: {
                    "api_url":        caps.api_url,
                    "gpu":            caps.gpu,
                    "priority":       caps.priority,
                    "status":         caps.status.name,
                    "active":         caps.active_requests,
                    "max_concurrent": caps.max_concurrent,
                    "load_factor":    round(caps.load_factor, 3),
                    "total_requests": caps.total_requests,
                    "total_failures": caps.total_failures,
                    "avg_duration":   round(caps.avg_duration, 3),
                    "loaded_models":  sorted(caps.loaded_models),
                    "tags":           sorted(caps.tags),
                }
                for rid, caps in self._runners.items()
            }

    # ------------------------------------------------------------------ #
    # Event subscriptions                                                  #
    # ------------------------------------------------------------------ #

    def on(self, event: str, callback: Callable):
        """Subscribe to registry events."""
        if event in self._callbacks:
            self._callbacks[event].append(callback)

    # ------------------------------------------------------------------ #
    # Internal — selection                                                 #
    # ------------------------------------------------------------------ #

    def _select(
        self,
        model:            Optional[str],
        require_gpu:      bool,
        allowed_runners:  Optional[List[str]],
        excluded_runners: Set[str],
        strategy:         str,
    ) -> Optional[tuple]:
        """
        Pick the best runner for the given constraints.
        Returns (runner_id, caps) or None.
        """
        with self._registry_lock:
            candidates = list(self._runners.items())

        # Filter
        eligible = []
        for rid, caps in candidates:
            if rid in excluded_runners:
                continue
            if allowed_runners is not None and rid not in allowed_runners:
                continue
            if caps.status not in (RunnerStatus.HEALTHY, RunnerStatus.DEGRADED):
                continue
            if not caps.has_capacity():
                continue
            if require_gpu and not caps.gpu:
                continue
            if model and not caps.has_model(model):
                continue
            eligible.append((rid, caps))

        if not eligible:
            return None

        if strategy == "least_loaded":
            return min(eligible, key=lambda x: (x[1].load_factor, -x[1].priority))

        if strategy == "priority":
            # Highest priority first; within same priority, least loaded
            return max(eligible, key=lambda x: (x[1].priority, -x[1].load_factor))

        if strategy == "round_robin":
            if not hasattr(self, "_rr_index"):
                self._rr_index = 0
            selected = eligible[self._rr_index % len(eligible)]
            self._rr_index += 1
            return selected

        # Default: least_loaded
        return min(eligible, key=lambda x: (x[1].load_factor, -x[1].priority))

    # ------------------------------------------------------------------ #
    # Internal — health checks                                             #
    # ------------------------------------------------------------------ #

    def _health_check_loop(self):
        while self._running:
            with self._registry_lock:
                runner_ids = list(self._runners.keys())

            for rid in runner_ids:
                if not self._running:
                    break
                self._probe_runner(rid)

            time.sleep(self.HEALTH_CHECK_INTERVAL)

    def _probe_runner(self, runner_id: str):
        """
        Probe a single runner:
          1. GET /api/tags  → derive loaded_models + health
          2. Update status, emit events on transitions
        """
        with self._registry_lock:
            if runner_id not in self._runners:
                return
            caps = self._runners[runner_id]
            api_url = caps.api_url

        prev_status = caps.status

        try:
            resp = requests.get(f"{api_url}/api/tags", timeout=5)
            resp.raise_for_status()
            data = resp.json()

            models: Set[str] = set()
            for m in data.get("models", []):
                name = m.get("name") or m.get("model", "")
                if name:
                    models.add(name)
                    # Also store without :latest for fuzzy matching
                    if name.endswith(":latest"):
                        models.add(name[:-7])

            caps.loaded_models = models
            caps.last_seen     = time.monotonic()

            # Determine health from load factor
            new_status = (
                RunnerStatus.DEGRADED
                if caps.load_factor >= 0.9
                else RunnerStatus.HEALTHY
            )

            if prev_status != new_status:
                caps.status = new_status
                if prev_status in (RunnerStatus.UNHEALTHY, RunnerStatus.OFFLINE):
                    self.logger.info(f"Runner {runner_id!r} recovered ({new_status.name})")
                    self._emit("runner.recovered", runner_id, caps)

        except Exception as exc:
            caps.status = RunnerStatus.UNHEALTHY
            caps.total_failures += 1

            if prev_status not in (RunnerStatus.UNHEALTHY, RunnerStatus.OFFLINE):
                self.logger.warning(f"Runner {runner_id!r} unavailable: {exc}")
                self._emit("runner.unavailable", runner_id, caps)

        # Handle stale runners that haven't been seen for a while
        if (
            caps.status == RunnerStatus.HEALTHY
            and time.monotonic() - caps.last_seen > self.STALE_THRESHOLD
        ):
            caps.status = RunnerStatus.DEGRADED

        # Clean up DRAINING runners with no active requests
        if caps.status == RunnerStatus.DRAINING and caps.active_requests == 0:
            with self._registry_lock:
                if runner_id in self._runners:
                    del self._runners[runner_id]
                    del self._locks[runner_id]
            self.logger.info(f"Runner {runner_id!r} drained and removed")
            self._emit("runner.deregistered", runner_id, caps)

    def _emit(self, event: str, runner_id: str, caps: RunnerCapabilities):
        """Fire local callbacks and publish to EventBus if available."""
        payload = {
            "runner_id": runner_id,
            "api_url":   caps.api_url,
            "gpu":       caps.gpu,
            "status":    caps.status.name,
            "models":    sorted(caps.loaded_models),
        }

        for cb in self._callbacks.get(event, []):
            try:
                cb(runner_id, caps)
            except Exception as e:
                self.logger.error(f"Callback error on {event}: {e}")

        if self._event_bus:
            try:
                self._event_bus.publish(event, payload)
            except Exception as e:
                self.logger.error(f"EventBus publish error ({event}): {e}")