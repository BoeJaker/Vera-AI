// =====================================================================
// Chat Routing Controls - FIXED POSITIONING
// Add to chat-modern-ui.js after the control bar section
// =====================================================================

(() => {
    console.log('🎛️ Loading Chat Routing Controls...');

    // =====================================================================
    // Routing Control Panel
    // =====================================================================
    
    VeraChat.prototype.addRoutingControls = function() {
        console.log('🔧 Adding routing controls...');
        
        // Check if already exists
        if (document.getElementById('routing-controls')) {
            console.log('⏭️ Routing controls already exist, removing old version');
            document.getElementById('routing-controls').remove();
        }
        
        // Find the input area container
        const inputArea = document.querySelector('.input-area');
        const messageInput = document.getElementById('messageInput');
        
        if (!inputArea && !messageInput) {
            console.error('❌ Could not find input area or message input');
            return;
        }
        
        // Initialize state from localStorage
        this.routingMode = localStorage.getItem('chat-routing-mode') || 'auto';
        this.routingExpanded = localStorage.getItem('routing-expanded') === 'true';
        this.forceRouting = localStorage.getItem('force-routing') === 'true';
        
        // Create routing controls container
        const routingControls = document.createElement('div');
        routingControls.id = 'routing-controls';
        routingControls.className = 'routing-controls';
        
        routingControls.innerHTML = `
            <div class="routing-header">
                <span class="routing-label">Route:</span>
                <select id="routing-mode-select" class="routing-select">
                    <option value="auto">🤖 Auto (Triage)</option>
                    <option value="simple">⚡ Simple (Fast)</option>
                    <option value="reasoning">🧠 Reasoning</option>
                    <option value="complex">🔬 Complex (Deep)</option>
                    <option value="intermediate">📊 Intermediate</option>
                    <option value="coding">💻 Coding</option>
                    <option value="toolchain">🔧 Toolchain</option>
                    <option value="toolchain-parallel">⚡🔧 Parallel Tools</option>
                    <option value="toolchain-adaptive">🎯 Adaptive Tools</option>
                    <option value="toolchain-stepbystep">📋 Step-by-Step</option>
                    <option value="counsel">👥 Counsel (Vote)</option>
                    <option value="counsel-debate">💬 Counsel (Debate)</option>
                    <option value="counsel-synthesize">🔀 Counsel (Synthesize)</option>
                </select>
                
                <button class="routing-info-btn" id="routing-info-btn" title="Routing info">
                    ℹ️
                </button>
                
                <button class="routing-toggle-btn" id="routing-toggle-btn" title="Toggle controls">
                    ${this.routingExpanded ? '▼' : '▶'}
                </button>
            </div>
            
            <div class="routing-details" id="routing-details" style="display: ${this.routingExpanded ? 'block' : 'none'};">
                <div class="routing-option-group">
                    <label class="routing-option">
                        <input type="checkbox" id="force-routing" ${this.forceRouting ? 'checked' : ''}>
                        <span>Force routing (skip triage)</span>
                    </label>
                    
                    <label class="routing-option" id="parallel-option" style="display: none;">
                        <input type="checkbox" id="enable-parallel">
                        <span>Enable parallel execution</span>
                    </label>
                    
                    <label class="routing-option" id="counsel-models-option" style="display: none;">
                        <span>Council models:</span>
                        <input type="text" id="counsel-models" placeholder="fast,intermediate,deep" class="routing-input">
                    </label>
                </div>
                
                <div class="routing-description" id="routing-description">
                    <strong>Auto Mode:</strong> Automatically selects the best routing based on query complexity.
                </div>
            </div>
        `;
        
        // Insert BEFORE the message input (not after)
        if (messageInput) {
            // If there's a parent wrapper, insert before that wrapper
            const inputWrapper = messageInput.closest('.message-input-wrapper') || messageInput.parentElement;
            if (inputWrapper && inputWrapper.parentElement) {
                inputWrapper.parentElement.insertBefore(routingControls, inputWrapper);
                console.log('✅ Routing controls inserted before message input wrapper');
            } else {
                messageInput.parentElement.insertBefore(routingControls, messageInput);
                console.log('✅ Routing controls inserted before message input');
            }
        } else if (inputArea) {
            // Insert as first child of input area
            inputArea.insertBefore(routingControls, inputArea.firstChild);
            console.log('✅ Routing controls inserted as first child of input area');
        }
        
        // Set initial value
        const select = document.getElementById('routing-mode-select');
        if (select) {
            select.value = this.routingMode;
            console.log(`🎯 Initial routing mode: ${this.routingMode}`);
        }
        
        // Wire up event handlers
        this.initRoutingEventHandlers();
        
        // Update UI to match current mode
        this.updateRoutingUI();
        
        console.log('✅ Routing controls fully initialized');
    };
    
    // =====================================================================
    // Event Handlers
    // =====================================================================
    
    VeraChat.prototype.initRoutingEventHandlers = function() {
        const select = document.getElementById('routing-mode-select');
        const toggleBtn = document.getElementById('routing-toggle-btn');
        const infoBtn = document.getElementById('routing-info-btn');
        const forceRouting = document.getElementById('force-routing');
        
        // Mode selection
        if (select) {
            select.addEventListener('change', (e) => {
                this.routingMode = e.target.value;
                localStorage.setItem('chat-routing-mode', this.routingMode);
                this.updateRoutingUI();
                this.setControlStatus(`📍 Routing set to: ${this.getRoutingDisplayName(this.routingMode)}`);
                console.log(`🎯 Routing mode changed to: ${this.routingMode}`);
            });
        }
        
        // Toggle details
        if (toggleBtn) {
            toggleBtn.addEventListener('click', () => {
                this.routingExpanded = !this.routingExpanded;
                const details = document.getElementById('routing-details');
                if (details) {
                    details.style.display = this.routingExpanded ? 'block' : 'none';
                }
                toggleBtn.textContent = this.routingExpanded ? '▼' : '▶';
                localStorage.setItem('routing-expanded', this.routingExpanded);
            });
        }
        
        // Info button
        if (infoBtn) {
            infoBtn.addEventListener('click', () => {
                this.showRoutingInfo();
            });
        }
        
        // Force routing checkbox
        if (forceRouting) {
            forceRouting.addEventListener('change', (e) => {
                this.forceRouting = e.target.checked;
                localStorage.setItem('force-routing', this.forceRouting);
                
                if (this.forceRouting) {
                    this.setControlStatus('⚠️ Routing forced - triage bypassed');
                } else {
                    this.setControlStatus('✅ Auto-routing enabled');
                }
            });
        }
        
        console.log('✅ Routing event handlers initialized');
    };
    
    // =====================================================================
    // UI Updates
    // =====================================================================
    
    VeraChat.prototype.updateRoutingUI = function() {
        const mode = this.routingMode;
        const description = document.getElementById('routing-description');
        const parallelOption = document.getElementById('parallel-option');
        const counselModelsOption = document.getElementById('counsel-models-option');
        
        // Update description
        if (description) {
            description.innerHTML = this.getRoutingDescription(mode);
        }
        
        // Show/hide mode-specific options
        if (parallelOption) {
            parallelOption.style.display = mode.includes('toolchain') ? 'block' : 'none';
        }
        
        if (counselModelsOption) {
            counselModelsOption.style.display = mode.startsWith('counsel') ? 'block' : 'none';
        }
    };
    
    VeraChat.prototype.getRoutingDisplayName = function(mode) {
        const names = {
            'auto': 'Auto (Triage)',
            'simple': 'Simple (Fast)',
            'reasoning': 'Reasoning',
            'complex': 'Complex (Deep)',
            'intermediate': 'Intermediate',
            'coding': 'Coding',
            'toolchain': 'Toolchain',
            'toolchain-parallel': 'Parallel Tools',
            'toolchain-adaptive': 'Adaptive Tools',
            'toolchain-stepbystep': 'Step-by-Step',
            'counsel': 'Counsel (Vote)',
            'counsel-debate': 'Counsel (Debate)',
            'counsel-synthesize': 'Counsel (Synthesize)'
        };
        return names[mode] || mode;
    };
    
    VeraChat.prototype.getRoutingDescription = function(mode) {
        const descriptions = {
            'auto': '<strong>Auto Mode:</strong> Automatically selects the best routing based on query complexity using triage.',
            'simple': '<strong>Simple/Fast:</strong> Quick responses using the fast model. Best for simple questions and casual chat.',
            'reasoning': '<strong>Reasoning:</strong> Deep logical analysis with step-by-step thinking. Best for complex problems requiring careful thought.',
            'complex': '<strong>Complex/Deep:</strong> Comprehensive analysis using the deep model. Best for research and detailed explanations.',
            'intermediate': '<strong>Intermediate:</strong> Balanced responses with moderate depth. Good for most queries.',
            'coding': '<strong>Coding:</strong> Specialized for code generation and debugging tasks.',
            'toolchain': '<strong>Toolchain:</strong> Execute tools and actions automatically. Best for tasks requiring external data or actions.',
            'toolchain-parallel': '<strong>Parallel Tools:</strong> Run multiple tools simultaneously for faster results.',
            'toolchain-adaptive': '<strong>Adaptive Tools:</strong> Intelligently plan and execute multi-step tool workflows.',
            'toolchain-stepbystep': '<strong>Step-by-Step:</strong> Execute tools sequentially with clear progression.',
            'counsel': '<strong>Counsel (Vote):</strong> Multiple AI agents discuss and vote on the best response.',
            'counsel-debate': '<strong>Counsel (Debate):</strong> Agents debate different perspectives before reaching consensus.',
            'counsel-synthesize': '<strong>Counsel (Synthesize):</strong> Combine insights from multiple agents into a unified response.'
        };
        return descriptions[mode] || '<strong>Unknown mode</strong>';
    };
    
    VeraChat.prototype.showRoutingInfo = function() {
        const modal = document.createElement('div');
        modal.className = 'routing-info-modal';
        
        modal.innerHTML = `
            <div class="modal-overlay" onclick="this.parentElement.remove()"></div>
            <div class="modal-content routing-info-content">
                <div class="modal-header">
                    <h3>🎛️ Routing Modes Guide</h3>
                    <button class="modal-close" onclick="this.parentElement.parentElement.remove()">✕</button>
                </div>
                <div class="modal-body">
                    <div class="routing-info-section">
                        <h4>🤖 Auto Mode</h4>
                        <p>Let Vera decide the best route based on your query. Uses intelligent triage to classify complexity.</p>
                    </div>
                    
                    <div class="routing-info-section">
                        <h4>⚡ Direct Modes</h4>
                        <ul>
                            <li><strong>Simple:</strong> Fast responses for quick questions</li>
                            <li><strong>Intermediate:</strong> Balanced depth for general queries</li>
                            <li><strong>Reasoning:</strong> Deep logical analysis with thinking process</li>
                            <li><strong>Complex:</strong> Comprehensive research and explanation</li>
                            <li><strong>Coding:</strong> Optimized for programming tasks</li>
                        </ul>
                    </div>
                    
                    <div class="routing-info-section">
                        <h4>🔧 Toolchain Modes</h4>
                        <ul>
                            <li><strong>Standard:</strong> Execute tools as needed</li>
                            <li><strong>Parallel:</strong> Run multiple tools simultaneously</li>
                            <li><strong>Adaptive:</strong> Plan and execute complex workflows</li>
                            <li><strong>Step-by-Step:</strong> Sequential execution with clear steps</li>
                        </ul>
                    </div>
                    
                    <div class="routing-info-section">
                        <h4>👥 Counsel Modes</h4>
                        <ul>
                            <li><strong>Vote:</strong> Multiple agents vote on best answer</li>
                            <li><strong>Debate:</strong> Agents discuss different perspectives</li>
                            <li><strong>Synthesize:</strong> Combine multiple viewpoints</li>
                        </ul>
                    </div>
                    
                    <div class="routing-info-section">
                        <h4>⚙️ Options</h4>
                        <ul>
                            <li><strong>Force routing:</strong> Skip triage and use selected mode directly</li>
                            <li><strong>Parallel execution:</strong> Enable concurrent tool execution</li>
                            <li><strong>Council models:</strong> Specify which models to use in counsel mode</li>
                        </ul>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        setTimeout(() => modal.classList.add('visible'), 10);
    };
    
    // =====================================================================
    // Modified sendMessage to use routing
    // =====================================================================
    
    if (!VeraChat.prototype._originalSendMessageRouting) {
        VeraChat.prototype._originalSendMessageRouting = VeraChat.prototype.sendMessage;
    }
    
    VeraChat.prototype.sendMessage = async function() {
        const input = document.getElementById('messageInput');
        let message = input.value.trim();
        
        // Include attached pastes if present
        if (this.attachedPastes && this.attachedPastes.length > 0) {
            this.attachedPastes.forEach(attachment => {
                message += '\n\n---\n**Attached Text:**\n```\n' + attachment.content + '\n```';
            });
            this.attachedPastes = [];
            const container = document.getElementById('attachments-container');
            if (container) container.innerHTML = '';
        }
        
        if (!message || this.processing) return;
        
        this.processing = true;
        document.getElementById('sendBtn').disabled = true;
        input.disabled = true;
        
        this.addMessage('user', message);
        input.value = '';
        if (typeof this.resetTextareaHeight === 'function') {
            this.resetTextareaHeight();
        }
        
        // Check if we should use WebSocket with routing
        if (this.useWebSocket) {
            const sent = await this.sendMessageViaWebSocketWithRouting(message);
            if (sent) return;
        }
        
        // Fallback to original send
        await this._originalSendMessageRouting.call(this);
    };
    
    VeraChat.prototype.sendMessageViaWebSocketWithRouting = async function(message) {
        this.veraRobot.setState('thinking');
        
        if (!this.websocket || this.websocket.readyState !== WebSocket.OPEN) {
            return false;
        }
        
        try {
            const routingConfig = this.getRoutingConfig();
            
            this.websocket.send(JSON.stringify({
                message: message,
                files: Object.keys(this.files || {}),
                routing: routingConfig
            }));
            
            // Show routing indicator
            if (routingConfig.mode !== 'auto') {
                this.setControlStatus(`🎯 Using ${this.getRoutingDisplayName(routingConfig.mode)} mode`);
            }
            
            return true;
        } catch (error) {
            console.error('WebSocket send error:', error);
            return false;
        }
    };
    
    VeraChat.prototype.getRoutingConfig = function() {
        const mode = this.routingMode || 'auto';
        const forceRouting = document.getElementById('force-routing')?.checked || false;
        
        const config = {
            mode: mode,
            force: forceRouting
        };
        
        // Add mode-specific configuration
        if (mode.includes('toolchain')) {
            const enableParallel = document.getElementById('enable-parallel')?.checked;
            if (enableParallel !== undefined) {
                config.parallel = enableParallel;
            }
        }
        
        if (mode.startsWith('counsel')) {
            const modelsInput = document.getElementById('counsel-models')?.value;
            if (modelsInput) {
                config.models = modelsInput.split(',').map(m => m.trim());
            }
            
            // Extract counsel sub-mode
            if (mode === 'counsel-debate') {
                config.counsel_mode = 'debate';
            } else if (mode === 'counsel-synthesize') {
                config.counsel_mode = 'synthesize';
            } else {
                config.counsel_mode = 'vote';
            }
        }
        
        return config;
    };
    
    // =====================================================================
    // Styles - FIXED FOR PROPER VISIBILITY
    // =====================================================================
    
    const routingStyles = `
        /* Routing Controls - Fixed positioning */
        .routing-controls {
            background: var(--panel-bg, #1e293b);
            border: 1px solid var(--border, #334155);
            border-radius: 8px;
            margin-bottom: 12px;
            overflow: visible;
            position: relative;
            z-index: 10;
            width: 100%;
        }
        
        .routing-header {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 10px 12px;
            background: var(--bg, #0f172a);
            border-radius: 8px 8px 0 0;
        }
        
        .routing-label {
            font-size: 13px;
            font-weight: 600;
            color: var(--text-muted, #94a3b8);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            white-space: nowrap;
        }
        
        .routing-select {
            flex: 1;
            min-width: 0;
            padding: 6px 10px;
            background: var(--panel-bg, #1e293b);
            border: 1px solid var(--border, #334155);
            border-radius: 6px;
            color: var(--text, #e2e8f0);
            font-size: 13px;
            cursor: pointer;
            transition: all 0.2s;
            appearance: none;
            -webkit-appearance: none;
            -moz-appearance: none;
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%2394a3b8' d='M6 8L2 4h8z'/%3E%3C/svg%3E");
            background-repeat: no-repeat;
            background-position: right 8px center;
            padding-right: 28px;
        }
        
        .routing-select:hover {
            border-color: var(--accent, #3b82f6);
            background-color: var(--bg, #0f172a);
        }
        
        .routing-select:focus {
            outline: none;
            border-color: var(--accent, #3b82f6);
            box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.1);
        }
        
        .routing-select option {
            background: var(--panel-bg, #1e293b);
            color: var(--text, #e2e8f0);
            padding: 8px;
        }
        
        .routing-info-btn, .routing-toggle-btn {
            width: 32px;
            height: 32px;
            flex-shrink: 0;
            display: flex;
            align-items: center;
            justify-content: center;
            background: transparent;
            border: 1px solid var(--border, #334155);
            border-radius: 6px;
            color: var(--text-muted, #94a3b8);
            cursor: pointer;
            font-size: 14px;
            transition: all 0.2s;
            padding: 0;
        }
        
        .routing-info-btn:hover, .routing-toggle-btn:hover {
            background: var(--panel-bg, #1e293b);
            border-color: var(--accent, #3b82f6);
            color: var(--text, #e2e8f0);
        }
        
        .routing-details {
            padding: 12px;
            border-top: 1px solid var(--border, #334155);
            animation: slideDown 0.2s ease-out;
            background: var(--panel-bg, #1e293b);
            border-radius: 0 0 8px 8px;
        }
        
        @keyframes slideDown {
            from {
                opacity: 0;
                transform: translateY(-10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .routing-option-group {
            display: flex;
            flex-direction: column;
            gap: 8px;
            margin-bottom: 12px;
        }
        
        .routing-option {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 13px;
            color: var(--text, #e2e8f0);
            cursor: pointer;
            user-select: none;
        }
        
        .routing-option input[type="checkbox"] {
            width: 16px;
            height: 16px;
            cursor: pointer;
            flex-shrink: 0;
        }
        
        .routing-option span {
            flex: 1;
        }
        
        .routing-input {
            flex: 1;
            min-width: 0;
            padding: 6px 8px;
            background: var(--bg, #0f172a);
            border: 1px solid var(--border, #334155);
            border-radius: 4px;
            color: var(--text, #e2e8f0);
            font-size: 12px;
        }
        
        .routing-input:focus {
            outline: none;
            border-color: var(--accent, #3b82f6);
        }
        
        .routing-description {
            padding: 10px;
            background: var(--bg, #0f172a);
            border: 1px solid var(--border, #334155);
            border-radius: 6px;
            font-size: 12px;
            line-height: 1.6;
            color: var(--text-muted, #94a3b8);
        }
        
        .routing-description strong {
            color: var(--accent, #3b82f6);
        }
        
        /* Routing Info Modal */
        .routing-info-modal {
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            z-index: 100000;
            display: flex;
            align-items: center;
            justify-content: center;
            opacity: 0;
            transition: opacity 0.3s ease;
        }
        
        .routing-info-modal.visible {
            opacity: 1;
        }
        
        .modal-overlay {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.7);
            cursor: pointer;
        }
        
        .modal-content {
            position: relative;
            background: var(--panel-bg, #1e293b);
            border: 1px solid var(--border, #334155);
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
            z-index: 1;
        }
        
        .routing-info-content {
            max-width: 600px;
            max-height: 80vh;
            overflow-y: auto;
            margin: 20px;
        }
        
        .modal-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 16px 20px;
            border-bottom: 1px solid var(--border, #334155);
            position: sticky;
            top: 0;
            background: var(--panel-bg, #1e293b);
            z-index: 1;
        }
        
        .modal-header h3 {
            margin: 0;
            font-size: 18px;
            color: var(--text, #e2e8f0);
        }
        
        .modal-close {
            width: 32px;
            height: 32px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: transparent;
            border: 1px solid var(--border, #334155);
            border-radius: 6px;
            color: var(--text-muted, #94a3b8);
            cursor: pointer;
            font-size: 18px;
            transition: all 0.2s;
            padding: 0;
        }
        
        .modal-close:hover {
            background: var(--bg, #0f172a);
            border-color: var(--accent, #3b82f6);
            color: var(--text, #e2e8f0);
        }
        
        .modal-body {
            padding: 20px;
        }
        
        .routing-info-section {
            margin-bottom: 20px;
            padding: 16px;
            background: var(--bg, #0f172a);
            border: 1px solid var(--border, #334155);
            border-radius: 8px;
        }
        
        .routing-info-section:last-child {
            margin-bottom: 0;
        }
        
        .routing-info-section h4 {
            margin: 0 0 12px 0;
            color: var(--accent, #3b82f6);
            font-size: 14px;
            font-weight: 600;
        }
        
        .routing-info-section p {
            margin: 0;
            color: var(--text-muted, #94a3b8);
            font-size: 13px;
            line-height: 1.6;
        }
        
        .routing-info-section ul {
            margin: 8px 0 0 0;
            padding-left: 20px;
            color: var(--text-muted, #94a3b8);
            font-size: 13px;
            line-height: 1.8;
        }
        
        .routing-info-section li {
            margin-bottom: 6px;
        }
        
        .routing-info-section li strong {
            color: var(--text, #e2e8f0);
        }
    `;
    
    // Inject styles
    if (!document.getElementById('routing-controls-styles')) {
        const style = document.createElement('style');
        style.id = 'routing-controls-styles';
        style.textContent = routingStyles;
        document.head.appendChild(style);
    }
    
    // =====================================================================
    // Initialize on VeraChat
    // =====================================================================
    
    if (!VeraChat.prototype._routingControlsWrapped) {
        const originalInit = VeraChat.prototype.init || VeraChat.prototype._originalInit;
        
        if (originalInit) {
            VeraChat.prototype.init = async function() {
                console.log('🔄 VeraChat.init with routing controls');
                
                const result = await originalInit.call(this);
                
                // Initialize routing controls after a short delay to ensure DOM is ready
                console.log('🎛️ Scheduling routing controls initialization...');
                setTimeout(() => {
                    this.addRoutingControls();
                }, 500);
                
                return result;
            };
            
            VeraChat.prototype._routingControlsWrapped = true;
            console.log('✅ Routing controls wrapper installed');
        } else {
            console.warn('⚠️ Could not find VeraChat.init to wrap');
        }
    }
    
    // Also try immediate initialization if app instance exists
    if (typeof app !== 'undefined' && app) {
        console.log('🚀 Attempting immediate routing controls initialization');
        setTimeout(() => {
            if (typeof app.addRoutingControls === 'function') {
                app.addRoutingControls();
            } else {
                console.warn('⚠️ app.addRoutingControls not available yet');
            }
        }, 1000);
    }
    
    console.log('🚀 Chat Routing Controls module loaded');
})();