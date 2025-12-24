/**
 * Graph Modules Initialization - Optimized Event-Driven Version
 * Eliminates polling delays by using custom events
 */

(function() {
    'use strict';
    
    let initializationAttempted = false;
    
    function initGraphModules() {
        console.log('=== INIT: Starting graph modules initialization ===');
        
        // Prevent double initialization
        if (initializationAttempted) {
            console.log('INIT: Already attempted, skipping...');
            return;
        }
        
        // Check if required objects exist
        if (typeof window.GraphAddon === 'undefined') {
            console.error('INIT: GraphAddon not found!');
            return;
        }
        
        if (typeof window.GraphDiscovery === 'undefined') {
            console.error('INIT: GraphDiscovery not found!');
            return;
        }
        
        if (typeof window.GraphContextMenu === 'undefined') {
            console.error('INIT: GraphContextMenu not found!');
            return;
        }
        
        // Check if GraphDiscovery is already initialized (better check than nodesData)
        if (window.GraphDiscovery.graphAddon) {
            console.log('INIT: Modules already initialized');
            return;
        }
        
        // Mark as attempted to prevent retries
        initializationAttempted = true;
        
        // Check if GraphAddon has data (allow empty graphs to initialize)
        const hasNodesData = window.GraphAddon.nodesData && 
                            typeof window.GraphAddon.nodesData === 'object';
        
        if (!hasNodesData) {
            console.warn('INIT: GraphAddon nodesData not initialized yet');
            initializationAttempted = false; // Allow retry
            return;
        }
        
        const nodeCount = Object.keys(window.GraphAddon.nodesData).length;
        console.log('INIT: GraphAddon ready with', nodeCount, 'nodes');
        
        // Initialize modules
        console.log('INIT: Initializing GraphDiscovery...');
        window.GraphDiscovery.init(window.GraphAddon);
        
        console.log('INIT: Initializing GraphContextMenu...');
        window.GraphContextMenu.init(window.GraphAddon, window.GraphDiscovery);
        
        // Initialize canvas context menu if available
        if (window.GraphCanvasMenu) {
            console.log('INIT: Initializing GraphCanvasMenu...');
            window.GraphCanvasMenu.init(window.GraphAddon, window.GraphDiscovery);
        }

        // Initialize GraphToolExecutor if available
        if (window.GraphToolExecutor && window.app && window.app.sessionId) {
            console.log('INIT: Initializing GraphToolExecutor...');
            window.GraphToolExecutor.init(window.GraphAddon, window.app.sessionId);
        }
        
        // Initialize GraphInfoCard if available
        if (window.GraphInfoCard) {
            console.log('INIT: Initializing GraphInfoCard...');
            window.GraphInfoCard.init(window.GraphAddon);
        }
        // Initialize GraphStyleControl
        if (window.GraphStyleControl) {
            console.log('INIT: Initializing GraphStyleControl...');
            window.GraphStyleControl.init(window.GraphAddon);
        }
        console.log('=== INIT: ✓ Graph modules initialized successfully ===');
        
        // Dispatch event to signal completion
        window.dispatchEvent(new CustomEvent('graphModulesReady', {
            detail: { nodeCount, timestamp: Date.now() }
        }));
    }
    
    // Expose globally
    window.initGraphModules = initGraphModules;
    
    // Listen for GraphAddon ready event
    window.addEventListener('graphAddonReady', () => {
        console.log('INIT: Received graphAddonReady event, initializing modules...');
        initGraphModules();
    });
    
    // Listen for network stabilization (alternative trigger)
    window.addEventListener('graphNetworkStabilized', () => {
        console.log('INIT: Received graphNetworkStabilized event');
        if (!initializationAttempted) {
            initGraphModules();
        }
    });
})();