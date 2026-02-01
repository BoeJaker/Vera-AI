# Modular Proactive Focus Manager

## Overview

This is a complete refactor of the ProactiveFocusManager into a modular, intelligent system that:

1. **Intelligently selects stages** based on focus board state (not just running all stages every time)
2. **Queries its own memory** (both session and project-wide) to enrich context
3. **Manages completion tracking** - moves completed actions to progress/completed
4. **Generates readable documentation** in curated prose style
5. **Remains a drop-in replacement** for the original implementation

## Architecture

### Component Breakdown

```
ProactiveFocusManager (Main Coordinator)
├── IterationManager          # Intelligent stage selection and orchestration
├── StageExecutor              # Executes individual stages (ideas, actions, etc.)
├── FocusBoardManager          # Board state and persistence
├── ContextManager             # Memory queries and context enrichment
├── DocumentationWriter        # Generates prose documentation
└── StreamingHandler           # UI output and progress tracking
```

### Key Components

#### 1. **IterationManager**
- Analyzes board state to determine what's needed
- Dynamically selects which stages to run
- Prioritizes stages (critical → high → medium → low)
- Gathers context from memory before each iteration
- Manages post-iteration cleanup

**Intelligent Decisions:**
- If 5+ high-priority actions exist → Execute them first
- If lots of ideas but no next steps → Generate next steps
- If next steps exist but no actions → Generate actions
- If issues are piling up → Address issues stage
- Generate ideas periodically (every 3 iterations) or when board is thin

#### 2. **StageExecutor**
- Runs individual stages (ideas, next_steps, actions, execution)
- Creates stage nodes in graph with full tracking
- Extracts resources (URLs, filepaths) and links them
- Uses agent's toolchain for action execution
- Handles LLM streaming with thought stripping

#### 3. **FocusBoardManager**
- Manages board state (6 categories: progress, next_steps, issues, ideas, actions, completed)
- Saves/loads boards from filesystem
- Syncs with hybrid memory graph
- Handles duplicate removal and consolidation
- Restores last focus from memory on startup

#### 4. **ContextManager**
- Queries session-specific memories
- Retrieves project-wide context via semantic search
- Gets related entities from knowledge graph
- Fetches iteration history
- Enriches prompts with relevant context

#### 5. **DocumentationWriter**
- Creates `./Output/projects/<project_id>/` structure
- Generates README.md for each project
- Creates iteration documents in prose (not lists!)
- Maintains PROJECT_SUMMARY.md with running summaries
- Can generate final reports

#### 6. **StreamingHandler**
- Manages progress tracking and UI updates
- Streams output with categories (info, success, warning, error)
- Maintains output buffer
- Tracks stage progress

## Installation

Drop-in replacement - just update your import:

```python
# Old
from Vera.Memory.proactive_focus import ProactiveFocusManager

# New
from Vera.Memory.proactive_focus_manager import ProactiveFocusManager

# Usage is identical
focus_manager = ProactiveFocusManager(
    agent=vera,
    hybrid_memory=vera.mem,
    proactive_interval=600,
    auto_restore=True
)
```

## Usage Examples

### Basic Usage (Same as Before)

```python
# Set focus
focus_manager.set_focus("Build a web scraping tool for research papers")

# Start iterative workflow
focus_manager.iterative_workflow(
    max_iterations=10,
    iteration_interval=300,  # 5 minutes
    auto_execute=True
)
```

### Manual Stage Control

```python
# Run individual stages
focus_manager.generate_ideas()
focus_manager.generate_next_steps()
focus_manager.generate_actions()
focus_manager.execute_actions_stage(max_executions=3, priority_filter="high")
```

### Proactive Thoughts

```python
# Single proactive thought
thought = focus_manager.trigger_proactive_thought()

# Background proactive loop
focus_manager.start()  # Runs in background thread
```

## Intelligent Stage Selection

The `IterationManager` analyzes the board state and creates an execution plan:

```
📋 Board analysis: 3 high-priority actions ready, 2 next steps defined, 5 ideas waiting

🎯 Stage plan:
   🔴 execute_actions (critical): 3 high-priority actions ready
   🟡 generate_actions (high): Convert next steps into executable actions
   🔵 generate_next_steps (medium): Define concrete next steps from ideas
```

Stages are executed in priority order, and low-priority stages may be skipped if time is limited.

## Memory Integration

Every iteration queries memory for context:

```python
# Session context (recent activity)
session_ctx = context_manager.get_session_context(session_id, k=10)

# Project context (semantic search)
project_ctx = context_manager.get_project_context(project_id, focus, k=10)

# Related entities (knowledge graph)
entities = context_manager.get_related_entities(project_id, depth=1)

# Iteration history
history = context_manager.get_iteration_history(project_id, limit=5)
```

This context is automatically injected into LLM prompts for all stages.

## Documentation Generation

Each iteration creates readable documentation:

```
./Output/projects/project_web_scraper/
├── README.md                          # Project overview
├── PROJECT_SUMMARY.md                 # Running summary
└── iterations/
    ├── iteration_001_20260128_143022.md
    ├── iteration_002_20260128_144322.md
    └── ...
```

**Example iteration document:**

```markdown
# Iteration 1

**Timestamp**: 2026-01-28 14:30 UTC

## Executive Summary

Iteration 1 completed 3/3 stages successfully. Generated 5 new ideas. 
Defined 5 next steps. Created 3 actionable items.

## Board State Analysis

Board initialized with project focus. No outstanding issues. 
Ready to begin development.

### Current Metrics

- Progress Items: 0
- Next Steps: 5
- Actions Pending: 3
- Ideas: 5
- Issues: 0

## Context & Decision Making

Focus: Build a web scraping tool for research papers. 
5 relevant project memories found in knowledge graph.

### Intelligent Stage Selection

- 🔵 generate_ideas (medium priority)
  - Reason: Board needs more ideas
  
- 🔵 generate_next_steps (medium priority)
  - Reason: Define concrete next steps from ideas
  
- 🟡 generate_actions (high priority)
  - Reason: Convert next steps into executable actions

## Focus Board Snapshot

### Progress (0 items)

### Next Steps (5 items)

1. Research existing Python web scraping libraries
2. Define paper metadata extraction requirements
3. Design database schema for storing papers
...
```

## Completion Tracking

Actions are automatically moved from `actions` to `progress` or `completed`:

```python
# After execution
focus_manager.board.move_to_completed('actions', idx)

# Automatic cleanup removes duplicates
focus_manager.board.remove_duplicates()
```

## Graph Integration

All entities created during workflow are linked in the knowledge graph:

```
(Project) -[:HAS_ITERATION]-> (Iteration)
(Iteration) -[:HAS_STAGE]-> (Stage)
(Stage) -[:GENERATED]-> (Idea|NextStep|Action)
(Entity) -[:REFERENCES]-> (Resource:URL|FilePath)
(Stage) -[NEXT_STAGE]-> (Stage)
```

This enables powerful queries like:
- "Show me all actions generated in iteration 5"
- "What URLs were discovered during this project?"
- "Which stages generated the most productive ideas?"

## Backward Compatibility

The refactored system maintains **100% API compatibility**:

✅ All public methods unchanged
✅ Same initialization parameters
✅ Same focus board structure
✅ Same WebSocket streaming
✅ Same proactive loop behavior

**Migration**: Just update the import path!

## Configuration

```python
focus_manager = ProactiveFocusManager(
    agent=vera,                          # Vera agent instance
    hybrid_memory=vera.mem,              # HybridMemory instance
    proactive_interval=600,              # Proactive thought interval (seconds)
    cpu_threshold=70.0,                  # Pause if CPU exceeds this
    focus_boards_dir="./Output/...",     # Board save directory
    auto_restore=True                    # Restore last focus on init
)
```

## Advanced Features

### Custom Iteration Plans

```python
# Get board state analysis
board_state = iteration_manager._analyze_board_state()

# Create custom plan
plan = iteration_manager._create_stage_plan(board_state, iteration_num=1)

# Execute specific stages
for stage in plan['stages']:
    iteration_manager._execute_stage(
        stage_name=stage['name'],
        focus=focus,
        project_id=project_id,
        # ...
    )
```

### Context Enrichment

```python
# Enrich any prompt with memory
enriched_prompt = context_manager.enrich_context_with_memory(
    base_context="Analyze the architecture",
    project_id=project_id,
    session_id=session_id,
    focus=focus
)
```

### Custom Documentation

```python
# Generate final report
doc_writer.generate_final_report(
    project_id=project_id,
    focus=focus,
    total_iterations=10,
    final_board=focus_manager.focus_board
)
```

## Benefits of Modular Design

1. **Testability**: Each component can be tested independently
2. **Extensibility**: Easy to add new stages or modify behavior
3. **Maintainability**: Clear separation of concerns
4. **Reusability**: Components can be used in other contexts
5. **Debuggability**: Easier to trace issues to specific components

## Future Enhancements

Potential additions (all backward compatible):

- **Issue Resolution Stage**: Automatically attempt to resolve issues
- **Progress Review Stage**: Periodic review and consolidation
- **Dependency Tracking**: Link actions to next steps and ideas
- **Resource Validation**: Check if URLs are still accessible
- **Metric Tracking**: Track velocity, completion rates over time
- **Multi-Project Support**: Manage multiple projects simultaneously

## Testing

```python
# Test individual components
board = FocusBoardManager("./test_boards")
board.set_focus("Test project")
board.add_item("ideas", "Test idea")
assert len(board.get_category("ideas")) == 1

# Test context retrieval
context = ContextManager(hybrid_memory, agent)
session_ctx = context.get_session_context(session_id)
assert isinstance(session_ctx, list)

# Test documentation
doc_writer = DocumentationWriter("./test_output")
doc_writer.initialize_project("test_proj", "Test focus")
assert os.path.exists("./test_output/test_proj/README.md")
```

## Performance

- **Memory queries**: Cached in vector store for fast retrieval
- **Graph operations**: Batched where possible
- **LLM calls**: Streamed to avoid blocking
- **File I/O**: Async-compatible design
- **CPU monitoring**: Automatic pause during high load

## Troubleshooting

### "No stages selected"
Board is empty. Run `generate_ideas()` manually to bootstrap.

### "Context retrieval failed"
Check hybrid_memory is initialized and Neo4j is running.

### "Documentation not created"
Ensure `./Output/projects/` directory is writable.

### "Actions not executing"
Check that `auto_execute=True` and actions have `priority="high"`.

## License

Same as parent Vera AI project.

## Contributors

Refactored by Claude (Anthropic) based on original ProactiveFocusManager design.