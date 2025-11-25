// Chat.js
(() => {
    class VeraChat {
        constructor() {
            this.messages = [];
            this.files = {};
            this.sessionId = null;
            this.processing = false;
            this.networkData = { nodes: [], edges: [] };
            this.networkInstance = null;
            this.websocket = null;
            this.currentStreamingMessageId = null;
            this.useWebSocket = true;
            this.isResizing = false;
            this.chatPanelWidth = 50;
            this.chatFullscreen = false;
            this.graphFullscreen = false;
            this.activeTab = 'graph';
            
            this.init();
            // this.initResize();
            this.veraRobot = new VeraRobot('vera-robot');
            this.sessionHistory = null; 
            this.toolchainWebSocket = null;
            this.currentExecution = null;
            this.toolchainExecutions = [];

            this.focusWebSocket = null;
            this.currentFocus = null;
            this.focusBoard = {
                progress: [],
                next_steps: [],
                issues: [],
                ideas: [],
                actions: []
            };
            this.focusRunning = false;

            this.memoryEntities = [];
            this.memoryRelationships = [];
            this.memoryQueryResults = null;

            this.notebooks = [];
            this.currentNotebook = null;
            this.notes = [];
            this.currentNote = null;

            this.messages = [];
            this.columns = [];
            this.nextColumnId = 1; // Track next available column ID
            this.tabs = [
                { id: 'chat', label: 'Chat', columnId: 1 },
                { id: 'chat-history', label: 'Chat History', columnId: 1 },
                { id: 'graph', label: 'Knowledge Graph', columnId: 2 },
                { id: 'memory', label: 'Memory', columnId: 2 },
                { id: 'notebook', label: 'Notebook', columnId: 2 },
                { id: 'canvas', label: 'Canvas', columnId: 2 },
                { id: 'visualiser', label: 'Visualiser', columnId: 2 },
                { id: 'toolchain', label: 'Toolchain', columnId: 2 },
                { id: 'focus', label: 'Proactive Focus', columnId: 2 },
                { id: 'training', label: 'Training', columnId: 2 },
                { id: 'orchestration', label: 'Orchestration', columnId: 2 },
                { id: 'analytics', label: 'Analytics', columnId: 2 },
                // { id: 'files', label: 'Files', columnId: 2 },
                { id: 'settings', label: 'Settings', columnId: 2 }
            ];
            this.activeTabPerColumn = {};
            this.draggedTab = null;
            this.networkInstance = null;
            
        }
        
        
        async init() {
            try {
                if (window.updateStartupStatus) {
                    window.updateStartupStatus('Starting session');
                }
                const response = await fetch('http://llm.int:8888/api/session/start', { method: 'POST' });
                const data = await response.json();
                this.sessionId = data.session_id;

                if (window.updateStartupStatus) {
                    window.updateStartupStatus('Building interface');
                }
                document.getElementById('sessionInfo').textContent = `Session: ${this.sessionId}`;
                document.getElementById('connectionStatus').innerHTML = '<span class="status-indicator connected"></span>Connected';
                this.initSessionHistory();
                
                // Create initial 2 columns
                this.createColumn();
                this.createColumn();
                
                // Render tabs in their columns
                this.renderAllTabs();
                
                // Initialize drag and drop
                this.initDragAndDrop();
                
                // Initialize column resizers
                this.initColumnResizers();
                
                // Initialize scroll indicators
                this.initScrollIndicators();
                
                // Set initial active tabs (this will also set up event listeners)
                this.activateTab('chat', 1);
                this.activateTab('graph', 2);
                if (app.initThemeSettings) {
                    app.initThemeSettings();
                }
                if (window.applyThemeToGraph) {
                    window.applyThemeToGraph();
                    console.log('Initial theme applied');
                }
                this.addSystemMessage('Vera connected and ready!');
                
                if (this.useWebSocket) {
                    this.connectWebSocket();
                    this.connectToolchainWebSocket(); 
                    this.connectFocusWebSocket();
                }
            } catch (error) {
                if (window.updateStartupStatus) {
                    window.updateStartupStatus('Connection failed');
                }
                console.error('Init error:', error);
                document.getElementById('connectionStatus').innerHTML = '<span class="status-indicator disconnected"></span>Offline';
                this.addSystemMessage('Connection failed. Running in offline mode.');
                this.veraRobot.setState('error');
            }
            VeraChat.prototype.initModernFeatures()
            // Hide overlay when ready
            setTimeout(() => {
                if (window.hideStartupOverlay) {
                    window.hideStartupOverlay();
                }
            }, 500);
                // DON'T add event listeners here - they're added in activateTab when the chat tab is shown
            }

        initSessionHistory() {
            // Wait for DOM to be ready
            setTimeout(() => {
                const container = document.getElementById('session-history-container');
                if (!container) {
                    console.warn('Session history container not found');
                    return;
                }

                this.sessionHistory = new SessionHistory({
                    containerId: 'session-history-container',
                    apiBaseUrl: 'http://llm.int:8888/api/session',
                    currentSessionId: this.sessionId,
                    onLoadSession: (sessionId) => this.loadHistoricalSession(sessionId),
                    autoRefresh: false,
                    refreshInterval: 30000
                });

                console.log('Session History initialized');
            }, 100);
        }

        async loadHistoricalSession(sessionId) {
            console.log('Loading historical session:', sessionId);
            
            try {
                // Update current session
                this.sessionId = sessionId;
                
                // Update session history UI
                if (this.sessionHistory) {
                    this.sessionHistory.setCurrentSession(sessionId);
                }
                
                // Update session display
                document.getElementById('sessionInfo').textContent = `Session: ${sessionId}`;
                
                // Load session details and messages
                const response = await fetch(
                    `http://llm.int:8888/api/session/${sessionId}/details?include_all_messages=true`
                );
                const data = await response.json();
                
                // Clear existing messages
                this.messages = [];
                const chatMessages = document.getElementById('chatMessages');
                if (chatMessages) {
                    chatMessages.innerHTML = '';
                }
                
                // Display loaded messages
                if (data.messages && data.messages.length > 0) {
                    data.messages.forEach(msg => {
                        if (msg.text) {
                            // Determine role from message metadata or type
                            const role = msg.type === 'user' ? 'user' : 'assistant';
                            this.addMessage(msg.text, role);
                        }
                    });
                    
                    this.addSystemMessage(`Loaded ${data.messages.length} messages from previous session`);
                } else {
                    this.addSystemMessage('Session loaded - no previous messages');
                }
                
                // Reconnect WebSocket for this session
                if (this.websocket) {
                    this.websocket.close();
                }
                if (this.useWebSocket) {
                    this.connectWebSocket();
                }
                
            } catch (error) {
                console.error('Error loading historical session:', error);
                this.addSystemMessage('Error loading session. Please try again.');
            }
        }
        createColumn() {
            const mainContent = document.getElementById('mainContent');
            const id = this.nextColumnId++;
            
            // Store current scroll position
            const scrollLeft = mainContent.scrollLeft;
            
            // Add resizer if not first column
            if (this.columns.length > 0) {
                const resizer = document.createElement('div');
                resizer.className = 'column-resizer';
                resizer.dataset.resizerId = id - 1;
                mainContent.appendChild(resizer);
            }

        const column = document.createElement('div');
            column.className = 'column';
            column.dataset.columnId = id;
            column.innerHTML = `
                <div class="column-header">
                    <div class="column-header-left">
                        <button class="column-btn" onclick="app.toggleColumnFullscreen(${id})" title="Toggle fullscreen">
                            <span class="fullscreen-icon" data-column-fs="${id}">⛶</span>
                        </button>
                        <button class="column-btn" onclick="app.addColumn()" title="Add new column">
                            ➕ Add
                        </button>
                    </div>
                    <span class="column-title" data-column-title="${id}">Column ${id}</span>
                    <div class="column-controls">
                        ${this.columns.length >= 2 ? `<button class="column-btn" onclick="app.removeColumn(${id})" title="Remove column">✕</button>` : ''}
                    </div>
                </div>
                <div class="tabs-container">
                    <div class="tab-bar-wrapper">
                        <div class="scroll-indicator-left"></div>
                        <div class="tab-bar" data-column-id="${id}"></div>
                        <div class="scroll-indicator-right"></div>
                    </div>
                    <div class="tab-content-area" data-column-id="${id}"></div>
                </div>
            `;
            
            mainContent.appendChild(column);
            this.columns.push(id);
            this.activeTabPerColumn[id] = null;
            
            // Restore scroll position to prevent jumping
            requestAnimationFrame(() => {
                mainContent.scrollLeft = scrollLeft;
            });
            
            return id;
        }
        
        renderAllTabs() {
            // Store ALL existing tab contents before clearing (not just active ones)
            const existingContents = new Map();
            document.querySelectorAll('.tab-content').forEach(content => {
                const tabId = content.dataset.tabId;
                // Clone the entire content to preserve state
                existingContents.set(tabId, content.cloneNode(true));
            });
            
            // Clear all tab bars but NOT content areas
            document.querySelectorAll('.tab-bar').forEach(bar => bar.innerHTML = '');
            
            // Only clear content areas that don't have any tabs assigned to them
            document.querySelectorAll('.tab-content-area').forEach(area => {
                const columnId = parseInt(area.dataset.columnId);
                const hasTabsInColumn = this.tabs.some(t => t.columnId === columnId);
                if (!hasTabsInColumn) {
                    area.innerHTML = '';
                }
            });
            
            // Render each tab in its column, passing existing contents
            this.tabs.forEach(tab => {
                this.renderTab(tab, existingContents);
            });
        }

        renderTab(tab, existingContents = null) {
            const tabBar = document.querySelector(`.tab-bar[data-column-id="${tab.columnId}"]`);
            const contentArea = document.querySelector(`.tab-content-area[data-column-id="${tab.columnId}"]`);
            
            if (!tabBar || !contentArea) return;
            
            // Create tab button
            const tabEl = document.createElement('div');
            tabEl.className = 'tab';
            tabEl.textContent = tab.label;
            tabEl.draggable = true;
            tabEl.dataset.tabId = tab.id;
            tabEl.onclick = () => this.activateTab(tab.id, tab.columnId);
            
            tabBar.appendChild(tabEl);
            
            // Check if content already exists in the DOM (being moved between columns)
            let existingContent = document.getElementById(`tab-${tab.id}`);
            
            // If not in DOM, check if we have a stored version (from before re-render)
            if (!existingContent && existingContents && existingContents.has(tab.id)) {
                existingContent = existingContents.get(tab.id);
                existingContent.id = `tab-${tab.id}`; // Ensure ID is set
            }
            
            if (existingContent) {
                // Content exists, move/restore it instead of recreating
                contentArea.appendChild(existingContent);
            } else {
                // Create new tab content only if it truly doesn't exist
                const content = document.createElement('div');
                content.className = 'tab-content';
                content.id = `tab-${tab.id}`;
                content.dataset.tabId = tab.id;
                content.innerHTML = this.getTabContent(tab.id);
                
                contentArea.appendChild(content);
            }
            
            // Update scroll indicators after adding tab
            const wrapper = tabBar.closest('.tab-bar-wrapper');
            if (wrapper) {
                const leftIndicator = wrapper.querySelector('.scroll-indicator-left');
                const rightIndicator = wrapper.querySelector('.scroll-indicator-right');
                this.updateScrollIndicators(tabBar, leftIndicator, rightIndicator);
            }
        }

        getTabContent(tabId) {
            switch(tabId) {
                case 'chat':
                    return `
                        <div id="chatMessages" style="flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 12px;"></div>
                        
                        <div class="input-area">
                            <div class="input-wrapper">
                                <textarea id="messageInput" placeholder="Type your message..." rows="1"></textarea>
                                <button class="send-btn" id="sendBtn" onclick="app.sendMessage()">Send</button>
                            </div>
                        </div>
                    `;
                case 'chat-history':
                    return `
                        <aside class="session-sidebar" style="float:left;">
                            <div id="session-history-container"></div>
                        </aside>
                    `;

                    
                case 'graph':
                    return `
                        <div class="panel-header" draggable="false" style="cursor: default; position: absolute; top: 0; left: 0; right: 0; z-index: 10;">
                            <span>
                                <span class="panel-title">KNOWLEDGE GRAPH</span>
                            </span>
                            <div class="panel-controls">
                                <button class="panel-btn" onclick="app.fitGraph()">🎯 Fit</button>
                                <button class="panel-btn" onclick="app.zoomIn()">🔍+</button>
                                <button class="panel-btn" onclick="app.zoomOut()">🔍-</button>
                                <button class="panel-btn" onclick="app.loadGraph()">🔄</button>
                            </div>
                        </div>
                        <div id="graph"></div>
                        <div class="graph-stats">
                            <div>Nodes: <span id="nodeCount">0</span></div>
                            <div>Edges: <span id="edgeCount">0</span></div>
                        </div>
                        <button id="settings-toggle-btn" onclick="window.GraphAddon && window.GraphAddon.toggleSettings()">⚙️</button>
                        <div id="search-container">
                            <div style="display: flex; align-items: center; gap: 8px;">
                            <input type="text" id="search-input" placeholder="Search nodes...">
                            <button id="search-btn">Search</button>
                            </div>
                            <div id="search-results"></div>
                            
                        </div>
                    `;
                    
                case 'notebook':
                    return `
                        <div style="display: flex; flex-direction: column; height: 100%; overflow: hidden;">
                            <div style="padding: 16px; background: var(--bg); border-bottom: 1px solid #334155;">
                                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                                    <h2 style=" margin: 0;">📓 Notebook</h2>
                                    <div style="display: flex; gap: 8px;">
                                        <button class="panel-btn" onclick="app.createNotebook()">+ New Notebook</button>
                                        <button class="panel-btn" onclick="app.loadNotebooks()">🔄 Refresh</button>
                                    </div>
                                </div>
                                <div style="display: flex; gap: 8px;">
                                    <select id="notebook-selector" onchange="app.switchNotebook(this.value)" 
                                            style="flex: 1; padding: 8px; background: var(--panel-bg); border: 1px solid #334155; color: #e2e8f0; border-radius: 4px;">
                                        <option value="">Select a notebook...</option>
                                    </select>
                                    <button class="panel-btn" onclick="app.deleteCurrentNotebook()" id="delete-notebook-btn" disabled>🗑️</button>
                                </div>
                            </div>
                            <div style="display: flex; flex: 1; overflow: hidden;">
                                <div id="notes-sidebar" style="width: 300px; background: var(--bg); border-right: 1px solid #334155; overflow-y: auto; padding: 12px;">
                                    <div style="margin-bottom: 12px;">
                                        <button class="panel-btn" onclick="app.createNote()" style="width: 100%;">+ New Note</button>
                                    </div>
                                    <div id="notes-list">
                                        <p style="color: #94a3b8; font-size: 13px; text-align: center;">Select a notebook</p>
                                    </div>
                                </div>
                                <div style="flex: 1; display: flex; flex-direction: column; overflow: hidden;">
                                    <div id="note-editor" style="flex: 1; padding: 20px; overflow-y: auto;">
                                        <p style="color: #94a3b8; text-align: center; margin-top: 100px;">Select or create a note to start</p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    `;
                    
                case 'canvas':
                    return `<div id="tab-canvas" style="height: 100%; display: flex; flex-direction: column;"></div>`;
                
                case 'focus':
                    // Container that proactive-focus-manager.js expects
                    return `
                        <div id="focus" style="padding: 20px; overflow-y: auto; height: 100%;">
                            <h2 style="margin-bottom: 16px;">🎯 Proactive Focus</h2>
                            <p style="color: #94a3b8;">Loading focus dashboard...</p>
                        </div>
                    `;

                case 'toolchain':
                    return `
                        <div id="toolchain" style="padding: 20px; overflow-y: auto; height: 100%;">
                            <h2 style="margin-bottom: 16px;">🔧 Toolchain</h2>
                            <p style="color: #94a3b8;">Loading toolchain...</p>
                        </div>
                    `;

                case 'memory':
                    return `
                        <div id="tab-memory" style="padding: 20px; overflow-y: auto; height: 100%;">
                            <div id="memory-content">
                                <p style="color: #94a3b8;">Loading memory system...</p>
                            </div>
                        </div>
                    `;
                    
                case 'orchestration':
                    return `
                        <div id="orchestration-container" style="height: 100%; overflow: hidden;">
                            <!-- Header -->
                            <div style="padding: 16px; background: var(--bg-darker); border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center;">
                                <div>
                                    <h2 style="margin: 0; font-size: 18px;">Task Orchestrator</h2>
                                    <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">
                                        <span id="orch-pool-indicator" style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #ef4444; margin-right: 6px;"></span>
                                        <span id="orch-pool-status">Stopped</span>
                                    </div>
                                </div>
                                
                                <div style="display: flex; gap: 8px;">
                                    <button onclick="app.startOrchestrator()" style="padding: 8px 16px; background: var(--success); border: none; border-radius: 4px; color: white; cursor: pointer; font-size: 12px;">
                                        Start
                                    </button>
                                    <button onclick="app.stopOrchestrator()" style="padding: 8px 16px; background: var(--danger); border: none; border-radius: 4px; color: white; cursor: pointer; font-size: 12px;">
                                        Stop
                                    </button>
                                </div>
                            </div>
                            
                            <!-- Navigation -->
                            <div style="padding: 12px 16px; background: var(--bg-darker); border-bottom: 1px solid var(--border); display: flex; gap: 8px; overflow-x: auto;">
                                <button class="orch-nav-btn active" data-panel="dashboard" onclick="app.switchOrchPanel('dashboard')" style="padding: 8px 16px; background: var(--accent); border: none; border-radius: 4px; color: white; cursor: pointer; font-size: 13px; white-space: nowrap;">
                                    Dashboard
                                </button>
                                <button class="orch-nav-btn" data-panel="workers" onclick="app.switchOrchPanel('workers')" style="padding: 8px 16px; background: var(--bg); border: none; border-radius: 4px; cursor: pointer; font-size: 13px; white-space: nowrap;">
                                    Worker Pools
                                </button>
                                <button class="orch-nav-btn" data-panel="tasks" onclick="app.switchOrchPanel('tasks')" style="padding: 8px 16px; background: var(--bg); border: none; border-radius: 4px; cursor: pointer; font-size: 13px; white-space: nowrap;">
                                    Tasks
                                </button>
                                <button class="orch-nav-btn" data-panel="monitor" onclick="app.switchOrchPanel('monitor')" style="padding: 8px 16px; background: var(--bg); border: none; border-radius: 4px; cursor: pointer; font-size: 13px; white-space: nowrap;">
                                    System Monitor
                                </button>
                                <button class="orch-nav-btn" data-panel="config" onclick="app.switchOrchPanel('config')" style="padding: 8px 16px; background: var(--bg); border: none; border-radius: 4px; cursor: pointer; font-size: 13px; white-space: nowrap;">
                                    Configuration
                                </button>
                            </div>
                            
                            <!-- Content Area -->
                            <div style="height: calc(100% - 120px); overflow-y: auto; padding: 16px;">
                                
                                <!-- Dashboard Panel -->
                                <div id="orch-panel-dashboard" class="orch-panel">
                                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px;">
                                        <!-- Workers Card -->
                                        <div style="padding: 16px; background: var(--bg); border-radius: 8px; border-left: 4px solid var(--accent);">
                                            <div style="font-size: 11px; color: var(--text-muted); text-transform: uppercase; margin-bottom: 8px;">Workers</div>
                                            <div style="font-size: 28px; font-weight: 600;">
                                                <span id="orch-workers-active">0</span>/<span id="orch-workers-total">0</span>
                                            </div>
                                            <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">Active / Total</div>
                                        </div>
                                        
                                        <!-- Queue Card -->
                                        <div style="padding: 16px; background: var(--bg); border-radius: 8px; border-left: 4px solid var(--warning);">
                                            <div style="font-size: 11px; color: var(--text-muted); text-transform: uppercase; margin-bottom: 8px;">Queue</div>
                                            <div style="font-size: 28px; font-weight: 600;" id="orch-queue">0</div>
                                            <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">Pending Tasks</div>
                                        </div>
                                        
                                        <!-- Utilization Card -->
                                        <div style="padding: 16px; background: var(--bg); border-radius: 8px; border-left: 4px solid var(--success);">
                                            <div style="font-size: 11px; color: var(--text-muted); text-transform: uppercase; margin-bottom: 8px;">Utilization</div>
                                            <div style="font-size: 28px; font-weight: 600;" id="orch-dash-util">0%</div>
                                            <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">Worker Usage</div>
                                        </div>
                                        
                                        <!-- CPU Card -->
                                        <div style="padding: 16px; background: var(--bg); border-radius: 8px; border-left: 4px solid var(--danger);">
                                            <div style="font-size: 11px; color: var(--text-muted); text-transform: uppercase; margin-bottom: 8px;">System CPU</div>
                                            <div style="font-size: 28px; font-weight: 600;" id="orch-cpu">0%</div>
                                            <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">Current Usage</div>
                                        </div>
                                    </div>
                                    
                                    <!-- Queue Breakdown -->
                                    <div style="padding: 16px; background: var(--bg); border-radius: 8px; margin-bottom: 16px;">
                                        <h3 style="margin: 0 0 12px 0; font-size: 14px;">Queue by Type</h3>
                                        <div id="orch-queue-breakdown">
                                            <p style="color: var(--text-muted); text-align: center;">No data available</p>
                                        </div>
                                    </div>
                                </div>
                                
                                <!-- Worker Pools Panel (NEW) -->
                                <div id="orch-panel-workers" class="orch-panel" style="display: none;">
                                    <div style="margin-bottom: 16px;">
                                        <h3 style="margin: 0 0 8px 0; font-size: 16px;">Worker Pool Management</h3>
                                        <p style="margin: 0; font-size: 12px; color: var(--text-muted);">
                                            Scale worker pools dynamically based on workload. Each task type has its own dedicated pool.
                                        </p>
                                    </div>
                                    
                                    <div id="orch-worker-pools-list">
                                        <p style="color: var(--text-muted); text-align: center;">Loading worker pools...</p>
                                    </div>
                                </div>
                                
                                <!-- Tasks Panel -->
                                <div id="orch-panel-tasks" class="orch-panel" style="display: none;">
                                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
                                        <!-- Task Submission -->
                                        <div style="padding: 16px; background: var(--bg); border-radius: 8px;">
                                            <h3 style="margin: 0 0 12px 0; font-size: 14px;">Submit Task</h3>
                                            
                                            <label style="display: block; margin-bottom: 8px; font-size: 12px; color: var(--text-muted);">Task Name</label>
                                            <select id="orch-task-name" style="width: 100%; padding: 8px; margin-bottom: 12px; background: var(--bg-darker); border: 1px solid var(--border); border-radius: 4px; color: var(--text);">
                                                <option>Loading...</option>
                                            </select>
                                            
                                            <label style="display: block; margin-bottom: 8px; font-size: 12px; color: var(--text-muted);">Payload (JSON)</label>
                                            <textarea id="orch-task-payload" style="width: 100%; padding: 8px; margin-bottom: 12px; background: var(--bg-darker); border: 1px solid var(--border); border-radius: 4px; color: var(--text); font-family: monospace; font-size: 11px; resize: vertical;" rows="6" placeholder='{"key": "value"}'>{}</textarea>
                                            
                                            <button onclick="app.submitTask()" style="width: 100%; padding: 10px; background: var(--accent); border: none; border-radius: 4px; color: white; cursor: pointer; font-size: 13px;">
                                                Submit Task
                                            </button>
                                        </div>
                                        
                                        <!-- Registered Tasks -->
                                        <div style="padding: 16px; background: var(--bg); border-radius: 8px;">
                                            <h3 style="margin: 0 0 12px 0; font-size: 14px;">Registered Tasks</h3>
                                            <div id="orch-registered-tasks" style="max-height: 400px; overflow-y: auto;">
                                                <p style="color: var(--text-muted);">Loading...</p>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                
                                <!-- System Monitor Panel -->
                                <div id="orch-panel-monitor" class="orch-panel" style="display: none;">
                                    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; margin-bottom: 16px;">
                                        <!-- CPU Monitor -->
                                        <div style="padding: 16px; background: var(--bg); border-radius: 8px;">
                                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                                                <h3 style="margin: 0; font-size: 14px;">CPU Usage</h3>
                                                <span id="orch-mon-cpu" style="font-size: 18px; font-weight: 600;">0%</span>
                                            </div>
                                            <div style="height: 12px; background: var(--bg-darker); border-radius: 6px; overflow: hidden;">
                                                <div id="orch-cpu-bar" style="height: 100%; background: var(--danger); width: 0%; transition: width 0.3s;"></div>
                                            </div>
                                        </div>
                                        
                                        <!-- Memory Monitor -->
                                        <div style="padding: 16px; background: var(--bg); border-radius: 8px;">
                                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                                                <h3 style="margin: 0; font-size: 14px;">Memory Usage</h3>
                                                <span id="orch-mon-memory" style="font-size: 18px; font-weight: 600;">0%</span>
                                            </div>
                                            <div style="height: 12px; background: var(--bg-darker); border-radius: 6px; overflow: hidden;">
                                                <div id="orch-memory-bar" style="height: 100%; background: var(--warning); width: 0%; transition: width 0.3s;"></div>
                                            </div>
                                        </div>
                                    </div>
                                    
                                    <!-- Top Processes -->
                                    <div style="padding: 16px; background: var(--bg); border-radius: 8px;">
                                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                                            <h3 style="margin: 0; font-size: 14px;">Top Processes</h3>
                                            <span style="font-size: 12px; color: var(--text-muted);">
                                                <span id="orch-mon-processes">0</span> active
                                            </span>
                                        </div>
                                        <div id="orch-processes-list" style="max-height: 300px; overflow-y: auto;">
                                            <p style="color: var(--text-muted); text-align: center;">No data</p>
                                        </div>
                                    </div>
                                </div>
                                
                                <!-- Configuration Panel (NEW) -->
                                <div id="orch-panel-config" class="orch-panel" style="display: none;">
                                    <div style="padding: 16px; background: var(--bg); border-radius: 8px; max-width: 600px;">
                                        <h3 style="margin: 0 0 16px 0; font-size: 16px;">Orchestrator Configuration</h3>
                                        <p style="margin: 0 0 24px 0; font-size: 12px; color: var(--text-muted);">
                                            Configure initial worker pool sizes. Changes require reinitialization.
                                        </p>
                                        
                                        <div style="display: grid; gap: 16px;">
                                            <!-- LLM Workers -->
                                            <div>
                                                <label style="display: block; margin-bottom: 8px; font-size: 13px; font-weight: 600;">LLM Workers</label>
                                                <input id="orch-llm-workers" type="number" value="3" min="1" max="20" style="width: 100%; padding: 8px; background: var(--bg-darker); border: 1px solid var(--border); border-radius: 4px; color: var(--text);">
                                                <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">Workers for language model tasks</div>
                                            </div>
                                            
                                            <!-- Tool Workers -->
                                            <div>
                                                <label style="display: block; margin-bottom: 8px; font-size: 13px; font-weight: 600;">Tool Workers</label>
                                                <input id="orch-tool-workers" type="number" value="4" min="1" max="20" style="width: 100%; padding: 8px; background: var(--bg-darker); border: 1px solid var(--border); border-radius: 4px; color: var(--text);">
                                                <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">Workers for tool execution</div>
                                            </div>
                                            
                                            <!-- Whisper Workers -->
                                            <div>
                                                <label style="display: block; margin-bottom: 8px; font-size: 13px; font-weight: 600;">Whisper Workers</label>
                                                <input id="orch-whisper-workers" type="number" value="1" min="0" max="10" style="width: 100%; padding: 8px; background: var(--bg-darker); border: 1px solid var(--border); border-radius: 4px; color: var(--text);">
                                                <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">Workers for audio transcription</div>
                                            </div>
                                            
                                            <!-- Background Workers -->
                                            <div>
                                                <label style="display: block; margin-bottom: 8px; font-size: 13px; font-weight: 600;">Background Workers</label>
                                                <input id="orch-bg-workers" type="number" value="2" min="1" max="10" style="width: 100%; padding: 8px; background: var(--bg-darker); border: 1px solid var(--border); border-radius: 4px; color: var(--text);">
                                                <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">Workers for background/proactive tasks</div>
                                            </div>
                                            
                                            <!-- General Workers -->
                                            <div>
                                                <label style="display: block; margin-bottom: 8px; font-size: 13px; font-weight: 600;">General Workers</label>
                                                <input id="orch-gen-workers" type="number" value="2" min="1" max="10" style="width: 100%; padding: 8px; background: var(--bg-darker); border: 1px solid var(--border); border-radius: 4px; color: var(--text);">
                                                <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">Workers for general tasks</div>
                                            </div>
                                            
                                            <!-- CPU Threshold -->
                                            <div>
                                                <label style="display: block; margin-bottom: 8px; font-size: 13px; font-weight: 600;">CPU Threshold (%)</label>
                                                <input id="orch-cpu-threshold" type="number" value="75" min="50" max="95" step="5" style="width: 100%; padding: 8px; background: var(--bg-darker); border: 1px solid var(--border); border-radius: 4px; color: var(--text);">
                                                <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">Pause workers when CPU exceeds this threshold</div>
                                            </div>
                                        </div>
                                        
                                        <button onclick="app.initializeOrchestrator()" style="width: 100%; padding: 12px; margin-top: 24px; background: var(--accent); border: none; border-radius: 4px; color: white; cursor: pointer; font-size: 14px; font-weight: 600;">
                                            Initialize Orchestrator
                                        </button>
                                    </div>
                                </div>
                                
                            </div>
                        </div>

                        <style>
                            .orch-nav-btn {
                                transition: all 0.2s;
                            }
                            
                            .orch-nav-btn:hover {
                                background: var(--accent-muted) !important;
                            }
                            
                            .orch-nav-btn.active {
                                background: var(--accent) !important;
                                color: white !important;
                            }
                        </style>
                    `;
                case 'analytics':
                    return `<div style="padding: 20px;"><h2 style="margin-bottom: 16px;">📈 Analytics</h2><p style="color: #94a3b8;">Analytics coming soon...</p></div>`;
                    
                case 'files':
                    return `<div style="padding: 20px;"><h2 style="margin-bottom: 16px;">📁 Files</h2><p style="color: #94a3b8;">File management coming soon...</p></div>`;
                    
                case 'settings':
                    return `
                        <div id="settings" style="padding: 20px;">
                        <h2 style="margin-bottom: 16px;">⚙️ Settings</h2>

                        <div id="theme-settings" style="margin-top: 20px;">
                        </div>
                        </div>
                    `;
                default:
                    return `<div style="padding: 20px;"><p>Content for ${tabId}</p></div>`;
            }
        }

        activateTab(tabId, columnId) {
            // Deactivate all tabs in this column
            const column = document.querySelector(`.column[data-column-id="${columnId}"]`);
            if (!column) return;
            
            column.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            column.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            
            // Activate the clicked tab
            const tab = column.querySelector(`.tab[data-tab-id="${tabId}"]`);
            const content = column.querySelector(`.tab-content[data-tab-id="${tabId}"]`);
            
            if (tab) tab.classList.add('active');
            if (content) content.classList.add('active');
            
            this.activeTabPerColumn[columnId] = tabId;
            
            // IMPORTANT: Set this.activeTab FIRST
            this.activeTab = tabId;
            
            // Update column title to match active tab
            const tabData = this.tabs.find(t => t.id === tabId);
            if (tabData) {
                const columnTitle = column.querySelector('.column-title');
                if (columnTitle) {
                    columnTitle.textContent = tabData.label;
                }
            }
            
            // Special handling for different tabs
            if (tabId === 'chat') {
                setTimeout(() => {
                    const input = document.getElementById('messageInput');
                    if (input) {
                        const newInput = input.cloneNode(true);
                        input.parentNode.replaceChild(newInput, input);
                        
                        newInput.addEventListener('input', () => {
                            newInput.style.height = 'auto';
                            newInput.style.height = Math.min(newInput.scrollHeight, 200) + 'px';
                        });
                        
                        newInput.addEventListener('keydown', (e) => {
                            if (e.key === 'Enter' && !e.shiftKey) {
                                e.preventDefault();
                                this.sendMessage();
                            }
                        });
                        
                        newInput.focus();
                    }
                }, 50);
            }
            
            if (tabId === 'graph') {
                setTimeout(() => {
                    if (this.networkInstance) {
                        this.networkInstance.redraw();
                        this.networkInstance.fit();
                    } else {
                        this.initGraph();
                    }
                }, 100);
            }

            if (tabId === 'orchestration') {
                setTimeout(() => {
                    if (this.initOrchestrator) {
                        this.initOrchestrator();
                    }
                }, 50);
            }
    
            if (tabId === 'notebook') {
                setTimeout(() => {
                    if (this.loadNotebooks) {
                        this.loadNotebooks();
                    }
                }, 50);
            }
            
            if (tabId === 'canvas') {
                setTimeout(() => {
                    if (this.initCanvasTab) {
                        this.initCanvasTab();
                    }
                }, 50);
            }

            if (tabId === 'memory') {
                setTimeout(() => {
                    if (this.loadMemoryData) {
                        this.loadMemoryData();
                    }
                }, 50);
            }
            if (tabId === 'settings') {
                setTimeout(() => {
                    if (this.initThemeSettings) {
                        console.log('Initializing theme settings...');
                        this.initThemeSettings();
                    } else {
                        console.warn('initThemeSettings not found');
                    }
                }, 100);
            }

            if (tabId === 'toolchain') {
                setTimeout(() => {
                    if (this.updateToolchainUI) {
                        this.updateToolchainUI();
                    }
                }, 50);
            }
                            
            if (tabId === 'focus') {
                console.log('=== FOCUS TAB ACTIVATED ===');
                console.log('this.activeTab:', this.activeTab);
                console.log('updateFocusUI exists?', typeof this.updateFocusUI);
                console.log('loadFocusStatus exists?', typeof this.loadFocusStatus);
                
                setTimeout(() => {
                    console.log('Focus timeout fired');
                    console.log('Container exists?', !!document.getElementById('tab-focus'));
                    
                    if (this.updateFocusUI) {
                        console.log('Calling updateFocusUI...');
                        this.updateFocusUI();
                    } else {
                        console.log('updateFocusUI not found!');
                    }
                    
                    if (this.loadFocusStatus) {
                        console.log('Calling loadFocusStatus...');
                        this.loadFocusStatus();
                    } else {
                        console.log('loadFocusStatus not found!');
                    }
                }, 50);
            }
        }

        initDragAndDrop() {
            document.addEventListener('dragstart', (e) => {
                const tab = e.target.closest('.tab');
                if (tab) {
                    this.draggedTab = {
                        id: tab.dataset.tabId,
                        sourceColumnId: parseInt(tab.closest('.column').dataset.columnId)
                    };
                    tab.classList.add('dragging');
                    e.dataTransfer.effectAllowed = 'move';
                }
            });

            document.addEventListener('dragend', (e) => {
                const tab = e.target.closest('.tab');
                if (tab) {
                    tab.classList.remove('dragging');
                }
                document.querySelectorAll('.tab-bar').forEach(bar => {
                    bar.classList.remove('drag-over');
                });
                this.draggedTab = null;
            });

            document.addEventListener('dragover', (e) => {
                const tabBar = e.target.closest('.tab-bar');
                if (tabBar && this.draggedTab) {
                    e.preventDefault();
                    tabBar.classList.add('drag-over');
                }
            });

            document.addEventListener('dragleave', (e) => {
                const tabBar = e.target.closest('.tab-bar');
                if (tabBar && !tabBar.contains(e.relatedTarget)) {
                    tabBar.classList.remove('drag-over');
                }
            });

            document.addEventListener('drop', (e) => {
                const tabBar = e.target.closest('.tab-bar');
                if (tabBar && this.draggedTab) {
                    e.preventDefault();
                    tabBar.classList.remove('drag-over');
                    
                    const targetColumnId = parseInt(tabBar.dataset.columnId);
                    this.moveTab(this.draggedTab.id, this.draggedTab.sourceColumnId, targetColumnId);
                }
            });
        }

        moveTab(tabId, fromColumnId, toColumnId) {
            // Update tab data
            const tab = this.tabs.find(t => t.id === tabId);
            if (!tab) return;
            
            tab.columnId = toColumnId;
            
            // Re-render all tabs (this will now preserve content)
            this.renderAllTabs();
            
            // Reactivate tabs in all columns
            Object.keys(this.activeTabPerColumn).forEach(colId => {
                const activeTabId = this.activeTabPerColumn[colId];
                if (activeTabId) {
                    // Check if the active tab is still in this column
                    const tabStillInColumn = this.tabs.find(t => t.id === activeTabId && t.columnId == colId);
                    if (tabStillInColumn) {
                        this.activateTab(activeTabId, parseInt(colId));
                    } else if (parseInt(colId) === toColumnId && tabId === activeTabId) {
                        // The moved tab was active in the source column, activate it in the target column
                        this.activateTab(tabId, toColumnId);
                    } else {
                        // Find first tab in this column and activate it
                        const firstTabInColumn = this.tabs.find(t => t.columnId == colId);
                        if (firstTabInColumn) {
                            this.activateTab(firstTabInColumn.id, parseInt(colId));
                        }
                    }
                }
            });
            
            // Activate the moved tab in its new column
            this.activateTab(tabId, toColumnId);
            
            // Re-initialize drag and drop
            this.initDragAndDrop();
            
            console.log(`Moved ${tabId} from column ${fromColumnId} to ${toColumnId}`);
        }

        initColumnResizers() {
            document.querySelectorAll('.column-resizer').forEach(resizer => {
                let isResizing = false;
                let startX, startWidths;

                resizer.addEventListener('mousedown', (e) => {
                    isResizing = true;
                    startX = e.clientX;
                    resizer.classList.add('resizing');

                    const leftColumn = resizer.previousElementSibling;
                    const rightColumn = resizer.nextElementSibling;

                    if (leftColumn && rightColumn) {
                        startWidths = {
                            left: leftColumn.offsetWidth,
                            right: rightColumn.offsetWidth
                        };
                    }

                    document.body.style.cursor = 'col-resize';
                    document.body.style.userSelect = 'none';
                    e.preventDefault();
                });

                document.addEventListener('mousemove', (e) => {
                    if (!isResizing) return;

                    const deltaX = e.clientX - startX;
                    const leftColumn = resizer.previousElementSibling;
                    const rightColumn = resizer.nextElementSibling;

                    if (leftColumn && rightColumn && startWidths) {
                        const newLeftWidth = startWidths.left + deltaX;
                        const newRightWidth = startWidths.right - deltaX;

                        if (newLeftWidth > 300 && newRightWidth > 300) {
                            leftColumn.style.flex = `0 0 ${newLeftWidth}px`;
                            rightColumn.style.flex = `0 0 ${newRightWidth}px`;
                            
                            if (this.networkInstance) {
                                this.networkInstance.redraw();
                            }
                        }
                    }
                });

                document.addEventListener('mouseup', () => {
                    if (isResizing) {
                        isResizing = false;
                        resizer.classList.remove('resizing');
                        document.body.style.cursor = '';
                        document.body.style.userSelect = '';
                    }
                });
            });
        }

        addColumn() {
            const newColumnId = this.createColumn();
            this.initColumnResizers();
            
            // Find first tab in column 1 to move (or any unused tab)
            const tabToMove = this.tabs.find(t => t.columnId === this.columns[0]);
            if (tabToMove) {
                tabToMove.columnId = newColumnId;
                this.renderAllTabs();
                this.initDragAndDrop();
                this.initScrollIndicators();
                
                // Reactivate existing tabs
                Object.keys(this.activeTabPerColumn).forEach(colId => {
                    const activeTabId = this.activeTabPerColumn[colId];
                    const tabInColumn = this.tabs.find(t => t.id === activeTabId && t.columnId == colId);
                    if (tabInColumn) {
                        this.activateTab(activeTabId, parseInt(colId));
                    }
                });
                
                // Activate the moved tab in the new column
                this.activateTab(tabToMove.id, newColumnId);
            } else {
                this.initScrollIndicators();
            }
            
            console.log('Added column', newColumnId);
        }

        removeColumn(columnId) {
            if (this.columns.length <= 2) {
                alert('Must keep at least 2 columns');
                return;
            }

            // Move tabs from this column to first column
            const firstColumnId = this.columns[0];
            this.tabs.forEach(tab => {
                if (tab.columnId === columnId) {
                    tab.columnId = firstColumnId;
                }
            });

            // Remove column DOM
            const column = document.querySelector(`.column[data-column-id="${columnId}"]`);
            const resizer = column.previousElementSibling;
            if (resizer && resizer.classList.contains('column-resizer')) {
                resizer.remove();
            }
            column.remove();

            // Update columns array
            this.columns = this.columns.filter(id => id !== columnId);
            
            // Remove from active tabs tracking
            delete this.activeTabPerColumn[columnId];
            
            // Reset flex on all remaining columns so they spread out evenly
            document.querySelectorAll('.column').forEach(col => {
                col.style.flex = '1';
            });
            
            // Re-render
            this.renderAllTabs();
            this.initDragAndDrop();
            this.initColumnResizers();
            this.initScrollIndicators();
            
            // Reactivate tabs in remaining columns
            this.columns.forEach(colId => {
                const tabInColumn = this.tabs.find(t => t.columnId === colId);
                if (tabInColumn) {
                    this.activateTab(tabInColumn.id, colId);
                }
            });
            
            console.log(`Removed column ${columnId}, tabs moved to column ${firstColumnId}`);
        }

        initScrollIndicators() {
            document.querySelectorAll('.tab-bar').forEach(tabBar => {
                const wrapper = tabBar.closest('.tab-bar-wrapper');
                const leftIndicator = wrapper.querySelector('.scroll-indicator-left');
                const rightIndicator = wrapper.querySelector('.scroll-indicator-right');
                
                // Update on scroll
                tabBar.addEventListener('scroll', () => {
                    this.updateScrollIndicators(tabBar, leftIndicator, rightIndicator);
                });
                
                // Initial update
                this.updateScrollIndicators(tabBar, leftIndicator, rightIndicator);
            });
            
            // Update on window resize
            window.addEventListener('resize', () => {
                document.querySelectorAll('.tab-bar').forEach(bar => {
                    const wrapper = bar.closest('.tab-bar-wrapper');
                    const leftIndicator = wrapper.querySelector('.scroll-indicator-left');
                    const rightIndicator = wrapper.querySelector('.scroll-indicator-right');
                    this.updateScrollIndicators(bar, leftIndicator, rightIndicator);
                });
            });
        }

        updateScrollIndicators(tabBar, leftIndicator, rightIndicator) {
            if (!tabBar || !leftIndicator || !rightIndicator) return;
            
            const scrollLeft = tabBar.scrollLeft;
            const scrollWidth = tabBar.scrollWidth;
            const clientWidth = tabBar.clientWidth;
            const maxScroll = scrollWidth - clientWidth;
            
            // Show left indicator if scrolled right
            if (scrollLeft > 10) {
                leftIndicator.classList.add('visible');
            } else {
                leftIndicator.classList.remove('visible');
            }
            
            // Show right indicator if can scroll more
            if (scrollLeft < maxScroll - 10) {
                rightIndicator.classList.add('visible');
            } else {
                rightIndicator.classList.remove('visible');
            }
        }
        
        initResize() {
            const resizer = document.getElementById('resizer');
            const chatPanel = document.getElementById('chatPanel');
            const graphPanel = document.getElementById('graphPanel');
            const mainContent = document.querySelector('.main-content');
            
            let startX, startChatWidth;
            
            const startResize = (e) => {
                this.isResizing = true;
                startX = e.clientX;
                startChatWidth = chatPanel.offsetWidth;
                resizer.classList.add('resizing');
                document.body.style.cursor = 'col-resize';
                document.body.style.userSelect = 'none';
            };
            
            const doResize = (e) => {
                if (!this.isResizing) return;
                
                const deltaX = e.clientX - startX;
                const newChatWidth = startChatWidth + deltaX;
                const containerWidth = mainContent.offsetWidth;
                const percentage = (newChatWidth / containerWidth) * 100;
                
                if (percentage >= 20 && percentage <= 80) {
                    this.chatPanelWidth = percentage;
                    chatPanel.style.width = `${percentage}%`;
                    graphPanel.style.width = `${100 - percentage}%`;
                    resizer.style.left = `${percentage}%`;
                    
                    if (this.networkInstance) {
                        this.networkInstance.redraw();
                    }
                }
            };
            
            const stopResize = () => {
                this.isResizing = false;
                resizer.classList.remove('resizing');
                document.body.style.cursor = '';
                document.body.style.userSelect = '';
            };
            
            resizer.addEventListener('mousedown', startResize);
            document.addEventListener('mousemove', doResize);
            document.addEventListener('mouseup', stopResize);
        }      

        toggleFullscreen(panel) {
            const chatPanel = document.getElementById('chatPanel');
            const graphPanel = document.getElementById('graphPanel');
            const chatBtn = document.getElementById('chatFullscreenBtn');
            const graphBtn = document.getElementById('graphFullscreenBtn');
            
            if (panel === 'chat') {
                this.chatFullscreen = !this.chatFullscreen;
                
                if (this.chatFullscreen) {
                    chatPanel.classList.add('fullscreen');
                    chatBtn.textContent = '⛶ Exit';
                    this.graphFullscreen = false;
                    graphPanel.classList.remove('fullscreen');
                } else {
                    chatPanel.classList.remove('fullscreen');
                    chatBtn.textContent = '⛶';
                }
            } else if (panel === 'graph') {
                this.graphFullscreen = !this.graphFullscreen;
                
                if (this.graphFullscreen) {
                    graphPanel.classList.add('fullscreen');
                    graphBtn.textContent = '⛶ Exit';
                    this.chatFullscreen = false;
                    chatPanel.classList.remove('fullscreen');
                    
                    setTimeout(() => {
                        if (this.networkInstance) {
                            this.networkInstance.redraw();
                            this.networkInstance.fit();
                        }
                    }, 350);
                } else {
                    graphPanel.classList.remove('fullscreen');
                    graphBtn.textContent = '⛶';
                    
                    setTimeout(() => {
                        if (this.networkInstance) {
                            this.networkInstance.redraw();
                        }
                    }, 350);
                }
            }
        }
        
        connectWebSocket() {
            if (!this.sessionId) return;
            
            const wsUrl = `ws://llm.int:8888/ws/chat/${this.sessionId}`;
            this.websocket = new WebSocket(wsUrl);
            
            this.websocket.onopen = () => {
                console.log('WebSocket connected');
                document.getElementById('connectionStatus').innerHTML = '<span class="status-indicator connected"></span>Connected (WS)';
                this.veraRobot.setState('idle');
            };
            
            this.websocket.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleWebSocketMessage(data);
                } catch (error) {
                    console.error('WebSocket message parse error:', error);
                }
            };
            
            this.websocket.onerror = (error) => {
                console.error('WebSocket error:', error);
            };
            
            this.websocket.onclose = (event) => {
                console.log('WebSocket disconnected');
                document.getElementById('connectionStatus').innerHTML = '<span class="status-indicator disconnected"></span>Disconnected';
                this.veraRobot.setState('error');
                if (event.code !== 1000 && this.sessionId) {
                    setTimeout(() => this.connectWebSocket(), 3000);
                }
            };
        }
        
        fitGraph() {
            if (this.networkInstance) {
                this.networkInstance.fit();
            }
        }
        
        zoomIn() {
            if (this.networkInstance) {
                const scale = this.networkInstance.getScale();
                this.networkInstance.moveTo({ scale: scale * 1.2 });
            }
        }
        
        zoomOut() {
            if (this.networkInstance) {
                const scale = this.networkInstance.getScale();
                this.networkInstance.moveTo({ scale: scale * 0.8 });
            }
        }
        toggleColumnFullscreen(columnId) {
            const column = document.querySelector(`.column[data-column-id="${columnId}"]`);
            if (!column) return;
            
            const isFullscreen = column.classList.contains('column-fullscreen');
            const icon = document.querySelector(`.fullscreen-icon[data-column-fs="${columnId}"]`);
            
            // Remove fullscreen from all columns first
            document.querySelectorAll('.column').forEach(col => {
                col.classList.remove('column-fullscreen');
                const colId = col.dataset.columnId;
                const colIcon = document.querySelector(`.fullscreen-icon[data-column-fs="${colId}"]`);
                if (colIcon) colIcon.textContent = '⛶';
            });
            
            // Hide/show resizers
            document.querySelectorAll('.column-resizer').forEach(resizer => {
                resizer.style.display = isFullscreen ? '' : 'none';
            });
            
            if (!isFullscreen) {
                // Enter fullscreen
                column.classList.add('column-fullscreen');
                if (icon) icon.textContent = '⛶ Exit';
                
                // Hide other columns
                document.querySelectorAll('.column').forEach(col => {
                    if (col.dataset.columnId !== String(columnId)) {
                        col.style.display = 'none';
                    }
                });
                
                // Redraw graph if it's in this column
                setTimeout(() => {
                    if (this.networkInstance) {
                        this.networkInstance.redraw();
                        this.networkInstance.fit();
                    }
                }, 100);
            } else {
                // Exit fullscreen
                if (icon) icon.textContent = '⛶';
                
                // Show all columns
                document.querySelectorAll('.column').forEach(col => {
                    col.style.display = '';
                    col.style.flex = '1';
                });
                
                // Show resizers
                document.querySelectorAll('.column-resizer').forEach(resizer => {
                    resizer.style.display = '';
                });
                
                // Redraw graph
                setTimeout(() => {
                    if (this.networkInstance) {
                        this.networkInstance.redraw();
                        this.networkInstance.fit();
                    }
                }, 100);
            }
        }

    }

    class FloatingPanel {
        constructor(options) {
            this.id = options.id || `floating-panel-${Date.now()}`;
            this.title = options.title || "Panel";
            this.content = options.content || "";
            this.container = options.container || document.body;

            this.isFloating = false;
            this.createPanel();
            this.initDrag();
            this.restoreState();
        }

        createPanel() {
            this.panel = document.createElement("div");
            this.panel.className = "floating-panel";
            this.panel.innerHTML = `
            <div class="fp-header">
                <span class="fp-title">${this.title}</span>
                <button class="fp-toggle" title="Pop out / Dock">⇕</button>
            </div>
            <div class="fp-content">${this.content}</div>
            `;

            // Scoped style for panels only
            const style = document.createElement("style");
            style.textContent = `
            .floating-panel {
                background: rgba(30,30,30,0.96);
                color: #fff;
                border: 1px solid #555;
                border-radius: 0.5rem;
                width: 300px;
                max-width: 90vw;
                box-shadow: 0 0 10px rgba(0,0,0,0.5);
                font-family: sans-serif;
                margin: 0.5rem 0;
                position: relative;
            }
            .floating-panel.floating {
                position: fixed !important;
                width: 300px;
                height: auto;
                z-index: 9999;
                cursor: grab;
            }
            .fp-header {
                background: #444;
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 0.3rem 0.5rem;
                border-bottom: 1px solid #555;
                cursor: grab;
                border-radius: 0.5rem 0.5rem 0 0;
            }
            .fp-toggle {
                background: #666;
                color: white;
                border: none;
                border-radius: 0.3rem;
                cursor: pointer;
                padding: 0.2rem 0.4rem;
            }
            .fp-content {
                padding: 0.5rem;
            }
            `;
            document.head.appendChild(style);

            this.container.appendChild(this.panel);

            this.toggleBtn = this.panel.querySelector(".fp-toggle");
            this.toggleBtn.addEventListener("click", () => {
                if (this.isFloating) this.dock();
                else this.float();
            });
        }

        initDrag() {
            const header = this.panel.querySelector(".fp-header");
            let isDragging = false;
            let offsetX = 0, offsetY = 0;

            header.addEventListener("mousedown", (e) => {
                if (!this.isFloating) return;
                isDragging = true;
                const rect = this.panel.getBoundingClientRect();
                offsetX = e.clientX - rect.left;
                offsetY = e.clientY - rect.top;
                this.panel.style.cursor = "grabbing";
                e.preventDefault();
            });

            document.addEventListener("mousemove", (e) => {
                if (!isDragging) return;
                // Compute new position but keep within screen
                let x = e.clientX - offsetX;
                let y = e.clientY - offsetY;

                const panelRect = this.panel.getBoundingClientRect();
                const vw = window.innerWidth;
                const vh = window.innerHeight;

                // keep fully visible
                if (x < 0) x = 0;
                if (y < 0) y = 0;
                if (x + panelRect.width > vw) x = vw - panelRect.width;
                if (y + panelRect.height > vh) y = vh - panelRect.height;

                this.panel.style.left = `${x}px`;
                this.panel.style.top = `${y}px`;
                this.panel.style.bottom = "";
                this.panel.style.right = "";
            });

            document.addEventListener("mouseup", () => {
                if (isDragging) {
                    isDragging = false;
                    this.panel.style.cursor = "grab";
                    this.savePosition();
                }
            });
        }

        float() {
            document.body.appendChild(this.panel);
            this.panel.classList.add("floating");
            this.isFloating = true;
            this.toggleBtn.textContent = "⇓";
            this.restorePosition();

            // Default if no stored pos
            if (!this.panel.style.left && !this.panel.style.top) {
                this.panel.style.left = "calc(100vw - 320px)";
                this.panel.style.top = "80vh";
            }

            localStorage.setItem(`${this.id}-floating`, "true");
        }

        dock() {
            this.container.appendChild(this.panel);
            this.panel.classList.remove("floating");
            this.panel.style.left = "";
            this.panel.style.top = "";
            this.panel.style.bottom = "";
            this.panel.style.right = "";
            this.isFloating = false;
            this.toggleBtn.textContent = "⇕";
            localStorage.setItem(`${this.id}-floating`, "false");
        }

        savePosition() {
            if (!this.isFloating) return;
            localStorage.setItem(`${this.id}-pos`, JSON.stringify({
                left: this.panel.style.left,
                top: this.panel.style.top
            }));
        }

        restorePosition() {
            const saved = localStorage.getItem(`${this.id}-pos`);
            if (saved) {
                const { left, top } = JSON.parse(saved);
                this.panel.style.left = left;
                this.panel.style.top = top;
            }
        }

        restoreState() {
            const isFloating = localStorage.getItem(`${this.id}-floating`) === "true";
            if (isFloating) this.float();
        }
    }

    window.VeraChat = VeraChat;
    window.app = new VeraChat();

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            const fullscreenColumn = document.querySelector('.column-fullscreen');
            if (fullscreenColumn && window.app) {
                const columnId = parseInt(fullscreenColumn.dataset.columnId);
                window.app.toggleColumnFullscreen(columnId);
            }
        }
    });
    const notesPanel = new FloatingPanel({
        id: "notesPanel",
        title: "Quick Notes",
        content: `<textarea style="width:100%;height:100px"></textarea>`,
        container: document.getElementById("tab-memory")
    });

    // Float it immediately so it appears on screen
    notesPanel.float();
})();