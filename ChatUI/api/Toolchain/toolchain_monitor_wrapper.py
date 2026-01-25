"""
Enhanced MonitoredToolChainPlanner - FULLY FIXED FOR MULTI-PARAMETER TOOLS
Executes plan step-by-step with reliable WebSocket broadcasting and proper dict input handling
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

# ============================================================
# CRITICAL: Reference to main event loop
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
                try:
                    websocket_connections[session_id].remove(ws)
                except ValueError:
                    pass
    
    # Use the captured main loop - this works from ANY thread
    if _main_loop and not _main_loop.is_closed():
        try:
            asyncio.run_coroutine_threadsafe(_broadcast(), _main_loop)
        except Exception as e:
            logger.error(f"Failed to schedule broadcast: {e}")
    else:
        logger.warning(f"Main loop not available for broadcast: {event_type}")


# ============================================================
# HELPER FUNCTIONS (FIXED FOR MULTI-PARAM TOOLS)
# ============================================================

def parse_tool_input(raw_input: Any) -> Any:
    """
    Parse tool input - handles both string and dict inputs.
    Converts JSON strings to dicts where appropriate.
    
    Args:
        raw_input: Raw input from plan (string or dict)
    
    Returns:
        Parsed input (string or dict)
    """
    # If already a dict, return as-is
    if isinstance(raw_input, dict):
        return raw_input
    
    # If not a string, convert to string
    if not isinstance(raw_input, str):
        return str(raw_input)
    
    # Try to parse as JSON if it looks like JSON
    stripped = raw_input.strip()
    if (stripped.startswith('{') and stripped.endswith('}')) or \
       (stripped.startswith('[') and stripped.endswith(']')):
        try:
            parsed = json.loads(stripped)
            # Only use parsed version if it's a dict (not a list or other JSON)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            # Try Python literal eval as fallback (handles single quotes)
            try:
                import ast
                parsed = ast.literal_eval(stripped)
                if isinstance(parsed, dict):
                    return parsed
            except (ValueError, SyntaxError):
                pass
    
    # Return as string if not parseable
    return raw_input


def resolve_placeholders(value: Any, step_num: int, executed: Dict[str, str]) -> Any:
    """
    Resolve {prev} and {step_N} placeholders in any value.
    Works recursively on dicts and strings.
    
    Args:
        value: Value to resolve (string, dict, or other)
        step_num: Current step number
        executed: Dict of previous step outputs
    
    Returns:
        Value with placeholders resolved
    """
    # Handle dict recursively
    if isinstance(value, dict):
        return {k: resolve_placeholders(v, step_num, executed) for k, v in value.items()}
    
    # Handle list recursively
    if isinstance(value, list):
        return [resolve_placeholders(item, step_num, executed) for item in value]
    
    # Handle strings with placeholders
    if isinstance(value, str):
        # Replace {prev} with previous step output
        if "{prev}" in value:
            prev_output = str(executed.get(f"step_{step_num-1}", ""))
            value = value.replace("{prev}", prev_output)
        
        # Replace {step_N} with that step's output
        for i in range(1, step_num):
            placeholder = f"{{step_{i}}}"
            if placeholder in value:
                step_output = str(executed.get(f"step_{i}", ""))
                value = value.replace(placeholder, step_output)
        
        return value
    
    # Return other types as-is
    return value


def execute_tool_with_input(tool, tool_name: str, tool_input: Any):
    """
    Execute a tool with proper argument handling.
    Matches original ToolChainPlanner pattern but with dict input support.
    
    Args:
        tool: Tool instance
        tool_name: Tool name (for logging)
        tool_input: Parsed and resolved input (dict or string)
    
    Yields/Returns:
        Tool execution result (may be generator or direct value)
    """
    logger.debug(f"[execute_tool_with_input] Tool: {tool_name}")
    logger.debug(f"[execute_tool_with_input] Input type: {type(tool_input)}")
    logger.debug(f"[execute_tool_with_input] Input value: {tool_input}")
    
    # Get the callable - matching original pattern from Document 3
    if hasattr(tool, 'run') and callable(tool.run):
        func = tool.run
    elif hasattr(tool, 'invoke') and callable(tool.invoke):
        func = tool.invoke
    elif hasattr(tool, 'func') and callable(tool.func):
        func = tool.func
    elif callable(tool):
        func = tool
    else:
        raise ValueError(f"Tool '{tool_name}' is not callable")
    
    # Execute - BaseTool.run() and similar methods accept tool_input as single arg (can be dict)
    # Only unpack dicts for raw functions (.func or callable tools)
    if hasattr(tool, 'run') or hasattr(tool, 'invoke'):
        # LangChain tool methods - pass tool_input as-is (they handle dicts internally)
        logger.debug(f"[execute_tool_with_input] Calling LangChain method with tool_input")
        return func(tool_input)
    else:
        # Raw functions - unpack dicts as kwargs
        if isinstance(tool_input, dict):
            logger.debug(f"[execute_tool_with_input] Calling raw function with **kwargs")
            return func(**tool_input)
        else:
            logger.debug(f"[execute_tool_with_input] Calling raw function with single arg")
            return func(tool_input)


class EnhancedMonitoredToolChainPlanner:
    """
    Wrapper that adds WebSocket monitoring to any toolchain planner.
    FIXED: Executes plan directly step-by-step with proper multi-parameter tool support.
    """
    
    def __init__(self, original_planner, session_id: str):
        self.original_planner = original_planner
        self.session_id = session_id
        self.execution_id = None
        self.agent = original_planner.agent
        self.tools = original_planner.tools
    
    def execute_tool_chain(self, query: str, plan=None, strategy: str = "static", 
                          mode: str = "incremental", **kwargs):
        """
        Monitored version of execute_tool_chain.
        FIXED: Executes plan directly with reliable step tracking and multi-param support.
        """
        # Create execution record
        self.execution_id = self._create_toolchain_execution(query)
        
        try:
            # Broadcast execution started
            schedule_broadcast(
                self.session_id,
                "execution_started",
                {"execution_id": self.execution_id, "query": query, "strategy": strategy, "mode": mode}
            )
            
            # Generate plan if not provided
            if plan is None:
                schedule_broadcast(self.session_id, "status", {"status": "planning"})
                
                # Use planner to generate plan
                if hasattr(self.original_planner, 'plan_tool_chain'):
                    try:
                        import inspect
                        plan_sig = inspect.signature(self.original_planner.plan_tool_chain)
                        if 'strategy' in plan_sig.parameters:
                            gen = self.original_planner.plan_tool_chain(query, strategy=strategy)
                        else:
                            gen = self.original_planner.plan_tool_chain(query)
                    except Exception as e:
                        logger.warning(f"Error calling plan_tool_chain with strategy: {e}")
                        gen = self.original_planner.plan_tool_chain(query)
                    
                    # Process planning chunks
                    for chunk in gen:
                        if isinstance(chunk, str):
                            # Broadcast planning chunks
                            schedule_broadcast(self.session_id, "plan_chunk", {"chunk": chunk})
                            yield chunk
                        elif isinstance(chunk, list):
                            # Final plan
                            plan = chunk
                            self._update_toolchain_plan(plan)
                            schedule_broadcast(
                                self.session_id,
                                "plan",
                                {"plan": plan, "total_steps": len(plan)}
                            )
                            yield chunk
                        elif isinstance(chunk, dict):
                            # Handle structured plans
                            if "primary_path" in chunk:
                                plan = chunk["primary_path"]
                            elif "alternatives" in chunk:
                                plan = chunk["alternatives"][0]
                            else:
                                plan = [chunk]
                            
                            self._update_toolchain_plan(plan)
                            schedule_broadcast(
                                self.session_id,
                                "plan",
                                {"plan": plan, "total_steps": len(plan)}
                            )
                            yield chunk
                else:
                    # No plan_tool_chain method, use simple plan
                    plan = [{"tool": "fast_llm", "input": query}]
                    self._update_toolchain_plan(plan)
            else:
                self._update_toolchain_plan(plan)
            
            if not plan or not isinstance(plan, list):
                raise ValueError(f"Invalid plan: {plan}")
            
            # Execute plan step by step (FIXED: Direct execution with multi-param support)
            schedule_broadcast(self.session_id, "status", {"status": "executing"})
            
            yield from self._execute_plan_directly(plan, query)
            
        except Exception as e:
            logger.error(f"Toolchain execution error: {e}", exc_info=True)
            self._complete_toolchain_execution(str(e), "failed")
            schedule_broadcast(
                self.session_id,
                "execution_failed",
                {"error": str(e)}
            )
            raise
    
    def _execute_plan_directly(self, plan: List[Dict], query: str):
        """
        Execute plan directly, step by step, with reliable broadcasting.
        FIXED: Properly handles multi-parameter tools with dict inputs.
        """
        executed = {}
        step_num = 0
        final_result = ""
        
        for step in plan:
            step_num += 1
            tool_name = step.get("tool")
            raw_input = step.get("input", "")
            
            logger.info(f"\n{'='*60}")
            logger.info(f"[Step {step_num}] Tool: {tool_name}")
            logger.info(f"[Step {step_num}] Raw input type: {type(raw_input)}")
            logger.info(f"[Step {step_num}] Raw input value: {raw_input}")
            
            # FIXED: Parse input (handles JSON strings -> dicts)
            parsed_input = parse_tool_input(raw_input)
            logger.info(f"[Step {step_num}] Parsed input type: {type(parsed_input)}")
            logger.info(f"[Step {step_num}] Parsed input value: {parsed_input}")
            
            # FIXED: Resolve placeholders (works on both strings and dicts)
            tool_input = resolve_placeholders(parsed_input, step_num, executed)
            logger.info(f"[Step {step_num}] Resolved input type: {type(tool_input)}")
            logger.info(f"[Step {step_num}] Resolved input value: {tool_input}")
            
            # Display input for monitoring (convert dict to JSON string)
            input_display = json.dumps(tool_input) if isinstance(tool_input, dict) else str(tool_input)
            
            # Add step to monitoring
            self._add_toolchain_step(step_num, tool_name, input_display)
            
            # Broadcast step started
            schedule_broadcast(
                self.session_id,
                "step_started",
                {
                    "step_number": step_num,
                    "tool_name": tool_name,
                    "tool_input": input_display,
                    "execution_id": self.execution_id
                }
            )
            
            # Show step info
            yield f"\n[Step {step_num}] Executing: {tool_name}\n"
            yield f"[Input] {input_display[:200]}{'...' if len(input_display) > 200 else ''}\n"
            
            # Find and execute tool
            tool = next((t for t in self.tools if getattr(t, "name", "") == tool_name), None)
            
            if not tool:
                error_msg = f"ERROR: Tool not found: {tool_name}"
                yield error_msg
                
                self._update_toolchain_step(step_num, error=error_msg, status="failed")
                schedule_broadcast(
                    self.session_id,
                    "step_failed",
                    {"step_number": step_num, "error": error_msg}
                )
                
                executed[f"step_{step_num}"] = error_msg
                continue
            
            # Execute tool
            try:
                logger.info(f"[Step {step_num}] Executing tool: {tool_name}")
                
                # FIXED: Execute with proper argument handling
                result = execute_tool_with_input(tool, tool_name, tool_input)
                
                # Collect output (handle both streaming and non-streaming)
                collected = []
                result_str = ""
                
                try:
                    # Try to iterate (streaming)
                    for chunk in result:
                        chunk_str = str(chunk)
                        yield chunk_str
                        collected.append(chunk_str)
                        
                        # FIXED: Broadcast EVERY chunk with correct step number
                        schedule_broadcast(
                            self.session_id,
                            "step_output",
                            {"step_number": step_num, "chunk": chunk_str}
                        )
                        
                except TypeError:
                    # Not iterable - single result
                    result_str = str(result)
                    yield result_str
                    
                    # Broadcast single result
                    schedule_broadcast(
                        self.session_id,
                        "step_output",
                        {"step_number": step_num, "chunk": result_str}
                    )
                else:
                    # Combine collected chunks
                    result_str = "".join(collected)
                
                # Store result
                executed[f"step_{step_num}"] = result_str
                executed[tool_name] = result_str
                final_result = result_str
                
                logger.info(f"[Step {step_num}] Result length: {len(result_str)} chars")
                logger.info(f"[Step {step_num}] Result preview: {result_str[:100]}...")
                
                # Update step as completed
                self._update_toolchain_step(step_num, output=result_str, status="completed")
                
                # Broadcast step completed
                schedule_broadcast(
                    self.session_id,
                    "step_completed",
                    {"step_number": step_num, "output": result_str[:500]}
                )
                
                # Save to memory if available
                try:
                    if hasattr(self.agent, 'save_to_memory'):
                        self.agent.save_to_memory(f"Step {step_num} - {tool_name}", result_str)
                except Exception as e:
                    logger.debug(f"Could not save to memory: {e}")
                
                yield f"\n[Step {step_num}] ✓ Complete\n"
                
            except Exception as e:
                error_msg = f"ERROR: {str(e)}"
                logger.error(f"[Step {step_num}] Execution failed: {error_msg}", exc_info=True)
                yield f"\n[Step {step_num}] ✗ Failed: {error_msg}\n"
                
                self._update_toolchain_step(step_num, error=error_msg, status="failed")
                schedule_broadcast(
                    self.session_id,
                    "step_failed",
                    {"step_number": step_num, "error": error_msg}
                )
                
                executed[f"step_{step_num}"] = error_msg
        
        # Mark execution as completed
        self._complete_toolchain_execution(final_result, "completed")
        schedule_broadcast(
            self.session_id,
            "execution_completed",
            {"final_result": final_result[:500]}
        )
        
        # Show final result
        yield f"\n{'='*60}\n"
        yield f"[Final Result]\n{final_result}\n"
        yield f"{'='*60}\n"
        
        return executed
    
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
                    if output is not None:
                        step["tool_output"] = output
                    if error is not None:
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