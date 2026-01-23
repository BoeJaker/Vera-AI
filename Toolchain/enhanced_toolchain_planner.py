"""
Enhanced ToolChain Planner with Orchestration Integration
==========================================================
Drop-in replacement for ToolChainPlanner with:
- Intelligent plan generation with multiple strategies
- Automatic parallel execution detection
- Integration with Vera's orchestration system
- Agent routing support
- Streaming output throughout

Compatible with existing Vera.py - just replace the import!
"""

import json
import time
import logging
import re
import hashlib
from typing import List, Dict, Any, Optional, Generator, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


def extract_chunk_text(chunk):
    """Extract text from chunk object - consistent with vera_tasks"""
    if chunk is None:
        return ""
    if isinstance(chunk, str):
        return chunk
    if isinstance(chunk, dict):
        for key in ['text', 'content', 'message', 'data', 'output']:
            if key in chunk and chunk[key] is not None:
                return str(chunk[key])
        return str(chunk)
    if hasattr(chunk, 'text'):
        return str(chunk.text)
    if hasattr(chunk, 'content'):
        return str(chunk.content)
    return str(chunk)


# ============================================================================
# ENUMS & CONFIGURATIONS
# ============================================================================

class PlanningStrategy(Enum):
    """Different planning approaches for different task types"""
    STATIC = "static"              # Fixed plan upfront (default)
    DYNAMIC = "dynamic"            # Plan one step at a time based on results
    EXPLORATORY = "exploratory"    # Multiple alternatives explored in parallel
    QUICK = "quick"                # Fast, minimal plan for simple tasks
    MULTIPATH = "multipath"        # Branch and try different approaches
    COMPREHENSIVE = "comprehensive" # Deep, thorough multi-step plans


class ExecutionMode(Enum):
    """Execution strategies for tool chains"""
    SEQUENTIAL = "sequential"      # Execute steps one by one
    CONCURRENT_MULTIPATH = "concurrent_multipath"  # Execute multiple paths in parallel
    CONCURRENT_INDEPENDENT = "concurrent_independent"  # Execute independent steps concurrently
    AUTO = "auto"                  # Automatically detect and parallelize when possible


# ============================================================================
# PLAN TEMPLATES
# ============================================================================

class PlanTemplate:
    """Common patterns for creating thorough tool chains"""
    
    @staticmethod
    def web_research(query: str, depth: str = "standard") -> List[Dict]:
        """Template for comprehensive web research"""
        if depth == "quick":
            return [
                {"tool": "web_search", "input": query},
                {"tool": "fast_llm", "input": f"Analyze search results: {query}\n\nResults: {{prev}}"}
            ]
        elif depth == "standard":
            return [
                {"tool": "web_search", "input": query},
                {"tool": "web_search_deep", "input": "{prev}"},
                {"tool": "deep_llm", "input": f"Comprehensive answer to: {query}\n\nContent: {{prev}}"}
            ]
        else:  # deep
            return [
                {"tool": "web_search", "input": query},
                {"tool": "web_search_deep", "input": "{prev}"},
                {"tool": "deep_llm", "input": f"Analyze findings: {{prev}}"},
                {"tool": "fast_llm", "input": f"Synthesize into clear answer for: {query}\n\nFindings: {{prev}}"},
                {"tool": "write_file", "input": "research_report.md|||{prev}"}
            ]
    
    @staticmethod
    def code_task(task_description: str, language: str = "python") -> List[Dict]:
        """Template for coding tasks"""
        return [
            {"tool": "deep_llm", "input": f"Write {language} code for: {task_description}"},
            {"tool": language, "input": "{prev}"},
            {"tool": "fast_llm", "input": "Review output and suggest fixes if needed:\n{prev}"}
        ]
    
    @staticmethod
    def comparison_research(topic_a: str, topic_b: str) -> List[Dict]:
        """Template for comparing two things"""
        return [
            {"tool": "web_search", "input": topic_a},
            {"tool": "web_search_deep", "input": "{step_1}"},
            {"tool": "web_search", "input": topic_b},
            {"tool": "web_search_deep", "input": "{step_3}"},
            {"tool": "deep_llm", "input": f"Compare {topic_a} vs {topic_b}\n\n{topic_a}: {{step_2}}\n\n{topic_b}: {{step_4}}"}
        ]


# ============================================================================
# ENHANCED TOOLCHAIN PLANNER
# ============================================================================

class EnhancedToolChainPlanner:
    """
    Enhanced planner with automatic parallel execution and orchestrator integration.
    DROP-IN COMPATIBLE with existing ToolChainPlanner interface.
    """
    
    def __init__(self, agent, tools: List[Any], enable_orchestrator: bool = True):
        """
        Initialize planner - COMPATIBLE WITH EXISTING INTERFACE
        
        Args:
            agent: Vera agent instance
            tools: List of available tools
            enable_orchestrator: Use orchestrator for parallel execution (default: True)
        """
        self.agent = agent
        self.deep_llm = agent.deep_llm
        self.tool_llm = agent.tool_llm
        self.fast_llm = agent.fast_llm
        self.tools = tools
        
        # Logging
        self.logger = agent.logger if hasattr(agent, 'logger') else logger
        
        # Orchestrator integration
        self.enable_orchestrator = enable_orchestrator and hasattr(agent, 'orchestrator')
        self.orchestrator = agent.orchestrator if self.enable_orchestrator else None
        
        # Agent routing (if available)
        self.use_agents = hasattr(agent, 'agents') and agent.agents is not None
        if self.use_agents:
            try:
                from Vera.Orchestration.agent_integration import AgentTaskRouter
                self.agent_router = AgentTaskRouter(agent)
                self.logger.debug("Agent routing enabled for toolchain")
            except ImportError:
                self.use_agents = False
                self.agent_router = None
        else:
            self.agent_router = None
        
        # Templates
        self.templates = PlanTemplate()
        
        # Planning context
        self._last_query = None
        self._last_strategy = None
        self._execution_history = []
        
        self.logger.info(
            f"EnhancedToolChainPlanner initialized: "
            f"orchestrator={self.enable_orchestrator}, agents={self.use_agents}"
        )
    
    # ========================================================================
    # PLANNING METHODS (All yield for streaming)
    # ========================================================================
    
    def plan_tool_chain(
        self,
        query: str,
        strategy: PlanningStrategy = PlanningStrategy.STATIC,
        history_context: str = ""
    ) -> Generator:
        """
        Create a plan using the specified strategy.
        YIELDS planning output as it's generated.
        
        Args:
            query: User query
            strategy: Planning strategy to use
            history_context: Previous execution context
        
        Yields:
            Plan generation output, final plan as dict/list
        """
        self._last_query = query
        self._last_strategy = strategy
        
        self.logger.info(f"Planning with strategy: {strategy.value}")
        
        # Route to appropriate planning method
        if strategy == PlanningStrategy.QUICK:
            yield from self._plan_quick(query, history_context)
        elif strategy == PlanningStrategy.COMPREHENSIVE:
            yield from self._plan_comprehensive(query, history_context)
        elif strategy == PlanningStrategy.EXPLORATORY:
            yield from self._plan_exploratory(query, history_context)
        elif strategy == PlanningStrategy.MULTIPATH:
            yield from self._plan_multipath(query, history_context)
        elif strategy == PlanningStrategy.DYNAMIC:
            # Dynamic planning handled during execution
            yield from self._plan_static(query, history_context)
        else:  # STATIC (default)
            yield from self._plan_static(query, history_context)
    
    def _plan_static(self, query: str, history_context: str = "") -> Generator:
        """Create a comprehensive static plan"""
        
        planning_prompt = f"""Task: {query}
Context: {history_context}

Create a COMPLETE, THOROUGH plan using available tools.

Planning guidance:
- Break into clear, sequential steps
- For research: search → fetch content → analyze
- For coding: generate → execute → verify
- For data: load → process → analyze
- Use {prev} or {step_N} for result references
- Include all necessary steps

Create the complete tool chain plan as JSON array."""
        
        plan_json = ""
        
        # Use agent if available, otherwise use tool_llm
        if self.agent_router:
            try:
                agent_name = self.agent_router.get_agent_for_task('tool_execution')
                llm = self.agent_router.create_llm_for_agent(agent_name)
                self.logger.debug(f"Using agent for planning: {agent_name}")
            except Exception as e:
                self.logger.warning(f"Agent routing failed, using tool_llm: {e}")
                llm = self.tool_llm
        else:
            llm = self.tool_llm
        
        # Stream planning
        if hasattr(self.agent, 'stream_llm'):
            for chunk in self.agent.stream_llm(llm, planning_prompt):
                chunk_text = extract_chunk_text(chunk)
                yield chunk_text
                plan_json += chunk_text
        else:
            plan_json = llm.invoke(planning_prompt)
            yield plan_json
        
        # Clean and parse
        plan_json = self._clean_json(plan_json)
        
        try:
            tool_plan = json.loads(plan_json)
        except Exception as e:
            self.logger.error(f"Planning failed: {e}")
            raise ValueError(f"Planning failed: {e}\n\n{plan_json}")
        
        # Validate and enhance
        tool_plan = self._validate_and_enhance_plan(tool_plan)
        
        # Save plan
        plan_id = hashlib.sha256(
            f"{time.time()}_{json.dumps(tool_plan)}".encode()
        ).hexdigest()
        self._save_plan(tool_plan, plan_id)
        
        self.logger.info(f"Plan created: {len(tool_plan)} steps")
        
        yield tool_plan
    
    def _plan_quick(self, query: str, history_context: str = "") -> Generator:
        """Create minimal, fast plan"""
        
        prompt = f"""Task: {query}

Create MINIMAL plan (1-3 steps max) for this simple query.
Most direct path to answer. Be concise."""
        
        plan_json = ""
        
        if hasattr(self.agent, 'stream_llm'):
            for chunk in self.agent.stream_llm(self.fast_llm, prompt):
                chunk_text = extract_chunk_text(chunk)
                yield chunk_text
                plan_json += chunk_text
        else:
            plan_json = self.fast_llm.invoke(prompt)
            yield plan_json
        
        plan_json = self._clean_json(plan_json)
        tool_plan = json.loads(plan_json)
        
        if isinstance(tool_plan, dict):
            tool_plan = [tool_plan]
        
        plan_id = hashlib.sha256(
            f"{time.time()}_{json.dumps(tool_plan)}".encode()
        ).hexdigest()
        self._save_plan(tool_plan, plan_id)
        
        yield tool_plan
    
    def _plan_comprehensive(self, query: str, history_context: str = "") -> Generator:
        """Create exhaustive, thorough plan"""
        
        prompt = f"""Task: {query}
Previous: {history_context}

Create MOST COMPREHENSIVE plan possible.

Comprehensive approach:
- Granular steps 
- All research phases: search → fetch → parse → analyze
- Multiple analysis passes
- Verification steps
- Save intermediate and final outputs
- Plan for potential issues

Be extremely thorough."""
        
        plan_json = ""
        
        llm = self.agent_router.create_llm_for_agent(
            self.agent_router.get_agent_for_task('tool_execution')
        ) if self.agent_router else self.tool_llm
        
        if hasattr(self.agent, 'stream_llm'):
            for chunk in self.agent.stream_llm(llm, prompt):
                chunk_text = extract_chunk_text(chunk)
                yield chunk_text
                plan_json += chunk_text
        else:
            plan_json = llm.invoke(prompt)
            yield plan_json
        
        plan_json = self._clean_json(plan_json)
        tool_plan = json.loads(plan_json)
        
        plan_id = hashlib.sha256(
            f"{time.time()}_{json.dumps(tool_plan)}".encode()
        ).hexdigest()
        self._save_plan(tool_plan, plan_id)
        
        yield tool_plan
    
    def _plan_exploratory(self, query: str, history_context: str = "", 
                         max_alternatives: int = 3) -> Generator:
        """Create multiple alternative plans"""
        
        prompt = f"""Task: {query}

Create {max_alternatives} DIFFERENT alternative plans.

Each takes different approach/strategy.
Return as JSON:
{{
  "alternatives": [
    [steps for approach 1],
    [steps for approach 2],
    [steps for approach 3]
  ]
}}"""
        
        plan_json = ""
        
        llm = self.agent_router.create_llm_for_agent(
            self.agent_router.get_agent_for_task('tool_execution')
        ) if self.agent_router else self.tool_llm
        
        if hasattr(self.agent, 'stream_llm'):
            for chunk in self.agent.stream_llm(llm, prompt):
                chunk_text = extract_chunk_text(chunk)
                yield chunk_text
                plan_json += chunk_text
        else:
            plan_json = llm.invoke(prompt)
            yield plan_json
        
        plan_json = self._clean_json(plan_json)
        result = json.loads(plan_json)
        
        alternatives = result.get("alternatives", [result]) if isinstance(result, dict) else [result]
        
        plan_id = hashlib.sha256(
            f"{time.time()}_{json.dumps(alternatives)}".encode()
        ).hexdigest()
        self._save_plan(alternatives, plan_id)
        
        yield alternatives
    
    def _plan_multipath(self, query: str, history_context: str = "") -> Generator:
        """Create plan with branching paths"""
        
        prompt = f"""Task: {query}

Create plan with BRANCHING paths and fallback options.

Return as JSON:
{{
  "primary_path": [steps for main approach],
  "fallback_paths": [
    [steps for fallback 1],
    [steps for fallback 2]
  ]
}}"""
        
        plan_json = ""
        
        llm = self.agent_router.create_llm_for_agent(
            self.agent_router.get_agent_for_task('tool_execution')
        ) if self.agent_router else self.tool_llm
        
        if hasattr(self.agent, 'stream_llm'):
            for chunk in self.agent.stream_llm(llm, prompt):
                chunk_text = extract_chunk_text(chunk)
                yield chunk_text
                plan_json += chunk_text
        else:
            plan_json = llm.invoke(prompt)
            yield plan_json
        
        plan_json = self._clean_json(plan_json)
        result = json.loads(plan_json)
        
        yield result
    
    # ========================================================================
    # EXECUTION METHODS (All yield for streaming)
    # ========================================================================
    
    def execute_tool_chain(
        self,
        query: str,
        plan=None,
        strategy: PlanningStrategy = PlanningStrategy.STATIC,
        execution_mode: ExecutionMode = ExecutionMode.AUTO
    ) -> Generator:
        """
        Execute tool chain with automatic parallel execution.
        COMPATIBLE WITH EXISTING INTERFACE - yields all output.
        
        Args:
            query: User query
            plan: Pre-existing plan (optional)
            strategy: Planning strategy
            execution_mode: Execution mode (AUTO/sequential/concurrent)
        
        Yields:
            All execution output including plan, steps, results
        """
        # Generate plan if not provided
        if plan is None:
            gen = self.plan_tool_chain(query, strategy=strategy)
            for r in gen:
                yield r
                if isinstance(r, (list, dict)):
                    tool_plan = r
        else:
            tool_plan = plan
        
        # Handle different plan structures
        if isinstance(tool_plan, dict):
            if "primary_path" in tool_plan:
                if execution_mode == ExecutionMode.CONCURRENT_MULTIPATH:
                    yield from self._execute_concurrent_multipath(tool_plan, query)
                    return
                else:
                    tool_plan = tool_plan["primary_path"]
            elif "alternatives" in tool_plan:
                if execution_mode == ExecutionMode.CONCURRENT_MULTIPATH:
                    yield from self._execute_concurrent_alternatives(tool_plan["alternatives"], query)
                    return
                else:
                    tool_plan = tool_plan["alternatives"][0]
            else:
                tool_plan = [tool_plan]
        
        if not isinstance(tool_plan, list):
            yield "[Error] Invalid plan structure\n"
            return
        
        # AUTO-DETECT PARALLELIZATION
        if execution_mode in [ExecutionMode.AUTO, ExecutionMode.SEQUENTIAL]:
            concurrent_groups = self._find_concurrent_groups(tool_plan)
            has_parallel = any(len(group) > 1 for group in concurrent_groups)
            
            if has_parallel:
                parallel_groups_count = sum(1 for g in concurrent_groups if len(g) > 1)
                total_parallel_steps = sum(len(g) for g in concurrent_groups if len(g) > 1)
                
                yield f"\n╔══════════════════════════════════════════════════════════╗\n"
                yield f"║  🚀 AUTO-PARALLEL EXECUTION DETECTED                     ║\n"
                yield f"╠══════════════════════════════════════════════════════════╣\n"
                yield f"║  Parallel Groups: {parallel_groups_count:<43} ║\n"
                yield f"║  Steps to Parallelize: {total_parallel_steps:<38} ║\n"
                yield f"║  Execution Mode: CONCURRENT                              ║\n"
                yield f"╚══════════════════════════════════════════════════════════╝\n\n"
                
                yield self._format_dependency_analysis(tool_plan, concurrent_groups)
                
                execution_mode = ExecutionMode.CONCURRENT_INDEPENDENT
            else:
                yield f"\n[Execution] Sequential execution - no parallel opportunities\n"
        
        # Choose execution method
        if execution_mode == ExecutionMode.CONCURRENT_INDEPENDENT and self.enable_orchestrator:
            # Use orchestrator for parallel execution
            yield from self._execute_concurrent_orchestrator(tool_plan, query)
        elif execution_mode == ExecutionMode.CONCURRENT_INDEPENDENT:
            # Use threading for parallel execution
            yield from self._execute_concurrent_independent(tool_plan, query)
        else:
            # Sequential execution
            yield from self._execute_sequential(tool_plan, query)
    
    def _execute_sequential(self, plan: List[Dict], query: str) -> Generator:
        """Execute plan sequentially - COMPATIBLE WITH EXISTING INTERFACE"""
        executed = {}
        step_num = 0
        
        for step in plan:
            step_num += 1
            tool_name = step.get("tool")
            tool_input = str(step.get("input", ""))
            
            # Auto-added notification
            if step.get("_auto_added"):
                yield f"\n[Auto-added step {step_num}] {step.get('_reason', '')}\n"
            
            # Resolve placeholders
            if "{prev}" in tool_input:
                tool_input = tool_input.replace("{prev}", str(executed.get(f"step_{step_num-1}", "")))
            
            for i in range(1, step_num):
                tool_input = tool_input.replace(f"{{step_{i}}}", str(executed.get(f"step_{i}", "")))
            
            # Special handling for write_file
            if tool_name == "write_file" and "|||" in tool_input:
                path, content = tool_input.split("|||", 1)
                tool_input = json.dumps({"path": path.strip(), "content": content.strip()})
            
            # Inject memory for LLM tools
            if "llm" in tool_name.lower():
                try:
                    chat_hist = self.agent.buffer_memory.load_memory_variables({}).get("chat_history", "")
                    if chat_hist:
                        tool_input = f"Context: {chat_hist}\n{tool_input}"
                except:
                    pass
            
            yield f"\n[Step {step_num}] Executing: {tool_name}\n"
            yield f"[Input] {tool_input[:200]}{'...' if len(tool_input) > 200 else ''}\n"
            
            # Find tool
            tool = next((t for t in self.tools if getattr(t, "name", "") == tool_name), None)
            
            if not tool:
                result = f"ERROR: Tool not found: {tool_name}"
                yield result
                executed[f"step_{step_num}"] = result
                continue
            
            try:
                # Get callable
                if hasattr(tool, "run") and callable(tool.run):
                    func = tool.run
                elif hasattr(tool, "func") and callable(tool.func):
                    func = tool.func
                elif callable(tool):
                    func = tool
                else:
                    raise ValueError(f"Tool {tool_name} is not callable")
                
                # Execute
                collected = []
                result = ""
                try:
                    for chunk in func(tool_input):
                        chunk_text = extract_chunk_text(chunk)
                        yield chunk_text
                        collected.append(chunk_text)
                except TypeError:
                    # Not iterable
                    result = func(tool_input)
                    yield result
                else:
                    result = "".join(str(c) for c in collected)
                
                executed[f"step_{step_num}"] = result
                executed[tool_name] = result
                
                # Save to memory
                try:
                    self.agent.save_to_memory(f"Step {step_num} - {tool_name}", result)
                except:
                    pass
                
                yield f"\n[Step {step_num}] ✓ Complete\n"
                
            except Exception as e:
                error_msg = f"ERROR: {str(e)}"
                yield f"\n[Step {step_num}] ✗ Failed: {error_msg}\n"
                executed[f"step_{step_num}"] = error_msg
        
        # Final result
        final_result = executed.get(f"step_{step_num}", "")
        yield f"\n{'='*60}\n"
        yield f"[Final Result]\n{final_result}\n"
        yield f"{'='*60}\n"
        
        yield executed
    
    def _execute_concurrent_orchestrator(self, plan: List[Dict], query: str) -> Generator:
        """
        Execute independent steps concurrently using orchestrator.
        Submits tasks and streams results.
        """
        groups = self._find_concurrent_groups(plan)
        
        executed = {}
        step_num = 0
        
        for group_idx, group in enumerate(groups):
            if len(group) == 1:
                # Single step - execute normally
                step_idx = group[0]
                step_num = step_idx + 1
                step = plan[step_idx]
                
                yield f"\n➜ [Sequential Step {step_num}]\n"
                
                for chunk in self._execute_single_step(step, step_num, executed, plan):
                    if isinstance(chunk, dict) and "step_result" in chunk:
                        executed[f"step_{step_num}"] = chunk["step_result"]
                        executed[step.get("tool")] = chunk["step_result"]
                    else:
                        yield chunk
            
            else:
                # Multiple steps - execute via orchestrator
                yield f"\n╔══════════════════════════════════════════════════════════╗\n"
                yield f"║  🔀 CONCURRENT GROUP {group_idx + 1} (Orchestrator)            ║\n"
                yield f"║  Executing {len(group)} steps in parallel{' ' * (29 - len(str(len(group))))}║\n"
                yield f"╚══════════════════════════════════════════════════════════╝\n"
                
                # Submit all tasks
                task_ids = {}
                for step_idx in group:
                    step_num = step_idx + 1
                    step = plan[step_idx]
                    
                    tool_name = step.get("tool")
                    tool_input = self._resolve_placeholders(
                        str(step.get("input", "")),
                        step_num,
                        executed
                    )
                    
                    yield f"  ⚡ Launching Step {step_num}: {tool_name}\n"
                    
                    # Submit via orchestrator
                    task_id = self.orchestrator.submit_task(
                        "tool.single",
                        tool_name=tool_name,
                        tool_input=tool_input
                    )
                    task_ids[task_id] = (step_num, step)
                
                # Collect results
                completed = 0
                for task_id, (step_num, step) in task_ids.items():
                    try:
                        # Stream result
                        result_chunks = []
                        for chunk in self.orchestrator.stream_result(task_id, timeout=60.0):
                            chunk_text = extract_chunk_text(chunk)
                            result_chunks.append(chunk_text)
                        
                        result = "".join(result_chunks)
                        completed += 1
                        
                        yield f"  ✓ [Step {step_num}] Complete ({completed}/{len(group)})\n"
                        
                        executed[f"step_{step_num}"] = result
                        executed[step.get("tool")] = result
                    
                    except Exception as e:
                        yield f"  ✗ [Step {step_num}] Failed: {e}\n"
                        executed[f"step_{step_num}"] = f"ERROR: {e}"
                
                yield f"\n  🎯 All {len(group)} parallel steps completed!\n"
        
        # Final result
        final_step = len(plan)
        final_result = executed.get(f"step_{final_step}", "")
        yield f"\n{'='*60}\n"
        yield f"[Final Result]\n{final_result}\n"
        yield f"{'='*60}\n"
        
        yield executed
    
    def _execute_concurrent_independent(self, plan: List[Dict], query: str) -> Generator:
        """Execute independent steps concurrently using threading"""
        groups = self._find_concurrent_groups(plan)
        
        executed = {}
        step_num = 0
        
        for group_idx, group in enumerate(groups):
            if len(group) == 1:
                # Single step
                step_idx = group[0]
                step_num = step_idx + 1
                step = plan[step_idx]
                
                yield f"\n➜ [Sequential Step {step_num}]\n"
                
                for chunk in self._execute_single_step(step, step_num, executed, plan):
                    if isinstance(chunk, dict) and "step_result" in chunk:
                        executed[f"step_{step_num}"] = chunk["step_result"]
                        executed[step.get("tool")] = chunk["step_result"]
                    else:
                        yield chunk
            
            else:
                # Multiple steps - threading
                yield f"\n╔══════════════════════════════════════════════════════════╗\n"
                yield f"║  🔀 CONCURRENT GROUP {group_idx + 1:<42} ║\n"
                yield f"║  Executing {len(group)} steps in parallel{' ' * (29 - len(str(len(group))))}║\n"
                yield f"╚══════════════════════════════════════════════════════════╝\n"
                
                with ThreadPoolExecutor(max_workers=len(group)) as executor:
                    futures = {}
                    for step_idx in group:
                        step_num = step_idx + 1
                        step = plan[step_idx]
                        yield f"  ⚡ Launching Step {step_num}: {step.get('tool')}\n"
                        future = executor.submit(
                            self._execute_step_sync,
                            step, step_num, executed, plan
                        )
                        futures[future] = (step_num, step)
                    
                    completed_count = 0
                    for future in as_completed(futures):
                        step_num, step = futures[future]
                        completed_count += 1
                        try:
                            result = future.result()
                            yield f"  ✓ [Step {step_num}] Complete ({completed_count}/{len(group)})\n"
                            executed[f"step_{step_num}"] = result
                            executed[step.get("tool")] = result
                        except Exception as e:
                            yield f"  ✗ [Step {step_num}] Failed: {e}\n"
                            executed[f"step_{step_num}"] = f"ERROR: {e}"
                
                yield f"\n  🎯 All {len(group)} parallel steps completed!\n"
        
        # Final result
        final_step = len(plan)
        final_result = executed.get(f"step_{final_step}", "")
        yield f"\n{'='*60}\n"
        yield f"[Final Result]\n{final_result}\n"
        yield f"{'='*60}\n"
        
        yield executed
    
    def _execute_concurrent_multipath(self, multipath_plan: Dict, query: str) -> Generator:
        """Execute multiple paths concurrently"""
        primary = multipath_plan.get("primary_path", [])
        fallbacks = multipath_plan.get("fallback_paths", [])
        
        all_paths = [primary] + fallbacks
        
        yield f"\n[Multipath Execution] Running {len(all_paths)} path(s) concurrently\n"
        
        with ThreadPoolExecutor(max_workers=len(all_paths)) as executor:
            futures = {}
            for idx, path in enumerate(all_paths):
                path_name = "Primary" if idx == 0 else f"Fallback {idx}"
                future = executor.submit(self._execute_path_sync, path, path_name)
                futures[future] = path_name
            
            results = {}
            for future in as_completed(futures):
                path_name = futures[future]
                try:
                    result = future.result()
                    yield f"\n[{path_name}] ✓ Complete\n"
                    results[path_name] = result
                except Exception as e:
                    yield f"\n[{path_name}] ✗ Failed: {e}\n"
                    results[path_name] = f"ERROR: {e}"
        
        yield f"\n{'='*60}\n"
        yield "[Multipath Results]\n"
        for path_name, result in results.items():
            yield f"\n{path_name}: {result}\n"
        yield f"{'='*60}\n"
        
        yield results
    
    def _execute_concurrent_alternatives(self, alternatives: List[List[Dict]], query: str) -> Generator:
        """Execute alternative plans concurrently"""
        yield f"\n[Exploratory Execution] Running {len(alternatives)} alternative(s) concurrently\n"
        
        with ThreadPoolExecutor(max_workers=len(alternatives)) as executor:
            futures = {}
            for idx, plan in enumerate(alternatives):
                future = executor.submit(self._execute_path_sync, plan, f"Alternative {idx + 1}")
                futures[future] = f"Alternative {idx + 1}"
            
            results = {}
            for future in as_completed(futures):
                alt_name = futures[future]
                try:
                    result = future.result()
                    yield f"\n[{alt_name}] ✓ Complete\n"
                    results[alt_name] = result
                except Exception as e:
                    yield f"\n[{alt_name}] ✗ Failed: {e}\n"
                    results[alt_name] = f"ERROR: {e}"
        
        yield f"\n{'='*60}\n"
        yield "[Exploratory Results]\n"
        for alt_name, result in results.items():
            yield f"\n{alt_name}: {result}\n"
        yield f"{'='*60}\n"
        
        yield results
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def _execute_single_step(
        self,
        step: Dict,
        step_num: int,
        executed: Dict,
        plan: List[Dict]
    ) -> Generator:
        """Execute a single step and yield results"""
        tool_name = step.get("tool")
        tool_input = self._resolve_placeholders(
            str(step.get("input", "")),
            step_num,
            executed
        )
        
        if step.get("_auto_added"):
            yield f"\n[Auto-added step {step_num}] {step.get('_reason', '')}\n"
        
        # Special handling for write_file
        if tool_name == "write_file" and "|||" in tool_input:
            path, content = tool_input.split("|||", 1)
            tool_input = json.dumps({"path": path.strip(), "content": content.strip()})
        
        yield f"\n[Step {step_num}] Executing: {tool_name}\n"
        yield f"[Input] {tool_input[:200]}{'...' if len(tool_input) > 200 else ''}\n"
        
        # Find tool
        tool = next((t for t in self.tools if getattr(t, "name", "") == tool_name), None)
        
        if not tool:
            result = f"ERROR: Tool not found: {tool_name}"
            yield result
            yield {"step_result": result}
            return
        
        try:
            # Get callable
            if hasattr(tool, "run") and callable(tool.run):
                func = tool.run
            elif hasattr(tool, "func") and callable(tool.func):
                func = tool.func
            elif callable(tool):
                func = tool
            else:
                raise ValueError(f"Tool {tool_name} is not callable")
            
            # Execute
            collected = []
            result = ""
            try:
                for chunk in func(tool_input):
                    chunk_text = extract_chunk_text(chunk)
                    yield chunk_text
                    collected.append(chunk_text)
            except TypeError:
                result = func(tool_input)
                yield result
            else:
                result = "".join(str(c) for c in collected)
            
            yield {"step_result": result}
            
        except Exception as e:
            error_msg = f"ERROR: {str(e)}"
            yield f"\n[Step {step_num}] ✗ Failed: {error_msg}\n"
            yield {"step_result": error_msg}
    
    def _execute_step_sync(
        self,
        step: Dict,
        step_num: int,
        executed: Dict,
        plan: List[Dict]
    ) -> str:
        """Execute a single step synchronously (for concurrent execution)"""
        tool_name = step.get("tool")
        tool_input = self._resolve_placeholders(
            str(step.get("input", "")),
            step_num,
            executed
        )
        
        # Special handling for write_file
        if tool_name == "write_file" and "|||" in tool_input:
            path, content = tool_input.split("|||", 1)
            tool_input = json.dumps({"path": path.strip(), "content": content.strip()})
        
        # Find tool
        tool = next((t for t in self.tools if getattr(t, "name", "") == tool_name), None)
        
        if not tool:
            raise ValueError(f"Tool not found: {tool_name}")
        
        # Get callable
        if hasattr(tool, "run") and callable(tool.run):
            func = tool.run
        elif hasattr(tool, "func") and callable(tool.func):
            func = tool.func
        elif callable(tool):
            func = tool
        else:
            raise ValueError(f"Tool {tool_name} is not callable")
        
        # Execute and collect
        collected = []
        try:
            for chunk in func(tool_input):
                collected.append(extract_chunk_text(chunk))
        except TypeError:
            return func(tool_input)
        
        return "".join(str(c) for c in collected)
    
    def _execute_path_sync(self, plan: List[Dict], path_name: str) -> str:
        """Execute a complete path synchronously"""
        executed = {}
        step_num = 0
        
        for step in plan:
            step_num += 1
            result = self._execute_step_sync(step, step_num, executed, plan)
            executed[f"step_{step_num}"] = result
            executed[step.get("tool")] = result
        
        return executed.get(f"step_{step_num}", "")
    
    def _resolve_placeholders(self, tool_input: str, step_num: int, executed: Dict) -> str:
        """Resolve {prev} and {step_N} placeholders"""
        if "{prev}" in tool_input:
            tool_input = tool_input.replace("{prev}", str(executed.get(f"step_{step_num-1}", "")))
        
        for i in range(1, step_num):
            tool_input = tool_input.replace(f"{{step_{i}}}", str(executed.get(f"step_{i}", "")))
        
        return tool_input
    
    def _analyze_dependencies(self, plan: List[Dict]) -> Dict[int, Set[int]]:
        """Analyze which steps depend on which other steps"""
        dependencies = {}
        
        for i, step in enumerate(plan):
            deps = set()
            tool_input = str(step.get("input", ""))
            
            if "{prev}" in tool_input:
                if i > 0:
                    deps.add(i - 1)
            
            for j in range(i):
                if f"{{step_{j+1}}}" in tool_input:
                    deps.add(j)
            
            dependencies[i] = deps
        
        return dependencies
    
    def _find_concurrent_groups(self, plan: List[Dict]) -> List[List[int]]:
        """Find groups of steps that can execute concurrently"""
        dependencies = self._analyze_dependencies(plan)
        groups = []
        executed = set()
        
        while len(executed) < len(plan):
            ready = []
            for i in range(len(plan)):
                if i not in executed and dependencies[i].issubset(executed):
                    ready.append(i)
            
            if not ready:
                break
            
            groups.append(ready)
            executed.update(ready)
        
        return groups
    
    def _format_dependency_analysis(self, plan: List[Dict], groups: List[List[int]]) -> str:
        """Format dependency analysis visualization"""
        output = "[Dependency Analysis]\n"
        output += "─" * 60 + "\n"
        
        for group_idx, group in enumerate(groups):
            if len(group) > 1:
                output += f"\n🔀 Concurrent Group {group_idx + 1} (can run in parallel):\n"
                for step_idx in group:
                    step = plan[step_idx]
                    output += f"   • Step {step_idx + 1}: {step.get('tool')} "
                    
                    tool_input = str(step.get("input", ""))
                    deps = []
                    if "{prev}" in tool_input and step_idx > 0:
                        deps.append(f"step {step_idx}")
                    for i in range(step_idx):
                        if f"{{step_{i+1}}}" in tool_input:
                            deps.append(f"step {i+1}")
                    
                    if deps:
                        output += "(depends on: " + ", ".join(deps) + ")"
                    else:
                        output += "(no dependencies)"
                    output += "\n"
            else:
                step_idx = group[0]
                step = plan[step_idx]
                output += f"\n➜ Sequential Step {step_idx + 1}: {step.get('tool')}\n"
        
        output += "─" * 60 + "\n"
        return output
    
    def _validate_and_enhance_plan(self, plan: List[Dict]) -> List[Dict]:
        """Validate and enhance plan for completeness"""
        if isinstance(plan, dict):
            plan = [plan]
        
        enhanced_plan = []
        
        for i, step in enumerate(plan):
            enhanced_plan.append(step)
            
            # Auto-add web_search_deep after web_search
            if step.get("tool") == "web_search":
                if i + 1 < len(plan):
                    next_step = plan[i + 1]
                    if next_step.get("tool") != "web_search_deep":
                        enhanced_plan.append({
                            "tool": "web_search_deep",
                            "input": "{prev}",
                            "_auto_added": True,
                            "_reason": "Fetch actual content from search results"
                        })
                else:
                    enhanced_plan.append({
                        "tool": "web_search_deep",
                        "input": "{prev}",
                        "_auto_added": True,
                        "_reason": "Fetch actual content from search results"
                    })
        
        return enhanced_plan
    
    def _clean_json(self, text: str) -> str:
        """Remove markdown code fences and clean JSON"""
        text = re.sub(r'^```json\s*', '', text.strip())
        text = re.sub(r'^```\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        return text.strip()
    
    def _save_plan(self, plan: Any, plan_id: str):
        """Save plan to memory and file"""
        try:
            # Save to file
            import os
            os.makedirs("./Configuration", exist_ok=True)
            with open("./Configuration/last_tool_plan.json", "w", encoding="utf-8") as f:
                json.dump(plan, f, indent=2)
            
            # Save to memory if available
            if hasattr(self.agent, "mem") and hasattr(self.agent, "sess"):
                self.agent.mem.add_session_memory(
                    self.agent.sess.id,
                    json.dumps(plan),
                    "Plan",
                    {
                        "topic": "plan",
                        "plan_id": plan_id,
                        "strategy": self._last_strategy.value if self._last_strategy else "static"
                    },
                    promote=True
                )
        except Exception as e:
            self.logger.warning(f"Failed to save plan: {e}")


# ============================================================================
# DROP-IN REPLACEMENT ALIAS
# ============================================================================

# For backward compatibility
ToolChainPlanner = EnhancedToolChainPlanner