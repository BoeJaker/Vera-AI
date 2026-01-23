"""
FastAPI Endpoints for Streaming Orchestrator - Enhanced Version
================================================================
Adds comprehensive task tracking, history, and management capabilities
"""

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import asyncio
import psutil
import json
from collections import deque
import threading
from Vera.Orchestration.orchestration import (
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
# GLOBAL STATE WITH ENHANCED TRACKING
# ============================================================================

class OrchestratorState:
    def __init__(self):
        self.orchestrator: Optional[Orchestrator] = None
        self.vera_instance = None
        self.websocket_connections: List[WebSocket] = []
        
        # Enhanced tracking with thread safety
        self.task_history = deque(maxlen=500)
        self.task_metadata_cache = {}
        self.active_tasks = {}
        self._lock = threading.Lock()  # Thread-safe access
        
        # Event loop for async broadcasts
        self._broadcast_queue = asyncio.Queue()
        self._broadcast_task = None


state = OrchestratorState()


# ============================================================================
# ENHANCED PYDANTIC MODELS
# ============================================================================

class OrchestratorConfig(BaseModel):
    llm_workers: int = 3
    tool_workers: int = 4
    whisper_workers: int = 1
    background_workers: int = 2
    general_workers: int = 2
    cpu_threshold: float = 75.0


class WorkerScaleRequest(BaseModel):
    task_type: str
    num_workers: int


class TaskSubmission(BaseModel):
    name: str
    payload: Dict[str, Any] = {}
    priority: Optional[str] = None
    context: Dict[str, Any] = {}
    description: Optional[str] = None  # Human-readable description


class TaskCreationTemplate(BaseModel):
    """Template for creating common tasks with UI helpers"""
    template_id: str
    display_name: str
    task_name: str
    parameters: List[Dict[str, Any]]  # Parameter definitions


class FocusUpdate(BaseModel):
    focus: str


class TaskFilter(BaseModel):
    """Filters for task history queries"""
    status: Optional[List[str]] = None
    task_type: Optional[List[str]] = None
    task_name: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: int = 100


# ============================================================================
# WEBSOCKET MANAGER
# ============================================================================


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"[Orchestrator API] WebSocket connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            print(f"[Orchestrator API] WebSocket disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Broadcast to all connected clients"""
        if not self.active_connections:
            return
        
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"[Orchestrator API] WebSocket send failed: {e}")
                disconnected.append(connection)
        
        for conn in disconnected:
            self.disconnect(conn)


manager = ConnectionManager()



# ============================================================================
# TASK TRACKING HELPERS
# ============================================================================

def record_task_submission(task_id: str, task_name: str, payload: dict = None, 
                          context: dict = None, description: str = None):
    """Record task submission for history tracking - THREAD SAFE"""
    metadata = registry.get_metadata(task_name)
    
    record = {
        "task_id": task_id,
        "task_name": task_name,
        "status": "queued",
        "submitted_at": datetime.now().isoformat(),
        "description": description or task_name,
        "payload_preview": str(payload)[:200] if payload else "",
        "task_type": metadata.task_type.value if metadata else "unknown",
        "priority": metadata.priority.name if metadata else "NORMAL",
        "estimated_duration": metadata.estimated_duration if metadata else None
    }
    
    with state._lock:
        state.task_metadata_cache[task_id] = record
        state.active_tasks[task_id] = record
    
    # Queue broadcast (async-safe)
    if state._broadcast_queue:
        try:
            asyncio.create_task(state._broadcast_queue.put({
                "type": "task_submitted",
                "data": {
                    "task_id": task_id,
                    "task_name": task_name,
                    "description": description or task_name,
                    "timestamp": datetime.now().isoformat()
                }
            }))
        except:
            pass  # Silently fail if event loop not ready


def record_task_update(task_id: str, status: str, **kwargs):
    """Update task status in tracking - THREAD SAFE"""
    with state._lock:
        if task_id in state.active_tasks:
            state.active_tasks[task_id]["status"] = status
            state.active_tasks[task_id].update(kwargs)
            
            # Move to history if completed/failed/cancelled
            if status in ["completed", "failed", "cancelled"]:
                record = state.active_tasks.pop(task_id)
                record["completed_at"] = datetime.now().isoformat()
                state.task_history.append(record)
        elif task_id in state.task_metadata_cache:
            # Update cache even if not in active
            state.task_metadata_cache[task_id]["status"] = status
            state.task_metadata_cache[task_id].update(kwargs)


def setup_orchestrator_tracking(orchestrator: Orchestrator):
    """
    Setup event hooks to track ALL task submissions and updates.
    This is the KEY fix - we hook into orchestrator events directly.
    """
    print("[Orchestrator API] Setting up comprehensive task tracking...")
    
    # Hook into task queue submissions
    original_submit = orchestrator.task_queue.submit
    
    def tracked_submit(task_name: str, *args, **kwargs):
        """Wrapper to track all task submissions"""
        # Call original submit
        task_id = original_submit(task_name, *args, **kwargs)
        
        # Record in our tracking
        try:
            # Extract description if provided
            description = kwargs.get('description', None)
            
            # Create payload preview (careful with large args)
            payload = {}
            if args:
                payload['args'] = str(args)[:100]
            if kwargs:
                # Filter out vera_instance and other non-serializable
                safe_kwargs = {k: v for k, v in kwargs.items() 
                             if k not in ['vera_instance', 'description'] and 
                             not k.startswith('_')}
                payload['kwargs'] = str(safe_kwargs)[:100]
            
            record_task_submission(
                task_id=task_id,
                task_name=task_name,
                payload=payload,
                context=kwargs,
                description=description
            )
            
            print(f"[Orchestrator API] Tracked submission: {task_name} ({task_id[:8]})")
        except Exception as e:
            print(f"[Orchestrator API] Warning: Failed to track task {task_id}: {e}")
        
        return task_id
    
    # Replace submit method
    orchestrator.task_queue.submit = tracked_submit
    
    # Subscribe to orchestrator events
    def on_task_started(msg):
        task_id = msg.get("task_id")
        if task_id:
            record_task_update(
                task_id, 
                "running",
                started_at=datetime.now().isoformat(),
                worker_id=msg.get("worker_id")
            )
            # Broadcast async
            if state._broadcast_queue:
                try:
                    asyncio.create_task(state._broadcast_queue.put({
                        "type": "task_started",
                        "data": msg
                    }))
                except:
                    pass
    
    def on_task_completed(msg):
        task_id = msg.get("task_id")
        if task_id:
            record_task_update(
                task_id,
                "completed",
                completed_at=datetime.now().isoformat(),
                duration=msg.get("duration")
            )
            # Broadcast async
            if state._broadcast_queue:
                try:
                    asyncio.create_task(state._broadcast_queue.put({
                        "type": "task_completed",
                        "data": msg
                    }))
                except:
                    pass
    
    def on_task_failed(msg):
        task_id = msg.get("task_id")
        if task_id:
            record_task_update(
                task_id,
                "failed",
                completed_at=datetime.now().isoformat(),
                error=msg.get("error")
            )
            # Broadcast async
            if state._broadcast_queue:
                try:
                    asyncio.create_task(state._broadcast_queue.put({
                        "type": "task_failed",
                        "data": msg
                    }))
                except:
                    pass
    
    # Subscribe to events
    orchestrator.event_bus.subscribe("task.started", on_task_started)
    orchestrator.event_bus.subscribe("task.completed", on_task_completed)
    orchestrator.event_bus.subscribe("task.failed", on_task_failed)
    
    print("[Orchestrator API] ✓ Task tracking hooks installed")

# ============================================================================
# ENHANCED TASK MANAGEMENT
# ============================================================================

@router.post("/tasks/submit")
async def submit_task(task: TaskSubmission):
    """Submit a task for execution with enhanced tracking"""
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
        
        # Record submission
        record_task_submission(
            task_id, 
            task.name, 
            task.payload, 
            context,
            task.description
        )
        
        # Broadcast to WebSocket
        await manager.broadcast({
            "type": "task_submitted",
            "data": {
                "task_id": task_id,
                "task_name": task.name,
                "description": task.description or task.name,
                "timestamp": datetime.now().isoformat()
            }
        })
        
        return {
            "status": "success",
            "task_id": task_id,
            "message": f"Task '{task.name}' submitted",
            "description": task.description
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit task: {str(e)}")
    
async def broadcast_worker():
    """Background task to handle async broadcasts"""
    while True:
        try:
            message = await state._broadcast_queue.get()
            await manager.broadcast(message)
        except Exception as e:
            print(f"[Orchestrator API] Broadcast error: {e}")
            await asyncio.sleep(0.1)


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    """Cancel a pending or running task"""
    # Note: Would need orchestrator support for actual cancellation
    # For now, just mark as cancelled in our tracking
    
    if task_id in state.active_tasks:
        record_task_update(task_id, "cancelled", 
                         cancelled_at=datetime.now().isoformat())
        
        await manager.broadcast({
            "type": "task_cancelled",
            "data": {"task_id": task_id}
        })
        
        return {"status": "cancelled", "task_id": task_id}
    
    raise HTTPException(status_code=404, detail="Task not found or already completed")


@router.post("/tasks/{task_id}/retry")
async def retry_task(task_id: str):
    """Retry a failed task"""
    if not state.orchestrator:
        raise HTTPException(status_code=400, detail="Orchestrator not initialized")
    
    # Get original task info
    original = state.task_metadata_cache.get(task_id)
    if not original:
        raise HTTPException(status_code=404, detail="Original task not found")
    
    # Resubmit with same parameters
    try:
        # Would need to store original payload - simplified here
        new_task_id = state.orchestrator.submit_task(original["task_name"])
        
        record_task_submission(
            new_task_id,
            original["task_name"],
            {},
            {},
            f"Retry of {task_id[:8]}"
        )
        
        return {
            "status": "retried",
            "original_task_id": task_id,
            "new_task_id": new_task_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retry failed: {str(e)}")



@router.get("/tasks/{task_id}/status")
async def get_task_status(task_id: str):
    """Get detailed status of a specific task with multiple fallbacks"""
    # Check active tasks first
    with state._lock:
        if task_id in state.active_tasks:
            return {
                "task_id": task_id,
                "source": "active_tracking",
                **state.active_tasks[task_id]
            }
        
        # Check history
        for record in reversed(state.task_history):
            if record["task_id"] == task_id:
                return {
                    "task_id": task_id,
                    "source": "history",
                    **record
                }
    
    # FALLBACK: Check orchestrator result
    if state.orchestrator:
        try:
            result = state.orchestrator.wait_for_result(task_id, timeout=0.1)
            if result:
                return {
                    "task_id": task_id,
                    "source": "orchestrator_result",
                    "status": result.status.value,
                    "result": str(result.result)[:500] if result.result else None,
                    "error": result.error,
                    "duration": result.duration,
                    "is_streaming": result.is_streaming,
                    "started_at": result.started_at,
                    "completed_at": result.completed_at,
                    "worker_id": result.worker_id
                }
        except Exception as e:
            print(f"[Orchestrator API] Failed to query orchestrator for {task_id}: {e}")
    
    raise HTTPException(status_code=404, detail="Task not found in any tracking system")


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
        
        # Update tracking
        record_task_update(
            task_id,
            result.status.value,
            duration=result.duration,
            error=result.error
        )
        
        return {
            "status": result.status.value,
            "task_id": task_id,
            "result": result.result,
            "error": result.error,
            "duration": result.duration,
            "is_streaming": result.is_streaming
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks/history/query")
async def query_task_history(filter: TaskFilter):
    """Query task history with filters"""
    results = []
    
    # Combine active and historical tasks
    all_tasks = list(state.active_tasks.values()) + list(state.task_history)
    
    for task in all_tasks:
        # Apply filters
        if filter.status and task.get("status") not in filter.status:
            continue
        
        if filter.task_type and task.get("task_type") not in filter.task_type:
            continue
        
        if filter.task_name and filter.task_name.lower() not in task.get("task_name", "").lower():
            continue
        
        if filter.start_time:
            task_time = datetime.fromisoformat(task.get("submitted_at", ""))
            if task_time < filter.start_time:
                continue
        
        if filter.end_time:
            task_time = datetime.fromisoformat(task.get("submitted_at", ""))
            if task_time > filter.end_time:
                continue
        
        results.append(task)
        
        if len(results) >= filter.limit:
            break
    
    # Sort by submission time (newest first)
    results.sort(key=lambda x: x.get("submitted_at", ""), reverse=True)
    
    return {
        "tasks": results[:filter.limit],
        "total": len(results),
        "filtered": True
    }



@router.get("/tasks/history")
async def get_task_history(limit: int = 50, offset: int = 0):
    """Get task execution history with enhanced info"""
    with state._lock:
        all_tasks = list(state.active_tasks.values()) + list(state.task_history)
    
    # Sort by time (newest first)
    all_tasks.sort(key=lambda x: x.get("submitted_at", ""), reverse=True)
    
    # Paginate
    paginated = all_tasks[offset:offset+limit]
    
    return {
        "tasks": paginated,
        "total": len(all_tasks),
        "limit": limit,
        "offset": offset,
        "has_more": len(all_tasks) > (offset + limit),
        "active_count": len(state.active_tasks),
        "history_count": len(state.task_history)
    }



@router.get("/tasks/active")
async def get_active_tasks():
    """Get all currently active tasks with fallback to orchestrator query"""
    with state._lock:
        active_list = list(state.active_tasks.values())
    
    # FALLBACK: If empty but orchestrator exists, try to reconstruct from queue
    if not active_list and state.orchestrator:
        try:
            stats = state.orchestrator.get_stats()
            queue_sizes = stats.get("queue_sizes", {})
            
            # If there are queued tasks but we don't have records, create basic entries
            total_queued = sum(queue_sizes.values())
            if total_queued > 0:
                # We have tasks but no tracking - create placeholder
                print(f"[Orchestrator API] WARNING: {total_queued} tasks in queue but no tracking records!")
                
                # Try to peek at orchestrator's internal state
                for task_type, size in queue_sizes.items():
                    if size > 0:
                        active_list.append({
                            "task_id": "unknown",
                            "task_name": "unknown",
                            "status": "queued",
                            "task_type": task_type,
                            "description": f"Untracked {task_type} task",
                            "submitted_at": datetime.now().isoformat(),
                            "warning": "Task tracking was not initialized properly"
                        })
        except Exception as e:
            print(f"[Orchestrator API] Fallback query failed: {e}")
    
    # Sort by priority and submission time
    active_list.sort(key=lambda x: (
        x.get("priority", "NORMAL"),
        x.get("submitted_at", "")
    ))
    
    return {
        "tasks": active_list,
        "count": len(active_list),
        "tracking_active": bool(active_list) or not state.orchestrator
    }




@router.get("/tasks/queue/detailed")
async def get_queue_detailed():
    """Get detailed queue status including position and estimated wait times"""
    if not state.orchestrator:
        return {"queues": []}
    
    stats = state.orchestrator.get_stats()
    queue_sizes = stats.get("queue_sizes", {})
    
    detailed_queues = []
    
    for task_type, size in queue_sizes.items():
        # Get active workers for this type
        pool_stats = stats.get("worker_pools", {}).get(task_type, {})
        num_workers = pool_stats.get("num_workers", 0)
        workers = pool_stats.get("workers", [])
        active_count = sum(1 for w in workers if w.get("current_task"))
        
        # Estimate wait time
        avg_duration = 5.0  # Default estimate
        if workers:
            completed_workers = [w for w in workers if w.get("tasks_completed", 0) > 0]
            if completed_workers:
                total_time = sum(w.get("total_duration", 0) for w in completed_workers)
                total_tasks = sum(w.get("tasks_completed", 0) for w in completed_workers)
                if total_tasks > 0:
                    avg_duration = total_time / total_tasks
        
        estimated_wait = (size / max(num_workers, 1)) * avg_duration if size > 0 else 0
        
        detailed_queues.append({
            "task_type": task_type,
            "queue_size": size,
            "num_workers": num_workers,
            "active_workers": active_count,
            "idle_workers": num_workers - active_count,
            "avg_task_duration": round(avg_duration, 2),
            "estimated_wait_time": round(estimated_wait, 2),
            "throughput_per_min": round((num_workers / avg_duration) * 60, 2) if avg_duration > 0 else 0
        })
    
    return {"queues": detailed_queues}


# ============================================================================
# TASK TEMPLATES
# ============================================================================

@router.get("/tasks/templates")
async def get_task_templates():
    """Get task creation templates for common operations"""
    templates = [
        {
            "template_id": "llm_generation",
            "display_name": "Generate Text (LLM)",
            "task_name": "llm.generate",
            "parameters": [
                {"name": "llm_type", "type": "select", "options": ["fast", "intermediate", "deep", "reasoning"], "default": "fast"},
                {"name": "prompt", "type": "textarea", "placeholder": "Enter your prompt..."},
                {"name": "with_memory", "type": "boolean", "default": False}
            ]
        },
        {
            "template_id": "toolchain",
            "display_name": "Execute Tool Chain",
            "task_name": "toolchain.execute",
            "parameters": [
                {"name": "query", "type": "textarea", "placeholder": "Describe what you want to accomplish..."}
            ]
        },
        {
            "template_id": "memory_search",
            "display_name": "Search Memory",
            "task_name": "memory.search",
            "parameters": [
                {"name": "query", "type": "text", "placeholder": "Search query..."},
                {"name": "top_k", "type": "number", "default": 5, "min": 1, "max": 20}
            ]
        },
        {
            "template_id": "proactive_thought",
            "display_name": "Generate Proactive Thought",
            "task_name": "proactive.generate_thought",
            "parameters": []
        },
        {
            "template_id": "set_focus",
            "display_name": "Set Focus",
            "task_name": "focus.set",
            "parameters": [
                {"name": "focus", "type": "text", "placeholder": "New focus..."}
            ]
        }
    ]
    
    return {"templates": templates}


@router.post("/tasks/submit/template")
async def submit_from_template(template_id: str, parameters: Dict[str, Any], 
                               description: Optional[str] = None):
    """Submit a task using a template"""
    # Get template
    templates_response = await get_task_templates()
    template = next((t for t in templates_response["templates"] 
                    if t["template_id"] == template_id), None)
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Create task submission
    submission = TaskSubmission(
        name=template["task_name"],
        payload=parameters,
        description=description or template["display_name"]
    )
    
    return await submit_task(submission)


# ============================================================================
# TASK REGISTRY ENHANCEMENTS
# ============================================================================

@router.get("/tasks/registry")
async def get_task_registry():
    """Get registered tasks with enhanced metadata"""
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
                    "requires_cpu_cores": metadata.requires_cpu_cores,
                    "memory_mb": metadata.memory_mb,
                    "proactive_focus": metadata.metadata.get("proactive_focus", False),
                    "labels": metadata.labels
                })
    
    # Also get tasks without type filter
    all_tasks = registry.list_tasks()
    for name in all_tasks:
        if not any(t["name"] == name for t in tasks):
            tasks.append({"name": name, "type": "unknown"})
    
    return {"tasks": tasks, "count": len(tasks)}


# ============================================================================
# STATISTICS & ANALYTICS
# ============================================================================

@router.get("/status")
async def get_status():
    """Get orchestrator status with tracking diagnostics"""
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
    
    # Diagnostics
    with state._lock:
        tracked_active = len(state.active_tasks)
        tracked_history = len(state.task_history)
    
    tracking_healthy = (total_queue == 0 or tracked_active > 0)
    
    return {
        "initialized": True,
        "running": stats.get("running", False),
        "worker_count": total_workers,
        "active_workers": active_workers,
        "queue_size": total_queue,
        "queue_sizes": queue_sizes,
        "worker_pools": stats.get("worker_pools", {}),
        "active_task_count": tracked_active,
        "total_history": tracked_history,
        "tracking_healthy": tracking_healthy,
        "tracking_diagnostics": {
            "tasks_in_queue": total_queue,
            "tasks_tracked_active": tracked_active,
            "tasks_tracked_history": tracked_history,
            "tracking_mismatch": total_queue > 0 and tracked_active == 0
        }
    }
# ============================================================================
# ORIGINAL ENDPOINTS (kept for compatibility)
# ============================================================================

@router.post("/initialize")
async def initialize_orchestrator(config: OrchestratorConfig):
    """Initialize the orchestrator with comprehensive tracking"""
    try:
        from Vera.Orchestration.orchestration import TaskType
        
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
        
        # CRITICAL: Setup tracking BEFORE starting
        setup_orchestrator_tracking(state.orchestrator)
        
        # Start the orchestrator
        state.orchestrator.start()
        
        # Start broadcast worker if not already running
        if not state._broadcast_task:
            state._broadcast_task = asyncio.create_task(broadcast_worker())
        
        print("[Orchestrator API] ✓ Initialized with comprehensive tracking")
        
        return {
            "status": "success",
            "message": "Orchestrator initialized with comprehensive task tracking",
            "config": {
                "llm_workers": config.llm_workers,
                "tool_workers": config.tool_workers,
                "whisper_workers": config.whisper_workers,
                "background_workers": config.background_workers,
                "general_workers": config.general_workers,
                "cpu_threshold": config.cpu_threshold
            },
            "tracking_enabled": True
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialize: {str(e)}")



async def _handle_task_started(msg):
    """Handle task started event"""
    task_id = msg.get("task_id")
    if task_id:
        record_task_update(task_id, "running", 
                         started_at=datetime.now().isoformat(),
                         worker_id=msg.get("worker_id"))
    
    await manager.broadcast({"type": "task_started", "data": msg})


async def _handle_task_completed(msg):
    """Handle task completed event"""
    task_id = msg.get("task_id")
    if task_id:
        record_task_update(task_id, "completed",
                         completed_at=datetime.now().isoformat(),
                         duration=msg.get("duration"))
    
    await manager.broadcast({"type": "task_completed", "data": msg})


async def _handle_task_failed(msg):
    """Handle task failed event"""
    task_id = msg.get("task_id")
    if task_id:
        record_task_update(task_id, "failed",
                         completed_at=datetime.now().isoformat(),
                         error=msg.get("error"))
    
    await manager.broadcast({"type": "task_failed", "data": msg})


@router.post("/start")
async def start_orchestrator():
    """Start the orchestrator (auto-initializes if needed)"""
    
    # Auto-initialize with defaults if not initialized
    if not state.orchestrator:
        print("[Orchestrator API] Orchestrator not initialized, initializing with defaults...")
        
        try:
            from Vera.Orchestration.orchestration import TaskType
            
            default_config = {
                TaskType.LLM: 3,
                TaskType.TOOL: 4,
                TaskType.WHISPER: 1,
                TaskType.BACKGROUND: 2,
                TaskType.GENERAL: 2
            }
            
            state.orchestrator = Orchestrator(
                config=default_config,
                cpu_threshold=75.0
            )
            
            # CRITICAL: Setup tracking
            setup_orchestrator_tracking(state.orchestrator)
            
            print("[Orchestrator API] ✓ Auto-initialized with default config")
            
        except Exception as e:
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to auto-initialize orchestrator: {str(e)}"
            )
    
    # Now start it
    try:
        if state.orchestrator.running:
            return {
                "status": "already_running",
                "message": "Orchestrator is already running"
            }
        
        state.orchestrator.start()
        
        # Start broadcast worker if not running
        if not state._broadcast_task or state._broadcast_task.done():
            state._broadcast_task = asyncio.create_task(broadcast_worker())
        
        return {
            "status": "success",
            "message": "Orchestrator started successfully"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start orchestrator: {str(e)}"
        )

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
        "worker_pools": stats.get("worker_pools", {}),
        "active_task_count": len(state.active_tasks),
        "total_history": len(state.task_history)
    }


@router.post("/workers/scale")
async def scale_workers(request: WorkerScaleRequest):
    """Scale a worker pool"""
    if not state.orchestrator:
        raise HTTPException(status_code=400, detail="Orchestrator not initialized")
    
    try:
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
        
        active_count = sum(1 for w in workers if w.get("current_task"))
        utilization = (active_count / num_workers * 100) if num_workers > 0 else 0
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


@router.get("/system/metrics")
async def get_system_metrics():
    """Get system metrics"""
    try:
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        
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
                "queue_size": queue_size,
                "active_tasks": len(state.active_tasks)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "orchestrator_initialized": state.orchestrator is not None,
        "orchestrator_running": state.orchestrator.running if state.orchestrator else False,
        "vera_connected": state.vera_instance is not None,
        "registered_tasks": len(list(registry._tasks.keys())) if hasattr(registry, '_tasks') else 0,
        "active_tasks": len(state.active_tasks),
        "historical_tasks": len(state.task_history)
    }


@router.websocket("/ws/updates")
async def websocket_updates(websocket: WebSocket):
    """WebSocket for real-time updates with enhanced status"""
    await manager.connect(websocket)
    
    try:
        # Send initial status
        if state.orchestrator:
            stats = state.orchestrator.get_stats()
            queue_sizes = stats.get("queue_sizes", {})
            
            with state._lock:
                active_count = len(state.active_tasks)
            
            await websocket.send_json({
                "type": "initial_status",
                "data": {
                    "queue_size": sum(queue_sizes.values()),
                    "queue_sizes": queue_sizes,
                    "active_tasks": active_count,
                    "tracking_active": True,
                    "timestamp": datetime.now().isoformat()
                }
            })
        
        # Keep connection alive and send periodic updates
        while True:
            await asyncio.sleep(3)
            
            if state.orchestrator:
                stats = state.orchestrator.get_stats()
                queue_sizes = stats.get("queue_sizes", {})
                
                with state._lock:
                    active_count = len(state.active_tasks)
                
                await websocket.send_json({
                    "type": "status_update",
                    "data": {
                        "queue_size": sum(queue_sizes.values()),
                        "queue_sizes": queue_sizes,
                        "active_tasks": active_count,
                        "timestamp": datetime.now().isoformat()
                    }
                })
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"[Orchestrator API] WebSocket error: {e}")
        manager.disconnect(websocket)


@router.get("/system/processes")
async def get_system_processes(limit: int = 20):
    """Get top system processes by CPU usage"""
    try:
        processes = []
        
        # Get CPU percent for each process (this is slow so we cache it)
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                # Get process info
                pinfo = proc.info
                cpu = proc.cpu_percent(interval=0.1)
                mem = proc.memory_percent()
                
                processes.append({
                    "pid": pinfo['pid'],
                    "name": pinfo['name'],
                    "cpu_percent": cpu,
                    "memory_percent": mem
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        # Sort by CPU usage
        processes.sort(key=lambda x: x['cpu_percent'], reverse=True)
        
        return {
            "processes": processes[:limit],
            "total": len(processes)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def initialize_orchestrator_api(vera_instance, config: Optional[Dict] = None):
    """
    Initialize orchestrator API with Vera instance.
    Call this from FastAPI startup with comprehensive tracking.
    """
    from Vera.Orchestration.orchestration import TaskType
    
    state.vera_instance = vera_instance
    
    if config is None:
        config = {
            TaskType.LLM: 3,
            TaskType.TOOL: 4,
            TaskType.WHISPER: 1,
            TaskType.BACKGROUND: 2,
            TaskType.GENERAL: 2
        }
    
    state.orchestrator = Orchestrator(
        config=config,
        cpu_threshold=75.0
    )
    
    # CRITICAL: Setup tracking BEFORE starting
    setup_orchestrator_tracking(state.orchestrator)
    
    state.orchestrator.start()
    
    print("[Orchestrator API] ✓ Initialized with comprehensive task tracking")
    
    return state.orchestrator

@router.get("/diagnostics")
async def get_diagnostics():
    """Diagnostic endpoint to debug tracking issues"""
    if not state.orchestrator:
        return {"error": "Orchestrator not initialized"}
    
    stats = state.orchestrator.get_stats()
    queue_sizes = stats.get("queue_sizes", {})
    
    with state._lock:
        active_tasks_list = list(state.active_tasks.keys())
        history_count = len(state.task_history)
        cache_count = len(state.task_metadata_cache)
    
    return {
        "orchestrator_running": stats.get("running", False),
        "queue_sizes": queue_sizes,
        "total_queued": sum(queue_sizes.values()),
        "tracking": {
            "active_tasks_tracked": len(active_tasks_list),
            "active_task_ids": active_tasks_list[:10],  # First 10
            "history_count": history_count,
            "cache_count": cache_count,
        },
        "tracking_installed": hasattr(state.orchestrator.task_queue.submit, '__wrapped__'),
        "broadcast_task_running": state._broadcast_task is not None and not state._broadcast_task.done(),
        "websocket_connections": len(manager.active_connections)
    }