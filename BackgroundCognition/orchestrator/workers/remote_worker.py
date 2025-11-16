"""
Remote worker implementation for distributed compute
"""

import asyncio
import aiohttp
from typing import Optional, List, Dict, Any
from datetime import datetime

from .base import BaseWorker, WorkerCapability, WorkerConfig, WorkerStatus
from ..tasks import Task, TaskResult, TaskType


class RemoteWorker(BaseWorker):
    """
    Worker that executes tasks on remote compute nodes
    """

    def __init__(
        self,
        remote_url: str,
        worker_id: Optional[str] = None,
        capabilities: Optional[List[WorkerCapability]] = None,
        config: Optional[WorkerConfig] = None,
        auth_token: Optional[str] = None,
    ):
        default_caps = capabilities or [WorkerCapability.REMOTE_COMPUTE]
        super().__init__(worker_id, default_caps, config)

        self.remote_url = remote_url.rstrip('/')
        self.auth_token = auth_token
        self._session: Optional[aiohttp.ClientSession] = None

    async def start(self) -> bool:
        """Start the remote worker"""
        try:
            self.status = WorkerStatus.STARTING

            # Create session with auth headers
            headers = {}
            if self.auth_token:
                headers['Authorization'] = f'Bearer {self.auth_token}'

            self._session = aiohttp.ClientSession(headers=headers)

            # Check remote availability
            is_available = await self.health_check()
            if is_available:
                # Fetch remote capabilities
                await self._fetch_capabilities()
                self.status = WorkerStatus.IDLE
                return True
            else:
                self.status = WorkerStatus.ERROR
                return False

        except Exception as e:
            print(f"Failed to start remote worker {self.id}: {e}")
            self.status = WorkerStatus.ERROR
            return False

    async def stop(self) -> bool:
        """Stop the remote worker"""
        try:
            if self._session:
                await self._session.close()
                self._session = None

            self.status = WorkerStatus.OFFLINE
            return True

        except Exception as e:
            print(f"Failed to stop remote worker {self.id}: {e}")
            return False

    async def _fetch_capabilities(self):
        """Fetch capabilities from remote worker"""
        try:
            async with self._session.get(f"{self.remote_url}/capabilities") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    caps = data.get('capabilities', [])

                    # Add capabilities
                    for cap_str in caps:
                        try:
                            cap = WorkerCapability(cap_str)
                            self.capabilities.add(cap)
                        except ValueError:
                            pass

                    # Update config
                    if 'max_concurrent_tasks' in data:
                        self.config.max_concurrent_tasks = data['max_concurrent_tasks']

        except Exception as e:
            print(f"Failed to fetch remote capabilities: {e}")

    async def execute_task(self, task: Task) -> TaskResult:
        """Execute task on remote worker"""
        try:
            # Serialize task
            task_data = {
                'id': task.id,
                'type': task.type.value,
                'payload': task.payload,
                'timeout': self.config.timeout_seconds,
            }

            # Send to remote worker
            async with self._session.post(
                f"{self.remote_url}/execute",
                json=task_data,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout_seconds + 10)
            ) as resp:
                if resp.status == 200:
                    result_data = await resp.json()

                    return TaskResult(
                        success=result_data.get('success', False),
                        data=result_data.get('data'),
                        error=result_data.get('error'),
                        metrics=result_data.get('metrics', {}),
                    )
                else:
                    error_text = await resp.text()
                    return TaskResult(
                        success=False,
                        error=f"Remote execution failed: {resp.status} - {error_text}",
                    )

        except asyncio.TimeoutError:
            return TaskResult(
                success=False,
                error="Remote execution timed out",
            )
        except Exception as e:
            return TaskResult(
                success=False,
                error=f"Remote execution error: {e}",
            )

    async def health_check(self) -> bool:
        """Check if remote worker is available"""
        try:
            if not self._session:
                return False

            async with self._session.get(
                f"{self.remote_url}/health",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                is_healthy = resp.status == 200

                if is_healthy:
                    # Update metrics from remote
                    try:
                        data = await resp.json()
                        if 'cpu_usage' in data:
                            self.metrics.cpu_usage_percent = data['cpu_usage']
                        if 'memory_usage_mb' in data:
                            self.metrics.memory_usage_mb = data['memory_usage_mb']
                    except:
                        pass

                    self.metrics.last_heartbeat = datetime.utcnow()

                return is_healthy

        except Exception as e:
            print(f"Remote health check failed for {self.remote_url}: {e}")
            return False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        base_dict = super().to_dict()
        base_dict['remote_url'] = self.remote_url
        base_dict['has_auth'] = bool(self.auth_token)
        return base_dict
