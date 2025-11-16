# Background Cognition Directory Documentation

## Overview

The `BackgroundCognition/` directory implements Vera's Proactive Background Cognition (PBC) system - an autonomous background thinking engine that continuously monitors context, generates actionable tasks, and executes them through a unified orchestration backend.

**Total Size:** 322KB (27 Python modules)
**Status:** Production-ready
**Core Components:** Orchestrator, Worker Pool, Focus Manager, Distributed Clustering

## Directory Structure

```
BackgroundCognition/
├── orchestrator/                    # Unified Orchestration Backend
│   ├── core.py                     # Central orchestrator with intelligent routing
│   ├── api_integration.py          # FastAPI integration layer
│   ├── router.py                   # Task routing logic
│   ├── resources.py                # Resource management & quotas
│   ├── tasks.py                    # Task models & definitions
│   ├── README.md                   # Comprehensive API documentation
│   └── workers/                    # Worker implementations
│       ├── __init__.py
│       ├── base.py                # BaseWorker abstract class
│       ├── docker_worker.py       # Docker container execution
│       ├── ollama_worker.py       # Local LLM via Ollama
│       ├── llm_api_worker.py      # Cloud LLM APIs (OpenAI, Anthropic, Gemini)
│       ├── remote_worker.py       # Remote compute nodes
│       └── registry.py            # Worker registry management
│
├── proactive_background_focus.py   # Focus management system
├── pbt_v2.py                       # Proactive Background Thinking v2
├── pbt_ui.py                       # PBT UI interface
├── cluster.py                      # Distributed computation clustering
├── worker_pool.py                  # Worker pool management
├── registry.py                     # Worker registry (global)
├── tasks.py                        # Task definitions (global)
└── ... (additional PBT modules)
```

## System Architecture

### Orchestration Flow

```
User/System Request
       ↓
┌──────────────────────────────────────┐
│   Orchestrator Core (core.py)       │
│   - Receives task                   │
│   - Determines task type            │
│   - Selects optimal worker          │
└──────────────────────────────────────┘
       ↓
┌──────────────────────────────────────┐
│   Router (router.py)                │
│   - Task type matching              │
│   - Worker capability check         │
│   - Load balancing                  │
└──────────────────────────────────────┘
       ↓
┌──────────────────────────────────────┐
│   Resource Manager (resources.py)   │
│   - Check quotas                    │
│   - Allocate resources              │
│   - Track utilization               │
└──────────────────────────────────────┘
       ↓
┌──────────────────────────────────────┐
│   Worker Execution                  │
│   ├─ Docker Worker                  │
│   ├─ Ollama Worker                  │
│   ├─ LLM API Worker                 │
│   └─ Remote Worker                  │
└──────────────────────────────────────┘
       ↓
Result Returned & Logged
```

---

## Core Components

### 1. Orchestrator Core (`orchestrator/core.py`)

The central orchestrator that intelligently routes tasks to appropriate workers.

#### Key Features

- **Intelligent Task Routing**: Automatically selects the best worker type for each task
- **Multi-Worker Support**: Manages Docker, Ollama, cloud API, and remote workers
- **Resource Management**: Tracks and enforces resource quotas
- **Fault Tolerance**: Handles worker failures gracefully
- **Task Queueing**: Manages task queue when workers are busy

#### Core Class

```python
class Orchestrator:
    def __init__(self, config: Dict[str, Any]):
        """Initialize orchestrator with configuration"""
        self.workers = {}  # Registry of available workers
        self.task_queue = asyncio.Queue()
        self.resource_manager = ResourceManager(config.get('quotas', {}))
        self.router = TaskRouter(config.get('routing', {}))

    async def submit_task(self, task: Task) -> TaskResult:
        """Submit task for execution"""
        # Route task to appropriate worker
        worker = await self.router.select_worker(task, self.workers)

        # Check resource availability
        if not self.resource_manager.can_allocate(worker, task):
            await self.task_queue.put(task)
            raise ResourceUnavailable("Worker busy, task queued")

        # Execute task
        result = await worker.execute_task(task)

        return result

    def register_worker(self, worker: BaseWorker):
        """Register a new worker"""
        self.workers[worker.worker_id] = worker
        self.router.update_worker_capabilities(worker)

    async def get_worker_status(self) -> Dict[str, Any]:
        """Get status of all workers"""
        return {
            worker_id: worker.get_status()
            for worker_id, worker in self.workers.items()
        }
```

#### Task Types Supported

```python
class TaskType(Enum):
    TOOL_CALL = "tool_call"                      # Execute Vera tools
    LLM_REQUEST = "llm_request"                  # General LLM inference
    OLLAMA_REQUEST = "ollama_request"            # Specific Ollama requests
    CODE_EXECUTION = "code_execution"            # Execute Python/Bash code
    BACKGROUND_COGNITION = "background_cognition"# Background thinking
    API_REQUEST = "api_request"                  # Generic API calls
    DOCKER_TASK = "docker_task"                  # Docker-specific tasks
    REMOTE_COMPUTE = "remote_compute"            # Remote computation
    PARALLEL_BATCH = "parallel_batch"            # Batch parallel execution
```

---

### 2. Task Router (`orchestrator/router.py`)

Implements intelligent task routing logic based on worker capabilities, load, and task requirements.

#### Routing Strategies

```python
class TaskRouter:
    def __init__(self, config: Dict[str, Any]):
        self.strategy = config.get('strategy', 'least_loaded')
        self.worker_capabilities = {}

    async def select_worker(
        self,
        task: Task,
        workers: Dict[str, BaseWorker]
    ) -> BaseWorker:
        """Select optimal worker for task"""

        # Filter workers by capability
        capable_workers = [
            w for w in workers.values()
            if self.can_handle_task(w, task)
        ]

        if not capable_workers:
            raise NoWorkerAvailable(f"No worker for {task.task_type}")

        # Apply routing strategy
        if self.strategy == 'least_loaded':
            return min(capable_workers, key=lambda w: w.current_load)
        elif self.strategy == 'random':
            return random.choice(capable_workers)
        elif self.strategy == 'round_robin':
            return self.next_round_robin(capable_workers)
        else:
            return capable_workers[0]

    def can_handle_task(self, worker: BaseWorker, task: Task) -> bool:
        """Check if worker can handle task type"""
        return task.task_type in self.worker_capabilities.get(
            worker.worker_id,
            []
        )
```

#### Routing Strategies

1. **least_loaded**: Choose worker with lowest current load
2. **random**: Random selection among capable workers
3. **round_robin**: Distribute evenly across workers
4. **priority**: Route to highest-priority worker first
5. **affinity**: Prefer workers that have handled similar tasks

---

### 3. Resource Manager (`orchestrator/resources.py`)

Manages resource allocation and enforces quotas.

#### Resource Quotas

```python
RESOURCE_QUOTAS = {
    "docker": {
        "max_workers": 4,
        "max_memory_gb": 16,
        "max_cpu_cores": 8,
        "max_concurrent_tasks": 10
    },
    "ollama": {
        "max_workers": 2,
        "max_memory_gb": 32,
        "max_cpu_cores": 12,
        "max_concurrent_tasks": 4
    },
    "llm_api": {
        "max_workers": 10,
        "max_concurrent_tasks": 20,
        "rate_limit_per_minute": 100
    },
    "remote": {
        "max_workers": 10,
        "max_memory_gb": 100,
        "max_concurrent_tasks": 50
    }
}
```

#### Resource Manager Class

```python
class ResourceManager:
    def __init__(self, quotas: Dict[str, Any]):
        self.quotas = quotas
        self.current_usage = defaultdict(lambda: {
            "memory_gb": 0,
            "cpu_cores": 0,
            "concurrent_tasks": 0
        })

    def can_allocate(
        self,
        worker: BaseWorker,
        task: Task
    ) -> bool:
        """Check if resources available for task"""
        worker_type = worker.worker_type
        quota = self.quotas.get(worker_type, {})
        usage = self.current_usage[worker_type]

        # Check concurrent task limit
        if usage['concurrent_tasks'] >= quota.get('max_concurrent_tasks', float('inf')):
            return False

        # Check memory limit
        if usage['memory_gb'] + task.memory_required > quota.get('max_memory_gb', float('inf')):
            return False

        # Check CPU limit
        if usage['cpu_cores'] + task.cpu_required > quota.get('max_cpu_cores', float('inf')):
            return False

        return True

    def allocate(self, worker: BaseWorker, task: Task):
        """Allocate resources for task"""
        worker_type = worker.worker_type
        self.current_usage[worker_type]['concurrent_tasks'] += 1
        self.current_usage[worker_type]['memory_gb'] += task.memory_required
        self.current_usage[worker_type]['cpu_cores'] += task.cpu_required

    def release(self, worker: BaseWorker, task: Task):
        """Release resources after task completion"""
        worker_type = worker.worker_type
        self.current_usage[worker_type]['concurrent_tasks'] -= 1
        self.current_usage[worker_type]['memory_gb'] -= task.memory_required
        self.current_usage[worker_type]['cpu_cores'] -= task.cpu_required
```

---

### 4. Worker Implementations

#### Base Worker (`orchestrator/workers/base.py`)

Abstract base class for all worker types.

```python
from abc import ABC, abstractmethod
from typing import Any, Dict

class BaseWorker(ABC):
    def __init__(self, worker_id: str, worker_type: str, config: Dict[str, Any]):
        self.worker_id = worker_id
        self.worker_type = worker_type
        self.config = config
        self.current_load = 0
        self.status = "idle"  # idle, busy, error, offline

    @abstractmethod
    async def execute_task(self, task: Task) -> TaskResult:
        """Execute task and return result"""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check worker health"""
        pass

    def get_status(self) -> Dict[str, Any]:
        """Get current worker status"""
        return {
            "worker_id": self.worker_id,
            "worker_type": self.worker_type,
            "status": self.status,
            "current_load": self.current_load,
            "capabilities": self.get_capabilities()
        }

    @abstractmethod
    def get_capabilities(self) -> List[TaskType]:
        """Return list of task types this worker can handle"""
        pass
```

#### Docker Worker (`orchestrator/workers/docker_worker.py`)

Executes tasks in isolated Docker containers.

```python
import docker
from .base import BaseWorker

class DockerWorker(BaseWorker):
    def __init__(self, worker_id: str, config: Dict[str, Any]):
        super().__init__(worker_id, "docker", config)
        self.client = docker.from_env()
        self.container_image = config.get('image', 'vera-worker:latest')

    async def execute_task(self, task: Task) -> TaskResult:
        """Execute task in Docker container"""
        try:
            # Create container
            container = self.client.containers.run(
                self.container_image,
                command=task.command,
                environment=task.environment,
                volumes=task.volumes,
                detach=True,
                mem_limit=f"{task.memory_required}g",
                cpu_quota=task.cpu_required * 100000
            )

            # Wait for completion
            result = container.wait()

            # Get logs
            logs = container.logs().decode('utf-8')

            # Cleanup
            container.remove()

            return TaskResult(
                task_id=task.task_id,
                status="success" if result['StatusCode'] == 0 else "failed",
                output=logs,
                error=None if result['StatusCode'] == 0 else logs
            )

        except Exception as e:
            return TaskResult(
                task_id=task.task_id,
                status="error",
                output=None,
                error=str(e)
            )

    async def health_check(self) -> bool:
        """Check Docker daemon connection"""
        try:
            self.client.ping()
            return True
        except:
            return False

    def get_capabilities(self) -> List[TaskType]:
        return [
            TaskType.DOCKER_TASK,
            TaskType.CODE_EXECUTION,
            TaskType.TOOL_CALL
        ]
```

#### Ollama Worker (`orchestrator/workers/ollama_worker.py`)

Handles local LLM inference via Ollama.

```python
import aiohttp
from .base import BaseWorker

class OllamaWorker(BaseWorker):
    def __init__(self, worker_id: str, config: Dict[str, Any]):
        super().__init__(worker_id, "ollama", config)
        self.base_url = config.get('base_url', 'http://localhost:11434')
        self.model = config.get('model', 'gemma2:latest')

    async def execute_task(self, task: Task) -> TaskResult:
        """Execute LLM inference via Ollama"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": task.model or self.model,
                        "prompt": task.prompt,
                        "stream": False
                    }
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return TaskResult(
                            task_id=task.task_id,
                            status="success",
                            output=data.get('response'),
                            metadata={"model": data.get('model')}
                        )
                    else:
                        error = await response.text()
                        return TaskResult(
                            task_id=task.task_id,
                            status="error",
                            output=None,
                            error=error
                        )

        except Exception as e:
            return TaskResult(
                task_id=task.task_id,
                status="error",
                output=None,
                error=str(e)
            )

    async def health_check(self) -> bool:
        """Check Ollama service availability"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/api/tags") as response:
                    return response.status == 200
        except:
            return False

    def get_capabilities(self) -> List[TaskType]:
        return [
            TaskType.LLM_REQUEST,
            TaskType.OLLAMA_REQUEST,
            TaskType.BACKGROUND_COGNITION
        ]
```

#### LLM API Worker (`orchestrator/workers/llm_api_worker.py`)

Interfaces with cloud LLM APIs (OpenAI, Anthropic, Google Gemini).

```python
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
import google.generativeai as genai
from .base import BaseWorker

class LLMAPIWorker(BaseWorker):
    def __init__(self, worker_id: str, config: Dict[str, Any]):
        super().__init__(worker_id, "llm_api", config)
        self.provider = config.get('provider', 'openai')  # openai, anthropic, gemini

        if self.provider == 'openai':
            self.client = AsyncOpenAI(api_key=config['api_key'])
        elif self.provider == 'anthropic':
            self.client = AsyncAnthropic(api_key=config['api_key'])
        elif self.provider == 'gemini':
            genai.configure(api_key=config['api_key'])

    async def execute_task(self, task: Task) -> TaskResult:
        """Execute LLM request via cloud API"""
        try:
            if self.provider == 'openai':
                response = await self.client.chat.completions.create(
                    model=task.model or "gpt-4",
                    messages=[{"role": "user", "content": task.prompt}]
                )
                output = response.choices[0].message.content

            elif self.provider == 'anthropic':
                response = await self.client.messages.create(
                    model=task.model or "claude-3-opus-20240229",
                    messages=[{"role": "user", "content": task.prompt}],
                    max_tokens=task.max_tokens or 4096
                )
                output = response.content[0].text

            elif self.provider == 'gemini':
                model = genai.GenerativeModel(task.model or 'gemini-pro')
                response = await model.generate_content_async(task.prompt)
                output = response.text

            return TaskResult(
                task_id=task.task_id,
                status="success",
                output=output,
                metadata={"provider": self.provider, "model": task.model}
            )

        except Exception as e:
            return TaskResult(
                task_id=task.task_id,
                status="error",
                output=None,
                error=str(e)
            )

    async def health_check(self) -> bool:
        """Check API connectivity"""
        try:
            # Simple test request
            await self.execute_task(Task(
                task_id="health_check",
                task_type=TaskType.LLM_REQUEST,
                prompt="Say 'OK'",
                max_tokens=10
            ))
            return True
        except:
            return False

    def get_capabilities(self) -> List[TaskType]:
        return [
            TaskType.LLM_REQUEST,
            TaskType.BACKGROUND_COGNITION,
            TaskType.API_REQUEST
        ]
```

#### Remote Worker (`orchestrator/workers/remote_worker.py`)

Executes tasks on remote compute nodes via HTTP.

```python
import aiohttp
from .base import BaseWorker

class RemoteWorker(BaseWorker):
    def __init__(self, worker_id: str, config: Dict[str, Any]):
        super().__init__(worker_id, "remote", config)
        self.endpoint = config['endpoint']  # e.g., http://worker-node:8080
        self.auth_token = config.get('auth_token')

    async def execute_task(self, task: Task) -> TaskResult:
        """Submit task to remote worker node"""
        try:
            headers = {}
            if self.auth_token:
                headers['Authorization'] = f"Bearer {self.auth_token}"

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.endpoint}/execute",
                    json=task.to_dict(),
                    headers=headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return TaskResult.from_dict(data)
                    else:
                        error = await response.text()
                        return TaskResult(
                            task_id=task.task_id,
                            status="error",
                            output=None,
                            error=error
                        )

        except Exception as e:
            return TaskResult(
                task_id=task.task_id,
                status="error",
                output=None,
                error=str(e)
            )

    async def health_check(self) -> bool:
        """Check remote worker availability"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.endpoint}/health") as response:
                    return response.status == 200
        except:
            return False

    def get_capabilities(self) -> List[TaskType]:
        return [
            TaskType.REMOTE_COMPUTE,
            TaskType.TOOL_CALL,
            TaskType.CODE_EXECUTION,
            TaskType.BACKGROUND_COGNITION
        ]
```

---

### 5. Proactive Background Focus (`proactive_background_focus.py`)

Manages the focus board and proactive thinking cycles.

#### Key Features

- **Focus Board Management**: Tracks progress, next_steps, issues, ideas, actions, completed
- **CPU-Aware Scheduling**: Adjusts activity based on CPU utilization (70% threshold)
- **WebSocket Broadcasting**: Real-time focus board updates
- **Thought Generation**: Streaming LLM-generated thoughts
- **Memory Integration**: Saves insights to knowledge graph

#### Focus Board Structure

```python
focus_board = {
    "timestamp": "2025-01-15T14:30:00Z",
    "focus": "Network Security Analysis",
    "progress": [
        "Completed port scan on 192.168.1.0/24",
        "Identified 15 active hosts",
        "Catalogued open services"
    ],
    "next_steps": [
        "Analyze vulnerabilities for identified services",
        "Run Metasploit auxiliary modules",
        "Generate comprehensive report"
    ],
    "issues": [
        "Service on port 8080 returned unexpected response",
        "Authentication mechanism unclear for SSH service"
    ],
    "ideas": [
        "Implement automated patching workflow",
        "Create recurring scan schedule",
        "Build vulnerability trending dashboard"
    ],
    "actions": [
        "Schedule follow-up scan for next week",
        "Document findings in knowledge graph",
        "Notify security team of critical findings"
    ],
    "completed": [
        "Initial network reconnaissance",
        "Service enumeration"
    ]
}
```

#### Proactive Cycle

```python
class ProactiveFocusManager:
    def __init__(self, orchestrator, memory, llm):
        self.orchestrator = orchestrator
        self.memory = memory
        self.llm = llm
        self.focus_board = {}
        self.tick_interval = 60  # seconds

    async def run_proactive_cycle(self):
        """Execute one proactive thinking cycle"""

        # Check CPU usage
        cpu_usage = psutil.cpu_percent(interval=1)
        if cpu_usage > 70:
            logger.info("CPU usage high, skipping proactive cycle")
            return

        # Gather context
        context = await self.gather_context()

        # Generate thoughts
        thought = await self.generate_thought(context)

        # Validate thought
        if await self.validate_thought(thought):
            # Execute action
            result = await self.execute_thought(thought)

            # Update focus board
            self.update_focus_board(thought, result)

            # Broadcast update
            await self.broadcast_focus_update()

    async def gather_context(self) -> Dict[str, Any]:
        """Aggregate context from multiple sources"""
        return {
            "conversation_history": await self.memory.get_recent_history(limit=10),
            "focus_board": self.focus_board,
            "pending_goals": await self.memory.get_pending_goals(),
            "system_metrics": self.get_system_metrics()
        }

    async def generate_thought(self, context: Dict[str, Any]) -> str:
        """Generate proactive thought using LLM"""
        prompt = f"""
        Given the following context, generate an actionable next step:

        Recent Activity: {context['conversation_history']}
        Current Focus: {context['focus_board'].get('focus', 'None')}
        Pending Goals: {context['pending_goals']}

        What should I work on next? Provide a specific, executable task.
        """

        thought = await self.llm.ainvoke(prompt)
        return thought

    async def validate_thought(self, thought: str) -> bool:
        """Validate thought is actionable and safe"""
        validation_prompt = f"""
        Is this task safe and executable?
        Task: {thought}

        Answer with YES or NO and brief reasoning.
        """

        validation = await self.llm.ainvoke(validation_prompt)
        return "YES" in validation.upper()

    async def execute_thought(self, thought: str) -> TaskResult:
        """Submit thought as task to orchestrator"""
        task = Task(
            task_id=f"proactive_{int(time.time())}",
            task_type=TaskType.BACKGROUND_COGNITION,
            description=thought
        )

        result = await self.orchestrator.submit_task(task)
        return result

    def update_focus_board(self, thought: str, result: TaskResult):
        """Update focus board with new information"""
        if result.status == "success":
            self.focus_board['completed'].append(thought)
        else:
            self.focus_board['issues'].append(f"Failed: {thought}")

    async def broadcast_focus_update(self):
        """Broadcast focus board update via WebSocket"""
        # Implementation in ChatUI/api/proactivefocus_api.py
        await websocket_manager.broadcast({
            "type": "focus_update",
            "data": self.focus_board
        })
```

---

### 6. Worker Pool (`worker_pool.py`)

Manages pool of local workers for task execution.

```python
import asyncio
from typing import List, Dict, Any
from .tasks import Task, TaskResult

class WorkerPool:
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.workers = []
        self.task_queue = asyncio.Queue()
        self.results = {}

    async def submit_task(self, task: Task) -> asyncio.Future:
        """Submit task to pool"""
        future = asyncio.Future()
        await self.task_queue.put((task, future))
        return future

    async def worker_loop(self, worker_id: int):
        """Worker loop that processes tasks from queue"""
        while True:
            task, future = await self.task_queue.get()

            try:
                result = await self.execute_task(task)
                future.set_result(result)
            except Exception as e:
                future.set_exception(e)
            finally:
                self.task_queue.task_done()

    async def execute_task(self, task: Task) -> TaskResult:
        """Execute task logic"""
        # Implementation varies by task type
        pass

    async def start(self):
        """Start worker pool"""
        self.workers = [
            asyncio.create_task(self.worker_loop(i))
            for i in range(self.max_workers)
        ]

    async def stop(self):
        """Stop worker pool"""
        for worker in self.workers:
            worker.cancel()

        await asyncio.gather(*self.workers, return_exceptions=True)
```

---

## Configuration

### Orchestrator Configuration

```python
# BackgroundCognition/config.py
ORCHESTRATOR_CONFIG = {
    "routing": {
        "strategy": "least_loaded",  # least_loaded, random, round_robin, priority
        "health_check_interval": 30,  # seconds
        "task_timeout": 300  # seconds
    },
    "quotas": {
        "docker": {
            "max_workers": 4,
            "max_memory_gb": 16,
            "max_cpu_cores": 8,
            "max_concurrent_tasks": 10
        },
        "ollama": {
            "max_workers": 2,
            "max_memory_gb": 32,
            "max_cpu_cores": 12,
            "max_concurrent_tasks": 4
        },
        "llm_api": {
            "max_workers": 10,
            "max_concurrent_tasks": 20,
            "rate_limit_per_minute": 100
        },
        "remote": {
            "max_workers": 10,
            "max_memory_gb": 100,
            "max_concurrent_tasks": 50
        }
    },
    "workers": {
        "docker": {
            "enabled": True,
            "image": "vera-worker:latest",
            "auto_scale": True
        },
        "ollama": {
            "enabled": True,
            "base_url": "http://localhost:11434",
            "models": ["gemma2:latest", "gemma3:12b", "gpt-oss:20b"]
        },
        "llm_api": {
            "enabled": False,
            "providers": {
                "openai": {"api_key": "sk-..."},
                "anthropic": {"api_key": "sk-ant-..."},
                "gemini": {"api_key": "..."}
            }
        },
        "remote": {
            "enabled": False,
            "nodes": [
                {"endpoint": "http://worker1.local:8080", "auth_token": "..."},
                {"endpoint": "http://worker2.local:8080", "auth_token": "..."}
            ]
        }
    }
}
```

### Proactive Focus Configuration

```python
PROACTIVE_FOCUS_CONFIG = {
    "tick_interval": 60,  # seconds between proactive cycles
    "cpu_threshold": 70,  # skip if CPU above this %
    "max_parallel_thoughts": 3,
    "validation_threshold": 0.8,  # confidence threshold for action
    "context_providers": [
        "ConversationProvider",
        "FocusBoardProvider",
        "GoalsProvider",
        "MetricsProvider"
    ],
    "focus_board_path": "Configuration/focus_boards/",
    "websocket_broadcast": True
}
```

---

## API Integration

### FastAPI Endpoints (`orchestrator/api_integration.py`)

```python
from fastapi import FastAPI, HTTPException
from .core import Orchestrator
from .tasks import Task, TaskResult

app = FastAPI()
orchestrator = Orchestrator(ORCHESTRATOR_CONFIG)

@app.post("/task", response_model=TaskResult)
async def submit_task(task: Task):
    """Submit task for execution"""
    try:
        result = await orchestrator.submit_task(task)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/workers")
async def list_workers():
    """Get status of all workers"""
    return await orchestrator.get_worker_status()

@app.post("/workers/{worker_type}/register")
async def register_worker(worker_type: str, config: Dict[str, Any]):
    """Register new worker"""
    worker = create_worker(worker_type, config)
    orchestrator.register_worker(worker)
    return {"status": "registered", "worker_id": worker.worker_id}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "workers": len(orchestrator.workers)}
```

---

## Usage Examples

### Submit Task to Orchestrator

```python
from BackgroundCognition.orchestrator.core import Orchestrator
from BackgroundCognition.orchestrator.tasks import Task, TaskType

# Initialize orchestrator
orchestrator = Orchestrator(ORCHESTRATOR_CONFIG)

# Register workers
orchestrator.register_worker(DockerWorker("docker-1", docker_config))
orchestrator.register_worker(OllamaWorker("ollama-1", ollama_config))

# Submit LLM task
task = Task(
    task_id="llm_001",
    task_type=TaskType.LLM_REQUEST,
    prompt="Explain quantum computing in simple terms",
    model="gemma3:12b"
)

result = await orchestrator.submit_task(task)
print(result.output)
```

### Run Proactive Background Cycle

```python
from BackgroundCognition.proactive_background_focus import ProactiveFocusManager

# Initialize focus manager
focus_manager = ProactiveFocusManager(
    orchestrator=orchestrator,
    memory=vera.memory,
    llm=vera.deep_llm
)

# Run single cycle
await focus_manager.run_proactive_cycle()

# Or start continuous background processing
async def background_loop():
    while True:
        await focus_manager.run_proactive_cycle()
        await asyncio.sleep(focus_manager.tick_interval)

asyncio.create_task(background_loop())
```

### Distributed Task Execution

```python
# Register remote workers
remote_config = {
    "endpoint": "http://compute-node-1:8080",
    "auth_token": "secret_token"
}
orchestrator.register_worker(RemoteWorker("remote-1", remote_config))

# Submit compute-intensive task
task = Task(
    task_id="compute_001",
    task_type=TaskType.REMOTE_COMPUTE,
    command="python train_model.py",
    memory_required=16,  # GB
    cpu_required=8,  # cores
    environment={"DATASET_PATH": "/data/training.csv"}
)

result = await orchestrator.submit_task(task)
```

---

## Performance Tuning

### Worker Pool Sizing

```python
# Optimal worker counts based on available resources
WORKER_SIZING = {
    "16GB RAM, 8 cores": {
        "docker": 2,
        "ollama": 1,
        "local_pool": 4
    },
    "32GB RAM, 16 cores": {
        "docker": 4,
        "ollama": 2,
        "local_pool": 8
    },
    "64GB RAM, 24 cores": {
        "docker": 8,
        "ollama": 4,
        "local_pool": 12
    }
}
```

### Resource Monitoring

```python
import psutil

class ResourceMonitor:
    @staticmethod
    def get_system_metrics():
        return {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "available_memory_gb": psutil.virtual_memory().available / (1024**3),
            "cpu_count": psutil.cpu_count(),
            "load_average": psutil.getloadavg()
        }

    @staticmethod
    def should_scale_workers():
        metrics = ResourceMonitor.get_system_metrics()
        return (
            metrics['cpu_percent'] < 60 and
            metrics['memory_percent'] < 70
        )
```

---

## Troubleshooting

### Common Issues

**Workers Not Responding**
- Check worker health: `await orchestrator.get_worker_status()`
- Verify service connectivity (Ollama, Docker daemon)
- Review worker logs

**Resource Exhaustion**
- Reduce `max_concurrent_tasks` in quotas
- Lower worker count
- Enable remote workers to distribute load

**Task Queue Backlog**
- Increase worker pool size
- Optimize task execution time
- Implement task prioritization

---

**Last Updated:** January 2025
**Maintainer:** Vera-AI Development Team
**Version:** 1.0.0
