/**
 * Unified Graph Initialization
 * Single entry point for all graph functionality
 */

(function() {
    'use strict';
    
    // Extend VeraChat prototype
    VeraChat.prototype.initGraph = async function() {
        console.log('=== GRAPH INIT: Starting ===');
        
        const container = document.getElementById('graph');
        if (!container) {
            console.error('Graph container not found');
            return;
        }
        
        // Show loader
        if (window.graphLoaderUtils) {
            window.graphLoaderUtils.init();
            window.graphLoaderUtils.show('Initializing Graph');
        }
        
        // Create vis.js network
        const options = {
            physics: {
                enabled: true,
                barnesHut: {
                    gravitationalConstant: -9000,
                    centralGravity: 0.06,
                    springLength: 300,
                    springConstant: 0.01,
                    damping: 0.62
                },
                stabilization: {
                    enabled: true,
                    iterations: 200
                }
            },
            interaction: {
                hover: true,
                navigationButtons: false,
                zoomView: true,
                dragView: true,
                keyboard: { enabled: true }
            },
            edges: {
                smooth: { enabled: true, type: 'dynamic' },
                font: { color: '#ffffff', strokeWidth: 0, size: 12 },
                width: 2,
                arrows: { to: { enabled: true, scaleFactor: 1.0 } }
            },
            nodes: {
                color: {
                    border: '#60a5fa',
                    highlight: { border: '#60a5fa' }
                },
                font: { color: '#fff', size: 13 }
            }
        };
        
        this.networkInstance = new vis.Network(container, this.networkData, options);
        window.network = this.networkInstance;
        
        console.log('GRAPH INIT: Network created');
        
        // Initialize GraphCore which handles all modules
        try {
            await window.GraphCore.init(this.networkInstance);
            console.log('GRAPH INIT: ✓ Core modules ready');
            
            // Apply theme after stabilization
            this.networkInstance.once('stabilizationIterationsDone', () => {
                console.log('GRAPH INIT: Network stabilized');
                
                if (window.applyThemeToGraph) {
                    window.applyThemeToGraph();
                }
                
                // Hide loader if we have data
                const nodeCount = this.networkData.nodes?.length || 0;
                if (nodeCount > 0 && window.graphLoaderUtils) {
                    window.graphLoaderUtils.hide(true);
                } else if (window.graphLoaderUtils) {
                    window.graphLoaderUtils.show('Waiting for data');
                }
            });
            
        } catch (error) {
            console.error('GRAPH INIT: Failed to initialize modules:', error);
        }
        
        console.log('=== GRAPH INIT: Complete ===');
    };
    
    VeraChat.prototype.loadGraph = async function() {
        if (!this.sessionId) {
            if (window.graphLoaderUtils) {
                window.graphLoaderUtils.show('No session active');
            }
            return;
        }
        
        if (window.graphLoaderUtils) {
            window.graphLoaderUtils.setLoading(true);
            window.graphLoaderUtils.show('Loading Graph');
        }
        
        try {
            const response = await fetch(`http://llm.int:8888/api/graph/session/${this.sessionId}`);
            const data = await response.json();
            
            console.log('Graph data received:', data.nodes.length, 'nodes', data.edges.length, 'edges');
            
            if (data.nodes.length === 0 && data.edges.length === 0) {
                if (window.graphLoaderUtils) {
                    window.graphLoaderUtils.setLoading(false);
                    window.graphLoaderUtils.show('No data in graph');
                }
                document.getElementById('nodeCount').textContent = '0';
                document.getElementById('edgeCount').textContent = '0';
                return;
            }
            
            // Process nodes and edges
            this.networkData.nodes = data.nodes.map(n => ({
                id: n.id,
                label: n.label,
                title: n.title,
                properties: n.properties,
                type: n.type || n.labels,
                color: n.color || '#3b82f6',
                size: n.size || 25
            }));
            
            this.networkData.edges = data.edges.map((e, index) => ({
                id: e.id || `edge_${e.from}_${e.to}_${index}`,
                from: e.from,
                to: e.to,
                label: e.label,
                title: e.label
            }));
            
            // Update network
            if (this.networkInstance) {
                this.networkInstance.setData(this.networkData);
                
                setTimeout(() => {
                    this.networkInstance.redraw();
                    this.networkInstance.fit();
                    
                    // Hide loader after render
                    setTimeout(() => {
                        if (window.graphLoaderUtils) {
                            window.graphLoaderUtils.setLoading(false);
                            window.graphLoaderUtils.hide(true);
                        }
                        
                        if (window.applyThemeToGraph) {
                            window.applyThemeToGraph();
                        }
                    }, 300);
                }, 100);
            }
            
            // Update counters
            document.getElementById('nodeCount').textContent = data.nodes.length;
            document.getElementById('edgeCount').textContent = data.edges.length;
            
            // Rebuild module data
            if (window.GraphCore?.data) {
                setTimeout(() => {
                    window.GraphCore.data.rebuild();
                    window.GraphCore.filters?.initialize();
                }, 500);
            }
            
        } catch (error) {
            console.error('Graph load error:', error);
            if (window.graphLoaderUtils) {
                window.graphLoaderUtils.setLoading(false);
                window.graphLoaderUtils.show('Error loading graph');
            }
        }
    };
    
    VeraChat.prototype.addNodesToGraph = function(nodes, edges) {
        // Delegate to GraphCore if available
        if (window.GraphCore?.networkInstance) {
            this._animatedNodeAddition(nodes, edges);
        }
    };
    
    VeraChat.prototype._animatedNodeAddition = function(nodes, edges) {
        // Your existing animated addition code...
        // (Keep the animation logic from the original)
    };
    
    // Emit ready event when graph is fully initialized
    window.addEventListener('graphReady', (event) => {
        console.log('Graph is ready!', event.detail);
    });
    
})();