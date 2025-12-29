/**
 * GraphCanvasMenu Module - GraphInfoCard Integration
 * Handles canvas (background) context menu interactions
 * All dialogs now display in GraphInfoCard's inline content area
 * Features: Unified tool execution with search, node/edge generation, layouts, insights
 */

(function() {
    'use strict';
    
    window.GraphCanvasMenu = {
        
        // Store references
        graphAddon: null,
        graphDiscovery: null,
        clickPosition: null,
        apiBase: 'http://llm.int:8888',
        availableTools: [],

        /**
         * Initialize the module
         */
        init: function(graphAddon, graphDiscovery) {
            console.log('GraphCanvasMenu.init called');
            this.graphAddon = graphAddon;
            this.graphDiscovery = graphDiscovery;
            this.waitForNetwork();
        },
        
        /**
         * Wait for network to be ready before setting up listeners
         */
        waitForNetwork: function() {
            if (typeof network !== 'undefined' && network.body && network.body.data) {
                console.log('Network ready for canvas menu');
                this.setupEventListeners();
            } else {
                setTimeout(() => this.waitForNetwork(), 500);
            }
        },
        
        /**
         * Setup event listeners for canvas context menu
         */
        setupEventListeners: function() {
            const canvasMenu = document.getElementById('canvas-context-menu');
            if (canvasMenu) {
                canvasMenu.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const item = e.target.closest('.context-menu-item');
                    if (item) {
                        const action = item.getAttribute('data-action');
                        console.log('Canvas context menu action:', action);
                        this.handleCanvasAction(action);
                    }
                });
                console.log('Canvas context menu listeners set up');
            }
        },
        
        /**
         * Show canvas context menu at position
         */
        show: function(x, y, canvasPosition) {
            this.clickPosition = canvasPosition;
            
            const menu = document.getElementById('canvas-context-menu');
            if (menu) {
                menu.style.display = 'block';
                menu.style.left = x + 'px';
                menu.style.top = y + 'px';
            }
        },
        
        /**
         * Hide canvas context menu
         */
        hide: function() {
            const menu = document.getElementById('canvas-context-menu');
            if (menu) {
                menu.style.display = 'none';
            }
        },

        /**
         * Handle canvas menu action
         */
        handleCanvasAction: function(action) {
            this.hide();

            switch(action) {
                // View Actions
                case 'reset-view':
                    this.resetView();
                    break;
                case 'fit-view':
                    this.fitView();
                    break;
                case 'zoom-in':
                    this.zoomIn();
                    break;
                case 'zoom-out':
                    this.zoomOut();
                    break;

                // Add Actions
                case 'add-node':
                    this.addNode();
                    break;
                case 'add-edge':
                    this.addEdge();
                    break;

                // Selection Actions
                case 'select-all':
                    this.selectAll();
                    break;
                case 'clear-selection':
                    this.clearSelection();
                    break;
                case 'invert-selection':
                    this.invertSelection();
                    break;

                // Layout Actions
                case 'layout-hierarchical':
                    this.applyLayout('hierarchical');
                    break;
                case 'layout-force':
                    this.applyLayout('force');
                    break;
                case 'layout-circular':
                    this.applyLayout('circular');
                    break;
                case 'layout-random':
                    this.applyLayout('random');
                    break;

                // Style Actions
                case 'style-default':
                    this.applyStylePreset('default');
                    break;
                case 'style-minimal':
                    this.applyStylePreset('minimal');
                    break;
                case 'style-vibrant':
                    this.applyStylePreset('vibrant');
                    break;

                // Tool & AI Actions
                case 'run-tool':
                case 'execute-tool-direct':
                    window.GraphToolExecutor.showToolSelector();
                    break;

                // Search & Insights
                case 'search-graph':
                    this.showSearchDialog();
                    break;
                case 'find-patterns':
                    this.showPatternFinder();
                    break;
                case 'analyze-structure':
                    this.analyzeGraphStructure();
                    break;
                case 'find-communities':
                    this.findCommunities();
                    break;

                // Export Actions
                case 'export-image':
                    this.exportImage();
                    break;
                case 'export-json':
                    this.exportJSON();
                    break;

                // Settings
                case 'canvas-settings':
                    this.showSettings();
                    break;
                case 'physics-toggle':
                    this.togglePhysics();
                    break;

                // AI Assistant
                case 'ai-assistant':
                    if (window.GraphAIAssistant) {
                        window.GraphAIAssistant.showAssistantMenu();
                    } else {
                        alert('AI Assistant not available');
                    }
                    break;

                default:
                    console.warn('Unknown canvas action:', action);
            }
        },

        // ============================================================
        // UNIFIED TOOL EXECUTION WITH SEARCH
        // ============================================================

        /**
         * Load available tools from API
         */
        loadAvailableTools: async function() {
            try {
                const response = await fetch(`${this.apiBase}/api/tools/list`);
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                const data = await response.json();
                this.availableTools = data.tools || [];
                console.log('Loaded tools:', this.availableTools.length);
                return this.availableTools;
            } catch (e) {
                console.error('Could not load tools:', e);
                this.availableTools = [];
                return [];
            }
        },

        /**
         * Show tool selector dialog with search - UNIFIED VERSION
         */
        showToolSelector: async function(nodeId = null) {
            if (!window.GraphInfoCard) {
                alert('GraphInfoCard not available');
                return;
            }
            
            // Set inline mode
            window.GraphInfoCard.inlineMode = true;
            window.GraphInfoCard.isExpanded = true;
            
            // Show loading state
            const backAction = nodeId ? `window.GraphInfoCard.expandNodeInfo('${nodeId}')` : 'window.GraphInfoCard.collapse()';
            window.GraphInfoCard.showInlineContent(
                '🛠️ Run Tool',
                `<div style="color: #94a3b8; padding: 40px; text-align: center;">
                    <div style="font-size: 32px; margin-bottom: 12px;">⏳</div>
                    <div>Loading available tools...</div>
                </div>`,
                backAction
            );
            
            // Load tools
            if (!this.availableTools || this.availableTools.length === 0) {
                await this.loadAvailableTools();
            }
            
            if (!this.availableTools || this.availableTools.length === 0) {
                window.GraphInfoCard.showInlineContent(
                    '🛠️ Run Tool',
                    `<div style="padding: 40px; text-align: center;">
                        <div style="font-size: 48px; margin-bottom: 16px; opacity: 0.5;">⚠️</div>
                        <div style="color: #f87171; font-weight: 600; margin-bottom: 8px;">No tools available</div>
                        <div style="color: #64748b; font-size: 12px;">
                            The tool service may be unavailable.<br>
                            Please check the API connection.
                        </div>
                    </div>`,
                    backAction
                );
                return;
            }

            // Group tools by category
            const categories = {};
            this.availableTools.forEach(tool => {
                const cat = tool.category || 'Other';
                if (!categories[cat]) categories[cat] = [];
                categories[cat].push(tool);
            });
            
            const sortedCategories = Object.keys(categories).sort();
            
            const content = `
                <div style="display: flex; flex-direction: column; gap: 16px;">
                    <!-- Search Bar -->
                    <div style="position: sticky; top: 0; background: inherit; z-index: 10; padding-bottom: 8px;">
                        <input 
                            type="text" 
                            id="tool-search-input" 
                            placeholder="🔍 Search tools by name or description..."
                            autocomplete="off"
                            style="
                                width: 100%; padding: 12px 16px;
                                background: #1e293b; color: #e2e8f0;
                                border: 1px solid #334155; border-radius: 8px;
                                font-size: 14px;
                                transition: all 0.2s;
                            "
                            oninput="window.GraphCanvasMenu.filterTools(this.value)"
                            onfocus="this.style.borderColor='#3b82f6'; this.style.boxShadow='0 0 0 3px rgba(59, 130, 246, 0.1)'"
                            onblur="this.style.borderColor='#334155'; this.style.boxShadow='none'"
                        >
                    </div>
                    
                    <!-- Tool Count -->
                    <div id="tool-count" style="
                        color: #64748b; font-size: 11px; text-align: center;
                        margin-top: -8px; font-weight: 500;
                    ">
                        ${this.availableTools.length} tool${this.availableTools.length !== 1 ? 's' : ''} available
                    </div>
                    
                    <!-- Tool List -->
                    <div id="tool-list-container" style="
                        display: flex; flex-direction: column; gap: 16px; 
                        max-height: 450px; overflow-y: auto;
                        padding-right: 4px;
                    ">
                        ${sortedCategories.map(cat => `
                            <div class="tool-category" data-category="${this.escapeHtml(cat)}">
                                <div style="
                                    color: #60a5fa; font-size: 11px; font-weight: 700; 
                                    margin-bottom: 8px; text-transform: uppercase;
                                    letter-spacing: 0.5px; display: flex;
                                    align-items: center; gap: 8px;
                                ">
                                    <span class="category-name">${this.escapeHtml(cat)}</span>
                                    <span class="category-count" style="
                                        background: rgba(96, 165, 250, 0.2);
                                        padding: 2px 8px; border-radius: 12px;
                                        font-size: 10px;
                                    ">${categories[cat].length}</span>
                                </div>
                                <div class="category-tools" style="display: flex; flex-direction: column; gap: 6px;">
                                    ${categories[cat].map(tool => `
                                        <div class="tool-option" 
                                            data-tool-name="${this.escapeHtml(tool.name)}"
                                            data-tool-description="${this.escapeHtml(tool.description || '')}"
                                            data-category="${this.escapeHtml(cat)}"
                                            onclick="window.GraphCanvasMenu.showToolExecutionDialog('${this.escapeHtml(tool.name)}', ${nodeId ? `'${nodeId}'` : 'null'})"
                                            style="
                                                padding: 12px; 
                                                background: #1e293b; 
                                                border: 1px solid #334155;
                                                border-radius: 8px; 
                                                cursor: pointer;
                                                transition: all 0.15s;
                                            "
                                            onmouseover="this.style.background='#334155'; this.style.borderColor='#475569'; this.style.transform='translateX(4px)'"
                                            onmouseout="this.style.background='#1e293b'; this.style.borderColor='#334155'; this.style.transform='translateX(0)'">
                                            <div style="
                                                font-weight: 600; 
                                                color: #e2e8f0; 
                                                margin-bottom: 4px;
                                                font-size: 13px;
                                            ">
                                                ${this.escapeHtml(tool.name)}
                                            </div>
                                            <div style="
                                                font-size: 11px; 
                                                color: #94a3b8;
                                                line-height: 1.4;
                                            ">
                                                ${this.escapeHtml(tool.description || 'No description available')}
                                            </div>
                                        </div>
                                    `).join('')}
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
            
            window.GraphInfoCard.showInlineContent('🛠️ Run Tool', content, backAction);
            
            // Focus search after render
            setTimeout(() => {
                const searchInput = document.getElementById('tool-search-input');
                if (searchInput) {
                    searchInput.focus();
                    searchInput.select();
                }
            }, 150);
        },

        /**
         * Filter tools based on search query
         */
        filterTools: function(query) {
            const searchTerm = query.toLowerCase().trim();
            const toolOptions = document.querySelectorAll('.tool-option');
            const categories = document.querySelectorAll('.tool-category');
            
            let totalVisible = 0;
            const categoryVisibleCounts = {};
            
            // Filter tools
            toolOptions.forEach(option => {
                const toolName = (option.dataset.toolName || '').toLowerCase();
                const toolDesc = (option.dataset.toolDescription || '').toLowerCase();
                const category = option.dataset.category;
                
                const matches = !searchTerm || 
                               toolName.includes(searchTerm) || 
                               toolDesc.includes(searchTerm);
                
                option.style.display = matches ? 'block' : 'none';
                
                if (matches) {
                    totalVisible++;
                    categoryVisibleCounts[category] = (categoryVisibleCounts[category] || 0) + 1;
                }
            });
            
            // Update categories
            categories.forEach(category => {
                const categoryName = category.dataset.category;
                const visibleInCategory = categoryVisibleCounts[categoryName] || 0;
                
                category.style.display = visibleInCategory > 0 ? 'block' : 'none';
                
                // Update category count
                const countSpan = category.querySelector('.category-count');
                if (countSpan) {
                    countSpan.textContent = visibleInCategory;
                }
            });
            
            // Update total count
            const countElement = document.getElementById('tool-count');
            if (countElement) {
                if (searchTerm) {
                    countElement.innerHTML = `
                        <span style="color: ${totalVisible > 0 ? '#60a5fa' : '#f87171'}; font-weight: 600;">
                            ${totalVisible}
                        </span> 
                        <span style="color: #64748b;">
                            of ${this.availableTools.length} tools match "${this.escapeHtml(searchTerm)}"
                        </span>
                    `;
                } else {
                    countElement.textContent = `${this.availableTools.length} tool${this.availableTools.length !== 1 ? 's' : ''} available`;
                }
            }
            
            // Show "no results" message
            const container = document.getElementById('tool-list-container');
            let noResults = document.getElementById('no-tool-results');
            
            if (totalVisible === 0 && searchTerm) {
                if (!noResults) {
                    noResults = document.createElement('div');
                    noResults.id = 'no-tool-results';
                    noResults.style.cssText = 'text-align: center; padding: 60px 20px;';
                    noResults.innerHTML = `
                        <div style="font-size: 48px; margin-bottom: 16px; opacity: 0.3;">🔍</div>
                        <div style="color: #e2e8f0; font-weight: 600; margin-bottom: 8px; font-size: 14px;">
                            No tools found
                        </div>
                        <div style="color: #64748b; font-size: 12px; line-height: 1.5;">
                            Try a different search term or<br>
                            <span style="color: #60a5fa; cursor: pointer;" onclick="document.getElementById('tool-search-input').value=''; window.GraphCanvasMenu.filterTools('');">
                                clear search
                            </span> to browse all tools
                        </div>
                    `;
                    container.appendChild(noResults);
                }
                noResults.style.display = 'block';
            } else if (noResults) {
                noResults.style.display = 'none';
            }
        },

        /**
         * Show tool execution dialog (placeholder - delegates to GraphToolExecutor if available)
         */
        showToolExecutionDialog: function(toolName, nodeId) {
            if (window.GraphToolExecutor) {
                // Delegate to GraphToolExecutor for full functionality
                window.GraphToolExecutor.selectItem(nodeId, toolName, 'tool');
            } else {
                // Fallback: populate chat
                const prompt = `Execute tool "${toolName}"${nodeId ? ` on node ${nodeId}` : ''} with the following parameters:\n\n[Specify parameters here]`;
                this.populateChat(prompt);
                if (window.GraphInfoCard) {
                    window.GraphInfoCard.collapse();
                }
            }
        },

        // ============================================================
        // VIEW ACTIONS
        // ============================================================

        resetView: function() {
            if (network) {
                network.moveTo({
                    position: {x: 0, y: 0},
                    scale: 1,
                    animation: {
                        duration: 500,
                        easingFunction: 'easeInOutQuad'
                    }
                });
                this.showToast('View reset');
            }
        },

        fitView: function() {
            if (network && network.fit) {
                network.fit({
                    animation: {
                        duration: 500,
                        easingFunction: 'easeInOutQuad'
                    }
                });
                this.showToast('View fitted');
            }
        },

        zoomIn: function() {
            if (network) {
                const scale = network.getScale();
                network.moveTo({
                    scale: scale * 1.2,
                    animation: {duration: 300}
                });
                this.showToast('Zoomed in');
            }
        },

        zoomOut: function() {
            if (network) {
                const scale = network.getScale();
                network.moveTo({
                    scale: scale / 1.2,
                    animation: {duration: 300}
                });
                this.showToast('Zoomed out');
            }
        },

        // ============================================================
        // ADD ACTIONS (Using GraphInfoCard)
        // ============================================================

        addNode: function() {
            if (!window.GraphInfoCard) {
                alert('GraphInfoCard not available');
                return;
            }
            
            // Generate position based on click or center
            let x = 0, y = 0;
            if (this.clickPosition) {
                x = this.clickPosition.x;
                y = this.clickPosition.y;
            }
            
            const content = `
                <div style="display: flex; flex-direction: column; gap: 16px;">
                    <div>
                        <label style="display: block; color: #94a3b8; font-size: 13px; margin-bottom: 6px; font-weight: 600;">Label/Name</label>
                        <input 
                            type="text" 
                            id="new-node-label" 
                            placeholder="Enter node name..."
                            style="
                                width: 100%; padding: 10px;
                                background: #1e293b; color: #e2e8f0;
                                border: 1px solid #334155; border-radius: 6px;
                            "
                        >
                    </div>
                    
                    <div>
                        <label style="display: block; color: #94a3b8; font-size: 13px; margin-bottom: 6px; font-weight: 600;">Type</label>
                        <select id="new-node-type" style="
                            width: 100%; padding: 10px;
                            background: #1e293b; color: #e2e8f0;
                            border: 1px solid #334155; border-radius: 6px;
                        ">
                            <option value="Entity">Entity</option>
                            <option value="Concept">Concept</option>
                            <option value="Person">Person</option>
                            <option value="Place">Place</option>
                            <option value="Event">Event</option>
                            <option value="Document">Document</option>
                            <option value="Custom">Custom</option>
                        </select>
                    </div>
                    
                    <div>
                        <label style="display: block; color: #94a3b8; font-size: 13px; margin-bottom: 6px; font-weight: 600;">Description (optional)</label>
                        <textarea 
                            id="new-node-description" 
                            placeholder="Add description..."
                            rows="3"
                            style="
                                width: 100%; padding: 10px;
                                background: #1e293b; color: #e2e8f0;
                                border: 1px solid #334155; border-radius: 6px;
                                resize: vertical;
                            "
                        ></textarea>
                    </div>
                    
                    <div style="display: flex; gap: 8px;">
                        <div style="flex: 1;">
                            <label style="display: block; color: #94a3b8; font-size: 13px; margin-bottom: 6px;">Position X</label>
                            <input type="number" id="new-node-x" value="${x.toFixed(0)}" style="
                                width: 100%; padding: 10px;
                                background: #1e293b; color: #e2e8f0;
                                border: 1px solid #334155; border-radius: 6px;
                            ">
                        </div>
                        <div style="flex: 1;">
                            <label style="display: block; color: #94a3b8; font-size: 13px; margin-bottom: 6px;">Position Y</label>
                            <input type="number" id="new-node-y" value="${y.toFixed(0)}" style="
                                width: 100%; padding: 10px;
                                background: #1e293b; color: #e2e8f0;
                                border: 1px solid #334155; border-radius: 6px;
                            ">
                        </div>
                    </div>
                    
                    <div style="display: flex; gap: 8px; margin-top: 8px;">
                        <button onclick="window.GraphCanvasMenu.createNode()" style="
                            flex: 1; padding: 12px;
                            background: #3b82f6; color: white; border: none;
                            border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 14px;
                        ">Create Node</button>
                        <button onclick="window.GraphInfoCard.collapse()" style="
                            padding: 12px 24px;
                            background: #334155; color: #e2e8f0;
                            border: 1px solid #475569; border-radius: 6px;
                            cursor: pointer; font-weight: 600; font-size: 14px;
                        ">Cancel</button>
                    </div>
                </div>
            `;
            
            window.GraphInfoCard.showInlineContent('➕ Add New Node', content);
            
            setTimeout(() => {
                const input = document.getElementById('new-node-label');
                if (input) input.focus();
            }, 100);
        },

        createNode: async function() {
            const label = document.getElementById('new-node-label')?.value.trim();
            const type = document.getElementById('new-node-type')?.value;
            const description = document.getElementById('new-node-description')?.value.trim();
            const x = parseFloat(document.getElementById('new-node-x')?.value || 0);
            const y = parseFloat(document.getElementById('new-node-y')?.value || 0);
            
            if (!label) {
                alert('Please enter a node name');
                return;
            }
            
            const nodeData = {
                label: label,
                type: type,
                description: description,
                x: x,
                y: y
            };
            
            // Check for duplicates first
            try {
                const checkResponse = await fetch(`${this.apiBase}/api/graph/node/check-duplicate`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(nodeData)
                });
                
                if (checkResponse.ok) {
                    const checkResult = await checkResponse.json();
                    
                    if (checkResult.exists) {
                        // Show duplicate dialog
                        this.showDuplicateNodeDialog(nodeData, checkResult.node);
                        return;
                    }
                }
            } catch (e) {
                console.warn('Duplicate check failed, proceeding with creation:', e);
            }
            
            // No duplicate, proceed with creation
            await this.createNodeDirect(nodeData, false);
        },

        /**
         * Show dialog when duplicate node is detected
         */
        showDuplicateNodeDialog: function(newNodeData, existingNode) {
            const content = `
                <div style="display: flex; flex-direction: column; gap: 16px;">
                    <div style="
                        background: #451a03; border: 1px solid #f59e0b;
                        padding: 16px; border-radius: 8px;
                    ">
                        <div style="color: #fbbf24; font-weight: 700; margin-bottom: 8px; display: flex; align-items: center; gap: 8px;">
                            <span style="font-size: 20px;">⚠️</span>
                            Duplicate Node Detected
                        </div>
                        <div style="color: #fde68a; font-size: 13px; line-height: 1.5;">
                            A node with this name and type already exists in the graph.
                        </div>
                    </div>
                    
                    <div style="
                        background: #0f172a; padding: 14px;
                        border-radius: 8px; border: 1px solid #1e293b;
                    ">
                        <div style="color: #60a5fa; font-size: 11px; font-weight: 700; margin-bottom: 8px; text-transform: uppercase;">
                            Existing Node
                        </div>
                        <div style="color: #e2e8f0; font-size: 13px; margin-bottom: 4px;">
                            <strong>Name:</strong> ${this.escapeHtml(existingNode.name)}
                        </div>
                        <div style="color: #e2e8f0; font-size: 13px; margin-bottom: 4px;">
                            <strong>Type:</strong> ${this.escapeHtml(existingNode.type)}
                        </div>
                        <div style="color: #94a3b8; font-size: 11px; margin-top: 8px;">
                            <strong>ID:</strong> ${this.escapeHtml(existingNode.id)}
                        </div>
                        ${existingNode.properties?.description ? `
                            <div style="color: #94a3b8; font-size: 11px; margin-top: 4px;">
                                <strong>Description:</strong> ${this.escapeHtml(existingNode.properties.description)}
                            </div>
                        ` : ''}
                    </div>
                    
                    <div style="color: #94a3b8; font-size: 12px; line-height: 1.5;">
                        What would you like to do?
                    </div>
                    
                    <div style="display: flex; flex-direction: column; gap: 8px;">
                        <button 
                            onclick="window.GraphCanvasMenu.loadExistingNode('${this.escapeHtml(existingNode.id)}')"
                            style="
                                padding: 14px;
                                background: #3b82f6; color: white; border: none;
                                border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 14px;
                                display: flex; align-items: center; justify-content: center; gap: 8px;
                            "
                        >
                            <span>📥</span>
                            Load Existing Node to Graph
                        </button>
                        
                        <button 
                            onclick='window.GraphCanvasMenu.createNodeDirect(${JSON.stringify(newNodeData)}, true)'
                            style="
                                padding: 14px;
                                background: #f59e0b; color: white; border: none;
                                border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 14px;
                                display: flex; align-items: center; justify-content: center; gap: 8px;
                            "
                        >
                            <span>➕</span>
                            Create New Node Anyway (with unique ID)
                        </button>
                        
                        <button 
                            onclick="window.GraphInfoCard.collapse()"
                            style="
                                padding: 12px;
                                background: #334155; color: #e2e8f0;
                                border: 1px solid #475569; border-radius: 6px;
                                cursor: pointer; font-weight: 600; font-size: 14px;
                            "
                        >
                            Cancel
                        </button>
                    </div>
                </div>
            `;
            
            window.GraphInfoCard.showInlineContent('⚠️ Duplicate Node', content);
        },

        /**
         * Load existing node from Neo4j into the graph visualization
         */
        loadExistingNode: async function(nodeId) {
            try {
                // Fetch node details from Neo4j
                const response = await fetch(`${this.apiBase}/api/graph/cypher`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        query: "MATCH (n {id: $id}) RETURN n",
                        parameters: { id: nodeId }
                    })
                });
                
                if (!response.ok) {
                    throw new Error('Failed to fetch node');
                }
                
                const result = await response.json();
                
                if (result.nodes && result.nodes.length > 0) {
                    const node = result.nodes[0];
                    
                    // Check if already in visualization
                    const existing = network.body.data.nodes.get(node.id);
                    if (existing) {
                        network.selectNodes([node.id]);
                        network.focus(node.id, { animation: true });
                        this.showToast('Node already in graph - selected');
                    } else {
                        // Add to network
                        network.body.data.nodes.add({
                            id: node.id,
                            label: node.properties.name || node.properties.text || node.id,
                            color: node.color || this.getColorForType(node.properties.type),
                            title: `${node.properties.type}: ${node.properties.name || node.properties.text}`,
                            ...node.properties
                        });
                        
                        // Store in graphAddon
                        if (this.graphAddon && this.graphAddon.nodesData) {
                            this.graphAddon.nodesData[node.id] = {
                                display_name: node.properties.name || node.properties.text,
                                labels: node.labels || [],
                                properties: node.properties
                            };
                        }
                        
                        // Select and focus
                        network.selectNodes([node.id]);
                        network.focus(node.id, { animation: true });
                        
                        this.showToast('Existing node loaded');
                    }
                }
                
                if (window.GraphInfoCard) {
                    window.GraphInfoCard.collapse();
                }
                
            } catch (e) {
                console.error('Error loading existing node:', e);
                alert('Failed to load existing node: ' + e.message);
            }
        },

        /**
         * Create node directly (with force option for duplicates)
         */
        createNodeDirect: async function(nodeData, forceCreate = false) {
            const nodeId = 'node_' + Date.now();
            const visualNodeData = {
                id: nodeId,
                label: nodeData.label,
                x: nodeData.x || 0,
                y: nodeData.y || 0,
                color: this.getColorForType(nodeData.type),
                properties: {
                    type: nodeData.type,
                    description: nodeData.description,
                    created_at: new Date().toISOString()
                }
            };
            
            // Add to network
            network.body.data.nodes.add(visualNodeData);
            
            // Store in graphAddon
            if (this.graphAddon && this.graphAddon.nodesData) {
                this.graphAddon.nodesData[nodeId] = {
                    display_name: nodeData.label,
                    labels: [nodeData.type],
                    properties: visualNodeData.properties
                };
            }
            
            // Try to persist to Neo4j
            try {
                const url = forceCreate 
                    ? `${this.apiBase}/api/graph/node/create?force_create=true`
                    : `${this.apiBase}/api/graph/node/create`;
                    
                const response = await fetch(url, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        label: nodeData.label,
                        type: nodeData.type,
                        description: nodeData.description || '',
                        x: nodeData.x || 0,
                        y: nodeData.y || 0,
                        properties: {
                            ...visualNodeData.properties,
                            original_id: nodeId
                        }
                    })
                });
                
                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail?.message || error.detail || 'Failed to persist node');
                }
                
                const result = await response.json();
                
                // Update with backend ID
                if (result.node_id !== nodeId) {
                    network.body.data.nodes.update({
                        id: nodeId,
                        backend_id: result.node_id
                    });
                }
                
                this.showToast(forceCreate ? 'Node created (duplicate allowed)' : 'Node created and saved');
            } catch (e) {
                console.warn('Could not persist to Neo4j:', e);
                this.showToast('Node created (local only): ' + e.message);
            }
            
            // Select the new node
            network.selectNodes([nodeId]);
            
            // Collapse card
            if (window.GraphInfoCard) {
                window.GraphInfoCard.collapse();
            }
        },
        /**
         * Persist node to Neo4j using the node creation API
         */
        persistNodeToNeo4j: async function(nodeData) {
            const response = await fetch(`${this.apiBase}/api/graph/node/create`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    label: nodeData.label,
                    type: nodeData.properties.type,
                    description: nodeData.properties.description || '',
                    x: nodeData.x || 0,
                    y: nodeData.y || 0,
                    properties: {
                        ...nodeData.properties,
                        original_id: nodeData.id  // Store the frontend ID
                    }
                })
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to persist node');
            }
            
            const result = await response.json();
            
            // Update the node with the backend ID if different
            if (result.node_id !== nodeData.id) {
                // Update network with new ID from backend
                network.body.data.nodes.update({
                    id: nodeData.id,
                    backend_id: result.node_id
                });
            }
            
            return result;
        },


        addEdge: function() {
            const selectedNodes = network.getSelectedNodes();
            
            if (selectedNodes.length === 0) {
                alert('Please select one or two nodes first.\n\nTo create an edge:\n1. Select source node (click it)\n2. Right-click canvas and choose "Add Edge"\n3. Or select both nodes before using this option');
                return;
            }
            
            if (!window.GraphInfoCard) {
                alert('GraphInfoCard not available');
                return;
            }
            
            const allNodes = network.body.data.nodes.get();
            const sourceId = selectedNodes[0];
            const targetId = selectedNodes.length > 1 ? selectedNodes[1] : null;
            
            const content = `
                <div style="display: flex; flex-direction: column; gap: 16px;">
                    <div>
                        <label style="display: block; color: #94a3b8; font-size: 13px; margin-bottom: 6px; font-weight: 600;">From (Source)</label>
                        <select id="edge-source" style="
                            width: 100%; padding: 10px;
                            background: #1e293b; color: #e2e8f0;
                            border: 1px solid #334155; border-radius: 6px;
                        ">
                            ${allNodes.map(n => `<option value="${n.id}" ${n.id === sourceId ? 'selected' : ''}>${n.label || n.id}</option>`).join('')}
                        </select>
                    </div>
                    
                    <div>
                        <label style="display: block; color: #94a3b8; font-size: 13px; margin-bottom: 6px; font-weight: 600;">To (Target)</label>
                        <select id="edge-target" style="
                            width: 100%; padding: 10px;
                            background: #1e293b; color: #e2e8f0;
                            border: 1px solid #334155; border-radius: 6px;
                        ">
                            ${allNodes.map(n => `<option value="${n.id}" ${n.id === targetId ? 'selected' : ''}>${n.label || n.id}</option>`).join('')}
                        </select>
                    </div>
                    
                    <div>
                        <label style="display: block; color: #94a3b8; font-size: 13px; margin-bottom: 6px; font-weight: 600;">Relationship Type</label>
                        <select id="edge-type" style="
                            width: 100%; padding: 10px;
                            background: #1e293b; color: #e2e8f0;
                            border: 1px solid #334155; border-radius: 6px;
                        ">
                            <option value="RELATES_TO">RELATES_TO</option>
                            <option value="CONNECTED_TO">CONNECTED_TO</option>
                            <option value="DEPENDS_ON">DEPENDS_ON</option>
                            <option value="PARENT_OF">PARENT_OF</option>
                            <option value="CONTAINS">CONTAINS</option>
                            <option value="REFERENCES">REFERENCES</option>
                            <option value="SIMILAR_TO">SIMILAR_TO</option>
                            <option value="LEADS_TO">LEADS_TO</option>
                            <option value="CAUSED_BY">CAUSED_BY</option>
                        </select>
                    </div>
                    
                    <div>
                        <label style="display: block; color: #94a3b8; font-size: 13px; margin-bottom: 6px; font-weight: 600;">Label (optional)</label>
                        <input 
                            type="text" 
                            id="edge-label" 
                            placeholder="Edge label..."
                            style="
                                width: 100%; padding: 10px;
                                background: #1e293b; color: #e2e8f0;
                                border: 1px solid #334155; border-radius: 6px;
                            "
                        >
                    </div>
                    
                    <div style="display: flex; gap: 8px; margin-top: 8px;">
                        <button onclick="window.GraphCanvasMenu.createEdge()" style="
                            flex: 1; padding: 12px;
                            background: #3b82f6; color: white; border: none;
                            border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 14px;
                        ">Create Edge</button>
                        <button onclick="window.GraphInfoCard.collapse()" style="
                            padding: 12px 24px;
                            background: #334155; color: #e2e8f0;
                            border: 1px solid #475569; border-radius: 6px;
                            cursor: pointer; font-weight: 600; font-size: 14px;
                        ">Cancel</button>
                    </div>
                </div>
            `;
            
            window.GraphInfoCard.showInlineContent('🔗 Add New Edge', content);
        },

        createEdge: async function() {
            const sourceId = document.getElementById('edge-source')?.value;
            const targetId = document.getElementById('edge-target')?.value;
            const type = document.getElementById('edge-type')?.value;
            const label = document.getElementById('edge-label')?.value.trim();
            
            if (sourceId === targetId) {
                alert('Source and target must be different nodes');
                return;
            }
            
            const edgeId = 'edge_' + Date.now();
            const edgeData = {
                id: edgeId,
                from: sourceId,
                to: targetId,
                label: label || type,
                arrows: 'to',
                properties: {
                    type: type,
                    created_at: new Date().toISOString()
                }
            };
            
            // Add to network
            network.body.data.edges.add(edgeData);
            
            // Try to persist to Neo4j
            try {
                await this.persistEdgeToNeo4j(edgeData);
                this.showToast('Edge created and saved');
            } catch (e) {
                console.warn('Could not persist to Neo4j:', e);
                this.showToast('Edge created (local only)');
            }
            
            // Collapse card
            if (window.GraphInfoCard) {
                window.GraphInfoCard.collapse();
            }
        },


        /**
         * Persist edge to Neo4j using the edge creation API
         */
        persistEdgeToNeo4j: async function(edgeData) {
            // Get backend IDs if they exist
            const sourceNode = network.body.data.nodes.get(edgeData.from);
            const targetNode = network.body.data.nodes.get(edgeData.to);
            
            const sourceId = sourceNode?.backend_id || edgeData.from;
            const targetId = targetNode?.backend_id || edgeData.to;
            
            const response = await fetch(`${this.apiBase}/api/graph/edge/create`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    source_id: sourceId,
                    target_id: targetId,
                    relationship_type: edgeData.properties.type,
                    label: edgeData.label,
                    properties: {
                        ...edgeData.properties,
                        original_id: edgeData.id
                    }
                })
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to persist edge');
            }
            
            return await response.json();
        },
        // ============================================================
        // SELECTION ACTIONS
        // ============================================================

        selectAll: function() {
            const allNodeIds = network.body.data.nodes.getIds();
            network.selectNodes(allNodeIds);
            this.showToast(`Selected ${allNodeIds.length} nodes`);
        },

        clearSelection: function() {
            network.unselectAll();
            this.showToast('Selection cleared');
        },

        invertSelection: function() {
            const allNodeIds = network.body.data.nodes.getIds();
            const selectedIds = network.getSelectedNodes();
            const unselectedIds = allNodeIds.filter(id => !selectedIds.includes(id));
            network.selectNodes(unselectedIds);
            this.showToast(`Selected ${unselectedIds.length} nodes`);
        },

        // ============================================================
        // LAYOUT ACTIONS
        // ============================================================

        applyLayout: function(layoutType) {
            const nodes = network.body.data.nodes.get();
            
            switch(layoutType) {
                case 'hierarchical':
                    this.applyHierarchicalLayout(nodes);
                    break;
                case 'force':
                    this.applyForceLayout();
                    break;
                case 'circular':
                    this.applyCircularLayout(nodes);
                    break;
                case 'random':
                    this.applyRandomLayout(nodes);
                    break;
            }
        },

        applyHierarchicalLayout: function(nodes) {
            network.setOptions({
                layout: {
                    hierarchical: {
                        enabled: true,
                        direction: 'UD',
                        sortMethod: 'directed',
                        levelSeparation: 150,
                        nodeSpacing: 200
                    }
                }
            });
            
            network.stabilize();
            
            setTimeout(() => {
                network.fit();
                this.showToast('Hierarchical layout applied');
            }, 1000);
        },

        applyForceLayout: function() {
            network.setOptions({
                layout: {
                    hierarchical: {
                        enabled: false
                    }
                },
                physics: {
                    enabled: true,
                    solver: 'forceAtlas2Based',
                    forceAtlas2Based: {
                        gravitationalConstant: -50,
                        centralGravity: 0.01,
                        springLength: 100,
                        springConstant: 0.08
                    }
                }
            });
            
            network.stabilize();
            this.showToast('Force layout applied');
        },

        applyCircularLayout: function(nodes) {
            const radius = Math.max(200, nodes.length * 30);
            const angleStep = (2 * Math.PI) / nodes.length;
            
            const updates = nodes.map((node, index) => ({
                id: node.id,
                x: radius * Math.cos(index * angleStep),
                y: radius * Math.sin(index * angleStep),
                physics: false
            }));
            
            network.body.data.nodes.update(updates);
            
            setTimeout(() => {
                network.fit();
                this.showToast('Circular layout applied');
            }, 100);
        },

        applyRandomLayout: function(nodes) {
            const spread = 500;
            
            const updates = nodes.map(node => ({
                id: node.id,
                x: (Math.random() - 0.5) * spread,
                y: (Math.random() - 0.5) * spread,
                physics: false
            }));
            
            network.body.data.nodes.update(updates);
            
            setTimeout(() => {
                network.fit();
                this.showToast('Random layout applied');
            }, 100);
        },

        // ============================================================
        // STYLE ACTIONS
        // ============================================================

        applyStylePreset: function(preset) {
            let nodeOptions = {};
            let edgeOptions = {};
            
            switch(preset) {
                case 'default':
                    nodeOptions = {
                        shape: 'dot',
                        size: 15,
                        font: {size: 14, color: '#ffffff'}
                    };
                    edgeOptions = {
                        width: 1,
                        color: {color: '#848484'}
                    };
                    break;
                    
                case 'minimal':
                    nodeOptions = {
                        shape: 'dot',
                        size: 10,
                        font: {size: 0}
                    };
                    edgeOptions = {
                        width: 0.5,
                        color: {color: '#404040'}
                    };
                    break;
                    
                case 'vibrant':
                    nodeOptions = {
                        shape: 'dot',
                        size: 20,
                        font: {size: 16, color: '#ffffff', bold: true}
                    };
                    edgeOptions = {
                        width: 2,
                        color: {color: '#60a5fa'}
                    };
                    break;
            }
            
            network.setOptions({
                nodes: nodeOptions,
                edges: edgeOptions
            });
            
            this.showToast(`${preset} style applied`);
        },

        // ============================================================
        // EXPORT ACTIONS
        // ============================================================

        exportImage: function() {
            const canvas = document.querySelector('#graph-container canvas');
            if (canvas) {
                const link = document.createElement('a');
                link.download = `graph_${new Date().getTime()}.png`;
                link.href = canvas.toDataURL();
                link.click();
                this.showToast('Image exported');
            } else {
                alert('Canvas not found for export');
            }
        },

        exportJSON: function() {
            const data = {
                nodes: network.body.data.nodes.get(),
                edges: network.body.data.edges.get(),
                exported: new Date().toISOString(),
                metadata: {
                    node_count: network.body.data.nodes.length,
                    edge_count: network.body.data.edges.length
                }
            };
            
            const blob = new Blob([JSON.stringify(data, null, 2)], {type: 'application/json'});
            const link = document.createElement('a');
            link.download = `graph_${new Date().getTime()}.json`;
            link.href = URL.createObjectURL(blob);
            link.click();
            
            this.showToast('JSON exported');
        },

        // ============================================================
        // SETTINGS
        // ============================================================

        togglePhysics: function() {
            const currentState = network.physics.options.enabled;
            network.setOptions({
                physics: {
                    enabled: !currentState
                }
            });
            
            const status = !currentState ? 'enabled' : 'disabled';
            this.showToast(`Physics ${status}`);
        },

        showSettings: function() {
            if (!window.GraphInfoCard) {
                alert('GraphInfoCard not available');
                return;
            }
            
            const physicsEnabled = network.physics.options.enabled;
            
            const content = `
                <div style="display: flex; flex-direction: column; gap: 12px;">
                    <!-- Physics -->
                    <div style="
                        background: #0f172a; padding: 14px;
                        border-radius: 8px; border: 1px solid #1e293b;
                    ">
                        <label style="
                            display: flex; align-items: center;
                            justify-content: space-between; cursor: pointer;
                        ">
                            <span style="color: #e2e8f0; font-weight: 600;">Physics Simulation</span>
                            <input type="checkbox" id="settings-physics" ${physicsEnabled ? 'checked' : ''} 
                                onchange="window.GraphCanvasMenu.togglePhysics()"
                                style="width: 18px; height: 18px; cursor: pointer;">
                        </label>
                        <div style="color: #94a3b8; font-size: 11px; margin-top: 6px;">
                            Force-directed automatic layout
                        </div>
                    </div>
                    
                    <!-- Node Labels -->
                    <div style="
                        background: #0f172a; padding: 14px;
                        border-radius: 8px; border: 1px solid #1e293b;
                    ">
                        <label style="
                            display: flex; align-items: center;
                            justify-content: space-between; cursor: pointer;
                        ">
                            <span style="color: #e2e8f0; font-weight: 600;">Show Node Labels</span>
                            <input type="checkbox" id="settings-labels" checked 
                                onchange="window.GraphCanvasMenu.toggleLabels()"
                                style="width: 18px; height: 18px; cursor: pointer;">
                        </label>
                    </div>
                    
                    <!-- Edge Labels -->
                    <div style="
                        background: #0f172a; padding: 14px;
                        border-radius: 8px; border: 1px solid #1e293b;
                    ">
                        <label style="
                            display: flex; align-items: center;
                            justify-content: space-between; cursor: pointer;
                        ">
                            <span style="color: #e2e8f0; font-weight: 600;">Show Edge Labels</span>
                            <input type="checkbox" id="settings-edge-labels" checked 
                                onchange="window.GraphCanvasMenu.toggleEdgeLabels()"
                                style="width: 18px; height: 18px; cursor: pointer;">
                        </label>
                    </div>
                    
                    <!-- Node Size -->
                    <div style="
                        background: #0f172a; padding: 14px;
                        border-radius: 8px; border: 1px solid #1e293b;
                    ">
                        <label style="color: #e2e8f0; font-weight: 600; display: block; margin-bottom: 10px;">
                            Node Size: <span id="node-size-value">15</span>px
                        </label>
                        <input type="range" id="settings-node-size" min="5" max="50" value="15" 
                            oninput="window.GraphCanvasMenu.updateNodeSize(this.value)"
                            style="width: 100%;">
                    </div>
                    
                    <!-- Edge Width -->
                    <div style="
                        background: #0f172a; padding: 14px;
                        border-radius: 8px; border: 1px solid #1e293b;
                    ">
                        <label style="color: #e2e8f0; font-weight: 600; display: block; margin-bottom: 10px;">
                            Edge Width: <span id="edge-width-value">1</span>px
                        </label>
                        <input type="range" id="settings-edge-width" min="0.5" max="5" step="0.5" value="1" 
                            oninput="window.GraphCanvasMenu.updateEdgeWidth(this.value)"
                            style="width: 100%;">
                    </div>
                </div>
            `;
            
            window.GraphInfoCard.showInlineContent('⚙️ Canvas Settings', content);
        },

        toggleLabels: function() {
            const checkbox = document.getElementById('settings-labels');
            const fontSize = checkbox.checked ? 14 : 0;
            network.setOptions({
                nodes: {
                    font: {size: fontSize}
                }
            });
            this.showToast(checkbox.checked ? 'Labels shown' : 'Labels hidden');
        },

        toggleEdgeLabels: function() {
            const checkbox = document.getElementById('settings-edge-labels');
            const fontSize = checkbox.checked ? 12 : 0;
            network.setOptions({
                edges: {
                    font: {size: fontSize}
                }
            });
            this.showToast(checkbox.checked ? 'Edge labels shown' : 'Edge labels hidden');
        },

        updateNodeSize: function(size) {
            document.getElementById('node-size-value').textContent = size;
            network.setOptions({
                nodes: {
                    size: parseInt(size)
                }
            });
        },

        updateEdgeWidth: function(width) {
            document.getElementById('edge-width-value').textContent = width;
            network.setOptions({
                edges: {
                    width: parseFloat(width)
                }
            });
        },

        // ============================================================
        // SEARCH & INSIGHTS
        // ============================================================

        showSearchDialog: function() {
            this.showToast('Graph search - use tool menu or context actions');
        },

        showPatternFinder: function() {
            this.showToast('Pattern finder - coming soon');
        },

        analyzeGraphStructure: async function() {
            try {
                const response = await fetch(`${this.apiBase}/api/graph/stats`);
                const stats = await response.json();
                
                const content = `
                    <div style="display: flex; flex-direction: column; gap: 14px;">
                        <div style="
                            background: #0f172a; padding: 16px;
                            border-radius: 8px; border: 1px solid #1e293b;
                        ">
                            <div style="color: #60a5fa; font-size: 12px; font-weight: 600; margin-bottom: 10px;">Overview</div>
                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
                                <div>
                                    <div style="color: #94a3b8; font-size: 11px;">Total Nodes</div>
                                    <div style="color: #e2e8f0; font-size: 24px; font-weight: 600;">${stats.total_nodes || 0}</div>
                                </div>
                                <div>
                                    <div style="color: #94a3b8; font-size: 11px;">Total Edges</div>
                                    <div style="color: #e2e8f0; font-size: 24px; font-weight: 600;">${stats.total_relationships || 0}</div>
                                </div>
                            </div>
                        </div>
                        
                        <div style="
                            background: #0f172a; padding: 16px;
                            border-radius: 8px; border: 1px solid #1e293b;
                        ">
                            <div style="color: #60a5fa; font-size: 12px; font-weight: 600; margin-bottom: 10px;">Metrics</div>
                            <div style="color: #e2e8f0; font-size: 12px; line-height: 1.6;">
                                Average degree: ${((stats.total_relationships || 0) * 2 / (stats.total_nodes || 1)).toFixed(2)}<br>
                                Density: ${((stats.total_relationships || 0) / ((stats.total_nodes || 1) * (stats.total_nodes - 1) / 2) * 100).toFixed(4)}%
                            </div>
                        </div>
                    </div>
                `;
                
                window.GraphInfoCard.showInlineContent('📊 Graph Analysis', content);
            } catch (e) {
                this.showToast('Analysis failed');
            }
        },

        findCommunities: function() {
            this.showToast('Community detection - use AI tools');
        },

        // ============================================================
        // UTILITIES
        // ============================================================

        getColorForType: function(type) {
            const colors = {
                'Entity': '#60a5fa',
                'Concept': '#a78bfa',
                'Person': '#f472b6',
                'Place': '#4ade80',
                'Event': '#fb923c',
                'Document': '#fbbf24',
                'Custom': '#94a3b8'
            };
            return colors[type] || '#60a5fa';
        },

        escapeHtml: function(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        },

        /**
         * Populate chat input
         */
        populateChat: function(prompt, autoSend = false) {
            const chatInput = document.getElementById('messageInput');
            if (chatInput) {
                chatInput.value = prompt;
                chatInput.focus();
                
                const chatSection = document.getElementById('chatMessages');
                if (chatSection) {
                    chatSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                }
                
                if (autoSend) {
                    const sendButton = document.querySelector('#chat-section button[type="submit"]');
                    if (sendButton) {
                        setTimeout(() => {
                            if (confirm('Send request to Vera?')) {
                                sendButton.click();
                            }
                        }, 100);
                    }
                }
            } else {
                alert('Chat interface not found. Please copy this:\n\n' + prompt);
            }
        },

        showToast: function(message) {
            document.querySelectorAll('.canvas-menu-toast').forEach(t => t.remove());
            
            const toast = document.createElement('div');
            toast.className = 'canvas-menu-toast';
            toast.textContent = message;
            toast.style.cssText = `
                position: fixed; top: 20px; right: 20px; z-index: 10000;
                background: #1e293b; color: #e2e8f0; padding: 12px 20px;
                border-radius: 6px; border: 1px solid #334155;
                box-shadow: 0 4px 12px rgba(0,0,0,0.3);
                transition: opacity 0.3s;
            `;
            document.body.appendChild(toast);
            
            setTimeout(() => {
                toast.style.opacity = '0';
                setTimeout(() => toast.remove(), 300);
            }, 2000);
        }
    };
})();