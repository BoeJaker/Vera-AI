(() => {
 VeraChat.prototype.showBackgroundControlPanel = function() {
        const modal = document.createElement('div');
        modal.id = 'backgroundControlModal';
        modal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.7);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 10000;
            backdrop-filter: blur(4px);
        `;
        
        const content = document.createElement('div');
        content.style.cssText = `
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            border-radius: 12px;
            padding: 24px;
            max-width: 600px;
            width: 90%;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
            border: 1px solid #334155;
        `;
        
        content.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                <h2 style="margin: 0; color: #e2e8f0;">⚙️ Background Thinking Control</h2>
                <button onclick="document.getElementById('backgroundControlModal').remove()" 
                        style="background: transparent; border: none; color: #94a3b8; font-size: 24px; cursor: pointer;">×</button>
            </div>
            
            <div style="margin-bottom: 16px;">
                <label style="color: #cbd5e1; font-size: 14px; font-weight: 600; display: block; margin-bottom: 8px;">
                    Background Mode
                </label>
                <select id="bgMode" style="width: 100%; padding: 8px; background: #0f172a; color: #e2e8f0; border: 1px solid #334155; border-radius: 6px; font-size: 14px;">
                    <option value="off">❌ Off - No background thinking</option>
                    <option value="manual">👆 Manual - Only on trigger</option>
                    <option value="scheduled">📅 Scheduled - Within time window</option>
                    <option value="continuous">♾️ Continuous - Always running</option>
                </select>
            </div>
            
            <div id="intervalSection" style="margin-bottom: 16px;">
                <label style="color: #cbd5e1; font-size: 14px; font-weight: 600; display: block; margin-bottom: 8px;">
                    Interval (seconds)
                </label>
                <input type="number" id="bgInterval" value="600" min="60" step="60"
                       style="width: 100%; padding: 8px; background: #0f172a; color: #e2e8f0; border: 1px solid #334155; border-radius: 6px; font-size: 14px;">
            </div>
            
            <div id="scheduleSection" style="display: none; margin-bottom: 16px; padding: 16px; background: rgba(15, 23, 42, 0.5); border-radius: 8px; border: 1px solid #334155;">
                <h3 style="margin: 0 0 12px 0; color: #cbd5e1; font-size: 14px;">📅 Schedule</h3>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
                    <div>
                        <label style="color: #94a3b8; font-size: 12px; display: block; margin-bottom: 4px;">Start Time</label>
                        <input type="time" id="bgStartTime" value="09:00"
                               style="width: 100%; padding: 6px; background: #0f172a; color: #e2e8f0; border: 1px solid #334155; border-radius: 4px;">
                    </div>
                    <div>
                        <label style="color: #94a3b8; font-size: 12px; display: block; margin-bottom: 4px;">End Time</label>
                        <input type="time" id="bgEndTime" value="17:00"
                               style="width: 100%; padding: 6px; background: #0f172a; color: #e2e8f0; border: 1px solid #334155; border-radius: 4px;">
                    </div>
                </div>
            </div>
            
            <div style="display: flex; gap: 8px; margin-top: 20px;">
                <button onclick="app.applyBackgroundConfig()" class="panel-btn" 
                        style="flex: 1; padding: 10px; background: #3b82f6; font-size: 14px; font-weight: 600;">
                    ✓ Apply Settings
                </button>
                <button onclick="document.getElementById('backgroundControlModal').remove()" class="panel-btn"
                        style="padding: 10px; font-size: 14px;">
                    Cancel
                </button>
            </div>
        `;
        
        modal.appendChild(content);
        document.body.appendChild(modal);
        
        // Show/hide schedule section based on mode
        const modeSelect = document.getElementById('bgMode');
        const scheduleSection = document.getElementById('scheduleSection');
        const intervalSection = document.getElementById('intervalSection');
        
        modeSelect.addEventListener('change', (e) => {
            const mode = e.target.value;
            scheduleSection.style.display = mode === 'scheduled' ? 'block' : 'none';
            intervalSection.style.display = mode === 'off' ? 'none' : 'block';
        });
        
        // Load current settings
        this.loadBackgroundStatus();
    };
    
    VeraChat.prototype.loadBackgroundStatus = async function() {
        if (!this.sessionId) return;
        
        try {
            const response = await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/background/status`);
            const data = await response.json();
            
            const modeSelect = document.getElementById('bgMode');
            const intervalInput = document.getElementById('bgInterval');
            const startTimeInput = document.getElementById('bgStartTime');
            const endTimeInput = document.getElementById('bgEndTime');
            
            if (modeSelect) modeSelect.value = data.mode;
            if (intervalInput) intervalInput.value = data.interval;
            if (startTimeInput && data.schedule.start_time) {
                startTimeInput.value = data.schedule.start_time;
            }
            if (endTimeInput && data.schedule.end_time) {
                endTimeInput.value = data.schedule.end_time;
            }
            
            // Trigger change event to show/hide schedule section
            if (modeSelect) modeSelect.dispatchEvent(new Event('change'));
            
        } catch (error) {
            console.error('Failed to load background status:', error);
        }
    };
    
    VeraChat.prototype.applyBackgroundConfig = async function() {
        if (!this.sessionId) return;
        
        const mode = document.getElementById('bgMode').value;
        const interval = parseInt(document.getElementById('bgInterval').value);
        const startTime = document.getElementById('bgStartTime').value;
        const endTime = document.getElementById('bgEndTime').value;
        
        try {
            const response = await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/background/config`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    mode: mode,
                    interval: interval,
                    start_time: mode === 'scheduled' ? startTime : null,
                    end_time: mode === 'scheduled' ? endTime : null
                })
            });
            
            const data = await response.json();
            
            this.addSystemMessage(`✓ Background mode set to: ${mode}`);
            document.getElementById('backgroundControlModal').remove();
            
            // Refresh focus UI
            this.loadFocusStatus();
            
        } catch (error) {
            console.error('Failed to apply background config:', error);
            this.addSystemMessage('Error applying background config');
        }
    };
    
    VeraChat.prototype.pauseBackground = async function() {
        if (!this.sessionId) return;
        
        try {
            await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/background/pause`, {
                method: 'POST'
            });
            this.addSystemMessage('⏸️ Background thinking paused');
        } catch (error) {
            console.error('Failed to pause background:', error);
        }
    };
    
    VeraChat.prototype.resumeBackground = async function() {
        if (!this.sessionId) return;
        
        try{
            await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/background/resume`, {
                method: 'POST'
            });
            this.addSystemMessage('▶️ Background thinking resumed');
        } catch (error) {
            console.error('Failed to resume background:', error);
        }
    };
    
    // ============================================================
    // ENTITY REFERENCE UI
    // ============================================================
    
    VeraChat.prototype.showEntityExplorer = async function() {
        if (!this.sessionId) return;
        
        // Fetch related entities
        try {
            const response = await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/entities/discover`);
            const data = await response.json();
            
            this.displayEntityExplorerModal(data.entities);
            
        } catch (error) {
            console.error('Failed to discover entities:', error);
            this.addSystemMessage('Error discovering entities');
        }
    };
    
    VeraChat.prototype.displayEntityExplorerModal = function(entities) {
        const modal = document.createElement('div');
        modal.id = 'entityExplorerModal';
        modal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.7);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 10000;
            backdrop-filter: blur(4px);
        `;
        
        const content = document.createElement('div');
        content.style.cssText = `
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            border-radius: 12px;
            padding: 24px;
            max-width: 800px;
            width: 90%;
            max-height: 80vh;
            overflow-y: auto;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
            border: 1px solid #334155;
        `;
        
        let html = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                <h2 style="margin: 0; color: #e2e8f0;">🔗 Related Entities</h2>
                <button onclick="document.getElementById('entityExplorerModal').remove()" 
                        style="background: transparent; border: none; color: #94a3b8; font-size: 24px; cursor: pointer;">×</button>
            </div>
        `;
        
        const entityTypes = {
            'sessions': { icon: '💬', color: '#3b82f6', label: 'Sessions' },
            'notebooks': { icon: '📓', color: '#8b5cf6', label: 'Notebooks' },
            'folders': { icon: '📁', color: '#f59e0b', label: 'Folders' },
            'documents': { icon: '📄', color: '#10b981', label: 'Documents' },
            'entities': { icon: '🔷', color: '#ec4899', label: 'Other Entities' }
        };
        
        for (const [type, config] of Object.entries(entityTypes)) {
            const items = entities[type] || [];
            
            if (items.length === 0) continue;
            
            html += `
                <div style="margin-bottom: 24px;">
                    <h3 style="color: ${config.color}; font-size: 16px; margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">
                        <span>${config.icon}</span>
                        <span>${config.label} (${items.length})</span>
                    </h3>
                    <div style="display: flex; flex-direction: column; gap: 8px;">
            `;
            
            items.forEach((entity, idx) => {
                html += `
                    <div style="background: rgba(15, 23, 42, 0.5); border-left: 3px solid ${config.color}; padding: 12px; border-radius: 6px;">
                        <div style="display: flex; justify-content: space-between; align-items: start;">
                            <div style="flex: 1;">
                                <div style="color: #e2e8f0; font-weight: 600; font-size: 14px; margin-bottom: 4px;">
                                    ${this.escapeHtml(entity.name)}
                                </div>
                                <div style="color: #64748b; font-size: 11px;">
                                    ID: ${this.escapeHtml(entity.entity_id)}
                                </div>
                                ${entity.content_summary ? `
                                    <div style="color: #94a3b8; font-size: 12px; margin-top: 8px; padding: 8px; background: rgba(0, 0, 0, 0.3); border-radius: 4px;">
                                        ${this.escapeHtml(entity.content_summary)}
                                    </div>
                                ` : ''}
                            </div>
                            <button onclick="app.viewEntityContent('${this.escapeHtml(entity.entity_id)}')" class="panel-btn"
                                    style="font-size: 11px; padding: 4px 8px; margin-left: 8px;">
                                👁️ View
                            </button>
                        </div>
                    </div>
                `;
            });
            
            html += `
                    </div>
                </div>
            `;
        }
        
        if (Object.values(entities).every(arr => arr.length === 0)) {
            html += `
                <div style="text-align: center; padding: 40px; color: #64748b;">
                    <div style="font-size: 48px; margin-bottom: 16px;">🔍</div>
                    <div>No related entities found</div>
                </div>
            `;
        }
        
        content.innerHTML = html;
        modal.appendChild(content);
        document.body.appendChild(modal);
    };
    
    VeraChat.prototype.viewEntityContent = async function(entityId) {
        if (!this.sessionId) return;
        
        try {
            const response = await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/entities/${entityId}/content?max_length=1000`);
            const data = await response.json();
            
            const contentModal = document.createElement('div');
            contentModal.style.cssText = `
                position: fixed;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                background: #1e293b;
                border-radius: 12px;
                padding: 24px;
                max-width: 700px;
                width: 90%;
                max-height: 70vh;
                overflow-y: auto;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
                border: 1px solid #334155;
                z-index: 10001;
            `;
            
            contentModal.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                    <h3 style="margin: 0; color: #e2e8f0; font-size: 16px;">${this.escapeHtml(data.name)}</h3>
                    <button onclick="this.parentElement.parentElement.remove()" class="panel-btn" style="font-size: 11px; padding: 4px 8px;">✕</button>
                </div>
                <div style="color: #64748b; font-size: 12px; margin-bottom: 12px;">
                    Type: ${this.escapeHtml(data.entity_type)} • ID: ${this.escapeHtml(entityId)}
                </div>
                <div style="color: #cbd5e1; font-size: 13px; line-height: 1.6; white-space: pre-wrap; background: rgba(0, 0, 0, 0.3); padding: 16px; border-radius: 8px;">
                    ${data.content ? this.escapeHtml(data.content) : 'No content available'}
                </div>
            `;
            
            document.body.appendChild(contentModal);
            
        } catch (error) {
            console.error('Failed to view entity content:', error);
            this.addSystemMessage('Error loading entity content');
        }
    };
    
    VeraChat.prototype.enrichBoardItem = async function(category, index) {
        if (!this.sessionId) return;
        
        try {
            const response = await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/board/item/enrich`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    category: category,
                    item_index: index,
                    auto_discover: true
                })
            });
            
            const data = await response.json();
            
            this.addSystemMessage(`✓ Enriched ${category} item with ${data.item.entity_refs.length} entity references`);
            this.loadFocusStatus();
            
        } catch (error) {
            console.error('Failed to enrich item:', error);
            this.addSystemMessage('Error enriching item');
        }
    };
    
    // ============================================================
    // TOOL INTEGRATION UI
    // ============================================================
    
    VeraChat.prototype.showToolSuggestions = async function(category, index) {
        if (!this.sessionId) return;
        
        try {
            await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/board/item/suggest-tools`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    category: category,
                    item_index: index
                })
            });
            
            this.addSystemMessage('🔧 Generating tool suggestions...');
            
            // Refresh board after a delay to show suggestions
            setTimeout(() => this.loadFocusStatus(), 3000);
            
        } catch (error) {
            console.error('Failed to suggest tools:', error);
            this.addSystemMessage('Error suggesting tools');
        }
    };
    
    VeraChat.prototype.executeToolForItem = async function(category, index, toolName) {
        if (!this.sessionId) return;
        
        if (!confirm(`Execute tool "${toolName}" for this item?`)) return;
        
        try {
            const response = await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/tools/execute`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    category: category,
                    item_index: index,
                    tool_name: toolName,
                    tool_input: null
                })
            });
            
            const data = await response.json();
            
            this.addSystemMessage(`✓ Executed ${toolName}: ${data.result ? data.result.substring(0, 100) : 'No result'}...`);
            this.loadFocusStatus();
            
        } catch (error) {
            console.error('Failed to execute tool:', error);
            this.addSystemMessage(`Error executing tool: ${error.message}`);
        }
    };
    
    VeraChat.prototype.showToolUsageHistory = async function() {
        if (!this.sessionId) return;
        
        try {
            const response = await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/tools/usage-history?limit=20`);
            const data = await response.json();
            
            const modal = document.createElement('div');
            modal.id = 'toolHistoryModal';
            modal.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0, 0, 0, 0.7);
                display: flex;
                justify-content: center;
                align-items: center;
                z-index: 10000;
                backdrop-filter: blur(4px);
            `;
            
            const content = document.createElement('div');
            content.style.cssText = `
                background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
                border-radius: 12px;
                padding: 24px;
                max-width: 700px;
                width: 90%;
                max-height: 80vh;
                overflow-y: auto;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
                border: 1px solid #334155;
            `;
            
            let html = `
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                    <h2 style="margin: 0; color: #e2e8f0;">🔧 Tool Usage History</h2>
                    <button onclick="document.getElementById('toolHistoryModal').remove()" 
                            style="background: transparent; border: none; color: #94a3b8; font-size: 24px; cursor: pointer;">×</button>
                </div>
            `;
            
            if (data.history.length === 0) {
                html += `
                    <div style="text-align: center; padding: 40px; color: #64748b;">
                        <div style="font-size: 48px; margin-bottom: 16px;">🔧</div>
                        <div>No tool usage history</div>
                    </div>
                `;
            } else {
                html += `<div style="display: flex; flex-direction: column; gap: 12px;">`;
                
                data.history.forEach((entry, idx) => {
                    const statusColor = entry.success ? '#10b981' : '#ef4444';
                    const statusIcon = entry.success ? '✓' : '✕';
                    
                    html += `
                        <div style="background: rgba(15, 23, 42, 0.5); border-left: 3px solid ${statusColor}; padding: 12px; border-radius: 6px;">
                            <div style="display: flex; justify-content: between; align-items: start; margin-bottom: 8px;">
                                <div style="flex: 1;">
                                    <div style="color: #e2e8f0; font-weight: 600; font-size: 13px; margin-bottom: 4px;">
                                        🔧 ${this.escapeHtml(entry.tool)}
                                        <span style="color: ${statusColor}; margin-left: 8px;">${statusIcon}</span>
                                    </div>
                                    <div style="color: #64748b; font-size: 11px;">
                                        ${new Date(entry.timestamp).toLocaleString()}
                                    </div>
                                </div>
                            </div>
                            <div style="color: #94a3b8; font-size: 12px; margin-bottom: 8px;">
                                Item: ${this.escapeHtml(entry.item_note ? entry.item_note.substring(0, 60) : 'N/A')}...
                            </div>
                            ${entry.result_preview ? `
                                <div style="color: #cbd5e1; font-size: 11px; background: rgba(0, 0, 0, 0.3); padding: 8px; border-radius: 4px;">
                                    ${this.escapeHtml(entry.result_preview)}
                                </div>
                            ` : ''}
                            ${entry.error ? `
                                <div style="color: #fca5a5; font-size: 11px; background: rgba(239, 68, 68, 0.1); padding: 8px; border-radius: 4px;">
                                    Error: ${this.escapeHtml(entry.error)}
                                </div>
                            ` : ''}
                        </div>
                    `;
                });
                
                html += `</div>`;
            }
            
            content.innerHTML = html;
            modal.appendChild(content);
            document.body.appendChild(modal);
            
        } catch (error) {
            console.error('Failed to load tool history:', error);
            this.addSystemMessage('Error loading tool history');
        }
    };
    
    // ============================================================
    // ENHANCED ITEM RENDERING
    // ============================================================
    
    VeraChat.prototype.renderEnhancedItem = function(item, idx, category, color) {
        const hasRefs = item.entity_refs && item.entity_refs.length > 0;
        const hasTools = item.tool_suggestions && item.tool_suggestions.length > 0;
        const hasHistory = item.execution_history && item.execution_history.length > 0;
        
        let html = `
            <div id="item-${category}-${idx}" class="draggable-item" draggable="true"
                 data-category="${category}" data-index="${idx}"
                 ondragstart="app.handleDragStart(event)" ondragend="app.handleDragEnd(event)"
                 style="padding: 12px; border-radius: 6px; border-left: 3px solid ${color}; background: rgba(15, 23, 42, 0.5); cursor: move;">
                
                <div style="color: #cbd5e1; font-size: 13px; margin-bottom: 8px;">${this.escapeHtml(item.note)}</div>
                
                ${hasRefs ? `
                    <div style="margin-bottom: 8px;">
                        <div style="color: #8b5cf6; font-size: 11px; font-weight: 600; margin-bottom: 4px;">🔗 References (${item.entity_refs.length})</div>
                        <div style="display: flex; flex-wrap: wrap; gap: 4px;">
                            ${item.entity_refs.map(ref => `
                                <span style="padding: 2px 6px; background: rgba(139, 92, 246, 0.2); color: #a78bfa; border-radius: 4px; font-size: 10px;">
                                    ${ref.entity_type}: ${this.escapeHtml(ref.name)}
                                </span>
                            `).join('')}
                        </div>
                    </div>
                ` : ''}
                
                ${hasTools ? `
                    <div style="margin-bottom: 8px;">
                        <div style="color: #3b82f6; font-size: 11px; font-weight: 600; margin-bottom: 4px;">🔧 Suggested Tools</div>
                        <div style="display: flex; flex-wrap: wrap; gap: 4px;">
                            ${item.tool_suggestions.map(tool => `
                                <button onclick="app.executeToolForItem('${category}', ${idx}, '${this.escapeHtml(tool.tool)}')"
                                        class="panel-btn" style="font-size: 10px; padding: 2px 6px;">
                                    ${this.escapeHtml(tool.tool)}
                                </button>
                            `).join('')}
                        </div>
                    </div>
                ` : ''}
                
                <div style="display: flex; gap: 6px; flex-wrap: wrap;">
                    <button class="panel-btn" style="font-size: 10px; padding: 3px 6px;" 
                            onclick="app.enrichBoardItem('${category}', ${idx})">🔗 Enrich</button>
                    <button class="panel-btn" style="font-size: 10px; padding: 3px 6px;"
                            onclick="app.showToolSuggestions('${category}', ${idx})">🔧 Suggest Tools</button>
                    <button class="panel-btn" style="font-size: 10px; padding: 3px 6px;"
                            onclick="app.editBoardItem('${category}', ${idx})">✏️ Edit</button>
                    <button class="panel-btn" style="font-size: 10px; padding: 3px 6px;"
                            onclick="app.deleteBoardItem('${category}', ${idx})">🗑️</button>
                    <button class="panel-btn" style="font-size: 10px; padding: 3px 6px;"
                            onclick="app.moveToCompleted('${category}', ${idx})">✓ Complete</button>
                </div>
            </div>
        `;
        
        return html;
    };
    
    // Update the main focus UI to include new controls
    VeraChat.prototype.renderEnhancedFocusControls = function() {
        return `
            <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                ${this.currentFocus ? `
                    <button class="panel-btn" onclick="app.${this.focusRunning ? 'stopProactiveThinking' : 'startProactiveThinking'}()" style="padding: 6px 12px;">
                        ${this.focusRunning ? '⏸️ Stop' : '▶️ Start'}
                    </button>
                    <button class="panel-btn" onclick="app.triggerProactiveThought()" style="padding: 6px 12px;">
                        💭 Think Now
                    </button>
                    <button class="panel-btn" onclick="app.pauseBackground()" style="padding: 6px 12px;">
                        ⏸️ Pause
                    </button>
                    <button class="panel-btn" onclick="app.resumeBackground()" style="padding: 6px 12px;">
                        ▶️ Resume
                    </button>
                ` : ''}
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
    };
    VeraChat.prototype.createResourceMonitorInHeader = function() {
    const header = document.getElementById('header');
    if (!header) return;
    
    const sessionInfo = document.getElementById('sessionInfo');
    if (!sessionInfo || !sessionInfo.parentElement) return;
    
    const resourceMonitor = document.createElement('div');
    resourceMonitor.id = 'resourceStatusIndicator';
    resourceMonitor.style.cssText = `
        display: inline-flex;
        align-items: center;
        gap: 8px;
        margin-left: 8px;
        padding: 4px 8px;
        background: rgba(15, 23, 42, 0.5);
        border-radius: 4px;
        font-size: 11px;
    `;
    
    sessionInfo.parentElement.appendChild(document.createTextNode(' • '));
    sessionInfo.parentElement.appendChild(resourceMonitor);
};
    /**
     * Enhanced Proactive Focus Manager UI
     * ===================================
     * Add this to your existing focus UI JavaScript to integrate:
     * - Resource monitoring and control
     * - External resources management
     * - Modular stage execution
     * - Calendar scheduling
     * - Background service monitoring
     * 
     * This extends the existing VeraChat class with new methods
     */


    // ============================================================
    // RESOURCE MONITORING
    // ============================================================
    
    VeraChat.prototype.initResourceMonitoring = function() {
        if (!this.sessionId) return;

        if (!document.getElementById('resourceStatusIndicator')) {
            this.createResourceMonitorInHeader();  
        }
        // Poll resource status every 5 seconds
        this.resourceMonitorInterval = setInterval(() => {
            this.updateResourceStatus();
        }, 5000);
    };
    
    VeraChat.prototype.updateResourceStatus = async function() {
        if (!this.sessionId) return;
        
        try {
            const response = await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/resources/status`);
            const data = await response.json();
            
            if (data.status === 'active') {
                this.currentResourceStatus = data;
                this.updateResourceStatusDisplay(data);
            }
        } catch (error) {
            console.error('Failed to update resource status:', error);
        }
    };
    
    VeraChat.prototype.updateResourceStatusDisplay = function(status) {
        const indicator = document.getElementById('resourceStatusIndicator');
        if (!indicator) return;
        
        const cpuColor = status.cpu_percent > 70 ? '#ef4444' : 
                        status.cpu_percent > 50 ? '#f59e0b' : '#10b981';
        const memColor = status.memory_percent > 80 ? '#ef4444' : 
                        status.memory_percent > 60 ? '#f59e0b' : '#10b981';
        
        indicator.innerHTML = `
        <div style="display: inline-flex; align-items: center; gap: 6px;">
            <span style="color: #94a3b8; font-size: 10px;">CPU</span>
            <div style="width: 40px; height: 6px; background: rgba(0,0,0,0.3); border-radius: 3px; overflow: hidden;">
                <div style="width: ${status.cpu_percent}%; height: 100%; background: ${cpuColor}; transition: width 0.3s;"></div>
            </div>
            <span style="color: ${cpuColor}; font-weight: 600; font-size: 10px;">${status.cpu_percent}%</span>
        </div>
        <div style="display: inline-flex; align-items: center; gap: 6px;">
            <span style="color: #94a3b8; font-size: 10px;">RAM</span>
            <div style="width: 40px; height: 6px; background: rgba(0,0,0,0.3); border-radius: 3px; overflow: hidden;">
                <div style="width: ${status.memory_percent}%; height: 100%; background: ${memColor}; transition: width 0.3s;"></div>
            </div>
            <span style="color: ${memColor}; font-weight: 600; font-size: 10px;">${status.memory_percent}%</span>
        </div>
        <div style="display: inline-flex; align-items: center; gap: 4px;">
            <span style="color: #94a3b8; font-size: 10px;">Ollama</span>
            <span style="color: #60a5fa; font-weight: 600; font-size: 10px;">${status.ollama_process_count}</span>
        </div>
        <button onclick="app.showResourceConfigModal()" 
                style="background: transparent; border: 1px solid #334155; color: #94a3b8; padding: 2px 6px; border-radius: 3px; font-size: 10px; cursor: pointer; margin-left: 4px;"
                onmouseover="this.style.background='rgba(59, 130, 246, 0.1)'; this.style.borderColor='#3b82f6'; this.style.color='#3b82f6';"
                onmouseout="this.style.background='transparent'; this.style.borderColor='#334155'; this.style.color='#94a3b8';">
            ⚙️
        </button>
        `;
    };
    
    VeraChat.prototype.showResourceConfigModal = function() {
        const modal = document.createElement('div');
        modal.id = 'resourceConfigModal';
        modal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.7);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 10000;
            backdrop-filter: blur(4px);
        `;
        
        const limits = this.currentResourceStatus?.limits || {
            cpu: 70,
            memory: 80,
            ollama: 2
        };
        
        const content = document.createElement('div');
        content.style.cssText = `
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            border-radius: 12px;
            padding: 24px;
            max-width: 500px;
            width: 90%;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
            border: 1px solid #334155;
        `;
        
        content.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                <h2 style="margin: 0; color: #e2e8f0;">⚙️ Resource Limits</h2>
                <button onclick="document.getElementById('resourceConfigModal').remove()" 
                        style="background: transparent; border: none; color: #94a3b8; font-size: 24px; cursor: pointer;">×</button>
            </div>
            
            <div style="margin-bottom: 16px;">
                <label style="color: #cbd5e1; font-size: 13px; font-weight: 600; display: block; margin-bottom: 8px;">
                    Max CPU (%)
                </label>
                <input type="number" id="maxCpuInput" value="${limits.cpu}" min="10" max="100" step="5"
                       style="width: 100%; padding: 8px; background: #0f172a; color: #e2e8f0; border: 1px solid #334155; border-radius: 6px; font-size: 14px;">
            </div>
            
            <div style="margin-bottom: 16px;">
                <label style="color: #cbd5e1; font-size: 13px; font-weight: 600; display: block; margin-bottom: 8px;">
                    Max Memory (%)
                </label>
                <input type="number" id="maxMemoryInput" value="${limits.memory}" min="10" max="100" step="5"
                       style="width: 100%; padding: 8px; background: #0f172a; color: #e2e8f0; border: 1px solid #334155; border-radius: 6px; font-size: 14px;">
            </div>
            
            <div style="margin-bottom: 20px;">
                <label style="color: #cbd5e1; font-size: 13px; font-weight: 600; display: block; margin-bottom: 8px;">
                    Max Ollama Processes
                </label>
                <input type="number" id="maxOllamaInput" value="${limits.ollama}" min="1" max="10" step="1"
                       style="width: 100%; padding: 8px; background: #0f172a; color: #e2e8f0; border: 1px solid #334155; border-radius: 6px; font-size: 14px;">
            </div>
            
            <button onclick="app.applyResourceConfig()" class="panel-btn" 
                    style="width: 100%; padding: 10px; background: #3b82f6; font-weight: 600;">
                ✓ Apply Settings
            </button>
        `;
        
        modal.appendChild(content);
        document.body.appendChild(modal);
    };
    
    VeraChat.prototype.applyResourceConfig = async function() {
        const maxCpu = parseFloat(document.getElementById('maxCpuInput').value);
        const maxMemory = parseFloat(document.getElementById('maxMemoryInput').value);
        const maxOllama = parseInt(document.getElementById('maxOllamaInput').value);
        
        try {
            await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/resources/configure`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    max_cpu_percent: maxCpu,
                    max_memory_percent: maxMemory,
                    max_ollama_processes: maxOllama
                })
            });
            
            this.addSystemMessage(`✓ Resource limits updated: CPU=${maxCpu}%, Memory=${maxMemory}%, Ollama=${maxOllama}`);
            document.getElementById('resourceConfigModal').remove();
            this.updateResourceStatus();
        } catch (error) {
            console.error('Failed to apply resource config:', error);
            this.addSystemMessage('Error updating resource limits');
        }
    };
    
    VeraChat.prototype.pauseResourceIntensive = async function(priority = null) {
        try {
            const url = `http://llm.int:8888/api/focus/${this.sessionId}/resources/pause${priority ? `?priority=${priority}` : ''}`;
            await fetch(url, { method: 'POST' });
            this.addSystemMessage(`⏸️ Paused resource-intensive operations${priority ? ` (${priority} priority)` : ''}`);
        } catch (error) {
            console.error('Failed to pause:', error);
        }
    };
    
    VeraChat.prototype.resumeResourceIntensive = async function(priority = null) {
        try {
            const url = `http://llm.int:8888/api/focus/${this.sessionId}/resources/resume${priority ? `?priority=${priority}` : ''}`;
            await fetch(url, { method: 'POST' });
            this.addSystemMessage(`▶️ Resumed resource-intensive operations${priority ? ` (${priority} priority)` : ''}`);
        } catch (error) {
            console.error('Failed to resume:', error);
        }
    };
    
    // ============================================================
    // EXTERNAL RESOURCES MANAGEMENT
    // ============================================================
    
    VeraChat.prototype.showExternalResourcesModal = async function() {
        try {
            const response = await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/external-resources`);
            const data = await response.json();
            
            this.displayExternalResourcesModal(data.resources);
        } catch (error) {
            console.error('Failed to load external resources:', error);
            this.addSystemMessage('Error loading external resources');
        }
    };
    
    VeraChat.prototype.displayExternalResourcesModal = function(resources) {
        const modal = document.createElement('div');
        modal.id = 'externalResourcesModal';
        modal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.7);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 10000;
            backdrop-filter: blur(4px);
        `;
        
        const content = document.createElement('div');
        content.style.cssText = `
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            border-radius: 12px;
            padding: 24px;
            max-width: 700px;
            width: 90%;
            max-height: 80vh;
            overflow-y: auto;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
            border: 1px solid #334155;
        `;
        
        let html = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                <h2 style="margin: 0; color: #e2e8f0;">🔗 External Resources</h2>
                <div style="display: flex; gap: 8px;">
                    <button onclick="app.showAddResourceForm()" class="panel-btn" style="font-size: 11px; padding: 4px 8px;">
                        + Add Resource
                    </button>
                    <button onclick="app.discoverNotebooks()" class="panel-btn" style="font-size: 11px; padding: 4px 8px;">
                        📓 Discover Notebooks
                    </button>
                    <button onclick="document.getElementById('externalResourcesModal').remove()" 
                            style="background: transparent; border: none; color: #94a3b8; font-size: 24px; cursor: pointer;">×</button>
                </div>
            </div>
        `;
        
        // Group resources by type
        const byType = {};
        resources.forEach(res => {
            if (!byType[res.type]) byType[res.type] = [];
            byType[res.type].push(res);
        });
        
        const typeIcons = {
            'URL': '🌐',
            'FILE': '📄',
            'FOLDER': '📁',
            'NOTEBOOK': '📓',
            'NEO4J_MEMORY': '🔷',
            'CHROMA_MEMORY': '💾'
        };
        
        const typeColors = {
            'URL': '#3b82f6',
            'FILE': '#10b981',
            'FOLDER': '#f59e0b',
            'NOTEBOOK': '#8b5cf6',
            'NEO4J_MEMORY': '#ec4899',
            'CHROMA_MEMORY': '#06b6d4'
        };
        
        for (const [type, items] of Object.entries(byType)) {
            html += `
                <div style="margin-bottom: 20px;">
                    <h3 style="color: ${typeColors[type] || '#94a3b8'}; font-size: 14px; margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">
                        <span>${typeIcons[type] || '📦'}</span>
                        <span>${type} (${items.length})</span>
                    </h3>
                    <div style="display: flex; flex-direction: column; gap: 8px;">
            `;
            
            items.forEach(res => {
                const statusColor = res.accessible ? '#10b981' : '#ef4444';
                const statusIcon = res.accessible ? '✓' : '✕';
                
                html += `
                    <div style="background: rgba(15, 23, 42, 0.5); border-left: 3px solid ${typeColors[type] || '#94a3b8'}; padding: 12px; border-radius: 6px;">
                        <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 8px;">
                            <div style="flex: 1;">
                                <div style="color: #e2e8f0; font-weight: 600; font-size: 13px; margin-bottom: 4px;">
                                    ${this.escapeHtml(res.title || res.uri)}
                                    <span style="color: ${statusColor}; margin-left: 8px; font-size: 11px;">${statusIcon}</span>
                                </div>
                                ${res.description ? `
                                    <div style="color: #94a3b8; font-size: 11px; margin-bottom: 4px;">
                                        ${this.escapeHtml(res.description)}
                                    </div>
                                ` : ''}
                                <div style="color: #64748b; font-size: 10px; word-break: break-all;">
                                    ${this.escapeHtml(res.uri)}
                                </div>
                            </div>
                            <div style="display: flex; gap: 4px; margin-left: 8px;">
                                <button onclick="app.refreshResource('${res.id}')" class="panel-btn" 
                                        style="font-size: 10px; padding: 3px 6px;">
                                    🔄
                                </button>
                                <button onclick="app.removeResource('${res.id}')" class="panel-btn" 
                                        style="font-size: 10px; padding: 3px 6px;">
                                    🗑️
                                </button>
                            </div>
                        </div>
                        ${res.last_checked ? `
                            <div style="color: #64748b; font-size: 10px;">
                                Last checked: ${new Date(res.last_checked).toLocaleString()}
                            </div>
                        ` : ''}
                    </div>
                `;
            });
            
            html += `
                    </div>
                </div>
            `;
        }
        
        if (resources.length === 0) {
            html += `
                <div style="text-align: center; padding: 40px; color: #64748b;">
                    <div style="font-size: 48px; margin-bottom: 16px;">🔗</div>
                    <div>No external resources yet</div>
                    <div style="font-size: 11px; margin-top: 8px;">Click "+ Add Resource" to get started</div>
                </div>
            `;
        }
        
        content.innerHTML = html;
        modal.appendChild(content);
        document.body.appendChild(modal);
    };
    
    VeraChat.prototype.showAddResourceForm = function() {
        const modal = document.getElementById('externalResourcesModal');
        if (!modal) return;
        
        const form = document.createElement('div');
        form.style.cssText = `
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: #1e293b;
            border-radius: 12px;
            padding: 24px;
            width: 500px;
            max-width: 90%;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
            border: 1px solid #334155;
            z-index: 10001;
        `;
        
        form.innerHTML = `
            <h3 style="margin: 0 0 16px 0; color: #e2e8f0;">Add External Resource</h3>
            
            <div style="margin-bottom: 12px;">
                <label style="color: #cbd5e1; font-size: 12px; display: block; margin-bottom: 4px;">
                    Resource URI
                </label>
                <input type="text" id="resourceUriInput" placeholder="URL, file path, neo4j:id, chroma:id, etc."
                       style="width: 100%; padding: 8px; background: #0f172a; color: #e2e8f0; border: 1px solid #334155; border-radius: 4px; font-size: 13px;">
                <div style="color: #64748b; font-size: 10px; margin-top: 4px;">
                    Examples: https://docs.com, /path/to/file, neo4j:entity_123, notebook:sess_abc/notebook_xyz
                </div>
            </div>
            
            <div style="margin-bottom: 12px;">
                <label style="color: #cbd5e1; font-size: 12px; display: block; margin-bottom: 4px;">
                    Description (optional)
                </label>
                <input type="text" id="resourceDescInput" placeholder="Brief description"
                       style="width: 100%; padding: 8px; background: #0f172a; color: #e2e8f0; border: 1px solid #334155; border-radius: 4px; font-size: 13px;">
            </div>
            
            <div style="margin-bottom: 16px;">
                <label style="color: #cbd5e1; font-size: 12px; display: block; margin-bottom: 4px;">
                    Link to category (optional)
                </label>
                <select id="resourceCategorySelect"
                        style="width: 100%; padding: 8px; background: #0f172a; color: #e2e8f0; border: 1px solid #334155; border-radius: 4px; font-size: 13px;">
                    <option value="">-- None --</option>
                    <option value="progress">Progress</option>
                    <option value="next_steps">Next Steps</option>
                    <option value="issues">Issues</option>
                    <option value="ideas">Ideas</option>
                    <option value="actions">Actions</option>
                </select>
            </div>
            
            <div style="display: flex; gap: 8px;">
                <button onclick="app.submitAddResource()" class="panel-btn" 
                        style="flex: 1; padding: 8px; background: #3b82f6;">
                    ✓ Add Resource
                </button>
                <button onclick="this.parentElement.parentElement.remove()" class="panel-btn" 
                        style="padding: 8px;">
                    Cancel
                </button>
            </div>
        `;
        
        document.body.appendChild(form);
    };
    
    VeraChat.prototype.submitAddResource = async function() {
        const uri = document.getElementById('resourceUriInput').value.trim();
        const description = document.getElementById('resourceDescInput').value.trim();
        const category = document.getElementById('resourceCategorySelect').value;
        
        if (!uri) {
            this.addSystemMessage('Please enter a resource URI');
            return;
        }
        
        try {
            const response = await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/external-resources/add`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    uri: uri,
                    description: description || null,
                    category: category || null
                })
            });
            
            const data = await response.json();
            
            this.addSystemMessage(`✓ Added resource: ${data.resource.title || uri}`);
            
            // Close form
            const forms = document.querySelectorAll('div[style*="position: fixed"][style*="z-index: 10001"]');
            forms.forEach(f => f.remove());
            
            // Refresh resources modal
            this.showExternalResourcesModal();
        } catch (error) {
            console.error('Failed to add resource:', error);
            this.addSystemMessage('Error adding resource');
        }
    };
    
    VeraChat.prototype.refreshResource = async function(resourceId) {
        try {
            await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/external-resources/${resourceId}/refresh`, {
                method: 'POST'
            });
            
            this.addSystemMessage('🔄 Resource refreshed');
            this.showExternalResourcesModal();
        } catch (error) {
            console.error('Failed to refresh resource:', error);
            this.addSystemMessage('Error refreshing resource');
        }
    };
    
    VeraChat.prototype.removeResource = async function(resourceId) {
        if (!confirm('Remove this resource?')) return;
        
        try {
            await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/external-resources/${resourceId}`, {
                method: 'DELETE'
            });
            
            this.addSystemMessage('🗑️ Resource removed');
            this.showExternalResourcesModal();
        } catch (error) {
            console.error('Failed to remove resource:', error);
            this.addSystemMessage('Error removing resource');
        }
    };
    
    VeraChat.prototype.discoverNotebooks = async function() {
        try {
            const response = await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/notebooks/discover`);
            const data = await response.json();
            
            this.addSystemMessage(`📓 Found ${data.total} notebooks`);
            
            // Optionally add them as resources
            if (data.notebooks.length > 0 && confirm(`Add ${data.notebooks.length} notebooks as resources?`)) {
                for (const notebook of data.notebooks) {
                    await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/external-resources/add`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            uri: `notebook:${notebook.path}`,
                            description: `${notebook.name} (${notebook.note_count} notes)`
                        })
                    });
                }
                this.showExternalResourcesModal();
            }
        } catch (error) {
            console.error('Failed to discover notebooks:', error);
            this.addSystemMessage('Error discovering notebooks');
        }
    };
    
    // ============================================================
    // STAGE ORCHESTRATION
    // ============================================================
    
    VeraChat.prototype.showStageExecutionModal = async function() {
        try {
            const response = await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/stages/available`);
            const data = await response.json();
            
            this.displayStageExecutionModal(data.stages);
        } catch (error) {
            console.error('Failed to load stages:', error);
            this.addSystemMessage('Error loading stages');
        }
    };
    
    VeraChat.prototype.displayStageExecutionModal = function(stages) {
        const modal = document.createElement('div');
        modal.id = 'stageExecutionModal';
        modal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.7);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 10000;
            backdrop-filter: blur(4px);
        `;
        
        const content = document.createElement('div');
        content.style.cssText = `
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            border-radius: 12px;
            padding: 24px;
            max-width: 600px;
            width: 90%;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
            border: 1px solid #334155;
        `;
        
        let html = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                <h2 style="margin: 0; color: #e2e8f0;">🎯 Execute Stages</h2>
                <button onclick="document.getElementById('stageExecutionModal').remove()" 
                        style="background: transparent; border: none; color: #94a3b8; font-size: 24px; cursor: pointer;">×</button>
            </div>
            
            <div style="margin-bottom: 16px; padding: 12px; background: rgba(59, 130, 246, 0.1); border: 1px solid rgba(59, 130, 246, 0.3); border-radius: 6px; font-size: 12px; color: #94a3b8;">
                Select stages to execute in sequence. Each stage will update the focus board with insights, actions, and next steps.
            </div>
            
            <div style="display: flex; flex-direction: column; gap: 8px; margin-bottom: 20px;">
        `;
        
        stages.forEach((stage, idx) => {
            html += `
                <label style="display: flex; align-items: start; gap: 12px; padding: 12px; background: rgba(15, 23, 42, 0.5); border-radius: 6px; cursor: pointer; transition: all 0.2s;"
                       onmouseover="this.style.background='rgba(59, 130, 246, 0.1)'" 
                       onmouseout="this.style.background='rgba(15, 23, 42, 0.5)'">
                    <input type="checkbox" id="stage_${idx}" value="${stage.name}" 
                           ${idx === 0 ? 'checked' : ''}
                           style="margin-top: 4px;">
                    <div style="flex: 1;">
                        <div style="color: #e2e8f0; font-weight: 600; font-size: 13px; margin-bottom: 4px;">
                            ${stage.icon} ${stage.name}
                        </div>
                        <div style="color: #94a3b8; font-size: 11px;">
                            ${stage.description}
                        </div>
                    </div>
                </label>
            `;
        });
        
        html += `
            </div>
            
            <button onclick="app.executeSelectedStages()" class="panel-btn" 
                    style="width: 100%; padding: 10px; background: #3b82f6; font-weight: 600;">
                ▶️ Execute Pipeline
            </button>
        `;
        
        content.innerHTML = html;
        modal.appendChild(content);
        document.body.appendChild(modal);
    };
    
    VeraChat.prototype.executeSelectedStages = async function() {
        const checkboxes = document.querySelectorAll('input[id^="stage_"]:checked');
        const stages = Array.from(checkboxes).map(cb => cb.value);
        
        if (stages.length === 0) {
            this.addSystemMessage('Please select at least one stage');
            return;
        }
        
        document.getElementById('stageExecutionModal').remove();
        
        try {
            const response = await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/stages/execute`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    stages: stages
                })
            });
            
            const data = await response.json();
            
            this.addSystemMessage(`▶️ Executing stages: ${stages.join(', ')}`);
            
            // Refresh focus board after a delay
            setTimeout(() => this.loadFocusStatus(), 5000);
        } catch (error) {
            console.error('Failed to execute stages:', error);
            this.addSystemMessage('Error executing stages');
        }
    };
    
    // ============================================================
    // CALENDAR SCHEDULING
    // ============================================================
    
    VeraChat.prototype.showCalendarModal = async function() {
        try {
            const response = await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/calendar/sessions`);
            const data = await response.json();
            
            this.displayCalendarModal(data.sessions);
        } catch (error) {
            console.error('Failed to load calendar:', error);
            this.addSystemMessage('Error loading calendar');
        }
    };
    
    VeraChat.prototype.displayCalendarModal = function(sessions) {
        const modal = document.createElement('div');
        modal.id = 'calendarModal';
        modal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.7);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 10000;
            backdrop-filter: blur(4px);
        `;
        
        const content = document.createElement('div');
        content.style.cssText = `
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            border-radius: 12px;
            padding: 24px;
            max-width: 700px;
            width: 90%;
            max-height: 80vh;
            overflow-y: auto;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
            border: 1px solid #334155;
        `;
        
        let html = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                <h2 style="margin: 0; color: #e2e8f0;">📅 Scheduled Sessions</h2>
                <div style="display: flex; gap: 8px;">
                    <button onclick="app.showScheduleForm()" class="panel-btn" style="font-size: 11px; padding: 4px 8px;">
                        + Schedule Session
                    </button>
                    <button onclick="document.getElementById('calendarModal').remove()" 
                            style="background: transparent; border: none; color: #94a3b8; font-size: 24px; cursor: pointer;">×</button>
                </div>
            </div>
        `;
        
        if (sessions.length === 0) {
            html += `
                <div style="text-align: center; padding: 40px; color: #64748b;">
                    <div style="font-size: 48px; margin-bottom: 16px;">📅</div>
                    <div>No scheduled sessions</div>
                    <div style="font-size: 11px; margin-top: 8px;">Click "+ Schedule Session" to create one</div>
                </div>
            `;
        } else {
            html += `<div style="display: flex; flex-direction: column; gap: 12px;">`;
            
            sessions.forEach(session => {
                const startTime = new Date(session.start_time);
                const isPast = startTime < new Date();
                
                html += `
                    <div style="background: rgba(15, 23, 42, 0.5); border-left: 3px solid ${isPast ? '#6b7280' : '#8b5cf6'}; padding: 12px; border-radius: 6px;">
                        <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 8px;">
                            <div style="flex: 1;">
                                <div style="color: #e2e8f0; font-weight: 600; font-size: 13px; margin-bottom: 4px;">
                                    🎯 ${this.escapeHtml(session.focus || 'Current Focus')}
                                </div>
                                <div style="color: #94a3b8; font-size: 11px; margin-bottom: 4px;">
                                    📅 ${startTime.toLocaleString()} (${session.duration_minutes} min)
                                </div>
                                ${session.stages ? `
                                    <div style="color: #64748b; font-size: 10px;">
                                        Stages: ${session.stages.join(', ')}
                                    </div>
                                ` : ''}
                                ${session.recurrence_rule ? `
                                    <div style="color: #64748b; font-size: 10px;">
                                        🔁 Recurring
                                    </div>
                                ` : ''}
                            </div>
                            <button onclick="app.cancelSession('${session.uid}')" class="panel-btn" 
                                    style="font-size: 10px; padding: 3px 6px; margin-left: 8px;">
                                🗑️
                            </button>
                        </div>
                    </div>
                `;
            });
            
            html += `</div>`;
        }
        
        content.innerHTML = html;
        modal.appendChild(content);
        document.body.appendChild(modal);
    };
    
    VeraChat.prototype.showScheduleForm = function() {
        const form = document.createElement('div');
        form.style.cssText = `
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: #1e293b;
            border-radius: 12px;
            padding: 24px;
            width: 500px;
            max-width: 90%;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
            border: 1px solid #334155;
            z-index: 10001;
        `;
        
        const tomorrow = new Date();
        tomorrow.setDate(tomorrow.getDate() + 1);
        tomorrow.setHours(9, 0, 0, 0);
        
        form.innerHTML = `
            <h3 style="margin: 0 0 16px 0; color: #e2e8f0;">Schedule Proactive Session</h3>
            
            <div style="margin-bottom: 12px;">
                <label style="color: #cbd5e1; font-size: 12px; display: block; margin-bottom: 4px;">
                    Start Time
                </label>
                <input type="datetime-local" id="scheduleStartTime" 
                       value="${tomorrow.toISOString().slice(0, 16)}"
                       style="width: 100%; padding: 8px; background: #0f172a; color: #e2e8f0; border: 1px solid #334155; border-radius: 4px; font-size: 13px;">
            </div>
            
            <div style="margin-bottom: 12px;">
                <label style="color: #cbd5e1; font-size: 12px; display: block; margin-bottom: 4px;">
                    Duration (minutes)
                </label>
                <input type="number" id="scheduleDuration" value="30" min="5" step="5"
                       style="width: 100%; padding: 8px; background: #0f172a; color: #e2e8f0; border: 1px solid #334155; border-radius: 4px; font-size: 13px;">
            </div>
            
            <div style="margin-bottom: 16px;">
                <label style="color: #cbd5e1; font-size: 12px; display: block; margin-bottom: 4px;">
                    Recurrence
                </label>
                <select id="scheduleRecurrence"
                        style="width: 100%; padding: 8px; background: #0f172a; color: #e2e8f0; border: 1px solid #334155; border-radius: 4px; font-size: 13px;">
                    <option value="">One-time</option>
                    <option value="daily">Daily (7 days)</option>
                    <option value="weekly">Weekly (4 weeks)</option>
                </select>
            </div>
            
            <div style="display: flex; gap: 8px;">
                <button onclick="app.submitScheduleForm()" class="panel-btn" 
                        style="flex: 1; padding: 8px; background: #8b5cf6;">
                    ✓ Schedule
                </button>
                <button onclick="this.parentElement.parentElement.remove()" class="panel-btn" 
                        style="padding: 8px;">
                    Cancel
                </button>
            </div>
        `;
        
        document.body.appendChild(form);
    };
    
    VeraChat.prototype.submitScheduleForm = async function() {
        const startTime = document.getElementById('scheduleStartTime').value;
        const duration = parseInt(document.getElementById('scheduleDuration').value);
        const recurrence = document.getElementById('scheduleRecurrence').value;
        
        if (!startTime) {
            this.addSystemMessage('Please select a start time');
            return;
        }
        
        try {
            await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/calendar/schedule`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    start_time: new Date(startTime).toISOString(),
                    duration_minutes: duration,
                    recurrence: recurrence || null
                })
            });
            
            this.addSystemMessage(`✓ Session scheduled for ${new Date(startTime).toLocaleString()}`);
            
            // Close form
            const forms = document.querySelectorAll('div[style*="position: fixed"][style*="z-index: 10001"]');
            forms.forEach(f => f.remove());
            
            // Refresh calendar
            this.showCalendarModal();
        } catch (error) {
            console.error('Failed to schedule session:', error);
            this.addSystemMessage('Error scheduling session');
        }
    };
    
    VeraChat.prototype.cancelSession = async function(uid) {
        if (!confirm('Cancel this scheduled session?')) return;
        
        try {
            await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/calendar/sessions/${uid}`, {
                method: 'DELETE'
            });
            
            this.addSystemMessage('🗑️ Session cancelled');
            this.showCalendarModal();
        } catch (error) {
            console.error('Failed to cancel session:', error);
            this.addSystemMessage('Error cancelling session');
        }
    };
    
    // ============================================================
    // BACKGROUND SERVICE
    // ============================================================
    
    VeraChat.prototype.showBackgroundServicePanel = async function() {
        try {
            const response = await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/background/status`);
            const data = await response.json();
            
            this.displayBackgroundServicePanel(data);
        } catch (error) {
            console.error('Failed to load background service status:', error);
            this.addSystemMessage('Error loading background service');
        }
    };
    
    VeraChat.prototype.displayBackgroundServicePanel = function(status) {
        const modal = document.createElement('div');
        modal.id = 'backgroundServiceModal';
        modal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.7);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 10000;
            backdrop-filter: blur(4px);
        `;
        
        const content = document.createElement('div');
        content.style.cssText = `
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            border-radius: 12px;
            padding: 24px;
            max-width: 600px;
            width: 90%;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
            border: 1px solid #334155;
        `;
        
        const isRunning = status.running;
        const isPaused = status.paused;
        
        let html = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                <h2 style="margin: 0; color: #e2e8f0;">🤖 Background Service</h2>
                <button onclick="document.getElementById('backgroundServiceModal').remove()" 
                        style="background: transparent; border: none; color: #94a3b8; font-size: 24px; cursor: pointer;">×</button>
            </div>
            
            <div style="margin-bottom: 20px; padding: 16px; background: rgba(15, 23, 42, 0.5); border-radius: 8px; border: 1px solid #334155;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                    <span style="color: #cbd5e1; font-weight: 600;">Status:</span>
                    <span style="padding: 4px 12px; background: ${isRunning ? '#10b981' : '#6b7280'}; color: white; border-radius: 6px; font-size: 12px; font-weight: 600;">
                        ${isRunning ? (isPaused ? '⏸️ PAUSED' : '● RUNNING') : '○ STOPPED'}
                    </span>
                </div>
                
                ${status.status !== 'not_started' ? `
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 12px; font-size: 11px;">
                        <div style="color: #94a3b8;">CPU Threshold:</div>
                        <div style="color: #e2e8f0;">${status.config.max_cpu_percent}%</div>
                        
                        <div style="color: #94a3b8;">Check Interval:</div>
                        <div style="color: #e2e8f0;">${status.config.check_interval}s</div>
                        
                        <div style="color: #94a3b8;">Min Idle Time:</div>
                        <div style="color: #e2e8f0;">${status.config.min_idle_seconds}s</div>
                        
                        <div style="color: #94a3b8;">Enabled Stages:</div>
                        <div style="color: #e2e8f0;">${status.config.enabled_stages?.join(', ') || 'All'}</div>
                        
                        <div style="color: #94a3b8;">Calendar:</div>
                        <div style="color: #e2e8f0;">${status.config.use_calendar ? '✓ Enabled' : '✕ Disabled'}</div>
                        
                        <div style="color: #94a3b8;">Executions:</div>
                        <div style="color: #e2e8f0;">${status.execution_count}</div>
                    </div>
                ` : ''}
            </div>
            
            <div style="display: flex; flex-direction: column; gap: 8px;">
                ${!isRunning ? `
                    <button onclick="app.startBackgroundService()" class="panel-btn" 
                            style="width: 100%; padding: 10px; background: #10b981; font-weight: 600;">
                        ▶️ Start Background Service
                    </button>
                ` : ''}
                
                ${isRunning ? `
                    ${!isPaused ? `
                        <button onclick="app.pauseBackgroundService()" class="panel-btn" 
                                style="width: 100%; padding: 10px; background: #f59e0b; font-weight: 600;">
                            ⏸️ Pause
                        </button>
                    ` : `
                        <button onclick="app.resumeBackgroundService()" class="panel-btn" 
                                style="width: 100%; padding: 10px; background: #10b981; font-weight: 600;">
                            ▶️ Resume
                        </button>
                    `}
                    
                    <button onclick="app.triggerBackgroundSession()" class="panel-btn" 
                            style="width: 100%; padding: 10px; background: #3b82f6; font-weight: 600;">
                        💭 Trigger Session Now
                    </button>
                    
                    <button onclick="app.stopBackgroundService()" class="panel-btn" 
                            style="width: 100%; padding: 10px; background: #ef4444; font-weight: 600;">
                        ⏹️ Stop Service
                    </button>
                ` : ''}
                
                ${status.execution_count > 0 ? `
                    <button onclick="app.showBackgroundHistory()" class="panel-btn" 
                            style="width: 100%; padding: 10px;">
                        📊 View History
                    </button>
                ` : ''}
            </div>
        `;
        
        content.innerHTML = html;
        modal.appendChild(content);
        document.body.appendChild(modal);
    };
    
    VeraChat.prototype.startBackgroundService = async function() {
        try {
            await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/background/start`, {
                method: 'POST'
            });
            
            this.addSystemMessage('▶️ Background service started');
            this.showBackgroundServicePanel();
        } catch (error) {
            console.error('Failed to start background service:', error);
            this.addSystemMessage('Error starting background service');
        }
    };
    
    VeraChat.prototype.stopBackgroundService = async function() {
        if (!confirm('Stop background service?')) return;
        
        try {
            await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/background/stop`, {
                method: 'POST'
            });
            
            this.addSystemMessage('⏹️ Background service stopped');
            this.showBackgroundServicePanel();
        } catch (error) {
            console.error('Failed to stop background service:', error);
            this.addSystemMessage('Error stopping background service');
        }
    };
    
    VeraChat.prototype.pauseBackgroundService = async function() {
        try {
            await this.pauseResourceIntensive();
            this.addSystemMessage('⏸️ Background service paused');
            setTimeout(() => this.showBackgroundServicePanel(), 500);
        } catch (error) {
            console.error('Failed to pause background service:', error);
        }
    };
    
    VeraChat.prototype.resumeBackgroundService = async function() {
        try {
            await this.resumeResourceIntensive();
            this.addSystemMessage('▶️ Background service resumed');
            setTimeout(() => this.showBackgroundServicePanel(), 500);
        } catch (error) {
            console.error('Failed to resume background service:', error);
        }
    };
    
    VeraChat.prototype.triggerBackgroundSession = async function() {
        try {
            await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/background/trigger`, {
                method: 'POST'
            });
            
            this.addSystemMessage('💭 Manual session triggered');
            document.getElementById('backgroundServiceModal')?.remove();
        } catch (error) {
            console.error('Failed to trigger session:', error);
            this.addSystemMessage('Error triggering session');
        }
    };
    
    VeraChat.prototype.showBackgroundHistory = async function() {
        try {
            const response = await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/background/history`);
            const data = await response.json();
            
            // Create history modal (similar to other modals)
            // Implement as needed...
            
            this.addSystemMessage(`📊 ${data.total} executions in history`);
        } catch (error) {
            console.error('Failed to load history:', error);
            this.addSystemMessage('Error loading history');
        }
    };
    
    // ============================================================
    // ENHANCED FOCUS UI WITH NEW CONTROLS
    // ============================================================
    
    // Override the original updateFocusUI to add new controls
    const originalUpdateFocusUI = VeraChat.prototype.updateFocusUI;
    
    VeraChat.prototype.updateFocusUI = function(preserveScrollPos = null) {
        // Call original
        originalUpdateFocusUI.call(this, preserveScrollPos);
        
        // // Add resource status indicator
        // const focusContent = document.querySelector('.focusContent');
        // if (focusContent && !document.getElementById('resourceStatusIndicator')) {
        //     const indicator = document.createElement('div');
        //     indicator.id = 'resourceStatusIndicator';
        //     focusContent.insertBefore(indicator, focusContent.firstChild);
            
        //     // Start monitoring
        //     if (!this.resourceMonitorInterval) {
        //         this.initResourceMonitoring();
        //     }
        // }
        
        // Add enhanced control buttons
        this.addEnhancedControlButtons();
    };
    
    VeraChat.prototype.addEnhancedControlButtons = function() {
        const focusContent = document.querySelector('.focusContent');
        if (!focusContent || document.getElementById('enhancedControls')) return;
        
        const controls = document.createElement('div');
        controls.id = 'enhancedControls';
        controls.style.cssText = 'margin-top: 16px; display: flex; gap: 8px; flex-wrap: wrap;';
        
        controls.innerHTML = `
            <button class="panel-btn" onclick="app.showExternalResourcesModal()" style="padding: 6px 12px; font-size: 12px;">
                Resources
            </button>
            <button class="panel-btn" onclick="app.showStageExecutionModal()" style="padding: 6px 12px; font-size: 12px;">
                Stages
            </button>
            <button class="panel-btn" onclick="app.showCalendarModal()" style="padding: 6px 12px; font-size: 12px;">
                Calendar
            </button>
            <button class="panel-btn" onclick="app.showBackgroundServicePanel()" style="padding: 6px 12px; font-size: 12px;">
                Background
            </button>
            <button class="panel-btn" onclick="app.showResourceConfigModal()" style="padding: 6px 12px; font-size: 12px;">
                Limits
            </button>
        `;
        
        focusContent.appendChild(controls);
    };

})();