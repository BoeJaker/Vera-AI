"""
Vera API Endpoints using FastAPI - Enhanced with Toolchain Monitoring
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
from collections import defaultdict
from queue import Queue
from threading import Thread

# Import your existing modules
from vera import Vera
from Memory.memory import HybridMemory

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

# Global storage
vera_instances: Dict[str, Vera] = {}
sessions: Dict[str, Dict[str, Any]] = {}
tts_queue: List[Dict[str, Any]] = []
tts_playing = False

# Toolchain monitoring storage
toolchain_executions: Dict[str, Dict[str, Any]] = defaultdict(dict)  # session_id -> execution_id -> execution_data
active_toolchains: Dict[str, str] = {}  # session_id -> current execution_id
websocket_connections: Dict[str, List[WebSocket]] = defaultdict(list)  # session_id -> [websockets]


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

class VectorStoreRequest(BaseModel):
    session_id: str
    collection_name: str

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


class ToolExecutionStep(BaseModel):
    step_number: int
    tool_name: str
    tool_input: str
    tool_output: Optional[str] = None
    status: str  # "pending", "running", "completed", "failed"
    start_time: str
    end_time: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = {}


class ToolchainExecution(BaseModel):
    execution_id: str
    session_id: str
    query: str
    plan: List[Dict[str, str]]
    steps: List[ToolExecutionStep]
    status: str  # "planning", "executing", "completed", "failed"
    start_time: str
    end_time: Optional[str] = None
    total_steps: int
    completed_steps: int
    final_result: Optional[str] = None


class ToolchainRequest(BaseModel):
    session_id: str
    query: str


class MemoryQueryRequest(BaseModel):
    session_id: str
    query: str
    k: int = 5
    retrieval_type: str = "hybrid"  # "vector", "graph", "hybrid"
    filters: Optional[Dict[str, Any]] = None

class MemoryQueryResponse(BaseModel):
    results: List[Dict[str, Any]]
    retrieval_type: str
    query: str
    session_id: str

class EntityExtractionRequest(BaseModel):
    session_id: str
    text: str
    auto_promote: bool = False
    source_node_id: Optional[str] = None

class EntityExtractionResponse(BaseModel):
    entities: List[Dict[str, Any]]
    relations: List[Dict[str, Any]]
    clusters: Dict[str, List[str]]
    session_id: str

class SubgraphRequest(BaseModel):
    session_id: str
    seed_entity_ids: List[str]
    depth: int = 2

class HybridRetrievalRequest(BaseModel):
    session_id: str
    query: str
    k_vector: int = 5
    k_graph: int = 3
    graph_depth: int = 2
    include_entities: bool = True
    filters: Optional[Dict[str, Any]] = None


# ============================================================
# Helper Functions
# ============================================================

def get_or_create_vera(session_id: str) -> Vera:
    """Get or create a Vera instance for a session."""
    if session_id not in vera_instances:
        logger.warning(f"Vera instance not found for session {session_id}, creating new one")
        raise HTTPException(
            status_code=400, 
            detail="Session not properly initialized. Please start a new session."
        )
    return vera_instances[session_id]


def create_toolchain_execution(session_id: str, query: str) -> str:
    """Create a new toolchain execution record."""
    execution_id = str(uuid.uuid4())
    
    toolchain_executions[session_id][execution_id] = {
        "execution_id": execution_id,
        "session_id": session_id,
        "query": query,
        "plan": [],
        "steps": [],
        "status": "planning",
        "start_time": datetime.utcnow().isoformat(),
        "end_time": None,
        "total_steps": 0,
        "completed_steps": 0,
        "final_result": None
    }
    
    active_toolchains[session_id] = execution_id
    
    return execution_id


def update_toolchain_plan(session_id: str, execution_id: str, plan: List[Dict[str, str]]):
    """Update the plan for a toolchain execution."""
    if session_id in toolchain_executions and execution_id in toolchain_executions[session_id]:
        toolchain_executions[session_id][execution_id]["plan"] = plan
        toolchain_executions[session_id][execution_id]["total_steps"] = len(plan)
        toolchain_executions[session_id][execution_id]["status"] = "executing"


def add_toolchain_step(session_id: str, execution_id: str, step_number: int, 
                       tool_name: str, tool_input: str):
    """Add a new step to toolchain execution."""
    if session_id in toolchain_executions and execution_id in toolchain_executions[session_id]:
        step = {
            "step_number": step_number,
            "tool_name": tool_name,
            "tool_input": tool_input,
            "tool_output": None,
            "status": "running",
            "start_time": datetime.utcnow().isoformat(),
            "end_time": None,
            "error": None,
            "metadata": {}
        }
        toolchain_executions[session_id][execution_id]["steps"].append(step)
        return step
    return None


def update_toolchain_step(session_id: str, execution_id: str, step_number: int,
                          output: Optional[str] = None, error: Optional[str] = None,
                          status: str = "completed"):
    """Update a toolchain execution step."""
    if session_id in toolchain_executions and execution_id in toolchain_executions[session_id]:
        steps = toolchain_executions[session_id][execution_id]["steps"]
        for step in steps:
            if step["step_number"] == step_number:
                step["tool_output"] = output
                step["error"] = error
                step["status"] = status
                step["end_time"] = datetime.utcnow().isoformat()
                
                if status == "completed":
                    toolchain_executions[session_id][execution_id]["completed_steps"] += 1
                
                return step
    return None


def complete_toolchain_execution(session_id: str, execution_id: str, 
                                 final_result: str, status: str = "completed"):
    """Mark toolchain execution as complete."""
    if session_id in toolchain_executions and execution_id in toolchain_executions[session_id]:
        toolchain_executions[session_id][execution_id]["status"] = status
        toolchain_executions[session_id][execution_id]["end_time"] = datetime.utcnow().isoformat()
        toolchain_executions[session_id][execution_id]["final_result"] = final_result
        
        if session_id in active_toolchains:
            del active_toolchains[session_id]


async def broadcast_toolchain_event(session_id: str, event_type: str, data: Dict[str, Any]):
    """Broadcast toolchain events to all connected WebSockets for a session."""
    if session_id in websocket_connections:
        disconnected = []
        for websocket in websocket_connections[session_id]:
            try:
                await websocket.send_json({
                    "type": event_type,
                    "data": data,
                    "timestamp": datetime.utcnow().isoformat()
                })
            except Exception as e:
                logger.warning(f"Failed to send to websocket: {e}")
                disconnected.append(websocket)
        
        # Clean up disconnected websockets
        for ws in disconnected:
            websocket_connections[session_id].remove(ws)


class MonitoredToolChainPlanner:
    """Wrapper around Vera's ToolChainPlanner that captures execution data."""
    
    def __init__(self, original_planner, session_id: str):
        self.original_planner = original_planner
        self.session_id = session_id
        self.execution_id = None
    
    def execute_tool_chain(self, query: str, plan=None):
        """Monitored version of execute_tool_chain."""
        # Create execution record
        self.execution_id = create_toolchain_execution(self.session_id, query)
        
        try:
            # Broadcast execution started
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(broadcast_toolchain_event(
                self.session_id,
                "execution_started",
                {"execution_id": self.execution_id, "query": query}
            ))
            
            # Generate plan
            if plan is None:
                loop.run_until_complete(broadcast_toolchain_event(
                    self.session_id,
                    "status",
                    {"status": "planning"}
                ))
                
                gen = self.original_planner.plan_tool_chain(query)
                plan_chunks = []
                for chunk in gen:
                    plan_chunks.append(chunk)
                    if isinstance(chunk, str):
                        loop.run_until_complete(broadcast_toolchain_event(
                            self.session_id,
                            "plan_chunk",
                            {"chunk": chunk}
                        ))
                        yield chunk
                    elif isinstance(chunk, list):
                        # Final plan
                        update_toolchain_plan(self.session_id, self.execution_id, chunk)
                        loop.run_until_complete(broadcast_toolchain_event(
                            self.session_id,
                            "plan",
                            {"plan": chunk, "total_steps": len(chunk)}
                        ))
                        plan = chunk
                        yield chunk
            else:
                update_toolchain_plan(self.session_id, self.execution_id, plan)
            
            # Execute plan
            loop.run_until_complete(broadcast_toolchain_event(
                self.session_id,
                "status",
                {"status": "executing"}
            ))
            
            step_num = 0
            for step in plan:
                step_num += 1
                tool_name = step.get("tool")
                tool_input = str(step.get("input", ""))
                
                # Add step to monitoring
                add_toolchain_step(self.session_id, self.execution_id, step_num, 
                                  tool_name, tool_input)
                
                loop.run_until_complete(broadcast_toolchain_event(
                    self.session_id,
                    "step_started",
                    {
                        "step_number": step_num,
                        "tool_name": tool_name,
                        "tool_input": tool_input,
                        "execution_id": self.execution_id
                    }
                ))
                
                # Find tool
                tool = next((t for t in self.original_planner.tools if t.name == tool_name), None)
                
                if not tool:
                    error_msg = f"Tool not found: {tool_name}"
                    update_toolchain_step(self.session_id, self.execution_id, step_num,
                                        error=error_msg, status="failed")
                    loop.run_until_complete(broadcast_toolchain_event(
                        self.session_id,
                        "step_failed",
                        {"step_number": step_num, "error": error_msg}
                    ))
                    yield error_msg
                    continue
                
                # Resolve placeholders in tool_input
                if "{prev}" in tool_input and step_num > 1:
                    prev_step = toolchain_executions[self.session_id][self.execution_id]["steps"][step_num-2]
                    tool_input = tool_input.replace("{prev}", str(prev_step.get("tool_output", "")))
                
                for i in range(1, step_num):
                    prev_step = toolchain_executions[self.session_id][self.execution_id]["steps"][i-1]
                    tool_input = tool_input.replace(f"{{step_{i}}}", str(prev_step.get("tool_output", "")))
                
                # Execute tool
                try:
                    if hasattr(tool, "run") and callable(tool.run):
                        func = tool.run
                    elif hasattr(tool, "func") and callable(tool.func):
                        func = tool.func
                    elif callable(tool):
                        func = tool
                    else:
                        raise ValueError(f"Tool is not callable")
                    
                    collected = []
                    result = ""
                    try:
                        for r in func(tool_input):
                            collected.append(r)
                            loop.run_until_complete(broadcast_toolchain_event(
                                self.session_id,
                                "step_output",
                                {"step_number": step_num, "chunk": str(r)}
                            ))
                            yield r
                    except TypeError:
                        result = func(tool_input)
                        loop.run_until_complete(broadcast_toolchain_event(
                            self.session_id,
                            "step_output",
                            {"step_number": step_num, "chunk": str(result)}
                        ))
                        yield result
                    else:
                        result = "".join(str(c) for c in collected)
                    
                    # Update step as completed
                    update_toolchain_step(self.session_id, self.execution_id, step_num,
                                        output=result, status="completed")
                    
                    loop.run_until_complete(broadcast_toolchain_event(
                        self.session_id,
                        "step_completed",
                        {"step_number": step_num, "output": result[:500]}  # Truncate long outputs
                    ))
                    
                except Exception as e:
                    error_msg = f"Error executing {tool_name}: {str(e)}"
                    update_toolchain_step(self.session_id, self.execution_id, step_num,
                                        error=error_msg, status="failed")
                    loop.run_until_complete(broadcast_toolchain_event(
                        self.session_id,
                        "step_failed",
                        {"step_number": step_num, "error": error_msg}
                    ))
                    yield error_msg
            
            # Get final result
            final_result = ""
            if toolchain_executions[self.session_id][self.execution_id]["steps"]:
                final_result = toolchain_executions[self.session_id][self.execution_id]["steps"][-1].get("tool_output", "")
            
            complete_toolchain_execution(self.session_id, self.execution_id, 
                                       final_result, "completed")
            
            loop.run_until_complete(broadcast_toolchain_event(
                self.session_id,
                "execution_completed",
                {"final_result": final_result[:500]}
            ))
            
            loop.close()
            return final_result
            
        except Exception as e:
            logger.error(f"Toolchain execution error: {e}", exc_info=True)
            complete_toolchain_execution(self.session_id, self.execution_id, 
                                       str(e), "failed")
            
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            loop.run_until_complete(broadcast_toolchain_event(
                self.session_id,
                "execution_failed",
                {"error": str(e)}
            ))
            loop.close()
            raise


# ============================================================
# Session Management
# ============================================================

@app.post("/api/session/start", response_model=SessionStartResponse)
async def start_session():
    """Start a new chat session."""
    try:
        from concurrent.futures import ThreadPoolExecutor
        
        def create_vera():
            return Vera()
        
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            vera = await loop.run_in_executor(executor, create_vera)
        
        session_id = vera.sess.id
        vera_instances[session_id] = vera
        
        sessions[session_id] = {
            "created_at": datetime.utcnow().isoformat(),
            "messages": [],
            "files": {},
            "vera": vera
        }
        
        # Initialize toolchain storage for this session
        toolchain_executions[session_id] = {}
        
        # IMPORTANT: Wrap Vera's toolchain with monitoring
        if hasattr(vera, 'toolchain'):
            original_toolchain = vera.toolchain
            vera.toolchain = MonitoredToolChainPlanner(original_toolchain, session_id)
            logger.info(f"Wrapped toolchain with monitoring for session {session_id}")
        
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
    toolchain_executions.pop(session_id, None)
    active_toolchains.pop(session_id, None)
    
    return {"status": "ended", "session_id": session_id}

#####
# Memory Helper
####

# Add this helper function before the chat endpoints
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
# Memory Endpoints 
# ============================================================

@app.post("/api/memory/query", response_model=MemoryQueryResponse)
async def query_memory(request: MemoryQueryRequest):
    """
    Query memory using vector, graph, or hybrid retrieval.
    
    Retrieval types:
    - vector: Semantic search using embeddings
    - graph: Graph traversal from relevant nodes
    - hybrid: Combined vector + graph retrieval
    """
    if request.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(request.session_id)
    
    try:
        results = []
        
        if request.retrieval_type == "vector":
            # Pure vector retrieval from session memory
            vector_results = vera.mem.focus_context(
                request.session_id, 
                request.query, 
                k=request.k
            )
            results = vector_results
            
        elif request.retrieval_type == "graph":
            # Graph-based retrieval
            # First, find relevant entities via vector search
            vector_hits = vera.mem.focus_context(
                request.session_id, 
                request.query, 
                k=3
            )
            
            # Extract entity IDs from hits
            seed_ids = []
            for hit in vector_hits:
                # Look for linked entities in metadata
                if "entity_ids" in hit.get("metadata", {}):
                    seed_ids.extend(hit["metadata"]["entity_ids"])
            
            if seed_ids:
                # Get subgraph around these entities
                subgraph = vera.mem.extract_subgraph(seed_ids[:5], depth=2)
                results = [{
                    "type": "subgraph",
                    "nodes": subgraph["nodes"],
                    "relationships": subgraph["rels"]
                }]
            else:
                results = []
                
        elif request.retrieval_type == "hybrid":
            # Hybrid retrieval: vector + graph
            vector_results = vera.mem.focus_context(
                request.session_id, 
                request.query, 
                k=request.k
            )
            
            # Get long-term semantic results too
            long_term_results = vera.mem.semantic_retrieve(
                request.query,
                k=request.k,
                where=request.filters
            )
            
            # Combine and deduplicate
            seen_ids = set()
            combined = []
            
            for result in vector_results + long_term_results:
                if result["id"] not in seen_ids:
                    seen_ids.add(result["id"])
                    combined.append(result)
            
            results = combined[:request.k]
            
        else:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid retrieval_type: {request.retrieval_type}"
            )
        
        return MemoryQueryResponse(
            results=results,
            retrieval_type=request.retrieval_type,
            query=request.query,
            session_id=request.session_id
        )
        
    except Exception as e:
        logger.error(f"Memory query error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/memory/hybrid-retrieve")
async def hybrid_retrieve(request: HybridRetrievalRequest):
    """
    Advanced hybrid retrieval combining vector search and graph traversal.
    Returns both semantic matches and related entities from the knowledge graph.
    """
    if request.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(request.session_id)
    
    try:
        # Step 1: Vector retrieval from session context
        session_hits = vera.mem.focus_context(
            request.session_id,
            request.query,
            k=request.k_vector
        )
        
        # Step 2: Vector retrieval from long-term memory
        long_term_hits = vera.mem.semantic_retrieve(
            request.query,
            k=request.k_vector,
            where=request.filters
        )
        
        # Step 3: Extract entity IDs for graph traversal
        seed_entity_ids = set()
        
        for hit in session_hits + long_term_hits:
            metadata = hit.get("metadata", {})
            
            # Check for linked entities
            if "entity_ids" in metadata:
                seed_entity_ids.update(metadata["entity_ids"])
            
            # If hit itself is an entity
            if metadata.get("type") == "extracted_entity":
                seed_entity_ids.add(hit["id"])
        
        # Step 4: Graph traversal around seed entities
        graph_context = None
        if seed_entity_ids and request.include_entities:
            seed_list = list(seed_entity_ids)[:request.k_graph]
            graph_context = vera.mem.extract_subgraph(
                seed_list,
                depth=request.graph_depth
            )
        
        # Step 5: Combine results
        return {
            "session_id": request.session_id,
            "query": request.query,
            "vector_results": {
                "session": session_hits,
                "long_term": long_term_hits,
                "total": len(session_hits) + len(long_term_hits)
            },
            "graph_context": graph_context,
            "seed_entities": list(seed_entity_ids),
            "retrieval_stats": {
                "k_vector": request.k_vector,
                "k_graph": request.k_graph,
                "graph_depth": request.graph_depth,
                "entities_found": len(seed_entity_ids)
            }
        }
        
    except Exception as e:
        logger.error(f"Hybrid retrieval error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/memory/extract-entities", response_model=EntityExtractionResponse)
async def extract_entities(request: EntityExtractionRequest):
    """
    Extract entities and relationships from text using NLP.
    Links extracted entities to the session graph.
    """
    if request.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(request.session_id)
    
    try:
        extraction = vera.mem.extract_and_link(
            request.session_id,
            request.text,
            source_node_id=request.source_node_id,
            auto_promote=request.auto_promote
        )
        
        return EntityExtractionResponse(
            entities=extraction.get("entities", []),
            relations=extraction.get("relations", []),
            clusters=extraction.get("clusters", {}),
            session_id=request.session_id
        )
        
    except Exception as e:
        logger.error(f"Entity extraction error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/memory/subgraph")
async def get_memory_subgraph(request: SubgraphRequest):
    """
    Extract a subgraph around specific entity IDs.
    Useful for exploring knowledge graph neighborhoods.
    """
    if request.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(request.session_id)
    
    try:
        subgraph = vera.mem.extract_subgraph(
            request.seed_entity_ids,
            depth=request.depth
        )
        
        return {
            "session_id": request.session_id,
            "seed_entity_ids": request.seed_entity_ids,
            "depth": request.depth,
            "subgraph": subgraph,
            "stats": {
                "nodes": len(subgraph.get("nodes", [])),
                "relationships": len(subgraph.get("rels", []))
            }
        }
        
    except Exception as e:
        logger.error(f"Subgraph extraction error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/memory/{session_id}/entities")
async def list_session_entities(session_id: str, limit: int = 50):
    """
    List all entities extracted in a session.
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    try:
        with vera.mem.graph._driver.session() as db_sess:
            result = db_sess.run("""
                MATCH (s:Session {id: $session_id})-[:EXTRACTED_IN]-(e:ExtractedEntity)
                RETURN e.id AS id, 
                       e.text AS text, 
                       e.type AS type,
                       labels(e) AS labels,
                       e.confidence AS confidence,
                       e.original_text AS original_text
                ORDER BY e.confidence DESC
                LIMIT $limit
            """, {"session_id": session_id, "limit": limit})
            
            entities = []
            for record in result:
                entities.append({
                    "id": record["id"],
                    "text": record["text"],
                    "type": record["type"],
                    "labels": record["labels"],
                    "confidence": record.get("confidence", 0.0),
                    "original_text": record.get("original_text")
                })
            
            return {
                "session_id": session_id,
                "entities": entities,
                "total": len(entities)
            }
            
    except Exception as e:
        logger.error(f"Error listing entities: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/memory/{session_id}/relationships")
async def list_session_relationships(session_id: str, limit: int = 50):
    """
    List all relationships extracted in a session.
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    try:
        with vera.mem.graph._driver.session() as db_sess:
            result = db_sess.run("""
                MATCH (s:Session {id: $session_id})-[:EXTRACTED_IN]-(e1:ExtractedEntity)
                MATCH (e1)-[r:REL]->(e2:ExtractedEntity)
                WHERE r.extracted_from_session = $session_id
                RETURN e1.text AS head,
                       type(r) AS rel_type,
                       r.rel AS relation,
                       e2.text AS tail,
                       r.confidence AS confidence,
                       r.context AS context
                ORDER BY r.confidence DESC
                LIMIT $limit
            """, {"session_id": session_id, "limit": limit})
            
            relationships = []
            for record in result:
                relationships.append({
                    "head": record["head"],
                    "relation": record.get("relation") or record["rel_type"],
                    "tail": record["tail"],
                    "confidence": record.get("confidence", 0.0),
                    "context": record.get("context", "")[:200]
                })
            
            return {
                "session_id": session_id,
                "relationships": relationships,
                "total": len(relationships)
            }
            
    except Exception as e:
        logger.error(f"Error listing relationships: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/memory/{session_id}/promote")
async def promote_memory(session_id: str, memory_id: str, entity_anchor: Optional[str] = None):
    """
    Promote a session memory item to long-term storage.
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    try:
        # Get the memory item
        memories = vera.mem.get_session_memory(session_id)
        memory = next((m for m in memories if m.id == memory_id), None)
        
        if not memory:
            raise HTTPException(status_code=404, detail="Memory item not found")
        
        # Promote to long-term
        vera.mem.promote_session_memory_to_long_term(memory, entity_anchor)
        
        return {
            "status": "promoted",
            "memory_id": memory_id,
            "session_id": session_id,
            "entity_anchor": entity_anchor
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Memory promotion error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


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
# Toolchain Monitoring Endpoints
# ============================================================
@app.post("/api/toolchain/{session_id}/execute-tool")
async def execute_single_tool(session_id: str, tool_name: str, tool_input: str):
    """Execute a single tool directly."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    try:
        # Find the tool
        tool = next((t for t in vera.tools if t.name == tool_name), None)
        
        if not tool:
            raise HTTPException(status_code=404, detail=f"Tool not found: {tool_name}")
        
        # Execute the tool
        start_time = datetime.utcnow()
        
        if hasattr(tool, "run") and callable(tool.run):
            func = tool.run
        elif hasattr(tool, "func") and callable(tool.func):
            func = tool.func
        elif callable(tool):
            func = tool
        else:
            raise ValueError(f"Tool is not callable")
        
        # Collect output
        output = ""
        try:
            # Try generator first
            for chunk in func(tool_input):
                output += str(chunk)
        except TypeError:
            # Not a generator, call directly
            output = str(func(tool_input))
        
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds() * 1000
        
        return {
            "success": True,
            "tool_name": tool_name,
            "input": tool_input,
            "output": output,
            "duration_ms": duration,
            "executed_at": start_time.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Tool execution error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/api/toolchain/execute")
async def execute_toolchain(request: ToolchainRequest):
    """Execute a toolchain with full monitoring."""
    if request.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(request.session_id)
    execution_id = create_toolchain_execution(request.session_id, request.query)
    
    try:
        from concurrent.futures import ThreadPoolExecutor
        
        def run_toolchain():
            try:
                # Get the toolchain planner
                toolchain = vera.toolchain
                
                # Generate plan
                plan_gen = toolchain.plan_tool_chain(request.query)
                plan_json = ""
                for chunk in plan_gen:
                    if isinstance(chunk, list):
                        # This is the final plan
                        update_toolchain_plan(request.session_id, execution_id, chunk)
                        break
                    plan_json += str(chunk)
                
                # Execute the plan
                step_num = 0
                final_result = ""
                
                for step in toolchain_executions[request.session_id][execution_id]["plan"]:
                    step_num += 1
                    tool_name = step.get("tool")
                    tool_input = step.get("input", "")
                    
                    # Add step to monitoring
                    add_toolchain_step(request.session_id, execution_id, step_num, 
                                      tool_name, tool_input)
                    
                    # Find and execute the tool
                    tool = next((t for t in vera.tools if t.name == tool_name), None)
                    
                    if not tool:
                        update_toolchain_step(request.session_id, execution_id, step_num,
                                            error=f"Tool not found: {tool_name}",
                                            status="failed")
                        continue
                    
                    try:
                        # Execute tool
                        if hasattr(tool, "run") and callable(tool.run):
                            func = tool.run
                        elif hasattr(tool, "func") and callable(tool.func):
                            func = tool.func
                        elif callable(tool):
                            func = tool
                        else:
                            raise ValueError(f"Tool is not callable")
                        
                        result = ""
                        try:
                            for chunk in func(tool_input):
                                result += str(chunk)
                        except TypeError:
                            result = str(func(tool_input))
                        
                        # Update step with result
                        update_toolchain_step(request.session_id, execution_id, step_num,
                                            output=result, status="completed")
                        final_result = result
                        
                    except Exception as e:
                        update_toolchain_step(request.session_id, execution_id, step_num,
                                            error=str(e), status="failed")
                
                # Mark execution as complete
                complete_toolchain_execution(request.session_id, execution_id, 
                                           final_result, "completed")
                
                return final_result
                
            except Exception as e:
                logger.error(f"Toolchain execution error: {str(e)}", exc_info=True)
                complete_toolchain_execution(request.session_id, execution_id, 
                                           str(e), "failed")
                raise
        
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(executor, run_toolchain)
        
        return {
            "execution_id": execution_id,
            "status": "completed",
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Toolchain execution error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/toolchain/{session_id}")
async def websocket_toolchain(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for monitoring toolchain executions triggered by chat."""
    await websocket.accept()
    
    if session_id not in sessions:
        await websocket.close(code=4004, reason="Session not found")
        return
    
    # Register this websocket for broadcasts
    websocket_connections[session_id].append(websocket)
    logger.info(f"WebSocket connected for toolchain monitoring: {session_id}")
    
    try:
        # Keep connection alive and listen for any manual queries
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
                message_data = json.loads(data)
                
                # Optional: Allow manual toolchain execution via websocket
                if "query" in message_data:
                    query = message_data["query"]
                    vera = get_or_create_vera(session_id)
                    
                    # Execute through monitored toolchain
                    execution_id = create_toolchain_execution(session_id, query)
                    await websocket.send_json({
                        "type": "execution_started",
                        "execution_id": execution_id,
                        "query": query
                    })
                    
                    # Run in thread
                    def run_toolchain():
                        try:
                            result = ""
                            for chunk in vera.toolchain.execute_tool_chain(query):
                                result += str(chunk)
                            return result
                        except Exception as e:
                            logger.error(f"Toolchain error: {e}")
                            return str(e)
                    
                    loop = asyncio.get_event_loop()
                    with ThreadPoolExecutor() as executor:
                        await loop.run_in_executor(executor, run_toolchain)
                    
            except asyncio.TimeoutError:
                # Just keep alive, broadcasts happen from MonitoredToolChainPlanner
                continue
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "error": "Invalid JSON"})
    
    except WebSocketDisconnect:
        logger.info(f"Toolchain WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"Toolchain WebSocket error: {str(e)}", exc_info=True)
    finally:
        # Clean up websocket connection
        if websocket in websocket_connections[session_id]:
            websocket_connections[session_id].remove(websocket)


@app.get("/api/toolchain/{session_id}/executions")
async def get_toolchain_executions(session_id: str):
    """Get all toolchain executions for a session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    executions = toolchain_executions.get(session_id, {})
    
    return {
        "session_id": session_id,
        "executions": list(executions.values()),
        "total": len(executions),
        "active_execution": active_toolchains.get(session_id)
    }


@app.get("/api/toolchain/{session_id}/execution/{execution_id}")
async def get_toolchain_execution(session_id: str, execution_id: str):
    """Get details of a specific toolchain execution."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session_id not in toolchain_executions or execution_id not in toolchain_executions[session_id]:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    return toolchain_executions[session_id][execution_id]


@app.get("/api/toolchain/{session_id}/active")
async def get_active_toolchain(session_id: str):
    """Get the currently active toolchain execution."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session_id not in active_toolchains:
        return {"active": False, "execution_id": None}
    
    execution_id = active_toolchains[session_id]
    execution = toolchain_executions[session_id][execution_id]
    
    return {
        "active": True,
        "execution": execution
    }


@app.get("/api/toolchain/{session_id}/tools")
async def list_available_tools(session_id: str):
    """List all available tools for a session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    tools_info = []
    for tool in vera.tools:
        tools_info.append({
            "name": tool.name,
            "description": tool.description if hasattr(tool, "description") else "No description available",
            "type": type(tool).__name__
        })
    
    return {
        "session_id": session_id,
        "tools": tools_info,
        "total": len(tools_info)
    }


@app.delete("/api/toolchain/{session_id}/execution/{execution_id}")
async def delete_toolchain_execution(session_id: str, execution_id: str):
    """Delete a toolchain execution record."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session_id not in toolchain_executions or execution_id not in toolchain_executions[session_id]:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    del toolchain_executions[session_id][execution_id]
    
    if active_toolchains.get(session_id) == execution_id:
        del active_toolchains[session_id]
    
    return {"status": "deleted", "execution_id": execution_id}


# ============================================================
# Toolchain Analytics Endpoints
# ============================================================

@app.get("/api/toolchain/{session_id}/stats")
async def get_toolchain_stats(session_id: str):
    """Get statistics about toolchain executions for a session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    executions = toolchain_executions.get(session_id, {})
    
    if not executions:
        return {
            "session_id": session_id,
            "total_executions": 0,
            "completed": 0,
            "failed": 0,
            "in_progress": 0,
            "total_steps": 0,
            "avg_steps_per_execution": 0,
            "most_used_tools": []
        }
    
    completed = sum(1 for e in executions.values() if e["status"] == "completed")
    failed = sum(1 for e in executions.values() if e["status"] == "failed")
    in_progress = sum(1 for e in executions.values() if e["status"] in ["planning", "executing"])
    
    total_steps = sum(e["total_steps"] for e in executions.values())
    avg_steps = total_steps / len(executions) if executions else 0
    
    # Count tool usage
    tool_usage = defaultdict(int)
    for execution in executions.values():
        for step in execution["steps"]:
            tool_usage[step["tool_name"]] += 1
    
    most_used_tools = sorted(
        [{"tool": tool, "count": count} for tool, count in tool_usage.items()],
        key=lambda x: x["count"],
        reverse=True
    )[:10]
    
    return {
        "session_id": session_id,
        "total_executions": len(executions),
        "completed": completed,
        "failed": failed,
        "in_progress": in_progress,
        "total_steps": total_steps,
        "avg_steps_per_execution": round(avg_steps, 2),
        "most_used_tools": most_used_tools
    }


@app.get("/api/toolchain/execution/{execution_id}/timeline")
async def get_execution_timeline(execution_id: str):
    """Get a timeline view of a toolchain execution."""
    # Find the execution across all sessions
    execution_data = None
    session_id = None
    
    for sid, execs in toolchain_executions.items():
        if execution_id in execs:
            execution_data = execs[execution_id]
            session_id = sid
            break
    
    if not execution_data:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    timeline = []
    
    # Add planning event
    timeline.append({
        "timestamp": execution_data["start_time"],
        "event": "planning_started",
        "description": "Toolchain planning initiated"
    })
    
    # Add step events
    for step in execution_data["steps"]:
        timeline.append({
            "timestamp": step["start_time"],
            "event": "step_started",
            "step_number": step["step_number"],
            "tool": step["tool_name"],
            "description": f"Started executing {step['tool_name']}"
        })
        
        if step["end_time"]:
            timeline.append({
                "timestamp": step["end_time"],
                "event": "step_completed" if step["status"] == "completed" else "step_failed",
                "step_number": step["step_number"],
                "tool": step["tool_name"],
                "description": f"{'Completed' if step['status'] == 'completed' else 'Failed'} {step['tool_name']}",
                "error": step.get("error")
            })
    
    # Add completion event
    if execution_data["end_time"]:
        timeline.append({
            "timestamp": execution_data["end_time"],
            "event": "execution_completed",
            "description": f"Toolchain execution {execution_data['status']}"
        })
    
    return {
        "execution_id": execution_id,
        "session_id": session_id,
        "timeline": timeline,
        "total_events": len(timeline)
    }

# ============================================================
# Vector Store Endpoints
# ============================================================
@app.get("/api/vectorstore/{session_id}/stats")
async def get_vectorstore_stats(session_id: str):
    """Get statistics about the vector store for a session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    try:
        index = vera.mem.vector_store.index
        total_vectors = index.ntotal if hasattr(index, 'ntotal') else 0
        dimension = index.d if hasattr(index, 'd') else 0
        
        return {
            "session_id": session_id,
            "total_vectors": total_vectors,
            "dimension": dimension
        }
        
    except Exception as e:
        logger.error(f"Vector store stats error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/vectorstore/{session_id}/get_similar")
async def get_similar_vectors(session_id: str, request: VectorStoreRequest):
    """Get similar vectors from the vector store."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    try:
        index = vera.mem.vector_store.index
        query_vector = request.vector
        top_k = request.top_k
        
        if not hasattr(index, 'search'):
            raise HTTPException(status_code=500, detail="Vector store does not support search")
        
        D, I = index.search(np.array([query_vector], dtype='float32'), top_k)
        
        results = []
        for dist, idx in zip(D[0], I[0]):
            if idx == -1:
                continue
            results.append({
                "index": int(idx),
                "distance": float(dist)
            })
        
        return {
            "session_id": session_id,
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Vector store search error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/vectorstore/{session_id}/get_collection")
async def get_vectorstore_collection(session_id: str):
    """Get vector store collection details."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    try:
        collection = vera.mem.vector_store.collection
        
        return {
            "session_id": session_id,
            "collection_name": collection.name if hasattr(collection, 'name') else "default",
            "metadata": collection.metadata if hasattr(collection, 'metadata') else {}
        }
        
    except Exception as e:
        logger.error(f"Vector store collection error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
# ============================================================
# Proactive Focus Manager Endpoints - FIXED
# ============================================================

@app.get("/api/focus/{session_id}/boards/list")
async def list_focus_boards(session_id: str):
    """Get list of all saved focus board files."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    try:
        boards = vera.focus_manager.list_saved_boards()
        
        return {
            "status": "success",
            "boards": boards,
            "total": len(boards)
        }
    except Exception as e:
        logger.error(f"Failed to list focus boards: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list boards: {str(e)}")


@app.post("/api/focus/{session_id}/boards/load")
async def load_focus_board_file(session_id: str, request: dict):
    """Load a focus board from file."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    filename = request.get("filename")
    if not filename:
        raise HTTPException(status_code=400, detail="Filename required")
    
    try:
        success = vera.focus_manager.load_focus_board(filename)
        
        if not success:
            return {
                "status": "error",
                "message": f"Focus board not found: {filename}"
            }
        
        # Broadcast the loaded state
        vera.focus_manager._broadcast_sync("focus_loaded", {
            "focus": vera.focus_manager.focus,
            "focus_board": vera.focus_manager.focus_board,
            "filename": filename
        })
        
        return {
            "status": "success",
            "focus": vera.focus_manager.focus,
            "focus_board": vera.focus_manager.focus_board,
            "project_id": vera.focus_manager.project_id,
            "filename": filename
        }
        
    except Exception as e:
        logger.error(f"Failed to load focus board: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load: {str(e)}")


@app.delete("/api/focus/{session_id}/boards/delete")
async def delete_focus_board_file(session_id: str, request: dict):
    """Delete a saved focus board file."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    filename = request.get("filename")
    if not filename:
        raise HTTPException(status_code=400, detail="Filename required")
    
    try:
        import os
        filepath = os.path.join(vera.focus_manager.focus_boards_dir, filename)
        
        if not os.path.exists(filepath):
            return {
                "status": "error",
                "message": f"File not found: {filename}"
            }
        
        # Delete the file
        os.remove(filepath)
        
        logger.info(f"Deleted focus board file: {filepath}")
        
        return {
            "status": "success",
            "message": f"Deleted: {filename}"
        }
        
    except Exception as e:
        logger.error(f"Failed to delete focus board: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete: {str(e)}")
    
@app.get("/api/focus/{session_id}")
async def get_focus_status(session_id: str):
    '''Get current focus manager status.'''
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        return {
            "focus": None,
            "focus_board": {},
            "running": False
        }
    
    fm = vera.focus_manager
    
    return {
        "focus": fm.focus,
        "focus_board": fm.focus_board,
        "running": fm.running,
        "latest_conversation": fm.latest_conversation,
        "proactive_interval": fm.proactive_interval,
        "cpu_threshold": fm.cpu_threshold
    }


@app.post("/api/focus/{session_id}/set")
async def set_focus(session_id: str, request: dict):
    '''Set the focus for proactive thinking.'''
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    focus_text = request.get("focus", "")
    if not focus_text:
        raise HTTPException(status_code=400, detail="Focus text required")
    
    vera.focus_manager.set_focus(focus_text)
    
    return {
        "status": "success",
        "focus": vera.focus_manager.focus
    }


@app.post("/api/focus/{session_id}/clear")
async def clear_focus(session_id: str):
    '''Clear the current focus.'''
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    vera.focus_manager.clear_focus()
    
    return {"status": "success", "focus": None}


@app.post("/api/focus/{session_id}/board/add")
async def add_to_focus_board(session_id: str, request: dict):
    '''Add an item to the focus board.'''
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    category = request.get("category", "actions")
    note = request.get("note", "")
    
    if not note:
        raise HTTPException(status_code=400, detail="Note text required")
    
    vera.focus_manager.add_to_focus_board(category, note)
    
    return {
        "status": "success",
        "focus_board": vera.focus_manager.focus_board
    }


@app.post("/api/focus/{session_id}/board/clear")
async def clear_focus_board_category(session_id: str, request: dict):
    '''Clear a specific category on the focus board.'''
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    category = request.get("category")
    if not category:
        raise HTTPException(status_code=400, detail="Category required")
    
    # Clear the category
    if category in vera.focus_manager.focus_board:
        vera.focus_manager.focus_board[category] = []
    
    # Broadcast update
    if hasattr(vera.focus_manager, '_broadcast_sync'):
        vera.focus_manager._broadcast_sync("board_updated", {
            "focus_board": vera.focus_manager.focus_board
        })
    
    return {
        "status": "success",
        "category": category,
        "focus_board": vera.focus_manager.focus_board
    }


# @app.get("/api/focus/{session_id}/start")
# async def start_proactive_thought(session_id: str):
#     """Start the proactive focus manager."""
#     if session_id not in sessions:
#         raise HTTPException(status_code=404, detail="Session not found")
    
#     vera = get_or_create_vera(session_id)
    
#     if not hasattr(vera, 'focus_manager'):
#         raise HTTPException(status_code=400, detail="Focus manager not available")
    
#     vera.focus_manager.iterative_workflow( 
#         max_iterations = None, 
#         iteration_interval = 600,
#         auto_execute = True
#         # stream_output = True
#     )
    
#     return {
#         "status": "started",
#         "focus": vera.focus_manager.focus
#     }


@app.post("/api/focus/{session_id}/stop")
async def stop_proactive_thought(session_id: str):
    """Stop the proactive focus manager."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    # Stop the focus manager
    vera.focus_manager.running = False
    
    # Broadcast update
    if hasattr(vera.focus_manager, '_broadcast_sync'):
        vera.focus_manager._broadcast_sync("focus_stopped", {
            "focus": vera.focus_manager.focus
        })
    
    return {
        "status": "stopped",
        "focus": vera.focus_manager.focus
    }


@app.get("/api/focus/{session_id}/start")
async def start_proactive_thought(session_id: str):
    """Start the proactive focus manager."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    # Remove the invalid stream_output parameter
    vera.focus_manager.start_workflow_thread(
        max_iterations=None, 
        iteration_interval=600,
        auto_execute=True
    )
    
    return {
        "status": "started",
        "focus": vera.focus_manager.focus
    }


@app.post("/api/focus/{session_id}/trigger")
async def trigger_proactive_thought(session_id: str):
    """Manually trigger a proactive thought generation."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    if not vera.focus_manager.focus:
        raise HTTPException(status_code=400, detail="No focus set")
    
    # Use the new async trigger method
    vera.focus_manager.trigger_proactive_thought_async()
    
    return {
        "status": "triggered",
        "message": "Proactive thought generation started"
    }
# ============================================================
# Granular Workflow Stage Control Endpoints
# ============================================================

@app.post("/api/focus/{session_id}/stage/ideas")
async def run_ideas_stage(session_id: str, request: dict = None):
    """Generate ideas for the current focus."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    if not vera.focus_manager.focus:
        raise HTTPException(status_code=400, detail="No focus set")
    
    # Run in background thread
    import threading
    
    def run():
        context = request.get("context") if request else None
        vera.focus_manager.generate_ideas_stage(context=context)
    
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    
    return {
        "status": "started",
        "stage": "ideas"
    }


@app.post("/api/focus/{session_id}/stage/next_steps")
async def run_next_steps_stage(session_id: str, request: dict = None):
    """Generate next steps for the current focus."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    if not vera.focus_manager.focus:
        raise HTTPException(status_code=400, detail="No focus set")
    
    # Run in background thread
    import threading
    
    def run():
        context = request.get("context") if request else None
        vera.focus_manager.generate_next_steps_stage(context=context)
    
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    
    return {
        "status": "started",
        "stage": "next_steps"
    }


@app.post("/api/focus/{session_id}/stage/actions")
async def run_actions_stage(session_id: str, request: dict = None):
    """Generate actions for the current focus."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    if not vera.focus_manager.focus:
        raise HTTPException(status_code=400, detail="No focus set")
    
    # Run in background thread
    import threading
    
    def run():
        context = request.get("context") if request else None
        vera.focus_manager.generate_actions_stage(context=context)
    
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    
    return {
        "status": "started",
        "stage": "actions"
    }


@app.post("/api/focus/{session_id}/stage/execute")
async def run_execute_stage(session_id: str, request: dict = None):
    """Execute actions from the focus board."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    if not vera.focus_manager.focus:
        raise HTTPException(status_code=400, detail="No focus set")
    
    # Get parameters
    max_executions = request.get("max_executions", 2) if request else 2
    priority_filter = request.get("priority", "high") if request else "high"
    
    # Run in background thread
    import threading
    
    def run():
        vera.focus_manager.execute_actions_stage(
            max_executions=max_executions,
            priority_filter=priority_filter
        )
    
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    
    return {
        "status": "started",
        "stage": "execute",
        "max_executions": max_executions,
        "priority": priority_filter
    }


@app.post("/api/focus/{session_id}/action/execute")
async def execute_single_action(session_id: str, request: dict):
    """Execute a single action directly."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    action = request.get("action")
    if not action:
        raise HTTPException(status_code=400, detail="Action required")
    
    # Run in background thread
    import threading
    
    def run():
        try:
            logger.info(f"Executing single action: {action.get('description', '')}")
            result = vera.focus_manager.handoff_to_toolchain(action)
            logger.info(f"Action execution result: {result}")
        except Exception as e:
            logger.error(f"Error executing action: {e}", exc_info=True)
    
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    
    return {
        "status": "started",
        "action": action.get("description", str(action))
    }


@app.post("/api/focus/{session_id}/stage/stop")
async def stop_stage(session_id: str):
    """Stop any running stage (best effort - threads may not stop immediately)."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    # Broadcast stop signal
    vera.focus_manager._broadcast_sync("stage_stopped", {
        "timestamp": datetime.utcnow().isoformat()
    })
    
    return {
        "status": "stop_requested",
        "message": "Stop signal sent (active stages will complete their current operation)"
    }

@app.websocket("/ws/focus/{session_id}")
async def websocket_focus(websocket: WebSocket, session_id: str):
    '''WebSocket endpoint for real-time focus manager updates.'''
    await websocket.accept()
    
    if session_id not in sessions:
        await websocket.close(code=4004, reason="Session not found")
        return
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        await websocket.send_json({"type": "error", "error": "Focus manager not available"})
        await websocket.close()
        return
    
    # Register websocket for focus updates
    if not hasattr(vera.focus_manager, '_websockets'):
        vera.focus_manager._websockets = []
    vera.focus_manager._websockets.append(websocket)
    
    # Send initial state
    await websocket.send_json({
        "type": "focus_status",
        "data": {
            "focus": vera.focus_manager.focus,
            "focus_board": vera.focus_manager.focus_board,
            "running": vera.focus_manager.running
        }
    })
    
    try:
        # Keep connection alive, only send updates on changes
        last_state = {
            "focus": vera.focus_manager.focus,
            "focus_board": json.dumps(vera.focus_manager.focus_board),
            "running": vera.focus_manager.running
        }
        
        while True:
            await asyncio.sleep(5)  # Check every 5 seconds instead of 1
            
            # Only send if state changed
            current_state = {
                "focus": vera.focus_manager.focus,
                "focus_board": json.dumps(vera.focus_manager.focus_board),
                "running": vera.focus_manager.running
            }
            
            if current_state != last_state:
                await websocket.send_json({
                    "type": "focus_status",
                    "data": {
                        "focus": vera.focus_manager.focus,
                        "focus_board": vera.focus_manager.focus_board,
                        "running": vera.focus_manager.running
                    }
                })
                last_state = current_state
    
    except WebSocketDisconnect:
        logger.info(f"Focus WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"Focus WebSocket error: {str(e)}", exc_info=True)
    finally:
        if websocket in vera.focus_manager._websockets:
            vera.focus_manager._websockets.remove(websocket)


@app.get("/api/focus/{session_id}/save")
async def save_focus_state(session_id: str):
    """Save current focus and board state to memory."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    fm = vera.focus_manager
    
    # Save to Neo4j memory
    focus_state = {
        "focus": fm.focus,
        "focus_board": fm.focus_board,
        "running": fm.running,
        "saved_at": datetime.utcnow().isoformat()
    }
    
    try:
        vera.mem.add_session_memory(
            vera.sess.id,
            json.dumps(focus_state, indent=2),
            "FocusState",
            {
                "topic": "focus_state",
                "focus": fm.focus or "none",
                "saved_at": focus_state["saved_at"]
            },
            promote=True
        )
        
        return {
            "status": "saved",
            "focus_state": focus_state
        }
    except Exception as e:
        logger.error(f"Failed to save focus state: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save: {str(e)}")


@app.get("/api/focus/{session_id}/load")
async def load_focus_state(session_id: str):
    """Load last saved focus state from memory."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    if not hasattr(vera, 'focus_manager'):
        raise HTTPException(status_code=400, detail="Focus manager not available")
    
    try:
        # Query Neo4j for last saved focus state
        driver = vera.mem.graph._driver
        
        with driver.session() as db_sess:
            result = db_sess.run("""
                MATCH (n:FocusState)
                WHERE n.session_id = $session_id
                RETURN n.text AS state, n.saved_at AS saved_at
                ORDER BY n.saved_at DESC
                LIMIT 1
            """, {"session_id": vera.sess.id})
            
            record = result.single()
            if not record:
                return {
                    "status": "not_found",
                    "message": "No saved focus state found"
                }
            
            focus_state = json.loads(record["state"])
            
            # Restore focus manager state
            fm = vera.focus_manager
            fm.focus = focus_state.get("focus")
            fm.focus_board = focus_state.get("focus_board", {
                "progress": [],
                "next_steps": [],
                "issues": [],
                "ideas": [],
                "actions": []
            })
            
            # Broadcast the loaded state
            fm._broadcast_sync("focus_loaded", {
                "focus": fm.focus,
                "focus_board": fm.focus_board,
                "loaded_from": record["saved_at"]
            })
            
            return {
                "status": "loaded",
                "focus_state": focus_state,
                "loaded_from": record["saved_at"]
            }
            
    except Exception as e:
        logger.error(f"Failed to load focus state: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load: {str(e)}")


@app.get("/api/focus/{session_id}/history")
async def get_focus_history(session_id: str):
    """Get history of saved focus states."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    try:
        driver = vera.mem.graph._driver
        
        with driver.session() as db_sess:
            result = db_sess.run("""
                MATCH (n:FocusState)
                WHERE n.session_id = $session_id
                RETURN n.text AS state, n.saved_at AS saved_at, n.focus AS focus
                ORDER BY n.saved_at DESC
                LIMIT 20
            """, {"session_id": vera.sess.id})
            
            history = []
            for record in result:
                try:
                    state = json.loads(record["state"])
                    history.append({
                        "focus": state.get("focus"),
                        "saved_at": record["saved_at"],
                        "board_items": sum(len(items) for items in state.get("focus_board", {}).values())
                    })
                except:
                    continue
            
            return {
                "status": "success",
                "history": history,
                "total": len(history)
            }
            
    except Exception as e:
        logger.error(f"Failed to get focus history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get history: {str(e)}")
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
                            elif node_type in ["Plan", "plan"]:
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
                            elif node_type == ["Session", "session"]:
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

# from fastapi import FastAPI, HTTPException, Depends
# from pydantic import BaseModel, Field
# from typing import Optional, List, Dict, Any
# from datetime import datetime
from uuid import uuid4
# import neo4j
from neo4j import GraphDatabase

# Pydantic Models
class NotebookCreate(BaseModel):
    name: str
    description: Optional[str] = None

class NotebookUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class NoteSource(BaseModel):
    type: str  # chat_message, graph_node, memory, etc.
    message_id: Optional[str] = None
    role: Optional[str] = None
    timestamp: Optional[str] = None
    node_id: Optional[str] = None
    content: Optional[str] = None

class NoteCreate(BaseModel):
    title: str
    content: str = ""
    source: Optional[NoteSource] = None
    tags: List[str] = []
    metadata: Dict[str, Any] = {}

class NoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None

class NoteSearch(BaseModel):
    query: str
    notebook_ids: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    source_type: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None

# Database helper
def get_neo4j_driver():
    # Replace with your actual connection
    return GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "testpassword"))

# ==================== NOTEBOOK ENDPOINTS ====================

@app.get("/api/notebooks/{session_id}")
async def get_notebooks(session_id: str):
    """Get all notebooks for a session"""
    driver = get_neo4j_driver()
    
    with driver.session() as session:
        result = session.run("""
            MATCH (s:Session {id: $session_id})-[:HAS_NOTEBOOK]->(nb:Notebook)
            OPTIONAL MATCH (nb)-[:CONTAINS]->(n:Note)
            WITH nb, count(n) as note_count
            RETURN nb.id as id, nb.name as name, nb.description as description,
                   nb.created_at as created_at, nb.updated_at as updated_at,
                   note_count
            ORDER BY nb.created_at DESC
        """, session_id=session_id)
        
        notebooks = []
        for record in result:
            notebooks.append({
                "id": record["id"],
                "session_id": session_id,
                "name": record["name"],
                "description": record["description"],
                "created_at": record["created_at"],
                "updated_at": record["updated_at"],
                "note_count": record["note_count"]
            })
    
    driver.close()
    return {"notebooks": notebooks}

@app.post("/api/notebooks/{session_id}/create")
async def create_notebook(session_id: str, notebook: NotebookCreate):
    """Create a new notebook"""
    driver = get_neo4j_driver()
    notebook_id = str(uuid4())
    now = datetime.utcnow().isoformat()
    
    with driver.session() as session:
        # Check if session exists
        session_check = session.run("""
            MATCH (s:Session {id: $session_id})
            RETURN s
        """, session_id=session_id)
        
        if not session_check.single():
            driver.close()
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Create notebook
        result = session.run("""
            MATCH (s:Session {id: $session_id})
            CREATE (nb:Notebook {
                id: $notebook_id,
                name: $name,
                description: $description,
                created_at: $now,
                updated_at: $now
            })
            CREATE (s)-[:HAS_NOTEBOOK]->(nb)
            RETURN nb
        """, session_id=session_id, notebook_id=notebook_id, 
             name=notebook.name, description=notebook.description, now=now)
        
        record = result.single()
        if not record:
            driver.close()
            raise HTTPException(status_code=500, detail="Failed to create notebook")
        
        nb = record["nb"]
        notebook_data = {
            "id": nb["id"],
            "session_id": session_id,
            "name": nb["name"],
            "description": nb["description"],
            "created_at": nb["created_at"],
            "updated_at": nb["updated_at"],
            "note_count": 0
        }
    
    driver.close()
    return {"notebook": notebook_data}

@app.put("/api/notebooks/{session_id}/{notebook_id}")
async def update_notebook(session_id: str, notebook_id: str, notebook: NotebookUpdate):
    """Update a notebook"""
    driver = get_neo4j_driver()
    now = datetime.utcnow().isoformat()
    
    update_fields = []
    params = {"session_id": session_id, "notebook_id": notebook_id, "now": now}
    
    if notebook.name is not None:
        update_fields.append("nb.name = $name")
        params["name"] = notebook.name
    
    if notebook.description is not None:
        update_fields.append("nb.description = $description")
        params["description"] = notebook.description
    
    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    update_fields.append("nb.updated_at = $now")
    
    with driver.session() as session:
        result = session.run(f"""
            MATCH (s:Session {{id: $session_id}})-[:HAS_NOTEBOOK]->(nb:Notebook {{id: $notebook_id}})
            SET {', '.join(update_fields)}
            RETURN nb
        """, **params)
        
        record = result.single()
        if not record:
            driver.close()
            raise HTTPException(status_code=404, detail="Notebook not found")
        
        nb = record["nb"]
        notebook_data = {
            "id": nb["id"],
            "session_id": session_id,
            "name": nb["name"],
            "description": nb["description"],
            "created_at": nb["created_at"],
            "updated_at": nb["updated_at"]
        }
    
    driver.close()
    return {"notebook": notebook_data}

@app.delete("/api/notebooks/{session_id}/{notebook_id}")
async def delete_notebook(session_id: str, notebook_id: str):
    """Delete a notebook and all its notes"""
    driver = get_neo4j_driver()
    
    with driver.session() as session:
        # Count notes before deletion
        count_result = session.run("""
            MATCH (s:Session {id: $session_id})-[:HAS_NOTEBOOK]->(nb:Notebook {id: $notebook_id})
            OPTIONAL MATCH (nb)-[:CONTAINS]->(n:Note)
            RETURN count(n) as note_count
        """, session_id=session_id, notebook_id=notebook_id)
        
        count_record = count_result.single()
        if not count_record:
            driver.close()
            raise HTTPException(status_code=404, detail="Notebook not found")
        
        note_count = count_record["note_count"]
        
        # Delete notebook and its notes
        session.run("""
            MATCH (s:Session {id: $session_id})-[:HAS_NOTEBOOK]->(nb:Notebook {id: $notebook_id})
            OPTIONAL MATCH (nb)-[:CONTAINS]->(n:Note)
            DETACH DELETE nb, n
        """, session_id=session_id, notebook_id=notebook_id)
    
    driver.close()
    return {"success": True, "deleted_notes": note_count}

# ==================== NOTE ENDPOINTS ====================

@app.get("/api/notebooks/{session_id}/{notebook_id}/notes")
async def get_notes(
    session_id: str, 
    notebook_id: str,
    sort_by: str = "created_at",
    order: str = "desc",
    limit: int = 50,
    offset: int = 0
):
    """Get all notes in a notebook"""
    driver = get_neo4j_driver()
    
    valid_sort_fields = ["created_at", "updated_at", "title"]
    if sort_by not in valid_sort_fields:
        sort_by = "created_at"
    
    order_clause = "DESC" if order.lower() == "desc" else "ASC"
    
    with driver.session() as session:
        result = session.run(f"""
            MATCH (s:Session {{id: $session_id}})-[:HAS_NOTEBOOK]->(nb:Notebook {{id: $notebook_id}})
            MATCH (nb)-[:CONTAINS]->(n:Note)
            RETURN n.id as id, n.title as title, n.content as content,
                   n.created_at as created_at, n.updated_at as updated_at,
                   n.source as source, n.tags as tags, n.metadata as metadata
            ORDER BY n.{sort_by} {order_clause}
            SKIP $offset
            LIMIT $limit
        """, session_id=session_id, notebook_id=notebook_id, 
             offset=offset, limit=limit)
        
        notes = []
        for record in result:
            note = {
                "id": record["id"],
                "notebook_id": notebook_id,
                "title": record["title"],
                "content": record["content"],
                "created_at": record["created_at"],
                "updated_at": record["updated_at"],
                "tags": record["tags"] or [],
                "metadata": record["metadata"] or {}
            }
            
            if record["source"]:
                note["source"] = record["source"]
            
            notes.append(note)
        
        # Get total count
        count_result = session.run("""
            MATCH (nb:Notebook {id: $notebook_id})-[:CONTAINS]->(n:Note)
            RETURN count(n) as total
        """, notebook_id=notebook_id)
        
        total = count_result.single()["total"]
    
    driver.close()
    return {
        "notes": notes,
        "total": total,
        "limit": limit,
        "offset": offset
    }

@app.get("/api/notebooks/{session_id}/{notebook_id}/notes/{note_id}")
async def get_note(session_id: str, notebook_id: str, note_id: str):
    """Get a single note"""
    driver = get_neo4j_driver()
    
    with driver.session() as session:
        result = session.run("""
            MATCH (s:Session {id: $session_id})-[:HAS_NOTEBOOK]->(nb:Notebook {id: $notebook_id})
            MATCH (nb)-[:CONTAINS]->(n:Note {id: $note_id})
            RETURN n.id as id, n.title as title, n.content as content,
                   n.created_at as created_at, n.updated_at as updated_at,
                   n.source as source, n.tags as tags, n.metadata as metadata
        """, session_id=session_id, notebook_id=notebook_id, note_id=note_id)
        
        record = result.single()
        if not record:
            driver.close()
            raise HTTPException(status_code=404, detail="Note not found")
        
        note = {
            "id": record["id"],
            "notebook_id": notebook_id,
            "title": record["title"],
            "content": record["content"],
            "created_at": record["created_at"],
            "updated_at": record["updated_at"],
            "tags": record["tags"] or [],
            "metadata": record["metadata"] or {}
        }
        
        if record["source"]:
            note["source"] = record["source"]
    
    driver.close()
    return {"note": note}

@app.post("/api/notebooks/{session_id}/{notebook_id}/notes/create")
async def create_note(session_id: str, notebook_id: str, note: NoteCreate):
    """Create a new note"""
    driver = get_neo4j_driver()
    note_id = str(uuid4())
    now = datetime.utcnow().isoformat()
    
    source_dict = note.source.dict() if note.source else None
    
    with driver.session() as session:
        # Check if notebook exists
        notebook_check = session.run("""
            MATCH (s:Session {id: $session_id})-[:HAS_NOTEBOOK]->(nb:Notebook {id: $notebook_id})
            RETURN nb
        """, session_id=session_id, notebook_id=notebook_id)
        
        if not notebook_check.single():
            driver.close()
            raise HTTPException(status_code=404, detail="Notebook not found")
        
        # Create note
        result = session.run("""
            MATCH (nb:Notebook {id: $notebook_id})
            CREATE (n:Note {
                id: $note_id,
                title: $title,
                content: $content,
                created_at: $now,
                updated_at: $now,
                source: $source,
                tags: $tags,
                metadata: $metadata
            })
            CREATE (nb)-[:CONTAINS]->(n)
            
            // Link to source message if applicable
            WITH n
            UNWIND CASE WHEN $source_message_id IS NOT NULL THEN [$source_message_id] ELSE [] END AS msg_id
            MATCH (m:Message {id: msg_id})
            CREATE (n)-[:CAPTURED_FROM]->(m)
            
            RETURN n
        """, notebook_id=notebook_id, note_id=note_id, title=note.title,
             content=note.content, now=now, source=source_dict,
             tags=note.tags, metadata=note.metadata,
             source_message_id=source_dict.get("message_id") if source_dict else None)
        
        record = result.single()
        if not record:
            driver.close()
            raise HTTPException(status_code=500, detail="Failed to create note")
        
        n = record["n"]
        note_data = {
            "id": n["id"],
            "notebook_id": notebook_id,
            "title": n["title"],
            "content": n["content"],
            "created_at": n["created_at"],
            "updated_at": n["updated_at"],
            "tags": n["tags"] or [],
            "metadata": n["metadata"] or {}
        }
        
        if n["source"]:
            note_data["source"] = n["source"]
    
    driver.close()
    return {"note": note_data}

@app.put("/api/notebooks/{session_id}/{notebook_id}/notes/{note_id}/update")
async def update_note(session_id: str, notebook_id: str, note_id: str, note: NoteUpdate):
    """Update a note"""
    driver = get_neo4j_driver()
    now = datetime.utcnow().isoformat()
    
    update_fields = []
    params = {
        "session_id": session_id,
        "notebook_id": notebook_id,
        "note_id": note_id,
        "now": now
    }
    
    if note.title is not None:
        update_fields.append("n.title = $title")
        params["title"] = note.title
    
    if note.content is not None:
        update_fields.append("n.content = $content")
        params["content"] = note.content
    
    if note.tags is not None:
        update_fields.append("n.tags = $tags")
        params["tags"] = note.tags
    
    if note.metadata is not None:
        update_fields.append("n.metadata = $metadata")
        params["metadata"] = note.metadata
    
    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    update_fields.append("n.updated_at = $now")
    
    with driver.session() as session:
        result = session.run(f"""
            MATCH (s:Session {{id: $session_id}})-[:HAS_NOTEBOOK]->(nb:Notebook {{id: $notebook_id}})
            MATCH (nb)-[:CONTAINS]->(n:Note {{id: $note_id}})
            SET {', '.join(update_fields)}
            RETURN n
        """, **params)
        
        record = result.single()
        if not record:
            driver.close()
            raise HTTPException(status_code=404, detail="Note not found")
        
        n = record["n"]
        note_data = {
            "id": n["id"],
            "notebook_id": notebook_id,
            "title": n["title"],
            "content": n["content"],
            "created_at": n["created_at"],
            "updated_at": n["updated_at"],
            "tags": n["tags"] or [],
            "metadata": n["metadata"] or {}
        }
        
        if n.get("source"):
            note_data["source"] = n["source"]
    
    driver.close()
    return {"note": note_data}

@app.delete("/api/notebooks/{session_id}/{notebook_id}/notes/{note_id}")
async def delete_note(session_id: str, notebook_id: str, note_id: str):
    """Delete a note"""
    driver = get_neo4j_driver()
    
    with driver.session() as session:
        result = session.run("""
            MATCH (s:Session {id: $session_id})-[:HAS_NOTEBOOK]->(nb:Notebook {id: $notebook_id})
            MATCH (nb)-[:CONTAINS]->(n:Note {id: $note_id})
            DETACH DELETE n
            RETURN count(n) as deleted
        """, session_id=session_id, notebook_id=notebook_id, note_id=note_id)
        
        record = result.single()
        if not record or record["deleted"] == 0:
            driver.close()
            raise HTTPException(status_code=404, detail="Note not found")
    
    driver.close()
    return {"success": True}

# ==================== SEARCH ENDPOINTS ====================

@app.post("/api/notebooks/{session_id}/search")
async def search_notes(session_id: str, search: NoteSearch):
    """Search notes across notebooks"""
    driver = get_neo4j_driver()
    
    # Build query filters
    where_clauses = ["toLower(n.title) CONTAINS toLower($query) OR toLower(n.content) CONTAINS toLower($query)"]
    params = {"session_id": session_id, "query": search.query}
    
    if search.notebook_ids:
        where_clauses.append("nb.id IN $notebook_ids")
        params["notebook_ids"] = search.notebook_ids
    
    if search.tags:
        where_clauses.append("ANY(tag IN $tags WHERE tag IN n.tags)")
        params["tags"] = search.tags
    
    if search.source_type:
        where_clauses.append("n.source.type = $source_type")
        params["source_type"] = search.source_type
    
    if search.date_from:
        where_clauses.append("n.created_at >= $date_from")
        params["date_from"] = search.date_from
    
    if search.date_to:
        where_clauses.append("n.created_at <= $date_to")
        params["date_to"] = search.date_to
    
    where_clause = " AND ".join(where_clauses)
    
    with driver.session() as session:
        result = session.run(f"""
            MATCH (s:Session {{id: $session_id}})-[:HAS_NOTEBOOK]->(nb:Notebook)
            MATCH (nb)-[:CONTAINS]->(n:Note)
            WHERE {where_clause}
            RETURN n.id as id, n.title as title, n.content as content,
                   n.created_at as created_at, n.updated_at as updated_at,
                   n.source as source, n.tags as tags, n.metadata as metadata,
                   nb.id as notebook_id, nb.name as notebook_name
            ORDER BY n.updated_at DESC
            LIMIT 50
        """, **params)
        
        results = []
        for record in result:
            # Create excerpt with highlighted search term
            content = record["content"] or ""
            query_lower = search.query.lower()
            
            # Find the position of the search term
            content_lower = content.lower()
            pos = content_lower.find(query_lower)
            
            if pos != -1:
                start = max(0, pos - 50)
                end = min(len(content), pos + len(search.query) + 50)
                excerpt = "..." + content[start:end] + "..."
            else:
                excerpt = content[:100] + "..." if len(content) > 100 else content
            
            results.append({
                "note": {
                    "id": record["id"],
                    "notebook_id": record["notebook_id"],
                    "title": record["title"],
                    "content": record["content"],
                    "created_at": record["created_at"],
                    "updated_at": record["updated_at"],
                    "tags": record["tags"] or [],
                    "metadata": record["metadata"] or {},
                    "source": record["source"]
                },
                "notebook": {
                    "id": record["notebook_id"],
                    "name": record["notebook_name"]
                },
                "relevance_score": 1.0,  # Could implement proper scoring
                "matched_content": excerpt
            })
    
    driver.close()
    return {"results": results, "total": len(results)}

@app.get("/api/notebooks/{session_id}/tags/{tag_name}")
async def get_notes_by_tag(session_id: str, tag_name: str):
    """Get all notes with a specific tag"""
    driver = get_neo4j_driver()
    
    with driver.session() as session:
        result = session.run("""
            MATCH (s:Session {id: $session_id})-[:HAS_NOTEBOOK]->(nb:Notebook)
            MATCH (nb)-[:CONTAINS]->(n:Note)
            WHERE $tag_name IN n.tags
            RETURN n, nb
            ORDER BY n.updated_at DESC
        """, session_id=session_id, tag_name=tag_name)
        
        notes = []
        notebooks_dict = {}
        
        for record in result:
            n = record["n"]
            nb = record["nb"]
            
            notes.append({
                "id": n["id"],
                "notebook_id": nb["id"],
                "title": n["title"],
                "content": n["content"],
                "created_at": n["created_at"],
                "updated_at": n["updated_at"],
                "tags": n["tags"] or [],
                "metadata": n["metadata"] or {}
            })
            
            if nb["id"] not in notebooks_dict:
                notebooks_dict[nb["id"]] = {
                    "id": nb["id"],
                    "name": nb["name"]
                }
    
    driver.close()
    return {
        "notes": notes,
        "notebooks": list(notebooks_dict.values())
    }

@app.get("/api/notebooks/{session_id}/tags")
async def get_all_tags(session_id: str):
    """Get all tags used in session notebooks"""
    driver = get_neo4j_driver()
    
    with driver.session() as session:
        result = session.run("""
            MATCH (s:Session {id: $session_id})-[:HAS_NOTEBOOK]->(nb:Notebook)
            MATCH (nb)-[:CONTAINS]->(n:Note)
            UNWIND n.tags as tag
            WITH tag, count(*) as usage_count
            RETURN tag, usage_count
            ORDER BY usage_count DESC
        """, session_id=session_id)
        
        tags = [{"tag": record["tag"], "count": record["usage_count"]} 
                for record in result]
    
    driver.close()
    return {"tags": tags}

# ==================== EXPORT/IMPORT ENDPOINTS ====================

@app.get("/api/notebooks/{session_id}/{notebook_id}/export")
async def export_notebook(session_id: str, notebook_id: str):
    """Export entire notebook as JSON"""
    driver = get_neo4j_driver()
    
    with driver.session() as session:
        # Get notebook
        nb_result = session.run("""
            MATCH (s:Session {id: $session_id})-[:HAS_NOTEBOOK]->(nb:Notebook {id: $notebook_id})
            RETURN nb
        """, session_id=session_id, notebook_id=notebook_id)
        
        nb_record = nb_result.single()
        if not nb_record:
            driver.close()
            raise HTTPException(status_code=404, detail="Notebook not found")
        
        nb = nb_record["nb"]
        
        # Get all notes
        notes_result = session.run("""
            MATCH (nb:Notebook {id: $notebook_id})-[:CONTAINS]->(n:Note)
            RETURN n
            ORDER BY n.created_at ASC
        """, notebook_id=notebook_id)
        
        notes = []
        for record in notes_result:
            n = record["n"]
            notes.append({
                "id": n["id"],
                "title": n["title"],
                "content": n["content"],
                "created_at": n["created_at"],
                "updated_at": n["updated_at"],
                "tags": n["tags"] or [],
                "metadata": n["metadata"] or {},
                "source": n.get("source")
            })
    
    driver.close()
    
    return {
        "notebook": {
            "id": nb["id"],
            "name": nb["name"],
            "description": nb.get("description"),
            "created_at": nb["created_at"],
            "updated_at": nb["updated_at"]
        },
        "notes": notes,
        "exported_at": datetime.utcnow().isoformat()
    }
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