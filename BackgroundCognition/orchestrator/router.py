"""
Task router for intelligent task distribution and parallel execution
"""

import asyncio
from typing import List, Dict, Set, Optional, Any
from collections import defaultdict, deque
import networkx as nx
from datetime import datetime

from .tasks import Task, TaskResult, TaskType, TaskStatus, ParallelBatch
from .workers import WorkerRegistry, BaseWorker
from .workers.base import WorkerCapability


class TaskRouter:
    """
    Routes tasks to appropriate workers and coordinates parallel execution
    """

    def __init__(self, worker_registry: WorkerRegistry):
        self.worker_registry = worker_registry
        self._task_graph = nx.DiGraph()
        self._completed_tasks: Set[str] = set()
        self._lock = asyncio.Lock()

    def analyze_dependencies(self, tasks: List[Task]) -> nx.DiGraph:
        """
        Analyze task dependencies and build a DAG

        Args:
            tasks: List of tasks to analyze

        Returns:
            NetworkX DiGraph representing dependencies
        """
        graph = nx.DiGraph()

        # Add all tasks as nodes
        for task in tasks:
            graph.add_node(task.id, task=task)

        # Add dependency edges
        for task in tasks:
            for dep_id in task.depends_on:
                if dep_id in [t.id for t in tasks]:
                    graph.add_edge(dep_id, task.id)

        return graph

    def get_parallel_batches(self, tasks: List[Task]) -> List[ParallelBatch]:
        """
        Group tasks into parallel execution batches based on dependencies

        Args:
            tasks: List of tasks to group

        Returns:
            List of ParallelBatch objects
        """
        graph = self.analyze_dependencies(tasks)

        # Topological sort to determine execution order
        try:
            topo_order = list(nx.topological_sort(graph))
        except nx.NetworkXError:
            # Cycle detected - cannot parallelize
            raise ValueError("Circular dependency detected in tasks")

        # Group into levels (batches that can run in parallel)
        batches = []
        remaining = set(topo_order)

        while remaining:
            # Find tasks with all dependencies satisfied
            batch = ParallelBatch()
            for task_id in list(remaining):
                task = graph.nodes[task_id]['task']
                deps = set(task.depends_on)

                # Check if all dependencies are completed or in previous batches
                completed_or_batched = self._completed_tasks | {
                    t.id for b in batches for t in b.tasks
                }

                if deps.issubset(completed_or_batched):
                    batch.add_task(task)
                    remaining.remove(task_id)

            if batch.tasks:
                batches.append(batch)
            else:
                # No progress - shouldn't happen with valid DAG
                break

        return batches

    async def route_task(self, task: Task) -> Optional[BaseWorker]:
        """
        Route a task to the best available worker

        Args:
            task: Task to route

        Returns:
            Best worker for this task or None
        """
        # Special routing for different task types
        if task.type == TaskType.OLLAMA_REQUEST:
            # Route to Ollama workers
            workers = self.worker_registry.get_workers_by_capability(
                WorkerCapability.OLLAMA
            )
            available = [w for w in workers if w.can_handle(task)]
            return available[0] if available else None

        elif task.type == TaskType.LLM_REQUEST:
            # Route to any LLM worker (Ollama or API)
            workers = self.worker_registry.get_workers_by_capability(
                WorkerCapability.LLM_INFERENCE
            )
            available = [w for w in workers if w.can_handle(task)]
            # Sort by cost/preference
            available.sort(key=lambda w: (
                w.get_load(),
                getattr(w, 'cost_per_1k_tokens', 0)
            ))
            return available[0] if available else None

        elif task.type == TaskType.DOCKER_TASK:
            # Route to Docker workers
            workers = self.worker_registry.get_workers_by_capability(
                WorkerCapability.DOCKER
            )
            available = [w for w in workers if w.can_handle(task)]
            return available[0] if available else None

        elif task.type == TaskType.CODE_EXECUTION:
            # Route to code execution workers (Docker or remote)
            workers = self.worker_registry.get_workers_by_capability(
                WorkerCapability.CODE_EXECUTION
            )
            available = [w for w in workers if w.can_handle(task)]
            return available[0] if available else None

        else:
            # Generic routing - use worker registry's best match
            return self.worker_registry.get_best_worker(task)

    async def execute_single(self, task: Task) -> TaskResult:
        """
        Execute a single task

        Args:
            task: Task to execute

        Returns:
            TaskResult
        """
        # Route to worker
        worker = await self.route_task(task)

        if not worker:
            return TaskResult(
                success=False,
                error=f"No available worker for task {task.id} (type: {task.type.value})",
            )

        # Execute
        try:
            result = await worker.submit_task(task)
            if result.success:
                async with self._lock:
                    self._completed_tasks.add(task.id)
            return result

        except Exception as e:
            return TaskResult(
                success=False,
                error=f"Execution error: {e}",
            )

    async def execute_parallel(
        self,
        tasks: List[Task],
        max_concurrent: Optional[int] = None
    ) -> List[TaskResult]:
        """
        Execute tasks in parallel where possible

        Args:
            tasks: List of tasks to execute
            max_concurrent: Maximum concurrent tasks (None = unlimited)

        Returns:
            List of TaskResults in same order as input tasks
        """
        # Get parallel batches
        try:
            batches = self.get_parallel_batches(tasks)
        except ValueError as e:
            # Dependency cycle - return error for all tasks
            return [
                TaskResult(success=False, error=str(e))
                for _ in tasks
            ]

        # Track results by task ID
        results_by_id: Dict[str, TaskResult] = {}

        # Execute batches sequentially, tasks within batch in parallel
        for batch in batches:
            batch_tasks = batch.tasks

            # Limit concurrency if specified
            if max_concurrent:
                # Execute in chunks
                for i in range(0, len(batch_tasks), max_concurrent):
                    chunk = batch_tasks[i:i + max_concurrent]
                    chunk_results = await asyncio.gather(*[
                        self.execute_single(task) for task in chunk
                    ])

                    for task, result in zip(chunk, chunk_results):
                        results_by_id[task.id] = result
            else:
                # Execute all in parallel
                batch_results = await asyncio.gather(*[
                    self.execute_single(task) for task in batch_tasks
                ])

                for task, result in zip(batch_tasks, batch_results):
                    results_by_id[task.id] = result

        # Return results in original task order
        return [results_by_id[task.id] for task in tasks]

    async def execute_with_retry(
        self,
        task: Task,
        max_retries: Optional[int] = None
    ) -> TaskResult:
        """
        Execute a task with retry logic

        Args:
            task: Task to execute
            max_retries: Override task's max_retries

        Returns:
            TaskResult
        """
        retries = max_retries if max_retries is not None else task.max_retries
        last_error = None

        for attempt in range(retries + 1):
            result = await self.execute_single(task)

            if result.success:
                return result

            last_error = result.error

            # Wait before retry (exponential backoff)
            if attempt < retries:
                wait_time = task.retry_delay_seconds * (2 ** attempt)
                await asyncio.sleep(wait_time)

        # All retries failed
        return TaskResult(
            success=False,
            error=f"Failed after {retries + 1} attempts. Last error: {last_error}",
        )

    def get_task_stats(self) -> Dict[str, Any]:
        """Get routing statistics"""
        return {
            'completed_tasks': len(self._completed_tasks),
            'available_workers': len(self.worker_registry.get_available_workers()),
            'total_workers': len(self.worker_registry.get_all_workers()),
        }


class SmartScheduler:
    """
    Intelligent task scheduler that optimizes execution order
    """

    def __init__(self, router: TaskRouter):
        self.router = router
        self.task_queue: deque[Task] = deque()
        self._priority_queue: List[Task] = []
        self._lock = asyncio.Lock()

    async def submit(self, task: Task):
        """Submit a task to the scheduler"""
        async with self._lock:
            self.task_queue.append(task)
            self._priority_queue.append(task)
            self._priority_queue.sort()  # Sort by priority

    async def submit_batch(self, tasks: List[Task]):
        """Submit multiple tasks"""
        async with self._lock:
            for task in tasks:
                self.task_queue.append(task)
                self._priority_queue.append(task)
            self._priority_queue.sort()

    async def get_next_batch(self, batch_size: int = 10) -> List[Task]:
        """
        Get next batch of tasks to execute

        Args:
            batch_size: Maximum batch size

        Returns:
            List of tasks ready to execute
        """
        async with self._lock:
            ready_tasks = []

            # Get tasks from priority queue
            for task in list(self._priority_queue[:batch_size]):
                # Check if dependencies are met
                if task.is_ready(self.router._completed_tasks):
                    ready_tasks.append(task)
                    self._priority_queue.remove(task)

                if len(ready_tasks) >= batch_size:
                    break

            return ready_tasks

    async def run_scheduler(
        self,
        max_concurrent: int = 5,
        check_interval: float = 1.0
    ):
        """
        Run the scheduler loop

        Args:
            max_concurrent: Maximum concurrent tasks
            check_interval: How often to check for new tasks (seconds)
        """
        while True:
            # Get next batch
            batch = await self.get_next_batch(max_concurrent)

            if batch:
                # Execute batch
                await self.router.execute_parallel(batch, max_concurrent)

            # Wait before next check
            await asyncio.sleep(check_interval)

            # Check if we should stop (can be controlled externally)
            async with self._lock:
                if not self.task_queue and not self._priority_queue:
                    await asyncio.sleep(check_interval)
