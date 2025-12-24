// =====================================================================
// Toolchain Flowchart - FIXED STEP INDEXING + DEBUG LOGGING
// Handles 1-based API step numbers vs 0-based array indexing
// =====================================================================

(() => {
    console.log('🔧 Loading Toolchain Flowchart (v2 - Fixed Indexing)...');

    // =====================================================================
    // Wrap handleToolchainEvent
    // =====================================================================
    
    if (!VeraChat.prototype._originalHandleToolchainEvent) {
        console.log('📝 Wrapping handleToolchainEvent...');
        VeraChat.prototype._originalHandleToolchainEvent = VeraChat.prototype.handleToolchainEvent;
    }
    
    VeraChat.prototype.handleToolchainEvent = function(data) {
        console.log('🔔 Toolchain event:', data.type, data);
        
        // Call original handler FIRST
        if (this._originalHandleToolchainEvent) {
            this._originalHandleToolchainEvent.call(this, data);
        }
        
        // Then update flowcharts
        this.updateFlowchart(data);
    };
    
    // =====================================================================
    // Update Flowchart Based on WebSocket Events
    // =====================================================================
    
    VeraChat.prototype.updateFlowchart = function(data) {
        console.log('🎨 updateFlowchart called, type:', data.type);
        
        if (!this.currentExecution) {
            console.warn('⚠️ No currentExecution, skipping update');
            return;
        }
        
        const execId = this.currentExecution.execution_id;
        console.log('📍 Execution ID:', execId);
        
        switch (data.type) {
            case 'plan':
                console.log('📋 Plan received!', data.data.plan);
                this.injectFlowchart(execId, data.data.plan);
                break;
                
            case 'step_started':
                // CRITICAL FIX: API uses 1-based step numbers (1, 2, 3...)
                // But flowchart uses 0-based indexing (0, 1, 2...)
                const stepNum = data.data.step_number;
                const arrayIndex = stepNum - 1; // Convert to 0-based
                
                console.log(`▶️ Step started - API step: ${stepNum}, Array index: ${arrayIndex}`);
                this.updateStepStatus(execId, arrayIndex, 'running');
                break;
                
            case 'step_output':
                const outputStepNum = data.data.step_number;
                const outputIndex = outputStepNum - 1; // Convert to 0-based
                
                console.log(`📝 Step output - API step: ${outputStepNum}, Array index: ${outputIndex}`);
                this.appendStepOutput(execId, outputIndex, data.data.chunk);
                break;
                
            case 'step_completed':
                const completedStepNum = data.data.step_number;
                const completedIndex = completedStepNum - 1; // Convert to 0-based
                
                console.log(`✅ Step completed - API step: ${completedStepNum}, Array index: ${completedIndex}`);
                this.updateStepStatus(execId, completedIndex, 'completed');
                break;
                
            case 'step_failed':
                const failedStepNum = data.data.step_number;
                const failedIndex = failedStepNum - 1; // Convert to 0-based
                
                console.log(`❌ Step failed - API step: ${failedStepNum}, Array index: ${failedIndex}`);
                this.updateStepStatus(execId, failedIndex, 'failed');
                
                if (data.data.error) {
                    this.setStepError(execId, failedIndex, data.data.error);
                }
                break;
                
            case 'execution_completed':
                console.log('✅ Execution completed');
                this.updateGlobalStatus(execId, 'completed');
                break;
                
            case 'execution_failed':
                console.log('❌ Execution failed');
                this.updateGlobalStatus(execId, 'failed');
                break;
        }
    };
    
    // =====================================================================
    // Inject Flowchart
    // =====================================================================
    
    VeraChat.prototype.injectFlowchart = function(execId, plan) {
        if (!plan || plan.length === 0) {
            console.warn('⚠️ Empty plan');
            return;
        }
        
        console.log('🎨 Building flowchart HTML for', plan.length, 'steps');
        
        const html = this.buildFlowchartHTML(execId, plan);
        
        // Find the last assistant message
        const messages = document.querySelectorAll('.message.assistant');
        console.log('📨 Found', messages.length, 'assistant messages');
        
        if (messages.length === 0) {
            console.warn('⚠️ No assistant messages found');
            return;
        }
        
        const lastMessage = messages[messages.length - 1];
        
        // Try different selectors for content div
        let contentDiv = lastMessage.querySelector('.message-content');
        if (!contentDiv) {
            contentDiv = lastMessage.querySelector('.content');
        }
        if (!contentDiv) {
            contentDiv = lastMessage.querySelector('[class*="content"]');
        }
        
        if (!contentDiv) {
            console.warn('⚠️ Could not find content div');
            console.log('Available elements:', lastMessage.innerHTML.substring(0, 200));
            return;
        }
        
        console.log('📦 Content div found:', contentDiv.className);
        
        // Check if already exists
        if (document.getElementById(`flowchart-${execId}`)) {
            console.log('ℹ️ Flowchart already exists, skipping');
            return;
        }
        
        // CRITICAL: Use insertAdjacentHTML to render HTML properly
        contentDiv.insertAdjacentHTML('beforeend', '\n\n' + html);
        
        console.log('✅ Flowchart injected!');
        
        // Verify it's in DOM
        const injected = document.getElementById(`flowchart-${execId}`);
        if (injected) {
            console.log('✅ Verified flowchart in DOM');
        } else {
            console.error('❌ Flowchart not found in DOM after injection!');
        }
    };
    
    // =====================================================================
    // Build Flowchart HTML
    // =====================================================================
    
    VeraChat.prototype.buildFlowchartHTML = function(execId, plan) {
        const stepsHtml = plan.map((step, index) => {
            const toolName = this.escapeHtml(step.tool || 'unknown');
            const inputPreview = this.escapeHtml(this.truncate(step.input, 50));
            
            // Use 0-based index for DOM IDs
            return `
                <div class="flow-row">
                    <div class="flow-node flow-step" 
                         id="step-node-${execId}-${index}"
                         data-step="${index}"
                         data-status="pending">
                        <div class="step-number">Step ${index}</div>
                        <div class="step-tool">${toolName}</div>
                        <div class="step-input">${inputPreview}</div>
                        <div class="step-status" id="status-${execId}-${index}">
                            <span class="status-icon">⏸️</span>
                            <span class="status-text">Pending</span>
                        </div>
                    </div>
                </div>
                ${index < plan.length - 1 ? '<div class="flow-row"><div class="flow-arrow">↓</div></div>' : ''}
            `;
        }).join('');
        
        const detailsHtml = plan.map((step, index) => {
            const toolName = this.escapeHtml(step.tool || 'unknown');
            const input = this.escapeHtml(step.input);
            
            return `
                <div class="step-detail" id="detail-${execId}-${index}">
                    <div class="detail-header">
                        <span class="detail-number">Step ${index}</span>
                        <span class="detail-tool">${toolName}</span>
                    </div>
                    <div class="detail-input">
                        <strong>Input:</strong>
                        <pre>${input}</pre>
                    </div>
                    <div class="detail-output" id="output-${execId}-${index}" style="display: none;">
                        <strong>Output:</strong>
                        <pre class="output-pre"></pre>
                    </div>
                    <div class="detail-error" id="error-${execId}-${index}" style="display: none;">
                        <strong>Error:</strong>
                        <pre class="error-pre"></pre>
                    </div>
                </div>
            `;
        }).join('');
        
        return `
            <div class="toolchain-flowchart-widget" id="flowchart-${execId}">
                <div class="flowchart-header">
                    <span class="flowchart-icon">🔧</span>
                    <span class="flowchart-title">Toolchain Execution</span>
                    <span class="flowchart-count">${plan.length} steps</span>
                    <span class="flowchart-status" id="global-status-${execId}">EXECUTING</span>
                </div>
                <div class="flowchart-body">
                    <div class="flow-nodes">
                        <div class="flow-row"><div class="flow-node flow-start">Start</div></div>
                        <div class="flow-row"><div class="flow-arrow">↓</div></div>
                        ${stepsHtml}
                        <div class="flow-row"><div class="flow-arrow">↓</div></div>
                        <div class="flow-row"><div class="flow-node flow-end">Complete</div></div>
                    </div>
                </div>
                <div class="flowchart-details">
                    <button class="flowchart-toggle-btn" onclick="this.parentElement.classList.toggle('expanded')">
                        <span class="toggle-icon">▼</span> Step Details
                    </button>
                    <div class="flowchart-details-content">
                        <div class="step-details-list">
                            ${detailsHtml}
                        </div>
                    </div>
                </div>
            </div>
        `;
    };
    
    // =====================================================================
    // Update Functions - DOM Manipulation
    // =====================================================================
    
    VeraChat.prototype.updateStepStatus = function(execId, stepIndex, status) {
        const elementId = `step-node-${execId}-${stepIndex}`;
        console.log(`🔍 Looking for element: ${elementId}`);
        
        const stepNode = document.getElementById(elementId);
        if (!stepNode) {
            console.error(`❌ Step node not found: ${elementId}`);
            console.log('Available flowcharts:', 
                Array.from(document.querySelectorAll('.toolchain-flowchart-widget')).map(fc => fc.id));
            console.log('Available step nodes:', 
                Array.from(document.querySelectorAll('.flow-step')).map(s => s.id));
            return;
        }
        
        console.log(`✅ Found step node, updating to: ${status}`);
        
        stepNode.dataset.status = status;
        
        const statusId = `status-${execId}-${stepIndex}`;
        const statusEl = document.getElementById(statusId);
        
        if (statusEl) {
            const statusConfig = {
                pending: { icon: '⏸️', text: 'Pending' },
                running: { icon: '⏳', text: 'Running' },
                completed: { icon: '✅', text: 'Done' },
                failed: { icon: '❌', text: 'Failed' }
            };
            
            const config = statusConfig[status] || statusConfig.pending;
            statusEl.innerHTML = `
                <span class="status-icon">${config.icon}</span>
                <span class="status-text">${config.text}</span>
            `;
            console.log(`✅ Status updated: ${config.text}`);
        } else {
            console.error(`❌ Status element not found: ${statusId}`);
        }
        
        // Show output section when running or completed
        if (status === 'running' || status === 'completed') {
            const outputSection = document.getElementById(`output-${execId}-${stepIndex}`);
            if (outputSection) {
                outputSection.style.display = 'block';
                console.log('✅ Output section visible');
            }
        }
    };
    
    VeraChat.prototype.appendStepOutput = function(execId, stepIndex, chunk) {
        const outputPre = document.querySelector(`#output-${execId}-${stepIndex} .output-pre`);
        if (outputPre) {
            outputPre.textContent += chunk;
            outputPre.scrollTop = outputPre.scrollHeight;
            console.log(`📝 Appended ${chunk.length} chars to step ${stepIndex} output`);
        } else {
            console.warn(`⚠️ Output element not found for step ${stepIndex}`);
        }
    };
    
    VeraChat.prototype.setStepError = function(execId, stepIndex, error) {
        const errorSection = document.getElementById(`error-${execId}-${stepIndex}`);
        if (errorSection) {
            errorSection.style.display = 'block';
            
            const errorPre = errorSection.querySelector('.error-pre');
            if (errorPre) {
                errorPre.textContent = error;
                console.log(`❌ Set error for step ${stepIndex}`);
            }
        }
    };
    
    VeraChat.prototype.updateGlobalStatus = function(execId, status) {
        const statusEl = document.getElementById(`global-status-${execId}`);
        if (statusEl) {
            statusEl.textContent = status.toUpperCase();
            statusEl.className = `flowchart-status status-${status}`;
            console.log(`✅ Global status updated: ${status}`);
        } else {
            console.warn(`⚠️ Global status element not found: global-status-${execId}`);
        }
    };
    
    // =====================================================================
    // Helper Functions
    // =====================================================================
    
    VeraChat.prototype.truncate = function(text, maxLen) {
        if (!text) return '';
        text = String(text);
        if (text.length <= maxLen) return text;
        return text.substring(0, maxLen) + '...';
    };
    
    // =====================================================================
    // Styles (unchanged)
    // =====================================================================
    
    const styles = `
    .toolchain-flowchart-widget {
        margin: 16px 0;
        background: var(--panel-bg, #1e293b);
        border: 2px solid var(--accent, #3b82f6);
        border-radius: 8px;
        overflow: hidden;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }

    .flowchart-header {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 12px 16px;
        background: linear-gradient(135deg, var(--panel-bg, #3b82f6), var(--bg));
        color: white;
    }

    .flowchart-icon { font-size: 20px; }
    .flowchart-title { font-size: 15px; font-weight: 600; flex: 1; }
    .flowchart-count { font-size: 12px; padding: 4px 10px; background: rgba(255, 255, 255, 0.2); border-radius: 12px; font-weight: 500; }
    .flowchart-status { font-size: 11px; padding: 4px 10px; border-radius: 12px; font-weight: 600; }
    .status-executing { background: rgba(59, 130, 246, 0.3); animation: pulse 2s infinite; }
    .status-completed { background: rgba(16, 185, 129, 0.3); }
    .status-failed { background: rgba(239, 68, 68, 0.3); }

    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.6; }
    }

    .flowchart-body { padding: 24px 16px; background: var(--bg, #0f172a); }
    .flow-nodes { display: flex; flex-direction: column; align-items: center; gap: 0; }
    .flow-row { display: flex; justify-content: center; width: 100%; }
    .flow-node { padding: 12px 20px; border-radius: 8px; text-align: center; font-size: 14px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3); min-width: 200px; max-width: 600px; transition: all 0.3s; }
    .flow-start, .flow-end { background: linear-gradient(135deg, #10b981, #059669); color: white; padding: 10px 24px; border-radius: 20px; font-weight: 600; min-width: 120px; }
    .flow-step { background: var(--panel-bg, #1e293b); border: 2px solid #64748b; color: var(--text, #e2e8f0); }
    .flow-step[data-status="pending"] { border-color: #64748b; opacity: 0.7; }
    .flow-step[data-status="running"] { border-color: #3b82f6; box-shadow: 0 0 20px rgba(59, 130, 246, 0.5); animation: pulse-border 1.5s infinite; }
    .flow-step[data-status="completed"] { border-color: #10b981; background: linear-gradient(135deg, #1e293b, #064e3b); }
    .flow-step[data-status="failed"] { border-color: #ef4444; background: linear-gradient(135deg, #1e293b, #7f1d1d); }

    @keyframes pulse-border {
        0%, 100% { box-shadow: 0 0 20px rgba(59, 130, 246, 0.5); }
        50% { box-shadow: 0 0 30px rgba(59, 130, 246, 0.8); }
    }

    .step-number { font-size: 10px; text-transform: uppercase; color: var(--accent, #3b82f6); font-weight: 600; margin-bottom: 4px; }
    .step-tool { font-size: 16px; font-weight: 600; margin-bottom: 6px; font-family: monospace; }
    .step-input { font-size: 12px; color: var(--text-muted, #94a3b8); margin-bottom: 8px; }
    .step-status { font-size: 11px; padding: 4px 8px; background: rgba(0, 0, 0, 0.3); border-radius: 4px; display: inline-flex; align-items: center; gap: 4px; }
    .status-icon { font-size: 13px; }
    .status-text { font-weight: 500; }
    .flow-arrow { color: var(--accent, #3b82f6); font-size: 24px; line-height: 1; padding: 4px 0; font-weight: bold; }

    .flowchart-details { border-top: 1px solid var(--border, #334155); background: var(--panel-bg, #1e293b); }
    .flowchart-toggle-btn { width: 100%; padding: 12px 16px; background: transparent; border: none; color: var(--text, #e2e8f0); cursor: pointer; font-size: 13px; font-weight: 500; display: flex; align-items: center; gap: 8px; transition: background 0.2s; text-align: left; }
    .flowchart-toggle-btn:hover { background: var(--bg, #0f172a); }
    .toggle-icon { transition: transform 0.2s; }
    .flowchart-details.expanded .toggle-icon { transform: rotate(180deg); }
    .flowchart-details-content { max-height: 0; overflow: hidden; transition: max-height 0.3s ease; }
    .flowchart-details.expanded .flowchart-details-content { max-height: 2000px; padding: 16px; }

    .step-details-list { display: flex; flex-direction: column; gap: 12px; }
    .step-detail { padding: 12px; background: var(--bg, #0f172a); border: 1px solid var(--border, #334155); border-radius: 6px; }
    .detail-header { display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }
    .detail-number { font-size: 11px; font-weight: 600; padding: 3px 8px; background: var(--accent, #3b82f6); color: white; border-radius: 4px; text-transform: uppercase; }
    .detail-tool { font-size: 14px; font-weight: 600; font-family: monospace; }
    .detail-input strong, .detail-output strong, .detail-error strong { color: var(--text, #e2e8f0); font-size: 12px; text-transform: uppercase; display: block; margin-bottom: 6px; }
    .detail-input pre, .detail-output pre, .detail-error pre { margin: 0; padding: 8px 12px; background: var(--panel-bg, #1e293b); border: 1px solid var(--border, #334155); border-radius: 4px; font-family: monospace; font-size: 12px; white-space: pre-wrap; word-wrap: break-word; max-height: 200px; overflow-y: auto; }
    .detail-output { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border, #334155); }
    .output-pre { color: #10b981; border-left: 3px solid #10b981; }
    .detail-error { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border, #334155); }
    .error-pre { color: #ef4444; border-left: 3px solid #ef4444; background: rgba(239, 68, 68, 0.1); }

    @media (max-width: 768px) {
        .flow-node { min-width: 150px; max-width: 90%; }
    }
    `;

    if (!document.getElementById('toolchain-flowchart-styles')) {
        const style = document.createElement('style');
        style.id = 'toolchain-flowchart-styles';
        style.textContent = styles;
        document.head.appendChild(style);
        console.log('✅ Styles injected');
    }

    console.log('✅ Toolchain Flowchart loaded (v2 - Fixed Indexing)');
    console.log('📡 Listening for WebSocket events...');
    console.log('ℹ️ Note: API uses 1-based steps, flowchart uses 0-based arrays');
})();