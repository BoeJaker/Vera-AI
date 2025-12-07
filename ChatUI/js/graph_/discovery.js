/**
 * GraphDiscovery Module
 * Handles all graph discovery features: hidden relationships, path finding, 
 * neighbor expansion, and similar node detection
 */

(function() {
    'use strict';
    
    window.GraphDiscovery = {
        
        // Store reference to GraphAddon for access to nodesData, etc.
        graphAddon: null,
        
        /**
         * Initialize the module with reference to GraphAddon
         */
        init: function(graphAddon) {
            console.log('GraphDiscovery.init called with:', graphAddon);
            this.graphAddon = graphAddon;
            
            if (!graphAddon) {
                console.error('GraphDiscovery.init: GraphAddon is null or undefined!');
                return;
            }
            
            if (!graphAddon.nodesData) {
                console.warn('GraphDiscovery.init: GraphAddon.nodesData is not yet available. It may initialize later.');
            } else {
                console.log('GraphDiscovery.init: GraphAddon.nodesData available with', Object.keys(graphAddon.nodesData).length, 'nodes');
            }
            
            console.log('GraphDiscovery module initialized');
        },
        
        // ============================================================
        // FIND HIDDEN RELATIONSHIPS
        // ============================================================
        
        /**
         * Find hidden relationships - discovers indirect 2-3 hop paths between nodes
         * @param {string} nodeId - The source node ID
         */
        findHiddenRelationships: async function(nodeId) {
            if (!this.graphAddon) {
                console.error('GraphDiscovery not initialized! GraphAddon reference is null.');
                alert('Graph system not ready. Please wait a moment and try again.');
                return;
            }
            
            if (!this.graphAddon.nodesData) {
                console.error('GraphAddon.nodesData is not available!');
                alert('Graph data not ready. Please wait a moment and try again.');
                return;
            }
            
            const nodeData = this.graphAddon.nodesData[nodeId];
            const nodeName = nodeData ? nodeData.display_name : nodeId;
            
            this.showLoadingPanel('Finding Hidden Relationships', 
                `Analyzing indirect connections for: ${this.escapeHtml(nodeName)}`);
            
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
                    this.showInfoPanel('No Hidden Relationships Found', 
                        `No indirect connections found for: ${this.escapeHtml(nodeName)}`);
                    return;
                }
                
                // Add discovered nodes to graph if not present
                const newNodes = result.nodes.filter(n => !this.graphAddon.nodesData[n.id]);
                
                if (newNodes.length > 0 && window.app && window.app.addNodesToGraph) {
                    window.app.addNodesToGraph(newNodes, []);
                }
                
                // Create pink dotted edges for hidden relationships
                const hiddenEdges = [];
                hiddenPaths.forEach((pathData, idx) => {
                    const endNode = pathData.end;
                    if (endNode && endNode.id) {
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
                    network.body.data.edges.add(hiddenEdges);
                }
                
                // Update internal data
                this.graphAddon.buildNodesData();
                
                // Focus on expanded area
                const allNodeIds = new Set([nodeId]);
                hiddenPaths.forEach(p => {
                    if (p.end && p.end.id) allNodeIds.add(p.end.id);
                });
                
                setTimeout(() => {
                    network.fit({
                        nodes: Array.from(allNodeIds),
                        animation: { duration: 1000, easingFunction: 'easeInOutQuad' }
                    });
                }, 100);
                
                this.showSuccessPanel('Hidden Relationships Found', 
                    `Found ${hiddenPaths.length} indirect connections via intermediary nodes.<br>
                     <small>Pink dotted lines show relationships through ${hiddenPaths.length} paths.</small>`);
                
            } catch (error) {
                console.error('Error finding hidden relationships:', error);
                this.showErrorPanel('Error Finding Hidden Relationships', error.message);
            }
        },
        
        // ============================================================
        // EXPAND NEIGHBORS
        // ============================================================
        
        /**
         * Expand neighbors to specified depth
         * @param {string} nodeId - The source node ID
         * @param {number} depth - Number of hops (1, 2, or 3)
         */
        expandNeighbors: async function(nodeId, depth = 1) {
            if (!this.graphAddon || !this.graphAddon.nodesData) {
                console.error('GraphDiscovery not properly initialized!');
                alert('Graph system not ready. Please wait and try again.');
                return;
            }
            
            const nodeData = this.graphAddon.nodesData[nodeId];
            const nodeName = nodeData ? nodeData.display_name : nodeId;
            
            this.showLoadingPanel(`Expanding Neighbors (${depth} ${depth === 1 ? 'hop' : 'hops'})`,
                `Finding neighbors for: ${this.escapeHtml(nodeName)}`);
            
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
                const existingIds = new Set(Object.keys(this.graphAddon.nodesData));
                const newNodes = result.nodes.filter(n => !existingIds.has(n.id));
                const newEdges = result.edges.filter(e => {
                    return !network.body.data.edges.get().some(existing => 
                        existing.from === e.from && existing.to === e.to
                    );
                });
                
                if (newNodes.length === 0 && newEdges.length === 0) {
                    this.showInfoPanel('No New Neighbors',
                        `All neighbors within ${depth} ${depth === 1 ? 'hop' : 'hops'} are already visible.`);
                    return;
                }
                
                // Add to graph with animation
                if (window.app && window.app.addNodesToGraph) {
                    window.app.addNodesToGraph(newNodes, newEdges);
                }
                
                // Update internal data
                this.graphAddon.buildNodesData();
                
                // Focus on expanded area
                setTimeout(() => {
                    const allNodeIds = [nodeId, ...newNodes.map(n => n.id)];
                    network.fit({
                        nodes: allNodeIds,
                        animation: { duration: 1000, easingFunction: 'easeInOutQuad' }
                    });
                }, 500);
                
                this.showSuccessPanel('Neighbors Expanded',
                    `Added ${newNodes.length} new nodes and ${newEdges.length} relationships within ${depth} ${depth === 1 ? 'hop' : 'hops'}.`);
                
            } catch (error) {
                console.error('Error expanding neighbors:', error);
                this.showErrorPanel('Error Expanding Neighbors', error.message);
            }
        },
        
        // ============================================================
        // FIND PATHS
        // ============================================================
        
        /**
         * Show path finder dialog
         * @param {string} sourceNodeId - The source node ID
         */
        showPathFinder: function(sourceNodeId) {
            const sourceData = this.graphAddon.nodesData[sourceNodeId];
            const sourceName = sourceData ? sourceData.display_name : sourceNodeId;
            
            this.pathFinderSourceNode = sourceNodeId;
            
            const panel = document.getElementById('property-panel');
            const content = document.getElementById('panel-content');
            
            // Build node selection dropdown
            let nodeOptions = '';
            Object.entries(this.graphAddon.nodesData).forEach(([id, data]) => {
                if (id !== sourceNodeId) {
                    const displayName = this.escapeHtml(data.display_name || id);
                    nodeOptions += `<option value="${this.escapeHtml(id)}">${displayName}</option>`;
                }
            });
            
            content.innerHTML = `
                <div class="section">
                    <div class="section-title">🔍 Find Paths</div>
                    <div style="margin: 16px 0; padding: 12px; background: #0f172a; border-radius: 6px;">
                        <div style="color: #94a3b8; font-size: 12px; margin-bottom: 8px;">From:</div>
                        <div style="color: #60a5fa; font-weight: 600; margin-bottom: 16px;">${this.escapeHtml(sourceName)}</div>
                        
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
        findPaths: async function() {
            const sourceId = this.pathFinderSourceNode;
            const targetId = document.getElementById('path-target-node').value;
            const maxLength = parseInt(document.getElementById('path-max-length').value);
            
            if (!targetId) {
                alert('Please select a target node');
                return;
            }
            
            const sourceData = this.graphAddon.nodesData[sourceId];
            const targetData = this.graphAddon.nodesData[targetId];
            
            this.showLoadingPanel('Finding Paths',
                `Searching for paths from ${this.escapeHtml(sourceData?.display_name || sourceId)} to ${this.escapeHtml(targetData?.display_name || targetId)}`);
            
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
                    this.showInfoPanel('No Paths Found',
                        `No path found between the selected nodes within ${maxLength} hops.<br>
                         <button onclick="window.GraphDiscovery.showPathFinder('${sourceId}')" style="margin-top: 12px; padding: 8px 20px; background: #3b82f6; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 600;">Try Again</button>`);
                    return;
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
                network.body.data.edges.add(pathEdges);
                
                // Focus on path
                setTimeout(() => {
                    network.fit({
                        nodes: Array.from(pathNodeIds),
                        animation: { duration: 1000, easingFunction: 'easeInOutQuad' }
                    });
                }, 100);
                
                // Build comprehensive path list HTML
                let pathsHtml = '';
                paths.forEach((p, idx) => {
                    const nodeIds = Array.isArray(p.nodeIds) ? p.nodeIds : [];
                    const relTypes = Array.isArray(p.relTypes) ? p.relTypes : [];
                    const pathColor = pathColors[idx % pathColors.length];
                    
                    // Build detailed path with node names
                    let pathDetails = '<div style="margin-top: 8px;">';
                    nodeIds.forEach((id, i) => {
                        const nodeName = this.graphAddon.nodesData[id]?.display_name || id;
                        const nodeLabels = this.graphAddon.nodesData[id]?.labels || [];
                        const labelText = nodeLabels.length > 0 ? ` (${nodeLabels.join(', ')})` : '';
                        
                        // Node
                        pathDetails += `
                            <div style="
                                display: inline-block; padding: 6px 12px; margin: 4px 2px;
                                background: rgba(59, 130, 246, 0.2); border: 1px solid ${pathColor};
                                border-radius: 6px; color: #e2e8f0; font-size: 11px;
                            ">
                                <strong>${this.escapeHtml(nodeName)}</strong>
                                <span style="color: #94a3b8; font-size: 10px;">${this.escapeHtml(labelText)}</span>
                            </div>
                        `;
                        
                        // Relationship arrow (if not last node)
                        if (i < relTypes.length) {
                            pathDetails += `
                                <div style="display: inline-block; margin: 0 4px; color: ${pathColor};">
                                    <div style="font-size: 10px; color: #64748b; text-align: center;">${this.escapeHtml(relTypes[i] || '?')}</div>
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
                                From <strong style="color: #60a5fa;">${this.escapeHtml(sourceData?.display_name || sourceId)}</strong>
                                to <strong style="color: #10b981;">${this.escapeHtml(targetData?.display_name || targetId)}</strong>
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
                                <button onclick="window.GraphAddon.closePanel()" style="
                                    padding: 10px 20px;
                                    background: #3b82f6; color: white; border: none;
                                    border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 13px;
                                ">Close</button>
                            </div>
                        </div>
                    </div>
                `;
                
            } catch (error) {
                console.error('Error finding paths:', error);
                this.showErrorPanel('Error Finding Paths', error.message);
            }
        },
        
        // ============================================================
        // FIND SIMILAR NODES
        // ============================================================
        
        /**
         * Find similar nodes based on properties and labels
         * @param {string} nodeId - The source node ID
         */
        findSimilarNodes: async function(nodeId) {
            const nodeData = this.graphAddon.nodesData[nodeId];
            const nodeName = nodeData ? nodeData.display_name : nodeId;
            
            this.showLoadingPanel('Finding Similar Nodes',
                `Analyzing similarity for: ${this.escapeHtml(nodeName)}`);
            
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
                    this.showInfoPanel('No Similar Nodes Found',
                        'No nodes with similar properties or labels found.');
                    return;
                }
                
                // Separate nodes already in graph vs new nodes
                const existingIds = new Set(Object.keys(this.graphAddon.nodesData));
                const newNodes = allSimilarNodes.filter(n => !existingIds.has(n.id));
                const existingNodes = allSimilarNodes.filter(n => existingIds.has(n.id));
                
                console.log(`Found ${allSimilarNodes.length} similar nodes: ${existingNodes.length} existing, ${newNodes.length} new`);
                
                // Add new nodes to graph if any
                if (newNodes.length > 0 && window.app && window.app.addNodesToGraph) {
                    window.app.addNodesToGraph(newNodes, []);
                    // Update internal data after adding nodes
                    setTimeout(() => {
                        this.graphAddon.buildNodesData();
                    }, 500);
                }
                
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
                
                // Add edges after a delay to ensure new nodes are added
                setTimeout(() => {
                    network.body.data.edges.add(similarityEdges);
                    
                    // Focus on similar nodes
                    const allNodeIds = [nodeId, ...allSimilarNodes.map(n => n.id)];
                    setTimeout(() => {
                        network.fit({
                            nodes: allNodeIds,
                            animation: { duration: 1000, easingFunction: 'easeInOutQuad' }
                        });
                    }, 100);
                }, 600);
                
                this.showSuccessPanel('Similar Nodes Found',
                    `Found ${allSimilarNodes.length} nodes with similar properties or labels.<br>
                     <small>${newNodes.length} new nodes added, ${existingNodes.length} already visible.<br>
                     Purple dotted lines show similarity connections.</small>`);
                
            } catch (error) {
                console.error('Error finding similar nodes:', error);
                this.showErrorPanel('Error Finding Similar Nodes', error.message);
            }
        },
        
        // ============================================================
        // CLEAR DISCOVERED RELATIONSHIPS
        // ============================================================
        
        /**
         * Clear all discovered relationships (dotted/dashed edges)
         */
        clearDiscoveredRelationships: function() {
            const edgesToRemove = network.body.data.edges.get().filter(edge => 
                edge.dashes || edge.id.startsWith('hidden-') || 
                edge.id.startsWith('path-') || edge.id.startsWith('similar-')
            );
            
            const count = edgesToRemove.length;
            
            network.body.data.edges.remove(edgesToRemove.map(e => e.id));
            
            console.log(`Removed ${count} discovered relationships`);
            
            this.showInfoPanel('Cleared Discovered Relationships',
                `Removed ${count} discovered edge${count !== 1 ? 's' : ''}`);
        },
        
        // ============================================================
        // HELPER FUNCTIONS
        // ============================================================
        
        /**
         * Show loading panel
         */
        showLoadingPanel: function(title, message) {
            const panel = document.getElementById('property-panel');
            const content = document.getElementById('panel-content');
            
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
        showSuccessPanel: function(title, message) {
            const panel = document.getElementById('property-panel');
            const content = document.getElementById('panel-content');
            
            content.innerHTML = `
                <div style="text-align: center; padding: 30px;">
                    <div style="font-size: 32px; margin-bottom: 16px;">✓</div>
                    <div style="color: #10b981; font-size: 14px; font-weight: 600; margin-bottom: 8px;">${title}</div>
                    <div style="color: #94a3b8; font-size: 13px; line-height: 1.5;">${message}</div>
                    <button onclick="window.GraphAddon.closePanel()" style="margin-top: 20px; padding: 8px 20px; background: #3b82f6; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 600;">Close</button>
                </div>
            `;
        },
        
        /**
         * Show info panel
         */
        showInfoPanel: function(title, message) {
            const panel = document.getElementById('property-panel');
            const content = document.getElementById('panel-content');
            
            content.innerHTML = `
                <div style="text-align: center; padding: 30px;">
                    <div style="font-size: 32px; margin-bottom: 16px;">ℹ️</div>
                    <div style="color: #60a5fa; font-size: 14px; font-weight: 600; margin-bottom: 8px;">${title}</div>
                    <div style="color: #94a3b8; font-size: 13px; line-height: 1.5;">${message}</div>
                    <button onclick="window.GraphAddon.closePanel()" style="margin-top: 20px; padding: 8px 20px; background: #3b82f6; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 600;">Close</button>
                </div>
            `;
            panel.style.display = 'flex';
        },
        
        /**
         * Show error panel
         */
        showErrorPanel: function(title, message) {
            const panel = document.getElementById('property-panel');
            const content = document.getElementById('panel-content');
            
            content.innerHTML = `
                <div style="text-align: center; padding: 30px;">
                    <div style="font-size: 32px; margin-bottom: 16px;">⚠️</div>
                    <div style="color: #ef4444; font-size: 14px; font-weight: 600; margin-bottom: 8px;">${title}</div>
                    <div style="color: #94a3b8; font-size: 13px; margin-bottom: 20px;">${this.escapeHtml(message)}</div>
                    <button onclick="window.GraphAddon.closePanel()" style="padding: 8px 20px; background: #3b82f6; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 600;">Close</button>
                </div>
            `;
            panel.style.display = 'flex';
        },
        
        /**
         * Escape HTML for safe display
         */
        escapeHtml: function(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
    };
})();