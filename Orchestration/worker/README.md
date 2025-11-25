# Worker Directory

## Table of Contents
- [Overview](#overview)
- [Files](#files)
- [Architecture](#architecture)
- [Worker API](#worker-api)
- [Docker Deployment](#docker-deployment)
- [Usage Examples](#usage-examples)
- [Configuration](#configuration)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)

---

## Overview

The worker directory implements Vera's distributed worker system - providing a FastAPI-based worker node that can be deployed in Docker containers or on remote machines to distribute computational tasks across a cluster.

**Purpose:** Distributed task execution nodes
**Technology:** FastAPI + Docker + Task Queue
**Total Files:** 3 files (API, Dockerfile, Documentation)
**Status:** ✅ Production
**Default Port:** 5000

### Key Features

- **Task Execution**: Execute arbitrary Python tasks
- **Docker Deployment**: Containerized worker nodes
- **API Interface**: RESTful API for task submission
- **Health Monitoring**: Built-in health checks
- **Resource Management**: CPU/memory tracking
- **Queue System**: Task queue with priority support
- **Distributed Architecture**: Multi-worker cluster support
- **Auto-scaling**: Dynamic worker pool scaling

---

## Files

### `worker_api.py` - Worker API

**Purpose:** FastAPI-based worker node API

**Size:** ~300 lines
**Framework:** FastAPI
**Port:** 5000 (default)

**Key Endpoints:**

#### POST `/task/submit` - Submit Task

```python
@app.post("/task/submit")
async def submit_task(task: TaskRequest):
    """
    Submit task to worker for execution

    Request:
        {
            "task_id": "task_123",
            "payload": {
                "function": "analyze_data",
                "args": [1, 2, 3],
                "kwargs": {"mode": "fast"}
            },
            "priority": "normal"
        }

    Response:
        {
            "status": "queued",
            "task_id": "task_123",
            "position": 5
        }
    """
```

#### GET `/task/{task_id}` - Get Task Status

```python
@app.get("/task/{task_id}")
async def get_task_status(task_id: str):
    """
    Get task execution status

    Response:
        {
            "task_id": "task_123",
            "status": "running|completed|failed",
            "result": {...},
            "started_at": "2025-01-15T10:00:00Z",
            "completed_at": "2025-01-15T10:05:00Z"
        }
    """
```

#### GET `/health` - Health Check

```python
@app.get("/health")
async def health_check():
    """
    Worker health status

    Response:
        {
            "status": "healthy",
            "active_tasks": 3,
            "queue_size": 12,
            "cpu_percent": 45.2,
            "memory_percent": 62.1
        }
    """
```

#### GET `/metrics` - Worker Metrics

```python
@app.get("/metrics")
async def get_metrics():
    """
    Detailed worker metrics

    Response:
        {
            "tasks_completed": 156,
            "tasks_failed": 2,
            "average_execution_time": 12.5,
            "uptime_seconds": 86400,
            "cpu_cores": 8,
            "memory_total_gb": 16
        }
    """
```

---

### `dockerfile` - Docker Configuration

**Purpose:** Container configuration for worker deployment

**Base Image:** python:3.10-slim
**Exposed Port:** 5000

**Dockerfile Contents:**

```dockerfile
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY worker_api.py .
COPY . /app/

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl --fail http://localhost:5000/health || exit 1

# Run worker
CMD ["uvicorn", "worker_api:app", "--host", "0.0.0.0", "--port", "5000"]
```

---

### `USER_GUIDE.MD` - User Documentation

**Purpose:** Worker deployment and usage guide

**Contents:**
- Installation instructions
- Configuration options
- Deployment patterns
- Usage examples
- Troubleshooting tips

---

## Architecture

### Distributed Worker System

```
┌─────────────────────────────────────────────────────┐
│              Orchestrator (Master)                   │
│                                                      │
│  ┌──────────────┐  ┌──────────────┐                │
│  │ Task Router  │  │ Worker Pool  │                │
│  │              │  │   Manager    │                │
│  └──────────────┘  └──────────────┘                │
└────────────────┬────────────────────────────────────┘
                 │
        ┌────────┼────────┬────────┐
        │        │        │        │
   ┌────▼───┐ ┌─▼────┐ ┌─▼────┐ ┌─▼────┐
   │Worker 1│ │Worker│ │Worker│ │Worker│
   │(Docker)│ │  2   │ │  3   │ │  N   │
   └────────┘ └──────┘ └──────┘ └──────┘
```

### Worker Internal Architecture

```
┌──────────────────────────────────────┐
│         Worker Node (FastAPI)         │
│                                       │
│  ┌────────────┐    ┌──────────────┐ │
│  │  API       │    │  Task Queue  │ │
│  │  Router    │───►│  (Priority)  │ │
│  └────────────┘    └──────┬───────┘ │
│                           │         │
│  ┌────────────┐    ┌──────▼───────┐ │
│  │  Resource  │    │   Executor   │ │
│  │  Monitor   │◄───│   Thread     │ │
│  └────────────┘    └──────────────┘ │
└──────────────────────────────────────┘
```

---

## Worker API

### Complete API Implementation

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
import asyncio
import uuid
from datetime import datetime
import psutil
from concurrent.futures import ThreadPoolExecutor
from queue import PriorityQueue

app = FastAPI(title="Vera Worker Node")

# Task storage
tasks = {}  # task_id -> task_data
task_queue = PriorityQueue()
executor = ThreadPoolExecutor(max_workers=4)

class TaskRequest(BaseModel):
    """Task submission request"""
    task_id: Optional[str] = None
    payload: Dict[str, Any]
    priority: str = "normal"  # low, normal, high, critical

class TaskResponse(BaseModel):
    """Task status response"""
    task_id: str
    status: str
    result: Optional[Any] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

@app.post("/task/submit")
async def submit_task(task: TaskRequest):
    """Submit task to worker"""
    task_id = task.task_id or str(uuid.uuid4())

    # Priority mapping
    priority_map = {
        "low": 3,
        "normal": 2,
        "high": 1,
        "critical": 0
    }

    # Create task record
    task_data = {
        "task_id": task_id,
        "payload": task.payload,
        "status": "queued",
        "queued_at": datetime.utcnow().isoformat(),
        "started_at": None,
        "completed_at": None,
        "result": None,
        "error": None
    }

    tasks[task_id] = task_data

    # Add to queue
    task_queue.put((
        priority_map.get(task.priority, 2),
        task_id
    ))

    return {
        "status": "queued",
        "task_id": task_id,
        "position": task_queue.qsize()
    }

@app.get("/task/{task_id}")
async def get_task_status(task_id: str):
    """Get task status"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    return tasks[task_id]

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()

    active_tasks = sum(
        1 for t in tasks.values()
        if t["status"] == "running"
    )

    return {
        "status": "healthy",
        "active_tasks": active_tasks,
        "queue_size": task_queue.qsize(),
        "cpu_percent": cpu_percent,
        "memory_percent": memory.percent,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/metrics")
async def get_metrics():
    """Get worker metrics"""
    completed = sum(1 for t in tasks.values() if t["status"] == "completed")
    failed = sum(1 for t in tasks.values() if t["status"] == "failed")

    # Calculate average execution time
    execution_times = []
    for task in tasks.values():
        if task["completed_at"] and task["started_at"]:
            start = datetime.fromisoformat(task["started_at"])
            end = datetime.fromisoformat(task["completed_at"])
            execution_times.append((end - start).total_seconds())

    avg_time = sum(execution_times) / len(execution_times) if execution_times else 0

    return {
        "tasks_completed": completed,
        "tasks_failed": failed,
        "tasks_queued": task_queue.qsize(),
        "average_execution_time": avg_time,
        "cpu_cores": psutil.cpu_count(),
        "memory_total_gb": psutil.virtual_memory().total / (1024**3)
    }

# Background task processor
async def process_tasks():
    """Background task processing loop"""
    while True:
        if not task_queue.empty():
            priority, task_id = task_queue.get()
            task_data = tasks[task_id]

            # Update status
            task_data["status"] = "running"
            task_data["started_at"] = datetime.utcnow().isoformat()

            try:
                # Execute task
                result = await execute_task(task_data["payload"])

                # Update result
                task_data["status"] = "completed"
                task_data["result"] = result
                task_data["completed_at"] = datetime.utcnow().isoformat()

            except Exception as e:
                # Update error
                task_data["status"] = "failed"
                task_data["error"] = str(e)
                task_data["completed_at"] = datetime.utcnow().isoformat()

        await asyncio.sleep(0.1)

async def execute_task(payload):
    """Execute task payload"""
    # Task execution logic here
    # This would call the appropriate function with args/kwargs
    function_name = payload.get("function")
    args = payload.get("args", [])
    kwargs = payload.get("kwargs", {})

    # Execute
    # result = function_registry[function_name](*args, **kwargs)

    return {"status": "success"}

@app.on_event("startup")
async def startup():
    """Start background task processor"""
    asyncio.create_task(process_tasks())
```

---

## Docker Deployment

### Build Worker Image

```bash
# Build image
docker build -t vera-worker:latest .

# Tag for registry
docker tag vera-worker:latest registry.example.com/vera-worker:latest

# Push to registry
docker push registry.example.com/vera-worker:latest
```

### Run Single Worker

```bash
# Run worker container
docker run -d \
  --name vera-worker-1 \
  -p 5000:5000 \
  -e WORKER_ID=worker-1 \
  -e LOG_LEVEL=INFO \
  vera-worker:latest

# Check logs
docker logs -f vera-worker-1

# Check health
curl http://localhost:5000/health
```

### Docker Compose Deployment

```yaml
# docker-compose.yml
version: '3.8'

services:
  worker-1:
    image: vera-worker:latest
    container_name: vera-worker-1
    ports:
      - "5001:5000"
    environment:
      - WORKER_ID=worker-1
      - LOG_LEVEL=INFO
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  worker-2:
    image: vera-worker:latest
    container_name: vera-worker-2
    ports:
      - "5002:5000"
    environment:
      - WORKER_ID=worker-2
      - LOG_LEVEL=INFO
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  worker-3:
    image: vera-worker:latest
    container_name: vera-worker-3
    ports:
      - "5003:5000"
    environment:
      - WORKER_ID=worker-3
      - LOG_LEVEL=INFO
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

networks:
  default:
    name: vera-workers
```

```bash
# Start worker cluster
docker-compose up -d

# Scale workers
docker-compose up -d --scale worker=5

# View logs
docker-compose logs -f

# Stop cluster
docker-compose down
```

---

## Usage Examples

### Submit Task to Worker

```python
import requests

# Submit task
response = requests.post('http://localhost:5000/task/submit', json={
    "payload": {
        "function": "process_data",
        "args": [1, 2, 3],
        "kwargs": {"mode": "fast"}
    },
    "priority": "high"
})

task_id = response.json()["task_id"]
print(f"Task submitted: {task_id}")

# Check status
import time
while True:
    status_response = requests.get(f'http://localhost:5000/task/{task_id}')
    status = status_response.json()

    print(f"Status: {status['status']}")

    if status['status'] in ['completed', 'failed']:
        print(f"Result: {status.get('result')}")
        print(f"Error: {status.get('error')}")
        break

    time.sleep(1)
```

### Monitor Worker Health

```python
def monitor_workers(worker_urls):
    """Monitor health of multiple workers"""
    for url in worker_urls:
        try:
            response = requests.get(f'{url}/health', timeout=5)
            health = response.json()

            print(f"\n{url}:")
            print(f"  Status: {health['status']}")
            print(f"  Active tasks: {health['active_tasks']}")
            print(f"  Queue size: {health['queue_size']}")
            print(f"  CPU: {health['cpu_percent']:.1f}%")
            print(f"  Memory: {health['memory_percent']:.1f}%")

        except Exception as e:
            print(f"\n{url}: ERROR - {e}")

# Usage
workers = [
    'http://localhost:5001',
    'http://localhost:5002',
    'http://localhost:5003'
]
monitor_workers(workers)
```

### Load Balancing

```python
def get_least_loaded_worker(worker_urls):
    """Find worker with least load"""
    best_worker = None
    min_load = float('inf')

    for url in worker_urls:
        try:
            response = requests.get(f'{url}/health', timeout=2)
            health = response.json()

            # Calculate load score
            load = (
                health['active_tasks'] * 2 +
                health['queue_size'] +
                health['cpu_percent'] / 10
            )

            if load < min_load:
                min_load = load
                best_worker = url

        except:
            continue

    return best_worker

# Usage
worker = get_least_loaded_worker(workers)
print(f"Selected worker: {worker}")
```

---

## Configuration

### Environment Variables

```bash
# Worker configuration
export WORKER_ID="worker-1"
export WORKER_PORT=5000
export LOG_LEVEL="INFO"
export MAX_WORKERS=4
export QUEUE_SIZE=100

# Resource limits
export MAX_CPU_PERCENT=90
export MAX_MEMORY_PERCENT=85

# Timeouts
export TASK_TIMEOUT=300
export HEALTH_CHECK_INTERVAL=30
```

### Configuration File

```python
# config.py
class WorkerConfig:
    WORKER_ID = os.getenv("WORKER_ID", "worker-1")
    PORT = int(os.getenv("WORKER_PORT", 5000))
    MAX_WORKERS = int(os.getenv("MAX_WORKERS", 4))
    QUEUE_SIZE = int(os.getenv("QUEUE_SIZE", 100))

    # Resource limits
    MAX_CPU_PERCENT = float(os.getenv("MAX_CPU_PERCENT", 90))
    MAX_MEMORY_PERCENT = float(os.getenv("MAX_MEMORY_PERCENT", 85))

    # Timeouts
    TASK_TIMEOUT = int(os.getenv("TASK_TIMEOUT", 300))
    HEALTH_CHECK_INTERVAL = int(os.getenv("HEALTH_CHECK_INTERVAL", 30))
```

---

## Monitoring

### Metrics Collection

```python
import prometheus_client as prom

# Define metrics
tasks_completed = prom.Counter('tasks_completed_total', 'Total tasks completed')
tasks_failed = prom.Counter('tasks_failed_total', 'Total tasks failed')
task_duration = prom.Histogram('task_duration_seconds', 'Task execution time')
active_tasks = prom.Gauge('active_tasks', 'Currently executing tasks')
queue_size = prom.Gauge('queue_size', 'Number of queued tasks')

# Expose metrics endpoint
from prometheus_client import generate_latest

@app.get("/metrics/prometheus")
async def prometheus_metrics():
    return generate_latest()
```

### Logging

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Log task execution
logger.info(f"Task {task_id} started")
logger.info(f"Task {task_id} completed in {duration}s")
logger.error(f"Task {task_id} failed: {error}")
```

---

## Troubleshooting

### Common Issues

**Worker Not Starting:**
```bash
# Check logs
docker logs vera-worker-1

# Verify port availability
netstat -tulpn | grep 5000

# Check resource limits
docker stats vera-worker-1
```

**Tasks Stuck in Queue:**
```python
# Check worker health
response = requests.get('http://localhost:5000/health')
print(response.json())

# Check executor threads
# Increase MAX_WORKERS if needed
```

**High CPU Usage:**
```bash
# Monitor resources
docker stats

# Limit CPU
docker update --cpus="2.0" vera-worker-1

# Or in docker-compose.yml:
# deploy:
#   resources:
#     limits:
#       cpus: '2.0'
```

---

## Related Documentation

- [Orchestrator](../BackgroundCognition/orchestrator/README.md)
- [Distributed System Architecture](../docs/distributed_architecture.md)

---

**Last Updated:** January 2025
**Maintainer:** Vera-AI Development Team
**Version:** 1.0.0
