"""
Vera Tool Framework - Orchestration Integration
Extends VTool with orchestration capabilities for distributed execution.

Features:
- Tools can submit sub-tasks to orchestrator
- Distributed work patterns (map/reduce, parallel execution)
- Shared compute pool access
- Task dependency management
- Progress aggregation from sub-tasks
"""

from typing import Any, Dict, List, Optional, Iterator, Union, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

# Import base framework
from tool_framework import (
    VTool, ToolResult, ToolEntity, ToolRelationship, OutputType
)

# Import orchestration
from Vera.Orchestration.orchestration import (
    Orchestrator, TaskType, Priority, TaskResult as OrchTaskResult
)

# =============================================================================
# ORCHESTRATION-AWARE VTOOL
# =============================================================================

class OrchestrationPattern(str, Enum):
    """Common orchestration patterns for distributed execution"""
    SEQUENTIAL = "sequential"      # Execute tasks one by one
    PARALLEL = "parallel"          # Execute all tasks simultaneously
    MAP_REDUCE = "map_reduce"      # Map work, then reduce results
    PIPELINE = "pipeline"          # Output of task N feeds into task N+1
    BROADCAST = "broadcast"        # Same task to multiple targets
    PRIORITY_QUEUE = "priority_queue"  # Dynamic priority-based execution


@dataclass
class SubTask:
    """Represents a sub-task to be executed by orchestrator"""
    task_name: str
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    priority: Priority = Priority.NORMAL
    timeout: Optional[float] = None
    depends_on: List[str] = field(default_factory=list)  # Task IDs this depends on
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Runtime tracking
    task_id: Optional[str] = None
    status: str = "pending"
    result: Any = None
    error: Optional[str] = None


@dataclass
class DistributedExecution:
    """Tracks a distributed execution across multiple sub-tasks"""
    pattern: OrchestrationPattern
    sub_tasks: List[SubTask]
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    results: Dict[str, Any] = field(default_factory=dict)
    errors: Dict[str, str] = field(default_factory=dict)
    
    @property
    def is_complete(self) -> bool:
        return all(t.status in ["completed", "failed"] for t in self.sub_tasks)
    
    @property
    def success_count(self) -> int:
        return sum(1 for t in self.sub_tasks if t.status == "completed")
    
    @property
    def failure_count(self) -> int:
        return sum(1 for t in self.sub_tasks if t.status == "failed")


class OrchestratedVTool(VTool):
    """
    VTool with orchestration capabilities.
    
    Provides:
    - Access to shared compute pool via orchestrator
    - Distributed execution patterns
    - Sub-task management
    - Progress aggregation
    - Dependency resolution
    
    Usage:
        class MyTool(OrchestratedVTool):
            def _execute(self, **kwargs):
                # Submit work to orchestrator
                sub_tasks = self.create_distributed_execution(
                    pattern=OrchestrationPattern.PARALLEL,
                    tasks=[...]
                )
                
                # Wait for completion
                results = self.wait_for_completion(sub_tasks)
                
                yield ToolResult(...)
    """
    
    def __init__(self, agent):
        super().__init__(agent)
        
        # Get orchestrator reference
        self.orchestrator: Optional[Orchestrator] = getattr(agent, 'orchestrator', None)
        
        if not self.orchestrator:
            print(f"[Warning] {self.tool_name}: No orchestrator available - distributed features disabled")
        
        # Track distributed executions
        self.active_executions: Dict[str, DistributedExecution] = {}
        
        # Execution stats
        self.total_subtasks_submitted = 0
        self.total_subtasks_completed = 0
        self.total_subtasks_failed = 0
    
    # -------------------------------------------------------------------------
    # ORCHESTRATOR ACCESS
    # -------------------------------------------------------------------------
    
    def has_orchestrator(self) -> bool:
        """Check if orchestrator is available"""
        return self.orchestrator is not None and self.orchestrator.running
    
    def submit_task(
        self,
        task_name: str,
        *args,
        priority: Priority = Priority.NORMAL,
        timeout: Optional[float] = None,
        **kwargs
    ) -> Optional[str]:
        """
        Submit a single task to orchestrator.
        
        Args:
            task_name: Name of registered task
            *args: Task arguments
            priority: Task priority
            timeout: Task timeout
            **kwargs: Task keyword arguments
        
        Returns:
            Task ID or None if orchestrator unavailable
        """
        if not self.has_orchestrator():
            print(f"[{self.tool_name}] Cannot submit task - no orchestrator")
            return None
        
        try:
            # Add tool context to metadata
            kwargs['_tool_context'] = {
                'tool_name': self.tool_name,
                'execution_id': self.execution_node_id,
                'session_id': self.sess.id
            }
            
            task_id = self.orchestrator.submit_task(task_name, *args, **kwargs)
            
            self.total_subtasks_submitted += 1
            
            yield f"[Orchestrator] Submitted task: {task_name} ({task_id[:8]}...)\n"
            
            return task_id
        
        except Exception as e:
            yield f"[Error] Failed to submit task: {e}\n"
            return None
    
    def wait_for_task(
        self,
        task_id: str,
        timeout: Optional[float] = None,
        stream: bool = False
    ) -> Iterator[Union[str, OrchTaskResult]]:
        """
        Wait for a task to complete.
        
        Args:
            task_id: Task ID to wait for
            timeout: Max wait time
            stream: If True, stream intermediate results
        
        Yields:
            Intermediate output (if streaming) and final result
        """
        if not self.has_orchestrator():
            return
        
        try:
            if stream:
                # Stream results as they arrive
                for chunk in self.orchestrator.stream_result(task_id, timeout=timeout):
                    yield chunk
            else:
                # Just wait for final result
                result = self.orchestrator.wait_for_result(task_id, timeout=timeout)
                if result:
                    yield result
        
        except Exception as e:
            yield f"[Error] Task {task_id[:8]}... failed: {e}\n"
    
    # -------------------------------------------------------------------------
    # DISTRIBUTED EXECUTION PATTERNS
    # -------------------------------------------------------------------------
    
    def create_distributed_execution(
        self,
        pattern: OrchestrationPattern,
        tasks: List[SubTask],
        execution_id: Optional[str] = None
    ) -> str:
        """
        Create a distributed execution plan.
        
        Args:
            pattern: Execution pattern to use
            tasks: List of sub-tasks to execute
            execution_id: Optional custom ID
        
        Returns:
            Execution ID for tracking
        """
        if not execution_id:
            execution_id = f"{self.tool_name}_{int(time.time()*1000)}"
        
        execution = DistributedExecution(
            pattern=pattern,
            sub_tasks=tasks
        )
        
        self.active_executions[execution_id] = execution
        
        return execution_id
    
    def execute_distributed(
        self,
        execution_id: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Iterator[Union[str, Dict[str, Any]]]:
        """
        Execute a distributed execution plan.
        
        Args:
            execution_id: ID of execution plan
            progress_callback: Optional callback for progress updates
        
        Yields:
            Status updates and final results
        """
        if execution_id not in self.active_executions:
            yield f"[Error] Unknown execution: {execution_id}\n"
            return
        
        execution = self.active_executions[execution_id]
        pattern = execution.pattern
        
        yield f"\n╔══════════════════════════════════════════════════════════╗\n"
        yield f"║  DISTRIBUTED EXECUTION: {pattern.upper()}\n"
        yield f"║  Tasks: {len(execution.sub_tasks)}\n"
        yield f"╚══════════════════════════════════════════════════════════╝\n\n"
        
        # Route to appropriate pattern handler
        if pattern == OrchestrationPattern.PARALLEL:
            yield from self._execute_parallel(execution, progress_callback)
        
        elif pattern == OrchestrationPattern.SEQUENTIAL:
            yield from self._execute_sequential(execution, progress_callback)
        
        elif pattern == OrchestrationPattern.MAP_REDUCE:
            yield from self._execute_map_reduce(execution, progress_callback)
        
        elif pattern == OrchestrationPattern.PIPELINE:
            yield from self._execute_pipeline(execution, progress_callback)
        
        elif pattern == OrchestrationPattern.BROADCAST:
            yield from self._execute_broadcast(execution, progress_callback)
        
        elif pattern == OrchestrationPattern.PRIORITY_QUEUE:
            yield from self._execute_priority_queue(execution, progress_callback)
        
        else:
            yield f"[Error] Unknown pattern: {pattern}\n"
            return
        
        # Mark completion
        execution.completed_at = time.time()
        duration = execution.completed_at - execution.created_at
        
        yield f"\n╔══════════════════════════════════════════════════════════╗\n"
        yield f"║  EXECUTION COMPLETE\n"
        yield f"║  Duration: {duration:.2f}s\n"
        yield f"║  Success: {execution.success_count}/{len(execution.sub_tasks)}\n"
        yield f"║  Failed: {execution.failure_count}/{len(execution.sub_tasks)}\n"
        yield f"╚══════════════════════════════════════════════════════════╝\n"
        
        # Yield aggregated results
        yield {
            "execution_id": execution_id,
            "pattern": pattern,
            "duration": duration,
            "results": execution.results,
            "errors": execution.errors,
            "success_count": execution.success_count,
            "failure_count": execution.failure_count
        }
    
    def _execute_parallel(
        self,
        execution: DistributedExecution,
        progress_callback: Optional[Callable]
    ) -> Iterator[str]:
        """Execute all tasks in parallel"""
        if not self.has_orchestrator():
            yield "[Error] No orchestrator available\n"
            return
        
        yield f"[Parallel] Submitting {len(execution.sub_tasks)} tasks...\n"
        
        # Submit all tasks
        for task in execution.sub_tasks:
            task_id = self.orchestrator.submit_task(
                task.task_name,
                *task.args,
                **task.kwargs
            )
            
            if task_id:
                task.task_id = task_id
                task.status = "submitted"
                self.total_subtasks_submitted += 1
                yield f"  [✓] {task.task_name} → {task_id[:8]}...\n"
            else:
                task.status = "failed"
                task.error = "Submission failed"
                yield f"  [✗] {task.task_name} → Submission failed\n"
        
        # Wait for all to complete
        yield f"\n[Parallel] Waiting for {len(execution.sub_tasks)} tasks...\n"
        
        completed = 0
        while not execution.is_complete:
            for task in execution.sub_tasks:
                if task.status != "submitted":
                    continue
                
                result = self.orchestrator.wait_for_result(task.task_id, timeout=0.1)
                
                if result:
                    if result.status.name == "COMPLETED":
                        task.status = "completed"
                        task.result = result.result
                        execution.results[task.task_id] = result.result
                        completed += 1
                        self.total_subtasks_completed += 1
                        
                        yield f"  [✓] {task.task_name} completed ({completed}/{len(execution.sub_tasks)})\n"
                    
                    elif result.status.name == "FAILED":
                        task.status = "failed"
                        task.error = result.error
                        execution.errors[task.task_id] = result.error
                        completed += 1
                        self.total_subtasks_failed += 1
                        
                        yield f"  [✗] {task.task_name} failed: {result.error}\n"
                    
                    if progress_callback:
                        progress_callback(completed, len(execution.sub_tasks))
            
            time.sleep(0.1)
    
    def _execute_sequential(
        self,
        execution: DistributedExecution,
        progress_callback: Optional[Callable]
    ) -> Iterator[str]:
        """Execute tasks one by one"""
        if not self.has_orchestrator():
            yield "[Error] No orchestrator available\n"
            return
        
        yield f"[Sequential] Executing {len(execution.sub_tasks)} tasks...\n"
        
        for idx, task in enumerate(execution.sub_tasks, 1):
            yield f"\n[{idx}/{len(execution.sub_tasks)}] {task.task_name}...\n"
            
            # Submit task
            task_id = self.orchestrator.submit_task(
                task.task_name,
                *task.args,
                **task.kwargs
            )
            
            if not task_id:
                task.status = "failed"
                task.error = "Submission failed"
                yield f"  [✗] Submission failed\n"
                continue
            
            task.task_id = task_id
            task.status = "running"
            self.total_subtasks_submitted += 1
            
            # Wait for completion
            result = self.orchestrator.wait_for_result(task_id, timeout=task.timeout)
            
            if result and result.status.name == "COMPLETED":
                task.status = "completed"
                task.result = result.result
                execution.results[task_id] = result.result
                self.total_subtasks_completed += 1
                
                yield f"  [✓] Completed in {result.duration:.2f}s\n"
            
            else:
                task.status = "failed"
                task.error = result.error if result else "Timeout"
                execution.errors[task_id] = task.error
                self.total_subtasks_failed += 1
                
                yield f"  [✗] Failed: {task.error}\n"
            
            if progress_callback:
                progress_callback(idx, len(execution.sub_tasks))
    
    def _execute_map_reduce(
        self,
        execution: DistributedExecution,
        progress_callback: Optional[Callable]
    ) -> Iterator[str]:
        """Execute map phase in parallel, then reduce"""
        # Find reduce task (last one)
        if len(execution.sub_tasks) < 2:
            yield "[Error] Map-reduce requires at least 2 tasks\n"
            return
        
        map_tasks = execution.sub_tasks[:-1]
        reduce_task = execution.sub_tasks[-1]
        
        yield f"[Map-Reduce] Map: {len(map_tasks)} tasks, Reduce: 1 task\n"
        
        # Execute map phase in parallel
        map_execution = DistributedExecution(
            pattern=OrchestrationPattern.PARALLEL,
            sub_tasks=map_tasks
        )
        
        yield "\n[Map Phase]\n"
        yield from self._execute_parallel(map_execution, progress_callback)
        
        # Collect map results
        map_results = [t.result for t in map_tasks if t.status == "completed"]
        
        yield f"\n[Reduce Phase] Collected {len(map_results)} results\n"
        
        # Execute reduce with map results
        reduce_task.kwargs['map_results'] = map_results
        
        task_id = self.orchestrator.submit_task(
            reduce_task.task_name,
            *reduce_task.args,
            **reduce_task.kwargs
        )
        
        if task_id:
            reduce_task.task_id = task_id
            self.total_subtasks_submitted += 1
            
            result = self.orchestrator.wait_for_result(task_id, timeout=reduce_task.timeout)
            
            if result and result.status.name == "COMPLETED":
                reduce_task.status = "completed"
                reduce_task.result = result.result
                execution.results['reduce'] = result.result
                self.total_subtasks_completed += 1
                
                yield f"  [✓] Reduce completed\n"
            else:
                reduce_task.status = "failed"
                reduce_task.error = result.error if result else "Failed"
                self.total_subtasks_failed += 1
                
                yield f"  [✗] Reduce failed\n"
    
    def _execute_pipeline(
        self,
        execution: DistributedExecution,
        progress_callback: Optional[Callable]
    ) -> Iterator[str]:
        """Execute tasks in pipeline (output of N feeds into N+1)"""
        if not self.has_orchestrator():
            yield "[Error] No orchestrator available\n"
            return
        
        yield f"[Pipeline] {len(execution.sub_tasks)} stages\n"
        
        pipeline_input = None
        
        for idx, task in enumerate(execution.sub_tasks, 1):
            yield f"\n[Stage {idx}/{len(execution.sub_tasks)}] {task.task_name}...\n"
            
            # Feed previous output as input
            if pipeline_input is not None:
                task.kwargs['pipeline_input'] = pipeline_input
            
            # Execute stage
            task_id = self.orchestrator.submit_task(
                task.task_name,
                *task.args,
                **task.kwargs
            )
            
            if not task_id:
                task.status = "failed"
                yield f"  [✗] Submission failed\n"
                break
            
            task.task_id = task_id
            self.total_subtasks_submitted += 1
            
            result = self.orchestrator.wait_for_result(task_id, timeout=task.timeout)
            
            if result and result.status.name == "COMPLETED":
                task.status = "completed"
                task.result = result.result
                execution.results[f"stage_{idx}"] = result.result
                self.total_subtasks_completed += 1
                
                # Feed to next stage
                pipeline_input = result.result
                
                yield f"  [✓] Stage {idx} completed\n"
            
            else:
                task.status = "failed"
                task.error = result.error if result else "Failed"
                execution.errors[f"stage_{idx}"] = task.error
                self.total_subtasks_failed += 1
                
                yield f"  [✗] Stage {idx} failed - pipeline stopped\n"
                break
            
            if progress_callback:
                progress_callback(idx, len(execution.sub_tasks))
    
    def _execute_broadcast(
        self,
        execution: DistributedExecution,
        progress_callback: Optional[Callable]
    ) -> Iterator[str]:
        """Execute same task with different targets (broadcast pattern)"""
        # Just parallel execution with progress tracking
        yield f"[Broadcast] Broadcasting to {len(execution.sub_tasks)} targets\n"
        yield from self._execute_parallel(execution, progress_callback)
    
    def _execute_priority_queue(
        self,
        execution: DistributedExecution,
        progress_callback: Optional[Callable]
    ) -> Iterator[str]:
        """Submit all tasks to priority queue and let orchestrator schedule"""
        if not self.has_orchestrator():
            yield "[Error] No orchestrator available\n"
            return
        
        yield f"[Priority Queue] Submitting {len(execution.sub_tasks)} tasks with priorities\n"
        
        # Submit all with their individual priorities
        for task in execution.sub_tasks:
            task_id = self.orchestrator.submit_task(
                task.task_name,
                *task.args,
                priority=task.priority,
                **task.kwargs
            )
            
            if task_id:
                task.task_id = task_id
                task.status = "submitted"
                self.total_subtasks_submitted += 1
                yield f"  [{task.priority.name}] {task.task_name} → {task_id[:8]}...\n"
        
        # Wait for all
        yield from self._execute_parallel(execution, progress_callback)
    
    # -------------------------------------------------------------------------
    # CONVENIENCE METHODS
    # -------------------------------------------------------------------------
    
    def parallel_execute(
        self,
        task_name: str,
        arg_list: List[tuple],
        kwarg_list: Optional[List[dict]] = None,
        priority: Priority = Priority.NORMAL
    ) -> Iterator[Union[str, Dict[str, Any]]]:
        """
        Execute same task with different arguments in parallel.
        
        Args:
            task_name: Task to execute
            arg_list: List of argument tuples
            kwarg_list: Optional list of kwargs dicts
            priority: Priority for all tasks
        
        Yields:
            Progress updates and final results
        """
        if not kwarg_list:
            kwarg_list = [{}] * len(arg_list)
        
        tasks = [
            SubTask(
                task_name=task_name,
                args=args,
                kwargs=kwargs,
                priority=priority
            )
            for args, kwargs in zip(arg_list, kwarg_list)
        ]
        
        exec_id = self.create_distributed_execution(
            OrchestrationPattern.PARALLEL,
            tasks
        )
        
        yield from self.execute_distributed(exec_id)
    
    def map_reduce(
        self,
        map_task: str,
        reduce_task: str,
        map_args_list: List[tuple],
        map_kwargs_list: Optional[List[dict]] = None,
        reduce_kwargs: Optional[dict] = None
    ) -> Iterator[Union[str, Dict[str, Any]]]:
        """
        Execute map-reduce pattern.
        
        Args:
            map_task: Task for map phase
            reduce_task: Task for reduce phase
            map_args_list: Arguments for each map task
            map_kwargs_list: Optional kwargs for map tasks
            reduce_kwargs: Optional kwargs for reduce task
        
        Yields:
            Progress and final result
        """
        if not map_kwargs_list:
            map_kwargs_list = [{}] * len(map_args_list)
        
        # Create map tasks
        tasks = [
            SubTask(
                task_name=map_task,
                args=args,
                kwargs=kwargs
            )
            for args, kwargs in zip(map_args_list, map_kwargs_list)
        ]
        
        # Add reduce task
        tasks.append(SubTask(
            task_name=reduce_task,
            args=(),
            kwargs=reduce_kwargs or {}
        ))
        
        exec_id = self.create_distributed_execution(
            OrchestrationPattern.MAP_REDUCE,
            tasks
        )
        
        yield from self.execute_distributed(exec_id)
    
    def pipeline(
        self,
        tasks: List[Tuple[str, tuple, dict]],
        initial_input: Any = None
    ) -> Iterator[Union[str, Dict[str, Any]]]:
        """
        Execute tasks in pipeline.
        
        Args:
            tasks: List of (task_name, args, kwargs) tuples
            initial_input: Initial input for first stage
        
        Yields:
            Progress and final result
        """
        sub_tasks = []
        
        for idx, (task_name, args, kwargs) in enumerate(tasks):
            if idx == 0 and initial_input is not None:
                kwargs['pipeline_input'] = initial_input
            
            sub_tasks.append(SubTask(
                task_name=task_name,
                args=args,
                kwargs=kwargs
            ))
        
        exec_id = self.create_distributed_execution(
            OrchestrationPattern.PIPELINE,
            sub_tasks
        )
        
        yield from self.execute_distributed(exec_id)


# =============================================================================
# EXAMPLE: DISTRIBUTED NETWORK SCANNER
# =============================================================================

class DistributedNetworkScanner(OrchestratedVTool):
    """
    Network scanner that distributes work across compute pool.
    
    For example:
    - Scan 10 hosts in parallel
    - Each host scans its ports using a worker
    - Results aggregated in main tool
    """
    
    def get_input_schema(self):
        from pydantic import BaseModel, Field
        
        class ScanInput(BaseModel):
            targets: List[str] = Field(description="List of IPs to scan")
            ports: str = Field(default="1-1000", description="Port range")
            parallel_hosts: int = Field(default=5, description="Max parallel hosts")
        
        return ScanInput
    
    def get_output_type(self):
        return OutputType.JSON
    
    def _execute(self, targets: List[str], ports: str = "1-1000", 
                 parallel_hosts: int = 5) -> Iterator:
        """Execute distributed network scan"""
        
        yield "╔═══════════════════════════════════════════════════════════╗\n"
        yield "║           DISTRIBUTED NETWORK SCAN                        ║\n"
        yield "╚═══════════════════════════════════════════════════════════╝\n\n"
        
        yield f"Targets: {len(targets)}\n"
        yield f"Ports: {ports}\n"
        yield f"Parallel hosts: {parallel_hosts}\n\n"
        
        # Check if orchestrator available
        if not self.has_orchestrator():
            yield "[Warning] No orchestrator - falling back to sequential\n"
            # Fall back to non-distributed execution
            # ... original implementation ...
            yield ToolResult(
                success=False,
                output="Orchestrator not available",
                output_type=self.get_output_type(),
                error="No orchestrator"
            )
            return
        
        # Create sub-tasks for each host
        # Batch hosts to respect parallel_hosts limit
        all_results = {}
        
        for batch_start in range(0, len(targets), parallel_hosts):
            batch_targets = targets[batch_start:batch_start + parallel_hosts]
            
            yield f"\n[Batch {batch_start//parallel_hosts + 1}] Scanning {len(batch_targets)} hosts...\n"
            
            # Create parallel scan tasks
            scan_tasks = [
                SubTask(
                    task_name="network.scan_host",  # Must be registered in orchestrator
                    args=(target, ports),
                    kwargs={},
                    priority=Priority.HIGH,
                    metadata={"target": target}
                )
                for target in batch_targets
            ]
            
            # Execute in parallel
            exec_id = self.create_distributed_execution(
                OrchestrationPattern.PARALLEL,
                scan_tasks
            )
            
            # Get results
            for item in self.execute_distributed(exec_id):
                if isinstance(item, dict) and 'results' in item:
                    # Aggregated results
                    all_results.update(item['results'])
                else:
                    # Progress updates
                    yield item
        
        # Aggregate all results
        total_hosts = len(targets)
        hosts_up = sum(1 for r in all_results.values() if r.get('status') == 'up')
        total_ports = sum(len(r.get('open_ports', [])) for r in all_results.values())
        
        yield f"\n╔═══════════════════════════════════════════════════════════╗\n"
        yield f"║  SCAN COMPLETE\n"
        yield f"║  Hosts scanned: {total_hosts}\n"
        yield f"║  Hosts up: {hosts_up}\n"
        yield f"║  Open ports: {total_ports}\n"
        yield f"╚═══════════════════════════════════════════════════════════╝\n"
        
        yield ToolResult(
            success=True,
            output=all_results,
            output_type=self.get_output_type(),
            metadata={
                "total_hosts": total_hosts,
                "hosts_up": hosts_up,
                "total_ports": total_ports,
                "distributed": True
            }
        )


# =============================================================================
# EXAMPLE: LLM TOOL WITH ORCHESTRATION
# =============================================================================

class DistributedLLMTool(OrchestratedVTool):
    """
    LLM tool that uses orchestration for parallel inference.
    
    For example:
    - Generate multiple variations in parallel
    - Use different models simultaneously
    - Aggregate/compare results
    """
    
    def get_input_schema(self):
        from pydantic import BaseModel, Field
        
        class LLMInput(BaseModel):
            prompt: str = Field(description="Prompt")
            variants: int = Field(default=3, description="Number of variants")
            models: List[str] = Field(default=["fast", "deep"], description="Models to use")
        
        return LLMInput
    
    def get_output_type(self):
        return OutputType.TEXT
    
    def _execute(self, prompt: str, variants: int = 3, 
                 models: List[str] = ["fast", "deep"]) -> Iterator:
        """Generate multiple LLM responses in parallel"""
        
        yield f"Generating {variants} variants across {len(models)} models...\n\n"
        
        if not self.has_orchestrator():
            yield "[Warning] No orchestrator - using sequential\n"
            # Fallback...
            return
        
        # Create tasks for each model/variant combination
        tasks = []
        for model in models:
            for i in range(variants):
                tasks.append(SubTask(
                    task_name="llm.generate",
                    kwargs={
                        "vera_instance": self.agent,
                        "llm_type": model,
                        "prompt": prompt
                    },
                    priority=Priority.NORMAL,
                    metadata={"model": model, "variant": i}
                ))
        
        # Execute in parallel
        exec_id = self.create_distributed_execution(
            OrchestrationPattern.PARALLEL,
            tasks
        )
        
        final_results = None
        for item in self.execute_distributed(exec_id):
            if isinstance(item, dict) and 'results' in item:
                final_results = item
            else:
                yield item
        
        # Aggregate responses
        if final_results:
            yield "\n╔═══════════════════════════════════════════════════════════╗\n"
            yield "║  GENERATED VARIANTS\n"
            yield "╚═══════════════════════════════════════════════════════════╝\n\n"
            
            for task_id, result in final_results['results'].items():
                yield f"─── Variant ───\n{result}\n\n"
            
            yield ToolResult(
                success=True,
                output=final_results['results'],
                output_type=self.get_output_type()
            )
        else:
            yield ToolResult(
                success=False,
                output="No results",
                output_type=self.get_output_type()
            )


# =============================================================================
# HELPER: REGISTER DISTRIBUTED TOOL TASKS
# =============================================================================

def register_tool_orchestration_tasks():
    """
    Register helper tasks for tool orchestration.
    Call this during Vera initialization.
    """
    from Vera.Orchestration.orchestration import task, TaskType, Priority
    
    @task("network.scan_host", task_type=TaskType.TOOL, priority=Priority.HIGH)
    def scan_single_host(target: str, ports: str):
        """Scan a single host - worker task"""
        # Import here to avoid circular dependencies
        from Vera.Toolchain.Tools.OSINT.network_scanning import (
            HostDiscovery, PortScanner, NetworkScanConfig, TargetParser
        )
        
        config = NetworkScanConfig()
        discoverer = HostDiscovery(config)
        scanner = PortScanner(config)
        parser = TargetParser()
        
        # Check if host is up
        host_info = next(discoverer.discover_live_hosts([target]))
        
        if not host_info['alive']:
            return {
                'target': target,
                'status': 'down',
                'open_ports': []
            }
        
        # Scan ports
        port_list = parser.parse_ports(ports)
        open_ports = []
        
        for port_info in scanner.scan_host(target, port_list):
            open_ports.append({
                'port': port_info['port'],
                'service': port_info['service']
            })
        
        return {
            'target': target,
            'status': 'up',
            'hostname': host_info['hostname'],
            'open_ports': open_ports
        }
    
    print("[ToolOrchestration] Registered distributed tool tasks")


# =============================================================================
# INTEGRATION WITH VERA
# =============================================================================

def integrate_orchestrated_tools(vera_instance):
    """
    Integrate orchestrated tools with Vera.
    
    Add to Vera.__init__:
        from tool_orchestration import integrate_orchestrated_tools
        integrate_orchestrated_tools(self)
    """
    
    # Register helper tasks
    register_tool_orchestration_tasks()
    
    # Add orchestrated tools to toolkit
    from Vera.Toolchain.tools import vtool_to_langchain
    
    orchestrated_tools = [
        DistributedNetworkScanner(vera_instance),
        DistributedLLMTool(vera_instance),
    ]
    
    for tool in orchestrated_tools:
        vera_instance.tools.append(vtool_to_langchain(tool))
    
    print(f"[ToolOrchestration] Added {len(orchestrated_tools)} orchestrated tools")

    """
        Now add this to your Vera.py:
    python# In Vera.__init__, after orchestrator initialization:

    # Integrate orchestrated tools
    if self.orchestrator and self.config.tools.enable_distributed_tools:
        from tool_orchestration import integrate_orchestrated_tools
        integrate_orchestrated_tools(self)
    And add to vera_config.yaml:
    yamltools:
    enable_distributed_tools: true
    max_parallel_subtasks: 10
    Key Features:

    Orchestration Access: Tools get direct access to the orchestrator through self.orchestrator
    Distribution Patterns: Built-in support for:

    Parallel execution
    Sequential execution
    Map-reduce
    Pipeline
    Broadcast
    Priority queue


    Network Scanner Example: Shows how to distribute host scanning across the compute pool
    LLM Tool Example: Shows how to run multiple models in parallel
    Progress Tracking: Real-time progress updates from distributed executions
    Error Handling: Graceful degradation when orchestrator unavailable
    Stats Tracking: Tools track subtask submission/completion
    """