# Vera-AI Developer Guide

## Table of Contents
1. [Getting Started](#getting-started)
2. [Development Workflow](#development-workflow)
3. [Architecture Overview](#architecture-overview)
4. [Code Structure & Conventions](#code-structure--conventions)
5. [Testing](#testing)
6. [Debugging](#debugging)
7. [Contributing](#contributing)
8. [Deployment](#deployment)

## Getting Started

### Prerequisites

- **Operating System**: Linux (Ubuntu 20.04+), macOS, or WSL2 on Windows
- **Python**: 3.11 or higher
- **Docker**: 20.10+ with Docker Compose
- **System Resources**: Minimum 16GB RAM, 12+ CPU cores (see [System Requirements](README.md#system-requirements))

### Required Services

Vera depends on several external services:

1. **Ollama** - Local LLM inference engine
2. **Neo4j** - Graph database (bolt://localhost:7687)
3. **ChromaDB** - Vector database
4. **PostgreSQL** - Audit logging (optional)

### Development Setup

```bash
# Clone repository
git clone https://github.com/BoeJaker/Vera-AI
cd Vera-AI

# Use makefile for automated setup
make full-install

# Or manual setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install

# Configure environment
cp .env.example .env
# Edit .env with your configuration

# Start required services (using Agentic Stack)
cd ../AgenticStack-POC
docker compose up -d neo4j ollama chromadb

# Verify installation
make verify-install
```

### Project Structure

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed architecture documentation.

```
Vera-AI/
├── vera.py                     # Main entry point
├── proactive_focus_manager.py  # Focus management
├── Agents/                     # Agent implementations
├── BackgroundCognition/        # Orchestration & workers
├── Memory/                     # Knowledge graph & memory
├── Toolchain/                  # Tool execution engine
├── ChatUI/                     # Web interface & APIs
├── plugins/                    # Tool plugins
├── Configuration/              # Config files
└── tests/                      # Test suite
```

## Development Workflow

### Branching Strategy

```
main (production)
  ├── develop (integration branch)
  │   ├── feature/new-tool
  │   ├── feature/memory-optimization
  │   └── bugfix/calendar-sync
  └── hotfix/critical-bug
```

### Making Changes

1. **Create Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make Changes**
   - Write code following conventions (see below)
   - Add tests for new functionality
   - Update documentation

3. **Test Locally**
   ```bash
   make test           # Run all tests
   make lint           # Check code style
   make format         # Auto-format code
   ```

4. **Commit**
   ```bash
   git add .
   git commit -m "feat: Add new feature description"
   ```

5. **Push & Create PR**
   ```bash
   git push origin feature/your-feature-name
   # Create pull request on GitHub
   ```

### Commit Message Format

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `perf`: Performance improvements
- `test`: Adding/updating tests
- `chore`: Maintenance tasks

**Examples:**
```
feat(memory): Add temporal navigation to graph
fix(toolchain): Handle null outputs in plan validation
docs(api): Update ChatAPI endpoint documentation
perf(vectorstore): Optimize embedding search with HNSW
```

## Architecture Overview

### Component Interaction

```
User Input → Chat API → CEO → Router → Workers → Tools → Memory → Response
                ↓                ↓                    ↓
          Proactive Focus    Orchestrator       Knowledge Graph
```

### Key Components

1. **CEO (Central Executive Orchestrator)**: Task routing and resource management
2. **Memory System**: 4-layer memory architecture (see [Memory/README.md](Memory/README.md))
3. **Tool Chain Engine**: Multi-step tool orchestration
4. **Background Cognition**: Proactive thinking and focus management
5. **Worker Pool**: Distributed task execution

### Data Flow

See [ARCHITECTURE.md#data-flow](ARCHITECTURE.md#data-flow) for detailed diagrams.

## Code Structure & Conventions

### Python Style Guide

Follow [PEP 8](https://pep8.org/) with these additions:

**Naming Conventions:**
```python
# Classes: PascalCase
class ExecutiveAgent:
    pass

# Functions/methods: snake_case
def execute_tool_chain(query: str) -> str:
    pass

# Constants: UPPER_SNAKE_CASE
MAX_WORKERS = 4
DEFAULT_MODEL = "gemma2:latest"

# Private methods: _leading_underscore
def _internal_helper():
    pass
```

**Type Hints:**
```python
from typing import List, Dict, Optional, Any

def process_tasks(
    tasks: List[Dict[str, Any]],
    timeout: Optional[int] = None
) -> Dict[str, Any]:
    """Process list of tasks with optional timeout"""
    results: Dict[str, Any] = {}
    # implementation
    return results
```

**Docstrings:**
```python
def complex_function(param1: str, param2: int) -> bool:
    """
    Brief one-line description.

    Longer description explaining what the function does,
    edge cases, and important implementation details.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Description of return value

    Raises:
        ValueError: When param2 is negative
        RuntimeError: When external service unavailable

    Example:
        >>> complex_function("test", 42)
        True
    """
    pass
```

### File Organization

**Agent Files:**
```python
# Agents/my_agent.py
from typing import Dict, Any
from langchain.schema import BaseAgent

class MyAgent(BaseAgent):
    """Agent description"""

    def __init__(self, llm, memory, **kwargs):
        """Initialize agent"""
        super().__init__()
        self.llm = llm
        self.memory = memory

    def process_query(self, query: str) -> str:
        """Main processing method"""
        pass
```

**Tool Files:**
```python
# Toolchain/Tools/my_tool.py
from typing import Optional

class MyTool:
    """Tool description"""

    name = "MyTool"
    description = "What this tool does"

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}

    def run(self, input_str: str) -> str:
        """Execute tool logic"""
        # Implementation
        return result
```

**API Endpoint Files:**
```python
# ChatUI/api/my_api.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/my-endpoint", tags=["MyEndpoint"])

class MyRequest(BaseModel):
    field1: str
    field2: int

@router.post("/action")
async def my_action(request: MyRequest):
    """Endpoint description"""
    try:
        # Implementation
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### Configuration Management

**Environment Variables:**
```python
# Use python-dotenv for .env files
from dotenv import load_dotenv
import os

load_dotenv()

NEO4J_URL = os.getenv("NEO4J_URL", "bolt://localhost:7687")
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
```

**Configuration Files:**
```python
# Use JSON for config files
import json

with open("Configuration/vera_models.json") as f:
    MODEL_CONFIG = json.load(f)

embedding_model = MODEL_CONFIG["embedding_model"]
```

## Testing

### Test Structure

```
tests/
├── unit/                    # Unit tests
│   ├── test_agents.py
│   ├── test_memory.py
│   └── test_toolchain.py
├── integration/             # Integration tests
│   ├── test_api_endpoints.py
│   └── test_worker_pool.py
└── performance/             # Performance tests
    └── test_vector_search.py
```

### Writing Tests

**Unit Tests:**
```python
# tests/unit/test_agents.py
import pytest
from Agents.planning import PlanningAgent

@pytest.fixture
def mock_llm():
    """Mock LLM for testing"""
    class MockLLM:
        def invoke(self, prompt):
            return "Mocked response"
    return MockLLM()

@pytest.fixture
def mock_memory():
    """Mock memory system"""
    class MockMemory:
        def retrieve_context(self, query):
            return []
    return MockMemory()

def test_plan_generation(mock_llm, mock_memory):
    """Test plan generation creates valid plan"""
    agent = PlanningAgent(mock_llm, mock_memory)
    plan = agent.generate_plan("Test goal")

    assert 'tasks' in plan
    assert len(plan['tasks']) > 0
    assert 'total_estimated_time' in plan

def test_dependency_identification(mock_llm, mock_memory):
    """Test dependency detection between tasks"""
    agent = PlanningAgent(mock_llm, mock_memory)
    tasks = [
        {"id": "1", "description": "Task 1"},
        {"id": "2", "description": "Task 2, requires task 1"}
    ]

    deps = agent.identify_dependencies(tasks)
    assert "1" in deps["2"]
```

**Integration Tests:**
```python
# tests/integration/test_api_endpoints.py
import pytest
from fastapi.testclient import TestClient
from ChatUI.api.vera_api import app

client = TestClient(app)

def test_chat_endpoint():
    """Test chat API endpoint"""
    response = client.post(
        "/chat",
        json={"message": "Hello"}
    )

    assert response.status_code == 200
    assert "response" in response.json()

@pytest.mark.asyncio
async def test_websocket_connection():
    """Test WebSocket chat connection"""
    with client.websocket_connect("/ws/chat") as websocket:
        websocket.send_json({"message": "Test"})
        data = websocket.receive_json()
        assert "response" in data
```

**Performance Tests:**
```python
# tests/performance/test_vector_search.py
import pytest
import time
from Memory.memory import HybridMemory

@pytest.mark.performance
def test_vector_search_latency(benchmark_memory):
    """Ensure vector search completes within 200ms"""
    memory = benchmark_memory

    start = time.time()
    results = memory.vector_search("test query", limit=10)
    elapsed = time.time() - start

    assert elapsed < 0.2, f"Search took {elapsed:.3f}s, expected <0.2s"
    assert len(results) > 0
```

### Running Tests

```bash
# Run all tests
make test

# Run specific test file
pytest tests/unit/test_agents.py

# Run specific test
pytest tests/unit/test_agents.py::test_plan_generation

# Run with coverage
make coverage

# Run only fast tests (exclude performance)
pytest -m "not performance"

# Run performance tests
pytest -m performance
```

### Test Coverage

Aim for:
- **Unit Tests**: 80%+ coverage
- **Integration Tests**: Cover all API endpoints
- **Performance Tests**: Critical paths only

```bash
# Generate coverage report
make coverage

# View HTML coverage report
open htmlcov/index.html
```

## Debugging

### Logging

Vera uses Python's built-in logging:

```python
import logging

logger = logging.getLogger(__name__)

# Log levels
logger.debug("Detailed debugging information")
logger.info("General informational message")
logger.warning("Warning message")
logger.error("Error occurred", exc_info=True)
logger.critical("Critical error")
```

**Configure logging:**
```python
# ChatUI/api/logging_config.py
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default"
        },
        "file": {
            "class": "logging.FileHandler",
            "filename": "vera.log",
            "formatter": "default"
        }
    },
    "root": {
        "level": "INFO",
        "handlers": ["console", "file"]
    },
    "loggers": {
        "vera.memory": {"level": "DEBUG"},
        "vera.toolchain": {"level": "INFO"}
    }
}
```

### Debugging Tools

**Interactive Debugger:**
```python
# Insert breakpoint
import pdb; pdb.set_trace()

# Or use built-in breakpoint (Python 3.7+)
breakpoint()
```

**VS Code Debug Configuration:**
```json
// .vscode/launch.json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Vera Main",
            "type": "python",
            "request": "launch",
            "program": "${workspaceFolder}/vera.py",
            "console": "integratedTerminal",
            "env": {
                "PYTHONPATH": "${workspaceFolder}"
            }
        },
        {
            "name": "Vera API",
            "type": "python",
            "request": "launch",
            "module": "uvicorn",
            "args": [
                "ChatUI.api.vera_api:app",
                "--reload"
            ],
            "env": {
                "PYTHONPATH": "${workspaceFolder}"
            }
        }
    ]
}
```

### Common Debugging Scenarios

**Memory System Issues:**
```python
# Enable verbose logging
import logging
logging.getLogger("vera.memory").setLevel(logging.DEBUG)

# Check graph connectivity
from Memory.memory import HybridMemory
memory = HybridMemory()
memory.test_connection()  # Verify Neo4j & ChromaDB

# Audit graph
from Memory.graph_audit import audit_graph
report = audit_graph()
print(report)
```

**Worker Pool Issues:**
```python
# Check worker status
from BackgroundCognition.orchestrator.core import orchestrator
status = await orchestrator.get_worker_status()
print(status)

# Monitor task queue
print(f"Queue size: {orchestrator.task_queue.qsize()}")
```

**LLM Connection Issues:**
```python
# Test Ollama connectivity
import requests
response = requests.get("http://localhost:11434/api/tags")
print(response.json())

# Test specific model
from vera import Vera
vera = Vera()
response = vera.fast_llm.invoke("Say 'OK'")
print(response)
```

## Contributing

### Code Review Guidelines

**For Reviewers:**
- Check code follows style guide
- Verify tests are included and passing
- Ensure documentation is updated
- Look for security issues
- Confirm backward compatibility

**For Contributors:**
- Keep PRs focused and small
- Write descriptive PR descriptions
- Respond to feedback promptly
- Update PR based on comments

### Pull Request Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] All tests passing locally

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No new warnings introduced
```

### Documentation Requirements

- **New Features**: Add to relevant README.md
- **API Changes**: Update API documentation
- **Breaking Changes**: Add to CHANGELOG.md
- **Complex Logic**: Add inline comments

## Deployment

### Local Development

```bash
# Start Vera in development mode
make dev

# Start with UI
make run-ui

# Watch for file changes
make docker-watch
```

### Docker Deployment

```bash
# Build Docker image
make docker-build

# Start with Docker Compose
make docker-up

# View logs
make docker-logs

# Scale workers
make docker-scale workers=4
```

### Proxmox Deployment

```bash
# Deploy to Proxmox VMs
make proxmox-deploy

# Scale Proxmox workers
make proxmox-scale nodes=3

# Monitor Proxmox deployment
make proxmox-monitor
```

### Production Checklist

- [ ] All tests passing
- [ ] Environment variables configured
- [ ] Neo4j credentials secured
- [ ] API keys in .env (not committed)
- [ ] Resource quotas set appropriately
- [ ] Logging configured
- [ ] Monitoring enabled
- [ ] Backup strategy in place
- [ ] Documentation updated

---

## Additional Resources

- [Architecture Documentation](ARCHITECTURE.md)
- [API Reference](ChatUI/api/README.md)
- [Memory System](Memory/README.md)
- [Tool Development](Toolchain/Tools/README.md)
- [Contributing Guidelines](CONTRIBUTING.md)

## Getting Help

- **GitHub Issues**: https://github.com/BoeJaker/Vera-AI/issues
- **Discussions**: https://github.com/BoeJaker/Vera-AI/discussions
- **Documentation**: https://github.com/BoeJaker/Vera-AI/wiki

---

**Last Updated:** January 2025
**Version:** 1.0.0
