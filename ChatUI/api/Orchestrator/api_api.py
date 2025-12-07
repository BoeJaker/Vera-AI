"""
FastAPI Router - External API Management
=========================================
Manages external compute and LLM API providers (OpenAI, Anthropic, AWS Lambda, etc.)
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, AsyncIterator
from datetime import datetime
from enum import Enum
import json
import asyncio

from Vera.Orchestration.orchestration_api import (
    ExternalAPIOrchestrator,
    ExternalProvider,
    ExternalTaskMetadata,
    APIUsageStats,
    OpenAIManager,
    AnthropicManager,
    GoogleGeminiManager,
    AWSLambdaManager,
    RunPodManager,
    HTTPEndpointManager
)


# ============================================================================
# ROUTER SETUP
# ============================================================================

router = APIRouter(prefix="/orchestrator/external", tags=["external_api"])


# ============================================================================
# GLOBAL STATE
# ============================================================================

class ExternalAPIState:
    def __init__(self):
        self.api_orchestrator: Optional[ExternalAPIOrchestrator] = None


external_state = ExternalAPIState()


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class ProviderEnum(str, Enum):
    """External providers"""
    # LLM Providers
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    COHERE = "cohere"
    HUGGINGFACE = "huggingface"
    TOGETHER = "together"
    FIREWORKS = "fireworks"
    OPENROUTER = "openrouter"
    OPENAI_COMPATIBLE = "openai_compatible"
    
    # Compute Providers
    AWS_LAMBDA = "aws_lambda"
    GCP_FUNCTIONS = "gcp_functions"
    AZURE_FUNCTIONS = "azure_functions"
    RUNPOD = "runpod"
    MODAL = "modal"
    REPLICATE = "replicate"
    HTTP_ENDPOINT = "http_endpoint"


class OpenAIConfig(BaseModel):
    """OpenAI configuration"""
    api_key: str
    base_url: Optional[str] = None


class AnthropicConfig(BaseModel):
    """Anthropic configuration"""
    api_key: str


class GoogleConfig(BaseModel):
    """Google Gemini configuration"""
    api_key: str


class AWSLambdaConfig(BaseModel):
    """AWS Lambda configuration"""
    access_key: str
    secret_key: str
    region: str = "us-east-1"


class RunPodConfig(BaseModel):
    """RunPod configuration"""
    api_key: str


class HTTPEndpointConfig(BaseModel):
    """Generic HTTP endpoint configuration"""
    enabled: bool = True


class ExternalAPIConfigRequest(BaseModel):
    """Request to initialize external API orchestrator"""
    openai: Optional[OpenAIConfig] = None
    anthropic: Optional[AnthropicConfig] = None
    google: Optional[GoogleConfig] = None
    aws_lambda: Optional[AWSLambdaConfig] = None
    runpod: Optional[RunPodConfig] = None
    http_endpoints: Optional[HTTPEndpointConfig] = None


class TaskExecutionRequest(BaseModel):
    """Request to execute a task on external API"""
    provider: ProviderEnum
    task_name: str
    prompt: Optional[str] = Field(None, description="Prompt for LLM tasks")
    model: Optional[str] = Field(None, description="Model to use")
    timeout: float = Field(300.0, ge=1.0, le=3600.0)
    max_retries: int = Field(3, ge=0, le=10)
    stream: bool = Field(False, description="Stream the response")
    
    # Additional parameters
    args: List[Any] = Field(default_factory=list)
    kwargs: Dict[str, Any] = Field(default_factory=dict)
    extra_params: Dict[str, Any] = Field(default_factory=dict)


class TaskExecutionResponse(BaseModel):
    """Response from task execution"""
    status: str
    provider: str
    task_name: str
    result: Any
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    cost_usd: Optional[float] = None
    latency_ms: Optional[float] = None


class ProviderStatsResponse(BaseModel):
    """Statistics for a provider"""
    provider: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    success_rate: float
    total_tokens_in: int
    total_tokens_out: int
    total_cost_usd: float
    avg_latency_ms: float
    last_request_at: Optional[float]


# ============================================================================
# INITIALIZATION
# ============================================================================

@router.post("/initialize")
async def initialize_external_apis(config: ExternalAPIConfigRequest):
    """Initialize external API orchestrator with provider configurations"""
    try:
        from Vera.Orchestration.orchestration import EventBus
        
        # Build configuration dict
        api_config = {}
        
        if config.openai:
            api_config['openai'] = {
                'api_key': config.openai.api_key,
                'base_url': config.openai.base_url
            }
        
        if config.anthropic:
            api_config['anthropic'] = {
                'api_key': config.anthropic.api_key
            }
        
        if config.google:
            api_config['google'] = {
                'api_key': config.google.api_key
            }
        
        if config.aws_lambda:
            api_config['aws_lambda'] = {
                'access_key': config.aws_lambda.access_key,
                'secret_key': config.aws_lambda.secret_key,
                'region': config.aws_lambda.region
            }
        
        if config.runpod:
            api_config['runpod'] = {
                'api_key': config.runpod.api_key
            }
        
        if config.http_endpoints:
            api_config['http_endpoints'] = {}
        
        # Create event bus (or get from main orchestrator)
        event_bus = EventBus()
        
        # Initialize orchestrator
        external_state.api_orchestrator = ExternalAPIOrchestrator(
            event_bus=event_bus,
            config=api_config
        )
        
        # Get list of initialized providers
        initialized_providers = list(external_state.api_orchestrator.managers.keys())
        
        return {
            "status": "success",
            "message": "External API orchestrator initialized",
            "providers_initialized": [p.value for p in initialized_providers],
            "provider_count": len(initialized_providers)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Initialization failed: {str(e)}")


# ============================================================================
# TASK EXECUTION
# ============================================================================

@router.post("/execute", response_model=TaskExecutionResponse)
async def execute_task(request: TaskExecutionRequest):
    """Execute a task on an external API provider"""
    if not external_state.api_orchestrator:
        raise HTTPException(status_code=400, detail="External APIs not initialized")
    
    try:
        # Map provider enum to ExternalProvider
        provider_map = {
            ProviderEnum.OPENAI: ExternalProvider.OPENAI,
            ProviderEnum.ANTHROPIC: ExternalProvider.ANTHROPIC,
            ProviderEnum.GOOGLE: ExternalProvider.GOOGLE,
            ProviderEnum.AWS_LAMBDA: ExternalProvider.AWS_LAMBDA,
            ProviderEnum.RUNPOD: ExternalProvider.RUNPOD,
            ProviderEnum.HTTP_ENDPOINT: ExternalProvider.HTTP_ENDPOINT,
        }
        
        provider = provider_map.get(request.provider)
        if not provider:
            raise HTTPException(status_code=400, detail=f"Unsupported provider: {request.provider}")
        
        # Check if provider is initialized
        if provider not in external_state.api_orchestrator.managers:
            raise HTTPException(
                status_code=400,
                detail=f"Provider not initialized: {request.provider.value}"
            )
        
        # Build metadata
        metadata = ExternalTaskMetadata(
            provider=provider,
            model=request.model,
            timeout=request.timeout,
            max_retries=request.max_retries,
            stream=request.stream,
            extra_params=request.extra_params
        )
        
        # Execute task
        if request.prompt:
            # LLM task
            result = external_state.api_orchestrator.execute_task(
                provider=provider,
                task_name=request.task_name,
                metadata=metadata,
                prompt=request.prompt,
                **request.kwargs
            )
        else:
            # Generic task
            result = external_state.api_orchestrator.execute_task(
                provider=provider,
                task_name=request.task_name,
                metadata=metadata,
                *request.args,
                **request.kwargs
            )
        
        # Get stats from manager
        manager = external_state.api_orchestrator.managers[provider]
        stats = manager.stats
        
        return TaskExecutionResponse(
            status="success",
            provider=request.provider.value,
            task_name=request.task_name,
            result=result,
            tokens_in=stats.total_tokens_in if hasattr(stats, 'total_tokens_in') else None,
            tokens_out=stats.total_tokens_out if hasattr(stats, 'total_tokens_out') else None,
            cost_usd=metadata.actual_cost_usd or stats.total_cost_usd,
            latency_ms=stats.avg_latency_ms
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Task execution failed: {str(e)}")


@router.post("/execute/stream")
async def execute_task_streaming(request: TaskExecutionRequest):
    """Execute a streaming task on an external API provider"""
    if not external_state.api_orchestrator:
        raise HTTPException(status_code=400, detail="External APIs not initialized")
    
    if not request.stream:
        raise HTTPException(status_code=400, detail="stream must be True for streaming endpoint")
    
    try:
        # Map provider enum
        provider_map = {
            ProviderEnum.OPENAI: ExternalProvider.OPENAI,
            ProviderEnum.ANTHROPIC: ExternalProvider.ANTHROPIC,
            ProviderEnum.GOOGLE: ExternalProvider.GOOGLE,
        }
        
        provider = provider_map.get(request.provider)
        if not provider:
            raise HTTPException(
                status_code=400,
                detail=f"Streaming not supported for provider: {request.provider}"
            )
        
        # Check if provider is initialized
        if provider not in external_state.api_orchestrator.managers:
            raise HTTPException(
                status_code=400,
                detail=f"Provider not initialized: {request.provider.value}"
            )
        
        # Build metadata
        metadata = ExternalTaskMetadata(
            provider=provider,
            model=request.model,
            timeout=request.timeout,
            max_retries=request.max_retries,
            stream=True,
            extra_params=request.extra_params
        )
        
        async def generate():
            """Generate streaming response"""
            try:
                if request.prompt:
                    # LLM streaming
                    for chunk in external_state.api_orchestrator.stream_task(
                        provider=provider,
                        task_name=request.task_name,
                        metadata=metadata,
                        prompt=request.prompt,
                        **request.kwargs
                    ):
                        yield f"data: {json.dumps({'chunk': chunk})}\n\n"
                else:
                    # Generic streaming
                    for chunk in external_state.api_orchestrator.stream_task(
                        provider=provider,
                        task_name=request.task_name,
                        metadata=metadata,
                        *request.args,
                        **request.kwargs
                    ):
                        yield f"data: {json.dumps({'chunk': chunk})}\n\n"
                
                yield f"data: {json.dumps({'status': 'complete'})}\n\n"
            
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e), 'status': 'error'})}\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Streaming failed: {str(e)}")


# ============================================================================
# LLM CONVENIENCE ENDPOINTS
# ============================================================================

@router.post("/llm/complete")
async def llm_complete(
    provider: ProviderEnum = Query(..., description="LLM provider"),
    prompt: str = Query(..., description="Prompt text"),
    model: Optional[str] = Query(None, description="Model name"),
    max_tokens: Optional[int] = Query(None, ge=1, le=100000),
    temperature: Optional[float] = Query(None, ge=0.0, le=2.0),
    stream: bool = Query(False, description="Stream response")
):
    """Convenience endpoint for LLM completions"""
    extra_params = {}
    if max_tokens:
        extra_params['max_tokens'] = max_tokens
    if temperature is not None:
        extra_params['temperature'] = temperature
    
    request = TaskExecutionRequest(
        provider=provider,
        task_name="llm.complete",
        prompt=prompt,
        model=model,
        stream=stream,
        extra_params=extra_params
    )
    
    if stream:
        return await execute_task_streaming(request)
    else:
        return await execute_task(request)


# @router.post("/llm/chat")
# async def llm_chat(
#     provider: ProviderEnum = Query(..., description="LLM provider"),
#     messages: List[Dict[str, str]] = Query(..., description="Chat messages"),
#     model: Optional[str] = Query(None, description="Model name"),
#     max_tokens: Optional[int] = Query(None, ge=1, le=100000),
#     temperature: Optional[float] = Query(None, ge=0.0, le=2.0),
#     stream: bool = Query(False, description="Stream response")
# ):
#     """Convenience endpoint for chat completions"""
#     extra_params = {"messages": messages}
#     if max_tokens:
#         extra_params['max_tokens'] = max_tokens
#     if temperature is not None:
#         extra_params['temperature'] = temperature
    
#     request = TaskExecutionRequest(
#         provider=provider,
#         task_name="llm.chat",
#         model=model,
#         stream=stream,
#         extra_params=extra_params
#     )
    
#     if stream:
#         return await execute_task_streaming(request)
#     else:
#         return await execute_task(request)


# ============================================================================
# PROVIDER MANAGEMENT
# ============================================================================

@router.get("/providers")
async def list_providers():
    """List all configured providers"""
    if not external_state.api_orchestrator:
        return {
            "providers": [],
            "count": 0
        }
    
    providers = []
    for provider, manager in external_state.api_orchestrator.managers.items():
        providers.append({
            "provider": provider.value,
            "type": "llm" if provider.value in [
                "openai", "anthropic", "google", "cohere", "huggingface"
            ] else "compute",
            "initialized": True
        })
    
    return {
        "providers": providers,
        "count": len(providers)
    }


@router.get("/providers/{provider}/status")
async def get_provider_status(provider: ProviderEnum):
    """Get status of a specific provider"""
    if not external_state.api_orchestrator:
        raise HTTPException(status_code=400, detail="External APIs not initialized")
    
    # Map provider
    provider_map = {
        ProviderEnum.OPENAI: ExternalProvider.OPENAI,
        ProviderEnum.ANTHROPIC: ExternalProvider.ANTHROPIC,
        ProviderEnum.GOOGLE: ExternalProvider.GOOGLE,
        ProviderEnum.AWS_LAMBDA: ExternalProvider.AWS_LAMBDA,
        ProviderEnum.RUNPOD: ExternalProvider.RUNPOD,
        ProviderEnum.HTTP_ENDPOINT: ExternalProvider.HTTP_ENDPOINT,
    }
    
    ext_provider = provider_map.get(provider)
    if not ext_provider:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    
    if ext_provider not in external_state.api_orchestrator.managers:
        return {
            "provider": provider.value,
            "initialized": False,
            "available": False
        }
    
    manager = external_state.api_orchestrator.managers[ext_provider]
    
    return {
        "provider": provider.value,
        "initialized": True,
        "available": True,
        "total_requests": manager.stats.total_requests,
        "success_rate": manager.stats.successful_requests / max(manager.stats.total_requests, 1)
    }


# ============================================================================
# STATISTICS & MONITORING
# ============================================================================

@router.get("/stats")
async def get_all_stats():
    """Get statistics for all providers"""
    if not external_state.api_orchestrator:
        return {
            "providers": {},
            "total_cost": 0.0,
            "total_requests": 0
        }
    
    stats = external_state.api_orchestrator.get_stats()
    total_cost = external_state.api_orchestrator.get_total_cost()
    
    total_requests = sum(
        provider_stats.get('total_requests', 0)
        for provider_stats in stats.values()
    )
    
    return {
        "providers": stats,
        "total_cost": total_cost,
        "total_requests": total_requests,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/stats/{provider}", response_model=ProviderStatsResponse)
async def get_provider_stats(provider: ProviderEnum):
    """Get detailed statistics for a specific provider"""
    if not external_state.api_orchestrator:
        raise HTTPException(status_code=400, detail="External APIs not initialized")
    
    # Map provider
    provider_map = {
        ProviderEnum.OPENAI: ExternalProvider.OPENAI,
        ProviderEnum.ANTHROPIC: ExternalProvider.ANTHROPIC,
        ProviderEnum.GOOGLE: ExternalProvider.GOOGLE,
        ProviderEnum.AWS_LAMBDA: ExternalProvider.AWS_LAMBDA,
        ProviderEnum.RUNPOD: ExternalProvider.RUNPOD,
        ProviderEnum.HTTP_ENDPOINT: ExternalProvider.HTTP_ENDPOINT,
    }
    
    ext_provider = provider_map.get(provider)
    if not ext_provider:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    
    if ext_provider not in external_state.api_orchestrator.managers:
        raise HTTPException(
            status_code=404,
            detail=f"Provider not initialized: {provider.value}"
        )
    
    manager = external_state.api_orchestrator.managers[ext_provider]
    stats = manager.stats
    
    return ProviderStatsResponse(
        provider=provider.value,
        total_requests=stats.total_requests,
        successful_requests=stats.successful_requests,
        failed_requests=stats.failed_requests,
        success_rate=stats.successful_requests / max(stats.total_requests, 1),
        total_tokens_in=stats.total_tokens_in,
        total_tokens_out=stats.total_tokens_out,
        total_cost_usd=stats.total_cost_usd,
        avg_latency_ms=stats.avg_latency_ms,
        last_request_at=stats.last_request_at
    )


@router.get("/stats/cost/summary")
async def get_cost_summary():
    """Get cost summary across all providers"""
    if not external_state.api_orchestrator:
        return {
            "total_cost": 0.0,
            "by_provider": {}
        }
    
    stats = external_state.api_orchestrator.get_stats()
    total_cost = external_state.api_orchestrator.get_total_cost()
    
    by_provider = {}
    for provider, provider_stats in stats.items():
        by_provider[provider] = provider_stats.get('total_cost_usd', 0.0)
    
    # Sort by cost
    sorted_providers = sorted(
        by_provider.items(),
        key=lambda x: x[1],
        reverse=True
    )
    
    return {
        "total_cost": total_cost,
        "by_provider": dict(sorted_providers),
        "currency": "USD",
        "timestamp": datetime.now().isoformat()
    }


@router.get("/stats/tokens/summary")
async def get_token_summary():
    """Get token usage summary for LLM providers"""
    if not external_state.api_orchestrator:
        return {
            "total_tokens": 0,
            "by_provider": {}
        }
    
    total_tokens_in = 0
    total_tokens_out = 0
    by_provider = {}
    
    for provider, manager in external_state.api_orchestrator.managers.items():
        if hasattr(manager.stats, 'total_tokens_in'):
            tokens_in = manager.stats.total_tokens_in
            tokens_out = manager.stats.total_tokens_out
            
            total_tokens_in += tokens_in
            total_tokens_out += tokens_out
            
            by_provider[provider.value] = {
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "total": tokens_in + tokens_out
            }
    
    return {
        "total_tokens_in": total_tokens_in,
        "total_tokens_out": total_tokens_out,
        "total_tokens": total_tokens_in + total_tokens_out,
        "by_provider": by_provider,
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get("/health")
async def external_api_health():
    """Health check for external API management"""
    if not external_state.api_orchestrator:
        return {
            "status": "not_initialized",
            "providers_available": 0
        }
    
    healthy_providers = 0
    total_providers = len(external_state.api_orchestrator.managers)
    
    for manager in external_state.api_orchestrator.managers.values():
        if manager.stats.total_requests == 0 or manager.stats.successful_requests > 0:
            healthy_providers += 1
    
    return {
        "status": "healthy" if healthy_providers > 0 else "degraded",
        "providers_available": total_providers,
        "healthy_providers": healthy_providers,
        "total_cost": external_state.api_orchestrator.get_total_cost()
    }


# ============================================================================
# HELPER FUNCTION FOR MAIN API
# ============================================================================

def initialize_external_api_router(
    api_orchestrator: ExternalAPIOrchestrator
):
    """
    Initialize external API router with orchestrator instance.
    Call this from main FastAPI startup.
    """
    external_state.api_orchestrator = api_orchestrator
    print("[External API] Initialized")