# Agents

## Overview

Agents are **specialized LLM instances with augmented capabilities**, including memory management, tool integration, task triage, and autonomous reasoning. They form the cognitive units of Vera, each designed to handle specific aspects of the system while coordinating through shared memory structures.

## Purpose

Agents enable Vera to:
- **Distribute cognitive work** across specialized units
- **Operate autonomously** on complex, multi-step tasks
- **Maintain context** through persistent memory
- **Coordinate activities** via shared knowledge graph
- **Scale reasoning** by running multiple agents in parallel

## Architecture Role

```
User Input → Triage Agent → Task Classification
                ↓
        Planning Agent → Goal Decomposition
                ↓
        Scheduler Agent → Task Orchestration
                ↓
        Execution Agents → Tool Invocation
                ↓
        Reviewer Agent → Validation & Quality Check
```

Agents exist at multiple levels:
- **Triage Agents** - Lightweight, prioritize tasks and delegate work
- **Tool Agents** - Fast LLMs for immediate, simple tool invocations
- **Strategic Agents** - Deep LLMs for long-term planning and complex reasoning
- **Specialized Agents** - Domain-specific expertise (code, security, scheduling)

## Key Agent Types

### Executive Agent
**Files:** `executive_0_9.py`, `executive_ui.py`

The orchestrator agent responsible for:
- High-level strategic planning
- Resource allocation across other agents
- Long-term goal tracking
- Calendar and schedule management
- Project coordination

**Technologies:**
- Google Calendar API integration
- APScheduler for task scheduling
- AsyncIO for concurrent operations
- LangChain for LLM integration

**Usage:**
```python
from Agents.executive_0_9 import ExecutiveAgent

executive = ExecutiveAgent(
    llm=vera.deep_llm,
    memory=vera.memory,
    calendar_credentials="path/to/credentials.json"
)

# Delegate high-level task
executive.plan_project("Build authentication system")
```

### Planning Agent
**File:** `planning.py`

Specialized in task decomposition and workflow design:
- Breaks complex goals into actionable steps
- Identifies dependencies and prerequisites
- Generates execution roadmaps
- Optimizes task ordering

### Reviewer Agent
**File:** `reviewer.py`

Validates outputs and ensures quality:
- Code review and quality checks
- Output validation against goals
- Error detection and suggestion
- Compliance verification

### Idea Generator Agent
**File:** `idea_generator.py`

Creative brainstorming and hypothesis generation:
- Generates novel approaches to problems
- Suggests alternative solutions
- Explores possibility space
- Synthesizes insights from memory

## Agent Hierarchy

### Fast Agents
- **Model:** Mistral 7B, Gemma2 2B
- **Memory:** 4-8GB
- **Use Case:** Quick responses, simple tool invocations, triage

### Intermediate Agents
- **Model:** Gemma2 9B, Llama 8B
- **Memory:** 8-16GB
- **Use Case:** Tool execution, moderate reasoning

### Deep Agents
- **Model:** Gemma3 27B, GPT-OSS 20B
- **Memory:** 16-32GB
- **Use Case:** Complex reasoning, strategic planning, code generation

### Specialized Agents
- **Model:** Domain-specific fine-tuned models
- **Memory:** Varies
- **Use Case:** Code generation, mathematical reasoning, security analysis

## Agent Capabilities

### Memory Management
Every agent has access to:
- **Micro Buffer** - Immediate working context
- **Macro Buffer** - Cross-sessional associative memory
- **Meta Buffer** - Self-modeling and strategic reasoning
- **Knowledge Graph** - Persistent relational memory

### Tool Integration
Agents can invoke:
- Internal tools (memory introspection, file operations)
- External APIs (web search, weather, calendar)
- Command-line tools (bash, python scripts)
- MCP servers (Model Context Protocol integrations)

### Autonomous Operation
Agents can:
- Set and track long-term goals
- Generate sub-tasks autonomously
- Request resources from the CEO
- Coordinate with other agents
- Learn from past executions

## Creating Custom Agents

### Basic Agent Template
```python
from Agents.base import Agent

class CustomAgent(Agent):
    """An agent specialized for your domain"""

    def __init__(self, name, llm, memory):
        super().__init__(name, llm, memory)
        self.expertise = "domain-specific-knowledge"
        self.tools = self.load_specialized_tools()

    def process_query(self, query):
        # Custom reasoning logic
        context = self.fetch_relevant_memory(query)
        response = self.llm.invoke(
            f"As a {self.expertise} expert with context: {context}\n\nQuery: {query}"
        )
        self.save_to_memory(query, response)
        return response

    def load_specialized_tools(self):
        return [
            Tool(name="SpecializedTool", func=self.custom_tool, description="...")
        ]

# Register with Vera
vera.register_agent(CustomAgent("domain-expert", vera.deep_llm, vera.memory))
```

### Advanced Agent with Proactive Behavior
```python
class ProactiveAgent(Agent):
    def __init__(self, name, llm, memory):
        super().__init__(name, llm, memory)
        self.goals = []
        self.scheduler = APScheduler()

    def set_goal(self, goal_description, deadline=None):
        goal = {
            "description": goal_description,
            "deadline": deadline,
            "status": "pending",
            "sub_tasks": self.decompose_goal(goal_description)
        }
        self.goals.append(goal)
        self.schedule_proactive_checks()

    def proactive_check(self):
        """Runs periodically to check goal progress"""
        for goal in self.goals:
            if self.is_deadline_approaching(goal):
                self.generate_reminder(goal)
            if self.detect_blocker(goal):
                self.suggest_alternatives(goal)
```

## Agent Communication

Agents communicate through:

### Shared Memory
```python
# Agent A stores insight
agent_a.memory.store_insight(
    content="User prefers detailed explanations",
    tags=["user_preference", "interaction_style"]
)

# Agent B retrieves it later
preferences = agent_b.memory.query_insights(tags=["user_preference"])
```

### Message Passing
```python
# Direct agent-to-agent communication
agent_a.send_message(agent_b, {
    "type": "task_delegation",
    "task": "Analyze security vulnerabilities",
    "priority": "high"
})
```

### Focus Board
```python
# Shared focus board for coordination
focus_board.add_task({
    "agent": "planning-agent",
    "task": "Design authentication system",
    "dependencies": ["security-review"],
    "status": "in_progress"
})
```

## Agent Lifecycle

1. **Initialization** - Agent created with LLM, memory, and tools
2. **Context Loading** - Retrieves relevant memory and active goals
3. **Task Reception** - Receives task from CEO or user
4. **Processing** - Executes reasoning and tool invocations
5. **Memory Update** - Stores results and learnings
6. **Completion** - Reports results and updates focus board

## Configuration

Agent behavior configured via:
- `Configuration/vera_models.json` - Model selection per agent type
- Environment variables - API keys, resource limits
- Agent-specific config files

## Technologies Used

- **Python** - Core implementation
- **LangChain** - LLM framework integration
- **ChromaDB** - Agent memory (vector store)
- **Neo4j** - Shared knowledge graph
- **APScheduler** - Proactive task scheduling
- **AsyncIO** - Concurrent operation

## Related Documentation

- [Agent Framework Overview](../Vera%20Assistant%20Docs/Agents/Agent.md)
- [Builder Agent](../Vera%20Assistant%20Docs/Agents/Agent%20-%20Builder.md)
- [Reviewer Agent](../Vera%20Assistant%20Docs/Agents/Agent%20-%20Reviewer.md)
- [Optimizer Agent](../Vera%20Assistant%20Docs/Agents/Agent%20-%20Optimiser.md)
- [Memory System](../Memory/)
- [Toolchain Engine](../Toolchain/)

## Best Practices

### Resource Management
- Use fast LLMs for simple tasks to conserve resources
- Batch similar operations when possible
- Release memory after long-running tasks

### Error Handling
- Always implement graceful degradation
- Log failures with context for learning
- Escalate to CEO when stuck

### Memory Hygiene
- Tag memories appropriately for retrieval
- Archive completed task context
- Prune irrelevant short-term memories

## Contributing

To add a new agent:
1. Create agent file in `Agents/` directory
2. Inherit from `Agent` base class
3. Implement required methods (`process_query`, `load_tools`)
4. Add documentation in `Vera Assistant Docs/Agents/`
5. Register with CEO orchestrator
6. Add unit tests

---

**Related Components:**
- [Toolchain](../Toolchain/) - Tool execution engine
- [Memory](../Memory/) - Persistent knowledge storage
- [Background Cognition](../BackgroundCognition/) - Autonomous task generation
- [CEO Orchestrator](../Vera%20Assistant%20Docs/Central%20Executive%20Orchestrator.md)
