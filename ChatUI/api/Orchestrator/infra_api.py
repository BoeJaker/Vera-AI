"""
FastAPI Router - Infrastructure Resource Management
====================================================
Manages Docker containers and Proxmox VMs/LXCs for task execution.
"""

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

from Vera.Orchestration.orchestration_infra import (
    InfrastructureOrchestrator,
    DockerResourceManager,
    ProxmoxResourceManager,
    ResourceType,
    ResourceStatus,
    ResourceSpec,
    ResourceInstance,
    InfrastructureStats
)


# ============================================================================
# ROUTER SETUP
# ============================================================================

router = APIRouter(prefix="/orchestrator/infrastructure", tags=["infrastructure"])


# ============================================================================
# GLOBAL STATE
# ============================================================================

class InfrastructureState:
    def __init__(self):
        self.infra_orchestrator: Optional[InfrastructureOrchestrator] = None
        self.websocket_connections: List[WebSocket] = []


infra_state = InfrastructureState()


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class ResourceTypeEnum(str, Enum):
    """Resource types for API"""
    DOCKER_CONTAINER = "docker_container"
    PROXMOX_VM = "proxmox_vm"
    PROXMOX_LXC = "proxmox_lxc"


class ResourceStatusEnum(str, Enum):
    """Resource statuses for API"""
    AVAILABLE = "available"
    ALLOCATED = "allocated"
    IN_USE = "in_use"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class ResourceSpecModel(BaseModel):
    """Resource specification"""
    cpu_cores: float = Field(1.0, ge=0.1, le=128.0, description="CPU cores (can be fractional)")
    memory_mb: int = Field(512, ge=128, le=512000, description="Memory in MB")
    disk_gb: int = Field(10, ge=1, le=10000, description="Disk space in GB")
    gpu_count: int = Field(0, ge=0, le=8, description="Number of GPUs")
    gpu_memory_mb: int = Field(0, ge=0, description="GPU memory in MB")
    network_bandwidth_mbps: int = Field(100, ge=1, description="Network bandwidth in Mbps")


class DockerProvisionRequest(BaseModel):
    """Request to provision Docker container"""
    spec: ResourceSpecModel
    image: Optional[str] = Field(None, description="Docker image (auto-selected if not provided)")
    task_type: Optional[str] = Field(None, description="Task type for image selection")
    environment: Optional[Dict[str, str]] = Field(default_factory=dict)
    volumes: Optional[Dict[str, Dict[str, str]]] = Field(default_factory=dict)
    network_mode: str = Field("bridge", description="Docker network mode")


class ProxmoxProvisionRequest(BaseModel):
    """Request to provision Proxmox VM/LXC"""
    spec: ResourceSpecModel
    node: str = Field(..., description="Proxmox node name")
    resource_type: ResourceTypeEnum = Field(ResourceTypeEnum.PROXMOX_VM)
    template: Optional[str] = Field(None, description="Template to clone from")
    storage: str = Field("local-lvm", description="Storage location")
    network_bridge: str = Field("vmbr0", description="Network bridge")


class ResourceProvisionResponse(BaseModel):
    """Response after provisioning resource"""
    status: str
    resource_id: str
    resource_type: str
    spec: ResourceSpecModel
    message: str


class ResourceListItem(BaseModel):
    """Resource list item"""
    resource_id: str
    resource_type: str
    status: str
    spec: ResourceSpecModel
    current_task_id: Optional[str]
    created_at: float
    last_used: float
    total_tasks: int
    metadata: Dict[str, Any]


class ResourceExecuteRequest(BaseModel):
    """Request to execute command in resource"""
    command: str = Field(..., description="Command to execute")
    workdir: Optional[str] = Field(None, description="Working directory")
    environment: Optional[Dict[str, str]] = Field(default_factory=dict)


class ResourceScaleRequest(BaseModel):
    """Request to scale resources"""
    resource_type: ResourceTypeEnum
    spec: ResourceSpecModel
    count: int = Field(..., ge=1, le=20, description="Number of resources to provision")
    task_type: Optional[str] = None


class CleanupRequest(BaseModel):
    """Request to cleanup idle resources"""
    max_idle_seconds: int = Field(300, ge=60, le=3600, description="Max idle time in seconds")


class InfrastructureConfigRequest(BaseModel):
    """Request to initialize infrastructure orchestrator"""
    enable_docker: bool = True
    enable_proxmox: bool = False
    docker_url: str = "unix://var/run/docker.sock"
    proxmox_host: Optional[str] = None
    proxmox_user: Optional[str] = None
    proxmox_password: Optional[str] = None
    proxmox_token_name: Optional[str] = None
    proxmox_token_value: Optional[str] = None
    auto_scale: bool = True
    max_resources: int = Field(10, ge=1, le=100)


# ============================================================================
# INITIALIZATION
# ============================================================================

@router.post("/initialize")
async def initialize_infrastructure(config: InfrastructureConfigRequest):
    """Initialize infrastructure orchestrator with Docker/Proxmox support"""
    try:
        from Vera.Orchestration.orchestration import TaskType
        
        # Build Proxmox config if enabled
        proxmox_config = None
        if config.enable_proxmox:
            if not config.proxmox_host or not config.proxmox_user:
                raise HTTPException(
                    status_code=400,
                    detail="Proxmox host and user required when enable_proxmox=True"
                )
            
            proxmox_config = {
                "host": config.proxmox_host,
                "user": config.proxmox_user,
                "verify_ssl": False
            }
            
            if config.proxmox_token_name and config.proxmox_token_value:
                proxmox_config["token_name"] = config.proxmox_token_name
                proxmox_config["token_value"] = config.proxmox_token_value
            elif config.proxmox_password:
                proxmox_config["password"] = config.proxmox_password
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Proxmox authentication required (password or token)"
                )
        
        # Initialize orchestrator
        infra_state.infra_orchestrator = InfrastructureOrchestrator(
            config={
                TaskType.LLM: 2,
                TaskType.TOOL: 2,
                TaskType.GENERAL: 2
            },
            enable_docker=config.enable_docker,
            enable_proxmox=config.enable_proxmox,
            docker_url=config.docker_url,
            proxmox_config=proxmox_config,
            auto_scale=config.auto_scale,
            max_resources=config.max_resources
        )
        
        infra_state.infra_orchestrator.start()
        
        return {
            "status": "success",
            "message": "Infrastructure orchestrator initialized",
            "config": {
                "docker_enabled": config.enable_docker,
                "proxmox_enabled": config.enable_proxmox,
                "auto_scale": config.auto_scale,
                "max_resources": config.max_resources
            }
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Initialization failed: {str(e)}")


# ============================================================================
# RESOURCE PROVISIONING
# ============================================================================

@router.post("/resources/docker/provision", response_model=ResourceProvisionResponse)
async def provision_docker_container(request: DockerProvisionRequest):
    """Provision a new Docker container"""
    if not infra_state.infra_orchestrator:
        raise HTTPException(status_code=400, detail="Infrastructure not initialized")
    
    if ResourceType.DOCKER_CONTAINER not in infra_state.infra_orchestrator.resource_managers:
        raise HTTPException(status_code=400, detail="Docker not enabled")
    
    try:
        from Vera.Orchestration.orchestration import TaskType
        
        # Convert spec
        spec = ResourceSpec(
            cpu_cores=request.spec.cpu_cores,
            memory_mb=request.spec.memory_mb,
            disk_gb=request.spec.disk_gb,
            gpu_count=request.spec.gpu_count,
            gpu_memory_mb=request.spec.gpu_memory_mb,
            network_bandwidth_mbps=request.spec.network_bandwidth_mbps
        )
        
        # Map task type
        task_type = None
        if request.task_type:
            task_type_map = {
                "LLM": TaskType.LLM,
                "TOOL": TaskType.TOOL,
                "WHISPER": TaskType.WHISPER,
                "BACKGROUND": TaskType.BACKGROUND,
                "GENERAL": TaskType.GENERAL,
                "ML_MODEL": TaskType.ML_MODEL
            }
            task_type = task_type_map.get(request.task_type.upper())
        
        # Provision
        manager = infra_state.infra_orchestrator.resource_managers[ResourceType.DOCKER_CONTAINER]
        resource = manager.provision_resource(
            spec=spec,
            image=request.image,
            task_type=task_type,
            environment=request.environment,
            volumes=request.volumes,
            network_mode=request.network_mode
        )
        
        return ResourceProvisionResponse(
            status="success",
            resource_id=resource.resource_id,
            resource_type=resource.resource_type.value,
            spec=ResourceSpecModel(**spec.__dict__),
            message=f"Docker container provisioned: {resource.resource_id}"
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Provisioning failed: {str(e)}")


@router.post("/resources/proxmox/provision", response_model=ResourceProvisionResponse)
async def provision_proxmox_resource(request: ProxmoxProvisionRequest):
    """Provision a new Proxmox VM or LXC container"""
    if not infra_state.infra_orchestrator:
        raise HTTPException(status_code=400, detail="Infrastructure not initialized")
    
    # Check if Proxmox is enabled
    resource_type_map = {
        ResourceTypeEnum.PROXMOX_VM: ResourceType.PROXMOX_VM,
        ResourceTypeEnum.PROXMOX_LXC: ResourceType.PROXMOX_LXC
    }
    
    resource_type = resource_type_map[request.resource_type]
    
    if resource_type not in infra_state.infra_orchestrator.resource_managers:
        raise HTTPException(status_code=400, detail="Proxmox not enabled")
    
    try:
        # Convert spec
        spec = ResourceSpec(
            cpu_cores=request.spec.cpu_cores,
            memory_mb=request.spec.memory_mb,
            disk_gb=request.spec.disk_gb,
            gpu_count=request.spec.gpu_count,
            gpu_memory_mb=request.spec.gpu_memory_mb,
            network_bandwidth_mbps=request.spec.network_bandwidth_mbps
        )
        
        # Provision
        manager = infra_state.infra_orchestrator.resource_managers[resource_type]
        resource = manager.provision_resource(
            spec=spec,
            node=request.node,
            resource_type=resource_type,
            template=request.template,
            storage=request.storage,
            network_bridge=request.network_bridge
        )
        
        return ResourceProvisionResponse(
            status="success",
            resource_id=resource.resource_id,
            resource_type=resource.resource_type.value,
            spec=ResourceSpecModel(**spec.__dict__),
            message=f"Proxmox resource provisioned: {resource.resource_id}"
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Provisioning failed: {str(e)}")


@router.post("/resources/scale")
async def scale_resources(request: ResourceScaleRequest):
    """Provision multiple resources at once"""
    if not infra_state.infra_orchestrator:
        raise HTTPException(status_code=400, detail="Infrastructure not initialized")
    
    try:
        # Convert types
        resource_type_map = {
            ResourceTypeEnum.DOCKER_CONTAINER: ResourceType.DOCKER_CONTAINER,
            ResourceTypeEnum.PROXMOX_VM: ResourceType.PROXMOX_VM,
            ResourceTypeEnum.PROXMOX_LXC: ResourceType.PROXMOX_LXC
        }
        
        resource_type = resource_type_map[request.resource_type]
        
        # Convert spec
        spec = ResourceSpec(
            cpu_cores=request.spec.cpu_cores,
            memory_mb=request.spec.memory_mb,
            disk_gb=request.spec.disk_gb,
            gpu_count=request.spec.gpu_count,
            gpu_memory_mb=request.spec.gpu_memory_mb,
            network_bandwidth_mbps=request.spec.network_bandwidth_mbps
        )
        
        # Provision multiple
        kwargs = {}
        if request.task_type and resource_type == ResourceType.DOCKER_CONTAINER:
            from Vera.Orchestration.orchestration import TaskType
            task_type_map = {
                "LLM": TaskType.LLM,
                "TOOL": TaskType.TOOL,
                "WHISPER": TaskType.WHISPER,
                "BACKGROUND": TaskType.BACKGROUND,
                "GENERAL": TaskType.GENERAL
            }
            kwargs["task_type"] = task_type_map.get(request.task_type.upper())
        
        resources = infra_state.infra_orchestrator.provision_resources(
            resource_type=resource_type,
            spec=spec,
            count=request.count,
            **kwargs
        )
        
        return {
            "status": "success",
            "message": f"Provisioned {len(resources)} resources",
            "resource_ids": [r.resource_id for r in resources],
            "requested": request.count,
            "provisioned": len(resources)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scaling failed: {str(e)}")


# ============================================================================
# RESOURCE MANAGEMENT
# ============================================================================

@router.get("/resources", response_model=List[ResourceListItem])
async def list_resources(
    status: Optional[ResourceStatusEnum] = Query(None, description="Filter by status"),
    resource_type: Optional[ResourceTypeEnum] = Query(None, description="Filter by type")
):
    """List all infrastructure resources"""
    if not infra_state.infra_orchestrator:
        return []
    
    try:
        resources = []
        
        for manager in infra_state.infra_orchestrator.resource_managers.values():
            # Filter by status if provided
            status_filter = None
            if status:
                status_map = {
                    ResourceStatusEnum.AVAILABLE: ResourceStatus.AVAILABLE,
                    ResourceStatusEnum.ALLOCATED: ResourceStatus.ALLOCATED,
                    ResourceStatusEnum.IN_USE: ResourceStatus.IN_USE,
                    ResourceStatusEnum.STOPPING: ResourceStatus.STOPPING,
                    ResourceStatusEnum.STOPPED: ResourceStatus.STOPPED,
                    ResourceStatusEnum.ERROR: ResourceStatus.ERROR
                }
                status_filter = status_map[status]
            
            manager_resources = manager.list_resources(status_filter)
            
            # Filter by resource type if provided
            if resource_type:
                type_map = {
                    ResourceTypeEnum.DOCKER_CONTAINER: ResourceType.DOCKER_CONTAINER,
                    ResourceTypeEnum.PROXMOX_VM: ResourceType.PROXMOX_VM,
                    ResourceTypeEnum.PROXMOX_LXC: ResourceType.PROXMOX_LXC
                }
                manager_resources = [
                    r for r in manager_resources
                    if r.resource_type == type_map[resource_type]
                ]
            
            # Convert to response model
            for resource in manager_resources:
                resources.append(ResourceListItem(
                    resource_id=resource.resource_id,
                    resource_type=resource.resource_type.value,
                    status=resource.status.name.lower(),
                    spec=ResourceSpecModel(**resource.spec.__dict__),
                    current_task_id=resource.current_task_id,
                    created_at=resource.created_at,
                    last_used=resource.last_used,
                    total_tasks=resource.total_tasks,
                    metadata=resource.metadata
                ))
        
        return resources
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list resources: {str(e)}")


@router.get("/resources/{resource_id}")
async def get_resource_details(resource_id: str):
    """Get detailed information about a specific resource"""
    if not infra_state.infra_orchestrator:
        raise HTTPException(status_code=400, detail="Infrastructure not initialized")
    
    try:
        # Find the resource across all managers
        resource = None
        manager = None
        
        for mgr in infra_state.infra_orchestrator.resource_managers.values():
            resource = mgr.get_resource(resource_id)
            if resource:
                manager = mgr
                break
        
        if not resource:
            raise HTTPException(status_code=404, detail=f"Resource not found: {resource_id}")
        
        # Get runtime stats
        stats = manager.get_resource_stats(resource_id)
        
        return {
            "resource_id": resource.resource_id,
            "resource_type": resource.resource_type.value,
            "status": resource.status.name.lower(),
            "spec": ResourceSpecModel(**resource.spec.__dict__).dict(),
            "current_task_id": resource.current_task_id,
            "created_at": resource.created_at,
            "last_used": resource.last_used,
            "total_tasks": resource.total_tasks,
            "metadata": resource.metadata,
            "runtime_stats": stats
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get resource: {str(e)}")


@router.delete("/resources/{resource_id}")
async def deallocate_resource(resource_id: str):
    """Deallocate and remove a resource"""
    if not infra_state.infra_orchestrator:
        raise HTTPException(status_code=400, detail="Infrastructure not initialized")
    
    try:
        # Find the manager for this resource
        manager = None
        for mgr in infra_state.infra_orchestrator.resource_managers.values():
            if mgr.get_resource(resource_id):
                manager = mgr
                break
        
        if not manager:
            raise HTTPException(status_code=404, detail=f"Resource not found: {resource_id}")
        
        # Deallocate
        manager.deallocate_resource(resource_id)
        
        return {
            "status": "success",
            "message": f"Resource deallocated: {resource_id}"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deallocation failed: {str(e)}")


@router.post("/resources/{resource_id}/execute")
async def execute_in_resource(resource_id: str, request: ResourceExecuteRequest):
    """Execute a command in a resource (container/VM)"""
    if not infra_state.infra_orchestrator:
        raise HTTPException(status_code=400, detail="Infrastructure not initialized")
    
    try:
        # Find the manager
        manager = None
        for mgr in infra_state.infra_orchestrator.resource_managers.values():
            if mgr.get_resource(resource_id):
                manager = mgr
                break
        
        if not manager:
            raise HTTPException(status_code=404, detail=f"Resource not found: {resource_id}")
        
        # Execute command
        exit_code, output = manager.execute_in_resource(
            resource_id,
            request.command,
            workdir=request.workdir,
            environment=request.environment
        )
        
        return {
            "status": "success" if exit_code == 0 else "error",
            "exit_code": exit_code,
            "output": output,
            "resource_id": resource_id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(e)}")


# ============================================================================
# RESOURCE CLEANUP
# ============================================================================

@router.post("/resources/cleanup")
async def cleanup_idle_resources(request: CleanupRequest):
    """Clean up idle resources that haven't been used recently"""
    if not infra_state.infra_orchestrator:
        raise HTTPException(status_code=400, detail="Infrastructure not initialized")
    
    try:
        infra_state.infra_orchestrator.cleanup_idle_resources(
            max_idle_seconds=request.max_idle_seconds
        )
        
        return {
            "status": "success",
            "message": f"Cleaned up resources idle for more than {request.max_idle_seconds}s"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")


# ============================================================================
# STATISTICS & MONITORING
# ============================================================================

@router.get("/stats")
async def get_infrastructure_stats():
    """Get comprehensive infrastructure statistics"""
    if not infra_state.infra_orchestrator:
        return {
            "initialized": False,
            "total_resources": 0
        }
    
    try:
        stats = infra_state.infra_orchestrator.get_infrastructure_stats()
        
        return {
            "initialized": True,
            "total_resources": stats.total_resources,
            "available_resources": stats.available_resources,
            "allocated_resources": stats.allocated_resources,
            "in_use_resources": stats.in_use_resources,
            "total_capacity": {
                "cpu_cores": stats.total_capacity.cpu_cores,
                "memory_mb": stats.total_capacity.memory_mb,
                "disk_gb": stats.total_capacity.disk_gb,
                "gpu_count": stats.total_capacity.gpu_count
            },
            "available_capacity": {
                "cpu_cores": stats.available_capacity.cpu_cores,
                "memory_mb": stats.available_capacity.memory_mb,
                "disk_gb": stats.available_capacity.disk_gb,
                "gpu_count": stats.available_capacity.gpu_count
            },
            "tasks_executed": stats.tasks_executed,
            "containers_created": stats.containers_created,
            "vms_created": stats.vms_created
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.get("/stats/resources/{resource_id}")
async def get_resource_stats(resource_id: str):
    """Get runtime statistics for a specific resource"""
    if not infra_state.infra_orchestrator:
        raise HTTPException(status_code=400, detail="Infrastructure not initialized")
    
    try:
        # Find the manager
        manager = None
        for mgr in infra_state.infra_orchestrator.resource_managers.values():
            if mgr.get_resource(resource_id):
                manager = mgr
                break
        
        if not manager:
            raise HTTPException(status_code=404, detail=f"Resource not found: {resource_id}")
        
        stats = manager.get_resource_stats(resource_id)
        
        return {
            "resource_id": resource_id,
            "stats": stats,
            "timestamp": datetime.now().isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get("/health")
async def infrastructure_health():
    """Health check for infrastructure management"""
    if not infra_state.infra_orchestrator:
        return {
            "status": "not_initialized",
            "docker_available": False,
            "proxmox_available": False
        }
    
    docker_available = ResourceType.DOCKER_CONTAINER in infra_state.infra_orchestrator.resource_managers
    proxmox_available = (
        ResourceType.PROXMOX_VM in infra_state.infra_orchestrator.resource_managers or
        ResourceType.PROXMOX_LXC in infra_state.infra_orchestrator.resource_managers
    )
    
    return {
        "status": "healthy",
        "docker_available": docker_available,
        "proxmox_available": proxmox_available,
        "auto_scale_enabled": infra_state.infra_orchestrator.auto_scale,
        "max_resources": infra_state.infra_orchestrator.max_resources
    }


# ============================================================================
# HELPER FUNCTION FOR MAIN API
# ============================================================================

def initialize_infrastructure_api(
    infra_orchestrator: InfrastructureOrchestrator
):
    """
    Initialize infrastructure API with orchestrator instance.
    Call this from main FastAPI startup.
    """
    infra_state.infra_orchestrator = infra_orchestrator
    print("[Infrastructure API] Initialized")