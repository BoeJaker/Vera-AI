# Agents Directory Documentation

## Overview

The `Agents/` directory contains specialized AI agent implementations that perform specific roles within the Vera architecture. Each agent is an LLM instance configured with augmented capabilities including memory management, tool integration, task triage, and autonomous goal setting.

**Total Lines of Code:** 1,529 LOC
**Number of Agents:** 5 implementations
**Status:** Production-ready (POC complete)

## Directory Structure

```
Agents/
├── executive_0_9.py      # Central Executive Agent (26KB)
├── planning.py           # Plan Generation Agent (17KB)
├── reviewer.py           # Quality Assurance Agent (2KB)
├── idea_generator.py     # Creative Idea Generation (449B)
└── executive_ui.py       # Executive UI Interface (14KB)
```

## Agent Hierarchy

```
┌───────────────────────────────────────┐
│      Strategic Agents (Deep LLM)      │
│  - Long-term planning                 │
│  - Complex reasoning                  │
│  - Proactive reflection               │
└───────────────────────────────────────┘
              ↓
┌───────────────────────────────────────┐
│   Tool Agents (Intermediate LLM)      │
│  - Tool invocation                    │
│  - Mid-complexity tasks               │
│  - Workflow coordination              │
└───────────────────────────────────────┘
              ↓
┌───────────────────────────────────────┐
│     Triage Agents (Fast LLM)          │
│  - Task prioritization                │
│  - Request routing                    │
│  - Quick validation                   │
└───────────────────────────────────────┘
```

---

## Agent Implementations

### 1. executive_0_9.py - Central Executive Agent

**File:** `Agents/executive_0_9.py`
**Size:** 26KB
**LLM Tier:** Deep/Reasoning
**Status:** Production

#### Purpose

The Central Executive Agent acts as the primary orchestrator for high-level decision-making, calendar management, and project coordination. It integrates with Google Calendar and maintains local calendar data in ICS format.

#### Key Features

- **Calendar Integration**
  - Google Calendar API integration
  - Local ICS file management
  - Event scheduling and deadline tracking
  - Recurring event handling

- **Project Management**
  - Project timeline coordination
  - Milestone tracking
  - Dependency analysis
  - Resource allocation oversight

- **Decision Making**
  - Strategic planning
  - Priority assessment
  - Goal decomposition
  - Long-term roadmap generation

#### Core Methods

```python
class ExecutiveAgent:
    def __init__(self, llm, memory, calendar_service):
        """Initialize executive agent with LLM, memory, and calendar access"""

    def process_calendar_event(self, event_data):
        """Process and schedule calendar events"""

    def generate_project_plan(self, project_description):
        """Generate comprehensive project execution plan"""

    def assess_priorities(self, task_list):
        """Evaluate and prioritize tasks based on strategic goals"""

    def track_deadlines(self):
        """Monitor upcoming deadlines and generate alerts"""

    def sync_google_calendar(self):
        """Synchronize with Google Calendar API"""

    def export_ics(self, calendar_data):
        """Export calendar to ICS format"""
```

#### Calendar Event Format

```python
event = {
    "summary": "Project Review Meeting",
    "start": {
        "dateTime": "2025-01-15T14:00:00",
        "timeZone": "UTC"
    },
    "end": {
        "dateTime": "2025-01-15T15:00:00",
        "timeZone": "UTC"
    },
    "description": "Review Q1 project progress",
    "attendees": ["user@example.com"],
    "reminders": {
        "useDefault": False,
        "overrides": [
            {"method": "popup", "minutes": 30}
        ]
    }
}
```

#### Google Calendar Integration

**Setup:**
1. Create Google Cloud Project
2. Enable Google Calendar API
3. Create OAuth 2.0 credentials
4. Download credentials.json
5. Place in Vera root directory

**Authentication Flow:**
```python
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# First-time authentication
flow = InstalledAppFlow.from_client_secrets_file(
    'credentials.json',
    scopes=['https://www.googleapis.com/auth/calendar']
)
creds = flow.run_local_server(port=0)

# Build service
service = build('calendar', 'v3', credentials=creds)
```

#### Local Calendar (ICS Format)

**Storage:** `Agents/calendars/*.ics`

**Example ICS:**
```ics
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Vera-AI//Executive Calendar//EN
BEGIN:VEVENT
UID:vera-event-20250115-140000@example.com
DTSTAMP:20250115T120000Z
DTSTART:20250115T140000Z
DTEND:20250115T150000Z
SUMMARY:Project Review Meeting
DESCRIPTION:Review Q1 project progress
STATUS:CONFIRMED
END:VEVENT
END:VCALENDAR
```

#### Project Integration

Integrates with `projects/` directory for project-specific planning:

```python
project_context = {
    "project_id": "proj_001",
    "name": "Network Security Analysis",
    "deadlines": [
        {"task": "Initial scan", "due": "2025-01-20"},
        {"task": "Vulnerability report", "due": "2025-01-25"}
    ],
    "milestones": [
        {"name": "Phase 1 Complete", "date": "2025-01-18"}
    ]
}
```

---

### 2. planning.py - Plan Generation Agent

**File:** `Agents/planning.py`
**Size:** 17KB
**LLM Tier:** Deep/Reasoning
**Status:** Production

#### Purpose

Specialized in breaking down complex goals into actionable, sequenced plans. Generates structured execution strategies with clear steps, dependencies, and success criteria.

#### Key Features

- **Goal Decomposition**
  - Break high-level goals into sub-tasks
  - Identify task dependencies
  - Sequence tasks for optimal execution
  - Estimate time and resources

- **Plan Generation**
  - Multi-level plan hierarchies
  - Parallel vs. sequential task identification
  - Contingency planning
  - Alternative approach generation

- **Plan Refinement**
  - Iterative plan improvement
  - Constraint validation
  - Resource feasibility checking
  - Risk assessment

#### Core Methods

```python
class PlanningAgent:
    def __init__(self, llm, memory):
        """Initialize planning agent"""

    def decompose_goal(self, goal_description):
        """Break goal into manageable sub-tasks"""

    def generate_plan(self, task_list, constraints):
        """Create structured execution plan"""

    def refine_plan(self, initial_plan, feedback):
        """Improve plan based on validation feedback"""

    def identify_dependencies(self, tasks):
        """Map task dependencies"""

    def sequence_tasks(self, tasks, dependencies):
        """Determine optimal task ordering"""

    def estimate_resources(self, plan):
        """Estimate time and resources required"""
```

#### Plan Structure

```python
plan = {
    "goal": "Implement user authentication system",
    "strategy": "sequential",  # or "parallel" or "hybrid"
    "tasks": [
        {
            "id": "task_1",
            "description": "Design authentication schema",
            "dependencies": [],
            "estimated_time": "2 hours",
            "resources": ["Deep LLM", "Database access"],
            "success_criteria": "Schema approved and documented"
        },
        {
            "id": "task_2",
            "description": "Implement password hashing",
            "dependencies": ["task_1"],
            "estimated_time": "3 hours",
            "resources": ["Code Executor", "Security libraries"],
            "success_criteria": "Tests pass with bcrypt hashing"
        },
        {
            "id": "task_3",
            "description": "Create login API endpoint",
            "dependencies": ["task_1", "task_2"],
            "estimated_time": "4 hours",
            "resources": ["FastAPI", "Testing tools"],
            "success_criteria": "API returns JWT on valid credentials"
        }
    ],
    "total_estimated_time": "9 hours",
    "parallelizable": ["task_4", "task_5"],  # If applicable
    "risks": [
        "Password complexity requirements may change",
        "Third-party auth integration not yet scoped"
    ],
    "alternatives": [
        "Use OAuth2 instead of custom auth",
        "Leverage existing auth library"
    ]
}
```

#### Integration with Tool Chain Engine

The Planning Agent works closely with the ToolChain Engine:

```python
# Planning Agent generates plan
plan = planning_agent.generate_plan(
    "Build web scraper for product prices"
)

# ToolChain Engine executes plan
result = toolchain.execute_tool_chain_from_plan(plan)
```

#### Planning Strategies

**Sequential Planning**
- Tasks executed one after another
- Clear dependencies
- Safer for complex workflows

**Parallel Planning**
- Independent tasks run concurrently
- Faster execution
- Requires sufficient resources

**Hybrid Planning**
- Mix of sequential and parallel
- Optimizes for speed and safety
- Most commonly used

---

### 3. reviewer.py - Quality Assurance Agent

**File:** `Agents/reviewer.py`
**Size:** 2KB
**LLM Tier:** Intermediate
**Status:** Production

#### Purpose

Validates outputs, checks quality, and ensures goals are met. Acts as a quality gate before results are returned to users or promoted to memory.

#### Key Features

- **Output Validation**
  - Check against success criteria
  - Verify completeness
  - Assess quality metrics
  - Flag issues

- **Goal Verification**
  - Compare output to original goal
  - Determine if requirements met
  - Suggest improvements if needed

- **Quality Metrics**
  - Accuracy assessment
  - Completeness check
  - Coherence evaluation
  - Usability analysis

#### Core Methods

```python
class ReviewerAgent:
    def __init__(self, llm, memory):
        """Initialize reviewer agent"""

    def validate_output(self, output, success_criteria):
        """Check if output meets criteria"""

    def verify_goal_met(self, output, original_goal):
        """Determine if goal was achieved"""

    def assess_quality(self, output):
        """Evaluate output quality"""

    def suggest_improvements(self, output, issues):
        """Provide improvement recommendations"""

    def approve_for_memory(self, output):
        """Determine if output should be promoted to long-term memory"""
```

#### Review Process

```python
review_result = {
    "approved": True,
    "confidence": 0.92,
    "quality_score": 0.88,
    "issues": [
        {"severity": "low", "description": "Minor formatting inconsistency"}
    ],
    "improvements": [
        "Add more detailed examples",
        "Include error handling documentation"
    ],
    "goal_met": True,
    "promote_to_memory": True
}
```

#### Integration Points

- **ToolChain Engine**: Validates tool chain outputs
- **Planning Agent**: Reviews plan quality before execution
- **Memory System**: Gates promotion to long-term storage
- **Chat API**: Ensures response quality before returning to user

---

### 4. idea_generator.py - Creative Idea Generation

**File:** `Agents/idea_generator.py`
**Size:** 449B
**LLM Tier:** Deep
**Status:** Production (lightweight)

#### Purpose

Generates creative ideas, hypotheses, and alternative approaches. Used during brainstorming, problem-solving, and exploration phases.

#### Key Features

- **Creative Generation**
  - Novel idea generation
  - Alternative approach suggestions
  - Hypothesis formation
  - Lateral thinking prompts

- **Context-Aware Creativity**
  - Leverages memory for relevant ideas
  - Considers project constraints
  - Builds on existing concepts

#### Core Methods

```python
class IdeaGeneratorAgent:
    def __init__(self, llm, memory):
        """Initialize idea generator"""

    def generate_ideas(self, context, num_ideas=5):
        """Generate creative ideas for given context"""

    def suggest_alternatives(self, current_approach):
        """Propose alternative approaches"""

    def form_hypotheses(self, problem_description):
        """Generate testable hypotheses"""
```

#### Output Format

```python
ideas = {
    "context": "Improving vector search performance",
    "ideas": [
        {
            "title": "Hierarchical vector indexing",
            "description": "Create multi-level index for faster coarse-to-fine search",
            "feasibility": "high",
            "impact": "medium"
        },
        {
            "title": "Approximate nearest neighbor with HNSW",
            "description": "Replace exact search with HNSW algorithm",
            "feasibility": "medium",
            "impact": "high"
        },
        {
            "title": "Semantic caching layer",
            "description": "Cache frequently queried embeddings",
            "feasibility": "high",
            "impact": "low"
        }
    ]
}
```

---

### 5. executive_ui.py - Executive UI Interface

**File:** `Agents/executive_ui.py`
**Size:** 14KB
**LLM Tier:** N/A (UI component)
**Status:** Production

#### Purpose

Provides web interface for interacting with the Executive Agent, viewing calendar, managing projects, and monitoring strategic planning.

#### Key Features

- **Calendar View**
  - Monthly/weekly/daily calendar display
  - Event creation and editing
  - Deadline visualization
  - Google Calendar sync interface

- **Project Dashboard**
  - Active project list
  - Milestone tracking
  - Progress visualization
  - Resource allocation view

- **Strategic Planning Interface**
  - Goal management
  - Priority matrix
  - Long-term roadmap
  - Decision logs

#### UI Components

```python
# FastAPI routes
@app.get("/executive/calendar")
async def get_calendar(start_date: str, end_date: str):
    """Get calendar events for date range"""

@app.post("/executive/event")
async def create_event(event: CalendarEvent):
    """Create new calendar event"""

@app.get("/executive/projects")
async def list_projects():
    """Get all active projects"""

@app.post("/executive/plan")
async def generate_plan(goal: str):
    """Generate strategic plan for goal"""
```

#### Frontend Integration

Located in `ChatUI/js/executive.js`

**Calendar Display:**
```javascript
function displayCalendar(events) {
    // Render calendar with events
    // Color-code by priority
    // Enable drag-and-drop rescheduling
}
```

**Project Tracking:**
```javascript
function updateProjectStatus(project_id, status) {
    // Update project state
    // Notify Executive Agent
    // Refresh dashboard
}
```

---

## Agent Communication

### Shared Memory Interface

All agents access the same memory system for context:

```python
# Read from memory
context = agent.memory.retrieve_context(
    query="authentication implementation",
    max_results=10
)

# Write to memory
agent.memory.save_interaction(
    user_message="Implement auth system",
    agent_response=plan,
    metadata={"agent": "planning", "session_id": "sess_001"}
)
```

### Inter-Agent Messaging

Agents can communicate via the message bus:

```python
# Planning Agent requests Executive review
planning_agent.send_message(
    to="executive",
    subject="plan_review",
    content=generated_plan
)

# Executive Agent responds
executive_agent.send_message(
    to="planning",
    subject="plan_approved",
    content={"approved": True, "comments": "..."}
)
```

### Orchestrator Coordination

The CEO coordinates agent activities:

```python
# CEO delegates to Planning Agent
result = ceo.delegate_task(
    agent="planning",
    task="generate_plan",
    input="Build recommendation system"
)

# CEO monitors progress
status = ceo.get_agent_status("planning")
```

---

## Usage Examples

### Executive Agent - Calendar Management

```python
from Ollama.Agents.Scheduling.executive_0_9 import ExecutiveAgent

# Initialize
executive = ExecutiveAgent(
    llm=vera.deep_llm,
    memory=vera.memory,
    calendar_service=google_calendar_service
)

# Schedule meeting
executive.process_calendar_event({
    "summary": "Weekly Standup",
    "start": "2025-01-20T10:00:00",
    "end": "2025-01-20T10:30:00",
    "recurrence": "RRULE:FREQ=WEEKLY;BYDAY=MO"
})

# Check upcoming deadlines
deadlines = executive.track_deadlines()
for deadline in deadlines:
    print(f"{deadline['task']} due in {deadline['days_remaining']} days")
```

### Planning Agent - Goal Decomposition

```python
from Agents.planning import PlanningAgent

# Initialize
planner = PlanningAgent(
    llm=vera.deep_llm,
    memory=vera.memory
)

# Generate plan
plan = planner.generate_plan(
    "Create automated testing framework",
    constraints={"max_time": "2 weeks", "team_size": 1}
)

print(f"Plan has {len(plan['tasks'])} tasks")
print(f"Estimated completion: {plan['total_estimated_time']}")
```

### Reviewer Agent - Quality Check

```python
from Ollama.Agents.experimental.Reviewer.reviewer import ReviewerAgent

# Initialize
reviewer = ReviewerAgent(
    llm=vera.intermediate_llm,
    memory=vera.memory
)

# Review output
review = reviewer.validate_output(
    output=generated_code,
    success_criteria="Code must have tests and handle errors"
)

if review['approved']:
    print("Output approved!")
    if review['promote_to_memory']:
        vera.memory.promote_to_long_term(generated_code)
else:
    print("Issues found:", review['issues'])
```

---

## Configuration

### Agent LLM Assignment

Configure which LLM each agent uses in `Configuration/vera_models.json`:

```json
{
  "agents": {
    "executive": "deep_llm",
    "planning": "deep_llm",
    "reviewer": "intermediate_llm",
    "idea_generator": "deep_llm",
    "triage": "fast_llm"
  }
}
```

### Agent-Specific Settings

```python
AGENT_CONFIG = {
    "executive": {
        "calendar_sync_interval": 300,  # seconds
        "default_event_duration": 30,   # minutes
        "reminder_lead_time": 1440      # minutes (24 hours)
    },
    "planning": {
        "max_task_depth": 5,
        "default_strategy": "hybrid",
        "enable_alternatives": True
    },
    "reviewer": {
        "min_quality_score": 0.7,
        "auto_approve_threshold": 0.9,
        "require_human_review": False
    }
}
```

---

## Extension Guide

### Creating a Custom Agent

```python
from Agents.base import BaseAgent

class CustomAgent(BaseAgent):
    """Your specialized agent"""

    def __init__(self, name, llm, memory, **kwargs):
        super().__init__(name, llm, memory)
        self.expertise = kwargs.get('expertise', 'general')

    def process_query(self, query):
        """Main processing logic"""
        # Access memory
        context = self.memory.retrieve_context(query)

        # Call LLM
        response = self.llm.invoke(
            f"As a {self.expertise} expert: {query}\nContext: {context}"
        )

        # Save to memory
        self.save_to_memory(query, response)

        return response

    def specialized_method(self, input_data):
        """Agent-specific functionality"""
        # Implement your logic
        pass

# Register with Vera
vera.register_agent(
    CustomAgent(
        name="domain_expert",
        llm=vera.deep_llm,
        memory=vera.memory,
        expertise="cybersecurity"
    )
)
```

---

## Testing

### Agent Unit Tests

```python
# tests/test_agents.py
import pytest
from Ollama.Agents.experimental.Planning.planning import PlanningAgent

def test_plan_generation():
    agent = PlanningAgent(mock_llm, mock_memory)
    plan = agent.generate_plan("Test goal")

    assert len(plan['tasks']) > 0
    assert 'total_estimated_time' in plan
    assert all('dependencies' in task for task in plan['tasks'])

def test_dependency_detection():
    agent = PlanningAgent(mock_llm, mock_memory)
    tasks = [
        {"id": "1", "description": "Task 1"},
        {"id": "2", "description": "Task 2, requires task 1"}
    ]

    deps = agent.identify_dependencies(tasks)
    assert "1" in deps["2"]
```

---

## Performance Considerations

### LLM Selection

- **Executive & Planning**: Use Deep LLM for strategic reasoning
- **Reviewer**: Intermediate LLM sufficient for validation
- **Idea Generator**: Deep LLM for creative thinking
- **Triage** (not in this dir): Fast LLM for quick routing

### Memory Access Patterns

- Cache frequently accessed context
- Use targeted queries instead of broad scans
- Implement pagination for large result sets

### Concurrent Agent Execution

```python
import asyncio

async def run_agents_concurrently():
    results = await asyncio.gather(
        planning_agent.async_generate_plan(goal_1),
        reviewer_agent.async_validate_output(output_1),
        idea_generator.async_generate_ideas(context_1)
    )
    return results
```

---

## Troubleshooting

### Common Issues

**Agent Not Responding**
- Check LLM connection (Ollama running?)
- Verify memory system accessible
- Review agent logs for errors

**Poor Quality Plans**
- Increase LLM model size
- Provide more context in prompts
- Adjust planning strategy

**Calendar Sync Failures**
- Verify Google Calendar API credentials
- Check OAuth token expiration
- Ensure network connectivity

---

**Last Updated:** January 2025
**Maintainer:** Vera-AI Development Team
**Version:** 1.0.0
