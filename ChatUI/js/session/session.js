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
                { id: 'terminal', label: 'Terminal', columnId: 1 },
                { id: 'agents', label: 'Agents', columnId: 1 },
                { id: 'organiser', label: 'Organiser', columnId: 1 },
                { id: 'graph', label: 'Knowledge Graph', columnId: 2 },
                { id: 'memory', label: 'Memory', columnId: 2 },
                { id: 'notebook', label: 'Notebook', columnId: 2 },
                { id: 'canvas', label: 'Canvas', columnId: 2 },
                { id: 'visualiser', label: 'Visualiser', columnId: 2 },
                { id: 'toolchain', label: 'Toolchain', columnId: 2 },
                { id: 'focus', label: 'Proactive Focus', columnId: 2 },
                { id: 'training', label: 'Training', columnId: 2 },
                { id: 'orchestration', label: 'Orchestration', columnId: 2 },
                { id: 'ollama', label: 'Ollama Manager', columnId: 2 },
                // { id: 'analytics', label: 'Analytics', columnId: 2 },
                // { id: 'files', label: 'Files', columnId: 2 },
                { id: 'settings', label: 'Settings', columnId: 1 },
                { id: 'ml', label: 'Machine Learning', columnId: 2 },
                { id: 'config', label: 'Configuration', columnId: 2 }

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
            // VeraChat.prototype.initModernFeatures()
            // VeraChat.prototype.initOllama()
            // ✅ CALL THESE AFTER init() completes, with existence checks
            if (typeof this.initModernFeatures === 'function') {
                this.initModernFeatures();
            } else {
                console.warn('initModernFeatures not loaded yet');
            }
            
            if (typeof this.initOllama === 'function') {
                this.initOllama();
            } else {
                console.warn('initOllama not loaded yet');
            }

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
                // 2. ADD THIS CASE TO getTabContent() function (around line 500+):
                case 'ml':
                    return `
                        <div id="ml-container" style="padding: 24px; height: 100%; overflow-y: auto;">
                            
                            <!-- Header -->
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 2px solid var(--border);">
                                <div>
                                    <h2 style="margin: 0 0 8px 0; font-size: 24px; font-weight: 700;">Machine Learning Lab</h2>
                                    <p style="margin: 0; color: var(--text-muted); font-size: 14px;">Train and test AI models</p>
                                </div>
                                
                                <div style="display: flex; align-items: center; gap: 12px;">
                                    <div style="display: flex; align-items: center; gap: 8px; padding: 8px 16px; background: var(--bg-darker); border-radius: 8px;">
                                        <div id="ml-status-indicator" style="width: 12px; height: 12px; border-radius: 50%; background: var(--text-muted);"></div>
                                        <span id="ml-status-text" style="font-size: 13px; font-weight: 600;">Ready</span>
                                    </div>
                                </div>
                            </div>
                            
                            <!-- Navigation -->
                            <div style="display: flex; gap: 12px; margin-bottom: 24px; flex-wrap: wrap;">
                                <button class="ml-nav-btn active" data-panel="models" onclick="app.switchMLPanel('models')"
                                        style="padding: 12px 24px; background: var(--accent); border: none; border-radius: 8px; color: white; cursor: pointer; font-size: 14px; font-weight: 600; transition: all 0.2s;">
                                    📊 Models
                                </button>
                                <button class="ml-nav-btn" data-panel="tictactoe" onclick="app.switchMLPanel('tictactoe')"
                                        style="padding: 12px 24px; background: var(--bg-darker); border: none; border-radius: 8px; color: var(--text); cursor: pointer; font-size: 14px; font-weight: 600; transition: all 0.2s;">
                                    🎮 Tic-Tac-Toe AI
                                </button>
                                <button class="ml-nav-btn" data-panel="crypto" onclick="app.switchMLPanel('crypto')"
                                        style="padding: 12px 24px; background: var(--bg-darker); border: none; border-radius: 8px; color: var(--text); cursor: pointer; font-size: 14px; font-weight: 600; transition: all 0.2s;">
                                    📈 Crypto Predictor
                                </button>
                                <button class="ml-nav-btn" data-panel="training" onclick="app.switchMLPanel('training')"
                                        style="padding: 12px 24px; background: var(--bg-darker); border: none; border-radius: 8px; color: var(--text); cursor: pointer; font-size: 14px; font-weight: 600; transition: all 0.2s;">
                                    🎯 Training
                                </button>
                            </div>
                            
                            <!-- Models Overview Panel -->
                            <div id="ml-panel-models" class="ml-panel">
                                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px;">
                                    <!-- Tic-Tac-Toe Card -->
                                    <div style="background: var(--bg); padding: 24px; border-radius: 12px; border-left: 4px solid #4CAF50;">
                                        <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px;">
                                            <div style="font-size: 48px;">🎮</div>
                                            <div>
                                                <h3 style="margin: 0 0 4px 0; font-size: 18px; font-weight: 600;">Tic-Tac-Toe AI</h3>
                                                <div style="font-size: 12px; color: var(--text-muted);">Policy Gradient Network</div>
                                            </div>
                                        </div>
                                        
                                        <div style="display: flex; flex-direction: column; gap: 8px; margin-bottom: 16px;">
                                            <div style="display: flex; justify-content: space-between; font-size: 13px;">
                                                <span style="color: var(--text-muted);">Win Rate</span>
                                                <span id="ttt-win-rate" style="font-weight: 600;">0%</span>
                                            </div>
                                            <div style="display: flex; justify-content: space-between; font-size: 13px;">
                                                <span style="color: var(--text-muted);">Games Played</span>
                                                <span id="ttt-games" style="font-weight: 600;">0</span>
                                            </div>
                                            <div style="display: flex; justify-content: space-between; font-size: 13px;">
                                                <span style="color: var(--text-muted);">Network Size</span>
                                                <span style="font-weight: 600;">9→18→9</span>
                                            </div>
                                        </div>
                                        
                                        <button onclick="app.switchMLPanel('tictactoe')" 
                                                style="width: 100%; padding: 10px; background: #4CAF50; border: none; border-radius: 6px; color: white; cursor: pointer; font-weight: 600;">
                                            Play Game
                                        </button>
                                    </div>
                                    
                                    <!-- Crypto Predictor Card -->
                                    <div style="background: var(--bg); padding: 24px; border-radius: 12px; border-left: 4px solid #2196F3;">
                                        <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px;">
                                            <div style="font-size: 48px;">📈</div>
                                            <div>
                                                <h3 style="margin: 0 0 4px 0; font-size: 18px; font-weight: 600;">Crypto Predictor</h3>
                                                <div style="font-size: 12px; color: var(--text-muted);">Vanilla RNN</div>
                                            </div>
                                        </div>
                                        
                                        <div style="display: flex; flex-direction: column; gap: 8px; margin-bottom: 16px;">
                                            <div style="display: flex; justify-content: space-between; font-size: 13px;">
                                                <span style="color: var(--text-muted);">Accuracy</span>
                                                <span id="crypto-accuracy" style="font-weight: 600;">--</span>
                                            </div>
                                            <div style="display: flex; justify-content: space-between; font-size: 13px;">
                                                <span style="color: var(--text-muted);">Status</span>
                                                <span id="crypto-status" style="font-weight: 600;">Idle</span>
                                            </div>
                                            <div style="display: flex; justify-content: space-between; font-size: 13px;">
                                                <span style="color: var(--text-muted);">Network Size</span>
                                                <span style="font-weight: 600;">4→16→1</span>
                                            </div>
                                        </div>
                                        
                                        <button onclick="app.switchMLPanel('crypto')" 
                                                style="width: 100%; padding: 10px; background: #2196F3; border: none; border-radius: 6px; color: white; cursor: pointer; font-weight: 600;">
                                            View Predictions
                                        </button>
                                    </div>
                                </div>
                            </div>
                            
                            <!-- Tic-Tac-Toe Panel -->
                            <div id="ml-panel-tictactoe" class="ml-panel" style="display: none;">
                                <div style="max-width: 800px; margin: 0 auto;">
                                    <div style="background: var(--bg); padding: 24px; border-radius: 12px; margin-bottom: 20px;">
                                        <h3 style="margin: 0 0 16px 0; font-size: 20px; font-weight: 600;">Play Against the AI</h3>
                                        
                                        <div style="display: grid; grid-template-columns: 1fr 300px; gap: 24px;">
                                            <!-- Game Board -->
                                            <div>
                                                <div id="ttt-board" style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; aspect-ratio: 1; max-width: 400px; margin: 0 auto;">
                                                    <!-- Cells generated by JS -->
                                                </div>
                                                
                                                <div style="text-align: center; margin-top: 20px;">
                                                    <div id="ttt-message" style="font-size: 18px; font-weight: 600; margin-bottom: 12px; min-height: 30px;">
                                                        Your turn (O)
                                                    </div>
                                                    <button onclick="app.resetTicTacToe()" 
                                                            style="padding: 10px 24px; background: var(--accent); border: none; border-radius: 6px; color: white; cursor: pointer; font-weight: 600;">
                                                        New Game
                                                    </button>
                                                </div>
                                            </div>
                                            
                                            <!-- Stats Sidebar -->
                                            <div>
                                                <div style="background: var(--bg-darker); padding: 16px; border-radius: 8px; margin-bottom: 16px;">
                                                    <h4 style="margin: 0 0 12px 0; font-size: 14px; text-transform: uppercase; color: var(--text-muted);">Game Stats</h4>
                                                    <div style="display: flex; flex-direction: column; gap: 8px;">
                                                        <div style="display: flex; justify-content: space-between;">
                                                            <span>AI Wins</span>
                                                            <span id="ttt-ai-wins" style="font-weight: 600; color: #f44336;">0</span>
                                                        </div>
                                                        <div style="display: flex; justify-content: space-between;">
                                                            <span>Your Wins</span>
                                                            <span id="ttt-human-wins" style="font-weight: 600; color: #4CAF50;">0</span>
                                                        </div>
                                                        <div style="display: flex; justify-content: space-between;">
                                                            <span>Draws</span>
                                                            <span id="ttt-draws" style="font-weight: 600;">0</span>
                                                        </div>
                                                    </div>
                                                </div>
                                                
                                                <div style="background: var(--bg-darker); padding: 16px; border-radius: 8px;">
                                                    <h4 style="margin: 0 0 12px 0; font-size: 14px; text-transform: uppercase; color: var(--text-muted);">AI Confidence</h4>
                                                    <div id="ttt-confidence" style="font-size: 12px; color: var(--text-muted);">
                                                        Waiting for move...
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <!-- Crypto Predictor Panel -->
                            <div id="ml-panel-crypto" class="ml-panel" style="display: none;">
                                <div style="background: var(--bg); padding: 24px; border-radius: 12px; margin-bottom: 20px;">
                                    <h3 style="margin: 0 0 16px 0; font-size: 20px; font-weight: 600;">BTC/USDT Price Predictor</h3>
                                    
                                    <!-- Controls -->
                                    <div style="display: flex; gap: 12px; margin-bottom: 24px; flex-wrap: wrap;">
                                        <button id="crypto-start-btn" onclick="app.startCryptoPredictor()" 
                                                style="padding: 10px 20px; background: var(--success); border: none; border-radius: 6px; color: white; cursor: pointer; font-weight: 600;">
                                            ▶ Start Learning
                                        </button>
                                        <button id="crypto-stop-btn" onclick="app.stopCryptoPredictor()" disabled
                                                style="padding: 10px 20px; background: var(--danger); border: none; border-radius: 6px; color: white; cursor: pointer; font-weight: 600;">
                                            ⏸ Stop
                                        </button>
                                        
                                        <select id="crypto-symbol" style="padding: 10px; background: var(--bg-darker); border: 1px solid var(--border); border-radius: 6px; color: var(--text);">
                                            <option>BTC/USDT</option>
                                            <option>ETH/USDT</option>
                                            <option>SOL/USDT</option>
                                        </select>
                                        
                                        <select id="crypto-timeframe" style="padding: 10px; background: var(--bg-darker); border: 1px solid var(--border); border-radius: 6px; color: var(--text);">
                                            <option>1m</option>
                                            <option>5m</option>
                                            <option>15m</option>
                                            <option>1h</option>
                                        </select>
                                    </div>
                                    
                                    <!-- Stats Grid -->
                                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px;">
                                        <div style="background: var(--bg-darker); padding: 16px; border-radius: 8px;">
                                            <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 4px;">ROLLING ACCURACY</div>
                                            <div id="crypto-accuracy-val" style="font-size: 28px; font-weight: 700;">--%</div>
                                        </div>
                                        <div style="background: var(--bg-darker); padding: 16px; border-radius: 8px;">
                                            <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 4px;">PREDICTIONS</div>
                                            <div id="crypto-predictions" style="font-size: 28px; font-weight: 700;">0</div>
                                        </div>
                                        <div style="background: var(--bg-darker); padding: 16px; border-radius: 8px;">
                                            <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 4px;">CURRENT PRICE</div>
                                            <div id="crypto-current-price" style="font-size: 28px; font-weight: 700;">--</div>
                                        </div>
                                        <div style="background: var(--bg-darker); padding: 16px; border-radius: 8px;">
                                            <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 4px;">NEXT PREDICTION</div>
                                            <div id="crypto-next-pred" style="font-size: 28px; font-weight: 700;">--</div>
                                        </div>
                                    </div>
                                    
                                    <!-- Prediction History -->
                                    <div style="background: var(--bg-darker); padding: 20px; border-radius: 8px;">
                                        <h4 style="margin: 0 0 16px 0; font-size: 14px; text-transform: uppercase; color: var(--text-muted);">Recent Predictions</h4>
                                        <div id="crypto-history" style="max-height: 300px; overflow-y: auto;">
                                            <div style="text-align: center; padding: 40px; color: var(--text-muted);">
                                                Start learning to see predictions...
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <!-- Training Panel -->
                            <div id="ml-panel-training" class="ml-panel" style="display: none;">
                                <div style="background: var(--bg); padding: 24px; border-radius: 12px;">
                                    <h3 style="margin: 0 0 16px 0; font-size: 20px; font-weight: 600;">Training Dashboard</h3>
                                    
                                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 16px;">
                                        <div style="background: var(--bg-darker); padding: 20px; border-radius: 8px;">
                                            <h4 style="margin: 0 0 12px 0;">Tic-Tac-Toe</h4>
                                            <div style="font-size: 13px; color: var(--text-muted); margin-bottom: 8px;">
                                                Learning through self-play and human games
                                            </div>
                                            <div id="ttt-training-info" style="font-size: 12px; margin-top: 12px; padding: 12px; background: var(--bg); border-radius: 4px;">
                                                Play games to train the network
                                            </div>
                                        </div>
                                        
                                        <div style="background: var(--bg-darker); padding: 20px; border-radius: 8px;">
                                            <h4 style="margin: 0 0 12px 0;">Crypto Predictor</h4>
                                            <div style="font-size: 13px; color: var(--text-muted); margin-bottom: 8px;">
                                                Online learning from live market data
                                            </div>
                                            <div id="crypto-training-info" style="font-size: 12px; margin-top: 12px; padding: 12px; background: var(--bg); border-radius: 4px;">
                                                Status: Idle
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                        </div>
                        
                        <style>
                            .ml-nav-btn.active {
                                background: var(--accent) !important;
                                color: white !important;
                            }
                            
                            .ml-nav-btn:hover {
                                opacity: 0.8;
                            }
                            
                            .ttt-cell {
                                aspect-ratio: 1;
                                background: var(--bg-darker);
                                border: 2px solid var(--border);
                                border-radius: 8px;
                                display: flex;
                                align-items: center;
                                justify-content: center;
                                font-size: 48px;
                                cursor: pointer;
                                transition: all 0.2s;
                            }
                            
                            .ttt-cell:hover:not(.filled) {
                                background: var(--bg);
                                border-color: var(--accent);
                            }
                            
                            .ttt-cell.filled {
                                cursor: not-allowed;
                            }
                            
                            .ttt-cell.win {
                                background: rgba(76, 175, 80, 0.2);
                                border-color: #4CAF50;
                            }
                        </style>
                    `;
                case 'terminal':
                    return `
                        <div id="terminal-container" style="height: 100%; display: flex; flex-direction: column;">
                            <div id="terminal-output" style="flex: 1; background: var(--bg-darker); color: var(--text); padding: 15px; font-family: 'Courier New', Courier, monospace; font-size: 0.9rem; overflow-y: auto; border-radius: 8px; box-shadow: inset 0 0 10px rgba(0,0,0,0.2);"></div>
                            <form id="terminal-form" style="display: flex; border-top: 1px solid var(--border);">
                                <input type="text" id="terminal-input" placeholder="Enter command..." style="flex: 1; padding: 10px; border: none; outline: none; font-family: 'Courier New', Courier, monospace; font-size: 0.9rem; background: var(--bg); color: var(--text); border-radius: 0 0 0 8px;">
                                <button type="submit" style="padding: 10px 15px; border: none; background: var(--accent); color: white; cursor: pointer; font-size: 0.9rem; border-radius: 0 0 8px 0;">Run</button>
                            </form>
                        </div>
                    `;
                    
                case 'config':
                    return `
                        <div id="config-container" style="height: 100%; overflow: hidden; display: flex; flex-direction: column;">
                            <p style="color: #94a3b8; text-align: center; margin-top: 100px;">Loading configuration...</p>
                        </div>
                        
                        <style>
                            .config-nav-btn {
                                transition: all 0.2s;
                            }
                            
                            .config-nav-btn:hover {
                                background: var(--accent-muted) !important;
                            }
                            
                            .config-panel {
                                animation: fadeIn 0.2s ease-in;
                            }
                            
                            @keyframes fadeIn {
                                from { opacity: 0; transform: translateY(-10px); }
                                to { opacity: 1; transform: translateY(0); }
                            }
                            
                            .config-panel input:focus,
                            .config-panel select:focus,
                            .config-panel textarea:focus {
                                outline: 2px solid var(--accent);
                                outline-offset: 2px;
                            }
                        </style>
                    `;
            
                case 'organiser':
                    return `
                        <body>
                            <!-- Calendar Tab Content for Vera AI -->
<!-- Features: Collapsible sidebars, responsive layout, agent chat, minimal emojis -->

<div id="calendar-container" style="display: grid; grid-template-columns: 250px 1fr 280px; gap: 15px; padding: 15px; height: 100%; transition: grid-template-columns 0.3s ease;">
    
    <!-- Left Sidebar -->
    <div class="calendar-sidebar-left" style="background: var(--bg-darker); border-radius: 8px; padding: 15px; display: flex; flex-direction: column; gap: 15px; overflow: hidden; transition: all 0.3s ease;">
        
        <!-- Header -->
        <div style="display: flex; align-items: center; justify-content: space-between; padding-bottom: 12px; border-bottom: 1px solid var(--border);">
            <div class="sidebar-header-content">
                <h3 style="font-size: 1.2rem; font-weight: 600; margin: 0;">Calendar</h3>
            </div>
            <button id="toggleLeftSidebar" class="sidebar-toggle" style="background: none; border: none; cursor: pointer; color: var(--text-muted); font-size: 1.2rem;" title="Toggle sidebar">‹</button>
        </div>
        
        <!-- Connection Status -->
        <div class="sidebar-content">
            <div id="connectionStatus" class="connection-status status-disconnected" style="padding: 6px 10px; border-radius: 4px; font-size: 0.85rem; text-align: center;">
                Disconnected
            </div>
            
            <!-- Action Buttons -->
            <div style="display: flex; flex-direction: column; gap: 8px; margin-top: 12px;">
                <button id="newEventBtn" class="btn btn-primary" style="width: 100%; padding: 10px; border: none; border-radius: 6px; cursor: pointer; background: var(--accent); color: white; font-size: 0.95rem;">
                    + New Event
                </button>
                <button id="refreshCalendar" class="btn btn-secondary" style="width: 100%; padding: 10px; border: 1px solid var(--border); border-radius: 6px; cursor: pointer; background: var(--bg); color: var(--text); font-size: 0.95rem;">
                    Refresh
                </button>
            </div>
            
            <!-- Calendar Sources -->
            <div style="margin-top: 20px;">
                <div style="font-size: 0.9rem; font-weight: 600; margin-bottom: 10px; color: var(--text-muted);">Sources</div>
                <div id="sourceFilters" style="display: flex; flex-direction: column; gap: 8px;">
                    <!-- Populated by JS -->
                </div>
            </div>
        </div>
    </div>
    
    <!-- Main Calendar Area -->
    <div style="background: var(--bg-darker); border-radius: 8px; padding: 15px; display: flex; flex-direction: column; overflow: hidden;">
        
        <!-- Calendar Header -->
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; padding-bottom: 12px; border-bottom: 1px solid var(--border);">
            <div id="calendarStats" style="font-size: 0.9rem; color: var(--text-muted);">
                <!-- Stats populated by JS -->
            </div>
        </div>
        
        <!-- Calendar -->
        <div id="calendar" style="flex: 1; overflow: auto;"></div>
    </div>
    
    <!-- Right Sidebar -->
    <div class="calendar-sidebar-right" style="background: var(--bg-darker); border-radius: 8px; padding: 15px; display: flex; flex-direction: column; gap: 15px; overflow: hidden; transition: all 0.3s ease;">
        
        <!-- Header -->
        <div style="display: flex; align-items: center; justify-content: space-between; padding-bottom: 12px; border-bottom: 1px solid var(--border);">
            <button id="toggleRightSidebar" class="sidebar-toggle" style="background: none; border: none; cursor: pointer; color: var(--text-muted); font-size: 1.2rem;" title="Toggle sidebar">›</button>
            <div class="sidebar-header-content">
                <h3 style="font-size: 1.2rem; font-weight: 600; margin: 0;">Assistant</h3>
            </div>
        </div>
        
        <div class="sidebar-content" style="flex: 1; display: flex; flex-direction: column; gap: 15px; overflow: hidden;">
            
            <!-- Agent Chat -->
            <div style="flex: 1; display: flex; flex-direction: column; border: 1px solid var(--border); border-radius: 6px; overflow: hidden;">
                <div style="padding: 10px; background: var(--bg); border-bottom: 1px solid var(--border);">
                    <div style="font-size: 0.9rem; font-weight: 600;">Scheduling Agent</div>
                    <div style="font-size: 0.8rem; color: var(--text-muted);">Ask about events, create tasks, manage schedule</div>
                </div>
                
                <div id="agentChatMessages" style="flex: 1; overflow-y: auto; padding: 12px; display: flex; flex-direction: column; gap: 10px; min-height: 200px; max-height: 400px;">
                    <div class="chat-message chat-message-assistant">
                        <div class="chat-message-content" style="background: var(--bg); padding: 10px; border-radius: 6px; font-size: 0.9rem;">
                            Hi! I can help you manage your calendar. Try asking me to:
                            <ul style="margin: 8px 0 0 20px; padding: 0;">
                                <li>Schedule a meeting</li>
                                <li>Check what's coming up</li>
                                <li>Find free time</li>
                                <li>Add a reminder</li>
                            </ul>
                        </div>
                    </div>
                </div>
                
                <form id="agentChatForm" style="padding: 12px; background: var(--bg); border-top: 1px solid var(--border); display: flex; gap: 8px;">
                    <input type="text" id="agentChatInput" placeholder="Ask the scheduling agent..." style="flex: 1; padding: 8px; border: 1px solid var(--border); border-radius: 4px; background: var(--bg-darker); color: var(--text); font-size: 0.9rem;" />
                    <button type="submit" id="agentChatSend" style="padding: 8px 15px; border: none; border-radius: 4px; background: var(--accent); color: white; cursor: pointer; font-size: 0.9rem;">
                        Send
                    </button>
                </form>
            </div>
            
            <!-- Scheduled Jobs -->
            <div style="border-top: 1px solid var(--border); padding-top: 15px;">
                <div style="font-size: 0.9rem; font-weight: 600; margin-bottom: 10px; color: var(--text-muted);">Scheduled Jobs</div>
                <div id="cronJobsList" style="display: flex; flex-direction: column; gap: 8px; max-height: 200px; overflow-y: auto;">
                    <!-- Populated by JS -->
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Event Creation Modal -->
<div id="eventModal" class="modal" style="display: none; position: fixed; z-index: 10000; left: 0; top: 0; width: 100%; height: 100%; background: rgba(0, 0, 0, 0.7); align-items: center; justify-content: center;">
    <div class="modal-content" style="background: var(--bg); border-radius: 12px; padding: 25px; max-width: 500px; width: 90%; box-shadow: 0 10px 40px rgba(0, 0, 0, 0.5);">
        <div class="modal-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding-bottom: 15px; border-bottom: 1px solid var(--border);">
            <h2 style="margin: 0; font-size: 1.4rem;">Create Event</h2>
            <span class="close" style="font-size: 1.8rem; cursor: pointer; color: var(--text-muted);">&times;</span>
        </div>
        <form id="eventForm">
            <div class="form-group" style="margin-bottom: 15px;">
                <label for="eventTitle" style="display: block; margin-bottom: 5px; font-weight: 500; color: var(--text-muted);">Title *</label>
                <input type="text" id="eventTitle" required style="width: 100%; padding: 8px; border: 1px solid var(--border); border-radius: 4px; background: var(--bg-darker); color: var(--text);">
            </div>
            <div class="form-group" style="margin-bottom: 15px;">
                <label for="eventStart" style="display: block; margin-bottom: 5px; font-weight: 500; color: var(--text-muted);">Start *</label>
                <input type="datetime-local" id="eventStart" required style="width: 100%; padding: 8px; border: 1px solid var(--border); border-radius: 4px; background: var(--bg-darker); color: var(--text);">
            </div>
            <div class="form-group" style="margin-bottom: 15px;">
                <label for="eventEnd" style="display: block; margin-bottom: 5px; font-weight: 500; color: var(--text-muted);">End *</label>
                <input type="datetime-local" id="eventEnd" required style="width: 100%; padding: 8px; border: 1px solid var(--border); border-radius: 4px; background: var(--bg-darker); color: var(--text);">
            </div>
            <div class="form-group" style="margin-bottom: 15px;">
                <label for="eventSource" style="display: block; margin-bottom: 5px; font-weight: 500; color: var(--text-muted);">Calendar *</label>
                <select id="eventSource" required style="width: 100%; padding: 8px; border: 1px solid var(--border); border-radius: 4px; background: var(--bg-darker); color: var(--text);"></select>
            </div>
            <div class="form-group" style="margin-bottom: 15px;">
                <label for="eventDescription" style="display: block; margin-bottom: 5px; font-weight: 500; color: var(--text-muted);">Description</label>
                <textarea id="eventDescription" style="width: 100%; padding: 8px; border: 1px solid var(--border); border-radius: 4px; background: var(--bg-darker); color: var(--text); min-height: 80px; resize: vertical;"></textarea>
            </div>
            <button type="submit" class="btn btn-primary" style="width: 100%; padding: 12px; background: var(--accent); color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 1rem;">
                Create Event
            </button>
        </form>
    </div>
</div>

<!-- Event Details Modal -->
<div id="eventDetailsModal" class="modal" style="display: none; position: fixed; z-index: 10000; left: 0; top: 0; width: 100%; height: 100%; background: rgba(0, 0, 0, 0.7); align-items: center; justify-content: center;">
    <div class="modal-content" style="background: var(--bg); border-radius: 12px; padding: 25px; max-width: 500px; width: 90%; box-shadow: 0 10px 40px rgba(0, 0, 0, 0.5);">
        <div class="modal-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding-bottom: 15px; border-bottom: 1px solid var(--border);">
            <h2 style="margin: 0; font-size: 1.4rem;">Event Details</h2>
            <span class="close" style="font-size: 1.8rem; cursor: pointer; color: var(--text-muted);">&times;</span>
        </div>
        <div id="eventDetailsContent">
            <!-- Populated by JS -->
        </div>
    </div>
</div>

<style>
/* Sidebar collapse styles */
.calendar-sidebar-left.collapsed,
.calendar-sidebar-right.collapsed {
    width: 50px;
}

.calendar-sidebar-left.collapsed .sidebar-content,
.calendar-sidebar-right.collapsed .sidebar-content,
.calendar-sidebar-left.collapsed .sidebar-header-content,
.calendar-sidebar-right.collapsed .sidebar-header-content {
    display: none;
}

.calendar-sidebar-left.collapsed #toggleLeftSidebar {
    transform: rotate(180deg);
}

.calendar-sidebar-right.collapsed #toggleRightSidebar {
    transform: rotate(180deg);
}

.sidebar-toggle {
    transition: transform 0.3s ease;
}

.sidebar-toggle:hover {
    color: var(--text) !important;
}

/* Source filter styles */
.source-filter {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 8px;
    border-radius: 4px;
    cursor: pointer;
    transition: background 0.2s;
    font-size: 0.9rem;
}

.source-filter:hover {
    background: rgba(255, 255, 255, 0.05);
}

.source-filter.disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.source-color {
    width: 14px;
    height: 14px;
    border-radius: 50%;
    flex-shrink: 0;
}

/* Connection status */
.connection-status {
    transition: all 0.3s;
}

.status-connected {
    background: rgba(52, 168, 83, 0.2);
    color: var(--success, #34a853);
}

.status-disconnected {
    background: rgba(234, 67, 53, 0.2);
    color: var(--danger, #ea4335);
}

.status-error {
    background: rgba(251, 188, 4, 0.2);
    color: var(--warning, #fbbc04);
}

/* Cron job items */
.cron-job-item {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 10px;
    font-size: 0.85rem;
}

.cron-job-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 6px;
}

.cron-job-details {
    display: flex;
    flex-direction: column;
    gap: 3px;
}

.cron-job-details small {
    color: var(--text-muted);
    font-size: 0.8rem;
}

/* Chat messages */
.chat-message {
    display: flex;
    animation: slideIn 0.2s ease-out;
}

@keyframes slideIn {
    from {
        opacity: 0;
        transform: translateY(10px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.chat-message-user {
    justify-content: flex-end;
}

.chat-message-user .chat-message-content {
    background: var(--accent) !important;
    color: white;
}

.chat-message-assistant .chat-message-content {
    background: var(--bg);
}

.chat-message-content {
    max-width: 85%;
    padding: 10px;
    border-radius: 6px;
    font-size: 0.9rem;
    line-height: 1.4;
}

/* Stats */
.stat-item {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    margin-right: 10px;
}

.stat-color {
    width: 10px;
    height: 10px;
    border-radius: 50%;
}

/* Event details */
.event-details h3 {
    margin: 0 0 15px 0;
    font-size: 1.3rem;
}

.event-info {
    display: flex;
    flex-direction: column;
    gap: 12px;
    margin-bottom: 20px;
}

.info-row {
    display: flex;
    flex-direction: column;
    gap: 5px;
}

.info-row strong {
    color: var(--text-muted);
    font-size: 0.85rem;
}

.source-badge {
    display: inline-block;
    padding: 4px 10px;
    border-radius: 4px;
    font-size: 0.85rem;
    width: fit-content;
}

.event-actions {
    display: flex;
    gap: 10px;
}

.btn {
    padding: 10px 15px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.9rem;
    transition: all 0.2s;
}

.btn-danger {
    background: var(--danger, #ea4335);
    color: white;
    border: none;
}

.btn-danger:hover {
    opacity: 0.9;
}

.btn-secondary {
    background: var(--bg);
    color: var(--text);
    border: 1px solid var(--border);
}

.btn-secondary:hover {
    background: var(--bg-darker);
}

.badge {
    padding: 2px 8px;
    border-radius: 3px;
    font-size: 0.75rem;
    font-weight: 600;
}

.badge-success {
    background: rgba(52, 168, 83, 0.2);
    color: var(--success, #34a853);
}

.badge-secondary {
    background: rgba(154, 160, 166, 0.2);
    color: var(--text-muted);
}

/* Notifications */
.notification-container {
    position: fixed;
    top: 20px;
    right: 20px;
    z-index: 10001;
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.calendar-notification {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 12px 18px;
    min-width: 250px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    opacity: 0;
    transform: translateX(400px);
    transition: all 0.3s ease-out;
    font-size: 0.9rem;
}

.calendar-notification.show {
    opacity: 1;
    transform: translateX(0);
}

.notification-success {
    border-left: 4px solid var(--success, #34a853);
}

.notification-error {
    border-left: 4px solid var(--danger, #ea4335);
}

.notification-warning {
    border-left: 4px solid var(--warning, #fbbc04);
}

.notification-info {
    border-left: 4px solid var(--accent, #4285f4);
}

/* FullCalendar theme */
.fc {
    --fc-border-color: var(--border);
    --fc-button-bg-color: var(--accent, #4285f4);
    --fc-button-border-color: var(--accent, #4285f4);
    --fc-button-hover-bg-color: #3367d6;
    --fc-button-active-bg-color: #2851a3;
    --fc-today-bg-color: rgba(66, 133, 244, 0.1);
}

.fc .fc-toolbar-title {
    color: var(--text);
    font-size: 1.4rem;
}

.fc .fc-col-header-cell {
    background: var(--bg);
    color: var(--text-muted);
    font-weight: 600;
    text-transform: uppercase;
    font-size: 0.7rem;
    padding: 8px 0;
}

.fc .fc-daygrid-day-number {
    color: var(--text);
    padding: 6px;
}

.fc-event {
    border-radius: 3px;
    padding: 2px 4px;
    cursor: pointer;
}
</style>
                               
                    `;
         case 'agents':
            return `
                <div id="agents-container" style="padding: 24px; height: 100%; overflow-y: auto;">
                    <div class="header">
                        <h1>Vera Agents Manager</h1>
                        <p>YAML-based agent configuration system with Jinja2 templates and Ollama model building</p>
                    </div>
                    
                    <!-- Navigation Tabs -->
                    <div class="nav-tabs">
                        <button class="nav-tab agents-nav-btn active" data-panel="browse" onclick="app.switchAgentsV2Panel('browse')">
                            Browse Agents
                        </button>
                        <button class="nav-tab agents-nav-btn" data-panel="edit" onclick="app.switchAgentsV2Panel('edit')">
                            Edit Agent
                        </button>
                        <button class="nav-tab agents-nav-btn" data-panel="build" onclick="app.switchAgentsV2Panel('build')">
                            Build
                        </button>
                        <button class="nav-tab agents-nav-btn" data-panel="system" onclick="app.switchAgentsV2Panel('system')">
                            System
                        </button>
                    </div>
                    
                    <!-- Browse Panel -->
                    <div id="agents-panel-browse" class="panel agents-panel">
                        <div id="agents-list">
                            <p style="color: var(--text-muted); text-align: center; padding: 48px;">Loading agents...</p>
                        </div>
                    </div>
                    
                    <!-- Edit Panel -->
                    <div id="agents-panel-edit" class="panel agents-panel" style="display: none;">
                        <div id="agents-editor-content">
                            <p style="color: var(--text-muted); text-align: center; padding: 48px;">Select an agent to edit</p>
                        </div>
                    </div>
                    
                    <!-- Build Panel -->
                    <div id="agents-panel-build" class="panel agents-panel" style="display: none;">
                        <div id="agents-build-content">
                            <p style="color: var(--text-muted); text-align: center; padding: 48px;">Loading build panel...</p>
                        </div>
                    </div>
                    
                    <!-- System Panel -->
                    <div id="agents-panel-system" class="panel agents-panel" style="display: none;">
                        <div id="agents-system-content">
                            <p style="color: var(--text-muted); text-align: center; padding: 48px;">Loading system info...</p>
                        </div>
                    </div>
                    
                </div>
                
                <style>
                    .agents-nav-btn.active {
                        background: var(--accent) !important;
                        color: white !important;
                    }
                    
                    .agents-nav-btn:hover {
                        opacity: 0.8;
                    }
                </style>
            `;
                case 'chat':
                    return `
                        <div id="chatMessages" style="flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 12px;"></div>
                        
                        <div class="input-area">
                            <div class="input-wrapper">
                                <textarea id="messageInput" placeholder="Type your message..." rows="1"></textarea>
                                <button class="send-btn" id="sendBtn" onclick="app.sendMessage()">Send</button>
                                <button class="stop-btn" id="stopBtn" onclick="app.stopMessage()">Stop</button>
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
                                <button class="panel-btn" id="openGraphStorage" onclick="window.GraphCardView.toggle()" title="Card View">Card view</button>
                                <button class="panel-btn" id="openGraphStorage" onclick="showGraphStorageMenu(app.VeraChat)" title="Saved Graphs">Saved Graphs</button>
                                <button class="panel-btn" onclick="window.GraphAddon && window.GraphAddon.toggleSettings()" title="Settings">Settings</button>
                                <button class="panel-btn" onclick="window.GraphStyleControl && window.GraphStyleControl.showInCard('');" title="Style Builder">Style</button>
                                <button class="panel-btn" onclick="window.GraphAdvancedFilters && window.GraphAdvancedFilters.showInCard('');" title="Filter Builder">Filters</button>
                                <button class="panel-btn" onclick="window.CypherQuery && window.CypherQuery.showInCard('');" title="Query Builder">Query</button>
                                <button class="panel-btn" onclick="app.fitGraph()" title="Fit Graph to Window">Fit</button>
                                <button class="panel-btn" onclick="app.zoomIn()"title="Zoom In">🔍+</button>
                                <button class="panel-btn" onclick="app.zoomOut()" title="Zoom Out">🔍-</button>
                                <button class="panel-btn" onclick="app.loadGraph()"  title="Refresh Graph">🔄</button>
                                <button class="panel-btn" onclick="app.loadGraph()"  title="Reset Graph">🗑️</button>
                            </div>
                        </div>
                        <div id="graph"></div>
                        <div class="graph-stats">
                            <div>Nodes: <span id="nodeCount">0</span></div>
                            <div>Edges: <span id="edgeCount">0</span></div>
                        </div>
                        <!-- <button id="settings-toggle-btn" onclick="window.GraphAddon && window.GraphAddon.toggleSettings()">⚙️</button>-->
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
                                    <h2 style=" margin: 0;">Notebook</h2>
                                    <div style="display: flex; gap: 8px;">
                                    <button id="toggle-view-btn" 
                                            class="panel-btn" 
                                            onclick="app.toggleNotebookView()" 
                                            title="View notebooks from all sessions"
                                            style="white-space: nowrap;">
                                        All Sessions
                                    </button>
                                    
                                    <!-- Storage Type Indicator -->
                                    <span id="storage-type-indicator" 
                                        style="font-size: 11px; color: #64748b; white-space: nowrap;">
                                    </span>
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
                            <h2 style="margin-bottom: 16px;">Proactive Focus</h2>
                            <p style="color: #94a3b8;">Loading focus dashboard...</p>
                        </div>
                    `;

                case 'toolchain':
                    return `
                        <div id="toolchain" style="padding: 20px; overflow-y: auto; height: 100%;">
                            <h2 style="margin-bottom: 16px;">Toolchain</h2>
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
                // ============================================================================
                // OLLAMA MANAGER HTML - Add this case to getTabContent() in Chat.js
                // ============================================================================

                case 'ollama':
                    return `
                        <div id="ollama-container" style="padding: 24px; height: 100%; overflow-y: auto;">
                            
                            <!-- Header with Status -->
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 2px solid var(--border);">
                                <div>
                                    <h2 style="margin: 0 0 8px 0; font-size: 24px; font-weight: 700;">Ollama Manager</h2>
                                    <p style="margin: 0; color: var(--text-muted); font-size: 14px;">Manage Ollama models and test generation</p>
                                </div>
                                
                                <div style="display: flex; align-items: center; gap: 12px;">
                                    <div style="display: flex; align-items: center; gap: 8px; padding: 8px 16px; background: var(--bg-darker); border-radius: 8px;">
                                        <div id="ollama-status-indicator" style="width: 12px; height: 12px; border-radius: 50%; background: var(--text-muted);"></div>
                                        <span id="ollama-status-text" style="font-size: 13px; font-weight: 600;">Checking...</span>
                                    </div>
                                    
                                    <button onclick="app.reconnectOllama()" 
                                            style="padding: 8px 16px; background: var(--accent); border: none; border-radius: 8px; color: white; cursor: pointer; font-size: 13px; font-weight: 600; transition: all 0.2s;"
                                            onmouseover="this.style.opacity='0.8'"
                                            onmouseout="this.style.opacity='1'">
                                        🔄 Reconnect
                                    </button>
                                </div>
                            </div>
                            
                            <!-- Navigation -->
                            <div style="display: flex; gap: 12px; margin-bottom: 24px; flex-wrap: wrap;">
                                <button class="ollama-nav-btn active" data-panel="models" 
                                        onclick="app.switchOllamaPanel('models')"
                                        style="padding: 12px 24px; background: var(--accent); border: none; border-radius: 8px; color: white; cursor: pointer; font-size: 14px; font-weight: 600; transition: all 0.2s;">
                                    Models
                                </button>
                                <button class="ollama-nav-btn" data-panel="pull" 
                                        onclick="app.switchOllamaPanel('pull')"
                                        style="padding: 12px 24px; background: var(--bg-darker); border: none; border-radius: 8px; color: var(--text); cursor: pointer; font-size: 14px; font-weight: 600; transition: all 0.2s;">
                                    Pull Model
                                </button>
                                <button class="ollama-nav-btn" data-panel="generate" 
                                        onclick="app.switchOllamaPanel('generate')"
                                        style="padding: 12px 24px; background: var(--bg-darker); border: none; border-radius: 8px; color: var(--text); cursor: pointer; font-size: 14px; font-weight: 600; transition: all 0.2s;">
                                    Test Generation
                                </button>
                                <button class="ollama-nav-btn" data-panel="config" 
                                        onclick="app.switchOllamaPanel('config')"
                                        style="padding: 12px 24px; background: var(--bg-darker); border: none; border-radius: 8px; color: var(--text); cursor: pointer; font-size: 14px; font-weight: 600; transition: all 0.2s;">
                                    Configuration
                                </button>
                                
                            </div>
                            
                            <!-- Models Panel -->
                            <div id="ollama-panel-models" class="ollama-panel">
                                <div style="background: var(--bg-darker); padding: 20px; border-radius: 12px; margin-bottom: 20px;">
                                    <h3 style="margin: 0 0 8px 0; font-size: 16px; font-weight: 600;">Available Models</h3>
                                    <p style="margin: 0; font-size: 13px; color: var(--text-muted);">Select a model to view details or perform actions</p>
                                </div>
                                
                                <div id="ollama-models-list" style="display: grid; gap: 16px;">
                                    <!-- Models will be populated here by JavaScript -->
                                    <div style="text-align: center; padding: 48px; color: var(--text-muted);">
                                        <div style="font-size: 48px; margin-bottom: 16px;">⏳</div>
                                        <h3 style="margin: 0 0 8px 0;">Loading Models...</h3>
                                        <p style="margin: 0;">Please wait</p>
                                    </div>
                                </div>
                            </div>
                            
                            <!-- Pull Model Panel -->
                            <div id="ollama-panel-pull" class="ollama-panel" style="display: none;">
                                <div style="background: var(--bg-darker); padding: 20px; border-radius: 12px; margin-bottom: 20px;">
                                    <h3 style="margin: 0 0 8px 0; font-size: 16px; font-weight: 600;">Pull a Model from Ollama Registry</h3>
                                    <p style="margin: 0; font-size: 13px; color: var(--text-muted);">Download models from the Ollama library. This may take several minutes.</p>
                                </div>
                                
                                <div style="background: var(--bg); padding: 24px; border-radius: 12px; max-width: 600px;">
                                    <label style="display: block; margin-bottom: 8px; font-size: 14px; font-weight: 600;">Model Name</label>
                                    <input type="text" 
                                        id="ollama-pull-model-name" 
                                        placeholder="e.g., llama3.2, gemma2:2b, mistral"
                                        style="width: 100%; padding: 12px; background: var(--bg-darker); border: 2px solid var(--border); border-radius: 8px; color: var(--text); font-size: 14px; margin-bottom: 16px;">
                                    
                                    <button onclick="app.pullOllamaModel()" 
                                            style="width: 100%; padding: 14px; background: var(--success); border: none; border-radius: 8px; color: white; cursor: pointer; font-size: 15px; font-weight: 600; transition: all 0.2s;"
                                            onmouseover="this.style.opacity='0.8'"
                                            onmouseout="this.style.opacity='1'">
                                        ⬇️ Pull Model
                                    </button>
                                    
                                    <div style="margin-top: 24px; padding-top: 24px; border-top: 1px solid var(--border);">
                                        <h4 style="margin: 0 0 12px 0; font-size: 13px; font-weight: 600; color: var(--text-muted); text-transform: uppercase;">Popular Models</h4>
                                        <div style="display: grid; gap: 8px;">
                                            <button onclick="document.getElementById('ollama-pull-model-name').value='llama3.2'" 
                                                    style="padding: 10px 16px; background: var(--bg-darker); border: 1px solid var(--border); border-radius: 6px; color: var(--text); cursor: pointer; font-size: 13px; text-align: left; transition: all 0.2s;"
                                                    onmouseover="this.style.background='var(--bg)'"
                                                    onmouseout="this.style.background='var(--bg-darker)'">
                                                llama3.2 <span style="color: var(--text-muted); font-size: 11px;">(3B, Fast & Capable)</span>
                                            </button>
                                            <button onclick="document.getElementById('ollama-pull-model-name').value='gemma2:2b'" 
                                                    style="padding: 10px 16px; background: var(--bg-darker); border: 1px solid var(--border); border-radius: 6px; color: var(--text); cursor: pointer; font-size: 13px; text-align: left; transition: all 0.2s;"
                                                    onmouseover="this.style.background='var(--bg)'"
                                                    onmouseout="this.style.background='var(--bg-darker)'">
                                                gemma2:2b <span style="color: var(--text-muted); font-size: 11px;">(2B, Lightweight)</span>
                                            </button>
                                            <button onclick="document.getElementById('ollama-pull-model-name').value='mistral'" 
                                                    style="padding: 10px 16px; background: var(--bg-darker); border: 1px solid var(--border); border-radius: 6px; color: var(--text); cursor: pointer; font-size: 13px; text-align: left; transition: all 0.2s;"
                                                    onmouseover="this.style.background='var(--bg)'"
                                                    onmouseout="this.style.background='var(--bg-darker)'">
                                                mistral <span style="color: var(--text-muted); font-size: 11px;">(7B, Balanced)</span>
                                            </button>
                                            <button onclick="document.getElementById('ollama-pull-model-name').value='qwen2.5:7b'" 
                                                    style="padding: 10px 16px; background: var(--bg-darker); border: 1px solid var(--border); border-radius: 6px; color: var(--text); cursor: pointer; font-size: 13px; text-align: left; transition: all 0.2s;"
                                                    onmouseover="this.style.background='var(--bg)'"
                                                    onmouseout="this.style.background='var(--bg-darker)'">
                                                qwen2.5:7b <span style="color: var(--text-muted); font-size: 11px;">(7B, Strong Reasoning)</span>
                                            </button>
                                            <button onclick="document.getElementById('ollama-pull-model-name').value='deepseek-r1:7b'" 
                                                    style="padding: 10px 16px; background: var(--bg-darker); border: 1px solid var(--border); border-radius: 6px; color: var(--text); cursor: pointer; font-size: 13px; text-align: left; transition: all 0.2s;"
                                                    onmouseover="this.style.background='var(--bg)'"
                                                    onmouseout="this.style.background='var(--bg-darker)'">
                                                deepseek-r1:7b <span style="color: var(--text-muted); font-size: 11px;">(7B, Chain-of-Thought)</span>
                                            </button>
                                            <button onclick="document.getElementById('ollama-pull-model-name').value='phi4'" 
                                                    style="padding: 10px 16px; background: var(--bg-darker); border: 1px solid var(--border); border-radius: 6px; color: var(--text); cursor: pointer; font-size: 13px; text-align: left; transition: all 0.2s;"
                                                    onmouseover="this.style.background='var(--bg)'"
                                                    onmouseout="this.style.background='var(--bg-darker)'">
                                                phi4 <span style="color: var(--text-muted); font-size: 11px;">(14B, High Quality)</span>
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <!-- Test Generation Panel -->
                            <div id="ollama-panel-generate" class="ollama-panel" style="display: none;">
                                <div style="background: var(--bg-darker); padding: 20px; border-radius: 12px; margin-bottom: 20px;">
                                    <h3 style="margin: 0 0 8px 0; font-size: 16px; font-weight: 600;">Test Model Generation</h3>
                                    <p style="margin: 0; font-size: 13px; color: var(--text-muted);">Quick test to verify a model works and see performance metrics</p>
                                </div>
                                
                                <div style="background: var(--bg); padding: 24px; border-radius: 12px; max-width: 800px;">
                                    <div style="margin-bottom: 20px;">
                                        <label style="display: block; margin-bottom: 8px; font-size: 14px; font-weight: 600;">Select Model</label>
                                        <select id="ollama-test-model" 
                                                style="width: 100%; padding: 12px; background: var(--bg-darker); border: 2px solid var(--border); border-radius: 8px; color: var(--text); font-size: 14px;">
                                            <option>Loading models...</option>
                                        </select>
                                    </div>
                                    
                                    <div style="margin-bottom: 20px;">
                                        <label style="display: block; margin-bottom: 8px; font-size: 14px; font-weight: 600;">Test Prompt</label>
                                        <textarea id="ollama-test-prompt" 
                                                placeholder="Enter a prompt to test the model..."
                                                style="width: 100%; min-height: 120px; padding: 12px; background: var(--bg-darker); border: 2px solid var(--border); border-radius: 8px; color: var(--text); font-size: 14px; font-family: inherit; resize: vertical;">Write a haiku about artificial intelligence</textarea>
                                    </div>
                                    
                                    <button onclick="app.testOllamaGeneration()" 
                                            style="width: 100%; padding: 14px; background: var(--accent); border: none; border-radius: 8px; color: white; cursor: pointer; font-size: 15px; font-weight: 600; transition: all 0.2s;"
                                            onmouseover="this.style.opacity='0.8'"
                                            onmouseout="this.style.opacity='1'">
                                        ✨ Generate
                                    </button>
                                    
                                    <div id="ollama-test-output" style="margin-top: 20px;">
                                        <!-- Output will be populated here -->
                                    </div>
                                </div>
                            </div>
                            
                            <!-- Configuration Panel -->
                            <div id="ollama-panel-config" class="ollama-panel" style="display: none;">
                                <div style="background: var(--bg-darker); padding: 20px; border-radius: 12px; margin-bottom: 20px;">
                                    <h3 style="margin: 0 0 8px 0; font-size: 16px; font-weight: 600;">Ollama Configuration</h3>
                                    <p style="margin: 0; font-size: 13px; color: var(--text-muted);">Current settings from configuration file</p>
                                </div>
                                
                                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px;">
                                    <div style="background: var(--bg); padding: 20px; border-radius: 12px;">
                                        <h4 style="margin: 0 0 16px 0; font-size: 14px; font-weight: 600; color: var(--text-muted); text-transform: uppercase;">Connection</h4>
                                        <div style="margin-bottom: 12px;">
                                            <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 4px;">API URL</div>
                                            <div id="ollama-config-url" style="font-size: 14px; font-weight: 600; font-family: monospace;">Loading...</div>
                                        </div>
                                        <div style="margin-bottom: 12px;">
                                            <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 4px;">Timeout</div>
                                            <div id="ollama-config-timeout" style="font-size: 14px; font-weight: 600;">Loading...</div>
                                        </div>
                                    </div>
                                    
                                    <div style="background: var(--bg); padding: 20px; border-radius: 12px;">
                                        <h4 style="margin: 0 0 16px 0; font-size: 14px; font-weight: 600; color: var(--text-muted); text-transform: uppercase;">Features</h4>
                                        <div style="margin-bottom: 12px;">
                                            <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 4px;">Thought Capture</div>
                                            <div id="ollama-config-thought" style="font-size: 14px; font-weight: 600;">Loading...</div>
                                        </div>
                                        <div style="margin-bottom: 12px;">
                                            <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 4px;">Default Temperature</div>
                                            <div id="ollama-config-temp" style="font-size: 14px; font-weight: 600;">Loading...</div>
                                        </div>
                                    </div>
                                </div>
                                
                                <div style="margin-top: 20px; padding: 16px; background: var(--bg); border-radius: 12px; border-left: 4px solid var(--info);">
                                    <div style="font-size: 13px; color: var(--text-muted);">
                                        💡 To edit these settings, go to the <strong>Configuration</strong> tab and modify the Ollama section.
                                    </div>
                                </div>
                            </div>
                            
                        </div>
                        
                        <style>
                            .ollama-nav-btn.active {
                                background: var(--accent) !important;
                                color: white !important;
                            }
                            
                            .ollama-nav-btn:hover {
                                opacity: 0.8;
                            }
                        </style>
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
                            <button class="orch-nav-btn active" data-panel="queue" onclick="app.switchOrchPanel('queue')" style="padding: 8px 16px; background: var(--accent); border: none; border-radius: 4px; color: white; cursor: pointer; font-size: 13px; white-space: nowrap;">
                                Queue
                            </button>
                            <button class="orch-nav-btn" data-panel="create" onclick="app.switchOrchPanel('create')" style="padding: 8px 16px; background: var(--bg); border: none; border-radius: 4px; cursor: pointer; font-size: 13px; white-space: nowrap;">
                                Create Task
                            </button>
                            <button class="orch-nav-btn" data-panel="dashboard" onclick="app.switchOrchPanel('dashboard')" style="padding: 8px 16px; background: var(--bg); border: none; border-radius: 4px; cursor: pointer; font-size: 13px; white-space: nowrap;">
                                Dashboard
                            </button>
                            <button class="orch-nav-btn" data-panel="workers" onclick="app.switchOrchPanel('workers')" style="padding: 8px 16px; background: var(--bg); border: none; border-radius: 4px; cursor: pointer; font-size: 13px; white-space: nowrap;">
                                Workers
                            </button>
                            <button class="orch-nav-btn" data-panel="tasks" onclick="app.switchOrchPanel('tasks')" style="padding: 8px 16px; background: var(--bg); border: none; border-radius: 4px; cursor: pointer; font-size: 13px; white-space: nowrap;">
                                Registry
                            </button>
                            <button class="orch-nav-btn" data-panel="monitor" onclick="app.switchOrchPanel('monitor')" style="padding: 8px 16px; background: var(--bg); border: none; border-radius: 4px; cursor: pointer; font-size: 13px; white-space: nowrap;">
                                Monitor
                            </button>
                            <button class="orch-nav-btn" data-panel="config" onclick="app.switchOrchPanel('config')" style="padding: 8px 16px; background: var(--bg); border: none; border-radius: 4px; cursor: pointer; font-size: 13px; white-space: nowrap;">
                                Config
                            </button>
                            <button class="orch-nav-btn" data-panel="infrastructure" onclick="app.switchOrchPanel('infrastructure')" style="padding: 8px 16px; background: var(--bg); border: none; border-radius: 4px; cursor: pointer; font-size: 13px; white-space: nowrap;">
                                Infrastructure
                            </button>
                            <button class="orch-nav-btn" data-panel="external" onclick="app.switchOrchPanel('external')" style="padding: 8px 16px; background: var(--bg); border: none; border-radius: 4px; cursor: pointer; font-size: 13px; white-space: nowrap;">
                                External APIs
                            </button>
                        </div>
                        
                        <!-- Content Area -->
                        <div style="height: calc(100% - 120px); overflow-y: auto; padding: 16px;">
                            
                            <!-- ========================================================================
                                QUEUE PANEL (NEW - PRIMARY VIEW)
                                ======================================================================== -->
                            <div id="orch-panel-queue" class="orch-panel">
                                <div style="margin-bottom: 20px; padding: 20px; background: var(--bg); border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                                    <h2 style="margin: 0 0 16px 0; font-size: 24px; font-weight: 700;">Task Queue</h2>
                                    
                                    <!-- Quick Stats -->
                                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-bottom: 16px;">
                                        <div style="padding: 16px; background: var(--bg-darker); border-radius: 8px; border-left: 4px solid var(--info);">
                                            <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 4px;">Active Tasks</div>
                                            <div style="font-size: 32px; font-weight: 700;" id="orch-active-count">0</div>
                                        </div>
                                        <div style="padding: 16px; background: var(--bg-darker); border-radius: 8px; border-left: 4px solid var(--warning);">
                                            <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 4px;">Queued</div>
                                            <div style="font-size: 32px; font-weight: 700;" id="orch-queue">0</div>
                                        </div>
                                        <div style="padding: 16px; background: var(--bg-darker); border-radius: 8px; border-left: 4px solid var(--success);">
                                            <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 4px;">Completed (Today)</div>
                                            <div style="font-size: 32px; font-weight: 700;" id="orch-completed-today">0</div>
                                        </div>
                                        <div style="padding: 16px; background: var(--bg-darker); border-radius: 8px; border-left: 4px solid var(--danger);">
                                            <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 4px;">Failed (Today)</div>
                                            <div style="font-size: 32px; font-weight: 700;" id="orch-failed-today">0</div>
                                        </div>
                                    </div>
                                </div>
                                
                                <!-- Task Queue Container (Populated by JS) -->
                                <div id="orch-task-queue-container"></div>
                            </div>
                            
                            <!-- ========================================================================
                                CREATE TASK PANEL (NEW)
                                ======================================================================== -->
                            <div id="orch-panel-create" class="orch-panel" style="display: none;">
                                <div style="margin-bottom: 20px; padding: 20px; background: var(--bg); border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                                    <h2 style="margin: 0 0 8px 0; font-size: 24px; font-weight: 700;">Create New Task</h2>
                                    <p style="margin: 0; color: var(--text-muted);">
                                        Use templates for common tasks or create advanced custom tasks
                                    </p>
                                </div>
                                
                                <!-- Task Creation Container (Populated by JS) -->
                                <div id="orch-task-creation-container"></div>
                            </div>
                            
                            <!-- ========================================================================
                                DASHBOARD PANEL
                                ======================================================================== -->
                            <div id="orch-panel-dashboard" class="orch-panel" style="display: none;">
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
                                        <div style="font-size: 28px; font-weight: 600;" id="orch-queue-dash">0</div>
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
                            
                            <!-- ========================================================================
                                WORKER POOLS PANEL
                                ======================================================================== -->
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
                            
                            <!-- ========================================================================
                                TASKS REGISTRY PANEL
                                ======================================================================== -->
                            <div id="orch-panel-tasks" class="orch-panel" style="display: none;">
                                <div style="margin-bottom: 16px;">
                                    <h3 style="margin: 0 0 8px 0; font-size: 16px;">Task Registry</h3>
                                    <p style="margin: 0; font-size: 12px; color: var(--text-muted);">
                                        All registered tasks available for execution
                                    </p>
                                </div>
                                
                                <div id="orch-registered-tasks">
                                    <p style="color: var(--text-muted);">Loading...</p>
                                </div>
                            </div>
                            
                            <!-- ========================================================================
                                SYSTEM MONITOR PANEL
                                ======================================================================== -->
                            <div id="orch-panel-monitor" class="orch-panel" style="display: none;">
                                <div style="margin-bottom: 20px;">
                                    <h2 style="margin: 0 0 8px 0; font-size: 24px; font-weight: 700;">System Monitor</h2>
                                </div>
                                
                                <!-- System Metrics -->
                                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px; margin-bottom: 20px;">
                                    <div style="padding: 20px; background: var(--bg); border-radius: 12px;">
                                        <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 8px;">CPU USAGE</div>
                                        <div style="font-size: 36px; font-weight: 700; margin-bottom: 12px;" id="orch-mon-cpu">0%</div>
                                        <div id="orch-cpu-bar" style="height: 8px; background: var(--accent); border-radius: 4px; width: 0%; transition: width 0.3s;"></div>
                                    </div>
                                    
                                    <div style="padding: 20px; background: var(--bg); border-radius: 12px;">
                                        <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 8px;">MEMORY USAGE</div>
                                        <div style="font-size: 36px; font-weight: 700; margin-bottom: 12px;" id="orch-mon-memory">0%</div>
                                        <div id="orch-memory-bar" style="height: 8px; background: var(--warning); border-radius: 4px; width: 0%; transition: width 0.3s;"></div>
                                    </div>
                                    
                                    <div style="padding: 20px; background: var(--bg); border-radius: 12px;">
                                        <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 8px;">ACTIVE PROCESSES</div>
                                        <div style="font-size: 36px; font-weight: 700;" id="orch-mon-processes">0</div>
                                    </div>
                                </div>
                                
                                <!-- Process List -->
                                <div style="padding: 20px; background: var(--bg); border-radius: 12px;">
                                    <h3 style="margin: 0 0 16px 0;">Top Processes</h3>
                                    <div id="orch-processes-list">
                                        <p style="color: var(--text-muted); text-align: center;">No data</p>
                                    </div>
                                </div>
                            </div>
                            
                            <!-- ========================================================================
                                CONFIGURATION PANEL
                                ======================================================================== -->
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
                            
                            <!-- ========================================================================
                                INFRASTRUCTURE PANEL
                                ======================================================================== -->
                            <div id="orch-panel-infrastructure" class="orch-panel" style="display: none;">
                                <!-- Header -->
                                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;">
                                    <div>
                                        <h2 style="margin: 0 0 4px 0; font-size: 24px; font-weight: 700;">Infrastructure Management</h2>
                                        <p style="margin: 0; color: var(--text-muted); font-size: 14px;">
                                            Docker containers and Proxmox VMs
                                        </p>
                                    </div>
                                    <div style="display: flex; align-items: center; gap: 12px;">
                                        <div id="infra-indicator" style="width: 12px; height: 12px; border-radius: 50%; background: var(--text-muted);"></div>
                                        <span style="font-weight: 600;">Infrastructure</span>
                                    </div>
                                </div>

                                <!-- Status Cards -->
                                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px;">
                                    <div style="padding: 20px; background: var(--bg); border-radius: 12px; border-left: 4px solid var(--accent);">
                                        <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">TOTAL RESOURCES</div>
                                        <div id="infra-total-resources" style="font-size: 32px; font-weight: 700;">0</div>
                                    </div>
                                    <div style="padding: 20px; background: var(--bg); border-radius: 12px; border-left: 4px solid var(--success);">
                                        <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">AVAILABLE</div>
                                        <div id="infra-available-resources" style="font-size: 32px; font-weight: 700; color: var(--success);">0</div>
                                    </div>
                                    <div style="padding: 20px; background: var(--bg); border-radius: 12px; border-left: 4px solid var(--warning);">
                                        <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">IN USE</div>
                                        <div id="infra-in-use-resources" style="font-size: 32px; font-weight: 700; color: var(--warning);">0</div>
                                    </div>
                                    <div style="padding: 20px; background: var(--bg); border-radius: 12px; border-left: 4px solid var(--info);">
                                        <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">TASKS EXECUTED</div>
                                        <div id="infra-tasks-executed" style="font-size: 32px; font-weight: 700;">0</div>
                                    </div>
                                </div>

                                <!-- System Status -->
                                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 24px;">
                                    <div style="padding: 16px; background: var(--bg); border-radius: 8px;">
                                        <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 8px;">DOCKER STATUS</div>
                                        <div id="infra-docker-status" style="font-weight: 600;">Checking...</div>
                                    </div>
                                    <div style="padding: 16px; background: var(--bg); border-radius: 8px;">
                                        <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 8px;">PROXMOX STATUS</div>
                                        <div id="infra-proxmox-status" style="font-weight: 600;">Checking...</div>
                                    </div>
                                </div>

                                <!-- Capacity Overview -->
                                <div style="padding: 20px; background: var(--bg-darker); border-radius: 12px; margin-bottom: 24px;">
                                    <h3 style="margin: 0 0 12px 0; font-size: 14px; font-weight: 700; text-transform: uppercase; color: var(--text-muted);">
                                        Capacity Overview
                                    </h3>
                                    <div id="infra-capacity"></div>
                                </div>

                                <!-- Actions Section -->
                                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 24px;">
                                    <!-- Provision Docker -->
                                    <div style="padding: 20px; background: var(--bg); border-radius: 12px;">
                                        <h3 style="margin: 0 0 16px 0; font-size: 16px; font-weight: 600;">🐳 Provision Docker Container</h3>
                                        
                                        <div style="margin-bottom: 12px;">
                                            <label style="display: block; font-size: 12px; color: var(--text-muted); margin-bottom: 4px;">CPU Cores</label>
                                            <input type="number" id="docker-cpu" value="2" step="0.5" min="0.5" max="32" 
                                                style="width: 100%; padding: 8px; background: var(--bg-darker); border: 1px solid var(--border); border-radius: 6px; color: var(--text); font-size: 14px;">
                                        </div>
                                        
                                        <div style="margin-bottom: 12px;">
                                            <label style="display: block; font-size: 12px; color: var(--text-muted); margin-bottom: 4px;">Memory (MB)</label>
                                            <input type="number" id="docker-memory" value="2048" step="512" min="512" max="65536" 
                                                style="width: 100%; padding: 8px; background: var(--bg-darker); border: 1px solid var(--border); border-radius: 6px; color: var(--text); font-size: 14px;">
                                        </div>
                                        
                                        <div style="margin-bottom: 12px;">
                                            <label style="display: block; font-size: 12px; color: var(--text-muted); margin-bottom: 4px;">Disk (GB)</label>
                                            <input type="number" id="docker-disk" value="20" step="5" min="5" max="1000" 
                                                style="width: 100%; padding: 8px; background: var(--bg-darker); border: 1px solid var(--border); border-radius: 6px; color: var(--text); font-size: 14px;">
                                        </div>
                                        
                                        <div style="margin-bottom: 12px;">
                                            <label style="display: block; font-size: 12px; color: var(--text-muted); margin-bottom: 4px;">Image</label>
                                            <input type="text" id="docker-image" value="python:3.11-slim" placeholder="e.g., python:3.11-slim"
                                                style="width: 100%; padding: 8px; background: var(--bg-darker); border: 1px solid var(--border); border-radius: 6px; color: var(--text); font-size: 14px;">
                                        </div>
                                        
                                        <div style="margin-bottom: 16px;">
                                            <label style="display: block; font-size: 12px; color: var(--text-muted); margin-bottom: 4px;">Task Type (Optional)</label>
                                            <select id="docker-task-type" 
                                                    style="width: 100%; padding: 8px; background: var(--bg-darker); border: 1px solid var(--border); border-radius: 6px; color: var(--text); font-size: 14px;">
                                                <option value="">Auto-select</option>
                                                <option value="LLM">LLM</option>
                                                <option value="TOOL">Tool</option>
                                                <option value="GENERAL">General</option>
                                                <option value="ML_MODEL">ML Model</option>
                                            </select>
                                        </div>
                                        
                                        <button onclick="app.provisionDockerContainer()" 
                                                style="width: 100%; padding: 12px; background: var(--accent); border: none; border-radius: 8px; color: white; cursor: pointer; font-weight: 600; font-size: 14px;">
                                            🚀 Provision Container
                                        </button>
                                    </div>

                                    <!-- Cleanup -->
                                    <div style="padding: 20px; background: var(--bg); border-radius: 12px;">
                                        <h3 style="margin: 0 0 16px 0; font-size: 16px; font-weight: 600;">🧹 Resource Cleanup</h3>
                                        
                                        <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 16px;">
                                            Remove resources that have been idle for a specified period.
                                        </p>
                                        
                                        <div style="margin-bottom: 16px;">
                                            <label style="display: block; font-size: 12px; color: var(--text-muted); margin-bottom: 4px;">Max Idle Time (seconds)</label>
                                            <input type="number" id="cleanup-idle-time" value="300" step="60" min="60" max="3600" 
                                                style="width: 100%; padding: 8px; background: var(--bg-darker); border: 1px solid var(--border); border-radius: 6px; color: var(--text); font-size: 14px;">
                                        </div>
                                        
                                        <button onclick="app.cleanupIdleResources()" 
                                                style="width: 100%; padding: 12px; background: var(--danger); border: none; border-radius: 8px; color: white; cursor: pointer; font-weight: 600; font-size: 14px;">
                                            🗑️ Cleanup Idle Resources
                                        </button>
                                        
                                        <div style="margin-top: 24px; padding: 16px; background: var(--bg-darker); border-radius: 8px; border-left: 3px solid var(--warning);">
                                            <div style="font-size: 12px; font-weight: 600; margin-bottom: 8px;">⚠️ Note</div>
                                            <p style="font-size: 11px; color: var(--text-muted); margin: 0;">
                                                Only idle resources will be removed. Resources currently running tasks will not be affected.
                                            </p>
                                        </div>
                                    </div>
                                </div>

                                <!-- Resources List -->
                                <div style="padding: 20px; background: var(--bg-darker); border-radius: 12px;">
                                    <h3 style="margin: 0 0 16px 0; font-size: 16px; font-weight: 600;">Active Resources</h3>
                                    <div id="infra-resources-list">
                                        <div style="text-align: center; padding: 48px; color: var(--text-muted);">
                                            Loading resources...
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <!-- ========================================================================
                                EXTERNAL API MANAGEMENT PANEL
                                ======================================================================== -->
                            <div id="orch-panel-external" class="orch-panel" style="display: none;">
                                <!-- Header -->
                                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;">
                                    <div>
                                        <h2 style="margin: 0 0 4px 0; font-size: 24px; font-weight: 700;">External API Management</h2>
                                        <p style="margin: 0; color: var(--text-muted); font-size: 14px;">
                                            LLM providers and cloud compute APIs
                                        </p>
                                    </div>
                                    <div style="display: flex; align-items: center; gap: 12px;">
                                        <div id="external-indicator" style="width: 12px; height: 12px; border-radius: 50%; background: var(--text-muted);"></div>
                                        <span style="font-weight: 600;">External APIs</span>
                                    </div>
                                </div>

                                <!-- Stats Cards -->
                                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px;">
                                    <div style="padding: 20px; background: var(--bg); border-radius: 12px; border-left: 4px solid var(--accent);">
                                        <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">PROVIDERS</div>
                                        <div id="external-providers-count" style="font-size: 32px; font-weight: 700;">0</div>
                                    </div>
                                    <div style="padding: 20px; background: var(--bg); border-radius: 12px; border-left: 4px solid var(--danger);">
                                        <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">TOTAL COST</div>
                                        <div id="external-total-cost" style="font-size: 32px; font-weight: 700; color: var(--danger);">$0.00</div>
                                    </div>
                                    <div style="padding: 20px; background: var(--bg); border-radius: 12px; border-left: 4px solid var(--info);">
                                        <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">TOTAL TOKENS</div>
                                        <div id="external-total-tokens" style="font-size: 32px; font-weight: 700;">0</div>
                                    </div>
                                    <div style="padding: 20px; background: var(--bg); border-radius: 12px; border-left: 4px solid var(--success);">
                                        <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">REQUESTS</div>
                                        <div id="external-total-requests" style="font-size: 32px; font-weight: 700;">0</div>
                                    </div>
                                </div>

                                <!-- Cost Breakdown -->
                                <div style="padding: 20px; background: var(--bg-darker); border-radius: 12px; margin-bottom: 24px;">
                                    <h3 style="margin: 0 0 12px 0; font-size: 14px; font-weight: 700; text-transform: uppercase; color: var(--text-muted);">
                                        💰 Cost Breakdown
                                    </h3>
                                    <div id="external-cost-breakdown">
                                        <p style="color: var(--text-muted); text-align: center; padding: 24px;">No cost data yet</p>
                                    </div>
                                </div>

                                <!-- Providers List -->
                                <div style="padding: 20px; background: var(--bg-darker); border-radius: 12px; margin-bottom: 24px;">
                                    <h3 style="margin: 0 0 16px 0; font-size: 16px; font-weight: 600;">Configured Providers</h3>
                                    <div id="external-providers-list">
                                        <div style="text-align: center; padding: 48px; color: var(--text-muted);">
                                            Loading providers...
                                        </div>
                                    </div>
                                </div>

                                <!-- Quick Test Section -->
                                <div style="padding: 20px; background: var(--bg); border-radius: 12px;">
                                    <h3 style="margin: 0 0 16px 0; font-size: 16px; font-weight: 600;">🧪 Quick LLM Test</h3>
                                    
                                    <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 16px;">
                                        Test your LLM providers with a quick prompt. Monitor costs and performance in real-time.
                                    </p>
                                    
                                    <div style="padding: 16px; background: var(--bg-darker); border-radius: 8px; border-left: 3px solid var(--info);">
                                        <div style="font-size: 12px; font-weight: 600; margin-bottom: 8px;">💡 Tip</div>
                                        <p style="font-size: 11px; color: var(--text-muted); margin: 0;">
                                            Use the Test button on each provider card to quickly verify connectivity and compare response quality across different models.
                                        </p>
                                    </div>
                                </div>
                            </div>
                            
                        </div>
                    </div>

                    <!-- Task Details Modal Container (for popups) -->
                    <div id="orch-task-details-modal"></div>

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

            if (tabId === 'agents') {
                setTimeout(() => this.initAgents && this.initAgents(), 50);
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
            if (tabId === 'organiser') {
                setTimeout(() => {
                    if (this.initCalendar) {
                        window.calendarManager.init();
                    }
                }, 50);
            }
            if (tabId === 'chat-history') {
                setTimeout(async () => {
                    if (!this.sessionHistoryReady) {
                        this.sessionHistoryReady = true;
                        const container = document.getElementById('session-history-container');
                        if (container) {
                            this.sessionHistory = new SessionHistory({
                                containerId: 'session-history-container',
                                apiBaseUrl: 'http://llm.int:8888/api/session',
                                currentSessionId: this.sessionId,
                                onLoadSession: (sessionId) => this.loadHistoricalSession(sessionId),
                                autoRefresh: false,
                                refreshInterval: 30000
                            });
                            console.log('Session History initialized on demand');
                        }
                    } else if (this.sessionHistory) {
                        // Non-blocking refresh
                        Promise.resolve().then(() => this.sessionHistory.refresh());
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
            if (tabId === 'ollama') {
                setTimeout(() => this.initOllama && this.initOllama(), 50);
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
            if (tabId === 'config') {
                setTimeout(() => {
                    if (this.initConfig) {
                        this.initConfig();
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

// ==================== CALENDAR METHODS ====================

initCalendar() {
    console.log('[Calendar] Initializing...');
    
    // Initialize state
    this.calendarInstance = null;
    this.calendarWs = null;
    this.calendarSources = [];
    this.calendarEvents = [];
    
    // Load FullCalendar library if not already loaded
    if (typeof FullCalendar === 'undefined') {
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = 'https://cdn.jsdelivr.net/npm/fullcalendar@6.1.10/index.global.min.css';
        document.head.appendChild(link);
        
        const script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/npm/fullcalendar@6.1.10/index.global.min.js';
        script.onload = () => this.setupCalendar();
        document.head.appendChild(script);
    } else {
        this.setupCalendar();
    }
    
    // Setup WebSocket
    this.setupCalendarWebSocket();
    
    // Load initial data
    this.loadCalendarSources();
    this.loadCalendarEvents();
    this.loadScheduledJobs();
}

setupCalendar() {
    const calendarEl = document.getElementById('vera-calendar');
    if (!calendarEl) {
        console.warn('[Calendar] Calendar element not found');
        return;
    }
    
    // Get theme colors
    const styles = getComputedStyle(document.documentElement);
    const bgColor = styles.getPropertyValue('--bg').trim();
    const textColor = styles.getPropertyValue('--text').trim();
    const borderColor = styles.getPropertyValue('--border').trim();
    
    this.calendarInstance = new FullCalendar.Calendar(calendarEl, {
        initialView: 'dayGridMonth',
        headerToolbar: {
            left: 'prev,next today',
            center: 'title',
            right: 'dayGridMonth,timeGridWeek,timeGridDay,listWeek'
        },
        editable: false,
        selectable: true,
        selectMirror: true,
        dayMaxEvents: true,
        height: '100%',
        
        // Theme colors
        eventColor: styles.getPropertyValue('--accent').trim(),
        
        // Event handlers
        select: (info) => this.handleDateSelect(info),
        eventClick: (info) => this.handleEventClick(info),
        
        // Custom rendering
        eventContent: (arg) => this.renderCalendarEvent(arg)
    });
    
    this.calendarInstance.render();
    console.log('[Calendar] FullCalendar rendered');
}

setupCalendarWebSocket() {
    const wsUrl = `ws://llm.int:8888/api/calendar/ws`;
    console.log('[Calendar WS] Connecting to:', wsUrl);
    
    this.calendarWs = new WebSocket(wsUrl);
    
    this.calendarWs.onopen = () => {
        console.log('[Calendar WS] Connected');
        this.updateCalendarStatus('connected', 'Connected');
        this.calendarWs.send(JSON.stringify({ type: 'subscribe' }));
    };
    
    this.calendarWs.onmessage = (event) => {
        try {
            const message = JSON.parse(event.data);
            this.handleCalendarWebSocketMessage(message);
        } catch (error) {
            console.error('[Calendar WS] Error parsing message:', error);
        }
    };
    
    this.calendarWs.onerror = (error) => {
        console.error('[Calendar WS] Error:', error);
        this.updateCalendarStatus('error', 'Error');
    };
    
    this.calendarWs.onclose = () => {
        console.log('[Calendar WS] Disconnected');
        this.updateCalendarStatus('disconnected', 'Disconnected');
        // Attempt reconnect
        setTimeout(() => this.setupCalendarWebSocket(), 3000);
    };
}

handleCalendarWebSocketMessage(message) {
    console.log('[Calendar WS] Received:', message.type);
    
    switch (message.type) {
        case 'subscribed':
            console.log('[Calendar WS] Subscription confirmed');
            break;
            
        case 'events_update':
            console.log('[Calendar WS] Events update received');
            this.loadCalendarEvents();
            break;
            
        case 'event_created':
            console.log('[Calendar WS] New event created');
            this.addCalendarEvent(message.data);
            this.showCalendarNotification('Event created successfully', 'success');
            break;
            
        case 'event_deleted':
            console.log('[Calendar WS] Event deleted');
            this.removeCalendarEvent(message.data.source, message.data.id);
            this.showCalendarNotification('Event deleted', 'info');
            break;
            
        case 'pong':
            // Heartbeat response
            break;
    }
}

async loadCalendarSources() {
    try {
        const response = await fetch('http://llm.int:8888/api/calendar/sources');
        const data = await response.json();
        this.calendarSources = data.sources;
        
        this.renderCalendarSources();
    } catch (error) {
        console.error('[Calendar] Error loading sources:', error);
    }
}

async loadCalendarEvents() {
    try {
        const response = await fetch('http://llm.int:8888/api/calendar/events?days_ahead=30');
        const events = await response.json();
        
        this.calendarEvents = events;
        
        // Clear existing events
        if (this.calendarInstance) {
            this.calendarInstance.getEvents().forEach(e => e.remove());
            
            // Add events to calendar
            events.forEach(event => {
                this.calendarInstance.addEvent({
                    id: `${event.source}_${event.id}`,
                    title: event.title,
                    start: event.start,
                    end: event.end || event.start,
                    backgroundColor: event.color || this.getSourceColor(event.source),
                    borderColor: event.color || this.getSourceColor(event.source),
                    extendedProps: {
                        source: event.source,
                        originalId: event.id,
                        description: event.description,
                        recurrence: event.recurrence
                    }
                });
            });
        }
        
        // Update stats
        this.updateCalendarStats(events);
        
        console.log(`[Calendar] Loaded ${events.length} events`);
    } catch (error) {
        console.error('[Calendar] Error loading events:', error);
        this.updateCalendarStatus('error', 'Failed to load events');
    }
}

async loadScheduledJobs() {
    try {
        const response = await fetch('http://llm.int:8888/api/calendar/cron');
        const jobs = await response.json();
        
        this.renderScheduledJobs(jobs);
    } catch (error) {
        console.error('[Calendar] Error loading jobs:', error);
    }
}

renderCalendarSources() {
    const container = document.getElementById('cal-sources-list');
    if (!container) return;
    
    if (this.calendarSources.length === 0) {
        container.innerHTML = '<p style="color: var(--text-muted); font-size: 12px;">No sources</p>';
        return;
    }
    
    container.innerHTML = this.calendarSources.map(source => `
        <label class="cal-source-filter">
            <input type="checkbox" 
                   value="${source.id}" 
                   ${source.enabled ? 'checked' : ''}
                   onchange="app.toggleCalendarSource('${source.id}', this.checked)">
            <span class="cal-source-color" style="background-color: ${source.color}"></span>
            <span style="font-size: 12px;">${source.name}</span>
        </label>
    `).join('');
}

renderScheduledJobs(jobs) {
    const container = document.getElementById('cal-jobs-list');
    if (!container) return;
    
    if (!jobs || jobs.length === 0) {
        container.innerHTML = '<p style="color: var(--text-muted); font-size: 12px;">No scheduled jobs</p>';
        return;
    }
    
    container.innerHTML = jobs.map(job => `
        <div class="cal-job-item">
            <strong>${job.name}</strong>
            <small>${job.schedule}</small>
            ${job.next_run ? `<small>Next: ${this.formatDateTime(new Date(job.next_run))}</small>` : ''}
        </div>
    `).join('');
}

updateCalendarStats(events) {
    const googleCount = events.filter(e => e.source === 'google').length;
    const localCount = events.filter(e => e.source === 'local').length;
    const jobsCount = events.filter(e => e.source === 'apscheduler').length;
    
    document.getElementById('cal-events-count').textContent = events.length;
    document.getElementById('cal-google-count').textContent = googleCount;
    document.getElementById('cal-local-count').textContent = localCount;
    document.getElementById('cal-jobs-count').textContent = jobsCount;
}

updateCalendarStatus(status, text) {
    const indicator = document.getElementById('cal-status-indicator');
    const statusText = document.getElementById('cal-status-text');
    
    if (indicator) {
        const colors = {
            'connected': 'var(--success)',
            'disconnected': 'var(--danger)',
            'error': 'var(--danger)',
            'loading': 'var(--warning)'
        };
        indicator.style.background = colors[status] || 'var(--text-muted)';
    }
    
    if (statusText) {
        statusText.textContent = text;
    }
}

getSourceColor(source) {
    const sourceObj = this.calendarSources.find(s => s.id === source);
    return sourceObj?.color || '#999';
}

toggleCalendarSource(sourceId, enabled) {
    console.log(`[Calendar] Toggle source ${sourceId}:`, enabled);
    
    if (!this.calendarInstance) return;
    
    const events = this.calendarInstance.getEvents();
    events.forEach(event => {
        if (event.extendedProps.source === sourceId) {
            event.setProp('display', enabled ? 'auto' : 'none');
        }
    });
}

handleDateSelect(info) {
    console.log('[Calendar] Date selected:', info.startStr, 'to', info.endStr);
    this.showCreateEventModal(info.start, info.end);
    this.calendarInstance.unselect();
}

handleEventClick(info) {
    console.log('[Calendar] Event clicked:', info.event.title);
    this.showEventDetails(info.event);
}

renderCalendarEvent(arg) {
    const source = arg.event.extendedProps.source;
    const icons = {
        'google': '📅',
        'local': '📋',
        'apscheduler': '⏰'
    };
    const icon = icons[source] || '📌';
    
    return {
        html: `
            <div style="padding: 2px 4px; overflow: hidden;">
                <span style="font-size: 0.85em;">${icon}</span>
                <span style="font-size: 0.9em; margin-left: 4px;">${arg.event.title}</span>
            </div>
        `
    };
}

showCreateEventModal(start = null, end = null) {
    const modal = document.getElementById('cal-event-modal');
    if (!modal) return;
    
    // Reset form
    document.getElementById('cal-event-form').reset();
    
    // Set default times
    if (start) {
        document.getElementById('cal-event-start').value = this.formatDatetimeLocal(start);
    } else {
        const now = new Date();
        document.getElementById('cal-event-start').value = this.formatDatetimeLocal(now);
    }
    
    if (end) {
        document.getElementById('cal-event-end').value = this.formatDatetimeLocal(end);
    } else {
        const oneHourLater = new Date(Date.now() + 3600000);
        document.getElementById('cal-event-end').value = this.formatDatetimeLocal(oneHourLater);
    }
    
    modal.style.display = 'flex';
}

closeEventModal() {
    const modal = document.getElementById('cal-event-modal');
    if (modal) modal.style.display = 'none';
}

async submitEvent(event) {
    event.preventDefault();
    
    const eventData = {
        title: document.getElementById('cal-event-title').value,
        start: new Date(document.getElementById('cal-event-start').value).toISOString(),
        end: new Date(document.getElementById('cal-event-end').value).toISOString(),
        source: document.getElementById('cal-event-source').value,
        description: document.getElementById('cal-event-description').value || null
    };
    
    try {
        const response = await fetch('http://llm.int:8888/api/calendar/events', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(eventData)
        });
        
        if (!response.ok) {
            throw new Error('Failed to create event');
        }
        
        const newEvent = await response.json();
        console.log('[Calendar] Event created:', newEvent);
        
        this.closeEventModal();
        this.showCalendarNotification('Event created successfully', 'success');
        
        // Reload events
        await this.loadCalendarEvents();
        
    } catch (error) {
        console.error('[Calendar] Error creating event:', error);
        this.showCalendarNotification('Failed to create event', 'error');
    }
}

showEventDetails(event) {
    const modal = document.getElementById('cal-details-modal');
    const content = document.getElementById('cal-event-details-content');
    if (!modal || !content) return;
    
    const props = event.extendedProps;
    const source = this.calendarSources.find(s => s.id === props.source);
    
    content.innerHTML = `
        <div style="margin-bottom: 16px;">
            <h4 style="margin: 0 0 8px 0; font-size: 16px;">${event.title}</h4>
            <div style="display: inline-block; padding: 4px 8px; background: ${source?.color || '#999'}; border-radius: 4px; color: white; font-size: 11px; font-weight: 600;">
                ${source?.name || props.source}
            </div>
        </div>
        
        <div style="display: flex; flex-direction: column; gap: 12px; margin-bottom: 20px;">
            <div>
                <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 4px;">Start</div>
                <div style="font-weight: 600;">${this.formatDateTime(event.start)}</div>
            </div>
            
            <div>
                <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 4px;">End</div>
                <div style="font-weight: 600;">${event.end ? this.formatDateTime(event.end) : 'N/A'}</div>
            </div>
            
            ${props.description ? `
                <div>
                    <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 4px;">Description</div>
                    <div>${props.description}</div>
                </div>
            ` : ''}
            
            ${props.recurrence ? `
                <div>
                    <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 4px;">Recurrence</div>
                    <div style="font-family: monospace; font-size: 11px;">${props.recurrence}</div>
                </div>
            ` : ''}
        </div>
        
        <div style="display: flex; gap: 8px; justify-content: flex-end; padding-top: 16px; border-top: 1px solid var(--border);">
            <button onclick="app.deleteCalendarEvent('${props.source}', '${props.originalId}')" 
                    style="padding: 8px 16px; background: var(--danger); border: none; border-radius: 4px; color: white; cursor: pointer;">
                Delete
            </button>
            <button onclick="app.closeDetailsModal()" 
                    style="padding: 8px 16px; background: var(--bg-darker); border: 1px solid var(--border); border-radius: 4px; color: var(--text); cursor: pointer;">
                Close
            </button>
        </div>
    `;
    
    modal.style.display = 'flex';
}

closeDetailsModal() {
    const modal = document.getElementById('cal-details-modal');
    if (modal) modal.style.display = 'none';
}

async deleteCalendarEvent(source, eventId) {
    if (!confirm('Are you sure you want to delete this event?')) {
        return;
    }
    
    try {
        const response = await fetch(`http://llm.int:8888/api/calendar/events/${source}/${eventId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            throw new Error('Failed to delete event');
        }
        
        console.log('[Calendar] Event deleted');
        this.closeDetailsModal();
        this.showCalendarNotification('Event deleted', 'success');
        
        // Remove from calendar
        const calendarEventId = `${source}_${eventId}`;
        const event = this.calendarInstance.getEventById(calendarEventId);
        if (event) {
            event.remove();
        }
        
        // Reload events
        await this.loadCalendarEvents();
        
    } catch (error) {
        console.error('[Calendar] Error deleting event:', error);
        this.showCalendarNotification('Failed to delete event', 'error');
    }
}

addCalendarEvent(eventData) {
    if (!this.calendarInstance) return;
    
    this.calendarInstance.addEvent({
        id: `${eventData.source}_${eventData.id}`,
        title: eventData.title,
        start: eventData.start,
        end: eventData.end,
        backgroundColor: eventData.color || this.getSourceColor(eventData.source),
        borderColor: eventData.color || this.getSourceColor(eventData.source),
        extendedProps: {
            source: eventData.source,
            originalId: eventData.id,
            description: eventData.description
        }
    });
}

removeCalendarEvent(source, eventId) {
    if (!this.calendarInstance) return;
    
    const calendarEventId = `${source}_${eventId}`;
    const event = this.calendarInstance.getEventById(calendarEventId);
    if (event) {
        event.remove();
    }
}

refreshCalendar() {
    console.log('[Calendar] Refreshing...');
    this.loadCalendarEvents();
    this.loadScheduledJobs();
}

showCalendarNotification(message, type = 'info') {
    // Reuse existing notification system if available
    if (this.addSystemMessage) {
        this.addSystemMessage(message);
    } else {
        console.log(`[Calendar] ${type.toUpperCase()}: ${message}`);
    }
}

formatDateTime(date) {
    if (!date) return 'N/A';
    const d = new Date(date);
    return d.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

formatDatetimeLocal(date) {
    const d = new Date(date);
    const offset = d.getTimezoneOffset();
    const localDate = new Date(d.getTime() - (offset * 60 * 1000));
    return localDate.toISOString().slice(0, 16);
}

// ==================== END CALENDAR METHODS ====================

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