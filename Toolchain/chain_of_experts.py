"""
Enhanced Expert Toolchain System
==================================

Three-stage intelligent tool execution:
1. TRIAGE: Analyze problem and select relevant domain experts
2. EXPERT SELECTION: Build domain-specific tool lists
3. PLANNING & EXECUTION: Domain expert plans and executes with specialized tools

Features:
- Domain tagging for tools
- Multi-expert collaboration
- Intelligent tool filtering
- Drop-in replacement for standard toolchain
- Runs alongside existing toolchain
"""

from typing import List, Dict, Set, Optional, Any
import json
import hashlib
import time
import traceback
from dataclasses import dataclass, field
from enum import Enum


# ============================================================================
# DOMAIN DEFINITIONS
# ============================================================================

class Domain(Enum):
    """Supported expert domains"""
    # Technical domains
    WEB_DEVELOPMENT = "web_development"
    BACKEND_DEVELOPMENT = "backend_development"
    DATABASE = "database"
    DEVOPS = "devops"
    SECURITY = "security"
    NETWORKING = "networking"
    
    # Data domains
    DATA_ANALYSIS = "data_analysis"
    MACHINE_LEARNING = "machine_learning"
    DATA_ENGINEERING = "data_engineering"
    
    # Content domains
    RESEARCH = "research"
    WRITING = "writing"
    DOCUMENTATION = "documentation"
    
    # System domains
    FILE_OPERATIONS = "file_operations"
    CODE_EXECUTION = "code_execution"
    SYSTEM_ADMINISTRATION = "system_administration"
    
    # Communication domains
    API_INTEGRATION = "api_integration"
    WEB_SCRAPING = "web_scraping"
    EMAIL = "email"
    
    # Specialized domains
    OSINT = "osint"
    PENETRATION_TESTING = "penetration_testing"
    VULNERABILITY_ANALYSIS = "vulnerability_analysis"
    
    # Language domains
    BASH = "bash"
    PYTHON = "python"

    # General
    GENERAL = "general"


# ============================================================================
# TOOL DOMAIN REGISTRY
# ============================================================================

@dataclass
class DomainToolMetadata:
    """Metadata for domain-tagged tools"""
    tool_name: str
    domains: Set[Domain]
    priority: int = 1  # Higher = more important for domain
    requires_authentication: bool = False
    cost_level: int = 0  # 0=free, 1=low, 2=medium, 3=high
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
        self.register("crawl_website", {Domain.WEB_SCRAPING, Domain.RESEARCH}, priority=2)
        self.register("query_crawl_memory", {Domain.RESEARCH, Domain.WEB_SCRAPING}, priority=2)
        self.register("navigate_web_smart", {Domain.RESEARCH, Domain.WEB_SCRAPING}, priority=2)
        
        # API & HTTP
        self.register("http_request", {Domain.API_INTEGRATION, Domain.WEB_DEVELOPMENT}, priority=3)
        self.register("babelfish", {Domain.API_INTEGRATION, Domain.NETWORKING}, priority=2)
        
        # Database
        self.register("sqlite_query", {Domain.DATABASE, Domain.DATA_ANALYSIS}, priority=3)
        self.register("postgres_query", {Domain.DATABASE, Domain.DATA_ENGINEERING}, priority=3)
        
        # Security & OSINT
        self.register("nmap_scan", {Domain.SECURITY, Domain.NETWORKING, Domain.OSINT}, priority=3)
        self.register("vulnerability_search", {Domain.SECURITY, Domain.VULNERABILITY_ANALYSIS}, priority=3)
        self.register("osint_search", {Domain.OSINT, Domain.RESEARCH}, priority=2)
        self.register("dorking_search", {Domain.OSINT, Domain.RESEARCH}, priority=2)
        
        # DevOps
        self.register("git", {Domain.DEVOPS, Domain.BACKEND_DEVELOPMENT}, priority=2)
        self.register("docker_exec", {Domain.DEVOPS, Domain.SYSTEM_ADMINISTRATION}, priority=2)
        
        # LLM tasks
        self.register("fast_llm", {Domain.GENERAL, Domain.WRITING}, priority=2)
        self.register("deep_llm", {Domain.RESEARCH, Domain.WRITING, Domain.DOCUMENTATION}, priority=2)
        
        # Memory
        self.register("search_memory", {Domain.GENERAL}, priority=1)
    
    def register(self, tool_name: str, domains: Set[Domain], 
                priority: int = 1, requires_auth: bool = False,
                cost_level: int = 0, description: Optional[str] = None):
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
    
    def get_tools_for_domain(self, domain: Domain) -> List[str]:
        """Get all tools tagged with a domain"""
        return [
            name for name, meta in self.tool_domains.items()
            if domain in meta.domains
        ]
    
    def get_tools_for_domains(self, domains: Set[Domain]) -> List[str]:
        """Get all tools tagged with any of the specified domains"""
        tools = set()
        for domain in domains:
            tools.update(self.get_tools_for_domain(domain))
        return list(tools)
    
    def get_prioritized_tools(self, domain: Domain) -> List[tuple]:
        """Get tools for domain sorted by priority"""
        tools = [
            (name, meta.priority)
            for name, meta in self.tool_domains.items()
            if domain in meta.domains
        ]
        return sorted(tools, key=lambda x: x[1], reverse=True)


# ============================================================================
# EXPERT DEFINITIONS
# ============================================================================

@dataclass
class DomainExpert:
    """Expert agent for a specific domain"""
    name: str
    domain: Domain
    description: str
    model: str = "gemma2"  # Default model
    temperature: float = 0.7
    system_prompt: Optional[str] = None
    specialization: Optional[str] = None


class ExpertRegistry:
    """Registry of domain experts"""
    
    def __init__(self):
        self.experts: Dict[Domain, DomainExpert] = {}
        self._initialize_default_experts()
    
    def _initialize_default_experts(self):
        """Initialize default domain experts"""
        
        self.register(DomainExpert(
            name="Web Development Expert",
            domain=Domain.WEB_DEVELOPMENT,
            description="Expert in frontend development, HTML/CSS/JS, frameworks",
            system_prompt="You are a web development expert. Focus on creating clean, modern, accessible web applications."
        ))
        
        self.register(DomainExpert(
            name="Security Analyst",
            domain=Domain.SECURITY,
            description="Expert in cybersecurity, vulnerability assessment, secure coding",
            model="gemma2",
            temperature=0.5,
            system_prompt="You are a security expert. Prioritize security best practices and identify vulnerabilities."
        ))
        
        self.register(DomainExpert(
            name="Data Scientist",
            domain=Domain.DATA_ANALYSIS,
            description="Expert in data analysis, visualization, statistical methods",
            system_prompt="You are a data scientist. Focus on extracting insights from data using rigorous methods."
        ))
        
        self.register(DomainExpert(
            name="Research Specialist",
            domain=Domain.RESEARCH,
            description="Expert in information gathering, synthesis, and verification",
            system_prompt="You are a research specialist. Gather comprehensive information and verify sources."
        ))
        
        self.register(DomainExpert(
            name="DevOps Engineer",
            domain=Domain.DEVOPS,
            description="Expert in CI/CD, infrastructure automation, deployment",
            system_prompt="You are a DevOps engineer. Focus on automation, reliability, and efficiency."
        ))
        
        self.register(DomainExpert(
            name="OSINT Investigator",
            domain=Domain.OSINT,
            description="Expert in open-source intelligence gathering and analysis",
            system_prompt="You are an OSINT specialist. Use all available public information systematically."
        ))
        
        self.register(DomainExpert(
            name="Database Administrator",
            domain=Domain.DATABASE,
            description="Expert in database design, optimization, and querying",
            system_prompt="You are a database expert. Focus on efficient queries and data integrity."
        ))
    
    def register(self, expert: DomainExpert):
        """Register an expert"""
        self.experts[expert.domain] = expert
    
    def get_expert(self, domain: Domain) -> Optional[DomainExpert]:
        """Get expert for domain"""
        return self.experts.get(domain)
    
    def get_expert_by_domains(self, domains: Set[Domain]) -> List[DomainExpert]:
        """Get experts for multiple domains"""
        return [
            self.experts[domain]
            for domain in domains
            if domain in self.experts
        ]


# ============================================================================
# STAGE 1: TRIAGE
# ============================================================================

class ExpertTriageAgent:
    """
    Stage 1: Analyze problem and select relevant domain experts
    """
    
    def __init__(self, agent, expert_registry: ExpertRegistry, 
                 tool_registry: ToolDomainRegistry):
        self.agent = agent
        self.expert_registry = expert_registry
        self.tool_registry = tool_registry
    
    def analyze_and_select_experts(self, query: str) -> Dict[str, Any]:
        """
        Analyze query and select relevant experts
        
        Returns:
            {
                'primary_domains': [Domain, ...],
                'secondary_domains': [Domain, ...],
                'selected_experts': [DomainExpert, ...],
                'reasoning': str,
                'complexity': str  # 'simple', 'moderate', 'complex'
            }
        """
        
        print("[Expert Triage] Analyzing query and selecting experts...")
        
        # Build expert selection prompt
        available_experts = "\n".join([
            f"- {expert.domain.value}: {expert.description}"
            for expert in self.expert_registry.experts.values()
        ])
        
        triage_prompt = f"""You are an expert coordinator. Analyze the following task and select the most appropriate domain experts.

Available Experts:
{available_experts}

Task: {query}

Respond in JSON format:
{{
    "primary_domains": ["domain1", "domain2"],  // Most critical domains (1-3)
    "secondary_domains": ["domain3"],            // Supporting domains (0-2)
    "complexity": "simple|moderate|complex",     // Task complexity
    "requires_collaboration": true|false,        // Multiple experts needed?
    "reasoning": "Brief explanation of expert selection"
}}

Only return valid JSON, no other text."""
        
        # Stream triage analysis
        triage_json = ""
        for chunk in self.agent.stream_llm(self.agent.fast_llm, triage_prompt):
            triage_json += chunk
            yield chunk
        
        # Parse result
        triage_json = triage_json.strip()
        for prefix in ("```json", "```"):
            if triage_json.startswith(prefix):
                triage_json = triage_json[len(prefix):].strip()
        if triage_json.endswith("```"):
            triage_json = triage_json[:-3].strip()
        
        try:
            result = json.loads(triage_json)
        except json.JSONDecodeError as e:
            print(f"[Expert Triage] Failed to parse JSON: {e}")
            # Fallback to general domain
            result = {
                "primary_domains": ["general"],
                "secondary_domains": [],
                "complexity": "simple",
                "requires_collaboration": False,
                "reasoning": "Fallback to general domain due to parsing error"
            }
        
        # Convert domain strings to Domain enums
        primary_domains = [
            Domain(d.lower()) for d in result.get("primary_domains", [])
            if d.lower() in [domain.value for domain in Domain]
        ]
        
        secondary_domains = [
            Domain(d.lower()) for d in result.get("secondary_domains", [])
            if d.lower() in [domain.value for domain in Domain]
        ]
        
        # Get experts
        all_domains = set(primary_domains + secondary_domains)
        selected_experts = self.expert_registry.get_expert_by_domains(all_domains)
        
        analysis = {
            'primary_domains': primary_domains,
            'secondary_domains': secondary_domains,
            'selected_experts': selected_experts,
            'reasoning': result.get('reasoning', ''),
            'complexity': result.get('complexity', 'simple'),
            'requires_collaboration': result.get('requires_collaboration', False)
        }
        
        print(f"\n[Expert Triage] Selected {len(selected_experts)} experts:")
        for expert in selected_experts:
            print(f"  - {expert.name} ({expert.domain.value})")
        print(f"[Expert Triage] Complexity: {analysis['complexity']}")
        print(f"[Expert Triage] Reasoning: {analysis['reasoning']}\n")
        
        yield analysis


# ============================================================================
# STAGE 2: TOOL FILTERING
# ============================================================================

class DomainToolFilter:
    """
    Stage 2: Build domain-specific tool lists
    """
    
    def __init__(self, agent, tool_registry: ToolDomainRegistry):
        self.agent = agent
        self.tool_registry = tool_registry
    
    def build_tool_list(self, domains: Set[Domain], all_tools: List) -> List:
        """
        Filter tools based on selected domains
        
        Args:
            domains: Selected domains
            all_tools: All available tools
            
        Returns:
            Filtered list of tools relevant to domains
        """
        
        print(f"[Tool Filter] Building specialized tool list for domains: {[d.value for d in domains]}")
        
        # Get tool names for domains
        relevant_tool_names = self.tool_registry.get_tools_for_domains(domains)
        
        # Add general tools
        relevant_tool_names.extend(
            self.tool_registry.get_tools_for_domain(Domain.GENERAL)
        )
        
        # Filter actual tool objects
        filtered_tools = [
            tool for tool in all_tools
            if tool.name in relevant_tool_names
        ]
        
        print(f"[Tool Filter] Filtered to {len(filtered_tools)} tools from {len(all_tools)} total")
        print(f"[Tool Filter] Available tools: {[t.name for t in filtered_tools][:10]}...")
        
        return filtered_tools


# ============================================================================
# STAGE 3: EXPERT PLANNING & EXECUTION
# ============================================================================

class ExpertPlanner:
    """
    Stage 3: Domain expert plans and executes with specialized tools
    """
    
    def __init__(self, agent, tool_registry: ToolDomainRegistry):
        self.agent = agent
        self.tool_registry = tool_registry
    
    def plan_tool_chain(self, query: str, expert: DomainExpert, 
                       filtered_tools: List) -> List[Dict]:
        """
        Expert creates execution plan using domain-specific tools
        """
        
        print(f"\n[Expert Planner] {expert.name} is planning the execution...")
        
        # Build tool descriptions
        tool_descriptions = []
        for tool in filtered_tools:
            # Get enhanced description if available
            meta = self.tool_registry.tool_domains.get(tool.name)
            desc = meta.description_override if meta and meta.description_override else tool.description
            
            tool_descriptions.append({
                "name": tool.name,
                "description": desc,
                "domains": [d.value for d in meta.domains] if meta else ["general"]
            })
        
        planning_prompt = f"""{expert.system_prompt}

You are planning how to solve this task using available tools.

Task: {query}

Available Tools:
{json.dumps(tool_descriptions, indent=2)}

Create a step-by-step execution plan. Each step should use ONE tool.

Respond ONLY with a JSON array of steps:
[
  {{
    "tool": "tool_name",
    "input": "input_value_or_dict",
    "reasoning": "why this step is needed"
  }},
  ...
]

Important:
- For multi-parameter tools, use {{"param1": "value1", "param2": "value2"}}
- For single-parameter tools, use a string value
- Reference previous steps with {{prev}} or {{step_N}}
- Keep the plan focused and efficient

Only return valid JSON, no other text."""
        
        plan_json = ""
        for chunk in self.agent.stream_llm(self.agent.tool_llm, planning_prompt):
            plan_json += chunk
            yield chunk
        
        # Clean and parse
        plan_json = plan_json.strip()
        for prefix in ("```json", "```"):
            if plan_json.startswith(prefix):
                plan_json = plan_json[len(prefix):].strip()
        if plan_json.endswith("```"):
            plan_json = plan_json[:-3].strip()
        
        try:
            tool_plan = json.loads(plan_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"Expert planning failed: {e}\n\n{plan_json}")
        
        # Normalize
        if isinstance(tool_plan, dict):
            tool_plan = [tool_plan]
        
        print(f"[Expert Planner] Plan created with {len(tool_plan)} steps")
        
        # Save plan
        plan_id = hashlib.sha256(f"{time.time()}_{json.dumps(tool_plan)}".encode()).hexdigest()
        self.agent.mem.add_session_memory(
            self.agent.sess.id,
            f"{json.dumps(tool_plan)}",
            "ExpertPlan",
            {"topic": "expert_plan", "plan_id": plan_id, "expert": expert.name},
            promote=True
        )
        
        yield tool_plan


# ============================================================================
# MAIN EXPERT TOOLCHAIN CONTROLLER
# ============================================================================

class ExpertToolChainPlanner:
    """
    Drop-in replacement for ToolChainPlanner with expert system
    
    Three-stage process:
    1. Triage: Select domain experts
    2. Filter: Build domain-specific tool list
    3. Plan & Execute: Expert plans and executes
    """
    
    def __init__(self, agent, tools):
        self.agent = agent
        self.tools = tools
        
        # Initialize registries
        self.tool_registry = ToolDomainRegistry()
        self.expert_registry = ExpertRegistry()
        
        # Initialize stages
        self.triage = ExpertTriageAgent(agent, self.expert_registry, self.tool_registry)
        self.tool_filter = DomainToolFilter(agent, self.tool_registry)
        self.expert_planner = ExpertPlanner(agent, self.tool_registry)
        
        print(f"[Expert Toolchain] Initialized with {len(self.expert_registry.experts)} experts")
        print(f"[Expert Toolchain] Registered {len(self.tool_registry.tool_domains)} domain-tagged tools")
    
    def register_tool_domain(self, tool_name: str, domains: Set[Domain], 
                            priority: int = 1, **kwargs):
        """Register a tool with domain tags (for custom tools)"""
        self.tool_registry.register(tool_name, domains, priority, **kwargs)
    
    def register_expert(self, expert: DomainExpert):
        """Register a custom expert"""
        self.expert_registry.register(expert)
    
    def execute_tool_chain(self, query: str, plan=None) -> str:
        """
        Execute expert toolchain with three-stage process
        
        If plan is provided, skips triage and uses provided plan directly
        """
        
        print("\n" + "="*80)
        print("EXPERT TOOLCHAIN EXECUTION")
        print("="*80)
        
        try:
            # ================================================================
            # STAGE 1: TRIAGE (select experts)
            # ================================================================
            
            if plan is None:
                yield "\n=== STAGE 1: EXPERT TRIAGE ===\n"
                
                triage_gen = self.triage.analyze_and_select_experts(query)
                analysis = None
                
                for result in triage_gen:
                    if isinstance(result, dict):
                        analysis = result
                    else:
                        yield result
                
                if not analysis:
                    raise ValueError("Triage analysis failed")
                
                selected_experts = analysis['selected_experts']
                all_domains = set(analysis['primary_domains'] + analysis['secondary_domains'])
                
                yield f"\n✓ Selected {len(selected_experts)} expert(s)\n"
                
                # ============================================================
                # STAGE 2: TOOL FILTERING
                # ============================================================
                
                yield "\n=== STAGE 2: TOOL FILTERING ===\n"
                
                filtered_tools = self.tool_filter.build_tool_list(all_domains, self.tools)
                
                yield f"✓ Filtered to {len(filtered_tools)} domain-relevant tools\n"
                
                # ============================================================
                # STAGE 3: EXPERT PLANNING
                # ============================================================
                
                yield "\n=== STAGE 3: EXPERT PLANNING ===\n"
                
                # Use primary expert for planning
                primary_expert = selected_experts[0] if selected_experts else None
                
                if not primary_expert:
                    raise ValueError("No expert selected")
                
                plan_gen = self.expert_planner.plan_tool_chain(
                    query, 
                    primary_expert,
                    filtered_tools
                )
                
                tool_plan = None
                for result in plan_gen:
                    if isinstance(result, list):
                        tool_plan = result
                    else:
                        yield result
                
                if not tool_plan:
                    raise ValueError("Planning failed")
            
            else:
                # Use provided plan
                tool_plan = plan
                filtered_tools = self.tools  # Use all tools if plan provided
            
            # ================================================================
            # STAGE 3.5: EXECUTION
            # ================================================================
            
            yield "\n\n=== STAGE 4: EXECUTION ===\n\n"
            
            print(f"\n[Expert Toolchain] Executing plan with {len(tool_plan)} steps")
            
            tool_outputs = {}
            step_num = 0
            errors_detected = False
            
            for step in tool_plan:
                step_num += 1
                tool_name = step.get("tool")
                raw_input = step.get("input", "")
                reasoning = step.get("reasoning", "")
                
                print(f"\n[Step {step_num}] Tool: {tool_name}")
                if reasoning:
                    print(f"[Step {step_num}] Reasoning: {reasoning}")
                
                # Resolve placeholders
                def resolve_placeholders(value, step_num, tool_outputs):
                    if not isinstance(value, str):
                        return value
                    
                    if "{prev}" in value:
                        prev_output = str(tool_outputs.get(f"step_{step_num-1}", ""))
                        value = value.replace("{prev}", prev_output)
                    
                    for i in range(1, step_num):
                        placeholder = f"{{step_{i}}}"
                        if placeholder in value:
                            step_output = str(tool_outputs.get(f"step_{i}", ""))
                            value = value.replace(placeholder, step_output)
                    
                    return value
                
                # Handle dict vs string input
                if isinstance(raw_input, dict):
                    tool_input = {}
                    for key, value in raw_input.items():
                        tool_input[key] = resolve_placeholders(value, step_num, tool_outputs)
                else:
                    tool_input = resolve_placeholders(str(raw_input), step_num, tool_outputs)
                
                # Parse string inputs that might be JSON
                if isinstance(tool_input, str):
                    stripped = tool_input.strip()
                    if (stripped.startswith('{') and stripped.endswith('}')) or \
                       (stripped.startswith('[') and stripped.endswith(']')):
                        try:
                            parsed = json.loads(stripped)
                            if isinstance(parsed, dict):
                                tool_input = parsed
                        except json.JSONDecodeError:
                            try:
                                import ast
                                parsed = ast.literal_eval(stripped)
                                if isinstance(parsed, dict):
                                    tool_input = parsed
                            except (ValueError, SyntaxError):
                                pass
                
                yield f"\n[Step {step_num}] {tool_name}\n"
                if reasoning:
                    yield f"  Reasoning: {reasoning}\n"
                
                # Find tool
                tool = next((t for t in filtered_tools if t.name == tool_name), None)
                
                if not tool:
                    result = f"Tool not found: {tool_name}"
                    errors_detected = True
                    yield result
                else:
                    try:
                        # Get callable
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
                        
                        # Execute
                        if isinstance(tool_input, dict):
                            exec_result = func(**tool_input)
                        else:
                            exec_result = func(tool_input)
                        
                        # Handle streaming vs non-streaming
                        collected = []
                        result = ""
                        
                        if hasattr(exec_result, '__iter__') and not isinstance(exec_result, (str, bytes, dict)):
                            for chunk in exec_result:
                                chunk_str = str(chunk)
                                yield chunk_str
                                collected.append(chunk_str)
                            result = "".join(collected)
                        else:
                            result = str(exec_result)
                            yield result
                        
                        # Store result
                        tool_outputs[f"step_{step_num}"] = result
                        tool_outputs[tool_name] = result
                        
                        # Save to memory
                        self.agent.mem.add_session_memory(
                            self.agent.sess.id,
                            f"Step {step_num} - {tool_name}\n{result}",
                            "ExpertStep",
                            {
                                "topic": "expert_step",
                                "author": "expert_toolchain",
                                "step": step_num,
                                "tool": tool_name
                            }
                        )
                    
                    except Exception as e:
                        result = f"Error executing {tool_name}: {str(e)}\n{traceback.format_exc()}"
                        errors_detected = True
                        tool_outputs[f"step_{step_num}"] = result
                        yield result
            
            # Final result
            final_result = tool_outputs.get(f"step_{step_num}", "")
            
            print(f"\n[Expert Toolchain] Execution complete")
            print("="*80 + "\n")
            
            return final_result
        
        except Exception as e:
            error_msg = f"\n[Expert Toolchain Error] {str(e)}\n{traceback.format_exc()}\n"
            print(error_msg)
            yield error_msg
            return error_msg


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_expert_toolchain(agent, tools) -> ExpertToolChainPlanner:
    """
    Create an expert toolchain instance
    
    Usage:
        expert_toolchain = create_expert_toolchain(vera_instance, tools)
        
        for chunk in expert_toolchain.execute_tool_chain("Build a secure API"):
            print(chunk, end='', flush=True)
    """
    return ExpertToolChainPlanner(agent, tools)


def register_custom_tool(expert_toolchain: ExpertToolChainPlanner,
                        tool_name: str, 
                        domains: List[str],
                        priority: int = 1):
    """
    Register a custom tool with domains
    
    Usage:
        register_custom_tool(
            expert_toolchain,
            "my_custom_tool",
            ["security", "api_integration"],
            priority=2
        )
    """
    domain_enums = [Domain(d.lower()) for d in domains]
    expert_toolchain.register_tool_domain(
        tool_name,
        set(domain_enums),
        priority=priority
    )
    print(f"✓ Registered {tool_name} with domains: {domains}")


def register_custom_expert(expert_toolchain: ExpertToolChainPlanner,
                          name: str,
                          domain: str,
                          description: str,
                          model: str = "gemma2",
                          system_prompt: Optional[str] = None):
    """
    Register a custom domain expert
    
    Usage:
        register_custom_expert(
            expert_toolchain,
            name="Blockchain Expert",
            domain="web_development",  # Use closest matching domain
            description="Expert in blockchain and smart contracts",
            system_prompt="You are a blockchain expert..."
        )
    """
    expert = DomainExpert(
        name=name,
        domain=Domain(domain.lower()),
        description=description,
        model=model,
        system_prompt=system_prompt or f"You are a {name.lower()}."
    )
    expert_toolchain.register_expert(expert)
    print(f"✓ Registered expert: {name} ({domain})")

"""
5-Stage Expert Toolchain System
================================

Proper multi-level planning with tool specialists:

STAGE 1: TRIAGE
    → Analyze query
    → Select relevant DOMAINS (not experts)
    → Output: List of domains

STAGE 2: DOMAIN FILTERING
    → Get tools for selected domains
    → Output: Tool names + short descriptions

STAGE 3: HIGH-LEVEL PLANNING
    → Domain expert creates step-by-step plan
    → Uses only tool names (no detailed inputs)
    → Output: [{"step": 1, "tool": "nmap_scan", "goal": "discover network"}]

STAGE 4: TOOL-LEVEL SPECIALIST PLANNING (per step)
    → For each step, tool specialist reads schema
    → Plans exact input/parameters for that specific tool
    → Output: {"tool": "nmap_scan", "input": {"target": "...", "scan_type": "..."}}

STAGE 5: EXECUTION
    → Execute each planned step
"""

from typing import List, Dict, Set, Optional, Any
import json
import hashlib
import time
import traceback
from dataclasses import dataclass, field
from enum import Enum

# ============================================================================
# STAGE 1: TRIAGE - SELECT DOMAINS
# ============================================================================

class DomainTriageAgent:
    """
    Stage 1: Analyze query and select relevant DOMAINS (not experts)
    """
    
    def __init__(self, agent, tool_registry: ToolDomainRegistry):
        self.agent = agent
        self.tool_registry = tool_registry
    
    def select_domains(self, query: str) -> Dict[str, Any]:
        """
        Analyze query and select relevant domains
        
        Returns:
            {
                'primary_domains': [Domain, ...],
                'secondary_domains': [Domain, ...],
                'reasoning': str,
                'complexity': str
            }
        """
        
        print("\n" + "="*80)
        print("STAGE 1: DOMAIN TRIAGE")
        print("="*80)
        
        # Build domain selection prompt
        available_domains = "\n".join([
            f"- {domain.value}: {self._get_domain_description(domain)}"
            for domain in Domain
        ])
        
        triage_prompt = f"""Analyze this task and select the most relevant technical domains.

Available Domains:
{available_domains}

Task: {query}

Select the domains needed to accomplish this task. Respond in JSON format:
{{
    "primary_domains": ["domain1", "domain2"],  // Critical domains (1-3)
    "secondary_domains": ["domain3"],           // Supporting domains (0-2)
    "complexity": "simple|moderate|complex",
    "reasoning": "Brief explanation"
}}

Only return valid JSON, no other text."""
        
        # Stream triage analysis
        triage_json = ""
        for chunk in self.agent.stream_llm(self.agent.fast_llm, triage_prompt):
            triage_json += chunk
            yield chunk
        
        # Parse result
        triage_json = triage_json.strip()
        for prefix in ("```json", "```"):
            if triage_json.startswith(prefix):
                triage_json = triage_json[len(prefix):].strip()
        if triage_json.endswith("```"):
            triage_json = triage_json[:-3].strip()
        
        try:
            result = json.loads(triage_json)
        except json.JSONDecodeError as e:
            print(f"\n[Triage] Failed to parse JSON: {e}")
            result = {
                "primary_domains": ["general"],
                "secondary_domains": [],
                "complexity": "simple",
                "reasoning": "Fallback due to parsing error"
            }
        
        # Convert to Domain enums
        primary_domains = [
            Domain(d.lower()) for d in result.get("primary_domains", [])
            if d.lower() in [domain.value for domain in Domain]
        ]
        
        secondary_domains = [
            Domain(d.lower()) for d in result.get("secondary_domains", [])
            if d.lower() in [domain.value for domain in Domain]
        ]
        
        analysis = {
            'primary_domains': primary_domains,
            'secondary_domains': secondary_domains,
            'reasoning': result.get('reasoning', ''),
            'complexity': result.get('complexity', 'simple')
        }
        
        print(f"\n✓ Selected Domains:")
        print(f"  Primary: {[d.value for d in primary_domains]}")
        print(f"  Secondary: {[d.value for d in secondary_domains]}")
        print(f"  Complexity: {analysis['complexity']}")
        print(f"  Reasoning: {analysis['reasoning']}\n")
        
        yield analysis
    
    def _get_domain_description(self, domain: Domain) -> str:
        """Get human-readable domain description"""
        descriptions = {
            Domain.SECURITY: "Cybersecurity, vulnerability scanning, pentesting",
            Domain.WEB_DEVELOPMENT: "Frontend development, HTML/CSS/JS",
            Domain.DATABASE: "SQL, NoSQL, data modeling",
            Domain.DEVOPS: "CI/CD, containers, infrastructure",
            Domain.RESEARCH: "Information gathering, web search",
            Domain.FILE_OPERATIONS: "File I/O, filesystem management",
            Domain.CODE_EXECUTION: "Running code, scripts",
            Domain.API_INTEGRATION: "REST APIs, webhooks",
            Domain.NETWORKING: "Network protocols, scanning",
            Domain.OSINT: "Open-source intelligence",
            Domain.DATA_ANALYSIS: "Data processing, statistics",
        }
        return descriptions.get(domain, "General purpose")


# ============================================================================
# STAGE 2: DOMAIN FILTERING - GET TOOLS
# ============================================================================

class DomainToolFilter:
    """
    Stage 2: Get tool names + descriptions for selected domains
    """
    
    def __init__(self, agent, tool_registry: ToolDomainRegistry):
        self.agent = agent
        self.tool_registry = tool_registry
    
    def get_tools_for_domains(self, domains: Set[Domain], all_tools: List) -> Dict[str, str]:
        """
        Get tool names and descriptions for domains
        
        Returns:
            {tool_name: short_description, ...}
        """
        
        print("\n" + "="*80)
        print("STAGE 2: DOMAIN TOOL FILTERING")
        print("="*80)
        
        # Get relevant tool names
        relevant_tool_names = self.tool_registry.get_tools_for_domains(domains)
        
        # Add general tools
        relevant_tool_names.extend(
            self.tool_registry.get_tools_for_domains({Domain.GENERAL})
        )
        
        # Build tool descriptions dict
        tool_descriptions = {}
        for tool in all_tools:
            if tool.name in relevant_tool_names:
                # Get short description (first sentence)
                desc = tool.description if hasattr(tool, 'description') else "No description"
                short_desc = desc.split('.')[0] if '.' in desc else desc
                tool_descriptions[tool.name] = short_desc[:100]
        
        print(f"\n✓ Found {len(tool_descriptions)} relevant tools")
        print(f"  Tools: {list(tool_descriptions.keys())[:10]}...")
        
        return tool_descriptions


# ============================================================================
# STAGE 3: HIGH-LEVEL PLANNING - TOOL SEQUENCE
# ============================================================================

class HighLevelPlanner:
    """
    Stage 3: Create step-by-step plan with tool names only (no inputs)
    """
    
    def __init__(self, agent):
        self.agent = agent
    
    def create_high_level_plan(self, query: str, domains: Set[Domain], 
                               tool_descriptions: Dict[str, str]) -> List[Dict]:
        """
        Create high-level execution plan (tool names + goals only)
        
        Returns:
            [
                {"step": 1, "tool": "nmap_scan", "goal": "Discover network devices"},
                {"step": 2, "tool": "vulnerability_search", "goal": "Find CVEs"},
                ...
            ]
        """
        
        print("\n" + "="*80)
        print("STAGE 3: HIGH-LEVEL PLANNING")
        print("="*80)
        
        # Build planning prompt
        tools_list = "\n".join([
            f"  - {name}: {desc}"
            for name, desc in tool_descriptions.items()
        ])
        
        planning_prompt = f"""You are a strategic planner for domains: {[d.value for d in domains]}

Task: {query}

Available Tools:
{tools_list}

Create a high-level step-by-step plan. Each step should:
- Use ONE tool
- Have a clear goal
- Build on previous steps when needed

Respond with a JSON array:
[
  {{
    "step": 1,
    "tool": "tool_name",
    "goal": "What this step accomplishes",
    "depends_on": []  // Optional: which steps this needs
  }},
  ...
]

Do NOT specify tool inputs/parameters - just the sequence and goals.
Only return valid JSON, no other text."""
        
        plan_json = ""
        for chunk in self.agent.stream_llm(self.agent.tool_llm, planning_prompt):
            plan_json += chunk
            yield chunk
        
        # Parse
        plan_json = plan_json.strip()
        for prefix in ("```json", "```"):
            if plan_json.startswith(prefix):
                plan_json = plan_json[len(prefix):].strip()
        if plan_json.endswith("```"):
            plan_json = plan_json[:-3].strip()
        
        try:
            high_level_plan = json.loads(plan_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"High-level planning failed: {e}\n\n{plan_json}")
        
        # Normalize
        if isinstance(high_level_plan, dict):
            high_level_plan = [high_level_plan]
        
        print(f"\n✓ Created plan with {len(high_level_plan)} steps:")
        for step in high_level_plan:
            print(f"  {step['step']}. {step['tool']}: {step['goal']}")
        
        # Save to memory
        plan_id = hashlib.sha256(f"{time.time()}_{json.dumps(high_level_plan)}".encode()).hexdigest()
        self.agent.mem.add_session_memory(
            self.agent.sess.id,
            json.dumps(high_level_plan, indent=2),
            "HighLevelPlan",
            {"topic": "high_level_plan", "plan_id": plan_id},
            promote=True
        )
        
        yield high_level_plan


# ============================================================================
# STAGE 4: TOOL SPECIALIST - DETAILED PARAMETER PLANNING
# ============================================================================

class ToolSpecialist:
    """
    Stage 4: For each tool, create detailed input/parameter plan
    
    This is the KEY missing piece - tool-level experts that understand schemas!
    """
    
    def __init__(self, agent):
        self.agent = agent
    
    def plan_tool_execution(self, tool, step_goal: str, previous_outputs: Dict[str, str],
                           context: str) -> Dict[str, Any]:
        """
        Plan exact inputs/parameters for a specific tool
        
        Args:
            tool: The actual tool object (with schema)
            step_goal: What this step should accomplish
            previous_outputs: Outputs from previous steps
            context: Original query context
            
        Returns:
            {
                "tool": "tool_name",
                "input": "value" or {"param1": "val1", ...},
                "reasoning": "Why these parameters"
            }
        """
        
        print(f"\n  [Tool Specialist] Planning inputs for: {tool.name}")
        
        # Extract tool schema
        schema_info = self._extract_tool_schema(tool)
        
        # Build specialist prompt
        prev_context = ""
        if previous_outputs:
            prev_context = "Previous step outputs:\n"
            for step_id, output in previous_outputs.items():
                prev_context += f"  {step_id}: {output[:200]}...\n"
        
        specialist_prompt = f"""You are a tool specialist for: {tool.name}

Tool Description: {tool.description if hasattr(tool, 'description') else 'No description'}

Tool Schema:
{schema_info}

Overall Task: {context}

This Step's Goal: {step_goal}

{prev_context}

Plan the EXACT inputs/parameters for this tool to accomplish the goal.

Rules:
- If multi-parameter tool: return {{"param1": "value1", "param2": "value2"}}
- If single-parameter tool: return "value"
- Use {{prev}} to reference previous step output
- Use {{step_N}} to reference specific step output
- Make sure all required parameters are provided

Respond with JSON:
{{
    "input": "value" or {{"param": "val"}},
    "reasoning": "Brief explanation of parameter choices"
}}

Only return valid JSON, no other text."""
        
        plan_json = ""
        for chunk in self.agent.stream_llm(self.agent.fast_llm, specialist_prompt):
            plan_json += chunk
        
        # Parse
        plan_json = plan_json.strip()
        for prefix in ("```json", "```"):
            if plan_json.startswith(prefix):
                plan_json = plan_json[len(prefix):].strip()
        if plan_json.endswith("```"):
            plan_json = plan_json[:-3].strip()
        
        try:
            result = json.loads(plan_json)
        except json.JSONDecodeError as e:
            print(f"  [Tool Specialist] Failed to parse JSON: {e}")
            # Fallback
            result = {
                "input": step_goal,
                "reasoning": "Fallback to goal as input"
            }
        
        print(f"  [Tool Specialist] Planned input: {str(result['input'])[:100]}...")
        print(f"  [Tool Specialist] Reasoning: {result['reasoning']}")
        
        return {
            "tool": tool.name,
            "input": result["input"],
            "reasoning": result["reasoning"]
        }
    
    def _extract_tool_schema(self, tool) -> str:
        """Extract schema information from tool"""
        schema_parts = []
        
        # Try to get schema
        if hasattr(tool, 'args_schema') and tool.args_schema:
            try:
                schema = tool.args_schema.schema()
                properties = schema.get('properties', {})
                required = schema.get('required', [])
                
                if properties:
                    schema_parts.append("Parameters:")
                    for param_name, param_info in properties.items():
                        param_type = param_info.get('type', 'string')
                        param_desc = param_info.get('description', 'No description')
                        is_req = " [REQUIRED]" if param_name in required else " [OPTIONAL]"
                        
                        schema_parts.append(f"  - {param_name} ({param_type}){is_req}: {param_desc}")
                        
                        if 'enum' in param_info:
                            schema_parts.append(f"    Allowed: {param_info['enum']}")
                else:
                    schema_parts.append("Single parameter tool (no schema)")
            except Exception as e:
                schema_parts.append(f"Schema extraction failed: {e}")
        else:
            schema_parts.append("No schema available - single parameter tool")
        
        return "\n".join(schema_parts)


# ============================================================================
# STAGE 5: EXECUTION ENGINE
# ============================================================================

class FiveStageExecutor:
    """
    Executes the complete 5-stage process
    """
    
    def __init__(self, agent):
        self.agent = agent
        self.tool_specialist = ToolSpecialist(agent)
    
    def execute_with_tool_outputs(self, high_level_plan: List[Dict], 
                                  all_tools: List, context: str):
        """
        Execute plan with tool specialist for each step
        
        This is where the magic happens - each tool gets its own specialist!
        """
        
        print("\n" + "="*80)
        print("STAGE 4 & 5: TOOL SPECIALIST PLANNING + EXECUTION")
        print("="*80)
        
        tool_outputs = {}
        
        for step_dict in high_level_plan:
            step_num = step_dict['step']
            tool_name = step_dict['tool']
            step_goal = step_dict['goal']
            
            print(f"\n{'─'*80}")
            print(f"STEP {step_num}: {tool_name}")
            print(f"Goal: {step_goal}")
            print(f"{'─'*80}")
            
            # Find tool
            tool = next((t for t in all_tools if t.name == tool_name), None)
            
            if not tool:
                result = f"[ERROR] Tool not found: {tool_name}"
                print(result)
                yield result
                tool_outputs[f"step_{step_num}"] = result
                continue
            
            # ================================================================
            # STAGE 4: TOOL SPECIALIST PLANS INPUTS
            # ================================================================
            
            try:
                detailed_plan = self.tool_specialist.plan_tool_execution(
                    tool=tool,
                    step_goal=step_goal,
                    previous_outputs=tool_outputs,
                    context=context
                )
                
                tool_input = detailed_plan['input']
                reasoning = detailed_plan['reasoning']
                
                yield f"\n[Specialist Planning]\n  Reasoning: {reasoning}\n  Input: {str(tool_input)[:200]}...\n"
                
            except Exception as e:
                result = f"[ERROR] Tool specialist planning failed: {e}"
                print(result)
                yield result
                tool_outputs[f"step_{step_num}"] = result
                continue
            
            # ================================================================
            # Resolve placeholders
            # ================================================================
            
            def resolve_placeholders(value, step_num, tool_outputs):
                if not isinstance(value, str):
                    return value
                
                if "{prev}" in value:
                    prev_output = str(tool_outputs.get(f"step_{step_num-1}", ""))
                    value = value.replace("{prev}", prev_output)
                
                for i in range(1, step_num):
                    placeholder = f"{{step_{i}}}"
                    if placeholder in value:
                        step_output = str(tool_outputs.get(f"step_{i}", ""))
                        value = value.replace(placeholder, step_output)
                
                return value
            
            # Handle dict vs string input
            if isinstance(tool_input, dict):
                resolved_input = {}
                for key, value in tool_input.items():
                    resolved_input[key] = resolve_placeholders(value, step_num, tool_outputs)
            else:
                resolved_input = resolve_placeholders(str(tool_input), step_num, tool_outputs)
            
            # ================================================================
            # STAGE 5: EXECUTE TOOL
            # ================================================================
            
            print(f"\n[Executing] {tool_name}")
            yield f"\n[Executing] {tool_name}\n"
            
            try:
                # Get callable
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
                
                # Execute
                if isinstance(resolved_input, dict):
                    exec_result = func(**resolved_input)
                else:
                    exec_result = func(resolved_input)
                
                # Handle streaming
                collected = []
                result = ""
                
                if hasattr(exec_result, '__iter__') and not isinstance(exec_result, (str, bytes, dict)):
                    for chunk in exec_result:
                        chunk_str = str(chunk)
                        yield chunk_str
                        collected.append(chunk_str)
                    result = "".join(collected)
                else:
                    result = str(exec_result)
                    yield result
                
                # Store
                tool_outputs[f"step_{step_num}"] = result
                tool_outputs[tool_name] = result
                
                # Save to memory
                self.agent.mem.add_session_memory(
                    self.agent.sess.id,
                    f"Step {step_num} - {tool_name}\nGoal: {step_goal}\n\nResult:\n{result}",
                    "ToolStep",
                    {
                        "topic": "tool_step",
                        "step": step_num,
                        "tool": tool_name,
                        "goal": step_goal
                    }
                )
                
                print(f"\n✓ Step {step_num} complete")
                yield f"\n✓ Step {step_num} complete\n"
            
            except Exception as e:
                result = f"[ERROR] Tool execution failed: {str(e)}\n{traceback.format_exc()}"
                print(result)
                yield result
                tool_outputs[f"step_{step_num}"] = result
        
        # Return final result
        final_result = tool_outputs.get(f"step_{len(high_level_plan)}", "")
        return final_result


# ============================================================================
# MAIN 5-STAGE CONTROLLER
# ============================================================================

class FiveStageToolChain:
    """
    Complete 5-stage expert toolchain
    """
    
    def __init__(self, agent, tools):
        self.agent = agent
        self.tools = tools
        
        # Initialize registries
        self.tool_registry = ToolDomainRegistry()
        
        # Initialize stages
        self.triage = DomainTriageAgent(agent, self.tool_registry)
        self.tool_filter = DomainToolFilter(agent, self.tool_registry)
        self.high_level_planner = HighLevelPlanner(agent)
        self.executor = FiveStageExecutor(agent)
        
        print(f"[5-Stage Toolchain] Initialized")
    
    def register_tool_domain(self, tool_name: str, domains: Set[Domain], priority: int = 1):
        """Register tool with domains"""
        self.tool_registry.register(tool_name, domains, priority)
    
    def execute_tool_chain(self, query: str):
        """
        Execute complete 5-stage process
        """
        
        print("\n" + "="*80)
        print("5-STAGE EXPERT TOOLCHAIN")
        print("="*80)
        
        try:
            # ================================================================
            # STAGE 1: DOMAIN TRIAGE
            # ================================================================
            
            triage_gen = self.triage.select_domains(query)
            analysis = None
            
            for result in triage_gen:
                if isinstance(result, dict):
                    analysis = result
                else:
                    yield result
            
            if not analysis:
                raise ValueError("Domain triage failed")
            
            all_domains = set(analysis['primary_domains'] + analysis['secondary_domains'])
            
            # ================================================================
            # STAGE 2: DOMAIN TOOL FILTERING
            # ================================================================
            
            tool_descriptions = self.tool_filter.get_tools_for_domains(all_domains, self.tools)
            
            yield f"\n✓ Stage 2 complete: {len(tool_descriptions)} tools available\n"
            
            # ================================================================
            # STAGE 3: HIGH-LEVEL PLANNING
            # ================================================================
            
            plan_gen = self.high_level_planner.create_high_level_plan(
                query, all_domains, tool_descriptions
            )
            
            high_level_plan = None
            for result in plan_gen:
                if isinstance(result, list):
                    high_level_plan = result
                else:
                    yield result
            
            if not high_level_plan:
                raise ValueError("High-level planning failed")
            
            yield f"\n✓ Stage 3 complete: {len(high_level_plan)} steps planned\n"
            
            # ================================================================
            # STAGES 4 & 5: TOOL SPECIALIST + EXECUTION
            # ================================================================
            
            for chunk in self.executor.execute_with_tool_outputs(
                high_level_plan, self.tools, query
            ):
                yield chunk
            
            print("\n" + "="*80)
            print("5-STAGE EXECUTION COMPLETE")
            print("="*80 + "\n")
        
        except Exception as e:
            error_msg = f"\n[5-Stage Error] {str(e)}\n{traceback.format_exc()}\n"
            print(error_msg)
            yield error_msg