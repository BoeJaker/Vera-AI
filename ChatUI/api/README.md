# ChatUI API

## Overview

The **ChatUI API** provides the backend endpoints for Vera's web interface, implementing REST and WebSocket APIs for real-time communication, toolchain monitoring, memory exploration, and system management.

## Purpose

The API layer enables:
- **Real-time chat** via WebSocket connections
- **Toolchain execution** monitoring and control
- **Memory queries** and graph exploration
- **System status** and health monitoring
- **Session management** and persistence
- **Proactive cognition** dashboard integration

## Architecture

```
Frontend (JavaScript) ←→ FastAPI Backend ←→ Vera Core
        ↓                      ↓                ↓
    HTTP/WebSocket         Routing          Agents/Memory/Tools
```

All backend endpoints are built with FastAPI for high-performance async handling.

## Key Files

| File | Purpose |
|------|---------|
| `vera_api.py` | Main FastAPI application and endpoint aggregation |
| `chat_api.py` | WebSocket chat interface and message handling |
| `toolchain_api.py` | Toolchain execution monitoring and control |
| `graph_api.py` | Neo4j knowledge graph queries and visualization |
| `memory_api.py` | Memory search, retrieval, and session management |
| `proactivefocus_api.py` | Background cognition status and focus board |
| `vectorstore_api.py` | ChromaDB vector database queries |
| `notebook_api.py` | Document and notebook management |
| `orchestrator_api.py` | CEO orchestrator status and resource monitoring |
| `session.py` | Session management and state persistence |
| `schemas.py` | Pydantic data models for request/response validation |
| `logging_config.py` | Structured logging configuration |

## Technologies

- **FastAPI** - Modern async Python web framework
- **WebSocket** - Real-time bidirectional communication
- **Pydantic** - Data validation and serialization
- **Uvicorn** - ASGI server
- **CORS Middleware** - Cross-origin request handling

## API Endpoints

### Chat API (`chat_api.py`)

#### WebSocket Connection
```
WS /ws/chat?session_id={session_id}
```

**Message Format:**
```json
{
  "message": "Explain Vera's memory system",
  "session_id": "session_abc123",
  "context": {
    "active_project": "auth_system_2024"
  }
}
```

**Response Stream:**
```json
{
  "type": "chunk",
  "content": "Vera's memory system consists of...",
  "role": "assistant"
}
```

#### REST Endpoints
```http
POST /api/chat/message
GET  /api/chat/history?session_id={id}&limit=50
DELETE /api/chat/clear?session_id={id}
GET  /api/chat/sessions
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is quantum computing?",
    "session_id": "session_123"
  }'
```

---

### Toolchain API (`toolchain_api.py`)

#### Execute Toolchain
```http
POST /api/toolchain/execute
Content-Type: application/json

{
  "query": "Analyze network security",
  "strategy": "hybrid",
  "timeout": 300
}
```

**Response:**
```json
{
  "execution_id": "exec_abc123",
  "status": "running",
  "steps": [
    {
      "step_number": 1,
      "tool": "NetworkScanner",
      "status": "completed",
      "duration": 3.2
    },
    {
      "step_number": 2,
      "tool": "VulnerabilityAnalyzer",
      "status": "running",
      "progress": 0.65
    }
  ]
}
```

#### Get Execution Status
```http
GET /api/toolchain/status/{execution_id}
```

#### Toolchain History
```http
GET /api/toolchain/history?limit=20
```

#### Replay Last Plan
```http
POST /api/toolchain/replay
```

---

### Graph API (`graph_api.py`)

#### Execute Cypher Query
```http
POST /api/graph/query
Content-Type: application/json

{
  "cypher": "MATCH (p:Project)-[:CONTAINS]->(d:Document) RETURN p, d LIMIT 10"
}
```

#### Get Subgraph
```http
POST /api/graph/subgraph
Content-Type: application/json

{
  "entity_id": "Project_X",
  "depth": 2,
  "relationship_types": ["USES", "CONTAINS", "RELATED_TO"]
}
```

**Response:**
```json
{
  "nodes": [
    {
      "id": "Project_X",
      "type": "Project",
      "properties": {"name": "Authentication System", "status": "active"}
    },
    {
      "id": "Doc_123",
      "type": "Document",
      "properties": {"title": "OAuth2 Specification"}
    }
  ],
  "edges": [
    {
      "source": "Project_X",
      "target": "Doc_123",
      "type": "REFERENCES"
    }
  ]
}
```

#### Get Entity Details
```http
GET /api/graph/entity/{entity_id}
```

#### Search Entities
```http
POST /api/graph/search
Content-Type: application/json

{
  "query": "authentication",
  "entity_types": ["Project", "Document", "Code"],
  "limit": 10
}
```

#### Graph Statistics
```http
GET /api/graph/statistics
```

**Response:**
```json
{
  "total_nodes": 15420,
  "total_relationships": 45890,
  "node_types": {
    "Project": 45,
    "Document": 1230,
    "Memory": 8900,
    "Session": 450
  },
  "relationship_types": {
    "CONTAINS": 5600,
    "RELATED_TO": 12300,
    "USES": 3400
  }
}
```

---

### Memory API (`memory_api.py`)

#### Semantic Search
```http
POST /api/memory/search
Content-Type: application/json

{
  "query": "how to implement JWT tokens",
  "layers": [2, 3],
  "top_k": 10,
  "include_relationships": true,
  "filters": {
    "tags": ["security", "authentication"]
  }
}
```

**Response:**
```json
{
  "results": [
    {
      "content": "JWT tokens should include expiration claims...",
      "relevance": 0.92,
      "entity_id": "Memory_xyz789",
      "tags": ["security", "jwt", "authentication"],
      "relationships": [
        {"type": "RELATED_TO", "target": "Project_auth_system"}
      ],
      "session_id": "session_abc123",
      "timestamp": "2024-01-15T14:30:00Z"
    }
  ],
  "total": 10,
  "search_time_ms": 45.3
}
```

#### Get Session
```http
GET /api/memory/session/{session_id}
```

#### List Sessions
```http
GET /api/memory/sessions?limit=50&offset=0&sort=desc
```

#### Promote to Long-Term Memory
```http
POST /api/memory/promote
Content-Type: application/json

{
  "session_id": "session_abc123",
  "thought_id": "thought_xyz789",
  "create_entity": true,
  "entity_type": "Insight"
}
```

#### Memory Statistics
```http
GET /api/memory/stats
```

**Response:**
```json
{
  "short_term_entries": 15,
  "working_memory_sessions": 8,
  "long_term_documents": 12450,
  "archived_records": 98760,
  "total_memory_mb": 2340,
  "vector_collections": 45,
  "graph_nodes": 15420
}
```

---

### Proactive Focus API (`proactivefocus_api.py`)

#### PBC Status
```http
GET /api/pbc/status
```

**Response:**
```json
{
  "active": true,
  "thoughts_generated": 142,
  "thoughts_executed": 128,
  "success_rate": 0.901,
  "queue_depth": 3,
  "worker_utilization": 0.68,
  "last_tick": "2024-01-15T14:32:00Z",
  "next_tick": "2024-01-15T14:33:00Z"
}
```

#### Get Focus Board
```http
GET /api/pbc/focus-board
```

**Response:**
```json
{
  "progress": [
    {
      "task": "Complete JWT implementation",
      "status": "in_progress",
      "completion": 0.75
    }
  ],
  "ideas": [
    {
      "idea": "Add Redis caching layer",
      "priority": "medium",
      "feasibility": 0.8
    }
  ],
  "actions": [
    {
      "action": "Research JWT best practices",
      "scheduled": "2024-01-15T15:00:00Z"
    }
  ],
  "issues": []
}
```

#### Trigger Manual PBC Cycle
```http
POST /api/pbc/trigger
```

#### Get Recent Thoughts
```http
GET /api/pbc/thoughts?limit=20
```

---

### Vector Store API (`vectorstore_api.py`)

#### Search Vectors
```http
POST /api/vectorstore/search
Content-Type: application/json

{
  "query_text": "OAuth2 implementation guide",
  "collection": "long_term_docs",
  "top_k": 5,
  "filters": {"tags": ["security"]}
}
```

#### List Collections
```http
GET /api/vectorstore/collections
```

#### Add Documents
```http
POST /api/vectorstore/add
Content-Type: application/json

{
  "collection": "session_123",
  "documents": [
    {
      "text": "Document content...",
      "metadata": {"source": "web", "timestamp": "2024-01-15"}
    }
  ]
}
```

#### Clear Collection
```http
DELETE /api/vectorstore/clear?collection=session_123
```

---

### Orchestrator API (`orchestrator_api.py`)

#### System Status
```http
GET /api/orchestrator/status
```

**Response:**
```json
{
  "active_agents": 5,
  "queued_tasks": 12,
  "worker_pool": {
    "local_workers": 4,
    "remote_workers": 2,
    "active_tasks": 3
  },
  "resources": {
    "llm_usage": {
      "fast_llm": {"active": 1, "queued": 0},
      "deep_llm": {"active": 2, "queued": 3}
    },
    "memory_usage_mb": 3456,
    "cpu_usage_percent": 68.5
  },
  "health": "healthy",
  "uptime_seconds": 86400
}
```

#### Active Agents
```http
GET /api/orchestrator/agents
```

#### Resource Allocation
```http
GET /api/orchestrator/resources
```

---

## Data Models (`schemas.py`)

Pydantic models for request/response validation:

### Message Schema
```python
class ChatMessage(BaseModel):
    message: str
    session_id: str
    context: Optional[Dict] = None
    stream: bool = True

class ChatResponse(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime
    session_id: str
```

### Toolchain Schema
```python
class ToolchainRequest(BaseModel):
    query: str
    strategy: str = "hybrid"  # "batch", "step", "hybrid"
    timeout: int = 300

class ToolchainStatus(BaseModel):
    execution_id: str
    status: str  # "pending", "running", "completed", "failed"
    steps: List[ToolStep]
    progress: float
```

### Memory Search Schema
```python
class MemorySearchRequest(BaseModel):
    query: str
    layers: List[int] = [2, 3]  # Memory layers
    top_k: int = 10
    include_relationships: bool = False
    filters: Optional[Dict] = None

class MemorySearchResult(BaseModel):
    content: str
    relevance: float
    entity_id: str
    tags: List[str]
    timestamp: datetime
```

## Session Management (`session.py`)

### Session Creation
```python
from session import create_session

session = create_session(user_id="user_123")
# Returns: {"session_id": "session_abc123", "created_at": "..."}
```

### Session Persistence
Sessions stored in:
- **Cookies** (browser)
- **Redis** (optional, for distributed deployment)
- **Neo4j** (long-term archival)

### Session State
```python
class Session:
    session_id: str
    user_id: Optional[str]
    created_at: datetime
    last_active: datetime
    preferences: Dict
    active_project: Optional[str]
    chat_history: List[Message]
```

## Logging (`logging_config.py`)

Structured logging with context:

```python
logger.info(
    "Toolchain execution started",
    extra={
        "execution_id": "exec_123",
        "query": "Analyze security",
        "session_id": "session_abc"
    }
)
```

**Log Output:**
```json
{
  "timestamp": "2024-01-15T14:30:00Z",
  "level": "INFO",
  "message": "Toolchain execution started",
  "execution_id": "exec_123",
  "query": "Analyze security",
  "session_id": "session_abc"
}
```

## Configuration

### Environment Variables
```bash
# API Server
API_HOST=0.0.0.0
API_PORT=8000
WORKERS=4

# CORS
CORS_ORIGINS=http://localhost:3000,https://vera.example.com

# WebSocket
WS_MAX_CONNECTIONS=100
WS_PING_INTERVAL=30

# Session
SESSION_TIMEOUT=3600
SESSION_SECRET_KEY=your-secret-key

# Redis (optional)
REDIS_URL=redis://localhost:6379/0

# Logging
LOG_LEVEL=INFO
LOG_FILE=/var/log/vera-api.log
LOG_FORMAT=json
```

## Running the API

### Development
```bash
cd ChatUI/api

# Run with auto-reload
uvicorn vera_api:app --reload --host 0.0.0.0 --port 8000

# With logging
uvicorn vera_api:app --reload --log-level debug
```

### Production
```bash
# With Gunicorn (4 workers)
gunicorn vera_api:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --access-logfile /var/log/vera-access.log \
  --error-logfile /var/log/vera-error.log
```

### Docker
```bash
docker run -d \
  --name vera-api \
  -p 8000:8000 \
  -e API_HOST=0.0.0.0 \
  -e API_PORT=8000 \
  vera-api:latest
```

## Security

### API Key Authentication (Optional)
```python
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPBearer

security = HTTPBearer()

async def verify_api_key(credentials = Security(security)):
    if credentials.credentials != os.getenv("API_KEY"):
        raise HTTPException(status_code=401)
    return credentials

@app.get("/api/protected", dependencies=[Depends(verify_api_key)])
async def protected_endpoint():
    return {"message": "Authenticated"}
```

### Rate Limiting
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/api/chat/message")
@limiter.limit("30/minute")
async def send_message(request: Request, message: ChatMessage):
    ...
```

### CORS Configuration
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## WebSocket Protocol

### Connection Flow
```
Client                          Server
  |------ Connect WS ----------->|
  |<----- Accept Connection -----|
  |                              |
  |------ Send Message --------->|
  |                              | (Process with Vera)
  |<----- Stream Chunks ---------|
  |<----- Stream Chunks ---------|
  |<----- Final Chunk ----------|
  |                              |
  |------ Ping --------------->|
  |<----- Pong -----------------|
```

### Message Types
```json
// User message
{"type": "message", "content": "...", "session_id": "..."}

// Response chunk
{"type": "chunk", "content": "...", "role": "assistant"}

// Status update
{"type": "status", "status": "thinking|responding|complete"}

// Error
{"type": "error", "message": "...", "code": 500}
```

## Error Handling

### Standard Error Response
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid session_id format",
    "details": {
      "field": "session_id",
      "value": "invalid_id"
    }
  },
  "timestamp": "2024-01-15T14:30:00Z"
}
```

### HTTP Status Codes
- **200 OK** - Successful request
- **201 Created** - Resource created
- **400 Bad Request** - Invalid input
- **401 Unauthorized** - Missing/invalid auth
- **404 Not Found** - Resource not found
- **429 Too Many Requests** - Rate limit exceeded
- **500 Internal Server Error** - Server error

## Testing

### Unit Tests
```python
from fastapi.testclient import TestClient
from vera_api import app

client = TestClient(app)

def test_chat_endpoint():
    response = client.post("/api/chat/message", json={
        "message": "Hello",
        "session_id": "test_session"
    })
    assert response.status_code == 200
    assert "content" in response.json()
```

### Integration Tests
```bash
pytest tests/api/ -v --cov=ChatUI/api
```

## Performance

### Caching
```python
from functools import lru_cache

@lru_cache(maxsize=100)
async def get_cached_graph_stats():
    return await fetch_graph_statistics()
```

### Async Optimization
All database queries use async/await for non-blocking I/O.

### Response Compression
```python
from fastapi.middleware.gzip import GZipMiddleware

app.add_middleware(GZipMiddleware, minimum_size=1000)
```

## Troubleshooting

### WebSocket Connection Fails
```bash
# Check server status
curl http://localhost:8000/health

# Test WebSocket
wscat -c ws://localhost:8000/ws/chat?session_id=test
```

### High Latency
```bash
# Check database connections
# Neo4j
curl http://localhost:7474

# ChromaDB
curl http://localhost:8000/api/v1/heartbeat
```

### Memory Leaks
```bash
# Monitor memory usage
py-spy top --pid $(pgrep -f vera_api)
```

## Related Documentation

- [ChatUI Frontend](../README.md)
- [Memory System](../../Memory/)
- [Toolchain Engine](../../Toolchain/)
- [Proactive Background Cognition](../../BackgroundCognition/)

---

**Related Components:**
- [JavaScript Frontend](../js/) - Client-side API consumption
- [Vera Core](../../vera.py) - Backend processing
- [Memory](../../Memory/) - Data storage
