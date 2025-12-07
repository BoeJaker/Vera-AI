"""
Task Orchestrator Management Tools for Vera
============================================
Tools for managing, monitoring, and controlling the distributed task execution system.

Features:
- Start/stop orchestrator and worker pools
- Submit and monitor tasks (with streaming support)
- Scale worker pools dynamically
- View real-time statistics and metrics
- Manage task priorities and queues
- Event subscription and monitoring
- Proactive focus integration
- Task registry inspection
"""

import json
import time
from typing import List, Dict, Any, Optional, Iterator
from pathlib import Path
from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool

# Import orchestrator components
try:
    from Vera.Orchestration.orchestration import (
        Orchestrator, TaskType, Priority, TaskStatus,
        registry, task, proactive_task
    )
    ORCHESTRATOR_AVAILABLE = True
except ImportError:
    ORCHESTRATOR_AVAILABLE = False
    print("[Warning] Orchestrator module not available")


# ============================================================================
# INPUT SCHEMAS
# ============================================================================

class OrchestratorStartInput(BaseModel):
    """Input schema for starting orchestrator."""
    llm_workers: int = Field(default=2, description="Number of LLM workers")
    whisper_workers: int = Field(default=1, description="Number of Whisper workers")
    tool_workers: int = Field(default=4, description="Number of tool workers")
    ml_workers: int = Field(default=1, description="Number of ML model workers")
    background_workers: int = Field(default=2, description="Number of background workers")
    general_workers: int = Field(default=2, description="Number of general workers")
    redis_url: Optional[str] = Field(
        default=None,
        description="Redis URL for pub/sub (optional)"
    )
    cpu_threshold: float = Field(
        default=85.0,
        description="CPU usage threshold for throttling (0-100)"
    )


class TaskSubmitInput(BaseModel):
    """Input schema for submitting tasks."""
    task_name: str = Field(..., description="Registered task name")
    args: Optional[List[Any]] = Field(
        default=None,
        description="Positional arguments as JSON array"
    )
    kwargs: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Keyword arguments as JSON object"
    )
    focus_context: Optional[str] = Field(
        default=None,
        description="Proactive focus context (optional)"
    )


class TaskWaitInput(BaseModel):
    """Input schema for waiting on tasks."""
    task_id: str = Field(..., description="Task ID to wait for")
    timeout: Optional[float] = Field(
        default=None,
        description="Timeout in seconds (None = no timeout)"
    )
    stream: bool = Field(
        default=False,
        description="Stream results as they arrive (for generator tasks)"
    )


class TaskQueryInput(BaseModel):
    """Input schema for querying tasks."""
    task_id: Optional[str] = Field(
        default=None,
        description="Specific task ID (or None for all recent)"
    )
    limit: int = Field(
        default=20,
        description="Number of recent tasks to show"
    )


class WorkerScaleInput(BaseModel):
    """Input schema for scaling workers."""
    task_type: str = Field(
        ...,
        description="Task type: llm, whisper, tool, ml_model, background, general"
    )
    num_workers: int = Field(
        ...,
        description="New number of workers (0 to disable)"
    )


class TaskRegistryQueryInput(BaseModel):
    """Input schema for querying task registry."""
    task_type: Optional[str] = Field(
        default=None,
        description="Filter by task type"
    )
    proactive_focus: Optional[bool] = Field(
        default=None,
        description="Filter by proactive focus flag"
    )


class EventSubscribeInput(BaseModel):
    """Input schema for event subscriptions."""
    channel: str = Field(
        ...,
        description="Event channel: task.started, task.completed, task.failed, focus.changed"
    )
    duration: float = Field(
        default=10.0,
        description="How long to monitor (seconds)"
    )


class TaskCancelInput(BaseModel):
    """Input schema for canceling tasks."""
    task_id: str = Field(..., description="Task ID to cancel")
    force: bool = Field(
        default=False,
        description="Force cancel even if running"
    )


# ============================================================================
# ORCHESTRATOR TOOLS CLASS
# ============================================================================

class OrchestratorTools:
    """Tools for managing the task orchestrator."""
    
    def __init__(self, agent):
        self.agent = agent
        self.orchestrator: Optional[Orchestrator] = None
        self.task_history: List[Dict[str, Any]] = []
        
        # Check if orchestrator already exists on agent
        if hasattr(agent, 'orchestrator') and agent.orchestrator:
            self.orchestrator = agent.orchestrator
    
    def _ensure_orchestrator(self) -> bool:
        """Ensure orchestrator is running."""
        if self.orchestrator is None:
            return False
        if not self.orchestrator.running:
            return False
        return True
    
    def _task_type_from_string(self, task_type_str: str) -> TaskType:
        """Convert string to TaskType enum."""
        mapping = {
            "llm": TaskType.LLM,
            "whisper": TaskType.WHISPER,
            "tool": TaskType.TOOL,
            "ml_model": TaskType.ML_MODEL,
            "background": TaskType.BACKGROUND,
            "general": TaskType.GENERAL
        }
        
        task_type_str = task_type_str.lower()
        if task_type_str not in mapping:
            raise ValueError(f"Unknown task type: {task_type_str}")
        
        return mapping[task_type_str]
    
    def start_orchestrator(
        self,
        llm_workers: int = 2,
        whisper_workers: int = 1,
        tool_workers: int = 4,
        ml_workers: int = 1,
        background_workers: int = 2,
        general_workers: int = 2,
        redis_url: Optional[str] = None,
        cpu_threshold: float = 85.0
    ) -> str:
        """
        Start the task orchestrator with worker pools.
        
        Initializes the distributed task execution system with configurable
        worker pools for different task types. Each worker pool can process
        tasks concurrently.
        
        Worker Types:
        - LLM: Language model inference tasks
        - Whisper: Audio transcription tasks
        - Tool: Tool execution tasks
        - ML Model: Machine learning model tasks
        - Background: Background cognitive tasks
        - General: General computation tasks
        
        Args:
            llm_workers: Number of LLM workers (default: 2)
            whisper_workers: Number of Whisper workers (default: 1)
            tool_workers: Number of tool workers (default: 4)
            ml_workers: Number of ML workers (default: 1)
            background_workers: Number of background workers (default: 2)
            general_workers: Number of general workers (default: 2)
            redis_url: Optional Redis URL for pub/sub coordination
            cpu_threshold: CPU usage threshold for throttling (0-100)
        
        The orchestrator provides:
        - Priority-based task queuing
        - CPU-aware throttling
        - Streaming task support
        - Event-driven coordination
        - Worker pool scaling
        
        Example:
            start_orchestrator(
                llm_workers=4,
                tool_workers=8,
                redis_url="redis://localhost:6379"
            )
        """
        if not ORCHESTRATOR_AVAILABLE:
            return "[Error] Orchestrator module not available"
        
        if self.orchestrator and self.orchestrator.running:
            return "[Error] Orchestrator already running. Stop it first."
        
        try:
            # Build worker config
            config = {
                TaskType.LLM: llm_workers,
                TaskType.WHISPER: whisper_workers,
                TaskType.TOOL: tool_workers,
                TaskType.ML_MODEL: ml_workers,
                TaskType.BACKGROUND: background_workers,
                TaskType.GENERAL: general_workers
            }
            
            # Create orchestrator
            self.orchestrator = Orchestrator(
                config=config,
                redis_url=redis_url,
                cpu_threshold=cpu_threshold
            )
            
            # Start it
            self.orchestrator.start()
            
            # Store on agent for other components
            self.agent.orchestrator = self.orchestrator
            
            output = [
                "✓ Orchestrator started successfully",
                "",
                "Worker Pools:",
                f"  LLM workers: {llm_workers}",
                f"  Whisper workers: {whisper_workers}",
                f"  Tool workers: {tool_workers}",
                f"  ML workers: {ml_workers}",
                f"  Background workers: {background_workers}",
                f"  General workers: {general_workers}",
                "",
                f"CPU Threshold: {cpu_threshold}%",
            ]
            
            if redis_url:
                output.append(f"Redis: {redis_url}")
            else:
                output.append("Redis: Not configured (using local pub/sub)")
            
            # Store in agent memory
            self.agent.mem.add_session_memory(
                self.agent.sess.id,
                "orchestrator_started",
                "system_event",
                metadata={
                    "config": {k.value: v for k, v in config.items()},
                    "cpu_threshold": cpu_threshold
                }
            )
            
            return "\n".join(output)
            
        except Exception as e:
            return f"[Error] Failed to start orchestrator: {str(e)}"
    
    def stop_orchestrator(self) -> str:
        """
        Stop the task orchestrator.
        
        Gracefully shuts down all worker pools and completes pending tasks.
        Running tasks are allowed to finish, but no new tasks are accepted.
        
        Returns status of shutdown process.
        
        Example:
            stop_orchestrator()
        """
        if not self.orchestrator:
            return "[Info] No orchestrator running"
        
        if not self.orchestrator.running:
            return "[Info] Orchestrator already stopped"
        
        try:
            self.orchestrator.stop()
            
            # Store in agent memory
            self.agent.mem.add_session_memory(
                self.agent.sess.id,
                "orchestrator_stopped",
                "system_event",
                metadata={"timestamp": time.time()}
            )
            
            return "✓ Orchestrator stopped successfully"
            
        except Exception as e:
            return f"[Error] Failed to stop orchestrator: {str(e)}"
    
    def submit_task(
        self,
        task_name: str,
        args: Optional[List[Any]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
        focus_context: Optional[str] = None
    ) -> str:
        """
        Submit a task for execution.
        
        Tasks are queued based on priority and executed by appropriate workers.
        Returns a task ID for tracking and retrieving results.
        
        Args:
            task_name: Name of registered task (e.g., "llm.generate", "tool.execute")
            args: Positional arguments as JSON array
            kwargs: Keyword arguments as JSON object
            focus_context: Optional proactive focus context
        
        The task is automatically routed to the appropriate worker pool based
        on its registered type (LLM, Tool, etc.).
        
        Task can be either:
        - Regular: Returns a single result when complete
        - Streaming: Yields results as a generator (for LLM streaming, etc.)
        
        Example:
            # Submit LLM generation task
            submit_task(
                task_name="llm.generate",
                kwargs={"prompt": "Hello world", "max_tokens": 100}
            )
            
            # Submit tool execution
            submit_task(
                task_name="tool.web_search",
                kwargs={"query": "Python asyncio"}
            )
        """
        if not self._ensure_orchestrator():
            return "[Error] Orchestrator not running. Start it first."
        
        try:
            # Parse arguments
            args = args or []
            kwargs = kwargs or {}
            
            # Add focus context if provided
            if focus_context:
                kwargs['focus_context'] = focus_context
            
            # Submit task
            task_id = self.orchestrator.submit_task(task_name, *args, **kwargs)
            
            # Track in history
            self.task_history.append({
                "task_id": task_id,
                "task_name": task_name,
                "submitted_at": time.time(),
                "args": args,
                "kwargs": {k: str(v)[:100] for k, v in kwargs.items()}  # Truncate for display
            })
            
            # Store in agent memory
            self.agent.mem.add_session_memory(
                self.agent.sess.id,
                task_name,
                "task_submission",
                metadata={
                    "task_id": task_id,
                    "focus_context": focus_context
                }
            )
            
            output = [
                f"✓ Task submitted successfully",
                f"Task ID: {task_id}",
                f"Task Name: {task_name}",
                "",
                "Use wait_for_task() to get results or stream_task() for streaming results."
            ]
            
            return "\n".join(output)
            
        except Exception as e:
            return f"[Error] Failed to submit task: {str(e)}"
    
    def wait_for_task(
        self,
        task_id: str,
        timeout: Optional[float] = None,
        stream: bool = False
    ) -> str:
        """
        Wait for a task to complete and retrieve results.
        
        Blocks until task completes or timeout is reached.
        
        Args:
            task_id: Task ID from submit_task()
            timeout: Timeout in seconds (None = wait forever)
            stream: If True, stream results for generator tasks
        
        For streaming tasks, set stream=True to get incremental results
        as they're produced. Otherwise, waits for complete result.
        
        Returns:
            Task result or error message
        
        Examples:
            # Wait for completion
            wait_for_task(task_id="abc123", timeout=30.0)
            
            # Stream results (for LLM generation, etc.)
            wait_for_task(task_id="abc123", stream=True)
        """
        if not self._ensure_orchestrator():
            return "[Error] Orchestrator not running"
        
        try:
            if stream:
                # Stream results
                output = [f"Streaming results for task {task_id}:", ""]
                
                try:
                    for chunk in self.orchestrator.stream_result(task_id, timeout=timeout):
                        output.append(str(chunk))
                    
                    output.append("")
                    output.append("✓ Stream complete")
                    
                except Exception as e:
                    output.append(f"\n[Stream Error] {str(e)}")
                
                return "\n".join(output)
            
            else:
                # Wait for complete result
                result = self.orchestrator.wait_for_result(task_id, timeout=timeout)
                
                if not result:
                    return f"[Timeout] Task {task_id} did not complete within {timeout}s"
                
                output = [
                    f"Task Result: {task_id}",
                    f"{'='*60}",
                    f"Status: {result.status.name}",
                ]
                
                if result.started_at:
                    output.append(f"Started: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(result.started_at))}")
                
                if result.completed_at:
                    output.append(f"Completed: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(result.completed_at))}")
                
                if result.duration:
                    output.append(f"Duration: {result.duration:.2f}s")
                
                if result.worker_id:
                    output.append(f"Worker: {result.worker_id}")
                
                output.append("")
                
                if result.status == TaskStatus.COMPLETED:
                    output.append("Result:")
                    output.append(str(result.result))
                elif result.status == TaskStatus.FAILED:
                    output.append(f"Error: {result.error}")
                else:
                    output.append(f"Status: {result.status.name}")
                
                return "\n".join(output)
            
        except Exception as e:
            return f"[Error] Failed to wait for task: {str(e)}"
    
    def stream_task(self, task_id: str, timeout: Optional[float] = None) -> str:
        """
        Stream results from a task as they arrive.
        
        Convenience wrapper for wait_for_task(stream=True).
        Works for both streaming (generator) and non-streaming tasks.
        
        Args:
            task_id: Task ID from submit_task()
            timeout: Timeout in seconds
        
        Example:
            stream_task(task_id="abc123")
        """
        return self.wait_for_task(task_id=task_id, timeout=timeout, stream=True)
    
    def get_orchestrator_stats(self) -> str:
        """
        Get comprehensive orchestrator statistics.
        
        Shows:
        - Running status
        - Queue sizes for each task type
        - Worker pool information
        - Per-worker statistics (tasks completed, failed, CPU usage)
        - Recent task history
        
        Useful for monitoring system health and performance.
        
        Example:
            get_orchestrator_stats()
        """
        if not self._ensure_orchestrator():
            return "[Error] Orchestrator not running"
        
        try:
            stats = self.orchestrator.get_stats()
            
            output = [
                "Orchestrator Statistics",
                "="*60,
                f"Status: {'Running' if stats['running'] else 'Stopped'}",
                "",
                "Queue Sizes:",
            ]
            
            for task_type, size in stats['queue_sizes'].items():
                output.append(f"  {task_type}: {size} tasks")
            
            output.append("")
            output.append("Worker Pools:")
            
            for task_type, pool_info in stats['worker_pools'].items():
                output.append(f"\n  {task_type.upper()}:")
                output.append(f"    Workers: {pool_info['num_workers']}")
                
                for worker in pool_info['workers']:
                    output.append(f"    - {worker['worker_id']}:")
                    output.append(f"        Completed: {worker['tasks_completed']}")
                    output.append(f"        Failed: {worker['tasks_failed']}")
                    
                    if worker['tasks_completed'] > 0:
                        avg_duration = worker['total_duration'] / worker['tasks_completed']
                        output.append(f"        Avg Duration: {avg_duration:.2f}s")
                    
                    if worker['current_task']:
                        output.append(f"        Current: {worker['current_task']}")
            
            # Add recent task history
            if self.task_history:
                output.append("")
                output.append("Recent Tasks (last 10):")
                
                for task in self.task_history[-10:]:
                    submitted_time = time.strftime(
                        '%H:%M:%S',
                        time.localtime(task['submitted_at'])
                    )
                    output.append(f"  [{submitted_time}] {task['task_name']} ({task['task_id'][:8]}...)")
            
            return "\n".join(output)
            
        except Exception as e:
            return f"[Error] Failed to get stats: {str(e)}"
    
    def scale_workers(self, task_type: str, num_workers: int) -> str:
        """
        Scale a worker pool dynamically.
        
        Adjust the number of workers for a specific task type while
        the orchestrator is running. Workers are added or removed gracefully.
        
        Args:
            task_type: Task type (llm, whisper, tool, ml_model, background, general)
            num_workers: New number of workers (0 to disable pool)
        
        Scaling up adds new workers immediately.
        Scaling down waits for current tasks to complete before removing workers.
        
        Example:
            # Scale up LLM workers for heavy load
            scale_workers(task_type="llm", num_workers=8)
            
            # Scale down to save resources
            scale_workers(task_type="background", num_workers=1)
        """
        if not self._ensure_orchestrator():
            return "[Error] Orchestrator not running"
        
        try:
            task_type_enum = self._task_type_from_string(task_type)
            
            # Get current size
            current_size = self.orchestrator.config.get(task_type_enum, 0)
            
            # Scale pool
            self.orchestrator.scale_pool(task_type_enum, num_workers)
            
            # Store in agent memory
            self.agent.mem.add_session_memory(
                self.agent.sess.id,
                f"scale_{task_type}",
                "worker_scaling",
                metadata={
                    "task_type": task_type,
                    "old_size": current_size,
                    "new_size": num_workers
                }
            )
            
            output = [
                f"✓ Worker pool scaled successfully",
                f"Task Type: {task_type}",
                f"Old Size: {current_size} workers",
                f"New Size: {num_workers} workers",
            ]
            
            if num_workers > current_size:
                output.append(f"Added: {num_workers - current_size} workers")
            elif num_workers < current_size:
                output.append(f"Removed: {current_size - num_workers} workers")
            
            return "\n".join(output)
            
        except Exception as e:
            return f"[Error] Failed to scale workers: {str(e)}"
    
    def list_registered_tasks(
        self,
        task_type: Optional[str] = None,
        proactive_focus: Optional[bool] = None
    ) -> str:
        """
        List all registered tasks in the task registry.
        
        Shows tasks that can be submitted to the orchestrator,
        with optional filtering by type or proactive focus flag.
        
        Args:
            task_type: Filter by task type (llm, tool, etc.)
            proactive_focus: Filter by proactive focus flag
        
        Registered tasks are defined using @task or @proactive_task decorators.
        Each task has metadata like type, priority, estimated duration, etc.
        
        Example:
            # List all tasks
            list_registered_tasks()
            
            # List only LLM tasks
            list_registered_tasks(task_type="llm")
            
            # List proactive focus tasks
            list_registered_tasks(proactive_focus=True)
        """
        if not ORCHESTRATOR_AVAILABLE:
            return "[Error] Orchestrator module not available"
        
        try:
            # Parse filters
            task_type_enum = None
            if task_type:
                task_type_enum = self._task_type_from_string(task_type)
            
            # Get tasks
            tasks = registry.list_tasks(
                task_type=task_type_enum,
                proactive_focus=proactive_focus
            )
            
            if not tasks:
                return "No registered tasks found matching criteria"
            
            output = [
                "Registered Tasks",
                "="*60,
                ""
            ]
            
            for task_name in sorted(tasks):
                metadata = registry.get_metadata(task_name)
                
                output.append(f"Task: {task_name}")
                output.append(f"  Type: {metadata.task_type.value}")
                output.append(f"  Priority: {metadata.priority.name}")
                output.append(f"  Est. Duration: {metadata.estimated_duration}s")
                
                if metadata.requires_gpu:
                    output.append(f"  GPU: Required")
                
                if metadata.requires_cpu_cores > 1:
                    output.append(f"  CPU Cores: {metadata.requires_cpu_cores}")
                
                if metadata.metadata.get('proactive_focus'):
                    output.append(f"  Proactive Focus: Yes")
                
                if metadata.labels:
                    output.append(f"  Labels: {', '.join(metadata.labels)}")
                
                output.append("")
            
            output.append(f"Total: {len(tasks)} tasks")
            
            return "\n".join(output)
            
        except Exception as e:
            return f"[Error] Failed to list tasks: {str(e)}"
    
    def monitor_events(self, channel: str, duration: float = 10.0) -> str:
        """
        Monitor orchestrator events for a duration.
        
        Subscribe to an event channel and collect events for analysis.
        Useful for debugging and monitoring task execution.
        
        Args:
            channel: Event channel to monitor
                - task.started: When tasks begin execution
                - task.completed: When tasks finish successfully
                - task.failed: When tasks fail
                - focus.changed: When proactive focus changes
            duration: How long to monitor (seconds)
        
        Events are collected and displayed with timestamps.
        
        Example:
            # Monitor task completions
            monitor_events(channel="task.completed", duration=30.0)
            
            # Monitor failures
            monitor_events(channel="task.failed", duration=60.0)
        """
        if not self._ensure_orchestrator():
            return "[Error] Orchestrator not running"
        
        try:
            events = []
            
            def event_callback(message: Dict[str, Any]):
                events.append({
                    "timestamp": time.time(),
                    "message": message
                })
            
            # Subscribe
            self.orchestrator.event_bus.subscribe(channel, event_callback)
            
            # Monitor
            start_time = time.time()
            
            while time.time() - start_time < duration:
                time.sleep(0.1)
            
            # Unsubscribe
            self.orchestrator.event_bus.unsubscribe(channel, event_callback)
            
            # Format output
            output = [
                f"Event Monitor: {channel}",
                f"Duration: {duration}s",
                f"Events Collected: {len(events)}",
                "="*60,
                ""
            ]
            
            for event in events:
                timestamp = time.strftime(
                    '%H:%M:%S',
                    time.localtime(event['timestamp'])
                )
                output.append(f"[{timestamp}] {json.dumps(event['message'], indent=2)}")
                output.append("")
            
            if not events:
                output.append("No events captured during monitoring period")
            
            return "\n".join(output)
            
        except Exception as e:
            return f"[Error] Failed to monitor events: {str(e)}"
    
    def get_task_info(self, task_id: str) -> str:
        """
        Get detailed information about a specific task.
        
        Shows current status, execution details, and metadata.
        
        Args:
            task_id: Task ID to query
        
        Example:
            get_task_info(task_id="abc123")
        """
        if not self._ensure_orchestrator():
            return "[Error] Orchestrator not running"
        
        try:
            # Try to get result (non-blocking)
            result = self.orchestrator.wait_for_result(task_id, timeout=0.1)
            
            if not result:
                # Check if in history
                task_info = None
                for task in self.task_history:
                    if task['task_id'] == task_id:
                        task_info = task
                        break
                
                if task_info:
                    return f"Task {task_id} is queued/running. Use wait_for_task() to get results."
                else:
                    return f"Task {task_id} not found"
            
            # Format result
            output = [
                f"Task Information: {task_id}",
                "="*60,
                f"Status: {result.status.name}",
            ]
            
            if result.started_at:
                output.append(f"Started: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(result.started_at))}")
            
            if result.completed_at:
                output.append(f"Completed: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(result.completed_at))}")
            
            if result.duration:
                output.append(f"Duration: {result.duration:.2f}s")
            
            if result.worker_id:
                output.append(f"Worker: {result.worker_id}")
            
            if result.retry_count > 0:
                output.append(f"Retries: {result.retry_count}")
            
            if result.is_streaming:
                output.append(f"Streaming: Yes")
            
            output.append("")
            
            if result.status == TaskStatus.COMPLETED:
                output.append("Result:")
                output.append(str(result.result)[:500])  # Truncate long results
            elif result.status == TaskStatus.FAILED:
                output.append(f"Error: {result.error}")
            
            return "\n".join(output)
            
        except Exception as e:
            return f"[Error] Failed to get task info: {str(e)}"
    
    def clear_task_history(self) -> str:
        """
        Clear the local task history.
        
        Removes tracked task submissions from memory.
        Does not affect actual task execution or results.
        
        Example:
            clear_task_history()
        """
        count = len(self.task_history)
        self.task_history.clear()
        return f"✓ Cleared {count} tasks from history"


# ============================================================================
# ADD TO TOOLLOADER FUNCTION
# ============================================================================

def add_orchestrator_tools(tool_list: List, agent):
    """
    Add task orchestrator management tools.
    
    Provides comprehensive control over the distributed task execution system:
    - Start/stop orchestrator
    - Submit and monitor tasks (with streaming)
    - Scale worker pools dynamically
    - View statistics and metrics
    - Monitor events
    - Inspect task registry
    
    Call this in your ToolLoader function:
        tool_list = ToolLoader(agent)
        add_orchestrator_tools(tool_list, agent)
        return tool_list
    """
    
    if not ORCHESTRATOR_AVAILABLE:
        print("[Info] Orchestrator tools not loaded - module not available")
        return tool_list
    
    orch_tools = OrchestratorTools(agent)
    
    tool_list.extend([
        StructuredTool.from_function(
            func=orch_tools.start_orchestrator,
            name="orchestrator_start",
            description=(
                "Start the task orchestrator with configurable worker pools. "
                "Initialize distributed task execution system with LLM, Whisper, "
                "Tool, ML, Background, and General workers. Supports Redis pub/sub "
                "and CPU-aware throttling. Returns status and configuration."
            ),
            args_schema=OrchestratorStartInput
        ),
        
        StructuredTool.from_function(
            func=orch_tools.stop_orchestrator,
            name="orchestrator_stop",
            description=(
                "Stop the task orchestrator gracefully. "
                "Shuts down all worker pools after completing running tasks. "
                "No new tasks accepted after shutdown begins."
            ),
        ),
        
        StructuredTool.from_function(
            func=orch_tools.submit_task,
            name="orchestrator_submit_task",
            description=(
                "Submit a task for execution through the orchestrator. "
                "Tasks are queued by priority and executed by appropriate workers. "
                "Supports both regular and streaming (generator) tasks. "
                "Returns task ID for tracking. "
                "Example: submit_task('llm.generate', kwargs={'prompt': 'Hello'})"
            ),
            args_schema=TaskSubmitInput
        ),
        
        StructuredTool.from_function(
            func=orch_tools.wait_for_task,
            name="orchestrator_wait_task",
            description=(
                "Wait for a task to complete and retrieve results. "
                "Blocks until task finishes or timeout. "
                "Set stream=True to stream incremental results from generator tasks. "
                "Returns task result or error. "
                "Example: wait_for_task(task_id='abc123', stream=True)"
            ),
            args_schema=TaskWaitInput
        ),
        
        StructuredTool.from_function(
            func=orch_tools.stream_task,
            name="orchestrator_stream_task",
            description=(
                "Stream results from a task as they arrive. "
                "Convenience wrapper for streaming tasks (LLM generation, etc.). "
                "Works for both streaming and non-streaming tasks. "
                "Example: stream_task(task_id='abc123')"
            ),
            args_schema=TaskWaitInput
        ),
        
        StructuredTool.from_function(
            func=orch_tools.get_orchestrator_stats,
            name="orchestrator_stats",
            description=(
                "Get comprehensive orchestrator statistics. "
                "Shows running status, queue sizes, worker pool info, "
                "per-worker stats (tasks completed/failed, CPU usage), "
                "and recent task history. Essential for monitoring."
            ),
        ),
        
        StructuredTool.from_function(
            func=orch_tools.scale_workers,
            name="orchestrator_scale",
            description=(
                "Scale a worker pool dynamically while running. "
                "Add or remove workers for specific task types. "
                "Scaling is graceful - running tasks complete before removal. "
                "Example: scale_workers('llm', 8) for heavy LLM load"
            ),
            args_schema=WorkerScaleInput
        ),
        
        StructuredTool.from_function(
            func=orch_tools.list_registered_tasks,
            name="orchestrator_list_tasks",
            description=(
                "List all registered tasks in the task registry. "
                "Shows tasks that can be submitted, with metadata like type, "
                "priority, duration, GPU requirements. "
                "Filter by task type or proactive focus flag. "
                "Example: list_registered_tasks(task_type='llm')"
            ),
            args_schema=TaskRegistryQueryInput
        ),
        
        StructuredTool.from_function(
            func=orch_tools.monitor_events,
            name="orchestrator_monitor",
            description=(
                "Monitor orchestrator events for debugging and analysis. "
                "Subscribe to channels: task.started, task.completed, task.failed, "
                "focus.changed. Collects events for specified duration. "
                "Example: monitor_events('task.completed', duration=30.0)"
            ),
            args_schema=EventSubscribeInput
        ),
        
        StructuredTool.from_function(
            func=orch_tools.get_task_info,
            name="orchestrator_task_info",
            description=(
                "Get detailed information about a specific task. "
                "Shows status, execution details, worker info, duration, errors. "
                "Example: get_task_info(task_id='abc123')"
            ),
            args_schema=TaskQueryInput
        ),
        
        StructuredTool.from_function(
            func=orch_tools.clear_task_history,
            name="orchestrator_clear_history",
            description=(
                "Clear the local task history. "
                "Removes tracked submissions from memory. "
                "Does not affect actual task execution."
            ),
        ),
    ])
    
    return tool_list


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

"""
USAGE EXAMPLES:

1. Start the orchestrator:
   orchestrator_start(
       llm_workers=4,
       tool_workers=8,
       cpu_threshold=80.0
   )

2. Submit a task:
   task_id = orchestrator_submit_task(
       task_name="llm.generate",
       kwargs={"prompt": "Write a story", "max_tokens": 500}
   )

3. Stream results:
   orchestrator_stream_task(task_id=task_id)
   # Or:
   orchestrator_wait_task(task_id=task_id, stream=True)

4. Monitor system:
   orchestrator_stats()
   orchestrator_monitor(channel="task.completed", duration=60.0)

5. Scale workers dynamically:
   orchestrator_scale(task_type="llm", num_workers=8)

6. List available tasks:
   orchestrator_list_tasks()
   orchestrator_list_tasks(task_type="llm")

7. Get specific task info:
   orchestrator_task_info(task_id=task_id)

8. Stop orchestrator:
   orchestrator_stop()

EXAMPLE WORKFLOW:

# Start with moderate resources
orchestrator_start(llm_workers=2, tool_workers=4)

# Submit multiple tasks
task1 = orchestrator_submit_task("llm.generate", kwargs={"prompt": "..."})
task2 = orchestrator_submit_task("tool.web_search", kwargs={"query": "..."})

# Check stats
orchestrator_stats()

# Heavy load detected - scale up!
orchestrator_scale(task_type="llm", num_workers=6)

# Stream results
orchestrator_stream_task(task_id=task1)

# Monitor for issues
orchestrator_monitor(channel="task.failed", duration=120.0)

# Done - scale down and stop
orchestrator_scale(task_type="llm", num_workers=1)
orchestrator_stop()
"""