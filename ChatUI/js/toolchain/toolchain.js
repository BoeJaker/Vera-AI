
(() => {
    VeraChat.prototype.connectToolchainWebSocket = function() {
        if (!this.sessionId) return;
        
        const wsUrl = `ws://llm.int:8888/ws/toolchain/${this.sessionId}`;
        this.toolchainWebSocket = new WebSocket(wsUrl);
        
        this.toolchainWebSocket.onopen = () => {
            console.log('Toolchain WebSocket connected');
        };
        
        this.toolchainWebSocket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleToolchainEvent(data);
            } catch (error) {
                console.error('Toolchain WebSocket message parse error:', error);
            }
        };
        
        this.toolchainWebSocket.onerror = (error) => {
            console.error('Toolchain WebSocket error:', error);
        };
        
        this.toolchainWebSocket.onclose = () => {
            console.log('Toolchain WebSocket disconnected');
            if (this.sessionId) {
                setTimeout(() => this.connectToolchainWebSocket(), 3000);
            }
        };
    };

    VeraChat.prototype.handleToolchainEvent = function(data) {
        console.log('Toolchain event:', data.type, data);
        
        switch (data.type) {
            case 'execution_started':
                this.currentExecution = {
                    execution_id: data.data.execution_id,
                    query: data.data.query,
                    status: 'planning',
                    steps: [],
                    plan: [],
                    startTime: new Date(data.timestamp),
                    start_time: data.timestamp,
                    totalSteps: 0,
                    total_steps: 0,
                    completedSteps: 0,
                    completed_steps: 0
                };
                
                // Auto-switch to executions view when execution starts
                if (this.activeTab === 'toolchain' && this.toolchainView === 'tools') {
                    this.toolchainView = 'executions';
                }
                this.updateToolchainUI();
                break;
                
            case 'status':
                if (this.currentExecution) {
                    this.currentExecution.status = data.data.status;
                    this.updateToolchainUI();
                }
                break;
                
            case 'plan':
                if (this.currentExecution) {
                    this.currentExecution.plan = data.data.plan;
                    this.currentExecution.totalSteps = data.data.total_steps;
                    this.currentExecution.total_steps = data.data.total_steps;
                    this.updateToolchainUI();
                }
                break;
                
            case 'step_started':
                if (this.currentExecution) {
                    const step = {
                        number: data.data.step_number,
                        toolName: data.data.tool_name,
                        input: data.data.tool_input,
                        status: 'running',
                        output: '',
                        startTime: new Date(data.timestamp),
                        start_time: data.timestamp
                    };
                    this.currentExecution.steps.push(step);
                    this.updateToolchainUI();
                }
                break;
                
            case 'step_output':
                if (this.currentExecution) {
                    const step = this.currentExecution.steps.find(s => s.number === data.data.step_number);
                    if (step) {
                        step.output += data.data.chunk;
                        
                        // Try to update DOM directly for better performance
                        const outputElement = document.getElementById(`step-output-${data.data.step_number}`);
                        if (outputElement) {
                            outputElement.textContent = step.output;
                            // Auto-scroll to bottom
                            outputElement.scrollTop = outputElement.scrollHeight;
                        } else {
                            // Fallback to full update if element not found (e.g., first chunk)
                            this.updateToolchainUI();
                        }
                    }
                }
                break;
                
            case 'step_completed':
                if (this.currentExecution) {
                    const step = this.currentExecution.steps.find(s => s.number === data.data.step_number);
                    if (step) {
                        step.status = 'completed';
                        step.endTime = new Date(data.timestamp);
                        step.end_time = data.timestamp;
                        this.currentExecution.completedSteps++;
                        this.currentExecution.completed_steps++;
                        this.updateToolchainUI();
                    }
                }
                break;
                
            case 'step_failed':
                if (this.currentExecution) {
                    const step = this.currentExecution.steps.find(s => s.number === data.data.step_number);
                    if (step) {
                        step.status = 'failed';
                        step.error = data.data.error;
                        step.endTime = new Date(data.timestamp);
                        step.end_time = data.timestamp;
                        this.updateToolchainUI();
                    }
                }
                break;
                
            case 'execution_completed':
                if (this.currentExecution) {
                    this.currentExecution.status = 'completed';
                    this.currentExecution.finalResult = data.data.final_result;
                    this.currentExecution.endTime = new Date(data.timestamp);
                    this.currentExecution.end_time = data.timestamp;
                    
                    // Add to history
                    if (!this.toolchainExecutions) this.toolchainExecutions = [];
                    this.toolchainExecutions.push({...this.currentExecution});
                    
                    this.updateToolchainUI();
                }
                break;
                
            case 'execution_failed':
                if (this.currentExecution) {
                    this.currentExecution.status = 'failed';
                    this.currentExecution.error = data.data.error;
                    this.currentExecution.endTime = new Date(data.timestamp);
                    this.currentExecution.end_time = data.timestamp;
                    
                    // Add to history
                    if (!this.toolchainExecutions) this.toolchainExecutions = [];
                    this.toolchainExecutions.push({...this.currentExecution});
                    
                    this.updateToolchainUI();
                }
                break;
            case 'plan_chunk':
                if (this.currentExecution) {
                    // Initialize plan_text if it doesn't exist
                    if (!this.currentExecution.plan_text) {
                        this.currentExecution.plan_text = '';
                    }
                    this.currentExecution.plan_text += data.data.chunk;
                    
                    // Try to update DOM directly for better performance
                    const planElement = document.getElementById('execution-plan-text');
                    if (planElement) {
                        planElement.textContent = this.currentExecution.plan_text;
                        // Auto-scroll to bottom
                        planElement.scrollTop = planElement.scrollHeight;
                    } else {
                        // Fallback to full update if element not found
                        this.updateToolchainUI();
                    }
                }
                break;
        }
    };

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
                            MCP Servers
                        </button>
                        <button class="panel-btn ${this.toolchainView === 'history' ? 'active' : ''}" 
                                onclick="app.switchToolchainView('history')">
                            History
                        </button>
                        <button class="panel-btn ${this.toolchainView === 'history' ? 'active' : ''}" 
                                onclick="app.switchToolchainView('history')">
                            Workflows
                        </button>
                        <button class="panel-btn ${this.toolchainView === 'history' ? 'active' : ''}" 
                                onclick="app.switchToolchainView('history')">
                            Query
                        </button>
                        <button class="panel-btn ${this.toolchainView === 'history' ? 'active' : ''}" 
                                onclick="app.switchToolchainView('history')">
                            Config
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

    VeraChat.prototype.switchToolchainView = function(view) {
        this.toolchainView = view;
        this.updateToolchainUI();
    };

VeraChat.prototype.updateSingleToolCard = function(toolName) {
    const tool = this.availableTools[toolName];
    if (!tool) return;
    
    const cardElement = document.querySelector(`[data-tool-name="${this.escapeHtml(toolName)}"]`);
    if (!cardElement) return;
    
    const isExecuting = this.executingTools && this.executingTools[toolName];
    const hasResult = this.toolResults && this.toolResults[toolName];
    const isExpanded = this.expandedTools && this.expandedTools[toolName];
    
    const newCardHtml = `
        <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 10px;">
            <div style="flex: 1;">
                <div style="color: #e2e8f0; font-weight: 600; font-size: 14px; margin-bottom: 4px;">
                    ${this.escapeHtml(tool.name)}
                </div>
                <div style="color: #64748b; font-size: 10px; font-family: monospace; margin-bottom: 8px;">
                    ${this.escapeHtml(tool.type)}
                </div>
            </div>
            <button class="panel-btn" 
                    onclick="app.toggleToolExpand('${this.escapeHtml(tool.name)}')"
                    style="padding: 4px 8px; font-size: 11px; min-width: auto;">
                ${isExpanded ? '▼' : '▶'}
            </button>
        </div>
        
        <div style="color: #94a3b8; font-size: 12px; line-height: 1.5; margin-bottom: 12px;">
            ${this.escapeHtml(tool.description)}
        </div>
        
        <div id="tool-expand-${this.escapeHtml(tool.name)}" 
            style="display: ${isExpanded ? 'block' : 'none'};">
            
            <div id="tool-inputs-${this.escapeHtml(tool.name)}" style="margin-bottom: 10px;">
                <div style="color: #94a3b8; font-size: 11px; margin-bottom: 6px;">Loading inputs...</div>
            </div>
            
            <div style="display: flex; gap: 6px; margin-bottom: 10px;">
                <button class="panel-btn" 
                        onclick="app.executeToolFromCard('${this.escapeHtml(tool.name)}')"
                        style="flex: 1; padding: 8px; font-size: 12px;"
                        ${isExecuting ? 'disabled' : ''}>
                    ${isExecuting ? '⏳ Executing...' : '🚀 Execute'}
                </button>
                <button class="panel-btn" 
                        onclick="app.clearToolInput('${this.escapeHtml(tool.name)}')"
                        style="background: #64748b; padding: 8px; font-size: 12px;"
                        ${isExecuting ? 'disabled' : ''}>
                    Clear
                </button>
            </div>
            
            ${hasResult ? `
                <div style="background: #0f172a; border-radius: 6px; padding: 10px; border-left: 3px solid ${this.toolResults[toolName].success ? '#10b981' : '#ef4444'};">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                        <div style="color: ${this.toolResults[toolName].success ? '#10b981' : '#ef4444'}; font-size: 10px; font-weight: 600; text-transform: uppercase;">
                            ${this.toolResults[toolName].success ? '✓ Success' : '✗ Error'}
                        </div>
                        <div style="display: flex; gap: 8px; align-items: center;">
                            <div style="color: #64748b; font-size: 9px;">
                                ${this.toolResults[toolName].duration}ms
                            </div>
                            <button onclick="app.clearToolResult('${this.escapeHtml(tool.name)}')" 
                                    style="background: none; border: none; color: #64748b; cursor: pointer; padding: 2px; font-size: 12px;"
                                    title="Clear result">✕</button>
                        </div>
                    </div>
                    <div style="color: #cbd5e1; font-size: 11px; font-family: monospace; max-height: 150px; overflow-y: auto; white-space: pre-wrap; word-break: break-word; line-height: 1.4;">
                        ${this.escapeHtml(this.toolResults[toolName].output)}
                    </div>
                </div>
            ` : ''}
        </div>
        
        ${!isExpanded ? `
            <button class="panel-btn" 
                    onclick="app.quickExpandTool('${this.escapeHtml(tool.name)}')"
                    style="width: 100%; padding: 8px; font-size: 12px;">
                ⚡ Quick Execute
            </button>
        ` : ''}
    `;
    
    // Update the card's opacity for executing state
    cardElement.style.opacity = isExecuting ? '0.7' : '1';
    cardElement.innerHTML = newCardHtml;
    
    // If expanded, load the schema
    if (isExpanded) {
        setTimeout(() => {
            this.renderToolInputs(toolName);
        }, 0);
    }
};
VeraChat.prototype.renderCurrentExecution = function() {
    // Initialize toolchainExecutions if it doesn't exist
    if (!this.toolchainExecutions) {
        this.toolchainExecutions = [];
    }
    
    if (!this.currentExecution && this.toolchainExecutions.length === 0) {
        return `
            <div style="padding: 20px; text-align: center;">
                <div style="font-size: 48px; margin-bottom: 16px; opacity: 0.3;">⚙️</div>
                <p style="color: #94a3b8;">No active toolchain executions.</p>
                <p style="color: #64748b; font-size: 12px;">Toolchain executions will appear here when tools are used in conversation.</p>
            </div>
        `;
    }
    
    let html = '';
    
    // Show current execution
    if (this.currentExecution) {
        const statusColor = this.currentExecution.status === 'completed' ? '#10b981' :
                        this.currentExecution.status === 'failed' ? '#ef4444' :
                        this.currentExecution.status === 'executing' ? '#3b82f6' : '#f59e0b';
        
        html += `
            <div class="tool-card" style="border-radius: 8px; padding: 16px; margin-bottom: 16px; border-left: 4px solid ${statusColor};">
                <div style="display: flex; justify-content: space-between; margin-bottom: 12px;">
                    <div style="font-weight: 600; color: #e2e8f0;">Current Execution</div>
                    <div style="color: ${statusColor}; font-size: 12px; text-transform: uppercase;">${this.currentExecution.status}</div>
                </div>
                <div style="color: #94a3b8; font-size: 13px; margin-bottom: 8px;">${this.escapeHtml(this.currentExecution.query)}</div>
                ${this.currentExecution.totalSteps ? `<div style="color: #94a3b8; font-size: 12px;">Steps: ${this.currentExecution.steps.length}/${this.currentExecution.totalSteps}</div>` : ''}
            </div>
        `;
        
        // Show plan if available
        if (this.currentExecution.plan || this.currentExecution.plan_text) {
            html += `
                <div class="tool-container" style="border-radius: 8px; padding: 16px; margin-bottom: 16px;">
                    <div style="font-weight: 600; margin-bottom: 12px;">Execution Plan</div>
            `;
            
            // Show streaming plan text if available
            if (this.currentExecution.plan_text) {
                html += `
                    <div class="tool-card" style="padding: 12px; border-radius: 6px; border-left: 3px solid #60a5fa; margin-bottom: 12px;">
                        <div id="execution-plan-text" style="color: #cbd5e1; font-size: 12px; line-height: 1.6; white-space: pre-wrap; max-height: 300px; overflow-y: auto;">${this.escapeHtml(this.currentExecution.plan_text)}</div>
                    </div>
                `;
            }
            
            // Show structured plan if available
            if (this.currentExecution.plan && this.currentExecution.plan.length > 0) {
                html += `<div style="display: flex; flex-direction: column; gap: 8px;">`;
                
                this.currentExecution.plan.forEach((step, i) => {
                    const toolInfo = this.availableTools && this.availableTools[step.tool];
                    html += `
                        <div class="tool-card" style="padding: 10px; border-radius: 6px; border-left: 3px solid #8b5cf6;">
                            <div style="color: #a78bfa; font-size: 11px; margin-bottom: 4px;">Step ${i + 1}</div>
                            <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 4px;">
                                <div style="color: #e2e8f0; font-size: 13px; font-weight: 600;">${this.escapeHtml(step.tool)}</div>
                                ${toolInfo ? `<span style="color: #60a5fa; font-size: 11px; cursor: help;" title="${this.escapeHtml(toolInfo.description)}">ℹ️</span>` : ''}
                            </div>
                            ${toolInfo ? `<div style="color: #64748b; font-size: 11px; margin-bottom: 6px; font-style: italic;">${this.escapeHtml(toolInfo.description.substring(0, 80))}${toolInfo.description.length > 80 ? '...' : ''}</div>` : ''}
                            <div style="color: #94a3b8; font-size: 12px; margin-top: 4px;">${this.escapeHtml(step.input)}</div>
                        </div>
                    `;
                });
                
                html += `</div>`;
            }
            
            html += `</div>`;
        }
        
        // Show steps execution
        if (this.currentExecution.steps && this.currentExecution.steps.length > 0) {
            html += `
                <div class="tool-container" style="border-radius: 8px; padding: 16px;">
                    <div style="font-weight: 600; color: #60a5fa; margin-bottom: 12px;">Step Execution</div>
                    <div style="display: flex; flex-direction: column; gap: 12px;">
            `;
            
            this.currentExecution.steps.forEach(step => {
                const stepStatusColor = step.status === 'completed' ? '#10b981' :
                                    step.status === 'failed' ? '#ef4444' : '#3b82f6';
                const toolInfo = this.availableTools && this.availableTools[step.toolName];
                
                html += `
                    <div class="tool-card" style="border-radius: 6px; overflow: hidden;">
                        <div style="padding: 12px; border-left: 4px solid ${stepStatusColor};">
                            <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                                <div>
                                    <div style="color: #e2e8f0; font-weight: 600;">Step ${step.number}: ${this.escapeHtml(step.toolName)}</div>
                                    ${toolInfo ? `<div style="color: #64748b; font-size: 11px; margin-top: 2px;">${this.escapeHtml(toolInfo.description)}</div>` : ''}
                                </div>
                                <div style="color: ${stepStatusColor}; font-size: 11px; text-transform: uppercase; white-space: nowrap;">${step.status}</div>
                            </div>
                            
                            <div class="tool-subcard" style="padding: 8px; border-radius: 4px; margin-bottom: 8px;">
                                <div style="color: #60a5fa; font-size: 11px; margin-bottom: 4px;">Input:</div>
                                <div style="color: #cbd5e1; font-size: 12px; font-family: monospace;">${step.input ? this.escapeHtml(step.input.substring(0, 200)) : 'No input'}${step.input.length > 200 ? '...' : ''}</div>
                            </div>
                            
                            ${step.output ? `
                                <div class="tool-subcard" style="padding: 8px; border-radius: 4px;">
                                    <div style="color: #10b981; font-size: 11px; margin-bottom: 4px;">Output:</div>
                                    <div id="step-output-${step.number}" style="color: #cbd5e1; font-size: 12px; font-family: monospace; max-height: 150px; overflow-y: auto;">${this.escapeHtml(step.output)}</div>
                                </div>
                            ` : ''}
                            
                            ${step.error ? `
                                <div style="background: #7f1d1d; padding: 8px; border-radius: 4px; margin-top: 8px;">
                                    <div style="color: #fca5a5; font-size: 11px; margin-bottom: 4px;">Error:</div>
                                    <div style="color: #fecaca; font-size: 12px;">${this.escapeHtml(step.error)}</div>
                                </div>
                            ` : ''}
                            
                            ${step.startTime && step.endTime ? `
                                <div style="color: #64748b; font-size: 10px; margin-top: 8px;">
                                    Duration: ${((new Date(step.endTime) - new Date(step.startTime)) / 1000).toFixed(2)}s
                                </div>
                            ` : ''}
                        </div>
                    </div>
                `;
            });
            
            html += `</div></div>`;
        }
        
        // Show final result if completed
        if (this.currentExecution.status === 'completed' && this.currentExecution.finalResult) {
            html += `
                <div style="background: #064e3b; border-radius: 8px; padding: 16px; margin-top: 16px; border-left: 4px solid #10b981;">
                    <div style="font-weight: 600; color: #10b981; margin-bottom: 12px;">✓ Final Result</div>
                    <div style="color: #d1fae5; font-size: 13px; line-height: 1.5; white-space: pre-wrap; max-height: 300px; overflow-y: auto;">
                        ${this.escapeHtml(this.currentExecution.finalResult.substring(0, 500))}${this.currentExecution.finalResult.length > 500 ? '...' : ''}
                    </div>
                </div>
            `;
        }
    }
    
    return html;
};

    VeraChat.prototype.renderExecutionHistory = function() {
        if (!this.toolchainExecutions || this.toolchainExecutions.length === 0) {
            return `
                <div style="padding: 20px; text-align: center;">
                    <div style="font-size: 48px; margin-bottom: 16px; opacity: 0.3;">📜</div>
                    <p style="color: #94a3b8;">No execution history.</p>
                    <p style="color: #64748b; font-size: 12px;">Past toolchain executions will appear here.</p>
                </div>
            `;
        }
        
        let html = `
            <div style="margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center;">
                <div style="color: #94a3b8; font-size: 13px;">
                    ${this.toolchainExecutions.length} execution${this.toolchainExecutions.length !== 1 ? 's' : ''}
                </div>
                <button class="panel-btn" onclick="app.clearExecutionHistory()" style="font-size: 12px; background: #64748b;">
                    Clear History
                </button>
            </div>
            <div style="display: flex; flex-direction: column; gap: 12px;">
        `;
        
        // Sort by start time, newest first
        const sortedExecutions = [...this.toolchainExecutions].sort((a, b) => 
            new Date(b.start_time) - new Date(a.start_time)
        );
        
        sortedExecutions.forEach(exec => {
            const statusColor = exec.status === 'completed' ? '#10b981' :
                            exec.status === 'failed' ? '#ef4444' : '#f59e0b';
            
            const duration = exec.end_time && exec.start_time ? 
                ((new Date(exec.end_time) - new Date(exec.start_time)) / 1000).toFixed(2) : 
                null;
            
            html += `
                <div class="tool-card" style=" border-radius: 8px; padding: 16px; border-left: 4px solid ${statusColor}; cursor: pointer; transition: all 0.2s;" 
                    onclick="app.viewExecution('${exec.execution_id}')"
                    //  onmouseover="this.style.background='#334155'" 
                    //  onmouseout="this.style.background='#1e293b'">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                        <div style="color: #e2e8f0; font-weight: 600; flex: 1; margin-right: 12px;">
                            ${this.escapeHtml(exec.query.substring(0, 80))}${exec.query.length > 80 ? '...' : ''}
                        </div>
                        <div style="color: ${statusColor}; font-size: 12px; text-transform: uppercase; white-space: nowrap;">
                            ${exec.status}
                        </div>
                    </div>
                    <div style="display: flex; gap: 16px; color: #94a3b8; font-size: 12px;">
                        <span>Steps: ${exec.completed_steps}/${exec.total_steps}</span>
                        ${duration ? `<span>⏱️ ${duration}s</span>` : ''}
                        <span>${new Date(exec.start_time).toLocaleString()}</span>
                    </div>
                </div>
            `;
        });
        
        html += `</div>`;
        return html;
    };

    VeraChat.prototype.clearExecutionHistory = function() {
        if (confirm('Clear all execution history?')) {
            this.toolchainExecutions = [];
            this.updateToolchainUI();
        }
    };

    VeraChat.prototype.viewExecution = async function(executionId) {
        try {
            const response = await fetch(`http://llm.int:8888/api/toolchain/${this.sessionId}/execution/${executionId}`);
            const execution = await response.json();
            
            this.currentExecution = execution;
            this.toolchainView = 'executions';
            this.updateToolchainUI();
            
        } catch (error) {
            console.error('Failed to load execution:', error);
            alert('Failed to load execution details');
        }
    };

    VeraChat.prototype.loadToolchainHistory = async function() {
        if (!this.sessionId) return;
        
        try {
            const response = await fetch(`http://llm.int:8888/api/toolchain/${this.sessionId}/executions`);
            const data = await response.json();
            
            this.toolchainExecutions = data.executions;
            
            // Show history in a modal or side panel
            const container = document.getElementById('tab-toolchain');
            let html = `
                <div style="padding: 20px; overflow-y: auto; height: 100%;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                        <h2 style="color: #60a5fa; margin: 0;">Toolchain History</h2>
                        <button class="panel-btn" onclick="app.updateToolchainUI()">← Back</button>
                    </div>
            `;
            
            if (this.toolchainExecutions.length === 0) {
                html += `<p style="color: #94a3b8;">No execution history.</p>`;
            } else {
                html += `<div style="display: flex; flex-direction: column; gap: 12px;">`;
                
                this.toolchainExecutions.forEach(exec => {
                    const statusColor = exec.status === 'completed' ? '#10b981' :
                                    exec.status === 'failed' ? '#ef4444' : '#f59e0b';
                    
                    html += `
                        <div style=" border-radius: 8px; padding: 16px; border-left: 4px solid ${statusColor}; cursor: pointer;" onclick="app.viewExecution('${exec.execution_id}')">
                            <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                                <div style="color: #e2e8f0; font-weight: 600;">${this.escapeHtml(exec.query.substring(0, 60))}...</div>
                                <div style="color: ${statusColor}; font-size: 12px;">${exec.status}</div>
                            </div>
                            <div style="color: #94a3b8; font-size: 12px;">
                                Steps: ${exec.completed_steps}/${exec.total_steps} • 
                                ${new Date(exec.start_time).toLocaleString()}
                            </div>
                        </div>
                    `;
                });
                
                html += `</div>`;
            }
            
            html += `</div>`;
            container.innerHTML = html;
            
        } catch (error) {
            console.error('Failed to load toolchain history:', error);
        }
    };

    VeraChat.prototype.viewExecution = async function(executionId) {
        try {
            const response = await fetch(`http://llm.int:8888/api/toolchain/${this.sessionId}/execution/${executionId}`);
            const execution = await response.json();
            
            this.currentExecution = execution;
            this.updateToolchainUI();
            
        } catch (error) {
            console.error('Failed to load execution:', error);
        }
    };

    VeraChat.prototype.loadAvailableTools = async function() {
        if (!this.sessionId || this.availableTools) return;
        
        try {
            const response = await fetch(`http://llm.int:8888/api/toolchain/${this.sessionId}/tools`);
            const data = await response.json();
            this.availableTools = data.tools.reduce((acc, tool) => {
                acc[tool.name] = tool;
                return acc;
            }, {});
        } catch (error) {
            console.error('Failed to load tools:', error);
            this.availableTools = {};
        }
    };
    VeraChat.prototype.renderToolList = function() {
        if (!this.availableTools || Object.keys(this.availableTools).length === 0) {
            return '<div style="color: #64748b; font-size: 12px; margin-top: 16px;">Loading tools...</div>';
        }
        
        let html = `
            <div style="margin-top: 24px;">
                <h3 style="color: #60a5fa; margin-bottom: 12px;">Available Tools (${Object.keys(this.availableTools).length})</h3>
                <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 12px;">
        `;
        
        Object.values(this.availableTools).forEach(tool => {
            html += `
                <div style=" border-radius: 6px; padding: 12px; border-left: 3px solid #8b5cf6;">
                    <div style="color: #e2e8f0; font-weight: 600; margin-bottom: 6px;">${this.escapeHtml(tool.name)}</div>
                    <div style="color: #94a3b8; font-size: 12px; line-height: 1.4;">${this.escapeHtml(tool.description)}</div>
                    <div style="color: #64748b; font-size: 10px; margin-top: 6px; font-family: monospace;">${tool.type}</div>
                </div>
            `;
        });
        
        html += `</div></div>`;
        return html;
    };

    VeraChat.prototype.toggleToolList = function() {
        this.showingToolList = !this.showingToolList;
        
        if (this.showingToolList) {
            const container = document.getElementById('tab-toolchain');
            container.innerHTML = `
                <div style="padding: 20px; overflow-y: auto; height: 100%;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                        <h2 style="margin: 0;">Available Tools</h2>
                        <button class="panel-btn" onclick="app.showingToolList = false; app.updateToolchainUI()">← Back</button>
                    </div>
                    ${this.renderToolList()}
                </div>
            `;
        } else {
            this.updateToolchainUI();
        }
    };
    VeraChat.prototype.renderManualToolExecution = function() {
        if (!this.availableTools) return '';
        
        const tools = Object.values(this.availableTools);
        
        return `
            <div style=" border-radius: 8px; padding: 16px; margin-bottom: 16px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                    <h3 style="color: #60a5fa; margin: 0;">Manual Tool Execution</h3>
                    <button class="panel-btn" onclick="app.toggleManualExecution()" style="font-size: 12px;">
                        ${this.showManualExecution ? '✕ Close' : '▶ Execute Tool'}
                    </button>
                </div>
                
                ${this.showManualExecution ? `
                    <div class="tool-subcard" style=" border-radius: 6px; padding: 12px;">
                        <div style="margin-bottom: 12px;">
                            <label style="display: block; color: #94a3b8; font-size: 12px; margin-bottom: 6px;">Select Tool:</label>
                            <select id="manual-tool-select" style="width: 100%; padding: 8px;  color: #e2e8f0; border: 1px solid #334155; border-radius: 4px; font-size: 13px;">
                                <option value="">-- Select a tool --</option>
                                ${tools.map(tool => `
                                    <option value="${this.escapeHtml(tool.name)}">${this.escapeHtml(tool.name)}</option>
                                `).join('')}
                            </select>
                        </div>
                        
                        <div id="tool-description" style="display: none;  padding: 10px; border-radius: 4px; margin-bottom: 12px; border-left: 3px solid #8b5cf6;">
                            <div style="color: #a78bfa; font-size: 11px; margin-bottom: 4px;">Description:</div>
                            <div id="tool-description-text" style="color: #cbd5e1; font-size: 12px;"></div>
                        </div>
                        
                        <div style="margin-bottom: 12px;">
                            <label style="display: block; color: #94a3b8; font-size: 12px; margin-bottom: 6px;">Tool Input:</label>
                            <textarea id="manual-tool-input" 
                                    placeholder="Enter tool input..." 
                                    style="width: 100%; min-height: 80px; padding: 8px;  color: #e2e8f0; border: 1px solid #334155; border-radius: 4px; font-size: 13px; font-family: monospace; resize: vertical;"
                            ></textarea>
                        </div>
                        
                        <div style="display: flex; gap: 8px;">
                            <button class="panel-btn" 
                                    onclick="app.executeManualTool()" 
                                    style="flex: 1;  padding: 10px;">
                                🚀 Execute
                            </button>
                            <button class="panel-btn" 
                                    onclick="app.clearManualExecution()" 
                                    style="background: #64748b;">
                                Clear
                            </button>
                        </div>
                        
                        ${this.manualExecutionResult ? `
                            <div style="margin-top: 12px;  border-radius: 4px; padding: 12px; border-left: 3px solid ${this.manualExecutionResult.success ? '#10b981' : '#ef4444'};">
                                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                                    <div style="color: ${this.manualExecutionResult.success ? '#10b981' : '#ef4444'}; font-size: 11px; font-weight: 600; text-transform: uppercase;">
                                        ${this.manualExecutionResult.success ? '✓ Success' : '✗ Error'}
                                    </div>
                                    <div style="color: #64748b; font-size: 10px;">
                                        ${this.manualExecutionResult.duration}ms
                                    </div>
                                </div>
                                <div style="color: #cbd5e1; font-size: 12px; font-family: monospace; max-height: 200px; overflow-y: auto; white-space: pre-wrap; word-break: break-word;">
                                    ${this.escapeHtml(this.manualExecutionResult.output)}
                                </div>
                            </div>
                        ` : ''}
                    </div>
                ` : ''}
            </div>
        `;
    };
 VeraChat.prototype.renderToolCards = function() {
    if (!this.availableTools || Object.keys(this.availableTools).length === 0) {
        return '<div style="color: #64748b; font-size: 12px; margin-top: 16px;">Loading tools...</div>';
    }
    
    const tools = Object.values(this.availableTools);
    
    // Apply search and filters (keep existing code)
    let filteredTools = tools;
    
    if (this.toolSearchQuery) {
        const query = this.toolSearchQuery.toLowerCase();
        filteredTools = filteredTools.filter(tool => 
            tool.name.toLowerCase().includes(query) ||
            tool.description.toLowerCase().includes(query) ||
            tool.type.toLowerCase().includes(query)
        );
    }
    
    if (this.toolTypeFilter && this.toolTypeFilter !== 'all') {
        filteredTools = filteredTools.filter(tool => 
            tool.type.toLowerCase() === this.toolTypeFilter.toLowerCase()
        );
    }
    
    const toolTypes = [...new Set(tools.map(t => t.type))].sort();
    
        
        let html = `
            <div style="margin-bottom: 16px;">
                <!-- Search and Filter Bar -->
                <div style=" border-radius: 8px; padding: 16px; margin-bottom: 16px;">
                    <div style="display: flex; gap: 12px; flex-wrap: wrap; align-items: center;">
                        <!-- Search Input -->
                        <div style="flex: 1; min-width: 250px; position: relative;">
                            <input type="text" 
                                id="tool-search" 
                                placeholder="🔍 Search by name, description, or type..." 
                                value="${this.escapeHtml(this.toolSearchQuery || '')}"
                                style="width: 100%; padding: 10px 40px 10px 12px; color: #e2e8f0; border: 1px solid #334155; border-radius: 6px; font-size: 13px;">
                            ${this.toolSearchQuery ? `
                                <button onclick="app.clearToolSearch()" 
                                        style="position: absolute; right: 10px; top: 50%; transform: translateY(-50%); background: none; border: none; color: #64748b; cursor: pointer; font-size: 16px; padding: 4px;"
                                        title="Clear search">✕</button>
                            ` : ''}
                        </div>
                        
                        <!-- Type Filter -->
                        <div style="position: relative;">
                            <select id="tool-type-filter" 
                                    onchange="app.setToolTypeFilter(this.value)"
                                    style="padding: 10px 35px 10px 12px; color: #e2e8f0; border: 1px solid #334155; border-radius: 6px; font-size: 13px; cursor: pointer; appearance: none;">
                                <option value="all">All Types</option>
                                ${toolTypes.map(type => `
                                    <option value="${this.escapeHtml(type)}" ${this.toolTypeFilter === type ? 'selected' : ''}>
                                        ${this.escapeHtml(type)}
                                    </option>
                                `).join('')}
                            </select>
                            <div style="position: absolute; right: 12px; top: 50%; transform: translateY(-50%); pointer-events: none; color: #64748b;">▼</div>
                        </div>
                        
                        <!-- View Toggle -->
                        <button class="panel-btn" onclick="app.toggleToolView()" style="padding: 10px 16px;">
                            ${this.toolViewMode === 'grid' ? '📋 List' : '⊞ Grid'}
                        </button>
                        
                        <!-- Results Count -->
                        <div style="color: #94a3b8; font-size: 13px; white-space: nowrap;">
                            ${filteredTools.length} of ${tools.length} tools
                        </div>
                    </div>
                    
                    <!-- Active Filters Display -->
                    ${this.toolSearchQuery || (this.toolTypeFilter && this.toolTypeFilter !== 'all') ? `
                        <div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid #334155; display: flex; gap: 8px; flex-wrap: wrap; align-items: center;">
                            <span style="color: #94a3b8; font-size: 12px;">Active filters:</span>
                            ${this.toolSearchQuery ? `
                                <span style=" color: white; padding: 4px 10px; border-radius: 12px; font-size: 11px; display: inline-flex; align-items: center; gap: 6px;">
                                    Search: "${this.escapeHtml(this.toolSearchQuery)}"
                                    <button onclick="app.clearToolSearch()" style="background: none; border: none; color: white; cursor: pointer; padding: 0; font-size: 14px;">✕</button>
                                </span>
                            ` : ''}
                            ${this.toolTypeFilter && this.toolTypeFilter !== 'all' ? `
                                <span style="background: #8b5cf6; color: white; padding: 4px 10px; border-radius: 12px; font-size: 11px; display: inline-flex; align-items: center; gap: 6px;">
                                    Type: ${this.escapeHtml(this.toolTypeFilter)}
                                    <button onclick="app.setToolTypeFilter('all')" style="background: none; border: none; color: white; cursor: pointer; padding: 0; font-size: 14px;">✕</button>
                                </span>
                            ` : ''}
                            <button onclick="app.clearAllToolFilters()" 
                                    class="panel-btn" 
                                    style="padding: 4px 10px; font-size: 11px; background: #64748b;">
                                Clear All
                            </button>
                        </div>
                    ` : ''}
                </div>
                
                <!-- Tool Cards Grid/List -->
                <div id="tool-cards-container" 
                    style="display: grid; 
                            grid-template-columns: repeat(auto-fill, minmax(${this.toolViewMode === 'grid' ? '300px' : '100%'}, 1fr)); 
                            gap: 12px;">
        `;
        
    if (filteredTools.length === 0) {
        html += `<!-- No tools found message -->`;
    } else {
        filteredTools.forEach(tool => {
            const isExecuting = this.executingTools && this.executingTools[tool.name];
            const hasResult = this.toolResults && this.toolResults[tool.name];
            const isExpanded = this.expandedTools && this.expandedTools[tool.name];
            
            html += `
                <div class="tool-card" 
                    data-tool-name="${this.escapeHtml(tool.name)}" 
                    data-tool-type="${this.escapeHtml(tool.type)}"
                    style="border-radius: 8px; padding: 14px; border-left: 4px solid #8b5cf6; transition: all 0.2s; ${isExecuting ? 'opacity: 0.7;' : ''}">
                    
                    <!-- Tool Header -->
                    <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 10px;">
                        <div style="flex: 1;">
                            <div style="color: #e2e8f0; font-weight: 600; font-size: 14px; margin-bottom: 4px;">
                                ${this.escapeHtml(tool.name)}
                            </div>
                            <div style="color: #64748b; font-size: 10px; font-family: monospace; margin-bottom: 8px;">
                                ${this.escapeHtml(tool.type)}
                            </div>
                        </div>
                        <button class="panel-btn" 
                                onclick="app.toggleToolExpand('${this.escapeHtml(tool.name)}')"
                                style="padding: 4px 8px; font-size: 11px; min-width: auto;">
                            ${isExpanded ? '▼' : '▶'}
                        </button>
                    </div>
                    
                    <!-- Tool Description -->
                    <div style="color: #94a3b8; font-size: 12px; line-height: 1.5; margin-bottom: 12px;">
                        ${this.escapeHtml(tool.description)}
                    </div>
                    
                    <!-- Expanded Content -->
                    <div id="tool-expand-${this.escapeHtml(tool.name)}" 
                        style="display: ${isExpanded ? 'block' : 'none'};">
                        
                        <!-- Dynamic Input Form -->
                        <div id="tool-inputs-${this.escapeHtml(tool.name)}" style="margin-bottom: 10px;">
                            <div style="color: #94a3b8; font-size: 11px; margin-bottom: 6px;">Loading inputs...</div>
                        </div>
                        
                        <!-- Action Buttons -->
                        <div style="display: flex; gap: 6px; margin-bottom: 10px;">
                            <button class="panel-btn" 
                                    onclick="app.executeToolFromCard('${this.escapeHtml(tool.name)}')"
                                    style="flex: 1; padding: 8px; font-size: 12px;"
                                    ${isExecuting ? 'disabled' : ''}>
                                ${isExecuting ? '⏳ Executing...' : '🚀 Execute'}
                            </button>
                            <button class="panel-btn" 
                                    onclick="app.clearToolInput('${this.escapeHtml(tool.name)}')"
                                    style="background: #64748b; padding: 8px; font-size: 12px;"
                                    ${isExecuting ? 'disabled' : ''}>
                                Clear
                            </button>
                        </div>
                        
                        <!-- Result Area -->
                        ${hasResult ? `
                            <div style="background: #0f172a; border-radius: 6px; padding: 10px; border-left: 3px solid ${this.toolResults[tool.name].success ? '#10b981' : '#ef4444'};">
                                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                                    <div style="color: ${this.toolResults[tool.name].success ? '#10b981' : '#ef4444'}; font-size: 10px; font-weight: 600; text-transform: uppercase;">
                                        ${this.toolResults[tool.name].success ? '✓ Success' : '✗ Error'}
                                    </div>
                                    <div style="display: flex; gap: 8px; align-items: center;">
                                        <div style="color: #64748b; font-size: 9px;">
                                            ${this.toolResults[tool.name].duration}ms
                                        </div>
                                        <button onclick="app.clearToolResult('${this.escapeHtml(tool.name)}')" 
                                                style="background: none; border: none; color: #64748b; cursor: pointer; padding: 2px; font-size: 12px;"
                                                title="Clear result">✕</button>
                                    </div>
                                </div>
                                <div style="color: #cbd5e1; font-size: 11px; font-family: monospace; max-height: 150px; overflow-y: auto; white-space: pre-wrap; word-break: break-word; line-height: 1.4;">
                                    ${this.escapeHtml(this.toolResults[tool.name].output)}
                                </div>
                            </div>
                        ` : ''}
                    </div>
                    
                    <!-- Quick Execute Button (when collapsed) -->
                    ${!isExpanded ? `
                        <button class="panel-btn" 
                                onclick="app.quickExpandTool('${this.escapeHtml(tool.name)}')"
                                style="width: 100%; padding: 8px; font-size: 12px;">
                            ⚡ Quick Execute
                        </button>
                    ` : ''}
                </div>
            `;
        });
    }
    
    html += `</div></div>`;
    
    return html;
};
VeraChat.prototype.loadToolSchema = async function(toolName) {
    if (!this.toolSchemas) this.toolSchemas = {};
    
    // Return cached schema if available
    if (this.toolSchemas[toolName]) {
        return this.toolSchemas[toolName];
    }
    
    try {
        const response = await fetch(`http://llm.int:8888/api/toolchain/${this.sessionId}/tool/${encodeURIComponent(toolName)}/schema`);
        const schema = await response.json();
        
        this.toolSchemas[toolName] = schema;
        return schema;
        
    } catch (error) {
        console.error('Failed to load tool schema:', error);
        // Fallback schema
        return {
            name: toolName,
            parameters: [{
                name: "input",
                type: "string",
                description: "Tool input",
                required: true
            }]
        };
    }
};

VeraChat.prototype.renderToolInputs = async function(toolName) {
    const schema = await this.loadToolSchema(toolName);
    const container = document.getElementById(`tool-inputs-${toolName}`);
    
    if (!container) return;
    
    let html = '';
    
    schema.parameters.forEach(param => {
        const inputId = `tool-input-${toolName}-${param.name}`;
        const isRequired = param.required ? '<span style="color: #ef4444;">*</span>' : '';
        const defaultValue = param.default !== undefined && param.default !== null ? ` (default: ${param.default})` : '';
        
        html += `
            <div style="margin-bottom: 10px;">
                <label style="display: block; color: #94a3b8; font-size: 11px; margin-bottom: 4px;">
                    ${this.escapeHtml(param.name)}${isRequired}${defaultValue}
                </label>
        `;
        
        // Render different input types based on parameter type
        if (param.type === 'boolean') {
            html += `
                <select id="${inputId}" 
                        style="width: 100%; padding: 8px; color: #e2e8f0; border: 1px solid #334155; border-radius: 4px; font-size: 12px;">
                    <option value="true"${param.default === true ? ' selected' : ''}>true</option>
                    <option value="false"${param.default === false ? ' selected' : ''}>false</option>
                </select>
            `;
        } else if (param.type === 'integer' || param.type === 'number') {
            html += `
                <input type="number" 
                       id="${inputId}"
                       placeholder="${this.escapeHtml(param.description)}"
                       value="${param.default || ''}"
                       style="width: 100%; padding: 8px; color: #e2e8f0; border: 1px solid #334155; border-radius: 4px; font-size: 12px;">
            `;
        } else if (param.description && param.description.length > 100) {
            // Long description = textarea
            html += `
                <textarea id="${inputId}" 
                          placeholder="${this.escapeHtml(param.description)}"
                          style="width: 100%; min-height: 60px; padding: 8px; color: #e2e8f0; border: 1px solid #334155; border-radius: 4px; font-size: 12px; font-family: monospace; resize: vertical;"
                >${param.default || ''}</textarea>
            `;
        } else {
            // Default to text input
            html += `
                <input type="text" 
                       id="${inputId}"
                       placeholder="${this.escapeHtml(param.description)}"
                       value="${param.default || ''}"
                       style="width: 100%; padding: 8px; color: #e2e8f0; border: 1px solid #334155; border-radius: 4px; font-size: 12px;">
            `;
        }
        
        if (param.description) {
            html += `
                <div style="color: #64748b; font-size: 10px; margin-top: 2px; font-style: italic;">
                    ${this.escapeHtml(param.description)}
                </div>
            `;
        }
        
        html += `</div>`;
    });
    
    container.innerHTML = html;
};
    VeraChat.prototype.toggleManualExecution = function() {
        this.showManualExecution = !this.showManualExecution;
        this.updateToolchainUI();
    };

    VeraChat.prototype.clearManualExecution = function() {
        const input = document.getElementById('manual-tool-input');
        const select = document.getElementById('manual-tool-select');
        if (input) input.value = '';
        if (select) select.value = '';
        
        const descDiv = document.getElementById('tool-description');
        if (descDiv) descDiv.style.display = 'none';
        
        this.manualExecutionResult = null;
        this.updateToolchainUI();
    };

    VeraChat.prototype.executeManualTool = async function() {
        const select = document.getElementById('manual-tool-select');
        const input = document.getElementById('manual-tool-input');
        
        if (!select || !input) return;
        
        const toolName = select.value;
        const toolInput = input.value;
        
        if (!toolName) {
            alert('Please select a tool');
            return;
        }
        
        if (!toolInput.trim()) {
            alert('Please enter tool input');
            return;
        }
        
        // Show loading state
        this.manualExecutionResult = {
            success: null,
            output: 'Executing...',
            duration: 0
        };
        this.updateToolchainUI();
        
        const startTime = Date.now();
        
        try {
            const response = await fetch(`http://llm.int:8888/api/toolchain/${this.sessionId}/execute-tool?tool_name=${encodeURIComponent(toolName)}&tool_input=${encodeURIComponent(toolInput)}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            this.manualExecutionResult = {
                success: data.success,
                output: data.output,
                duration: Math.round(data.duration_ms),
                tool_name: data.tool_name,
                executed_at: data.executed_at
            };
            
        } catch (error) {
            const duration = Date.now() - startTime;
            this.manualExecutionResult = {
                success: false,
                output: error.message || 'Execution failed',
                duration: duration
            };
        }
        
        this.updateToolchainUI();
    };
    VeraChat.prototype.executeManualToolStreaming = async function() {
        const select = document.getElementById('manual-tool-select');
        const input = document.getElementById('manual-tool-input');
        
        if (!select || !input) return;
        
        const toolName = select.value;
        const toolInput = input.value;
        
        if (!toolName || !toolInput.trim()) {
            alert('Please select a tool and enter input');
            return;
        }
        
        this.manualExecutionResult = {
            success: null,
            output: '',
            duration: 0,
            streaming: true
        };
        this.updateToolchainUI();
        
        const startTime = Date.now();
        
        try {
            const response = await fetch(`http://llm.int:8888/api/toolchain/${this.sessionId}/execute-tool-stream?tool_name=${encodeURIComponent(toolName)}&tool_input=${encodeURIComponent(toolInput)}`, {
                method: 'POST',
            });
            
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            
            while (true) {
                const {done, value} = await reader.read();
                if (done) break;
                
                const chunk = decoder.decode(value);
                this.manualExecutionResult.output += chunk;
                this.manualExecutionResult.duration = Date.now() - startTime;
                this.updateToolchainUI();
            }
            
            this.manualExecutionResult.success = true;
            this.manualExecutionResult.streaming = false;
            
        } catch (error) {
            this.manualExecutionResult.success = false;
            this.manualExecutionResult.output += `\n\nError: ${error.message}`;
            this.manualExecutionResult.streaming = false;
        }
        
        this.updateToolchainUI();
    };

    VeraChat.prototype.filterTools = function(query) {
        this.toolSearchQuery = query;
        
        // Only update the cards container, not the whole UI
        this.updateToolCardsOnly();
    };

    VeraChat.prototype.updateToolCardsOnly = function() {
        const container = document.getElementById('tool-cards-container');
        if (!container) return;
        
        const tools = Object.values(this.availableTools);
        
        // Apply filters
        let filteredTools = tools;
        
        if (this.toolSearchQuery) {
            const query = this.toolSearchQuery.toLowerCase();
            filteredTools = filteredTools.filter(tool => 
                tool.name.toLowerCase().includes(query) ||
                tool.description.toLowerCase().includes(query) ||
                tool.type.toLowerCase().includes(query)
            );
        }
        
        if (this.toolTypeFilter && this.toolTypeFilter !== 'all') {
            filteredTools = filteredTools.filter(tool => 
                tool.type.toLowerCase() === this.toolTypeFilter.toLowerCase()
            );
        }
        
        // Update results count
        const tools_count = document.querySelector('[style*="white-space: nowrap"]');
        if (tools_count) {
            tools_count.textContent = `${filteredTools.length} of ${tools.length} tools`;
        }
        
        // Update active filters display
        this.updateActiveFiltersDisplay();
        
        // Rebuild cards HTML
        let cardsHtml = '';
        
        if (filteredTools.length === 0) {
            cardsHtml = `
                <div style="grid-column: 1 / -1; text-align: center; padding: 40px;  border-radius: 8px;">
                    <div style="font-size: 48px; margin-bottom: 16px; opacity: 0.3;">🔍</div>
                    <div style="color: #94a3b8; font-size: 14px; margin-bottom: 8px;">No tools found</div>
                    <div style="color: #64748b; font-size: 12px;">
                        ${this.toolSearchQuery ? `Try a different search term or ` : ''}
                        <button onclick="app.clearAllToolFilters()" style="background: none; border: none; color: #3b82f6; cursor: pointer; text-decoration: underline;">clear filters</button>
                    </div>
                </div>
            `;
        } else {
            filteredTools.forEach(tool => {
                const isExecuting = this.executingTools && this.executingTools[tool.name];
                const hasResult = this.toolResults && this.toolResults[tool.name];
                
                cardsHtml += `
                    <div class="tool-card" 
                        data-tool-name="${this.escapeHtml(tool.name)}" 
                        data-tool-type="${this.escapeHtml(tool.type)}"
                        style=" border-radius: 8px; padding: 14px; border-left: 4px solid #8b5cf6; transition: all 0.2s; ${isExecuting ? 'opacity: 0.7;' : ''}">
                        
                        <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 10px;">
                            <div style="flex: 1;">
                                <div style="color: #e2e8f0; font-weight: 600; font-size: 14px; margin-bottom: 4px;">
                                    ${this.escapeHtml(tool.name)}
                                </div>
                                <div style="color: #64748b; font-size: 10px; font-family: monospace; margin-bottom: 8px;">
                                    ${this.escapeHtml(tool.type)}
                                </div>
                            </div>
                            <button class="panel-btn" 
                                    onclick="app.toggleToolExpand('${this.escapeHtml(tool.name)}')"
                                    style="padding: 4px 8px; font-size: 11px; min-width: auto;">
                                ${this.expandedTools && this.expandedTools[tool.name] ? '▼' : '▶'}
                            </button>
                        </div>
                        
                        <div style="color: #94a3b8; font-size: 12px; line-height: 1.5; margin-bottom: 12px;">
                            ${this.escapeHtml(tool.description)}
                        </div>
                        
                        <div id="tool-expand-${this.escapeHtml(tool.name)}" 
                            style="display: ${this.expandedTools && this.expandedTools[tool.name] ? 'block' : 'none'};">
                            
                            <div style="margin-bottom: 10px;">
                                <label style="display: block; color: #94a3b8; font-size: 11px; margin-bottom: 4px;">Input:</label>
                                <textarea id="tool-input-${this.escapeHtml(tool.name)}" 
                                        placeholder="Enter tool input..."
                                        style="width: 100%; min-height: 60px; padding: 8px; color: #e2e8f0; border: 1px solid #334155; border-radius: 4px; font-size: 12px; font-family: monospace; resize: vertical;"
                                        ${isExecuting ? 'disabled' : ''}
                                ></textarea>
                            </div>
                            
                            <div style="display: flex; gap: 6px; margin-bottom: 10px;">
                                <button class="panel-btn" 
                                        onclick="app.executeToolFromCard('${this.escapeHtml(tool.name)}')"
                                        style="flex: 1;  padding: 8px; font-size: 12px;"
                                        ${isExecuting ? 'disabled' : ''}>
                                    ${isExecuting ? '⏳ Executing...' : '🚀 Execute'}
                                </button>
                                <button class="panel-btn" 
                                        onclick="app.clearToolInput('${this.escapeHtml(tool.name)}')"
                                        style="background: #64748b; padding: 8px; font-size: 12px;"
                                        ${isExecuting ? 'disabled' : ''}>
                                    Clear
                                </button>
                            </div>
                            
                            ${hasResult ? `
                                <div style="background: #0f172a; border-radius: 6px; padding: 10px; border-left: 3px solid ${this.toolResults[tool.name].success ? '#10b981' : '#ef4444'};">
                                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                                        <div style="color: ${this.toolResults[tool.name].success ? '#10b981' : '#ef4444'}; font-size: 10px; font-weight: 600; text-transform: uppercase;">
                                            ${this.toolResults[tool.name].success ? '✓ Success' : '✗ Error'}
                                        </div>
                                        <div style="display: flex; gap: 8px; align-items: center;">
                                            <div style="color: #64748b; font-size: 9px;">
                                                ${this.toolResults[tool.name].duration}ms
                                            </div>
                                            <button onclick="app.clearToolResult('${this.escapeHtml(tool.name)}')" 
                                                    style="background: none; border: none; color: #64748b; cursor: pointer; padding: 2px; font-size: 12px;"
                                                    title="Clear result">✕</button>
                                        </div>
                                    </div>
                                    <div style="color: #cbd5e1; font-size: 11px; font-family: monospace; max-height: 150px; overflow-y: auto; white-space: pre-wrap; word-break: break-word; line-height: 1.4;">
                                        ${this.escapeHtml(this.toolResults[tool.name].output)}
                                    </div>
                                </div>
                            ` : ''}
                        </div>
                        
                        ${!this.expandedTools || !this.expandedTools[tool.name] ? `
                            <button class="panel-btn" 
                                    onclick="app.quickExpandTool('${this.escapeHtml(tool.name)}')"
                                    style="width: 100%; background: #334155; padding: 8px; font-size: 12px;">
                                ⚡ Quick Execute
                            </button>
                        ` : ''}
                    </div>
                `;
            });
        }
        
        container.innerHTML = cardsHtml;
    };

    VeraChat.prototype.updateActiveFiltersDisplay = function() {
        // Find the parent of tool-cards-container
        const container = document.getElementById('tool-cards-container');
        if (!container || !container.parentElement) return;
        
        const searchBar = container.parentElement.querySelector('div[style*="border-top"]');
        if (!searchBar) return;
        
        if (this.toolSearchQuery || (this.toolTypeFilter && this.toolTypeFilter !== 'all')) {
            const filtersHtml = `
                <span style="color: #94a3b8; font-size: 12px;">Active filters:</span>
                ${this.toolSearchQuery ? `
                    <span style=" color: white; padding: 4px 10px; border-radius: 12px; font-size: 11px; display: inline-flex; align-items: center; gap: 6px;">
                        Search: "${this.escapeHtml(this.toolSearchQuery)}"
                        <button onclick="app.clearToolSearch()" style="background: none; border: none; color: white; cursor: pointer; padding: 0; font-size: 14px;">✕</button>
                    </span>
                ` : ''}
                ${this.toolTypeFilter && this.toolTypeFilter !== 'all' ? `
                    <span style="background: #8b5cf6; color: white; padding: 4px 10px; border-radius: 12px; font-size: 11px; display: inline-flex; align-items: center; gap: 6px;">
                        Type: ${this.escapeHtml(this.toolTypeFilter)}
                        <button onclick="app.setToolTypeFilter('all')" style="background: none; border: none; color: white; cursor: pointer; padding: 0; font-size: 14px;">✕</button>
                    </span>
                ` : ''}
                <button onclick="app.clearAllToolFilters()" 
                        class="panel-btn" 
                        style="padding: 4px 10px; font-size: 11px; background: #64748b;">
                    Clear All
                </button>
            `;
            searchBar.innerHTML = filtersHtml;
            searchBar.style.display = 'flex';
        } else {
            searchBar.style.display = 'none';
        }
    };

    VeraChat.prototype.setupToolSearchListener = function() {
        const searchInput = document.getElementById('tool-search');
        if (!searchInput) return;
        
        searchInput.addEventListener('input', (e) => {
            this.filterTools(e.target.value);
        });
        
        // Prevent form submission
        searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
            }
            if (e.key === 'Escape') {
                this.clearToolSearch();
            }
        });
    };

    VeraChat.prototype.clearToolSearch = function() {
        this.toolSearchQuery = '';
        const searchInput = document.getElementById('tool-search');
        if (searchInput) {
            searchInput.value = '';
        }
        this.updateToolCardsOnly();
    };

    VeraChat.prototype.setToolTypeFilter = function(type) {
        this.toolTypeFilter = type;
        this.updateToolCardsOnly();
    };

    VeraChat.prototype.clearAllToolFilters = function() {
        this.toolSearchQuery = '';
        this.toolTypeFilter = 'all';
        
        const searchInput = document.getElementById('tool-search');
        if (searchInput) searchInput.value = '';
        
        const typeFilter = document.getElementById('tool-type-filter');
        if (typeFilter) typeFilter.value = 'all';
        
        this.updateToolCardsOnly();
    };

    VeraChat.prototype.toggleToolExpand = function(toolName) {
        if (!this.expandedTools) this.expandedTools = {};
        this.expandedTools[toolName] = !this.expandedTools[toolName];
        this.updateSingleToolCard(toolName);
    };

    VeraChat.prototype.quickExpandTool = function(toolName) {
        if (!this.expandedTools) this.expandedTools = {};
        this.expandedTools[toolName] = true;
        this.updateSingleToolCard(toolName);
        
        setTimeout(async () => {
            await this.renderToolInputs(toolName);
            const firstInput = document.querySelector(`#tool-inputs-${toolName} input, #tool-inputs-${toolName} textarea`);
            if (firstInput) firstInput.focus();
        }, 50);
    };

    VeraChat.prototype.toggleToolView = function() {
        this.toolViewMode = this.toolViewMode === 'grid' ? 'list' : 'grid';
        this.updateToolchainUI();
    };

    VeraChat.prototype.filterTools = function(query) {
        this.toolSearchQuery = query;
        this.updateToolCardsOnly();
    };

    VeraChat.prototype.clearToolInput = function(toolName) {
        const schema = this.toolSchemas[toolName];
        if (!schema) return;
        
        // Clear all inputs for this tool
        schema.parameters.forEach(param => {
            const inputId = `tool-input-${toolName}-${param.name}`;
            const input = document.getElementById(inputId);
            if (input) {
                input.value = param.default || '';
            }
        });
        
        // Focus first input
        const firstInput = document.querySelector(`#tool-inputs-${toolName} input, #tool-inputs-${toolName} textarea`);
        if (firstInput) firstInput.focus();
    };
    
    VeraChat.prototype.clearToolResult = function(toolName) {
        if (!this.toolResults) this.toolResults = {};
        delete this.toolResults[toolName];
        this.updateSingleToolCard(toolName);
    };

    VeraChat.prototype.executeToolFromCard = async function(toolName) {
        const schema = this.toolSchemas[toolName];
        
        if (!schema) {
            alert('Tool schema not loaded');
            return;
        }
        
        // Collect all input values
        const toolInput = {};
        let hasError = false;
        
        for (const param of schema.parameters) {
            const inputId = `tool-input-${toolName}-${param.name}`;
            const input = document.getElementById(inputId);
            
            if (!input) continue;
            
            let value = input.value.trim();
            
            // Validate required fields
            if (param.required && !value) {
                alert(`Required field missing: ${param.name}`);
                input.focus();
                hasError = true;
                break;
            }
            
            // Type conversion
            if (param.type === 'integer') {
                value = parseInt(value, 10);
                if (isNaN(value)) value = param.default || 0;
            } else if (param.type === 'number') {
                value = parseFloat(value);
                if (isNaN(value)) value = param.default || 0;
            } else if (param.type === 'boolean') {
                value = value === 'true';
            }
            
            // Only include if value is present or required
            if (value !== '' || param.required) {
                toolInput[param.name] = value;
            }
        }
        
        if (hasError) return;
        
        // Initialize tracking objects
        if (!this.executingTools) this.executingTools = {};
        if (!this.toolResults) this.toolResults = {};
        
        // Mark as executing and update just this card
        this.executingTools[toolName] = true;
        delete this.toolResults[toolName];
        this.updateSingleToolCard(toolName);
        
        const startTime = Date.now();
        
        try {
            // Convert toolInput to query params
            const params = new URLSearchParams();
            params.append('tool_name', toolName);
            params.append('tool_input', JSON.stringify(toolInput));
            
            const response = await fetch(
                `http://llm.int:8888/api/toolchain/${this.sessionId}/execute-tool?${params.toString()}`, 
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    }
                }
            );
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            this.toolResults[toolName] = {
                success: data.success,
                output: data.output,
                duration: Math.round(data.duration_ms),
                executed_at: data.executed_at
            };
            
        } catch (error) {
            const duration = Date.now() - startTime;
            this.toolResults[toolName] = {
                success: false,
                output: error.message || 'Execution failed',
                duration: duration
            };
        } finally {
            delete this.executingTools[toolName];
            this.updateSingleToolCard(toolName);
        }
    };
})();