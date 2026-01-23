/**
 * Graph initialization - HIGH PERFORMANCE VERSION
 * Optimized for large graphs (1000+ nodes, 5000+ edges)
 * 
 * Key optimizations:
 * - Batch node/edge additions (no animation delays)
 * - Smart physics (disable for large graphs)
 * - Automatic clustering for huge graphs
 * - Efficient data structures
 * - Deferred rendering
 */

(() => {
    let graphLoader = null;
    let isDataLoading = false;

    // Performance thresholds
    const PERF_THRESHOLDS = {
        LARGE_GRAPH: 500,        // Nodes - disable animations
        HUGE_GRAPH: 1000,        // Nodes - force clustering
        MASSIVE_GRAPH: 5000,     // Nodes - aggressive optimizations
        PHYSICS_DISABLE: 2000    // Nodes - disable physics entirely
    };

    function initGraphLoader() {
        const container = document.getElementById('graph');
        if (!container) {
            console.warn('Graph container not found for loader');
            return null;
        }

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
        }

        return graphLoader;
    }

    function showGraphLoader(message = 'Loading Graph') {
        if (!graphLoader) initGraphLoader();
        if (graphLoader) graphLoader.show(message);
    }

    function hideGraphLoader(force = false) {
        if (graphLoader && (force || !isDataLoading)) {
            graphLoader.hide();
        }
    }

    function updateLoaderVisibility(nodeCount = 0, edgeCount = 0) {
        if (nodeCount === 0 && edgeCount === 0) {
            showGraphLoader('No data in graph');
        } else {
            hideGraphLoader(true);
        }
    }

    function checkGraphState(networkData) {
        const nodeCount = networkData?.nodes?.length || 0;
        const edgeCount = networkData?.edges?.length || 0;
        updateLoaderVisibility(nodeCount, edgeCount);
    }

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
     * Get optimal physics settings based on graph size
     */
    function getPhysicsConfig(nodeCount) {
        if (nodeCount > PERF_THRESHOLDS.PHYSICS_DISABLE) {
            // Massive graph - no physics
            return { enabled: false };
        } else if (nodeCount > PERF_THRESHOLDS.HUGE_GRAPH) {
            // Huge graph - minimal physics
            return {
                enabled: true,
                solver: 'forceAtlas2Based',
                forceAtlas2Based: {
                    gravitationalConstant: -50,
                    centralGravity: 0.01,
                    springLength: 200,
                    springConstant: 0.05,
                    damping: 0.4,
                    avoidOverlap: 0
                },
                stabilization: {
                    enabled: true,
                    iterations: 100,
                    updateInterval: 50,
                    fit: false
                }
            };
        } else if (nodeCount > PERF_THRESHOLDS.LARGE_GRAPH) {
            // Large graph - moderate physics
            return {
                enabled: true,
                barnesHut: {
                    gravitationalConstant: -5000,
                    centralGravity: 0.05,
                    springLength: 250,
                    springConstant: 0.02,
                    damping: 0.5,
                    avoidOverlap: 0.1
                },
                stabilization: {
                    enabled: true,
                    iterations: 150,
                    updateInterval: 25
                }
            };
        } else {
            // Small/medium graph - full physics
            return {
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
            };
        }
    }

    /**
     * Enhanced initGraph - OPTIMIZED for large graphs
     */
    VeraChat.prototype.initGraph = function() {
        const container = document.getElementById('graph');
        
        initGraphLoader();
        showGraphLoader('Initializing Graph');
        
        const nodeCount = this.networkData.nodes?.length || 0;
        const physicsConfig = getPhysicsConfig(nodeCount);
        
        const options = {
            physics: physicsConfig,
            interaction: {
                hover: true,
                navigationButtons: false,
                zoomView: true,
                dragView: true,
                keyboard: { enabled: true },
                tooltipDelay: 300,
                hideEdgesOnDrag: nodeCount > PERF_THRESHOLDS.LARGE_GRAPH,
                hideEdgesOnZoom: nodeCount > PERF_THRESHOLDS.HUGE_GRAPH
            },
            edges: {
                smooth: {
                    enabled: nodeCount < PERF_THRESHOLDS.LARGE_GRAPH,
                    type: 'dynamic'
                },
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
            },
            // Performance boost for large graphs
            configure: {
                enabled: false
            }
        };
        
        this.networkInstance = new vis.Network(container, this.networkData, options);
        window.network = this.networkInstance;
        
        console.log(`Network created with ${nodeCount} nodes - Physics: ${physicsConfig.enabled ? 'enabled' : 'disabled'}`);
        
        // Keyboard interaction
        const graph = document.getElementById('graph');
        graph.addEventListener('mouseenter', () => {
            this.networkInstance.setOptions({
                interaction: { keyboard: { enabled: true } }
            });
        });

        graph.addEventListener('mouseleave', () => {
            this.networkInstance.setOptions({
                interaction: { keyboard: { enabled: false } }
            });
        });

        // Apply theme when network is first stabilized
        this.networkInstance.once('stabilizationIterationsDone', () => {
            console.log('Initial network stabilized, applying theme...');
            
            const nodeCount = this.networkData.nodes?.length || 0;
            const edgeCount = this.networkData.edges?.length || 0;
            
            if (nodeCount === 0 && edgeCount === 0) {
                showGraphLoader('Waiting for data');
            } else {
                hideGraphLoader(true);
            }
            
            if (app.initThemeSettings) {
                app.initThemeSettings();
            }
            if (window.applyThemeToGraph) {
                window.applyThemeToGraph();
            }
            // Apply initial styles
            app.GraphStyleControl.applyAllStyles();
        });

        // Initialize GraphStyleControl with session ID
        // if (window.GraphStyleControl && window.GraphAddon) {
        //     console.log('Initializing GraphStyleControl with session:', this.sessionId);
        //     window.GraphStyleControl.init(window.GraphAddon, this.sessionId);
            
        //     // Optional: Enable session view by default
        //     window.GraphStyleControl.toggleSessionView(true);
        //     window.GraphStyleControl.setSessionViewMode('linked');
        // }
        // // Auto-cluster huge graphs
        // if (nodeCount > PERF_THRESHOLDS.HUGE_GRAPH) {
        //     console.log('Large graph detected, applying automatic clustering...');
        //     setTimeout(() => {
        //         this.autoClusterLargeGraph();
        //     }, 1000);
        // }
        
        // Initialize GraphAddon immediately
        if (window.GraphAddon) {
            window.GraphAddon.init({});
            
            this.networkInstance.off("click");
            
        //     this.networkInstance.on("click", (params) => {
        //         if (params.nodes.length > 0) {
        //             const nodeId = params.nodes[0];
        //             const panel = document.getElementById('property-panel');
        //             panel.classList.add('active');
        //             panel.style.right = '0';
                    
        //             if (window.GraphAddon && window.GraphAddon.showNodeDetails) {
        //                 window.GraphAddon.showNodeDetails(nodeId, true);
        //             }
        //         } else if (params.edges.length > 0) {
        //             const panel = document.getElementById('property-panel');
        //             panel.classList.add('active');
                    
        //             if (window.GraphAddon && window.GraphAddon.showEdgeDetails) {
        //                 window.GraphAddon.showEdgeDetails(params.edges[0]);
        //             }
        //         } else {
        //             const panel = document.getElementById('property-panel');
        //             panel.classList.remove('active');
        //         }
        //     });
        }
        
        window.addEventListener('graphAddonReady', () => {
            if (window.initGraphModules) {
                window.initGraphModules();
            }
        }, { once: true });
    }

    /**
     * Auto-cluster large graphs by hub size
     */
    VeraChat.prototype.autoClusterLargeGraph = function() {
        if (!this.networkInstance) return;
        
        try {
            const nodeCount = this.networkData.nodes?.length || 0;
            
            if (nodeCount > PERF_THRESHOLDS.MASSIVE_GRAPH) {
                // Aggressive clustering for massive graphs
                this.networkInstance.clusterByHubsize(3);
                console.log('Applied aggressive clustering (threshold: 3)');
            } else if (nodeCount > PERF_THRESHOLDS.HUGE_GRAPH) {
                // Moderate clustering for huge graphs
                this.networkInstance.clusterByHubsize(8);
                console.log('Applied moderate clustering (threshold: 8)');
            }
        } catch (e) {
            console.error('Auto-clustering error:', e);
        }
    }

    /**
     * Enhanced loadGraph with performance optimizations
     */
    VeraChat.prototype.loadGraph = async function() { 
        if (!this.sessionId) {
            showGraphLoader('No session active');
            return;
        }
        
        isDataLoading = true;
        showGraphLoader('Loading Graph');
        
        try {
            const response = await fetch(`http://llm.int:8888/api/graph/session/${this.sessionId}`);
            const data = await response.json();
            
            const nodeCount = data.nodes.length;
            const edgeCount = data.edges.length;
            
            console.log(`Graph data received: ${nodeCount} nodes, ${edgeCount} edges`);
            
            if (nodeCount === 0 && edgeCount === 0) {
                isDataLoading = false;
                showGraphLoader('No data in graph');
                document.getElementById('nodeCount').textContent = '0';
                document.getElementById('edgeCount').textContent = '0';
                return;
            }
            
            // Show performance warning for huge graphs
            if (nodeCount > PERF_THRESHOLDS.HUGE_GRAPH) {
                showGraphLoader(`Loading large graph (${nodeCount} nodes)...`);
            }
            
            // Batch process nodes and edges (much faster than individual mapping)
            const processedNodes = new Array(nodeCount);
            const processedEdges = new Array(edgeCount);
            
            // Parallel processing using chunks
            const chunkSize = 1000;
            for (let i = 0; i < nodeCount; i += chunkSize) {
                const end = Math.min(i + chunkSize, nodeCount);
                for (let j = i; j < end; j++) {
                    const n = data.nodes[j];
                    processedNodes[j] = {
                        id: n.id,
                        label: n.label,
                        title: n.title,
                        properties: n.properties,
                        type: n.type || n.labels,
                        color: n.color || '#3b82f6',
                        size: n.size || 25
                    };
                }
                // Yield to UI every chunk
                if (end < nodeCount) {
                    await new Promise(resolve => setTimeout(resolve, 0));
                }
            }
            
            for (let i = 0; i < edgeCount; i += chunkSize) {
                const end = Math.min(i + chunkSize, edgeCount);
                for (let j = i; j < end; j++) {
                    const e = data.edges[j];
                    processedEdges[j] = {
                        id: e.id || `edge_${e.from}_${e.to}_${j}`,
                        from: e.from,
                        to: e.to,
                        label: e.label,
                        title: e.label
                    };
                }
                if (end < edgeCount) {
                    await new Promise(resolve => setTimeout(resolve, 0));
                }
            }
            
            this.networkData.nodes = processedNodes;
            this.networkData.edges = processedEdges;
            
            if (this.networkInstance) {
                showGraphLoader('Rendering graph');
                
                // Disable physics temporarily for faster rendering
                const hadPhysics = this.networkInstance.physics.options.enabled;
                if (hadPhysics && nodeCount > PERF_THRESHOLDS.LARGE_GRAPH) {
                    this.networkInstance.setOptions({ physics: { enabled: false } });
                }
                
                this.networkInstance.setData(this.networkData);
                
                // Re-enable physics after render
                requestAnimationFrame(() => {
                    if (hadPhysics && nodeCount > PERF_THRESHOLDS.LARGE_GRAPH) {
                        this.networkInstance.setOptions({
                            physics: getPhysicsConfig(nodeCount)
                        });
                    }
                    
                    this.networkInstance.fit();
                    
                    requestAnimationFrame(() => {
                        isDataLoading = false;
                        hideGraphLoader(true);
                        
                        if (app.initThemeSettings) {
                            app.initThemeSettings();
                        }
                        if (window.applyThemeToGraph) {
                            window.applyThemeToGraph();
                        }
                        // Apply initial styles
                        app.GraphStyleControl.applyAllStyles();
                    });
                });
            }
            
            document.getElementById('nodeCount').textContent = nodeCount;
            document.getElementById('edgeCount').textContent = edgeCount;

            // Update GraphAddon data (deferred)
            if (window.GraphAddon && window.GraphAddon.networkReady) {
                // Defer to avoid blocking
                setTimeout(() => {
                    window.GraphAddon.buildNodesData();
                    window.GraphAddon.initializeFilters();
                }, 100);
            }
        } catch (error) {
            console.error('Graph load error:', error);
            isDataLoading = false;
            showGraphLoader('Error loading graph');
        }
    }

    VeraChat.prototype.reloadGraph = async function() {
        showGraphLoader('Refreshing graph');
        await this.loadGraph();
    }

    VeraChat.prototype.clearGraph = function() {
        if (this.networkInstance) {
            this.networkData.nodes = [];
            this.networkData.edges = [];
            this.networkInstance.setData(this.networkData);
        }
        
        document.getElementById('nodeCount').textContent = '0';
        document.getElementById('edgeCount').textContent = '0';
        
        showGraphLoader('Graph cleared');
    }

    /**
     * Add nodes to graph - OPTIMIZED for performance
     * NO animation delays - batch operations instead
     */
    VeraChat.prototype.addNodesToGraph = function(nodes, edges) {
        if (!nodes || nodes.length === 0) return;
        
        const wasEmpty = (this.networkData.nodes?.length || 0) === 0;
        const newNodeCount = nodes.length;
        const shouldAnimate = newNodeCount < 200; // Animate for reasonable sizes
        
        if (wasEmpty) {
            if (window.graphLoaderUtils) {
                window.graphLoaderUtils.show('Adding nodes');
            }
        }
        
        if (!this.networkInstance) {
            console.warn('Network instance not available');
            return;
        }
        
        const nodesDataSet = this.networkInstance.body.data.nodes;
        const edgesDataSet = this.networkInstance.body.data.edges;
        
        // Build parent-child relationships from edges
        const parentMap = new Map(); // nodeId -> [parent node IDs]
        const newNodeIds = new Set(nodes.map(n => n.id));
        
        if (edges && edges.length > 0) {
            edges.forEach(edge => {
                const isNewNodeTo = newNodeIds.has(edge.to);
                const isNewNodeFrom = newNodeIds.has(edge.from);
                
                // If edge connects new node to existing node
                if (isNewNodeTo && !isNewNodeFrom) {
                    // edge.from is parent of edge.to
                    if (!parentMap.has(edge.to)) {
                        parentMap.set(edge.to, []);
                    }
                    parentMap.get(edge.to).push(edge.from);
                } else if (isNewNodeFrom && !isNewNodeTo) {
                    // edge.to is parent of edge.from
                    if (!parentMap.has(edge.from)) {
                        parentMap.set(edge.from, []);
                    }
                    parentMap.get(edge.from).push(edge.to);
                }
            });
        }
        
        console.log(`Adding ${nodes.length} nodes (${parentMap.size} with parents)`);
        
        // Get existing node positions for parent positioning
        const existingPositions = {};
        if (shouldAnimate) {
            try {
                this.networkInstance.body.data.nodes.forEach(node => {
                    const pos = this.networkInstance.getPositions([node.id])[node.id];
                    if (pos) {
                        existingPositions[node.id] = pos;
                    }
                });
            } catch (e) {
                console.warn('Could not get existing positions:', e);
            }
        }
        
        // Disable physics temporarily for controlled animation
        const hadPhysics = this.networkInstance.physics.options.enabled;
        if (hadPhysics) {
            this.networkInstance.setOptions({ physics: { enabled: false } });
        }
        
        // Process nodes with initial positioning near parents
        const processedNodes = nodes.map(node => {
            let initialX, initialY;
            
            if (shouldAnimate && parentMap.has(node.id)) {
                // Position near parent node(s)
                const parents = parentMap.get(node.id);
                const parentPositions = parents
                    .map(parentId => existingPositions[parentId])
                    .filter(pos => pos !== undefined);
                
                if (parentPositions.length > 0) {
                    // Average position of all parents
                    const avgX = parentPositions.reduce((sum, pos) => sum + pos.x, 0) / parentPositions.length;
                    const avgY = parentPositions.reduce((sum, pos) => sum + pos.y, 0) / parentPositions.length;
                    
                    // Add small random offset so nodes don't stack perfectly
                    const offset = 40;
                    initialX = avgX + (Math.random() - 0.5) * offset;
                    initialY = avgY + (Math.random() - 0.5) * offset;
                }
            }
            
            const processedNode = {
                id: node.id,
                label: node.label,
                title: node.title,
                properties: node.properties,
                type: node.type || node.labels,
                color: node.color || '#3b82f6',
                size: node.size || 25,
                scaling: {
                    min: 1,
                    max: 50
                }
            };
            
            // Set initial position if we have one (nodes spawn near parents)
            if (initialX !== undefined && initialY !== undefined) {
                processedNode.x = initialX;
                processedNode.y = initialY;
                processedNode.fixed = { x: false, y: false }; // Allow physics to move them
            }
            
            // Start with small size and low opacity for animation
            if (shouldAnimate) {
                processedNode.value = 1; // Start tiny
                processedNode.opacity = 0.1; // Start transparent
            } else {
                processedNode.value = node.size || 25;
                processedNode.opacity = 1.0;
            }
            
            return processedNode;
        });
        
        // BATCH ADD - All nodes at once (fast!)
        try {
            nodesDataSet.add(processedNodes);
            console.log(`✓ Batch added ${processedNodes.length} nodes`);
        } catch (e) {
            console.warn('Some nodes exist, updating:', e);
            nodesDataSet.update(processedNodes);
        }
        
        // Animate nodes growing to full size with smooth easing
        if (shouldAnimate) {
            const animationDuration = 800; // ms
            const startTime = performance.now();
            
            const animate = (currentTime) => {
                const elapsed = currentTime - startTime;
                const progress = Math.min(elapsed / animationDuration, 1);
                
                // Ease-out cubic for smooth deceleration
                const easeProgress = 1 - Math.pow(1 - progress, 3);
                
                // Update all nodes in batch (efficient!)
                const updates = processedNodes.map(node => {
                    const targetSize = nodes.find(n => n.id === node.id)?.size || 25;
                    
                    return {
                        id: node.id,
                        value: 1 + (targetSize - 1) * easeProgress,
                        opacity: 0.1 + 0.9 * easeProgress
                    };
                });
                
                nodesDataSet.update(updates);
                
                if (progress < 1) {
                    requestAnimationFrame(animate);
                } else {
                    // Animation complete - finalize node properties
                    const finalUpdates = processedNodes.map(node => {
                        const targetSize = nodes.find(n => n.id === node.id)?.size || 25;
                        return {
                            id: node.id,
                            value: targetSize,
                            opacity: 1.0
                        };
                    });
                    nodesDataSet.update(finalUpdates);
                    console.log('✓ Node animation complete');
                    
                    // Re-enable physics after animation for natural spreading
                    if (hadPhysics) {
                        setTimeout(() => {
                            const totalNodes = this.networkData.nodes.length + nodes.length;
                            
                            // Use adaptive physics if available
                            let physicsConfig;
                            if (typeof getPhysicsConfig === 'function') {
                                physicsConfig = getPhysicsConfig(totalNodes);
                            } else {
                                physicsConfig = { enabled: true };
                            }
                            
                            this.networkInstance.setOptions({ physics: physicsConfig });
                            
                            // Smoothly fit view after physics settles
                            setTimeout(() => {
                                const newNodeIdsList = nodes.map(n => n.id);
                                this.networkInstance.fit({
                                    nodes: newNodeIdsList,
                                    animation: {
                                        duration: 1000,
                                        easingFunction: 'easeInOutQuad'
                                    }
                                });
                            }, 500);
                        }, 100);
                    }
                    
                    // Update GraphAddon data after animation
                    if (window.GraphAddon && window.GraphAddon.networkReady) {
                        setTimeout(() => {
                            window.GraphAddon.buildNodesData();
                            window.GraphAddon.initializeFilters();
                        }, 100);
                    }
                }
            };
            
            requestAnimationFrame(animate);
        } else {
            // No animation - just add everything immediately
            if (hadPhysics) {
                const totalNodes = this.networkData.nodes.length + nodes.length;
                let physicsConfig;
                if (typeof getPhysicsConfig === 'function') {
                    physicsConfig = getPhysicsConfig(totalNodes);
                } else {
                    physicsConfig = { enabled: true };
                }
                this.networkInstance.setOptions({ physics: physicsConfig });
            }
        }
        
        // Add edges with fade-in animation
        if (edges && edges.length > 0) {
            const processedEdges = edges.map((edge, index) => ({
                id: edge.id || `edge_${edge.from}_${edge.to}_${index}`,
                from: edge.from,
                to: edge.to,
                label: edge.label,
                title: edge.label,
                color: shouldAnimate ? { opacity: 0.0 } : undefined,
                width: shouldAnimate ? 0.1 : 2
            }));
            
            try {
                edgesDataSet.add(processedEdges);
                console.log(`✓ Batch added ${processedEdges.length} edges`);
            } catch (e) {
                console.warn('Some edges exist, updating:', e);
                edgesDataSet.update(processedEdges);
            }
            
            // Fade in edges after node animation starts
            if (shouldAnimate) {
                setTimeout(() => {
                    const edgeAnimationDuration = 600;
                    const startTime = performance.now();
                    
                    const animateEdges = (currentTime) => {
                        const elapsed = currentTime - startTime;
                        const progress = Math.min(elapsed / edgeAnimationDuration, 1);
                        const easeProgress = 1 - Math.pow(1 - progress, 2);
                        
                        const edgeUpdates = processedEdges.map(edge => ({
                            id: edge.id,
                            color: { opacity: easeProgress },
                            width: 0.1 + 1.9 * easeProgress
                        }));
                        
                        edgesDataSet.update(edgeUpdates);
                        
                        if (progress < 1) {
                            requestAnimationFrame(animateEdges);
                        } else {
                            // Finalize edges
                            const finalEdgeUpdates = processedEdges.map(edge => ({
                                id: edge.id,
                                color: { opacity: 1.0 },
                                width: 2
                            }));
                            edgesDataSet.update(finalEdgeUpdates);
                            console.log('✓ Edge animation complete');
                        }
                    };
                    
                    requestAnimationFrame(animateEdges);
                }, 200); // Start edge animation 200ms after nodes
            }
        }
        
        // Update internal arrays
        if (nodes && nodes.length > 0) {
            this.networkData.nodes = [...(this.networkData.nodes || []), ...nodes];
        }
        if (edges && edges.length > 0) {
            this.networkData.edges = [...(this.networkData.edges || []), ...edges];
        }
        
        // Update counters
        document.getElementById('nodeCount').textContent = this.networkData.nodes.length;
        document.getElementById('edgeCount').textContent = this.networkData.edges.length;
        
        // Hide loader when done
        if (window.graphLoaderUtils) {
            setTimeout(() => {
                if (this.networkData.nodes?.length > 0) {
                    window.graphLoaderUtils.hide(true);
                }
            }, shouldAnimate ? 1500 : 500);
        }
    };

    /**
     * Optional: Advanced version with staggered spawning (wave effect)
     * Nodes appear in waves based on their distance from parents
     */
    VeraChat.prototype.addNodesToGraphWithWaves = function(nodes, edges) {
        if (!nodes || nodes.length === 0) return;
        
        const newNodeCount = nodes.length;
        const shouldAnimate = newNodeCount < 200;
        
        if (!this.networkInstance) {
            console.warn('Network instance not available');
            return;
        }
        
        // Build dependency graph to determine spawn order
        const parentMap = new Map();
        const newNodeIds = new Set(nodes.map(n => n.id));
        
        if (edges && edges.length > 0) {
            edges.forEach(edge => {
                const isNewNodeTo = newNodeIds.has(edge.to);
                const isNewNodeFrom = newNodeIds.has(edge.from);
                
                if (isNewNodeTo && !isNewNodeFrom) {
                    if (!parentMap.has(edge.to)) {
                        parentMap.set(edge.to, []);
                    }
                    parentMap.get(edge.to).push(edge.from);
                } else if (isNewNodeFrom && !isNewNodeTo) {
                    if (!parentMap.has(edge.from)) {
                        parentMap.set(edge.from, []);
                    }
                    parentMap.get(edge.from).push(edge.to);
                }
            });
        }
        
        // Calculate spawn waves (nodes with parents spawn in waves)
        const waves = [];
        const processed = new Set();
        
        // Wave 0: Nodes with no parents (or orphans)
        const wave0 = nodes.filter(n => !parentMap.has(n.id));
        if (wave0.length > 0) {
            waves.push(wave0);
            wave0.forEach(n => processed.add(n.id));
        }
        
        // Subsequent waves: Nodes whose parents are in previous waves
        let currentWave = 1;
        while (processed.size < nodes.length && currentWave < 10) {
            const waveNodes = nodes.filter(n => {
                if (processed.has(n.id)) return false;
                
                const parents = parentMap.get(n.id) || [];
                // All parents must be processed or not exist
                return parents.length === 0 || parents.every(p => {
                    // Parent is either existing node or processed new node
                    return !newNodeIds.has(p) || processed.has(p);
                });
            });
            
            if (waveNodes.length === 0) break;
            
            waves.push(waveNodes);
            waveNodes.forEach(n => processed.add(n.id));
            currentWave++;
        }
        
        // Add any remaining nodes to final wave
        const remaining = nodes.filter(n => !processed.has(n.id));
        if (remaining.length > 0) {
            waves.push(remaining);
        }
        
        console.log(`Adding ${nodes.length} nodes in ${waves.length} waves:`, 
                    waves.map(w => w.length));
        
        // Add nodes wave by wave with delays
        const waveDelay = shouldAnimate ? 300 : 0; // 300ms between waves
        
        waves.forEach((waveNodes, waveIndex) => {
            setTimeout(() => {
                // Use the standard addNodesToGraph for each wave
                const waveEdges = edges ? edges.filter(e => 
                    waveNodes.some(n => n.id === e.from || n.id === e.to)
                ) : [];
                
                this.addNodesToGraph(waveNodes, waveEdges);
            }, waveIndex * waveDelay);
        });
        
    };
/**
 * Unified Graph Data Loader - PERFORMANCE OPTIMIZED
 * Single source of truth for loading data into the graph
 * Includes chunked processing, physics management, and theme handling
 */
(() => {
    'use strict';
    
    window.GraphDataLoader = {
        PERF_THRESHOLDS: {
            LARGE_GRAPH: 500,
            HUGE_GRAPH: 1000,
            MASSIVE_GRAPH: 5000,
            PHYSICS_DISABLE: 2000,
            ANIMATE_THRESHOLD: 200
        },
        
        /**
         * Normalize a node to standard format
         * Preserves ALL properties and ensures correct styling
         */
        normalizeNode: function(node) {
            const properties = node.properties || {};
            
            const labelText = node.label || 
                            properties.text?.substring(0, 30) || 
                            properties.name || 
                            properties.display_name ||
                            node.id;
            
            const titleText = node.title || 
                            properties.text || 
                            properties.name ||
                            properties.display_name ||
                            node.id;
            
            const nodeType = node.type || node.labels || properties.type || [];
            const nodeLabels = Array.isArray(nodeType) ? nodeType : [nodeType];
            
            let nodeColor = node.color || properties.color || '#3b82f6';
            
            if (properties.type === 'extracted_entity' || 
                nodeLabels.includes('extracted_entity')) {
                nodeColor = '#10b981';
            }
            
            const nodeSize = node.size || properties.size || 25;
            
            return {
                id: node.id,
                label: labelText,
                title: titleText,
                properties: properties,
                type: nodeLabels,
                labels: nodeLabels,
                color: nodeColor,
                size: nodeSize,
                font: {
                    color: '#ffffff',
                    size: 14
                },
                borderWidth: 2,
                borderWidthSelected: 3
            };
        },
        
        /**
         * Normalize an edge to standard format
         * CRITICAL FIX: Checks properties.rel (your custom property)
         */
        normalizeEdge: function(edge, index = 0) {
            const properties = edge.properties || {};
            
            // Priority: edge.label > edge.type > properties.rel > properties.relationship > 'RELATED_TO'
            const edgeLabel = edge.label || 
                            edge.type || 
                            properties.rel ||
                            properties.relationship ||
                            properties.label ||
                            'RELATED_TO';
            
            const edgeId = edge.id || 
                          `edge_${edge.from || edge.start}_${edge.to || edge.end}_${index}`;
            
            const fromNode = edge.from || edge.start;
            const toNode = edge.to || edge.end;
            
            return {
                id: edgeId,
                from: fromNode,
                to: toNode,
                label: edgeLabel,
                title: edgeLabel,
                properties: properties,
                font: {
                    color: '#ffffff',
                    strokeWidth: 0,
                    size: 12
                },
                width: 2,
                arrows: {
                    to: {
                        enabled: true,
                        scaleFactor: 1.0
                    }
                },
                smooth: {
                    enabled: true,
                    type: 'dynamic'
                }
            };
        },
        
        /**
         * Process nodes in chunks (for large datasets)
         * Yields to UI to prevent blocking
         */
        processNodesInChunks: async function(rawNodes, chunkSize = 1000) {
            const nodeCount = rawNodes.length;
            const processedNodes = new Array(nodeCount);
            
            for (let i = 0; i < nodeCount; i += chunkSize) {
                const end = Math.min(i + chunkSize, nodeCount);
                for (let j = i; j < end; j++) {
                    processedNodes[j] = this.normalizeNode(rawNodes[j]);
                }
                
                // Yield to UI every chunk
                if (end < nodeCount) {
                    await new Promise(resolve => setTimeout(resolve, 0));
                }
            }
            
            return processedNodes;
        },
        
        /**
         * Process edges in chunks (for large datasets)
         * Yields to UI to prevent blocking
         */
        processEdgesInChunks: async function(rawEdges, chunkSize = 1000) {
            const edgeCount = rawEdges.length;
            const processedEdges = new Array(edgeCount);
            
            for (let i = 0; i < edgeCount; i += chunkSize) {
                const end = Math.min(i + chunkSize, edgeCount);
                for (let j = i; j < end; j++) {
                    processedEdges[j] = this.normalizeEdge(rawEdges[j], j);
                }
                
                // Yield to UI every chunk
                if (end < edgeCount) {
                    await new Promise(resolve => setTimeout(resolve, 0));
                }
            }
            
            return processedEdges;
        },
        
        /**
         * Get optimal physics configuration based on graph size
         */
        getPhysicsConfig: function(nodeCount) {
            if (nodeCount > this.PERF_THRESHOLDS.PHYSICS_DISABLE) {
                return { enabled: false };
            } else if (nodeCount > this.PERF_THRESHOLDS.HUGE_GRAPH) {
                return {
                    enabled: true,
                    solver: 'forceAtlas2Based',
                    forceAtlas2Based: {
                        gravitationalConstant: -50,
                        centralGravity: 0.01,
                        springLength: 200,
                        springConstant: 0.05,
                        damping: 0.4,
                        avoidOverlap: 0
                    },
                    stabilization: {
                        enabled: true,
                        iterations: 100,
                        updateInterval: 50,
                        fit: false
                    }
                };
            } else if (nodeCount > this.PERF_THRESHOLDS.LARGE_GRAPH) {
                return {
                    enabled: true,
                    barnesHut: {
                        gravitationalConstant: -5000,
                        centralGravity: 0.05,
                        springLength: 250,
                        springConstant: 0.02,
                        damping: 0.5,
                        avoidOverlap: 0.1
                    },
                    stabilization: {
                        enabled: true,
                        iterations: 150,
                        updateInterval: 25
                    }
                };
            } else {
                return {
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
                };
            }
        },
        
        /**
         * Main loading function - PERFORMANCE OPTIMIZED
         * Handles both initial load (replace) and incremental updates
         */
        loadData: async function(rawNodes, rawEdges, options = {}) {
            if (!window.network) {
                console.error('Network not initialized');
                return null;
            }
            
            const defaults = {
                replace: false,           // Replace all data or add incrementally
                fit: true,               // Fit view after loading
                animate: null,           // Auto-detect based on size
                applyLayout: false,      // Apply layout after loading
                focusNodes: null,        // Specific nodes to focus on
                chunkSize: 1000,        // Chunk size for processing
                applyTheme: true,       // Apply theme after loading
                updateGraphAddon: true  // Update GraphAddon data
            };
            
            const opts = { ...defaults, ...options };
            const nodeCount = rawNodes.length;
            const edgeCount = rawEdges.length;
            
            console.log(`GraphDataLoader: Loading ${nodeCount} nodes, ${edgeCount} edges (replace: ${opts.replace})`);
            
            // Show loader for large graphs
            if (window.graphLoaderUtils && nodeCount > this.PERF_THRESHOLDS.LARGE_GRAPH) {
                window.graphLoaderUtils.show(`Loading ${nodeCount} nodes...`);
            }
            
            // Auto-detect animation threshold
            if (opts.animate === null) {
                opts.animate = nodeCount < this.PERF_THRESHOLDS.ANIMATE_THRESHOLD;
            }
            
            // Process nodes and edges in chunks (prevents UI blocking)
            const processedNodes = await this.processNodesInChunks(rawNodes, opts.chunkSize);
            const processedEdges = await this.processEdgesInChunks(rawEdges, opts.chunkSize);
            
            // INITIAL LOAD (REPLACE MODE) - Optimized path
            if (opts.replace) {
                return await this._loadDataReplace(processedNodes, processedEdges, opts);
            }
            
            // INCREMENTAL LOAD (ADD MODE) - Different strategy
            return await this._loadDataIncremental(processedNodes, processedEdges, opts);
        },
        
        /**
         * Replace mode - optimized for initial graph load
         * Uses setData for best performance
         */
        _loadDataReplace: async function(nodes, edges, opts) {
            const nodeCount = nodes.length;
            const edgeCount = edges.length;
            
            if (window.graphLoaderUtils) {
                window.graphLoaderUtils.show('Rendering graph');
            }
            
            // Store in networkData if available
            if (window.app && window.app.networkData) {
                window.app.networkData.nodes = nodes;
                window.app.networkData.edges = edges;
            }
            
            // Get current physics state
            const hadPhysics = network.physics.options.enabled;
            
            // Disable physics temporarily for large graphs
            if (hadPhysics && nodeCount > this.PERF_THRESHOLDS.LARGE_GRAPH) {
                network.setOptions({ physics: { enabled: false } });
            }
            
            // Use setData for best performance
            network.setData({
                nodes: nodes,
                edges: edges
            });
            
            // Re-enable physics with optimized settings
            await new Promise(resolve => {
                requestAnimationFrame(() => {
                    if (hadPhysics && nodeCount > this.PERF_THRESHOLDS.LARGE_GRAPH) {
                        network.setOptions({
                            physics: this.getPhysicsConfig(nodeCount)
                        });
                    }
                    
                    // Fit view
                    if (opts.fit) {
                        network.fit();
                    }
                    
                    requestAnimationFrame(() => {
                        // Apply theme
                        if (opts.applyTheme) {
                            if (window.app && window.app.initThemeSettings) {
                                window.app.initThemeSettings();
                            }
                            if (window.applyThemeToGraph) {
                                window.applyThemeToGraph();
                            }
                        }
                        
                        // Hide loader
                        if (window.graphLoaderUtils) {
                            window.graphLoaderUtils.hide(true);
                        }
                        
                        resolve();
                    });
                });
            });
            
            // Update counters
            this._updateCounters(nodeCount, edgeCount);
            
            // Update GraphAddon
            if (opts.updateGraphAddon) {
                this._updateGraphAddon();
            }
            
            return {
                nodesAdded: nodeCount,
                edgesAdded: edgeCount,
                totalNodes: nodeCount,
                totalEdges: edgeCount,
                mode: 'replace'
            };
        },
        
        /**
         * Incremental mode - add nodes/edges to existing graph
         * Uses animated loading for small sets, batch for large
         */
        _loadDataIncremental: async function(nodes, edges, opts) {
            const nodeCount = nodes.length;
            const edgeCount = edges.length;
            
            // Use animated loading for small datasets
            if (opts.animate && window.app && window.app.addNodesToGraph) {
                window.app.addNodesToGraph(nodes, edges);
                
                // Update counters after animation
                setTimeout(() => {
                    const totalNodes = network.body.data.nodes.length;
                    const totalEdges = network.body.data.edges.length;
                    this._updateCounters(totalNodes, totalEdges);
                }, 2000);
                
                return {
                    nodesAdded: nodeCount,
                    edgesAdded: edgeCount,
                    totalNodes: network.body.data.nodes.length + nodeCount,
                    totalEdges: network.body.data.edges.length + edgeCount,
                    mode: 'incremental-animated'
                };
            }
            
            // Batch loading for large datasets
            const existingNodeIds = new Set(network.body.data.nodes.getIds());
            const existingEdgeIds = new Set(network.body.data.edges.getIds());
            
            const newNodes = nodes.filter(n => !existingNodeIds.has(n.id));
            const newEdges = edges.filter(e => !existingEdgeIds.has(e.id));
            const updateNodes = nodes.filter(n => existingNodeIds.has(n.id));
            
            let actualNodesAdded = 0;
            let actualEdgesAdded = 0;
            
            // Add new nodes
            if (newNodes.length > 0) {
                network.body.data.nodes.add(newNodes);
                actualNodesAdded = newNodes.length;
                console.log(`Added ${newNodes.length} new nodes`);
            }
            
            // Update existing nodes
            if (updateNodes.length > 0) {
                network.body.data.nodes.update(updateNodes);
                console.log(`Updated ${updateNodes.length} existing nodes`);
            }
            
            // Add new edges
            if (newEdges.length > 0) {
                network.body.data.edges.add(newEdges);
                actualEdgesAdded = newEdges.length;
                console.log(`Added ${newEdges.length} new edges`);
            }
            
            // Apply layout if requested
            if (opts.applyLayout && window.CypherQuery) {
                setTimeout(() => {
                    window.CypherQuery.applyCurrentLayout();
                }, 200);
            }
            
            // Fit view
            if (opts.fit) {
                setTimeout(() => {
                    if (opts.focusNodes && opts.focusNodes.length > 0) {
                        network.fit({
                            nodes: opts.focusNodes,
                            animation: {
                                duration: 1000,
                                easingFunction: 'easeInOutQuad'
                            }
                        });
                    } else {
                        network.fit({
                            animation: {
                                duration: 1000,
                                easingFunction: 'easeInOutQuad'
                            }
                        });
                    }
                }, 300);
            }
            
            // Update counters
            const totalNodes = network.body.data.nodes.length;
            const totalEdges = network.body.data.edges.length;
            this._updateCounters(totalNodes, totalEdges);
            
            // Update GraphAddon
            if (opts.updateGraphAddon) {
                this._updateGraphAddon();
            }
            
            // Hide loader
            if (window.graphLoaderUtils) {
                setTimeout(() => {
                    window.graphLoaderUtils.hide(true);
                }, 500);
            }
            
            return {
                nodesAdded: actualNodesAdded,
                edgesAdded: actualEdgesAdded,
                totalNodes: totalNodes,
                totalEdges: totalEdges,
                mode: 'incremental-batch'
            };
        },
        
        /**
         * Update node/edge counters in UI
         */
        _updateCounters: function(nodeCount, edgeCount) {
            const nodeCountEl = document.getElementById('nodeCount');
            const edgeCountEl = document.getElementById('edgeCount');
            
            if (nodeCountEl) nodeCountEl.textContent = nodeCount;
            if (edgeCountEl) edgeCountEl.textContent = edgeCount;
        },
        
        /**
         * Update GraphAddon data (deferred to avoid blocking)
         */
        _updateGraphAddon: function() {
            if (window.GraphAddon && window.GraphAddon.networkReady) {
                setTimeout(() => {
                    if (window.GraphAddon.buildNodesData) {
                        window.GraphAddon.buildNodesData();
                    }
                    if (window.GraphAddon.initializeFilters) {
                        window.GraphAddon.initializeFilters();
                    }
                }, 100);
            }
        }
    };
    
    console.log('GraphDataLoader initialized (PERFORMANCE OPTIMIZED)');
})();
})();