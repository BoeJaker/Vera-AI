"""
Vera OllamaRunnerWorker
=======================
A specialised Worker subclass that is bound to a specific Ollama runner
(registered in RunnerRegistry) rather than being a generic thread.

Each worker knows:
  - Which runner it serves (runner_id → api_url via registry)
  - How to stream / non-stream from the Ollama API directly
  - How to acquire / release runner slots (not thread slots)
  - How to apply ThoughtCapture to streamed chunks
  - How to requeue a task on runner failure (with excluded_runners hint)

The existing Worker / WorkerPool infrastructure is preserved.
OllamaRunnerWorker replaces the generic Worker only for TaskType.LLM pools
when the orchestrator is started with runner-aware mode.
"""

import json
import queue
import threading
import time
import logging
import requests
from typing import Any, Dict, Iterator, List, Optional

# Re-use existing infrastructure from the main orchestrator module
from Vera.Orchestration.Registries.llm_registry import RunnerRegistry, RunnerStatus


class OllamaRunnerWorker(threading.Thread):
    """
    Worker thread bound to the RunnerRegistry.

    Unlike the generic Worker (which pulls a callable from TaskRegistry and
    runs it), OllamaRunnerWorker:
      1. Pulls an LLM task from the RunnerAwareTaskQueue
      2. Asks RunnerRegistry for a capable runner slot
      3. Makes the Ollama HTTP request directly (streaming or not)
      4. Processes thought-capture tags on the fly
      5. Feeds chunks into the TaskResult.stream_queue

    This means LLM task handlers registered in the TaskRegistry no longer
    need to do any HTTP work — they can be thin stubs (or omitted entirely
    when the runner-aware path is used).
    """

    # How long to wait for the queue before looping back
    QUEUE_POLL_INTERVAL = 1.0
    # Ollama HTTP timeout (seconds); 0 = no limit
    REQUEST_TIMEOUT = 2400

    def __init__(
        self,
        worker_id:       str,
        registry:        RunnerRegistry,
        task_queue,                         # RunnerAwareTaskQueue
        event_bus,                          # EventBus
        thought_capture_factory: Optional[callable] = None,
        gpu_runner_ids:  Optional[List[str]] = None,
        gpu_prefer_timeout: float = 45.0,
        default_acquire_timeout: float = 30.0,
        light_model_patterns: Optional[List[str]] = None,
        heavy_model_patterns: Optional[List[str]] = None,
    ):
        super().__init__(daemon=True, name=f"OllamaRunnerWorker-{worker_id}")
        self.worker_id   = worker_id
        self.registry    = registry
        self.task_queue  = task_queue
        self.event_bus   = event_bus
        self.thought_capture_factory = thought_capture_factory

        # Routing policy mirrors what was in MultiInstanceOllamaManager
        self.gpu_runner_ids          = set(gpu_runner_ids or [])
        self.gpu_prefer_timeout      = gpu_prefer_timeout
        self.default_acquire_timeout = default_acquire_timeout
        self.light_model_patterns    = [p.lower() for p in (light_model_patterns or [])]
        self.heavy_model_patterns    = [p.lower() for p in (heavy_model_patterns or [])]

        self.running      = False
        self.current_task: Optional[str] = None

        # Stats
        self.tasks_completed = 0
        self.tasks_failed    = 0
        self.total_duration  = 0.0

        self.logger = logging.getLogger(f"OllamaRunnerWorker-{worker_id}")

    # ------------------------------------------------------------------ #
    # Thread main loop                                                     #
    # ------------------------------------------------------------------ #

    def run(self):
        self.running = True
        self.logger.info(f"OllamaRunnerWorker {self.worker_id} started")

        while self.running:
            try:
                item = self.task_queue.get_next_llm_task(
                    timeout=self.QUEUE_POLL_INTERVAL
                )
                if item is None:
                    continue

                task_id, task_name, args, kwargs, metadata = item
                self.current_task = task_id
                self._handle_task(task_id, task_name, args, kwargs, metadata)
                self.current_task = None

            except Exception as exc:
                self.logger.error(
                    f"Unhandled error in worker loop: {exc}", exc_info=True
                )
                if self.current_task:
                    self.task_queue.mark_failed(self.current_task, str(exc))
                    self.current_task = None

        self.logger.info(
            f"OllamaRunnerWorker {self.worker_id} stopped "
            f"(completed={self.tasks_completed}, failed={self.tasks_failed})"
        )

    def stop(self):
        self.running = False

    # ------------------------------------------------------------------ #
    # Task handling                                                        #
    # ------------------------------------------------------------------ #

    def _handle_task(self, task_id, task_name, args, kwargs, metadata):
        """Acquire a runner, call Ollama, feed results into stream_queue."""
        started_at = time.time()

        # ── Pull the LLM parameters out of kwargs ──────────────────────
        prompt         = kwargs.get("prompt", args[0] if args else "")
        model          = kwargs.get("model", metadata.metadata.get("model", ""))
        temperature    = kwargs.get("temperature", 0.7)
        top_k          = kwargs.get("top_k", 40)
        top_p          = kwargs.get("top_p", 0.9)
        num_predict    = kwargs.get("num_predict", -1)
        stream         = kwargs.get("stream", True)
        stop_tokens    = kwargs.get("stop", None)
        extra_params   = kwargs.get("extra_params", {})

        # ── Mark task as running ───────────────────────────────────────
        with self.task_queue._lock:
            if task_id not in self.task_queue._pending:
                return
            result = self.task_queue._pending[task_id]
            result.started_at = started_at

        from vera_orchestration.orchestrator_patch import TaskStatus  # avoid circular
        result.status = TaskStatus.RUNNING

        self.event_bus.publish("task.started", {
            "task_id":    task_id,
            "task_name":  task_name,
            "worker_id":  self.worker_id,
            "started_at": started_at,
            "model":      model,
        })

        # ── Set up streaming result ────────────────────────────────────
        result.is_streaming  = True
        result.stream_queue  = queue.Queue()

        # ── Classify model → routing policy ───────────────────────────
        classification, acquire_timeout, gpu_preferred = self._classify_model(model)

        self.logger.info(
            f"Executing {task_name} [{classification.upper()}] "
            f"model={model!r} acquire_timeout={acquire_timeout}s"
        )

        # ── ThoughtCapture ─────────────────────────────────────────────
        thought_capture = None
        if self.thought_capture_factory:
            thought_capture = self.thought_capture_factory()

        # ── Try runners (with retry / failover) ────────────────────────
        tried: set = set()
        success    = False
        last_error: Optional[Exception] = None
        max_attempts = 3

        for attempt in range(1, max_attempts + 1):
            runner_acquisition = self._acquire_runner(
                model=model,
                classification=classification,
                acquire_timeout=acquire_timeout,
                gpu_preferred=gpu_preferred,
                excluded=tried,
            )

            if runner_acquisition is None:
                last_error = RuntimeError(
                    f"No runner available for model {model!r} "
                    f"(attempt {attempt}/{max_attempts})"
                )
                self.logger.warning(str(last_error))
                if attempt < max_attempts:
                    time.sleep(1.0)
                continue

            runner_id, caps, release = runner_acquisition
            tried.add(runner_id)

            try:
                if stream:
                    self._stream_from_runner(
                        runner_id=runner_id,
                        api_url=caps.api_url,
                        model=model,
                        prompt=prompt,
                        temperature=temperature,
                        top_k=top_k,
                        top_p=top_p,
                        num_predict=num_predict,
                        stop_tokens=stop_tokens,
                        extra_params=extra_params,
                        result=result,
                        thought_capture=thought_capture,
                    )
                else:
                    self._call_runner(
                        runner_id=runner_id,
                        api_url=caps.api_url,
                        model=model,
                        prompt=prompt,
                        temperature=temperature,
                        top_k=top_k,
                        top_p=top_p,
                        num_predict=num_predict,
                        stop_tokens=stop_tokens,
                        extra_params=extra_params,
                        result=result,
                        thought_capture=thought_capture,
                    )

                success = True
                break

            except Exception as exc:
                self.logger.warning(
                    f"Runner {runner_id!r} failed (attempt {attempt}): {exc}"
                )
                last_error = exc
                # Mark unhealthy so health-check loop picks it up
                caps.total_failures += 1
                if attempt < max_attempts:
                    time.sleep(0.5)
            finally:
                release()

        # ── Finalise result ────────────────────────────────────────────
        completed_at = time.time()
        duration     = completed_at - started_at

        if success:
            result.status       = TaskStatus.COMPLETED
            result.completed_at = completed_at
            result.worker_id    = self.worker_id
            self.tasks_completed += 1
            self.total_duration  += duration
            self.task_queue.mark_completed(task_id, result)

            self.event_bus.publish("task.completed", {
                "task_id":      task_id,
                "task_name":    task_name,
                "worker_id":    self.worker_id,
                "duration":     duration,
                "is_streaming": stream,
                "model":        model,
            })
            self.logger.info(f"✓ {task_name} completed in {duration:.2f}s")

        else:
            result.status       = TaskStatus.FAILED
            result.error        = str(last_error)
            result.completed_at = completed_at
            result.worker_id    = self.worker_id

            # Signal stream consumers that it's over
            if result.stream_queue:
                result.stream_queue.put(last_error or RuntimeError("Unknown failure"))

            self.tasks_failed += 1
            self.task_queue.mark_failed(task_id, str(last_error))

            self.event_bus.publish("task.failed", {
                "task_id":   task_id,
                "task_name": task_name,
                "worker_id": self.worker_id,
                "error":     str(last_error),
                "duration":  duration,
                "model":     model,
            })
            self.logger.error(f"✗ {task_name} failed after {duration:.2f}s: {last_error}")

    # ------------------------------------------------------------------ #
    # Ollama HTTP calls                                                    #
    # ------------------------------------------------------------------ #

    def _stream_from_runner(
        self,
        runner_id:      str,
        api_url:        str,
        model:          str,
        prompt:         str,
        temperature:    float,
        top_k:          int,
        top_p:          float,
        num_predict:    int,
        stop_tokens:    Optional[List[str]],
        extra_params:   Dict,
        result,
        thought_capture,
    ):
        """Stream chunks from Ollama into result.stream_queue."""
        payload = {
            "model":       model,
            "prompt":      prompt,
            "temperature": temperature,
            "top_k":       top_k,
            "top_p":       top_p,
            "num_predict": num_predict,
            "stream":      True,
            **extra_params,
        }
        if stop_tokens:
            payload["stop"] = stop_tokens

        url = f"{api_url}/api/generate"
        self.logger.debug(f"Streaming {model!r} from {runner_id!r}")

        collected: list = []
        chunk_count     = 0

        with requests.post(url, json=payload, stream=True,
                           timeout=self.REQUEST_TIMEOUT) as resp:
            resp.raise_for_status()

            for raw_line in resp.iter_lines():
                if not raw_line:
                    continue
                try:
                    data = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue

                # Apply thought capture if available
                if thought_capture:
                    text = thought_capture.process_chunk(data)
                else:
                    text = data.get("response", "")

                if text:
                    result.stream_queue.put(text)
                    collected.append(text)
                    chunk_count += 1

        # Signal end-of-stream
        result.stream_queue.put(StopIteration)
        result.result = "".join(collected)

        self.logger.debug(
            f"Stream complete: {chunk_count} chunks, "
            f"{len(result.result)} chars from {runner_id!r}"
        )

    def _call_runner(
        self,
        runner_id:    str,
        api_url:      str,
        model:        str,
        prompt:       str,
        temperature:  float,
        top_k:        int,
        top_p:        float,
        num_predict:  int,
        stop_tokens:  Optional[List[str]],
        extra_params: Dict,
        result,
        thought_capture,
    ):
        """Non-streaming call; wraps response in a single stream_queue item."""
        payload = {
            "model":       model,
            "prompt":      prompt,
            "temperature": temperature,
            "top_k":       top_k,
            "top_p":       top_p,
            "num_predict": num_predict,
            "stream":      False,
            **extra_params,
        }
        if stop_tokens:
            payload["stop"] = stop_tokens

        url = f"{api_url}/api/generate"
        self.logger.debug(f"Calling {model!r} on {runner_id!r} (non-streaming)")

        resp = requests.post(url, json=payload, timeout=self.REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        if thought_capture:
            text = thought_capture.process_chunk(data)
        else:
            text = data.get("response", "")

        result.result = text
        result.stream_queue.put(text)
        result.stream_queue.put(StopIteration)

        self.logger.debug(f"Non-stream complete: {len(text)} chars from {runner_id!r}")

    # ------------------------------------------------------------------ #
    # Model classification → routing                                       #
    # ------------------------------------------------------------------ #

    def _classify_model(self, model: str):
        """
        Returns (classification, acquire_timeout, gpu_preferred_runners).
        Mirrors _get_model_routing() from MultiInstanceOllamaManager but
        uses the RunnerRegistry's live data.
        """
        ml = model.lower()
        gpu_runners = list(self.gpu_runner_ids)
        cpu_runners = [
            rid for rid in self.registry.list_runners(has_model=model)
            if rid not in self.gpu_runner_ids
        ]

        # Light models → CPU only
        if any(p in ml for p in self.light_model_patterns):
            allowed = cpu_runners if cpu_runners else None   # None = any
            self.logger.debug(
                f"[routing] {model!r} → LIGHT (CPU-only, excluded GPU: {gpu_runners})"
            )
            return "light", self.default_acquire_timeout, None

        # Heavy models → GPU preferred, fall back to CPU
        if any(p in ml for p in self.heavy_model_patterns):
            self.logger.debug(
                f"[routing] {model!r} → HEAVY (GPU-preferred: {gpu_runners})"
            )
            return "heavy", self.gpu_prefer_timeout, gpu_runners or None

        # Normal → no special treatment
        return "normal", self.default_acquire_timeout, None

    def _acquire_runner(
        self,
        model:          str,
        classification: str,
        acquire_timeout: float,
        gpu_preferred:  Optional[List[str]],
        excluded:       set,
    ) -> Optional[tuple]:
        """
        Acquire a runner for the given model/classification.

        For HEAVY models, tries GPU runners first (60% of the timeout
        budget), then falls back to any runner with the model.
        """
        # All runners that have this model
        runners_with_model = self.registry.list_runners(has_model=model)

        if not runners_with_model:
            self.logger.warning(f"No runners have model {model!r}")
            return None

        if classification == "heavy" and gpu_preferred:
            gpu_timeout = acquire_timeout * 0.6
            cpu_timeout = acquire_timeout * 0.4

            # Phase 1: GPU
            gpu_candidates = [
                r for r in runners_with_model
                if r in gpu_preferred and r not in excluded
            ]
            if gpu_candidates:
                acq = self.registry.acquire(
                    model=model,
                    require_gpu=True,
                    allowed_runners=gpu_candidates,
                    excluded_runners=excluded,
                    strategy="least_loaded",
                    timeout=gpu_timeout,
                )
                if acq:
                    self.logger.info(
                        f"[heavy] Acquired GPU runner: {acq[0]!r}"
                    )
                    return acq
                self.logger.info(
                    f"[heavy] GPU runners busy, falling back to CPU "
                    f"({cpu_timeout:.1f}s remaining)"
                )

            # Phase 2: any runner with the model
            return self.registry.acquire(
                model=model,
                allowed_runners=[r for r in runners_with_model if r not in excluded],
                excluded_runners=excluded,
                strategy="least_loaded",
                timeout=cpu_timeout,
            )

        if classification == "light":
            # Exclude GPU runners if CPU alternatives exist
            non_gpu = [
                r for r in runners_with_model
                if r not in self.gpu_runner_ids and r not in excluded
            ]
            candidates = non_gpu if non_gpu else [
                r for r in runners_with_model if r not in excluded
            ]
            return self.registry.acquire(
                model=model,
                allowed_runners=candidates,
                excluded_runners=excluded,
                strategy="least_loaded",
                timeout=acquire_timeout,
            )

        # Normal
        return self.registry.acquire(
            model=model,
            allowed_runners=[r for r in runners_with_model if r not in excluded],
            excluded_runners=excluded,
            strategy="least_loaded",
            timeout=acquire_timeout,
        )