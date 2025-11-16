# ChatUI API Directory

## Table of Contents
- [Overview](#overview)
- [Architecture](#architecture)
- [API Modules](#api-modules)
- [Request/Response Schemas](#requestresponse-schemas)
- [Session Management](#session-management)
- [WebSocket Protocols](#websocket-protocols)
- [Authentication & Security](#authentication--security)
- [Usage Examples](#usage-examples)
- [Error Handling](#error-handling)
- [Performance](#performance)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

---

## Overview

The ChatUI API directory implements Vera's FastAPI-based backend REST and WebSocket APIs - providing comprehensive endpoints for chat interaction, memory management, knowledge graph operations, toolchain execution, orchestration, and proactive focus management.

**Purpose:** Backend API server for Vera web interface
**Technology:** FastAPI + Pydantic + WebSockets
**Total Endpoints:** 50+ REST endpoints + 5 WebSocket channels
**Files:** 12 modules
**Status:** ✅ Production
**Default Port:** 8888

### Key Features

- **RESTful Architecture**: Standard HTTP methods for CRUD operations
- **WebSocket Streaming**: Real-time bidirectional communication
- **Pydantic Validation**: Type-safe request/response handling
- **Session Management**: Per-user session isolation
- **CORS Support**: Cross-origin resource sharing enabled
- **Async/Await**: Non-blocking I/O operations
- **Error Recovery**: Graceful error handling and logging
- **Rate Limiting**: Request throttling (configurable)

---

## Architecture

### API Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    FastAPI Application                   │
│                      (vera_api.py)                       │
└──────────────────────┬──────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
   ┌────▼────┐   ┌────▼────┐   ┌────▼────┐
   │  Chat   │   │ Memory  │   │  Graph  │
   │   API   │   │   API   │   │   API   │
   └────┬────┘   └────┬────┘   └────┬────┘
        │              │              │
   ┌────▼────┐   ┌────▼────┐   ┌────▼────┐
   │Toolchain│   │Notebook │   │  Focus  │
   │   API   │   │   API   │   │   API   │
   └────┬────┘   └────┬────┘   └────┬────┘
        │              │              │
   ┌────▼────┐   ┌────▼────┐   ┌────▼────┐
   │Orchestr.│   │Vector   │   │ Session │
   │   API   │   │Store API│   │Manager  │
   └─────────┘   └─────────┘   └─────────┘
```

### Request Flow

```
Client Request
    │
    ▼
┌──────────────────┐
│  CORS Middleware │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Router          │
│  (URL matching)  │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Pydantic        │
│  Validation      │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Endpoint        │
│  Handler         │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Vera Instance   │
│  Operations      │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Response        │
│  Serialization   │
└──────────────────┘
```

---

## API Modules

### `vera_api.py` - Main Application

**Purpose:** FastAPI application initialization and router registration

**Size:** ~200 lines

**Application Setup:**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Initialize FastAPI app
app = FastAPI(
    title="Vera AI Chat API",
    description="Multi-agent AI chat system with knowledge graph",
    version="1.0.0",
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc"  # ReDoc
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Production: specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Router Registration
app.include_router(chat_api.router)
app.include_router(chat_api.wsrouter)
app.include_router(memory_api.router)
app.include_router(graph_api.router)
app.include_router(toolchain_api.router)
app.include_router(toolchain_api.wsrouter)
app.include_router(orchestrator_api.router)
app.include_router(vectorstore_api.router)
app.include_router(proactivefocus_api.router)
app.include_router(proactivefocus_api.wsrouter)
app.include_router(session.router)
app.include_router(notebook_api.router)
```

**Health Endpoints:**

```python
@app.get("/health")
async def health_check():
    """
    Health check endpoint

    Response:
        {
            "status": "healthy",
            "timestamp": "2025-01-15T10:00:00Z"
        }
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/info")
async def get_info():
    """
    API information

    Response:
        {
            "name": "Vera AI Chat API",
            "version": "1.0.0",
            "active_sessions": 5
        }
    """
    return {
        "name": "Vera AI Chat API",
        "version": "1.0.0",
        "active_sessions": len(sessions)
    }
```

---

### `chat_api.py` - Chat Endpoints

**Purpose:** Main chat interaction endpoints

**Size:** ~400 lines
**Prefix:** `/api/chat`

**Key Endpoints:**

#### POST `/api/chat` - Send Message

```python
@router.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Send message to Vera and get response

    Request:
        {
            "session_id": "sess_abc123",
            "message": "Hello, Vera!",
            "context": {
                "use_tools": true,
                "stream": false
            }
        }

    Response:
        {
            "response": "Hello! How can I help you?",
            "session_id": "sess_abc123",
            "timestamp": "2025-01-15T10:00:00Z",
            "metadata": {
                "tokens_used": 150,
                "tools_called": []
            }
        }
    """
    if request.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    vera = get_or_create_vera(request.session_id)

    # Add to message history
    sessions[request.session_id]["messages"].append({
        "role": "user",
        "content": request.message,
        "timestamp": datetime.utcnow().isoformat()
    })

    # Get enhanced context
    context = await get_enhanced_context(
        vera,
        request.session_id,
        request.message
    )

    # Execute in thread pool (sync vera.run in async context)
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        result = await loop.run_in_executor(
            executor,
            vera.run,
            request.message
        )

    # Add to message history
    sessions[request.session_id]["messages"].append({
        "role": "assistant",
        "content": result,
        "timestamp": datetime.utcnow().isoformat()
    })

    return ChatResponse(
        response=result,
        session_id=request.session_id,
        timestamp=datetime.utcnow().isoformat()
    )
```

#### WebSocket `/ws/chat/{session_id}` - Streaming Chat

```python
@wsrouter.websocket("/ws/chat/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for streaming chat

    Client -> Server:
        {
            "type": "message",
            "content": "User message"
        }

    Server -> Client (streaming):
        {
            "type": "chunk",
            "content": "Partial response"
        }
        {
            "type": "complete",
            "full_response": "Complete response"
        }
    """
    await websocket.accept()
    websocket_connections[session_id].append(websocket)

    try:
        while True:
            # Receive message
            data = await websocket.receive_json()

            if data["type"] == "message":
                message = data["content"]

                # Stream response
                vera = get_or_create_vera(session_id)

                # Get streaming response
                for chunk in vera.run_streaming(message):
                    await websocket.send_json({
                        "type": "chunk",
                        "content": chunk
                    })

                # Send completion
                await websocket.send_json({
                    "type": "complete",
                    "full_response": "".join(chunks)
                })

    except WebSocketDisconnect:
        websocket_connections[session_id].remove(websocket)
```

#### Enhanced Context Retrieval

```python
async def get_enhanced_context(
    vera,
    session_id: str,
    message: str,
    k: int = 5
) -> Dict[str, Any]:
    """
    Get enhanced context using hybrid retrieval

    Combines:
        1. Session-specific vector search
        2. Long-term semantic search
        3. Graph entity extraction
        4. Subgraph relationships

    Returns:
        {
            "session_context": [...],
            "long_term_context": [...],
            "graph_context": {...},
            "entity_ids": [...]
        }
    """
    try:
        # 1. Session context (working memory)
        session_context = vera.mem.focus_context(
            session_id,
            message,
            k=k
        )

        # 2. Long-term context (persistent memory)
        long_term_context = vera.mem.semantic_retrieve(
            message,
            k=k
        )

        # 3. Extract entity IDs from contexts
        entity_ids = set()
        for hit in session_context + long_term_context:
            metadata = hit.get("metadata", {})
            if "entity_ids" in metadata:
                entity_ids.update(metadata["entity_ids"])
            if metadata.get("type") == "extracted_entity":
                entity_ids.add(hit["id"])

        # 4. Get graph relationships
        graph_context = None
        if entity_ids:
            graph_context = vera.mem.extract_subgraph(
                list(entity_ids)[:3],
                depth=1
            )

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
```

---

### `memory_api.py` - Memory Operations

**Purpose:** Neo4j graph and ChromaDB vector operations

**Size:** ~500 lines
**Prefix:** `/api/memory`

**Key Endpoints:**

#### POST `/api/memory/query` - Query Memory

```python
@router.post("/query", response_model=MemoryQueryResponse)
async def query_memory(request: MemoryQueryRequest):
    """
    Query memory using vector, graph, or hybrid retrieval

    Request:
        {
            "query": "network security",
            "session_id": "sess_123",
            "retrieval_type": "hybrid",
            "k": 10,
            "filters": {
                "type": "insight",
                "project": "security_audit"
            }
        }

    Response:
        {
            "results": [
                {
                    "id": "mem_1",
                    "text": "Security finding...",
                    "score": 0.95,
                    "metadata": {...},
                    "source": "long_term"
                }
            ],
            "retrieval_type": "hybrid",
            "total_results": 15
        }
    """
    vera = get_or_create_vera(request.session_id)
    k = request.k or 50
    results = []

    if request.retrieval_type == "vector":
        # Session memory
        session_results = vera.mem.focus_context(
            request.session_id,
            request.query,
            k=k
        )
        results.extend(normalize_results(session_results, "session"))

        # Long-term memory
        long_term_results = vera.mem.semantic_retrieve(
            request.query,
            k=k,
            where=build_chroma_filters(request.filters)
        )
        results.extend(normalize_results(long_term_results, "long_term"))

    elif request.retrieval_type == "graph":
        # Graph-based search
        results = await search_graph_mode(vera, request.session_id, request.query, k)

    elif request.retrieval_type == "hybrid":
        # Combined search
        results = await hybrid_search(
            vera,
            request.session_id,
            request.query,
            k,
            request.filters
        )

    # Deduplicate and filter
    unique_results = deduplicate_results(results)

    return MemoryQueryResponse(
        results=unique_results,
        retrieval_type=request.retrieval_type,
        total_results=len(unique_results)
    )
```

#### GET `/api/memory/entities` - Get All Entities

```python
@router.get("/entities")
async def get_entities(
    session_id: str,
    limit: int = 100,
    offset: int = 0,
    entity_type: Optional[str] = None
):
    """
    Get entities from knowledge graph

    Query Parameters:
        - session_id: Session identifier
        - limit: Max results (default: 100)
        - offset: Pagination offset (default: 0)
        - entity_type: Filter by type (optional)

    Response:
        {
            "entities": [
                {
                    "id": "entity_1",
                    "name": "Project Alpha",
                    "type": "Project",
                    "properties": {...}
                }
            ],
            "total": 250,
            "limit": 100,
            "offset": 0
        }
    """
    vera = get_or_create_vera(session_id)
    driver = vera.mem.graph._driver

    with driver.session() as db_sess:
        # Build query
        if entity_type:
            query = """
                MATCH (e:Entity {type: $type})
                RETURN e
                SKIP $offset
                LIMIT $limit
            """
            params = {"type": entity_type, "offset": offset, "limit": limit}
        else:
            query = """
                MATCH (e:Entity)
                RETURN e
                SKIP $offset
                LIMIT $limit
            """
            params = {"offset": offset, "limit": limit}

        result = db_sess.run(query, params)
        entities = [dict(record["e"]) for record in result]

    return {
        "entities": entities,
        "total": len(entities),
        "limit": limit,
        "offset": offset
    }
```

#### GET `/api/memory/relationships` - Get Relationships

```python
@router.get("/relationships")
async def get_relationships(
    session_id: str,
    source_id: Optional[str] = None,
    target_id: Optional[str] = None,
    relationship_type: Optional[str] = None
):
    """
    Get relationships from knowledge graph

    Response:
        {
            "relationships": [
                {
                    "id": "rel_1",
                    "source": "entity_1",
                    "target": "entity_2",
                    "type": "RELATED_TO",
                    "properties": {...}
                }
            ]
        }
    """
    vera = get_or_create_vera(session_id)
    driver = vera.mem.graph._driver

    with driver.session() as db_sess:
        # Build query based on filters
        query = "MATCH (a)-[r"
        params = {}

        if relationship_type:
            query += f":{relationship_type}"

        query += "]->(b) "

        if source_id:
            query += "WHERE id(a) = $source_id "
            params["source_id"] = source_id

        if target_id:
            if source_id:
                query += "AND id(b) = $target_id "
            else:
                query += "WHERE id(b) = $target_id "
            params["target_id"] = target_id

        query += "RETURN a, r, b LIMIT 1000"

        result = db_sess.run(query, params)
        relationships = []

        for record in result:
            relationships.append({
                "source": dict(record["a"]),
                "relationship": dict(record["r"]),
                "target": dict(record["b"])
            })

    return {"relationships": relationships}
```

#### POST `/api/memory/extract_entities` - Extract Entities

```python
@router.post("/extract_entities", response_model=EntityExtractionResponse)
async def extract_entities(request: EntityExtractionRequest):
    """
    Extract entities from text using NLP

    Request:
        {
            "text": "Apple Inc. is headquartered in Cupertino.",
            "session_id": "sess_123",
            "save_to_graph": true
        }

    Response:
        {
            "entities": [
                {
                    "text": "Apple Inc.",
                    "type": "ORGANIZATION",
                    "start": 0,
                    "end": 10
                },
                {
                    "text": "Cupertino",
                    "type": "LOCATION",
                    "start": 33,
                    "end": 42
                }
            ],
            "relationships": [
                {
                    "source": "Apple Inc.",
                    "target": "Cupertino",
                    "type": "LOCATED_IN"
                }
            ]
        }
    """
    vera = get_or_create_vera(request.session_id)

    # Extract entities using NLP
    from Memory.nlp import extract_entities, extract_relationships

    entities = extract_entities(request.text)
    relationships = extract_relationships(request.text)

    # Optionally save to graph
    if request.save_to_graph:
        for entity in entities:
            vera.mem.add_entity(
                name=entity["text"],
                entity_type=entity["type"],
                properties={"extracted_from_session": request.session_id}
            )

        for rel in relationships:
            vera.mem.add_relationship(
                source=rel["source"],
                target=rel["target"],
                relationship_type=rel["type"]
            )

    return EntityExtractionResponse(
        entities=entities,
        relationships=relationships
    )
```

#### GET `/api/memory/subgraph/{entity_id}` - Extract Subgraph

```python
@router.get("/subgraph/{entity_id}")
async def get_subgraph(
    entity_id: str,
    session_id: str,
    depth: int = 2,
    max_nodes: int = 50
):
    """
    Extract subgraph around entity

    Response:
        {
            "nodes": [...],
            "edges": [...],
            "center_entity": {...}
        }
    """
    vera = get_or_create_vera(session_id)
    subgraph = vera.mem.extract_subgraph(
        entity_ids=[entity_id],
        depth=depth,
        max_nodes=max_nodes
    )

    return subgraph
```

---

### `graph_api.py` - Graph Visualization

**Purpose:** Knowledge graph data for visualization

**Size:** ~300 lines
**Prefix:** `/api/graph`

**Key Endpoints:**

#### GET `/api/graph/session/{session_id}` - Get Session Graph

```python
@router.get("/session/{session_id}", response_model=GraphResponse)
async def get_session_graph(session_id: str):
    """
    Get complete graph for visualization

    Response:
        {
            "nodes": [
                {
                    "id": "node_1",
                    "label": "Entity",
                    "title": "Entity: Name",
                    "color": "#4CAF50",
                    "type": "entity"
                }
            ],
            "edges": [
                {
                    "id": "edge_1",
                    "from": "node_1",
                    "to": "node_2",
                    "label": "RELATED_TO",
                    "arrows": "to"
                }
            ]
        }
    """
    vera = get_or_create_vera(session_id)
    driver = vera.mem.graph._driver

    nodes = []
    edges = []

    with driver.session() as db_sess:
        # Get all nodes for session
        result = db_sess.run("""
            MATCH (n)
            WHERE n.session_id = $session_id OR
                  n.extracted_from_session = $session_id
            OPTIONAL MATCH path = (n)-[r*0..3]-(connected)
            WITH collect(DISTINCT connected) + collect(DISTINCT n) AS nodes,
                 collect(DISTINCT relationships(path)) AS rels
            UNWIND rels AS rel_list
            UNWIND rel_list AS rel
            RETURN DISTINCT nodes, collect(DISTINCT rel) AS relationships
        """, {"session_id": session_id})

        # Process nodes
        seen_nodes = set()
        for record in result:
            for node in record.get("nodes", []):
                if node and node.get("id") not in seen_nodes:
                    seen_nodes.add(node["id"])

                    # Color by type
                    color = get_node_color(node.get("type"))

                    nodes.append(GraphNode(
                        id=node["id"],
                        label=node.get("type", "node"),
                        title=f"{node.get('type')}: {node.get('text', node['id'])}",
                        color=color,
                        type=node.get("type")
                    ))

        # Process edges
        seen_edges = set()
        for record in result:
            for rel in record.get("relationships", []):
                if rel:
                    edge_id = f"{rel.start_node['id']}-{rel.end_node['id']}"
                    if edge_id not in seen_edges:
                        seen_edges.add(edge_id)

                        edges.append(GraphEdge(
                            id=edge_id,
                            from_node=rel.start_node["id"],
                            to_node=rel.end_node["id"],
                            label=rel.type,
                            arrows="to"
                        ))

    return GraphResponse(nodes=nodes, edges=edges)

def get_node_color(node_type: str) -> str:
    """Get color for node type"""
    colors = {
        "thought": "#f59e0b",
        "memory": "#f59e0b",
        "decision": "#ef4444",
        "plan": "#8b5cf6",
        "tool": "#f97316",
        "entity": "#10b93a",
        "session": "#3f1b92",
        "default": "#3b82f6"
    }
    return colors.get(node_type.lower(), colors["default"])
```

---

### `toolchain_api.py` - Tool Execution

**Purpose:** Toolchain planning and execution

**Size:** ~450 lines
**Prefix:** `/api/toolchain`

**Key Endpoints:**

#### POST `/api/toolchain/execute` - Execute Tool Chain

```python
@router.post("/execute")
async def execute_toolchain(request: ToolchainRequest):
    """
    Execute tool chain

    Request:
        {
            "query": "Search for AI news and summarize",
            "strategy": "hybrid",
            "session_id": "sess_123"
        }

    Response:
        {
            "execution_id": "exec_abc",
            "status": "started",
            "plan": [...]
        }
    """
    vera = get_or_create_vera(request.session_id)
    execution_id = str(uuid4())

    # Create execution record
    toolchain_executions[request.session_id][execution_id] = {
        "id": execution_id,
        "query": request.query,
        "strategy": request.strategy,
        "status": "started",
        "started_at": datetime.utcnow().isoformat(),
        "plan": None,
        "results": []
    }

    # Execute in background
    asyncio.create_task(
        execute_toolchain_background(
            execution_id,
            request,
            vera
        )
    )

    return {
        "execution_id": execution_id,
        "status": "started"
    }
```

#### WebSocket `/ws/toolchain/{execution_id}` - Stream Execution

```python
@wsrouter.websocket("/ws/toolchain/{execution_id}")
async def toolchain_stream(websocket: WebSocket, execution_id: str):
    """
    Stream tool execution updates

    Server -> Client messages:
        - {"type": "plan", "plan": [...]}
        - {"type": "step_start", "step_num": 1, "tool": "..."}
        - {"type": "step_complete", "step_num": 1, "output": "..."}
        - {"type": "complete", "result": "..."}
        - {"type": "error", "message": "..."}
    """
    await websocket.accept()

    try:
        # Wait for execution to complete, streaming updates
        execution = toolchain_executions.get(execution_id)

        while execution["status"] != "complete":
            # Send updates
            if execution.get("current_step"):
                await websocket.send_json({
                    "type": "step_update",
                    "step": execution["current_step"]
                })

            await asyncio.sleep(0.5)

        # Send final result
        await websocket.send_json({
            "type": "complete",
            "result": execution["result"]
        })

    except WebSocketDisconnect:
        pass
```

---

### `orchestrator_api.py` - Orchestration

**Purpose:** Distributed worker pool management

**Size:** ~600 lines
**Prefix:** `/orchestrator`

**Key Endpoints:**

#### POST `/orchestrator/init` - Initialize Orchestrator

```python
@router.post("/init")
async def initialize_orchestrator(config: WorkerPoolConfig):
    """
    Initialize worker pool

    Request:
        {
            "worker_count": 4,
            "cpu_threshold": 85.0,
            "max_processes": 24
        }
    """
    state.local_pool = PriorityWorkerPool(
        worker_count=config.worker_count
    )

    return {"status": "initialized"}
```

#### POST `/orchestrator/task/submit` - Submit Task

```python
@router.post("/task/submit")
async def submit_task(task: TaskSubmission):
    """
    Submit task to orchestrator

    Request:
        {
            "name": "task_name",
            "payload": {...},
            "priority": "HIGH",
            "labels": ["gpu"]
        }
    """
    task_id = state.local_pool.submit_task(
        name=task.name,
        payload=task.payload,
        priority=Priority[task.priority],
        labels=task.labels
    )

    return {"task_id": task_id}
```

#### GET `/orchestrator/status` - Get Status

```python
@router.get("/status")
async def get_status():
    """
    Get orchestrator status

    Response:
        {
            "worker_pool": {
                "active_workers": 4,
                "pending_tasks": 12
            },
            "system_metrics": {
                "cpu_percent": 45.2,
                "memory_percent": 62.1
            }
        }
    """
    return {
        "worker_pool": {
            "active_workers": len(state.local_pool.workers),
            "pending_tasks": state.local_pool.queue.qsize()
        },
        "system_metrics": {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent
        }
    }
```

---

### `proactivefocus_api.py` - Proactive Focus

**Purpose:** Background thinking and focus boards

**Size:** ~400 lines
**Prefix:** `/api/focus`

**Key Endpoints:**

#### POST `/api/focus/start` - Start Focus Session

```python
@router.post("/start")
async def start_focus(request: FocusRequest):
    """
    Start proactive focus session

    Request:
        {
            "topic": "network security",
            "duration_minutes": 30,
            "session_id": "sess_123"
        }
    """
    focus_id = str(uuid4())

    # Create focus manager
    focus_manager = ProactiveFocusManager(
        topic=request.topic,
        duration=request.duration_minutes
    )

    # Run in background
    asyncio.create_task(
        focus_manager.run_async(focus_id)
    )

    return {"focus_id": focus_id}
```

#### GET `/api/focus/board/{session_id}` - Get Focus Board

```python
@router.get("/board/{session_id}")
async def get_focus_board(session_id: str):
    """
    Get current focus board

    Response:
        {
            "progress": ["Completed X", "Analyzed Y"],
            "next_steps": ["Do A", "Then B"],
            "issues": ["Problem 1"],
            "ideas": ["Idea 1", "Idea 2"],
            "actions": ["Action 1"]
        }
    """
    board = load_focus_board(session_id)
    return board
```

---

### `notebook_api.py` - Notebook System

**Purpose:** Note-taking and markdown management

**Size:** ~250 lines
**Prefix:** `/api/notebook`

**Key Endpoints:**

```python
@router.post("/create")
async def create_notebook(request: NotebookCreateRequest):
    """Create new notebook"""

@router.post("/{notebook_id}/note")
async def create_note(notebook_id: str, note: NoteRequest):
    """Add note to notebook"""

@router.get("/{notebook_id}")
async def get_notebook(notebook_id: str):
    """Get notebook with all notes"""
```

---

### `vectorstore_api.py` - Vector Operations

**Purpose:** Direct ChromaDB operations

**Size:** ~200 lines
**Prefix:** `/api/vectorstore`

---

### `session.py` - Session Management

**Purpose:** Session lifecycle management

**Size:** ~200 lines

**Global State:**

```python
# Session storage
sessions: Dict[str, Dict] = {}
vera_instances: Dict[str, Vera] = {}
toolchain_executions: Dict[str, Dict] = {}
active_toolchains: Dict[str, str] = {}
websocket_connections: Dict[str, List[WebSocket]] = defaultdict(list)
```

**Functions:**

```python
def get_or_create_vera(session_id: str) -> Vera:
    """Get or create Vera instance for session"""
    if session_id not in vera_instances:
        vera_instances[session_id] = Vera()
    return vera_instances[session_id]

async def cleanup_session(session_id: str):
    """Cleanup session resources"""
    # Close WebSockets
    for ws in websocket_connections[session_id]:
        await ws.close()

    # Remove from caches
    del sessions[session_id]
    del vera_instances[session_id]
```

**Endpoints:**

```python
@router.post("/api/session/start")
async def start_session():
    """Create new session"""
    session_id = f"sess_{uuid4().hex[:12]}"
    sessions[session_id] = {
        "created_at": datetime.utcnow().isoformat(),
        "messages": []
    }
    return {"session_id": session_id}
```

---

### `schemas.py` - Pydantic Models

**Purpose:** Request/response validation

**Size:** ~300 lines

**Core Schemas:**

```python
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class ChatRequest(BaseModel):
    """Chat message request"""
    session_id: str
    message: str
    context: Optional[Dict[str, Any]] = {}

class ChatResponse(BaseModel):
    """Chat message response"""
    response: str
    session_id: str
    timestamp: str
    metadata: Optional[Dict] = {}

class MemoryQueryRequest(BaseModel):
    """Memory query request"""
    query: str
    session_id: str
    retrieval_type: str = "hybrid"  # vector, graph, hybrid
    k: int = 10
    filters: Optional[Dict] = {}

class MemoryQueryResponse(BaseModel):
    """Memory query response"""
    results: List[Dict]
    retrieval_type: str
    total_results: int

class GraphNode(BaseModel):
    """Graph node for visualization"""
    id: str
    label: str
    title: str
    color: str
    type: Optional[str] = None

class GraphEdge(BaseModel):
    """Graph edge for visualization"""
    id: str
    from_node: str = Field(..., alias="from")
    to_node: str = Field(..., alias="to")
    label: str
    arrows: str = "to"

class GraphResponse(BaseModel):
    """Graph visualization response"""
    nodes: List[GraphNode]
    edges: List[GraphEdge]
```

---

### `logging_config.py` - Logging Setup

**Purpose:** Centralized logging configuration

```python
import logging
from logging.handlers import RotatingFileHandler

def setup_logging(log_level=logging.INFO):
    """Configure application logging"""

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # File handler with rotation
    file_handler = RotatingFileHandler(
        'logs/api.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
```

---

## Usage Examples

### Starting the Server

```bash
# Using uvicorn
uvicorn Vera.ChatUI.api.vera_api:app --host 0.0.0.0 --port 8888 --reload

# Using Python
python -m uvicorn Vera.ChatUI.api.vera_api:app --host 0.0.0.0 --port 8888
```

### Client Examples

**Python Client:**

```python
import requests
import json

# Start session
response = requests.post('http://localhost:8888/api/session/start')
session_id = response.json()['session_id']

# Send message
response = requests.post('http://localhost:8888/api/chat', json={
    'session_id': session_id,
    'message': 'Hello, Vera!'
})
print(response.json()['response'])

# Query memory
response = requests.post('http://localhost:8888/api/memory/query', json={
    'query': 'security findings',
    'session_id': session_id,
    'retrieval_type': 'hybrid',
    'k': 10
})
results = response.json()['results']
```

**JavaScript Client:**

```javascript
// Start session
const sessionResponse = await fetch('http://localhost:8888/api/session/start', {
    method: 'POST'
});
const { session_id } = await sessionResponse.json();

// Send message
const chatResponse = await fetch('http://localhost:8888/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        session_id: session_id,
        message: 'Hello, Vera!'
    })
});
const { response } = await chatResponse.json();
```

---

## Error Handling

### Standard Error Response

```json
{
    "detail": "Error message",
    "status_code": 400
}
```

### Common HTTP Status Codes

- `200` - Success
- `400` - Bad Request (invalid input)
- `404` - Not Found (session/resource not found)
- `500` - Internal Server Error
- `503` - Service Unavailable

### Error Handling Example

```python
from fastapi import HTTPException

@router.post("/api/example")
async def example_endpoint(request: ExampleRequest):
    try:
        # Process request
        result = process(request)
        return {"result": result}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
```

---

## Performance

### Optimization Techniques

**1. Async Operations:**
```python
# Use async for I/O operations
async def fetch_data():
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()
```

**2. Connection Pooling:**
```python
# Reuse database connections
@router.on_event("startup")
async def startup():
    app.state.db_pool = create_db_pool()
```

**3. Caching:**
```python
from functools import lru_cache

@lru_cache(maxsize=100)
def expensive_operation(param):
    # Cached result
    return result
```

---

## Testing

### Unit Tests

```python
from fastapi.testclient import TestClient
from Vera.ChatUI.api.vera_api import app

client = TestClient(app)

def test_start_session():
    response = client.post("/api/session/start")
    assert response.status_code == 200
    assert "session_id" in response.json()

def test_chat():
    # Start session
    session_response = client.post("/api/session/start")
    session_id = session_response.json()["session_id"]

    # Send message
    response = client.post("/api/chat", json={
        "session_id": session_id,
        "message": "Hello"
    })
    assert response.status_code == 200
    assert "response" in response.json()
```

---

## Troubleshooting

### Common Issues

**CORS Errors:**
```python
# Ensure CORS is configured
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"]
)
```

**Session Not Found:**
```python
# Verify session exists before operations
if session_id not in sessions:
    raise HTTPException(status_code=404, detail="Session not found")
```

**WebSocket Connection Failed:**
```javascript
// Add reconnection logic
websocket.onclose = () => {
    setTimeout(() => connectWebSocket(), 1000);
};
```

---

## Related Documentation

- [Main ChatUI README](../README.md)
- [JavaScript Frontend](../js/README.md)
- [Memory System](../../Memory/README.md)
- [Toolchain](../../Toolchain/README.md)

---

**Last Updated:** January 2025
**Maintainer:** Vera-AI Development Team
**Version:** 1.0.0
