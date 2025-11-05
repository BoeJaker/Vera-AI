(() => {


    // VeraChat.prototype.addToFocusBoard = async function(category) {
    //     let note = '';
    //     let priority = 'medium';
        
    //     // Special handling for actions - ask for priority
    //     if (category === 'actions') {
    //         note = prompt(`Enter action description:`);
    //         if (!note || !note.trim()) return;
            
    //         const priorityInput = prompt('Priority (high/medium/low):', 'medium');
    //         priority = (priorityInput || 'medium').toLowerCase();
    //         if (!['high', 'medium', 'low'].includes(priority)) {
    //             priority = 'medium';
    //         }
            
    //         // Format as action object
    //         note = JSON.stringify({
    //             description: note.trim(),
    //             tools: [],
    //             priority: priority
    //         });
    //     } else {
    //         note = prompt(`Add to ${category}:`);
    //         if (!note || !note.trim()) return;
    //         note = note.trim();
    //     }
        
    //     try {
    //         const response = await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/board/add`, {
    //             method: 'POST',
    //             headers: { 'Content-Type': 'application/json' },
    //             body: JSON.stringify({ 
    //                 category: category,
    //                 note: note
    //             })
    //         });
            
    //         const data = await response.json();
    //         this.focusBoard = this.normalizeFocusBoard(data.focus_board);
    //         this.updateFocusUI();
    //         this.addSystemMessage(`Added to ${category}`);
    //     } catch (error) {
    //         console.error('Failed to add to focus board:', error);
    //     }
    // };

    // VeraChat.prototype.editBoardItem = async function(category, index) {
    //     const items = this.focusBoard[category];
    //     if (!items || index >= items.length) return;
        
    //     const item = items[index];
    //     const currentText = category === 'actions' ? 
    //         this.parseActionItem(item).description : 
    //         this.parseGenericItem(item).text;
        
    //     const newText = prompt(`Edit ${category} item:`, currentText);
        
    //     if (newText === null || newText.trim() === currentText) return;
        
    //     // Update locally first for immediate feedback
    //     if (category === 'actions') {
    //         const action = this.parseActionItem(item);
    //         action.description = newText.trim();
    //         items[index] = { 
    //             note: JSON.stringify(action),
    //             timestamp: new Date().toISOString() 
    //         };
    //     } else {
    //         items[index] = { 
    //             note: newText.trim(), 
    //             timestamp: new Date().toISOString() 
    //         };
    //     }
        
    //     this.updateFocusUI();
    //     this.addSystemMessage(`Updated ${category} item`);
        
    //     // Persist to backend
    //     await this._syncBoardToBackend();
    // };

    // VeraChat.prototype.deleteBoardItem = async function(category, index) {
    //     if (!confirm('Delete this item?')) return;
        
    //     const items = this.focusBoard[category];
    //     if (!items || index >= items.length) return;
        
    //     // Delete locally first for immediate feedback
    //     const deletedItem = items.splice(index, 1)[0];
    //     this.updateFocusUI();
        
    //     // Sync to backend by rebuilding the category via API
    //     try {
    //         // Clear the category on backend
    //         const clearResponse = await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/board/clear`, {
    //             method: 'POST',
    //             headers: { 'Content-Type': 'application/json' },
    //             body: JSON.stringify({ category: category })
    //         });
            
    //         // Re-add remaining items
    //         for (const item of items) {
    //             const noteText = typeof item === 'object' && item.note ? item.note : 
    //                            typeof item === 'object' ? JSON.stringify(item) : 
    //                            String(item);
                
    //             await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/board/add`, {
    //                 method: 'POST',
    //                 headers: { 'Content-Type': 'application/json' },
    //                 body: JSON.stringify({ 
    //                     category: category,
    //                     note: noteText
    //                 })
    //             });
    //         }
            
    //         this.addSystemMessage(`✓ Deleted ${category} item`);
    //         await this.loadFocusStatus(); // Reload to ensure sync
    //     } catch (error) {
    //         console.error('Failed to delete item:', error);
    //         this.addSystemMessage(`Error deleting item: ${error.message}`);
    //     }
    // };

    // VeraChat.prototype.moveToCompleted = async function(category, index) {
    //     const items = this.focusBoard[category];
    //     if (!items || index >= items.length) return;
        
    //     // Get the item
    //     const item = items[index];
    //     const completedItem = typeof item === 'object' ? {...item} : { note: item };
    //     completedItem.completed_at = new Date().toISOString();
    //     completedItem.original_category = category;
        
    //     // Add to completed via API
    //     try {
    //         await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/board/add`, {
    //             method: 'POST',
    //             headers: { 'Content-Type': 'application/json' },
    //             body: JSON.stringify({ 
    //                 category: 'completed',
    //                 note: JSON.stringify(completedItem)
    //             })
    //         });
            
    //         // Now delete from original category
    //         await this.deleteBoardItem(category, index);
            
    //         this.addSystemMessage(`✓ Moved to completed`);
    //     } catch (error) {
    //         console.error('Failed to move to completed:', error);
    //         this.addSystemMessage(`Error: ${error.message}`);
    //     }
    // };

    // VeraChat.prototype.clearCategory = async function(category) {
    //     if (!confirm(`Clear all items in ${category}?`)) return;
        
    //     try {
    //         // Try to clear via API if endpoint exists
    //         const response = await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/board/clear`, {
    //             method: 'POST',
    //             headers: { 'Content-Type': 'application/json' },
    //             body: JSON.stringify({ category: category })
    //         });
            
    //         // Clear locally
    //         this.focusBoard[category] = [];
    //         this.updateFocusUI();
    //         this.addSystemMessage(`✓ Cleared ${category}`);
            
    //     } catch (error) {
    //         // Fallback: delete items one by one
    //         console.log('Clear endpoint not available, clearing manually');
    //         const items = this.focusBoard[category] || [];
            
    //         for (let i = items.length - 1; i >= 0; i--) {
    //             items.splice(i, 1);
    //         }
            
    //         this.focusBoard[category] = [];
    //         this.updateFocusUI();
    //         this.addSystemMessage(`✓ Cleared ${category}`);
    //     }
    // };

    // // Helper to sync entire board state to backend
    // VeraChat.prototype._syncBoardToBackend = async function() {
    //     if (!this.sessionId) return;
        
    //     try {
    //         // Use save endpoint to persist current state
    //         await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/save`);
    //         console.log('Board synced to backend');
    //     } catch (error) {
    //         console.error('Failed to sync board to backend:', error);
    //     }
    // };

    // VeraChat.prototype.executeAction = async function(index) {
    //     const action = this.focusBoard.actions[index];
    //     if (!action) return;
        
    //     const parsed = this.parseActionItem(action);
        
    //     if (confirm(`Execute action: ${parsed.description}?`)) {
    //         this.addSystemMessage(`⚡ Executing: ${parsed.description}`);
    //         // Move to completed
    //         await this.moveToCompleted('actions', index);
    //     }
    // };

    // VeraChat.prototype.saveFocusBoard = async function() {
    //     if (!this.sessionId) return;
        
    //     try {
    //         const response = await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/save`);
    //         const data = await response.json();
    //         this.addSystemMessage(`💾 Focus board saved`);
    //     } catch (error) {
    //         console.error('Failed to save focus board:', error);
    //         this.addSystemMessage('Error saving focus board');
    //     }
    // };

    // ============================================================
    // STREAMING AND WEBSOCKET HANDLERS
    // ============================================================

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

    VeraChat.prototype.handleFocusEvent = function(data) {
        console.log('Focus event:', data.type);
        
        // Preserve scroll position
        const container = document.getElementById('tab-focus');
        const scrollPos = container ? container.scrollTop : 0;
        
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
    
    // Helper to clean markdown blocks from text
    VeraChat.prototype._cleanMarkdown = function(text) {
        if (typeof text !== 'string') return text;
        return text.replace(/```json\s*/g, '').replace(/```\s*/g, '').trim();
    };
    
    // Helper to expand array items into individual items
    VeraChat.prototype.expandActionArray = function(item) {
        let actions = [];
        
        if (typeof item === 'object' && item !== null) {
            if (item.description) {
                // Already a single action object
                actions.push(item);
            } else if (item.note) {
                // Try to parse note - clean markdown first
                let noteText = this._cleanMarkdown(item.note);
                
                // Try to parse as JSON
                try {
                    const noteData = JSON.parse(noteText);
                    if (Array.isArray(noteData)) {
                        // Expand the array - each element becomes an action
                        noteData.forEach(actionObj => {
                            if (typeof actionObj === 'object' && actionObj.description) {
                                actions.push(actionObj);
                            } else if (typeof actionObj === 'string') {
                                actions.push({ description: actionObj, tools: [], priority: 'medium' });
                            }
                        });
                    } else if (noteData.description) {
                        actions.push(noteData);
                    } else {
                        actions.push({ description: noteText, tools: [], priority: 'medium' });
                    }
                } catch (e) {
                    // Not valid JSON - treat as plain text
                    console.log('Failed to parse action item:', e);
                    actions.push({ description: noteText, tools: [], priority: 'medium' });
                }
            }
        } else if (typeof item === 'string') {
            let itemText = this._cleanMarkdown(item);
            
            // Try to parse as JSON
            try {
                const jsonData = JSON.parse(itemText);
                if (Array.isArray(jsonData)) {
                    // Expand the array - each element becomes an action
                    jsonData.forEach(actionObj => {
                        if (typeof actionObj === 'object' && actionObj.description) {
                            actions.push(actionObj);
                        } else if (typeof actionObj === 'string') {
                            actions.push({ description: actionObj, tools: [], priority: 'medium' });
                        }
                    });
                } else if (jsonData.description) {
                    actions.push(jsonData);
                } else {
                    actions.push({ description: itemText, tools: [], priority: 'medium' });
                }
            } catch (e) {
                // Not valid JSON - treat as plain text
                console.log('Failed to parse action string:', e);
                actions.push({ description: itemText, tools: [], priority: 'medium' });
            }
        }
        
        // Filter out any empty or invalid actions
        return actions.filter(a => a.description && a.description.trim().length > 0);
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
                // Check if description itself is a JSON array string
                if (typeof item.description === 'string') {
                    let cleaned = this._cleanMarkdown(item.description);
                    if (cleaned.startsWith('[')) {
                        // Description contains an array - this shouldn't happen
                        // Return null to signal this needs array expansion
                        console.log('  → Description contains array, needs expansion');
                        return null;
                    }
                }
                
                parsed.description = item.description;
                parsed.tools = item.tools || [];
                parsed.priority = item.priority || 'medium';
                parsed.metadata = item.metadata || {};
            } else if (item.note) {
                let noteText = this._cleanMarkdown(item.note);
                
                try {
                    const noteData = JSON.parse(noteText);
                    if (Array.isArray(noteData)) {
                        // Note contains an array - return null to signal expansion needed
                        console.log('  → Note contains array, needs expansion');
                        return null;
                    } else if (noteData.description) {
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
            let itemText = this._cleanMarkdown(item);
            
            try {
                const jsonData = JSON.parse(itemText);
                if (Array.isArray(jsonData)) {
                    // String contains an array - return null to signal expansion needed
                    console.log('  → String contains array, needs expansion');
                    return null;
                }
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
            // Handle object with note field
            if (item.note) {
                let noteText = this._cleanMarkdown(item.note);
                try {
                    const parsed = JSON.parse(noteText);
                    if (typeof parsed === 'string') {
                        return { text: parsed, timestamp: item.timestamp, metadata: item.metadata || {} };
                    }
                } catch {}
                return {
                    text: noteText,
                    timestamp: item.timestamp,
                    metadata: item.metadata || {}
                };
            }
            return {
                text: item.description || JSON.stringify(item),
                timestamp: item.timestamp,
                metadata: item.metadata || {}
            };
        } else if (typeof item === 'string') {
            // Remove markdown blocks
            let text = this._cleanMarkdown(item);
            
            // Don't try to parse if it looks like a plain string
            if (!text.startsWith('{') && !text.startsWith('[')) {
                return { text: text, timestamp: null, metadata: {} };
            }
            
            try {
                const parsed = JSON.parse(text);
                if (Array.isArray(parsed)) {
                    // This shouldn't happen for generic items, but handle it
                    console.warn('Array found in generic item:', parsed);
                    return { text: text, timestamp: null, metadata: {} };
                }
                return {
                    text: parsed.note || parsed.description || text,
                    timestamp: parsed.timestamp,
                    metadata: parsed.metadata || {}
                };
            } catch {}
            return { text: text, timestamp: null, metadata: {} };
        }
        return { text: String(item), timestamp: null, metadata: {} };
    };

    // ============================================================
    // UI RENDERING - FIXED TO PRESERVE SCROLL
    // ============================================================
    
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
            <div class="focusContent" style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border-radius: 8px; padding: 16px; margin-bottom: 16px; border-left: 4px solid #8b5cf6; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
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
        
        // Expand arrays in all categories
        let expandedItems = [];
        items.forEach(item => {
            if (cat.key === 'actions') {
                // Use special action expansion for actions
                const expanded = this.expandActionArray(item);
                expandedItems.push(...expanded);
            } else {
                // For non-action categories, check if item is an array
                if (typeof item === 'string') {
                    let cleaned = this._cleanMarkdown(item);
                    
                    // Skip if it's just markdown syntax artifacts
                    if (cleaned === '' || cleaned === 'json' || cleaned === '```') {
                        return; // Skip this item
                    }
                    
                    try {
                        const parsed = JSON.parse(cleaned);
                        if (Array.isArray(parsed)) {
                            // Expand array into individual string items
                            parsed.forEach(arrayItem => {
                                if (typeof arrayItem === 'string' && arrayItem.trim()) {
                                    expandedItems.push(arrayItem.trim());
                                } else if (typeof arrayItem === 'object') {
                                    expandedItems.push(arrayItem);
                                }
                            });
                        } else if (parsed && typeof parsed === 'object') {
                            expandedItems.push(parsed);
                        } else {
                            expandedItems.push(item);
                        }
                    } catch {
                        // Not JSON - add as plain text if not empty
                        if (cleaned.trim()) {
                            expandedItems.push(item);
                        }
                    }
                } else if (typeof item === 'object' && item !== null) {
                    // Handle object items
                    if (item.note) {
                        let noteText = this._cleanMarkdown(item.note);
                        
                        // Skip markdown artifacts
                        if (noteText === '' || noteText === 'json' || noteText === '```') {
                            return;
                        }
                        
                        try {
                            const parsed = JSON.parse(noteText);
                            if (Array.isArray(parsed)) {
                                // Expand array
                                parsed.forEach(arrayItem => {
                                    if (typeof arrayItem === 'string' && arrayItem.trim()) {
                                        expandedItems.push(arrayItem.trim());
                                    } else if (typeof arrayItem === 'object') {
                                        expandedItems.push(arrayItem);
                                    }
                                });
                            } else {
                                expandedItems.push(item);
                            }
                        } catch {
                            expandedItems.push(item);
                        }
                    } else {
                        expandedItems.push(item);
                    }
                } else {
                    expandedItems.push(item);
                }
            }
        });
        items = expandedItems;
        
        let html = `
            <div class="focusContent" style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border-radius: 8px; padding: 16px; border-left: 4px solid ${cat.color}; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">
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
        
        // If parseActionItem returns null, the item needs array expansion
        // This shouldn't happen here as renderCategory should have expanded it
        if (!action || !action.description) {
            console.error('Invalid action at index', idx, '- item needs expansion:', item);
            return '';
        }
        
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
        
        // Skip empty items
        if (!parsed.text || parsed.text.trim() === '') {
            return '';
        }
        
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
        
        } catch (error){
            console.error()
        }
    };

})();