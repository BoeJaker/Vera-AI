#!/usr/bin/env python3
# vera_chat.py - Streamlined Chat Module

"""
Vera Chat Module - Parallel Execution Only

KEY FEATURES:
- Triage and preamble ALWAYS run in parallel
- Toolchain/actions execute IMMEDIATELY upon classification
- Preamble stops gracefully when action route takes over
- Clean continuation paths for reasoning/complex/intermediate
"""

from typing import Optional, Dict, Any, Iterator
import threading
import queue
from queue import Empty

from Vera.Logging.logging import LogContext


def extract_chunk_text(chunk):
    """Extract text from chunk object"""
    if hasattr(chunk, 'text'):
        return chunk.text
    elif hasattr(chunk, 'content'):
        return chunk.content
    elif isinstance(chunk, str):
        return chunk
    else:
        return str(chunk)


class VeraChat:
    """Handles all chat/query processing logic for Vera"""
    
    def __init__(self, vera_instance):
        self.vera = vera_instance
        self.logger = vera_instance.logger
        
        # Action routes that interrupt preamble
        self.ACTION_ROUTES = {
            "toolchain", "toolchain-parallel", "toolchain-adaptive", 
            "toolchain-quick", "toolchain-stepbystep",
            "tool", "bash-agent", "python-agent", 
            "scheduling-agent", "idea-agent", "toolchain-expert"
        }
    
    def execute_direct_route(self, query: str, routing_config: Dict, context: LogContext) -> Iterator[str]:
        """Execute query with forced routing, bypassing triage"""
        mode = routing_config.get('mode', 'simple')
        
        self.logger.info(f"🎯 Direct routing to: {mode}", context=context)
        
        # Map UI mode names to execution methods
        if mode == 'simple' or mode == 'fast':
            self.logger.info("Executing simple/fast mode", context=context)
            try:
                task_id = self.vera.orchestrator.submit_task(
                    "llm.fast",
                    vera_instance=self.vera,
                    prompt=query
                )
                
                for chunk in self.vera.orchestrator.stream_result(task_id, timeout=30.0):
                    chunk_text = extract_chunk_text(chunk)
                    yield chunk_text
            
            except Exception as e:
                self.logger.error(f"Fast LLM failed: {e}", context=context)
                for chunk in self.vera.stream_llm(self.vera.fast_llm, query):
                    chunk_text = extract_chunk_text(chunk)
                    yield chunk_text
        
        elif mode == 'intermediate':
            self.logger.info("Executing intermediate mode", context=context)
            try:
                task_id = self.vera.orchestrator.submit_task(
                    "llm.generate",
                    vera_instance=self.vera,
                    llm_type='intermediate',
                    prompt=query
                )
                
                for chunk in self.vera.orchestrator.stream_result(task_id, timeout=60.0):
                    chunk_text = extract_chunk_text(chunk)
                    yield chunk_text
            
            except Exception as e:
                self.logger.error(f"Intermediate LLM failed: {e}", context=context)
                for chunk in self.vera.stream_llm(self.vera.intermediate_llm, query):
                    chunk_text = extract_chunk_text(chunk)
                    yield chunk_text
        
        elif mode == 'reasoning':
            self.logger.info("Executing reasoning mode", context=context)
            try:
                task_id = self.vera.orchestrator.submit_task(
                    "llm.reasoning",
                    vera_instance=self.vera,
                    prompt=query
                )
                
                for chunk in self._stream_orchestrator_with_thoughts(task_id, timeout=90.0):
                    chunk_text = extract_chunk_text(chunk)
                    yield chunk_text
            
            except Exception as e:
                self.logger.error(f"Reasoning LLM failed: {e}", context=context)
                for chunk in self.vera.stream_llm(self.vera.reasoning_llm, query):
                    chunk_text = extract_chunk_text(chunk)
                    yield chunk_text
            
            # Add conclusion for reasoning
            yield "\n\n--- Conclusion ---\n"
            for chunk in self._generate_conclusion(query, query, context):
                yield chunk
        
        elif mode == 'complex':
            self.logger.info("Executing complex/deep mode", context=context)
            try:
                task_id = self.vera.orchestrator.submit_task(
                    "llm.deep",
                    vera_instance=self.vera,
                    prompt=query
                )
                
                for chunk in self._stream_orchestrator_with_thoughts(task_id, timeout=90.0):
                    chunk_text = extract_chunk_text(chunk)
                    yield chunk_text
            
            except Exception as e:
                self.logger.error(f"Deep LLM failed: {e}", context=context)
                for chunk in self.vera.stream_llm(self.vera.deep_llm, query):
                    chunk_text = extract_chunk_text(chunk)
                    yield chunk_text
            
            # Add conclusion
            yield "\n\n--- Conclusion ---\n"
            for chunk in self._generate_conclusion(query, query, context):
                yield chunk
        
        elif mode == 'coding':
            self.logger.info("Executing coding mode", context=context)
            try:
                task_id = self.vera.orchestrator.submit_task(
                    "llm.coding",
                    vera_instance=self.vera,
                    prompt=query
                )
                
                for chunk in self.vera.orchestrator.stream_result(task_id, timeout=60.0):
                    chunk_text = extract_chunk_text(chunk)
                    yield chunk_text
            
            except Exception as e:
                self.logger.error(f"Coding LLM failed: {e}", context=context)
                for chunk in self.vera.stream_llm(self.vera.fast_llm, query):
                    chunk_text = extract_chunk_text(chunk)
                    yield chunk_text
        
        elif mode in ['toolchain', 'toolchain-parallel', 'toolchain-adaptive', 'toolchain-stepbystep']:
            # Map to appropriate task
            task_map = {
                'toolchain':           ('toolchain.execute',          {}),
                'toolchain-parallel':  ('toolchain.execute.parallel', {}),
                'toolchain-adaptive':  ('toolchain.execute_adaptive', {}),          # ← fixed task name
                'toolchain-stepbystep':('toolchain.execute_adaptive', {'max_steps': 10}), # ← fixed task name
            }
            
            task_name, kwargs = task_map.get(mode, ('toolchain.execute', {}))
            
            self.logger.info(f"Executing {task_name}", context=context)
            yield "\n\n--- Executing Toolchain ---\n"
            
            try:
                expert_mode = routing_config.get('expert', False)
                
                task_id = self.vera.orchestrator.submit_task(
                    task_name,
                    vera_instance=self.vera,
                    query=query,
                    **kwargs
                )
                
                for chunk in self.vera.orchestrator.stream_result(task_id, timeout=600.0):
                    chunk_text = extract_chunk_text(chunk)
                    yield chunk_text
            
            except Exception as e:
                self.logger.error(f"Toolchain execution failed: {e}", context=context)
                # Adaptive fallback — run directly without orchestrator
                if 'adaptive' in mode or 'stepbystep' in mode:
                    max_steps = kwargs.get('max_steps', 20)
                    for chunk in self.vera.adaptive_toolchain.execute_adaptive(query, max_steps=max_steps):
                        yield extract_chunk_text(chunk)
                else:
                    for chunk in self.vera.toolchain.execute_tool_chain(query):
                        yield extract_chunk_text(chunk)
        
        elif mode == 'counsel' or mode.startswith('counsel-'):
            counsel_mode = routing_config.get('counsel_mode', 'vote')
            models = routing_config.get('models', ['fast', 'intermediate', 'deep'])
            
            self.logger.info(f"Executing counsel mode: {counsel_mode} with models: {models}", context=context)
            yield from self._execute_counsel_mode(query, context, counsel_mode=counsel_mode, models=models)
        
        else:
            # Unknown mode - default to simple
            self.logger.warning(f"Unknown routing mode '{mode}', defaulting to simple", context=context)
            yield from self.execute_direct_route(query, {'mode': 'simple'}, context)
            
    def _detect_parallel_opportunity(self, query: str) -> bool:
        """Detect if query has parallel execution opportunities"""
        parallel_indicators = [
            # Comparison patterns
            r'\bvs\b', r'\bversus\b', r'\bcompare\b', r'\bcomparing\b',
            r'\bdifference between\b', r'\bsimilarities\b',
            
            # Multiple item patterns
            r'\band\b.*\band\b',  # "X and Y and Z"
            r'\beach\b', r'\ball\b', r'\bboth\b',
            r'\bmultiple\b', r'\bseveral\b',
            
            # List patterns
            r'\b\d+\s+\w+',  # "3 files", "5 topics"
            
            # Explicit parallelism
            r'\bsimultaneously\b', r'\bin parallel\b', r'\bat once\b'
        ]
        
        import re
        query_lower = query.lower()
        
        for pattern in parallel_indicators:
            if re.search(pattern, query_lower):
                return True
        
        return False
            
    
    def async_run(self, query: str, use_parallel: bool = True, ramp_config: Optional[Dict] = None, routing_hints: Optional[Dict] = None) -> Iterator[str]:
        """
        Fully parallel orchestrated execution with optional routing hints
        
        Args:
            query: User query
            use_parallel: Enable parallel execution
            ramp_config: Optional custom ramp configuration
            routing_hints: Optional routing configuration from UI
            
        Yields:
            Response chunks as they're generated
        """
        
        query_context = LogContext(
            session_id=self.vera.sess.id,
            agent="async_run",
            extra={"query_length": len(query)}
        )
        
        self.logger.info(f"Processing query: {query[:100]}{'...' if len(query) > 100 else ''}", context=query_context)

        self.logger.info(f"🔍 async_run called with routing_hints: {routing_hints}", context=query_context)
        
        # Check for forced routing
        if routing_hints:
            self.logger.info(f"🔍 routing_hints.get('force'): {routing_hints.get('force')}", context=query_context)
            self.logger.info(f"🔍 routing_hints.get('mode'): {routing_hints.get('mode')}", context=query_context)
        
        # Check for forced routing
        if routing_hints and routing_hints.get('force') and routing_hints.get('mode') != 'auto':
            self.logger.info(f"🎯 Forced routing to: {routing_hints['mode']}", context=query_context)
            yield from self.execute_direct_route(query, routing_hints, query_context)
            return
    
        
        self.logger.start_timer("total_query_processing")
        
        # Log query to memory
        if hasattr(self.vera, 'mem') and hasattr(self.vera, 'sess'):
            self.vera.mem.add_session_memory(self.vera.sess.id, query, "Query", {"topic": "plan"}, promote=True)
        
        # Verify orchestrator is available
        if not hasattr(self.vera, 'orchestrator') or not self.vera.orchestrator or not self.vera.orchestrator.running:
            self.logger.error("Orchestrator not running - async_run requires orchestrator")
            yield "Error: Orchestrator not available. Please start the orchestrator."
            return
        
        # ====================================================================
        # PARALLEL EXECUTION WITH IMMEDIATE ACTION ROUTING
        # ====================================================================
        
        full_triage, preamble_response, classification, total_response, complete = yield from self._parallel_execute(
            query, query_context, routing_hints
        )
        
        # Save triage to memory
        if hasattr(self.vera, 'mem') and hasattr(self.vera, 'sess'):
            self.vera.mem.add_session_memory(
                self.vera.sess.id, 
                full_triage, 
                "Triage", 
                {"topic": "triage"}, 
                promote=True
            )
        
        # If parallel mode handled everything, we're done
        if complete:
            self.vera.save_to_memory(query, total_response)
            total_duration = self.logger.stop_timer("total_query_processing", context=query_context)
            self.logger.success(
                f"Query complete ({classification}): {len(total_response)} chars in {total_duration:.2f}s",
                context=query_context
            )
            return
        
        # ====================================================================
        # CONTINUATION ROUTES (reasoning, complex, intermediate)
        # ====================================================================
        
        route_context = LogContext(
            session_id=self.vera.sess.id,
            extra={"triage_result": classification}
        )
        
        # Special routes
        if "focus" in classification:
            yield from self._handle_focus_change(full_triage, route_context)
            total_response += "[Focus changed]"
        
        elif "adaptive" in classification:
            # ── Adaptive step-by-step toolchain ──────────────────────────────
            max_steps = getattr(self.vera.config, 'adaptive_toolchain', {}).get('max_steps', 20) \
                        if hasattr(self.vera, 'config') else 20
            try:
                task_id = self.vera.orchestrator.submit_task(
                    "toolchain.execute_adaptive",
                    vera_instance=self.vera,
                    query=query,
                    max_steps=max_steps,
                )
                for chunk in self.vera.orchestrator.stream_result(task_id, timeout=300.0):
                    chunk_text = extract_chunk_text(chunk)
                    yield chunk_text
                    total_response += chunk_text
            except Exception as e:
                self.logger.error(f"Adaptive toolchain task failed: {e}, falling back to direct", context=route_context)
                for chunk in self.vera.adaptive_toolchain.execute_adaptive(query, max_steps=max_steps):
                    chunk_text = extract_chunk_text(chunk)
                    yield chunk_text
                    total_response += chunk_text

        elif classification == "proactive":
            yield from self._handle_proactive(route_context)
            total_response += "[Proactive thinking started]"
        
        elif "counsel" in classification or "coun" in classification:
            yield from self._execute_counsel_mode(query, query_context)
            # Counsel saves its own memory
        
        elif classification == "reasoning":
            yield "\n\n"
            total_response += "\n\n"
            
            for chunk in self._execute_reasoning_continuation(query, preamble_response, route_context):
                yield chunk
                total_response += chunk
            
            if total_response.strip():
                yield "\n\n--- Conclusion ---\n"
                total_response += "\n\n--- Conclusion ---\n"
                
                for chunk in self._generate_conclusion(query, total_response, query_context):
                    yield chunk
                    total_response += chunk
        
        elif classification == "complex":
            yield "\n\n"
            total_response += "\n\n"
            
            for chunk in self._execute_deep_continuation(query, preamble_response, route_context):
                yield chunk
                total_response += chunk
            
            if total_response.strip():
                yield "\n\n--- Conclusion ---\n"
                total_response += "\n\n--- Conclusion ---\n"
                
                for chunk in self._generate_conclusion(query, total_response, query_context):
                    yield chunk
                    total_response += chunk
        
        elif classification == "intermediate":
            yield "\n\n"
            total_response += "\n\n"
            
            for chunk in self._execute_intermediate_continuation(query, preamble_response, route_context):
                yield chunk
                total_response += chunk

        elif classification == "coding":
            yield "\n\n"
            total_response += "\n\n"
            
            for chunk in self._execute_coding(query):
                yield chunk
                total_response += chunk
        
        # Save to memory
        if total_response:
            self.vera.save_to_memory(query, total_response)
        
        total_duration = self.logger.stop_timer("total_query_processing", context=query_context)
        self.logger.success(
            f"Query complete: {len(total_response)} chars in {total_duration:.2f}s",
            context=query_context
        )

    def _enhance_triage_classification(self, classification: str, query: str) -> str:
        """Enhance triage with execution mode detection"""
        
        # If already a toolchain variant, keep it
        if classification.startswith("toolchain-"):
            return classification
        
        # If classified as toolchain, try to specialize
        if classification == "toolchain":
            
            # Quick detection
            if len(query.split()) < 10 and query.count("search") == 1:
                return "toolchain-quick"
            
            # Parallel detection
            if self._detect_parallel_opportunity(query):
                return "toolchain-parallel"
            
            # Adaptive detection (complex multi-step)
            adaptive_keywords = [
                "research", "analyze", "create report", "investigate",
                "debug and fix", "optimize", "refactor", "comprehensive",
                "step by step", "step-by-step", "iteratively", "one at a time",
            ]
            
            if any(kw in query.lower() for kw in adaptive_keywords):
                return "toolchain-adaptive"
        
        return classification

    # ====================================================================
    # PARALLEL EXECUTION
    # ====================================================================
        
    def _parallel_execute(self, query: str, context: LogContext, routing_hints: Optional[Dict] = None) -> tuple:
        """
        Execute triage and preamble in parallel.
        Start action immediately when classified.
        """
        self.logger.info("🚀 Parallel execution: triage + preamble + action", context=context)
        
        # Shared state
        triage_result = queue.Queue()
        preamble_chunks = queue.Queue()
        action_chunks = queue.Queue()
        stop_preamble = threading.Event()
        action_start_event = threading.Event()
        
        full_triage = ""
        preamble_response = ""
        classification = None
        action_started = False
        
        # ================================================================
        # TRIAGE THREAD
        # ================================================================
        def triage_worker():
            nonlocal full_triage, classification
            try:
                self.logger.start_timer("triage")
                
                task_id = self.vera.orchestrator.submit_task(
                    "llm.triage",
                    vera_instance=self.vera,
                    query=query
                )
                
                for chunk in self.vera.orchestrator.stream_result(task_id, timeout=10.0):
                    chunk_text = extract_chunk_text(chunk)
                    full_triage += chunk_text
                    
                    # Extract classification from first word
                    if not classification and full_triage.strip():
                        classification = full_triage.strip().split()[0].lower()
                        triage_result.put(("classified", classification))
                        self.logger.info(f"🎯 Classification: {classification}")
                        
                        # Signal action routes
                        if classification in self.ACTION_ROUTES:
                            stop_preamble.set()
                            action_start_event.set()
                
                self.logger.stop_timer("triage", context=context)
                triage_result.put(("complete", full_triage))
            
            except Exception as e:
                self.logger.error(f"Triage failed: {e}")
                triage_result.put(("error", str(e)))
        
        # ================================================================
        # PREAMBLE THREAD
        # ================================================================
        def preamble_worker():
            nonlocal preamble_response
            try:
                preamble_prompt = self._build_context_aware_preamble_prompt(query)
                
                task_id = self.vera.orchestrator.submit_task(
                    "llm.fast",
                    vera_instance=self.vera,
                    prompt=preamble_prompt
                )
                
                for chunk in self.vera.orchestrator.stream_result(task_id, timeout=30.0):
                    if stop_preamble.is_set():
                        self.logger.info("⏹️ Preamble stopped - action route active")
                        break
                    
                    chunk_text = extract_chunk_text(chunk)
                    preamble_response += chunk_text
                    preamble_chunks.put(chunk_text)
                
                preamble_chunks.put(None)
            
            except Exception as e:
                self.logger.error(f"Preamble failed: {e}")
                preamble_chunks.put(None)
        
        # ================================================================
        # ACTION THREAD
        # ================================================================
        def action_worker():
            action_start_event.wait()
            
            self.logger.info(f"🎬 Action worker started, classification: {classification}")
            
            if not classification:
                self.logger.warning("⚠️ No classification set")
                action_chunks.put(None)
                return
            
            if classification not in self.ACTION_ROUTES:
                self.logger.info(f"ℹ️ Classification '{classification}' not an action route")
                action_chunks.put(None)
                return
            
            # ============================================================
            # TOOLCHAIN VARIANTS
            # ============================================================
            if classification.startswith("toolchain") or classification == "tool":
                task_config = {
                    "toolchain": {
                        "task": "toolchain.execute",
                        "kwargs": {},
                        "timeout": 120.0
                    },
                    "toolchain-parallel": {
                        "task": "toolchain.execute.parallel",
                        "kwargs": {},
                        "timeout": 90.0
                    },
                    "toolchain-adaptive": {
                        "task": "toolchain.execute_adaptive",       # ← fixed
                        "kwargs": {},
                        "timeout": 300.0                            # ← longer timeout for adaptive
                    },
                    "toolchain-quick": {
                        "task": "toolchain.execute_adaptive",       # ← reuse adaptive with few steps
                        "kwargs": {"max_steps": 5},
                        "timeout": 60.0
                    },
                    "toolchain-stepbystep": {
                        "task": "toolchain.execute_adaptive",       # ← same engine, explicit cap
                        "kwargs": {"max_steps": 10},
                        "timeout": 180.0
                    },
                    "tool": {
                        "task": "toolchain.execute",
                        "kwargs": {},
                        "timeout": 120.0
                    }
                }
                
                config = task_config.get(classification, {
                    "task": "toolchain.execute",
                    "kwargs": {},
                    "timeout": 120.0
                })
                
                self.logger.info(
                    f"⚡ Executing {config['task']} for '{classification}' "
                    f"(timeout={config['timeout']}s)"
                )
                
                try:
                    task_id = self.vera.orchestrator.submit_task(
                        config["task"],
                        vera_instance=self.vera,
                        query=query,
                        **config["kwargs"]
                    )
                    
                    self.logger.info(f"📋 Task submitted: {task_id}")
                    
                    chunk_count = 0
                    for chunk in self.vera.orchestrator.stream_result(
                        task_id, 
                        timeout=config["timeout"]
                    ):
                        chunk_text = extract_chunk_text(chunk)
                        action_chunks.put(chunk_text)
                        chunk_count += 1
                    
                    self.logger.success(f"✓ Toolchain complete: {chunk_count} chunks")
                    action_chunks.put(None)
                
                except Exception as e:
                    self.logger.error(f"❌ Task {config['task']} failed: {e}")
                    
                    # Adaptive-aware fallback
                    is_adaptive = classification in (
                        "toolchain-adaptive", "toolchain-quick", "toolchain-stepbystep"
                    )
                    
                    if is_adaptive and hasattr(self.vera, 'adaptive_toolchain'):
                        self.logger.info("🔄 Falling back to direct adaptive execution...")
                        max_steps = config["kwargs"].get("max_steps", 20)
                        try:
                            for chunk in self.vera.adaptive_toolchain.execute_adaptive(
                                query, max_steps=max_steps
                            ):
                                action_chunks.put(extract_chunk_text(chunk))
                        except Exception as e2:
                            self.logger.error(f"❌ Direct adaptive also failed: {e2}")
                            action_chunks.put(f"\n[Error in adaptive toolchain: {e2}]\n")
                    else:
                        self.logger.info("🔄 Falling back to standard toolchain...")
                        try:
                            for chunk in self.vera.toolchain.execute_tool_chain(query):
                                action_chunks.put(extract_chunk_text(chunk))
                        except Exception as e2:
                            self.logger.error(f"❌ Fallback also failed: {e2}")
                            action_chunks.put(f"\n[Error executing toolchain: {e2}]\n")
                    
                    action_chunks.put(None)
            
            # ============================================================
            # OTHER ACTION ROUTES
            # ============================================================
            else:
                self.logger.info(f"⚡ Executing action route: {classification}")
                
                route_task_map = {
                    "bash-agent": "agent.bash",
                    "python-agent": "agent.python",
                    "scheduling-agent": "agent.scheduling",
                    "idea-agent": "agent.idea",
                    "toolchain-expert": "toolchain.execute"
                }
                
                task_name = route_task_map.get(classification, "toolchain.execute")
                
                try:
                    task_id = self.vera.orchestrator.submit_task(
                        task_name,
                        vera_instance=self.vera,
                        query=query
                    )
                    
                    for chunk in self.vera.orchestrator.stream_result(task_id, timeout=120.0):
                        chunk_text = extract_chunk_text(chunk)
                        action_chunks.put(chunk_text)
                    
                    action_chunks.put(None)
                
                except Exception as e:
                    self.logger.error(f"❌ Action route '{classification}' failed: {e}")
                    action_chunks.put(f"\n[Error executing {classification}: {e}]\n")
                    action_chunks.put(None)
        
        # Start threads
        triage_thread = threading.Thread(target=triage_worker, daemon=True)
        preamble_thread = threading.Thread(target=preamble_worker, daemon=True)
        action_thread = threading.Thread(target=action_worker, daemon=True)
        
        triage_thread.start()
        preamble_thread.start()
        action_thread.start()
        
        # ================================================================
        # COORDINATION LOOP - Stream outputs
        # ================================================================
        
        triage_done = False
        preamble_done = False
        action_done = False
        total_response = ""
        action_response = ""
        transition_added = False
        
        while not triage_done or not preamble_done or not action_done:
            
            # Check triage updates
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
                    self.logger.warning(f"Triage error, defaulting to simple")
                    full_triage = "simple"
                    classification = "simple"
                    triage_done = True
            
            except Empty:
                pass

            # Stream preamble (until action starts)
            if not action_started:
                try:
                    chunk = preamble_chunks.get(timeout=0.01)
                    
                    if chunk is None:
                        preamble_done = True
                    else:
                        yield chunk
                        total_response += chunk
                        preamble_response += chunk
                
                except Empty:
                    pass
            else:
                # Drain preamble without yielding
                try:
                    chunk = preamble_chunks.get_nowait()
                    if chunk is None:
                        preamble_done = True
                    else:
                        preamble_response += chunk
                except Empty:
                    pass
            
            # Stream action chunks
            if action_started:
                try:
                    chunk = action_chunks.get(timeout=0.01)
                    
                    if chunk is None:
                        action_done = True
                    else:
                        yield chunk
                        total_response += chunk
                        action_response += chunk
                
                except Empty:
                    pass
            else:
                if classification and classification not in self.ACTION_ROUTES and triage_done:
                    action_done = True
        
        # ================================================================
        # DETERMINE IF COMPLETE
        # ================================================================
        
        if not classification:
            classification = "simple"
        
        # Simple queries - complete
        if classification == "simple":
            is_complete = self._is_complete_response(total_response)
            
            if not is_complete and len(total_response.strip()) < 30:
                self.logger.info("Preamble incomplete, continuing...")
                yield "\n"
                
                for chunk in self._continue_preamble(query, total_response, context):
                    yield chunk
                    total_response += chunk
            
            if hasattr(self.vera, 'mem') and hasattr(self.vera, 'sess'):
                self.vera.mem.add_session_memory(
                    self.vera.sess.id,
                    total_response,
                    "Response",
                    {"topic": "response", "agent": "fast"}
                )
            
            return full_triage, total_response, classification, total_response, True
        
        # Action routes - add conclusion and complete
        elif classification in self.ACTION_ROUTES:
            if action_response.strip():
                yield "\n\n--- Conclusion ---\n"
                total_response += "\n\n--- Conclusion ---\n"
                
                for chunk in self._generate_conclusion(query, total_response, context):
                    yield chunk
                    total_response += chunk
            
            if hasattr(self.vera, 'mem') and hasattr(self.vera, 'sess'):
                self.vera.mem.add_session_memory(
                    self.vera.sess.id,
                    action_response,
                    "Response",
                    {"topic": "response", "agent": classification}
                )
            
            return full_triage, preamble_response, classification, total_response, True
        
        # Other routes need continuation
        else:
            self.logger.info(f"Preamble complete, continuing with {classification} route...")
            return full_triage, preamble_response, classification, total_response, False
    
    def _build_context_aware_preamble_prompt(self, query: str) -> str:
        """Build preamble prompt that's aware it might be interrupted"""
        action_keywords = [
            "get", "find", "search", "look up", "check", "show me",
            "create", "make", "write", "generate", "build",
            "run", "execute", "do", "perform", "calculate",
            "list", "display", "fetch", "retrieve", "pull"
        ]
        
        query_lower = query.lower()
        is_action_query = any(keyword in query_lower for keyword in action_keywords)
        query_length = len(query.strip().split())
        
        if is_action_query:
            return f"""Briefly acknowledge that you're working on this request. Keep it to 1 sentence.
Do NOT provide instructions or explanations - just confirm you're taking action.

Query: {query}
"""
        
        elif query_length <= 3:
            return f"""Respond naturally to this query. If it's a greeting, respond warmly and ask how you can help.

Query: {query}"""
        
        elif query_length <= 10:
            return f"""Provide a concise, complete response to this query:

Query: {query}"""
        
        else:
            return f"""Provide an opening response to this query. Start by acknowledging the question and providing initial context.

Query: {query}"""
    
    def _is_complete_response(self, text: str) -> bool:
        """Check if response appears complete"""
        text = text.strip()
        return len(text) > 50 and text[-1] in '.!?'
    
    def _continue_preamble(self, query: str, partial: str, context: LogContext) -> Iterator[str]:
        """Continue incomplete preamble"""
        self.logger.start_timer("preamble_continuation")
        
        prompt = f"""Continue and complete this response naturally:

User: {query}

Response so far: {partial}

Continue from where it left off and finish the answer."""
        
        try:
            task_id = self.vera.orchestrator.submit_task(
                "llm.fast",
                vera_instance=self.vera,
                prompt=prompt
            )
            
            for chunk in self.vera.orchestrator.stream_result(task_id, timeout=30.0):
                chunk_text = extract_chunk_text(chunk)
                yield chunk_text
        
        except Exception as e:
            self.logger.error(f"Preamble continuation failed: {e}")
            for chunk in self.vera.stream_llm(self.vera.fast_llm, prompt):
                chunk_text = extract_chunk_text(chunk)
                yield chunk_text
        
        self.logger.stop_timer("preamble_continuation", context=context)
    
    # ====================================================================
    # CONTINUATION ROUTES
    # ====================================================================
    
    def _execute_intermediate_continuation(self, query: str, preamble: str, context: LogContext) -> Iterator[str]:
        """Continue with intermediate model"""
        self.logger.start_timer("intermediate_continuation")
        
        prompt = f"""The user asked: {query}

Brief introduction provided: {preamble}

Now provide intermediate-level analysis to fully answer the user's question."""
        
        response = ""
        try:
            task_id = self.vera.orchestrator.submit_task(
                "llm.intermediate",
                vera_instance=self.vera,
                prompt=prompt
            )
            
            for chunk in self.vera.orchestrator.stream_result(task_id, timeout=60.0):
                chunk_text = extract_chunk_text(chunk)
                response += chunk_text
                yield chunk_text
        
        except Exception as e:
            self.logger.error(f"Intermediate continuation failed: {e}")
            for chunk in self.vera.stream_llm(self.vera.intermediate_llm, prompt):
                chunk_text = extract_chunk_text(chunk)
                response += chunk_text
                yield chunk_text
        
        duration = self.logger.stop_timer("intermediate_continuation", context=context)
        
        if hasattr(self.vera, 'mem') and hasattr(self.vera, 'sess'):
            self.vera.mem.add_session_memory(
                self.vera.sess.id,
                response,
                "Response",
                {"topic": "response", "agent": "intermediate", "duration": duration}
            )
    
    def _execute_reasoning_continuation(self, query: str, preamble: str, context: LogContext) -> Iterator[str]:
        """Continue with reasoning model"""
        self.logger.start_timer("reasoning_continuation")
        
        prompt = f"""The user asked: {query}

Brief introduction provided: {preamble}

Now apply deep reasoning to fully answer the user's question."""
        
        response = ""
        try:
            task_id = self.vera.orchestrator.submit_task(
                "llm.reasoning",
                vera_instance=self.vera,
                prompt=prompt
            )
            
            for chunk in self._stream_orchestrator_with_thoughts(task_id, timeout=90.0):
                chunk_text = extract_chunk_text(chunk)
                response += chunk_text
                yield chunk_text
        
        except Exception as e:
            self.logger.error(f"Reasoning continuation failed: {e}")
            for chunk in self.vera.stream_llm(self.vera.reasoning_llm, prompt):
                chunk_text = extract_chunk_text(chunk)
                response += chunk_text
                yield chunk_text
        
        duration = self.logger.stop_timer("reasoning_continuation", context=context)
        
        if hasattr(self.vera, 'mem') and hasattr(self.vera, 'sess'):
            self.vera.mem.add_session_memory(
                self.vera.sess.id,
                response,
                "Response",
                {"topic": "response", "agent": "reasoning", "duration": duration}
            )
    
    def _execute_deep_continuation(self, query: str, preamble: str, context: LogContext) -> Iterator[str]:
        """Continue with deep model"""
        self.logger.start_timer("deep_continuation")
        
        prompt = f"""The user asked: {query}

Brief introduction provided: {preamble}

Now provide comprehensive analysis to fully answer the user's question."""
        
        response = ""
        try:
            task_id = self.vera.orchestrator.submit_task(
                "llm.deep",
                vera_instance=self.vera,
                prompt=prompt
            )
            
            for chunk in self._stream_orchestrator_with_thoughts(task_id, timeout=60.0):
                chunk_text = extract_chunk_text(chunk)
                response += chunk_text
                yield chunk_text
        
        except Exception as e:
            self.logger.error(f"Deep continuation failed: {e}")
            for chunk in self.vera.stream_llm(self.vera.deep_llm, prompt):
                chunk_text = extract_chunk_text(chunk)
                response += chunk_text
                yield chunk_text
        
        duration = self.logger.stop_timer("deep_continuation", context=context)
        
        if hasattr(self.vera, 'mem') and hasattr(self.vera, 'sess'):
            self.vera.mem.add_session_memory(
                self.vera.sess.id,
                response,
                "Response",
                {"topic": "response", "agent": "deep", "duration": duration}
            )
    
    # ====================================================================
    # HELPER METHODS
    # ====================================================================
    
    def _handle_focus_change(self, full_triage: str, context: LogContext) -> Iterator[str]:
        """Handle focus change requests"""
        if hasattr(self.vera, 'focus_manager'):
            new_focus = full_triage.lower().split("focus:", 1)[-1].strip()
            self.vera.focus_manager.set_focus(new_focus)
            message = f"\n✓ Focus changed to: {self.vera.focus_manager.focus}\n"
            yield message
    
    def _handle_proactive(self, context: LogContext) -> Iterator[str]:
        """Handle proactive thinking"""
        try:
            task_id = self.vera.orchestrator.submit_task(
                "proactive.generate_thought",
                vera_instance=self.vera
            )
            yield "\n[Proactive thought generation started]\n"
        except Exception as e:
            self.logger.error(f"Proactive task failed: {e}")
            yield "\n[Proactive thinking unavailable]\n"
        
    def _execute_counsel_mode(self, query: str, context: LogContext, counsel_mode: str = 'vote', models: list = None) -> Iterator[str]:
        """Execute counsel mode with specified configuration"""
        from Vera.vera_counsel import CounselExecutor
        
        if models is None:
            models = ['fast', 'intermediate', 'deep']
        
        executor = CounselExecutor(self.vera, self.logger)
        
        for chunk in executor.execute(
            query=query,
            mode=counsel_mode,
            models=models,
            context=context
        ):
            yield chunk
    
    def _execute_coding(self, query: str) -> Iterator[str]:
        """Execute coding task"""
        self.logger.start_timer("Executing coding task")
        
        coding_prompt = query
        
        try:
            task_id = self.vera.orchestrator.submit_task(
                "llm.coding",
                vera_instance=self.vera,
                prompt=coding_prompt
            )
            
            for chunk in self.vera.orchestrator.stream_result(task_id, timeout=30.0):
                chunk_text = extract_chunk_text(chunk)
                yield chunk_text
        
        except Exception as e:
            for chunk in self.vera.stream_llm(self.vera.fast_llm, coding_prompt):
                chunk_text = extract_chunk_text(chunk)
                yield chunk_text

    def _generate_conclusion(self, query: str, total_response: str, context: LogContext) -> Iterator[str]:
        """Generate conclusion summary"""
        self.logger.start_timer("conclusion_generation")
        
        conclusion_prompt = f"""Provide a brief conclusion (2-3 sentences) for this interaction:

Query: {query}
Response: {total_response[:2000]}{'...' if len(total_response) > 2000 else ''}"""
        
        try:
            task_id = self.vera.orchestrator.submit_task(
                "llm.fast",
                vera_instance=self.vera,
                prompt=conclusion_prompt
            )
            
            for chunk in self.vera.orchestrator.stream_result(task_id, timeout=30.0):
                chunk_text = extract_chunk_text(chunk)
                yield chunk_text
        
        except Exception as e:
            for chunk in self.vera.stream_llm(self.vera.fast_llm, conclusion_prompt):
                chunk_text = extract_chunk_text(chunk)
                yield chunk_text
        
        self.logger.stop_timer("conclusion_generation", context=context)
    
    def _stream_orchestrator_with_thoughts(self, task_id: str, timeout: float = 60.0) -> Iterator[str]:
        """Stream orchestrator results while polling thought queue"""
        import time
        from queue import Empty
        
        last_check = time.time()
        in_thought = False
        
        for chunk in self.vera.orchestrator.stream_result(task_id, timeout=timeout):
            # Poll thought queue
            if time.time() - last_check > 0.05:
                try:
                    while True:
                        thought_chunk = self.vera.thought_queue.get_nowait()
                        
                        if not in_thought:
                            yield "\n<thought>"
                            in_thought = True
                        
                        yield thought_chunk
                        
                except Empty:
                    pass
                last_check = time.time()
            
            if in_thought:
                yield "</thought>\n"
                in_thought = False
            
            yield chunk
        
        # Final thought drain
        try:
            while True:
                thought_chunk = self.vera.thought_queue.get_nowait()
                
                if not in_thought:
                    yield "\n<thought>"
                    in_thought = True
                
                yield thought_chunk
        except Empty:
            pass
        
        if in_thought:
            yield "</thought>\n"