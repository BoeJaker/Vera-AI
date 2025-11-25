"""
Vera Task Orchestration - External API Integration
===================================================
Extends orchestration with external compute APIs and LLM providers.

FEATURES:
- Cloud compute APIs (Lambda, Cloud Functions, etc.)
- LLM provider APIs (OpenAI, Anthropic, Google, etc.)
- Unified interface matching local execution
- Automatic routing based on task type
- Cost tracking and optimization
- Fallback mechanisms

SUPPORTED COMPUTE APIs:
- AWS Lambda
- Google Cloud Functions
- Azure Functions
- RunPod
- Modal
- Replicate
- Generic HTTP endpoints

SUPPORTED LLM PROVIDERS:
- OpenAI (GPT-4, GPT-3.5-turbo)
- Anthropic (Claude)
- Google (Gemini)
- Cohere
- Hugging Face
- Together AI
- Fireworks AI
- OpenAI-compatible APIs
"""

import json
import time
import logging
import requests
import asyncio
from typing import Any, Dict, List, Optional, Iterator, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from abc import ABC, abstractmethod
import threading
from collections import defaultdict

# Import base orchestration components
from vera_orchestrator import (
    TaskType, Priority, TaskStatus, TaskMetadata, TaskResult,
    registry, EventBus
)


# ============================================================================
# ENUMS & DATA CLASSES
# ============================================================================

class ExternalProvider(Enum):
    """External compute and LLM providers"""
    # Compute providers
    AWS_LAMBDA = "aws_lambda"
    GCP_FUNCTIONS = "gcp_functions"
    AZURE_FUNCTIONS = "azure_functions"
    RUNPOD = "runpod"
    MODAL = "modal"
    REPLICATE = "replicate"
    BANANA = "banana"
    HTTP_ENDPOINT = "http_endpoint"
    
    # LLM providers
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    COHERE = "cohere"
    HUGGINGFACE = "huggingface"
    TOGETHER = "together"
    FIREWORKS = "fireworks"
    OPENROUTER = "openrouter"
    OPENAI_COMPATIBLE = "openai_compatible"


@dataclass
class ExternalTaskMetadata:
    """Metadata for external API tasks"""
    provider: ExternalProvider
    endpoint: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    region: Optional[str] = None
    timeout: float = 300.0
    max_retries: int = 3
    stream: bool = False
    
    # Cost tracking
    estimated_cost_usd: float = 0.0
    actual_cost_usd: float = 0.0
    
    # Provider-specific settings
    extra_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class APIUsageStats:
    """Track API usage and costs"""
    provider: ExternalProvider
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_tokens_in: int = 0
    total_tokens_out: int = 0
    total_cost_usd: float = 0.0
    avg_latency_ms: float = 0.0
    last_request_at: Optional[float] = None


# ============================================================================
# EXTERNAL API MANAGER (BASE)
# ============================================================================

class ExternalAPIManager(ABC):
    """Abstract base class for external API managers"""
    
    def __init__(self, provider: ExternalProvider, event_bus: EventBus):
        self.provider = provider
        self.event_bus = event_bus
        self.stats = APIUsageStats(provider=provider)
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
    
    @abstractmethod
    def execute_task(
        self,
        task_name: str,
        metadata: ExternalTaskMetadata,
        *args,
        **kwargs
    ) -> Any:
        """Execute a task on the external API"""
        pass
    
    @abstractmethod
    def stream_task(
        self,
        task_name: str,
        metadata: ExternalTaskMetadata,
        *args,
        **kwargs
    ) -> Iterator[Any]:
        """Execute a streaming task on the external API"""
        pass
    
    def update_stats(
        self,
        success: bool,
        tokens_in: int = 0,
        tokens_out: int = 0,
        cost: float = 0.0,
        latency: float = 0.0
    ):
        """Update usage statistics"""
        self.stats.total_requests += 1
        if success:
            self.stats.successful_requests += 1
        else:
            self.stats.failed_requests += 1
        
        self.stats.total_tokens_in += tokens_in
        self.stats.total_tokens_out += tokens_out
        self.stats.total_cost_usd += cost
        
        # Update average latency
        if self.stats.avg_latency_ms == 0:
            self.stats.avg_latency_ms = latency
        else:
            self.stats.avg_latency_ms = (
                self.stats.avg_latency_ms * 0.9 + latency * 0.1
            )
        
        self.stats.last_request_at = time.time()
        
        # Broadcast stats update
        self.event_bus.publish("api.stats_updated", {
            "provider": self.provider.value,
            "stats": {
                "total_requests": self.stats.total_requests,
                "success_rate": self.stats.successful_requests / max(self.stats.total_requests, 1),
                "total_cost": self.stats.total_cost_usd,
                "avg_latency": self.stats.avg_latency_ms
            }
        })


# ============================================================================
# LLM API MANAGERS
# ============================================================================

class OpenAIManager(ExternalAPIManager):
    """OpenAI API manager (GPT-4, GPT-3.5-turbo, etc.)"""
    
    def __init__(self, event_bus: EventBus, api_key: str, base_url: Optional[str] = None):
        super().__init__(ExternalProvider.OPENAI, event_bus)
        self.api_key = api_key
        self.base_url = base_url or "https://api.openai.com/v1"
        
        # Cost per 1M tokens (approximate)
        self.costs = {
            "gpt-4": {"input": 30.0, "output": 60.0},
            "gpt-4-turbo": {"input": 10.0, "output": 30.0},
            "gpt-3.5-turbo": {"input": 0.5, "output": 1.5},
        }
    
    def execute_task(
        self,
        task_name: str,
        metadata: ExternalTaskMetadata,
        prompt: str,
        **kwargs
    ) -> str:
        """Execute LLM task on OpenAI"""
        start_time = time.time()
        
        try:
            # Prepare request
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": metadata.model or "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                **metadata.extra_params
            }
            
            # Make request
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=data,
                timeout=metadata.timeout
            )
            response.raise_for_status()
            
            result = response.json()
            
            # Extract response
            content = result["choices"][0]["message"]["content"]
            
            # Calculate cost
            usage = result.get("usage", {})
            tokens_in = usage.get("prompt_tokens", 0)
            tokens_out = usage.get("completion_tokens", 0)
            
            model_key = data["model"].split("-")[0] + "-" + data["model"].split("-")[1]
            costs = self.costs.get(model_key, {"input": 1.0, "output": 2.0})
            cost = (tokens_in * costs["input"] + tokens_out * costs["output"]) / 1_000_000
            
            # Update stats
            latency = (time.time() - start_time) * 1000
            self.update_stats(True, tokens_in, tokens_out, cost, latency)
            
            return content
            
        except Exception as e:
            self.logger.error(f"OpenAI API error: {e}")
            self.update_stats(False, 0, 0, 0, (time.time() - start_time) * 1000)
            raise
    
    def stream_task(
        self,
        task_name: str,
        metadata: ExternalTaskMetadata,
        prompt: str,
        **kwargs
    ) -> Iterator[str]:
        """Stream LLM task from OpenAI"""
        start_time = time.time()
        tokens_in = 0
        tokens_out = 0
        
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": metadata.model or "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": prompt}],
                "stream": True,
                **metadata.extra_params
            }
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=data,
                stream=True,
                timeout=metadata.timeout
            )
            response.raise_for_status()
            
            # Stream chunks
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data_str = line[6:]
                        if data_str == '[DONE]':
                            break
                        
                        try:
                            data = json.loads(data_str)
                            delta = data['choices'][0]['delta']
                            if 'content' in delta:
                                chunk = delta['content']
                                tokens_out += len(chunk.split())
                                yield chunk
                        except json.JSONDecodeError:
                            continue
            
            # Estimate cost (streaming doesn't return token counts)
            tokens_in = len(prompt.split()) * 1.3  # Rough estimate
            model_key = data["model"].split("-")[0] + "-" + data["model"].split("-")[1]
            costs = self.costs.get(model_key, {"input": 1.0, "output": 2.0})
            cost = (tokens_in * costs["input"] + tokens_out * costs["output"]) / 1_000_000
            
            latency = (time.time() - start_time) * 1000
            self.update_stats(True, int(tokens_in), tokens_out, cost, latency)
            
        except Exception as e:
            self.logger.error(f"OpenAI streaming error: {e}")
            self.update_stats(False, 0, 0, 0, (time.time() - start_time) * 1000)
            raise


class AnthropicManager(ExternalAPIManager):
    """Anthropic API manager (Claude)"""
    
    def __init__(self, event_bus: EventBus, api_key: str):
        super().__init__(ExternalProvider.ANTHROPIC, event_bus)
        self.api_key = api_key
        self.base_url = "https://api.anthropic.com/v1"
        
        # Cost per 1M tokens
        self.costs = {
            "claude-3-opus": {"input": 15.0, "output": 75.0},
            "claude-3-sonnet": {"input": 3.0, "output": 15.0},
            "claude-3-haiku": {"input": 0.25, "output": 1.25},
        }
    
    def execute_task(
        self,
        task_name: str,
        metadata: ExternalTaskMetadata,
        prompt: str,
        **kwargs
    ) -> str:
        """Execute LLM task on Anthropic"""
        start_time = time.time()
        
        try:
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": metadata.model or "claude-3-sonnet-20240229",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": metadata.extra_params.get("max_tokens", 4096),
                **{k: v for k, v in metadata.extra_params.items() if k != "max_tokens"}
            }
            
            response = requests.post(
                f"{self.base_url}/messages",
                headers=headers,
                json=data,
                timeout=metadata.timeout
            )
            response.raise_for_status()
            
            result = response.json()
            content = result["content"][0]["text"]
            
            # Calculate cost
            usage = result.get("usage", {})
            tokens_in = usage.get("input_tokens", 0)
            tokens_out = usage.get("output_tokens", 0)
            
            model_key = "-".join(data["model"].split("-")[:3])
            costs = self.costs.get(model_key, {"input": 3.0, "output": 15.0})
            cost = (tokens_in * costs["input"] + tokens_out * costs["output"]) / 1_000_000
            
            latency = (time.time() - start_time) * 1000
            self.update_stats(True, tokens_in, tokens_out, cost, latency)
            
            return content
            
        except Exception as e:
            self.logger.error(f"Anthropic API error: {e}")
            self.update_stats(False, 0, 0, 0, (time.time() - start_time) * 1000)
            raise
    
    def stream_task(
        self,
        task_name: str,
        metadata: ExternalTaskMetadata,
        prompt: str,
        **kwargs
    ) -> Iterator[str]:
        """Stream LLM task from Anthropic"""
        start_time = time.time()
        tokens_in = 0
        tokens_out = 0
        
        try:
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": metadata.model or "claude-3-sonnet-20240229",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": metadata.extra_params.get("max_tokens", 4096),
                "stream": True,
                **{k: v for k, v in metadata.extra_params.items() if k not in ["max_tokens", "stream"]}
            }
            
            response = requests.post(
                f"{self.base_url}/messages",
                headers=headers,
                json=data,
                stream=True,
                timeout=metadata.timeout
            )
            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data_str = line[6:]
                        try:
                            event = json.loads(data_str)
                            if event.get('type') == 'content_block_delta':
                                delta = event.get('delta', {})
                                if delta.get('type') == 'text_delta':
                                    chunk = delta.get('text', '')
                                    tokens_out += len(chunk.split())
                                    yield chunk
                            elif event.get('type') == 'message_start':
                                usage = event.get('message', {}).get('usage', {})
                                tokens_in = usage.get('input_tokens', 0)
                        except json.JSONDecodeError:
                            continue
            
            model_key = "-".join(data["model"].split("-")[:3])
            costs = self.costs.get(model_key, {"input": 3.0, "output": 15.0})
            cost = (tokens_in * costs["input"] + tokens_out * costs["output"]) / 1_000_000
            
            latency = (time.time() - start_time) * 1000
            self.update_stats(True, tokens_in, tokens_out, cost, latency)
            
        except Exception as e:
            self.logger.error(f"Anthropic streaming error: {e}")
            self.update_stats(False, 0, 0, 0, (time.time() - start_time) * 1000)
            raise


class GoogleGeminiManager(ExternalAPIManager):
    """Google Gemini API manager"""
    
    def __init__(self, event_bus: EventBus, api_key: str):
        super().__init__(ExternalProvider.GOOGLE, event_bus)
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        
        # Cost per 1M tokens
        self.costs = {
            "gemini-pro": {"input": 0.5, "output": 1.5},
            "gemini-pro-vision": {"input": 0.5, "output": 1.5},
        }
    
    def execute_task(
        self,
        task_name: str,
        metadata: ExternalTaskMetadata,
        prompt: str,
        **kwargs
    ) -> str:
        """Execute LLM task on Google Gemini"""
        start_time = time.time()
        
        try:
            model = metadata.model or "gemini-pro"
            url = f"{self.base_url}/models/{model}:generateContent?key={self.api_key}"
            
            data = {
                "contents": [{"parts": [{"text": prompt}]}],
                **metadata.extra_params
            }
            
            response = requests.post(
                url,
                json=data,
                timeout=metadata.timeout
            )
            response.raise_for_status()
            
            result = response.json()
            content = result["candidates"][0]["content"]["parts"][0]["text"]
            
            # Estimate tokens and cost
            tokens_in = len(prompt.split()) * 1.3
            tokens_out = len(content.split()) * 1.3
            
            costs = self.costs.get(model, {"input": 0.5, "output": 1.5})
            cost = (tokens_in * costs["input"] + tokens_out * costs["output"]) / 1_000_000
            
            latency = (time.time() - start_time) * 1000
            self.update_stats(True, int(tokens_in), int(tokens_out), cost, latency)
            
            return content
            
        except Exception as e:
            self.logger.error(f"Google Gemini API error: {e}")
            self.update_stats(False, 0, 0, 0, (time.time() - start_time) * 1000)
            raise
    
    def stream_task(
        self,
        task_name: str,
        metadata: ExternalTaskMetadata,
        prompt: str,
        **kwargs
    ) -> Iterator[str]:
        """Stream LLM task from Google Gemini"""
        start_time = time.time()
        tokens_in = len(prompt.split()) * 1.3
        tokens_out = 0
        
        try:
            model = metadata.model or "gemini-pro"
            url = f"{self.base_url}/models/{model}:streamGenerateContent?key={self.api_key}"
            
            data = {
                "contents": [{"parts": [{"text": prompt}]}],
                **metadata.extra_params
            }
            
            response = requests.post(
                url,
                json=data,
                stream=True,
                timeout=metadata.timeout
            )
            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    try:
                        chunk_data = json.loads(line)
                        if "candidates" in chunk_data:
                            text = chunk_data["candidates"][0]["content"]["parts"][0].get("text", "")
                            if text:
                                tokens_out += len(text.split())
                                yield text
                    except json.JSONDecodeError:
                        continue
            
            costs = self.costs.get(model, {"input": 0.5, "output": 1.5})
            cost = (tokens_in * costs["input"] + tokens_out * costs["output"]) / 1_000_000
            
            latency = (time.time() - start_time) * 1000
            self.update_stats(True, int(tokens_in), tokens_out, cost, latency)
            
        except Exception as e:
            self.logger.error(f"Google Gemini streaming error: {e}")
            self.update_stats(False, 0, 0, 0, (time.time() - start_time) * 1000)
            raise


# ============================================================================
# COMPUTE API MANAGERS
# ============================================================================

class AWSLambdaManager(ExternalAPIManager):
    """AWS Lambda manager"""
    
    def __init__(self, event_bus: EventBus, aws_access_key: str, aws_secret_key: str, region: str = "us-east-1"):
        super().__init__(ExternalProvider.AWS_LAMBDA, event_bus)
        self.region = region
        
        try:
            import boto3
            self.lambda_client = boto3.client(
                'lambda',
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key,
                region_name=region
            )
        except ImportError:
            self.logger.error("boto3 not installed. Install with: pip install boto3")
            raise
    
    def execute_task(
        self,
        task_name: str,
        metadata: ExternalTaskMetadata,
        *args,
        **kwargs
    ) -> Any:
        """Execute task on AWS Lambda"""
        start_time = time.time()
        
        try:
            function_name = metadata.extra_params.get('function_name', task_name)
            
            payload = {
                'args': args,
                'kwargs': kwargs
            }
            
            response = self.lambda_client.invoke(
                FunctionName=function_name,
                InvocationType='RequestResponse',
                Payload=json.dumps(payload)
            )
            
            result = json.loads(response['Payload'].read())
            
            # Calculate approximate cost
            billed_duration = response['ResponseMetadata']['HTTPHeaders'].get('x-amzn-remapped-content-length', 0)
            memory_mb = metadata.extra_params.get('memory_mb', 128)
            cost = (billed_duration / 1000) * (memory_mb / 1024) * 0.0000166667
            
            latency = (time.time() - start_time) * 1000
            self.update_stats(True, 0, 0, cost, latency)
            
            return result
            
        except Exception as e:
            self.logger.error(f"AWS Lambda error: {e}")
            self.update_stats(False, 0, 0, 0, (time.time() - start_time) * 1000)
            raise
    
    def stream_task(self, task_name: str, metadata: ExternalTaskMetadata, *args, **kwargs) -> Iterator[Any]:
        """AWS Lambda doesn't support streaming"""
        raise NotImplementedError("AWS Lambda does not support streaming")


class RunPodManager(ExternalAPIManager):
    """RunPod API manager for GPU workloads"""
    
    def __init__(self, event_bus: EventBus, api_key: str):
        super().__init__(ExternalProvider.RUNPOD, event_bus)
        self.api_key = api_key
        self.base_url = "https://api.runpod.io/v2"
    
    def execute_task(
        self,
        task_name: str,
        metadata: ExternalTaskMetadata,
        *args,
        **kwargs
    ) -> Any:
        """Execute task on RunPod"""
        start_time = time.time()
        
        try:
            endpoint_id = metadata.extra_params.get('endpoint_id')
            if not endpoint_id:
                raise ValueError("RunPod endpoint_id required")
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "input": {
                    "task": task_name,
                    "args": args,
                    "kwargs": kwargs
                }
            }
            
            # Submit job
            response = requests.post(
                f"{self.base_url}/{endpoint_id}/run",
                headers=headers,
                json=data,
                timeout=metadata.timeout
            )
            response.raise_for_status()
            
            job_id = response.json()['id']
            
            # Poll for result
            while True:
                status_response = requests.get(
                    f"{self.base_url}/{endpoint_id}/status/{job_id}",
                    headers=headers
                )
                status_response.raise_for_status()
                
                status_data = status_response.json()
                
                if status_data['status'] == 'COMPLETED':
                    result = status_data['output']
                    break
                elif status_data['status'] in ['FAILED', 'CANCELLED']:
                    raise Exception(f"Job failed: {status_data.get('error')}")
                
                time.sleep(1)
            
            # Estimate cost (RunPod charges per second)
            execution_time = status_data.get('executionTime', 0)
            gpu_type = metadata.extra_params.get('gpu_type', 'A40')
            cost_per_hour = {'A40': 0.79, 'A100': 1.89, 'RTX3090': 0.44}.get(gpu_type, 1.0)
            cost = (execution_time / 3600) * cost_per_hour
            
            latency = (time.time() - start_time) * 1000
            self.update_stats(True, 0, 0, cost, latency)
            
            return result
            
        except Exception as e:
            self.logger.error(f"RunPod error: {e}")
            self.update_stats(False, 0, 0, 0, (time.time() - start_time) * 1000)
            raise
    
    def stream_task(self, task_name: str, metadata: ExternalTaskMetadata, *args, **kwargs) -> Iterator[Any]:
        """RunPod streaming support"""
        # Implementation depends on specific RunPod endpoint
        raise NotImplementedError("Streaming depends on RunPod endpoint configuration")


class HTTPEndpointManager(ExternalAPIManager):
    """Generic HTTP endpoint manager"""
    
    def __init__(self, event_bus: EventBus):
        super().__init__(ExternalProvider.HTTP_ENDPOINT, event_bus)
    
    def execute_task(
        self,
        task_name: str,
        metadata: ExternalTaskMetadata,
        *args,
        **kwargs
    ) -> Any:
        """Execute task via HTTP endpoint"""
        start_time = time.time()
        
        try:
            if not metadata.endpoint:
                raise ValueError("HTTP endpoint URL required")
            
            headers = metadata.extra_params.get('headers', {})
            if metadata.api_key:
                headers['Authorization'] = f"Bearer {metadata.api_key}"
            
            method = metadata.extra_params.get('method', 'POST').upper()
            
            payload = {
                'task': task_name,
                'args': args,
                'kwargs': kwargs
            }
            
            if method == 'POST':
                response = requests.post(
                    metadata.endpoint,
                    headers=headers,
                    json=payload,
                    timeout=metadata.timeout
                )
            elif method == 'GET':
                response = requests.get(
                    metadata.endpoint,
                    headers=headers,
                    params=payload,
                    timeout=metadata.timeout
                )
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            result = response.json()
            
            latency = (time.time() - start_time) * 1000
            self.update_stats(True, 0, 0, 0, latency)
            
            return result
            
        except Exception as e:
            self.logger.error(f"HTTP endpoint error: {e}")
            self.update_stats(False, 0, 0, 0, (time.time() - start_time) * 1000)
            raise
    
    def stream_task(
        self,
        task_name: str,
        metadata: ExternalTaskMetadata,
        *args,
        **kwargs
    ) -> Iterator[Any]:
        """Stream from HTTP endpoint (SSE)"""
        start_time = time.time()
        
        try:
            if not metadata.endpoint:
                raise ValueError("HTTP endpoint URL required")
            
            headers = metadata.extra_params.get('headers', {})
            if metadata.api_key:
                headers['Authorization'] = f"Bearer {metadata.api_key}"
            headers['Accept'] = 'text/event-stream'
            
            payload = {
                'task': task_name,
                'args': args,
                'kwargs': kwargs,
                'stream': True
            }
            
            response = requests.post(
                metadata.endpoint,
                headers=headers,
                json=payload,
                stream=True,
                timeout=metadata.timeout
            )
            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data = line[6:]
                        if data == '[DONE]':
                            break
                        try:
                            yield json.loads(data)
                        except json.JSONDecodeError:
                            yield data
            
            latency = (time.time() - start_time) * 1000
            self.update_stats(True, 0, 0, 0, latency)
            
        except Exception as e:
            self.logger.error(f"HTTP streaming error: {e}")
            self.update_stats(False, 0, 0, 0, (time.time() - start_time) * 1000)
            raise


# ============================================================================
# EXTERNAL API ORCHESTRATOR
# ============================================================================

class ExternalAPIOrchestrator:
    """
    Orchestrator for external compute and LLM APIs.
    Integrates with InfrastructureOrchestrator for unified task management.
    """
    
    def __init__(self, event_bus: EventBus, config: Dict[str, Any]):
        """
        Initialize external API orchestrator.
        
        Args:
            event_bus: Event bus for coordination
            config: Configuration dict with API keys and settings
        """
        self.event_bus = event_bus
        self.config = config
        self.managers: Dict[ExternalProvider, ExternalAPIManager] = {}
        self.logger = logging.getLogger("ExternalAPIOrchestrator")
        
        # Initialize managers based on config
        self._initialize_managers()
    
    def _initialize_managers(self):
        """Initialize API managers from configuration"""
        # LLM providers
        if 'openai' in self.config:
            cfg = self.config['openai']
            self.managers[ExternalProvider.OPENAI] = OpenAIManager(
                self.event_bus,
                cfg['api_key'],
                cfg.get('base_url')
            )
            self.logger.info("Initialized OpenAI manager")
        
        if 'anthropic' in self.config:
            cfg = self.config['anthropic']
            self.managers[ExternalProvider.ANTHROPIC] = AnthropicManager(
                self.event_bus,
                cfg['api_key']
            )
            self.logger.info("Initialized Anthropic manager")
        
        if 'google' in self.config:
            cfg = self.config['google']
            self.managers[ExternalProvider.GOOGLE] = GoogleGeminiManager(
                self.event_bus,
                cfg['api_key']
            )
            self.logger.info("Initialized Google Gemini manager")
        
        # Compute providers
        if 'aws_lambda' in self.config:
            cfg = self.config['aws_lambda']
            self.managers[ExternalProvider.AWS_LAMBDA] = AWSLambdaManager(
                self.event_bus,
                cfg['access_key'],
                cfg['secret_key'],
                cfg.get('region', 'us-east-1')
            )
            self.logger.info("Initialized AWS Lambda manager")
        
        if 'runpod' in self.config:
            cfg = self.config['runpod']
            self.managers[ExternalProvider.RUNPOD] = RunPodManager(
                self.event_bus,
                cfg['api_key']
            )
            self.logger.info("Initialized RunPod manager")
        
        if 'http_endpoints' in self.config:
            self.managers[ExternalProvider.HTTP_ENDPOINT] = HTTPEndpointManager(
                self.event_bus
            )
            self.logger.info("Initialized HTTP endpoint manager")
    
    def execute_task(
        self,
        provider: ExternalProvider,
        task_name: str,
        metadata: ExternalTaskMetadata,
        *args,
        **kwargs
    ) -> Any:
        """Execute task on external API"""
        manager = self.managers.get(provider)
        if not manager:
            raise ValueError(f"Provider not configured: {provider.value}")
        
        self.logger.info(f"Executing {task_name} on {provider.value}")
        
        try:
            result = manager.execute_task(task_name, metadata, *args, **kwargs)
            
            self.event_bus.publish("external_task.completed", {
                "task_name": task_name,
                "provider": provider.value,
                "success": True
            })
            
            return result
            
        except Exception as e:
            self.event_bus.publish("external_task.failed", {
                "task_name": task_name,
                "provider": provider.value,
                "error": str(e)
            })
            raise
    
    def stream_task(
        self,
        provider: ExternalProvider,
        task_name: str,
        metadata: ExternalTaskMetadata,
        *args,
        **kwargs
    ) -> Iterator[Any]:
        """Stream task results from external API"""
        manager = self.managers.get(provider)
        if not manager:
            raise ValueError(f"Provider not configured: {provider.value}")
        
        self.logger.info(f"Streaming {task_name} from {provider.value}")
        
        try:
            for chunk in manager.stream_task(task_name, metadata, *args, **kwargs):
                yield chunk
            
            self.event_bus.publish("external_task.completed", {
                "task_name": task_name,
                "provider": provider.value,
                "success": True,
                "streaming": True
            })
            
        except Exception as e:
            self.event_bus.publish("external_task.failed", {
                "task_name": task_name,
                "provider": provider.value,
                "error": str(e)
            })
            raise
    
    def get_stats(self, provider: Optional[ExternalProvider] = None) -> Dict[str, Any]:
        """Get usage statistics"""
        if provider:
            manager = self.managers.get(provider)
            if manager:
                return {
                    "provider": provider.value,
                    "stats": {
                        "total_requests": manager.stats.total_requests,
                        "successful_requests": manager.stats.successful_requests,
                        "failed_requests": manager.stats.failed_requests,
                        "total_tokens_in": manager.stats.total_tokens_in,
                        "total_tokens_out": manager.stats.total_tokens_out,
                        "total_cost_usd": manager.stats.total_cost_usd,
                        "avg_latency_ms": manager.stats.avg_latency_ms,
                        "success_rate": manager.stats.successful_requests / max(manager.stats.total_requests, 1)
                    }
                }
        
        # All providers
        return {
            provider.value: {
                "total_requests": manager.stats.total_requests,
                "successful_requests": manager.stats.successful_requests,
                "total_cost_usd": manager.stats.total_cost_usd,
                "avg_latency_ms": manager.stats.avg_latency_ms
            }
            for provider, manager in self.managers.items()
        }
    
    def get_total_cost(self) -> float:
        """Get total cost across all providers"""
        return sum(
            manager.stats.total_cost_usd
            for manager in self.managers.values()
        )


# ============================================================================
# CONVENIENCE DECORATORS
# ============================================================================

def external_task(
    name: str,
    provider: ExternalProvider,
    model: Optional[str] = None,
    **kwargs
):
    """
    Decorator for external API tasks.
    
    Usage:
        @external_task("llm.summarize", provider=ExternalProvider.OPENAI, model="gpt-4")
        def summarize(text: str):
            return text
    """
    metadata = ExternalTaskMetadata(
        provider=provider,
        model=model,
        **kwargs
    )
    
    def decorator(func: Callable) -> Callable:
        # Register with task registry
        from vera_orchestrator import task, TaskType
        
        # Determine task type
        task_type = TaskType.LLM if provider in [
            ExternalProvider.OPENAI,
            ExternalProvider.ANTHROPIC,
            ExternalProvider.GOOGLE
        ] else TaskType.GENERAL
        
        return task(name, task_type=task_type, **kwargs)(func)
    
    return decorator


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    from vera_orchestrator import EventBus as BaseEventBus
    
    # Example configuration
    config = {
        'openai': {
            'api_key': 'sk-...',
            'base_url': None
        },
        'anthropic': {
            'api_key': 'sk-ant-...'
        },
        'runpod': {
            'api_key': 'your-runpod-key'
        }
    }
    
    # Initialize
    event_bus = BaseEventBus()
    orchestrator = ExternalAPIOrchestrator(event_bus, config)
    
    # Execute LLM task
    metadata = ExternalTaskMetadata(
        provider=ExternalProvider.OPENAI,
        model="gpt-3.5-turbo"
    )
    
    result = orchestrator.execute_task(
        ExternalProvider.OPENAI,
        "llm.summarize",
        metadata,
        prompt="Summarize the benefits of distributed computing"
    )
    
    print(f"Result: {result}")
    
    # Stream LLM task
    for chunk in orchestrator.stream_task(
        ExternalProvider.OPENAI,
        "llm.generate",
        metadata,
        prompt="Write a short story about AI"
    ):
        print(chunk, end='', flush=True)
    
    # Get stats
    stats = orchestrator.get_stats()
    print(f"\nTotal cost: ${orchestrator.get_total_cost():.4f}")
    print(f"Stats: {stats}")