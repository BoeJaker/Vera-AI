"""
Ollama worker implementation for local LLM inference
"""

import asyncio
import aiohttp
from typing import Optional, List, Dict, Any
from datetime import datetime

from .base import BaseWorker, WorkerCapability, WorkerConfig, WorkerStatus
from ..tasks import Task, TaskResult, TaskType


class OllamaWorker(BaseWorker):
    """
    Worker specialized for Ollama LLM requests
    """

    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        worker_id: Optional[str] = None,
        config: Optional[WorkerConfig] = None,
        default_model: str = "llama2",
    ):
        capabilities = [
            WorkerCapability.LLM_INFERENCE,
            WorkerCapability.OLLAMA,
        ]
        super().__init__(worker_id, capabilities, config)

        self.ollama_url = ollama_url
        self.default_model = default_model
        self.available_models: List[str] = []
        self._session: Optional[aiohttp.ClientSession] = None

    async def start(self) -> bool:
        """Start the Ollama worker"""
        try:
            self.status = WorkerStatus.STARTING
            self._session = aiohttp.ClientSession()

            # Check Ollama availability and get models
            is_available = await self.health_check()
            if is_available:
                await self._fetch_available_models()
                self.status = WorkerStatus.IDLE
                return True
            else:
                self.status = WorkerStatus.ERROR
                return False

        except Exception as e:
            print(f"Failed to start Ollama worker {self.id}: {e}")
            self.status = WorkerStatus.ERROR
            return False

    async def stop(self) -> bool:
        """Stop the Ollama worker"""
        try:
            if self._session:
                await self._session.close()
                self._session = None

            self.status = WorkerStatus.OFFLINE
            return True

        except Exception as e:
            print(f"Failed to stop Ollama worker {self.id}: {e}")
            return False

    async def _fetch_available_models(self):
        """Fetch list of available models from Ollama"""
        try:
            async with self._session.get(f"{self.ollama_url}/api/tags") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.available_models = [
                        model['name'] for model in data.get('models', [])
                    ]
        except Exception as e:
            print(f"Failed to fetch Ollama models: {e}")

    async def execute_task(self, task: Task) -> TaskResult:
        """Execute LLM task using Ollama"""
        try:
            if task.type not in [TaskType.LLM_REQUEST, TaskType.OLLAMA_REQUEST]:
                return TaskResult(
                    success=False,
                    error=f"Unsupported task type: {task.type}",
                )

            # Extract parameters
            prompt = task.payload.get('prompt', '')
            model = task.payload.get('model', self.default_model)
            system = task.payload.get('system', '')
            temperature = task.payload.get('temperature', 0.7)
            stream = task.payload.get('stream', False)

            # Prepare request
            request_data = {
                'model': model,
                'prompt': prompt,
                'stream': stream,
                'options': {
                    'temperature': temperature,
                }
            }

            if system:
                request_data['system'] = system

            # Make request
            async with self._session.post(
                f"{self.ollama_url}/api/generate",
                json=request_data,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout_seconds)
            ) as resp:
                if resp.status == 200:
                    if stream:
                        # Handle streaming response
                        full_response = ""
                        async for line in resp.content:
                            if line:
                                import json
                                chunk = json.loads(line)
                                full_response += chunk.get('response', '')

                                # Report progress if callback available
                                if task.on_progress and chunk.get('done', False):
                                    task.on_progress(1.0)

                        return TaskResult(
                            success=True,
                            data=full_response,
                            metrics={
                                'model': model,
                                'stream': True,
                            }
                        )
                    else:
                        # Non-streaming response
                        data = await resp.json()
                        return TaskResult(
                            success=True,
                            data=data.get('response', ''),
                            metrics={
                                'model': model,
                                'total_duration': data.get('total_duration', 0),
                                'load_duration': data.get('load_duration', 0),
                                'prompt_eval_count': data.get('prompt_eval_count', 0),
                                'eval_count': data.get('eval_count', 0),
                            }
                        )
                else:
                    error_text = await resp.text()
                    return TaskResult(
                        success=False,
                        error=f"Ollama request failed: {resp.status} - {error_text}",
                    )

        except asyncio.TimeoutError:
            return TaskResult(
                success=False,
                error="Ollama request timed out",
            )
        except Exception as e:
            return TaskResult(
                success=False,
                error=f"Ollama execution error: {e}",
            )

    async def health_check(self) -> bool:
        """Check if Ollama is available"""
        try:
            if not self._session:
                return False

            async with self._session.get(
                f"{self.ollama_url}/api/tags",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                is_healthy = resp.status == 200

                if is_healthy:
                    self.metrics.last_heartbeat = datetime.utcnow()

                return is_healthy

        except Exception as e:
            print(f"Ollama health check failed: {e}")
            return False

    async def pull_model(self, model_name: str) -> bool:
        """Pull a model from Ollama"""
        try:
            async with self._session.post(
                f"{self.ollama_url}/api/pull",
                json={'name': model_name, 'stream': False},
                timeout=aiohttp.ClientTimeout(total=600)  # 10 minutes for model download
            ) as resp:
                if resp.status == 200:
                    await self._fetch_available_models()
                    return True
                return False

        except Exception as e:
            print(f"Failed to pull model {model_name}: {e}")
            return False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        base_dict = super().to_dict()
        base_dict['ollama_url'] = self.ollama_url
        base_dict['default_model'] = self.default_model
        base_dict['available_models'] = self.available_models
        return base_dict
