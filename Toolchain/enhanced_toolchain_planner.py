"""
Enhanced ToolChain Planner with Intelligent Plan Generation
Produces thorough, multi-step plans that follow through on tasks completely.
"""

import json
import time
import logging
import re
import hashlib
from typing import List, Dict, Any, Optional, Generator, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class PlanningStrategy(Enum):
    """Different planning approaches for different task types."""
    STATIC = "static"              # Fixed plan upfront (default)
    DYNAMIC = "dynamic"            # Plan one step at a time based on results
    EXPLORATORY = "exploratory"    # Multiple alternatives explored in parallel
    QUICK = "quick"                # Fast, minimal plan for simple tasks
    MULTIPATH = "multipath"        # Branch and try different approaches
    COMPREHENSIVE = "comprehensive" # Deep, thorough multi-step plans


class PlanTemplate:
    """Common patterns for creating thorough tool chains."""
    
    @staticmethod
    def web_research(query: str, depth: str = "standard") -> List[Dict]:
        """
        Template for comprehensive web research.
        Goes beyond just searching - fetches, parses, and analyzes.
        """
        if depth == "quick":
            return [
                {"tool": "web_search", "input": query},
                {"tool": "deep_llm", "input": f"Analyze these search results and answer: {query}\n\nResults: {{prev}}"}
            ]
        elif depth == "standard":
            return [
                {"tool": "web_search", "input": query},
                {"tool": "web_search_deep", "input": "{prev}"},  # Fetches and parses top results
                {"tool": "deep_llm", "input": f"Based on the detailed content, provide a comprehensive answer to: {query}\n\nContent: {{prev}}"}
            ]
        else:  # deep
            return [
                {"tool": "web_search", "input": query},
                {"tool": "web_search_deep", "input": "{prev}"},
                {"tool": "deep_llm", "input": f"Analyze and extract key findings from: {{prev}}"},
                {"tool": "fast_llm", "input": f"Synthesize the findings into a clear answer for: {query}\n\nFindings: {{prev}}"},
                {"tool": "write_file", "input": "research_report.md|||{prev}"}  # Save for reference
            ]
    
    @staticmethod
    def data_analysis(data_source: str, analysis_type: str) -> List[Dict]:
        """Template for data processing and analysis."""
        return [
            {"tool": "read_file", "input": data_source},
            {"tool": "python", "input": f"import pandas as pd\ndf = pd.read_csv('{data_source}')\nprint(df.describe())"},
            {"tool": "python", "input": f"# Perform {analysis_type}\n# Use the data from previous step\n{{prev}}"},
            {"tool": "deep_llm", "input": f"Interpret these statistical results and provide insights:\n{{prev}}"}
        ]
    
    @staticmethod
    def code_task(task_description: str, language: str = "python") -> List[Dict]:
        """Template for coding tasks."""
        return [
            {"tool": "deep_llm", "input": f"Write {language} code for: {task_description}"},
            {"tool": language, "input": "{prev}"},
            {"tool": "fast_llm", "input": "Review the output. If there are errors, explain them and suggest fixes:\n{prev}"}
        ]
    
    @staticmethod
    def comparison_research(topic_a: str, topic_b: str) -> List[Dict]:
        """Template for comparing two things."""
        return [
            {"tool": "web_search", "input": topic_a},
            {"tool": "web_search_deep", "input": "{step_1}"},
            {"tool": "web_search", "input": topic_b},
            {"tool": "web_search_deep", "input": "{step_3}"},
            {"tool": "deep_llm", "input": f"Compare and contrast {topic_a} vs {topic_b}\n\n{topic_a} info: {{step_2}}\n\n{topic_b} info: {{step_4}}"}
        ]
    
    @staticmethod
    def document_creation(topic: str, doc_type: str = "report") -> List[Dict]:
        """Template for creating documents."""
        return [
            {"tool": "web_search", "input": f"latest information about {topic}"},
            {"tool": "web_search_deep", "input": "{prev}"},
            {"tool": "deep_llm", "input": f"Create an outline for a {doc_type} about {topic} based on: {{prev}}"},
            {"tool": "deep_llm", "input": f"Write a complete {doc_type} using this outline: {{prev}}"},
            {"tool": "write_file", "input": f"{topic.replace(' ', '_')}_{doc_type}.md|||{prev}"}
        ]


class EnhancedToolChainPlanner:
    """
    Enhanced planner that creates thorough, multi-step plans.
    Integrates with n8n and supports multiple planning strategies.
    """
    
    def __init__(self, agent, tools: List[Any], enable_n8n: bool = False, n8n_url: str = "http://localhost:5678"):
        self.agent = agent
        self.deep_llm = agent.deep_llm
        self.fast_llm = agent.fast_llm
        self.tools = tools
        self.stream_llm = getattr(agent, "stream_llm", None)
        
        # Create tool reference for the planner
        self.tool_descriptions = self._create_tool_reference()
        
        # n8n integration
        self.enable_n8n = enable_n8n
        if enable_n8n:
            try:
                from Toolchain.n8n_toolchain import N8nToolchainBridge
                self.n8n_bridge = N8nToolchainBridge(n8n_url=n8n_url)
            except ImportError:
                logger.warning("n8n integration requested but not available")
                self.enable_n8n = False
                self.n8n_bridge = None
        else:
            self.n8n_bridge = None
        
        # Plan templates
        self.templates = PlanTemplate()
        
        # Planning context
        self._last_query = None
        self._last_strategy = None
        self._execution_history = []
    
    def _create_tool_reference(self) -> str:
        """Create a comprehensive tool reference for the planner."""
        tool_info = []
        
        for tool in self.tools:
            name = getattr(tool, "name", str(tool))
            desc = getattr(tool, "description", "")
            
            # Enhanced descriptions for common patterns
            enhanced_desc = desc
            if "web_search" in name and "deep" not in name:
                enhanced_desc += " → Returns URLs. Use web_search_deep to fetch actual content from URLs."
            elif "web_search_deep" in name:
                enhanced_desc += " → Fetches and parses full page content from search results or URLs."
            elif "llm" in name.lower():
                enhanced_desc += " → Can analyze, summarize, or reason about data from previous steps."
            
            tool_info.append(f"- {name}: {enhanced_desc}")
        
        return "\n".join(tool_info)
    
    def plan_tool_chain(self, query: str, strategy: PlanningStrategy = PlanningStrategy.STATIC, 
                       history_context: str = "", max_alternatives: int = 3) -> Generator:
        """
        Create a plan using the specified strategy.
        
        Args:
            query: User query
            strategy: Planning strategy to use
            history_context: Previous execution context
            max_alternatives: Number of alternative plans (for exploratory/multipath)
        """
        self._last_query = query
        self._last_strategy = strategy
        
        if strategy == PlanningStrategy.QUICK:
            yield from self._plan_quick(query, history_context)
        elif strategy == PlanningStrategy.COMPREHENSIVE:
            yield from self._plan_comprehensive(query, history_context)
        elif strategy == PlanningStrategy.EXPLORATORY:
            yield from self._plan_exploratory(query, history_context, max_alternatives)
        elif strategy == PlanningStrategy.MULTIPATH:
            yield from self._plan_multipath(query, history_context, max_alternatives)
        elif strategy == PlanningStrategy.DYNAMIC:
            # Dynamic planning is handled during execution
            yield from self._plan_static(query, history_context)
        else:  # STATIC (default)
            yield from self._plan_static(query, history_context)
    
    def _plan_static(self, query: str, history_context: str = "") -> Generator:
        """Create a comprehensive static plan."""
        
        # First, analyze the query to understand what's needed
        analysis_prompt = f"""
Analyze this query and determine what type of task it is:

Query: {query}
Previous context: {history_context}

Classify the task and identify required steps. Consider:
1. Is this a research task? (needs web search → content fetching → analysis)
2. Is this a coding task? (needs code generation → execution → verification)
3. Is this a data task? (needs data loading → processing → analysis)
4. Is this a comparison? (needs multiple searches → synthesis)
5. Is this a creation task? (needs research → outline → writing → saving)

Respond with JSON:
{{
    "task_type": "research|coding|data|comparison|creation|other",
    "complexity": "simple|moderate|complex",
    "needs_web": true/false,
    "needs_deep_content": true/false,
    "needs_analysis": true/false,
    "needs_output_file": true/false,
    "reasoning": "brief explanation"
}}
"""
        
        analysis_response = ""
        if self.stream_llm:
            for chunk in self.stream_llm(self.fast_llm, analysis_prompt):
                analysis_response += chunk
        else:
            analysis_response = self.fast_llm.invoke(analysis_prompt)
        
        # Parse analysis
        analysis_response = self._clean_json(analysis_response)
        try:
            analysis = json.loads(analysis_response)
        except:
            # Fallback if analysis fails
            analysis = {
                "task_type": "other",
                "complexity": "moderate",
                "needs_web": "search" in query.lower() or "find" in query.lower(),
                "needs_deep_content": False,
                "needs_analysis": True,
                "needs_output_file": "report" in query.lower() or "document" in query.lower()
            }
        
        # Now create a comprehensive plan based on analysis
        planning_prompt = f"""
You are an expert planning assistant creating THOROUGH, COMPLETE plans.

Task Analysis:
{json.dumps(analysis, indent=2)}

Query: {query}
Previous attempts: {history_context}

Available tools:
{self.tool_descriptions}

CRITICAL PLANNING RULES:
1. **Follow Through**: If you search, you MUST fetch and parse the results
   - web_search returns only URLs → ALWAYS follow with web_search_deep to get actual content
   - Don't stop at URLs - get the actual information

2. **Complete Chains**: Think about the full workflow
   - Search → Fetch → Parse → Analyze (not just Search)
   - Generate → Execute → Verify (not just Generate)
   - Read → Process → Output (not just Read)

3. **Use Appropriate Tools**:
   - web_search: Gets URLs only
   - web_search_deep: Gets actual page content (use this after web_search!)
   - deep_llm: For analysis, synthesis, complex reasoning
   - fast_llm: For quick processing, formatting

4. **Reference Previous Steps**:
   - Use {{prev}} for the immediately previous step
   - Use {{step_N}} to reference any specific step

EXAMPLES OF GOOD PLANS:

Example 1 - Research Query:
Query: "What are the latest AI developments?"
GOOD PLAN:
[
  {{"tool": "web_search", "input": "latest AI developments 2024"}},
  {{"tool": "web_search_deep", "input": "{{prev}}"}},  ← Fetches actual content!
  {{"tool": "deep_llm", "input": "Analyze and summarize the key AI developments: {{prev}}"}}
]
BAD PLAN:
[
  {{"tool": "web_search", "input": "latest AI developments 2024"}},
  {{"tool": "deep_llm", "input": "Summarize: {{prev}}"}}  ← Only has URLs, not content!
]

Example 2 - Comparison Task:
Query: "Compare Python vs JavaScript"
GOOD PLAN:
[
  {{"tool": "web_search", "input": "Python programming language features"}},
  {{"tool": "web_search_deep", "input": "{{step_1}}"}},
  {{"tool": "web_search", "input": "JavaScript programming language features"}},
  {{"tool": "web_search_deep", "input": "{{step_3}}"}},
  {{"tool": "deep_llm", "input": "Compare Python and JavaScript based on:\\nPython: {{step_2}}\\nJavaScript: {{step_4}}"}}
]

Example 3 - Code Task:
Query: "Write a function to sort a list"
GOOD PLAN:
[
  {{"tool": "deep_llm", "input": "Write a Python function to sort a list with examples"}},
  {{"tool": "python", "input": "{{prev}}"}},
  {{"tool": "fast_llm", "input": "Review the execution. If errors, explain and suggest fixes: {{prev}}"}}
]

Now create a COMPREHENSIVE plan for this query. Make it complete and thorough!

Respond with ONLY a JSON array of steps:
[
  {{"tool": "tool_name", "input": "input text or {{prev}} or {{step_N}}"}},
  ...
]
"""
        
        plan_json = ""
        if self.stream_llm:
            for chunk in self.stream_llm(self.deep_llm, planning_prompt):
                yield chunk
                plan_json += chunk
        else:
            plan_json = self.deep_llm.invoke(planning_prompt)
            yield plan_json
        
        # Clean and parse
        plan_json = self._clean_json(plan_json)
        
        try:
            tool_plan = json.loads(plan_json)
        except Exception as e:
            raise ValueError(f"Planning failed: {e}\n\n{plan_json}")
        
        # Validate and enhance the plan
        tool_plan = self._validate_and_enhance_plan(tool_plan, analysis)
        
        # Save plan
        plan_id = hashlib.sha256(f"{time.time()}_{json.dumps(tool_plan)}".encode()).hexdigest()
        self._save_plan(tool_plan, plan_id)
        
        # Export to n8n if enabled
        if self.enable_n8n and self.n8n_bridge:
            try:
                workflow_id = self.n8n_bridge.export_toolchain_to_n8n(
                    tool_plan, 
                    f"Toolchain_{plan_id[:8]}"
                )
                yield f"\n[n8n] Exported to workflow {workflow_id}\n"
            except Exception as e:
                logger.warning(f"n8n export failed: {e}")
        
        yield tool_plan
    
    def _plan_quick(self, query: str, history_context: str = "") -> Generator:
        """Create a minimal, fast plan for simple queries."""
        
        prompt = f"""
Create a MINIMAL plan for this simple query. 1-3 steps maximum.

Query: {query}
Tools: {self.tool_descriptions}

Quick plan as JSON array:
"""
        
        plan_json = ""
        if self.stream_llm:
            for chunk in self.stream_llm(self.fast_llm, prompt):
                yield chunk
                plan_json += chunk
        else:
            plan_json = self.fast_llm.invoke(prompt)
            yield plan_json
        
        plan_json = self._clean_json(plan_json)
        tool_plan = json.loads(plan_json)
        
        if isinstance(tool_plan, dict):
            tool_plan = [tool_plan]
        
        plan_id = hashlib.sha256(f"{time.time()}_{json.dumps(tool_plan)}".encode()).hexdigest()
        self._save_plan(tool_plan, plan_id)
        
        yield tool_plan
    
    def _plan_comprehensive(self, query: str, history_context: str = "") -> Generator:
        """Create an exhaustive, thorough plan with maximum detail."""
        
        prompt = f"""
Create the MOST COMPREHENSIVE plan possible for this query.
Include ALL necessary steps: research, fetching, parsing, analysis, verification, output.

Query: {query}
Previous: {history_context}

Tools available:
{self.tool_descriptions}

Rules for comprehensive planning:
1. Break down into granular steps
2. Always fetch actual content after searches
3. Include multiple analysis passes
4. Add verification steps
5. Save important outputs
6. Include error recovery options

Create a detailed, thorough plan (5-15 steps) as JSON array:
"""
        
        plan_json = ""
        if self.stream_llm:
            for chunk in self.stream_llm(self.deep_llm, prompt):
                yield chunk
                plan_json += chunk
        else:
            plan_json = self.deep_llm.invoke(prompt)
            yield plan_json
        
        plan_json = self._clean_json(plan_json)
        tool_plan = json.loads(plan_json)
        
        plan_id = hashlib.sha256(f"{time.time()}_{json.dumps(tool_plan)}".encode()).hexdigest()
        self._save_plan(tool_plan, plan_id)
        
        yield tool_plan
    
    def _plan_exploratory(self, query: str, history_context: str = "", 
                         max_alternatives: int = 3) -> Generator:
        """Create multiple alternative plans to explore different approaches."""
        
        prompt = f"""
Create {max_alternatives} DIFFERENT alternative plans for solving this query.
Each plan should take a different approach or strategy.

Query: {query}
Previous: {history_context}

Tools: {self.tool_descriptions}

Respond with JSON:
{{
  "alternatives": [
    [{{"tool": "...", "input": "..."}}, ...],  ← Approach 1
    [{{"tool": "...", "input": "..."}}, ...],  ← Approach 2
    [{{"tool": "...", "input": "..."}}, ...]   ← Approach 3
  ]
}}
"""
        
        plan_json = ""
        if self.stream_llm:
            for chunk in self.stream_llm(self.deep_llm, prompt):
                yield chunk
                plan_json += chunk
        else:
            plan_json = self.deep_llm.invoke(prompt)
            yield plan_json
        
        plan_json = self._clean_json(plan_json)
        result = json.loads(plan_json)
        
        alternatives = result.get("alternatives", [result]) if isinstance(result, dict) else [result]
        
        plan_id = hashlib.sha256(f"{time.time()}_{json.dumps(alternatives)}".encode()).hexdigest()
        self._save_plan(alternatives, plan_id)
        
        yield alternatives
    
    def _plan_multipath(self, query: str, history_context: str = "", 
                       max_paths: int = 2) -> Generator:
        """Create a plan with branching paths based on intermediate results."""
        
        prompt = f"""
Create a plan that branches based on intermediate results.
Include conditional paths and fallback options.

Query: {query}

Tools: {self.tool_descriptions}

Create a branching plan structure with primary and fallback paths.
JSON format:
{{
  "primary_path": [steps...],
  "fallback_paths": [[steps...], [steps...]]
}}
"""
        
        plan_json = ""
        if self.stream_llm:
            for chunk in self.stream_llm(self.deep_llm, prompt):
                yield chunk
                plan_json += chunk
        else:
            plan_json = self.deep_llm.invoke(prompt)
            yield plan_json
        
        plan_json = self._clean_json(plan_json)
        result = json.loads(plan_json)
        
        yield result
    
    def _validate_and_enhance_plan(self, plan: List[Dict], analysis: Dict) -> List[Dict]:
        """
        Validate and enhance plan to ensure completeness.
        Automatically adds missing steps for common patterns.
        """
        enhanced_plan = []
        
        for i, step in enumerate(plan):
            enhanced_plan.append(step)
            
            # Pattern: web_search not followed by web_search_deep
            if step.get("tool") == "web_search":
                # Check if next step fetches content
                if i + 1 < len(plan):
                    next_step = plan[i + 1]
                    if next_step.get("tool") != "web_search_deep":
                        # Insert content fetching step
                        enhanced_plan.append({
                            "tool": "web_search_deep",
                            "input": "{prev}",
                            "_auto_added": True,
                            "_reason": "Fetch actual content from search results"
                        })
                else:
                    # Add at end if it's the last step
                    enhanced_plan.append({
                        "tool": "web_search_deep",
                        "input": "{prev}",
                        "_auto_added": True,
                        "_reason": "Fetch actual content from search results"
                    })
            
            # Pattern: Multiple web_search_deep results should be synthesized
            if step.get("tool") == "web_search_deep" and i > 0:
                # Check if there's analysis after fetching
                if i + 1 >= len(plan) or plan[i + 1].get("tool") not in ["deep_llm", "fast_llm"]:
                    enhanced_plan.append({
                        "tool": "deep_llm",
                        "input": f"Analyze and synthesize the information: {{prev}}",
                        "_auto_added": True,
                        "_reason": "Analysis step after content fetching"
                    })
        
        # Add output file if analysis indicates it's needed
        if analysis.get("needs_output_file") and not any(s.get("tool") == "write_file" for s in enhanced_plan):
            enhanced_plan.append({
                "tool": "write_file",
                "input": f"output_{int(time.time())}.md|||{{prev}}",
                "_auto_added": True,
                "_reason": "Save results to file"
            })
        
        return enhanced_plan
    
    def _clean_json(self, text: str) -> str:
        """Remove markdown code fences and clean JSON."""
        text = re.sub(r'^```json\s*', '', text.strip())
        text = re.sub(r'^```\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        return text.strip()
    
    def _save_plan(self, plan: Any, plan_id: str):
        """Save plan to memory and file."""
        try:
            # Save to file
            with open("./Configuration/last_tool_plan.json", "w", encoding="utf-8") as f:
                json.dump(plan, f, indent=2)
            
            # Save to memory if available
            if hasattr(self.agent, "mem"):
                self.agent.mem.add_session_memory(
                    self.agent.sess.id,
                    json.dumps(plan),
                    "Plan",
                    {"topic": "plan", "plan_id": plan_id, "strategy": self._last_strategy.value if self._last_strategy else "static"},
                    promote=True
                )
        except Exception as e:
            logger.warning(f"Failed to save plan: {e}")
    
    def execute_tool_chain(self, query: str, plan=None, strategy: PlanningStrategy = PlanningStrategy.STATIC,
                          use_n8n: bool = False) -> Generator:
        """
        Execute a tool chain with the specified strategy.
        
        Args:
            query: User query
            plan: Pre-existing plan (optional)
            strategy: Planning strategy
            use_n8n: Execute via n8n if available
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
            # Multipath or structured plan
            if "primary_path" in tool_plan:
                tool_plan = tool_plan["primary_path"]
            elif "alternatives" in tool_plan:
                tool_plan = tool_plan["alternatives"][0]  # Use first alternative
            else:
                tool_plan = [tool_plan]
        
        if not isinstance(tool_plan, list):
            yield "[Error] Invalid plan structure"
            return
        
        # Execute via n8n if requested and available
        if use_n8n and self.enable_n8n and self.n8n_bridge:
            yield "\n[n8n] Executing via n8n workflow engine...\n"
            try:
                from Toolchain.n8n_toolchain import N8nToolchainExecutor
                executor = N8nToolchainExecutor(self.n8n_bridge)
                result = executor.execute_via_n8n(tool_plan, save_workflow=True)
                yield result
                return
            except Exception as e:
                yield f"[n8n] Execution failed: {e}\n[n8n] Falling back to local execution...\n"
        
        # Local execution
        yield from self._execute_local(tool_plan, query)
    
    def _execute_local(self, plan: List[Dict], query: str) -> Generator:
        """Execute plan locally."""
        executed = {}
        step_num = 0
        
        for step in plan:
            step_num += 1
            tool_name = step.get("tool")
            tool_input = str(step.get("input", ""))
            
            # Show if auto-added
            if step.get("_auto_added"):
                yield f"\n[Auto-added step {step_num}] {step.get('_reason', '')}\n"
            
            # Resolve placeholders
            if "{prev}" in tool_input:
                tool_input = tool_input.replace("{prev}", str(executed.get(f"step_{step_num-1}", "")))
            
            for i in range(1, step_num):
                tool_input = tool_input.replace(f"{{step_{i}}}", str(executed.get(f"step_{i}", "")))
            
            # Special handling for write_file with ||| separator
            if tool_name == "write_file" and "|||" in tool_input:
                path, content = tool_input.split("|||", 1)
                tool_input = json.dumps({"path": path.strip(), "content": content.strip()})
            
            # Inject memory context for LLM tools
            if "llm" in tool_name.lower():
                try:
                    chat_hist = self.agent.buffer_memory.load_memory_variables({}).get("chat_history", "")
                    if chat_hist:
                        tool_input = f"Context: {chat_hist}\n{tool_input}"
                except:
                    pass
            
            yield f"\n[Step {step_num}] Executing: {tool_name}\n"
            yield f"[Input] {tool_input[:200]}{'...' if len(tool_input) > 200 else ''}\n"
            
            # Find and execute tool
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
                        yield chunk
                        collected.append(chunk)
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


def integrate_enhanced_planner(vera_instance, enable_n8n: bool = False):
    """
    Replace Vera's toolchain planner with the enhanced version.
    
    Usage in Vera.__init__:
        from enhanced_toolchain_planner import integrate_enhanced_planner
        integrate_enhanced_planner(self, enable_n8n=True)
    """
    vera_instance.toolchain = EnhancedToolChainPlanner(
        vera_instance,
        vera_instance.tools,
        enable_n8n=enable_n8n
    )
    
    print("[Enhanced Planner] Loaded with intelligent plan generation")
    print("[Enhanced Planner] Strategies: static, quick, comprehensive, exploratory, multipath, dynamic")
    
    if enable_n8n:
        print("[Enhanced Planner] n8n integration enabled")