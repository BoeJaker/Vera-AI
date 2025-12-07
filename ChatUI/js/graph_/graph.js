/**
 * Graph initialization with integrated GraphLoader and smooth animations
 * Shows the V-unfurl animation during loading and when graph is empty
 * Animates new nodes and edges being added to the graph
 */

(() => {
    // Store loader reference
    let graphLoader = null;
    let isDataLoading = false;

    /**
     * Initialize the graph loader in the container
     * Call this early, before initGraph()
     */
    function initGraphLoader() {
        const container = document.getElementById('graph');
        if (!container) {
            console.warn('Graph container not found for loader');
            return null;
        }

        // Create loader if it doesn't exist
        if (!graphLoader && typeof GraphLoader !== 'undefined') {
            graphLoader = new GraphLoader(container, {
                nodeCount: 14,
                baseRadius: 80,
                rotationSpeed: 0.003,
                text: 'Initializing Graph',
                introDuration: 2.5,
                width: Math.min(300, container.clientWidth || 300),
                height: Math.min(300, container.clientHeight || 300)
            });
            console.log('GraphLoader initialized');
        }

        return graphLoader;
    }

    /**
     * Show the graph loader with optional message
     */
    function showGraphLoader(message = 'Loading Graph') {
        if (!graphLoader) {
            initGraphLoader();
        }
        if (graphLoader) {
            graphLoader.show(message);
        }
    }

    /**
     * Hide the graph loader (only if we have data)
     */
    function hideGraphLoader(force = false) {
        if (graphLoader) {
            // Only hide if forced OR if we're not in a loading/empty state
            if (force || !isDataLoading) {
                graphLoader.hide();
            }
        }
    }

    /**
     * Check if graph has data and show/hide loader accordingly
     */
    function updateLoaderVisibility(nodeCount = 0, edgeCount = 0) {
        if (nodeCount === 0 && edgeCount === 0) {
            showGraphLoader('No data in graph');
        } else {
            hideGraphLoader(true);
        }
    }

    /**
     * Check current graph state and show loader if empty
     */
    function checkGraphState(networkData) {
        const nodeCount = networkData?.nodes?.length || 0;
        const edgeCount = networkData?.edges?.length || 0;
        updateLoaderVisibility(nodeCount, edgeCount);
    }

    // Expose functions globally
    window.graphLoaderUtils = {
        init: initGraphLoader,
        show: showGraphLoader,
        hide: hideGraphLoader,
        updateVisibility: updateLoaderVisibility,
        checkState: checkGraphState,
        setLoading: (loading) => { isDataLoading = loading; },
        get instance() { return graphLoader; },
        get isLoading() { return isDataLoading; }
    };

    /**
     * Enhanced initGraph with loader integration
     */
    VeraChat.prototype.initGraph = function() {
        const container = document.getElementById('graph');
        
        // Initialize and show loader immediately
        initGraphLoader();
        showGraphLoader('Initializing Graph');
        
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
        
        console.log('Network created:', !!this.networkInstance);
        
        // Apply theme when network is first stabilized
        this.networkInstance.once('stabilizationIterationsDone', () => {
            console.log('Initial network stabilized, applying theme...');
            
            // Check if we have data - if not, keep loader visible
            const nodeCount = this.networkData.nodes?.length || 0;
            const edgeCount = this.networkData.edges?.length || 0;
            
            if (nodeCount === 0 && edgeCount === 0) {
                // No data yet, show "empty" state - keep loader visible
                showGraphLoader('Waiting for data');
            } else {
                // We have data, hide loader
                hideGraphLoader(true);
            }
            
            if (app.initThemeSettings) {
                app.initThemeSettings();
            }
            if (window.applyThemeToGraph) {
                window.applyThemeToGraph();
                console.log('Initial theme applied');
            }
        });
        
        // Initialize GraphAddon
        setTimeout(() => {
            console.log('Checking for GraphAddon...');
            if (window.GraphAddon) {
                console.log('GraphAddon found, initializing...');
                window.GraphAddon.init({});
                console.log('GraphAddon initialized');
                
                setTimeout(() => {
                    console.log('Setting up node panel click handler...');
                    
                    this.networkInstance.off("click");
                    
                    this.networkInstance.on("click", (params) => {
                        console.log('=== OUR CLICK HANDLER ===');
                        console.log('Nodes clicked:', params.nodes);
                        
                        if (params.nodes.length > 0) {
                            const nodeId = params.nodes[0];
                            console.log('Opening panel for node:', nodeId);
                            
                            const panel = document.getElementById('property-panel');
                            panel.classList.add('active');
                            panel.style.right = '0';
                            console.log('Panel forced open, classes:', panel.className);
                            
                            if (window.GraphAddon && window.GraphAddon.showNodeDetails) {
                                window.GraphAddon.showNodeDetails(nodeId, true);
                                console.log('Content populated');
                            }
                        } else if (params.edges.length > 0) {
                            const panel = document.getElementById('property-panel');
                            panel.classList.add('active');
                            
                            if (window.GraphAddon && window.GraphAddon.showEdgeDetails) {
                                window.GraphAddon.showEdgeDetails(params.edges[0]);
                            }
                        } else {
                            const panel = document.getElementById('property-panel');
                            panel.classList.remove('active');
                            console.log('Panel closed');
                        }
                    });
                    
                    console.log('Click handler installed');
                }, 1000);
            } else {
                console.error('GraphAddon not available! Is graph-addon.js loaded?');
            }
            // Call the standalone init function
            if (window.initGraphModules) {
                console.log('Calling initGraphModules...');
                window.initGraphModules();
            } else {
                console.warn('initGraphModules not found');
            }

        }, 500);
    }


    /**
     * Enhanced loadGraph with loader integration
     */
    VeraChat.prototype.loadGraph = async function() { 
        if (!this.sessionId) {
            // No session, show waiting state
            showGraphLoader('No session active');
            return;
        }
        
        // Mark as loading and show loader
        isDataLoading = true;
        showGraphLoader('Loading Graph');
        
        try {
            const response = await fetch(`http://llm.int:8888/api/graph/session/${this.sessionId}`);
            const data = await response.json();
            
            console.log('Graph data received:', data.nodes.length, 'nodes', data.edges.length, 'edges');
            
            // Check if we got empty data
            if (data.nodes.length === 0 && data.edges.length === 0) {
                isDataLoading = false;
                showGraphLoader('No data in graph');
                document.getElementById('nodeCount').textContent = '0';
                document.getElementById('edgeCount').textContent = '0';
                return;
            }
            
            // Update loader text while processing
            showGraphLoader('Processing nodes');
            
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
            
            // Render the graph with new data
            console.log('Updating graph with new data...');

            // Animated addition is handled in addNodesToGraph()
            // app.addNodesToGraph(data.nodes, data.edges);
            
            if (this.networkInstance) {
                showGraphLoader('Rendering graph');
                
                this.networkInstance.setData(this.networkData);
                
                setTimeout(() => {
                    this.networkInstance.redraw();
                    this.networkInstance.fit();
                    
                    // Hide loader after rendering - we have data now
                    setTimeout(() => {
                        isDataLoading = false;
                        hideGraphLoader(true);
                        
                        console.log('Applying theme to graph...');
                        if (app.initThemeSettings) {
                            app.initThemeSettings();
                        }
                        if (window.applyThemeToGraph) {
                            window.applyThemeToGraph();
                            console.log('Theme applied');
                        }
                    }, 300);
                }, 100);
            }
            
            document.getElementById('nodeCount').textContent = data.nodes.length;
            document.getElementById('edgeCount').textContent = data.edges.length;

            if (window.GraphAddon) {
                setTimeout(() => {
                    console.log('Updating GraphAddon data...');
                    window.GraphAddon.buildNodesData();
                    window.GraphAddon.initializeFilters();
                }, 500);
            }
        } catch (error) {
            console.error('Graph load error:', error);
            isDataLoading = false;
            
            // Show error state in loader
            showGraphLoader('Error loading graph');
        }
    }

    /**
     * Reload graph data - useful for refresh button
     */
    VeraChat.prototype.reloadGraph = async function() {
        showGraphLoader('Refreshing graph');
        await this.loadGraph();
    }

    /**
     * Clear graph and show loader
     */
    VeraChat.prototype.clearGraph = function() {
        if (this.networkInstance) {
            this.networkData.nodes = [];
            this.networkData.edges = [];
            this.networkInstance.setData(this.networkData);
        }
        
        document.getElementById('nodeCount').textContent = '0';
        document.getElementById('edgeCount').textContent = '0';
        
        // Show empty state
        showGraphLoader('Graph cleared');
    }

    /**
     * Add nodes to graph with smooth animations
     * Features:
     * - Staggered node appearance (100ms between nodes)
     * - Fade-in from transparent to opaque
     * - Size animation from small to full size
     * - Edge animation after nodes (fades in)
     * - Smooth camera movement to focus on new nodes
     * - Physics temporarily disabled during animation
     * - Integrates with GraphAddon for data rebuild
     */
    VeraChat.prototype.addNodesToGraph = function(nodes, edges) {
        const wasEmpty = (this.networkData.nodes?.length || 0) === 0;
        
        if (wasEmpty) {
            showGraphLoader('Adding nodes');
        }
        
        if (!this.networkInstance) {
            console.warn('Network instance not available');
            return;
        }
        
        // Get current data set references
        const nodesDataSet = this.networkInstance.body.data.nodes;
        const edgesDataSet = this.networkInstance.body.data.edges;
        
        // Temporarily disable physics for smooth entry
        this.networkInstance.setOptions({ physics: { enabled: false } });
        
        // Track new node IDs for animation
        const newNodeIds = [];
        
        // Add nodes one at a time with staggered animation
        if (nodes && nodes.length > 0) {
            nodes.forEach((node, index) => {
                const processedNode = {
                    id: node.id,
                    label: node.label,
                    title: node.title,
                    properties: node.properties,
                    type: node.type || node.labels,
                    color: node.color || '#3b82f6',
                    size: node.size || 25,
                    // Start small and transparent
                    scaling: {
                        min: 1,
                        max: 50
                    },
                    value: 1, // Will animate to proper size
                    opacity: 0.1 // Start nearly invisible
                };
                
                newNodeIds.push(node.id);
                
                // Add with a slight delay for staggered effect
                setTimeout(() => {
                    try {
                        nodesDataSet.add(processedNode);
                        
                        // Animate to full size and opacity
                        setTimeout(() => {
                            nodesDataSet.update({
                                id: node.id,
                                value: node.size || 25,
                                opacity: 1.0
                            });
                        }, 50);
                    } catch (e) {
                        // Node might already exist, update instead
                        nodesDataSet.update(processedNode);
                    }
                }, index * 100); // Stagger by 100ms
            });
        }
        
        // Add edges after nodes with animation
        if (edges && edges.length > 0) {
            setTimeout(() => {
                edges.forEach((edge, index) => {
                    const processedEdge = {
                        id: edge.id || `edge_${edge.from}_${edge.to}_${index}`,
                        from: edge.from,
                        to: edge.to,
                        label: edge.label,
                        title: edge.label,
                        // Start with low opacity
                        color: { opacity: 0.1 },
                        width: 0.5
                    };
                    
                    setTimeout(() => {
                        try {
                            edgesDataSet.add(processedEdge);
                            
                            // Animate to full opacity and width
                            setTimeout(() => {
                                edgesDataSet.update({
                                    id: processedEdge.id,
                                    color: { opacity: 1.0 },
                                    width: 2
                                });
                            }, 50);
                        } catch (e) {
                            // Edge might already exist
                            edgesDataSet.update(processedEdge);
                        }
                    }, index * 80); // Slightly faster than nodes
                });
            }, nodes.length * 100); // Start after nodes
        }
        
        // Re-enable physics after all animations, then stabilize
        const totalAnimationTime = (nodes.length * 100) + (edges.length * 80) + 500;
        setTimeout(() => {
            this.networkInstance.setOptions({ 
                physics: { 
                    enabled: true,
                    stabilization: {
                        enabled: true,
                        iterations: 100,
                        updateInterval: 25
                    }
                } 
            });
            
            // Fit the view to show new nodes
            setTimeout(() => {
                if (newNodeIds.length > 0) {
                    this.networkInstance.fit({
                        nodes: newNodeIds,
                        animation: {
                            duration: 1000,
                            easingFunction: 'easeInOutQuad'
                        }
                    });
                } else {
                    this.networkInstance.fit({
                        animation: {
                            duration: 1000,
                            easingFunction: 'easeInOutQuad'
                        }
                    });
                }
                
                // Update GraphAddon's internal node data
                if (window.GraphAddon) {
                    setTimeout(() => {
                        console.log('Rebuilding GraphAddon data after node addition...');
                        window.GraphAddon.buildNodesData();
                        window.GraphAddon.initializeFilters();
                    }, 500);
                }
                
                // Hide loader after animation completes
                setTimeout(() => {
                    if (this.networkData.nodes?.length > 0) {
                        hideGraphLoader(true);
                    }
                }, 1000);
            }, 200);
        }, totalAnimationTime);
        
        // Update the internal data arrays for tracking
        if (nodes && nodes.length > 0) {
            this.networkData.nodes = [...(this.networkData.nodes || []), ...nodes];
        }
        if (edges && edges.length > 0) {
            this.networkData.edges = [...(this.networkData.edges || []), ...edges];
        }
        
        // Update counters
        document.getElementById('nodeCount').textContent = this.networkData.nodes.length;
        document.getElementById('edgeCount').textContent = this.networkData.edges.length;
    }

})();