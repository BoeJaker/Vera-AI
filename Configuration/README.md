# Configuration Directory

## Table of Contents
- [Overview](#overview)
- [Files](#files)
- [Focus Boards](#focus-boards)
- [Model Configuration](#model-configuration)
- [Focus Board Structure](#focus-board-structure)
- [Usage Examples](#usage-examples)
- [Configuration Management](#configuration-management)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

---

## Overview

The Configuration directory stores Vera's system configuration files and proactive focus board snapshots - providing persistent storage for model settings, LLM configurations, tool execution plans, and background thinking session states.

**Purpose:** Configuration storage and focus board persistence
**Total Files:** 100+ focus board snapshots + 2 configuration files
**Status:** ✅ Production
**Storage Format:** JSON

### Directory Structure

```
Configuration/
├── vera_models.json          # LLM model configuration
├── last_tool_plan.json       # Last toolchain execution plan
└── focus_boards/             # Proactive focus session snapshots
    ├── poetry_*.json         # Poetry project focus boards
    ├── network_scanning_*.json   # Network scanning focus boards
    ├── system_info_*.json    # System information focus boards
    ├── games_design_*.json   # Game design focus boards
    └── focus_*.json          # Generic focus boards
```

---

## Files

### `vera_models.json` - Model Configuration

**Purpose:** LLM model selection and configuration

**Size:** ~200 bytes
**Format:** JSON

**Content:**

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

| Model | Role | Use Case |
|-------|------|----------|
| `embedding_model` | Vector embeddings | ChromaDB semantic search, memory retrieval |
| `fast_llm` | Quick responses | Simple queries, fast interactions |
| `intermediate_llm` | Balanced processing | Standard chat, moderate complexity |
| `deep_llm` | Complex reasoning | Deep analysis, long-form generation |
| `reasoning_llm` | Strategic thinking | Planning, decision making, problem solving |
| `tool_llm` | Tool planning | Toolchain orchestration, tool selection |

**Supported Models:**

```python
# Ollama Models
OLLAMA_MODELS = [
    "gemma2:latest",
    "gemma3:12b",
    "gemma3:27b",
    "mistral:7b",
    "llama3:70b",
    "codellama:13b"
]

# OpenAI-compatible Models
OPENAI_MODELS = [
    "gpt-oss:20b",
    "gpt-4",
    "gpt-3.5-turbo"
]
```

**Configuration Loading:**

```python
import json

# Load model configuration
with open('Configuration/vera_models.json', 'r') as f:
    config = json.load(f)

# Initialize Vera with config
from vera import Vera
vera = Vera(
    fast_llm=config['fast_llm'],
    intermediate_llm=config['intermediate_llm'],
    deep_llm=config['deep_llm'],
    reasoning_llm=config['reasoning_llm'],
    tool_llm=config['tool_llm'],
    embedding_model=config['embedding_model']
)
```

---

### `last_tool_plan.json` - Last Tool Plan

**Purpose:** Cache of most recent toolchain execution plan

**Format:** JSON
**Updated:** After each toolchain execution

**Structure:**

```json
{
  "query": "Search for AI news and summarize",
  "strategy": "hybrid",
  "plan": [
    {
      "tool": "WebSearch",
      "input": "AI news 2025"
    },
    {
      "tool": "Summarizer",
      "input": "{prev}"
    }
  ],
  "timestamp": "2025-01-15T10:30:00Z",
  "session_id": "sess_abc123"
}
```

**Usage:**

```python
# Load last plan
with open('Configuration/last_tool_plan.json', 'r') as f:
    last_plan = json.load(f)

# Replay plan
from Toolchain.toolchain import ToolChainPlanner
planner = ToolChainPlanner(vera, vera.tools)
result = planner.execute_tool_chain(
    query=last_plan['query'],
    plan=last_plan['plan']
)
```

---

## Focus Boards

### Overview

Focus boards are JSON snapshots of proactive background thinking sessions - capturing progress, next steps, issues, ideas, and action items for specific topics or projects.

**Total Boards:** 100+ snapshots
**Naming Convention:** `{topic}_{timestamp}.json`
**Categories:**
- Poetry writing sessions
- Network scanning projects
- System information gathering
- Game design brainstorming
- Generic focus sessions

### Focus Board Categories

#### Poetry Focus Boards (`poetry_*.json`)

**Purpose:** Creative writing and poetry composition sessions

**Total Files:** ~40 snapshots
**Example:** `poetry_20251106_200603.json`

**Typical Content:**

```json
{
  "focus": "poetry",
  "project_id": null,
  "created_at": "2025-11-06T20:06:03.162973",
  "board": {
    "progress": [
      "Brainstormed 5 poetry themes",
      "Drafted first 8-line poem about nature"
    ],
    "next_steps": [
      {
        "note": "Write second draft incorporating feedback",
        "timestamp": "2025-11-06T20:10:00Z",
        "metadata": {}
      },
      {
        "note": "Research haiku structure and attempt 3 haikus",
        "timestamp": "2025-11-06T20:11:00Z",
        "metadata": {}
      }
    ],
    "issues": [
      {
        "note": "Struggling with meter in sonnet form",
        "timestamp": "2025-11-06T20:12:00Z",
        "metadata": {}
      }
    ],
    "ideas": [
      {
        "note": "Explore contrast between urban and natural imagery",
        "timestamp": "2025-11-06T20:13:00Z",
        "metadata": {}
      },
      {
        "note": "Consider collaboration with visual artist",
        "timestamp": "2025-11-06T20:14:00Z",
        "metadata": {}
      }
    ],
    "actions": [
      {
        "note": "Research inspirational poets using web search",
        "timestamp": "2025-11-06T20:15:00Z",
        "metadata": {
          "description": "Research poets",
          "tools": ["DuckDuckGo Web Search"],
          "priority": "medium"
        }
      }
    ],
    "completed": [
      {
        "note": "Brainstormed 3-5 potential themes",
        "timestamp": "2025-11-06T20:16:00Z",
        "metadata": {}
      }
    ]
  },
  "metadata": {
    "session_id": "sess_1762456906279"
  }
}
```

---

#### Network Scanning Focus Boards (`network_scanning_*.json`)

**Purpose:** Network reconnaissance and security scanning sessions

**Total Files:** ~25 snapshots
**Example:** `network_scanning_20251104_022742.json`

**Typical Content:**

```json
{
  "focus": "network_scanning",
  "project_id": "netscan_001",
  "created_at": "2025-11-04T02:27:42.000000",
  "board": {
    "progress": [
      "Completed initial nmap scan of 192.168.1.0/24",
      "Identified 15 active hosts",
      "Performed service version detection"
    ],
    "next_steps": [
      {
        "note": "Run vulnerability scan on identified services",
        "timestamp": "2025-11-04T02:30:00Z",
        "metadata": {
          "target": "192.168.1.100"
        }
      },
      {
        "note": "Analyze open ports for security risks",
        "timestamp": "2025-11-04T02:31:00Z",
        "metadata": {}
      }
    ],
    "issues": [
      {
        "note": "Port 22 (SSH) exposed on 5 hosts",
        "timestamp": "2025-11-04T02:32:00Z",
        "metadata": {
          "severity": "medium",
          "affected_hosts": ["192.168.1.100", "192.168.1.101"]
        }
      }
    ],
    "ideas": [
      {
        "note": "Implement automated periodic scanning",
        "timestamp": "2025-11-04T02:33:00Z",
        "metadata": {}
      }
    ],
    "actions": [
      {
        "note": "Execute deep port scan on host 192.168.1.100",
        "timestamp": "2025-11-04T02:34:00Z",
        "metadata": {
          "description": "Deep scan",
          "tools": ["Nmap"],
          "priority": "high"
        }
      }
    ]
  }
}
```

---

#### System Information Focus Boards (`system_info_*.json`)

**Purpose:** System monitoring and information gathering

**Total Files:** ~5 snapshots

**Example Content:**

```json
{
  "focus": "system_info",
  "created_at": "2025-11-11T01:58:49.000000",
  "board": {
    "progress": [
      "Gathered CPU information",
      "Checked disk usage",
      "Monitored memory consumption"
    ],
    "next_steps": [
      {
        "note": "Analyze performance bottlenecks",
        "timestamp": "2025-11-11T02:00:00Z"
      }
    ],
    "issues": [
      {
        "note": "High memory usage detected (85%)",
        "timestamp": "2025-11-11T02:01:00Z",
        "metadata": {"severity": "warning"}
      }
    ]
  }
}
```

---

#### Game Design Focus Boards (`games_design_pico-8_*.json`)

**Purpose:** Game design and development brainstorming

**Total Files:** ~2 snapshots

**Example:**

```json
{
  "focus": "games_design_pico-8",
  "created_at": "2025-11-09T08:55:42.000000",
  "board": {
    "progress": [
      "Defined core game mechanic: platformer with time rewind",
      "Sketched initial level design"
    ],
    "next_steps": [
      {
        "note": "Implement basic player movement in PICO-8",
        "timestamp": "2025-11-09T09:00:00Z"
      },
      {
        "note": "Design sprite sheet for player character",
        "timestamp": "2025-11-09T09:01:00Z"
      }
    ],
    "ideas": [
      {
        "note": "Add sound effects using PICO-8's music tracker",
        "timestamp": "2025-11-09T09:02:00Z"
      }
    ]
  }
}
```

---

## Focus Board Structure

### Standard Fields

```json
{
  "focus": "string",           // Topic identifier
  "project_id": "string|null", // Associated project ID
  "created_at": "ISO8601",     // Creation timestamp
  "board": {
    "progress": [],            // Completed items
    "next_steps": [],          // Upcoming tasks
    "issues": [],              // Problems and blockers
    "ideas": [],               // Creative insights
    "actions": [],             // Executable actions with tools
    "completed": []            // Archived completed items
  },
  "metadata": {
    "session_id": "string"     // Originating session
  }
}
```

### Entry Structure

Each entry in `next_steps`, `issues`, `ideas`, `actions`, and `completed` follows this format:

```json
{
  "note": "string",            // Main content
  "timestamp": "ISO8601",      // When created
  "metadata": {                // Optional metadata
    "key": "value"
  }
}
```

### Action Entry Structure

Actions include additional fields for tool execution:

```json
{
  "note": "Description of action",
  "timestamp": "ISO8601",
  "metadata": {
    "description": "Detailed description",
    "tools": ["Tool1", "Tool2"],    // Required tools
    "priority": "high|medium|low"   // Priority level
  }
}
```

---

## Usage Examples

### Creating a Focus Board

```python
from datetime import datetime
import json

# Create focus board
focus_board = {
    "focus": "security_audit",
    "project_id": "proj_001",
    "created_at": datetime.utcnow().isoformat(),
    "board": {
        "progress": [
            "Completed initial vulnerability scan",
            "Identified 3 critical issues"
        ],
        "next_steps": [
            {
                "note": "Patch critical vulnerabilities",
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": {"priority": "critical"}
            }
        ],
        "issues": [],
        "ideas": [],
        "actions": [],
        "completed": []
    },
    "metadata": {
        "session_id": "sess_abc123"
    }
}

# Save to file
filename = f"Configuration/focus_boards/security_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
with open(filename, 'w') as f:
    json.dump(focus_board, f, indent=2)
```

---

### Loading a Focus Board

```python
import json
from pathlib import Path

# Load most recent focus board for topic
def load_latest_focus_board(topic):
    focus_boards_dir = Path('Configuration/focus_boards')
    boards = sorted(
        focus_boards_dir.glob(f'{topic}_*.json'),
        reverse=True
    )

    if not boards:
        return None

    with open(boards[0], 'r') as f:
        return json.load(f)

# Usage
poetry_board = load_latest_focus_board('poetry')
print(f"Progress: {len(poetry_board['board']['progress'])} items")
print(f"Next steps: {len(poetry_board['board']['next_steps'])} items")
```

---

### Updating a Focus Board

```python
# Load existing board
with open('Configuration/focus_boards/poetry_latest.json', 'r') as f:
    board = json.load(f)

# Add progress
board['board']['progress'].append("Completed first draft of haiku series")

# Add next step
board['board']['next_steps'].append({
    "note": "Revise haiku series based on feedback",
    "timestamp": datetime.utcnow().isoformat(),
    "metadata": {}
})

# Save updated board
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
with open(f'Configuration/focus_boards/poetry_{timestamp}.json', 'w') as f:
    json.dump(board, f, indent=2)
```

---

## Configuration Management

### Model Configuration Updates

```python
def update_model_config(updates):
    """Update model configuration"""
    config_file = 'Configuration/vera_models.json'

    # Load existing
    with open(config_file, 'r') as f:
        config = json.load(f)

    # Apply updates
    config.update(updates)

    # Save
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)

# Usage
update_model_config({
    'fast_llm': 'gemma2:9b',
    'deep_llm': 'llama3:70b'
})
```

---

### Focus Board Cleanup

```python
from pathlib import Path
from datetime import datetime, timedelta

def cleanup_old_focus_boards(days=30):
    """Remove focus boards older than specified days"""
    cutoff_date = datetime.now() - timedelta(days=days)
    focus_boards_dir = Path('Configuration/focus_boards')

    for board_file in focus_boards_dir.glob('*.json'):
        # Extract timestamp from filename
        timestamp_str = board_file.stem.split('_')[-2:]
        timestamp_str = '_'.join(timestamp_str)

        try:
            file_date = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
            if file_date < cutoff_date:
                board_file.unlink()
                print(f"Removed old focus board: {board_file.name}")
        except ValueError:
            # Skip files with invalid timestamp format
            continue

# Usage
cleanup_old_focus_boards(days=30)
```

---

### Focus Board Analytics

```python
def analyze_focus_boards(topic):
    """Analyze focus board progression over time"""
    focus_boards_dir = Path('Configuration/focus_boards')
    boards = sorted(focus_boards_dir.glob(f'{topic}_*.json'))

    analytics = {
        'total_boards': len(boards),
        'total_progress': 0,
        'total_next_steps': 0,
        'total_issues': 0,
        'total_ideas': 0,
        'total_completed': 0
    }

    for board_file in boards:
        with open(board_file, 'r') as f:
            board = json.load(f)
            b = board['board']

            analytics['total_progress'] += len(b.get('progress', []))
            analytics['total_next_steps'] += len(b.get('next_steps', []))
            analytics['total_issues'] += len(b.get('issues', []))
            analytics['total_ideas'] += len(b.get('ideas', []))
            analytics['total_completed'] += len(b.get('completed', []))

    return analytics

# Usage
stats = analyze_focus_boards('poetry')
print(f"Poetry project statistics:")
print(f"  Total sessions: {stats['total_boards']}")
print(f"  Total progress items: {stats['total_progress']}")
print(f"  Total next steps: {stats['total_next_steps']}")
```

---

## Best Practices

### 1. Model Configuration

**Do:**
- Test new models before updating production config
- Document model selection rationale
- Keep backup of working configurations
- Use appropriate models for task complexity

**Don't:**
- Change models mid-session
- Use slow models for fast operations
- Ignore model deprecation warnings

---

### 2. Focus Board Management

**Do:**
- Create timestamped snapshots
- Include descriptive metadata
- Archive completed items
- Regular cleanup of old boards

**Don't:**
- Manually edit timestamps
- Delete recent boards without backup
- Mix different topics in same board

---

### 3. File Organization

**Do:**
- Use consistent naming conventions
- Group related focus boards
- Maintain chronological order
- Back up regularly

**Don't:**
- Use spaces in filenames
- Mix configuration types
- Store large files in this directory

---

## Troubleshooting

### Common Issues

**Model Not Found:**
```python
# Verify model exists in Ollama
import subprocess
result = subprocess.run(['ollama', 'list'], capture_output=True, text=True)
print(result.stdout)

# Pull missing model
subprocess.run(['ollama', 'pull', 'gemma2:latest'])
```

**Focus Board Parse Error:**
```python
# Validate JSON
import json

try:
    with open('Configuration/focus_boards/poetry_latest.json', 'r') as f:
        board = json.load(f)
except json.JSONDecodeError as e:
    print(f"Invalid JSON: {e}")
    print(f"Line {e.lineno}, Column {e.colno}")
```

**Configuration Not Loading:**
```python
# Check file permissions
import os
config_file = 'Configuration/vera_models.json'

if not os.path.exists(config_file):
    print(f"File not found: {config_file}")
elif not os.access(config_file, os.R_OK):
    print(f"No read permission: {config_file}")
    os.chmod(config_file, 0o644)
```

---

## Related Documentation

- [Proactive Focus System](../BackgroundCognition/proactive_focus.md)
- [Model Configuration Guide](../docs/model_configuration.md)
- [Toolchain Planning](../Toolchain/README.md)

---

**Last Updated:** January 2025
**Maintainer:** Vera-AI Development Team
**Version:** 1.0.0
