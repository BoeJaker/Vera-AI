# Projects Directory

## Table of Contents
- [Overview](#overview)
- [Directory Structure](#directory-structure)
- [Project Management](#project-management)
- [Project Structure](#project-structure)
- [Usage Examples](#usage-examples)
- [Best Practices](#best-practices)
- [Integration](#integration)

---

## Overview

The projects directory provides project-based organization for Vera's work - storing project-specific files, progress tracking, and context isolation for focused multi-session work on specific goals or initiatives.

**Purpose:** Project workspace and progress tracking
**Total Projects:** User-defined
**Status:** ✅ Production
**Storage Format:** Directory-based with progress files

### Key Features

- **Project Isolation**: Separate workspaces for different initiatives
- **Progress Tracking**: Track completion status per project
- **Context Persistence**: Maintain project-specific memory and context
- **File Organization**: Structured file storage per project
- **Multi-Session Support**: Continue projects across multiple sessions
- **Integration**: Links with Focus Boards and Memory system

---

## Directory Structure

```
projects/
├── test/                    # Example test project
│   └── progress.txt         # Progress tracking file
├── project_1/              # User project 1
│   ├── progress.txt
│   ├── notes.md
│   └── files/
├── project_2/              # User project 2
│   ├── progress.txt
│   └── data/
└── ...
```

### Standard Project Layout

```
project_name/
├── progress.txt            # Progress tracking (required)
├── README.md               # Project description
├── notes.md                # Project notes
├── config.json             # Project configuration
├── files/                  # Project files
│   ├── documents/
│   ├── data/
│   └── outputs/
├── focus_boards/           # Project-specific focus boards
└── memory/                 # Project-specific memory exports
```

---

## Files

### `test/progress.txt` - Example Progress File

**Purpose:** Track project completion status

**Format:** Plain text or JSON

**Example Content:**

```
Project: Test Project
Status: In Progress
Created: 2025-01-15
Last Updated: 2025-01-20

Progress:
- [x] Initialize project structure
- [x] Define project goals
- [ ] Complete implementation
- [ ] Testing phase
- [ ] Documentation

Notes:
- This is a test project for demonstrating the structure
- Add additional progress items as needed
```

**JSON Format:**

```json
{
  "project_name": "Test Project",
  "status": "in_progress",
  "created": "2025-01-15",
  "updated": "2025-01-20",
  "progress": [
    {"task": "Initialize project structure", "completed": true},
    {"task": "Define project goals", "completed": true},
    {"task": "Complete implementation", "completed": false},
    {"task": "Testing phase", "completed": false},
    {"task": "Documentation", "completed": false}
  ],
  "completion_percentage": 40,
  "notes": [
    "This is a test project for demonstrating the structure",
    "Add additional progress items as needed"
  ]
}
```

---

## Project Management

### Creating a New Project

```python
from pathlib import Path
import json
from datetime import datetime

def create_project(project_name, description="", goals=None):
    """
    Create new project with standard structure

    Args:
        project_name: Name of project
        description: Project description
        goals: List of project goals

    Returns:
        Path to project directory
    """
    # Create project directory
    project_dir = Path('projects') / project_name
    project_dir.mkdir(parents=True, exist_ok=True)

    # Create subdirectories
    (project_dir / 'files').mkdir(exist_ok=True)
    (project_dir / 'files' / 'documents').mkdir(exist_ok=True)
    (project_dir / 'files' / 'data').mkdir(exist_ok=True)
    (project_dir / 'files' / 'outputs').mkdir(exist_ok=True)
    (project_dir / 'focus_boards').mkdir(exist_ok=True)
    (project_dir / 'memory').mkdir(exist_ok=True)

    # Create README
    readme_content = f"""# {project_name}

## Description
{description}

## Goals
{chr(10).join(f'- {goal}' for goal in (goals or []))}

## Created
{datetime.now().strftime('%Y-%m-%d')}
"""
    (project_dir / 'README.md').write_text(readme_content)

    # Create progress file
    progress = {
        "project_name": project_name,
        "description": description,
        "status": "not_started",
        "created": datetime.now().isoformat(),
        "updated": datetime.now().isoformat(),
        "goals": goals or [],
        "progress": [],
        "completion_percentage": 0,
        "notes": []
    }

    (project_dir / 'progress.txt').write_text(
        json.dumps(progress, indent=2)
    )

    # Create config
    config = {
        "project_name": project_name,
        "focus_topic": project_name.lower().replace(' ', '_'),
        "memory_context": f"project:{project_name}",
        "auto_save": True,
        "notifications": True
    }

    (project_dir / 'config.json').write_text(
        json.dumps(config, indent=2)
    )

    print(f"Project created: {project_dir}")
    return project_dir

# Usage
create_project(
    "Network Security Audit",
    description="Comprehensive network security assessment",
    goals=[
        "Scan network for vulnerabilities",
        "Analyze findings",
        "Generate security report",
        "Implement fixes"
    ]
)
```

---

### Tracking Progress

```python
def update_progress(project_name, task, completed=True):
    """Update project progress"""
    progress_file = Path('projects') / project_name / 'progress.txt'

    # Load current progress
    with open(progress_file, 'r') as f:
        progress = json.load(f)

    # Add or update task
    task_entry = {
        "task": task,
        "completed": completed,
        "updated": datetime.now().isoformat()
    }

    # Find existing task
    existing = None
    for i, t in enumerate(progress['progress']):
        if t['task'] == task:
            existing = i
            break

    if existing is not None:
        progress['progress'][existing] = task_entry
    else:
        progress['progress'].append(task_entry)

    # Update completion percentage
    total_tasks = len(progress['progress'])
    completed_tasks = sum(1 for t in progress['progress'] if t['completed'])
    progress['completion_percentage'] = int((completed_tasks / total_tasks) * 100)

    # Update status
    if progress['completion_percentage'] == 100:
        progress['status'] = 'completed'
    elif progress['completion_percentage'] > 0:
        progress['status'] = 'in_progress'

    progress['updated'] = datetime.now().isoformat()

    # Save
    with open(progress_file, 'w') as f:
        json.dump(progress, f, indent=2)

    print(f"Progress updated: {progress['completion_percentage']}% complete")

# Usage
update_progress("Network Security Audit", "Scan network for vulnerabilities", completed=True)
update_progress("Network Security Audit", "Analyze findings", completed=False)
```

---

### Listing Projects

```python
def list_projects():
    """List all projects with status"""
    projects_dir = Path('projects')
    projects = []

    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue

        progress_file = project_dir / 'progress.txt'
        if not progress_file.exists():
            continue

        with open(progress_file, 'r') as f:
            progress = json.load(f)

        projects.append({
            'name': progress['project_name'],
            'status': progress['status'],
            'completion': progress['completion_percentage'],
            'updated': progress['updated']
        })

    # Sort by last updated
    projects.sort(key=lambda x: x['updated'], reverse=True)

    return projects

# Usage
for project in list_projects():
    print(f"{project['name']}: {project['completion']}% ({project['status']})")
```

---

## Project Structure

### Configuration File (`config.json`)

```json
{
  "project_name": "Network Security Audit",
  "focus_topic": "network_security_audit",
  "memory_context": "project:network_security_audit",
  "auto_save": true,
  "notifications": true,
  "tools": [
    "nmap",
    "vulnerability_scanner",
    "report_generator"
  ],
  "metadata": {
    "priority": "high",
    "deadline": "2025-02-15",
    "team": ["security_team"]
  }
}
```

---

### Notes File (`notes.md`)

```markdown
# Project Notes

## 2025-01-20
- Completed initial network scan
- Found 15 active hosts
- Identified 3 potential vulnerabilities

## 2025-01-19
- Set up scanning environment
- Configured tools
- Defined scope

## Ideas
- Implement automated periodic scanning
- Create dashboard for real-time monitoring
- Integrate with SIEM system

## Issues
- Port 22 exposed on multiple hosts
- Outdated SSL certificates detected
- Firewall rules need review

## Next Steps
1. Deep dive into identified vulnerabilities
2. Generate detailed report
3. Propose remediation plan
```

---

## Usage Examples

### Project-Aware Vera Session

```python
from vera import Vera
from pathlib import Path
import json

def start_project_session(project_name):
    """
    Start Vera session with project context

    Args:
        project_name: Name of project

    Returns:
        Vera instance with project context loaded
    """
    # Load project config
    project_dir = Path('projects') / project_name
    config_file = project_dir / 'config.json'

    with open(config_file, 'r') as f:
        config = json.load(f)

    # Initialize Vera
    vera = Vera()

    # Set project context in memory
    vera.mem.add_session_memory(
        vera.sess.id,
        f"Working on project: {project_name}",
        memory_type="context",
        metadata={
            "project": project_name,
            "focus": config['focus_topic']
        }
    )

    # Load project notes
    notes_file = project_dir / 'notes.md'
    if notes_file.exists():
        notes = notes_file.read_text()
        vera.mem.add_session_memory(
            vera.sess.id,
            notes,
            memory_type="project_notes",
            metadata={"project": project_name}
        )

    print(f"Project session started: {project_name}")
    return vera

# Usage
vera = start_project_session("Network Security Audit")
response = vera.run("What are the next steps for this project?")
```

---

### Automatic Progress Updates

```python
def auto_update_progress_from_focus_board(project_name):
    """
    Update project progress from focus board

    Args:
        project_name: Name of project
    """
    from pathlib import Path
    import json

    # Load latest focus board
    focus_boards_dir = Path('Configuration/focus_boards')
    project_focus = config['focus_topic']

    boards = sorted(
        focus_boards_dir.glob(f'{project_focus}_*.json'),
        reverse=True
    )

    if not boards:
        return

    with open(boards[0], 'r') as f:
        focus_board = json.load(f)

    # Extract completed items
    completed = focus_board['board'].get('completed', [])

    # Update progress
    for item in completed:
        update_progress(
            project_name,
            item['note'],
            completed=True
        )

    print(f"Progress updated from focus board: {len(completed)} items")

# Usage
auto_update_progress_from_focus_board("Network Security Audit")
```

---

### Project Report Generation

```python
def generate_project_report(project_name):
    """
    Generate comprehensive project report

    Args:
        project_name: Name of project

    Returns:
        Report content as string
    """
    project_dir = Path('projects') / project_name

    # Load progress
    with open(project_dir / 'progress.txt', 'r') as f:
        progress = json.load(f)

    # Load notes
    notes = ""
    if (project_dir / 'notes.md').exists():
        notes = (project_dir / 'notes.md').read_text()

    # Generate report
    report = f"""# Project Report: {project_name}

## Overview
- **Status:** {progress['status']}
- **Completion:** {progress['completion_percentage']}%
- **Created:** {progress['created']}
- **Last Updated:** {progress['updated']}

## Description
{progress.get('description', 'No description')}

## Goals
{chr(10).join(f'- {goal}' for goal in progress.get('goals', []))}

## Progress
{chr(10).join(
    f"- {'[x]' if t['completed'] else '[ ]'} {t['task']}"
    for t in progress['progress']
)}

## Notes
{notes}

## Statistics
- Total Tasks: {len(progress['progress'])}
- Completed: {sum(1 for t in progress['progress'] if t['completed'])}
- Remaining: {sum(1 for t in progress['progress'] if not t['completed'])}

---
*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""

    # Save report
    report_file = project_dir / 'files' / 'outputs' / 'report.md'
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(report)

    return report

# Usage
report = generate_project_report("Network Security Audit")
print(report)
```

---

## Best Practices

### 1. Project Naming

**Do:**
- Use descriptive names
- Use underscores or hyphens for spaces
- Keep names concise but meaningful

**Don't:**
- Use special characters
- Use extremely long names
- Use generic names like "project1"

---

### 2. Progress Tracking

**Do:**
- Update progress regularly
- Break tasks into manageable items
- Include completion timestamps
- Link to related focus boards

**Don't:**
- Create overly granular tasks
- Forget to update completion status
- Mix multiple projects in one tracking file

---

### 3. File Organization

**Do:**
- Use standard subdirectory structure
- Organize files by type
- Keep project files self-contained
- Regular backups

**Don't:**
- Mix project files with system files
- Store large binary files directly
- Duplicate files across projects

---

## Integration

### With Focus Boards

```python
# Link project to focus board
def link_focus_board(project_name, focus_topic):
    """Link project to focus board topic"""
    config_file = Path('projects') / project_name / 'config.json'

    with open(config_file, 'r') as f:
        config = json.load(f)

    config['focus_topic'] = focus_topic

    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)

# Usage
link_focus_board("Network Security Audit", "network_scanning")
```

### With Memory System

```python
# Store project context in memory
def save_project_to_memory(project_name, vera):
    """Save project information to memory"""
    project_dir = Path('projects') / project_name

    with open(project_dir / 'progress.txt', 'r') as f:
        progress = json.load(f)

    # Add to long-term memory
    vera.mem.add_memory(
        text=f"Project: {project_name}. {progress['description']}",
        memory_type="project",
        metadata={
            "project": project_name,
            "status": progress['status'],
            "completion": progress['completion_percentage']
        }
    )

# Usage
save_project_to_memory("Network Security Audit", vera)
```

---

## Related Documentation

- [Focus Boards](../Configuration/README.md#focus-boards)
- [Memory System](../Memory/README.md)
- [Project Management Guide](../docs/project_management.md)

---

**Last Updated:** January 2025
**Maintainer:** Vera-AI Development Team
**Version:** 1.0.0
