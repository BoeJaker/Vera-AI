/**
 * GraphToolExecutor Module - FIXED VERSION
 * Direct tool execution without AI intermediary
 * Executes tools immediately and displays results with auto-refresh
 */

(function() {
    'use strict';
    
    window.GraphToolExecutor = {
        
        apiBase: 'http://llm.int:8888',
        sessionId: null,              // FIXED: Added
        graphAddon: null,             // FIXED: Added
        availableTools: [],
        executionHistory: [],
        currentExecution: null,
        eventSource: null,            // FIXED: Added for SSE
        
        /**
         * Initialize the module
         */
        init: function(graphAddon, sessionId) {
            console.log('GraphToolExecutor.init called with session:', sessionId);
            this.graphAddon = graphAddon;
            this.sessionId = sessionId;
            
            this.loadTools();           // FIXED: Correct method name
            this.loadHistory();
            this.connectToUpdateStream(); // FIXED: Will work now
            
            console.log('GraphToolExecutor initialized for session:', sessionId);
        },
        
        /**
         * Load available tools from API - FIXED
         */
        loadTools: async function() {
            if (!this.sessionId) {
                console.error('No session ID available');
                return;
            }
            
            try {
                // FIXED: Use correct endpoint with session_id
                const response = await fetch(`${this.apiBase}/api/tools/${this.sessionId}/list`);
                if (response.ok) {
                    const data = await response.json();
                    this.availableTools = data.tools || [];
                    console.log('Loaded tools for direct execution:', this.availableTools.length);
                }
            } catch (e) {
                console.error('Failed to load tools:', e);
            }
        },
        
        /**
         * Connect to update stream - FIXED
         */
        connectToUpdateStream: function() {
            if (!this.sessionId) {
                console.warn('Cannot connect to update stream: no session ID');
                return;
            }
            
            if (this.eventSource) {
                this.eventSource.close();
            }
            
            const streamUrl = `${this.apiBase}/api/tools/${this.sessionId}/updates/stream`;
            console.log('Connecting to update stream:', streamUrl);
            
            this.eventSource = new EventSource(streamUrl);
            
            this.eventSource.addEventListener('graph_update', (event) => {
                const data = JSON.parse(event.data);
                console.log('Graph update received:', data);
                
                if (data.type === 'tool_execution') {
                    this.handleGraphUpdate(data);
                }
            });
            
            this.eventSource.onopen = () => {
                console.log('✓ Update stream connected');
            };
            
            this.eventSource.onerror = (error) => {
                console.error('Update stream error:', error);
                if (this.eventSource) {
                    this.eventSource.close();
                }
                // Reconnect after delay
                setTimeout(() => this.connectToUpdateStream(), 5000);
            };
        },

        handleGraphUpdate: function(updateData) {
            console.log('Handling graph update:', updateData);
            
            const message = `${updateData.tool_name} created ${updateData.created_nodes_count} nodes`;
            this.showUpdateToast(message);
            
            // Reload graph after small delay
            if (window.app && window.app.reloadGraph) {
                setTimeout(() => {
                    console.log('Reloading graph...');
                    window.app.reloadGraph();
                }, 1000);
            }
        },

        showUpdateToast: function(message) {
            // Remove existing toast
            const existing = document.querySelector('.graph-update-toast');
            if (existing) existing.remove();
            
            const toast = document.createElement('div');
            toast.className = 'graph-update-toast';
            toast.innerHTML = `
                <div style="display: flex; align-items: center; gap: 8px;">
                    <div style="width: 16px; height: 16px; border: 2px solid #334155; border-top-color: #60a5fa; border-radius: 50%; animation: spin 1s linear infinite;"></div>
                    <span>${this.escapeHtml(message)} - Updating graph...</span>
                </div>
            `;
            toast.style.cssText = `
                position: fixed; bottom: 20px; right: 20px; z-index: 10000;
                background: #1e293b; color: #e2e8f0; padding: 12px 20px;
                border-radius: 8px; border: 1px solid #60a5fa;
                box-shadow: 0 4px 12px rgba(96, 165, 250, 0.2);
            `;
            
            document.body.appendChild(toast);
            
            setTimeout(() => {
                toast.style.opacity = '0';
                toast.style.transition = 'opacity 0.3s';
                setTimeout(() => toast.remove(), 300);
            }, 3000);
        },
        
        /**
         * Show tool selector for direct execution
         */
        showToolSelector: function(contextNodes = null) {
            const panel = document.getElementById('property-panel');
            const content = document.getElementById('panel-content');
            
            if (!this.availableTools || this.availableTools.length === 0) {
                this.showLoadingState(panel, content);
                return;
            }
            
            const categories = this.groupToolsByCategory(this.availableTools);
            this._executionContext = contextNodes;
            
            content.innerHTML = `
                <div style="padding: 20px;">
                    <div class="section">
                        <div class="section-title">⚡ Direct Tool Execution</div>
                        <div style="color: #94a3b8; font-size: 13px; margin-top: 8px;">
                            Execute tools directly without AI assistance
                        </div>
                        
                        <div style="margin-top: 16px;">
                            <input type="text" id="tool-search" placeholder="Search tools..." 
                                style="width: 100%; padding: 10px; background: #1e293b; color: #e2e8f0; border: 1px solid #334155; border-radius: 6px;">
                        </div>
                        
                        <div style="max-height: 500px; overflow-y: auto; margin-top: 16px;" id="tools-container">
                            ${this.renderToolCategories(categories)}
                        </div>
                    </div>
                    
                    <div style="display: flex; gap: 8px; margin-top: 20px;">
                        <button onclick="window.GraphToolExecutor.showExecutionHistory()" style="
                            flex: 1; padding: 12px;
                            background: #334155; color: #e2e8f0; border: 1px solid #475569;
                            border-radius: 6px; cursor: pointer; font-weight: 600;
                        ">📜 History</button>
                        <button onclick="window.GraphAddon.closePanel()" style="
                            flex: 1; padding: 12px;
                            background: #334155; color: #e2e8f0; border: 1px solid #475569;
                            border-radius: 6px; cursor: pointer; font-weight: 600;
                        ">Close</button>
                    </div>
                </div>
            `;
            
            panel.style.display = 'flex';
            
            const searchInput = document.getElementById('tool-search');
            searchInput.addEventListener('input', (e) => this.filterTools(e.target.value));
            
            content.querySelectorAll('.tool-item').forEach(el => {
                el.addEventListener('click', () => {
                    const toolName = el.dataset.tool;
                    this.showToolConfiguration(toolName);
                });
            });
        },
        
        showLoadingState: function(panel, content) {
            content.innerHTML = `
                <div style="padding: 20px; text-align: center;">
                    <div class="section">
                        <div class="section-title">⚡ Direct Tool Execution</div>
                        <div style="color: #94a3b8; margin-top: 16px;">
                            <div style="margin-bottom: 12px;">Loading tools...</div>
                            <div style="margin: 20px auto; width: 40px; height: 40px; border: 3px solid #334155; border-top: 3px solid #3b82f6; border-radius: 50%; animation: spin 1s linear infinite;"></div>
                        </div>
                    </div>
                    <button onclick="window.GraphAddon.closePanel()" style="
                        width: 100%; padding: 12px; margin-top: 20px;
                        background: #334155; color: #e2e8f0; border: 1px solid #475569;
                        border-radius: 6px; cursor: pointer; font-weight: 600;
                    ">Cancel</button>
                </div>
            `;
            panel.style.display = 'flex';
            
            this.loadTools().then(() => {
                if (this.availableTools.length > 0) {
                    this.showToolSelector();
                }
            });
        },
        
        groupToolsByCategory: function(tools) {
            const categories = {};
            tools.forEach(tool => {
                const cat = tool.category || 'Other';
                if (!categories[cat]) categories[cat] = [];
                categories[cat].push(tool);
            });
            return categories;
        },
        
        renderToolCategories: function(categories) {
            return Object.keys(categories).sort().map(cat => `
                <div class="tool-category" style="background: #0f172a; padding: 12px; border-radius: 6px; border: 1px solid #1e293b; margin-bottom: 12px;">
                    <div style="color: #60a5fa; font-size: 12px; font-weight: 600; margin-bottom: 8px;">${this.escapeHtml(cat)}</div>
                    ${categories[cat].map(tool => `
                        <div class="tool-item" data-tool="${this.escapeHtml(tool.name)}" 
                            style="padding: 10px; margin: 4px 0; background: #1e293b; border-radius: 4px; cursor: pointer; transition: all 0.15s;"
                            onmouseover="this.style.background='#334155'" onmouseout="this.style.background='#1e293b'">
                            <div style="font-weight: 600; color: #e2e8f0;">${this.escapeHtml(tool.name)}</div>
                            <div style="font-size: 11px; color: #94a3b8; margin-top: 2px;">${this.escapeHtml(tool.description || 'No description')}</div>
                        </div>
                    `).join('')}
                </div>
            `).join('');
        },
        
        filterTools: function(query) {
            const lowerQuery = query.toLowerCase();
            document.querySelectorAll('.tool-category').forEach(catEl => {
                let hasVisibleTools = false;
                catEl.querySelectorAll('.tool-item').forEach(toolEl => {
                    const toolName = toolEl.dataset.tool.toLowerCase();
                    const toolDesc = toolEl.textContent.toLowerCase();
                    const matches = toolName.includes(lowerQuery) || toolDesc.includes(lowerQuery);
                    toolEl.style.display = matches ? 'block' : 'none';
                    if (matches) hasVisibleTools = true;
                });
                catEl.style.display = hasVisibleTools ? 'block' : 'none';
            });
        },
        
        showToolConfiguration: function(toolName) {
            const tool = this.availableTools.find(t => t.name === toolName);
            if (!tool) return;
            
            const panel = document.getElementById('property-panel');
            const content = document.getElementById('panel-content');
            
            const allNodes = network.body.data.nodes.get();
            const selectedNodes = network.getSelectedNodes();
            const visibleNodes = allNodes.filter(n => !n.hidden);
            
            const paramInputs = this.buildParameterInputs(tool);
            
            content.innerHTML = `
                <div style="padding: 20px;">
                    <div class="section">
                        <div class="section-title">⚡ ${this.escapeHtml(toolName)}</div>
                        <div style="color: #94a3b8; font-size: 13px; margin-bottom: 16px;">
                            ${this.escapeHtml(tool.description || '')}
                        </div>
                        
                        <div style="background: #0f172a; padding: 16px; border-radius: 8px; border: 1px solid #1e293b; margin-bottom: 16px;">
                            <label style="display: block; color: #94a3b8; font-size: 13px; margin-bottom: 8px; font-weight: 600;">Execution Context</label>
                            <select id="exec-context" style="width: 100%; padding: 10px; background: #1e293b; color: #e2e8f0; border: 1px solid #334155; border-radius: 6px; margin-bottom: 12px;">
                                <option value="entire">Entire Graph (${allNodes.length} nodes)</option>
                                <option value="visible">Visible Nodes (${visibleNodes.length})</option>
                                <option value="selected" ${selectedNodes.length > 0 ? '' : 'disabled'}>Selected Nodes (${selectedNodes.length})</option>
                                <option value="custom">Custom Node List</option>
                            </select>
                            
                            <div id="custom-nodes-input" style="display: none;">
                                <label style="display: block; color: #94a3b8; font-size: 12px; margin-bottom: 4px;">Node IDs (comma-separated)</label>
                                <input type="text" id="custom-node-ids" placeholder="node1, node2, node3..." 
                                    style="width: 100%; padding: 8px; background: #1e293b; color: #e2e8f0; border: 1px solid #334155; border-radius: 4px;">
                            </div>
                        </div>
                        
                        ${paramInputs.length > 0 ? `
                            <div style="background: #0f172a; padding: 16px; border-radius: 8px; border: 1px solid #1e293b; margin-bottom: 16px;">
                                <div style="color: #94a3b8; font-size: 13px; margin-bottom: 12px; font-weight: 600;">Tool Parameters</div>
                                ${paramInputs.join('')}
                            </div>
                        ` : `
                            <div style="background: #0f172a; padding: 12px; border-radius: 8px; border: 1px solid #1e293b; margin-bottom: 16px; text-align: center; color: #64748b; font-size: 12px;">
                                This tool has no configurable parameters
                            </div>
                        `}
                        
                        <div style="background: #0f172a; padding: 16px; border-radius: 8px; border: 1px solid #1e293b; margin-bottom: 16px;">
                            <div style="color: #94a3b8; font-size: 13px; margin-bottom: 12px; font-weight: 600;">Execution Options</div>
                            <label style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px; cursor: pointer;">
                                <input type="checkbox" id="opt-update-graph" checked>
                                <span style="color: #e2e8f0; font-size: 13px;">Auto-refresh graph with results</span>
                            </label>
                            <label style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px; cursor: pointer;">
                                <input type="checkbox" id="opt-show-results">
                                <span style="color: #e2e8f0; font-size: 13px;">Show detailed results</span>
                            </label>
                            <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                                <input type="checkbox" id="opt-save-history" checked>
                                <span style="color: #e2e8f0; font-size: 13px;">Save to execution history</span>
                            </label>
                        </div>
                        
                        <div style="background: rgba(59, 130, 246, 0.1); padding: 12px; border-radius: 6px; border: 1px solid rgba(59, 130, 246, 0.2);">
                            <div style="color: #60a5fa; font-size: 11px; font-weight: 600; margin-bottom: 4px;">ℹ️ Direct Execution</div>
                            <div style="color: #94a3b8; font-size: 11px; line-height: 1.4;">
                                This tool will execute directly on the graph data without AI assistance. Results will be processed immediately.
                            </div>
                        </div>
                    </div>
                    
                    <div style="display: flex; gap: 8px; margin-top: 20px;">
                        <button onclick="window.GraphToolExecutor.executeTool('${this.escapeHtml(toolName)}')" style="
                            flex: 1; padding: 12px;
                            background: #3b82f6; color: white; border: none;
                            border-radius: 6px; cursor: pointer; font-weight: 600;
                        ">▶ Execute Now</button>
                        <button onclick="window.GraphToolExecutor.showToolSelector()" style="
                            padding: 12px 24px;
                            background: #334155; color: #e2e8f0; border: 1px solid #475569;
                            border-radius: 6px; cursor: pointer; font-weight: 600;
                        ">← Back</button>
                    </div>
                </div>
            `;
            
            panel.style.display = 'flex';
            
            document.getElementById('exec-context').addEventListener('change', (e) => {
                const customInput = document.getElementById('custom-nodes-input');
                customInput.style.display = e.target.value === 'custom' ? 'block' : 'none';
            });
        },
        
        buildParameterInputs: function(tool) {
            if (!tool.parameters || Object.keys(tool.parameters).length === 0) {
                return [];
            }
            
            return Object.entries(tool.parameters).map(([paramName, paramDef]) => {
                const isRequired = paramDef.required || false;
                const paramType = paramDef.type || 'string';
                const paramDesc = paramDef.description || '';
                const defaultValue = paramDef.default !== undefined ? paramDef.default : '';
                
                let inputHtml = '';
                
                switch (paramType) {
                    case 'boolean':
                        inputHtml = `
                            <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                                <input type="checkbox" id="param-${paramName}" ${defaultValue ? 'checked' : ''}>
                                <span style="color: #e2e8f0;">${this.escapeHtml(paramName)} ${isRequired ? '<span style="color: #f87171;">*</span>' : ''}</span>
                            </label>
                        `;
                        break;
                        
                    case 'number':
                    case 'integer':
                        inputHtml = `
                            <label style="display: block; color: #94a3b8; font-size: 12px; margin-bottom: 4px;">
                                ${this.escapeHtml(paramName)} ${isRequired ? '<span style="color: #f87171;">*</span>' : ''}
                            </label>
                            <input type="number" id="param-${paramName}" value="${defaultValue}" 
                                placeholder="${this.escapeHtml(paramDesc)}"
                                style="width: 100%; padding: 8px; background: #1e293b; color: #e2e8f0; border: 1px solid #334155; border-radius: 4px;">
                        `;
                        break;
                        
                    case 'array':
                        inputHtml = `
                            <label style="display: block; color: #94a3b8; font-size: 12px; margin-bottom: 4px;">
                                ${this.escapeHtml(paramName)} ${isRequired ? '<span style="color: #f87171;">*</span>' : ''}
                            </label>
                            <input type="text" id="param-${paramName}" value="${defaultValue}" 
                                placeholder="Comma-separated values"
                                style="width: 100%; padding: 8px; background: #1e293b; color: #e2e8f0; border: 1px solid #334155; border-radius: 4px;">
                            <div style="font-size: 10px; color: #64748b; margin-top: 2px;">Enter values separated by commas</div>
                        `;
                        break;
                        
                    default:
                        inputHtml = `
                            <label style="display: block; color: #94a3b8; font-size: 12px; margin-bottom: 4px;">
                                ${this.escapeHtml(paramName)} ${isRequired ? '<span style="color: #f87171;">*</span>' : ''}
                            </label>
                            <input type="text" id="param-${paramName}" value="${defaultValue}" 
                                placeholder="${this.escapeHtml(paramDesc)}"
                                style="width: 100%; padding: 8px; background: #1e293b; color: #e2e8f0; border: 1px solid #334155; border-radius: 4px;">
                        `;
                }
                
                return `
                    <div style="margin-bottom: 12px;">
                        ${inputHtml}
                        ${paramDesc ? `<div style="font-size: 10px; color: #64748b; margin-top: 2px;">${this.escapeHtml(paramDesc)}</div>` : ''}
                    </div>
                `;
            });
        },
        
        /**
         * Execute tool directly - FIXED
         */
        executeTool: async function(toolName) {
            const tool = this.availableTools.find(t => t.name === toolName);
            if (!tool) return;
            
            const context = document.getElementById('exec-context').value;
            const updateGraph = document.getElementById('opt-update-graph').checked;
            const showResults = document.getElementById('opt-show-results').checked;
            const saveHistory = document.getElementById('opt-save-history').checked;
            
            let nodes = this.getNodesForContext(context);
            const params = this.collectParameters(tool);
            
            const execution = {
                tool: toolName,
                context: context,
                nodeCount: nodes.length,
                parameters: params,
                timestamp: new Date().toISOString(),
                status: 'running'
            };
            
            this.currentExecution = execution;
            this.showExecutionProgress(toolName);
            
            try {
                // FIXED: Use correct endpoint with session_id
                const response = await fetch(`${this.apiBase}/api/tools/${this.sessionId}/execute`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        tool_name: toolName,
                        tool_input: params,
                        node_id: nodes.length > 0 ? nodes[0].id : null,
                        link_results: true
                    })
                });
                
                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({}));
                    throw new Error(errorData.detail || `HTTP ${response.status}`);
                }
                
                const result = await response.json();
                
                execution.status = 'completed';
                execution.result = result;
                execution.duration = Date.now() - new Date(execution.timestamp).getTime();
                
                if (saveHistory) {
                    this.addToHistory(execution);
                }
                
                // FIXED: Auto-refresh graph if execution created nodes
                if (updateGraph && result.graph_context && result.graph_context.execution_node_id) {
                    await this.refreshGraphAfterExecution(result.graph_context.execution_node_id);
                }
                
                if (showResults) {
                    this.showExecutionResults(execution);
                } else {
                    this.showToast(`Tool executed successfully`);
                    if (window.GraphAddon && window.GraphAddon.closePanel) {
                        window.GraphAddon.closePanel();
                    }
                }
                
            } catch (error) {
                execution.status = 'failed';
                execution.error = error.message;
                this.showExecutionError(toolName, error);
            }
        },
        
        /**
         * Refresh graph after tool execution - NEW
         */
        refreshGraphAfterExecution: async function(executionNodeId) {
            console.log('Refreshing graph after execution:', executionNodeId);
            
            try {
                // Fetch only newly created nodes
                const response = await fetch(
                    `${this.apiBase}/api/tools/${this.sessionId}/execution/${executionNodeId}/created-nodes`
                );
                
                if (!response.ok) {
                    console.warn('Created-nodes endpoint not available, falling back to full reload');
                    if (window.app && window.app.reloadGraph) {
                        await window.app.reloadGraph();
                    }
                    return;
                }
                
                const data = await response.json();
                
                if (!data.nodes || data.nodes.length === 0) {
                    console.log('No new nodes to add, reloading graph to show execution nodes');
                    if (window.app && window.app.reloadGraph) {
                        await window.app.reloadGraph();
                    }
                    return;
                }
                
                console.log(`Adding ${data.nodes.length} new nodes from execution`);
                
                // Use GraphDataLoader for incremental update if available
                if (window.GraphDataLoader) {
                    await window.GraphDataLoader.loadData(data.nodes, data.edges, {
                        replace: false,     // Incremental add
                        fit: true,          // Focus on new nodes
                        animate: true,      // Smooth animation
                        focusNodes: data.nodes.map(n => n.id),
                        applyTheme: true,
                        updateGraphAddon: true
                    });
                    
                    this.showToast(`Added ${data.nodes.length} nodes to graph`);
                } else {
                    // Fallback to full reload
                    if (window.app && window.app.reloadGraph) {
                        await window.app.reloadGraph();
                    }
                }
                window.app.loadGraph();
                
            } catch (error) {
                window.app.loadGraph();
                console.error('Failed to load new nodes:', error);
                // Fallback to full reload
                if (window.app && window.app.reloadGraph) {
                    await window.app.reloadGraph();
                }
            }
        },
        
        getNodesForContext: function(context) {
            const allNodes = network.body.data.nodes.get();
            
            switch (context) {
                case 'selected':
                    const selectedIds = network.getSelectedNodes();
                    return allNodes.filter(n => selectedIds.includes(n.id));
                    
                case 'visible':
                    return allNodes.filter(n => !n.hidden);
                    
                case 'custom':
                    const customIds = document.getElementById('custom-node-ids').value
                        .split(',')
                        .map(id => id.trim())
                        .filter(id => id);
                    return allNodes.filter(n => customIds.includes(n.id));
                    
                default:
                    return allNodes;
            }
        },
        
        getRelevantEdges: function(nodes) {
            const nodeIds = new Set(nodes.map(n => n.id));
            const allEdges = network.body.data.edges.get();
            
            return allEdges
                .filter(e => nodeIds.has(e.from) && nodeIds.has(e.to))
                .map(e => ({
                    id: e.id,
                    from: e.from,
                    to: e.to,
                    label: e.label,
                    properties: e.properties || {}
                }));
        },
        
        collectParameters: function(tool) {
            const params = {};
            
            if (!tool.parameters) return params;
            
            Object.entries(tool.parameters).forEach(([paramName, paramDef]) => {
                const input = document.getElementById(`param-${paramName}`);
                if (!input) return;
                
                const paramType = paramDef.type || 'string';
                
                switch (paramType) {
                    case 'boolean':
                        params[paramName] = input.checked;
                        break;
                    case 'number':
                    case 'integer':
                        params[paramName] = parseFloat(input.value) || 0;
                        break;
                    case 'array':
                        params[paramName] = input.value.split(',').map(v => v.trim()).filter(v => v);
                        break;
                    default:
                        params[paramName] = input.value;
                }
            });
            
            return params;
        },
        
        showExecutionProgress: function(toolName) {
            const panel = document.getElementById('property-panel');
            const content = document.getElementById('panel-content');
            
            content.innerHTML = `
                <div style="padding: 40px; text-align: center;">
                    <div style="margin: 20px auto; width: 60px; height: 60px; border: 4px solid #334155; border-top: 4px solid #3b82f6; border-radius: 50%; animation: spin 1s linear infinite;"></div>
                    <div style="color: #e2e8f0; font-size: 16px; font-weight: 600; margin-top: 20px;">
                        Executing: ${this.escapeHtml(toolName)}
                    </div>
                    <div style="color: #94a3b8; font-size: 13px; margin-top: 8px;">
                        Please wait...
                    </div>
                </div>
            `;
        },
        
        showExecutionResults: function(execution) {
            const panel = document.getElementById('property-panel');
            const content = document.getElementById('panel-content');
            
            const result = execution.result || {};
            window.app.loadGraph();
            content.innerHTML = `
                <div style="padding: 20px;">
                    <div class="section">
                        <div class="section-title">✅ Execution Complete</div>
                        <div style="color: #94a3b8; font-size: 13px; margin-bottom: 16px;">
                            ${this.escapeHtml(execution.tool)} - ${execution.duration}ms
                        </div>
                        
                        <div style="background: #0f172a; padding: 16px; border-radius: 8px; border: 1px solid #1e293b; margin-bottom: 16px;">
                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
                                <div>
                                    <div style="color: #94a3b8; font-size: 11px;">Status</div>
                                    <div style="color: #10b981; font-size: 20px; font-weight: 600;">Success</div>
                                </div>
                                <div>
                                    <div style="color: #94a3b8; font-size: 11px;">Duration</div>
                                    <div style="color: #e2e8f0; font-size: 20px; font-weight: 600;">${execution.duration}ms</div>
                                </div>
                            </div>
                        </div>
                        
                        ${result.output ? `
                            <div style="background: #0f172a; padding: 16px; border-radius: 8px; border: 1px solid #1e293b; margin-bottom: 16px;">
                                <div style="color: #94a3b8; font-size: 12px; font-weight: 600; margin-bottom: 8px;">Output</div>
                                <div style="color: #e2e8f0; font-size: 13px; max-height: 200px; overflow-y: auto;">${this.escapeHtml(result.output.substring(0, 500))}${result.output.length > 500 ? '...' : ''}</div>
                            </div>
                        ` : ''}
                        
                        ${result.graph_context && result.graph_context.enabled ? `
                            <div style="background: #0f172a; padding: 16px; border-radius: 8px; border: 1px solid #1e293b; margin-bottom: 16px;">
                                <div style="color: #60a5fa; font-size: 12px; font-weight: 600; margin-bottom: 8px;">🔗 Graph Context</div>
                                <div style="color: #94a3b8; font-size: 11px;">
                                    Created ${result.graph_context.created_nodes_count || 0} nodes
                                </div>
                            </div>
                        ` : ''}
                    </div>
                    
                    <div style="display: flex; gap: 8px; margin-top: 20px;">
                        <button onclick="window.GraphToolExecutor.showToolSelector()" style="
                            flex: 1; padding: 12px;
                            background: #3b82f6; color: white; border: none;
                            border-radius: 6px; cursor: pointer; font-weight: 600;
                        ">Run Another</button>
                        <button onclick="window.GraphAddon.closePanel()" style="
                            padding: 12px 24px;
                            background: #334155; color: #e2e8f0; border: 1px solid #475569;
                            border-radius: 6px; cursor: pointer; font-weight: 600;
                        ">Close</button>
                    </div>
                </div>
            `;
            
            panel.style.display = 'flex';
        },
        
        showExecutionError: function(toolName, error) {
            const panel = document.getElementById('property-panel');
            const content = document.getElementById('panel-content');
            
            content.innerHTML = `
                <div style="padding: 20px;">
                    <div class="section">
                        <div class="section-title">❌ Execution Failed</div>
                        <div style="color: #94a3b8; font-size: 13px; margin-bottom: 16px;">
                            ${this.escapeHtml(toolName)}
                        </div>
                        
                        <div style="background: rgba(239, 68, 68, 0.1); padding: 16px; border-radius: 8px; border: 1px solid rgba(239, 68, 68, 0.2); margin-bottom: 16px;">
                            <div style="color: #f87171; font-size: 13px; font-weight: 600; margin-bottom: 8px;">Error</div>
                            <div style="color: #fca5a5; font-size: 12px;">${this.escapeHtml(error.message || error)}</div>
                        </div>
                    </div>
                    
                    <div style="display: flex; gap: 8px; margin-top: 20px;">
                        <button onclick="window.GraphToolExecutor.showToolConfiguration('${this.escapeHtml(toolName)}')" style="
                            flex: 1; padding: 12px;
                            background: #3b82f6; color: white; border: none;
                            border-radius: 6px; cursor: pointer; font-weight: 600;
                        ">Try Again</button>
                        <button onclick="window.GraphToolExecutor.showToolSelector()" style="
                            padding: 12px 24px;
                            background: #334155; color: #e2e8f0; border: 1px solid #475569;
                            border-radius: 6px; cursor: pointer; font-weight: 600;
                        ">← Back</button>
                    </div>
                </div>
            `;
            
            panel.style.display = 'flex';
        },
        
        showExecutionHistory: function() {
            const panel = document.getElementById('property-panel');
            const content = document.getElementById('panel-content');
            
            if (this.executionHistory.length === 0) {
                content.innerHTML = `
                    <div style="padding: 20px; text-align: center;">
                        <div class="section-title">📜 Execution History</div>
                        <div style="color: #64748b; margin-top: 40px;">No executions yet</div>
                        <button onclick="window.GraphToolExecutor.showToolSelector()" style="
                            padding: 12px 24px; margin-top: 20px;
                            background: #334155; color: #e2e8f0; border: 1px solid #475569;
                            border-radius: 6px; cursor: pointer; font-weight: 600;
                        ">← Back</button>
                    </div>
                `;
                panel.style.display = 'flex';
                return;
            }
            
            content.innerHTML = `
                <div style="padding: 20px;">
                    <div class="section">
                        <div class="section-title">📜 Execution History</div>
                        
                        <div style="max-height: 500px; overflow-y: auto; margin-top: 16px;">
                            ${this.executionHistory.slice().reverse().map((exec, idx) => `
                                <div class="history-item" style="background: #0f172a; padding: 12px; border-radius: 6px; border: 1px solid #1e293b; margin-bottom: 8px; cursor: pointer; transition: all 0.15s;"
                                    onmouseover="this.style.background='#1e293b'" onmouseout="this.style.background='#0f172a'"
                                    onclick="window.GraphToolExecutor.viewHistoryItem(${this.executionHistory.length - 1 - idx})">
                                    <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 8px;">
                                        <div style="font-weight: 600; color: #e2e8f0;">${this.escapeHtml(exec.tool)}</div>
                                        <div style="font-size: 11px; color: ${exec.status === 'completed' ? '#4ade80' : exec.status === 'failed' ? '#f87171' : '#94a3b8'};">
                                            ${exec.status === 'completed' ? '✅' : exec.status === 'failed' ? '❌' : '⏳'} ${exec.status}
                                        </div>
                                    </div>
                                    <div style="font-size: 11px; color: #64748b;">
                                        ${new Date(exec.timestamp).toLocaleString()} • ${exec.duration || '?'}ms
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                    
                    <div style="display: flex; gap: 8px; margin-top: 20px;">
                        <button onclick="window.GraphToolExecutor.clearHistory()" style="
                            flex: 1; padding: 12px;
                            background: #991b1b; color: white; border: none;
                            border-radius: 6px; cursor: pointer; font-weight: 600;
                        ">Clear History</button>
                        <button onclick="window.GraphToolExecutor.showToolSelector()" style="
                            flex: 1; padding: 12px;
                            background: #334155; color: #e2e8f0; border: 1px solid #475569;
                            border-radius: 6px; cursor: pointer; font-weight: 600;
                        ">← Back</button>
                    </div>
                </div>
            `;
            
            panel.style.display = 'flex';
        },
        
        viewHistoryItem: function(index) {
            const execution = this.executionHistory[index];
            if (!execution) return;
            this.showExecutionResults(execution);
        },
        
        addToHistory: function(execution) {
            this.executionHistory.push(execution);
            if (this.executionHistory.length > 50) {
                this.executionHistory = this.executionHistory.slice(-50);
            }
            this.saveHistory();
        },
        
        clearHistory: function() {
            if (confirm('Clear all execution history?')) {
                this.executionHistory = [];
                this.saveHistory();
                this.showExecutionHistory();
            }
        },
        
        saveHistory: function() {
            try {
                localStorage.setItem('tool_execution_history', JSON.stringify(this.executionHistory));
            } catch (e) {
                console.warn('Failed to save history:', e);
            }
        },
        
        loadHistory: function() {
            try {
                const saved = localStorage.getItem('tool_execution_history');
                if (saved) {
                    this.executionHistory = JSON.parse(saved);
                }
            } catch (e) {
                console.warn('Failed to load history:', e);
            }
        },
        
        showToast: function(message, type = 'success') {
            document.querySelectorAll('.tool-executor-toast').forEach(t => t.remove());
            
            const toast = document.createElement('div');
            toast.className = 'tool-executor-toast';
            toast.textContent = message;
            toast.style.cssText = `
                position: fixed; top: 20px; right: 20px; z-index: 10000;
                background: ${type === 'error' ? '#991b1b' : '#1e293b'}; 
                color: #e2e8f0; padding: 12px 20px;
                border-radius: 6px; border: 1px solid ${type === 'error' ? '#dc2626' : '#334155'};
                box-shadow: 0 4px 12px rgba(0,0,0,0.3);
                transition: opacity 0.3s;
            `;
            document.body.appendChild(toast);
            
            setTimeout(() => {
                toast.style.opacity = '0';
                setTimeout(() => toast.remove(), 300);
            }, 3000);
        },
        
        escapeHtml: function(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
    };
    
    // Don't auto-initialize - wait for explicit call with session ID
    console.log('GraphToolExecutor module loaded (awaiting init with session ID)');
    
})();