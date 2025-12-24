/**
 * Advanced Toolchain Query Builder - PERFECT BUTTON PLACEMENT
 * Fixes: Button now appears inline with Tools, Executions, History
 */

(() => {
    console.log('[Query Builder] Starting initialization...');

    // ============================================================
    // Planning Strategy Definitions
    // ============================================================
    const PLANNING_STRATEGIES = {
        STATIC: {
            id: 'static',
            name: 'Static',
            description: 'Fixed plan upfront (default)',
            icon: '📋',
            color: '#3b82f6'
        },
        QUICK: {
            id: 'quick',
            name: 'Quick',
            description: 'Fast, minimal plan for simple tasks',
            icon: '⚡',
            color: '#f59e0b'
        },
        COMPREHENSIVE: {
            id: 'comprehensive',
            name: 'Comprehensive',
            description: 'Deep, thorough multi-step plans',
            icon: '🔍',
            color: '#8b5cf6'
        },
        DYNAMIC: {
            id: 'dynamic',
            name: 'Dynamic',
            description: 'Plan one step at a time based on results',
            icon: '🔄',
            color: '#10b981'
        },
        EXPLORATORY: {
            id: 'exploratory',
            name: 'Exploratory',
            description: 'Multiple alternatives explored in parallel',
            icon: '🌳',
            color: '#06b6d4'
        },
        MULTIPATH: {
            id: 'multipath',
            name: 'Multi-path',
            description: 'Branch and try different approaches',
            icon: '🔀',
            color: '#ec4899'
        }
    };

    // ============================================================
    // Plan Templates
    // ============================================================
    const PLAN_TEMPLATES = [
        {
            id: 'direct_prompt',
            name: 'Direct Prompt',
            description: 'Just describe what you want - AI creates the toolchain',
            icon: '💬',
            category: 'direct',
            params: [
                { name: 'query', type: 'textarea', label: 'What do you want to do?', required: true, placeholder: 'Describe your task in natural language...' }
            ]
        },
        {
            id: 'web_research',
            name: 'Web Research',
            description: 'Comprehensive web research with content fetching and analysis',
            icon: '🌐',
            category: 'research',
            params: [
                { name: 'query', type: 'text', label: 'Research Query', required: true },
                { name: 'depth', type: 'select', label: 'Research Depth', options: ['quick', 'standard', 'deep'], default: 'standard' }
            ]
        },
        {
            id: 'data_analysis',
            name: 'Data Analysis',
            description: 'Load, process, and analyze data files',
            icon: '📊',
            category: 'data',
            params: [
                { name: 'data_source', type: 'text', label: 'Data File Path', required: true },
                { name: 'analysis_type', type: 'text', label: 'Analysis Type', required: true }
            ]
        },
        {
            id: 'code_task',
            name: 'Code Task',
            description: 'Generate, execute, and verify code',
            icon: '💻',
            category: 'code',
            params: [
                { name: 'task_description', type: 'textarea', label: 'Task Description', required: true },
                { name: 'language', type: 'select', label: 'Language', options: ['python', 'javascript', 'bash'], default: 'python' }
            ]
        },
        {
            id: 'comparison_research',
            name: 'Comparison Research',
            description: 'Research and compare two topics',
            icon: '⚖️',
            category: 'research',
            params: [
                { name: 'topic_a', type: 'text', label: 'First Topic', required: true },
                { name: 'topic_b', type: 'text', label: 'Second Topic', required: true }
            ]
        },
        {
            id: 'document_creation',
            name: 'Document Creation',
            description: 'Research, outline, and create documents',
            icon: '📝',
            category: 'creation',
            params: [
                { name: 'topic', type: 'text', label: 'Document Topic', required: true },
                { name: 'doc_type', type: 'select', label: 'Document Type', options: ['report', 'article', 'guide', 'analysis'], default: 'report' }
            ]
        },
        {
            id: 'custom',
            name: 'Custom Toolchain',
            description: 'Build your own step-by-step toolchain',
            icon: '🛠️',
            category: 'custom',
            params: []
        }
    ];

    // ============================================================
    // Button Injection - FIXED PLACEMENT
    // ============================================================
    
    function injectQueryButton() {
        const container = document.getElementById('tab-toolchain');
        if (!container) {
            console.log('[Query Builder] Container not found');
            return false;
        }
        
        // Find all panel buttons in the container
        const allButtons = container.querySelectorAll('button.panel-btn');
        
        // Look for Tools, Executions, History buttons that are siblings
        for (let i = 0; i < allButtons.length - 2; i++) {
            const btn1 = allButtons[i];
            const btn2 = allButtons[i + 1];
            const btn3 = allButtons[i + 2];
            
            const text1 = btn1.textContent.trim();
            const text2 = btn2.textContent.trim();
            const text3 = btn3.textContent.trim();
            
            // Check if this is the view switcher group
            if ((text1 === 'Tools' || text1 === 'Executions' || text1 === 'History') &&
                (text2 === 'Tools' || text2 === 'Executions' || text2 === 'History') &&
                (text3 === 'Tools' || text3 === 'Executions' || text3 === 'History')) {
                
                // Check if they have the same parent
                const parent1 = btn1.parentElement;
                const parent2 = btn2.parentElement;
                const parent3 = btn3.parentElement;
                
                if (parent1 === parent2 && parent2 === parent3) {
                    // Found the button container!
                    const buttonContainer = parent1;
                    
                    // Check if Query button already exists
                    const existingQuery = Array.from(buttonContainer.children)
                        .find(btn => btn.textContent.trim() === 'Query');
                    
                    if (existingQuery) {
                        console.log('[Query Builder] Query button already exists');
                        return true;
                    }
                    
                    // Create and inject Query button
                    console.log('[Query Builder] Injecting Query button into:', buttonContainer);
                    
                    const queryButton = document.createElement('button');
                    queryButton.className = 'panel-btn';
                    queryButton.textContent = 'Query';
                    queryButton.onclick = function() {
                        if (window.app) {
                            window.app.switchToolchainView('query');
                        }
                    };
                    
                    // Check if we're in query view and mark as active
                    if (window.app && window.app.toolchainView === 'query') {
                        queryButton.classList.add('active');
                    }
                    
                    // CRITICAL: Append to the SAME parent as the other buttons
                    buttonContainer.appendChild(queryButton);
                    console.log('[Query Builder] Query button injected successfully');
                    return true;
                }
            }
        }
        
        console.log('[Query Builder] View switcher buttons not found');
        return false;
    }

    // Try to inject immediately
    function tryInject() {
        if (document.getElementById('tab-toolchain')) {
            console.log('[Query Builder] Attempting injection...');
            injectQueryButton();
        }
    }

    // Set up mutation observer
    const observer = new MutationObserver((mutations) => {
        // Only inject if we're on the toolchain tab
        if (window.app && window.app.activeTab === 'toolchain') {
            injectQueryButton();
        }
    });

    function startObserving() {
        const container = document.getElementById('tab-toolchain');
        if (container) {
            observer.observe(container, {
                childList: true,
                subtree: true
            });
            console.log('[Query Builder] Observer started');
            
            // Try immediate injection with delays
            setTimeout(tryInject, 100);
            setTimeout(tryInject, 500);
            setTimeout(tryInject, 1000);
        } else {
            console.log('[Query Builder] Container not found, retrying...');
            setTimeout(startObserving, 100);
        }
    }

    // ============================================================
    // Extend VeraChat Prototype
    // ============================================================
    
    if (typeof VeraChat === 'undefined' || !VeraChat.prototype) {
        console.error('[Query Builder] VeraChat not found!');
        return;
    }

    // Initialize query builder state
    VeraChat.prototype.initQueryBuilder = function() {
        if (!this.queryBuilder) {
            this.queryBuilder = {
                selectedStrategy: 'static',
                selectedTemplate: null,
                templateParams: {},
                customSteps: [],
                queryHistory: [],
                executing: false,
                currentExecution: null
            };
        }
    };

    // Override switchToolchainView to include 'query' option
    const originalSwitchToolchainView = VeraChat.prototype.switchToolchainView;
    VeraChat.prototype.switchToolchainView = function(view) {
        console.log('[Query Builder] Switching to view:', view);
        
        if (view === 'query') {
            this.initQueryBuilder();
            this.toolchainView = 'query';
            this.renderQueryBuilderView();
        } else if (originalSwitchToolchainView) {
            originalSwitchToolchainView.call(this, view);
        } else {
            this.toolchainView = view;
            if (typeof this.updateToolchainUI === 'function') {
                this.updateToolchainUI();
            }
        }
        
        // Try to inject button after view switch
        setTimeout(injectQueryButton, 100);
    };

    // ============================================================
    // Main Query Builder UI (keeping all your fixed code)
    // ============================================================
    
    VeraChat.prototype.renderQueryBuilderView = async function() {
        console.log('[Query Builder] Rendering query view');
        
        const container = document.getElementById('tab-toolchain');
        if (!container || this.activeTab !== 'toolchain') return;
        
        await this.loadAvailableTools();
        
        const qb = this.queryBuilder;
        
        let html = `
            <div style="padding: 20px; overflow-y: auto; height: 100%;">
                <!-- Header -->
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                    <h2 style="margin: 0; color: #60a5fa;">Toolchain Query Builder</h2>
                    <div style="display: flex; gap: 8px;">
                        <button class="panel-btn" onclick="app.switchToolchainView('tools')">Tools</button>
                        <button class="panel-btn" onclick="app.switchToolchainView('executions')">Executions</button>
                        <button class="panel-btn" onclick="app.switchToolchainView('history')">History</button>
                        <button class="panel-btn active" onclick="app.switchToolchainView('query')">Query</button>
                    </div>
                </div>

                <!-- Main Content -->
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px;">
                    <div>
                        ${this.renderStrategySelector()}
                        ${this.renderTemplateSelector()}
                    </div>
                    <div>
                        ${qb.selectedTemplate ? this.renderTemplateParams() : this.renderQuickStart()}
                    </div>
                </div>

                ${qb.selectedTemplate === 'custom' ? this.renderCustomToolchainBuilder() : ''}
                ${this.renderExecutionControls()}
                ${qb.currentExecution ? this.renderCurrentQueryExecution() : ''}
                ${qb.queryHistory.length > 0 ? this.renderQueryHistory() : ''}
            </div>
        `;
        
        container.innerHTML = html;
        
        setTimeout(() => {
            this.setupQueryBuilderListeners();
        }, 0);
    };

    // All your existing rendering methods stay the same...
    VeraChat.prototype.renderStrategySelector = function() {
        const qb = this.queryBuilder;
        
        let html = `
            <div class="tool-container" style="border-radius: 8px; padding: 16px; margin-bottom: 16px;">
                <h3 style="color: #60a5fa; margin: 0 0 12px 0; font-size: 16px;">Planning Strategy</h3>
                <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px;">
        `;
        
        Object.values(PLANNING_STRATEGIES).forEach(strategy => {
            const isSelected = qb.selectedStrategy === strategy.id;
            html += `
                <button 
                    class="panel-btn ${isSelected ? 'active' : ''}"
                    onclick="app.selectPlanningStrategy('${strategy.id}')"
                    style="display: flex; flex-direction: column; align-items: start; padding: 12px; text-align: left; border-left: 3px solid ${strategy.color}; ${isSelected ? `background: ${strategy.color}20;` : ''}">
                    <div style="font-size: 20px; margin-bottom: 4px;">${strategy.icon}</div>
                    <div style="font-weight: 600; margin-bottom: 4px; font-size: 13px;">${strategy.name}</div>
                    <div style="color: #94a3b8; font-size: 11px; line-height: 1.3;">${strategy.description}</div>
                </button>
            `;
        });
        
        html += `</div></div>`;
        return html;
    };

    VeraChat.prototype.renderTemplateSelector = function() {
        const qb = this.queryBuilder;
        
        const categories = {};
        PLAN_TEMPLATES.forEach(template => {
            if (!categories[template.category]) {
                categories[template.category] = [];
            }
            categories[template.category].push(template);
        });
        
        let html = `
            <div class="tool-container" style="border-radius: 8px; padding: 16px;">
                <h3 style="color: #60a5fa; margin: 0 0 12px 0; font-size: 16px;">Plan Templates</h3>
        `;
        
        Object.entries(categories).forEach(([category, templates]) => {
            html += `
                <div style="margin-bottom: 16px;">
                    <div style="color: #94a3b8; font-size: 11px; text-transform: uppercase; font-weight: 600; margin-bottom: 8px; letter-spacing: 0.5px;">
                        ${category}
                    </div>
                    <div style="display: flex; flex-direction: column; gap: 6px;">
            `;
            
            templates.forEach(template => {
                const isSelected = qb.selectedTemplate === template.id;
                html += `
                    <button 
                        class="panel-btn ${isSelected ? 'active' : ''}"
                        onclick="app.selectPlanTemplate('${template.id}')"
                        style="display: flex; align-items: start; gap: 10px; padding: 10px; text-align: left; ${isSelected ? 'border-left: 3px solid #8b5cf6;' : ''}">
                        <div style="font-size: 20px; margin-top: 2px;">${template.icon}</div>
                        <div style="flex: 1;">
                            <div style="font-weight: 600; margin-bottom: 2px; font-size: 13px;">${template.name}</div>
                            <div style="color: #94a3b8; font-size: 11px; line-height: 1.3;">${template.description}</div>
                        </div>
                    </button>
                `;
            });
            
            html += `</div></div>`;
        });
        
        html += `</div>`;
        return html;
    };

    VeraChat.prototype.renderQuickStart = function() {
        return `
            <div class="tool-container" style="border-radius: 8px; padding: 20px; text-align: center; height: 100%; display: flex; flex-direction: column; justify-content: center;">
                <div style="font-size: 48px; margin-bottom: 16px; opacity: 0.5;">🎯</div>
                <h3 style="color: #60a5fa; margin-bottom: 8px;">Quick Start</h3>
                <p style="color: #94a3b8; font-size: 13px; line-height: 1.6; margin-bottom: 16px;">
                    Select a planning strategy and a template to get started.
                </p>
                <div style="color: #64748b; font-size: 11px; line-height: 1.8; text-align: left; background: #0f172a; padding: 12px; border-radius: 6px;">
                    <strong style="color: #60a5fa;">💡 Tips:</strong><br>
                    • <strong>Direct Prompt:</strong> Just describe what you want<br>
                    • <strong>Quick:</strong> Fast execution for simple tasks<br>
                    • <strong>Comprehensive:</strong> Thorough multi-step plans<br>
                    • <strong>Custom:</strong> Build step-by-step manually
                </div>
            </div>
        `;
    };

    VeraChat.prototype.renderTemplateParams = function() {
        const qb = this.queryBuilder;
        const template = PLAN_TEMPLATES.find(t => t.id === qb.selectedTemplate);
        
        if (!template) return '';
        
        if (template.id === 'custom') {
            return `
                <div class="tool-container" style="border-radius: 8px; padding: 16px;">
                    <h3 style="color: #60a5fa; margin: 0 0 12px 0; font-size: 16px;">🛠️ Custom Toolchain</h3>
                    <p style="color: #94a3b8; font-size: 12px; margin-bottom: 12px;">
                        Build your own multi-step toolchain below. Add steps, configure tools, and chain them together.
                    </p>
                    <button class="panel-btn" onclick="app.addCustomStep()" style="width: 100%;">
                        ➕ Add First Step
                    </button>
                </div>
            `;
        }
        
        let html = `
            <div class="tool-container" style="border-radius: 8px; padding: 16px;">
                <h3 style="color: #60a5fa; margin: 0 0 12px 0; font-size: 16px;">
                    ${template.icon} ${template.name}
                </h3>
                <p style="color: #94a3b8; font-size: 12px; margin-bottom: 16px;">
                    ${template.description}
                </p>
        `;
        
        if (template.params && template.params.length > 0) {
            html += '<div style="display: flex; flex-direction: column; gap: 12px;">';
            
            template.params.forEach(param => {
                const value = qb.templateParams[param.name] || param.default || '';
                const isRequired = param.required ? '<span style="color: #ef4444;">*</span>' : '';
                
                html += `
                    <div>
                        <label style="display: block; color: #94a3b8; font-size: 12px; margin-bottom: 4px;">
                            ${param.label}${isRequired}
                        </label>
                `;
                
                if (param.type === 'textarea') {
                    html += `
                        <textarea 
                            id="param-${param.name}"
                            placeholder="${param.placeholder || param.label}"
                            style="width: 100%; min-height: 80px; padding: 8px; color: #e2e8f0; border: 1px solid #334155; border-radius: 4px; font-size: 12px; resize: vertical;"
                        >${this.escapeHtml(value)}</textarea>
                    `;
                } else if (param.type === 'select') {
                    html += `
                        <select 
                            id="param-${param.name}"
                            style="width: 100%; padding: 8px; color: #e2e8f0; border: 1px solid #334155; border-radius: 4px; font-size: 12px;">
                            ${param.options.map(opt => `
                                <option value="${opt}" ${opt === value ? 'selected' : ''}>${opt}</option>
                            `).join('')}
                        </select>
                    `;
                } else {
                    html += `
                        <input 
                            type="text"
                            id="param-${param.name}"
                            placeholder="${param.placeholder || param.label}"
                            value="${this.escapeHtml(value)}"
                            style="width: 100%; padding: 8px; color: #e2e8f0; border: 1px solid #334155; border-radius: 4px; font-size: 12px;">
                    `;
                }
                
                html += `</div>`;
            });
            
            html += '</div>';
        }
        
        html += `</div>`;
        return html;
    };

    VeraChat.prototype.renderCustomToolchainBuilder = function() {
        const qb = this.queryBuilder;
        
        let html = `
            <div class="tool-container" style="border-radius: 8px; padding: 16px; margin-bottom: 16px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                    <h3 style="color: #60a5fa; margin: 0; font-size: 16px;">Build Your Toolchain</h3>
                    <button class="panel-btn" onclick="app.addCustomStep()" style="font-size: 12px;">
                        ➕ Add Step
                    </button>
                </div>
        `;
        
        if (qb.customSteps.length === 0) {
            html += `
                <div style="text-align: center; padding: 40px; color: #64748b; font-size: 12px;">
                    <div style="font-size: 32px; margin-bottom: 8px; opacity: 0.5;">🔨</div>
                    Click "Add Step" to start building your custom toolchain
                </div>
            `;
        } else {
            html += '<div style="display: flex; flex-direction: column; gap: 8px;">';
            
            qb.customSteps.forEach((step, index) => {
                html += `
                    <div class="tool-card" style="border-radius: 6px; padding: 12px; border-left: 3px solid #8b5cf6;">
                        <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 8px;">
                            <div style="flex: 1;">
                                <div style="color: #a78bfa; font-size: 11px; margin-bottom: 4px;">Step ${index + 1}</div>
                                <select 
                                    id="custom-step-tool-${index}"
                                    onchange="app.updateCustomStepTool(${index}, this.value)"
                                    style="width: 100%; padding: 6px; color: #e2e8f0; border: 1px solid #334155; border-radius: 4px; font-size: 12px; margin-bottom: 8px;">
                                    <option value="">Select tool...</option>
                                    ${this.renderToolOptions(step.tool)}
                                </select>
                            </div>
                            <button 
                                onclick="app.removeCustomStep(${index})"
                                style="background: none; border: none; color: #ef4444; cursor: pointer; padding: 4px 8px; font-size: 14px; margin-left: 8px;"
                                title="Remove step">✕</button>
                        </div>
                        <textarea 
                            id="custom-step-input-${index}"
                            placeholder="Tool input (use {prev} for previous result, {step_N} for specific step)"
                            onchange="app.updateCustomStepInput(${index}, this.value)"
                            style="width: 100%; min-height: 60px; padding: 8px; color: #e2e8f0; border: 1px solid #334155; border-radius: 4px; font-size: 11px; font-family: monospace; resize: vertical;"
                        >${this.escapeHtml(step.input || '')}</textarea>
                    </div>
                `;
            });
            
            html += '</div>';
            
            html += `
                <div style="display: flex; gap: 8px; margin-top: 12px;">
                    <button class="panel-btn" onclick="app.saveCustomToolchain()" style="flex: 1; font-size: 12px;">
                        💾 Save
                    </button>
                    <button class="panel-btn" onclick="app.loadCustomToolchain()" style="flex: 1; font-size: 12px; background: #334155;">
                        📂 Load
                    </button>
                    <button class="panel-btn" onclick="app.clearCustomSteps()" style="background: #64748b; font-size: 12px;">
                        🗑️ Clear
                    </button>
                </div>
            `;
        }
        
        html += `</div>`;
        return html;
    };

    VeraChat.prototype.renderToolOptions = function(selectedTool) {
        if (!this.availableTools) return '';
        
        return Object.values(this.availableTools)
            .map(tool => `<option value="${this.escapeHtml(tool.name)}" ${tool.name === selectedTool ? 'selected' : ''}>${this.escapeHtml(tool.name)}</option>`)
            .join('');
    };

    VeraChat.prototype.renderExecutionControls = function() {
        const qb = this.queryBuilder;
        const canExecute = qb.selectedTemplate && !qb.executing;
        
        return `
            <div class="tool-container" style="border-radius: 8px; padding: 16px; margin-bottom: 16px; border: 2px solid #8b5cf6;">
                <div style="display: flex; gap: 12px; align-items: center;">
                    <button 
                        class="panel-btn"
                        onclick="app.executeQueryBuilder()"
                        style="flex: 1; padding: 14px; font-size: 14px; font-weight: 600; background: linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%); ${!canExecute ? 'opacity: 0.5; cursor: not-allowed;' : ''}"
                        ${!canExecute ? 'disabled' : ''}>
                        ${qb.executing ? '⏳ Executing...' : '🚀 Execute Toolchain'}
                    </button>
                    <button 
                        class="panel-btn"
                        onclick="app.previewQueryPlan()"
                        style="padding: 14px; background: #334155; ${!qb.selectedTemplate || qb.executing ? 'opacity: 0.5;' : ''}"
                        ${!qb.selectedTemplate || qb.executing ? 'disabled' : ''}>
                        👁️ Preview Plan
                    </button>
                </div>
                ${qb.selectedTemplate ? `
                    <div style="margin-top: 12px; padding: 12px; background: #0f172a; border-radius: 6px; border-left: 3px solid #8b5cf6;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <div style="color: #a78bfa; font-size: 11px; margin-bottom: 2px;">Ready to execute:</div>
                                <div style="color: #e2e8f0; font-size: 13px; font-weight: 600;">
                                    ${PLANNING_STRATEGIES[qb.selectedStrategy.toUpperCase()].name} + 
                                    ${PLAN_TEMPLATES.find(t => t.id === qb.selectedTemplate)?.name}
                                </div>
                            </div>
                            <div style="color: #64748b; font-size: 11px;">
                                Session: ${this.sessionId ? this.sessionId.substring(0, 8) + '...' : 'N/A'}
                            </div>
                        </div>
                    </div>
                ` : ''}
            </div>
        `;
    };

    VeraChat.prototype.renderCurrentQueryExecution = function() {
        const exec = this.queryBuilder.currentExecution;
        if (!exec) return '';
        
        return `
            <div class="tool-container" style="border-radius: 8px; padding: 16px; margin-bottom: 16px; border-left: 4px solid #10b981;">
                <h3 style="color: #10b981; margin: 0 0 12px 0; font-size: 16px;">⚡ Executing...</h3>
                <div class="tool-card" style="padding: 12px; border-radius: 6px;">
                    <div style="color: #94a3b8; font-size: 12px; margin-bottom: 8px;">
                        Strategy: <strong style="color: #e2e8f0;">${exec.strategy}</strong> | 
                        Template: <strong style="color: #e2e8f0;">${exec.template}</strong>
                    </div>
                    ${exec.plan ? `
                        <div style="color: #94a3b8; font-size: 12px; margin-bottom: 8px;">
                            Steps: ${exec.completed || 0} / ${exec.total || 0}
                        </div>
                    ` : ''}
                    <div style="background: #0f172a; border-radius: 4px; padding: 10px; max-height: 300px; overflow-y: auto;">
                        <div id="query-execution-output" style="color: #cbd5e1; font-size: 11px; font-family: monospace; white-space: pre-wrap;">
                            ${this.escapeHtml(exec.output || 'Starting execution...')}
                        </div>
                    </div>
                </div>
            </div>
        `;
    };

    VeraChat.prototype.renderQueryHistory = function() {
        const qb = this.queryBuilder;
        
        return `
            <div class="tool-container" style="border-radius: 8px; padding: 16px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                    <h3 style="color: #60a5fa; margin: 0; font-size: 16px;">Query History</h3>
                    <button class="panel-btn" onclick="app.clearQueryHistory()" style="font-size: 11px; background: #64748b;">
                        Clear History
                    </button>
                </div>
                <div style="display: flex; flex-direction: column; gap: 8px; max-height: 300px; overflow-y: auto;">
                    ${qb.queryHistory.slice(-10).reverse().map((item, index) => `
                        <div class="tool-card" style="padding: 10px; border-radius: 6px; cursor: pointer;" onclick="app.loadQueryFromHistory(${qb.queryHistory.length - 1 - index})">
                            <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                                <div style="color: #e2e8f0; font-size: 12px; font-weight: 600;">
                                    ${PLANNING_STRATEGIES[item.strategy.toUpperCase()]?.name || item.strategy} + 
                                    ${PLAN_TEMPLATES.find(t => t.id === item.template)?.name || item.template}
                                </div>
                                <div style="color: #64748b; font-size: 10px;">
                                    ${new Date(item.timestamp).toLocaleTimeString()}
                                </div>
                            </div>
                            ${item.params && Object.keys(item.params).length > 0 ? `
                                <div style="color: #94a3b8; font-size: 11px;">
                                    ${Object.entries(item.params).slice(0, 2).map(([k, v]) => `${k}: ${String(v).substring(0, 30)}...`).join(' | ')}
                                </div>
                            ` : ''}
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    };

    // Action Handlers
    VeraChat.prototype.selectPlanningStrategy = function(strategyId) {
        this.queryBuilder.selectedStrategy = strategyId;
        this.renderQueryBuilderView();
    };

    VeraChat.prototype.selectPlanTemplate = function(templateId) {
        this.queryBuilder.selectedTemplate = templateId;
        this.queryBuilder.templateParams = {};
        if (templateId !== 'custom') {
            this.queryBuilder.customSteps = [];
        }
        this.renderQueryBuilderView();
    };

    VeraChat.prototype.addCustomStep = function() {
        this.queryBuilder.customSteps.push({ tool: '', input: '' });
        this.renderQueryBuilderView();
    };

    VeraChat.prototype.removeCustomStep = function(index) {
        this.queryBuilder.customSteps.splice(index, 1);
        this.renderQueryBuilderView();
    };

    VeraChat.prototype.updateCustomStepTool = function(index, toolName) {
        if (this.queryBuilder.customSteps[index]) {
            this.queryBuilder.customSteps[index].tool = toolName;
        }
    };

    VeraChat.prototype.updateCustomStepInput = function(index, input) {
        if (this.queryBuilder.customSteps[index]) {
            this.queryBuilder.customSteps[index].input = input;
        }
    };

    VeraChat.prototype.clearCustomSteps = function() {
        if (confirm('Clear all custom steps?')) {
            this.queryBuilder.customSteps = [];
            this.renderQueryBuilderView();
        }
    };

    VeraChat.prototype.saveCustomToolchain = function() {
        const qb = this.queryBuilder;
        const name = prompt('Enter a name for this toolchain:');
        if (!name) return;
        
        const toolchain = {
            name: name,
            strategy: qb.selectedStrategy,
            steps: qb.customSteps,
            timestamp: new Date().toISOString()
        };
        
        const saved = JSON.parse(localStorage.getItem('vera_saved_toolchains') || '[]');
        saved.push(toolchain);
        localStorage.setItem('vera_saved_toolchains', JSON.stringify(saved));
        
        alert(`Toolchain "${name}" saved successfully!`);
    };

    VeraChat.prototype.loadCustomToolchain = function() {
        const saved = JSON.parse(localStorage.getItem('vera_saved_toolchains') || '[]');
        
        if (saved.length === 0) {
            alert('No saved toolchains found');
            return;
        }
        
        const options = saved.map((tc, i) => `${i + 1}. ${tc.name} (${tc.steps.length} steps)`).join('\n');
        const selection = prompt(`Select a toolchain to load:\n\n${options}\n\nEnter number:`);
        
        if (!selection) return;
        
        const index = parseInt(selection) - 1;
        if (index >= 0 && index < saved.length) {
            const toolchain = saved[index];
            this.queryBuilder.selectedStrategy = toolchain.strategy;
            this.queryBuilder.selectedTemplate = 'custom';
            this.queryBuilder.customSteps = toolchain.steps;
            this.renderQueryBuilderView();
        }
    };

    // Execution & Preview (keeping your working versions)
    VeraChat.prototype.executeQueryBuilder = async function() {
        const qb = this.queryBuilder;
        
        if (!qb.selectedTemplate || qb.executing) return;
        
        const template = PLAN_TEMPLATES.find(t => t.id === qb.selectedTemplate);
        const params = {};
        
        if (template.id === 'custom') {
            if (qb.customSteps.length === 0) {
                alert('Please add at least one step to your custom toolchain');
                return;
            }
            
            for (let i = 0; i < qb.customSteps.length; i++) {
                const step = qb.customSteps[i];
                if (!step.tool) {
                    alert(`Step ${i + 1}: Please select a tool`);
                    return;
                }
                if (!step.input) {
                    alert(`Step ${i + 1}: Please provide input`);
                    return;
                }
            }
            
            params.custom_plan = qb.customSteps;
        } else {
            if (template.params) {
                for (const param of template.params) {
                    const element = document.getElementById(`param-${param.name}`);
                    if (element) {
                        const value = element.value.trim();
                        
                        if (param.required && !value) {
                            alert(`Required field missing: ${param.label}`);
                            element.focus();
                            return;
                        }
                        
                        params[param.name] = value;
                        qb.templateParams[param.name] = value;
                    }
                }
            }
        }
        
        qb.queryHistory.push({
            strategy: qb.selectedStrategy,
            template: qb.selectedTemplate,
            params: {...params},
            timestamp: new Date().toISOString()
        });
        
        qb.executing = true;
        qb.currentExecution = {
            strategy: qb.selectedStrategy,
            template: qb.selectedTemplate,
            params: params,
            output: '',
            plan: null,
            completed: 0,
            total: 0
        };
        
        this.renderQueryBuilderView();
        
        try {
            const response = await fetch(`http://llm.int:8888/api/toolchain/query/execute`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    session_id: this.sessionId,
                    strategy: qb.selectedStrategy,
                    template: qb.selectedTemplate,
                    params: params
                })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            
            while (true) {
                const {done, value} = await reader.read();
                if (done) break;
                
                const chunk = decoder.decode(value);
                qb.currentExecution.output += chunk;
                
                const outputElement = document.getElementById('query-execution-output');
                if (outputElement) {
                    outputElement.textContent = qb.currentExecution.output;
                    outputElement.scrollTop = outputElement.scrollHeight;
                }
            }
            
            setTimeout(() => {
                qb.executing = false;
                qb.currentExecution = null;
                this.renderQueryBuilderView();
                alert('✅ Toolchain execution completed!\n\nCheck the Executions tab for full details.');
                this.switchToolchainView('executions');
            }, 1000);
            
        } catch (error) {
            console.error('[Execute] Error:', error);
            qb.executing = false;
            if (qb.currentExecution) {
                qb.currentExecution.output += `\n\nError: ${error.message}`;
            }
            this.renderQueryBuilderView();
            alert('Execution failed: ' + error.message);
        }
    };

    VeraChat.prototype.previewQueryPlan = async function() {
        const qb = this.queryBuilder;
        
        if (!qb.selectedTemplate) return;
        
        const template = PLAN_TEMPLATES.find(t => t.id === qb.selectedTemplate);
        const params = {};
        
        if (template.id === 'custom') {
            if (qb.customSteps.length === 0) {
                alert('Please add at least one step to preview');
                return;
            }
            params.custom_plan = qb.customSteps;
        } else if (template.params) {
            for (const param of template.params) {
                const element = document.getElementById(`param-${param.name}`);
                if (element) {
                    params[param.name] = element.value.trim();
                }
            }
        }
        
        try {
            const response = await fetch(`http://llm.int:8888/api/toolchain/query/preview`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    session_id: this.sessionId,
                    strategy: qb.selectedStrategy,
                    template: qb.selectedTemplate,
                    params: params
                })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            const planPreview = JSON.stringify(data.plan, null, 2);
            
            const modal = document.createElement('div');
            modal.style.cssText = `
                position: fixed; top: 0; left: 0; right: 0; bottom: 0;
                background: rgba(0, 0, 0, 0.8); display: flex;
                align-items: center; justify-content: center; z-index: 10000;
            `;
            
            modal.innerHTML = `
                <div style="background: #1e293b; border-radius: 8px; padding: 24px; max-width: 800px; max-height: 80vh; overflow-y: auto; border: 2px solid #8b5cf6;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                        <h3 style="color: #60a5fa; margin: 0;">👁️ Plan Preview</h3>
                        <button onclick="this.closest('div[style*=\"position: fixed\"]').remove()" 
                                style="background: none; border: none; color: #94a3b8; cursor: pointer; font-size: 20px;">✕</button>
                    </div>
                    <div style="background: #0f172a; border-radius: 6px; padding: 16px; border-left: 3px solid #8b5cf6; margin-bottom: 16px;">
                        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; color: #94a3b8; font-size: 12px;">
                            <div><strong style="color: #60a5fa;">Strategy:</strong> ${data.strategy}</div>
                            <div><strong style="color: #60a5fa;">Template:</strong> ${data.template}</div>
                            <div><strong style="color: #60a5fa;">Total Steps:</strong> ${data.estimated_steps}</div>
                            <div><strong style="color: #60a5fa;">Mode:</strong> ${data.template === 'custom' ? 'Custom' : 'Template'}</div>
                        </div>
                    </div>
                    <div style="background: #0f172a; border-radius: 6px; padding: 16px; border-left: 3px solid #10b981;">
                        <div style="color: #10b981; font-size: 12px; font-weight: 600; margin-bottom: 8px;">Execution Plan:</div>
                        <pre style="color: #cbd5e1; font-size: 11px; margin: 0; white-space: pre-wrap; word-break: break-word; max-height: 400px; overflow-y: auto;">${this.escapeHtml(planPreview)}</pre>
                    </div>
                    <div style="margin-top: 16px; display: flex; justify-content: space-between; align-items: center; gap: 12px;">
                        <div style="color: #94a3b8; font-size: 12px;">
                            This plan will be executed when you click "Execute Toolchain"
                        </div>
                        <button class="panel-btn" onclick="this.closest('div[style*=\"position: fixed\"]').remove()">
                            Close
                        </button>
                    </div>
                </div>
            `;
            
            document.body.appendChild(modal);
            
        } catch (error) {
            console.error('Preview error:', error);
            alert('Failed to generate preview: ' + error.message);
        }
    };

    VeraChat.prototype.loadQueryFromHistory = function(index) {
        const item = this.queryBuilder.queryHistory[index];
        if (!item) return;
        
        this.queryBuilder.selectedStrategy = item.strategy;
        this.queryBuilder.selectedTemplate = item.template;
        this.queryBuilder.templateParams = {...item.params};
        
        this.renderQueryBuilderView();
        
        setTimeout(() => {
            Object.entries(item.params).forEach(([key, value]) => {
                const element = document.getElementById(`param-${key}`);
                if (element) {
                    element.value = value;
                }
            });
        }, 100);
    };

    VeraChat.prototype.clearQueryHistory = function() {
        if (confirm('Clear all query history?')) {
            this.queryBuilder.queryHistory = [];
            this.renderQueryBuilderView();
        }
    };

    VeraChat.prototype.setupQueryBuilderListeners = function() {
        const template = PLAN_TEMPLATES.find(t => t.id === this.queryBuilder.selectedTemplate);
        if (template && template.params) {
            template.params.forEach(param => {
                const element = document.getElementById(`param-${param.name}`);
                if (element) {
                    element.addEventListener('change', () => {
                        this.queryBuilder.templateParams[param.name] = element.value;
                    });
                }
            });
        }
    };

    // Start Everything
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', startObserving);
    } else {
        startObserving();
    }

    // Manual trigger
    window.injectQueryButtonManual = function() {
        console.log('[Query Builder] Manual injection triggered');
        injectQueryButton();
    };

    console.log('[Toolchain Query Builder] Perfect button placement version loaded');
    console.log('[Query Builder] Button will appear inline with Tools, Executions, History');
})();