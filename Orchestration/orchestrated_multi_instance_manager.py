"""
Vera MultiInstanceOllamaManager (Runner-Aware Edition)
======================================================
Thin wrapper around the existing MultiInstanceOllamaManager that:

  1. Accepts an optional RunnerAwareOrchestrator at construction time
  2. Registers every enabled Ollama instance into the orchestrator's
     RunnerRegistry on start-up and whenever instances are added/removed
  3. Keeps all Ollama-specific API operations (pull, list, copy, sync,
     metadata) in this class — the orchestrator owns scheduling only
  4. Exposes submit_llm() as a convenience pass-through so callers that
     previously used create_llm().predict() can migrate gradually

The manager is fully backward-compatible — if no orchestrator is passed,
it behaves exactly as before.
"""

import time
import threading
import requests
import logging
from typing import Any, Dict, List, Optional, Set

try:
    from Vera.Configuration.config_manager import OllamaConfig, OllamaInstanceConfig
except ImportError:
    from Configuration.config_manager import OllamaConfig, OllamaInstanceConfig

# Import the original manager to inherit all non-scheduling logic
try:
    from Vera.Ollama.multi_instance_manager import (
        MultiInstanceOllamaManager as _BaseManager,
        PooledOllamaLLM,
    )
except ImportError:
    from Ollama.multi_instance_manager import (
        MultiInstanceOllamaManager as _BaseManager,
        PooledOllamaLLM,
    )

from vera_orchestration.orchestrator_patch import RunnerAwareOrchestrator


class OrchestratedOllamaManager(_BaseManager):
    """
    MultiInstanceOllamaManager that registers Ollama instances as
    first-class runners in a RunnerAwareOrchestrator.

    Parameters
    ----------
    config : OllamaConfig
        Existing configuration (unchanged).
    orchestrator : RunnerAwareOrchestrator, optional
        If provided, every enabled instance is registered into the
        orchestrator's RunnerRegistry.  If None, behaviour is identical
        to the base class.
    thought_callback : callable, optional
        Shared thought-capture callback (unchanged).
    logger : LogContext, optional
        Vera logger instance.

    Example
    -------
        orchestrator = RunnerAwareOrchestrator(
            num_llm_workers=6,
            gpu_runner_ids=["remote"],
        )
        orchestrator.start()

        manager = OrchestratedOllamaManager(
            config=ollama_config,
            orchestrator=orchestrator,
        )

        # Direct LLM submission — no create_llm() needed
        task_id = manager.submit_llm(
            prompt="What is the capital of France?",
            model="mistral:latest",
        )
        for chunk in manager.stream_result(task_id):
            print(chunk, end="", flush=True)
    """

    def __init__(
        self,
        config:       OllamaConfig,
        orchestrator: Optional[RunnerAwareOrchestrator] = None,
        thought_callback=None,
        logger=None,
    ):
        super().__init__(config, thought_callback=thought_callback, logger=logger)

        self._orchestrator = orchestrator
        self._registered_runners: Set[str] = set()
        self._reg_lock = threading.Lock()
        self._orch_logger = logging.getLogger("OrchestratedOllamaManager")

        if orchestrator is not None:
            self._register_all_instances()
            self._start_sync_thread()

    # ------------------------------------------------------------------ #
    # Registration                                                         #
    # ------------------------------------------------------------------ #

    def _register_all_instances(self):
        """Register every enabled instance into the orchestrator."""
        if self._orchestrator is None:
            return

        for name, instance_cfg in self.pool.instances.items():
            self._register_instance(name, instance_cfg)

    def _register_instance(self, name: str, instance_cfg):
        """Register a single Ollama instance into the RunnerRegistry."""
        if self._orchestrator is None:
            return

        gpu = getattr(instance_cfg, "gpu", False) or (
            name in self.gpu_instances
        )

        with self._reg_lock:
            self._orchestrator.register_ollama_instance(
                name=name,
                api_url=instance_cfg.api_url,
                gpu=gpu,
                max_concurrent=getattr(instance_cfg, "max_concurrent", 2),
                priority=getattr(instance_cfg, "priority", 0),
                tags={"ollama"},
                probe=True,
            )
            self._registered_runners.add(name)

        self._orch_logger.info(
            f"Instance {name!r} registered in orchestrator (gpu={gpu})"
        )

    def _start_sync_thread(self):
        """
        Background thread that periodically syncs the instance pool state
        with the RunnerRegistry (handles new/removed instances if the pool
        is modified at runtime).
        """
        def _sync_loop():
            while True:
                time.sleep(60)
                self._sync_instances()

        t = threading.Thread(target=_sync_loop, daemon=True, name="OllamaManagerSync")
        t.start()

    def _sync_instances(self):
        """Reconcile pool instances with the registry."""
        if self._orchestrator is None:
            return

        current = set(self.pool.instances.keys())

        # Register new instances
        for name in current - self._registered_runners:
            cfg = self.pool.instances[name]
            self._register_instance(name, cfg)

        # Deregister removed instances
        for name in self._registered_runners - current:
            self._orchestrator.deregister_runner(name, drain=True)
            with self._reg_lock:
                self._registered_runners.discard(name)
            self._orch_logger.info(f"Instance {name!r} deregistered from orchestrator")

    # ------------------------------------------------------------------ #
    # LLM submission pass-through                                          #
    # ------------------------------------------------------------------ #

    def submit_llm(
        self,
        prompt:      str,
        model:       str,
        *,
        stream:      bool  = True,
        temperature: float = 0.7,
        top_k:       int   = 40,
        top_p:       float = 0.9,
        num_predict: int   = -1,
        stop:        Optional[List[str]] = None,
        **kwargs,
    ) -> str:
        """
        Submit an LLM task to the orchestrator and return a task_id.

        Falls back to the base-class behaviour (direct HTTP) if no
        orchestrator was configured.
        """
        if self._orchestrator is None:
            raise RuntimeError(
                "submit_llm() requires an orchestrator. "
                "Pass orchestrator= to OrchestratedOllamaManager()."
            )

        return self._orchestrator.submit_llm(
            prompt=prompt,
            model=model,
            stream=stream,
            temperature=temperature,
            top_k=top_k,
            top_p=top_p,
            num_predict=num_predict,
            stop=stop,
            **kwargs,
        )

    def stream_result(self, task_id: str, timeout: Optional[float] = None):
        """Pass-through to orchestrator.stream_result()."""
        if self._orchestrator is None:
            raise RuntimeError("No orchestrator configured.")
        return self._orchestrator.stream_result(task_id, timeout=timeout)

    def wait_for_result(self, task_id: str, timeout: Optional[float] = None):
        """Pass-through to orchestrator.wait_for_result()."""
        if self._orchestrator is None:
            raise RuntimeError("No orchestrator configured.")
        return self._orchestrator.wait_for_result(task_id, timeout=timeout)

    # ------------------------------------------------------------------ #
    # create_llm() — upgraded to use registry routing                     #
    # ------------------------------------------------------------------ #

    def create_llm(self, model: str, temperature: float = 0.7, **kwargs):
        """
        If an orchestrator is configured, produce a PooledOllamaLLM whose
        instance pool is driven by the RunnerRegistry rather than the
        internal OllamaInstancePool.

        Falls back to the base-class implementation when no orchestrator
        is present.
        """
        if self._orchestrator is None:
            return super().create_llm(model, temperature=temperature, **kwargs)

        # Normalise model name
        model_norm = model if ":" in model else f"{model}:latest"

        # Confirm at least one runner has the model
        runners = self._orchestrator.runner_registry.list_runners(
            has_model=model_norm, healthy_only=True
        )
        if not runners:
            # Refresh and retry
            for rid, caps in self._orchestrator.runner_registry._runners.items():
                self._orchestrator.runner_registry._probe_runner(rid)
            runners = self._orchestrator.runner_registry.list_runners(
                has_model=model_norm, healthy_only=True
            )

        if not runners:
            available = self._orchestrator.runner_registry.list_runners()
            all_models: Set[str] = set()
            for rid in available:
                caps = self._orchestrator.runner_registry.get(rid)
                if caps:
                    all_models.update(caps.loaded_models)

            raise ValueError(
                f"Model {model_norm!r} not found on any healthy runner. "
                f"Available models: {sorted(all_models)[:10]}"
            )

        # Use existing base-class LLM builder but override the pool with
        # a thin adapter so routing goes through the registry.
        llm = super().create_llm(model, temperature=temperature, **kwargs)

        # Inject registry-aware pool adapter
        llm.pool = _RegistryPoolAdapter(
            registry=self._orchestrator.runner_registry,
            gpu_runner_ids=set(self._orchestrator._gpu_runner_ids),
        )
        return llm

    # ------------------------------------------------------------------ #
    # Stats                                                                #
    # ------------------------------------------------------------------ #

    def get_pool_stats(self) -> Dict:
        base_stats = super().get_pool_stats()

        if self._orchestrator is not None:
            base_stats["runner_registry"] = (
                self._orchestrator.runner_registry.get_stats()
            )

        return base_stats


# ============================================================================
# _RegistryPoolAdapter
# ============================================================================

class _RegistryPoolAdapter:
    """
    Minimal shim that makes PooledOllamaLLM.pool work against the
    RunnerRegistry instead of OllamaInstancePool.

    Only the methods actually called by PooledOllamaLLM are implemented.
    """

    def __init__(
        self,
        registry:       RunnerRegistry,
        gpu_runner_ids: Optional[Set[str]] = None,
    ):
        self._registry       = registry
        self._gpu_runner_ids = gpu_runner_ids or set()

    # Expose a fake `instances` dict so PooledOllamaLLM attribute access works
    @property
    def instances(self) -> Dict[str, Any]:
        return {
            rid: _FakeInstance(
                api_url=caps.api_url,
                max_concurrent=caps.max_concurrent,
                priority=caps.priority,
            )
            for rid, caps in self._registry._runners.items()
        }

    # Expose a fake `stats` dict
    @property
    def stats(self) -> Dict[str, Any]:
        return {
            rid: _FakeStat(caps)
            for rid, caps in self._registry._runners.items()
        }

    def acquire_instance(
        self,
        timeout: float = 30.0,
        allowed_instances: Optional[List[str]] = None,
    ) -> Optional[tuple]:
        """Map PooledOllamaLLM's acquire_instance() to registry.acquire()."""
        acq = self._registry.acquire(
            allowed_runners=allowed_instances,
            strategy="least_loaded",
            timeout=timeout,
        )
        if acq is None:
            return None

        runner_id, caps, release = acq

        # PooledOllamaLLM expects (instance_name, instance_config, release_fn)
        return runner_id, _FakeInstance(
            api_url=caps.api_url,
            max_concurrent=caps.max_concurrent,
            priority=caps.priority,
        ), release


class _FakeInstance:
    """Minimal instance config object expected by PooledOllamaLLM."""
    def __init__(self, api_url: str, max_concurrent: int, priority: int):
        self.api_url        = api_url
        self.max_concurrent = max_concurrent
        self.priority       = priority


class _FakeStat:
    """Minimal stats object expected by PooledOllamaLLM."""
    def __init__(self, caps):
        self.active_requests = caps.active_requests
        self.total_requests  = caps.total_requests
        self.total_failures  = caps.total_failures
        self.total_duration  = caps.total_duration
        self.is_healthy      = caps.status.name in ("HEALTHY", "DEGRADED")

    def __setattr__(self, name, value):
        # Allow external code to update fields
        object.__setattr__(self, name, value)