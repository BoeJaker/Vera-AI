// ollama-ui-manager.js - Following orchestrator-manager.js pattern
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
        selectedModel: null,
        modelInfo: {},
        connected: false,
        mode: 'unknown',
        modelCount: 0
    };

    // ========================================================================
    // INITIALIZATION
    // ========================================================================
    
    VeraChat.prototype.initOllama = async function() {
        console.log('Initializing Ollama UI...');
        
        // Setup WebSocket for streaming (optional)
        // this.setupOllamaWebSocket();
        
        // Start periodic updates
        this.startOllamaUpdates();
        
        // Initial load
        await this.refreshOllama();
    };

    // ========================================================================
    // WEBSOCKET MANAGEMENT (Optional - for streaming)
    // ========================================================================
    
    VeraChat.prototype.setupOllamaWebSocket = function() {
        const wsUrl = this.ollamaState.apiUrl.replace('http', 'ws') + '/ws/generate';
        
        try {
            this.ollamaState.ws = new WebSocket(wsUrl);
            
            this.ollamaState.ws.onopen = () => {
                console.log('Ollama WebSocket connected');
                this.addSystemMessage('Ollama WebSocket connected', 'success');
            };
            
            this.ollamaState.ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleOllamaMessage(data);
            };
            
            this.ollamaState.ws.onclose = () => {
                console.log('Ollama WebSocket closed, reconnecting...');
                setTimeout(() => this.setupOllamaWebSocket(), 5000);
            };
            
            this.ollamaState.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
            };
        } catch (error) {
            console.error('Failed to setup Ollama WebSocket:', error);
        }
    };

    VeraChat.prototype.handleOllamaMessage = function(data) {
        if (data.type === 'chunk') {
            // Handle streaming chunk
            console.log('Received chunk:', data.text);
        } else if (data.type === 'done') {
            console.log('Streaming complete');
        } else if (data.type === 'error') {
            console.error('Streaming error:', data.error);
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
            case 'pull':
                // Static panel, no refresh needed
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
                this.refreshModels()
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
                if (status) status.textContent = `Connected (${data.mode})`;
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
    // MODEL MANAGEMENT
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
                            <div style="font-size: 12px; color: var(--text-muted);">Click to select • Click info for details</div>
                        </div>
                    </div>
                    
                    <div style="display: flex; gap: 8px; margin-top: 12px;">
                        <button onclick="event.stopPropagation(); app.showOllamaModelInfo('${modelName}')" 
                                style="padding: 8px 16px; background: var(--accent); border: none; border-radius: 6px; color: white; cursor: pointer; font-size: 13px; font-weight: 600; transition: all 0.2s;"
                                onmouseover="this.style.opacity='0.8'"
                                onmouseout="this.style.opacity='1'">
                            ℹInfo
                        </button>
                        <button onclick="event.stopPropagation(); app.testGenerateWithModel('${modelName}')" 
                                style="padding: 8px 16px; background: var(--success); border: none; border-radius: 6px; color: white; cursor: pointer; font-size: 13px; font-weight: 600; transition: all 0.2s;"
                                onmouseover="this.style.opacity='0.8'"
                                onmouseout="this.style.opacity='1'">
                            Test
                        </button>
                        <button onclick="event.stopPropagation(); app.deleteOllamaModel('${modelName}')" 
                                style="padding: 8px 16px; background: var(--danger); border: none; border-radius: 6px; color: white; cursor: pointer; font-size: 13px; font-weight: 600; transition: all 0.2s;"
                                onmouseover="this.style.opacity='0.8'"
                                onmouseout="this.style.opacity='1'">
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
        this.addSystemMessage(`Selected model: ${modelName}`, 'info');
    };

    VeraChat.prototype.showOllamaModelInfo = async function(modelName) {
        try {
            this.addSystemMessage(`Loading info for ${modelName}...`, 'info');
            
            const response = await fetch(`${this.ollamaState.apiUrl}/models/${encodeURIComponent(modelName)}/info`);
            
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            const model = data.model;
            
            // Create modal with model info
            const infoHtml = `
                <div class="modal-overlay" onclick="this.remove()" style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.7); z-index: 10000; display: flex; align-items: center; justify-content: center;">
                    <div onclick="event.stopPropagation()" style="background: var(--bg); border-radius: 12px; padding: 24px; max-width: 700px; max-height: 85vh; overflow-y: auto; box-shadow: 0 4px 20px rgba(0,0,0,0.5);">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                            <h2 style="margin: 0; font-size: 20px;">📦 ${model.name}</h2>
                            <button onclick="this.closest('.modal-overlay').remove()" style="background: none; border: none; font-size: 28px; cursor: pointer; color: var(--text); line-height: 1;">×</button>
                        </div>
                        
                        <div style="display: grid; gap: 20px;">
                            <!-- Basic Info -->
                            <div style="padding: 16px; background: var(--bg-darker); border-radius: 8px;">
                                <h3 style="margin: 0 0 12px 0; font-size: 14px; text-transform: uppercase; color: var(--text-muted);">Model Information</h3>
                                <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px;">
                                    <div>
                                        <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">Family</div>
                                        <div style="font-size: 14px; font-weight: 600;">${model.family || 'N/A'}</div>
                                    </div>
                                    <div>
                                        <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">Parameters</div>
                                        <div style="font-size: 14px; font-weight: 600;">${model.parameter_size || 'N/A'}</div>
                                    </div>
                                    <div>
                                        <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">Quantization</div>
                                        <div style="font-size: 14px; font-weight: 600;">${model.quantization_level || 'N/A'}</div>
                                    </div>
                                    <div>
                                        <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">Format</div>
                                        <div style="font-size: 14px; font-weight: 600;">${model.format || 'N/A'}</div>
                                    </div>
                                </div>
                            </div>
                            
                            <!-- Context & Embeddings -->
                            <div style="padding: 16px; background: var(--bg-darker); border-radius: 8px;">
                                <h3 style="margin: 0 0 12px 0; font-size: 14px; text-transform: uppercase; color: var(--text-muted);">Capabilities</h3>
                                <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px;">
                                    <div>
                                        <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">Context Length</div>
                                        <div style="font-size: 18px; font-weight: 700; color: var(--accent);">${model.context_length.toLocaleString()}</div>
                                        <div style="font-size: 11px; color: var(--text-muted);">tokens</div>
                                    </div>
                                    ${model.embedding_length ? `
                                        <div>
                                            <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">Embedding Dim</div>
                                            <div style="font-size: 18px; font-weight: 700; color: var(--success);">${model.embedding_length}</div>
                                            <div style="font-size: 11px; color: var(--text-muted);">dimensions</div>
                                        </div>
                                    ` : ''}
                                </div>
                                
                                <div style="display: flex; gap: 8px; flex-wrap: wrap; margin-top: 16px;">
                                    ${model.supports_thought ? '<span style="padding: 6px 12px; background: var(--accent); border-radius: 6px; font-size: 12px; font-weight: 600;">💭 Thought Output</span>' : ''}
                                    ${model.supports_vision ? '<span style="padding: 6px 12px; background: var(--success); border-radius: 6px; font-size: 12px; font-weight: 600;">👁️ Vision</span>' : ''}
                                    ${model.supports_streaming ? '<span style="padding: 6px 12px; background: var(--info); border-radius: 6px; font-size: 12px; font-weight: 600;">⚡ Streaming</span>' : ''}
                                </div>
                            </div>
                            
                            <!-- Default Parameters -->
                            <div style="padding: 16px; background: var(--bg-darker); border-radius: 8px;">
                                <h3 style="margin: 0 0 12px 0; font-size: 14px; text-transform: uppercase; color: var(--text-muted);">Default Parameters</h3>
                                <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; font-size: 13px;">
                                    <div><span style="color: var(--text-muted);">Temperature:</span> <strong>${model.temperature}</strong></div>
                                    <div><span style="color: var(--text-muted);">Top-K:</span> <strong>${model.top_k}</strong></div>
                                    <div><span style="color: var(--text-muted);">Top-P:</span> <strong>${model.top_p}</strong></div>
                                    <div><span style="color: var(--text-muted);">Num Predict:</span> <strong>${model.num_predict === -1 ? 'unlimited' : model.num_predict}</strong></div>
                                </div>
                            </div>
                            
                            ${model.license ? `
                                <div style="padding: 16px; background: var(--bg-darker); border-radius: 8px;">
                                    <h3 style="margin: 0 0 8px 0; font-size: 14px; text-transform: uppercase; color: var(--text-muted);">License</h3>
                                    <div style="font-size: 12px;">${model.license}</div>
                                </div>
                            ` : ''}
                        </div>
                    </div>
                </div>
            `;
            
            document.body.insertAdjacentHTML('beforeend', infoHtml);
            
        } catch (error) {
            this.addSystemMessage(`Failed to load model info: ${error.message}`, 'error');
        }
    };

    VeraChat.prototype.testGenerateWithModel = async function(modelName) {
        this.ollamaState.selectedModel = modelName;
        
        // Populate dropdown
        const select = document.getElementById('ollama-test-model');
        if (select) {
            select.value = modelName;
        }
        
        // Switch to generate panel
        this.switchOllamaPanel('generate');
        
        this.addSystemMessage(`Ready to test ${modelName}`, 'info');
    };

    VeraChat.prototype.pullOllamaModel = async function() {
        const modelName = document.getElementById('ollama-pull-model-name')?.value;
        if (!modelName) {
            this.addSystemMessage('Please enter a model name', 'error');
            return;
        }
        
        try {
            this.addSystemMessage(`Pulling model ${modelName}... This may take a while.`, 'info');
            
            const response = await fetch(`${this.ollamaState.apiUrl}/models/pull`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    model_name: modelName,
                    stream: false
                })
            });
            
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            this.addSystemMessage(data.message, 'success');
            
            // Reload models
            await this.refreshModels();
            
            // Clear input
            const input = document.getElementById('ollama-pull-model-name');
            if (input) input.value = '';
            
            // Switch to models panel to see the new model
            this.switchOllamaPanel('models');
            
        } catch (error) {
            this.addSystemMessage(`Failed to pull model: ${error.message}`, 'error');
        }
    };

    VeraChat.prototype.deleteOllamaModel = async function(modelName) {
        if (!confirm(`Delete model "${modelName}"? This cannot be undone.`)) {
            return;
        }
        
        try {
            this.addSystemMessage(`Deleting ${modelName}...`, 'info');
            
            const response = await fetch(`${this.ollamaState.apiUrl}/models/${encodeURIComponent(modelName)}`, {
                method: 'DELETE'
            });
            
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            this.addSystemMessage(data.message, 'success');
            
            // Clear selection if this was the selected model
            if (this.ollamaState.selectedModel === modelName) {
                this.ollamaState.selectedModel = null;
            }
            
            // Reload models
            await this.refreshModels();
            
        } catch (error) {
            this.addSystemMessage(`Failed to delete model: ${error.message}`, 'error');
        }
    };

    // ========================================================================
    // TEXT GENERATION
    // ========================================================================
    
    VeraChat.prototype.testOllamaGeneration = async function() {
        const model = document.getElementById('ollama-test-model')?.value;
        const prompt = document.getElementById('ollama-test-prompt')?.value || 'Hello, how are you?';
        
        if (!model) {
            this.addSystemMessage('Please select a model', 'error');
            return;
        }
        
        try {
            const outputDiv = document.getElementById('ollama-test-output');
            if (outputDiv) {
                outputDiv.innerHTML = '<div style="padding: 12px; background: var(--bg-darker); border-radius: 6px; color: var(--text-muted);">Generating...</div>';
            }
            
            const response = await fetch(`${this.ollamaState.apiUrl}/test-generation?model=${encodeURIComponent(model)}&prompt=${encodeURIComponent(prompt)}`, {
                method: 'POST'
            });
            
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            
            if (outputDiv) {
                outputDiv.innerHTML = `
                    <div style="padding: 16px; background: var(--bg-darker); border-radius: 8px; margin-top: 16px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                            <div style="font-size: 12px; color: var(--text-muted); text-transform: uppercase; font-weight: 600;">Response</div>
                            <div style="font-size: 11px; color: var(--text-muted);">
                                ${data.duration_seconds}s • ${data.tokens_per_second} tok/s
                            </div>
                        </div>
                        <div style="white-space: pre-wrap; line-height: 1.6; padding: 12px; background: var(--bg); border-radius: 6px;">${this.escapeHtml(data.response)}</div>
                    </div>
                `;
            }
            
            this.addSystemMessage('✓ Generation complete', 'success');
            
        } catch (error) {
            this.addSystemMessage(`Generation failed: ${error.message}`, 'error');
            
            const outputDiv = document.getElementById('ollama-test-output');
            if (outputDiv) {
                outputDiv.innerHTML = `<div style="padding: 12px; background: var(--danger); color: white; border-radius: 6px; margin-top: 16px;">Error: ${this.escapeHtml(error.message)}</div>`;
            }
        }
    };

    VeraChat.prototype.populateTestModelDropdown = function() {
        const select = document.getElementById('ollama-test-model');
        if (!select) return;
        
        if (this.ollamaState.models.length === 0) {
            select.innerHTML = '<option>No models available - Pull a model first</option>';
            return;
        }
        
        select.innerHTML = this.ollamaState.models.map(model => {
            const modelName = model.model || model.name || 'Unknown';
            const selected = modelName === this.ollamaState.selectedModel ? 'selected' : '';
            return `<option value="${modelName}" ${selected}>${modelName}</option>`;
        }).join('');
    };

    // ========================================================================
    // CONFIGURATION
    // ========================================================================
    
    VeraChat.prototype.loadOllamaConfig = async function() {
        try {
            const response = await fetch(`${this.ollamaState.apiUrl}/config`);
            const data = await response.json();
            const config = data.config;
            
            // Update config display
            const elements = {
                'ollama-config-url': config.api_url,
                'ollama-config-timeout': `${config.timeout}s`,
                'ollama-config-thought': config.enable_thought_capture ? 'Enabled' : 'Disabled',
                'ollama-config-temp': config.temperature
            };
            
            Object.entries(elements).forEach(([id, value]) => {
                const elem = document.getElementById(id);
                if (elem) elem.textContent = value;
            });
            
        } catch (error) {
            console.error('Failed to load Ollama config:', error);
        }
    };

    VeraChat.prototype.reconnectOllama = async function() {
        try {
            this.addSystemMessage('Reconnecting to Ollama...', 'info');
            
            const response = await fetch(`${this.ollamaState.apiUrl}/reconnect`, {
                method: 'POST'
            });
            
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            this.addSystemMessage(data.message, data.connected ? 'success' : 'error');
            
            await this.refreshHealth();
            await this.refreshModels();
            
        } catch (error) {
            this.addSystemMessage(`Reconnection failed: ${error.message}`, 'error');
        }
    };

    // ========================================================================
    // CLEANUP
    // ========================================================================
    
    VeraChat.prototype.cleanupOllama = function() {
        console.log('Cleaning up Ollama UI...');
        
        // Stop updates
        this.stopOllamaUpdates();
        
        // Close WebSocket
        if (this.ollamaState.ws) {
            this.ollamaState.ws.close();
            this.ollamaState.ws = null;
        }
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