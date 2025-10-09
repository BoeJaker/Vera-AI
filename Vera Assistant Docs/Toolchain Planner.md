Tool Orchestrator

---

# ToolChainPlanner for Vera Agent

**ToolChainPlanner** is a flexible, multi-modal tool orchestration framework designed to integrate with the `Vera` multi-agent system. It enables the Vera agent to plan and execute sequences of tool calls, leveraging large language models (LLMs) for planning, error recovery, and speculative branching.

---

## Features

### 1. Flexible Tool Planning

- Generate full multi-step tool execution plans from the Vera agent’s deep LLM.
    
- Supports incremental, batch, and speculative planning modes.
    
- Allows referencing outputs from previous steps using `{prev}` or `{step_n}` placeholders.
    

### 2. Speculative Branch Execution

- Run multiple candidate plans concurrently using Python threads.
    
- Choose the best plan based on LLM evaluation (`first_success` strategy by default).
    
- Supports other speculative strategies (e.g., most completed steps, LLM-scored branches).
    

### 3. Robust Tool Execution

- Automatically resolves step dependencies and placeholders.
    
- Supports tools implemented as:
    
    - Callable objects
        
    - Objects with `.run()` or `.func()` methods
        
- Collects streaming outputs from iterable tools.
    
- Injects short-term memory context into LLM-style tools.
    

### 4. Recovery & Retry

- Detects errors during tool execution.
    
- Automatically generates recovery plans via LLM.
    
- Supports configurable per-step retries with exponential backoff.
    

### 5. Memory Integration

- Writes execution results to Vera’s session memory.
    
- Supports persistent storage and logging for each step.
    
- Compatible with hybrid memory systems (Neo4j + Chroma + conversation buffer).
    

### 6. Streaming & Hooks

- Yields incremental status updates and results.
    
- Supports hooks for:
    
    - `on_plan`: called when a plan is generated.
        
    - `on_step_start`: called when a step starts.
        
    - `on_step_end`: called when a step finishes.
        
    - `on_error`: called on execution or planning errors.
        

### 7. Goal Verification

- Uses Vera’s deep LLM to evaluate whether the plan outputs satisfy the original query.
    
- Supports both intermediate and final goal checks.
    

---

## Installation

1. Install dependencies (example):
    

```bash
pip install ollama chromadb neo4j playwright
```

2. Ensure your `Vera` agent is configured with:
    

- Deep LLM (`deep_llm`)
    
- Buffer memory (`buffer_memory`)
    
- Hybrid memory (`mem`) for session storage
    
- Tools to execute
    

3. Include `ToolChainPlanner.py` in your project and instantiate:
    

```python
from toolchain_planner import ToolChainPlanner

planner = ToolChainPlanner(agent=vera_instance, tools=vera_instance.tools)
```

---

## Usage

### Basic Execution

```python
query = "Extract the latest sales data and summarize trends."
results = planner.run_sync(query, mode="batch")
print(results)
```

### Incremental Mode

```python
for update in planner.execute(query, mode="incremental"):
    print(update)
```

### Speculative Branch Execution

```python
for update in planner.execute(query, mode="speculative"):
    print(update)
```

- Speculative mode generates multiple alternative plans and runs them concurrently.
    
- First successful plan (as evaluated by the deep LLM) is selected by default.
    

---

## Configuration Options

- `max_steps`: Maximum steps per plan (default: 60)
    
- `default_retries`: Default retry count per tool (default: 1)
    
- `default_step_timeout`: Optional timeout per tool
    
- `speculative_workers`: Number of concurrent speculative branches
    
- `stop_on_error`: Stop execution if a step fails
    
- `allow_replan_on_error`: Automatically generate recovery plan on failure
    
- `allow_partial`: Return partial results if full plan fails
    

---

## Integration with Vera

The planner fully integrates with Vera’s agent class:

```python
planner = ToolChainPlanner(agent=vera_instance, tools=vera_instance.tools)
```

- Access session memory via `self.agent.mem`.
    
- Access short-term memory via `self.agent.buffer_memory`.
    
- Use `deep_llm.invoke(prompt)` for planning and evaluation.
    
- Works with Vera’s tool set including Playwright tools.
    

---

## Hooks Example

```python
def on_plan(plans):
    print(f"Generated {len(plans)} plans.")

def on_step_start(step):
    print(f"Starting {step.tool}")

def on_step_end(step, result):
    print(f"Completed {step.tool}: {result.raw}")

planner.on_plan = on_plan
planner.on_step_start = on_step_start
planner.on_step_end = on_step_end
```

---

## Developer Notes

- **Memory Safety**: Speculative branches may write to memory immediately; consider dry-run isolation if branches must not mutate shared memory.
    
- **Concurrency**: Python threads cannot be forcefully cancelled; speculative workers may continue to run in the background until completion.
    
- **Timeouts**: Per-tool timeouts are not enforced by default; wrap blocking tools if needed.
    

---

## License

MIT License. Free to use and extend for research or production.

---

I can also draft a **visual diagram** showing the workflow with speculative branching and memory integration for easier onboarding if you want.

Do you want me to add that diagram?