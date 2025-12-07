// config-manager.js
(() => {
    // ========================================================================
    // CONFIG STATE
    // ========================================================================
    
    VeraChat.prototype.configState = {
        currentSection: 'ollama',
        apiUrl: 'http://llm.int:8888/api/config',
        originalConfig: {},
        modifiedConfig: {},
        hasChanges: false,
        sections: [],
        updateInterval: null
    };

    // ========================================================================
    // INITIALIZATION
    // ========================================================================
    
    VeraChat.prototype.initConfig = async function() {
        console.log('Initializing configuration UI...');
        
        // Load current configuration
        await this.loadConfiguration();
        
        // Start hot-reload monitoring if enabled
        if (this.configState.originalConfig?.enable_hot_reload) {
            this.startConfigMonitoring();
        }
    };

    // ========================================================================
    // CONFIGURATION LOADING
    // ========================================================================
    
    VeraChat.prototype.loadConfiguration = async function() {
        try {
            const response = await fetch(`${this.configState.apiUrl}`);
            const data = await response.json();
            
            this.configState.originalConfig = JSON.parse(JSON.stringify(data.config));
            this.configState.modifiedConfig = JSON.parse(JSON.stringify(data.config));
            this.configState.hasChanges = false;
            
            // Extract sections dynamically (only nested objects, not root-level fields)
            const rootLevelFields = ['enable_hot_reload', 'config_file'];
            this.configState.sections = Object.keys(data.config).filter(key => 
                typeof data.config[key] === 'object' && 
                !Array.isArray(data.config[key]) &&
                !rootLevelFields.includes(key)
            );
            
            // Add general settings section for root-level fields
            this.configState.sections.push('general');
            
            // Render the navigation and content
            this.renderConfigUI();
            
        } catch (error) {
            console.error('Failed to load configuration:', error);
            this.addSystemMessage('Failed to load configuration', 'error');
        }
    };

    // ========================================================================
    // UI RENDERING
    // ========================================================================
    
    VeraChat.prototype.renderConfigUI = function() {
        const container = document.getElementById('config-container');
        if (!container) {
            console.warn('Config container not found');
            return;
        }
        
        container.innerHTML = `
            <!-- Header -->
            <div style="padding: 16px; background: var(--bg-darker); border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <h2 style="margin: 0; font-size: 18px;">⚙️ System Configuration</h2>
                    <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">
                        <span id="config-hot-reload-indicator" style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #ef4444; margin-right: 6px;"></span>
                        <span id="config-reload-status">Hot Reload: Unknown</span>
                    </div>
                </div>
                
                <div style="display: flex; gap: 8px; align-items: center;">
                    <span id="config-changes-indicator" style="display: none; font-size: 12px; color: var(--warning); font-weight: 600;">● Unsaved Changes</span>
                    <button onclick="app.discardConfigChanges()" id="config-discard-btn" style="padding: 8px 16px; background: var(--bg); border: 1px solid var(--border); border-radius: 4px; color: var(--text); cursor: pointer; font-size: 12px;" disabled>
                        Discard
                    </button>
                    <button onclick="app.saveConfiguration()" id="config-save-btn" style="padding: 8px 16px; background: var(--success); border: none; border-radius: 4px; color: white; cursor: pointer; font-size: 12px; font-weight: 600;" disabled>
                        💾 Save Configuration
                    </button>
                    <button onclick="app.reloadConfiguration()" style="padding: 8px 16px; background: var(--accent); border: none; border-radius: 4px; color: white; cursor: pointer; font-size: 12px;">
                        🔄 Reload
                    </button>
                </div>
            </div>
            
            <!-- Navigation -->
            <div style="padding: 12px 16px; background: var(--bg-darker); border-bottom: 1px solid var(--border); display: flex; gap: 8px; overflow-x: auto;">
                ${this.renderConfigNavigation()}
            </div>
            
            <!-- Content Area -->
            <div style="height: calc(100% - 120px); overflow-y: auto; padding: 16px;">
                ${this.renderConfigSections()}
            </div>
        `;
        
        // Update hot reload indicator
        this.updateHotReloadIndicator();
        
        // Show first section
        this.switchConfigSection(this.configState.currentSection);
    };

    VeraChat.prototype.renderConfigNavigation = function() {
        const sectionLabels = {
            'ollama': 'Ollama',
            'models': 'Models',
            'memory': 'Memory',
            'orchestrator': 'Orchestrator',
            'infrastructure': 'Infrastructure',
            'proactive_focus': 'Focus',
            'playwright': 'Browser',
            'logging': 'Logging',
            'general': 'General',
            'appearance': 'Appearance'
        };
        
        return this.configState.sections.map(section => {
            const label = sectionLabels[section] || section;
            return `
                <button class="config-nav-btn" 
                        data-section="${section}" 
                        onclick="app.switchConfigSection('${section}')"
                        style="padding: 8px 16px; background: var(--bg); border: none; border-radius: 4px; cursor: pointer; font-size: 13px; white-space: nowrap;">
                    ${label}
                </button>
            `;
        }).join('');
    };

    VeraChat.prototype.renderConfigSections = function() {
        return this.configState.sections.map(section => {
            return `
                <div id="config-panel-${section}" class="config-panel" style="display: none;">
                    ${this.renderConfigSection(section)}
                </div>
            `;
        }).join('');
    };

    VeraChat.prototype.renderConfigSection = function(section) {
        if (section === 'general') {
            return this.renderGeneralSection();
        }
        
        const config = this.configState.modifiedConfig[section];
        if (!config) return '<p style="color: var(--text-muted);">No configuration available</p>';
        
        const sectionDescriptions = {
            'ollama': 'Configure Ollama API connection and inference parameters',
            'models': 'Select and configure AI models for different tasks',
            'memory': 'Memory system and knowledge graph database settings',
            'orchestrator': 'Task orchestration and worker pool configuration',
            'infrastructure': 'Advanced infrastructure management (Docker, Proxmox)',
            'proactive_focus': 'Proactive cognition and autonomous focus settings',
            'playwright': 'Browser automation configuration',
            'logging': 'Logging levels and output settings'
        };
        
        let html = `
            <div style="max-width: 900px;">
                <div style="margin-bottom: 24px;">
                    <h3 style="margin: 0 0 8px 0; font-size: 18px; text-transform: capitalize;">${section.replace(/_/g, ' ')}</h3>
                    <p style="margin: 0; font-size: 13px; color: var(--text-muted);">
                        ${sectionDescriptions[section] || 'Configure settings for this section'}
                    </p>
                </div>
                
                <div style="display: grid; gap: 20px;">
        `;
        
        // Group related settings
        const groups = this.groupConfigSettings(section, config);
        
        for (const [groupName, settings] of Object.entries(groups)) {
            html += `
                <div style="padding: 20px; background: var(--bg); border-radius: 8px; border-left: 3px solid var(--accent);">
                    ${groupName !== 'default' ? `<h4 style="margin: 0 0 16px 0; font-size: 14px; text-transform: uppercase; color: var(--text-muted);">${groupName}</h4>` : ''}
                    <div style="display: grid; gap: 16px;">
                        ${settings.map(key => this.renderConfigField(section, key, config[key])).join('')}
                    </div>
                </div>
            `;
        }
        
        html += `
                </div>
            </div>
        `;
        
        return html;
    };

    VeraChat.prototype.groupConfigSettings = function(section, config) {
        const groups = { default: [] };
        
        // Define logical groupings for each section
        const groupings = {
            'ollama': {
                'Connection': ['api_url', 'timeout', 'use_local_fallback', 'connection_retry_attempts', 'connection_retry_delay'],
                'Thought Capture': ['enable_thought_capture', 'thought_display_format'],
                'Inference Defaults': ['temperature', 'top_k', 'top_p', 'num_predict', 'repeat_penalty'],
                'Metadata': ['cache_model_metadata', 'metadata_cache_ttl']
            },
            'models': {
                'Model Selection': ['embedding_model', 'fast_llm', 'intermediate_llm', 'deep_llm', 'reasoning_llm', 'tool_llm'],
                'Temperature Settings': ['fast_temperature', 'intermediate_temperature', 'deep_temperature', 'reasoning_temperature', 'tool_temperature'],
                'Advanced Parameters': ['fast_top_k', 'fast_top_p', 'intermediate_top_k', 'intermediate_top_p', 'deep_top_k', 'deep_top_p', 'reasoning_top_k', 'reasoning_top_p', 'tool_top_k', 'tool_top_p'],
                'Context Management': ['max_context_tokens', 'context_overflow_strategy']
            },
            'memory': {
                'Storage Paths': ['chroma_path', 'chroma_dir', 'archive_path'],
                'Neo4j Database': ['neo4j_uri', 'neo4j_user', 'neo4j_password'],
                'Search Settings': ['vector_search_k', 'plan_vector_search_k'],
                'Management': ['enable_memory_triage', 'auto_persist', 'persist_interval']
            },
            'orchestrator': {
                'Connection': ['redis_url', 'cpu_threshold'],
                'Worker Pools': ['llm_workers', 'whisper_workers', 'tool_workers', 'ml_model_workers', 'background_workers', 'general_workers'],
                'Timeouts': ['triage_timeout', 'toolchain_timeout', 'llm_timeout', 'fast_llm_timeout']
            },
            'infrastructure': {
                'Feature Flags': ['enable_infrastructure', 'enable_docker', 'enable_proxmox', 'auto_scale', 'max_resources'],
                'Docker': ['docker_url', 'docker_registry'],
                'Proxmox': ['proxmox_host', 'proxmox_user', 'proxmox_password', 'proxmox_verify_ssl', 'proxmox_node'],
                'Resource Management': ['idle_resource_cleanup_interval', 'max_idle_time']
            }
        };
        
        if (groupings[section]) {
            for (const [groupName, keys] of Object.entries(groupings[section])) {
                groups[groupName] = keys.filter(key => key in config);
            }
        } else {
            groups.default = Object.keys(config);
        }
        
        return groups;
    };

    VeraChat.prototype.renderConfigField = function(section, key, value) {
        const fieldId = `config-${section}-${key}`;
        
        // Handle 'general' section which has root-level fields
        const currentValue = section === 'general' 
            ? this.configState.modifiedConfig[key]
            : this.configState.modifiedConfig[section][key];
        const originalValue = section === 'general'
            ? this.configState.originalConfig[key]
            : this.configState.originalConfig[section][key];
        const hasChanged = JSON.stringify(currentValue) !== JSON.stringify(originalValue);
        
        const fieldLabel = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        const fieldDescription = this.getFieldDescription(section, key);
        
        let inputHtml = '';
        
        if (typeof value === 'boolean') {
            inputHtml = `
                <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                    <input type="checkbox" 
                           id="${fieldId}" 
                           ${currentValue ? 'checked' : ''}
                           onchange="app.updateConfigValue('${section}', '${key}', this.checked)"
                           style="width: 18px; height: 18px; cursor: pointer;">
                    <span style="font-size: 13px;">${currentValue ? 'Enabled' : 'Disabled'}</span>
                </label>
            `;
        } else if (typeof value === 'number') {
            const isFloat = value % 1 !== 0;
            inputHtml = `
                <input type="number" 
                       id="${fieldId}" 
                       value="${currentValue}"
                       ${isFloat ? 'step="0.1"' : ''}
                       onchange="app.updateConfigValue('${section}', '${key}', ${isFloat ? 'parseFloat(this.value)' : 'parseInt(this.value)'})"
                       style="width: 100%; padding: 8px; background: var(--bg-darker); border: 1px solid ${hasChanged ? 'var(--warning)' : 'var(--border)'}; border-radius: 4px; color: var(--text); font-size: 13px;">
            `;
        } else if (key.includes('password') || key.includes('token')) {
            inputHtml = `
                <input type="password" 
                       id="${fieldId}" 
                       value="${currentValue || ''}"
                       oninput="app.updateConfigValue('${section}', '${key}', this.value)"
                       placeholder="Enter ${fieldLabel.toLowerCase()}"
                       style="width: 100%; padding: 8px; background: var(--bg-darker); border: 1px solid ${hasChanged ? 'var(--warning)' : 'var(--border)'}; border-radius: 4px; color: var(--text); font-size: 13px; font-family: monospace;">
            `;
        } else if (this.getFieldOptions(section, key)) {
            const options = this.getFieldOptions(section, key);
            inputHtml = `
                <select id="${fieldId}" 
                        onchange="app.updateConfigValue('${section}', '${key}', this.value)"
                        style="width: 100%; padding: 8px; background: var(--bg-darker); border: 1px solid ${hasChanged ? 'var(--warning)' : 'var(--border)'}; border-radius: 4px; color: var(--text); font-size: 13px;">
                    ${options.map(opt => `<option value="${opt}" ${currentValue === opt ? 'selected' : ''}>${opt}</option>`).join('')}
                </select>
            `;
        } else {
            inputHtml = `
                <input type="text" 
                       id="${fieldId}" 
                       value="${currentValue || ''}"
                       oninput="app.updateConfigValue('${section}', '${key}', this.value)"
                       placeholder="Enter ${fieldLabel.toLowerCase()}"
                       style="width: 100%; padding: 8px; background: var(--bg-darker); border: 1px solid ${hasChanged ? 'var(--warning)' : 'var(--border)'}; border-radius: 4px; color: var(--text); font-size: 13px;">
            `;
        }
        
        return `
            <div style="display: grid; gap: 6px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <label style="font-size: 13px; font-weight: 600; color: ${hasChanged ? 'var(--warning)' : 'var(--text)'};">
                        ${fieldLabel}
                        ${hasChanged ? '<span style="margin-left: 6px;">●</span>' : ''}
                    </label>
                    ${hasChanged ? `
                        <button onclick="app.resetConfigField('${section}', '${key}')" 
                                style="padding: 2px 8px; background: var(--bg-darker); border: 1px solid var(--border); border-radius: 3px; color: var(--text-muted); cursor: pointer; font-size: 11px;">
                            Reset
                        </button>
                    ` : ''}
                </div>
                ${inputHtml}
                ${fieldDescription ? `<div style="font-size: 11px; color: var(--text-muted);">${fieldDescription}</div>` : ''}
            </div>
        `;
    };

    VeraChat.prototype.renderGeneralSection = function() {
        const generalKeys = ['enable_hot_reload', 'config_file'];
        const config = this.configState.modifiedConfig;
        
        return `
            <div style="max-width: 900px;">
                <div style="margin-bottom: 24px;">
                    <h3 style="margin: 0 0 8px 0; font-size: 18px;">General Settings</h3>
                    <p style="margin: 0; font-size: 13px; color: var(--text-muted);">
                        System-wide configuration options
                    </p>
                </div>
                
                <div style="padding: 20px; background: var(--bg); border-radius: 8px; border-left: 3px solid var(--accent);">
                    <div style="display: grid; gap: 16px;">
                        ${generalKeys.map(key => this.renderConfigField('general', key, config[key])).join('')}
                    </div>
                </div>
                
                <div style="margin-top: 20px; padding: 16px; background: var(--bg-darker); border-radius: 8px; border-left: 3px solid var(--info);">
                    <h4 style="margin: 0 0 12px 0; font-size: 14px;">Configuration Info</h4>
                    <div style="font-size: 12px; color: var(--text-muted); display: grid; gap: 8px;">
                        <div>Last loaded: <span id="config-last-loaded">Just now</span></div>
                        <div>Total sections: ${this.configState.sections.length}</div>
                        <div>Hot reload: ${config.enable_hot_reload ? '✓ Enabled' : '✗ Disabled'}</div>
                    </div>
                </div>
            </div>
        `;
    };

    VeraChat.prototype.getFieldDescription = function(section, key) {
        const descriptions = {
            'ollama': {
                'api_url': 'URL endpoint for Ollama API service',
                'timeout': 'Maximum time (seconds) to wait for API responses',
                'enable_thought_capture': 'Capture and display model reasoning chains',
                'thought_display_format': 'How to display captured thoughts (inline, separate, minimal)',
                'temperature': 'Randomness in output (0 = deterministic, 1 = creative)',
                'top_k': 'Consider only top K most likely tokens',
                'top_p': 'Cumulative probability threshold (nucleus sampling)',
                'num_predict': 'Max tokens to generate (-1 = unlimited)',
                'repeat_penalty': 'Penalty for repeating tokens (>1 = less repetition)'
            },
            'models': {
                'fast_llm': 'Quick responses for simple queries',
                'intermediate_llm': 'Balanced quality and speed',
                'deep_llm': 'Best quality for complex tasks',
                'reasoning_llm': 'Step-by-step logical reasoning',
                'tool_llm': 'Specialized for tool execution',
                'max_context_tokens': 'Maximum context window size',
                'context_overflow_strategy': 'What to do when context exceeds limit'
            },
            'memory': {
                'neo4j_uri': 'Neo4j database connection string',
                'vector_search_k': 'Number of similar memories to retrieve',
                'auto_persist': 'Automatically save memory changes',
                'persist_interval': 'Seconds between auto-save operations'
            },
            'orchestrator': {
                'redis_url': 'Redis connection for task queuing',
                'cpu_threshold': 'Pause workers when CPU exceeds this %',
                'llm_workers': 'Workers for language model tasks',
                'tool_workers': 'Workers for tool execution',
                'whisper_workers': 'Workers for audio transcription'
            },
            'infrastructure': {
                'enable_infrastructure': 'Enable advanced infrastructure management',
                'enable_docker': 'Allow Docker container orchestration',
                'enable_proxmox': 'Allow Proxmox VM management',
                'auto_scale': 'Automatically scale resources based on load'
            },
            'proactive_focus': {
                'enabled': 'Enable autonomous background thinking',
                'iteration_interval': 'Seconds between proactive thoughts',
                'auto_execute': 'Automatically execute proactive actions'
            }
        };
        
        return descriptions[section]?.[key] || '';
    };

    VeraChat.prototype.getFieldOptions = function(section, key) {
        const options = {
            'ollama': {
                'thought_display_format': ['inline', 'separate', 'minimal']
            },
            'models': {
                'context_overflow_strategy': ['truncate', 'summarize', 'error']
            },
            'playwright': {
                'browser_type': ['chromium', 'firefox', 'webkit']
            },
            'logging': {
                'level': ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
            }
        };
        
        return options[section]?.[key] || null;
    };

    // ========================================================================
    // SECTION SWITCHING
    // ========================================================================
    
    VeraChat.prototype.switchConfigSection = function(section) {
        // Update navigation
        document.querySelectorAll('.config-nav-btn').forEach(btn => {
            btn.style.background = btn.dataset.section === section ? 'var(--accent)' : 'var(--bg)';
            btn.style.color = btn.dataset.section === section ? 'white' : 'var(--text)';
        });
        
        // Update panels
        document.querySelectorAll('.config-panel').forEach(panel => {
            panel.style.display = 'none';
        });
        
        const activePanel = document.getElementById(`config-panel-${section}`);
        if (activePanel) {
            activePanel.style.display = 'block';
        }
        
        this.configState.currentSection = section;
    };

    // ========================================================================
    // VALUE UPDATES
    // ========================================================================
    
    VeraChat.prototype.updateConfigValue = function(section, key, value) {
        if (section === 'general') {
            this.configState.modifiedConfig[key] = value;
        } else {
            this.configState.modifiedConfig[section][key] = value;
        }
        
        this.checkForChanges();
    };

    VeraChat.prototype.resetConfigField = function(section, key) {
        if (section === 'general') {
            this.configState.modifiedConfig[key] = this.configState.originalConfig[key];
        } else {
            this.configState.modifiedConfig[section][key] = this.configState.originalConfig[section][key];
        }
        
        // Re-render just this section
        const panel = document.getElementById(`config-panel-${section}`);
        if (panel) {
            panel.innerHTML = this.renderConfigSection(section);
        }
        
        this.checkForChanges();
    };

    VeraChat.prototype.checkForChanges = function() {
        this.configState.hasChanges = JSON.stringify(this.configState.originalConfig) !== 
                                      JSON.stringify(this.configState.modifiedConfig);
        
        // Update UI indicators
        const indicator = document.getElementById('config-changes-indicator');
        const saveBtn = document.getElementById('config-save-btn');
        const discardBtn = document.getElementById('config-discard-btn');
        
        if (indicator) indicator.style.display = this.configState.hasChanges ? 'block' : 'none';
        if (saveBtn) saveBtn.disabled = !this.configState.hasChanges;
        if (discardBtn) discardBtn.disabled = !this.configState.hasChanges;
    };

    // ========================================================================
    // SAVE/RELOAD
    // ========================================================================
    
    VeraChat.prototype.saveConfiguration = async function() {
        if (!this.configState.hasChanges) return;
        
        try {
            this.addSystemMessage('Saving configuration...', 'info');
            
            const response = await fetch(`${this.configState.apiUrl}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(this.configState.modifiedConfig)
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const data = await response.json();
            this.addSystemMessage('✓ Configuration saved successfully', 'success');
            
            // Update original config to match
            this.configState.originalConfig = JSON.parse(JSON.stringify(this.configState.modifiedConfig));
            this.checkForChanges();
            
        } catch (error) {
            this.addSystemMessage(`Failed to save configuration: ${error.message}`, 'error');
        }
    };

    VeraChat.prototype.reloadConfiguration = async function() {
        if (this.configState.hasChanges) {
            if (!confirm('You have unsaved changes. Reload anyway?')) {
                return;
            }
        }
        
        await this.loadConfiguration();
        this.addSystemMessage('✓ Configuration reloaded', 'success');
    };

    VeraChat.prototype.discardConfigChanges = function() {
        if (!confirm('Discard all unsaved changes?')) return;
        
        this.configState.modifiedConfig = JSON.parse(JSON.stringify(this.configState.originalConfig));
        this.renderConfigUI();
        this.switchConfigSection(this.configState.currentSection);
        this.checkForChanges();
        
        this.addSystemMessage('Changes discarded', 'info');
    };

    // ========================================================================
    // HOT RELOAD MONITORING
    // ========================================================================
    
    VeraChat.prototype.startConfigMonitoring = function() {
        if (this.configState.updateInterval) {
            clearInterval(this.configState.updateInterval);
        }
        
        this.configState.updateInterval = setInterval(async () => {
            if (this.activeTab === 'config') {
                await this.checkConfigChanges();
            }
        }, 5000);
    };

    VeraChat.prototype.checkConfigChanges = async function() {
        try {
            const response = await fetch(`${this.configState.apiUrl}/status`);
            const data = await response.json();
            
            // Update indicator based on hot reload status
            if (data.hot_reload_enabled) {
                this.updateHotReloadIndicator(true, data.last_reload);
            }
            
        } catch (error) {
            console.error('Config status check failed:', error);
        }
    };

    VeraChat.prototype.updateHotReloadIndicator = function(enabled = null, lastReload = null) {
        const indicator = document.getElementById('config-hot-reload-indicator');
        const status = document.getElementById('config-reload-status');
        
        if (enabled === null) {
            enabled = this.configState.originalConfig?.enable_hot_reload || false;
        }
        
        if (indicator) {
            indicator.style.background = enabled ? '#22c55e' : '#ef4444';
        }
        
        if (status) {
            status.textContent = enabled ? 'Hot Reload: Active' : 'Hot Reload: Disabled';
        }
    };

    // ========================================================================
    // CLEANUP
    // ========================================================================
    
    VeraChat.prototype.cleanupConfig = function() {
        console.log('Cleaning up config UI...');
        
        if (this.configState.updateInterval) {
            clearInterval(this.configState.updateInterval);
            this.configState.updateInterval = null;
        }
    };

})();