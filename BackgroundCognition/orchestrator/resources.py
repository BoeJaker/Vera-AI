"""
Resource management for the unified orchestrator
"""

import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict

from .workers import LLMAPIWorker, OllamaWorker, WorkerCapability


@dataclass
class APIQuota:
    """Quota configuration for an API"""
    requests_per_minute: int = 60
    requests_per_hour: int = 3600
    requests_per_day: int = 86400
    tokens_per_minute: Optional[int] = None
    tokens_per_day: Optional[int] = None
    cost_limit_per_day: Optional[float] = None


@dataclass
class APIUsage:
    """Current usage tracking for an API"""
    requests_this_minute: int = 0
    requests_this_hour: int = 0
    requests_this_day: int = 0
    tokens_this_minute: int = 0
    tokens_this_day: int = 0
    cost_this_day: float = 0.0
    last_request: Optional[datetime] = None
    last_reset_minute: datetime = field(default_factory=datetime.utcnow)
    last_reset_hour: datetime = field(default_factory=datetime.utcnow)
    last_reset_day: datetime = field(default_factory=datetime.utcnow)


class LLMAPIPool:
    """
    Pool of LLM API workers with intelligent routing and quota management
    """

    def __init__(self):
        self.workers: Dict[str, LLMAPIWorker] = {}
        self.quotas: Dict[str, APIQuota] = {}
        self.usage: Dict[str, APIUsage] = defaultdict(APIUsage)
        self._lock = asyncio.Lock()

    async def add_worker(
        self,
        worker: LLMAPIWorker,
        quota: Optional[APIQuota] = None
    ):
        """Add an LLM API worker to the pool"""
        async with self._lock:
            self.workers[worker.id] = worker
            if quota:
                self.quotas[worker.id] = quota

    async def remove_worker(self, worker_id: str):
        """Remove an LLM API worker from the pool"""
        async with self._lock:
            if worker_id in self.workers:
                await self.workers[worker_id].stop()
                del self.workers[worker_id]
                if worker_id in self.quotas:
                    del self.quotas[worker_id]
                if worker_id in self.usage:
                    del self.usage[worker_id]

    def _reset_usage_if_needed(self, worker_id: str):
        """Reset usage counters if time windows have passed"""
        usage = self.usage[worker_id]
        now = datetime.utcnow()

        # Reset minute counter
        if (now - usage.last_reset_minute).total_seconds() >= 60:
            usage.requests_this_minute = 0
            usage.tokens_this_minute = 0
            usage.last_reset_minute = now

        # Reset hour counter
        if (now - usage.last_reset_hour).total_seconds() >= 3600:
            usage.requests_this_hour = 0
            usage.last_reset_hour = now

        # Reset day counter
        if (now - usage.last_reset_day).total_seconds() >= 86400:
            usage.requests_this_day = 0
            usage.tokens_this_day = 0
            usage.cost_this_day = 0.0
            usage.last_reset_day = now

    def check_quota(self, worker_id: str) -> tuple[bool, Optional[str]]:
        """
        Check if worker has available quota

        Returns:
            (has_quota, reason_if_no_quota)
        """
        if worker_id not in self.quotas:
            return True, None  # No quota configured

        quota = self.quotas[worker_id]
        usage = self.usage[worker_id]

        self._reset_usage_if_needed(worker_id)

        # Check request limits
        if usage.requests_this_minute >= quota.requests_per_minute:
            return False, "Minute request limit exceeded"

        if usage.requests_this_hour >= quota.requests_per_hour:
            return False, "Hour request limit exceeded"

        if usage.requests_this_day >= quota.requests_per_day:
            return False, "Day request limit exceeded"

        # Check token limits
        if quota.tokens_per_minute and usage.tokens_this_minute >= quota.tokens_per_minute:
            return False, "Minute token limit exceeded"

        if quota.tokens_per_day and usage.tokens_this_day >= quota.tokens_per_day:
            return False, "Day token limit exceeded"

        # Check cost limits
        if quota.cost_limit_per_day and usage.cost_this_day >= quota.cost_limit_per_day:
            return False, "Day cost limit exceeded"

        return True, None

    def record_usage(
        self,
        worker_id: str,
        tokens_used: int = 0,
        cost: float = 0.0
    ):
        """Record API usage"""
        usage = self.usage[worker_id]

        usage.requests_this_minute += 1
        usage.requests_this_hour += 1
        usage.requests_this_day += 1
        usage.tokens_this_minute += tokens_used
        usage.tokens_this_day += tokens_used
        usage.cost_this_day += cost
        usage.last_request = datetime.utcnow()

    async def get_available_worker(
        self,
        api_type: Optional[str] = None,
        prefer_low_cost: bool = True
    ) -> Optional[LLMAPIWorker]:
        """
        Get an available LLM API worker

        Args:
            api_type: Specific API type to filter by
            prefer_low_cost: Prefer lower cost options

        Returns:
            Available worker or None
        """
        async with self._lock:
            candidates = []

            for worker_id, worker in self.workers.items():
                # Filter by API type if specified
                if api_type and worker.api_type != api_type:
                    continue

                # Check quota
                has_quota, _ = self.check_quota(worker_id)
                if not has_quota:
                    continue

                # Check worker availability
                if worker.can_handle(None):  # Generic availability check
                    candidates.append(worker)

            if not candidates:
                return None

            # Sort by preference
            if prefer_low_cost:
                candidates.sort(key=lambda w: w.cost_per_1k_tokens)
            else:
                candidates.sort(key=lambda w: w.get_load())

            return candidates[0]

    def get_usage_summary(self) -> Dict[str, Any]:
        """Get summary of API usage across all workers"""
        summary = {
            'total_workers': len(self.workers),
            'workers': {},
            'totals': {
                'requests_today': 0,
                'tokens_today': 0,
                'cost_today': 0.0,
            }
        }

        for worker_id, worker in self.workers.items():
            usage = self.usage[worker_id]
            self._reset_usage_if_needed(worker_id)

            worker_summary = {
                'api_type': worker.api_type,
                'status': worker.status.value,
                'requests_today': usage.requests_this_day,
                'tokens_today': usage.tokens_this_day,
                'cost_today': usage.cost_this_day,
                'last_request': usage.last_request.isoformat() if usage.last_request else None,
            }

            if worker_id in self.quotas:
                quota = self.quotas[worker_id]
                worker_summary['quota'] = {
                    'requests_per_day': quota.requests_per_day,
                    'tokens_per_day': quota.tokens_per_day,
                    'cost_limit_per_day': quota.cost_limit_per_day,
                }
                worker_summary['quota_remaining'] = {
                    'requests': quota.requests_per_day - usage.requests_this_day,
                    'tokens': (quota.tokens_per_day - usage.tokens_this_day)
                              if quota.tokens_per_day else None,
                    'cost': (quota.cost_limit_per_day - usage.cost_this_day)
                           if quota.cost_limit_per_day else None,
                }

            summary['workers'][worker_id] = worker_summary

            # Add to totals
            summary['totals']['requests_today'] += usage.requests_this_day
            summary['totals']['tokens_today'] += usage.tokens_this_day
            summary['totals']['cost_today'] += usage.cost_this_day

        return summary


class ResourceManager:
    """
    Central resource manager for all compute resources
    """

    def __init__(self):
        self.llm_api_pool = LLMAPIPool()
        self.ollama_workers: Dict[str, OllamaWorker] = {}

        # Track resource allocations
        self.allocated_resources: Dict[str, Dict[str, Any]] = {}

        self._lock = asyncio.Lock()

    async def register_llm_api(
        self,
        worker: LLMAPIWorker,
        quota: Optional[APIQuota] = None
    ):
        """Register an LLM API worker"""
        await self.llm_api_pool.add_worker(worker, quota)

    async def register_ollama(self, worker: OllamaWorker):
        """Register an Ollama worker"""
        async with self._lock:
            self.ollama_workers[worker.id] = worker

    async def get_llm_worker(
        self,
        prefer_ollama: bool = True,
        api_type: Optional[str] = None,
        require_capability: Optional[WorkerCapability] = None
    ) -> Optional[Any]:
        """
        Get an available LLM worker (Ollama or API)

        Args:
            prefer_ollama: Prefer local Ollama if available
            api_type: Specific API type for cloud APIs
            require_capability: Required capability

        Returns:
            Available LLM worker or None
        """
        # Try Ollama first if preferred
        if prefer_ollama and self.ollama_workers:
            for worker in self.ollama_workers.values():
                if require_capability and require_capability not in worker.capabilities:
                    continue
                if worker.can_handle(None):
                    return worker

        # Try cloud APIs
        api_worker = await self.llm_api_pool.get_available_worker(api_type=api_type)
        if api_worker:
            return api_worker

        # Try Ollama as fallback if not preferred initially
        if not prefer_ollama and self.ollama_workers:
            for worker in self.ollama_workers.values():
                if require_capability and require_capability not in worker.capabilities:
                    continue
                if worker.can_handle(None):
                    return worker

        return None

    async def allocate_resources(
        self,
        task_id: str,
        cpu_cores: Optional[float] = None,
        memory_mb: Optional[int] = None,
        gpu: bool = False,
    ) -> bool:
        """
        Allocate resources for a task

        Args:
            task_id: ID of task requesting resources
            cpu_cores: CPU cores needed
            memory_mb: Memory in MB needed
            gpu: GPU required

        Returns:
            True if resources allocated successfully
        """
        async with self._lock:
            # Simple allocation tracking
            # In production, this would check actual available resources
            allocation = {
                'cpu_cores': cpu_cores,
                'memory_mb': memory_mb,
                'gpu': gpu,
                'allocated_at': datetime.utcnow(),
            }

            self.allocated_resources[task_id] = allocation
            return True

    async def release_resources(self, task_id: str):
        """Release resources allocated to a task"""
        async with self._lock:
            if task_id in self.allocated_resources:
                del self.allocated_resources[task_id]

    def get_resource_stats(self) -> Dict[str, Any]:
        """Get resource utilization statistics"""
        total_cpu = sum(
            alloc.get('cpu_cores', 0)
            for alloc in self.allocated_resources.values()
            if alloc.get('cpu_cores')
        )
        total_memory = sum(
            alloc.get('memory_mb', 0)
            for alloc in self.allocated_resources.values()
            if alloc.get('memory_mb')
        )
        gpu_count = sum(
            1 for alloc in self.allocated_resources.values()
            if alloc.get('gpu')
        )

        return {
            'active_allocations': len(self.allocated_resources),
            'total_cpu_allocated': total_cpu,
            'total_memory_mb_allocated': total_memory,
            'gpus_allocated': gpu_count,
            'llm_api_usage': self.llm_api_pool.get_usage_summary(),
            'ollama_workers': len(self.ollama_workers),
        }
