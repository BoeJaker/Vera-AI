# Proactive Background Cognition (PBC)

## Overview

**Proactive Background Cognition** is Vera's autonomous thinking engine that runs during idle moments to generate actionable insights, monitor long-term goals, and prepare for future tasks without explicit user prompts. It transforms Vera from a reactive system into a proactive intelligence.

## Purpose

PBC enables Vera to:
- **Think autonomously** during downtime
- **Monitor long-term goals** and detect approaching deadlines
- **Generate actionable tasks** based on context
- **Detect inconsistencies** or knowledge gaps
- **Prepare for complex operations** in advance
- **Improve continuously** through self-reflection

## Architecture Role

```
Idle System → PBC Tick Triggered → Context Gathering
    ↓
Deep LLM Reasoning → Actionable Task Generation
    ↓
Fast LLM Validation → Executability Check
    ↓
Worker Pool Execution → Tool Invocation
    ↓
Focus Board Update → Progress Tracking
    ↓
Memory Storage → Learning from Results
```

PBC operates as a background daemon, periodically checking system state and context to generate valuable work autonomously.

## Key Components

### Proactive Focus Manager
**File:** `proactive_background_focus.py`

The core autonomous cognition engine that:
- Monitors project context and pending goals continuously
- Generates proactive thoughts (reminders, hypotheses, plans)
- Validates proposed actions using fast LLM
- Executes validated actions through toolchain
- Maintains focus board tracking progress

**Features:**
- Non-blocking scheduling with configurable intervals
- Context-aware task generation from multiple sources
- LLM-driven reasoning for next-step identification
- Action validation before execution
- Rate limiting and resource awareness

### Worker Pool
**File:** `worker_pool.py`

Manages distributed task execution:
- Local thread pool workers
- Remote HTTP workers
- Proxmox cluster integration
- Priority-based task scheduling
- Failure handling with retry policies

### Task Management
**File:** `tasks.py`

Task scheduling and priority management:
- Task queue with priority levels
- Deadline tracking
- Dependency resolution
- Status monitoring

### Registry
**File:** `registry.py`

Task registry and configuration:
- Available task definitions
- Worker capabilities
- Resource requirements
- Execution policies

### Cluster Support
**File:** `cluster.py`

Remote worker cluster integration:
- Proxmox node management
- Label-based task routing
- Health monitoring
- Load balancing

### UI Components
**File:** `pbt_ui.py`

Web interface for monitoring background tasks:
- Real-time task status
- Focus board visualization
- Performance metrics
- Manual task triggering

## Technologies

- **APScheduler** - Periodic task scheduling with cron-like functionality
- **Priority Queues** - Task prioritization and ordering
- **Thread Pools** - Local concurrent execution
- **AsyncIO** - Non-blocking I/O operations
- **HTTP Workers** - Remote task execution
- **Proxmox API** - Cluster node management

## Configuration

### Basic Setup
```python
from BackgroundCognition.proactive_background_focus import ProactiveBackgroundCognition

pbc = ProactiveBackgroundCognition(
    tick_interval=60,  # Check every 60 seconds
    context_providers=[
        ConversationProvider(),
        FocusBoardProvider(),
        MemoryProvider()
    ],
    max_parallel_thoughts=3,
    action_validation_threshold=0.8
)

# Start autonomous thinking
pbc.start()
```

### Advanced Configuration
```python
pbc = ProactiveBackgroundCognition(
    tick_interval=30,
    max_parallel_thoughts=5,
    validation_threshold=0.85,
    worker_pool=CustomWorkerPool(
        local_workers=4,
        remote_workers=["http://worker1:8000", "http://worker2:8000"],
        proxmox_nodes=["node1", "node2"]
    ),
    rate_limit={"thoughts_per_hour": 20, "tools_per_thought": 5},
    enable_learning=True,
    focus_board_path="./focus_boards/main.json"
)
```

## Context Providers

Context providers feed information to the PBC for decision-making:

### Conversation Provider
```python
class ConversationProvider:
    def get_context(self):
        return {
            "recent_topics": ["authentication", "database design"],
            "user_questions": ["How to implement OAuth2?"],
            "pending_responses": []
        }
```

### Focus Board Provider
```python
class FocusBoardProvider:
    def get_context(self):
        return {
            "active_tasks": [...],
            "blockers": [...],
            "ideas": [...],
            "next_steps": [...]
        }
```

### Memory Provider
```python
class MemoryProvider:
    def get_context(self):
        return {
            "active_projects": [...],
            "long_term_goals": [...],
            "knowledge_gaps": [...],
            "recent_insights": [...]
        }
```

## Thought Generation Process

1. **Context Gathering:**
   ```python
   context = pbc.gather_context()
   # Combines inputs from all context providers
   ```

2. **LLM Reasoning:**
   ```python
   prompt = f"""
   Given the current context:
   {context}

   What are the most valuable next actions to take?
   Consider:
   - Approaching deadlines
   - Blocked tasks
   - Knowledge gaps
   - Opportunities for improvement
   """
   thoughts = deep_llm.invoke(prompt)
   ```

3. **Action Validation:**
   ```python
   validation_prompt = f"""
   Proposed action: {thought}
   Available tools: {tools}

   Is this action executable? Rate 0-1.
   """
   score = fast_llm.invoke(validation_prompt)
   if score > threshold:
       execute(thought)
   ```

4. **Execution:**
   ```python
   result = pbc.execute_thought(thought)
   focus_board.update(thought, result)
   memory.store_result(thought, result)
   ```

## Focus Board Structure

The focus board tracks PBC-generated work:

```json
{
  "progress": [
    {
      "task": "Implement user authentication",
      "status": "in_progress",
      "completion": 0.65,
      "blockers": [],
      "next_steps": ["Write unit tests", "Add error handling"]
    }
  ],
  "ideas": [
    {
      "idea": "Add caching layer to reduce database load",
      "priority": "medium",
      "feasibility": 0.8,
      "impact": 0.9
    }
  ],
  "actions": [
    {
      "action": "Research Redis caching patterns",
      "scheduled": "2024-01-16T10:00:00Z",
      "status": "pending"
    }
  ],
  "issues": [
    {
      "issue": "Database connection pool exhaustion under load",
      "severity": "high",
      "proposed_solution": "Increase pool size and add connection timeout"
    }
  ]
}
```

## Worker Pool Architecture

### Local Workers
```python
local_pool = ThreadPoolExecutor(max_workers=4)
future = local_pool.submit(execute_task, task)
```

### Remote HTTP Workers
```python
response = requests.post(
    "http://worker1:8000/execute",
    json={"task": task, "priority": "high"}
)
```

### Proxmox Cluster Workers
```python
cluster.assign_task(
    task=task,
    labels=["gpu", "high-memory"],
    node_preference="node1"
)
```

## Execution Strategies

### Sequential
Execute thoughts one at a time:
```python
for thought in thoughts:
    result = execute(thought)
    if result.failed():
        handle_error(thought, result)
```

### Parallel
Execute multiple thoughts concurrently:
```python
futures = [executor.submit(execute, t) for t in thoughts]
results = [f.result() for f in futures]
```

### Priority-Based
Execute highest-priority thoughts first:
```python
thoughts.sort(key=lambda t: t.priority, reverse=True)
for thought in thoughts:
    if resources_available():
        execute(thought)
    else:
        queue(thought)
```

## Retry Policies

Automatic retry with exponential backoff:
```python
@retry(
    max_attempts=3,
    backoff=exponential(base=2, max_value=60),
    retry_on=[NetworkError, TimeoutError]
)
def execute_remote_task(task, worker_url):
    return requests.post(f"{worker_url}/execute", json=task)
```

## Rate Limiting

Prevent resource exhaustion:
```python
rate_limiter = RateLimiter(
    thoughts_per_hour=20,
    tools_per_thought=5,
    max_concurrent_executions=3
)

if rate_limiter.can_execute():
    execute(thought)
else:
    schedule_for_later(thought)
```

## Monitoring and Observability

### Real-Time Dashboard
```bash
python3 BackgroundCognition/pbt_ui.py
# Opens on localhost:8502
```

Dashboard shows:
- Active thoughts being processed
- Execution queue status
- Worker pool utilization
- Focus board state
- Recent completions and failures
- Resource consumption

### Metrics
```python
metrics = pbc.get_metrics()
# {
#   "thoughts_generated": 156,
#   "thoughts_executed": 142,
#   "success_rate": 0.91,
#   "avg_execution_time": 12.5,
#   "worker_utilization": 0.68,
#   "queue_depth": 3
# }
```

## Use Cases

### Deadline Monitoring
```python
# PBC detects approaching deadline
thought = "Project X deadline in 2 days - review completion status"
actions = [
    "Check task completion percentage",
    "Identify remaining blockers",
    "Generate priority task list",
    "Send reminder to user"
]
execute_thought(thought, actions)
```

### Knowledge Gap Detection
```python
# PBC notices repeated failures on similar tasks
thought = "Multiple OAuth2 integration attempts failed - knowledge gap detected"
actions = [
    "Search memory for OAuth2 documentation",
    "Fetch latest OAuth2 best practices",
    "Create learning roadmap",
    "Schedule knowledge acquisition tasks"
]
execute_thought(thought, actions)
```

### Proactive Optimization
```python
# PBC detects performance degradation
thought = "Vector search latency increasing - investigate optimization"
actions = [
    "Analyze query performance metrics",
    "Identify slow queries",
    "Research indexing strategies",
    "Generate optimization proposal",
    "Add to focus board for review"
]
execute_thought(thought, actions)
```

### Consistency Checking
```python
# PBC validates knowledge graph integrity
thought = "Weekly knowledge graph consistency check"
actions = [
    "Run graph audit tools",
    "Detect orphaned nodes",
    "Find relationship inconsistencies",
    "Generate fix proposals",
    "Apply automated corrections"
]
execute_thought(thought, actions)
```

## Integration with Other Components

### CEO Orchestrator
```python
# PBC requests resources from CEO
pbc.request_resource(
    resource_type="deep_llm",
    duration=300,
    priority="medium",
    reason="Strategic planning task"
)
```

### Memory System
```python
# PBC enriches memory during idle time
pbc.schedule_task(
    task="enrich_memory_relationships",
    target_nodes=recently_added_nodes,
    enrichment_depth=2
)
```

### Toolchain Engine
```python
# PBC generates and executes tool chains
toolchain_plan = pbc.generate_toolchain(
    goal="Update project documentation",
    available_tools=tools
)
pbc.execute_toolchain(toolchain_plan)
```

## Configuration File Example

**`pbc_config.json`:**
```json
{
  "tick_interval_seconds": 60,
  "max_parallel_thoughts": 3,
  "validation_threshold": 0.8,
  "rate_limits": {
    "thoughts_per_hour": 20,
    "tools_per_thought": 5,
    "max_concurrent_executions": 3
  },
  "context_providers": [
    "conversation",
    "focus_board",
    "memory",
    "system_metrics"
  ],
  "worker_pool": {
    "local_workers": 4,
    "remote_workers": [
      "http://worker1:8000",
      "http://worker2:8000"
    ],
    "proxmox_enabled": true,
    "proxmox_nodes": ["pve-node1", "pve-node2"]
  },
  "focus_board_path": "./focus_boards/main.json",
  "enable_learning": true,
  "log_level": "INFO"
}
```

## Best Practices

### Resource Management
- Set appropriate rate limits to prevent CPU/memory exhaustion
- Use priority queuing for critical vs nice-to-have tasks
- Monitor worker pool utilization

### Thought Quality
- Validate all generated thoughts before execution
- Use fast LLM for validation to save resources
- Maintain thought generation quality metrics

### Error Handling
- Implement retry policies with backoff
- Log all failures for analysis
- Escalate persistent failures to CEO

### Focus Board Hygiene
- Archive completed tasks regularly
- Prune stale ideas periodically
- Prioritize actionable items

## Troubleshooting

### PBC Not Generating Thoughts
```bash
# Check scheduler status
python3 -c "from BackgroundCognition.proactive_background_focus import PBC; print(PBC.scheduler.get_jobs())"

# Verify context providers
python3 -c "from BackgroundCognition.proactive_background_focus import PBC; print(PBC.gather_context())"
```

### High Resource Usage
```bash
# Reduce tick frequency
# Edit pbc_config.json: "tick_interval_seconds": 120

# Lower parallel thought limit
# Edit pbc_config.json: "max_parallel_thoughts": 2

# Enable aggressive rate limiting
# Edit pbc_config.json: "thoughts_per_hour": 10
```

### Worker Pool Issues
```bash
# Check worker health
curl http://worker1:8000/health

# Restart worker pool
python3 -c "from BackgroundCognition.worker_pool import WorkerPool; WorkerPool.restart()"
```

## Related Documentation

- [Central Executive Orchestrator](../Vera%20Assistant%20Docs/Central%20Executive%20Orchestrator.md)
- [Proactive Background Cognition Deep Dive](../Vera%20Assistant%20Docs/Central%20Executive%20Orchestrator.md#2-proactive-background-cognition)
- [Worker Pool Architecture](worker_pool.py)
- [Focus Board Management](tasks.py)

## Contributing

To extend PBC:
1. Add new context providers in `context_providers/`
2. Implement custom thought generators
3. Create specialized worker types
4. Add monitoring metrics
5. Extend focus board schema

---

**Related Components:**
- [Agents](../Agents/) - Specialized cognitive units
- [Memory](../Memory/) - Knowledge storage and retrieval
- [Toolchain](../Toolchain/) - Tool execution engine
- [Worker Pool](../worker/) - Distributed task execution
