#!/usr/bin/env python3
"""
Cluster management for distributed task execution across remote nodes
"""

from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

from tasks import Priority
from worker_pool import PriorityWorkerPool


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
            from registry import GLOBAL_TASK_REGISTRY as R
            return self.local.submit(lambda: R.run(name, payload, context or {}), priority=priority, delay=delay, labels=labels, name=name)

        # otherwise send remote
        from transport_http import HttpJsonClient
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