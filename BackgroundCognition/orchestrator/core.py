"""
Core orchestrator that ties all components together
"""

import asyncio
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from collections import deque
import logging

from .tasks import Task, TaskResult, TaskType, TaskStatus, TaskPriority
from .workers import (
    WorkerRegistry,
    BaseWorker,
    DockerWorker,
    DockerWorkerPool,
    OllamaWorker,
    LLMAPIWorker,
    RemoteWorker,
    WorkerConfig,
)
from .resources import ResourceManager, APIQuota
from .router import TaskRouter, SmartScheduler


logger = logging.getLogger(__name__)


class OrchestratorConfig:
    """Configuration for the unified orchestrator"""

    def __init__(
        self,
        max_concurrent_tasks: int = 10,
        enable_auto_scaling: bool = True,
        docker_pool_size: int = 3,
        docker_image: str = "vera-worker:latest",
        ollama_url: str = "http://localhost:11434",
        health_check_interval: int = 30,
        task_timeout_seconds: int = 300,
    ):
        self.max_concurrent_tasks = max_concurrent_tasks
        self.enable_auto_scaling = enable_auto_scaling
        self.docker_pool_size = docker_pool_size
        self.docker_image = docker_image
        self.ollama_url = ollama_url
        self.health_check_interval = health_check_interval
        self.task_timeout_seconds = task_timeout_seconds


class UnifiedOrchestrator:
    """
    Unified orchestration backend for Vera-AI

    Manages all compute tasks with intelligent routing, resource management,
    and worker pool orchestration.
    """

    def __init__(self, config: Optional[OrchestratorConfig] = None):
        self.config = config or OrchestratorConfig()

        # Core components
        self.worker_registry = WorkerRegistry()
        self.resource_manager = ResourceManager()
        self.router = TaskRouter(self.worker_registry)
        self.scheduler = SmartScheduler(self.router)

        # Task tracking
        self.task_history: Dict[str, Task] = {}
        self.active_tasks: Dict[str, Task] = {}
        self.task_queue: deque[Task] = deque()

        # Worker pools
        self.docker_pool: Optional[DockerWorkerPool] = None

        # State
        self.is_running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        self._health_check_task: Optional[asyncio.Task] = None

        # Metrics
        self.metrics = {
            'tasks_submitted': 0,
            'tasks_completed': 0,
            'tasks_failed': 0,
            'total_execution_time_ms': 0,
            'started_at': None,
        }

        # Event hooks
        self.on_task_complete: Optional[Callable[[Task, TaskResult], None]] = None
        self.on_task_failed: Optional[Callable[[Task, str], None]] = None

    async def start(self):
        """Start the orchestrator"""
        if self.is_running:
            logger.warning("Orchestrator already running")
            return

        logger.info("Starting Unified Orchestrator")
        self.is_running = True
        self.metrics['started_at'] = datetime.utcnow()

        try:
            # Initialize Docker worker pool
            if self.config.docker_pool_size > 0:
                await self._initialize_docker_pool()

            # Initialize Ollama worker
            await self._initialize_ollama_worker()

            # Start background tasks
            self._scheduler_task = asyncio.create_task(self._run_scheduler())
            self._health_check_task = asyncio.create_task(self._run_health_checks())

            logger.info("Orchestrator started successfully")

        except Exception as e:
            logger.error(f"Failed to start orchestrator: {e}")
            self.is_running = False
            raise

    async def stop(self):
        """Stop the orchestrator"""
        if not self.is_running:
            return

        logger.info("Stopping Unified Orchestrator")
        self.is_running = False

        # Cancel background tasks
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass

        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        # Stop all workers
        for worker in self.worker_registry.get_all_workers():
            await worker.stop()

        # Stop Docker pool
        if self.docker_pool:
            await self.docker_pool.stop()

        logger.info("Orchestrator stopped")

    async def _initialize_docker_pool(self):
        """Initialize Docker worker pool"""
        logger.info(f"Initializing Docker pool with {self.config.docker_pool_size} workers")

        worker_config = WorkerConfig(
            max_concurrent_tasks=1,
            timeout_seconds=self.config.task_timeout_seconds,
        )

        self.docker_pool = DockerWorkerPool(
            image=self.config.docker_image,
            pool_size=self.config.docker_pool_size,
            worker_config=worker_config,
        )

        workers = await self.docker_pool.start()

        # Register workers
        for worker in workers:
            await self.worker_registry.register(worker)

        logger.info(f"Docker pool initialized with {len(workers)} workers")

    async def _initialize_ollama_worker(self):
        """Initialize Ollama worker"""
        logger.info("Initializing Ollama worker")

        worker = OllamaWorker(
            ollama_url=self.config.ollama_url,
            worker_id="ollama-local",
            config=WorkerConfig(
                max_concurrent_tasks=2,
                timeout_seconds=300,
            ),
        )

        if await worker.start():
            await self.worker_registry.register(worker)
            await self.resource_manager.register_ollama(worker)
            logger.info("Ollama worker initialized")
        else:
            logger.warning("Failed to initialize Ollama worker")

    async def register_llm_api(
        self,
        api_type: str,
        api_key: str,
        rate_limit_per_minute: int = 60,
        cost_per_1k_tokens: float = 0.0,
        quota: Optional[APIQuota] = None,
    ) -> str:
        """
        Register an LLM API worker

        Args:
            api_type: API type ('openai', 'anthropic', 'gemini')
            api_key: API key
            rate_limit_per_minute: Rate limit
            cost_per_1k_tokens: Cost per 1k tokens
            quota: Optional quota configuration

        Returns:
            Worker ID
        """
        worker = LLMAPIWorker(
            api_type=api_type,
            api_key=api_key,
            worker_id=f"{api_type}-api",
            rate_limit_per_minute=rate_limit_per_minute,
            cost_per_1k_tokens=cost_per_1k_tokens,
        )

        if await worker.start():
            await self.worker_registry.register(worker)
            await self.resource_manager.register_llm_api(worker, quota)
            logger.info(f"Registered {api_type} API worker")
            return worker.id
        else:
            raise Exception(f"Failed to start {api_type} API worker")

    async def register_remote_worker(
        self,
        remote_url: str,
        worker_id: Optional[str] = None,
        auth_token: Optional[str] = None,
    ) -> str:
        """
        Register a remote worker

        Args:
            remote_url: URL of remote worker
            worker_id: Optional worker ID
            auth_token: Optional auth token

        Returns:
            Worker ID
        """
        worker = RemoteWorker(
            remote_url=remote_url,
            worker_id=worker_id,
            auth_token=auth_token,
        )

        if await worker.start():
            await self.worker_registry.register(worker)
            logger.info(f"Registered remote worker: {remote_url}")
            return worker.id
        else:
            raise Exception(f"Failed to start remote worker: {remote_url}")

    async def submit_task(
        self,
        task: Task,
        wait: bool = False,
    ) -> Optional[TaskResult]:
        """
        Submit a task to the orchestrator

        Args:
            task: Task to submit
            wait: If True, wait for task completion and return result

        Returns:
            TaskResult if wait=True, None otherwise
        """
        if not self.is_running:
            raise RuntimeError("Orchestrator not running")

        # Track task
        self.task_history[task.id] = task
        self.active_tasks[task.id] = task
        self.metrics['tasks_submitted'] += 1

        # Submit to scheduler
        await self.scheduler.submit(task)

        logger.debug(f"Task {task.id} submitted (type: {task.type.value})")

        if wait:
            # Wait for completion
            while task.id in self.active_tasks:
                await asyncio.sleep(0.1)

            return task.result

        return None

    async def submit_batch(
        self,
        tasks: List[Task],
        execute_parallel: bool = True,
        wait: bool = False,
    ) -> Optional[List[TaskResult]]:
        """
        Submit a batch of tasks

        Args:
            tasks: List of tasks to submit
            execute_parallel: Execute in parallel if possible
            wait: Wait for all tasks to complete

        Returns:
            List of TaskResults if wait=True, None otherwise
        """
        if not self.is_running:
            raise RuntimeError("Orchestrator not running")

        # Track tasks
        for task in tasks:
            self.task_history[task.id] = task
            self.active_tasks[task.id] = task
            self.metrics['tasks_submitted'] += 1

        if execute_parallel:
            # Execute immediately in parallel
            if wait:
                results = await self.router.execute_parallel(
                    tasks,
                    max_concurrent=self.config.max_concurrent_tasks
                )

                # Mark tasks as complete
                for task, result in zip(tasks, results):
                    self._handle_task_completion(task, result)

                return results
            else:
                # Submit to scheduler
                await self.scheduler.submit_batch(tasks)
        else:
            # Submit to scheduler for sequential execution
            await self.scheduler.submit_batch(tasks)

            if wait:
                # Wait for all tasks
                results = []
                for task in tasks:
                    while task.id in self.active_tasks:
                        await asyncio.sleep(0.1)
                    results.append(task.result)
                return results

        return None

    async def execute_tool_call(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL,
    ) -> TaskResult:
        """
        Execute a tool call through the orchestrator

        Args:
            tool_name: Name of tool to execute
            tool_input: Tool input parameters
            priority: Task priority

        Returns:
            TaskResult
        """
        task = Task(
            type=TaskType.TOOL_CALL,
            priority=priority,
            payload={
                'tool_name': tool_name,
                'tool_input': tool_input,
            },
            metadata={'tool': tool_name},
        )

        result = await self.submit_task(task, wait=True)
        return result

    async def execute_llm_request(
        self,
        prompt: str,
        model: Optional[str] = None,
        system: Optional[str] = None,
        temperature: float = 0.7,
        prefer_ollama: bool = True,
        priority: TaskPriority = TaskPriority.NORMAL,
    ) -> TaskResult:
        """
        Execute an LLM request through the orchestrator

        Args:
            prompt: User prompt
            model: Optional model name
            system: Optional system message
            temperature: Temperature
            prefer_ollama: Prefer local Ollama
            priority: Task priority

        Returns:
            TaskResult
        """
        task = Task(
            type=TaskType.OLLAMA_REQUEST if prefer_ollama else TaskType.LLM_REQUEST,
            priority=priority,
            payload={
                'prompt': prompt,
                'model': model,
                'system': system,
                'temperature': temperature,
            },
        )

        result = await self.submit_task(task, wait=True)
        return result

    def _handle_task_completion(self, task: Task, result: TaskResult):
        """Handle task completion"""
        # Update metrics
        if result.success:
            self.metrics['tasks_completed'] += 1
        else:
            self.metrics['tasks_failed'] += 1

        self.metrics['total_execution_time_ms'] += result.execution_time_ms

        # Remove from active tasks
        if task.id in self.active_tasks:
            del self.active_tasks[task.id]

        # Call hooks
        if result.success and self.on_task_complete:
            try:
                self.on_task_complete(task, result)
            except Exception as e:
                logger.error(f"Error in task completion hook: {e}")

        if not result.success and self.on_task_failed:
            try:
                self.on_task_failed(task, result.error)
            except Exception as e:
                logger.error(f"Error in task failure hook: {e}")

    async def _run_scheduler(self):
        """Background scheduler loop"""
        logger.info("Scheduler started")

        while self.is_running:
            try:
                # Get next batch of tasks
                batch = await self.scheduler.get_next_batch(
                    self.config.max_concurrent_tasks
                )

                if batch:
                    # Execute batch
                    results = await self.router.execute_parallel(
                        batch,
                        max_concurrent=self.config.max_concurrent_tasks
                    )

                    # Handle completions
                    for task, result in zip(batch, results):
                        self._handle_task_completion(task, result)

                await asyncio.sleep(1.0)  # Check every second

            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                await asyncio.sleep(5.0)

        logger.info("Scheduler stopped")

    async def _run_health_checks(self):
        """Background health check loop"""
        logger.info("Health check started")

        while self.is_running:
            try:
                # Run health checks on all workers
                await self.worker_registry.health_check_all()

                # Auto-scale if enabled
                if self.config.enable_auto_scaling:
                    await self._auto_scale()

                await asyncio.sleep(self.config.health_check_interval)

            except Exception as e:
                logger.error(f"Health check error: {e}")
                await asyncio.sleep(30.0)

        logger.info("Health check stopped")

    async def _auto_scale(self):
        """Auto-scale worker pools based on load"""
        # Simple auto-scaling logic
        queue_size = len(self.scheduler.task_queue)
        active_count = len(self.active_tasks)
        worker_count = len(self.worker_registry.get_available_workers())

        # If queue is building up, scale up Docker pool
        if queue_size > worker_count * 2 and self.docker_pool:
            current_size = len(self.docker_pool.workers)
            new_size = min(current_size + 1, 10)  # Max 10 workers
            if new_size > current_size:
                logger.info(f"Scaling Docker pool from {current_size} to {new_size}")
                await self.docker_pool.scale(new_size)

                # Register new workers
                for worker in self.docker_pool.workers[current_size:]:
                    await self.worker_registry.register(worker)

    def get_status(self) -> Dict[str, Any]:
        """Get orchestrator status"""
        uptime = None
        if self.metrics['started_at']:
            uptime = (datetime.utcnow() - self.metrics['started_at']).total_seconds()

        return {
            'is_running': self.is_running,
            'uptime_seconds': uptime,
            'metrics': {
                **self.metrics,
                'started_at': self.metrics['started_at'].isoformat() if self.metrics['started_at'] else None,
                'active_tasks': len(self.active_tasks),
                'queued_tasks': len(self.scheduler.task_queue),
                'avg_execution_time_ms': (
                    self.metrics['total_execution_time_ms'] / self.metrics['tasks_completed']
                    if self.metrics['tasks_completed'] > 0 else 0
                ),
            },
            'workers': self.worker_registry.get_statistics(),
            'resources': self.resource_manager.get_resource_stats(),
        }

    def get_task_history(
        self,
        limit: int = 100,
        status_filter: Optional[TaskStatus] = None,
    ) -> List[Dict[str, Any]]:
        """Get task history"""
        tasks = list(self.task_history.values())

        # Filter by status
        if status_filter:
            tasks = [t for t in tasks if t.status == status_filter]

        # Sort by submission time (newest first)
        tasks.sort(key=lambda t: t.submitted_at, reverse=True)

        # Limit results
        tasks = tasks[:limit]

        return [task.to_dict() for task in tasks]
