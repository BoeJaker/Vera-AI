/**
 * Graph Modules Initialization
 * Call this AFTER all modules are loaded
 */

(function() {
    'use strict';
    
    function initGraphModules() {
        console.log('=== INIT: Starting graph modules initialization ===');
        
        // Check if required objects exist
        if (typeof window.GraphAddon === 'undefined') {
            console.error('INIT: GraphAddon not found!');
            setTimeout(initGraphModules, 500);
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
        
        // Wait for GraphAddon to have nodesData ready
        if (!window.GraphAddon.nodesData || Object.keys(window.GraphAddon.nodesData).length === 0) {
            console.log('INIT: GraphAddon not ready yet (nodesData empty), waiting...');
            setTimeout(initGraphModules, 500);
            return;
        }
        
        // Check if already initialized (prevent double init)
        if (window.GraphDiscovery.graphAddon) {
            console.log('INIT: Modules already initialized, skipping...');
            return;
        }
        
        console.log('INIT: GraphAddon ready with', Object.keys(window.GraphAddon.nodesData).length, 'nodes');
        
        console.log('INIT: Initializing GraphDiscovery...');
        window.GraphDiscovery.init(window.GraphAddon);
        
        console.log('INIT: Initializing GraphContextMenu...');
        window.GraphContextMenu.init(window.GraphAddon, window.GraphDiscovery);
        
        // Initialize GraphToolExecutor if available
        if (window.GraphToolExecutor && window.app && window.app.sessionId) {
            console.log('INIT: Initializing GraphToolExecutor...');
            window.GraphToolExecutor.init(window.GraphAddon, window.app.sessionId);
        } else {
            console.warn('INIT: GraphToolExecutor not available or session ID not found');
        }
        
        // Initialize GraphInfoCard if available
        if (window.GraphInfoCard) {
            console.log('INIT: Initializing GraphInfoCard...');
            window.GraphInfoCard.init(window.GraphAddon);
        }
        
        console.log('=== INIT: ✓ Graph modules initialized successfully ===');
        console.log('  - GraphAddon:', window.GraphAddon ? 'LOADED' : 'NULL');
        console.log('  - GraphDiscovery.graphAddon:', window.GraphDiscovery.graphAddon ? 'SET' : 'NULL');
        console.log('  - GraphContextMenu.graphAddon:', window.GraphContextMenu.graphAddon ? 'SET' : 'NULL');
        console.log('  - GraphContextMenu.graphDiscovery:', window.GraphContextMenu.graphDiscovery ? 'SET' : 'NULL');
        console.log('  - GraphToolExecutor.sessionId:', window.GraphToolExecutor?.sessionId || 'NULL');
        console.log('  - GraphInfoCard:', window.GraphInfoCard ? 'LOADED' : 'NULL');
    }
    
    // Expose globally so it can be called manually
    window.initGraphModules = initGraphModules;
    
    // // Also try to auto-init when DOM is ready
    // if (document.readyState === 'loading') {
    //     document.addEventListener('DOMContentLoaded', () => {
    //         console.log('INIT: DOM loaded, waiting 1 second before init...');
    //         setTimeout(initGraphModules, 1000);
    //     });
    // } else {
    //     console.log('INIT: DOM already loaded, waiting 1 second before init...');
    //     setTimeout(initGraphModules, 1000);
    // }
})();