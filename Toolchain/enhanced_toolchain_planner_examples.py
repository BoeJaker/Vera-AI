"""
Enhanced Toolchain Planner - Integration Guide and Examples
Shows how to integrate and use the improved planning system
"""

import json
from enhanced_toolchain_planner import (
    EnhancedToolChainPlanner, 
    PlanningStrategy,
    integrate_enhanced_planner
)


# ============================================================================
# INTEGRATION WITH VERA
# ============================================================================

def integrate_with_vera():
    """
    Step-by-step integration instructions
    """
    
    instructions = """
    ═══════════════════════════════════════════════════════════════
    INTEGRATION STEPS
    ═══════════════════════════════════════════════════════════════
    
    1. ADD IMPORT at top of Vera.py:
       from enhanced_toolchain_planner import integrate_enhanced_planner, PlanningStrategy
    
    2. REPLACE in Vera.__init__ (after tools are loaded):
       # OLD:
       # self.toolchain = ToolChainPlanner(self, self.tools)
       
       # NEW:
       integrate_enhanced_planner(self, enable_n8n=True)  # or False
    
    3. UPDATE async_run method to support strategies:
       
       # Add strategy parameter
       def async_run(self, query: str, strategy: str = "static"):
           # Convert string to enum
           strat_map = {
               "static": PlanningStrategy.STATIC,
               "quick": PlanningStrategy.QUICK,
               "comprehensive": PlanningStrategy.COMPREHENSIVE,
               "exploratory": PlanningStrategy.EXPLORATORY,
               "multipath": PlanningStrategy.MULTIPATH,
               "dynamic": PlanningStrategy.DYNAMIC
           }
           strategy_enum = strat_map.get(strategy, PlanningStrategy.STATIC)
           
           # In the toolchain section:
           elif triage_lower.startswith("toolchain"):
               print("\\n[ Tool Chain Agent ]\\n")
               for toolchain_chunk in self.toolchain.execute_tool_chain(
                   query, 
                   strategy=strategy_enum  # ← Pass strategy here
               ):
                   toolchain_response += str(toolchain_chunk)
                   yield toolchain_chunk
    
    4. ADD NEW COMMANDS to main loop:
       
       elif user_query.lower().startswith("/plan "):
           # Manual planning with strategy
           parts = user_query.split(" ", 2)
           strategy = parts[1] if len(parts) > 1 else "static"
           query = parts[2] if len(parts) > 2 else "test query"
           
           print(f"\\n[Planner] Creating {strategy} plan for: {query}\\n")
           for chunk in vera.toolchain.plan_tool_chain(
               query, 
               strategy=PlanningStrategy[strategy.upper()]
           ):
               print(chunk)
           continue
       
       elif user_query.lower() == "/strategies":
           print(\"\"\"
Available Planning Strategies:

📋 STATIC (default)
   - Analyzes query thoroughly
   - Creates complete, multi-step plan upfront
   - Automatically enhances incomplete plans
   - Best for: Most tasks
   
⚡ QUICK
   - Minimal plan (1-3 steps)
   - Fast planning, fast execution
   - Best for: Simple queries, quick answers
   
🔍 COMPREHENSIVE
   - Maximum detail (5-15 steps)
   - Includes verification, error recovery
   - Saves outputs to files
   - Best for: Research, reports, complex analysis
   
🌳 EXPLORATORY
   - Generates 3 alternative approaches
   - Tries different strategies
   - Best for: Uncertain/ambiguous tasks
   
🔀 MULTIPATH
   - Branching plan with fallbacks
   - Conditional paths based on results
   - Best for: Unreliable data sources
   
🎯 DYNAMIC
   - Plans one step at a time
   - Adapts based on intermediate results
   - Best for: Highly unpredictable tasks
           \"\"\")
           continue
    
    5. OPTIONAL - Add strategy selection to triage:
       
       In the triage prompt, add:
       - 'toolchain_quick'  → Fast multi-step execution
       - 'toolchain_deep'   → Comprehensive research/analysis
       
       Then in routing:
       elif "toolchain_quick" in triage_lower:
           strategy = PlanningStrategy.QUICK
       elif "toolchain_deep" in triage_lower:
           strategy = PlanningStrategy.COMPREHENSIVE
       else:
           strategy = PlanningStrategy.STATIC
    
    ═══════════════════════════════════════════════════════════════
    """
    
    print(instructions)


# ============================================================================
# EXAMPLE PLANS - BEFORE vs AFTER
# ============================================================================

def show_example_improvements():
    """
    Show how plans are improved in the new system
    """
    
    examples = """
    ═══════════════════════════════════════════════════════════════
    PLAN QUALITY IMPROVEMENTS
    ═══════════════════════════════════════════════════════════════
    
    Example 1: Web Research Query
    ─────────────────────────────────────────────────────────────
    Query: "What are the latest AI safety developments?"
    
    ❌ OLD PLAN (incomplete):
    [
      {"tool": "web_search", "input": "latest AI safety developments"},
      {"tool": "deep_llm", "input": "Summarize: {prev}"}
    ]
    
    Problem: LLM only gets URLs, not actual content!
    Result: Generic answer based on search result titles
    
    ✅ NEW PLAN (complete):
    [
      {"tool": "web_search", "input": "latest AI safety developments 2024"},
      {"tool": "web_search_deep", "input": "{prev}"},  ← FETCHES CONTENT
      {"tool": "deep_llm", "input": "Analyze and summarize key developments: {prev}"}
    ]
    
    Result: Detailed answer based on actual article content
    
    
    Example 2: Comparison Task
    ─────────────────────────────────────────────────────────────
    Query: "Compare Rust vs Go for backend development"
    
    ❌ OLD PLAN (shallow):
    [
      {"tool": "web_search", "input": "Rust vs Go comparison"},
      {"tool": "deep_llm", "input": "Compare: {prev}"}
    ]
    
    Problem: Single search, no depth, comparison based on snippets
    
    ✅ NEW PLAN (thorough):
    [
      {"tool": "web_search", "input": "Rust backend development features"},
      {"tool": "web_search_deep", "input": "{step_1}"},
      {"tool": "web_search", "input": "Go backend development features"},
      {"tool": "web_search_deep", "input": "{step_3}"},
      {"tool": "deep_llm", "input": "Compare Rust vs Go for backend:\\n\\nRust: {step_2}\\n\\nGo: {step_4}"}
    ]
    
    Result: Detailed comparison based on in-depth research of both
    
    
    Example 3: Code + Execution
    ─────────────────────────────────────────────────────────────
    Query: "Write a function to find prime numbers and test it"
    
    ❌ OLD PLAN (incomplete):
    [
      {"tool": "deep_llm", "input": "Write Python function for prime numbers"}
    ]
    
    Problem: Code generated but never executed or verified
    
    ✅ NEW PLAN (complete workflow):
    [
      {"tool": "deep_llm", "input": "Write a Python function to find prime numbers with test cases"},
      {"tool": "python", "input": "{prev}"},
      {"tool": "fast_llm", "input": "Review execution. If errors, explain and suggest fixes: {prev}"},
      {"tool": "write_file", "input": "prime_numbers.py|||{step_1}"}
    ]
    
    Result: Code is generated, executed, verified, and saved
    
    
    Example 4: Data Analysis
    ─────────────────────────────────────────────────────────────
    Query: "Analyze sales_data.csv and create a report"
    
    ❌ OLD PLAN (partial):
    [
      {"tool": "read_file", "input": "sales_data.csv"},
      {"tool": "python", "input": "import pandas as pd\\ndf = pd.read_csv('sales_data.csv')\\nprint(df.head())"}
    ]
    
    Problem: Just reads file, no actual analysis or report
    
    ✅ NEW PLAN (full pipeline):
    [
      {"tool": "read_file", "input": "sales_data.csv"},
      {"tool": "python", "input": "import pandas as pd\\ndf = pd.read_csv('sales_data.csv')\\nprint(df.describe())\\nprint(df.groupby('category').sum())"},
      {"tool": "deep_llm", "input": "Analyze this sales data and identify trends, insights: {prev}"},
      {"tool": "fast_llm", "input": "Create a markdown report with sections: Summary, Key Findings, Recommendations\\n\\nData: {step_3}"},
      {"tool": "write_file", "input": "sales_report.md|||{prev}"}
    ]
    
    Result: Complete analysis with saved report
    
    ═══════════════════════════════════════════════════════════════
    AUTO-ENHANCEMENT FEATURES
    ═══════════════════════════════════════════════════════════════
    
    The planner automatically detects and fixes common issues:
    
    1. Missing Content Fetching
       If plan has: web_search → llm
       Auto-adds: web_search → web_search_deep → llm
    
    2. Missing Analysis
       If plan has: web_search_deep (no llm after)
       Auto-adds: web_search_deep → deep_llm
    
    3. Missing Output
       If query mentions "report" or "document"
       Auto-adds: write_file at the end
    
    4. Memory Context
       LLM tools automatically get conversation context
    
    These enhancements are marked with "_auto_added": true
    in the plan JSON for transparency.
    
    ═══════════════════════════════════════════════════════════════
    """
    
    print(examples)


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

def usage_examples():
    """
    Practical examples of using different strategies
    """
    
    examples = """
    ═══════════════════════════════════════════════════════════════
    USAGE EXAMPLES
    ═══════════════════════════════════════════════════════════════
    
    Example 1: Quick Answer (QUICK strategy)
    ─────────────────────────────────────────────────────────────
    User: "What's the capital of France?"
    
    Command: /plan quick What's the capital of France?
    
    Generated Plan:
    [
      {"tool": "deep_llm", "input": "What's the capital of France?"}
    ]
    
    → 1 step, instant answer
    
    
    Example 2: Research Task (STATIC strategy - default)
    ─────────────────────────────────────────────────────────────
    User: "Research quantum computing breakthroughs in 2024"
    
    Automatically generated plan:
    [
      {"tool": "web_search", "input": "quantum computing breakthroughs 2024"},
      {"tool": "web_search_deep", "input": "{prev}"},
      {"tool": "deep_llm", "input": "Analyze and summarize key quantum computing breakthroughs: {prev}"}
    ]
    
    → Complete research workflow
    
    
    Example 3: Deep Dive (COMPREHENSIVE strategy)
    ─────────────────────────────────────────────────────────────
    User: "Create a comprehensive analysis of renewable energy trends"
    
    Command: /plan comprehensive Create analysis of renewable energy
    
    Generated Plan (8+ steps):
    [
      {"tool": "web_search", "input": "renewable energy trends 2024"},
      {"tool": "web_search_deep", "input": "{step_1}"},
      {"tool": "web_search", "input": "solar energy market analysis 2024"},
      {"tool": "web_search_deep", "input": "{step_3}"},
      {"tool": "web_search", "input": "wind energy market analysis 2024"},
      {"tool": "web_search_deep", "input": "{step_5}"},
      {"tool": "deep_llm", "input": "Create detailed analysis outline: {step_2}, {step_4}, {step_6}"},
      {"tool": "deep_llm", "input": "Write comprehensive analysis using outline: {prev}"},
      {"tool": "write_file", "input": "renewable_energy_analysis.md|||{prev}"}
    ]
    
    → Thorough research + comprehensive report + saved file
    
    
    Example 4: Uncertain Task (EXPLORATORY strategy)
    ─────────────────────────────────────────────────────────────
    User: "Find information about obscure topic X"
    
    Command: /plan exploratory Find information about [topic]
    
    Generates 3 different approaches:
    
    Alternative 1 (Web Search):
    [
      {"tool": "web_search", "input": "topic X information"},
      {"tool": "web_search_deep", "input": "{prev}"},
      ...
    ]
    
    Alternative 2 (Academic Search):
    [
      {"tool": "web_search", "input": "topic X research papers"},
      {"tool": "web_search_deep", "input": "{prev}"},
      ...
    ]
    
    Alternative 3 (Direct LLM):
    [
      {"tool": "deep_llm", "input": "What do you know about topic X?"},
      ...
    ]
    
    → Tries multiple strategies, picks best result
    
    
    Example 5: Comparison (Auto-detected pattern)
    ─────────────────────────────────────────────────────────────
    User: "Compare TypeScript vs JavaScript"
    
    Automatically uses comparison template:
    [
      {"tool": "web_search", "input": "TypeScript features benefits"},
      {"tool": "web_search_deep", "input": "{step_1}"},
      {"tool": "web_search", "input": "JavaScript features benefits"},
      {"tool": "web_search_deep", "input": "{step_3}"},
      {"tool": "deep_llm", "input": "Compare TypeScript vs JavaScript:\\n\\nTypeScript: {step_2}\\n\\nJavaScript: {step_4}"}
    ]
    
    → Researches both sides independently, then compares
    
    
    Example 6: Code Task (Auto-detected pattern)
    ─────────────────────────────────────────────────────────────
    User: "Write a binary search algorithm and test it"
    
    Automatically uses code template:
    [
      {"tool": "deep_llm", "input": "Write a Python binary search with test cases"},
      {"tool": "python", "input": "{prev}"},
      {"tool": "fast_llm", "input": "Review output, explain errors if any: {prev}"}
    ]
    
    → Generate → Execute → Verify cycle
    
    
    Example 7: Dynamic Planning (DYNAMIC strategy)
    ─────────────────────────────────────────────────────────────
    User: "Investigate this error message: [error]"
    
    Command: Execute with DYNAMIC strategy
    
    Step 1: Search for error
    ↓
    If results insufficient → Search with different terms
    If results found → Fetch content
    ↓
    If content unclear → Ask LLM to explain
    If content clear → Provide solution
    ↓
    Continue adapting based on results...
    
    → Plans one step at a time based on what's working
    
    ═══════════════════════════════════════════════════════════════
    """
    
    print(examples)


# ============================================================================
# COMMAND REFERENCE
# ============================================================================

def command_reference():
    """
    Quick reference for new commands
    """
    
    reference = """
    ═══════════════════════════════════════════════════════════════
    COMMAND REFERENCE
    ═══════════════════════════════════════════════════════════════
    
    PLANNING COMMANDS:
    ─────────────────────────────────────────────────────────────
    /plan <strategy> <query>      Create plan with specific strategy
        /plan static Research AI safety
        /plan quick What is 2+2
        /plan comprehensive Create detailed report on climate change
        /plan exploratory Find obscure information
        /plan multipath Handle unreliable API
    
    /strategies                   Show all available strategies
    
    /replay                       Execute last saved plan
    
    /show-plan                    Display last generated plan
    
    /enhance-plan                 Auto-enhance current plan
    
    
    EXECUTION COMMANDS:
    ─────────────────────────────────────────────────────────────
    Just ask a question          Uses default (STATIC) strategy
    
    "quick: <query>"             Forces QUICK strategy
        quick: What's the weather?
    
    "deep: <query>"              Forces COMPREHENSIVE strategy
        deep: Analyze market trends
    
    
    N8N COMMANDS (if enabled):
    ─────────────────────────────────────────────────────────────
    /n8n-edit                    Open last plan in n8n editor
    /n8n-execute                 Execute via n8n engine
    /n8n-list                    List all n8n workflows
    /n8n-import <id>             Import edited workflow
    
    
    DEBUGGING COMMANDS:
    ─────────────────────────────────────────────────────────────
    /verbose                     Enable verbose planning output
    /show-tools                  List all available tools
    /validate-plan               Check plan for completeness
    
    ═══════════════════════════════════════════════════════════════
    """
    
    print(reference)


# ============================================================================
# TESTING SUITE
# ============================================================================

def test_planning_quality(vera_instance):
    """
    Test suite to verify plan quality improvements
    """
    
    test_queries = [
        {
            "query": "What are the latest developments in quantum computing?",
            "expected_steps": ["web_search", "web_search_deep", "deep_llm"],
            "min_steps": 3
        },
        {
            "query": "Compare Python vs Rust",
            "expected_steps": ["web_search", "web_search_deep", "web_search", "web_search_deep", "deep_llm"],
            "min_steps": 5
        },
        {
            "query": "Write a quicksort algorithm",
            "expected_steps": ["deep_llm", "python"],
            "min_steps": 2
        },
        {
            "query": "Analyze data.csv and create report",
            "expected_steps": ["read_file", "python", "deep_llm", "write_file"],
            "min_steps": 4
        }
    ]
    
    results = []
    
    for test in test_queries:
        print(f"\n{'='*60}")
        print(f"Testing: {test['query']}")
        print('='*60)
        
        plan = None
        for output in vera_instance.toolchain.plan_tool_chain(test['query']):
            if isinstance(output, list):
                plan = output
        
        if not plan:
            results.append({"query": test['query'], "passed": False, "reason": "No plan generated"})
            continue
        
        # Check plan quality
        step_tools = [step.get("tool") for step in plan]
        
        # Verify minimum steps
        if len(plan) < test['min_steps']:
            results.append({
                "query": test['query'],
                "passed": False,
                "reason": f"Too few steps: {len(plan)} < {test['min_steps']}"
            })
            continue
        
        # Verify expected tools present
        missing_tools = [tool for tool in test['expected_steps'] if tool not in step_tools]
        if missing_tools:
            results.append({
                "query": test['query'],
                "passed": False,
                "reason": f"Missing tools: {missing_tools}"
            })
            continue
        
        # Check for web_search without web_search_deep
        for i, tool in enumerate(step_tools):
            if tool == "web_search":
                if i + 1 >= len(step_tools) or step_tools[i + 1] != "web_search_deep":
                    results.append({
                        "query": test['query'],
                        "passed": False,
                        "reason": "web_search not followed by web_search_deep"
                    })
                    break
        else:
            results.append({
                "query": test['query'],
                "passed": True,
                "plan": plan
            })
    
    # Print results
    print("\n" + "="*60)
    print("TEST RESULTS")
    print("="*60)
    
    passed = sum(1 for r in results if r['passed'])
    total = len(results)
    
    for result in results:
        status = "✓ PASS" if result['passed'] else "✗ FAIL"
        print(f"\n{status}: {result['query']}")
        if not result['passed']:
            print(f"  Reason: {result['reason']}")
    
    print(f"\n{'='*60}")
    print(f"Score: {passed}/{total} tests passed")
    print("="*60)
    
    return results


# ============================================================================
# MAIN - Run demonstrations
# ============================================================================

if __name__ == "__main__":
    print("\n")
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║  Enhanced Toolchain Planner - Integration Guide          ║")
    print("╚═══════════════════════════════════════════════════════════╝")
    
    print("\n[1] Integration Instructions")
    integrate_with_vera()
    
    input("\nPress Enter to continue...")
    
    print("\n[2] Plan Quality Improvements")
    show_example_improvements()
    
    input("\nPress Enter to continue...")
    
    print("\n[3] Usage Examples")
    usage_examples()
    
    input("\nPress Enter to continue...")
    
    print("\n[4] Command Reference")
    command_reference()
    
    print("\n" + "="*60)
    print("Setup complete! Check the files for full implementation.")
    print("="*60)
    