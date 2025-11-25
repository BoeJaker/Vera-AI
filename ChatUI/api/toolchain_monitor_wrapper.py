"""
Enhanced MonitoredToolChainPlanner - FIXED FOR ASYNC CONTEXTS
Works correctly when called from FastAPI/async contexts
"""

import asyncio
import json
import uuid
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Import these from your session module
from Vera.ChatUI.api.session import (
    sessions, 
    toolchain_executions, 
    active_toolchains, 
    websocket_connections
)


class EnhancedMonitoredToolChainPlanner:
    """
    Wrapper that adds WebSocket monitoring to any toolchain planner.
    Compatible with both original ToolChainPlanner and HybridToolChainPlanner.
    FIXED: Works correctly in async contexts (FastAPI).
    """
    
    def __init__(self, original_planner, session_id: str):
        self.original_planner = original_planner
        self.session_id = session_id
        self.execution_id = None
    
    def execute_tool_chain(self, query: str, plan=None, strategy: str = "static", 
                          mode: str = "incremental", **kwargs):
        """
        Monitored version of execute_tool_chain.
        
        Args:
            query: User query
            plan: Optional pre-generated plan
            strategy: Planning strategy (static, quick, comprehensive, etc.)
            mode: Execution mode (batch, incremental, speculative, hybrid)
            **kwargs: Additional arguments passed to underlying planner
        """
        # Create execution record
        self.execution_id = self._create_toolchain_execution(query)
        
        try:
            # Broadcast execution started (non-blocking)
            self._broadcast_event_nonblocking(
                "execution_started",
                {"execution_id": self.execution_id, "query": query, "strategy": strategy, "mode": mode}
            )
            
            # Check if planner supports strategy parameter
            planner_method = self.original_planner.execute_tool_chain
            import inspect
            sig = inspect.signature(planner_method)
            supports_strategy = 'strategy' in sig.parameters
            supports_mode = 'mode' in sig.parameters
            
            # Generate plan if not provided
            if plan is None:
                self._broadcast_event_nonblocking("status", {"status": "planning"})
                
                # Try to use plan_tool_chain with strategy if available
                if hasattr(self.original_planner, 'plan_tool_chain'):
                    try:
                        # Check if plan_tool_chain supports strategy
                        plan_sig = inspect.signature(self.original_planner.plan_tool_chain)
                        if 'strategy' in plan_sig.parameters:
                            gen = self.original_planner.plan_tool_chain(query, strategy=strategy)
                        else:
                            gen = self.original_planner.plan_tool_chain(query)
                    except Exception as e:
                        logger.warning(f"Error calling plan_tool_chain with strategy: {e}")
                        gen = self.original_planner.plan_tool_chain(query)
                else:
                    gen = None
                
                if gen:
                    plan_chunks = []
                    for chunk in gen:
                        plan_chunks.append(chunk)
                        if isinstance(chunk, str):
                            self._broadcast_event_nonblocking("plan_chunk", {"chunk": chunk})
                            yield chunk
                        elif isinstance(chunk, list):
                            # Final plan
                            self._update_toolchain_plan(chunk)
                            self._broadcast_event_nonblocking(
                                "plan",
                                {"plan": chunk, "total_steps": len(chunk)}
                            )
                            plan = chunk
                            yield chunk
                        elif isinstance(chunk, dict):
                            # Could be multipath or other structured plan
                            if "primary_path" in chunk:
                                plan = chunk["primary_path"]
                            elif "alternatives" in chunk:
                                plan = chunk["alternatives"][0]
                            else:
                                plan = [chunk]
                            
                            self._update_toolchain_plan(plan)
                            self._broadcast_event_nonblocking(
                                "plan",
                                {"plan": plan, "total_steps": len(plan)}
                            )
                            yield chunk
            else:
                self._update_toolchain_plan(plan)
            
            # Execute plan
            self._broadcast_event_nonblocking("status", {"status": "executing"})
            
            # Prepare execution arguments
            exec_kwargs = {'query': query, **kwargs}
            if plan is not None:
                exec_kwargs['plan'] = plan
            if supports_strategy:
                exec_kwargs['strategy'] = strategy
            if supports_mode:
                exec_kwargs['mode'] = mode
            
            # Execute with monitoring
            step_num = 0
            final_result = ""
            
            # Call the underlying execute_tool_chain
            try:
                result_gen = planner_method(**exec_kwargs)
            except TypeError as e:
                # If it doesn't support some parameters, try with minimal set
                logger.warning(f"Planner doesn't support all parameters: {e}")
                if plan is not None:
                    result_gen = planner_method(query, plan=plan)
                else:
                    result_gen = planner_method(query)
            
            # Monitor execution
            for chunk in result_gen:
                # Detect step transitions
                chunk_str = str(chunk)
                
                # Check for step markers in output
                if "[Step " in chunk_str and "] Executing:" in chunk_str:
                    # New step started
                    try:
                        import re
                        match = re.search(r'\[Step (\d+)\] Executing: (\w+)', chunk_str)
                        if match:
                            step_num = int(match.group(1))
                            tool_name = match.group(2)
                            
                            self._add_toolchain_step(step_num, tool_name, "")
                            self._broadcast_event_nonblocking(
                                "step_started",
                                {
                                    "step_number": step_num,
                                    "tool_name": tool_name,
                                    "execution_id": self.execution_id
                                }
                            )
                    except Exception as e:
                        logger.debug(f"Error parsing step marker: {e}")
                
                # Broadcast output
                if step_num > 0:
                    self._broadcast_event_nonblocking(
                        "step_output",
                        {"step_number": step_num, "chunk": chunk_str}
                    )
                
                yield chunk
                final_result += chunk_str
            
            # Mark as completed
            self._complete_toolchain_execution(final_result, "completed")
            self._broadcast_event_nonblocking(
                "execution_completed",
                {"final_result": final_result[:500]}
            )
            
            return final_result
            
        except Exception as e:
            logger.error(f"Toolchain execution error: {e}", exc_info=True)
            self._complete_toolchain_execution(str(e), "failed")
            self._broadcast_event_nonblocking(
                "execution_failed",
                {"error": str(e)}
            )
            raise
    
    def plan_tool_chain(self, query: str, strategy: str = "static", **kwargs):
        """Generate a plan with optional strategy parameter."""
        if hasattr(self.original_planner, 'plan_tool_chain'):
            import inspect
            sig = inspect.signature(self.original_planner.plan_tool_chain)
            
            if 'strategy' in sig.parameters:
                yield from self.original_planner.plan_tool_chain(query, strategy=strategy, **kwargs)
            else:
                yield from self.original_planner.plan_tool_chain(query, **kwargs)
        else:
            # Fallback: no separate planning method
            yield [{"tool": "fast_llm", "input": query}]
    
    # ============================================================
    # Helper Methods - Non-blocking Event Broadcasting
    # ============================================================
    
    def _broadcast_event_nonblocking(self, event_type: str, data: Dict[str, Any]):
        """
        Broadcast event without blocking.
        Works correctly in both sync and async contexts.
        """
        try:
            # Try to get the running event loop
            loop = asyncio.get_running_loop()
            
            # Schedule the broadcast as a task (fire and forget)
            loop.create_task(self._broadcast_toolchain_event(event_type, data))
            
        except RuntimeError:
            # No event loop running (unlikely in FastAPI, but handle it)
            logger.debug(f"No event loop running, skipping broadcast of {event_type}")
    
    async def _broadcast_toolchain_event(self, event_type: str, data: Dict[str, Any]):
        """Broadcast toolchain events to all connected WebSockets for a session."""
        if self.session_id in websocket_connections:
            disconnected = []
            for websocket in websocket_connections[self.session_id]:
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
                try:
                    websocket_connections[self.session_id].remove(ws)
                except ValueError:
                    pass  # Already removed
    
    # ============================================================
    # Storage Helper Methods
    # ============================================================
    
    def _create_toolchain_execution(self, query: str) -> str:
        """Create a new toolchain execution record."""
        execution_id = str(uuid.uuid4())
        
        if self.session_id not in toolchain_executions:
            toolchain_executions[self.session_id] = {}
        
        toolchain_executions[self.session_id][execution_id] = {
            "execution_id": execution_id,
            "session_id": self.session_id,
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
        
        active_toolchains[self.session_id] = execution_id
        
        return execution_id
    
    def _update_toolchain_plan(self, plan: List[Dict[str, str]]):
        """Update the plan for a toolchain execution."""
        if self.session_id in toolchain_executions and self.execution_id in toolchain_executions[self.session_id]:
            toolchain_executions[self.session_id][self.execution_id]["plan"] = plan
            toolchain_executions[self.session_id][self.execution_id]["total_steps"] = len(plan)
            toolchain_executions[self.session_id][self.execution_id]["status"] = "executing"
    
    def _add_toolchain_step(self, step_number: int, tool_name: str, tool_input: str):
        """Add a new step to toolchain execution."""
        if self.session_id in toolchain_executions and self.execution_id in toolchain_executions[self.session_id]:
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
            toolchain_executions[self.session_id][self.execution_id]["steps"].append(step)
            return step
        return None
    
    def _update_toolchain_step(self, step_number: int, output: Optional[str] = None, 
                               error: Optional[str] = None, status: str = "completed"):
        """Update a toolchain execution step."""
        if self.session_id in toolchain_executions and self.execution_id in toolchain_executions[self.session_id]:
            steps = toolchain_executions[self.session_id][self.execution_id]["steps"]
            for step in steps:
                if step["step_number"] == step_number:
                    step["tool_output"] = output
                    step["error"] = error
                    step["status"] = status
                    step["end_time"] = datetime.utcnow().isoformat()
                    
                    if status == "completed":
                        toolchain_executions[self.session_id][self.execution_id]["completed_steps"] += 1
                    
                    return step
        return None
    
    def _complete_toolchain_execution(self, final_result: str, status: str = "completed"):
        """Mark toolchain execution as complete."""
        if self.session_id in toolchain_executions and self.execution_id in toolchain_executions[self.session_id]:
            toolchain_executions[self.session_id][self.execution_id]["status"] = status
            toolchain_executions[self.session_id][self.execution_id]["end_time"] = datetime.utcnow().isoformat()
            toolchain_executions[self.session_id][self.execution_id]["final_result"] = final_result
            
            if self.session_id in active_toolchains:
                del active_toolchains[self.session_id]
    
    # Delegate other methods to original planner
    def __getattr__(self, name):
        """Delegate unknown attributes to original planner."""
        return getattr(self.original_planner, name)


# ============================================================
# Integration Helper
# ============================================================

def wrap_toolchain_with_monitoring(vera_instance, session_id: str):
    """
    Wrap Vera's toolchain with monitoring capabilities.
    This should be called when creating/retrieving a Vera instance for a session.
    
    Usage in get_or_create_vera():
        vera = VeraAgent(session_id=session_id, ...)
        wrap_toolchain_with_monitoring(vera, session_id)
        return vera
    
    Args:
        vera_instance: Vera agent instance
        session_id: Session ID for WebSocket broadcasting
    """
    # Only wrap if not already wrapped
    if not isinstance(vera_instance.toolchain, EnhancedMonitoredToolChainPlanner):
        vera_instance.toolchain = EnhancedMonitoredToolChainPlanner(
            vera_instance.toolchain,
            session_id
        )
        logger.info(f"[Monitoring] Wrapped toolchain for session {session_id}")
    
    return vera_instance


# ============================================================
# Backward Compatibility
# ============================================================

# Alias for backward compatibility
MonitoredToolChainPlanner = EnhancedMonitoredToolChainPlanner