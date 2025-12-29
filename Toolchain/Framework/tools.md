# Vera Tool Framework - Complete Documentation

**Version:** 1.0  
**Last Updated:** December 2024

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Core Concepts](#3-core-concepts)
4. [Base Tool Framework (VTool)](#4-base-tool-framework-vtool)
5. [UI Extensions (UITool)](#5-ui-extensions-uitool)
6. [Type System & Interoperability](#6-type-system--interoperability)
7. [Memory Integration](#7-memory-integration)
8. [Real-time Communication](#8-real-time-communication)
9. [Frontend Integration](#9-frontend-integration)
10. [Complete Examples](#10-complete-examples)
11. [Migration Guide](#11-migration-guide)
12. [API Reference](#12-api-reference)
13. [Best Practices](#13-best-practices)
14. [Troubleshooting](#14-troubleshooting)

---

## 1. Overview

### 1.1 What is the Vera Tool Framework?

The Vera Tool Framework is a comprehensive system for building intelligent, memory-aware tools that can:

- **Automatically track discoveries** in a knowledge graph
- **Stream progress updates** to users in real-time
- **Communicate with UI components** through WebSockets
- **Chain together** based on type compatibility
- **Reuse entities** across multiple tool executions
- **Broadcast graph events** to all connected clients

### 1.2 Key Features

| Feature | Description |
|---------|-------------|
| **Automatic Memory** | Tools automatically create entities and relationships in Neo4j |
| **Streaming Output** | Real-time progress updates via Python generators |
| **UI Communication** | Send structured components (tables, graphs, alerts) to frontend |
| **Event Broadcasting** | WebSocket-based real-time notifications of graph changes |
| **Type System** | Standardized input/output types enable automatic tool chaining |
| **Entity Reuse** | Smart detection and reuse of existing graph entities |
| **Error Handling** | Standardized error reporting and recovery |
| **LangChain Compatible** | Seamless integration with existing LangChain agents |

### 1.3 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (React)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │   ToolUI     │  │  EventLog    │  │ GraphViz        │  │
│  │  Components  │  │              │  │                 │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬────────┘  │
│         │                  │                    │            │
│         └──────────────────┴────────────────────┘            │
│                            │                                 │
│                      WebSocket                               │
└────────────────────────────┼─────────────────────────────────┘
                             │
┌────────────────────────────┼─────────────────────────────────┐
│                     Backend (FastAPI)                        │
│                            │                                 │
│         ┌──────────────────┴────────────────────┐           │
│         │   ToolWebSocketManager                │           │
│         └──────────────────┬────────────────────┘           │
│                            │                                 │
│         ┌──────────────────┴────────────────────┐           │
│         │      EventBroadcaster                 │           │
│         └──────────────────┬────────────────────┘           │
│                            │                                 │
│    ┌───────────────────────┴──────────────────────┐        │
│    │              UITool / VTool                   │        │
│    │  ┌──────────────┐  ┌─────────────────────┐  │        │
│    │  │   Execute    │→ │  Create Entities    │  │        │
│    │  │   Logic      │  │  Link Relationships │  │        │
│    │  └──────────────┘  └─────────────────────┘  │        │
│    └───────────────────────┬──────────────────────┘        │
│                            │                                 │
│         ┌──────────────────┴────────────────────┐           │
│         │       HybridMemory System             │           │
│         │  ┌──────────┐    ┌────────────────┐  │           │
│         │  │  Neo4j   │    │   ChromaDB     │  │           │
│         │  │  Graph   │    │   Vectors      │  │           │
│         │  └──────────┘    └────────────────┘  │           │
│         └───────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Architecture

### 2.1 System Layers

#### Layer 1: Core Tool Framework (VTool)
- Base class for all tools
- Execution lifecycle management
- Memory operations (entity creation, linking)
- Error handling and recovery
- LangChain integration

#### Layer 2: UI Communication (UITool)
- Extends VTool with UI capabilities
- Component-based UI updates
- Event broadcasting
- Progress tracking

#### Layer 3: Event System
- EventBroadcaster for pub/sub
- GraphEvent definitions
- WebSocket management

#### Layer 4: Frontend Components
- React components for rendering
- WebSocket client
- Real-time updates

### 2.2 Data Flow

```
User Input → Tool Execution → Graph Updates → Events → UI Updates
                     ↓
              Memory Storage
                     ↓
              Entity/Relationship
                     ↓
              Neo4j + ChromaDB
```

### 2.3 Component Responsibilities

| Component | Responsibility |
|-----------|---------------|
| **VTool** | Core tool logic, memory management |
| **UITool** | UI communication, event broadcasting |
| **EventBroadcaster** | Event distribution to listeners |
| **ToolWebSocketManager** | WebSocket connection management |
| **ToolResult** | Standardized execution results |
| **ToolEntity** | Entity representation and tracking |
| **GraphEvent** | Graph change notifications |
| **UIComponent** | Structured UI data |

---

## 3. Core Concepts

### 3.1 Tool Execution Lifecycle

```python
# 1. Initialization
tool = MyTool(agent)

# 2. Execution starts
for item in tool.execute(**inputs):
    # 3. Progress updates (strings)
    if isinstance(item, str):
        print(item)  # "Processing..."
    
    # 4. UI updates
    elif isinstance(item, UIUpdate):
        send_to_frontend(item)
    
    # 5. Final result
    elif isinstance(item, ToolResult):
        store_result(item)
```

### 3.2 Memory Operations

Every tool execution creates a hierarchical graph structure:

```
Session
  ↓ [PERFORMED_SCAN]
Execution Node (created automatically)
  ↓ [CREATED/DISCOVERED]
Entities (IPs, Ports, Services, etc.)
  ↓ [HAS_PORT/RUNS_SERVICE/etc.]
Related Entities
```

### 3.3 Entity Reuse

The framework automatically reuses existing entities:

```python
# First tool run
entity1 = tool.create_entity("ip_192_168_1_1", "network_host", ...)
# Creates new entity

# Second tool run (same ID)
entity2 = tool.create_entity("ip_192_168_1_1", "network_host", ...)
# Reuses existing entity, entity2.metadata["reused"] = True
```

### 3.4 Type-Based Interoperability

Tools declare input/output types to enable chaining:

```python
class HostDiscoveryTool(VTool):
    def get_output_type(self) -> OutputType:
        return OutputType.IP_LIST

class PortScanTool(VTool):
    def get_input_schema(self):
        # Accepts str or List[str] (IP_LIST)
        class Input(BaseModel):
            target: Union[str, List[str]]
        return Input
```

---

## 4. Base Tool Framework (VTool)

### 4.1 Creating a Tool

Every tool must:
1. Subclass `VTool`
2. Implement three required methods
3. Use `self.create_entity()` and `self.link_entities()` for memory
4. Yield strings for progress, final `ToolResult` at end

#### Minimal Example

```python
from tool_framework import VTool, ToolResult, OutputType
from pydantic import BaseModel, Field
from typing import Iterator, Union

class MyToolInput(BaseModel):
    """Define inputs with Pydantic"""
    target: str = Field(description="What to process")
    option: str = Field(default="default", description="Processing option")

class MyTool(VTool):
    """My custom tool - does X, Y, Z"""
    
    def get_input_schema(self) -> Type[BaseModel]:
        """Return the input schema"""
        return MyToolInput
    
    def get_output_type(self) -> OutputType:
        """Declare what this tool produces"""
        return OutputType.TEXT
    
    def _execute(self, target: str, option: str = "default") -> Iterator[Union[str, ToolResult]]:
        """
        Execute the tool logic.
        
        Yield strings for progress updates.
        Yield final ToolResult at the end.
        """
        # Progress update
        yield f"Processing {target} with {option}...\n"
        
        # Do work
        result = process_something(target, option)
        
        # Create memory entities
        entity = self.create_entity(
            entity_id=f"result_{target}",
            entity_type="my_result",
            labels=["Result", "MyTool"],
            properties={
                "target": target,
                "value": result
            }
        )
        
        # More progress
        yield f"Created entity: {entity.id}\n"
        
        # Final result
        yield ToolResult(
            success=True,
            output=result,
            output_type=OutputType.TEXT
        )
```

### 4.2 VTool API Reference

#### Constructor

```python
def __init__(self, agent):
    """
    Initialize tool with agent reference.
    
    Args:
        agent: Vera agent instance with .mem, .sess
    
    Provides:
        self.agent - Agent reference
        self.mem - HybridMemory instance
        self.sess - Current session
        self.tool_name - Tool class name
        self.execution_node_id - Current execution ID
    """
```

#### Required Methods

```python
@abstractmethod
def get_input_schema(self) -> Type[BaseModel]:
    """
    Return Pydantic model defining tool inputs.
    
    Example:
        class MyInput(BaseModel):
            target: str = Field(description="Target to process")
            count: int = Field(default=10, description="How many")
        
        return MyInput
    """
    pass

@abstractmethod
def get_output_type(self) -> OutputType:
    """
    Declare the type of output this tool produces.
    
    Used for tool chaining and type checking.
    
    Returns:
        OutputType enum value
    
    Example:
        return OutputType.JSON
    """
    pass

@abstractmethod
def _execute(self, **kwargs) -> Iterator[Union[str, ToolResult]]:
    """
    Execute tool logic.
    
    Must yield:
        - Strings for progress updates
        - Final ToolResult with success/output
    
    Example:
        yield "Starting...\n"
        result = do_work()
        yield ToolResult(success=True, output=result, output_type=OutputType.TEXT)
    """
    pass
```

#### Memory Methods

```python
def create_entity(
    self,
    entity_id: str,
    entity_type: str,
    labels: Optional[List[str]] = None,
    properties: Optional[Dict] = None,
    metadata: Optional[Dict] = None,
    reuse_if_exists: bool = True
) -> ToolEntity:
    """
    Create an entity and track it for memory storage.
    
    Args:
        entity_id: Unique identifier (e.g., "ip_192_168_1_1")
        entity_type: Entity type (e.g., "network_host")
        labels: Neo4j labels (defaults to [entity_type])
        properties: Entity properties dict
        metadata: Metadata for linking (not stored in entity)
        reuse_if_exists: If True, reuse existing entity
    
    Returns:
        ToolEntity instance
        
    Notes:
        - Automatically adds created_at and created_by
        - If entity exists and reuse_if_exists=True:
          - Returns existing entity
          - Sets metadata["reused"] = True
          - Still links to current execution
    
    Example:
        entity = self.create_entity(
            entity_id="host_example_com",
            entity_type="web_server",
            labels=["Server", "HTTP"],
            properties={
                "hostname": "example.com",
                "ip": "93.184.216.34",
                "status": "online"
            }
        )
    """

def link_entities(
    self,
    source_id: str,
    target_id: str,
    rel_type: str,
    properties: Optional[Dict] = None
) -> ToolRelationship:
    """
    Create a relationship between entities.
    
    Args:
        source_id: Source entity ID
        target_id: Target entity ID
        rel_type: Relationship type (e.g., "HAS_PORT", "RUNS_SERVICE")
        properties: Relationship properties
    
    Returns:
        ToolRelationship instance
    
    Example:
        self.link_entities(
            "host_example_com",
            "port_80_http",
            "HAS_PORT",
            {"port_number": 80, "state": "open"}
        )
    """
```

#### Utility Methods

```python
def format_output(self, data: Any, truncate: int = 5000) -> str:
    """
    Format data for display.
    
    - Converts dicts/lists to pretty JSON
    - Converts other types to string
    - Truncates if longer than truncate
    """

def get_description(self) -> str:
    """
    Get tool description.
    
    Override for custom descriptions.
    Defaults to class docstring.
    """
```

### 4.3 ToolResult Structure

```python
@dataclass
class ToolResult:
    """Standardized tool execution result"""
    
    # Required fields
    success: bool                    # Execution succeeded?
    output: Any                      # Tool output (any type)
    output_type: OutputType          # Type classification
    
    # Memory artifacts (populated automatically)
    entities: List[ToolEntity]       # Created entities
    relationships: List[ToolRelationship]  # Created relationships
    
    # Metadata (populated automatically)
    tool_name: str                   # Tool that created this
    execution_time: float            # Seconds elapsed
    error: Optional[str]             # Error message if failed
    metadata: Dict[str, Any]         # Additional metadata
    
    # For chaining
    intermediate_results: Dict[str, Any]  # Step-by-step results
    
    # Methods
    def to_json(self) -> str:
        """Convert to JSON string"""
    
    def get_entity_ids(self) -> List[str]:
        """Get all created entity IDs"""
    
    def get_output_for_chaining(self) -> Any:
        """Get output formatted for next tool in chain"""
```

### 4.4 ToolEntity & ToolRelationship

```python
@dataclass
class ToolEntity:
    """Entity created/discovered by a tool"""
    id: str                          # Unique ID
    type: str                        # Entity type
    labels: List[str]                # Neo4j labels
    properties: Dict[str, Any]       # Entity properties
    metadata: Dict[str, Any]         # Linking metadata (e.g., {"reused": True})

@dataclass
class ToolRelationship:
    """Relationship between entities"""
    source_id: str                   # Source entity ID
    target_id: str                   # Target entity ID
    rel_type: str                    # Relationship type
    properties: Dict[str, Any]       # Relationship properties
```

### 4.5 OutputType Enum

```python
class OutputType(str, Enum):
    """Standard output types for tool interoperability"""
    TEXT = "text"
    JSON = "json"
    IP_LIST = "ip_list"
    PORT_LIST = "port_list"
    SERVICE_LIST = "service_list"
    VULNERABILITY_LIST = "vulnerability_list"
    FILE_PATH = "file_path"
    URL = "url"
    ENTITY_ID = "entity_id"
    SUBGRAPH = "subgraph"
    SEARCH_RESULTS = "search_results"
    CODE = "code"
    COMMAND_OUTPUT = "command_output"
    
    # Add custom types by extending:
    # OutputType.CUSTOM_TYPE = "custom_type"
```

---

## 5. UI Extensions (UITool)

### 5.1 UITool Overview

`UITool` extends `VTool` with:
- Real-time UI component updates
- Event broadcasting to WebSocket clients
- Progress bars, tables, graphs, alerts
- Entity visualization

### 5.2 Creating a UI-Enabled Tool

```python
from tool_framework import UITool, ToolResult, OutputType
from pydantic import BaseModel, Field

class MyUIToolInput(BaseModel):
    target: str = Field(description="What to process")

class MyUITool(UITool):
    """Tool with UI capabilities"""
    
    def get_input_schema(self):
        return MyUIToolInput
    
    def get_output_type(self):
        return OutputType.JSON
    
    def _execute(self, target: str):
        # Send alert to UI
        self.send_alert(f"Starting processing of {target}", "info")
        
        # Show progress
        for i in range(10):
            self.send_progress(i+1, 10, f"Processing step {i+1}")
            
            # Do work
            result = process_step(i)
            
            # Create entity (automatically sends entity card to UI)
            entity = self.create_entity(
                f"result_{i}",
                "result",
                properties={"step": i, "value": result}
            )
            
            yield f"Step {i+1} complete\n"
        
        # Send final table
        self.send_table(
            headers=["Step", "Result"],
            rows=[[i, f"value_{i}"] for i in range(10)],
            title="Processing Results"
        )
        
        # Final result
        yield ToolResult(
            success=True,
            output={"steps": 10, "status": "complete"},
            output_type=OutputType.JSON
        )
```

### 5.3 UITool API Reference

#### UI Component Methods

```python
def send_ui_component(
    self,
    component: UIComponent,
    update_type: str = "append"
):
    """
    Send a UI component to frontend.
    
    Args:
        component: UIComponent instance
        update_type: "append", "replace", or "update"
    """

def send_progress(
    self,
    current: int,
    total: int,
    message: str = ""
):
    """
    Send progress bar update.
    
    Args:
        current: Current progress (0-total)
        total: Total steps
        message: Optional message
    
    Creates progress bar showing percentage.
    """

def send_table(
    self,
    headers: List[str],
    rows: List[List[Any]],
    title: str = ""
):
    """
    Send table data to UI.
    
    Args:
        headers: Column headers
        rows: List of rows (each row is list of values)
        title: Optional table title
    
    Renders as formatted table in UI.
    """

def send_entity_card(self, entity: ToolEntity):
    """
    Send entity card for display.
    
    Shows entity properties, labels, type in expandable card.
    """

def send_graph_update(
    self,
    nodes: List[Dict],
    edges: List[Dict],
    layout: str = "force"
):
    """
    Send graph visualization update.
    
    Args:
        nodes: List of node dicts with id, label, properties
        edges: List of edge dicts with source, target, label
        layout: Layout algorithm ("force", "hierarchical", "circular")
    """

def send_network_topology(self, topology: Dict[str, Any]):
    """
    Send network topology visualization.
    
    Specialized for network scanning results.
    """

def send_alert(
    self,
    message: str,
    severity: str = "info"
):
    """
    Send alert/notification.
    
    Args:
        message: Alert message
        severity: "info", "success", "warning", or "error"
    
    Shows as toast notification.
    """

def send_metrics(self, metrics: Dict[str, Any]):
    """
    Send metrics/statistics.
    
    Args:
        metrics: Dict of metric_name: value
    
    Displays as metric cards (e.g., "Hosts: 10", "Ports: 45").
    """
```

#### Event Broadcasting Methods

```python
def broadcast_event(self, event: GraphEvent):
    """
    Broadcast a graph event to all listeners.
    
    Args:
        event: GraphEvent instance
    
    Event is sent to:
    - All WebSocket connections for this session
    - Event log
    - Registered event listeners
    """

# These are called automatically:
def _broadcast_execution_started(self, inputs: Dict):
    """Broadcast when execution starts"""

def _broadcast_execution_progress(self, progress: Dict):
    """Broadcast progress updates"""

def _broadcast_execution_completed(self, result: ToolResult):
    """Broadcast when execution completes"""
```

#### Enhanced Entity Methods

```python
def create_entity(..., broadcast: bool = True) -> ToolEntity:
    """
    Create entity with optional broadcasting.
    
    If broadcast=True:
    - Broadcasts ENTITY_CREATED event
    - Sends entity card to UI
    """

def link_entities(..., broadcast: bool = True) -> ToolRelationship:
    """
    Link entities with optional broadcasting.
    
    If broadcast=True:
    - Broadcasts RELATIONSHIP_CREATED event
    """
```

#### Graph Visualization

```python
def visualize_subgraph(
    self,
    entity_ids: List[str],
    depth: int = 1
):
    """
    Visualize subgraph around entities.
    
    Args:
        entity_ids: Central entity IDs
        depth: How many hops to include
    
    Extracts subgraph and sends to UI as graph visualization.
    """
```

### 5.4 UIComponent Types

```python
class UIComponentType(str, Enum):
    TEXT = "text"                    # Plain text
    TABLE = "table"                  # Data table
    GRAPH = "graph"                  # Graph visualization
    PROGRESS = "progress"            # Progress bar
    ENTITY_CARD = "entity_card"      # Entity details card
    RELATIONSHIP_GRAPH = "relationship_graph"  # Relationship visualization
    CODE_BLOCK = "code_block"        # Code with syntax highlighting
    ALERT = "alert"                  # Alert/notification
    METRICS = "metrics"              # Metrics display
    TIMELINE = "timeline"            # Timeline visualization
    NETWORK_TOPOLOGY = "network_topology"  # Network map
```

### 5.5 GraphEvent Types

```python
class GraphEventType(str, Enum):
    ENTITY_CREATED = "entity_created"
    ENTITY_UPDATED = "entity_updated"
    RELATIONSHIP_CREATED = "relationship_created"
    EXECUTION_STARTED = "execution_started"
    EXECUTION_PROGRESS = "execution_progress"
    EXECUTION_COMPLETED = "execution_completed"
    EXECUTION_FAILED = "execution_failed"
    DATA_DISCOVERED = "data_discovered"
```

---

## 6. Type System & Interoperability

### 6.1 Type-Based Tool Chaining

Tools can be automatically chained if output type matches input type:

```python
# Tool 1: Produces IP_LIST
class HostDiscovery(VTool):
    def get_output_type(self):
        return OutputType.IP_LIST

# Tool 2: Accepts IP_LIST
class PortScan(VTool):
    class Input(BaseModel):
        target: Union[str, List[str]]  # Accepts IP_LIST
    
    def _execute(self, target: Union[str, List[str]]):
        # Handle both single IP or list
        if isinstance(target, list):
            ips = target  # From HostDiscovery
        else:
            ips = parse_target(target)
```

### 6.2 ToolChain Manager

```python
from tool_framework import ToolChain

# Create chain manager
chain = ToolChain(agent)

# Register tools
chain.register_tool(HostDiscoveryTool(agent))
chain.register_tool(PortScanTool(agent))

# Find compatible tools
compatible = chain.find_compatible_tools(OutputType.IP_LIST)
# Returns: ["PortScanTool", "ServiceDetectionTool", ...]

# Check if tools can chain
can_chain = chain.can_chain("HostDiscoveryTool", "PortScanTool")
# Returns: True
```

### 6.3 Custom Output Types

```python
# Extend OutputType for your domain
class CustomOutputType(str, Enum):
    SECURITY_REPORT = "security_report"
    CODE_REVIEW = "code_review"
    ANALYSIS_RESULTS = "analysis_results"

# Register extension
OutputType.SECURITY_REPORT = "security_report"
OutputType.CODE_REVIEW = "code_review"

# Use in tool
class SecurityAnalysisTool(VTool):
    def get_output_type(self):
        return OutputType.SECURITY_REPORT
```

---

## 7. Memory Integration

### 7.1 Automatic Memory Operations

Every tool execution automatically:

1. **Creates execution node** - Links to session
2. **Tracks all entities** - Created via `create_entity()`
3. **Links entities** - To execution, session, and each other
4. **Stores results** - In ChromaDB for semantic search
5. **Enables graph queries** - All data queryable via Cypher

### 7.2 Memory Graph Structure

```cypher
# Query example - get all results from a tool
MATCH (session:Session {id: $session_id})
      -[:PERFORMED_SCAN]->(exec:Execution {tool_name: $tool_name})
      -[:CREATED]->(entity)
RETURN exec, entity

# Query example - get full execution topology
MATCH (exec:Execution {id: $execution_id})
OPTIONAL MATCH (exec)-[*1..3]->(node)
RETURN exec, node
```

### 7.3 Entity Reuse Strategy

```python
# First execution
tool1 = NetworkScanTool(agent)
for item in tool1.execute(target="192.168.1.0/24"):
    pass
# Creates: ip_192_168_1_1, ip_192_168_1_2, etc.

# Second execution (same targets)
tool2 = NetworkScanTool(agent)
for item in tool2.execute(target="192.168.1.1"):
    pass
# Reuses: ip_192_168_1_1 (doesn't create duplicate)
# Links: new execution -> existing entity
```

### 7.4 Memory Query Methods

```python
# In any tool
def _execute(self, target: str):
    # Check if entity already exists
    try:
        subgraph = self.mem.extract_subgraph([entity_id], depth=0)
        exists = any(n.get("id") == entity_id 
                    for n in subgraph.get("nodes", []))
    except:
        exists = False
    
    if exists:
        yield "Entity already exists, updating...\n"
    else:
        yield "Creating new entity...\n"
    
    # Create or update
    entity = self.create_entity(entity_id, ..., reuse_if_exists=True)
```

---

## 8. Real-time Communication

### 8.1 WebSocket Architecture

```
Browser                Backend                  Tool
   │                      │                      │
   │──── Connect WS ─────→│                      │
   │←─── Subscribe ───────│                      │
   │                      │                      │
   │                      │←── Tool Execute ─────│
   │                      │                      │
   │←── Progress Event ───│←── Broadcast ────────│
   │←── Entity Created ───│←── Broadcast ────────│
   │←── UI Update ────────│←── Send Component ───│
   │                      │                      │
   │←── Complete ─────────│←── Broadcast ────────│
```

### 8.2 Backend Integration

#### FastAPI Endpoint

```python
# In ChatUI/api/session.py or similar

from fastapi import WebSocket, WebSocketDisconnect
from tool_framework import ToolWebSocketManager, EventBroadcaster
import json

# Initialize once per application
event_broadcaster = EventBroadcaster()
ws_manager = ToolWebSocketManager(event_broadcaster)

@router.websocket("/ws/tools/{session_id}")
async def tool_websocket(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time tool updates"""
    
    await websocket.accept()
    
    # Get agent for session
    agent = get_agent_for_session(session_id)
    
    # Register connection
    await ws_manager.register_connection(session_id, websocket)
    
    try:
        # Keep connection alive
        while True:
            data = await websocket.receive_text()
            
            # Handle client commands
            try:
                cmd = json.loads(data)
                
                if cmd.get("type") == "subscribe":
                    await websocket.send_text(json.dumps({
                        "type": "subscribed",
                        "session_id": session_id
                    }))
                
                elif cmd.get("type") == "get_events":
                    # Send recent events
                    events = event_broadcaster.get_recent_events(100)
                    await websocket.send_text(json.dumps({
                        "type": "event_history",
                        "events": [e.to_dict() for e in events]
                    }))
            except:
                pass
    
    except WebSocketDisconnect:
        await ws_manager.unregister_connection(session_id)
```

#### Agent Initialization

```python
# In vera.py or agent setup

def integrate_ui_tools(agent):
    """Add UI/Broadcasting support to agent"""
    
    # Add event broadcaster
    if not hasattr(agent, 'event_broadcaster'):
        agent.event_broadcaster = EventBroadcaster()
    
    # Add WebSocket manager
    if not hasattr(agent, 'tool_websocket_manager'):
        agent.tool_websocket_manager = ToolWebSocketManager(
            agent.event_broadcaster
        )

# In Vera.__init__
class Vera:
    def __init__(self):
        # ... existing setup ...
        
        # Add UI support
        integrate_ui_tools(self)
```

### 8.3 EventBroadcaster API

```python
class EventBroadcaster:
    """Manages event distribution"""
    
    def register_listener(self, callback: Callable[[GraphEvent], None]):
        """
        Register callback for events.
        
        Callback signature: def on_event(event: GraphEvent) -> None
        """
    
    def unregister_listener(self, callback: Callable):
        """Remove callback"""
    
    def broadcast(self, event: GraphEvent):
        """
        Broadcast event to all listeners.
        
        Adds to event queue and notifies all callbacks.
        """
    
    def get_recent_events(self, count: int = 100) -> List[GraphEvent]:
        """Get recent events from queue"""
```

### 8.4 ToolWebSocketManager API

```python
class ToolWebSocketManager:
    """Manages WebSocket connections for tools"""
    
    async def register_connection(self, session_id: str, websocket):
        """Register WebSocket for session"""
    
    async def unregister_connection(self, session_id: str):
        """Unregister WebSocket"""
    
    def on_event(self, event: GraphEvent):
        """
        Handle broadcast event.
        
        Automatically sends to appropriate WebSocket connections.
        """
```

---

## 9. Frontend Integration

### 9.1 React Component Structure

```tsx
// Main container component
<ToolUIContainer sessionId={sessionId}>
  ├─ <ToolUI />               // Renders tool components
  ├─ <EventLog />             // Shows event history
  └─ <GraphVisualization />   // Live graph view
```

### 9.2 WebSocket Hook

```typescript
// hooks/useWebSocket.ts
import { useEffect, useState } from 'react';

export const useWebSocket = (url: string) => {
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [lastMessage, setLastMessage] = useState<any>(null);
  
  useEffect(() => {
    const websocket = new WebSocket(url);
    
    websocket.onopen = () => {
      console.log('WebSocket connected');
      // Subscribe to events
      websocket.send(JSON.stringify({ type: 'subscribe' }));
    };
    
    websocket.onmessage = (event) => {
      setLastMessage(event);
    };
    
    websocket.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
    
    websocket.onclose = () => {
      console.log('WebSocket disconnected');
    };
    
    setWs(websocket);
    
    return () => {
      websocket.close();
    };
  }, [url]);
  
  const sendMessage = (message: any) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(message));
    }
  };
  
  return { lastMessage, sendMessage };
};
```

### 9.3 Component Examples

#### Progress Component

```typescript
interface ProgressProps {
  current: number;
  total: number;
  percentage: number;
  message: string;
}

export const ProgressComponent: React.FC<ProgressProps> = ({
  current,
  total,
  percentage,
  message
}) => (
  <div className="progress-component">
    <div className="progress-bar">
      <div 
        className="progress-fill"
        style={{ width: `${percentage}%` }}
      />
    </div>
    <div className="progress-text">
      {message || `${current} / ${total} (${percentage.toFixed(1)}%)`}
    </div>
  </div>
);
```

#### Entity Card Component

```typescript
interface EntityCardProps {
  entity_id: string;
  type: string;
  labels: string[];
  properties: Record<string, any>;
}

export const EntityCardComponent: React.FC<EntityCardProps> = ({
  entity_id,
  type,
  labels,
  properties
}) => (
  <div className="entity-card">
    <div className="entity-header">
      <span className="entity-id">{entity_id}</span>
      <span className="entity-type">{type}</span>
    </div>
    <div className="entity-labels">
      {labels.map(label => (
        <span key={label} className="label">{label}</span>
      ))}
    </div>
    <div className="entity-properties">
      {Object.entries(properties).map(([key, value]) => (
        <div key={key} className="property">
          <span className="key">{key}:</span>
          <span className="value">{JSON.stringify(value)}</span>
        </div>
      ))}
    </div>
  </div>
);
```

#### Table Component

```typescript
interface TableProps {
  headers: string[];
  rows: any[][];
  title?: string;
}

export const TableComponent: React.FC<TableProps> = ({
  headers,
  rows,
  title
}) => (
  <div className="table-component">
    {title && <h3>{title}</h3>}
    <table>
      <thead>
        <tr>
          {headers.map((h, i) => <th key={i}>{h}</th>)}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr key={i}>
            {row.map((cell, j) => <td key={j}>{cell}</td>)}
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);
```

### 9.4 Main Container Component

```typescript
export const ToolUIContainer: React.FC<{ sessionId: string }> = ({
  sessionId
}) => {
  const [components, setComponents] = useState<UIComponent[]>([]);
  const [events, setEvents] = useState<GraphEvent[]>([]);
  const { lastMessage } = useWebSocket(`/ws/tools/${sessionId}`);
  
  useEffect(() => {
    if (!lastMessage) return;
    
    const message = JSON.parse(lastMessage.data);
    
    if (message.type === 'tool_event') {
      const event = message.event as GraphEvent;
      handleEvent(event);
    }
  }, [lastMessage]);
  
  const handleEvent = (event: GraphEvent) => {
    // Add to event log
    setEvents(prev => [...prev, event]);
    
    // Handle UI updates
    if (event.data.ui_update) {
      handleUIUpdate(event.data.ui_update);
    }
  };
  
  const handleUIUpdate = (update: UIUpdate) => {
    switch (update.update_type) {
      case 'append':
        setComponents(prev => [...prev, update.component]);
        break;
      case 'replace':
        setComponents(prev =>
          prev.map(c =>
            c.component_id === update.target_id ? update.component : c
          )
        );
        break;
    }
  };
  
  return (
    <div className="tool-ui-container">
      {components.map(component => {
        const Component = ComponentRegistry[component.component_type];
        return <Component key={component.component_id} {...component.data} />;
      })}
      <EventLog events={events} />
    </div>
  );
};
```

### 9.5 Styling

```css
/* Tool UI Styles */
.tool-ui-container {
  padding: 1rem;
  max-height: 80vh;
  overflow-y: auto;
  background: #f5f5f5;
}

.progress-component {
  margin: 1rem 0;
  padding: 1rem;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.progress-bar {
  height: 24px;
  background: #e0e0e0;
  border-radius: 12px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #4CAF50, #8BC34A);
  transition: width 0.3s ease;
}

.entity-card {
  margin: 1rem 0;
  padding: 1rem;
  background: white;
  border-radius: 8px;
  border-left: 4px solid #2196F3;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  animation: slideIn 0.3s ease;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateX(-20px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.table-component {
  margin: 1rem 0;
  background: white;
  border-radius: 8px;
  padding: 1rem;
  overflow-x: auto;
}

.table-component table {
  width: 100%;
  border-collapse: collapse;
}

.table-component th {
  background: #f0f0f0;
  padding: 0.75rem;
  text-align: left;
  font-weight: 600;
}

.table-component td {
  padding: 0.75rem;
  border-bottom: 1px solid #e0e0e0;
}
```

---

## 10. Complete Examples

### 10.1 Network Scanner with Full UI

```python
from tool_framework import UITool, ToolResult, OutputType
from pydantic import BaseModel, Field
from typing import Iterator, Union, List

class NetworkScanInput(BaseModel):
    target: str = Field(description="Network target (IP, CIDR, range)")
    ports: str = Field(default="1-1000", description="Port range to scan")
    timeout: float = Field(default=1.0, description="Scan timeout")

class NetworkScannerTool(UITool):
    """
    Comprehensive network scanner with real-time UI updates.
    
    Features:
    - Live progress tracking
    - Network topology visualization
    - Entity tracking and reuse
    - Event broadcasting
    """
    
    def get_input_schema(self):
        return NetworkScanInput
    
    def get_output_type(self):
        return OutputType.JSON
    
    def _execute(self, target: str, ports: str = "1-1000", 
                 timeout: float = 1.0) -> Iterator[Union[str, ToolResult]]:
        
        # Initial alert
        self.send_alert(f"Starting network scan of {target}", "info")
        
        # Parse targets
        from Vera.Toolchain.Tools.OSINT.network_scanning import (
            TargetParser, HostDiscovery, PortScanner, NetworkScanConfig
        )
        
        parser = TargetParser()
        targets = parser.parse(target)
        port_list = parser.parse_ports(ports)
        
        # Initial metrics
        self.send_metrics({
            "total_targets": len(targets),
            "total_ports": len(port_list),
            "status": "scanning"
        })
        
        yield f"╔════════════════════════════════════════════════════╗\n"
        yield f"║           NETWORK SCAN - {target:^25} ║\n"
        yield f"╚════════════════════════════════════════════════════╝\n\n"
        
        # Initialize scanners
        config = NetworkScanConfig(scan_timeout=timeout)
        discoverer = HostDiscovery(config)
        scanner = PortScanner(config)
        
        # Track discoveries
        live_hosts = []
        all_ports = []
        topology_nodes = []
        topology_edges = []
        
        # Phase 1: Host Discovery
        yield "[1/2] HOST DISCOVERY\n"
        yield "─" * 60 + "\n\n"
        
        for idx, host_info in enumerate(discoverer.discover_live_hosts(targets), 1):
            if host_info["alive"]:
                ip = host_info["ip"]
                hostname = host_info["hostname"]
                
                live_hosts.append(ip)
                
                # Create entity with broadcasting
                entity = self.create_entity(
                    entity_id=f"ip_{ip.replace('.', '_')}",
                    entity_type="network_host",
                    labels=["NetworkHost", "IP"],
                    properties={
                        "ip_address": ip,
                        "hostname": hostname,
                        "status": "up"
                    },
                    broadcast=True  # Sends entity card + event
                )
                
                # Add to topology
                topology_nodes.append({
                    "id": entity.id,
                    "label": ip,
                    "type": "host",
                    "status": "up"
                })
                
                # Update progress
                self.send_progress(
                    idx, 
                    len(targets), 
                    f"Discovered {ip}"
                )
                
                # Broadcast discovery
                self.broadcast_event(GraphEvent(
                    event_type=GraphEventType.DATA_DISCOVERED,
                    data={
                        "discovery_type": "host",
                        "ip": ip,
                        "hostname": hostname
                    }
                ))
                
                marker = "[♻]" if entity.metadata.get("reused") else "[✓]"
                yield f"  {marker} {ip}"
                if hostname:
                    yield f" ({hostname})"
                yield "\n"
        
        if not live_hosts:
            self.send_alert("No live hosts found", "warning")
            yield ToolResult(
                success=False,
                output={},
                output_type=OutputType.JSON,
                error="No live hosts"
            )
            return
        
        # Phase 2: Port Scanning
        yield f"\n[2/2] PORT SCANNING\n"
        yield "─" * 60 + "\n\n"
        
        for host_idx, ip in enumerate(live_hosts, 1):
            ip_entity_id = f"ip_{ip.replace('.', '_')}"
            
            yield f"[•] Scanning {ip}...\n"
            
            port_count = 0
            
            for port_info in scanner.scan_host(ip, port_list):
                port_num = port_info["port"]
                port_count += 1
                
                # Create port entity
                port_entity = self.create_entity(
                    entity_id=f"{ip_entity_id}_port_{port_num}",
                    entity_type="network_port",
                    labels=["NetworkPort", "Port"],
                    properties={
                        "port_number": port_num,
                        "state": "open",
                        "service": port_info["service"]
                    },
                    broadcast=True
                )
                
                # Link entities
                self.link_entities(
                    ip_entity_id,
                    port_entity.id,
                    "HAS_PORT",
                    {"port": port_num},
                    broadcast=True
                )
                
                # Add to topology
                topology_edges.append({
                    "source": ip_entity_id,
                    "target": port_entity.id,
                    "label": f":{port_num}"
                })
                
                all_ports.append({
                    "ip": ip,
                    "port": port_num,
                    "service": port_info["service"]
                })
                
                # Broadcast discovery
                self.broadcast_event(GraphEvent(
                    event_type=GraphEventType.DATA_DISCOVERED,
                    data={
                        "discovery_type": "port",
                        "ip": ip,
                        "port": port_num,
                        "service": port_info["service"]
                    }
                ))
                
                marker = "[♻]" if port_entity.metadata.get("reused") else "[✓]"
                yield f"    {marker} Port {port_num}: {port_info['service']}\n"
            
            if port_count == 0:
                yield f"    No open ports found\n"
            
            # Update topology after each host
            self.send_network_topology({
                "nodes": topology_nodes,
                "edges": topology_edges,
                "stats": {
                    "hosts": len(live_hosts),
                    "ports": len(all_ports)
                }
            })
            
            # Update metrics
            self.send_metrics({
                "total_targets": len(targets),
                "live_hosts": len(live_hosts),
                "open_ports": len(all_ports),
                "status": "scanning",
                "progress": f"{host_idx}/{len(live_hosts)}"
            })
        
        # Final summary table
        if all_ports:
            self.send_table(
                headers=["IP", "Port", "Service"],
                rows=[[p["ip"], p["port"], p["service"]] for p in all_ports],
                title="Scan Results"
            )
        
        # Final metrics
        self.send_metrics({
            "total_targets": len(targets),
            "live_hosts": len(live_hosts),
            "open_ports": len(all_ports),
            "status": "completed"
        })
        
        # Visualize final graph
        self.visualize_subgraph(
            [f"ip_{ip.replace('.', '_')}" for ip in live_hosts],
            depth=2
        )
        
        self.send_alert("Scan completed successfully", "success")
        
        yield f"\n╔════════════════════════════════════════════════════╗\n"
        yield f"  Live Hosts:     {len(live_hosts)}\n"
        yield f"  Open Ports:     {len(all_ports)}\n"
        yield f"  Execution:      {self.execution_node_id}\n"
        yield f"╚════════════════════════════════════════════════════╝\n"
        
        # Final result
        yield ToolResult(
            success=True,
            output={
                "live_hosts": live_hosts,
                "open_ports": all_ports,
                "topology": {
                    "nodes": topology_nodes,
                    "edges": topology_edges
                }
            },
            output_type=OutputType.JSON,
            metadata={
                "hosts_found": len(live_hosts),
                "ports_found": len(all_ports)
            }
        )
```

### 10.2 Code Execution Tool

```python
class CodeExecutionInput(BaseModel):
    code: str = Field(description="Code to execute")
    language: str = Field(default="python", description="Programming language")

class CodeExecutionTool(UITool):
    """Execute code with live output streaming"""
    
    def get_input_schema(self):
        return CodeExecutionInput
    
    def get_output_type(self):
        return OutputType.CODE
    
    def _execute(self, code: str, language: str = "python") -> Iterator:
        # Send code block to UI
        self.send_ui_component(UIComponent(
            component_type=UIComponentType.CODE_BLOCK,
            data={
                "code": code,
                "language": language,
                "status": "executing"
            }
        ))
        
        self.send_alert("Executing code...", "info")
        
        import sys
        import io
        
        old_stdout = sys.stdout
        redirected = sys.stdout = io.StringIO()
        
        try:
            # Execute code
            exec(code, globals())
            output = redirected.getvalue()
            
            # Create code entity
            code_entity = self.create_entity(
                entity_id=f"code_{hash(code) % 1000000}",
                entity_type="python_code",
                labels=["Code", "Python"],
                properties={
                    "code": code[:1000],
                    "language": language
                }
            )
            
            # Create output entity
            if output:
                output_entity = self.create_entity(
                    entity_id=f"output_{hash(output) % 1000000}",
                    entity_type="execution_output",
                    labels=["Output"],
                    properties={"output": output[:1000]}
                )
                
                self.link_entities(
                    code_entity.id,
                    output_entity.id,
                    "PRODUCED"
                )
            
            # Update UI with success
            self.send_ui_component(UIComponent(
                component_type=UIComponentType.CODE_BLOCK,
                data={
                    "code": code,
                    "language": language,
                    "output": output,
                    "status": "success"
                }
            ), update_type="replace")
            
            self.send_alert("Execution completed", "success")
            
            yield output
            
            yield ToolResult(
                success=True,
                output=output,
                output_type=OutputType.CODE
            )
            
        except Exception as e:
            error_msg = str(e)
            
            # Update UI with error
            self.send_ui_component(UIComponent(
                component_type=UIComponentType.CODE_BLOCK,
                data={
                    "code": code,
                    "language": language,
                    "output": error_msg,
                    "status": "error"
                }
            ), update_type="replace")
            
            self.send_alert(f"Execution failed: {error_msg}", "error")
            
            yield ToolResult(
                success=False,
                output=error_msg,
                output_type=OutputType.CODE,
                error=error_msg
            )
        
        finally:
            sys.stdout = old_stdout
```

### 10.3 File Processing Tool

```python
class FileProcessInput(BaseModel):
    path: str = Field(description="File path to process")
    operation: str = Field(default="analyze", description="Operation to perform")

class FileProcessingTool(UITool):
    """Process files with progress tracking"""
    
    def get_input_schema(self):
        return FileProcessInput
    
    def get_output_type(self):
        return OutputType.JSON
    
    def _execute(self, path: str, operation: str = "analyze") -> Iterator:
        import os
        
        self.send_alert(f"Processing file: {path}", "info")
        
        # Check file exists
        if not os.path.exists(path):
            self.send_alert(f"File not found: {path}", "error")
            yield ToolResult(
                success=False,
                output={},
                output_type=OutputType.JSON,
                error="File not found"
            )
            return
        
        # Get file info
        file_size = os.path.getsize(path)
        
        # Create file entity
        file_entity = self.create_entity(
            entity_id=f"file_{path.replace('/', '_')}",
            entity_type="file",
            labels=["File", "Document"],
            properties={
                "path": path,
                "size": file_size,
                "exists": True
            }
        )
        
        yield f"Processing {path} ({file_size} bytes)...\n"
        
        # Read file with progress
        with open(path, 'r') as f:
            lines = f.readlines()
        
        total_lines = len(lines)
        
        # Process lines
        results = []
        for idx, line in enumerate(lines, 1):
            # Update progress
            if idx % 100 == 0:
                self.send_progress(idx, total_lines, f"Processing line {idx}")
            
            # Process line
            result = process_line(line)
            results.append(result)
        
        # Create results table
        self.send_table(
            headers=["Line", "Result"],
            rows=[[i+1, r] for i, r in enumerate(results[:100])],
            title=f"Processing Results (first 100/{total_lines} lines)"
        )
        
        # Create result entity
        result_entity = self.create_entity(
            entity_id=f"result_{file_entity.id}",
            entity_type="processing_result",
            labels=["Result"],
            properties={
                "lines_processed": total_lines,
                "operation": operation
            }
        )
        
        self.link_entities(file_entity.id, result_entity.id, "HAS_RESULT")
        
        self.send_alert("Processing completed", "success")
        
        yield ToolResult(
            success=True,
            output={
                "file": path,
                "lines": total_lines,
                "results": results
            },
            output_type=OutputType.JSON
        )
```

---

## 11. Migration Guide

### 11.1 Converting Existing Tools

#### Before (Old Style)

```python
def old_tool_function(query: str) -> str:
    """Old style tool"""
    results = do_search(query)
    
    # Manual memory storage
    agent.mem.upsert_entity(
        f"search_{query}",
        "search",
        properties={"query": query}
    )
    
    return json.dumps(results)

# In ToolLoader
tool_list.append(
    StructuredTool.from_function(
        func=old_tool_function,
        name="old_tool",
        description="Does search"
    )
)
```

#### After (VTool Style)

```python
class SearchToolInput(BaseModel):
    query: str = Field(description="Search query")

class SearchTool(VTool):
    """New style tool with automatic memory"""
    
    def get_input_schema(self):
        return SearchToolInput
    
    def get_output_type(self):
        return OutputType.SEARCH_RESULTS
    
    def _execute(self, query: str) -> Iterator:
        yield "Searching...\n"
        
        results = do_search(query)
        
        # Automatic memory - entity created and linked
        for idx, result in enumerate(results):
            entity = self.create_entity(
                f"result_{idx}",
                "search_result",
                properties=result
            )
            yield f"Found: {result['title']}\n"
        
        yield ToolResult(
            success=True,
            output=results,
            output_type=OutputType.SEARCH_RESULTS
        )

# In ToolLoader
from tool_framework import vtool_to_langchain

tool_list.append(vtool_to_langchain(SearchTool(agent)))
```

### 11.2 Adding UI to Existing VTools

```python
# Change base class from VTool to UITool
class SearchTool(UITool):  # Changed from VTool
    
    def _execute(self, query: str):
        # Add UI updates
        self.send_alert(f"Searching for: {query}", "info")
        self.send_progress(0, 100, "Starting search")
        
        results = do_search(query)
        
        # Send results as table
        self.send_table(
            headers=["Title", "URL"],
            rows=[[r["title"], r["url"]] for r in results],
            title="Search Results"
        )
        
        # Rest of existing code...
```

### 11.3 Migration Checklist

- [ ] Convert function-based tools to VTool classes
- [ ] Define Pydantic input schemas
- [ ] Declare output types
- [ ] Replace manual memory operations with `create_entity()`
- [ ] Replace string returns with `yield ToolResult(...)`
- [ ] Add progress updates with `yield` statements
- [ ] (Optional) Upgrade to UITool for UI features
- [ ] (Optional) Add event broadcasting
- [ ] Update ToolLoader to use `vtool_to_langchain()`
- [ ] Test execution and memory storage
- [ ] Verify WebSocket communication (if using UI)

---

## 12. API Reference

### 12.1 Class Hierarchy

```
VTool (ABC, Generic[T])
  ├─ UITool
  │   ├─ NetworkScannerTool
  │   ├─ CodeExecutionTool
  │   └─ ... (your UI tools)
  └─ ... (your basic tools)
```

### 12.2 VTool Methods

| Method | Type | Description |
|--------|------|-------------|
| `__init__(agent)` | Constructor | Initialize with agent |
| `get_input_schema()` | Abstract | Return Pydantic input schema |
| `get_output_type()` | Abstract | Return OutputType |
| `_execute(**kwargs)` | Abstract | Execute tool logic (yields) |
| `execute(**kwargs)` | Public | Main execution wrapper |
| `create_entity(...)` | Public | Create/track entity |
| `link_entities(...)` | Public | Create relationship |
| `format_output(data)` | Public | Format output |
| `get_description()` | Public | Get tool description |

### 12.3 UITool Additional Methods

| Method | Description |
|--------|-------------|
| `send_ui_component(component, type)` | Send UI component |
| `send_progress(current, total, msg)` | Send progress bar |
| `send_table(headers, rows, title)` | Send table |
| `send_entity_card(entity)` | Send entity card |
| `send_graph_update(nodes, edges, layout)` | Send graph viz |
| `send_network_topology(topology)` | Send network map |
| `send_alert(message, severity)` | Send alert |
| `send_metrics(metrics)` | Send metrics |
| `broadcast_event(event)` | Broadcast event |
| `visualize_subgraph(ids, depth)` | Visualize graph |

### 12.4 Data Classes

#### ToolResult

```python
@dataclass
class ToolResult:
    success: bool
    output: Any
    output_type: OutputType
    entities: List[ToolEntity] = field(default_factory=list)
    relationships: List[ToolRelationship] = field(default_factory=list)
    tool_name: str = ""
    execution_time: float = 0.0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    intermediate_results: Dict[str, Any] = field(default_factory=dict)
```

#### ToolEntity

```python
@dataclass
class ToolEntity:
    id: str
    type: str
    labels: List[str] = field(default_factory=list)
    properties: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
```

#### ToolRelationship

```python
@dataclass
class ToolRelationship:
    source_id: str
    target_id: str
    rel_type: str
    properties: Dict[str, Any] = field(default_factory=dict)
```

#### GraphEvent

```python
@dataclass
class GraphEvent:
    event_type: GraphEventType
    data: Dict[str, Any]
    timestamp: float
    event_id: str
    tool_name: str = ""
    session_id: str = ""
```

#### UIComponent

```python
@dataclass
class UIComponent:
    component_type: UIComponentType
    data: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    component_id: str = field(default_factory=lambda: str(uuid.uuid4()))
```

### 12.5 Enums

#### OutputType

```python
class OutputType(str, Enum):
    TEXT = "text"
    JSON = "json"
    IP_LIST = "ip_list"
    PORT_LIST = "port_list"
    SERVICE_LIST = "service_list"
    VULNERABILITY_LIST = "vulnerability_list"
    FILE_PATH = "file_path"
    URL = "url"
    ENTITY_ID = "entity_id"
    SUBGRAPH = "subgraph"
    SEARCH_RESULTS = "search_results"
    CODE = "code"
    COMMAND_OUTPUT = "command_output"
```

#### GraphEventType

```python
class GraphEventType(str, Enum):
    ENTITY_CREATED = "entity_created"
    ENTITY_UPDATED = "entity_updated"
    RELATIONSHIP_CREATED = "relationship_created"
    EXECUTION_STARTED = "execution_started"
    EXECUTION_PROGRESS = "execution_progress"
    EXECUTION_COMPLETED = "execution_completed"
    EXECUTION_FAILED = "execution_failed"
    DATA_DISCOVERED = "data_discovered"
```

#### UIComponentType

```python
class UIComponentType(str, Enum):
    TEXT = "text"
    TABLE = "table"
    GRAPH = "graph"
    PROGRESS = "progress"
    ENTITY_CARD = "entity_card"
    RELATIONSHIP_GRAPH = "relationship_graph"
    CODE_BLOCK = "code_block"
    ALERT = "alert"
    METRICS = "metrics"
    TIMELINE = "timeline"
    NETWORK_TOPOLOGY = "network_topology"
```

---

## 13. Best Practices

### 13.1 Tool Design

#### Do's

✅ **Keep tools focused** - One tool = one clear purpose  
✅ **Use descriptive entity IDs** - `ip_192_168_1_1` not `entity_1234`  
✅ **Yield progress frequently** - Every major step  
✅ **Reuse entities when possible** - Set `reuse_if_exists=True`  
✅ **Add rich properties** - More context = better queries  
✅ **Document your schemas** - Clear field descriptions  
✅ **Handle errors gracefully** - Always return ToolResult  
✅ **Test memory creation** - Verify entities in Neo4j  

#### Don'ts

❌ **Don't create duplicate entities** - Check/reuse first  
❌ **Don't forget final ToolResult** - Must yield it  
❌ **Don't block on I/O** - Use async where possible  
❌ **Don't ignore errors** - Wrap in try/except  
❌ **Don't hardcode values** - Use input schema  
❌ **Don't skip progress updates** - Users want feedback  
❌ **Don't create orphan entities** - Link to execution  

### 13.2 Memory Management

```python
# Good - Descriptive, hierarchical
entity = self.create_entity(
    entity_id=f"ip_{ip.replace('.', '_')}",
    entity_type="network_host",
    labels=["NetworkHost", "IP", "Device"],
    properties={
        "ip_address": ip,
        "hostname": hostname,
        "status": "up",
        "discovered_at": datetime.now().isoformat(),
        "scan_method": "ping"
    }
)

# Bad - Generic, no context
entity = self.create_entity(
    "entity_123",
    "thing",
    properties={"value": ip}
)
```

### 13.3 UI Updates

```python
# Good - Progressive disclosure
self.send_alert("Starting scan", "info")
self.send_progress(0, 100, "Initializing")

for i in range(100):
    # Update every 10%
    if i % 10 == 0:
        self.send_progress(i, 100, f"Processing {i}%")
    
    # Send discoveries immediately
    entity = self.create_entity(...)
    # Entity card sent automatically

self.send_table(...)  # Summary at end
self.send_metrics(...)  # Final stats

# Bad - No updates until end
results = []
for i in range(100):
    results.append(process(i))

yield json.dumps(results)  # User sees nothing until done
```

### 13.4 Error Handling

```python
# Good - Comprehensive error handling
def _execute(self, target: str):
    try:
        # Validate input
        if not validate_target(target):
            self.send_alert(f"Invalid target: {target}", "error")
            yield ToolResult(
                success=False,
                output={},
                output_type=self.get_output_type(),
                error="Invalid input"
            )
            return
        
        # Do work with progress
        try:
            results = process_target(target)
        except NetworkError as e:
            self.send_alert(f"Network error: {str(e)}", "error")
            yield ToolResult(
                success=False,
                output={},
                output_type=self.get_output_type(),
                error=str(e)
            )
            return
        
        # Success
        yield ToolResult(
            success=True,
            output=results,
            output_type=self.get_output_type()
        )
    
    except Exception as e:
        # Catch-all
        self.send_alert(f"Unexpected error: {str(e)}", "error")
        yield ToolResult(
            success=False,
            output={},
            output_type=self.get_output_type(),
            error=str(e)
        )
```

### 13.5 Performance Tips

1. **Batch entity creation** - Create entities as discovered, don't wait
2. **Use async for I/O** - Network calls, file operations
3. **Limit graph depth** - Don't query depth > 3
4. **Cache lookups** - Store `self.discovered_entities = {}`
5. **Throttle UI updates** - Not every iteration, every N%
6. **Stream large results** - Don't load all in memory
7. **Use connection pooling** - For Neo4j, HTTP clients

### 13.6 Testing Tools

```python
# test_my_tool.py
import pytest
from unittest.mock import Mock
from my_tool import MyTool

@pytest.fixture
def mock_agent():
    agent = Mock()
    agent.mem = Mock()
    agent.sess = Mock(id="test_session")
    agent.event_broadcaster = Mock()
    return agent

def test_tool_execution(mock_agent):
    tool = MyTool(mock_agent)
    
    # Collect results
    results = []
    final_result = None
    
    for item in tool.execute(target="test"):
        if isinstance(item, ToolResult):
            final_result = item
        else:
            results.append(item)
    
    # Verify
    assert final_result is not None
    assert final_result.success
    assert len(final_result.entities) > 0
    assert len(results) > 0  # Progress messages

def test_entity_reuse(mock_agent):
    tool = MyTool(mock_agent)
    
    # Mock existing entity
    mock_agent.mem.extract_subgraph.return_value = {
        "nodes": [{"id": "test_entity"}]
    }
    
    entity = tool.create_entity(
        "test_entity",
        "test_type",
        reuse_if_exists=True
    )
    
    assert entity.metadata.get("reused") == True
```

---

## 14. Troubleshooting

### 14.1 Common Issues

#### Tool doesn't yield final ToolResult

**Symptom:** Tool executes but no result stored  
**Cause:** Missing `yield ToolResult(...)`  
**Fix:**
```python
def _execute(self, ...):
    # ... work ...
    
    # Add this at the end:
    yield ToolResult(
        success=True,
        output=results,
        output_type=self.get_output_type()
    )
```

#### Entities not appearing in Neo4j

**Symptom:** No entities created  
**Cause:** Not calling `create_entity()` or execution failed  
**Fix:**
```python
# Verify entities are being created
entity = self.create_entity(...)
print(f"Created entity: {entity.id}")

# Check execution completed
assert final_result.success
assert len(final_result.entities) > 0
```

#### WebSocket not receiving events

**Symptom:** No real-time updates in UI  
**Cause:** WebSocket not connected or broadcaster not initialized  
**Fix:**
```python
# Verify broadcaster exists
if not hasattr(agent, 'event_broadcaster'):
    from tool_framework import integrate_ui_tools
    integrate_ui_tools(agent)

# Verify WebSocket endpoint
# Check browser console for connection errors
```

#### UI components not rendering

**Symptom:** No visual updates  
**Cause:** Component type not registered or data format wrong  
**Fix:**
```typescript
// Verify component registered
const ComponentRegistry = {
  table: TableComponent,
  // ... must include your component_type
};

// Check data format matches component expectations
```

#### Duplicate entities created

**Symptom:** Multiple entities with same ID  
**Cause:** `reuse_if_exists=False` or different entity IDs  
**Fix:**
```python
# Always use consistent IDs
entity_id = f"ip_{ip.replace('.', '_')}"

# Enable reuse
entity = self.create_entity(
    entity_id,
    "network_host",
    reuse_if_exists=True  # Default is True
)
```

### 14.2 Debug Techniques

#### Enable verbose logging

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class MyTool(VTool):
    def _execute(self, ...):
        logger.debug(f"Starting execution with inputs: {kwargs}")
        
        entity = self.create_entity(...)
        logger.debug(f"Created entity: {entity.id}, reused={entity.metadata.get('reused')}")
```

#### Inspect graph structure

```cypher
// Get all entities from execution
MATCH (exec:Execution {id: $execution_id})
OPTIONAL MATCH (exec)-[r*1..3]->(node)
RETURN exec, r, node

// Check for duplicates
MATCH (n)
WITH n.id as id, count(*) as count
WHERE count > 1
RETURN id, count

// Find orphan entities (not linked to execution)
MATCH (n)
WHERE NOT (n)<-[:CREATED]-(:Execution)
  AND NOT (n:Session)
RETURN n
LIMIT 10
```

#### Monitor WebSocket

```javascript
// In browser console
const ws = new WebSocket('ws://localhost:8000/ws/tools/session_id');

ws.onmessage = (event) => {
  console.log('Received:', JSON.parse(event.data));
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};
```

#### Test tool standalone

```python
# test_standalone.py
from my_tool import MyTool

# Create mock agent
class MockAgent:
    def __init__(self):
        from Memory.memory import HybridMemory
        from Session.session import Session
        from tool_framework import EventBroadcaster
        
        self.mem = HybridMemory()
        self.sess = Session()
        self.event_broadcaster = EventBroadcaster()

agent = MockAgent()
tool = MyTool(agent)

# Execute
for item in tool.execute(target="test"):
    print(item)
```

### 14.3 Performance Optimization

#### Slow entity creation

```python
# Batch create if possible
entities = []
for item in items:
    entity = self.create_entity(...)
    entities.append(entity)
    
    # Don't query graph for each one
    # Let framework handle at finalize

# Or cache checks
self.entity_cache = {}

def create_cached_entity(self, entity_id, ...):
    if entity_id in self.entity_cache:
        return self.entity_cache[entity_id]
    
    entity = self.create_entity(entity_id, ...)
    self.entity_cache[entity_id] = entity
    return entity
```

#### Too many UI updates

```python
# Throttle updates
update_interval = 10  # Update every 10 items

for idx, item in enumerate(items):
    process(item)
    
    # Only update UI periodically
    if idx % update_interval == 0:
        self.send_progress(idx, len(items))
```

#### Large graph queries

```python
# Limit depth
subgraph = self.mem.extract_subgraph(ids, depth=1)  # Not 3+

# Limit results
results = self.mem.semantic_retrieve(query, k=10)  # Not 100

# Use focused queries
# Instead of getting all related:
# MATCH (n)-[*1..5]-(m) RETURN n, m  # BAD
# Use specific paths:
# MATCH (n)-[:SPECIFIC_REL]->(m) RETURN n, m  # GOOD
```

---

## Appendices

### A. Quick Reference Card

```python
# Minimal Tool
class MyTool(VTool):
    def get_input_schema(self):
        class Input(BaseModel):
            target: str = Field(description="Target")
        return Input
    
    def get_output_type(self):
        return OutputType.TEXT
    
    def _execute(self, target: str):
        entity = self.create_entity("id", "type", properties={})
        yield "Progress...\n"
        yield ToolResult(success=True, output="done", output_type=OutputType.TEXT)

# UI Tool
class MyUITool(UITool):
    def _execute(self, target: str):
        self.send_alert("Starting", "info")
        self.send_progress(1, 10, "Processing")
        self.send_table(headers=["A", "B"], rows=[[1, 2]])
        yield ToolResult(success=True, output={}, output_type=OutputType.JSON)

# Integration
from tool_framework import vtool_to_langchain
tool_list.append(vtool_to_langchain(MyTool(agent)))
```

### B. File Structure

```
Vera/
├── tool_framework.py           # Core VTool framework
├── tool_ui_framework.py        # UITool extensions
├── Toolchain/
│   ├── tools.py               # ToolLoader
│   └── Tools/
│       ├── my_tool.py         # Your tools
│       └── ...
├── ChatUI/
│   ├── api/
│   │   └── session.py         # WebSocket endpoints
│   └── frontend/
│       └── src/
│           ├── components/
│           │   ├── ToolUI.tsx
│           │   └── ...
│           └── hooks/
│               └── useWebSocket.ts
└── Memory/
    └── memory.py              # HybridMemory
```

### C. Version History

- **v1.0** (Dec 2024) - Initial release
  - VTool base class
  - UITool extensions
  - WebSocket integration
  - React components
  - Complete documentation

### D. Contributing

To add features to the framework:

1. **Core features** → `tool_framework.py`
2. **UI features** → `tool_ui_framework.py`
3. **Frontend components** → `ChatUI/frontend/src/components/`
4. **Update docs** → This document
5. **Add examples** → Section 10
6. **Add tests** → `tests/test_tool_framework.py`

### E. License & Credits

Built for the Vera AI system.  
MIT License (or your preferred license).

---

## Summary

The Vera Tool Framework provides:

1. **Standardized tool development** with VTool base class
2. **Automatic memory management** with entity tracking
3. **Real-time UI communication** via WebSockets
4. **Event broadcasting** for graph changes
5. **Type-based interoperability** for tool chaining
6. **Progressive disclosure** with streaming updates
7. **Entity reuse** across multiple executions
8. **Complete frontend integration** with React components

**Key Benefits:**

- 🚀 **Faster development** - Standard patterns, less boilerplate
- 🧠 **Better memory** - Automatic graph creation and linking
- 👁️ **Real-time visibility** - See tools working in real-time
- 🔗 **Composability** - Tools chain together naturally
- 📊 **Rich UI** - Tables, graphs, progress bars, entity cards
- 🏗️ **Production-ready** - Error handling, type safety, testing


# Vera Tool Framework Extension - Capability, Monitoring & Action Tools

**Complete Documentation**  
**Version:** 1.0  
**Last Updated:** December 2024

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture & Design Philosophy](#2-architecture--design-philosophy)
3. [CapabilityTool Class](#3-capabilitytool-class)
4. [MonitoringTool Class](#4-monitoringtool-class)
5. [ActionTool Class](#5-actiontool-class)
6. [Complete Examples](#6-complete-examples)
7. [Frontend Integration](#7-frontend-integration)
8. [API Reference](#8-api-reference)
9. [Integration Guide](#9-integration-guide)
10. [Best Practices](#10-best-practices)
11. [Troubleshooting](#11-troubleshooting)
12. [Use Cases & Patterns](#12-use-cases--patterns)

---

## 1. Overview

### 1.1 What Are Extended Tool Types?

The Vera Tool Framework extension introduces three new tool classes that complement the base `VTool` and `UITool` classes:

| Tool Class | Purpose | Lifecycle | Output |
|------------|---------|-----------|--------|
| **VTool/UITool** | Discovery & Processing | One-time execution | Creates entities |
| **CapabilityTool** | Add interactive features | Persistent capability | Enables interaction |
| **MonitoringTool** | Continuous observation | Long-running background | Streams metrics |
| **ActionTool** | Ad-hoc operations | Quick one-off | Ephemeral results |

### 1.2 Why These Tool Types?

#### The Problem

With the base framework, you could discover a network host and its open ports, but you couldn't:
- **Interact** with the discovered host (SSH, web interface)
- **Monitor** if the ports remain open over time
- **Execute** quick commands without creating a full execution graph

#### The Solution

```
Discovery Flow:
1. VTool discovers network host → Creates entity
2. CapabilityTool adds SSH capability → Enables terminal
3. MonitoringTool watches port status → Continuous metrics
4. ActionTool executes quick commands → Ad-hoc operations
```

### 1.3 Key Differences from Base Tools

| Aspect | VTool/UITool | CapabilityTool | MonitoringTool | ActionTool |
|--------|--------------|----------------|----------------|------------|
| **Creates entities** | Yes, always | Rarely | Sometimes | Optional |
| **Execution model** | One-time | Attachment | Continuous | One-off |
| **Result persistence** | Always | Configuration | Metrics stream | Optional |
| **UI interaction** | Progress updates | Interactive interface | Real-time dashboard | Quick display |
| **Typical duration** | Seconds-minutes | N/A (capability) | Hours-days | Seconds |

### 1.4 Relationship Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Discovery Phase                          │
│                                                              │
│  VTool/UITool                                               │
│  ├─ Scans network                                           │
│  ├─ Creates: ip_192_168_1_1 (NetworkHost)                  │
│  ├─ Creates: ip_192_168_1_1_port_22 (NetworkPort)          │
│  └─ Links: NetworkHost -[HAS_PORT]-> NetworkPort           │
│                                                              │
└───────────────────────┬────────────────────────────────────┘
                        │
┌───────────────────────┴────────────────────────────────────┐
│                  Capability Phase                           │
│                                                              │
│  CapabilityTool                                             │
│  ├─ Checks: Can attach SSH to ip_192_168_1_1?             │
│  ├─ Attaches: SSH_TERMINAL capability                      │
│  ├─ Updates: ip_192_168_1_1.capabilities += "ssh"         │
│  └─ Enables: Interactive terminal in UI                    │
│                                                              │
└───────────────────────┬────────────────────────────────────┘
                        │
┌───────────────────────┴────────────────────────────────────┐
│                  Monitoring Phase                           │
│                                                              │
│  MonitoringTool                                             │
│  ├─ Starts: Background monitoring job                      │
│  ├─ Checks: Port 22 status every 5s                        │
│  ├─ Streams: Metrics to UI dashboard                       │
│  └─ Alerts: On status changes                              │
│                                                              │
└───────────────────────┬────────────────────────────────────┘
                        │
┌───────────────────────┴────────────────────────────────────┐
│                    Action Phase                             │
│                                                              │
│  ActionTool                                                 │
│  ├─ Executes: "uptime" command on host                     │
│  ├─ Returns: Quick result                                  │
│  ├─ Optionally stores in graph                             │
│  └─ No persistent monitoring                               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Architecture & Design Philosophy

### 2.1 Design Principles

#### Separation of Concerns

```python
# WRONG - Mixing discovery and interaction
class NetworkScanTool(VTool):
    def _execute(self, target: str):
        # Discover host
        entity = self.create_entity(...)
        
        # DON'T DO THIS - Tool tries to also provide SSH
        ssh_client = paramiko.SSHClient()
        ssh_client.connect(...)  # Wrong place!

# RIGHT - Separate responsibilities
class NetworkScanTool(VTool):
    """Only discovers hosts"""
    def _execute(self, target: str):
        entity = self.create_entity(...)
        # That's it - just discovery

class SSHCapabilityTool(CapabilityTool):
    """Only provides SSH capability"""
    def attach_capability(self, entity_id: str):
        # Check entity exists from discovery
        # Add SSH capability
```

#### Progressive Enhancement

Tools build on each other:

```
Level 1: Discovery (VTool)
  ↓ Creates entities
Level 2: Capabilities (CapabilityTool)
  ↓ Adds interactive features
Level 3: Monitoring (MonitoringTool)
  ↓ Continuous observation
Level 4: Actions (ActionTool)
  ↓ Ad-hoc operations
```

#### Declarative Capabilities

Entities declare what they support:

```python
# Entity after discovery
{
  "id": "ip_192_168_1_1",
  "type": "network_host",
  "capabilities": []  # Empty
}

# Entity after capability attachment
{
  "id": "ip_192_168_1_1",
  "type": "network_host",
  "capabilities": ["ssh_terminal", "file_browser"]  # Available!
}
```

### 2.2 Execution Models

#### VTool: Synchronous Discovery

```python
for item in tool.execute(target="192.168.1.0/24"):
    # Progress updates
    # Final result
    # Done - tool exits
```

#### CapabilityTool: Capability Attachment

```python
capability = tool.attach_capability("ip_192_168_1_1", config)
# Capability attached - entity now has feature
# Tool can exit, capability persists
# User can interact via UI
```

#### MonitoringTool: Background Async Loop

```python
job = tool.start_monitoring("ip_192_168_1_1")
# Tool returns immediately
# Background task continues forever
# Streams metrics to UI
# tool.stop_monitoring(job.job_id) to stop
```

#### ActionTool: One-off Execution

```python
for item in tool.execute_action("ip_192_168_1_1", params):
    # Quick execution
    # Optional storage
    # Done - no persistence
```

### 2.3 State Management

```python
# VTool state
class MyVTool(VTool):
    def __init__(self, agent):
        super().__init__(agent)
        # State: Per-execution
        # Cleared after execute() completes

# CapabilityTool state
class MyCapabilityTool(CapabilityTool):
    def __init__(self, agent):
        super().__init__(agent)
        self.capabilities = {}  # Persistent across executions
        # State: Global capability registry

# MonitoringTool state
class MyMonitoringTool(MonitoringTool):
    def __init__(self, agent):
        super().__init__(agent)
        self.jobs = {}           # Active monitoring jobs
        self.monitoring_tasks = {} # Async tasks
        # State: Global job registry

# ActionTool state
class MyActionTool(ActionTool):
    def __init__(self, agent):
        super().__init__(agent)
        # State: Minimal, execution-scoped only
```

### 2.4 Memory Patterns

```cypher
// VTool creates this structure
(session:Session)-[:PERFORMED_SCAN]->(exec:Execution)
(exec)-[:CREATED]->(entity:NetworkHost)
(entity)-[:HAS_PORT]->(port:NetworkPort)

// CapabilityTool updates entity
(entity {capabilities: ["ssh_terminal"]})

// MonitoringTool creates job tracking
(entity)-[:MONITORED_BY]->(job:MonitoringJob)
(job {status: "active", frequency: "normal"})

// ActionTool optionally creates results
(entity)-[:EXECUTED_COMMAND]->(result:CommandResult)
(result {command: "uptime", output: "..."})
```

---

## 3. CapabilityTool Class

### 3.1 Concept & Purpose

**CapabilityTool** attaches interactive features to existing entities without re-discovering them.

#### Mental Model

Think of capabilities as "plugins" for entities:

```
Entity (Plain)          Entity (With Capabilities)
┌──────────┐           ┌──────────────────────────┐
│ IP: X.X  │    →      │ IP: X.X                  │
│ Port: 22 │           │ Port: 22                 │
└──────────┘           │ ┌────────────────────┐  │
                       │ │ [SSH Terminal]     │  │
                       │ │ [File Browser]     │  │
                       │ │ [Log Viewer]       │  │
                       │ └────────────────────┘  │
                       └──────────────────────────┘
```

#### When to Use CapabilityTool

✅ **Use when you want to:**
- Add interactive features to discovered entities
- Provide UI interfaces (terminals, browsers, dashboards)
- Enable user actions on entities
- Attach context-specific functionality
- Offer optional capabilities based on entity type

❌ **Don't use when you want to:**
- Discover new entities (use VTool)
- Monitor entities continuously (use MonitoringTool)
- Execute one-off commands (use ActionTool)
- Transform data (use VTool)

### 3.2 Class Structure

```python
class CapabilityTool(UITool):
    """Base class for capability attachment"""
    
    def __init__(self, agent):
        super().__init__(agent)
        self.capabilities: Dict[str, Capability] = {}
    
    # Required methods
    @abstractmethod
    def get_capability_type(self) -> CapabilityType:
        """Return capability type"""
    
    @abstractmethod
    def check_compatibility(self, entity_id: str) -> bool:
        """Check if entity supports this capability"""
    
    @abstractmethod
    def create_interface(self, entity_id: str, config: Dict) -> Any:
        """Create interface object (SSH client, etc.)"""
    
    # Provided methods
    def attach_capability(self, entity_id: str, config: Dict) -> Capability:
        """Attach capability to entity"""
    
    def get_capabilities_for_entity(self, entity_id: str) -> List[Capability]:
        """Get entity's capabilities"""
```

### 3.3 CapabilityType Enum

```python
class CapabilityType(str, Enum):
    """Predefined capability types"""
    SSH_TERMINAL = "ssh_terminal"        # SSH shell access
    WEB_TERMINAL = "web_terminal"        # Web-based terminal
    FILE_BROWSER = "file_browser"        # Browse filesystem
    LOG_VIEWER = "log_viewer"            # View log files
    SHELL_EXECUTOR = "shell_executor"    # Execute shell commands
    API_CLIENT = "api_client"            # API interaction
    DATABASE_CLIENT = "database_client"  # Database queries
    DEBUGGER = "debugger"                # Debug processes
    REPL = "repl"                        # Interactive REPL
    
    # Extend with custom types:
    # CapabilityType.CUSTOM = "custom"
```

### 3.4 Capability Data Structure

```python
@dataclass
class Capability:
    """A capability attached to an entity"""
    capability_type: CapabilityType     # Type of capability
    entity_id: str                      # Entity it's attached to
    config: Dict[str, Any]              # Configuration
    status: str                         # available, active, error
    metadata: Dict[str, Any]            # Additional data
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "capability_type": self.capability_type,
            "entity_id": self.entity_id,
            "config": self.config,
            "status": self.status,
            "metadata": self.metadata
        }
```

### 3.5 Creating a CapabilityTool

#### Example: File Browser Capability

```python
from tool_framework import CapabilityTool, Capability, CapabilityType
from pydantic import BaseModel, Field
from typing import Iterator, Dict, Any
import os

class FileBrowserInput(BaseModel):
    entity_id: str = Field(description="Host entity ID")
    base_path: str = Field(default="/", description="Starting directory")
    username: str = Field(description="SSH username")
    password: Optional[str] = Field(default=None)

class FileBrowserCapability(CapabilityTool):
    """
    Add file browser capability to network hosts.
    
    Allows browsing filesystem via SFTP over SSH.
    """
    
    def get_capability_type(self):
        return CapabilityType.FILE_BROWSER
    
    def get_input_schema(self):
        return FileBrowserInput
    
    def get_output_type(self):
        return OutputType.JSON
    
    def check_compatibility(self, entity_id: str) -> bool:
        """Check if entity has SSH access"""
        try:
            # Get entity
            subgraph = self.mem.extract_subgraph([entity_id], depth=1)
            entity = next((n for n in subgraph.get("nodes", []) 
                          if n.get("id") == entity_id), None)
            
            if not entity:
                return False
            
            # Must be a NetworkHost
            labels = entity.get("labels", [])
            if "NetworkHost" not in labels:
                return False
            
            # Check for port 22
            for rel in subgraph.get("rels", []):
                if rel and rel.get("start") == entity_id:
                    target = next((n for n in subgraph.get("nodes", [])
                                  if n.get("id") == rel.get("end")), None)
                    if target and "Port" in target.get("labels", []):
                        if target.get("properties", {}).get("port_number") == 22:
                            return True
            
            return False
        except:
            return False
    
    def create_interface(self, entity_id: str, config: Dict[str, Any]):
        """Create SFTP client for file browsing"""
        import paramiko
        
        # Get IP from entity
        subgraph = self.mem.extract_subgraph([entity_id], depth=0)
        entity = next((n for n in subgraph.get("nodes", [])
                      if n.get("id") == entity_id), None)
        
        ip = entity.get("properties", {}).get("ip_address")
        
        # Create SFTP connection
        transport = paramiko.Transport((ip, 22))
        transport.connect(
            username=config["username"],
            password=config.get("password")
        )
        
        sftp = paramiko.SFTPClient.from_transport(transport)
        
        return {
            "sftp": sftp,
            "transport": transport,
            "current_path": config.get("base_path", "/")
        }
    
    def _execute(self, entity_id: str, base_path: str = "/",
                 username: str = "", password: Optional[str] = None) -> Iterator:
        
        yield f"Attaching file browser to {entity_id}...\n"
        
        # Check compatibility
        if not self.check_compatibility(entity_id):
            self.send_alert(f"Entity {entity_id} not compatible", "error")
            yield ToolResult(
                success=False,
                output={},
                output_type=OutputType.JSON,
                error="Not compatible"
            )
            return
        
        # Attach capability
        config = {
            "username": username,
            "base_path": base_path
        }
        
        capability = self.attach_capability(entity_id, config)
        
        # Test connection and list directory
        try:
            interface = self.create_interface(entity_id, {
                "username": username,
                "password": password,
                "base_path": base_path
            })
            
            sftp = interface["sftp"]
            
            # List files in base directory
            files = sftp.listdir(base_path)
            
            # Send file browser UI component
            file_list = []
            for filename in files[:50]:  # Limit to 50
                filepath = os.path.join(base_path, filename)
                try:
                    stat = sftp.stat(filepath)
                    file_list.append({
                        "name": filename,
                        "path": filepath,
                        "size": stat.st_size,
                        "is_dir": stat.st_mode & 0o40000 != 0,
                        "modified": stat.st_mtime
                    })
                except:
                    file_list.append({
                        "name": filename,
                        "path": filepath
                    })
            
            # Send table of files
            self.send_table(
                headers=["Name", "Size", "Type"],
                rows=[
                    [
                        f["name"],
                        f.get("size", "?"),
                        "DIR" if f.get("is_dir") else "FILE"
                    ]
                    for f in file_list
                ],
                title=f"Files in {base_path}"
            )
            
            # Send file browser UI component
            self.send_ui_component(UIComponent(
                component_type=UIComponentType.TEXT,  # Or custom FILE_BROWSER
                data={
                    "entity_id": entity_id,
                    "capability": "file_browser",
                    "current_path": base_path,
                    "files": file_list,
                    "status": "connected"
                }
            ))
            
            sftp.close()
            interface["transport"].close()
            
            self.send_alert("File browser ready", "success")
            
            yield ToolResult(
                success=True,
                output={
                    "entity_id": entity_id,
                    "capability": capability.to_dict(),
                    "files_count": len(file_list),
                    "current_path": base_path
                },
                output_type=OutputType.JSON
            )
            
        except Exception as e:
            capability.status = "error"
            self.send_alert(f"Connection failed: {str(e)}", "error")
            
            yield ToolResult(
                success=False,
                output={},
                output_type=OutputType.JSON,
                error=str(e)
            )
```

### 3.6 Capability Lifecycle

```python
# 1. Check if capability can be attached
compatible = tool.check_compatibility("ip_192_168_1_1")

# 2. Attach capability
capability = tool.attach_capability("ip_192_168_1_1", {
    "username": "admin",
    "password": "secret"
})

# 3. Entity now has capability
# Graph: entity.capabilities = ["file_browser"]
# UI shows: [File Browser] button

# 4. User clicks button in UI
# Frontend calls: create_interface()
# Backend creates: SFTP client

# 5. User interacts
# Frontend sends: "list /var/log"
# Backend uses: SFTP client to list

# 6. Capability remains until removed
# Multiple users can use same capability
```

### 3.7 Best Practices for CapabilityTool

#### ✅ Do's

```python
# Store lightweight config only
config = {
    "username": "admin",
    "port": 22,
    "base_path": "/"
}
# NOT: config = {"password": "secret123"}  # Security risk

# Check compatibility thoroughly
def check_compatibility(self, entity_id: str):
    # Verify entity type
    # Check required ports/services
    # Validate access permissions
    return all_checks_pass

# Create interface lazily
def create_interface(self, entity_id: str, config: Dict):
    # Only create when needed (user activates)
    # Not during attach_capability()
    
# Clean up resources
def cleanup_interface(self, interface):
    if hasattr(interface, 'close'):
        interface.close()
```

#### ❌ Don'ts

```python
# Don't store sensitive data in capability
config = {"password": "secret"}  # BAD

# Don't create interface during attachment
def attach_capability(self, entity_id: str, config: Dict):
    ssh_client = paramiko.SSHClient()
    ssh_client.connect(...)  # BAD - Too early!

# Don't assume entity structure
def check_compatibility(self, entity_id: str):
    return True  # BAD - Always check properly

# Don't leak connections
def create_interface(self, entity_id: str, config: Dict):
    client = create_client()
    return client  # BAD - No cleanup mechanism
```

---

## 4. MonitoringTool Class

### 4.1 Concept & Purpose

**MonitoringTool** continuously observes entities and streams metrics over time.

#### Mental Model

```
Regular Tool:              Monitoring Tool:
─────────────              ────────────────────────────→
Execute once               Execute continuously
Return result              Stream metrics
Exit                       Run in background
                          Until stopped
```

#### When to Use MonitoringTool

✅ **Use when you want to:**
- Track entity status over time
- Detect changes and alert
- Collect time-series metrics
- Provide real-time dashboards
- Monitor health/availability
- Observe system behavior

❌ **Don't use when you want to:**
- One-time status check (use VTool)
- Interactive control (use CapabilityTool)
- Quick ad-hoc query (use ActionTool)

### 4.2 Class Structure

```python
class MonitoringTool(UITool):
    """Base class for monitoring tools"""
    
    def __init__(self, agent):
        super().__init__(agent)
        self.jobs: Dict[str, MonitoringJob] = {}
        self.monitoring_tasks: Dict[str, asyncio.Task] = {}
    
    # Required methods
    @abstractmethod
    def get_monitor_type(self) -> str:
        """Return monitor type identifier"""
    
    @abstractmethod
    async def check_entity(self, entity_id: str, config: Dict) -> Dict:
        """Perform single check - must be async"""
    
    # Provided methods
    def start_monitoring(
        self,
        entity_id: str,
        frequency: MonitoringFrequency,
        config: Optional[Dict] = None
    ) -> MonitoringJob:
        """Start background monitoring"""
    
    def stop_monitoring(self, job_id: str):
        """Stop monitoring job"""
    
    def list_monitoring_jobs(self, entity_id: Optional[str] = None) -> List[MonitoringJob]:
        """List active jobs"""
```

### 4.3 MonitoringFrequency Enum

```python
class MonitoringFrequency(str, Enum):
    REALTIME = "realtime"  # Every 0.1s - High load
    FAST = "fast"          # Every 1s
    NORMAL = "normal"      # Every 5s - Default
    SLOW = "slow"          # Every 30s
    CUSTOM = "custom"      # User-defined interval
    
# Interval mapping
INTERVALS = {
    MonitoringFrequency.REALTIME: 0.1,
    MonitoringFrequency.FAST: 1,
    MonitoringFrequency.NORMAL: 5,
    MonitoringFrequency.SLOW: 30,
}
```

### 4.4 MonitoringJob Data Structure

```python
@dataclass
class MonitoringJob:
    """Represents an active monitoring job"""
    job_id: str                        # Unique job identifier
    entity_id: str                     # Entity being monitored
    monitor_type: str                  # Type of monitoring
    frequency: MonitoringFrequency     # Check frequency
    config: Dict[str, Any]             # Monitor config
    started_at: float                  # Start timestamp
    last_check: Optional[float]        # Last check timestamp
    status: str                        # active, paused, stopped, error
    metrics: Dict[str, Any]            # Latest metrics
```

### 4.5 Creating a MonitoringTool

#### Example: Service Health Monitor

```python
from tool_framework import MonitoringTool, MonitoringJob, MonitoringFrequency
from pydantic import BaseModel, Field
import asyncio
import aiohttp

class ServiceHealthInput(BaseModel):
    entity_id: str = Field(description="Service entity ID")
    frequency: str = Field(default="normal", description="Check frequency")
    health_endpoint: str = Field(description="Health check URL")
    timeout: int = Field(default=5, description="Request timeout")
    alert_threshold: int = Field(default=3, description="Consecutive failures before alert")

class ServiceHealthMonitor(MonitoringTool):
    """
    Monitor service health by checking HTTP endpoint.
    
    Tracks:
    - Response time
    - Status codes
    - Uptime percentage
    - Alerts on failures
    """
    
    def get_monitor_type(self):
        return "service_health"
    
    def get_input_schema(self):
        return ServiceHealthInput
    
    def get_output_type(self):
        return OutputType.JSON
    
    async def check_entity(self, entity_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Perform health check"""
        
        health_endpoint = config["health_endpoint"]
        timeout = config.get("timeout", 5)
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    health_endpoint,
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    response_time = asyncio.get_event_loop().time() - start_time
                    
                    result = {
                        "status": "healthy" if response.status == 200 else "unhealthy",
                        "status_code": response.status,
                        "response_time": response_time,
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    # Track consecutive failures
                    if response.status != 200:
                        config["consecutive_failures"] = config.get("consecutive_failures", 0) + 1
                    else:
                        config["consecutive_failures"] = 0
                    
                    # Alert if threshold exceeded
                    alert_threshold = config.get("alert_threshold", 3)
                    if config["consecutive_failures"] >= alert_threshold:
                        result["alert"] = {
                            "message": f"Service unhealthy: {config['consecutive_failures']} consecutive failures",
                            "severity": "error"
                        }
                    
                    return result
                    
        except asyncio.TimeoutError:
            config["consecutive_failures"] = config.get("consecutive_failures", 0) + 1
            
            result = {
                "status": "timeout",
                "response_time": timeout,
                "timestamp": datetime.now().isoformat()
            }
            
            if config["consecutive_failures"] >= config.get("alert_threshold", 3):
                result["alert"] = {
                    "message": f"Service timeout: {config['consecutive_failures']} consecutive timeouts",
                    "severity": "error"
                }
            
            return result
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def _execute(self, entity_id: str, frequency: str = "normal",
                 health_endpoint: str = "", timeout: int = 5,
                 alert_threshold: int = 3) -> Iterator:
        
        yield f"Starting health monitoring for {entity_id}...\n"
        
        # Convert frequency string to enum
        freq_map = {
            "realtime": MonitoringFrequency.REALTIME,
            "fast": MonitoringFrequency.FAST,
            "normal": MonitoringFrequency.NORMAL,
            "slow": MonitoringFrequency.SLOW
        }
        
        freq = freq_map.get(frequency, MonitoringFrequency.NORMAL)
        
        # Start monitoring
        job = self.start_monitoring(
            entity_id,
            frequency=freq,
            config={
                "health_endpoint": health_endpoint,
                "timeout": timeout,
                "alert_threshold": alert_threshold,
                "consecutive_failures": 0
            }
        )
        
        # Send initial UI
        self.send_ui_component(UIComponent(
            component_type=UIComponentType.METRICS,
            data={
                "job_id": job.job_id,
                "entity_id": entity_id,
                "monitor_type": "service_health",
                "frequency": frequency,
                "status": "active"
            }
        ))
        
        yield f"Monitoring job started: {job.job_id}\n"
        yield f"Frequency: {frequency} ({INTERVALS[freq]}s)\n"
        yield f"Health endpoint: {health_endpoint}\n"
        
        yield ToolResult(
            success=True,
            output={
                "job_id": job.job_id,
                "entity_id": entity_id,
                "frequency": frequency,
                "status": "active"
            },
            output_type=OutputType.JSON,
            metadata={"job_id": job.job_id}
        )
```

### 4.6 Monitoring Lifecycle

```python
# 1. Start monitoring
job = tool.start_monitoring(
    "service_api",
    frequency=MonitoringFrequency.NORMAL,
    config={"health_endpoint": "https://api.example.com/health"}
)

# 2. Background loop begins
# Every 5s:
#   - Calls check_entity()
#   - Gets metrics
#   - Broadcasts to WebSocket
#   - Updates UI dashboard
#   - Checks for alerts

# 3. Metrics stream to UI
# WebSocket receives:
# {
#   "event_type": "execution_progress",
#   "data": {
#     "job_id": "...",
#     "metrics": {
#       "status": "healthy",
#       "response_time": 0.145
#     }
#   }
# }

# 4. Alert triggered
# If consecutive failures >= threshold:
#   - Sends alert event
#   - UI shows notification
#   - Can trigger actions

# 5. Stop monitoring
tool.stop_monitoring(job.job_id)
# Background task cancelled
# Job status = "stopped"
```

### 4.7 Best Practices for MonitoringTool

#### ✅ Do's

```python
# Use async for I/O operations
async def check_entity(self, entity_id: str, config: Dict):
    async with aiohttp.ClientSession() as session:
        # Async HTTP request
        pass

# Handle errors gracefully
async def check_entity(self, entity_id: str, config: Dict):
    try:
        # Check logic
        pass
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

# Store minimal state in config
config = {
    "consecutive_failures": 0,
    "last_alert": None
}

# Broadcast structured metrics
return {
    "status": "healthy",
    "response_time": 0.123,
    "memory_usage": 45.2,
    "timestamp": "2024-12-28T10:00:00"
}

# Provide stop mechanism
def cleanup(self):
    for job_id in list(self.jobs.keys()):
        self.stop_monitoring(job_id)
```

#### ❌ Don'ts

```python
# Don't use blocking I/O
def check_entity(self, entity_id: str, config: Dict):
    response = requests.get(url)  # BAD - Blocks event loop

# Don't ignore errors
async def check_entity(self, entity_id: str, config: Dict):
    result = await some_check()  # BAD - No try/except

# Don't create new connections every check
async def check_entity(self, entity_id: str, config: Dict):
    client = create_client()  # BAD - Connection overhead
    # Better: Store client in config or class

# Don't store large data in job
config = {
    "history": [...]  # BAD - Unbounded growth
}

# Don't forget cleanup
# Always provide stop_monitoring()
# Always cancel async tasks
```

---

## 5. ActionTool Class

### 5.1 Concept & Purpose

**ActionTool** performs quick, ad-hoc operations on entities without creating persistent monitoring or complex graph structures.

#### Mental Model

```
VTool:                    ActionTool:
──────                    ───────────
Structured execution      Quick operation
Creates entities          Optionally stores
Full graph tracking       Minimal tracking
Comprehensive result      Fast result
```

#### When to Use ActionTool

✅ **Use when you want to:**
- Execute quick commands
- Fetch current data
- Perform one-off operations
- Test entity functionality
- Run diagnostic commands
- Get instant feedback

❌ **Don't use when you want to:**
- Discover entities systematically (use VTool)
- Monitor continuously (use MonitoringTool)
- Provide interactive interface (use CapabilityTool)

### 5.2 Class Structure

```python
class ActionTool(UITool):
    """Base class for ad-hoc action tools"""
    
    # Required methods
    @abstractmethod
    def get_action_type(self) -> str:
        """Return action type identifier"""
    
    @abstractmethod
    def validate_action(self, entity_id: str, action_params: Dict) -> bool:
        """Check if action can be performed"""
    
    # Provided methods
    def execute_action(
        self,
        entity_id: str,
        action_params: Dict[str, Any],
        store_result: bool = False
    ) -> Iterator[Union[str, ToolResult]]:
        """Execute ad-hoc action"""
```

### 5.3 Creating an ActionTool

#### Example: Quick Data Fetch

```python
from tool_framework import ActionTool, ToolResult, OutputType
from pydantic import BaseModel, Field
import requests

class FetchAPIDataInput(BaseModel):
    entity_id: str = Field(description="API service entity ID")
    endpoint: str = Field(description="API endpoint to fetch")
    method: str = Field(default="GET", description="HTTP method")
    headers: Optional[Dict[str, str]] = Field(default=None)
    store_result: bool = Field(default=False, description="Store in graph")

class FetchAPIDataAction(ActionTool):
    """
    Quickly fetch data from API endpoint.
    
    Fast, one-off data retrieval without full discovery.
    """
    
    def get_action_type(self):
        return "fetch_api_data"
    
    def get_input_schema(self):
        return FetchAPIDataInput
    
    def get_output_type(self):
        return OutputType.JSON
    
    def validate_action(self, entity_id: str, action_params: Dict[str, Any]) -> bool:
        """Check if entity is an API service"""
        try:
            subgraph = self.mem.extract_subgraph([entity_id], depth=0)
            entity = next((n for n in subgraph.get("nodes", [])
                          if n.get("id") == entity_id), None)
            
            if not entity:
                return False
            
            # Check if it's an API service
            entity_type = entity.get("properties", {}).get("type")
            labels = entity.get("labels", [])
            
            return entity_type == "api_service" or "API" in labels
            
        except:
            return False
    
    def _execute(self, entity_id: str, endpoint: str, method: str = "GET",
                 headers: Optional[Dict] = None, store_result: bool = False) -> Iterator:
        
        self.send_alert(f"Fetching data from {endpoint}", "info")
        
        # Get base URL from entity
        subgraph = self.mem.extract_subgraph([entity_id], depth=0)
        entity = next((n for n in subgraph.get("nodes", [])
                      if n.get("id") == entity_id), None)
        
        base_url = entity.get("properties", {}).get("base_url", "")
        full_url = f"{base_url}{endpoint}"
        
        yield f"Fetching: {method} {full_url}\n"
        
        # Show request in UI
        self.send_ui_component(UIComponent(
            component_type=UIComponentType.CODE_BLOCK,
            data={
                "code": f"{method} {full_url}",
                "language": "http",
                "status": "executing"
            }
        ))
        
        try:
            # Make request
            response = requests.request(
                method,
                full_url,
                headers=headers or {},
                timeout=10
            )
            
            # Parse response
            try:
                data = response.json()
            except:
                data = {"text": response.text}
            
            # Update UI with response
            self.send_ui_component(UIComponent(
                component_type=UIComponentType.CODE_BLOCK,
                data={
                    "code": f"{method} {full_url}",
                    "language": "http",
                    "output": json.dumps(data, indent=2),
                    "status": "success" if response.ok else "error",
                    "status_code": response.status_code
                }
            ), update_type="replace")
            
            # Send metrics
            self.send_metrics({
                "status_code": response.status_code,
                "response_time": response.elapsed.total_seconds(),
                "size": len(response.content)
            })
            
            # Optionally store result
            if store_result:
                result_entity = self.create_entity(
                    f"api_fetch_{hash(full_url) % 1000000}",
                    "api_response",
                    labels=["APIResponse"],
                    properties={
                        "url": full_url,
                        "method": method,
                        "status_code": response.status_code,
                        "data_preview": str(data)[:500]
                    }
                )
                
                self.link_entities(entity_id, result_entity.id, "FETCHED_FROM")
                
                yield f"Stored as: {result_entity.id}\n"
            
            self.send_alert("Data fetched successfully", "success")
            
            yield ToolResult(
                success=response.ok,
                output=data,
                output_type=OutputType.JSON,
                metadata={
                    "status_code": response.status_code,
                    "response_time": response.elapsed.total_seconds()
                }
            )
            
        except Exception as e:
            self.send_alert(f"Fetch failed: {str(e)}", "error")
            
            yield ToolResult(
                success=False,
                output={},
                output_type=OutputType.JSON,
                error=str(e)
            )
```

#### Example: Quick Diagnostic

```python
class DiagnosticInput(BaseModel):
    entity_id: str = Field(description="Network host entity ID")
    diagnostic_type: str = Field(description="Type: ping, traceroute, nslookup")
    target: Optional[str] = Field(default=None, description="Optional target")

class RunDiagnosticAction(ActionTool):
    """Run quick network diagnostics"""
    
    def get_action_type(self):
        return "run_diagnostic"
    
    def get_input_schema(self):
        return DiagnosticInput
    
    def get_output_type(self):
        return OutputType.COMMAND_OUTPUT
    
    def validate_action(self, entity_id: str, action_params: Dict) -> bool:
        # Any network entity can run diagnostics
        try:
            subgraph = self.mem.extract_subgraph([entity_id], depth=0)
            entity = next((n for n in subgraph.get("nodes", [])
                          if n.get("id") == entity_id), None)
            
            return entity and "NetworkHost" in entity.get("labels", [])
        except:
            return False
    
    def _execute(self, entity_id: str, diagnostic_type: str,
                 target: Optional[str] = None) -> Iterator:
        
        import subprocess
        
        # Get IP from entity
        subgraph = self.mem.extract_subgraph([entity_id], depth=0)
        entity = next((n for n in subgraph.get("nodes", [])
                      if n.get("id") == entity_id), None)
        
        ip = entity.get("properties", {}).get("ip_address")
        target = target or ip
        
        # Build command
        commands = {
            "ping": f"ping -c 4 {target}",
            "traceroute": f"traceroute {target}",
            "nslookup": f"nslookup {target}"
        }
        
        command = commands.get(diagnostic_type)
        if not command:
            yield ToolResult(
                success=False,
                output="",
                output_type=OutputType.COMMAND_OUTPUT,
                error=f"Unknown diagnostic type: {diagnostic_type}"
            )
            return
        
        self.send_alert(f"Running {diagnostic_type} on {target}", "info")
        
        yield f"Executing: {command}\n"
        
        # Show in UI
        self.send_ui_component(UIComponent(
            component_type=UIComponentType.CODE_BLOCK,
            data={
                "code": command,
                "language": "bash",
                "status": "executing"
            }
        ))
        
        try:
            # Execute
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Update UI
            self.send_ui_component(UIComponent(
                component_type=UIComponentType.CODE_BLOCK,
                data={
                    "code": command,
                    "language": "bash",
                    "output": result.stdout + result.stderr,
                    "status": "success" if result.returncode == 0 else "error",
                    "exit_code": result.returncode
                }
            ), update_type="replace")
            
            yield result.stdout
            if result.stderr:
                yield f"\nSTDERR:\n{result.stderr}"
            
            yield ToolResult(
                success=result.returncode == 0,
                output=result.stdout,
                output_type=OutputType.COMMAND_OUTPUT,
                metadata={"exit_code": result.returncode}
            )
            
        except Exception as e:
            yield ToolResult(
                success=False,
                output="",
                output_type=OutputType.COMMAND_OUTPUT,
                error=str(e)
            )
```

### 5.4 Action Patterns

#### Pattern 1: Quick Check

```python
# User wants to know: "Is this service responding?"
# Don't start full monitoring, just check once

class QuickHealthCheck(ActionTool):
    def _execute(self, entity_id: str) -> Iterator:
        response = requests.get(url, timeout=5)
        yield f"Status: {response.status_code}\n"
        yield ToolResult(success=response.ok, output={"status": response.status_code})
```

#### Pattern 2: Data Snapshot

```python
# User wants current state, not historical monitoring

class GetCurrentMetrics(ActionTool):
    def _execute(self, entity_id: str) -> Iterator:
        metrics = fetch_current_metrics(entity_id)
        self.send_metrics(metrics)
        yield ToolResult(success=True, output=metrics)
```

#### Pattern 3: Test Operation

```python
# User wants to test if something works

class TestConnection(ActionTool):
    def _execute(self, entity_id: str, test_params: Dict) -> Iterator:
        try:
            connection = create_connection(entity_id, test_params)
            yield "Connection successful\n"
            yield ToolResult(success=True, output={"connected": True})
        except Exception as e:
            yield f"Connection failed: {e}\n"
            yield ToolResult(success=False, output={}, error=str(e))
```

---

## 6. Complete Examples

### 6.1 Complete Network Administration Suite

```python
"""
Complete example: Network administration with all tool types.

Workflow:
1. VTool discovers hosts and ports
2. CapabilityTool adds SSH terminals
3. MonitoringTool watches port status
4. ActionTool executes quick commands
"""

from tool_framework import VTool, CapabilityTool, MonitoringTool, ActionTool

# 1. Discovery (VTool) - Already shown in main docs

# 2. SSH Capability
class SSHTerminalCapability(CapabilityTool):
    """Adds SSH terminal to hosts - Full implementation above"""
    pass

# 3. Port Monitoring
class PortStatusMonitor(MonitoringTool):
    """Monitors port availability - Full implementation above"""
    pass

# 4. Quick Command Execution
class SSHCommandAction(ActionTool):
    """Execute commands quickly - Full implementation above"""
    pass

# Integration in ToolLoader
def ToolLoader(agent):
    tool_list = []
    
    # Discovery
    add_vtools(tool_list, agent, [NetworkScanTool])
    
    # Capabilities
    add_capability_tools(tool_list, agent)
    
    # Monitoring
    add_monitoring_tools(tool_list, agent)
    
    # Actions
    add_action_tools(tool_list, agent)
    
    return tool_list
```

### 6.2 Complete Database Management Suite

```python
"""
Database management with all tool types.
"""

# 1. Discovery
class DatabaseDiscoveryTool(VTool):
    """Discover database servers"""
    
    def _execute(self, connection_string: str) -> Iterator:
        # Connect and discover schema
        db = connect(connection_string)
        
        # Create database entity
        db_entity = self.create_entity(
            f"db_{hash(connection_string)}",
            "database",
            labels=["Database", "PostgreSQL"],
            properties={
                "connection_string": "***",
                "version": db.version
            }
        )
        
        # Discover tables
        for table in db.tables:
            table_entity = self.create_entity(
                f"{db_entity.id}_table_{table.name}",
                "database_table",
                labels=["Table"],
                properties={
                    "name": table.name,
                    "row_count": table.count()
                }
            )
            
            self.link_entities(db_entity.id, table_entity.id, "HAS_TABLE")
        
        yield ToolResult(success=True, output={...})

# 2. Query Interface Capability
class DatabaseQueryCapability(CapabilityTool):
    """Adds SQL query interface"""
    
    def get_capability_type(self):
        return CapabilityType.DATABASE_CLIENT
    
    def check_compatibility(self, entity_id: str) -> bool:
        # Check if database entity
        subgraph = self.mem.extract_subgraph([entity_id], depth=0)
        entity = next((n for n in subgraph.get("nodes", [])
                      if n.get("id") == entity_id), None)
        return entity and "Database" in entity.get("labels", [])
    
    def create_interface(self, entity_id: str, config: Dict):
        # Create database connection
        return create_db_connection(config["connection_string"])
    
    def _execute(self, entity_id: str, connection_string: str) -> Iterator:
        capability = self.attach_capability(entity_id, {
            "connection_string": connection_string
        })
        
        # Send query interface UI
        self.send_ui_component(UIComponent(
            component_type=UIComponentType.TEXT,  # Or QUERY_INTERFACE
            data={
                "entity_id": entity_id,
                "capability": "database_client",
                "interface_type": "sql_query"
            }
        ))
        
        yield ToolResult(success=True, output={"capability": capability.to_dict()})

# 3. Performance Monitoring
class DatabasePerformanceMonitor(MonitoringTool):
    """Monitor database performance"""
    
    def get_monitor_type(self):
        return "database_performance"
    
    async def check_entity(self, entity_id: str, config: Dict) -> Dict:
        db = connect(config["connection_string"])
        
        metrics = {
            "active_connections": db.active_connections,
            "queries_per_second": db.qps,
            "cache_hit_ratio": db.cache_hit_ratio,
            "slow_queries": len(db.slow_queries()),
            "timestamp": datetime.now().isoformat()
        }
        
        # Alert on slow queries
        if metrics["slow_queries"] > config.get("slow_query_threshold", 10):
            metrics["alert"] = {
                "message": f"{metrics['slow_queries']} slow queries detected",
                "severity": "warning"
            }
        
        return metrics

# 4. Quick Query Action
class ExecuteQueryAction(ActionTool):
    """Execute SQL query quickly"""
    
    def get_action_type(self):
        return "execute_query"
    
    def validate_action(self, entity_id: str, action_params: Dict) -> bool:
        # Validate entity is database
        subgraph = self.mem.extract_subgraph([entity_id], depth=0)
        entity = next((n for n in subgraph.get("nodes", [])
                      if n.get("id") == entity_id), None)
        return entity and "Database" in entity.get("labels", [])
    
    def _execute(self, entity_id: str, query: str, 
                 connection_string: str, store_result: bool = False) -> Iterator:
        
        # Get connection
        db = connect(connection_string)
        
        # Show query
        self.send_ui_component(UIComponent(
            component_type=UIComponentType.CODE_BLOCK,
            data={
                "code": query,
                "language": "sql",
                "status": "executing"
            }
        ))
        
        try:
            # Execute
            result = db.execute(query)
            rows = result.fetchall()
            
            # Show results as table
            if rows:
                headers = [col[0] for col in result.description]
                self.send_table(headers, rows, title="Query Results")
            
            # Update UI
            self.send_ui_component(UIComponent(
                component_type=UIComponentType.CODE_BLOCK,
                data={
                    "code": query,
                    "language": "sql",
                    "output": f"{len(rows)} rows returned",
                    "status": "success"
                }
            ), update_type="replace")
            
            yield ToolResult(
                success=True,
                output={"rows": len(rows), "data": rows[:100]},
                output_type=OutputType.JSON
            )
            
        except Exception as e:
            yield ToolResult(success=False, output={}, error=str(e))
```

### 6.3 Complete API Management Suite

```python
"""
API management and testing with all tool types.
"""

# 1. Discovery
class APIDiscoveryTool(VTool):
    """Discover API endpoints from OpenAPI spec"""
    
    def _execute(self, openapi_url: str) -> Iterator:
        # Fetch OpenAPI spec
        spec = requests.get(openapi_url).json()
        
        # Create API entity
        api_entity = self.create_entity(
            f"api_{hash(spec['info']['title'])}",
            "api_service",
            labels=["API", "REST"],
            properties={
                "title": spec["info"]["title"],
                "version": spec["info"]["version"],
                "base_url": spec["servers"][0]["url"]
            }
        )
        
        # Discover endpoints
        for path, methods in spec["paths"].items():
            for method, details in methods.items():
                endpoint_entity = self.create_entity(
                    f"{api_entity.id}_endpoint_{hash(path+method)}",
                    "api_endpoint",
                    labels=["Endpoint"],
                    properties={
                        "path": path,
                        "method": method.upper(),
                        "summary": details.get("summary", "")
                    }
                )
                
                self.link_entities(api_entity.id, endpoint_entity.id, "HAS_ENDPOINT")
        
        yield ToolResult(success=True, output={...})

# 2. API Test Capability
class APITestingCapability(CapabilityTool):
    """Add API testing interface"""
    
    def get_capability_type(self):
        return CapabilityType.API_CLIENT
    
    # Full implementation similar to database example

# 3. API Monitoring
class APIHealthMonitor(MonitoringTool):
    """Monitor API health and performance"""
    
    # Similar to ServiceHealthMonitor shown earlier

# 4. Quick API Call
class CallAPIAction(ActionTool):
    """Make quick API call"""
    
    # Similar to FetchAPIDataAction shown earlier
```

---

## 7. Frontend Integration

### 7.1 Capability UI Components

```typescript
// CapabilityPanel.tsx - Shows available capabilities for an entity

interface CapabilityPanelProps {
  entity: Entity;
  capabilities: Capability[];
}

export const CapabilityPanel: React.FC<CapabilityPanelProps> = ({
  entity,
  capabilities
}) => {
  const [activeCapability, setActiveCapability] = useState<Capability | null>(null);
  
  const activateCapability = async (capability: Capability) => {
    // Call backend to create interface
    const response = await fetch('/api/capabilities/activate', {
      method: 'POST',
      body: JSON.stringify({
        entity_id: entity.id,
        capability_type: capability.capability_type,
        config: capability.config
      })
    });
    
    setActiveCapability(capability);
  };
  
  return (
    <div className="capability-panel">
      <h3>Capabilities for {entity.id}</h3>
      
      <div className="capability-buttons">
        {capabilities.map(cap => (
          <button
            key={cap.capability_type}
            onClick={() => activateCapability(cap)}
            className={`capability-btn ${cap.status}`}
            disabled={cap.status === 'error'}
          >
            <span className="icon">{getCapabilityIcon(cap.capability_type)}</span>
            <span className="label">{formatCapabilityName(cap.capability_type)}</span>
            {cap.status === 'active' && <span className="badge">Active</span>}
          </button>
        ))}
      </div>
      
      {activeCapability && (
        <CapabilityInterface capability={activeCapability} entity={entity} />
      )}
    </div>
  );
};

function getCapabilityIcon(type: string): string {
  const icons = {
    ssh_terminal: '💻',
    file_browser: '📁',
    database_client: '🗄️',
    api_client: '🔌',
    log_viewer: '📋',
  };
  return icons[type] || '🔧';
}
```

### 7.2 SSH Terminal Component

```typescript
// SSHTerminal.tsx - Interactive SSH terminal

interface SSHTerminalProps {
  entity_id: string;
  capability: Capability;
}

export const SSHTerminal: React.FC<SSHTerminalProps> = ({
  entity_id,
  capability
}) => {
  const [history, setHistory] = useState<string[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const terminalRef = useRef<HTMLDivElement>(null);
  
  const executeCommand = async (command: string) => {
    setLoading(true);
    
    // Add command to history
    setHistory(prev => [...prev, `$ ${command}`]);
    
    try {
      // Call ActionTool to execute command
      const response = await fetch('/api/tools/execute_command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          entity_id,
          command,
          username: capability.config.username,
          // Include auth from capability config
        })
      });
      
      const result = await response.json();
      
      // Add output to history
      if (result.success) {
        setHistory(prev => [...prev, result.output]);
      } else {
        setHistory(prev => [...prev, `Error: ${result.error}`]);
      }
    } catch (error) {
      setHistory(prev => [...prev, `Error: ${error}`]);
    } finally {
      setLoading(false);
      setInput('');
    }
  };
  
  useEffect(() => {
    // Auto-scroll to bottom
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [history]);
  
  return (
    <div className="ssh-terminal">
      <div className="terminal-header">
        <span className="title">SSH Terminal - {entity_id}</span>
        <button className="close-btn">×</button>
      </div>
      
      <div className="terminal-body" ref={terminalRef}>
        {history.map((line, i) => (
          <div key={i} className={line.startsWith('$') ? 'command' : 'output'}>
            {line}
          </div>
        ))}
        
        {loading && <div className="loading">Executing...</div>}
      </div>
      
      <div className="terminal-input">
        <span className="prompt">$</span>
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyPress={e => {
            if (e.key === 'Enter' && input.trim()) {
              executeCommand(input.trim());
            }
          }}
          placeholder="Enter command..."
          disabled={loading}
        />
      </div>
    </div>
  );
};
```

### 7.3 Monitoring Dashboard

```typescript
// MonitoringDashboard.tsx - Real-time monitoring display

interface MonitoringDashboardProps {
  sessionId: string;
}

export const MonitoringDashboard: React.FC<MonitoringDashboardProps> = ({
  sessionId
}) => {
  const [jobs, setJobs] = useState<MonitoringJob[]>([]);
  const [metrics, setMetrics] = useState<Map<string, any>>(new Map());
  const { lastMessage } = useWebSocket(`/ws/tools/${sessionId}`);
  
  // Load active jobs on mount
  useEffect(() => {
    loadActiveJobs();
  }, []);
  
  const loadActiveJobs = async () => {
    const response = await fetch(`/api/monitoring/jobs?session_id=${sessionId}`);
    const data = await response.json();
    setJobs(data.jobs);
  };
  
  // Handle WebSocket updates
  useEffect(() => {
    if (!lastMessage) return;
    
    try {
      const msg = JSON.parse(lastMessage.data);
      
      if (msg.type === 'tool_event' && 
          msg.event.event_type === 'execution_progress') {
        const data = msg.event.data;
        
        if (data.job_id && data.metrics) {
          setMetrics(prev => new Map(prev).set(data.job_id, data.metrics));
        }
      }
    } catch (error) {
      console.error('Failed to parse WebSocket message:', error);
    }
  }, [lastMessage]);
  
  const stopJob = async (jobId: string) => {
    await fetch(`/api/monitoring/jobs/${jobId}/stop`, { method: 'POST' });
    loadActiveJobs();
  };
  
  return (
    <div className="monitoring-dashboard">
      <div className="dashboard-header">
        <h2>Monitoring Dashboard</h2>
        <span className="job-count">{jobs.length} active jobs</span>
      </div>
      
      <div className="monitoring-grid">
        {jobs.map(job => {
          const jobMetrics = metrics.get(job.job_id);
          
          return (
            <div key={job.job_id} className="monitoring-card">
              <div className="card-header">
                <div className="entity-info">
                  <span className="entity-id">{job.entity_id}</span>
                  <span className="monitor-type">{job.monitor_type}</span>
                </div>
                <span className={`status-badge status-${job.status}`}>
                  {job.status}
                </span>
              </div>
              
              <div className="card-body">
                {jobMetrics && (
                  <>
                    <MetricsDisplay metrics={jobMetrics} />
                    
                    {jobMetrics.alert && (
                      <div className={`alert alert-${jobMetrics.alert.severity}`}>
                        {jobMetrics.alert.message}
                      </div>
                    )}
                  </>
                )}
                
                <div className="job-meta">
                  <span>Frequency: {job.frequency}</span>
                  <span>
                    Started: {new Date(job.started_at * 1000).toLocaleString()}
                  </span>
                  {job.last_check && (
                    <span>
                      Last check: {new Date(job.last_check * 1000).toLocaleString()}
                    </span>
                  )}
                </div>
              </div>
              
              <div className="card-footer">
                <button onClick={() => stopJob(job.job_id)} className="btn-stop">
                  Stop Monitoring
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

// Metrics display component
const MetricsDisplay: React.FC<{ metrics: any }> = ({ metrics }) => {
  return (
    <div className="metrics-grid">
      {Object.entries(metrics)
        .filter(([key]) => key !== 'alert' && key !== 'timestamp')
        .map(([key, value]) => (
          <div key={key} className="metric">
            <span className="metric-label">{formatMetricName(key)}</span>
            <span className="metric-value">{formatMetricValue(value)}</span>
          </div>
        ))}
    </div>
  );
};

function formatMetricName(key: string): string {
  return key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function formatMetricValue(value: any): string {
  if (typeof value === 'number') {
    return value.toFixed(2);
  }
  return String(value);
}
```

### 7.4 Quick Action Panel

```typescript
// QuickActionPanel.tsx - Execute ad-hoc actions

interface QuickActionPanelProps {
  entity: Entity;
  actions: ActionDefinition[];
}

interface ActionDefinition {
  action_type: string;
  name: string;
  description: string;
  inputs: InputField[];
}

export const QuickActionPanel: React.FC<QuickActionPanelProps> = ({
  entity,
  actions
}) => {
  const [selectedAction, setSelectedAction] = useState<ActionDefinition | null>(null);
  const [params, setParams] = useState<Record<string, any>>({});
  const [executing, setExecuting] = useState(false);
  const [result, setResult] = useState<any>(null);
  
  const executeAction = async () => {
    if (!selectedAction) return;
    
    setExecuting(true);
    setResult(null);
    
    try {
      const response = await fetch('/api/tools/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          entity_id: entity.id,
          action_type: selectedAction.action_type,
          params
        })
      });
      
      const data = await response.json();
      setResult(data);
    } catch (error) {
      setResult({ success: false, error: String(error) });
    } finally {
      setExecuting(false);
    }
  };
  
  return (
    <div className="quick-action-panel">
      <h3>Quick Actions</h3>
      
      <div className="action-selector">
        {actions.map(action => (
          <button
            key={action.action_type}
            onClick={() => {
              setSelectedAction(action);
              setParams({});
              setResult(null);
            }}
            className={selectedAction?.action_type === action.action_type ? 'active' : ''}
          >
            {action.name}
          </button>
        ))}
      </div>
      
      {selectedAction && (
        <div className="action-form">
          <h4>{selectedAction.name}</h4>
          <p className="description">{selectedAction.description}</p>
          
          <div className="inputs">
            {selectedAction.inputs.map(input => (
              <div key={input.name} className="input-group">
                <label>{input.label}</label>
                <input
                  type={input.type}
                  value={params[input.name] || ''}
                  onChange={e => setParams({
                    ...params,
                    [input.name]: e.target.value
                  })}
                  placeholder={input.placeholder}
                />
              </div>
            ))}
          </div>
          
          <button
            onClick={executeAction}
            disabled={executing}
            className="btn-execute"
          >
            {executing ? 'Executing...' : 'Execute'}
          </button>
        </div>
      )}
      
      {result && (
        <div className={`result ${result.success ? 'success' : 'error'}`}>
          <h4>Result</h4>
          {result.success ? (
            <pre>{JSON.stringify(result.output, null, 2)}</pre>
          ) : (
            <div className="error-message">{result.error}</div>
          )}
        </div>
      )}
    </div>
  );
};
```

---

## 8. API Reference

### 8.1 CapabilityTool API

```python
class CapabilityTool(UITool):
    
    # Constructor
    def __init__(self, agent)
    
    # Abstract methods (must implement)
    @abstractmethod
    def get_capability_type(self) -> CapabilityType
    
    @abstractmethod
    def check_compatibility(self, entity_id: str) -> bool
    
    @abstractmethod
    def create_interface(self, entity_id: str, config: Dict[str, Any]) -> Any
    
    # Provided methods
    def attach_capability(
        self,
        entity_id: str,
        config: Optional[Dict] = None
    ) -> Capability
    
    def get_capabilities_for_entity(
        self,
        entity_id: str
    ) -> List[Capability]
```

### 8.2 MonitoringTool API

```python
class MonitoringTool(UITool):
    
    # Constructor
    def __init__(self, agent)
    
    # Abstract methods (must implement)
    @abstractmethod
    def get_monitor_type(self) -> str
    
    @abstractmethod
    async def check_entity(
        self,
        entity_id: str,
        config: Dict[str, Any]
    ) -> Dict[str, Any]
    
    # Provided methods
    def start_monitoring(
        self,
        entity_id: str,
        frequency: MonitoringFrequency = MonitoringFrequency.NORMAL,
        config: Optional[Dict] = None
    ) -> MonitoringJob
    
    def stop_monitoring(self, job_id: str) -> None
    
    def list_monitoring_jobs(
        self,
        entity_id: Optional[str] = None
    ) -> List[MonitoringJob]
```

### 8.3 ActionTool API

```python
class ActionTool(UITool):
    
    # Constructor
    def __init__(self, agent)
    
    # Abstract methods (must implement)
    @abstractmethod
    def get_action_type(self) -> str
    
    @abstractmethod
    def validate_action(
        self,
        entity_id: str,
        action_params: Dict[str, Any]
    ) -> bool
    
    # Provided methods
    def execute_action(
        self,
        entity_id: str,
        action_params: Dict[str, Any],
        store_result: bool = False
    ) -> Iterator[Union[str, ToolResult]]
```

### 8.4 Data Structures

```python
# Capability
@dataclass
class Capability:
    capability_type: CapabilityType
    entity_id: str
    config: Dict[str, Any]
    status: str  # available, active, error
    metadata: Dict[str, Any]

# MonitoringJob
@dataclass
class MonitoringJob:
    job_id: str
    entity_id: str
    monitor_type: str
    frequency: MonitoringFrequency
    config: Dict[str, Any]
    started_at: float
    last_check: Optional[float]
    status: str  # active, paused, stopped, error
    metrics: Dict[str, Any]

# Enums
class CapabilityType(str, Enum):
    SSH_TERMINAL = "ssh_terminal"
    WEB_TERMINAL = "web_terminal"
    FILE_BROWSER = "file_browser"
    LOG_VIEWER = "log_viewer"
    SHELL_EXECUTOR = "shell_executor"
    API_CLIENT = "api_client"
    DATABASE_CLIENT = "database_client"
    DEBUGGER = "debugger"
    REPL = "repl"

class MonitoringFrequency(str, Enum):
    REALTIME = "realtime"  # 0.1s
    FAST = "fast"          # 1s
    NORMAL = "normal"      # 5s
    SLOW = "slow"          # 30s
    CUSTOM = "custom"
```

---

## 9. Integration Guide

### 9.1 Adding to Existing System

```python
# In tools.py

from tool_framework_extended import (
    CapabilityTool,
    MonitoringTool,
    ActionTool,
    add_capability_tools,
    add_monitoring_tools,
    add_action_tools
)

def ToolLoader(agent):
    """Enhanced ToolLoader with all tool types"""
    tool_list = []
    
    # Existing discovery tools
    add_vtools(tool_list, agent, [
        HostDiscoveryTool,
        PortScanTool,
        ServiceDetectionTool
    ])
    
    # NEW: Capability tools
    add_capability_tools(tool_list, agent)
    
    # NEW: Monitoring tools
    add_monitoring_tools(tool_list, agent)
    
    # NEW: Action tools
    add_action_tools(tool_list, agent)
    
    return tool_list
```

### 9.2 Backend API Endpoints

```python
# In FastAPI app (ChatUI/api/tools.py)

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/tools")

# Capabilities
@router.post("/capabilities/activate")
async def activate_capability(request: dict):
    """Activate a capability on an entity"""
    entity_id = request["entity_id"]
    capability_type = request["capability_type"]
    config = request.get("config", {})
    
    # Get appropriate capability tool
    tool = get_capability_tool(capability_type)
    
    # Attach capability
    result = await tool.attach_capability(entity_id, config)
    
    return {"success": True, "capability": result.to_dict()}

# Monitoring
@router.get("/monitoring/jobs")
async def list_monitoring_jobs(session_id: str, entity_id: Optional[str] = None):
    """List active monitoring jobs"""
    agent = get_agent_for_session(session_id)
    
    jobs = []
    for tool_name, tool in agent.tools.items():
        if isinstance(tool, MonitoringTool):
            jobs.extend(tool.list_monitoring_jobs(entity_id))
    
    return {"jobs": [job.__dict__ for job in jobs]}

@router.post("/monitoring/jobs/{job_id}/stop")
async def stop_monitoring_job(job_id: str):
    """Stop a monitoring job"""
    # Find tool that owns this job
    tool = find_tool_with_job(job_id)
    tool.stop_monitoring(job_id)
    
    return {"success": True}

# Actions
@router.post("/tools/action")
async def execute_action(request: dict):
    """Execute ad-hoc action"""
    entity_id = request["entity_id"]
    action_type = request["action_type"]
    params = request.get("params", {})
    
    # Get action tool
    tool = get_action_tool(action_type)
    
    # Execute
    results = []
    final_result = None
    
    for item in tool.execute_action(entity_id, params):
        if isinstance(item, ToolResult):
            final_result = item
        else:
            results.append(item)
    
    return {
        "success": final_result.success if final_result else False,
        "output": final_result.output if final_result else None,
        "error": final_result.error if final_result else None
    }
```

### 9.3 Frontend Routes

```typescript
// In your React Router config

import { CapabilityPanel } from './components/CapabilityPanel';
import { MonitoringDashboard } from './components/MonitoringDashboard';
import { QuickActionPanel } from './components/QuickActionPanel';

const routes = [
  // Existing routes...
  
  {
    path: '/entities/:entityId/capabilities',
    element: <CapabilityPanel />
  },
  {
    path: '/monitoring',
    element: <MonitoringDashboard />
  },
  {
    path: '/entities/:entityId/actions',
    element: <QuickActionPanel />
  }
];
```

---

## 10. Best Practices

### 10.1 When to Use Each Tool Type

```
Decision Tree:

Need to discover/create entities?
├─ YES → Use VTool
└─ NO → Already have entity
    │
    Need to add interactive feature?
    ├─ YES → Use CapabilityTool
    └─ NO → Need continuous monitoring?
        ├─ YES → Use MonitoringTool
        └─ NO → Quick one-off operation?
            ├─ YES → Use ActionTool
            └─ NO → Reconsider requirements
```

### 10.2 Tool Composition

```python
# Good - Tools work together
class NetworkAdminSuite:
    def __init__(self, agent):
        self.discovery = NetworkScanTool(agent)
        self.ssh = SSHTerminalCapability(agent)
        self.monitor = PortStatusMonitor(agent)
        self.command = SSHCommandAction(agent)
    
    def full_workflow(self, target: str):
        # 1. Discover
        for item in self.discovery.execute(target=target):
            if isinstance(item, ToolResult):
                discovered = item.entities
        
        # 2. Add capabilities
        for entity in discovered:
            if self.ssh.check_compatibility(entity.id):
                self.ssh.attach_capability(entity.id, {...})
        
        # 3. Start monitoring
        for entity in discovered:
            self.monitor.start_monitoring(entity.id)
        
        # 4. Ready for ad-hoc commands via self.command
```

### 10.3 Resource Management

```python
# CapabilityTool - Clean up interfaces
class MyCapabilityTool(CapabilityTool):
    def __init__(self, agent):
        super().__init__(agent)
        self.active_interfaces = {}
    
    def create_interface(self, entity_id: str, config: Dict):
        # Create connection
        interface = create_connection(config)
        
        # Track it
        self.active_interfaces[entity_id] = interface
        
        return interface
    
    def cleanup(self):
        """Call this when shutting down"""
        for interface in self.active_interfaces.values():
            interface.close()
        self.active_interfaces.clear()

# MonitoringTool - Stop all jobs on shutdown
class MyMonitoringTool(MonitoringTool):
    def cleanup(self):
        """Call this when shutting down"""
        for job_id in list(self.jobs.keys()):
            self.stop_monitoring(job_id)
```

### 10.4 Security Considerations

```python
# CapabilityTool - Don't store credentials
class SSHCapability(CapabilityTool):
    def attach_capability(self, entity_id: str, config: Dict):
        # Store config WITHOUT sensitive data
        safe_config = {
            "username": config["username"],
            "port": config.get("port", 22),
            # NOT: "password": config["password"]
        }
        
        return super().attach_capability(entity_id, safe_config)
    
    def create_interface(self, entity_id: str, config: Dict):
        # Credentials provided fresh each time
        # Not stored in capability
        username = config["username"]
        password = config["password"]  # From user, not storage
        
        # Create connection with fresh credentials

# ActionTool - Validate permissions
class ExecuteCommandAction(ActionTool):
    def validate_action(self, entity_id: str, action_params: Dict) -> bool:
        # Check user has permission
        if not user_has_permission(entity_id, "execute_command"):
            return False
        
        # Validate command safety
        command = action_params.get("command", "")
        if any(dangerous in command for dangerous in ["rm -rf", "dd if="]):
            return False
        
        return True
```

---

## 11. Troubleshooting

### 11.1 Common Issues

#### Capability not showing in UI

```python
# Check: Is capability properly attached?
capability = tool.attach_capability(entity_id, config)
print(capability.status)  # Should be "available"

# Check: Is entity updated in graph?
with agent.mem.graph._driver.session() as sess:
    result = sess.run("""
        MATCH (e {id: $entity_id})
        RETURN e.capabilities as caps
    """, {"entity_id": entity_id})
    print(result.single()["caps"])  # Should include capability type
```

#### Monitoring job not streaming metrics

```python
# Check: Is job status active?
jobs = tool.list_monitoring_jobs()
print(jobs)  # Should show status="active"

# Check: Is WebSocket connected?
# In browser console:
# WebSocket connection should be open

# Check: Are metrics being broadcast?
# Add logging in check_entity:
async def check_entity(self, entity_id: str, config: Dict):
    result = {...}
    print(f"Broadcasting metrics: {result}")  # Debug
    return result
```

#### Action not executing

```python
# Check: Validation passing?
valid = tool.validate_action(entity_id, params)
print(valid)  # Should be True

# Check: Error in execution?
for item in tool.execute_action(entity_id, params):
    if isinstance(item, ToolResult):
        if not item.success:
            print(item.error)  # See error
```

### 11.2 Performance Issues

```python
# MonitoringTool using too much CPU
# Solution: Reduce frequency
job = tool.start_monitoring(
    entity_id,
    frequency=MonitoringFrequency.SLOW,  # 30s instead of 1s
    config={...}
)

# Too many monitoring jobs
# Solution: Implement job limits
class MyMonitoringTool(MonitoringTool):
    MAX_JOBS_PER_ENTITY = 3
    
    def start_monitoring(self, entity_id: str, **kwargs):
        # Check existing jobs
        existing = self.list_monitoring_jobs(entity_id)
        if len(existing) >= self.MAX_JOBS_PER_ENTITY:
            raise ValueError(f"Max {self.MAX_JOBS_PER_ENTITY} jobs per entity")
        
        return super().start_monitoring(entity_id, **kwargs)
```

### 11.3 Debugging

```python
# Enable debug logging
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class MyCapabilityTool(CapabilityTool):
    def attach_capability(self, entity_id: str, config: Dict):
        logger.debug(f"Attaching {self.get_capability_type()} to {entity_id}")
        logger.debug(f"Config: {config}")
        
        result = super().attach_capability(entity_id, config)
        
        logger.debug(f"Capability status: {result.status}")
        return result

class MyMonitoringTool(MonitoringTool):
    async def check_entity(self, entity_id: str, config: Dict):
        logger.debug(f"Checking {entity_id}")
        
        result = await self._perform_check(entity_id, config)
        
        logger.debug(f"Metrics: {result}")
        return result
```

---

## 12. Use Cases & Patterns

### 12.1 DevOps Monitoring Suite

```python
"""
Complete DevOps monitoring with capabilities, monitoring, and actions.
"""

# Discovery
class InfrastructureDiscoveryTool(VTool):
    """Discover servers, containers, services"""
    pass

# Capabilities
class KubernetesCapability(CapabilityTool):
    """Add kubectl interface"""
    pass

class DockerCapability(CapabilityTool):
    """Add docker interface"""
    pass

# Monitoring
class ResourceMonitor(MonitoringTool):
    """Monitor CPU, memory, disk"""
    
    async def check_entity(self, entity_id: str, config: Dict):
        # SSH to host, get metrics
        return {
            "cpu_percent": 45.2,
            "memory_percent": 67.8,
            "disk_percent": 23.1
        }

class ServiceMonitor(MonitoringTool):
    """Monitor service health"""
    pass

# Actions
class RestartServiceAction(ActionTool):
    """Restart a service"""
    pass

class ScaleServiceAction(ActionTool):
    """Scale service replicas"""
    pass
```

### 12.2 Security Auditing Suite

```python
"""
Security scanning with monitoring and rapid response.
"""

# Discovery
class SecurityScanTool(VTool):
    """Scan for vulnerabilities"""
    pass

# Capabilities
class SecurityConsoleCapability(CapabilityTool):
    """Add security console"""
    pass

# Monitoring
class VulnerabilityMonitor(MonitoringTool):
    """Continuous vulnerability scanning"""
    
    async def check_entity(self, entity_id: str, config: Dict):
        vulns = scan_for_vulnerabilities(entity_id)
        
        result = {
            "vulnerability_count": len(vulns),
            "critical": len([v for v in vulns if v.severity == "CRITICAL"]),
            "high": len([v for v in vulns if v.severity == "HIGH"])
        }
        
        if result["critical"] > 0:
            result["alert"] = {
                "message": f"{result['critical']} critical vulnerabilities found",
                "severity": "error"
            }
        
        return result

# Actions
class PatchSystemAction(ActionTool):
    """Apply security patches"""
    pass

class IsolateHostAction(ActionTool):
    """Isolate compromised host"""
    pass
```

### 12.3 Data Pipeline Monitoring

```python
"""
Monitor and manage data pipelines.
"""

# Discovery
class PipelineDiscoveryTool(VTool):
    """Discover data pipelines"""
    pass

# Capabilities
class PipelineDebuggerCapability(CapabilityTool):
    """Add pipeline debugger"""
    pass

# Monitoring
class PipelineMonitor(MonitoringTool):
    """Monitor pipeline health"""
    
    async def check_entity(self, entity_id: str, config: Dict):
        stats = get_pipeline_stats(entity_id)
        
        return {
            "records_processed": stats.records,
            "throughput": stats.throughput,
            "error_rate": stats.error_rate,
            "lag": stats.lag
        }

# Actions
class ReprocessDataAction(ActionTool):
    """Reprocess failed records"""
    pass

class SkipRecordAction(ActionTool):
    """Skip problematic record"""
    pass
```

---

## Summary

This extension provides three powerful new tool classes:

### CapabilityTool
- **Purpose**: Add interactive features to entities
- **Use When**: Need UI interaction, terminals, browsers
- **Lifecycle**: Attach once, use many times
- **Storage**: Capability metadata in entity

### MonitoringTool
- **Purpose**: Continuous entity observation
- **Use When**: Need metrics over time, alerts, dashboards
- **Lifecycle**: Start → runs in background → stop
- **Storage**: Metrics stream, optional time-series

### ActionTool
- **Purpose**: Quick ad-hoc operations
- **Use When**: One-off commands, testing, diagnostics
- **Lifecycle**: Execute → return → done
- **Storage**: Optional result storage

**Together they enable:**
1. 🔍 **Discover** entities (VTool)
2. 🎮 **Interact** with them (CapabilityTool)
3. 👁️ **Monitor** their status (MonitoringTool)
4. ⚡ **Act** on them quickly (ActionTool)

---
