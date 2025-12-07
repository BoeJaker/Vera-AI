"""
Integration Bridge - Connects Enhanced Planner with Existing ToolChainPlanner
Provides backward compatibility while adding new features
"""

import json
import logging
from typing import List, Dict, Any, Generator, Optional
from Vera.Toolchain.enhanced_toolchain_planner import EnhancedToolChainPlanner, PlanningStrategy, PlanTemplate

logger = logging.getLogger(__name__)


class HybridToolChainPlanner:
    """
    Combines the robust execution engine from the original ToolChainPlanner
    with the intelligent planning from EnhancedToolChainPlanner.
    
    This gives you:
    - Better plan quality (from EnhancedToolChainPlanner)
    - Robust execution with retries, error handling (from original)
    - All execution modes (batch, incremental, speculative, hybrid)
    - n8n integration
    """
    
    def __init__(self, agent, tools: List[Any], 
                 max_steps: int = 60,
                 default_retries: int = 1,
                 default_step_timeout: Optional[float] = 30.0,
                 speculative_workers: int = 3,
                 max_parallel_steps: int = 5,
                 enable_n8n: bool = False,
                 n8n_url: str = "http://localhost:5678"):
        
        # Import the original ToolChainPlanner
        try:
            from Toolchain.toolchain import ToolChainPlanner as OriginalPlanner
            self.executor = OriginalPlanner(
                agent, tools, max_steps, default_retries, 
                default_step_timeout, speculative_workers, max_parallel_steps
            )
        except ImportError:
            logger.warning("Original ToolChainPlanner not found, using minimal executor")
            self.executor = None
        
        # Enhanced planner for intelligent plan generation
        self.planner = EnhancedToolChainPlanner(agent, tools, enable_n8n, n8n_url)
        
        # Share references
        self.agent = agent
        self.tools = tools
        self.max_steps = max_steps
        self.enable_n8n = enable_n8n
    
    def execute_tool_chain(self, query: str, *,
                          mode: str = "incremental",
                          strategy: str = "static",
                          initial_plan: Optional[List[Dict]] = None,
                          max_steps: Optional[int] = None,
                          stop_on_error: bool = False,
                          allow_replan_on_error: bool = True,
                          allow_partial: bool = True,
                          step_retries: Optional[int] = None,
                          retry_backoff: float = 1.5,
                          use_n8n: bool = False,
                          **kwargs) -> Generator:
        """
        Main execution method that combines intelligent planning with robust execution.
        
        Args:
            query: User query
            mode: Execution mode (batch, incremental, speculative, hybrid)
            strategy: Planning strategy (static, quick, comprehensive, exploratory, multipath, dynamic)
            use_n8n: Execute via n8n if available
            **kwargs: Additional arguments passed to executor
        
        Yields:
            Progress updates and final results
        """
        
        # Convert strategy string to enum
        strategy_map = {
            "static": PlanningStrategy.STATIC,
            "quick": PlanningStrategy.QUICK,
            "comprehensive": PlanningStrategy.COMPREHENSIVE,
            "exploratory": PlanningStrategy.EXPLORATORY,
            "multipath": PlanningStrategy.MULTIPATH,
            "dynamic": PlanningStrategy.DYNAMIC
        }
        strategy_enum = strategy_map.get(strategy.lower(), PlanningStrategy.STATIC)
        
        # Phase 1: Generate intelligent plan
        yield f"\n{'='*60}\n"
        yield f"[Planning Phase] Using {strategy.upper()} strategy\n"
        yield f"{'='*60}\n"
        
        if initial_plan is None:
            plan = None
            for output in self.planner.plan_tool_chain(query, strategy=strategy_enum):
                yield output
                if isinstance(output, (list, dict)):
                    plan = output
        else:
            plan = initial_plan
        
        if plan is None:
            yield "[Error] No plan generated\n"
            return
        
        # Handle different plan structures
        if isinstance(plan, dict):
            if "primary_path" in plan:
                plan = plan["primary_path"]
            elif "alternatives" in plan:
                plan = plan["alternatives"][0]
            else:
                plan = [plan]
        
        # Phase 2: Execute via n8n or locally
        if use_n8n and self.enable_n8n:
            yield f"\n{'='*60}\n"
            yield "[Execution Phase] Executing via n8n\n"
            yield f"{'='*60}\n"
            
            for output in self.planner.execute_tool_chain(query, plan=plan, use_n8n=True):
                yield output
        
        # Phase 3: Execute with original robust executor (if available)
        elif self.executor is not None:
            yield f"\n{'='*60}\n"
            yield f"[Execution Phase] Using {mode.upper()} mode\n"
            yield f"{'='*60}\n"
            
            # Execute using original planner's robust execution
            for output in self.executor.execute_tool_chain(
                query,
                mode=mode,
                initial_plan=plan,
                max_steps=max_steps,
                stop_on_error=stop_on_error,
                allow_replan_on_error=allow_replan_on_error,
                allow_partial=allow_partial,
                step_retries=step_retries,
                retry_backoff=retry_backoff,
                **kwargs
            ):
                yield output
        
        # Phase 4: Fallback to simple execution
        else:
            yield f"\n{'='*60}\n"
            yield "[Execution Phase] Using simple executor\n"
            yield f"{'='*60}\n"
            
            for output in self.planner._execute_local(plan, query):
                yield output
    
    def plan_tool_chain(self, query: str, strategy: str = "static", **kwargs) -> Generator:
        """
        Generate plan only (no execution).
        
        Args:
            query: User query
            strategy: Planning strategy
        """
        strategy_map = {
            "static": PlanningStrategy.STATIC,
            "quick": PlanningStrategy.QUICK,
            "comprehensive": PlanningStrategy.COMPREHENSIVE,
            "exploratory": PlanningStrategy.EXPLORATORY,
            "multipath": PlanningStrategy.MULTIPATH,
            "dynamic": PlanningStrategy.DYNAMIC
        }
        strategy_enum = strategy_map.get(strategy.lower(), PlanningStrategy.STATIC)
        
        yield from self.planner.plan_tool_chain(query, strategy=strategy_enum, **kwargs)
    
    # Delegate other methods to appropriate component
    def __getattr__(self, name):
        """Delegate unknown attributes to executor or planner."""
        if self.executor is not None and hasattr(self.executor, name):
            return getattr(self.executor, name)
        elif hasattr(self.planner, name):
            return getattr(self.planner, name)
        else:
            raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")


def integrate_hybrid_planner(vera_instance, enable_n8n: bool = False, **kwargs):
    """
    Replace Vera's toolchain with the hybrid planner.
    
    This preserves all functionality from the original ToolChainPlanner
    while adding intelligent plan generation.
    
    Usage in Vera.__init__:
        from toolchain_integration_bridge import integrate_hybrid_planner
        integrate_hybrid_planner(self, enable_n8n=True)
    
    Args:
        vera_instance: Vera agent instance
        enable_n8n: Enable n8n integration
        **kwargs: Additional arguments for ToolChainPlanner
    """
    vera_instance.toolchain = HybridToolChainPlanner(
        vera_instance,
        vera_instance.tools,
        enable_n8n=enable_n8n,
        **kwargs
    )
    
    print("[Hybrid Planner] ✓ Loaded")
    print("  ├─ Intelligent planning (EnhancedToolChainPlanner)")
    print("  ├─ Robust execution (Original ToolChainPlanner)")
    print("  ├─ All execution modes (batch, incremental, speculative, hybrid)")
    
    if enable_n8n:
        print("  └─ n8n integration enabled")
    else:
        print("  └─ n8n integration disabled")


# ============================================================================
# VERA ASYNC_RUN INTEGRATION
# ============================================================================

def enhanced_async_run_example():
    """
    Example of how to modify Vera.async_run to use the hybrid planner.
    
    This is a drop-in replacement for the existing async_run method.
    """
    
    example_code = '''
def async_run(self, query: str, strategy: str = "static", mode: str = "incremental"):
    """
    Enhanced async_run with intelligent planning.
    
    Args:
        query: User query
        strategy: Planning strategy (static, quick, comprehensive, exploratory, multipath, dynamic)
        mode: Execution mode (batch, incremental, speculative, hybrid)
    """
    self.mem.add_session_memory(self.sess.id, f"{query}", "Query", {"topic": "plan"}, promote=True)
    
    # Triage prompt remains the same, but add new categories
    triage_prompt = f"""
    Classify this Query into one of the following categories:
        - 'simple'          → Simple textual response
        - 'toolchain_quick' → Quick multi-step task (1-3 steps)
        - 'toolchain'       → Standard multi-step task
        - 'toolchain_deep'  → Complex research/analysis task
        - 'reasoning'       → Deep reasoning required
        - 'complex'         → Complex written response
        
    Query: {query}
    
    Respond with a single classification term.
    """
    
    full_triage = ""
    for triage_chunk in self.stream_llm(self.fast_llm, triage_prompt):
        full_triage += triage_chunk
        yield triage_chunk
    
    self.mem.add_session_memory(self.sess.id, f"{full_triage}", "Response", {"topic": "triage"}, promote=True)
    triage_lower = full_triage.lower()
    
    # Route based on triage
    if triage_lower.startswith("toolchain"):
        print("\\n[ Tool Chain Agent ]\\n")
        
        # Determine strategy based on triage
        if "quick" in triage_lower:
            strategy = "quick"
        elif "deep" in triage_lower:
            strategy = "comprehensive"
        else:
            strategy = "static"
        
        toolchain_response = ""
        for toolchain_chunk in self.toolchain.execute_tool_chain(
            query,
            strategy=strategy,  # ← Use intelligent planning
            mode=mode           # ← Keep robust execution
        ):
            toolchain_response += str(toolchain_chunk)
            yield toolchain_chunk
        
        self.mem.add_session_memory(
            self.sess.id, f"{toolchain_response}", "Response", 
            {"topic": "response", "agent": "toolchain"}
        )
        total_response = toolchain_response
    
    elif triage_lower.startswith("complex"):
        # ... existing code ...
        pass
    
    elif triage_lower.startswith("reasoning"):
        # ... existing code ...
        pass
    
    else:
        # ... existing code ...
        pass
    
    self.save_to_memory(query, total_response)
'''
    
    return example_code


# ============================================================================
# COMMAND ADDITIONS FOR MAIN LOOP
# ============================================================================

def get_main_loop_additions():
    """
    Commands to add to Vera's main loop for enhanced planner functionality.
    """
    
    commands = '''

elif user_query.lower().startswith("/plan "):
    # Manual planning with strategy
    parts = user_query.split(" ", 2)
    strategy = parts[1] if len(parts) > 1 else "static"
    query_text = parts[2] if len(parts) > 2 else "test query"
    
    print(f"\\n[Planner] Creating {strategy.upper()} plan for: {query_text}\\n")
    for chunk in vera.toolchain.plan_tool_chain(query_text, strategy=strategy):
        if isinstance(chunk, (list, dict)):
            print(json.dumps(chunk, indent=2))
        else:
            print(chunk, end="", flush=True)
    continue

elif user_query.lower().startswith("/execute "):
    # Execute with specific strategy and mode
    # Format: /execute [strategy] [mode] query
    parts = user_query.split(" ", 3)
    strategy = parts[1] if len(parts) > 1 else "static"
    mode = parts[2] if len(parts) > 2 else "incremental"
    query_text = parts[3] if len(parts) > 3 else "test query"
    
    print(f"\\n[Execute] Strategy={strategy}, Mode={mode}\\n")
    result = ""
    for chunk in vera.toolchain.execute_tool_chain(
        query_text, 
        strategy=strategy, 
        mode=mode
    ):
        print(chunk, end="", flush=True)
        result += str(chunk)
    continue

elif user_query.lower() == "/strategies":
    print("""
Available Planning Strategies:
    
📋 STATIC (default) - Thorough analysis, complete multi-step plan
⚡ QUICK            - Minimal plan (1-3 steps) for simple queries
🔍 COMPREHENSIVE    - Maximum detail (5-15 steps) with verification
🌳 EXPLORATORY      - 3 alternative approaches tried in parallel
🔀 MULTIPATH        - Branching plan with conditional fallbacks
🎯 DYNAMIC          - One step at a time, adapts to results

Available Execution Modes:

📦 BATCH            - Execute all steps sequentially
🔄 INCREMENTAL      - Plan and execute one step at a time
🚀 SPECULATIVE      - Try multiple plans in parallel
⚖️  HYBRID           - Start with batch, fallback to incremental

Usage:
    /plan <strategy> <query>
    /execute <strategy> <mode> <query>
    
Examples:
    /plan quick What is 2+2
    /plan comprehensive Research quantum computing
    /execute static batch Create a report on AI
    /execute exploratory speculative Find obscure information
    """)
    continue

elif user_query.lower() == "/modes":
    print("""
Execution Modes (from original ToolChainPlanner):

BATCH:
  - Creates complete plan upfront
  - Executes all steps sequentially
  - Best for: Predictable workflows
  - Error handling: Continue or stop on error

INCREMENTAL:
  - Plans one step at a time
  - Adapts based on intermediate results
  - Best for: Dynamic, unpredictable tasks
  - Error handling: Can replan after errors

SPECULATIVE:
  - Generates multiple alternative plans
  - Executes them in parallel
  - Takes first successful result
  - Best for: Unreliable data sources

HYBRID:
  - Starts with batch mode
  - Falls back to incremental on error
  - Best for: Most tasks (recommended default)
  - Error handling: Automatic fallback
    """)
    continue

elif user_query.lower() == "/templates":
    print("""
Available Plan Templates:

1. web_research(query, depth="standard")
   - Depths: quick, standard, deep
   - Complete research workflow
   
2. data_analysis(data_source, analysis_type)
   - Load → Process → Analyze → Report
   
3. code_task(description, language="python")
   - Generate → Execute → Verify
   
4. comparison_research(topic_a, topic_b)
   - Research both → Compare
   
5. document_creation(topic, doc_type="report")
   - Research → Outline → Write → Save

Usage in custom code:
    from enhanced_toolchain_planner import PlanTemplate
    plan = PlanTemplate.web_research("AI safety", depth="deep")
    """)
    continue

elif user_query.lower() == "/test-plans":
    # Run test suite
    from enhanced_planner_examples import test_planning_quality
    test_planning_quality(vera)
    continue

elif user_query.lower() == "/show-tools":
    # Show all available tools
    print("\\nAvailable Tools:\\n")
    for i, tool in enumerate(vera.tools, 1):
        name = getattr(tool, "name", f"tool_{i}")
        desc = getattr(tool, "description", "No description")
        print(f"{i:2d}. {name:20s} - {desc[:60]}")
    continue
'''
    
    return commands


# ============================================================================
# QUICK START GUIDE
# ============================================================================

def quick_start_guide():
    """
    Print quick start guide for integration.
    """
    
    guide = """
╔═══════════════════════════════════════════════════════════════╗
║           QUICK START GUIDE - Hybrid Planner                  ║
╚═══════════════════════════════════════════════════════════════╝

STEP 1: Install (one line in Vera.__init__)
────────────────────────────────────────────────────────────────
from toolchain_integration_bridge import integrate_hybrid_planner

# Replace your existing toolchain initialization with:
integrate_hybrid_planner(self, enable_n8n=True)  # or False


STEP 2: Update async_run (optional but recommended)
────────────────────────────────────────────────────────────────
Add strategy parameter to async_run:

def async_run(self, query: str, strategy: str = "static"):
    # ... existing triage code ...
    
    # In toolchain section:
    for chunk in self.toolchain.execute_tool_chain(
        query, 
        strategy=strategy  # ← Add this
    ):
        yield chunk


STEP 3: Add commands to main loop (copy from above)
────────────────────────────────────────────────────────────────
/plan <strategy> <query>     - Generate plan
/execute <strategy> <mode>   - Execute with options
/strategies                  - List strategies
/modes                       - List execution modes
/templates                   - Show templates


THAT'S IT! Now you have:
────────────────────────────────────────────────────────────────
✓ Intelligent plan generation (complete workflows)
✓ Robust execution (retries, error handling)
✓ Multiple strategies (quick, comprehensive, exploratory, etc.)
✓ Multiple execution modes (batch, incremental, speculative, hybrid)
✓ n8n integration (if enabled)
✓ Backward compatibility (existing code still works)


EXAMPLES:
────────────────────────────────────────────────────────────────
User: "Research quantum computing"
→ Automatically creates: search → fetch → analyze plan

User: quick: What's 2+2
→ Uses QUICK strategy (1 step)

User: deep: Analyze market trends
→ Uses COMPREHENSIVE strategy (5-15 steps)

/plan comprehensive Create climate change report
→ Generates detailed plan with research, analysis, writing, saving

/execute exploratory speculative Find obscure topic
→ Tries 3 different approaches in parallel


WHAT'S IMPROVED:
────────────────────────────────────────────────────────────────
Before: web_search → llm (only gets URLs)
After:  web_search → web_search_deep → llm (gets actual content)

Before: Single approach, hope it works
After:  Multiple strategies, pick best approach

Before: Manual plan creation
After:  Intelligent auto-planning with validation

Before: No persistence
After:  Plans saved, n8n integration, replay capability

╚═══════════════════════════════════════════════════════════════╝
"""
    
    print(guide)


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    quick_start_guide()
    
    print("\nFor full integration examples, see:")
    print("  - enhanced_planner_examples.py")
    print("  - enhanced_toolchain_planner.py")
    print("\nFor n8n integration, see:")
    print("  - n8n_toolchain_integration.py")
    print("  - enhanced_toolchain_n8n.py")