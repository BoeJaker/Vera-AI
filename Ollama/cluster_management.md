# Ollama Cluster Manager - Complete TUI Guide

## Overview

The unified Ollama Cluster Manager provides a rich terminal UI for:
- **Real-time cluster monitoring** - Node status, response times, GPU detection
- **Model distribution visualization** - See which models are where
- **Interactive model pulling** - Pull models to specific or all nodes
- **Graph export** - Neo4j Cypher and JSON formats
- **Live dashboards** - Color-coded status indicators and progress bars

## Installation

```bash
# Install dependencies
pip install rich pyyaml requests jinja2

# Make executable
chmod +x ollama_cluster_manager.py
```

## Quick Start

```bash
# Auto-discovers vera_config.yaml in current directory
./ollama_cluster_manager.py

# Or specify config explicitly
./ollama_cluster_manager.py --vera-config /path/to/vera_config.yaml

# With verbose output
./ollama_cluster_manager.py --vera-config vera_config.yaml -v
```

## Dashboard Overview

The main dashboard displays:

```
╭──────────────────────── 🚀 Ollama Cluster Manager ─────────────────────────╮
│                     Last scan: 2026-02-01 14:23:45                         │
╰────────────────────────────────────────────────────────────────────────────╯

╭───────────────── Summary ──────────────────╮
│       Nodes: 5/5 online                    │
│      Models: 12 unique, 47 total           │
╰────────────────────────────────────────────╯

╭─────────────────────── Cluster Status ────────────────────────╮
│ Node                      Status  Models  Response  GPU  Ver  │
├───────────────────────────────────────────────────────────────┤
│ gpu-1                       ●       8      23ms    🎮   0.4.0 │
│ 192.168.0.250:11435                                           │
│ gpu-2                       ●       7      31ms    🎮   0.4.0 │
│ 192.168.0.251:11435                                           │
│ gpu-3                       ●       6      28ms    🎮   0.4.0 │
│ 192.168.0.252:11435                                           │
│ cpu-1                       ●       4      45ms    💻   0.4.0 │
│ 192.168.0.253:11434                                           │
│ backup                      ●       3      67ms    💻   0.3.9 │
│ 192.168.0.254:11434                                           │
╰───────────────────────────────────────────────────────────────╯

╭────────────────── Model Distribution ─────────────────────╮
│ Model                  Nodes  Distribution            Size │
├───────────────────────────────────────────────────────────┤
│ llama3.2:latest         5/5   ████████████████████  2.3GB │
│ qwen2.5:latest          5/5   ████████████████████  4.7GB │
│ deepseek-r1:latest      3/5   ████████████░░░░░░░░  8.2GB │
│ qwen2.5-coder:32b       2/5   ████████░░░░░░░░░░░░  18.1GB│
│ tool-agent:latest       5/5   ████████████████████  2.1GB │
╰───────────────────────────────────────────────────────────╯

Menu:
  1 - Scan cluster
  2 - Pull models
  3 - Export graph
  4 - Refresh dashboard
  q - Quit

Select option [4]: 
```

## Features

### 1. Cluster Monitoring

**Node Status Indicators:**
- 🟢 **Green dot (●)** - Node online and healthy
- 🔴 **Red dot (●)** - Node offline
- 🟡 **Yellow dot (●)** - Node degraded (slow response)

**Hardware Detection:**
- 🎮 **GPU icon** - Node has GPU-accelerated models
- 💻 **CPU icon** - CPU-only node

**Response Times:**
- Measures actual latency to each node
- Helps identify network issues
- Sorted by priority (highest first)

### 2. Model Distribution Visualization

The distribution bar shows model coverage:

```
qwen2.5:latest          5/5   ████████████████████  (All nodes)
deepseek-r1:latest      3/5   ████████████░░░░░░░░  (60% coverage)
experimental:latest     1/5   ████░░░░░░░░░░░░░░░░  (20% coverage)
```

**Color Coding:**
- 🟢 **Green** - Model on all nodes (100% coverage)
- 🟡 **Yellow** - Model on majority of nodes (>50%)
- 🔴 **Red** - Model on minority of nodes (<50%)

### 3. Interactive Model Pulling

Menu option 2 provides interactive model pulling:

```
Pull Models

Models currently in cluster:
  • llama3.2:latest
  • qwen2.5:latest
  • deepseek-r1:latest
  • tool-agent:latest
  • qwen2.5-coder:32b

Enter model name(s) to pull (space-separated): llama3.3:latest phi4:latest
Pull to all online nodes? [Y/n]: y
Skip models that already exist? [Y/n]: y

Pulling llama3.3:latest... ████████████████████ 100% (5/5) 47.3s
✓ llama3.3:latest pulled to all targets

Pulling phi4:latest... ████████████████████ 100% (5/5) 23.8s
✓ phi4:latest pulled to all targets

Refreshing cluster state...
Scanning cluster... ████████████████████ 100% 2.1s
✓ Scan complete
```

**Selective Node Pulling:**

```
Pull to all online nodes? [Y/n]: n

Available nodes:
  1. gpu-1 (192.168.0.250:11435)
  2. gpu-2 (192.168.0.251:11435)
  3. gpu-3 (192.168.0.252:11435)
  4. cpu-1 (192.168.0.253:11434)
  5. backup (192.168.0.254:11434)

Select nodes (comma-separated numbers): 1,2,3

Pulling qwen2.5:72b... ████████████████████ 100% (3/3) 124.7s
✓ qwen2.5:72b pulled to all targets
```

### 4. Graph Export

Export cluster topology for visualization in Neo4j or other tools.

**Neo4j Cypher Format:**

```cypher
MERGE (cluster:OllamaCluster {name: 'main'})
SET cluster.last_scanned = datetime(),
    cluster.total_nodes = 5,
    cluster.online_nodes = 5

MERGE (node_192_168_0_250_11435:OllamaNode {host: "192.168.0.250:11435"})
SET host: "192.168.0.250:11435",
    name: "gpu-1",
    status: "online",
    priority: 10,
    enabled: true,
    gpu_enabled: true,
    model_count: 8

MERGE (node_192_168_0_250_11435)-[:PART_OF]->(cluster)

MERGE (model_llama3_2_latest:OllamaModel {name: "llama3.2:latest"})
SET name: "llama3.2:latest",
    size: 2457740288,
    family: "llama",
    format: "gguf"

MERGE (node_192_168_0_250_11435)-[:HAS_MODEL]->(model_llama3_2_latest)
```

**JSON Graph Format:**

```json
{
  "nodes": [
    {
      "id": "cluster_hub",
      "type": "cluster",
      "label": "Ollama Cluster",
      "properties": {
        "scanned_at": "2026-02-01T14:23:45",
        "total_nodes": 5,
        "online_nodes": 5
      }
    },
    {
      "id": "node_192_168_0_250_11435",
      "type": "ollama_node",
      "label": "gpu-1",
      "properties": {
        "host": "192.168.0.250:11435",
        "status": "online",
        "priority": 10,
        "gpu_enabled": true,
        "model_count": 8,
        "response_time_ms": 23.4
      }
    },
    {
      "id": "model_llama3_2_latest",
      "type": "model",
      "label": "llama3.2:latest",
      "properties": {
        "name": "llama3.2:latest",
        "size": 2457740288,
        "family": "llama"
      }
    }
  ],
  "edges": [
    {
      "source": "node_192_168_0_250_11435",
      "target": "cluster_hub",
      "type": "PART_OF"
    },
    {
      "source": "node_192_168_0_250_11435",
      "target": "model_llama3_2_latest",
      "type": "HAS_MODEL"
    }
  ]
}
```

## Graph Structure

The exported graph uses this schema:

```
         ┌──────────────────┐
         │ OllamaCluster    │
         │   (Hub Node)     │
         └────────┬─────────┘
                  │
         ┌────────┴─────────┐
         │                  │
    ┌────▼─────┐      ┌────▼─────┐
    │OllamaNode│      │OllamaNode│
    │  gpu-1   │      │  gpu-2   │
    └────┬─────┘      └────┬─────┘
         │                 │
    ┌────▼────┐       ┌────▼────┐
    │  Model  │       │  Model  │
    │ llama3.2│       │qwen2.5  │
    └─────────┘       └─────────┘
```

**Node Types:**
- **OllamaCluster** - Hub representing entire cluster
- **OllamaNode** - Individual Ollama instances
- **OllamaModel** - Models (shared across nodes that have them)

**Relationships:**
- **PART_OF** - Node → Cluster
- **HAS_MODEL** - Node → Model

## Neo4j Integration

### Import to Neo4j

```bash
# Export from cluster manager
./ollama_cluster_manager.py --vera-config vera_config.yaml
# Select option 3, then option 1 for Cypher export

# Import to Neo4j
cat cluster_graph_20260201_142345.cypher | cypher-shell -u neo4j -p password
```

### Useful Neo4j Queries

**Find models on all nodes:**
```cypher
MATCH (m:OllamaModel)
WHERE size((m)<-[:HAS_MODEL]-()) = 
      size((:OllamaNode)-[:PART_OF]->(:OllamaCluster))
RETURN m.name as model, 
       size((m)<-[:HAS_MODEL]-()) as node_count
```

**Find nodes without a specific model:**
```cypher
MATCH (n:OllamaNode)
WHERE NOT (n)-[:HAS_MODEL]->(:OllamaModel {name: "llama3.2:latest"})
RETURN n.name, n.host
```

**Get cluster topology:**
```cypher
MATCH (c:OllamaCluster)<-[:PART_OF]-(n:OllamaNode)-[:HAS_MODEL]->(m:OllamaModel)
RETURN c, n, m
```

**Find GPU-enabled nodes:**
```cypher
MATCH (n:OllamaNode {gpu_enabled: true})
RETURN n.name, n.host, n.model_count
ORDER BY n.priority DESC
```

**Model distribution statistics:**
```cypher
MATCH (m:OllamaModel)
WITH m, size((m)<-[:HAS_MODEL]-()) as node_count
RETURN m.name, 
       node_count,
       m.size,
       m.family
ORDER BY node_count DESC
```

## Use Cases

### 1. Monitor Cluster Health

```bash
./ollama_cluster_manager.py --vera-config vera_config.yaml
# Select option 1 to scan
# Review dashboard for offline nodes or slow response times
```

### 2. Ensure Model Consistency

```bash
# Check which models are missing from some nodes
# Use option 2 to pull missing models to specific nodes
```

### 3. Capacity Planning

```bash
# Export graph to analyze model sizes and distribution
# Identify nodes with high model count
# Plan redistribution for better balance
```

### 4. Automated Monitoring

Create a cron job for periodic exports:

```bash
#!/bin/bash
# cluster_monitor.sh

./ollama_cluster_manager.py --vera-config vera_config.yaml << EOF
1
3
3
q
EOF
```

### 5. CI/CD Integration

Use in deployment pipelines:

```bash
# After deploying new models
./ollama_cluster_manager.py --vera-config vera_config.yaml
# Pull to all nodes
# Verify distribution
# Export state to graph database
```

## Performance Tips

### 1. Worker Count Optimization

```bash
# For fast local networks (10Gbps+)
./ollama_cluster_manager.py --vera-config vera_config.yaml --workers 16

# For slower connections
./ollama_cluster_manager.py --vera-config vera_config.yaml --workers 4
```

### 2. Scan Frequency

- **Initial deployment**: Scan after each model pull
- **Production**: Scan every 5-10 minutes
- **Troubleshooting**: Continuous scanning (option 1 repeatedly)

### 3. Selective Pulling

For large models, pull to high-priority GPU nodes only:

```bash
# In interactive mode, select option 2
# Choose specific nodes (e.g., only GPU nodes for 70B models)
```

## Troubleshooting

### Connection Issues

If nodes show offline:

1. Verify Ollama is running: `systemctl status ollama`
2. Check network connectivity: `curl http://node:11434/api/tags`
3. Review firewall rules
4. Check `vera_config.yaml` has correct host:port

### Slow Performance

If scanning is slow:

1. Reduce worker count: `--workers 4`
2. Check network bandwidth
3. Verify DNS resolution is fast
4. Consider local network vs VPN overhead

### Model Pull Failures

If pulls fail:

1. Check disk space on target nodes
2. Verify Ollama version compatibility
3. Test manual pull: `OLLAMA_HOST=node:port ollama pull model`
4. Review Ollama logs on target node

### Graph Export Issues

If export fails:

1. Ensure write permissions in current directory
2. Check disk space
3. Verify node data was collected (run scan first)

## Advanced Features

### Custom Graph Analysis

After exporting JSON, use tools like:

- **NetworkX** (Python) for graph analysis
- **D3.js** for web visualization
- **Gephi** for interactive exploration
- **Graphviz** for diagram generation

### Integration with Vera

The cluster manager complements Vera by:

- Monitoring Vera's Ollama instances
- Ensuring model consistency across instances
- Providing visual topology for debugging
- Exporting state for Vera's knowledge graph

### Automation Scripts

Example auto-sync script:

```python
#!/usr/bin/env python3
import subprocess
import json

# Scan cluster
subprocess.run(["./ollama_cluster_manager.py", "--vera-config", "vera_config.yaml"], 
               input="1\nq\n", text=True)

# Export state
subprocess.run(["./ollama_cluster_manager.py", "--vera-config", "vera_config.yaml"],
               input="3\n2\nq\n", text=True)

# Analyze JSON
with open("cluster_graph_latest.json") as f:
    graph = json.load(f)
    
# Find nodes missing key models
required_models = ["llama3.2:latest", "qwen2.5:latest"]
# ... custom logic ...
```

## Comparison: TUI vs CLI

| Feature | TUI Mode | CLI Mode (old scripts) |
|---------|----------|------------------------|
| Visual feedback | ✅ Rich tables & colors | ❌ Plain text |
| Progress tracking | ✅ Real-time bars | ⚠️ Basic counters |
| Interactive | ✅ Menu-driven | ❌ Command args only |
| Cluster overview | ✅ Dashboard | ❌ Must query each node |
| Model distribution | ✅ Visual bars | ❌ Manual analysis |
| Graph export | ✅ Integrated | ❌ Separate tool needed |
| Learning curve | ✅ Self-documenting | ⚠️ Need to read docs |

## Keyboard Shortcuts

While in TUI:

- **1** - Scan cluster
- **2** - Pull models (interactive)
- **3** - Export graph
- **4** - Refresh dashboard
- **q** - Quit
- **Ctrl+C** - Emergency exit

## Best Practices

1. **Scan before operations** - Always run option 1 before pulling models
2. **Export regularly** - Create snapshots with option 3 for audit trails
3. **Monitor distribution** - Keep key models at 100% coverage (green bars)
4. **Use priorities** - Set higher priority for GPU nodes in vera_config.yaml
5. **Verify after changes** - Rescan after pulling to confirm success

## Future Enhancements

Planned features:

- **Live monitoring mode** - Auto-refresh dashboard every N seconds
- **Model deployment** - Sync custom models from configs
- **Health alerts** - Notify when nodes go offline
- **Resource monitoring** - RAM/VRAM usage tracking
- **Model recommendations** - Suggest which models to pull where
- **Batch operations** - Pull multiple models with one command
- **History tracking** - Track changes over time
- **Web UI** - Browser-based dashboard option