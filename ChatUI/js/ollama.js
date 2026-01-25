// ollama-ui-manager-v2.js - Multi-Instance Unified Manager
(() => {
    // ========================================================================
    // OLLAMA STATE
    // ========================================================================
    
    VeraChat.prototype.ollamaState = {
        currentPanel: 'models',
        apiUrl: 'http://llm.int:8888/api/ollama',
        updateInterval: null,
        ws: null,
        models: [],
        instances: {},
        selectedModel: null,
        selectedInstance: null,
        routingMode: 'auto', // 'auto' or 'manual'
        selectedInstances: [], // For manual mode
        modelInfo: {},
        connected: false,
        mode: 'unknown',
        modelCount: 0,
        isMultiInstance: false,
        syncInProgress: false,
        comparison: null,
        operationInProgress: false, // Prevent duplicate submissions
    };

    // ========================================================================
    // INITIALIZATION
    // ========================================================================
    
    VeraChat.prototype.initOllama = async function() {
        console.log('Initializing Ollama UI...');
        
        // Start periodic updates
        this.startOllamaUpdates();
        
        // Initial load
        await this.refreshOllama();
        
        // Check if multi-instance is available
        await this.checkMultiInstance();
    };

    // ========================================================================
    // MULTI-INSTANCE DETECTION
    // ========================================================================
    
    VeraChat.prototype.checkMultiInstance = async function() {
        try {
            const response = await fetch(`${this.ollamaState.apiUrl}/diagnostics`);
            const data = await response.json();
            
            this.ollamaState.isMultiInstance = data.is_multi_instance || false;
            
            if (this.ollamaState.isMultiInstance) {
                console.log('Multi-instance Ollama detected');
                await this.refreshInstances();
            }
        } catch (error) {
            console.error('Failed to check multi-instance support:', error);
            this.ollamaState.isMultiInstance = false;
        }
    };

    // ========================================================================
    // PERIODIC UPDATES
    // ========================================================================
    
    VeraChat.prototype.startOllamaUpdates = function() {
        if (this.ollamaState.updateInterval) {
            clearInterval(this.ollamaState.updateInterval);
        }
        
        this.ollamaState.updateInterval = setInterval(() => {
            if (this.activeTab === 'ollama') {
                this.refreshOllama();
            }
        }, 5000);
    };

    VeraChat.prototype.stopOllamaUpdates = function() {
        if (this.ollamaState.updateInterval) {
            clearInterval(this.ollamaState.updateInterval);
            this.ollamaState.updateInterval = null;
        }
    };

    // ========================================================================
    // PANEL SWITCHING
    // ========================================================================
    
    VeraChat.prototype.switchOllamaPanel = function(panelName) {
        // Update navigation buttons
        document.querySelectorAll('.ollama-nav-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        const activeBtn = document.querySelector(`.ollama-nav-btn[data-panel="${panelName}"]`);
        if (activeBtn) activeBtn.classList.add('active');
        
        // Update panels
        document.querySelectorAll('.ollama-panel').forEach(panel => {
            panel.style.display = 'none';
        });
        const activePanel = document.getElementById(`ollama-panel-${panelName}`);
        if (activePanel) activePanel.style.display = 'block';
        
        this.ollamaState.currentPanel = panelName;
        
        // Load panel-specific data
        switch(panelName) {
            case 'models':
                this.refreshModels();
                break;
            case 'instances':
                if (this.ollamaState.isMultiInstance) {
                    this.refreshInstances();
                }
                break;
            case 'sync':
                if (this.ollamaState.isMultiInstance) {
                    this.refreshComparison();
                }
                break;
            case 'routing':
                this.renderRoutingPanel();
                break;
            case 'pull':
                break;
            case 'generate':
                this.populateTestModelDropdown();
                break;
            case 'config':
                this.loadOllamaConfig();
                break;
        }
    };

    // ========================================================================
    // DATA REFRESH
    // ========================================================================
    
    VeraChat.prototype.refreshOllama = async function() {
        try {
            await Promise.all([
                this.refreshHealth(),
                this.refreshModels(),
                this.ollamaState.isMultiInstance ? this.refreshInstances() : Promise.resolve()
            ]);
        } catch (error) {
            console.error('Failed to refresh Ollama:', error);
        }
    };

    VeraChat.prototype.refreshHealth = async function() {
        try {
            const response = await fetch(`${this.ollamaState.apiUrl}/health`);
            const data = await response.json();
            
            this.ollamaState.connected = data.connected;
            this.ollamaState.mode = data.mode;
            
            const indicator = document.getElementById('ollama-status-indicator');
            const status = document.getElementById('ollama-status-text');
            
            if (data.connected) {
                if (indicator) indicator.style.background = '#22c55e';
                if (status) {
                    const modeText = this.ollamaState.isMultiInstance ? 
                        `Multi-Instance (${Object.keys(this.ollamaState.instances).length} instances)` : 
                        data.mode;
                    status.textContent = `Connected (${modeText})`;
                }
            } else {
                if (indicator) indicator.style.background = '#ef4444';
                if (status) status.textContent = 'Disconnected';
            }
        } catch (error) {
            console.error('Ollama health check failed:', error);
            this.ollamaState.connected = false;
        }
    };

    VeraChat.prototype.refreshModels = async function() {
        try {
            const response = await fetch(`${this.ollamaState.apiUrl}/models`);
            const data = await response.json();
            
            this.ollamaState.models = data.models || [];
            this.ollamaState.modelCount = data.count || 0;
            
            // Update UI if on models panel
            if (this.ollamaState.currentPanel === 'models') {
                this.renderOllamaModels();
            }
        } catch (error) {
            console.error('Failed to load models:', error);
        }
    };

    // ========================================================================
    // MULTI-INSTANCE MANAGEMENT
    // ========================================================================
    
    VeraChat.prototype.refreshInstances = async function() {
        if (!this.ollamaState.isMultiInstance) return;
        
        try {
            const response = await fetch(`${this.ollamaState.apiUrl}/instances`);
            const data = await response.json();
            
            this.ollamaState.instances = data.instances || {};
            
            if (this.ollamaState.currentPanel === 'instances') {
                this.renderInstances();
            }
        } catch (error) {
            console.error('Failed to load instances:', error);
        }
    };

    VeraChat.prototype.renderInstances = function() {
        const container = document.getElementById('ollama-instances-list');
        if (!container) return;
        
        const instances = Object.entries(this.ollamaState.instances);
        
        if (instances.length === 0) {
            container.innerHTML = `
                <div style="text-align: center; padding: 48px; color: var(--text-muted);">
                    <div style="font-size: 48px; margin-bottom: 16px;">🖥️</div>
                    <h3 style="margin: 0 0 8px 0;">No Instances Available</h3>
                    <p style="margin: 0;">Multi-instance mode not configured</p>
                </div>
            `;
            return;
        }
        
        container.innerHTML = instances.map(([name, stats]) => {
            const healthColor = stats.is_healthy ? '#22c55e' : '#ef4444';
            const loadPct = stats.max_concurrent > 0 ? 
                Math.round((stats.active_requests / stats.max_concurrent) * 100) : 0;
            
            return `
                <div style="padding: 20px; margin-bottom: 16px; background: var(--bg); border-radius: 12px; border-left: 4px solid ${healthColor}; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px;">
                        <div>
                            <h3 style="margin: 0 0 4px 0; font-size: 18px; font-weight: 600;">${name}</h3>
                            <div style="font-size: 12px; color: var(--text-muted);">${stats.api_url}</div>
                        </div>
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <div style="width: 10px; height: 10px; border-radius: 50%; background: ${healthColor};"></div>
                            <span style="font-size: 12px; font-weight: 600; color: ${healthColor};">
                                ${stats.is_healthy ? 'Healthy' : 'Unhealthy'}
                            </span>
                        </div>
                    </div>
                    
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 16px; margin-bottom: 16px;">
                        <div>
                            <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">Priority</div>
                            <div style="font-size: 24px; font-weight: 700; color: var(--accent);">${stats.priority}</div>
                        </div>
                        <div>
                            <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">Active Requests</div>
                            <div style="font-size: 24px; font-weight: 700; color: var(--info);">${stats.active_requests}/${stats.max_concurrent}</div>
                        </div>
                        <div>
                            <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">Total Requests</div>
                            <div style="font-size: 24px; font-weight: 700;">${stats.total_requests.toLocaleString()}</div>
                        </div>
                        <div>
                            <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">Failures</div>
                            <div style="font-size: 24px; font-weight: 700; color: ${stats.total_failures > 0 ? 'var(--danger)' : 'var(--success)'};">${stats.total_failures}</div>
                        </div>
                    </div>
                    
                    <!-- Load Bar -->
                    <div style="margin-bottom: 12px;">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                            <span style="font-size: 11px; color: var(--text-muted);">Load</span>
                            <span style="font-size: 11px; font-weight: 600;">${loadPct}%</span>
                        </div>
                        <div style="height: 6px; background: var(--bg-darker); border-radius: 3px; overflow: hidden;">
                            <div style="height: 100%; background: ${loadPct > 80 ? 'var(--danger)' : loadPct > 50 ? 'var(--warning)' : 'var(--success)'}; width: ${loadPct}%; transition: width 0.3s;"></div>
                        </div>
                    </div>
                    
                    <div style="display: flex; gap: 8px;">
                        <button onclick="app.showInstanceModels('${name}')" 
                                style="padding: 8px 16px; background: var(--accent); border: none; border-radius: 6px; color: white; cursor: pointer; font-size: 13px; font-weight: 600;">
                            📦 View Models
                        </button>
                        <button onclick="app.diagnoseInstance('${name}')" 
                                style="padding: 8px 16px; background: var(--info); border: none; border-radius: 6px; color: white; cursor: pointer; font-size: 13px; font-weight: 600;">
                            🔍 Diagnose
                        </button>
                    </div>
                </div>
            `;
        }).join('');
    };

    // ========================================================================
    // ROUTING CONTROL PANEL
    // ========================================================================
    
    VeraChat.prototype.renderRoutingPanel = function() {
        const container = document.getElementById('ollama-routing-content');
        if (!container) return;
        
        const instances = Object.keys(this.ollamaState.instances);
        
        container.innerHTML = `
            <div style="background: var(--bg); padding: 24px; border-radius: 12px; margin-bottom: 20px;">
                <h3 style="margin: 0 0 16px 0; font-size: 20px; font-weight: 600;">Instance Routing Configuration</h3>
                
                <!-- Routing Mode Selection -->
                <div style="margin-bottom: 24px;">
                    <label style="display: block; margin-bottom: 12px; font-size: 14px; font-weight: 600;">Routing Mode</label>
                    <div style="display: flex; gap: 12px;">
                        <button 
                            onclick="app.setRoutingMode('auto')"
                            class="routing-mode-btn ${this.ollamaState.routingMode === 'auto' ? 'active' : ''}"
                            data-mode="auto"
                            style="flex: 1; padding: 16px; background: ${this.ollamaState.routingMode === 'auto' ? 'var(--accent)' : 'var(--bg-darker)'}; border: 2px solid ${this.ollamaState.routingMode === 'auto' ? 'var(--accent)' : 'var(--border)'}; border-radius: 8px; cursor: pointer; transition: all 0.2s;">
                            <div style="font-size: 24px; margin-bottom: 8px;">🤖</div>
                            <div style="font-weight: 600; margin-bottom: 4px;">Automatic</div>
                            <div style="font-size: 12px; color: var(--text-muted);">Load balancing across all healthy instances</div>
                        </button>
                        
                        <button 
                            onclick="app.setRoutingMode('manual')"
                            class="routing-mode-btn ${this.ollamaState.routingMode === 'manual' ? 'active' : ''}"
                            data-mode="manual"
                            style="flex: 1; padding: 16px; background: ${this.ollamaState.routingMode === 'manual' ? 'var(--accent)' : 'var(--bg-darker)'}; border: 2px solid ${this.ollamaState.routingMode === 'manual' ? 'var(--accent)' : 'var(--border)'}; border-radius: 8px; cursor: pointer; transition: all 0.2s;">
                            <div style="font-size: 24px; margin-bottom: 8px;">🎯</div>
                            <div style="font-weight: 600; margin-bottom: 4px;">Manual</div>
                            <div style="font-size: 12px; color: var(--text-muted);">Select specific instances to use</div>
                        </button>
                    </div>
                </div>
                
                <!-- Manual Instance Selection (shown when manual mode) -->
                <div id="manual-instance-selection" style="display: ${this.ollamaState.routingMode === 'manual' ? 'block' : 'none'};">
                    <label style="display: block; margin-bottom: 12px; font-size: 14px; font-weight: 600;">Select Instances</label>
                    <div style="display: grid; gap: 8px; margin-bottom: 16px;">
                        ${instances.map(name => {
                            const stats = this.ollamaState.instances[name];
                            const isSelected = this.ollamaState.selectedInstances.includes(name);
                            const isHealthy = stats.is_healthy;
                            
                            return `
                                <label style="display: flex; align-items: center; padding: 12px; background: var(--bg-darker); border-radius: 8px; cursor: ${isHealthy ? 'pointer' : 'not-allowed'}; opacity: ${isHealthy ? '1' : '0.5'};">
                                    <input 
                                        type="checkbox" 
                                        value="${name}"
                                        ${isSelected ? 'checked' : ''}
                                        ${!isHealthy ? 'disabled' : ''}
                                        onchange="app.toggleInstanceSelection('${name}', this.checked)"
                                        style="margin-right: 12px;">
                                    <div style="flex: 1;">
                                        <div style="font-weight: 600; margin-bottom: 4px;">${name}</div>
                                        <div style="font-size: 11px; color: var(--text-muted);">${stats.api_url}</div>
                                    </div>
                                    <div style="display: flex; align-items: center; gap: 8px;">
                                        <div style="width: 8px; height: 8px; border-radius: 50%; background: ${isHealthy ? '#22c55e' : '#ef4444'};"></div>
                                        <span style="font-size: 11px; color: var(--text-muted);">Priority: ${stats.priority}</span>
                                    </div>
                                </label>
                            `;
                        }).join('')}
                    </div>
                    
                    ${this.ollamaState.selectedInstances.length === 0 ? `
                        <div style="padding: 12px; background: rgba(251, 188, 4, 0.1); border-left: 4px solid var(--warning); border-radius: 4px;">
                            <div style="font-size: 13px; color: var(--warning);">⚠️ No instances selected. Requests will fail in manual mode.</div>
                        </div>
                    ` : ''}
                </div>
                
                <!-- Current Strategy Info (shown when auto mode) -->
                <div id="auto-strategy-info" style="display: ${this.ollamaState.routingMode === 'auto' ? 'block' : 'none'};">
                    <div style="padding: 16px; background: var(--bg-darker); border-radius: 8px;">
                        <h4 style="margin: 0 0 12px 0; font-size: 14px; font-weight: 600;">Load Balancing Strategy</h4>
                        <div style="font-size: 13px; color: var(--text-muted); line-height: 1.6;">
                            Requests are distributed using the <strong>least loaded</strong> strategy:
                            <ul style="margin: 8px 0 0 20px; padding: 0;">
                                <li>Selects instance with lowest active request ratio</li>
                                <li>Prioritizes higher priority instances when load is equal</li>
                                <li>Automatically fails over to other instances on errors</li>
                                <li>Health checks run every 30 seconds</li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Test Routing -->
            <div style="background: var(--bg); padding: 24px; border-radius: 12px;">
                <h3 style="margin: 0 0 16px 0; font-size: 16px; font-weight: 600;">Test Current Configuration</h3>
                
                <div style="display: flex; gap: 12px; margin-bottom: 16px;">
                    <select id="routing-test-model" style="flex: 1; padding: 10px; background: var(--bg-darker); border: 1px solid var(--border); border-radius: 6px; color: var(--text);">
                        ${this.ollamaState.models.map(m => `
                            <option value="${m.model}">${m.model}</option>
                        `).join('')}
                    </select>
                    
                    <button 
                        onclick="app.testRouting()"
                        style="padding: 10px 20px; background: var(--accent); border: none; border-radius: 6px; color: white; cursor: pointer; font-weight: 600;">
                        Test Routing
                    </button>
                </div>
                
                <div id="routing-test-result" style="display: none; padding: 12px; background: var(--bg-darker); border-radius: 6px; font-family: monospace; font-size: 12px;"></div>
            </div>
        `;
    };

    VeraChat.prototype.setRoutingMode = function(mode) {
        this.ollamaState.routingMode = mode;
        
        // If switching to manual and no instances selected, select all healthy ones
        if (mode === 'manual' && this.ollamaState.selectedInstances.length === 0) {
            this.ollamaState.selectedInstances = Object.entries(this.ollamaState.instances)
                .filter(([_, stats]) => stats.is_healthy)
                .map(([name, _]) => name);
        }
        
        this.renderRoutingPanel();
        this.addSystemMessage(`Routing mode set to: ${mode}`, 'info');
    };

    VeraChat.prototype.toggleInstanceSelection = function(instanceName, checked) {
        if (checked) {
            if (!this.ollamaState.selectedInstances.includes(instanceName)) {
                this.ollamaState.selectedInstances.push(instanceName);
            }
        } else {
            this.ollamaState.selectedInstances = this.ollamaState.selectedInstances.filter(
                name => name !== instanceName
            );
        }
        
        this.renderRoutingPanel();
    };

    VeraChat.prototype.testRouting = async function() {
        const model = document.getElementById('routing-test-model')?.value;
        if (!model) return;
        
        const resultDiv = document.getElementById('routing-test-result');
        if (!resultDiv) return;
        
        resultDiv.style.display = 'block';
        resultDiv.textContent = 'Testing routing...';
        
        try {
            const response = await fetch(`${this.ollamaState.apiUrl}/test-generation`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    model: model,
                    prompt: 'Say hello in one sentence.',
                    routing_mode: this.ollamaState.routingMode,
                    selected_instances: this.ollamaState.selectedInstances
                })
            });
            
            const data = await response.json();
            
            if (data.status === 'success') {
                resultDiv.innerHTML = `
                    <div style="color: var(--success); margin-bottom: 8px;">✓ Success</div>
                    <div style="color: var(--text-muted); margin-bottom: 4px;">Model: ${data.model}</div>
                    <div style="color: var(--text-muted); margin-bottom: 4px;">Instance Used: ${data.instance_used || 'N/A'}</div>
                    <div style="color: var(--text-muted); margin-bottom: 4px;">Duration: ${data.duration_seconds}s</div>
                    <div style="color: var(--text-muted); margin-bottom: 8px;">Tokens/sec: ${data.tokens_per_second}</div>
                    <div style="padding: 8px; background: var(--bg); border-radius: 4px; white-space: pre-wrap;">${data.response}</div>
                `;
            } else {
                resultDiv.innerHTML = `
                    <div style="color: var(--danger);">✗ Failed</div>
                    <div style="color: var(--text-muted);">${JSON.stringify(data, null, 2)}</div>
                `;
            }
        } catch (error) {
            resultDiv.innerHTML = `
                <div style="color: var(--danger);">✗ Error</div>
                <div style="color: var(--text-muted);">${error.message}</div>
            `;
        }
    };

    // ========================================================================
    // MODEL MANAGEMENT WITH DEBOUNCING
    // ========================================================================
    
    VeraChat.prototype.renderOllamaModels = function() {
        const container = document.getElementById('ollama-models-list');
        if (!container) return;
        
        if (this.ollamaState.models.length === 0) {
            container.innerHTML = `
                <div style="text-align: center; padding: 48px; color: var(--text-muted);">
                    <div style="font-size: 48px; margin-bottom: 16px;">📦</div>
                    <h3 style="margin: 0 0 8px 0;">No Models Available</h3>
                    <p style="margin: 0;">Pull a model from the Pull Model tab to get started</p>
                </div>
            `;
            return;
        }
        
        container.innerHTML = this.ollamaState.models.map(model => {
            const modelName = model.model || model.name || 'Unknown';
            const isSelected = this.ollamaState.selectedModel === modelName;
            
            return `
                <div style="padding: 20px; margin-bottom: 16px; background: var(--bg); border-radius: 12px; border-left: 4px solid ${isSelected ? 'var(--accent)' : 'var(--border)'}; box-shadow: 0 2px 8px rgba(0,0,0,0.1); cursor: pointer; transition: all 0.2s;"
                     onclick="app.selectOllamaModel('${modelName}')"
                     onmouseover="this.style.background='var(--bg-darker)'"
                     onmouseout="this.style.background='var(--bg)'">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                        <div>
                            <h3 style="margin: 0 0 4px 0; font-size: 16px; font-weight: 600;">${modelName}</h3>
                            <div style="font-size: 12px; color: var(--text-muted);">
                                ${model.size ? `${(model.size / 1e9).toFixed(2)} GB` : 'Size unknown'}
                            </div>
                        </div>
                    </div>
                    
                    <div style="display: flex; gap: 8px; margin-top: 12px;">
                        <button onclick="event.stopPropagation(); app.showOllamaModelInfo('${modelName}')" 
                                style="padding: 8px 16px; background: var(--accent); border: none; border-radius: 6px; color: white; cursor: pointer; font-size: 13px; font-weight: 600;">
                            ℹ️ Info
                        </button>
                        <button onclick="event.stopPropagation(); app.testGenerateWithModel('${modelName}')" 
                                style="padding: 8px 16px; background: var(--success); border: none; border-radius: 6px; color: white; cursor: pointer; font-size: 13px; font-weight: 600;">
                            ⚡ Test
                        </button>
                        ${this.ollamaState.isMultiInstance ? `
                            <button onclick="event.stopPropagation(); app.selectModelForSync('${modelName}')" 
                                    style="padding: 8px 16px; background: var(--info); border: none; border-radius: 6px; color: white; cursor: pointer; font-size: 13px; font-weight: 600;">
                                🔄 Sync
                            </button>
                        ` : ''}
                        <button onclick="event.stopPropagation(); app.deleteOllamaModel('${modelName}')" 
                                style="padding: 8px 16px; background: var(--danger); border: none; border-radius: 6px; color: white; cursor: pointer; font-size: 13px; font-weight: 600;">
                            🗑️ Delete
                        </button>
                    </div>
                </div>
            `;
        }).join('');
    };

    VeraChat.prototype.selectOllamaModel = function(modelName) {
        this.ollamaState.selectedModel = modelName;
        this.renderOllamaModels();
    };

    VeraChat.prototype.testGenerateWithModel = async function(modelName) {
        if (this.ollamaState.operationInProgress) {
            this.addSystemMessage('Operation already in progress', 'warning');
            return;
        }
        
        this.ollamaState.operationInProgress = true;
        
        try {
            this.addSystemMessage(`Testing ${modelName}...`, 'info');
            
            const response = await fetch(`${this.ollamaState.apiUrl}/test-generation?model=${encodeURIComponent(modelName)}`, {
                method: 'POST'
            });
            
            const data = await response.json();
            
            if (data.status === 'success') {
                this.addSystemMessage(
                    `✓ ${modelName}: ${data.duration_seconds}s, ${data.tokens_per_second} tok/s`,
                    'success'
                );
            } else {
                this.addSystemMessage(`✗ Test failed: ${data.error || 'Unknown error'}`, 'error');
            }
        } catch (error) {
            this.addSystemMessage(`Test failed: ${error.message}`, 'error');
        } finally {
            // Reset after delay to prevent rapid double-clicks
            setTimeout(() => {
                this.ollamaState.operationInProgress = false;
            }, 1000);
        }
    };

    VeraChat.prototype.showOllamaModelInfo = async function(modelName) {
        try {
            const response = await fetch(`${this.ollamaState.apiUrl}/models/${encodeURIComponent(modelName)}/info`);
            const data = await response.json();
            
            if (data.status === 'success') {
                const model = data.model;
                
                const modalHtml = `
                    <div class="modal-overlay" onclick="this.remove()" style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.7); z-index: 10000; display: flex; align-items: center; justify-content: center;">
                        <div onclick="event.stopPropagation()" style="background: var(--bg); border-radius: 12px; padding: 24px; max-width: 600px; max-height: 85vh; overflow-y: auto; box-shadow: 0 4px 20px rgba(0,0,0,0.5);">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                                <h2 style="margin: 0; font-size: 20px;">📦 ${modelName}</h2>
                                <button onclick="this.closest('.modal-overlay').remove()" style="background: none; border: none; font-size: 28px; cursor: pointer; color: var(--text); line-height: 1;">×</button>
                            </div>
                            
                            <div style="display: grid; gap: 16px;">
                                ${model.family ? `
                                    <div>
                                        <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 4px;">Family</div>
                                        <div style="font-weight: 600;">${model.family}</div>
                                    </div>
                                ` : ''}
                                
                                ${model.parameter_size ? `
                                    <div>
                                        <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 4px;">Parameters</div>
                                        <div style="font-weight: 600;">${model.parameter_size}</div>
                                    </div>
                                ` : ''}
                                
                                ${model.quantization_level ? `
                                    <div>
                                        <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 4px;">Quantization</div>
                                        <div style="font-weight: 600;">${model.quantization_level}</div>
                                    </div>
                                ` : ''}
                                
                                ${model.context_length ? `
                                    <div>
                                        <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 4px;">Context Length</div>
                                        <div style="font-weight: 600;">${model.context_length.toLocaleString()} tokens</div>
                                    </div>
                                ` : ''}
                            </div>
                        </div>
                    </div>
                `;
                
                document.body.insertAdjacentHTML('beforeend', modalHtml);
            }
        } catch (error) {
            this.addSystemMessage(`Failed to load model info: ${error.message}`, 'error');
        }
    };

    VeraChat.prototype.pullOllamaModel = async function() {
        if (this.ollamaState.operationInProgress) {
            this.addSystemMessage('Pull operation already in progress', 'warning');
            return;
        }
        
        const modelName = document.getElementById('ollama-pull-model-name')?.value?.trim();
        if (!modelName) {
            this.addSystemMessage('Please enter a model name', 'warning');
            return;
        }
        
        this.ollamaState.operationInProgress = true;
        
        try {
            this.addSystemMessage(`Pulling ${modelName}...`, 'info');
            
            const response = await fetch(`${this.ollamaState.apiUrl}/models/pull?model_name=${encodeURIComponent(modelName)}`, {
                method: 'POST'
            });
            
            const data = await response.json();
            
            if (data.status === 'success') {
                this.addSystemMessage(`✓ ${data.message}`, 'success');
                await this.refreshModels();
            } else {
                this.addSystemMessage(`✗ Pull failed: ${data.error || 'Unknown error'}`, 'error');
            }
        } catch (error) {
            this.addSystemMessage(`Pull failed: ${error.message}`, 'error');
        } finally {
            setTimeout(() => {
                this.ollamaState.operationInProgress = false;
            }, 2000);
        }
    };

    VeraChat.prototype.deleteOllamaModel = async function(modelName) {
        if (this.ollamaState.operationInProgress) {
            this.addSystemMessage('Operation already in progress', 'warning');
            return;
        }
        
        if (!confirm(`Are you sure you want to delete ${modelName}?`)) {
            return;
        }
        
        this.ollamaState.operationInProgress = true;
        
        try {
            this.addSystemMessage(`Deleting ${modelName}...`, 'info');
            
            // Implementation depends on your API endpoint
            this.addSystemMessage('Delete functionality not yet implemented', 'warning');
            
        } catch (error) {
            this.addSystemMessage(`Delete failed: ${error.message}`, 'error');
        } finally {
            setTimeout(() => {
                this.ollamaState.operationInProgress = false;
            }, 1000);
        }
    };

    VeraChat.prototype.populateTestModelDropdown = function() {
        const select = document.getElementById('ollama-test-model');
        if (!select) return;
        
        select.innerHTML = this.ollamaState.models.map(model => {
            const modelName = model.model || model.name;
            return `<option value="${modelName}">${modelName}</option>`;
        }).join('');
    };

    VeraChat.prototype.testOllamaGeneration = async function() {
        if (this.ollamaState.operationInProgress) {
            this.addSystemMessage('Test already in progress', 'warning');
            return;
        }
        
        const model = document.getElementById('ollama-test-model')?.value;
        const prompt = document.getElementById('ollama-test-prompt')?.value;
        
        if (!model || !prompt) {
            this.addSystemMessage('Please select a model and enter a prompt', 'warning');
            return;
        }
        
        this.ollamaState.operationInProgress = true;
        
        const outputDiv = document.getElementById('ollama-test-output');
        if (outputDiv) {
            outputDiv.innerHTML = '<div style="padding: 12px; background: var(--bg-darker); border-radius: 8px;">Generating...</div>';
        }
        
        try {
            const response = await fetch(`${this.ollamaState.apiUrl}/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    model: model,
                    prompt: prompt,
                    stream: false
                })
            });
            
            const data = await response.json();
            
            if (data.status === 'success') {
                if (outputDiv) {
                    outputDiv.innerHTML = `
                        <div style="padding: 16px; background: var(--bg-darker); border-radius: 8px;">
                            <div style="margin-bottom: 12px; font-size: 13px; color: var(--text-muted);">
                                Model: ${data.model}
                            </div>
                            <div style="padding: 12px; background: var(--bg); border-radius: 6px; white-space: pre-wrap; font-family: inherit; line-height: 1.6;">
                                ${this.escapeHtml(data.response)}
                            </div>
                        </div>
                    `;
                }
                this.addSystemMessage('Generation completed', 'success');
            } else {
                if (outputDiv) {
                    outputDiv.innerHTML = `
                        <div style="padding: 12px; background: rgba(239, 68, 68, 0.1); border-left: 4px solid var(--danger); border-radius: 4px; color: var(--danger);">
                            Error: ${data.error || 'Unknown error'}
                        </div>
                    `;
                }
            }
        } catch (error) {
            if (outputDiv) {
                outputDiv.innerHTML = `
                    <div style="padding: 12px; background: rgba(239, 68, 68, 0.1); border-left: 4px solid var(--danger); border-radius: 4px; color: var(--danger);">
                        Error: ${error.message}
                    </div>
                `;
            }
        } finally {
            setTimeout(() => {
                this.ollamaState.operationInProgress = false;
            }, 1000);
        }
    };

    VeraChat.prototype.loadOllamaConfig = async function() {
        try {
            const response = await fetch(`${this.ollamaState.apiUrl}/config`);
            const data = await response.json();
            
            if (data.status === 'success') {
                const config = data.config;
                
                const urlEl = document.getElementById('ollama-config-url');
                const timeoutEl = document.getElementById('ollama-config-timeout');
                const thoughtEl = document.getElementById('ollama-config-thought');
                const tempEl = document.getElementById('ollama-config-temp');
                
                if (urlEl) urlEl.textContent = config.api_url || 'N/A';
                if (timeoutEl) timeoutEl.textContent = `${config.timeout || 0}s`;
                if (thoughtEl) thoughtEl.textContent = config.use_local_fallback ? 'Enabled' : 'Disabled';
                if (tempEl) tempEl.textContent = config.load_balance_strategy || 'N/A';
            }
        } catch (error) {
            console.error('Failed to load config:', error);
        }
    };

    // Keep all existing sync functions from original file...
    // (refreshComparison, renderComparison, copyModelToInstance, syncAllToInstance, etc.)
    // Copy them from the original file as-is

    // ========================================================================
    // CLEANUP
    // ========================================================================
    
    VeraChat.prototype.cleanupOllama = function() {
        console.log('Cleaning up Ollama UI...');
        this.stopOllamaUpdates();
        
        if (this.ollamaState.ws) {
            this.ollamaState.ws.close();
            this.ollamaState.ws = null;
        }
    };

    VeraChat.prototype.escapeHtml = function(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    };

})();