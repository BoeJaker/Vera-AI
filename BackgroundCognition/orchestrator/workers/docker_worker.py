"""
Docker worker implementation for container-based task execution
"""

import asyncio
import docker
import json
from typing import Optional, Dict, Any, List
from datetime import datetime

from .base import BaseWorker, WorkerCapability, WorkerConfig, WorkerStatus
from ..tasks import Task, TaskResult, TaskType


class DockerWorker(BaseWorker):
    """
    Worker that executes tasks in Docker containers
    """

    def __init__(
        self,
        image: str,
        worker_id: Optional[str] = None,
        capabilities: Optional[List[WorkerCapability]] = None,
        config: Optional[WorkerConfig] = None,
        container_config: Optional[Dict[str, Any]] = None,
    ):
        default_caps = capabilities or [
            WorkerCapability.CODE_EXECUTION,
            WorkerCapability.DOCKER,
        ]
        super().__init__(worker_id, default_caps, config)

        self.image = image
        self.container_config = container_config or {}
        self.container = None
        self.docker_client = None

    async def start(self) -> bool:
        """Start the Docker worker by creating a container"""
        try:
            self.status = WorkerStatus.STARTING

            # Initialize Docker client
            self.docker_client = docker.from_env()

            # Check if image exists, pull if needed
            try:
                self.docker_client.images.get(self.image)
            except docker.errors.ImageNotFound:
                print(f"Pulling Docker image: {self.image}")
                self.docker_client.images.pull(self.image)

            # Create container
            container_opts = {
                'image': self.image,
                'detach': True,
                'name': f'vera-worker-{self.id}',
                'labels': {'vera-worker-id': self.id},
                **self.container_config,
            }

            self.container = self.docker_client.containers.create(**container_opts)
            self.container.start()

            self.status = WorkerStatus.IDLE
            return True

        except Exception as e:
            print(f"Failed to start Docker worker {self.id}: {e}")
            self.status = WorkerStatus.ERROR
            return False

    async def stop(self) -> bool:
        """Stop the Docker worker and remove container"""
        try:
            if self.container:
                self.container.stop(timeout=10)
                self.container.remove()
                self.container = None

            if self.docker_client:
                self.docker_client.close()
                self.docker_client = None

            self.status = WorkerStatus.OFFLINE
            return True

        except Exception as e:
            print(f"Failed to stop Docker worker {self.id}: {e}")
            return False

    async def execute_task(self, task: Task) -> TaskResult:
        """Execute task in Docker container"""
        try:
            if not self.container:
                return TaskResult(
                    success=False,
                    error="Container not running",
                )

            # Prepare command based on task type
            if task.type == TaskType.CODE_EXECUTION:
                code = task.payload.get('code', '')
                language = task.payload.get('language', 'python')

                if language == 'python':
                    cmd = ['python', '-c', code]
                elif language == 'bash':
                    cmd = ['bash', '-c', code]
                else:
                    return TaskResult(
                        success=False,
                        error=f"Unsupported language: {language}",
                    )

                # Execute in container
                exec_result = self.container.exec_run(
                    cmd,
                    workdir='/tmp',
                    user='root',
                )

                output = exec_result.output.decode('utf-8')
                success = exec_result.exit_code == 0

                return TaskResult(
                    success=success,
                    data=output,
                    error=None if success else f"Exit code: {exec_result.exit_code}",
                    metrics={'exit_code': exec_result.exit_code},
                )

            elif task.type == TaskType.DOCKER_TASK:
                # Generic Docker task
                cmd = task.payload.get('command', [])
                exec_result = self.container.exec_run(cmd)

                return TaskResult(
                    success=exec_result.exit_code == 0,
                    data=exec_result.output.decode('utf-8'),
                    metrics={'exit_code': exec_result.exit_code},
                )

            else:
                return TaskResult(
                    success=False,
                    error=f"Unsupported task type: {task.type}",
                )

        except Exception as e:
            return TaskResult(
                success=False,
                error=f"Docker execution error: {e}",
            )

    async def health_check(self) -> bool:
        """Check if container is running"""
        try:
            if not self.container:
                return False

            self.container.reload()
            is_running = self.container.status == 'running'

            if is_running:
                # Update metrics
                stats = self.container.stats(stream=False)
                cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - \
                           stats['precpu_stats']['cpu_usage']['total_usage']
                system_delta = stats['cpu_stats']['system_cpu_usage'] - \
                              stats['precpu_stats']['system_cpu_usage']
                cpu_count = stats['cpu_stats'].get('online_cpus', 1)

                if system_delta > 0:
                    self.metrics.cpu_usage_percent = (cpu_delta / system_delta) * cpu_count * 100.0

                memory_usage = stats['memory_stats'].get('usage', 0)
                self.metrics.memory_usage_mb = memory_usage / (1024 * 1024)

            return is_running

        except Exception as e:
            print(f"Health check failed for Docker worker {self.id}: {e}")
            return False


class DockerWorkerPool:
    """
    Manages a pool of Docker workers
    """

    def __init__(
        self,
        image: str,
        pool_size: int = 3,
        worker_config: Optional[WorkerConfig] = None,
        container_config: Optional[Dict[str, Any]] = None,
    ):
        self.image = image
        self.pool_size = pool_size
        self.worker_config = worker_config
        self.container_config = container_config
        self.workers: List[DockerWorker] = []

    async def start(self) -> List[DockerWorker]:
        """Start all workers in the pool"""
        for i in range(self.pool_size):
            worker = DockerWorker(
                image=self.image,
                worker_id=f"docker-{i}",
                config=self.worker_config,
                container_config=self.container_config,
            )

            if await worker.start():
                self.workers.append(worker)
            else:
                print(f"Failed to start Docker worker {i}")

        return self.workers

    async def stop(self):
        """Stop all workers in the pool"""
        for worker in self.workers:
            await worker.stop()

        self.workers.clear()

    async def scale(self, new_size: int):
        """Scale the pool to a new size"""
        current_size = len(self.workers)

        if new_size > current_size:
            # Scale up
            for i in range(current_size, new_size):
                worker = DockerWorker(
                    image=self.image,
                    worker_id=f"docker-{i}",
                    config=self.worker_config,
                    container_config=self.container_config,
                )
                if await worker.start():
                    self.workers.append(worker)

        elif new_size < current_size:
            # Scale down
            workers_to_remove = self.workers[new_size:]
            self.workers = self.workers[:new_size]

            for worker in workers_to_remove:
                await worker.stop()

    def get_workers(self) -> List[DockerWorker]:
        """Get all workers in the pool"""
        return self.workers
