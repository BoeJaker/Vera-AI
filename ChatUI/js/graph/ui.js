/**
 * GraphUI - User interface controls and panels
 */

(function() {
    'use strict';
    
    window.GraphUI = {
        networkInstance: null,
        dataModule: null,
        styleModule: null,
        initialized: false,
        
        panels: {
            property: null,
            settings: null
        },
        
        async init(networkInstance, dataModule, styleModule) {
            console.log('GraphUI: Initializing...');
            this.networkInstance = networkInstance;
            this.dataModule = dataModule;
            this.styleModule = styleModule;
            
            this._cachePanels();
            this._setupEventListeners();
            this._setupClickHandlers();
            this._setupSearch();
            
            this.initialized = true;
        },
        
        _cachePanels() {
            this.panels.property = document.getElementById('property-panel');
            this.panels.settings = document.getElementById('settings-panel');
        },
        
        _setupEventListeners() {
            const handlers = {
                'close-panel-btn': () => this.closePanel(),
                'reset-focus-btn': () => this.resetFocus(),
                'cluster-hubs-btn': () => this.clusterHubs(),
                'nodeSize': () => this.styleModule.updateSettings(),
                'edgeWidth': () => this.styleModule.updateSettings(),
                'physics': () => this.styleModule.updateSettings()
            };
            
            Object.entries(handlers).forEach(([id, handler]) => {
                const el = document.getElementById(id);
                if (el) {
                    const eventType = el.tagName === 'INPUT' ? 'input' : 'click';
                    el.addEventListener(eventType, handler);
                }
            });
        },
        
        _setupClickHandlers() {
            this.networkInstance.off("click");
            
            this.networkInstance.on("click", (params) => {
                if (params.nodes.length > 0) {
                    this.showNodeDetails(params.nodes[0], true);
                } else if (params.edges.length > 0) {
                    this.showEdgeDetails(params.edges[0]);
                } else {
                    this.closePanel();
                }
            });
        },
        
        _setupSearch() {
            const searchBtn = document.getElementById('search-btn');
            const searchInput = document.getElementById('search-input');
            
            if (searchBtn) {
                searchBtn.addEventListener('click', () => this.performSearch());
            }
            
            if (searchInput) {
                searchInput.addEventListener('keypress', (e) => {
                    if (e.key === 'Enter') this.performSearch();
                });
            }
        },
        
        performSearch() {
            const searchInput = document.getElementById('search-input');
            const resultsContainer = document.getElementById('search-results');
            
            if (!searchInput || !resultsContainer) return;
            
            const searchTerm = searchInput.value.toLowerCase().trim();
            
            if (!searchTerm) {
                resultsContainer.style.display = 'none';
                resultsContainer.innerHTML = '';
                return;
            }
            
            const matches = this.dataModule.searchNodes(searchTerm);
            
            if (matches.length === 0) {
                resultsContainer.innerHTML = '<div style="padding:8px; color:#94a3b8; font-size:12px; text-align:center;">No results found</div>';
                resultsContainer.style.display = 'block';
                return;
            }
            
            this._renderSearchResults(matches, resultsContainer);
        },
        
        _renderSearchResults(matches, container) {
            let html = '';
            const displayMatches = matches.slice(0, 20);
            
            displayMatches.forEach(match => {
                const labels = match.data.labels?.slice(0, 2).join(', ') || '';
                html += `
                    <div class="search-result-item" data-node-id="${this._escapeHtml(String(match.id))}">
                        <div class="search-result-name">${this._escapeHtml(match.data.display_name)}</div>
                        ${labels ? `<div class="search-result-labels">${this._escapeHtml(labels)}</div>` : ''}
                    </div>
                `;
            });
            
            if (matches.length > 20) {
                html += `<div style="padding:8px; color:#94a3b8; font-size:11px; text-align:center;">Showing first 20 of ${matches.length} results</div>`;
            }
            
            container.innerHTML = html;
            container.style.display = 'block';
            
            // Attach click handlers
            container.querySelectorAll('.search-result-item').forEach(item => {
                item.addEventListener('click', () => {
                    const nodeId = item.getAttribute('data-node-id');
                    this.focusOnNode(nodeId);
                });
            });
            
            // Select matching nodes
            const matchingIds = displayMatches.map(m => m.id);
            this.networkInstance.selectNodes(matchingIds);
        },
        
        showNodeDetails(nodeId, focusViewport = false) {
            const nodeData = this.dataModule.getNode(nodeId);
            
            if (!nodeData) {
                this._showError('Node data not found');
                return;
            }
            
            const content = this._buildNodeDetailsHTML(nodeId, nodeData);
            this._showPanel(content);
            
            // Attach neighbor click handlers
            this._attachNeighborHandlers();
            
            if (focusViewport) {
                this._focusViewportOnNode(nodeId);
            }
        },
        
        _buildNodeDetailsHTML(nodeId, nodeData) {
            const neighbors = this.dataModule.getNeighbors(nodeId);
            const props = nodeData.properties || {};
            const propEntries = Object.entries(props).slice(0, 20);
            
            return `
                <div class="section">
                    <div class="section-title">Node ID</div>
                    <div class="property"><code>${this._escapeHtml(String(nodeData.id))}</code></div>
                </div>
                <div class="section">
                    <div class="section-title">Labels</div>
                    <div>${(nodeData.labels || []).map(l => `<span class="label-badge">${this._escapeHtml(String(l))}</span>`).join('')}</div>
                </div>
                <div class="section">
                    <div class="section-title">Display Name</div>
                    <div class="property">${this._escapeHtml(nodeData.display_name)}</div>
                </div>
                <div class="section">
                    <div class="section-title">Properties</div>
                    ${propEntries.map(([key, value]) => {
                        const displayValue = String(value).length > 200 
                            ? this._escapeHtml(String(value).substring(0, 200)) + '...'
                            : this._escapeHtml(String(value));
                        return `<div class="property"><span class="property-key">${this._escapeHtml(key)}:</span> ${displayValue}</div>`;
                    }).join('')}
                    ${propEntries.length < Object.keys(props).length ? `<div style="text-align:center; font-style:italic; color:#94a3b8; margin-top:8px;">Showing first 20 of ${Object.keys(props).length} properties</div>` : ''}
                </div>
                <div class="section">
                    <div class="section-title">Neighbors (${neighbors.length})</div>
                    ${this._buildNeighborsHTML(neighbors)}
                </div>
            `;
        },
        
        _buildNeighborsHTML(neighbors) {
            if (neighbors.length === 0) {
                return '<div style="text-align:center; font-style:italic; color:#64748b;">No neighbors</div>';
            }
            
            const displayNeighbors = neighbors.slice(0, 50);
            let html = displayNeighbors.map(neighbor => `
                <div class="neighbor-item" data-neighbor-id="${this._escapeHtml(String(neighbor.id))}" style="border-left-color: ${neighbor.color};">
                    <div class="neighbor-name">${this._escapeHtml(neighbor.name)}</div>
                    <div class="neighbor-relationship">${this._escapeHtml(neighbor.relationship)}</div>
                </div>
            `).join('');
            
            if (neighbors.length > 50) {
                html += `<div style="text-align:center; font-style:italic; color:#94a3b8; margin-top:8px;">Showing first 50 of ${neighbors.length} neighbors</div>`;
            }
            
            return html;
        },
        
        showEdgeDetails(edgeId) {
            const edge = this.networkInstance.body.data.edges.get(edgeId);
            
            if (!edge) {
                this._showError('Edge data not found');
                return;
            }
            
            const fromNode = this.dataModule.getNode(edge.from);
            const toNode = this.dataModule.getNode(edge.to);
            const relationship = edge.label || edge.type || 'Connection';
            
            const content = `
                <div class="section">
                    <div class="section-title">Edge</div>
                    <div class="property"><code>${this._escapeHtml(String(edge.id || 'N/A'))}</code></div>
                </div>
                <div class="section">
                    <div class="section-title">Relationship</div>
                    <div class="property">${this._escapeHtml(String(relationship))}</div>
                </div>
                <div class="section">
                    <div class="section-title">From Node</div>
                    <div class="neighbor-item" data-node-id="${this._escapeHtml(String(edge.from))}" style="border-left-color: ${fromNode?.color || '#3b82f6'};">
                        <div class="neighbor-name">${this._escapeHtml(fromNode?.display_name || String(edge.from))}</div>
                        <div class="neighbor-relationship">Click to view details</div>
                    </div>
                </div>
                <div class="section">
                    <div class="section-title">To Node</div>
                    <div class="neighbor-item" data-node-id="${this._escapeHtml(String(edge.to))}" style="border-left-color: ${toNode?.color || '#3b82f6'};">
                        <div class="neighbor-name">${this._escapeHtml(toNode?.display_name || String(edge.to))}</div>
                        <div class="neighbor-relationship">Click to view details</div>
                    </div>
                </div>
            `;
            
            this._showPanel(content);
            this._attachNeighborHandlers();
        },
        
        _showPanel(content) {
            if (this.panels.property) {
                const contentEl = document.getElementById('panel-content');
                if (contentEl) {
                    contentEl.innerHTML = content;
                }
                this.panels.property.style.display = 'flex';
                this.panels.property.classList.add('active');
            }
        },
        
        _showError(message) {
            this._showPanel(`<p style="color:#ef4444;">${this._escapeHtml(message)}</p>`);
        },
        
        _attachNeighborHandlers() {
            const items = document.querySelectorAll('.neighbor-item[data-neighbor-id], .neighbor-item[data-node-id]');
            items.forEach(item => {
                const nodeId = item.getAttribute('data-neighbor-id') || item.getAttribute('data-node-id');
                if (nodeId) {
                    item.addEventListener('click', (e) => {
                        e.stopPropagation();
                        this.focusOnNode(nodeId);
                    });
                }
            });
        },
        
        _focusViewportOnNode(nodeId) {
            try {
                const connectedNodes = this.networkInstance.getConnectedNodes(nodeId);
                const nodesToFit = [nodeId, ...connectedNodes.slice(0, 100)];
                
                this.networkInstance.fit({
                    nodes: nodesToFit,
                    animation: {
                        duration: 1000,
                        easingFunction: 'easeInOutQuad'
                    }
                });
            } catch (error) {
                console.warn('GraphUI: Error fitting viewport:', error);
            }
        },
        
        focusOnNode(nodeId) {
            this.showNodeDetails(nodeId, true);
            this.networkInstance.selectNodes([nodeId]);
        },
        
        closePanel() {
            if (this.panels.property) {
                this.panels.property.style.display = 'none';
                this.panels.property.classList.remove('active');
            }
        },
        
        resetFocus() {
            try {
                this.networkInstance.unselectAll();
                this.networkInstance.fit({ animation: true });
            } catch (error) {
                console.error('GraphUI: Error resetting focus:', error);
            }
        },
        
        clusterHubs() {
            try {
                this.networkInstance.clusterByHubsize({ threshold: 12 });
            } catch (error) {
                console.log('GraphUI: Clustering error:', error);
            }
        },
        
        toggleSettings() {
            if (!this.panels.settings) return;
            
            const isOpen = this.panels.settings.style.left === '0px';
            this.panels.settings.style.left = isOpen ? '-320px' : '0px';
        },
        
        _escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
    };
})();