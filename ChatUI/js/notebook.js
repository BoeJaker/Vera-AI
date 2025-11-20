(() => {
    // ============================================================
    // Enhanced Notebooks UI with Optimizations
    // ============================================================
    
    // State management
    VeraChat.prototype.notebookState = {
        isLoading: false,
        isSaving: false,
        searchQuery: '',
        sortBy: 'updated_at',
        sortOrder: 'desc',
        autoSaveTimeout: null,
        storageType: null
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
    // Enhanced Notebook Management
    // ============================================================
    
    VeraChat.prototype.loadNotebooks = async function() {
        if (!this.sessionId || this.notebookState.isLoading) return;
        
        this.notebookState.isLoading = true;
        
        try {
            const response = await fetch(`http://llm.int:8888/api/notebooks/${this.sessionId}`);
            if (!response.ok) throw new Error('Failed to load notebooks');
            
            const data = await response.json();
            this.notebooks = data.notebooks || [];
            this.notebookState.storageType = data.storage_type;
            this.updateNotebookSelector();
            
            // Show storage type indicator
            if (data.storage_type === 'file') {
                this.showToast('Using file storage (Neo4j unavailable)', 'info');
            }
        } catch (error) {
            console.error('Failed to load notebooks:', error);
            this.showToast('Failed to load notebooks', 'error');
        } finally {
            this.notebookState.isLoading = false;
        }
    };

    VeraChat.prototype.createNotebook = async function() {
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
                const response = await fetch(`http://llm.int:8888/api/notebooks/${this.sessionId}/create`, {
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
            const response = await fetch(
                `http://llm.int:8888/api/notebooks/${this.sessionId}/${this.currentNotebook.id}`,
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
        this.notebooks.forEach(nb => {
            const option = document.createElement('option');
            option.value = nb.id;
            option.textContent = `${nb.name} (${nb.note_count || 0} notes)`;
            if (this.currentNotebook && nb.id === this.currentNotebook.id) {
                option.selected = true;
            }
            selector.appendChild(option);
        });
        
        if (deleteBtn) {
            deleteBtn.disabled = !this.currentNotebook;
        }
        
        // Update storage indicator
        if (storageIndicator && this.notebookState.storageType) {
            storageIndicator.textContent = this.notebookState.storageType === 'file' ? '📁 File Storage' : '🗄️ Neo4j';
            storageIndicator.style.color = this.notebookState.storageType === 'file' ? '#f59e0b' : '#10b981';
        }
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
        await this.loadNotes();
        this.updateNotebookSelector();
    };

    // ============================================================
    // Enhanced Notes Management
    // ============================================================
    
    VeraChat.prototype.loadNotes = async function() {
        if (!this.currentNotebook || this.notebookState.isLoading) return;
        
        this.notebookState.isLoading = true;
        this.updateNotesUI(); // Show loading state
        
        try {
            const params = new URLSearchParams({
                sort_by: this.notebookState.sortBy,
                order: this.notebookState.sortOrder
            });
            
            const response = await fetch(
                `http://llm.int:8888/api/notebooks/${this.sessionId}/${this.currentNotebook.id}/notes?${params}`
            );
            
            if (!response.ok) throw new Error('Failed to load notes');
            
            const data = await response.json();
            this.notes = data.notes || [];
            this.updateNotesUI();
        } catch (error) {
            console.error('Failed to load notes:', error);
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
                const response = await fetch(
                    `http://llm.int:8888/api/notebooks/${this.sessionId}/${this.currentNotebook.id}/notes/create`,
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
            const response = await fetch(
                `http://llm.int:8888/api/notebooks/${this.sessionId}/${this.currentNotebook.id}/notes/${this.currentNote.id}/update`,
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
            const response = await fetch(
                `http://llm.int:8888/api/notebooks/${this.sessionId}/${this.currentNotebook.id}/notes/${noteId}`,
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
                const response = await fetch(
                    `http://llm.int:8888/api/notebooks/${this.sessionId}/${this.currentNotebook.id}/notes/create`,
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
})();