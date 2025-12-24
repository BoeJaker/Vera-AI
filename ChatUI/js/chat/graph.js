// =====================================================================
// GraphChatIntegration - Smart Graph Context for Chat
// =====================================================================
// Provides:
// - Graph context panel in chat UI
// - Selected nodes/edges tracking
// - Smart context inclusion controls
// - Graph query templates
// - Real-time graph state synchronization
// =====================================================================

(function() {
    'use strict';
    
    window.GraphChatIntegration = {
        
        // State
        selectedNodes: [],
        selectedEdges: [],
        visibleNodes: [],
        graphStats: {},
        contextMode: 'selected', // 'selected', 'visible', 'all', 'custom', 'none'
        includeProperties: true,
        includeRelationships: true,
        maxNodesInContext: 50,
        
        // Graph data cache
        nodesData: {},
        edgesData: {},
        
        // Initialization
        init: function(veraChat, network) {
            console.log('🔗 Initializing GraphChatIntegration');
            
            this.veraChat = veraChat;
            this.network = network;
            
            // Add graph context panel to chat
            this.addGraphContextPanel();
            
            // Setup graph event listeners
            this.setupGraphListeners();
            
            // Initialize context tracking
            this.updateGraphContext();
            
            console.log('✅ GraphChatIntegration initialized');
        },
        
        // ================================================================
        // UI Components
        // ================================================================
        
        addGraphContextPanel: function() {
            const chatContainer = document.getElementById('tab-chat');
            if (!chatContainer) return;
            
            // Create context panel
            const contextPanel = document.createElement('div');
            contextPanel.id = 'graph-context-panel';
            contextPanel.className = 'graph-context-panel collapsed';
            
            contextPanel.innerHTML = `
                <div class="context-panel-header" onclick="window.GraphChatIntegration.toggleContextPanel()">
                    <div class="context-panel-title">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <circle cx="12" cy="12" r="2"/>
                            <circle cx="12" cy="5" r="2"/>
                            <circle cx="19" cy="12" r="2"/>
                            <circle cx="5" cy="12" r="2"/>
                            <path d="M12 7v3m0 4v3m-5-5h3m4 0h3"/>
                        </svg>
                        <span>Graph Context</span>
                        <span class="context-badge" id="context-badge">0 nodes</span>
                    </div>
                    <button class="context-toggle-btn" id="context-toggle-btn">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="6 9 12 15 18 9"/>
                        </svg>
                    </button>
                </div>
                
                <div class="context-panel-body" id="context-panel-body">
                    <!-- Mode Selection -->
                    <div class="context-section">
                        <label class="context-label">Include in queries:</label>
                        <div class="context-mode-buttons">
                            <button class="context-mode-btn active" data-mode="selected" 
                                    onclick="window.GraphChatIntegration.setContextMode('selected')">
                                Selected
                            </button>
                            <button class="context-mode-btn" data-mode="visible" 
                                    onclick="window.GraphChatIntegration.setContextMode('visible')">
                                Visible
                            </button>
                            <button class="context-mode-btn" data-mode="all" 
                                    onclick="window.GraphChatIntegration.setContextMode('all')">
                                All
                            </button>
                            <button class="context-mode-btn" data-mode="none" 
                                    onclick="window.GraphChatIntegration.setContextMode('none')">
                                None
                            </button>
                        </div>
                    </div>
                    
                    <!-- Context Options -->
                    <div class="context-section">
                        <label class="context-checkbox">
                            <input type="checkbox" id="include-properties" checked 
                                   onchange="window.GraphChatIntegration.toggleOption('properties', this.checked)">
                            <span>Include node properties</span>
                        </label>
                        <label class="context-checkbox">
                            <input type="checkbox" id="include-relationships" checked 
                                   onchange="window.GraphChatIntegration.toggleOption('relationships', this.checked)">
                            <span>Include relationships</span>
                        </label>
                        <label class="context-checkbox">
                            <input type="checkbox" id="auto-include-neighbors" 
                                   onchange="window.GraphChatIntegration.toggleOption('neighbors', this.checked)">
                            <span>Auto-include connected nodes</span>
                        </label>
                    </div>
                    
                    <!-- Current Selection -->
                    <div class="context-section">
                        <div class="context-stats">
                            <div class="stat-item">
                                <span class="stat-label">Selected:</span>
                                <span class="stat-value" id="selected-count">0</span>
                            </div>
                            <div class="stat-item">
                                <span class="stat-label">Visible:</span>
                                <span class="stat-value" id="visible-count">0</span>
                            </div>
                            <div class="stat-item">
                                <span class="stat-label">Total:</span>
                                <span class="stat-value" id="total-count">0</span>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Selected Nodes Preview -->
                    <div class="context-section" id="selected-preview-section" style="display: none;">
                        <label class="context-label">Selected Nodes:</label>
                        <div class="selected-nodes-list" id="selected-nodes-list"></div>
                    </div>
                    
                    <!-- Quick Graph Queries -->
                    <div class="context-section">
                        <label class="context-label">Quick Graph Queries:</label>
                        <div class="quick-queries">
                            <button class="quick-query-btn" onclick="window.GraphChatIntegration.insertGraphQuery('summarize')">
                                📊 Summarize Selection
                            </button>
                            <button class="quick-query-btn" onclick="window.GraphChatIntegration.insertGraphQuery('analyze')">
                                🔍 Analyze Relationships
                            </button>
                            <button class="quick-query-btn" onclick="window.GraphChatIntegration.insertGraphQuery('patterns')">
                                🎯 Find Patterns
                            </button>
                            <button class="quick-query-btn" onclick="window.GraphChatIntegration.insertGraphQuery('suggest')">
                                💡 Suggest Connections
                            </button>
                            <button class="quick-query-btn" onclick="window.GraphChatIntegration.insertGraphQuery('export')">
                                📤 Export Context
                            </button>
                        </div>
                    </div>
                    
                    <!-- Context Preview -->
                    <div class="context-section">
                        <button class="context-action-btn" onclick="window.GraphChatIntegration.previewContext()">
                            👁️ Preview Context Data
                        </button>
                        <button class="context-action-btn" onclick="window.GraphChatIntegration.copyContextToClipboard()">
                            📋 Copy Context
                        </button>
                    </div>
                </div>
            `;
            
            // Insert before chat messages
            const messages = chatContainer.querySelector('#chatMessages');
            if (messages) {
                chatContainer.insertBefore(contextPanel, messages);
            }
            
            console.log('✅ Graph context panel added');
        },
        
        toggleContextPanel: function() {
            const panel = document.getElementById('graph-context-panel');
            const btn = document.getElementById('context-toggle-btn');
            
            if (panel.classList.contains('collapsed')) {
                panel.classList.remove('collapsed');
                btn.innerHTML = `
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="18 15 12 9 6 15"/>
                    </svg>
                `;
            } else {
                panel.classList.add('collapsed');
                btn.innerHTML = `
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="6 9 12 15 18 9"/>
                    </svg>
                `;
            }
        },
        
        // ================================================================
        // Graph Event Listeners
        // ================================================================
        
        setupGraphListeners: function() {
            if (!this.network) return;
            
            // Selection changes
            this.network.on('selectNode', (params) => {
                this.selectedNodes = params.nodes;
                this.selectedEdges = params.edges;
                this.updateGraphContext();
            });
            
            this.network.on('deselectNode', () => {
                this.selectedNodes = this.network.getSelectedNodes();
                this.selectedEdges = this.network.getSelectedEdges();
                this.updateGraphContext();
            });
            
            // Viewport changes (for visible nodes)
            this.network.on('zoom', () => {
                this.updateVisibleNodes();
            });
            
            this.network.on('dragEnd', () => {
                this.updateVisibleNodes();
            });
            
            // Data changes
            this.network.body.data.nodes.on('*', () => {
                this.updateGraphStats();
            });
            
            this.network.body.data.edges.on('*', () => {
                this.updateGraphStats();
            });
            
            console.log('✅ Graph event listeners setup');
        },
        
        // ================================================================
        // Context Management
        // ================================================================
        
        updateGraphContext: function() {
            this.updateVisibleNodes();
            this.updateGraphStats();
            this.updateUI();
        },
        
        updateVisibleNodes: function() {
            if (!this.network) return;
            
            const positions = this.network.getPositions();
            const scale = this.network.getScale();
            const viewPosition = this.network.getViewPosition();
            
            // Get viewport bounds
            const canvas = this.network.canvas.frame.canvas;
            const width = canvas.clientWidth;
            const height = canvas.clientHeight;
            
            const bounds = {
                left: viewPosition.x - (width / (2 * scale)),
                right: viewPosition.x + (width / (2 * scale)),
                top: viewPosition.y - (height / (2 * scale)),
                bottom: viewPosition.y + (height / (2 * scale))
            };
            
            // Filter visible nodes
            this.visibleNodes = Object.keys(positions).filter(nodeId => {
                const pos = positions[nodeId];
                return pos.x >= bounds.left && pos.x <= bounds.right &&
                       pos.y >= bounds.top && pos.y <= bounds.bottom;
            });
        },
        
        updateGraphStats: function() {
            if (!this.network) return;
            
            const nodes = this.network.body.data.nodes.get();
            const edges = this.network.body.data.edges.get();
            
            this.graphStats = {
                totalNodes: nodes.length,
                totalEdges: edges.length,
                selectedNodes: this.selectedNodes.length,
                selectedEdges: this.selectedEdges.length,
                visibleNodes: this.visibleNodes.length
            };
            
            // Cache node and edge data
            nodes.forEach(node => {
                this.nodesData[node.id] = node;
            });
            
            edges.forEach(edge => {
                this.edgesData[edge.id] = edge;
            });
        },
        
        updateUI: function() {
            // Update badge
            const badge = document.getElementById('context-badge');
            if (badge) {
                const count = this.getContextNodeCount();
                badge.textContent = `${count} node${count !== 1 ? 's' : ''}`;
            }
            
            // Update stats
            document.getElementById('selected-count').textContent = this.graphStats.selectedNodes || 0;
            document.getElementById('visible-count').textContent = this.graphStats.visibleNodes || 0;
            document.getElementById('total-count').textContent = this.graphStats.totalNodes || 0;
            
            // Update selected nodes preview
            if (this.selectedNodes.length > 0) {
                this.showSelectedNodesPreview();
            } else {
                const previewSection = document.getElementById('selected-preview-section');
                if (previewSection) previewSection.style.display = 'none';
            }
        },
        
        getContextNodeCount: function() {
            switch(this.contextMode) {
                case 'selected':
                    return this.selectedNodes.length;
                case 'visible':
                    return this.visibleNodes.length;
                case 'all':
                    return this.graphStats.totalNodes || 0;
                case 'none':
                    return 0;
                default:
                    return 0;
            }
        },
        
        showSelectedNodesPreview: function() {
            const previewSection = document.getElementById('selected-preview-section');
            const nodesList = document.getElementById('selected-nodes-list');
            
            if (!previewSection || !nodesList) return;
            
            previewSection.style.display = 'block';
            nodesList.innerHTML = '';
            
            this.selectedNodes.slice(0, 10).forEach(nodeId => {
                const node = this.nodesData[nodeId];
                if (!node) return;
                
                const nodeItem = document.createElement('div');
                nodeItem.className = 'selected-node-item';
                nodeItem.innerHTML = `
                    <span class="node-color-dot" style="background: ${node.color || '#3b82f6'}"></span>
                    <span class="node-label">${this.escapeHtml(node.label || nodeId)}</span>
                    <button class="node-remove-btn" onclick="window.GraphChatIntegration.removeNodeFromSelection('${nodeId}')">×</button>
                `;
                nodesList.appendChild(nodeItem);
            });
            
            if (this.selectedNodes.length > 10) {
                const moreItem = document.createElement('div');
                moreItem.className = 'selected-node-item more-indicator';
                moreItem.textContent = `+${this.selectedNodes.length - 10} more`;
                nodesList.appendChild(moreItem);
            }
        },
        
        removeNodeFromSelection: function(nodeId) {
            const index = this.selectedNodes.indexOf(nodeId);
            if (index > -1) {
                this.selectedNodes.splice(index, 1);
                this.network.unselectAll();
                this.network.selectNodes(this.selectedNodes);
                this.updateGraphContext();
            }
        },
        
        setContextMode: function(mode) {
            this.contextMode = mode;
            
            // Update UI
            document.querySelectorAll('.context-mode-btn').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.mode === mode);
            });
            
            this.updateUI();
            console.log('📍 Context mode:', mode);
        },
        
        toggleOption: function(option, enabled) {
            switch(option) {
                case 'properties':
                    this.includeProperties = enabled;
                    break;
                case 'relationships':
                    this.includeRelationships = enabled;
                    break;
                case 'neighbors':
                    this.autoIncludeNeighbors = enabled;
                    break;
            }
            console.log(`⚙️ ${option}:`, enabled);
        },
        
        // ================================================================
        // Context Data Generation
        // ================================================================
        
        getContextData: function() {
            let nodeIds = [];
            
            switch(this.contextMode) {
                case 'selected':
                    nodeIds = this.selectedNodes;
                    break;
                case 'visible':
                    nodeIds = this.visibleNodes;
                    break;
                case 'all':
                    nodeIds = Object.keys(this.nodesData);
                    break;
                case 'none':
                    return null;
            }
            
            // Limit nodes
            if (nodeIds.length > this.maxNodesInContext) {
                console.warn(`⚠️ Too many nodes (${nodeIds.length}), limiting to ${this.maxNodesInContext}`);
                nodeIds = nodeIds.slice(0, this.maxNodesInContext);
            }
            
            // Include neighbors if enabled
            if (this.autoIncludeNeighbors) {
                const neighbors = this.getNeighborNodes(nodeIds);
                nodeIds = [...new Set([...nodeIds, ...neighbors])];
            }
            
            return this.buildContextObject(nodeIds);
        },
        
        getNeighborNodes: function(nodeIds) {
            const neighbors = new Set();
            
            nodeIds.forEach(nodeId => {
                const connected = this.network.getConnectedNodes(nodeId);
                connected.forEach(id => neighbors.add(id));
            });
            
            return Array.from(neighbors);
        },
        
        buildContextObject: function(nodeIds) {
            const context = {
                metadata: {
                    mode: this.contextMode,
                    node_count: nodeIds.length,
                    timestamp: new Date().toISOString()
                },
                nodes: [],
                relationships: []
            };
            
            // Add nodes
            nodeIds.forEach(nodeId => {
                const node = this.nodesData[nodeId];
                if (!node) return;
                
                const nodeData = {
                    id: node.id,
                    label: node.label || node.id
                };
                
                if (this.includeProperties && node.properties) {
                    nodeData.properties = node.properties;
                }
                
                if (node.group) nodeData.group = node.group;
                if (node.type) nodeData.type = node.type;
                
                context.nodes.push(nodeData);
            });
            
            // Add relationships
            if (this.includeRelationships) {
                const nodeIdSet = new Set(nodeIds);
                
                Object.values(this.edgesData).forEach(edge => {
                    // Only include edges between included nodes
                    if (nodeIdSet.has(edge.from) && nodeIdSet.has(edge.to)) {
                        const edgeData = {
                            from: edge.from,
                            to: edge.to
                        };
                        
                        if (edge.label) edgeData.label = edge.label;
                        if (edge.properties) edgeData.properties = edge.properties;
                        
                        context.relationships.push(edgeData);
                    }
                });
            }
            
            return context;
        },
        
        formatContextAsText: function(contextData) {
            if (!contextData) return '';
            
            let text = '**Graph Context:**\n\n';
            text += `Mode: ${contextData.metadata.mode}\n`;
            text += `Nodes: ${contextData.metadata.node_count}\n\n`;
            
            text += '**Nodes:**\n';
            contextData.nodes.forEach(node => {
                text += `- ${node.label}`;
                if (node.type) text += ` (${node.type})`;
                if (node.properties && Object.keys(node.properties).length > 0) {
                    text += `\n  Properties: ${JSON.stringify(node.properties, null, 2).split('\n').join('\n  ')}`;
                }
                text += '\n';
            });
            
            if (contextData.relationships.length > 0) {
                text += '\n**Relationships:**\n';
                contextData.relationships.forEach(rel => {
                    const fromNode = contextData.nodes.find(n => n.id === rel.from);
                    const toNode = contextData.nodes.find(n => n.id === rel.to);
                    text += `- ${fromNode?.label || rel.from} → ${toNode?.label || rel.to}`;
                    if (rel.label) text += ` [${rel.label}]`;
                    text += '\n';
                });
            }
            
            return text;
        },
        
        // ================================================================
        // Quick Graph Queries
        // ================================================================
        
        insertGraphQuery: function(queryType) {
            const contextData = this.getContextData();
            if (!contextData || contextData.nodes.length === 0) {
                this.showToast('⚠️ No graph context selected');
                return;
            }
            
            const templates = {
                'summarize': `Analyze and summarize this graph data:\n\n${this.formatContextAsText(contextData)}\n\nProvide key insights, patterns, and notable relationships.`,
                
                'analyze': `Analyze the relationships in this graph:\n\n${this.formatContextAsText(contextData)}\n\nIdentify:\n- Key connections\n- Central nodes\n- Relationship patterns\n- Potential gaps`,
                
                'patterns': `Find patterns and clusters in this graph data:\n\n${this.formatContextAsText(contextData)}\n\nLook for:\n- Common themes\n- Node groupings\n- Unusual connections\n- Potential communities`,
                
                'suggest': `Based on this graph data:\n\n${this.formatContextAsText(contextData)}\n\nSuggest:\n- Missing connections that would make sense\n- Additional nodes to explore\n- Ways to organize or categorize`,
                
                'export': this.formatContextAsText(contextData)
            };
            
            const messageInput = document.getElementById('messageInput');
            if (messageInput) {
                messageInput.value = templates[queryType] || '';
                messageInput.focus();
                messageInput.dispatchEvent(new Event('input')); // Trigger auto-resize
            }
        },
        
        // ================================================================
        // Context Actions
        // ================================================================
        
        previewContext: function() {
            const contextData = this.getContextData();
            if (!contextData) {
                this.showToast('⚠️ No context selected');
                return;
            }
            
            const modal = document.createElement('div');
            modal.className = 'context-preview-modal';
            modal.innerHTML = `
                <div class="modal-overlay" onclick="this.parentElement.remove()"></div>
                <div class="modal-content" style="max-width: 800px;">
                    <div class="modal-header">
                        <h3>📊 Graph Context Preview</h3>
                        <button class="modal-close" onclick="this.closest('.context-preview-modal').remove()">×</button>
                    </div>
                    <div class="modal-body">
                        <div class="context-preview-stats">
                            <div class="preview-stat">
                                <span class="stat-number">${contextData.nodes.length}</span>
                                <span class="stat-label">Nodes</span>
                            </div>
                            <div class="preview-stat">
                                <span class="stat-number">${contextData.relationships.length}</span>
                                <span class="stat-label">Relationships</span>
                            </div>
                            <div class="preview-stat">
                                <span class="stat-number">${contextData.metadata.mode}</span>
                                <span class="stat-label">Mode</span>
                            </div>
                        </div>
                        <div class="context-preview-tabs">
                            <button class="preview-tab active" onclick="window.GraphChatIntegration.switchPreviewTab('formatted', this)">Formatted</button>
                            <button class="preview-tab" onclick="window.GraphChatIntegration.switchPreviewTab('json', this)">JSON</button>
                        </div>
                        <div class="context-preview-content">
                            <pre id="preview-formatted" class="preview-pane active">${this.escapeHtml(this.formatContextAsText(contextData))}</pre>
                            <pre id="preview-json" class="preview-pane" style="display: none;">${this.escapeHtml(JSON.stringify(contextData, null, 2))}</pre>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button class="modal-action-btn" onclick="window.GraphChatIntegration.copyContextToClipboard(); this.textContent='✅ Copied!'">
                            📋 Copy to Clipboard
                        </button>
                        <button class="modal-action-btn" onclick="window.GraphChatIntegration.insertContextInChat(); this.closest('.context-preview-modal').remove()">
                            💬 Insert in Chat
                        </button>
                    </div>
                </div>
            `;
            
            document.body.appendChild(modal);
        },
        
        switchPreviewTab: function(tab, button) {
            document.querySelectorAll('.preview-tab').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.preview-pane').forEach(p => p.style.display = 'none');
            
            button.classList.add('active');
            document.getElementById(`preview-${tab}`).style.display = 'block';
        },
        
        copyContextToClipboard: function() {
            const contextData = this.getContextData();
            if (!contextData) {
                this.showToast('⚠️ No context to copy');
                return;
            }
            
            const text = this.formatContextAsText(contextData);
            navigator.clipboard.writeText(text).then(() => {
                this.showToast('✅ Context copied to clipboard');
            });
        },
        
        insertContextInChat: function() {
            const contextData = this.getContextData();
            if (!contextData) return;
            
            const messageInput = document.getElementById('messageInput');
            if (messageInput) {
                messageInput.value = this.formatContextAsText(contextData);
                messageInput.focus();
            }
        },
        
        // ================================================================
        // Message Intercept - Auto-append context
        // ================================================================
        
        interceptMessage: function(originalMessage) {
            if (this.contextMode === 'none') {
                return originalMessage;
            }
            
            const contextData = this.getContextData();
            if (!contextData || contextData.nodes.length === 0) {
                return originalMessage;
            }
            
            // Add context footer
            const contextFooter = `\n\n---\n**Graph Context (${this.contextMode}):**\n${this.formatContextAsText(contextData)}`;
            
            return originalMessage + contextFooter;
        },
        
        // ================================================================
        // Utilities
        // ================================================================
        
        escapeHtml: function(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        },
        
        showToast: function(message) {
            const toast = document.createElement('div');
            toast.className = 'graph-context-toast';
            toast.textContent = message;
            toast.style.cssText = `
                position: fixed;
                bottom: 80px;
                right: 20px;
                background: #1e293b;
                color: #e2e8f0;
                padding: 12px 20px;
                border-radius: 6px;
                border: 1px solid #334155;
                box-shadow: 0 4px 12px rgba(0,0,0,0.3);
                z-index: 100000;
                animation: slideInRight 0.3s ease;
            `;
            
            document.body.appendChild(toast);
            
            setTimeout(() => {
                toast.style.animation = 'slideOutRight 0.3s ease';
                setTimeout(() => toast.remove(), 300);
            }, 3000);
        }
    };
    
    // ================================================================
    // CSS Styles
    // ================================================================
    
    const styles = `
    @keyframes slideInRight {
        from { transform: translateX(400px); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    
    @keyframes slideOutRight {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(400px); opacity: 0; }
    }
    
    .graph-context-panel {
        background: var(--panel-bg, #1e293b);
        border-bottom: 1px solid var(--border, #334155);
        transition: all 0.3s ease;
        max-height: 600px;
        overflow: hidden;
    }
    
    .graph-context-panel.collapsed {
        max-height: 48px;
    }
    
    .graph-context-panel.collapsed .context-panel-body {
        display: none;
    }
    
    .context-panel-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 12px 16px;
        cursor: pointer;
        transition: background 0.2s;
    }
    
    .context-panel-header:hover {
        background: var(--bg, #0f172a);
    }
    
    .context-panel-title {
        display: flex;
        align-items: center;
        gap: 10px;
        font-size: 14px;
        font-weight: 600;
        color: var(--text, #e2e8f0);
    }
    
    .context-panel-title svg {
        color: var(--accent, #3b82f6);
    }
    
    .context-badge {
        background: var(--accent, #3b82f6);
        color: white;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 600;
    }
    
    .context-toggle-btn {
        background: transparent;
        border: none;
        color: var(--text-muted, #94a3b8);
        cursor: pointer;
        padding: 4px;
        border-radius: 4px;
        transition: all 0.2s;
    }
    
    .context-toggle-btn:hover {
        background: var(--bg, #0f172a);
        color: var(--text, #e2e8f0);
    }
    
    .context-panel-body {
        padding: 0 16px 16px 16px;
        overflow-y: auto;
        max-height: 550px;
    }
    
    .context-section {
        margin-bottom: 16px;
        padding-bottom: 16px;
        border-bottom: 1px solid var(--border, #334155);
    }
    
    .context-section:last-child {
        border-bottom: none;
        margin-bottom: 0;
        padding-bottom: 0;
    }
    
    .context-label {
        display: block;
        font-size: 12px;
        font-weight: 600;
        color: var(--text-muted, #94a3b8);
        margin-bottom: 8px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .context-mode-buttons {
        display: flex;
        gap: 6px;
        flex-wrap: wrap;
    }
    
    .context-mode-btn {
        flex: 1;
        min-width: 70px;
        padding: 8px 12px;
        background: var(--bg, #0f172a);
        border: 1px solid var(--border, #334155);
        color: var(--text, #e2e8f0);
        border-radius: 6px;
        font-size: 12px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s;
    }
    
    .context-mode-btn:hover {
        border-color: var(--accent, #3b82f6);
        background: var(--panel-bg, #1e293b);
    }
    
    .context-mode-btn.active {
        background: var(--accent, #3b82f6);
        border-color: var(--accent, #3b82f6);
        color: white;
    }
    
    .context-checkbox {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px 0;
        cursor: pointer;
        color: var(--text, #e2e8f0);
        font-size: 13px;
    }
    
    .context-checkbox input[type="checkbox"] {
        width: 18px;
        height: 18px;
        cursor: pointer;
    }
    
    .context-stats {
        display: flex;
        gap: 16px;
    }
    
    .stat-item {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        padding: 12px;
        background: var(--bg, #0f172a);
        border-radius: 6px;
    }
    
    .stat-label {
        font-size: 11px;
        color: var(--text-muted, #94a3b8);
        text-transform: uppercase;
    }
    
    .stat-value {
        font-size: 20px;
        font-weight: 700;
        color: var(--accent, #3b82f6);
    }
    
    .selected-nodes-list {
        display: flex;
        flex-direction: column;
        gap: 6px;
        max-height: 200px;
        overflow-y: auto;
    }
    
    .selected-node-item {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px 12px;
        background: var(--bg, #0f172a);
        border: 1px solid var(--border, #334155);
        border-radius: 6px;
    }
    
    .selected-node-item.more-indicator {
        justify-content: center;
        font-size: 12px;
        color: var(--text-muted, #94a3b8);
        font-style: italic;
    }
    
    .node-color-dot {
        width: 12px;
        height: 12px;
        border-radius: 50%;
        flex-shrink: 0;
    }
    
    .node-label {
        flex: 1;
        font-size: 13px;
        color: var(--text, #e2e8f0);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    
    .node-remove-btn {
        background: transparent;
        border: none;
        color: var(--text-muted, #94a3b8);
        cursor: pointer;
        font-size: 18px;
        padding: 0 4px;
        border-radius: 4px;
        transition: all 0.2s;
    }
    
    .node-remove-btn:hover {
        background: var(--panel-bg, #1e293b);
        color: #ef4444;
    }
    
    .quick-queries {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
        gap: 6px;
    }
    
    .quick-query-btn {
        padding: 10px;
        background: var(--bg, #0f172a);
        border: 1px solid var(--border, #334155);
        color: var(--text, #e2e8f0);
        border-radius: 6px;
        font-size: 12px;
        cursor: pointer;
        transition: all 0.2s;
        text-align: left;
    }
    
    .quick-query-btn:hover {
        border-color: var(--accent, #3b82f6);
        background: var(--panel-bg, #1e293b);
    }
    
    .context-action-btn {
        width: 100%;
        padding: 10px;
        background: var(--accent, #3b82f6);
        border: none;
        color: white;
        border-radius: 6px;
        font-size: 13px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s;
        margin-top: 6px;
    }
    
    .context-action-btn:hover {
        background: var(--accent-hover, #2563eb);
    }
    
    .context-action-btn:first-child {
        background: var(--panel-bg, #1e293b);
        border: 1px solid var(--border, #334155);
        color: var(--text, #e2e8f0);
    }
    
    .context-action-btn:first-child:hover {
        border-color: var(--accent, #3b82f6);
    }
    
    /* Preview Modal */
    .context-preview-modal {
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        z-index: 100000;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    
    .context-preview-stats {
        display: flex;
        gap: 16px;
        margin-bottom: 20px;
    }
    
    .preview-stat {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        padding: 16px;
        background: var(--bg, #0f172a);
        border-radius: 8px;
    }
    
    .preview-stat .stat-number {
        font-size: 24px;
        font-weight: 700;
        color: var(--accent, #3b82f6);
    }
    
    .preview-stat .stat-label {
        font-size: 12px;
        color: var(--text-muted, #94a3b8);
        text-transform: uppercase;
    }
    
    .context-preview-tabs {
        display: flex;
        gap: 8px;
        margin-bottom: 12px;
        border-bottom: 1px solid var(--border, #334155);
    }
    
    .preview-tab {
        padding: 8px 16px;
        background: transparent;
        border: none;
        color: var(--text-muted, #94a3b8);
        cursor: pointer;
        font-size: 13px;
        font-weight: 600;
        border-bottom: 2px solid transparent;
        transition: all 0.2s;
    }
    
    .preview-tab:hover {
        color: var(--text, #e2e8f0);
    }
    
    .preview-tab.active {
        color: var(--accent, #3b82f6);
        border-bottom-color: var(--accent, #3b82f6);
    }
    
    .context-preview-content {
        position: relative;
        max-height: 400px;
        overflow-y: auto;
    }
    
    .preview-pane {
        padding: 16px;
        background: var(--bg, #0f172a);
        border: 1px solid var(--border, #334155);
        border-radius: 6px;
        font-size: 12px;
        line-height: 1.6;
        color: var(--text, #e2e8f0);
        white-space: pre-wrap;
        font-family: monospace;
    }
    
    .modal-footer {
        display: flex;
        gap: 8px;
        padding-top: 16px;
        border-top: 1px solid var(--border, #334155);
    }
    
    .modal-action-btn {
        flex: 1;
        padding: 10px;
        background: var(--accent, #3b82f6);
        border: none;
        color: white;
        border-radius: 6px;
        font-size: 13px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s;
    }
    
    .modal-action-btn:hover {
        background: var(--accent-hover, #2563eb);
    }
    `;
    
    // Inject styles
    if (!document.getElementById('graph-chat-integration-styles')) {
        const styleEl = document.createElement('style');
        styleEl.id = 'graph-chat-integration-styles';
        styleEl.textContent = styles;
        document.head.appendChild(styleEl);
    }
    
    console.log('✅ GraphChatIntegration module loaded');
})();