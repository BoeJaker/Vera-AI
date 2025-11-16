# Toolchain Engine (TCE)

## Overview

The **Toolchain Engine** is Vera's execution orchestrator that breaks down complex queries into structured, executable plans and manages their execution using available tools. It sits at the heart of Vera's execution layer, transforming high-level user requests into concrete multi-step workflows.

## Purpose

The ToolChain Engine (TCE) enables Vera to:
- **Decompose complex tasks** into manageable, sequential steps
- **Orchestrate tool execution** with automatic error handling
- **Validate results** against original goals
- **Replan dynamically** when failures occur
- **Integrate external systems** via the Babelfish communication toolkit

## Architecture Role

```
User Query → CEO Orchestrator → ToolChain Engine → Tool Execution → Result Validation
                                        ↓
                                   Babelfish (protocol translation)
                                        ↓
                                External Services/APIs
```

The TCE receives high-level queries from the Central Executive Orchestrator (CEO), generates structured execution plans using the deep LLM, and executes those plans using both internal and external tools.

## Key Files

| File | Purpose |
|------|---------|
| `toolchain.py` | Core toolchain orchestration and planning logic |
| `tools.py` | Tool definitions and registry |
| `enhanced_toolchain_planner.py` | Advanced planning strategies (Batch, Step, Hybrid) |
| `n8n_toolchain.py` | Integration with n8n workflow automation platform |
| `toolchain_planner_integration.py` | Integration layer for external toolchain systems |

## Technologies

- **Python** - Core implementation language
- **JSON** - Execution plan format
- **LLM-based planning** - Uses Vera's deep LLM for intelligent plan generation
- **Tool registry system** - Dynamic tool discovery and invocation

## Planning Strategies

### Batch Planning
Generate the entire plan upfront before execution:
```json
[
  { "tool": "WebSearch", "input": "latest AI trends 2024" },
  { "tool": "WebSearch", "input": "generative AI applications" },
  { "tool": "SummarizerLLM", "input": "{step_1}\n{step_2}" }
]
```

### Step Planning
Generate each next step based on previous results (adaptive):
```json
[
  { "tool": "WebSearch", "input": "authenticate with OAuth2" }
]
// After step 1 completes, determine next step dynamically
```

### Hybrid Planning
Mix of upfront and adaptive planning for optimal balance

## Execution Strategies

- **Sequential** - Execute steps one at a time (safe, traceable)
- **Parallel** - Execute independent steps concurrently (faster)
- **Speculative** - Run multiple possible next steps, then prune based on validation (advanced)

## Example Usage

```python
from toolchain import ToolChainPlanner

# Initialize planner with agent and tools
planner = ToolChainPlanner(agent, agent.tools)

# Execute a multi-tool workflow
query = "Retrieve latest weather for New York and generate a report"
final_output = planner.execute_tool_chain(query)
print("Result:", final_output)

# Generate execution history report
history = planner.report_history()
print(history)
```

## Tools Directory

The `Tools/` subdirectory contains specialized tool implementations:

### Core Tools
- **`memory.py`** - Memory introspection tools enabling LLM self-awareness
- **`file_explorer.py`** - File system navigation and manipulation
- **`securityandML.py`** - Security analysis and machine learning tools

### Specialized Toolkits

#### crawlers/
Web scraping and corpus analysis tools:
- `corpus_crawler.py` - Comprehensive website/corpus mapping
- `total_crawl.py` - Deep web crawling with context extraction

#### tamagotchi/
Interactive monitoring agents with personality:
- `tamagochi.py` - Main agent implementation
- `tamagochi_gen.py` - Agent generation and customization

#### babelfish/
Protocol-agnostic communication toolkit:
- `babelfish.py` - Universal protocol translator enabling communication via HTTP, WebSockets, MQTT, SSH, IRC, and more

See [Babelfish Documentation](../Vera%20Assistant%20Docs/Babelfish.md) for details.

#### web security/
Dynamic security analysis tools for vulnerability detection and penetration testing

## Tool Integration

Tools can be:
- **Internal** - Built-in Python functions
- **External** - API calls, command-line tools
- **MCP Servers** - Model Context Protocol integrations
- **Custom** - User-defined tools following the callable interface

### Adding Custom Tools

```python
def load_tools(self):
    tools = super().load_tools()

    tools.append(
        Tool(
            name="CustomTool",
            func=lambda input: process(input),
            description="Description of what this tool does"
        )
    )

    return tools
```

## Error Handling

The TCE includes automatic error recovery:
1. Tool execution failure detected
2. Error logged with context
3. Automatic replanning triggered
4. Retry with modified approach
5. Escalation to CEO if persistent failure

## Plan Format

Plans are represented as JSON arrays of tool invocations:
```json
[
  { "tool": "SearchAPI", "input": "query text" },
  { "tool": "SummarizerLLM", "input": "{step_1}" }
]
```

Placeholders like `{step_1}` or `{prev}` are replaced with actual outputs during execution.

## Validation

After execution, the LLM validates whether the final output meets the original query's goal. If not satisfied, automatic replanning occurs.

## Memory Integration

All toolchain executions are saved to memory:
- Execution plans stored for replay
- Intermediate results cached
- Success/failure patterns learned
- Historical context used for future planning

## Configuration

Tool behavior can be configured via:
- `Configuration/vera_models.json` - Model selection for planning
- `Configuration/last_tool_plan.json` - Last executed plan (for replay)

## Related Documentation

- [ToolChain Planner Documentation](../Vera%20Assistant%20Docs/Toolchain%20Planner.md)
- [Central Executive Orchestrator](../Vera%20Assistant%20Docs/Central%20Executive%20Orchestrator.md)
- [Babelfish Communication Toolkit](../Vera%20Assistant%20Docs/Babelfish.md)

## Security Warning

> **WARNING**: Vera has unrestricted access to Bash and Python execution by default. Be very careful with queries. There is nothing stopping it from running `rm -rf /`. Disable these tools in production environments or when untrusted users have access.

## Contributing

To extend the ToolChain Engine:
1. Add new tools to the `Tools/` directory
2. Register them in `tools.py`
3. Update tool descriptions for LLM planning
4. Add unit tests for reliability
5. Document usage patterns

---

**Related Components:**
- [Agents](../Agents/) - Specialized LLM instances that use tools
- [Memory](../Memory/) - Persistent knowledge storage
- [Background Cognition](../BackgroundCognition/) - Autonomous task generation
