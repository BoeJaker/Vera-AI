"""
Vera API Endpoints using FastAPI
Compatible with the frontend chat interface
"""

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import json
import asyncio
import uuid
from datetime import datetime
import logging

# Import your existing modules
from vera import Vera
from Memory.memory import HybridMemory

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Vera AI Chat API",
    description="Multi-agent AI chat system with knowledge graph visualization",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global storage
vera_instances: Dict[str, Vera] = {}
sessions: Dict[str, Dict[str, Any]] = {}
tts_queue: List[Dict[str, Any]] = []
tts_playing = False


# ============================================================
# Request/Response Models
# ============================================================

class SessionStartResponse(BaseModel):
    session_id: str
    status: str = "started"
    timestamp: str


class ChatRequest(BaseModel):
    session_id: str
    message: str
    files: Optional[List[str]] = []


class ChatResponse(BaseModel):
    response: str
    session_id: str
    timestamp: str


class TTSRequest(BaseModel):
    text: str
    lang: str = "en"


class GraphNode(BaseModel):
    id: str
    label: str
    title: str
    color: str = "#3b82f6"
    properties: Dict[str, Any]
    size: int = 25


class GraphEdge(BaseModel):
    from_node: str = Field(..., alias="from")
    to_node: str = Field(..., alias="to")
    label: str
    
    class Config:
        populate_by_name = True


class GraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    stats: Dict[str, Any]


# ============================================================
# Helper Functions
# ============================================================

def get_or_create_vera(session_id: str) -> Vera:
    """Get or create a Vera instance for a session."""
    if session_id not in vera_instances:
        # This should not happen if session was properly created
        logger.warning(f"Vera instance not found for session {session_id}, creating new one")
        # Note: This will fail in async context, session should be created via /api/session/start
        raise HTTPException(
            status_code=400, 
            detail="Session not properly initialized. Please start a new session."
        )
    return vera_instances[session_id]


# ============================================================
# Session Management
# ============================================================

@app.post("/api/session/start", response_model=SessionStartResponse)
async def start_session():
    """Start a new chat session."""
    try:
        # Create Vera instance in thread to avoid async conflict
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        
        def create_vera():
            return Vera()
        
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            vera = await loop.run_in_executor(executor, create_vera)
        
        # Use Vera's actual session ID
        session_id = vera.sess.id
        vera_instances[session_id] = vera
        
        # Initialize session data
        sessions[session_id] = {
            "created_at": datetime.utcnow().isoformat(),
            "messages": [],
            "files": {},
            "vera": vera
        }
        
        logger.info(f"Started session: {session_id}")
        
        return SessionStartResponse(
            session_id=session_id,
            status="started",
            timestamp=datetime.utcnow().isoformat()
        )
    except Exception as e:
        logger.error(f"Session start error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start session: {str(e)}")


@app.post("/api/session/{session_id}/end")
async def end_session(session_id: str):
    """End a chat session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Cleanup
    vera_instances.pop(session_id, None)
    sessions.pop(session_id, None)
    
    return {"status": "ended", "session_id": session_id}


# ============================================================
# Chat Endpoints
# ============================================================

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Process a chat message."""
    if request.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(request.session_id)
    
    try:
        # Store user message
        sessions[request.session_id]["messages"].append({
            "role": "user",
            "content": request.message,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Process with Vera in thread to avoid async conflicts
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        
        def process_message():
            return vera.run(request.message)
        
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(executor, process_message)
        
        # Extract response text
        if isinstance(result, dict):
            response_text = result.get("output", str(result))
        else:
            response_text = str(result)
        
        # Store assistant response
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

import asyncio
from queue import Queue
from threading import Thread
from datetime import datetime

@app.websocket("/ws/chat/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for streaming chat - works with sync generators."""
    await websocket.accept()
    
    if session_id not in sessions:
        await websocket.close(code=4004, reason="Session not found")
        return
    
    vera = get_or_create_vera(session_id)
    
    try:
        while True:
            # Receive message
            data = await websocket.receive_text()
            message_data = json.loads(data)
            message = message_data.get("message", "")
            
            if not message:
                await websocket.send_json({"type": "error", "error": "Empty message"})
                continue
            
            # Process and stream response
            try:
                if hasattr(vera, 'async_run') and callable(getattr(vera, 'async_run')):
                    logger.info("Using vera.async_run() for streaming")
                    
                    # Create a queue to pass chunks from sync thread to async handler
                    chunk_queue = Queue()
                    error_occurred = [False]  # Mutable container for error flag
                    
                    def run_in_thread():
                        """Run the synchronous generator in a separate thread."""
                        try:
                            for chunk in vera.async_run(message):
                                chunk_queue.put(("chunk", chunk))
                            chunk_queue.put(("done", None))
                        except Exception as e:
                            logger.error(f"Error in vera.async_run: {e}", exc_info=True)
                            chunk_queue.put(("error", str(e)))
                            error_occurred[0] = True
                    
                    # Start the generator in a background thread
                    thread = Thread(target=run_in_thread, daemon=True)
                    thread.start()
                    
                    # Read from queue and send to websocket
                    while True:
                        # Non-blocking check for queue items
                        try:
                            # Wait briefly for queue item (allows cancellation)
                            item_type, item_data = await asyncio.get_event_loop().run_in_executor(
                                None, chunk_queue.get, True, 0.1  # timeout=0.1s
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
                            # Queue timeout - check if thread is still alive
                            if not thread.is_alive() and chunk_queue.empty():
                                break
                            continue
                    
                    # Wait for thread to finish
                    thread.join(timeout=1.0)
                    
                    if not error_occurred[0]:
                        await websocket.send_json({
                            "type": "complete",
                            "timestamp": datetime.utcnow().isoformat()
                        })
                
                else:
                    # Fallback to regular run()
                    logger.info("Falling back to vera.run() - no streaming")
                    result = await asyncio.get_event_loop().run_in_executor(
                        None, vera.run, message
                    )
                    
                    # Extract response text
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
        try:
            await websocket.send_json({
                "type": "error",
                "error": f"WebSocket error: {str(e)}"
            })
        except:
            pass
        
# ============================================================
# Graph Endpoints
# ============================================================
# ============================================================
# Graph Endpoints
# ============================================================
@app.get("/api/graph/session/{session_id}", response_model=GraphResponse)
async def get_session_graph(session_id: str):
    """Get the knowledge graph for a session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    actual_session_id = vera.sess.id
    
    try:
        driver = vera.mem.graph._driver
        
        with driver.session() as db_sess:
            # Get all nodes matching session_id and connected nodes within 3 hops
            result = db_sess.run("""
                MATCH (n)
                WHERE n.session_id = $session_id OR n.extracted_from_session = $session_id
                OPTIONAL MATCH path = (n)-[r*0..3]-(connected)
                WITH collect(DISTINCT connected) + collect(DISTINCT n) AS nodes,
                     collect(DISTINCT relationships(path)) AS rels
                UNWIND rels AS rel_list
                UNWIND rel_list AS rel
                RETURN DISTINCT nodes, collect(DISTINCT rel) AS relationships
            """, {"session_id": actual_session_id})
            
            nodes_list = []
            edges = []
            seen_nodes = set()
            seen_edges = set()
            
            # Process the query results
            for record in result:
                # Process all nodes
                all_nodes = record.get("nodes", [])
                for node in all_nodes:
                    if node and node.get("id"):
                        node_id = node.get("id", "")
                        if node_id and node_id not in seen_nodes:
                            seen_nodes.add(node_id)
                            
                            properties = dict(node)
                            logger.debug(properties)
                            text = properties.get("text", properties.get("name", node_id))
                            node_type = properties.get("type", "node")
                            
                            # Determine color based on type
                            color = "#3b82f6"  # Default blue
                            if node_type in ["thought", "memory", "Thought","Memory"]:
                                color = "#f59e0b"  # Orange
                            elif node_type in ["decision", "Decision"]:
                                color = "#ef4444"  # Red
                            elif node_type in ["class", "Class"]:
                                color = "#2d8cf0"  # Blue
                            elif node_type in ["Action", "action"]:
                                color = "#8b5cf6"  # Purple
                            elif node_type in ["Tool", "tool"]:
                                color = "#f97316"  # Deep Orange  
                            elif node_type in ["Process", "process"]:
                                color = "#e879f9"  # Pink
                            elif node_type in ["File", "file"]:
                                color = "#f43f5e"  # Rose
                            elif node_type in ["Webpage", "webpage"]:
                                color = "#60a5fa"  # Light Blue
                            elif node_type in ["Document", "document"]:
                                color = "#34d399"  # Emerald
                            elif node_type in ["Query", "query"]:
                                color = "#32B39D"  # Turquoise
                            elif node_type == "extracted_entity":
                                color = "#07c3e4"  # Cyan
                            elif node_type == "session":
                                color = "#3f1b92"  # Purple
                            elif "Entity" in properties.get("labels", []):
                                color = "#10b93a"  # Green

                            
                            nodes_list.append(GraphNode(
                                id=node_id,
                                label=node_type,
                                title=f"{node_type}: {text}",
                                color=node.get("color",color),
                                properties=properties,
                                size=min(properties.get("importance", 20), 40)
                            ))
                
                # Process all relationships
                all_relationships = record.get("relationships", [])
                for rel in all_relationships:
                    if rel:
                        try:
                            # Get source and target nodes
                            start_node = rel.start_node
                            end_node = rel.end_node
                            
                            start_id = start_node.get("id", "") if start_node else ""
                            end_id = end_node.get("id", "") if end_node else ""
                            
                            if start_id and end_id:
                                # Get relationship label
                                rel_props = dict(rel) if hasattr(rel, 'items') else {}
                                rel_label = rel_props.get("rel", getattr(rel, "type", "RELATED"))
                                
                                edge_key = f"{start_id}-{rel_label}->{end_id}"
                                if edge_key not in seen_edges:
                                    seen_edges.add(edge_key)
                                    edges.append(GraphEdge(
                                        **{
                                            "from": start_id,
                                            "to": end_id,
                                            "label": str(rel_label)
                                        }
                                    ))
                        except Exception as e:
                            logger.debug(f"Error processing relationship: {e}")
                            continue
            
            logger.info(f"Returning {len(nodes_list)} nodes and {len(edges)} edges for session {actual_session_id}")
            
            return GraphResponse(
                nodes=nodes_list,
                edges=edges,
                stats={
                    "node_count": len(nodes_list),
                    "edge_count": len(edges),
                    "session_id": actual_session_id
                }
            )
            
    except Exception as e:
        logger.error(f"Graph error: {str(e)}", exc_info=True)
        # Return minimal graph with session node only
        return GraphResponse(
            nodes=[GraphNode(
                id=actual_session_id,
                label=f"Session {actual_session_id[-8:]}",
                title=f"Session: {actual_session_id}",
                properties={},
                color="#8b5cf6",
                size=30
            )],
            edges=[],
            stats={"node_count": 1, "edge_count": 0, "session_id": actual_session_id}
        )
    
# ============================================================
# Text-to-Speech Endpoints
# ============================================================

@app.post("/api/tts")
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


@app.post("/api/tts/stop")
async def stop_tts():
    """Stop current TTS playback."""
    global tts_playing
    tts_playing = False
    
    return {"status": "stopped"}


@app.post("/api/tts/queue/clear")
async def clear_tts_queue():
    """Clear the TTS queue."""
    global tts_queue
    tts_queue.clear()
    
    return {"status": "cleared", "queue_length": 0}


@app.get("/api/tts/queue")
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

@app.post("/api/files/upload/{session_id}")
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


@app.get("/api/files/{session_id}")
async def list_files(session_id: str):
    """List files for a session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "files": list(sessions[session_id]["files"].values())
    }


@app.delete("/api/files/{session_id}/{filename}")
async def delete_file(session_id: str, filename: str):
    """Delete a file from a session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if filename not in sessions[session_id]["files"]:
        raise HTTPException(status_code=404, detail="File not found")
    
    sessions[session_id]["files"].pop(filename)
    
    return {"status": "deleted", "filename": filename}


# ============================================================
# Health and Info
# ============================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "active_sessions": len(sessions),
        "tts_queue_length": len(tts_queue)
    }


@app.get("/api/info")
async def get_info():
    """Get API information."""
    return {
        "name": "Vera AI Chat API",
        "version": "1.0.0",
        "active_sessions": len(sessions),
        "endpoints": {
            "session": ["/api/session/start", "/api/session/{id}/end"],
            "chat": ["/api/chat", "/ws/chat/{session_id}"],
            "graph": ["/api/graph/session/{session_id}"],
            "tts": ["/api/tts", "/api/tts/stop", "/api/tts/queue/clear"],
            "files": ["/api/files/upload/{session_id}", "/api/files/{session_id}"]
        }
    }


@app.get("/api/debug/neo4j/{session_id}")
async def debug_neo4j(session_id: str):
    """Debug endpoint to see what's in Neo4j for a session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    actual_session_id = vera.sess.id
    
    try:
        driver = vera.mem.graph._driver
        
        with driver.session() as db_sess:
            # Get session node
            session_result = db_sess.run("""
                MATCH (s:Session {id: $session_id})
                RETURN s, labels(s) AS labels
            """, {"session_id": actual_session_id})
            
            session_info = []
            for record in session_result:
                session_info.append({
                    "node": dict(record["s"]),
                    "labels": record["labels"]
                })
            
            # Get directly connected nodes
            connected_result = db_sess.run("""
                MATCH (s:Session {id: $session_id})-[r]-(n)
                RETURN n.id AS id, labels(n) AS labels, n.type AS type, 
                       n.text AS text, type(r) AS rel_type, 
                       startNode(r).id AS start_id, endNode(r).id AS end_id
                LIMIT 100
            """, {"session_id": actual_session_id})
            
            directly_connected = []
            for record in connected_result:
                directly_connected.append({
                    "id": record["id"],
                    "labels": record["labels"],
                    "type": record["type"],
                    "text": record["text"][:100] if record["text"] else None,
                    "rel_type": record["rel_type"],
                    "start_id": record["start_id"],
                    "end_id": record["end_id"]
                })
            
            # Get all nodes (sample)
            all_nodes_result = db_sess.run("""
                MATCH (n)
                RETURN n.id AS id, labels(n) AS labels, n.type AS type, n.text AS text
                LIMIT 50
            """)
            
            all_nodes = []
            for record in all_nodes_result:
                all_nodes.append({
                    "id": record["id"],
                    "labels": record["labels"],
                    "type": record["type"],
                    "text": record["text"][:100] if record["text"] else None
                })
            
            # Get all relationships (sample)
            all_rels_result = db_sess.run("""
                MATCH (a)-[r]->(b)
                RETURN a.id AS from, type(r) AS rel_type, 
                       properties(r) AS rel_props, b.id AS to
                LIMIT 100
            """)
            
            all_rels = []
            for record in all_rels_result:
                all_rels.append({
                    "from": record["from"],
                    "rel_type": record["rel_type"],
                    "rel_props": record["rel_props"],
                    "to": record["to"]
                })
            
            # Check for FOLLOWS chain
            follows_result = db_sess.run("""
                MATCH (a)-[r:REL {rel: 'FOLLOWS'}]->(b)
                RETURN a.id AS from, a.text AS from_text, b.id AS to, b.text AS to_text
                LIMIT 50
            """)
            
            follows_chain = []
            for record in follows_result:
                follows_chain.append({
                    "from": record["from"],
                    "from_text": record["from_text"][:50] if record["from_text"] else None,
                    "to": record["to"],
                    "to_text": record["to_text"][:50] if record["to_text"] else None
                })
            
            return {
                "session_id": actual_session_id,
                "session_nodes": session_info,
                "directly_connected_to_session": directly_connected,
                "follows_chain": follows_chain,
                "all_nodes_sample": all_nodes,
                "all_relationships_sample": all_rels,
                "summary": {
                    "session_found": len(session_info) > 0,
                    "direct_connections": len(directly_connected),
                    "follows_count": len(follows_chain),
                    "total_nodes_sample": len(all_nodes),
                    "total_relationships_sample": len(all_rels)
                }
            }
    
    except Exception as e:
        logger.error(f"Debug error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Run Server
# ============================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8888,
        log_level="info"
    )