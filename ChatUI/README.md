# ChatUI Directory

## Table of Contents
- [Overview](#overview)
- [Architecture](#architecture)
- [Directory Structure](#directory-structure)
- [API Modules](#api-modules)
- [Frontend JavaScript](#frontend-javascript)
- [UI Components](#ui-components)
- [WebSocket Communication](#websocket-communication)
- [Session Management](#session-management)
- [Usage Examples](#usage-examples)
- [Configuration](#configuration)
- [Development Guide](#development-guide)
- [Performance](#performance)
- [Troubleshooting](#troubleshooting)

---

## Overview

The ChatUI directory implements Vera's comprehensive web interface - a sophisticated multi-panel dashboard that provides real-time interaction with the AI agent through chat, knowledge graph visualization, memory exploration, notebook management, and distributed orchestration monitoring.

**Purpose:** Unified web interface for all Vera AI interactions
**Technology Stack:** FastAPI (backend) + Vanilla JavaScript (frontend) + WebSockets (real-time)
**Size:** 28 files across 5 subdirectories
**Status:** ✅ Production
**Server Port:** 8888 (default)

### Key Capabilities

- **Multi-Panel Chat Interface**: Flexible column-based layout with draggable tabs
- **Real-Time Communication**: WebSocket streaming for chat, toolchain, and orchestration
- **Knowledge Graph Visualization**: Interactive vis.js network graph with entity relationships
- **Memory Explorer**: Browse and query Neo4j graph and ChromaDB vectors
- **Notebook System**: Markdown-based note-taking with hierarchical organization
- **Proactive Focus Manager**: Background task monitoring and focus board visualization
- **Toolchain Execution Tracker**: Real-time tool execution progress and results
- **Orchestration Dashboard**: Distributed worker pool monitoring and task management
- **File Upload System**: Multi-file upload with progress tracking
- **Canvas Drawing**: Interactive canvas for visual annotations
- **Theme Customization**: Dark/light theme support with custom color schemes

---

## Architecture

### System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      ChatUI Web Interface                        │
│                         (Port 8888)                              │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
   ┌────▼─────┐         ┌────▼─────┐        ┌─────▼──────┐
   │ FastAPI  │         │   HTTP   │        │ WebSocket  │
   │  Router  │         │   REST   │        │  Streaming │
   └────┬─────┘         └────┬─────┘        └─────┬──────┘
        │                    │                     │
        └────────────────────┼─────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
   ┌────▼──────┐      ┌─────▼──────┐      ┌─────▼──────┐
   │ Session   │      │   Memory   │      │   Vera     │
   │ Manager   │      │   System   │      │  Instance  │
   └───────────┘      └────────────┘      └────────────┘
```

### Frontend Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      ui.html (Main Page)                      │
└──────────────────────────────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
   ┌────▼──────┐      ┌─────▼──────┐      ┌─────▼──────┐
   │  chat.js  │      │ enhanced_  │      │  graph.js  │
   │           │      │  chat.js   │      │            │
   └───────────┘      └────────────┘      └────────────┘
        │                    │                    │
   ┌────▼──────┐      ┌─────▼──────┐      ┌─────▼──────┐
   │ memory.js │      │notebook.js │      │toolchain.js│
   └───────────┘      └────────────┘      └────────────┘
        │                    │                    │
   ┌────▼──────┐      ┌─────▼──────┐      ┌─────▼──────┐
   │ canvas.js │      │  theme.js  │      │ window.js  │
   └───────────┘      └────────────┘      └────────────┘
```

### Data Flow

```
User Input
    │
    ▼
┌──────────────────┐
│  Frontend JS     │
│  (chat.js)       │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐     ┌──────────────────┐
│  WebSocket       │────►│  chat_api.py     │
│  /ws/chat        │     │  (FastAPI)       │
└──────────────────┘     └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │  Vera Instance   │
                         │  - LLM calls     │
                         │  - Memory ops    │
                         │  - Tool exec     │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │  Stream Response │
                         │  back to client  │
                         └──────────────────┘
```

---

## Directory Structure

### Root Files

#### `ui.html` (Main Interface)
**Purpose:** Primary web interface HTML template

**Size:** ~1200 lines
**Features:**
- Multi-column responsive layout
- Tab management system
- WebSocket initialization
- Component integration
- Theme support

**Structure:**
```html
<!DOCTYPE html>
<html>
<head>
    <!-- Theme CSS -->
    <link rel="stylesheet" href="css/style.css">
    <link rel="stylesheet" href="css/enhanced-chat.css">

    <!-- External dependencies -->
    <script src="vis-network.min.js"></script>
    <script src="marked.min.js"></script>
</head>
<body>
    <!-- Header with session info -->
    <div class="header">
        <div class="session-info"></div>
        <div class="connection-status"></div>
    </div>

    <!-- Multi-column layout -->
    <div class="columns-container">
        <!-- Dynamically created columns -->
    </div>

    <!-- Scripts -->
    <script src="js/chat.js"></script>
    <script src="js/enhanced_chat.js"></script>
    <script src="js/graph.js"></script>
    <!-- ... more components -->
</body>
</html>
```

---

#### `orchestrator.html`
**Purpose:** Standalone orchestration dashboard

**Features:**
- Real-time worker pool monitoring
- Task queue visualization
- Performance metrics
- System resource tracking
- Remote node management

---

#### `temp_pyvis_graph.html`
**Purpose:** Temporary graph visualization output
**Generated By:** Memory dashboard graph exports

---

### Subdirectories

#### `api/` - FastAPI Backend
**See:** [api/README.md](api/README.md)
**Files:** 12 modules
**Purpose:** REST and WebSocket API endpoints

#### `js/` - Frontend JavaScript
**See:** [js/README.md](js/README.md)
**Files:** 11 modules
**Purpose:** Client-side application logic

#### `css/` - Stylesheets
**Files:** 3 files (style.css, enhanced-chat.css, style.js)
**Purpose:** UI styling and theme management

#### `tamagochi/` - Interactive Companion
**Files:** 2 files (tamagochi_robot.js, tamagochi_duck.js)
**Purpose:** Animated assistant character

---

## API Modules

### Core API Files

#### `api/chat_api.py` - Chat Endpoints
**Purpose:** Main chat interaction API

**Size:** ~400 lines

**Key Endpoints:**

```python
@router.post("/api/chat")
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Process chat message with Vera

    Request:
        {
            "session_id": "sess_123",
            "message": "User message",
            "context": {}
        }

    Response:
        {
            "response": "Vera's response",
            "session_id": "sess_123",
            "timestamp": "2025-01-15T10:30:00Z"
        }
    """

@wsrouter.websocket("/ws/chat/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: str):
    """
    Real-time chat via WebSocket

    Streams:
        - Partial response chunks
        - Tool execution updates
        - Memory operations
        - Final response
    """
```

**Features:**
- Enhanced context retrieval (session + long-term + graph)
- Streaming response generation
- Concurrent execution (ThreadPoolExecutor)
- Error handling and recovery
- Message history tracking

**Context Retrieval:**
```python
async def get_enhanced_context(vera, session_id, message, k=5):
    """
    Hybrid retrieval combining:
    1. Session-specific vector search
    2. Long-term semantic search
    3. Graph entity extraction
    4. Subgraph context
    """
    session_context = vera.mem.focus_context(session_id, message, k=k)
    long_term_context = vera.mem.semantic_retrieve(message, k=k)

    # Extract entity IDs from context
    entity_ids = extract_entity_ids(session_context + long_term_context)

    # Get graph relationships
    graph_context = vera.mem.extract_subgraph(entity_ids[:3], depth=1)

    return {
        "session_context": session_context,
        "long_term_context": long_term_context,
        "graph_context": graph_context,
        "entity_ids": entity_ids
    }
```

---

#### `api/memory_api.py` - Memory Operations
**Purpose:** Neo4j graph and ChromaDB vector operations

**Key Endpoints:**

```python
@router.get("/api/memory/entities")
async def get_entities(session_id: str, limit: int = 100):
    """Get all entities from knowledge graph"""

@router.get("/api/memory/relationships")
async def get_relationships(session_id: str):
    """Get all relationships between entities"""

@router.post("/api/memory/query")
async def query_memory(request: MemoryQueryRequest):
    """
    Semantic search across memory layers

    Request:
        {
            "query": "search text",
            "filters": {"project": "xyz"},
            "k": 10
        }
    """

@router.get("/api/memory/subgraph/{entity_id}")
async def get_subgraph(entity_id: str, depth: int = 2):
    """Extract subgraph around entity"""
```

---

#### `api/graph_api.py` - Graph Visualization
**Purpose:** Knowledge graph data for vis.js rendering

**Endpoints:**

```python
@router.get("/api/graph/nodes")
async def get_graph_nodes(session_id: str):
    """
    Get nodes for graph visualization

    Returns:
        [
            {
                "id": "node_1",
                "label": "Entity Name",
                "type": "Person",
                "color": "#4CAF50"
            },
            ...
        ]
    """

@router.get("/api/graph/edges")
async def get_graph_edges(session_id: str):
    """
    Get edges for graph visualization

    Returns:
        [
            {
                "from": "node_1",
                "to": "node_2",
                "label": "RELATED_TO",
                "arrows": "to"
            },
            ...
        ]
    """
```

---

#### `api/toolchain_api.py` - Tool Execution
**Purpose:** Tool chain planning and execution monitoring

**Key Endpoints:**

```python
@router.post("/api/toolchain/execute")
async def execute_toolchain(request: ToolchainRequest):
    """
    Execute tool chain plan

    Request:
        {
            "query": "Task description",
            "strategy": "hybrid",
            "session_id": "sess_123"
        }
    """

@wsrouter.websocket("/ws/toolchain/{execution_id}")
async def toolchain_stream(websocket: WebSocket, execution_id: str):
    """
    Real-time tool execution updates

    Streams:
        - Plan generation
        - Step execution
        - Tool outputs
        - Errors and retries
        - Final result
    """

@router.get("/api/toolchain/executions/{session_id}")
async def get_executions(session_id: str):
    """Get execution history"""
```

---

#### `api/orchestrator_api.py` - Distributed Orchestration
**Purpose:** Worker pool and task management API

**Size:** ~600 lines

**Key Endpoints:**

```python
@router.post("/orchestrator/init")
async def initialize_orchestrator(config: WorkerPoolConfig):
    """Initialize worker pool"""

@router.post("/orchestrator/task/submit")
async def submit_task(task: TaskSubmission):
    """
    Submit task to orchestrator

    Request:
        {
            "name": "task_name",
            "payload": {...},
            "priority": "HIGH",
            "labels": ["gpu", "python"]
        }
    """

@router.get("/orchestrator/status")
async def get_status():
    """
    Get orchestrator status

    Response:
        {
            "worker_pool": {
                "active_workers": 4,
                "pending_tasks": 12,
                "completed_tasks": 156
            },
            "system_metrics": {
                "cpu_percent": 45.2,
                "memory_percent": 62.1
            }
        }
    """

@wsrouter.websocket("/orchestrator/ws")
async def orchestrator_stream(websocket: WebSocket):
    """Real-time orchestrator updates"""

@router.post("/orchestrator/node/add")
async def add_remote_node(node: RemoteNodeConfig):
    """Add remote compute node to cluster"""
```

---

#### `api/notebook_api.py` - Notebook System
**Purpose:** Hierarchical note-taking and markdown management

**Endpoints:**

```python
@router.post("/api/notebook/create")
async def create_notebook(request: NotebookCreateRequest):
    """Create new notebook"""

@router.post("/api/notebook/{notebook_id}/note")
async def create_note(notebook_id: str, note: NoteRequest):
    """Add note to notebook"""

@router.get("/api/notebook/{notebook_id}")
async def get_notebook(notebook_id: str):
    """Get notebook with all notes"""
```

---

#### `api/proactive_focus.py` / `api/proactivefocus_api.py` - Background Thinking
**Purpose:** Proactive task management and focus board API

**Features:**
- Focus board creation and management
- Background task execution
- Progress tracking
- Issue identification
- Next step suggestions
- Idea generation

**Endpoints:**

```python
@router.post("/api/focus/start")
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

@router.get("/api/focus/board/{session_id}")
async def get_focus_board(session_id: str):
    """
    Get current focus board state

    Response:
        {
            "progress": ["Completed task 1", "Completed task 2"],
            "next_steps": ["Do this next", "Then do that"],
            "issues": ["Problem found", "Another issue"],
            "ideas": ["Interesting idea", "Future exploration"],
            "actions": ["Action item 1", "Action item 2"]
        }
    """

@wsrouter.websocket("/ws/focus/{session_id}")
async def focus_stream(websocket: WebSocket, session_id: str):
    """Real-time focus board updates"""
```

---

#### `api/vectorstore_api.py` - Vector Operations
**Purpose:** Direct ChromaDB vector store operations

**Endpoints:**

```python
@router.post("/api/vectorstore/add")
async def add_to_vectorstore(request: VectorStoreRequest):
    """Add documents to vector store"""

@router.post("/api/vectorstore/search")
async def search_vectorstore(request: VectorSearchRequest):
    """Semantic search in vector store"""
```

---

#### `api/vera_api.py` - Vera Instance Management
**Purpose:** Vera agent lifecycle and configuration

**Endpoints:**

```python
@router.post("/api/vera/initialize")
async def initialize_vera(config: VeraConfig):
    """Initialize or reconfigure Vera instance"""

@router.get("/api/vera/status/{session_id}")
async def get_vera_status(session_id: str):
    """Get Vera instance status"""
```

---

#### `api/session.py` - Session Management
**Purpose:** Session lifecycle and state management

**Size:** ~200 lines

**Global State:**

```python
# Session storage
sessions = {}  # session_id -> session_data
vera_instances = {}  # session_id -> Vera instance
toolchain_executions = {}  # execution_id -> execution_data
active_toolchains = {}  # execution_id -> toolchain instance
websocket_connections = {}  # session_id -> [websockets]

# Session structure
{
    "session_id": "sess_abc123",
    "created_at": "2025-01-15T10:00:00Z",
    "last_activity": "2025-01-15T10:30:00Z",
    "messages": [],
    "context": {},
    "vera_config": {}
}
```

**Functions:**

```python
def get_or_create_vera(session_id: str) -> Vera:
    """
    Get existing Vera instance or create new one

    Features:
        - Instance caching per session
        - Lazy initialization
        - Configuration from session
    """

async def cleanup_session(session_id: str):
    """
    Clean up session resources

    Cleanup:
        - Close WebSocket connections
        - Save memory to archive
        - Remove from caches
    """
```

**Endpoints:**

```python
@router.post("/api/session/start")
async def start_session():
    """
    Create new session

    Response:
        {
            "session_id": "sess_abc123",
            "status": "created"
        }
    """

@router.delete("/api/session/{session_id}")
async def end_session(session_id: str):
    """End session and cleanup"""
```

---

#### `api/schemas.py` - Pydantic Models
**Purpose:** Request/response data validation

**Key Models:**

```python
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class ChatRequest(BaseModel):
    session_id: str
    message: str
    context: Optional[Dict[str, Any]] = {}

class ChatResponse(BaseModel):
    response: str
    session_id: str
    timestamp: str

class ToolchainRequest(BaseModel):
    query: str
    strategy: str = "hybrid"
    session_id: str

class MemoryQueryRequest(BaseModel):
    query: str
    filters: Optional[Dict] = {}
    k: int = 10

class NotebookCreateRequest(BaseModel):
    name: str
    description: Optional[str] = ""

class NoteRequest(BaseModel):
    title: str
    content: str
    tags: Optional[List[str]] = []

class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = "default"
```

---

#### `api/logging_config.py` - Logging Configuration
**Purpose:** Centralized logging setup

```python
import logging
from logging.handlers import RotatingFileHandler

def setup_logging(log_level=logging.INFO):
    """
    Configure application logging

    Features:
        - Console output
        - File rotation (10MB, 5 backups)
        - Structured formatting
        - Per-module loggers
    """

    # Format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # File handler
    file_handler = RotatingFileHandler(
        'logs/chatui.log',
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

## Frontend JavaScript

### Core JavaScript Modules

#### `js/chat.js` - Main Chat Interface
**Purpose:** Primary chat interaction logic

**Size:** ~1500 lines

**Class: VeraChat**

```javascript
class VeraChat {
    constructor() {
        this.messages = [];
        this.files = {};
        this.sessionId = null;
        this.processing = false;
        this.websocket = null;
        this.currentStreamingMessageId = null;
        this.useWebSocket = true;

        // Multi-panel system
        this.columns = [];
        this.tabs = [
            { id: 'chat', label: 'Chat', columnId: 1 },
            { id: 'graph', label: 'Knowledge Graph', columnId: 2 },
            { id: 'memory', label: 'Memory', columnId: 2 },
            { id: 'notebook', label: 'Notebook', columnId: 2 },
            { id: 'canvas', label: 'Canvas', columnId: 2 },
            { id: 'toolchain', label: 'Toolchain', columnId: 2 },
            { id: 'focus', label: 'Proactive Focus', columnId: 2 },
            { id: 'orchestration', label: 'Orchestration', columnId: 2 }
        ];

        this.init();
    }

    async init() {
        // Start session
        const response = await fetch('http://llm.int:8888/api/session/start', {
            method: 'POST'
        });
        const data = await response.json();
        this.sessionId = data.session_id;

        // Initialize WebSocket
        this.connectWebSocket();

        // Create initial columns
        this.createColumn();
        this.createColumn();
    }

    connectWebSocket() {
        this.websocket = new WebSocket(
            `ws://llm.int:8888/ws/chat/${this.sessionId}`
        );

        this.websocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleWebSocketMessage(data);
        };
    }

    handleWebSocketMessage(data) {
        if (data.type === 'chunk') {
            // Streaming response chunk
            this.appendToStreamingMessage(data.content);
        } else if (data.type === 'complete') {
            // Response complete
            this.finalizeStreamingMessage();
        } else if (data.type === 'error') {
            // Error occurred
            this.showError(data.message);
        }
    }

    async sendMessage(message) {
        if (this.useWebSocket && this.websocket.readyState === WebSocket.OPEN) {
            // Send via WebSocket for streaming
            this.websocket.send(JSON.stringify({
                type: 'message',
                content: message
            }));
        } else {
            // Fallback to HTTP POST
            const response = await fetch('http://llm.int:8888/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    message: message
                })
            });
            const data = await response.json();
            this.addMessage('assistant', data.response);
        }
    }
}
```

**Key Features:**
- Multi-column layout management
- Draggable tab system
- WebSocket streaming
- File upload handling
- Message rendering (Markdown support)
- Auto-scroll management

---

#### `js/enhanced_chat.js` - Enhanced Chat Features
**Purpose:** Advanced chat interactions

**Features:**
- Rich message formatting
- Code syntax highlighting
- LaTeX math rendering
- Mermaid diagram support
- Interactive elements

---

#### `js/graph.js` - Knowledge Graph Visualization
**Purpose:** Interactive graph rendering with vis.js

**Size:** ~800 lines

**Features:**

```javascript
class KnowledgeGraph {
    constructor() {
        this.network = null;
        this.nodes = new vis.DataSet([]);
        this.edges = new vis.DataSet([]);
        this.options = {
            nodes: {
                shape: 'dot',
                size: 16,
                font: {
                    size: 14,
                    color: '#ffffff'
                },
                borderWidth: 2
            },
            edges: {
                arrows: 'to',
                smooth: {
                    type: 'continuous'
                },
                font: {
                    size: 12,
                    align: 'middle'
                }
            },
            physics: {
                stabilization: false,
                barnesHut: {
                    gravitationalConstant: -2000,
                    springConstant: 0.001,
                    springLength: 200
                }
            }
        };
    }

    async loadGraph() {
        // Fetch nodes
        const nodesResponse = await fetch(
            `http://llm.int:8888/api/graph/nodes?session_id=${sessionId}`
        );
        const nodes = await nodesResponse.json();

        // Fetch edges
        const edgesResponse = await fetch(
            `http://llm.int:8888/api/graph/edges?session_id=${sessionId}`
        );
        const edges = await edgesResponse.json();

        // Update graph
        this.nodes.clear();
        this.nodes.add(nodes);
        this.edges.clear();
        this.edges.add(edges);
    }

    render(containerId) {
        const container = document.getElementById(containerId);
        this.network = new vis.Network(container, {
            nodes: this.nodes,
            edges: this.edges
        }, this.options);

        // Event handlers
        this.network.on('selectNode', (params) => {
            this.onNodeSelect(params.nodes[0]);
        });
    }

    async onNodeSelect(nodeId) {
        // Fetch node details
        const response = await fetch(
            `http://llm.int:8888/api/memory/entity/${nodeId}`
        );
        const data = await response.json();

        // Show in sidebar
        this.showNodeDetails(data);
    }
}
```

---

#### `js/memory.js` - Memory Explorer
**Purpose:** Memory browsing and querying interface

**Features:**
- Entity browser
- Relationship explorer
- Semantic search
- Filter system
- Export functionality

---

#### `js/notebook.js` - Notebook Manager
**Purpose:** Note-taking system

**Features:**
- Markdown editor
- Notebook hierarchy
- Tag system
- Search functionality
- Auto-save

---

#### `js/toolchain.js` - Toolchain Tracker
**Purpose:** Tool execution monitoring

**Features:**
- Real-time execution tracking
- Plan visualization
- Step-by-step progress
- Error display
- Result rendering

---

#### `js/canvas.js` - Drawing Canvas
**Purpose:** Visual annotation system

**Features:**
- Freehand drawing
- Shape tools
- Text annotations
- Image export
- Undo/redo

---

#### `js/theme.js` - Theme Management
**Purpose:** UI theme customization

```javascript
class ThemeManager {
    constructor() {
        this.themes = {
            dark: {
                background: '#1a1a1a',
                foreground: '#ffffff',
                primary: '#4CAF50',
                secondary: '#2196F3'
            },
            light: {
                background: '#ffffff',
                foreground: '#000000',
                primary: '#4CAF50',
                secondary: '#2196F3'
            }
        };
        this.currentTheme = 'dark';
    }

    applyTheme(themeName) {
        const theme = this.themes[themeName];
        document.documentElement.style.setProperty('--bg-color', theme.background);
        document.documentElement.style.setProperty('--fg-color', theme.foreground);
        document.documentElement.style.setProperty('--primary-color', theme.primary);
        document.documentElement.style.setProperty('--secondary-color', theme.secondary);
        this.currentTheme = themeName;
    }
}
```

---

## WebSocket Communication

### WebSocket Protocols

#### Chat WebSocket
**Endpoint:** `ws://localhost:8888/ws/chat/{session_id}`

**Message Types:**

```javascript
// Client -> Server
{
    "type": "message",
    "content": "User message"
}

// Server -> Client: Streaming chunk
{
    "type": "chunk",
    "content": "Partial response"
}

// Server -> Client: Complete
{
    "type": "complete",
    "full_response": "Complete response"
}

// Server -> Client: Error
{
    "type": "error",
    "message": "Error description"
}
```

---

#### Toolchain WebSocket
**Endpoint:** `ws://localhost:8888/ws/toolchain/{execution_id}`

**Message Types:**

```javascript
// Plan generated
{
    "type": "plan",
    "plan": [
        {"tool": "WebSearch", "input": "query"},
        {"tool": "Summarizer", "input": "{prev}"}
    ]
}

// Step started
{
    "type": "step_start",
    "step_num": 1,
    "tool": "WebSearch",
    "input": "query"
}

// Step complete
{
    "type": "step_complete",
    "step_num": 1,
    "output": "Search results..."
}

// Execution complete
{
    "type": "complete",
    "result": "Final result"
}
```

---

#### Orchestrator WebSocket
**Endpoint:** `ws://localhost:8888/orchestrator/ws`

**Message Types:**

```javascript
// Worker status update
{
    "type": "worker_status",
    "worker_id": "worker_1",
    "status": "busy",
    "current_task": "task_123"
}

// Task complete
{
    "type": "task_complete",
    "task_id": "task_123",
    "result": {...}
}

// System metrics
{
    "type": "metrics",
    "cpu": 45.2,
    "memory": 62.1,
    "tasks_pending": 12
}
```

---

## Session Management

### Session Lifecycle

```
Create Session
    │
    ▼
┌──────────────────┐
│  POST /api/      │
│  session/start   │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Generate UUID    │
│ Create Vera      │
│ Initialize State │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ User Interaction │
│ - Chat           │
│ - Tools          │
│ - Memory         │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ DELETE /api/     │
│ session/{id}     │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Cleanup          │
│ - Close WS       │
│ - Save memory    │
│ - Remove cache   │
└──────────────────┘
```

---

## Usage Examples

### Starting the Server

```python
# Start FastAPI server
import uvicorn
from fastapi import FastAPI
from Vera.ChatUI.api import chat_api, memory_api, graph_api, toolchain_api

app = FastAPI()

# Register routers
app.include_router(chat_api.router)
app.include_router(chat_api.wsrouter)
app.include_router(memory_api.router)
app.include_router(graph_api.router)
app.include_router(toolchain_api.router)
app.include_router(toolchain_api.wsrouter)

# Start server
uvicorn.run(app, host="0.0.0.0", port=8888)
```

---

### Client Usage

```javascript
// Initialize chat
const chat = new VeraChat();

// Send message
await chat.sendMessage("Hello, Vera!");

// Load knowledge graph
const graph = new KnowledgeGraph();
await graph.loadGraph();
graph.render('graph-container');

// Query memory
const memoryResults = await fetch('http://llm.int:8888/api/memory/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        query: "network security",
        k: 10
    })
});
const results = await memoryResults.json();
```

---

## Configuration

### Server Configuration

```python
# config.py
class ChatUIConfig:
    # Server
    HOST = "0.0.0.0"
    PORT = 8888
    WORKERS = 4

    # WebSocket
    WS_PING_INTERVAL = 30  # seconds
    WS_PING_TIMEOUT = 10   # seconds

    # Session
    SESSION_TIMEOUT = 3600  # 1 hour
    MAX_SESSIONS = 100

    # Upload
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS = ['.txt', '.pdf', '.md', '.py', '.json']

    # Logging
    LOG_LEVEL = "INFO"
    LOG_FILE = "logs/chatui.log"
```

---

### Frontend Configuration

```javascript
// config.js
const CONFIG = {
    API_BASE: 'http://llm.int:8888',
    WS_BASE: 'ws://llm.int:8888',

    GRAPH_OPTIONS: {
        physics: {
            enabled: true,
            barnesHut: {
                gravitationalConstant: -2000
            }
        }
    },

    THEME: 'dark',
    AUTO_SAVE_INTERVAL: 30000  // 30 seconds
};
```

---

## Development Guide

### Adding New API Endpoint

```python
# 1. Define schema in api/schemas.py
class MyRequest(BaseModel):
    param1: str
    param2: int

# 2. Create endpoint in appropriate api file
@router.post("/api/myendpoint")
async def my_endpoint(request: MyRequest):
    # Implementation
    return {"result": "success"}

# 3. Update frontend to call endpoint
async function callMyEndpoint(param1, param2) {
    const response = await fetch('http://llm.int:8888/api/myendpoint', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ param1, param2 })
    });
    return await response.json();
}
```

---

### Adding New Tab

```javascript
// 1. Add tab definition in chat.js
this.tabs.push({
    id: 'newtab',
    label: 'New Tab',
    columnId: 2
});

// 2. Create tab content in ui.html
function renderNewTab() {
    return `
        <div id="newtab-content" class="tab-content">
            <!-- Tab content here -->
        </div>
    `;
}

// 3. Add tab logic in separate JS file
class NewTabManager {
    constructor() {
        this.init();
    }

    init() {
        // Initialize tab functionality
    }
}
```

---

## Performance

### Optimization Techniques

**1. WebSocket Connection Pooling**
```python
# Reuse connections per session
websocket_connections[session_id] = []
```

**2. Message Batching**
```javascript
// Batch multiple chunks
const batchSize = 10;
let batch = [];

websocket.onmessage = (event) => {
    batch.push(event.data);
    if (batch.length >= batchSize) {
        processBatch(batch);
        batch = [];
    }
};
```

**3. Lazy Loading**
```javascript
// Load graph nodes in chunks
async function loadGraphLazy(offset = 0, limit = 100) {
    const response = await fetch(
        `/api/graph/nodes?offset=${offset}&limit=${limit}`
    );
    const nodes = await response.json();

    if (nodes.length === limit) {
        // More nodes available
        setTimeout(() => loadGraphLazy(offset + limit, limit), 100);
    }
}
```

---

### Performance Benchmarks

| Operation | Time | Notes |
|-----------|------|-------|
| Session creation | ~50ms | Includes Vera initialization |
| Chat message (streaming) | ~1-3s | Depends on LLM response time |
| Graph load (100 nodes) | ~200ms | Includes render time |
| Memory query | ~100ms | Vector + graph search |
| File upload (1MB) | ~500ms | With progress tracking |

---

## Troubleshooting

### Common Issues

**WebSocket Connection Failed**
```javascript
// Check connection status
if (websocket.readyState !== WebSocket.OPEN) {
    console.error('WebSocket not connected');
    // Reconnect
    this.connectWebSocket();
}
```

**Session Not Found**
```python
# Verify session exists
if session_id not in sessions:
    raise HTTPException(status_code=404, detail="Session not found")
```

**Graph Not Rendering**
```javascript
// Ensure vis.js is loaded
if (typeof vis === 'undefined') {
    console.error('vis.js not loaded');
    // Load vis.js
    await loadScript('vis-network.min.js');
}
```

**Memory Full**
```python
# Cleanup old sessions
async def cleanup_old_sessions():
    now = datetime.utcnow()
    for session_id, session in list(sessions.items()):
        last_activity = session.get('last_activity')
        if (now - last_activity).seconds > SESSION_TIMEOUT:
            await cleanup_session(session_id)
```

---

## Related Documentation

- [API Documentation](api/README.md)
- [JavaScript Modules](js/README.md)
- [Memory System](../Memory/README.md)
- [Toolchain](../Toolchain/README.md)
- [Orchestration Backend](../BackgroundCognition/orchestrator/README.md)

---

**Last Updated:** January 2025
**Maintainer:** Vera-AI Development Team
**Version:** 2.0.0
