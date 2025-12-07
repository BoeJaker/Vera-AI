/**
 * GraphCore - Main coordinator for graph functionality
 * Manages initialization flow and module lifecycle
 */

(function() {
    'use strict';
    
    window.GraphCore = {
        // Module references
        data: null,
        style: null,
        ui: null,
        filters: null,
        
        // State
        networkInstance: null,
        initialized: false,
        initPromise: null,
        
        /**
         * Initialize all graph modules in the correct order
         */
        async init(networkInstance) {
            if (this.initialized) {
                console.warn('GraphCore already initialized');
                return this.initPromise;
            }
            
            console.log('GraphCore: Starting initialization...');
            
            this.initPromise = this._initInternal(networkInstance);
            return this.initPromise;
        },
        
        async _initInternal(networkInstance) {
            try {
                this.networkInstance = networkInstance;
                window.network = networkInstance;
                
                // Wait for network to be ready
                await this._waitForNetwork();
                
                // Initialize modules in order
                await this._initModules();
                
                // Set up event coordination
                this._setupEventCoordination();
                
                this.initialized = true;
                console.log('GraphCore: ✓ Initialization complete');
                
                // Trigger ready event
                this._triggerReady();
                
            } catch (error) {
                console.error('GraphCore: Initialization failed:', error);
                throw error;
            }
        },
        
        async _waitForNetwork() {
            return new Promise((resolve) => {
                if (this.networkInstance?.body?.data?.nodes) {
                    resolve();
                } else {
                    const checkInterval = setInterval(() => {
                        if (this.networkInstance?.body?.data?.nodes) {
                            clearInterval(checkInterval);
                            resolve();
                        }
                    }, 100);
                }
            });
        },
        
        async _initModules() {
            console.log('GraphCore: Initializing modules...');
            
            // Initialize data module first (others depend on it)
            if (window.GraphData) {
                this.data = window.GraphData;
                await this.data.init(this.networkInstance);
                console.log('GraphCore: ✓ Data module ready');
            }
            
            // Initialize style module
            if (window.GraphStyle) {
                this.style = window.GraphStyle;
                await this.style.init(this.networkInstance, this.data);
                console.log('GraphCore: ✓ Style module ready');
            }
            
            // Initialize UI module
            if (window.GraphUI) {
                this.ui = window.GraphUI;
                await this.ui.init(this.networkInstance, this.data, this.style);
                console.log('GraphCore: ✓ UI module ready');
            }
            
            // Initialize filters module
            if (window.GraphFilters) {
                this.filters = window.GraphFilters;
                await this.filters.init(this.networkInstance, this.data);
                console.log('GraphCore: ✓ Filters module ready');
            }
            
            // Initialize optional modules
            if (window.GraphDiscovery) {
                await window.GraphDiscovery.init(this);
                console.log('GraphCore: ✓ Discovery module ready');
            }
            
            if (window.GraphContextMenu) {
                await window.GraphContextMenu.init(this);
                console.log('GraphCore: ✓ Context menu ready');
            }
        },
        
        _setupEventCoordination() {
            // Listen for network data changes
            this.networkInstance.on('dataChange', () => {
                console.log('GraphCore: Data changed, updating modules...');
                this.data?.rebuild();
                this.filters?.refresh();
            });
            
            // Handle stabilization
            this.networkInstance.once('stabilized', () => {
                console.log('GraphCore: Network stabilized');
                this.filters?.initialize();
            });
            
            // Timeout fallback
            setTimeout(() => {
                if (!this.filters?.initialized) {
                    console.log('GraphCore: Timeout fallback, initializing filters');
                    this.filters?.initialize();
                }
            }, 5000);
        },
        
        _triggerReady() {
            const event = new CustomEvent('graphReady', {
                detail: { core: this }
            });
            window.dispatchEvent(event);
        },
        
        /**
         * Public API methods
         */
        getNodeData(nodeId) {
            return this.data?.getNode(nodeId);
        },
        
        focusNode(nodeId) {
            this.ui?.focusOnNode(nodeId);
        },
        
        applyFilters() {
            this.filters?.apply();
        }
    };
})();