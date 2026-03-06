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
# MAIN LOOP REFERENCE (thread-safe broadcasting)
# ============================================================================

_main_loop: Optional[asyncio.AbstractEventLoop] = None


def set_main_loop():
    """
    Capture the running event loop.
    Call this from FastAPI startup (inside an async context).
    """
    global _main_loop
    try:
        _main_loop = asyncio.get_event_loop()
        print(f"[Orchestrator API] ✓ Main event loop captured: {_main_loop}")
    except RuntimeError as e:
        print(f"[Orchestrator API] ✗ Could not capture main event loop: {e}")


def _thread_safe_broadcast(payload: dict):
    """
    Schedule a broadcast from ANY thread (including orchestrator worker threads).
    Uses run_coroutine_threadsafe so it's safe to call from sync code.
    """
    global _main_loop
    if _main_loop is None or _main_loop.is_closed():
        return
    try:
        asyncio.run_coroutine_threadsafe(
            state._broadcast_queue.put(payload),
            _main_loop
        )
    except Exception as e:
        print(f"[Orchestrator API] Broadcast enqueue failed: {e}")


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
        self._lock = threading.Lock()

        # Async broadcast queue — populated from any thread via _thread_safe_broadcast
        self._broadcast_queue: asyncio.Queue = asyncio.Queue()
        self._broadcast_task: Optional[asyncio.Task] = None


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
    description: Optional[str] = None


class TaskCreationTemplate(BaseModel):
    template_id: str
    display_name: str
    task_name: str
    parameters: List[Dict[str, Any]]


class FocusUpdate(BaseModel):
    focus: str


class TaskFilter(BaseModel):
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
# BROADCAST WORKER
# ============================================================================

async def broadcast_worker():
    """Drains the broadcast queue and sends to all WebSocket clients."""
    while True:
        try:
            message = await state._broadcast_queue.get()
            await manager.broadcast(message)
        except Exception as e:
            print(f"[Orchestrator API] Broadcast worker error: {e}")
            await asyncio.sleep(0.1)


# ============================================================================
# TASK TRACKING HELPERS  (all thread-safe)
# ============================================================================

def record_task_submission(task_id: str, task_name: str, payload: dict = None,
                           context: dict = None, description: str = None):
    """Record task submission — THREAD SAFE."""
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

    # Thread-safe broadcast
    _thread_safe_broadcast({
        "type": "task_submitted",
        "data": {
            "task_id": task_id,
            "task_name": task_name,
            "description": description or task_name,
            "timestamp": datetime.now().isoformat()
        }
    })


def record_task_update(task_id: str, status: str, **kwargs):
    """Update task status — THREAD SAFE."""
    with state._lock:
        if task_id in state.active_tasks:
            state.active_tasks[task_id]["status"] = status
            state.active_tasks[task_id].update(kwargs)

            if status in ("completed", "failed", "cancelled"):
                record = state.active_tasks.pop(task_id)
                record["completed_at"] = datetime.now().isoformat()
                state.task_history.append(record)

        elif task_id in state.task_metadata_cache:
            state.task_metadata_cache[task_id]["status"] = status
            state.task_metadata_cache[task_id].update(kwargs)


# ============================================================================
# ORCHESTRATOR EVENT HOOKS
# ============================================================================

def setup_orchestrator_tracking(orchestrator: Orchestrator):
    """
    Hook into orchestrator events to track ALL task submissions and updates.
    All callbacks run in worker threads — must use thread-safe operations only.
    """
    print("[Orchestrator API] Setting up comprehensive task tracking...")

    # ── Wrap task_queue.submit ──────────────────────────────────────────────
    original_submit = orchestrator.task_queue.submit

    def tracked_submit(task_name: str, *args, **kwargs):
        task_id = original_submit(task_name, *args, **kwargs)
        try:
            description = kwargs.get("description", None)
            payload = {}
            if args:
                payload["args"] = str(args)[:100]
            safe_kwargs = {
                k: v for k, v in kwargs.items()
                if k not in ("vera_instance", "description") and not k.startswith("_")
            }
            if safe_kwargs:
                payload["kwargs"] = str(safe_kwargs)[:100]

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

    orchestrator.task_queue.submit = tracked_submit

    # ── Event subscribers ───────────────────────────────────────────────────
    # These run in worker threads — use _thread_safe_broadcast, not create_task

    def on_task_started(msg):
        task_id = msg.get("task_id")
        if task_id:
            record_task_update(
                task_id,
                "running",
                started_at=datetime.now().isoformat(),
                worker_id=msg.get("worker_id")
            )
        _thread_safe_broadcast({"type": "task_started", "data": msg})

    def on_task_completed(msg):
        task_id = msg.get("task_id")
        if task_id:
            record_task_update(
                task_id,
                "completed",
                completed_at=datetime.now().isoformat(),
                duration=msg.get("duration")
            )
        _thread_safe_broadcast({"type": "task_completed", "data": msg})

    def on_task_failed(msg):
        task_id = msg.get("task_id")
        if task_id:
            record_task_update(
                task_id,
                "failed",
                completed_at=datetime.now().isoformat(),
                error=msg.get("error")
            )
        _thread_safe_broadcast({"type": "task_failed", "data": msg})

    orchestrator.event_bus.subscribe("task.started", on_task_started)
    orchestrator.event_bus.subscribe("task.completed", on_task_completed)
    orchestrator.event_bus.subscribe("task.failed", on_task_failed)

    print("[Orchestrator API] ✓ Task tracking hooks installed")


# ============================================================================
# TASK MANAGEMENT ENDPOINTS
# ============================================================================

@router.post("/tasks/submit")
async def submit_task(task: TaskSubmission):
    """Submit a task for execution with enhanced tracking."""
    if not state.orchestrator:
        raise HTTPException(status_code=400, detail="Orchestrator not initialized")
    if not state.vera_instance:
        raise HTTPException(status_code=400, detail="Vera instance not connected")

    try:
        context = task.context.copy()
        context["vera_instance"] = state.vera_instance

        task_id = state.orchestrator.submit_task(
            task.name,
            **task.payload,
            **context
        )

        record_task_submission(task_id, task.name, task.payload, context, task.description)

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


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    with state._lock:
        if task_id not in state.active_tasks:
            raise HTTPException(status_code=404, detail="Task not found or already completed")

    record_task_update(task_id, "cancelled", cancelled_at=datetime.now().isoformat())

    await manager.broadcast({"type": "task_cancelled", "data": {"task_id": task_id}})
    return {"status": "cancelled", "task_id": task_id}


@router.post("/tasks/{task_id}/retry")
async def retry_task(task_id: str):
    if not state.orchestrator:
        raise HTTPException(status_code=400, detail="Orchestrator not initialized")

    original = state.task_metadata_cache.get(task_id)
    if not original:
        raise HTTPException(status_code=404, detail="Original task not found")

    try:
        new_task_id = state.orchestrator.submit_task(original["task_name"])
        record_task_submission(new_task_id, original["task_name"], {}, {}, f"Retry of {task_id[:8]}")
        return {"status": "retried", "original_task_id": task_id, "new_task_id": new_task_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retry failed: {str(e)}")


@router.get("/tasks/{task_id}/status")
async def get_task_status(task_id: str):
    with state._lock:
        if task_id in state.active_tasks:
            return {"task_id": task_id, "source": "active_tracking", **state.active_tasks[task_id]}
        for record in reversed(state.task_history):
            if record["task_id"] == task_id:
                return {"task_id": task_id, "source": "history", **record}

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
            print(f"[Orchestrator API] Orchestrator query failed for {task_id}: {e}")

    raise HTTPException(status_code=404, detail="Task not found in any tracking system")


@router.get("/tasks/result/{task_id}")
async def get_task_result(task_id: str, timeout: float = 5.0):
    if not state.orchestrator:
        raise HTTPException(status_code=400, detail="Orchestrator not initialized")

    try:
        result = state.orchestrator.wait_for_result(task_id, timeout=timeout)
        if not result:
            return {"status": "pending", "task_id": task_id, "message": "Task not completed yet"}

        record_task_update(task_id, result.status.value, duration=result.duration, error=result.error)

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
    results = []
    with state._lock:
        all_tasks = list(state.active_tasks.values()) + list(state.task_history)

    for task in all_tasks:
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

    results.sort(key=lambda x: x.get("submitted_at", ""), reverse=True)
    return {"tasks": results[:filter.limit], "total": len(results), "filtered": True}


@router.get("/tasks/history")
async def get_task_history(limit: int = 50, offset: int = 0):
    with state._lock:
        all_tasks = list(state.active_tasks.values()) + list(state.task_history)

    all_tasks.sort(key=lambda x: x.get("submitted_at", ""), reverse=True)
    paginated = all_tasks[offset:offset + limit]

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
    with state._lock:
        active_list = list(state.active_tasks.values())

    if not active_list and state.orchestrator:
        try:
            stats = state.orchestrator.get_stats()
            queue_sizes = stats.get("queue_sizes", {})
            total_queued = sum(queue_sizes.values())
            if total_queued > 0:
                print(f"[Orchestrator API] WARNING: {total_queued} tasks in queue but no tracking records!")
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

    active_list.sort(key=lambda x: (x.get("priority", "NORMAL"), x.get("submitted_at", "")))

    return {
        "tasks": active_list,
        "count": len(active_list),
        "tracking_active": bool(active_list) or not state.orchestrator
    }


@router.get("/tasks/queue/detailed")
async def get_queue_detailed():
    if not state.orchestrator:
        return {"queues": []}

    stats = state.orchestrator.get_stats()
    queue_sizes = stats.get("queue_sizes", {})
    detailed_queues = []

    for task_type, size in queue_sizes.items():
        pool_stats = stats.get("worker_pools", {}).get(task_type, {})
        num_workers = pool_stats.get("num_workers", 0)
        workers = pool_stats.get("workers", [])
        active_count = sum(1 for w in workers if w.get("current_task"))

        avg_duration = 5.0
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
    templates_response = await get_task_templates()
    template = next((t for t in templates_response["templates"] if t["template_id"] == template_id), None)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    submission = TaskSubmission(
        name=template["task_name"],
        payload=parameters,
        description=description or template["display_name"]
    )
    return await submit_task(submission)


# ============================================================================
# TASK REGISTRY
# ============================================================================

@router.get("/tasks/registry")
async def get_task_registry():
    tasks = []
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

    all_tasks = registry.list_tasks()
    for name in all_tasks:
        if not any(t["name"] == name for t in tasks):
            tasks.append({"name": name, "type": "unknown"})

    return {"tasks": tasks, "count": len(tasks)}


# ============================================================================
# ORCHESTRATOR LIFECYCLE
# ============================================================================

@router.post("/initialize")
async def initialize_orchestrator(config: OrchestratorConfig):
    global _main_loop
    try:
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

        setup_orchestrator_tracking(state.orchestrator)
        state.orchestrator.start()

        # Ensure broadcast worker is running
        if not state._broadcast_task or state._broadcast_task.done():
            state._broadcast_task = asyncio.create_task(broadcast_worker())

        # Capture loop if not already done
        if _main_loop is None:
            set_main_loop()

        print("[Orchestrator API] ✓ Initialized with comprehensive tracking")

        return {
            "status": "success",
            "message": "Orchestrator initialized with comprehensive task tracking",
            "config": config.dict(),
            "tracking_enabled": True
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialize: {str(e)}")


@router.post("/start")
async def start_orchestrator():
    global _main_loop

    if not state.orchestrator:
        print("[Orchestrator API] Orchestrator not initialized, auto-initializing with defaults...")
        try:
            default_config = {
                TaskType.LLM: 3,
                TaskType.TOOL: 4,
                TaskType.WHISPER: 1,
                TaskType.BACKGROUND: 2,
                TaskType.GENERAL: 2
            }
            state.orchestrator = Orchestrator(config=default_config, cpu_threshold=75.0)
            setup_orchestrator_tracking(state.orchestrator)
            print("[Orchestrator API] ✓ Auto-initialized with default config and tracking")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to auto-initialize orchestrator: {str(e)}")

    try:
        if state.orchestrator.running:
            return {"status": "already_running", "message": "Orchestrator is already running"}

        state.orchestrator.start()

        if not state._broadcast_task or state._broadcast_task.done():
            state._broadcast_task = asyncio.create_task(broadcast_worker())

        if _main_loop is None:
            set_main_loop()

        return {"status": "success", "message": "Orchestrator started successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start orchestrator: {str(e)}")


@router.post("/stop")
async def stop_orchestrator():
    if not state.orchestrator:
        raise HTTPException(status_code=400, detail="Orchestrator not initialized")
    try:
        state.orchestrator.stop()
        return {"status": "success", "message": "Orchestrator stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# STATUS & DIAGNOSTICS  (single /status route — duplicate removed)
# ============================================================================

@router.get("/status")
async def get_status():
    if not state.orchestrator:
        return {"initialized": False, "running": False}

    stats = state.orchestrator.get_stats()
    total_workers = 0
    active_workers = 0

    for pool_stats in stats.get("worker_pools", {}).values():
        total_workers += pool_stats.get("num_workers", 0)
        for worker in pool_stats.get("workers", []):
            if worker.get("current_task"):
                active_workers += 1

    queue_sizes = stats.get("queue_sizes", {})
    total_queue = sum(queue_sizes.values())

    with state._lock:
        tracked_active = len(state.active_tasks)
        tracked_history = len(state.task_history)

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
        "tracking_healthy": total_queue == 0 or tracked_active > 0,
        "tracking_diagnostics": {
            "tasks_in_queue": total_queue,
            "tasks_tracked_active": tracked_active,
            "tasks_tracked_history": tracked_history,
            "tracking_mismatch": total_queue > 0 and tracked_active == 0
        }
    }


@router.get("/diagnostics")
async def get_diagnostics():
    if not state.orchestrator:
        return {"error": "Orchestrator not initialized"}

    stats = state.orchestrator.get_stats()
    queue_sizes = stats.get("queue_sizes", {})

    with state._lock:
        active_task_ids = list(state.active_tasks.keys())
        history_count = len(state.task_history)
        cache_count = len(state.task_metadata_cache)

    return {
        "orchestrator_running": stats.get("running", False),
        "queue_sizes": queue_sizes,
        "total_queued": sum(queue_sizes.values()),
        "main_loop_captured": _main_loop is not None and not _main_loop.is_closed(),
        "tracking": {
            "active_tasks_tracked": len(active_task_ids),
            "active_task_ids": active_task_ids[:10],
            "history_count": history_count,
            "cache_count": cache_count,
        },
        "broadcast_task_running": (
            state._broadcast_task is not None and not state._broadcast_task.done()
        ),
        "websocket_connections": len(manager.active_connections)
    }


@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "orchestrator_initialized": state.orchestrator is not None,
        "orchestrator_running": state.orchestrator.running if state.orchestrator else False,
        "vera_connected": state.vera_instance is not None,
        "registered_tasks": len(list(registry._tasks.keys())) if hasattr(registry, "_tasks") else 0,
        "active_tasks": len(state.active_tasks),
        "historical_tasks": len(state.task_history),
        "main_loop_captured": _main_loop is not None and not _main_loop.is_closed(),
        "broadcast_task_running": (
            state._broadcast_task is not None and not state._broadcast_task.done()
        )
    }


# ============================================================================
# WORKER POOLS
# ============================================================================

@router.post("/workers/scale")
async def scale_workers(request: WorkerScaleRequest):
    if not state.orchestrator:
        raise HTTPException(status_code=400, detail="Orchestrator not initialized")

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

    try:
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


# ============================================================================
# SYSTEM METRICS
# ============================================================================

@router.get("/system/metrics")
async def get_system_metrics():
    try:
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()

        queue_size = 0
        if state.orchestrator:
            stats = state.orchestrator.get_stats()
            queue_size = sum(stats.get("queue_sizes", {}).values())

        return {
            "metrics": {
                "timestamp": datetime.now().isoformat(),
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_used_gb": memory.used / (1024 ** 3),
                "memory_total_gb": memory.total / (1024 ** 3),
                "queue_size": queue_size,
                "active_tasks": len(state.active_tasks)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/system/processes")
async def get_system_processes(limit: int = 20):
    try:
        processes = []
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                pinfo = proc.info
                cpu = proc.cpu_percent(interval=0.1)
                mem = proc.memory_percent()
                processes.append({
                    "pid": pinfo["pid"],
                    "name": pinfo["name"],
                    "cpu_percent": cpu,
                    "memory_percent": mem
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

        processes.sort(key=lambda x: x["cpu_percent"], reverse=True)
        return {"processes": processes[:limit], "total": len(processes)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# WEBSOCKET
# ============================================================================

@router.websocket("/ws/updates")
async def websocket_updates(websocket: WebSocket):
    await manager.connect(websocket)

    # Ensure broadcast worker is running
    if not state._broadcast_task or state._broadcast_task.done():
        state._broadcast_task = asyncio.create_task(broadcast_worker())

    # Capture loop here too as a fallback (we're definitely in async context now)
    global _main_loop
    if _main_loop is None:
        set_main_loop()

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

        while True:
            await asyncio.sleep(3)

            if state.orchestrator:
                stats = state.orchestrator.get_stats()
                queue_sizes = stats.get("queue_sizes", {})
                with state._lock:
                    active_count = len(state.active_tasks)

                try:
                    await websocket.send_json({
                        "type": "status_update",
                        "data": {
                            "queue_size": sum(queue_sizes.values()),
                            "queue_sizes": queue_sizes,
                            "active_tasks": active_count,
                            "timestamp": datetime.now().isoformat()
                        }
                    })
                except (WebSocketDisconnect, Exception):
                    break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[Orchestrator API] WebSocket error: {e}")
    finally:
        manager.disconnect(websocket)


# ============================================================================
# PUBLIC INIT HELPER (called from main.py startup)
# ============================================================================

def initialize_orchestrator_api(vera_instance, config: Optional[Dict] = None):
    """
    Initialize orchestrator API with Vera instance.
    Call from FastAPI startup.  Note: async tasks (broadcast_worker) cannot be
    started here — they are started lazily on first /start or WebSocket connect.
    """
    state.vera_instance = vera_instance

    if config is None:
        config = {
            TaskType.LLM: 3,
            TaskType.TOOL: 4,
            TaskType.WHISPER: 1,
            TaskType.BACKGROUND: 2,
            TaskType.GENERAL: 2
        }

    state.orchestrator = Orchestrator(config=config, cpu_threshold=75.0)
    setup_orchestrator_tracking(state.orchestrator)
    state.orchestrator.start()

    print("[Orchestrator API] ✓ Initialized with comprehensive task tracking")
    return state.orchestrator

@router.post("/tasks/clear_stale")
async def clear_stale_tasks():
    """
    Remove completed/failed/cancelled tasks from active tracking that are
    older than 60 seconds. Call this when the UI reconnects after a new session.
    """
    cutoff = (datetime.now() - timedelta(seconds=60)).isoformat()
    cleared = 0
    
    with state._lock:
        stale = [
            tid for tid, task in list(state.active_tasks.items())
            if task.get("status") in ("completed", "failed", "cancelled")
            and task.get("submitted_at", "") < cutoff
        ]
        for tid in stale:
            record = state.active_tasks.pop(tid)
            state.task_history.append(record)
            cleared += 1
    
    return {"cleared": cleared, "active_remaining": len(state.active_tasks)}