/**
 * GraphToolExecutor Module
 * Executes Vera tools against selected graph nodes
 * Integrates with toolchain API and graph context menu
 */

(function() {
    'use strict';
    
    window.GraphToolExecutor = {
        
        // Store references
        graphAddon: null,
        sessionId: null,
        apiBaseUrl: 'http://llm.int:8888',
        availableTools: [],
        executionHistory: [],
        
        /**
         * Initialize the module
         */
        init: function(graphAddon, sessionId) {
            console.log('GraphToolExecutor.init called');
            this.graphAddon = graphAddon;
            this.sessionId = sessionId;
            
            // Load available tools
            this.loadAvailableTools();
            
            console.log('GraphToolExecutor initialized for session:', sessionId);
        },
        
        /**
         * Load available tools from API
         */
        loadAvailableTools: async function() {
            try {
                const response = await fetch(
                    `${this.apiBaseUrl}/api/toolchain/${this.sessionId}/tools`
                );
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                
                const data = await response.json();
                this.availableTools = data.tools || [];
                
                console.log('Loaded', this.availableTools.length, 'tools');
                
            } catch (error) {
                console.error('Error loading tools:', error);
                this.availableTools = [];
            }
        },
        
        /**
         * Show tool selection dialog for a node
         */
        showToolSelector: function(nodeId) {
            const nodeData = this.graphAddon.nodesData[nodeId];
            const nodeName = nodeData ? nodeData.display_name : nodeId;
            
            const panel = document.getElementById('property-panel');
            const content = document.getElementById('panel-content');
            
            // Build tool list
            let toolsHtml = '';
            
            // Group tools by common categories
            const categories = {
                'Analysis': ['deep_llm', 'fast_llm', 'text_stats'],
                'Web': ['web_search', 'web_search_deep', 'news_search'],
                'File': ['read_file', 'write_file', 'list_directory'],
                'Code': ['python', 'bash'],
                'Data': ['parse_json', 'sqlite_query', 'csv_to_json'],
                'Other': []
            };
            
            // Categorize tools
            const categorizedTools = {};
            for (const category in categories) {
                categorizedTools[category] = [];
            }
            
            this.availableTools.forEach(tool => {
                let found = false;
                for (const [category, toolNames] of Object.entries(categories)) {
                    if (category !== 'Other' && toolNames.includes(tool.name)) {
                        categorizedTools[category].push(tool);
                        found = true;
                        break;
                    }
                }
                if (!found) {
                    categorizedTools['Other'].push(tool);
                }
            });
            
            // Build HTML
            for (const [category, tools] of Object.entries(categorizedTools)) {
                if (tools.length === 0) continue;
                
                toolsHtml += `
                    <div style="margin-top: 16px;">
                        <div style="color: #94a3b8; font-size: 12px; font-weight: 600; margin-bottom: 8px;">${category}</div>
                `;
                
                tools.forEach(tool => {
                    const desc = tool.description.length > 80 
                        ? tool.description.substring(0, 80) + '...' 
                        : tool.description;
                    
                    toolsHtml += `
                        <div class="tool-item" onclick="window.GraphToolExecutor.selectTool('${nodeId}', '${tool.name}')" style="
                            padding: 12px;
                            margin-bottom: 8px;
                            background: #1e293b;
                            border: 1px solid #334155;
                            border-radius: 6px;
                            cursor: pointer;
                            transition: all 0.2s;
                        " onmouseover="this.style.background='#334155'" onmouseout="this.style.background='#1e293b'">
                            <div style="color: #60a5fa; font-weight: 600; font-size: 13px; margin-bottom: 4px;">${tool.name}</div>
                            <div style="color: #94a3b8; font-size: 11px;">${this.escapeHtml(desc)}</div>
                        </div>
                    `;
                });
                
                toolsHtml += `</div>`;
            }
            
            content.innerHTML = `
                <div style="padding: 20px;">
                    <div style="margin-bottom: 16px;">
                        <div style="font-size: 18px; font-weight: 600; color: #60a5fa; margin-bottom: 8px;">🔧 Execute Tool</div>
                        <div style="color: #94a3b8; font-size: 13px;">
                            Execute a tool on: <strong style="color: #e2e8f0;">${this.escapeHtml(nodeName)}</strong>
                        </div>
                    </div>
                    
                    <div style="max-height: 500px; overflow-y: auto;">
                        ${toolsHtml}
                    </div>
                    
                    <button onclick="window.GraphAddon.closePanel()" style="
                        width: 100%; margin-top: 16px; padding: 10px;
                        background: #334155; color: #e2e8f0; border: 1px solid #475569;
                        border-radius: 6px; cursor: pointer; font-weight: 600;
                    ">Cancel</button>
                </div>
            `;
            
            panel.style.display = 'flex';
        },
        
        /**
         * Select a tool and show input form
         */
        selectTool: async function(nodeId, toolName) {
            const nodeData = this.graphAddon.nodesData[nodeId];
            const nodeName = nodeData ? nodeData.display_name : nodeId;
            
            const panel = document.getElementById('property-panel');
            const content = document.getElementById('panel-content');
            
            // Show loading state
            content.innerHTML = `
                <div style="text-align: center; padding: 40px;">
                    <div style="font-size: 32px; margin-bottom: 16px;">⚙️</div>
                    <div style="color: #60a5fa; font-size: 14px;">Loading tool schema...</div>
                </div>
            `;
            
            try {
                // Get tool schema
                const response = await fetch(
                    `${this.apiBaseUrl}/api/toolchain/${this.sessionId}/tool/${toolName}/schema`
                );
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                
                const schema = await response.json();
                
                // Build input form based on schema
                this.showToolInputForm(nodeId, nodeName, toolName, schema);
                
            } catch (error) {
                console.error('Error loading tool schema:', error);
                content.innerHTML = `
                    <div style="text-align: center; padding: 30px;">
                        <div style="font-size: 32px; margin-bottom: 16px;">⚠️</div>
                        <div style="color: #ef4444; font-size: 14px; font-weight: 600; margin-bottom: 8px;">Error Loading Tool</div>
                        <div style="color: #94a3b8; font-size: 13px; margin-bottom: 20px;">${this.escapeHtml(error.message)}</div>
                        <button onclick="window.GraphToolExecutor.showToolSelector('${nodeId}')" style="
                            padding: 8px 20px; background: #3b82f6; color: white;
                            border: none; border-radius: 6px; cursor: pointer; font-weight: 600;
                        ">Back to Tools</button>
                    </div>
                `;
            }
        },
        
        /**
         * Show tool input form
         */
        showToolInputForm: function(nodeId, nodeName, toolName, schema) {
            const nodeData = this.graphAddon.nodesData[nodeId];
            const content = document.getElementById('panel-content');
            
            // Build form fields
            let formHtml = '';
            
            // Auto-populate with node data where possible
            schema.parameters.forEach(param => {
                let defaultValue = '';
                
                // Try to auto-populate from node properties
                if (nodeData && nodeData.properties) {
                    if (param.name === 'text' || param.name === 'query' || param.name === 'input') {
                        defaultValue = nodeData.properties.text || 
                                     nodeData.properties.body || 
                                     nodeData.properties.content || 
                                     nodeData.properties.summary || '';
                    } else if (nodeData.properties[param.name]) {
                        defaultValue = nodeData.properties[param.name];
                    }
                }
                
                // Fallback to schema default
                if (!defaultValue && param.default !== null && param.default !== undefined) {
                    defaultValue = param.default;
                }
                
                const isRequired = param.required ? ' *' : '';
                
                formHtml += `
                    <div style="margin-bottom: 16px;">
                        <label style="display: block; color: #94a3b8; font-size: 12px; font-weight: 600; margin-bottom: 6px;">
                            ${this.escapeHtml(param.name)}${isRequired}
                        </label>
                        <div style="color: #64748b; font-size: 11px; margin-bottom: 6px;">
                            ${this.escapeHtml(param.description || 'No description')}
                        </div>
                        ${this.renderFormField(param, defaultValue)}
                    </div>
                `;
            });
            
            content.innerHTML = `
                <div style="padding: 20px;">
                    <div style="margin-bottom: 16px;">
                        <div style="font-size: 18px; font-weight: 600; color: #60a5fa; margin-bottom: 8px;">
                            🔧 ${this.escapeHtml(toolName)}
                        </div>
                        <div style="color: #94a3b8; font-size: 13px; margin-bottom: 4px;">
                            On node: <strong style="color: #e2e8f0;">${this.escapeHtml(nodeName)}</strong>
                        </div>
                        <div style="color: #64748b; font-size: 11px; font-style: italic;">
                            ${this.escapeHtml(schema.description)}
                        </div>
                    </div>
                    
                    <form id="tool-input-form" style="max-height: 400px; overflow-y: auto; padding-right: 8px;">
                        ${formHtml}
                    </form>
                    
                    <div style="display: flex; gap: 8px; margin-top: 16px;">
                        <button onclick="window.GraphToolExecutor.executeTool('${nodeId}', '${toolName}')" style="
                            flex: 1; padding: 10px; background: #3b82f6; color: white;
                            border: none; border-radius: 6px; cursor: pointer; font-weight: 600;
                        ">Execute</button>
                        <button onclick="window.GraphToolExecutor.showToolSelector('${nodeId}')" style="
                            padding: 10px 20px; background: #334155; color: #e2e8f0;
                            border: 1px solid #475569; border-radius: 6px; cursor: pointer; font-weight: 600;
                        ">Back</button>
                    </div>
                </div>
            `;
        },
        
        /**
         * Render appropriate form field based on parameter type
         */
        renderFormField: function(param, defaultValue) {
            const value = defaultValue ? this.escapeHtml(String(defaultValue)) : '';
            
            if (param.type === 'boolean') {
                return `
                    <select id="param-${param.name}" style="
                        width: 100%; padding: 8px; background: #1e293b; color: #e2e8f0;
                        border: 1px solid #334155; border-radius: 4px;
                    ">
                        <option value="true" ${defaultValue === true ? 'selected' : ''}>True</option>
                        <option value="false" ${defaultValue === false ? 'selected' : ''}>False</option>
                    </select>
                `;
            } else if (param.type === 'integer' || param.type === 'number') {
                return `
                    <input type="number" id="param-${param.name}" value="${value}" style="
                        width: 100%; padding: 8px; background: #1e293b; color: #e2e8f0;
                        border: 1px solid #334155; border-radius: 4px;
                    " ${param.required ? 'required' : ''}>
                `;
            } else if (value.length > 100) {
                // Use textarea for long text
                return `
                    <textarea id="param-${param.name}" rows="6" style="
                        width: 100%; padding: 8px; background: #1e293b; color: #e2e8f0;
                        border: 1px solid #334155; border-radius: 4px; resize: vertical;
                        font-family: monospace; font-size: 12px;
                    " ${param.required ? 'required' : ''}>${value}</textarea>
                `;
            } else {
                return `
                    <input type="text" id="param-${param.name}" value="${value}" style="
                        width: 100%; padding: 8px; background: #1e293b; color: #e2e8f0;
                        border: 1px solid #334155; border-radius: 4px;
                    " ${param.required ? 'required' : ''}>
                `;
            }
        },
        
        /**
         * Execute the tool with collected inputs
         */
        executeTool: async function(nodeId, toolName) {
            const content = document.getElementById('panel-content');
            
            // Collect form data
            const form = document.getElementById('tool-input-form');
            const inputs = form.querySelectorAll('input, select, textarea');
            
            const toolInput = {};
            inputs.forEach(input => {
                const paramName = input.id.replace('param-', '');
                let value = input.value;
                
                // Type conversion
                if (input.type === 'number') {
                    value = parseFloat(value);
                } else if (input.tagName === 'SELECT' && (value === 'true' || value === 'false')) {
                    value = value === 'true';
                }
                
                toolInput[paramName] = value;
            });
            
            // Show executing state
            content.innerHTML = `
                <div style="text-align: center; padding: 40px;">
                    <div style="font-size: 32px; margin-bottom: 16px;">⚙️</div>
                    <div style="color: #60a5fa; font-size: 16px; font-weight: 600; margin-bottom: 8px;">
                        Executing ${this.escapeHtml(toolName)}
                    </div>
                    <div style="color: #94a3b8; font-size: 13px;">Processing...</div>
                </div>
            `;
            
            try {
                const startTime = Date.now();
                
                // Execute tool via API
                const response = await fetch(
                    `${this.apiBaseUrl}/api/toolchain/${this.sessionId}/execute-tool?tool_name=${encodeURIComponent(toolName)}&tool_input=${encodeURIComponent(JSON.stringify(toolInput))}`
                    , {
                        method: 'POST'
                    }
                );
                
                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.detail || `HTTP ${response.status}`);
                }
                
                const result = await response.json();
                const duration = Date.now() - startTime;
                
                // Store in execution history
                this.executionHistory.push({
                    nodeId,
                    toolName,
                    input: toolInput,
                    output: result.output,
                    timestamp: new Date().toISOString(),
                    duration
                });
                
                // Show result
                this.showToolResult(nodeId, toolName, toolInput, result.output, duration);
                
            } catch (error) {
                console.error('Tool execution error:', error);
                content.innerHTML = `
                    <div style="text-align: center; padding: 30px;">
                        <div style="font-size: 32px; margin-bottom: 16px;">❌</div>
                        <div style="color: #ef4444; font-size: 14px; font-weight: 600; margin-bottom: 8px;">
                            Execution Failed
                        </div>
                        <div style="color: #94a3b8; font-size: 13px; margin-bottom: 20px;">
                            ${this.escapeHtml(error.message)}
                        </div>
                        <button onclick="window.GraphToolExecutor.showToolSelector('${nodeId}')" style="
                            padding: 8px 20px; background: #3b82f6; color: white;
                            border: none; border-radius: 6px; cursor: pointer; font-weight: 600;
                        ">Try Again</button>
                    </div>
                `;
            }
        },
        
        /**
         * Show tool execution result
         */
        showToolResult: function(nodeId, toolName, input, output, duration) {
            const nodeData = this.graphAddon.nodesData[nodeId];
            const nodeName = nodeData ? nodeData.display_name : nodeId;
            const content = document.getElementById('panel-content');
            
            // Truncate output if very long
            let displayOutput = output;
            let truncated = false;
            if (output.length > 2000) {
                displayOutput = output.substring(0, 2000);
                truncated = true;
            }
            
            content.innerHTML = `
                <div style="padding: 20px;">
                    <div style="text-align: center; margin-bottom: 20px;">
                        <div style="font-size: 32px; margin-bottom: 8px;">✅</div>
                        <div style="color: #10b981; font-size: 16px; font-weight: 600; margin-bottom: 4px;">
                            Tool Executed Successfully
                        </div>
                        <div style="color: #94a3b8; font-size: 12px;">
                            Completed in ${duration}ms
                        </div>
                    </div>
                    
                    <div style="margin-bottom: 16px;">
                        <div style="color: #94a3b8; font-size: 12px; font-weight: 600; margin-bottom: 6px;">Tool</div>
                        <div style="color: #60a5fa; font-size: 14px;">${this.escapeHtml(toolName)}</div>
                    </div>
                    
                    <div style="margin-bottom: 16px;">
                        <div style="color: #94a3b8; font-size: 12px; font-weight: 600; margin-bottom: 6px;">Node</div>
                        <div style="color: #e2e8f0; font-size: 13px;">${this.escapeHtml(nodeName)}</div>
                    </div>
                    
                    <div style="margin-bottom: 16px;">
                        <div style="color: #94a3b8; font-size: 12px; font-weight: 600; margin-bottom: 6px;">Output</div>
                        <div style="
                            background: #0f172a; padding: 12px; border-radius: 6px;
                            border: 1px solid #1e293b; max-height: 300px; overflow-y: auto;
                            font-family: monospace; font-size: 12px; color: #e2e8f0;
                            white-space: pre-wrap; word-break: break-word;
                        ">${this.escapeHtml(displayOutput)}${truncated ? '\n\n... [truncated]' : ''}</div>
                    </div>
                    
                    <div style="display: flex; gap: 8px;">
                        <button onclick="window.GraphToolExecutor.saveResultToNode('${nodeId}', ${JSON.stringify(output).replace(/'/g, "&apos;")})" style="
                            flex: 1; padding: 10px; background: #10b981; color: white;
                            border: none; border-radius: 6px; cursor: pointer; font-weight: 600;
                        ">Save to Node</button>
                        <button onclick="window.GraphToolExecutor.showToolSelector('${nodeId}')" style="
                            padding: 10px 20px; background: #3b82f6; color: white;
                            border: none; border-radius: 6px; cursor: pointer; font-weight: 600;
                        ">Run Another Tool</button>
                        <button onclick="window.GraphAddon.closePanel()" style="
                            padding: 10px 20px; background: #334155; color: #e2e8f0;
                            border: 1px solid #475569; border-radius: 6px; cursor: pointer; font-weight: 600;
                        ">Close</button>
                    </div>
                </div>
            `;
        },
        
        /**
         * Save tool result to node properties
         */
        saveResultToNode: function(nodeId, output) {
            // This would require API endpoint to update node
            // For now, just show confirmation
            alert(`Result saved to node ${nodeId}\n\n(Implementation pending)`);
        },
        
        /**
         * Escape HTML for safe display
         */
        escapeHtml: function(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
    };
})();