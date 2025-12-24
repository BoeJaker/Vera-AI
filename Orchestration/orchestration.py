"""
Vera Task Orchestration System (With Streaming Support)
========================================================
Distributed task execution substrate with priority queuing, worker pools,
streaming support, and integration with ProactiveFocusManager.

NEW: Tasks can now yield results (generators) for streaming!

Architecture:
- Task Registry: Decorator-based task registration with metadata
- Worker Pools: Specialized pools for LLM, Whisper, Tools, ML models
- Priority Queue: Task prioritization with CPU-aware throttling
- Streaming: Native support for generator tasks
- Pub/Sub: Redis-based event broadcasting and coordination
- Integration: Seamless ProactiveFocusManager integration
"""
"""
Vera Task Orchestration System (With Streaming Support & Enhanced Logging)
===========================================================================
Distributed task execution substrate with priority queuing, worker pools,
streaming support, and integration with ProactiveFocusManager.

NEW: Tasks can now yield results (generators) for streaming!

Architecture:
- Task Registry: Decorator-based task registration with metadata
- Worker Pools: Specialized pools for LLM, Whisper, Tools, ML models
- Priority Queue: Task prioritization with CPU-aware throttling
- Streaming: Native support for generator tasks
- Pub/Sub: Redis-based event broadcasting and coordination
- Integration: Seamless ProactiveFocusManager integration
"""

import asyncio
import threading
import time
import json
import uuid
import logging
import queue
from typing import Any, Callable, Dict, List, Optional, Tuple, Union, Iterator
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
from datetime import datetime
from functools import wraps
from collections import defaultdict
import psutil

# Optional Redis for pub/sub (graceful degradation if not available)
try:
    import redis
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    print("[Orchestrator] Redis not available - pub/sub features disabled")

def extract_chunk_text(chunk):
    """Extract text from chunk object"""
    if hasattr(chunk, 'text'):
        return chunk.text
    elif hasattr(chunk, 'content'):
        return chunk.content
    elif isinstance(chunk, str):
        return chunk
    else:
        return str(chunk)
    
    
# ============================================================================
# ENUMS & DATA CLASSES
# ============================================================================

class TaskType(Enum):
    """Types of tasks that can be executed"""
    LLM = "llm"              # Language model inference
    WHISPER = "whisper"      # Audio transcription
    TOOL = "tool"            # Tool execution
    ML_MODEL = "ml_model"    # Machine learning model
    BACKGROUND = "background" # Background cognitive task
    GENERAL = "general"      # General computation


class Priority(Enum):
    """Task priority levels"""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BACKGROUND = 4


class TaskStatus(Enum):
    """Task execution status"""
    PENDING = auto()
    QUEUED = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


@dataclass
class TaskMetadata:
    """Metadata for task execution and tracking"""
    task_id: str
    task_type: TaskType
    priority: Priority
    created_at: float
    estimated_duration: float = 1.0  # seconds
    max_retries: int = 3
    timeout: float = 300.0  # seconds
    requires_gpu: bool = False
    requires_cpu_cores: int = 1
    memory_mb: int = 512
    focus_context: Optional[str] = None  # Link to ProactiveFocus context
    labels: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskResult:
    """Result of task execution (with streaming support)"""
    task_id: str
    status: TaskStatus
    result: Any = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    worker_id: Optional[str] = None
    retry_count: int = 0
    
    # Streaming support
    is_streaming: bool = False
    stream_queue: Optional[queue.Queue] = None
    
    @property
    def duration(self) -> Optional[float]:
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None


@dataclass
class WorkerStats:
    """Statistics for a worker"""
    worker_id: str
    worker_type: TaskType
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_duration: float = 0.0
    current_task: Optional[str] = None
    cpu_usage: float = 0.0
    memory_mb: float = 0.0


# ============================================================================
# TASK REGISTRY
# ============================================================================

class TaskRegistry:
    """
    Central registry for all executable tasks.
    Uses decorators to register tasks with metadata.
    """
    
    def __init__(self):
        self._tasks: Dict[str, Callable] = {}
        self._metadata: Dict[str, TaskMetadata] = {}
        self.logger = logging.getLogger("TaskRegistry")
    
    def register(
        self,
        name: str,
        task_type: TaskType = TaskType.GENERAL,
        priority: Priority = Priority.NORMAL,
        estimated_duration: float = 1.0,
        requires_gpu: bool = False,
        requires_cpu_cores: int = 1,
        memory_mb: int = 512,
        proactive_focus: bool = False,  # Mark for ProactiveFocusManager
        labels: Optional[List[str]] = None,
        **kwargs
    ):
        """
        Decorator to register a task handler.
        Task can return a value OR yield chunks (generator).
        
        Usage:
            @registry.register("llm.generate", task_type=TaskType.LLM, priority=Priority.HIGH)
            def generate_text(prompt: str):
                for chunk in llm.stream(prompt):
                    yield chunk  # ← Streaming!
        """
        def decorator(func: Callable) -> Callable:
            self._tasks[name] = func
            
            # Create metadata template (task_id will be generated per execution)
            metadata = TaskMetadata(
                task_id="",  # Will be set during submission
                task_type=task_type,
                priority=priority,
                created_at=0.0,  # Will be set during submission
                estimated_duration=estimated_duration,
                requires_gpu=requires_gpu,
                requires_cpu_cores=requires_cpu_cores,
                memory_mb=memory_mb,
                labels=labels or [],
                metadata={"proactive_focus": proactive_focus, **kwargs}
            )
            
            self._metadata[name] = metadata
            self.logger.info(
                f"Registered: {name} [type={task_type.value}, priority={priority.value}, "
                f"duration={estimated_duration}s, gpu={requires_gpu}]"
            )
            
            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            
            return wrapper
        
        return decorator
    
    def get_task(self, name: str) -> Optional[Callable]:
        """Get task handler by name"""
        return self._tasks.get(name)
    
    def get_metadata(self, name: str) -> Optional[TaskMetadata]:
        """Get task metadata template by name"""
        return self._metadata.get(name)
    
    def list_tasks(self, task_type: Optional[TaskType] = None, 
                   proactive_focus: Optional[bool] = None) -> List[str]:
        """List registered tasks, optionally filtered"""
        tasks = []
        for name, metadata in self._metadata.items():
            if task_type and metadata.task_type != task_type:
                continue
            if proactive_focus is not None:
                if metadata.metadata.get("proactive_focus") != proactive_focus:
                    continue
            tasks.append(name)
        return tasks


# Global task registry
registry = TaskRegistry()


# ============================================================================
# WORKER POOL
# ============================================================================

class Worker(threading.Thread):
    """Individual worker thread for task execution"""
    
    def __init__(self, worker_id: str, worker_type: TaskType, 
                 task_queue: "TaskQueue", event_bus: "EventBus"):
        super().__init__(daemon=True)
        self.worker_id = worker_id
        self.worker_type = worker_type
        self.task_queue = task_queue
        self.event_bus = event_bus
        self.running = False
        self.current_task: Optional[str] = None
        self.stats = WorkerStats(worker_id=worker_id, worker_type=worker_type)
        self.logger = logging.getLogger(f"Worker-{worker_id}")
    
    def run(self):
        """Main worker loop"""
        self.running = True
        self.logger.info(f"Worker started (type={self.worker_type.value})")
        
        while self.running:
            try:
                # Get next task from queue
                task_id, task_name, args, kwargs, metadata = self.task_queue.get_next(
                    worker_type=self.worker_type,
                    timeout=1.0
                )
                
                if not task_id:
                    continue
                
                self.logger.debug(f"Acquired task: {task_name} ({task_id[:8]}...)")
                
                self.current_task = task_id
                self._execute_task(task_id, task_name, args, kwargs, metadata)
                self.current_task = None
                
            except Exception as e:
                self.logger.error(f"Worker error: {e}", exc_info=True)
                if self.current_task:
                    self.task_queue.mark_failed(self.current_task, str(e))
                    self.current_task = None
        
        self.logger.info(
            f"Worker stopped (completed={self.stats.tasks_completed}, "
            f"failed={self.stats.tasks_failed})"
        )
    
    def _execute_task(self, task_id: str, task_name: str, 
                     args: tuple, kwargs: dict, metadata: TaskMetadata):
        """Execute a single task (with streaming support)"""
        started_at = time.time()
        
        self.logger.info(
            f"Executing: {task_name} [{metadata.priority.name}] "
            f"(est: {metadata.estimated_duration:.1f}s, timeout: {metadata.timeout:.1f}s)"
        )
        
        # Get the result object from pending
        with self.task_queue._lock:
            if task_id not in self.task_queue._pending:
                return
            result = self.task_queue._pending[task_id]
            result.started_at = started_at
            result.status = TaskStatus.RUNNING
        
        # Broadcast task start
        self.event_bus.publish("task.started", {
            "task_id": task_id,
            "task_name": task_name,
            "worker_id": self.worker_id,
            "started_at": started_at
        })
        
        try:
            # Get task handler
            handler = registry.get_task(task_name)
            if not handler:
                raise ValueError(f"Task handler not found: {task_name}")
            
            self.logger.debug(f"Invoking handler for {task_name}")
            
            # Execute
            output = handler(*args, **kwargs)
            
            # Check if it's a generator (streaming)
            is_generator = hasattr(output, '__iter__') and hasattr(output, '__next__')
            
            if is_generator:
                # Set up streaming
                with self.task_queue._lock:
                    result.is_streaming = True
                    result.stream_queue = queue.Queue()
                
                self.logger.debug(f"Task streaming: {task_name}")
                
                # Consume generator and queue chunks
                chunk_count = 0
                try:
                    for chunk in output:
                        result.stream_queue.put(chunk)
                        chunk_count += 1
                    
                    # Signal end of stream
                    result.stream_queue.put(StopIteration)
                    
                    self.logger.debug(f"Stream complete: {chunk_count} chunks")
                    
                except Exception as e:
                    result.stream_queue.put(e)
                    raise
            
            else:
                # Regular result
                result.result = output
                self.logger.debug(f"Result captured: {type(output).__name__}")
            
            # Record success
            completed_at = time.time()
            duration = completed_at - started_at
            
            self.stats.tasks_completed += 1
            self.stats.total_duration += duration
            
            result.status = TaskStatus.COMPLETED
            result.completed_at = completed_at
            result.worker_id = self.worker_id
            
            self.task_queue.mark_completed(task_id, result)
            
            # Broadcast completion
            self.event_bus.publish("task.completed", {
                "task_id": task_id,
                "task_name": task_name,
                "worker_id": self.worker_id,
                "duration": duration,
                "is_streaming": is_generator
            })
            
            # Calculate duration variance
            duration_diff = duration - metadata.estimated_duration
            variance_pct = (duration_diff / metadata.estimated_duration) * 100 if metadata.estimated_duration > 0 else 0
            
            self.logger.info(
                f"✓ Completed: {task_name} in {duration:.2f}s [{metadata.priority.name}]"
            )
            
            if abs(variance_pct) > 20:
                self.logger.debug(
                    f"Duration variance: {duration:.2f}s vs {metadata.estimated_duration:.2f}s est "
                    f"({duration_diff:+.2f}s, {variance_pct:+.1f}%)"
                )
            
        except Exception as e:
            # Record failure
            completed_at = time.time()
            duration = completed_at - started_at
            
            self.stats.tasks_failed += 1
            
            result.status = TaskStatus.FAILED
            result.error = str(e)
            result.completed_at = completed_at
            result.worker_id = self.worker_id
            
            self.task_queue.mark_failed(task_id, str(e))
            
            # Broadcast failure
            self.event_bus.publish("task.failed", {
                "task_id": task_id,
                "task_name": task_name,
                "worker_id": self.worker_id,
                "error": str(e),
                "duration": duration
            })
            
            self.logger.error(f"✗ Failed: {task_name} after {duration:.2f}s - {e}")
    
    def stop(self):
        """Stop the worker"""
        self.logger.debug("Stopping worker")
        self.running = False


class WorkerPool:
    """
    Pool of workers for a specific task type.
    Manages worker lifecycle and load balancing.
    """
    
    def __init__(self, worker_type: TaskType, num_workers: int,
                 task_queue: "TaskQueue", event_bus: "EventBus"):
        self.worker_type = worker_type
        self.num_workers = num_workers
        self.task_queue = task_queue
        self.event_bus = event_bus
        self.workers: List[Worker] = []
        self.logger = logging.getLogger(f"WorkerPool-{worker_type.value}")
    
    def start(self):
        """Start all workers in the pool"""
        self.logger.info(f"Starting {self.num_workers} workers for {self.worker_type.value}")
        
        for i in range(self.num_workers):
            worker_id = f"{self.worker_type.value}-{i}"
            worker = Worker(worker_id, self.worker_type, self.task_queue, self.event_bus)
            worker.start()
            self.workers.append(worker)
            self.logger.debug(f"  Started worker: {worker_id}")
        
        self.logger.info(f"All {self.num_workers} workers started")
    
    def stop(self):
        """Stop all workers in the pool"""
        self.logger.info(f"Stopping {len(self.workers)} workers")
        
        for worker in self.workers:
            worker.stop()
        
        stopped_count = 0
        for worker in self.workers:
            worker.join(timeout=5.0)
            if not worker.is_alive():
                stopped_count += 1
        
        self.logger.info(f"Stopped {stopped_count}/{len(self.workers)} workers")
    
    def get_stats(self) -> List[WorkerStats]:
        """Get statistics for all workers"""
        return [worker.stats for worker in self.workers]
    
    def scale(self, num_workers: int):
        """Scale the pool to a different number of workers"""
        current = len(self.workers)
        
        if num_workers > current:
            # Scale up
            self.logger.info(f"Scaling up: {current} → {num_workers}")
            
            for i in range(current, num_workers):
                worker_id = f"{self.worker_type.value}-{i}"
                worker = Worker(worker_id, self.worker_type, self.task_queue, self.event_bus)
                worker.start()
                self.workers.append(worker)
                self.logger.debug(f"  Added worker: {worker_id}")
            
            self.logger.info(f"Scaled up to {num_workers} workers")
        
        elif num_workers < current:
            # Scale down
            self.logger.info(f"Scaling down: {current} → {num_workers}")
            
            workers_to_stop = self.workers[num_workers:]
            self.workers = self.workers[:num_workers]
            
            for worker in workers_to_stop:
                worker.stop()
                self.logger.debug(f"  Stopping worker: {worker.worker_id}")
            
            for worker in workers_to_stop:
                worker.join(timeout=5.0)
            
            self.logger.info(f"Scaled down to {num_workers} workers")


# ============================================================================
# TASK QUEUE
# ============================================================================

class TaskQueue:
    """
    Priority-based task queue with support for multiple task types and streaming.
    Tracks task state and provides retrieval by priority and type.
    """
    
    def __init__(self, cpu_threshold: float = 85.0):
        self._queues: Dict[TaskType, List[Tuple[Priority, float, str, str, tuple, dict, TaskMetadata]]] = defaultdict(list)
        self._pending: Dict[str, TaskResult] = {}
        self._completed: Dict[str, TaskResult] = {}
        self._lock = threading.Lock()
        self.cpu_threshold = cpu_threshold
        self.logger = logging.getLogger("TaskQueue")
        self._last_cpu_check = 0
        self._cached_cpu = 0
        self._cpu_check_interval = 1.0  # Check once per second
        
        self.logger.info(f"TaskQueue initialized (cpu_threshold={cpu_threshold}%)")
    
    def submit(self, task_name: str, *args, **kwargs) -> str:
        """Submit a task for execution"""
        # Get task metadata template
        metadata_template = registry.get_metadata(task_name)
        if not metadata_template:
            raise ValueError(f"Task not registered: {task_name}")
        
        # Generate task ID and create metadata
        task_id = str(uuid.uuid4())
        created_at = time.time()
        
        # Clone metadata and set task-specific fields
        metadata = TaskMetadata(
            task_id=task_id,
            task_type=metadata_template.task_type,
            priority=metadata_template.priority,
            created_at=created_at,
            estimated_duration=metadata_template.estimated_duration,
            max_retries=metadata_template.max_retries,
            timeout=metadata_template.timeout,
            requires_gpu=metadata_template.requires_gpu,
            requires_cpu_cores=metadata_template.requires_cpu_cores,
            memory_mb=metadata_template.memory_mb,
            focus_context=kwargs.pop('focus_context', None),
            labels=metadata_template.labels.copy(),
            metadata=metadata_template.metadata.copy()
        )
        
        # Add to queue
        with self._lock:
            queue = self._queues[metadata.task_type]
            # Store: (priority, created_at, task_id, task_name, args, kwargs, metadata)
            queue.append((
                metadata.priority,
                created_at,
                task_id,
                task_name,
                args,
                kwargs,
                metadata
            ))
            # Sort by priority (lower number = higher priority), then by creation time
            queue.sort(key=lambda x: (x[0].value, x[1]))
            
            queue_position = next((i for i, item in enumerate(queue) if item[2] == task_id), -1) + 1
            
            # Initialize result tracking
            self._pending[task_id] = TaskResult(
                task_id=task_id,
                status=TaskStatus.QUEUED
            )
            
            self.logger.info(
                f"Task queued: {task_name} ({task_id[:8]}...) [{metadata.priority.name}] "
                f"pos={queue_position}/{len(queue)}"
            )
            
            self.logger.info(f"Queue state: {metadata.task_type.value} has {len(queue)} tasks")
        
        return task_id
    
    def get_next(self, worker_type: TaskType, timeout: float = 1.0) -> Tuple[Optional[str], ...]:
        """Get next task for a worker of the given type"""
        # Check CPU usage (cached)
        now = time.time()
        if now - self._last_cpu_check > self._cpu_check_interval:
            self._cached_cpu = psutil.cpu_percent(interval=0.1)
            self._last_cpu_check = now
        
        if self._cached_cpu >= self.cpu_threshold:
            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug(f"CPU throttle: {self._cached_cpu:.1f}% >= {self.cpu_threshold}%")
            return None, None, None, None, None
        
        with self._lock:
            queue = self._queues[worker_type]
            
            if not queue:
                return None, None, None, None, None
            
            # Get highest priority task
            priority, created_at, task_id, task_name, args, kwargs, metadata = queue.pop(0)
            
            wait_time = now - created_at
            
            self.logger.debug(
                f"Dequeued: {task_name} ({task_id[:8]}...) wait={wait_time:.3f}s "
                f"queue_remaining={len(queue)}"
            )
            
            # Update status
            if task_id in self._pending:
                self._pending[task_id].status = TaskStatus.RUNNING
            
            return task_id, task_name, args, kwargs, metadata
    
    def mark_completed(self, task_id: str, result: TaskResult):
        """Mark a task as completed"""
        with self._lock:
            if task_id in self._pending:
                self._completed[task_id] = result
                del self._pending[task_id]
                
                self.logger.info(
                    f"Marked completed: {task_id[:8]}... "
                    f"(pending={len(self._pending)}, completed={len(self._completed)})"
                )
    
    def mark_failed(self, task_id: str, error: str):
        """Mark a task as failed"""
        with self._lock:
            if task_id in self._pending:
                result = self._pending[task_id]
                result.status = TaskStatus.FAILED
                result.error = error
                result.completed_at = time.time()
                self._completed[task_id] = result
                del self._pending[task_id]
                
                self.logger.info(
                    f"Marked failed: {task_id[:8]}... "
                    f"(pending={len(self._pending)}, completed={len(self._completed)})"
                )
    
    def get_result(self, task_id: str, timeout: Optional[float] = None) -> Optional[TaskResult]:
        """Get task result (blocking if timeout specified)"""
        start = time.time()
        
        while True:
            with self._lock:
                if task_id in self._completed:
                    return self._completed[task_id]
                
                # Check if it's streaming
                if task_id in self._pending:
                    result = self._pending[task_id]
                    if result.is_streaming:
                        return result
            
            if timeout is None:
                break
            
            if time.time() - start >= timeout:
                break
            
            time.sleep(0.1)
        
        return None
    
    def stream_result(self, task_id: str, timeout: Optional[float] = None) -> Iterator[Any]:
        """
        Stream results from a task as they become available.
        Works for both streaming (generator) and non-streaming tasks.
        
        Usage:
            task_id = task_queue.submit("llm.generate", prompt="...")
            for chunk in task_queue.stream_result(task_id):
                print(chunk, end='', flush=True)
        """
        # Wait for task to start/be ready
        start_time = time.time()
        result = None
        
        self.logger.debug(f"Waiting for task to start: {task_id[:8]}...")
        
        while True:
            result = self.get_result(task_id, timeout=0.1)
            if result:
                break
            
            if timeout and (time.time() - start_time) > timeout:
                raise TimeoutError(f"Task {task_id[:8]}... timed out waiting to start")
            
            time.sleep(0.1)
        
        # Check if task failed
        if result.status == TaskStatus.FAILED:
            self.logger.error(f"Task failed: {result.error}")
            raise Exception(f"Task failed: {result.error}")
        
        # If streaming task
        if result.is_streaming and result.stream_queue:
            self.logger.debug(f"Streaming results for task {task_id[:8]}...")
            
            chunk_count = 0
            while True:
                try:
                    chunk = result.stream_queue.get(timeout=timeout or 300)
                    
                    # Check for end of stream
                    if chunk is StopIteration:
                        self.logger.debug(f"Stream ended: {chunk_count} chunks")
                        break
                    
                    # Check for exception
                    if isinstance(chunk, Exception):
                        raise chunk
                    
                    chunk_count += 1
                    yield chunk
                
                except queue.Empty:
                    # Check if task is completed
                    with self._lock:
                        if task_id in self._completed:
                            self.logger.debug(f"Task completed externally: {chunk_count} chunks")
                            break
                    continue
        
        else:
            # Non-streaming task, yield complete result once
            if result.result is not None:
                self.logger.debug(f"Yielding non-streaming result")
                yield result.result
    
    def get_queue_sizes(self) -> Dict[str, int]:
        """Get size of each queue"""
        with self._lock:
            sizes = {
                task_type.value: len(queue)
                for task_type, queue in self._queues.items()
            }
            
            if sizes:
                self.logger.info(f"Queue sizes: {sizes}")
            
            return sizes
    
    def clear(self):
        """Clear all queues"""
        with self._lock:
            total_pending = len(self._pending)
            total_completed = len(self._completed)
            
            self._queues.clear()
            self._pending.clear()
            self._completed.clear()
            
            self.logger.info(f"Cleared queues (pending={total_pending}, completed={total_completed})")


# ============================================================================
# EVENT BUS (Pub/Sub)
# ============================================================================

class EventBus:
    """
    Event bus for pub/sub communication between components.
    Uses Redis if available, falls back to local threading.Event system.
    """
    
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url
        self.redis_client: Optional[redis.Redis] = None
        self.local_subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self.logger = logging.getLogger("EventBus")
        
        if REDIS_AVAILABLE and redis_url:
            try:
                self.redis_client = redis.from_url(redis_url, decode_responses=True)
                self.redis_client.ping()
                self.logger.info(f"Connected to Redis: {redis_url}")
            except Exception as e:
                self.logger.warning(f"Failed to connect to Redis: {e}. Using local pub/sub.")
                self.redis_client = None
        else:
            self.logger.info("Using local pub/sub (Redis not available)")
    
    def publish(self, channel: str, message: Dict[str, Any]):
        """Publish a message to a channel"""
        if self.redis_client:
            try:
                self.redis_client.publish(channel, json.dumps(message))
                self.logger.info(f"Published to Redis channel: {channel}")
            except Exception as e:
                self.logger.error(f"Redis publish error: {e}")
        
        # Also trigger local subscribers
        subscriber_count = len(self.local_subscribers.get(channel, []))
        if subscriber_count > 0:
            self.logger.info(f"Notifying {subscriber_count} local subscribers on {channel}")
        
        for callback in self.local_subscribers.get(channel, []):
            try:
                callback(message)
            except Exception as e:
                self.logger.error(f"Local subscriber error on {channel}: {e}")
    
    def subscribe(self, channel: str, callback: Callable[[Dict[str, Any]], None]):
        """Subscribe to a channel with a callback"""
        self.local_subscribers[channel].append(callback)
        subscriber_count = len(self.local_subscribers[channel])
        self.logger.debug(f"Subscribed to channel: {channel} ({subscriber_count} subscribers)")
    
    def unsubscribe(self, channel: str, callback: Callable):
        """Unsubscribe from a channel"""
        if channel in self.local_subscribers:
            try:
                self.local_subscribers[channel].remove(callback)
                subscriber_count = len(self.local_subscribers[channel])
                self.logger.debug(f"Unsubscribed from channel: {channel} ({subscriber_count} remaining)")
            except ValueError:
                pass


# ============================================================================
# ORCHESTRATOR
# ============================================================================

class Orchestrator:
    """
    Main orchestration system that ties everything together.
    Manages worker pools, task queue, event bus, and streaming.
    """
    
    def __init__(
        self,
        config: Optional[Dict[TaskType, int]] = None,
        redis_url: Optional[str] = None,
        cpu_threshold: float = 85.0
    ):
        """
        Initialize orchestrator.
        
        Args:
            config: Dict mapping TaskType to number of workers
            redis_url: Redis connection URL for pub/sub
            cpu_threshold: CPU usage threshold for throttling
        """
        self.config = config or {
            TaskType.LLM: 2,
            TaskType.WHISPER: 1,
            TaskType.TOOL: 4,
            TaskType.ML_MODEL: 1,
            TaskType.BACKGROUND: 2,
            TaskType.GENERAL: 2
        }
        
        self.event_bus = EventBus(redis_url=redis_url)
        self.task_queue = TaskQueue(cpu_threshold=cpu_threshold)
        self.worker_pools: Dict[TaskType, WorkerPool] = {}
        self.running = False
        self.logger = logging.getLogger("Orchestrator")
        
        # For compatibility
        self.registry = registry
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='[%(asctime)s] %(name)s - %(levelname)s - %(message)s'
        )
        
        # Log initialization
        total_workers = sum(self.config.values())
        self.logger.info(f"Orchestrator initialized ({total_workers} total workers)")
        for task_type, count in self.config.items():
            if count > 0:
                self.logger.debug(f"  {task_type.value}: {count} workers")
    
    def start(self):
        """Start the orchestrator and all worker pools"""
        if self.running:
            self.logger.warning("Orchestrator already running")
            return
        
        self.logger.info("Starting orchestrator")
        self.running = True
        
        # Start worker pools
        started_pools = 0
        for task_type, num_workers in self.config.items():
            if num_workers > 0:
                pool = WorkerPool(task_type, num_workers, self.task_queue, self.event_bus)
                pool.start()
                self.worker_pools[task_type] = pool
                started_pools += 1
        
        # Subscribe to events for monitoring
        self.event_bus.subscribe("task.completed", self._on_task_completed)
        self.event_bus.subscribe("task.failed", self._on_task_failed)
        
        self.logger.info(f"Orchestrator started ({started_pools} pools active)")
    
    def stop(self):
        """Stop the orchestrator and all worker pools"""
        if not self.running:
            return
        
        self.logger.info("Stopping orchestrator")
        self.running = False
        
        # Stop all worker pools
        for task_type, pool in self.worker_pools.items():
            self.logger.debug(f"Stopping {task_type.value} pool")
            pool.stop()
        
        self.logger.info("Orchestrator stopped")
    
    def submit_task(self, task_name: str, *args, **kwargs) -> str:
        """Submit a task for execution"""
        return self.task_queue.submit(task_name, *args, **kwargs)
    
    def wait_for_result(self, task_id: str, timeout: Optional[float] = None) -> Optional[TaskResult]:
        """Wait for a task to complete and return its result"""
        return self.task_queue.get_result(task_id, timeout=timeout)
    
    def stream_result(self, task_id: str, timeout: Optional[float] = None) -> Iterator[Any]:
        """
        Stream results from a task.
        Works for both streaming (generator) and non-streaming tasks.
        
        Usage:
            task_id = orchestrator.submit_task("llm.generate", prompt="...")
            for chunk in orchestrator.stream_result(task_id):
                print(chunk, end='', flush=True)
        """
        yield from self.task_queue.stream_result(task_id, timeout=timeout)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get orchestrator statistics"""
        stats = {
            "running": self.running,
            "queue_sizes": self.task_queue.get_queue_sizes(),
            "worker_pools": {}
        }
        
        for task_type, pool in self.worker_pools.items():
            stats["worker_pools"][task_type.value] = {
                "num_workers": pool.num_workers,
                "workers": [asdict(s) for s in pool.get_stats()]
            }
        
        self.logger.info(f"Generated stats: {len(stats['worker_pools'])} pools")
        
        return stats
    
    def scale_pool(self, task_type: TaskType, num_workers: int):
        """Scale a worker pool"""
        if task_type in self.worker_pools:
            self.logger.info(f"Scaling {task_type.value} pool to {num_workers} workers")
            self.worker_pools[task_type].scale(num_workers)
            self.config[task_type] = num_workers
        else:
            self.logger.warning(f"Cannot scale - pool not found: {task_type.value}")
    
    def _on_task_completed(self, message: Dict[str, Any]):
        """Handle task completion event"""
        self.logger.info(
            f"Task completed: {message['task_name']} ({message['task_id'][:8]}...) "
            f"in {message['duration']:.2f}s by {message['worker_id']}"
        )
    
    def _on_task_failed(self, message: Dict[str, Any]):
        """Handle task failure event"""
        self.logger.error(
            f"Task failed: {message['task_name']} ({message['task_id'][:8]}...) - {message['error']}"
        )


# ============================================================================
# PROACTIVE FOCUS INTEGRATION
# ============================================================================

class ProactiveFocusOrchestrator:
    """
    Integration layer between ProactiveFocusManager and Orchestrator.
    Routes proactive focus tasks through the orchestration system.
    """
    
    def __init__(self, orchestrator: Orchestrator, focus_manager):
        self.orchestrator = orchestrator
        self.focus_manager = focus_manager
        self.logger = logging.getLogger("ProactiveFocusOrchestrator")
        
        # Subscribe to focus events
        orchestrator.event_bus.subscribe("focus.changed", self._on_focus_changed)
        orchestrator.event_bus.subscribe("task.completed", self._on_task_completed)
        
        self.logger.info("ProactiveFocusOrchestrator initialized")
    
    def submit_proactive_task(self, task_name: str, *args, **kwargs) -> str:
        """Submit a task marked for proactive focus"""
        # Add focus context
        focus = self.focus_manager.focus
        kwargs['focus_context'] = focus
        
        # Submit through orchestrator
        task_id = self.orchestrator.submit_task(task_name, *args, **kwargs)
        
        self.logger.info(f"Submitted proactive task: {task_name} (focus={focus}, task_id={task_id[:8]}...)")
        
        return task_id
    
    def _on_focus_changed(self, message: Dict[str, Any]):
        """Handle focus change event"""
        new_focus = message.get("focus")
        self.logger.info(f"Focus changed to: {new_focus}")
    
    def _on_task_completed(self, message: Dict[str, Any]):
        """Handle task completion for proactive tasks"""
        # Could add focus-specific handling here
        pass


# ============================================================================
# CONVENIENCE DECORATORS
# ============================================================================

def task(
    name: str,
    task_type: TaskType = TaskType.GENERAL,
    priority: Priority = Priority.NORMAL,
    **kwargs
):
    """
    Convenience decorator for registering tasks.
    Task can return a value OR yield chunks (generator).
    
    Usage:
        @task("llm.generate", task_type=TaskType.LLM, priority=Priority.HIGH)
        def generate_text(prompt: str):
            for chunk in llm.stream(prompt):
                yield chunk  # ← Streaming!
    """
    return registry.register(name, task_type=task_type, priority=priority, **kwargs)


def proactive_task(name: str, **kwargs):
    """
    Decorator for tasks that should be part of the proactive focus system.
    
    Usage:
        @proactive_task("analyze_context")
        def analyze_focus_context(context: str):
            return analysis
    """
    kwargs['proactive_focus'] = True
    kwargs.setdefault('task_type', TaskType.BACKGROUND)
    kwargs.setdefault('priority', Priority.LOW)
    return registry.register(name, **kwargs)


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # Example task registrations (with streaming!)
    
    @task("llm.generate", task_type=TaskType.LLM, priority=Priority.HIGH, estimated_duration=5.0)
    def generate_text(prompt: str, model: str = "default"):
        """Generate text using LLM (streaming)"""
        import time
        for i in range(5):
            time.sleep(0.5)
            yield f"Chunk {i+1} for: {prompt}\n"
    
    @task("compute.sum", task_type=TaskType.GENERAL, priority=Priority.NORMAL)
    def compute_sum(a: int, b: int):
        """Compute sum (non-streaming)"""
        return a + b
    
    @proactive_task("focus.analyze")
    def analyze_focus(focus: str):
        """Analyze current focus"""
        import time
        time.sleep(1)
        return f"Analysis of focus: {focus}"
    
    # Initialize orchestrator
    orchestrator = Orchestrator(
        config={
            TaskType.LLM: 2,
            TaskType.GENERAL: 2,
            TaskType.BACKGROUND: 2
        }
    )
    
    # Start orchestrator
    orchestrator.start()
    
    try:
        # Test streaming task
        print("Testing streaming task:")
        task1 = orchestrator.submit_task("llm.generate", prompt="Hello world")
        for chunk in orchestrator.stream_result(task1, timeout=10.0):
            print(chunk, end='', flush=True)
        print("\n")
        
        # Test non-streaming task
        print("Testing non-streaming task:")
        task2 = orchestrator.submit_task("compute.sum", a=10, b=5)
        for result in orchestrator.stream_result(task2, timeout=5.0):
            print(f"Result: {result}")
        print()
        
        # Get stats
        stats = orchestrator.get_stats()
        print(f"Orchestrator stats:\n{json.dumps(stats, indent=2)}")
        
        # Keep running
        time.sleep(2)
        
    finally:
        # Stop orchestrator
        orchestrator.stop()