"""
Vera Unified Orchestrator
==========================
Brings together all orchestration capabilities:
- Local worker pools
- Docker containers
- Proxmox VMs/LXC
- External compute APIs (Lambda, RunPod, etc.)
- External LLM APIs (OpenAI, Anthropic, Google, etc.)

Provides intelligent routing, cost optimization, and failover.
"""

import os
import time
import logging
from typing import Any, Dict, List, Optional, Iterator
from dataclasses import dataclass
from enum import Enum

# Import all orchestration components
from vera_orchestrator import (
    Orchestrator, TaskType, Priority, TaskStatus,
    TaskMetadata, TaskResult, registry
)
from vera_orchestrator_infra import (
    InfrastructureOrchestrator,
    ResourceType, ResourceSpec, ResourceStatus
)
from vera_orchestrator_external import (
    ExternalAPIOrchestrator,
    ExternalProvider,
    ExternalTaskMetadata
)


# ============================================================================
# EXECUTION STRATEGY
# ============================================================================

class ExecutionStrategy(Enum):
    """Strategy for task execution"""
    LOCAL = "local"              # Local worker pools
    DOCKER = "docker"            # Docker containers
    PROXMOX = "proxmox"         # Proxmox VMs/LXC
    EXTERNAL_COMPUTE = "external_compute"  # External compute APIs
    EXTERNAL_LLM = "external_llm"          # External LLM APIs
    AUTO = "auto"                # Automatic selection


@dataclass
class RoutingPolicy:
    """Policy for routing tasks to execution backends"""
    # Prefer external APIs for these task types
    external_task_types: List[TaskType] = None
    
    # Cost threshold (USD) - use cheaper option if below
    cost_threshold: float = 1.0
    
    # Latency threshold (ms) - use faster option if critical
    latency_threshold: float = 1000.0
    
    # Prefer local/Docker for quick tasks
    quick_task_threshold_seconds: float = 5.0
    
    # Enable failover between backends
    enable_failover: bool = True
    
    # Prefer cheap providers
    prefer_cheap: bool = False


# ============================================================================
# UNIFIED ORCHESTRATOR
# ============================================================================

class UnifiedOrchestrator:
    """
    Unified orchestration system that intelligently routes tasks across:
    - Local worker pools
    - Docker containers
    - Proxmox VMs/LXC  
    - External compute APIs
    - External LLM APIs
    """
    
    def __init__(
        self,
        # Base orchestrator config
        worker_config: Optional[Dict[TaskType, int]] = None,
        
        # Infrastructure config
        enable_docker: bool = True,
        enable_proxmox: bool = False,
        docker_config: Optional[Dict[str, Any]] = None,
        proxmox_config: Optional[Dict[str, Any]] = None,
        
        # External API config
        external_api_config: Optional[Dict[str, Any]] = None,
        
        # Routing policy
        routing_policy: Optional[RoutingPolicy] = None,
        
        # General config
        redis_url: Optional[str] = None,
        auto_scale: bool = True,
        max_resources: int = 10
    ):
        """
        Initialize unified orchestrator.
        
        Args:
            worker_config: Local worker pool configuration
            enable_docker: Enable Docker resources
            enable_proxmox: Enable Proxmox resources
            docker_config: Docker-specific config
            proxmox_config: Proxmox connection config
            external_api_config: External API keys and config
            routing_policy: Task routing policy
            redis_url: Redis URL for coordination
            auto_scale: Enable auto-scaling
            max_resources: Maximum resources to provision
        """
        self.logger = logging.getLogger("UnifiedOrchestrator")
        
        # Initialize infrastructure orchestrator
        self.infra = InfrastructureOrchestrator(
            config=worker_config,
            redis_url=redis_url,
            enable_docker=enable_docker,
            enable_proxmox=enable_proxmox,
            docker_url=docker_config.get('url') if docker_config else None,
            proxmox_config=proxmox_config,
            auto_scale=auto_scale,
            max_resources=max_resources
        )
        
        # Initialize external API orchestrator
        self.external = None
        if external_api_config:
            self.external = ExternalAPIOrchestrator(
                self.infra.event_bus,
                external_api_config
            )
        
        # Routing policy
        self.routing_policy = routing_policy or RoutingPolicy()
        
        # Statistics
        self.execution_stats = {
            ExecutionStrategy.LOCAL: {"count": 0, "total_time": 0.0},
            ExecutionStrategy.DOCKER: {"count": 0, "total_time": 0.0},
            ExecutionStrategy.PROXMOX: {"count": 0, "total_time": 0.0},
            ExecutionStrategy.EXTERNAL_COMPUTE: {"count": 0, "total_time": 0.0},
            ExecutionStrategy.EXTERNAL_LLM: {"count": 0, "total_time": 0.0},
        }
        
        self.logger.info("Unified orchestrator initialized")
    
    def start(self):
        """Start the orchestrator"""
        self.infra.start()
        self.logger.info("Unified orchestrator started")
    
    def stop(self):
        """Stop the orchestrator"""
        self.infra.stop()
        self.logger.info("Unified orchestrator stopped")
    
    def _select_execution_strategy(
        self,
        task_name: str,
        task_metadata: TaskMetadata,
        *args,
        **kwargs
    ) -> ExecutionStrategy:
        """
        Intelligently select execution strategy based on:
        - Task type and characteristics
        - Cost considerations
        - Latency requirements
        - Resource availability
        """
        # Check if external LLM preferred
        if (self.external and 
            task_metadata.task_type == TaskType.LLM and
            self.routing_policy.external_task_types and
            TaskType.LLM in self.routing_policy.external_task_types):
            return ExecutionStrategy.EXTERNAL_LLM
        
        # Check if external compute preferred for heavy tasks
        if (self.external and
            task_metadata.estimated_duration > 60.0 and
            task_metadata.requires_gpu):
            return ExecutionStrategy.EXTERNAL_COMPUTE
        
        # Quick tasks -> prefer local or Docker
        if task_metadata.estimated_duration < self.routing_policy.quick_task_threshold_seconds:
            # Check if Docker available
            if self.infra.resource_managers.get(ResourceType.DOCKER_CONTAINER):
                return ExecutionStrategy.DOCKER
            return ExecutionStrategy.LOCAL
        
        # GPU tasks -> prefer Proxmox VMs if available, else external
        if task_metadata.requires_gpu:
            if self.infra.resource_managers.get(ResourceType.PROXMOX_VM):
                return ExecutionStrategy.PROXMOX
            elif self.external:
                return ExecutionStrategy.EXTERNAL_COMPUTE
            return ExecutionStrategy.DOCKER
        
        # Default: use infrastructure orchestrator (local/Docker)
        return ExecutionStrategy.DOCKER if self.infra.resource_managers else ExecutionStrategy.LOCAL
    
    def submit_task(
        self,
        task_name: str,
        *args,
        strategy: ExecutionStrategy = ExecutionStrategy.AUTO,
        external_provider: Optional[ExternalProvider] = None,
        external_model: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Submit a task for execution.
        
        Args:
            task_name: Name of the task
            *args: Task arguments
            strategy: Execution strategy (AUTO for automatic selection)
            external_provider: Specific external provider (if using external APIs)
            external_model: Specific model (for LLM tasks)
            **kwargs: Task keyword arguments
        
        Returns:
            Task ID
        """
        # Get task metadata
        task_metadata = registry.get_metadata(task_name)
        if not task_metadata:
            raise ValueError(f"Task not registered: {task_name}")
        
        # Select strategy
        if strategy == ExecutionStrategy.AUTO:
            strategy = self._select_execution_strategy(
                task_name, task_metadata, *args, **kwargs
            )
        
        self.logger.info(f"Routing task {task_name} to {strategy.value}")
        
        # Execute based on strategy
        if strategy in [ExecutionStrategy.LOCAL, ExecutionStrategy.DOCKER, ExecutionStrategy.PROXMOX]:
            # Use infrastructure orchestrator
            task_id = self.infra.submit_task(task_name, *args, **kwargs)
            
        elif strategy == ExecutionStrategy.EXTERNAL_LLM:
            # Use external LLM API
            if not self.external:
                raise ValueError("External APIs not configured")
            
            # Determine provider
            if not external_provider:
                # Select cheapest provider
                external_provider = ExternalProvider.OPENAI  # Default
            
            # Create metadata
            ext_metadata = ExternalTaskMetadata(
                provider=external_provider,
                model=external_model,
                stream=kwargs.pop('stream', False)
            )
            
            # Execute (synchronously for now, could be async)
            result = self.external.execute_task(
                external_provider,
                task_name,
                ext_metadata,
                *args,
                **kwargs
            )
            
            # Generate task ID and store result
            import uuid
            task_id = str(uuid.uuid4())
            task_result = TaskResult(
                task_id=task_id,
                status=TaskStatus.COMPLETED,
                result=result,
                started_at=time.time(),
                completed_at=time.time()
            )
            
            # Store in infrastructure orchestrator's completed tasks
            with self.infra.task_queue._lock:
                self.infra.task_queue._completed[task_id] = task_result
            
        elif strategy == ExecutionStrategy.EXTERNAL_COMPUTE:
            # Use external compute API
            if not self.external:
                raise ValueError("External APIs not configured")
            
            if not external_provider:
                external_provider = ExternalProvider.AWS_LAMBDA  # Default
            
            ext_metadata = ExternalTaskMetadata(
                provider=external_provider
            )
            
            result = self.external.execute_task(
                external_provider,
                task_name,
                ext_metadata,
                *args,
                **kwargs
            )
            
            import uuid
            task_id = str(uuid.uuid4())
            task_result = TaskResult(
                task_id=task_id,
                status=TaskStatus.COMPLETED,
                result=result,
                started_at=time.time(),
                completed_at=time.time()
            )
            
            with self.infra.task_queue._lock:
                self.infra.task_queue._completed[task_id] = task_result
        
        else:
            raise ValueError(f"Unknown strategy: {strategy}")
        
        # Update stats
        self.execution_stats[strategy]["count"] += 1
        
        return task_id
    
    def wait_for_result(
        self,
        task_id: str,
        timeout: Optional[float] = None
    ) -> Optional[TaskResult]:
        """Wait for task result"""
        return self.infra.wait_for_result(task_id, timeout)
    
    def stream_result(
        self,
        task_id: str,
        timeout: Optional[float] = None
    ) -> Iterator[Any]:
        """Stream task results"""
        yield from self.infra.stream_result(task_id, timeout)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics"""
        stats = {
            "infrastructure": self.infra.get_infrastructure_stats(),
            "execution_strategy": self.execution_stats,
            "orchestrator": self.infra.get_stats()
        }
        
        if self.external:
            stats["external_apis"] = {
                "usage": self.external.get_stats(),
                "total_cost": self.external.get_total_cost()
            }
        
        return stats
    
    def optimize_costs(self) -> Dict[str, Any]:
        """
        Analyze costs and provide optimization recommendations.
        
        Returns:
            Dict with cost analysis and recommendations
        """
        recommendations = {
            "current_costs": {},
            "recommendations": [],
            "potential_savings": 0.0
        }
        
        # Get infrastructure costs (approximate)
        infra_stats = self.infra.get_infrastructure_stats()
        docker_hours = infra_stats.containers_created * 1.0  # Assume 1 hour avg
        proxmox_hours = infra_stats.vms_created * 2.0  # Assume 2 hours avg
        
        docker_cost = docker_hours * 0.01  # $0.01/hour estimate
        proxmox_cost = proxmox_hours * 0.50  # $0.50/hour estimate
        
        recommendations["current_costs"]["docker"] = docker_cost
        recommendations["current_costs"]["proxmox"] = proxmox_cost
        
        # Get external API costs
        if self.external:
            api_cost = self.external.get_total_cost()
            recommendations["current_costs"]["external_apis"] = api_cost
            
            # Analyze external API usage
            api_stats = self.external.get_stats()
            
            for provider, stats in api_stats.items():
                if stats['total_requests'] > 10:
                    # Check if moving to local could save money
                    if stats['total_cost_usd'] > 1.0:
                        recommendations["recommendations"].append({
                            "type": "consider_local",
                            "provider": provider,
                            "reason": f"High API costs (${stats['total_cost_usd']:.2f})",
                            "suggestion": "Consider running models locally or on Proxmox"
                        })
        
        # Check resource utilization
        if infra_stats.available_resources > infra_stats.in_use_resources * 2:
            recommendations["recommendations"].append({
                "type": "reduce_resources",
                "reason": f"Low utilization ({infra_stats.in_use_resources}/{infra_stats.total_resources} in use)",
                "suggestion": "Consider reducing max_resources or enabling more aggressive cleanup"
            })
        
        return recommendations


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_unified_orchestrator(
    scenario: str = "local_dev",
    external_apis: Optional[Dict[str, str]] = None
) -> UnifiedOrchestrator:
    """
    Create a unified orchestrator with pre-configured scenario.
    
    Args:
        scenario: One of "local_dev", "production", "hybrid", "cloud_first"
        external_apis: Dict of API keys (openai, anthropic, etc.)
    
    Returns:
        Configured UnifiedOrchestrator
    """
    if scenario == "local_dev":
        # Local development - Docker only
        return UnifiedOrchestrator(
            worker_config={TaskType.GENERAL: 2, TaskType.LLM: 1},
            enable_docker=True,
            enable_proxmox=False,
            external_api_config=external_apis,
            auto_scale=True,
            max_resources=5
        )
    
    elif scenario == "production":
        # Production - Docker + Proxmox
        return UnifiedOrchestrator(
            worker_config={
                TaskType.LLM: 2,
                TaskType.ML_MODEL: 1,
                TaskType.TOOL: 4,
                TaskType.GENERAL: 4
            },
            enable_docker=True,
            enable_proxmox=True,
            external_api_config=external_apis,
            routing_policy=RoutingPolicy(
                enable_failover=True,
                cost_threshold=1.0
            ),
            auto_scale=True,
            max_resources=20
        )
    
    elif scenario == "hybrid":
        # Hybrid - local for quick, cloud for heavy
        return UnifiedOrchestrator(
            worker_config={TaskType.GENERAL: 4},
            enable_docker=True,
            enable_proxmox=False,
            external_api_config=external_apis,
            routing_policy=RoutingPolicy(
                external_task_types=[TaskType.LLM, TaskType.ML_MODEL],
                quick_task_threshold_seconds=5.0,
                prefer_cheap=True
            ),
            auto_scale=True,
            max_resources=10
        )
    
    elif scenario == "cloud_first":
        # Cloud first - prefer external APIs
        return UnifiedOrchestrator(
            worker_config={TaskType.GENERAL: 2},
            enable_docker=False,
            enable_proxmox=False,
            external_api_config=external_apis,
            routing_policy=RoutingPolicy(
                external_task_types=[TaskType.LLM, TaskType.ML_MODEL, TaskType.TOOL],
                enable_failover=True
            ),
            auto_scale=False,
            max_resources=0
        )
    
    else:
        raise ValueError(f"Unknown scenario: {scenario}")


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # Example: Unified orchestrator with all backends
    
    external_config = {
        'openai': {
            'api_key': os.getenv('OPENAI_API_KEY', 'your-key')
        },
        'anthropic': {
            'api_key': os.getenv('ANTHROPIC_API_KEY', 'your-key')
        }
    }
    
    # Create orchestrator
    orchestrator = create_unified_orchestrator(
        scenario="hybrid",
        external_apis=external_config
    )
    
    orchestrator.start()
    
    try:
        # Quick task -> will use Docker/local
        task1 = orchestrator.submit_task("compute.sum", a=10, b=20)
        result1 = orchestrator.wait_for_result(task1, timeout=10)
        print(f"Quick task result: {result1.result}")
        
        # LLM task -> will use external API
        task2 = orchestrator.submit_task(
            "llm.summarize",
            prompt="Explain quantum computing",
            external_provider=ExternalProvider.OPENAI,
            external_model="gpt-3.5-turbo"
        )
        result2 = orchestrator.wait_for_result(task2, timeout=30)
        print(f"LLM task result: {result2.result[:100]}...")
        
        # Get comprehensive stats
        stats = orchestrator.get_stats()
        print(f"\nStats: {stats}")
        
        # Get cost recommendations
        recommendations = orchestrator.optimize_costs()
        print(f"\nCost analysis: {recommendations}")
        
    finally:
        orchestrator.stop()