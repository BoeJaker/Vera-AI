# Vera-AI: Three Main Components Analysis

## EXECUTIVE SUMMARY

Your Vera-AI codebase consists of three interconnected major components that work together to create a comprehensive AI system:

1. **vera.py** - The main entry point and orchestrator
2. **Orchestration Code** - Background task execution and distributed computing  
3. **ChatUI** - Web interface and API endpoints

---

## 1. VERA.PY - Main Entry Point & Core System

**Location:** `/home/user/Vera-AI/vera.py` (1,103 lines, 49KB)

### What It Does:
- **Central Coordinator** - Manages all major subsystems
- **LLM Management** - Handles Ollama API connections with fallback to local
- **Multi-Agent System** - Runs 5 specialized LLM tiers with different capabilities
- **Memory Integration** - Connects to Neo4j and ChromaDB for persistent knowledge
- **Tool Execution** - Loads and manages tools for task execution
- **WebSocket Communication** - Streams responses to frontend in real-time

### Key Classes:
```python
class Vera:
  ├── OllamaConnectionManager        # Manages LLM access (API or local)
  ├── OllamaAPIWrapper              # LLM wrapper with streaming & fallback
  │
  ├── Multiple LLM Instances:
  │   ├── fast_llm                  # Quick responses (gemma2)
  │   ├── intermediate_llm          # Moderate reasoning (gemma3:12b)
  │   ├── deep_llm                  # Complex reasoning (gemma3:27b)
  │   ├── reasoning_llm             # Strategic planning (gpt-oss:20b)
  │   └── tool_llm                  # Tool-specific tasks (gemma2)
  │
  ├── Memory System:
  │   ├── HybridMemory              # Neo4j + ChromaDB
  │   ├── buffer_memory             # Short-term chat history
  │   ├── vector_memory             # Long-term semantic search
  │   └── plan_memory               # Plan tracking
  │
  ├── Tool Systems:
  │   ├── ToolLoader                # Load available tools
  │   ├── ToolChainPlanner          # Plan tool sequences
  │   └── PlayWrightTools           # Browser automation
  │
  ├── Agents:
  │   ├── light_agent               # Fast tool execution
  │   ├── deep_agent                # Complex reasoning + tools
  │   ├── executive_instance        # Calendar, scheduling
  │   └── focus_manager             # Proactive background thinking
  │
  └── Methods:
      ├── async_run(query)          # Main query processing
      ├── stream_llm_with_memory()  # Stream responses
      ├── stream_llm()              # Raw LLM streaming
      └── save_to_memory()          # Persist to memory
```

### Main Entry Point:
```python
if __name__ == "__main__":
    vera = Vera()
    while True:
        user_query = input("\nEnter your query:\n ")
        # Route through async_run() which triages and dispatches
```

### Response Pipeline:
```
User Input
    ↓
async_run() - Triage Classification
    ↓
    ├→ "simple"    → fast_llm (direct response)
    ├→ "complex"   → deep_llm (reasoning)
    ├→ "reasoning" → reasoning_llm (strategic)
    ├→ "toolchain" → ToolChainPlanner (multi-step)
    ├→ "focus"     → ProactiveFocusManager (background)
    └→ other       → fast_llm (default)
    ↓
stream_llm_with_memory() - Retrieve context
    ↓
LLM inference with streaming
    ↓
save_to_memory() - Persist context
    ↓
WebSocket broadcast to frontend
```

---

## 2. ORCHESTRATION CODE - Background Execution & Task Management

**Location:** `/home/user/Vera-AI/BackgroundCognition/orchestrator/` (19 files, 322KB)

### What It Does:
- **Task Scheduling** - Queue and prioritize distributed work
- **Worker Management** - Local, Docker, Ollama, Remote, and Cloud workers
- **Resource Management** - CPU/memory constraints, API rate limiting
- **Auto-Scaling** - Dynamically adjust worker pools based on load
- **Health Monitoring** - Continuous worker health checks

### Architecture:

```
UnifiedOrchestrator
├── Core Components:
│   ├── WorkerRegistry          # Manages all available workers
│   ├── ResourceManager         # Tracks quotas, rate limits, costs
│   ├── TaskRouter              # Routes tasks to best worker
│   └── SmartScheduler          # Priority-based task scheduling
│
├── Task Management:
│   ├── task_history            # All tasks ever submitted
│   ├── active_tasks            # Currently running tasks
│   ├── task_queue              # Pending tasks
│   └── metrics                 # Performance data
│
├── Worker Types (orchestrator/workers/):
│   ├── DockerWorker            # Isolated container execution
│   ├── OllamaWorker            # Local LLM inference
│   ├── LLMAPIWorker            # OpenAI, Anthropic, Gemini APIs
│   └── RemoteWorker            # SSH/HTTP remote nodes
│
└── Configuration (OrchestratorConfig):
    ├── max_concurrent_tasks    # Default: 10
    ├── enable_auto_scaling     # Default: True
    ├── docker_pool_size        # Default: 3
    ├── health_check_interval   # Default: 30s
    └── task_timeout_seconds    # Default: 300s
```

### Task Types:
```python
TaskType:
  ├── OLLAMA_REQUEST           # Local LLM inference
  ├── LLM_REQUEST              # Cloud LLM API call
  ├── TOOL_CALL                # Execute a tool
  ├── BACKGROUND_COGNITION     # Proactive thinking
  ├── DOCKER_EXECUTION         # Container-based code
  └── REMOTE_EXECUTION         # Remote node execution
```

### Key Methods:

```python
# Submit tasks
orchestrator.submit_task(task, wait=True)
orchestrator.submit_batch(tasks, execute_parallel=True, wait=True)

# Execute specific operations
orchestrator.execute_llm_request(prompt, model, temperature)
orchestrator.execute_tool_call(tool_name, tool_input)

# Management
orchestrator.start()
orchestrator.stop()
orchestrator.get_status()           # Returns metrics & worker stats
orchestrator.get_task_history()     # Task execution history
```

### Worker Pool Flow:

```
Task Submission
    ↓
SmartScheduler - Apply priority & dependencies
    ↓
TaskRouter - Select best worker
    │   ├→ Least loaded worker (for compute)
    │   ├→ Qualified worker (by labels)
    │   └→ Round-robin / Random fallback
    ↓
ResourceManager - Check quotas
    │   ├→ API rate limits
    │   ├→ Memory available
    │   └→ Cost constraints
    ↓
Worker Execution
    │   ├→ Docker: Run in isolated container
    │   ├→ Ollama: Local LLM inference
    │   ├→ LLM API: Call cloud API with retries
    │   └→ Remote: SSH/HTTP to remote node
    ↓
Health Checks (every 30 seconds)
    │   ├→ Worker responsiveness
    │   ├→ System resources
    │   └→ Auto-scale if needed
    ↓
Result Collection & Metrics
```

### Integration with Vera:

Located at: `/home/user/Vera-AI/BackgroundCognition/orchestrator/integration/vera_integration.py`

```python
class VeraOrchestratorIntegration:
    async def initialize()
    async def execute_tool(tool_name, tool_input, priority)
    async def execute_tool_chain(tool_plan, priority)
    async def execute_background_cognition(context, priority)
    async def ask_llm(prompt, model, temperature, prefer_local)
    async def parallel_llm_requests(prompts, model, temperature)
    def get_metrics()  # Returns orchestrator status
```

---

## 3. CHATUI - Web Interface & API Endpoints

**Location:** `/home/user/Vera-AI/ChatUI/` (908KB, 15+ modules)

### What It Does:
- **Web API** - FastAPI-based REST endpoints
- **Real-time Communication** - WebSocket for streaming responses
- **Session Management** - User sessions with persistent state
- **Memory Operations** - Query knowledge graph and vector store
- **Toolchain Monitoring** - Track tool execution in real-time
- **Graph Visualization** - Interactive knowledge graph UI
- **Proactive Focus** - Background thinking controls

### Architecture:

```
FastAPI App (vera_api.py)
├── Routers (api/*.py):
│   ├── chat_api.py              # Chat endpoints + WebSocket
│   ├── graph_api.py             # Knowledge graph queries
│   ├── memory_api.py            # Memory operations
│   ├── toolchain_api.py         # Tool execution tracking
│   ├── orchestrator_api.py      # Orchestrator control (commented out)
│   ├── proactivefocus_api.py    # Focus management
│   ├── vectorstore_api.py       # Vector search
│   ├── notebook_api.py          # Notebook execution
│   ├── session.py               # Session management
│   └── schemas.py               # Request/response models
│
├── CORS Middleware - Allow cross-origin requests
│
└── Dependencies:
    ├── vera.py instance
    ├── HybridMemory
    ├── Neo4j driver
    └── ChromaDB vectorstore
```

### API Endpoints:

#### Session Management
```
POST   /api/session/start         # Create new chat session
POST   /api/session/{id}/end      # End session
GET    /api/session/{id}          # Get session info
```

#### Chat & Streaming
```
POST   /api/chat                  # Send message (non-streaming)
WS     /ws/chat/{session_id}      # WebSocket for streaming responses
```

#### Memory Operations
```
GET    /api/memory/query          # Search memory
GET    /api/memory/hybrid-retrieve  # Hybrid graph+vector search
POST   /api/memory/{session_id}/promote  # Promote to long-term
GET    /api/memory/{session_id}/entities  # Get session entities
GET    /api/memory/{session_id}/relationships  # Get relationships
```

#### Knowledge Graph
```
GET    /api/graph/session/{session_id}  # Get session graph
GET    /api/graph/visualize            # Graph visualization
```

#### Toolchain
```
POST   /api/toolchain/execute            # Execute tool sequence
WS     /ws/toolchain/{session_id}        # Tool monitoring
GET    /api/toolchain/{session_id}/executions  # Execution history
GET    /api/toolchain/{session_id}/tools       # Available tools
```

#### Proactive Focus
```
GET    /api/focus/set              # Set focus topic
GET    /api/focus/status           # Current focus state
GET    /api/focus/stop             # Stop proactive thinking
WS     /ws/focus/{session_id}      # Focus updates
```

#### System
```
GET    /health                      # Health check
GET    /api/info                    # API information
GET    /api/debug/neo4j/{session_id}  # Debug memory graph
```

### Frontend UI Files:

```
/ChatUI/
├── ui.html                        # Main web interface
│   ├── Vis.js for graph visualization
│   ├── Real-time WebSocket updates
│   ├── Message history display
│   ├── Graph controls & filtering
│   └── Settings panel
│
├── orchestrator.html              # Orchestrator UI
│   ├── Task submission
│   ├── Worker pool monitoring
│   ├── Real-time metrics
│   ├── System resource graphs
│   └── Rate limit controls
│
└── js/                            # Frontend JavaScript
    ├── chat.js
    ├── graph.js
    ├── memory.js
    ├── toolchain.js
    └── orchestration.js
```

### Session Management:

```python
# Global state in session.py
vera_instances: Dict[str, Vera]    # Session → Vera instance
sessions: Dict[str, Dict]          # Session → chat history
active_toolchains: Dict[str, str]  # Session → current execution
websocket_connections: Dict        # Session → WebSocket list

# Functions
get_or_create_vera(session_id)     # Lazy initialization
```

### WebSocket Flow:

```
Browser WebSocket Connection
    ↓
accept() in wsrouter
    ↓
User sends message via /ws/chat/{session_id}
    ↓
get_or_create_vera(session_id) - Get/create Vera instance
    ↓
vera.async_run(message) - Process with streaming
    ↓
for chunk in vera.async_run():
    websocket.send_json({
        "type": "token",
        "data": chunk
    })
    ↓
Browser receives and displays in real-time
```

---

## INTEGRATION POINTS

### 1. vera.py ↔ Orchestration

**Current Integration:**
- vera.py does NOT currently use UnifiedOrchestrator
- Tools are executed directly via ToolChainPlanner
- No task queueing or worker pools

**Suggested Integration Path:**
```python
# In vera.py.__init__()
from BackgroundCognition.orchestrator import UnifiedOrchestrator
self.orchestrator = UnifiedOrchestrator(config)
await self.orchestrator.start()

# In async_run() for tool execution
if "toolchain" in triage_lower:
    # Instead of direct toolchain execution:
    # Use orchestrator to manage tool chain
    result = await self.orchestrator.execute_tool_chain(
        tool_plan=plan,
        priority=TaskPriority.NORMAL
    )
```

### 2. vera.py ↔ ChatUI

**Current Integration:**
```python
# ChatUI imports vera.py
from Vera.vera import Vera

# In vera_api.py
app.include_router(chat_api.router)
app.include_router(toolchain_api.router)

# Session management
vera_instances[session_id] = Vera()
result = vera.async_run(message)
```

**Flow:**
```
Browser → WebSocket → /ws/chat/{session_id}
           ↓
        chat_api.py
           ↓
        vera.async_run(message)
           ↓
        Stream response back to WebSocket
```

### 3. Orchestration ↔ ChatUI

**Current Integration:**
- orchestrator_api.py exists but is COMMENTED OUT in vera_api.py
- No active connection between orchestrator and web interface

**Line in vera_api.py (line 73):**
```python
# app.include_router(orchestrator_api.router)  # ← DISABLED
```

**Available in orchestrator_api.py:**
```
POST   /orchestrator/pool/initialize
POST   /orchestrator/pool/start
POST   /orchestrator/pool/stop
GET    /orchestrator/pool/status
POST   /orchestrator/tasks/submit
GET    /orchestrator/tasks/history
WS     /orchestrator/ws/updates
GET    /orchestrator/health
GET    /orchestrator/system/metrics
```

---

## CURRENT STATE DIAGRAM

```
┌─────────────────────────────────────────────────────────────┐
│                      WEB BROWSER                             │
│                      (ui.html)                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
                    ┌───────────────┐
                    │   WebSocket   │
                    │  /ws/chat     │
                    └───────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    CHATUI LAYER                              │
│  (vera_api.py / chat_api.py / FastAPI)                      │
│                                                              │
│  ├─ Session Management                                      │
│  ├─ WebSocket Handlers                                      │
│  ├─ REST Endpoints                                          │
│  └─ Dependencies: vera.py instance                          │
└─────────────────────────────────────────────────────────────┘
        ↓                       ↓              ↓
    ┌────────────┐      ┌──────────────┐   ┌──────────┐
    │ vera.py    │      │ Memory APIs  │   │ Graph    │
    │            │      │ (Neo4j)      │   │ APIs     │
    │ - LLM      │      │              │   │          │
    │   tiers    │      └──────────────┘   └──────────┘
    │ - Tools    │            ↑
    │ - Agents   │            │
    │ - Memory   │      ┌──────────────┐
    └────────────┘      │ ChromaDB +   │
         ↓              │ Neo4j        │
    ┌────────────┐      └──────────────┘
    │ToolChain  │
    │ Planner    │
    └────────────┘
         ↓
    ┌────────────┐
    │   Tools    │
    │            │
    │  Browser   │
    │  Code Exec │
    │  Web       │
    │  Security  │
    └────────────┘


[NOT INTEGRATED]:
┌─────────────────────────────────────────────────────────────┐
│          ORCHESTRATION LAYER (Currently Unused)             │
│                                                              │
│  ├─ UnifiedOrchestrator                                    │
│  ├─ Task Router & Scheduler                                │
│  ├─ Worker Pools (Docker, Ollama, LLM APIs, Remote)       │
│  ├─ Resource Manager                                       │
│  └─ Auto-scaling                                           │
│                                                              │
│  [orchestrator_api.py - COMMENTED OUT]                     │
└─────────────────────────────────────────────────────────────┘
```

---

## RECOMMENDED INTEGRATION APPROACH

### Phase 1: Enable Orchestrator API (Quick Win)
```python
# In ChatUI/api/vera_api.py, uncomment line 73:
app.include_router(orchestrator_api.router)

# Update orchestrator_api.py to initialize with vera instance
```

### Phase 2: Connect Vera to Orchestrator
```python
# In vera.py, add orchestrator initialization:
async def initialize_orchestrator(self):
    config = OrchestratorConfig(
        max_concurrent_tasks=10,
        enable_auto_scaling=True
    )
    self.orchestrator = UnifiedOrchestrator(config)
    await self.orchestrator.start()

# Modify async_run() to use orchestrator for tool execution
```

### Phase 3: Create Unified Dashboard
```html
<!-- New page that combines:
  - Chat interface (existing ui.html)
  - Orchestrator monitoring (existing orchestrator.html)
  - Unified control panel
-->
```

### Phase 4: Implement Distributed Execution
```python
# Route expensive operations through orchestrator:
# - LLM requests → Ollama workers
# - Tool calls → Docker workers + Remote nodes
# - Background thinking → Background worker pool
```

---

## DATA FLOW EXAMPLES

### Example 1: Simple Chat Message
```
User: "What is 2+2?"
       ↓
WebSocket /ws/chat → chat_api.py
       ↓
vera.async_run("What is 2+2?")
       ↓
triage_prompt → classify as "simple"
       ↓
fast_llm.stream("What is 2+2?")
       ↓
Stream response back through WebSocket
       ↓
save_to_memory(question, answer)
       ↓
Browser displays response
```

### Example 2: Complex Tool Chain
```
User: "Schedule a meeting and send an email"
       ↓
vera.async_run()
       ↓
triage_prompt → classify as "toolchain"
       ↓
deep_llm.invoke(planning_prompt)
       ↓
Generate tool plan:
  [
    {"tool": "calendar_add", "input": {...}},
    {"tool": "email_send", "input": {...}}
  ]
       ↓
[CURRENT] ToolChainPlanner.execute_tool_chain()
[FUTURE] orchestrator.execute_tool_chain(plan)
       ↓
Execute tools with dependency tracking
       ↓
Merge results and return final answer
       ↓
save_to_memory()
```

### Example 3: Background Proactive Thinking
```
User: "Set focus on project management"
       ↓
vera.async_run()
       ↓
triage_prompt → classify as "focus"
       ↓
focus_manager.set_focus("project management")
       ↓
[FUTURE] orchestrator.submit_task(
    type=TaskType.BACKGROUND_COGNITION,
    priority=TaskPriority.LOW,
    payload={...}
)
       ↓
Run in background worker pool
       ↓
Periodically generate proactive thoughts
       ↓
Send updates via WebSocket /ws/focus
       ↓
Update focus board and notify user
```

---

## FILE SUMMARY TABLE

| Component | Location | Purpose | Status |
|-----------|----------|---------|--------|
| **vera.py** | Root | Main entry point, core system | ✅ Active |
| **Orchestrator** | BackgroundCognition/orchestrator/ | Task scheduling & execution | ✅ Built, ⚠️ Unused |
| **ChatUI API** | ChatUI/api/ | Web interface & endpoints | ✅ Active |
| **ChatUI Frontend** | ChatUI/*.html | Web UI | ✅ Active |
| **Integration Layer** | orchestrator/integration/ | Connects orchestrator to vera | ⚠️ Incomplete |
| **Memory System** | Memory/ | Neo4j + ChromaDB | ✅ Active |
| **Tool Execution** | Toolchain/ | Tool planning & execution | ✅ Active |

---

## NEXT STEPS FOR INTEGRATION

1. **Uncomment orchestrator_api.py** in vera_api.py line 73
2. **Update orchestrator_api.py** to accept vera instance
3. **Modify vera.async_run()** to use orchestrator for tool chains
4. **Create integration tests** with both systems working together
5. **Build unified monitoring dashboard** combining all three components
6. **Implement distributed tool execution** via orchestrator workers

