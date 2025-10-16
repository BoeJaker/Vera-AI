/**
 * GraphAddon - Knowledge Graph Visualization and Interaction Module
 * 
 * This module provides advanced graph visualization capabilities including:
 * - Node search and filtering
 * - Context menus and node details panels
 * - Edge type filtering
 * - Subgraph extraction
 * - Visual customization (node styles, physics settings, etc.)
 * 
 * Usage:
 *   GraphAddon.init(vectorData);
 */

(function() {
    'use strict';
    
    window.GraphAddon = {
        vectorData: {},
        nodesData: {},
        focusedNodeId: null,
        allEdges: [],
        edgeTypes: new Set(),
        activeFilters: {},
        cascadeHideNodes: false,
        networkReady: false,
        contextMenuNode: null,
        settingsPanelOpen: false,
        toggleTimeout: null,
        
        /**
         * Initialize GraphAddon with vector data
         * @param {Object} vectorData - Optional vector data for nodes
         */
        init: function(vectorData) {
            console.log('GraphAddon initializing...');
            this.vectorData = vectorData || {};
            
            // Add a small delay to ensure DOM elements exist
            setTimeout(() => {
                this.setupUIListeners();
                this.waitForNetwork();
            }, 100);
        },
        
        /**
         * Set up event listeners for all UI controls
         */
        setupUIListeners: function() {
            const self = this;
            
            const addListener = (id, event, handler) => {
                const el = document.getElementById(id);
                if (el) el.addEventListener(event, handler);
            };
            
            // Note: settings-toggle-btn is handled via inline onclick to avoid double-binding
            addListener('close-panel-btn', 'click', () => self.closePanel());
            addListener('reset-focus-btn', 'click', () => self.resetFocus());
            addListener('cluster-hubs-btn', 'click', () => self.clusterHubs());
            addListener('select-all-filters-btn', 'click', () => self.toggleAllFilters(true));
            addListener('deselect-all-filters-btn', 'click', () => self.toggleAllFilters(false));
            addListener('refresh-filters-btn', 'click', () => self.initializeFilters());
            addListener('cascade-hide', 'change', () => self.toggleCascadeHide());
            addListener('nodeSize', 'input', () => self.updateSettings());
            addListener('edgeWidth', 'input', () => self.updateSettings());
            addListener('physics', 'input', () => self.updateSettings());
            addListener('nodeStyle', 'change', () => self.updateNodeStyle());
            addListener('search-btn', 'click', () => self.performSearch());
            addListener('search-input', 'keypress', (e) => {
                if (e.key === 'Enter') self.performSearch();
            });
            
            // Context menu
            document.addEventListener('click', () => self.hideContextMenu());
            
            const contextMenu = document.getElementById('context-menu');
            if (contextMenu) {
                contextMenu.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const item = e.target.closest('.context-menu-item');
                    if (item) {
                        const action = item.getAttribute('data-action');
                        self.handleContextMenuAction(action);
                    }
                });
            }
        },
        
        /**
         * Wait for network to be ready before initializing
         */
        waitForNetwork: function() {
            const self = this;
            if (typeof network !== 'undefined' && network.body && network.body.data && network.body.data.nodes) {
                console.log('Network found, building node data...');
                setTimeout(() => {
                    self.buildNodesData();
                    self.setupEventListeners();
                }, 100);
            } else {
                console.log('Waiting for network...');
                setTimeout(() => self.waitForNetwork(), 500);
            }
        },
        
        /**
         * Build node data from network
         */
        buildNodesData: function() {
            try {
                const nodes = network.body.data.nodes.get();
                console.log('RAW NETWORK NODES:', nodes); // Add this
                console.log('Sample node:', nodes[0]); // And this
                this.nodesData = {};
                
                if (!nodes || nodes.length === 0) {
                    console.warn('No nodes found in network');
                    return;
                }
                
                nodes.forEach(node => {
                    let properties = {};
                    let labels = [];
                    
                    // Extract label from node.label (not node.title)
                    if (node.label) {
                        labels = [node.label]; // Wrap single label in array
                    }
                    
                    // Try to parse title for additional properties
                    // if (node.title) {
                    try {
                        const parsed = node.properties;
                        properties = node.properties;
                        console.log(node.properties)
                        // Only override labels if parsed data has them
                        if ([node.type] && Array.isArray(node.type)) {
                            labels = node.rtpe;
                        }
                    } catch (e) {
                        // If title is not JSON, just store it as a property
                        console.log(e)
                        const titleStr = String(node.title);
                        // properties = { raw_title: titleStr };
                    }
                    // }
                    
                    const safeProperties = this.sanitizeProperties(properties);
                    // titleStr.split(":")[0] is a bit of a hacky fix, this whole function needs reworking to match the MX implementation
                    this.nodesData[node.id] = {
                        id: node.id,
                        labels: labels, //node.title.split(':')[0] || labels[0] || '',
                        properties: properties,
                        display_name: node.label || String(node.id),
                        color: node.color
                    };
                });
                
                console.log(`Built data for ${Object.keys(this.nodesData).length} nodes`, this.nodesData);
            } catch (e) {
                console.error('Error building nodes data:', e);
            }
        },
        
        /**
         * Sanitize properties for safe display
         */
        sanitizeProperties: function(properties) {
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
                    console.warn(`Error sanitizing property ${key}:`, e);
                    sanitized[key] = '[Error rendering value]';
                }
            }
            return sanitized;
        },
        
        /**
         * Create card view label for nodes
         */
        createCardViewLabel: function(node) {
            const nodeData = this.nodesData[node.id];
            if (!nodeData) return node.label;
            
            const title = nodeData.display_name || node.id;
            const labels = nodeData.labels || [];
            const props = nodeData.properties || {};
            
            let bodyText = props.text || props.body || props.summary || props.description || props.content || '';
            if (bodyText.length > 100) {
                bodyText = bodyText.substring(0, 100) + '...';
            }
            
            let label = title;
            
            if (labels.length > 0) {
                label += '\n[' + labels.slice(0, 3).join(', ') + ']';
            }
            
            if (bodyText) {
                label += '\n' + bodyText;
            }
            
            return label;
        },
        
        /**
         * Create enhanced tooltip for nodes
         */
        createEnhancedTooltip: function(node) {
            const nodeData = this.nodesData[node.id];
            if (!nodeData) return node.label || String(node.id);
            
            const title = nodeData.display_name || String(node.id);
            const labels = nodeData.labels || [];
            const props = nodeData.properties || {};
            
            let bodyText = props.text || props.body || props.summary || props.description || props.content || '';
            if (bodyText.length > 200) {
                bodyText = bodyText.substring(0, 200) + '...';
            }
            
            let html = '<div style="max-width:350px;">';
            html += `<div style="font-weight:bold; color:#ffffff; margin-bottom:8px; font-size:14px; border-bottom:1px solid #000000; padding-bottom:6px;">${this.escapeHtml(title)}</div>`;
            
            if (labels.length > 0) {
                html += '<div style="margin-bottom:8px;">';
                labels.slice(0, 3).forEach(label => {
                    html += `<span style="display:inline-block; background:#ffffff; color:black; padding:2px 8px; border-radius:4px; margin:2px; font-size:11px;">${this.escapeHtml(String(label))}</span>`;
                });
                html += '</div>';
            }
            
            if (bodyText) {
                html += `<div style="margin-top:8px; color:#ffffff; font-size:12px; line-height:1.5;">${this.escapeHtml(bodyText)}</div>`;
            }
            
            html += '</div>';
            return html;
        },
        
        /**
         * Set up network event listeners
         */
        setupEventListeners: function() {
            const self = this;
            
            network.off("click");
            network.on("click", function(params) {
                if (!self.networkReady) return;
                
                if (params.nodes.length > 0) {
                    self.focusOnNode(params.nodes[0]);
                } else if (params.edges.length > 0) {
                    self.showEdgeDetails(params.edges[0]);
                } else {
                    self.closePanel();
                }
            });
            
            // Right-click context menu
            network.on("oncontext", function(params) {
                params.event.preventDefault();
                
                const nodeId = network.getNodeAt(params.pointer.DOM);
                if (nodeId) {
                    self.contextMenuNode = nodeId;
                    self.showContextMenu(params.event.clientX, params.event.clientY);
                }
            });
            
            // Listen for data changes (when graph is updated dynamically)
            network.on('dataChange', function() {
                console.log('Network data changed, rebuilding node data...');
                self.buildNodesData();
                if (self.networkReady) {
                    self.initializeFilters();
                }
            });
            
            network.once('stabilized', function() {
                console.log('Network stabilized');
                self.networkReady = true;
                self.buildNodesData();
                setTimeout(() => self.initializeFilters(), 1000);
            });
            
            setTimeout(function() {
                if (!self.networkReady) {
                    self.networkReady = true;
                    self.buildNodesData();
                    self.initializeFilters();
                }
            }, 5000);
        },
        
        /**
         * Show context menu at specified coordinates
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
         * Handle context menu actions
         */
        handleContextMenuAction: function(action) {
            this.hideContextMenu();
            
            if (!this.contextMenuNode) return;
            
            const nodeData = this.nodesData[this.contextMenuNode];
            const nodeName = nodeData ? nodeData.display_name : this.contextMenuNode;
            
            switch(action) {
                case 'search':
                    console.log('Search action for node:', nodeName);
                    alert(`Search functionality will be implemented for: ${nodeName}`);
                    break;
                case 'enrich':
                    console.log('Enrich (NLP) action for node:', nodeName);
                    alert(`NLP Analysis will be performed on: ${nodeName}\n\nThis will analyze text content and extract:\n- Entities\n- Keywords\n- Sentiment\n- Topics`);
                    break;
                case 'hidden-relationships':
                    console.log('Hidden relationships action for node:', nodeName);
                    alert(`Discovering hidden relationships for: ${nodeName}\n\nThis will analyze:\n- Indirect connections\n- Pattern-based relationships\n- Semantic similarities`);
                    break;
                case 'discover':
                    console.log('Discover action for node:', nodeName);
                    alert(`Discovery mode for: ${nodeName}\n\nThis will explore:\n- Related concepts\n- Knowledge gaps\n- Expansion opportunities`);
                    break;
                case 'ideas':
                    console.log('Generate ideas action for node:', nodeName);
                    alert(`Generating idea stubs for: ${nodeName}\n\nThis will create:\n- Related concepts\n- Questions to explore\n- Potential connections`);
                    break;
                case 'subgraph':
                    this.extractSubgraph(this.contextMenuNode);
                    break;
                case 'ask-vera':
                    console.log('Ask Vera action for node:', nodeName);
                    alert(`Ask Vera about: ${nodeName}\n\nYou can ask:\n- Questions about this node\n- Request analysis\n- Get recommendations`);
                    break;
            }
        },
        
        /**
         * Extract and display subgraph centered on a node
         */
        extractSubgraph: function(centerNodeId) {
            console.log('Extracting subgraph for node:', centerNodeId);
            
            try {
                const connectedNodes = network.getConnectedNodes(centerNodeId);
                const subgraphNodes = [centerNodeId, ...connectedNodes];
                
                const allEdges = network.body.data.edges.get();
                const subgraphEdges = allEdges.filter(edge => {
                    return subgraphNodes.includes(edge.from) && subgraphNodes.includes(edge.to);
                });
                
                const allNodeIds = Object.keys(this.nodesData);
                const nodeUpdates = allNodeIds.map(nodeId => ({
                    id: nodeId,
                    hidden: !subgraphNodes.includes(nodeId)
                }));
                
                network.body.data.nodes.update(nodeUpdates);
                
                const edgeUpdates = allEdges.map(edge => ({
                    id: edge.id,
                    hidden: !subgraphEdges.some(e => e.id === edge.id)
                }));
                
                network.body.data.edges.update(edgeUpdates);
                
                setTimeout(() => {
                    network.fit({
                        nodes: subgraphNodes,
                        animation: { duration: 1000, easingFunction: 'easeInOutQuad' }
                    });
                }, 100);
                
                const nodeData = this.nodesData[centerNodeId];
                const nodeName = nodeData ? nodeData.display_name : centerNodeId;
                
                console.log(`Subgraph extracted: ${subgraphNodes.length} nodes, ${subgraphEdges.length} edges`);
                
                const panel = document.getElementById('property-panel');
                const content = document.getElementById('panel-content');
                
                content.innerHTML = `
                    <div style="text-align:center; padding:20px;">
                        <div style="font-size:24px; margin-bottom:10px;">🗺️</div>
                        <div style="font-weight:bold; color:#60a5fa; margin-bottom:10px;">Subgraph Extracted</div>
                        <div style="color:#cbd5e1; font-size:13px; margin-bottom:15px;">
                            Centered on: <strong>${this.escapeHtml(nodeName)}</strong>
                        </div>
                        <div style="background:#0f172a; padding:12px; border-radius:6px; margin-bottom:15px;">
                            <div style="color:#94a3b8; font-size:12px;">
                                <div>Nodes: <strong style="color:#60a5fa;">${subgraphNodes.length}</strong></div>
                                <div style="margin-top:4px;">Edges: <strong style="color:#60a5fa;">${subgraphEdges.length}</strong></div>
                            </div>
                        </div>
                        <button onclick="window.GraphAddon.resetSubgraph()" style="
                            background:#3b82f6; color:white; border:none; padding:8px 16px;
                            border-radius:6px; cursor:pointer; font-weight:600; font-size:13px;
                        ">Show Full Graph</button>
                    </div>
                `;
                panel.style.display = 'flex';
                
            } catch (e) {
                console.error('Error extracting subgraph:', e);
                alert('Error extracting subgraph. See console for details.');
            }
        },
        
        /**
         * Reset to full graph view
         */
        resetSubgraph: function() {
            console.log('Resetting to full graph');
            
            const allNodeIds = Object.keys(this.nodesData);
            const nodeUpdates = allNodeIds.map(nodeId => ({
                id: nodeId,
                hidden: false
            }));
            network.body.data.nodes.update(nodeUpdates);
            
            const allEdges = network.body.data.edges.get();
            const edgeUpdates = allEdges.map(edge => ({
                id: edge.id,
                hidden: false
            }));
            network.body.data.edges.update(edgeUpdates);
            
            this.applyFilters();
            this.resetFocus();
            this.closePanel();
        },
        
        /**
         * Perform search across nodes
         */
        performSearch: function() {
            const searchTerm = document.getElementById('search-input').value.toLowerCase().trim();
            const resultsContainer = document.getElementById('search-results');
            
            if (!searchTerm) {
                resultsContainer.style.display = 'none';
                resultsContainer.innerHTML = '';
                return;
            }
            
            const matchingNodes = [];
            
            for (const [nodeId, nodeData] of Object.entries(this.nodesData)) {
                const searchableText = [
                    nodeData.display_name,
                    ...(nodeData.labels || []),
                    ...Object.values(nodeData.properties || {})
                ].join(' ').toLowerCase();
                
                if (searchableText.includes(searchTerm)) {
                    matchingNodes.push({
                        id: nodeId,
                        data: nodeData
                    });
                }
            }
            
            if (matchingNodes.length === 0) {
                resultsContainer.innerHTML = '<div style="padding:8px; color:#94a3b8; font-size:12px; text-align:center;">No results found</div>';
                resultsContainer.style.display = 'block';
                return;
            }
            
            console.log(`Found ${matchingNodes.length} matching nodes`);
            
            let html = '';
            matchingNodes.slice(0, 20).forEach(match => {
                const labels = match.data.labels && match.data.labels.length > 0 
                    ? match.data.labels.slice(0, 2).join(', ') 
                    : '';
                html += `
                    <div class="search-result-item" data-node-id="${this.escapeHtml(String(match.id))}">
                        <div class="search-result-name">${this.escapeHtml(match.data.display_name)}</div>
                        ${labels ? `<div class="search-result-labels">${this.escapeHtml(labels)}</div>` : ''}
                    </div>
                `;
            });
            
            if (matchingNodes.length > 20) {
                html += `<div style="padding:8px; color:#94a3b8; font-size:11px; text-align:center;">Showing first 20 of ${matchingNodes.length} results</div>`;
            }
            
            resultsContainer.innerHTML = html;
            resultsContainer.style.display = 'block';
            
            const self = this;
            resultsContainer.querySelectorAll('.search-result-item').forEach(item => {
                item.addEventListener('click', function() {
                    const nodeId = this.getAttribute('data-node-id');
                    self.focusOnNode(nodeId);
                });
            });
            
            const matchingIds = matchingNodes.map(m => m.id);
            network.selectNodes(matchingIds);
        },
        
        /**
         * Initialize edge type filters
         */
        initializeFilters: function() {
            if (!network.body || !network.body.data) {
                setTimeout(() => this.initializeFilters(), 1000);
                return;
            }
            
            const edges = network.body.data.edges.get();
            if (edges.length === 0) {
                setTimeout(() => this.initializeFilters(), 2000);
                return;
            }
            
            this.allEdges = edges;
            const previousFilters = {...this.activeFilters};
            this.edgeTypes.clear();
            
            edges.forEach(edge => {
                const edgeType = edge.label || edge.type || edge.title || 'unlabeled';
                this.edgeTypes.add(edgeType);
            });
            
            const filterContainer = document.getElementById('edge-filters');
            if (!filterContainer) return;
            
            filterContainer.innerHTML = '';
            
            this.edgeTypes.forEach(type => {
                this.activeFilters[type] = previousFilters.hasOwnProperty(type) ? previousFilters[type] : true;
                
                const div = document.createElement('div');
                div.className = 'filter-item';
                
                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.id = `filter-${type}`;
                checkbox.checked = this.activeFilters[type];
                checkbox.addEventListener('change', () => this.applyFilters());
                
                const label = document.createElement('label');
                label.setAttribute('for', `filter-${type}`);
                label.textContent = type;
                
                div.appendChild(checkbox);
                div.appendChild(label);
                filterContainer.appendChild(div);
            });
            
            this.applyFilters();
        },
        
        /**
         * Apply edge filters
         */
        applyFilters: function() {
            if (!this.networkReady) return;
            
            try {
                this.edgeTypes.forEach(type => {
                    const checkbox = document.getElementById(`filter-${type}`);
                    if (checkbox) {
                        this.activeFilters[type] = checkbox.checked;
                    }
                });
                
                const filteredEdges = this.allEdges.filter(edge => {
                    const edgeType = edge.label || edge.type || edge.title || 'unlabeled';
                    return this.activeFilters[edgeType] !== false;
                });
                
                network.body.data.edges.clear();
                network.body.data.edges.add(filteredEdges);
                
                if (this.cascadeHideNodes) {
                    const connectedNodeIds = new Set();
                    filteredEdges.forEach(edge => {
                        connectedNodeIds.add(edge.from);
                        connectedNodeIds.add(edge.to);
                    });
                    
                    const nodeUpdates = Object.keys(this.nodesData).map(nodeId => ({
                        id: nodeId,
                        hidden: !connectedNodeIds.has(nodeId)
                    }));
                    
                    network.body.data.nodes.update(nodeUpdates);
                } else {
                    const nodeUpdates = Object.keys(this.nodesData).map(nodeId => ({
                        id: nodeId,
                        hidden: false
                    }));
                    
                    network.body.data.nodes.update(nodeUpdates);
                }
            } catch (e) {
                console.error('Error applying filters:', e);
            }
        },
        
        /**
         * Toggle all filters on or off
         */
        toggleAllFilters: function(state) {
            this.edgeTypes.forEach(type => {
                const checkbox = document.getElementById(`filter-${type}`);
                if (checkbox) {
                    checkbox.checked = state;
                    this.activeFilters[type] = state;
                }
            });
            this.applyFilters();
        },
        
        /**
         * Toggle cascade hide of isolated nodes
         */
        toggleCascadeHide: function() {
            this.cascadeHideNodes = document.getElementById('cascade-hide').checked;
            this.applyFilters();
        },
        
        /**
         * Focus on a specific node
         */
        focusOnNode: function(nodeId) {
            this.showNodeDetails(nodeId, true);
            network.selectNodes([nodeId]);
        },
        
        /**
         * Show node details panel
         */
        showNodeDetails: function(nodeId, focusViewport) {
            const panel = document.getElementById('property-panel');
            const content = document.getElementById('panel-content');
            
            try {
                if (!this.nodesData[nodeId]) {
                    content.innerHTML = '<p style="color:#ef4444;">Node data not found</p>';
                    panel.style.display = 'flex';
                    return;
                }
                
                const node = this.nodesData[nodeId];
                
                let html = `
                    <div class="section">
                        <div class="section-title">Node ID</div>
                        <div class="property"><code>${this.escapeHtml(String(node.id))}</code></div>
                    </div>
                    <div class="section">
                        <div class="section-title">Labels</div>
                        <div>${(node.labels || []).map(l => `<span class="label-badge">${this.escapeHtml(String(l))}</span>`).join('')}</div>
                    </div>
                    <div class="section">
                        <div class="section-title">Display Name</div>
                        <div class="property">${this.escapeHtml(node.display_name || String(node.id))}</div>
                    </div>
                    <div class="section">
                        <div class="section-title">Properties</div>
                `;
                
                const props = node.properties || {};
                const propEntries = Object.entries(props);
                const maxPropsToShow = 20;
                const propsToShow = propEntries.slice(0, maxPropsToShow);
                const hasMoreProps = propEntries.length > maxPropsToShow;
                
                propsToShow.forEach(([key, value]) => {
                    const displayValue = typeof value === 'string' && value.length > 200 
                        ? this.escapeHtml(value.substring(0, 200)) + '...' 
                        : this.escapeHtml(String(value));
                    html += `<div class="property"><span class="property-key">${this.escapeHtml(String(key))}:</span> ${displayValue}</div>`;
                });
                
                if (hasMoreProps) {
                    html += `<div style="text-align:center; font-style:italic; color:#94a3b8; margin-top:8px;">Showing first ${maxPropsToShow} of ${propEntries.length} properties</div>`;
                }
                
                html += `</div><div class="section"><div class="section-title">Neighbors</div>`;
                const neighbors = this.getNeighbors(nodeId);
                const maxNeighbors = 50;
                const neighborsToShow = neighbors.slice(0, maxNeighbors);
                const hasMoreNeighbors = neighbors.length > maxNeighbors;
                
                if (neighborsToShow.length > 0) {
                    neighborsToShow.forEach(neighbor => {
                        const borderColor = neighbor.color || '#3b82f6';
                        html += `
                            <div class="neighbor-item" data-neighbor-id="${this.escapeHtml(String(neighbor.id))}" style="border-left-color: ${borderColor};">
                                <div class="neighbor-name">${this.escapeHtml(neighbor.name)}</div>
                                <div class="neighbor-relationship">${this.escapeHtml(neighbor.relationship)}</div>
                            </div>
                        `;
                    });
                    
                    if (hasMoreNeighbors) {
                        html += `<div style="text-align:center; font-style:italic; color:#94a3b8; margin-top:8px;">Showing first ${maxNeighbors} of ${neighbors.length} neighbors</div>`;
                    }
                } else {
                    html += '<div style="text-align:center; font-style:italic; color:#64748b;">No neighbors</div>';
                }
                
                html += `</div><div class="section"><div class="section-title">Vector Content</div>${this.renderVectorContent(nodeId)}</div>`;
                
                content.innerHTML = html;
                panel.style.display = 'flex';
                
                const neighborItems = content.querySelectorAll('.neighbor-item[data-neighbor-id]');
                neighborItems.forEach(item => {
                    const neighborId = item.getAttribute('data-neighbor-id');
                    item.addEventListener('click', (e) => {
                        e.stopPropagation();
                        this.focusOnNode(neighborId);
                    });
                });
                
                if (focusViewport) {
                    try {
                        const connectedNodes = network.getConnectedNodes(nodeId);
                        const nodesToFit = [nodeId, ...connectedNodes.slice(0, 100)];
                        network.fit({
                            nodes: nodesToFit,
                            animation: { duration: 1000, easingFunction: 'easeInOutQuad' }
                        });
                    } catch (e) {
                        console.warn('Error fitting viewport:', e);
                    }
                }
            } catch (e) {
                console.error('Error showing node details:', e);
                content.innerHTML = `<p style="color:#ef4444;">Error displaying node: ${e.message}</p>`;
                panel.style.display = 'flex';
            }
        },
        
        /**
         * Show edge details panel
         */
        showEdgeDetails: function(edgeId) {
            const panel = document.getElementById('property-panel');
            const content = document.getElementById('panel-content');
            
            try {
                const edge = network.body.data.edges.get(edgeId);
                if (!edge) {
                    content.innerHTML = '<p style="color:#ef4444;">Edge data not found</p>';
                    panel.style.display = 'flex';
                    return;
                }
                
                const fromNode = this.nodesData[edge.from];
                const toNode = this.nodesData[edge.to];
                const relationship = edge.label || edge.type || 'Connection';
                
                let html = `
                    <div class="section">
                        <div class="section-title">Edge</div>
                        <div class="property"><code>${this.escapeHtml(String(edge.id || 'N/A'))}</code></div>
                    </div>
                    <div class="section">
                        <div class="section-title">Relationship</div>
                        <div class="property">${this.escapeHtml(String(relationship))}</div>
                    </div>
                    <div class="section">
                        <div class="section-title">From Node</div>
                        <div class="neighbor-item" data-node-id="${this.escapeHtml(String(edge.from))}" style="border-left-color: ${fromNode?.color || '#3b82f6'};">
                            <div class="neighbor-name">${this.escapeHtml(fromNode ? fromNode.display_name : String(edge.from))}</div>
                            <div class="neighbor-relationship">Click to view details</div>
                        </div>
                    </div>
                    <div class="section">
                        <div class="section-title">To Node</div>
                        <div class="neighbor-item" data-node-id="${this.escapeHtml(String(edge.to))}" style="border-left-color: ${toNode?.color || '#3b82f6'};">
                            <div class="neighbor-name">${this.escapeHtml(toNode ? toNode.display_name : String(edge.to))}</div>
                            <div class="neighbor-relationship">Click to view details</div>
                        </div>
                    </div>
                `;
                
                content.innerHTML = html;
                panel.style.display = 'flex';
                
                const edgeNeighbors = content.querySelectorAll('.neighbor-item[data-node-id]');
                edgeNeighbors.forEach(item => {
                    const nodeId = item.getAttribute('data-node-id');
                    item.addEventListener('click', (e) => {
                        e.stopPropagation();
                        this.focusOnNode(nodeId);
                    });
                });
            } catch (e) {
                console.error('Error showing edge details:', e);
                content.innerHTML = `<p style="color:#ef4444;">Error displaying edge: ${e.message}</p>`;
                panel.style.display = 'flex';
            }
        },
        
        /**
         * Get neighboring nodes
         */
        getNeighbors: function(nodeId) {
            const neighbors = [];
            try {
                const connectedEdges = network.getConnectedEdges(nodeId);
                
                connectedEdges.forEach(edgeId => {
                    const edge = network.body.data.edges.get(edgeId);
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
            } catch (e) {
                console.error('Error getting neighbors:', e);
            }
            
            return neighbors;
        },
        
        /**
         * Render vector content for a node
         */
        renderVectorContent: function(nodeId) {
            try {
                if (!this.vectorData || !this.vectorData[nodeId]) {
                    return '<div style="text-align:center; font-style:italic; color:#64748b;">No vector content</div>';
                }
                
                let vectorItems = this.vectorData[nodeId];
                
                if (!Array.isArray(vectorItems)) {
                    if (typeof vectorItems === 'object') {
                        vectorItems = [vectorItems];
                    } else if (typeof vectorItems === 'string') {
                        vectorItems = [{type: 'content', content: vectorItems}];
                    } else {
                        return '<div style="text-align:center; font-style:italic; color:#64748b;">Invalid vector data format</div>';
                    }
                }
                
                if (vectorItems.length === 0) {
                    return '<div style="text-align:center; font-style:italic; color:#64748b;">No vector content</div>';
                }
                
                const itemsToShow = vectorItems.slice(0, 50);
                const hasMore = vectorItems.length > 50;
                
                let html = '';
                itemsToShow.forEach(item => {
                    let content = '';
                    let type = 'content';
                    
                    if (typeof item === 'string') {
                        content = item;
                    } else if (typeof item === 'object' && item !== null) {
                        content = item.content || item.text || JSON.stringify(item);
                        type = item.type || 'content';
                    } else {
                        content = String(item);
                    }
                    
                    if (content.length > 500) {
                        content = content.substring(0, 500) + '...';
                    }
                    
                    const typeLabel = type === 'file_chunk' ? '📄 File Chunk' :
                                     type === 'collection_doc' ? '📚 Collection Doc' :
                                     type === 'semantic_match' ? '🔍 Semantic Match' :
                                     '📝 Content';
                    
                    html += `
                        <div class="vector-item">
                            <div class="vector-type">${typeLabel}</div>
                            <div style="font-size:12px;">${this.escapeHtml(content)}</div>
                        </div>
                    `;
                });
                
                if (hasMore) {
                    html += `<div style="text-align:center; font-style:italic; color:#94a3b8; margin-top:10px;">Showing first 50 of ${vectorItems.length} items</div>`;
                }
                
                return html;
            } catch (e) {
                console.error('Error rendering vector content:', e);
                return '<div style="text-align:center; font-style:italic; color:#ef4444;">Error rendering vector content</div>';
            }
        },
        
        /**
         * Escape HTML special characters
         */
        escapeHtml: function(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        },
        
        /**
         * Adjust brightness of hex color
         */
        adjustBrightness: function(color, percent) {
            if (!color || !color.startsWith('#')) return color;
            
            const num = parseInt(color.replace('#', ''), 16);
            const amt = Math.round(2.55 * percent);
            const R = (num >> 16) + amt;
            const G = (num >> 8 & 0x00FF) + amt;
            const B = (num & 0x0000FF) + amt;
            
            return '#' + (0x1000000 + 
                (R < 255 ? (R < 1 ? 0 : R) : 255) * 0x10000 +
                (G < 255 ? (G < 1 ? 0 : G) : 255) * 0x100 +
                (B < 255 ? (B < 1 ? 0 : B) : 255))
                .toString(16).slice(1);
        },
        
        /**
         * Toggle settings panel
         */
        toggleSettings: function() {
            // Prevent rapid repeated toggles
            if (this.toggleTimeout) {
                clearTimeout(this.toggleTimeout);
            }
            
            const panel = document.getElementById('settings-panel');
            if (!panel) {
                console.error('Settings panel element not found!');
                return;
            }
            
            // Toggle the state
            this.settingsPanelOpen = !this.settingsPanelOpen;
            panel.style.left = this.settingsPanelOpen ? '0px' : '-320px';
            
            console.log('Settings panel toggled to:', this.settingsPanelOpen, 'Left:', panel.style.left);
            
            // Block further toggles for 300ms
            this.toggleTimeout = setTimeout(() => {
                this.toggleTimeout = null;
            }, 300);
        },
        
        /**
         * Close property panel
         */
        closePanel: function() {
            const panel = document.getElementById('property-panel');
            if (panel) {
                panel.style.display = 'none';
                console.log('Property panel closed');
            }
        },
        
        /**
         * Reset focus to full graph
         */
        resetFocus: function() {
            if (!this.networkReady) return;
            try {
                network.unselectAll();
                network.fit({animation: true});
                this.focusedNodeId = null;
            } catch (e) {
                console.error('Error resetting focus:', e);
            }
        },
        
        /**
         * Cluster nodes by hub size
         */
        clusterHubs: function() {
            if (!this.networkReady) return;
            try {
                network.clusterByHubsize({threshold: 12});
            } catch(e) {
                console.log('Clustering error:', e);
            }
        },
        
        /**
         * Update graph settings
         */
        updateSettings: function() {
            if (!this.networkReady) return;
            
            try {
                const baseSize = parseInt(document.getElementById('nodeSize').value);
                const edgeWidth = parseInt(document.getElementById('edgeWidth').value);
                const physicsStrength = parseFloat(document.getElementById('physics').value);
                
                document.getElementById('nodeSizeVal').innerText = baseSize;
                document.getElementById('edgeWidthVal').innerText = edgeWidth;
                document.getElementById('physicsVal').innerText = physicsStrength.toFixed(3);
                
                const nodeUpdates = [];
                network.body.data.nodes.forEach(node => {
                    nodeUpdates.push({id: node.id, size: baseSize});
                });
                network.body.data.nodes.update(nodeUpdates);
                
                const edgeUpdates = [];
                network.body.data.edges.forEach(edge => {
                    edgeUpdates.push({id: edge.id, width: edgeWidth});
                });
                network.body.data.edges.update(edgeUpdates);
                
                network.setOptions({
                    physics: {
                        barnesHut: { springConstant: physicsStrength }
                    }
                });
            } catch (e) {
                console.error('Error updating settings:', e);
            }
        },
        
        /**
         * Update node visualization style
         */
        updateNodeStyle: function() {
            if (!this.networkReady) return;
            
            try {
                const style = document.getElementById('nodeStyle').value;
                
                const nodeUpdates = [];
                network.body.data.nodes.forEach(node => {
                    const updateData = {
                        id: node.id
                    };
                    
                    if (style === 'card') {
                        const nodeColor = node.color || '#3b82f6';
                        updateData.shape = 'box';
                        updateData.label = this.createCardViewLabel(node);
                        updateData.font = {
                            multi: true,
                            color: '#000000',
                            size: 12,
                            face: 'arial',
                            align: 'left',
                            bold: { color: '#000000', size: 14 }
                        };
                        updateData.widthConstraint = {
                            minimum: 180,
                            maximum: 280
                        };
                        updateData.heightConstraint = {
                            minimum: 60
                        };
                        updateData.margin = 12;
                        updateData.shapeProperties = {
                            borderRadius: 6
                        };
                        if (typeof nodeColor === 'string') {
                            updateData.color = {
                                background: nodeColor,
                                border: this.adjustBrightness(nodeColor, 20),
                                highlight: {
                                    background: this.adjustBrightness(nodeColor, -10),
                                    border: this.adjustBrightness(nodeColor, 40)
                                },
                                hover: {
                                    background: this.adjustBrightness(nodeColor, -5),
                                    border: this.adjustBrightness(nodeColor, 30)
                                }
                            };
                        } else if (typeof nodeColor === 'object') {
                            updateData.color = nodeColor;
                        }
                        updateData.title = this.createEnhancedTooltip(node);
                    } else if (style === 'box') {
                        const nodeColor = node.color;
                        updateData.shape = 'box';
                        updateData.font = {
                            color: '#ffffffff',
                            size: 14,
                            face: 'arial'
                        };
                        updateData.widthConstraint = {
                            minimum: 80,
                            maximum: 200
                        };
                        updateData.heightConstraint = {
                            minimum: 40
                        };
                        if (nodeColor) {
                            updateData.color = nodeColor;
                        }
                        updateData.title = this.createEnhancedTooltip(node);
                    } else {
                        const nodeColor = node.color;
                        updateData.shape = style;
                        updateData.font = {
                            color: '#ffffff',
                            size: 14
                        };
                        if (nodeColor) {
                            updateData.color = nodeColor;
                        }
                        updateData.title = this.createEnhancedTooltip(node);
                    }
                    
                    nodeUpdates.push(updateData);
                });
                
                network.body.data.nodes.update(nodeUpdates);
                network.redraw();
            } catch (e) {
                console.error('Error updating node style:', e);
            }
        }
    };
    
    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            GraphAddon.init({});
        });
    } else {
        GraphAddon.init({});
    }
})();