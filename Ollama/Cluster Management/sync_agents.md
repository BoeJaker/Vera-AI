# Ollama Model Sync for Vera AI

Synchronize custom Ollama models across your Vera AI cluster using YAML configs and Jinja2 templates.

## 🚀 Quick Start (Vera Integration)

```bash
# 1. Setup
bash setup.sh

# 2. List your Vera instances
./ollama-sync list-vera

# 3. Sync one model to all instances
./ollama-sync sync-vera tool-agent.yaml

# 4. Sync all models to all instances
./ollama-sync sync-all-vera
```

## 📋 What This Does

Your Vera AI system has multiple Ollama instances:
- `192.168.0.250:11435` (remote, priority 4)
- `192.168.0.249:11435` (remote-b, priority 3)  
- `192.168.0.248:11435` (remote-c, priority 2)
- `localhost:11434` (local, priority 1)

This tool automatically syncs your custom models to all of them, reading configuration directly from your `vera_config.yaml`.

## 🎯 Key Features

### ✨ Vera Config Integration
- **Auto-discovery**: Reads Ollama instances from `vera_config.yaml`
- **Priority filtering**: Sync only to high-priority instances
- **Enabled/disabled**: Respects instance enable flags
- **One command**: Deploy to entire cluster instantly

### 📝 YAML + Jinja2 Support
- **YAML configs**: Define models declaratively
- **Template system**: Dynamic prompts with variables
- **File inclusion**: Modular prompt components
- **Hot reload**: Changes detected automatically

### 🔧 Production Ready
- **Verification**: Confirms models deployed successfully
- **Rebuild support**: Force recreation when needed
- **Batch operations**: Sync entire directories
- **Error handling**: Clear feedback on failures

## 📦 Files Included

- `ollama_model_sync.py` - Main Python script (full-featured)
- `ollama-sync` - Convenient bash wrapper (quick commands)
- `setup.sh` - One-command setup
- `requirements.txt` - Python dependencies
- `OLLAMA_SYNC_GUIDE.md` - Complete documentation
- `VERA_INTEGRATION_GUIDE.md` - Vera-specific guide
- `example-tool-agent.yaml` - Example model config
- `example_vera_sync.sh` - Interactive demo

## 🎬 Usage Examples

### Sync Single Model
```bash
# To specific host
./ollama-sync sync-one tool-agent.yaml 192.168.0.250:11435

# To all Vera instances
./ollama-sync sync-vera tool-agent.yaml

# With priority filter (only priority >= 3)
PRIORITY_MIN=3 ./ollama-sync sync-vera tool-agent.yaml
```

### Sync All Models
```bash
# To specific host
./ollama-sync sync-all 192.168.0.250:11435

# To all Vera instances (with confirmation)
./ollama-sync sync-all-vera
```

### Test & Verify
```bash
# Test config (build locally only)
./ollama-sync test tool-agent.yaml

# List instances
./ollama-sync list-vera

# Verify deployment
./ollama-sync verify tool-agent 192.168.0.250:11435
```

### Advanced Options
```bash
# Rebuild model even if exists
python ollama_model_sync.py \
  -c tool-agent.yaml \
  --vera-config Configuration/vera_config.yaml \
  --sync-all \
  --rebuild -v

# Sync only high-priority instances
python ollama_model_sync.py \
  -c tool-agent.yaml \
  --vera-config Configuration/vera_config.yaml \
  --sync-all \
  --priority-filter 3

# Sync from specific source
python ollama_model_sync.py \
  -s 192.168.0.250:11435 \
  -c tool-agent.yaml \
  --vera-config Configuration/vera_config.yaml \
  --sync-all
```

## 🗂️ Model Configuration Format

### Example: `tool-agent.yaml`

```yaml
name: "tool-agent"
description: "Agent that executes tools with high precision"

base_model: "qwen2.5:7b"
num_ctx: 65536

parameters:
  temperature: 0.4
  top_p: 0.9
  repeat_penalty: 1.05

# Custom metadata (your tracking)
memory:
  use_vector: true
  use_neo4j: true

# Include files for modularity
includes:
  - includes/tool_list.txt
  - includes/capabilities.md

# System prompt from template
system_prompt:
  template: "prompt_template.j2"
  variables:
    agent_name: "Tool Agent"
    version: "1.0.0"
    enable_advanced_reasoning: false
```

### Template: `prompt_template.j2`

```jinja2
# {{ agent_name }} (v{{ version }})

You are a specialized tool execution agent.

## Available Tools
{{ include_file("includes/tool_list.txt") }}

## Capabilities  
{{ include_file("includes/capabilities.md") }}

{% if enable_advanced_reasoning %}
You may use multi-step reasoning.
{% endif %}
```

## 🔄 Workflow

### 1. Develop Locally
```bash
# Edit model config
vim models/tool-agent.yaml

# Test configuration
./ollama-sync test models/tool-agent.yaml
```

### 2. Deploy to Cluster
```bash
# Sync to all Vera instances
./ollama-sync sync-vera models/tool-agent.yaml
```

### 3. Verify Deployment
```bash
# Check each instance
./ollama-sync verify tool-agent 192.168.0.250:11435
./ollama-sync verify tool-agent 192.168.0.249:11435
./ollama-sync verify tool-agent 192.168.0.248:11435
```

### 4. Use in Vera
```yaml
# vera_config.yaml
models:
  tool_llm: "tool-agent"  # Now available on all instances!
```

## 🔧 Integration with Vera

### Load Balancing
Your synced models work seamlessly with Vera's load balancing:

```yaml
ollama:
  load_balance_strategy: "least_loaded"
  instances:
    - name: "remote"      # Has tool-agent ✓
    - name: "remote-b"    # Has tool-agent ✓
    - name: "remote-c"    # Has tool-agent ✓
```

### Agent System
Sync your agent models to all instances:

```bash
cd Vera/Ollama/Agents
./ollama-sync sync-all-vera
```

Now Vera can use these agents on any instance in the cluster.

## 🤖 Automation

### Cron Job
```bash
# Sync nightly
0 2 * * * /path/to/ollama-sync sync-all-vera >> /var/log/ollama-sync.log 2>&1
```

### Git Hook
```bash
# Auto-sync on commit
#!/bin/bash
if git diff --name-only | grep -q "models/"; then
    ./ollama-sync sync-all-vera
fi
```

### CI/CD
```yaml
# .github/workflows/sync-models.yml
name: Sync Models
on:
  push:
    paths: ['models/**']
jobs:
  sync:
    runs-on: self-hosted
    steps:
      - uses: actions/checkout@v2
      - run: ./ollama-sync sync-all-vera
```

## 🌟 Environment Variables

```bash
# Vera config location
export VERA_CONFIG=/path/to/vera_config.yaml

# Models directory
export MODELS_DIR=./Vera/Ollama/Agents/agents

# Source host
export SOURCE_HOST=localhost:11434

# Priority filter (only sync to priority >= 3)
export PRIORITY_MIN=3

# Verbose output
export VERBOSE=1
```

## 📚 Documentation

- **[OLLAMA_SYNC_GUIDE.md](OLLAMA_SYNC_GUIDE.md)** - Complete usage guide
- **[VERA_INTEGRATION_GUIDE.md](VERA_INTEGRATION_GUIDE.md)** - Vera-specific features

## 🐛 Troubleshooting

### Can't connect to instances
```bash
# Test connectivity
for host in $(./ollama-sync list-vera | tail -n +4 | awk '{print $3}'); do
    echo "Testing $host..."
    curl -sf $host/api/tags > /dev/null && echo "✓" || echo "✗"
done
```

### Models not syncing
```bash
# Enable verbose logging
VERBOSE=1 ./ollama-sync sync-vera tool-agent.yaml

# Check base model exists on targets
./ollama-sync list-target 192.168.0.250:11435 | grep qwen2.5
```

### Vera config not found
```bash
# Check location
ls -l Configuration/vera_config.yaml

# Or set custom path
export VERA_CONFIG=/full/path/to/vera_config.yaml
```

## 💡 Pro Tips

1. **Test first**: Always `./ollama-sync test` before syncing
2. **Use priorities**: Deploy to staging (low priority) before production (high priority)
3. **Check base models**: Ensure base models exist on all targets
4. **Monitor logs**: Use verbose mode for troubleshooting
5. **Automate**: Set up git hooks or cron jobs for continuous sync

## 🎓 Learning Path

1. Start with `setup.sh` to install
2. Run `./ollama-sync list-vera` to see your cluster
3. Try `./ollama-sync test example-tool-agent.yaml`
4. Sync one model: `./ollama-sync sync-vera tool-agent.yaml`
5. Read [VERA_INTEGRATION_GUIDE.md](VERA_INTEGRATION_GUIDE.md) for advanced features

## 🤝 Your Vera Setup

Based on your config, you have:
- **4 Ollama instances** (1 local, 3 remote)
- **Priority-based tiering** (1-4)
- **Load balancing enabled**
- **Perfect for this tool!**

## 📄 License

MIT - Use freely in your Vera AI projects

## ⚡ Need Help?

Check the guides:
- General usage → [OLLAMA_SYNC_GUIDE.md](OLLAMA_SYNC_GUIDE.md)
- Vera integration → [VERA_INTEGRATION_GUIDE.md](VERA_INTEGRATION_GUIDE.md)
- Quick commands → `./ollama-sync help`

---

**Ready to sync your models?**

```bash
./ollama-sync sync-vera tool-agent.yaml
```

Let your entire Vera cluster have access to your custom models! 🚀