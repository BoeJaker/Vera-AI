# Projects

## Overview

The **Projects** directory provides structured project management and context persistence, allowing users to define long-term goals, track progress across sessions, and maintain organized workspaces for complex multi-step endeavors.

## Purpose

Projects enable:
- **Long-term goal tracking** - Define and monitor goals spanning weeks or months
- **Multi-session context** - Maintain continuity across conversations
- **Progress monitoring** - Track completion status and milestones
- **Dependency management** - Understand task relationships
- **Resource allocation** - Plan and track resource usage
- **Knowledge organization** - Group related memories and documents

## Architecture Role

```
User Defines Project → Stored in Memory Graph
         ↓
   Agents Reference Project Context
         ↓
   Background Cognition Monitors Progress
         ↓
   Proactive Reminders & Suggestions
         ↓
   Project Completion & Archival
```

Projects provide high-level organizational structure that spans Vera's memory, agent activities, and autonomous cognition systems.

## Directory Structure

```
projects/
├── README.md                 # This file
├── test/                     # Example test project
│   └── progress.json        # Progress tracking
└── (user-created projects)
```

## Project Configuration

Projects are defined using JSON configuration files that specify:
- Project metadata (name, description, owner)
- Goals and objectives
- Milestones and deadlines
- Related entities (documents, code, people)
- Status tracking
- Resource requirements

### Example Project Configuration

**`projects/authentication_system/project.json`:**
```json
{
  "project_id": "auth_system_2024",
  "name": "Authentication System Implementation",
  "description": "Implement OAuth2 authentication with JWT tokens",
  "owner": "User",
  "status": "in_progress",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-15T14:30:00Z",
  "deadline": "2024-02-01T00:00:00Z",

  "goals": [
    {
      "id": "goal_1",
      "description": "Implement OAuth2 authorization server",
      "status": "completed",
      "completion": 1.0
    },
    {
      "id": "goal_2",
      "description": "Add JWT token generation and validation",
      "status": "in_progress",
      "completion": 0.65
    },
    {
      "id": "goal_3",
      "description": "Write comprehensive tests",
      "status": "pending",
      "completion": 0.0
    }
  ],

  "milestones": [
    {
      "name": "MVP Complete",
      "date": "2024-01-20T00:00:00Z",
      "status": "pending",
      "criteria": ["goal_1", "goal_2"]
    },
    {
      "name": "Production Ready",
      "date": "2024-02-01T00:00:00Z",
      "status": "pending",
      "criteria": ["goal_1", "goal_2", "goal_3"]
    }
  ],

  "dependencies": {
    "external": ["OAuth2 library", "JWT library"],
    "internal": ["User database schema", "API framework"]
  },

  "resources": {
    "documentation": [
      "https://oauth.net/2/",
      "https://jwt.io/"
    ],
    "code_repositories": [
      "projects/authentication_system/src"
    ],
    "related_sessions": [
      "session_abc123",
      "session_def456"
    ]
  },

  "tags": ["security", "backend", "api"],
  "priority": "high"
}
```

## Usage

### Creating a Project

**Via Vera Chat:**
```
User: "Create a new project for implementing user authentication"

Vera: "I'll create a project for user authentication. What are the main goals?"

User: "Implement OAuth2, add JWT tokens, and write tests"

Vera: "Project created: 'User Authentication System'
      Goals:
      1. Implement OAuth2 authorization
      2. Add JWT token generation
      3. Write comprehensive tests

      I'll track progress and provide proactive updates."
```

**Programmatically:**
```python
from vera import Vera

vera = Vera()

project = vera.create_project(
    name="User Authentication System",
    description="Implement OAuth2 with JWT tokens",
    goals=[
        "Implement OAuth2 authorization server",
        "Add JWT token generation and validation",
        "Write comprehensive tests"
    ],
    deadline="2024-02-01",
    priority="high"
)

print(f"Project created: {project['project_id']}")
```

### Tracking Progress

```python
# Update goal progress
vera.update_goal_progress(
    project_id="auth_system_2024",
    goal_id="goal_2",
    completion=0.75,
    notes="Implemented JWT generation, working on validation"
)

# Check project status
status = vera.get_project_status("auth_system_2024")
print(f"Overall completion: {status['completion_percentage']}%")
print(f"Days until deadline: {status['days_remaining']}")
```

### Querying Projects

```python
# List all active projects
active_projects = vera.list_projects(status="in_progress")

# Get projects by tag
security_projects = vera.list_projects(tags=["security"])

# Find projects approaching deadline
urgent_projects = vera.list_projects(days_until_deadline__lte=7)
```

## Integration with Memory System

Projects are deeply integrated with Vera's knowledge graph:

### Graph Relationships
```cypher
// Project stored as node in Neo4j
CREATE (p:Project {
    id: "auth_system_2024",
    name: "User Authentication System",
    status: "in_progress"
})

// Link to related entities
MATCH (p:Project {id: "auth_system_2024"})
MATCH (doc:Document {title: "OAuth2 Specification"})
CREATE (p)-[:REFERENCES]->(doc)

MATCH (p:Project {id: "auth_system_2024"})
MATCH (session:Session {id: "session_abc123"})
CREATE (p)-[:INCLUDES_SESSION]->(session)

// Link to code repositories
MATCH (p:Project {id: "auth_system_2024"})
MATCH (code:CodeRepository {path: "/auth_system/src"})
CREATE (p)-[:CONTAINS_CODE]->(code)
```

### Memory Tagging
All memories created during project work are automatically tagged:
```python
# When working on a project, memories are tagged
vera.set_active_project("auth_system_2024")

# User asks question
user_query = "How do I implement JWT token expiration?"

# Response is stored with project context
memory = vera.store_memory(
    content=response,
    tags=["auth_system_2024", "jwt", "security"],
    related_to=["Project:auth_system_2024"]
)
```

## Proactive Background Cognition Integration

Projects are actively monitored by PBC (Proactive Background Cognition):

### Deadline Monitoring
```python
# PBC checks project deadlines during idle time
thought = "Project 'auth_system_2024' deadline in 3 days - check progress"

actions = [
    "Review goal completion status",
    "Identify blockers",
    "Generate priority task list",
    "Send reminder notification"
]

pbc.execute_thought(thought, actions)
```

### Progress Tracking
```python
# PBC analyzes progress and suggests next steps
thought = "Goal 2 of 'auth_system_2024' at 65% - suggest next actions"

actions = [
    "Review last implementation session",
    "Identify remaining tasks for JWT validation",
    "Check for available code examples",
    "Update focus board with next steps"
]
```

### Blocker Detection
```python
# PBC detects stalled progress
thought = "No progress on 'auth_system_2024' for 5 days - investigate"

actions = [
    "Check for related questions or errors",
    "Identify knowledge gaps",
    "Suggest research or learning tasks",
    "Generate recovery plan"
]
```

## Focus Board Integration

Projects automatically appear on the focus board:

```json
{
  "active_projects": [
    {
      "project": "auth_system_2024",
      "status": "in_progress",
      "completion": 0.55,
      "next_steps": [
        "Complete JWT validation",
        "Write unit tests for token generation",
        "Review security best practices"
      ],
      "blockers": [],
      "deadline": "2024-02-01T00:00:00Z",
      "urgency": "medium"
    }
  ]
}
```

## Project Templates

Create reusable project templates:

**`projects/templates/security_implementation.json`:**
```json
{
  "template_name": "Security Feature Implementation",
  "description": "Template for implementing security features",
  "default_goals": [
    "Research security best practices",
    "Design implementation approach",
    "Implement core functionality",
    "Add comprehensive tests",
    "Security audit and review"
  ],
  "default_milestones": [
    {"name": "Research Complete", "offset_days": 7},
    {"name": "Implementation Complete", "offset_days": 21},
    {"name": "Security Audit Complete", "offset_days": 30}
  ],
  "recommended_resources": [
    "https://owasp.org/",
    "https://cheatsheetseries.owasp.org/"
  ],
  "tags": ["security", "implementation"]
}
```

**Usage:**
```python
# Create project from template
project = vera.create_project_from_template(
    template="security_implementation",
    name="Two-Factor Authentication",
    deadline="2024-03-01"
)
```

## Progress Tracking File

**`projects/auth_system/progress.json`:**
```json
{
  "last_updated": "2024-01-15T14:30:00Z",
  "completion_history": [
    {"date": "2024-01-05", "completion": 0.20},
    {"date": "2024-01-10", "completion": 0.40},
    {"date": "2024-01-15", "completion": 0.55}
  ],
  "work_sessions": [
    {
      "session_id": "session_abc123",
      "date": "2024-01-15",
      "duration_minutes": 120,
      "goals_worked_on": ["goal_2"],
      "progress_made": "Implemented JWT generation logic"
    }
  ],
  "notes": [
    {
      "date": "2024-01-15",
      "content": "Need to review JWT expiration best practices",
      "priority": "medium"
    }
  ]
}
```

## Project Reports

Generate project status reports:

```python
# Generate comprehensive report
report = vera.generate_project_report("auth_system_2024")

print(report)
```

**Output:**
```
Project Report: User Authentication System
==========================================

Status: In Progress (55% complete)
Deadline: 2024-02-01 (16 days remaining)
Priority: High

Goals:
✓ Implement OAuth2 authorization server (100%)
→ Add JWT token generation and validation (65%)
  ▸ Remaining: Implement token expiration handling
  ▸ Remaining: Add refresh token logic
  ▸ Remaining: Write validation unit tests
☐ Write comprehensive tests (0%)

Milestones:
☐ MVP Complete (2024-01-20) - 5 days remaining
  Dependencies: goal_1 ✓, goal_2 (in progress)
☐ Production Ready (2024-02-01) - 16 days remaining
  Dependencies: goal_1 ✓, goal_2, goal_3

Recent Activity:
• 2024-01-15: Implemented JWT generation logic (2h)
• 2024-01-14: Researched JWT libraries (1h)
• 2024-01-12: Completed OAuth2 server (3h)

Recommended Next Steps:
1. Complete JWT validation (estimated 4h)
2. Implement token expiration (estimated 2h)
3. Begin writing unit tests (estimated 6h)

Blockers: None identified
```

## Best Practices

### Project Organization
- Use clear, descriptive project names
- Break large goals into smaller, measurable sub-goals
- Set realistic deadlines with buffer time
- Tag projects consistently for easy filtering

### Progress Tracking
- Update progress regularly (at least weekly)
- Document blockers immediately when encountered
- Link relevant sessions and documents
- Use focus board for daily task planning

### Knowledge Management
- Store all project-related research in linked documents
- Tag memories with project ID
- Maintain updated resource lists
- Archive completed projects for future reference

### Proactive Monitoring
- Set milestone reminders
- Enable PBC deadline monitoring
- Review progress weekly
- Adjust goals based on actual progress

## Command-Line Interface

```bash
# List projects
python3 -c "from vera import Vera; Vera().list_projects()"

# Create project
python3 -c "
from vera import Vera
Vera().create_project(
    name='New Feature',
    goals=['Design', 'Implement', 'Test']
)
"

# Update progress
python3 -c "
from vera import Vera
Vera().update_goal_progress(
    project_id='auth_system_2024',
    goal_id='goal_2',
    completion=0.80
)
"

# Generate report
python3 -c "
from vera import Vera
print(Vera().generate_project_report('auth_system_2024'))
"
```

## Related Documentation

- [Memory System](../Memory/) - Project storage in knowledge graph
- [Background Cognition](../BackgroundCognition/) - Proactive project monitoring
- [Focus Board](../BackgroundCognition/tasks.py) - Daily task management

## Contributing

To extend project management:
1. Add new project templates
2. Implement milestone auto-adjustment
3. Add Gantt chart visualization
4. Create project collaboration features
5. Add time tracking integration

---

**Related Components:**
- [Memory](../Memory/) - Persistent project storage
- [Background Cognition](../BackgroundCognition/) - Proactive monitoring
- [Agents](../Agents/) - Project-aware reasoning
