/**
 * GraphToolExecutor Module
 * Direct tool execution without AI intermediary
 * Executes tools immediately and displays results
 */

(function() {
    'use strict';
    
    window.GraphToolExecutor = {
        
        apiBase: 'http://llm.int:8888',
        availableTools: [],
        executionHistory: [],
        currentExecution: null,
        
        /**
         * Initialize the module
         */
        init: function() {
            console.log('GraphToolExecutor initialized');
            this.loadTools();
            this.loadHistory();
        },
        
        /**
         * Load available tools from API
         */
        loadTools: async function() {
            try {
                const response = await fetch(`${this.apiBase}/api/tools/list`);
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
         * Show tool selector for direct execution
         */
        showToolSelector: function(contextNodes = null) {
            const panel = document.getElementById('property-panel');
            const content = document.getElementById('panel-content');
            
            if (!this.availableTools || this.availableTools.length === 0) {
                this.showLoadingState(panel, content);
                return;
            }
            
            // Group tools by category
            const categories = this.groupToolsByCategory(this.availableTools);
            
            // Store context for later use
            this._executionContext = contextNodes;
            
            content.innerHTML = `
                <div style="padding: 20px;">
                    <div class="section">
                        <div class="section-title">⚡ Direct Tool Execution</div>
                        <div style="color: #94a3b8; font-size: 13px; margin-top: 8px;">
                            Execute tools directly without AI assistance
                        </div>
                        
                        <!-- Search -->
                        <div style="margin-top: 16px;">
                            <input type="text" id="tool-search" placeholder="Search tools..." 
                                style="width: 100%; padding: 10px; background: #1e293b; color: #e2e8f0; border: 1px solid #334155; border-radius: 6px;">
                        </div>
                        
                        <!-- Tools by category -->
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
            
            // Setup search
            const searchInput = document.getElementById('tool-search');
            searchInput.addEventListener('input', (e) => this.filterTools(e.target.value));
            
            // Setup tool click handlers
            content.querySelectorAll('.tool-item').forEach(el => {
                el.addEventListener('click', () => {
                    const toolName = el.dataset.tool;
                    this.showToolConfiguration(toolName);
                });
            });
        },
        
        /**
         * Show loading state
         */
        showLoadingState: function(panel, content) {
            content.innerHTML = `
                <div style="padding: 20px; text-align: center;">
                    <div class="section">
                        <div class="section-title">⚡ Direct Tool Execution</div>
                        <div style="color: #94a3b8; margin-top: 16px;">
                            <div style="margin-bottom: 12px;">Loading tools...</div>
                            <div class="spinner" style="margin: 20px auto; width: 40px; height: 40px; border: 3px solid #334155; border-top: 3px solid #3b82f6; border-radius: 50%; animation: spin 1s linear infinite;"></div>
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
        
        /**
         * Group tools by category
         */
        groupToolsByCategory: function(tools) {
            const categories = {};
            tools.forEach(tool => {
                const cat = tool.category || 'Other';
                if (!categories[cat]) categories[cat] = [];
                categories[cat].push(tool);
            });
            return categories;
        },
        
        /**
         * Render tool categories
         */
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
                            ${tool.parameters ? `<div style="font-size: 10px; color: #64748b; margin-top: 4px;">📋 ${Object.keys(tool.parameters).length} parameters</div>` : ''}
                        </div>
                    `).join('')}
                </div>
            `).join('');
        },
        
        /**
         * Filter tools by search
         */
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
        
        /**
         * Show tool configuration dialog
         */
        showToolConfiguration: function(toolName) {
            const tool = this.availableTools.find(t => t.name === toolName);
            if (!tool) return;
            
            const panel = document.getElementById('property-panel');
            const content = document.getElementById('panel-content');
            
            // Get graph context
            const allNodes = network.body.data.nodes.get();
            const selectedNodes = network.getSelectedNodes();
            const visibleNodes = allNodes.filter(n => !n.hidden);
            
            // Build parameter inputs
            const paramInputs = this.buildParameterInputs(tool);
            
            content.innerHTML = `
                <div style="padding: 20px;">
                    <div class="section">
                        <div class="section-title">⚡ ${this.escapeHtml(toolName)}</div>
                        <div style="color: #94a3b8; font-size: 13px; margin-bottom: 16px;">
                            ${this.escapeHtml(tool.description || '')}
                        </div>
                        
                        <!-- Context Selection -->
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
                        
                        <!-- Tool Parameters -->
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
                        
                        <!-- Execution Options -->
                        <div style="background: #0f172a; padding: 16px; border-radius: 8px; border: 1px solid #1e293b; margin-bottom: 16px;">
                            <div style="color: #94a3b8; font-size: 13px; margin-bottom: 12px; font-weight: 600;">Execution Options</div>
                            <label style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px; cursor: pointer;">
                                <input type="checkbox" id="opt-update-graph" checked>
                                <span style="color: #e2e8f0; font-size: 13px;">Update graph with results</span>
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
                        
                        <!-- Info -->
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
            
            // Setup context selector
            document.getElementById('exec-context').addEventListener('change', (e) => {
                const customInput = document.getElementById('custom-nodes-input');
                customInput.style.display = e.target.value === 'custom' ? 'block' : 'none';
            });
        },
        
        /**
         * Build parameter inputs for tool
         */
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
                        
                    default: // string
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
         * Execute tool directly
         */
        executeTool: async function(toolName) {
            const tool = this.availableTools.find(t => t.name === toolName);
            if (!tool) return;
            
            // Get context
            const context = document.getElementById('exec-context').value;
            const updateGraph = document.getElementById('opt-update-graph').checked;
            const showResults = document.getElementById('opt-show-results').checked;
            const saveHistory = document.getElementById('opt-save-history').checked;
            
            // Get nodes based on context
            let nodes = this.getNodesForContext(context);
            
            // Get parameters
            const params = this.collectParameters(tool);
            
            // Prepare execution
            const execution = {
                tool: toolName,
                context: context,
                nodeCount: nodes.length,
                parameters: params,
                timestamp: new Date().toISOString(),
                status: 'running'
            };
            
            this.currentExecution = execution;
            
            // Show execution progress
            this.showExecutionProgress(toolName);
            
            try {
                // Build request payload
                const payload = {
                    tool: toolName,
                    nodes: nodes.map(n => ({
                        id: n.id,
                        label: n.label,
                        properties: n.properties || {}
                    })),
                    edges: this.getRelevantEdges(nodes),
                    parameters: params
                };
                
                // Execute tool
                const response = await fetch(`${this.apiBase}/api/tools/execute`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                
                const result = await response.json();
                
                execution.status = 'completed';
                execution.result = result;
                execution.duration = Date.now() - new Date(execution.timestamp).getTime();
                
                // Save to history
                if (saveHistory) {
                    this.addToHistory(execution);
                }
                
                // Process results
                if (updateGraph && result.nodes) {
                    this.updateGraphWithResults(result);
                }
                
                // Show results
                if (showResults || !updateGraph) {
                    this.showExecutionResults(execution);
                } else {
                    this.showToast(`Tool executed: ${result.nodes?.length || 0} nodes, ${result.edges?.length || 0} edges`);
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
         * Get nodes for execution context
         */
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
                    
                default: // entire
                    return allNodes;
            }
        },
        
        /**
         * Get relevant edges for nodes
         */
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
        
        /**
         * Collect parameters from form
         */
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
        
        /**
         * Show execution progress
         */
        showExecutionProgress: function(toolName) {
            const panel = document.getElementById('property-panel');
            const content = document.getElementById('panel-content');
            
            content.innerHTML = `
                <div style="padding: 40px; text-align: center;">
                    <div class="spinner" style="margin: 20px auto; width: 60px; height: 60px; border: 4px solid #334155; border-top: 4px solid #3b82f6; border-radius: 50%; animation: spin 1s linear infinite;"></div>
                    <div style="color: #e2e8f0; font-size: 16px; font-weight: 600; margin-top: 20px;">
                        Executing: ${this.escapeHtml(toolName)}
                    </div>
                    <div style="color: #94a3b8; font-size: 13px; margin-top: 8px;">
                        Please wait...
                    </div>
                </div>
            `;
        },
        
        /**
         * Show execution results
         */
        showExecutionResults: function(execution) {
            const panel = document.getElementById('property-panel');
            const content = document.getElementById('panel-content');
            
            const result = execution.result || {};
            
            content.innerHTML = `
                <div style="padding: 20px;">
                    <div class="section">
                        <div class="section-title">✅ Execution Complete</div>
                        <div style="color: #94a3b8; font-size: 13px; margin-bottom: 16px;">
                            ${this.escapeHtml(execution.tool)} - ${execution.duration}ms
                        </div>
                        
                        <!-- Summary -->
                        <div style="background: #0f172a; padding: 16px; border-radius: 8px; border: 1px solid #1e293b; margin-bottom: 16px;">
                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
                                <div>
                                    <div style="color: #94a3b8; font-size: 11px;">Input Nodes</div>
                                    <div style="color: #e2e8f0; font-size: 20px; font-weight: 600;">${execution.nodeCount}</div>
                                </div>
                                <div>
                                    <div style="color: #94a3b8; font-size: 11px;">Output Nodes</div>
                                    <div style="color: #e2e8f0; font-size: 20px; font-weight: 600;">${result.nodes?.length || 0}</div>
                                </div>
                                <div>
                                    <div style="color: #94a3b8; font-size: 11px;">Output Edges</div>
                                    <div style="color: #e2e8f0; font-size: 20px; font-weight: 600;">${result.edges?.length || 0}</div>
                                </div>
                                <div>
                                    <div style="color: #94a3b8; font-size: 11px;">Duration</div>
                                    <div style="color: #e2e8f0; font-size: 20px; font-weight: 600;">${execution.duration}ms</div>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Result Data -->
                        ${result.message ? `
                            <div style="background: #0f172a; padding: 16px; border-radius: 8px; border: 1px solid #1e293b; margin-bottom: 16px;">
                                <div style="color: #94a3b8; font-size: 12px; font-weight: 600; margin-bottom: 8px;">Message</div>
                                <div style="color: #e2e8f0; font-size: 13px;">${this.escapeHtml(result.message)}</div>
                            </div>
                        ` : ''}
                        
                        ${result.data ? `
                            <div style="background: #0f172a; padding: 16px; border-radius: 8px; border: 1px solid #1e293b; margin-bottom: 16px;">
                                <div style="color: #94a3b8; font-size: 12px; font-weight: 600; margin-bottom: 8px;">Result Data</div>
                                <pre style="color: #e2e8f0; font-size: 11px; overflow-x: auto; max-height: 300px;">${JSON.stringify(result.data, null, 2)}</pre>
                            </div>
                        ` : ''}
                    </div>
                    
                    <div style="display: flex; gap: 8px; margin-top: 20px;">
                        <button onclick="window.GraphToolExecutor.updateGraphWithResults(${JSON.stringify(result).replace(/"/g, '&quot;')})" style="
                            flex: 1; padding: 12px;
                            background: #3b82f6; color: white; border: none;
                            border-radius: 6px; cursor: pointer; font-weight: 600;
                        ">Update Graph</button>
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
        
        /**
         * Show execution error
         */
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
        
        /**
         * Update graph with tool results
         */
        updateGraphWithResults: function(result) {
            if (!result || !window.network) return;
            
            try {
                if (result.nodes && result.nodes.length > 0) {
                    const newNodes = result.nodes.map(n => ({
                        id: n.id || `tool_node_${Date.now()}_${Math.random()}`,
                        label: n.label || n.name || n.id,
                        color: n.color || '#60a5fa',
                        properties: n.properties || n
                    }));
                    
                    network.body.data.nodes.add(newNodes);
                }
                
                if (result.edges && result.edges.length > 0) {
                    const newEdges = result.edges.map(e => ({
                        id: e.id || `tool_edge_${Date.now()}_${Math.random()}`,
                        from: e.from,
                        to: e.to,
                        label: e.label || e.type,
                        properties: e.properties || e
                    }));
                    
                    network.body.data.edges.add(newEdges);
                }
                
                this.showToast(`Graph updated: ${result.nodes?.length || 0} nodes, ${result.edges?.length || 0} edges added`);
                
                if (window.GraphAddon) {
                    setTimeout(() => window.GraphAddon.buildNodesData(), 100);
                }
                
            } catch (error) {
                console.error('Failed to update graph:', error);
                this.showToast('Failed to update graph', 'error');
            }
        },
        
        /**
         * Show execution history
         */
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
                                        ${new Date(exec.timestamp).toLocaleString()} • ${exec.nodeCount} nodes • ${exec.duration || '?'}ms
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
        
        /**
         * View history item
         */
        viewHistoryItem: function(index) {
            const execution = this.executionHistory[index];
            if (!execution) return;
            
            this.showExecutionResults(execution);
        },
        
        /**
         * Add to history
         */
        addToHistory: function(execution) {
            this.executionHistory.push(execution);
            if (this.executionHistory.length > 50) {
                this.executionHistory = this.executionHistory.slice(-50);
            }
            this.saveHistory();
        },
        
        /**
         * Clear history
         */
        clearHistory: function() {
            if (confirm('Clear all execution history?')) {
                this.executionHistory = [];
                this.saveHistory();
                this.showExecutionHistory();
            }
        },
        
        /**
         * Save history to localStorage
         */
        saveHistory: function() {
            try {
                localStorage.setItem('tool_execution_history', JSON.stringify(this.executionHistory));
            } catch (e) {
                console.warn('Failed to save history:', e);
            }
        },
        
        /**
         * Load history from localStorage
         */
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
        
        /**
         * Show toast notification
         */
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
        
        /**
         * Escape HTML
         */
        escapeHtml: function(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
    };
    
    // Initialize on load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => window.GraphToolExecutor.init());
    } else {
        window.GraphToolExecutor.init();
    }
    
})();