/**
 * GraphDiscovery Module
 * Handles all graph discovery features: hidden relationships, path finding, 
 * neighbor expansion, and similar node detection
 * Integrates with the modular GraphCore system
 */

(function() {
    'use strict';
    
    window.GraphDiscovery = {
        
        // Core reference
        core: null,
        
        // State
        initialized: false,
        pathFinderSourceNode: null,
        
        /**
         * Initialize the module with reference to GraphCore
         * @param {Object} graphCore - Reference to GraphCore
         */
        async init(graphCore) {
            if (this.initialized) {
                console.warn('GraphDiscovery already initialized');
                return;
            }
            
            console.log('GraphDiscovery: Initializing...');
            
            if (!graphCore) {
                console.error('GraphDiscovery: GraphCore is required!');
                throw new Error('GraphCore is required for initialization');
            }
            
            this.core = graphCore;
            
            // Verify required modules are available
            if (!this.core.data) {
                console.warn('GraphDiscovery: GraphData module not available yet');
            }
            
            if (!this.core.networkInstance) {
                console.error('GraphDiscovery: Network instance not available');
                throw new Error('Network instance required');
            }
            
            this.initialized = true;
            console.log('GraphDiscovery: ✓ Initialized');
        },
        
        /**
         * Verify the module is ready for operations
         */
        _checkReady() {
            if (!this.initialized) {
                throw new Error('GraphDiscovery not initialized');
            }
            
            if (!this.core?.data?.nodesData) {
                throw new Error('Graph data not available');
            }
            
            return true;
        },
        
        /**
         * Add nodes and edges to the graph with proper formatting
         * @param {Array} nodes - Nodes to add
         * @param {Array} edges - Edges to add
         */
        _addNodesToGraph(nodes, edges = []) {
            if (!nodes || nodes.length === 0) {
                return { addedNodes: 0, addedEdges: 0 };
            }
            
            console.log(`GraphDiscovery: Adding ${nodes.length} nodes and ${edges.length} edges to graph`);
            
            // Process nodes into vis.js format
            const processedNodes = nodes.map(node => ({
                id: node.id,
                label: node.label || node.id,
                title: node.title || node.label || node.id,
                properties: node.properties || {},
                type: node.type || node.labels || [],
                color: node.color || '#3b82f6',
                size: node.size || 25
            }));
            
            // Process edges into vis.js format
            const processedEdges = edges.map((edge, index) => ({
                id: edge.id || `edge_${edge.from}_${edge.to}_${index}`,
                from: edge.from,
                to: edge.to,
                label: edge.label || '',
                title: edge.title || edge.label || ''
            }));
            
            // Add to network
            try {
                this.core.networkInstance.body.data.nodes.add(processedNodes);
                if (processedEdges.length > 0) {
                    this.core.networkInstance.body.data.edges.add(processedEdges);
                }
                
                console.log(`GraphDiscovery: Successfully added ${processedNodes.length} nodes and ${processedEdges.length} edges`);
                
                return { 
                    addedNodes: processedNodes.length, 
                    addedEdges: processedEdges.length 
                };
            } catch (error) {
                console.error('GraphDiscovery: Error adding nodes/edges:', error);
                return { addedNodes: 0, addedEdges: 0 };
            }
        },
        
        // ============================================================
        // FIND HIDDEN RELATIONSHIPS
        // ============================================================
        
        /**
         * Find hidden relationships - discovers indirect 2-3 hop paths between nodes
         * @param {string} nodeId - The source node ID
         */
        async findHiddenRelationships(nodeId) {
            try {
                this._checkReady();
            } catch (error) {
                console.error('GraphDiscovery:', error.message);
                alert('Graph system not ready. Please wait a moment and try again.');
                return;
            }
            
            const nodeData = this.core.getNodeData(nodeId);
            const nodeName = nodeData ? nodeData.display_name : nodeId;
            
            this._showLoadingPanel('Finding Hidden Relationships', 
                `Analyzing indirect connections for: ${this._escapeHtml(nodeName)}`);
            
            try {
                const response = await fetch('http://llm.int:8888/api/graph/cypher', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        query: `
                            MATCH path = (start)-[*2..3]-(end)
                            WHERE start.id = $nodeId 
                            AND NOT (start)--(end)
                            AND start.id < end.id
                            WITH start, end, path, length(path) as pathLength
                            ORDER BY pathLength
                            LIMIT 50
                            RETURN DISTINCT start, end, 
                                   [node IN nodes(path) | node.id] as pathNodeIds,
                                   [rel IN relationships(path) | type(rel)] as relTypes,
                                   pathLength
                        `,
                        parameters: { nodeId }
                    })
                });
                
                const result = await response.json();
                
                if (!result.success) {
                    throw new Error(result.error || 'Query failed');
                }
                
                const hiddenPaths = result.raw_results || [];
                
                if (hiddenPaths.length === 0) {
                    this._showInfoPanel('No Hidden Relationships Found', 
                        `No indirect connections found for: ${this._escapeHtml(nodeName)}`);
                    return;
                }
                
                // Filter nodes that aren't already in the graph
                const existingIds = new Set(Object.keys(this.core.data.nodesData));
                const newNodes = result.nodes.filter(n => !existingIds.has(n.id));
                
                console.log(`GraphDiscovery: Found ${result.nodes.length} total nodes, ${newNodes.length} are new`);
                
                // Add new nodes to graph
                if (newNodes.length > 0) {
                    this._addNodesToGraph(newNodes, []);
                }
                
                // Create pink dotted edges for hidden relationships
                const hiddenEdges = [];
                hiddenPaths.forEach((pathData, idx) => {
                    const endNode = pathData.end;
                    if (endNode?.id) {
                        const endId = endNode.id;
                        const pathLength = pathData.pathLength || 0;
                        const relTypes = Array.isArray(pathData.relTypes) ? pathData.relTypes : [];
                        
                        hiddenEdges.push({
                            id: `hidden-${nodeId}-${endId}-${idx}`,
                            from: nodeId,
                            to: endId,
                            label: `Hidden (${pathLength} hops)`,
                            title: relTypes.length > 0 ? `Path: ${relTypes.join(' → ')}` : 'Hidden path',
                            color: { color: '#ec4899', opacity: 0.6 },
                            dashes: [10, 5],
                            width: 2,
                            smooth: { type: 'curvedCW', roundness: 0.2 }
                        });
                    }
                });
                
                // Add hidden edges to network
                if (hiddenEdges.length > 0) {
                    this.core.networkInstance.body.data.edges.add(hiddenEdges);
                }
                
                // Update internal data
                setTimeout(async () => {
                    await this.core.data.rebuild();
                    
                    // Focus on expanded area
                    const allNodeIds = new Set([nodeId]);
                    hiddenPaths.forEach(p => {
                        if (p.end?.id) allNodeIds.add(p.end.id);
                    });
                    
                    this.core.networkInstance.fit({
                        nodes: Array.from(allNodeIds),
                        animation: { duration: 1000, easingFunction: 'easeInOutQuad' }
                    });
                }, 300);
                
                this._showSuccessPanel('Hidden Relationships Found', 
                    `Found ${hiddenPaths.length} indirect connections via intermediary nodes.<br>
                     <small>${newNodes.length} new nodes added. Pink dotted lines show relationships through ${hiddenPaths.length} paths.</small>`);
                
            } catch (error) {
                console.error('GraphDiscovery: Error finding hidden relationships:', error);
                this._showErrorPanel('Error Finding Hidden Relationships', error.message);
            }
        },
        
        // ============================================================
        // EXPAND NEIGHBORS
        // ============================================================
        
        /**
         * Expand neighbors to specified depth
         * @param {string} nodeId - The source node ID
         * @param {number} depth - Number of hops (1-10)
         */
        async expandNeighbors(nodeId, depth = 1) {
            try {
                this._checkReady();
            } catch (error) {
                console.error('GraphDiscovery:', error.message);
                alert('Graph system not ready. Please wait and try again.');
                return;
            }
            
            const nodeData = this.core.getNodeData(nodeId);
            const nodeName = nodeData ? nodeData.display_name : nodeId;
            
            this._showLoadingPanel(`Expanding Neighbors (${depth} ${depth === 1 ? 'hop' : 'hops'})`,
                `Finding neighbors for: ${this._escapeHtml(nodeName)}`);
            
            try {
                const response = await fetch('http://llm.int:8888/api/graph/cypher', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        query: `
                            MATCH path = (start)-[*1..${depth}]-(neighbor)
                            WHERE start.id = $nodeId
                            RETURN DISTINCT start, neighbor, relationships(path) as rels
                            LIMIT 200
                        `,
                        parameters: { nodeId }
                    })
                });
                
                const result = await response.json();
                
                if (!result.success) {
                    throw new Error(result.error || 'Query failed');
                }
                
                // Filter out nodes already in graph
                const existingIds = new Set(Object.keys(this.core.data.nodesData));
                const newNodes = result.nodes.filter(n => !existingIds.has(n.id));
                
                // Filter out edges that already exist
                const existingEdges = this.core.networkInstance.body.data.edges.get();
                const existingEdgeKeys = new Set(
                    existingEdges.map(e => `${e.from}-${e.to}`)
                );
                const newEdges = result.edges.filter(e => {
                    const key = `${e.from}-${e.to}`;
                    const reverseKey = `${e.to}-${e.from}`;
                    return !existingEdgeKeys.has(key) && !existingEdgeKeys.has(reverseKey);
                });
                
                console.log(`GraphDiscovery: Found ${result.nodes.length} nodes (${newNodes.length} new), ${result.edges.length} edges (${newEdges.length} new)`);
                
                if (newNodes.length === 0 && newEdges.length === 0) {
                    this._showInfoPanel('No New Neighbors',
                        `All neighbors within ${depth} ${depth === 1 ? 'hop' : 'hops'} are already visible.`);
                    return;
                }
                
                // Add to graph
                const addResult = this._addNodesToGraph(newNodes, newEdges);
                
                // Update internal data and focus
                setTimeout(async () => {
                    await this.core.data.rebuild();
                    
                    const allNodeIds = [nodeId, ...newNodes.map(n => n.id)];
                    this.core.networkInstance.fit({
                        nodes: allNodeIds,
                        animation: { duration: 1000, easingFunction: 'easeInOutQuad' }
                    });
                }, 300);
                
                this._showSuccessPanel('Neighbors Expanded',
                    `Added ${addResult.addedNodes} new nodes and ${addResult.addedEdges} new relationships within ${depth} ${depth === 1 ? 'hop' : 'hops'}.`);
                
            } catch (error) {
                console.error('GraphDiscovery: Error expanding neighbors:', error);
                this._showErrorPanel('Error Expanding Neighbors', error.message);
            }
        },
        
        // ============================================================
        // FIND PATHS
        // ============================================================
        
        /**
         * Show path finder dialog
         * @param {string} sourceNodeId - The source node ID
         */
        showPathFinder(sourceNodeId) {
            try {
                this._checkReady();
            } catch (error) {
                console.error('GraphDiscovery:', error.message);
                alert('Graph system not ready. Please wait and try again.');
                return;
            }
            
            const sourceData = this.core.getNodeData(sourceNodeId);
            const sourceName = sourceData ? sourceData.display_name : sourceNodeId;
            
            this.pathFinderSourceNode = sourceNodeId;
            
            const panel = document.getElementById('property-panel');
            const content = document.getElementById('panel-content');
            
            if (!panel || !content) {
                console.error('GraphDiscovery: Panel elements not found');
                return;
            }
            
            // Build node selection dropdown
            let nodeOptions = '';
            Object.entries(this.core.data.nodesData).forEach(([id, data]) => {
                if (id !== sourceNodeId) {
                    const displayName = this._escapeHtml(data.display_name || id);
                    nodeOptions += `<option value="${this._escapeHtml(id)}">${displayName}</option>`;
                }
            });
            
            content.innerHTML = `
                <div class="section">
                    <div class="section-title">🔍 Find Paths</div>
                    <div style="margin: 16px 0; padding: 12px; background: #0f172a; border-radius: 6px;">
                        <div style="color: #94a3b8; font-size: 12px; margin-bottom: 8px;">From:</div>
                        <div style="color: #60a5fa; font-weight: 600; margin-bottom: 16px;">${this._escapeHtml(sourceName)}</div>
                        
                        <div style="color: #94a3b8; font-size: 12px; margin-bottom: 8px;">To:</div>
                        <select id="path-target-node" style="
                            width: 100%; padding: 8px; background: #1e293b; color: #e2e8f0;
                            border: 1px solid #334155; border-radius: 4px; font-size: 13px;
                        ">
                            <option value="">Select target node...</option>
                            ${nodeOptions}
                        </select>
                        
                        <div style="margin-top: 16px; color: #94a3b8; font-size: 12px; margin-bottom: 8px;">Max Path Length:</div>
                        <select id="path-max-length" style="
                            width: 100%; padding: 8px; background: #1e293b; color: #e2e8f0;
                            border: 1px solid #334155; border-radius: 4px; font-size: 13px;
                        ">
                            <option value="3">3 hops</option>
                            <option value="4" selected>4 hops</option>
                            <option value="5">5 hops</option>
                            <option value="6">6 hops</option>
                        </select>
                        
                        <button onclick="window.GraphDiscovery.findPaths()" style="
                            width: 100%; margin-top: 16px; padding: 10px;
                            background: #3b82f6; color: white; border: none;
                            border-radius: 6px; cursor: pointer; font-weight: 600;
                        ">Find Paths</button>
                    </div>
                </div>
            `;
            
            panel.style.display = 'flex';
        },
        
        /**
         * Execute path finding
         */
        async findPaths() {
            const sourceId = this.pathFinderSourceNode;
            const targetId = document.getElementById('path-target-node')?.value;
            const maxLength = parseInt(document.getElementById('path-max-length')?.value || '4');
            
            if (!targetId) {
                alert('Please select a target node');
                return;
            }
            
            const sourceData = this.core.getNodeData(sourceId);
            const targetData = this.core.getNodeData(targetId);
            
            this._showLoadingPanel('Finding Paths',
                `Searching for paths from ${this._escapeHtml(sourceData?.display_name || sourceId)} to ${this._escapeHtml(targetData?.display_name || targetId)}`);
            
            try {
                const response = await fetch('http://llm.int:8888/api/graph/cypher', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        query: `
                            MATCH path = allShortestPaths((start)-[*1..${maxLength}]-(end))
                            WHERE start.id = $sourceId AND end.id = $targetId
                            RETURN path,
                                   length(path) as pathLength,
                                   [node IN nodes(path) | node.id] as nodeIds,
                                   [rel IN relationships(path) | type(rel)] as relTypes
                            LIMIT 20
                        `,
                        parameters: { sourceId, targetId }
                    })
                });
                
                const result = await response.json();
                
                if (!result.success) {
                    throw new Error(result.error || 'Query failed');
                }
                
                const paths = result.raw_results || [];
                
                if (paths.length === 0) {
                    this._showInfoPanel('No Paths Found',
                        `No path found between the selected nodes within ${maxLength} hops.<br>
                         <button onclick="window.GraphDiscovery.showPathFinder('${sourceId}')" style="margin-top: 12px; padding: 8px 20px; background: #3b82f6; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 600;">Try Again</button>`);
                    return;
                }
                
                // Add any new nodes from paths
                const existingIds = new Set(Object.keys(this.core.data.nodesData));
                const newNodes = result.nodes.filter(n => !existingIds.has(n.id));
                
                if (newNodes.length > 0) {
                    console.log(`GraphDiscovery: Adding ${newNodes.length} new nodes found in paths`);
                    this._addNodesToGraph(newNodes, []);
                    
                    // Rebuild data after adding nodes
                    await this.core.data.rebuild();
                }
                
                // Highlight all nodes in found paths
                const pathNodeIds = new Set();
                paths.forEach(p => {
                    const nodeIds = Array.isArray(p.nodeIds) ? p.nodeIds : [];
                    nodeIds.forEach(id => pathNodeIds.add(id));
                });
                
                // Create path visualization with colored edges
                const pathEdges = [];
                const pathColors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16'];
                
                paths.forEach((pathData, pathIdx) => {
                    const nodeIds = Array.isArray(pathData.nodeIds) ? pathData.nodeIds : [];
                    const relTypes = Array.isArray(pathData.relTypes) ? pathData.relTypes : [];
                    const pathColor = pathColors[pathIdx % pathColors.length];
                    
                    for (let i = 0; i < nodeIds.length - 1; i++) {
                        pathEdges.push({
                            id: `path-${pathIdx}-${i}`,
                            from: nodeIds[i],
                            to: nodeIds[i + 1],
                            label: `Path ${pathIdx + 1}`,
                            title: (relTypes[i] || 'CONNECTED'),
                            color: { color: pathColor, opacity: 0.8 },
                            width: 3,
                            dashes: [5, 5]
                        });
                    }
                });
                
                // Add path edges
                this.core.networkInstance.body.data.edges.add(pathEdges);
                
                // Focus on path
                setTimeout(() => {
                    this.core.networkInstance.fit({
                        nodes: Array.from(pathNodeIds),
                        animation: { duration: 1000, easingFunction: 'easeInOutQuad' }
                    });
                }, 100);
                
                // Build comprehensive path list HTML
                this._showPathsResults(paths, pathColors, sourceData, targetData, sourceId);
                
            } catch (error) {
                console.error('GraphDiscovery: Error finding paths:', error);
                this._showErrorPanel('Error Finding Paths', error.message);
            }
        },
        
        /**
         * Show paths results in panel
         */
        _showPathsResults(paths, pathColors, sourceData, targetData, sourceId) {
            let pathsHtml = '';
            
            paths.forEach((p, idx) => {
                const nodeIds = Array.isArray(p.nodeIds) ? p.nodeIds : [];
                const relTypes = Array.isArray(p.relTypes) ? p.relTypes : [];
                const pathColor = pathColors[idx % pathColors.length];
                
                // Build detailed path with node names
                let pathDetails = '<div style="margin-top: 8px;">';
                nodeIds.forEach((id, i) => {
                    const nodeData = this.core.getNodeData(id);
                    const nodeName = nodeData?.display_name || id;
                    const nodeLabels = nodeData?.labels || [];
                    const labelText = nodeLabels.length > 0 ? ` (${nodeLabels.join(', ')})` : '';
                    
                    // Node
                    pathDetails += `
                        <div style="
                            display: inline-block; padding: 6px 12px; margin: 4px 2px;
                            background: rgba(59, 130, 246, 0.2); border: 1px solid ${pathColor};
                            border-radius: 6px; color: #e2e8f0; font-size: 11px;
                        ">
                            <strong>${this._escapeHtml(nodeName)}</strong>
                            <span style="color: #94a3b8; font-size: 10px;">${this._escapeHtml(labelText)}</span>
                        </div>
                    `;
                    
                    // Relationship arrow (if not last node)
                    if (i < relTypes.length) {
                        pathDetails += `
                            <div style="display: inline-block; margin: 0 4px; color: ${pathColor};">
                                <div style="font-size: 10px; color: #64748b; text-align: center;">${this._escapeHtml(relTypes[i] || '?')}</div>
                                <div style="font-size: 16px;">→</div>
                            </div>
                        `;
                    }
                });
                pathDetails += '</div>';
                
                // Path card
                pathsHtml += `
                    <div style="
                        margin: 12px 0; padding: 12px; 
                        background: #1e293b; border-radius: 8px; 
                        border-left: 4px solid ${pathColor};
                        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
                    ">
                        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <div style="
                                    width: 12px; height: 12px; border-radius: 50%;
                                    background: ${pathColor};
                                "></div>
                                <span style="color: #60a5fa; font-weight: 600; font-size: 13px;">
                                    Path ${idx + 1}
                                </span>
                            </div>
                            <div style="
                                padding: 3px 10px; background: rgba(59, 130, 246, 0.2);
                                border-radius: 4px; color: #60a5fa; font-size: 11px; font-weight: 600;
                            ">
                                ${p.pathLength} hop${p.pathLength !== 1 ? 's' : ''}
                            </div>
                        </div>
                        ${pathDetails}
                    </div>
                `;
            });
            
            const panel = document.getElementById('property-panel');
            const content = document.getElementById('panel-content');
            
            content.innerHTML = `
                <div style="padding: 20px;">
                    <!-- Header -->
                    <div style="text-align: center; margin-bottom: 20px;">
                        <div style="font-size: 32px; margin-bottom: 8px;">🛤️</div>
                        <div style="color: #10b981; font-size: 16px; font-weight: 600; margin-bottom: 4px;">
                            Found ${paths.length} Path${paths.length !== 1 ? 's' : ''}
                        </div>
                        <div style="color: #94a3b8; font-size: 12px;">
                            From <strong style="color: #60a5fa;">${this._escapeHtml(sourceData?.display_name || sourceId)}</strong>
                            to <strong style="color: #10b981;">${this._escapeHtml(targetData?.display_name || 'unknown')}</strong>
                        </div>
                    </div>
                    
                    <!-- Path list -->
                    <div style="max-height: 500px; overflow-y: auto; padding-right: 8px;">
                        ${pathsHtml}
                    </div>
                    
                    <!-- Footer -->
                    <div style="margin-top: 16px; padding-top: 16px; border-top: 1px solid #334155;">
                        <div style="display: flex; gap: 8px;">
                            <button onclick="window.GraphDiscovery.showPathFinder('${sourceId}')" style="
                                flex: 1; padding: 10px;
                                background: #334155; color: #e2e8f0; border: 1px solid #475569;
                                border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 13px;
                            ">Find More Paths</button>
                            <button onclick="window.GraphCore.ui.closePanel()" style="
                                padding: 10px 20px;
                                background: #3b82f6; color: white; border: none;
                                border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 13px;
                            ">Close</button>
                        </div>
                    </div>
                </div>
            `;
            
            panel.style.display = 'flex';
        },
        
        // ============================================================
        // FIND SIMILAR NODES
        // ============================================================
        
        /**
         * Find similar nodes based on properties and labels
         * @param {string} nodeId - The source node ID
         */
        async findSimilarNodes(nodeId) {
            try {
                this._checkReady();
            } catch (error) {
                console.error('GraphDiscovery:', error.message);
                alert('Graph system not ready. Please wait and try again.');
                return;
            }
            
            const nodeData = this.core.getNodeData(nodeId);
            const nodeName = nodeData ? nodeData.display_name : nodeId;
            
            this._showLoadingPanel('Finding Similar Nodes',
                `Analyzing similarity for: ${this._escapeHtml(nodeName)}`);
            
            try {
                const response = await fetch('http://llm.int:8888/api/graph/cypher', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        query: `
                            MATCH (reference), (similar)
                            WHERE reference.id = $nodeId
                            AND similar.id <> $nodeId
                            AND (
                                similar.type = reference.type
                                OR size([l IN labels(similar) WHERE l IN labels(reference)]) > 0
                            )
                            WITH DISTINCT similar, reference,
                                 size([l IN labels(similar) WHERE l IN labels(reference)]) as labelOverlap,
                                 CASE WHEN similar.type = reference.type THEN 1 ELSE 0 END as typeMatch
                            WHERE labelOverlap + typeMatch > 0
                            RETURN DISTINCT similar, (labelOverlap + typeMatch) as similarity
                            ORDER BY similarity DESC
                            LIMIT 50
                        `,
                        parameters: { nodeId }
                    })
                });
                
                const result = await response.json();
                
                if (!result.success) {
                    throw new Error(result.error || 'Query failed');
                }
                
                // Get unique similar nodes
                const similarNodesMap = new Map();
                result.nodes.forEach(n => {
                    if (n.id !== nodeId) {
                        similarNodesMap.set(n.id, n);
                    }
                });
                const allSimilarNodes = Array.from(similarNodesMap.values());
                
                if (allSimilarNodes.length === 0) {
                    this._showInfoPanel('No Similar Nodes Found',
                        'No nodes with similar properties or labels found.');
                    return;
                }
                
                // Separate nodes already in graph vs new nodes
                const existingIds = new Set(Object.keys(this.core.data.nodesData));
                const newNodes = allSimilarNodes.filter(n => !existingIds.has(n.id));
                const existingNodes = allSimilarNodes.filter(n => existingIds.has(n.id));
                
                console.log(`GraphDiscovery: Found ${allSimilarNodes.length} similar nodes: ${existingNodes.length} already visible, ${newNodes.length} new`);
                
                // Add new nodes to graph
                if (newNodes.length > 0) {
                    this._addNodesToGraph(newNodes, []);
                }
                
                // Update data and create similarity edges after a short delay
                setTimeout(async () => {
                    await this.core.data.rebuild();
                    
                    // Create purple dotted edges for similarity (for all similar nodes)
                    const similarityEdges = [];
                    const edgeSet = new Set();
                    
                    allSimilarNodes.forEach(node => {
                        const edgeKey = `${nodeId}-${node.id}`;
                        if (!edgeSet.has(edgeKey)) {
                            edgeSet.add(edgeKey);
                            similarityEdges.push({
                                id: `similar-${nodeId}-${node.id}`,
                                from: nodeId,
                                to: node.id,
                                label: 'Similar',
                                title: 'Similar properties/labels',
                                color: { color: '#8b5cf6', opacity: 0.6 },
                                dashes: [8, 8],
                                width: 2
                            });
                        }
                    });
                    
                    // Add similarity edges
                    this.core.networkInstance.body.data.edges.add(similarityEdges);
                    
                    // Focus on similar nodes
                    setTimeout(() => {
                        const allNodeIds = [nodeId, ...allSimilarNodes.map(n => n.id)];
                        this.core.networkInstance.fit({
                            nodes: allNodeIds,
                            animation: { duration: 1000, easingFunction: 'easeInOutQuad' }
                        });
                    }, 100);
                }, 300);
                
                this._showSuccessPanel('Similar Nodes Found',
                    `Found ${allSimilarNodes.length} nodes with similar properties or labels.<br>
                     <small>${newNodes.length} new nodes added, ${existingNodes.length} already visible.<br>
                     Purple dotted lines show similarity connections.</small>`);
                
            } catch (error) {
                console.error('GraphDiscovery: Error finding similar nodes:', error);
                this._showErrorPanel('Error Finding Similar Nodes', error.message);
            }
        },
        
        // ============================================================
        // CLEAR DISCOVERED RELATIONSHIPS
        // ============================================================
        
        /**
         * Clear all discovered relationships (dotted/dashed edges)
         */
        clearDiscoveredRelationships() {
            try {
                this._checkReady();
            } catch (error) {
                console.error('GraphDiscovery:', error.message);
                alert('Graph system not ready.');
                return;
            }
            
            const edgesToRemove = this.core.networkInstance.body.data.edges.get().filter(edge => 
                edge.dashes || edge.id.startsWith('hidden-') || 
                edge.id.startsWith('path-') || edge.id.startsWith('similar-')
            );
            
            const count = edgesToRemove.length;
            
            this.core.networkInstance.body.data.edges.remove(edgesToRemove.map(e => e.id));
            
            console.log(`GraphDiscovery: Removed ${count} discovered relationships`);
            
            this._showInfoPanel('Cleared Discovered Relationships',
                `Removed ${count} discovered edge${count !== 1 ? 's' : ''}`);
        },
        
        // ============================================================
        // HELPER FUNCTIONS
        // ============================================================
        
        /**
         * Show loading panel
         */
        _showLoadingPanel(title, message) {
            const panel = document.getElementById('property-panel');
            const content = document.getElementById('panel-content');
            
            if (!panel || !content) return;
            
            content.innerHTML = `
                <div style="text-align: center; padding: 40px;">
                    <div style="font-size: 32px; margin-bottom: 16px;">🔄</div>
                    <div style="color: #60a5fa; font-size: 16px; font-weight: 600; margin-bottom: 8px;">${title}</div>
                    <div style="color: #94a3b8; font-size: 13px;">${message}</div>
                </div>
            `;
            panel.style.display = 'flex';
        },
        
        /**
         * Show success panel
         */
        _showSuccessPanel(title, message) {
            const panel = document.getElementById('property-panel');
            const content = document.getElementById('panel-content');
            
            if (!panel || !content) return;
            
            content.innerHTML = `
                <div style="text-align: center; padding: 30px;">
                    <div style="font-size: 32px; margin-bottom: 16px;">✓</div>
                    <div style="color: #10b981; font-size: 14px; font-weight: 600; margin-bottom: 8px;">${title}</div>
                    <div style="color: #94a3b8; font-size: 13px; line-height: 1.5;">${message}</div>
                    <button onclick="window.GraphCore.ui.closePanel()" style="margin-top: 20px; padding: 8px 20px; background: #3b82f6; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 600;">Close</button>
                </div>
            `;
            panel.style.display = 'flex';
        },
        
        /**
         * Show info panel
         */
        _showInfoPanel(title, message) {
            const panel = document.getElementById('property-panel');
            const content = document.getElementById('panel-content');
            
            if (!panel || !content) return;
            
            content.innerHTML = `
                <div style="text-align: center; padding: 30px;">
                    <div style="font-size: 32px; margin-bottom: 16px;">ℹ️</div>
                    <div style="color: #60a5fa; font-size: 14px; font-weight: 600; margin-bottom: 8px;">${title}</div>
                    <div style="color: #94a3b8; font-size: 13px; line-height: 1.5;">${message}</div>
                    <button onclick="window.GraphCore.ui.closePanel()" style="margin-top: 20px; padding: 8px 20px; background: #3b82f6; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 600;">Close</button>
                </div>
            `;
            panel.style.display = 'flex';
        },
        
        /**
         * Show error panel
         */
        _showErrorPanel(title, message) {
            const panel = document.getElementById('property-panel');
            const content = document.getElementById('panel-content');
            
            if (!panel || !content) return;
            
            content.innerHTML = `
                <div style="text-align: center; padding: 30px;">
                    <div style="font-size: 32px; margin-bottom: 16px;">⚠️</div>
                    <div style="color: #ef4444; font-size: 14px; font-weight: 600; margin-bottom: 8px;">${title}</div>
                    <div style="color: #94a3b8; font-size: 13px; margin-bottom: 20px;">${this._escapeHtml(message)}</div>
                    <button onclick="window.GraphCore.ui.closePanel()" style="padding: 8px 20px; background: #3b82f6; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 600;">Close</button>
                </div>
            `;
            panel.style.display = 'flex';
        },
        
        /**
         * Escape HTML for safe display
         */
        _escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
    };
})();