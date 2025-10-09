#!/usr/bin/env python3
"""
Priority worker pool with rate limiting, resource awareness, and retry logic
"""

from __future__ import annotations
import queue
import threading
import time
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Tuple, Callable

try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover
    psutil = None

from tasks import Priority, ScheduledTask


class TokenBucket:
    """Minimal token bucket for per-label rate limiting."""
    def __init__(self, fill_rate: float, capacity: float) -> None:
        self.fill_rate = float(fill_rate)
        self.capacity = float(capacity)
        self.tokens = float(capacity)
        self.ts = time.time()
        self._lock = threading.Lock()

    def allow(self, cost: float = 1.0) -> bool:
        with self._lock:
            now = time.time()
            elapsed = now - self.ts
            self.ts = now
            self.tokens = min(self.capacity, self.tokens + elapsed * self.fill_rate)
            if self.tokens >= cost:
                self.tokens -= cost
                return True
            return False


class PriorityWorkerPool:
    """Threaded worker pool with priorities, delays, retries, rate limits, and
    resource-aware pausing. Designed to be embedded locally or behind a remote
    HTTP executor.
    """
    def __init__(
        self,
        worker_count: int = 4,
        *,
        cpu_threshold: float = 85.0,
        max_process_name: Optional[str] = None,
        max_processes: Optional[int] = None,
        rate_limits: Optional[Dict[str, Tuple[float, float]]] = None,  # label -> (fill, cap)
        on_task_start: Optional[Callable[[ScheduledTask], None]] = None,
        on_task_end: Optional[Callable[[ScheduledTask, Optional[Any], Optional[BaseException]], None]] = None,
        name: str = "WorkerPool",
    ) -> None:
        self.name = name
        self.worker_count = int(worker_count)
        self._q: "queue.PriorityQueue[ScheduledTask]" = queue.PriorityQueue()
        self._seq = 0
        self._lock = threading.RLock()
        self._running = False
        self._stop_evt = threading.Event()
        self._pause_evt = threading.Event(); self._pause_evt.set()
        self._threads: List[threading.Thread] = []

        self.cpu_threshold = cpu_threshold
        self.max_process_name = (max_process_name or "").lower() if max_process_name else None
        self.max_processes = max_processes

        self.on_task_start = on_task_start
        self.on_task_end = on_task_end

        self.rate_buckets: Dict[str, TokenBucket] = {}
        if rate_limits:
            for label, (fill, cap) in rate_limits.items():
                self.rate_buckets[label] = TokenBucket(fill, cap)

        self.max_inflight_per_label: Dict[str, int] = defaultdict(lambda: 1_000_000)
        self.inflight_per_label: Dict[str, int] = defaultdict(int)

    # lifecycle
    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._stop_evt.clear()
        for i in range(self.worker_count):
            t = threading.Thread(target=self._loop, name=f"{self.name}-{i}", daemon=True)
            t.start(); self._threads.append(t)

    def stop(self, wait: bool = True, drain: bool = False) -> None:
        if not self._running:
            return
        self._running = False
        self._stop_evt.set()
        if not drain:
            for _ in self._threads:
                self._q.put(ScheduledTask(priority=Priority.CRITICAL, scheduled_at=0.0, seq=self._next_seq(), func=lambda: None, name="__STOP__"))
        if wait:
            for t in self._threads:
                t.join(timeout=5)
        self._threads.clear()

    def pause(self) -> None:
        self._pause_evt.clear()
    def resume(self) -> None:
        self._pause_evt.set()

    # submission
    def _next_seq(self) -> int:
        with self._lock:
            self._seq += 1
            return self._seq

    def submit(
        self,
        func: Callable[..., Any],
        *args: Any,
        priority: Priority = Priority.NORMAL,
        delay: float = 0.0,
        name: str = "task",
        labels: Optional[Iterable[str]] = None,
        deadline_ts: Optional[float] = None,
        max_retries: int = 2,
        backoff_base: float = 1.5,
        backoff_cap: float = 60.0,
        jitter: float = 0.2,
        context: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> str:
        st = ScheduledTask(
            priority=priority,
            scheduled_at=time.time() + max(0.0, delay),
            seq=self._next_seq(),
            func=func,
            args=args,
            kwargs=kwargs,
            name=name,
            labels=tuple(labels or ()),
            deadline_ts=deadline_ts,
            max_retries=max_retries,
            backoff_base=backoff_base,
            backoff_cap=backoff_cap,
            jitter=jitter,
            context=context or {},
        )
        self._q.put(st)
        return st.task_id

    # limits
    def set_concurrency_limit(self, label: str, max_inflight: int) -> None:
        self.max_inflight_per_label[label] = max(1, int(max_inflight))

    def _labels_ok(self, labels: Iterable[str]) -> bool:
        for l in labels:
            if self.inflight_per_label[l] >= self.max_inflight_per_label[l]:
                return False
        return True

    def _labels_start(self, labels: Iterable[str]) -> None:
        for l in labels:
            self.inflight_per_label[l] += 1
    def _labels_done(self, labels: Iterable[str]) -> None:
        for l in labels:
            self.inflight_per_label[l] = max(0, self.inflight_per_label[l] - 1)

    def _resource_hot(self) -> bool:
        # CPU guard
        if psutil and self.cpu_threshold is not None:
            try:
                if psutil.cpu_percent(interval=0.05) >= self.cpu_threshold:
                    return True
            except Exception:
                pass
        # process-count guard
        if psutil and self.max_process_name and self.max_processes is not None:
            try:
                cnt = 0
                for p in psutil.process_iter(attrs=["name"]):
                    if (p.info.get("name") or "").lower().find(self.max_process_name) >= 0:
                        cnt += 1
                        if cnt >= self.max_processes:
                            return True
            except Exception:
                pass
        return False

    def _rate_ok(self, labels: Iterable[str]) -> bool:
        if not self.rate_buckets:
            return True
        for l in labels or ("__default__",):
            b = self.rate_buckets.get(l)
            if b and not b.allow(1.0):
                return False
        return True

    # worker loop
    def _loop(self) -> None:
        while not self._stop_evt.is_set():
            try:
                st: ScheduledTask = self._q.get(timeout=0.25)
            except queue.Empty:
                continue

            if st.name == "__STOP__":
                self._q.task_done(); break

            now = time.time()
            if st.scheduled_at > now:
                self._q.put(st)
                self._q.task_done()
                time.sleep(min(0.1, st.scheduled_at - now))
                continue

            if not self._pause_evt.is_set() or self._resource_hot() or not self._rate_ok(st.labels) or not self._labels_ok(st.labels):
                st.scheduled_at = now + 0.2
                self._q.put(st)
                self._q.task_done()
                continue

            if st.deadline_ts and now > st.deadline_ts:
                if self.on_task_end:
                    self.on_task_end(st, None, TimeoutError("deadline exceeded"))
                self._q.task_done()
                continue

            try:
                self._labels_start(st.labels)
                if self.on_task_start: self.on_task_start(st)
                result = st.func(*st.args, **st.kwargs)
                if self.on_task_end: self.on_task_end(st, result, None)
            except Exception as e:  # noqa: BLE001
                if st.retries < st.max_retries:
                    self._q.put(st.with_retry())
                else:
                    if self.on_task_end: self.on_task_end(st, None, e)
            finally:
                self._labels_done(st.labels)
                self._q.task_done()