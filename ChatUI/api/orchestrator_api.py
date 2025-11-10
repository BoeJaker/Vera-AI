
"""
Integration module to add orchestrator routes to existing FastAPI application
Usage: 
    from orchestrator_integration import add_orchestrator_routes
    add_orchestrator_routes(app, vera_instance)
"""

from fastapi import APIRouter, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import os
import asyncio
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime
import psutil

from Vera.BackgroundCognition.proactive_background_focus import (
    PriorityWorkerPool, 
    ClusterWorkerPool, 
    RemoteNode,
    GLOBAL_TASK_REGISTRY as R,
    Priority,
    ProactiveFocusManager,
    ScheduledTask,
    TokenBucket
)

# ============================================================
# Router Setup
# ============================================================
router = APIRouter(prefix="/orchestrator", tags=["orchestrator"])

# ============================================================================
# GLOBAL STATE
# ============================================================================

class OrchestratorState:
    def __init__(self):
        self.local_pool: Optional[PriorityWorkerPool] = None
        self.cluster_pool: Optional[ClusterWorkerPool] = None
        self.focus_manager: Optional[ProactiveFocusManager] = None
        self.vera_instance = None
        self.task_history: List[Dict] = []
        self.system_metrics: List[Dict] = []
        self.remote_nodes: List[RemoteNode] = []
        self.websocket_connections: List[WebSocket] = []

state = OrchestratorState()


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class WorkerPoolConfig(BaseModel):
    worker_count: int = 4
    cpu_threshold: float = 85.0
    max_processes: int = 24
    max_process_name: str = "ollama"


class RemoteNodeConfig(BaseModel):
    name: str
    base_url: str
    labels: List[str]
    auth_token: Optional[str] = None
    weight: int = 1


class TaskSubmission(BaseModel):
    name: str
    payload: Dict[str, Any]
    priority: str = "NORMAL"
    labels: List[str] = []
    delay: float = 0.0
    context: Dict[str, Any] = {}


class FocusUpdate(BaseModel):
    focus: str


class RateLimitConfig(BaseModel):
    label: str
    fill_rate: float
    capacity: int


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
# TASK CALLBACKS
# ============================================================================

def on_task_start(task: ScheduledTask):
    """Called when a task starts execution"""
    task_data = {
        "type": "task_start",
        "timestamp": datetime.now().isoformat(),
        "task_id": task.task_id,
        "name": task.name,
        "priority": task.priority.name if hasattr(task.priority, 'name') else str(task.priority),
        "labels": list(task.labels)
    }
    
    state.task_history.append({
        "timestamp": task_data["timestamp"],
        "task_id": task.task_id,
        "name": task.name,
        "priority": task_data["priority"],
        "status": "started",
        "labels": ", ".join(task.labels)
    })
    
    # Broadcast to WebSocket clients
    asyncio.create_task(manager.broadcast({"type": "task_start", "data": task_data}))


def on_task_end(task: ScheduledTask, result: Optional[Any], error: Optional[BaseException]):
    """Called when a task completes or fails"""
    status = "completed" if error is None else "failed"
    
    task_data = {
        "type": "task_end",
        "timestamp": datetime.now().isoformat(),
        "task_id": task.task_id,
        "name": task.name,
        "priority": task.priority.name if hasattr(task.priority, 'name') else str(task.priority),
        "status": status,
        "result": str(result) if result else None,
        "error": str(error) if error else None,
        "labels": list(task.labels)
    }
    
    state.task_history.append({
        "timestamp": task_data["timestamp"],
        "task_id": task.task_id,
        "name": task.name,
        "priority": task_data["priority"],
        "status": status,
        "result": task_data["result"],
        "error": task_data["error"],
        "labels": ", ".join(task.labels)
    })
    
    # Keep history limited
    if len(state.task_history) > 1000:
        state.task_history = state.task_history[-500:]
    
    # Broadcast to WebSocket clients
    asyncio.create_task(manager.broadcast({"type": "task_end", "data": task_data}))


# ============================================================================
# FRONTEND UI
# ============================================================================

@router.get("/")
async def serve_orchestrator_ui():
    """Serve the orchestrator frontend"""
    html_path = os.path.join(os.path.dirname(__file__), "orchestrator.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    else:
        return {
            "message": "Orchestrator UI not found. Place orchestrator.html in the same directory.",
            "expected_path": html_path
        }


# ============================================================================
# HEALTH & STATUS
# ============================================================================

@router.get("/health")
async def orchestrator_health():
    """Get overall system health status"""
    return {
        "status": "healthy",
        "local_pool": state.local_pool is not None and state.local_pool._running,
        "cluster_pool": state.cluster_pool is not None,
        "focus_manager": state.focus_manager is not None and state.focus_manager._running,
        "vera_connected": state.vera_instance is not None
    }

@router.get("/system/metrics")
async def get_system_metrics():
    """Get current system metrics"""
    try:
        # Get queue size safely
        queue_size = 0
        if state.local_pool and hasattr(state.local_pool, '_q'):
            try:
                queue_size = state.local_pool._q.qsize()
            except Exception:
                queue_size = 0
        
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory_percent": psutil.virtual_memory().percent,
            "queue_size": queue_size
        }
        
        state.system_metrics.append(metrics)
        if len(state.system_metrics) > 100:
            state.system_metrics = state.system_metrics[-100:]
        
        return {"metrics": metrics}
    except Exception as e:
        # Log the error but return a valid response
        print(f"Error in get_system_metrics: {e}")
        return {
            "metrics": {
                "timestamp": datetime.now().isoformat(),
                "cpu_percent": 0.0,
                "memory_percent": 0.0,
                "queue_size": 0
            }
        }


# ============================================================================
# WORKER POOL MANAGEMENT
# ============================================================================

@router.post("/pool/initialize")
async def initialize_pool(config: WorkerPoolConfig):
    """Initialize the local worker pool"""
    try:
        # Define rate limits
        rate_limits = {
            "llm": (0.5, 2),
            "exec": (2.0, 5),
            "heavy": (0.2, 1)
        }
        
        # Create the pool
        state.local_pool = PriorityWorkerPool(
            worker_count=config.worker_count,
            cpu_threshold=config.cpu_threshold,
            max_process_name=config.max_process_name,
            max_processes=config.max_processes,
            rate_limits=rate_limits,
            on_task_start=on_task_start,
            on_task_end=on_task_end,
            name="VeraPool"
        )
        
        # Set concurrency limits
        state.local_pool.set_concurrency_limit("llm", 2)
        state.local_pool.set_concurrency_limit("exec", 3)
        state.local_pool.set_concurrency_limit("heavy", 1)
        
        return {
            "status": "success",
            "message": "Local pool initialized",
            "config": {
                "worker_count": config.worker_count,
                "cpu_threshold": config.cpu_threshold,
                "max_processes": config.max_processes,
                "max_process_name": config.max_process_name
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialize pool: {str(e)}")


@router.post("/pool/start")
async def start_pool():
    """Start the worker pool"""
    if not state.local_pool:
        raise HTTPException(status_code=400, detail="Pool not initialized. Call /pool/initialize first.")
    
    try:
        state.local_pool.start()
        return {"status": "success", "message": "Pool started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pool/stop")
async def stop_pool():
    """Stop the worker pool"""
    if not state.local_pool:
        raise HTTPException(status_code=400, detail="Pool not initialized")
    
    try:
        state.local_pool.stop()
        return {"status": "success", "message": "Pool stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pool/pause")
async def pause_pool():
    """Pause the worker pool (stop accepting new tasks)"""
    if not state.local_pool:
        raise HTTPException(status_code=400, detail="Pool not initialized")
    
    try:
        state.local_pool.pause()
        return {"status": "success", "message": "Pool paused"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pool/resume")
async def resume_pool():
    """Resume the worker pool"""
    if not state.local_pool:
        raise HTTPException(status_code=400, detail="Pool not initialized")
    
    try:
        state.local_pool.resume()
        return {"status": "success", "message": "Pool resumed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pool/status")
async def get_pool_status():
    """Get current pool status and metrics"""
    if not state.local_pool:
        return {"initialized": False}
    
    return {
        "initialized": True,
        "running": state.local_pool._running,
        "worker_count": state.local_pool.worker_count,
        "queue_size": state.local_pool._q.qsize(),
        "active_workers": len([t for t in state.local_pool._threads if t.is_alive()]),
        "rate_limits": {
            label: {
                "fill_rate": bucket.fill_rate,
                "capacity": bucket.capacity,
                "current_tokens": bucket.tokens
            }
            for label, bucket in getattr(state.local_pool, 'rate_buckets', {}).items()
        }
    }


# ============================================================================
# CLUSTER MANAGEMENT
# ============================================================================

@router.post("/cluster/initialize")
async def initialize_cluster():
    """Initialize the cluster pool"""
    if not state.local_pool:
        raise HTTPException(status_code=400, detail="Local pool must be initialized first")
    
    try:
        state.cluster_pool = ClusterWorkerPool(state.local_pool)
        
        # Re-add any existing nodes
        for node in state.remote_nodes:
            state.cluster_pool.add_node(node)
        
        return {
            "status": "success",
            "message": "Cluster initialized",
            "node_count": len(state.remote_nodes)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cluster/nodes/add")
async def add_cluster_node(config: RemoteNodeConfig):
    """Add a remote node to the cluster"""
    if not state.cluster_pool:
        raise HTTPException(status_code=400, detail="Cluster not initialized. Call /cluster/initialize first.")
    
    try:
        node = RemoteNode(
            name=config.name,
            base_url=config.base_url,
            labels=tuple(config.labels),
            auth_token=config.auth_token or "",
            weight=config.weight
        )
        
        state.remote_nodes.append(node)
        state.cluster_pool.add_node(node)
        
        return {
            "status": "success",
            "message": f"Node '{config.name}' added",
            "node": {
                "name": node.name,
                "base_url": node.base_url,
                "labels": list(node.labels),
                "weight": node.weight
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cluster/nodes")
async def get_cluster_nodes():
    """Get list of all cluster nodes"""
    nodes = []
    for node in state.remote_nodes:
        nodes.append({
            "name": node.name,
            "base_url": node.base_url,
            "labels": list(node.labels),
            "weight": node.weight,
            "last_ok": node.last_ok > 0,
            "inflight": node.inflight
        })
    
    return {"nodes": nodes}


@router.get("/cluster/nodes/{node_name}")
async def remove_cluster_node(node_name: str):
    """Remove a node from the cluster"""
    if not state.cluster_pool:
        raise HTTPException(status_code=400, detail="Cluster not initialized")
    
    # Find and remove from state
    node = next((n for n in state.remote_nodes if n.name == node_name), None)
    if not node:
        raise HTTPException(status_code=404, detail=f"Node '{node_name}' not found")
    
    state.remote_nodes.remove(node)
    
    # Remove from cluster pool
    state.cluster_pool.nodes = [n for n in state.cluster_pool.nodes if n.name != node_name]
    
    return {"status": "success", "message": f"Node '{node_name}' removed"}


# ============================================================================
# TASK MANAGEMENT
# ============================================================================

@router.get("/tasks/submit")
async def submit_task(task: TaskSubmission):
    """Submit a new task for execution"""
    try:
        # Map priority string to enum
        priority_map = {
            "CRITICAL": Priority.CRITICAL,
            "HIGH": Priority.HIGH,
            "NORMAL": Priority.NORMAL,
            "LOW": Priority.LOW
        }
        
        priority = priority_map.get(task.priority.upper(), Priority.NORMAL)
        
        # Submit through cluster if available, otherwise local pool
        if state.cluster_pool:
            task_id = state.cluster_pool.submit_task(
                name=task.name,
                payload=task.payload,
                priority=priority,
                labels=task.labels,
                delay=task.delay,
                context=task.context
            )
        elif state.local_pool:
            task_id = state.local_pool.submit(
                lambda: R.run(task.name, task.payload, task.context),
                priority=priority,
                delay=task.delay,
                name=task.name,
                labels=tuple(task.labels)
            )
        else:
            raise HTTPException(status_code=400, detail="No worker pool available. Initialize a pool first.")
        
        return {
            "status": "success",
            "task_id": task_id,
            "message": f"Task '{task.name}' submitted"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit task: {str(e)}")


@router.get("/tasks/history")
async def get_task_history(limit: int = 50):
    """Get task execution history"""
    return {"history": state.task_history[-limit:]}


@router.get("/tasks/registry")
async def get_registered_tasks():
    """Get list of registered task handlers"""
    tasks = list(R._h.keys()) if hasattr(R, '_h') else []
    return {"tasks": tasks}


# ============================================================================
# SYSTEM MONITORING
# ============================================================================

@router.get("/system/metrics")
async def get_system_metrics():
    """Get current system metrics"""
    try:
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory_percent": psutil.virtual_memory().percent,
            "queue_size": state.local_pool._q.qsize() if state.local_pool else 0
        }
        
        state.system_metrics.append(metrics)
        if len(state.system_metrics) > 100:
            state.system_metrics = state.system_metrics[-100:]
        
        return {"metrics": metrics}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/system/processes")
async def get_process_info():
    """Get top processes by CPU usage"""
    try:
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'num_threads']):
            try:
                info = proc.info
                if info['cpu_percent'] is not None:
                    processes.append(info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        processes.sort(key=lambda x: x.get('cpu_percent', 0) or 0, reverse=True)
        return {"processes": processes[:20]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# RATE LIMITS
# ============================================================================

@router.get("/rate-limits/add")
async def add_rate_limit(config: RateLimitConfig):
    """Add or update a rate limit"""
    if not state.local_pool:
        raise HTTPException(status_code=400, detail="Pool not initialized")
    
    try:
        # from worker_pool import TokenBucket
        state.local_pool.rate_buckets[config.label] = TokenBucket(
            fill_rate=config.fill_rate,
            capacity=float(config.capacity)
        )
        
        return {
            "status": "success",
            "message": f"Rate limit set for label '{config.label}'"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rate-limits")
async def get_rate_limits():
    """Get all configured rate limits"""
    if not state.local_pool:
        return {"rate_limits": {}}
    
    limits = {}
    for label, bucket in getattr(state.local_pool, 'rate_buckets', {}).items():
        limits[label] = {
            "fill_rate": bucket.fill_rate,
            "capacity": bucket.capacity,
            "current_tokens": bucket.tokens
        }
    
    return {"rate_limits": limits}


# ============================================================================
# OLLAMA MONITORING
# ============================================================================

@router.get("/ollama/status")
async def get_ollama_status():
    """Get Ollama process status and API health"""
    try:
        import requests
        
        ollama_processes = []
        total_cpu = 0
        total_memory = 0
        total_threads = 0
        
        # Find Ollama processes
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'num_threads', 'memory_info']):
            try:
                if proc.info['name'] and 'ollama' in proc.info['name'].lower():
                    memory_mb = (proc.info['memory_info'].rss / 1024 / 1024) if proc.info.get('memory_info') else 0
                    
                    ollama_processes.append({
                        'pid': proc.info['pid'],
                        'name': proc.info['name'],
                        'cpu_percent': proc.info['cpu_percent'] or 0,
                        'memory_percent': proc.info['memory_percent'] or 0,
                        'num_threads': proc.info['num_threads'] or 0,
                        'memory_mb': memory_mb
                    })
                    
                    total_cpu += proc.info['cpu_percent'] or 0
                    total_memory += proc.info['memory_percent'] or 0
                    total_threads += proc.info['num_threads'] or 0
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # Check Ollama API health
        api_status = "unknown"
        models = []
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            if response.status_code == 200:
                api_status = "healthy"
                models_data = response.json().get("models", [])
                models = [m.get("name", m.get("model", "")) for m in models_data]
        except Exception:
            api_status = "unavailable"
        
        return {
            "processes": ollama_processes,
            "summary": {
                "process_count": len(ollama_processes),
                "total_cpu": total_cpu,
                "total_memory": total_memory,
                "total_threads": total_threads
            },
            "api_status": api_status,
            "models": models
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# WEBSOCKET ENDPOINTS
# ============================================================================

@router.websocket("/ws/updates")
async def websocket_updates(websocket: WebSocket):
    """WebSocket endpoint for real-time system updates"""
    await manager.connect(websocket)
    try:
        while True:
            await asyncio.sleep(2)
            if state.local_pool:
                try:
                    await websocket.send_json({
                        "type": "status_update",
                        "data": {
                            "queue_size": state.local_pool._q.qsize(),
                            "timestamp": datetime.now().isoformat()
                        }
                    })
                except Exception:
                    break
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)


# ============================================================================
# FOCUS MANAGER
# ============================================================================

@router.get("/focus/set")
async def set_focus(update: FocusUpdate):
    """Set the proactive focus"""
    if not state.focus_manager:
        # Initialize focus manager if not exists
        if state.local_pool:
            state.focus_manager = ProactiveFocusManager(
                agent=state.vera_instance,
                pool=state.local_pool
            )
        else:
            raise HTTPException(status_code=400, detail="Pool not initialized")
    
    try:
        state.focus_manager.set_focus(update.focus)
        state.focus_manager.start()
        
        return {
            "status": "success",
            "message": f"Focus set to: {update.focus}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/focus/status")
async def get_focus_status():
    """Get current focus status"""
    if not state.focus_manager:
        return {"active": False, "focus": None}
    
    return {
        "active": state.focus_manager._running,
        "focus": state.focus_manager.focus,
        "focus_board": state.focus_manager.focus_board if hasattr(state.focus_manager, 'focus_board') else {}
    }


@router.get("/focus/stop")
async def stop_focus():
    """Stop the proactive focus manager"""
    if not state.focus_manager:
        raise HTTPException(status_code=400, detail="Focus manager not initialized")
    
    try:
        state.focus_manager.stop()
        return {"status": "success", "message": "Focus manager stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# STARTUP / SHUTDOWN
# ============================================================================

@router.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    print("=" * 60)
    print("Vera Task Orchestrator API Starting...")
    print("=" * 60)
    
    # Register some example tasks
    @R.register("example.hello")
    def hello_task(payload, context):
        name = payload.get("name", "World")
        return f"Hello, {name}!"
    
    @R.register("example.compute")
    def compute_task(payload, context):
        import time
        duration = payload.get("duration", 1)
        time.sleep(duration)
        return f"Computed for {duration} seconds"
    
    print("Registered example tasks: example.hello, example.compute")
    print("=" * 60)


@router.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    print("Shutting down Vera Task Orchestrator...")
    
    if state.focus_manager and state.focus_manager._running:
        state.focus_manager.stop()
    
    if state.local_pool and state.local_pool._running:
        state.local_pool.stop(wait=True)
    
    print("Shutdown complete")

