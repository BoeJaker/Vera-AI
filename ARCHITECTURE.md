# Vera-AI Architecture Documentation

## Table of Contents
- [System Overview](#system-overview)
- [Directory Structure](#directory-structure)
- [Core Architecture](#core-architecture)
- [Data Flow](#data-flow)
- [Technology Stack](#technology-stack)
- [Component Interactions](#component-interactions)

## System Overview

Vera-AI is a distributed multi-agent AI architecture implementing Self-Modifying, Multi-Agent Cognition with Proactive Background Reflection and Execution Engine (SMMAC-PBR-XE). The system is designed to provide autonomous, intelligent task execution with persistent memory, proactive cognition, and self-improvement capabilities.

### Key Architectural Principles

1. **Modularity**: Each component can operate standalone or as part of the complete framework
2. **Distributed Execution**: Tasks can be distributed across local workers, Docker containers, remote nodes, and cloud APIs
3. **Persistent Memory**: Multi-layered memory system ensuring context preservation across sessions
4. **Autonomous Evolution**: Self-modification capabilities enable continuous improvement
5. **Protocol Agnostic**: Communication layer supports any digital protocol

## Directory Structure

```
/home/user/Vera-AI/
├── Agents/                          # Agent implementations (1529 LOC)
│   ├── executive_0_9.py            # Central Executive Agent
│   ├── planning.py                 # Plan Generation Agent
│   ├── reviewer.py                 # Quality Control Agent
│   ├── idea_generator.py           # Creative Idea Generation
│   └── executive_ui.py             # Executive UI Interface
│
├── BackgroundCognition/             # Proactive cognition & orchestration (322KB, 27 modules)
│   ├── orchestrator/               # Unified orchestration backend
│   │   ├── core.py                # Central orchestrator
│   │   ├── router.py              # Task routing logic
│   │   ├── resources.py           # Resource management
│   │   ├── workers/               # Worker implementations
│   │   │   ├── base.py           # BaseWorker abstract class
│   │   │   ├── docker_worker.py  # Docker container execution
│   │   │   ├── ollama_worker.py  # Local LLM via Ollama
│   │   │   ├── llm_api_worker.py # Cloud LLM APIs
│   │   │   └── remote_worker.py  # Remote compute nodes
│   │   └── api_integration.py    # FastAPI integration
│   ├── proactive_background_focus.py  # Focus management
│   ├── pbt_v2.py                  # Background thinking v2
│   ├── cluster.py                 # Distributed clustering
│   ├── worker_pool.py             # Worker pool management
│   └── registry.py                # Worker registry
│
├── Memory/                          # Knowledge graph & memory systems (633KB)
│   ├── memory.py                  # Hybrid Memory System (100KB)
│   ├── memory_v2.py               # Enhanced memory
│   ├── nlp.py                     # NLP extraction
│   ├── graph_audit.py             # Graph validation
│   ├── archive.py                 # Long-term archival
│   ├── cve_ingestor.py            # CVE database ingestion
│   ├── network_ingestor.py        # Network data ingestion
│   └── dashboard/                 # Memory visualization
│       ├── dashboard.py           # Memory explorer backend
│       └── graphui.html           # Interactive graph UI
│
├── Toolchain/                       # Tool execution & planning (812KB, 34 modules)
│   ├── toolchain.py               # Tool planning & execution
│   ├── enhanced_toolchain_planner.py  # Advanced planning
│   ├── n8n_toolchain.py           # n8n workflow integration
│   ├── dynamic_tools.py           # Dynamic tool discovery
│   ├── mcp_manager.py             # MCP protocol integration
│   ├── schemas.py                 # Input/output schemas
│   └── Tools/                     # Individual tool implementations
│       ├── web_security.py        # Security testing
│       ├── code_executor.py       # Code execution
│       ├── Babelfish/             # Translation engine
│       └── Crawlers/              # Web crawling tools
│
├── ChatUI/                          # Web interface & API endpoints (908KB)
│   ├── api/                       # FastAPI routers (12 modules)
│   │   ├── vera_api.py           # Main Vera API
│   │   ├── chat_api.py           # Chat endpoints + WebSocket
│   │   ├── graph_api.py          # Knowledge graph endpoints
│   │   ├── memory_api.py         # Memory operations
│   │   ├── toolchain_api.py      # Toolchain execution
│   │   ├── orchestrator_api.py   # Orchestrator endpoints
│   │   └── proactivefocus_api.py # Focus management
│   ├── js/                        # Frontend JavaScript
│   │   ├── chat.js               # Chat interface
│   │   ├── memory.js             # Memory explorer
│   │   ├── graph.js              # Graph visualization
│   │   └── toolchain.js          # Toolchain monitoring
│   └── orchestrator.html          # Main UI
│
├── Configuration/                   # Config files & focus boards (977KB)
│   ├── vera_models.json           # LLM model configuration
│   ├── focus_boards/              # 70+ focus board states
│   └── last_tool_plan.json        # Last tool execution plan
│
├── Speech/                          # Speech processing
│   ├── speech.py                  # Recognition/synthesis
│   └── __init__.py
│
├── Plugins/                         # Plugin framework
│   └── __init__.py
│
├── plugins/                         # Individual tool plugins (38+ modules)
│   ├── nmap_module.py             # Network scanning
│   ├── metasploit_module.py       # Exploitation framework
│   ├── wireshark.py               # Packet analysis
│   ├── python_parser.py           # Code analysis
│   └── ... (35+ more tools)
│
├── worker/                          # Distributed worker system
│   ├── worker_api.py              # Worker API
│   ├── dockerfile                 # Worker container
│   └── USER_GUIDE.MD              # Worker documentation
│
├── projects/                        # Project management
│
├── .github/                         # GitHub workflows & instructions
│   ├── workflows/
│   │   └── update_dev_days.yml
│   └── instructions/
│       └── snyk_rules.instructions.md
│
├── Vera Assistant Docs/             # Existing documentation (160KB)
│   ├── Vera - Versatile, Evolving Reflective Architecture.md
│   ├── Central Executive Orchestrator.md
│   ├── Knowledge Graph.md
│   └── ... (17+ more docs)
│
├── vera.py                          # Main entry point (49KB)
├── proactive_focus_manager.py       # Focus management (67KB)
├── makefile                         # Build automation (24KB)
├── docker-compose.yml               # Container orchestration
├── Dockerfile                       # Docker build config
└── start.sh                         # Startup script
```

## Core Architecture

### Multi-Tier LLM System

Vera uses a tiered approach to LLM utilization:

```
┌─────────────────────────────────────────┐
│     REASONING LLM (gpt-oss:20b)         │  ← Complex reasoning, strategic planning
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│      DEEP LLM (gemma3:27b)              │  ← Advanced reasoning, long-form generation
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│   INTERMEDIATE LLM (gemma3:12b)         │  ← Tool execution, mid-complexity tasks
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│      FAST LLM (gemma2:latest)           │  ← Triage, quick responses, validation
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│   EMBEDDING MODEL (mistral:7b)          │  ← Vector embeddings for semantic search
└─────────────────────────────────────────┘
```

### Memory Architecture (Layers 1-4)

```
┌──────────────────────────────────────────────────────────────┐
│  Layer 1: Short-Term Context Buffer (In-Memory)              │
│  - Last 10-20 message exchanges                              │
│  - System prompts, user input, recent history                │
└──────────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────────┐
│  Layer 2: Working Memory (Session Context)                   │
│  - Neo4j: Session nodes + relationships                      │
│  - ChromaDB: session_<id> collections                        │
│  - Agent thoughts, notes, task-specific data                 │
└──────────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────────┐
│  Layer 3: Long-Term Knowledge                                │
│  - Neo4j: Entities, relationships, graph structure           │
│  - ChromaDB: long_term_docs collection                       │
│  - Persistent facts, insights, promoted memories             │
└──────────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────────┐
│  Layer 4: Temporal Archive (Postgres + JSONL)                │
│  - Immutable audit log of all system activity                │
│  - Version history, telemetry, change records                │
│  - Complete timeline for temporal navigation                 │
└──────────────────────────────────────────────────────────────┘
                          ↑
┌──────────────────────────────────────────────────────────────┐
│  Layer 5: External Knowledge Bases                           │
│  - APIs, web documentation, Git repos                        │
│  - Dynamic networked data stores                             │
│  - External sources of truth                                 │
└──────────────────────────────────────────────────────────────┘
```

### Memory Buffer Hierarchy

```
┌──────────────────────────────────────────┐
│         Meta Buffer (Strategic)          │
│  - Knowledge gap analysis                │
│  - Self-modeling & capabilities          │
│  - Strategic learning plans              │
└──────────────────────────────────────────┘
              ↕
┌──────────────────────────────────────────┐
│      Macro Buffer (Operational)          │
│  - Cross-sessional retrieval             │
│  - Graph-accelerated search              │
│  - Temporal pattern recognition          │
└──────────────────────────────────────────┘
              ↕
┌──────────────────────────────────────────┐
│       Micro Buffer (Tactical)            │
│  - Immediate working context             │
│  - Attention scoring (7±2 chunks)        │
│  - Real-time NLP processing              │
└──────────────────────────────────────────┘
```

## Data Flow

### User Query Processing Flow

```
1. User Input
      ↓
2. Triage Agent (Fast LLM)
   - Classify query type
   - Determine complexity
   - Route to appropriate handler
      ↓
3. Routing Decision
      ↓
   ┌──────────────┬──────────────┬──────────────┐
   ↓              ↓              ↓              ↓
Simple        Tool Chain     Background     Memory
Query         Required       Task          Query
   ↓              ↓              ↓              ↓
Fast LLM    ToolChain       Orchestrator  Memory
Direct      Engine          Worker Pool   System
Response
   ↓              ↓              ↓              ↓
4. Execution Phase
   - Query LLM or execute tools
   - Retrieve memory context
   - Generate response
      ↓
5. Memory Integration
   - Save to short-term buffer
   - Extract entities/relationships (NLP)
   - Promote to long-term if valuable
   - Archive to Layer 4
      ↓
6. Return to User
```

### Background Cognition Flow

```
1. Proactive Focus Manager (Tick)
      ↓
2. Context Aggregation
   - Conversation history
   - Focus board state
   - Pending goals
   - System metrics
      ↓
3. LLM Thought Generation (Deep LLM)
   - Analyze context
   - Identify actionable tasks
   - Generate hypotheses/plans
      ↓
4. Validation (Fast LLM)
   - Check executability
   - Verify safety
   - Assess priority
      ↓
5. Task Submission
      ↓
   ┌──────────────┬──────────────┬──────────────┐
   ↓              ↓              ↓              ↓
Local         Docker        Remote        Cloud
Worker        Worker        Worker        API
   ↓              ↓              ↓              ↓
6. Execution & Results
      ↓
7. Focus Board Update
   - Progress tracking
   - Issue logging
   - Idea capture
   - Action items
      ↓
8. Memory Storage
   - Save insights to Layer 3
   - Archive to Layer 4
   - Update knowledge graph
```

### Tool Chain Execution Flow

```
1. Complex Query Received
      ↓
2. Tool Chain Planner
   - Analyze available tools
   - Generate execution plan (JSON)
   - Determine strategy (Sequential/Parallel/Hybrid)
      ↓
3. Plan Validation
      ↓
4. Step-by-Step Execution
   For each step:
      ↓
   ┌──────────────────────────┐
   │ 4a. Resolve Placeholders  │  ({prev}, {step_N})
   └──────────────────────────┘
      ↓
   ┌──────────────────────────┐
   │ 4b. Execute Tool          │
   └──────────────────────────┘
      ↓
   ┌──────────────────────────┐
   │ 4c. Capture Output        │
   └──────────────────────────┘
      ↓
   ┌──────────────────────────┐
   │ 4d. Error Handling        │  (Replan if failure)
   └──────────────────────────┘
      ↓
5. Result Validation (LLM)
   - Check if goal met
   - Trigger retry if needed
      ↓
6. Memory Save
   - Store plan + results
   - Record in history
      ↓
7. Return Final Output
```

## Technology Stack

### Core Languages & Frameworks
- **Python 3.11** - Primary language
- **FastAPI** - REST/WebSocket API framework
- **LangChain** - Multi-agent orchestration & tool integration

### AI/ML Stack
- **Ollama** - Local LLM inference engine
- **spaCy** - NLP entity extraction & dependency parsing
- **sentence-transformers** - Semantic embeddings
- **scikit-learn** - ML clustering & analysis

### Data Storage
- **Neo4j** - Knowledge graph database (relationships, entities)
- **ChromaDB** - Vector embeddings & semantic search
- **PostgreSQL** - Immutable audit log & telemetry
- **JSONL** - Backup log streaming

### Frontend Technologies
- **HTML/CSS/JavaScript** - Web UI components
- **WebSocket** - Real-time bidirectional communication
- **PyVis** - Interactive graph visualization

### Automation & Integration
- **Playwright** - Browser automation
- **BeautifulSoup** - HTML parsing
- **requests/aiohttp** - HTTP clients (sync/async)
- **apscheduler** - Task scheduling

### DevOps & Deployment
- **Docker** - Containerization
- **Docker Compose** - Multi-container orchestration
- **Proxmox** - VM deployment support
- **Make** - Build automation

### System Utilities
- **psutil** - System monitoring & resource management
- **asyncio** - Asynchronous task execution
- **python-dotenv** - Environment configuration

## Component Interactions

### CEO (Central Executive Orchestrator) Interactions

```
CEO
 ├─ Receives queries from → Chat API
 ├─ Delegates to → Triage Agent
 ├─ Manages → Worker Pool
 │   ├─ Local Workers
 │   ├─ Docker Workers
 │   ├─ Remote Workers (HTTP)
 │   └─ Proxmox Workers
 ├─ Monitors → Resource Utilization
 ├─ Queues → Pending Tasks
 └─ Reports to → Orchestrator UI
```

### Memory System Interactions

```
Memory System
 ├─ Receives from → All Agents & Tools
 ├─ NLP Processing → spaCy extraction
 ├─ Stores in →
 │   ├─ Neo4j (graph structure)
 │   ├─ ChromaDB (vector embeddings)
 │   └─ Postgres (audit log)
 ├─ Queried by →
 │   ├─ Chat API (conversation context)
 │   ├─ Proactive Focus Manager (background cognition)
 │   ├─ Tool Chain Planner (historical plans)
 │   └─ Memory Explorer UI
 └─ Exports to → Memory Explorer Dashboard
```

### Tool Chain Engine Interactions

```
Tool Chain Engine
 ├─ Receives queries from → CEO
 ├─ Plans using → Deep LLM
 ├─ Executes via →
 │   ├─ Internal Tools (35+ built-in)
 │   ├─ Plugin Tools (38+ modules)
 │   ├─ MCP Tools (Model Context Protocol)
 │   └─ n8n Workflows
 ├─ Validates with → Fast LLM
 ├─ Saves to → Memory System
 └─ Reports to → Tool Chain UI
```

### Proactive Background Cognition Interactions

```
Proactive Background Cognition
 ├─ Reads from →
 │   ├─ Conversation History (Memory)
 │   ├─ Focus Board State (JSON)
 │   ├─ System Metrics (psutil)
 │   └─ Long-term Goals (Memory Graph)
 ├─ Thinks using → Deep LLM
 ├─ Validates using → Fast LLM
 ├─ Submits to → Orchestrator Worker Pool
 ├─ Updates → Focus Board (WebSocket broadcast)
 └─ Stores insights → Memory System
```

### API Integration Shim Interactions

```
API Integration Shim (IAS)
 ├─ Receives from → External API Clients
 │   ├─ OpenAI SDK format
 │   ├─ Anthropic SDK format
 │   └─ Custom formats
 ├─ Translates to → Vera internal format
 ├─ Routes to → CEO
 ├─ Accesses → Memory System (for context)
 ├─ Returns in → Expected API format
 └─ Enables → External LLMs to use Vera's memory
```

## Communication Patterns

### Synchronous Communication
- User queries via Chat API
- Direct LLM invocations
- Tool execution
- Memory queries

### Asynchronous Communication
- Background cognition ticks
- Focus board updates
- Worker pool task execution
- Proactive alerts

### Real-Time Communication (WebSocket)
- Chat streaming responses
- Focus board live updates
- Tool chain execution monitoring
- Memory graph event streaming

## Configuration Management

### Model Configuration (`Configuration/vera_models.json`)
```json
{
  "embedding_model": "mistral:7b",
  "fast_llm": "gemma2:latest",
  "intermediate_llm": "gemma3:12b",
  "deep_llm": "gemma3:27b",
  "reasoning_llm": "gpt-oss:20b",
  "tool_llm": "gpt-oss:20b"
}
```

### Environment Configuration (`.env`)
```bash
# Neo4j Database
NEO4J_URL=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

# Ollama LLM Service
OLLAMA_BASE_URL=http://localhost:11434

# ChromaDB Vector Database
CHROMADB_HOST=localhost
CHROMADB_PORT=8000

# n8n Workflow Engine
N8N_API_KEY=your_n8n_api_key

# System Configuration
PUID=1000
PGID=1000
TZ=UTC
```

### Focus Board State (`Configuration/focus_boards/*.json`)
```json
{
  "timestamp": "2025-01-15T14:30:00Z",
  "focus": "Network Security Analysis",
  "progress": ["Completed port scan", "Identified open services"],
  "next_steps": ["Analyze vulnerabilities", "Generate report"],
  "issues": ["Service X authentication unclear"],
  "ideas": ["Implement automated patching workflow"],
  "actions": ["Schedule follow-up scan"],
  "completed": ["Initial reconnaissance"]
}
```

## Performance Optimization

### CPU Pinning
Pin critical processes to specific CPU cores to reduce context switching:
```bash
make cpu-pin
```

### NUMA Configuration
Optimize memory access for NUMA architectures:
```bash
make numa-check
make numa-optimize
```

### HugePages
Enable transparent hugepages for large memory workloads:
```bash
make hugepages-setup
```

### Resource Quotas
Configure worker pool resource limits in `orchestrator/resources.py`:
```python
RESOURCE_QUOTAS = {
    "docker": {"max_workers": 4, "max_memory_gb": 16},
    "ollama": {"max_workers": 2, "max_memory_gb": 32},
    "remote": {"max_workers": 10, "max_memory_gb": 100}
}
```

## Security Considerations

### Execution Sandboxing
- **Docker Workers**: Isolated container execution
- **Remote Workers**: Network-separated compute nodes
- **Code Execution**: Restricted to designated sandboxes

### Authentication
- **Neo4j**: Username/password authentication
- **API Endpoints**: API key validation (optional)
- **Worker API**: Token-based authentication

### Data Privacy
- **Local-First**: All data stored locally by default
- **No External Calls**: Unless explicitly configured
- **Audit Logging**: Complete activity log in Layer 4

### Vulnerability Management
- **Snyk Integration**: Automated dependency scanning (`.github/instructions/snyk_rules.instructions.md`)
- **Graph Auditing**: Consistency validation (`Memory/graph_audit.py`)
- **Code Review**: Self-modification changes logged and reversible

## Deployment Architectures

### Single-Node Deployment
```
┌─────────────────────────────────────┐
│         Docker Compose              │
│  ┌──────────┐  ┌──────────┐        │
│  │  Vera    │  │  Neo4j   │        │
│  └──────────┘  └──────────┘        │
│  ┌──────────┐  ┌──────────┐        │
│  │ Ollama   │  │ ChromaDB │        │
│  └──────────┘  └──────────┘        │
└─────────────────────────────────────┘
```

### Distributed Deployment
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Main Node     │    │  Worker Node 1  │    │  Worker Node 2  │
│  ┌──────────┐   │    │  ┌──────────┐   │    │  ┌──────────┐   │
│  │  Vera    │───┼────┼─►│  Worker  │   │    │  │  Worker  │   │
│  └──────────┘   │    │  │   API    │   │    │  │   API    │   │
│  ┌──────────┐   │    │  └──────────┘   │    │  └──────────┘   │
│  │  Neo4j   │   │    │  ┌──────────┐   │    │  ┌──────────┐   │
│  └──────────┘   │    │  │  Docker  │   │    │  │  Ollama  │   │
│  ┌──────────┐   │    │  └──────────┘   │    │  └──────────┘   │
│  │ ChromaDB │   │    └─────────────────┘    └─────────────────┘
│  └──────────┘   │
└─────────────────┘
```

### Proxmox VM Deployment
```
┌──────────────────────────────────────────────────────────┐
│                    Proxmox Cluster                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │  VM 1    │  │  VM 2    │  │  VM 3    │              │
│  │  Vera    │  │  Workers │  │  Ollama  │              │
│  └──────────┘  └──────────┘  └──────────┘              │
│  ┌──────────────────────────────────────┐              │
│  │      Shared NAS Storage (Neo4j)      │              │
│  └──────────────────────────────────────┘              │
└──────────────────────────────────────────────────────────┘
```

## Extension Points

### Adding Custom Workers
Extend `BackgroundCognition/orchestrator/workers/base.py`:
```python
class CustomWorker(BaseWorker):
    def execute_task(self, task: Task) -> TaskResult:
        # Implement custom execution logic
        pass
```

### Adding Custom Tools
Add to `Toolchain/Tools/`:
```python
class CustomTool:
    name = "CustomTool"
    description = "Does something useful"

    def run(self, input_str: str) -> str:
        # Implement tool logic
        return result
```

### Adding Custom Agents
Extend base agent in `Agents/`:
```python
class CustomAgent(BaseAgent):
    def process_query(self, query: str) -> str:
        # Implement agent logic
        return response
```

### Adding Custom Ingestors
Extend `Memory/` ingestor pattern:
```python
class CustomIngestor:
    def ingest(self, source: str):
        # Parse data
        # Create nodes & relationships
        # Insert into Neo4j & ChromaDB
        pass
```

## Monitoring & Observability

### System Metrics
- CPU usage per worker type
- Memory consumption per component
- LLM inference latency
- Vector search performance
- Graph query execution time

### Application Metrics
- Tool chain execution time
- Memory promotion rate
- Background cognition frequency
- Focus board update frequency
- API request rate

### Logging Levels
```python
LOGGING_CONFIG = {
    "version": 1,
    "loggers": {
        "vera.ceo": {"level": "INFO"},
        "vera.memory": {"level": "DEBUG"},
        "vera.toolchain": {"level": "INFO"},
        "vera.workers": {"level": "WARNING"}
    }
}
```

## Troubleshooting

### Common Issues

**High Memory Usage**
- Reduce number of concurrent workers
- Lower LLM model sizes
- Enable memory caching limits

**Slow LLM Responses**
- Use faster model tiers for non-critical tasks
- Enable GPU acceleration
- Distribute across remote workers

**Graph Query Timeouts**
- Add indexes to frequently queried node types
- Limit graph traversal depth
- Use pagination for large result sets

**Worker Pool Exhaustion**
- Increase worker pool size
- Enable remote workers
- Adjust task prioritization

---

**Last Updated:** January 2025
**Version:** 1.0.0
