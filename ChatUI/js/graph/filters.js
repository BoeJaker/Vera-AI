/**
 * GraphFilters - Edge type filtering and node visibility
 */

(function() {
    'use strict';
    
    window.GraphFilters = {
        networkInstance: null,
        dataModule: null,
        initialized: false,
        
        allEdges: [],
        edgeTypes: new Set(),
        activeFilters: {},
        cascadeHideNodes: false,
        
        async init(networkInstance, dataModule) {
            console.log('GraphFilters: Initializing...');
            this.networkInstance = networkInstance;
            this.dataModule = dataModule;
            this._setupControls();
            this.initialized = false; // Will be set true after first initialize()
        },
        
        _setupControls() {
            const selectAll = document.getElementById('select-all-filters-btn');
            const deselectAll = document.getElementById('deselect-all-filters-btn');
            const refresh = document.getElementById('refresh-filters-btn');
            const cascade = document.getElementById('cascade-hide');
            
            if (selectAll) {
                selectAll.addEventListener('click', () => this.toggleAll(true));
            }
            
            if (deselectAll) {
                deselectAll.addEventListener('click', () => this.toggleAll(false));
            }
            
            if (refresh) {
                refresh.addEventListener('click', () => this.initialize());
            }
            
            if (cascade) {
                cascade.addEventListener('change', () => {
                    this.cascadeHideNodes = cascade.checked;
                    this.apply();
                });
            }
        },
        
        initialize() {
            if (!this.networkInstance?.body?.data) {
                console.warn('GraphFilters: Network not ready');
                setTimeout(() => this.initialize(), 1000);
                return;
            }
            
            const edges = this.networkInstance.body.data.edges.get();
            
            if (edges.length === 0) {
                console.warn('GraphFilters: No edges found');
                setTimeout(() => this.initialize(), 2000);
                return;
            }
            
            this.allEdges = edges;
            const previousFilters = {...this.activeFilters};
            this.edgeTypes.clear();
            
            // Collect edge types
            edges.forEach(edge => {
                const edgeType = edge.label || edge.type || edge.title || 'unlabeled';
                this.edgeTypes.add(edgeType);
            });
            
            // Build filter UI
            this._buildFilterUI(previousFilters);
            
            this.initialized = true;
            this.apply();
            
            console.log(`GraphFilters: Initialized with ${this.edgeTypes.size} edge types`);
        },
        
        _buildFilterUI(previousFilters) {
            const container = document.getElementById('edge-filters');
            if (!container) return;
            
            container.innerHTML = '';
            
            this.edgeTypes.forEach(type => {
                // Preserve previous filter state if it exists
                this.activeFilters[type] = previousFilters.hasOwnProperty(type) 
                    ? previousFilters[type] 
                    : true;
                
                const div = document.createElement('div');
                div.className = 'filter-item';
                
                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.id = `filter-${type}`;
                checkbox.checked = this.activeFilters[type];
                checkbox.addEventListener('change', () => this.apply());
                
                const label = document.createElement('label');
                label.setAttribute('for', `filter-${type}`);
                label.textContent = type;
                
                div.appendChild(checkbox);
                div.appendChild(label);
                container.appendChild(div);
            });
        },
        
        apply() {
            if (!this.initialized) return;
            
            try {
                // Update filter states from checkboxes
                this.edgeTypes.forEach(type => {
                    const checkbox = document.getElementById(`filter-${type}`);
                    if (checkbox) {
                        this.activeFilters[type] = checkbox.checked;
                    }
                });
                
                // Filter edges
                const filteredEdges = this.allEdges.filter(edge => {
                    const edgeType = edge.label || edge.type || edge.title || 'unlabeled';
                    return this.activeFilters[edgeType] !== false;
                });
                
                // Update edges
                this.networkInstance.body.data.edges.clear();
                this.networkInstance.body.data.edges.add(filteredEdges);
                
                // Handle node visibility based on cascade setting
                if (this.cascadeHideNodes) {
                    this._applyCascadeHide(filteredEdges);
                } else {
                    this._showAllNodes();
                }
                
            } catch (error) {
                console.error('GraphFilters: Error applying filters:', error);
            }
        },
        
        _applyCascadeHide(filteredEdges) {
            const connectedNodeIds = new Set();
            
            filteredEdges.forEach(edge => {
                connectedNodeIds.add(edge.from);
                connectedNodeIds.add(edge.to);
            });
            
            const nodeUpdates = Object.keys(this.dataModule.nodesData).map(nodeId => ({
                id: nodeId,
                hidden: !connectedNodeIds.has(nodeId)
            }));
            
            this.networkInstance.body.data.nodes.update(nodeUpdates);
        },
        
        _showAllNodes() {
            const nodeUpdates = Object.keys(this.dataModule.nodesData).map(nodeId => ({
                id: nodeId,
                hidden: false
            }));
            
            this.networkInstance.body.data.nodes.update(nodeUpdates);
        },
        
        toggleAll(state) {
            this.edgeTypes.forEach(type => {
                const checkbox = document.getElementById(`filter-${type}`);
                if (checkbox) {
                    checkbox.checked = state;
                    this.activeFilters[type] = state;
                }
            });
            this.apply();
        },
        
        refresh() {
            this.initialize();
        }
    };
})();