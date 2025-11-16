# Chat UI

## Overview

The **Chat UI** provides a comprehensive web-based interface for interacting with Vera, including real-time chat, toolchain monitoring, memory exploration, knowledge graph visualization, and system status dashboards.

## Purpose

ChatUI enables users to:
- **Interact with Vera** via real-time chat interface
- **Monitor toolchain execution** with live progress tracking
- **Explore the knowledge graph** interactively
- **Browse memories** and search across sessions
- **Track background cognition** tasks and focus boards
- **Visualize system state** and health metrics
- **Manage documents** and notebooks

## Architecture Role

```
User Browser ←→ FastAPI Backend ←→ Vera Core
      ↓                ↓                ↓
   HTML/JS/CSS    WebSocket/REST   Agents/Memory/Tools
      ↓
 Interactive UI ←→ Real-time Updates
```

The ChatUI acts as the primary user-facing interface, providing both synchronous (REST) and asynchronous (WebSocket) communication with Vera's core systems.

## Directory Structure

```
ChatUI/
├── orchestrator.html          # Main web interface
├── ui.html                    # Alternative simplified UI
├── style.css                  # Global styling
├── temp_pyvis_graph.html      # Graph visualization (PyVis)
├── api/                       # Backend API endpoints
│   ├── vera_api.py           # Main Vera API
│   ├── chat_api.py           # Chat WebSocket endpoints
│   ├── toolchain_api.py      # Toolchain monitoring
│   ├── graph_api.py          # Knowledge graph queries
│   ├── memory_api.py         # Memory exploration
│   ├── proactivefocus_api.py # Background cognition
│   ├── vectorstore_api.py    # Vector database queries
│   ├── notebook_api.py       # Document management
│   ├── orchestrator_api.py   # CEO status
│   ├── session.py            # Session management
│   ├── schemas.py            # Pydantic models
│   └── logging_config.py     # Logging setup
├── js/                        # Frontend JavaScript
│   ├── chat.js               # Chat controller
│   ├── toolchain.js          # Toolchain monitoring
│   ├── graph.js              # Graph visualization
│   ├── graph-addon.js        # Graph extensions
│   ├── memory.js             # Memory explorer
│   ├── enhanced_chat.js      # Advanced chat features
│   ├── proactive-focus-manager.js  # PBC monitoring
│   ├── notebook.js           # Document manager
│   ├── canvas.js             # Drawing/whiteboard
│   ├── window.js             # Layout management
│   └── theme.js              # UI theming
├── tamagochi/                 # Interactive agents
│   ├── tamagochi_robot.js    # Robot mascot
│   └── tamagochi_duck.js     # Duck mascot
└── css/                       # Component styles
    └── (various CSS files)
```

## Key Technologies

- **FastAPI** - Python async web framework (backend)
- **WebSocket** - Real-time bidirectional communication
- **Neo4j Browser API** - Graph visualization
- **PyVis** - Network graph visualization library
- **JavaScript/HTML5/CSS3** - Frontend technologies
- **Pydantic** - Request/response validation
- **CORS Middleware** - Cross-origin requests

## Main Features

### 1. Real-Time Chat Interface
**Files:** `chat.js`, `api/chat_api.py`, `enhanced_chat.js`

Interactive chat with Vera agents:
- **WebSocket connection** for real-time streaming responses
- **Chat history** persisted across sessions
- **Multi-turn conversations** with context retention
- **Voice input/output** integration (optional)
- **Code highlighting** in responses
- **Markdown rendering** for rich text

**Usage:**
```javascript
// Connect to chat WebSocket
const ws = new WebSocket('ws://localhost:8000/ws/chat');

ws.onmessage = (event) => {
    const message = JSON.parse(event.data);
    displayMessage(message.content, message.role);
};

// Send message
ws.send(JSON.stringify({
    message: "Explain how Vera's memory system works",
    session_id: sessionId
}));
```

---

### 2. Toolchain Execution Monitoring
**Files:** `toolchain.js`, `api/toolchain_api.py`

Live monitoring of multi-step tool executions:
- **Step-by-step progress** visualization
- **Tool invocation details** (inputs, outputs)
- **Error tracking** and automatic retries
- **Execution timeline** with timing metrics
- **Result validation** status

**Example View:**
```
Toolchain Execution: Security Analysis
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[✓] Step 1: NetworkScanner (3.2s)
[✓] Step 2: VulnerabilityAnalyzer (12.5s)
[→] Step 3: ReportGenerator (in progress...)
[ ] Step 4: NotificationSender (pending)
```

---

### 3. Knowledge Graph Explorer
**Files:** `graph.js`, `graph-addon.js`, `api/graph_api.py`

Interactive visualization of Vera's knowledge graph:
- **Node browsing** with filters (entities, memories, sessions)
- **Relationship traversal** with multi-hop queries
- **Search functionality** for entities and content
- **Temporal navigation** (view graph at different points in time)
- **Subgraph extraction** for focused analysis
- **Export capabilities** (JSON, GraphML)

**Features:**
- Zoom/pan/rotate 3D graph
- Color-coded node types
- Edge labels showing relationship types
- Node details panel
- Cluster detection
- Path finding between entities

**API Example:**
```javascript
// Fetch subgraph around entity
fetch('/api/graph/subgraph', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
        entity_id: 'Project_X',
        depth: 2,
        relationship_types: ['USES', 'RELATED_TO']
    })
})
.then(res => res.json())
.then(graph => renderGraph(graph));
```

---

### 4. Memory Explorer
**Files:** `memory.js`, `api/memory_api.py`

Search and browse Vera's multi-layered memory:
- **Semantic search** across all memory layers
- **Session browser** with timeline view
- **Entity details** with full relationship context
- **Memory tags** for filtering
- **Cross-session queries** using Macro Buffer

**Search Example:**
```javascript
// Semantic memory search
fetch('/api/memory/search', {
    method: 'POST',
    body: JSON.stringify({
        query: "authentication implementation",
        layers: [2, 3],  // Working Memory + Long-Term
        top_k: 10,
        include_relationships: true
    })
})
.then(res => res.json())
.then(results => displayResults(results));
```

---

### 5. Proactive Focus Manager Dashboard
**Files:** `proactive-focus-manager.js`, `api/proactivefocus_api.py`

Monitor autonomous background cognition:
- **Active thoughts** being processed
- **Focus board** with tasks, ideas, actions, issues
- **Execution queue** status
- **Worker pool** utilization
- **Generated insights** and recommendations

**Dashboard Metrics:**
```
Proactive Background Cognition
━━━━━━━━━━━━━━━━━━━━━━━━━━━
Thoughts Generated: 142
Thoughts Executed: 128
Success Rate: 90.1%
Avg Execution Time: 12.5s
Worker Utilization: 68%
Queue Depth: 3
```

---

### 6. Notebook and Document Manager
**Files:** `notebook.js`, `api/notebook_api.py`

Manage documents, notes, and code snippets:
- **Create/edit/delete** documents
- **Organize by projects** and tags
- **Syntax highlighting** for code
- **Markdown preview**
- **Version history**
- **Automatic saving**

---

### 7. Orchestrator Status Dashboard
**Files:** `api/orchestrator_api.py`

Monitor CEO (Central Executive Orchestrator):
- **Active agents** and their status
- **Resource allocation** (LLMs, tools, workers)
- **Task queue** depth and priorities
- **System performance** metrics
- **Health checks** for all components

---

## API Endpoints

### Chat API (`api/chat_api.py`)

**WebSocket Connection:**
```
WS /ws/chat?session_id={id}
```

**REST Endpoints:**
```
POST /api/chat/message      # Send message
GET  /api/chat/history      # Get chat history
DELETE /api/chat/clear      # Clear history
```

---

### Toolchain API (`api/toolchain_api.py`)

```
POST /api/toolchain/execute           # Execute toolchain
GET  /api/toolchain/status/{id}       # Get execution status
GET  /api/toolchain/history           # Execution history
POST /api/toolchain/replay            # Replay last plan
```

---

### Graph API (`api/graph_api.py`)

```
POST /api/graph/query                 # Cypher query
POST /api/graph/subgraph              # Get subgraph
GET  /api/graph/entity/{id}           # Get entity details
POST /api/graph/search                # Search entities
GET  /api/graph/statistics            # Graph statistics
```

---

### Memory API (`api/memory_api.py`)

```
POST /api/memory/search               # Semantic search
GET  /api/memory/session/{id}         # Get session
GET  /api/memory/sessions             # List sessions
POST /api/memory/promote              # Promote to LTM
GET  /api/memory/stats                # Memory statistics
```

---

### Proactive Focus API (`api/proactivefocus_api.py`)

```
GET  /api/pbc/status                  # PBC status
GET  /api/pbc/focus-board             # Get focus board
POST /api/pbc/trigger                 # Manual trigger
GET  /api/pbc/thoughts                # Recent thoughts
```

---

### Vector Store API (`api/vectorstore_api.py`)

```
POST /api/vectorstore/search          # Vector search
GET  /api/vectorstore/collections     # List collections
POST /api/vectorstore/add             # Add documents
DELETE /api/vectorstore/clear         # Clear collection
```

---

## Frontend Components

### Chat Controller (`js/chat.js`)
Manages chat interface, WebSocket connection, message rendering, and user input handling.

### Toolchain Monitor (`js/toolchain.js`)
Displays real-time toolchain execution with step-by-step progress, timing, and error handling.

### Graph Visualizer (`js/graph.js`, `js/graph-addon.js`)
Renders interactive knowledge graph using vis.js or Neo4j Browser, with zoom, pan, filtering, and search.

### Memory Browser (`js/memory.js`)
Provides memory search interface, session timeline, and entity details viewer.

### Theme Manager (`js/theme.js`)
Handles light/dark theme switching, color schemes, and accessibility preferences.

### Window Manager (`js/window.js`)
Manages multi-window layout, tab organization, and workspace persistence.

---

## Starting the UI

### Development Mode
```bash
cd ChatUI

# Start API server
uvicorn api.vera_api:app --reload --host 0.0.0.0 --port 8000

# Open browser
xdg-open http://localhost:8000/orchestrator.html
```

### Production Mode
```bash
# With Gunicorn (production ASGI server)
gunicorn api.vera_api:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120
```

### Docker Deployment
```bash
# Build image
docker build -t vera-ui:latest -f Dockerfile .

# Run container
docker run -d \
  --name vera-ui \
  -p 8000:8000 \
  -e NEO4J_URL=bolt://neo4j:7687 \
  -e CHROMADB_HOST=chromadb \
  vera-ui:latest
```

---

## Configuration

### Environment Variables
```bash
# API server
API_HOST=0.0.0.0
API_PORT=8000
WORKERS=4

# CORS (for cross-origin requests)
CORS_ORIGINS=http://localhost:3000,https://vera.example.com

# WebSocket
WS_MAX_CONNECTIONS=100
WS_PING_INTERVAL=30

# Session
SESSION_TIMEOUT=3600
SESSION_COOKIE_NAME=vera_session

# Logging
LOG_LEVEL=INFO
LOG_FILE=/var/log/vera-ui.log
```

### Frontend Configuration (`js/config.js`)
```javascript
const config = {
    apiBaseUrl: 'http://localhost:8000',
    wsBaseUrl: 'ws://localhost:8000',
    theme: 'auto',  // 'light', 'dark', or 'auto'
    enableVoice: true,
    autoSave: true,
    maxChatHistory: 100
};
```

---

## Customization

### Adding Custom Themes
```css
/* css/themes/custom.css */
:root {
    --primary-color: #4A90E2;
    --background-color: #1E1E1E;
    --text-color: #E0E0E0;
    --accent-color: #FF6B6B;
}
```

### Creating Custom Dashboard Widgets
```javascript
// js/widgets/custom-widget.js
class CustomWidget {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.init();
    }

    async init() {
        this.render();
        this.startPolling();
    }

    async fetchData() {
        const response = await fetch('/api/custom/data');
        return response.json();
    }

    render() {
        // Custom rendering logic
    }

    startPolling() {
        setInterval(() => this.update(), 5000);
    }
}
```

---

## Session Management

Sessions are tracked via cookies and store:
- User preferences
- Active workspace layout
- Chat history (configurable retention)
- Theme selection
- Open tabs and windows

**Session API:**
```javascript
// Get current session
fetch('/api/session/current')
    .then(res => res.json())
    .then(session => console.log(session));

// Update session preferences
fetch('/api/session/preferences', {
    method: 'PUT',
    body: JSON.stringify({
        theme: 'dark',
        voice_enabled: true
    })
});
```

---

## Security

### Authentication (Optional)
```python
# api/auth.py
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer

security = HTTPBearer()

async def verify_token(credentials = Depends(security)):
    if not valid_token(credentials.credentials):
        raise HTTPException(status_code=401)
    return credentials
```

### Rate Limiting
```python
from slowapi import Limiter

limiter = Limiter(key_func=get_remote_address)

@app.post("/api/chat/message")
@limiter.limit("30/minute")
async def send_message(message: Message):
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

---

## Performance Optimization

### WebSocket Connection Pooling
Limit concurrent WebSocket connections to prevent resource exhaustion.

### Lazy Loading
Load graph data incrementally for large knowledge graphs.

### Caching
Cache frequently accessed memory queries and graph subgraphs.

### Compression
Enable gzip compression for API responses:
```python
from fastapi.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=1000)
```

---

## Troubleshooting

### WebSocket Connection Failed
```bash
# Check if API server is running
curl http://localhost:8000/health

# Check WebSocket endpoint
wscat -c ws://localhost:8000/ws/chat

# Verify CORS settings in browser console
```

### Graph Not Rendering
```bash
# Check Neo4j connection
curl http://localhost:7474

# Verify graph data exists
curl http://localhost:8000/api/graph/statistics
```

### Chat Not Responding
```bash
# Check backend logs
tail -f /var/log/vera-ui.log

# Verify LLM service
curl http://localhost:11434/api/tags  # Ollama
```

---

## Related Documentation

- [User Interface Documentation](../Vera%20Assistant%20Docs/User%20Interface.md)
- [Memory Explorer](../Memory/dashboard/)
- [API Integration Shim](../README.md#5-api-integration-shim)
- [Knowledge Graph](../Vera%20Assistant%20Docs/Knowledge%20Graph.md)

## Subdirectories

- **[api/](api/)** - Backend API endpoints and services
- **[js/](js/)** - Frontend JavaScript modules
- **[tamagochi/](tamagochi/)** - Interactive agent mascots
- **[css/](css/)** - Component stylesheets

## Contributing

To extend the UI:
1. Add new API endpoints in `api/`
2. Create frontend components in `js/`
3. Add styling in `css/`
4. Update documentation
5. Add tests for new features

---

**Related Components:**
- [Agents](../Agents/) - Backend cognitive units
- [Memory](../Memory/) - Data source for exploration
- [Toolchain](../Toolchain/) - Execution monitoring
- [Background Cognition](../BackgroundCognition/) - Proactive tasks
