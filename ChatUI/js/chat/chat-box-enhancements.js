// =====================================================================
// Chat Input Enhancements
// - Large paste detection with attachment UI
// - Dynamic textarea expansion
// =====================================================================

(() => {
    console.log('🎯 Loading Chat Input Enhancements...');

    // =====================================================================
    // Configuration
    // =====================================================================
    
    const CONFIG = {
        LARGE_PASTE_THRESHOLD: 1000, // Characters
        MAX_TEXTAREA_HEIGHT: 300,    // Pixels
        MIN_TEXTAREA_HEIGHT: 44,     // Pixels
        LINE_HEIGHT: 20,             // Approximate line height in pixels
    };

    // =====================================================================
    // Large Paste Detection & Attachment System
    // =====================================================================
    
    VeraChat.prototype.initPasteDetection = function() {
        const messageInput = document.getElementById('messageInput');
        if (!messageInput) {
            console.error('❌ Message input not found for paste detection');
            setTimeout(() => this.initPasteDetection(), 500);
            return;
        }

        // Storage for attached pastes
        if (!this.attachedPastes) {
            this.attachedPastes = [];
        }

        // Remove any existing listeners to avoid duplicates
        if (this._pasteHandler) {
            messageInput.removeEventListener('paste', this._pasteHandler);
        }

        // Create and store the handler
        this._pasteHandler = (e) => {
            console.log('📋 Paste event detected');
            this.handleLargePaste(e);
        };

        // Listen for paste events
        messageInput.addEventListener('paste', this._pasteHandler);

        console.log('✅ Paste detection initialized on messageInput');
    };

    VeraChat.prototype.handleLargePaste = function(event) {
        console.log('🔍 handleLargePaste called');
        
        const clipboardData = event.clipboardData || window.clipboardData;
        if (!clipboardData) {
            console.warn('⚠️ No clipboard data available');
            return;
        }

        const pastedText = clipboardData.getData('text');
        console.log(`📊 Pasted text length: ${pastedText.length} characters`);
        console.log(`📊 Threshold: ${CONFIG.LARGE_PASTE_THRESHOLD} characters`);

        if (pastedText.length >= CONFIG.LARGE_PASTE_THRESHOLD) {
            console.log(`✅ Large paste detected: ${pastedText.length} characters`);
            
            // Prevent default paste
            event.preventDefault();

            // Create attachment
            this.createPasteAttachment(pastedText);

            // Show notification
            const sizeStr = this.formatFileSize(pastedText.length);
            this.setControlStatus(`📎 Large text attached (${sizeStr})`);
            
            console.log('✅ Attachment created successfully');
        } else {
            console.log(`ℹ️ Text too small for attachment (${pastedText.length} < ${CONFIG.LARGE_PASTE_THRESHOLD})`);
        }
    };

    VeraChat.prototype.createPasteAttachment = function(content) {
        const attachmentId = `paste-${Date.now()}`;
        
        const attachment = {
            id: attachmentId,
            type: 'text',
            content: content,
            size: content.length,
            timestamp: new Date()
        };

        this.attachedPastes.push(attachment);

        // Create visual element
        this.renderPasteAttachment(attachment);

        // Ensure attachments container exists
        this.ensureAttachmentsContainer();
    };

    VeraChat.prototype.ensureAttachmentsContainer = function() {
        let container = document.getElementById('attachments-container');
        if (container) return;

        // Find input area
        const inputArea = document.querySelector('.chat-input-area') || 
                         document.getElementById('messageInput')?.parentElement;
        
        if (!inputArea) {
            console.error('❌ Could not find input area');
            return;
        }

        // Create container
        container = document.createElement('div');
        container.id = 'attachments-container';
        container.className = 'attachments-container';

        // Insert before input
        const messageInput = document.getElementById('messageInput');
        if (messageInput) {
            messageInput.parentElement.insertBefore(container, messageInput);
        } else {
            inputArea.insertBefore(container, inputArea.firstChild);
        }
    };

    VeraChat.prototype.renderPasteAttachment = function(attachment) {
        const container = document.getElementById('attachments-container');
        if (!container) {
            this.ensureAttachmentsContainer();
            return this.renderPasteAttachment(attachment);
        }

        const attachmentEl = document.createElement('div');
        attachmentEl.className = 'paste-attachment';
        attachmentEl.id = attachment.id;
        attachmentEl.dataset.attachmentId = attachment.id;

        // Truncate preview
        const preview = attachment.content.substring(0, 100) + 
                       (attachment.content.length > 100 ? '...' : '');

        attachmentEl.innerHTML = `
            <div class="attachment-icon">📋</div>
            <div class="attachment-content">
                <div class="attachment-header">
                    <span class="attachment-title">Pasted Text</span>
                    <span class="attachment-size">${this.formatFileSize(attachment.size)}</span>
                </div>
                <div class="attachment-preview">${this.escapeHtml(preview)}</div>
            </div>
            <div class="attachment-actions">
                <button class="attachment-btn view-btn" 
                        onclick="app.viewPasteAttachment('${attachment.id}'); event.stopPropagation();"
                        title="View full content">
                    👁️
                </button>
                <button class="attachment-btn edit-btn" 
                        onclick="app.editPasteAttachment('${attachment.id}'); event.stopPropagation();"
                        title="Edit content">
                    ✏️
                </button>
                <button class="attachment-btn remove-btn" 
                        onclick="app.removePasteAttachment('${attachment.id}'); event.stopPropagation();"
                        title="Remove">
                    ✕
                </button>
            </div>
        `;

        container.appendChild(attachmentEl);

        // Animate in
        setTimeout(() => attachmentEl.classList.add('visible'), 10);
    };

    VeraChat.prototype.viewPasteAttachment = function(attachmentId) {
        const attachment = this.attachedPastes.find(a => a.id === attachmentId);
        if (!attachment) return;

        // Create modal
        const modal = document.createElement('div');
        modal.className = 'paste-viewer-modal';
        modal.innerHTML = `
            <div class="modal-overlay" onclick="this.parentElement.remove()"></div>
            <div class="modal-content paste-viewer">
                <div class="modal-header">
                    <h3>📋 Pasted Content</h3>
                    <div class="modal-header-actions">
                        <span class="attachment-size">${this.formatFileSize(attachment.size)}</span>
                        <button class="icon-btn" onclick="app.copyToClipboard('${attachmentId}'); event.stopPropagation();" title="Copy">
                            📋
                        </button>
                        <button class="icon-btn" onclick="this.closest('.paste-viewer-modal').remove();" title="Close">
                            ✕
                        </button>
                    </div>
                </div>
                <div class="modal-body">
                    <pre class="paste-content">${this.escapeHtml(attachment.content)}</pre>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
        setTimeout(() => modal.classList.add('visible'), 10);
    };

    VeraChat.prototype.editPasteAttachment = function(attachmentId) {
        const attachment = this.attachedPastes.find(a => a.id === attachmentId);
        if (!attachment) return;

        // Create editor modal
        const modal = document.createElement('div');
        modal.className = 'paste-editor-modal';
        modal.innerHTML = `
            <div class="modal-overlay" onclick="if(confirm('Discard changes?')) this.parentElement.remove();"></div>
            <div class="modal-content paste-editor">
                <div class="modal-header">
                    <h3>✏️ Edit Pasted Content</h3>
                    <button class="icon-btn" onclick="this.closest('.paste-editor-modal').remove();">✕</button>
                </div>
                <div class="modal-body">
                    <textarea class="paste-edit-area" id="paste-edit-${attachmentId}">${this.escapeHtml(attachment.content)}</textarea>
                </div>
                <div class="modal-footer">
                    <button class="modal-btn secondary" onclick="this.closest('.paste-editor-modal').remove();">
                        Cancel
                    </button>
                    <button class="modal-btn primary" onclick="app.savePasteEdit('${attachmentId}');">
                        💾 Save Changes
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
        setTimeout(() => {
            modal.classList.add('visible');
            document.getElementById(`paste-edit-${attachmentId}`)?.focus();
        }, 10);
    };

    VeraChat.prototype.savePasteEdit = function(attachmentId) {
        const textarea = document.getElementById(`paste-edit-${attachmentId}`);
        if (!textarea) return;

        const newContent = textarea.value;
        const attachment = this.attachedPastes.find(a => a.id === attachmentId);
        
        if (attachment) {
            attachment.content = newContent;
            attachment.size = newContent.length;

            // Update visual
            const attachmentEl = document.getElementById(attachmentId);
            if (attachmentEl) {
                const preview = newContent.substring(0, 100) + 
                               (newContent.length > 100 ? '...' : '');
                attachmentEl.querySelector('.attachment-preview').textContent = preview;
                attachmentEl.querySelector('.attachment-size').textContent = 
                    this.formatFileSize(newContent.length);
            }

            this.setControlStatus('✅ Content updated');
        }

        // Close modal
        document.querySelector('.paste-editor-modal')?.remove();
    };

    VeraChat.prototype.copyToClipboard = function(attachmentId) {
        const attachment = this.attachedPastes.find(a => a.id === attachmentId);
        if (!attachment) return;

        navigator.clipboard.writeText(attachment.content).then(() => {
            this.setControlStatus('📋 Copied to clipboard');
        }).catch(err => {
            console.error('Copy failed:', err);
            this.setControlStatus('❌ Copy failed');
        });
    };

    VeraChat.prototype.removePasteAttachment = function(attachmentId) {
        // Remove from array
        this.attachedPastes = this.attachedPastes.filter(a => a.id !== attachmentId);

        // Remove visual element
        const attachmentEl = document.getElementById(attachmentId);
        if (attachmentEl) {
            attachmentEl.classList.remove('visible');
            setTimeout(() => attachmentEl.remove(), 300);
        }

        this.setControlStatus('🗑️ Attachment removed');
    };

    VeraChat.prototype.formatFileSize = function(bytes) {
        if (typeof bytes !== 'number' || isNaN(bytes)) {
            bytes = String(bytes).length;
        }
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    };

    // =====================================================================
    // Dynamic Textarea Expansion
    // =====================================================================

    VeraChat.prototype.initDynamicTextarea = function() {
        const messageInput = document.getElementById('messageInput');
        if (!messageInput) {
            console.error('❌ Message input not found for dynamic textarea');
            setTimeout(() => this.initDynamicTextarea(), 500);
            return;
        }

        // Set initial styles
        messageInput.style.minHeight = CONFIG.MIN_TEXTAREA_HEIGHT + 'px';
        messageInput.style.maxHeight = CONFIG.MAX_TEXTAREA_HEIGHT + 'px';
        messageInput.style.height = 'auto';
        messageInput.style.overflowY = 'hidden';
        messageInput.style.resize = 'none';
        messageInput.style.transition = 'height 0.1s ease';

        // Remove existing listeners to avoid duplicates
        if (this._inputHandler) {
            messageInput.removeEventListener('input', this._inputHandler);
        }
        if (this._pasteHeightHandler) {
            messageInput.removeEventListener('paste', this._pasteHeightHandler);
        }

        // Create handlers
        this._inputHandler = () => {
            this.adjustTextareaHeight(messageInput);
        };

        this._pasteHeightHandler = () => {
            setTimeout(() => this.adjustTextareaHeight(messageInput), 10);
        };

        // Listen for input changes
        messageInput.addEventListener('input', this._inputHandler);

        // Listen for paste (in case content changes)
        messageInput.addEventListener('paste', this._pasteHeightHandler);

        // Add MutationObserver to catch programmatic value changes
        if (this._textareaObserver) {
            this._textareaObserver.disconnect();
        }

        this._textareaObserver = new MutationObserver(() => {
            this.adjustTextareaHeight(messageInput);
        });

        // Watch for attribute changes (like value)
        this._textareaObserver.observe(messageInput, {
            attributes: true,
            attributeFilter: ['value']
        });

        // Also create a polling mechanism as backup for programmatic changes
        // Store reference to clear on cleanup
        if (this._heightCheckInterval) {
            clearInterval(this._heightCheckInterval);
        }

        let lastValue = messageInput.value;
        this._heightCheckInterval = setInterval(() => {
            if (messageInput.value !== lastValue) {
                lastValue = messageInput.value;
                this.adjustTextareaHeight(messageInput);
            }
        }, 100);

        // Expose global helper for programmatic updates
        window.updateTextareaHeight = () => {
            if (this && typeof this.adjustTextareaHeight === 'function') {
                this.adjustTextareaHeight(messageInput);
            }
        };

        console.log('✅ Dynamic textarea initialized with programmatic change detection');
    };

    VeraChat.prototype.adjustTextareaHeight = function(textarea) {
        // Reset height to auto to get accurate scrollHeight
        textarea.style.height = 'auto';

        // Calculate new height
        let newHeight = textarea.scrollHeight;

        // Apply constraints
        newHeight = Math.max(CONFIG.MIN_TEXTAREA_HEIGHT, newHeight);
        newHeight = Math.min(CONFIG.MAX_TEXTAREA_HEIGHT, newHeight);

        // Set new height
        textarea.style.height = newHeight + 'px';

        // Show/hide scrollbar
        if (newHeight >= CONFIG.MAX_TEXTAREA_HEIGHT) {
            textarea.style.overflowY = 'auto';
        } else {
            textarea.style.overflowY = 'hidden';
        }
    };

    // Public method to force textarea height update (call after programmatic changes)
    VeraChat.prototype.updateTextareaHeight = function() {
        const messageInput = document.getElementById('messageInput');
        if (messageInput) {
            this.adjustTextareaHeight(messageInput);
        }
    };

    VeraChat.prototype.resetTextareaHeight = function() {
        const messageInput = document.getElementById('messageInput');
        if (messageInput) {
            messageInput.style.height = 'auto';
            messageInput.style.overflowY = 'hidden';
        }
    };

    // =====================================================================
    // Enhanced Send Message - Include Attachments
    // =====================================================================

    // Store original sendMessage if not already stored
    if (!VeraChat.prototype._originalSendMessage) {
        VeraChat.prototype._originalSendMessage = VeraChat.prototype.sendMessage;
    }

    VeraChat.prototype.sendMessage = async function() {
        const input = document.getElementById('messageInput');
        let message = input.value.trim();

        // Include attached pastes
        if (this.attachedPastes && this.attachedPastes.length > 0) {
            console.log(`📎 Including ${this.attachedPastes.length} attached paste(s)`);
            
            this.attachedPastes.forEach(attachment => {
                message += '\n\n---\n**Attached Text:**\n```\n' + attachment.content + '\n```';
            });

            // Clear attachments after including
            this.attachedPastes = [];
            const container = document.getElementById('attachments-container');
            if (container) container.innerHTML = '';
        }

        if (!message || this.processing) return;

        // Update input value to include attachments
        input.value = message;

        // Call original send
        await this._originalSendMessage.call(this);

        // Reset textarea height after send
        this.resetTextareaHeight();
    };

    // =====================================================================
    // Styles
    // =====================================================================

    const styles = `
        /* Attachments Container */
        .attachments-container {
            display: flex;
            flex-direction: column;
            gap: 8px;
            padding: 8px 12px;
            background: var(--panel-bg, #1e293b);
            border-bottom: 1px solid var(--border, #334155);
            max-height: 200px;
            overflow-y: auto;
        }

        .attachments-container:empty {
            display: none;
        }

        /* Paste Attachment Card */
        .paste-attachment {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 10px 12px;
            background: var(--bg, #0f172a);
            border: 1px solid var(--border, #334155);
            border-radius: 8px;
            opacity: 0;
            transform: translateY(-10px);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }

        .paste-attachment.visible {
            opacity: 1;
            transform: translateY(0);
        }

        .attachment-icon {
            font-size: 24px;
            flex-shrink: 0;
        }

        .attachment-content {
            flex: 1;
            min-width: 0;
        }

        .attachment-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 4px;
        }

        .attachment-title {
            font-weight: 600;
            font-size: 13px;
            color: var(--text, #e2e8f0);
        }

        .attachment-size {
            font-size: 11px;
            color: var(--text-muted, #94a3b8);
            background: var(--panel-bg, #1e293b);
            padding: 2px 6px;
            border-radius: 4px;
        }

        .attachment-preview {
            font-size: 12px;
            color: var(--text-muted, #94a3b8);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            font-family: monospace;
        }

        .attachment-actions {
            display: flex;
            gap: 4px;
            flex-shrink: 0;
        }

        .attachment-btn {
            width: 32px;
            height: 32px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: transparent;
            border: 1px solid var(--border, #334155);
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.2s;
        }

        .attachment-btn:hover {
            background: var(--panel-bg, #1e293b);
            border-color: var(--accent, #3b82f6);
        }

        .attachment-btn.remove-btn:hover {
            background: rgba(239, 68, 68, 0.1);
            border-color: #ef4444;
            color: #ef4444;
        }

        /* Paste Viewer Modal */
        .paste-viewer-modal, .paste-editor-modal {
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            z-index: 100000;
            display: flex;
            align-items: center;
            justify-content: center;
            opacity: 0;
            transition: opacity 0.3s ease;
        }

        .paste-viewer-modal.visible, .paste-editor-modal.visible {
            opacity: 1;
        }

        .paste-viewer-modal .modal-overlay, .paste-editor-modal .modal-overlay {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.7);
            backdrop-filter: blur(4px);
        }

        .paste-viewer .modal-content, .paste-editor .modal-content {
            position: relative;
            width: 90%;
            max-width: 800px;
            max-height: 80vh;
            background: var(--panel-bg, #1e293b);
            border: 1px solid var(--border, #334155);
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
            display: flex;
            flex-direction: column;
        }

        .paste-viewer-modal .modal-header, .paste-editor-modal .modal-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 16px 20px;
            border-bottom: 1px solid var(--border, #334155);
            background: var(--bg, #0f172a);
            border-radius: 12px 12px 0 0;
        }

        .modal-header h3 {
            margin: 0;
            font-size: 16px;
            font-weight: 600;
            color: var(--text, #e2e8f0);
        }

        .modal-header-actions {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .icon-btn {
            background: transparent;
            border: 1px solid var(--border, #334155);
            color: var(--text, #e2e8f0);
            width: 32px;
            height: 32px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s;
        }

        .icon-btn:hover {
            background: var(--panel-bg, #1e293b);
            border-color: var(--accent, #3b82f6);
        }

        .paste-viewer-modal .modal-body, .paste-editor-modal .modal-body {
            flex: 1;
            overflow: auto;
            padding: 20px;
        }

        .paste-content {
            margin: 0;
            padding: 16px;
            background: var(--bg, #0f172a);
            border: 1px solid var(--border, #334155);
            border-radius: 8px;
            color: var(--text, #e2e8f0);
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            font-size: 13px;
            line-height: 1.6;
            white-space: pre-wrap;
            word-wrap: break-word;
        }

        .paste-edit-area {
            width: 100%;
            min-height: 400px;
            padding: 16px;
            background: var(--bg, #0f172a);
            border: 1px solid var(--border, #334155);
            border-radius: 8px;
            color: var(--text, #e2e8f0);
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            font-size: 13px;
            line-height: 1.6;
            resize: vertical;
            outline: none;
        }

        .paste-edit-area:focus {
            border-color: var(--accent, #3b82f6);
            box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.1);
        }

        .modal-footer {
            display: flex;
            justify-content: flex-end;
            gap: 12px;
            padding: 16px 20px;
            border-top: 1px solid var(--border, #334155);
            background: var(--bg, #0f172a);
            border-radius: 0 0 12px 12px;
        }

        .modal-btn {
            padding: 10px 20px;
            border: 1px solid var(--border, #334155);
            border-radius: 6px;
            cursor: pointer;
            font-size: 13px;
            font-weight: 500;
            transition: all 0.2s;
        }

        .modal-btn.secondary {
            background: transparent;
            color: var(--text, #e2e8f0);
        }

        .modal-btn.secondary:hover {
            background: var(--panel-bg, #1e293b);
        }

        .modal-btn.primary {
            background: var(--accent, #3b82f6);
            border-color: var(--accent, #3b82f6);
            color: white;
        }

        .modal-btn.primary:hover {
            background: var(--accent-hover, #2563eb);
            border-color: var(--accent-hover, #2563eb);
        }

        /* Dynamic Textarea Enhancements */
        #messageInput {
            transition: height 0.1s ease;
        }

        /* Scrollbar for attachments container */
        .attachments-container::-webkit-scrollbar {
            width: 6px;
        }

        .attachments-container::-webkit-scrollbar-track {
            background: transparent;
        }

        .attachments-container::-webkit-scrollbar-thumb {
            background: var(--border, #334155);
            border-radius: 3px;
        }

        .attachments-container::-webkit-scrollbar-thumb:hover {
            background: var(--text-muted, #94a3b8);
        }
    `;

    // Inject styles
    if (!document.getElementById('chat-input-enhancement-styles')) {
        const styleEl = document.createElement('style');
        styleEl.id = 'chat-input-enhancement-styles';
        styleEl.textContent = styles;
        document.head.appendChild(styleEl);
    }

    // =====================================================================
    // Initialize on VeraChat
    // =====================================================================

    // Wrap initialization
    if (!VeraChat.prototype._inputEnhancementsWrapped) {
        const originalInit = VeraChat.prototype.init || VeraChat.prototype._originalInit;
        
        if (originalInit) {
            VeraChat.prototype.init = async function() {
                console.log('🔄 VeraChat.init with input enhancements');
                
                const result = await originalInit.call(this);
                
                // Initialize enhancements immediately
                console.log('🎯 Initializing paste detection and dynamic textarea...');
                this.initPasteDetection();
                this.initDynamicTextarea();

                return result;
            };
            
            VeraChat.prototype._inputEnhancementsWrapped = true;
            console.log('✅ Input enhancements wrapper installed');
        }
    }

    // Also try immediate initialization if app/VeraChat instance already exists
    if (typeof app !== 'undefined' && app) {
        console.log('🚀 Attempting immediate initialization on existing app instance');
        setTimeout(() => {
            if (typeof app.initPasteDetection === 'function') {
                app.initPasteDetection();
            }
            if (typeof app.initDynamicTextarea === 'function') {
                app.initDynamicTextarea();
            }
        }, 100);
    }

    // Expose manual initialization helper for console debugging
    window.initChatEnhancements = function() {
        console.log('🔧 Manual initialization triggered');
        if (typeof app !== 'undefined' && app) {
            if (typeof app.initPasteDetection === 'function') {
                app.initPasteDetection();
                console.log('✅ Paste detection initialized');
            }
            if (typeof app.initDynamicTextarea === 'function') {
                app.initDynamicTextarea();
                console.log('✅ Dynamic textarea initialized');
            }
            console.log('✅ Manual initialization complete');
        } else {
            console.error('❌ app instance not found');
        }
    };

    console.log('🚀 Chat Input Enhancements loaded successfully');
    console.log('💡 Run initChatEnhancements() from console to manually initialize');
})();