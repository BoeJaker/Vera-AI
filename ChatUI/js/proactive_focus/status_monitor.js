(() => {
    // ============================================================
    // PROACTIVE FOCUS STATUS UI
    // ============================================================
    
    // Initialize state storage on first load
    if (!VeraChat.prototype._focusStatusState) {
        VeraChat.prototype._focusStatusState = {
            consoleLines: [],
            currentStage: null,
            stageActivity: null,
            stageProgress: 0,
            stageTotal: 0,
            consoleVisible: false,
            inLLMThought: false,  
            pendingThoughtChunks: [],  // NEW: Buffer chunks when UI not ready
            currentThoughtBuffer: ""
        };
    }
    VeraChat.prototype.initProactiveFocusStatusUI = function() {
        // Add status panel to focus tab
        const focusTab = document.getElementById('tab-focus');
        if (!focusTab) return;
        
        // Remove existing if present (to recreate with fresh state)
        const existing = document.getElementById('proactiveFocusStatus');
        if (existing) existing.remove();
        
        // Create status container
        const statusContainer = document.createElement('div');
        statusContainer.id = 'proactiveFocusStatus';
        statusContainer.style.cssText = `
            position: sticky;
            top: 0;
            z-index: 100;
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            border-bottom: 2px solid #334155;
            padding: 16px;
            margin-bottom: 20px;
        `;
        
        statusContainer.innerHTML = `
            <!-- Stage Indicator -->
            <div id="currentStagePanel" style="display: none; margin-bottom: 12px; padding: 12px; background: rgba(59, 130, 246, 0.1); border-left: 4px solid #3b82f6; border-radius: 6px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <div id="stageSpinner" class="spinner" style="width: 16px; height: 16px; border: 2px solid #3b82f6; border-top: 2px solid transparent; border-radius: 50%; animation: spin 1s linear infinite;"></div>
                        <span id="stageName" style="color: #60a5fa; font-weight: 600; font-size: 14px;">Initializing...</span>
                    </div>
                    <button onclick="app.toggleStreamConsole()" class="panel-btn" style="font-size: 11px; padding: 4px 8px;">
                        <span id="consoleToggleIcon">📜</span> Console
                    </button>
                </div>
                <div id="stageActivity" style="color: #94a3b8; font-size: 12px; margin-bottom: 8px;">Preparing...</div>
                <div id="stageProgressBar" style="display: none; background: rgba(0, 0, 0, 0.3); border-radius: 4px; height: 6px; overflow: hidden;">
                    <div id="stageProgressFill" style="background: linear-gradient(90deg, #3b82f6, #8b5cf6); height: 100%; width: 0%; transition: width 0.3s ease;"></div>
                </div>
                <div id="stageProgressText" style="display: none; color: #64748b; font-size: 11px; margin-top: 4px; text-align: right;"></div>
            </div>
            
            <!-- Stream Console (collapsible) -->
            <div id="streamConsole" style="display: none; background: #0f172a; border: 1px solid #334155; border-radius: 6px; padding: 12px; max-height: 300px; overflow-y: auto; font-family: 'Monaco', 'Courier New', monospace; font-size: 12px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; padding-bottom: 8px; border-bottom: 1px solid #334155;">
                    <span style="color: #94a3b8; font-weight: 600;">Live Output Console</span>
                    <button onclick="app.clearStreamConsole()" class="panel-btn" style="font-size: 10px; padding: 2px 6px;">Clear</button>
                </div>
                <div id="streamConsoleOutput"></div>
            </div>
        `;
        
        // Add CSS for spinner animation and collapsible thoughts
        const styleId = 'proactiveFocusStyles';
        if (!document.getElementById(styleId)) {
            const style = document.createElement('style');
            style.id = styleId;
            style.textContent = `
                @keyframes spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }
                
                .stream-line {
                    margin: 2px 0;
                    padding: 4px 8px;
                    border-radius: 4px;
                    line-height: 1.4;
                    word-wrap: break-word;
                }
                
                .stream-line.info {
                    color: #cbd5e1;
                    background: rgba(148, 163, 184, 0.05);
                }
                
                .stream-line.success {
                    color: #34d399;
                    background: rgba(16, 185, 129, 0.1);
                    font-weight: 600;
                }
                
                .stream-line.warning {
                    color: #fbbf24;
                    background: rgba(245, 158, 11, 0.1);
                }
                
                .stream-line.error {
                    color: #f87171;
                    background: rgba(239, 68, 68, 0.1);
                    font-weight: 600;
                }
                
                /* LLM Thought styling */
                .stream-line.llm-thought {
                    background: rgba(138, 92, 246, 0.15);
                    border-left: 3px solid #8b5cf6;
                    padding: 8px 12px;
                    margin: 4px 0;
                }
                
                .stream-line.llm-thought.completed {
                    background: rgba(138, 92, 246, 0.08);
                    border-left: 3px solid #7c3aed;
                }
                
                .stream-line.llm-thought .thought-header {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    cursor: pointer;
                    user-select: none;
                }
                
                .stream-line.llm-thought .thought-header:hover {
                    opacity: 0.8;
                }
                
                .stream-line.llm-thought .thought-content {
                    color: #c4b5fd;
                    font-family: 'Monaco', 'Courier New', monospace;
                    font-size: 11px;
                    line-height: 1.5;
                    padding-left: 20px;
                    white-space: pre-wrap;
                    word-wrap: break-word;
                    margin-top: 6px;
                }
                
                .stream-line.llm-thought .thought-content.collapsed {
                    display: none;
                }
                
                .stream-line .timestamp {
                    color: #64748b;
                    font-size: 10px;
                    margin-right: 8px;
                }
                
                .collapse-icon {
                    transition: transform 0.2s;
                    display: inline-block;
                    font-size: 10px;
                }
                
                .collapse-icon.collapsed {
                    transform: rotate(-90deg);
                }
            `;
            document.head.appendChild(style);
        }
        
        // Insert at top of focus tab
        focusTab.insertBefore(statusContainer, focusTab.firstChild);
        
        // Restore state from memory
        this._restoreFocusStatusState();
        
        // Replay any buffered thought chunks
        this._replayBufferedThoughts();
        
        console.log('[ProactiveFocusUI] Status panel initialized');
    };
    VeraChat.prototype._replayBufferedThoughts = function() {
        const state = this._focusStatusState;
        
        if (state.pendingThoughtChunks.length === 0) return;
        
        console.log(`[ProactiveFocusUI] Replaying ${state.pendingThoughtChunks.length} buffered thought chunks`);
        
        // Process all buffered chunks
        state.pendingThoughtChunks.forEach(event => {
            switch (event.type) {
                case 'start':
                    this.startLLMThought(event.timestamp);
                    break;
                case 'chunk':
                    this.appendLLMThought(event.chunk);
                    break;
                case 'end':
                    this.completeLLMThought();
                    break;
            }
        });
        
        // Clear buffer
        state.pendingThoughtChunks = [];
    };
    VeraChat.prototype._restoreFocusStatusState = function() {
        const state = this._focusStatusState;
        
        // Restore stage info
        if (state.currentStage) {
            this.updateStageStatus({
                stage: state.currentStage,
                activity: state.stageActivity,
                progress: state.stageProgress,
                total: state.stageTotal
            });
        }
        
        // Restore console lines
        const output = document.getElementById('streamConsoleOutput');
        if (output && state.consoleLines.length > 0) {
            output.innerHTML = '';
            state.consoleLines.forEach(line => {
                output.appendChild(line.cloneNode(true));
            });
        }
        
        // Restore console visibility
        const console = document.getElementById('streamConsole');
        const icon = document.getElementById('consoleToggleIcon');
        if (console && state.consoleVisible) {
            console.style.display = 'block';
            if (icon) icon.textContent = '📖';
            // Auto-scroll to bottom
            setTimeout(() => {
                console.scrollTop = console.scrollHeight;
            }, 100);
        }
    };
    VeraChat.prototype.updateStageStatus = function(data) {
        const panel = document.getElementById('currentStagePanel');
        const stageName = document.getElementById('stageName');
        const stageActivity = document.getElementById('stageActivity');
        const progressBar = document.getElementById('stageProgressBar');
        const progressFill = document.getElementById('stageProgressFill');
        const progressText = document.getElementById('stageProgressText');
        
        // Save state to memory
        this._focusStatusState.currentStage = data.stage;
        this._focusStatusState.stageActivity = data.activity || 'Processing...';
        this._focusStatusState.stageProgress = data.progress || 0;
        this._focusStatusState.stageTotal = data.total || 0;
        
        if (!panel || !stageName || !stageActivity) return;
        
        // Show panel
        panel.style.display = 'block';
        
        // Update stage name
        const stageIcons = {
            'Ideas Generation': '💡',
            'Next Steps': '→',
            'Action Planning': '⚡',
            'Action Execution': '▶️',
            'State Review': '📊',
            'Saving': '💾'
        };
        
        const icon = stageIcons[data.stage] || '🔄';
        stageName.textContent = `${icon} ${data.stage}`;
        
        // Update activity
        stageActivity.textContent = data.activity || 'Processing...';
        
        // Update progress bar
        if (data.total && data.total > 0) {
            progressBar.style.display = 'block';
            progressText.style.display = 'block';
            
            const percentage = Math.round((data.progress / data.total) * 100);
            progressFill.style.width = `${percentage}%`;
            progressText.textContent = `${data.progress}/${data.total} steps (${percentage}%)`;
        } else {
            progressBar.style.display = 'none';
            progressText.style.display = 'none';
        }
    };

    VeraChat.prototype.updateStageProgress = function(data) {
        const progressFill = document.getElementById('stageProgressFill');
        const progressText = document.getElementById('stageProgressText');
        
        if (!progressFill || !progressText) return;
        
        const percentage = Math.round(data.percentage || 0);
        progressFill.style.width = `${percentage}%`;
        progressText.textContent = `${data.progress}/${data.total} steps (${percentage}%)`;
    };

    
    VeraChat.prototype.clearStage = function() {
        // Clear memory state
        this._focusStatusState.currentStage = null;
        this._focusStatusState.stageActivity = null;
        this._focusStatusState.stageProgress = 0;
        this._focusStatusState.stageTotal = 0;
        
        const panel = document.getElementById('currentStagePanel');
        if (panel) {
            panel.style.display = 'none';
        }
    };
    
    VeraChat.prototype.addStreamOutput = function(text, category = 'info') {
        const line = document.createElement('div');
        line.className = `stream-line ${category}`;
        
        const timestamp = new Date().toLocaleTimeString('en-US', { 
            hour12: false, 
            hour: '2-digit', 
            minute: '2-digit', 
            second: '2-digit' 
        });
        
        line.innerHTML = `
            <span class="timestamp">[${timestamp}]</span>
            <span class="text">${this.escapeHtml(text)}</span>
        `;
        
        // Save to memory (keep last 200 lines)
        this._focusStatusState.consoleLines.push(line.cloneNode(true));
        if (this._focusStatusState.consoleLines.length > 200) {
            this._focusStatusState.consoleLines.shift();
        }
        
        // Add to DOM if console exists
        const console = document.getElementById('streamConsoleOutput');
        if (console) {
            console.appendChild(line);
            
            // Auto-scroll to bottom
            const consoleContainer = document.getElementById('streamConsole');
            if (consoleContainer && consoleContainer.style.display !== 'none') {
                consoleContainer.scrollTop = consoleContainer.scrollHeight;
            }
            
            // Limit DOM to last 200 lines
            while (console.children.length > 200) {
                console.removeChild(console.firstChild);
            }
        }
    };
    VeraChat.prototype.toggleStreamConsole = function() {
        const console = document.getElementById('streamConsole');
        const icon = document.getElementById('consoleToggleIcon');
        
        if (!console) return;
        
        if (console.style.display === 'none') {
            console.style.display = 'block';
            if (icon) icon.textContent = '📖';
            this._focusStatusState.consoleVisible = true;
            
            // Auto-scroll to bottom
            setTimeout(() => {
                console.scrollTop = console.scrollHeight;
            }, 100);
        } else {
            console.style.display = 'none';
            if (icon) icon.textContent = '📜';
            this._focusStatusState.consoleVisible = false;
        }
    };

    VeraChat.prototype.clearStreamConsole = function() {
        // Clear memory state
        this._focusStatusState.consoleLines = [];
        
        // Clear DOM
        const output = document.getElementById('streamConsoleOutput');
        if (output) {
            output.innerHTML = '';
        }
    };
    
    // ============================================================
    // ENHANCED WEBSOCKET HANDLER
    // ============================================================
    
    const originalHandleFocusEvent = VeraChat.prototype.handleFocusEvent;
    
    VeraChat.prototype.handleFocusEvent = function(data) {
        // Call original handler
        if (originalHandleFocusEvent) {
            originalHandleFocusEvent.call(this, data);
        }
        
        // Handle new event types
        switch (data.type) {
            case 'stage_update':
                this.updateStageStatus(data.data);
                break;
                
            case 'stage_progress':
                this.updateStageProgress(data.data);
                break;
                
            case 'stage_cleared':
                this.clearStage();
                break;
                
            case 'stream_output':
                this.addStreamOutput(data.data.text, data.data.category);
                
                // Auto-open console on first output if not already open
                const console = document.getElementById('streamConsole');
                if (console && console.style.display === 'none' && !this._consoleAutoOpened) {
                    this.toggleStreamConsole();
                    this._consoleAutoOpened = true;
                }
                break;
                
            case 'workflow_started':
                this.addStreamOutput('🚀 Workflow started', 'success');
                this._consoleAutoOpened = false;
                break;
                
            case 'workflow_iteration_complete':
                this.addStreamOutput(`✅ Iteration ${data.data.iteration} complete`, 'success');
                break;
                
            case 'workflow_completed':
                this.addStreamOutput(`🏁 Workflow completed - ${data.data.total_iterations} iterations`, 'success');
                this.clearStage();
                break;
                
            case 'workflow_error':
                this.addStreamOutput(`❌ Workflow error: ${data.data.error}`, 'error');
                break;
        }
    };
    
    // ============================================================
    // AUTO-INITIALIZE ON FOCUS TAB SWITCH
    // ============================================================
    
    const originalUpdateFocusUI = VeraChat.prototype.updateFocusUI;
    
    VeraChat.prototype.updateFocusUI = function(preserveScrollPos = null) {
        // Call original to render content
        if (originalUpdateFocusUI) {
            originalUpdateFocusUI.call(this, preserveScrollPos);
        }
        
        // THEN initialize status UI (after content is rendered)
        // Use setTimeout to ensure DOM has updated
        setTimeout(() => {
            this.initProactiveFocusStatusUI();
        }, 0);
    };
    
    // ============================================================
    // WORKFLOW CONTROL ENHANCEMENTS
    // ============================================================
    
    // Also initialize when switching to focus tab manually
    // This catches cases where updateFocusUI isn't called
    if (typeof MutationObserver !== 'undefined') {
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
                    const target = mutation.target;
                    if (target.id === 'tab-focus' && !target.classList.contains('hidden')) {
                        // Focus tab is now visible
                        if (window.app && typeof window.app.initProactiveFocusStatusUI === 'function') {
                            setTimeout(() => {
                                window.app.initProactiveFocusStatusUI();
                            }, 50);
                        }
                    }
                }
            });
        });
        
        // Observe the focus tab for visibility changes
        const focusTab = document.getElementById('tab-focus');
        if (focusTab) {
            observer.observe(focusTab, {
                attributes: true,
                attributeFilter: ['class', 'style']
            });
        }
    }
    
    VeraChat.prototype.stopWorkflow = async function() {
        if (!this.sessionId) return;
        
        if (!confirm('Stop the current workflow?')) return;
        
        try {
            await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/workflow/stop`, {
                method: 'POST'
            });
            
            this.addSystemMessage('⏹️ Workflow stop requested');
            this.addStreamOutput('⏹️ Workflow stop requested', 'warning');
            
        } catch (error) {
            console.error('Failed to stop workflow:', error);
            this.addSystemMessage('Error stopping workflow');
        }
    };
    
    // Add stop button to focus UI
    VeraChat.prototype.renderEnhancedFocusControls = function() {
        let html = `
            <div style="display: flex; gap: 8px; flex-wrap: wrap;">
        `;
        
        if (this.currentFocus) {
            html += `
                <button class="panel-btn" onclick="app.${this.focusRunning ? 'stopProactiveThinking' : 'startProactiveThinking'}()" style="padding: 6px 12px;">
                    ${this.focusRunning ? '⏸️ Stop' : '▶️ Start'}
                </button>
                <button class="panel-btn" onclick="app.triggerProactiveThought()" style="padding: 6px 12px;">
                    💭 Think Now
                </button>
            `;
            
            // Show stop workflow button if workflow is active
            if (this.focusRunning) {
                html += `
                    <button class="panel-btn" onclick="app.stopWorkflow()" style="padding: 6px 12px; background: #ef4444;">
                        ⏹️ Stop Workflow
                    </button>
                `;
            }
        }
        
        html += `
                <button class="panel-btn" onclick="app.showBackgroundControlPanel()" style="padding: 6px 12px;">
                    ⚙️ Background
                </button>
                <button class="panel-btn" onclick="app.showEntityExplorer()" style="padding: 6px 12px;">
                    🔗 Entities
                </button>
                <button class="panel-btn" onclick="app.showToolUsageHistory()" style="padding: 6px 12px;">
                    🔧 Tool History
                </button>
                <button class="panel-btn" onclick="app.showFocusBoardMenu()" style="padding: 6px 12px;">
                    📂 Load
                </button>
                <button class="panel-btn" onclick="app.loadFocusStatus()" style="padding: 6px 12px;">
                    🔄 Refresh
                </button>
                <button class="panel-btn" onclick="app.saveFocusBoard()" style="padding: 6px 12px;">
                    💾 Save
                </button>
            </div>
        `;
        
        return html;
    };

    VeraChat.prototype.startLLMThought = function(timestamp) {
        const state = this._focusStatusState;
        
        // Check if console exists
        const console = document.getElementById('streamConsoleOutput');
        if (!console) {
            // Buffer this event
            console.log('[ProactiveFocusUI] Console not ready, buffering thought start');
            state.pendingThoughtChunks.push({ type: 'start', timestamp: timestamp || Date.now() });
            state.inLLMThought = true;
            state.thoughtStartTime = timestamp || Date.now();
            return;
        }
        
        state.inLLMThought = true;
        state.currentThoughtBuffer = "";
        state.thoughtStartTime = timestamp || Date.now();
        
        const thoughtContainer = document.createElement('div');
        thoughtContainer.id = 'currentLLMThought';
        thoughtContainer.className = 'stream-line llm-thought';
        
        const timeStr = new Date(state.thoughtStartTime).toLocaleTimeString('en-US', { 
            hour12: false, 
            hour: '2-digit', 
            minute: '2-digit', 
            second: '2-digit' 
        });
        
        thoughtContainer.innerHTML = `
            <div class="thought-header">
                <span class="timestamp">[${timeStr}]</span>
                <span style="color: #a78bfa; font-weight: 600; font-size: 11px;">
                    🧠 LLM REASONING
                </span>
                <div class="thinking-spinner" style="
                    width: 12px;
                    height: 12px;
                    border: 2px solid #8b5cf6;
                    border-top: 2px solid transparent;
                    border-radius: 50%;
                    animation: spin 1s linear infinite;
                "></div>
            </div>
            <div class="thought-content"></div>
        `;
        
        console.appendChild(thoughtContainer);
        
        // Auto-scroll
        const consoleContainer = document.getElementById('streamConsole');
        if (consoleContainer && consoleContainer.style.display !== 'none') {
            consoleContainer.scrollTop = consoleContainer.scrollHeight;
        }
    };
    
    // NEW: Append to current LLM thought
    VeraChat.prototype.appendLLMThought = function(chunk) {
        const state = this._focusStatusState;
        
        // Check if console exists
        const console = document.getElementById('streamConsoleOutput');
        if (!console) {
            // Buffer this chunk
            state.pendingThoughtChunks.push({ type: 'chunk', chunk });
            state.currentThoughtBuffer += chunk;
            return;
        }
        
        if (!state.inLLMThought) {
            this.startLLMThought();
        }
        
        state.currentThoughtBuffer += chunk;
        
        // Update DOM
        const thoughtContainer = document.getElementById('currentLLMThought');
        if (thoughtContainer) {
            const contentDiv = thoughtContainer.querySelector('.thought-content');
            if (contentDiv) {
                contentDiv.textContent = state.currentThoughtBuffer;
            }
            
            // Auto-scroll
            const consoleContainer = document.getElementById('streamConsole');
            if (consoleContainer && consoleContainer.style.display !== 'none') {
                consoleContainer.scrollTop = consoleContainer.scrollHeight;
            }
        }
    };
    
    // NEW: Complete LLM thought - make it collapsible
    VeraChat.prototype.completeLLMThought = function() {
        const state = this._focusStatusState;
        
        // Check if console exists
        const console = document.getElementById('streamConsoleOutput');
        if (!console) {
            // Buffer this event
            console.log('[ProactiveFocusUI] Console not ready, buffering thought end');
            state.pendingThoughtChunks.push({ type: 'end' });
            state.inLLMThought = false;
            return;
        }
        
        state.inLLMThought = false;
        
        const thoughtContainer = document.getElementById('currentLLMThought');
        if (thoughtContainer) {
            // Remove spinner
            const spinner = thoughtContainer.querySelector('.thinking-spinner');
            if (spinner) {
                spinner.remove();
            }
            
            // Add completion marker and collapse icon
            const header = thoughtContainer.querySelector('.thought-header');
            if (header) {
                // Add collapse icon at the start
                const collapseIcon = document.createElement('span');
                collapseIcon.className = 'collapse-icon';
                collapseIcon.textContent = '▼';
                collapseIcon.style.cssText = 'color: #8b5cf6; margin-right: 4px;';
                header.insertBefore(collapseIcon, header.firstChild);
                
                // Add completion marker
                const complete = document.createElement('span');
                complete.style.cssText = 'color: #10b981; font-size: 11px; margin-left: auto;';
                complete.textContent = '✓ Complete';
                header.appendChild(complete);
                
                // Make header clickable to toggle collapse
                const contentDiv = thoughtContainer.querySelector('.thought-content');
                const thoughtId = `thought_${Date.now()}`;
                thoughtContainer.setAttribute('data-thought-id', thoughtId);
                
                header.onclick = () => {
                    const isCollapsed = contentDiv.classList.toggle('collapsed');
                    collapseIcon.classList.toggle('collapsed', isCollapsed);
                };
            }
            
            // Mark as completed
            thoughtContainer.classList.add('completed');
            
            // Remove ID so it becomes permanent
            thoughtContainer.removeAttribute('id');
            
            // Save to memory
            state.consoleLines.push(thoughtContainer.cloneNode(true));
            if (state.consoleLines.length > 200) {
                state.consoleLines.shift();
            }
        }
        
        state.currentThoughtBuffer = "";
        state.thoughtStartTime = null;
    };
    
     // ============================================================
    // ENHANCED WEBSOCKET HANDLER
    // ============================================================
    
    // const originalHandleFocusEvent = VeraChat.prototype.handleFocusEvent;
    
    VeraChat.prototype.handleFocusEvent = function(data) {
        // Call original handler
        if (originalHandleFocusEvent) {
            originalHandleFocusEvent.call(this, data);
        }
        
        // Handle new event types
        switch (data.type) {
            case 'stage_update':
                this.updateStageStatus(data.data);
                break;
                
            case 'stage_progress':
                this.updateStageProgress(data.data);
                break;
                
            case 'stage_cleared':
                this.clearStage();
                break;
                
            case 'stream_output':
                this.addStreamOutput(data.data.text, data.data.category);
                
                // Auto-open console on first output if not already open
                const console = document.getElementById('streamConsole');
                if (console && console.style.display === 'none' && !this._consoleAutoOpened) {
                    this.toggleStreamConsole();
                    this._consoleAutoOpened = true;
                }
                break;
            
            // LLM thought events
            case 'llm_thought_start':
                this.startLLMThought(data.data?.timestamp);
                break;
            
            case 'llm_thought_chunk':
                this.appendLLMThought(data.data.chunk);
                break;
            
            case 'llm_thought_end':
                this.completeLLMThought();
                break;
            
            case 'response_chunk':
                // Regular response content - for now we just ignore it
                // since it's handled by the workflow output
                break;
                
            case 'workflow_started':
                this.addStreamOutput('🚀 Workflow started', 'success');
                this._consoleAutoOpened = false;
                break;
                
            case 'workflow_iteration_complete':
                this.addStreamOutput(`✅ Iteration ${data.data.iteration} complete`, 'success');
                break;
                
            case 'workflow_completed':
                this.addStreamOutput(`🏁 Workflow completed - ${data.data.total_iterations} iterations`, 'success');
                this.clearStage();
                break;
                
            case 'workflow_error':
                this.addStreamOutput(`❌ Workflow error: ${data.data.error}`, 'error');
                break;
        }
    };
    const style = document.createElement('style');
    style.textContent = `
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .stream-line {
            margin: 2px 0;
            padding: 4px 8px;
            border-radius: 4px;
            line-height: 1.4;
            word-wrap: break-word;
        }
        
        .stream-line.info {
            color: #cbd5e1;
            background: rgba(148, 163, 184, 0.05);
        }
        
        .stream-line.success {
            color: #34d399;
            background: rgba(16, 185, 129, 0.1);
            font-weight: 600;
        }
        
        .stream-line.warning {
            color: #fbbf24;
            background: rgba(245, 158, 11, 0.1);
        }
        
        .stream-line.error {
            color: #f87171;
            background: rgba(239, 68, 68, 0.1);
            font-weight: 600;
        }
        
        /* NEW: LLM Thought styling */
        .stream-line.llm-thought {
            background: rgba(138, 92, 246, 0.15);
            border-left: 3px solid #8b5cf6;
            padding: 8px 12px;
            margin: 4px 0;
        }
        
        .stream-line.llm-thought .thought-content {
            color: #c4b5fd;
            font-family: 'Monaco', 'Courier New', monospace;
            font-size: 11px;
            line-height: 1.5;
            padding-left: 20px;
            white-space: pre-wrap;
            word-wrap: break-word;
        }
        
        .stream-line .timestamp {
            color: #64748b;
            font-size: 10px;
            margin-right: 8px;
        }
    `;
    console.log('[ProactiveFocusUI] Enhanced UI components loaded');
})();