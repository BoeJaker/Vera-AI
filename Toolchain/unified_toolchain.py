"""
Unified ToolChain Planner
=========================
Combines features from all toolchain implementations:
- Enhanced parallel execution and orchestration (from EnhancedToolChainPlanner)
- Domain-based expert routing (from ExpertToolChainPlanner)
- Multi-stage specialist planning (from FiveStageToolChain)
- Original reliable execution (from ToolChainPlanner - fallback)

Configuration Modes:
- SIMPLE: Original ToolChainPlanner behavior (default fallback)
- ENHANCED: Auto-parallel with orchestration
- EXPERT: Domain expert routing
- FIVE_STAGE: Full multi-stage specialist planning
- AUTO: Intelligent selection based on query complexity

All modes stream output and support the orchestrator.
"""

import json
import time
import logging
import re
import hashlib
import traceback
from typing import List, Dict, Any, Optional, Generator, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def extract_chunk_text(chunk):
    """Extract text from chunk object - consistent across all implementations"""
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
# CONFIGURATION ENUMS
# ============================================================================

class ToolChainMode(Enum):
    """Execution modes for unified toolchain"""
    SIMPLE = "simple"              # Original ToolChainPlanner
    ENHANCED = "enhanced"          # EnhancedToolChainPlanner features
    EXPERT = "expert"              # Domain expert routing
    FIVE_STAGE = "five_stage"      # Full multi-stage planning
    AUTO = "auto"                  # Intelligent mode selection


class PlanningStrategy(Enum):
    """Planning approaches"""
    STATIC = "static"              # Fixed plan upfront (default)
    DYNAMIC = "dynamic"            # Plan one step at a time
    EXPLORATORY = "exploratory"    # Multiple alternatives in parallel
    QUICK = "quick"                # Fast, minimal plan
    MULTIPATH = "multipath"        # Branch with fallback paths
    COMPREHENSIVE = "comprehensive" # Deep, thorough multi-step


class ExecutionMode(Enum):
    """Execution strategies"""
    SEQUENTIAL = "sequential"      # Execute steps one by one
    CONCURRENT_MULTIPATH = "concurrent_multipath"
    CONCURRENT_INDEPENDENT = "concurrent_independent"
    AUTO = "auto"                  # Auto-detect parallelization


# ============================================================================
# DOMAIN SYSTEM (from Expert implementation)
# ============================================================================

class Domain(Enum):
    """Supported expert domains"""
    WEB_DEVELOPMENT = "web_development"
    BACKEND_DEVELOPMENT = "backend_development"
    DATABASE = "database"
    DEVOPS = "devops"
    SECURITY = "security"
    NETWORKING = "networking"
    DATA_ANALYSIS = "data_analysis"
    MACHINE_LEARNING = "machine_learning"
    DATA_ENGINEERING = "data_engineering"
    RESEARCH = "research"
    WRITING = "writing"
    DOCUMENTATION = "documentation"
    FILE_OPERATIONS = "file_operations"
    CODE_EXECUTION = "code_execution"
    SYSTEM_ADMINISTRATION = "system_administration"
    API_INTEGRATION = "api_integration"
    WEB_SCRAPING = "web_scraping"
    EMAIL = "email"
    OSINT = "osint"
    PENETRATION_TESTING = "penetration_testing"
    VULNERABILITY_ANALYSIS = "vulnerability_analysis"
    BASH = "bash"
    PYTHON = "python"
    GENERAL = "general"


@dataclass
class DomainToolMetadata:
    """Metadata for domain-tagged tools"""
    tool_name: str
    domains: Set[Domain]
    priority: int = 1
    requires_authentication: bool = False
    cost_level: int = 0
    description_override: Optional[str] = None


class ToolDomainRegistry:
    """Registry mapping tools to domains"""
    
    def __init__(self):
        self.tool_domains: Dict[str, DomainToolMetadata] = {}
        self._initialize_default_mappings()
    
    def _initialize_default_mappings(self):
        """Initialize default tool → domain mappings"""
        # File operations
        self.register("read_file", {Domain.FILE_OPERATIONS}, priority=3)
        self.register("write_file", {Domain.FILE_OPERATIONS}, priority=3)
        self.register("list_directory", {Domain.FILE_OPERATIONS}, priority=2)
        self.register("search_files", {Domain.FILE_OPERATIONS}, priority=2)
        
        # Code execution
        self.register("python", {Domain.CODE_EXECUTION, Domain.DATA_ANALYSIS}, priority=3)
        self.register("bash", {Domain.SYSTEM_ADMINISTRATION, Domain.DEVOPS}, priority=3)
        
        # Web & research
        self.register("web_search", {Domain.RESEARCH, Domain.WEB_SCRAPING}, priority=3)
        self.register("news_search", {Domain.RESEARCH}, priority=2)
        self.register("web_search_deep", {Domain.RESEARCH, Domain.WEB_SCRAPING}, priority=2)
        
        # API & HTTP
        self.register("http_request", {Domain.API_INTEGRATION, Domain.WEB_DEVELOPMENT}, priority=3)
        self.register("babelfish", {Domain.API_INTEGRATION, Domain.NETWORKING}, priority=2)
        
        # Database
        self.register("sqlite_query", {Domain.DATABASE, Domain.DATA_ANALYSIS}, priority=3)
        
        # Security & OSINT
        self.register("nmap_scan", {Domain.SECURITY, Domain.NETWORKING, Domain.OSINT}, priority=3)
        self.register("vulnerability_search", {Domain.SECURITY, Domain.VULNERABILITY_ANALYSIS}, priority=3)
        
        # LLM tasks
        self.register("fast_llm", {Domain.GENERAL, Domain.WRITING}, priority=2)
        self.register("deep_llm", {Domain.RESEARCH, Domain.WRITING, Domain.DOCUMENTATION}, priority=2)
    
    def register(self, tool_name: str, domains: Set[Domain], priority: int = 1, 
                requires_auth: bool = False, cost_level: int = 0, 
                description: Optional[str] = None):
        """Register a tool with domain tags"""
        self.tool_domains[tool_name] = DomainToolMetadata(
            tool_name=tool_name,
            domains=domains,
            priority=priority,
            requires_authentication=requires_auth,
            cost_level=cost_level,
            description_override=description
        )
    
    def get_domains(self, tool_name: str) -> Set[Domain]:
        """Get domains for a tool"""
        if tool_name in self.tool_domains:
            return self.tool_domains[tool_name].domains
        return {Domain.GENERAL}
    
    def get_tools_for_domains(self, domains: Set[Domain]) -> List[str]:
        """Get all tools tagged with any of the specified domains"""
        tools = set()
        for domain in domains:
            for name, meta in self.tool_domains.items():
                if domain in meta.domains:
                    tools.add(name)
        return list(tools)


# ============================================================================
# UNIFIED TOOLCHAIN PLANNER
# ============================================================================

class UnifiedToolChainPlanner:
    """
    Unified toolchain combining all implementations with configurable modes.
    
    Modes:
    - SIMPLE: Original reliable execution (default fallback)
    - ENHANCED: Auto-parallel with orchestration
    - EXPERT: Domain expert routing
    - FIVE_STAGE: Multi-stage specialist planning
    - AUTO: Intelligent selection
    
    All modes support:
    - Streaming output
    - Orchestrator integration
    - Agent routing
    - Memory integration
    - Error recovery
    """
    
    def __init__(self, agent, tools: List[Any], 
                 mode: ToolChainMode = ToolChainMode.AUTO,
                 enable_orchestrator: bool = True):
        """
        Initialize unified toolchain planner
        
        Args:
            agent: Vera agent instance
            tools: List of available tools
            mode: Execution mode (SIMPLE, ENHANCED, EXPERT, FIVE_STAGE, AUTO)
            enable_orchestrator: Use orchestrator for parallel execution
        """
        self.agent = agent
        self.tools = tools
        self.mode = mode
        
        # LLM references
        self.deep_llm = agent.deep_llm
        self.tool_llm = agent.tool_llm
        self.fast_llm = agent.fast_llm
        
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
                self.logger.debug("Agent routing enabled for unified toolchain")
            except ImportError:
                self.use_agents = False
                self.agent_router = None
        else:
            self.agent_router = None
        
        # Domain registry (for EXPERT and FIVE_STAGE modes)
        self.domain_registry = ToolDomainRegistry()
        
        # Planning context
        self._last_query = None
        self._last_strategy = None
        self._execution_history = []
        
        self.logger.info(
            f"UnifiedToolChainPlanner initialized: mode={mode.value}, "
            f"orchestrator={self.enable_orchestrator}, agents={self.use_agents}"
        )
    
    # ========================================================================
    # MODE SELECTION
    # ========================================================================
    
    def _select_mode(self, query: str) -> ToolChainMode:
        """Intelligently select mode based on query complexity"""
        if self.mode != ToolChainMode.AUTO:
            return self.mode
        
        # Simple heuristics for mode selection
        query_lower = query.lower()
        
        # Complex research/analysis → FIVE_STAGE
        if any(word in query_lower for word in ['research', 'analyze', 'investigate', 'comprehensive']):
            if len(query.split()) > 20:
                return ToolChainMode.FIVE_STAGE
        
        # Domain-specific tasks → EXPERT
        domain_keywords = {
            'security': Domain.SECURITY,
            'hack': Domain.PENETRATION_TESTING,
            'vulnerability': Domain.VULNERABILITY_ANALYSIS,
            'database': Domain.DATABASE,
            'api': Domain.API_INTEGRATION,
        }
        
        if any(keyword in query_lower for keyword in domain_keywords.keys()):
            return ToolChainMode.EXPERT
        
        # Parallel opportunities → ENHANCED
        if 'and' in query_lower or ',' in query:
            return ToolChainMode.ENHANCED
        
        # Default to SIMPLE for straightforward tasks
        return ToolChainMode.SIMPLE
    
    # ========================================================================
    # UNIFIED INTERFACE
    # ========================================================================
    
    def plan_tool_chain(self, query: str, 
                       strategy: PlanningStrategy = PlanningStrategy.STATIC,
                       history_context: str = "") -> Generator:
        """
        Create a plan using the configured mode and strategy.
        
        Args:
            query: User query
            strategy: Planning strategy
            history_context: Previous execution context
        
        Yields:
            Planning output and final plan
        """
        selected_mode = self._select_mode(query)
        
        self.logger.info(
            f"Planning with mode={selected_mode.value}, strategy={strategy.value}"
        )
        
        # Route to appropriate implementation
        if selected_mode == ToolChainMode.SIMPLE:
            yield from self._plan_simple(query, history_context)
        
        elif selected_mode == ToolChainMode.ENHANCED:
            yield from self._plan_enhanced(query, strategy, history_context)
        
        elif selected_mode == ToolChainMode.EXPERT:
            yield from self._plan_expert(query, history_context)
        
        elif selected_mode == ToolChainMode.FIVE_STAGE:
            yield from self._plan_five_stage(query, history_context)
        
        else:
            # Fallback to simple
            yield from self._plan_simple(query, history_context)
    
    def execute_tool_chain(self, query: str, plan=None,
                          strategy: PlanningStrategy = PlanningStrategy.STATIC,
                          execution_mode: ExecutionMode = ExecutionMode.AUTO) -> Generator:
        """
        Execute tool chain with the configured mode.
        
        Args:
            query: User query
            plan: Pre-existing plan (optional)
            strategy: Planning strategy
            execution_mode: Execution mode
        
        Yields:
            All execution output
        """
        selected_mode = self._select_mode(query)
        
        self.logger.info(
            f"Executing with mode={selected_mode.value}, "
            f"execution_mode={execution_mode.value}"
        )
        
        # Route to appropriate implementation
        if selected_mode == ToolChainMode.SIMPLE:
            yield from self._execute_simple(query, plan)
        
        elif selected_mode == ToolChainMode.ENHANCED:
            yield from self._execute_enhanced(query, plan, strategy, execution_mode)
        
        elif selected_mode == ToolChainMode.EXPERT:
            yield from self._execute_expert(query, plan)
        
        elif selected_mode == ToolChainMode.FIVE_STAGE:
            yield from self._execute_five_stage(query)
        
        else:
            # Fallback to simple
            yield from self._execute_simple(query, plan)
    
    # ========================================================================
    # SIMPLE MODE (Original ToolChainPlanner - Document 2)
    # ========================================================================
    
    def _plan_simple(self, query: str, history_context: str = "") -> Generator:
        """Simple planning - original ToolChainPlanner approach"""
        
        planning_prompt = f"""
You are a rigorous, disciplined system planner. You generate ONLY a JSON array describing tool invocations. No commentary, no markdown, no prose.

The user query is:
{query}
"""
        
        plan_json = ""
        
        # Stream and accumulate the plan
        for r in self.agent.stream_llm(self.tool_llm, planning_prompt):
            chunk_text = extract_chunk_text(r)
            yield chunk_text
            plan_json += chunk_text
        
        # Clean formatting
        plan_json = self._clean_json(plan_json)
        
        try:
            tool_plan = json.loads(plan_json)
        except Exception as e:
            raise ValueError(f"Planning failed: {e}\n\n{plan_json}")
        
        # Normalize to list
        if isinstance(tool_plan, dict):
            tool_plan = [tool_plan]
        
        # Save plan
        self._save_plan(tool_plan, "simple")
        
        yield tool_plan
    
    def _execute_simple(self, query: str, plan=None) -> Generator:
        """Simple execution - original ToolChainPlanner approach"""
        
        # Get plan if not provided
        if plan is None:
            gen = self._plan_simple(query)
            tool_plan = None
            for r in gen:
                if isinstance(r, list):
                    tool_plan = r
                else:
                    yield r
            
            if tool_plan is None:
                raise ValueError("No plan generated")
        else:
            tool_plan = plan
        
        # Execute sequentially with placeholder resolution
        tool_outputs = {}
        step_num = 0
        
        for step in tool_plan:
            step_num += 1
            tool_name = step.get("tool")
            raw_input = step.get("input", "")
            
            # Resolve placeholders
            tool_input = self._resolve_placeholders_simple(
                raw_input, step_num, tool_outputs
            )
            
            # Inject memory for LLM tools
            if "llm" in tool_name.lower():
                try:
                    chat_hist = self.agent.buffer_memory.load_memory_variables({}).get("chat_history", "")
                    if chat_hist:
                        if isinstance(tool_input, str):
                            tool_input = f"Context: {chat_hist}\n{tool_input}"
                except:
                    pass
            
            yield f"\n[Step {step_num}] Executing: {tool_name}\n"
            
            # Find tool
            tool = next((t for t in self.tools if getattr(t, "name", "") == tool_name), None)
            
            if not tool:
                result = f"ERROR: Tool not found: {tool_name}"
                yield result
                tool_outputs[f"step_{step_num}"] = result
                continue
            
            try:
                # Execute tool
                result = self._execute_tool_simple(tool, tool_name, tool_input)
                
                # Handle streaming vs non-streaming
                collected = []
                final_result = ""
                
                if hasattr(result, '__iter__') and not isinstance(result, (str, bytes, dict)):
                    for chunk in result:
                        chunk_text = extract_chunk_text(chunk)
                        yield chunk_text
                        collected.append(chunk_text)
                    final_result = "".join(str(c) for c in collected)
                else:
                    final_result = str(result)
                    yield final_result
                
                tool_outputs[f"step_{step_num}"] = final_result
                tool_outputs[tool_name] = final_result
                
                # Save to memory
                try:
                    self.agent.save_to_memory(f"Step {step_num} - {tool_name}", final_result)
                except:
                    pass
                
                yield f"\n[Step {step_num}] ✓ Complete\n"
            
            except Exception as e:
                error_msg = f"ERROR: {str(e)}\n{traceback.format_exc()}"
                yield f"\n[Step {step_num}] ✗ Failed: {error_msg}\n"
                tool_outputs[f"step_{step_num}"] = error_msg
        
        # Final result
        final_result = tool_outputs.get(f"step_{step_num}", "")
        yield f"\n{'='*60}\n[Final Result]\n{final_result}\n{'='*60}\n"
        
        yield tool_outputs
    
    def _resolve_placeholders_simple(self, value, step_num: int, 
                                    tool_outputs: Dict[str, str]) -> Any:
        """Resolve {prev} and {step_N} placeholders - simple mode"""
        
        # Handle dict input (multi-parameter tools)
        if isinstance(value, dict):
            resolved = {}
            for key, val in value.items():
                if isinstance(val, str):
                    # Replace {prev}
                    if "{prev}" in val:
                        prev_output = str(tool_outputs.get(f"step_{step_num-1}", ""))
                        val = val.replace("{prev}", prev_output)
                    
                    # Replace {step_N}
                    for i in range(1, step_num):
                        placeholder = f"{{step_{i}}}"
                        if placeholder in val:
                            step_output = str(tool_outputs.get(f"step_{i}", ""))
                            val = val.replace(placeholder, step_output)
                
                resolved[key] = val
            return resolved
        
        # Handle string input
        if isinstance(value, str):
            # Replace {prev}
            if "{prev}" in value:
                prev_output = str(tool_outputs.get(f"step_{step_num-1}", ""))
                value = value.replace("{prev}", prev_output)
            
            # Replace {step_N}
            for i in range(1, step_num):
                placeholder = f"{{step_{i}}}"
                if placeholder in value:
                    step_output = str(tool_outputs.get(f"step_{i}", ""))
                    value = value.replace(placeholder, step_output)
            
            # Try to parse as JSON if it looks like a dict
            stripped = value.strip()
            if (stripped.startswith('{') and stripped.endswith('}')) or \
               (stripped.startswith('[') and stripped.endswith(']')):
                try:
                    parsed = json.loads(stripped)
                    if isinstance(parsed, dict):
                        return parsed
                except json.JSONDecodeError:
                    try:
                        import ast
                        parsed = ast.literal_eval(stripped)
                        if isinstance(parsed, dict):
                            return parsed
                    except:
                        pass
        
        return value
    
    def _execute_tool_simple(self, tool, tool_name: str, tool_input: Any):
        """Execute a single tool - simple mode"""
        
        # Get the actual function to call
        if hasattr(tool, 'run') and callable(tool.run):
            func = tool.run
        elif hasattr(tool, 'invoke') and callable(tool.invoke):
            func = tool.invoke
        elif hasattr(tool, 'func') and callable(tool.func):
            func = tool.func
        elif callable(tool):
            func = tool
        else:
            raise ValueError(f"Tool '{tool_name}' is not callable")
        
        # Execute with proper argument unpacking
        if isinstance(tool_input, dict):
            return func(**tool_input)
        else:
            return func(tool_input)
    
    # ========================================================================
    # ENHANCED MODE (EnhancedToolChainPlanner features)
    # ========================================================================
    
    def _plan_enhanced(self, query: str, strategy: PlanningStrategy,
                      history_context: str = "") -> Generator:
        """Enhanced planning with multiple strategies"""
        
        if strategy == PlanningStrategy.QUICK:
            yield from self._plan_quick(query)
        elif strategy == PlanningStrategy.COMPREHENSIVE:
            yield from self._plan_comprehensive(query, history_context)
        elif strategy == PlanningStrategy.EXPLORATORY:
            yield from self._plan_exploratory(query)
        elif strategy == PlanningStrategy.MULTIPATH:
            yield from self._plan_multipath(query)
        else:
            yield from self._plan_static_enhanced(query, history_context)
    
    def _plan_static_enhanced(self, query: str, history_context: str = "") -> Generator:
        """Enhanced static planning"""
        
        planning_prompt = f"""Task: {query}
Context: {history_context}

Create a COMPLETE, THOROUGH plan using available tools.

Planning guidance:
- Break into clear, sequential steps
- For research: search → fetch content → analyze
- For coding: generate → execute → verify
- Use {{prev}} or {{step_N}} for result references
- Include all necessary steps

Create the complete tool chain plan as JSON array."""
        
        plan_json = ""
        
        # Use agent if available
        llm = self.agent_router.create_llm_for_agent(
            self.agent_router.get_agent_for_task('tool_execution')
        ) if self.agent_router else self.tool_llm
        
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
            raise ValueError(f"Planning failed: {e}\n\n{plan_json}")
        
        # Validate and enhance
        tool_plan = self._validate_and_enhance_plan(tool_plan)
        
        # Save plan
        self._save_plan(tool_plan, "enhanced")
        
        yield tool_plan
    
    def _plan_quick(self, query: str) -> Generator:
        """Quick minimal planning"""
        prompt = f"""Task: {query}

Create MINIMAL plan (1-3 steps max) for this simple query.
Most direct path to answer. Be concise."""
        
        plan_json = ""
        
        for chunk in self.agent.stream_llm(self.fast_llm, prompt):
            chunk_text = extract_chunk_text(chunk)
            yield chunk_text
            plan_json += chunk_text
        
        plan_json = self._clean_json(plan_json)
        tool_plan = json.loads(plan_json)
        
        if isinstance(tool_plan, dict):
            tool_plan = [tool_plan]
        
        self._save_plan(tool_plan, "quick")
        
        yield tool_plan
    
    def _plan_comprehensive(self, query: str, history_context: str = "") -> Generator:
        """Comprehensive planning"""
        prompt = f"""Task: {query}
Previous: {history_context}

Create MOST COMPREHENSIVE plan possible.
Be extremely thorough with all phases."""
        
        plan_json = ""
        
        llm = self.agent_router.create_llm_for_agent(
            self.agent_router.get_agent_for_task('tool_execution')
        ) if self.agent_router else self.tool_llm
        
        for chunk in self.agent.stream_llm(llm, prompt):
            chunk_text = extract_chunk_text(chunk)
            yield chunk_text
            plan_json += chunk_text
        
        plan_json = self._clean_json(plan_json)
        tool_plan = json.loads(plan_json)
        
        self._save_plan(tool_plan, "comprehensive")
        
        yield tool_plan
    
    def _plan_exploratory(self, query: str, max_alternatives: int = 3) -> Generator:
        """Exploratory planning with alternatives"""
        prompt = f"""Task: {query}

Create {max_alternatives} DIFFERENT alternative plans.
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
        
        for chunk in self.agent.stream_llm(llm, prompt):
            chunk_text = extract_chunk_text(chunk)
            yield chunk_text
            plan_json += chunk_text
        
        plan_json = self._clean_json(plan_json)
        result = json.loads(plan_json)
        
        alternatives = result.get("alternatives", [result]) if isinstance(result, dict) else [result]
        
        self._save_plan(alternatives, "exploratory")
        
        yield alternatives
    
    def _plan_multipath(self, query: str) -> Generator:
        """Multipath planning with fallbacks"""
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
        
        for chunk in self.agent.stream_llm(llm, prompt):
            chunk_text = extract_chunk_text(chunk)
            yield chunk_text
            plan_json += chunk_text
        
        plan_json = self._clean_json(plan_json)
        result = json.loads(plan_json)
        
        yield result
    
    def _execute_enhanced(self, query: str, plan=None,
                         strategy: PlanningStrategy = PlanningStrategy.STATIC,
                         execution_mode: ExecutionMode = ExecutionMode.AUTO) -> Generator:
        """Enhanced execution with auto-parallel detection"""
        
        # Generate plan if not provided
        if plan is None:
            gen = self._plan_enhanced(query, strategy)
            for r in gen:
                yield r
                if isinstance(r, (list, dict)):
                    tool_plan = r
        else:
            tool_plan = plan
        
        # Handle different plan structures
        if isinstance(tool_plan, dict):
            if "primary_path" in tool_plan:
                tool_plan = tool_plan["primary_path"]
            elif "alternatives" in tool_plan:
                tool_plan = tool_plan["alternatives"][0]
            else:
                tool_plan = [tool_plan]
        
        if not isinstance(tool_plan, list):
            yield "[Error] Invalid plan structure\n"
            return
        
        # Auto-detect parallelization
        if execution_mode == ExecutionMode.AUTO:
            concurrent_groups = self._find_concurrent_groups(tool_plan)
            has_parallel = any(len(group) > 1 for group in concurrent_groups)
            
            if has_parallel:
                yield f"\n🚀 AUTO-PARALLEL EXECUTION DETECTED\n"
                execution_mode = ExecutionMode.CONCURRENT_INDEPENDENT
            else:
                yield f"\n[Execution] Sequential execution\n"
                execution_mode = ExecutionMode.SEQUENTIAL
        
        # Choose execution method
        if execution_mode == ExecutionMode.CONCURRENT_INDEPENDENT and self.enable_orchestrator:
            yield from self._execute_concurrent_orchestrator(tool_plan, query)
        elif execution_mode == ExecutionMode.CONCURRENT_INDEPENDENT:
            yield from self._execute_concurrent_independent(tool_plan, query)
        else:
            yield from self._execute_sequential_enhanced(tool_plan, query)
    
    def _execute_sequential_enhanced(self, plan: List[Dict], query: str) -> Generator:
        """Sequential execution - enhanced version"""
        executed = {}
        step_num = 0
        
        for step in plan:
            step_num += 1
            tool_name = step.get("tool")
            tool_input = str(step.get("input", ""))
            
            # Resolve placeholders
            tool_input = self._resolve_placeholders_enhanced(tool_input, step_num, executed)
            
            yield f"\n[Step {step_num}] Executing: {tool_name}\n"
            
            # Find tool
            tool = next((t for t in self.tools if getattr(t, "name", "") == tool_name), None)
            
            if not tool:
                result = f"ERROR: Tool not found: {tool_name}"
                yield result
                executed[f"step_{step_num}"] = result
                continue
            
            try:
                # Execute
                for chunk in self._execute_single_step_enhanced(step, step_num, executed, plan):
                    if isinstance(chunk, dict) and "step_result" in chunk:
                        executed[f"step_{step_num}"] = chunk["step_result"]
                        executed[tool_name] = chunk["step_result"]
                    else:
                        yield chunk
                
                yield f"\n[Step {step_num}] ✓ Complete\n"
            
            except Exception as e:
                error_msg = f"ERROR: {str(e)}"
                yield f"\n[Step {step_num}] ✗ Failed: {error_msg}\n"
                executed[f"step_{step_num}"] = error_msg
        
        # Final result
        final_result = executed.get(f"step_{step_num}", "")
        yield f"\n{'='*60}\n[Final Result]\n{final_result}\n{'='*60}\n"
        
        yield executed
    
    def _execute_concurrent_orchestrator(self, plan: List[Dict], query: str) -> Generator:
        """Execute using orchestrator for parallelization"""
        groups = self._find_concurrent_groups(plan)
        executed = {}
        
        for group_idx, group in enumerate(groups):
            if len(group) == 1:
                # Single step
                step_idx = group[0]
                step_num = step_idx + 1
                step = plan[step_idx]
                
                yield f"\n➜ [Sequential Step {step_num}]\n"
                
                for chunk in self._execute_single_step_enhanced(step, step_num, executed, plan):
                    if isinstance(chunk, dict) and "step_result" in chunk:
                        executed[f"step_{step_num}"] = chunk["step_result"]
                        executed[step.get("tool")] = chunk["step_result"]
                    else:
                        yield chunk
            
            else:
                # Parallel group
                yield f"\n🔀 CONCURRENT GROUP {group_idx + 1} ({len(group)} steps)\n"
                
                # Submit tasks
                task_ids = {}
                for step_idx in group:
                    step_num = step_idx + 1
                    step = plan[step_idx]
                    
                    tool_name = step.get("tool")
                    tool_input = self._resolve_placeholders_enhanced(
                        str(step.get("input", "")),
                        step_num,
                        executed
                    )
                    
                    yield f"  ⚡ Launching Step {step_num}: {tool_name}\n"
                    
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
        yield f"\n{'='*60}\n[Final Result]\n{final_result}\n{'='*60}\n"
        
        yield executed
    
    def _execute_concurrent_independent(self, plan: List[Dict], query: str) -> Generator:
        """Execute using threading for parallelization"""
        groups = self._find_concurrent_groups(plan)
        executed = {}
        
        for group_idx, group in enumerate(groups):
            if len(group) == 1:
                # Single step
                step_idx = group[0]
                step_num = step_idx + 1
                step = plan[step_idx]
                
                yield f"\n➜ [Sequential Step {step_num}]\n"
                
                for chunk in self._execute_single_step_enhanced(step, step_num, executed, plan):
                    if isinstance(chunk, dict) and "step_result" in chunk:
                        executed[f"step_{step_num}"] = chunk["step_result"]
                        executed[step.get("tool")] = chunk["step_result"]
                    else:
                        yield chunk
            
            else:
                # Parallel group
                yield f"\n🔀 CONCURRENT GROUP {group_idx + 1} ({len(group)} steps)\n"
                
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
        yield f"\n{'='*60}\n[Final Result]\n{final_result}\n{'='*60}\n"
        
        yield executed
    
    def _execute_single_step_enhanced(self, step: Dict, step_num: int,
                                     executed: Dict, plan: List[Dict]) -> Generator:
        """Execute a single step and yield results"""
        tool_name = step.get("tool")
        tool_input = self._resolve_placeholders_enhanced(
            str(step.get("input", "")),
            step_num,
            executed
        )
        
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
            if hasattr(tool, 'run') and callable(tool.run):
                func = tool.run
            elif hasattr(tool, 'func') and callable(tool.func):
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
            yield error_msg
            yield {"step_result": error_msg}
    
    def _execute_step_sync(self, step: Dict, step_num: int,
                          executed: Dict, plan: List[Dict]) -> str:
        """Execute step synchronously (for threading)"""
        tool_name = step.get("tool")
        tool_input = self._resolve_placeholders_enhanced(
            str(step.get("input", "")),
            step_num,
            executed
        )
        
        tool = next((t for t in self.tools if getattr(t, "name", "") == tool_name), None)
        
        if not tool:
            raise ValueError(f"Tool not found: {tool_name}")
        
        if hasattr(tool, 'run') and callable(tool.run):
            func = tool.run
        elif hasattr(tool, 'func') and callable(tool.func):
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
    
    def _resolve_placeholders_enhanced(self, tool_input: str, step_num: int,
                                      executed: Dict) -> str:
        """Resolve placeholders - enhanced version"""
        if "{prev}" in tool_input:
            tool_input = tool_input.replace("{prev}", str(executed.get(f"step_{step_num-1}", "")))
        
        for i in range(1, step_num):
            tool_input = tool_input.replace(f"{{step_{i}}}", str(executed.get(f"step_{i}", "")))
        
        return tool_input
    
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
    
    def _analyze_dependencies(self, plan: List[Dict]) -> Dict[int, Set[int]]:
        """Analyze step dependencies"""
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
    
    def _validate_and_enhance_plan(self, plan: List[Dict]) -> List[Dict]:
        """Validate and enhance plan"""
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
    
    # ========================================================================
    # EXPERT MODE (Domain-based routing)
    # ========================================================================
    
    def _plan_expert(self, query: str, history_context: str = "") -> Generator:
        """Expert planning with domain routing"""
        
        # Triage to select domains
        yield "\n=== EXPERT DOMAIN TRIAGE ===\n"
        
        domains = self._triage_domains(query)
        
        yield f"✓ Selected domains: {[d.value for d in domains]}\n"
        
        # Filter tools by domain
        relevant_tools = self._filter_tools_by_domain(domains)
        
        yield f"✓ Filtered to {len(relevant_tools)} domain-relevant tools\n"
        
        # Create plan with domain-specific tools
        yield "\n=== EXPERT PLANNING ===\n"
        
        tool_descriptions = [
            {"name": t.name, "description": getattr(t, 'description', 'No description')}
            for t in relevant_tools
        ]
        
        planning_prompt = f"""You are a domain expert in: {[d.value for d in domains]}

Task: {query}

Available Tools:
{json.dumps(tool_descriptions, indent=2)}

Create a step-by-step execution plan using domain-specific tools.
Return as JSON array of steps."""
        
        plan_json = ""
        
        llm = self.agent_router.create_llm_for_agent(
            self.agent_router.get_agent_for_task('tool_execution')
        ) if self.agent_router else self.tool_llm
        
        for chunk in self.agent.stream_llm(llm, planning_prompt):
            chunk_text = extract_chunk_text(chunk)
            yield chunk_text
            plan_json += chunk_text
        
        plan_json = self._clean_json(plan_json)
        tool_plan = json.loads(plan_json)
        
        if isinstance(tool_plan, dict):
            tool_plan = [tool_plan]
        
        self._save_plan(tool_plan, "expert")
        
        yield tool_plan
    
    def _execute_expert(self, query: str, plan=None) -> Generator:
        """Execute with expert domain routing"""
        
        # Get plan if not provided
        if plan is None:
            gen = self._plan_expert(query)
            tool_plan = None
            for r in gen:
                if isinstance(r, list):
                    tool_plan = r
                else:
                    yield r
            
            if not tool_plan:
                raise ValueError("Expert planning failed")
        else:
            tool_plan = plan
        
        # Execute using enhanced sequential
        yield "\n=== EXPERT EXECUTION ===\n"
        yield from self._execute_sequential_enhanced(tool_plan, query)
    
    def _triage_domains(self, query: str) -> Set[Domain]:
        """Triage query to select relevant domains"""
        
        # Simple keyword-based triage
        query_lower = query.lower()
        
        domains = set()
        
        # Map keywords to domains
        keyword_map = {
            'security': Domain.SECURITY,
            'hack': Domain.PENETRATION_TESTING,
            'vulnerability': Domain.VULNERABILITY_ANALYSIS,
            'scan': Domain.NETWORKING,
            'database': Domain.DATABASE,
            'sql': Domain.DATABASE,
            'api': Domain.API_INTEGRATION,
            'search': Domain.RESEARCH,
            'analyze': Domain.DATA_ANALYSIS,
            'file': Domain.FILE_OPERATIONS,
            'code': Domain.CODE_EXECUTION,
        }
        
        for keyword, domain in keyword_map.items():
            if keyword in query_lower:
                domains.add(domain)
        
        # Always include GENERAL
        domains.add(Domain.GENERAL)
        
        return domains
    
    def _filter_tools_by_domain(self, domains: Set[Domain]) -> List[Any]:
        """Filter tools by domains"""
        relevant_tool_names = self.domain_registry.get_tools_for_domains(domains)
        
        return [
            tool for tool in self.tools
            if getattr(tool, 'name', '') in relevant_tool_names
        ]
    
    # ========================================================================
    # FIVE STAGE MODE (Multi-stage specialist planning)
    # ========================================================================
    
    def _plan_five_stage(self, query: str, history_context: str = "") -> Generator:
        """Five-stage planning"""
        
        yield "\n=== FIVE STAGE PLANNING ===\n"
        
        # Stage 1: Domain triage
        yield "\n--- Stage 1: Domain Triage ---\n"
        domains = self._triage_domains(query)
        yield f"Selected domains: {[d.value for d in domains]}\n"
        
        # Stage 2: Tool filtering
        yield "\n--- Stage 2: Tool Filtering ---\n"
        relevant_tools = self._filter_tools_by_domain(domains)
        yield f"Filtered to {len(relevant_tools)} tools\n"
        
        # Stage 3: High-level planning
        yield "\n--- Stage 3: High-Level Planning ---\n"
        
        tool_descriptions = {
            t.name: getattr(t, 'description', 'No description')[:100]
            for t in relevant_tools
        }
        
        planning_prompt = f"""Task: {query}

Available Tools:
{json.dumps(tool_descriptions, indent=2)}

Create high-level step-by-step plan (tool names + goals only).
Return as JSON array:
[
  {{"step": 1, "tool": "tool_name", "goal": "what this accomplishes"}},
  ...
]"""
        
        plan_json = ""
        
        llm = self.agent_router.create_llm_for_agent(
            self.agent_router.get_agent_for_task('tool_execution')
        ) if self.agent_router else self.tool_llm
        
        for chunk in self.agent.stream_llm(llm, planning_prompt):
            chunk_text = extract_chunk_text(chunk)
            yield chunk_text
            plan_json += chunk_text
        
        plan_json = self._clean_json(plan_json)
        high_level_plan = json.loads(plan_json)
        
        if isinstance(high_level_plan, dict):
            high_level_plan = [high_level_plan]
        
        self._save_plan(high_level_plan, "five_stage")
        
        yield high_level_plan
    
    def _execute_five_stage(self, query: str) -> Generator:
        """Execute with five-stage process"""
        
        # Get high-level plan
        gen = self._plan_five_stage(query)
        high_level_plan = None
        for r in gen:
            if isinstance(r, list):
                high_level_plan = r
            else:
                yield r
        
        if not high_level_plan:
            raise ValueError("Five-stage planning failed")
        
        yield "\n=== STAGE 4 & 5: SPECIALIST PLANNING + EXECUTION ===\n"
        
        # Execute each step with specialist planning
        tool_outputs = {}
        
        for step_dict in high_level_plan:
            step_num = step_dict['step']
            tool_name = step_dict['tool']
            step_goal = step_dict['goal']
            
            yield f"\n--- Step {step_num}: {tool_name} ---\n"
            yield f"Goal: {step_goal}\n"
            
            # Find tool
            tool = next((t for t in self.tools if getattr(t, 'name', '') == tool_name), None)
            
            if not tool:
                result = f"ERROR: Tool not found: {tool_name}"
                yield result
                tool_outputs[f"step_{step_num}"] = result
                continue
            
            # Stage 4: Specialist plans inputs
            yield "\n[Specialist Planning]\n"
            
            tool_input = self._plan_tool_specialist(
                tool, step_goal, tool_outputs, query
            )
            
            yield f"Planned input: {str(tool_input)[:200]}...\n"
            
            # Stage 5: Execute
            yield f"\n[Executing] {tool_name}\n"
            
            try:
                if hasattr(tool, 'run') and callable(tool.run):
                    func = tool.run
                elif callable(tool):
                    func = tool
                else:
                    raise ValueError(f"Tool {tool_name} is not callable")
                
                # Execute
                collected = []
                result = ""
                
                if isinstance(tool_input, dict):
                    exec_result = func(**tool_input)
                else:
                    exec_result = func(tool_input)
                
                if hasattr(exec_result, '__iter__') and not isinstance(exec_result, (str, bytes, dict)):
                    for chunk in exec_result:
                        chunk_str = str(chunk)
                        yield chunk_str
                        collected.append(chunk_str)
                    result = "".join(collected)
                else:
                    result = str(exec_result)
                    yield result
                
                tool_outputs[f"step_{step_num}"] = result
                tool_outputs[tool_name] = result
                
                yield f"\n✓ Step {step_num} complete\n"
            
            except Exception as e:
                error_msg = f"ERROR: {str(e)}"
                yield error_msg
                tool_outputs[f"step_{step_num}"] = error_msg
        
        # Final result
        final_result = tool_outputs.get(f"step_{len(high_level_plan)}", "")
        yield f"\n{'='*60}\n[Final Result]\n{final_result}\n{'='*60}\n"
        
        yield tool_outputs
    
    def _plan_tool_specialist(self, tool, step_goal: str,
                             previous_outputs: Dict[str, str],
                             context: str) -> Any:
        """Plan exact inputs for a specific tool (Stage 4)"""
        
        # Extract tool schema
        schema_info = "No schema available"
        
        if hasattr(tool, 'args_schema') and tool.args_schema:
            try:
                schema = tool.args_schema.schema()
                properties = schema.get('properties', {})
                
                if properties:
                    schema_parts = ["Parameters:"]
                    for param_name, param_info in properties.items():
                        param_type = param_info.get('type', 'string')
                        param_desc = param_info.get('description', 'No description')
                        schema_parts.append(f"  - {param_name} ({param_type}): {param_desc}")
                    schema_info = "\n".join(schema_parts)
            except:
                pass
        
        # Build specialist prompt
        prev_context = ""
        if previous_outputs:
            prev_context = "Previous outputs:\n"
            for step_id, output in list(previous_outputs.items())[-3:]:  # Last 3 outputs
                prev_context += f"  {step_id}: {output[:200]}...\n"
        
        specialist_prompt = f"""Tool: {tool.name}
Description: {getattr(tool, 'description', 'No description')}

Schema:
{schema_info}

Task: {context}
Goal: {step_goal}

{prev_context}

Plan EXACT inputs/parameters for this tool.
Return JSON: {{"input": "value" or {{"param": "val"}}, "reasoning": "brief explanation"}}"""
        
        # Get specialist plan
        plan_json = ""
        for chunk in self.agent.stream_llm(self.fast_llm, specialist_prompt):
            plan_json += extract_chunk_text(chunk)
        
        plan_json = self._clean_json(plan_json)
        
        try:
            result = json.loads(plan_json)
            return result.get("input", step_goal)
        except:
            return step_goal
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def _clean_json(self, text: str) -> str:
        """Remove markdown code fences and clean JSON"""
        text = re.sub(r'^```json\s*', '', text.strip())
        text = re.sub(r'^```\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        return text.strip()
    
    def _save_plan(self, plan: Any, mode: str):
        """Save plan to memory and file"""
        try:
            import os
            os.makedirs("./Configuration", exist_ok=True)
            with open(f"./Configuration/last_tool_plan_{mode}.json", "w", encoding="utf-8") as f:
                json.dump(plan, f, indent=2)
            
            # Save to memory if available
            if hasattr(self.agent, "mem") and hasattr(self.agent, "sess"):
                plan_id = hashlib.sha256(f"{time.time()}_{json.dumps(plan)}".encode()).hexdigest()
                self.agent.mem.add_session_memory(
                    self.agent.sess.id,
                    json.dumps(plan),
                    "Plan",
                    {
                        "topic": "plan",
                        "plan_id": plan_id,
                        "mode": mode
                    },
                    promote=True
                )
        except Exception as e:
            self.logger.warning(f"Failed to save plan: {e}")


# ============================================================================
# BACKWARD COMPATIBILITY ALIAS
# ============================================================================

# For drop-in replacement
ToolChainPlanner = UnifiedToolChainPlanner