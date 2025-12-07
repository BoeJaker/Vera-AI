/**
 * GraphData - Node and edge data management
 */

(function() {
    'use strict';
    
    window.GraphData = {
        networkInstance: null,
        nodesData: {},
        vectorData: {},
        initialized: false,
        
        async init(networkInstance) {
            console.log('GraphData: Initializing...');
            this.networkInstance = networkInstance;
            await this.rebuild();
            this.initialized = true;
        },
        
        async rebuild() {
            console.log('GraphData: Rebuilding node data...');
            
            try {
                const nodes = this.networkInstance.body.data.nodes.get();
                
                if (!nodes || nodes.length === 0) {
                    console.warn('GraphData: No nodes found');
                    this.nodesData = {};
                    return;
                }
                
                this.nodesData = {};
                
                nodes.forEach(node => {
                    const properties = node.properties || {};
                    const labels = node.label ? [node.label] : [];
                    
                    this.nodesData[node.id] = {
                        id: node.id,
                        labels: labels,
                        properties: this._sanitizeProperties(properties),
                        display_name: String(node.title || node.id),
                        color: node.color || '#3b82f6',
                        type: node.type || labels[0] || ''
                    };
                });
                
                console.log(`GraphData: Built data for ${Object.keys(this.nodesData).length} nodes`);
                
                // Trigger event for other modules
                this._triggerDataUpdate();
                
            } catch (error) {
                console.error('GraphData: Error building data:', error);
            }
        },
        
        _sanitizeProperties(properties) {
            if (!properties || typeof properties !== 'object') {
                return {};
            }
            
            const sanitized = {};
            for (const [key, value] of Object.entries(properties)) {
                try {
                    if (value === null || value === undefined) {
                        sanitized[key] = 'null';
                    } else if (value instanceof Date) {
                        sanitized[key] = value.toISOString();
                    } else if (typeof value === 'object') {
                        try {
                            sanitized[key] = JSON.stringify(value);
                        } catch (e) {
                            sanitized[key] = '[Complex Object]';
                        }
                    } else {
                        sanitized[key] = String(value);
                    }
                } catch (e) {
                    console.warn(`GraphData: Error sanitizing property ${key}:`, e);
                    sanitized[key] = '[Error rendering value]';
                }
            }
            return sanitized;
        },
        
        _triggerDataUpdate() {
            const event = new CustomEvent('graphDataUpdated', {
                detail: { nodesData: this.nodesData }
            });
            window.dispatchEvent(event);
        },
        
        // Public API
        getNode(nodeId) {
            return this.nodesData[nodeId] || null;
        },
        
        getAllNodes() {
            return this.nodesData;
        },
        
        searchNodes(searchTerm) {
            const term = searchTerm.toLowerCase().trim();
            const matches = [];
            
            for (const [nodeId, nodeData] of Object.entries(this.nodesData)) {
                const searchableText = [
                    nodeData.display_name,
                    ...(nodeData.labels || []),
                    ...Object.values(nodeData.properties || {})
                ].join(' ').toLowerCase();
                
                if (searchableText.includes(term)) {
                    matches.push({ id: nodeId, data: nodeData });
                }
            }
            
            return matches;
        },
        
        getNeighbors(nodeId) {
            const neighbors = [];
            
            try {
                const connectedEdges = this.networkInstance.getConnectedEdges(nodeId);
                
                connectedEdges.forEach(edgeId => {
                    const edge = this.networkInstance.body.data.edges.get(edgeId);
                    if (!edge) return;
                    
                    const neighborId = edge.from === nodeId ? edge.to : edge.from;
                    const neighborNode = this.nodesData[neighborId];
                    
                    if (neighborNode) {
                        const edgeLabel = edge.label || edge.type || 'connected';
                        const direction = edge.from === nodeId ? '→' : '←';
                        neighbors.push({
                            id: neighborId,
                            name: neighborNode.display_name || neighborId,
                            relationship: `${direction} ${edgeLabel}`,
                            color: neighborNode.color
                        });
                    }
                });
            } catch (error) {
                console.error('GraphData: Error getting neighbors:', error);
            }
            
            return neighbors;
        },
        
        setVectorData(nodeId, data) {
            this.vectorData[nodeId] = data;
        },
        
        getVectorData(nodeId) {
            return this.vectorData[nodeId] || null;
        }
    };
})();