/**
 * GraphContextMenu Module
 * Handles all context menu interactions and routing to appropriate handlers
 */

(function() {
    'use strict';
    
    window.GraphContextMenu = {
        
        // Store references
        graphAddon: null,
        graphDiscovery: null,
        contextMenuNode: null,
        
        /**
         * Initialize the module
         */
        init: function(graphAddon, graphDiscovery) {
            console.log('GraphContextMenu.init called');
            console.log('  graphAddon:', graphAddon ? 'SET' : 'NULL');
            console.log('  graphDiscovery:', graphDiscovery ? 'SET' : 'NULL');
            
            this.graphAddon = graphAddon;
            this.graphDiscovery = graphDiscovery;
            this.waitForNetwork();
            console.log('GraphContextMenu module initialized, waiting for network...');
        },
        
        /**
         * Wait for network to be ready before setting up listeners
         */
        waitForNetwork: function() {
            if (typeof network !== 'undefined' && network.body && network.body.data) {
                console.log('Network ready, setting up context menu listeners');
                this.setupEventListeners();
            } else {
                console.log('Network not ready, waiting...');
                setTimeout(() => this.waitForNetwork(), 500);
            }
        },
        
        /**
         * Setup event listeners for context menu
         */
        setupEventListeners: function() {
            const self = this;
            
            console.log('Setting up context menu event listeners');
            
            // Right-click on network to show context menu
            network.on("oncontext", function(params) {
                params.event.preventDefault();
                
                const nodeId = network.getNodeAt(params.pointer.DOM);
                if (nodeId) {
                    console.log('Context menu triggered for node:', nodeId);
                    self.contextMenuNode = nodeId;
                    self.showContextMenu(params.event.clientX, params.event.clientY);
                }
            });
            
            // Click anywhere to hide context menu
            document.addEventListener('click', () => self.hideContextMenu());
            
            // Handle context menu item clicks
            const contextMenu = document.getElementById('context-menu');
            if (contextMenu) {
                contextMenu.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const item = e.target.closest('.context-menu-item');
                    if (item) {
                        const action = item.getAttribute('data-action');
                        console.log('Context menu action triggered:', action);
                        self.handleAction(action);
                    }
                });
                console.log('Context menu event listeners set up successfully');
            } else {
                console.warn('Context menu element #context-menu not found!');
            }
        },
        
        /**
         * Show context menu at position
         */
        showContextMenu: function(x, y) {
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
        hideContextMenu: function() {
            const menu = document.getElementById('context-menu');
            if (menu) {
                menu.style.display = 'none';
            }
        },
        
        /**
         * Handle context menu action
         */
        handleAction: function(action) {
            this.hideContextMenu();
            
            if (!this.contextMenuNode) return;
            
            // Safety check
            if (!this.graphAddon || !this.graphAddon.nodesData) {
                console.error('GraphAddon not initialized!');
                alert('Graph system not ready. Please wait a moment and try again.');
                return;
            }
            
            if (!this.graphDiscovery) {
                console.error('GraphDiscovery not initialized!');
                alert('Discovery system not ready. Please wait a moment and try again.');
                return;
            }
            
            const nodeData = this.graphAddon.nodesData[this.contextMenuNode];
            const nodeName = nodeData ? nodeData.display_name : this.contextMenuNode;
            
            console.log(`Context menu action: ${action} on node: ${nodeName}`);
            
            switch(action) {
                // Discovery Actions - Route to GraphDiscovery module
                case 'hidden-relationships':
                    this.graphDiscovery.findHiddenRelationships(this.contextMenuNode);
                    break;
                    
                case 'similar-nodes':
                    this.graphDiscovery.findSimilarNodes(this.contextMenuNode);
                    break;
                    
                case 'find-paths':
                    this.graphDiscovery.showPathFinder(this.contextMenuNode);
                    break;
                    
                // Expansion Actions - Show slider dialog
                case 'expand-neighbors':
                    this.showExpandDialog(this.contextMenuNode);
                    break;
                    
                // View Actions - Route to GraphAddon
                case 'subgraph':
                    if (this.graphAddon.extractSubgraph) {
                        this.graphAddon.extractSubgraph(this.contextMenuNode);
                    }
                    break;
                    
                // Management Actions - Route to GraphDiscovery module
                case 'clear-discovered':
                    this.graphDiscovery.clearDiscoveredRelationships();
                    break;
                    
                // Analysis Actions - Placeholder implementations
                case 'search':
                    this.handleSearch(nodeName);
                    break;
                    
                case 'enrich':
                    this.handleEnrich(nodeName);
                    break;
                    
                case 'extract-entities':
                    this.handleExtractEntities(nodeName);
                    break;
                    
                // Generate Actions - Placeholder implementations
                case 'discover':
                    this.handleDiscover(nodeName);
                    break;
                    
                case 'ideas':
                    this.handleGenerateIdeas(nodeName);
                    break;
                    
                // AI Actions - Integrated implementation
                case 'ask-vera':
                    this.handleAskVera(this.contextMenuNode, nodeName, nodeData);
                    break;
                
                // Tool Execution
                case 'execute-tool':
                    if (window.GraphToolExecutor) {
                        window.GraphToolExecutor.showToolSelector(this.contextMenuNode);
                    } else {
                        console.warn('GraphToolExecutor not loaded');
                        alert('Tool executor not available');
                    }
                    break;
                    
                default:
                    console.warn(`Unknown action: ${action}`);
            }
        },
        
        // ============================================================
        // PLACEHOLDER IMPLEMENTATIONS
        // ============================================================
        
        handleSearch: function(nodeName) {
            console.log('Search action for node:', nodeName);
            alert(`Search functionality will be implemented for: ${nodeName}`);
        },
        
        handleEnrich: function(nodeName) {
            console.log('Enrich (NLP) action for node:', nodeName);
            alert(`NLP Analysis will be performed on: ${nodeName}`);
        },
        
        handleExtractEntities: function(nodeName) {
            console.log('Extract entities action for node:', nodeName);
            alert(`Entity extraction will be performed on: ${nodeName}`);
        },
        
        handleDiscover: function(nodeName) {
            console.log('Discover action for node:', nodeName);
            alert(`Discovery mode for: ${nodeName}`);
        },
        
        handleGenerateIdeas: function(nodeName) {
            console.log('Generate ideas action for node:', nodeName);
            alert(`Generating idea stubs for: ${nodeName}`);
        },
        
        handleAskVera: function(nodeId, nodeName, nodeData) {
            console.log('Ask Vera action for node:', nodeId);
            
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
                
                console.log('Chat input populated with node context');
            } else {
                console.warn('Chat input not found');
                alert(`Ask Vera about: ${nodeName}\n\n${nodeContext}\n\nCopy this to the chat.`);
            }
        },
        
        /**
         * Show expand neighbors dialog with slider
         */
        showExpandDialog: function(nodeId) {
            const nodeData = this.graphAddon.nodesData[nodeId];
            const nodeName = nodeData ? nodeData.display_name : nodeId;
            
            const panel = document.getElementById('property-panel');
            const content = document.getElementById('panel-content');
            
            content.innerHTML = `
                <div style="padding: 20px;">
                    <div class="section">
                        <div class="section-title">🔎 Expand Neighbors</div>
                        <div style="color: #94a3b8; font-size: 13px; margin-bottom: 16px;">
                            Expand connections for: <strong style="color: #e2e8f0;">${this.escapeHtml(nodeName)}</strong>
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
                            window.GraphContextMenu.graphDiscovery.expandNeighbors('${nodeId}', depth);
                        " style="
                            flex: 1; padding: 12px;
                            background: #3b82f6; color: white; border: none;
                            border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 14px;
                        ">Expand</button>
                        <button onclick="window.GraphAddon.closePanel()" style="
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
         * Escape HTML
         */
        escapeHtml: function(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
    };
})();