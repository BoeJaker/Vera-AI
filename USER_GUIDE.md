# Vera-AI Complete User Guide

**Your Comprehensive Guide to Vera: Intelligence sans Frontières**

Version 1.0 | Last Updated: January 2025

---

## Table of Contents

### Getting Started
1. [What is Vera?](#what-is-vera)
2. [Quick Start Guide](#quick-start-guide)
3. [System Requirements](#system-requirements)
4. [Installation](#installation)
5. [First Steps](#first-steps)

### Core Concepts
6. [Understanding Vera's Architecture](#understanding-veras-architecture)
7. [Memory System Explained](#memory-system-explained)
8. [Agents and Their Roles](#agents-and-their-roles)
9. [The Toolchain Engine](#the-toolchain-engine)
10. [Proactive Background Cognition](#proactive-background-cognition)

### Using Vera
11. [Terminal Interface](#terminal-interface)
12. [Web Interface](#web-interface)
13. [Working with Projects](#working-with-projects)
14. [Voice Interaction](#voice-interaction)
15. [Memory Management](#memory-management)

### Advanced Features
16. [Tool Development](#tool-development)
17. [Custom Agents](#custom-agents)
18. [API Integration](#api-integration)
19. [Distributed Workers](#distributed-workers)
20. [Self-Modification](#self-modification)

### Troubleshooting & Reference
21. [Common Issues](#common-issues)
22. [Configuration Guide](#configuration-guide)
23. [Performance Optimization](#performance-optimization)
24. [FAQ](#faq)
25. [Component Reference](#component-reference)

---

## What is Vera?

Vera is an advanced, **model-agnostic, multi-agent AI architecture** that runs entirely on your local hardware. Unlike cloud-based AI assistants, Vera provides:

### Core Capabilities

**🧠 Multi-Layered Memory**
- Short-term conversational context
- Working memory for active tasks
- Long-term knowledge persistence
- Immutable historical archive
- External knowledge integration

**🤖 Multi-Agent Intelligence**
- Specialized agents for different cognitive tasks
- Triage, planning, execution, and review agents
- Autonomous coordination through shared memory
- Parallel reasoning across multiple LLMs

**🔧 Dynamic Tool Execution**
- Automatic task decomposition
- Multi-step workflow planning
- Error handling and recovery
- Seamless external service integration

**🎯 Proactive Cognition**
- Background autonomous thinking
- Long-term goal tracking
- Deadline monitoring
- Knowledge gap detection

**🔒 Complete Privacy**
- Runs 100% locally
- No data sent to cloud services
- Full control over your data
- Customizable and extensible

---

## Quick Start Guide

### 5-Minute Setup

```bash
# 1. Clone the repository
git clone https://github.com/BoeJaker/Vera-AI
cd Vera-AI

# 2. Install dependencies (automated)
make full-install

# 3. Start required services
cd ../AgenticStack-POC  # or manually start services
docker-compose up -d

# 4. Configure environment
cp .env.example .env
nano .env  # Add your database credentials

# 5. Launch Vera
python3 vera.py
```

**First Interaction:**
```
Vera> Hello! How can I help you today?
You> Explain how your memory system works
Vera> [Detailed explanation with context from knowledge graph...]
```

### Web Interface Quick Start

```bash
# Start the web UI
streamlit run ChatUI/orchestrator.html

# Or use the API
cd ChatUI/api
uvicorn orchestrator_api:app --reload
```

Open browser: `http://localhost:8501`

---

## System Requirements

### Minimum Configuration

**For CPU-Only Operation:**
- **CPU:** 12+ cores (24 threads) @ 3GHz+
- **RAM:** 16GB (32GB recommended)
- **Storage:** 100GB SSD
- **OS:** Linux, macOS, or WSL2

**For GPU-Accelerated Operation:**
- **GPU:** 14GB+ VRAM (NVIDIA recommended)
- **RAM:** 8GB system + GPU VRAM
- **Storage:** 100GB SSD

### Recommended Configuration

**Production CPU Setup:**
- **CPU:** 16+ cores @ 3.5GHz+
- **RAM:** 64GB
- **Storage:** 200GB NVMe SSD
- **Network:** 1Gbps for distributed workers

**Production GPU Setup:**
- **GPU:** 24GB+ VRAM (RTX 4090, A6000)
- **RAM:** 32GB system
- **Storage:** 500GB NVMe SSD

### Understanding Resource Usage

**Memory Tiers:**
- **16GB:** Single fast LLM, limited parallelism
- **32GB:** 2-3 concurrent LLMs, moderate parallelism
- **64GB:** Full multi-agent operation, high parallelism
- **128GB+:** Large-scale deployment, extensive history

**CPU vs GPU:**
- **CPU:** Runs smaller quantized models (3B-13B)
- **GPU:** Runs full-precision larger models (20B-70B)
- **Hybrid:** GPU for deep reasoning, CPU for fast tasks

---

## Installation

### Automated Installation (Recommended)

The Makefile provides one-command installation:

```bash
# Complete installation
make full-install

# Or step-by-step
make install-system     # System dependencies
make install-python     # Python environment
make install-deps       # Python packages
make install-browsers   # Playwright browsers
make setup-env         # Environment config
make verify-install    # Validation
```

### Manual Installation

#### 1. System Dependencies

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y \
    python3.10 python3-pip python3-venv \
    build-essential git curl wget \
    portaudio19-dev ffmpeg
```

**macOS:**
```bash
brew install python@3.10 git portaudio ffmpeg
```

#### 2. Database Services

**Option A: Use AgenticStack-POC (Recommended)**
```bash
git clone https://github.com/BoeJaker/AgenticStack-POC
cd AgenticStack-POC
docker-compose up -d
```

This starts:
- Neo4j (graph database) - Port 7474/7687
- ChromaDB (vector store) - Port 8000
- PostgreSQL (archive) - Port 5432
- Ollama (LLM server) - Port 11434

**Option B: Manual Installation**
```bash
# Install Ollama
curl https://ollama.ai/install.sh | sh
ollama serve &

# Pull models
ollama pull gemma2:latest
ollama pull gemma3:27b
ollama pull mistral:7b

# Install Neo4j (see neo4j.com/download)
# Install PostgreSQL
sudo apt-get install postgresql
```

#### 3. Python Environment

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install browser drivers
playwright install
```

#### 4. Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit configuration
nano .env
```

**Minimum `.env` Configuration:**
```bash
# Neo4j
NEO4J_URL=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

# ChromaDB
CHROMADB_HOST=localhost
CHROMADB_PORT=8000

# Ollama
OLLAMA_BASE_URL=http://localhost:11434

# PostgreSQL
POSTGRES_URL=postgresql://user:pass@localhost:5432/vera_archive
```

#### 5. Verify Installation

```bash
# Run verification
make verify-install

# Or manual checks
curl http://localhost:7474              # Neo4j
curl http://localhost:11434/api/tags    # Ollama
curl http://localhost:8000/api/v1/heartbeat  # ChromaDB

# Test Vera import
python3 -c "import vera; print('✓ Vera ready')"
```

---

## First Steps

### Terminal Interface Tutorial

#### Starting Vera

```bash
# Activate virtual environment
source venv/bin/activate

# Launch Vera
python3 vera.py

# With options
python3 vera.py --triage-memory  # Enable triage memory
python3 vera.py --forgetful      # No memory persistence
python3 vera.py --replay         # Replay last toolchain plan
```

#### Basic Interaction

```
Vera> Hello! I'm Vera, your local AI assistant. How can I help?

You> What can you do?

Vera> I can help with:
- Complex research and analysis
- Code generation and debugging
- Project planning and tracking
- Web scraping and data extraction
- Security analysis and testing
- Multi-step workflow automation
- ... and much more!

You> Create a project to build a REST API

Vera> I'll create a project for building a REST API.
      [Creates project in knowledge graph]
      [Sets up tracking and milestones]

      Project created: "REST API Development"
      Goals:
      1. Design API architecture
      2. Implement endpoints
      3. Add authentication
      4. Write documentation
      5. Deploy to production

      Should I help you start with the architecture design?

You> Yes, let's design the architecture

Vera> [Generates detailed API architecture plan...]
      [Stores design in knowledge graph]
      [Links to project]
```

#### In-Chat Commands

```
/help           # Show available commands
/status         # System status
/memory-stats   # Memory usage
/agents-list    # Active agents
/tools-list     # Available tools
/config         # Configuration
/clear          # Clear conversation
```

### Web Interface Tutorial

#### Launching the Dashboard

```bash
# Method 1: Streamlit UI
streamlit run ChatUI/orchestrator.html

# Method 2: FastAPI backend
cd ChatUI/api
uvicorn orchestrator_api:app --reload
```

#### Dashboard Overview

**Main Panels:**

1. **Chat Interface** (Left)
   - Real-time conversation
   - Message history
   - Voice input/output
   - Code highlighting

2. **Knowledge Graph** (Center)
   - Interactive visualization
   - Node inspection
   - Relationship exploration
   - Search and filter

3. **Toolchain Monitor** (Right)
   - Active executions
   - Step-by-step progress
   - Resource usage
   - Error tracking

4. **Memory Explorer** (Tab)
   - Search memories
   - Browse sessions
   - View relationships
   - Export data

5. **Background Cognition** (Tab)
   - Active thoughts
   - Focus board
   - Worker status
   - Generated insights

#### Web Interface Features

**Real-Time Chat:**
- WebSocket streaming responses
- Markdown rendering
- Code syntax highlighting
- Image/diagram display

**Graph Visualization:**
```javascript
// Click any node to see:
- Properties
- Relationships
- Connected entities
- Creation timestamp

// Actions:
- Zoom/pan/rotate
- Filter by type
- Search entities
- Export subgraph
```

**Memory Search:**
```
Query: "authentication implementation"
Filters:
  - Layers: [Working Memory, Long-Term]
  - Tags: ["security", "api"]
  - Date: Last 30 days

Results: 15 memories found
  - JWT implementation notes
  - OAuth2 research
  - Security best practices
  - Related code snippets
```

---

## Understanding Vera's Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────┐
│                    User Interfaces                       │
│  [Terminal] [Web UI] [API] [Voice]                      │
└────────────────┬────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────┐
│          Central Executive Orchestrator (CEO)           │
│  [Task Routing] [Resource Allocation] [Scheduling]     │
└────────────────┬────────────────────────────────────────┘
                 │
     ┌───────────┼───────────┐
     │           │           │
┌────▼────┐  ┌──▼────┐  ┌──▼──────┐
│ Agents  │  │ Tools │  │ Memory  │
│         │  │       │  │         │
│ Triage  │  │ Web   │  │ Layer 1 │
│ Planning│  │ File  │  │ Layer 2 │
│ Execute │  │ Code  │  │ Layer 3 │
│ Review  │  │ Security│ │ Layer 4 │
└─────────┘  └───────┘  └─────────┘
     │
┌────▼──────────────────────────────────────┐
│  Proactive Background Cognition (PBC)    │
│  [Autonomous Thinking] [Goal Monitoring]  │
└───────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Role | When It Acts |
|-----------|------|--------------|
| **CEO** | Traffic control & orchestration | Every user request |
| **Triage Agent** | Route tasks to appropriate handlers | First contact |
| **Planning Agent** | Break complex goals into steps | Multi-step tasks |
| **Execution Agents** | Run tools and workflows | Task execution |
| **Review Agent** | Validate outputs | After completion |
| **Toolchain Engine** | Orchestrate multi-tool workflows | Complex queries |
| **Memory System** | Store and retrieve context | Continuous |
| **PBC** | Autonomous thinking | Background/idle time |

### Data Flow Example

**User Query:** *"Analyze the security of example.com and create a report"*

```
1. User → CEO
   - Receives query
   - Determines complexity: High

2. CEO → Triage Agent
   - Analyzes: Security + Analysis + Report
   - Routes to Toolchain Engine

3. Toolchain Engine → Planning
   - Generates plan:
     Step 1: Port scan (NetworkScanner)
     Step 2: Vulnerability scan (VulnAnalyzer)
     Step 3: Web crawl (CorpusCrawler)
     Step 4: AI analysis (DeepLLM)
     Step 5: Report generation (ReportTool)

4. Toolchain → Workers
   - Allocates resources
   - Executes sequentially/parallel
   - Handles errors

5. Each Step → Memory
   - Results stored in graph
   - Linked to session
   - Tagged appropriately

6. Review Agent → Validation
   - Checks completeness
   - Verifies accuracy
   - Suggests improvements

7. Final Result → User
   - Comprehensive report
   - Stored in knowledge graph
   - Available for future reference
```

---

## Memory System Explained

### The 5-Layer Architecture

Vera's memory mimics human cognition through distinct storage layers:

#### Layer 1: Short-Term Context Buffer
**Storage:** In-memory (volatile)
**Lifespan:** Active conversation only
**Capacity:** Last 10-20 exchanges

**Contents:**
- Current conversation
- System prompts
- Recent tool outputs
- Active focus

**Example:**
```
[Current conversation]
User: "What's 2+2?"
Vera: "4"
User: "And if I add 3?"
Vera: "7" [remembers previous answer from Layer 1]
```

#### Layer 2: Working Memory (Session Scope)
**Storage:** ChromaDB + Neo4j
**Lifespan:** Single session/task
**Capacity:** Unlimited within session

**Contents:**
- Agent reasoning chains
- Intermediate results
- Task-specific notes
- Exploratory thoughts

**Example:**
```cypher
// Session created for debugging task
CREATE (s:Session {
  id: "session_debug_auth",
  task: "Fix authentication bug",
  started: "2025-01-16T10:00:00Z"
})

// Agent thoughts stored
CREATE (t:Thought {
  content: "Bug likely in JWT validation",
  session_id: "session_debug_auth"
})

// Links to relevant code
MATCH (s:Session {id: "session_debug_auth"})
MATCH (c:Code {file: "auth.py"})
CREATE (s)-[:EXAMINED]->(c)
```

#### Layer 3: Long-Term Knowledge
**Storage:** Neo4j (graph) + ChromaDB (vectors)
**Lifespan:** Permanent
**Capacity:** Unlimited

**Contents:**
- Projects and goals
- Documents and code
- Validated insights
- Learned patterns

**Promotion Process:**
```
Working Memory → Validation → Long-Term Storage

Example:
Session thought: "JWT should expire in 15 min"
↓ [Validated as valuable]
Creates Memory node in graph
↓
Links to Project + Authentication + Security
↓
Full text stored in ChromaDB with vector embedding
↓
Available for semantic search forever
```

**Retrieval:**
```python
# Semantic search
results = memory.query("JWT best practices", top_k=5)

# Returns:
# 1. Text: "JWT tokens should include expiration..."
#    + Graph context: [Project:Auth]-[:REFERENCES]->[Doc:OAuth2]
# 2. Text: "Use RS256 algorithm for production..."
#    + Graph context: [Memory:Security]-[:RELATED_TO]->[Code:auth.py]
```

#### Layer 4: Temporal Archive
**Storage:** PostgreSQL (immutable ledger)
**Lifespan:** Permanent, timestamped
**Capacity:** Unlimited

**Contents:**
- All interactions (every query/response)
- Memory changes (creates, updates, deletes)
- Graph modifications
- System telemetry
- Performance metrics

**Time Travel:**
```sql
-- View knowledge graph state on specific date
SELECT * FROM graph_snapshots
WHERE timestamp = '2025-01-01 00:00:00';

-- Track memory evolution
SELECT * FROM memory_changes
WHERE entity_id = 'Project_Auth'
ORDER BY timestamp;
```

#### Layer 5: External Knowledge Bases
**Storage:** Remote APIs, web services
**Lifespan:** Dynamic (live data)
**Capacity:** Unlimited

**Sources:**
- Wikipedia, documentation sites
- GitHub repositories
- CVE databases
- Live APIs (weather, stock, news)
- DNS/WHOIS records

**Caching:**
```python
# External query
result = fetch_cve_data("CVE-2024-1234")

# Cached in Layer 3 for 24 hours
memory.store_external(
    source="CVE Database",
    content=result,
    cache_ttl=86400
)
```

### Memory Buffers

#### Micro Buffer (Real-Time Focus)
Manages immediate cognitive load:

```
Working on: Fix authentication bug
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Active Context (7±2 items):
✓ Current function: validate_token()
✓ Recent error: "Signature verification failed"
✓ Related code: jwt.decode() call
✓ Security docs: JWT validation section
✓ Previous fix attempt: Updated secret key
✓ Stack trace: Lines 45-52
✓ Test case: test_token_validation()

Filtered out:
✗ Project documentation (not immediately relevant)
✗ Unrelated auth functions
✗ Old debugging sessions
```

#### Macro Buffer (Cross-Session Links)
Connects insights across time:

```cypher
// Find all sessions about authentication
MATCH (s:Session)-[:ABOUT]->(topic:Authentication)
WHERE s.date > date('2025-01-01')
RETURN s, collect(s.insights)

// Results connect:
- Initial OAuth2 research (Jan 5)
- JWT implementation session (Jan 10)
- Security audit (Jan 12)
- Current bug fix (Jan 16)

// Enables question: "What patterns led to this bug?"
```

#### Meta Buffer (Strategic Reasoning)
Understands knowledge gaps:

```
Query: "Implement quantum-resistant encryption"
↓
Meta Buffer analyzes: Do we know quantum cryptography?
↓
Knowledge Graph Search: No quantum crypto entities found
↓
Generates Learning Plan:
1. Research post-quantum cryptography
2. Study NIST PQC standards
3. Evaluate algorithms (Kyber, Dilithium)
4. Implementation guide
5. Then tackle original query
```

---

## Agents and Their Roles

### Agent Hierarchy

```
                 ┌─────────────────┐
                 │   CEO Manager   │
                 └────────┬────────┘
                          │
           ┌──────────────┼──────────────┐
           │              │              │
      ┌────▼────┐    ┌───▼────┐    ┌───▼─────┐
      │ Triage  │    │Planning│    │Scheduler│
      └─────────┘    └────────┘    └─────────┘
                          │
              ┌───────────┼───────────┐
              │           │           │
         ┌────▼───┐  ┌───▼────┐  ┌──▼─────┐
         │Execute │  │ Review │  │Optimize│
         └────────┘  └────────┘  └────────┘
```

### Agent Types by LLM Tier

**Fast Agents** (Mistral 7B, Gemma2 2B)
- Triage agent
- Simple tool execution
- Quick Q&A
- Memory tagging

**Intermediate Agents** (Gemma2 9B, Llama 8B)
- Tool selection
- Basic planning
- Code analysis
- Data processing

**Deep Agents** (Gemma3 27B, GPT-OSS 20B)
- Strategic planning
- Complex reasoning
- Code generation
- Report writing

**Specialized Agents** (Domain-specific models)
- Security analysis
- Mathematical reasoning
- Code review
- Creative writing

### Agent Workflows

#### Triage Agent
```
Incoming Query
↓
Analyze: Complexity? Domain? Tools needed?
↓
Simple query → Fast LLM direct response
Medium query → Intermediate agent + tools
Complex query → Planning agent → Toolchain
```

#### Planning Agent
```
Complex Task
↓
Break into subtasks
↓
Identify dependencies
↓
Allocate resources (LLMs, tools, workers)
↓
Create execution plan
↓
Monitor progress
↓
Adjust if needed
```

#### Review Agent
```
Task Completed
↓
Check: Does output match goal?
↓
Validate: Correct? Complete? Quality?
↓
If issues: Generate feedback → Re-execute
If good: Approve → Store in memory
```

---

## The Toolchain Engine

### Overview

The Toolchain Engine automatically breaks complex queries into executable multi-step workflows.

### Planning Strategies

#### Batch Planning
Generate complete plan upfront:

```json
Query: "Research OAuth2 and implement authentication"
Plan: [
  {"tool": "WebSearch", "input": "OAuth2 specification"},
  {"tool": "WebSearch", "input": "OAuth2 implementation guide"},
  {"tool": "DeepLLM", "input": "Synthesize: {step_1}, {step_2}"},
  {"tool": "CodeGenerator", "input": "Generate from: {step_3}"},
  {"tool": "CodeReviewer", "input": "Review: {step_4}"}
]
```

#### Step-by-Step Planning
Generate next step based on results:

```json
Query: "Debug authentication issue"
Step 1: {"tool": "CodeAnalyzer", "input": "auth.py"}
  → Result: "Potential issue in JWT validation"

Step 2: {"tool": "LogAnalyzer", "input": "error logs"}
  → Result: "Signature mismatch errors"

Step 3: {"tool": "SecurityAuditor", "input": "JWT config"}
  → Result: "Secret key rotation not implemented"

Step 4: {"tool": "CodeGenerator", "input": "Add key rotation"}
```

#### Hybrid Planning
Mix of upfront + adaptive:

```json
Query: "Build REST API"
Upfront: [
  {"tool": "ArchitectureDesigner", "input": "REST API design"},
  {"tool": "DatabaseSchema", "input": "Design schema"}
]
Adaptive: [
  // Steps 3+ determined after architecture is complete
]
```

### Execution Strategies

**Sequential Execution:**
```
Step 1 → Complete → Step 2 → Complete → Step 3
[Safe, traceable, deterministic]
```

**Parallel Execution:**
```
Step 1 ┐
Step 2 ┼→ All complete → Combine results → Step 4
Step 3 ┘
[Faster, requires independence]
```

**Speculative Execution:**
```
Step 1 → Result A or B?
         ├→ If A: Run Steps 2a, 3a
         └→ If B: Run Steps 2b, 3b
Then prune unused branch
[Handles uncertainty]
```

### Error Handling

```
Tool Execution
↓
Success? → Continue
Failure? → Analyze error
         ↓
         Retry? (network timeout)
         Replan? (tool unavailable)
         Escalate? (unrecoverable)
```

---

## Proactive Background Cognition

### What It Does

PBC runs autonomously during idle time to:
- Monitor long-term goals
- Detect approaching deadlines
- Identify knowledge gaps
- Generate insights
- Prepare for future tasks

### How It Works

```
Every 60 seconds (configurable):
┌─────────────────────┐
│ Context Gathering   │
│ - Active projects   │
│ - Pending goals     │
│ - Recent activity   │
│ - System state      │
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│ Thought Generation  │
│ (Deep LLM)          │
│ "What's valuable to │
│  work on right now?"│
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│ Action Validation   │
│ (Fast LLM)          │
│ "Is this executable │
│  and worthwhile?"   │
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│ Execute if Valid    │
│ - Run tools         │
│ - Update focus board│
│ - Store results     │
└─────────────────────┘
```

### Focus Board

Tracks PBC-generated work:

```json
{
  "progress": [
    {
      "task": "Implement JWT refresh tokens",
      "status": "in_progress",
      "completion": 0.65,
      "next_steps": [
        "Add refresh_token field to User model",
        "Implement token rotation logic"
      ],
      "blockers": []
    }
  ],
  "ideas": [
    {
      "idea": "Add Redis caching for sessions",
      "priority": "high",
      "feasibility": 0.9,
      "impact": 0.85
    }
  ],
  "actions": [
    {
      "action": "Research Redis integration patterns",
      "scheduled": "2025-01-16T15:00:00Z",
      "estimated_duration": "30 minutes"
    }
  ],
  "issues": [
    {
      "issue": "No tests for authentication module",
      "severity": "high",
      "proposed_solution": "Generate test suite with 80% coverage"
    }
  ]
}
```

### Example Scenarios

**Deadline Monitoring:**
```
PBC detects: Project "REST API" deadline in 3 days
↓
Checks progress: 60% complete
↓
Identifies blockers: No tests written
↓
Generates action: "Write test suite for API endpoints"
↓
Updates focus board: High priority action
↓
Notifies user: "Reminder: API project due in 3 days, tests needed"
```

**Knowledge Gap Detection:**
```
PBC analyzes: Multiple failed attempts at caching
↓
Searches memory: No Redis documentation
↓
Identifies gap: "Need Redis knowledge"
↓
Generates learning plan:
  1. Fetch Redis documentation
  2. Research cache patterns
  3. Find code examples
↓
Executes autonomously
↓
Updates knowledge graph
```

---

## Terminal Interface

### Basic Commands

```bash
# Start Vera
python3 vera.py

# With options
python3 vera.py --triage-memory  # Enable triage memory
python3 vera.py --forgetful      # Disable memory persistence
python3 vera.py --replay         # Replay last toolchain plan
python3 vera.py --dumbledore     # Silent mode (no responses)
```

### In-Chat Commands

```
/help           Show available commands
/status         System status and resource usage
/memory-stats   Memory layer statistics
/agents-list    List active agents
/tools-list     Show available tools
/config         Display configuration
/clear          Clear conversation history
```

### Example Workflows

**Research & Analysis:**
```
You> Research the latest developments in quantum computing

Vera> I'll research quantum computing developments.
      [Initiates web search toolchain]
      [Searches multiple sources]
      [Synthesizes findings]
      [Stores in knowledge graph]

      Key developments:
      1. IBM's 1,000+ qubit processor
      2. Error correction breakthroughs
      3. Commercial applications emerging

      Would you like details on any specific area?

You> Tell me about error correction breakthroughs

Vera> [Retrieves from just-stored knowledge]
      [Provides detailed explanation]
```

**Code Generation:**
```
You> Generate a Python function to validate email addresses

Vera> I'll create an email validation function.

```python
import re

def validate_email(email: str) -> bool:
    """
    Validate email address format.

    Args:
        email: Email address to validate

    Returns:
        True if valid, False otherwise
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

# Tests
assert validate_email("user@example.com") == True
assert validate_email("invalid.email") == False
```

      Function created with validation and tests.
      Stored in knowledge graph for future reference.
```

**Project Management:**
```
You> Create a project to build a machine learning model

Vera> Creating project: "Machine Learning Model"

      Project Goals:
      1. Data collection and preprocessing
      2. Model selection and training
      3. Hyperparameter tuning
      4. Evaluation and validation
      5. Deployment

      Timeline: 4 weeks
      Priority: High

      Project stored in knowledge graph.
      I'll monitor progress and provide reminders.

      Ready to start with data collection?
```

---

## Web Interface

### Dashboard Layout

```
┌────────────────────────────────────────────────────────┐
│  Vera Dashboard                          [⚙] [👤] [☾] │
├──────────────┬─────────────────────────┬───────────────┤
│              │                         │               │
│  Chat        │   Knowledge Graph       │  Toolchain    │
│  Interface   │   Visualization         │  Monitor      │
│              │                         │               │
│  [Message]   │   ○──○──○               │  Step 1 ✓     │
│  [Message]   │   │  │  │               │  Step 2 →     │
│  [Message]   │   ○──○──○               │  Step 3 ○     │
│              │                         │               │
│  [Input___]  │   [Search] [Filter]     │  [Progress]   │
│              │                         │               │
├──────────────┴─────────────────────────┴───────────────┤
│  [Memory Explorer] [Projects] [Settings] [Logs]        │
└────────────────────────────────────────────────────────┘
```

### Features

**Real-Time Chat:**
- Streaming responses
- Markdown rendering
- Code syntax highlighting
- Image display
- Voice input/output

**Knowledge Graph:**
- Interactive 3D/2D visualization
- Node inspection
- Relationship traversal
- Search and filter
- Temporal navigation
- Export capabilities

**Toolchain Monitor:**
- Live execution tracking
- Step-by-step progress
- Tool outputs
- Error display
- Resource usage
- Timing metrics

**Memory Explorer:**
- Semantic search
- Session browser
- Entity details
- Cross-session queries
- Export memories

**Project Dashboard:**
- Active projects
- Goal tracking
- Progress visualization
- Deadline monitoring
- Task management

---

## Working with Projects

### Creating Projects

**Via Chat:**
```
You> Create a project to implement user authentication

Vera> Project Created: "User Authentication System"

      Automatically generated goals:
      1. Design authentication architecture
      2. Implement user registration
      3. Implement login/logout
      4. Add password reset
      5. Security audit and testing

      Deadline: 2 weeks from now
      Priority: High

      [Project stored in knowledge graph]
      [Proactive monitoring enabled]
```

**Via API:**
```python
from vera import Vera

vera = Vera()

project = vera.create_project(
    name="User Authentication System",
    description="Implement secure auth with OAuth2 and JWT",
    goals=[
        "Design architecture",
        "Implement registration",
        "Implement login/logout",
        "Add password reset",
        "Security audit"
    ],
    deadline="2025-02-01",
    priority="high",
    tags=["security", "backend", "api"]
)
```

### Tracking Progress

```python
# Update goal progress
vera.update_goal_progress(
    project_id="auth_system",
    goal_id="goal_2",
    completion=0.75,
    notes="Registration endpoint complete, testing in progress"
)

# Get project status
status = vera.get_project_status("auth_system")
print(f"Overall: {status['completion']}%")
print(f"Days remaining: {status['days_until_deadline']}")
```

### Proactive Monitoring

Vera automatically monitors projects:

```
[Background Cognition detects]
Project: "User Authentication"
Deadline: 5 days
Completion: 60%

[Generates thought]
"Progress slower than expected, identify blockers"

[Executes analysis]
1. Reviews recent sessions
2. Identifies: "No tests written"
3. Suggests: "Priority: Write test suite"

[Updates focus board]
Action: Write authentication tests
Priority: High
Estimated time: 4 hours

[Notifies user]
"Reminder: Auth project deadline in 5 days.
 Recommended next action: Write test suite (est. 4 hrs)"
```

---

## Voice Interaction

### Setup

```bash
# Install dependencies
pip install faster-whisper TTS sounddevice soundfile

# Download models (automatic on first use)
python3 -c "from TTS.api import TTS; TTS('tts_models/en/vctk/vits')"
```

### Usage

**Python API:**
```python
from Speech.speech import VoiceCommunication

voice = VoiceCommunication(
    model_size="base",  # STT model
    speaker_id="p225"   # TTS voice
)

# Voice-based chat
while True:
    user_query = voice.listen()
    response = vera.process_query(user_query)
    voice.speak(response)
```

**With Vera:**
```python
from vera import Vera
from Speech.speech import VoiceCommunication

vera = Vera()
voice = VoiceCommunication()

print("Voice assistant ready. Speak now...")
while True:
    query = voice.listen()

    if "goodbye" in query.lower():
        voice.speak("Goodbye!")
        break

    response = vera.process_query(query)
    voice.speak(response)
```

### Voice Models

**STT (Speech-to-Text):**
- tiny: Fastest, good accuracy
- base: Recommended for real-time
- small: Better accuracy
- medium: High accuracy
- large: Best accuracy

**TTS (Text-to-Speech):**
- 110+ voices available
- Multiple accents (British, American, etc.)
- Male and female options
- Adjustable speed and pitch

---

## Memory Management

### Viewing Memories

**Memory Explorer (Web UI):**
```
1. Open Memory Explorer tab
2. Search: "authentication"
3. Filter by:
   - Layers: [Working Memory, Long-Term]
   - Tags: ["security", "api"]
   - Date range: Last 30 days
4. View results with full context
```

**Python API:**
```python
# Semantic search
results = vera.memory.query(
    "JWT implementation best practices",
    top_k=10,
    include_relationships=True
)

for result in results:
    print(f"Content: {result['text']}")
    print(f"Related: {result['entities']}")
    print(f"Tags: {result['tags']}")
```

### Managing Sessions

```python
# List recent sessions
sessions = vera.memory.list_sessions(limit=20)

# Get specific session
session = vera.memory.get_session("session_abc123")

# End session (triggers promotion)
vera.memory.end_session(
    session_id="session_abc123",
    promote_all=False,  # Manual promotion for quality
    archive=True
)
```

### Promoting Memories

```python
# Promote thought to long-term memory
vera.memory.promote_to_long_term(
    session_id="session_abc123",
    thought_id="thought_xyz789",
    create_entity=True,
    entity_type="Insight",
    tags=["security", "best-practice"]
)
```

### Memory Maintenance

```python
# Audit graph integrity
from Memory.graph_audit import GraphAuditor

auditor = GraphAuditor(vera.memory)
report = auditor.run_full_audit()
print(report)

# Cleanup old sessions
vera.memory.cleanup_old_sessions(
    older_than_days=90,
    exclude_projects=True  # Keep project-related
)
```

---

## Tool Development

### Creating Custom Tools

```python
# tools/my_custom_tool.py
from Toolchain.tools import Tool

def analyze_sentiment(text: str) -> dict:
    """
    Analyze sentiment of text.

    Args:
        text: Text to analyze

    Returns:
        dict with sentiment scores
    """
    # Your implementation
    return {
        "sentiment": "positive",
        "confidence": 0.92
    }

# Register tool
custom_tool = Tool(
    name="SentimentAnalyzer",
    func=analyze_sentiment,
    description="Analyzes sentiment of text and returns scores"
)
```

### Registering Tools

```python
# In Toolchain/tools.py
def load_tools(self):
    tools = super().load_tools()

    # Add custom tool
    tools.append(custom_tool)

    return tools
```

### Tool Best Practices

1. **Clear naming**: Use descriptive, action-oriented names
2. **Good documentation**: Docstrings help LLM understand usage
3. **Error handling**: Return errors, don't raise exceptions
4. **Type hints**: Help with validation
5. **Idempotency**: Same input → same output

---

## Custom Agents

### Creating an Agent

```python
from Agents.base import Agent

class CustomAnalysisAgent(Agent):
    """Specialized agent for data analysis"""

    def __init__(self, name, llm, memory):
        super().__init__(name, llm, memory)
        self.expertise = "data-analysis"
        self.tools = self.load_specialized_tools()

    def process_query(self, query):
        # Custom reasoning logic
        context = self.fetch_relevant_memory(query)

        prompt = f"""
        As a data analysis expert with context:
        {context}

        Query: {query}

        Provide detailed analysis with:
        1. Statistical insights
        2. Visualizations needed
        3. Actionable recommendations
        """

        response = self.llm.invoke(prompt)
        self.save_to_memory(query, response)

        return response

    def load_specialized_tools(self):
        return [
            Tool(name="StatisticalAnalysis", func=self.stats_analysis),
            Tool(name="DataVisualization", func=self.create_viz),
            Tool(name="PredictiveModeling", func=self.build_model)
        ]
```

### Registering Agents

```python
# In vera.py
from Agents.custom_analysis import CustomAnalysisAgent

# Register during initialization
custom_agent = CustomAnalysisAgent(
    name="data-analyst",
    llm=self.intermediate_llm,
    memory=self.memory
)

self.agents.append(custom_agent)
```

---

## API Integration

### REST API

**Starting the API:**
```bash
cd ChatUI/api
uvicorn orchestrator_api:app --host 0.0.0.0 --port 8000
```

**Endpoints:**

```bash
# Chat
curl -X POST http://localhost:8000/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello", "session_id": "test"}'

# Execute toolchain
curl -X POST http://localhost:8000/api/toolchain/execute \
  -H "Content-Type: application/json" \
  -d '{"query": "Analyze security of example.com"}'

# Search memory
curl -X POST http://localhost:8000/api/memory/search \
  -H "Content-Type: application/json" \
  -d '{"query": "authentication", "top_k": 5}'

# Query graph
curl -X POST http://localhost:8000/api/graph/query \
  -H "Content-Type: application/json" \
  -d '{"cypher": "MATCH (n) RETURN n LIMIT 10"}'
```

### WebSocket API

```javascript
// Connect to chat
const ws = new WebSocket('ws://localhost:8000/ws/chat?session_id=test');

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('Response:', data.content);
};

ws.send(JSON.stringify({
    message: "What is machine learning?",
    session_id: "test"
}));
```

### Python Client

```python
import requests

class VeraClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url

    def chat(self, message, session_id="default"):
        response = requests.post(
            f"{self.base_url}/api/chat/message",
            json={"message": message, "session_id": session_id}
        )
        return response.json()

    def search_memory(self, query, top_k=10):
        response = requests.post(
            f"{self.base_url}/api/memory/search",
            json={"query": query, "top_k": top_k}
        )
        return response.json()

# Usage
client = VeraClient()
result = client.chat("Explain quantum computing")
print(result['content'])
```

---

## Distributed Workers

### Worker Setup

**Start a worker:**
```bash
cd worker
python3 worker_api.py --port 8001 --capabilities cpu,high-memory
```

**Docker deployment:**
```bash
docker run -d \
  --name vera-worker-1 \
  -p 8001:8000 \
  -e WORKER_ID=worker-001 \
  -e WORKER_CAPABILITIES=cpu,high-memory \
  vera-worker:latest
```

### Registering Workers

```python
from BackgroundCognition.worker_pool import WorkerPool

pool = WorkerPool()

# Register remote worker
pool.register_worker(
    url="http://worker-1:8001",
    capabilities=["cpu", "high-memory"],
    priority=1
)
```

### Distributed Execution

```python
# Task execution on worker pool
result = pool.execute_task(
    task={
        "type": "data_processing",
        "data": large_dataset
    },
    required_capabilities=["high-memory"],
    timeout=300
)
```

---

## Self-Modification

### Overview

Vera can modify its own code through a CI/CD pipeline.

### Safety Mechanisms

1. **Testing**: Auto-generated test suites
2. **Validation**: Multi-LLM review
3. **Versioning**: Git-based change tracking
4. **Rollback**: Automatic reversion on failure

### Example Workflow

```
1. Performance analysis detects slow vector search
2. Self-modification engine generates optimization
3. Automated testing validates changes
4. Git commit with detailed context
5. Deployment with monitoring
6. Rollback if metrics degrade
```

---

## Common Issues

### Connection Errors

**Neo4j not responding:**
```bash
# Check status
curl http://localhost:7474

# Restart
docker-compose restart neo4j

# Check logs
docker logs neo4j
```

**ChromaDB connection failed:**
```bash
# Verify service
curl http://localhost:8000/api/v1/heartbeat

# Restart
docker-compose restart chroma
```

### Performance Issues

**High memory usage:**
```bash
# Check resource usage
docker stats

# Limit resources in docker-compose.yml
deploy:
  resources:
    limits:
      memory: 4G
```

**Slow LLM responses:**
```python
# Use smaller/faster models
# Edit Configuration/vera_models.json
{
  "fast_llm": "gemma2:2b",  # Smaller model
  "deep_llm": "gemma3:12b"  # Instead of 27b
}
```

### Installation Issues

**Dependencies fail:**
```bash
# Update pip
pip install --upgrade pip

# Install one at a time
pip install -r requirements.txt --no-cache-dir

# Or use conda
conda env create -f environment.yml
```

---

## Configuration Guide

### Model Selection

**Edit `Configuration/vera_models.json`:**

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

### Environment Variables

**Edit `.env`:**

```bash
# LLM Configuration
OLLAMA_BASE_URL=http://localhost:11434
VERA_FAST_LLM=gemma2:latest
VERA_DEEP_LLM=gemma3:27b

# Memory Configuration
NEO4J_URL=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
CHROMADB_HOST=localhost
CHROMADB_PORT=8000
POSTGRES_URL=postgresql://user:pass@localhost:5432/vera_archive

# Performance
MAX_PARALLEL_TASKS=4
MAX_PARALLEL_THOUGHTS=3
CPU_PINNING=false
NUMA_ENABLED=false

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=http://localhost:3000

# Session
SESSION_TIMEOUT=3600
SESSION_SECRET_KEY=your-secret-key
```

---

## Performance Optimization

### Hardware Optimization

**CPU Pinning:**
```bash
# Enable in .env
CPU_PINNING=true
CPU_CORES=0-7  # Cores to use
```

**NUMA Awareness:**
```bash
# Enable NUMA
NUMA_ENABLED=true

# Check NUMA topology
numactl --hardware
```

**GPU Acceleration:**
```bash
# Verify GPU
nvidia-smi

# Enable GPU in Ollama
export CUDA_VISIBLE_DEVICES=0
```

### Software Optimization

**Model Quantization:**
```bash
# Use quantized models for speed
ollama pull gemma2:7b-q4_0  # 4-bit quantization
ollama pull gemma3:27b-q8_0  # 8-bit quantization
```

**Caching:**
```python
# Enable aggressive caching
ENABLE_RESULT_CACHE=true
CACHE_TTL=3600
```

**Connection Pooling:**
```python
# Increase database connection pools
NEO4J_MAX_CONNECTIONS=50
POSTGRES_POOL_SIZE=20
```

---

## FAQ

**Q: Can Vera run on Windows?**
A: Yes, but use WSL2 for best compatibility. Native Windows support is limited.

**Q: How much does Vera cost to run?**
A: Zero recurring costs after hardware investment. No API fees or subscriptions.

**Q: Can I use cloud LLMs (OpenAI, Anthropic)?**
A: Yes, via API integration shim. Configure API keys in .env.

**Q: Is my data private?**
A: Completely. All processing is local unless you enable external services.

**Q: Can Vera access the internet?**
A: Only if you enable web scraping tools. Internet access is opt-in.

**Q: How do I backup my memories?**
A: See Memory/database server/README.md for backup procedures.

**Q: Can multiple users use one Vera instance?**
A: Yes, with session management. Each user gets isolated context.

**Q: Does Vera require constant internet?**
A: No. Runs completely offline except for external knowledge sources.

---

## Component Reference

### Directory Structure

```
Vera-AI/
├── vera.py                    # Main entry point
├── proactive_focus_manager.py # PBC system
├── Agents/                    # Specialized agents
├── BackgroundCognition/       # Autonomous reasoning
├── ChatUI/                    # Web interface
│   ├── api/                  # REST/WebSocket API
│   ├── js/                   # Frontend JavaScript
│   ├── css/                  # Stylesheets
│   └── tamagochi/            # Interactive mascots
├── Configuration/             # System config
├── Memory/                    # Knowledge graph
│   ├── dashboard/            # Visualization UI
│   └── database server/      # DB infrastructure
├── Speech/                    # Voice I/O
├── Toolchain/                 # Execution engine
│   └── Tools/                # Specialized tools
│       ├── babelfish/        # Protocol translation
│       ├── crawlers/         # Web scraping
│       ├── tamagotchi/       # Monitoring agents
│       └── web security/     # Security analysis
├── Vera Assistant Docs/       # Documentation
├── images/                    # Media assets
├── projects/                  # Project management
└── worker/                    # Distributed execution
```

### Key Files

| File | Purpose | Size |
|------|---------|------|
| `vera.py` | Main orchestrator | 48KB |
| `vera_api.py` | API layer | 175KB |
| `proactive_focus_manager.py` | PBC system | 67KB |
| `requirements.txt` | Dependencies | 6KB |
| `docker-compose.yml` | Services | 446B |
| `makefile` | Build automation | 23KB |

### READMEs

Every directory has a comprehensive README:
- Overview and purpose
- Architecture integration
- Usage examples
- Configuration
- Troubleshooting

**Navigate via:**
```bash
# View directory README
cat Agents/README.md
cat Memory/README.md
cat Toolchain/Tools/babelfish/README.md
```

---

## Getting Help

### Documentation
- **Main README**: [README.md](README.md)
- **User Guide**: This file
- **Component READMEs**: In each directory
- **API Docs**: [ChatUI/api/README.md](ChatUI/api/README.md)

### Community
- **GitHub Issues**: https://github.com/BoeJaker/Vera-AI/issues
- **Discussions**: https://github.com/BoeJaker/Vera-AI/discussions
- **Agentic Stack**: https://github.com/BoeJaker/AgenticStack-POC

### Debugging
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Check system status
python3 -c "from vera import Vera; Vera().system_check()"

# Verify components
make verify-install
```

---

## Quick Reference Card

### Starting Vera
```bash
source venv/bin/activate
python3 vera.py
```

### Web Interface
```bash
streamlit run ChatUI/orchestrator.html
# or
cd ChatUI/api && uvicorn orchestrator_api:app --reload
```

### Memory Explorer
```bash
python3 Memory/dashboard/dashboard.py
```

### Database Services
```bash
cd Memory/database\ server
docker-compose up -d
```

### Essential Commands
```
/help          # Show help
/status        # System status
/memory-stats  # Memory usage
/config        # Configuration
```

### Configuration Files
- **Models**: `Configuration/vera_models.json`
- **Environment**: `.env`
- **Tool Plan**: `Configuration/last_tool_plan.json`

### Database Access
- **Neo4j Browser**: http://localhost:7474
- **Neo4j Bolt**: bolt://localhost:7687
- **ChromaDB**: http://localhost:8000
- **PostgreSQL**: localhost:5432

---

**Version:** 1.0
**Last Updated:** January 2025
**Maintainer:** Vera-AI Project

For the latest updates, visit: https://github.com/BoeJaker/Vera-AI

---

*This guide is continuously updated. Contributions welcome!*
