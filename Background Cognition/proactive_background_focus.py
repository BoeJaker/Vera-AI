#!/usr/bin/env python3
""" 
A task scheduler and worker orchestrator with priorities, delays, retries,
rate limits, and resource-aware pausing. Designed to be embedded locally or
behind a remote HTTP executor. Built-in cluster support with label-based
routing to remote nodes. 

Features:
- Orchestration as a tool for LLM agents, bots, and autonomous systems.
- Push-based: no polling, no cron, no infinite loops
- Priorities: CRITICAL, HIGH, NORMAL, LOW
- Delays: schedule tasks for future execution
- Retries: configurable retry policies with exponential backoff and jitter
- Rate Limits: per-label rate limiting with token buckets
- Resource Awareness: pause when CPU or process count is high
- Cluster Support: route tasks to remote nodes, via http, based on labels
- Proactive Focus Manager: autonomous background cognition with LLMs
- Context Providers: plug in custom context sources
- Can be used standalone or as a python package

Proactive background focus manager for autonomous background cognition:
- Pulls fresh context via providers
- Generates the best next action via deep LLM
- Validates actionability with fast LLM
- Executes through toolchain and tracks results to a focus board


"""
# ──────────────────────────────────────────────────────────────────────────────
# Package: proactive_background_engine (streamlined, cluster-ready)
# Files in this single canvas:
#   - tasks.py
#   - worker_pool.py
#   - registry.py
#   - transport_http.py
#   - cluster.py
#   - context_providers.py
#   - proactive_focus.py
#   - README (usage)
#
# Copy/paste each section into separate .py files with the shown filenames.
# Everything is stdlib-only and typed. Swap HTTP with gRPC/NATS later if needed.
# ──────────────────────────────────────────────────────────────────────────────

# =============================== tasks.py =====================================
from __future__ import annotations
import enum
import random
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Tuple


class Priority(enum.IntEnum):
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


@dataclass(order=True)
class ScheduledTask:
    """PriorityQueue envelope.
    Sorted by (priority, scheduled_at, seq). Tasks carry labels & retry policy.
    """
    # sort keys
    priority: Priority
    scheduled_at: float
    seq: int

    # payload
    func: Callable[..., Any] = field(compare=False)
    args: Tuple[Any, ...] = field(default_factory=tuple, compare=False)
    kwargs: Dict[str, Any] = field(default_factory=dict, compare=False)

    # meta
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()), compare=False)
    name: str = field(default="task", compare=False)
    retries: int = field(default=0, compare=False)
    max_retries: int = field(default=2, compare=False)
    backoff_base: float = field(default=1.5, compare=False)
    backoff_cap: float = field(default=60.0, compare=False)
    jitter: float = field(default=0.2, compare=False)
    deadline_ts: Optional[float] = field(default=None, compare=False)
    labels: Tuple[str, ...] = field(default_factory=tuple, compare=False)
    context: Dict[str, Any] = field(default_factory=dict, compare=False)

    def next_retry_delay(self) -> float:
        exp = self.backoff_base ** max(0, self.retries)
        delay = min(self.backoff_cap, exp)
        if self.jitter:
            span = delay * self.jitter
            delay = delay + random.uniform(-span, span)
        return max(0.05, delay)

    def with_retry(self, now: Optional[float] = None) -> "ScheduledTask":
        now = now or time.time()
        return ScheduledTask(
            priority=self.priority,
            scheduled_at=now + self.next_retry_delay(),
            seq=self.seq + 100000,
            func=self.func,
            args=self.args,
            kwargs=self.kwargs,
            task_id=self.task_id,
            name=self.name,
            retries=self.retries + 1,
            max_retries=self.max_retries,
            backoff_base=self.backoff_base,
            backoff_cap=self.backoff_cap,
            jitter=self.jitter,
            deadline_ts=self.deadline_ts,
            labels=self.labels,
            context=self.context,
        )


class CancelToken:
    __slots__ = ("_cancelled",)
    def __init__(self) -> None:
        self._cancelled = False
    def cancel(self) -> None:
        self._cancelled = True
    @property
    def cancelled(self) -> bool:
        return self._cancelled


# ============================ worker_pool.py ==================================
# from __future__ import annotations
import queue
import threading
import time
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Tuple, Callable

try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover
    psutil = None

# from tasks import Priority, ScheduledTask


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


# ================================ registry.py ================================
# from __future__ import annotations
from typing import Any, Callable, Dict


class TaskRegistry:
    """Name → handler registry for serializable tasks.
    handler(payload, context) -> Any
    """
    def __init__(self) -> None:
        self._h: Dict[str, Callable[[Dict[str, Any], Dict[str, Any]], Any]] = {}

    def register(self, name: str):
        def deco(fn: Callable[[Dict[str, Any], Dict[str, Any]], Any]):
            self._h[name] = fn
            return fn
        return deco

    def run(self, name: str, payload: Dict[str, Any], context: Dict[str, Any]) -> Any:
        if name not in self._h:
            raise KeyError(f"No task handler registered for '{name}'")
        return self._h[name](payload, context)


GLOBAL_TASK_REGISTRY = TaskRegistry()


# ============================ transport_http.py ===============================
# from __future__ import annotations
import json
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Tuple

# from tasks import Priority
# from worker_pool import PriorityWorkerPool
# from registry import TaskRegistry


class HttpJsonClient:
    def __init__(self, base_url: str, timeout: float = 30.0, auth_token: str = "") -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.auth_token = auth_token

    def submit(self, task: Dict[str, Any]) -> Dict[str, Any]:
        data = json.dumps(task).encode("utf-8")
        req = urllib.request.Request(self.base_url + "/submit", data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        if self.auth_token:
            req.add_header("Authorization", f"Bearer {self.auth_token}")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # nosec B310
            return json.loads(resp.read().decode("utf-8"))

    def heartbeat(self) -> Dict[str, Any]:
        req = urllib.request.Request(self.base_url + "/heartbeat", method="GET")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # nosec B310
            return json.loads(resp.read().decode("utf-8"))


class RemoteExecutorHTTPServer(HTTPServer):
    def __init__(self, addr: Tuple[str, int], auth_token: str, pool: PriorityWorkerPool, registry: TaskRegistry):
        self.auth_token = auth_token
        self.pool = pool
        self.registry = registry
        super().__init__(addr, self._make_handler())

    def _make_handler(self):
        outer = self
        class Handler(BaseHTTPRequestHandler):
            def _auth(self) -> bool:
                if not outer.auth_token:
                    return True
                return self.headers.get("Authorization", "") == f"Bearer {outer.auth_token}"

            def do_GET(self):  # noqa: N802
                if self.path == "/heartbeat":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "ok"}).encode())
                else:
                    self.send_error(404)

            def do_POST(self):  # noqa: N802
                if self.path != "/submit":
                    self.send_error(404); return
                if not self._auth():
                    self.send_error(401); return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    raw = self.rfile.read(length)
                    task = json.loads(raw.decode("utf-8"))
                except Exception:
                    self.send_error(400); return

                name = task.get("name")
                payload = task.get("payload") or {}
                context = task.get("context") or {}
                priority = Priority(task.get("priority", int(Priority.NORMAL)))
                labels = tuple(task.get("labels") or ())

                outer.pool.submit(
                    lambda: outer.registry.run(name, payload, context),
                    priority=priority,
                    labels=labels,
                    name=f"remote:{name}",
                )
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"enqueued": True}).encode())

            def log_message(self, *args, **kwargs):
                return
        return Handler


def serve_http_executor(host: str, port: int, auth_token: str, pool: PriorityWorkerPool, registry: TaskRegistry) -> threading.Thread:
    server = RemoteExecutorHTTPServer((host, port), auth_token, pool, registry)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return t


# ================================ cluster.py =================================
# from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

# from tasks import Priority
# from worker_pool import PriorityWorkerPool


@dataclass
class RemoteNode:
    name: str
    base_url: str
    labels: Tuple[str, ...] = field(default_factory=tuple)
    auth_token: str = ""
    weight: int = 1
    last_ok: float = 0.0
    inflight: int = 0


class ClusterWorkerPool:
    """Route tasks to local pool or remote nodes using label-based capabilities."""
    def __init__(self, local_pool: PriorityWorkerPool) -> None:
        self.local = local_pool
        self.nodes: List[RemoteNode] = []

    def add_node(self, node: RemoteNode) -> None:
        self.nodes.append(node)

    def _pick_remote(self, labels: Iterable[str]) -> Optional[RemoteNode]:
        need = set(labels)
        cands = [n for n in self.nodes if set(n.labels) & need]
        if not cands:
            return None
        cands.sort(key=lambda n: (n.inflight, -n.weight, -n.last_ok))
        return cands[0]

    def submit_local(self, *args, **kwargs) -> str:
        return self.local.submit(*args, **kwargs)

    def submit_task(
        self,
        name: str,
        payload: Dict[str, Any],
        *,
        priority: Priority = Priority.NORMAL,
        labels: Iterable[str] = (),
        delay: float = 0.0,
        context: Optional[Dict[str, Any]] = None,
        router_hint: Optional[str] = None,
    ) -> str:
        labels = tuple(labels or ())
        node = None if router_hint == "local" else self._pick_remote(labels)
        if node is None:
            # run locally through registry
            # from registry import GLOBAL_TASK_REGISTRY as R
            return self.local.submit(lambda: R.run(name, payload, context or {}), priority=priority, delay=delay, labels=labels, name=name)

        # otherwise send remote
        # from transport_http import HttpJsonClient
        client = HttpJsonClient(node.base_url, auth_token=node.auth_token)
        try:
            node.inflight += 1
            client.submit({
                "name": name,
                "payload": payload,
                "context": context or {},
                "priority": int(priority),
                "labels": list(labels),
            })
            node.last_ok = time.time()
            return f"remote:{node.name}:{name}:{int(node.last_ok)}"
        finally:
            node.inflight = max(0, node.inflight - 1)


# =========================== context_providers.py =============================
# from __future__ import annotations
from typing import Any, Callable, Dict, Protocol


class ContextProvider(Protocol):
    name: str
    def collect(self) -> Dict[str, Any]: ...


class ConversationProvider:
    def __init__(self, get_latest: Callable[[], str]):
        self.name = "conversation"
        self._get_latest = get_latest
    def collect(self) -> Dict[str, Any]:
        return {"latest_conversation": self._get_latest()}


class FocusBoardProvider:
    def __init__(self, get_board: Callable[[], Dict[str, Any]]):
        self.name = "focus_board"
        self._get_board = get_board
    def collect(self) -> Dict[str, Any]:
        return {"focus_board": self._get_board()}


# =========================== proactive_focus.py ===============================
# from __future__ import annotations
import json
from typing import Any, Callable, Dict, List, Optional

# from tasks import Priority
# from worker_pool import PriorityWorkerPool
# from context_providers import ContextProvider, ConversationProvider, FocusBoardProvider


class ProactiveFocusManager:
    """Autonomous background cognition built on PriorityWorkerPool.

    - Pulls fresh context via providers
    - Generates the best next action via deep LLM
    - Validates actionability with fast LLM
    - Executes through your toolchain and logs results to a focus board
    """

    def __init__(
        self,
        agent,
        pool: PriorityWorkerPool,
        proactive_interval: float = 600.0,
        system_label_llm: str = "llm",
        system_label_exec: str = "exec",
        proactive_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.agent = agent
        self.pool = pool
        self.proactive_interval = proactive_interval
        self.system_label_llm = system_label_llm
        self.system_label_exec = system_label_exec
        self.proactive_callback = proactive_callback

        self.focus: Optional[str] = None
        self.focus_board: Dict[str, List[str]] = {
            "progress": [],
            "next_steps": [],
            "issues": [],
            "ideas": [],
            "actions": [],
        }

        self.latest_conversation: str = ""
        self._running = False
        self._ticker_task_id: Optional[str] = None

        self.context_providers: List[ContextProvider] = [
            ConversationProvider(lambda: self.latest_conversation),
            FocusBoardProvider(lambda: self.focus_board.copy()),
        ]

        # Conservative defaults; adjust upstream if desired
        self.pool.set_concurrency_limit(self.system_label_llm, 2)
        self.pool.set_concurrency_limit(self.system_label_exec, 1)

    # Focus & state
    def set_focus(self, focus: str) -> None:
        self.focus = focus
        try:
            self.agent.mem.add_session_memory(self.agent.sess.id, f"[FocusManager] Focus set to: {focus}", "Thought", {"topic": "focus"})
        except Exception:
            pass

    def clear_focus(self) -> None:
        self.focus = None
        self.stop()

    def add_provider(self, provider: ContextProvider) -> None:
        self.context_providers.append(provider)

    def update_latest_conversation(self, text: str) -> None:
        self.latest_conversation = text

    def add_to_focus_board(self, category: str, note: str) -> None:
        self.focus_board.setdefault(category, []).append(note)

    # lifecycle
    def start(self) -> None:
        if self._running or not self.focus:
            return
        self._running = True
        self._schedule_tick(0.0)

    def stop(self) -> None:
        self._running = False

    def _schedule_tick(self, delay: float) -> None:
        if not self._running:
            return
        self._ticker_task_id = self.pool.submit(
            self._tick,
            priority=Priority.LOW,
            delay=delay,
            name="proactive.tick",
            labels=(self.system_label_llm,),
        )

    # tick → generate → evaluate → execute
    def _collect_context(self) -> Dict[str, Any]:
        ctx: Dict[str, Any] = {"focus": self.focus}
        for p in self.context_providers:
            try:
                ctx.update(p.collect())
            except Exception as e:
                self.add_to_focus_board("issues", f"Context provider {getattr(p,'name','?')} failed: {e}")
        return ctx

    def _tick(self) -> None:
        ctx = self._collect_context()
        self.pool.submit(self._generate_and_route, ctx, priority=Priority.NORMAL, name="proactive.generate_and_route", labels=(self.system_label_llm,))
        self._schedule_tick(self.proactive_interval)

    def _generate_and_route(self, ctx: Dict[str, Any]) -> None:
        if not self.focus:
            return
        thought = self._generate_proactive_thought(ctx)
        if not thought:
            return
        if self.proactive_callback:
            try:
                self.proactive_callback(thought)
            except Exception:
                pass
        self.add_to_focus_board("actions", thought)

        if self._is_actionable(thought):
            self.pool.submit(self._execute_goal, thought, priority=Priority.HIGH, name="proactive.execute_goal", labels=(self.system_label_exec,))
        else:
            self.add_to_focus_board("issues", f"Thought not actionable: {thought[:160]}")

    def _generate_proactive_thought(self, ctx: Dict[str, Any]) -> Optional[str]:
        prompt = (
            "You are an autonomous background co-pilot for the project."
            f"Project Focus: {ctx.get('focus')}"
            f"Recent conversation/context:{ctx.get('latest_conversation','')}"
            f"Focus board (JSON):{json.dumps(ctx.get('focus_board',{}), ensure_ascii=False)}"
            "Return ONE best immediate, concrete action (single sentence)."
            " Prefer steps that unblock progress, reduce risk, or increase clarity."
            " The result must be directly actionable with available tools."
        )
        try:
            txt = self.agent.deep_llm.predict(prompt)
            return (txt or "").strip()
        except Exception as e:
            self.add_to_focus_board("issues", f"LLM generate failed: {e}")
            return None

    def _is_actionable(self, thought: str) -> bool:
        tools = [getattr(t, "name", str(t)) for t in getattr(self.agent, "tools", [])]
        eval_prompt = (
            "Evaluate if the proposal is executable given the tool list."
            f"Tools: {tools}"            
            f"Focus: {self.focus}"
            f"Proposal: {thought}"
            "Respond exactly with YES or NO."
        )
        try:
            verdict = self.agent.fast_llm.invoke(eval_prompt)
            return str(verdict).strip().upper().startswith("YES")
        except Exception as e:
            self.add_to_focus_board("issues", f"LLM evaluate failed: {e}")
            return False

    def _execute_goal(self, goal: str) -> None:
        try:
            payload = f"Goal: {goal} Focus: {self.focus} Status: {json.dumps(self.focus_board, ensure_ascii=False)}"
            result_str = ""
            for chunk in self.agent.toolchain.execute_tool_chain(payload):
                result_str += str(chunk)
            if result_str:
                self.add_to_focus_board("progress", f"Executed goal: {goal}")
                self.add_to_focus_board("progress", f"Result: {result_str[:4000]}")
        except Exception as e:
            self.add_to_focus_board("issues", f"Execution failed for '{goal}': {e}")

    def relate_to_focus(self, user_input: str, response: str) -> str:
        if not self.focus:
            return response
        return f"{response} [Reminder: Current project focus is '{self.focus}']"

# ======================== proxmox_worker_manager.py ==========================
# from __future__ import annotations
import threading
import time
from typing import Any, Dict, List, Optional, Tuple, Callable
import paramiko  # for SSH, install with `pip install paramiko`
import requests  # for Proxmox API, install with `pip install requests`
# from worker_pool import PriorityWorkerPool
# from tasks import Priority, ScheduledTask
# from cluster import RemoteNode


class ProxmoxWorkerManager:
    """
    Manage worker VMs or CTs on Proxmox hosts and expose them as cluster nodes.
    Supports:
    - autoscaling
    - teardown
    - SSH/API execution
    """

    def __init__(
        self,
        host: str,
        user: str,
        password: Optional[str] = None,
        token_name: Optional[str] = None,
        token_value: Optional[str] = None,
        verify_ssl: bool = True,
        default_worker_count: int = 1,
        worker_name_prefix: str = "worker",
    ):
        self.host = host
        self.user = user
        self.password = password
        self.token_name = token_name
        self.token_value = token_value
        self.verify_ssl = verify_ssl
        self.worker_name_prefix = worker_name_prefix
        self.default_worker_count = default_worker_count
        self.workers: Dict[str, Dict[str, Any]] = {}  # name -> metadata
        self.lock = threading.Lock()
        self._client_session: Optional[requests.Session] = None
        self._setup_session()

    def _setup_session(self):
        s = requests.Session()
        if self.token_name and self.token_value:
            s.headers.update({"Authorization": f"PVEAPIToken={self.user}!{self.token_name}={self.token_value}"})
        elif self.password:
            s.auth = (self.user, self.password)
        self._client_session = s

    def _proxmox_api(self, path: str, method: str = "GET", data: Optional[dict] = None):
        url = f"https://{self.host}:8006/api2/json/{path.lstrip('/')}"
        s = self._client_session or requests.Session()
        r = s.request(method, url, json=data, verify=self.verify_ssl, timeout=10)
        r.raise_for_status()
        return r.json()["data"]

    def list_workers(self) -> Dict[str, Dict[str, Any]]:
        """Return current worker VMs/CTs metadata"""
        with self.lock:
            return self.workers.copy()

    def provision_worker(self, vmid: int, node_name: str, labels: Tuple[str, ...] = ("exec",)) -> str:
        """Provision a worker VM/CT (simplified, assumes VM exists and is started)."""
        name = f"{self.worker_name_prefix}-{vmid}"
        self._proxmox_api(f"nodes/{node_name}/qemu/{vmid}/status/start", method="POST")
        with self.lock:
            self.workers[name] = {"vmid": vmid, "node_name": node_name, "labels": labels, "host_ip": self._get_guest_ip(vmid, node_name)}
        return name

    def teardown_worker(self, name: str) -> None:
        with self.lock:
            if name not in self.workers:
                return
            meta = self.workers.pop(name)
        vmid = meta["vmid"]
        node_name = meta["node_name"]
        self._proxmox_api(f"nodes/{node_name}/qemu/{vmid}/status/stop", method="POST")

    def _get_guest_ip(self, vmid: int, node_name: str) -> str:
        """Retrieve IP of the VM/CT; simplified example, assumes DHCP + guest-agent installed"""
        try:
            data = self._proxmox_api(f"nodes/{node_name}/qemu/{vmid}/agent/network-get-interfaces")
            for iface in data.get("result", []):
                for addr in iface.get("ip-addresses", []):
                    ip = addr.get("ip-address")
                    if ip and "." in ip:
                        return ip
        except Exception:
            pass
        return "127.0.0.1"

    def execute_via_ssh(self, worker_name: str, command: str) -> str:
        """Execute arbitrary command via SSH"""
        meta = self.workers.get(worker_name)
        if not meta:
            raise ValueError(f"No such worker {worker_name}")
        ip = meta["host_ip"]
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username=self.user, password=self.password, timeout=5)
        stdin, stdout, stderr = ssh.exec_command(command)
        out = stdout.read().decode()
        ssh.close()
        return out

    def scale_up(self, count: int) -> None:
        """Provision new workers"""
        for _ in range(count):
            vmid = 1000 + len(self.workers)
            node_name = "pve"  # adjust accordingly
            self.provision_worker(vmid, node_name)

    def scale_down(self, count: int) -> None:
        """Teardown workers"""
        names = list(self.workers.keys())[:count]
        for name in names:
            self.teardown_worker(name)


# ======================== Cluster integration example ========================
class ProxmoxRemoteNode:
    """Wrap a Proxmox worker as a ClusterWorkerPool node."""
    def __init__(self, manager: ProxmoxWorkerManager, worker_name: str, labels: Tuple[str, ...] = ("exec",)):
        self.manager = manager
        self.worker_name = worker_name
        self.labels = labels

    def submit_task(self, name: str, payload: dict, context: dict, priority: Priority):
        """Return a callable to submit task through the remote worker"""
        def task():
            # send through HTTP on the worker itself or SSH-run HTTP executor
            ip = self.manager.list_workers()[self.worker_name]["host_ip"]
            # from transport_http import HttpJsonClient
            client = HttpJsonClient(f"http://{ip}:8080", auth_token="secret")
            client.submit({"name": name, "payload": payload, "context": context, "priority": int(priority), "labels": list(self.labels)})
        return task


# ======================== LangChain tool integration =========================
from langchain.tools import BaseTool

class ProxmoxWorkerTool(BaseTool):
    name: str = "proxmox_worker"  # Add type annotation
    description: str = "Submit a task to a worker running on a Proxmox host." 

    def __init__(self, cluster_pool: "ClusterWorkerPool"):
        self.cluster_pool = cluster_pool

    def _run(self, task_name: str, payload: dict, labels: Tuple[str, ...] = ("exec",), priority: int = Priority.NORMAL) -> str:
        """Execute via the cluster pool"""
        return self.cluster_pool.submit_task(task_name, payload, labels=labels, priority=Priority(priority))

    async def _arun(self, *args, **kwargs) -> str:
        # LangChain async interface
        return self._run(*args, **kwargs)
    
# ======================== proxmox_autoscale_cluster.py ======================
# from __future__ import annotations
import threading
import time
from typing import Any, Dict, Iterable, Optional, Tuple
# from worker_pool import PriorityWorkerPool
# from cluster import ClusterWorkerPool, RemoteNode
# from proxmox_worker_manager import ProxmoxWorkerManager, ProxmoxRemoteNode
# from tasks import Priority


class ProxmoxAutoClusterPool:
    """
    Cluster pool that automatically scales Proxmox workers based on load.
    Integrates:
    - Local pool
    - Remote non-Proxmox nodes
    - Proxmox worker nodes via API/SSH
    """

    def __init__(
        self,
        local_pool: PriorityWorkerPool,
        proxmox_manager: ProxmoxWorkerManager,
        max_workers: int = 8,
        min_workers: int = 1,
        check_interval: float = 10.0,
        scale_up_threshold: int = 4,
        scale_down_threshold: int = 1,
        node_labels: Tuple[str, ...] = ("exec",),
    ):
        self.local_pool = local_pool
        self.proxmox_manager = proxmox_manager
        self.cluster_pool = ClusterWorkerPool(local_pool)
        self.max_workers = max_workers
        self.min_workers = min_workers
        self.check_interval = check_interval
        self.scale_up_threshold = scale_up_threshold
        self.scale_down_threshold = scale_down_threshold
        self.node_labels = node_labels

        self._stop_event = threading.Event()
        self._autoscale_thread = threading.Thread(target=self._autoscale_loop, daemon=True)
        self._lock = threading.Lock()

        # track proxmox nodes inside cluster
        self._prox_nodes: Dict[str, ProxmoxRemoteNode] = {}

    def add_remote_node(self, node: RemoteNode):
        self.cluster_pool.add_node(node)

    def start_autoscaler(self):
        self._stop_event.clear()
        self._autoscale_thread.start()

    def stop_autoscaler(self):
        self._stop_event.set()
        self._autoscale_thread.join(timeout=5)

    def submit_task(
        self,
        name: str,
        payload: Dict[str, Any],
        *,
        priority: Priority = Priority.NORMAL,
        labels: Iterable[str] = (),
        delay: float = 0.0,
        context: Optional[Dict[str, Any]] = None,
        router_hint: Optional[str] = None,
    ) -> str:
        return self.cluster_pool.submit_task(
            name,
            payload,
            priority=priority,
            labels=labels,
            delay=delay,
            context=context,
            router_hint=router_hint,
        )

    # ----------------- autoscaling logic -----------------
    def _autoscale_loop(self):
        while not self._stop_event.is_set():
            queue_size = self.local_pool._q.qsize()
            current_workers = len(self.proxmox_manager.list_workers())

            # scale up if queue is long and under max_workers
            if queue_size >= self.scale_up_threshold and current_workers < self.max_workers:
                to_add = min(queue_size, self.max_workers - current_workers)
                self._scale_up_proxmox(to_add)

            # scale down if queue is small and above min_workers
            if queue_size <= self.scale_down_threshold and current_workers > self.min_workers:
                to_remove = current_workers - self.min_workers
                self._scale_down_proxmox(to_remove)

            time.sleep(self.check_interval)

    def _scale_up_proxmox(self, count: int):
        for _ in range(count):
            vmid = 1000 + len(self._prox_nodes)
            node_name = "pve"  # adjust per your Proxmox cluster
            worker_name = self.proxmox_manager.provision_worker(vmid, node_name, labels=self.node_labels)
            prox_node = ProxmoxRemoteNode(self.proxmox_manager, worker_name, labels=self.node_labels)
            with self._lock:
                self._prox_nodes[worker_name] = prox_node
            # add to cluster routing
            self.cluster_pool.add_node(RemoteNode(
                name=worker_name,
                base_url=f"http://{self.proxmox_manager.list_workers()[worker_name]['host_ip']}:8080",
                labels=self.node_labels,
                auth_token="secret",
                weight=1
            ))

    def _scale_down_proxmox(self, count: int):
        with self._lock:
            to_remove = list(self._prox_nodes.keys())[:count]
        for worker_name in to_remove:
            self.proxmox_manager.teardown_worker(worker_name)
            with self._lock:
                self._prox_nodes.pop(worker_name, None)
            # remove from cluster nodes
            self.cluster_pool.nodes = [n for n in self.cluster_pool.nodes if n.name != worker_name]


# ================================= README ====================================
"""
USAGE SNAPSHOT
--------------
from worker_pool import PriorityWorkerPool
from cluster import ClusterWorkerPool, RemoteNode
from tasks import Priority
from registry import GLOBAL_TASK_REGISTRY as R
from proactive_focus import ProactiveFocusManager
from transport_http import serve_http_executor

# Local pool on the main machine
local_pool = PriorityWorkerPool(
    worker_count=8,
    cpu_threshold=90.0,
    max_process_name="ollama",
    max_processes=24,
    rate_limits={"llm": (0.5, 2), "exec": (5, 10)},
    name="MainPool",
)
local_pool.set_concurrency_limit("llm", 2)
local_pool.set_concurrency_limit("exec", 2)
local_pool.start()

# Remote executors (run these on other boxes)
light_pool = PriorityWorkerPool(worker_count=4, name="LightLLM"); light_pool.start()
serve_http_executor("0.0.0.0", 8081, auth_token="secretA", pool=light_pool, registry=R)

heavy_pool = PriorityWorkerPool(worker_count=6, name="Heavy"); heavy_pool.start()
serve_http_executor("0.0.0.0", 8082, auth_token="secretB", pool=heavy_pool, registry=R)

# Cluster routing on main box
cluster = ClusterWorkerPool(local_pool)
cluster.add_node(RemoteNode(name="light", base_url="http://light-host:8081", labels=("llm_light","llm"), auth_token="secretA", weight=2))
cluster.add_node(RemoteNode(name="heavy", base_url="http://heavy-host:8082", labels=("llm_heavy","exec"), auth_token="secretB", weight=1))

# Register tasks once (works locally & remotely)
@R.register("llm.generate")
def task_llm_generate(payload, context):
    prompt = payload["prompt"]
    model = context.get("model", "default")
    return my_llm_client.generate(prompt, model=model)

@R.register("tools.run_toolchain")
def task_run_toolchain(payload, context):
    plan = payload["plan"]
    return agent.toolchain.execute_tool_chain(plan)

# Submit work via cluster
cluster.submit_task("llm.generate", {"prompt": "Quick summary of issue #123"}, labels=("llm_light",), priority=Priority.HIGH)
cluster.submit_task("llm.generate", {"prompt": "Deep RAG"}, labels=("llm_heavy",), priority=Priority.NORMAL)

# Proactive manager (can use local or cluster.local pool)
pfm = ProactiveFocusManager(agent=my_agent, pool=local_pool, proactive_interval=300)
pfm.set_focus("Improve developer onboarding docs")
pfm.start()

NOTES
-----
- All tasks are (name, payload, context) and executed via the global registry → easy to route over the network.
- Transport is HTTP+JSON with bearer token. Swap to gRPC/NATS/ZeroMQ by providing another client/server with the same interface.
- PriorityWorkerPool handles CPU/process pressure and per-label concurrency so heavy jobs never starve latency-sensitive ones.
"""
