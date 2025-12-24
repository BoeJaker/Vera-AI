/**
 * Frontend Graph Update Integration
 * 
 * Real-time graph updates from tool execution
 * Add this to your main HTML or include as a module
 * 
 * USAGE:
 *   <script src="tool_graph_frontend.js"></script>
 *   <script>
 *     // After VeraChat initialization
 *     const graphUpdater = new GraphUpdateManager(app.sessionId);
 *     graphUpdater.connect();
 *   </script>
 */

class GraphUpdateManager {
    /**
     * Manages real-time graph updates via WebSocket
     * 
     * @param {string} sessionId - Current session ID
     * @param {Object} options - Configuration options
     */
    constructor(sessionId, options = {}) {
        this.sessionId = sessionId;
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectDelay = 1000; // Start with 1 second
        this.isConnected = false;
        
        this.options = {
            wsUrl: options.wsUrl || `ws://llm.int:8888/api/ws/graph/${sessionId}`,
            autoReconnect: options.autoReconnect !== false,
            animateNewNodes: options.animateNewNodes !== false,
            showNotifications: options.showNotifications !== false,
            debug: options.debug || false,
            ...options
        };
        
        // Callbacks
        this.onConnect = options.onConnect || (() => {});
        this.onDisconnect = options.onDisconnect || (() => {});
        this.onUpdate = options.onUpdate || (() => {});
        this.onError = options.onError || ((err) => console.error('GraphUpdate error:', err));
        
        this.log('GraphUpdateManager initialized');
    }
    
    /**
     * Connect to WebSocket server
     */
    connect() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.log('Already connected');
            return;
        }
        
        this.log(`Connecting to ${this.options.wsUrl}`);
        
        try {
            this.ws = new WebSocket(this.options.wsUrl);
            
            this.ws.onopen = () => this.handleOpen();
            this.ws.onmessage = (event) => this.handleMessage(event);
            this.ws.onclose = (event) => this.handleClose(event);
            this.ws.onerror = (error) => this.handleError(error);
            
        } catch (error) {
            this.log('Connection error:', error);
            this.onError(error);
            this.scheduleReconnect();
        }
    }
    
    /**
     * Disconnect from WebSocket
     */
    disconnect() {
        this.options.autoReconnect = false;
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        this.isConnected = false;
    }
    
    /**
     * Handle WebSocket open
     */
    handleOpen() {
        this.log('✓ WebSocket connected');
        this.isConnected = true;
        this.reconnectAttempts = 0;
        this.reconnectDelay = 1000;
        
        // Start keepalive ping
        this.startKeepalive();
        
        this.onConnect();
        
        if (this.options.showNotifications) {
            this.showNotification('Connected to graph updates', 'success');
        }
    }
    
    /**
     * Handle incoming WebSocket message
     */
    handleMessage(event) {
        try {
            const message = JSON.parse(event.data);
            this.log('Received message:', message.type);
            
            switch (message.type) {
                case 'connected':
                    this.log('Connection confirmed:', message.message);
                    break;
                
                case 'graph_update':
                    this.handleGraphUpdate(message);
                    break;
                
                case 'pong':
                    // Keepalive response
                    break;
                
                default:
                    this.log('Unknown message type:', message.type);
            }
            
        } catch (error) {
            this.log('Error parsing message:', error);
        }
    }
    
    /**
     * Handle graph update message
     */
    handleGraphUpdate(message) {
        const { nodes, edges } = message.data;
        
        this.log(`Graph update: ${nodes?.length || 0} nodes, ${edges?.length || 0} edges`);
        
        if (!window.app || !window.app.networkInstance) {
            this.log('Network instance not available yet, queuing update');
            // Queue for later
            this.queuedUpdate = message;
            return;
        }
        
        // Add nodes and edges to graph
        this.addToGraph(nodes, edges);
        
        // Callback
        this.onUpdate(nodes, edges);
        
        // Show notification
        if (this.options.showNotifications && (nodes?.length > 0 || edges?.length > 0)) {
            this.showNotification(
                `Added ${nodes.length} node(s) and ${edges.length} edge(s)`,
                'info'
            );
        }
    }
    
    /**
     * Add nodes and edges to the graph with animation
     */
    addToGraph(nodes, edges) {
        if (!nodes || nodes.length === 0) return;
        
        const network = window.app.networkInstance;
        const nodesDataSet = network.body.data.nodes;
        const edgesDataSet = network.body.data.edges;
        
        // Use the existing addNodesToGraph method if available
        if (window.app.addNodesToGraph && this.options.animateNewNodes) {
            window.app.addNodesToGraph(nodes, edges);
        } else {
            // Fallback to direct addition
            try {
                // Add nodes
                nodesDataSet.add(nodes);
                
                // Add edges
                if (edges && edges.length > 0) {
                    edgesDataSet.add(edges);
                }
                
                // Update counters
                if (window.app.networkData) {
                    window.app.networkData.nodes = [...window.app.networkData.nodes, ...nodes];
                    if (edges) {
                        window.app.networkData.edges = [...window.app.networkData.edges, ...edges];
                    }
                }
                
                // Update UI counters
                const nodeCount = network.body.data.nodes.length;
                const edgeCount = network.body.data.edges.length;
                
                const nodeCountEl = document.getElementById('nodeCount');
                const edgeCountEl = document.getElementById('edgeCount');
                
                if (nodeCountEl) nodeCountEl.textContent = nodeCount;
                if (edgeCountEl) edgeCountEl.textContent = edgeCount;
                
                // Fit new nodes into view
                const newNodeIds = nodes.map(n => n.id);
                setTimeout(() => {
                    network.fit({
                        nodes: newNodeIds,
                        animation: {
                            duration: 1000,
                            easingFunction: 'easeInOutQuad'
                        }
                    });
                }, 500);
                
            } catch (error) {
                this.log('Error adding to graph:', error);
                // Try update instead
                try {
                    nodesDataSet.update(nodes);
                    if (edges) edgesDataSet.update(edges);
                } catch (updateError) {
                    this.log('Error updating graph:', updateError);
                }
            }
        }
        
        // Update GraphAddon if available
        if (window.GraphAddon && window.GraphAddon.networkReady) {
            setTimeout(() => {
                window.GraphAddon.buildNodesData();
                window.GraphAddon.initializeFilters();
            }, 100);
        }
    }
    
    /**
     * Handle WebSocket close
     */
    handleClose(event) {
        this.log(`WebSocket closed: ${event.code} ${event.reason}`);
        this.isConnected = false;
        
        this.stopKeepalive();
        this.onDisconnect();
        
        if (this.options.autoReconnect) {
            this.scheduleReconnect();
        }
    }
    
    /**
     * Handle WebSocket error
     */
    handleError(error) {
        this.log('WebSocket error:', error);
        this.onError(error);
    }
    
    /**
     * Schedule reconnection attempt
     */
    scheduleReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            this.log('Max reconnection attempts reached');
            if (this.options.showNotifications) {
                this.showNotification('Failed to reconnect to graph updates', 'error');
            }
            return;
        }
        
        this.reconnectAttempts++;
        const delay = Math.min(this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1), 30000);
        
        this.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
        
        setTimeout(() => {
            if (this.options.autoReconnect) {
                this.connect();
            }
        }, delay);
    }
    
    /**
     * Start keepalive ping
     */
    startKeepalive() {
        this.stopKeepalive();
        this.keepaliveInterval = setInterval(() => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send('ping');
            }
        }, 30000); // Ping every 30 seconds
    }
    
    /**
     * Stop keepalive ping
     */
    stopKeepalive() {
        if (this.keepaliveInterval) {
            clearInterval(this.keepaliveInterval);
            this.keepaliveInterval = null;
        }
    }
    
    /**
     * Show notification
     */
    showNotification(message, type = 'info') {
        // Try to use existing notification system
        if (window.showNotification) {
            window.showNotification(message, type);
            return;
        }
        
        // Fallback to console
        const prefix = {
            'success': '✓',
            'info': 'ℹ',
            'warning': '⚠',
            'error': '✗'
        }[type] || 'ℹ';
        
        console.log(`${prefix} ${message}`);
        
        // Simple toast notification
        const toast = document.createElement('div');
        toast.className = `graph-update-toast toast-${type}`;
        toast.textContent = message;
        toast.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            padding: 12px 20px;
            background: ${type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#3b82f6'};
            color: white;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            z-index: 10000;
            font-size: 14px;
            font-weight: 500;
            animation: slideIn 0.3s ease-out;
        `;
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.style.animation = 'slideOut 0.3s ease-out';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
    
    /**
     * Debug logging
     */
    log(...args) {
        if (this.options.debug) {
            console.log('[GraphUpdate]', ...args);
        }
    }
    
    /**
     * Get connection status
     */
    getStatus() {
        return {
            connected: this.isConnected,
            reconnectAttempts: this.reconnectAttempts,
            sessionId: this.sessionId
        };
    }
}

// ============================================================================
// AUTO-INITIALIZATION
// ============================================================================

/**
 * Auto-initialize when VeraChat is ready
 */
(function() {
    // Add CSS for toast notifications
    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideIn {
            from {
                transform: translateX(400px);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }
        
        @keyframes slideOut {
            from {
                transform: translateX(0);
                opacity: 1;
            }
            to {
                transform: translateX(400px);
                opacity: 0;
            }
        }
    `;
    document.head.appendChild(style);
    
    // Wait for app to be ready
    function initGraphUpdates() {
        if (!window.app || !window.app.sessionId) {
            setTimeout(initGraphUpdates, 500);
            return;
        }
        
        console.log('[GraphUpdate] Initializing for session:', window.app.sessionId);
        
        // Create global instance
        window.graphUpdater = new GraphUpdateManager(window.app.sessionId, {
            debug: true,
            onConnect: () => {
                console.log('[GraphUpdate] ✓ Connected to graph updates');
            },
            onDisconnect: () => {
                console.log('[GraphUpdate] ✗ Disconnected from graph updates');
            },
            onUpdate: (nodes, edges) => {
                console.log('[GraphUpdate] ✓ Graph updated:', {
                    nodes: nodes.length,
                    edges: edges.length
                });
            }
        });
        
        // Connect automatically
        window.graphUpdater.connect();
        
        // Expose to console for debugging
        console.log('[GraphUpdate] Available methods:');
        console.log('  graphUpdater.connect()    - Connect to updates');
        console.log('  graphUpdater.disconnect() - Disconnect');
        console.log('  graphUpdater.getStatus()  - Get connection status');
    }
    
    // Start initialization
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initGraphUpdates);
    } else {
        initGraphUpdates();
    }
})();

// ============================================================================
// EXPORTS
// ============================================================================

if (typeof module !== 'undefined' && module.exports) {
    module.exports = GraphUpdateManager;
}