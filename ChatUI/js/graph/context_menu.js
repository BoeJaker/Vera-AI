/**
 * GraphContextMenu Module
 * Handles all context menu interactions and routing to appropriate handlers
 * Integrates with the modular GraphCore system
 */

(function() {
    'use strict';
    
    window.GraphContextMenu = {
        
        // Core references
        core: null,
        discovery: null,
        
        // State
        contextMenuNode: null,
        initialized: false,
        
        /**
         * Initialize the context menu module
         * @param {Object} graphCore - Reference to GraphCore
         */
        async init(graphCore) {
            if (this.initialized) {
                console.warn('GraphContextMenu already initialized');
                return;
            }
            
            console.log('GraphContextMenu: Initializing...');
            
            this.core = graphCore;
            
            // Wait for GraphDiscovery if it exists
            if (window.GraphDiscovery) {
                this.discovery = window.GraphDiscovery;
                
                // Ensure GraphDiscovery is initialized
                if (!this.discovery.initialized && this.discovery.init) {
                    await this.discovery.init(graphCore);
                }
            }
            
            this._setupEventListeners();
            this._setupClickAwayListener();
            
            this.initialized = true;
            console.log('GraphContextMenu: ✓ Initialized');
        },
        
        /**
         * Setup event listeners for context menu
         */
        _setupEventListeners() {
            if (!this.core?.networkInstance) {
                console.error('GraphContextMenu: Network instance not available');
                return;
            }
            
            const network = this.core.networkInstance;
            
            // Right-click on network to show context menu
            network.on("oncontext", (params) => {
                params.event.preventDefault();
                
                const nodeId = network.getNodeAt(params.pointer.DOM);
                if (nodeId) {
                    console.log('GraphContextMenu: Context menu triggered for node:', nodeId);
                    this.contextMenuNode = nodeId;
                    this._showContextMenu(params.event.clientX, params.event.clientY);
                }
            });
            
            // Handle context menu item clicks
            const contextMenu = document.getElementById('context-menu');
            if (contextMenu) {
                contextMenu.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const item = e.target.closest('.context-menu-item');
                    if (item) {
                        const action = item.getAttribute('data-action');
                        console.log('GraphContextMenu: Action triggered:', action);
                        this._handleAction(action);
                    }
                });
                console.log('GraphContextMenu: Event listeners attached');
            } else {
                console.warn('GraphContextMenu: #context-menu element not found');
            }
        },
        
        /**
         * Setup click-away listener to hide menu
         */
        _setupClickAwayListener() {
            document.addEventListener('click', () => this._hideContextMenu());
        },
        
        /**
         * Show context menu at position
         */
        _showContextMenu(x, y) {
            const menu = document.getElementById('context-menu');
            if (menu) {
                menu.style.display = 'block';
                menu.style.left = x + 'px';
                menu.style.top = y + 'px';
            }
        },
        
        /**
         * Hide context menu
         */
        _hideContextMenu() {
            const menu = document.getElementById('context-menu');
            if (menu) {
                menu.style.display = 'none';
            }
        },
        
        /**
         * Handle context menu action
         */
        _handleAction(action) {
            this._hideContextMenu();
            
            if (!this.contextMenuNode) {
                console.warn('GraphContextMenu: No node selected');
                return;
            }
            
            // Get node data using the new modular API
            const nodeData = this.core.getNodeData(this.contextMenuNode);
            const nodeName = nodeData ? nodeData.display_name : this.contextMenuNode;
            
            console.log(`GraphContextMenu: Executing ${action} on ${nodeName}`);
            
            // Route to appropriate handler
            const handler = this._getActionHandler(action);
            if (handler) {
                handler.call(this, this.contextMenuNode, nodeName, nodeData);
            } else {
                console.warn(`GraphContextMenu: Unknown action: ${action}`);
            }
        },
        
        /**
         * Get handler for specific action
         */
        _getActionHandler(action) {
            const handlers = {
                // Discovery Actions
                'hidden-relationships': this._handleHiddenRelationships,
                'similar-nodes': this._handleSimilarNodes,
                'find-paths': this._handleFindPaths,
                'expand-neighbors': this._handleExpandNeighbors,
                'clear-discovered': this._handleClearDiscovered,
                
                // View Actions
                'subgraph': this._handleSubgraph,
                
                // Analysis Actions
                'search': this._handleSearch,
                'enrich': this._handleEnrich,
                'extract-entities': this._handleExtractEntities,
                
                // Generate Actions
                'discover': this._handleDiscover,
                'ideas': this._handleGenerateIdeas,
                
                // AI Actions
                'ask-vera': this._handleAskVera,
                
                // Tool Execution
                'execute-tool': this._handleExecuteTool
            };
            
            return handlers[action];
        },
        
        // ============================================================
        // DISCOVERY ACTIONS (Route to GraphDiscovery)
        // ============================================================
        
        _handleHiddenRelationships(nodeId, nodeName, nodeData) {
            if (!this.discovery) {
                this._showModuleNotAvailable('GraphDiscovery');
                return;
            }
            
            if (this.discovery.findHiddenRelationships) {
                this.discovery.findHiddenRelationships(nodeId);
            } else {
                console.error('GraphContextMenu: findHiddenRelationships not available');
            }
        },
        
        _handleSimilarNodes(nodeId, nodeName, nodeData) {
            if (!this.discovery) {
                this._showModuleNotAvailable('GraphDiscovery');
                return;
            }
            
            if (this.discovery.findSimilarNodes) {
                this.discovery.findSimilarNodes(nodeId);
            } else {
                console.error('GraphContextMenu: findSimilarNodes not available');
            }
        },
        
        _handleFindPaths(nodeId, nodeName, nodeData) {
            if (!this.discovery) {
                this._showModuleNotAvailable('GraphDiscovery');
                return;
            }
            
            if (this.discovery.showPathFinder) {
                this.discovery.showPathFinder(nodeId);
            } else {
                console.error('GraphContextMenu: showPathFinder not available');
            }
        },
        
        _handleExpandNeighbors(nodeId, nodeName, nodeData) {
            this._showExpandDialog(nodeId, nodeName);
        },
        
        _handleClearDiscovered(nodeId, nodeName, nodeData) {
            if (!this.discovery) {
                this._showModuleNotAvailable('GraphDiscovery');
                return;
            }
            
            if (this.discovery.clearDiscoveredRelationships) {
                this.discovery.clearDiscoveredRelationships();
            } else {
                console.error('GraphContextMenu: clearDiscoveredRelationships not available');
            }
        },
        
        // ============================================================
        // VIEW ACTIONS
        // ============================================================
        
        _handleSubgraph(nodeId, nodeName, nodeData) {
            // Use GraphCore's networkInstance directly
            if (!this.core?.networkInstance) {
                console.error('GraphContextMenu: Network not available');
                return;
            }
            
            this._extractSubgraph(nodeId);
        },
        
        /**
         * Extract and display subgraph centered on a node
         */
        _extractSubgraph(centerNodeId) {
            console.log('GraphContextMenu: Extracting subgraph for node:', centerNodeId);
            
            try {
                const network = this.core.networkInstance;
                const connectedNodes = network.getConnectedNodes(centerNodeId);
                const subgraphNodes = [centerNodeId, ...connectedNodes];
                
                const allEdges = network.body.data.edges.get();
                const subgraphEdges = allEdges.filter(edge => {
                    return subgraphNodes.includes(edge.from) && subgraphNodes.includes(edge.to);
                });
                
                // Hide nodes not in subgraph
                const allNodeIds = Object.keys(this.core.data.nodesData);
                const nodeUpdates = allNodeIds.map(nodeId => ({
                    id: nodeId,
                    hidden: !subgraphNodes.includes(nodeId)
                }));
                network.body.data.nodes.update(nodeUpdates);
                
                // Hide edges not in subgraph
                const edgeUpdates = allEdges.map(edge => ({
                    id: edge.id,
                    hidden: !subgraphEdges.some(e => e.id === edge.id)
                }));
                network.body.data.edges.update(edgeUpdates);
                
                // Fit view to subgraph
                setTimeout(() => {
                    network.fit({
                        nodes: subgraphNodes,
                        animation: { duration: 1000, easingFunction: 'easeInOutQuad' }
                    });
                }, 100);
                
                // Show info in panel
                const nodeData = this.core.getNodeData(centerNodeId);
                const nodeName = nodeData ? nodeData.display_name : centerNodeId;
                
                this._showSubgraphInfo(nodeName, subgraphNodes.length, subgraphEdges.length);
                
            } catch (error) {
                console.error('GraphContextMenu: Error extracting subgraph:', error);
                alert('Error extracting subgraph. See console for details.');
            }
        },
        
        /**
         * Show subgraph info in panel
         */
        _showSubgraphInfo(nodeName, nodeCount, edgeCount) {
            if (!this.core?.ui) return;
            
            const panel = document.getElementById('property-panel');
            const content = document.getElementById('panel-content');
            
            if (!panel || !content) return;
            
            content.innerHTML = `
                <div style="text-align:center; padding:20px;">
                    <div style="font-size:24px; margin-bottom:10px;">🗺️</div>
                    <div style="font-weight:bold; color:#60a5fa; margin-bottom:10px;">Subgraph Extracted</div>
                    <div style="color:#cbd5e1; font-size:13px; margin-bottom:15px;">
                        Centered on: <strong>${this._escapeHtml(nodeName)}</strong>
                    </div>
                    <div style="background:#0f172a; padding:12px; border-radius:6px; margin-bottom:15px;">
                        <div style="color:#94a3b8; font-size:12px;">
                            <div>Nodes: <strong style="color:#60a5fa;">${nodeCount}</strong></div>
                            <div style="margin-top:4px;">Edges: <strong style="color:#60a5fa;">${edgeCount}</strong></div>
                        </div>
                    </div>
                    <button onclick="window.GraphContextMenu.resetSubgraph()" style="
                        background:#3b82f6; color:white; border:none; padding:8px 16px;
                        border-radius:6px; cursor:pointer; font-weight:600; font-size:13px;
                    ">Show Full Graph</button>
                </div>
            `;
            panel.style.display = 'flex';
        },
        
        /**
         * Reset to full graph view
         */
        resetSubgraph() {
            console.log('GraphContextMenu: Resetting to full graph');
            
            const network = this.core.networkInstance;
            const allNodeIds = Object.keys(this.core.data.nodesData);
            
            // Show all nodes
            const nodeUpdates = allNodeIds.map(nodeId => ({
                id: nodeId,
                hidden: false
            }));
            network.body.data.nodes.update(nodeUpdates);
            
            // Show all edges
            const allEdges = network.body.data.edges.get();
            const edgeUpdates = allEdges.map(edge => ({
                id: edge.id,
                hidden: false
            }));
            network.body.data.edges.update(edgeUpdates);
            
            // Re-apply filters
            if (this.core.filters) {
                this.core.filters.apply();
            }
            
            // Reset focus
            if (this.core.ui) {
                this.core.ui.resetFocus();
                this.core.ui.closePanel();
            }
        },
        
        // ============================================================
        // ANALYSIS ACTIONS (Placeholder implementations)
        // ============================================================
        
        _handleSearch(nodeId, nodeName, nodeData) {
            console.log('GraphContextMenu: Search action for node:', nodeName);
            alert(`Search functionality will be implemented for: ${nodeName}`);
        },
        
        _handleEnrich(nodeId, nodeName, nodeData) {
            console.log('GraphContextMenu: Enrich (NLP) action for node:', nodeName);
            alert(`NLP Analysis will be performed on: ${nodeName}`);
        },
        
        _handleExtractEntities(nodeId, nodeName, nodeData) {
            console.log('GraphContextMenu: Extract entities action for node:', nodeName);
            alert(`Entity extraction will be performed on: ${nodeName}`);
        },
        
        // ============================================================
        // GENERATE ACTIONS (Placeholder implementations)
        // ============================================================
        
        _handleDiscover(nodeId, nodeName, nodeData) {
            console.log('GraphContextMenu: Discover action for node:', nodeName);
            alert(`Discovery mode for: ${nodeName}`);
        },
        
        _handleGenerateIdeas(nodeId, nodeName, nodeData) {
            console.log('GraphContextMenu: Generate ideas action for node:', nodeName);
            alert(`Generating idea stubs for: ${nodeName}`);
        },
        
        // ============================================================
        // AI ACTIONS
        // ============================================================
        
        _handleAskVera(nodeId, nodeName, nodeData) {
            console.log('GraphContextMenu: Ask Vera action for node:', nodeId);
            
            // Build context about the node
            let nodeContext = `Node: ${nodeName}\n`;
            
            if (nodeData) {
                if (nodeData.labels && nodeData.labels.length > 0) {
                    nodeContext += `Type: ${nodeData.labels.join(', ')}\n`;
                }
                
                if (nodeData.properties) {
                    const importantProps = ['text', 'body', 'summary', 'description', 'content', 'type'];
                    for (const prop of importantProps) {
                        if (nodeData.properties[prop]) {
                            let value = nodeData.properties[prop];
                            if (typeof value === 'string' && value.length > 200) {
                                value = value.substring(0, 200) + '...';
                            }
                            nodeContext += `${prop}: ${value}\n`;
                        }
                    }
                }
            }
            
            // Pre-fill the chat input
            const question = `Can you tell me more about this node?\n\n${nodeContext}`;
            
            const chatInput = document.getElementById('message-input');
            if (chatInput) {
                chatInput.value = question;
                chatInput.focus();
                
                const chatSection = document.getElementById('chat-section');
                if (chatSection) {
                    chatSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                }
                
                console.log('GraphContextMenu: Chat input populated with node context');
            } else {
                console.warn('GraphContextMenu: Chat input not found');
                alert(`Ask Vera about: ${nodeName}\n\n${nodeContext}\n\nCopy this to the chat.`);
            }
        },
        
        // ============================================================
        // TOOL EXECUTION
        // ============================================================
        
        _handleExecuteTool(nodeId, nodeName, nodeData) {
            if (window.GraphToolExecutor) {
                window.GraphToolExecutor.showToolSelector(nodeId);
            } else {
                console.warn('GraphContextMenu: GraphToolExecutor not loaded');
                this._showModuleNotAvailable('GraphToolExecutor');
            }
        },
        
        // ============================================================
        // UI HELPERS
        // ============================================================
        
        /**
         * Show expand neighbors dialog with slider
         */
        _showExpandDialog(nodeId, nodeName) {
            const panel = document.getElementById('property-panel');
            const content = document.getElementById('panel-content');
            
            if (!panel || !content) return;
            
            content.innerHTML = `
                <div style="padding: 20px;">
                    <div class="section">
                        <div class="section-title">🔎 Expand Neighbors</div>
                        <div style="color: #94a3b8; font-size: 13px; margin-bottom: 16px;">
                            Expand connections for: <strong style="color: #e2e8f0;">${this._escapeHtml(nodeName)}</strong>
                        </div>
                        
                        <div style="background: #0f172a; padding: 16px; border-radius: 8px; border: 1px solid #1e293b;">
                            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
                                <label style="color: #94a3b8; font-size: 13px; font-weight: 600;">Depth (Hops)</label>
                                <div style="display: flex; align-items: center; gap: 12px;">
                                    <input 
                                        type="number" 
                                        id="expand-depth-input" 
                                        value="2" 
                                        min="1" 
                                        max="10"
                                        style="
                                            width: 60px; padding: 6px 10px;
                                            background: #1e293b; color: #e2e8f0;
                                            border: 1px solid #334155; border-radius: 6px;
                                            font-size: 14px; font-weight: 600; text-align: center;
                                        "
                                        oninput="document.getElementById('expand-depth-slider').value = this.value"
                                    >
                                </div>
                            </div>
                            
                            <input 
                                type="range" 
                                id="expand-depth-slider" 
                                value="2" 
                                min="1" 
                                max="10" 
                                step="1"
                                style="
                                    width: 100%; height: 8px;
                                    background: linear-gradient(to right, #3b82f6 0%, #60a5fa 100%);
                                    border-radius: 4px; outline: none;
                                    -webkit-appearance: none;
                                "
                                oninput="document.getElementById('expand-depth-input').value = this.value"
                            >
                            
                            <div style="display: flex; justify-content: space-between; margin-top: 8px; color: #64748b; font-size: 11px;">
                                <span>1 hop</span>
                                <span>5 hops</span>
                                <span>10 hops</span>
                            </div>
                            
                            <div style="margin-top: 16px; padding: 12px; background: rgba(59, 130, 246, 0.1); border-radius: 6px; border: 1px solid rgba(59, 130, 246, 0.2);">
                                <div style="color: #60a5fa; font-size: 11px; font-weight: 600; margin-bottom: 4px;">💡 Tip</div>
                                <div style="color: #94a3b8; font-size: 11px; line-height: 1.4;">
                                    Higher depths find more connections but may take longer.<br>
                                    Start with 2-3 hops for best results.
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div style="display: flex; gap: 8px; margin-top: 20px;">
                        <button onclick="
                            const depth = parseInt(document.getElementById('expand-depth-input').value);
                            if (window.GraphContextMenu.discovery && window.GraphContextMenu.discovery.expandNeighbors) {
                                window.GraphContextMenu.discovery.expandNeighbors('${nodeId}', depth);
                            }
                        " style="
                            flex: 1; padding: 12px;
                            background: #3b82f6; color: white; border: none;
                            border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 14px;
                        ">Expand</button>
                        <button onclick="
                            if (window.GraphContextMenu.core && window.GraphContextMenu.core.ui) {
                                window.GraphContextMenu.core.ui.closePanel();
                            }
                        " style="
                            padding: 12px 24px;
                            background: #334155; color: #e2e8f0; border: 1px solid #475569;
                            border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 14px;
                        ">Cancel</button>
                    </div>
                </div>
                
                <style>
                    /* Custom slider styling */
                    #expand-depth-slider::-webkit-slider-thumb {
                        -webkit-appearance: none;
                        appearance: none;
                        width: 20px;
                        height: 20px;
                        border-radius: 50%;
                        background: #3b82f6;
                        cursor: pointer;
                        border: 3px solid #ffffff;
                        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
                    }
                    
                    #expand-depth-slider::-moz-range-thumb {
                        width: 20px;
                        height: 20px;
                        border-radius: 50%;
                        background: #3b82f6;
                        cursor: pointer;
                        border: 3px solid #ffffff;
                        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
                    }
                </style>
            `;
            
            panel.style.display = 'flex';
        },
        
        /**
         * Show module not available message
         */
        _showModuleNotAvailable(moduleName) {
            alert(`${moduleName} module is not available. Please ensure it is loaded.`);
        },
        
        /**
         * Escape HTML special characters
         */
        _escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
    };
})();