# Quick Start Guide

Get up and running with Vera Infrastructure Orchestration in minutes!

## Prerequisites

- Python 3.11+
- Docker (for container orchestration)
- Proxmox (optional, for VM/LXC orchestration)

## 1. Installation

```bash
# Clone repository
git clone https://github.com/your-org/vera-orchestrator.git
cd vera-orchestrator

# Run setup script
python setup.py
```

The setup script will:
- Check Python version
- Install dependencies
- Validate Docker/Proxmox connectivity
- Run basic tests
- Create configuration

## 2. Configuration

### Option A: Environment Variables

```bash
# Copy example environment file
cp .env.example .env

# Edit with your settings
nano .env
```

### Option B: Configuration File

```python
from vera_orchestrator_config import get_config

# Use pre-built configuration
config = get_config("local_dev")  # or "production", "gpu_cluster", "hybrid"
```

### Option C: Manual Configuration

```python
orchestrator = InfrastructureOrchestrator(
    enable_docker=True,
    enable_proxmox=False,
    auto_scale=True,
    max_resources=10
)
```

## 3. Quick Examples

### Example 1: Hello World

```python
from vera_orchestrator_infra import InfrastructureOrchestrator
from vera_orchestrator import task, TaskType

# Define task
@task("hello.world", task_type=TaskType.GENERAL)
def hello_world(name: str):
    return f"Hello, {name}!"

# Create orchestrator
orchestrator = InfrastructureOrchestrator(enable_docker=True)
orchestrator.start()

try:
    # Submit task
    task_id = orchestrator.submit_task("hello.world", name="World")
    
    # Get result
    result = orchestrator.wait_for_result(task_id, timeout=30)
    print(result.result)  # "Hello, World!"
    
finally:
    orchestrator.stop()
```

### Example 2: Auto-Scaling

```python
# Orchestrator with auto-scaling
orchestrator = InfrastructureOrchestrator(
    config={TaskType.GENERAL: 0},  # Start with 0 workers
    enable_docker=True,
    auto_scale=True,
    max_resources=5
)

orchestrator.start()

try:
    # Submit multiple tasks
    task_ids = [
        orchestrator.submit_task("hello.world", name=f"Task {i}")
        for i in range(10)
    ]
    
    # Orchestrator will automatically provision containers as needed
    
    # Wait for all results
    for task_id in task_ids:
        result = orchestrator.wait_for_result(task_id)
        print(result.result)
        
finally:
    orchestrator.stop()
```

### Example 3: Streaming Tasks

```python
@task("llm.generate", task_type=TaskType.LLM)
def generate_text(prompt: str):
    """Streaming task - yields chunks"""
    for i in range(10):
        yield f"Chunk {i+1} for: {prompt}\n"

# Submit and stream
task_id = orchestrator.submit_task("llm.generate", prompt="Hello")
for chunk in orchestrator.stream_result(task_id):
    print(chunk, end='', flush=True)
```

## 4. Docker Compose Deployment

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f orchestrator

# Stop all services
docker-compose down

# With monitoring (Prometheus + Grafana)
docker-compose --profile monitoring up -d
```

Access:
- Grafana: http://localhost:3000 (admin/admin)
- Prometheus: http://localhost:9090

## 5. Common Operations

### Provision Resources

```python
from vera_orchestrator_infra import ResourceType, ResourceSpec

# Define resource spec
spec = ResourceSpec(
    cpu_cores=2.0,
    memory_mb=2048,
    disk_gb=20
)

# Provision Docker containers
resources = orchestrator.provision_resources(
    ResourceType.DOCKER_CONTAINER,
    spec=spec,
    count=3,
    image="python:3.11-slim"
)

# Provision Proxmox VMs (if Proxmox enabled)
vm_resources = orchestrator.provision_resources(
    ResourceType.PROXMOX_VM,
    spec=spec,
    count=1,
    node="pve1"
)
```

### Monitor Infrastructure

```python
# Get overall stats
stats = orchestrator.get_infrastructure_stats()
print(f"Total Resources: {stats.total_resources}")
print(f"Available: {stats.available_resources}")
print(f"CPU Cores: {stats.total_capacity.cpu_cores}")
print(f"Memory: {stats.total_capacity.memory_mb} MB")

# Get resource-specific stats
for manager in orchestrator.resource_managers.values():
    for resource in manager.list_resources():
        resource_stats = manager.get_resource_stats(resource.resource_id)
        print(f"{resource.resource_id}: {resource_stats}")
```

### Cleanup Resources

```python
# Cleanup idle resources (5 minutes idle)
orchestrator.cleanup_idle_resources(max_idle_seconds=300)

# Manual cleanup
for resource in orchestrator.docker_manager.list_resources():
    orchestrator.docker_manager.deallocate_resource(resource.resource_id)
```

## 6. Run Example Suite

```bash
# Interactive menu
python vera_orchestrator_examples.py

# Run specific example
python -c "from vera_orchestrator_examples import example_docker_basic; example_docker_basic()"
```

## 7. Troubleshooting

### Docker Connection Issues

```bash
# Check Docker is running
sudo systemctl status docker

# Check permissions
docker ps

# Fix permissions (Linux)
sudo usermod -aG docker $USER
newgrp docker
```

### Proxmox Connection Issues

```bash
# Test connection
curl -k https://proxmox.example.com:8006/api2/json/version

# Test with token
curl -k https://proxmox.example.com:8006/api2/json/version \
  -H "Authorization: PVEAPIToken=USER@REALM!TOKENID=SECRET"
```

### No Resources Available

```python
# Check current allocation
stats = orchestrator.get_infrastructure_stats()
print(f"Available: {stats.available_resources}/{stats.total_resources}")

# Increase limit
orchestrator.max_resources = 20

# Force cleanup
orchestrator.cleanup_idle_resources(max_idle_seconds=0)
```

## 8. Next Steps

- Read the full documentation: [README.md](README.md)
- Explore configuration options: [vera_orchestrator_config.py](vera_orchestrator_config.py)
- Review examples: [vera_orchestrator_examples.py](vera_orchestrator_examples.py)
- Integrate with Vera AI system
- Set up monitoring with Prometheus/Grafana
- Configure production deployment

## 9. Getting Help

- GitHub Issues: https://github.com/your-org/vera-orchestrator/issues
- Documentation: https://docs.vera.ai/orchestration
- Email: support@vera.ai

## 10. What's Next?

After getting started, consider:

1. **Security**: Set up proper authentication and network isolation
2. **Monitoring**: Enable Prometheus metrics and Grafana dashboards
3. **Scaling**: Configure multi-node Proxmox cluster or Docker Swarm
4. **Integration**: Connect with your Vera AI pipelines
5. **Optimization**: Tune resource allocation and cleanup policies

Happy orchestrating! 🚀