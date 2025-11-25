"""
Vera Task Orchestration System - Infrastructure Extension
==========================================================
Extends the base orchestration system with Docker and Proxmox
resource allocation and control.

NEW FEATURES:
- Docker container lifecycle management
- Docker resource allocation (CPU, memory, GPU)
- Proxmox VM/LXC management
- Proxmox resource allocation
- Dynamic worker provisioning
- Infrastructure-aware task scheduling
- Resource monitoring and optimization

Architecture:
- ResourceManager: Abstract resource management interface
- DockerResourceManager: Docker container orchestration
- ProxmoxResourceManager: Proxmox VM/LXC orchestration
- InfrastructureOrchestrator: Enhanced orchestrator with infra support
"""

import asyncio
import docker
import proxmoxer
import json
import time
import logging
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
from abc import ABC, abstractmethod
import threading
import requests
from collections import defaultdict

# Import base orchestration components
from vera_orchestrator import (
    TaskType, Priority, TaskStatus, TaskMetadata, TaskResult,
    Orchestrator, registry, WorkerPool, Worker, TaskQueue, EventBus
)


# ============================================================================
# INFRASTRUCTURE ENUMS & DATA CLASSES
# ============================================================================

class ResourceType(Enum):
    """Types of computational resources"""
    DOCKER_CONTAINER = "docker_container"
    PROXMOX_VM = "proxmox_vm"
    PROXMOX_LXC = "proxmox_lxc"
    BARE_METAL = "bare_metal"


class ResourceStatus(Enum):
    """Status of a resource"""
    AVAILABLE = auto()
    ALLOCATED = auto()
    IN_USE = auto()
    STOPPING = auto()
    STOPPED = auto()
    ERROR = auto()


@dataclass
class ResourceSpec:
    """Specification for computational resources"""
    cpu_cores: float = 1.0  # Can be fractional for containers
    memory_mb: int = 512
    disk_gb: int = 10
    gpu_count: int = 0
    gpu_memory_mb: int = 0
    network_bandwidth_mbps: int = 100
    
    def __le__(self, other: 'ResourceSpec') -> bool:
        """Check if this spec fits within another"""
        return (
            self.cpu_cores <= other.cpu_cores and
            self.memory_mb <= other.memory_mb and
            self.disk_gb <= other.disk_gb and
            self.gpu_count <= other.gpu_count and
            self.gpu_memory_mb <= other.gpu_memory_mb
        )


@dataclass
class ResourceInstance:
    """A computational resource instance (container, VM, etc.)"""
    resource_id: str
    resource_type: ResourceType
    status: ResourceStatus
    spec: ResourceSpec
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Docker-specific
    container_id: Optional[str] = None
    image: Optional[str] = None
    
    # Proxmox-specific
    vmid: Optional[int] = None
    node: Optional[str] = None
    
    # Usage tracking
    current_task_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    total_tasks: int = 0


@dataclass
class InfrastructureStats:
    """Statistics about infrastructure resources"""
    total_resources: int = 0
    available_resources: int = 0
    allocated_resources: int = 0
    in_use_resources: int = 0
    total_capacity: ResourceSpec = field(default_factory=ResourceSpec)
    available_capacity: ResourceSpec = field(default_factory=ResourceSpec)
    tasks_executed: int = 0
    containers_created: int = 0
    vms_created: int = 0


# ============================================================================
# RESOURCE MANAGER INTERFACE
# ============================================================================

class ResourceManager(ABC):
    """Abstract base class for resource managers"""
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.resources: Dict[str, ResourceInstance] = {}
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def provision_resource(self, spec: ResourceSpec, **kwargs) -> ResourceInstance:
        """Provision a new resource"""
        pass
    
    @abstractmethod
    def deallocate_resource(self, resource_id: str):
        """Deallocate and cleanup a resource"""
        pass
    
    @abstractmethod
    def get_resource_stats(self, resource_id: str) -> Dict[str, Any]:
        """Get runtime statistics for a resource"""
        pass
    
    @abstractmethod
    def execute_in_resource(self, resource_id: str, command: str, **kwargs) -> Any:
        """Execute a command in the resource"""
        pass
    
    def list_resources(self, status: Optional[ResourceStatus] = None) -> List[ResourceInstance]:
        """List all resources, optionally filtered by status"""
        resources = list(self.resources.values())
        if status:
            resources = [r for r in resources if r.status == status]
        return resources
    
    def get_resource(self, resource_id: str) -> Optional[ResourceInstance]:
        """Get a specific resource"""
        return self.resources.get(resource_id)
    
    def update_resource_status(self, resource_id: str, status: ResourceStatus):
        """Update resource status and broadcast event"""
        if resource_id in self.resources:
            old_status = self.resources[resource_id].status
            self.resources[resource_id].status = status
            
            self.event_bus.publish("resource.status_changed", {
                "resource_id": resource_id,
                "old_status": old_status.name,
                "new_status": status.name,
                "resource_type": self.resources[resource_id].resource_type.value
            })


# ============================================================================
# DOCKER RESOURCE MANAGER
# ============================================================================

class DockerResourceManager(ResourceManager):
    """
    Manages Docker containers as computational resources.
    Handles container lifecycle, resource allocation, and monitoring.
    """
    
    def __init__(self, event_bus: EventBus, docker_url: str = "unix://var/run/docker.sock"):
        super().__init__(event_bus)
        self.docker_client = docker.DockerClient(base_url=docker_url)
        self.containers: Dict[str, docker.models.containers.Container] = {}
        self.logger.info(f"Connected to Docker: {docker_url}")
        
        # Default images for different task types
        self.default_images = {
            TaskType.LLM: "python:3.11-slim",
            TaskType.WHISPER: "python:3.11-slim",
            TaskType.TOOL: "python:3.11-slim",
            TaskType.ML_MODEL: "pytorch/pytorch:latest",
            TaskType.BACKGROUND: "python:3.11-slim",
            TaskType.GENERAL: "python:3.11-slim"
        }
    
    def provision_resource(
        self,
        spec: ResourceSpec,
        image: Optional[str] = None,
        task_type: Optional[TaskType] = None,
        environment: Optional[Dict[str, str]] = None,
        volumes: Optional[Dict[str, Dict[str, str]]] = None,
        network_mode: str = "bridge",
        **kwargs
    ) -> ResourceInstance:
        """
        Provision a Docker container.
        
        Args:
            spec: Resource specifications
            image: Docker image (defaults based on task_type)
            task_type: Type of task this container will run
            environment: Environment variables
            volumes: Volume mappings
            network_mode: Docker network mode
        """
        # Select image
        if not image and task_type:
            image = self.default_images.get(task_type, "python:3.11-slim")
        elif not image:
            image = "python:3.11-slim"
        
        # Build container configuration
        container_config = {
            "image": image,
            "detach": True,
            "environment": environment or {},
            "volumes": volumes or {},
            "network_mode": network_mode,
            "stdin_open": True,
            "tty": True,
            **kwargs
        }
        
        # Resource limits
        container_config["cpu_quota"] = int(spec.cpu_cores * 100000)  # 100000 = 1 core
        container_config["cpu_period"] = 100000
        container_config["mem_limit"] = f"{spec.memory_mb}m"
        
        # GPU support
        if spec.gpu_count > 0:
            container_config["device_requests"] = [
                docker.types.DeviceRequest(
                    count=spec.gpu_count,
                    capabilities=[["gpu"]]
                )
            ]
        
        try:
            # Pull image if not available
            try:
                self.docker_client.images.get(image)
            except docker.errors.ImageNotFound:
                self.logger.info(f"Pulling image: {image}")
                self.docker_client.images.pull(image)
            
            # Create and start container
            container = self.docker_client.containers.run(**container_config)
            
            # Create resource instance
            resource = ResourceInstance(
                resource_id=f"docker-{container.short_id}",
                resource_type=ResourceType.DOCKER_CONTAINER,
                status=ResourceStatus.AVAILABLE,
                spec=spec,
                container_id=container.id,
                image=image,
                metadata={
                    "task_type": task_type.value if task_type else None,
                    "network_mode": network_mode
                }
            )
            
            # Track
            self.resources[resource.resource_id] = resource
            self.containers[resource.resource_id] = container
            
            self.logger.info(f"Provisioned Docker container: {resource.resource_id}")
            
            # Broadcast event
            self.event_bus.publish("resource.provisioned", {
                "resource_id": resource.resource_id,
                "resource_type": ResourceType.DOCKER_CONTAINER.value,
                "spec": asdict(spec),
                "image": image
            })
            
            return resource
            
        except Exception as e:
            self.logger.error(f"Failed to provision Docker container: {e}")
            raise
    
    def deallocate_resource(self, resource_id: str):
        """Stop and remove a Docker container"""
        if resource_id not in self.resources:
            raise ValueError(f"Resource not found: {resource_id}")
        
        resource = self.resources[resource_id]
        container = self.containers.get(resource_id)
        
        if not container:
            self.logger.warning(f"Container not found for resource: {resource_id}")
            del self.resources[resource_id]
            return
        
        try:
            # Update status
            self.update_resource_status(resource_id, ResourceStatus.STOPPING)
            
            # Stop and remove container
            container.stop(timeout=10)
            container.remove()
            
            # Cleanup
            del self.resources[resource_id]
            del self.containers[resource_id]
            
            self.logger.info(f"Deallocated Docker container: {resource_id}")
            
            # Broadcast event
            self.event_bus.publish("resource.deallocated", {
                "resource_id": resource_id,
                "resource_type": ResourceType.DOCKER_CONTAINER.value
            })
            
        except Exception as e:
            self.logger.error(f"Failed to deallocate container {resource_id}: {e}")
            resource.status = ResourceStatus.ERROR
            raise
    
    def get_resource_stats(self, resource_id: str) -> Dict[str, Any]:
        """Get Docker container statistics"""
        container = self.containers.get(resource_id)
        if not container:
            return {}
        
        try:
            container.reload()
            stats = container.stats(stream=False)
            
            # Calculate CPU usage
            cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - \
                       stats["precpu_stats"]["cpu_usage"]["total_usage"]
            system_delta = stats["cpu_stats"]["system_cpu_usage"] - \
                          stats["precpu_stats"]["system_cpu_usage"]
            cpu_percent = (cpu_delta / system_delta) * 100.0 if system_delta > 0 else 0.0
            
            # Memory usage
            memory_usage = stats["memory_stats"]["usage"]
            memory_limit = stats["memory_stats"]["limit"]
            memory_percent = (memory_usage / memory_limit) * 100.0
            
            return {
                "status": container.status,
                "cpu_percent": cpu_percent,
                "memory_usage_mb": memory_usage / (1024 * 1024),
                "memory_limit_mb": memory_limit / (1024 * 1024),
                "memory_percent": memory_percent,
                "network_rx_bytes": stats["networks"]["eth0"]["rx_bytes"] if "eth0" in stats["networks"] else 0,
                "network_tx_bytes": stats["networks"]["eth0"]["tx_bytes"] if "eth0" in stats["networks"] else 0,
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get stats for {resource_id}: {e}")
            return {}
    
    def execute_in_resource(
        self,
        resource_id: str,
        command: Union[str, List[str]],
        workdir: Optional[str] = None,
        environment: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> Tuple[int, str]:
        """
        Execute a command in a Docker container.
        
        Returns:
            (exit_code, output)
        """
        container = self.containers.get(resource_id)
        if not container:
            raise ValueError(f"Container not found: {resource_id}")
        
        try:
            exec_result = container.exec_run(
                cmd=command,
                workdir=workdir,
                environment=environment,
                **kwargs
            )
            
            return exec_result.exit_code, exec_result.output.decode('utf-8')
            
        except Exception as e:
            self.logger.error(f"Failed to execute in {resource_id}: {e}")
            raise
    
    def cleanup_unused_resources(self, max_idle_seconds: int = 300):
        """Remove containers that haven't been used recently"""
        now = time.time()
        to_remove = []
        
        for resource_id, resource in self.resources.items():
            if resource.status == ResourceStatus.AVAILABLE:
                idle_time = now - resource.last_used
                if idle_time > max_idle_seconds:
                    to_remove.append(resource_id)
        
        for resource_id in to_remove:
            try:
                self.deallocate_resource(resource_id)
                self.logger.info(f"Cleaned up idle resource: {resource_id}")
            except Exception as e:
                self.logger.error(f"Failed to cleanup {resource_id}: {e}")


# ============================================================================
# PROXMOX RESOURCE MANAGER
# ============================================================================

class ProxmoxResourceManager(ResourceManager):
    """
    Manages Proxmox VMs and LXC containers as computational resources.
    Handles VM/LXC lifecycle, resource allocation, and monitoring.
    """
    
    def __init__(
        self,
        event_bus: EventBus,
        host: str,
        user: str,
        password: Optional[str] = None,
        token_name: Optional[str] = None,
        token_value: Optional[str] = None,
        verify_ssl: bool = True
    ):
        super().__init__(event_bus)
        
        # Connect to Proxmox
        if token_name and token_value:
            self.proxmox = proxmoxer.ProxmoxAPI(
                host,
                user=user,
                token_name=token_name,
                token_value=token_value,
                verify_ssl=verify_ssl
            )
        else:
            self.proxmox = proxmoxer.ProxmoxAPI(
                host,
                user=user,
                password=password,
                verify_ssl=verify_ssl
            )
        
        self.host = host
        self.logger.info(f"Connected to Proxmox: {host}")
        
        # Track VMs and containers
        self.vms: Dict[str, int] = {}  # resource_id -> vmid
        self.next_vmid = 100  # Starting VMID for auto-allocation
    
    def _get_next_vmid(self) -> int:
        """Get next available VMID"""
        # Check existing VMs across all nodes
        used_vmids = set()
        for node in self.proxmox.nodes.get():
            node_name = node['node']
            for vm in self.proxmox.nodes(node_name).qemu.get():
                used_vmids.add(vm['vmid'])
            for lxc in self.proxmox.nodes(node_name).lxc.get():
                used_vmids.add(lxc['vmid'])
        
        # Find next available
        while self.next_vmid in used_vmids:
            self.next_vmid += 1
        
        vmid = self.next_vmid
        self.next_vmid += 1
        return vmid
    
    def provision_resource(
        self,
        spec: ResourceSpec,
        node: str,
        resource_type: ResourceType = ResourceType.PROXMOX_VM,
        template: Optional[str] = None,
        storage: str = "local-lvm",
        network_bridge: str = "vmbr0",
        **kwargs
    ) -> ResourceInstance:
        """
        Provision a Proxmox VM or LXC container.
        
        Args:
            spec: Resource specifications
            node: Proxmox node name
            resource_type: VM or LXC
            template: Template to clone from
            storage: Storage location
            network_bridge: Network bridge
        """
        vmid = self._get_next_vmid()
        
        try:
            if resource_type == ResourceType.PROXMOX_VM:
                # Create VM
                config = {
                    "vmid": vmid,
                    "cores": int(spec.cpu_cores),
                    "memory": spec.memory_mb,
                    "storage": storage,
                    "net0": f"virtio,bridge={network_bridge}",
                    **kwargs
                }
                
                if template:
                    # Clone from template
                    self.proxmox.nodes(node).qemu(template).clone.post(**config)
                else:
                    # Create new VM
                    config["ostype"] = "l26"  # Linux 2.6+
                    self.proxmox.nodes(node).qemu.post(**config)
                
                # Start VM
                self.proxmox.nodes(node).qemu(vmid).status.start.post()
                
            elif resource_type == ResourceType.PROXMOX_LXC:
                # Create LXC container
                config = {
                    "vmid": vmid,
                    "cores": int(spec.cpu_cores),
                    "memory": spec.memory_mb,
                    "rootfs": f"{storage}:{spec.disk_gb}",
                    "net0": f"name=eth0,bridge={network_bridge},ip=dhcp",
                    "ostemplate": template or "local:vztmpl/ubuntu-22.04-standard_22.04-1_amd64.tar.zst",
                    **kwargs
                }
                
                self.proxmox.nodes(node).lxc.post(**config)
                
                # Start container
                self.proxmox.nodes(node).lxc(vmid).status.start.post()
            
            else:
                raise ValueError(f"Unsupported resource type: {resource_type}")
            
            # Create resource instance
            resource = ResourceInstance(
                resource_id=f"proxmox-{node}-{vmid}",
                resource_type=resource_type,
                status=ResourceStatus.AVAILABLE,
                spec=spec,
                vmid=vmid,
                node=node,
                metadata={
                    "storage": storage,
                    "network_bridge": network_bridge,
                    "template": template
                }
            )
            
            # Track
            self.resources[resource.resource_id] = resource
            self.vms[resource.resource_id] = vmid
            
            self.logger.info(f"Provisioned Proxmox resource: {resource.resource_id}")
            
            # Broadcast event
            self.event_bus.publish("resource.provisioned", {
                "resource_id": resource.resource_id,
                "resource_type": resource_type.value,
                "spec": asdict(spec),
                "vmid": vmid,
                "node": node
            })
            
            return resource
            
        except Exception as e:
            self.logger.error(f"Failed to provision Proxmox resource: {e}")
            raise
    
    def deallocate_resource(self, resource_id: str):
        """Stop and delete a Proxmox VM/LXC"""
        if resource_id not in self.resources:
            raise ValueError(f"Resource not found: {resource_id}")
        
        resource = self.resources[resource_id]
        vmid = resource.vmid
        node = resource.node
        
        try:
            # Update status
            self.update_resource_status(resource_id, ResourceStatus.STOPPING)
            
            if resource.resource_type == ResourceType.PROXMOX_VM:
                # Stop and delete VM
                try:
                    self.proxmox.nodes(node).qemu(vmid).status.stop.post()
                    time.sleep(5)  # Wait for shutdown
                except:
                    pass
                
                self.proxmox.nodes(node).qemu(vmid).delete()
                
            elif resource.resource_type == ResourceType.PROXMOX_LXC:
                # Stop and delete LXC
                try:
                    self.proxmox.nodes(node).lxc(vmid).status.stop.post()
                    time.sleep(3)
                except:
                    pass
                
                self.proxmox.nodes(node).lxc(vmid).delete()
            
            # Cleanup
            del self.resources[resource_id]
            del self.vms[resource_id]
            
            self.logger.info(f"Deallocated Proxmox resource: {resource_id}")
            
            # Broadcast event
            self.event_bus.publish("resource.deallocated", {
                "resource_id": resource_id,
                "resource_type": resource.resource_type.value
            })
            
        except Exception as e:
            self.logger.error(f"Failed to deallocate resource {resource_id}: {e}")
            resource.status = ResourceStatus.ERROR
            raise
    
    def get_resource_stats(self, resource_id: str) -> Dict[str, Any]:
        """Get Proxmox VM/LXC statistics"""
        if resource_id not in self.resources:
            return {}
        
        resource = self.resources[resource_id]
        vmid = resource.vmid
        node = resource.node
        
        try:
            if resource.resource_type == ResourceType.PROXMOX_VM:
                stats = self.proxmox.nodes(node).qemu(vmid).status.current.get()
            else:
                stats = self.proxmox.nodes(node).lxc(vmid).status.current.get()
            
            return {
                "status": stats.get("status"),
                "cpu_percent": stats.get("cpu", 0) * 100,
                "memory_usage_mb": stats.get("mem", 0) / (1024 * 1024),
                "memory_limit_mb": stats.get("maxmem", 0) / (1024 * 1024),
                "disk_usage_bytes": stats.get("disk", 0),
                "disk_limit_bytes": stats.get("maxdisk", 0),
                "uptime": stats.get("uptime", 0)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get stats for {resource_id}: {e}")
            return {}
    
    def execute_in_resource(
        self,
        resource_id: str,
        command: str,
        **kwargs
    ) -> Tuple[int, str]:
        """
        Execute a command in a Proxmox VM/LXC.
        Note: Requires qemu-guest-agent for VMs
        """
        if resource_id not in self.resources:
            raise ValueError(f"Resource not found: {resource_id}")
        
        resource = self.resources[resource_id]
        vmid = resource.vmid
        node = resource.node
        
        try:
            if resource.resource_type == ResourceType.PROXMOX_LXC:
                # Execute in LXC
                result = self.proxmox.nodes(node).lxc(vmid).exec.post(
                    command=command
                )
                return 0, result
            else:
                # Execute in VM (requires guest agent)
                result = self.proxmox.nodes(node).qemu(vmid).agent.exec.post(
                    command=command.split()
                )
                return 0, str(result)
                
        except Exception as e:
            self.logger.error(f"Failed to execute in {resource_id}: {e}")
            raise


# ============================================================================
# INFRASTRUCTURE-AWARE ORCHESTRATOR
# ============================================================================

class InfrastructureOrchestrator(Orchestrator):
    """
    Enhanced orchestrator with infrastructure resource management.
    Automatically provisions and manages Docker/Proxmox resources for tasks.
    """
    
    def __init__(
        self,
        config: Optional[Dict[TaskType, int]] = None,
        redis_url: Optional[str] = None,
        cpu_threshold: float = 85.0,
        enable_docker: bool = True,
        enable_proxmox: bool = False,
        docker_url: str = "unix://var/run/docker.sock",
        proxmox_config: Optional[Dict[str, Any]] = None,
        auto_scale: bool = True,
        max_resources: int = 10
    ):
        """
        Initialize infrastructure-aware orchestrator.
        
        Args:
            enable_docker: Enable Docker resource management
            enable_proxmox: Enable Proxmox resource management
            docker_url: Docker daemon URL
            proxmox_config: Proxmox connection config
            auto_scale: Automatically provision resources as needed
            max_resources: Maximum number of resources to provision
        """
        super().__init__(config, redis_url, cpu_threshold)
        
        self.auto_scale = auto_scale
        self.max_resources = max_resources
        self.resource_managers: Dict[ResourceType, ResourceManager] = {}
        
        # Initialize Docker manager
        if enable_docker:
            try:
                self.docker_manager = DockerResourceManager(self.event_bus, docker_url)
                self.resource_managers[ResourceType.DOCKER_CONTAINER] = self.docker_manager
                self.logger.info("Docker resource manager initialized")
            except Exception as e:
                self.logger.warning(f"Failed to initialize Docker manager: {e}")
        
        # Initialize Proxmox manager
        if enable_proxmox and proxmox_config:
            try:
                self.proxmox_manager = ProxmoxResourceManager(self.event_bus, **proxmox_config)
                self.resource_managers[ResourceType.PROXMOX_VM] = self.proxmox_manager
                self.resource_managers[ResourceType.PROXMOX_LXC] = self.proxmox_manager
                self.logger.info("Proxmox resource manager initialized")
            except Exception as e:
                self.logger.warning(f"Failed to initialize Proxmox manager: {e}")
        
        # Resource allocation tracking
        self.task_resources: Dict[str, str] = {}  # task_id -> resource_id
        self.resource_allocation_lock = threading.Lock()
        
        # Subscribe to task events for resource management
        self.event_bus.subscribe("task.queued", self._on_task_queued)
        self.event_bus.subscribe("task.completed", self._on_task_completed_infra)
        self.event_bus.subscribe("task.failed", self._on_task_failed_infra)
    
    def provision_resources(
        self,
        resource_type: ResourceType,
        spec: ResourceSpec,
        count: int = 1,
        **kwargs
    ) -> List[ResourceInstance]:
        """Provision multiple resources"""
        manager = self.resource_managers.get(resource_type)
        if not manager:
            raise ValueError(f"No manager for resource type: {resource_type}")
        
        resources = []
        for i in range(count):
            try:
                resource = manager.provision_resource(spec, **kwargs)
                resources.append(resource)
            except Exception as e:
                self.logger.error(f"Failed to provision resource {i+1}/{count}: {e}")
        
        return resources
    
    def allocate_resource_for_task(
        self,
        task_id: str,
        task_metadata: TaskMetadata,
        preferred_type: ResourceType = ResourceType.DOCKER_CONTAINER
    ) -> Optional[ResourceInstance]:
        """
        Allocate a resource for a task.
        If no suitable resource exists and auto_scale is enabled, provision one.
        """
        with self.resource_allocation_lock:
            # Check if we have a suitable resource
            manager = self.resource_managers.get(preferred_type)
            if not manager:
                self.logger.warning(f"No manager for resource type: {preferred_type}")
                return None
            
            # Build required spec from task metadata
            required_spec = ResourceSpec(
                cpu_cores=task_metadata.requires_cpu_cores,
                memory_mb=task_metadata.memory_mb,
                gpu_count=1 if task_metadata.requires_gpu else 0
            )
            
            # Find available resource that fits
            available = manager.list_resources(ResourceStatus.AVAILABLE)
            for resource in available:
                if required_spec <= resource.spec:
                    # Allocate this resource
                    resource.status = ResourceStatus.ALLOCATED
                    resource.current_task_id = task_id
                    resource.last_used = time.time()
                    self.task_resources[task_id] = resource.resource_id
                    
                    self.event_bus.publish("resource.allocated", {
                        "resource_id": resource.resource_id,
                        "task_id": task_id
                    })
                    
                    return resource
            
            # No suitable resource found - provision if auto_scale enabled
            if self.auto_scale:
                total_resources = len(manager.list_resources())
                if total_resources < self.max_resources:
                    self.logger.info(f"Auto-provisioning resource for task {task_id}")
                    
                    try:
                        # Provision appropriate resource
                        if preferred_type == ResourceType.DOCKER_CONTAINER:
                            resource = manager.provision_resource(
                                spec=required_spec,
                                task_type=task_metadata.task_type
                            )
                        else:
                            # Need node info for Proxmox
                            node = self.proxmox_manager.proxmox.nodes.get()[0]['node']
                            resource = manager.provision_resource(
                                spec=required_spec,
                                node=node,
                                resource_type=preferred_type
                            )
                        
                        # Allocate immediately
                        resource.status = ResourceStatus.ALLOCATED
                        resource.current_task_id = task_id
                        self.task_resources[task_id] = resource.resource_id
                        
                        return resource
                        
                    except Exception as e:
                        self.logger.error(f"Failed to auto-provision resource: {e}")
            
            self.logger.warning(f"No available resources for task {task_id}")
            return None
    
    def release_resource(self, task_id: str):
        """Release resource allocated to a task"""
        with self.resource_allocation_lock:
            resource_id = self.task_resources.get(task_id)
            if not resource_id:
                return
            
            # Find the resource
            resource = None
            for manager in self.resource_managers.values():
                resource = manager.get_resource(resource_id)
                if resource:
                    break
            
            if resource:
                resource.status = ResourceStatus.AVAILABLE
                resource.current_task_id = None
                resource.total_tasks += 1
                
                self.event_bus.publish("resource.released", {
                    "resource_id": resource_id,
                    "task_id": task_id
                })
            
            del self.task_resources[task_id]
    
    def get_infrastructure_stats(self) -> InfrastructureStats:
        """Get comprehensive infrastructure statistics"""
        stats = InfrastructureStats()
        
        for manager in self.resource_managers.values():
            resources = manager.list_resources()
            
            for resource in resources:
                stats.total_resources += 1
                
                if resource.status == ResourceStatus.AVAILABLE:
                    stats.available_resources += 1
                elif resource.status == ResourceStatus.ALLOCATED:
                    stats.allocated_resources += 1
                elif resource.status == ResourceStatus.IN_USE:
                    stats.in_use_resources += 1
                
                # Aggregate capacity
                stats.total_capacity.cpu_cores += resource.spec.cpu_cores
                stats.total_capacity.memory_mb += resource.spec.memory_mb
                stats.total_capacity.disk_gb += resource.spec.disk_gb
                stats.total_capacity.gpu_count += resource.spec.gpu_count
                
                if resource.status == ResourceStatus.AVAILABLE:
                    stats.available_capacity.cpu_cores += resource.spec.cpu_cores
                    stats.available_capacity.memory_mb += resource.spec.memory_mb
                    stats.available_capacity.disk_gb += resource.spec.disk_gb
                    stats.available_capacity.gpu_count += resource.spec.gpu_count
                
                # Count by type
                if resource.resource_type == ResourceType.DOCKER_CONTAINER:
                    stats.containers_created += 1
                elif resource.resource_type in [ResourceType.PROXMOX_VM, ResourceType.PROXMOX_LXC]:
                    stats.vms_created += 1
                
                stats.tasks_executed += resource.total_tasks
        
        return stats
    
    def cleanup_idle_resources(self, max_idle_seconds: int = 300):
        """Cleanup resources that haven't been used recently"""
        for manager in self.resource_managers.values():
            if hasattr(manager, 'cleanup_unused_resources'):
                manager.cleanup_unused_resources(max_idle_seconds)
    
    def _on_task_queued(self, message: Dict[str, Any]):
        """Handle task queued event - potentially allocate resources"""
        # This could trigger pre-allocation if desired
        pass
    
    def _on_task_completed_infra(self, message: Dict[str, Any]):
        """Handle task completion - release resources"""
        task_id = message.get("task_id")
        if task_id:
            self.release_resource(task_id)
    
    def _on_task_failed_infra(self, message: Dict[str, Any]):
        """Handle task failure - release resources"""
        task_id = message.get("task_id")
        if task_id:
            self.release_resource(task_id)


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # Example configuration
    
    # Initialize infrastructure orchestrator
    orchestrator = InfrastructureOrchestrator(
        config={
            TaskType.LLM: 2,
            TaskType.GENERAL: 2
        },
        enable_docker=True,
        enable_proxmox=False,  # Set to True if you have Proxmox
        auto_scale=True,
        max_resources=5
    )
    
    # Start orchestrator
    orchestrator.start()
    
    try:
        # Manually provision some Docker containers
        print("Provisioning Docker resources...")
        spec = ResourceSpec(cpu_cores=2, memory_mb=1024)
        resources = orchestrator.provision_resources(
            ResourceType.DOCKER_CONTAINER,
            spec=spec,
            count=2,
            task_type=TaskType.GENERAL
        )
        print(f"Provisioned {len(resources)} resources")
        
        # Get infrastructure stats
        stats = orchestrator.get_infrastructure_stats()
        print(f"\nInfrastructure Stats:")
        print(f"  Total Resources: {stats.total_resources}")
        print(f"  Available: {stats.available_resources}")
        print(f"  Total CPU Cores: {stats.total_capacity.cpu_cores}")
        print(f"  Total Memory: {stats.total_capacity.memory_mb} MB")
        
        # Task will auto-allocate resources if needed
        print("\nSubmitting task (will auto-allocate if needed)...")
        task_id = orchestrator.submit_task("compute.sum", a=10, b=20)
        
        # Wait for result
        result = orchestrator.wait_for_result(task_id, timeout=30)
        if result:
            print(f"Task Result: {result.result}")
        
        # Cleanup
        time.sleep(2)
        print("\nCleaning up idle resources...")
        orchestrator.cleanup_idle_resources(max_idle_seconds=10)
        
    finally:
        # Stop orchestrator
        orchestrator.stop()