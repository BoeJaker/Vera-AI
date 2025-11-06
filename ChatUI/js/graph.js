(() => {
    initGraph() {
        const container = document.getElementById('graph');
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
                navigationButtons: true,
                zoomView: true,
                dragView: true
            },
            edges: {
                smooth: { enabled: true, type: 'dynamic' },
                // color: { color: '#ffffff', hover: '#ffaa00' },
                font:  {color: '#ffffff', strokeWidth: 0, size: 12 },
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
        
        // Initialize GraphAddon first
        setTimeout(() => {
            console.log('Checking for GraphAddon...');
            if (window.GraphAddon) {
                console.log('GraphAddon found, initializing...');
                window.GraphAddon.init({});
                console.log('GraphAddon initialized');
                
                // Wait a bit more for GraphAddon to fully set up
                setTimeout(() => {
                    console.log('Setting up our click handler...');
                    
                    // Remove GraphAddon's click handler and add our own
                    this.networkInstance.off("click");
                    
                    this.networkInstance.on("click", (params) => {
                        console.log('=== OUR CLICK HANDLER ===');
                        console.log('Nodes clicked:', params.nodes);
                        
                        if (params.nodes.length > 0) {
                            const nodeId = params.nodes[0];
                            console.log('Opening panel for node:', nodeId);
                            
                            // Force open the panel
                            const panel = document.getElementById('property-panel');
                            panel.classList.add('active');
                            panel.style.right = '0';
                            console.log('Panel forced open, classes:', panel.className);
                            
                            // Call GraphAddon to populate content
                            if (window.GraphAddon && window.GraphAddon.showNodeDetails) {
                                window.GraphAddon.showNodeDetails(nodeId, true);
                                console.log('Content populated');
                            }
                        } else if (params.edges.length > 0) {
                            // Handle edge clicks
                            const panel = document.getElementById('property-panel');
                            panel.classList.add('active');
                            
                            if (window.GraphAddon && window.GraphAddon.showEdgeDetails) {
                                window.GraphAddon.showEdgeDetails(params.edges[0]);
                            }
                        } else {
                            // Clicking empty space - close panel
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
        }, 500);
    }

    async loadGraph() {
        if (!this.sessionId) return;
        
        try {
            const response = await fetch(`http://llm.int:8888/api/graph/session/${this.sessionId}`);
            const data = await response.json();
            
            console.log('Graph data received:', data.nodes.length, 'nodes', data.edges.length, 'edges');
            
            this.networkData.nodes = data.nodes.map(n => ({
                id: n.id,
                label: n.label,
                title: n.title,
                properties: n.properties,
                type: n.type || n.labels,
                color: n.color || '#3b82f6',
                size: n.size || 25
            }));
            
            this.networkData.edges = data.edges.map(e => ({
                id: e.id || `${e.from}-${e.to}`,
                from: e.from,
                to: e.to,
                label: e.label,
                title: e.label
            }));
            
            if (this.networkInstance) {
                this.networkInstance.setData(this.networkData);
                
                setTimeout(() => {
                    this.networkInstance.redraw();
                    this.networkInstance.fit();
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
        }
    }
})();