// =====================================================================
// Modern Interactive Chat UI - COMPLETE FIX
// Fixes: Canvas buttons, mermaid rendering, auto-focus, full-width bubbles
// =====================================================================

(() => {

          
        VeraChat.prototype.handleWebSocketMessage = function(data) {
            this.veraRobot.setState('thinking');
            
            if (data.type === 'chunk') {
                if (!this.currentStreamingMessageId) {
                    this.currentStreamingMessageId = `msg-${Date.now()}`;
                    this.addMessage('assistant', '', this.currentStreamingMessageId);
                    
                    // Reset TTS tracking for new message
                    if (this.ttsEnabled) {
                        this.ttsSpokenLength = 0;
                    }
                }
                
                const message = this.messages.find(m => m.id === this.currentStreamingMessageId);
                if (message) {
                    message.content += data.content;
                    this.updateStreamingMessageContent(this.currentStreamingMessageId, message.content);
                    
                    // *** STREAMING TTS ***
                    if (typeof this.speakStreamingText === 'function') {
                        this.speakStreamingText(message.content);
                    }
                }
            } else if (data.type === 'complete') {
                this.veraRobot.setState('idle');
                
                if (this.currentStreamingMessageId) {
                    const message = this.messages.find(m => m.id === this.currentStreamingMessageId);
                    if (message) {
                        const messageEl = document.getElementById(this.currentStreamingMessageId);
                        
                        // Remove streaming indicator
                        if (messageEl) {
                            const indicator = messageEl.querySelector('.streaming-indicator');
                            if (indicator) indicator.remove();
                        }
                        
                        // IMPORTANT: Do final render with modern features
                        const renderedView = messageEl.querySelector('.message-rendered');
                        if (renderedView && typeof this.renderMessageContent === 'function') {
                            renderedView.innerHTML = this.renderMessageContent(message.content);
                        }
                        
                        // Apply rendering (syntax highlighting + mermaid)
                        if (typeof this.applyRendering === 'function') {
                            setTimeout(() => {
                                this.applyRendering(this.currentStreamingMessageId);
                            }, 100);
                        }
                        
                        // Auto-canvas check
                        if (this.canvasAutoFocus && typeof this.checkAndAutoRenderCanvas === 'function') {
                            setTimeout(() => {
                                this.checkAndAutoRenderCanvas(message);
                            }, 200);
                        }
                        
                        // *** FINALIZE TTS ***
                        if (typeof this.finalizeTTS === 'function') {
                            setTimeout(() => {
                                this.finalizeTTS(message.content);
                            }, 300);
                        }
                    }
                }
                
                this.currentStreamingMessageId = null;
                this.processing = false;
                
                // Re-enable input and restore focus
                const sendBtn = document.getElementById('sendBtn');
                const messageInput = document.getElementById('messageInput');
                
                if (sendBtn) sendBtn.disabled = false;
                if (messageInput) {
                    messageInput.disabled = false;
                    setTimeout(() => {
                        if (messageInput && document.activeElement !== messageInput) {
                            messageInput.focus();
                        }
                    }, 100);
                }
                
                this.loadGraph();
            } else if (data.type === 'error') {
                this.veraRobot.setState('error');
                this.addSystemMessage(`Error: ${data.error}`);
                
                if (this.currentStreamingMessageId) {
                    const messageEl = document.getElementById(this.currentStreamingMessageId);
                    if (messageEl) {
                        const indicator = messageEl.querySelector('.streaming-indicator');
                        if (indicator) indicator.remove();
                    }
                }
                
                this.currentStreamingMessageId = null;
                this.processing = false;
                
                const sendBtn = document.getElementById('sendBtn');
                const messageInput = document.getElementById('messageInput');
                if (sendBtn) sendBtn.disabled = false;
                if (messageInput) {
                    messageInput.disabled = false;
                    messageInput.focus();
                }
            }
        };

        
        // NEW METHOD: Detect code blocks in message content
        VeraChat.prototype.detectCodeBlocksInMessage = function(content) {
            const blocks = [];
            const codeBlockRegex = /```(\w+)?\n([\s\S]*?)```/g;
            let match;
            
            while ((match = codeBlockRegex.exec(content)) !== null) {
                blocks.push({
                    lang: match[1] || 'plaintext',
                    code: match[2].trim()
                });
            }
            
            return blocks;
        };
        
        VeraChat.prototype.updateStreamingMessageContent = function(messageId, content) {
            const messageEl = document.getElementById(messageId);
            if (!messageEl) return;
            
            // Use the message-content div, NOT the inner rendered div
            const contentContainer = messageEl.querySelector('.message-content');
            if (!contentContainer) return;
            
            // Check if we have modern UI structure (with message-rendered div)
            let renderedView = contentContainer.querySelector('.message-rendered');
            
            if (renderedView) {
                // MODERN UI: Update the rendered view
                if (typeof this.renderMessageContent === 'function') {
                    // Use modern renderMessageContent (has mermaid, advanced features)
                    renderedView.innerHTML = this.renderMessageContent(content);
                } else {
                    // Fallback to basic if modern not loaded yet
                    renderedView.innerHTML = this.parseMessageContent(content);
                }
            } else {
                // BASIC UI: Just update the content directly
                if (typeof this.renderMessageContent === 'function') {
                    contentContainer.innerHTML = this.renderMessageContent(content);
                } else {
                    const updatedContent = content.replace(/^(\w+)/, '**Agent: $1**');
                    contentContainer.innerHTML = this.parseMessageContent(updatedContent);
                }
            }
            
            // Add/update streaming indicator
            let indicator = contentContainer.querySelector('.streaming-indicator');
            if (!indicator) {
                indicator = document.createElement('div');
                indicator.className = 'streaming-indicator';
                indicator.style.cssText = 'color: #60a5fa; font-size: 12px; margin-top: 8px; padding: 4px 8px; background: rgba(59, 130, 246, 0.1); border-radius: 4px; display: inline-block;';
                indicator.textContent = '● Streaming...';
                contentContainer.appendChild(indicator);
            }
            
            // Auto-scroll if near bottom
            const container = document.getElementById('chatMessages');
            if (container) {
                const isScrolledToBottom = container.scrollHeight - container.clientHeight <= container.scrollTop + 50;
                if (isScrolledToBottom) {
                    container.scrollTop = container.scrollHeight;
                }
            }
        };

        
        VeraChat.prototype.sendMessageViaWebSocket = async function(message) {
            this.veraRobot.setState('thinking');
            if (!this.websocket || this.websocket.readyState !== WebSocket.OPEN) {
                return false;
            }
            
            try {
                this.websocket.send(JSON.stringify({
                    message: message,
                    files: Object.keys(this.files)
                }));
                return true;
            } catch (error) {
                console.error('WebSocket send error:', error);
                return false;
            }
        }
        
        VeraChat.prototype.sendMessage = async function() {
            const input = document.getElementById('messageInput');
            const message = input.value.trim();
            
            if (!message || this.processing) return;
            
            this.processing = true;
            document.getElementById('sendBtn').disabled = true;
            input.disabled = true;
            
            this.addMessage('user', message);
            input.value = '';
            input.style.height = 'auto';
            
            if (this.useWebSocket) {
                const sent = await this.sendMessageViaWebSocket(message);
                if (sent) return;
            }
            
            try {
                const response = await fetch('http://llm.int:8888/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        session_id: this.sessionId,
                        message: message,
                        files: Object.keys(this.files)
                    })
                });
                
                const data = await response.json();
                const responseText = typeof data.response === 'string' ? data.response : JSON.stringify(data.response);
                
                this.addMessage('assistant', responseText);
                await this.loadGraph();
            } catch (error) {
                console.error('Send error:', error);
                this.addSystemMessage(`Error: ${error.message}`);
            }
            
            this.processing = false;
            document.getElementById('sendBtn').disabled = false;
            input.disabled = false;
            input.focus();
        }
        
        VeraChat.prototype.addMessage = function(role, content, id = null) {
            const messageId = id || `msg-${Date.now()}`;
            const message = { id: messageId, role, content, timestamp: new Date() };
            this.messages.push(message);
            this.renderMessage(message);
        }

        VeraChat.prototype.escapeHtml = function(unsafe) {
            if (unsafe === null || unsafe === undefined) return '';
            if (typeof unsafe !== 'string') {
                console.warn('escapeHtml expected string, got:', unsafe, typeof unsafe);
                try {
                    unsafe = JSON.stringify(unsafe);
                } catch {
                    unsafe = String(unsafe);
                }
            }

            // Now guaranteed to be string
            return unsafe
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#039;");
        }

        
        VeraChat.prototype.parseMessageContent = function(content) {
            if (typeof content === 'object' && content !== null) {
                if (Array.isArray(content)) {
                    content = content.filter(item => typeof item === 'string').join('\n');
                } else {
                    content = content.deep || content.fast || Object.values(content).filter(value => typeof value === 'string').join('\n');
                }
            }
            
            content = String(content).replace(/\\n/g, '\n').replace(/\\'/g, "'").replace(/\\"/g, '"');
            
            const codeBlocks = [];
            const inlineCodes = [];
            const links = [];
            
            content = content.replace(/```(\w+)?\n([\s\S]*?)```/g, (match, lang, code) => {
                const language = lang || 'code';
                const escapedCode = this.escapeHtml(code.trim());
                const placeholder = `###CODEBLOCK${codeBlocks.length}###`;
                codeBlocks.push(`<div style="position: relative; background: #0f172a; border-radius: 4px; padding: 10px; margin: 8px 0;"><div style="display: flex; justify-content: space-between; margin-bottom: 6px;"><div style="color: #94a3b8; font-size: 11px; text-transform: uppercase;">${language}</div><button onclick="app.copyCode(this)" style="background: #334155; border: none; color: #cbd5e1; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 11px;">Copy</button></div><pre style="margin: 0; color: #e2e8f0; font-family: monospace; font-size: 12px; white-space: pre-wrap;">${escapedCode}</pre></div>`);
                return placeholder;
            });
            
            content = content.replace(/`([^`]+)`/g, (match, code) => {
                const placeholder = `###INLINECODE${inlineCodes.length}###`;
                inlineCodes.push(`<code style="background: #0f172a; padding: 2px 6px; border-radius: 3px; color: #a78bfa; font-family: monospace; font-size: 12px;">${this.escapeHtml(code)}</code>`);
                return placeholder;
            });
            
            content = content.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, text, url) => {
                const placeholder = `###LINK${links.length}###`;
                links.push(`<a href="${this.escapeHtml(url)}" target="_blank" style="color: #3b82f6; text-decoration: underline;">${this.escapeHtml(text)}</a>`);
                return placeholder;
            });
            
            content = content.replace(/https?:\/\/[^\s<]+[^<.,:;"')\]\s]/g, (url) => {
                const placeholder = `###LINK${links.length}###`;
                links.push(`<a href="${url}" target="_blank" style="color: #3b82f6; text-decoration: underline;">${url}</a>`);
                return placeholder;
            });
            
            content = this.escapeHtml(content);
            
            content = content.replace(/^### (.+)$/gm, '<h3 style="font-size: 16px; font-weight: 600; margin: 12px 0 8px 0;">$1</h3>');
            content = content.replace(/^## (.+)$/gm, '<h2 style="font-size: 18px; font-weight: 600; margin: 14px 0 10px 0;">$1</h2>');
            content = content.replace(/^# (.+)$/gm, '<h1 style="font-size: 20px; font-weight: 600; margin: 16px 0 12px 0;">$1</h1>');
            content = content.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
            content = content.replace(/__(?!#)([^_]+)__/g, '<strong>$1</strong>');
            content = content.replace(/(?<!\*)(\*)(?!\*)([^*]+)(?<!\*)(\*)(?!\*)/g, '<em>$2</em>');
            content = content.replace(/^[\*\-\+] (.+)$/gm, '<li style="margin-left: 20px;">$1</li>');
            content = content.replace(/^(\d+)\. (.+)$/gm, '<li style="margin-left: 20px; list-style-type: decimal;">$2</li>');
            content = content.replace(/(<li[^>]*>.*?<\/li>\n?)+/g, (match) => {
                return match.includes('decimal') ? '<ol style="margin: 8px 0;">' + match + '</ol>' : '<ul style="margin: 8px 0;">' + match + '</ul>';
            });
            content = content.replace(/^&gt; (.+)$/gm, '<blockquote style="border-left: 3px solid #60a5fa; padding-left: 12px; margin: 8px 0; color: #94a3b8; font-style: italic;">$1</blockquote>');
            content = content.replace(/^---$/gm, '<hr style="border: none; border-top: 1px solid #334155; margin: 12px 0;">');
            content = content.replace(/\n/g, '<br>');
            
            codeBlocks.forEach((block, i) => content = content.replace(`###CODEBLOCK${i}###`, block));
            inlineCodes.forEach((code, i) => content = content.replace(`###INLINECODE${i}###`, code));
            links.forEach((link, i) => content = content.replace(`###LINK${i}###`, link));
            
            return content;
        }
        
        VeraChat.prototype.copyCode = function(button) {
            const codeBlock = button.closest('div').querySelector('pre');
            const code = codeBlock.textContent;
            navigator.clipboard.writeText(code).then(() => {
                const originalText = button.textContent;
                button.textContent = 'Copied!';
                setTimeout(() => button.textContent = originalText, 2000);
            });
        }
        
        VeraChat.prototype.copyMessage = function(button) {
            const messageContent = button.closest('.message').querySelector('.message-content');
            const text = messageContent.innerText;
            navigator.clipboard.writeText(text).then(() => {
                const originalText = button.textContent;
                button.textContent = '✓';
                setTimeout(() => button.textContent = originalText, 2000);
            });
        }
        
        VeraChat.prototype.renderMessage = function(message) {
            const container = document.getElementById('chatMessages');
            const messageEl = document.createElement('div');
            messageEl.id = message.id;
            messageEl.className = `message ${message.role}`;
            
            const avatar = document.createElement('div');
            avatar.className = 'message-avatar';
            avatar.textContent = message.role === 'user' ? 'You' : message.role === 'system' ? 'ℹ️' : 'V';
            
            const content = document.createElement('div');
            content.className = 'message-content';
            content.innerHTML = this.parseMessageContent(message.content);
            
            if (message.role !== 'system') {
                const saveBtn = document.createElement('button');
                saveBtn.className = 'message-copy-btn';
                saveBtn.textContent = '📓';
                saveBtn.title = 'Save to notebook';
                saveBtn.style.right = '40px'; // Position next to copy button
                saveBtn.onclick = (e) => {
                    e.stopPropagation();
                    this.captureMessageAsNote(message.id);
                };
                content.appendChild(saveBtn);
            }
            
            if (message.role !== 'system') {
                messageEl.appendChild(avatar);
            }
            messageEl.appendChild(content);
            
            container.appendChild(messageEl);
            
            // Detect and attach canvas buttons for code blocks
            const codeBlocks = this.detectCodeBlocksInMessage(message.content);
            if (codeBlocks.length > 0) {
                const block = codeBlocks[0]; // Use first code block
                this.attachCanvasButtonsToMessage(messageEl, block.lang, block.code, message.id);
            }
            
            container.scrollTop = container.scrollHeight;
        }
        
        VeraChat.prototype.addSystemMessage = function(content) {
            this.addMessage('system', content);
        }
        
        VeraChat.prototype.clearChat = function() {
            if (confirm('Clear all messages?')) {
                this.messages = [];
                document.getElementById('chatMessages').innerHTML = '';
                this.addSystemMessage('Chat cleared');
            }
        }
        
        VeraChat.prototype.exportChat = function() {
            const data = {
                session_id: this.sessionId,
                messages: this.messages,
                export_time: new Date().toISOString()
            };
            
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `vera_chat_${Date.now()}.json`;
            a.click();
            URL.revokeObjectURL(url);
        }
        
    // =====================================================================
    // Initialize Modern Features - INTEGRATED
    // =====================================================================
    
    VeraChat.prototype.initModernFeatures = function() {
        console.log('🎨 Initializing Modern Features...');
        
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
        
        // Add control bar
        setTimeout(() => {
            this.addControlBar();
        }, 100);
        
        // Start timestamp updater
        this.startTimestampUpdater();
    };
    
    VeraChat.prototype.ensureToolsLoaded = async function() {
        if (this.availableTools && Object.keys(this.availableTools).length > 0) {
            return;
        }
        
        if (this.sessionId && typeof this.loadAvailableTools === 'function') {
            await this.loadAvailableTools();
        }
    };
    
    // =====================================================================
    // Timestamp Updater - NEW
    // =====================================================================
    
    VeraChat.prototype.startTimestampUpdater = function() {
        // Update timestamps every minute
        setInterval(() => {
            document.querySelectorAll('.message-timestamp').forEach(el => {
                const messageId = el.closest('.message')?.id;
                if (messageId) {
                    const message = this.messages.find(m => m.id === messageId);
                    if (message && message.timestamp) {
                        el.textContent = this.formatTimestamp(message.timestamp);
                    }
                }
            });
        }, 60000); // Update every minute
    };
    
    // =====================================================================
    // Control Bar - ENHANCED WITH NEW BUTTONS
    // =====================================================================
    
    VeraChat.prototype.addControlBar = function() {
        console.log('🔧 Adding control bar...');
        
        let chatContainer = document.getElementById('tab-chat');
        if (!chatContainer) {
            console.error('❌ tab-chat container not found!');
            return;
        }
        
        // Create sleek control bar
        const controlBar = document.createElement('div');
        controlBar.id = 'chat-control-bar';
        controlBar.className = 'chat-control-bar-sleek';
        controlBar.innerHTML = `
            <div class="control-group-sleek">
                <button class="ctrl-btn ${this.canvasAutoFocus ? 'active' : ''}" 
                        id="toggle-canvas-focus"
                        onclick="app.toggleCanvasFocus()"
                        title="Auto-focus canvas">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="3" y="3" width="18" height="18" rx="2"/>
                        <circle cx="12" cy="12" r="3"/>
                    </svg>
                </button>
                
                <button class="ctrl-btn ${this.ttsEnabled ? 'active' : ''}" 
                        id="toggle-tts"
                        onclick="app.toggleTTS()"
                        title="Text-to-speech">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M11 5L6 9H2v6h4l5 4V5z"/>
                        <path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/>
                    </svg>
                </button>
                
                ${this.recognition ? `
                <button class="ctrl-btn ${this.sttActive ? 'active recording' : ''}" 
                        id="toggle-stt"
                        onclick="app.toggleSTT()"
                        title="Voice input">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
                        <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
                        <line x1="12" y1="19" x2="12" y2="23"/>
                        <line x1="8" y1="23" x2="16" y2="23"/>
                    </svg>
                </button>
                ` : ''}
                
                <button class="ctrl-btn" 
                        onclick="app.openFileUpload()"
                        title="Upload file">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/>
                    </svg>
                </button>
                
                <div class="ctrl-divider"></div>
                
                <button class="ctrl-btn" 
                        onclick="app.openChatSettings()"
                        title="Chat settings">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="3"/>
                        <path d="M12 1v6m0 6v6M4.22 4.22l4.24 4.24m5.08 5.08l4.24 4.24M1 12h6m6 0h6M4.22 19.78l4.24-4.24m5.08-5.08l4.24-4.24"/>
                    </svg>
                </button>
                
                <button class="ctrl-btn" 
                        onclick="app.openChatHistory()"
                        title="Chat history">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/>
                        <path d="M3 3v5h5"/>
                        <path d="M12 7v5l4 2"/>
                    </svg>
                </button>
                
                <button class="ctrl-btn" 
                        onclick="app.clearChat()"
                        title="Clear chat">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M3 6h18"/>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>
                        <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                    </svg>
                </button>
                
                <button class="ctrl-btn" 
                        onclick="app.exportChat()"
                        title="Export chat">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                        <polyline points="7 10 12 15 17 10"/>
                        <line x1="12" y1="15" x2="12" y2="3"/>
                    </svg>
                </button>
            </div>
            
            <div class="control-search-wrapper">
                <svg class="search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="11" cy="11" r="8"/>
                    <path d="m21 21-4.35-4.35"/>
                </svg>
                <input type="text" 
                       id="chat-search-input" 
                       class="chat-search-input" 
                       placeholder="Search chat..."
                       oninput="app.searchChat(this.value)">
                <button class="search-clear-btn" 
                        onclick="app.clearSearch()"
                        style="display: none;">
                    ✕
                </button>
            </div>
            
            <div class="control-status-sleek" id="control-status"></div>
        `;
        
        // Insert at the top of chat container
        const messages = chatContainer.querySelector('#chatMessages');
        if (messages) {
            chatContainer.insertBefore(controlBar, messages);
            messages.style.flex = '1';
            messages.style.overflowY = 'auto';
        } else {
            chatContainer.insertBefore(controlBar, chatContainer.firstChild);
        }
        
        console.log('✅ Sleek control bar added');
    };

    // Update the updateControlBar method to work with new structure
    VeraChat.prototype.updateControlBar = function() {
        const canvasBtn = document.getElementById('toggle-canvas-focus');
        const ttsBtn = document.getElementById('toggle-tts');
        const sttBtn = document.getElementById('toggle-stt');
        
        if (canvasBtn) {
            canvasBtn.className = `ctrl-btn ${this.canvasAutoFocus ? 'active' : ''}`;
        }
        
        if (ttsBtn) {
            ttsBtn.className = `ctrl-btn ${this.ttsEnabled ? 'active' : ''}`;
        }
        
        if (sttBtn) {
            sttBtn.className = `ctrl-btn ${this.sttActive ? 'active recording' : ''}`;
        }
    };

    // ============================================================================
    // NEW: Chat Search
    // ============================================================================
    
    VeraChat.prototype.searchChat = function(query) {
        const clearBtn = document.querySelector('.search-clear-btn');
        if (clearBtn) {
            clearBtn.style.display = query ? 'block' : 'none';
        }
        
        if (!query) {
            // Clear highlights
            document.querySelectorAll('.message.search-hidden').forEach(el => {
                el.classList.remove('search-hidden');
            });
            document.querySelectorAll('.search-highlight').forEach(el => {
                const text = el.textContent;
                el.replaceWith(document.createTextNode(text));
            });
            return;
        }
        
        const lowerQuery = query.toLowerCase();
        
        document.querySelectorAll('.message').forEach(messageEl => {
            const message = this.messages.find(m => m.id === messageEl.id);
            if (!message) return;
            
            const content = message.content.toLowerCase();
            if (content.includes(lowerQuery)) {
                messageEl.classList.remove('search-hidden');
                // Highlight matches
                this.highlightText(messageEl, query);
            } else {
                messageEl.classList.add('search-hidden');
            }
        });
    };
    
    VeraChat.prototype.highlightText = function(element, query) {
        const walker = document.createTreeWalker(
            element,
            NodeFilter.SHOW_TEXT,
            null,
            false
        );
        
        const textNodes = [];
        while (walker.nextNode()) {
            textNodes.push(walker.currentNode);
        }
        
        const regex = new RegExp(`(${query})`, 'gi');
        
        textNodes.forEach(node => {
            const text = node.textContent;
            if (regex.test(text)) {
                const span = document.createElement('span');
                span.innerHTML = text.replace(regex, '<span class="search-highlight">$1</span>');
                node.replaceWith(...span.childNodes);
            }
        });
    };
    
    VeraChat.prototype.clearSearch = function() {
        const input = document.getElementById('chat-search-input');
        if (input) {
            input.value = '';
            this.searchChat('');
        }
    };
    
    // ============================================================================
    // NEW: Placeholder functions for settings and history
    // ============================================================================
    
    VeraChat.prototype.openChatSettings = function() {
        this.setControlStatus('⚙️ Chat settings (coming soon)');
        console.log('Chat settings clicked - to be implemented');
    };
    
    VeraChat.prototype.openChatHistory = function() {
        this.setControlStatus('📜 Chat history (coming soon)');
        console.log('Chat history clicked - to be implemented');
    };

    // ============================================================================
    // CSS - Add this or replace existing control bar styles
    // ============================================================================

    const sleekControlBarStyles = `
    /* Sleek Control Bar */
    .chat-control-bar-sleek {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 6px 12px;
        background: var(--panel-bg, #1e293b);
        border-bottom: 1px solid var(--border, #334155);
        min-height: 32px;
        flex-shrink: 0;
        gap: 12px;
    }

    .control-group-sleek {
        display: flex;
        align-items: center;
        gap: 4px;
    }

    .ctrl-btn {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 28px;
        height: 28px;
        padding: 0;
        background: transparent;
        border: 1px solid transparent;
        border-radius: 4px;
        color: var(--text-muted, #94a3b8);
        cursor: pointer;
        transition: all 0.15s ease;
    }

    .ctrl-btn:hover {
        background: var(--bg, #0f172a);
        border-color: var(--border, #334155);
        color: var(--text, #e2e8f0);
    }

    .ctrl-btn.active {
        background: var(--accent, #3b82f6);
        border-color: var(--accent, #3b82f6);
        color: white;
    }

    .ctrl-btn.active:hover {
        background: var(--accent-hover, #2563eb);
        border-color: var(--accent-hover, #2563eb);
    }

    .ctrl-btn.recording {
        animation: pulse-recording 1.5s ease-in-out infinite;
    }

    .ctrl-btn svg {
        flex-shrink: 0;
    }

    .ctrl-divider {
        width: 1px;
        height: 16px;
        background: var(--border, #334155);
        margin: 0 4px;
    }

    .control-search-wrapper {
        position: relative;
        display: flex;
        align-items: center;
        flex: 1;
        max-width: 300px;
    }

    .search-icon {
        position: absolute;
        left: 10px;
        color: var(--text-muted, #94a3b8);
        pointer-events: none;
    }

    .chat-search-input {
        flex: 1;
        padding: 6px 30px 6px 32px;
        background: var(--bg, #0f172a);
        border: 1px solid var(--border, #334155);
        border-radius: 4px;
        color: var(--text, #e2e8f0);
        font-size: 12px;
        outline: none;
        transition: all 0.2s ease;
    }

    .chat-search-input:focus {
        border-color: var(--accent, #3b82f6);
        box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.1);
    }

    .search-clear-btn {
        position: absolute;
        right: 8px;
        background: transparent;
        border: none;
        color: var(--text-muted, #94a3b8);
        cursor: pointer;
        padding: 2px 4px;
        border-radius: 2px;
        font-size: 14px;
        transition: all 0.15s ease;
    }

    .search-clear-btn:hover {
        color: var(--text, #e2e8f0);
        background: var(--border, #334155);
    }

    .control-status-sleek {
        font-size: 11px;
        color: var(--text-muted, #94a3b8);
        opacity: 0;
        transition: opacity 0.2s ease;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        max-width: 200px;
    }

    @keyframes pulse-recording {
        0%, 100% { 
            box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4);
        }
        50% { 
            box-shadow: 0 0 0 4px rgba(239, 68, 68, 0);
            background: #ef4444;
        }
    }

    /* Search Highlighting */
    .message.search-hidden {
        display: none !important;
    }

    .search-highlight {
        background: var(--warning, #fbbf24);
        color: var(--bg, #0f172a);
        padding: 2px 4px;
        border-radius: 2px;
        font-weight: 600;
    }

    /* Override old control bar styles if present */
    .chat-control-bar {
        display: none !important;
    }
    `;

    // Inject styles
    if (!document.getElementById('sleek-control-bar-styles')) {
        const style = document.createElement('style');
        style.id = 'sleek-control-bar-styles';
        style.textContent = sleekControlBarStyles;
        document.head.appendChild(style);
    }
    
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
    
    // =====================================================================
    // Control Functions
    // =====================================================================
    
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
    // NEW METHOD: Speak text as it streams in
    VeraChat.prototype.speakStreamingText = function(fullText) {
        if (!this.ttsEnabled || !('speechSynthesis' in window)) return;
        
        // Initialize tracking on first call
        if (!this.ttsSpokenLength) this.ttsSpokenLength = 0;
        
        // Get only the NEW text since last spoken
        const newText = fullText.substring(this.ttsSpokenLength);
        
        if (newText.length < 40) {
            // Wait for more text to accumulate
            return;
        }
        
        // Find the last complete sentence in the new text
        const sentenceEnd = Math.max(
            newText.lastIndexOf('. '),
            newText.lastIndexOf('! '),
            newText.lastIndexOf('? '),
            newText.lastIndexOf('\n\n')
        );
        
        if (sentenceEnd === -1) {
            // No complete sentence yet, wait for more
            return;
        }
        
        // Speak up to the end of the last complete sentence
        const textToSpeak = newText.substring(0, sentenceEnd + 1);
        
        // Clean the text (remove markdown/code)
        let cleanText = textToSpeak
            .replace(/```[\s\S]*?```/g, ' code block ')
            .replace(/`([^`]+)`/g, '$1')
            .replace(/\*\*([^*]+)\*\*/g, '$1')
            .replace(/\*([^*]+)\*/g, '$1')
            .replace(/#{1,6}\s/g, '')
            .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
            .replace(/<[^>]+>/g, '')
            .trim();
        
        if (cleanText.length === 0) {
            this.ttsSpokenLength += textToSpeak.length;
            return;
        }
        
        // Update tracking BEFORE speaking
        this.ttsSpokenLength += textToSpeak.length;
        
        // Speak it
        const utterance = new SpeechSynthesisUtterance(cleanText);
        utterance.voice = this.ttsVoice;
        utterance.rate = 1.1; // Slightly faster for streaming
        utterance.pitch = 1.0;
        utterance.volume = 1.0;
        
        console.log('🔊 Speaking chunk:', cleanText.substring(0, 50) + '...');
        speechSynthesis.speak(utterance);
    };

    // NEW METHOD: Speak remaining text when streaming completes
    VeraChat.prototype.finalizeTTS = function(fullText) {
        if (!this.ttsEnabled || !('speechSynthesis' in window)) return;
        if (!this.ttsSpokenLength) this.ttsSpokenLength = 0;
        
        // Speak any remaining text
        const remainingText = fullText.substring(this.ttsSpokenLength);
        
        if (remainingText.trim().length > 0) {
            let cleanText = remainingText
                .replace(/```[\s\S]*?```/g, ' code block ')
                .replace(/`([^`]+)`/g, '$1')
                .replace(/\*\*([^*]+)\*\*/g, '$1')
                .replace(/\*([^*]+)\*/g, '$1')
                .replace(/#{1,6}\s/g, '')
                .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
                .replace(/<[^>]+>/g, '')
                .trim();
            
            if (cleanText.length > 0) {
                const utterance = new SpeechSynthesisUtterance(cleanText);
                utterance.voice = this.ttsVoice;
                utterance.rate = 1.0;
                utterance.pitch = 1.0;
                utterance.volume = 1.0;
                
                console.log('🔊 Finalizing TTS:', cleanText.substring(0, 50) + '...');
                speechSynthesis.speak(utterance);
            }
        }
        
        // Reset for next message
        this.ttsSpokenLength = 0;
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
    // Message Rendering - INTEGRATED WITH SOURCE VIEW
    // =====================================================================
    
    VeraChat.prototype.renderMessage = function(message) {
        const container = document.getElementById('chatMessages');
        const messageEl = document.createElement('div');
        messageEl.id = message.id;
        messageEl.className = `message ${message.role} modern-message`;
        messageEl.dataset.messageId = message.id;
        messageEl.dataset.messageContent = message.content;
        messageEl.dataset.graphNodeId = message.graph_node_id || `msg_${message.id}`;
        messageEl.dataset.showingSource = 'false';
        
        // Detect if message has wide content (code blocks, JSON, tables, diagrams)
        const hasWideContent = this.hasWideContent(message.content);
        if (hasWideContent) {
            messageEl.classList.add('message-wide');
        }
        
        // Make clickable ONLY for non-system messages
        if (message.role !== 'system') {
            messageEl.onclick = (e) => {
                if (e.target.closest('button') || e.target.closest('a') || e.target.closest('.format-btn')) {
                    return;
                }
                this.toggleMessageMenu(message.id);
            };
        }
        
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
        
        // Add source toggle button if content has renderable elements
        const hasRenderableContent = this.hasRenderableContent(message.content);
        const sourceToggle = hasRenderableContent ? 
            `<button class="source-toggle-btn" onclick="app.toggleSource('${message.id}'); event.stopPropagation();" title="Toggle source view">
                <span class="source-icon">📝</span>
            </button>` : '';
        
        header.innerHTML = `
            <span class="message-role">${roleName}</span>
            <span class="message-timestamp">${timestamp}</span>
            ${sourceToggle}
            ${message.role !== 'system' ? '<span class="click-hint">Click for options</span>' : ''}
        `;
        
        // Content
        const content = document.createElement('div');
        content.className = 'message-content';
        
        // Rendered view
        const renderedView = document.createElement('div');
        renderedView.className = 'message-rendered';
        renderedView.innerHTML = this.renderMessageContent(message.content);
        
        // Source view
        const sourceView = document.createElement('pre');
        sourceView.className = 'message-source';
        sourceView.style.display = 'none';
        sourceView.textContent = message.content;
        
        content.appendChild(renderedView);
        content.appendChild(sourceView);
        
        // Assemble
        contentContainer.appendChild(header);
        contentContainer.appendChild(content);
        
        if (message.role !== 'system') {
            messageEl.appendChild(avatar);
        }
        messageEl.appendChild(contentContainer);
        
        container.appendChild(messageEl);
        
        // Apply syntax highlighting and mermaid rendering
        setTimeout(() => {
            this.applyRendering(message.id);
        }, 100);
        
        // Auto-focus canvas if enabled
        if (this.canvasAutoFocus && message.role === 'assistant') {
            setTimeout(() => {
                this.checkAndAutoRenderCanvas(message);
            }, 300);
        }
        
        container.scrollTop = container.scrollHeight;
    };
    
    // NEW: Detect if content has elements that need full width
    VeraChat.prototype.hasWideContent = function(content) {
        return content.includes('```') || 
               content.includes('graph ') ||
               content.includes('sequenceDiagram') ||
               content.includes('classDiagram') ||
               content.includes('flowchart') ||
               (content.startsWith('{') && content.includes('"')) ||
               (content.startsWith('[') && content.includes('"'));
    };
    
    VeraChat.prototype.updateStreamingMessageContent = function(messageId, content) {
        const messageEl = document.getElementById(messageId);
        if (!messageEl) return;

        // Find the rendered view (modern UI structure)
        const renderedView = messageEl.querySelector('.message-rendered');

        if (renderedView) {
            // Use modern rendering with all features
            renderedView.innerHTML = this.renderMessageContent(content);
            
            // Apply syntax highlighting to any new code blocks
            if (window.hljs) {
                renderedView.querySelectorAll('pre code:not(.hljs)').forEach((block) => {
                    window.hljs.highlightElement(block);
                });
            }
        } else {
            // Fallback: update content container directly
            const contentContainer = messageEl.querySelector('.message-content');
            if (contentContainer) {
                contentContainer.innerHTML = this.renderMessageContent(content);
            }
        }

        // Add/update streaming indicator
        const contentContainer = messageEl.querySelector('.message-content');
        if (contentContainer) {
            let indicator = contentContainer.querySelector('.streaming-indicator');
            if (!indicator) {
                indicator = document.createElement('div');
                indicator.className = 'streaming-indicator';
                indicator.style.cssText = `
                    color: var(--accent);
                    font-size: 12px;
                    margin-top: 8px;
                    padding: 4px 8px;
                    background: rgba(var(--accent-rgb), 0.1);
                    border-radius: 4px;
                    display: inline-block;
                    animation: pulse 1.5s ease-in-out infinite;
                `;
                indicator.innerHTML = '<span style="display: inline-block; width: 8px; height: 8px; background: var(--accent); border-radius: 50%; margin-right: 6px;"></span>Streaming...';
                contentContainer.appendChild(indicator);
            }
        }

        // Auto-scroll if near bottom
        const container = document.getElementById('chatMessages');
        if (container) {
            const isScrolledToBottom = container.scrollHeight - container.clientHeight <= container.scrollTop + 50;
            if (isScrolledToBottom) {
                container.scrollTop = container.scrollHeight;
            }
        }
        };

        // Add pulse animation for streaming indicator
        if (!document.getElementById('streaming-indicator-styles')) {
        const style = document.createElement('style');
        style.id = 'streaming-indicator-styles';
        style.textContent = `
            @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.5; }
            }
        `;
        document.head.appendChild(style);
        }
    VeraChat.prototype.hasRenderableContent = function(content) {
        return content.includes('```') || 
               content.includes('# ') || 
               content.includes('## ') ||
               content.includes('**') ||
               content.includes('*') ||
               content.includes('[') ||
               content.includes('![');
    };
    
    VeraChat.prototype.toggleSource = function(messageId) {
        const messageEl = document.getElementById(messageId);
        if (!messageEl) return;
        
        const showingSource = messageEl.dataset.showingSource === 'true';
        const renderedView = messageEl.querySelector('.message-rendered');
        const sourceView = messageEl.querySelector('.message-source');
        const toggleBtn = messageEl.querySelector('.source-toggle-btn');
        
        if (showingSource) {
            // Show rendered
            renderedView.style.display = 'block';
            sourceView.style.display = 'none';
            messageEl.dataset.showingSource = 'false';
            if (toggleBtn) toggleBtn.querySelector('.source-icon').textContent = '📝';
        } else {
            // Show source
            renderedView.style.display = 'none';
            sourceView.style.display = 'block';
            messageEl.dataset.showingSource = 'true';
            if (toggleBtn) toggleBtn.querySelector('.source-icon').textContent = '🎨';
        }
    };
    
    
    VeraChat.prototype.applyRendering = function(messageId) {
        const messageEl = document.getElementById(messageId);
        if (!messageEl) return;
        
        // Apply syntax highlighting
        if (window.hljs) {
            messageEl.querySelectorAll('pre code:not(.hljs)').forEach((block) => {
                window.hljs.highlightElement(block);
            });
        }
        
        // Render mermaid diagrams
        if (window.mermaid) {
            messageEl.querySelectorAll('.mermaid-diagram').forEach((block, index) => {
                // Skip if already rendered
                if (block.querySelector('svg') || block.querySelector('.mermaid-wrapper')) return;
                
                const id = `mermaid-${messageId}-${index}`;
                const mermaidCode = block.textContent.trim();
                
                console.log('🎨 Rendering Mermaid:', mermaidCode.substring(0, 50));
                
                try {
                    // Use the async render API
                    window.mermaid.render(id + '-svg', mermaidCode).then(result => {
                        // Store original code
                        block.dataset.mermaidSource = mermaidCode;
                        block.dataset.showing = 'rendered';
                        
                        // Create wrapper with toggle button
                        const wrapper = document.createElement('div');
                        wrapper.className = 'mermaid-wrapper';
                        
                        const toggleBtn = document.createElement('button');
                        toggleBtn.className = 'mermaid-toggle-btn';
                        toggleBtn.innerHTML = '📝';
                        toggleBtn.title = 'Toggle source';
                        toggleBtn.onclick = (e) => {
                            e.stopPropagation();
                            this.toggleMermaid(block);
                        };
                        
                        const svgContainer = document.createElement('div');
                        svgContainer.className = 'mermaid-rendered';
                        svgContainer.innerHTML = result.svg;
                        
                        const sourceContainer = document.createElement('pre');
                        sourceContainer.className = 'mermaid-source';
                        sourceContainer.style.display = 'none';
                        sourceContainer.textContent = mermaidCode;
                        
                        wrapper.appendChild(toggleBtn);
                        wrapper.appendChild(svgContainer);
                        wrapper.appendChild(sourceContainer);
                        
                        block.innerHTML = '';
                        block.appendChild(wrapper);
                        
                        console.log('✅ Mermaid rendered successfully');
                    }).catch(err => {
                        console.error('❌ Mermaid render error:', err);
                        block.innerHTML = `
                            <div class="mermaid-error" style="
                                padding: 12px;
                                background: rgba(239, 68, 68, 0.1);
                                border: 1px solid #ef4444;
                                border-radius: 6px;
                                color: #ef4444;
                                font-family: monospace;
                                font-size: 12px;
                            ">
                                <div style="font-weight: bold; margin-bottom: 8px;">⚠️ Mermaid Render Error</div>
                                <pre style="margin: 0; white-space: pre-wrap;">${err.message}</pre>
                            </div>
                        `;
                    });
                } catch (error) {
                    console.error('❌ Mermaid error:', error);
                    block.innerHTML = `
                        <div class="mermaid-error" style="
                            padding: 12px;
                            background: rgba(239, 68, 68, 0.1);
                            border: 1px solid #ef4444;
                            border-radius: 6px;
                            color: #ef4444;
                        ">Failed to initialize mermaid</div>
                    `;
                }
            });
        }
    };

    // NEW: Toggle mermaid between rendered and source
    VeraChat.prototype.toggleMermaid = function(block) {
        const showing = block.dataset.showing;
        const rendered = block.querySelector('.mermaid-rendered');
        const source = block.querySelector('.mermaid-source');
        const toggleBtn = block.querySelector('.mermaid-toggle-btn');
        
        if (showing === 'rendered') {
            rendered.style.display = 'none';
            source.style.display = 'block';
            block.dataset.showing = 'source';
            toggleBtn.innerHTML = '🎨';
            toggleBtn.title = 'Show diagram';
        } else {
            rendered.style.display = 'block';
            source.style.display = 'none';
            block.dataset.showing = 'rendered';
            toggleBtn.innerHTML = '📝';
            toggleBtn.title = 'Show source';
        }
    };


    
    // =====================================================================
    // Content Rendering - INTEGRATED WITH ADVANCED FEATURES
    // =====================================================================
    
    VeraChat.prototype.renderMessageContent = function(content) {
        if (typeof content === 'object') {
            content = JSON.stringify(content, null, 2);
        }
        
        content = String(content);
        
        const codeBlocks = [];
        const mermaidBlocks = [];
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
        
        // Extract code blocks with mermaid detection
        
        // Extract code blocks with mermaid detection
        content = content.replace(/```(\w+)?\n([\s\S]*?)```/g, (match, lang, code) => {
            const language = (lang || 'text').toLowerCase().trim();
            const trimmedCode = code.trim();
            
            // More precise mermaid detection
            const isMermaid = (
                language === 'mermaid' ||
                /^graph\s+(TD|TB|BT|RL|LR)/i.test(trimmedCode) ||
                /^flowchart\s+(TD|TB|BT|RL|LR)/i.test(trimmedCode) ||
                /^sequenceDiagram/i.test(trimmedCode) ||
                /^classDiagram/i.test(trimmedCode) ||
                /^stateDiagram/i.test(trimmedCode) ||
                /^erDiagram/i.test(trimmedCode) ||
                /^gantt/i.test(trimmedCode) ||
                /^pie/i.test(trimmedCode)
            );
            
            if (isMermaid) {
                const placeholder = `###MERMAID${mermaidBlocks.length}###`;
                // Don't escape HTML for mermaid - it needs the raw text
                mermaidBlocks.push(`<div class="mermaid-diagram">${trimmedCode}</div>`);
                return placeholder;
            }
            
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
        mermaidBlocks.forEach((block, i) => content = content.replace(`###MERMAID${i}###`, block));
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
    
    // FIXED: JSON renders in tree mode by default
    VeraChat.prototype.renderInlineJSON = function(code) {
        try {
            const parsed = JSON.parse(code);
            const formatted = JSON.stringify(parsed, null, 2);
            
            return `
                <div class="inline-json-viewer">
                    <div class="format-toolbar">
                        <span class="format-label">JSON</span>
                        <button class="format-btn" onclick="app.toggleJSONView(this); event.stopPropagation();">Raw</button>
                        <button class="format-btn" onclick="app.copyFormatContent(this); event.stopPropagation();">Copy</button>
                    </div>
                    <div class="json-content">
                        <pre class="json-formatted" style="display:none;"><code class="language-json">${this.escapeHtml(formatted)}</code></pre>
                        <div class="json-tree">${this.createCompactJSONTree(parsed)}</div>
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
    
    // FIXED: Canvas button now properly connected
    VeraChat.prototype.renderCodeBlock = function(language, code) {
        const codeId = 'code_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
        return `
            <div class="enhanced-code-block" data-code-id="${codeId}" data-code-lang="${language}" data-code-content="${this.escapeHtml(code).replace(/"/g, '&quot;')}">
                <div class="code-toolbar">
                    <span class="code-language">${language.toUpperCase()}</span>
                    <div class="code-actions">
                        <button class="code-action-btn" onclick="app.copyCodeBlock(this); event.stopPropagation();" title="Copy">📋</button>
                        <button class="code-action-btn" onclick="app.showCanvasModeSelector(this); event.stopPropagation();" title="Send to Canvas">🎨</button>
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
    // Auto-Canvas Streaming - FIXED
    // =====================================================================
        
    VeraChat.prototype.checkAndAutoRenderCanvas = function(message) {
        if (!this.canvasAutoFocus) {
            console.log('Canvas auto-focus disabled');
            return;
        }
        
        const content = message.content;
        console.log('🎯 Checking auto-canvas for content:', content.substring(0, 100));
        
        // Check for code blocks first
        const codeBlockMatch = content.match(/```(\w+)?\n([\s\S]{50,}?)```/);
        if (codeBlockMatch) {
            const language = codeBlockMatch[1] || 'text';
            const code = codeBlockMatch[2];
            
            console.log('📝 Found code block:', language);
            
            // Mermaid diagrams
            if (language === 'mermaid' || code.includes('graph TD') || code.includes('graph LR') || 
                code.includes('sequenceDiagram') || code.includes('flowchart')) {
                console.log('🎨 Auto-rendering mermaid diagram');
                this.autoRenderToCanvas('diagram', code, language);
                return;
            }
            
            // HTML preview
            if (language === 'html' && code.length > 100) {
                console.log('🌐 Auto-rendering HTML preview');
                this.autoRenderToCanvas('preview', code, language);
                return;
            }
            
            // Python/Jupyter
            if ((language === 'python' || language === 'py') && code.length > 100) {
                console.log('📓 Auto-rendering Python code');
                this.autoRenderToCanvas('code', code, language);
                return;
            }
            
            // JavaScript/React preview
            if ((language === 'js' || language === 'javascript' || language === 'jsx') && 
                (code.includes('React') || code.includes('useState') || code.length > 200)) {
                console.log('⚛️ Auto-rendering React code');
                this.autoRenderToCanvas('preview', code, language);
                return;
            }
            
            // SVG
            if (language === 'svg' || code.includes('<svg')) {
                console.log('🖼️ Auto-rendering SVG');
                this.autoRenderToCanvas('preview', code, language);
                return;
            }
            
            // Generic code editor for longer code
            if (code.length > 200) {
                console.log('💻 Auto-rendering generic code');
                this.autoRenderToCanvas('code', code, language);
                return;
            }
        }
        
        // Check for JSON
        if (this.looksLikeJSON(content) && content.length > 100) {
            try {
                JSON.parse(content);
                console.log('🗂️ Auto-rendering JSON');
                this.autoRenderToCanvas('json', content, 'json');
                return;
            } catch (e) {}
        }
        
        // Check for CSV/TSV
        if (this.looksLikeCSV(content) && content.split('\n').length > 3) {
            console.log('📊 Auto-rendering table');
            this.autoRenderToCanvas('table', content, 'csv');
            return;
        }
        
        // Check for Markdown content
        if (content.includes('# ') && content.length > 200) {
            console.log('📝 Auto-rendering markdown');
            this.autoRenderToCanvas('markdown', content, 'markdown');
            return;
        }
        
        console.log('ℹ️ No auto-canvas trigger found');
    };
    
    VeraChat.prototype.autoRenderToCanvas = function(mode, content, language) {
        const now = Date.now();
        if (now - this.lastCanvasCheck < 2000) {
            console.log('⏳ Too soon since last canvas check, skipping');
            return;
        }
        this.lastCanvasCheck = now;
        
        console.log(`🚀 Auto-rendering to canvas: mode=${mode}, lang=${language}`);
        
        const canvasTab = this.tabs ? this.tabs.find(t => t.id === 'canvas') : null;
        if (!canvasTab) {
            console.error('❌ Canvas tab not found');
            return;
        }
        
        this.setControlStatus(`🎨 Auto-rendering in ${mode} mode...`);
        
        setTimeout(() => {
            console.log('📍 Activating canvas tab');
            this.activateTab('canvas', canvasTab.columnId);
            
            setTimeout(() => {
                console.log('🔧 Switching canvas mode and loading content');
                
                if (typeof this.switchCanvasMode === 'function') {
                    this.switchCanvasMode(mode);
                }
                
                const modeSelector = document.querySelector('#canvasMode');
                if (modeSelector) modeSelector.value = mode;
                
                if (typeof this.loadIntoCanvas === 'function') {
                    this.loadIntoCanvas(language, content);
                } else {
                    console.error('❌ loadIntoCanvas function not found');
                }
                
                console.log('✅ Canvas loaded successfully');
            }, 100);
        }, 500);
    };
    
    // FIXED: loadIntoCanvas function that properly integrates with canvas modes
    VeraChat.prototype.loadIntoCanvas = function(language, code) {
        console.log(`📥 Loading into canvas: language=${language}, code length=${code.length}`);
        
        if (!this.canvas) {
            console.error('❌ Canvas not initialized');
            return;
        }
        
        const mode = this.canvas.mode;
        console.log(`📍 Current canvas mode: ${mode}`);
        
        // Set persistent content
        this.canvas.persistentContent = code;
        
        // Load into appropriate editor based on mode
        setTimeout(() => {
            switch(mode) {
                case 'code':
                    if (this.canvas.monacoEditor) {
                        console.log('✏️ Loading into Monaco editor');
                        this.canvas.monacoEditor.setValue(code);
                        
                        // Set language
                        const monacoLang = this.getMonacoLanguageForCanvas(language);
                        monaco.editor.setModelLanguage(this.canvas.monacoEditor.getModel(), monacoLang);
                    }
                    break;
                    
                case 'diagram':
                    const mermaidEditor = document.querySelector('#mermaid-editor');
                    if (mermaidEditor) {
                        console.log('📊 Loading into diagram editor');
                        mermaidEditor.value = code;
                        // Auto-render
                        const renderBtn = document.querySelector('#renderDiagram');
                        if (renderBtn) renderBtn.click();
                    }
                    break;
                    
                case 'preview':
                    const htmlEditor = document.querySelector('#html-editor');
                    if (htmlEditor) {
                        console.log('🌐 Loading into preview editor');
                        htmlEditor.value = code;
                        // Auto-run
                        const runBtn = document.querySelector('#runPreview');
                        if (runBtn) runBtn.click();
                    }
                    break;
                    
                case 'json':
                    const jsonEditor = document.querySelector('#json-editor');
                    if (jsonEditor) {
                        console.log('🗂️ Loading into JSON editor');
                        jsonEditor.value = code;
                        // Auto-parse
                        const parseBtn = document.querySelector('#parseJson');
                        if (parseBtn) parseBtn.click();
                    }
                    break;
                    
                case 'markdown':
                    const mdEditor = document.querySelector('#md-editor');
                    if (mdEditor) {
                        console.log('📝 Loading into markdown editor');
                        mdEditor.value = code;
                        mdEditor.dispatchEvent(new Event('input'));
                    }
                    break;
                    
                case 'table':
                    const tableData = document.querySelector('#table-data');
                    if (tableData) {
                        console.log('📊 Loading into table viewer');
                        tableData.value = code;
                        const parseTableBtn = document.querySelector('#parseTable');
                        if (parseTableBtn) parseTableBtn.click();
                    }
                    break;
                    
                default:
                    console.warn(`⚠️ Unknown canvas mode: ${mode}`);
            }
            
            console.log('✅ Content loaded into canvas');
        }, 200);
    };
    
    VeraChat.prototype.getMonacoLanguageForCanvas = function(language) {
        const map = {
            'javascript': 'javascript',
            'js': 'javascript',
            'python': 'python',
            'py': 'python',
            'html': 'html',
            'css': 'css',
            'json': 'json',
            'markdown': 'markdown',
            'md': 'markdown',
            'typescript': 'typescript',
            'ts': 'typescript',
            'lua': 'lua',
            'cpp': 'cpp',
            'c': 'c',
            'rust': 'rust',
            'go': 'go',
            'arduino': 'arduino'
        };
        return map[language.toLowerCase()] || 'plaintext';
    };
    
    // =====================================================================
    // Message Menu with Proper Positioning & Tools
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
        
        // Tools section
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
        
        // Append to chatMessages container
        chatMessages.appendChild(menu);

        // Position menu VERY close to message bubble
        setTimeout(() => {
            const messageRect = messageEl.getBoundingClientRect();
            const menuRect = menu.getBoundingClientRect();
            
            const gap = 5;
            
            let top = messageRect.top;
            let left = messageRect.right + gap;
            
            const viewportWidth = window.innerWidth;
            if (left + menuRect.width > viewportWidth - 10) {
                left = messageRect.left - menuRect.width - gap;
            }
            
            if (left < 10) {
                left = messageRect.right + gap;
                menu.style.maxWidth = `${viewportWidth - left - 20}px`;
            }
            
            const viewportHeight = window.innerHeight;
            const availableHeight = viewportHeight - top;
            
            if (menuRect.height > availableHeight - 20) {
                const maxHeight = viewportHeight - 40;
                
                if (menuRect.height > maxHeight) {
                    menu.style.maxHeight = `${maxHeight}px`;
                    menu.style.overflowY = 'auto';
                    top = 20;
                } else {
                    top = Math.max(10, messageRect.bottom - menuRect.height);
                }
            }
            
            menu.style.position = 'fixed';
            menu.style.top = `${top}px`;
            menu.style.left = `${left}px`;
            menu.style.zIndex = '10000';
            
        }, 50);
        
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
    // Graph Focus with Better Node Matching
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
            
            let node = null;
            
            if (message.graph_node_id) {
                node = this.networkData.nodes.find(n => n.id === message.graph_node_id);
            }
            
            if (!node) {
                node = this.networkData.nodes.find(n => 
                    n.properties && n.properties.message_id === message.id
                );
            }
            
            if (!node && message.content) {
                const contentStart = message.content.substring(0, 100);
                const role = message.role === 'user' ? 'Query' : 'Response';
                
                node = this.networkData.nodes.find(n => {
                    if (!n.properties) return false;
                    
                    const isRightType = n.type === role || 
                                       n.labels === role ||
                                       (n.properties.type && n.properties.type === role);
                    
                    if (!isRightType) return false;
                    
                    const nodeContent = n.properties.content || n.properties.text || n.properties.query || '';
                    return nodeContent.includes(contentStart) || contentStart.includes(nodeContent.substring(0, 100));
                });
            }
            
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
    // Canvas Integration - FIXED
    // =====================================================================
    
    VeraChat.prototype.sendToCanvasAuto = function(message) {
        console.log('🎯 sendToCanvasAuto called');
        const detection = this.detectContentType ? this.detectContentType(message.content) : { mode: 'code', language: 'text' };
        this.sendToCanvasMode(message, detection.mode);
        this.setControlStatus(`🎨 Sent to Canvas (${detection.mode})`);
    };
    
    VeraChat.prototype.sendToCanvasMode = function(message, mode) {
        console.log(`🚀 sendToCanvasMode: mode=${mode}`);
        
        const canvasTab = this.tabs ? this.tabs.find(t => t.id === 'canvas') : null;
        if (!canvasTab) {
            console.error('❌ Canvas tab not found');
            this.setControlStatus('❌ Canvas not available');
            return;
        }
        
        console.log('📍 Activating canvas tab');
        this.activateTab('canvas', canvasTab.columnId);
        
        setTimeout(() => {
            console.log(`🔧 Switching to ${mode} mode`);
            
            if (typeof this.switchCanvasMode === 'function') {
                this.switchCanvasMode(mode);
            }
            
            const modeSelector = document.querySelector('#canvasMode');
            if (modeSelector) modeSelector.value = mode;
            
            const detection = this.detectContentType ? this.detectContentType(message.content) : { language: 'text' };
            console.log(`📥 Loading content: language=${detection.language}`);
            
            if (typeof this.loadIntoCanvas === 'function') {
                this.loadIntoCanvas(detection.language, message.content);
            } else {
                console.error('❌ loadIntoCanvas function not found');
            }
            
            this.setControlStatus(`✅ Loaded in ${mode} mode`);
            console.log('✅ Canvas load complete');
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
    
    // FIXED: Toggle between raw and tree views
    VeraChat.prototype.toggleJSONView = function(button) {
        const viewer = button.closest('.inline-json-viewer');
        const formatted = viewer.querySelector('.json-formatted');
        const tree = viewer.querySelector('.json-tree');
        
        if (formatted.style.display === 'none') {
            // Currently showing tree, switch to raw
            formatted.style.display = 'block';
            tree.style.display = 'none';
            button.textContent = 'Tree';
        } else {
            // Currently showing raw, switch to tree
            formatted.style.display = 'none';
            tree.style.display = 'block';
            button.textContent = 'Raw';
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
    
    // FIXED: Canvas button now properly extracts code from data attributes
    VeraChat.prototype.showCanvasModeSelector = function(button) {
        console.log('🎨 showCanvasModeSelector called');
        
        const block = button.closest('.enhanced-code-block');
        if (!block) {
            console.error('❌ Could not find code block');
            return;
        }
        
        const code = block.dataset.codeContent || block.querySelector('code').textContent;
        const language = block.dataset.codeLang || block.querySelector('.code-language').textContent.toLowerCase();
        
        console.log(`📝 Code extracted: lang=${language}, length=${code.length}`);
        
        document.querySelectorAll('.canvas-mode-popup').forEach(p => p.remove());
        
        const popup = document.createElement('div');
        popup.className = 'canvas-mode-popup';
        
        // Store in button's dataset for sendCodeToCanvas
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
        
        console.log('✅ Canvas mode popup shown');
    };
    
    VeraChat.prototype.sendCodeToCanvas = function(mode, button) {
        console.log(`🚀 sendCodeToCanvas: mode=${mode}`);
        
        const code = button.dataset.codeContent;
        const language = button.dataset.codeLanguage;
        
        if (!code) {
            console.error('❌ No code found in button dataset');
            return;
        }
        
        console.log(`📝 Code: lang=${language}, length=${code.length}`);
        
        const canvasTab = this.tabs ? this.tabs.find(t => t.id === 'canvas') : null;
        if (!canvasTab) {
            console.error('❌ Canvas tab not found');
            return;
        }
        
        console.log('📍 Activating canvas tab');
        this.activateTab('canvas', canvasTab.columnId);
        
        setTimeout(() => {
            console.log(`🔧 Switching to ${mode} mode and loading content`);
            
            if (typeof this.switchCanvasMode === 'function') {
                this.switchCanvasMode(mode);
            }
            const modeSelector = document.querySelector('#canvasMode');
            if (modeSelector) modeSelector.value = mode;
            
            if (typeof this.loadIntoCanvas === 'function') {
                this.loadIntoCanvas(language, code);
            } else {
                console.error('❌ loadIntoCanvas function not found');
            }
            
            console.log('✅ Code loaded into canvas');
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
    
    VeraChat.prototype.escapeHtml = function(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    };
    
    // =====================================================================
    // Load External Libraries
    // =====================================================================
    
    const loadExternalLibraries = () => {
        if (!window.marked) {
            const markedScript = document.createElement('script');
            markedScript.src = 'https://cdn.jsdelivr.net/npm/marked/marked.min.js';
            document.head.appendChild(markedScript);
        }
        
        if (!window.hljs) {
            const hljsScript = document.createElement('script');
            hljsScript.src = 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js';
            document.head.appendChild(hljsScript);
            
            const hljsStyle = document.createElement('link');
            hljsStyle.rel = 'stylesheet';
            hljsStyle.href = 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-dark.min.css';
            document.head.appendChild(hljsStyle);
        }
        
        if (!window.mermaid) {
            const mermaidScript = document.createElement('script');
            mermaidScript.src = 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js';
            mermaidScript.onload = () => {
                window.mermaid.initialize({ 
                    startOnLoad: false,
                    theme: 'dark',
                    themeVariables: {
                        primaryColor: '#3b82f6',
                        primaryTextColor: '#e2e8f0',
                        primaryBorderColor: '#60a5fa',
                        lineColor: '#475569',
                        secondaryColor: '#1e293b',
                        tertiaryColor: '#0f172a'
                    }
                });
                console.log('✅ Mermaid initialized');
            };
            document.head.appendChild(mermaidScript);
        }
    };
    
    loadExternalLibraries();
    
    // =====================================================================
    // Initialize - ONE-TIME WRAPPER
    // =====================================================================
    
    if (!VeraChat.prototype._originalInit) {
        console.log('💾 Storing original init function');
        VeraChat.prototype._originalInit = VeraChat.prototype.init;
    }

    if (!VeraChat.prototype._modernUIWrapped) {
        console.log('🔧 Wrapping init function (first time only)');
        
        VeraChat.prototype.init = async function() {
            console.log('🔄 VeraChat.init called');
            
            const result = await this._originalInit.call(this);
            
            console.log('🎨 Calling initModernFeatures');
            this.initModernFeatures();

            return result;
        };
        
        VeraChat.prototype._modernUIWrapped = true;
        console.log('✅ Init wrapper installed');
    } else {
        console.log('⏭️ Init already wrapped, skipping');
    }
    
    console.log('🚀 Modern Interactive Chat UI (COMPLETE FIX) loaded successfully');
})();