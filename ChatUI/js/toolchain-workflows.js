(() => {
    // n8n Workflows integration for VeraChat Toolchain UI
    // Uses backend proxy to avoid CORS issues
    
    // Extend updateToolchainUI to include workflows button
    const originalUpdateToolchainUI = VeraChat.prototype.updateToolchainUI;
    
    VeraChat.prototype.updateToolchainUI = async function() {
        await this.loadAvailableTools();
        
        const container = document.getElementById('tab-toolchain');
        if (!container || this.activeTab !== 'toolchain') return;
        
        if (!this.toolViewMode) this.toolViewMode = 'grid';
        if (!this.toolchainView) this.toolchainView = 'tools';
        
        let html = `
            <div style="padding: 20px; overflow-y: auto; height: 100%;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                    <h2 style="margin: 0;">Toolchain Monitor</h2>
                    <div style="display: flex; gap: 8px;">
                        <button class="panel-btn ${this.toolchainView === 'tools' ? 'active' : ''}" 
                                onclick="app.switchToolchainView('tools')">
                            Tools
                        </button>
                        <button class="panel-btn ${this.toolchainView === 'executions' ? 'active' : ''}" 
                                onclick="app.switchToolchainView('executions')">
                            Executions
                        </button>
                        <button class="panel-btn ${this.toolchainView === 'history' ? 'active' : ''}" 
                                onclick="app.switchToolchainView('history')">
                            History
                        </button>
                        <button class="panel-btn ${this.toolchainView === 'workflows' ? 'active' : ''}" 
                                onclick="app.switchToolchainView('workflows')">
                            🔄 Workflows
                        </button>
                    </div>
                </div>
        `;
        
        if (this.toolchainView === 'tools') {
            html += this.renderToolCards();
        } else if (this.toolchainView === 'executions') {
            html += this.renderCurrentExecution();
        } else if (this.toolchainView === 'history') {
            html += this.renderExecutionHistory();
        } else if (this.toolchainView === 'workflows') {
            html += await this.renderWorkflows();
        }
        
        html += `</div>`;
        container.innerHTML = html;
        
        // Setup listeners after render
        setTimeout(() => {
            if (this.toolchainView === 'tools') {
                this.setupToolSearchListener();
            }
        }, 0);
    };

    // API base URL - uses the same base as toolchain API
    VeraChat.prototype.getN8nApiBase = function() {
        // Use the same host as the toolchain API
        return 'http://llm.int:8888/api/n8n';
    };

    // ============================================================
    // n8n API Methods (via proxy)
    // ============================================================

    // Load workflows from n8n via proxy
    VeraChat.prototype.loadN8nWorkflows = async function(forceRefresh = false) {
        if (this.n8nWorkflows && !forceRefresh) {
            return this.n8nWorkflows;
        }

        this.n8nWorkflowsLoading = true;
        this.n8nWorkflowsError = null;

        try {
            const response = await fetch(`${this.getN8nApiBase()}/workflows`, {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' }
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                
                // Handle authentication error specially
                if (response.status === 401) {
                    const message = errorData.detail?.message || errorData.message || 'Authentication required';
                    const hint = errorData.detail?.hint || 'Configure your n8n API key';
                    throw new Error(`${message}\n\n${hint}`);
                }
                
                throw new Error(errorData.detail?.message || errorData.detail || `Failed to fetch workflows: ${response.status}`);
            }

            const data = await response.json();
            this.n8nWorkflows = data.data || data || [];
            this.n8nWorkflowsLastFetched = new Date();
            
        } catch (error) {
            console.error('Failed to load n8n workflows:', error);
            this.n8nWorkflowsError = error.message;
            this.n8nWorkflows = [];
        } finally {
            this.n8nWorkflowsLoading = false;
        }

        return this.n8nWorkflows;
    };

    // Get n8n configuration
    VeraChat.prototype.getN8nConfig = async function() {
        try {
            const response = await fetch(`${this.getN8nApiBase()}/config`);
            if (response.ok) {
                return await response.json();
            }
        } catch (error) {
            console.error('Failed to get n8n config:', error);
        }
        return { url: 'http://localhost:5678', has_api_key: false };
    };

    // Test n8n connection
    VeraChat.prototype.testN8nConnection = async function() {
        const resultDiv = document.getElementById('n8n-test-result');
        
        if (resultDiv) {
            resultDiv.innerHTML = `
                <div style="padding: 10px; background: #0f172a; border-radius: 6px; color: #94a3b8; font-size: 12px;">
                    Testing connection...
                </div>
            `;
        }

        try {
            // First update config if inputs exist
            const urlInput = document.getElementById('n8n-url-input');
            const apiKeyInput = document.getElementById('n8n-apikey-input');
            
            if (urlInput) {
                await fetch(`${this.getN8nApiBase()}/config`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        url: urlInput.value.trim(),
                        api_key: apiKeyInput?.value.trim() || null
                    })
                });
            }

            // Test the connection
            const response = await fetch(`${this.getN8nApiBase()}/test`);
            const result = await response.json();

            if (resultDiv) {
                if (result.status === 'connected') {
                    resultDiv.innerHTML = `
                        <div style="padding: 10px; background: #064e3b; border-radius: 6px; color: #10b981; font-size: 12px;">
                            ✓ ${result.message}
                        </div>
                    `;
                } else {
                    resultDiv.innerHTML = `
                        <div style="padding: 10px; background: #7f1d1d; border-radius: 6px; color: #fca5a5; font-size: 12px;">
                            ✗ ${result.message}
                            ${result.detail ? `<br><small style="opacity: 0.8;">${this.escapeHtml(result.detail)}</small>` : ''}
                        </div>
                    `;
                }
            }
            
            return result;
        } catch (error) {
            if (resultDiv) {
                resultDiv.innerHTML = `
                    <div style="padding: 10px; background: #7f1d1d; border-radius: 6px; color: #fca5a5; font-size: 12px;">
                        ✗ Connection test failed: ${this.escapeHtml(error.message)}
                    </div>
                `;
            }
            return { status: 'error', message: error.message };
        }
    };

    // Save n8n settings
    VeraChat.prototype.saveN8nSettings = async function() {
        const urlInput = document.getElementById('n8n-url-input');
        const apiKeyInput = document.getElementById('n8n-apikey-input');
        
        if (!urlInput) return;

        try {
            const response = await fetch(`${this.getN8nApiBase()}/config`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    url: urlInput.value.trim(),
                    api_key: apiKeyInput?.value.trim() || null
                })
            });

            if (!response.ok) {
                throw new Error('Failed to save settings');
            }

            // Clear cached workflows to force refresh
            this.n8nWorkflows = null;
            this.n8nWorkflowsError = null;
            
            // Close modal
            document.getElementById('n8n-settings-modal')?.remove();
            
            // Refresh UI
            this.updateToolchainUI();
            
        } catch (error) {
            alert(`Failed to save settings: ${error.message}`);
        }
    };

    // Get single workflow details
    VeraChat.prototype.getN8nWorkflow = async function(workflowId) {
        try {
            const response = await fetch(`${this.getN8nApiBase()}/workflows/${workflowId}`);

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `Failed to fetch workflow: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Failed to get workflow:', error);
            throw error;
        }
    };

    // Execute a workflow
    VeraChat.prototype.executeN8nWorkflow = async function(workflowId, inputData = null) {
        try {
            const payload = inputData ? { data: inputData } : {};

            const response = await fetch(`${this.getN8nApiBase()}/workflows/${workflowId}/execute`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `Execution failed: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Failed to execute workflow:', error);
            throw error;
        }
    };

    // Get workflow executions
    VeraChat.prototype.getN8nWorkflowExecutions = async function(workflowId = null, limit = 20) {
        try {
            let url = `${this.getN8nApiBase()}/executions?limit=${limit}`;
            if (workflowId) {
                url += `&workflow_id=${workflowId}`;
            }

            const response = await fetch(url);

            if (!response.ok) {
                throw new Error(`Failed to fetch executions: ${response.status}`);
            }

            const data = await response.json();
            return data.data || data || [];
        } catch (error) {
            console.error('Failed to get executions:', error);
            return [];
        }
    };

    // Activate/Deactivate workflow
    VeraChat.prototype.toggleN8nWorkflowActive = async function(workflowId, active) {
        try {
            const response = await fetch(`${this.getN8nApiBase()}/workflows/${workflowId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ active })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `Failed to update workflow: ${response.status}`);
            }

            // Refresh workflows list
            await this.loadN8nWorkflows(true);
            this.updateToolchainUI();
            
            return await response.json();
        } catch (error) {
            console.error('Failed to toggle workflow:', error);
            alert(`Failed to ${active ? 'activate' : 'deactivate'} workflow: ${error.message}`);
        }
    };

    // Export toolchain to n8n workflow
    VeraChat.prototype.exportToolchainToN8n = async function(toolPlan, workflowName = null) {
        try {
            const response = await fetch(`${this.getN8nApiBase()}/toolchain-to-workflow`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    tool_plan: toolPlan,
                    workflow_name: workflowName
                })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `Failed to create workflow: ${response.status}`);
            }

            const result = await response.json();
            
            // Refresh workflows list
            await this.loadN8nWorkflows(true);
            this.updateToolchainUI();
            
            return result;
        } catch (error) {
            console.error('Failed to export to n8n:', error);
            throw error;
        }
    };

    // Import n8n workflow as toolchain
    VeraChat.prototype.importWorkflowAsToolchain = async function(workflowId) {
        try {
            const response = await fetch(`${this.getN8nApiBase()}/workflow-to-toolchain/${workflowId}`);

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `Failed to import workflow: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Failed to import workflow:', error);
            throw error;
        }
    };

    // ============================================================
    // UI Rendering
    // ============================================================

    // Render workflows view
    VeraChat.prototype.renderWorkflows = async function() {
        // Load n8n config first
        const config = await this.getN8nConfig();
        
        // Load workflows
        await this.loadN8nWorkflows();

        let html = `
            <div class="tool-container" style="border-radius: 8px; padding: 16px; margin-bottom: 16px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <h3 style="color: #60a5fa; margin: 0;">n8n Workflows</h3>
                        ${this.n8nWorkflowsLastFetched ? `
                            <span style="color: #64748b; font-size: 11px;">
                                Last updated: ${this.n8nWorkflowsLastFetched.toLocaleTimeString()}
                            </span>
                        ` : ''}
                    </div>
                    <div style="display: flex; gap: 8px;">
                        <button class="panel-btn" onclick="app.loadN8nWorkflows(true).then(() => app.updateToolchainUI())" 
                                style="font-size: 12px;">
                            🔄 Refresh
                        </button>
                        <button class="panel-btn" onclick="app.showN8nSettings()" 
                                style="font-size: 12px; background: #64748b;">
                            ⚙️ Settings
                        </button>
                    </div>
                </div>
        `;

        // Connection status
        html += `
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding: 10px; background: #0f172a; border-radius: 6px;">
                <div style="width: 8px; height: 8px; border-radius: 50%; background: ${this.n8nWorkflowsError ? '#ef4444' : '#10b981'};"></div>
                <span style="color: #94a3b8; font-size: 12px;">
                    ${this.n8nWorkflowsError 
                        ? `Connection error: ${this.escapeHtml(this.n8nWorkflowsError)}` 
                        : `Connected via proxy → ${this.escapeHtml(config.url)}`
                    }
                </span>
            </div>
        `;

        // Error state
        if (this.n8nWorkflowsError) {
            // Split error message by newlines for better display
            const errorLines = this.n8nWorkflowsError.split('\n').filter(l => l.trim());
            const mainError = errorLines[0] || this.n8nWorkflowsError;
            const hint = errorLines.slice(1).join(' ');
            
            html += `
                <div style="text-align: center; padding: 40px;">
                    <div style="font-size: 48px; margin-bottom: 16px; opacity: 0.3;">⚠️</div>
                    <p style="color: #ef4444; margin-bottom: 8px; font-weight: 600;">${this.escapeHtml(mainError)}</p>
                    ${hint ? `<p style="color: #94a3b8; font-size: 13px; margin-bottom: 16px;">${this.escapeHtml(hint)}</p>` : ''}
                    <button class="panel-btn" onclick="app.showN8nSettings()" style="background: #10b981;">
                        ⚙️ Configure n8n Settings
                    </button>
                </div>
            `;
            html += `</div>`;
            return html;
        }

        // Loading state
        if (this.n8nWorkflowsLoading) {
            html += `
                <div style="text-align: center; padding: 40px;">
                    <div style="font-size: 32px; margin-bottom: 16px;">⏳</div>
                    <p style="color: #94a3b8;">Loading workflows...</p>
                </div>
            `;
            html += `</div>`;
            return html;
        }

        // Empty state
        if (!this.n8nWorkflows || this.n8nWorkflows.length === 0) {
            html += `
                <div style="text-align: center; padding: 40px;">
                    <div style="font-size: 48px; margin-bottom: 16px; opacity: 0.3;">🔄</div>
                    <p style="color: #94a3b8; margin-bottom: 8px;">No workflows found</p>
                    <p style="color: #64748b; font-size: 12px;">Create workflows in n8n to see them here.</p>
                    <a href="${this.escapeHtml(config.url)}" target="_blank" class="panel-btn" style="display: inline-block; margin-top: 16px; text-decoration: none;">
                        Open n8n →
                    </a>
                </div>
            `;
            html += `</div>`;
            return html;
        }

        // Filter controls
        html += `
            <div style="display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap;">
                <input type="text" 
                       id="workflow-search" 
                       placeholder="🔍 Search workflows..."
                       value="${this.escapeHtml(this.workflowSearchQuery || '')}"
                       oninput="app.filterWorkflows(this.value)"
                       style="flex: 1; min-width: 200px; padding: 8px 12px; background: #1e293b; color: #e2e8f0; border: 1px solid #334155; border-radius: 6px; font-size: 13px;">
                <select id="workflow-status-filter" 
                        onchange="app.setWorkflowStatusFilter(this.value)"
                        style="padding: 8px 12px; background: #1e293b; color: #e2e8f0; border: 1px solid #334155; border-radius: 6px; font-size: 13px;">
                    <option value="all" ${this.workflowStatusFilter === 'all' ? 'selected' : ''}>All Status</option>
                    <option value="active" ${this.workflowStatusFilter === 'active' ? 'selected' : ''}>Active</option>
                    <option value="inactive" ${this.workflowStatusFilter === 'inactive' ? 'selected' : ''}>Inactive</option>
                </select>
            </div>
        `;

        // Apply filters
        let filteredWorkflows = [...this.n8nWorkflows];
        
        if (this.workflowSearchQuery) {
            const query = this.workflowSearchQuery.toLowerCase();
            filteredWorkflows = filteredWorkflows.filter(w => 
                w.name?.toLowerCase().includes(query) ||
                w.tags?.some(t => (t.name || t).toLowerCase().includes(query))
            );
        }

        if (this.workflowStatusFilter && this.workflowStatusFilter !== 'all') {
            filteredWorkflows = filteredWorkflows.filter(w => 
                this.workflowStatusFilter === 'active' ? w.active : !w.active
            );
        }

        // Results count
        html += `
            <div style="color: #64748b; font-size: 12px; margin-bottom: 12px;">
                Showing ${filteredWorkflows.length} of ${this.n8nWorkflows.length} workflows
            </div>
        `;

        // Workflow cards
        html += `<div style="display: flex; flex-direction: column; gap: 12px;">`;

        for (const workflow of filteredWorkflows) {
            const isActive = workflow.active;
            const statusColor = isActive ? '#10b981' : '#64748b';
            const isExpanded = this.expandedWorkflows && this.expandedWorkflows[workflow.id];
            const isExecuting = this.executingWorkflows && this.executingWorkflows[workflow.id];
            
            // Count nodes
            const nodeCount = workflow.nodes?.length || 0;
            const triggerNode = workflow.nodes?.find(n => n.type?.includes('Trigger'));
            
            html += `
                <div class="tool-card" 
                     data-workflow-id="${workflow.id}"
                     style="border-radius: 8px; padding: 14px; border-left: 4px solid ${statusColor}; transition: all 0.2s; ${isExecuting ? 'opacity: 0.7;' : ''}">
                    
                    <!-- Workflow Header -->
                    <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 10px;">
                        <div style="flex: 1;">
                            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                                <div style="color: #e2e8f0; font-weight: 600; font-size: 14px;">
                                    ${this.escapeHtml(workflow.name)}
                                </div>
                                <span style="background: ${isActive ? '#064e3b' : '#1e293b'}; color: ${isActive ? '#10b981' : '#64748b'}; padding: 2px 8px; border-radius: 10px; font-size: 10px; text-transform: uppercase;">
                                    ${isActive ? 'Active' : 'Inactive'}
                                </span>
                            </div>
                            <div style="color: #64748b; font-size: 11px;">
                                ID: ${workflow.id} • ${nodeCount} nodes
                                ${triggerNode ? ` • Trigger: ${this.escapeHtml(triggerNode.type?.split('.').pop() || 'Unknown')}` : ''}
                            </div>
                        </div>
                        <div style="display: flex; gap: 6px;">
                            <button class="panel-btn" 
                                    onclick="app.toggleWorkflowExpand('${workflow.id}')"
                                    style="padding: 4px 8px; font-size: 11px; min-width: auto;">
                                ${isExpanded ? '▼' : '▶'}
                            </button>
                        </div>
                    </div>
                    
                    <!-- Tags -->
                    ${workflow.tags && workflow.tags.length > 0 ? `
                        <div style="display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 10px;">
                            ${workflow.tags.map(tag => `
                                <span style="background: #334155; color: #94a3b8; padding: 2px 8px; border-radius: 10px; font-size: 10px;">
                                    ${this.escapeHtml(tag.name || tag)}
                                </span>
                            `).join('')}
                        </div>
                    ` : ''}
                    
                    <!-- Quick Actions (collapsed) -->
                    ${!isExpanded ? `
                        <div style="display: flex; gap: 8px; margin-top: 10px;">
                            <button class="panel-btn" 
                                    onclick="app.quickExecuteWorkflow('${workflow.id}')"
                                    style="flex: 1; padding: 8px; font-size: 12px;"
                                    ${isExecuting ? 'disabled' : ''}>
                                ${isExecuting ? '⏳ Running...' : '▶️ Execute'}
                            </button>
                            <a href="${this.escapeHtml(config.url)}/workflow/${workflow.id}" 
                               target="_blank" 
                               class="panel-btn" 
                               style="padding: 8px 12px; font-size: 12px; background: #64748b; text-decoration: none;">
                                ↗️ Edit
                            </a>
                            <button class="panel-btn" 
                                    onclick="app.toggleN8nWorkflowActive('${workflow.id}', ${!isActive})"
                                    style="padding: 8px 12px; font-size: 12px; background: ${isActive ? '#7f1d1d' : '#064e3b'};">
                                ${isActive ? '⏸️' : '▶️'}
                            </button>
                        </div>
                    ` : ''}
                    
                    <!-- Expanded Content -->
                    <div id="workflow-expand-${workflow.id}" style="display: ${isExpanded ? 'block' : 'none'};">
                        
                        <!-- Workflow Details -->
                        <div class="tool-subcard" style="padding: 12px; border-radius: 6px; margin-bottom: 12px;">
                            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; font-size: 12px;">
                                <div>
                                    <div style="color: #64748b; margin-bottom: 4px;">Created</div>
                                    <div style="color: #e2e8f0;">${workflow.createdAt ? new Date(workflow.createdAt).toLocaleDateString() : 'N/A'}</div>
                                </div>
                                <div>
                                    <div style="color: #64748b; margin-bottom: 4px;">Updated</div>
                                    <div style="color: #e2e8f0;">${workflow.updatedAt ? new Date(workflow.updatedAt).toLocaleDateString() : 'N/A'}</div>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Node List -->
                        ${workflow.nodes && workflow.nodes.length > 0 ? `
                            <div style="margin-bottom: 12px;">
                                <div style="color: #94a3b8; font-size: 11px; margin-bottom: 8px; text-transform: uppercase;">Nodes</div>
                                <div style="display: flex; flex-wrap: wrap; gap: 6px;">
                                    ${workflow.nodes.slice(0, 10).map(node => `
                                        <span style="background: #1e293b; color: #cbd5e1; padding: 4px 8px; border-radius: 4px; font-size: 11px; border-left: 2px solid #8b5cf6;">
                                            ${this.escapeHtml(node.name || node.type?.split('.').pop() || 'Node')}
                                        </span>
                                    `).join('')}
                                    ${workflow.nodes.length > 10 ? `
                                        <span style="color: #64748b; font-size: 11px; padding: 4px;">
                                            +${workflow.nodes.length - 10} more
                                        </span>
                                    ` : ''}
                                </div>
                            </div>
                        ` : ''}
                        
                        <!-- Input Parameters (for manual execution) -->
                        <div id="workflow-input-${workflow.id}" style="margin-bottom: 12px;">
                            <div style="color: #94a3b8; font-size: 11px; margin-bottom: 6px; text-transform: uppercase;">
                                Execution Input (JSON, optional)
                            </div>
                            <textarea id="workflow-input-data-${workflow.id}"
                                      placeholder='{"key": "value"}'
                                      style="width: 100%; min-height: 60px; padding: 8px; background: #0f172a; color: #e2e8f0; border: 1px solid #334155; border-radius: 4px; font-size: 12px; font-family: monospace; resize: vertical;"
                            ></textarea>
                        </div>
                        
                        <!-- Action Buttons -->
                        <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                            <button class="panel-btn" 
                                    onclick="app.executeWorkflowWithInput('${workflow.id}')"
                                    style="flex: 1; padding: 10px; font-size: 12px;"
                                    ${isExecuting ? 'disabled' : ''}>
                                ${isExecuting ? '⏳ Running...' : '🚀 Execute Workflow'}
                            </button>
                            <button class="panel-btn" 
                                    onclick="app.viewWorkflowExecutions('${workflow.id}')"
                                    style="padding: 10px; font-size: 12px; background: #334155;">
                                📜 Executions
                            </button>
                            <button class="panel-btn" 
                                    onclick="app.importWorkflowAsToolchainUI('${workflow.id}')"
                                    style="padding: 10px; font-size: 12px; background: #7c3aed;">
                                📥 Import
                            </button>
                            <a href="${this.escapeHtml(config.url)}/workflow/${workflow.id}" 
                               target="_blank" 
                               class="panel-btn" 
                               style="padding: 10px; font-size: 12px; background: #64748b; text-decoration: none;">
                                ↗️ Open in n8n
                            </a>
                            <button class="panel-btn" 
                                    onclick="app.toggleN8nWorkflowActive('${workflow.id}', ${!isActive})"
                                    style="padding: 10px; font-size: 12px; background: ${isActive ? '#7f1d1d' : '#064e3b'};">
                                ${isActive ? '⏸️ Deactivate' : '▶️ Activate'}
                            </button>
                        </div>
                        
                        <!-- Execution Result -->
                        <div id="workflow-result-${workflow.id}"></div>
                    </div>
                </div>
            `;
        }

        html += `</div>`; // End workflow cards container
        html += `</div>`; // End main container

        return html;
    };

    // ============================================================
    // UI Interaction Methods
    // ============================================================

    // Filter workflows
    VeraChat.prototype.filterWorkflows = function(query) {
        this.workflowSearchQuery = query;
        this.updateToolchainUI();
    };

    VeraChat.prototype.setWorkflowStatusFilter = function(status) {
        this.workflowStatusFilter = status;
        this.updateToolchainUI();
    };

    // Toggle workflow expand
    VeraChat.prototype.toggleWorkflowExpand = function(workflowId) {
        if (!this.expandedWorkflows) this.expandedWorkflows = {};
        this.expandedWorkflows[workflowId] = !this.expandedWorkflows[workflowId];
        this.updateToolchainUI();
    };

    // Quick execute workflow
    VeraChat.prototype.quickExecuteWorkflow = async function(workflowId) {
        if (!this.executingWorkflows) this.executingWorkflows = {};
        this.executingWorkflows[workflowId] = true;
        this.updateToolchainUI();

        try {
            const result = await this.executeN8nWorkflow(workflowId);
            console.log('Workflow execution result:', result);
            
        } catch (error) {
            alert(`Execution failed: ${error.message}`);
        } finally {
            delete this.executingWorkflows[workflowId];
            this.updateToolchainUI();
        }
    };

    // Execute workflow with input data
    VeraChat.prototype.executeWorkflowWithInput = async function(workflowId) {
        const inputEl = document.getElementById(`workflow-input-data-${workflowId}`);
        let inputData = null;

        if (inputEl && inputEl.value.trim()) {
            try {
                inputData = JSON.parse(inputEl.value);
            } catch (e) {
                alert('Invalid JSON input. Please check your syntax.');
                return;
            }
        }

        if (!this.executingWorkflows) this.executingWorkflows = {};
        this.executingWorkflows[workflowId] = true;
        
        const resultContainer = document.getElementById(`workflow-result-${workflowId}`);
        if (resultContainer) {
            resultContainer.innerHTML = `
                <div style="margin-top: 12px; padding: 12px; background: #0f172a; border-radius: 6px; border-left: 3px solid #3b82f6;">
                    <div style="color: #3b82f6; font-size: 11px; margin-bottom: 4px;">⏳ Executing...</div>
                </div>
            `;
        }

        // Update card opacity
        const card = document.querySelector(`[data-workflow-id="${workflowId}"]`);
        if (card) card.style.opacity = '0.7';

        try {
            const result = await this.executeN8nWorkflow(workflowId, inputData);
            
            if (resultContainer) {
                resultContainer.innerHTML = `
                    <div style="margin-top: 12px; padding: 12px; background: #0f172a; border-radius: 6px; border-left: 3px solid #10b981;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                            <div style="color: #10b981; font-size: 11px; font-weight: 600; text-transform: uppercase;">✓ Success</div>
                            <button onclick="document.getElementById('workflow-result-${workflowId}').innerHTML=''" 
                                    style="background: none; border: none; color: #64748b; cursor: pointer; padding: 2px;">✕</button>
                        </div>
                        <div style="color: #cbd5e1; font-size: 11px; font-family: monospace; max-height: 200px; overflow-y: auto; white-space: pre-wrap;">
${this.escapeHtml(JSON.stringify(result, null, 2))}
                        </div>
                    </div>
                `;
            }
            
        } catch (error) {
            if (resultContainer) {
                resultContainer.innerHTML = `
                    <div style="margin-top: 12px; padding: 12px; background: #0f172a; border-radius: 6px; border-left: 3px solid #ef4444;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                            <div style="color: #ef4444; font-size: 11px; font-weight: 600; text-transform: uppercase;">✗ Error</div>
                            <button onclick="document.getElementById('workflow-result-${workflowId}').innerHTML=''" 
                                    style="background: none; border: none; color: #64748b; cursor: pointer; padding: 2px;">✕</button>
                        </div>
                        <div style="color: #fca5a5; font-size: 12px;">${this.escapeHtml(error.message)}</div>
                    </div>
                `;
            }
        } finally {
            delete this.executingWorkflows[workflowId];
            if (card) card.style.opacity = '1';
        }
    };

    // View workflow executions
    VeraChat.prototype.viewWorkflowExecutions = async function(workflowId) {
        const executions = await this.getN8nWorkflowExecutions(workflowId);
        const workflow = this.n8nWorkflows?.find(w => w.id === workflowId);
        const config = await this.getN8nConfig();
        
        const container = document.getElementById('tab-toolchain');
        if (!container) return;

        let html = `
            <div style="padding: 20px; overflow-y: auto; height: 100%;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                    <div>
                        <button class="panel-btn" onclick="app.updateToolchainUI()" style="margin-right: 12px;">
                            ← Back
                        </button>
                        <span style="color: #e2e8f0; font-size: 18px; font-weight: 600;">
                            Executions: ${this.escapeHtml(workflow?.name || workflowId)}
                        </span>
                    </div>
                    <button class="panel-btn" onclick="app.viewWorkflowExecutions('${workflowId}')">
                        🔄 Refresh
                    </button>
                </div>
        `;

        if (executions.length === 0) {
            html += `
                <div style="text-align: center; padding: 40px;">
                    <div style="font-size: 48px; margin-bottom: 16px; opacity: 0.3;">📭</div>
                    <p style="color: #94a3b8;">No executions found for this workflow.</p>
                </div>
            `;
        } else {
            html += `<div style="display: flex; flex-direction: column; gap: 12px;">`;
            
            for (const exec of executions) {
                const statusColor = exec.finished 
                    ? (exec.status === 'success' ? '#10b981' : '#ef4444')
                    : '#f59e0b';
                const statusText = exec.finished 
                    ? (exec.status === 'success' ? 'Success' : 'Failed')
                    : 'Running';

                html += `
                    <div class="tool-card" style="border-radius: 8px; padding: 14px; border-left: 4px solid ${statusColor};">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                            <div>
                                <div style="color: #e2e8f0; font-weight: 600;">Execution #${exec.id}</div>
                                <div style="color: #64748b; font-size: 11px;">
                                    ${exec.startedAt ? new Date(exec.startedAt).toLocaleString() : 'N/A'}
                                </div>
                            </div>
                            <span style="background: ${statusColor}20; color: ${statusColor}; padding: 4px 10px; border-radius: 10px; font-size: 11px; text-transform: uppercase;">
                                ${statusText}
                            </span>
                        </div>
                        ${exec.stoppedAt ? `
                            <div style="color: #94a3b8; font-size: 12px;">
                                Duration: ${((new Date(exec.stoppedAt) - new Date(exec.startedAt)) / 1000).toFixed(2)}s
                            </div>
                        ` : ''}
                        ${exec.mode ? `
                            <div style="color: #64748b; font-size: 11px; margin-top: 4px;">
                                Mode: ${exec.mode}
                            </div>
                        ` : ''}
                    </div>
                `;
            }
            
            html += `</div>`;
        }

        html += `</div>`;
        container.innerHTML = html;
    };

    // Import workflow as toolchain UI
    VeraChat.prototype.importWorkflowAsToolchainUI = async function(workflowId) {
        try {
            const result = await this.importWorkflowAsToolchain(workflowId);
            
            // Show the imported toolchain
            const modal = document.createElement('div');
            modal.id = 'import-result-modal';
            modal.style.cssText = `
                position: fixed; top: 0; left: 0; right: 0; bottom: 0;
                background: rgba(0,0,0,0.7); display: flex; align-items: center;
                justify-content: center; z-index: 10000;
            `;
            
            modal.innerHTML = `
                <div style="background: #1e293b; border-radius: 12px; padding: 24px; width: 500px; max-width: 90vw; max-height: 80vh; overflow-y: auto;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                        <h3 style="margin: 0; color: #e2e8f0;">Imported Toolchain</h3>
                        <button onclick="document.getElementById('import-result-modal').remove()" 
                                style="background: none; border: none; color: #64748b; cursor: pointer; font-size: 20px;">✕</button>
                    </div>
                    
                    <div style="margin-bottom: 16px;">
                        <div style="color: #94a3b8; font-size: 12px; margin-bottom: 4px;">Workflow</div>
                        <div style="color: #e2e8f0; font-size: 14px;">${this.escapeHtml(result.workflow_name)}</div>
                    </div>
                    
                    <div style="margin-bottom: 16px;">
                        <div style="color: #94a3b8; font-size: 12px; margin-bottom: 8px;">Tool Plan (${result.total_steps} steps)</div>
                        <div style="background: #0f172a; border-radius: 6px; padding: 12px; font-family: monospace; font-size: 12px; color: #cbd5e1; max-height: 300px; overflow-y: auto;">
                            <pre style="margin: 0; white-space: pre-wrap;">${this.escapeHtml(JSON.stringify(result.tool_plan, null, 2))}</pre>
                        </div>
                    </div>
                    
                    <div style="display: flex; gap: 12px;">
                        <button class="panel-btn" onclick="app.copyToClipboard(JSON.stringify(${JSON.stringify(result.tool_plan)}, null, 2)); alert('Copied to clipboard!');" style="flex: 1;">
                            📋 Copy JSON
                        </button>
                        <button class="panel-btn" onclick="document.getElementById('import-result-modal').remove()" style="flex: 1; background: #64748b;">
                            Close
                        </button>
                    </div>
                </div>
            `;
            
            document.body.appendChild(modal);
            modal.addEventListener('click', (e) => {
                if (e.target === modal) modal.remove();
            });
            
        } catch (error) {
            alert(`Failed to import workflow: ${error.message}`);
        }
    };

    // Copy to clipboard helper
    VeraChat.prototype.copyToClipboard = function(text) {
        navigator.clipboard.writeText(text);
    };

    // Show n8n settings modal
    VeraChat.prototype.showN8nSettings = async function() {
        const config = await this.getN8nConfig();
        
        const modal = document.createElement('div');
        modal.id = 'n8n-settings-modal';
        modal.style.cssText = `
            position: fixed; top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.7); display: flex; align-items: center;
            justify-content: center; z-index: 10000;
        `;
        
        modal.innerHTML = `
            <div style="background: #1e293b; border-radius: 12px; padding: 24px; width: 400px; max-width: 90vw;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                    <h3 style="margin: 0; color: #e2e8f0;">n8n Connection Settings</h3>
                    <button onclick="document.getElementById('n8n-settings-modal').remove()" 
                            style="background: none; border: none; color: #64748b; cursor: pointer; font-size: 20px;">✕</button>
                </div>
                
                <div style="background: #0f172a; border-radius: 6px; padding: 12px; margin-bottom: 16px;">
                    <div style="color: #64748b; font-size: 11px; margin-bottom: 4px;">ℹ️ Connection Info</div>
                    <div style="color: #94a3b8; font-size: 12px;">
                        Requests are proxied through the Vera API to avoid CORS issues.
                        Configure the n8n URL that the backend should connect to.
                    </div>
                </div>
                
                <div style="margin-bottom: 16px;">
                    <label style="display: block; color: #94a3b8; font-size: 12px; margin-bottom: 6px;">n8n URL</label>
                    <input type="text" id="n8n-url-input" 
                           value="${this.escapeHtml(config.url)}"
                           placeholder="http://localhost:5678"
                           style="width: 100%; padding: 10px; background: #0f172a; color: #e2e8f0; border: 1px solid #334155; border-radius: 6px; font-size: 13px;">
                </div>
                
                <div style="margin-bottom: 20px;">
                    <label style="display: block; color: #94a3b8; font-size: 12px; margin-bottom: 6px;">
                        API Key ${config.has_api_key ? '<span style="color: #10b981;">✓ (configured)</span>' : '<span style="color: #f59e0b;">⚠ (not set)</span>'}
                    </label>
                    <input type="password" id="n8n-apikey-input" 
                           placeholder="${config.has_api_key ? '••••••••' : 'Enter your n8n API key'}"
                           style="width: 100%; padding: 10px; background: #0f172a; color: #e2e8f0; border: 1px solid #334155; border-radius: 6px; font-size: 13px;">
                    <div style="color: #64748b; font-size: 11px; margin-top: 4px;">
                        ${config.has_api_key 
                            ? 'Leave empty to keep current key, or enter a new one to replace it.' 
                            : 'Required if n8n has authentication enabled. Get it from n8n Settings → API.'
                        }
                    </div>
                </div>
                
                <div style="display: flex; gap: 12px;">
                    <button class="panel-btn" onclick="app.testN8nConnection()" style="flex: 1;">
                        🔍 Test Connection
                    </button>
                    <button class="panel-btn" onclick="app.saveN8nSettings()" style="flex: 1; background: #10b981;">
                        💾 Save
                    </button>
                </div>
                
                <div id="n8n-test-result" style="margin-top: 12px;"></div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Close on backdrop click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) modal.remove();
        });
    };

    console.log('Toolchain Workflows extension loaded (proxy mode)');
})();