"""
Vera API Endpoints using FastAPI - Enhanced with Toolchain Monitoring
Compatible with the frontend chat interface
""" 

# ============================================================
# Fast API imports
# ============================================================


from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

# ============================================================
# General imports
# ============================================================

from typing import List, Dict, Any
import json
import asyncio
import uuid
from datetime import datetime
import logging
from collections import defaultdict
from queue import Queue
from threading import Thread
from uuid import uuid4
from neo4j import GraphDatabase

# ============================================================
# Vera imports
# ============================================================

from Vera.vera import Vera
import Vera.ChatUI.api.Canvas.execution_api as execution_api
import Vera.ChatUI.api.Canvas.canvas_api as canvas_api # < to be replaced by execution_api
import Vera.ChatUI.api.vectorstore_api as vectorstore_api
import Vera.ChatUI.api.Toolchain.toolchain_api as toolchain_api
import Vera.ChatUI.api.Toolchain.toolchain_query_api as toolchain_query_api
import Vera.ChatUI.api.Toolchain.n8n_proxy as n8n_proxy
import Vera.ChatUI.api.Graph.graph_api as graph_api
import Vera.ChatUI.api.Chat.chat_api as chat_api
import Vera.ChatUI.api.Chat.chat_history_api as chat_history_api
import Vera.ChatUI.api.Orchestrator.orchestrator_api as orchestrator_api
import Vera.ChatUI.api.Orchestrator.api_api as api_api
import Vera.ChatUI.api.Orchestrator.infra_api as infra_api
import Vera.ChatUI.api.memory_api as memory_api
import Vera.ChatUI.api.proactivefocus_api as proactivefocus_api
import Vera.ChatUI.api.notebook_api as notebook_api
import Vera.ChatUI.api.schemas as schemas
import Vera.ChatUI.api.session as session
import Vera.ChatUI.api.config as config_api
import Vera.ChatUI.api.Orchestrator.ollama_api as ollama_api
import Vera.ChatUI.api.agents_api as agents_api
# from Vera.ChatUI.api.session import vera_instances, sessions, toolchain_executions, active_toolchains, websocket_connections

# ============================================================
# Logging setup
# ============================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# FastAPI setup
# ============================================================

# Initialize FastAPI app
app = FastAPI(
    title="Vera AI Chat API",
    description="Multi-agent AI chat system with knowledge graph visualization and toolchain monitoring",
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

# ============================================================
# Router setup
# ============================================================

app.include_router(execution_api.router)
app.include_router(canvas_api.router)
app.include_router(chat_api.router)
app.include_router(chat_api.wsrouter)
app.include_router(chat_history_api.router)
app.include_router(graph_api.router)
app.include_router(toolchain_api.router)
app.include_router(toolchain_query_api.router)
app.include_router(toolchain_api.wsrouter)
app.include_router(n8n_proxy.router)
app.include_router(orchestrator_api.router)
app.include_router(api_api.router)
app.include_router(infra_api.router)
app.include_router(vectorstore_api.router)
app.include_router(memory_api.router)
app.include_router(proactivefocus_api.router)
app.include_router(proactivefocus_api.wsrouter)
app.include_router(session.router)
app.include_router(notebook_api.router)
app.include_router(config_api.router)
app.include_router(ollama_api.router)
app.include_router(agents_api.router)
# ============================================================
# Global storage
# ============================================================

# vera_instances: Dict[str, Vera] = {}
# sessions: Dict[str, Dict[str, Any]] = {}
tts_queue: List[Dict[str, Any]] = []
tts_playing = False

# Toolchain monitoring storage
toolchain_executions: Dict[str, Dict[str, Any]] = defaultdict(dict)  # session_id -> execution_id -> execution_data
active_toolchains: Dict[str, str] = {}  # session_id -> current execution_id
websocket_connections: Dict[str, List[WebSocket]] = defaultdict(list)  # session_id -> [websockets]

from Vera.ChatUI.api.Toolchain.toolchain_api import set_main_loop

@app.on_event("startup")
async def startup_event():
    set_main_loop()
    print("✓ Main event loop captured for WebSocket broadcasts")

# ============================================================
# Health and Info Endpoints
# ============================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "active_sessions": len(sessions),
        "tts_queue_length": len(tts_queue),
        "active_toolchains": len(active_toolchains)
    }

# Update the info endpoint to include new memory endpoints
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
            "memory": [
                "/api/memory/query",
                "/api/memory/hybrid-retrieve",
                "/api/memory/extract-entities",
                "/api/memory/subgraph",
                "/api/memory/{session_id}/entities",
                "/api/memory/{session_id}/relationships",
                "/api/memory/{session_id}/promote"
            ],
            "graph": ["/api/graph/session/{session_id}"],
            "toolchain": [
                "/api/toolchain/execute",
                "/ws/toolchain/{session_id}",
                "/api/toolchain/{session_id}/executions",
                "/api/toolchain/{session_id}/execution/{execution_id}",
                "/api/toolchain/{session_id}/active",
                "/api/toolchain/{session_id}/tools"
            ],
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