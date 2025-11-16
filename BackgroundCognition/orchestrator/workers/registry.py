"""
Worker registry for managing all available workers
"""

from typing import Dict, List, Optional, Set
import asyncio
from datetime import datetime

from .base import BaseWorker, WorkerStatus, WorkerCapability
from ..tasks import Task


class WorkerRegistry:
    """
    Central registry for all workers in the orchestration system
    """

    def __init__(self):
        self._workers: Dict[str, BaseWorker] = {}
        self._workers_by_capability: Dict[WorkerCapability, Set[str]] = {}
        self._lock = asyncio.Lock()

    async def register(self, worker: BaseWorker) -> bool:
        """
        Register a new worker

        Args:
            worker: Worker to register

        Returns:
            bool: True if registered successfully
        """
        async with self._lock:
            if worker.id in self._workers:
                return False

            self._workers[worker.id] = worker

            # Index by capabilities
            for capability in worker.capabilities:
                if capability not in self._workers_by_capability:
                    self._workers_by_capability[capability] = set()
                self._workers_by_capability[capability].add(worker.id)

            return True

    async def unregister(self, worker_id: str) -> bool:
        """
        Unregister a worker

        Args:
            worker_id: ID of worker to unregister

        Returns:
            bool: True if unregistered successfully
        """
        async with self._lock:
            if worker_id not in self._workers:
                return False

            worker = self._workers[worker_id]

            # Remove from capability index
            for capability in worker.capabilities:
                if capability in self._workers_by_capability:
                    self._workers_by_capability[capability].discard(worker_id)

            # Stop worker
            await worker.stop()

            del self._workers[worker_id]
            return True

    def get_worker(self, worker_id: str) -> Optional[BaseWorker]:
        """Get worker by ID"""
        return self._workers.get(worker_id)

    def get_all_workers(self) -> List[BaseWorker]:
        """Get all registered workers"""
        return list(self._workers.values())

    def get_workers_by_capability(
        self,
        capability: WorkerCapability
    ) -> List[BaseWorker]:
        """
        Get all workers with a specific capability

        Args:
            capability: Capability to filter by

        Returns:
            List of workers with that capability
        """
        worker_ids = self._workers_by_capability.get(capability, set())
        return [self._workers[wid] for wid in worker_ids if wid in self._workers]

    def get_available_workers(
        self,
        task: Optional[Task] = None,
        required_capabilities: Optional[List[WorkerCapability]] = None,
    ) -> List[BaseWorker]:
        """
        Get available workers, optionally filtered by task requirements

        Args:
            task: Optional task to check compatibility with
            required_capabilities: Optional list of required capabilities

        Returns:
            List of available workers
        """
        candidates = []

        # Get candidates based on capabilities
        if required_capabilities:
            # Find workers with ALL required capabilities
            candidate_ids = None
            for cap in required_capabilities:
                worker_ids = self._workers_by_capability.get(cap, set())
                if candidate_ids is None:
                    candidate_ids = worker_ids.copy()
                else:
                    candidate_ids &= worker_ids

            candidates = [
                self._workers[wid]
                for wid in (candidate_ids or set())
                if wid in self._workers
            ]
        else:
            candidates = list(self._workers.values())

        # Filter by task compatibility if provided
        if task:
            candidates = [w for w in candidates if w.can_handle(task)]
        else:
            # Filter by general availability
            candidates = [
                w for w in candidates
                if w.status in [WorkerStatus.IDLE, WorkerStatus.BUSY]
                and len(w.current_tasks) < w.config.max_concurrent_tasks
            ]

        # Sort by load (least loaded first)
        candidates.sort(key=lambda w: w.get_load())

        return candidates

    def get_best_worker(
        self,
        task: Task,
    ) -> Optional[BaseWorker]:
        """
        Get the best worker for a task based on load and capabilities

        Args:
            task: Task to find worker for

        Returns:
            Best worker or None if no suitable worker available
        """
        # Get required capabilities from task
        required_caps = []
        if task.requirements.worker_capabilities:
            # Convert string capabilities to enum
            for cap_str in task.requirements.worker_capabilities:
                try:
                    cap = WorkerCapability(cap_str)
                    required_caps.append(cap)
                except ValueError:
                    pass

        available = self.get_available_workers(
            task=task,
            required_capabilities=required_caps if required_caps else None,
        )

        return available[0] if available else None

    async def health_check_all(self) -> Dict[str, bool]:
        """
        Run health checks on all workers

        Returns:
            Dict mapping worker_id to health status
        """
        results = {}
        tasks = []

        for worker_id, worker in self._workers.items():
            tasks.append((worker_id, worker.health_check()))

        for worker_id, health_task in tasks:
            try:
                is_healthy = await health_task
                results[worker_id] = is_healthy

                # Update worker status based on health
                worker = self._workers.get(worker_id)
                if worker and not is_healthy and worker.status != WorkerStatus.OFFLINE:
                    worker.status = WorkerStatus.ERROR
            except Exception:
                results[worker_id] = False

        return results

    def get_statistics(self) -> Dict:
        """Get registry statistics"""
        total = len(self._workers)
        by_status = {}
        by_capability = {}

        for worker in self._workers.values():
            # Count by status
            status_name = worker.status.value
            by_status[status_name] = by_status.get(status_name, 0) + 1

            # Count by capability
            for cap in worker.capabilities:
                cap_name = cap.value
                by_capability[cap_name] = by_capability.get(cap_name, 0) + 1

        total_tasks_running = sum(
            len(w.current_tasks) for w in self._workers.values()
        )
        total_tasks_completed = sum(
            w.metrics.tasks_completed for w in self._workers.values()
        )
        total_tasks_failed = sum(
            w.metrics.tasks_failed for w in self._workers.values()
        )

        return {
            'total_workers': total,
            'workers_by_status': by_status,
            'workers_by_capability': by_capability,
            'total_tasks_running': total_tasks_running,
            'total_tasks_completed': total_tasks_completed,
            'total_tasks_failed': total_tasks_failed,
            'timestamp': datetime.utcnow().isoformat(),
        }

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return {
            'workers': [w.to_dict() for w in self._workers.values()],
            'statistics': self.get_statistics(),
        }
