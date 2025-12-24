"""
Tool-to-Graph Integration Framework
Enables tools to output entities/relationships that automatically appear in the graph UI

USAGE IN TOOLS:
    from tool_graph_integration import ToolGraphOutput, GraphEntity, GraphRelationship
    
    def my_tool(agent, input_data):
        # ... tool logic ...
        
        # Declare entities discovered/created
        output = ToolGraphOutput()
        output.add_entity(GraphEntity(
            entity_id="discovered_item_123",
            entity_type="DiscoveredItem",
            label="Important Finding",
            properties={"confidence": 0.95, "source": "my_tool"}
        ))
        
        # Link to source node
        output.add_relationship(GraphRelationship(
            from_id="source_node",
            to_id="discovered_item_123",
            rel_type="DISCOVERED",
            properties={"tool": "my_tool"}
        ))
        
        # Return result with graph data
        return output.to_json()

API ENDPOINT (in your FastAPI app):
    from tool_graph_integration import process_tool_graph_output
    
    @app.post("/api/toolchain/{session_id}/execute-tool")
    async def execute_tool(session_id: str, tool_name: str, tool_input: dict):
        result = tool_executor.execute(tool_name, tool_input)
        
        # Process any graph outputs
        entities, relationships = process_tool_graph_output(
            result, session_id, agent.mem
        )
        
        # Broadcast to WebSocket clients
        if entities or relationships:
            await broadcast_graph_update(session_id, entities, relationships)
        
        return {"output": result, "graph_entities": len(entities)}
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# CORE DATA STRUCTURES
# ============================================================================

@dataclass
class GraphEntity:
    """
    Represents a graph node to be created/updated.
    
    Attributes:
        entity_id: Unique identifier (use existing ID to update)
        entity_type: Type/class of entity (e.g., "Person", "Document", "Tool")
        label: Display name for the node
        properties: Additional metadata (dict)
        labels: Neo4j labels (list of strings)
        color: Hex color for visualization (optional)
        size: Node size in pixels (optional, default: 25)
    """
    entity_id: str
    entity_type: str
    label: str
    properties: Dict[str, Any] = None
    labels: List[str] = None
    color: Optional[str] = None
    size: Optional[int] = 25
    
    def __post_init__(self):
        if self.properties is None:
            self.properties = {}
        if self.labels is None:
            self.labels = [self.entity_type]
        
        # Auto-add metadata
        self.properties['created_at'] = self.properties.get('created_at', datetime.utcnow().isoformat())
        self.properties['type'] = self.entity_type


@dataclass
class GraphRelationship:
    """
    Represents a graph edge/relationship to be created.
    
    Attributes:
        from_id: Source node ID
        to_id: Target node ID
        rel_type: Relationship type (e.g., "DISCOVERED", "ANALYZED", "RELATED_TO")
        properties: Additional metadata (dict)
        label: Display label (optional, uses rel_type if not provided)
    """
    from_id: str
    to_id: str
    rel_type: str
    properties: Dict[str, Any] = None
    label: Optional[str] = None
    
    def __post_init__(self):
        if self.properties is None:
            self.properties = {}
        if self.label is None:
            self.label = self.rel_type.replace('_', ' ').title()
        
        self.properties['created_at'] = self.properties.get('created_at', datetime.utcnow().isoformat())
        self.properties['rel'] = self.rel_type


class ToolGraphOutput:
    """
    Container for tool outputs that includes graph data.
    
    Use this in your tools to declare entities and relationships
    that should be added to the graph.
    """
    
    def __init__(self, text_output: str = ""):
        self.text_output = text_output
        self.entities: List[GraphEntity] = []
        self.relationships: List[GraphRelationship] = []
        self.metadata: Dict[str, Any] = {}
    
    def add_entity(self, entity: GraphEntity):
        """Add an entity to be created/updated in the graph."""
        self.entities.append(entity)
        return self
    
    def add_relationship(self, relationship: GraphRelationship):
        """Add a relationship to be created in the graph."""
        self.relationships.append(relationship)
        return self
    
    def set_metadata(self, key: str, value: Any):
        """Add custom metadata to the output."""
        self.metadata[key] = value
        return self
    
    def to_json(self) -> str:
        """
        Convert to JSON string for tool return.
        
        This format is automatically detected and processed by the framework.
        """
        return json.dumps({
            "output": self.text_output,
            "__graph_data__": {
                "entities": [asdict(e) for e in self.entities],
                "relationships": [asdict(r) for r in self.relationships],
                "metadata": self.metadata
            }
        }, default=str)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for direct API use."""
        return {
            "output": self.text_output,
            "__graph_data__": {
                "entities": [asdict(e) for e in self.entities],
                "relationships": [asdict(r) for r in self.relationships],
                "metadata": self.metadata
            }
        }


# ============================================================================
# BACKEND PROCESSING
# ============================================================================

def extract_graph_data(tool_result: Any) -> Tuple[List[Dict], List[Dict]]:
    """
    Extract graph data from tool result.
    
    Supports:
    - JSON strings with __graph_data__ marker
    - Dict objects with __graph_data__ key
    - Plain strings (returns empty lists)
    
    Returns:
        Tuple of (entities, relationships) as list of dicts
    """
    try:
        # Handle string results
        if isinstance(tool_result, str):
            try:
                data = json.loads(tool_result)
            except json.JSONDecodeError:
                # Plain text result, no graph data
                return [], []
        elif isinstance(tool_result, dict):
            data = tool_result
        else:
            return [], []
        
        # Check for graph data marker
        if "__graph_data__" not in data:
            return [], []
        
        graph_data = data["__graph_data__"]
        entities = graph_data.get("entities", [])
        relationships = graph_data.get("relationships", [])
        
        logger.info(f"Extracted {len(entities)} entities and {len(relationships)} relationships from tool output")
        
        return entities, relationships
        
    except Exception as e:
        logger.error(f"Error extracting graph data: {e}")
        return [], []


def process_tool_graph_output(
    tool_result: Any,
    session_id: str,
    memory_system,
    link_to_session: bool = True
) -> Tuple[List[Dict], List[Dict]]:
    """
    Process tool output and store entities/relationships in memory.
    
    Args:
        tool_result: Result from tool execution (string or dict)
        session_id: Current session ID
        memory_system: Agent's memory system (must have .upsert_entity() and .link())
        link_to_session: Whether to link entities to the session
    
    Returns:
        Tuple of (stored_entities, stored_relationships) with full node data
    """
    entities_data, relationships_data = extract_graph_data(tool_result)
    
    if not entities_data and not relationships_data:
        return [], []
    
    stored_entities = []
    stored_relationships = []
    
    # Store entities
    for entity_dict in entities_data:
        try:
            entity_id = entity_dict['entity_id']
            entity_type = entity_dict['entity_type']
            properties = entity_dict.get('properties', {})
            labels = entity_dict.get('labels', [entity_type])
            
            # Store in memory system
            node = memory_system.upsert_entity(
                entity_id=entity_id,
                etype=entity_type,
                labels=labels,
                properties=properties
            )
            
            # Link to session if requested
            if link_to_session and session_id:
                try:
                    memory_system.link_to_session(session_id, entity_id, "CREATED_IN")
                except Exception as e:
                    logger.warning(f"Could not link {entity_id} to session: {e}")
            
            # Build full node data for UI
            stored_entities.append({
                "id": entity_id,
                "label": entity_dict['label'],
                "title": entity_dict['label'],
                "type": entity_type,
                "labels": labels,
                "properties": properties,
                "color": entity_dict.get('color', '#3b82f6'),
                "size": entity_dict.get('size', 25)
            })
            
            logger.debug(f"Stored entity: {entity_id} ({entity_type})")
            
        except Exception as e:
            logger.error(f"Failed to store entity {entity_dict.get('entity_id')}: {e}")
    
    # Store relationships
    for rel_dict in relationships_data:
        try:
            from_id = rel_dict['from_id']
            to_id = rel_dict['to_id']
            rel_type = rel_dict['rel_type']
            properties = rel_dict.get('properties', {})
            
            # Store in memory system
            memory_system.link(from_id, to_id, rel_type, properties)
            
            # Build full edge data for UI
            stored_relationships.append({
                "id": f"{from_id}_{rel_type}_{to_id}",
                "from": from_id,
                "to": to_id,
                "label": rel_dict.get('label', rel_type),
                "title": rel_dict.get('label', rel_type),
                "properties": properties
            })
            
            logger.debug(f"Stored relationship: {from_id} -[{rel_type}]-> {to_id}")
            
        except Exception as e:
            logger.error(f"Failed to store relationship {rel_dict.get('from_id')} -> {rel_dict.get('to_id')}: {e}")
    
    return stored_entities, stored_relationships


# ============================================================================
# WEBSOCKET BROADCAST HELPERS
# ============================================================================

async def broadcast_graph_update(
    session_id: str,
    entities: List[Dict],
    relationships: List[Dict],
    websocket_manager=None
):
    """
    Broadcast graph updates to connected WebSocket clients.
    
    Args:
        session_id: Session to broadcast to
        entities: List of entity dicts (from process_tool_graph_output)
        relationships: List of relationship dicts
        websocket_manager: Your WebSocket manager instance
    
    Usage in FastAPI:
        await broadcast_graph_update(
            session_id, 
            entities, 
            relationships,
            app.state.websocket_manager
        )
    """
    if not websocket_manager:
        logger.warning("No WebSocket manager provided, skipping broadcast")
        return
    
    if not entities and not relationships:
        return
    
    message = {
        "type": "graph_update",
        "session_id": session_id,
        "data": {
            "nodes": entities,
            "edges": relationships
        },
        "timestamp": datetime.utcnow().isoformat()
    }
    
    try:
        await websocket_manager.broadcast_to_session(session_id, message)
        logger.info(f"Broadcasted {len(entities)} entities and {len(relationships)} relationships to session {session_id}")
    except Exception as e:
        logger.error(f"Failed to broadcast graph update: {e}")


# ============================================================================
# DECORATOR FOR AUTOMATIC INTEGRATION
# ============================================================================

def graph_integrated_tool(entity_type: str = None, auto_link_input: bool = True):
    """
    Decorator to automatically integrate tool with graph system.
    
    Args:
        entity_type: Default entity type for outputs (optional)
        auto_link_input: Automatically link output to input node (if node_id in params)
    
    Usage:
        @graph_integrated_tool(entity_type="AnalysisResult")
        def analyze_text(agent, text: str, node_id: str = None):
            # ... your tool logic ...
            result = do_analysis(text)
            
            # Framework automatically creates entity and links it
            return result  # Can return plain string or ToolGraphOutput
    """
    def decorator(func):
        def wrapper(agent, *args, **kwargs):
            # Execute original function
            result = func(agent, *args, **kwargs)
            
            # If result is already ToolGraphOutput, return as-is
            if isinstance(result, ToolGraphOutput):
                return result.to_json()
            
            # Auto-wrap plain results
            output = ToolGraphOutput(text_output=str(result))
            
            # Auto-create entity if entity_type specified
            if entity_type:
                import time
                entity_id = f"{entity_type.lower()}_{int(time.time()*1000)}"
                
                output.add_entity(GraphEntity(
                    entity_id=entity_id,
                    entity_type=entity_type,
                    label=f"{entity_type} Result",
                    properties={
                        "tool": func.__name__,
                        "result_preview": str(result)[:200]
                    }
                ))
                
                # Auto-link to input node if provided
                if auto_link_input and 'node_id' in kwargs and kwargs['node_id']:
                    output.add_relationship(GraphRelationship(
                        from_id=kwargs['node_id'],
                        to_id=entity_id,
                        rel_type="ANALYZED_BY",
                        properties={"tool": func.__name__}
                    ))
            
            return output.to_json()
        
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    
    return decorator


# ============================================================================
# EXAMPLE TOOL IMPLEMENTATIONS
# ============================================================================

def example_search_tool(agent, query: str, source_node: str = None):
    """
    Example tool that discovers entities from search results.
    """
    from duckduckgo_search import DDGS
    
    output = ToolGraphOutput()
    output.text_output = f"Search results for: {query}\n\n"
    
    # Perform search
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=5))
    
    # Create entities for each result
    for idx, result in enumerate(results):
        entity_id = f"search_result_{hash(result['href'])}"
        
        output.add_entity(GraphEntity(
            entity_id=entity_id,
            entity_type="SearchResult",
            label=result['title'][:50],
            properties={
                "url": result['href'],
                "snippet": result['body'],
                "query": query
            },
            color="#10b981"
        ))
        
        # Link result to source node if provided
        if source_node:
            output.add_relationship(GraphRelationship(
                from_id=source_node,
                to_id=entity_id,
                rel_type="SEARCH_RESULT",
                properties={"rank": idx + 1, "query": query}
            ))
        
        output.text_output += f"{idx+1}. {result['title']}\n   {result['href']}\n\n"
    
    return output.to_json()


@graph_integrated_tool(entity_type="Analysis", auto_link_input=True)
def example_analyze_tool(agent, text: str, node_id: str = None):
    """
    Example tool using decorator for automatic integration.
    """
    # Just return analysis - decorator handles graph integration
    word_count = len(text.split())
    char_count = len(text)
    
    return f"Analysis: {word_count} words, {char_count} characters"


# ============================================================================
# TESTING & VALIDATION
# ============================================================================

def test_graph_integration():
    """
    Test the graph integration framework.
    """
    print("Testing Tool-to-Graph Integration Framework")
    print("=" * 60)
    
    # Test 1: Create output with entities
    output = ToolGraphOutput("Test completed successfully")
    output.add_entity(GraphEntity(
        entity_id="test_entity_1",
        entity_type="TestEntity",
        label="Test Node",
        properties={"test": True}
    ))
    output.add_relationship(GraphRelationship(
        from_id="source",
        to_id="test_entity_1",
        rel_type="TESTED"
    ))
    
    json_output = output.to_json()
    print(f"\n✓ Test 1: ToolGraphOutput creation")
    print(f"  Output length: {len(json_output)} chars")
    
    # Test 2: Extract graph data
    entities, relationships = extract_graph_data(json_output)
    print(f"\n✓ Test 2: Data extraction")
    print(f"  Entities: {len(entities)}")
    print(f"  Relationships: {len(relationships)}")
    
    # Test 3: Verify structure
    assert len(entities) == 1
    assert len(relationships) == 1
    assert entities[0]['entity_id'] == "test_entity_1"
    print(f"\n✓ Test 3: Data structure validation")
    
    print("\n" + "=" * 60)
    print("All tests passed! Framework is ready to use.")


if __name__ == "__main__":
    test_graph_integration()