"""
Integration layer for existing API endpoints
"""

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import asyncio

from .core import UnifiedOrchestrator, OrchestratorConfig
from .tasks import Task, TaskType, TaskPriority, TaskRequirements
from .resources import APIQuota


# Pydantic models for API requests
class TaskSubmitRequest(BaseModel):
    """Request model for task submission"""
    type: str
    payload: Dict[str, Any]
    priority: str = "normal"
    max_retries: int = 3
    metadata: Dict[str, Any] = {}


class LLMRequestModel(BaseModel):
    """Request model for LLM requests"""
    prompt: str
    model: Optional[str] = None
    system: Optional[str] = None
    temperature: float = 0.7
    prefer_ollama: bool = True
    priority: str = "normal"


class ToolCallRequest(BaseModel):
    """Request model for tool calls"""
    tool_name: str
    tool_input: Dict[str, Any]
    priority: str = "normal"


class RegisterLLMAPIRequest(BaseModel):
    """Request model for registering LLM API"""
    api_type: str
    api_key: str
    rate_limit_per_minute: int = 60
    cost_per_1k_tokens: float = 0.0
    quota_requests_per_day: Optional[int] = None
    quota_tokens_per_day: Optional[int] = None
    quota_cost_limit_per_day: Optional[float] = None


class RegisterRemoteWorkerRequest(BaseModel):
    """Request model for registering remote worker"""
    remote_url: str
    worker_id: Optional[str] = None
    auth_token: Optional[str] = None


# Global orchestrator instance
_orchestrator: Optional[UnifiedOrchestrator] = None


def get_orchestrator() -> UnifiedOrchestrator:
    """Get the global orchestrator instance"""
    global _orchestrator
    if _orchestrator is None:
        raise RuntimeError("Orchestrator not initialized")
    return _orchestrator


async def initialize_orchestrator(config: Optional[OrchestratorConfig] = None):
    """Initialize the global orchestrator instance"""
    global _orchestrator
    if _orchestrator is not None:
        raise RuntimeError("Orchestrator already initialized")

    _orchestrator = UnifiedOrchestrator(config)
    await _orchestrator.start()


async def shutdown_orchestrator():
    """Shutdown the global orchestrator instance"""
    global _orchestrator
    if _orchestrator is not None:
        await _orchestrator.stop()
        _orchestrator = None


def register_routes(app: FastAPI, prefix: str = "/api/v2/orchestrator"):
    """
    Register orchestrator API routes with FastAPI app

    Args:
        app: FastAPI application
        prefix: URL prefix for routes
    """

    @app.on_event("startup")
    async def startup_event():
        """Initialize orchestrator on startup"""
        await initialize_orchestrator()

    @app.on_event("shutdown")
    async def shutdown_event():
        """Shutdown orchestrator on shutdown"""
        await shutdown_orchestrator()

    @app.get(f"{prefix}/health")
    async def health_check():
        """Health check endpoint"""
        try:
            orchestrator = get_orchestrator()
            return {
                "status": "healthy" if orchestrator.is_running else "stopped",
                "version": "2.0.0"
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"status": "unhealthy", "error": str(e)}
            )

    @app.get(f"{prefix}/status")
    async def get_status():
        """Get orchestrator status"""
        try:
            orchestrator = get_orchestrator()
            return orchestrator.get_status()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post(f"{prefix}/tasks/submit")
    async def submit_task(request: TaskSubmitRequest):
        """Submit a task to the orchestrator"""
        try:
            orchestrator = get_orchestrator()

            # Parse task type
            try:
                task_type = TaskType(request.type)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid task type: {request.type}")

            # Parse priority
            try:
                priority = TaskPriority[request.priority.upper()]
            except KeyError:
                raise HTTPException(status_code=400, detail=f"Invalid priority: {request.priority}")

            # Create task
            task = Task(
                type=task_type,
                priority=priority,
                payload=request.payload,
                max_retries=request.max_retries,
                metadata=request.metadata,
            )

            # Submit task (non-blocking)
            await orchestrator.submit_task(task, wait=False)

            return {
                "task_id": task.id,
                "status": "submitted",
                "message": "Task submitted successfully"
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post(f"{prefix}/tasks/execute")
    async def execute_task(request: TaskSubmitRequest):
        """Execute a task and wait for result"""
        try:
            orchestrator = get_orchestrator()

            # Parse task type
            try:
                task_type = TaskType(request.type)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid task type: {request.type}")

            # Parse priority
            try:
                priority = TaskPriority[request.priority.upper()]
            except KeyError:
                raise HTTPException(status_code=400, detail=f"Invalid priority: {request.priority}")

            # Create task
            task = Task(
                type=task_type,
                priority=priority,
                payload=request.payload,
                max_retries=request.max_retries,
                metadata=request.metadata,
            )

            # Submit and wait for result
            result = await orchestrator.submit_task(task, wait=True)

            return {
                "task_id": task.id,
                "success": result.success,
                "data": result.data,
                "error": result.error,
                "metrics": result.metrics,
                "execution_time_ms": result.execution_time_ms,
                "worker_id": result.worker_id,
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post(f"{prefix}/llm/request")
    async def llm_request(request: LLMRequestModel):
        """Execute an LLM request"""
        try:
            orchestrator = get_orchestrator()

            # Parse priority
            try:
                priority = TaskPriority[request.priority.upper()]
            except KeyError:
                priority = TaskPriority.NORMAL

            # Execute LLM request
            result = await orchestrator.execute_llm_request(
                prompt=request.prompt,
                model=request.model,
                system=request.system,
                temperature=request.temperature,
                prefer_ollama=request.prefer_ollama,
                priority=priority,
            )

            return {
                "success": result.success,
                "response": result.data,
                "error": result.error,
                "metrics": result.metrics,
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post(f"{prefix}/tools/execute")
    async def execute_tool(request: ToolCallRequest):
        """Execute a tool call"""
        try:
            orchestrator = get_orchestrator()

            # Parse priority
            try:
                priority = TaskPriority[request.priority.upper()]
            except KeyError:
                priority = TaskPriority.NORMAL

            # Execute tool call
            result = await orchestrator.execute_tool_call(
                tool_name=request.tool_name,
                tool_input=request.tool_input,
                priority=priority,
            )

            return {
                "success": result.success,
                "result": result.data,
                "error": result.error,
                "metrics": result.metrics,
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get(f"{prefix}/tasks/history")
    async def get_task_history(
        limit: int = 100,
        status: Optional[str] = None
    ):
        """Get task history"""
        try:
            orchestrator = get_orchestrator()

            # Parse status filter
            status_filter = None
            if status:
                from .tasks import TaskStatus
                try:
                    status_filter = TaskStatus(status)
                except ValueError:
                    raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

            history = orchestrator.get_task_history(
                limit=limit,
                status_filter=status_filter
            )

            return {
                "tasks": history,
                "count": len(history)
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post(f"{prefix}/workers/llm-api/register")
    async def register_llm_api(request: RegisterLLMAPIRequest):
        """Register an LLM API worker"""
        try:
            orchestrator = get_orchestrator()

            # Create quota if specified
            quota = None
            if any([
                request.quota_requests_per_day,
                request.quota_tokens_per_day,
                request.quota_cost_limit_per_day
            ]):
                quota = APIQuota(
                    requests_per_day=request.quota_requests_per_day or 86400,
                    tokens_per_day=request.quota_tokens_per_day,
                    cost_limit_per_day=request.quota_cost_limit_per_day,
                )

            # Register worker
            worker_id = await orchestrator.register_llm_api(
                api_type=request.api_type,
                api_key=request.api_key,
                rate_limit_per_minute=request.rate_limit_per_minute,
                cost_per_1k_tokens=request.cost_per_1k_tokens,
                quota=quota,
            )

            return {
                "worker_id": worker_id,
                "status": "registered",
                "message": f"{request.api_type} API worker registered successfully"
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post(f"{prefix}/workers/remote/register")
    async def register_remote_worker(request: RegisterRemoteWorkerRequest):
        """Register a remote worker"""
        try:
            orchestrator = get_orchestrator()

            worker_id = await orchestrator.register_remote_worker(
                remote_url=request.remote_url,
                worker_id=request.worker_id,
                auth_token=request.auth_token,
            )

            return {
                "worker_id": worker_id,
                "status": "registered",
                "message": "Remote worker registered successfully"
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get(f"{prefix}/workers/list")
    async def list_workers():
        """List all workers"""
        try:
            orchestrator = get_orchestrator()
            return orchestrator.worker_registry.to_dict()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get(f"{prefix}/resources/stats")
    async def get_resource_stats():
        """Get resource statistics"""
        try:
            orchestrator = get_orchestrator()
            return orchestrator.resource_manager.get_resource_stats()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.websocket(f"{prefix}/ws/status")
    async def websocket_status(websocket: WebSocket):
        """WebSocket endpoint for real-time status updates"""
        await websocket.accept()

        try:
            orchestrator = get_orchestrator()

            while True:
                # Send status update
                status = orchestrator.get_status()
                await websocket.send_json(status)

                # Wait before next update
                await asyncio.sleep(2.0)

        except Exception as e:
            print(f"WebSocket error: {e}")
        finally:
            try:
                await websocket.close()
            except:
                pass
