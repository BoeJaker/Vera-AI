"""
FastAPI Endpoints for Streaming Orchestrator
=============================================
Exposes the new streaming-enabled orchestrator via REST API
"""

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
import asyncio
import psutil

from Vera.orchestration import (
    Orchestrator,
    TaskType,
    Priority,
    TaskStatus,
    registry
)

# ============================================================================
# ROUTER SETUP
# ============================================================================

router = APIRouter(prefix="/orchestrator", tags=["orchestrator"])


# ============================================================================
# GLOBAL STATE
# ============================================================================

class OrchestratorState:
    def __init__(self):
        self.orchestrator: Optional[Orchestrator] = None
        self.vera_instance = None
        self.websocket_connections: List[WebSocket] = []


state = OrchestratorState()


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class OrchestratorConfig(BaseModel):
    llm_workers: int = 3
    tool_workers: int = 4
    whisper_workers: int = 1
    background_workers: int = 2
    general_workers: int = 2
    cpu_threshold: float = 75.0


class WorkerScaleRequest(BaseModel):
    task_type: str  # "LLM", "TOOL", "WHISPER", "BACKGROUND", "GENERAL"
    num_workers: int


class TaskSubmission(BaseModel):
    name: str
    payload: Dict[str, Any] = {}
    priority: Optional[str] = None
    context: Dict[str, Any] = {}


class FocusUpdate(BaseModel):
    focus: str


# ============================================================================
# WEBSOCKET MANAGER
# ============================================================================

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        
        for conn in disconnected:
            self.disconnect(conn)


manager = ConnectionManager()


# ============================================================================
# ORCHESTRATOR MANAGEMENT
# ============================================================================

@router.post("/initialize")
async def initialize_orchestrator(config: OrchestratorConfig):
    """Initialize the orchestrator with worker pools"""
    try:
        from Vera.orchestration import TaskType
        
        orchestrator_config = {
            TaskType.LLM: config.llm_workers,
            TaskType.TOOL: config.tool_workers,
            TaskType.WHISPER: config.whisper_workers,
            TaskType.BACKGROUND: config.background_workers,
            TaskType.GENERAL: config.general_workers
        }
        
        state.orchestrator = Orchestrator(
            config=orchestrator_config,
            cpu_threshold=config.cpu_threshold
        )
        
        # Start the orchestrator
        state.orchestrator.start()
        
        # Subscribe to events for WebSocket broadcasting
        state.orchestrator.event_bus.subscribe("task.completed", lambda msg: 
            asyncio.create_task(manager.broadcast({"type": "task_completed", "data": msg}))
        )
        state.orchestrator.event_bus.subscribe("task.failed", lambda msg: 
            asyncio.create_task(manager.broadcast({"type": "task_failed", "data": msg}))
        )
        
        return {
            "status": "success",
            "message": "Orchestrator initialized and started",
            "config": {
                "llm_workers": config.llm_workers,
                "tool_workers": config.tool_workers,
                "whisper_workers": config.whisper_workers,
                "background_workers": config.background_workers,
                "general_workers": config.general_workers,
                "cpu_threshold": config.cpu_threshold
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialize: {str(e)}")


@router.post("/start")
async def start_orchestrator():
    """Start the orchestrator"""
    if not state.orchestrator:
        raise HTTPException(status_code=400, detail="Orchestrator not initialized")
    
    try:
        state.orchestrator.start()
        return {"status": "success", "message": "Orchestrator started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop")
async def stop_orchestrator():
    """Stop the orchestrator"""
    if not state.orchestrator:
        raise HTTPException(status_code=400, detail="Orchestrator not initialized")
    
    try:
        state.orchestrator.stop()
        return {"status": "success", "message": "Orchestrator stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_status():
    """Get orchestrator status"""
    if not state.orchestrator:
        return {
            "initialized": False,
            "running": False
        }
    
    stats = state.orchestrator.get_stats()
    
    # Calculate totals
    total_workers = 0
    active_workers = 0
    
    for pool_stats in stats.get("worker_pools", {}).values():
        total_workers += pool_stats.get("num_workers", 0)
        for worker in pool_stats.get("workers", []):
            if worker.get("current_task"):
                active_workers += 1
    
    # Get queue sizes
    queue_sizes = stats.get("queue_sizes", {})
    total_queue = sum(queue_sizes.values())
    
    return {
        "initialized": True,
        "running": stats.get("running", False),
        "worker_count": total_workers,
        "active_workers": active_workers,
        "queue_size": total_queue,
        "queue_sizes": queue_sizes,
        "worker_pools": stats.get("worker_pools", {})
    }


# ============================================================================
# WORKER POOL SCALING
# ============================================================================

@router.post("/workers/scale")
async def scale_workers(request: WorkerScaleRequest):
    """Scale a worker pool"""
    if not state.orchestrator:
        raise HTTPException(status_code=400, detail="Orchestrator not initialized")
    
    try:
        # Map string to TaskType enum
        task_type_map = {
            "LLM": TaskType.LLM,
            "TOOL": TaskType.TOOL,
            "WHISPER": TaskType.WHISPER,
            "BACKGROUND": TaskType.BACKGROUND,
            "GENERAL": TaskType.GENERAL,
            "ML_MODEL": TaskType.ML_MODEL
        }
        
        task_type = task_type_map.get(request.task_type.upper())
        if not task_type:
            raise HTTPException(status_code=400, detail=f"Invalid task type: {request.task_type}")
        
        # Scale the pool
        state.orchestrator.scale_pool(task_type, request.num_workers)
        
        return {
            "status": "success",
            "message": f"Scaled {request.task_type} pool to {request.num_workers} workers",
            "task_type": request.task_type,
            "num_workers": request.num_workers
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workers/pools")
async def get_worker_pools():
    """Get detailed worker pool information"""
    if not state.orchestrator:
        return {"pools": []}
    
    stats = state.orchestrator.get_stats()
    pools_data = []
    
    for task_type_str, pool_stats in stats.get("worker_pools", {}).items():
        num_workers = pool_stats.get("num_workers", 0)
        workers = pool_stats.get("workers", [])
        
        # Count active workers
        active_count = sum(1 for w in workers if w.get("current_task"))
        
        # Calculate utilization
        utilization = (active_count / num_workers * 100) if num_workers > 0 else 0
        
        # Get queue size for this type
        queue_size = stats.get("queue_sizes", {}).get(task_type_str, 0)
        
        pools_data.append({
            "task_type": task_type_str,
            "num_workers": num_workers,
            "active_workers": active_count,
            "idle_workers": num_workers - active_count,
            "utilization": round(utilization, 1),
            "queue_size": queue_size,
            "workers": workers
        })
    
    return {"pools": pools_data}


# ============================================================================
# TASK MANAGEMENT
# ============================================================================

@router.post("/tasks/submit")
async def submit_task(task: TaskSubmission):
    """Submit a task for execution"""
    if not state.orchestrator:
        raise HTTPException(status_code=400, detail="Orchestrator not initialized")
    
    if not state.vera_instance:
        raise HTTPException(status_code=400, detail="Vera instance not connected")
    
    try:
        # Add vera_instance to context
        context = task.context.copy()
        context["vera_instance"] = state.vera_instance
        
        # Submit task
        task_id = state.orchestrator.submit_task(
            task.name,
            **task.payload,
            **context
        )
        
        return {
            "status": "success",
            "task_id": task_id,
            "message": f"Task '{task.name}' submitted"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit task: {str(e)}")


@router.get("/tasks/result/{task_id}")
async def get_task_result(task_id: str, timeout: float = 5.0):
    """Get task result (for non-streaming tasks)"""
    if not state.orchestrator:
        raise HTTPException(status_code=400, detail="Orchestrator not initialized")
    
    try:
        result = state.orchestrator.wait_for_result(task_id, timeout=timeout)
        
        if not result:
            return {
                "status": "pending",
                "task_id": task_id,
                "message": "Task not completed yet"
            }
        
        return {
            "status": result.status.value,
            "task_id": task_id,
            "result": result.result,
            "error": result.error,
            "duration": result.duration
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/registry")
async def get_task_registry():
    """Get registered tasks"""
    tasks = []
    
    # Get all registered tasks
    for task_type in TaskType:
        task_names = registry.list_tasks(task_type=task_type)
        for name in task_names:
            metadata = registry.get_metadata(name)
            if metadata:
                tasks.append({
                    "name": name,
                    "type": task_type.value,
                    "priority": metadata.priority.value,
                    "estimated_duration": metadata.estimated_duration,
                    "requires_gpu": metadata.requires_gpu,
                    "proactive_focus": metadata.metadata.get("proactive_focus", False)
                })
    
    # Also get tasks without type filter
    all_tasks = registry.list_tasks()
    for name in all_tasks:
        if not any(t["name"] == name for t in tasks):
            tasks.append({"name": name, "type": "unknown"})
    
    return {"tasks": tasks, "count": len(tasks)}


@router.get("/tasks/history")
async def get_task_history(limit: int = 50):
    """Get task execution history"""
    # Get completed tasks from orchestrator
    # Note: You may want to add a history tracking mechanism to the orchestrator
    # For now, return empty list
    return {"history": [], "message": "Task history not yet implemented"}


# ============================================================================
# SYSTEM MONITORING
# ============================================================================

@router.get("/system/metrics")
async def get_system_metrics():
    """Get system metrics"""
    try:
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        
        # Get queue sizes if orchestrator is running
        queue_size = 0
        if state.orchestrator:
            stats = state.orchestrator.get_stats()
            queue_sizes = stats.get("queue_sizes", {})
            queue_size = sum(queue_sizes.values())
        
        return {
            "metrics": {
                "timestamp": datetime.now().isoformat(),
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_used_gb": memory.used / (1024**3),
                "memory_total_gb": memory.total / (1024**3),
                "queue_size": queue_size
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/system/processes")
async def get_system_processes():
    """Get system processes"""
    try:
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                info = proc.info
                if info['cpu_percent'] and info['cpu_percent'] > 0.1:  # Only show active processes
                    processes.append({
                        "pid": info['pid'],
                        "name": info['name'],
                        "cpu_percent": info['cpu_percent'] or 0,
                        "memory_percent": info['memory_percent'] or 0
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # Sort by CPU usage
        processes.sort(key=lambda x: x['cpu_percent'], reverse=True)
        
        return {"processes": processes[:20]}  # Top 20
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "orchestrator_initialized": state.orchestrator is not None,
        "orchestrator_running": state.orchestrator.running if state.orchestrator else False,
        "vera_connected": state.vera_instance is not None,
        "registered_tasks": len(list(registry._tasks.keys())) if hasattr(registry, '_tasks') else 0
    }


# ============================================================================
# WEBSOCKET
# ============================================================================

@router.websocket("/ws/updates")
async def websocket_updates(websocket: WebSocket):
    """WebSocket for real-time updates"""
    await manager.connect(websocket)
    try:
        while True:
            await asyncio.sleep(2)
            
            if state.orchestrator:
                stats = state.orchestrator.get_stats()
                queue_sizes = stats.get("queue_sizes", {})
                
                await websocket.send_json({
                    "type": "status_update",
                    "data": {
                        "queue_size": sum(queue_sizes.values()),
                        "queue_sizes": queue_sizes,
                        "timestamp": datetime.now().isoformat()
                    }
                })
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)


# ============================================================================
# INITIALIZATION HELPER
# ============================================================================

def initialize_orchestrator_api(vera_instance, config: Optional[Dict] = None):
    """
    Initialize orchestrator API with Vera instance.
    Call this from FastAPI startup.
    """
    from Vera.orchestration import TaskType
    
    state.vera_instance = vera_instance
    
    # Default config
    if config is None:
        config = {
            TaskType.LLM: 3,
            TaskType.TOOL: 4,
            TaskType.WHISPER: 1,
            TaskType.BACKGROUND: 2,
            TaskType.GENERAL: 2
        }
    
    # Create and start orchestrator
    state.orchestrator = Orchestrator(
        config=config,
        cpu_threshold=75.0
    )
    state.orchestrator.start()
    
    # Subscribe to events for WebSocket broadcasting
    state.orchestrator.event_bus.subscribe("task.completed", lambda msg: 
        asyncio.create_task(manager.broadcast({"type": "task_completed", "data": msg}))
    )
    state.orchestrator.event_bus.subscribe("task.failed", lambda msg: 
        asyncio.create_task(manager.broadcast({"type": "task_failed", "data": msg}))
    )
    
    print("[Orchestrator API] Initialized and started")
    
    return state.orchestrator