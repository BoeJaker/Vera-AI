(() => {
    // ============================================================
    // Enhanced Notebooks UI with Session-Independent Storage
    // ============================================================
    
    // State management
    VeraChat.prototype.notebookState = {
        isLoading: false,
        isSaving: false,
        searchQuery: '',
        sortBy: 'updated_at',
        sortOrder: 'desc',
        autoSaveTimeout: null,
        storageType: null,
        viewMode: 'current', // 'current' or 'all'
        allNotebooks: []
    };
    
    // ============================================================
    // Utility Functions
    // ============================================================
    
    VeraChat.prototype.showToast = function(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        toast.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 20px;
            background: ${type === 'error' ? '#ef4444' : type === 'success' ? '#10b981' : '#3b82f6'};
            color: white;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            z-index: 10000;
            animation: slideIn 0.3s ease-out;
            font-size: 14px;
            max-width: 300px;
        `;
        
        document.body.appendChild(toast);
        setTimeout(() => {
            toast.style.animation = 'slideOut 0.3s ease-out';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    };
    
    VeraChat.prototype.showLoadingOverlay = function(message = 'Loading...') {
        let overlay = document.getElementById('notebook-loading-overlay');
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.id = 'notebook-loading-overlay';
            overlay.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0,0,0,0.5);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 9999;
            `;
            overlay.innerHTML = `
                <div style="background: var(--panel-bg); padding: 24px; border-radius: 12px; text-align: center;">
                    <div class="spinner"></div>
                    <div style="color: #94a3b8; margin-top: 12px;">${message}</div>
                </div>
            `;
            document.body.appendChild(overlay);
        }
        overlay.style.display = 'flex';
    };
    
    VeraChat.prototype.hideLoadingOverlay = function() {
        const overlay = document.getElementById('notebook-loading-overlay');
        if (overlay) {
            overlay.style.display = 'none';
        }
    };
    
    VeraChat.prototype.debounce = function(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    };
    
    // ============================================================
    // Enhanced Notebook Management with All-Sessions View
    // ============================================================
    
    VeraChat.prototype.ensureToggleButton = function() {
        // Check if button already exists
        if (document.getElementById('toggle-view-btn')) return;
        
        // Find the notebook selector container
        const notebookControls = document.querySelector('.notebook-controls, #notebook-controls');
        if (!notebookControls) {
            console.warn('Could not find notebook controls container');
            return;
        }
        
        // Create the toggle button
        const toggleBtn = document.createElement('button');
        toggleBtn.id = 'toggle-view-btn';
        toggleBtn.className = 'panel-btn';
        toggleBtn.textContent = 'All Sessions';
        toggleBtn.title = 'View notebooks from all sessions';
        toggleBtn.style.cssText = 'margin-left: 8px;';
        toggleBtn.onclick = () => this.toggleNotebookView();
        
        // Insert after the notebook selector or at the end
        const selector = document.getElementById('notebook-selector');
        if (selector && selector.parentElement === notebookControls) {
            selector.parentElement.insertBefore(toggleBtn, selector.nextSibling);
        } else {
            notebookControls.appendChild(toggleBtn);
        }
    };
    
    VeraChat.prototype.loadNotebooks = async function(allSessions = false) {
        // Ensure toggle button exists
        this.ensureToggleButton();
        if (!this.sessionId && !allSessions) {
            console.log('⚠️ No session ID and not loading all sessions');
            return;
        }
        
        this.notebookState.isLoading = true;
        this.notebookState.viewMode = allSessions ? 'all' : 'current';
        
        console.log(`📓 Loading notebooks: ${allSessions ? 'ALL SESSIONS' : 'CURRENT SESSION'}`);
        console.log(`   Session ID: ${this.sessionId}`);
        
        try {
            let url = allSessions ? 
                `http://llm.int:8888/api/notebooks/global/list` :
                `http://llm.int:8888/api/notebooks/${this.sessionId}?all_sessions=false`;
            
            console.log(`   URL: ${url}`);
            
            const response = await fetch(url);
            if (!response.ok) {
                console.error(`❌ API returned ${response.status}: ${response.statusText}`);
                throw new Error('Failed to load notebooks');
            }
            
            const data = await response.json();
            console.log(`✅ API Response:`, data);
            
            if (allSessions) {
                this.notebookState.allNotebooks = data.notebooks || [];
                this.notebooks = data.notebooks || [];
                console.log(`   Loaded ${data.notebooks?.length || 0} notebooks from ${data.sessions} sessions`);
                this.showToast(`Loaded ${data.total} notebooks from ${data.sessions} sessions`, 'success');
            } else {
                this.notebooks = data.notebooks || [];
                this.notebookState.storageType = data.storage_type;
                console.log(`   Loaded ${data.notebooks?.length || 0} notebooks`);
                console.log(`   Storage type: ${data.storage_type}`);
                
                if (this.notebooks.length > 0) {
                    console.log('   Notebooks:');
                    this.notebooks.forEach(nb => {
                        console.log(`   • ${nb.name} (${nb.note_count} notes, session: ${nb.session_id?.substring(0, 20)}...)`);
                    });
                } else {
                    console.log('   ⚠️ No notebooks in current session');
                }
                
                // Show message if current session is empty but global notebooks exist
                // if (this.notebooks.length === 0 && data.global_notebooks_available > 0) {
                //     console.log(`   ℹ️ ${data.global_notebooks_available} notebooks available in other sessions`);
                //     this.showGlobalNotebooksPrompt(data.global_notebooks_available);
                // }
            }
            
            this.updateNotebookSelector();
            
            // Show storage type indicator
            if (data.storage_type === 'file') {
                console.log('   ℹ️ Using file storage (Neo4j unavailable)');
                this.showToast('Using file storage (Neo4j unavailable)', 'info');
            } else if (data.storage_type === 'neo4j') {
                console.log('   ℹ️ Using Neo4j storage');
            }
        } catch (error) {
            console.error('❌ Failed to load notebooks:', error);
            this.showToast('Failed to load notebooks', 'error');
        } finally {
            this.notebookState.isLoading = false;
        }
    };

    VeraChat.prototype.showGlobalNotebooksPrompt = function(count) {
        const prompt = document.createElement('div');
        prompt.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            padding: 16px 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 12px;
            box-shadow: 0 8px 16px rgba(0,0,0,0.3);
            z-index: 10000;
            max-width: 350px;
            animation: slideIn 0.3s ease-out;
        `;
        
        prompt.innerHTML = `
            <div style="font-weight: 600; margin-bottom: 8px; font-size: 15px;">
                📚 ${count} notebook${count === 1 ? '' : 's'} from previous sessions
            </div>
            <div style="font-size: 13px; margin-bottom: 12px; opacity: 0.9;">
                You have notebooks from previous sessions. Would you like to view them?
            </div>
            <div style="display: flex; gap: 8px;">
                <button class="panel-btn" style="background: rgba(255,255,255,0.2); color: white; flex: 1;" onclick="this.closest('div').parentElement.remove()">
                    Later
                </button>
                <button class="panel-btn primary-btn" style="flex: 1;" onclick="app.toggleNotebookView(); this.closest('div').parentElement.remove()">
                    View All
                </button>
            </div>
        `;
        
        document.body.appendChild(prompt);
        
        // Auto-dismiss after 30 seconds
        setTimeout(() => {
            if (prompt.parentElement) {
                prompt.style.animation = 'slideOut 0.3s ease-out';
                setTimeout(() => prompt.remove(), 300);
            }
        }, 30000);
    };

    VeraChat.prototype.toggleNotebookView = async function() {
        const isCurrentlyAll = this.notebookState.viewMode === 'all';
        await this.loadNotebooks(!isCurrentlyAll);
        this.updateViewToggleButton();
    };

    VeraChat.prototype.updateViewToggleButton = function() {
        const toggleBtn = document.getElementById('toggle-view-btn');
        if (toggleBtn) {
            if (this.notebookState.viewMode === 'all') {
                toggleBtn.textContent = 'Current Session Only';
                toggleBtn.title = 'Switch to viewing only current session notebooks';
            } else {
                toggleBtn.textContent = 'All Sessions';
                toggleBtn.title = 'View notebooks from all sessions';
            }
        }
    };

    VeraChat.prototype.createNotebook = async function() {
        if (!this.sessionId && this.notebookState.viewMode !== 'all') {
            this.showToast('No session ID available', 'error');
            return;
        }
        
        const modal = this.createPromptModal(
            'Create New Notebook',
            [
                { label: 'Name', id: 'notebook-name', type: 'text', required: true },
                { label: 'Description', id: 'notebook-desc', type: 'textarea', required: false }
            ]
        );
        
        modal.onConfirm = async (values) => {
            const name = values['notebook-name']?.trim();
            const description = values['notebook-desc']?.trim();
            
            if (!name) {
                this.showToast('Name is required', 'error');
                return;
            }
            
            this.showLoadingOverlay('Creating notebook...');
            
            try {
                const sessionId = this.sessionId || 'default';
                const response = await fetch(`http://llm.int:8888/api/notebooks/${sessionId}/create`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name, description })
                });
                
                if (!response.ok) throw new Error('Failed to create notebook');
                
                const data = await response.json();
                this.notebooks.push(data.notebook);
                this.updateNotebookSelector();
                this.showToast(`Created notebook: ${name}`, 'success');
                modal.close();
            } catch (error) {
                console.error('Failed to create notebook:', error);
                this.showToast('Failed to create notebook', 'error');
            } finally {
                this.hideLoadingOverlay();
            }
        };
    };

    VeraChat.prototype.createPromptModal = function(title, fields) {
        const modal = document.createElement('div');
        modal.className = 'modal-overlay';
        modal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.7);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 10001;
            animation: fadeIn 0.2s ease-out;
        `;
        
        const fieldsHTML = fields.map(field => `
            <div style="margin-bottom: 16px;">
                <label style="display: block; color: #94a3b8; margin-bottom: 6px; font-size: 13px;">
                    ${field.label}${field.required ? ' *' : ''}
                </label>
                ${field.type === 'textarea' ? 
                    `<textarea id="${field.id}" style="width: 100%; min-height: 80px; background: var(--input-bg); border: 1px solid #334155; border-radius: 6px; padding: 8px; color: #e2e8f0; font-family: inherit; resize: vertical;"></textarea>` :
                    `<input type="${field.type}" id="${field.id}" style="width: 100%; background: var(--input-bg); border: 1px solid #334155; border-radius: 6px; padding: 8px; color: #e2e8f0;" ${field.required ? 'required' : ''}>`
                }
            </div>
        `).join('');
        
        modal.innerHTML = `
            <div style="background: var(--panel-bg); padding: 24px; border-radius: 12px; max-width: 500px; width: 90%;">
                <h3 style="color: #60a5fa; margin: 0 0 20px 0;">${title}</h3>
                ${fieldsHTML}
                <div style="display: flex; gap: 12px; justify-content: flex-end; margin-top: 20px;">
                    <button class="panel-btn cancel-btn">Cancel</button>
                    <button class="panel-btn primary-btn">Confirm</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        const firstInput = modal.querySelector('input, textarea');
        if (firstInput) firstInput.focus();
        
        modal.close = () => {
            modal.style.animation = 'fadeOut 0.2s ease-out';
            setTimeout(() => modal.remove(), 200);
        };
        
        modal.querySelector('.cancel-btn').onclick = () => modal.close();
        modal.querySelector('.primary-btn').onclick = () => {
            const values = {};
            fields.forEach(field => {
                const el = document.getElementById(field.id);
                values[field.id] = el.value;
            });
            if (modal.onConfirm) modal.onConfirm(values);
        };
        
        modal.onclick = (e) => {
            if (e.target === modal) modal.close();
        };
        
        return modal;
    };

    VeraChat.prototype.deleteCurrentNotebook = async function() {
        if (!this.currentNotebook) return;
        
        const confirmed = await this.confirmDialog(
            `Delete notebook "${this.currentNotebook.name}"?`,
            'This will delete all notes in this notebook. This action cannot be undone.'
        );
        
        if (!confirmed) return;
        
        this.showLoadingOverlay('Deleting notebook...');
        
        try {
            const sessionId = this.currentNotebook.session_id || this.sessionId;
            const response = await fetch(
                `http://llm.int:8888/api/notebooks/${sessionId}/${this.currentNotebook.id}`,
                { method: 'DELETE' }
            );
            
            if (!response.ok) throw new Error('Failed to delete notebook');
            
            this.notebooks = this.notebooks.filter(nb => nb.id !== this.currentNotebook.id);
            this.currentNotebook = null;
            this.notes = [];
            this.currentNote = null;
            this.updateNotebookSelector();
            this.updateNotesUI();
            this.showToast('Notebook deleted', 'success');
        } catch (error) {
            console.error('Failed to delete notebook:', error);
            this.showToast('Failed to delete notebook', 'error');
        } finally {
            this.hideLoadingOverlay();
        }
    };

    VeraChat.prototype.confirmDialog = function(title, message) {
        return new Promise((resolve) => {
            const modal = document.createElement('div');
            modal.className = 'modal-overlay';
            modal.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0,0,0,0.7);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 10001;
                animation: fadeIn 0.2s ease-out;
            `;
            
            modal.innerHTML = `
                <div style="background: var(--panel-bg); padding: 24px; border-radius: 12px; max-width: 400px; width: 90%;">
                    <h3 style="color: #ef4444; margin: 0 0 12px 0;">${title}</h3>
                    <p style="color: #94a3b8; margin-bottom: 20px;">${message}</p>
                    <div style="display: flex; gap: 12px; justify-content: flex-end;">
                        <button class="panel-btn cancel-btn">Cancel</button>
                        <button class="panel-btn danger-btn">Delete</button>
                    </div>
                </div>
            `;
            
            document.body.appendChild(modal);
            
            const close = (result) => {
                modal.style.animation = 'fadeOut 0.2s ease-out';
                setTimeout(() => modal.remove(), 200);
                resolve(result);
            };
            
            modal.querySelector('.cancel-btn').onclick = () => close(false);
            modal.querySelector('.danger-btn').onclick = () => close(true);
            modal.onclick = (e) => {
                if (e.target === modal) close(false);
            };
        });
    };

    VeraChat.prototype.updateNotebookSelector = function() {
        const selector = document.getElementById('notebook-selector');
        const deleteBtn = document.getElementById('delete-notebook-btn');
        const storageIndicator = document.getElementById('storage-type-indicator');
        
        selector.innerHTML = '<option value="">Select a notebook...</option>';
        
        // Group by session if viewing all
        if (this.notebookState.viewMode === 'all') {
            const bySession = {};
            this.notebooks.forEach(nb => {
                const sessionId = nb.session_id || 'unknown';
                if (!bySession[sessionId]) {
                    bySession[sessionId] = [];
                }
                bySession[sessionId].push(nb);
            });
            
            Object.keys(bySession).sort().forEach(sessionId => {
                const optgroup = document.createElement('optgroup');
                const displaySession = sessionId === this.sessionId ? 
                    `${sessionId} (Current)` : sessionId;
                optgroup.label = `Session: ${displaySession.substring(0, 20)}...`;
                
                bySession[sessionId].forEach(nb => {
                    const option = document.createElement('option');
                    option.value = nb.id;
                    option.textContent = `${nb.name} (${nb.note_count || 0} notes)`;
                    option.setAttribute('data-session-id', nb.session_id);
                    if (this.currentNotebook && nb.id === this.currentNotebook.id) {
                        option.selected = true;
                    }
                    optgroup.appendChild(option);
                });
                
                selector.appendChild(optgroup);
            });
        } else {
            // Standard single-session view
            if (this.notebooks.length === 0) {
                // Show helpful message when no notebooks in current session
                selector.innerHTML = '<option value="">No notebooks in current session - click "All Sessions" to view previous notebooks</option>';
            } else {
                this.notebooks.forEach(nb => {
                    const option = document.createElement('option');
                    option.value = nb.id;
                    option.textContent = `${nb.name} (${nb.note_count || 0} notes)`;
                    if (this.currentNotebook && nb.id === this.currentNotebook.id) {
                        option.selected = true;
                    }
                    selector.appendChild(option);
                });
            }
        }
        
        if (deleteBtn) {
            deleteBtn.disabled = !this.currentNotebook;
        }
        
        // Update storage indicator
        if (storageIndicator && this.notebookState.storageType) {
            const viewModeText = this.notebookState.viewMode === 'all' ? ' (All Sessions)' : '';
            storageIndicator.textContent = 
                (this.notebookState.storageType === 'file' ? 'File Storage' : 'Neo4j') + 
                viewModeText;
            storageIndicator.style.color = this.notebookState.storageType === 'file' ? '#f59e0b' : '#10b981';
        }
        
        this.updateViewToggleButton();
    };

    VeraChat.prototype.switchNotebook = async function(notebookId) {
        if (!notebookId) {
            this.currentNotebook = null;
            this.notes = [];
            this.currentNote = null;
            this.updateNotesUI();
            this.renderNoteEditor();
            return;
        }
        
        this.currentNotebook = this.notebooks.find(nb => nb.id === notebookId);
        if (this.currentNotebook) {
            await this.loadNotes();
            this.updateNotebookSelector();
        }
    };

    // ============================================================
    // Enhanced Notes Management
    // ============================================================
    
    VeraChat.prototype.loadNotes = async function() {
        if (!this.currentNotebook || this.notebookState.isLoading) {
            console.log('⚠️ Cannot load notes:', {
                hasNotebook: !!this.currentNotebook,
                isLoading: this.notebookState.isLoading
            });
            return;
        }
        
        console.log(`📝 Loading notes for notebook: ${this.currentNotebook.name}`);
        console.log(`   Notebook ID: ${this.currentNotebook.id}`);
        console.log(`   Session ID: ${this.currentNotebook.session_id || this.sessionId}`);
        
        this.notebookState.isLoading = true;
        this.updateNotesUI(); // Show loading state
        
        try {
            const params = new URLSearchParams({
                sort_by: this.notebookState.sortBy,
                order: this.notebookState.sortOrder
            });
            
            const sessionId = this.currentNotebook.session_id || this.sessionId;
            const url = `http://llm.int:8888/api/notebooks/${sessionId}/${this.currentNotebook.id}/notes?${params}`;
            console.log(`   URL: ${url}`);
            
            const response = await fetch(url);
            
            if (!response.ok) {
                console.error(`❌ API returned ${response.status}: ${response.statusText}`);
                throw new Error('Failed to load notes');
            }
            
            const data = await response.json();
            console.log(`✅ Notes API Response:`, data);
            
            this.notes = data.notes || [];
            console.log(`   Loaded ${this.notes.length} notes (total: ${data.total})`);
            console.log(`   Storage type: ${data.storage_type}`);
            
            if (this.notes.length > 0) {
                console.log('   Notes:');
                this.notes.forEach(note => {
                    console.log(`   • ${note.title} (${note.content?.length || 0} chars)`);
                });
            } else {
                console.log('   ⚠️ No notes in this notebook');
            }
            
            // Use setTimeout to ensure DOM is ready and force UI update
            setTimeout(() => {
                console.log('🎨 Updating notes UI...');
                this.updateNotesUI();
                
                // Double-check it worked
                const container = document.getElementById('notes-list');
                if (container) {
                    const noteItems = container.querySelectorAll('.note-item');
                    console.log(`   ✅ UI updated: ${noteItems.length} note items in DOM`);
                } else {
                    console.error('   ❌ notes-list container not found!');
                }
            }, 100);
        } catch (error) {
            console.error('❌ Failed to load notes:', error);
            this.showToast('Failed to load notes', 'error');
        } finally {
            this.notebookState.isLoading = false;
        }
    };

    VeraChat.prototype.createNote = async function() {
        if (!this.currentNotebook) {
            this.showToast('Please select a notebook first', 'error');
            return;
        }
        
        const modal = this.createPromptModal(
            'Create New Note',
            [{ label: 'Title', id: 'note-title', type: 'text', required: true }]
        );
        
        modal.onConfirm = async (values) => {
            const title = values['note-title']?.trim();
            if (!title) {
                this.showToast('Title is required', 'error');
                return;
            }
            
            this.showLoadingOverlay('Creating note...');
            
            try {
                const sessionId = this.currentNotebook.session_id || this.sessionId;
                const response = await fetch(
                    `http://llm.int:8888/api/notebooks/${sessionId}/${this.currentNotebook.id}/notes/create`,
                    {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ title, content: '' })
                    }
                );
                
                if (!response.ok) throw new Error('Failed to create note');
                
                const data = await response.json();
                this.notes.unshift(data.note);
                this.updateNotesUI();
                this.selectNote(data.note.id);
                this.showToast(`Created note: ${title}`, 'success');
                modal.close();
            } catch (error) {
                console.error('Failed to create note:', error);
                this.showToast('Failed to create note', 'error');
            } finally {
                this.hideLoadingOverlay();
            }
        };
    };

    VeraChat.prototype.selectNote = function(noteId) {
        this.currentNote = this.notes.find(n => n.id === noteId);
        this.updateNotesUI();
        this.renderNoteEditor();
    };

    VeraChat.prototype.saveCurrentNote = async function() {
        if (!this.currentNote || this.notebookState.isSaving) return;
        
        const textarea = document.getElementById('note-editor-area');
        if (!textarea) return;
        
        const content = textarea.value;
        if (content === this.currentNote.content) return; // No changes
        
        this.notebookState.isSaving = true;
        this.updateSaveStatus('Saving...');
        
        try {
            const sessionId = this.currentNotebook.session_id || this.sessionId;
            const response = await fetch(
                `http://llm.int:8888/api/notebooks/${sessionId}/${this.currentNotebook.id}/notes/${this.currentNote.id}/update`,
                {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ content })
                }
            );
            
            if (!response.ok) throw new Error('Failed to save note');
            
            this.currentNote.content = content;
            this.currentNote.updated_at = new Date().toISOString();
            
            // Update preview in sidebar
            const noteItem = document.querySelector(`.note-item[data-note-id="${this.currentNote.id}"] .note-preview`);
            if (noteItem) {
                noteItem.textContent = content.substring(0, 50);
            }
            
            this.updateSaveStatus('Saved');
            setTimeout(() => this.updateSaveStatus(''), 2000);
        } catch (error) {
            console.error('Failed to save note:', error);
            this.updateSaveStatus('Error saving');
            this.showToast('Failed to save note', 'error');
        } finally {
            this.notebookState.isSaving = false;
        }
    };

    VeraChat.prototype.updateSaveStatus = function(status) {
        const statusEl = document.getElementById('note-save-status');
        if (statusEl) {
            statusEl.textContent = status;
            statusEl.style.color = status === 'Error saving' ? '#ef4444' : 
                                   status === 'Saved' ? '#10b981' : '#94a3b8';
        }
    };

    // Debounced auto-save
    VeraChat.prototype.autoSaveNote = function() {
        clearTimeout(this.notebookState.autoSaveTimeout);
        this.notebookState.autoSaveTimeout = setTimeout(() => {
            this.saveCurrentNote();
        }, 1000);
    };

    VeraChat.prototype.deleteNote = async function(noteId) {
        const note = this.notes.find(n => n.id === noteId);
        if (!note) return;
        
        const confirmed = await this.confirmDialog(
            `Delete note "${note.title}"?`,
            'This action cannot be undone.'
        );
        
        if (!confirmed) return;
        
        this.showLoadingOverlay('Deleting note...');
        
        try {
            const sessionId = this.currentNotebook.session_id || this.sessionId;
            const response = await fetch(
                `http://llm.int:8888/api/notebooks/${sessionId}/${this.currentNotebook.id}/notes/${noteId}`,
                { method: 'DELETE' }
            );
            
            if (!response.ok) throw new Error('Failed to delete note');
            
            this.notes = this.notes.filter(n => n.id !== noteId);
            if (this.currentNote && this.currentNote.id === noteId) {
                this.currentNote = null;
            }
            this.updateNotesUI();
            this.renderNoteEditor();
            this.showToast('Note deleted', 'success');
        } catch (error) {
            console.error('Failed to delete note:', error);
            this.showToast('Failed to delete note', 'error');
        } finally {
            this.hideLoadingOverlay();
        }
    };

    VeraChat.prototype.exportNotebookAsMarkdown = async function() {
        if (!this.currentNotebook) return;
        
        this.showLoadingOverlay('Exporting as markdown...');
        
        try {
            const sessionId = this.currentNotebook.session_id || this.sessionId;
            const response = await fetch(
                `http://llm.int:8888/api/notebooks/${sessionId}/${this.currentNotebook.id}/export-markdown`,
                { method: 'POST' }
            );
            
            if (!response.ok) throw new Error('Failed to export');
            
            const data = await response.json();
            this.showToast('Notebook exported as markdown!', 'success');
        } catch (error) {
            console.error('Failed to export markdown:', error);
            this.showToast('Failed to export markdown', 'error');
        } finally {
            this.hideLoadingOverlay();
        }
    };

    VeraChat.prototype.captureMessageAsNote = async function(messageId) {
        if (!this.currentNotebook) {
            this.showToast('Please select a notebook first', 'error');
            return;
        }
        
        const message = this.messages.find(m => m.id === messageId);
        if (!message) return;
        
        const defaultTitle = `${message.role} - ${new Date(message.timestamp).toLocaleString()}`;
        
        const modal = this.createPromptModal(
            'Capture Message as Note',
            [{ label: 'Note title', id: 'note-title', type: 'text', required: true }]
        );
        
        document.getElementById('note-title').value = defaultTitle;
        
        modal.onConfirm = async (values) => {
            const title = values['note-title']?.trim();
            if (!title) {
                this.showToast('Title is required', 'error');
                return;
            }
            
            this.showLoadingOverlay('Capturing message...');
            
            try {
                const sessionId = this.currentNotebook.session_id || this.sessionId;
                const response = await fetch(
                    `http://llm.int:8888/api/notebooks/${sessionId}/${this.currentNotebook.id}/notes/create`,
                    {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            title,
                            content: message.content,
                            source: {
                                type: 'chat_message',
                                message_id: messageId,
                                role: message.role,
                                timestamp: message.timestamp
                            }
                        })
                    }
                );
                
                if (!response.ok) throw new Error('Failed to capture message');
                
                const data = await response.json();
                this.notes.unshift(data.note);
                this.updateNotesUI();
                this.showToast(`Captured as: ${title}`, 'success');
                modal.close();
            } catch (error) {
                console.error('Failed to capture message:', error);
                this.showToast('Failed to capture message', 'error');
            } finally {
                this.hideLoadingOverlay();
            }
        };
    };

    // ============================================================
    // Enhanced UI Rendering
    // ============================================================
    
    VeraChat.prototype.updateNotesUI = function() {
        const container = document.getElementById('notes-list');
        
        // Safety check: ensure container exists
        if (!container) {
            console.warn('⚠️ updateNotesUI called but notes-list container not found in DOM');
            return;
        }
        
        const searchBox = document.getElementById('notes-search');
        
        if (!this.currentNotebook) {
            container.innerHTML = '<p style="color: #94a3b8; font-size: 13px; text-align: center; padding: 20px;">Select a notebook to view notes</p>';
            return;
        }
        
        if (this.notebookState.isLoading) {
            container.innerHTML = '<div style="text-align: center; padding: 20px;"><div class="spinner"></div></div>';
            return;
        }
        
        // Filter notes by search query
        let filteredNotes = this.notes;
        if (this.notebookState.searchQuery) {
            const query = this.notebookState.searchQuery.toLowerCase();
            filteredNotes = this.notes.filter(note => 
                note.title.toLowerCase().includes(query) ||
                (note.content || '').toLowerCase().includes(query)
            );
        }
        
        if (filteredNotes.length === 0) {
            const msg = this.notebookState.searchQuery ? 'No notes match your search' : 'No notes yet';
            container.innerHTML = `<p style="color: #94a3b8; font-size: 13px; text-align: center; padding: 20px;">${msg}</p>`;
            return;
        }
        
        console.log(`🎨 Rendering ${filteredNotes.length} notes to UI`);
        
        container.innerHTML = '';
        filteredNotes.forEach(note => {
            const noteItem = document.createElement('div');
            noteItem.className = 'note-item';
            noteItem.setAttribute('data-note-id', note.id);
            if (this.currentNote && note.id === this.currentNote.id) {
                noteItem.classList.add('active');
            }
            
            const updatedDate = new Date(note.updated_at || note.created_at);
            const timeAgo = this.getTimeAgo(updatedDate);
            
            noteItem.innerHTML = `
                <div class="note-title">${this.escapeHtml(note.title)}</div>
                <div class="note-preview">${this.escapeHtml((note.content || '').substring(0, 60))}</div>
                <div class="note-meta">
                    <span style="color: #64748b; font-size: 11px;">${timeAgo}</span>
                    ${note.source ? '<span class="note-source-tag">From Chat</span>' : ''}
                </div>
                <div style="margin-top: 6px; display: flex; gap: 4px; justify-content: flex-end;">
                    <button class="panel-btn" style="padding: 2px 6px; font-size: 10px;" onclick="event.stopPropagation(); app.deleteNote('${note.id}')">🗑️</button>
                </div>
            `;
            
            noteItem.addEventListener('click', (e) => {
                if (!e.target.closest('button')) {
                    this.selectNote(note.id);
                }
            });
            
            container.appendChild(noteItem);
        });
        
        console.log(`✅ Rendered ${filteredNotes.length} note items`);
    };

    VeraChat.prototype.getTimeAgo = function(date) {
        const seconds = Math.floor((new Date() - date) / 1000);
        const intervals = {
            year: 31536000,
            month: 2592000,
            week: 604800,
            day: 86400,
            hour: 3600,
            minute: 60
        };
        
        for (const [name, seconds_in] of Object.entries(intervals)) {
            const interval = Math.floor(seconds / seconds_in);
            if (interval >= 1) {
                return `${interval} ${name}${interval === 1 ? '' : 's'} ago`;
            }
        }
        return 'Just now';
    };

    VeraChat.prototype.renderNoteEditor = function() {
        const container = document.getElementById('note-editor');
        
        if (!this.currentNote) {
            container.innerHTML = `
                <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; color: #64748b;">
                    <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" style="margin-bottom: 16px;">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" stroke-width="2"/>
                        <polyline points="14 2 14 8 20 8" stroke-width="2"/>
                        <line x1="12" y1="18" x2="12" y2="12" stroke-width="2"/>
                        <line x1="9" y1="15" x2="15" y2="15" stroke-width="2"/>
                    </svg>
                    <p>Select or create a note to start editing</p>
                </div>
            `;
            return;
        }
        
        const charCount = (this.currentNote.content || '').length;
        const wordCount = (this.currentNote.content || '').trim().split(/\s+/).filter(w => w).length;
        
        container.innerHTML = `
            <div style="margin-bottom: 16px; display: flex; justify-content: space-between; align-items: flex-start;">
                <div style="flex: 1;">
                    <h3 style="color: #60a5fa; margin: 0 0 8px 0;">${this.escapeHtml(this.currentNote.title)}</h3>
                    <div style="color: #94a3b8; font-size: 12px;">
                        ${this.currentNote.source ? `
                            <span class="note-source-tag">${this.currentNote.source.type}</span>
                        ` : ''}
                        Last updated: ${new Date(this.currentNote.updated_at || this.currentNote.created_at).toLocaleString()}
                    </div>
                </div>
                <div style="display: flex; gap: 8px; align-items: center;">
                    <span id="note-save-status" style="color: #94a3b8; font-size: 12px;"></span>
                    <button class="panel-btn" onclick="app.saveCurrentNote()" title="Save (Ctrl+S)">💾 Save</button>
                    <button class="panel-btn" onclick="app.exportNote()" title="Export">📤 Export</button>
                </div>
            </div>
            
            <div style="position: relative; flex: 1; display: flex; flex-direction: column;">
                <textarea id="note-editor-area" 
                          placeholder="Write your note... (Ctrl+S to save)"
                          style="flex: 1; resize: none;"
                          spellcheck="true">${this.escapeHtml(this.currentNote.content || '')}</textarea>
                <div style="padding: 8px 0; color: #64748b; font-size: 11px; display: flex; justify-content: space-between;">
                    <span>${wordCount} words, ${charCount} characters</span>
                    <span>Auto-saves after 1 second</span>
                </div>
            </div>
            
            ${this.currentNote.source ? `
                <div style="margin-top: 16px; padding: 12px; background: var(--panel-bg); border-radius: 6px; border-left: 3px solid #8b5cf6;">
                    <div style="color: #a78bfa; font-size: 11px; margin-bottom: 6px; font-weight: 600;">ORIGINAL MESSAGE</div>
                    <div style="color: #cbd5e1; font-size: 13px; max-height: 200px; overflow-y: auto;">${this.parseMessageContent(this.currentNote.content)}</div>
                </div>
            ` : ''}
        `;
        
        // Setup auto-save and keyboard shortcuts
        const textarea = document.getElementById('note-editor-area');
        textarea.addEventListener('input', () => {
            this.updateSaveStatus('Unsaved changes');
            this.autoSaveNote();
        });
        
        textarea.addEventListener('keydown', (e) => {
            // Ctrl+S to save
            if ((e.ctrlKey || e.metaKey) && e.key === 's') {
                e.preventDefault();
                this.saveCurrentNote();
            }
            // Tab for indentation
            if (e.key === 'Tab') {
                e.preventDefault();
                const start = textarea.selectionStart;
                const end = textarea.selectionEnd;
                textarea.value = textarea.value.substring(0, start) + '    ' + textarea.value.substring(end);
                textarea.selectionStart = textarea.selectionEnd = start + 4;
            }
        });
        
        textarea.focus();
    };

    VeraChat.prototype.filterNotes = function(query) {
        this.notebookState.searchQuery = query;
        this.updateNotesUI();
    };

    VeraChat.prototype.exportNote = async function() {
        if (!this.currentNote) return;
        
        const data = {
            notebook: this.currentNotebook.name,
            note: this.currentNote,
            exported_at: new Date().toISOString()
        };
        
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${this.currentNote.title.replace(/[^a-z0-9]/gi, '_')}.json`;
        a.click();
        URL.revokeObjectURL(url);
        
        this.showToast('Note exported', 'success');
    };

    // ============================================================
    // Global Keyboard Shortcuts
    // ============================================================
    
    VeraChat.prototype.setupNotebookKeyboardShortcuts = function() {
        document.addEventListener('keydown', (e) => {
            // Don't trigger if user is typing in an input
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                return;
            }
            
            // Ctrl+N: New note
            if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
                e.preventDefault();
                if (this.currentNotebook) {
                    this.createNote();
                }
            }
            
            // Ctrl+F: Focus search
            if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
                e.preventDefault();
                const searchInput = document.getElementById('notes-search');
                if (searchInput) searchInput.focus();
            }
        });
    };

    // Initialize keyboard shortcuts
    if (!VeraChat.prototype._notebookShortcutsInitialized) {
        VeraChat.prototype.setupNotebookKeyboardShortcuts();
        VeraChat.prototype._notebookShortcutsInitialized = true;
    }

    // ============================================================
    // CSS Animations (inject once)
    // ============================================================
    
    if (!document.getElementById('notebook-animations')) {
        const style = document.createElement('style');
        style.id = 'notebook-animations';
        style.textContent = `
            @keyframes fadeIn {
                from { opacity: 0; }
                to { opacity: 1; }
            }
            
            @keyframes fadeOut {
                from { opacity: 1; }
                to { opacity: 0; }
            }
            
            @keyframes slideIn {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
            
            @keyframes slideOut {
                from { transform: translateX(0); opacity: 1; }
                to { transform: translateX(100%); opacity: 0; }
            }
            
            .spinner {
                width: 40px;
                height: 40px;
                border: 4px solid #334155;
                border-top-color: #60a5fa;
                border-radius: 50%;
                animation: spin 1s linear infinite;
            }
            
            @keyframes spin {
                to { transform: rotate(360deg); }
            }
            
            .note-item {
                transition: all 0.2s ease;
            }
            
            .note-item:hover {
                transform: translateX(4px);
            }
            
            .note-item.active {
                border-color: #60a5fa !important;
                background: rgba(96, 165, 250, 0.1) !important;
            }
            
            .panel-btn.primary-btn {
                background: #3b82f6;
                color: white;
            }
            
            .panel-btn.primary-btn:hover {
                background: #2563eb;
            }
            
            .panel-btn.danger-btn {
                background: #ef4444;
                color: white;
            }
            
            .panel-btn.danger-btn:hover {
                background: #dc2626;
            }
            
            .note-source-tag {
                background: rgba(139, 92, 246, 0.2);
                color: #a78bfa;
                font-size: 10px;
                padding: 2px 6px;
                border-radius: 4px;
                font-weight: 600;
            }
            
            .note-meta {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-top: 6px;
            }
        `;
        document.head.appendChild(style);
    }

// notebooks-full-canvas.js
// Full Canvas Integration for Notebooks
// Uses your existing canvas.js system with all features

/**
 * This integrates the FULL canvas system into notebooks
 * Each canvas note becomes a complete canvas instance with:
 * - Multiple parsers
 * - File management
 * - Multi-instance support
 * - Code execution
 * - Everything from your existing canvas.js
 */


    console.log('📋 Loading Full Canvas Notebook Integration...');
    
    // ============================================================
    // Canvas Note Management
    // ============================================================
    
    /**
     * Initialize canvas system for notebooks
     */
    VeraChat.prototype.initNotebookCanvas = function() {
        if (this.notebookCanvasInitialized) return;
        
        console.log('🎨 Initializing Full Canvas for Notebooks');
        
        // Store canvas instances by note ID
        this.noteCanvasInstances = this.noteCanvasInstances || new Map();
        
        // Track which notes are canvas type
        this.canvasNotes = this.canvasNotes || new Set();
        
        this.notebookCanvasInitialized = true;
    };
    
    /**
     * Create a new canvas note
     */
    VeraChat.prototype.createCanvasNote = async function() {
        if (!this.currentNotebook) {
            this.showToast('Please select a notebook first', 'error');
            return;
        }
        
        const modal = this.createPromptModal(
            'Create Canvas Note',
            [
                { label: 'Title', id: 'canvas-title', type: 'text', required: true }
            ]
        );
        
        modal.onConfirm = async (values) => {
            const title = values['canvas-title']?.trim();
            
            if (!title) {
                this.showToast('Title is required', 'error');
                return;
            }
            
            try {
                const sessionId = this.currentNotebook.session_id || this.sessionId;
                
                // Create canvas note with metadata
                const response = await fetch(
                    `http://llm.int:8888/api/notebooks/${sessionId}/${this.currentNotebook.id}/notes/create`,
                    {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            title: title,
                            content: JSON.stringify({
                                type: 'canvas',
                                canvases: [] // Will be populated by canvas system
                            }),
                            metadata: {
                                type: 'canvas',
                                created_with: 'full_canvas_system'
                            },
                            tags: ['canvas']
                        })
                    }
                );
                
                if (response.ok) {
                    const data = await response.json();
                    await this.loadNotes();
                    this.selectNote(data.note.id);
                    this.showToast(`Canvas note "${title}" created`, 'success');
                } else {
                    throw new Error('Failed to create canvas note');
                }
            } catch (error) {
                console.error('Error creating canvas note:', error);
                this.showToast('Failed to create canvas note', 'error');
            }
        };
    };
    
    /**
     * Enhanced renderNoteEditor that supports both text and canvas
     */
    const originalRenderNoteEditor = VeraChat.prototype.renderNoteEditor;
    VeraChat.prototype.renderNoteEditor = function() {
        const container = document.getElementById('note-editor');
        
        if (!this.currentNote) {
            container.innerHTML = `
                <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; color: #64748b;">
                    <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" style="margin-bottom: 16px;">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" stroke-width="2"/>
                        <polyline points="14 2 14 8 20 8" stroke-width="2"/>
                        <line x1="12" y1="18" x2="12" y2="12" stroke-width="2"/>
                        <line x1="9" y1="15" x2="15" y2="15" stroke-width="2"/>
                    </svg>
                    <p style="margin: 0 0 16px 0; font-size: 14px;">Select or create a note</p>
                    <div style="display: flex; gap: 8px;">
                        <button class="panel-btn" onclick="app.createNote()">📝 Text Note</button>
                        <button class="panel-btn" onclick="app.createCanvasNote()">🎨 Canvas Note</button>
                    </div>
                </div>
            `;
            return;
        }
        
        // Check if this is a canvas note
        const isCanvas = this.currentNote.metadata?.type === 'canvas';
        
        if (isCanvas) {
            this.renderFullCanvasNote();
        } else {
            this.renderTextNote();
        }
    };
    
    /**
     * Render full canvas note using existing canvas system
     */
    VeraChat.prototype.renderFullCanvasNote = function() {
        const container = document.getElementById('note-editor');
        const noteId = this.currentNote.id;
        
        container.innerHTML = `
            <div style="height: 100%; display: flex; flex-direction: column;">
                <!-- Canvas Note Header -->
                <div style="padding: 12px 20px; background: var(--bg-darker); border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center;">
                    <div style="flex: 1;">
                        <input 
                            type="text" 
                            id="canvas-note-title-${noteId}"
                            value="${this.escapeHtml(this.currentNote.title)}"
                            style="background: transparent; border: none; color: var(--text); font-size: 18px; font-weight: 600; width: 100%; outline: none;"
                            placeholder="Canvas Note Title"
                        />
                        <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">
                            Full Canvas Note with Multi-Parser Support
                        </div>
                    </div>
                    <div style="display: flex; gap: 8px; align-items: center;">
                        <span id="canvas-save-status-${noteId}" style="font-size: 12px; color: var(--text-muted);"></span>
                        <button class="panel-btn" onclick="app.convertNoteType('${noteId}', 'text')" title="Convert to text note">
                            📝 To Text
                        </button>
                        <button class="panel-btn" onclick="app.saveCanvasNoteManual('${noteId}')" title="Save canvas">
                            💾 Save
                        </button>
                    </div>
                </div>
                
                <!-- Full Canvas Container -->
                <div id="canvas-note-container-${noteId}" style="flex: 1; overflow: hidden; background: var(--bg);">
                    <!-- Canvas system will initialize here -->
                </div>
            </div>
        `;
        
        // Initialize full canvas system for this note
        setTimeout(() => {
            this.initializeFullCanvasForNote(noteId);
        }, 100);
        
        // Setup title auto-save
        const titleInput = document.getElementById(`canvas-note-title-${noteId}`);
        if (titleInput) {
            let titleSaveTimeout;
            titleInput.addEventListener('input', () => {
                clearTimeout(titleSaveTimeout);
                titleSaveTimeout = setTimeout(() => {
                    this.saveCanvasNoteTitle(noteId, titleInput.value);
                }, 1000);
            });
        }
    };
    
    /**
     * Initialize full canvas system for a note
     */
    VeraChat.prototype.initializeFullCanvasForNote = function(noteId) {
        console.log(`🎨 Initializing full canvas for note: ${noteId}`);
        
        const note = this.notes.find(n => n.id === noteId);
        if (!note) {
            console.error('Note not found:', noteId);
            return;
        }
        
        const container = document.getElementById(`canvas-note-container-${noteId}`);
        if (!container) {
            console.error('Canvas container not found for note:', noteId);
            return;
        }
        
        // Create a canvas tab container that mimics the main canvas tab
        container.innerHTML = `
            <div id="canvas-notebook-${noteId}" style="height: 100%; width: 100%;">
                <!-- Canvas content will be initialized here -->
                <div style="padding: 20px; text-align: center; color: var(--text-muted);">
                    <p>Initializing canvas system...</p>
                </div>
            </div>
        `;
        
        // Load saved canvas state
        let canvasState;
        try {
            const content = typeof note.content === 'string' ? JSON.parse(note.content) : note.content;
            canvasState = content.canvases || [];
        } catch (e) {
            console.warn('Could not parse canvas state, starting fresh:', e);
            canvasState = [];
        }
        
        // Initialize canvas using your existing initCanvasTab function
        // We need to adapt it to work within a note
        if (typeof this.initCanvasForContainer === 'function') {
            this.initCanvasForContainer(`canvas-notebook-${noteId}`, canvasState, noteId);
        } else {
            // Fallback: Create a basic canvas interface
            this.createBasicCanvasInterface(noteId, canvasState);
        }
        
        // Store canvas instance
        this.noteCanvasInstances.set(noteId, {
            noteId: noteId,
            containerId: `canvas-notebook-${noteId}`,
            state: canvasState
        });
        
        // Setup auto-save
        this.setupCanvasAutoSave(noteId);
    };
    
    /**
     * Create basic canvas interface (fallback if full system not available)
     */
    VeraChat.prototype.createBasicCanvasInterface = function(noteId, initialState) {
        const container = document.getElementById(`canvas-notebook-${noteId}`);
        
        container.innerHTML = `
            <div style="display: flex; flex-direction: column; height: 100%;">
                <div style="padding: 12px; background: var(--bg-darker); border-bottom: 1px solid var(--border);">
                    <button class="panel-btn" onclick="app.addCanvasToNote('${noteId}')">+ Add Canvas</button>
                </div>
                <div id="canvas-list-${noteId}" style="flex: 1; overflow-y: auto; padding: 16px;">
                    ${initialState.length === 0 ? '<p style="color: var(--text-muted); text-align: center;">No canvases yet. Click "+ Add Canvas" to create one.</p>' : ''}
                </div>
            </div>
        `;
        
        // Render existing canvases
        initialState.forEach((canvas, index) => {
            this.renderCanvasInNote(noteId, canvas, index);
        });
    };
    
    /**
     * Add a new canvas to a note
     */
    VeraChat.prototype.addCanvasToNote = function(noteId) {
        const instance = this.noteCanvasInstances.get(noteId);
        if (!instance) return;
        
        const newCanvas = {
            id: `canvas-${Date.now()}`,
            parser: 'python',
            content: '# Start coding here!',
            output: '',
            files: []
        };
        
        instance.state.push(newCanvas);
        this.renderCanvasInNote(noteId, newCanvas, instance.state.length - 1);
        this.saveCanvasNoteAuto(noteId);
    };
    
    /**
     * Render a canvas within a note
     */
    VeraChat.prototype.renderCanvasInNote = function(noteId, canvas, index) {
        const listContainer = document.getElementById(`canvas-list-${noteId}`);
        if (!listContainer) return;
        
        const canvasEl = document.createElement('div');
        canvasEl.id = `canvas-item-${canvas.id}`;
        canvasEl.style.cssText = 'margin-bottom: 16px; border: 1px solid var(--border); border-radius: 8px; overflow: hidden;';
        
        canvasEl.innerHTML = `
            <div style="padding: 8px 12px; background: var(--bg-darker); display: flex; justify-content: space-between; align-items: center;">
                <select onchange="app.changeCanvasParser('${noteId}', ${index}, this.value)" 
                        style="background: var(--bg); border: 1px solid var(--border); color: var(--text); padding: 4px 8px; border-radius: 4px;">
                    <option value="python" ${canvas.parser === 'python' ? 'selected' : ''}>Python</option>
                    <option value="javascript" ${canvas.parser === 'javascript' ? 'selected' : ''}>JavaScript</option>
                    <option value="bash" ${canvas.parser === 'bash' ? 'selected' : ''}>Bash</option>
                    <option value="html" ${canvas.parser === 'html' ? 'selected' : ''}>HTML</option>
                </select>
                <div style="display: flex; gap: 4px;">
                    <button class="panel-btn" onclick="app.executeCanvasInNote('${noteId}', ${index})" style="padding: 4px 8px; font-size: 11px;">▶️ Run</button>
                    <button class="panel-btn" onclick="app.deleteCanvasFromNote('${noteId}', ${index})" style="padding: 4px 8px; font-size: 11px;">🗑️</button>
                </div>
            </div>
            <textarea 
                id="canvas-editor-${canvas.id}"
                onchange="app.updateCanvasContent('${noteId}', ${index}, this.value)"
                style="width: 100%; min-height: 200px; padding: 12px; background: var(--bg); color: var(--text); border: none; border-top: 1px solid var(--border); font-family: monospace; font-size: 13px; resize: vertical;"
            >${this.escapeHtml(canvas.content)}</textarea>
            <div id="canvas-output-${canvas.id}" style="display: none; padding: 12px; background: var(--bg-darker); border-top: 1px solid var(--border); max-height: 200px; overflow-y: auto; font-family: monospace; font-size: 12px;"></div>
        `;
        
        listContainer.appendChild(canvasEl);
    };
    
    /**
     * Execute canvas in note
     */
    VeraChat.prototype.executeCanvasInNote = async function(noteId, index) {
        const instance = this.noteCanvasInstances.get(noteId);
        if (!instance || !instance.state[index]) return;
        
        const canvas = instance.state[index];
        const outputEl = document.getElementById(`canvas-output-${canvas.id}`);
        
        if (!outputEl) return;
        
        outputEl.style.display = 'block';
        outputEl.innerHTML = '<div style="color: var(--text-muted);">⏳ Executing...</div>';
        
        try {
            const response = await fetch('http://llm.int:8888/api/canvas/execute', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    parser: canvas.parser,
                    content: canvas.content,
                    session_id: this.sessionId
                })
            });
            
            if (response.ok) {
                const data = await response.json();
                
                let output = '';
                if (data.stdout) {
                    output += `<pre style="margin: 0; color: var(--text);">${this.escapeHtml(data.stdout)}</pre>`;
                }
                if (data.stderr) {
                    output += `<pre style="margin: 8px 0 0 0; color: var(--danger);">${this.escapeHtml(data.stderr)}</pre>`;
                }
                if (!data.stdout && !data.stderr) {
                    output = '<div style="color: var(--success);">✅ Executed successfully (no output)</div>';
                }
                
                outputEl.innerHTML = output;
                canvas.output = data.stdout || data.stderr || '';
                this.saveCanvasNoteAuto(noteId);
            } else {
                const error = await response.json();
                outputEl.innerHTML = `<div style="color: var(--danger);">❌ Error: ${this.escapeHtml(error.detail || 'Execution failed')}</div>`;
            }
        } catch (error) {
            console.error('Execution error:', error);
            outputEl.innerHTML = `<div style="color: var(--danger);">❌ Error: ${this.escapeHtml(error.message)}</div>`;
        }
    };
    
    /**
     * Update canvas content
     */
    VeraChat.prototype.updateCanvasContent = function(noteId, index, content) {
        const instance = this.noteCanvasInstances.get(noteId);
        if (!instance || !instance.state[index]) return;
        
        instance.state[index].content = content;
        this.saveCanvasNoteAuto(noteId);
    };
    
    /**
     * Change canvas parser
     */
    VeraChat.prototype.changeCanvasParser = function(noteId, index, parser) {
        const instance = this.noteCanvasInstances.get(noteId);
        if (!instance || !instance.state[index]) return;
        
        instance.state[index].parser = parser;
        this.saveCanvasNoteAuto(noteId);
    };
    
    /**
     * Delete canvas from note
     */
    VeraChat.prototype.deleteCanvasFromNote = function(noteId, index) {
        const instance = this.noteCanvasInstances.get(noteId);
        if (!instance || !instance.state[index]) return;
        
        if (!confirm('Delete this canvas?')) return;
        
        const canvas = instance.state[index];
        const canvasEl = document.getElementById(`canvas-item-${canvas.id}`);
        if (canvasEl) canvasEl.remove();
        
        instance.state.splice(index, 1);
        this.saveCanvasNoteAuto(noteId);
    };
    
    /**
     * Setup canvas auto-save
     */
    VeraChat.prototype.setupCanvasAutoSave = function(noteId) {
        // Auto-save every 5 seconds when canvas is edited
        if (this[`canvasAutoSaveInterval_${noteId}`]) {
            clearInterval(this[`canvasAutoSaveInterval_${noteId}`]);
        }
        
        this[`canvasAutoSaveInterval_${noteId}`] = setInterval(() => {
            const instance = this.noteCanvasInstances.get(noteId);
            if (instance && instance.dirty) {
                this.saveCanvasNoteAuto(noteId);
                instance.dirty = false;
            }
        }, 5000);
    };
    
    /**
     * Auto-save canvas note
     */
    VeraChat.prototype.saveCanvasNoteAuto = function(noteId) {
        const instance = this.noteCanvasInstances.get(noteId);
        if (instance) {
            instance.dirty = true;
        }
    };
    
    /**
     * Manual save canvas note
     */
    VeraChat.prototype.saveCanvasNoteManual = async function(noteId) {
        const instance = this.noteCanvasInstances.get(noteId);
        const note = this.notes.find(n => n.id === noteId);
        
        if (!instance || !note) return;
        
        const statusEl = document.getElementById(`canvas-save-status-${noteId}`);
        if (statusEl) statusEl.textContent = 'Saving...';
        
        try {
            const sessionId = note.notebook_id ? 
                this.notebooks.find(nb => nb.id === note.notebook_id)?.session_id || this.sessionId :
                this.sessionId;
            
            const content = JSON.stringify({
                type: 'canvas',
                canvases: instance.state
            });
            
            const response = await fetch(
                `http://llm.int:8888/api/notebooks/${sessionId}/${note.notebook_id}/notes/${noteId}/update`,
                {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        content: content,
                        metadata: note.metadata
                    })
                }
            );
            
            if (response.ok) {
                note.content = content;
                note.updated_at = new Date().toISOString();
                if (statusEl) {
                    statusEl.textContent = '✅ Saved';
                    statusEl.style.color = 'var(--success)';
                    setTimeout(() => statusEl.textContent = '', 2000);
                }
                instance.dirty = false;
            } else {
                throw new Error('Failed to save');
            }
        } catch (error) {
            console.error('Error saving canvas note:', error);
            if (statusEl) {
                statusEl.textContent = '❌ Error';
                statusEl.style.color = 'var(--danger)';
            }
            this.showToast('Failed to save canvas note', 'error');
        }
    };
    
    /**
     * Save canvas note title
     */
    VeraChat.prototype.saveCanvasNoteTitle = async function(noteId, newTitle) {
        const note = this.notes.find(n => n.id === noteId);
        if (!note) return;
        
        try {
            const sessionId = note.notebook_id ? 
                this.notebooks.find(nb => nb.id === note.notebook_id)?.session_id || this.sessionId :
                this.sessionId;
            
            const response = await fetch(
                `http://llm.int:8888/api/notebooks/${sessionId}/${note.notebook_id}/notes/${noteId}/update`,
                {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ title: newTitle })
                }
            );
            
            if (response.ok) {
                note.title = newTitle;
                note.updated_at = new Date().toISOString();
                this.updateNotesUI();
            }
        } catch (error) {
            console.error('Error saving title:', error);
        }
    };
    
    /**
     * Render regular text note (FIXED VERSION with proper saving)
     */
    VeraChat.prototype.renderTextNote = function() {
        const container = document.getElementById('note-editor');
        
        container.innerHTML = `
            <div style="height: 100%; display: flex; flex-direction: column; padding: 20px;">
                <div style="margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center;">
                    <input 
                        type="text" 
                        id="note-title-input" 
                        value="${this.escapeHtml(this.currentNote.title)}"
                        style="flex: 1; padding: 8px 12px; background: var(--bg); border: 1px solid var(--border); color: var(--text); font-size: 20px; font-weight: 600; border-radius: 4px;"
                        placeholder="Note title"
                    />
                    <button class="panel-btn" onclick="app.convertNoteType('${this.currentNote.id}', 'canvas')" style="margin-left: 12px;" title="Convert to canvas note">
                        Canvas
                    </button>
                </div>
                
                <textarea 
                    id="note-editor-area"
                    style="flex: 1; padding: 16px; background: var(--bg); border: 1px solid var(--border); color: var(--text); border-radius: 4px; resize: none; font-size: 14px; line-height: 1.6;"
                    placeholder="Write your note here..."
                >${this.escapeHtml(this.currentNote.content || '')}</textarea>
                
                <div style="margin-top: 12px; display: flex; justify-content: space-between; align-items: center;">
                    <span id="note-save-status" style="font-size: 12px;"></span>
                    <button class="panel-btn" onclick="app.saveCurrentNote()" style="background: var(--accent);" title="Save (Ctrl+S)">💾 Save</button>
                </div>
            </div>
        `;
        
        // Setup auto-save
        const titleInput = document.getElementById('note-title-input');
        const contentInput = document.getElementById('note-editor-area');
        
        [titleInput, contentInput].forEach(input => {
            input?.addEventListener('input', () => {
                this.autoSaveNote();
            });
        });
        
        // Setup Ctrl+S shortcut
        contentInput?.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 's') {
                e.preventDefault();
                this.saveCurrentNote();
            }
        });
    };
    
    /**
     * FIXED saveCurrentNote that works with both old and new IDs
     */
    const originalSaveCurrentNote = VeraChat.prototype.saveCurrentNote;
    VeraChat.prototype.saveCurrentNote = async function() {
        if (!this.currentNote || this.notebookState.isSaving) return;
        
        // Try to find textarea with either ID
        const textarea = document.getElementById('note-editor-area') || 
                        document.querySelector('#note-editor textarea');
        const titleInput = document.getElementById('note-title-input');
        
        if (!textarea) {
            console.warn('Could not find note editor textarea');
            return;
        }
        
        const content = textarea.value;
        const title = titleInput ? titleInput.value : this.currentNote.title;
        
        // Check if anything changed
        if (content === this.currentNote.content && title === this.currentNote.title) {
            return; // No changes
        }
        
        this.notebookState.isSaving = true;
        this.updateSaveStatus('Saving...');
        
        try {
            const sessionId = this.currentNotebook.session_id || this.sessionId;
            const updateData = {};
            
            if (content !== this.currentNote.content) {
                updateData.content = content;
            }
            if (title !== this.currentNote.title) {
                updateData.title = title;
            }
            
            const response = await fetch(
                `http://llm.int:8888/api/notebooks/${sessionId}/${this.currentNotebook.id}/notes/${this.currentNote.id}/update`,
                {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(updateData)
                }
            );
            
            if (!response.ok) throw new Error('Failed to save note');
            
            this.currentNote.content = content;
            this.currentNote.title = title;
            this.currentNote.updated_at = new Date().toISOString();
            
            // Update preview in sidebar
            const noteItem = document.querySelector(`.note-item[data-note-id="${this.currentNote.id}"]`);
            if (noteItem) {
                const titleEl = noteItem.querySelector('.note-title');
                const previewEl = noteItem.querySelector('.note-preview');
                if (titleEl) titleEl.textContent = title;
                if (previewEl) previewEl.textContent = content.substring(0, 60);
            }
            
            this.updateSaveStatus('Saved');
            setTimeout(() => this.updateSaveStatus(''), 2000);
        } catch (error) {
            console.error('Failed to save note:', error);
            this.updateSaveStatus('Error saving');
            this.showToast('Failed to save note', 'error');
        } finally {
            this.notebookState.isSaving = false;
        }
    };
    
    /**
     * Convert note type
     */
    VeraChat.prototype.convertNoteType = async function(noteId, targetType) {
        const note = this.notes.find(n => n.id === noteId);
        if (!note) return;
        
        const currentType = note.metadata?.type || 'text';
        
        if (currentType === targetType) {
            this.showToast('Note is already that type', 'info');
            return;
        }
        
        const confirmMsg = targetType === 'canvas' ?
            'Convert this text note to a Canvas note? You can execute code in Canvas notes.' :
            'Convert this Canvas note to a text note? Code execution will be disabled.';
        
        if (!confirm(confirmMsg)) return;
        
        try {
            const sessionId = note.notebook_id ? 
                this.notebooks.find(nb => nb.id === note.notebook_id)?.session_id || this.sessionId :
                this.sessionId;
            
            let newContent = note.content;
            let newMetadata = { ...note.metadata, type: targetType };
            
            if (targetType === 'canvas') {
                // Convert text to canvas
                newContent = JSON.stringify({
                    type: 'canvas',
                    canvases: [{
                        id: `canvas-${Date.now()}`,
                        parser: 'python',
                        content: note.content || '# Start coding here!',
                        output: '',
                        files: []
                    }]
                });
            } else {
                // Convert canvas to text
                try {
                    const canvasData = JSON.parse(note.content);
                    newContent = canvasData.canvases?.map(c => c.content).join('\n\n---\n\n') || '';
                } catch {
                    newContent = note.content;
                }
            }
            
            const response = await fetch(
                `http://llm.int:8888/api/notebooks/${sessionId}/${note.notebook_id}/notes/${noteId}/update`,
                {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        content: newContent,
                        metadata: newMetadata
                    })
                }
            );
            
            if (response.ok) {
                note.content = newContent;
                note.metadata = newMetadata;
                this.showToast(`Converted to ${targetType} note`, 'success');
                this.renderNoteEditor();
            } else {
                throw new Error('Failed to convert note');
            }
        } catch (error) {
            console.error('Error converting note:', error);
            this.showToast('Failed to convert note', 'error');
        }
    };
    
    // Initialize on load
    if (!window.app.notebookCanvasInitialized) {
        window.app.initNotebookCanvas();
    }
    
    console.log('✅ Full Canvas Notebook Integration loaded!');
    
})();