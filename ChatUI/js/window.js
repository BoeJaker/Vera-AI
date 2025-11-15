    
(() => {
    async function init() {
        try {
            const response = await fetch('http://llm.int:8888/api/session/start', { method: 'POST' });
            const data = await response.json();
            this.sessionId = data.session_id;
            
            document.getElementById('sessionInfo').textContent = `Session: ${this.sessionId}`;
            document.getElementById('connectionStatus').innerHTML = '<span class="status-indicator connected"></span>Connected';
            
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
            
            this.addSystemMessage('Vera connected and ready!');
            
            if (this.useWebSocket) {
                this.connectWebSocket();
                this.connectToolchainWebSocket(); 
                this.connectFocusWebSocket();
            }
        } catch (error) {
            console.error('Init error:', error);
            document.getElementById('connectionStatus').innerHTML = '<span class="status-indicator disconnected"></span>Offline';
            this.addSystemMessage('Connection failed. Running in offline mode.');
            this.veraRobot.setState('error');
        }
        
        // DON'T add event listeners here - they're added in activateTab when the chat tab is shown
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
        // const header = document.getElementById('header');
        // const statusIndicator = document.createElement('div');
        // statusIndicator.innerHTML = `
        //     <span style="padding: 6px 12px; background: ${this.focusRunning ? '#10b981' : '#6b7280'}; color: white; border-radius: 6px; font-size: 12px; font-weight: 600;">
        //         ${this.focusRunning ? '● RUNNING' : '○ STOPPED'}
        //     </span>`;
        // header.appendChild(statusIndicator);

        const column = document.createElement('div');
        column.className = 'column';
        column.dataset.columnId = id;
        column.innerHTML = `
            <div class="column-header">
                <span class="column-title" data-column-title="${id}">Column ${id}</span>

                    ${this.columns.length >= 1 ? `<button class="column-btn" onclick="app.addColumn()" style="padding: 6px 12px; font-size: 12px;">
                        ➕ Add Column
                    </button>` : ''}

                <div class="column-controls">
                    ${this.columns.length >= 2 ? `<button class="column-btn" onclick="app.removeColumn(${id})">✕ Remove</button>` : ''}
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
                
            case 'graph':
                return `
                    <div class="panel-header" draggable="false" style="cursor: default; position: absolute; top: 0; left: 0; right: 0; z-index: 10;">
                        <span>
                            <span class="panel-title">KNOWLEDGE GRAPH</span>
                        </span>
                        <div class="panel-controls">
                            <button class="panel-btn" onclick="app.testPanel()">🧪 Test</button>
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
                        <div style="padding: 16px; background: #0f172a; border-bottom: 1px solid #334155;">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                                <h2 style="color: #60a5fa; margin: 0;">📓 Notebook</h2>
                                <div style="display: flex; gap: 8px;">
                                    <button class="panel-btn" onclick="app.createNotebook()">+ New Notebook</button>
                                    <button class="panel-btn" onclick="app.loadNotebooks()">🔄 Refresh</button>
                                </div>
                            </div>
                            <div style="display: flex; gap: 8px;">
                                <select id="notebook-selector" onchange="app.switchNotebook(this.value)" 
                                        style="flex: 1; padding: 8px; background: #1e293b; border: 1px solid #334155; color: #e2e8f0; border-radius: 4px;">
                                    <option value="">Select a notebook...</option>
                                </select>
                                <button class="panel-btn" onclick="app.deleteCurrentNotebook()" id="delete-notebook-btn" disabled>🗑️</button>
                            </div>
                        </div>
                        <div style="display: flex; flex: 1; overflow: hidden;">
                            <div id="notes-sidebar" style="width: 300px; background: #1e293b; border-right: 1px solid #334155; overflow-y: auto; padding: 12px;">
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

            // Also update the toolchain case to match what toolchain.js expects:

            case 'toolchain':
                return `
                    <div id="toolchain" style="padding: 20px; overflow-y: auto; height: 100%;">
                        <h2 style="margin-bottom: 16px;">🔧 Toolchain</h2>
                        <p style="color: #94a3b8;">Loading toolchain...</p>
                    </div>
                `;

            // And update the memory case:

            case 'memory':
                return `
                    <div id="tab-memory" style="padding: 20px; overflow-y: auto; height: 100%;">
                        <div id="memory-content">
                            <p style="color: #94a3b8;">Loading memory system...</p>
                        </div>
                    </div>
                `;
                
            case 'orchestration':
                return `<div id="tab-orchestration" style="padding: 20px;"><h2 style="margin-bottom: 16px;">🎻 Orchestration</h2><p style="color: #94a3b8;">Orchestration coming soon...</p></div>`;
                
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
        //     fetch("orchestratior.html")
        //     .then(response => response.text())
        //     .then(html => {
        //         document.getElementById("tab-orchestration").innerHTML = html;
        //     })
        //     .catch(err => console.error("Error loading HTML:", err));
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
    
    testPanel() {
        // console.log('Test button clicked');
        app.initThemeSettings();
        window.applyThemeToGraph();
        // const panel = document.getElementById('property-panel');
        // console.log('Panel element:', panel);
        // panel.classList.add('active');
        // console.log('Panel classes:', panel.className);
        
        // const content = document.getElementById('panel-content');
        // content.innerHTML = '<div style="padding: 20px;"><h3 style="color: #60a5fa;">Test Panel</h3><p>If you see this, the panel HTML/CSS is working correctly!</p></div>';
    }            


    // Update the existing switchTab method:
    // switchTab(tabName) {
    //     this.activeTab = tabName;
        
    //     document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    //     document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
        
    //     event.target.classList.add('active');
    //     document.getElementById(`tab-${tabName}`).classList.add('active');
        
    //     if (tabName === 'graph' && this.networkInstance) {
    //         setTimeout(() => this.networkInstance.redraw(), 100);
    //     }
        
    //     if (tabName === 'toolchain') {
    //         this.updateToolchainUI();
    //     }
        
    //     if (tabName === 'proactive-focus') {
    //         this.loadFocusStatus();
    //     }
        
    //     if (tabName === 'memory') {
    //         this.loadMemoryData();
    //     }
    //     if (tabName === 'notebook') {
    //         this.loadNotebooks();
    //     }
    // }

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
})();