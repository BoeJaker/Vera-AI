(() => {
    // Add CSS for drag and drop
    const style = document.createElement('style');
    style.textContent = `
        .draggable-item {
            transition: opacity 0.2s, transform 0.1s;
        }
        
        .draggable-item:hover {
            transform: translateX(2px);
        }
        
        .drop-zone {
            transition: border-color 0.2s, background 0.2s;
        }
    `;
    document.head.appendChild(style);
    
    // ============================================================
    // GRANULAR WORKFLOW CONTROL METHODS
    // ============================================================
    VeraChat.prototype.runIdeasStage = async function() {
        if (!this.sessionId || !this.currentFocus) return;
        
        try {
            await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/stage/ideas`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({})
            });
            this.addSystemMessage('💡 Generating ideas...');
        } catch (error) {
            console.error('Failed to run ideas stage:', error);
            this.addSystemMessage('Error running ideas stage');
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
    
    VeraChat.prototype.runNextStepsStage = async function() {
        if (!this.sessionId || !this.currentFocus) return;
        
        try {
            await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/stage/next_steps`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({})
            });
            this.addSystemMessage('→ Generating next steps...');
        } catch (error) {
            console.error('Failed to run next steps stage:', error);
            this.addSystemMessage('Error running next steps stage');
        }
    };
    
    VeraChat.prototype.runActionsStage = async function() {
        if (!this.sessionId || !this.currentFocus) return;
        
        try {
            await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/stage/actions`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({})
            });
            this.addSystemMessage('⚡ Generating actions...');
        } catch (error) {
            console.error('Failed to run actions stage:', error);
            this.addSystemMessage('Error running actions stage');
        }
    };
    
    VeraChat.prototype.runExecuteStage = async function() {
        if (!this.sessionId || !this.currentFocus) return;
        
        const maxStr = prompt('Max actions to execute:', '2');
        const max = parseInt(maxStr) || 2;
        
        const priority = prompt('Priority filter (high/medium/low/all):', 'high');
        const priorityValue = priority === 'all' ? 'all' : priority;
        
        try {
            await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/stage/execute`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    max_executions: max,
                    priority: priorityValue
                })
            });
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
            const response = await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/action/execute`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    action: parsed,
                    index: index
                })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            this.addSystemMessage(`⚡ Executing: ${parsed.description.substring(0, 50)}...`);
            
        } catch (error) {
            console.error('Failed to execute action:', error);
            this.addSystemMessage(`Error executing action: ${error.message}`);
        }
    };
    
    VeraChat.prototype.stopCurrentStage = async function() {
        if (!this.sessionId) return;
        
        try {
            await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/stage/stop`, {
                method: 'POST'
            });
            this.addSystemMessage('⏹️ Stop signal sent');
        } catch (error) {
            console.error('Failed to stop stage:', error);
            this.addSystemMessage('Error stopping stage');
        }
    };
    
    // ============================================================
    // WEBSOCKET & EVENT HANDLERS
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

    VeraChat.prototype._focusBoardsEqual = function(board1, board2) {
        if (!board1 && !board2) return true;
        if (!board1 || !board2) return false;
        
        const keys = ['actions', 'progress', 'next_steps', 'issues', 'ideas', 'completed'];
        
        for (const key of keys) {
            const arr1 = board1[key] || [];
            const arr2 = board2[key] || [];
            
            if (arr1.length !== arr2.length) return false;
            if (JSON.stringify(arr1) !== JSON.stringify(arr2)) return false;
        }
        
        return true;
    };

    VeraChat.prototype.handleFocusEvent = function(data) {
        console.log('Focus event:', data.type);
        
        const container = document.getElementById('tab-focus');
        const scrollPos = container ? container.scrollTop : 0;
                
        if (data.type.startsWith('stage_')) {
            switch (data.type) {
                case 'stage_started':
                    this.addSystemMessage(`▶️ Started ${data.data.stage} stage`);
                    break;
                case 'stage_completed':
                    this.addSystemMessage(`✓ Completed ${data.data.stage} stage (${data.data.count} items)`);
                    this.loadFocusStatus();
                    break;
                case 'stage_error':
                    this.addSystemMessage(`❌ Error in ${data.data.stage} stage: ${data.data.error}`);
                    break;
                case 'stage_stopped':
                    this.addSystemMessage('⏹️ Stage stopped');
                    break;
            }
        } else {
            switch (data.type) {
                case 'focus_status':
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
    // DATA NORMALIZATION & PARSING
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

    VeraChat.prototype.expandActionArray = function(item) {
        let actions = [];
        
        if (typeof item === 'object' && item !== null) {
            if (item.description) {
                actions.push(item);
            } else if (item.note) {
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
    // UI RENDERING
    // ============================================================
    
    VeraChat.prototype.initCollapsedState = function() {
        if (!this.collapsedSections) {
            this.collapsedSections = {};
        }
    };
    
    VeraChat.prototype.toggleSection = function(category) {
        this.initCollapsedState();
        this.collapsedSections[category] = !this.collapsedSections[category];
        this.updateFocusUI();
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
            <div class="focusContent" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
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
        
        html += this.renderFocusSection();
        html += `<div style="display: grid; grid-template-columns: 1fr; gap: 16px;">`;
        
        const categories = [
            { key: 'ideas', label: 'Ideas', color: '#8b5cf6', icon: '💡', hasStageControl: true },
            { key: 'next_steps', label: 'Next Steps', color: '#f59e0b', icon: '→', hasStageControl: true },
            { key: 'actions', label: 'Actions', color: '#3b82f6', icon: '⚡', hasStageControl: true },
            { key: 'progress', label: 'Progress', color: '#10b981', icon: '✓', hasStageControl: false },
            { key: 'issues', label: 'Issues', color: '#ef4444', icon: '⚠', hasStageControl: false },
            { key: 'completed', label: 'Completed', color: '#6b7280', icon: '✔', hasStageControl: false }
        ];
        
        categories.forEach(cat => {
            html += this.renderCategory(cat);
        });
        
        html += `</div></div>`;
        container.innerHTML = html;
        
        this.initializeDragAndDrop();
        
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
        this.initCollapsedState();
        const isCollapsed = this.collapsedSections[cat.key];
        
        let items = this.focusBoard[cat.key] || [];
        
        if (cat.key === 'actions') {
            let expandedItems = [];
            items.forEach(item => {
                const expanded = this.expandActionArray(item);
                expandedItems.push(...expanded);
            });
            items = expandedItems;
            this.focusBoard[cat.key] = expandedItems;
        }
        
        let html = `
            <div class="focusContent" style="border-radius: 8px; padding: 16px; border-left: 4px solid ${cat.color}; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                    <div style="display: flex; align-items: center; gap: 8px; flex: 1;">
                        <button class="panel-btn" onclick="app.toggleSection('${cat.key}')" 
                                style="font-size: 11px; padding: 4px 8px;">
                            ${isCollapsed ? '▶' : '▼'}
                        </button>
                        <div style="font-weight: 600; color: #e2e8f0; font-size: 14px;">
                            ${cat.icon} ${cat.label}
                            <span style="color: #94a3b8; font-weight: normal; font-size: 12px; margin-left: 8px;">(${items.length})</span>
                        </div>
                    </div>
                    <div style="display: flex; gap: 6px; align-items: center;">
        `;
        
        if (cat.hasStageControl && this.currentFocus) {
            const stageMap = {
                'ideas': 'runIdeasStage',
                'next_steps': 'runNextStepsStage',
                'actions': 'runActionsStage'
            };
            
            if (stageMap[cat.key]) {
                html += `<button class="panel-btn" style="font-size: 11px; padding: 4px 8px;" onclick="app.${stageMap[cat.key]}()">▶️ Generate</button>`;
            }
        }
        
        // Execute button for actions (always show if focus is set)
        if (cat.key === 'actions' && this.currentFocus) {
            html += `<button class="panel-btn" style="font-size: 11px; padding: 4px 8px; background: #34d399;" onclick="app.runExecuteStage()">🚀 Execute All</button>`;
        }
        
        html += `
                        <button class="panel-btn" style="font-size: 11px; padding: 4px 8px;" onclick="app.showAddItemForm('${cat.key}')">+ Add</button>
                        ${items.length > 0 ? `<button class="panel-btn" style="font-size: 11px; padding: 4px 8px;" onclick="app.clearCategory('${cat.key}')">🗑️ Clear</button>` : ''}
                    </div>
                </div>
        `;
        
        if (!isCollapsed) {
            html += `
                <div id="add-item-form-${cat.key}" style="display: none; margin-bottom: 12px; padding: 12px; background: rgba(15, 23, 42, 0.5); border-radius: 6px;">
                    ${cat.key === 'actions' ? this.renderActionForm(cat.key) : this.renderGenericForm(cat.key)}
                </div>
                <div id="category-items-${cat.key}" class="drop-zone" data-category="${cat.key}" style="display: flex; flex-direction: column; gap: 8px; min-height: 60px; padding: 8px; border-radius: 6px; border: 2px dashed transparent;">
            `;
            
            if (items.length === 0) {
                html += `<div style="color: #64748b; font-size: 12px; font-style: italic; text-align: center; padding: 8px;">No ${cat.label.toLowerCase()} yet. Click "+ Add" to create one.</div>`;
            } else {
                if (cat.key === 'actions') {
                    items.forEach((item, idx) => {
                        html += this.renderActionItem(item, idx, cat.color, cat.key);
                    });
                } else {
                    items.forEach((item, idx) => {
                        html += this.renderGenericItem(item, idx, cat.key, cat.color);
                    });
                }
            }
            
            html += `</div>`;
        }
        
        html += `</div>`;
        return html;
    };

    VeraChat.prototype.renderActionForm = function(category) {
        return `
            <div style="display: flex; flex-direction: column; gap: 8px;">
                <input type="text" id="action-desc-${category}" placeholder="Action description..." 
                       style="background: #1e293b; color: #e2e8f0; border: 1px solid #334155; padding: 8px; border-radius: 4px; font-size: 13px; width: 100%;">
                <select id="action-priority-${category}" 
                        style="background: #1e293b; color: #e2e8f0; border: 1px solid #334155; padding: 8px; border-radius: 4px; font-size: 13px;">
                    <option value="high">High Priority</option>
                    <option value="medium" selected>Medium Priority</option>
                    <option value="low">Low Priority</option>
                </select>
                <div style="display: flex; gap: 6px;">
                    <button class="panel-btn" onclick="app.submitActionForm('${category}')" 
                            style="flex: 1; font-size: 12px; padding: 6px;">✓ Add Action</button>
                    <button class="panel-btn" onclick="app.hideAddItemForm('${category}')" 
                            style="font-size: 12px; padding: 6px;">✕ Cancel</button>
                </div>
            </div>
        `;
    };
    
    VeraChat.prototype.renderGenericForm = function(category) {
        return `
            <div style="display: flex; flex-direction: column; gap: 8px;">
                <textarea id="item-text-${category}" placeholder="Enter text..." rows="3"
                          style="background: #1e293b; color: #e2e8f0; border: 1px solid #334155; padding: 8px; border-radius: 4px; font-size: 13px; width: 100%; resize: vertical;"></textarea>
                <div style="display: flex; gap: 6px;">
                    <button class="panel-btn" onclick="app.submitGenericForm('${category}')" 
                            style="flex: 1; font-size: 12px; padding: 6px;">✓ Add Item</button>
                    <button class="panel-btn" onclick="app.hideAddItemForm('${category}')" 
                            style="font-size: 12px; padding: 6px;">✕ Cancel</button>
                </div>
            </div>
        `;
    };

    VeraChat.prototype.renderActionItem = function(item, idx, color, category) {
        const action = this.parseActionItem(item);
        const priorityColors = {
            high: '#ef4444',
            medium: '#f59e0b',
            low: '#6b7280'
        };
        
        const itemId = `item-${category}-${idx}`;
        
        return `
            <div id="${itemId}" class="draggable-item" draggable="true" 
                 data-category="${category}" data-index="${idx}"
                 ondragstart="app.handleDragStart(event)"
                 ondragend="app.handleDragEnd(event)"
                 style="padding: 12px; border-radius: 6px; border-left: 3px solid ${color}; background: rgba(15, 23, 42, 0.5); cursor: move;">
                <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 8px;">
                    <div style="color: #cbd5e1; font-size: 13px; flex: 1; word-wrap: break-word; white-space: pre-wrap;">${this.escapeHtml(action.description)}</div>
                    <span style="padding: 2px 6px; background: ${priorityColors[action.priority]}; color: white; border-radius: 4px; font-size: 10px; font-weight: 600; margin-left: 8px; white-space: nowrap;">
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
                <div style="display: flex; gap: 6px; margin-top: 8px; flex-wrap: wrap;">
                    <button class="panel-btn" style="font-size: 10px; padding: 3px 6px;" onclick="app.executeActionDirectly(${idx})">▶️ Execute</button>
                    <button class="panel-btn" style="font-size: 10px; padding: 3px 6px;" onclick="app.editBoardItem('${category}', ${idx})">✏️ Edit</button>
                    <button class="panel-btn" style="font-size: 10px; padding: 3px 6px;" onclick="app.deleteBoardItem('${category}', ${idx})">🗑️</button>
                    <button class="panel-btn" style="font-size: 10px; padding: 3px 6px;" onclick="app.moveToCompleted('${category}', ${idx})">✓ Complete</button>
                </div>
            </div>
        `;
    };

    VeraChat.prototype.renderGenericItem = function(item, idx, category, color) {
        const parsed = this.parseGenericItem(item);
        const itemId = `item-${category}-${idx}`;
        const isDraggable = category === 'next_steps';
        
        return `
            <div id="${itemId}" class="${isDraggable ? 'draggable-item' : ''}" 
                 ${isDraggable ? 'draggable="true"' : ''}
                 data-category="${category}" data-index="${idx}"
                 ${isDraggable ? 'ondragstart="app.handleDragStart(event)" ondragend="app.handleDragEnd(event)"' : ''}
                 style="padding: 10px 12px; border-radius: 6px; border-left: 3px solid ${color}; background: rgba(15, 23, 42, 0.5); ${isDraggable ? 'cursor: move;' : ''}">
                <div style="display: flex; justify-content: space-between; align-items: start;">
                    <div style="color: #cbd5e1; font-size: 13px; flex: 1; word-wrap: break-word; white-space: pre-wrap;">${this.escapeHtml(parsed.text)}</div>
                    <div style="display: flex; gap: 4px; margin-left: 8px; flex-shrink: 0;">
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
    // FORM HANDLERS
    // ============================================================
    
    VeraChat.prototype.showAddItemForm = function(category) {
        const form = document.getElementById(`add-item-form-${category}`);
        if (form) {
            form.style.display = 'block';
            const input = category === 'actions' ? 
                document.getElementById(`action-desc-${category}`) : 
                document.getElementById(`item-text-${category}`);
            if (input) setTimeout(() => input.focus(), 100);
        }
    };
    
    VeraChat.prototype.hideAddItemForm = function(category) {
        const form = document.getElementById(`add-item-form-${category}`);
        if (form) {
            form.style.display = 'none';
            if (category === 'actions') {
                const desc = document.getElementById(`action-desc-${category}`);
                const priority = document.getElementById(`action-priority-${category}`);
                if (desc) desc.value = '';
                if (priority) priority.value = 'medium';
            } else {
                const text = document.getElementById(`item-text-${category}`);
                if (text) text.value = '';
            }
        }
    };
    
    VeraChat.prototype.submitActionForm = async function(category) {
        const descInput = document.getElementById(`action-desc-${category}`);
        const priorityInput = document.getElementById(`action-priority-${category}`);
        
        const description = descInput ? descInput.value.trim() : '';
        const priority = priorityInput ? priorityInput.value : 'medium';
        
        if (!description) {
            this.addSystemMessage('Please enter an action description');
            return;
        }
        
        const note = JSON.stringify({
            description: description,
            tools: [],
            priority: priority
        });
        
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
            this.hideAddItemForm(category);
            this.updateFocusUI();
            this.addSystemMessage(`Added action: ${description}`);
        } catch (error) {
            console.error('Failed to add action:', error);
            this.addSystemMessage('Error adding action');
        }
    };
    
    VeraChat.prototype.submitGenericForm = async function(category) {
        const textInput = document.getElementById(`item-text-${category}`);
        const text = textInput ? textInput.value.trim() : '';
        
        if (!text) {
            this.addSystemMessage('Please enter some text');
            return;
        }
        
        try {
            const response = await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/board/add`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    category: category,
                    note: text
                })
            });
            
            const data = await response.json();
            this.focusBoard = this.normalizeFocusBoard(data.focus_board);
            this.hideAddItemForm(category);
            this.updateFocusUI();
            this.addSystemMessage(`Added to ${category}`);
        } catch (error) {
            console.error('Failed to add item:', error);
            this.addSystemMessage('Error adding item');
        }
    };

    // ============================================================
    // DRAG AND DROP
    // ============================================================
    
    VeraChat.prototype.initializeDragAndDrop = function() {
        const dropZones = document.querySelectorAll('.drop-zone');
        
        dropZones.forEach(zone => {
            zone.addEventListener('dragover', (e) => {
                e.preventDefault();
                const category = zone.dataset.category;
                
                if (category === 'completed') {
                    zone.style.borderColor = '#10b981';
                    zone.style.background = 'rgba(16, 185, 129, 0.1)';
                }
            });
            
            zone.addEventListener('dragleave', (e) => {
                e.preventDefault();
                zone.style.borderColor = 'transparent';
                zone.style.background = 'transparent';
            });
            
            zone.addEventListener('drop', (e) => {
                e.preventDefault();
                zone.style.borderColor = 'transparent';
                zone.style.background = 'transparent';
                
                const targetCategory = zone.dataset.category;
                
                if (targetCategory !== 'completed') return;
                
                const sourceCategory = e.dataTransfer.getData('category');
                const sourceIndex = parseInt(e.dataTransfer.getData('index'));
                
                if (sourceCategory === 'actions' || sourceCategory === 'next_steps') {
                    this.moveToCompleted(sourceCategory, sourceIndex);
                }
            });
        });
    };
    
    VeraChat.prototype.handleDragStart = function(e) {
        const item = e.target.closest('.draggable-item');
        if (!item) return;
        
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('category', item.dataset.category);
        e.dataTransfer.setData('index', item.dataset.index);
        
        item.style.opacity = '0.5';
    };
    
    VeraChat.prototype.handleDragEnd = function(e) {
        const item = e.target.closest('.draggable-item');
        if (!item) return;
        
        item.style.opacity = '1';
    };

    // ============================================================
    // EDIT/DELETE/MOVE OPERATIONS
    // ============================================================
    
    VeraChat.prototype.editBoardItem = async function(category, index) {
        const items = this.focusBoard[category];
        if (!items || index >= items.length) return;
        
        const item = items[index];
        const isAction = category === 'actions';
        
        const itemElement = document.getElementById(`item-${category}-${index}`);
        if (!itemElement) return;
        
        const currentText = isAction ? 
            this.parseActionItem(item).description : 
            this.parseGenericItem(item).text;
        
        const currentPriority = isAction ? this.parseActionItem(item).priority : null;
        
        let formHtml = `
            <div style="padding: 12px; background: rgba(15, 23, 42, 0.8); border-radius: 6px;">
        `;
        
        if (isAction) {
            formHtml += `
                <input type="text" id="edit-text-${category}-${index}" value="${this.escapeHtml(currentText)}"
                       style="background: #1e293b; color: #e2e8f0; border: 1px solid #334155; padding: 8px; border-radius: 4px; font-size: 13px; width: 100%; margin-bottom: 8px;">
                <select id="edit-priority-${category}-${index}" 
                        style="background: #1e293b; color: #e2e8f0; border: 1px solid #334155; padding: 8px; border-radius: 4px; font-size: 13px; width: 100%; margin-bottom: 8px;">
                    <option value="high" ${currentPriority === 'high' ? 'selected' : ''}>High Priority</option>
                    <option value="medium" ${currentPriority === 'medium' ? 'selected' : ''}>Medium Priority</option>
                    <option value="low" ${currentPriority === 'low' ? 'selected' : ''}>Low Priority</option>
                </select>
            `;
        } else {
            formHtml += `
                <textarea id="edit-text-${category}-${index}" rows="3"
                          style="background: #1e293b; color: #e2e8f0; border: 1px solid #334155; padding: 8px; border-radius: 4px; font-size: 13px; width: 100%; resize: vertical; margin-bottom: 8px;">${this.escapeHtml(currentText)}</textarea>
            `;
        }
        
        formHtml += `
                <div style="display: flex; gap: 6px;">
                    <button class="panel-btn" onclick="app.saveEdit('${category}', ${index})" 
                            style="flex: 1; font-size: 11px; padding: 6px;">✓ Save</button>
                    <button class="panel-btn" onclick="app.cancelEdit('${category}', ${index})" 
                            style="font-size: 11px; padding: 6px;">✕ Cancel</button>
                </div>
            </div>
        `;
        
        itemElement.dataset.originalContent = itemElement.innerHTML;
        itemElement.innerHTML = formHtml;
        
        const input = document.getElementById(`edit-text-${category}-${index}`);
        if (input) setTimeout(() => input.focus(), 100);
    };
    
    VeraChat.prototype.saveEdit = async function(category, index) {
        const textInput = document.getElementById(`edit-text-${category}-${index}`);
        const newText = textInput ? textInput.value.trim() : '';
        
        if (!newText) {
            this.addSystemMessage('Text cannot be empty');
            return;
        }
        
        const items = this.focusBoard[category];
        if (!items || index >= items.length) return;
        
        if (category === 'actions') {
            const priorityInput = document.getElementById(`edit-priority-${category}-${index}`);
            const priority = priorityInput ? priorityInput.value : 'medium';
            
            const action = this.parseActionItem(items[index]);
            action.description = newText;
            action.priority = priority;
            
            items[index] = { 
                note: JSON.stringify(action),
                timestamp: new Date().toISOString() 
            };
        } else {
            items[index] = { 
                note: newText, 
                timestamp: new Date().toISOString() 
            };
        }
        
        this.updateFocusUI();
        this.addSystemMessage(`Updated ${category} item`);
        
        await this._syncBoardToBackend();
    };
    
    VeraChat.prototype.cancelEdit = function(category, index) {
        const itemElement = document.getElementById(`item-${category}-${index}`);
        if (itemElement && itemElement.dataset.originalContent) {
            itemElement.innerHTML = itemElement.dataset.originalContent;
            delete itemElement.dataset.originalContent;
        }
    };

    VeraChat.prototype.deleteBoardItem = async function(category, index) {
        if (!confirm('Delete this item?')) return;
        
        const items = this.focusBoard[category];
        if (!items || index >= items.length) return;
        
        // Store the item to delete for logging
        const deletedItem = items[index];
        
        try {
            // First, try to use a delete endpoint if it exists
            const deleteResponse = await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/board/delete`, {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    category: category,
                    index: index
                })
            });
            
            if (deleteResponse.ok) {
                // Backend handled it - just refresh
                this.addSystemMessage(`✓ Deleted ${category} item`);
                await this.loadFocusStatus();
                return;
            }
        } catch (error) {
            console.log('Delete endpoint not available, using clear/re-add method');
        }
        
        // Fallback: Remove locally first
        items.splice(index, 1);
        
        try {
            // Clear the category
            await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/board/clear`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ category: category })
            });
            
            // Re-add remaining items ONE AT A TIME with error handling
            for (let i = 0; i < items.length; i++) {
                const item = items[i];
                const noteText = typeof item === 'object' && item.note ? item.note : 
                            typeof item === 'object' ? JSON.stringify(item) : 
                            String(item);
                
                try {
                    await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/board/add`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ 
                            category: category,
                            note: noteText
                        })
                    });
                } catch (addError) {
                    console.error(`Failed to re-add item ${i}:`, addError);
                    // Continue with other items even if one fails
                }
            }
            
            this.addSystemMessage(`✓ Deleted ${category} item`);
            
            // Refresh to ensure UI matches backend
            await this.loadFocusStatus();
            
        } catch (error) {
            console.error('Failed to delete item:', error);
            // Restore the deleted item since we failed
            items.splice(index, 0, deletedItem);
            this.updateFocusUI();
            this.addSystemMessage(`Error deleting item: ${error.message}`);
        }
    };

    VeraChat.prototype.moveToCompleted = async function(category, index) {
        const items = this.focusBoard[category];
        if (!items || index >= items.length) return;
        
        const item = items[index];
        const completedItem = typeof item === 'object' ? {...item} : { note: item };
        completedItem.completed_at = new Date().toISOString();
        completedItem.original_category = category;
        
        try {
            await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/board/add`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    category: 'completed',
                    note: JSON.stringify(completedItem)
                })
            });
            
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
            await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/board/clear`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ category: category })
            });
            
            this.focusBoard[category] = [];
            this.updateFocusUI();
            this.addSystemMessage(`✓ Cleared ${category}`);
            
        } catch (error) {
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

    VeraChat.prototype._syncBoardToBackend = async function() {
        if (!this.sessionId) return;
        
        try {
            await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/save`);
            console.log('Board synced to backend');
        } catch (error) {
            console.error('Failed to sync board to backend:', error);
        }
    };

    // ============================================================
    // API METHODS
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
    VeraChat.prototype.showSetFocusDialog = async function() {
        if (!this.sessionId) {
            this.addSystemMessage('No active session');
            return;
        }
        
        // Remove existing modal if any
        const existingModal = document.getElementById('setFocusModal');
        if (existingModal) existingModal.remove();
        
        // Fetch similar focuses
        let allSimilarFocuses = [];
        try {
            const response = await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/similar`);
            const data = await response.json();
            allSimilarFocuses = data.similar_focuses || [];
        } catch (error) {
            console.error('Failed to load similar focuses:', error);
        }
        
        // Store for filtering
        this._allSimilarFocuses = allSimilarFocuses;
        this._currentFilteredFocuses = allSimilarFocuses;
        
        this._renderSetFocusModal(allSimilarFocuses);
    };

    VeraChat.prototype._renderSetFocusModal = function(similarFocuses) {
        // Create modal overlay
        const modal = document.createElement('div');
        modal.id = 'setFocusModal';
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
            max-width: 600px;
            width: 90%;
            max-height: 80vh;
            overflow-y: auto;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
            border: 1px solid #334155;
        `;
        
        let html = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                <h2 style="margin: 0; color: #e2e8f0; font-size: 20px;">🎯 Set Focus</h2>
                <button onclick="document.getElementById('setFocusModal').remove()" 
                        style="background: transparent; border: none; color: #94a3b8; font-size: 24px; cursor: pointer; padding: 0; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;"
                        onmouseover="this.style.color='#e2e8f0'" onmouseout="this.style.color='#94a3b8'">
                    ×
                </button>
            </div>
        `;
        
        // New focus input section
        html += `
            <div style="margin-bottom: 24px; padding: 16px; background: rgba(59, 130, 246, 0.1); border: 1px solid rgba(59, 130, 246, 0.3); border-radius: 8px;">
                <label style="color: #cbd5e1; font-size: 13px; font-weight: 600; display: block; margin-bottom: 8px;">
                    ✨ Create New Focus
                </label>
                <input type="text" id="newFocusInput" placeholder="Enter your focus..." 
                    value="${this.escapeHtml(this.currentFocus || '')}"
                    style="background: #1e293b; color: #e2e8f0; border: 1px solid #334155; padding: 10px; border-radius: 6px; font-size: 14px; width: 100%; margin-bottom: 12px;">
                <button onclick="app.createNewFocus()" class="panel-btn" 
                        style="width: 100%; padding: 10px; background: #3b82f6; font-weight: 600;">
                    ✓ Create New Focus
                </button>
            </div>
        `;
        
        // Similar focuses section
        html += `<div id="similarFocusesContainer">`;
        html += this._renderSimilarFocusesList(similarFocuses);
        html += `</div>`;
        
        modalContent.innerHTML = html;
        modal.appendChild(modalContent);
        document.body.appendChild(modal);
        
        // Add input event listener for filtering
        const input = document.getElementById('newFocusInput');
        if (input) {
            input.addEventListener('input', (e) => {
                this._filterSimilarFocuses(e.target.value);
            });
            
            setTimeout(() => {
                input.focus();
                input.select();
            }, 100);
            
            // Allow Enter key to submit
            input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    this.createNewFocus();
                }
            });
        }
        
        // Close on outside click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.remove();
            }
        });
    };

    VeraChat.prototype._renderSimilarFocusesList = function(similarFocuses) {
        if (similarFocuses.length === 0) {
            return `
                <div style="text-align: center; padding: 20px; color: #64748b; font-size: 12px; border-top: 1px solid #334155;">
                    <div style="font-size: 32px; margin-bottom: 8px;">📋</div>
                    <div>No matching focuses found</div>
                </div>
            `;
        }
        
        let html = `
            <div style="border-top: 1px solid #334155; padding-top: 16px;">
                <div style="color: #cbd5e1; font-size: 13px; font-weight: 600; margin-bottom: 12px;">
                    📋 Similar Focuses (${similarFocuses.length})
                </div>
                <div style="display: flex; flex-direction: column; gap: 8px;">
        `;
        
        similarFocuses.forEach((focus, idx) => {
            const focusText = focus.focus || 'Untitled';
            const lastUsed = focus.last_used ? new Date(focus.last_used).toLocaleString() : 'Unknown';
            const itemCount = focus.total_items || 0;
            
            html += `
                <div style="background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 12px; cursor: pointer; transition: all 0.2s;"
                    onmouseover="this.style.borderColor='#8b5cf6'; this.style.background='#1e293b';"
                    onmouseout="this.style.borderColor='#334155'; this.style.background='#0f172a';"
                    onclick="app.loadSimilarFocus('${this.escapeHtml(focus.focus)}')">
                    <div style="display: flex; justify-content: space-between; align-items: start;">
                        <div style="flex: 1;">
                            <div style="color: #e2e8f0; font-weight: 600; font-size: 13px; margin-bottom: 4px;">
                                🎯 ${this.escapeHtml(focusText)}
                            </div>
                            <div style="color: #64748b; font-size: 11px; margin-bottom: 4px;">
                                🕒 Last used: ${lastUsed}
                            </div>
                            <div style="color: #94a3b8; font-size: 11px;">
                                📋 ${itemCount} items
                            </div>
                        </div>
                        <div style="padding: 4px 8px; background: #8b5cf6; color: white; border-radius: 4px; font-size: 10px; font-weight: 600; margin-left: 8px;">
                            Load
                        </div>
                    </div>
                </div>
            `;
        });
        
        html += `
                </div>
            </div>
        `;
        
        return html;
    };

    VeraChat.prototype._filterSimilarFocuses = function(searchText) {
        if (!searchText || searchText.trim() === '') {
            this._currentFilteredFocuses = this._allSimilarFocuses;
        } else {
            const searchLower = searchText.toLowerCase().trim();
            this._currentFilteredFocuses = this._allSimilarFocuses.filter(focus => {
                const focusText = (focus.focus || '').toLowerCase();
                return focusText.includes(searchLower);
            });
        }
        
        // Update the similar focuses list
        const container = document.getElementById('similarFocusesContainer');
        if (container) {
            container.innerHTML = this._renderSimilarFocusesList(this._currentFilteredFocuses);
        }
    };

    VeraChat.prototype.createNewFocus = async function() {
        const input = document.getElementById('newFocusInput');
        const focus = input ? input.value.trim() : '';
        
        if (!focus) {
            this.addSystemMessage('Please enter a focus');
            return;
        }
        
        // Force create new by passing force_new parameter
        await this.setFocusForceNew(focus);
        
        // Close the modal
        const modal = document.getElementById('setFocusModal');
        if (modal) modal.remove();
    };

    VeraChat.prototype.setFocusForceNew = async function(focus) {
        if (!this.sessionId) return;
        
        try {
            const response = await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/set`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    focus: focus,
                    force_new: true  // This tells the backend to create new, not load existing
                })
            });
            
            const data = await response.json();
            this.currentFocus = data.focus;
            this.focusBoard = this.normalizeFocusBoard(data.focus_board);
            this.updateFocusUI();
            this.addSystemMessage(`🎯 Created new focus: ${focus}`);
        } catch (error) {
            console.error('Failed to set focus:', error);
            this.addSystemMessage(`Error setting focus: ${error.message}`);
        }
    };

    VeraChat.prototype.loadSimilarFocus = async function(focusText) {
        if (!this.sessionId || !focusText) return;
        
        try {
            // First set the focus
            await this.setFocus(focusText);
            
            // Then try to load the associated board
            const response = await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/load-by-focus`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ focus: focusText })
            });
            
            if (response.ok) {
                const data = await response.json();
                if (data.status === 'loaded') {
                    this.focusBoard = this.normalizeFocusBoard(data.focus_state.focus_board);
                    this.updateFocusUI();
                    this.addSystemMessage(`✓ Loaded existing focus: ${focusText}`);
                }
            }
            
            // Close the modal
            const modal = document.getElementById('setFocusModal');
            if (modal) modal.remove();
            
        } catch (error) {
            console.error('Failed to load similar focus:', error);
            this.addSystemMessage(`Error loading focus: ${error.message}`);
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

    VeraChat.prototype.saveFocusBoard = async function() {
        if (!this.sessionId) return;
        
        try {
            await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/save`);
            this.addSystemMessage(`💾 Focus board saved`);
        } catch (error) {
            console.error('Failed to save focus board:', error);
            this.addSystemMessage('Error saving focus board');
        }
    };

    VeraChat.prototype.startProactiveThinking = async function() {
        if (!this.sessionId) return;
        
        try {
            await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/start`, {
                method: 'GET'
            });
            
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
    // FOCUS BOARD MENU METHODS
    // ============================================================
    
    VeraChat.prototype.showFocusBoardMenu = async function() {
        if (!this.sessionId) {
            this.addSystemMessage('No active session');
            return;
        }
        
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
            <div style="display: flex; gap: 12px; align-items: center; padding: 8px 12px; background: rgba(15, 23, 42, 0.5); border-radius: 6px; font-size: 11px;">
                <div style="display: flex; align-items: center; gap: 4px;">
                    <span style="color: #94a3b8;">CPU:</span>
                    <div style="width: 60px; height: 8px; background: rgba(0,0,0,0.3); border-radius: 4px; overflow: hidden;">
                        <div style="width: ${status.cpu_percent}%; height: 100%; background: ${cpuColor}; transition: width 0.3s;"></div>
                    </div>
                    <span style="color: ${cpuColor}; font-weight: 600;">${status.cpu_percent}%</span>
                </div>
                <div style="display: flex; align-items: center; gap: 4px;">
                    <span style="color: #94a3b8;">RAM:</span>
                    <div style="width: 60px; height: 8px; background: rgba(0,0,0,0.3); border-radius: 4px; overflow: hidden;">
                        <div style="width: ${status.memory_percent}%; height: 100%; background: ${memColor}; transition: width 0.3s;"></div>
                    </div>
                    <span style="color: ${memColor}; font-weight: 600;">${status.memory_percent}%</span>
                </div>
                <div style="display: flex; align-items: center; gap: 4px;">
                    <span style="color: #94a3b8;">Ollama:</span>
                    <span style="color: #60a5fa; font-weight: 600;">${status.ollama_process_count}</span>
                </div>
            </div>
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
        
        // Add resource status indicator
        const focusContent = document.querySelector('.focusContent');
        if (focusContent && !document.getElementById('resourceStatusIndicator')) {
            const indicator = document.createElement('div');
            indicator.id = 'resourceStatusIndicator';
            focusContent.insertBefore(indicator, focusContent.firstChild);
            
            // Start monitoring
            if (!this.resourceMonitorInterval) {
                this.initResourceMonitoring();
            }
        }
        
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
                🔗 Resources
            </button>
            <button class="panel-btn" onclick="app.showStageExecutionModal()" style="padding: 6px 12px; font-size: 12px;">
                🎯 Stages
            </button>
            <button class="panel-btn" onclick="app.showCalendarModal()" style="padding: 6px 12px; font-size: 12px;">
                📅 Calendar
            </button>
            <button class="panel-btn" onclick="app.showBackgroundServicePanel()" style="padding: 6px 12px; font-size: 12px;">
                🤖 Background
            </button>
            <button class="panel-btn" onclick="app.showResourceConfigModal()" style="padding: 6px 12px; font-size: 12px;">
                ⚙️ Limits
            </button>
        `;
        
        focusContent.appendChild(controls);
    };
    
    // Clean up on session change
    const originalInit = VeraChat.prototype.init;
    VeraChat.prototype.init = function() {
        if (originalInit) {
            originalInit.call(this);
        }
        
        // Clean up intervals
        if (this.resourceMonitorInterval) {
            clearInterval(this.resourceMonitorInterval);
            this.resourceMonitorInterval = null;
        }
    };

})();