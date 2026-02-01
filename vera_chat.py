#!/usr/bin/env python3
# vera_chat.py - Chat and Query Processing Module

"""
Vera Chat Module
Handles query processing, triage, routing, and response generation.

KEY FEATURES:
- Triage and preamble run in parallel
- Toolchain/actions execute IMMEDIATELY upon triage classification
- Preamble stops gracefully when action route takes over
- Preamble is action-confirmatory, not solution-providing for action routes
"""

from typing import Optional, Dict, Any, Iterator
import time
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
    """
    Handles all chat/query processing logic for Vera.
    Separated from main Vera class for modularity.
    """
    
    def __init__(self, vera_instance):
        """
        Initialize chat handler with reference to main Vera instance
        
        Args:
            vera_instance: Reference to main Vera object
        """
        self.vera = vera_instance
        self.logger = vera_instance.logger
        
        # Ramp configuration
        self.DEFAULT_RAMP_CONFIG = {
            "simple": [],                        # Stop at preamble
            "intermediate": [1],                 # Preamble → Intermediate
            "complex": [1, 2],                   # Preamble → Intermediate → Deep
            "reasoning": [1, 3],                 # Preamble → Intermediate → Reasoning
            "toolchain": [4],                    # Preamble → Toolchain (immediate)
            "tool": [4],                         # Alias
            "bash-agent": [4],                   # Bash agent
            "python-agent": [4],                 # Python agent
            "scheduling-agent": [4],             # Scheduling
            "idea-agent": [4],                   # Ideas
            "toolchian-expert": [5],            # Toolchain Expert
            "counsel": [],                       # Counsel mode (handled separately)
            "focus": [],                         # Focus change (handled separately)
            "proactive": []                      # Proactive (handled separately)
        }
        
        self.TIER_NAMES = {
            0: "Preamble",
            1: "Intermediate", 
            2: "Deep",
            3: "Reasoning",
            4: "Toolchain",
            5: "Toolchain Expert"
        }
        
        # Action routes that should interrupt preamble
        self.ACTION_ROUTES = {
            "toolchain", "tool", "bash-agent", "python-agent", 
            "scheduling-agent", "idea-agent", "toolchain-expert"
        }
        
    def async_run(self, query: str, use_parallel: bool = True, ramp_config: Optional[Dict] = None) -> Iterator[str]:
        """
        Fully orchestrated async_run with immediate action execution.
        
        Args:
            query: User query
            use_parallel: Enable parallel triage+preamble execution (default: True)
            ramp_config: Optional custom ramp configuration
            
        Yields:
            str: Response chunks as they're generated
        """
        
        ramp_config = ramp_config or getattr(self.vera.config, 'ramp', self.DEFAULT_RAMP_CONFIG)
        
        query_context = LogContext(
            session_id=self.vera.sess.id,
            agent="async_run",
            extra={"query_length": len(query), "parallel": use_parallel}
        )
        
        self.logger.info(f"Processing query: {query[:100]}{'...' if len(query) > 100 else ''}", context=query_context)
        self.logger.start_timer("total_query_processing")
        
        # Log query to memory
        if hasattr(self.vera, 'mem') and hasattr(self.vera, 'sess'):
            self.vera.mem.add_session_memory(self.vera.sess.id, query, "Query", {"topic": "plan"}, promote=True)
        
        # ====================================================================
        # STEP 1: PARALLEL TRIAGE + PREAMBLE WITH IMMEDIATE ACTION ROUTING
        # ====================================================================
        
        use_orchestrator = hasattr(self.vera, 'orchestrator') and self.vera.orchestrator and self.vera.orchestrator.running
        
        full_triage = ""
        preamble_response = ""
        triage_duration = 0.0
        total_response = ""
        route_classification = None
        parallel_complete = False  # Track if parallel mode completed the entire request
        
        if use_parallel and use_orchestrator:
            # PARALLEL MODE - Execute actions immediately when triage completes
            full_triage, preamble_response, route_classification, total_response, parallel_complete = yield from self._parallel_with_immediate_action(
                query, query_context, ramp_config
            )
            triage_duration = 0  # Included in parallel timing
        else:
            # SERIAL MODE
            full_triage, triage_duration = yield from self._serial_triage(
                query, query_context, use_orchestrator
            )
            route_classification = full_triage.lower().strip().split('\n')[0].strip().split()[0]
        
        # Save triage to memory
        if hasattr(self.vera, 'mem') and hasattr(self.vera, 'sess'):
            self.vera.mem.add_session_memory(
                self.vera.sess.id, 
                full_triage, 
                "Triage", 
                {"topic": "triage", "duration": triage_duration}, 
                promote=True
            )
        
        # If parallel mode handled everything completely, we're done
        if parallel_complete:
            self.vera.save_to_memory(query, total_response)
            total_duration = self.logger.stop_timer("total_query_processing", context=query_context)
            self.logger.success(
                f"Query complete ({route_classification}): {len(total_response)} chars in {total_duration:.2f}s",
                context=query_context
            )
            return
        
        # ====================================================================
        # STEP 2: ROUTE EXECUTION (Serial mode OR parallel mode continuation)
        # ====================================================================
        
        triage_lower = full_triage.lower().strip()
        
        route_context = LogContext(
            session_id=self.vera.sess.id,
            extra={"triage_result": triage_lower[:50]}
        )
        
        # Special routes
        if "focus" in triage_lower:
            for chunk in self._handle_focus_change(full_triage, route_context):
                yield chunk
                total_response += chunk
            
            self.vera.save_to_memory(query, total_response)
            total_duration = self.logger.stop_timer("total_query_processing", context=query_context)
            self.logger.success(f"Query complete (focus): {len(total_response)} chars in {total_duration:.2f}s", context=query_context)
            return
        
        elif triage_lower.startswith("proactive"):
            for chunk in self._handle_proactive(route_context, use_orchestrator, triage_duration):
                yield chunk
                total_response += chunk
            
            self.vera.save_to_memory(query, total_response)
            total_duration = self.logger.stop_timer("total_query_processing", context=query_context)
            self.logger.success(f"Query complete (proactive): {len(total_response)} chars in {total_duration:.2f}s", context=query_context)
            return
        
        elif triage_lower.startswith("counsel"):
            for chunk in self._execute_counsel_mode(query, query_context):
                yield chunk
                total_response += chunk
            
            if hasattr(self.vera, 'mem') and hasattr(self.vera, 'sess'):
                self.vera.mem.add_session_memory(
                    self.vera.sess.id,
                    total_response,
                    "Response",
                    {"topic": "response", "agent": "counsel"}
                )
            
            self.vera.save_to_memory(query, total_response)
            total_duration = self.logger.stop_timer("total_query_processing", context=query_context)
            self.logger.success(f"Query complete (counsel): {len(total_response)} chars in {total_duration:.2f}s", context=query_context)
            return
        
        # Determine ramp path
        ramp_path = []
        for keyword, path in ramp_config.items():
            if keyword in triage_lower:
                ramp_path = path
                break
        
        self.logger.info(
            f"🎯 Triage: '{route_classification}' → Ramp: {[self.TIER_NAMES.get(t, f'T{t}') for t in ramp_path] or ['NONE']}",
            context=route_context
        )
        
        # Execute routes
        # Note: If we got here from parallel mode, preamble is already streamed and in total_response
        if route_classification in self.ACTION_ROUTES:
            # Action routes only reach here in serial mode
            if not use_parallel:  # Only add transition in serial mode
                yield "\n\n--- Tool Execution ---\n"
                total_response += "\n\n--- Tool Execution ---\n"
            
            for chunk in self._execute_toolchain(
                query, preamble_response, ramp_path, use_orchestrator, route_context
            ):
                yield chunk
                total_response += chunk
            
            # Generate conclusion
            if total_response.strip():
                yield "\n\n--- Conclusion ---\n"
                total_response += "\n\n--- Conclusion ---\n"
                
                for chunk in self._generate_conclusion(
                    query, total_response, use_orchestrator, query_context
                ):
                    yield chunk
                    total_response += chunk
        
        elif triage_lower.startswith("reasoning"):
            # Add transition if not parallel (parallel already did it)
            if not use_parallel:
                yield "\n\n--- Reasoning Mode ---\n"
                total_response += "\n\n--- Reasoning Mode ---\n"
            else:
                # Parallel mode - add smooth transition
                yield "\n\n"
                total_response += "\n\n"
            
            # Execute continuation
            for chunk in self._execute_reasoning_continuation(
                query, preamble_response, use_orchestrator, route_context
            ):
                yield chunk
                total_response += chunk
            
            if total_response.strip():
                yield "\n\n--- Conclusion ---\n"
                total_response += "\n\n--- Conclusion ---\n"
                
                for chunk in self._generate_conclusion(
                    query, total_response, use_orchestrator, query_context
                ):
                    yield chunk
                    total_response += chunk
        
        elif triage_lower.startswith("complex"):
            # Add transition
            if not use_parallel:
                yield "\n\n--- Deep Analysis ---\n"
                total_response += "\n\n--- Deep Analysis ---\n"
            else:
                yield "\n\n"
                total_response += "\n\n"
            
            # Execute continuation
            for chunk in self._execute_deep_continuation(
                query, preamble_response, use_orchestrator, route_context
            ):
                yield chunk
                total_response += chunk
            
            if total_response.strip():
                yield "\n\n--- Conclusion ---\n"
                total_response += "\n\n--- Conclusion ---\n"
                
                for chunk in self._generate_conclusion(
                    query, total_response, use_orchestrator, query_context
                ):
                    yield chunk
                    total_response += chunk
        
        elif triage_lower.startswith("intermediate"):
            # Add transition
            if not use_parallel:
                yield "\n\n"
                total_response += "\n\n"
            else:
                yield "\n\n"
                total_response += "\n\n"
            
            # Execute continuation
            for chunk in self._execute_intermediate_continuation(
                query, preamble_response, use_orchestrator, route_context
            ):
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
        
    # ====================================================================
    # HELPER METHODS - Parallel with Immediate Action Execution
    # ====================================================================
    
    def _parallel_with_immediate_action(self, query: str, context: LogContext, 
                                        ramp_config: Dict) -> tuple:
        """
        Execute triage and preamble in parallel.
        When triage completes with action route, IMMEDIATELY start execution.
        Preamble stops gracefully when action takes over.
        
        Returns:
            tuple: (full_triage, preamble_response, classification, total_response, parallel_complete)
        """
        self.logger.info("🚀 Parallel triage + preamble with immediate action", context=context)
        
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
        # TRIAGE THREAD - Signals classification and starts action
        # ================================================================
        def triage_worker():
            nonlocal full_triage, classification
            try:
                self.logger.start_timer("triage")
                
                triage_task_id = self.vera.orchestrator.submit_task(
                    "llm.triage",
                    vera_instance=self.vera,
                    query=query
                )
                
                for chunk in self.vera.orchestrator.stream_result(triage_task_id, timeout=10.0):
                    chunk_text = extract_chunk_text(chunk)
                    full_triage += chunk_text
                    
                    # Get first word as classification
                    if not classification and full_triage.strip():
                        classification = full_triage.strip().split()[0].lower()
                        triage_result.put(("classified", classification))
                        self.logger.info(f"🎯 Classification: {classification}")
                        
                        # If action route, signal to stop verbose preamble and start action
                        if classification in self.ACTION_ROUTES:
                            stop_preamble.set()
                            action_start_event.set()
                
                triage_duration = self.logger.stop_timer("triage", context=context)
                triage_result.put(("complete", full_triage, triage_duration))
            
            except Exception as e:
                self.logger.error(f"Triage failed: {e}")
                triage_result.put(("error", str(e)))
        
        # ================================================================
        # PREAMBLE THREAD - Context-aware, stops for actions
        # ================================================================
        def preamble_worker():
            nonlocal preamble_response
            try:
                # Build action-aware preamble prompt
                preamble_prompt = self._build_action_aware_preamble_prompt(query)
                
                preamble_task_id = self.vera.orchestrator.submit_task(
                    "llm.fast",
                    vera_instance=self.vera,
                    prompt=preamble_prompt
                )
                
                for chunk in self.vera.orchestrator.stream_result(preamble_task_id, timeout=30.0):
                    # Check if we should stop (action route detected)
                    if stop_preamble.is_set():
                        self.logger.info("⏹️ Preamble stopped - action route taking over")
                        break
                    
                    chunk_text = extract_chunk_text(chunk)
                    preamble_response += chunk_text
                    preamble_chunks.put(chunk_text)
                
                preamble_chunks.put(None)  # Signal completion
            
            except Exception as e:
                self.logger.error(f"Preamble failed: {e}")
                preamble_chunks.put(None)
        
        # ================================================================
        # ACTION THREAD - Starts immediately when event is set
        # ================================================================
        def action_worker():
            """Wait for action signal, then execute immediately"""
            # Wait for action signal
            action_start_event.wait()
            
            if not classification or classification not in self.ACTION_ROUTES:
                action_chunks.put(None)
                return
            
            self.logger.info(f"⚡ Action route '{classification}' executing immediately")
            
            try:
                # Execute appropriate action
                task_id = self.vera.orchestrator.submit_task(
                    "toolchain.execute",
                    vera_instance=self.vera,
                    query=query
                )
                
                for chunk in self.vera.orchestrator.stream_result(task_id, timeout=120.0):
                    chunk_text = extract_chunk_text(chunk)
                    action_chunks.put(chunk_text)
                
                action_chunks.put(None)  # Signal completion
            
            except Exception as e:
                self.logger.error(f"Action execution failed: {e}")
                # Fallback to direct execution
                try:
                    for chunk in self.vera.toolchain.execute_tool_chain(query):
                        chunk_text = extract_chunk_text(chunk)
                        action_chunks.put(chunk_text)
                except Exception as e2:
                    self.logger.error(f"Fallback failed: {e2}")
                
                action_chunks.put(None)
        
        # Start all threads
        triage_thread = threading.Thread(target=triage_worker, daemon=True)
        preamble_thread = threading.Thread(target=preamble_worker, daemon=True)
        action_thread = threading.Thread(target=action_worker, daemon=True)
        
        triage_thread.start()
        preamble_thread.start()
        action_thread.start()
        
        # ================================================================
        # MAIN COORDINATION LOOP
        # ================================================================
        
        self.logger.info("⚡ Streaming preamble while awaiting triage...")
        
        triage_done = False
        preamble_done = False
        action_done = False
        total_response = ""
        action_response = ""
        transition_added = False
        
        # Stream outputs as they become available
        while not triage_done or not preamble_done or not action_done:
            
            # Check for triage updates
            try:
                event = triage_result.get_nowait()
                
                if event[0] == "classified":
                    classification = event[1]
                    self.logger.info(f"✓ Classified as: {classification}")
                    
                    # Check if this is an action route
                    if classification in self.ACTION_ROUTES:
                        action_started = True
                        if not transition_added:
                            yield "\n\n--- Executing ---\n"
                            total_response += "\n\n--- Executing ---\n"
                            transition_added = True
                
                elif event[0] == "complete":
                    full_triage = event[1]
                    triage_done = True
                    self.logger.success("Triage complete")
                
                elif event[0] == "error":
                    self.logger.warning(f"Triage error: {event[1]}, defaulting to simple")
                    full_triage = "simple"
                    classification = "simple"
                    triage_done = True
            
            except Empty:
                pass
            
            # Stream preamble chunks (until action takes over)
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
                # Drain remaining preamble chunks without yielding
                try:
                    chunk = preamble_chunks.get_nowait()
                    if chunk is None:
                        preamble_done = True
                    else:
                        preamble_response += chunk  # Store but don't yield
                except Empty:
                    pass
            
            # Stream action chunks (when available)
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
                # No action started, mark as done
                if classification and classification not in self.ACTION_ROUTES and triage_done:
                    action_done = True
        
        # ================================================================
        # DECISION POINT: Return based on what happened
        # ================================================================
        
        if not classification:
            classification = "simple"
        
        if classification == "simple":
            # Simple query - check if preamble is complete
            is_complete = self._is_complete_response(total_response)
            
            if not is_complete and len(total_response.strip()) < 30:
                self.logger.info("Preamble incomplete for simple query, continuing...")
                yield "\n"
                
                for chunk in self._continue_preamble(query, total_response, context):
                    yield chunk
                    total_response += chunk
            
            # Save and return
            if hasattr(self.vera, 'mem') and hasattr(self.vera, 'sess'):
                self.vera.mem.add_session_memory(
                    self.vera.sess.id,
                    total_response,
                    "Response",
                    {"topic": "response", "agent": "fast"}
                )
            
            return full_triage, total_response, classification, total_response, True  # parallel_complete=True
        
        elif classification in self.ACTION_ROUTES:
            # Action route - add conclusion
            if action_response.strip():
                yield "\n\n--- Conclusion ---\n"
                total_response += "\n\n--- Conclusion ---\n"
                
                for chunk in self._generate_conclusion(query, total_response, True, context):
                    yield chunk
                    total_response += chunk
            
            # Save and return
            if hasattr(self.vera, 'mem') and hasattr(self.vera, 'sess'):
                self.vera.mem.add_session_memory(
                    self.vera.sess.id,
                    action_response,
                    "Response",
                    {"topic": "response", "agent": classification}
                )
            
            return full_triage, preamble_response, classification, total_response, True  # parallel_complete=True
        
        else:
            # Other routes (reasoning, complex, intermediate) - need continuation
            # Preamble already streamed, return for continuation
            self.logger.info(f"Preamble complete ({len(preamble_response)} chars), continuing with {classification} route...")
            return full_triage, preamble_response, classification, total_response, False  # parallel_complete=False
        
    def _build_action_aware_preamble_prompt(self, query: str) -> str:
        """
        Build a preamble prompt that's aware it might be interrupted by actions.
        For action-like queries, generates brief acknowledgment instead of full solution.
        """
        # Detect action indicators
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
            # Action query - brief acknowledgment only
            return f"""Briefly acknowledge that you're working on this request. Keep it to 1 sentence.
Do NOT provide instructions or explanations - just confirm you're taking action.

Query: {query}

Example responses:
- "I'll get that information for you..."
- "Looking that up now..."
- "Running the command..."
- "Creating that file..."
"""
        
        elif query_length <= 3:
            # Very short query - likely greeting or simple question
            return f"""Respond naturally to this query. If it's a greeting, respond warmly and ask how you can help.

Query: {query}"""
        
        elif query_length <= 10:
            # Short query - concise complete response
            return f"""Provide a concise, complete response to this query:

Query: {query}"""
        
        else:
            # Longer query - opening that can lead into deeper analysis
            return f"""Provide an opening response to this query. Start by acknowledging the question and providing initial context. This may be followed by deeper analysis.

Query: {query}"""
    
    def _is_complete_response(self, text: str) -> bool:
        """Check if response appears complete"""
        text = text.strip()
        
        if len(text) < 20:
            return False
        
        # Check for sentence endings
        ends_with_punctuation = text[-1] in '.!?'
        
        # Check for reasonable length
        has_reasonable_length = len(text) > 50
        
        return ends_with_punctuation and has_reasonable_length
    
    def _continue_preamble(self, query: str, partial: str, context: LogContext) -> Iterator[str]:
        """Continue an incomplete preamble"""
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
    # HELPER METHODS - Route Continuations
    # ====================================================================
    
    def _execute_intermediate_continuation(self, query: str, preamble: str, 
                                          use_orchestrator: bool, context: LogContext) -> Iterator[str]:
        """Continue from preamble with intermediate model"""
        self.logger.start_timer("intermediate_continuation")
        
        prompt = f"""Building on this introduction:
{preamble}

Provide intermediate-level analysis for: {query}"""
        
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
    
    def _execute_reasoning_continuation(self, query: str, preamble: str,
                                       use_orchestrator: bool, context: LogContext) -> Iterator[str]:
        """Continue from preamble with reasoning model"""
        self.logger.start_timer("reasoning_continuation")
        
        prompt = f"""Building on this introduction:
{preamble}

Apply deep reasoning to: {query}"""
        
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
    
    def _execute_deep_continuation(self, query: str, preamble: str,
                                   use_orchestrator: bool, context: LogContext) -> Iterator[str]:
        """Continue from preamble with deep model"""
        self.logger.start_timer("deep_continuation")
        
        prompt = f"""Building on this introduction:
{preamble}

Provide comprehensive analysis for: {query}"""
        
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
    # HELPER METHODS - Serial Mode (fallback)
    # ====================================================================
    
    def _serial_triage(self, query: str, context: LogContext, use_orchestrator: bool) -> tuple:
        """Execute triage serially (traditional mode)"""
        self.logger.debug(f"Using orchestrator: {use_orchestrator}", context=context)
        self.logger.start_timer("triage")
        
        full_triage = ""
        
        if use_orchestrator:
            try:
                triage_task_id = self.vera.orchestrator.submit_task(
                    "llm.triage",
                    vera_instance=self.vera,
                    query=query
                )
                
                for chunk in self.vera.orchestrator.stream_result(triage_task_id, timeout=10.0):
                    full_triage += chunk
                    yield extract_chunk_text(chunk)
            
            except Exception as e:
                self.logger.error(f"Triage failed: {e}")
                for chunk in self._triage_direct(query):
                    full_triage += chunk
                    yield extract_chunk_text(chunk)
        else:
            for chunk in self._triage_direct(query):
                full_triage += chunk
                yield extract_chunk_text(chunk)
        
        yield "\n"
        triage_duration = self.logger.stop_timer("triage", context=context)
        
        return full_triage, triage_duration
    
    def _triage_direct(self, query: str) -> Iterator[str]:
        """Direct triage without orchestrator"""
        triage_context = LogContext(
            session_id=self.vera.sess.id,
            agent="triage"
        )
        
        if self.vera.agents:
            agent_name = self.vera.get_agent_for_task('triage')
            triage_llm = self.vera.create_llm_for_agent(agent_name)
            triage_context.agent = agent_name
            triage_context.model = agent_name
        else:
            triage_llm = self.vera.fast_llm
            triage_context.model = self.vera.selected_models.fast_llm
        
        triage_prompt = f"""
        Classify this Query into one of the following categories:
            - 'focus'      → Change the focus of background thought.
            - 'proactive'  → Trigger proactive thinking.
            - 'simple'     → Simple textual response.
            - 'toolchain'  → Requires a series of tools or step-by-step planning.
            - 'reasoning'  → Requires deep reasoning.
            - 'complex'    → Complex written response with high-quality output.
            - 'bash-agent' → Bash commands/scripts
            - 'python-agent' → Python commands/scripts
            - 'scheduling-agent' → Scheduling tasks
            - 'idea-agent' → Generate ideas

        Current focus: {self.vera.focus_manager.focus if hasattr(self.vera, 'focus_manager') else 'None'}

        Query: {query}

        Respond with a single classification term on the first line.
        """
        
        for chunk in self.vera.stream_llm(triage_llm, triage_prompt):
            yield chunk
    
    # ====================================================================
    # HELPER METHODS - Special Routes
    # ====================================================================
    
    def _handle_focus_change(self, full_triage: str, context: LogContext) -> Iterator[str]:
        """Handle focus change requests"""
        self.logger.info("Routing to: Proactive Focus Manager", context=context)
        
        if hasattr(self.vera, 'focus_manager'):
            new_focus = full_triage.lower().split("focus:", 1)[-1].strip()
            self.vera.focus_manager.set_focus(new_focus)
            message = f"\n✓ Focus changed to: {self.vera.focus_manager.focus}\n"
            yield message
            self.logger.success(f"Focus changed to: {self.vera.focus_manager.focus}")
    
    def _handle_proactive(self, context: LogContext, use_orchestrator: bool, triage_duration: float) -> Iterator[str]:
        """Handle proactive thinking requests"""
        self.logger.info("Routing to: Proactive Thinking", context=context)
        
        if use_orchestrator:
            try:
                task_id = self.vera.orchestrator.submit_task(
                    "proactive.generate_thought",
                    vera_instance=self.vera
                )
                message = "\n[Proactive thought generation started in background]\n"
                yield message
                self.logger.success("Proactive task submitted")
                
                if hasattr(self.vera, 'mem') and hasattr(self.vera, 'sess'):
                    self.vera.mem.add_session_memory(
                        self.vera.sess.id,
                        message,
                        "Thought",
                        {"topic": "response", "agent": "proactive", "task_id": task_id, "duration": triage_duration}
                    )
                return
            
            except Exception as e:
                self.logger.error(f"Failed to submit proactive task: {e}")
        
        # Fallback
        if hasattr(self.vera, 'focus_manager') and self.vera.focus_manager.focus:
            self.vera.focus_manager.iterative_workflow(
                max_iterations=None,
                iteration_interval=600,
                auto_execute=True
            )
            message = "\n[Proactive workflow started]\n"
            yield message
        else:
            message = "\n[No active focus for proactive thinking]\n"
            yield message
    
    # ====================================================================
    # HELPER METHODS - Route Execution
    # ====================================================================
    
    def _execute_toolchain(self, query: str, preamble: str, ramp_path: list, 
                          use_orchestrator: bool, context: LogContext) -> Iterator[str]:
        """Execute toolchain route"""
        self.logger.info("Routing to: Tool Chain Agent", context=context)
        self.logger.start_timer("toolchain_execution")
        
        # For toolchain, use original query (preamble was just acknowledgment)
        toolchain_query = query
        toolchain_response = ""
        
        if use_orchestrator:
            try:
                task_id = self.vera.orchestrator.submit_task(
                    "toolchain.execute",
                    vera_instance=self.vera,
                    query=toolchain_query,
                )
                
                for chunk in self.vera.orchestrator.stream_result(task_id, timeout=120.0):
                    chunk_text = extract_chunk_text(chunk)
                    toolchain_response += chunk_text
                    yield chunk_text
            
            except Exception as e:
                self.logger.error(f"Toolchain failed: {e}")
                for chunk in self.vera.toolchain.execute_tool_chain(toolchain_query):
                    chunk_text = extract_chunk_text(chunk)
                    toolchain_response += chunk_text
                    yield chunk_text
        else:
            for chunk in self.vera.toolchain.execute_tool_chain(toolchain_query):
                chunk_text = extract_chunk_text(chunk)
                toolchain_response += chunk_text
                yield chunk_text
        
        duration = self.logger.stop_timer("toolchain_execution", context=context)
        
        if hasattr(self.vera, 'mem') and hasattr(self.vera, 'sess'):
            self.vera.mem.add_session_memory(
                self.vera.sess.id,
                toolchain_response,
                "Response",
                {"topic": "response", "agent": "toolchain", "duration": duration}
            )
    
    def _execute_counsel_mode(self, query: str, context: LogContext) -> Iterator[str]:
        """Execute counsel mode"""
        counsel_config = getattr(self.vera.config, 'counsel', {
            'mode': 'vote',
            'models': ['fast', 'fast', 'fast'],
            'instances': None
        })
        
        from Vera.vera_counsel import CounselExecutor
        
        executor = CounselExecutor(self.vera, self.logger)
        
        for chunk in executor.execute(
            query=query,
            mode=counsel_config.get('mode', 'race'),
            models=counsel_config.get('models', ['fast', 'intermediate', 'reasoning']),
            instances=counsel_config.get('instances', None),
            context=context
        ):
            yield chunk
    
    def _generate_conclusion(self, query: str, total_response: str, 
                            use_orchestrator: bool, context: LogContext) -> Iterator[str]:
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
        last_check = time.time()
        in_thought = False
        
        for chunk in self.vera.orchestrator.stream_result(task_id, timeout=timeout):
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