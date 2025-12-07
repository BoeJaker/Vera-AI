"""
Toolchain API Module

This module provides a set of APIs for managing and monitoring toolchain executions
within the Vera ChatUI application. It includes endpoints for executing tools, 
managing toolchain sessions, broadcasting updates via WebSocket, and retrieving 
execution statistics.

Key Features:
- Toolchain execution with real-time monitoring and broadcasting.
- WebSocket support for live updates on toolchain progress.
- RESTful endpoints for managing toolchain sessions, tools, and executions.
- Analytics and statistics for toolchain usage and performance.

"""
import asyncio
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

import logging
from fastapi import APIRouter, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocket

# ============================================================
# Global state references
# ============================================================
from Vera.ChatUI.api.session import sessions, toolchain_executions, active_toolchains, websocket_connections, get_or_create_vera
from Vera.ChatUI.api.schemas import ToolchainRequest

# ============================================================
# Logging setup
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# Router setup
# ============================================================
router = APIRouter(prefix="/api/toolchain", tags=["toolchain"])
wsrouter = APIRouter(prefix="/ws/toolchain", tags=["wstoolchain"])

# ============================================================
# CRITICAL: Store reference to main event loop
# ============================================================
_main_loop = None

def set_main_loop():
    """Call this from your FastAPI startup to capture the main loop"""
    global _main_loop
    try:
        _main_loop = asyncio.get_event_loop()
        logger.info(f"Captured main event loop: {_main_loop}")
    except RuntimeError:
        logger.warning("Could not capture main event loop")

# ============================================================
# Thread-safe WebSocket Broadcasting (FIXED for worker threads)
# ============================================================

def schedule_broadcast(session_id: str, event_type: str, data: Dict[str, Any]):
    """
    Schedule a broadcast event on the main event loop.
    Thread-safe - works from ANY thread including orchestrator workers.
    """
    global _main_loop
    
    async def _broadcast():
        if session_id in websocket_connections:
            disconnected = []
            for websocket in websocket_connections[session_id]:
                try:
                    await websocket.send_json({
                        "type": event_type,
                        "data": data,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                except Exception as e:
                    logger.warning(f"Failed to send to websocket: {e}")
                    disconnected.append(websocket)
            
            # Clean up disconnected websockets
            for ws in disconnected:
                websocket_connections[session_id].remove(ws)
    
    # Use the captured main loop, not get_event_loop() which won't work from worker threads
    if _main_loop and not _main_loop.is_closed():
        try:
            # This works from ANY thread
            asyncio.run_coroutine_threadsafe(_broadcast(), _main_loop)
        except Exception as e:
            logger.error(f"Failed to schedule broadcast: {e}")
    else:
        logger.warning(f"Main loop not available for broadcast: {event_type}")


# ============================================================
# Toolchain Endpoints
# ============================================================
@router.get("/{session_id}/tool/{tool_name}/schema")
async def get_tool_schema(session_id: str, tool_name: str):
    """Get the input schema for a specific tool."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    # Find the tool
    tool = next((t for t in vera.tools if t.name == tool_name), None)
    
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool not found: {tool_name}")
    
    # Extract schema information
    schema_info = {
        "name": tool.name,
        "description": tool.description if hasattr(tool, "description") else "",
        "parameters": []
    }
    
    # Get args_schema if available
    if hasattr(tool, "args_schema") and tool.args_schema:
        schema = tool.args_schema.schema()
        
        for field_name, field_info in schema.get("properties", {}).items():
            param = {
                "name": field_name,
                "type": field_info.get("type", "string"),
                "description": field_info.get("description", ""),
                "required": field_name in schema.get("required", []),
                "default": field_info.get("default")
            }
            schema_info["parameters"].append(param)
    else:
        # Fallback for tools without schema - single input field
        schema_info["parameters"] = [{
            "name": "input",
            "type": "string",
            "description": "Tool input",
            "required": True,
            "default": None
        }]
    
    return schema_info


def create_toolchain_execution(session_id: str, query: str) -> str:
    """Create a new toolchain execution record."""
    execution_id = str(uuid.uuid4())
    
    toolchain_executions[session_id][execution_id] = {
        "execution_id": execution_id,
        "session_id": session_id,
        "query": query,
        "plan": [],
        "steps": [],
        "status": "planning",
        "start_time": datetime.utcnow().isoformat(),
        "end_time": None,
        "total_steps": 0,
        "completed_steps": 0,
        "final_result": None
    }
    
    active_toolchains[session_id] = execution_id
    
    return execution_id


def update_toolchain_plan(session_id: str, execution_id: str, plan: List[Dict[str, str]]):
    """Update the plan for a toolchain execution."""
    if session_id in toolchain_executions and execution_id in toolchain_executions[session_id]:
        toolchain_executions[session_id][execution_id]["plan"] = plan
        toolchain_executions[session_id][execution_id]["total_steps"] = len(plan)
        toolchain_executions[session_id][execution_id]["status"] = "executing"


def add_toolchain_step(session_id: str, execution_id: str, step_number: int, 
                       tool_name: str, tool_input: str):
    """Add a new step to toolchain execution."""
    if session_id in toolchain_executions and execution_id in toolchain_executions[session_id]:
        step = {
            "step_number": step_number,
            "tool_name": tool_name,
            "tool_input": tool_input,
            "tool_output": None,
            "status": "running",
            "start_time": datetime.utcnow().isoformat(),
            "end_time": None,
            "error": None,
            "metadata": {}
        }
        toolchain_executions[session_id][execution_id]["steps"].append(step)
        return step
    return None


def update_toolchain_step(session_id: str, execution_id: str, step_number: int,
                          output: Optional[str] = None, error: Optional[str] = None,
                          status: str = "completed"):
    """Update a toolchain execution step."""
    if session_id in toolchain_executions and execution_id in toolchain_executions[session_id]:
        steps = toolchain_executions[session_id][execution_id]["steps"]
        for step in steps:
            if step["step_number"] == step_number:
                step["tool_output"] = output
                step["error"] = error
                step["status"] = status
                step["end_time"] = datetime.utcnow().isoformat()
                
                if status == "completed":
                    toolchain_executions[session_id][execution_id]["completed_steps"] += 1
                
                return step
    return None


def complete_toolchain_execution(session_id: str, execution_id: str, 
                                 final_result: str, status: str = "completed"):
    """Mark toolchain execution as complete."""
    if session_id in toolchain_executions and execution_id in toolchain_executions[session_id]:
        toolchain_executions[session_id][execution_id]["status"] = status
        toolchain_executions[session_id][execution_id]["end_time"] = datetime.utcnow().isoformat()
        toolchain_executions[session_id][execution_id]["final_result"] = final_result
        
        if session_id in active_toolchains:
            del active_toolchains[session_id]


class MonitoredToolChainPlanner:
    """Wrapper around Vera's ToolChainPlanner that captures execution data."""
    
    def __init__(self, original_planner, session_id: str):
        self.original_planner = original_planner
        self.session_id = session_id
        self.execution_id = None
    
    def execute_tool_chain(self, query: str, plan=None):
        """Monitored version of execute_tool_chain with thread-safe broadcasting."""
        # Create execution record
        self.execution_id = create_toolchain_execution(self.session_id, query)
        
        try:
            # Broadcast execution started (thread-safe)
            schedule_broadcast(
                self.session_id,
                "execution_started",
                {"execution_id": self.execution_id, "query": query}
            )
            
            # Generate plan
            if plan is None:
                schedule_broadcast(
                    self.session_id,
                    "status",
                    {"status": "planning"}
                )
                
                gen = self.original_planner.plan_tool_chain(query)
                plan_chunks = []
                for chunk in gen:
                    plan_chunks.append(chunk)
                    if isinstance(chunk, str):
                        schedule_broadcast(
                            self.session_id,
                            "plan_chunk",
                            {"chunk": chunk}
                        )
                        yield chunk
                    elif isinstance(chunk, list):
                        # Final plan
                        update_toolchain_plan(self.session_id, self.execution_id, chunk)
                        schedule_broadcast(
                            self.session_id,
                            "plan",
                            {"plan": chunk, "total_steps": len(chunk)}
                        )
                        plan = chunk
                        yield chunk
            else:
                update_toolchain_plan(self.session_id, self.execution_id, plan)
            
            # Execute plan
            schedule_broadcast(
                self.session_id,
                "status",
                {"status": "executing"}
            )
            
            step_num = 0
            for step in plan:
                step_num += 1
                tool_name = step.get("tool")
                tool_input = str(step.get("input", ""))
                
                # Add step to monitoring
                add_toolchain_step(self.session_id, self.execution_id, step_num, 
                                  tool_name, tool_input)
                
                schedule_broadcast(
                    self.session_id,
                    "step_started",
                    {
                        "step_number": step_num,
                        "tool_name": tool_name,
                        "tool_input": tool_input,
                        "execution_id": self.execution_id
                    }
                )
                
                # Find tool
                tool = next((t for t in self.original_planner.tools if t.name == tool_name), None)
                
                if not tool:
                    error_msg = f"Tool not found: {tool_name}"
                    update_toolchain_step(self.session_id, self.execution_id, step_num,
                                        error=error_msg, status="failed")
                    schedule_broadcast(
                        self.session_id,
                        "step_failed",
                        {"step_number": step_num, "error": error_msg}
                    )
                    yield error_msg
                    continue
                
                # Resolve placeholders in tool_input
                if "{prev}" in tool_input and step_num > 1:
                    prev_step = toolchain_executions[self.session_id][self.execution_id]["steps"][step_num-2]
                    tool_input = tool_input.replace("{prev}", str(prev_step.get("tool_output", "")))
                
                for i in range(1, step_num):
                    prev_step = toolchain_executions[self.session_id][self.execution_id]["steps"][i-1]
                    tool_input = tool_input.replace(f"{{step_{i}}}", str(prev_step.get("tool_output", "")))
                
                # Execute tool
                try:
                    if hasattr(tool, "run") and callable(tool.run):
                        func = tool.run
                    elif hasattr(tool, "func") and callable(tool.func):
                        func = tool.func
                    elif callable(tool):
                        func = tool
                    else:
                        raise ValueError(f"Tool is not callable")
                    
                    collected = []
                    result = ""
                    try:
                        for r in func(tool_input):
                            collected.append(r)
                            # Broadcast each chunk (now works from worker threads!)
                            schedule_broadcast(
                                self.session_id,
                                "step_output",
                                {"step_number": step_num, "chunk": str(r)}
                            )
                            yield r
                    except TypeError:
                        result = func(tool_input)
                        schedule_broadcast(
                            self.session_id,
                            "step_output",
                            {"step_number": step_num, "chunk": str(result)}
                        )
                        yield result
                    else:
                        result = "".join(str(c) for c in collected)
                    
                    # Update step as completed
                    update_toolchain_step(self.session_id, self.execution_id, step_num,
                                        output=result, status="completed")
                    
                    schedule_broadcast(
                        self.session_id,
                        "step_completed",
                        {"step_number": step_num, "output": result[:500]}  # Truncate long outputs
                    )
                    
                except Exception as e:
                    error_msg = f"Error executing {tool_name}: {str(e)}"
                    update_toolchain_step(self.session_id, self.execution_id, step_num,
                                        error=error_msg, status="failed")
                    schedule_broadcast(
                        self.session_id,
                        "step_failed",
                        {"step_number": step_num, "error": error_msg}
                    )
                    yield error_msg
            
            # Get final result
            final_result = ""
            if toolchain_executions[self.session_id][self.execution_id]["steps"]:
                final_result = toolchain_executions[self.session_id][self.execution_id]["steps"][-1].get("tool_output", "")
            
            complete_toolchain_execution(self.session_id, self.execution_id, 
                                       final_result, "completed")
            
            schedule_broadcast(
                self.session_id,
                "execution_completed",
                {"final_result": final_result[:500]}
            )
            
            return final_result
            
        except Exception as e:
            logger.error(f"Toolchain execution error: {e}", exc_info=True)
            complete_toolchain_execution(self.session_id, self.execution_id, 
                                       str(e), "failed")
            
            schedule_broadcast(
                self.session_id,
                "execution_failed",
                {"error": str(e)}
            )
            raise


# ============================================================
# Toolchain Monitoring Endpoints
# ============================================================
@router.post("/{session_id}/execute-tool")
async def execute_single_tool(session_id: str, tool_name: str, tool_input: str):
    """Execute a single tool directly."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    try:
        tool = next((t for t in vera.tools if t.name == tool_name), None)
        
        if not tool:
            raise HTTPException(status_code=404, detail=f"Tool not found: {tool_name}")
        
        start_time = datetime.utcnow()
        
        # Parse tool_input as JSON if it looks like JSON
        try:
            input_data = json.loads(tool_input)
        except (json.JSONDecodeError, TypeError):
            input_data = tool_input
        
        # Execute using LangChain's tool.run() method
        output = ""
        try:
            if isinstance(input_data, dict):
                result = tool.run(input_data)
            else:
                result = tool.run(input_data)
            
            # Handle generator vs direct return
            if hasattr(result, '__iter__') and not isinstance(result, (str, bytes)):
                for chunk in result:
                    output += str(chunk)
            else:
                output = str(result)
                
        except Exception as e:
            logger.warning(f"tool.run() failed, trying direct function call: {e}")
            
            if hasattr(tool, "func") and callable(tool.func):
                func = tool.func
                
                if isinstance(input_data, dict):
                    result = func(**input_data)
                else:
                    result = func(input_data)
                
                if hasattr(result, '__iter__') and not isinstance(result, (str, bytes)):
                    for chunk in result:
                        output += str(chunk)
                else:
                    output = str(result)
            else:
                raise
        
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds() * 1000
        
        return {
            "success": True,
            "tool_name": tool_name,
            "input": tool_input,
            "output": output,
            "duration_ms": duration,
            "executed_at": start_time.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Tool execution error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute")
async def execute_toolchain(request: ToolchainRequest):
    """Execute a toolchain with full monitoring."""
    if request.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(request.session_id)
    execution_id = create_toolchain_execution(request.session_id, request.query)
    
    try:
        def run_toolchain():
            try:
                toolchain = vera.toolchain
                
                # Generate plan
                plan_gen = toolchain.plan_tool_chain(request.query)
                plan_json = ""
                for chunk in plan_gen:
                    if isinstance(chunk, list):
                        update_toolchain_plan(request.session_id, execution_id, chunk)
                        break
                    plan_json += str(chunk)
                
                # Execute the plan
                step_num = 0
                final_result = ""
                
                for step in toolchain_executions[request.session_id][execution_id]["plan"]:
                    step_num += 1
                    tool_name = step.get("tool")
                    tool_input = step.get("input", "")
                    
                    add_toolchain_step(request.session_id, execution_id, step_num, 
                                      tool_name, tool_input)
                    
                    tool = next((t for t in vera.tools if t.name == tool_name), None)
                    
                    if not tool:
                        update_toolchain_step(request.session_id, execution_id, step_num,
                                            error=f"Tool not found: {tool_name}",
                                            status="failed")
                        continue
                    
                    try:
                        if hasattr(tool, "run") and callable(tool.run):
                            func = tool.run
                        elif hasattr(tool, "func") and callable(tool.func):
                            func = tool.func
                        elif callable(tool):
                            func = tool
                        else:
                            raise ValueError(f"Tool is not callable")
                        
                        result = ""
                        try:
                            for chunk in func(tool_input):
                                result += str(chunk)
                        except TypeError:
                            result = str(func(tool_input))
                        
                        update_toolchain_step(request.session_id, execution_id, step_num,
                                            output=result, status="completed")
                        final_result = result
                        
                    except Exception as e:
                        update_toolchain_step(request.session_id, execution_id, step_num,
                                            error=str(e), status="failed")
                
                complete_toolchain_execution(request.session_id, execution_id, 
                                           final_result, "completed")
                
                return final_result
                
            except Exception as e:
                logger.error(f"Toolchain execution error: {str(e)}", exc_info=True)
                complete_toolchain_execution(request.session_id, execution_id, 
                                           str(e), "failed")
                raise
        
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(executor, run_toolchain)
        
        return {
            "execution_id": execution_id,
            "status": "completed",
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Toolchain execution error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@wsrouter.websocket("/{session_id}")
async def websocket_toolchain(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for monitoring toolchain executions."""
    await websocket.accept()
    
    # Capture main loop on first WebSocket connection
    if _main_loop is None:
        set_main_loop()
    
    if session_id not in sessions:
        # Send error message before closing
        try:
            await websocket.send_json({
                "type": "error",
                "error": "Session not found",
                "timestamp": datetime.utcnow().isoformat()
            })
        except Exception:
            pass
        finally:
            try:
                await websocket.close()
            except Exception:
                pass
        return
    
    # Register this websocket for broadcasts
    websocket_connections[session_id].append(websocket)
    logger.info(f"Toolchain WebSocket connected for session: {session_id}")
    
    try:
        # Keep connection alive
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
                message_data = json.loads(data)
                
                # Optional: Allow manual toolchain execution via websocket
                if "query" in message_data:
                    query = message_data["query"]
                    vera = get_or_create_vera(session_id)
                    
                    execution_id = create_toolchain_execution(session_id, query)
                    await websocket.send_json({
                        "type": "execution_started",
                        "execution_id": execution_id,
                        "query": query
                    })
                    
                    def run_toolchain():
                        try:
                            result = ""
                            for chunk in vera.toolchain.execute_tool_chain(query):
                                result += str(chunk)
                            return result
                        except Exception as e:
                            logger.error(f"Toolchain error: {e}")
                            return str(e)
                    
                    loop = asyncio.get_event_loop()
                    with ThreadPoolExecutor() as executor:
                        await loop.run_in_executor(executor, run_toolchain)
                    
            except asyncio.TimeoutError:
                continue
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "error": "Invalid JSON"})
    
    except WebSocketDisconnect:
        logger.info(f"Toolchain WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"Toolchain WebSocket error: {str(e)}", exc_info=True)
    finally:
        # Clean up websocket connection - handle all possible error cases
        try:
            if session_id in websocket_connections and websocket in websocket_connections[session_id]:
                websocket_connections[session_id].remove(websocket)
        except (ValueError, KeyError, AttributeError) as e:
            logger.debug(f"Cleanup warning: {e}")


@router.get("/{session_id}/executions")
async def get_toolchain_executions(session_id: str):
    """Get all toolchain executions for a session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    executions = toolchain_executions.get(session_id, {})
    
    return {
        "session_id": session_id,
        "executions": list(executions.values()),
        "total": len(executions),
        "active_execution": active_toolchains.get(session_id)
    }


@router.get("/{session_id}/execution/{execution_id}")
async def get_toolchain_execution(session_id: str, execution_id: str):
    """Get details of a specific toolchain execution."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session_id not in toolchain_executions or execution_id not in toolchain_executions[session_id]:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    return toolchain_executions[session_id][execution_id]


@router.get("/{session_id}/active")
async def get_active_toolchain(session_id: str):
    """Get the currently active toolchain execution."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session_id not in active_toolchains:
        return {"active": False, "execution_id": None}
    
    execution_id = active_toolchains[session_id]
    execution = toolchain_executions[session_id][execution_id]
    
    return {
        "active": True,
        "execution": execution
    }


@router.get("/{session_id}/tools")
async def list_available_tools(session_id: str):
    """List all available tools for a session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    tools_info = []
    for tool in vera.tools:
        tools_info.append({
            "name": tool.name,
            "description": tool.description if hasattr(tool, "description") else "No description available",
            "type": type(tool).__name__
        })
    
    return {
        "session_id": session_id,
        "tools": tools_info,
        "total": len(tools_info)
    }


@router.delete("/{session_id}/execution/{execution_id}")
async def delete_toolchain_execution(session_id: str, execution_id: str):
    """Delete a toolchain execution record."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session_id not in toolchain_executions or execution_id not in toolchain_executions[session_id]:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    del toolchain_executions[session_id][execution_id]
    
    if active_toolchains.get(session_id) == execution_id:
        del active_toolchains[session_id]
    
    return {"status": "deleted", "execution_id": execution_id}


# ============================================================
# Toolchain Analytics Endpoints
# ============================================================

@router.get("/{session_id}/stats")
async def get_toolchain_stats(session_id: str):
    """Get statistics about toolchain executions for a session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    executions = toolchain_executions.get(session_id, {})
    
    if not executions:
        return {
            "session_id": session_id,
            "total_executions": 0,
            "completed": 0,
            "failed": 0,
            "in_progress": 0,
            "total_steps": 0,
            "avg_steps_per_execution": 0,
            "most_used_tools": []
        }
    
    completed = sum(1 for e in executions.values() if e["status"] == "completed")
    failed = sum(1 for e in executions.values() if e["status"] == "failed")
    in_progress = sum(1 for e in executions.values() if e["status"] in ["planning", "executing"])
    
    total_steps = sum(e["total_steps"] for e in executions.values())
    avg_steps = total_steps / len(executions) if executions else 0
    
    # Count tool usage
    tool_usage = defaultdict(int)
    for execution in executions.values():
        for step in execution["steps"]:
            tool_usage[step["tool_name"]] += 1
    
    most_used_tools = sorted(
        [{"tool": tool, "count": count} for tool, count in tool_usage.items()],
        key=lambda x: x["count"],
        reverse=True
    )[:10]
    
    return {
        "session_id": session_id,
        "total_executions": len(executions),
        "completed": completed,
        "failed": failed,
        "in_progress": in_progress,
        "total_steps": total_steps,
        "avg_steps_per_execution": round(avg_steps, 2),
        "most_used_tools": most_used_tools
    }


@router.get("/execution/{execution_id}/timeline")
async def get_execution_timeline(execution_id: str):
    """Get a timeline view of a toolchain execution."""
    execution_data = None
    session_id = None
    
    for sid, execs in toolchain_executions.items():
        if execution_id in execs:
            execution_data = execs[execution_id]
            session_id = sid
            break
    
    if not execution_data:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    timeline = []
    
    timeline.append({
        "timestamp": execution_data["start_time"],
        "event": "planning_started",
        "description": "Toolchain planning initiated"
    })
    
    for step in execution_data["steps"]:
        timeline.append({
            "timestamp": step["start_time"],
            "event": "step_started",
            "step_number": step["step_number"],
            "tool": step["tool_name"],
            "description": f"Started executing {step['tool_name']}"
        })
        
        if step["end_time"]:
            timeline.append({
                "timestamp": step["end_time"],
                "event": "step_completed" if step["status"] == "completed" else "step_failed",
                "step_number": step["step_number"],
                "tool": step["tool_name"],
                "description": f"{'Completed' if step['status'] == 'completed' else 'Failed'} {step['tool_name']}",
                "error": step.get("error")
            })
    
    if execution_data["end_time"]:
        timeline.append({
            "timestamp": execution_data["end_time"],
            "event": "execution_completed",
            "description": f"Toolchain execution {execution_data['status']}"
        })
    
    return {
        "execution_id": execution_id,
        "session_id": session_id,
        "timeline": timeline,
        "total_events": len(timeline)
    }