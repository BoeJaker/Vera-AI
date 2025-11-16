# ChatUI JavaScript Directory

## Table of Contents
- [Overview](#overview)
- [Architecture](#architecture)
- [Core Modules](#core-modules)
- [Component Integration](#component-integration)
- [Event System](#event-system)
- [State Management](#state-management)
- [UI Components](#ui-components)
- [Usage Examples](#usage-examples)
- [Development Guide](#development-guide)
- [Performance](#performance)
- [Troubleshooting](#troubleshooting)

---

## Overview

The ChatUI JavaScript directory contains the client-side application logic for Vera's web interface - implementing a sophisticated multi-panel dashboard with real-time WebSocket communication, knowledge graph visualization, memory exploration, and interactive UI components.

**Purpose:** Frontend application logic for Vera web interface
**Technology:** Vanilla JavaScript (ES6+) + vis.js + marked.js
**Total Files:** 11 JavaScript modules
**Status:** ✅ Production
**Code Style:** Class-based with prototype extensions

### Key Features

- **Multi-Column Layout**: Flexible workspace with draggable tabs
- **Real-Time Updates**: WebSocket streaming for chat, tools, and orchestration
- **Knowledge Graph**: Interactive vis.js network visualization
- **Memory Browser**: Advanced search and filtering
- **Notebook System**: Markdown editor with auto-save
- **Canvas Drawing**: Freehand drawing and annotations
- **Theme Support**: Dark/light themes with customization
- **Speech Integration**: Text-to-speech and speech-to-text
- **Tool Monitoring**: Real-time toolchain execution tracking

---

## Architecture

### Module Architecture

```
┌──────────────────────────────────────────────────────────┐
│                     VeraChat (Core)                       │
│                      (chat.js)                            │
└────────────────────┬─────────────────────────────────────┘
                     │
        ┌────────────┼────────────┬────────────┐
        │            │            │            │
   ┌────▼────┐ ┌────▼────┐ ┌────▼────┐ ┌────▼────┐
   │enhanced │ │ memory  │ │  graph  │ │notebook │
   │ _chat   │ │   .js   │ │   .js   │ │  .js    │
   └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘
        │            │            │            │
   ┌────▼────┐ ┌────▼────┐ ┌────▼────┐ ┌────▼────┐
   │toolchain│ │ canvas  │ │  theme  │ │ window  │
   │  .js    │ │  .js    │ │   .js   │ │  .js    │
   └─────────┘ └─────────┘ └─────────┘ └─────────┘
```

### Data Flow

```
User Action
    │
    ▼
┌──────────────┐
│  Event       │
│  Handler     │
└──────┬───────┘
       │
       ▼
┌──────────────┐     ┌──────────────┐
│  State       │────►│  API Call    │
│  Update      │     │  (REST/WS)   │
└──────┬───────┘     └──────┬───────┘
       │                    │
       │                    ▼
       │             ┌──────────────┐
       │             │  Backend     │
       │             │  Processing  │
       │             └──────┬───────┘
       │                    │
       ▼                    ▼
┌──────────────┐     ┌──────────────┐
│  UI Update   │◄────│  Response    │
│  (DOM)       │     │  Data        │
└──────────────┘     └──────────────┘
```

---

## Core Modules

### `chat.js` - Main Chat Interface

**Purpose:** Core chat functionality and application orchestration

**Size:** ~1500 lines

**Main Class:**

```javascript
class VeraChat {
    constructor() {
        // State
        this.messages = [];
        this.files = {};
        this.sessionId = null;
        this.processing = false;

        // WebSockets
        this.websocket = null;
        this.toolchainWebSocket = null;
        this.focusWebSocket = null;

        // UI State
        this.columns = [];
        this.tabs = [
            { id: 'chat', label: 'Chat', columnId: 1 },
            { id: 'graph', label: 'Knowledge Graph', columnId: 2 },
            { id: 'memory', label: 'Memory', columnId: 2 },
            { id: 'notebook', label: 'Notebook', columnId: 2 },
            { id: 'canvas', label: 'Canvas', columnId: 2 },
            { id: 'toolchain', label: 'Toolchain', columnId: 2 },
            { id: 'focus', label: 'Proactive Focus', columnId: 2 },
            { id: 'orchestration', label: 'Orchestration', columnId: 2 }
        ];
        this.activeTabPerColumn = {};

        // Features
        this.networkInstance = null;
        this.veraRobot = null;

        this.init();
    }
}
```

**Key Methods:**

#### Session Management

```javascript
async init() {
    // Start session
    const response = await fetch('http://llm.int:8888/api/session/start', {
        method: 'POST'
    });
    const data = await response.json();
    this.sessionId = data.session_id;

    // Update UI
    document.getElementById('sessionInfo').textContent =
        `Session: ${this.sessionId}`;
    document.getElementById('connectionStatus').innerHTML =
        '<span class="status-indicator connected"></span>Connected';

    // Initialize components
    this.createColumn();
    this.createColumn();
    this.connectWebSocket();
    this.loadAvailableTools();
}
```

#### WebSocket Communication

```javascript
connectWebSocket() {
    this.websocket = new WebSocket(
        `ws://llm.int:8888/ws/chat/${this.sessionId}`
    );

    this.websocket.onopen = () => {
        console.log('WebSocket connected');
        this.updateConnectionStatus('connected');
    };

    this.websocket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        this.handleWebSocketMessage(data);
    };

    this.websocket.onerror = (error) => {
        console.error('WebSocket error:', error);
        this.updateConnectionStatus('error');
    };

    this.websocket.onclose = () => {
        console.log('WebSocket closed');
        this.updateConnectionStatus('disconnected');
        // Reconnect after 3 seconds
        setTimeout(() => this.connectWebSocket(), 3000);
    };
}

handleWebSocketMessage(data) {
    switch (data.type) {
        case 'chunk':
            // Streaming response chunk
            this.appendToStreamingMessage(data.content);
            break;

        case 'complete':
            // Response complete
            this.finalizeStreamingMessage();
            break;

        case 'tool_call':
            // Tool execution update
            this.handleToolCallUpdate(data);
            break;

        case 'error':
            // Error occurred
            this.showError(data.message);
            break;
    }
}
```

#### Message Handling

```javascript
async sendMessage(message) {
    if (!message.trim()) return;

    // Add user message to UI
    this.addMessage('user', message);

    // Clear input
    document.getElementById('messageInput').value = '';

    // Show processing indicator
    this.processing = true;
    this.updateUI();

    try {
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
            // Send via WebSocket for streaming
            this.websocket.send(JSON.stringify({
                type: 'message',
                content: message,
                session_id: this.sessionId
            }));

            // Create placeholder for streaming response
            this.currentStreamingMessageId = this.createStreamingMessage();

        } else {
            // Fallback to HTTP POST
            const response = await fetch('http://llm.int:8888/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    message: message
                })
            });

            const data = await response.json();
            this.addMessage('assistant', data.response);
        }
    } catch (error) {
        console.error('Error sending message:', error);
        this.showError('Failed to send message');
    } finally {
        this.processing = false;
        this.updateUI();
    }
}

addMessage(role, content) {
    const messageElement = document.createElement('div');
    messageElement.className = `message ${role}-message`;

    // Render markdown
    const contentHtml = marked.parse(content);

    messageElement.innerHTML = `
        <div class="message-role">${role}</div>
        <div class="message-content">${contentHtml}</div>
        <div class="message-timestamp">${new Date().toLocaleTimeString()}</div>
    `;

    // Add to messages container
    const container = document.getElementById('messages-container');
    container.appendChild(messageElement);

    // Auto-scroll
    container.scrollTop = container.scrollHeight;

    // Store in messages array
    this.messages.push({
        role: role,
        content: content,
        timestamp: new Date().toISOString()
    });
}
```

#### Column and Tab Management

```javascript
createColumn() {
    const columnId = this.nextColumnId++;
    const column = {
        id: columnId,
        tabs: []
    };
    this.columns.push(column);

    // Create column DOM
    const columnsContainer = document.querySelector('.columns-container');
    const columnElement = document.createElement('div');
    columnElement.className = 'column';
    columnElement.dataset.columnId = columnId;

    columnElement.innerHTML = `
        <div class="tab-bar">
            <div class="tab-list"></div>
            <button class="column-close-btn" onclick="veraChat.closeColumn(${columnId})">
                ✕
            </button>
        </div>
        <div class="tab-content-area"></div>
    `;

    columnsContainer.appendChild(columnElement);
    this.renderTabs();
}

switchTab(tabId, columnId) {
    // Update active tab state
    this.activeTabPerColumn[columnId] = tabId;

    // Update UI
    const column = document.querySelector(`[data-column-id="${columnId}"]`);
    if (!column) return;

    // Update tab buttons
    column.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tabId === tabId);
    });

    // Update content area
    const contentArea = column.querySelector('.tab-content-area');
    contentArea.innerHTML = this.getTabContent(tabId);

    // Initialize tab-specific functionality
    this.initializeTab(tabId, columnId);
}
```

---

### `enhanced_chat.js` - Enhanced Features

**Purpose:** Advanced chat functionality

**Size:** ~800 lines

**Features:**

#### Text-to-Speech

```javascript
VeraChat.prototype.initModernFeatures = function() {
    this.ttsEnabled = localStorage.getItem('tts-enabled') === 'true';

    // Initialize speech synthesis
    if ('speechSynthesis' in window) {
        speechSynthesis.onvoiceschanged = () => {
            const voices = speechSynthesis.getVoices();
            this.ttsVoice = voices.find(v => v.lang.startsWith('en')) || voices[0];
        };
    }
}

VeraChat.prototype.speak = function(text) {
    if (!this.ttsEnabled || !('speechSynthesis' in window)) return;

    // Cancel any ongoing speech
    speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.voice = this.ttsVoice;
    utterance.rate = 1.0;
    utterance.pitch = 1.0;

    speechSynthesis.speak(utterance);
}
```

#### Speech-to-Text

```javascript
VeraChat.prototype.initSpeechRecognition = function() {
    if (!('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
        return;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    this.recognition = new SpeechRecognition();
    this.recognition.continuous = false;
    this.recognition.interimResults = true;
    this.recognition.lang = 'en-US';

    this.recognition.onresult = (event) => {
        const transcript = Array.from(event.results)
            .map(result => result[0].transcript)
            .join('');

        const textarea = document.getElementById('messageInput');
        if (textarea) {
            textarea.value = transcript;
            textarea.dispatchEvent(new Event('input'));
        }
    };

    this.recognition.onend = () => {
        this.sttActive = false;
        this.updateControlBar();
    };
}

VeraChat.prototype.toggleSTT = function() {
    if (!this.recognition) return;

    if (this.sttActive) {
        this.recognition.stop();
        this.sttActive = false;
    } else {
        this.recognition.start();
        this.sttActive = true;
    }

    this.updateControlBar();
}
```

#### Control Bar

```javascript
VeraChat.prototype.addControlBar = function() {
    const chatContainer = document.getElementById('tab-chat');
    if (!chatContainer) return;

    const controlBar = document.createElement('div');
    controlBar.id = 'chat-control-bar';
    controlBar.className = 'chat-control-bar';

    controlBar.innerHTML = `
        <button id="stt-btn" class="control-btn" title="Speech-to-Text">
            🎤
        </button>
        <button id="tts-btn" class="control-btn" title="Text-to-Speech">
            🔊
        </button>
        <button id="canvas-focus-btn" class="control-btn" title="Canvas Auto-Focus">
            🎨
        </button>
    `;

    chatContainer.insertBefore(controlBar, chatContainer.firstChild);

    // Event listeners
    document.getElementById('stt-btn').addEventListener('click', () => {
        this.toggleSTT();
    });

    document.getElementById('tts-btn').addEventListener('click', () => {
        this.toggleTTS();
    });
}
```

---

### `memory.js` - Memory Explorer

**Purpose:** Memory search and browsing interface

**Size:** ~600 lines

**Key Features:**

#### Memory Search

```javascript
VeraChat.prototype.searchMemory = async function(query, searchMode = 'hybrid') {
    if (!query.trim()) return;

    const resultsContainer = document.getElementById('memory-results');
    resultsContainer.innerHTML = '<div class="loading">Searching...</div>';

    try {
        const response = await fetch('http://llm.int:8888/api/memory/query', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query: query,
                session_id: this.sessionId,
                retrieval_type: searchMode,
                k: 50
            })
        });

        const data = await response.json();
        this.memoryQueryResults = data.results;
        this.renderMemoryResults(data.results);

    } catch (error) {
        console.error('Memory search failed:', error);
        resultsContainer.innerHTML = '<div class="error">Search failed</div>';
    }
}

VeraChat.prototype.renderMemoryResults = function(results) {
    const container = document.getElementById('memory-results');

    if (!results || results.length === 0) {
        container.innerHTML = '<div class="no-results">No results found</div>';
        return;
    }

    container.innerHTML = results.map((result, index) => `
        <div class="memory-result-item" data-index="${index}">
            <div class="result-header">
                <span class="result-source">${result.source || 'unknown'}</span>
                <span class="result-score">${(result.score * 100).toFixed(1)}%</span>
            </div>
            <div class="result-text">${this.highlightQuery(result.text, query)}</div>
            <div class="result-metadata">
                ${Object.entries(result.metadata || {})
                    .map(([k, v]) => `<span class="metadata-tag">${k}: ${v}</span>`)
                    .join('')}
            </div>
            <div class="result-actions">
                <button onclick="veraChat.viewMemoryDetail(${index})">
                    View Details
                </button>
                <button onclick="veraChat.addToGraph('${result.id}')">
                    Add to Graph
                </button>
            </div>
        </div>
    `).join('');
}
```

#### Entity Browser

```javascript
VeraChat.prototype.loadMemoryEntities = async function() {
    try {
        const response = await fetch(
            `http://llm.int:8888/api/memory/entities?session_id=${this.sessionId}&limit=100`
        );
        const data = await response.json();
        this.memoryEntities = data.entities;
        this.renderEntityBrowser();

    } catch (error) {
        console.error('Failed to load entities:', error);
    }
}

VeraChat.prototype.renderEntityBrowser = function() {
    const container = document.getElementById('entity-browser');

    const groupedEntities = this.groupEntitiesByType(this.memoryEntities);

    container.innerHTML = Object.entries(groupedEntities)
        .map(([type, entities]) => `
            <div class="entity-type-group">
                <h4 class="entity-type-header">
                    ${type} (${entities.length})
                </h4>
                <div class="entity-list">
                    ${entities.map(entity => `
                        <div class="entity-item" data-id="${entity.id}">
                            <span class="entity-name">${entity.name}</span>
                            <button onclick="veraChat.viewEntity('${entity.id}')">
                                View
                            </button>
                        </div>
                    `).join('')}
                </div>
            </div>
        `).join('');
}
```

---

### `graph.js` - Knowledge Graph

**Purpose:** Interactive graph visualization

**Size:** ~700 lines

**Key Features:**

#### Graph Initialization

```javascript
VeraChat.prototype.initializeGraph = function() {
    const container = document.getElementById('graph-canvas');
    if (!container) return;

    this.nodes = new vis.DataSet([]);
    this.edges = new vis.DataSet([]);

    const options = {
        nodes: {
            shape: 'dot',
            size: 16,
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
                align: 'middle',
                color: '#cccccc'
            },
            width: 2
        },
        physics: {
            stabilization: false,
            barnesHut: {
                gravitationalConstant: -2000,
                springConstant: 0.001,
                springLength: 200,
                damping: 0.09
            }
        },
        interaction: {
            hover: true,
            tooltipDelay: 100,
            zoomView: true,
            dragView: true
        }
    };

    this.networkInstance = new vis.Network(
        container,
        { nodes: this.nodes, edges: this.edges },
        options
    );

    // Event handlers
    this.setupGraphEvents();
}
```

#### Graph Loading

```javascript
VeraChat.prototype.loadGraph = async function() {
    try {
        const response = await fetch(
            `http://llm.int:8888/api/graph/session/${this.sessionId}`
        );
        const data = await response.json();

        // Clear existing
        this.nodes.clear();
        this.edges.clear();

        // Add nodes
        if (data.nodes && data.nodes.length > 0) {
            this.nodes.add(data.nodes);
        }

        // Add edges
        if (data.edges && data.edges.length > 0) {
            this.edges.add(data.edges);
        }

        // Fit to view
        if (this.networkInstance) {
            this.networkInstance.fit({
                animation: {
                    duration: 1000,
                    easingFunction: 'easeInOutQuad'
                }
            });
        }

    } catch (error) {
        console.error('Failed to load graph:', error);
    }
}
```

#### Graph Interactions

```javascript
VeraChat.prototype.setupGraphEvents = function() {
    if (!this.networkInstance) return;

    // Node selection
    this.networkInstance.on('selectNode', (params) => {
        if (params.nodes.length > 0) {
            const nodeId = params.nodes[0];
            this.showNodeDetails(nodeId);
        }
    });

    // Node hover
    this.networkInstance.on('hoverNode', (params) => {
        const nodeId = params.node;
        this.highlightConnections(nodeId);
    });

    // Double click to expand
    this.networkInstance.on('doubleClick', (params) => {
        if (params.nodes.length > 0) {
            const nodeId = params.nodes[0];
            this.expandNode(nodeId);
        }
    });
}

VeraChat.prototype.expandNode = async function(nodeId) {
    try {
        const response = await fetch(
            `http://llm.int:8888/api/memory/subgraph/${nodeId}?session_id=${this.sessionId}&depth=1`
        );
        const data = await response.json();

        // Add new nodes and edges
        const newNodes = data.nodes.filter(n =>
            !this.nodes.get(n.id)
        );
        const newEdges = data.edges.filter(e =>
            !this.edges.get(e.id)
        );

        if (newNodes.length > 0) this.nodes.add(newNodes);
        if (newEdges.length > 0) this.edges.add(newEdges);

    } catch (error) {
        console.error('Failed to expand node:', error);
    }
}
```

---

### `notebook.js` - Notebook System

**Purpose:** Note-taking and markdown editing

**Size:** ~500 lines

**Key Features:**

#### Notebook Management

```javascript
VeraChat.prototype.loadNotebooks = async function() {
    try {
        const response = await fetch(
            `http://llm.int:8888/api/notebooks/${this.sessionId}`
        );
        const data = await response.json();
        this.notebooks = data.notebooks || [];
        this.updateNotebookSelector();

    } catch (error) {
        console.error('Failed to load notebooks:', error);
    }
}

VeraChat.prototype.createNotebook = async function() {
    const name = prompt('Enter notebook name:');
    if (!name || !name.trim()) return;

    try {
        const response = await fetch(
            `http://llm.int:8888/api/notebooks/${this.sessionId}/create`,
            {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: name.trim() })
            }
        );

        const data = await response.json();
        this.notebooks.push(data.notebook);
        this.updateNotebookSelector();

    } catch (error) {
        console.error('Failed to create notebook:', error);
    }
}
```

#### Note Editing

```javascript
VeraChat.prototype.createNote = async function() {
    if (!this.currentNotebook) return;

    const title = prompt('Note title:');
    if (!title || !title.trim()) return;

    const noteData = {
        title: title.trim(),
        content: '',
        tags: []
    };

    try {
        const response = await fetch(
            `http://llm.int:8888/api/notebooks/${this.sessionId}/${this.currentNotebook.id}/note`,
            {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(noteData)
            }
        );

        const data = await response.json();
        this.notes.push(data.note);
        this.updateNotesUI();
        this.editNote(data.note.id);

    } catch (error) {
        console.error('Failed to create note:', error);
    }
}

VeraChat.prototype.saveNote = async function() {
    if (!this.currentNote) return;

    const content = document.getElementById('note-editor').value;

    try {
        await fetch(
            `http://llm.int:8888/api/notebooks/${this.sessionId}/${this.currentNotebook.id}/note/${this.currentNote.id}`,
            {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content: content })
            }
        );

        this.currentNote.content = content;
        this.showSaveIndicator();

    } catch (error) {
        console.error('Failed to save note:', error);
    }
}
```

---

### `toolchain.js` - Toolchain Monitor

**Purpose:** Tool execution tracking

**Size:** ~400 lines

**Features:**

```javascript
VeraChat.prototype.executeToolchain = async function(query) {
    try {
        const response = await fetch('http://llm.int:8888/api/toolchain/execute', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query: query,
                strategy: 'hybrid',
                session_id: this.sessionId
            })
        });

        const data = await response.json();
        const executionId = data.execution_id;

        // Connect to WebSocket for streaming updates
        this.connectToolchainWebSocket(executionId);

    } catch (error) {
        console.error('Failed to execute toolchain:', error);
    }
}

VeraChat.prototype.connectToolchainWebSocket = function(executionId) {
    this.toolchainWebSocket = new WebSocket(
        `ws://llm.int:8888/ws/toolchain/${executionId}`
    );

    this.toolchainWebSocket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        this.handleToolchainUpdate(data);
    };
}

VeraChat.prototype.handleToolchainUpdate = function(data) {
    switch (data.type) {
        case 'plan':
            this.displayToolchainPlan(data.plan);
            break;
        case 'step_start':
            this.updateStepStatus(data.step_num, 'running');
            break;
        case 'step_complete':
            this.updateStepStatus(data.step_num, 'complete');
            this.displayStepOutput(data.step_num, data.output);
            break;
        case 'complete':
            this.displayFinalResult(data.result);
            break;
        case 'error':
            this.displayError(data.message);
            break;
    }
}
```

---

## State Management

### Application State

```javascript
const AppState = {
    // Session
    sessionId: null,
    vera: null,

    // UI
    columns: [],
    activeTabPerColumn: {},
    processing: false,

    // Data
    messages: [],
    nodes: [],
    edges: [],
    notebooks: [],
    memoryResults: [],

    // WebSockets
    chatWS: null,
    toolchainWS: null,
    focusWS: null
};
```

### Local Storage

```javascript
// Persist preferences
localStorage.setItem('theme', 'dark');
localStorage.setItem('tts-enabled', 'true');
localStorage.setItem('canvas-auto-focus', 'true');

// Retrieve preferences
const theme = localStorage.getItem('theme') || 'dark';
const ttsEnabled = localStorage.getItem('tts-enabled') === 'true';
```

---

## Performance

### Optimization Techniques

**1. Debouncing:**
```javascript
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}

// Usage
const debouncedSearch = debounce(searchMemory, 300);
```

**2. Virtual Scrolling:**
```javascript
// Render only visible items
function renderVisibleItems(items, container, itemHeight) {
    const scrollTop = container.scrollTop;
    const viewportHeight = container.clientHeight;

    const startIndex = Math.floor(scrollTop / itemHeight);
    const endIndex = Math.ceil((scrollTop + viewportHeight) / itemHeight);

    const visibleItems = items.slice(startIndex, endIndex);
    // Render only visible items
}
```

**3. Request Batching:**
```javascript
// Batch multiple requests
const requestQueue = [];
let batchTimer = null;

function queueRequest(request) {
    requestQueue.push(request);

    if (!batchTimer) {
        batchTimer = setTimeout(processBatch, 100);
    }
}

function processBatch() {
    const batch = [...requestQueue];
    requestQueue.length = 0;
    batchTimer = null;

    // Process batch
    executeBatchRequest(batch);
}
```

---

## Troubleshooting

### Common Issues

**WebSocket Disconnect:**
```javascript
// Auto-reconnect
websocket.onclose = () => {
    console.log('Reconnecting in 3s...');
    setTimeout(() => this.connectWebSocket(), 3000);
};
```

**Graph Not Rendering:**
```javascript
// Ensure container has dimensions
const container = document.getElementById('graph-canvas');
if (container.offsetWidth === 0) {
    setTimeout(() => this.initializeGraph(), 100);
}
```

**Memory Leak:**
```javascript
// Clean up event listeners
cleanup() {
    this.websocket?.close();
    this.networkInstance?.destroy();
    document.querySelectorAll('.my-listener')
        .forEach(el => el.removeEventListener('click', handler));
}
```

---

## Related Documentation

- [ChatUI Main README](../README.md)
- [API Documentation](../api/README.md)
- [CSS Styles](../css/)

---

**Last Updated:** January 2025
**Maintainer:** Vera-AI Development Team
**Version:** 1.0.0
