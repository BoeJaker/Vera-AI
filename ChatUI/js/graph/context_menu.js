/**
 * GraphContextMenu Module
 * Handles all context menu interactions and routing to appropriate handlers
 * Uses unified tool selector from GraphCanvasMenu
 */

(function() {
    'use strict';
    
    window.GraphContextMenu = {
        
        // Store references
        graphAddon: null,
        graphDiscovery: null,
        contextMenuNode: null,
        canvasContextMenuNode: null,

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
                    console.log('Node context menu triggered for node:', nodeId);
                    self.contextMenuNode = nodeId;
                    self.showContextMenu(params.event.clientX, params.event.clientY);
                } else {
                    console.log('Canvas context menu triggered');
                    self.showCanvasContextMenu(params.event.clientX, params.event.clientY);
                }
            });

            
            // Click anywhere to hide context menu
            document.addEventListener('click', () => {
                self.hideContextMenu();
                self.hideCanvasContextMenu();
            });

            
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
        
        showCanvasContextMenu: function(x, y) {
            this.hideContextMenu();

            const menu = document.getElementById('canvas-context-menu');
            if (menu) {
                menu.style.display = 'block';
                menu.style.left = x + 'px';
                menu.style.top = y + 'px';
            }
        },

        hideCanvasContextMenu: function() {
            const menu = document.getElementById('canvas-context-menu');
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
                    
                // Expansion Actions - Show slider dialog in GraphInfoCard
                case 'expand-neighbors':
                    if (window.GraphInfoCard) {
                        window.GraphInfoCard.showExpandDialog(this.contextMenuNode);
                    }
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
                    
                // Analysis Actions - Route to GraphInfoCard
                case 'search':
                    this.handleSearch(nodeName);
                    break;
                    
                case 'enrich':
                    this.handleEnrich(nodeName);
                    break;
                    
                case 'extract-entities':
                    this.handleExtractEntities(nodeName);
                    break;
                    
                // Generate Actions - Route to GraphInfoCard
                case 'discover':
                    this.handleDiscover(nodeName);
                    break;
                    
                case 'ideas':
                    this.handleGenerateIdeas(nodeName);
                    break;
                    
                // AI Actions
                case 'ask-vera':
                    this.handleAskVera(this.contextMenuNode, nodeName, nodeData);
                    break;

                // Tool Execution - USE UNIFIED TOOL SELECTOR
                case 'execute-tool':
                    // Route to unified tool selector in GraphCanvasMenu OR GraphToolExecutor
                    if (window.GraphToolExecutor && window.GraphToolExecutor.showToolSelector) {
                        // Prefer GraphToolExecutor for full plugin support
                        window.GraphToolExecutor.showToolSelector(this.contextMenuNode);
                    } else if (window.GraphCanvasMenu && window.GraphCanvasMenu.showToolSelector) {
                        // Fallback to GraphCanvasMenu's unified tool selector
                        window.GraphCanvasMenu.showToolSelector(this.contextMenuNode);
                    } else {
                        console.error('No tool selector available');
                        alert('Tool executor not available. Please reload the page.');
                    }
                    break;
                    
                default:
                    console.warn(`Unknown action: ${action}`);
            }
        },

        // ============================================================
        // PLACEHOLDER IMPLEMENTATIONS - USE GRAPHINFOCARD
        // ============================================================
        
        handleSearch: function(nodeName) {
            console.log('Search action for node:', nodeName);
            if (window.GraphInfoCard) {
                window.GraphInfoCard.showInlineContent(
                    '🔍 Search',
                    `<div style="padding: 20px; text-align: center; color: #94a3b8;">
                        Search functionality for: <strong style="color: #e2e8f0;">${this.escapeHtml(nodeName)}</strong>
                        <br><br>
                        Coming soon...
                    </div>`
                );
            } else {
                alert(`Search functionality will be implemented for: ${nodeName}`);
            }
        },
        
        handleEnrich: function(nodeName) {
            console.log('Enrich (NLP) action for node:', nodeName);
            if (window.GraphInfoCard) {
                window.GraphInfoCard.showInlineContent(
                    '🧠 NLP Analysis',
                    `<div style="padding: 20px; text-align: center; color: #94a3b8;">
                        NLP Analysis for: <strong style="color: #e2e8f0;">${this.escapeHtml(nodeName)}</strong>
                        <br><br>
                        Coming soon...
                    </div>`
                );
            } else {
                alert(`NLP Analysis will be performed on: ${nodeName}`);
            }
        },
        
        handleExtractEntities: function(nodeName) {
            console.log('Extract entities action for node:', nodeName);
            if (window.GraphInfoCard) {
                window.GraphInfoCard.showInlineContent(
                    '🏷️ Extract Entities',
                    `<div style="padding: 20px; text-align: center; color: #94a3b8;">
                        Entity extraction for: <strong style="color: #e2e8f0;">${this.escapeHtml(nodeName)}</strong>
                        <br><br>
                        Coming soon...
                    </div>`
                );
            } else {
                alert(`Entity extraction will be performed on: ${nodeName}`);
            }
        },
        
        handleDiscover: function(nodeName) {
            console.log('Discover action for node:', nodeName);
            if (window.GraphInfoCard) {
                window.GraphInfoCard.showInlineContent(
                    '🔭 Discovery Mode',
                    `<div style="padding: 20px; text-align: center; color: #94a3b8;">
                        Discovery mode for: <strong style="color: #e2e8f0;">${this.escapeHtml(nodeName)}</strong>
                        <br><br>
                        Coming soon...
                    </div>`
                );
            } else {
                alert(`Discovery mode for: ${nodeName}`);
            }
        },
        
        handleGenerateIdeas: function(nodeName) {
            console.log('Generate ideas action for node:', nodeName);
            if (window.GraphInfoCard) {
                window.GraphInfoCard.showInlineContent(
                    '💡 Generate Ideas',
                    `<div style="padding: 20px; text-align: center; color: #94a3b8;">
                        Generating idea stubs for: <strong style="color: #e2e8f0;">${this.escapeHtml(nodeName)}</strong>
                        <br><br>
                        Coming soon...
                    </div>`
                );
            } else {
                alert(`Generating idea stubs for: ${nodeName}`);
            }
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
            
            const chatInput = document.getElementById('messageInput');
            if (chatInput) {
                chatInput.value = question;
                chatInput.focus();
                
                const chatSection = document.getElementById('chatMessages');
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
         * Escape HTML
         */
        escapeHtml: function(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
    };
})();