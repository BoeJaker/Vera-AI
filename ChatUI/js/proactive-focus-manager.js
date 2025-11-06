(() => {
       // ============================================================
    // GRANULAR WORKFLOW CONTROL METHODS
    // ============================================================
     VeraChat.prototype.runIdeasStage = async function() {
        if (!this.sessionId || !this.currentFocus) return;
        
        try {
            const response = await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/stage/ideas`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({})
            });
            
            const data = await response.json();
            this.addSystemMessage('💡 Generating ideas...');
        } catch (error) {
            console.error('Failed to run ideas stage:', error);
            this.addSystemMessage('Error running ideas stage');
        }
    };
    
    VeraChat.prototype.runNextStepsStage = async function() {
        if (!this.sessionId || !this.currentFocus) return;
        
        try {
            const response = await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/stage/next_steps`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({})
            });
            
            const data = await response.json();
            this.addSystemMessage('→ Generating next steps...');
        } catch (error) {
            console.error('Failed to run next steps stage:', error);
            this.addSystemMessage('Error running next steps stage');
        }
    };
    
    VeraChat.prototype.runActionsStage = async function() {
        if (!this.sessionId || !this.currentFocus) return;
        
        try {
            const response = await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/stage/actions`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({})
            });
            
            const data = await response.json();
            this.addSystemMessage('⚡ Generating actions...');
        } catch (error) {
            console.error('Failed to run actions stage:', error);
            this.addSystemMessage('Error running actions stage');
        }
    };
    
    VeraChat.prototype.runExecuteStage = async function() {
        if (!this.sessionId || !this.currentFocus) return;
        
        // Ask user for parameters
        const maxStr = prompt('Max actions to execute:', '2');
        const max = parseInt(maxStr) || 2;
        
        const priority = prompt('Priority filter (high/medium/low/all):', 'high');
        const priorityValue = priority === 'all' ? 'all' : priority;
        
        try {
            const response = await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/stage/execute`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    max_executions: max,
                    priority: priorityValue
                })
            });
            
            const data = await response.json();
            this.addSystemMessage(`▶️ Executing up to ${max} ${priorityValue} priority actions...`);
        } catch (error) {
            console.error('Failed to run execute stage:', error);
            this.addSystemMessage('Error running execute stage');
        }
    };
    
    VeraChat.prototype.executeActionDirectly = async function(index) {
        if (!this.sessionId || !this.currentFocus) return;
        
        const action = this.focusBoard.actions[index];
        if (!action) {
            this.addSystemMessage('Action not found');
            return;
        }
        
        const parsed = this.parseActionItem(action);
        
        if (!confirm(`Execute this action now?\n\n${parsed.description}`)) {
            return;
        }
        
        try {
            // Create a temporary single-action execution
            const response = await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/action/execute`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    action: parsed,
                    index: index
                })
            });
            
            const data = await response.json();
            this.addSystemMessage(`⚡ Executing action: ${parsed.description.substring(0, 50)}...`);
            
        } catch (error) {
            console.error('Failed to execute action:', error);
            this.addSystemMessage('Error executing action');
        }
    };
    
    VeraChat.prototype.stopCurrentStage = async function() {
        if (!this.sessionId) return;
        
        try {
            const response = await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/stage/stop`, {
                method: 'POST'
            });
            
            const data = await response.json();
            this.addSystemMessage('⏹️ Stop signal sent');
        } catch (error) {
            console.error('Failed to stop stage:', error);
            this.addSystemMessage('Error stopping stage');
        }
    };
    
    // ============================================================
    // STREAMING AND WEBSOCKET HANDLERS
    // ============================================================
    
    VeraChat.prototype.showProactiveThoughtStreaming = function() {
        const messageId = 'proactive-thought-streaming';
        
        const existing = document.getElementById(messageId);
        if (existing) existing.remove();
        
        const container = document.getElementById('chatMessages');
        const messageEl = document.createElement('div');
        messageEl.id = messageId;
        messageEl.className = 'message system';
        messageEl.style.opacity = '0.7';
        
        const content = document.createElement('div');
        content.className = 'message-content';
        content.innerHTML = `
            <div style="display: flex; align-items: center; gap: 8px;">
                <div style="color: #8b5cf6; font-weight: 600;">💭 Generating proactive thought...</div>
                <div class="loading-dots" style="display: flex; gap: 4px;">
                    <span style="animation: pulse 1.5s infinite;">●</span>
                    <span style="animation: pulse 1.5s infinite 0.2s;">●</span>
                    <span style="animation: pulse 1.5s infinite 0.4s;">●</span>
                </div>
            </div>
            <div id="proactive-thought-content" style="margin-top: 8px; color: #cbd5e1;"></div>
        `;
        
        messageEl.appendChild(content);
        container.appendChild(messageEl);
        container.scrollTop = container.scrollHeight;
    };

    VeraChat.prototype.updateProactiveThoughtStream = function(chunk) {
        const contentEl = document.getElementById('proactive-thought-content');
        if (contentEl) {
            contentEl.textContent += chunk;
            const container = document.getElementById('chatMessages');
            container.scrollTop = container.scrollHeight;
        }
    };

    VeraChat.prototype.completeProactiveThoughtStream = function(thought) {
        const messageEl = document.getElementById('proactive-thought-streaming');
        if (messageEl) {
            messageEl.style.opacity = '1';
            messageEl.classList.remove('system');
            messageEl.classList.add('assistant');
            messageEl.id = `msg-proactive-${Date.now()}`;
            
            const content = messageEl.querySelector('.message-content');
            if (content) {
                content.innerHTML = `
                    <div style="color: #8b5cf6; font-weight: 600; margin-bottom: 8px;">💭 Proactive Thought</div>
                    <div style="color: #cbd5e1;">${this.escapeHtml(thought)}</div>
                `;
            }
        }
    };
    
    // ============================================================
    // API CALLS
    // ============================================================
    
    VeraChat.prototype.startProactiveThinking = async function() {
        if (!this.sessionId) return;
        
        try {
            const response = await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/start`, {
                method: 'GET'
            });
            
            const data = await response.json();
            this.focusRunning = true;
            this.updateFocusUI();
            this.addSystemMessage('▶️ Proactive thinking started');
        } catch (error) {
            console.error('Failed to start proactive thinking:', error);
            this.addSystemMessage(`Error starting proactive thinking: ${error.message}`);
        }
    };

    VeraChat.prototype.stopProactiveThinking = async function() {
        if (!this.sessionId) return;
        
        try {
            await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/stop`, {
                method: 'POST'
            });
            
            this.focusRunning = false;
            this.updateFocusUI();
            this.addSystemMessage('⏸️ Proactive thinking stopped');
        } catch (error) {
            console.error('Failed to stop proactive thinking:', error);
        }
    };

    VeraChat.prototype.triggerProactiveThought = async function() {
        if (!this.sessionId) return;
        
        try {
            await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/trigger`, {
                method: 'POST'
            });
            
            this.addSystemMessage('💭 Triggering proactive thought generation...');
        } catch (error) {
            console.error('Failed to trigger thought:', error);
            this.addSystemMessage(`Error: ${error.message}`);
        }
    };

    // ============================================================
    // WEBSOCKET CONNECTION
    // ============================================================
    
    VeraChat.prototype.connectFocusWebSocket = function() {
        if (!this.sessionId) return;
        
        const wsUrl = `ws://llm.int:8888/ws/focus/${this.sessionId}`;
        this.focusWebSocket = new WebSocket(wsUrl);
        
        this.focusWebSocket.onopen = () => {
            console.log('Focus WebSocket connected');
        };
        
        this.focusWebSocket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleFocusEvent(data);
            } catch (error) {
                console.error('Focus WebSocket message parse error:', error);
            }
        };
        
        this.focusWebSocket.onerror = (error) => {
            console.error('Focus WebSocket error:', error);
        };
        
        this.focusWebSocket.onclose = () => {
            console.log('Focus WebSocket disconnected');
            if (this.sessionId) {
                setTimeout(() => this.connectFocusWebSocket(), 3000);
            }
        };
    };

    // Helper to compare focus board states
    VeraChat.prototype._focusBoardsEqual = function(board1, board2) {
        if (!board1 && !board2) return true;
        if (!board1 || !board2) return false;
        
        const keys = ['actions', 'progress', 'next_steps', 'issues', 'ideas', 'completed'];
        
        for (const key of keys) {
            const arr1 = board1[key] || [];
            const arr2 = board2[key] || [];
            
            if (arr1.length !== arr2.length) return false;
            
            // Deep comparison of arrays
            if (JSON.stringify(arr1) !== JSON.stringify(arr2)) return false;
        }
        
        return true;
    };

    // Add to existing handleFocusEvent method:
    VeraChat.prototype.handleFocusEventStages = function(data) {
        const container = document.getElementById('tab-focus');
        const scrollPos = container ? container.scrollTop : 0;
        
        switch (data.type) {
            case 'stage_started':
                this.addSystemMessage(`▶️ Started ${data.data.stage} stage`);
                break;
                
            case 'stage_completed':
                this.addSystemMessage(`✓ Completed ${data.data.stage} stage (${data.data.count} items)`);
                this.loadFocusStatus(); // Refresh board
                break;
                
            case 'stage_error':
                this.addSystemMessage(`❌ Error in ${data.data.stage} stage: ${data.data.error}`);
                break;
                
            case 'stage_stopped':
                this.addSystemMessage('⏹️ Stage stopped');
                break;
        }
    };
    
    VeraChat.prototype.handleFocusEvent = function(data) {
        console.log('Focus event:', data.type);
        
        // Preserve scroll position
        const container = document.getElementById('tab-focus');
        const scrollPos = container ? container.scrollTop : 0;
                
        // Handle stage events
        if (data.type.startsWith('stage_')) {
            this.handleFocusEventStages(data);
        }else{
        switch (data.type) {
            case 'focus_status':
                // Only update if something actually changed
                const focusChanged = this.currentFocus !== data.data.focus;
                const runningChanged = this.focusRunning !== data.data.running;
                const boardChanged = !this._focusBoardsEqual(this.focusBoard, data.data.focus_board);
                
                if (focusChanged || runningChanged || boardChanged) {
                    this.currentFocus = data.data.focus;
                    this.focusBoard = this.normalizeFocusBoard(data.data.focus_board);
                    this.focusRunning = data.data.running;
                    this.updateFocusUI(scrollPos);
                }
                break;
                
            case 'focus_changed':
                this.currentFocus = data.data.focus;
                this.updateFocusUI(scrollPos);
                this.addSystemMessage(`🎯 Focus changed to: ${data.data.focus}`);
                break;
                
            case 'focus_cleared':
                this.currentFocus = null;
                this.updateFocusUI(scrollPos);
                this.addSystemMessage('Focus cleared');
                break;
                
            case 'focus_started':
                this.focusRunning = true;
                this.updateFocusUI(scrollPos);
                this.addSystemMessage(`▶️ Proactive thinking started`);
                break;
                
            case 'focus_stopped':
                this.focusRunning = false;
                this.updateFocusUI(scrollPos);
                this.addSystemMessage('⏸️ Proactive thinking stopped');
                break;
                
            case 'board_updated':
                this.focusBoard = this.normalizeFocusBoard(data.data.focus_board);
                this.updateFocusUI(scrollPos);
                break;
                
            case 'thought_generation_started':
                this.showProactiveThoughtStreaming();
                break;
                
            case 'thought_chunk':
                this.updateProactiveThoughtStream(data.data.chunk);
                break;
                
            case 'thought_completed':
                this.completeProactiveThoughtStream(data.data.thought);
                break;
                
            case 'thought_error':
                this.addSystemMessage(`❌ Error generating thought: ${data.data.error}`);
                break;
        }
        }
    };

    // ============================================================
    // DATA NORMALIZATION
    // ============================================================
    
    VeraChat.prototype.normalizeFocusBoard = function(board) {
        if (!board) {
            return {
                actions: [],
                progress: [],
                next_steps: [],
                issues: [],
                ideas: [],
                completed: []
            };
        }
        
        if (typeof board === 'object' && !Array.isArray(board)) {
            return {
                actions: Array.isArray(board.actions) ? board.actions : [],
                progress: Array.isArray(board.progress) ? board.progress : [],
                next_steps: Array.isArray(board.next_steps) ? board.next_steps : [],
                issues: Array.isArray(board.issues) ? board.issues : [],
                ideas: Array.isArray(board.ideas) ? board.ideas : [],
                completed: Array.isArray(board.completed) ? board.completed : []
            };
        }
        
        return {
            actions: [],
            progress: [],
            next_steps: [],
            issues: [],
            ideas: [],
            completed: []
        };
    };

    // ============================================================
    // ITEM PARSING - FIXED TO HANDLE MARKDOWN BLOCKS
    // ============================================================
    
    // Helper to expand array items into individual items
    VeraChat.prototype.expandActionArray = function(item) {
        let actions = [];
        
        if (typeof item === 'object' && item !== null) {
            if (item.description) {
                // Already a single action object
                actions.push(item);
            } else if (item.note) {
                // Try to parse note
                let noteText = item.note;
                noteText = noteText.replace(/```json\s*/g, '').replace(/```\s*/g, '').trim();
                
                try {
                    const noteData = JSON.parse(noteText);
                    if (Array.isArray(noteData)) {
                        actions = noteData;
                    } else if (noteData.description) {
                        actions.push(noteData);
                    }
                } catch {
                    actions.push({ description: noteText, tools: [], priority: 'medium' });
                }
            }
        } else if (typeof item === 'string') {
            let itemText = item.replace(/```json\s*/g, '').replace(/```\s*/g, '').trim();
            
            try {
                const jsonData = JSON.parse(itemText);
                if (Array.isArray(jsonData)) {
                    actions = jsonData;
                } else if (jsonData.description) {
                    actions.push(jsonData);
                } else {
                    actions.push({ description: itemText, tools: [], priority: 'medium' });
                }
            } catch {
                actions.push({ description: itemText, tools: [], priority: 'medium' });
            }
        }
        
        return actions;
    };

    VeraChat.prototype.parseActionItem = function(item) {
        let parsed = {
            description: '',
            tools: [],
            priority: 'medium',
            metadata: {}
        };
        
        // Handle different formats
        if (typeof item === 'object' && item !== null) {
            if (item.description) {
                parsed.description = item.description;
                parsed.tools = item.tools || [];
                parsed.priority = item.priority || 'medium';
                parsed.metadata = item.metadata || {};
            } else if (item.note) {
                let noteText = item.note;
                noteText = noteText.replace(/```json\s*/g, '').replace(/```\s*/g, '').trim();
                
                try {
                    const noteData = JSON.parse(noteText);
                    if (noteData.description) {
                        parsed.description = noteData.description;
                        parsed.tools = noteData.tools || [];
                        parsed.priority = noteData.priority || 'medium';
                    } else {
                        parsed.description = noteText;
                    }
                } catch {
                    parsed.description = noteText;
                }
                parsed.metadata = item.metadata || {};
            }
        } else if (typeof item === 'string') {
            let itemText = item.replace(/```json\s*/g, '').replace(/```\s*/g, '').trim();
            
            try {
                const jsonData = JSON.parse(itemText);
                if (jsonData.description) {
                    parsed.description = jsonData.description;
                    parsed.tools = jsonData.tools || [];
                    parsed.priority = jsonData.priority || 'medium';
                } else {
                    parsed.description = itemText;
                }
            } catch {
                parsed.description = itemText;
            }
        }
        
        return parsed;
    };

    VeraChat.prototype.parseGenericItem = function(item) {
        if (typeof item === 'object' && item !== null) {
            return {
                text: item.note || item.description || JSON.stringify(item),
                timestamp: item.timestamp,
                metadata: item.metadata || {}
            };
        } else if (typeof item === 'string') {
            // Remove markdown blocks
            let text = item.replace(/```json\s*/g, '').replace(/```\s*/g, '').trim();
            
            try {
                if (text.startsWith('{') || text.startsWith('[')) {
                    const parsed = JSON.parse(text);
                    return {
                        text: parsed.note || parsed.description || text,
                        timestamp: parsed.timestamp,
                        metadata: parsed.metadata || {}
                    };
                }
            } catch {}
            return { text: text, timestamp: null, metadata: {} };
        }
        return { text: String(item), timestamp: null, metadata: {} };
    };

    // ============================================================
    // UI RENDERING - FIXED TO PRESERVE SCROLL
    // ============================================================
     VeraChat.prototype.renderStageControls = function() {
        if (!this.currentFocus) return '';
        
        return `
            <div class="focusContent" style="border-radius: 8px; padding: 16px; margin-bottom: 16px; border-left: 4px solid #f59e0b; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">
                <div style="font-weight: 600; color: #e2e8f0; font-size: 14px; margin-bottom: 12px;">
                    🎮 Workflow Stage Controls
                </div>
                
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 8px;">
                    <!-- Ideas Stage -->
                    <div style="background: #0f172a; padding: 12px; border-radius: 6px; border: 1px solid #334155;">
                        <div style="color: #a78bfa; font-size: 12px; font-weight: 600; margin-bottom: 8px;">💡 Ideas</div>
                        <div style="display: flex; gap: 4px;">
                            <button class="panel-btn" onclick="app.runIdeasStage()" style="flex: 1; font-size: 11px; padding: 6px;">
                                ▶️ Run
                            </button>
                        </div>
                    </div>
                    
                    <!-- Next Steps Stage -->
                    <div style="background: #0f172a; padding: 12px; border-radius: 6px; border: 1px solid #334155;">
                        <div style="color: #fbbf24; font-size: 12px; font-weight: 600; margin-bottom: 8px;">→ Next Steps</div>
                        <div style="display: flex; gap: 4px;">
                            <button class="panel-btn" onclick="app.runNextStepsStage()" style="flex: 1; font-size: 11px; padding: 6px;">
                                ▶️ Run
                            </button>
                        </div>
                    </div>
                    
                    <!-- Actions Stage -->
                    <div style="background: #0f172a; padding: 12px; border-radius: 6px; border: 1px solid #334155;">
                        <div style="color: #60a5fa; font-size: 12px; font-weight: 600; margin-bottom: 8px;">⚡ Actions</div>
                        <div style="display: flex; gap: 4px;">
                            <button class="panel-btn" onclick="app.runActionsStage()" style="flex: 1; font-size: 11px; padding: 6px;">
                                ▶️ Run
                            </button>
                        </div>
                    </div>
                    
                    <!-- Execute Stage -->
                    <div style="background: #0f172a; padding: 12px; border-radius: 6px; border: 1px solid #334155;">
                        <div style="color: #34d399; font-size: 12px; font-weight: 600; margin-bottom: 8px;">🚀 Execute</div>
                        <div style="display: flex; gap: 4px;">
                            <button class="panel-btn" onclick="app.runExecuteStage()" style="flex: 1; font-size: 11px; padding: 6px;">
                                ▶️ Run
                            </button>
                        </div>
                    </div>
                </div>
                
                <!-- Stop All Button -->
                <div style="margin-top: 12px;">
                    <button class="panel-btn" onclick="app.stopCurrentStage()" 
                            style="width: 100%; background: #ef4444; font-size: 12px; padding: 8px;">
                        ⏹️ Stop Current Stage
                    </button>
                </div>
            </div>
        `;
    };

    VeraChat.prototype.updateFocusUI = function(preserveScrollPos = null) {
        let container = document.getElementById('tab-focus');
        if (!container) {
            console.log('Focus container not found');
            return;
        }
        
        this.focusBoard = this.normalizeFocusBoard(this.focusBoard);
            

    let html = `
        <div style="padding: 20px; overflow-y: auto; height: 100%;">
            <!-- HEADER -->
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                <h2 style="margin: 0; color: #e2e8f0;">Proactive Focus Manager</h2>
                <div style="display: flex; gap: 8px; align-items: center;">
                    <span style="padding: 6px 12px; background: ${this.focusRunning ? '#10b981' : '#6b7280'}; color: white; border-radius: 6px; font-size: 12px; font-weight: 600;">
                        ${this.focusRunning ? '● RUNNING' : '○ STOPPED'}
                    </span>
                    ${this.currentFocus ? `
                        <button class="panel-btn" onclick="app.${this.focusRunning ? 'stopProactiveThinking' : 'startProactiveThinking'}()" style="padding: 6px 12px;">
                            ${this.focusRunning ? '⏸️ Stop' : '▶️ Start'}
                        </button>
                        <button class="panel-btn" onclick="app.triggerProactiveThought()" style="padding: 6px 12px;">
                            💭 Think Now
                        </button>
                    ` : ''}
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
            </div>
    `;
        
        // CURRENT FOCUS SECTION
        html += this.renderFocusSection();
        html += this.renderStageControls();  
        // FOCUS BOARD SECTIONS
        html += `<div style="display: grid; grid-template-columns: 1fr; gap: 16px;">`;
        
        const categories = [
            { key: 'actions', label: 'Actions', color: '#3b82f6', icon: '⚡' },
            { key: 'progress', label: 'Progress', color: '#10b981', icon: '✓' },
            { key: 'next_steps', label: 'Next Steps', color: '#f59e0b', icon: '→' },
            { key: 'issues', label: 'Issues', color: '#ef4444', icon: '⚠' },
            { key: 'ideas', label: 'Ideas', color: '#8b5cf6', icon: '💡' },
            { key: 'completed', label: 'Completed', color: '#6b7280', icon: '✔' }
        ];
        
        categories.forEach(cat => {
            html += this.renderCategory(cat);
        });
        
        html += `</div></div>`;
        container.innerHTML = html;
        
        // Restore scroll position if provided
        if (preserveScrollPos !== null) {
            container.scrollTop = preserveScrollPos;
        }
    };

    VeraChat.prototype.renderFocusSection = function() {
        return `
            <div class="focusContent" style="border-radius: 8px; padding: 16px; margin-bottom: 16px; border-left: 4px solid #8b5cf6; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                    <div style="font-weight: 600; color: #e2e8f0; font-size: 14px;">🎯 Current Focus</div>
                    <div style="display: flex; gap: 8px;">
                        <button class="panel-btn" style="font-size: 11px; padding: 4px 8px;" onclick="app.showSetFocusDialog()">✏️ Set</button>
                        ${this.currentFocus ? `<button class="panel-btn" style="font-size: 11px; padding: 4px 8px;" onclick="app.clearFocus()">✕ Clear</button>` : ''}
                    </div>
                </div>
                ${this.currentFocus ? `
                    <div style="background: rgba(139, 92, 246, 0.1); padding: 12px; border-radius: 6px; border: 1px solid rgba(139, 92, 246, 0.3);">
                        <div style="color: #a78bfa; font-size: 18px; font-weight: 600;">${this.escapeHtml(this.currentFocus)}</div>
                    </div>
                ` : `
                    <div style="color: #94a3b8; font-size: 13px; font-style: italic; text-align: center; padding: 12px;">
                        No focus set. Set a focus to enable proactive thinking.
                    </div>
                `}
            </div>
        `;
    };

    VeraChat.prototype.renderCategory = function(cat) {
        let items = this.focusBoard[cat.key] || [];
        
        // Expand arrays in actions category
        if (cat.key === 'actions') {
            let expandedItems = [];
            items.forEach(item => {
                const expanded = this.expandActionArray(item);
                expandedItems.push(...expanded);
            });
            items = expandedItems;
            // Update the actual board with expanded items
            this.focusBoard[cat.key] = expandedItems;
        }
        
        let html = `
            <div class="focusContent" style="border-radius: 8px; padding: 16px; border-left: 4px solid ${cat.color}; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                    <div style="font-weight: 600; color: #e2e8f0; font-size: 14px;">
                        ${cat.icon} ${cat.label}
                        <span style="color: #94a3b8; font-weight: normal; font-size: 12px; margin-left: 8px;">(${items.length})</span>
                    </div>
                    <div style="display: flex; gap: 6px;">
                        <button class="panel-btn" style="font-size: 11px; padding: 4px 8px;" onclick="app.addToFocusBoard('${cat.key}')">+ Add</button>
                        ${items.length > 0 ? `<button class="panel-btn" style="font-size: 11px; padding: 4px 8px;" onclick="app.clearCategory('${cat.key}')">🗑️ Clear</button>` : ''}
                    </div>
                </div>
                <div style="display: flex; flex-direction: column; gap: 8px;">
        `;
        
        if (items.length === 0) {
            html += `<div style="color: #64748b; font-size: 12px; font-style: italic; text-align: center; padding: 8px;">No ${cat.label.toLowerCase()} yet.</div>`;
        } else {
            if (cat.key === 'actions') {
                items.forEach((item, idx) => {
                    html += this.renderActionItem(item, idx, cat.color);
                });
            } else {
                items.forEach((item, idx) => {
                    html += this.renderGenericItem(item, idx, cat.key, cat.color);
                });
            }
        }
        
        html += `</div></div>`;
        return html;
    };

    VeraChat.prototype.renderActionItem = function(item, idx, color) {
        const action = this.parseActionItem(item);
        const priorityColors = {
            high: '#ef4444',
            medium: '#f59e0b',
            low: '#6b7280'
        };
        
        return `
            <div style="background: #0f172a; padding: 12px; border-radius: 6px; border-left: 3px solid ${color};">
                <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 8px;">
                    <div style="color: #cbd5e1; font-size: 13px; flex: 1;">${this.escapeHtml(action.description)}</div>
                    <span style="padding: 2px 6px; background: ${priorityColors[action.priority]}; color: white; border-radius: 4px; font-size: 10px; font-weight: 600; margin-left: 8px;">
                        ${action.priority.toUpperCase()}
                    </span>
                </div>
                ${action.tools.length > 0 ? `
                    <div style="display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 8px;">
                        ${action.tools.map(tool => `
                            <span style="padding: 2px 6px; background: rgba(59, 130, 246, 0.2); color: #60a5fa; border-radius: 4px; font-size: 10px;">
                                🔧 ${this.escapeHtml(tool)}
                            </span>
                        `).join('')}
                    </div>
                ` : ''}
                <div style="display: flex; gap: 6px; margin-top: 8px;">
                    <button class="panel-btn" style="font-size: 10px; padding: 3px 6px;" onclick="app.executeAction(${idx})">▶️ Execute</button>
                    <button class="panel-btn" style="font-size: 10px; padding: 3px 6px;" onclick="app.editBoardItem('actions', ${idx})">✏️ Edit</button>
                    <button class="panel-btn" style="font-size: 10px; padding: 3px 6px;" onclick="app.deleteBoardItem('actions', ${idx})">🗑️ Delete</button>
                    <button class="panel-btn" style="font-size: 10px; padding: 3px 6px;" onclick="app.moveToCompleted('actions', ${idx})">✓ Complete</button>
                </div>
            </div>
        `;
    };

    VeraChat.prototype.renderGenericItem = function(item, idx, category, color) {
        const parsed = this.parseGenericItem(item);
        
        return `
            <div style="background: #0f172a; padding: 10px 12px; border-radius: 6px; border-left: 3px solid ${color};">
                <div style="display: flex; justify-content: space-between; align-items: start;">
                    <div style="color: #cbd5e1; font-size: 13px; flex: 1;">${this.escapeHtml(parsed.text)}</div>
                    <div style="display: flex; gap: 4px; margin-left: 8px;">
                        <button class="panel-btn" style="font-size: 10px; padding: 3px 6px;" onclick="app.editBoardItem('${category}', ${idx})">✏️</button>
                        <button class="panel-btn" style="font-size: 10px; padding: 3px 6px;" onclick="app.deleteBoardItem('${category}', ${idx})">🗑️</button>
                        ${category !== 'completed' ? `<button class="panel-btn" style="font-size: 10px; padding: 3px 6px;" onclick="app.moveToCompleted('${category}', ${idx})">✓</button>` : ''}
                    </div>
                </div>
                ${parsed.timestamp ? `<div style="color: #64748b; font-size: 10px; margin-top: 4px;">${new Date(parsed.timestamp).toLocaleString()}</div>` : ''}
            </div>
        `;
    };

    // ============================================================
    // API METHODS - FIXED TO PERSIST CHANGES TO BACKEND
    // ============================================================
    
    VeraChat.prototype.loadFocusStatus = async function() {
        if (!this.sessionId) return;
        
        try {
            const response = await fetch(`http://llm.int:8888/api/focus/${this.sessionId}`);
            const data = await response.json();
            
            this.currentFocus = data.focus;
            this.focusBoard = this.normalizeFocusBoard(data.focus_board);
            this.focusRunning = data.running;
            
            this.updateFocusUI();
            console.log('Focus status loaded:', data);
        } catch (error) {
            console.error('Failed to load focus status:', error);
            this.addSystemMessage('Error loading focus status');
        }
    };

    VeraChat.prototype.showSetFocusDialog = function() {
        const focus = prompt('Enter focus for proactive thinking:', this.currentFocus || '');
        if (focus !== null && focus.trim()) {
            this.setFocus(focus.trim());
        }
    };

    VeraChat.prototype.setFocus = async function(focus) {
        if (!this.sessionId) return;
        
        try {
            const response = await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/set`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ focus: focus })
            });
            
            const data = await response.json();
            this.currentFocus = data.focus;
            this.updateFocusUI();
            this.addSystemMessage(`🎯 Focus set to: ${focus}`);
        } catch (error) {
            console.error('Failed to set focus:', error);
            this.addSystemMessage(`Error setting focus: ${error.message}`);
        }
    };

    VeraChat.prototype.clearFocus = async function() {
        if (!this.sessionId) return;
        if (!confirm('Clear current focus? This will stop proactive thinking.')) return;
        
        try {
            await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/clear`, {
                method: 'POST'
            });
            
            this.currentFocus = null;
            this.focusRunning = false;
            this.updateFocusUI();
            this.addSystemMessage('Focus cleared');
        } catch (error) {
            console.error('Failed to clear focus:', error);
        }
    };

    VeraChat.prototype.addToFocusBoard = async function(category) {
        let note = '';
        let priority = 'medium';
        
        // Special handling for actions - ask for priority
        if (category === 'actions') {
            note = prompt(`Enter action description:`);
            if (!note || !note.trim()) return;
            
            const priorityInput = prompt('Priority (high/medium/low):', 'medium');
            priority = (priorityInput || 'medium').toLowerCase();
            if (!['high', 'medium', 'low'].includes(priority)) {
                priority = 'medium';
            }
            
            // Format as action object
            note = JSON.stringify({
                description: note.trim(),
                tools: [],
                priority: priority
            });
        } else {
            note = prompt(`Add to ${category}:`);
            if (!note || !note.trim()) return;
            note = note.trim();
        }
        
        try {
            const response = await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/board/add`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    category: category,
                    note: note
                })
            });
            
            const data = await response.json();
            this.focusBoard = this.normalizeFocusBoard(data.focus_board);
            this.updateFocusUI();
            this.addSystemMessage(`Added to ${category}`);
        } catch (error) {
            console.error('Failed to add to focus board:', error);
        }
    };

    VeraChat.prototype.editBoardItem = async function(category, index) {
        const items = this.focusBoard[category];
        if (!items || index >= items.length) return;
        
        const item = items[index];
        const currentText = category === 'actions' ? 
            this.parseActionItem(item).description : 
            this.parseGenericItem(item).text;
        
        const newText = prompt(`Edit ${category} item:`, currentText);
        
        if (newText === null || newText.trim() === currentText) return;
        
        // Update locally first for immediate feedback
        if (category === 'actions') {
            const action = this.parseActionItem(item);
            action.description = newText.trim();
            items[index] = { 
                note: JSON.stringify(action),
                timestamp: new Date().toISOString() 
            };
        } else {
            items[index] = { 
                note: newText.trim(), 
                timestamp: new Date().toISOString() 
            };
        }
        
        this.updateFocusUI();
        this.addSystemMessage(`Updated ${category} item`);
        
        // Persist to backend
        await this._syncBoardToBackend();
    };

    VeraChat.prototype.deleteBoardItem = async function(category, index) {
        if (!confirm('Delete this item?')) return;
        
        const items = this.focusBoard[category];
        if (!items || index >= items.length) return;
        
        // Delete locally first for immediate feedback
        const deletedItem = items.splice(index, 1)[0];
        this.updateFocusUI();
        
        // Sync to backend by rebuilding the category via API
        try {
            // Clear the category on backend
            const clearResponse = await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/board/clear`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ category: category })
            });
            
            // Re-add remaining items
            for (const item of items) {
                const noteText = typeof item === 'object' && item.note ? item.note : 
                               typeof item === 'object' ? JSON.stringify(item) : 
                               String(item);
                
                await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/board/add`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        category: category,
                        note: noteText
                    })
                });
            }
            
            this.addSystemMessage(`✓ Deleted ${category} item`);
            await this.loadFocusStatus(); // Reload to ensure sync
        } catch (error) {
            console.error('Failed to delete item:', error);
            this.addSystemMessage(`Error deleting item: ${error.message}`);
        }
    };

    VeraChat.prototype.moveToCompleted = async function(category, index) {
        const items = this.focusBoard[category];
        if (!items || index >= items.length) return;
        
        // Get the item
        const item = items[index];
        const completedItem = typeof item === 'object' ? {...item} : { note: item };
        completedItem.completed_at = new Date().toISOString();
        completedItem.original_category = category;
        
        // Add to completed via API
        try {
            await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/board/add`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    category: 'completed',
                    note: JSON.stringify(completedItem)
                })
            });
            
            // Now delete from original category
            await this.deleteBoardItem(category, index);
            
            this.addSystemMessage(`✓ Moved to completed`);
        } catch (error) {
            console.error('Failed to move to completed:', error);
            this.addSystemMessage(`Error: ${error.message}`);
        }
    };

    VeraChat.prototype.clearCategory = async function(category) {
        if (!confirm(`Clear all items in ${category}?`)) return;
        
        try {
            // Try to clear via API if endpoint exists
            const response = await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/board/clear`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ category: category })
            });
            
            // Clear locally
            this.focusBoard[category] = [];
            this.updateFocusUI();
            this.addSystemMessage(`✓ Cleared ${category}`);
            
        } catch (error) {
            // Fallback: delete items one by one
            console.log('Clear endpoint not available, clearing manually');
            const items = this.focusBoard[category] || [];
            
            for (let i = items.length - 1; i >= 0; i--) {
                items.splice(i, 1);
            }
            
            this.focusBoard[category] = [];
            this.updateFocusUI();
            this.addSystemMessage(`✓ Cleared ${category}`);
        }
    };

    // Helper to sync entire board state to backend
    VeraChat.prototype._syncBoardToBackend = async function() {
        if (!this.sessionId) return;
        
        try {
            // Use save endpoint to persist current state
            await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/save`);
            console.log('Board synced to backend');
        } catch (error) {
            console.error('Failed to sync board to backend:', error);
        }
    };

    VeraChat.prototype.executeAction = async function(index) {
        const action = this.focusBoard.actions[index];
        if (!action) return;
        
        const parsed = this.parseActionItem(action);
        
        if (confirm(`Execute action: ${parsed.description}?`)) {
            this.addSystemMessage(`⚡ Executing: ${parsed.description}`);
            // Move to completed
            await this.moveToCompleted('actions', index);
        }
    };

    VeraChat.prototype.saveFocusBoard = async function() {
        if (!this.sessionId) return;
        
        try {
            const response = await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/save`);
            const data = await response.json();
            this.addSystemMessage(`💾 Focus board saved`);
        } catch (error) {
            console.error('Failed to save focus board:', error);
            this.addSystemMessage('Error saving focus board');
        }
    };
        // ============================================================
    // FOCUS BOARD MENU METHODS
    // ============================================================
    
    VeraChat.prototype.showFocusBoardMenu = async function() {
        if (!this.sessionId) return;
        
        try {
            // First, get the list of saved boards from the file system
            const fileListResponse = await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/boards/list`);
            const fileData = await fileListResponse.json();
            
            // Then get the history from Neo4j memory
            const historyResponse = await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/history`);
            const historyData = await historyResponse.json();
            
            this.showFocusBoardSelectionModal(fileData.boards || [], historyData.history || []);
            
        } catch (error) {
            console.error('Failed to load focus board list:', error);
            this.addSystemMessage('Error loading saved focus boards');
        }
    };
    
    VeraChat.prototype.showFocusBoardSelectionModal = function(fileBoards, historyBoards) {
        // Remove existing modal if any
        const existingModal = document.getElementById('focusBoardModal');
        if (existingModal) existingModal.remove();
        
        // Create modal overlay
        const modal = document.createElement('div');
        modal.id = 'focusBoardModal';
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
        
        // Create modal content
        const modalContent = document.createElement('div');
        modalContent.style.cssText = `
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
                <h2 style="margin: 0; color: #e2e8f0; font-size: 20px;">📂 Load Focus Board</h2>
                <button onclick="document.getElementById('focusBoardModal').remove()" 
                        style="background: transparent; border: none; color: #94a3b8; font-size: 24px; cursor: pointer; padding: 0; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;"
                        onmouseover="this.style.color='#e2e8f0'" onmouseout="this.style.color='#94a3b8'">
                    ×
                </button>
            </div>
        `;
        
        // Tab buttons
        html += `
            <div style="display: flex; gap: 8px; margin-bottom: 16px; border-bottom: 2px solid #334155; padding-bottom: 8px;">
                <button id="tabFileBoards" class="focus-tab-btn active" onclick="app.switchFocusBoardTab('file')" 
                        style="padding: 8px 16px; background: #3b82f6; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 13px;">
                    📁 Saved Files (${fileBoards.length})
                </button>
                <button id="tabHistoryBoards" class="focus-tab-btn" onclick="app.switchFocusBoardTab('history')" 
                        style="padding: 8px 16px; background: #334155; color: #94a3b8; border: none; border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 13px;">
                    🕒 Session History (${historyBoards.length})
                </button>
            </div>
        `;
        
        // File boards tab
        html += `<div id="fileBoardsTab" class="focus-board-tab">`;
        
        if (fileBoards.length === 0) {
            html += `
                <div style="text-align: center; padding: 40px; color: #64748b;">
                    <div style="font-size: 48px; margin-bottom: 16px;">📂</div>
                    <div style="font-size: 14px;">No saved focus boards found</div>
                </div>
            `;
        } else {
            html += `<div style="display: flex; flex-direction: column; gap: 12px;">`;
            
            fileBoards.forEach((board, idx) => {
                const focusText = board.focus || 'Untitled';
                const createdDate = board.created_at ? new Date(board.created_at).toLocaleString() : 'Unknown date';
                
                html += `
                    <div style="background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 16px; cursor: pointer; transition: all 0.2s;"
                         onmouseover="this.style.borderColor='#3b82f6'; this.style.background='#1e293b';"
                         onmouseout="this.style.borderColor='#334155'; this.style.background='#0f172a';"
                         onclick="app.loadFocusBoardFromFile('${this.escapeHtml(board.filename)}')">
                        <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 8px;">
                            <div style="flex: 1;">
                                <div style="color: #e2e8f0; font-weight: 600; font-size: 14px; margin-bottom: 4px;">
                                    🎯 ${this.escapeHtml(focusText)}
                                </div>
                                <div style="color: #64748b; font-size: 11px;">
                                    📅 ${createdDate}
                                </div>
                            </div>
                            <button onclick="event.stopPropagation(); app.deleteFocusBoardFile('${this.escapeHtml(board.filename)}', ${idx})"
                                    style="background: #ef4444; color: white; border: none; padding: 4px 8px; border-radius: 4px; font-size: 11px; cursor: pointer;"
                                    onmouseover="this.style.background='#dc2626'"
                                    onmouseout="this.style.background='#ef4444'">
                                🗑️ Delete
                            </button>
                        </div>
                        ${board.project_id ? `
                            <div style="color: #94a3b8; font-size: 11px; margin-top: 4px;">
                                🔗 Project: ${this.escapeHtml(board.project_id)}
                            </div>
                        ` : ''}
                    </div>
                `;
            });
            
            html += `</div>`;
        }
        
        html += `</div>`;
        
        // History boards tab
        html += `<div id="historyBoardsTab" class="focus-board-tab" style="display: none;">`;
        
        if (historyBoards.length === 0) {
            html += `
                <div style="text-align: center; padding: 40px; color: #64748b;">
                    <div style="font-size: 48px; margin-bottom: 16px;">🕒</div>
                    <div style="font-size: 14px;">No session history found</div>
                </div>
            `;
        } else {
            html += `<div style="display: flex; flex-direction: column; gap: 12px;">`;
            
            historyBoards.forEach((board, idx) => {
                const focusText = board.focus || 'Untitled';
                const savedDate = board.saved_at ? new Date(board.saved_at).toLocaleString() : 'Unknown date';
                const itemCount = board.board_items || 0;
                
                html += `
                    <div style="background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 16px; cursor: pointer; transition: all 0.2s;"
                         onmouseover="this.style.borderColor='#8b5cf6'; this.style.background='#1e293b';"
                         onmouseout="this.style.borderColor='#334155'; this.style.background='#0f172a';"
                         onclick="app.loadFocusBoardFromHistory('${this.escapeHtml(board.saved_at)}')">
                        <div style="display: flex; justify-content: space-between; align-items: start;">
                            <div style="flex: 1;">
                                <div style="color: #e2e8f0; font-weight: 600; font-size: 14px; margin-bottom: 4px;">
                                    🎯 ${this.escapeHtml(focusText)}
                                </div>
                                <div style="color: #64748b; font-size: 11px; margin-bottom: 4px;">
                                    🕒 ${savedDate}
                                </div>
                                <div style="color: #94a3b8; font-size: 11px;">
                                    📋 ${itemCount} items
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            });
            
            html += `</div>`;
        }
        
        html += `</div>`;
        
        modalContent.innerHTML = html;
        modal.appendChild(modalContent);
        document.body.appendChild(modal);
        
        // Close on outside click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.remove();
            }
        });
    };
    
    VeraChat.prototype.switchFocusBoardTab = function(tab) {
        // Update button styles
        const fileBtn = document.getElementById('tabFileBoards');
        const historyBtn = document.getElementById('tabHistoryBoards');
        
        if (tab === 'file') {
            fileBtn.style.background = '#3b82f6';
            fileBtn.style.color = 'white';
            historyBtn.style.background = '#334155';
            historyBtn.style.color = '#94a3b8';
            
            document.getElementById('fileBoardsTab').style.display = 'block';
            document.getElementById('historyBoardsTab').style.display = 'none';
        } else {
            historyBtn.style.background = '#8b5cf6';
            historyBtn.style.color = 'white';
            fileBtn.style.background = '#334155';
            fileBtn.style.color = '#94a3b8';
            
            document.getElementById('historyBoardsTab').style.display = 'block';
            document.getElementById('fileBoardsTab').style.display = 'none';
        }
    };
    
    VeraChat.prototype.loadFocusBoardFromFile = async function(filename) {
        if (!this.sessionId) return;
        
        try {
            const response = await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/boards/load`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filename: filename })
            });
            
            const data = await response.json();
            
            if (data.status === 'success') {
                this.currentFocus = data.focus;
                this.focusBoard = this.normalizeFocusBoard(data.focus_board);
                this.updateFocusUI();
                
                // Close modal
                const modal = document.getElementById('focusBoardModal');
                if (modal) modal.remove();
                
                this.addSystemMessage(`📂 Loaded focus board: ${filename}`);
            } else {
                this.addSystemMessage(`Error: ${data.message}`);
            }
        } catch (error) {
            console.error('Failed to load focus board:', error);
            this.addSystemMessage('Error loading focus board');
        }
    };
    
    VeraChat.prototype.loadFocusBoardFromHistory = async function(savedAt) {
        if (!this.sessionId) return;
        
        try {
            const response = await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/load`);
            const data = await response.json();
            
            if (data.status === 'loaded') {
                this.currentFocus = data.focus_state.focus;
                this.focusBoard = this.normalizeFocusBoard(data.focus_state.focus_board);
                this.updateFocusUI();
                
                // Close modal
                const modal = document.getElementById('focusBoardModal');
                if (modal) modal.remove();
                
                this.addSystemMessage(`🕒 Loaded focus state from ${new Date(data.loaded_from).toLocaleString()}`);
            } else {
                this.addSystemMessage('No saved focus state found');
            }
        } catch (error) {
            console.error('Failed to load focus state:', error);
            this.addSystemMessage('Error loading focus state');
        }
    };
    
    VeraChat.prototype.deleteFocusBoardFile = async function(filename, index) {
        if (!confirm(`Delete focus board: ${filename}?`)) return;
        
        try {
            const response = await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/boards/delete`, {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filename: filename })
            });
            
            const data = await response.json();
            
            if (data.status === 'success') {
                this.addSystemMessage(`🗑️ Deleted: ${filename}`);
                // Refresh the modal
                this.showFocusBoardMenu();
            } else {
                this.addSystemMessage(`Error: ${data.message}`);
            }
        } catch (error) {
            console.error('Failed to delete focus board:', error);
            this.addSystemMessage('Error deleting focus board');
        }
    };

})();