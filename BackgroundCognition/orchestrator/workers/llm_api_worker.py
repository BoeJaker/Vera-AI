"""
LLM API worker implementation for cloud-based LLM services
"""

import asyncio
import aiohttp
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from collections import deque

from .base import BaseWorker, WorkerCapability, WorkerConfig, WorkerStatus
from ..tasks import Task, TaskResult, TaskType


class RateLimiter:
    """Token bucket rate limiter"""

    def __init__(self, rate_per_minute: int, burst: Optional[int] = None):
        self.rate_per_minute = rate_per_minute
        self.burst = burst or rate_per_minute
        self.tokens = self.burst
        self.last_update = datetime.utcnow()
        self.lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> bool:
        """Acquire tokens, return True if successful"""
        async with self.lock:
            now = datetime.utcnow()
            elapsed = (now - self.last_update).total_seconds()

            # Refill tokens
            new_tokens = elapsed * (self.rate_per_minute / 60.0)
            self.tokens = min(self.burst, self.tokens + new_tokens)
            self.last_update = now

            # Check if we have enough tokens
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    def get_available_tokens(self) -> float:
        """Get current available tokens"""
        return self.tokens


class LLMAPIWorker(BaseWorker):
    """
    Worker for cloud LLM API services (OpenAI, Anthropic, etc.)
    """

    def __init__(
        self,
        api_type: str,  # 'openai', 'anthropic', 'gemini'
        api_key: str,
        worker_id: Optional[str] = None,
        config: Optional[WorkerConfig] = None,
        rate_limit_per_minute: int = 60,
        cost_per_1k_tokens: float = 0.0,
    ):
        # Set capabilities based on API type
        capabilities = [WorkerCapability.LLM_INFERENCE]
        if api_type == 'openai':
            capabilities.append(WorkerCapability.OPENAI_API)
        elif api_type == 'anthropic':
            capabilities.append(WorkerCapability.ANTHROPIC_API)
        elif api_type == 'gemini':
            capabilities.append(WorkerCapability.GEMINI_API)

        super().__init__(worker_id, capabilities, config)

        self.api_type = api_type
        self.api_key = api_key
        self.cost_per_1k_tokens = cost_per_1k_tokens

        # Rate limiting
        self.rate_limiter = RateLimiter(rate_limit_per_minute)

        # Usage tracking
        self.total_tokens_used = 0
        self.total_cost = 0.0
        self.requests_this_minute = deque()

        self._session: Optional[aiohttp.ClientSession] = None

    async def start(self) -> bool:
        """Start the LLM API worker"""
        try:
            self.status = WorkerStatus.STARTING

            # Create session with appropriate headers
            headers = self._get_headers()
            self._session = aiohttp.ClientSession(headers=headers)

            # Verify API key
            is_valid = await self.health_check()
            if is_valid:
                self.status = WorkerStatus.IDLE
                return True
            else:
                self.status = WorkerStatus.ERROR
                return False

        except Exception as e:
            print(f"Failed to start LLM API worker {self.id}: {e}")
            self.status = WorkerStatus.ERROR
            return False

    async def stop(self) -> bool:
        """Stop the LLM API worker"""
        try:
            if self._session:
                await self._session.close()
                self._session = None

            self.status = WorkerStatus.OFFLINE
            return True

        except Exception as e:
            print(f"Failed to stop LLM API worker {self.id}: {e}")
            return False

    def _get_headers(self) -> Dict[str, str]:
        """Get API-specific headers"""
        if self.api_type == 'openai':
            return {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
            }
        elif self.api_type == 'anthropic':
            return {
                'x-api-key': self.api_key,
                'anthropic-version': '2023-06-01',
                'Content-Type': 'application/json',
            }
        elif self.api_type == 'gemini':
            return {
                'Content-Type': 'application/json',
            }
        return {}

    def _get_api_url(self) -> str:
        """Get API endpoint URL"""
        if self.api_type == 'openai':
            return 'https://api.openai.com/v1/chat/completions'
        elif self.api_type == 'anthropic':
            return 'https://api.anthropic.com/v1/messages'
        elif self.api_type == 'gemini':
            return f'https://generativelanguage.googleapis.com/v1beta/models:generateContent?key={self.api_key}'
        return ''

    async def execute_task(self, task: Task) -> TaskResult:
        """Execute LLM task using cloud API"""
        try:
            if task.type != TaskType.LLM_REQUEST:
                return TaskResult(
                    success=False,
                    error=f"Unsupported task type: {task.type}",
                )

            # Check rate limit
            if not await self.rate_limiter.acquire():
                task.status = task.TaskStatus.RATE_LIMITED
                return TaskResult(
                    success=False,
                    error="Rate limit exceeded",
                )

            # Extract parameters
            messages = task.payload.get('messages', [])
            model = task.payload.get('model', self._get_default_model())
            temperature = task.payload.get('temperature', 0.7)
            max_tokens = task.payload.get('max_tokens', 1000)

            # Format request based on API type
            request_data = self._format_request(
                messages, model, temperature, max_tokens
            )

            # Make API request
            start_time = datetime.utcnow()
            async with self._session.post(
                self._get_api_url(),
                json=request_data,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout_seconds)
            ) as resp:
                response_data = await resp.json()

                if resp.status == 200:
                    # Extract response based on API type
                    content, tokens_used = self._extract_response(response_data)

                    # Track usage
                    self.total_tokens_used += tokens_used
                    cost = (tokens_used / 1000.0) * self.cost_per_1k_tokens
                    self.total_cost += cost

                    execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

                    return TaskResult(
                        success=True,
                        data=content,
                        metrics={
                            'model': model,
                            'tokens_used': tokens_used,
                            'cost_usd': cost,
                            'api_type': self.api_type,
                            'execution_time_ms': execution_time,
                        }
                    )
                else:
                    error_msg = response_data.get('error', {}).get('message', str(response_data))
                    return TaskResult(
                        success=False,
                        error=f"API request failed: {resp.status} - {error_msg}",
                    )

        except asyncio.TimeoutError:
            return TaskResult(
                success=False,
                error="API request timed out",
            )
        except Exception as e:
            return TaskResult(
                success=False,
                error=f"API execution error: {e}",
            )

    def _get_default_model(self) -> str:
        """Get default model for API type"""
        if self.api_type == 'openai':
            return 'gpt-4'
        elif self.api_type == 'anthropic':
            return 'claude-3-sonnet-20240229'
        elif self.api_type == 'gemini':
            return 'gemini-pro'
        return ''

    def _format_request(
        self,
        messages: List[Dict],
        model: str,
        temperature: float,
        max_tokens: int
    ) -> Dict:
        """Format request for specific API"""
        if self.api_type == 'openai':
            return {
                'model': model,
                'messages': messages,
                'temperature': temperature,
                'max_tokens': max_tokens,
            }
        elif self.api_type == 'anthropic':
            # Convert messages format
            system = None
            anthropic_messages = []
            for msg in messages:
                if msg['role'] == 'system':
                    system = msg['content']
                else:
                    anthropic_messages.append(msg)

            request = {
                'model': model,
                'messages': anthropic_messages,
                'temperature': temperature,
                'max_tokens': max_tokens,
            }
            if system:
                request['system'] = system
            return request

        elif self.api_type == 'gemini':
            # Convert to Gemini format
            contents = []
            for msg in messages:
                if msg['role'] != 'system':
                    contents.append({
                        'role': 'user' if msg['role'] == 'user' else 'model',
                        'parts': [{'text': msg['content']}]
                    })

            return {
                'contents': contents,
                'generationConfig': {
                    'temperature': temperature,
                    'maxOutputTokens': max_tokens,
                }
            }

        return {}

    def _extract_response(self, response_data: Dict) -> tuple[str, int]:
        """Extract content and token usage from API response"""
        if self.api_type == 'openai':
            content = response_data['choices'][0]['message']['content']
            tokens = response_data.get('usage', {}).get('total_tokens', 0)
            return content, tokens

        elif self.api_type == 'anthropic':
            content = response_data['content'][0]['text']
            tokens = response_data.get('usage', {}).get('input_tokens', 0) + \
                    response_data.get('usage', {}).get('output_tokens', 0)
            return content, tokens

        elif self.api_type == 'gemini':
            content = response_data['candidates'][0]['content']['parts'][0]['text']
            tokens = response_data.get('usageMetadata', {}).get('totalTokenCount', 0)
            return content, tokens

        return '', 0

    async def health_check(self) -> bool:
        """Check API availability"""
        try:
            if not self._session:
                return False

            # Make a minimal request to verify API key
            test_messages = [{'role': 'user', 'content': 'test'}]
            request_data = self._format_request(
                test_messages,
                self._get_default_model(),
                0.7,
                10
            )

            async with self._session.post(
                self._get_api_url(),
                json=request_data,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                is_healthy = resp.status in [200, 429]  # 429 = rate limited but valid

                if is_healthy:
                    self.metrics.last_heartbeat = datetime.utcnow()

                return is_healthy

        except Exception as e:
            print(f"LLM API health check failed: {e}")
            return False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        base_dict = super().to_dict()
        base_dict['api_type'] = self.api_type
        base_dict['rate_limit_per_minute'] = self.rate_limiter.rate_per_minute
        base_dict['available_tokens'] = self.rate_limiter.get_available_tokens()
        base_dict['total_tokens_used'] = self.total_tokens_used
        base_dict['total_cost_usd'] = self.total_cost
        base_dict['cost_per_1k_tokens'] = self.cost_per_1k_tokens
        return base_dict
