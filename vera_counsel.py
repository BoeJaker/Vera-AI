#!/usr/bin/env python3
# Vera/Chat/counsel.py - Counsel Mode Execution

"""
Counsel Mode: Multiple models/instances deliberate on the same query
"""

import threading
import queue
import time
import re
from typing import Iterator, List, Optional, Dict, Any
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


class CounselExecutor:
    """Executes counsel mode with multiple models or instances"""
    
    def __init__(self, vera_instance, logger):
        self.vera = vera_instance
        self.logger = logger
    
    def execute(
        self,
        query: str,
        mode: str = 'vote',
        models: Optional[List[str]] = None,
        instances: Optional[List[str]] = None,
        context: Optional[LogContext] = None
    ) -> Iterator[str]:
        """
        Execute counsel mode
        
        Args:
            query: User query
            mode: 'race', 'synthesis', or 'vote'
            models: List of model types (if using model-based)
            instances: List of instance specs (if using instance-based)
            context: Logging context
        
        Yields:
            str: Response chunks
        """
        
        models = models or ['fast', 'intermediate', 'reasoning']
        
        if instances:
            strategy = "instances"
            executors = instances
            self.logger.info(
                f"🏛️ Counsel mode: {mode} using instances: {executors}",
                context=context
            )
        else:
            strategy = "models"
            executors = models
            self.logger.info(
                f"🏛️ Counsel mode: {mode} using models: {executors}",
                context=context
            )
        
        response_queue = queue.Queue()
        
        # Launch execution threads
        if strategy == "instances":
            threads = self._launch_instance_threads(executors, query, response_queue, context)
        else:
            threads = self._launch_model_threads(executors, query, response_queue, context)
        
        # Execute mode-specific logic
        if mode == 'race':
            yield from self._mode_race(response_queue, context)
        elif mode == 'synthesis':
            yield from self._mode_synthesis(threads, response_queue, query, context)
        elif mode == 'vote':
            yield from self._mode_vote(threads, response_queue, query, context)
        else:
            yield f"\n\nError: Unknown counsel mode '{mode}'\n"
    
    def _launch_instance_threads(self, instance_specs: List[str], query: str, 
                                 response_queue: queue.Queue, context: LogContext) -> List[threading.Thread]:
        """Launch threads for instance-based execution"""
        
        instance_map = {}
        
        for spec in instance_specs:
            if ':' in spec:
                instance_name, model_name = spec.split(':', 1)
            else:
                instance_name = spec
                model_name = self.vera.selected_models.fast_llm
            
            instance_map[spec] = {
                'instance': instance_name,
                'model': model_name
            }
        
        def run_instance(spec, instance_info, label):
            try:
                self.logger.debug(f"Counsel: Starting {label}", context=context)
                start_time = time.time()
                
                llm = self.vera.ollama_manager.create_llm_with_routing(
                    model=instance_info['model'],
                    routing_mode='manual',
                    selected_instances=[instance_info['instance']],
                    temperature=0.7
                )
                
                response = ""
                for chunk in self.vera.stream_llm(llm, query):
                    response += extract_chunk_text(chunk)
                
                duration = time.time() - start_time
                response_queue.put((label, response, duration, time.time()))
                
                self.logger.success(f"Counsel: {label} completed in {duration:.2f}s", context=context)
            
            except Exception as e:
                self.logger.error(f"Counsel: {label} failed: {e}", context=context)
        
        threads = []
        for spec, info in instance_map.items():
            label = f"{info['model']}@{info['instance']}"
            thread = threading.Thread(
                target=run_instance,
                args=(spec, info, label),
                daemon=True
            )
            thread.start()
            threads.append(thread)
        
        return threads
    
    def _launch_model_threads(self, model_types: List[str], query: str, 
                             response_queue: queue.Queue, context: LogContext) -> List[threading.Thread]:
        """Launch threads for model-based execution"""
        
        model_map = {
            'fast': self.vera.fast_llm,
            'intermediate': self.vera.intermediate_llm if hasattr(self.vera, 'intermediate_llm') else self.vera.fast_llm,
            'deep': self.vera.deep_llm,
            'reasoning': self.vera.reasoning_llm
        }
        
        def run_model(model_type, model_llm, label):
            try:
                self.logger.debug(f"Counsel: Starting {label}", context=context)
                start_time = time.time()
                
                response = ""
                for chunk in self.vera.stream_llm(model_llm, query):
                    response += extract_chunk_text(chunk)
                
                duration = time.time() - start_time
                response_queue.put((label, response, duration, time.time()))
                
                self.logger.success(f"Counsel: {label} completed in {duration:.2f}s", context=context)
            
            except Exception as e:
                self.logger.error(f"Counsel: {label} failed: {e}", context=context)
        
        threads = []
        for idx, model_type in enumerate(model_types):
            if model_type in model_map:
                count = model_types[:idx+1].count(model_type)
                label = f"{model_type.title()}" + (f" #{count}" if model_types.count(model_type) > 1 else "")
                
                thread = threading.Thread(
                    target=run_model,
                    args=(model_type, model_map[model_type], label),
                    daemon=True
                )
                thread.start()
                threads.append(thread)
        
        return threads
    
    def _mode_race(self, response_queue: queue.Queue, context: LogContext) -> Iterator[str]:
        """Race mode: Fastest response wins"""
        try:
            winner_label, winner_response, duration, completion_time = response_queue.get(timeout=120.0)
            
            self.logger.success(f"🏆 Counsel winner: {winner_label} ({duration:.2f}s)", context=context)
            
            yield f"\n\n--- Counsel Mode: Race Winner ---\n"
            yield f"**{winner_label}** (completed in {duration:.2f}s)\n\n"
            yield winner_response
        
        except Empty:
            self.logger.error("Counsel: All models timed out", context=context)
            yield "\n\n--- Counsel Mode: Error ---\nAll models timed out\n"
    
    def _mode_synthesis(self, threads: List[threading.Thread], response_queue: queue.Queue, 
                       query: str, context: LogContext) -> Iterator[str]:
        """Synthesis mode: Combine all responses"""
        responses = []
        
        for _ in range(len(threads)):
            try:
                label, response, duration, completion_time = response_queue.get(timeout=120.0)
                responses.append((label, response, duration))
            except Empty:
                break
        
        if not responses:
            self.logger.error("Counsel: No models completed", context=context)
            yield "\n\n--- Counsel Mode: Error ---\nNo models completed\n"
            return
        
        self.logger.info(f"Counsel: Collected {len(responses)} responses, synthesizing...", context=context)
        
        yield f"\n\n--- Counsel Mode: Synthesis ({len(responses)} perspectives) ---\n\n"
        
        for label, response, duration in responses:
            yield f"**{label}** ({duration:.2f}s):\n{response[:300]}{'...' if len(response) > 300 else ''}\n\n"
        
        # Synthesize
        synthesis_prompt = f"""Multiple AI perspectives on this query: {query}

Perspectives:
"""
        
        for label, response, duration in responses:
            synthesis_prompt += f"\n**{label}**:\n{response[:800]}{'...' if len(response) > 800 else ''}\n\n"
        
        synthesis_prompt += """
Synthesize these perspectives into a single, coherent response that:
1. Captures the best insights from each perspective
2. Highlights areas of agreement
3. Notes any important differences or unique contributions
4. Provides a unified conclusion

Keep the synthesis concise and actionable."""
        
        yield "--- Synthesis ---\n"
        
        for chunk in self.vera.stream_llm(self.vera.fast_llm, synthesis_prompt):
            yield extract_chunk_text(chunk)
    
    def _mode_vote(self, threads: List[threading.Thread], response_queue: queue.Queue, 
                   query: str, context: LogContext) -> Iterator[str]:
        """Vote mode: Judge selects best response"""
        responses = []
        
        for _ in range(len(threads)):
            try:
                label, response, duration, completion_time = response_queue.get(timeout=120.0)
                responses.append((label, response, duration))
            except Empty:
                break
        
        if not responses:
            self.logger.error("Counsel: No models completed", context=context)
            yield "\n\n--- Counsel Mode: Error ---\nNo models completed\n"
            return
        
        if len(responses) == 1:
            label, response, duration = responses[0]
            self.logger.info(f"Counsel: Only one response from {label}, using it", context=context)
            yield f"\n\n--- Counsel Mode: Vote (Only One Response) ---\n"
            yield f"**{label}** ({duration:.2f}s)\n\n"
            yield response
            return
        
        self.logger.info(f"Counsel: Collected {len(responses)} responses, voting...", context=context)
        
        yield f"\n\n--- Counsel Mode: Vote ({len(responses)} candidates) ---\n\n"
        
        for idx, (label, response, duration) in enumerate(responses, 1):
            yield f"**Candidate {idx}: {label}** ({duration:.2f}s)\n{response[:200]}{'...' if len(response) > 200 else ''}\n\n"
        
        # Judge
        vote_prompt = f"""You are judging multiple AI responses to select the BEST one.

Original Query: {query}

Candidates:
"""
        
        for idx, (label, response, duration) in enumerate(responses, 1):
            vote_prompt += f"\n**Candidate {idx} ({label})**:\n{response}\n\n"
        
        vote_prompt += f"""
Evaluate each candidate on:
1. Accuracy and correctness
2. Completeness and depth
3. Clarity and coherence
4. Relevance to the query
5. Practical value

Respond with ONLY the candidate number (1-{len(responses)}) of the BEST response, followed by a brief 1-2 sentence explanation.
Format: "Candidate X: [reason]"
"""
        
        yield "--- Voting ---\n"
        
        self.logger.info("Counsel: Judge evaluating responses...", context=context)
        
        vote_result = ""
        for chunk in self.vera.stream_llm(self.vera.fast_llm, vote_prompt):
            chunk_text = extract_chunk_text(chunk)
            vote_result += chunk_text
            yield chunk_text
        
        yield "\n\n"
        
        # Parse vote
        match = re.search(r'Candidate\s+(\d+)', vote_result, re.IGNORECASE)
        
        if match:
            winner_idx = int(match.group(1)) - 1
            
            if 0 <= winner_idx < len(responses):
                winner_label, winner_response, winner_duration = responses[winner_idx]
                
                self.logger.success(f"🏆 Counsel vote winner: Candidate {winner_idx + 1} ({winner_label})", context=context)
                
                yield f"--- Selected Response ---\n"
                yield f"**{winner_label}** (selected by vote)\n\n"
                yield winner_response
                return
        
        # Fallback
        self.logger.warning("Could not parse vote result, using first response", context=context)
        label, response, duration = responses[0]
        
        yield f"--- Selected Response (Fallback) ---\n"
        yield f"**{label}**\n\n"
        yield response