# Vera Orchestration API - Complete Guide

Complete FastAPI-based REST API for the Vera orchestration system with support for local execution, infrastructure management (Docker/Proxmox), and external APIs (LLMs, cloud compute).

## 📦 Components

### 1. **Base Orchestrator API** (`orchestrator_api.py`)
- Task submission and management
- Worker pool scaling
- Task registry and metadata
- Real-time WebSocket updates
- System monitoring

### 2. **Infrastructure Management API** (`orchestrator_infrastructure_api.py`)
- Docker container provisioning and management
- Proxmox VM/LXC provisioning and management
- Resource allocation and tracking
- Auto-scaling capabilities
- Resource cleanup and optimization

### 3. **External API Management** (`orchestrator_external_api.py`)
- LLM provider integration (OpenAI, Anthropic, Google Gemini)
- Cloud compute APIs (AWS Lambda, RunPod)
- Cost tracking and optimization
- Streaming support for LLM responses
- Generic HTTP endpoint support

## 🚀 Quick Start

### Installation

```bash
# Install dependencies
pip install fastapi uvicorn websockets psutil
pip install docker proxmoxer  # For infrastructure management
pip install boto3  # For AWS Lambda
pip install openai anthropic google-generativeai  # For LLM providers
```

### Basic Setup

```python
from fastapi import FastAPI
from orchestrator_api import router as base_router
from orchestrator_infrastructure_api import router as infra_router
from orchestrator_external_api import router as external_router

app = FastAPI(title="Vera Orchestration")
app.include_router(base_router)
app.include_router(infra_router)
app.include_router(external_router)
```

### Run the Server

```bash
# Using the integration example
python orchestrator_integration_example.py

# Or with uvicorn directly
uvicorn orchestrator_integration_example:app --host 0.0.0.0 --port 8000
```

## 📚 API Endpoints

### Base Orchestrator (`/orchestrator`)

#### Initialize Orchestrator
```bash
POST /orchestrator/initialize
Content-Type: application/json

{
  "llm_workers": 3,
  "tool_workers": 4,
  "whisper_workers": 1,
  "background_workers": 2,
  "general_workers": 2,
  "cpu_threshold": 75.0
}
```

#### Submit Task
```bash
POST /orchestrator/tasks/submit
Content-Type: application/json

{
  "name": "compute.sum",
  "payload": {"a": 10, "b": 20},
  "priority": "normal",
  "context": {}
}
```

#### Get Status
```bash
GET /orchestrator/status

# Response
{
  "initialized": true,
  "running": true,
  "worker_count": 12,
  "active_workers": 3,
  "queue_size": 5
}
```

#### Scale Worker Pool
```bash
POST /orchestrator/workers/scale
Content-Type: application/json

{
  "task_type": "LLM",
  "num_workers": 5
}
```

#### WebSocket Updates
```javascript
const ws = new WebSocket('ws://localhost:8000/orchestrator/ws/updates');
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Update:', data);
};
```

### Infrastructure Management (`/orchestrator/infrastructure`)

#### Initialize Infrastructure
```bash
POST /orchestrator/infrastructure/initialize
Content-Type: application/json

{
  "enable_docker": true,
  "enable_proxmox": false,
  "docker_url": "unix://var/run/docker.sock",
  "auto_scale": true,
  "max_resources": 10
}
```

#### Provision Docker Container
```bash
POST /orchestrator/infrastructure/resources/docker/provision
Content-Type: application/json

{
  "spec": {
    "cpu_cores": 2.0,
    "memory_mb": 2048,
    "disk_gb": 20,
    "gpu_count": 0
  },
  "image": "python:3.11-slim",
  "task_type": "GENERAL",
  "environment": {
    "PYTHON_ENV": "production"
  },
  "network_mode": "bridge"
}

# Response
{
  "status": "success",
  "resource_id": "docker-a3f2c1",
  "resource_type": "docker_container",
  "message": "Docker container provisioned"
}
```

#### Provision Proxmox VM
```bash
POST /orchestrator/infrastructure/resources/proxmox/provision
Content-Type: application/json

{
  "spec": {
    "cpu_cores": 4,
    "memory_mb": 8192,
    "disk_gb": 100,
    "gpu_count": 1
  },
  "node": "pve-node1",
  "resource_type": "proxmox_vm",
  "template": "ubuntu-22.04-template",
  "storage": "local-lvm"
}
```

#### List Resources
```bash
GET /orchestrator/infrastructure/resources?status=available&resource_type=docker_container

# Response
[
  {
    "resource_id": "docker-a3f2c1",
    "resource_type": "docker_container",
    "status": "available",
    "spec": {
      "cpu_cores": 2.0,
      "memory_mb": 2048,
      "disk_gb": 20
    },
    "current_task_id": null,
    "total_tasks": 5
  }
]
```

#### Execute in Resource
```bash
POST /orchestrator/infrastructure/resources/{resource_id}/execute
Content-Type: application/json

{
  "command": "python --version",
  "workdir": "/app"
}

# Response
{
  "status": "success",
  "exit_code": 0,
  "output": "Python 3.11.5"
}
```

#### Scale Resources
```bash
POST /orchestrator/infrastructure/resources/scale
Content-Type: application/json

{
  "resource_type": "docker_container",
  "spec": {
    "cpu_cores": 1.0,
    "memory_mb": 1024,
    "disk_gb": 10
  },
  "count": 5,
  "task_type": "GENERAL"
}
```

#### Cleanup Idle Resources
```bash
POST /orchestrator/infrastructure/resources/cleanup
Content-Type: application/json

{
  "max_idle_seconds": 300
}
```

#### Get Infrastructure Stats
```bash
GET /orchestrator/infrastructure/stats

# Response
{
  "initialized": true,
  "total_resources": 8,
  "available_resources": 5,
  "allocated_resources": 2,
  "in_use_resources": 1,
  "total_capacity": {
    "cpu_cores": 16.0,
    "memory_mb": 16384,
    "disk_gb": 160,
    "gpu_count": 2
  },
  "available_capacity": {
    "cpu_cores": 10.0,
    "memory_mb": 10240,
    "disk_gb": 100,
    "gpu_count": 1
  },
  "tasks_executed": 342,
  "containers_created": 8,
  "vms_created": 0
}
```

### External API Management (`/orchestrator/external`)

#### Initialize External APIs
```bash
POST /orchestrator/external/initialize
Content-Type: application/json

{
  "openai": {
    "api_key": "sk-...",
    "base_url": null
  },
  "anthropic": {
    "api_key": "sk-ant-..."
  },
  "google": {
    "api_key": "your-google-api-key"
  },
  "aws_lambda": {
    "access_key": "AKIA...",
    "secret_key": "...",
    "region": "us-east-1"
  },
  "runpod": {
    "api_key": "your-runpod-key"
  }
}

# Response
{
  "status": "success",
  "providers_initialized": ["openai", "anthropic", "google"],
  "provider_count": 3
}
```

#### Execute Task on External API
```bash
POST /orchestrator/external/execute
Content-Type: application/json

{
  "provider": "openai",
  "task_name": "llm.summarize",
  "prompt": "Summarize the benefits of distributed computing",
  "model": "gpt-4",
  "timeout": 60.0,
  "extra_params": {
    "temperature": 0.7,
    "max_tokens": 500
  }
}

# Response
{
  "status": "success",
  "provider": "openai",
  "task_name": "llm.summarize",
  "result": "Distributed computing offers...",
  "tokens_in": 12,
  "tokens_out": 145,
  "cost_usd": 0.0234,
  "latency_ms": 1234.5
}
```

#### Stream LLM Response
```bash
POST /orchestrator/external/execute/stream
Content-Type: application/json

{
  "provider": "openai",
  "task_name": "llm.generate",
  "prompt": "Write a short story about AI",
  "model": "gpt-3.5-turbo",
  "stream": true
}

# Response (Server-Sent Events)
data: {"chunk": "Once upon a time"}
data: {"chunk": ", in a world where"}
data: {"chunk": " artificial intelligence..."}
data: {"status": "complete"}
```

#### LLM Completion (Convenience Endpoint)
```bash
POST /orchestrator/external/llm/complete?provider=openai&prompt=Hello+world&model=gpt-3.5-turbo&temperature=0.7&stream=false
```

#### List Providers
```bash
GET /orchestrator/external/providers

# Response
{
  "providers": [
    {
      "provider": "openai",
      "type": "llm",
      "initialized": true
    },
    {
      "provider": "anthropic",
      "type": "llm",
      "initialized": true
    },
    {
      "provider": "aws_lambda",
      "type": "compute",
      "initialized": true
    }
  ],
  "count": 3
}
```

#### Get Provider Stats
```bash
GET /orchestrator/external/stats/openai

# Response
{
  "provider": "openai",
  "total_requests": 156,
  "successful_requests": 152,
  "failed_requests": 4,
  "success_rate": 0.974,
  "total_tokens_in": 45230,
  "total_tokens_out": 67891,
  "total_cost_usd": 12.45,
  "avg_latency_ms": 1234.5,
  "last_request_at": 1701234567.89
}
```

#### Get Cost Summary
```bash
GET /orchestrator/external/stats/cost/summary

# Response
{
  "total_cost": 24.89,
  "by_provider": {
    "openai": 12.45,
    "anthropic": 8.23,
    "google": 4.21
  },
  "currency": "USD"
}
```

#### Get Token Summary
```bash
GET /orchestrator/external/stats/tokens/summary

# Response
{
  "total_tokens_in": 145230,
  "total_tokens_out": 234891,
  "total_tokens": 380121,
  "by_provider": {
    "openai": {
      "tokens_in": 45230,
      "tokens_out": 67891,
      "total": 113121
    },
    "anthropic": {
      "tokens_in": 67000,
      "tokens_out": 89000,
      "total": 156000
    }
  }
}
```

## 🔧 Configuration Examples

### Full Infrastructure Setup

```python
# Initialize with Docker and Proxmox
config = {
    "enable_docker": True,
    "enable_proxmox": True,
    "docker_url": "unix://var/run/docker.sock",
    "proxmox_host": "192.168.1.100",
    "proxmox_user": "root@pam",
    "proxmox_token_name": "api",
    "proxmox_token_value": "your-token",
    "auto_scale": True,
    "max_resources": 20
}
```

### External API Configuration

```python
# Configure all LLM providers
external_config = {
    "openai": {
        "api_key": "sk-...",
        "base_url": None  # or "https://api.openai.com/v1"
    },
    "anthropic": {
        "api_key": "sk-ant-..."
    },
    "google": {
        "api_key": "AIza..."
    },
    "aws_lambda": {
        "access_key": "AKIA...",
        "secret_key": "...",
        "region": "us-east-1"
    },
    "runpod": {
        "api_key": "..."
    }
}
```

## 📊 Monitoring & Metrics

### Real-Time WebSocket Monitoring

```javascript
// Connect to WebSocket
const ws = new WebSocket('ws://localhost:8000/orchestrator/ws/updates');

ws.onmessage = (event) => {
  const update = JSON.parse(event.data);
  
  switch(update.type) {
    case 'status_update':
      console.log('Queue size:', update.data.queue_size);
      break;
    case 'task_completed':
      console.log('Task completed:', update.data.task_id);
      break;
    case 'task_failed':
      console.log('Task failed:', update.data.task_id);
      break;
  }
};
```

### System Metrics

```bash
GET /orchestrator/system/metrics

# Response
{
  "metrics": {
    "timestamp": "2024-01-15T10:30:00",
    "cpu_percent": 45.2,
    "memory_percent": 62.8,
    "memory_used_gb": 10.5,
    "memory_total_gb": 16.0,
    "queue_size": 12
  }
}
```

## 🎯 Use Cases

### 1. Distributed LLM Processing
```bash
# Submit multiple LLM tasks across providers
curl -X POST http://localhost:8000/orchestrator/external/execute \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "task_name": "llm.analyze",
    "prompt": "Analyze this document...",
    "model": "gpt-4"
  }'
```

### 2. Auto-Scaling Docker Workers
```bash
# Enable auto-scaling
curl -X POST http://localhost:8000/orchestrator/infrastructure/initialize \
  -d '{"auto_scale": true, "max_resources": 20}'

# System will automatically provision Docker containers as needed
```

### 3. GPU Workload Management
```bash
# Provision GPU-enabled container
curl -X POST http://localhost:8000/orchestrator/infrastructure/resources/docker/provision \
  -d '{
    "spec": {"cpu_cores": 4, "memory_mb": 16384, "gpu_count": 1},
    "image": "pytorch/pytorch:latest"
  }'
```

### 4. Cost-Optimized LLM Selection
```bash
# Get cost summary to make informed decisions
curl http://localhost:8000/orchestrator/external/stats/cost/summary

# Use cheaper provider for simple tasks
# Use premium provider for complex tasks
```

## 🛡️ Error Handling

All endpoints return standard HTTP status codes:
- `200`: Success
- `400`: Bad request (invalid parameters)
- `404`: Resource not found
- `500`: Internal server error

Error response format:
```json
{
  "detail": "Error message describing what went wrong"
}
```

## 📈 Performance Tips

1. **Worker Pool Sizing**: Start with conservative numbers, scale based on metrics
2. **Resource Cleanup**: Run cleanup regularly to free idle resources
3. **Cost Monitoring**: Check cost stats frequently when using external APIs
4. **Auto-Scaling**: Enable for variable workloads, disable for predictable loads
5. **Streaming**: Use streaming for long-running LLM tasks to reduce latency

## 🔒 Security Considerations

1. **API Keys**: Store in environment variables, never commit to code
2. **Network**: Use HTTPS in production
3. **Authentication**: Add JWT/OAuth authentication middleware
4. **Rate Limiting**: Implement rate limiting for public APIs
5. **CORS**: Configure CORS appropriately for your use case

## 📝 Example Integration

```python
import requests

class VeraOrchestrationClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
    
    def submit_task(self, name, payload):
        response = requests.post(
            f"{self.base_url}/orchestrator/tasks/submit",
            json={"name": name, "payload": payload}
        )
        return response.json()["task_id"]
    
    def get_result(self, task_id, timeout=5):
        response = requests.get(
            f"{self.base_url}/orchestrator/tasks/result/{task_id}",
            params={"timeout": timeout}
        )
        return response.json()
    
    def provision_docker(self, cpu_cores, memory_mb):
        response = requests.post(
            f"{self.base_url}/orchestrator/infrastructure/resources/docker/provision",
            json={
                "spec": {
                    "cpu_cores": cpu_cores,
                    "memory_mb": memory_mb,
                    "disk_gb": 10
                }
            }
        )
        return response.json()["resource_id"]
    
    def llm_complete(self, provider, prompt, model=None):
        response = requests.post(
            f"{self.base_url}/orchestrator/external/execute",
            json={
                "provider": provider,
                "task_name": "llm.complete",
                "prompt": prompt,
                "model": model
            }
        )
        return response.json()["result"]

# Usage
client = VeraOrchestrationClient()
task_id = client.submit_task("compute.sum", {"a": 10, "b": 20})
result = client.get_result(task_id)
print(result)
```

## 🤝 Contributing

To extend the orchestration system:

1. Add new task types to `TaskType` enum
2. Implement task handlers using `@task` decorator
3. Register tasks with appropriate metadata
4. Add API endpoints as needed

## 📄 License

[Your License Here]

## 🆘 Support

For issues and questions:
- GitHub Issues: [your-repo-url]
- Documentation: [your-docs-url]
- Discord: [your-discord-url]