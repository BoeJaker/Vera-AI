# Toolchain Directory

## Table of Contents
- [Overview](#overview)
- [Architecture](#architecture)
- [Core Files](#core-files)
- [Planning Strategies](#planning-strategies)
- [Execution Strategies](#execution-strategies)
- [Tool Integration](#tool-integration)
- [Usage Examples](#usage-examples)
- [Configuration](#configuration)
- [Advanced Features](#advanced-features)
- [Performance](#performance)
- [Troubleshooting](#troubleshooting)

---

## Overview

The Toolchain directory implements Vera's intelligent tool orchestration system - a sophisticated engine that breaks down complex user queries into executable sequences of tool calls, manages their execution, validates results, and handles errors with automatic replanning.

**Purpose:** Multi-step tool orchestration and execution
**Size:** 812KB (34 modules across subdirectories)
**Status:** ✅ Production
**Key Technology:** LLM-driven planning + Dynamic tool discovery + Error recovery

### Key Capabilities

- **Intelligent Planning**: LLM-generated execution plans tailored to each query
- **Multiple Planning Strategies**: Batch, Step-by-step, and Hybrid approaches
- **Dynamic Execution**: Sequential, Parallel, and Speculative execution modes
- **Error Recovery**: Automatic replanning and retry on failures
- **Result Validation**: LLM-based verification that goals were met
- **Tool Discovery**: Dynamic tool loading from multiple sources
- **MCP Integration**: Model Context Protocol support for external tools
- **n8n Integration**: Workflow automation engine integration

---

## Architecture

### Tool Chain Flow

```
User Query
    ↓
┌─────────────────────────────────────┐
│  ToolChainPlanner                   │
│  - Analyze query                    │
│  - Select planning strategy         │
│  - Generate execution plan (JSON)   │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│  Plan Validation                    │
│  - Validate tool availability       │
│  - Check dependency resolution      │
│  - Verify input schemas             │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│  Execution Engine                   │
│  For each step:                     │
│    1. Resolve placeholders          │
│    2. Execute tool                  │
│    3. Capture output                │
│    4. Handle errors                 │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│  Result Validation                  │
│  - Check if goal achieved           │
│  - Trigger replan if needed         │
│  - Save to memory                   │
└─────────────────────────────────────┘
    ↓
Final Result
```

### Component Interaction

```
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│   Enhanced   │      │     Tool     │      │     n8n      │
│  Toolchain   │◄────►│   Loader     │◄────►│  Workflow    │
│   Planner    │      │              │      │   Engine     │
└──────────────┘      └──────────────┘      └──────────────┘
       ↓                     ↓                      ↓
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│   Dynamic    │      │     MCP      │      │    Tools     │
│    Tools     │      │   Manager    │      │  Directory   │
│  Discovery   │      │              │      │   (35+)      │
└──────────────┘      └──────────────┘      └──────────────┘
```

---

## Core Files

### `toolchain.py` - Base ToolChain Planner

**Purpose:** Core tool chain planning and execution engine

**Size:** ~500 lines
**Class:** `ToolChainPlanner`

#### Key Methods

```python
class ToolChainPlanner:
    def __init__(self, agent, tools):
        """
        Initialize tool chain planner

        Args:
            agent: Vera agent instance with LLM and memory
            tools: List of available tool objects
        """
        self.agent = agent
        self.deep_llm = agent.deep_llm
        self.tools = agent.tools
        self.history = agent.buffer_memory.load_memory_variables({})

    def plan_tool_chain(self, query: str, history_context: str = "") -> List[Dict]:
        """
        Generate execution plan from LLM

        Args:
            query: User query to plan for
            history_context: Previous attempts and outputs

        Returns:
            List of tool call dictionaries: [{"tool": "name", "input": "value"}, ...]

        Yields:
            Streaming plan generation tokens

        Example:
            planner = ToolChainPlanner(agent, tools)
            for chunk in planner.plan_tool_chain("Search and summarize AI news"):
                print(chunk, end="")
        """

    def execute_tool_chain(self, query: str, plan=None) -> str:
        """
        Execute tool chain with error handling and validation

        Args:
            query: Original user query
            plan: Optional pre-generated plan (if None, will generate)

        Returns:
            Final execution result

        Yields:
            Streaming execution updates

        Features:
            - Placeholder resolution ({prev}, {step_1}, {step_2}, etc.)
            - Error detection and recovery
            - Output validation
            - Memory storage

        Example:
            result_generator = planner.execute_tool_chain(
                "Scan network and analyze results"
            )
            for update in result_generator:
                if isinstance(update, dict):  # Final result
                    print(f"Completed: {update}")
                else:  # Progress update
                    print(update)
        """
```

#### Placeholder System

The toolchain supports dynamic output referencing:

```python
# Plan example with placeholders
[
    {"tool": "WebSearch", "input": "latest AI trends 2025"},
    {"tool": "WebSearch", "input": "generative AI applications"},
    {"tool": "Summarizer", "input": "{step_1}\n\n{step_2}"},  # References steps 1 and 2
    {"tool": "Editor", "input": "{prev}"}  # References previous step (step 3)
]
```

**Supported Placeholders:**
- `{prev}` - Output of the previous step
- `{step_N}` - Output of step N (e.g., `{step_1}`, `{step_2}`)
- `{all}` - Concatenation of all previous outputs

#### Error Handling

```python
# Automatic error recovery flow
try:
    result = execute_tool(tool_name, tool_input)
    tool_outputs[f"step_{step_num}"] = result
except Exception as e:
    errors_detected = True
    # Log error
    error_msg = f"Step {step_num} failed: {e}"

    # Trigger replanning with error context
    history_context += f"\n{error_msg}"
    new_plan = self.plan_tool_chain(query, history_context)

    # Retry with new plan
    return self.execute_tool_chain(query, new_plan)
```

---

### `enhanced_toolchain_planner.py` - Advanced Planning

**Purpose:** Enhanced planner with multiple planning strategies

**Key Features:**
- **Batch Planning**: Generate complete plan upfront
- **Step Planning**: Generate next step based on results
- **Hybrid Planning**: Mix of batch and adaptive planning
- **Cost Estimation**: Estimate tokens and execution time
- **Plan Optimization**: Identify parallelizable steps

#### Core Class

```python
class EnhancedToolChainPlanner(ToolChainPlanner):
    """
    Enhanced tool chain planner with advanced strategies

    Strategies:
        - BATCH: Plan all steps upfront (fast, predictable)
        - STEP: Generate each step adaptively (flexible, exploratory)
        - HYBRID: Batch plan with adaptive refinement (balanced)
        - SPECULATIVE: Generate multiple plans, execute best (advanced)
    """

    def __init__(self, agent, tools, strategy="hybrid"):
        """
        Args:
            agent: Vera agent instance
            tools: Available tools
            strategy: Planning strategy ("batch", "step", "hybrid", "speculative")
        """
        super().__init__(agent, tools)
        self.strategy = strategy
        self.cost_estimator = CostEstimator()

    def plan_with_strategy(self, query: str) -> Dict:
        """
        Plan execution using selected strategy

        Returns:
            {
                "strategy": "hybrid",
                "plan": [...],
                "estimated_cost": {"tokens": 1500, "time_seconds": 45},
                "parallelizable_steps": [[2, 3], [5, 6]],
                "confidence": 0.85
            }
        """
```

#### Planning Strategy Examples

**Batch Planning:**
```python
# All steps planned upfront
planner = EnhancedToolChainPlanner(agent, tools, strategy="batch")
result = planner.plan_with_strategy("Research AI safety and write report")

# Generated plan:
{
    "strategy": "batch",
    "plan": [
        {"tool": "WebSearch", "input": "AI safety research 2025"},
        {"tool": "WebSearch", "input": "AI alignment techniques"},
        {"tool": "WebSearch", "input": "AI risk mitigation strategies"},
        {"tool": "Summarizer", "input": "{step_1}\n{step_2}\n{step_3}"},
        {"tool": "ReportWriter", "input": "{step_4}"}
    ],
    "estimated_cost": {"tokens": 2500, "time_seconds": 120},
    "parallelizable_steps": [[0, 1, 2]]  # First 3 searches can run in parallel
}
```

**Step-by-Step Planning:**
```python
# Each step planned after previous completes
planner = EnhancedToolChainPlanner(agent, tools, strategy="step")

# Step 1: Plan first action
plan_step_1 = planner.plan_next_step(query, previous_results={})
# Returns: {"tool": "WebSearch", "input": "AI safety research 2025"}

# Execute step 1
result_1 = execute_tool("WebSearch", "AI safety research 2025")

# Step 2: Plan based on result_1
plan_step_2 = planner.plan_next_step(query, previous_results={"step_1": result_1})
# Returns: {"tool": "Summarizer", "input": "{step_1}"}
```

**Hybrid Planning:**
```python
# Batch plan with adaptive refinement
planner = EnhancedToolChainPlanner(agent, tools, strategy="hybrid")

# Initial batch plan
initial_plan = planner.create_batch_plan(query)
# [step1, step2, step3, step4, step5]

# Execute with refinement checkpoints
for i, step in enumerate(initial_plan):
    result = execute_tool(step["tool"], step["input"])

    # Refine remaining steps based on results so far
    if i in planner.refinement_points:
        remaining_steps = planner.refine_plan(
            query,
            completed_steps=initial_plan[:i+1],
            results=results_so_far
        )
        initial_plan = initial_plan[:i+1] + remaining_steps
```

---

### `n8n_toolchain.py` - n8n Workflow Integration

**Purpose:** Integration with n8n workflow automation platform

**Key Features:**
- Execute n8n workflows as tools
- Pass data between Vera and n8n
- Trigger webhooks
- Poll for workflow results

#### Usage

```python
from Toolchain.n8n_toolchain import N8NToolchain

# Initialize
n8n = N8NToolchain(
    api_url="https://n8n.example.com",
    api_key=os.getenv("N8N_API_KEY")
)

# Execute workflow
result = n8n.execute_workflow(
    workflow_id="123",
    input_data={
        "email": "user@example.com",
        "subject": "Report Generated",
        "body": "Your report is ready"
    }
)

# Trigger webhook
n8n.trigger_webhook(
    webhook_url="https://n8n.example.com/webhook/abc123",
    payload={"event": "new_scan_complete", "scan_id": "scan_456"}
)
```

#### n8n Tool Definition

```python
class N8NWorkflowTool:
    """
    Wrapper to use n8n workflows as Vera tools
    """
    name = "N8N_EmailReport"
    description = "Send email report via n8n workflow"

    def __init__(self, workflow_id, n8n_client):
        self.workflow_id = workflow_id
        self.n8n = n8n_client

    def run(self, input_str: str) -> str:
        """Execute n8n workflow with input"""
        result = self.n8n.execute_workflow(
            workflow_id=self.workflow_id,
            input_data=json.loads(input_str)
        )
        return json.dumps(result)
```

---

### `mcp_manager.py` - Model Context Protocol Manager

**Purpose:** Manage MCP (Model Context Protocol) tool integration

**Key Features:**
- Discover MCP-compatible tools
- Load tool schemas
- Execute MCP tools
- Handle authentication

#### MCP Tool Integration

```python
from Toolchain.mcp_manager import MCPManager

# Initialize
mcp = MCPManager()

# Discover available MCP tools
tools = mcp.discover_tools()
# Returns: [
#     {"name": "calculator", "protocol": "mcp", "endpoint": "http://..."},
#     {"name": "translator", "protocol": "mcp", "endpoint": "http://..."}
# ]

# Load tool schema
schema = mcp.get_tool_schema("calculator")
# Returns: {
#     "name": "calculator",
#     "description": "Perform mathematical calculations",
#     "input_schema": {"type": "object", "properties": {...}},
#     "output_schema": {"type": "object", "properties": {...}}
# }

# Execute MCP tool
result = mcp.execute_tool(
    tool_name="calculator",
    input_data={"expression": "2 + 2 * 3"}
)
# Returns: {"result": 8}
```

---

### `dynamic_tools.py` - Dynamic Tool Discovery

**Purpose:** Automatically discover and load tools at runtime

**Key Features:**
- Scan tool directories
- Load tools from plugins
- Hot-reload tools without restart
- Validate tool interfaces

#### Dynamic Loading

```python
from Toolchain.dynamic_tools import DynamicToolLoader

# Initialize
loader = DynamicToolLoader()

# Load all tools from directory
tools = loader.load_tools_from_directory("Toolchain/Tools")
# Returns: [Tool1, Tool2, Tool3, ...]

# Load specific tool
tool = loader.load_tool("Toolchain/Tools/web_security.py", "WebSecurityTool")

# Reload tools (hot-reload)
loader.reload_all_tools()

# Validate tool interface
is_valid = loader.validate_tool(tool)
# Checks for: name, description, run() method
```

#### Tool Discovery Pattern

```python
class ToolDiscovery:
    """Automatic tool discovery system"""

    @staticmethod
    def discover_tools(base_path: str) -> List[Tool]:
        """
        Scan directory for valid tools

        A valid tool must have:
            - name: str attribute
            - description: str attribute
            - run(input: str) -> str method
        """
        tools = []

        for file in Path(base_path).rglob("*.py"):
            module = load_module_from_file(file)

            for item in dir(module):
                obj = getattr(module, item)

                if (hasattr(obj, 'name') and
                    hasattr(obj, 'description') and
                    callable(getattr(obj, 'run', None))):

                    tools.append(obj())

        return tools
```

---

### `tools.py` - Tool Loader and Manager

**Purpose:** Central tool management and loading

**Key Components:**

```python
class ToolManager:
    """
    Central tool management
    """

    def __init__(self):
        self.tools = {}
        self.tool_registry = {}

    def register_tool(self, tool):
        """Register a tool for use"""
        self.tools[tool.name] = tool
        self.tool_registry[tool.name] = {
            "description": tool.description,
            "category": getattr(tool, 'category', 'general'),
            "schema": getattr(tool, 'schema', None)
        }

    def get_tool(self, name: str):
        """Retrieve tool by name"""
        return self.tools.get(name)

    def list_tools(self, category: str = None) -> List:
        """List all tools, optionally filtered by category"""
        if category:
            return [
                name for name, info in self.tool_registry.items()
                if info['category'] == category
            ]
        return list(self.tools.keys())

    def execute_tool(self, name: str, input_data: str) -> str:
        """Execute tool by name"""
        tool = self.get_tool(name)
        if not tool:
            raise ValueError(f"Tool not found: {name}")
        return tool.run(input_data)
```

---

### `schemas.py` - Tool Input/Output Schemas

**Purpose:** Define and validate tool schemas

**Schema Definition:**

```python
from pydantic import BaseModel, Field
from typing import Optional, List, Dict

class ToolInput(BaseModel):
    """Base tool input schema"""
    query: str = Field(..., description="Input query or data")
    options: Optional[Dict] = Field(default={}, description="Tool-specific options")

class ToolOutput(BaseModel):
    """Base tool output schema"""
    result: str = Field(..., description="Tool execution result")
    status: str = Field(..., description="Execution status: success/error")
    metadata: Optional[Dict] = Field(default={}, description="Additional metadata")
    error: Optional[str] = Field(default=None, description="Error message if failed")

# Example: Web Search Tool Schema
class WebSearchInput(ToolInput):
    query: str = Field(..., description="Search query")
    num_results: int = Field(default=10, description="Number of results")
    date_range: Optional[str] = Field(default=None, description="Date range filter")

class WebSearchOutput(ToolOutput):
    results: List[Dict] = Field(..., description="Search results")
    total_found: int = Field(..., description="Total results found")
```

**Schema Validation:**

```python
from Toolchain.schemas import validate_input, validate_output

# Validate tool input
try:
    validated_input = validate_input(
        tool_name="WebSearch",
        input_data={"query": "AI news", "num_results": 5}
    )
except ValidationError as e:
    print(f"Invalid input: {e}")

# Validate tool output
try:
    validated_output = validate_output(
        tool_name="WebSearch",
        output_data={"result": "[...]", "status": "success"}
    )
except ValidationError as e:
    print(f"Invalid output: {e}")
```

---

## Planning Strategies

### Batch Planning

**When to Use:**
- Well-defined workflows
- Predictable outcomes
- Fast execution priority
- Low complexity

**Advantages:**
- Fastest planning time
- Clear execution path
- Easy to visualize

**Disadvantages:**
- Less flexible
- Can't adapt to unexpected results

**Example:**
```python
query = "Download report, extract data, generate summary"

# Batch plan generated upfront
plan = [
    {"tool": "FileDownloader", "input": "https://example.com/report.pdf"},
    {"tool": "PDFExtractor", "input": "{step_1}"},
    {"tool": "Summarizer", "input": "{step_2}"}
]
```

---

### Step-by-Step Planning

**When to Use:**
- Exploratory tasks
- Uncertain outcomes
- Research workflows
- High complexity

**Advantages:**
- Maximally adaptive
- Handles unknowns well
- Can course-correct

**Disadvantages:**
- Slower (multiple LLM calls)
- Higher token cost

**Example:**
```python
query = "Research authentication vulnerabilities and find solutions"

# Step 1: Generated initially
step_1 = {"tool": "WebSearch", "input": "OAuth2 vulnerabilities 2025"}
result_1 = execute(step_1)

# Step 2: Generated based on result_1
step_2 = {"tool": "WebSearch", "input": "JWT security best practices"}
result_2 = execute(step_2)

# Step 3: Generated based on results_1 and result_2
step_3 = {"tool": "Summarizer", "input": "{step_1}\n{step_2}"}
```

---

### Hybrid Planning

**When to Use:**
- Most real-world scenarios
- Balance between speed and flexibility
- Medium complexity

**Advantages:**
- Balanced approach
- Good performance
- Adaptive when needed

**Disadvantages:**
- More complex implementation

**Example:**
```python
query = "Scan network, analyze vulnerabilities, generate report"

# Initial batch plan
plan = [
    {"tool": "NmapScan", "input": "192.168.1.0/24"},
    {"tool": "VulnerabilityAnalyzer", "input": "{step_1}"},
    # Refinement point here
    {"tool": "ReportGenerator", "input": "{step_2}"}
]

# After step 2, refine remaining steps
if critical_vulnerabilities_found:
    plan.append({"tool": "MetasploitVerify", "input": "{step_2}"})
    plan.append({"tool": "ReportGenerator", "input": "{step_2}\n{step_3}"})
```

---

### Speculative Planning

**When to Use:**
- Critical tasks requiring high success rate
- Resources available for parallel execution
- Complex problem-solving

**Advantages:**
- Highest success rate
- Multiple solution paths
- Best result selection

**Disadvantages:**
- High resource cost
- Complex orchestration

**Example:**
```python
query = "Find best solution for database performance issue"

# Generate multiple plans
plan_a = [
    {"tool": "DatabaseAnalyzer", "input": "check_indexes"},
    {"tool": "OptimizationSuggester", "input": "{step_1}"}
]

plan_b = [
    {"tool": "QueryProfiler", "input": "slow_queries"},
    {"tool": "QueryOptimizer", "input": "{step_1}"}
]

plan_c = [
    {"tool": "SchemaAnalyzer", "input": "table_structure"},
    {"tool": "SchemaSuggester", "input": "{step_1}"}
]

# Execute all plans in parallel
results = await asyncio.gather(
    execute_plan(plan_a),
    execute_plan(plan_b),
    execute_plan(plan_c)
)

# Select best result
best_result = llm.evaluate_best_solution(results)
```

---

## Execution Strategies

### Sequential Execution

**Default and safest execution mode**

```python
def execute_sequential(plan):
    """Execute steps one at a time"""
    results = {}
    for i, step in enumerate(plan):
        tool_input = resolve_placeholders(step['input'], results)
        result = execute_tool(step['tool'], tool_input)
        results[f'step_{i+1}'] = result
    return results
```

**Characteristics:**
- Predictable order
- Easy debugging
- Lower resource usage
- Clear error isolation

---

### Parallel Execution

**Execute independent steps concurrently**

```python
async def execute_parallel(plan):
    """Execute independent steps in parallel"""
    # Identify parallelizable steps
    parallel_groups = identify_independent_steps(plan)

    results = {}
    for group in parallel_groups:
        # Execute group in parallel
        tasks = [
            execute_tool_async(step['tool'], step['input'])
            for step in group
        ]
        group_results = await asyncio.gather(*tasks)

        # Store results
        for step, result in zip(group, group_results):
            results[step['id']] = result

    return results

def identify_independent_steps(plan):
    """
    Identify which steps can run in parallel

    Steps are independent if:
    - They don't reference each other's outputs
    - They don't conflict on resources
    """
    dependency_graph = build_dependency_graph(plan)
    return find_parallel_groups(dependency_graph)
```

**Example:**
```python
# These steps can run in parallel
plan = [
    {"id": "1", "tool": "WebSearch", "input": "AI trends"},
    {"id": "2", "tool": "WebSearch", "input": "ML advances"},
    {"id": "3", "tool": "WebSearch", "input": "LLM news"},
    {"id": "4", "tool": "Summarizer", "input": "{1}\n{2}\n{3}"}  # Depends on 1,2,3
]

# Parallel groups: [[1,2,3], [4]]
```

---

## Tool Integration

### Built-in Tools

See `Tools/README.md` for comprehensive documentation of 35+ built-in tools.

**Categories:**
- Security Testing (web_security, dynamic_web_security, ai_in_the_middle)
- Code Execution (code_executor, python_parser, bash_parser)
- Web Crawling (corpus_crawler, spider)
- Translation (babelfish)
- File Management (file_explorer)

### Plugin Tools

See `../plugins/README.md` for 38+ plugin modules.

### Custom Tool Creation

```python
class CustomTool:
    """
    Template for creating custom tools
    """
    # Required attributes
    name = "CustomTool"
    description = "What this tool does"
    category = "custom"  # Optional: for organization

    # Optional: Input/output schemas
    input_schema = {
        "type": "object",
        "properties": {
            "param1": {"type": "string"},
            "param2": {"type": "integer"}
        },
        "required": ["param1"]
    }

    def __init__(self, config: dict = None):
        """Initialize tool with optional config"""
        self.config = config or {}

    def run(self, input_str: str) -> str:
        """
        Execute tool logic

        Args:
            input_str: Input data (often JSON string)

        Returns:
            Result string (often JSON)
        """
        try:
            # Parse input
            input_data = json.loads(input_str) if input_str.startswith('{') else input_str

            # Execute logic
            result = self._execute(input_data)

            # Return result
            return json.dumps({"status": "success", "result": result})

        except Exception as e:
            return json.dumps({"status": "error", "error": str(e)})

    def _execute(self, input_data):
        """Internal execution logic"""
        # Implement your tool logic here
        pass

# Register tool
from Toolchain.tools import ToolManager
manager = ToolManager()
manager.register_tool(CustomTool())
```

---

## Usage Examples

### Basic Tool Chain Execution

```python
from vera import Vera
from Toolchain.toolchain import ToolChainPlanner

# Initialize
vera = Vera()
planner = ToolChainPlanner(vera, vera.tools)

# Execute tool chain
query = "Search for Python tutorials and summarize the top 3"
result = planner.execute_tool_chain(query)

print(result)
# Output: "Summary of top 3 Python tutorials: ..."
```

### Custom Plan Execution

```python
# Pre-define a plan
custom_plan = [
    {"tool": "WebSearch", "input": "Python tutorials"},
    {"tool": "ContentExtractor", "input": "{prev}"},
    {"tool": "Summarizer", "input": "{prev}"}
]

# Execute custom plan
result = planner.execute_tool_chain(
    query="Python tutorial search",
    plan=custom_plan
)
```

### Streaming Execution Updates

```python
# Stream execution progress
for update in planner.execute_tool_chain("Complex multi-step task"):
    if isinstance(update, str):
        print(f"Progress: {update}")
    elif isinstance(update, dict):
        print(f"Step complete: {update}")
    elif isinstance(update, list):
        print(f"Plan generated: {update}")
```

### Error Handling

```python
try:
    result = planner.execute_tool_chain("Risky operation")
except ToolExecutionError as e:
    print(f"Tool failed: {e.tool_name}")
    print(f"Error: {e.error_message}")
    print(f"Attempted plan: {e.plan}")
except PlanningError as e:
    print(f"Planning failed: {e}")
```

---

## Configuration

### Toolchain Configuration

```python
# Configuration/toolchain_config.json
{
    "default_strategy": "hybrid",
    "max_retries": 3,
    "timeout_seconds": 300,
    "enable_parallel": true,
    "max_parallel_workers": 4,
    "enable_caching": true,
    "cache_ttl_seconds": 3600,
    "enable_validation": true,
    "save_plans_to_memory": true,
    "verbose_logging": false
}
```

### Model Selection

```python
# Use different LLMs for planning
planner = ToolChainPlanner(vera, vera.tools)
planner.deep_llm = vera.reasoning_llm  # Use reasoning LLM for complex plans

# Or use faster LLM for simple plans
planner.deep_llm = vera.intermediate_llm
```

---

## Advanced Features

### Plan Caching

```python
class CachedToolChainPlanner(ToolChainPlanner):
    """Cache generated plans for similar queries"""

    def __init__(self, agent, tools):
        super().__init__(agent, tools)
        self.plan_cache = {}

    def plan_tool_chain(self, query: str, **kwargs):
        # Check cache
        cache_key = self.get_cache_key(query)
        if cache_key in self.plan_cache:
            return self.plan_cache[cache_key]

        # Generate plan
        plan = super().plan_tool_chain(query, **kwargs)

        # Cache plan
        self.plan_cache[cache_key] = plan
        return plan
```

### Plan Versioning

```python
# Save plan with version
plan_id = hashlib.sha256(
    f"{time.time()}_{json.dumps(plan)}".encode()
).hexdigest()

vera.memory.add_session_memory(
    session_id,
    json.dumps(plan),
    memory_type="Plan",
    metadata={"plan_id": plan_id, "query": query}
)
```

### Cost Estimation

```python
class CostEstimator:
    """Estimate execution cost"""

    def estimate_plan_cost(self, plan):
        total_tokens = 0
        total_time = 0

        for step in plan:
            tool_cost = self.get_tool_cost(step['tool'])
            total_tokens += tool_cost['tokens']
            total_time += tool_cost['time_seconds']

        return {
            "estimated_tokens": total_tokens,
            "estimated_time_seconds": total_time,
            "estimated_cost_usd": total_tokens * 0.000002  # Example pricing
        }
```

---

## Performance

### Optimization Techniques

**1. Parallel Execution**
```python
# Enable parallel execution
planner.enable_parallel = True
planner.max_parallel_workers = 4
```

**2. Plan Caching**
```python
# Cache similar plans
planner.enable_caching = True
planner.cache_ttl = 3600  # 1 hour
```

**3. Early Validation**
```python
# Validate plan before execution
def validate_plan_early(plan, available_tools):
    for step in plan:
        if step['tool'] not in available_tools:
            raise PlanningError(f"Tool not available: {step['tool']}")
```

**4. Batch Tool Calls**
```python
# Batch similar tool calls
batch_results = execute_tools_batch([
    ("WebSearch", "query1"),
    ("WebSearch", "query2"),
    ("WebSearch", "query3")
])
```

### Performance Benchmarks

| Operation | Sequential | Parallel | Improvement |
|-----------|-----------|----------|-------------|
| 5 web searches | 25s | 6s | 4.2x faster |
| 3 summarizations | 45s | 16s | 2.8x faster |
| Complex plan (10 steps) | 120s | 35s | 3.4x faster |

---

## Troubleshooting

### Common Issues

**Plan Generation Fails**
```python
# Issue: LLM returns invalid JSON
# Solution: Add retry with format enforcement
for attempt in range(3):
    try:
        plan = json.loads(plan_json)
        break
    except json.JSONDecodeError:
        plan_json = clean_json_response(plan_json)
```

**Tool Not Found**
```python
# Issue: Tool name in plan doesn't match registered tool
# Solution: Implement fuzzy matching
def find_tool_fuzzy(tool_name, available_tools):
    from difflib import get_close_matches
    matches = get_close_matches(tool_name, available_tools, n=1, cutoff=0.6)
    return matches[0] if matches else None
```

**Timeout Errors**
```python
# Issue: Tool execution exceeds timeout
# Solution: Implement timeout handling
import signal

def timeout_handler(signum, frame):
    raise TimeoutError("Tool execution timeout")

signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(300)  # 5 minute timeout
try:
    result = execute_tool(tool_name, input_data)
finally:
    signal.alarm(0)  # Cancel alarm
```

**Memory Errors with Large Plans**
```python
# Issue: Large plan exceeds memory
# Solution: Stream execution, don't store all results
def execute_streaming(plan):
    for step in plan:
        result = execute_tool(step['tool'], step['input'])
        yield result
        # Don't store, just yield
```

---

## Related Documentation

- [Tools Directory](Tools/README.md) - Built-in tools documentation
- [Plugins Directory](../plugins/README.md) - Plugin tools
- [Enhanced Planner Examples](enhanced_toolchain_planner_examples.py)
- [n8n Integration Guide](n8n_examples.py)
- [Architecture Overview](../ARCHITECTURE.md)

---

**Last Updated:** January 2025
**Maintainer:** Vera-AI Development Team
**Version:** 1.0.0
