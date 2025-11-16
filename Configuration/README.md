# Configuration

## Overview

The Configuration directory contains centralized settings for Vera's model selection, tool planning, and system behavior. It enables model flexibility, plug-and-play upgrades, and performance tuning without code changes.

## Purpose

Configuration enables:
- **Model flexibility** - Swap LLMs without modifying code
- **Plug-and-play upgrades** - Upgrade models while preserving memories
- **Performance tuning** - Optimize via model selection
- **Environment-specific settings** - Different configs for dev/prod
- **Tool plan caching** - Replay last successful plans

## Key Files

### vera_models.json
**Purpose:** LLM model configuration for different cognitive tasks

**Structure:**
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

**Model Roles:**

| Model Type | Purpose | Typical Size | Use Cases |
|------------|---------|--------------|-----------|
| `embedding_model` | Text vectorization for semantic search | 7B | Encoding documents for ChromaDB |
| `fast_llm` | Quick responses, simple tasks | 2B-7B | Triage, simple queries, validation |
| `intermediate_llm` | Balanced reasoning | 8B-12B | Tool execution, moderate complexity |
| `deep_llm` | Complex reasoning, planning | 20B-27B | Strategic planning, code generation |
| `reasoning_llm` | Heavy logical processing | 20B+ | Multi-step deduction, mathematics |
| `tool_llm` | Tool selection and orchestration | 20B | ToolChain planning |

**Editing:**
```bash
# Edit model configuration
nano Configuration/vera_models.json

# Models are loaded at runtime, changes take effect immediately
```

**Model Compatibility:**
- Must be available in Ollama: `ollama list`
- Pull new models: `ollama pull gemma3:27b`
- Format: `model_name:tag` or `model_name:latest`

---

### last_tool_plan.json
**Purpose:** Cached last successful tool execution plan for replay

**Structure:**
```json
{
  "query": "Analyze network security and generate report",
  "plan": [
    {"tool": "NetworkScanner", "input": "192.168.1.0/24"},
    {"tool": "VulnerabilityAnalyzer", "input": "{step_1}"},
    {"tool": "ReportGenerator", "input": "{step_2}"}
  ],
  "timestamp": "2024-01-15T14:30:00Z",
  "success": true,
  "execution_time_seconds": 45.2
}
```

**Usage:**
```bash
# Replay last plan
python3 vera.py --replay

# Or via API
vera.toolchain.replay_last_plan()
```

**Benefits:**
- Quick iteration during development
- Debugging tool sequences
- Reproducing issues
- Performance benchmarking

---

## Environment Variables

In addition to JSON configs, Vera uses environment variables for sensitive data and runtime settings.

**Create `.env` file:**
```bash
cp .env.example .env
nano .env
```

### LLM Configuration
```bash
# Ollama API endpoint
OLLAMA_API_BASE=http://localhost:11434

# Override models from JSON (optional)
VERA_FAST_LLM=gemma2:latest
VERA_DEEP_LLM=gemma3:27b
```

### Memory Configuration
```bash
# Neo4j Database
NEO4J_URL=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_secure_password

# ChromaDB Vector Store
CHROMADB_HOST=localhost
CHROMADB_PORT=8000
CHROMA_PATH=./vera_agent_memory

# PostgreSQL Archive
POSTGRES_URL=postgresql://user:pass@localhost:5432/vera_archive
```

### Performance Configuration
```bash
# Parallel task limits
MAX_PARALLEL_TASKS=4
MAX_PARALLEL_THOUGHTS=3

# CPU pinning (advanced)
CPU_PINNING=false
NUMA_ENABLED=false

# Memory limits
MAX_MEMORY_GB=32
```

### API Keys (External Services)
```bash
# Optional external integrations
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_CALENDAR_CREDENTIALS=path/to/credentials.json
```

---

## Configuration Hierarchy

Vera uses a layered configuration system:

1. **Hardcoded Defaults** (in code)
2. **JSON Configuration Files** (`vera_models.json`)
3. **Environment Variables** (`.env`)
4. **Runtime Overrides** (command-line flags)

Later layers override earlier ones.

### Example Override Chain:
```python
# 1. Hardcoded default
fast_llm = "mistral:7b"

# 2. Overridden by vera_models.json
# "fast_llm": "gemma2:latest"
fast_llm = "gemma2:latest"

# 3. Overridden by environment variable
# VERA_FAST_LLM=gemma2:2b
fast_llm = "gemma2:2b"

# 4. Overridden by runtime flag
# python3 vera.py --fast-llm gemma2:9b
fast_llm = "gemma2:9b"
```

---

## Model Selection Strategy

### Development Environment
```json
{
  "embedding_model": "mistral:7b",
  "fast_llm": "gemma2:2b",
  "intermediate_llm": "gemma2:9b",
  "deep_llm": "gemma3:12b",
  "reasoning_llm": "gemma3:12b",
  "tool_llm": "gemma3:12b"
}
```
Optimized for speed and quick iteration on modest hardware.

### Production Environment (CPU)
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
Balanced for quality and resource usage on CPU-only systems.

### Production Environment (GPU)
```json
{
  "embedding_model": "mistral:7b",
  "fast_llm": "gemma2:9b",
  "intermediate_llm": "gemma3:27b",
  "deep_llm": "llama3:70b",
  "reasoning_llm": "gpt-oss:20b",
  "tool_llm": "gpt-oss:20b"
}
```
Leverages GPU acceleration for larger, more capable models.

---

## Memory Continuity Across Model Changes

One of Vera's key features is that **memories persist across model upgrades**. When you swap models in `vera_models.json`, the knowledge graph and vector stores remain intact.

### How It Works:
1. **Memory is model-agnostic** - Stored in Neo4j (graph) and ChromaDB (vectors)
2. **Embeddings are separated** - Only the embedding model affects vector representation
3. **Re-embedding on demand** - If embedding model changes, vectors can be regenerated

### Safe Model Upgrade Process:
```bash
# 1. Backup current configuration
cp Configuration/vera_models.json Configuration/vera_models.json.backup

# 2. Edit configuration
nano Configuration/vera_models.json

# 3. Test with new models
python3 vera.py --test

# 4. If issues occur, rollback
cp Configuration/vera_models.json.backup Configuration/vera_models.json

# 5. Verify memory integrity
python3 -c "from Memory.graph_audit import GraphAuditor; GraphAuditor().run_full_audit()"
```

### Embedding Model Changes:
If you change the `embedding_model`, you may want to re-embed existing documents:

```python
from Memory.memory import VeraMemory

memory = VeraMemory()
memory.re_embed_all_documents(new_embedding_model="mistral:7b")
```

This process:
1. Retrieves all documents from ChromaDB
2. Re-encodes them with the new embedding model
3. Updates vector store with new embeddings
4. Preserves all metadata and relationships

---

## Performance Tuning

### For Speed (Fast Responses)
- Use smaller models for `fast_llm` and `intermediate_llm`
- Increase `MAX_PARALLEL_TASKS` for concurrency
- Use local models to avoid API latency

### For Quality (Better Reasoning)
- Use larger models for `deep_llm` and `reasoning_llm`
- Accept longer response times
- Consider external APIs (GPT-4, Claude) for critical tasks

### For Resource Efficiency
- Limit `MAX_PARALLEL_TASKS` to reduce memory usage
- Use quantized models (faster, less memory)
- Enable CPU pinning for predictable performance

---

## Tool Plan Caching

### Automatic Caching
Every successful toolchain execution is automatically saved to `last_tool_plan.json`.

### Manual Caching
```python
from Toolchain.toolchain import ToolChainPlanner

planner = ToolChainPlanner(agent, tools)

# Execute and cache
result = planner.execute_tool_chain("Generate security report")

# Save plan explicitly
planner.save_plan("security_report_plan.json")
```

### Loading Cached Plans
```python
# Load and execute cached plan
plan = planner.load_plan("security_report_plan.json")
result = planner.execute_plan(plan)
```

---

## Configuration Validation

### Validate Configuration
```bash
# Check if all configured models are available
python3 -c "
from Configuration.validate import ConfigValidator
validator = ConfigValidator()
report = validator.validate_all()
print(report)
"
```

### Common Issues

**Model Not Found:**
```
Error: Model 'gemma3:27b' not found in Ollama
Solution: ollama pull gemma3:27b
```

**Invalid JSON:**
```
Error: Configuration file contains invalid JSON
Solution: Use a JSON validator (jq, jsonlint)
```

**Missing Environment Variables:**
```
Error: NEO4J_PASSWORD not set
Solution: Add to .env file
```

---

## Best Practices

### Version Control
- Commit `vera_models.json` to track configuration history
- **DO NOT** commit `.env` (contains secrets)
- Use `.env.example` as a template for others

### Documentation
- Document why you chose specific models
- Note performance characteristics
- Track changes with git commit messages

### Testing
- Test configuration changes in development first
- Verify memory integrity after model changes
- Benchmark performance before/after

### Backup
- Keep backups of working configurations
- Document rollback procedures
- Maintain configuration history

---

## Related Documentation

- [LLM Flexibility and Integration](../README.md#llm-flexibility-and-seamless-integration)
- [Model Compatibility Table](../README.md#model-compatibility)
- [System Requirements](../README.md#system-requirements)
- [Environment Configuration](../README.md#environment-configuration)

## Contributing

To improve configuration management:
1. Add validation scripts
2. Create configuration templates for common use cases
3. Implement configuration migration tools
4. Add performance profiling per model
5. Document optimal settings for different hardware

---

**Related Components:**
- [Agents](../Agents/) - Use configured models for reasoning
- [Toolchain](../Toolchain/) - Cached plans and tool configuration
- [Memory](../Memory/) - Model-agnostic memory persistence
