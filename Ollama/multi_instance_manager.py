#!/usr/bin/env python3
# Vera/Ollama/multi_instance_manager.py

"""
Multi-Instance Ollama Manager with Load Balancing
Distributes requests across multiple Ollama instances
"""

import threading
import time
import queue
import requests
import json
from typing import List, Dict, Any, Optional, Iterator
from dataclasses import dataclass, field
from collections import defaultdict

# LangChain imports for proper LLM compatibility
from langchain.llms.base import LLM
from langchain_core.outputs import GenerationChunk
from pydantic import Field

try:
    from Vera.Logging.logging import LogContext
    from Vera.Configuration.config_manager import OllamaConfig, OllamaInstanceConfig
except ImportError:
    from Logging.logging import LogContext
    from Configuration.config_manager import OllamaConfig, OllamaInstanceConfig

from Vera.Ollama.manager import ThoughtCapture  # Reuse the existing implementation


# ── Logging helpers ────────────────────────────────────────────────────────────

def _cluster_snapshot(instances: dict, stats: dict) -> str:
    """
    Build a compact one-line cluster state string showing every instance.
    Format: [name=active/max(load%) H/U, ...]
    """
    parts = []
    for name in sorted(instances):
        s = stats[name]
        inst = instances[name]
        load_pct = int((s.active_requests / max(inst.max_concurrent, 1)) * 100)
        health = "✓" if s.is_healthy else "✗"
        parts.append(
            f"{health}{name}={s.active_requests}/{inst.max_concurrent}({load_pct}%)"
        )
    return "[" + "  ".join(parts) + "]"


def _instance_summary(name: str, instances: dict, stats: dict) -> str:
    """Single-instance compact summary: name=active/max(load%) pri=N"""
    s = stats[name]
    inst = instances[name]
    load_pct = int((s.active_requests / max(inst.max_concurrent, 1)) * 100)
    return (
        f"'{name}' {s.active_requests}/{inst.max_concurrent} "
        f"({load_pct}% load, pri={inst.priority})"
    )


# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class InstanceStats:
    """Statistics for an Ollama instance"""
    name: str
    active_requests: int = 0
    total_requests: int = 0
    total_failures: int = 0
    total_duration: float = 0.0
    last_request_time: float = 0.0
    is_healthy: bool = True
    last_health_check: float = 0.0


class OllamaInstancePool:
    """
    Manages multiple Ollama instances with load balancing.

    Key fix: selection + acquisition are now atomic under a single global lock,
    eliminating the TOCTOU race where two concurrent callers both read load=0
    on the same instance and both acquire it simultaneously.
    """

    def __init__(self, config, logger=None):
        self.config = config
        self.logger = logger

        self.instances: Dict[str, Any] = {}
        self.stats: Dict[str, Any] = {}

        # ── Single global lock covers both selection AND acquisition ──────────
        self._global_lock = threading.Lock()

        # Round-robin state — protected by _global_lock
        self._round_robin_index: int = 0

        self.request_queue = queue.Queue(maxsize=config.max_queue_size)
        self.queue_enabled = config.enable_request_queue

        self.health_check_interval = 30.0
        self.health_check_thread: Optional[threading.Thread] = None
        self.running = False

        self._initialize_instances()
        self.start()

        if self.logger:
            self.logger.success(
                f"Initialized {len(self.instances)} Ollama instances "
                f"[strategy={self.config.load_balance_strategy}]"
            )

    def _initialize_instances(self):
        for instance_config in self.config.instances:
            if isinstance(instance_config, dict):
                from Vera.Configuration.config_manager import OllamaInstanceConfig
                instance_config = OllamaInstanceConfig.from_dict(instance_config)
            if not instance_config.enabled:
                continue
            self.instances[instance_config.name] = instance_config
            self.stats[instance_config.name] = InstanceStats(name=instance_config.name)
            if self.logger:
                self.logger.debug(
                    f"  Registered instance: '{instance_config.name}' "
                    f"@ {instance_config.api_url} "
                    f"(priority={instance_config.priority}, "
                    f"max_concurrent={instance_config.max_concurrent})"
                )

    def start(self):
        if self.running:
            return
        self.running = True
        self.health_check_thread = threading.Thread(
            target=self._health_check_loop, daemon=True
        )
        self.health_check_thread.start()
        if self.logger:
            self.logger.debug("Health monitoring started")

    def stop(self):
        self.running = False
        if self.health_check_thread:
            self.health_check_thread.join(timeout=5.0)

    # ── Health monitoring ─────────────────────────────────────────────────────

    def _health_check_loop(self):
        while self.running:
            for name in list(self.instances.keys()):
                self._check_instance_health(name)
            time.sleep(self.health_check_interval)

    def _check_instance_health(self, name: str):
        instance = self.instances[name]
        stats    = self.stats[name]
        try:
            response = requests.get(f"{instance.api_url}/api/tags", timeout=5)
            was_unhealthy   = not stats.is_healthy
            stats.is_healthy = response.status_code == 200
            stats.last_health_check = time.time()
            if was_unhealthy and stats.is_healthy and self.logger:
                self.logger.success(
                    f"[health] Instance '{name}' recovered  "
                    f"cluster: {_cluster_snapshot(self.instances, self.stats)}"
                )
        except Exception as e:
            was_healthy      = stats.is_healthy
            stats.is_healthy = False
            stats.last_health_check = time.time()
            if was_healthy and self.logger:
                self.logger.warning(
                    f"[health] Instance '{name}' went UNHEALTHY: {e}  "
                    f"cluster: {_cluster_snapshot(self.instances, self.stats)}"
                )

    # ── Instance selection (MUST be called while holding _global_lock) ────────

    def _select_instance(self, candidates: List[str]) -> str:
        """
        Choose the best candidate according to load_balance_strategy.
        Logs the scoring/selection rationale at DEBUG level.
        """
        strategy = self.config.load_balance_strategy

        if strategy == "round_robin":
            selected = candidates[self._round_robin_index % len(candidates)]
            if self.logger:
                self.logger.debug(
                    f"[select/round_robin] index={self._round_robin_index} "
                    f"candidates={candidates} → '{selected}'"
                )
            self._round_robin_index += 1
            return selected

        elif strategy == "least_loaded":
            def load_score(name: str):
                inst  = self.instances[name]
                s     = self.stats[name]
                load  = s.active_requests / max(inst.max_concurrent, 1)
                return (load, -inst.priority)

            scores = {n: load_score(n) for n in candidates}
            selected = min(candidates, key=load_score)

            if self.logger:
                score_str = "  ".join(
                    f"'{n}' load={scores[n][0]:.2f} pri={self.instances[n].priority}"
                    for n in candidates
                )
                self.logger.debug(
                    f"[select/least_loaded] scores: [{score_str}] → '{selected}'"
                )
            return selected

        elif strategy == "priority":
            with_capacity = [
                n for n in candidates
                if self.stats[n].active_requests < self.instances[n].max_concurrent
            ]
            pool = with_capacity if with_capacity else candidates
            selected = max(pool, key=lambda n: self.instances[n].priority)

            if self.logger:
                at_cap = [n for n in candidates if n not in with_capacity]
                self.logger.debug(
                    f"[select/priority] candidates={candidates}  "
                    f"at_capacity={at_cap}  pool={pool} → '{selected}'"
                )
            return selected

        else:
            selected = candidates[0]
            if self.logger:
                self.logger.debug(
                    f"[select/first] candidates={candidates} → '{selected}'"
                )
            return selected

    # ── Atomic acquire ────────────────────────────────────────────────────────

    def acquire_instance(
        self,
        timeout: float = 30.0,
        allowed_instances: Optional[List[str]] = None,
        caller_hint: str = "",
    ) -> Optional[tuple]:
        """
        Atomically select and acquire an instance.

        Selection and active_requests increment happen inside the same lock,
        preventing two concurrent callers from both reading load=0 on the same
        instance before either has incremented the counter.

        Args:
            timeout:           Seconds to wait for a free slot.
            allowed_instances: Whitelist of instance names (None = all healthy).
            caller_hint:       Label for log messages (e.g. "triage", "preamble").

        Returns:
            (instance_name, instance_config, release_fn)  or  None on timeout.
        """
        start_time    = time.time()
        hint          = f"[{caller_hint}] " if caller_hint else ""
        waited_logged = False
        poll_count    = 0

        if self.logger:
            filter_note = f" restrict={allowed_instances}" if allowed_instances else " restrict=none"
            self.logger.debug(
                f"{hint}acquire_instance  timeout={timeout:.1f}s{filter_note}  "
                f"strategy={self.config.load_balance_strategy}  "
                f"cluster: {_cluster_snapshot(self.instances, self.stats)}"
            )

        while time.time() - start_time < timeout:
            poll_count += 1
            elapsed = time.time() - start_time

            with self._global_lock:
                healthy = [
                    name for name, s in self.stats.items()
                    if s.is_healthy and (
                        allowed_instances is None or name in allowed_instances
                    )
                ]
                unhealthy_filtered = [
                    name for name, s in self.stats.items()
                    if not s.is_healthy and (
                        allowed_instances is None or name in allowed_instances
                    )
                ]

                if not healthy:
                    if not waited_logged and self.logger:
                        filter_note = f" (restricted to: {allowed_instances})" if allowed_instances else ""
                        unhealthy_note = (
                            f"  unhealthy_in_filter={unhealthy_filtered}"
                            if unhealthy_filtered else ""
                        )
                        self.logger.warning(
                            f"{hint}No healthy instances available{filter_note}{unhealthy_note}  "
                            f"cluster: {_cluster_snapshot(self.instances, self.stats)}"
                        )
                        waited_logged = True

                else:
                    name  = self._select_instance(healthy)
                    inst  = self.instances[name]
                    stats = self.stats[name]

                    if stats.active_requests < inst.max_concurrent:
                        # ── ATOMIC: select + increment in one critical section ──
                        stats.active_requests   += 1
                        stats.total_requests    += 1
                        stats.last_request_time  = time.time()

                        active   = stats.active_requests
                        max_c    = inst.max_concurrent
                        load_pct = int((active / max_c) * 100)

                        if self.logger:
                            wait_note = (
                                f"  waited={elapsed:.2f}s polls={poll_count}"
                                if elapsed > 0.15 else f"  wait={elapsed:.3f}s"
                            )
                            self.logger.info(
                                f"{hint}ACQUIRED '{name}'  "
                                f"slot={active}/{max_c} ({load_pct}% load)  "
                                f"pri={inst.priority}{wait_note}  "
                                f"cluster: {_cluster_snapshot(self.instances, self.stats)}"
                            )

                        _name  = name
                        _stats = stats
                        _lock  = self._global_lock
                        _hint  = hint
                        _inst  = inst
                        _start = time.time()
                        _pool_ref = self  # for cluster snapshot on release

                        def release(
                            _n=_name, _s=_stats, _l=_lock, _h=_hint,
                            _i=_inst, _t=_start, _p=_pool_ref
                        ):
                            with _l:
                                _s.active_requests = max(0, _s.active_requests - 1)
                            held_for = time.time() - _t
                            if _p.logger:
                                _p.logger.debug(
                                    f"{_h}RELEASED '{_n}'  "
                                    f"held={held_for:.2f}s  "
                                    f"now={_s.active_requests}/{_i.max_concurrent}  "
                                    f"cluster: {_cluster_snapshot(_p.instances, _p.stats)}"
                                )

                        return (name, inst, release)

                    else:
                        if not waited_logged and self.logger:
                            at_cap_details = "  ".join(
                                f"'{n}' {self.stats[n].active_requests}/{self.instances[n].max_concurrent}"
                                for n in healthy
                            )
                            self.logger.debug(
                                f"{hint}All {len(healthy)} candidate(s) at capacity  "
                                f"[{at_cap_details}]  "
                                f"elapsed={elapsed:.2f}s  waiting…"
                            )
                            waited_logged = True

            time.sleep(0.1)
            waited_logged = False  # allow re-logging after each sleep burst

        # ── Timeout ──────────────────────────────────────────────────────────
        elapsed = time.time() - start_time
        if self.logger:
            filter_note = f" (restricted to: {allowed_instances})" if allowed_instances else ""
            state = "  ".join(
                f"'{n}' {self.stats[n].active_requests}/{self.instances[n].max_concurrent}"
                f"{'[UNHEALTHY]' if not self.stats[n].is_healthy else ''}"
                for n in sorted(self.instances)
            )
            self.logger.warning(
                f"{hint}acquire_instance TIMED OUT after {elapsed:.1f}s "
                f"(budget={timeout:.1f}s, polls={poll_count}){filter_note}  "
                f"final state: [{state}]"
            )
        return None

    # ── Non-atomic peek (kept for compatibility) ───────────────────────────────

    def get_best_instance(
        self, allowed_instances: Optional[List[str]] = None
    ) -> Optional[str]:
        """
        Non-atomic peek at the best instance.
        Use acquire_instance() when you actually intend to USE the instance.
        """
        with self._global_lock:
            healthy = [
                name for name, s in self.stats.items()
                if s.is_healthy and (
                    allowed_instances is None or name in allowed_instances
                )
            ]
            return self._select_instance(healthy) if healthy else None

    def get_stats(self) -> Dict[str, Dict[str, Any]]:
        with self._global_lock:
            result = {}
            for name, stats in self.stats.items():
                inst = self.instances[name]
                result[name] = {
                    "api_url":           inst.api_url,
                    "priority":          inst.priority,
                    "max_concurrent":    inst.max_concurrent,
                    "active_requests":   stats.active_requests,
                    "total_requests":    stats.total_requests,
                    "total_failures":    stats.total_failures,
                    "avg_duration":      stats.total_duration / max(stats.total_requests, 1),
                    "is_healthy":        stats.is_healthy,
                    "last_health_check": stats.last_health_check,
                }
            return result


# ---------------------------------------------------------------------------
# MultiInstanceOllamaManager
# ---------------------------------------------------------------------------

class MultiInstanceOllamaManager:
    """Ollama manager that uses multiple instances with load balancing"""

    def __init__(self, config: OllamaConfig, thought_callback=None, logger=None):
        self.config = config
        self.logger = logger
        self.thought_callback = thought_callback

        # Initialize instance pool
        self.pool = OllamaInstancePool(config, logger)

        # Model metadata cache
        self.model_metadata_cache: Dict[str, Any] = {}

        # Model location cache (instance_name -> set of model names)
        self._model_location_cache: Dict[str, set] = {}
        self._model_location_cache_time: float = 0
        self._model_location_cache_ttl: float = 300  # 5 minutes

        # Connection tested flag
        self.connection_tested = False

        # ── Model Routing Policy ──────────────────────────────────────
        self.gpu_instances: List[str] = getattr(config, 'gpu_instances', ["remote"])

        self.light_model_patterns: List[str] = getattr(
            config, 'light_model_patterns',
            [
                "triage-agent",
                "triage-agent:latest",
                "gpt-oss:20b",
                "gpt-oss:latest",
                "nemotron3-super:latest",
                "gemma2",
                "gemma2:latest",
            ]
        )

        self.heavy_model_patterns: List[str] = getattr(
            config, 'heavy_model_patterns',
            [
                "mistral:7b",
                "mistral:latest",
                "codestral",
                "codestral:latest",
                "gemma3",
                "gpt-oss:latest",
                "deepseek-r1",
                "qwen2.5:7b",
                "llama3",
                "nomic-embed-text",
                "nomic-embed-text:latest",
            ]
        )

        self.gpu_prefer_timeout: float    = getattr(config, 'gpu_prefer_timeout', 45.0)
        self.default_acquire_timeout: float = getattr(config, 'default_acquire_timeout', 30.0)

        if self.logger:
            self.logger.success("Multi-instance Ollama manager initialized")
            if self.gpu_instances:
                self.logger.info(f"GPU instances: {self.gpu_instances}")
                self.logger.info(f"Light model patterns (CPU-only): {self.light_model_patterns}")
                self.logger.info(f"Heavy model patterns (GPU-preferred): {self.heavy_model_patterns}")
                self.logger.info(
                    f"Timeouts: gpu_prefer={self.gpu_prefer_timeout}s  "
                    f"default={self.default_acquire_timeout}s"
                )

    # ── Routing policy ────────────────────────────────────────────────────────

    def _get_model_routing(self, model: str, instances_with_model: List[str]) -> Dict[str, Any]:
        """
        Classify a model and build its routing policy.
        Emits a structured INFO log summarising the decision.
        """
        model_lower = model.lower()

        gpu_set       = set(self.gpu_instances)
        cpu_instances = [i for i in instances_with_model if i not in gpu_set]
        gpu_instances = [i for i in instances_with_model if i in gpu_set]

        # ── Light ──
        matched_light = [p for p in self.light_model_patterns if p.lower() in model_lower]
        if matched_light:
            allowed = cpu_instances if cpu_instances else instances_with_model
            fallback_note = ""

            if cpu_instances and gpu_instances:
                fallback_note = f"  GPU instances EXCLUDED: {gpu_instances}"
            elif not cpu_instances:
                fallback_note = (
                    f"  WARNING: model only on GPU — allowing GPU as fallback"
                )

            if self.logger:
                self.logger.info(
                    f"[routing] '{model}' → LIGHT  "
                    f"matched_patterns={matched_light}  "
                    f"allowed={allowed}  "
                    f"timeout={self.default_acquire_timeout}s"
                    f"{fallback_note}"
                )
            return {
                "allowed_instances":      allowed,
                "acquire_timeout":        self.default_acquire_timeout,
                "gpu_preferred_instances": None,
                "classification":         "light",
            }

        # ── Heavy ──
        matched_heavy = [p for p in self.heavy_model_patterns if p.lower() in model_lower]
        if matched_heavy:
            if self.logger:
                self.logger.info(
                    f"[routing] '{model}' → HEAVY  "
                    f"matched_patterns={matched_heavy}  "
                    f"gpu_preferred={gpu_instances or 'none'}  "
                    f"cpu_fallback={cpu_instances or 'none'}  "
                    f"all_allowed={instances_with_model}  "
                    f"gpu_timeout={self.gpu_prefer_timeout}s  "
                    f"total_timeout={self.gpu_prefer_timeout}s "
                    f"(gpu_phase={self.gpu_prefer_timeout * 0.6:.1f}s  "
                    f"cpu_phase={self.gpu_prefer_timeout * 0.4:.1f}s)"
                )
            return {
                "allowed_instances":       instances_with_model,
                "acquire_timeout":         self.gpu_prefer_timeout,
                "gpu_preferred_instances": gpu_instances if gpu_instances else None,
                "classification":          "heavy",
            }

        # ── Normal ──
        if self.logger:
            self.logger.debug(
                f"[routing] '{model}' → NORMAL  "
                f"allowed={instances_with_model}  "
                f"timeout={self.default_acquire_timeout}s  "
                f"(no pattern match)"
            )
        return {
            "allowed_instances":       instances_with_model,
            "acquire_timeout":         self.default_acquire_timeout,
            "gpu_preferred_instances": None,
            "classification":          "normal",
        }

    # ── Model location cache ──────────────────────────────────────────────────

    def _refresh_model_location_cache(self):
        current_time = time.time()
        if current_time - self._model_location_cache_time < self._model_location_cache_ttl:
            return

        if self.logger:
            self.logger.debug("Refreshing model location cache…")

        self._model_location_cache = {}

        for name, instance in self.pool.instances.items():
            if not self.pool.stats[name].is_healthy:
                continue
            try:
                response = requests.get(f"{instance.api_url}/api/tags", timeout=5)
                if response.status_code == 200:
                    data   = response.json()
                    models = data.get("models", [])
                    self._model_location_cache[name] = {
                        m.get("name", m.get("model", "")) for m in models
                    }
            except Exception as e:
                if self.logger:
                    self.logger.debug(f"[cache] Failed to query {name}: {e}")
                continue

        self._model_location_cache_time = current_time

        if self.logger:
            summary = "  ".join(
                f"'{n}': {len(m)} models"
                for n, m in self._model_location_cache.items()
            )
            self.logger.debug(f"[cache] Refreshed  [{summary}]")

    def find_instances_with_model(self, model: str, use_cache: bool = True) -> List[str]:
        """
        Find which instances have a specific model.
        Returns list of instance names sorted by priority (highest first).
        """
        model_to_find = model if ':' in model else f"{model}:latest"
        if model != model_to_find and self.logger:
            self.logger.debug(f"[find_model] Name normalised: '{model}' → '{model_to_find}'")

        if use_cache:
            self._refresh_model_location_cache()
            instances_with_model = [
                name for name, models in self._model_location_cache.items()
                if model_to_find in models and self.pool.stats[name].is_healthy
            ]
        else:
            instances_with_model = []
            for name, instance in self.pool.instances.items():
                if not self.pool.stats[name].is_healthy:
                    continue
                try:
                    response = requests.get(f"{instance.api_url}/api/tags", timeout=5)
                    if response.status_code == 200:
                        model_names = [
                            m.get("name", m.get("model", ""))
                            for m in response.json().get("models", [])
                        ]
                        if model_to_find in model_names:
                            instances_with_model.append(name)
                            if self.logger:
                                self.logger.debug(
                                    f"[find_model] '{model_to_find}' found on '{name}'"
                                )
                except Exception as e:
                    if self.logger:
                        self.logger.debug(f"[find_model] Could not check '{name}': {e}")
                    continue

        instances_with_model.sort(
            key=lambda n: self.pool.instances[n].priority, reverse=True
        )

        if self.logger:
            if instances_with_model:
                self.logger.debug(
                    f"[find_model] '{model_to_find}' on "
                    f"{len(instances_with_model)} instance(s): "
                    f"{instances_with_model}  (cache={'yes' if use_cache else 'no'})"
                )
            else:
                self.logger.warning(
                    f"[find_model] '{model_to_find}' NOT FOUND on any healthy instance  "
                    f"(cache={'yes' if use_cache else 'no'})"
                )

        return instances_with_model

    # ── Connection / list helpers ─────────────────────────────────────────────

    def test_connection(self) -> bool:
        """Test connection to all instances"""
        if self.connection_tested:
            return True

        healthy_count = 0
        for name, instance in self.pool.instances.items():
            try:
                response = requests.get(f"{instance.api_url}/api/tags", timeout=5)
                if response.status_code == 200:
                    healthy_count += 1
                    self.pool.stats[name].is_healthy = True
                    if self.logger:
                        self.logger.success(f"[connect] '{name}' OK  url={instance.api_url}")
                else:
                    self.pool.stats[name].is_healthy = False
                    if self.logger:
                        self.logger.warning(
                            f"[connect] '{name}' HTTP {response.status_code}  url={instance.api_url}"
                        )
            except Exception as e:
                self.pool.stats[name].is_healthy = False
                if self.logger:
                    self.logger.warning(f"[connect] '{name}' FAILED: {e}")

        self.connection_tested = healthy_count > 0
        if self.logger:
            self.logger.info(
                f"[connect] Result: {healthy_count}/{len(self.pool.instances)} healthy  "
                f"cluster: {_cluster_snapshot(self.pool.instances, self.pool.stats)}"
            )
        return self.connection_tested

    def list_models(self) -> List[Dict]:
        """
        List models using API ONLY - returns plain dicts
        """
        if not self.connection_tested:
            self.test_connection()
        if self.logger:
            self.logger.debug("Listing models via API")
        for name, instance in self.pool.instances.items():
            if not self.pool.stats[name].is_healthy:
                continue
            try:
                response = requests.get(f"{instance.api_url}/api/tags", timeout=5)
                if response.status_code == 200:
                    models_data = response.json().get("models", [])
                    model_list = [
                        {
                            "model":       m.get("name") or m.get("model", "unknown"),
                            "name":        m.get("name") or m.get("model", "unknown"),
                            "size":        m.get("size", 0),
                            "modified_at": m.get("modified_at", ""),
                        }
                        for m in models_data
                    ]
                    if self.logger:
                        self.logger.success(f"Found {len(model_list)} models from '{name}'")
                    return model_list
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"Failed to list models from '{name}': {e}")
                continue
        if self.logger:
            self.logger.error("No healthy instances available to list models")
        return []

    def get_model_metadata(self, model_name: str, force_refresh: bool = False):
        """Get model metadata via API ONLY"""
        if not force_refresh and model_name in self.model_metadata_cache:
            return self.model_metadata_cache[model_name]
        if self.logger:
            self.logger.debug(f"Fetching metadata for '{model_name}'")
        for name, instance in self.pool.instances.items():
            if not self.pool.stats[name].is_healthy:
                continue
            try:
                response = requests.post(
                    f"{instance.api_url}/api/show",
                    json={"name": model_name},
                    timeout=10,
                )
                if response.status_code == 200:
                    metadata = response.json()
                    self.model_metadata_cache[model_name] = metadata
                    if self.logger:
                        self.logger.success(f"Got metadata for '{model_name}' from '{name}'")
                    return metadata
            except Exception as e:
                if self.logger:
                    self.logger.debug(f"Failed to get metadata from '{name}': {e}")
                continue
        if self.logger:
            self.logger.warning(f"Could not fetch metadata for '{model_name}'")
        return {}

    def pull_model(self, model_name: str, stream: bool = True) -> bool:
        """Pull model via API ONLY"""
        if self.logger:
            self.logger.info(f"Pulling model: {model_name}")
        for name, instance in self.pool.instances.items():
            if not self.pool.stats[name].is_healthy:
                continue
            try:
                response = requests.post(
                    f"{instance.api_url}/api/pull",
                    json={"name": model_name, "stream": stream},
                    timeout=300 if not stream else None,
                    stream=stream,
                )
                if stream:
                    for line in response.iter_lines():
                        if line:
                            try:
                                data   = json.loads(line)
                                status = data.get('status', '')
                                if 'total' in data and 'completed' in data:
                                    pct = int((data['completed'] / data['total']) * 100)
                                    if self.logger and pct % 10 == 0:
                                        self.logger.info(f"Pull progress: {pct}%")
                            except Exception:
                                pass
                if response.status_code == 200:
                    if self.logger:
                        self.logger.success(f"Model pulled: {model_name}")
                    self._model_location_cache_time = 0
                    return True
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Failed to pull model from '{name}': {e}")
                continue
        return False

    # ── create_llm ────────────────────────────────────────────────────────────

    def create_llm(self, model: str, temperature: float = 0.7, **kwargs):
        """Create LLM that uses the instance pool with intelligent routing."""
        model_normalized = model if ':' in model else f"{model}:latest"

        if self.logger:
            if model != model_normalized:
                self.logger.debug(
                    f"[create_llm] Name normalised: '{model}' → '{model_normalized}'"
                )
            self.logger.info(
                f"[create_llm] Requesting model='{model_normalized}' temp={temperature}"
            )

        # ── Locate model ──
        instances_with_model = self.find_instances_with_model(model_normalized, use_cache=True)

        if not instances_with_model:
            if self.logger:
                self.logger.debug(
                    f"[create_llm] '{model_normalized}' not in cache — querying instances directly"
                )
            instances_with_model = self.find_instances_with_model(model_normalized, use_cache=False)

            if not instances_with_model:
                all_models = self.list_models()
                available_model_names = list(set(
                    m.get("model", m.get("name", "")) for m in all_models
                ))
                from difflib import get_close_matches
                suggestions = get_close_matches(model_normalized, available_model_names, n=3, cutoff=0.6)
                error_msg = f"Model '{model_normalized}' not found on any healthy Ollama instance."
                if suggestions:
                    error_msg += f" Did you mean: {', '.join(suggestions)}?"
                else:
                    preview = sorted(available_model_names)[:10]
                    error_msg += (
                        f" Available: {', '.join(preview)}"
                        + (f" (+{len(available_model_names)-10} more)" if len(available_model_names) > 10 else "")
                    )
                if self.logger:
                    self.logger.error(f"[create_llm] {error_msg}")
                raise ValueError(error_msg)

        if self.logger:
            self.logger.success(
                f"[create_llm] '{model_normalized}' found on "
                f"{len(instances_with_model)} instance(s): {instances_with_model}"
            )

        # ── Apply routing policy ──
        routing         = self._get_model_routing(model_normalized, instances_with_model)
        routed_instances = routing["allowed_instances"]
        acquire_timeout  = routing["acquire_timeout"]
        gpu_preferred    = routing["gpu_preferred_instances"]
        classification   = routing["classification"]

        if self.logger and routed_instances != instances_with_model:
            excluded = [i for i in instances_with_model if i not in routed_instances]
            self.logger.info(
                f"[create_llm] Routing policy reduced instances: "
                f"{instances_with_model} → {routed_instances}  excluded={excluded}"
            )

        # ── Metadata ──
        metadata = {}
        try:
            metadata = self.get_model_metadata(model_normalized)
        except Exception as e:
            if self.logger:
                self.logger.debug(f"[create_llm] Metadata unavailable for '{model_normalized}': {e}")

        top_k       = kwargs.pop('top_k', 40)
        top_p       = kwargs.pop('top_p', 0.9)
        num_predict = kwargs.pop('num_predict', -1)
        max_retries = kwargs.pop('max_retries', 2)

        llm = PooledOllamaLLM(
            model=model_normalized,
            temperature=temperature,
            top_k=top_k,
            top_p=top_p,
            num_predict=num_predict,
            max_retries=max_retries,
        )

        # Non-Pydantic fields
        llm.pool             = self.pool
        llm.timeout          = self.config.timeout
        llm.thought_callback = self.thought_callback

        # CRITICAL FIX: Create a NEW ThoughtCapture instance for this LLM.
        # Each LLM gets its own capture instance to avoid interference between concurrent requests,
        # but they all share the same callback function for unified thought handling.
        llm.thought_capture  = ThoughtCapture(
            enabled=getattr(self.config, 'enable_thought_capture', True),
            callback=self.thought_callback,  # Shared callback
            logger=self.logger,
        )
        llm.model_metadata    = metadata
        llm.logger            = self.logger
        llm.extra_kwargs      = kwargs

        # IMPORTANT: Apply routing policy to this LLM
        llm.allowed_instances       = routed_instances
        llm.acquire_timeout         = acquire_timeout
        llm.gpu_preferred_instances = gpu_preferred
        llm.model_classification    = classification

        if self.logger:
            gpu_note = f"  gpu_preferred={gpu_preferred}" if gpu_preferred else ""
            self.logger.info(
                f"[create_llm] LLM ready  "
                f"model='{model_normalized}'  class={classification.upper()}  "
                f"instances={routed_instances}  "
                f"timeout={acquire_timeout}s{gpu_note}"
            )

        return llm

    # ── Embeddings ────────────────────────────────────────────────────────────

    def create_embeddings(self, model: str, **kwargs):
        """Create embeddings using API ONLY"""
        best_instance = None
        best_priority = -1
        for name, instance in self.pool.instances.items():
            if self.pool.stats[name].is_healthy and instance.priority > best_priority:
                best_instance = instance
                best_priority = instance.priority
        if not best_instance:
            raise RuntimeError("No healthy instances available for embeddings")
        from langchain_community.embeddings import OllamaEmbeddings
        if self.logger:
            self.logger.info(f"Creating embeddings: model='{model}'  url={best_instance.api_url}")
        return OllamaEmbeddings(model=model, base_url=best_instance.api_url, **kwargs)

    # ── Stats / utils ─────────────────────────────────────────────────────────

    def get_pool_stats(self) -> Dict:
        """Get statistics for all instances"""
        return self.pool.get_stats()

    def print_model_info(self, model_name: str):
        """Print model information via API"""
        metadata = self.get_model_metadata(model_name)
        if not metadata:
            if self.logger:
                self.logger.error(f"No metadata available for '{model_name}'")
            return
        if self.logger:
            self.logger.info("=" * 60)
            self.logger.info(f"Model: {model_name}")
            self.logger.info("=" * 60)
            details    = metadata.get('details', {})
            model_info = metadata.get('model_info', {})
            if details:
                self.logger.info(f"Family:       {details.get('family', 'Unknown')}")
                self.logger.info(f"Parameters:   {details.get('parameter_size', 'Unknown')}")
                self.logger.info(f"Quantization: {details.get('quantization_level', 'Unknown')}")
            if model_info:
                ctx_len = model_info.get('context_length') or model_info.get('n_ctx', 'Unknown')
                self.logger.info(f"Context:      {ctx_len} tokens")
            self.logger.info("=" * 60)

    def list_models_by_instance(self) -> Dict[str, List[Dict]]:
        """Get models from each instance separately"""
        models_by_instance = {}
        for name, instance in self.pool.instances.items():
            if not self.pool.stats[name].is_healthy:
                if self.logger:
                    self.logger.warning(f"Skipping unhealthy instance: '{name}'")
                continue
            try:
                response = requests.get(f"{instance.api_url}/api/tags", timeout=5)
                if response.status_code == 200:
                    models_data = response.json().get("models", [])
                    models_by_instance[name] = [
                        {
                            "name":        m.get("name") or m.get("model", "unknown"),
                            "size":        m.get("size", 0),
                            "modified_at": m.get("modified_at", ""),
                            "digest":      m.get("digest", ""),
                            "details":     m.get("details", {}),
                        }
                        for m in models_data
                    ]
                    if self.logger:
                        self.logger.info(
                            f"Instance '{name}': {len(models_by_instance[name])} models"
                        )
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"Failed to list models from '{name}': {e}")
                models_by_instance[name] = []
        return models_by_instance

    def compare_instances(self) -> Dict[str, Any]:
        """Compare models across instances"""
        models_by_instance = self.list_models_by_instance()
        if len(models_by_instance) < 2:
            return {
                "error": "Need at least 2 healthy instances to compare",
                "instances": list(models_by_instance.keys()),
            }
        all_models = set()
        for models in models_by_instance.values():
            all_models.update(m["name"] for m in models)
        comparison = {
            "instances": list(models_by_instance.keys()),
            "total_unique_models": len(all_models),
            "models": {
                model_name: {
                    inst_name: any(m["name"] == model_name for m in models)
                    for inst_name, models in models_by_instance.items()
                }
                for model_name in sorted(all_models)
            },
        }
        comparison["missing_by_instance"] = {}
        for instance_name in models_by_instance.keys():
            instance_models = {m["name"] for m in models_by_instance[instance_name]}
            missing = all_models - instance_models
            comparison["missing_by_instance"][instance_name] = sorted(missing)
        if self.logger:
            self.logger.info("Model comparison complete:")
            for instance, missing in comparison["missing_by_instance"].items():
                if missing:
                    self.logger.warning(
                        f"  '{instance}' missing {len(missing)} model(s): {missing[:5]}"
                    )
                else:
                    self.logger.success(f"  '{instance}' has all models")
        return comparison

    def analyze_model_dependencies(self, model_name: str, instance_name: str) -> Dict[str, Any]:
        """
        Analyze a model's dependencies (base models, files, etc.)
        Useful for debugging copy failures
        """
        if instance_name not in self.pool.instances:
            return {"error": f"Instance '{instance_name}' not found"}
        instance = self.pool.instances[instance_name]
        try:
            response = requests.post(
                f"{instance.api_url}/api/show", json={"name": model_name}, timeout=10
            )
            if response.status_code != 200:
                return {"error": f"Model '{model_name}' not found on {instance_name}"}
            metadata  = response.json()
            modelfile = metadata.get("modelfile", "")
            dependencies = {
                "base_model": None, "adapters": [], "system_prompt": None,
                "parameters": {}, "template": None,
            }
            for line in modelfile.split('\n'):
                line = line.strip()
                if line.upper().startswith('FROM '):
                    dependencies["base_model"] = line[5:].strip()
                elif line.upper().startswith('ADAPTER '):
                    dependencies["adapters"].append(line[8:].strip())
                elif line.upper().startswith('SYSTEM '):
                    dependencies["system_prompt"] = line[7:].strip()
                elif line.upper().startswith('PARAMETER '):
                    param_line = line[10:].strip()
                    if ' ' in param_line:
                        key, value = param_line.split(' ', 1)
                        dependencies["parameters"][key] = value
                elif line.upper().startswith('TEMPLATE '):
                    dependencies["template"] = line[9:].strip()
            return {
                "model": model_name, "instance": instance_name,
                "dependencies": dependencies,
                "modelfile": modelfile, "modelfile_size": len(modelfile),
            }
        except Exception as e:
            return {"error": f"Failed to analyse model: {e}"}

    def copy_model(self, model_name: str, from_instance: str, to_instance: str,
                   force: bool = False) -> Dict[str, Any]:
        """
        Copy a model from one instance to another.
        Uses a smarter approach that checks for base model dependencies.
        """
        if self.logger:
            self.logger.info(f"Copying '{model_name}': '{from_instance}' → '{to_instance}'")
        if from_instance not in self.pool.instances:
            return {"error": f"Source instance '{from_instance}' not found"}
        if to_instance not in self.pool.instances:
            return {"error": f"Destination instance '{to_instance}' not found"}
        source = self.pool.instances[from_instance]
        dest   = self.pool.instances[to_instance]
        try:
            response = requests.post(
                f"{source.api_url}/api/show", json={"name": model_name}, timeout=10
            )
            if response.status_code != 200:
                return {"error": f"Model '{model_name}' not found on {from_instance}",
                        "status_code": response.status_code}
            source_metadata = response.json()
        except Exception as e:
            return {"error": f"Failed to get model info from {from_instance}: {e}"}
        if not force:
            try:
                response = requests.post(
                    f"{dest.api_url}/api/show", json={"name": model_name}, timeout=10
                )
                if response.status_code == 200:
                    return {"status": "skipped",
                            "message": f"Model already exists on {to_instance} (use force=True to overwrite)",
                            "model": model_name}
            except Exception:
                pass
        modelfile = source_metadata.get("modelfile", "")
        if not modelfile:
            return {"error": f"Could not get Modelfile from {from_instance}", "model": model_name}
        base_model = None
        for line in modelfile.split('\n'):
            if line.strip().upper().startswith('FROM '):
                base_model = line.strip()[5:].strip()
                break
        if self.logger:
            self.logger.info(f"Modelfile size={len(modelfile)} chars  base='{base_model or 'none'}'")
        if base_model:
            try:
                response = requests.post(
                    f"{dest.api_url}/api/show", json={"name": base_model}, timeout=10
                )
                if response.status_code != 200:
                    if self.logger:
                        self.logger.warning(
                            f"Base model '{base_model}' missing on '{to_instance}' — pulling…"
                        )
                    pull_response = requests.post(
                        f"{dest.api_url}/api/pull",
                        json={"name": base_model}, stream=True, timeout=600,
                    )
                    if pull_response.status_code != 200:
                        return {"error": f"Base '{base_model}' not available on {to_instance} and pull failed",
                                "model": model_name,
                                "suggestion": f"Pull '{base_model}' on {to_instance} first"}
                    for line in pull_response.iter_lines():
                        if line:
                            try:
                                data = json.loads(line)
                                if self.logger and data.get('status'):
                                    self.logger.debug(f"  pull: {data['status']}")
                            except Exception:
                                pass
                    if self.logger:
                        self.logger.success(f"Base model '{base_model}' pulled")
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"Could not verify base model: {e}")
        try:
            response = requests.post(
                f"{dest.api_url}/api/create",
                json={"name": model_name, "modelfile": modelfile, "stream": True},
                stream=True, timeout=600,
            )
            if response.status_code != 200:
                return {"error": f"Failed to create model on {to_instance}",
                        "status_code": response.status_code,
                        "response": response.text[:500]}
            last_status = None
            error_in_stream = None
            for line in response.iter_lines():
                if line:
                    try:
                        data   = json.loads(line)
                        status = data.get("status", "")
                        if status and status != last_status:
                            if self.logger:
                                self.logger.info(f"  create: {status}")
                            last_status = status
                        if "error" in data:
                            error_in_stream = data["error"]
                            if self.logger:
                                self.logger.error(f"Stream error: {error_in_stream}")
                    except json.JSONDecodeError:
                        continue
            if error_in_stream:
                return {"error": f"Model creation failed: {error_in_stream}", "model": model_name}
            if self.logger:
                self.logger.success(f"Model '{model_name}' copied successfully")
            self._model_location_cache_time = 0
            return {"status": "success", "model": model_name,
                    "source": from_instance, "destination": to_instance}
        except requests.exceptions.Timeout:
            return {"error": "Model creation timed out", "model": model_name}
        except Exception as e:
            if self.logger:
                self.logger.error(f"Copy failed: {e}", exc_info=True)
            return {"error": f"Failed to copy model: {e}", "model": model_name}

    def sync_models(self, source_instance: str, target_instances: Optional[List[str]] = None,
                    models: Optional[List[str]] = None, force: bool = False,
                    dry_run: bool = False) -> Dict[str, Any]:
        """
        Sync models from source to target instances.

        Args:
            source_instance: Instance to copy models from
            target_instances: Instances to copy to (None = all other instances)
            models: Specific models to sync (None = all models)
            force: Overwrite existing models
            dry_run: Just report what would be synced, don't actually sync

        Returns:
            Detailed sync report
        """
        if self.logger:
            self.logger.info(
                f"{'[DRY RUN] ' if dry_run else ''}Syncing from '{source_instance}'"
            )
        if source_instance not in self.pool.instances:
            return {"error": f"Source instance '{source_instance}' not found"}
        if target_instances is None:
            target_instances = [n for n in self.pool.instances if n != source_instance]
        for t in target_instances:
            if t not in self.pool.instances:
                return {"error": f"Target instance '{t}' not found"}
        try:
            response = requests.get(
                f"{self.pool.instances[source_instance].api_url}/api/tags", timeout=5
            )
            if response.status_code != 200:
                return {"error": f"Failed to list models on '{source_instance}'"}
            source_models = [
                m.get("name") or m.get("model", "")
                for m in response.json().get("models", [])
            ]
        except Exception as e:
            return {"error": f"Failed to get models from '{source_instance}': {e}"}
        if models is not None:
            source_models = [m for m in source_models if m in models]
            missing = set(models) - set(source_models)
            if missing and self.logger:
                self.logger.warning(f"Requested models not on '{source_instance}': {missing}")
        if not source_models:
            return {"status": "nothing_to_sync", "source": source_instance, "targets": target_instances}
        sync_plan = {
            "source": source_instance, "targets": target_instances,
            "models": source_models, "total_models": len(source_models),
            "dry_run": dry_run, "operations": [],
        }
        for target in target_instances:
            try:
                response = requests.get(
                    f"{self.pool.instances[target].api_url}/api/tags", timeout=5
                )
                target_models = []
                if response.status_code == 200:
                    target_models = [
                        m.get("name") or m.get("model", "")
                        for m in response.json().get("models", [])
                    ]
                for model in source_models:
                    exists = model in target_models
                    if exists and not force:
                        action, reason = "skip", "already exists"
                    else:
                        action = "copy" if not dry_run else "would_copy"
                        reason = "overwrite" if exists else "new"
                    sync_plan["operations"].append({
                        "model": model, "target": target,
                        "action": action, "reason": reason, "exists": exists,
                    })
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Failed to check '{target}': {e}")
        sync_plan["summary"] = {
            "total_operations": len(sync_plan["operations"]),
            "will_copy":  sum(1 for op in sync_plan["operations"] if op["action"] in ["copy", "would_copy"]),
            "will_skip":  sum(1 for op in sync_plan["operations"] if op["action"] == "skip"),
        }
        if self.logger:
            self.logger.info(
                f"Sync plan: {sync_plan['summary']['will_copy']} to copy  "
                f"{sync_plan['summary']['will_skip']} to skip"
            )
        if not dry_run:
            results = []
            for op in sync_plan["operations"]:
                if op["action"] == "copy":
                    if self.logger:
                        self.logger.info(f"Copying '{op['model']}' → '{op['target']}'…")
                    result = self.copy_model(op["model"], source_instance, op["target"], force=force)
                    results.append({**op, "result": result})
            sync_plan["results"]   = results
            sync_plan["execution"] = {
                "success": sum(1 for r in results if r["result"].get("status") == "success"),
                "failed":  sum(1 for r in results if "error" in r["result"]),
                "skipped": sum(1 for r in results if r["result"].get("status") == "skipped"),
            }
            if self.logger:
                self.logger.success(
                    f"Sync complete: {sync_plan['execution']['success']} succeeded  "
                    f"{sync_plan['execution']['failed']} failed"
                )
        return sync_plan

    def set_manual_routing(self, instance_names: List[str]):
        """
        Enable manual routing to specific instances.
        Temporarily filters the pool to only use specified instances.

        Args:
            instance_names: List of instance names to use
        """
        if not instance_names:
            raise ValueError("Must specify at least one instance for manual routing")
        invalid = set(instance_names) - set(self.pool.instances.keys())
        if invalid:
            raise ValueError(f"Invalid instance names: {invalid}")
        if not hasattr(self, '_original_instances'):
            self._original_instances = self.pool.instances.copy()
        self.pool.instances = {
            name: config
            for name, config in self._original_instances.items()
            if name in instance_names
        }
        if self.logger:
            self.logger.info(f"Manual routing enabled: {instance_names}")

    def set_auto_routing(self):
        """Restore automatic routing (use all instances)"""
        if hasattr(self, '_original_instances'):
            self.pool.instances = self._original_instances.copy()
            delattr(self, '_original_instances')
        if self.logger:
            self.logger.info("Automatic routing restored")

    def get_routing_mode(self) -> dict:
        """
        Get current routing configuration.

        Returns:
            Dict with routing mode and active instances
        """
        is_manual = hasattr(self, '_original_instances')
        return {
            "mode":             "manual" if is_manual else "auto",
            "active_instances": list(self.pool.instances.keys()),
            "total_instances":  len(self._original_instances) if is_manual else len(self.pool.instances),
            "filtered":         is_manual,
        }

    def create_llm_with_routing(self, model: str, routing_mode: str = "auto",
                                  selected_instances: Optional[List[str]] = None, **kwargs):
        """
        Create LLM with explicit routing control.

        Args:
            model: Model name
            routing_mode: 'auto' or 'manual'
            selected_instances: Instance names for manual mode
            **kwargs: Additional LLM parameters

        Returns:
            Configured LLM instance
        """
        if routing_mode == "manual" and selected_instances:
            self.set_manual_routing(selected_instances)
        elif routing_mode == "auto":
            self.set_auto_routing()
        return self.create_llm(model, **kwargs)


# ---------------------------------------------------------------------------
# PooledOllamaLLM
# ---------------------------------------------------------------------------

from langchain.llms.base import LLM
from langchain_core.outputs import GenerationChunk
from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from typing import Any, List, Optional, Iterator, Dict
from pydantic import Field
import time
import json
import requests


class PooledOllamaLLM(LLM):
    """
    LLM wrapper that uses instance pool for all requests.
    Fully compatible with LangChain by properly inheriting from LLM base class.
    """

    # Required Pydantic fields
    model:       str   = Field(description="Model name")
    temperature: float = Field(default=0.7, description="Temperature for generation")
    top_k:       int   = Field(default=40, description="Top-k sampling parameter")
    top_p:       float = Field(default=0.9, description="Top-p sampling parameter")
    num_predict: int   = Field(default=-1, description="Number of tokens to predict")
    max_retries: int   = Field(default=2, description="Max retries across instances")

    # Non-Pydantic fields (excluded from validation)
    pool:                    Any             = Field(default=None, exclude=True, repr=False)
    timeout:                 int             = Field(default=2400, exclude=True)
    thought_callback:        Optional[Any]   = Field(default=None, exclude=True, repr=False)
    thought_capture:         Any             = Field(default=None, exclude=True, repr=False)
    model_metadata:          Optional[Dict]  = Field(default=None, exclude=True)
    logger:                  Any             = Field(default=None, exclude=True, repr=False)
    extra_kwargs:            Dict            = Field(default_factory=dict, exclude=True)
    allowed_instances:       Optional[List[str]] = Field(default=None, exclude=True)

    # ── Routing policy fields (set by create_llm) ────────────────────────────
    acquire_timeout:         float           = Field(default=30.0, exclude=True)
    gpu_preferred_instances: Optional[List[str]] = Field(default=None, exclude=True)
    model_classification:    str             = Field(default="normal", exclude=True)

    class Config:
        """Pydantic config"""
        arbitrary_types_allowed = True
        extra = "forbid"  # Don't allow extra fields

    @property
    def _llm_type(self) -> str:
        """Return identifier for LLM type - REQUIRED by LangChain"""
        return "pooled_ollama"

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        """Return identifying parameters - used by LangChain"""
        return {
            "model":                  self.model,
            "temperature":            self.temperature,
            "top_k":                  self.top_k,
            "top_p":                  self.top_p,
            "pool_instances":         len(self.pool.instances) if self.pool else 0,
            "allowed_instances":      self.allowed_instances,
            "model_classification":   self.model_classification,
            "gpu_preferred_instances": self.gpu_preferred_instances,
        }

    # ── GPU-aware acquisition ─────────────────────────────────────────────────

    def _acquire_with_gpu_preference(
        self,
        timeout: float,
        caller_hint: str = "",
    ) -> Optional[tuple]:
        """
        Acquire an instance, preferring GPU for heavy models.

        Phase 1 (heavy only): try gpu_preferred_instances for 60% of the budget.
        Phase 2 (heavy only): fall back to all allowed instances for remaining 40%.
        Non-heavy / no GPU list: standard acquire.
        """
        hint = f"[{caller_hint}] " if caller_hint else ""

        if not self.gpu_preferred_instances or self.model_classification != "heavy":
            if self.logger:
                self.logger.debug(
                    f"{hint}_acquire  class={self.model_classification}  "
                    f"gpu_preferred=none  "
                    f"→ standard acquire  allowed={self.allowed_instances}  "
                    f"timeout={timeout:.1f}s"
                )
            return self.pool.acquire_instance(
                timeout=timeout,
                allowed_instances=self.allowed_instances,
                caller_hint=caller_hint,
            )

        gpu_timeout = timeout * 0.6
        cpu_timeout = timeout * 0.4

        if self.logger:
            self.logger.info(
                f"{hint}_acquire  class=HEAVY  "
                f"phase1=GPU {self.gpu_preferred_instances} ({gpu_timeout:.1f}s)  "
                f"phase2=CPU_fallback {self.allowed_instances} ({cpu_timeout:.1f}s)  "
                f"total={timeout:.1f}s"
            )

        # Phase 1: GPU
        t0  = time.time()
        acq = self.pool.acquire_instance(
            timeout=gpu_timeout,
            allowed_instances=self.gpu_preferred_instances,
            caller_hint=f"{caller_hint}/gpu-phase1",
        )
        if acq:
            if self.logger:
                elapsed = time.time() - t0
                self.logger.success(
                    f"{hint}GPU phase succeeded  instance='{acq[0]}'  "
                    f"waited={elapsed:.2f}s"
                )
            return acq

        # Phase 2: CPU fallback
        gpu_elapsed = time.time() - t0
        if self.logger:
            self.logger.info(
                f"{hint}GPU phase TIMED OUT ({gpu_elapsed:.2f}s)  "
                f"→ CPU fallback phase  allowed={self.allowed_instances}  "
                f"budget={cpu_timeout:.1f}s"
            )
        t1  = time.time()
        acq = self.pool.acquire_instance(
            timeout=cpu_timeout,
            allowed_instances=self.allowed_instances,
            caller_hint=f"{caller_hint}/cpu-phase2",
        )
        if acq:
            if self.logger:
                elapsed = time.time() - t1
                self.logger.info(
                    f"{hint}CPU fallback succeeded  instance='{acq[0]}'  "
                    f"waited={elapsed:.2f}s"
                )
        else:
            if self.logger:
                self.logger.warning(
                    f"{hint}Both GPU and CPU phases FAILED  "
                    f"total_elapsed={time.time() - t0:.2f}s"
                )
        return acq

    # ── LangChain interface ───────────────────────────────────────────────────

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """
        Call method REQUIRED by LangChain LLM base class.
        This is NOT a property - it's a regular method.
        """
        return self._invoke_with_retry(prompt, stop=stop, **kwargs)

    def _stream(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[GenerationChunk]:
        """
        Stream method for LangChain compatibility.
        Yields GenerationChunk objects.
        """
        for chunk_text in self._stream_with_retry(prompt, stop=stop, **kwargs):
            chunk = GenerationChunk(text=chunk_text)
            if run_manager:
                run_manager.on_llm_new_token(chunk_text)
            yield chunk

    # ── _invoke_with_retry ────────────────────────────────────────────────────

    def _invoke_with_retry(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        caller_hint: str = "",
        **kwargs,
    ) -> str:
        """Internal method: Non-streaming generation with automatic failover."""
        hint         = f"[{caller_hint}] " if caller_hint else f"[{self.model}] "
        last_error   = None
        attempts     = 0
        # Use allowed_instances if set, otherwise try all
        available    = self.allowed_instances or list(self.pool.instances.keys())
        max_attempts = min(self.max_retries, len(available))

        if self.thought_capture:
            self.thought_capture.reset()

        if self.logger:
            self.logger.info(
                f"{hint}invoke (non-stream)  "
                f"class={self.model_classification}  "
                f"max_attempts={max_attempts}  "
                f"allowed={self.allowed_instances}  "
                f"acquire_timeout={self.acquire_timeout}s"
            )

        while attempts < max_attempts:
            attempts += 1
            attempt_start = time.time()

            if self.logger:
                self.logger.debug(
                    f"{hint}attempt {attempts}/{max_attempts}  acquiring instance…"
                )

            if not self.pool:
                raise RuntimeError("Pool not initialised")

            acquisition = self._acquire_with_gpu_preference(
                timeout=self.acquire_timeout,
                caller_hint=caller_hint or self.model,
            )

            if not acquisition:
                if self.logger:
                    filter_msg = (
                        f" (filtered to: {self.allowed_instances})"
                        if self.allowed_instances else ""
                    )
                    self.logger.warning(
                        f"{hint}attempt {attempts}/{max_attempts}  "
                        f"NO INSTANCE AVAILABLE{filter_msg}"
                    )
                if attempts < max_attempts:
                    time.sleep(1.0)
                    continue
                raise RuntimeError(
                    f"No Ollama instances available after {max_attempts} attempts "
                    f"(allowed: {self.allowed_instances})"
                )

            instance_name, instance, release = acquisition

            try:
                if self.logger:
                    self.logger.debug(
                        f"{hint}attempt {attempts}/{max_attempts}  "
                        f"sending to '{instance_name}'  "
                        f"url={instance.api_url}/api/generate  "
                        f"prompt_len={len(prompt)}"
                    )

                request_data = {
                    "model":       self.model,
                    "prompt":      prompt,
                    "temperature": self.temperature,
                    "stream":      False,
                    "top_k":       self.top_k,
                    "top_p":       self.top_p,
                    "num_predict": self.num_predict,
                    **self.extra_kwargs,
                }
                if stop:
                    request_data["stop"] = stop

                t0       = time.time()
                response = requests.post(
                    f"{instance.api_url}/api/generate",
                    json=request_data,
                    timeout=self.timeout,
                )
                duration = time.time() - t0

                if response.status_code == 200:
                    data   = response.json()

                    # PROCESS THOUGHTS using ThoughtCapture
                    result = (
                        self.thought_capture.process_chunk(data)
                        if self.thought_capture
                        else data.get("response", "")
                    )

                    # Update stats
                    if hasattr(self.pool, 'stats') and instance_name in self.pool.stats:
                        self.pool.stats[instance_name].total_duration += duration

                    if self.logger:
                        token_note = (
                            f"  tokens={data.get('eval_count', '?')}"
                            f"/{data.get('prompt_eval_count', '?')}"
                            if 'eval_count' in data else ""
                        )
                        self.logger.success(
                            f"{hint}DONE on '{instance_name}'  "
                            f"duration={duration:.2f}s  "
                            f"response_len={len(result)}{token_note}  "
                            f"attempt={attempts}/{max_attempts}"
                        )
                    return result

                else:
                    error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                    if self.logger:
                        self.logger.warning(
                            f"{hint}attempt {attempts}/{max_attempts}  "
                            f"'{instance_name}' FAILED: {error_msg}  "
                            f"elapsed={duration:.2f}s"
                        )
                    if response.status_code >= 500:
                        if hasattr(self.pool, 'stats') and instance_name in self.pool.stats:
                            self.pool.stats[instance_name].is_healthy = False
                        if self.logger:
                            self.logger.warning(
                                f"{hint}Marking '{instance_name}' UNHEALTHY (5xx)  "
                                f"cluster: {_cluster_snapshot(self.pool.instances, self.pool.stats)}"
                            )
                    if hasattr(self.pool, 'stats') and instance_name in self.pool.stats:
                        self.pool.stats[instance_name].total_failures += 1
                    last_error = RuntimeError(error_msg)
                    if attempts < max_attempts:
                        if self.logger:
                            self.logger.info(
                                f"{hint}Retrying (attempt {attempts+1}/{max_attempts})…"
                            )
                        continue

            except requests.exceptions.Timeout as e:
                if self.logger:
                    elapsed = time.time() - attempt_start
                    self.logger.warning(
                        f"{hint}attempt {attempts}/{max_attempts}  "
                        f"TIMEOUT on '{instance_name}'  "
                        f"elapsed={elapsed:.1f}s  limit={self.timeout}s"
                    )
                if hasattr(self.pool, 'stats') and instance_name in self.pool.stats:
                    self.pool.stats[instance_name].is_healthy = False
                    self.pool.stats[instance_name].total_failures += 1
                if self.logger:
                    self.logger.warning(
                        f"{hint}Marking '{instance_name}' UNHEALTHY (timeout)  "
                        f"cluster: {_cluster_snapshot(self.pool.instances, self.pool.stats)}"
                    )
                last_error = e
                if attempts < max_attempts:
                    if self.logger:
                        self.logger.info(f"{hint}Retrying (attempt {attempts+1}/{max_attempts})…")
                    continue

            except Exception as e:
                if self.logger:
                    elapsed = time.time() - attempt_start
                    self.logger.error(
                        f"{hint}attempt {attempts}/{max_attempts}  "
                        f"EXCEPTION on '{instance_name}': {e}  "
                        f"elapsed={elapsed:.1f}s"
                    )
                if hasattr(self.pool, 'stats') and instance_name in self.pool.stats:
                    self.pool.stats[instance_name].total_failures += 1
                last_error = e
                if attempts < max_attempts:
                    if self.logger:
                        self.logger.info(f"{hint}Retrying (attempt {attempts+1}/{max_attempts})…")
                    continue

            finally:
                release()

        if self.logger:
            self.logger.error(
                f"{hint}ALL {attempts} attempt(s) failed  "
                f"cluster: {_cluster_snapshot(self.pool.instances, self.pool.stats)}"
            )
        raise last_error or RuntimeError(
            f"Generation failed after {attempts} attempts"
        )

    # ── _stream_with_retry ────────────────────────────────────────────────────

    def _stream_with_retry(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        caller_hint: str = "",
        **kwargs,
    ) -> Iterator[str]:
        """Internal method: Streaming generation with automatic failover."""
        hint         = f"[{caller_hint}] " if caller_hint else f"[{self.model}] "
        last_error   = None
        attempts     = 0
        # Use allowed_instances if set, otherwise try all
        available    = self.allowed_instances or list(self.pool.instances.keys())
        max_attempts = min(self.max_retries, len(available))
        tried: set   = set()  # Track which instances we've tried to avoid immediate retry on same instance

        if self.thought_capture:
            self.thought_capture.reset()

        if self.logger:
            self.logger.info(
                f"{hint}stream  "
                f"class={self.model_classification}  "
                f"max_attempts={max_attempts}  "
                f"allowed={self.allowed_instances}  "
                f"acquire_timeout={self.acquire_timeout}s"
            )

        while attempts < max_attempts:
            attempts += 1
            attempt_start = time.time()

            untried = [
                i for i in available
                if i not in tried and self.pool.stats[i].is_healthy
            ]
            if not untried and attempts < max_attempts:
                if self.logger:
                    self.logger.debug(
                        f"{hint}All candidate instances tried — resetting tried set  "
                        f"tried={tried}"
                    )
                tried.clear()
                untried = [i for i in available if self.pool.stats[i].is_healthy]

            if self.logger:
                self.logger.debug(
                    f"{hint}stream attempt {attempts}/{max_attempts}  "
                    f"untried={untried}  tried={tried}"
                )

            # Acquire instance with GPU-aware routing.
            # For first attempt on heavy models, prefer GPU from untried set.
            if (
                attempts == 1
                and self.model_classification == "heavy"
                and self.gpu_preferred_instances
            ):
                # First try: use the full GPU-preference logic
                acquisition = self._acquire_with_gpu_preference(
                    timeout=self.acquire_timeout,
                    caller_hint=caller_hint or self.model,
                )
            else:
                # Subsequent tries or non-heavy: standard acquire from untried
                acquisition = self.pool.acquire_instance(
                    timeout=self.acquire_timeout,
                    allowed_instances=untried or self.allowed_instances,
                    caller_hint=f"{caller_hint or self.model}/stream-a{attempts}",
                )

            if not acquisition:
                if self.logger:
                    self.logger.warning(
                        f"{hint}stream attempt {attempts}/{max_attempts}  "
                        f"NO INSTANCE AVAILABLE  untried={untried}"
                    )
                if attempts < max_attempts:
                    time.sleep(1.0)
                    continue
                raise RuntimeError(
                    f"No Ollama instances available after {max_attempts} attempts"
                )

            instance_name, instance, release = acquisition
            tried.add(instance_name)

            try:
                if self.logger:
                    self.logger.debug(
                        f"{hint}stream attempt {attempts}/{max_attempts}  "
                        f"streaming from '{instance_name}'  "
                        f"url={instance.api_url}/api/generate  "
                        f"prompt_len={len(prompt)}"
                    )

                request_data = {
                    "model":       self.model,
                    "prompt":      prompt,
                    "temperature": self.temperature,
                    "stream":      True,
                    "top_k":       self.top_k,
                    "top_p":       self.top_p,
                    "num_predict": self.num_predict,
                    **self.extra_kwargs,
                }
                if stop:
                    request_data["stop"] = stop

                response = requests.post(
                    f"{instance.api_url}/api/generate",
                    json=request_data,
                    stream=True,
                    timeout=self.timeout,
                )

                if response.status_code != 200:
                    error_msg = f"HTTP {response.status_code}"
                    if self.logger:
                        self.logger.warning(
                            f"{hint}stream attempt {attempts}/{max_attempts}  "
                            f"'{instance_name}' returned {error_msg}"
                        )
                    if response.status_code >= 500:
                        if hasattr(self.pool, 'stats') and instance_name in self.pool.stats:
                            self.pool.stats[instance_name].is_healthy = False
                        if self.logger:
                            self.logger.warning(
                                f"{hint}Marking '{instance_name}' UNHEALTHY (5xx)  "
                                f"cluster: {_cluster_snapshot(self.pool.instances, self.pool.stats)}"
                            )
                    if hasattr(self.pool, 'stats') and instance_name in self.pool.stats:
                        self.pool.stats[instance_name].total_failures += 1
                    last_error = RuntimeError(error_msg)
                    release()
                    if attempts < max_attempts:
                        if self.logger:
                            self.logger.info(
                                f"{hint}Retrying stream on different instance "
                                f"(attempt {attempts+1}/{max_attempts})…"
                            )
                        continue
                    raise last_error

                # ── Consume stream ────────────────────────────────────────────
                chunk_count      = 0
                first_chunk_time: Optional[float] = None
                stream_start     = time.time()

                try:
                    for line in response.iter_lines():
                        if line:
                            try:
                                data = json.loads(line)

                                # PROCESS THOUGHTS using ThoughtCapture
                                chunk_text = (
                                    self.thought_capture.process_chunk(data)
                                    if self.thought_capture
                                    else data.get("response", "")
                                )

                                # Only yield if we have actual response text
                                if chunk_text:
                                    if first_chunk_time is None:
                                        first_chunk_time = time.time()
                                        if self.logger:
                                            self.logger.debug(
                                                f"{hint}First chunk from '{instance_name}'  "
                                                f"ttfc={first_chunk_time - stream_start:.2f}s"
                                            )
                                    chunk_count += 1
                                    yield chunk_text
                            except json.JSONDecodeError:
                                continue

                    total_duration = time.time() - stream_start
                    if self.logger:
                        ttfc_note = (
                            f"  ttfc={first_chunk_time - stream_start:.2f}s"
                            if first_chunk_time else "  ttfc=n/a"
                        )
                        self.logger.success(
                            f"{hint}Stream COMPLETE from '{instance_name}'  "
                            f"chunks={chunk_count}  "
                            f"duration={total_duration:.2f}s{ttfc_note}  "
                            f"attempt={attempts}/{max_attempts}"
                        )
                    return  # success

                except Exception as stream_err:
                    elapsed = time.time() - stream_start
                    if self.logger:
                        self.logger.warning(
                            f"{hint}Stream INTERRUPTED on '{instance_name}'  "
                            f"chunks_so_far={chunk_count}  "
                            f"elapsed={elapsed:.2f}s  "
                            f"error={stream_err}"
                        )
                    last_error = stream_err
                    if attempts < max_attempts:
                        if self.logger:
                            self.logger.info(
                                f"{hint}Retrying stream "
                                f"(attempt {attempts+1}/{max_attempts})…"
                            )
                        continue

            except Exception as e:
                elapsed = time.time() - attempt_start
                if self.logger:
                    self.logger.warning(
                        f"{hint}stream attempt {attempts}/{max_attempts}  "
                        f"OUTER EXCEPTION on '{instance_name}': {e}  "
                        f"elapsed={elapsed:.2f}s"
                    )
                if hasattr(self.pool, 'stats') and instance_name in self.pool.stats:
                    self.pool.stats[instance_name].total_failures += 1
                last_error = e
                if attempts < max_attempts:
                    if self.logger:
                        self.logger.info(
                            f"{hint}Retrying stream "
                            f"(attempt {attempts+1}/{max_attempts})…"
                        )
                    continue

            finally:
                release()

        if self.logger:
            self.logger.error(
                f"{hint}ALL {attempts} stream attempt(s) failed  "
                f"tried={tried}  "
                f"cluster: {_cluster_snapshot(self.pool.instances, self.pool.stats)}"
            )
        raise last_error or RuntimeError(
            f"Stream failed after {attempts} attempts"
        )