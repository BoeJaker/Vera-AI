"""
Ollama API Router for Vera
Exposes Ollama manager functionality through REST endpoints
"""

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import asyncio
import json
from datetime import datetime

# Import the Ollama manager
from Vera.Ollama.manager import OllamaConnectionManager, OllamaModelInfo

router = APIRouter(prefix="/api/ollama", tags=["ollama"])

# Global manager instance (initialized on first use)
_manager: Optional[OllamaConnectionManager] = None


def get_manager() -> OllamaConnectionManager:
    """Get or create the global Ollama manager instance"""
    global _manager
    if _manager is None:
        try:
            # Try to import the configuration manager
            from Vera.Configuration.config_manager import ConfigManager
            config_mgr = ConfigManager()
            config = config_mgr.config.ollama
        except (ImportError, AttributeError) as e:
            print(f"[Ollama API] Could not load config manager: {e}")
            print("[Ollama API] Using default configuration")
            # Create a simple default config object
            class DefaultOllamaConfig:
                api_url = "http://localhost:11434"
                timeout = 2400
                use_local_fallback = True
                connection_retry_attempts = 3
                connection_retry_delay = 1.0
                enable_thought_capture = True
                temperature = 0.7
                top_k = 40
                top_p = 0.9
                num_predict = -1
                repeat_penalty = 1.1
                cache_model_metadata = True
                metadata_cache_ttl = 3600
            
            config = DefaultOllamaConfig()
        
        _manager = OllamaConnectionManager(config=config)
    return _manager


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

@router.get("/ping")
async def ping():
    """
    Simple ping endpoint to test if the router is working
    """
    return JSONResponse({
        "status": "ok",
        "message": "Ollama API router is running"
    })


class ModelMetadataResponse(BaseModel):
    """Model metadata response"""
    name: str
    size: int
    format: str
    family: str
    parameter_size: str
    quantization_level: str
    context_length: int
    embedding_length: int
    capabilities: List[str]
    license: str
    modified_at: str
    temperature: float
    top_k: int
    top_p: float
    num_predict: int
    supports_thought: bool
    supports_streaming: bool
    supports_vision: bool


class PullModelRequest(BaseModel):
    """Request to pull a model"""
    model_name: str
    stream: bool = True


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
# CONNECTION & STATUS
# ============================================================================

@router.get("/health")
async def health_check():
    """
    Check Ollama connection health
    
    Returns connection status and API availability
    """
    try:
        manager = get_manager()
        is_connected = manager.test_connection()
        
        return JSONResponse({
            "status": "healthy" if is_connected else "unhealthy",
            "connected": is_connected,
            "api_url": manager.api_url,
            "mode": "local" if manager.use_local else "api",
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


@router.get("/status")
async def get_status():
    """
    Get detailed Ollama status
    
    Returns comprehensive status including model count and configuration
    """
    try:
        manager = get_manager()
        
        # Test connection if not already done
        if not manager.connection_tested:
            manager.test_connection()
        
        # Get model count
        try:
            models = manager.list_models()
            model_count = len(models)
        except:
            model_count = 0
        
        return JSONResponse({
            "status": "success",
            "connected": manager.connection_tested,
            "mode": "local" if manager.use_local else "api",
            "api_url": manager.api_url,
            "timeout": manager.timeout,
            "model_count": model_count,
            "thought_capture_enabled": manager.thought_capture.enabled,
            "cache_size": len(manager.model_metadata_cache)
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")


@router.post("/reconnect")
async def reconnect():
    """
    Force reconnection to Ollama
    
    Resets connection state and tests again
    """
    try:
        manager = get_manager()
        manager.connection_tested = False
        manager.use_local = False
        
        is_connected = manager.test_connection()
        
        return JSONResponse({
            "status": "success",
            "connected": is_connected,
            "mode": "local" if manager.use_local else "api",
            "message": "Reconnection successful" if is_connected else "Reconnection failed"
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reconnect failed: {str(e)}")


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
        
        return JSONResponse({
            "status": "success",
            "models": models,
            "count": len(models)
        })
    except Exception as e:
        print(f"[Ollama API] Error in list_models: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to list models: {str(e)}")


@router.get("/models/{model_name}/info")
async def get_model_info(model_name: str, force_refresh: bool = False):
    """
    Get detailed information about a specific model
    
    Args:
        model_name: Name of the model
        force_refresh: Force refresh from API (ignore cache)
    
    Returns comprehensive model metadata
    """
    try:
        manager = get_manager()
        model_info = manager.get_model_metadata(model_name, force_refresh=force_refresh)
        
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get model info: {str(e)}")


@router.post("/models/pull")
async def pull_model(request: PullModelRequest):
    """
    Pull/download a model
    
    Downloads the specified model from Ollama registry
    """
    try:
        manager = get_manager()
        success = manager.pull_model(request.model_name, stream=request.stream)
        
        if success:
            return JSONResponse({
                "status": "success",
                "message": f"Model {request.model_name} pulled successfully",
                "model": request.model_name
            })
        else:
            raise HTTPException(status_code=500, detail="Model pull failed")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to pull model: {str(e)}")


@router.delete("/models/{model_name}")
async def delete_model(model_name: str):
    """
    Delete a model
    
    Removes the specified model from local storage
    """
    try:
        manager = get_manager()
        
        # Call Ollama API to delete
        import requests
        response = requests.delete(
            f"{manager.api_url}/api/delete",
            json={"name": model_name},
            timeout=10
        )
        
        if response.status_code == 200:
            # Clear from cache
            if model_name in manager.model_metadata_cache:
                del manager.model_metadata_cache[model_name]
            
            return JSONResponse({
                "status": "success",
                "message": f"Model {model_name} deleted successfully"
            })
        else:
            raise HTTPException(status_code=500, detail="Model deletion failed")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete model: {str(e)}")


@router.get("/models/capabilities")
async def get_models_by_capability():
    """
    Get models grouped by capabilities
    
    Returns models categorized by their features (thought, vision, etc.)
    """
    try:
        manager = get_manager()
        models = manager.list_models()
        
        capabilities = {
            "thought": [],
            "vision": [],
            "streaming": [],
            "embedding": []
        }
        
        for model in models:
            model_name = model.get('model', model.get('name', ''))
            if not model_name:
                continue
            
            try:
                info = manager.get_model_metadata(model_name)
                
                if info.supports_thought:
                    capabilities["thought"].append(model_name)
                if info.supports_vision:
                    capabilities["vision"].append(model_name)
                if info.supports_streaming:
                    capabilities["streaming"].append(model_name)
                if info.embedding_length > 0:
                    capabilities["embedding"].append(model_name)
            except:
                continue
        
        return JSONResponse({
            "status": "success",
            "capabilities": capabilities
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get capabilities: {str(e)}")


# ============================================================================
# TEXT GENERATION
# ============================================================================

@router.post("/generate")
async def generate_text(request: GenerateRequest):
    """
    Generate text using a model
    
    Supports both streaming and non-streaming responses
    """
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
        if request.system:
            kwargs['system'] = request.system
        if request.stop:
            kwargs['stop'] = request.stop
        
        # Create LLM
        llm = manager.create_llm(request.model, **kwargs)
        
        if request.stream:
            # Stream response
            async def stream_generator():
                try:
                    for chunk in llm.stream(request.prompt):
                        chunk_text = chunk.text if hasattr(chunk, 'text') else str(chunk)
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
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


@router.post("/chat")
async def chat_completion(request: ChatRequest):
    """
    Chat completion endpoint
    
    Handles multi-turn conversations with message history
    """
    try:
        manager = get_manager()
        
        # Build prompt from messages
        prompt = ""
        for msg in request.messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            
            if role == 'system':
                prompt = f"System: {content}\n\n" + prompt
            elif role == 'user':
                prompt += f"User: {content}\n"
            elif role == 'assistant':
                prompt += f"Assistant: {content}\n"
        
        prompt += "Assistant: "
        
        # Create LLM
        kwargs = {}
        if request.temperature is not None:
            kwargs['temperature'] = request.temperature
        
        llm = manager.create_llm(request.model, **kwargs)
        
        if request.stream:
            async def stream_generator():
                try:
                    for chunk in llm.stream(prompt):
                        chunk_text = chunk.text if hasattr(chunk, 'text') else str(chunk)
                        yield f"data: {json.dumps({'content': chunk_text})}\n\n"
                    yield "data: [DONE]\n\n"
                except Exception as e:
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
            
            return StreamingResponse(
                stream_generator(),
                media_type="text/event-stream"
            )
        else:
            response_text = llm.invoke(prompt)
            
            return JSONResponse({
                "status": "success",
                "model": request.model,
                "message": {
                    "role": "assistant",
                    "content": response_text
                }
            })
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


# ============================================================================
# EMBEDDINGS
# ============================================================================

@router.post("/embeddings")
async def create_embeddings(request: EmbeddingRequest):
    """
    Create embeddings for text
    
    Returns vector embeddings using the specified model
    """
    try:
        manager = get_manager()
        
        # Create embeddings
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


@router.post("/embeddings/batch")
async def create_batch_embeddings(model: str, texts: List[str]):
    """
    Create embeddings for multiple texts
    
    More efficient than calling /embeddings multiple times
    """
    try:
        manager = get_manager()
        
        # Create embeddings
        embeddings = manager.create_embeddings(model)
        vectors = embeddings.embed_documents(texts)
        
        return JSONResponse({
            "status": "success",
            "model": model,
            "embeddings": vectors,
            "count": len(vectors),
            "dimension": len(vectors[0]) if vectors else 0
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch embedding failed: {str(e)}")


# ============================================================================
# CACHE MANAGEMENT
# ============================================================================

@router.get("/cache/stats")
async def get_cache_stats():
    """
    Get metadata cache statistics
    
    Returns information about cached model metadata
    """
    try:
        manager = get_manager()
        
        cache_info = []
        for model_name, model_info in manager.model_metadata_cache.items():
            cache_info.append({
                "model": model_name,
                "context_length": model_info.context_length,
                "supports_thought": model_info.supports_thought,
                "supports_vision": model_info.supports_vision
            })
        
        return JSONResponse({
            "status": "success",
            "cache_size": len(manager.model_metadata_cache),
            "cached_models": cache_info
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cache stats failed: {str(e)}")


@router.post("/cache/clear")
async def clear_cache(model_name: Optional[str] = None):
    """
    Clear metadata cache
    
    Args:
        model_name: Specific model to clear, or None to clear all
    """
    try:
        manager = get_manager()
        
        if model_name:
            if model_name in manager.model_metadata_cache:
                del manager.model_metadata_cache[model_name]
                return JSONResponse({
                    "status": "success",
                    "message": f"Cleared cache for {model_name}"
                })
            else:
                raise HTTPException(status_code=404, detail=f"Model {model_name} not in cache")
        else:
            count = len(manager.model_metadata_cache)
            manager.model_metadata_cache.clear()
            return JSONResponse({
                "status": "success",
                "message": f"Cleared {count} cached models"
            })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cache clear failed: {str(e)}")


# ============================================================================
# WEBSOCKET FOR STREAMING
# ============================================================================

@router.websocket("/ws/generate")
async def websocket_generate(websocket: WebSocket):
    """
    WebSocket endpoint for streaming generation
    
    Allows real-time bidirectional communication for text generation
    """
    await websocket.accept()
    manager = get_manager()
    
    try:
        while True:
            # Receive request
            data = await websocket.receive_json()
            
            model = data.get('model')
            prompt = data.get('prompt')
            temperature = data.get('temperature')
            
            if not model or not prompt:
                await websocket.send_json({
                    "error": "Missing model or prompt"
                })
                continue
            
            try:
                # Create LLM
                kwargs = {}
                if temperature is not None:
                    kwargs['temperature'] = temperature
                
                llm = manager.create_llm(model, **kwargs)
                
                # Stream response
                await websocket.send_json({"status": "generating"})
                
                for chunk in llm.stream(prompt):
                    chunk_text = chunk.text if hasattr(chunk, 'text') else str(chunk)
                    await websocket.send_json({
                        "type": "chunk",
                        "text": chunk_text
                    })
                
                await websocket.send_json({"type": "done"})
                
            except Exception as e:
                await websocket.send_json({
                    "type": "error",
                    "error": str(e)
                })
    
    except WebSocketDisconnect:
        print("[Ollama WS] Client disconnected")
    except Exception as e:
        print(f"[Ollama WS] Error: {e}")
        try:
            await websocket.send_json({"error": str(e)})
        except:
            pass


# ============================================================================
# UTILITY ENDPOINTS
# ============================================================================

@router.get("/config")
async def get_ollama_config():
    """
    Get current Ollama configuration
    
    Returns the active configuration settings
    """
    try:
        manager = get_manager()
        
        return JSONResponse({
            "status": "success",
            "config": {
                "api_url": manager.api_url,
                "timeout": manager.timeout,
                "use_local_fallback": manager.config.use_local_fallback,
                "connection_retry_attempts": manager.config.connection_retry_attempts,
                "connection_retry_delay": manager.config.connection_retry_delay,
                "enable_thought_capture": manager.thought_capture.enabled,
                "temperature": manager.config.temperature,
                "top_k": manager.config.top_k,
                "top_p": manager.config.top_p,
                "num_predict": manager.config.num_predict
            }
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Config retrieval failed: {str(e)}")


@router.post("/test-generation")
async def test_generation(model: str, prompt: str = "Hello, how are you?"):
    """
    Quick test endpoint for model generation
    
    Useful for testing if a model works correctly
    """
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
        raise HTTPException(status_code=500, detail=f"Test failed: {str(e)}")


# ============================================================================
# Add to your main FastAPI app:
# ============================================================================
"""
from ollama_api import router as ollama_router

app = FastAPI()
app.include_router(ollama_router)
"""