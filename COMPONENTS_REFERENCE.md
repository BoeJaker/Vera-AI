# Vera-AI Components Reference

## Quick Reference Guide to All Folders and Tools

This document provides a comprehensive index of all components in the Vera-AI repository.

---

## Core Directories

### `/Agents/` - Agent Implementations
**Purpose:** Specialized AI agents for specific tasks
**Size:** 1,529 LOC
**Status:** ✅ Production

| File | Size | Purpose | LLM Tier |
|------|------|---------|----------|
| `executive_0_9.py` | 26KB | Central executive, calendar management, project coordination | Deep/Reasoning |
| `planning.py` | 17KB | Goal decomposition, plan generation, task sequencing | Deep/Reasoning |
| `reviewer.py` | 2KB | Quality assurance, output validation, goal verification | Intermediate |
| `idea_generator.py` | 449B | Creative idea generation, hypothesis formation | Deep |
| `executive_ui.py` | 14KB | Executive agent web interface | N/A |

**Documentation:** [Agents/README.md](Agents/README.md)

---

### `/BackgroundCognition/` - Proactive Orchestration
**Purpose:** Autonomous background thinking and distributed task execution
**Size:** 322KB (27 modules)
**Status:** ✅ Production

#### Core Files

| File | Purpose |
|------|---------|
| `proactive_background_focus.py` | Focus board management, proactive cycles |
| `pbt_v2.py` | Background thinking engine v2 |
| `pbt_ui.py` | Background thinking UI |
| `cluster.py` | Distributed computation clustering |
| `worker_pool.py` | Local worker pool management |
| `registry.py` | Worker registry |
| `tasks.py` | Task definitions |

#### Orchestrator Subsystem (`orchestrator/`)

| File | Purpose |
|------|---------|
| `core.py` | Central orchestrator with intelligent routing |
| `router.py` | Task routing logic (least_loaded, random, round_robin) |
| `resources.py` | Resource management & quota enforcement |
| `tasks.py` | Task models & definitions |
| `api_integration.py` | FastAPI integration layer |

#### Worker Types (`orchestrator/workers/`)

| Worker | Purpose | Capabilities |
|--------|---------|--------------|
| `docker_worker.py` | Docker container execution | Isolated code execution, tool calls |
| `ollama_worker.py` | Local LLM via Ollama | LLM inference, background cognition |
| `llm_api_worker.py` | Cloud APIs (OpenAI, Anthropic, Gemini) | Cloud LLM access |
| `remote_worker.py` | Remote compute nodes | Distributed execution |

**Documentation:** [BackgroundCognition/README.md](BackgroundCognition/README.md)

---

### `/Memory/` - Knowledge Graph & Memory Systems
**Purpose:** Multi-layered persistent memory with graph and vector storage
**Size:** 633KB
**Status:** ✅ Production

#### Core Files

| File | Size | Purpose |
|------|------|---------|
| `memory.py` | 100KB | Hybrid memory system (Neo4j + ChromaDB) |
| `memory_v2.py` | - | Enhanced memory with advanced features |
| `nlp.py` | - | NLP entity extraction, relationship detection |
| `graph_audit.py` | - | Graph validation & consistency checks |
| `archive.py` | - | Long-term archival (Layer 4) |
| `cve_ingestor.py` | - | CVE database ingestion |
| `network_ingestor.py` | - | Network topology ingestion |

#### Memory Layers

| Layer | Storage | Purpose | Content |
|-------|---------|---------|---------|
| **Layer 1** | In-Memory | Short-term context buffer | Last 10-20 messages, system prompts |
| **Layer 2** | Neo4j + ChromaDB | Working memory (session context) | Agent thoughts, notes, task-specific data |
| **Layer 3** | Neo4j + ChromaDB | Long-term knowledge | Entities, relationships, promoted memories |
| **Layer 4** | Postgres + JSONL | Temporal archive | Immutable audit log, version history |
| **Layer 5** | External APIs | Knowledge bases | Web docs, APIs, Git repos |

#### Memory Buffers

| Buffer | Scale | Purpose |
|--------|-------|---------|
| **Micro Buffer** | Tactical | Immediate working context (7±2 chunks) |
| **Macro Buffer** | Operational | Cross-sessional retrieval & associations |
| **Meta Buffer** | Strategic | Knowledge gap analysis, self-modeling |

#### Dashboard (`dashboard/`)

| File | Purpose |
|------|---------|
| `dashboard.py` | Memory visualization backend |
| `graphui.html` | Interactive graph exploration UI |

**Documentation:** [Memory/README.md](Memory/README.md)

---

### `/Toolchain/` - Tool Execution Engine
**Purpose:** Multi-step tool orchestration and execution
**Size:** 812KB (34 modules)
**Status:** ✅ Production

#### Core Files

| File | Purpose |
|------|---------|
| `toolchain.py` | Tool chain planner & executor |
| `enhanced_toolchain_planner.py` | Advanced planning (batch, step, hybrid strategies) |
| `n8n_toolchain.py` | n8n workflow engine integration |
| `dynamic_tools.py` | Dynamic tool discovery |
| `mcp_manager.py` | Model Context Protocol integration |
| `schemas.py` | Input/output schemas for tools |
| `tools.py` | Tool loader & manager |

#### Planning Strategies

| Strategy | Description | Use Case |
|----------|-------------|----------|
| **Batch** | Generate entire plan upfront | Well-defined, predictable workflows |
| **Step** | Generate next step based on results | Adaptive, exploratory tasks |
| **Hybrid** | Mix of batch and adaptive | Most common, balances speed & flexibility |

#### Execution Strategies

| Strategy | Description | Performance |
|----------|-------------|-------------|
| **Sequential** | Execute steps one-by-one | Safe, traceable |
| **Parallel** | Execute independent steps concurrently | Faster |
| **Speculative** | Run multiple possibilities, prune | Advanced, resource-intensive |

#### Tools Subsystem (`Tools/`)

##### Security Tools

| Tool | Purpose |
|------|---------|
| `web_security.py` | OWASP & CWE security testing |
| `dynamic_web_security.py` | Dynamic vulnerability testing |
| `ai_in_the_middle.py` | AI-powered security analysis |
| `securityandML.py` | ML-based security analysis |

##### Code & Development

| Tool | Purpose |
|------|---------|
| `code_executor.py` | Python/Bash code execution |
| `python_parser.py` | Python code analysis |
| `bash_parser.py` | Bash script analysis |
| `version_manager.py` | Version control integration |

##### Translation (`Babelfish/`)

| File | Purpose |
|------|---------|
| `babelfish.py` | Multi-language translation engine |
| `integration.py` | Protocol-agnostic communication |

##### Web Crawling (`Crawlers/`)

| File | Purpose |
|------|---------|
| `corpus_crawler.py` | Web corpus building |
| `tech_detection_rules.json` | Technology stack detection |
| `integration.py` | Crawler integration module |

##### Other Tools

| Tool | Purpose |
|------|---------|
| `protocols.py` | Protocol handling |
| `microcontrollers.py` | IoT/microcontroller tools |
| `file_explorer.py` | File system navigation |
| `memory.py` | Memory file operations |

##### Interactive (`tamagotchi/`)

| File | Purpose |
|------|---------|
| `tamagochi.py` | Interactive AI companion game logic |
| `tamagochi_gen.py` | Generation utilities |

**Total Tools:** 35+ built-in tools

---

### `/plugins/` - Tool Plugins
**Purpose:** Modular tool plugins for network, security, and analysis
**Size:** 38+ modules
**Status:** ✅ Production

#### Network Reconnaissance (10 tools)

| Plugin | Purpose |
|--------|---------|
| `nmap_module.py` | Network scanning (port scan, OS detection) |
| `traceroute.py` | Route tracing |
| `traceroutev2.py` | Enhanced route tracing |
| `dns_records.py` | DNS record lookup |
| `nslookup.py` | DNS query tool |
| `whois_module.py` | WHOIS domain lookup |
| `brute_subdomains.py` | Subdomain enumeration |
| `spider.py` | Web crawling |
| `docker_map.py` | Docker network mapping |
| `detect_technologies.py` | Tech stack detection |

#### Web & Data Extraction (9 tools)

| Plugin | Purpose |
|--------|---------|
| `html_extract_text.py` | HTML text extraction |
| `get-soup.py` | BeautifulSoup wrapper |
| `fb_searchv2.py` | Facebook search v2 |
| `facebook_search.py` | Facebook search |
| `open_webbrowser.py` | Browser automation |
| `open_file.py` | File opening utility |
| `pathwalker.py` | Directory traversal |
| `wordlist_generator.py` | Wordlist generation |
| `port_rules.py` | Port analysis rules |

#### Streaming & Packet Capture (3 tools)

| Plugin | Purpose |
|--------|---------|
| `wireshark.py` | Packet capture & analysis |
| `rtmp.py` | RTMP streaming |
| `mjpeg.py` | MJPEG streaming |

#### Exploitation & Security (3 tools)

| Plugin | Purpose | Size |
|--------|---------|------|
| `metasploit_module.py` | Metasploit framework integration | 9KB |
| `metasploit_http.py` | HTTP exploitation via Metasploit | - |
| `ssh_connect.py` | SSH connection utility | - |

#### Code Analysis (4 tools)

| Plugin | Purpose |
|--------|---------|
| `python_execution_flow.py` | Python execution tracing |
| `python_parser.py` | Python AST parsing |
| `bash_parser.py` | Bash script parsing |
| `example_modules.py` | Plugin template examples |

#### AI & Advanced (9 tools)

| Plugin | Purpose |
|--------|---------|
| `nlp.py` | NLP processing (spaCy) |
| `image_analysis.py` | Image recognition & analysis |
| `hugging_face.py` | HuggingFace model integration |
| `nllp_terminal.py` | NLP terminal interface |
| `stream_to_graph.py` | Real-time data streaming to graph |
| `stream-to_graph0.py` | Streaming variant |

**Total Plugins:** 38+ modules

---

### `/ChatUI/` - Web Interface & API
**Purpose:** FastAPI web interface and real-time APIs
**Size:** 908KB
**Status:** ✅ Production

#### API Routers (`api/` - 12 modules)

| Router | Endpoint | Purpose |
|--------|----------|---------|
| `vera_api.py` | `/api/vera` | Main Vera API aggregator |
| `chat_api.py` | `/api/chat`, `/ws/chat` | Chat endpoints + WebSocket |
| `graph_api.py` | `/api/graph` | Knowledge graph operations |
| `memory_api.py` | `/api/memory` | Memory CRUD operations |
| `toolchain_api.py` | `/api/toolchain` | Tool chain execution & monitoring |
| `vectorstore_api.py` | `/api/vectorstore` | Vector search operations |
| `orchestrator_api.py` | `/api/orchestrator` | Worker orchestration |
| `proactivefocus_api.py` | `/api/focus`, `/ws/focus` | Focus management + WebSocket |
| `notebook_api.py` | `/api/notebook` | Notebook interface |
| `session.py` | `/api/session` | Session management |
| `schemas.py` | - | Pydantic models |
| `logging_config.py` | - | Logging configuration |

#### Frontend JavaScript (`js/`)

| File | Purpose |
|------|---------|
| `chat.js` | Chat interface & message handling |
| `memory.js` | Memory explorer frontend |
| `graph.js` | Knowledge graph visualization (PyVis) |
| `canvas.js` | Canvas drawing utilities |
| `window.js` | Window management |
| `theme.js` | Theme switching (dark/light) |
| `toolchain.js` | Tool chain execution monitoring |
| `proactive-focus-manager.js` | Focus board live updates |
| `notebook.js` | Notebook interface |
| `graph-addon.js` | Graph extensions |
| `enhanced_chat.js` | Enhanced chat features |

#### Tamagotchi UI (`tamagochi/`)

| File | Purpose |
|------|---------|
| `tamagochi_duck.js` | Interactive duck companion |
| `tamagochi_robot.js` | Interactive robot companion |

#### Main UI

| File | Purpose |
|------|---------|
| `orchestrator.html` | Main orchestrator interface |

---

### `/Configuration/` - Configuration Files
**Purpose:** System configuration and focus board state
**Size:** 977KB
**Status:** ✅ Production

| Item | Purpose |
|------|---------|
| `vera_models.json` | LLM model configuration (embedding, fast, intermediate, deep, reasoning) |
| `focus_boards/*.json` | 70+ focus board states (timestamped) |
| `last_tool_plan.json` | Last executed tool chain plan |

#### Model Configuration Structure

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

---

### `/Speech/` - Speech Processing
**Purpose:** Speech recognition and synthesis
**Status:** 🔄 Partial

| File | Purpose |
|------|---------|
| `speech.py` | Speech recognition & synthesis |
| `__init__.py` | Module initialization |

---

### `/worker/` - Distributed Worker System
**Purpose:** Standalone worker nodes for distributed execution
**Status:** ✅ Production

| File | Purpose |
|------|---------|
| `worker_api.py` | Worker API implementation |
| `dockerfile` | Worker container configuration |
| `USER_GUIDE.MD` | Worker setup documentation |

---

### `/projects/` - Project Management
**Purpose:** Project-specific files and configurations
**Status:** 🔄 In Development

*Directory for storing project-specific data, goals, and configurations*

---

### `/.github/` - GitHub Configuration
**Purpose:** CI/CD workflows and repository instructions

#### Workflows (`workflows/`)

| File | Purpose |
|------|---------|
| `update_dev_days.yml` | Automated development days counter |

#### Instructions (`instructions/`)

| File | Purpose |
|------|---------|
| `snyk_rules.instructions.md` | Snyk security scanning rules |

---

### `/Vera Assistant Docs/` - Documentation Archive
**Purpose:** Comprehensive documentation and articles
**Size:** 160KB (20+ files)

#### Core Architecture Docs

| File | Size | Purpose |
|------|------|---------|
| `Vera - Versatile, Evolving Reflective Architecture.md` | 57KB | Main architecture overview |
| `Vera (Veritas) - Article.md` | 16KB | Deep-dive article |
| `Veritas.MD` | 4KB | Veritas concept |

#### Component Documentation

| File | Size | Purpose |
|------|------|---------|
| `Central Executive Orchestrator.md` | 18KB | CEO documentation |
| `Babelfish.md` | 16KB | Protocol translation |
| `Knowledge Graph.md` | 13KB | Graph architecture |
| `Docker Stack.md` | 13KB | Docker deployment |
| `Toolchain Planner.md` | 5KB | Tool chain planning |
| `Corpus Crawler.md` | - | Web crawling |
| `Knowledge Bases.md` | - | External knowledge |
| `Toolkit.md` | - | Tool reference |
| `Scheduler.md` | - | Task scheduling |
| `Prompt Engineering.md` | - | Prompt design guide |

---

## Root Files

### Main Entry Points

| File | Size | Purpose |
|------|------|---------|
| `vera.py` | 49KB | Main orchestrator entry point |
| `proactive_focus_manager.py` | 67KB | Proactive focus management system |
| `start.sh` | 263B | Startup script |

### Build & Deployment

| File | Size | Purpose |
|------|------|---------|
| `makefile` | 24KB | Build automation (40+ targets) |
| `Dockerfile` | - | Main container image (Python 3.11) |
| `docker-compose.yml` | - | Multi-container orchestration |

### Configuration

| File | Purpose |
|------|---------|
| `.env` | Environment variables (n8n API, service URLs) |
| `.gitignore` | Git ignore rules |
| `requirements.txt` | Python dependencies |

### Documentation

| File | Purpose |
|------|---------|
| `README.md` | Main repository README (2,128 lines) |
| `ARCHITECTURE.md` | Architecture documentation |
| `DEVELOPER_GUIDE.md` | Developer setup & workflow |
| `COMPONENTS_REFERENCE.md` | This file - component index |
| `LICENSE` | License information |

### Audit & Reports

| File | Size | Purpose |
|------|------|---------|
| `graph_audit_report.json` | 51KB | Graph validation report |
| `graph_audit_resolutions.json` | 512B | Audit issue resolutions |
| `temp_pyvis_graph.html` | 348KB | Interactive graph visualization |

---

## Makefile Targets Reference

### Setup & Installation

```bash
make install           # Complete installation
make install-system    # System dependencies
make install-python    # Python virtual environment
make install-deps      # Python packages
make install-browsers  # Playwright browsers
make setup-env         # Create .env file
make verify-install    # Validate installation
```

### Development

```bash
make dev               # Development mode
make run               # Run Vera
make run-ui            # Run with UI
make clean             # Clean temporary files
make docs              # Generate documentation
```

### Testing

```bash
make test              # Run all tests
make test-unit         # Unit tests only
make test-integration  # Integration tests
make test-performance  # Performance tests
make lint              # Code linting
make format            # Auto-format code
make coverage          # Test coverage report
```

### Docker Operations

```bash
make docker-build      # Build Docker image
make docker-up         # Start containers
make docker-down       # Stop containers
make docker-logs       # View logs
make docker-shell      # Shell into container
make docker-scale      # Scale workers
make docker-stats      # Resource usage stats
make docker-watch      # Watch mode (auto-reload)
```

### Proxmox Deployment

```bash
make proxmox-deploy    # Deploy to Proxmox VMs
make proxmox-scale     # Scale Proxmox workers
make proxmox-monitor   # Monitor deployment
make proxmox-destroy   # Tear down deployment
```

### Performance

```bash
make performance-test  # Run performance benchmarks
make cpu-pin           # Pin processes to CPU cores
make numa-check        # Check NUMA configuration
make cache-setup       # Setup caching optimizations
make benchmark         # Full benchmark suite
```

---

## Technology Stack Summary

### Languages & Frameworks
- **Python 3.11** - Primary language
- **FastAPI** - REST/WebSocket API framework
- **LangChain** - Multi-agent orchestration

### AI/ML Stack
- **Ollama** - Local LLM inference
- **spaCy** - NLP processing
- **sentence-transformers** - Semantic embeddings
- **scikit-learn** - ML algorithms

### Data Storage
- **Neo4j** - Graph database
- **ChromaDB** - Vector database
- **PostgreSQL** - Audit logging
- **JSONL** - Log streaming

### Frontend
- **HTML/CSS/JavaScript** - Web UI
- **WebSocket** - Real-time communication
- **PyVis** - Graph visualization

### Automation
- **Playwright** - Browser automation
- **BeautifulSoup** - HTML parsing
- **requests/aiohttp** - HTTP clients
- **apscheduler** - Task scheduling

### DevOps
- **Docker** - Containerization
- **Docker Compose** - Orchestration
- **Proxmox** - VM deployment
- **Make** - Build automation

---

## System Metrics

| Metric | Count |
|--------|-------|
| **Total Repository Size** | 3.4GB |
| **Lines of Code (Agents)** | 1,529 |
| **BackgroundCognition Modules** | 27 |
| **Toolchain Modules** | 34 |
| **Plugin Tools** | 38+ |
| **Built-in Tools** | 35+ |
| **API Routers** | 12 |
| **Focus Boards** | 70+ |
| **Documentation Files** | 20+ |
| **Docker Images** | 2 (main, worker) |
| **Makefile Targets** | 40+ |

---

## Quick Start Commands

```bash
# Complete installation
make full-install

# Start all services (requires Agentic Stack)
cd ../AgenticStack-POC && docker compose up -d

# Run Vera
python3 vera.py

# Run with UI
streamlit run ui.py

# Run with Docker
make docker-up

# Run tests
make test

# View documentation
make docs
```

---

**Last Updated:** January 2025
**Version:** 1.0.0
