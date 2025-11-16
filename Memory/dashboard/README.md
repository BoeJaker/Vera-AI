# Memory Explorer Dashboard

## Overview

The **Memory Explorer** provides an interactive web interface for visualizing and navigating Vera's knowledge graph, enabling deep exploration of memories, entities, relationships, and sessions.

## Purpose

The dashboard enables:
- **Graph visualization** - Interactive knowledge graph rendering
- **Entity exploration** - Browse nodes and their properties
- **Relationship analysis** - Understand connections between entities
- **Session browsing** - Navigate through conversation history
- **Temporal navigation** - View graph state at different points in time
- **Search and filtering** - Find specific entities or patterns

## Key Files

| File | Purpose |
|------|---------|
| `dashboard.py` | Main Streamlit dashboard application |
| `dashboard.md` | Comprehensive dashboard documentation |
| `graphui.html` | Standalone graph visualization interface |

## Technologies

- **Streamlit** - Python web app framework
- **Neo4j Browser API** - Graph visualization
- **PyVis** - Network graph rendering
- **Pandas** - Data manipulation
- **Plotly** - Interactive charts

## Starting the Dashboard

```bash
# From project root
python3 Memory/dashboard/dashboard.py

# Or from dashboard directory
cd Memory/dashboard
streamlit run dashboard.py --server.port 8501
```

Opens on: `http://localhost:8501`

## Features

### Graph Visualization
- **3D/2D graph rendering** with zoom, pan, rotate
- **Color-coded node types** (Projects, Documents, Memories, Sessions)
- **Edge labels** showing relationship types
- **Interactive node selection** with details panel
- **Cluster detection** for related entities
- **Path finding** between any two nodes

### Entity Search
```python
# Search for entities by name or type
search_query = "authentication"
entity_type = "Project"  # or "Document", "Memory", etc.
```

### Relationship Exploration
```cypher
// Find all entities connected to a project
MATCH (p:Project {name: "Auth System"})-[r]-(related)
RETURN p, r, related
```

### Temporal Navigation
- **Timeline slider** to view graph at different points in time
- **Change history** showing additions/deletions
- **Diff view** between time periods

### Session Browser
- **Chronological session list** with metadata
- **Session content viewer** with full text
- **Cross-session search** for related topics
- **Promotion tracking** (which thoughts became LTM)

## Configuration

Dashboard settings via environment variables or Streamlit config:

```bash
# Neo4j connection
NEO4J_URL=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# Dashboard settings
STREAMLIT_SERVER_PORT=8501
STREAMLIT_SERVER_ADDRESS=0.0.0.0
```

## Usage Examples

### View Full Knowledge Graph
1. Open dashboard
2. Select "Full Graph" view
3. Use filters to show specific node types
4. Click nodes to see properties

### Find Related Entities
1. Search for entity (e.g., "Project X")
2. Select "Subgraph" view with depth=2
3. Visualize all connected entities

### Browse Session History
1. Navigate to "Sessions" tab
2. Filter by date range or tags
3. Click session to view full content
4. See promoted memories

### Analyze Relationships
1. Select two entities
2. Click "Find Path"
3. View shortest path and all relationships

## Visualization Options

### Layout Algorithms
- **Force-directed** - Natural clustering
- **Hierarchical** - Tree-like structure
- **Circular** - Equal spacing
- **Grid** - Organized layout

### Node Styling
```python
# Customize node appearance
node_style = {
    "Project": {"color": "#4A90E2", "shape": "box"},
    "Document": {"color": "#50E3C2", "shape": "ellipse"},
    "Memory": {"color": "#F5A623", "shape": "dot"}
}
```

## Advanced Features

### Cypher Query Console
Execute custom Neo4j queries:
```cypher
MATCH (m:Memory)-[:ABOUT]->(p:Project)
WHERE p.status = 'active'
RETURN m, p
LIMIT 20
```

### Export Capabilities
- **JSON** - Graph data
- **GraphML** - For import to other tools
- **CSV** - Entity/relationship tables
- **PNG/SVG** - Graph visualizations

### Statistics Dashboard
- Node count by type
- Relationship count by type
- Graph density metrics
- Growth over time charts

## Documentation

See [`dashboard.md`](dashboard.md) for comprehensive documentation including:
- Detailed feature descriptions
- Advanced usage patterns
- Troubleshooting guide
- API reference

## Related Documentation

- [Memory System](../README.md) - Overall memory architecture
- [Knowledge Graph](../../Vera%20Assistant%20Docs/Knowledge%20Graph.md) - Graph structure and schema
- [Memory Schema](../schema.md) - Node and relationship types

---

**Access Dashboard:** http://localhost:8501 (after starting)
**Related Components:** [Memory](../), [Neo4j](../database%20server/)
