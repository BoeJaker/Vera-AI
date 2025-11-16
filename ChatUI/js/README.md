# ChatUI JavaScript Frontend

## Overview

The JavaScript frontend provides interactive UI components for Vera's web interface, handling real-time communication, graph visualization, and user interactions.

## Key Modules

| File | Purpose |
|------|---------|
| `chat.js` | WebSocket chat interface and message handling |
| `toolchain.js` | Real-time toolchain execution monitoring |
| `graph.js` | Knowledge graph visualization (Neo4j integration) |
| `graph-addon.js` | Additional graph features and interactions |
| `memory.js` | Memory search and session browser |
| `enhanced_chat.js` | Advanced chat features (voice, markdown) |
| `proactive-focus-manager.js` | Background cognition dashboard |
| `notebook.js` | Document management interface |
| `canvas.js` | Drawing and whiteboard functionality |
| `window.js` | Multi-window layout management |
| `theme.js` | Theme switching and customization |

## Technologies

- **Vanilla JavaScript** - No heavy framework dependencies
- **WebSocket API** - Real-time communication
- **Fetch API** - REST endpoint calls
- **vis.js** (or similar) - Graph visualization
- **Markdown-it** - Markdown rendering
- **Highlight.js** - Code syntax highlighting

## Usage Examples

### WebSocket Chat Connection
```javascript
// chat.js
const ws = new WebSocket(`ws://${window.location.host}/ws/chat?session_id=${sessionId}`);

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'chunk') {
        appendToMessage(data.content);
    }
};

ws.send(JSON.stringify({
    message: userInput,
    session_id: sessionId
}));
```

### Graph Visualization
```javascript
// graph.js
async function loadGraph(entityId) {
    const response = await fetch('/api/graph/subgraph', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({entity_id: entityId, depth: 2})
    });

    const graphData = await response.json();
    renderGraph(graphData);
}
```

### Memory Search
```javascript
// memory.js
async function searchMemory(query) {
    const response = await fetch('/api/memory/search', {
        method: 'POST',
        body: JSON.stringify({query, top_k: 10})
    });

    const results = await response.json();
    displayResults(results);
}
```

## Component Architecture

```
UI Components
├── Chat Controller (chat.js)
│   ├── Message Display
│   ├── Input Handling
│   └── WebSocket Management
├── Graph Visualizer (graph.js)
│   ├── Node Rendering
│   ├── Interaction Handling
│   └── Layout Algorithms
├── Toolchain Monitor (toolchain.js)
│   ├── Progress Display
│   ├── Step Tracking
│   └── Error Handling
└── Theme Manager (theme.js)
    ├── Color Schemes
    ├── Dark/Light Toggle
    └── Preference Persistence
```

## Related Documentation

- [ChatUI API](../api/) - Backend endpoints
- [ChatUI Overview](../README.md) - Complete interface documentation

---

**See individual .js files for detailed inline documentation**
