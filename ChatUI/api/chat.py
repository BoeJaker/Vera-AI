import asyncio
import json
import uuid
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from threading import Thread
from queue import Queue
from typing import Any, Dict, List
import logging
from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect,
    HTTPException,
    UploadFile,
    File,
)

from state import vera_instances, sessions, toolchain_executions, active_toolchains, websocket_connections
from session import get_or_create_vera

# ============================================================
# Logging setup
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# Router setup
# ============================================================
router = APIRouter(tags=["chat"])
wsrouter = APIRouter(prefix="/ws/chat", tags=["wschat"])

async def get_enhanced_context(vera, session_id: str, message: str, k: int = 5) -> Dict[str, Any]:
    """
    Get enhanced context using hybrid retrieval for chat responses.
    """
    try:
        # Session-specific vector retrieval
        session_context = vera.mem.focus_context(session_id, message, k=k)
        
        # Long-term semantic retrieval
        long_term_context = vera.mem.semantic_retrieve(message, k=k)
        
        # Extract entity IDs for graph context
        entity_ids = set()
        for hit in session_context + long_term_context:
            metadata = hit.get("metadata", {})
            if "entity_ids" in metadata:
                entity_ids.update(metadata["entity_ids"])
            if metadata.get("type") == "extracted_entity":
                entity_ids.add(hit["id"])
        
        # Get graph context if entities found
        graph_context = None
        if entity_ids:
            graph_context = vera.mem.extract_subgraph(list(entity_ids)[:3], depth=1)
        
        return {
            "session_context": session_context,
            "long_term_context": long_term_context,
            "graph_context": graph_context,
            "entity_ids": list(entity_ids)
        }
    except Exception as e:
        logger.error(f"Error getting enhanced context: {e}")
        return {
            "session_context": [],
            "long_term_context": [],
            "graph_context": None,
            "entity_ids": []
        }

# ============================================================
# Chat Endpoints 
# ============================================================

@router.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Process a chat message."""
    if request.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(request.session_id)
    
    try:
        sessions[request.session_id]["messages"].append({
            "role": "user",
            "content": request.message,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        from concurrent.futures import ThreadPoolExecutor
        
        def process_message():
            return vera.run(request.message)
        
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(executor, process_message)
        
        if isinstance(result, dict):
            response_text = result.get("output", str(result))
        else:
            response_text = str(result)
        
        sessions[request.session_id]["messages"].append({
            "role": "assistant",
            "content": response_text,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        return ChatResponse(
            response=response_text,
            session_id=request.session_id,
            timestamp=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@wsrouter.websocket("/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for streaming chat - works with sync generators."""
    await websocket.accept()
    
    if session_id not in sessions:
        await websocket.close(code=4004, reason="Session not found")
        return
    
    vera = get_or_create_vera(session_id)
    
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            message = message_data.get("message", "")
            
            if not message:
                await websocket.send_json({"type": "error", "error": "Empty message"})
                continue
            
            try:
                if hasattr(vera, 'async_run') and callable(getattr(vera, 'async_run')):
                    logger.info("Using vera.async_run() for streaming")
                    
                    chunk_queue = Queue()
                    error_occurred = [False]
                    
                    def run_in_thread():
                        try:
                            for chunk in vera.async_run(message):
                                chunk_queue.put(("chunk", chunk))
                            chunk_queue.put(("done", None))
                        except Exception as e:
                            logger.error(f"Error in vera.async_run: {e}", exc_info=True)
                            chunk_queue.put(("error", str(e)))
                            error_occurred[0] = True
                    
                    thread = Thread(target=run_in_thread, daemon=True)
                    thread.start()
                    
                    while True:
                        try:
                            item_type, item_data = await asyncio.get_event_loop().run_in_executor(
                                None, chunk_queue.get, True, 0.1
                            )
                            
                            if item_type == "chunk":
                                await websocket.send_json({
                                    "type": "chunk",
                                    "content": str(item_data),
                                    "timestamp": datetime.utcnow().isoformat()
                                })
                            elif item_type == "done":
                                break
                            elif item_type == "error":
                                await websocket.send_json({
                                    "type": "error",
                                    "error": item_data
                                })
                                break
                                
                        except Exception as e:
                            if not thread.is_alive() and chunk_queue.empty():
                                break
                            continue
                    
                    thread.join(timeout=1.0)
                    
                    if not error_occurred[0]:
                        await websocket.send_json({
                            "type": "complete",
                            "timestamp": datetime.utcnow().isoformat()
                        })
                
                else:
                    logger.info("Falling back to vera.run() - no streaming")
                    result = await asyncio.get_event_loop().run_in_executor(
                        None, vera.run, message
                    )
                    
                    if isinstance(result, dict):
                        response = result.get("deep") or result.get("fast") or result.get("output", str(result))
                    else:
                        response = str(result)
                    
                    await websocket.send_json({
                        "type": "chunk",
                        "content": response,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    
                    await websocket.send_json({
                        "type": "complete",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}", exc_info=True)
                await websocket.send_json({
                    "type": "error",
                    "error": str(e)
                })
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}", exc_info=True)

# ============================================================
# Text-to-Speech Endpoints
# ============================================================

@router.post("/api/tts")
async def text_to_speech(request: TTSRequest):
    """Add text to TTS queue."""
    global tts_queue
    
    tts_item = {
        "id": str(uuid.uuid4()),
        "text": request.text,
        "lang": request.lang,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    tts_queue.append(tts_item)
    logger.info(f"Added to TTS queue: {request.text[:50]}...")
    
    return {
        "status": "queued",
        "queue_length": len(tts_queue)
    }


@router.post("/api/tts/stop")
async def stop_tts():
    """Stop current TTS playback."""
    global tts_playing
    tts_playing = False
    
    return {"status": "stopped"}


@router.post("/api/tts/queue/clear")
async def clear_tts_queue():
    """Clear the TTS queue."""
    global tts_queue
    tts_queue.clear()
    
    return {"status": "cleared", "queue_length": 0}


@router.get("/api/tts/queue")
async def get_tts_queue():
    """Get current TTS queue."""
    return {
        "queue": tts_queue,
        "playing": tts_playing,
        "queue_length": len(tts_queue)
    }


# ============================================================
# File Upload Endpoints
# ============================================================

@router.post("/api/files/upload/{session_id}")
async def upload_files(session_id: str, files: List[UploadFile] = File(...)):
    """Upload files for a session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    uploaded = []
    
    for file in files:
        try:
            content = await file.read()
            
            # Store file metadata
            sessions[session_id]["files"][file.filename] = {
                "filename": file.filename,
                "size": len(content),
                "content_type": file.content_type,
                "uploaded_at": datetime.utcnow().isoformat()
            }
            
            uploaded.append({
                "filename": file.filename,
                "size": len(content)
            })
            
            logger.info(f"Uploaded file: {file.filename} ({len(content)} bytes)")
            
        except Exception as e:
            logger.error(f"File upload error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to upload {file.filename}")
    
    return {
        "status": "success",
        "uploaded": uploaded,
        "total": len(uploaded)
    }


@router.get("/api/files/{session_id}")
async def list_files(session_id: str):
    """List files for a session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "files": list(sessions[session_id]["files"].values())
    }


@router.delete("/api/files/{session_id}/{filename}")
async def delete_file(session_id: str, filename: str):
    """Delete a file from a session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if filename not in sessions[session_id]["files"]:
        raise HTTPException(status_code=404, detail="File not found")
    
    sessions[session_id]["files"].pop(filename)
    
    return {"status": "deleted", "filename": filename}
