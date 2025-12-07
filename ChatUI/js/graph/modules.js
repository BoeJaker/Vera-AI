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
                    
                // Expansion Actions - Route to GraphDiscovery module
                case 'expand-1':
                    this.graphDiscovery.expandNeighbors(this.contextMenuNode, 1);
                    break;
                    
                case 'expand-2':
                    this.graphDiscovery.expandNeighbors(this.contextMenuNode, 2);
                    break;
                    
                case 'expand-3':
                    this.graphDiscovery.expandNeighbors(this.contextMenuNode, 3);
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
                    
                // AI Actions - Placeholder implementations
                case 'ask-vera':
                    this.handleAskVera(nodeName);
                    break;
                    
                default:
                    console.warn(`Unknown action: ${action}`);
            }
        },
        
        // ============================================================
        // PLACEHOLDER IMPLEMENTATIONS
        // These can be replaced with actual implementations later
        // ============================================================
        
        handleSearch: function(nodeName) {
            console.log('Search action for node:', nodeName);
            alert(`Search functionality will be implemented for: ${nodeName}`);
        },
        
        handleEnrich: function(nodeName) {
            console.log('Enrich (NLP) action for node:', nodeName);
            alert(`NLP Analysis will be performed on: ${nodeName}\n\nThis will analyze text content and extract:\n- Entities\n- Keywords\n- Sentiment\n- Topics`);
        },
        
        handleExtractEntities: function(nodeName) {
            console.log('Extract entities action for node:', nodeName);
            alert(`Entity extraction will be performed on: ${nodeName}\n\nThis will identify:\n- People\n- Organizations\n- Locations\n- Dates\n- Other named entities`);
        },
        
        handleDiscover: function(nodeName) {
            console.log('Discover action for node:', nodeName);
            alert(`Discovery mode for: ${nodeName}\n\nThis will explore:\n- Related concepts\n- Knowledge gaps\n- Expansion opportunities`);
        },
        
        handleGenerateIdeas: function(nodeName) {
            console.log('Generate ideas action for node:', nodeName);
            alert(`Generating idea stubs for: ${nodeName}\n\nThis will create:\n- Related concepts\n- Questions to explore\n- Potential connections`);
        },
        
        handleAskVera: function(nodeName) {
            console.log('Ask Vera action for node:', nodeName);
            alert(`Ask Vera about: ${nodeName}\n\nYou can ask:\n- Questions about this node\n- Request analysis\n- Get recommendations`);
        },
        /**
 * Graph Modules Initialization
 * 
 * This script initializes all graph modules in the correct order.
 * Include this after all modules are loaded.
 * 
 * Required order:
 * 1. graph-addon.js (your existing GraphAddon)
 * 2. graph-discovery-module.js
 * 3. graph-context-menu-module.js
 * 4. graph-modules-init.js (this file)
 */
    
    // Wait for DOM and network to be ready
    initGraphModules: function() {
        console.log('Initializing graph modules...');
        
        // Check if required objects exist
        if (typeof window.GraphAddon === 'undefined') {
            console.error('GraphAddon not found! Make sure graph-addon.js is loaded.');
            return;
        }
        
        if (typeof window.GraphDiscovery === 'undefined') {
            console.error('GraphDiscovery not found! Make sure graph-discovery-module.js is loaded.');
            return;
        }
        
        if (typeof window.GraphContextMenu === 'undefined') {
            console.error('GraphContextMenu not found! Make sure graph-context-menu-module.js is loaded.');
            return;
        }
        
        // Wait for GraphAddon to have nodesData ready
        if (!window.GraphAddon.nodesData || Object.keys(window.GraphAddon.nodesData).length === 0) {
            console.log('GraphAddon not ready yet (nodesData empty), waiting...');
            setTimeout(initGraphModules, 500);
            return;
        }
        
        console.log('GraphAddon ready with', Object.keys(window.GraphAddon.nodesData).length, 'nodes');
        
        // Check if already initialized (prevent double init)
        if (window.GraphDiscovery.graphAddon) {
            console.log('Modules already initialized, skipping...');
            return;
        }
        
        console.log('Initializing GraphDiscovery...');
        // Initialize GraphDiscovery with reference to GraphAddon
        window.GraphDiscovery.init(window.GraphAddon);
        
        console.log('Initializing GraphContextMenu...');
        // // Initialize GraphContextMenu with references to both modules
        // window.GraphContextMenu.init(window.GraphAddon, window.GraphDiscovery);
        
        console.log('✓ Graph modules initialized successfully');
        console.log('  - GraphAddon: Ready');
        console.log('  - GraphDiscovery.graphAddon:', window.GraphDiscovery.graphAddon ? 'SET' : 'NULL');
        console.log('  - GraphContextMenu.graphAddon:', window.GraphContextMenu.graphAddon ? 'SET' : 'NULL');
        console.log('  - GraphContextMenu.graphDiscovery:', window.GraphContextMenu.graphDiscovery ? 'SET' : 'NULL');
    }
    };

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initGraphModules);
    } else {
        // DOM already loaded
        initGraphModules();
    }


})();
