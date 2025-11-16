# Memory Dashboard Directory

## Table of Contents
- [Overview](#overview)
- [Files](#files)
- [Graph UI](#graph-ui)
- [Dashboard Features](#dashboard-features)
- [Usage Examples](#usage-examples)
- [Visualization](#visualization)
- [Integration](#integration)
- [Troubleshooting](#troubleshooting)

---

## Overview

The Memory dashboard directory implements Vera's interactive memory exploration interface - providing visual tools for browsing the knowledge graph, exploring entities and relationships, and analyzing memory patterns through web-based visualizations.

**Purpose:** Interactive memory exploration and visualization
**Technology:** vis.js + pyvis + FastAPI
**Total Files:** 4 files
**Status:** ✅ Production
**Access:** Web-based UI at `/memory/dashboard`

### Key Features

- **Interactive Graph Visualization**: vis.js-powered network graphs
- **Entity Browser**: Explore nodes and relationships
- **Search Interface**: Find entities and patterns
- **Timeline View**: Temporal memory navigation
- **Export Functionality**: Generate graph exports (HTML, JSON)
- **Real-Time Updates**: Live graph updates via WebSocket
- **Filtering**: Multi-dimensional filtering by type, date, session
- **Analytics**: Graph statistics and insights

---

## Files

### `graphui.html` - Interactive Graph Interface

**Purpose:** Web-based interactive graph visualization

**Size:** ~1200 lines (HTML + CSS + JavaScript)
**Framework:** vis.js
**Features:**
- Interactive node/edge visualization
- Zoom and pan controls
- Node selection and highlighting
- Physics simulation
- Custom styling per node type

**Key Components:**

```html
<!DOCTYPE html>
<html>
<head>
    <title>Vera Memory Graph</title>
    <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style>
        #graph-container {
            width: 100%;
            height: 800px;
            border: 1px solid #ddd;
        }

        .controls {
            margin: 20px;
        }

        .node-details {
            position: fixed;
            right: 20px;
            top: 100px;
            width: 300px;
            background: white;
            padding: 15px;
            border: 1px solid #ccc;
            display: none;
        }
    </style>
</head>
<body>
    <div class="controls">
        <button id="fit-btn">Fit to View</button>
        <button id="physics-toggle">Toggle Physics</button>
        <input id="search-input" placeholder="Search nodes...">
        <select id="filter-type">
            <option value="">All Types</option>
            <option value="entity">Entities</option>
            <option value="memory">Memories</option>
            <option value="insight">Insights</option>
        </select>
    </div>

    <div id="graph-container"></div>
    <div id="node-details" class="node-details"></div>

    <script>
        // Initialize network
        const container = document.getElementById('graph-container');

        const options = {
            nodes: {
                shape: 'dot',
                size: 20,
                font: {
                    size: 14,
                    color: '#ffffff'
                },
                borderWidth: 2,
                shadow: true
            },
            edges: {
                arrows: {
                    to: { enabled: true, scaleFactor: 0.5 }
                },
                smooth: {
                    type: 'continuous',
                    roundness: 0.5
                },
                font: {
                    size: 12,
                    align: 'middle'
                }
            },
            physics: {
                stabilization: false,
                barnesHut: {
                    gravitationalConstant: -2000,
                    springConstant: 0.001,
                    springLength: 200
                }
            },
            interaction: {
                hover: true,
                tooltipDelay: 100
            }
        };

        let network = null;
        let nodes = new vis.DataSet([]);
        let edges = new vis.DataSet([]);

        function initializeGraph(data) {
            network = new vis.Network(
                container,
                { nodes: nodes, edges: edges },
                options
            );

            // Load data
            nodes.add(data.nodes);
            edges.add(data.edges);

            // Event handlers
            network.on('selectNode', onNodeSelect);
            network.on('hoverNode', onNodeHover);
            network.on('doubleClick', onNodeDoubleClick);
        }

        function onNodeSelect(params) {
            if (params.nodes.length > 0) {
                const nodeId = params.nodes[0];
                showNodeDetails(nodeId);
            }
        }

        function showNodeDetails(nodeId) {
            const node = nodes.get(nodeId);
            const detailsDiv = document.getElementById('node-details');

            detailsDiv.innerHTML = `
                <h3>${node.label}</h3>
                <p><strong>Type:</strong> ${node.type || 'Unknown'}</p>
                <p><strong>ID:</strong> ${node.id}</p>
                <div id="node-properties"></div>
                <button onclick="expandNode('${nodeId}')">Expand</button>
                <button onclick="hideNode('${nodeId}')">Hide</button>
            `;

            detailsDiv.style.display = 'block';

            // Load additional properties
            loadNodeProperties(nodeId);
        }

        async function loadNodeProperties(nodeId) {
            const response = await fetch(`/api/memory/entity/${nodeId}`);
            const data = await response.json();

            const propsDiv = document.getElementById('node-properties');
            propsDiv.innerHTML = '<h4>Properties:</h4>';

            for (const [key, value] of Object.entries(data.properties || {})) {
                propsDiv.innerHTML += `<p><strong>${key}:</strong> ${value}</p>`;
            }
        }

        async function expandNode(nodeId) {
            const response = await fetch(`/api/memory/subgraph/${nodeId}?depth=1`);
            const data = await response.json();

            // Add new nodes and edges
            const newNodes = data.nodes.filter(n => !nodes.get(n.id));
            const newEdges = data.edges.filter(e => !edges.get(e.id));

            nodes.add(newNodes);
            edges.add(newEdges);
        }

        function hideNode(nodeId) {
            nodes.remove(nodeId);
        }

        // Search functionality
        document.getElementById('search-input').addEventListener('input', (e) => {
            const searchTerm = e.target.value.toLowerCase();

            nodes.forEach(node => {
                const matches = node.label.toLowerCase().includes(searchTerm);
                nodes.update({
                    id: node.id,
                    opacity: matches ? 1.0 : 0.3
                });
            });
        });

        // Filter by type
        document.getElementById('filter-type').addEventListener('change', (e) => {
            const filterType = e.target.value;

            nodes.forEach(node => {
                const visible = !filterType || node.type === filterType;
                nodes.update({
                    id: node.id,
                    hidden: !visible
                });
            });
        });

        // Fit to view
        document.getElementById('fit-btn').addEventListener('click', () => {
            network.fit({
                animation: { duration: 1000, easingFunction: 'easeInOutQuad' }
            });
        });

        // Toggle physics
        let physicsEnabled = true;
        document.getElementById('physics-toggle').addEventListener('click', () => {
            physicsEnabled = !physicsEnabled;
            network.setOptions({ physics: { enabled: physicsEnabled } });
        });

        // Load initial data
        async function loadGraph() {
            const response = await fetch('/api/graph/session/current');
            const data = await response.json();
            initializeGraph(data);
        }

        loadGraph();
    </script>
</body>
</html>
```

---

### `dashboard.py` - Dashboard Backend

**Purpose:** FastAPI backend for dashboard functionality

**Size:** ~400 lines
**Features:**
- Graph data API endpoints
- Export generation
- Analytics computation
- Real-time updates via WebSocket

**Key Functions:**

```python
from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse
import networkx as nx
from pyvis.network import Network
from pathlib import Path
import json

app = FastAPI()

@app.get("/api/dashboard/graph")
async def get_graph_data(session_id: str):
    """
    Get graph data for visualization

    Returns:
        {
            "nodes": [...],
            "edges": [...],
            "stats": {...}
        }
    """
    # Get graph from Neo4j
    nodes, edges = fetch_graph_from_neo4j(session_id)

    # Calculate statistics
    G = nx.DiGraph()
    G.add_nodes_from([n['id'] for n in nodes])
    G.add_edges_from([(e['from'], e['to']) for e in edges])

    stats = {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "density": nx.density(G),
        "average_degree": sum(dict(G.degree()).values()) / len(G.nodes()) if G.nodes() else 0
    }

    return {
        "nodes": nodes,
        "edges": edges,
        "stats": stats
    }

@app.get("/api/dashboard/export/html")
async def export_html_graph(session_id: str):
    """
    Export graph as interactive HTML using pyvis

    Returns:
        HTML file for download
    """
    # Create pyvis network
    net = Network(
        height="800px",
        width="100%",
        bgcolor="#222222",
        font_color="white"
    )

    # Configure physics
    net.barnes_hut(
        gravity=-2000,
        central_gravity=0.3,
        spring_length=200,
        spring_strength=0.001
    )

    # Load graph data
    nodes, edges = fetch_graph_from_neo4j(session_id)

    # Add nodes
    for node in nodes:
        net.add_node(
            node['id'],
            label=node['label'],
            title=node.get('title', ''),
            color=node.get('color', '#3b82f6')
        )

    # Add edges
    for edge in edges:
        net.add_edge(
            edge['from'],
            edge['to'],
            label=edge.get('label', ''),
            arrows='to'
        )

    # Save to file
    output_file = f"exports/graph_{session_id}.html"
    net.save_graph(output_file)

    return FileResponse(output_file, filename="memory_graph.html")

@app.get("/api/dashboard/analytics")
async def get_analytics(session_id: str):
    """
    Get graph analytics

    Returns:
        {
            "centrality": {...},
            "communities": [...],
            "clusters": [...],
            "statistics": {...}
        }
    """
    # Build NetworkX graph
    G = build_networkx_graph(session_id)

    # Calculate metrics
    analytics = {
        "degree_centrality": nx.degree_centrality(G),
        "betweenness_centrality": nx.betweenness_centrality(G),
        "closeness_centrality": nx.closeness_centrality(G),
        "pagerank": nx.pagerank(G),
        "communities": list(nx.community.greedy_modularity_communities(G.to_undirected())),
        "statistics": {
            "nodes": G.number_of_nodes(),
            "edges": G.number_of_edges(),
            "density": nx.density(G),
            "average_clustering": nx.average_clustering(G.to_undirected()),
            "transitivity": nx.transitivity(G.to_undirected())
        }
    }

    return analytics

@app.websocket("/ws/dashboard/{session_id}")
async def dashboard_stream(websocket: WebSocket, session_id: str):
    """
    WebSocket for real-time graph updates

    Messages:
        - node_added: New node created
        - edge_added: New edge created
        - node_updated: Node properties changed
    """
    await websocket.accept()

    try:
        while True:
            # Check for graph changes
            changes = check_graph_changes(session_id)

            if changes:
                await websocket.send_json({
                    "type": "graph_update",
                    "changes": changes
                })

            await asyncio.sleep(1)

    except WebSocketDisconnect:
        pass
```

---

### `dashboard.md` / `graph_ui.md` - Documentation

**Purpose:** Feature documentation and usage guide

**Contents:**
- Dashboard features overview
- User interface guide
- API endpoint documentation
- Customization options
- Best practices

**Example Content:**

```markdown
# Memory Dashboard

## Features

### Graph Visualization
- Interactive network visualization using vis.js
- Physics-based layout
- Node/edge customization
- Real-time updates

### Entity Explorer
- Browse all entities and relationships
- Filter by type, date, session
- Search functionality
- Detailed property viewing

### Analytics
- Graph statistics
- Community detection
- Centrality metrics
- Pattern recognition

## Usage

### Accessing Dashboard
Navigate to: http://llm.int:8888/memory/dashboard

### Controls
- **Zoom**: Mouse wheel or pinch
- **Pan**: Click and drag
- **Select**: Click node or edge
- **Expand**: Double-click node
- **Search**: Type in search box

### Filters
- Type: Filter by entity type
- Date: Show entities from date range
- Session: Filter by session ID

## Customization

### Node Styling
Customize node appearance in `graphui.html`:
```javascript
nodes: {
    shape: 'dot',      // 'dot', 'box', 'diamond', 'star'
    size: 20,          // Node size
    color: '#3b82f6',  // Node color
    font: {
        size: 14,
        color: '#ffffff'
    }
}
```

### Physics Settings
Adjust graph physics:
```javascript
physics: {
    barnesHut: {
        gravitationalConstant: -2000,
        springConstant: 0.001,
        springLength: 200
    }
}
```
```

---

## Dashboard Features

### 1. Interactive Graph Exploration

**Node Selection:**
- Click node to view details
- Double-click to expand connections
- Right-click for context menu

**Navigation:**
- Mouse wheel: Zoom in/out
- Click + drag: Pan view
- Fit to view button: Center and scale graph

**Search:**
- Real-time node filtering
- Highlight matching nodes
- Jump to search results

---

### 2. Entity Details Panel

When selecting a node:
- Display entity properties
- Show connected relationships
- View creation/update timestamps
- Access raw data

---

### 3. Graph Analytics

**Centrality Metrics:**
- Degree centrality: Most connected nodes
- Betweenness centrality: Key bridge nodes
- Closeness centrality: Most accessible nodes
- PageRank: Most important nodes

**Community Detection:**
- Identify node clusters
- Color-code communities
- Analyze intra-community connections

**Statistics:**
- Total nodes/edges
- Graph density
- Average clustering coefficient
- Network diameter

---

### 4. Export Functionality

**HTML Export:**
- Standalone interactive graph
- Embeddable in reports
- Preserves interactivity

**JSON Export:**
- Raw graph data
- Import into other tools
- Backup and versioning

**Image Export:**
- PNG/SVG snapshots
- High-resolution graphics
- Documentation and presentations

---

## Usage Examples

### Loading Dashboard

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# Mount dashboard
app.mount("/memory/dashboard", StaticFiles(directory="Memory/dashboard"), name="dashboard")

# Start server
import uvicorn
uvicorn.run(app, host="0.0.0.0", port=8888)
```

Access at: `http://localhost:8888/memory/dashboard/graphui.html`

---

### Programmatic Graph Export

```python
from pyvis.network import Network

def export_memory_graph(session_id, output_file="memory_graph.html"):
    """Export memory graph to HTML"""
    net = Network(height="800px", width="100%")

    # Get graph data from Vera
    from vera import Vera
    vera = Vera()

    # Fetch entities and relationships
    driver = vera.mem.graph._driver
    with driver.session() as db_sess:
        # Get nodes
        nodes_result = db_sess.run("MATCH (n) WHERE n.session_id = $sid RETURN n", sid=session_id)
        for record in nodes_result:
            node = record['n']
            net.add_node(
                node['id'],
                label=node.get('type', 'Node'),
                title=node.get('text', '')
            )

        # Get relationships
        edges_result = db_sess.run("""
            MATCH (a)-[r]->(b)
            WHERE a.session_id = $sid
            RETURN a.id AS from, b.id AS to, type(r) AS label
        """, sid=session_id)

        for record in edges_result:
            net.add_edge(record['from'], record['to'], label=record['label'])

    # Save
    net.save_graph(output_file)
    print(f"Graph exported to {output_file}")

# Usage
export_memory_graph("sess_abc123")
```

---

### Custom Visualization

```python
import networkx as nx
import matplotlib.pyplot as plt

def visualize_with_networkx(session_id):
    """Create custom visualization with NetworkX"""
    G = nx.DiGraph()

    # Build graph from Vera memory
    from vera import Vera
    vera = Vera()

    driver = vera.mem.graph._driver
    with driver.session() as db_sess:
        result = db_sess.run("""
            MATCH (a)-[r]->(b)
            WHERE a.session_id = $sid
            RETURN a.id AS from, b.id AS to
        """, sid=session_id)

        for record in result:
            G.add_edge(record['from'], record['to'])

    # Layout
    pos = nx.spring_layout(G)

    # Draw
    plt.figure(figsize=(15, 10))
    nx.draw_networkx_nodes(G, pos, node_color='lightblue', node_size=500)
    nx.draw_networkx_edges(G, pos, edge_color='gray', arrows=True)
    nx.draw_networkx_labels(G, pos)

    plt.title(f"Memory Graph - Session {session_id}")
    plt.axis('off')
    plt.tight_layout()
    plt.savefig(f"graph_{session_id}.png", dpi=300)
    plt.show()

# Usage
visualize_with_networkx("sess_abc123")
```

---

## Visualization

### Color Schemes

**Node Colors by Type:**
```python
COLOR_SCHEME = {
    'thought': '#f59e0b',    # Orange
    'memory': '#f59e0b',
    'decision': '#ef4444',   # Red
    'class': '#2d8cf0',      # Blue
    'plan': '#8b5cf6',       # Purple
    'tool': '#f97316',       # Deep Orange
    'process': '#e879f9',    # Pink
    'file': '#f43f5e',       # Rose
    'webpage': '#60a5fa',    # Light Blue
    'document': '#34d399',   # Emerald
    'query': '#32B39D',      # Turquoise
    'entity': '#10b93a',     # Green
    'session': '#3f1b92',    # Deep Purple
    'default': '#3b82f6'     # Blue
}
```

### Layout Algorithms

**Available Layouts:**
- Barnes-Hut: Force-directed (default)
- Hierarchical: Tree-like structure
- Circular: Circular arrangement
- Grid: Grid-based positioning

---

## Integration

### With Chat UI

```javascript
// In ChatUI js/graph.js
async function loadDashboardView() {
    const iframe = document.createElement('iframe');
    iframe.src = '/memory/dashboard/graphui.html';
    iframe.style.width = '100%';
    iframe.style.height = '800px';

    document.getElementById('graph-panel').appendChild(iframe);
}
```

### With Memory API

```python
# Real-time graph updates
@router.post("/api/memory/entity/create")
async def create_entity(entity: EntityCreate):
    # Create entity in Neo4j
    node_id = vera.mem.add_entity(entity.name, entity.type)

    # Notify dashboard via WebSocket
    await notify_dashboard_update({
        "type": "node_added",
        "node": {
            "id": node_id,
            "label": entity.type,
            "properties": entity.properties
        }
    })

    return {"id": node_id}
```

---

## Troubleshooting

### Graph Not Loading

**Issue:** Dashboard shows empty graph

**Solution:**
```javascript
// Check API endpoint
console.log('Fetching graph from:', API_URL);

// Verify data format
fetch(API_URL).then(r => r.json()).then(data => {
    console.log('Nodes:', data.nodes.length);
    console.log('Edges:', data.edges.length);
});
```

### Performance Issues

**Issue:** Graph slow with many nodes

**Solutions:**
1. Limit node count:
```python
# Add pagination
@app.get("/api/dashboard/graph")
async def get_graph_data(limit: int = 100):
    nodes = fetch_nodes(limit=limit)
    ...
```

2. Disable physics:
```javascript
network.setOptions({ physics: { enabled: false } });
```

3. Simplify rendering:
```javascript
nodes: {
    shape: 'dot',  // Simple shape
    size: 10,      // Smaller nodes
    font: false    // Hide labels
}
```

---

## Related Documentation

- [Memory System](../README.md)
- [Graph API](../../ChatUI/api/README.md#graph-api)
- [vis.js Documentation](https://visjs.github.io/vis-network/docs/network/)

---

**Last Updated:** January 2025
**Maintainer:** Vera-AI Development Team
**Version:** 1.0.0
