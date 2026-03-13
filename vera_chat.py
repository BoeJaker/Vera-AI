#!/usr/bin/env python3
# vera_chat.py - Streamlined Chat Module
"""
Vera Chat Module — Parallel Execution with tiered context injection.

Context strategy per stage
───────────────────────────────────────────────────────────────────
Stage           | Identity | Style | History | Vectors | Graph | Tools
──────────────  | ──────── | ────── | ─────── | ─────── | ───── | ─────
triage          |    ✗     |   ✗   |    ✗    |    ✗    |   ✗   |  ✓
preamble        |    ✓     |   ✓   |   4t    |  sess   |   ✗   |  ✗
general/simple  |    ✓     |   ✓   |   6t    |  sess   |   ✗   |  ✗
intermediate    |    ✓     |   ✓   |   6t    | sess+lt |   ✗   |  ✗
reasoning       |    ✓     |   ✓   |   8t    | sess+lt |   ✓   |  ✗
action/toolchain|    ✗     |   ✗   |   3t    |  sess   |   ✗   |  ✗  (agent has tools)
coding          |    ✓     |   ✓   |   4t    |    ✗    |   ✗   |  ✗
conclusion      |    ✗     |   ✗   |    ✗    |    ✗    |   ✗   |  ✗
"""

from typing import Optional, Dict, Any, Iterator
import threading
import queue
import time
from queue import Empty

from Vera.Logging.logging import LogContext
from Vera.context_builder import ContextBuilder


def extract_chunk_text(chunk):
    if hasattr(chunk, 'text'):
        return chunk.text
    elif hasattr(chunk, 'content'):
        return chunk.content
    elif isinstance(chunk, str):
        return chunk
    return str(chunk)


class VeraChat:
    def __init__(self, vera_instance):
        self.vera = vera_instance
        self.logger = vera_instance.logger
        self.ctx = ContextBuilder(vera_instance)

        self.ACTION_ROUTES = {
            "toolchain", "toolchain-parallel", "toolchain-adaptive",
            "toolchain-quick", "toolchain-stepbystep",
            "tool", "bash-agent", "python-agent",
            "scheduling-agent", "idea-agent", "toolchain-expert"
        }

    # ====================================================================
    # STREAM HELPER — per-chunk idle timeout
    # ====================================================================

    def _stream_with_idle_timeout(self, task_id: str, idle_timeout: float = 60.0,
                                   total_timeout: float = 600.0) -> Iterator[str]:
        """
        Stream result chunks from the orchestrator with a per-chunk idle timeout.

        idle_timeout  — max seconds to wait for the *next* chunk before giving up.
                        This prevents false positives from slow-starting models
                        while still catching genuinely stalled streams.
        total_timeout — hard cap for the entire stream regardless of activity.
        """
        result_queue: queue.Queue = queue.Queue()

        def producer():
            try:
                for chunk in self.vera.orchestrator.stream_result(task_id, timeout=total_timeout):
                    result_queue.put(("chunk", chunk))
                result_queue.put(("done", None))
            except Exception as e:
                result_queue.put(("error", e))

        t = threading.Thread(target=producer, daemon=True)
        t.start()

        wall_start = time.time()
        while True:
            if time.time() - wall_start > total_timeout:
                raise TimeoutError(f"stream_result: total timeout ({total_timeout}s) exceeded")
            try:
                event, payload = result_queue.get(timeout=idle_timeout)
            except Empty:
                raise TimeoutError(
                    f"stream_result: idle timeout ({idle_timeout}s) — no chunk received"
                )
            if event == "done":
                return
            elif event == "error":
                raise payload
            else:
                yield extract_chunk_text(payload)

    # ====================================================================
    # DIRECT ROUTING (forced by UI)
    # ====================================================================

    def _resolve_llm_for_override(self, override: str):
        role_map = {
            'fast':         lambda: self.vera.fast_llm,
            'intermediate': lambda: getattr(self.vera, 'intermediate_llm', self.vera.fast_llm),
            'deep':         lambda: self.vera.deep_llm,
            'reasoning':    lambda: self.vera.reasoning_llm,
        }
        return role_map.get(override, lambda: self.vera.fast_llm)()

    def execute_direct_route(self, query: str, routing_config: Dict, context: LogContext) -> Iterator[str]:
        mode           = routing_config.get('mode', 'simple')
        model_override = routing_config.get('model_override', '')

        self.logger.info(
            f"🎯 Direct routing to: {mode}"
            + (f" [model: {model_override}]" if model_override else ""),
            context=context,
        )

        # FIX: save query to memory before executing — was missing for direct routes
        if hasattr(self.vera, 'mem') and hasattr(self.vera, 'sess'):
            self.vera.mem.add_session_memory(
                self.vera.sess.id, query, "Query", {"topic": "plan"}, promote=True
            )

        def fallback_llm(default_role: str):
            role = model_override or default_role
            return self._resolve_llm_for_override(role)

        total_response = ""

        if mode in ('simple', 'fast'):
            prompt = self.ctx.build(query, stage="general")
            for chunk in self._stream_llm_task("llm.fast", query, prompt, context,
                                                idle_timeout=60.0, fallback=fallback_llm('fast')):
                yield chunk
                total_response += chunk

        elif mode == 'intermediate':
            prompt = self.ctx.build(query, stage="intermediate")
            for chunk in self._stream_llm_task("llm.generate", query, prompt, context,
                                                idle_timeout=45.0, fallback=fallback_llm('intermediate'),
                                                extra_kwargs={"llm_type": model_override or "intermediate"}):
                yield chunk
                total_response += chunk

        elif mode == 'reasoning':
            prompt = self.ctx.build(query, stage="reasoning")
            for chunk in self._stream_with_thoughts("llm.reasoning", prompt, context,
                                                     idle_timeout=60.0, fallback=fallback_llm('reasoning')):
                yield chunk
                total_response += chunk
            if total_response.strip():
                yield "\n\n--- Conclusion ---\n"
                total_response += "\n\n--- Conclusion ---\n"
                for chunk in self._generate_conclusion(query, total_response, context):
                    yield chunk
                    total_response += chunk

        elif mode == 'complex':
            prompt = self.ctx.build(query, stage="reasoning")
            for chunk in self._stream_with_thoughts("llm.deep", prompt, context,
                                                     idle_timeout=60.0, fallback=fallback_llm('deep')):
                yield chunk
                total_response += chunk
            if total_response.strip():
                yield "\n\n--- Conclusion ---\n"
                total_response += "\n\n--- Conclusion ---\n"
                for chunk in self._generate_conclusion(query, total_response, context):
                    yield chunk
                    total_response += chunk

        elif mode == 'coding':
            prompt = self.ctx.build(query, stage="coding")
            for chunk in self._stream_llm_task("llm.coding", query, prompt, context,
                                                idle_timeout=45.0, fallback=fallback_llm('fast')):
                yield chunk
                total_response += chunk

        elif mode in ('toolchain', 'toolchain-parallel', 'toolchain-adaptive', 'toolchain-stepbystep'):
            yield "\n\n--- Executing Toolchain ---\n"
            total_response += "\n\n--- Executing Toolchain ---\n"
            action_response = ""
            for chunk in self._run_toolchain(query, mode, context):
                yield chunk
                action_response += chunk
                total_response += chunk
            if action_response.strip():
                yield "\n\n--- Conclusion ---\n"
                total_response += "\n\n--- Conclusion ---\n"
                for chunk in self._generate_conclusion(query, action_response, context):
                    yield chunk
                    total_response += chunk

        elif mode == 'counsel' or mode.startswith('counsel-'):
            for chunk in self._execute_counsel_mode(
                query, context,
                counsel_mode=routing_config.get('counsel_mode', 'vote'),
                models=routing_config.get('models', ['fast', 'intermediate', 'deep']),
            ):
                yield chunk
                total_response += chunk

        else:
            self.logger.warning(f"Unknown routing mode '{mode}', defaulting to simple", context=context)
            yield from self.execute_direct_route(query, {'mode': 'simple'}, context)
            return  # memory already saved by recursive call

        if total_response:
            self.vera.save_to_memory(query, total_response)

    # ====================================================================
    # MAIN ENTRY POINT
    # ====================================================================

    def async_run(
        self,
        query: str,
        use_parallel: bool = True,
        ramp_config: Optional[Dict] = None,
        routing_hints: Optional[Dict] = None,
    ) -> Iterator[str]:

        query_context = LogContext(
            session_id=self.vera.sess.id,
            agent="async_run",
            extra={"query_length": len(query)}
        )

        self.logger.info(f"Processing query: {query[:100]}{'...' if len(query) > 100 else ''}", context=query_context)

        # Forced routing
        if routing_hints and routing_hints.get('force') and routing_hints.get('mode') != 'auto':
            self.logger.info(f"🎯 Forced routing to: {routing_hints['mode']}", context=query_context)
            yield from self.execute_direct_route(query, routing_hints, query_context)
            return

        self.logger.start_timer("total_query_processing")

        if hasattr(self.vera, 'mem') and hasattr(self.vera, 'sess'):
            self.vera.mem.add_session_memory(self.vera.sess.id, query, "Query", {"topic": "plan"}, promote=True)

        if not hasattr(self.vera, 'orchestrator') or not self.vera.orchestrator or not self.vera.orchestrator.running:
            self.logger.error("Orchestrator not running")
            yield "Error: Orchestrator not available. Please start the orchestrator."
            return

        full_triage, preamble_response, classification, total_response, complete = yield from self._parallel_execute(
            query, query_context, routing_hints
        )

        if hasattr(self.vera, 'mem') and hasattr(self.vera, 'sess'):
            self.vera.mem.add_session_memory(
                self.vera.sess.id, full_triage, "Triage", {"topic": "triage"}, promote=True
            )

        if complete:
            self.vera.save_to_memory(query, total_response)
            total_duration = self.logger.stop_timer("total_query_processing", context=query_context)
            self.logger.success(f"Query complete ({classification}): {len(total_response)} chars in {total_duration:.2f}s", context=query_context)
            return

        # ── Continuation routes ──────────────────────────────────────────
        route_context = LogContext(session_id=self.vera.sess.id, extra={"triage_result": classification})

        if "focus" in classification:
            yield from self._handle_focus_change(full_triage, route_context)
            total_response += "[Focus changed]"

        elif "adaptive" in classification:
            max_steps = 20
            try:
                task_id = self.vera.orchestrator.submit_task(
                    "toolchain.execute_adaptive", vera_instance=self.vera,
                    query=query, max_steps=max_steps
                )
                for chunk in self._stream_with_idle_timeout(task_id, idle_timeout=60.0, total_timeout=300.0):
                    yield chunk; total_response += chunk
            except Exception as e:
                self.logger.error(f"Adaptive toolchain failed: {e}", context=route_context)
                for chunk in self.vera.adaptive_toolchain.execute_adaptive(query, max_steps=max_steps):
                    c = extract_chunk_text(chunk); yield c; total_response += c

        elif classification == "proactive":
            yield from self._handle_proactive(route_context)
            total_response += "[Proactive thinking started]"

        elif "counsel" in classification or "coun" in classification:
            rh = routing_hints or {}
            yield from self._execute_counsel_mode(
                query, query_context,
                counsel_mode=rh.get('counsel_mode', 'vote'),
                models=rh.get('models', ['fast', 'intermediate', 'deep']),
                model_overrides=rh.get('model_overrides', {}),
            )

        elif classification == "reasoning":
            yield "\n\n"
            total_response += "\n\n"
            prompt = self.ctx.build(query, stage="reasoning", preamble=preamble_response)
            continuation = ""
            for chunk in self._execute_reasoning_continuation(query, prompt, route_context):
                yield chunk; total_response += chunk; continuation += chunk
            if continuation.strip():
                yield "\n\n--- Conclusion ---\n"
                total_response += "\n\n--- Conclusion ---\n"
                for chunk in self._generate_conclusion(query, total_response, query_context):
                    yield chunk; total_response += chunk

        elif classification == "complex":
            yield "\n\n"
            total_response += "\n\n"
            prompt = self.ctx.build(query, stage="reasoning", preamble=preamble_response)
            continuation = ""
            for chunk in self._execute_deep_continuation(query, prompt, route_context):
                yield chunk; total_response += chunk; continuation += chunk
            if continuation.strip():
                yield "\n\n--- Conclusion ---\n"
                total_response += "\n\n--- Conclusion ---\n"
                for chunk in self._generate_conclusion(query, total_response, query_context):
                    yield chunk; total_response += chunk

        elif classification == "intermediate":
            yield "\n\n"; total_response += "\n\n"
            prompt = self.ctx.build(query, stage="intermediate", preamble=preamble_response)
            for chunk in self._execute_intermediate_continuation(query, prompt, route_context):
                yield chunk; total_response += chunk

        elif classification == "coding":
            yield "\n\n"; total_response += "\n\n"
            for chunk in self._execute_coding(query):
                yield chunk; total_response += chunk

        if total_response:
            self.vera.save_to_memory(query, total_response)

        total_duration = self.logger.stop_timer("total_query_processing", context=query_context)
        self.logger.success(f"Query complete: {len(total_response)} chars in {total_duration:.2f}s", context=query_context)

    # ====================================================================
    # PARALLEL EXECUTION
    # ====================================================================

    def _parallel_execute(self, query: str, context: LogContext, routing_hints: Optional[Dict] = None) -> tuple:
        self.logger.info("🚀 Parallel execution: triage + preamble + action", context=context)

        triage_result   = queue.Queue()
        preamble_chunks = queue.Queue()
        action_chunks   = queue.Queue()
        stop_preamble   = threading.Event()
        action_start    = threading.Event()

        full_triage       = ""
        preamble_response = ""
        classification    = None
        action_started    = False

        # ── Triage thread ─────────────────────────────────────────────────
        def triage_worker():
            nonlocal full_triage, classification
            try:
                self.logger.start_timer("triage")
                # Triage only needs the raw query — no context, no history, no vectors.
                # Passing ctx.build() output here was making triage slow (60s+) because
                # it bloated the prompt with unnecessary context the classifier never uses.
                task_id = self.vera.orchestrator.submit_task(
                    "llm.triage", vera_instance=self.vera, query=query
                )
                for chunk in self._stream_with_idle_timeout(task_id, idle_timeout=60.0, total_timeout=80.0):
                    full_triage += chunk
                    if not classification and full_triage.strip():
                        classification = full_triage.strip().split()[0].lower()
                        triage_result.put(("classified", classification))
                        self.logger.info(f"🎯 Classification: {classification}")
                        if classification in self.ACTION_ROUTES:
                            stop_preamble.set()
                            action_start.set()
                self.logger.stop_timer("triage", context=context)
                triage_result.put(("complete", full_triage))
            except Exception as e:
                self.logger.error(f"Triage failed: {e}")
                triage_result.put(("error", str(e)))

        # ── Preamble thread ───────────────────────────────────────────────
        def preamble_worker():
            # NOTE: do NOT accumulate into preamble_response here.
            # The coordination loop is the single source of truth — it accumulates
            # preamble_response as it drains preamble_chunks. Accumulating in both
            # places caused the preamble to be doubled when returned to the caller.
            try:
                preamble_prompt = self.ctx.build(query, stage="preamble")
                task_id = self.vera.orchestrator.submit_task(
                    "llm.fast", vera_instance=self.vera, prompt=preamble_prompt
                )
                for chunk in self._stream_with_idle_timeout(task_id, idle_timeout=60.0, total_timeout=120.0):
                    if stop_preamble.is_set():
                        self.logger.info("⏹️ Preamble stopped — action route active")
                        break
                    preamble_chunks.put(chunk)
                preamble_chunks.put(None)
            except Exception as e:
                self.logger.error(f"Preamble failed: {e}")
                preamble_chunks.put(None)

        # ── Action thread ─────────────────────────────────────────────────
        def action_worker():
            action_start.wait()
            self.logger.info(f"🎬 Action worker started: {classification}")

            if not classification or classification not in self.ACTION_ROUTES:
                action_chunks.put(None)
                return

            # (task_name, kwargs, idle_timeout, total_timeout)
            task_config = {
                "toolchain":            ("toolchain.execute",          {},                  120.0, 600.0),
                "toolchain-parallel":   ("toolchain.execute.parallel", {},                   60.0,  90.0),
                "toolchain-adaptive":   ("toolchain.execute_adaptive", {},                   60.0, 300.0),
                "toolchain-quick":      ("toolchain.execute_adaptive", {"max_steps": 5},     60.0,  120.0),
                "toolchain-stepbystep": ("toolchain.execute_adaptive", {"max_steps": 10},    60.0, 180.0),
                "tool":                 ("toolchain.execute",          {},                  120.0, 600.0),
                "bash-agent":           ("agent.bash",                 {},                   60.0, 120.0),
                "python-agent":         ("agent.python",               {},                   60.0, 120.0),
                "scheduling-agent":     ("agent.scheduling",           {},                   60.0, 120.0),
                "idea-agent":           ("agent.idea",                 {},                   60.0, 120.0),
                "toolchain-expert":     ("toolchain.execute",          {},                  120.0, 600.0),
            }

            task_name, kwargs, idle_timeout, total_timeout = task_config.get(
                classification, ("toolchain.execute", {}, 120.0, 600.0)
            )

            self.logger.info(f"⚡ Executing {task_name} (idle={idle_timeout}s total={total_timeout}s)")
            try:
                task_id = self.vera.orchestrator.submit_task(
                    task_name, vera_instance=self.vera, query=query, **kwargs
                )
                chunk_count = 0
                for chunk in self._stream_with_idle_timeout(task_id, idle_timeout=idle_timeout,
                                                             total_timeout=total_timeout):
                    action_chunks.put(chunk)
                    chunk_count += 1
                self.logger.success(f"✓ Action complete: {chunk_count} chunks")
                action_chunks.put(None)

            except Exception as e:
                self.logger.error(f"❌ {task_name} failed: {e}")
                is_adaptive = classification in ("toolchain-adaptive", "toolchain-quick", "toolchain-stepbystep")
                try:
                    if is_adaptive and hasattr(self.vera, 'adaptive_toolchain'):
                        for chunk in self.vera.adaptive_toolchain.execute_adaptive(
                            query, max_steps=kwargs.get("max_steps", 20)
                        ):
                            action_chunks.put(extract_chunk_text(chunk))
                    else:
                        for chunk in self.vera.toolchain.execute_tool_chain(query):
                            action_chunks.put(extract_chunk_text(chunk))
                except Exception as e2:
                    action_chunks.put(f"\n[Error: {e2}]\n")
                action_chunks.put(None)

        # ── Start threads ─────────────────────────────────────────────────
        for t in [
            threading.Thread(target=triage_worker,   daemon=True),
            threading.Thread(target=preamble_worker, daemon=True),
            threading.Thread(target=action_worker,   daemon=True),
        ]:
            t.start()

        # ── Coordination loop ─────────────────────────────────────────────
        triage_done = preamble_done = action_done = False
        total_response = action_response = ""
        transition_added = False

        while not triage_done or not preamble_done or not action_done:

            try:
                event = triage_result.get_nowait()
                if event[0] == "classified":
                    classification = event[1]
                    if classification in self.ACTION_ROUTES:
                        action_started = True
                        if not transition_added:
                            yield "\n\n--- Executing ---\n"
                            total_response += "\n\n--- Executing ---\n"
                            transition_added = True
                elif event[0] == "complete":
                    full_triage = event[1]
                    classification = full_triage.strip().split()[0].lower()
                    classification = self._enhance_triage_classification(classification, query)
                    triage_done = True
                elif event[0] == "error":
                    full_triage = "simple"; classification = "simple"; triage_done = True
            except Empty:
                pass

            if not action_started:
                try:
                    chunk = preamble_chunks.get(timeout=0.01)
                    if chunk is None:
                        preamble_done = True
                    else:
                        yield chunk; total_response += chunk; preamble_response += chunk
                except Empty:
                    pass
            else:
                # Action is running — drain preamble queue without yielding,
                # but still accumulate so caller has the full preamble text.
                try:
                    chunk = preamble_chunks.get_nowait()
                    if chunk is None:
                        preamble_done = True
                    else:
                        preamble_response += chunk
                except Empty:
                    pass

            if action_started:
                try:
                    chunk = action_chunks.get(timeout=0.01)
                    if chunk is None:
                        action_done = True
                    else:
                        yield chunk; total_response += chunk; action_response += chunk
                except Empty:
                    pass
            else:
                if classification and classification not in self.ACTION_ROUTES and triage_done:
                    action_done = True

        if not classification:
            classification = "simple"

        # ── Determine completion ──────────────────────────────────────────
        if classification == "simple":
            streamed = preamble_response.strip()
            if not self._is_complete_response(streamed) and len(streamed) < 30:
                yield "\n"
                continuation_prompt = self.ctx.build(query, stage="continuation", preamble=preamble_response)
                for chunk in self._stream_llm_task(
                    "llm.fast", query, continuation_prompt,
                    LogContext(session_id=self.vera.sess.id),
                    idle_timeout=60.0, fallback=self.vera.fast_llm
                ):
                    yield chunk
                    total_response += chunk
                    preamble_response += chunk

            if hasattr(self.vera, 'mem') and hasattr(self.vera, 'sess'):
                self.vera.mem.add_session_memory(
                    self.vera.sess.id, total_response, "Response", {"topic": "response", "agent": "fast"}
                )
            return full_triage, preamble_response, classification, total_response, True

        elif classification in self.ACTION_ROUTES:
            if action_response.strip():
                yield "\n\n--- Conclusion ---\n"; total_response += "\n\n--- Conclusion ---\n"
                for chunk in self._generate_conclusion(query, action_response, context):
                    yield chunk; total_response += chunk

            if hasattr(self.vera, 'mem') and hasattr(self.vera, 'sess'):
                self.vera.mem.add_session_memory(
                    self.vera.sess.id, action_response, "Response",
                    {"topic": "response", "agent": classification}
                )
            return full_triage, preamble_response, classification, total_response, True

        else:
            self.logger.info(f"Preamble complete, continuing with {classification} route…")
            return full_triage, preamble_response, classification, total_response, False

    # ====================================================================
    # TRIAGE ENHANCEMENT
    # ====================================================================

    def _enhance_triage_classification(self, classification: str, query: str) -> str:
        if classification.startswith("toolchain-"):
            return classification
        if classification == "toolchain":
            if len(query.split()) < 10 and query.count("search") == 1:
                return "toolchain-quick"
            if self._detect_parallel_opportunity(query):
                return "toolchain-parallel"
            adaptive_keywords = [
                "research", "analyze", "create report", "investigate",
                "debug and fix", "optimize", "refactor", "comprehensive",
                "step by step", "step-by-step", "iteratively",
            ]
            if any(kw in query.lower() for kw in adaptive_keywords):
                return "toolchain-adaptive"
        return classification

    def _detect_parallel_opportunity(self, query: str) -> bool:
        import re
        patterns = [
            r'\bvs\b', r'\bversus\b', r'\bcompare\b', r'\bdifference between\b',
            r'\beach\b', r'\ball\b', r'\bboth\b', r'\bmultiple\b',
            r'\bsimultaneously\b', r'\bin parallel\b', r'\bat once\b',
        ]
        q = query.lower()
        return any(re.search(p, q) for p in patterns)

    # ====================================================================
    # CONTINUATION ROUTES
    # ====================================================================

    def _execute_intermediate_continuation(self, query: str, prompt: str, context: LogContext) -> Iterator[str]:
        self.logger.start_timer("intermediate_continuation")
        response = ""
        try:
            task_id = self.vera.orchestrator.submit_task("llm.intermediate", vera_instance=self.vera, prompt=prompt)
            for chunk in self._stream_with_idle_timeout(task_id, idle_timeout=45.0, total_timeout=120.0):
                response += chunk; yield chunk
        except Exception as e:
            self.logger.error(f"Intermediate failed: {e}")
            for chunk in self.vera.stream_llm(self.vera.intermediate_llm, prompt):
                c = extract_chunk_text(chunk); response += c; yield c
        duration = self.logger.stop_timer("intermediate_continuation", context=context)
        self._save_response(response, "intermediate", duration)

    def _execute_reasoning_continuation(self, query: str, prompt: str, context: LogContext) -> Iterator[str]:
        self.logger.start_timer("reasoning_continuation")
        response = ""
        try:
            task_id = self.vera.orchestrator.submit_task("llm.reasoning", vera_instance=self.vera, prompt=prompt)
            for chunk in self._stream_orchestrator_with_thoughts(task_id, idle_timeout=60.0, total_timeout=180.0):
                response += chunk; yield chunk
        except Exception as e:
            self.logger.error(f"Reasoning failed: {e}")
            for chunk in self.vera.stream_llm(self.vera.reasoning_llm, prompt):
                c = extract_chunk_text(chunk); response += c; yield c
        duration = self.logger.stop_timer("reasoning_continuation", context=context)
        self._save_response(response, "reasoning", duration)

    def _execute_deep_continuation(self, query: str, prompt: str, context: LogContext) -> Iterator[str]:
        self.logger.start_timer("deep_continuation")
        response = ""
        try:
            task_id = self.vera.orchestrator.submit_task("llm.deep", vera_instance=self.vera, prompt=prompt)
            for chunk in self._stream_orchestrator_with_thoughts(task_id, idle_timeout=60.0, total_timeout=180.0):
                response += chunk; yield chunk
        except Exception as e:
            self.logger.error(f"Deep failed: {e}")
            for chunk in self.vera.stream_llm(self.vera.deep_llm, prompt):
                c = extract_chunk_text(chunk); response += c; yield c
        duration = self.logger.stop_timer("deep_continuation", context=context)
        self._save_response(response, "deep", duration)

    def _execute_coding(self, query: str) -> Iterator[str]:
        prompt = self.ctx.build(query, stage="coding")
        try:
            task_id = self.vera.orchestrator.submit_task("llm.coding", vera_instance=self.vera, prompt=prompt)
            for chunk in self._stream_with_idle_timeout(task_id, idle_timeout=45.0, total_timeout=120.0):
                yield chunk
        except Exception:
            for chunk in self.vera.stream_llm(self.vera.fast_llm, prompt):
                yield extract_chunk_text(chunk)

    # ====================================================================
    # HELPERS
    # ====================================================================

    def _run_toolchain(self, query: str, mode: str, context: LogContext) -> Iterator[str]:
        task_map = {
            'toolchain':            ('toolchain.execute',          {},               120.0, 600.0),
            'toolchain-parallel':   ('toolchain.execute.parallel', {},                60.0,  90.0),
            'toolchain-adaptive':   ('toolchain.execute_adaptive', {},                60.0, 300.0),
            'toolchain-stepbystep': ('toolchain.execute_adaptive', {'max_steps':10},  60.0, 180.0),
        }
        task_name, kwargs, idle_timeout, total_timeout = task_map.get(
            mode, ('toolchain.execute', {}, 120.0, 600.0)
        )
        try:
            task_id = self.vera.orchestrator.submit_task(task_name, vera_instance=self.vera, query=query, **kwargs)
            for chunk in self._stream_with_idle_timeout(task_id, idle_timeout=idle_timeout,
                                                         total_timeout=total_timeout):
                yield chunk
        except Exception as e:
            self.logger.error(f"Toolchain {mode} failed: {e}", context=context)
            if 'adaptive' in mode:
                for chunk in self.vera.adaptive_toolchain.execute_adaptive(query):
                    yield extract_chunk_text(chunk)
            else:
                for chunk in self.vera.toolchain.execute_tool_chain(query):
                    yield extract_chunk_text(chunk)

    def _stream_llm_task(
        self, task_name: str, query: str, prompt: str, context: LogContext,
        idle_timeout: float, fallback, extra_kwargs: dict = None
    ) -> Iterator[str]:
        """Submit an LLM task and stream with per-chunk idle timeout."""
        try:
            kwargs = {"vera_instance": self.vera, "prompt": prompt}
            if extra_kwargs:
                kwargs.update(extra_kwargs)
            task_id = self.vera.orchestrator.submit_task(task_name, **kwargs)
            for chunk in self._stream_with_idle_timeout(task_id, idle_timeout=idle_timeout,
                                                         total_timeout=idle_timeout * 20):
                yield chunk
        except Exception as e:
            self.logger.error(f"{task_name} failed: {e}", context=context)
            for chunk in self.vera.stream_llm(fallback, prompt):
                yield extract_chunk_text(chunk)

    def _stream_with_thoughts(
        self, task_name: str, prompt: str, context: LogContext,
        idle_timeout: float, fallback
    ) -> Iterator[str]:
        try:
            task_id = self.vera.orchestrator.submit_task(task_name, vera_instance=self.vera, prompt=prompt)
            for chunk in self._stream_orchestrator_with_thoughts(task_id, idle_timeout=idle_timeout,
                                                                  total_timeout=idle_timeout * 10):
                yield chunk
        except Exception as e:
            self.logger.error(f"{task_name} failed: {e}", context=context)
            for chunk in self.vera.stream_llm(fallback, prompt):
                yield extract_chunk_text(chunk)

    def _generate_conclusion(self, query: str, total_response: str, context: LogContext) -> Iterator[str]:
        prompt = self.ctx.build(query, stage="conclusion", preamble=total_response)
        yield from self._stream_llm_task("llm.fast", query, prompt, context,
                                          idle_timeout=60.0, fallback=self.vera.fast_llm)

    def _handle_focus_change(self, full_triage: str, context: LogContext) -> Iterator[str]:
        if hasattr(self.vera, 'focus_manager'):
            new_focus = full_triage.lower().split("focus:", 1)[-1].strip()
            self.vera.focus_manager.set_focus(new_focus)
            yield f"\n✓ Focus changed to: {self.vera.focus_manager.focus}\n"

    def _handle_proactive(self, context: LogContext) -> Iterator[str]:
        try:
            self.vera.orchestrator.submit_task("proactive.generate_thought", vera_instance=self.vera)
            yield "\n[Proactive thought generation started]\n"
        except Exception as e:
            self.logger.error(f"Proactive task failed: {e}")
            yield "\n[Proactive thinking unavailable]\n"

    def _execute_counsel_mode(
        self,
        query: str,
        context: LogContext,
        counsel_mode: str = 'vote',
        models: list = None,
        model_overrides: dict = None,
    ) -> Iterator[str]:
        from Vera.vera_counsel import CounselExecutor
        executor = CounselExecutor(self.vera, self.logger)
        yield from executor.execute(
            query=query,
            mode=counsel_mode,
            models=models or ['fast', 'intermediate', 'deep'],
            model_overrides=model_overrides or {},
            context=context,
        )

    def _save_response(self, response: str, agent: str, duration: float):
        if response and hasattr(self.vera, 'mem') and hasattr(self.vera, 'sess'):
            self.vera.mem.add_session_memory(
                self.vera.sess.id, response, "Response",
                {"topic": "response", "agent": agent, "duration": duration}
            )

    def _is_complete_response(self, text: str) -> bool:
        text = text.strip()
        return len(text) > 50 and text[-1] in '.!?'

    def _stream_orchestrator_with_thoughts(self, task_id: str,
                                            idle_timeout: float = 60.0,
                                            total_timeout: float = 300.0) -> Iterator[str]:
        """
        Stream chunks from the orchestrator interleaved with any <thought> content,
        using per-chunk idle timeout via _stream_with_idle_timeout.
        """
        last_check = time.time()
        in_thought = False
        for chunk in self._stream_with_idle_timeout(task_id, idle_timeout=idle_timeout,
                                                     total_timeout=total_timeout):
            if time.time() - last_check > 0.05:
                try:
                    while True:
                        thought_chunk = self.vera.thought_queue.get_nowait()
                        if not in_thought:
                            yield "\n<thought>"; in_thought = True
                        yield thought_chunk
                except Empty:
                    pass
                last_check = time.time()
            if in_thought:
                yield "</thought>\n"; in_thought = False
            yield chunk
        try:
            while True:
                thought_chunk = self.vera.thought_queue.get_nowait()
                if not in_thought:
                    yield "\n<thought>"; in_thought = True
                yield thought_chunk
        except Empty:
            pass
        if in_thought:
            yield "</thought>\n"