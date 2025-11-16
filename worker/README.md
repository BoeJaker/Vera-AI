# Worker API

## Overview

The **Worker API** provides distributed task execution capabilities, enabling Vera to offload computation to remote systems or specialized hardware. Workers handle CPU-intensive, long-running, or resource-specific tasks asynchronously.

## Purpose

Worker nodes enable:
- **Distributed task execution** across multiple machines
- **Horizontal scaling** for compute-intensive workloads
- **Specialized worker pools** (GPU, high-memory, CPU-optimized)
- **Asynchronous task processing** without blocking main agent
- **Remote system integration** and cluster deployment

## Architecture Role

```
CEO/PBC → Task Queue → Worker Pool → Worker Selection
              ↓
         Worker API (HTTP)
              ↓
    Task Execution (isolated environment)
              ↓
    Result Return → Memory Storage
```

Workers act as execution endpoints for tasks that require:
- Heavy computation (ML training, data processing)
- Specialized hardware (GPU inference, large memory)
- Isolation (security analysis, sandboxed code execution)
- Parallelism (batch processing, concurrent operations)

## Key Files

| File | Purpose |
|------|---------|
| `worker_api.py` | FastAPI endpoint for task execution and management |
| `dockerfile` | Container definition for worker deployment |
| `USER_GUIDE.MD` | Comprehensive deployment and usage documentation |

## Technologies

- **FastAPI** - High-performance async Python web framework
- **Docker** - Containerization for portable deployment
- **HTTP/REST** - Communication protocol
- **Pydantic** - Request/response validation
- **Uvicorn** - ASGI server for production

## Worker API Endpoints

### Health Check
```http
GET /health
```
Returns worker status and capabilities.

**Response:**
```json
{
  "status": "healthy",
  "worker_id": "worker-001",
  "capabilities": ["cpu", "high-memory"],
  "active_tasks": 2,
  "queue_depth": 5,
  "uptime_seconds": 86400
}
```

### Execute Task
```http
POST /execute
Content-Type: application/json
```

**Request:**
```json
{
  "task_id": "task-abc-123",
  "task_type": "toolchain_execution",
  "payload": {
    "query": "Analyze security vulnerabilities",
    "tools": ["NetworkScanner", "VulnerabilityAnalyzer"],
    "timeout": 300
  },
  "priority": "high",
  "callback_url": "http://vera-main:8000/task/complete"
}
```

**Response:**
```json
{
  "task_id": "task-abc-123",
  "status": "accepted",
  "estimated_completion": "2024-01-15T14:35:00Z",
  "worker_id": "worker-001"
}
```

### Get Task Status
```http
GET /task/{task_id}/status
```

**Response:**
```json
{
  "task_id": "task-abc-123",
  "status": "running",
  "progress": 0.45,
  "started_at": "2024-01-15T14:30:00Z",
  "estimated_completion": "2024-01-15T14:35:00Z"
}
```

### Get Task Result
```http
GET /task/{task_id}/result
```

**Response:**
```json
{
  "task_id": "task-abc-123",
  "status": "completed",
  "result": {
    "vulnerabilities_found": 3,
    "report": "...",
    "severity": "medium"
  },
  "execution_time_seconds": 42.5,
  "completed_at": "2024-01-15T14:32:42Z"
}
```

### Cancel Task
```http
DELETE /task/{task_id}
```

## Deployment

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run worker locally
python3 worker_api.py --host 0.0.0.0 --port 8001
```

### Docker Deployment
```bash
# Build image
docker build -t vera-worker:latest .

# Run container
docker run -d \
  --name vera-worker-1 \
  -p 8001:8000 \
  -e WORKER_ID=worker-001 \
  -e WORKER_CAPABILITIES=cpu,high-memory \
  vera-worker:latest
```

### Docker Compose (Multiple Workers)
```yaml
version: '3.8'

services:
  worker-cpu-1:
    build: .
    ports:
      - "8001:8000"
    environment:
      - WORKER_ID=worker-cpu-1
      - WORKER_CAPABILITIES=cpu
      - MAX_CONCURRENT_TASKS=4

  worker-gpu-1:
    build: .
    ports:
      - "8002:8000"
    environment:
      - WORKER_ID=worker-gpu-1
      - WORKER_CAPABILITIES=gpu,cuda
      - MAX_CONCURRENT_TASKS=2
    runtime: nvidia
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  worker-memory-1:
    build: .
    ports:
      - "8003:8000"
    environment:
      - WORKER_ID=worker-memory-1
      - WORKER_CAPABILITIES=high-memory
      - MAX_CONCURRENT_TASKS=2
    deploy:
      resources:
        limits:
          memory: 64G
```

### Kubernetes Deployment
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vera-worker
spec:
  replicas: 3
  selector:
    matchLabels:
      app: vera-worker
  template:
    metadata:
      labels:
        app: vera-worker
    spec:
      containers:
      - name: worker
        image: vera-worker:latest
        ports:
        - containerPort: 8000
        env:
        - name: WORKER_CAPABILITIES
          value: "cpu"
        resources:
          requests:
            memory: "8Gi"
            cpu: "2"
          limits:
            memory: "16Gi"
            cpu: "4"
---
apiVersion: v1
kind: Service
metadata:
  name: vera-worker-service
spec:
  selector:
    app: vera-worker
  ports:
  - protocol: TCP
    port: 8000
    targetPort: 8000
  type: LoadBalancer
```

## Configuration

### Environment Variables
```bash
# Worker identification
WORKER_ID=worker-001
WORKER_CAPABILITIES=cpu,high-memory,specialized

# Resource limits
MAX_CONCURRENT_TASKS=4
MAX_MEMORY_GB=32
MAX_CPU_CORES=8

# Timeouts
TASK_TIMEOUT_SECONDS=600
HEALTH_CHECK_INTERVAL=30

# Callback configuration
CALLBACK_ENABLED=true
CALLBACK_RETRY_ATTEMPTS=3

# Logging
LOG_LEVEL=INFO
LOG_FILE=/var/log/vera-worker.log
```

### Worker Capabilities

Workers can advertise capabilities for intelligent routing:

| Capability | Description | Example Use Case |
|------------|-------------|------------------|
| `cpu` | CPU-intensive tasks | Data processing, compilation |
| `gpu` | GPU acceleration | ML inference, rendering |
| `cuda` | CUDA-enabled GPU | Deep learning, CUDA kernels |
| `high-memory` | Large memory (64GB+) | Big data, in-memory databases |
| `specialized` | Domain-specific | Security scanning, video encoding |
| `sandbox` | Isolated execution | Code execution, untrusted workloads |

## Worker Pool Integration

### Registering Workers with Vera

**Manual Registration:**
```python
from BackgroundCognition.worker_pool import WorkerPool

pool = WorkerPool()
pool.register_worker(
    url="http://worker1:8000",
    capabilities=["cpu", "high-memory"],
    priority=1
)
```

**Auto-Discovery:**
```python
# Workers announce themselves via multicast/service discovery
pool = WorkerPool(auto_discover=True)
pool.start_discovery()
```

### Task Routing

**Label-Based Routing:**
```python
pool.assign_task(
    task=compute_task,
    required_capabilities=["gpu", "cuda"],
    preferred_worker="worker-gpu-1"
)
```

**Load-Based Routing:**
```python
pool.assign_task(
    task=compute_task,
    strategy="least_loaded"  # Routes to worker with lowest queue
)
```

## Task Types

### ToolChain Execution
```python
{
  "task_type": "toolchain_execution",
  "payload": {
    "query": "Security analysis",
    "tools": [...],
    "context": {...}
  }
}
```

### Model Inference
```python
{
  "task_type": "model_inference",
  "payload": {
    "model": "gemma3:27b",
    "prompt": "...",
    "max_tokens": 2000
  }
}
```

### Data Processing
```python
{
  "task_type": "data_processing",
  "payload": {
    "operation": "transform",
    "data": [...],
    "transformations": [...]
  }
}
```

### Custom Tasks
```python
{
  "task_type": "custom",
  "payload": {
    "handler": "custom_security_scan",
    "params": {...}
  }
}
```

## Retry and Error Handling

### Automatic Retry
```python
@retry(
    max_attempts=3,
    backoff=exponential(base=2),
    retry_on=[NetworkError, TimeoutError, WorkerBusyError]
)
def execute_on_worker(task, worker_url):
    return requests.post(f"{worker_url}/execute", json=task)
```

### Circuit Breaker
```python
circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60,
    expected_exception=WorkerError
)

@circuit_breaker
def execute_task(task):
    return worker.execute(task)
```

## Monitoring

### Metrics Endpoint
```http
GET /metrics
```

**Response:**
```json
{
  "tasks_completed": 1542,
  "tasks_failed": 23,
  "success_rate": 0.985,
  "avg_execution_time_seconds": 15.3,
  "active_tasks": 2,
  "queue_depth": 5,
  "cpu_usage_percent": 68.5,
  "memory_usage_gb": 12.4,
  "uptime_hours": 168.5
}
```

### Logging
```python
# Structured logging for observability
logger.info(
    "Task execution completed",
    extra={
        "task_id": task_id,
        "execution_time": 15.3,
        "worker_id": worker_id,
        "status": "success"
    }
)
```

## Security

### Authentication
```python
# API key authentication
headers = {
    "X-API-Key": "your-worker-api-key",
    "Content-Type": "application/json"
}
```

### Sandboxing
```python
# Execute untrusted code in isolated container
{
  "task_type": "sandboxed_execution",
  "payload": {
    "code": "...",
    "language": "python",
    "timeout": 30,
    "memory_limit_mb": 512
  }
}
```

### Rate Limiting
```python
from fastapi import FastAPI
from slowapi import Limiter

limiter = Limiter(key_func=get_remote_address)
app = FastAPI()

@app.post("/execute")
@limiter.limit("10/minute")
async def execute_task(task: Task):
    ...
```

## Use Cases

### ML Model Inference
```python
# Offload large model inference to GPU worker
result = worker_pool.execute(
    task={
        "type": "model_inference",
        "model": "llama3:70b",
        "prompt": "..."
    },
    required_capabilities=["gpu", "cuda"],
    timeout=120
)
```

### Security Scanning
```python
# Isolated security scan on sandbox worker
result = worker_pool.execute(
    task={
        "type": "security_scan",
        "target": "192.168.1.0/24"
    },
    required_capabilities=["sandbox", "specialized"],
    timeout=600
)
```

### Batch Processing
```python
# Distribute batch processing across worker pool
tasks = [create_task(item) for item in dataset]
results = worker_pool.execute_batch(
    tasks=tasks,
    parallelism=10,
    strategy="round_robin"
)
```

## Best Practices

### Resource Management
- Set appropriate resource limits per worker
- Monitor memory/CPU usage
- Implement task timeouts

### Fault Tolerance
- Use retry policies with exponential backoff
- Implement circuit breakers for failing workers
- Maintain worker health checks

### Scaling
- Add workers horizontally as load increases
- Use load balancing for task distribution
- Implement auto-scaling based on queue depth

### Monitoring
- Collect metrics from all workers
- Centralize logging for debugging
- Set up alerts for worker failures

## Troubleshooting

### Worker Not Responding
```bash
# Check worker health
curl http://worker1:8000/health

# Check worker logs
docker logs vera-worker-1

# Restart worker
docker restart vera-worker-1
```

### Task Timeout
```bash
# Increase timeout in configuration
# Environment variable: TASK_TIMEOUT_SECONDS=1200

# Or per-task timeout
{
  "task": {...},
  "timeout": 1200
}
```

### High Queue Depth
```bash
# Add more workers
docker-compose up --scale worker-cpu=5

# Or increase concurrency
# Environment variable: MAX_CONCURRENT_TASKS=8
```

## Related Documentation

- [User Guide](USER_GUIDE.MD) - Comprehensive deployment guide
- [Worker Pool Architecture](../BackgroundCognition/worker_pool.py)
- [Cluster Integration](../BackgroundCognition/cluster.py)
- [Proactive Background Cognition](../BackgroundCognition/)

## Contributing

To extend worker capabilities:
1. Add new task types in `worker_api.py`
2. Implement custom task handlers
3. Add capability discovery mechanisms
4. Extend monitoring and metrics
5. Add documentation and examples

---

**Related Components:**
- [Background Cognition](../BackgroundCognition/) - Autonomous task generation
- [Toolchain](../Toolchain/) - Tool execution orchestration
- [CEO Orchestrator](../Vera%20Assistant%20Docs/Central%20Executive%20Orchestrator.md)
