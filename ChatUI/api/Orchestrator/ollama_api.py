"""
Ollama API Router for Vera
Exposes Ollama manager functionality through REST endpoints
Updated to support multi-instance Ollama with load balancing
"""

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import asyncio
import json
from datetime import datetime

# ============================================================================
# UPDATED IMPORTS - Multi-Instance Manager
# ============================================================================

try:
    from Vera.Ollama.multi_instance_manager import MultiInstanceOllamaManager
    MULTI_INSTANCE_AVAILABLE = True
except ImportError:
    MULTI_INSTANCE_AVAILABLE = False
    from Vera.Ollama.manager import OllamaConnectionManager
    MultiInstanceOllamaManager = None

router = APIRouter(prefix="/api/ollama", tags=["ollama"])

# Global manager instance (initialized on first use)
_manager: Optional[Any] = None

# In Vera/ChatUI/api/Orchestrator/ollama_api.py

def get_manager():
    """Get or create the global Ollama manager instance"""
    global _manager
    if _manager is None:
        try:
            # Try to import the configuration manager
            from Vera.Configuration.config_manager import ConfigManager
            config_mgr = ConfigManager()
            config = config_mgr.config.ollama
            
            # Use multi-instance manager if available
            if MULTI_INSTANCE_AVAILABLE and MultiInstanceOllamaManager:
                print("[Ollama API] Using MultiInstanceOllamaManager")
                _manager = MultiInstanceOllamaManager(config=config)
            else:
                print("[Ollama API] Using OllamaConnectionManager (fallback)")
                _manager = OllamaConnectionManager(config=config)
                
        except (ImportError, AttributeError) as e:
            print(f"[Ollama API] Could not load config manager: {e}")
            print("[Ollama API] Using default configuration")
            
            # Create a complete default config object with ALL required fields
            from dataclasses import dataclass, field
            from typing import List
            
            @dataclass
            class DefaultInstanceConfig:
                name: str = "default"
                api_url: str = "http://localhost:11434"
                priority: int = 1
                max_concurrent: int = 2
                enabled: bool = True
                timeout: int = 2400
            
            @dataclass
            class DefaultOllamaConfig:
                # Primary settings
                api_url: str = "http://localhost:11434"
                timeout: int = 2400
                use_local_fallback: bool = False
                connection_retry_attempts: int = 3
                connection_retry_delay: float = 1.0
                
                # Multi-instance settings
                instances: List = field(default_factory=lambda: [
                    DefaultInstanceConfig(
                        name="local",
                        api_url="http://localhost:11434",
                        priority=1,
                        max_concurrent=2
                    )
                ])
                load_balance_strategy: str = "least_loaded"
                enable_request_queue: bool = True
                max_queue_size: int = 100
                
                # Legacy settings
                enable_thought_capture: bool = True
                temperature: float = 0.7
                top_k: int = 40
                top_p: float = 0.9
                num_predict: int = -1
                repeat_penalty: float = 1.1
                cache_model_metadata: bool = True
                metadata_cache_ttl: int = 3600
            
            config = DefaultOllamaConfig()
            
            if MULTI_INSTANCE_AVAILABLE and MultiInstanceOllamaManager:
                _manager = MultiInstanceOllamaManager(config=config)
            else:
                _manager = OllamaConnectionManager(config=config)
    
    return _manager
# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def serialize_model(model) -> Dict[str, Any]:
    """
    Convert model object to JSON-serializable dict
    Handles both dict and object types
    """
    if isinstance(model, dict):
        return {
            "model": model.get("model") or model.get("name", "unknown"),
            "name": model.get("name") or model.get("model", "unknown"),
            "size": model.get("size", 0),
            "modified_at": model.get("modified_at", "")
        }
    else:
        # Handle object types (from old manager or ollama library)
        try:
            if hasattr(model, 'model'):
                name = model.model
            elif hasattr(model, 'name'):
                name = model.name
            else:
                name = str(model)
            
            return {
                "model": name,
                "name": name,
                "size": getattr(model, 'size', 0),
                "modified_at": getattr(model, 'modified_at', "")
            }
        except Exception as e:
            print(f"[Ollama API] Warning: Failed to serialize model {model}: {e}")
            return {
                "model": str(model),
                "name": str(model),
                "size": 0,
                "modified_at": ""
            }


# ============================================================================
# DIAGNOSTIC ENDPOINTS
# ============================================================================

@router.get("/ping")
async def ping():
    """Simple ping endpoint to test if the router is working"""
    return JSONResponse({
        "status": "ok",
        "message": "Ollama API router is running",
        "multi_instance": MULTI_INSTANCE_AVAILABLE
    })


@router.get("/diagnostics")
async def diagnostics():
    """Diagnostic endpoint to check manager type and configuration"""
    try:
        manager = get_manager()
        manager_type = type(manager).__name__
        
        # Get pool stats if multi-instance
        pool_stats = None
        if hasattr(manager, 'get_pool_stats'):
            try:
                pool_stats = manager.get_pool_stats()
            except Exception as e:
                pool_stats = {"error": str(e)}
        
        # Test connection
        connection_ok = False
        try:
            if hasattr(manager, 'test_connection'):
                connection_ok = manager.test_connection()
        except Exception as e:
            connection_ok = f"Error: {e}"
        
        # Get model count
        model_count = 0
        try:
            models = manager.list_models()
            model_count = len(models) if models else 0
        except Exception as e:
            model_count = f"Error: {e}"
        
        return JSONResponse({
            "manager_type": manager_type,
            "is_multi_instance": manager_type == "MultiInstanceOllamaManager",
            "multi_instance_available": MULTI_INSTANCE_AVAILABLE,
            "has_pool": hasattr(manager, 'pool'),
            "pool_stats": pool_stats,
            "connection_ok": connection_ok,
            "model_count": model_count,
            "api_url": getattr(manager, 'api_url', 'unknown'),
            "manager_module": type(manager).__module__
        })
    
    except Exception as e:
        import traceback
        return JSONResponse({
            "error": str(e),
            "traceback": traceback.format_exc()
        }, status_code=500)


# ============================================================================
# CONNECTION & STATUS
# ============================================================================

@router.get("/health")
async def health_check():
    """Check Ollama connection health"""
    try:
        manager = get_manager()
        is_connected = manager.test_connection()
        
        # Get mode based on manager type
        mode = "multi_instance" if hasattr(manager, 'pool') else "single"
        if hasattr(manager, 'use_local'):
            mode = "local" if manager.use_local else mode
        
        result = {
            "status": "healthy" if is_connected else "unhealthy",
            "connected": is_connected,
            "mode": mode,
            "timestamp": datetime.now().isoformat()
        }
        
        # Add API URL info
        if hasattr(manager, 'api_url'):
            result["api_url"] = manager.api_url
        elif hasattr(manager, 'pool'):
            # Multi-instance - show all instances
            pool_stats = manager.get_pool_stats()
            result["instances"] = {
                name: {
                    "url": stats["api_url"],
                    "healthy": stats["is_healthy"]
                }
                for name, stats in pool_stats.items()
            }
        
        return JSONResponse(result)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


@router.get("/status")
async def get_status():
    """Get detailed Ollama status"""
    try:
        manager = get_manager()
        
        # Test connection if not already done
        if hasattr(manager, 'test_connection'):
            if hasattr(manager, 'connection_tested') and not manager.connection_tested:
                manager.test_connection()
        
        # Get model count
        model_count = 0
        try:
            models = manager.list_models()
            model_count = len(models) if models else 0
        except:
            model_count = 0
        
        result = {
            "status": "success",
            "model_count": model_count,
        }
        
        # Add manager-specific info
        if hasattr(manager, 'pool'):
            # Multi-instance manager
            pool_stats = manager.get_pool_stats()
            result.update({
                "mode": "multi_instance",
                "instances": pool_stats,
                "total_instances": len(pool_stats),
                "healthy_instances": sum(1 for s in pool_stats.values() if s["is_healthy"])
            })
        else:
            # Single instance manager
            result.update({
                "mode": "local" if getattr(manager, 'use_local', False) else "api",
                "api_url": getattr(manager, 'api_url', 'unknown'),
                "timeout": getattr(manager, 'timeout', 0),
                "connected": getattr(manager, 'connection_tested', False)
            })
        
        # Add thought capture info if available
        if hasattr(manager, 'thought_capture'):
            result["thought_capture_enabled"] = manager.thought_capture.enabled
        
        # Add cache info
        if hasattr(manager, 'model_metadata_cache'):
            result["cache_size"] = len(manager.model_metadata_cache)
        
        return JSONResponse(result)
    
    except Exception as e:
        import traceback
        raise HTTPException(
            status_code=500, 
            detail=f"Status check failed: {str(e)}\n{traceback.format_exc()}"
        )


# ============================================================================
# MODEL MANAGEMENT
# ============================================================================

@router.get("/models")
async def list_models():
    """
    List all available models
    Returns a list of all models available in Ollama
    """
    try:
        manager = get_manager()
        models = manager.list_models()
        
        # Ensure all models are JSON-serializable
        serializable_models = [serialize_model(m) for m in models]
        
        return JSONResponse({
            "status": "success",
            "models": serializable_models,
            "count": len(serializable_models)
        })
    
    except Exception as e:
        import traceback
        print(f"[Ollama API] Error in list_models: {e}")
        traceback.print_exc()
        
        return JSONResponse({
            "status": "error",
            "error": str(e),
            "models": [],
            "count": 0
        }, status_code=500)


@router.get("/models/{model_name}/info")
async def get_model_info(model_name: str, force_refresh: bool = False):
    """Get detailed information about a specific model"""
    try:
        manager = get_manager()
        
        # Get metadata (different methods for different managers)
        if hasattr(manager, 'get_model_metadata'):
            model_info = manager.get_model_metadata(model_name, force_refresh=force_refresh)
            
            # Check if it's a dict or object
            if isinstance(model_info, dict):
                # Multi-instance manager returns dict
                return JSONResponse({
                    "status": "success",
                    "model": model_info
                })
            else:
                # Old manager returns OllamaModelInfo object
                return JSONResponse({
                    "status": "success",
                    "model": {
                        "name": model_info.name,
                        "size": model_info.size,
                        "format": model_info.format,
                        "family": model_info.family,
                        "parameter_size": model_info.parameter_size,
                        "quantization_level": model_info.quantization_level,
                        "context_length": model_info.context_length,
                        "embedding_length": model_info.embedding_length,
                        "capabilities": model_info.capabilities,
                        "license": model_info.license,
                        "modified_at": model_info.modified_at,
                        "temperature": model_info.temperature,
                        "top_k": model_info.top_k,
                        "top_p": model_info.top_p,
                        "num_predict": model_info.num_predict,
                        "supports_thought": model_info.supports_thought,
                        "supports_streaming": model_info.supports_streaming,
                        "supports_vision": model_info.supports_vision
                    }
                })
        else:
            raise HTTPException(status_code=501, detail="Model metadata not supported by this manager")
    
    except Exception as e:
        import traceback
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to get model info: {str(e)}\n{traceback.format_exc()}"
        )


@router.post("/models/pull")
async def pull_model(model_name: str, stream: bool = True):
    """Pull/download a model"""
    try:
        manager = get_manager()
        success = manager.pull_model(model_name, stream=stream)
        
        if success:
            return JSONResponse({
                "status": "success",
                "message": f"Model {model_name} pulled successfully",
                "model": model_name
            })
        else:
            raise HTTPException(status_code=500, detail="Model pull failed")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to pull model: {str(e)}")


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class GenerateRequest(BaseModel):
    """Request to generate text"""
    model: str
    prompt: str
    temperature: Optional[float] = None
    top_k: Optional[int] = None
    top_p: Optional[float] = None
    num_predict: Optional[int] = None
    stream: bool = False
    system: Optional[str] = None
    stop: Optional[List[str]] = None


class ChatRequest(BaseModel):
    """Request for chat completion"""
    model: str
    messages: List[Dict[str, str]]
    temperature: Optional[float] = None
    stream: bool = False


class EmbeddingRequest(BaseModel):
    """Request for embeddings"""
    model: str
    text: str


# ============================================================================
# TEXT GENERATION
# ============================================================================

@router.post("/generate")
async def generate_text(request: GenerateRequest):
    """Generate text using a model"""
    try:
        manager = get_manager()
        
        # Build parameters
        kwargs = {}
        if request.temperature is not None:
            kwargs['temperature'] = request.temperature
        if request.top_k is not None:
            kwargs['top_k'] = request.top_k
        if request.top_p is not None:
            kwargs['top_p'] = request.top_p
        if request.num_predict is not None:
            kwargs['num_predict'] = request.num_predict
        
        # Create LLM
        llm = manager.create_llm(request.model, **kwargs)
        
        if request.stream:
            # Stream response
            async def stream_generator():
                try:
                    for chunk in llm.stream(request.prompt):
                        # Extract text from chunk
                        if hasattr(chunk, 'text'):
                            chunk_text = chunk.text
                        elif isinstance(chunk, str):
                            chunk_text = chunk
                        else:
                            chunk_text = str(chunk)
                        
                        yield f"data: {json.dumps({'text': chunk_text})}\n\n"
                    
                    yield "data: [DONE]\n\n"
                
                except Exception as e:
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
            
            return StreamingResponse(
                stream_generator(),
                media_type="text/event-stream"
            )
        else:
            # Non-streaming response
            response_text = llm.invoke(request.prompt)
            
            return JSONResponse({
                "status": "success",
                "model": request.model,
                "response": response_text
            })
    
    except Exception as e:
        import traceback
        raise HTTPException(
            status_code=500, 
            detail=f"Generation failed: {str(e)}\n{traceback.format_exc()}"
        )


# ============================================================================
# EMBEDDINGS
# ============================================================================

@router.post("/embeddings")
async def create_embeddings(request: EmbeddingRequest):
    """Create embeddings for text"""
    try:
        manager = get_manager()
        embeddings = manager.create_embeddings(request.model)
        vector = embeddings.embed_query(request.text)
        
        return JSONResponse({
            "status": "success",
            "model": request.model,
            "embedding": vector,
            "dimension": len(vector)
        })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding failed: {str(e)}")


# ============================================================================
# INSTANCE MANAGEMENT (Multi-Instance Only)
# ============================================================================

@router.get("/instances")
async def get_instances():
    """Get information about all Ollama instances (multi-instance only)"""
    try:
        manager = get_manager()
        
        if not hasattr(manager, 'get_pool_stats'):
            return JSONResponse({
                "status": "not_available",
                "message": "Instance management only available with MultiInstanceOllamaManager"
            })
        
        pool_stats = manager.get_pool_stats()
        
        return JSONResponse({
            "status": "success",
            "instances": pool_stats,
            "count": len(pool_stats)
        })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get instances: {str(e)}")


@router.get("/instances/{instance_name}/stats")
async def get_instance_stats(instance_name: str):
    """Get statistics for a specific instance"""
    try:
        manager = get_manager()
        
        if not hasattr(manager, 'get_pool_stats'):
            raise HTTPException(
                status_code=501, 
                detail="Instance stats only available with MultiInstanceOllamaManager"
            )
        
        pool_stats = manager.get_pool_stats()
        
        if instance_name not in pool_stats:
            raise HTTPException(status_code=404, detail=f"Instance '{instance_name}' not found")
        
        return JSONResponse({
            "status": "success",
            "instance": instance_name,
            "stats": pool_stats[instance_name]
        })
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get instance stats: {str(e)}")


# ============================================================================
# UTILITY ENDPOINTS
# ============================================================================

@router.get("/config")
async def get_ollama_config():
    """Get current Ollama configuration"""
    try:
        manager = get_manager()
        
        config_data = {
            "manager_type": type(manager).__name__
        }
        
        # Add manager-specific config
        if hasattr(manager, 'api_url'):
            config_data["api_url"] = manager.api_url
        if hasattr(manager, 'timeout'):
            config_data["timeout"] = manager.timeout
        if hasattr(manager, 'config'):
            if hasattr(manager.config, 'use_local_fallback'):
                config_data["use_local_fallback"] = manager.config.use_local_fallback
            if hasattr(manager.config, 'load_balance_strategy'):
                config_data["load_balance_strategy"] = manager.config.load_balance_strategy
        
        return JSONResponse({
            "status": "success",
            "config": config_data
        })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Config retrieval failed: {str(e)}")


@router.post("/test-generation")
async def test_generation(model: str, prompt: str = "Hello, how are you?"):
    """Quick test endpoint for model generation"""
    try:
        manager = get_manager()
        llm = manager.create_llm(model)
        
        import time
        start_time = time.time()
        response = llm.invoke(prompt)
        duration = time.time() - start_time
        
        return JSONResponse({
            "status": "success",
            "model": model,
            "prompt": prompt,
            "response": response,
            "duration_seconds": round(duration, 2),
            "tokens_per_second": round(len(response.split()) / duration, 2) if duration > 0 else 0
        })
    
    except Exception as e:
        import traceback
        raise HTTPException(
            status_code=500, 
            detail=f"Test failed: {str(e)}\n{traceback.format_exc()}"
        )

from pydantic import BaseModel
from typing import List, Optional

class ModelSyncRequest(BaseModel):
    source_instance: str
    target_instances: Optional[List[str]] = None
    models: Optional[List[str]] = None
    force: bool = False
    dry_run: bool = False


class ModelCopyRequest(BaseModel):
    model_name: str
    from_instance: str
    to_instance: str
    force: bool = False


@router.get("/instances/compare")
async def compare_instances():
    """Compare models across all instances"""
    try:
        manager = get_manager()
        
        if not hasattr(manager, 'compare_instances'):
            raise HTTPException(
                status_code=501,
                detail="Model comparison only available with MultiInstanceOllamaManager"
            )
        
        comparison = manager.compare_instances()
        
        return JSONResponse({
            "status": "success",
            **comparison
        })
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        raise HTTPException(
            status_code=500,
            detail=f"Comparison failed: {str(e)}\n{traceback.format_exc()}"
        )


@router.get("/instances/{instance_name}/models")
async def get_instance_models(instance_name: str):
    """Get models for a specific instance"""
    try:
        manager = get_manager()
        
        if not hasattr(manager, 'list_models_by_instance'):
            raise HTTPException(
                status_code=501,
                detail="Per-instance model listing only available with MultiInstanceOllamaManager"
            )
        
        models_by_instance = manager.list_models_by_instance()
        
        if instance_name not in models_by_instance:
            raise HTTPException(
                status_code=404,
                detail=f"Instance '{instance_name}' not found or unhealthy"
            )
        
        return JSONResponse({
            "status": "success",
            "instance": instance_name,
            "models": models_by_instance[instance_name],
            "count": len(models_by_instance[instance_name])
        })
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# In Vera/ChatUI/api/Orchestrator/ollama_api.py

@router.post("/models/copy")
async def copy_model(request: ModelCopyRequest):
    """Copy a single model between instances with detailed error reporting"""
    try:
        manager = get_manager()
        
        if not hasattr(manager, 'copy_model'):
            raise HTTPException(
                status_code=501,
                detail="Model copying only available with MultiInstanceOllamaManager"
            )
        
        # First, analyze the source model
        if hasattr(manager, 'analyze_model_dependencies'):
            analysis = manager.analyze_model_dependencies(
                request.model_name, 
                request.from_instance
            )
            
            if "error" in analysis:
                return JSONResponse(
                    {
                        "error": analysis["error"],
                        "model": request.model_name
                    }, 
                    status_code=400
                )
            
            # Log the analysis
            print(f"[Ollama API] Model analysis for {request.model_name}:")
            print(f"  Base model: {analysis['dependencies']['base_model']}")
            print(f"  Adapters: {analysis['dependencies']['adapters']}")
            print(f"  Parameters: {analysis['dependencies']['parameters']}")
        
        # Attempt the copy
        result = manager.copy_model(
            request.model_name,
            request.from_instance,
            request.to_instance,
            force=request.force
        )
        
        if "error" in result:
            return JSONResponse(
                {
                    **result,
                    "model": request.model_name,
                    "from": request.from_instance,
                    "to": request.to_instance
                }, 
                status_code=400
            )
        
        return JSONResponse(result)
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"[Ollama API] Copy error:\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Copy failed: {str(e)}\n{traceback.format_exc()}"
        )


@router.get("/models/{model_name}/analyze")
async def analyze_model(model_name: str, instance: str):
    """Analyze a model's dependencies"""
    try:
        manager = get_manager()
        
        if not hasattr(manager, 'analyze_model_dependencies'):
            raise HTTPException(
                status_code=501,
                detail="Model analysis only available with MultiInstanceOllamaManager"
            )
        
        result = manager.analyze_model_dependencies(model_name, instance)
        
        if "error" in result:
            return JSONResponse(result, status_code=400)
        
        return JSONResponse(result)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/models/sync")
async def sync_models(request: ModelSyncRequest):
    """Sync models from source to target instances"""
    try:
        manager = get_manager()
        
        if not hasattr(manager, 'sync_models'):
            raise HTTPException(
                status_code=501,
                detail="Model syncing only available with MultiInstanceOllamaManager"
            )
        
        result = manager.sync_models(
            source_instance=request.source_instance,
            target_instances=request.target_instances,
            models=request.models,
            force=request.force,
            dry_run=request.dry_run
        )
        
        if "error" in result:
            return JSONResponse(result, status_code=400)
        
        return JSONResponse(result)
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        raise HTTPException(
            status_code=500,
            detail=f"Sync failed: {str(e)}\n{traceback.format_exc()}"
        )

        