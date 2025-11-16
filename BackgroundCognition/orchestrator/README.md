# Vera-AI Unified Orchestration Backend

A comprehensive orchestration system for managing compute tasks with intelligent routing, resource management, and worker pool orchestration.

## Features

### Core Capabilities

- **Intelligent Task Routing**: Automatically route tasks to the best available worker based on capabilities, load, and cost
- **Resource Management**: Track and manage LLM API quotas, compute resources, and rate limits
- **Worker Pool Management**: Support for Docker, Ollama, remote workers, and cloud LLM APIs
- **Parallel Execution**: Automatically analyze task dependencies and execute in parallel where possible
- **Auto-scaling**: Dynamic worker pool scaling based on load
- **Rate Limiting**: Per-API rate limiting with token bucket algorithm
- **Cost Tracking**: Monitor API costs and enforce budget limits
- **Priority Queuing**: Task prioritization (Critical, High, Normal, Low, Background)
- **Health Monitoring**: Continuous health checks on all workers
- **Real-time Status**: WebSocket API for live status updates

### Supported Worker Types

1. **Docker Workers**: Execute code in isolated containers
2. **Ollama Workers**: Local LLM inference via Ollama
3. **LLM API Workers**: Cloud-based LLM APIs (OpenAI, Anthropic, Gemini)
4. **Remote Workers**: Distributed compute nodes via HTTP
5. **Custom Workers**: Extensible base class for custom implementations

### Task Types

- `TOOL_CALL`: Execute Vera tools
- `LLM_REQUEST`: General LLM inference
- `OLLAMA_REQUEST`: Specific Ollama requests
- `CODE_EXECUTION`: Execute code (Python, Bash)
- `BACKGROUND_COGNITION`: Background thinking tasks
- `API_REQUEST`: Generic API calls
- `DOCKER_TASK`: Docker-specific tasks
- `REMOTE_COMPUTE`: Remote computation
- `PARALLEL_BATCH`: Batch of parallel tasks
- `CUSTOM`: User-defined task types

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  Unified Orchestrator                        │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Task Router  │  │   Resource   │  │   Worker     │     │
│  │              │  │   Manager    │  │   Registry   │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │           Smart Scheduler (Priority Queue)            │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
    ┌───▼────┐      ┌────▼─────┐     ┌────▼────┐
    │ Docker │      │  Ollama  │     │   LLM   │
    │ Workers│      │  Worker  │     │   APIs  │
    └────────┘      └──────────┘     └─────────┘
        │
    ┌───▼────┐
    │ Remote │
    │ Workers│
    └────────┘
```

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Ensure Docker is running (for Docker workers)
docker ps

# Ensure Ollama is running (for Ollama workers)
curl http://localhost:11434/api/tags
```

## Quick Start

### Basic Usage

```python
from BackgroundCognition.orchestrator import (
    UnifiedOrchestrator,
    OrchestratorConfig,
    Task,
    TaskType,
    TaskPriority,
)

# Initialize orchestrator
config = OrchestratorConfig(
    max_concurrent_tasks=10,
    docker_pool_size=3,
    ollama_url="http://localhost:11434",
)

orchestrator = UnifiedOrchestrator(config)
await orchestrator.start()

# Submit a simple LLM request
result = await orchestrator.execute_llm_request(
    prompt="What is the capital of France?",
    prefer_ollama=True,
)

print(result.data)  # Output: "Paris"

# Stop orchestrator
await orchestrator.stop()
```

### Task Submission

```python
# Create a task
task = Task(
    type=TaskType.CODE_EXECUTION,
    priority=TaskPriority.HIGH,
    payload={
        'code': 'print("Hello from Docker!")',
        'language': 'python',
    },
)

# Submit and wait for result
result = await orchestrator.submit_task(task, wait=True)

if result.success:
    print(f"Output: {result.data}")
else:
    print(f"Error: {result.error}")
```

### Parallel Execution

```python
# Create multiple tasks
tasks = [
    Task(
        type=TaskType.LLM_REQUEST,
        payload={'prompt': f'Explain {topic}'}
    )
    for topic in ['AI', 'ML', 'NLP', 'CV']
]

# Execute in parallel
results = await orchestrator.submit_batch(
    tasks,
    execute_parallel=True,
    wait=True,
)

for result in results:
    print(result.data)
```

### Register Cloud LLM APIs

```python
# Register OpenAI
await orchestrator.register_llm_api(
    api_type='openai',
    api_key='sk-...',
    rate_limit_per_minute=60,
    cost_per_1k_tokens=0.002,
    quota=APIQuota(
        requests_per_day=10000,
        cost_limit_per_day=10.0,
    ),
)

# Register Anthropic
await orchestrator.register_llm_api(
    api_type='anthropic',
    api_key='sk-ant-...',
    rate_limit_per_minute=50,
    cost_per_1k_tokens=0.008,
)
```

### Register Remote Workers

```python
# Add remote compute node
await orchestrator.register_remote_worker(
    remote_url='http://192.168.1.100:8000',
    auth_token='bearer-token-here',
)
```

### Tool Call Execution

```python
# Execute a tool through orchestrator
result = await orchestrator.execute_tool_call(
    tool_name='web_search',
    tool_input={'query': 'Python asyncio tutorial'},
    priority=TaskPriority.NORMAL,
)
```

## API Integration

### FastAPI Integration

```python
from fastapi import FastAPI
from BackgroundCognition.orchestrator.api_integration import register_routes

app = FastAPI()

# Register orchestrator routes
register_routes(app, prefix="/api/v2/orchestrator")

# Start server
# uvicorn main:app --host 0.0.0.0 --port 8000
```

### API Endpoints

```
GET  /api/v2/orchestrator/health            - Health check
GET  /api/v2/orchestrator/status            - Get status
POST /api/v2/orchestrator/tasks/submit      - Submit task (non-blocking)
POST /api/v2/orchestrator/tasks/execute     - Execute task (blocking)
POST /api/v2/orchestrator/llm/request       - LLM request
POST /api/v2/orchestrator/tools/execute     - Tool execution
GET  /api/v2/orchestrator/tasks/history     - Task history
POST /api/v2/orchestrator/workers/llm-api/register - Register LLM API
POST /api/v2/orchestrator/workers/remote/register  - Register remote worker
GET  /api/v2/orchestrator/workers/list      - List workers
GET  /api/v2/orchestrator/resources/stats   - Resource stats
WS   /api/v2/orchestrator/ws/status         - WebSocket status updates
```

### Example API Requests

```bash
# Submit LLM request
curl -X POST http://localhost:8000/api/v2/orchestrator/llm/request \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Explain quantum computing",
    "prefer_ollama": true,
    "temperature": 0.7
  }'

# Register OpenAI API
curl -X POST http://localhost:8000/api/v2/orchestrator/workers/llm-api/register \
  -H "Content-Type: application/json" \
  -d '{
    "api_type": "openai",
    "api_key": "sk-...",
    "rate_limit_per_minute": 60,
    "cost_per_1k_tokens": 0.002,
    "quota_cost_limit_per_day": 10.0
  }'

# Get status
curl http://localhost:8000/api/v2/orchestrator/status
```

## Advanced Features

### Task Dependencies

```python
# Create tasks with dependencies
task1 = Task(
    id="task-1",
    type=TaskType.LLM_REQUEST,
    payload={'prompt': 'Generate a story'},
)

task2 = Task(
    id="task-2",
    type=TaskType.LLM_REQUEST,
    payload={'prompt': 'Summarize: {task-1}'},
    depends_on=['task-1'],  # Wait for task-1
)

# Execute - task2 will wait for task1
results = await orchestrator.submit_batch([task1, task2], wait=True)
```

### Custom Workers

```python
from BackgroundCognition.orchestrator.workers import BaseWorker, WorkerCapability

class MyCustomWorker(BaseWorker):
    def __init__(self):
        super().__init__(
            worker_id="custom-1",
            capabilities=[WorkerCapability.CUSTOM],
        )

    async def start(self) -> bool:
        self.status = WorkerStatus.IDLE
        return True

    async def stop(self) -> bool:
        self.status = WorkerStatus.OFFLINE
        return True

    async def execute_task(self, task: Task) -> TaskResult:
        # Your custom logic here
        return TaskResult(
            success=True,
            data="Custom result",
        )

    async def health_check(self) -> bool:
        return True

# Register custom worker
worker = MyCustomWorker()
await worker.start()
await orchestrator.worker_registry.register(worker)
```

### Event Hooks

```python
# Set completion hook
def on_complete(task, result):
    print(f"Task {task.id} completed: {result.success}")

orchestrator.on_task_complete = on_complete

# Set failure hook
def on_failure(task, error):
    print(f"Task {task.id} failed: {error}")

orchestrator.on_task_failed = on_failure
```

### Monitoring and Metrics

```python
# Get current status
status = orchestrator.get_status()
print(f"Active tasks: {status['metrics']['active_tasks']}")
print(f"Completed: {status['metrics']['tasks_completed']}")
print(f"Failed: {status['metrics']['tasks_failed']}")

# Get resource stats
stats = orchestrator.resource_manager.get_resource_stats()
print(f"LLM API usage: {stats['llm_api_usage']}")

# Get worker statistics
worker_stats = orchestrator.worker_registry.get_statistics()
print(f"Total workers: {worker_stats['total_workers']}")
print(f"By status: {worker_stats['workers_by_status']}")
```

## Configuration

### OrchestratorConfig Options

```python
config = OrchestratorConfig(
    max_concurrent_tasks=10,        # Max parallel tasks
    enable_auto_scaling=True,       # Auto-scale worker pools
    docker_pool_size=3,             # Initial Docker workers
    docker_image="vera-worker:latest",
    ollama_url="http://localhost:11434",
    health_check_interval=30,       # Health check frequency (seconds)
    task_timeout_seconds=300,       # Default task timeout
)
```

### Worker Configuration

```python
from BackgroundCognition.orchestrator.workers import WorkerConfig

worker_config = WorkerConfig(
    max_concurrent_tasks=2,         # Tasks per worker
    rate_limit_per_minute=60,       # Rate limit
    timeout_seconds=300,            # Task timeout
    auto_restart=True,              # Auto-restart on failure
    health_check_interval_seconds=30,
)
```

### API Quotas

```python
from BackgroundCognition.orchestrator.resources import APIQuota

quota = APIQuota(
    requests_per_minute=60,
    requests_per_hour=3600,
    requests_per_day=86400,
    tokens_per_minute=100000,
    tokens_per_day=5000000,
    cost_limit_per_day=10.0,
)
```

## Best Practices

1. **Always use priorities**: Set appropriate task priorities to ensure critical tasks execute first
2. **Monitor quotas**: Keep track of API usage to avoid hitting limits
3. **Use dependencies**: Define task dependencies for complex workflows
4. **Enable auto-scaling**: Let the orchestrator scale worker pools automatically
5. **Set timeouts**: Always set reasonable task timeouts
6. **Handle failures**: Implement retry logic and error handling
7. **Use health checks**: Monitor worker health regularly
8. **Resource cleanup**: Always stop the orchestrator on shutdown

## Troubleshooting

### Docker workers not starting

```bash
# Check Docker is running
docker ps

# Check image exists
docker images | grep vera-worker

# Build image if needed
cd worker && docker build -t vera-worker:latest .
```

### Ollama not responding

```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama if needed
ollama serve
```

### Tasks stuck in queue

```python
# Check worker availability
status = orchestrator.get_status()
print(status['workers'])

# Check for worker errors
worker_stats = orchestrator.worker_registry.get_statistics()
print(worker_stats['workers_by_status'])
```

## Contributing

To extend the orchestrator:

1. Create custom worker types by extending `BaseWorker`
2. Add new task types to `TaskType` enum
3. Implement custom routing logic in `TaskRouter`
4. Add new API endpoints in `api_integration.py`

## License

Part of the Vera-AI project.
