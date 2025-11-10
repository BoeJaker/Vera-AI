(() => {
        VeraChat.prototype.loadNotebooks = async function() {
            if (!this.sessionId) return;
            
            try {
                const response = await fetch(`http://llm.int:8888/api/notebooks/${this.sessionId}`);
                const data = await response.json();
                this.notebooks = data.notebooks || [];
                this.updateNotebookSelector();
            } catch (error) {
                console.error('Failed to load notebooks:', error);
            }
        }

        VeraChat.prototype.createNotebook = async function() {
            const name = prompt('Enter notebook name:');
            if (!name || !name.trim()) return;
            
            try {
                const response = await fetch(`http://llm.int:8888/api/notebooks/${this.sessionId}/create`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: name.trim() })
                });
                
                const data = await response.json();
                this.notebooks.push(data.notebook);
                this.updateNotebookSelector();
                this.addSystemMessage(`Created notebook: ${name}`);
            } catch (error) {
                console.error('Failed to create notebook:', error);
            }
        }

        VeraChat.prototype.deleteCurrentNotebook = async function() {
            if (!this.currentNotebook) return;
            if (!confirm(`Delete notebook "${this.currentNotebook.name}"?`)) return;
            
            try {
                await fetch(`http://llm.int:8888/api/notebooks/${this.sessionId}/${this.currentNotebook.id}`, {
                    method: 'DELETE'
                });
                
                this.notebooks = this.notebooks.filter(nb => nb.id !== this.currentNotebook.id);
                this.currentNotebook = null;
                this.notes = [];
                this.currentNote = null;
                this.updateNotebookSelector();
                this.updateNotesUI();
                this.addSystemMessage('Notebook deleted');
            } catch (error) {
                console.error('Failed to delete notebook:', error);
            }
        }

        VeraChat.prototype.updateNotebookSelector = function() {
            const selector = document.getElementById('notebook-selector');
            const deleteBtn = document.getElementById('delete-notebook-btn');
            
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
            
            deleteBtn.disabled = !this.currentNotebook;
        }

        VeraChat.prototype.switchNotebook = async function(notebookId) {
            if (!notebookId) {
                this.currentNotebook = null;
                this.notes = [];
                this.updateNotesUI();
                return;
            }
            
            this.currentNotebook = this.notebooks.find(nb => nb.id === notebookId);
            await this.loadNotes();
            this.updateNotebookSelector();
        }

        // Notes Management
        VeraChat.prototype.loadNotes = async function() {
            if (!this.currentNotebook) return;
            
            try {
                const response = await fetch(`http://llm.int:8888/api/notebooks/${this.sessionId}/${this.currentNotebook.id}/notes`);
                const data = await response.json();
                this.notes = data.notes || [];
                this.updateNotesUI();
            } catch (error) {
                console.error('Failed to load notes:', error);
            }
        }

        VeraChat.prototype.createNote = async function() {
            if (!this.currentNotebook) {
                alert('Please select a notebook first');
                return;
            }
            
            const title = prompt('Enter note title:');
            if (!title || !title.trim()) return;
            
            try {
                const response = await fetch(`http://llm.int:8888/api/notebooks/${this.sessionId}/${this.currentNotebook.id}/notes/create`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        title: title.trim(),
                        content: ''
                    })
                });
                
                const data = await response.json();
                this.notes.push(data.note);
                this.updateNotesUI();
                this.selectNote(data.note.id);
            } catch (error) {
                console.error('Failed to create note:', error);
            }
        }

        VeraChat.prototype.selectNote = function(noteId) {
            this.currentNote = this.notes.find(n => n.id === noteId);
            this.updateNotesUI();
            this.renderNoteEditor();
        }

        VeraChat.prototype.saveCurrentNote = async function() {
            if (!this.currentNote) return;
            
            const textarea = document.getElementById('note-editor-area');
            if (!textarea) return;
            
            const content = textarea.value;
            
            try {
                await fetch(`http://llm.int:8888/api/notebooks/${this.sessionId}/${this.currentNotebook.id}/notes/${this.currentNote.id}/update`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ content: content })
                });
                
                this.currentNote.content = content;
                this.currentNote.updated_at = new Date().toISOString();
                
                // Update preview in sidebar
                const noteItem = document.querySelector(`.note-item[data-note-id="${this.currentNote.id}"] .note-preview`);
                if (noteItem) {
                    noteItem.textContent = content.substring(0, 50);
                }
            } catch (error) {
                console.error('Failed to save note:', error);
            }
        }

        VeraChat.prototype.deleteNote = async function(noteId) {
            if (!confirm('Delete this note?')) return;
            
            try {
                await fetch(`http://llm.int:8888/api/notebooks/${this.sessionId}/${this.currentNotebook.id}/notes/${noteId}`, {
                    method: 'DELETE'
                });
                
                this.notes = this.notes.filter(n => n.id !== noteId);
                if (this.currentNote && this.currentNote.id === noteId) {
                    this.currentNote = null;
                }
                this.updateNotesUI();
                this.renderNoteEditor();
            } catch (error) {
                console.error('Failed to delete note:', error);
            }
        }

        VeraChat.prototype.captureMessageAsNote = async function(messageId) {
            if (!this.currentNotebook) {
                alert('Please select a notebook first');
                return;
            }
            
            const message = this.messages.find(m => m.id === messageId);
            if (!message) return;
            
            const title = prompt('Note title:', `${message.role} - ${new Date(message.timestamp).toLocaleString()}`);
            if (!title) return;
            
            try {
                const response = await fetch(`http://llm.int:8888/api/notebooks/${this.sessionId}/${this.currentNotebook.id}/notes/create`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        title: title,
                        content: message.content,
                        source: {
                            type: 'chat_message',
                            message_id: messageId,
                            role: message.role,
                            timestamp: message.timestamp
                        }
                    })
                });
                
                const data = await response.json();
                this.notes.push(data.note);
                this.updateNotesUI();
                this.addSystemMessage(`Captured message as note: ${title}`);
            } catch (error) {
                console.error('Failed to capture message:', error);
            }
        }

        VeraChat.prototype.updateNotesUI = function() {
            const container = document.getElementById('notes-list');
            
            if (!this.currentNotebook) {
                container.innerHTML = '<p style="color: #94a3b8; font-size: 13px; text-align: center;">Select a notebook</p>';
                return;
            }
            
            if (this.notes.length === 0) {
                container.innerHTML = '<p style="color: #94a3b8; font-size: 13px; text-align: center;">No notes yet</p>';
                return;
            }
            
            container.innerHTML = '';
            this.notes.forEach(note => {
                const noteItem = document.createElement('div');
                noteItem.className = 'note-item';
                noteItem.setAttribute('data-note-id', note.id);
                if (this.currentNote && note.id === this.currentNote.id) {
                    noteItem.classList.add('active');
                }
                
                noteItem.innerHTML = `
                    <div class="note-title">${this.escapeHtml(note.title)}</div>
                    <div class="note-preview">${this.escapeHtml((note.content || '').substring(0, 50))}</div>
                    ${note.source ? '<span class="note-source-tag">From Chat</span>' : ''}
                    <div style="margin-top: 6px; display: flex; gap: 4px; justify-content: flex-end;">
                        <button class="panel-btn" style="padding: 2px 6px; font-size: 10px;" onclick="app.deleteNote('${note.id}')">🗑️</button>
                    </div>
                `;
                
                noteItem.addEventListener('click', (e) => {
                    if (!e.target.closest('button')) {
                        this.selectNote(note.id);
                    }
                });
                
                container.appendChild(noteItem);
            });
        }

        VeraChat.prototype.renderNoteEditor = function() {
            const container = document.getElementById('note-editor');
            
            if (!this.currentNote) {
                container.innerHTML = '<p style="color: #94a3b8; text-align: center; margin-top: 100px;">Select or create a note to start</p>';
                return;
            }
            
            container.innerHTML = `
                <div style="margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <h3 style="color: #60a5fa; margin: 0 0 8px 0;">${this.escapeHtml(this.currentNote.title)}</h3>
                        <div style="color: #94a3b8; font-size: 12px;">
                            ${this.currentNote.source ? `
                                <span class="note-source-tag">${this.currentNote.source.type}</span>
                            ` : ''}
                            Last updated: ${new Date(this.currentNote.updated_at || this.currentNote.created_at).toLocaleString()}
                        </div>
                    </div>
                    <div style="display: flex; gap: 8px;">
                        <button class="panel-btn" onclick="app.saveCurrentNote()">💾 Save</button>
                        <button class="panel-btn" onclick="app.exportNote()">📤 Export</button>
                    </div>
                </div>
                
                <textarea id="note-editor-area" placeholder="Write your note...">${this.escapeHtml(this.currentNote.content || '')}</textarea>
                
                ${this.currentNote.source ? `
                    <div style="margin-top: 16px; padding: 12px; background: #1e293b; border-radius: 6px; border-left: 3px solid #8b5cf6;">
                        <div style="color: #a78bfa; font-size: 11px; margin-bottom: 6px;">ORIGINAL MESSAGE</div>
                        <div style="color: #cbd5e1; font-size: 13px;">${this.parseMessageContent(this.currentNote.source.content || this.currentNote.content)}</div>
                    </div>
                ` : ''}
            `;
            
            // Auto-save on edit
            const textarea = document.getElementById('note-editor-area');
            let saveTimeout;
            textarea.addEventListener('input', () => {
                clearTimeout(saveTimeout);
                saveTimeout = setTimeout(() => this.saveCurrentNote(), 1000);
            });
        }

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
        }
})();