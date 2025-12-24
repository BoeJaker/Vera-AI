// agents-ui-manager-v2.js - YAML-based agent system UI
(() => {
    // ========================================================================
    // STATE
    // ========================================================================
    
    VeraChat.prototype.agentsV2State = {
        currentPanel: 'browse',
        apiUrl: 'http://llm.int:8888/api/agents/v2',
        updateInterval: null,
        agents: [],
        selectedAgent: null,
        editingFile: null,
        systemInfo: null
    };

    // ========================================================================
    // INITIALIZATION
    // ========================================================================
    
    VeraChat.prototype.initAgentsV2 = async function() {
        console.log('Initializing Agents V2 UI...');
        
        // Load system info
        await this.loadAgentsV2SystemInfo();
        
        // Start periodic updates
        this.startAgentsV2Updates();
        
        // Initial load
        await this.refreshAgentsV2();
    };

    // ========================================================================
    // PERIODIC UPDATES
    // ========================================================================
    
    VeraChat.prototype.startAgentsV2Updates = function() {
        if (this.agentsV2State.updateInterval) {
            clearInterval(this.agentsV2State.updateInterval);
        }
        
        this.agentsV2State.updateInterval = setInterval(() => {
            if (this.activeTab === 'agents') {
                this.refreshAgentsV2();
            }
        }, 15000); // 15 seconds
    };

    VeraChat.prototype.stopAgentsV2Updates = function() {
        if (this.agentsV2State.updateInterval) {
            clearInterval(this.agentsV2State.updateInterval);
            this.agentsV2State.updateInterval = null;
        }
    };

    // ========================================================================
    // DATA LOADING
    // ========================================================================
    
    VeraChat.prototype.loadAgentsV2SystemInfo = async function() {
        try {
            const response = await fetch(`${this.agentsV2State.apiUrl}/system/info`);
            const data = await response.json();
            this.agentsV2State.systemInfo = data;
        } catch (error) {
            console.error('Failed to load system info:', error);
        }
    };

    VeraChat.prototype.refreshAgentsV2 = async function() {
        try {
            const response = await fetch(`${this.agentsV2State.apiUrl}/list`);
            const data = await response.json();
            
            this.agentsV2State.agents = data.agents || [];
            
            // Update UI if on browse panel
            if (this.agentsV2State.currentPanel === 'browse') {
                this.renderAgentsV2List();
            }
        } catch (error) {
            console.error('Failed to refresh agents:', error);
        }
    };

    // ========================================================================
    // PANEL SWITCHING
    // ========================================================================
    
    VeraChat.prototype.switchAgentsV2Panel = function(panelName) {
        // Update navigation
        document.querySelectorAll('.agents-nav-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        const activeBtn = document.querySelector(`.agents-nav-btn[data-panel="${panelName}"]`);
        if (activeBtn) activeBtn.classList.add('active');
        
        // Update panels
        document.querySelectorAll('.agents-panel').forEach(panel => {
            panel.style.display = 'none';
        });
        const activePanel = document.getElementById(`agents-panel-${panelName}`);
        if (activePanel) activePanel.style.display = 'block';
        
        this.agentsV2State.currentPanel = panelName;
        
        // Load panel-specific data
        switch(panelName) {
            case 'browse':
                this.renderAgentsV2List();
                break;
            case 'edit':
                if (this.agentsV2State.selectedAgent) {
                    this.loadAgentV2Editor(this.agentsV2State.selectedAgent);
                }
                break;
            case 'build':
                this.loadAgentV2BuildPanel();
                break;
            case 'system':
                this.loadAgentV2SystemPanel();
                break;
        }
    };

    // ========================================================================
    // AGENT LIST RENDERING
    // ========================================================================
    
    VeraChat.prototype.renderAgentsV2List = function() {
        const container = document.getElementById('agents-list');
        if (!container) return;
        
        const agents = this.agentsV2State.agents;
        
        if (agents.length === 0) {
            container.innerHTML = `
                <div style="text-align: center; padding: 48px; color: var(--text-muted);">
                    <div style="font-size: 48px; margin-bottom: 16px;">🤖</div>
                    <h3 style="margin: 0 0 8px 0;">No Agents Found</h3>
                    <p style="margin: 0 0 20px 0;">Create your first agent to get started</p>
                    <button onclick="app.showCreateAgentV2Dialog()" 
                            style="padding: 12px 24px; background: var(--accent); border: none; border-radius: 8px; color: white; cursor: pointer; font-size: 14px; font-weight: 600;">
                        ➕ Create New Agent
                    </button>
                </div>
            `;
            return;
        }
        
        let html = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                <h3 style="margin: 0; font-size: 18px; font-weight: 600;">Agents (${agents.length})</h3>
                <button onclick="app.showCreateAgentV2Dialog()" 
                        style="padding: 8px 16px; background: var(--accent); border: none; border-radius: 6px; color: white; cursor: pointer; font-size: 13px; font-weight: 600;">
                    ➕ New Agent
                </button>
            </div>
            
            <div style="display: grid; gap: 12px;">
        `;
        
        agents.forEach(agent => {
            const isSelected = this.agentsV2State.selectedAgent === agent.id;
            const hasIssues = agent.status.validation_issues && agent.status.validation_issues.length > 0;
            const needsBuild = !agent.status.has_modelfile || agent.status.modelfile_age > 3600;
            
            // Status badge
            let statusBadge = '';
            if (hasIssues) {
                statusBadge = '<span style="padding: 2px 8px; background: var(--danger); color: white; border-radius: 4px; font-size: 10px; font-weight: 600;">⚠️ ISSUES</span>';
            } else if (needsBuild) {
                statusBadge = '<span style="padding: 2px 8px; background: var(--warning); color: white; border-radius: 4px; font-size: 10px; font-weight: 600;">🔨 BUILD NEEDED</span>';
            } else {
                statusBadge = '<span style="padding: 2px 8px; background: var(--success); color: white; border-radius: 4px; font-size: 10px; font-weight: 600;">✓ READY</span>';
            }
            
            html += `
                <div style="padding: 16px; background: var(--bg); border-radius: 10px; border-left: 4px solid ${isSelected ? 'var(--accent)' : 'var(--border)'}; box-shadow: 0 2px 6px rgba(0,0,0,0.1); cursor: pointer; transition: all 0.2s;"
                     onclick="app.selectAgentV2('${agent.id}')"
                     onmouseover="this.style.background='var(--bg-darker)'"
                     onmouseout="this.style.background='var(--bg)'">
                    
                    <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 12px;">
                        <div style="flex: 1;">
                            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                                <h4 style="margin: 0; font-size: 15px; font-weight: 600;">${agent.name}</h4>
                                ${statusBadge}
                            </div>
                            <p style="margin: 0; font-size: 12px; color: var(--text-muted);">${agent.description || 'No description'}</p>
                        </div>
                    </div>
                    
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 12px; padding: 12px; background: var(--bg-darker); border-radius: 6px;">
                        <div>
                            <div style="font-size: 10px; color: var(--text-muted);">Base Model</div>
                            <div style="font-size: 12px; font-weight: 600; font-family: monospace;">${agent.base_model}</div>
                        </div>
                        <div>
                            <div style="font-size: 10px; color: var(--text-muted);">Version</div>
                            <div style="font-size: 12px; font-weight: 600;">${agent.version}</div>
                        </div>
                        <div>
                            <div style="font-size: 10px; color: var(--text-muted);">Tools</div>
                            <div style="font-size: 12px; font-weight: 600;">${agent.tools.length || 0}</div>
                        </div>
                    </div>
                    
                    ${hasIssues ? `
                        <div style="padding: 8px; background: rgba(239, 68, 68, 0.1); border-radius: 4px; margin-bottom: 12px;">
                            <div style="font-size: 11px; font-weight: 600; color: var(--danger); margin-bottom: 4px;">Validation Issues:</div>
                            ${agent.status.validation_issues.map(issue => `
                                <div style="font-size: 11px; color: var(--danger);">• ${issue}</div>
                            `).join('')}
                        </div>
                    ` : ''}
                    
                    <div style="display: flex; gap: 6px;">
                        <button onclick="event.stopPropagation(); app.editAgentV2('${agent.id}')" 
                                style="flex: 1; padding: 8px; background: var(--accent); border: none; border-radius: 6px; color: white; cursor: pointer; font-size: 12px; font-weight: 600;">
                            ✏️ Edit
                        </button>
                        <button onclick="event.stopPropagation(); app.buildAgentV2('${agent.id}')" 
                                style="flex: 1; padding: 8px; background: var(--success); border: none; border-radius: 6px; color: white; cursor: pointer; font-size: 12px; font-weight: 600;">
                            🔨 Build
                        </button>
                        <button onclick="event.stopPropagation(); app.validateAgentV2('${agent.id}')" 
                                style="flex: 1; padding: 8px; background: #9333ea; border: none; border-radius: 6px; color: white; cursor: pointer; font-size: 12px; font-weight: 600;">
                            ✓ Validate
                        </button>
                        <button onclick="event.stopPropagation(); app.deleteAgentV2('${agent.id}')" 
                                style="flex: 1; padding: 8px; background: var(--danger); border: none; border-radius: 6px; color: white; cursor: pointer; font-size: 12px; font-weight: 600;">
                            🗑️ Delete
                        </button>
                    </div>
                </div>
            `;
        });
        
        html += '</div>';
        container.innerHTML = html;
    };

    // ========================================================================
    // AGENT ACTIONS
    // ========================================================================
    
    VeraChat.prototype.selectAgentV2 = function(agentId) {
        this.agentsV2State.selectedAgent = agentId;
        this.renderAgentsV2List();
        
        const agent = this.agentsV2State.agents.find(a => a.id === agentId);
        if (agent) {
            this.addSystemMessage(`Selected agent: ${agent.name}`, 'info');
        }
    };

    VeraChat.prototype.editAgentV2 = function(agentId) {
        this.agentsV2State.selectedAgent = agentId;
        this.switchAgentsV2Panel('edit');
    };

    VeraChat.prototype.buildAgentV2 = async function(agentId, createOllamaModel = true) {
        try {
            this.addSystemMessage(`Building agent: ${agentId}...`, 'info');
            
            const response = await fetch(`${this.agentsV2State.apiUrl}/${agentId}/build`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ create_ollama_model: createOllamaModel })
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                if (data.issues) {
                    this.addSystemMessage(`Build failed. Issues:`, 'error');
                    data.issues.forEach(issue => {
                        this.addSystemMessage(`  • ${issue}`, 'error');
                    });
                } else {
                    throw new Error(data.detail || `HTTP ${response.status}`);
                }
                return;
            }
            
            this.addSystemMessage(data.message, 'success');
            
            if (createOllamaModel) {
                this.addSystemMessage(`Ollama model created: ${agentId}`, 'success');
            }
            
            // Refresh
            await this.refreshAgentsV2();
            
        } catch (error) {
            this.addSystemMessage(`Failed to build agent: ${error.message}`, 'error');
        }
    };

    VeraChat.prototype.validateAgentV2 = async function(agentId) {
        try {
            const response = await fetch(`${this.agentsV2State.apiUrl}/${agentId}/validate`, {
                method: 'POST'
            });
            
            const data = await response.json();
            
            if (data.valid) {
                this.addSystemMessage(`✓ Agent ${agentId} is valid`, 'success');
            } else {
                this.addSystemMessage(`⚠️ Validation issues for ${agentId}:`, 'warning');
                data.issues.forEach(issue => {
                    this.addSystemMessage(`  • ${issue}`, 'warning');
                });
            }
        } catch (error) {
            this.addSystemMessage(`Validation failed: ${error.message}`, 'error');
        }
    };

    VeraChat.prototype.deleteAgentV2 = async function(agentId) {
        if (!confirm(`Delete agent "${agentId}" and all its files?\n\nThis cannot be undone!`)) {
            return;
        }
        
        try {
            const response = await fetch(`${this.agentsV2State.apiUrl}/${agentId}?confirm=true`, {
                method: 'DELETE'
            });
            
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            this.addSystemMessage(data.message, 'success');
            
            // Clear selection if deleted agent was selected
            if (this.agentsV2State.selectedAgent === agentId) {
                this.agentsV2State.selectedAgent = null;
            }
            
            // Refresh
            await this.refreshAgentsV2();
            
        } catch (error) {
            this.addSystemMessage(`Failed to delete agent: ${error.message}`, 'error');
        }
    };

    // ========================================================================
    // AGENT EDITOR
    // ========================================================================
    
    VeraChat.prototype.loadAgentV2Editor = async function(agentId) {
        const container = document.getElementById('agents-editor-content');
        if (!container) return;
        
        try {
            // Load agent details
            const response = await fetch(`${this.agentsV2State.apiUrl}/${agentId}`);
            const data = await response.json();
            const agent = data.agent;
            
            container.innerHTML = `
                <div style="max-width: 1200px;">
                    <!-- Header -->
                    <div style="background: var(--bg-darker); padding: 20px; border-radius: 12px; margin-bottom: 20px;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <h3 style="margin: 0 0 8px 0; font-size: 18px; font-weight: 600;">${agent.config.name}</h3>
                                <p style="margin: 0; font-size: 13px; color: var(--text-muted);">${agent.config.description || 'No description'}</p>
                            </div>
                            <button onclick="app.saveAgentV2Config('${agentId}')" 
                                    style="padding: 12px 24px; background: var(--success); border: none; border-radius: 8px; color: white; cursor: pointer; font-size: 14px; font-weight: 600;">
                                💾 Save All Changes
                            </button>
                        </div>
                    </div>
                    
                    <!-- File Browser -->
                    <div style="background: var(--bg); padding: 20px; border-radius: 12px; margin-bottom: 20px;">
                        <h4 style="margin: 0 0 16px 0; font-size: 14px; font-weight: 600; text-transform: uppercase; color: var(--text-muted);">Agent Files</h4>
                        <div id="agent-files-list" style="display: grid; gap: 8px;">
                            ${agent.files.map(file => `
                                <div onclick="app.loadAgentV2File('${agentId}', '${file.path}')"
                                     style="padding: 10px; background: var(--bg-darker); border-radius: 6px; cursor: pointer; transition: all 0.2s; border-left: 3px solid ${this.getFileTypeColor(file.type)};"
                                     onmouseover="this.style.background='var(--bg)'"
                                     onmouseout="this.style.background='var(--bg-darker)'">
                                    <div style="display: flex; justify-content: space-between; align-items: center;">
                                        <div>
                                            <div style="font-weight: 600; font-size: 13px;">${this.getFileIcon(file.type)} ${file.name}</div>
                                            <div style="font-size: 11px; color: var(--text-muted);">${file.path}</div>
                                        </div>
                                        <div style="font-size: 11px; color: var(--text-muted);">
                                            ${this.formatFileSize(file.size)}
                                        </div>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                    
                    <!-- File Editor -->
                    <div id="agent-file-editor" style="background: var(--bg); padding: 20px; border-radius: 12px; display: none;">
                        <!-- Content loaded dynamically -->
                    </div>
                    
                    <!-- Config Editor -->
                    <div style="background: var(--bg); padding: 20px; border-radius: 12px;">
                        <h4 style="margin: 0 0 16px 0; font-size: 14px; font-weight: 600; text-transform: uppercase; color: var(--text-muted);">YAML Configuration</h4>
                        <textarea id="agent-config-yaml" 
                                  style="width: 100%; min-height: 400px; padding: 12px; background: var(--bg-darker); border: 2px solid var(--border); border-radius: 6px; color: var(--text); font-size: 12px; font-family: 'Courier New', monospace; resize: vertical;">${this.yamlStringify(agent.config)}</textarea>
                    </div>
                </div>
            `;
            
        } catch (error) {
            this.addSystemMessage(`Failed to load editor: ${error.message}`, 'error');
        }
    };

    VeraChat.prototype.loadAgentV2File = async function(agentId, filePath) {
        try {
            const response = await fetch(`${this.agentsV2State.apiUrl}/${agentId}/files/${filePath}`);
            
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const content = await response.text();
            
            const editorContainer = document.getElementById('agent-file-editor');
            if (!editorContainer) return;
            
            editorContainer.style.display = 'block';
            editorContainer.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                    <h4 style="margin: 0; font-size: 14px; font-weight: 600; text-transform: uppercase; color: var(--text-muted);">
                        Editing: ${filePath}
                    </h4>
                    <button onclick="app.saveAgentV2File('${agentId}', '${filePath}')" 
                            style="padding: 8px 16px; background: var(--success); border: none; border-radius: 6px; color: white; cursor: pointer; font-size: 13px; font-weight: 600;">
                        💾 Save File
                    </button>
                </div>
                <textarea id="agent-file-content" 
                          style="width: 100%; min-height: 400px; padding: 12px; background: var(--bg-darker); border: 2px solid var(--border); border-radius: 6px; color: var(--text); font-size: 12px; font-family: 'Courier New', monospace; resize: vertical;">${this.escapeHtml(content)}</textarea>
            `;
            
            this.agentsV2State.editingFile = filePath;
            
        } catch (error) {
            this.addSystemMessage(`Failed to load file: ${error.message}`, 'error');
        }
    };

    VeraChat.prototype.saveAgentV2File = async function(agentId, filePath) {
        try {
            const content = document.getElementById('agent-file-content')?.value;
            if (!content) {
                throw new Error('No content to save');
            }
            
            // Determine endpoint based on file type
            let endpoint;
            if (filePath.endsWith('.j2')) {
                endpoint = `${this.agentsV2State.apiUrl}/${agentId}/template`;
            } else {
                this.addSystemMessage('Direct file saving not yet implemented for non-template files', 'warning');
                return;
            }
            
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content })
            });
            
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            this.addSystemMessage(data.message, 'success');
            
        } catch (error) {
            this.addSystemMessage(`Failed to save file: ${error.message}`, 'error');
        }
    };

    VeraChat.prototype.saveAgentV2Config = async function(agentId) {
        try {
            const yamlContent = document.getElementById('agent-config-yaml')?.value;
            if (!yamlContent) {
                throw new Error('No config to save');
            }
            
            // Parse YAML
            const config = jsyaml.load(yamlContent);
            
            const response = await fetch(`${this.agentsV2State.apiUrl}/${agentId}/config`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });
            
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            this.addSystemMessage(data.message, 'success');
            
            // Also save file content if editing
            if (this.agentsV2State.editingFile) {
                await this.saveAgentV2File(agentId, this.agentsV2State.editingFile);
            }
            
            // Refresh
            await this.refreshAgentsV2();
            
        } catch (error) {
            this.addSystemMessage(`Failed to save config: ${error.message}`, 'error');
        }
    };

    // ========================================================================
    // CREATE AGENT DIALOG
    // ========================================================================
    
    VeraChat.prototype.showCreateAgentV2Dialog = function() {
        const modalHtml = `
            <div class="modal-overlay" onclick="this.remove()" style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.8); z-index: 10000; display: flex; align-items: center; justify-content: center; padding: 20px;">
                <div onclick="event.stopPropagation()" style="background: var(--bg); border-radius: 12px; padding: 24px; max-width: 600px; width: 100%; box-shadow: 0 4px 20px rgba(0,0,0,0.5);">
                    <h2 style="margin: 0 0 20px 0; font-size: 20px;">➕ Create New Agent</h2>
                    
                    <div style="display: grid; gap: 16px;">
                        <div>
                            <label style="display: block; margin-bottom: 6px; font-size: 13px; font-weight: 600;">Agent ID (directory name)</label>
                            <input type="text" id="new-agent-id" placeholder="my_agent"
                                   style="width: 100%; padding: 10px; background: var(--bg-darker); border: 2px solid var(--border); border-radius: 6px; color: var(--text); font-size: 13px;">
                            <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">Use lowercase, underscores, no spaces</div>
                        </div>
                        
                        <div>
                            <label style="display: block; margin-bottom: 6px; font-size: 13px; font-weight: 600;">Display Name</label>
                            <input type="text" id="new-agent-name" placeholder="My Agent"
                                   style="width: 100%; padding: 10px; background: var(--bg-darker); border: 2px solid var(--border); border-radius: 6px; color: var(--text); font-size: 13px;">
                        </div>
                        
                        <div>
                            <label style="display: block; margin-bottom: 6px; font-size: 13px; font-weight: 600;">Description</label>
                            <textarea id="new-agent-description" placeholder="What does this agent do?"
                                      style="width: 100%; min-height: 80px; padding: 10px; background: var(--bg-darker); border: 2px solid var(--border); border-radius: 6px; color: var(--text); font-size: 13px; resize: vertical;"></textarea>
                        </div>
                        
                        <div>
                            <label style="display: block; margin-bottom: 6px; font-size: 13px; font-weight: 600;">Base Model</label>
                            <select id="new-agent-model"
                                    style="width: 100%; padding: 10px; background: var(--bg-darker); border: 2px solid var(--border); border-radius: 6px; color: var(--text); font-size: 13px;">
                                <option value="gemma2">Gemma 2</option>
                                <option value="llama3.1">Llama 3.1</option>
                                <option value="qwen2.5">Qwen 2.5</option>
                                <option value="mistral">Mistral</option>
                                <option value="deepseek-coder-v2">DeepSeek Coder V2</option>
                            </select>
                        </div>
                    </div>
                    
                    <div style="display: flex; gap: 12px; margin-top: 24px;">
                        <button onclick="app.createAgentV2()" 
                                style="flex: 1; padding: 12px; background: var(--success); border: none; border-radius: 8px; color: white; cursor: pointer; font-size: 14px; font-weight: 600;">
                            ✓ Create Agent
                        </button>
                        <button onclick="this.closest('.modal-overlay').remove()" 
                                style="flex: 1; padding: 12px; background: var(--bg-darker); border: none; border-radius: 8px; color: var(--text); cursor: pointer; font-size: 14px; font-weight: 600;">
                            Cancel
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', modalHtml);
    };

    VeraChat.prototype.createAgentV2 = async function() {
        try {
            const agentId = document.getElementById('new-agent-id')?.value.trim();
            const name = document.getElementById('new-agent-name')?.value.trim();
            const description = document.getElementById('new-agent-description')?.value.trim();
            const baseModel = document.getElementById('new-agent-model')?.value;
            
            if (!agentId) {
                this.addSystemMessage('Agent ID is required', 'error');
                return;
            }
            
            if (!/^[a-z0-9_]+$/.test(agentId)) {
                this.addSystemMessage('Agent ID must be lowercase letters, numbers, and underscores only', 'error');
                return;
            }
            
            const response = await fetch(`${this.agentsV2State.apiUrl}/new`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: agentId,
                    description: description,
                    base_model: baseModel
                })
            });
            
            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.detail || `HTTP ${response.status}`);
            }
            
            const data = await response.json();
            this.addSystemMessage(data.message, 'success');
            
            // Close modal
            document.querySelector('.modal-overlay')?.remove();
            
            // Refresh and select new agent
            await this.refreshAgentsV2();
            this.selectAgentV2(agentId);
            this.editAgentV2(agentId);
            
        } catch (error) {
            this.addSystemMessage(`Failed to create agent: ${error.message}`, 'error');
        }
    };

    // ========================================================================
    // BUILD PANEL
    // ========================================================================
    
    VeraChat.prototype.loadAgentV2BuildPanel = async function() {
        const container = document.getElementById('agents-build-content');
        if (!container) return;
        
        container.innerHTML = `
            <div style="max-width: 900px;">
                <div style="background: var(--bg-darker); padding: 20px; border-radius: 12px; margin-bottom: 20px;">
                    <h3 style="margin: 0 0 8px 0; font-size: 18px; font-weight: 600;">🔨 Build Agents</h3>
                    <p style="margin: 0; font-size: 13px; color: var(--text-muted);">Build Modelfiles and create Ollama models</p>
                </div>
                
                <div style="display: grid; gap: 16px; margin-bottom: 20px;">
                    <button onclick="app.buildAllAgentsV2(false)" 
                            style="padding: 16px; background: var(--accent); border: none; border-radius: 8px; color: white; cursor: pointer; font-size: 14px; font-weight: 600;">
                        🔨 Build All Modelfiles
                    </button>
                    <button onclick="app.buildAllAgentsV2(true)" 
                            style="padding: 16px; background: var(--success); border: none; border-radius: 8px; color: white; cursor: pointer; font-size: 14px; font-weight: 600;">
                        🚀 Build All + Create Ollama Models
                    </button>
                </div>
                
                <div id="build-status" style="background: var(--bg); padding: 20px; border-radius: 12px;">
                    <p style="color: var(--text-muted);">Select a build option to begin</p>
                </div>
            </div>
        `;
    };

    VeraChat.prototype.buildAllAgentsV2 = async function(createModels = false) {
        try {
            const statusDiv = document.getElementById('build-status');
            if (statusDiv) {
                statusDiv.innerHTML = '<p>Building agents...</p>';
            }
            
            this.addSystemMessage('Building all agents...', 'info');
            
            const response = await fetch(`${this.agentsV2State.apiUrl}/build-all?create_models=${createModels}`, {
                method: 'POST'
            });
            
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            
            this.addSystemMessage(data.message, 'success');
            
            if (statusDiv) {
                let html = '<h4 style="margin: 0 0 12px 0;">Build Results</h4>';
                html += '<div style="display: grid; gap: 8px;">';
                
                data.results.forEach(result => {
                    html += `
                        <div style="padding: 10px; background: var(--bg-darker); border-radius: 6px; border-left: 3px solid var(--success);">
                            <div style="font-weight: 600;">${result.agent_name}</div>
                            <div style="font-size: 11px; color: var(--text-muted);">Base: ${result.base_model}</div>
                        </div>
                    `;
                });
                
                html += '</div>';
                statusDiv.innerHTML = html;
            }
            
            // Refresh
            await this.refreshAgentsV2();
            
        } catch (error) {
            this.addSystemMessage(`Build failed: ${error.message}`, 'error');
        }
    };

    // ========================================================================
    // SYSTEM PANEL
    // ========================================================================
    
    VeraChat.prototype.loadAgentV2SystemPanel = function() {
        const container = document.getElementById('agents-system-content');
        if (!container) return;
        
        const info = this.agentsV2State.systemInfo;
        
        container.innerHTML = `
            <div style="max-width: 900px;">
                <div style="background: var(--bg-darker); padding: 20px; border-radius: 12px; margin-bottom: 20px;">
                    <h3 style="margin: 0 0 8px 0; font-size: 18px; font-weight: 600;">⚙️ System Information</h3>
                    <p style="margin: 0; font-size: 13px; color: var(--text-muted);">Agent system configuration and paths</p>
                </div>
                
                ${info ? `
                    <div style="display: grid; gap: 16px;">
                        <div style="background: var(--bg); padding: 20px; border-radius: 12px;">
                            <h4 style="margin: 0 0 12px 0; font-size: 14px; font-weight: 600; text-transform: uppercase; color: var(--text-muted);">Paths</h4>
                            <div style="display: grid; gap: 8px; font-family: monospace; font-size: 12px;">
                                <div>
                                    <strong>Agents:</strong><br>
                                    <code style="color: var(--accent);">${info.paths?.agents_dir || 'N/A'}</code>
                                </div>
                                <div>
                                    <strong>Templates:</strong><br>
                                    <code style="color: var(--accent);">${info.paths?.templates_dir || 'N/A'}</code>
                                </div>
                                <div>
                                    <strong>Build:</strong><br>
                                    <code style="color: var(--accent);">${info.paths?.build_dir || 'N/A'}</code>
                                </div>
                            </div>
                        </div>
                        
                        <div style="background: var(--bg); padding: 20px; border-radius: 12px;">
                            <h4 style="margin: 0 0 12px 0; font-size: 14px; font-weight: 600; text-transform: uppercase; color: var(--text-muted);">Counts</h4>
                            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px;">
                                <div style="padding: 12px; background: var(--bg-darker); border-radius: 6px; text-align: center;">
                                    <div style="font-size: 24px; font-weight: 700; color: var(--accent);">${info.counts?.agents || 0}</div>
                                    <div style="font-size: 11px; color: var(--text-muted);">Agents</div>
                                </div>
                                <div style="padding: 12px; background: var(--bg-darker); border-radius: 6px; text-align: center;">
                                    <div style="font-size: 24px; font-weight: 700; color: var(--success);">${info.counts?.shared_templates || 0}</div>
                                    <div style="font-size: 11px; color: var(--text-muted);">Templates</div>
                                </div>
                                <div style="padding: 12px; background: var(--bg-darker); border-radius: 6px; text-align: center;">
                                    <div style="font-size: 24px; font-weight: 700; color: var(--warning);">${info.counts?.modelfiles || 0}</div>
                                    <div style="font-size: 11px; color: var(--text-muted);">Modelfiles</div>
                                </div>
                            </div>
                        </div>
                        
                        <div style="background: var(--bg); padding: 20px; border-radius: 12px;">
                            <h4 style="margin: 0 0 12px 0; font-size: 14px; font-weight: 600; text-transform: uppercase; color: var(--text-muted);">Status</h4>
                            <div style="display: flex; align-items: center; gap: 12px;">
                                <div style="width: 12px; height: 12px; background: ${info.agent_manager_available ? 'var(--success)' : 'var(--danger)'}; border-radius: 50%;"></div>
                                <span>AgentManager: ${info.agent_manager_available ? 'Available' : 'Not Available'}</span>
                            </div>
                        </div>
                    </div>
                ` : '<p style="color: var(--text-muted);">Loading system information...</p>'}
            </div>
        `;
    };

    // ========================================================================
    // UTILITY FUNCTIONS
    // ========================================================================
    
    VeraChat.prototype.getFileTypeColor = function(type) {
        const colors = {
            'yaml': 'var(--accent)',
            'template': 'var(--success)',
            'text': 'var(--info)',
            'other': 'var(--text-muted)'
        };
        return colors[type] || colors.other;
    };

    VeraChat.prototype.getFileIcon = function(type) {
        const icons = {
            'yaml': '⚙️',
            'template': '📝',
            'text': '📄',
            'other': '📎'
        };
        return icons[type] || icons.other;
    };

    VeraChat.prototype.formatFileSize = function(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    };

    VeraChat.prototype.yamlStringify = function(obj) {
        // Simple YAML stringification - in production use js-yaml
        return JSON.stringify(obj, null, 2);
    };

    VeraChat.prototype.escapeHtml = function(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    };

    // ========================================================================
    // CLEANUP
    // ========================================================================
    
    VeraChat.prototype.cleanupAgentsV2 = function() {
        console.log('Cleaning up Agents V2 UI...');
        this.stopAgentsV2Updates();
    };

    // ========================================================================
    // AGENT EDITOR - ENHANCED
    // ========================================================================
    
    VeraChat.prototype.loadAgentV2Editor = async function(agentId) {
        const container = document.getElementById('agents-editor-content');
        if (!container) return;
        
        container.innerHTML = '<div style="text-align: center; padding: 48px;">⏳ Loading editor...</div>';
        
        try {
            const data = await this.apiCallV2(`/${agentId}`);
            const agent = data.agent;
            
            container.innerHTML = `
                <div style="max-width: 1400px;">
                    <!-- Header with Actions -->
                    <div style="background: var(--bg-darker); padding: 20px; border-radius: 12px; margin-bottom: 20px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
                            <div>
                                <h3 style="margin: 0 0 8px 0; font-size: 18px; font-weight: 600;">${agent.config.name}</h3>
                                <p style="margin: 0; font-size: 13px; color: var(--text-muted);">${agent.config.description || 'No description'}</p>
                            </div>
                            <div style="display: flex; gap: 8px;">
                                <button onclick="app.buildAgentV2('${agentId}', false)" 
                                        style="padding: 10px 16px; background: var(--warning); border: none; border-radius: 6px; color: white; cursor: pointer; font-size: 13px; font-weight: 600;">
                                    🔨 Quick Build
                                </button>
                                <button onclick="app.saveAgentV2All('${agentId}')" 
                                        style="padding: 10px 24px; background: var(--success); border: none; border-radius: 8px; color: white; cursor: pointer; font-size: 14px; font-weight: 600;">
                                    💾 Save All Changes
                                </button>
                            </div>
                        </div>
                    </div>
                    
                    <div style="display: grid; grid-template-columns: 300px 1fr; gap: 20px;">
                        <!-- File Browser Sidebar -->
                        <div style="background: var(--bg); padding: 20px; border-radius: 12px; height: fit-content;">
                            <h4 style="margin: 0 0 16px 0; font-size: 14px; font-weight: 600; text-transform: uppercase; color: var(--text-muted);">
                                📁 Files
                            </h4>
                            <div id="agent-files-tree" style="display: grid; gap: 4px;">
                                ${agent.files.map(file => `
                                    <div onclick="app.loadAgentV2File('${agentId}', '${file.path}')"
                                         class="file-item ${this.agentsV2State.editingFile === file.path ? 'active' : ''}"
                                         style="padding: 8px 10px; background: ${this.agentsV2State.editingFile === file.path ? 'var(--accent)' : 'var(--bg-darker)'}; border-radius: 6px; cursor: pointer; transition: all 0.2s; border-left: 3px solid ${this.getFileTypeColor(file.type)};"
                                         onmouseover="if(!this.classList.contains('active')) this.style.background='rgba(59, 130, 246, 0.1)'"
                                         onmouseout="if(!this.classList.contains('active')) this.style.background='var(--bg-darker)'">
                                        <div style="font-weight: 600; font-size: 12px; color: ${this.agentsV2State.editingFile === file.path ? 'white' : 'var(--text)'};">
                                            ${this.getFileIcon(file.type)} ${file.name}
                                        </div>
                                        <div style="font-size: 10px; color: ${this.agentsV2State.editingFile === file.path ? 'rgba(255,255,255,0.8)' : 'var(--text-muted)'};">
                                            ${this.formatFileSize(file.size)}
                                        </div>
                                    </div>
                                `).join('')}
                            </div>
                            
                            <!-- File Actions -->
                            <div style="margin-top: 16px; padding-top: 16px; border-top: 2px solid var(--border);">
                                <button onclick="app.createNewFile('${agentId}')" 
                                        style="width: 100%; padding: 8px; background: var(--accent); border: none; border-radius: 6px; color: white; cursor: pointer; font-size: 12px; font-weight: 600;">
                                    ➕ New File
                                </button>
                            </div>
                        </div>
                        
                        <!-- Main Editor Area -->
                        <div style="display: grid; gap: 20px;">
                            <!-- File Editor -->
                            <div id="agent-file-editor" style="background: var(--bg); padding: 20px; border-radius: 12px; display: none;">
                                <!-- Loaded dynamically -->
                            </div>
                            
                            <!-- Config Editor -->
                            <div style="background: var(--bg); padding: 20px; border-radius: 12px;">
                                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                                    <h4 style="margin: 0; font-size: 14px; font-weight: 600; text-transform: uppercase; color: var(--text-muted);">
                                        ⚙️ YAML Configuration
                                    </h4>
                                    <div style="display: flex; gap: 8px;">
                                        <button onclick="app.formatYAML('${agentId}')" 
                                                style="padding: 6px 12px; background: var(--bg-darker); border: none; border-radius: 6px; color: var(--text); cursor: pointer; font-size: 11px; font-weight: 600;">
                                            ✨ Format
                                        </button>
                                        <button onclick="app.validateYAML('${agentId}')" 
                                                style="padding: 6px 12px; background: #9333ea; border: none; border-radius: 6px; color: white; cursor: pointer; font-size: 11px; font-weight: 600;">
                                            ✓ Validate
                                        </button>
                                    </div>
                                </div>
                                <textarea id="agent-config-yaml" 
                                          style="width: 100%; min-height: 400px; padding: 14px; background: var(--bg-darker); border: 2px solid var(--border); border-radius: 8px; color: var(--text); font-size: 12px; font-family: 'Courier New', monospace; resize: vertical; line-height: 1.6;">${this.yamlStringify(agent.config)}</textarea>
                                
                                <!-- Quick Stats -->
                                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 16px;">
                                    <div style="padding: 10px; background: var(--bg-darker); border-radius: 6px; text-align: center;">
                                        <div style="font-size: 18px; font-weight: 700; color: var(--accent);">${agent.config.num_ctx}</div>
                                        <div style="font-size: 10px; color: var(--text-muted);">Context</div>
                                    </div>
                                    <div style="padding: 10px; background: var(--bg-darker); border-radius: 6px; text-align: center;">
                                        <div style="font-size: 18px; font-weight: 700; color: var(--success);">${agent.config.parameters?.temperature || 0.7}</div>
                                        <div style="font-size: 10px; color: var(--text-muted);">Temp</div>
                                    </div>
                                    <div style="padding: 10px; background: var(--bg-darker); border-radius: 6px; text-align: center;">
                                        <div style="font-size: 18px; font-weight: 700; color: var(--warning);">${agent.config.tools?.length || 'All'}</div>
                                        <div style="font-size: 10px; color: var(--text-muted);">Tools</div>
                                    </div>
                                    <div style="padding: 10px; background: var(--bg-darker); border-radius: 6px; text-align: center;">
                                        <div style="font-size: 18px; font-weight: 700; color: var(--info);">${agent.config.capabilities?.length || 0}</div>
                                        <div style="font-size: 10px; color: var(--text-muted);">Capabilities</div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            
            // Auto-load the main template if no file is being edited
            if (!this.agentsV2State.editingFile) {
                const mainTemplate = agent.files.find(f => f.name.includes('template'));
                if (mainTemplate) {
                    this.loadAgentV2File(agentId, mainTemplate.path);
                }
            }
            
        } catch (error) {
            this.addSystemMessage(`Failed to load editor: ${error.message}`, 'error');
            container.innerHTML = `
                <div style="text-align: center; padding: 48px; color: var(--danger);">
                    <div style="font-size: 48px; margin-bottom: 16px;">❌</div>
                    <h3 style="margin: 0 0 8px 0;">Failed to Load Editor</h3>
                    <p style="margin: 0;">${error.message}</p>
                </div>
            `;
        }
    };

    VeraChat.prototype.loadAgentV2File = async function(agentId, filePath) {
        try {
            const response = await fetch(`${this.agentsV2State.apiUrl}/${agentId}/files/${filePath}`);
            
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const content = await response.text();
            
            const editorContainer = document.getElementById('agent-file-editor');
            if (!editorContainer) return;
            
            // Detect file type for syntax highlighting hints
            const ext = filePath.split('.').pop();
            const isYAML = ext === 'yaml' || ext === 'yml';
            const isTemplate = ext === 'j2';
            const isJSON = ext === 'json';
            
            editorContainer.style.display = 'block';
            editorContainer.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                    <div>
                        <h4 style="margin: 0; font-size: 14px; font-weight: 600; text-transform: uppercase; color: var(--text-muted);">
                            ${isTemplate ? '📝' : isYAML ? '⚙️' : isJSON ? '📊' : '📄'} ${filePath}
                        </h4>
                        <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">
                            ${isTemplate ? 'Jinja2 Template' : isYAML ? 'YAML Configuration' : isJSON ? 'JSON Data' : 'Text File'}
                        </div>
                    </div>
                    <div style="display: flex; gap: 8px;">
                        <button onclick="app.previewTemplate('${agentId}')" 
                                style="padding: 6px 12px; background: #9333ea; border: none; border-radius: 6px; color: white; cursor: pointer; font-size: 11px; font-weight: 600;"
                                ${!isTemplate ? 'disabled style="opacity: 0.5; cursor: not-allowed;"' : ''}>
                            👁️ Preview
                        </button>
                        <button onclick="app.saveAgentV2File('${agentId}', '${filePath}')" 
                                style="padding: 6px 12px; background: var(--success); border: none; border-radius: 6px; color: white; cursor: pointer; font-size: 11px; font-weight: 600;">
                            💾 Save File
                        </button>
                    </div>
                </div>
                
                <!-- Editor with line numbers -->
                <div style="position: relative;">
                    <textarea id="agent-file-content" 
                              style="width: 100%; min-height: 500px; padding: 14px; padding-left: 50px; background: var(--bg-darker); border: 2px solid var(--border); border-radius: 8px; color: var(--text); font-size: 12px; font-family: 'Courier New', monospace; resize: vertical; line-height: 1.8;"
                              spellcheck="false">${this.escapeHtml(content)}</textarea>
                    
                    <!-- Character/Line Count -->
                    <div style="margin-top: 8px; font-size: 11px; color: var(--text-muted); display: flex; justify-content: space-between;">
                        <span id="file-stats">${content.length} characters, ${content.split('\n').length} lines</span>
                        <span>${this.formatFileSize(content.length)}</span>
                    </div>
                </div>
                
                ${isTemplate ? `
                    <div style="margin-top: 12px; padding: 12px; background: rgba(59, 130, 246, 0.1); border-radius: 6px; border-left: 4px solid var(--accent);">
                        <div style="font-size: 12px; font-weight: 600; margin-bottom: 6px;">Jinja2 Template Tips:</div>
                        <div style="font-size: 11px; color: var(--text-muted); line-height: 1.6;">
                            • Variables: <code style="background: var(--bg-darker); padding: 2px 6px; border-radius: 3px;">{{ variable }}</code><br>
                            • Conditionals: <code style="background: var(--bg-darker); padding: 2px 6px; border-radius: 3px;">{% if condition %} ... {% endif %}</code><br>
                            • Loops: <code style="background: var(--bg-darker); padding: 2px 6px; border-radius: 3px;">{% for item in items %} ... {% endfor %}</code><br>
                            • Include: <code style="background: var(--bg-darker); padding: 2px 6px; border-radius: 3px;">{{ include_file('file.txt') }}</code>
                        </div>
                    </div>
                ` : ''}
            `;
            
            this.agentsV2State.editingFile = filePath;
            
            // Update file tree highlighting
            document.querySelectorAll('.file-item').forEach(item => {
                item.classList.remove('active');
                item.style.background = 'var(--bg-darker)';
            });
            
            // Update character count on typing
            const textarea = document.getElementById('agent-file-content');
            if (textarea) {
                textarea.addEventListener('input', () => {
                    const stats = document.getElementById('file-stats');
                    if (stats) {
                        const text = textarea.value;
                        stats.textContent = `${text.length} characters, ${text.split('\n').length} lines`;
                    }
                });
            }
            
        } catch (error) {
            this.addSystemMessage(`Failed to load file: ${error.message}`, 'error');
        }
    };

    VeraChat.prototype.previewTemplate = async function(agentId) {
        try {
            // Build agent to render template
            await this.buildAgentV2(agentId, false);
            
            // Get rendered prompt
            const response = await fetch(`${this.agentsV2State.apiUrl}/${agentId}/modelfile`);
            const modelfile = await response.text();
            
            // Extract SYSTEM section
            const systemMatch = modelfile.match(/SYSTEM """([\s\S]*?)"""/);
            const systemPrompt = systemMatch ? systemMatch[1] : 'Could not extract system prompt';
            
            this.createModal(`Template Preview: ${agentId}`, `
                <div style="margin-bottom: 16px;">
                    <div style="padding: 10px; background: rgba(34, 197, 94, 0.1); border-radius: 6px; border-left: 4px solid var(--success);">
                        <div style="font-size: 12px; font-weight: 600; color: var(--success);">✓ Template Rendered Successfully</div>
                        <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">
                            ${systemPrompt.length} characters, ${systemPrompt.split('\n').length} lines
                        </div>
                    </div>
                </div>
                <pre style="background: var(--bg-darker); padding: 16px; border-radius: 8px; overflow-x: auto; max-height: 600px; font-size: 12px; line-height: 1.6; white-space: pre-wrap;">${this.escapeHtml(systemPrompt)}</pre>
            `, '900px');
            
        } catch (error) {
            this.addSystemMessage(`Preview failed: ${error.message}`, 'error');
        }
    };

    VeraChat.prototype.saveAgentV2File = async function(agentId, filePath) {
        try {
            const content = document.getElementById('agent-file-content')?.value;
            if (content === undefined) {
                throw new Error('No content to save');
            }
            
            if (filePath.endsWith('.j2')) {
                await this.apiCallV2(`/${agentId}/template`, {
                    method: 'POST',
                    body: JSON.stringify({ content })
                });
            } else {
                this.addSystemMessage('Direct file saving only supported for templates currently', 'warning');
                return;
            }
            
            this.addSystemMessage(`✓ Saved: ${filePath}`, 'success');
            
        } catch (error) {
            this.addSystemMessage(`Save failed: ${error.message}`, 'error');
        }
    };

VeraChat.prototype.apiCallV2 = async function(endpoint, options = {}) {
    /**
     * Unified API call wrapper for Agents V2 API
     * 
     * @param {string} endpoint - API endpoint (e.g., '/list', '/{id}/build')
     * @param {object} options - Fetch options (method, body, headers, etc.)
     * @returns {Promise<object>} - Parsed JSON response
     * @throws {Error} - On API errors
     * 
     * Usage:
     *   const data = await this.apiCallV2('/list');
     *   const data = await this.apiCallV2('/new', {
     *       method: 'POST',
     *       body: JSON.stringify({ name: 'agent' })
     *   });
     */
    
    const url = `${this.agentsV2State.apiUrl}${endpoint}`;
    
    try {
        const response = await fetch(url, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            }
        });
        
        if (!response.ok) {
            // Try to get error details from response
            const data = await response.json().catch(() => ({}));
            throw new Error(data.detail || `HTTP ${response.status}`);
        }
        
        return await response.json();
        
    } catch (error) {
        console.error(`API call failed: ${endpoint}`, error);
        throw error;
    }
};
    VeraChat.prototype.saveAgentV2All = async function(agentId) {
        try {
            // Save YAML config
            const yamlContent = document.getElementById('agent-config-yaml')?.value;
            if (yamlContent) {
                const config = jsyaml.load(yamlContent);
                await this.apiCallV2(`/${agentId}/config`, {
                    method: 'POST',
                    body: JSON.stringify(config)
                });
            }
            
            // Save current file if editing
            if (this.agentsV2State.editingFile) {
                await this.saveAgentV2File(agentId, this.agentsV2State.editingFile);
            }
            
            this.addSystemMessage('✓ All changes saved', 'success');
            await this.refreshAgentsV2();
            
        } catch (error) {
            this.addSystemMessage(`Save failed: ${error.message}`, 'error');
        }
    };

    VeraChat.prototype.formatYAML = function(agentId) {
        try {
            const textarea = document.getElementById('agent-config-yaml');
            if (!textarea) return;
            
            const parsed = jsyaml.load(textarea.value);
            const formatted = jsyaml.dump(parsed, {
                indent: 2,
                lineWidth: 80,
                noRefs: true
            });
            
            textarea.value = formatted;
            this.addSystemMessage('✓ YAML formatted', 'success');
            
        } catch (error) {
            this.addSystemMessage(`Format failed: ${error.message}`, 'error');
        }
    };

    VeraChat.prototype.validateYAML = async function(agentId) {
        try {
            const textarea = document.getElementById('agent-config-yaml');
            if (!textarea) return;
            
            // Try to parse YAML
            const parsed = jsyaml.load(textarea.value);
            
            // Validate with API
            const result = await this.apiCallV2(`/${agentId}/validate`, {
                method: 'POST'
            });
            
            if (result.valid) {
                this.addSystemMessage('✓ YAML is valid', 'success');
            } else {
                this.addSystemMessage('⚠️ Validation issues found', 'warning');
                result.issues.forEach(issue => {
                    this.addSystemMessage(`  • ${issue}`, 'warning');
                });
            }
            
        } catch (error) {
            this.addSystemMessage(`Validation failed: ${error.message}`, 'error');
        }
    };

    VeraChat.prototype.createNewFile = function(agentId) {
        const fileName = prompt('Enter file name (e.g., notes.txt, data.json):');
        if (!fileName) return;
        
        this.addSystemMessage('File creation UI coming soon', 'info');
    };

    // ========================================================================
    // BUILD PANEL
    // ========================================================================
    
    VeraChat.prototype.loadAgentV2BuildPanel = async function() {
        const container = document.getElementById('agents-build-content');
        if (!container) return;
        
        container.innerHTML = `
            <div style="max-width: 1000px;">
                <div style="background: var(--bg-darker); padding: 20px; border-radius: 12px; margin-bottom: 20px;">
                    <h3 style="margin: 0 0 8px 0; font-size: 18px; font-weight: 600;">🔨 Build System</h3>
                    <p style="margin: 0; font-size: 13px; color: var(--text-muted);">Build Modelfiles and create Ollama models</p>
                </div>
                
                <!-- Build Options -->
                <div style="display: grid; gap: 16px; margin-bottom: 24px;">
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
                        <button onclick="app.buildAllAgentsV2(false)" 
                                style="padding: 20px; background: var(--accent); border: none; border-radius: 12px; color: white; cursor: pointer; text-align: left; transition: all 0.2s;"
                                onmouseover="this.style.transform='scale(1.02)'"
                                onmouseout="this.style.transform='scale(1)'">
                            <div style="font-size: 32px; margin-bottom: 8px;">🔨</div>
                            <div style="font-size: 16px; font-weight: 600; margin-bottom: 4px;">Build All Modelfiles</div>
                            <div style="font-size: 12px; opacity: 0.9;">Fast - Only generates Modelfiles (~2s per agent)</div>
                        </button>
                        
                        <button onclick="app.buildAllAgentsV2(true)" 
                                style="padding: 20px; background: var(--success); border: none; border-radius: 12px; color: white; cursor: pointer; text-align: left; transition: all 0.2s;"
                                onmouseover="this.style.transform='scale(1.02)'"
                                onmouseout="this.style.transform='scale(1)'">
                            <div style="font-size: 32px; margin-bottom: 8px;">🚀</div>
                            <div style="font-size: 16px; font-weight: 600; margin-bottom: 4px;">Build + Create Ollama Models</div>
                            <div style="font-size: 12px; opacity: 0.9;">Slower - Creates actual models (~30s per agent)</div>
                        </button>
                    </div>
                    
                    <button onclick="app.showSelectiveBuildDialog()" 
                            style="padding: 16px; background: var(--bg); border: 2px solid var(--border); border-radius: 12px; color: var(--text); cursor: pointer; font-size: 14px; font-weight: 600;">
                        🎯 Selective Build...
                    </button>
                </div>
                
                <!-- Build Status -->
                <div id="build-status" style="background: var(--bg); padding: 20px; border-radius: 12px;">
                    <h4 style="margin: 0 0 12px 0; font-size: 14px; font-weight: 600; text-transform: uppercase; color: var(--text-muted);">
                        Build Status
                    </h4>
                    <p style="color: var(--text-muted); font-size: 13px;">Select a build option to begin</p>
                </div>
            </div>
        `;
    };

    VeraChat.prototype.buildAllAgentsV2 = async function(createModels = false) {
        try {
            const statusDiv = document.getElementById('build-status');
            if (statusDiv) {
                statusDiv.innerHTML = `
                    <h4 style="margin: 0 0 12px 0; font-size: 14px; font-weight: 600; text-transform: uppercase; color: var(--text-muted);">
                        Building...
                    </h4>
                    <div style="padding: 16px; background: rgba(59, 130, 246, 0.1); border-radius: 6px;">
                        <div style="font-size: 24px; margin-bottom: 8px;">⏳</div>
                        <div style="font-size: 14px; font-weight: 600;">Building ${this.agentsV2State.agents.length} agents...</div>
                        <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">
                            ${createModels ? 'Creating Ollama models (this may take several minutes)' : 'Generating Modelfiles'}
                        </div>
                    </div>
                `;
            }
            
            this.addSystemMessage(`Building ${this.agentsV2State.agents.length} agents...`, 'info');
            
            const data = await this.apiCallV2(`/build-all?create_models=${createModels}`, {
                method: 'POST'
            });
            
            this.addSystemMessage(data.message, 'success');
            
            if (statusDiv) {
                let html = `
                    <h4 style="margin: 0 0 12px 0; font-size: 14px; font-weight: 600; text-transform: uppercase; color: var(--success);">
                        ✓ Build Complete
                    </h4>
                    <div style="padding: 12px; background: rgba(34, 197, 94, 0.1); border-radius: 6px; margin-bottom: 16px;">
                        <div style="font-size: 14px; font-weight: 600; color: var(--success);">${data.message}</div>
                    </div>
                    <div style="display: grid; gap: 8px;">
                `;
                
                data.results.forEach(result => {
                    html += `
                        <div style="padding: 12px; background: var(--bg-darker); border-radius: 6px; border-left: 4px solid var(--success);">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <div>
                                    <div style="font-weight: 600; font-size: 13px;">${result.agent_name}</div>
                                    <div style="font-size: 11px; color: var(--text-muted);">Base: ${result.base_model}</div>
                                </div>
                                <div style="color: var(--success); font-size: 18px;">✓</div>
                            </div>
                        </div>
                    `;
                });
                
                html += '</div>';
                statusDiv.innerHTML = html;
            }
            
            await this.refreshAgentsV2();
            
        } catch (error) {
            this.addSystemMessage(`Build failed: ${error.message}`, 'error');
            
            const statusDiv = document.getElementById('build-status');
            if (statusDiv) {
                statusDiv.innerHTML = `
                    <div style="padding: 16px; background: rgba(239, 68, 68, 0.1); border-radius: 6px;">
                        <div style="font-size: 24px; margin-bottom: 8px;">❌</div>
                        <div style="font-size: 14px; font-weight: 600; color: var(--danger);">Build Failed</div>
                        <div style="font-size: 12px; color: var(--danger); margin-top: 4px;">${error.message}</div>
                    </div>
                `;
            }
        }
    };

    VeraChat.prototype.showSelectiveBuildDialog = function() {
        const agents = this.agentsV2State.agents;
        
        let html = `
            <div style="margin-bottom: 16px;">
                <label style="display: flex; align-items: center; gap: 8px; padding: 10px; background: var(--bg-darker); border-radius: 6px; cursor: pointer;">
                    <input type="checkbox" id="select-all-agents" onchange="app.toggleAllAgents(this.checked)" style="width: 18px; height: 18px;">
                    <span style="font-weight: 600;">Select All</span>
                </label>
            </div>
            
            <div style="max-height: 400px; overflow-y: auto; margin-bottom: 16px;">
        `;
        
        agents.forEach(agent => {
            html += `
                <label style="display: flex; align-items: center; gap: 8px; padding: 10px; background: var(--bg-darker); border-radius: 6px; margin-bottom: 8px; cursor: pointer;">
                    <input type="checkbox" class="agent-select" value="${agent.id}" style="width: 18px; height: 18px;">
                    <div style="flex: 1;">
                        <div style="font-weight: 600; font-size: 13px;">${agent.name}</div>
                        <div style="font-size: 11px; color: var(--text-muted);">${agent.base_model}</div>
                    </div>
                </label>
            `;
        });
        
        html += `
            </div>
            
            <div style="display: flex; gap: 12px;">
                <button onclick="app.buildSelectedAgents(false)" 
                        style="flex: 1; padding: 12px; background: var(--accent); border: none; border-radius: 8px; color: white; cursor: pointer; font-size: 14px; font-weight: 600;">
                    🔨 Build Selected
                </button>
                <button onclick="app.buildSelectedAgents(true)" 
                        style="flex: 1; padding: 12px; background: var(--success); border: none; border-radius: 8px; color: white; cursor: pointer; font-size: 14px; font-weight: 600;">
                    🚀 Build + Ollama
                </button>
            </div>
        `;
        
        this.createModal('Selective Build', html, '500px');
    };

    VeraChat.prototype.toggleAllAgents = function(checked) {
        document.querySelectorAll('.agent-select').forEach(cb => {
            cb.checked = checked;
        });
    };

    VeraChat.prototype.buildSelectedAgents = async function(createModels) {
        const selected = Array.from(document.querySelectorAll('.agent-select:checked')).map(cb => cb.value);
        
        if (selected.length === 0) {
            this.addSystemMessage('No agents selected', 'warning');
            return;
        }
        
        document.querySelector('.modal-overlay')?.remove();
        
        this.addSystemMessage(`Building ${selected.length} agents...`, 'info');
        
        for (const agentId of selected) {
            await this.buildAgentV2(agentId, createModels);
        }
        
        this.addSystemMessage(`✓ Built ${selected.length} agents`, 'success');
    };

    // ========================================================================
    // SYSTEM PANEL
    // ========================================================================
    
    VeraChat.prototype.loadAgentV2SystemPanel = async function() {
        const container = document.getElementById('agents-system-content');
        if (!container) return;
        
        await this.loadAgentsV2SystemInfo();
        const info = this.agentsV2State.systemInfo;
        
        container.innerHTML = `
            <div style="max-width: 1000px;">
                <div style="background: var(--bg-darker); padding: 20px; border-radius: 12px; margin-bottom: 20px;">
                    <h3 style="margin: 0 0 8px 0; font-size: 18px; font-weight: 600;">⚙️ System Information</h3>
                    <p style="margin: 0; font-size: 13px; color: var(--text-muted);">Agent system configuration and status</p>
                </div>
                
                ${info ? `
                    <div style="display: grid; gap: 20px;">
                        <!-- Paths -->
                        <div style="background: var(--bg); padding: 20px; border-radius: 12px;">
                            <h4 style="margin: 0 0 12px 0; font-size: 14px; font-weight: 600; text-transform: uppercase; color: var(--text-muted);">
                                📁 Paths
                            </h4>
                            <div style="display: grid; gap: 12px; font-family: monospace; font-size: 12px;">
                                <div>
                                    <div style="font-size: 10px; color: var(--text-muted); margin-bottom: 4px;">AGENTS DIRECTORY</div>
                                    <code style="display: block; padding: 8px; background: var(--bg-darker); border-radius: 4px; color: var(--accent);">${info.paths?.agents_dir || 'N/A'}</code>
                                </div>
                                <div>
                                    <div style="font-size: 10px; color: var(--text-muted); margin-bottom: 4px;">TEMPLATES DIRECTORY</div>
                                    <code style="display: block; padding: 8px; background: var(--bg-darker); border-radius: 4px; color: var(--accent);">${info.paths?.templates_dir || 'N/A'}</code>
                                </div>
                                <div>
                                    <div style="font-size: 10px; color: var(--text-muted); margin-bottom: 4px;">BUILD DIRECTORY</div>
                                    <code style="display: block; padding: 8px; background: var(--bg-darker); border-radius: 4px; color: var(--accent);">${info.paths?.build_dir || 'N/A'}</code>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Statistics -->
                        <div style="background: var(--bg); padding: 20px; border-radius: 12px;">
                            <h4 style="margin: 0 0 12px 0; font-size: 14px; font-weight: 600; text-transform: uppercase; color: var(--text-muted);">
                                📊 Statistics
                            </h4>
                            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px;">
                                <div style="padding: 20px; background: var(--bg-darker); border-radius: 8px; text-align: center; border-left: 4px solid var(--accent);">
                                    <div style="font-size: 36px; font-weight: 700; color: var(--accent);">${info.counts?.agents || 0}</div>
                                    <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">Agents</div>
                                </div>
                                <div style="padding: 20px; background: var(--bg-darker); border-radius: 8px; text-align: center; border-left: 4px solid var(--success);">
                                    <div style="font-size: 36px; font-weight: 700; color: var(--success);">${info.counts?.shared_templates || 0}</div>
                                    <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">Shared Templates</div>
                                </div>
                                <div style="padding: 20px; background: var(--bg-darker); border-radius: 8px; text-align: center; border-left: 4px solid var(--warning);">
                                    <div style="font-size: 36px; font-weight: 700; color: var(--warning);">${info.counts?.modelfiles || 0}</div>
                                    <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">Modelfiles</div>
                                </div>
                            </div>
                        </div>
                        
                        <!-- System Status -->
                        <div style="background: var(--bg); padding: 20px; border-radius: 12px;">
                            <h4 style="margin: 0 0 12px 0; font-size: 14px; font-weight: 600; text-transform: uppercase; color: var(--text-muted);">
                                🔌 Status
                            </h4>
                            <div style="display: grid; gap: 12px;">
                                <div style="display: flex; align-items: center; gap: 12px; padding: 12px; background: var(--bg-darker); border-radius: 6px;">
                                    <div style="width: 12px; height: 12px; background: ${info.agent_manager_available ? 'var(--success)' : 'var(--danger)'}; border-radius: 50%;"></div>
                                    <div>
                                        <div style="font-weight: 600; font-size: 13px;">AgentManager</div>
                                        <div style="font-size: 11px; color: var(--text-muted);">${info.agent_manager_available ? 'Available' : 'Not Available'}</div>
                                    </div>
                                </div>
                                
                                <div style="display: flex; align-items: center; gap: 12px; padding: 12px; background: var(--bg-darker); border-radius: 6px;">
                                    <div style="width: 12px; height: 12px; background: var(--success); border-radius: 50%;"></div>
                                    <div>
                                        <div style="font-weight: 600; font-size: 13px;">API v2</div>
                                        <div style="font-size: 11px; color: var(--text-muted);">Connected</div>
                                    </div>
                                </div>
                                
                                <div style="display: flex; align-items: center; gap: 12px; padding: 12px; background: var(--bg-darker); border-radius: 6px;">
                                    <div style="width: 12px; height: 12px; background: var(--success); border-radius: 50%;"></div>
                                    <div>
                                        <div style="font-weight: 600; font-size: 13px;">UI Enhanced</div>
                                        <div style="font-size: 11px; color: var(--text-muted);">Version 2.0</div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Actions -->
                        <div style="background: var(--bg); padding: 20px; border-radius: 12px;">
                            <h4 style="margin: 0 0 12px 0; font-size: 14px; font-weight: 600; text-transform: uppercase; color: var(--text-muted);">
                                🔧 System Actions
                            </h4>
                            <div style="display: grid; gap: 12px;">
                                <button onclick="app.refreshAgentsV2()" 
                                        style="padding: 12px; background: var(--accent); border: none; border-radius: 6px; color: white; cursor: pointer; font-size: 13px; font-weight: 600; text-align: left;">
                                    🔄 Refresh Agent List
                                </button>
                                <button onclick="app.exportAllAgentsV2()" 
                                        style="padding: 12px; background: var(--success); border: none; border-radius: 6px; color: white; cursor: pointer; font-size: 13px; font-weight: 600; text-align: left;">
                                    📤 Export All Agents
                                </button>
                                <button onclick="app.showSystemLogs()" 
                                        style="padding: 12px; background: #9333ea; border: none; border-radius: 6px; color: white; cursor: pointer; font-size: 13px; font-weight: 600; text-align: left;">
                                    📋 View System Logs
                                </button>
                            </div>
                        </div>
                    </div>
                ` : '<p style="color: var(--text-muted);">Loading system information...</p>'}
            </div>
        `;
    };

    VeraChat.prototype.showSystemLogs = function() {
        this.createModal('System Logs', `
            <div style="padding: 16px; background: var(--bg-darker); border-radius: 6px; font-family: monospace; font-size: 11px; max-height: 400px; overflow-y: auto;">
                System logging feature coming soon...
            </div>
        `);
    };

    // ========================================================================
    // UTILITY HELPERS
    // ========================================================================
    
    VeraChat.prototype.yamlStringify = function(obj) {
        try {
            return jsyaml.dump(obj, {
                indent: 2,
                lineWidth: 80,
                noRefs: true
            });
        } catch (error) {
            console.error('YAML stringify failed:', error);
            return JSON.stringify(obj, null, 2);
        }
    };

    VeraChat.prototype.getFileTypeColor = function(type) {
        const colors = {
            'yaml': 'var(--accent)',
            'template': 'var(--success)',
            'text': 'var(--info)',
            'other': 'var(--text-muted)'
        };
        return colors[type] || colors.other;
    };

    VeraChat.prototype.getFileIcon = function(type) {
        const icons = {
            'yaml': '⚙️',
            'template': '📝',
            'text': '📄',
            'other': '📎'
        };
        return icons[type] || icons.other;
    };

    VeraChat.prototype.formatFileSize = function(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    };

})();

console.log('[Agents V2 UI Enhanced - Part 2] Loaded - Editor, Build, and System panels');
// Load js-yaml for YAML parsing (add to your HTML)
console.log('[Agents V2 UI] Loaded - requires js-yaml library');