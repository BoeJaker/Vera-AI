"""
Vera Orchestrator Patch — Runner-Aware Extensions
==================================================
Drop-in additions to the existing orchestrator.py.

Provides:
  RunnerAwareTaskQueue  — extends TaskQueue with a dedicated LLM lane
                          that OllamaRunnerWorker drains
  RunnerAwareOrchestrator — extends Orchestrator; registers Ollama
                            instances into RunnerRegistry and stands up
                            OllamaRunnerWorker threads for the LLM pool
  TaskStatus re-export  — so ollama_runner_worker.py can import it here
                          without a circular dependency

Backward compatibility
----------------------
All existing call-sites (submit_task, wait_for_result, stream_result,
get_stats, scale_pool) work unchanged.  The only new behaviour is that
TaskType.LLM tasks are routed through OllamaRunnerWorker → RunnerRegistry
instead of the generic Worker → TaskRegistry path.
"""

import threading
import time
import logging
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple

# ── Re-export so ollama_runner_worker avoids a circular import ──
from enum import auto
from enum import Enum as _Enum

class TaskStatus(_Enum):
    PENDING   = auto()
    QUEUED    = auto()
    RUNNING   = auto()
    COMPLETED = auto()
    FAILED    = auto()
    CANCELLED = auto()


# ── Core orchestration types (from the original module) ──────────────
# We import only what we need to avoid pulling in everything.

from Vera.Orchestration.orchestration import (
    TaskType, Priority, TaskMetadata, TaskResult,
    TaskQueue, WorkerPool, EventBus, Orchestrator,
    registry as global_registry,
)


from Vera.Orchestration.Registries.llm_registry import RunnerRegistry, RunnerCapabilities
from Vera.Orchestration.Workers.llm_runner_worker import OllamaRunnerWorker


# ============================================================================
# RunnerAwareTaskQueue
# ============================================================================

class RunnerAwareTaskQueue(TaskQueue):
    """
    Extends TaskQueue with a dedicated LLM task lane.

    OllamaRunnerWorker threads call get_next_llm_task() rather than the
    generic get_next().  All other task types (TOOL, BACKGROUND, …) continue
    to use get_next() and the existing Worker machinery unchanged.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Dedicated FIFO for LLM tasks consumed by OllamaRunnerWorkers
        self._llm_queue: List[Tuple] = []
        self._llm_condition = threading.Condition(self._lock)
        self.llm_logger = logging.getLogger("RunnerAwareTaskQueue.LLM")

    def submit(self, task_name: str, *args, **kwargs) -> str:
        """
        Override: LLM tasks go into the dedicated LLM lane; everything
        else falls through to the parent implementation.
        """
        import uuid, time as _time

        meta_template = global_registry.get_metadata(task_name)
        if not meta_template:
            # No registered template means it's a direct LLM call submitted
            # via submit_llm_task() — those bypass this method.
            return super().submit(task_name, *args, **kwargs)

        if meta_template.task_type != TaskType.LLM:
            return super().submit(task_name, *args, **kwargs)

        # ── LLM task: enqueue in the dedicated lane ──────────────────
        task_id    = str(uuid.uuid4())
        created_at = _time.time()

        metadata = TaskMetadata(
            task_id=task_id,
            task_type=meta_template.task_type,
            priority=meta_template.priority,
            created_at=created_at,
            estimated_duration=meta_template.estimated_duration,
            max_retries=meta_template.max_retries,
            timeout=meta_template.timeout,
            requires_gpu=meta_template.requires_gpu,
            requires_cpu_cores=meta_template.requires_cpu_cores,
            memory_mb=meta_template.memory_mb,
            focus_context=kwargs.pop("focus_context", None),
            labels=meta_template.labels.copy(),
            metadata=meta_template.metadata.copy(),
        )

        with self._llm_condition:
            self._llm_queue.append(
                (metadata.priority, created_at, task_id, task_name, args, kwargs, metadata)
            )
            self._llm_queue.sort(key=lambda x: (x[0].value, x[1]))

            with self._lock:
                self._pending[task_id] = TaskResult(
                    task_id=task_id, status=TaskStatus.QUEUED
                )

            self._llm_condition.notify_all()

        self.llm_logger.info(
            f"LLM task queued: {task_name} ({task_id[:8]}…) "
            f"[{metadata.priority.name}] "
            f"pos={len(self._llm_queue)}"
        )
        return task_id

    def submit_llm_task(
        self,
        task_id:    str,
        task_name:  str,
        args:       tuple,
        kwargs:     dict,
        metadata:   TaskMetadata,
    ):
        """
        Low-level entry point used by RunnerAwareOrchestrator.submit_llm()
        when bypassing the TaskRegistry entirely.
        """
        import time as _time

        with self._llm_condition:
            self._llm_queue.append(
                (metadata.priority, _time.time(), task_id, task_name, args, kwargs, metadata)
            )
            self._llm_queue.sort(key=lambda x: (x[0].value, x[1]))

            with self._lock:
                self._pending[task_id] = TaskResult(
                    task_id=task_id, status=TaskStatus.QUEUED
                )

            self._llm_condition.notify_all()

        self.llm_logger.info(
            f"LLM task enqueued directly: {task_name} ({task_id[:8]}…)"
        )

    def get_next_llm_task(self, timeout: float = 1.0) -> Optional[Tuple]:
        """
        Called by OllamaRunnerWorker to dequeue the next LLM task.
        Blocks for up to `timeout` seconds.
        """
        with self._llm_condition:
            if not self._llm_queue:
                self._llm_condition.wait(timeout=timeout)

            if not self._llm_queue:
                return None

            priority, created_at, task_id, task_name, args, kwargs, metadata = \
                self._llm_queue.pop(0)

            wait_time = time.time() - created_at
            self.llm_logger.debug(
                f"Dequeued LLM: {task_name} ({task_id[:8]}…) "
                f"wait={wait_time:.3f}s remaining={len(self._llm_queue)}"
            )

            with self._lock:
                if task_id in self._pending:
                    self._pending[task_id].status = TaskStatus.RUNNING

            return task_id, task_name, args, kwargs, metadata

    def get_queue_sizes(self) -> Dict[str, int]:
        sizes = super().get_queue_sizes()
        with self._llm_condition:
            sizes["llm_runner_queue"] = len(self._llm_queue)
        return sizes


# ============================================================================
# RunnerAwareOrchestrator
# ============================================================================

class RunnerAwareOrchestrator(Orchestrator):
    """
    Drop-in replacement for Orchestrator that adds:

    1. A shared RunnerRegistry (started automatically)
    2. register_ollama_instance() / deregister_runner() helpers
    3. OllamaRunnerWorker threads replace the generic LLM WorkerPool
    4. submit_llm() — convenience method for direct LLM task submission
       without needing a TaskRegistry entry
    5. get_runner_stats() — live runner health / load snapshot
    6. All existing methods (submit_task, wait_for_result, stream_result,
       scale_pool, get_stats) still work unchanged.
    """

    def __init__(
        self,
        *args,
        # RunnerRegistry / LLM worker config
        runner_registry:         Optional[RunnerRegistry] = None,
        num_llm_workers:         int   = 4,     # OllamaRunnerWorker threads
        gpu_runner_ids:          Optional[List[str]] = None,
        gpu_prefer_timeout:      float = 45.0,
        default_acquire_timeout: float = 30.0,
        light_model_patterns:    Optional[List[str]] = None,
        heavy_model_patterns:    Optional[List[str]] = None,
        thought_capture_factory: Optional[callable] = None,
        **kwargs,
    ):
        # Remove LLM from the generic worker config so the parent doesn't
        # create generic Worker threads for it.
        config = kwargs.pop("config", None) or args[0] if args else {}
        if isinstance(config, dict):
            config.pop(TaskType.LLM, None)
        else:
            config = {
                TaskType.WHISPER:    1,
                TaskType.TOOL:       4,
                TaskType.ML_MODEL:   1,
                TaskType.BACKGROUND: 2,
                TaskType.GENERAL:    2,
            }

        super().__init__(config=config, **kwargs)

        # Swap in our runner-aware queue
        self.task_queue = RunnerAwareTaskQueue(
            cpu_threshold=kwargs.get("cpu_threshold", 85.0)
        )

        # Runner registry
        self.runner_registry = runner_registry or RunnerRegistry(
            event_bus=self.event_bus
        )

        # LLM worker config
        self._num_llm_workers         = num_llm_workers
        self._gpu_runner_ids          = gpu_runner_ids or []
        self._gpu_prefer_timeout      = gpu_prefer_timeout
        self._default_acquire_timeout = default_acquire_timeout
        self._light_model_patterns    = light_model_patterns or [
            "gemma2", "nomic-embed", "triage-agent", "fast.llm",
        ]
        self._heavy_model_patterns    = heavy_model_patterns or [
            "mistral", "codestral", "deepseek-r1", "qwen", "llama3",
            "gpt-oss", "gemma3",
        ]
        self._thought_capture_factory = thought_capture_factory
        self._llm_workers: List[OllamaRunnerWorker] = []

        self.logger = logging.getLogger("RunnerAwareOrchestrator")

    # ------------------------------------------------------------------ #
    # Lifecycle                                                            #
    # ------------------------------------------------------------------ #

    def start(self):
        """Start the orchestrator, registry, and LLM workers."""
        super().start()

        self.runner_registry.start()

        # Subscribe to runner events
        self.runner_registry.on("runner.unavailable", self._on_runner_unavailable)
        self.runner_registry.on("runner.recovered",   self._on_runner_recovered)

        # Start OllamaRunnerWorker threads
        for i in range(self._num_llm_workers):
            worker = OllamaRunnerWorker(
                worker_id=f"llm-{i}",
                registry=self.runner_registry,
                task_queue=self.task_queue,
                event_bus=self.event_bus,
                thought_capture_factory=self._thought_capture_factory,
                gpu_runner_ids=self._gpu_runner_ids,
                gpu_prefer_timeout=self._gpu_prefer_timeout,
                default_acquire_timeout=self._default_acquire_timeout,
                light_model_patterns=self._light_model_patterns,
                heavy_model_patterns=self._heavy_model_patterns,
            )
            worker.start()
            self._llm_workers.append(worker)

        self.logger.info(
            f"RunnerAwareOrchestrator started "
            f"({self._num_llm_workers} LLM workers, "
            f"{len(self._gpu_runner_ids)} GPU runners configured)"
        )

    def stop(self):
        """Stop everything cleanly."""
        for w in self._llm_workers:
            w.stop()
        for w in self._llm_workers:
            w.join(timeout=5.0)
        self._llm_workers.clear()

        self.runner_registry.stop()
        super().stop()
        self.logger.info("RunnerAwareOrchestrator stopped")

    # ------------------------------------------------------------------ #
    # Runner management                                                    #
    # ------------------------------------------------------------------ #

    def register_ollama_instance(
        self,
        name:           str,
        api_url:        str,
        *,
        gpu:            bool = False,
        max_concurrent: int  = 2,
        priority:       int  = 0,
        tags:           Optional[Set[str]] = None,
        probe:          bool = True,
    ) -> RunnerCapabilities:
        """
        Register an Ollama instance as a runner.

        This is the primary way MultiInstanceOllamaManager (or any other
        caller) adds instances to the orchestrator.  Safe to call at any
        time — the registry handles duplicates gracefully.
        """
        caps = self.runner_registry.register(
            runner_id=name,
            api_url=api_url,
            gpu=gpu,
            max_concurrent=max_concurrent,
            priority=priority,
            tags=tags or set(),
            probe=probe,
        )

        # Track GPU runners for routing
        if gpu and name not in self._gpu_runner_ids:
            self._gpu_runner_ids.append(name)
            # Update all existing workers
            for w in self._llm_workers:
                w.gpu_runner_ids.add(name)

        self.logger.info(
            f"Ollama instance registered: {name!r} @ {api_url} "
            f"(gpu={gpu}, priority={priority})"
        )
        return caps

    def deregister_runner(self, name: str, drain: bool = True):
        """Remove a runner from the registry."""
        self.runner_registry.deregister(name, drain=drain)
        if name in self._gpu_runner_ids:
            self._gpu_runner_ids.remove(name)
            for w in self._llm_workers:
                w.gpu_runner_ids.discard(name)
        self.logger.info(f"Runner deregistered: {name!r}")

    # ------------------------------------------------------------------ #
    # Task submission helpers                                              #
    # ------------------------------------------------------------------ #

    def submit_llm(
        self,
        prompt:       str,
        model:        str,
        *,
        temperature:  float = 0.7,
        top_k:        int   = 40,
        top_p:        float = 0.9,
        num_predict:  int   = -1,
        stream:       bool  = True,
        stop:         Optional[List[str]] = None,
        priority:     Priority = Priority.NORMAL,
        focus_context: Optional[str] = None,
        **extra_params,
    ) -> str:
        """
        Submit an LLM generation task directly — no TaskRegistry entry needed.

        Returns a task_id that can be passed to stream_result() or
        wait_for_result() exactly like any other task.

        Usage
        -----
            task_id = orchestrator.submit_llm(
                prompt="Explain quantum entanglement",
                model="mistral:latest",
                stream=True,
            )
            for chunk in orchestrator.stream_result(task_id):
                print(chunk, end="", flush=True)
        """
        import uuid, time as _time

        task_id    = str(uuid.uuid4())
        task_name  = f"llm.generate/{model}"

        metadata = TaskMetadata(
            task_id=task_id,
            task_type=TaskType.LLM,
            priority=priority,
            created_at=_time.time(),
            estimated_duration=30.0,
            focus_context=focus_context,
            metadata={"model": model},
        )

        kwargs = dict(
            prompt=prompt,
            model=model,
            temperature=temperature,
            top_k=top_k,
            top_p=top_p,
            num_predict=num_predict,
            stream=stream,
            stop=stop,
            extra_params=extra_params,
        )

        self.task_queue.submit_llm_task(
            task_id=task_id,
            task_name=task_name,
            args=(),
            kwargs=kwargs,
            metadata=metadata,
        )

        self.logger.debug(
            f"LLM task submitted: {task_id[:8]}… model={model!r} "
            f"prompt_len={len(prompt)}"
        )
        return task_id

    # ------------------------------------------------------------------ #
    # Stats                                                                #
    # ------------------------------------------------------------------ #

    def get_stats(self) -> Dict[str, Any]:
        """Extends parent stats with runner registry data."""
        stats = super().get_stats()

        stats["runner_registry"] = self.runner_registry.get_stats()
        stats["llm_workers"] = [
            {
                "worker_id":        w.worker_id,
                "tasks_completed":  w.tasks_completed,
                "tasks_failed":     w.tasks_failed,
                "total_duration":   round(w.total_duration, 2),
                "current_task":     w.current_task,
                "alive":            w.is_alive(),
            }
            for w in self._llm_workers
        ]
        return stats

    def get_runner_stats(self) -> Dict[str, Dict]:
        """Shortcut to the live runner stats snapshot."""
        return self.runner_registry.get_stats()

    # ------------------------------------------------------------------ #
    # Scaling                                                              #
    # ------------------------------------------------------------------ #

    def scale_llm_workers(self, n: int):
        """
        Dynamically adjust the number of OllamaRunnerWorker threads.
        """
        current = len(self._llm_workers)

        if n > current:
            for i in range(current, n):
                w = OllamaRunnerWorker(
                    worker_id=f"llm-{i}",
                    registry=self.runner_registry,
                    task_queue=self.task_queue,
                    event_bus=self.event_bus,
                    thought_capture_factory=self._thought_capture_factory,
                    gpu_runner_ids=self._gpu_runner_ids,
                    gpu_prefer_timeout=self._gpu_prefer_timeout,
                    default_acquire_timeout=self._default_acquire_timeout,
                    light_model_patterns=self._light_model_patterns,
                    heavy_model_patterns=self._heavy_model_patterns,
                )
                w.start()
                self._llm_workers.append(w)
            self.logger.info(f"LLM workers scaled up: {current} → {n}")

        elif n < current:
            to_stop = self._llm_workers[n:]
            self._llm_workers = self._llm_workers[:n]
            for w in to_stop:
                w.stop()
            for w in to_stop:
                w.join(timeout=5.0)
            self.logger.info(f"LLM workers scaled down: {current} → {n}")

    # ------------------------------------------------------------------ #
    # Event handlers                                                       #
    # ------------------------------------------------------------------ #

    def _on_runner_unavailable(self, runner_id: str, caps: RunnerCapabilities):
        self.logger.warning(
            f"Runner {runner_id!r} went offline — "
            f"in-flight tasks will be retried on other runners"
        )
        self.event_bus.publish("runner.unavailable", {
            "runner_id": runner_id,
            "api_url":   caps.api_url,
        })

    def _on_runner_recovered(self, runner_id: str, caps: RunnerCapabilities):
        self.logger.info(f"Runner {runner_id!r} recovered")
        self.event_bus.publish("runner.recovered", {
            "runner_id": runner_id,
            "api_url":   caps.api_url,
            "models":    sorted(caps.loaded_models),
        })