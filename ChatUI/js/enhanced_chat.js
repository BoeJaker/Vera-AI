// =====================================================================
// Modern Interactive Chat UI - FIXED VERSION
// Fixes: alignment, graph focus, menu positioning, tools
// =====================================================================

(() => {
    // =====================================================================
    // Initialize Modern Features
    // =====================================================================
    
    VeraChat.prototype.initModernFeatures = function() {
        this.canvasAutoFocus = localStorage.getItem('canvas-auto-focus') !== 'false';
        this.ttsEnabled = localStorage.getItem('tts-enabled') === 'true';
        this.sttActive = false;
        this.streamingBuffer = '';
        this.lastCanvasCheck = 0;
        
        // Initialize speech recognition
        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            this.recognition = new SpeechRecognition();
            this.recognition.continuous = false;
            this.recognition.interimResults = true;
            this.recognition.lang = 'en-US';
            
            this.recognition.onresult = (event) => {
                const transcript = Array.from(event.results)
                    .map(result => result[0].transcript)
                    .join('');
                
                const textarea = document.getElementById('messageInput');
                if (textarea) {
                    textarea.value = transcript;
                    textarea.dispatchEvent(new Event('input'));
                }
            };
            
            this.recognition.onend = () => {
                this.sttActive = false;
                this.updateControlBar();
            };
        }
        
        // Initialize speech synthesis
        this.ttsVoice = null;
        if ('speechSynthesis' in window) {
            speechSynthesis.onvoiceschanged = () => {
                const voices = speechSynthesis.getVoices();
                this.ttsVoice = voices.find(v => v.lang.startsWith('en')) || voices[0];
            };
        }
        
        // Ensure tools are loaded
        this.ensureToolsLoaded();
        
        this.addControlBar();
    };
    
    VeraChat.prototype.ensureToolsLoaded = async function() {
        if (this.availableTools && Object.keys(this.availableTools).length > 0) {
            return; // Already loaded
        }
        
        if (this.sessionId && typeof this.loadAvailableTools === 'function') {
            await this.loadAvailableTools();
        }
    };
    
    // =====================================================================
    // Control Bar
    // =====================================================================
    
    VeraChat.prototype.addControlBar = function() {
        const chatContainer = document.getElementById('tab-chat');
        if (!chatContainer) return;
        
        const existing = document.getElementById('chat-control-bar');
        if (existing) existing.remove();
        
        const controlBar = document.createElement('div');
        controlBar.id = 'chat-control-bar';
        controlBar.className = 'chat-control-bar';
        controlBar.innerHTML = `
            <div class="control-group">
                <button class="control-btn ${this.canvasAutoFocus ? 'active' : ''}" 
                        id="toggle-canvas-focus"
                        onclick="app.toggleCanvasFocus()"
                        title="Auto-focus canvas for code/diagrams">
                    <span class="control-icon">${this.canvasAutoFocus ? '🎯' : '⏸️'}</span>
                    <span class="control-label">Canvas</span>
                </button>
                
                <button class="control-btn ${this.ttsEnabled ? 'active' : ''}" 
                        id="toggle-tts"
                        onclick="app.toggleTTS()"
                        title="Read responses aloud">
                    <span class="control-icon">🔊</span>
                    <span class="control-label">TTS</span>
                </button>
                
                ${this.recognition ? `
                <button class="control-btn ${this.sttActive ? 'active recording' : ''}" 
                        id="toggle-stt"
                        onclick="app.toggleSTT()"
                        title="Voice input">
                    <span class="control-icon">🎤</span>
                    <span class="control-label">Voice</span>
                </button>
                ` : ''}
                
                <button class="control-btn" 
                        onclick="app.openFileUpload()"
                        title="Upload file">
                    <span class="control-icon">📎</span>
                    <span class="control-label">File</span>
                </button>
            </div>
            
            <div class="control-status" id="control-status"></div>
        `;
        
        const messages = chatContainer.querySelector('#chatMessages');
        if (messages) {
            chatContainer.insertBefore(controlBar, messages);
        }
    };
    
    VeraChat.prototype.updateControlBar = function() {
        const canvasBtn = document.getElementById('toggle-canvas-focus');
        const ttsBtn = document.getElementById('toggle-tts');
        const sttBtn = document.getElementById('toggle-stt');
        
        if (canvasBtn) {
            canvasBtn.className = `control-btn ${this.canvasAutoFocus ? 'active' : ''}`;
            canvasBtn.querySelector('.control-icon').textContent = this.canvasAutoFocus ? '🎯' : '⏸️';
        }
        
        if (ttsBtn) {
            ttsBtn.className = `control-btn ${this.ttsEnabled ? 'active' : ''}`;
        }
        
        if (sttBtn) {
            sttBtn.className = `control-btn ${this.sttActive ? 'active recording' : ''}`;
        }
    };
    
    VeraChat.prototype.setControlStatus = function(message, duration = 3000) {
        const status = document.getElementById('control-status');
        if (!status) return;
        
        status.textContent = message;
        status.style.opacity = '1';
        
        if (duration > 0) {
            setTimeout(() => {
                status.style.opacity = '0';
            }, duration);
        }
    };
    
    // Control functions
    VeraChat.prototype.toggleCanvasFocus = function() {
        this.canvasAutoFocus = !this.canvasAutoFocus;
        localStorage.setItem('canvas-auto-focus', this.canvasAutoFocus);
        this.updateControlBar();
        this.setControlStatus(
            this.canvasAutoFocus ? '🎯 Canvas auto-focus enabled' : '⏸️ Canvas auto-focus paused'
        );
    };
    
    VeraChat.prototype.toggleTTS = function() {
        this.ttsEnabled = !this.ttsEnabled;
        localStorage.setItem('tts-enabled', this.ttsEnabled);
        this.updateControlBar();
        
        if (this.ttsEnabled) {
            this.setControlStatus('🔊 Text-to-speech enabled');
            this.speakText('Text to speech enabled');
        } else {
            this.setControlStatus('🔇 Text-to-speech disabled');
            if ('speechSynthesis' in window) {
                speechSynthesis.cancel();
            }
        }
    };
    
    VeraChat.prototype.speakText = function(text) {
        if (!this.ttsEnabled || !('speechSynthesis' in window)) return;
        
        speechSynthesis.cancel();
        
        let cleanText = text
            .replace(/```[\s\S]*?```/g, ' code block ')
            .replace(/`([^`]+)`/g, '$1')
            .replace(/\*\*([^*]+)\*\*/g, '$1')
            .replace(/\*([^*]+)\*/g, '$1')
            .replace(/#{1,6}\s/g, '')
            .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
            .replace(/<[^>]+>/g, '')
            .trim();
        
        if (cleanText.length === 0) return;
        if (cleanText.length > 500) {
            cleanText = cleanText.substring(0, 497) + '...';
        }
        
        const utterance = new SpeechSynthesisUtterance(cleanText);
        utterance.voice = this.ttsVoice;
        utterance.rate = 1.0;
        utterance.pitch = 1.0;
        utterance.volume = 1.0;
        
        speechSynthesis.speak(utterance);
    };
    
    VeraChat.prototype.toggleSTT = function() {
        if (!this.recognition) {
            this.setControlStatus('❌ Speech recognition not available');
            return;
        }
        
        if (this.sttActive) {
            this.recognition.stop();
            this.sttActive = false;
            this.setControlStatus('🎤 Voice input stopped');
        } else {
            try {
                this.recognition.start();
                this.sttActive = true;
                this.setControlStatus('🎤 Listening... Speak now', 0);
            } catch (error) {
                console.error('Speech recognition error:', error);
                this.setControlStatus('❌ Could not start voice input');
            }
        }
        
        this.updateControlBar();
    };
    
    VeraChat.prototype.openFileUpload = function() {
        const input = document.createElement('input');
        input.type = 'file';
        input.multiple = true;
        input.accept = '*/*';
        
        input.onchange = (e) => {
            const files = Array.from(e.target.files);
            if (files.length > 0) {
                this.handleFileUpload(files);
            }
        };
        
        input.click();
    };
    
    VeraChat.prototype.handleFileUpload = async function(files) {
        this.setControlStatus(`📎 Uploading ${files.length} file(s)...`, 0);
        
        for (const file of files) {
            await this.uploadFile(file);
        }
        
        this.setControlStatus(`✅ Uploaded ${files.length} file(s)`);
    };
    
    VeraChat.prototype.uploadFile = async function(file) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('session_id', this.sessionId);
        
        try {
            const response = await fetch('http://llm.int:8888/api/upload', {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) throw new Error('Upload failed');
            
            const data = await response.json();
            this.addFileMessage(file, data);
            
        } catch (error) {
            console.error('File upload error:', error);
            this.setControlStatus(`❌ Failed to upload ${file.name}`);
        }
    };
    
    VeraChat.prototype.addFileMessage = function(file, uploadData) {
        const fileExt = file.name.split('.').pop().toLowerCase();
        const isImage = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg'].includes(fileExt);
        
        let content = `📎 Uploaded: **${file.name}**\n`;
        content += `Size: ${this.formatFileSize(file.size)}\n`;
        
        if (uploadData.file_id) {
            content += `File ID: \`${uploadData.file_id}\`\n`;
        }
        
        if (isImage && uploadData.url) {
            content += `\n![${file.name}](${uploadData.url})`;
        }
        
        this.addMessage('system', content);
    };
    
    VeraChat.prototype.formatFileSize = function(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    };
    
    // =====================================================================
    // FIXED: Message Rendering with Proper Alignment
    // =====================================================================
    
    VeraChat.prototype.renderMessage = function(message) {
        const container = document.getElementById('chatMessages');
        const messageEl = document.createElement('div');
        messageEl.id = message.id;
        messageEl.className = `message ${message.role} modern-message`;
        messageEl.dataset.messageId = message.id;
        messageEl.dataset.messageContent = message.content; // For graph matching
        messageEl.dataset.graphNodeId = message.graph_node_id || `msg_${message.id}`;
        
        // Make clickable
        messageEl.onclick = (e) => {
            if (e.target.closest('button') || e.target.closest('a') || e.target.closest('.format-btn')) {
                return;
            }
            this.toggleMessageMenu(message.id);
        };
        
        // Avatar
        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.innerHTML = message.role === 'user' 
            ? '<div class="avatar-circle user-avatar">👤</div>'
            : message.role === 'assistant'
            ? '<div class="avatar-circle assistant-avatar pulse">V</div>'
            : '<div class="avatar-circle system-avatar">ℹ️</div>';
        
        // Content container
        const contentContainer = document.createElement('div');
        contentContainer.className = 'message-content-container';
        
        // Header
        const header = document.createElement('div');
        header.className = 'message-header';
        const roleName = message.role === 'user' ? 'You' : message.role === 'assistant' ? 'Vera' : 'System';
        const timestamp = this.formatTimestamp(message.timestamp);
        header.innerHTML = `
            <span class="message-role">${roleName}</span>
            <span class="message-timestamp">${timestamp}</span>
            ${message.role !== 'system' ? '<span class="click-hint">Click for options</span>' : ''}
        `;
        
        // Content
        const content = document.createElement('div');
        content.className = 'message-content';
        content.innerHTML = this.renderMessageContent(message.content);
        
        // Assemble
        contentContainer.appendChild(header);
        contentContainer.appendChild(content);
        
        if (message.role !== 'system') {
            messageEl.appendChild(avatar);
        }
        messageEl.appendChild(contentContainer);
        
        container.appendChild(messageEl);
        
        // Auto-focus canvas if enabled
        if (this.canvasAutoFocus && message.role === 'assistant') {
            this.checkAndAutoRenderCanvas(message);
        }
        
        // TTS if enabled
        if (this.ttsEnabled && message.role === 'assistant') {
            setTimeout(() => this.speakText(message.content), 500);
        }
        
        container.scrollTop = container.scrollHeight;
    };
    
    // =====================================================================
    // Content Rendering (same as before)
    // =====================================================================
    
    VeraChat.prototype.renderMessageContent = function(content) {
        if (typeof content === 'object') {
            content = JSON.stringify(content, null, 2);
        }
        
        content = String(content);
        
        const codeBlocks = [];
        const inlineCodes = [];
        const links = [];
        const images = [];
        
        // Extract images
        content = content.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (match, alt, url) => {
            const placeholder = `###IMAGE${images.length}###`;
            images.push(`
                <div class="inline-image">
                    <img src="${this.escapeHtml(url)}" alt="${this.escapeHtml(alt)}" loading="lazy">
                    ${alt ? `<div class="image-caption">${this.escapeHtml(alt)}</div>` : ''}
                </div>
            `);
            return placeholder;
        });
        
        // Extract code blocks
        content = content.replace(/```(\w+)?\n([\s\S]*?)```/g, (match, lang, code) => {
            const language = lang || 'text';
            const trimmedCode = code.trim();
            const placeholder = `###CODEBLOCK${codeBlocks.length}###`;
            const rendered = this.renderSpecialFormat(language, trimmedCode);
            codeBlocks.push(rendered);
            return placeholder;
        });
        
        // Extract inline code
        content = content.replace(/`([^`]+)`/g, (match, code) => {
            const placeholder = `###INLINECODE${inlineCodes.length}###`;
            inlineCodes.push(`<code class="inline-code">${this.escapeHtml(code)}</code>`);
            return placeholder;
        });
        
        // Extract links
        content = content.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, text, url) => {
            const placeholder = `###LINK${links.length}###`;
            links.push(`<a href="${this.escapeHtml(url)}" target="_blank" class="message-link">${this.escapeHtml(text)}</a>`);
            return placeholder;
        });
        
        // Escape HTML
        content = this.escapeHtml(content);
        
        // Markdown formatting
        content = content.replace(/^### (.+)$/gm, '<h3 class="msg-h3">$1</h3>');
        content = content.replace(/^## (.+)$/gm, '<h2 class="msg-h2">$1</h2>');
        content = content.replace(/^# (.+)$/gm, '<h1 class="msg-h1">$1</h1>');
        content = content.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
        content = content.replace(/\*([^*]+)\*/g, '<em>$1</em>');
        content = content.replace(/^[\*\-\+] (.+)$/gm, '<li class="msg-li">$1</li>');
        content = content.replace(/(<li[^>]*>.*?<\/li>\n?)+/g, '<ul class="msg-ul">$&</ul>');
        content = content.replace(/\n/g, '<br>');
        
        // Restore elements
        images.forEach((img, i) => content = content.replace(`###IMAGE${i}###`, img));
        codeBlocks.forEach((block, i) => content = content.replace(`###CODEBLOCK${i}###`, block));
        inlineCodes.forEach((code, i) => content = content.replace(`###INLINECODE${i}###`, code));
        links.forEach((link, i) => content = content.replace(`###LINK${i}###`, link));
        
        return content;
    };
    
    VeraChat.prototype.renderSpecialFormat = function(language, code) {
        language = language.toLowerCase();
        
        if (language === 'json' || this.looksLikeJSON(code)) {
            return this.renderInlineJSON(code);
        }
        
        if (language === 'csv' || language === 'tsv' || this.looksLikeCSV(code)) {
            return this.renderInlineTable(code);
        }
        
        return this.renderCodeBlock(language, code);
    };
    
    VeraChat.prototype.looksLikeJSON = function(text) {
        text = text.trim();
        return (text.startsWith('{') || text.startsWith('[')) && text.length > 10;
    };
    
    VeraChat.prototype.looksLikeCSV = function(text) {
        const lines = text.trim().split('\n');
        if (lines.length < 2) return false;
        const firstLine = lines[0];
        return (firstLine.split(',').length > 1 || firstLine.split('\t').length > 1);
    };
    
    VeraChat.prototype.renderInlineJSON = function(code) {
        try {
            const parsed = JSON.parse(code);
            const formatted = JSON.stringify(parsed, null, 2);
            
            return `
                <div class="inline-json-viewer">
                    <div class="format-toolbar">
                        <span class="format-label">JSON</span>
                        <button class="format-btn" onclick="app.toggleJSONView(this); event.stopPropagation();">Tree</button>
                        <button class="format-btn" onclick="app.copyFormatContent(this); event.stopPropagation();">Copy</button>
                    </div>
                    <div class="json-content">
                        <pre class="json-formatted"><code class="language-json">${this.escapeHtml(formatted)}</code></pre>
                        <div class="json-tree" style="display:none;">${this.createCompactJSONTree(parsed)}</div>
                    </div>
                </div>
            `;
        } catch(e) {
            return this.renderCodeBlock('json', code);
        }
    };
    
    VeraChat.prototype.renderInlineTable = function(code) {
        const lines = code.trim().split('\n');
        if (lines.length < 2) return this.renderCodeBlock('csv', code);
        
        const delimiter = lines[0].includes('\t') ? '\t' : ',';
        const headers = lines[0].split(delimiter).map(h => h.trim());
        const rows = lines.slice(1);
        
        let tableHTML = `
            <div class="inline-table-viewer">
                <div class="format-toolbar">
                    <span class="format-label">Table (${rows.length} rows)</span>
                    <button class="format-btn" onclick="app.copyFormatContent(this); event.stopPropagation();">Copy</button>
                    <button class="format-btn" onclick="app.exportTable(this, 'csv'); event.stopPropagation();">Export CSV</button>
                </div>
                <div class="table-wrapper">
                    <table class="inline-table">
                        <thead><tr>
        `;
        
        headers.forEach(h => {
            tableHTML += `<th>${this.escapeHtml(h)}</th>`;
        });
        
        tableHTML += `</tr></thead><tbody>`;
        
        rows.forEach(row => {
            const cells = row.split(delimiter).map(c => c.trim());
            tableHTML += '<tr>';
            cells.forEach(cell => {
                tableHTML += `<td>${this.escapeHtml(cell)}</td>`;
            });
            tableHTML += '</tr>';
        });
        
        tableHTML += `</tbody></table></div></div>`;
        return tableHTML;
    };
    
    VeraChat.prototype.renderCodeBlock = function(language, code) {
        const codeId = 'code_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
        return `
            <div class="enhanced-code-block" data-code-id="${codeId}">
                <div class="code-toolbar">
                    <span class="code-language">${language.toUpperCase()}</span>
                    <div class="code-actions">
                        <button class="code-action-btn" onclick="app.copyCodeBlock(this); event.stopPropagation();" title="Copy">📋</button>
                        <button class="code-action-btn" onclick="app.showCanvasModeSelector(this, '${codeId}'); event.stopPropagation();" title="Send to Canvas">🎨</button>
                    </div>
                </div>
                <pre><code class="language-${language}">${this.escapeHtml(code)}</code></pre>
            </div>
        `;
    };
    
    VeraChat.prototype.createCompactJSONTree = function(obj, level = 0) {
        let html = '';
        const indent = level * 20;
        
        if (Array.isArray(obj)) {
            html += `<div style="margin-left: ${indent}px;"><span class="json-bracket">[</span>`;
            obj.forEach((item, i) => {
                html += this.createCompactJSONTree(item, level + 1);
                if (i < obj.length - 1) html += '<span class="json-comma">,</span>';
            });
            html += `<span class="json-bracket">]</span></div>`;
        } else if (typeof obj === 'object' && obj !== null) {
            html += `<div style="margin-left: ${indent}px;"><span class="json-bracket">{</span>`;
            const entries = Object.entries(obj);
            entries.forEach(([key, value], i) => {
                html += `<div style="margin-left: ${indent + 20}px;">`;
                html += `<span class="json-key">"${this.escapeHtml(key)}"</span><span class="json-colon">:</span> `;
                if (typeof value === 'object') {
                    html += this.createCompactJSONTree(value, level + 1);
                } else {
                    html += `<span class="json-value">${JSON.stringify(value)}</span>`;
                }
                if (i < entries.length - 1) html += '<span class="json-comma">,</span>';
                html += '</div>';
            });
            html += `<span class="json-bracket">}</span></div>`;
        } else {
            html += `<span class="json-value">${JSON.stringify(obj)}</span>`;
        }
        
        return html;
    };
    
    // =====================================================================
    // Auto-Canvas Streaming
    // =====================================================================
    
    VeraChat.prototype.checkAndAutoRenderCanvas = function(message) {
        if (!this.canvasAutoFocus) return;
        
        const content = message.content;
        const codeBlockMatch = content.match(/```(\w+)?\n([\s\S]{50,}?)```/);
        if (codeBlockMatch) {
            const language = codeBlockMatch[1] || 'text';
            const code = codeBlockMatch[2];
            
            if (language === 'mermaid' || code.includes('graph TD') || code.includes('sequenceDiagram')) {
                this.autoRenderToCanvas('diagram', code, language);
                return;
            }
            
            if (language === 'html' && code.length > 100) {
                this.autoRenderToCanvas('preview', code, language);
                return;
            }
            
            if (language === 'python' && code.length > 100) {
                this.autoRenderToCanvas('jupyter', code, language);
                return;
            }
            
            if ((language === 'js' || language === 'javascript') && code.includes('React')) {
                this.autoRenderToCanvas('preview', code, language);
                return;
            }
            
            if (code.length > 200) {
                this.autoRenderToCanvas('code', code, language);
                return;
            }
        }
        
        if (this.looksLikeJSON(content) && content.length > 100) {
            try {
                JSON.parse(content);
                this.autoRenderToCanvas('json', content, 'json');
                return;
            } catch (e) {}
        }
        
        if (this.looksLikeCSV(content)) {
            this.autoRenderToCanvas('table', content, 'csv');
            return;
        }
    };
    
    VeraChat.prototype.autoRenderToCanvas = function(mode, content, language) {
        const now = Date.now();
        if (now - this.lastCanvasCheck < 2000) return;
        this.lastCanvasCheck = now;
        
        const canvasTab = this.tabs ? this.tabs.find(t => t.id === 'canvas') : null;
        if (!canvasTab) return;
        
        this.setControlStatus(`🎨 Auto-rendering in ${mode} mode...`);
        
        setTimeout(() => {
            this.activateTab('canvas', canvasTab.columnId);
            
            setTimeout(() => {
                if (typeof this.switchCanvasMode === 'function') {
                    this.switchCanvasMode(mode);
                }
                
                const modeSelector = document.querySelector('#canvasMode');
                if (modeSelector) modeSelector.value = mode;
                
                if (typeof this.loadIntoCanvas === 'function') {
                    this.loadIntoCanvas(language, content);
                }
            }, 100);
        }, 500);
    };
    
    // =====================================================================
    // FIXED: Message Menu with Proper Positioning & Tools
    // =====================================================================
    
    VeraChat.prototype.toggleMessageMenu = async function(messageId) {
        // Close any open menus
        document.querySelectorAll('.message-menu.active').forEach(menu => {
            if (menu.dataset.messageId !== messageId) {
                menu.remove();
            }
        });
        
        // Check if menu already exists
        const existing = document.querySelector(`.message-menu[data-message-id="${messageId}"]`);
        if (existing) {
            existing.classList.add('slide-out');
            setTimeout(() => existing.remove(), 200);
            return;
        }
        
        const message = this.messages.find(m => m.id === messageId);
        if (!message) return;
        
        // Ensure tools are loaded before creating menu
        await this.ensureToolsLoaded();
        
        this.createMessageMenu(messageId, message);
    };
    
    VeraChat.prototype.createMessageMenu = function(messageId, message) {
        const messageEl = document.getElementById(messageId);
        const chatMessages = document.getElementById('chatMessages');
        if (!messageEl || !chatMessages) return;
        
        const menu = document.createElement('div');
        menu.className = 'message-menu active slide-in';
        menu.dataset.messageId = messageId;
        
        const sections = [];
        
        // Canvas section
        sections.push({
            title: 'Send to Canvas',
            icon: '🎨',
            items: [
                { label: 'Auto-detect', icon: '🤖', action: () => this.sendToCanvasAuto(message) },
                { label: 'Code Editor', icon: '💻', action: () => this.sendToCanvasMode(message, 'code') },
                { label: 'Markdown', icon: '📝', action: () => this.sendToCanvasMode(message, 'markdown') },
                { label: 'Jupyter', icon: '📓', action: () => this.sendToCanvasMode(message, 'jupyter') },
                { label: 'JSON Viewer', icon: '🗂️', action: () => this.sendToCanvasMode(message, 'json') },
                { label: 'Table', icon: '📊', action: () => this.sendToCanvasMode(message, 'table') },
                { label: 'Diagram', icon: '📈', action: () => this.sendToCanvasMode(message, 'diagram') },
                { label: 'Preview', icon: '🌐', action: () => this.sendToCanvasMode(message, 'preview') },
                { label: 'Terminal', icon: '💻', action: () => this.sendToCanvasMode(message, 'terminal') }
            ]
        });
        
        // Tools section - FIXED
        if (this.availableTools && Object.keys(this.availableTools).length > 0) {
            const toolItems = Object.values(this.availableTools).slice(0, 8).map(tool => ({
                label: tool.name,
                icon: '🔧',
                action: () => this.runToolOnMessage(message, tool.name)
            }));
            
            if (Object.keys(this.availableTools).length > 8) {
                toolItems.push({
                    label: 'More tools...',
                    icon: '⋯',
                    action: () => this.showAllToolsForMessage(message)
                });
            }
            
            sections.push({
                title: 'Run Tool',
                icon: '🔧',
                items: toolItems
            });
        } else {
            // Show loading or empty state
            sections.push({
                title: 'Run Tool',
                icon: '🔧',
                items: [
                    { label: 'Loading tools...', icon: '⏳', action: () => this.ensureToolsLoaded() }
                ]
            });
        }
        
        // Actions section
        sections.push({
            title: 'Actions',
            icon: '⚡',
            items: [
                { label: 'Focus in Graph', icon: '🎯', action: () => this.focusMessageInGraph(message) },
                { label: 'Copy', icon: '📋', action: () => this.copyMessageContent(messageId) },
                { label: 'Star', icon: '⭐', action: () => this.starMessage(messageId) },
                { label: 'Delete', icon: '🗑️', action: () => this.deleteMessage(messageId), className: 'danger' }
            ]
        });
        
        let menuHTML = '<div class="message-menu-inner">';
        
        sections.forEach((section, sectionIndex) => {
            menuHTML += `
                <div class="menu-section">
                    <div class="menu-section-header">
                        <span class="menu-section-icon">${section.icon}</span>
                        <span class="menu-section-title">${section.title}</span>
                    </div>
                    <div class="menu-items">
            `;
            
            section.items.forEach((item, itemIndex) => {
                const actionKey = `${messageId}_${sectionIndex}_${itemIndex}`;
                menuHTML += `
                    <button class="menu-item ${item.className || ''}" 
                            onclick="app.executeMenuAction('${actionKey}'); event.stopPropagation();">
                        <span class="menu-item-icon">${item.icon}</span>
                        <span class="menu-item-label">${this.escapeHtml(item.label)}</span>
                    </button>
                `;
            });
            
            menuHTML += `</div></div>`;
        });
        
        menuHTML += '</div>';
        menu.innerHTML = menuHTML;
        
        if (!this.menuActions) this.menuActions = {};
        sections.forEach((section, sectionIndex) => {
            section.items.forEach((item, itemIndex) => {
                const actionKey = `${messageId}_${sectionIndex}_${itemIndex}`;
                this.menuActions[actionKey] = item.action;
            });
        });
        
        // FIXED: Append to chatMessages container, not individual message
        chatMessages.appendChild(menu);
        
        // Position relative to message
        setTimeout(() => {
            const messageRect = messageEl.getBoundingClientRect();
            const chatRect = chatMessages.getBoundingClientRect();
            
            // Position next to message
            const top = messageRect.top - chatRect.top + chatMessages.scrollTop;
            const left = messageRect.right - chatRect.left + 12;
            
            menu.style.position = 'absolute';
            menu.style.top = `${top}px`;
            menu.style.left = `${left}px`;
            menu.style.maxHeight = `${chatRect.height - 40}px`;
            
            // If menu goes off right, position on left side
            const menuRect = menu.getBoundingClientRect();
            if (menuRect.right > chatRect.right) {
                menu.style.left = 'auto';
                menu.style.right = `${chatRect.right - messageRect.left + 12}px`;
            }
        }, 0);
        
        // Close on click outside
        setTimeout(() => {
            const closeHandler = (e) => {
                if (!menu.contains(e.target) && !messageEl.contains(e.target)) {
                    menu.classList.add('slide-out');
                    setTimeout(() => menu.remove(), 200);
                    document.removeEventListener('click', closeHandler);
                }
            };
            document.addEventListener('click', closeHandler);
        }, 10);
    };
    
    VeraChat.prototype.executeMenuAction = function(actionKey) {
        const action = this.menuActions && this.menuActions[actionKey];
        if (!action) return;
        
        document.querySelectorAll('.message-menu').forEach(m => {
            m.classList.add('slide-out');
            setTimeout(() => m.remove(), 200);
        });
        action();
    };
    
    // =====================================================================
    // FIXED: Graph Focus with Better Node Matching
    // =====================================================================
    
    VeraChat.prototype.focusMessageInGraph = async function(message) {
        const graphTab = this.tabs ? this.tabs.find(t => t.id === 'graph') : null;
        if (!graphTab) {
            this.setControlStatus('❌ Graph not available');
            return;
        }
        
        this.activateTab('graph', graphTab.columnId);
        
        setTimeout(async () => {
            if (!this.networkInstance) {
                this.setControlStatus('❌ Graph not initialized');
                return;
            }
            
            // Try multiple matching strategies
            let node = null;
            
            // Strategy 1: Direct graph_node_id match
            if (message.graph_node_id) {
                node = this.networkData.nodes.find(n => n.id === message.graph_node_id);
            }
            
            // Strategy 2: Match by message ID in properties
            if (!node) {
                node = this.networkData.nodes.find(n => 
                    n.properties && n.properties.message_id === message.id
                );
            }
            
            // Strategy 3: Match by content + role
            if (!node && message.content) {
                const contentStart = message.content.substring(0, 100);
                const role = message.role === 'user' ? 'Query' : 'Response';
                
                node = this.networkData.nodes.find(n => {
                    if (!n.properties) return false;
                    
                    // Check if it's a Query or Response node
                    const isRightType = n.type === role || 
                                       n.labels === role ||
                                       (n.properties.type && n.properties.type === role);
                    
                    if (!isRightType) return false;
                    
                    // Check if content matches
                    const nodeContent = n.properties.content || n.properties.text || n.properties.query || '';
                    return nodeContent.includes(contentStart) || contentStart.includes(nodeContent.substring(0, 100));
                });
            }
            
            // Strategy 4: Query Neo4j directly
            if (!node && this.sessionId) {
                try {
                    const role = message.role === 'user' ? 'Query' : 'Response';
                    const contentStart = message.content.substring(0, 100);
                    
                    const response = await fetch(`http://llm.int:8888/api/graph/find-message`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            session_id: this.sessionId,
                            role: role,
                            content_start: contentStart
                        })
                    });
                    
                    if (response.ok) {
                        const data = await response.json();
                        if (data.node_id) {
                            node = this.networkData.nodes.find(n => n.id === data.node_id);
                        }
                    }
                } catch (error) {
                    console.log('Could not query graph for message:', error);
                }
            }
            
            if (node) {
                this.networkInstance.focus(node.id, {
                    scale: 1.5,
                    animation: {
                        duration: 1000,
                        easingFunction: 'easeInOutQuad'
                    }
                });
                
                this.networkInstance.selectNodes([node.id]);
                
                if (window.GraphAddon && window.GraphAddon.showNodeDetails) {
                    setTimeout(() => {
                        window.GraphAddon.showNodeDetails(node.id, true);
                    }, 1100);
                }
                
                this.setControlStatus('✅ Focused on message in graph');
            } else {
                this.setControlStatus('⚠️ Message not found in graph');
                console.log('Could not find graph node for message:', {
                    id: message.id,
                    role: message.role,
                    content_start: message.content.substring(0, 50)
                });
            }
        }, 200);
    };
    
    // =====================================================================
    // Canvas Integration
    // =====================================================================
    
    VeraChat.prototype.sendToCanvasAuto = function(message) {
        const detection = this.detectContentType ? this.detectContentType(message.content) : { mode: 'code', language: 'text' };
        this.sendToCanvasMode(message, detection.mode);
        this.setControlStatus(`🎨 Sent to Canvas (${detection.mode})`);
    };
    
    VeraChat.prototype.sendToCanvasMode = function(message, mode) {
        const canvasTab = this.tabs ? this.tabs.find(t => t.id === 'canvas') : null;
        if (!canvasTab) {
            this.setControlStatus('❌ Canvas not available');
            return;
        }
        
        this.activateTab('canvas', canvasTab.columnId);
        
        setTimeout(() => {
            if (typeof this.switchCanvasMode === 'function') {
                this.switchCanvasMode(mode);
            }
            const modeSelector = document.querySelector('#canvasMode');
            if (modeSelector) modeSelector.value = mode;
            
            const detection = this.detectContentType ? this.detectContentType(message.content) : { language: 'text' };
            if (typeof this.loadIntoCanvas === 'function') {
                this.loadIntoCanvas(detection.language, message.content);
            }
            
            this.setControlStatus(`✅ Loaded in ${mode} mode`);
        }, 100);
    };
    
    // =====================================================================
    // Tool Integration
    // =====================================================================
    
    VeraChat.prototype.runToolOnMessage = async function(message, toolName) {
        const tool = this.availableTools[toolName];
        if (!tool) {
            this.setControlStatus('❌ Tool not found');
            return;
        }
        
        this.setControlStatus(`🔧 Running ${toolName}...`, 0);
        
        try {
            const params = new URLSearchParams();
            params.append('tool_name', toolName);
            params.append('tool_input', message.content);
            
            const response = await fetch(
                `http://llm.int:8888/api/toolchain/${this.sessionId}/execute-tool?${params.toString()}`,
                { method: 'POST', headers: { 'Content-Type': 'application/json' } }
            );
            
            if (!response.ok) throw new Error('Tool execution failed');
            
            const data = await response.json();
            
            if (typeof this.addMessage === 'function') {
                this.addMessage('system', `**Tool: ${toolName}**\n\n${data.output}`);
            }
            this.setControlStatus('✅ Tool executed successfully');
            
        } catch (error) {
            this.setControlStatus(`❌ Tool error: ${error.message}`);
        }
    };
    
    VeraChat.prototype.showAllToolsForMessage = function(message) {
        const modal = document.createElement('div');
        modal.className = 'tool-selector-modal';
        
        let toolsHTML = '';
        if (this.availableTools) {
            const tools = Object.values(this.availableTools);
            toolsHTML = tools.map(tool => `
                <button class="tool-list-item" onclick="app.runToolOnMessage(app.messages.find(m => m.id === '${message.id}'), '${tool.name}'); this.closest('.tool-selector-modal').remove();">
                    <div class="tool-name">${this.escapeHtml(tool.name)}</div>
                    <div class="tool-description">${this.escapeHtml(tool.description)}</div>
                </button>
            `).join('');
        }
        
        modal.innerHTML = `
            <div class="modal-overlay" onclick="this.parentElement.remove()"></div>
            <div class="modal-content">
                <div class="modal-header">
                    <h3>Select Tool</h3>
                    <button class="modal-close" onclick="this.closest('.tool-selector-modal').remove()">✕</button>
                </div>
                <div class="modal-body">
                    <input type="text" id="tool-search-modal" placeholder="Search tools..." class="tool-search-input">
                    <div class="tool-list" id="tool-list-modal">${toolsHTML}</div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        const searchInput = document.getElementById('tool-search-modal');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                const query = e.target.value.toLowerCase();
                const items = modal.querySelectorAll('.tool-list-item');
                items.forEach(item => {
                    const name = item.querySelector('.tool-name').textContent.toLowerCase();
                    const desc = item.querySelector('.tool-description').textContent.toLowerCase();
                    item.style.display = (name.includes(query) || desc.includes(query)) ? '' : 'none';
                });
            });
        }
    };
    
    // =====================================================================
    // Utility Functions
    // =====================================================================
    
    VeraChat.prototype.toggleJSONView = function(button) {
        const viewer = button.closest('.inline-json-viewer');
        const formatted = viewer.querySelector('.json-formatted');
        const tree = viewer.querySelector('.json-tree');
        
        if (tree.style.display === 'none') {
            formatted.style.display = 'none';
            tree.style.display = 'block';
            button.textContent = 'Raw';
        } else {
            formatted.style.display = 'block';
            tree.style.display = 'none';
            button.textContent = 'Tree';
        }
    };
    
    VeraChat.prototype.copyFormatContent = function(button) {
        const viewer = button.closest('[class*="inline-"]');
        const pre = viewer.querySelector('pre');
        const text = pre ? pre.textContent : viewer.textContent;
        
        navigator.clipboard.writeText(text).then(() => {
            button.textContent = '✅';
            setTimeout(() => button.textContent = 'Copy', 2000);
        });
    };
    
    VeraChat.prototype.exportTable = function(button, format) {
        const viewer = button.closest('.inline-table-viewer');
        const table = viewer.querySelector('table');
        
        let csv = '';
        table.querySelectorAll('tr').forEach(row => {
            const cells = Array.from(row.querySelectorAll('th, td'));
            csv += cells.map(cell => cell.textContent).join(',') + '\n';
        });
        
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `table-${Date.now()}.csv`;
        a.click();
        URL.revokeObjectURL(url);
    };
    
    VeraChat.prototype.copyCodeBlock = function(button) {
        const block = button.closest('.enhanced-code-block');
        const code = block.querySelector('code').textContent;
        
        navigator.clipboard.writeText(code).then(() => {
            button.textContent = '✅';
            setTimeout(() => button.textContent = '📋', 2000);
        });
    };
    
    VeraChat.prototype.showCanvasModeSelector = function(button, codeId) {
        const block = button.closest('.enhanced-code-block');
        const code = block.querySelector('code').textContent;
        const language = block.querySelector('.code-language').textContent.toLowerCase();
        
        document.querySelectorAll('.canvas-mode-popup').forEach(p => p.remove());
        
        const popup = document.createElement('div');
        popup.className = 'canvas-mode-popup';
        
        button.dataset.codeContent = code;
        button.dataset.codeLanguage = language;
        
        popup.innerHTML = `
            <div class="popup-title">Send to Canvas</div>
            <button onclick="app.sendCodeToCanvas('code', this.parentElement.parentElement.querySelector('.code-action-btn[title=\\'Send to Canvas\\']')); event.stopPropagation();">💻 Code Editor</button>
            <button onclick="app.sendCodeToCanvas('preview', this.parentElement.parentElement.querySelector('.code-action-btn[title=\\'Send to Canvas\\']')); event.stopPropagation();">🌐 Preview</button>
            <button onclick="app.sendCodeToCanvas('markdown', this.parentElement.parentElement.querySelector('.code-action-btn[title=\\'Send to Canvas\\']')); event.stopPropagation();">📝 Markdown</button>
            <button onclick="app.sendCodeToCanvas('json', this.parentElement.parentElement.querySelector('.code-action-btn[title=\\'Send to Canvas\\']')); event.stopPropagation();">🗂️ JSON</button>
        `;
        
        block.appendChild(popup);
        
        setTimeout(() => {
            const closeHandler = (e) => {
                if (!popup.contains(e.target) && e.target !== button) {
                    popup.remove();
                    document.removeEventListener('click', closeHandler);
                }
            };
            document.addEventListener('click', closeHandler);
        }, 10);
    };
    
    VeraChat.prototype.sendCodeToCanvas = function(mode, button) {
        const code = button.dataset.codeContent;
        const language = button.dataset.codeLanguage;
        
        const canvasTab = this.tabs ? this.tabs.find(t => t.id === 'canvas') : null;
        if (!canvasTab) return;
        
        this.activateTab('canvas', canvasTab.columnId);
        
        setTimeout(() => {
            if (typeof this.switchCanvasMode === 'function') {
                this.switchCanvasMode(mode);
            }
            const modeSelector = document.querySelector('#canvasMode');
            if (modeSelector) modeSelector.value = mode;
            if (typeof this.loadIntoCanvas === 'function') {
                this.loadIntoCanvas(language, code);
            }
        }, 100);
        
        document.querySelectorAll('.canvas-mode-popup').forEach(p => p.remove());
    };
    
    VeraChat.prototype.formatTimestamp = function(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const diff = now - date;
        
        if (diff < 60000) return 'Just now';
        if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
        if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
        
        return date.toLocaleString();
    };
    
    VeraChat.prototype.copyMessageContent = function(messageId) {
        const message = this.messages.find(m => m.id === messageId);
        if (!message) return;
        
        navigator.clipboard.writeText(message.content).then(() => {
            this.setControlStatus('📋 Copied to clipboard');
        });
    };
    
    VeraChat.prototype.starMessage = function(messageId) {
        const messageEl = document.getElementById(messageId);
        if (!messageEl) return;
        
        messageEl.classList.toggle('starred');
        const starred = JSON.parse(localStorage.getItem('starred-messages') || '[]');
        
        if (messageEl.classList.contains('starred')) {
            if (!starred.includes(messageId)) starred.push(messageId);
            this.setControlStatus('⭐ Message starred');
        } else {
            const index = starred.indexOf(messageId);
            if (index > -1) starred.splice(index, 1);
            this.setControlStatus('Star removed');
        }
        
        localStorage.setItem('starred-messages', JSON.stringify(starred));
    };
    
    VeraChat.prototype.deleteMessage = function(messageId) {
        if (!confirm('Delete this message?')) return;
        
        const messageEl = document.getElementById(messageId);
        if (messageEl) {
            messageEl.style.opacity = '0';
            setTimeout(() => messageEl.remove(), 300);
        }
        
        this.messages = this.messages.filter(m => m.id !== messageId);
        this.setControlStatus('🗑️ Message deleted');
    };
    
    // Initialize modern features when chat loads
    const originalInit = VeraChat.prototype.init;
    VeraChat.prototype.init = async function() {
        const result = await originalInit.call(this);
        this.initModernFeatures();
        return result;
    };
    
    console.log('🚀 Modern Interactive Chat UI (FIXED) loaded successfully');
})();