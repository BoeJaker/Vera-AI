// agents-ui-manager.js - Following orchestrator-manager.js pattern
(() => {
    // ========================================================================
    // AGENTS STATE
    // ========================================================================
    
    VeraChat.prototype.agentsState = {
        currentPanel: 'browse',
        apiUrl: 'http://llm.int:8888/api/agents',
        updateInterval: null,
        agents: [],
        categories: {},
        selectedAgent: null,
        editingAgent: null,
        stats: {},
        filterCategory: 'all',
        filterEnabled: 'all'
    };

    // ========================================================================
    // INITIALIZATION
    // ========================================================================
    
    VeraChat.prototype.initAgents = async function() {
        console.log('Initializing Agents UI...');
        
        // Start periodic updates
        this.startAgentsUpdates();
        
        // Initial load
        await this.refreshAgents();
    };

    // ========================================================================
    // PERIODIC UPDATES
    // ========================================================================
    
    VeraChat.prototype.startAgentsUpdates = function() {
        if (this.agentsState.updateInterval) {
            clearInterval(this.agentsState.updateInterval);
        }
        
        this.agentsState.updateInterval = setInterval(() => {
            if (this.activeTab === 'agents') {
                this.refreshAgents();
            }
        }, 10000); // 10 seconds
    };

    VeraChat.prototype.stopAgentsUpdates = function() {
        if (this.agentsState.updateInterval) {
            clearInterval(this.agentsState.updateInterval);
            this.agentsState.updateInterval = null;
        }
    };

    // ========================================================================
    // PANEL SWITCHING
    // ========================================================================
    
    VeraChat.prototype.switchAgentsPanel = function(panelName) {
        // Update navigation buttons
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
        
        this.agentsState.currentPanel = panelName;
        
        // Load panel-specific data
        switch(panelName) {
            case 'browse':
                this.renderAgentsList();
                break;
            case 'edit':
                if (this.agentsState.selectedAgent) {
                    this.loadAgentEditor(this.agentsState.selectedAgent);
                }
                break;
            case 'test':
                if (this.agentsState.selectedAgent) {
                    this.loadAgentTester(this.agentsState.selectedAgent);
                }
                break;
            case 'stats':
                this.loadAgentStats();
                break;
        }
    };

    // ========================================================================
    // DATA REFRESH
    // ========================================================================
    
    VeraChat.prototype.refreshAgents = async function() {
        try {
            await Promise.all([
                this.refreshAgentsList(),
                this.refreshAgentsStats()
            ]);
        } catch (error) {
            console.error('Failed to refresh agents:', error);
        }
    };

    VeraChat.prototype.refreshAgentsList = async function() {
        try {
            const response = await fetch(`${this.agentsState.apiUrl}/categories`);
            const data = await response.json();
            
            this.agentsState.categories = data.categories || {};
            
            // Flatten agents list
            this.agentsState.agents = [];
            Object.values(data.categories).forEach(categoryAgents => {
                this.agentsState.agents.push(...categoryAgents);
            });
            
            // Update UI if on browse panel
            if (this.agentsState.currentPanel === 'browse') {
                this.renderAgentsList();
            }
        } catch (error) {
            console.error('Failed to load agents list:', error);
        }
    };

    VeraChat.prototype.refreshAgentsStats = async function() {
        try {
            const response = await fetch(`${this.agentsState.apiUrl}/stats`);
            const data = await response.json();
            
            this.agentsState.stats = data.stats || {};
        } catch (error) {
            console.error('Failed to load agent stats:', error);
        }
    };

    // ========================================================================
    // AGENT LIST RENDERING
    // ========================================================================
    
    VeraChat.prototype.renderAgentsList = function() {
        const container = document.getElementById('agents-list');
        if (!container) return;
        
        const categories = this.agentsState.categories;
        
        if (Object.keys(categories).length === 0) {
            container.innerHTML = `
                <div style="text-align: center; padding: 48px; color: var(--text-muted);">
                    <div style="font-size: 48px; margin-bottom: 16px;">🤖</div>
                    <h3 style="margin: 0 0 8px 0;">No Agents Configured</h3>
                    <p style="margin: 0;">Load default agents from the Stats panel</p>
                </div>
            `;
            return;
        }
        
        // Apply filters
        const filterCategory = this.agentsState.filterCategory;
        const filterEnabled = this.agentsState.filterEnabled;
        
        let html = '';
        
        Object.entries(categories).forEach(([category, agents]) => {
            // Skip if category filter doesn't match
            if (filterCategory !== 'all' && category !== filterCategory) {
                return;
            }
            
            // Filter agents by enabled status
            const filteredAgents = agents.filter(agent => {
                if (filterEnabled === 'enabled') return agent.enabled;
                if (filterEnabled === 'disabled') return !agent.enabled;
                return true;
            });
            
            if (filteredAgents.length === 0) return;
            
            const categoryColors = {
                'routing': 'var(--accent)',
                'execution': 'var(--success)',
                'proactive': 'var(--info)',
                'management': 'var(--warning)',
                'quality': 'var(--danger)',
                'processing': '#9333ea',
                'debugging': '#ea580c',
                'memory': '#0891b2'
            };
            const color = categoryColors[category] || 'var(--text-muted)';
            
            html += `
                <div style="margin-bottom: 32px;">
                    <h3 style="margin: 0 0 16px 0; font-size: 14px; text-transform: uppercase; color: ${color}; font-weight: 700; display: flex; align-items: center;">
                        <span style="display: inline-block; width: 10px; height: 10px; border-radius: 50%; background: ${color}; margin-right: 10px;"></span>
                        ${category} (${filteredAgents.length})
                    </h3>
                    
                    <div style="display: grid; gap: 12px;">
                        ${filteredAgents.map(agent => this.renderAgentCard(agent, color)).join('')}
                    </div>
                </div>
            `;
        });
        
        container.innerHTML = html || '<p style="color: var(--text-muted); text-align: center;">No agents match current filters</p>';
    };

    VeraChat.prototype.renderAgentCard = function(agent, categoryColor) {
        const isSelected = this.agentsState.selectedAgent === agent.id;
        const stats = this.agentsState.stats[agent.id] || {};
        
        return `
            <div style="padding: 16px; background: var(--bg); border-radius: 10px; border-left: 4px solid ${isSelected ? categoryColor : 'var(--border)'}; box-shadow: 0 2px 6px rgba(0,0,0,0.1); cursor: pointer; transition: all 0.2s;"
                 onclick="app.selectAgent('${agent.id}')"
                 onmouseover="this.style.background='var(--bg-darker)'"
                 onmouseout="this.style.background='var(--bg)'">
                
                <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 12px;">
                    <div style="flex: 1;">
                        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                            <h4 style="margin: 0; font-size: 15px; font-weight: 600;">${agent.name}</h4>
                            ${agent.enabled 
                                ? '<span style="padding: 2px 8px; background: var(--success); color: white; border-radius: 4px; font-size: 10px; font-weight: 600;">ENABLED</span>'
                                : '<span style="padding: 2px 8px; background: var(--text-muted); color: white; border-radius: 4px; font-size: 10px; font-weight: 600;">DISABLED</span>'}
                        </div>
                        <p style="margin: 0; font-size: 12px; color: var(--text-muted);">${agent.description}</p>
                    </div>
                    
                    <div style="display: flex; flex-direction: column; align-items: flex-end; gap: 4px;">
                        <span style="font-size: 11px; color: var(--text-muted); font-weight: 600;">${agent.task_type}</span>
                        <span style="font-size: 11px; color: var(--text-muted);">~${agent.estimated_duration}s</span>
                    </div>
                </div>
                
                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 12px; padding: 12px; background: var(--bg-darker); border-radius: 6px;">
                    <div>
                        <div style="font-size: 10px; color: var(--text-muted);">Model</div>
                        <div style="font-size: 12px; font-weight: 600; font-family: monospace;">${agent.model}</div>
                    </div>
                    <div>
                        <div style="font-size: 10px; color: var(--text-muted);">Temperature</div>
                        <div style="font-size: 12px; font-weight: 600;">${agent.temperature}</div>
                    </div>
                    <div>
                        <div style="font-size: 10px; color: var(--text-muted);">Tests</div>
                        <div style="font-size: 12px; font-weight: 600;">${stats.tests || 0}</div>
                    </div>
                </div>
                
                <div style="display: flex; gap: 6px;">
                    <button onclick="event.stopPropagation(); app.editAgent('${agent.id}')" 
                            style="flex: 1; padding: 8px; background: var(--accent); border: none; border-radius: 6px; color: white; cursor: pointer; font-size: 12px; font-weight: 600; transition: all 0.2s;"
                            onmouseover="this.style.opacity='0.8'"
                            onmouseout="this.style.opacity='1'">
                        ✏️ Edit
                    </button>
                    <button onclick="event.stopPropagation(); app.testAgent('${agent.id}')" 
                            style="flex: 1; padding: 8px; background: var(--success); border: none; border-radius: 6px; color: white; cursor: pointer; font-size: 12px; font-weight: 600; transition: all 0.2s;"
                            onmouseover="this.style.opacity='0.8'"
                            onmouseout="this.style.opacity='1'">
                        🧪 Test
                    </button>
                    <button onclick="event.stopPropagation(); app.generateTaskCode('${agent.id}')" 
                            style="flex: 1; padding: 8px; background: #9333ea; border: none; border-radius: 6px; color: white; cursor: pointer; font-size: 12px; font-weight: 600; transition: all 0.2s;"
                            onmouseover="this.style.opacity='0.8'"
                            onmouseout="this.style.opacity='1'"
                            title="Generate task registration code">
                        📝 Code
                    </button>
                    <button onclick="event.stopPropagation(); app.toggleAgent('${agent.id}', ${!agent.enabled})" 
                            style="flex: 1; padding: 8px; background: ${agent.enabled ? 'var(--danger)' : 'var(--success)'}; border: none; border-radius: 6px; color: white; cursor: pointer; font-size: 12px; font-weight: 600; transition: all 0.2s;"
                            onmouseover="this.style.opacity='0.8'"
                            onmouseout="this.style.opacity='1'">
                        ${agent.enabled ? '⏸️ Disable' : '▶️ Enable'}
                    </button>
                </div>
            </div>
        `;
    };

    // ========================================================================
    // AGENT ACTIONS
    // ========================================================================
    
    VeraChat.prototype.selectAgent = function(agentId) {
        this.agentsState.selectedAgent = agentId;
        this.renderAgentsList();
        
        const agent = this.agentsState.agents.find(a => a.id === agentId);
        if (agent) {
            this.addSystemMessage(`Selected agent: ${agent.name}`, 'info');
        }
    };

    VeraChat.prototype.editAgent = function(agentId) {
        this.agentsState.selectedAgent = agentId;
        this.agentsState.editingAgent = agentId;
        this.switchAgentsPanel('edit');
    };

    VeraChat.prototype.testAgent = function(agentId) {
        this.agentsState.selectedAgent = agentId;
        this.switchAgentsPanel('test');
    };

    VeraChat.prototype.toggleAgent = async function(agentId, enabled) {
        try {
            const response = await fetch(`${this.agentsState.apiUrl}/${agentId}/enable?enabled=${enabled}`, {
                method: 'POST'
            });
            
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            this.addSystemMessage(data.message, 'success');
            
            // Refresh agents list
            await this.refreshAgentsList();
            
        } catch (error) {
            this.addSystemMessage(`Failed to toggle agent: ${error.message}`, 'error');
        }
    };

    // ========================================================================
    // AGENT EDITOR
    // ========================================================================
    
    VeraChat.prototype.loadAgentEditor = async function(agentId) {
        const container = document.getElementById('agents-editor-content');
        if (!container) return;
        
        try {
            const response = await fetch(`${this.agentsState.apiUrl}/${agentId}/config`);
            const data = await response.json();
            const config = data.config;
            
            container.innerHTML = `
                <div style="max-width: 900px;">
                    <div style="background: var(--bg-darker); padding: 20px; border-radius: 12px; margin-bottom: 20px;">
                        <h3 style="margin: 0 0 8px 0; font-size: 18px; font-weight: 600;">${config.name}</h3>
                        <p style="margin: 0; font-size: 13px; color: var(--text-muted);">${config.description}</p>
                    </div>
                    
                    <div style="display: grid; gap: 20px;">
                        <!-- Basic Settings -->
                        <div style="background: var(--bg); padding: 20px; border-radius: 12px;">
                            <h4 style="margin: 0 0 16px 0; font-size: 14px; font-weight: 600; text-transform: uppercase; color: var(--text-muted);">Basic Settings</h4>
                            
                            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px;">
                                <div>
                                    <label style="display: block; margin-bottom: 6px; font-size: 13px; font-weight: 600;">Model</label>
                                    <input type="text" id="edit-model" value="${config.model}" 
                                           style="width: 100%; padding: 10px; background: var(--bg-darker); border: 2px solid var(--border); border-radius: 6px; color: var(--text); font-size: 13px;">
                                </div>
                                
                                <div>
                                    <label style="display: block; margin-bottom: 6px; font-size: 13px; font-weight: 600;">Priority</label>
                                    <select id="edit-priority" 
                                            style="width: 100%; padding: 10px; background: var(--bg-darker); border: 2px solid var(--border); border-radius: 6px; color: var(--text); font-size: 13px;">
                                        <option value="CRITICAL" ${config.priority === 'CRITICAL' ? 'selected' : ''}>Critical</option>
                                        <option value="HIGH" ${config.priority === 'HIGH' ? 'selected' : ''}>High</option>
                                        <option value="NORMAL" ${config.priority === 'NORMAL' ? 'selected' : ''}>Normal</option>
                                        <option value="LOW" ${config.priority === 'LOW' ? 'selected' : ''}>Low</option>
                                    </select>
                                </div>
                                
                                <div>
                                    <label style="display: block; margin-bottom: 6px; font-size: 13px; font-weight: 600;">Temperature</label>
                                    <input type="number" id="edit-temperature" value="${config.temperature}" step="0.1" min="0" max="2"
                                           style="width: 100%; padding: 10px; background: var(--bg-darker); border: 2px solid var(--border); border-radius: 6px; color: var(--text); font-size: 13px;">
                                </div>
                                
                                <div>
                                    <label style="display: block; margin-bottom: 6px; font-size: 13px; font-weight: 600;">Max Tokens</label>
                                    <input type="number" id="edit-max-tokens" value="${config.max_tokens}" 
                                           style="width: 100%; padding: 10px; background: var(--bg-darker); border: 2px solid var(--border); border-radius: 6px; color: var(--text); font-size: 13px;">
                                </div>
                            </div>
                            
                            <div style="margin-top: 16px;">
                                <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                                    <input type="checkbox" id="edit-enabled" ${config.enabled ? 'checked' : ''}
                                           style="width: 18px; height: 18px;">
                                    <span style="font-size: 13px; font-weight: 600;">Agent Enabled</span>
                                </label>
                            </div>
                        </div>
                        
                        <!-- Prompt Template -->
                        <div style="background: var(--bg); padding: 20px; border-radius: 12px;">
                            <h4 style="margin: 0 0 8px 0; font-size: 14px; font-weight: 600; text-transform: uppercase; color: var(--text-muted);">Prompt Template</h4>
                            <p style="margin: 0 0 12px 0; font-size: 12px; color: var(--text-muted);">
                                Use {parameter_name} for replaceable parameters
                            </p>
                            
                            <textarea id="edit-prompt" 
                                      style="width: 100%; min-height: 300px; padding: 12px; background: var(--bg-darker); border: 2px solid var(--border); border-radius: 6px; color: var(--text); font-size: 13px; font-family: 'Courier New', monospace; resize: vertical;">${this.escapeHtml(config.prompt_template)}</textarea>
                            
                            <div style="margin-top: 12px; padding: 12px; background: var(--bg-darker); border-radius: 6px;">
                                <div style="font-size: 11px; font-weight: 600; color: var(--text-muted); margin-bottom: 6px;">Available Parameters:</div>
                                <div style="display: flex; flex-wrap: wrap; gap: 8px;">
                                    ${Object.entries(config.parameters).map(([param, desc]) => `
                                        <span style="padding: 4px 10px; background: var(--bg); border-radius: 4px; font-size: 11px; font-family: monospace;">
                                            <strong>{${param}}</strong> - ${desc}
                                        </span>
                                    `).join('')}
                                </div>
                            </div>
                        </div>
                        
                        <!-- Actions -->
                        <div style="display: flex; gap: 12px;">
                            <button onclick="app.saveAgentConfig('${agentId}')" 
                                    style="flex: 1; padding: 14px; background: var(--success); border: none; border-radius: 8px; color: white; cursor: pointer; font-size: 14px; font-weight: 600; transition: all 0.2s;"
                                    onmouseover="this.style.opacity='0.8'"
                                    onmouseout="this.style.opacity='1'">
                                💾 Save Changes
                            </button>
                            <button onclick="app.switchAgentsPanel('browse')" 
                                    style="flex: 1; padding: 14px; background: var(--bg-darker); border: none; border-radius: 8px; color: var(--text); cursor: pointer; font-size: 14px; font-weight: 600; transition: all 0.2s;"
                                    onmouseover="this.style.opacity='0.8'"
                                    onmouseout="this.style.opacity='1'">
                                Cancel
                            </button>
                        </div>
                    </div>
                </div>
            `;
            
        } catch (error) {
            this.addSystemMessage(`Failed to load agent config: ${error.message}`, 'error');
        }
    };

    VeraChat.prototype.saveAgentConfig = async function(agentId) {
        try {
            const update = {
                enabled: document.getElementById('edit-enabled')?.checked,
                temperature: parseFloat(document.getElementById('edit-temperature')?.value),
                max_tokens: parseInt(document.getElementById('edit-max-tokens')?.value),
                prompt_template: document.getElementById('edit-prompt')?.value,
                priority: document.getElementById('edit-priority')?.value
            };
            
            const response = await fetch(`${this.agentsState.apiUrl}/${agentId}/config`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(update)
            });
            
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            this.addSystemMessage(data.message, 'success');
            
            // Refresh and go back to browse
            await this.refreshAgentsList();
            this.switchAgentsPanel('browse');
            
        } catch (error) {
            this.addSystemMessage(`Failed to save config: ${error.message}`, 'error');
        }
    };

    // ========================================================================
    // AGENT TESTER
    // ========================================================================
    
    VeraChat.prototype.loadAgentTester = async function(agentId) {
        const container = document.getElementById('agents-test-content');
        if (!container) return;
        
        try {
            const response = await fetch(`${this.agentsState.apiUrl}/${agentId}/config`);
            const data = await response.json();
            const config = data.config;
            
            container.innerHTML = `
                <div style="max-width: 900px;">
                    <div style="background: var(--bg-darker); padding: 20px; border-radius: 12px; margin-bottom: 20px;">
                        <h3 style="margin: 0 0 8px 0; font-size: 18px; font-weight: 600;">🧪 Test: ${config.name}</h3>
                        <p style="margin: 0; font-size: 13px; color: var(--text-muted);">Enter test parameters to see the formatted prompt</p>
                    </div>
                    
                    <div style="display: grid; gap: 20px;">
                        <!-- Parameters -->
                        <div style="background: var(--bg); padding: 20px; border-radius: 12px;">
                            <h4 style="margin: 0 0 16px 0; font-size: 14px; font-weight: 600; text-transform: uppercase; color: var(--text-muted);">Test Parameters</h4>
                            
                            <div style="display: grid; gap: 12px;">
                                ${Object.entries(config.parameters).map(([param, desc]) => `
                                    <div>
                                        <label style="display: block; margin-bottom: 6px; font-size: 13px; font-weight: 600;">{${param}} - ${desc}</label>
                                        <textarea id="test-param-${param}" 
                                                  placeholder="Enter value for ${param}"
                                                  style="width: 100%; min-height: 60px; padding: 10px; background: var(--bg-darker); border: 2px solid var(--border); border-radius: 6px; color: var(--text); font-size: 13px; resize: vertical;"></textarea>
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                        
                        <!-- Test Button -->
                        <button onclick="app.runAgentTest('${agentId}')" 
                                style="width: 100%; padding: 14px; background: var(--accent); border: none; border-radius: 8px; color: white; cursor: pointer; font-size: 15px; font-weight: 600; transition: all 0.2s;"
                                onmouseover="this.style.opacity='0.8'"
                                onmouseout="this.style.opacity='1'">
                            ▶️ Run Test
                        </button>
                        
                        <!-- Results -->
                        <div id="test-results" style="display: none;">
                            <!-- Results will be populated here -->
                        </div>
                    </div>
                </div>
            `;
            
        } catch (error) {
            this.addSystemMessage(`Failed to load agent tester: ${error.message}`, 'error');
        }
    };

    VeraChat.prototype.runAgentTest = async function(agentId) {
        try {
            // Get agent config to know parameters
            const configResponse = await fetch(`${this.agentsState.apiUrl}/${agentId}/config`);
            const configData = await configResponse.json();
            const config = configData.config;
            
            // Collect parameter values
            const parameters = {};
            Object.keys(config.parameters).forEach(param => {
                const input = document.getElementById(`test-param-${param}`);
                if (input) {
                    parameters[param] = input.value;
                }
            });
            
            // Run test
            const response = await fetch(`${this.agentsState.apiUrl}/${agentId}/test`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ parameters })
            });
            
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            
            // Display results
            const resultsContainer = document.getElementById('test-results');
            if (resultsContainer) {
                resultsContainer.style.display = 'block';
                resultsContainer.innerHTML = `
                    <div style="background: var(--bg); padding: 20px; border-radius: 12px;">
                        <h4 style="margin: 0 0 16px 0; font-size: 14px; font-weight: 600; text-transform: uppercase; color: var(--success);">✓ Test Results</h4>
                        
                        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 16px;">
                            <div style="padding: 12px; background: var(--bg-darker); border-radius: 6px;">
                                <div style="font-size: 11px; color: var(--text-muted);">Model</div>
                                <div style="font-size: 13px; font-weight: 600; font-family: monospace;">${data.model}</div>
                            </div>
                            <div style="padding: 12px; background: var(--bg-darker); border-radius: 6px;">
                                <div style="font-size: 11px; color: var(--text-muted);">Temperature</div>
                                <div style="font-size: 13px; font-weight: 600;">${data.temperature}</div>
                            </div>
                            <div style="padding: 12px; background: var(--bg-darker); border-radius: 6px;">
                                <div style="font-size: 11px; color: var(--text-muted);">Max Tokens</div>
                                <div style="font-size: 13px; font-weight: 600;">${data.max_tokens}</div>
                            </div>
                        </div>
                        
                        <div style="margin-bottom: 12px;">
                            <div style="font-size: 12px; font-weight: 600; color: var(--text-muted); margin-bottom: 8px;">FORMATTED PROMPT:</div>
                            <div style="padding: 16px; background: var(--bg-darker); border-radius: 6px; border-left: 4px solid var(--success); white-space: pre-wrap; font-family: 'Courier New', monospace; font-size: 12px; line-height: 1.6;">${this.escapeHtml(data.formatted_prompt)}</div>
                        </div>
                        
                        <div style="padding: 12px; background: rgba(255, 193, 7, 0.1); border-radius: 6px; border-left: 4px solid #ffc107;">
                            <div style="font-size: 12px; color: var(--text-muted);">${data.note}</div>
                        </div>
                    </div>
                `;
            }
            
            this.addSystemMessage('✓ Test completed successfully', 'success');
            
        } catch (error) {
            this.addSystemMessage(`Test failed: ${error.message}`, 'error');
        }
    };

    // ========================================================================
    // AGENT STATS
    // ========================================================================
    
    VeraChat.prototype.loadAgentStats = async function() {
        const container = document.getElementById('agents-stats-content');
        if (!container) return;
        
        try {
            await this.refreshAgentsStats();
            const stats = this.agentsState.stats;
            
            // Calculate totals
            let totalTests = 0;
            let enabledCount = 0;
            let disabledCount = 0;
            
            Object.values(stats).forEach(stat => {
                totalTests += stat.tests || 0;
                if (stat.enabled) enabledCount++;
                else disabledCount++;
            });
            
            container.innerHTML = `
                <div style="max-width: 1200px;">
                    <!-- Summary Cards -->
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px;">
                        <div style="padding: 20px; background: var(--bg); border-radius: 12px; border-left: 4px solid var(--success);">
                            <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">ENABLED AGENTS</div>
                            <div style="font-size: 32px; font-weight: 700; color: var(--success);">${enabledCount}</div>
                        </div>
                        <div style="padding: 20px; background: var(--bg); border-radius: 12px; border-left: 4px solid var(--text-muted);">
                            <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">DISABLED AGENTS</div>
                            <div style="font-size: 32px; font-weight: 700; color: var(--text-muted);">${disabledCount}</div>
                        </div>
                        <div style="padding: 20px; background: var(--bg); border-radius: 12px; border-left: 4px solid var(--accent);">
                            <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">TOTAL TESTS</div>
                            <div style="font-size: 32px; font-weight: 700; color: var(--accent);">${totalTests}</div>
                        </div>
                    </div>
                    
                    <!-- Stats Table -->
                    <div style="background: var(--bg); border-radius: 12px; padding: 20px;">
                        <h3 style="margin: 0 0 16px 0; font-size: 16px; font-weight: 600;">Agent Statistics</h3>
                        
                        <div style="display: grid; gap: 8px;">
                            ${Object.entries(stats).map(([agentId, stat]) => `
                                <div style="padding: 12px; background: var(--bg-darker); border-radius: 6px; display: flex; justify-content: space-between; align-items: center;">
                                    <div style="flex: 1;">
                                        <div style="font-weight: 600; font-size: 13px;">${stat.name}</div>
                                        <div style="font-size: 11px; color: var(--text-muted);">${stat.category}</div>
                                    </div>
                                    <div style="display: flex; gap: 20px; align-items: center;">
                                        <div style="text-align: center;">
                                            <div style="font-size: 18px; font-weight: 700;">${stat.tests || 0}</div>
                                            <div style="font-size: 10px; color: var(--text-muted);">tests</div>
                                        </div>
                                        <div>
                                            ${stat.enabled 
                                                ? '<span style="padding: 4px 10px; background: var(--success); color: white; border-radius: 4px; font-size: 11px; font-weight: 600;">ENABLED</span>'
                                                : '<span style="padding: 4px 10px; background: var(--text-muted); color: white; border-radius: 4px; font-size: 11px; font-weight: 600;">DISABLED</span>'}
                                        </div>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                    
                    <!-- Actions -->
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 24px;">
                        <button onclick="app.generateAllTasksCode()" 
                                style="padding: 14px; background: #9333ea; border: none; border-radius: 8px; color: white; cursor: pointer; font-size: 14px; font-weight: 600; transition: all 0.2s;"
                                onmouseover="this.style.opacity='0.8'"
                                onmouseout="this.style.opacity='1'">
                            📝 Generate All Tasks
                        </button>
                        <button onclick="app.exportAgentsConfig()" 
                                style="padding: 14px; background: var(--accent); border: none; border-radius: 8px; color: white; cursor: pointer; font-size: 14px; font-weight: 600; transition: all 0.2s;"
                                onmouseover="this.style.opacity='0.8'"
                                onmouseout="this.style.opacity='1'">
                            📥 Export Config
                        </button>
                        <button onclick="app.resetAgentsToDefaults()" 
                                style="padding: 14px; background: var(--danger); border: none; border-radius: 8px; color: white; cursor: pointer; font-size: 14px; font-weight: 600; transition: all 0.2s;"
                                onmouseover="this.style.opacity='0.8'"
                                onmouseout="this.style.opacity='1'">
                            🔄 Reset to Defaults
                        </button>
                    </div>
                </div>
            `;
            
        } catch (error) {
            this.addSystemMessage(`Failed to load stats: ${error.message}`, 'error');
        }
    };

    VeraChat.prototype.exportAgentsConfig = async function() {
        try {
            const response = await fetch(`${this.agentsState.apiUrl}/export`);
            const data = await response.json();
            
            // Create download
            const blob = new Blob([JSON.stringify(data.config, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `vera_agents_${new Date().toISOString().split('T')[0]}.json`;
            a.click();
            URL.revokeObjectURL(url);
            
            this.addSystemMessage('✓ Configuration exported', 'success');
            
        } catch (error) {
            this.addSystemMessage(`Export failed: ${error.message}`, 'error');
        }
    };

    VeraChat.prototype.resetAgentsToDefaults = async function() {
        if (!confirm('Reset all agents to default configuration? This cannot be undone.')) {
            return;
        }
        
        try {
            const response = await fetch(`${this.agentsState.apiUrl}/reset`, {
                method: 'POST'
            });
            
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            this.addSystemMessage(data.message, 'success');
            
            // Refresh
            await this.refreshAgents();
            this.loadAgentStats();
            
        } catch (error) {
            this.addSystemMessage(`Reset failed: ${error.message}`, 'error');
        }
    };

    // ========================================================================
    // FILTERS
    // ========================================================================
    
    VeraChat.prototype.setAgentFilter = function(filterType, value) {
        if (filterType === 'category') {
            this.agentsState.filterCategory = value;
        } else if (filterType === 'enabled') {
            this.agentsState.filterEnabled = value;
        }
        
        this.renderAgentsList();
    };

    // ========================================================================
    // TASK CODE GENERATION
    // ========================================================================
    
    VeraChat.prototype.generateTaskCode = async function(agentId) {
        try {
            const response = await fetch(`${this.agentsState.apiUrl}/${agentId}/generate-task`);
            
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            
            // Show modal with code
            this.showTaskCodeModal(agentId, data.task_code, data.filename);
            
        } catch (error) {
            this.addSystemMessage(`Failed to generate task code: ${error.message}`, 'error');
        }
    };

    VeraChat.prototype.generateAllTasksCode = async function() {
        try {
            const response = await fetch(`${this.agentsState.apiUrl}/generate-all-tasks`);
            
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            
            // Show modal with code
            this.showTaskCodeModal('all_agents', data.task_code, data.filename);
            this.addSystemMessage(`Generated code for ${data.agent_count} agents`, 'success');
            
        } catch (error) {
            this.addSystemMessage(`Failed to generate task code: ${error.message}`, 'error');
        }
    };

    VeraChat.prototype.showTaskCodeModal = function(agentId, code, filename) {
        const modalHtml = `
            <div class="modal-overlay" onclick="this.remove()" style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.8); z-index: 10000; display: flex; align-items: center; justify-content: center; padding: 20px;">
                <div onclick="event.stopPropagation()" style="background: var(--bg); border-radius: 12px; padding: 24px; max-width: 1000px; width: 100%; max-height: 90vh; overflow-y: auto; box-shadow: 0 4px 20px rgba(0,0,0,0.5);">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                        <div>
                            <h2 style="margin: 0; font-size: 20px;">📝 Generated Task Code</h2>
                            <p style="margin: 4px 0 0 0; font-size: 13px; color: var(--text-muted);">${filename}</p>
                        </div>
                        <button onclick="this.closest('.modal-overlay').remove()" style="background: none; border: none; font-size: 28px; cursor: pointer; color: var(--text); line-height: 1;">×</button>
                    </div>
                    
                    <div style="margin-bottom: 16px;">
                        <div style="display: flex; gap: 8px;">
                            <button onclick="app.copyTaskCode('${agentId}')" 
                                    style="flex: 1; padding: 12px; background: var(--accent); border: none; border-radius: 8px; color: white; cursor: pointer; font-size: 14px; font-weight: 600; transition: all 0.2s;"
                                    onmouseover="this.style.opacity='0.8'"
                                    onmouseout="this.style.opacity='1'">
                                📋 Copy to Clipboard
                            </button>
                            <button onclick="app.downloadTaskCode('${agentId}', '${filename}')" 
                                    style="flex: 1; padding: 12px; background: var(--success); border: none; border-radius: 8px; color: white; cursor: pointer; font-size: 14px; font-weight: 600; transition: all 0.2s;"
                                    onmouseover="this.style.opacity='0.8'"
                                    onmouseout="this.style.opacity='1'">
                                💾 Download File
                            </button>
                        </div>
                    </div>
                    
                    <div style="background: var(--bg-darker); border-radius: 8px; padding: 16px; border: 2px solid var(--border);">
                        <pre id="task-code-${agentId}" style="margin: 0; white-space: pre-wrap; font-family: 'Courier New', monospace; font-size: 12px; line-height: 1.6; overflow-x: auto; max-height: 60vh;">${this.escapeHtml(code)}</pre>
                    </div>
                    
                    <div style="margin-top: 16px; padding: 12px; background: rgba(34, 197, 94, 0.1); border-radius: 6px; border-left: 4px solid var(--success);">
                        <div style="font-size: 13px; color: var(--text);">
                            <strong>Next steps:</strong><br>
                            1. Copy or download this code<br>
                            2. Add to <code>Vera/vera_agent_tasks.py</code> or create a new file<br>
                            3. Import in <code>Vera.py</code>: <code>from vera_agent_tasks import ${agentId.replace('-', '_')}</code><br>
                            4. The task will be automatically registered via the @task decorator
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', modalHtml);
    };

    VeraChat.prototype.copyTaskCode = async function(agentId) {
        try {
            const codeElement = document.getElementById(`task-code-${agentId}`);
            if (!codeElement) {
                throw new Error('Code element not found');
            }
            
            // Get the text content (unescaped)
            const code = codeElement.textContent;
            
            // Copy to clipboard
            await navigator.clipboard.writeText(code);
            
            this.addSystemMessage('✓ Code copied to clipboard', 'success');
            
        } catch (error) {
            this.addSystemMessage(`Failed to copy: ${error.message}`, 'error');
        }
    };

    VeraChat.prototype.downloadTaskCode = async function(agentId, filename) {
        try {
            const codeElement = document.getElementById(`task-code-${agentId}`);
            if (!codeElement) {
                throw new Error('Code element not found');
            }
            
            // Get the text content (unescaped)
            const code = codeElement.textContent;
            
            // Create download
            const blob = new Blob([code], { type: 'text/python' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            a.click();
            URL.revokeObjectURL(url);
            
            this.addSystemMessage('✓ Code downloaded', 'success');
            
        } catch (error) {
            this.addSystemMessage(`Failed to download: ${error.message}`, 'error');
        }
    };

    // ========================================================================
    // CLEANUP
    // ========================================================================
    
    VeraChat.prototype.cleanupAgents = function() {
        console.log('Cleaning up Agents UI...');
        this.stopAgentsUpdates();
    };

    // ========================================================================
    // UTILITY FUNCTIONS
    // ========================================================================
    
    VeraChat.prototype.escapeHtml = function(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    };

})();