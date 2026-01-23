# Vera Infrastructure Orchestration System

A sophisticated task orchestration system with **Docker** and **Proxmox** integration for dynamic resource allocation, auto-scaling, and distributed computing.

## 🚀 Features

### Core Orchestration
- **Task Registry**: Decorator-based task registration with metadata
- **Priority Queuing**: Multi-level priority system for task scheduling
- **Worker Pools**: Specialized pools for different task types (LLM, ML, Tools, etc.)
- **Streaming Support**: Native support for generator-based tasks
- **Event System**: Redis-based pub/sub for distributed coordination

### Infrastructure Management
- **Docker Integration**: Full container lifecycle management
- **Proxmox Integration**: VM and LXC container orchestration
- **Auto-Scaling**: Automatic resource provisioning based on demand
- **Resource Pooling**: Efficient reuse of computational resources
- **GPU Support**: First-class support for GPU-accelerated workloads

### Advanced Features
- **CPU-Aware Throttling**: Prevents system overload
- **Resource Monitoring**: Real-time statistics and metrics
- **Proactive Focus Integration**: Links with ProactiveFocusManager
- **Hybrid Deployments**: Mix Docker and Proxmox resources

## 📋 Requirements

- Python 3.11+
- Docker (if using Docker resources)
- Proxmox VE 7.0+ (if using Proxmox resources)
- Redis (optional, for distributed deployments)

## 🔧 Installation

### Basic Installation

```bash
# Clone repository
git clone https://github.com/your-org/vera-orchestrator.git
cd vera-orchestrator

# Install dependencies
pip install -r requirements.txt
```

### Docker Setup

```bash
# Ensure Docker daemon is running
sudo systemctl start docker

# Add user to docker group (Linux)
sudo usermod -aG docker $USER
newgrp docker

# Verify Docker access
docker ps
```

### Proxmox Setup

1. **Create API Token**:
   ```bash
   # In Proxmox UI: Datacenter → Permissions → API Tokens
   # Create token for user (e.g., root@pam)
   # Note the Token ID and Secret
   ```

2. **Configure Permissions**:
   ```bash
   # Grant necessary permissions to the token user
   pveum role add Orchestrator -privs "VM.Allocate VM.Config.* Datastore.Allocate*"
   pveum acl modify / -user orchestrator@pam -role Orchestrator
   ```

3. **Test Connection**:
   ```python
   from proxmoxer import ProxmoxAPI
   proxmox = ProxmoxAPI('proxmox.example.com', 
                        user='root@pam',
                        token_name='orchestrator',
                        token_value='your-secret-token',
                        verify_ssl=False)
   print(proxmox.version.get())
   ```

## 🎯 Quick Start

### Example 1: Basic Docker Orchestration

```python
from vera_orchestrator_infra import (
    InfrastructureOrchestrator,
    ResourceType, ResourceSpec,
    TaskType, task
)

# Define a task
@task("compute.fibonacci", task_type=TaskType.GENERAL)
def fibonacci(n: int):
    if n <= 1:
        return n
    a, b = 0, 1
    for _ in range(n - 1):
        a, b = b, a + b
    return b

# Initialize orchestrator
orchestrator = InfrastructureOrchestrator(
    enable_docker=True,
    auto_scale=True,
    max_resources=5
)

orchestrator.start()

try:
    # Submit task (auto-provisions container if needed)
    task_id = orchestrator.submit_task("compute.fibonacci", n=30)
    
    # Wait for result
    result = orchestrator.wait_for_result(task_id, timeout=30)
    print(f"Result: {result.result}")
    
finally:
    orchestrator.stop()
```

### Example 2: Streaming Task

```python
@task("llm.generate", task_type=TaskType.LLM)
def generate_text(prompt: str):
    """Streaming LLM generation"""
    for i in range(10):
        yield f"Chunk {i+1}: Generated text for '{prompt}'\n"

# Submit streaming task
task_id = orchestrator.submit_task("llm.generate", prompt="Hello world")

# Stream results
for chunk in orchestrator.stream_result(task_id):
    print(chunk, end='', flush=True)
```

### Example 3: GPU Workload

```python
@task(
    "ml.train",
    task_type=TaskType.ML_MODEL,
    requires_gpu=True,
    requires_cpu_cores=4,
    memory_mb=8192
)
def train_model(model_name: str):
    # Your training code here
    return f"Trained {model_name}"

# Auto-provisions GPU-enabled container
task_id = orchestrator.submit_task("ml.train", model_name="ResNet50")
result = orchestrator.wait_for_result(task_id)
```

### Example 4: Mixed Infrastructure

```python
from vera_orchestrator_config import HYBRID_CONFIG

orchestrator = InfrastructureOrchestrator(
    **HYBRID_CONFIG,
    enable_docker=True,
    enable_proxmox=True,
    proxmox_config={
        "host": "proxmox.internal",
        "user": "orchestrator@pam",
        "token_name": "my-token",
        "token_value": "secret-value"
    }
)

orchestrator.start()

# Quick tasks run in Docker
quick_task = orchestrator.submit_task("tool.parse_json", data={...})

# Heavy tasks run in Proxmox VMs
heavy_task = orchestrator.submit_task("ml.train_large_model", ...)
```

## 📖 Configuration

### Configuration Scenarios

The system includes pre-built configurations for different scenarios:

```python
from vera_orchestrator_config import get_config

# Local development (Docker only)
config = get_config("local_dev")

# Production (Docker + Proxmox)
config = get_config("production")

# GPU cluster
config = get_config("gpu_cluster")

# Hybrid deployment
config = get_config("hybrid")
```

### Environment Variables

```bash
# Worker configuration
export WORKERS_LLM=4
export WORKERS_ML=2
export WORKERS_GENERAL=4

# Resource limits
export MAX_RESOURCES=20
export AUTO_SCALE=true

# Docker
export DOCKER_ENABLED=true
export DOCKER_URL=unix:///var/run/docker.sock

# Proxmox
export PROXMOX_ENABLED=true
export PROXMOX_HOST=proxmox.example.com
export PROXMOX_USER=orchestrator@pam
export PROXMOX_TOKEN_NAME=my-token
export PROXMOX_TOKEN_VALUE=secret-value

# Redis (optional)
export REDIS_URL=redis://localhost:6379/0
```

### Custom Configuration

```python
from vera_orchestrator_infra import InfrastructureOrchestrator
from vera_orchestrator import TaskType

orchestrator = InfrastructureOrchestrator(
    config={
        TaskType.LLM: 4,      # 4 LLM workers
        TaskType.TOOL: 8,     # 8 tool workers
        TaskType.ML_MODEL: 2  # 2 ML workers
    },
    enable_docker=True,
    enable_proxmox=True,
    auto_scale=True,
    max_resources=20,
    cpu_threshold=80.0,
    docker_url="tcp://docker-host:2375",
    proxmox_config={
        "host": "proxmox.internal",
        "user": "orchestrator@pam",
        "token_name": "my-token",
        "token_value": "secret",
        "verify_ssl": False,
        "default_node": "pve1"
    }
)
```

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   InfrastructureOrchestrator                │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  TaskQueue   │  │  WorkerPool  │  │  EventBus    │     │
│  │  (Priority)  │  │  (Multiple)  │  │  (Pub/Sub)   │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
                            │
                            │
        ┌───────────────────┴───────────────────┐
        │                                       │
        ▼                                       ▼
┌───────────────────┐                  ┌───────────────────┐
│  DockerManager    │                  │  ProxmoxManager   │
├───────────────────┤                  ├───────────────────┤
│ • Containers      │                  │ • VMs             │
│ • Resource Pools  │                  │ • LXC Containers  │
│ • Auto-scaling    │                  │ • Storage         │
│ • GPU Support     │                  │ • Networking      │
└───────────────────┘                  └───────────────────┘
        │                                       │
        │                                       │
        ▼                                       ▼
┌───────────────────┐                  ┌───────────────────┐
│  Docker Daemon    │                  │  Proxmox Cluster  │
└───────────────────┘                  └───────────────────┘
```

## 🔍 Resource Management

### Resource Specifications

```python
from vera_orchestrator_infra import ResourceSpec

# Define resource requirements
spec = ResourceSpec(
    cpu_cores=4.0,        # Can be fractional for containers
    memory_mb=8192,       # 8GB RAM
    disk_gb=50,           # 50GB disk
    gpu_count=1,          # 1 GPU
    gpu_memory_mb=24576,  # 24GB VRAM
    network_bandwidth_mbps=1000
)
```

### Manual Provisioning

```python
# Provision Docker containers
resources = orchestrator.provision_resources(
    ResourceType.DOCKER_CONTAINER,
    spec=spec,
    count=3,
    image="pytorch/pytorch:latest",
    task_type=TaskType.ML_MODEL,
    volumes={
        "/host/data": {"bind": "/data", "mode": "rw"}
    },
    environment={
        "CUDA_VISIBLE_DEVICES": "0"
    }
)

# Provision Proxmox VMs
vm_resources = orchestrator.provision_resources(
    ResourceType.PROXMOX_VM,
    spec=spec,
    count=1,
    node="pve1",
    template=9000,  # Clone from template
    storage="local-lvm",
    network_bridge="vmbr0"
)
```

### Auto-Scaling

When `auto_scale=True`, the orchestrator automatically provisions resources:

```python
# Task submitted → No available resources → Auto-provision → Execute
task_id = orchestrator.submit_task("ml.train", model="resnet50")

# Orchestrator will:
# 1. Check for available resources matching requirements
# 2. If none found and under max_resources limit, provision new resource
# 3. Allocate resource to task
# 4. Execute task
# 5. Release resource when complete
```

### Resource Cleanup

```python
# Manual cleanup of idle resources
orchestrator.cleanup_idle_resources(max_idle_seconds=300)

# Automatic cleanup (runs periodically)
# Set in Docker/Proxmox config:
config["docker"]["cleanup_idle_seconds"] = 300
config["docker"]["cleanup_interval_seconds"] = 60
```

## 📊 Monitoring

### Infrastructure Statistics

```python
stats = orchestrator.get_infrastructure_stats()

print(f"Total Resources: {stats.total_resources}")
print(f"Available: {stats.available_resources}")
print(f"In Use: {stats.in_use_resources}")
print(f"Total CPU: {stats.total_capacity.cpu_cores} cores")
print(f"Total Memory: {stats.total_capacity.memory_mb} MB")
print(f"Total GPUs: {stats.total_capacity.gpu_count}")
print(f"Tasks Executed: {stats.tasks_executed}")
```

### Resource-Level Monitoring

```python
# Get stats for specific resource
for manager in orchestrator.resource_managers.values():
    for resource in manager.list_resources():
        stats = manager.get_resource_stats(resource.resource_id)
        print(f"{resource.resource_id}:")
        print(f"  CPU: {stats.get('cpu_percent', 0):.2f}%")
        print(f"  Memory: {stats.get('memory_usage_mb', 0):.2f} MB")
        print(f"  Status: {resource.status.name}")
        print(f"  Tasks: {resource.total_tasks}")
```

### Event Monitoring

```python
def on_resource_provisioned(event):
    print(f"Resource provisioned: {event['resource_id']}")

def on_task_completed(event):
    print(f"Task completed: {event['task_id']} in {event['duration']:.2f}s")

orchestrator.event_bus.subscribe("resource.provisioned", on_resource_provisioned)
orchestrator.event_bus.subscribe("task.completed", on_task_completed)
```

## 🔒 Security Considerations

### Docker Security

1. **Socket Access**: Limit access to Docker socket
   ```bash
   sudo chown root:docker /var/run/docker.sock
   sudo chmod 660 /var/run/docker.sock
   ```

2. **Container Isolation**: Use network namespaces
   ```python
   orchestrator.provision_resources(
       ResourceType.DOCKER_CONTAINER,
       network_mode="none"  # No network access
   )
   ```

3. **Resource Limits**: Always specify limits
   ```python
   spec = ResourceSpec(
       cpu_cores=2.0,
       memory_mb=1024
   )
   ```

### Proxmox Security

1. **API Token**: Use tokens instead of passwords
2. **Least Privilege**: Grant minimal required permissions
3. **Network Isolation**: Use separate VLANs for orchestrated VMs
4. **SSL/TLS**: Enable SSL verification in production
   ```python
   proxmox_config = {
       "verify_ssl": True,
       # ... other config
   }
   ```

## 🧪 Testing

Run the example suite:

```bash
python vera_orchestrator_examples.py
```

Run specific examples:

```python
from vera_orchestrator_examples import (
    example_docker_basic,
    example_docker_autoscale,
    example_resource_pooling,
    example_monitoring
)

example_docker_basic()
example_docker_autoscale()
example_resource_pooling()
example_monitoring()
```

## 🐛 Troubleshooting

### Docker Issues

**Problem**: Cannot connect to Docker daemon
```bash
# Check Docker is running
sudo systemctl status docker

# Check socket permissions
ls -l /var/run/docker.sock

# Test Docker access
docker ps
```

**Problem**: Out of memory errors
```python
# Increase container memory limits
spec = ResourceSpec(memory_mb=4096)  # 4GB instead of default
```

### Proxmox Issues

**Problem**: Authentication failed
```bash
# Verify credentials
curl -k https://proxmox.example.com:8006/api2/json/version \
  -H "Authorization: PVEAPIToken=USER@REALM!TOKENID=TOKEN"
```

**Problem**: Cannot create VMs
```bash
# Check permissions
pveum user permissions <user>@<realm>

# Check storage
pvesm status
```

### Resource Issues

**Problem**: No resources available
```python
# Check current allocation
stats = orchestrator.get_infrastructure_stats()
print(f"Available: {stats.available_resources}/{stats.total_resources}")

# Increase max_resources
orchestrator.max_resources = 20

# Force cleanup
orchestrator.cleanup_idle_resources(max_idle_seconds=0)
```

## 📚 API Reference

See inline documentation in:
- `vera_orchestrator.py` - Core orchestration
- `vera_orchestrator_infra.py` - Infrastructure management
- `vera_orchestrator_config.py` - Configuration management

## 🤝 Integration with Vera

This orchestration system integrates seamlessly with the Vera AI system:

```python
from vera import ProactiveFocusManager
from vera_orchestrator_infra import InfrastructureOrchestrator, proactive_task

# Create orchestrator
orchestrator = InfrastructureOrchestrator(...)

# Define proactive task
@proactive_task("focus.analyze")
def analyze_focus(context: str):
    return f"Analysis of: {context}"

# Submit through proactive focus
task_id = orchestrator.submit_task("focus.analyze", context="current_conversation")
```

## 📝 License

MIT License - See LICENSE file for details

## 🙏 Acknowledgments

- Docker SDK for Python
- Proxmoxer library
- Redis for pub/sub
- Vera AI framework

## 📧 Support

For issues and questions:
- GitHub Issues: https://github.com/your-org/vera-orchestrator/issues
- Documentation: https://docs.vera.ai/orchestration
- Email: support@vera.ai
"""
Vera Infrastructure Orchestration - Usage Guide
================================================

This guide demonstrates how to use the infrastructure-aware orchestration
system with Docker and Proxmox for dynamic resource allocation.

FEATURES:
- Automatic Docker container provisioning
- Proxmox VM/LXC management
- Dynamic resource scaling
- Resource pooling and reuse
- Infrastructure monitoring
- Task-resource binding
"""

import time
import json
from vera_orchestrator_infra import (
    InfrastructureOrchestrator,
    ResourceType, ResourceSpec,
    TaskType, Priority,
    task, registry
)


# ============================================================================
# EXAMPLE 1: BASIC DOCKER ORCHESTRATION
# ============================================================================

def example_docker_basic():
    """Basic Docker container orchestration"""
    print("=" * 70)
    print("EXAMPLE 1: Basic Docker Orchestration")
    print("=" * 70)
    
    # Initialize with Docker only
    orchestrator = InfrastructureOrchestrator(
        config={TaskType.GENERAL: 2},
        enable_docker=True,
        enable_proxmox=False,
        auto_scale=True,
        max_resources=5
    )
    
    orchestrator.start()
    
    try:
        # Provision a Docker container
        print("\n1. Provisioning Docker container...")
        spec = ResourceSpec(
            cpu_cores=2.0,
            memory_mb=1024,
            disk_gb=10
        )
        
        resources = orchestrator.provision_resources(
            ResourceType.DOCKER_CONTAINER,
            spec=spec,
            count=1,
            image="python:3.11-slim",
            task_type=TaskType.GENERAL
        )
        
        print(f"   ✓ Provisioned {len(resources)} container(s)")
        for r in resources:
            print(f"     - {r.resource_id}: {r.spec.cpu_cores} cores, {r.spec.memory_mb}MB")
        
        # Execute command in container
        print("\n2. Executing command in container...")
        resource_id = resources[0].resource_id
        exit_code, output = orchestrator.docker_manager.execute_in_resource(
            resource_id,
            "python --version"
        )
        print(f"   ✓ Command output: {output.strip()}")
        
        # Get resource stats
        print("\n3. Getting resource statistics...")
        stats = orchestrator.docker_manager.get_resource_stats(resource_id)
        print(f"   ✓ CPU: {stats.get('cpu_percent', 0):.2f}%")
        print(f"   ✓ Memory: {stats.get('memory_usage_mb', 0):.2f} MB")
        
        # Get infrastructure stats
        print("\n4. Infrastructure overview...")
        infra_stats = orchestrator.get_infrastructure_stats()
        print(f"   ✓ Total Resources: {infra_stats.total_resources}")
        print(f"   ✓ Available: {infra_stats.available_resources}")
        print(f"   ✓ Total Capacity: {infra_stats.total_capacity.cpu_cores} cores, "
              f"{infra_stats.total_capacity.memory_mb}MB")
        
        # Cleanup
        print("\n5. Cleaning up...")
        for r in resources:
            orchestrator.docker_manager.deallocate_resource(r.resource_id)
        print("   ✓ Resources deallocated")
        
    finally:
        orchestrator.stop()
    
    print("\n✅ Example completed successfully\n")


# ============================================================================
# EXAMPLE 2: AUTO-SCALING DOCKER CONTAINERS
# ============================================================================

def example_docker_autoscale():
    """Demonstrate automatic scaling of Docker containers"""
    print("=" * 70)
    print("EXAMPLE 2: Auto-Scaling Docker Containers")
    print("=" * 70)
    
    # Register a task
    @task("compute.fibonacci", task_type=TaskType.GENERAL, priority=Priority.NORMAL)
    def fibonacci(n: int):
        """Compute fibonacci number"""
        if n <= 1:
            return n
        a, b = 0, 1
        for _ in range(n - 1):
            a, b = b, a + b
        return b
    
    # Initialize with auto-scaling
    orchestrator = InfrastructureOrchestrator(
        config={TaskType.GENERAL: 0},  # Start with 0 workers
        enable_docker=True,
        auto_scale=True,
        max_resources=3
    )
    
    orchestrator.start()
    
    try:
        print("\n1. Initial state (no containers)...")
        stats = orchestrator.get_infrastructure_stats()
        print(f"   ✓ Containers: {stats.containers_created}")
        
        print("\n2. Submitting tasks (will trigger auto-provisioning)...")
        task_ids = []
        for i in range(3):
            task_id = orchestrator.submit_task("compute.fibonacci", n=30 + i)
            task_ids.append(task_id)
            print(f"   ✓ Submitted task {i+1}: {task_id[:8]}...")
        
        print("\n3. Waiting for auto-provisioning...")
        time.sleep(5)
        
        stats = orchestrator.get_infrastructure_stats()
        print(f"   ✓ Auto-provisioned containers: {stats.containers_created}")
        print(f"   ✓ Available: {stats.available_resources}")
        print(f"   ✓ Allocated: {stats.allocated_resources}")
        
        print("\n4. Waiting for task completion...")
        results = []
        for task_id in task_ids:
            result = orchestrator.wait_for_result(task_id, timeout=30)
            if result:
                results.append(result.result)
                print(f"   ✓ Task {task_id[:8]}... completed: {result.result}")
        
        print("\n5. Final infrastructure state...")
        stats = orchestrator.get_infrastructure_stats()
        print(f"   ✓ Total tasks executed: {stats.tasks_executed}")
        print(f"   ✓ Resources available: {stats.available_resources}")
        
    finally:
        orchestrator.stop()
    
    print("\n✅ Example completed successfully\n")


# ============================================================================
# EXAMPLE 3: MIXED DOCKER + PROXMOX ORCHESTRATION
# ============================================================================

def example_mixed_infrastructure():
    """
    Demonstrate orchestration across Docker and Proxmox.
    NOTE: Requires Proxmox setup and configuration.
    """
    print("=" * 70)
    print("EXAMPLE 3: Mixed Infrastructure (Docker + Proxmox)")
    print("=" * 70)
    
    # Proxmox configuration (update with your details)
    proxmox_config = {
        "host": "proxmox.example.com",
        "user": "root@pam",
        "password": "your_password",  # Or use token
        # "token_name": "your_token_name",
        # "token_value": "your_token_value",
        "verify_ssl": False
    }
    
    # Initialize with both Docker and Proxmox
    orchestrator = InfrastructureOrchestrator(
        config={
            TaskType.GENERAL: 2,
            TaskType.ML_MODEL: 1
        },
        enable_docker=True,
        enable_proxmox=True,
        proxmox_config=proxmox_config,
        auto_scale=True,
        max_resources=10
    )
    
    orchestrator.start()
    
    try:
        print("\n1. Provisioning Docker containers for general tasks...")
        docker_spec = ResourceSpec(cpu_cores=1, memory_mb=512)
        docker_resources = orchestrator.provision_resources(
            ResourceType.DOCKER_CONTAINER,
            spec=docker_spec,
            count=2,
            task_type=TaskType.GENERAL
        )
        print(f"   ✓ Provisioned {len(docker_resources)} Docker containers")
        
        print("\n2. Provisioning Proxmox VM for ML workload...")
        proxmox_spec = ResourceSpec(
            cpu_cores=4,
            memory_mb=8192,
            disk_gb=50,
            gpu_count=1
        )
        
        # Get first available Proxmox node
        nodes = orchestrator.proxmox_manager.proxmox.nodes.get()
        node_name = nodes[0]['node']
        
        proxmox_resources = orchestrator.provision_resources(
            ResourceType.PROXMOX_VM,
            spec=proxmox_spec,
            count=1,
            node=node_name,
            template=None  # Create from scratch
        )
        print(f"   ✓ Provisioned {len(proxmox_resources)} Proxmox VM")
        
        print("\n3. Infrastructure overview...")
        stats = orchestrator.get_infrastructure_stats()
        print(f"   ✓ Total Resources: {stats.total_resources}")
        print(f"   ✓ Docker Containers: {stats.containers_created}")
        print(f"   ✓ Proxmox VMs: {stats.vms_created}")
        print(f"   ✓ Total CPU Cores: {stats.total_capacity.cpu_cores}")
        print(f"   ✓ Total Memory: {stats.total_capacity.memory_mb} MB")
        print(f"   ✓ Total GPUs: {stats.total_capacity.gpu_count}")
        
        print("\n4. Resource statistics...")
        for manager in orchestrator.resource_managers.values():
            for resource in manager.list_resources():
                resource_stats = manager.get_resource_stats(resource.resource_id)
                print(f"\n   {resource.resource_id}:")
                print(f"     Type: {resource.resource_type.value}")
                print(f"     Status: {resource.status.name}")
                print(f"     CPU: {resource_stats.get('cpu_percent', 0):.2f}%")
                print(f"     Memory: {resource_stats.get('memory_usage_mb', 0):.2f} MB")
        
        print("\n5. Cleaning up...")
        # Cleanup Docker
        for r in docker_resources:
            orchestrator.docker_manager.deallocate_resource(r.resource_id)
        
        # Cleanup Proxmox (careful - this deletes VMs!)
        for r in proxmox_resources:
            orchestrator.proxmox_manager.deallocate_resource(r.resource_id)
        
        print("   ✓ All resources deallocated")
        
    finally:
        orchestrator.stop()
    
    print("\n✅ Example completed successfully\n")


# ============================================================================
# EXAMPLE 4: RESOURCE POOLING AND REUSE
# ============================================================================

def example_resource_pooling():
    """Demonstrate resource pooling and reuse across multiple tasks"""
    print("=" * 70)
    print("EXAMPLE 4: Resource Pooling and Reuse")
    print("=" * 70)
    
    @task("data.process", task_type=TaskType.GENERAL)
    def process_data(data: str):
        """Process some data"""
        import time
        time.sleep(1)
        return f"Processed: {data}"
    
    orchestrator = InfrastructureOrchestrator(
        config={TaskType.GENERAL: 0},
        enable_docker=True,
        auto_scale=True,
        max_resources=2  # Limit to 2 containers
    )
    
    orchestrator.start()
    
    try:
        print("\n1. Pre-provisioning resource pool...")
        spec = ResourceSpec(cpu_cores=1, memory_mb=512)
        resources = orchestrator.provision_resources(
            ResourceType.DOCKER_CONTAINER,
            spec=spec,
            count=2,
            task_type=TaskType.GENERAL
        )
        print(f"   ✓ Provisioned pool of {len(resources)} containers")
        
        print("\n2. Submitting 10 tasks (will reuse 2 containers)...")
        task_ids = []
        for i in range(10):
            task_id = orchestrator.submit_task("data.process", data=f"batch_{i}")
            task_ids.append(task_id)
        
        print("\n3. Monitoring resource allocation...")
        completed = 0
        while completed < len(task_ids):
            time.sleep(2)
            
            stats = orchestrator.get_infrastructure_stats()
            new_completed = stats.tasks_executed
            if new_completed > completed:
                completed = new_completed
                print(f"   ✓ Progress: {completed}/{len(task_ids)} tasks completed")
                print(f"     - Available: {stats.available_resources}")
                print(f"     - In Use: {stats.in_use_resources}")
        
        print("\n4. Resource reuse statistics...")
        for resource in resources:
            print(f"   {resource.resource_id}:")
            print(f"     - Total tasks executed: {resource.total_tasks}")
            print(f"     - Currently available: {resource.status.name}")
        
    finally:
        orchestrator.stop()
    
    print("\n✅ Example completed successfully\n")


# ============================================================================
# EXAMPLE 5: GPU-ACCELERATED WORKLOADS
# ============================================================================

def example_gpu_workloads():
    """Demonstrate GPU resource allocation for ML workloads"""
    print("=" * 70)
    print("EXAMPLE 5: GPU-Accelerated Workloads")
    print("=" * 70)
    
    @task(
        "ml.train_model",
        task_type=TaskType.ML_MODEL,
        priority=Priority.HIGH,
        requires_gpu=True,
        requires_cpu_cores=4,
        memory_mb=8192
    )
    def train_model(model_name: str, epochs: int):
        """Train a machine learning model (mock)"""
        import time
        print(f"Training {model_name} for {epochs} epochs...")
        time.sleep(2)
        return f"Model {model_name} trained for {epochs} epochs"
    
    orchestrator = InfrastructureOrchestrator(
        config={TaskType.ML_MODEL: 0},
        enable_docker=True,
        auto_scale=True,
        max_resources=2
    )
    
    orchestrator.start()
    
    try:
        print("\n1. Provisioning GPU-enabled container...")
        gpu_spec = ResourceSpec(
            cpu_cores=4,
            memory_mb=8192,
            gpu_count=1,
            gpu_memory_mb=8192
        )
        
        resources = orchestrator.provision_resources(
            ResourceType.DOCKER_CONTAINER,
            spec=gpu_spec,
            count=1,
            image="pytorch/pytorch:latest",
            task_type=TaskType.ML_MODEL
        )
        
        if resources:
            print(f"   ✓ Provisioned GPU container: {resources[0].resource_id}")
            print(f"     - GPUs: {resources[0].spec.gpu_count}")
            print(f"     - GPU Memory: {resources[0].spec.gpu_memory_mb} MB")
        
        print("\n2. Submitting GPU task...")
        task_id = orchestrator.submit_task(
            "ml.train_model",
            model_name="ResNet50",
            epochs=10
        )
        
        print("\n3. Waiting for task completion...")
        result = orchestrator.wait_for_result(task_id, timeout=30)
        if result:
            print(f"   ✓ Result: {result.result}")
        
        print("\n4. Resource statistics...")
        if resources:
            stats = orchestrator.docker_manager.get_resource_stats(resources[0].resource_id)
            print(f"   CPU: {stats.get('cpu_percent', 0):.2f}%")
            print(f"   Memory: {stats.get('memory_usage_mb', 0):.2f} MB")
        
    finally:
        orchestrator.stop()
    
    print("\n✅ Example completed successfully\n")


# ============================================================================
# EXAMPLE 6: MONITORING AND MAINTENANCE
# ============================================================================

def example_monitoring():
    """Demonstrate infrastructure monitoring and maintenance"""
    print("=" * 70)
    print("EXAMPLE 6: Infrastructure Monitoring and Maintenance")
    print("=" * 70)
    
    orchestrator = InfrastructureOrchestrator(
        config={TaskType.GENERAL: 0},
        enable_docker=True,
        auto_scale=True,
        max_resources=5
    )
    
    orchestrator.start()
    
    # Subscribe to events
    events_received = []
    
    def event_logger(event_data):
        events_received.append(event_data)
        print(f"   📡 Event: {json.dumps(event_data, indent=6)}")
    
    orchestrator.event_bus.subscribe("resource.provisioned", event_logger)
    orchestrator.event_bus.subscribe("resource.allocated", event_logger)
    orchestrator.event_bus.subscribe("resource.released", event_logger)
    orchestrator.event_bus.subscribe("resource.deallocated", event_logger)
    
    try:
        print("\n1. Provisioning resources (monitoring events)...")
        spec = ResourceSpec(cpu_cores=1, memory_mb=512)
        resources = orchestrator.provision_resources(
            ResourceType.DOCKER_CONTAINER,
            spec=spec,
            count=3
        )
        time.sleep(1)
        
        print("\n2. Simulating task execution...")
        
        @task("dummy.task", task_type=TaskType.GENERAL)
        def dummy_task():
            time.sleep(1)
            return "done"
        
        task_id = orchestrator.submit_task("dummy.task")
        orchestrator.wait_for_result(task_id, timeout=10)
        time.sleep(1)
        
        print("\n3. Periodic monitoring...")
        for i in range(3):
            print(f"\n   --- Monitoring Cycle {i+1} ---")
            stats = orchestrator.get_infrastructure_stats()
            print(f"   Total Resources: {stats.total_resources}")
            print(f"   Available: {stats.available_resources}")
            print(f"   Tasks Executed: {stats.tasks_executed}")
            
            # Check each resource
            for manager in orchestrator.resource_managers.values():
                for resource in manager.list_resources():
                    resource_stats = manager.get_resource_stats(resource.resource_id)
                    print(f"\n   {resource.resource_id}:")
                    print(f"     Status: {resource.status.name}")
                    print(f"     CPU: {resource_stats.get('cpu_percent', 0):.2f}%")
                    print(f"     Memory: {resource_stats.get('memory_usage_mb', 0):.2f} MB")
                    print(f"     Tasks: {resource.total_tasks}")
            
            time.sleep(2)
        
        print("\n4. Cleanup idle resources...")
        orchestrator.cleanup_idle_resources(max_idle_seconds=5)
        time.sleep(2)
        
        final_stats = orchestrator.get_infrastructure_stats()
        print(f"   ✓ Remaining resources: {final_stats.total_resources}")
        
        print(f"\n5. Events Summary...")
        print(f"   Total events captured: {len(events_received)}")
        
    finally:
        orchestrator.stop()
    
    print("\n✅ Example completed successfully\n")


# ============================================================================
# MAIN MENU
# ============================================================================

def main():
    """Run example demonstrations"""
    print("\n" + "=" * 70)
    print("VERA INFRASTRUCTURE ORCHESTRATION - EXAMPLES")
    print("=" * 70)
    print("\nAvailable examples:")
    print("  1. Basic Docker Orchestration")
    print("  2. Auto-Scaling Docker Containers")
    print("  3. Mixed Infrastructure (Docker + Proxmox) - Requires Proxmox")
    print("  4. Resource Pooling and Reuse")
    print("  5. GPU-Accelerated Workloads - Requires GPU")
    print("  6. Monitoring and Maintenance")
    print("  0. Run All Examples (except 3 & 5)")
    
    choice = input("\nSelect example (0-6): ").strip()
    
    examples = {
        "1": example_docker_basic,
        "2": example_docker_autoscale,
        "3": example_mixed_infrastructure,
        "4": example_resource_pooling,
        "5": example_gpu_workloads,
        "6": example_monitoring,
    }
    
    if choice == "0":
        # Run safe examples
        for key in ["1", "2", "4", "6"]:
            examples[key]()
            time.sleep(2)
    elif choice in examples:
        examples[choice]()
    else:
        print("Invalid choice!")


if __name__ == "__main__":
    main()