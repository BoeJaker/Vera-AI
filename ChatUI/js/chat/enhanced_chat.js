// =====================================================================
// Modern Interactive Chat UI - COMPLETE FIX
// Fixes: Canvas buttons, mermaid rendering, auto-focus, full-width bubbles
// =====================================================================

(() => {

        // Make sure handleWebSocketMessage uses the correct function
        VeraChat.prototype.handleWebSocketMessage = function(data) {
            this.veraRobot.setState('thinking');
            
            if (data.type === 'chunk') {
                if (!this.currentStreamingMessageId) {
                    this.currentStreamingMessageId = `msg-${Date.now()}`;
                    this.addMessage('assistant', '', this.currentStreamingMessageId);
                    
                    if (this.ttsEnabled) {
                        this.ttsSpokenLength = 0;
                    }
                }
                
                const message = this.messages.find(m => m.id === this.currentStreamingMessageId);
                if (message) {
                    message.content += data.content;
                    this.updateStreamingMessageContent(this.currentStreamingMessageId, message.content);
                    
                    // TTS: speak ONLY main content (no thoughts)
                    if (typeof this.speakStreamingText === 'function' && this.ttsEnabled) {
                        const { mainContent } = this.extractThoughtsByBalance(message.content);
                        this.speakStreamingText(mainContent);
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
                        
                        // Final render with thoughts properly separated
                        const { mainContent } = this.extractThoughtsByBalance(message.content);
                        const renderedView = messageEl.querySelector('.message-rendered');
                        if (renderedView && typeof this.renderMessageContent === 'function') {
                            renderedView.innerHTML = this.renderMessageContent(mainContent);
                        }
                        
                        // Apply syntax highlighting
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
                        
                        // Finalize TTS
                        if (typeof this.finalizeTTS === 'function' && this.ttsEnabled) {
                            setTimeout(() => {
                                const { mainContent } = this.extractThoughtsByBalance(message.content);
                                this.finalizeTTS(mainContent);
                            }, 300);
                        }
                    }
                }
                
                this.currentStreamingMessageId = null;
                this.processing = false;
                
                const sendBtn = document.getElementById('sendBtn');
                const messageInput = document.getElementById('messageInput');
                app.loadGraph();
                if (sendBtn) sendBtn.disabled = false;
                if (messageInput) {
                    messageInput.disabled = false;
                    setTimeout(() => {
                        if (messageInput && document.activeElement !== messageInput) {
                            messageInput.focus();
                        }
                    }, 100);
                }
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
        
        // VeraChat.prototype.updateStreamingMessageContent = function(messageId, content) {
        //     const messageEl = document.getElementById(messageId);
        //     if (!messageEl) return;
            
        //     // Use the message-content div, NOT the inner rendered div
        //     const contentContainer = messageEl.querySelector('.message-content');
        //     if (!contentContainer) return;
            
        //     // Check if we have modern UI structure (with message-rendered div)
        //     let renderedView = contentContainer.querySelector('.message-rendered');
            
        //     if (renderedView) {
        //         // MODERN UI: Update the rendered view
        //         if (typeof this.renderMessageContent === 'function') {
        //             // Use modern renderMessageContent (has mermaid, advanced features)
        //             renderedView.innerHTML = this.renderMessageContent(content);
        //         } else {
        //             // Fallback to basic if modern not loaded yet
        //             renderedView.innerHTML = this.parseMessageContent(content);
        //         }
        //     } else {
        //         // BASIC UI: Just update the content directly
        //         if (typeof this.renderMessageContent === 'function') {
        //             contentContainer.innerHTML = this.renderMessageContent(content);
        //         } else {
        //             const updatedContent = content.replace(/^(\w+)/, '**Agent: $1**');
        //             contentContainer.innerHTML = this.parseMessageContent(updatedContent);
        //         }
        //     }
            
        //     // Add/update streaming indicator
        //     let indicator = contentContainer.querySelector('.streaming-indicator');
        //     if (!indicator) {
        //         indicator = document.createElement('div');
        //         indicator.className = 'streaming-indicator';
        //         indicator.style.cssText = 'color: #60a5fa; font-size: 12px; margin-top: 8px; padding: 4px 8px; background: rgba(59, 130, 246, 0.0); border-radius: 4px; display: inline-block;';
        //         indicator.textContent = '● Streaming...';
        //         contentContainer.appendChild(indicator);
        //     }
            
        //     // Auto-scroll if near bottom
        //     const container = document.getElementById('chatMessages');
        //     if (container) {
        //         const isScrolledToBottom = container.scrollHeight - container.clientHeight <= container.scrollTop + 50;
        //         if (isScrolledToBottom) {
        //             container.scrollTop = container.scrollHeight;
        //         }
        //     }
        // };

        VeraChat.prototype.updateStreamingMessageContent = function(messageId, content) {
            const messageEl = document.getElementById(messageId);
            if (!messageEl) return;
            
            const contentContainer = messageEl.querySelector('.message-content');
            if (!contentContainer) return;
            
            // Extract thoughts and clean content
            const { thoughtContent, mainContent, isThinking } = this.extractThoughtsByBalance(content);
            
            // Handle thought container
            if (thoughtContent || isThinking) {
                let thoughtContainer = contentContainer.querySelector('.thought-container');
                
                if (!thoughtContainer) {
                    thoughtContainer = document.createElement('div');
                    thoughtContainer.className = 'thought-container';
                    contentContainer.insertBefore(thoughtContainer, contentContainer.firstChild);
                }
                
                // Update thought container
                const isComplete = !isThinking;
                thoughtContainer.className = isComplete ? 'thought-container complete' : 'thought-container';
                thoughtContainer.innerHTML = `
                    <div class="thought-header">
                        <span class="thought-icon">${isComplete ? '✓' : '💭'}</span>
                        <span class="thought-label">${isComplete ? 'Thought process' : 'Thinking...'}</span>
                    </div>
                    <div class="thought-content">${this.escapeHtml(thoughtContent || '')}</div>
                `;
            }
            
            // Update main content
            let renderedView = contentContainer.querySelector('.message-rendered');
            if (!renderedView) {
                renderedView = document.createElement('div');
                renderedView.className = 'message-rendered';
                contentContainer.appendChild(renderedView);
            }
            
            renderedView.textContent = mainContent;
            
            // Streaming indicator
            let indicator = contentContainer.querySelector('.streaming-indicator');
            if (!indicator) {
                indicator = document.createElement('div');
                indicator.className = 'streaming-indicator';
                indicator.style.cssText = 'color: #60a5fa; font-size: 12px; margin-top: 8px; padding: 4px 8px; background: rgba(59, 130, 246, 0.0); border-radius: 4px; display: inline-block;';
                indicator.innerHTML = '<span style="display: inline-block; width: 8px; height: 8px; background: var(--accent); border-radius: 50%; margin-right: 6px;"></span>Streaming...';
                contentContainer.appendChild(indicator);
            }
            
            // Auto-scroll
            const container = document.getElementById('chatMessages');
            if (container) {
                const isScrolledToBottom = container.scrollHeight - container.clientHeight <= container.scrollTop + 50;
                if (isScrolledToBottom) {
                    container.scrollTop = container.scrollHeight;
                }
            }
        };

        
        VeraChat.prototype.extractThoughtsByBalance = function(content) {
            let thoughtContent = '';
            let mainContent = '';
            let inThought = false;
            let openCount = 0;
            let closeCount = 0;
            let currentThought = '';
            let currentMain = '';
            let i = 0;
            
            while (i < content.length) {
                // Check for opening tag
                if (content.substring(i, i + 9) === '<thought>') {
                    openCount++;
                    
                    // If this is the FIRST opening tag, switch to thought mode
                    if (openCount === 1) {
                        inThought = true;
                        // Save any content before first thought tag to main
                        mainContent += currentMain;
                        currentMain = '';
                    }
                    
                    // Skip past the tag
                    i += 9;
                    continue;
                }
                
                // Check for closing tag
                if (content.substring(i, i + 10) === '</thought>') {
                    closeCount++;
                    
                    // If counts now match, we're done with ALL thoughts
                    if (openCount === closeCount && openCount > 0) {
                        thoughtContent = currentThought;
                        currentThought = '';
                        inThought = false;
                        // Reset for potential new thought blocks
                        openCount = 0;
                        closeCount = 0;
                    }
                    
                    // Skip past the tag
                    i += 10;
                    continue;
                }
                
                // Regular character - add to appropriate bucket
                if (inThought) {
                    currentThought += content[i];
                } else {
                    currentMain += content[i];
                }
                
                i++;
            }
            
            // CRITICAL: If still in thought mode, capture current thought
            // but DON'T add it to mainContent
            if (inThought && currentThought) {
                thoughtContent = currentThought;
            }
            
            // CRITICAL: Only add currentMain if we're NOT in thought mode
            if (!inThought) {
                mainContent += currentMain;
            }
            
            const isThinking = openCount > closeCount;
            
            return {
                thoughtContent: thoughtContent.trim(),
                mainContent: mainContent.trim(),
                isThinking: isThinking
            };
        };

        // NEW: Parse streaming content to separate thoughts from main content
        VeraChat.prototype.parseStreamingContent = function(content) {
            const hasOpenTag = content.includes('<thought>');
            const hasCloseTag = content.includes('</thought>');
            
            if (!hasOpenTag) {
                return {
                    hasThought: false,
                    thoughtText: '',
                    thoughtComplete: false,
                    mainContent: content
                };
            }
            
            const thoughtStart = content.indexOf('<thought>') + 9;
            let thoughtEnd = content.indexOf('</thought>');
            
            if (thoughtEnd === -1) {
                thoughtEnd = content.length;
            }
            
            const thoughtText = content.substring(thoughtStart, thoughtEnd);
            const beforeThought = content.substring(0, content.indexOf('<thought>'));
            const afterThought = hasCloseTag ? content.substring(content.indexOf('</thought>') + 10) : '';
            const mainContent = (beforeThought + ' ' + afterThought).trim();
            
            return {
                hasThought: true,
                thoughtText: thoughtText,
                thoughtComplete: hasCloseTag,
                mainContent: mainContent
            };
        };

        VeraChat.prototype.sendMessageViaWebSocket = async function(message) {
            this.veraRobot.setState('thinking');
            if (!this.websocket || this.websocket.readyState !== WebSocket.OPEN) {
                return false;
            }
            app.loadGraph()
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
        VeraChat.prototype.stopMessage = async function() {
            if (!this.processing) {
                console.warn('No message is currently being processed.');
                return;
            }

            try {
                const response = await fetch('http://llm.int:8888/api/stop', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ session_id: this.sessionId })
                });

                if (!response.ok) {
                    throw new Error('Failed to stop the message');
                }

                const data = await response.json();
                console.log('Message stopped:', data);

                this.processing = false;
                this.currentStreamingMessageId = null;

                const sendBtn = document.getElementById('sendBtn');
                const messageInput = document.getElementById('messageInput');
                if (sendBtn) sendBtn.disabled = false;
                if (messageInput) {
                    messageInput.disabled = false;
                    messageInput.focus();
                }

                this.setControlStatus('🛑 Message processing stopped');
            } catch (error) {
                console.error('Error stopping message:', error);
                this.addSystemMessage(`Error: ${error.message}`);
            }
        };
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
                // await VeraChat.loadGraph();
            } catch (error) {
                console.error('Send error:', error);
                this.addSystemMessage(`Error: ${error.message}`);
            }
            // VeraChat.loadGraph();

            this.processing = false;
            document.getElementById('sendBtn').disabled = false;
            input.disabled = false;
            input.focus();
        }
        
        VeraChat.prototype.addMessage = function(role, content, id = null) {
            const messageId = id || `msg-${Date.now()}`;
            const message = { id: messageId, role, content, timestamp: Date.now() }; // Store as number, not Date object
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
            messageEl.className = `message ${message.role} modern-message`;
            messageEl.dataset.messageId = message.id;
            messageEl.dataset.messageContent = message.content;
            messageEl.dataset.graphNodeId = message.graph_node_id || `msg_${message.id}`;
            messageEl.dataset.showingSource = 'false';
            
            // Detect wide content
            const hasWideContent = this.hasWideContent(message.content);
            if (hasWideContent) {
                messageEl.classList.add('message-wide');
            }
            
            // Make clickable for non-system messages
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
            
            // Extract thoughts
            const { thoughtContent, mainContent } = this.extractThoughtsByBalance(message.content);
            
            // Add thought container if thoughts exist
            if (thoughtContent) {
                const thoughtContainer = document.createElement('div');
                thoughtContainer.className = 'thought-container complete';
                thoughtContainer.innerHTML = `
                    <div class="thought-header">
                        <span class="thought-icon">✓</span>
                        <span class="thought-label">Thought process</span>
                    </div>
                    <div class="thought-content">${this.escapeHtml(thoughtContent)}</div>
                `;
                content.appendChild(thoughtContainer);
            }
            
            // Rendered view (main content without thoughts)
            const renderedView = document.createElement('div');
            renderedView.className = 'message-rendered';
            renderedView.innerHTML = this.renderMessageContent(mainContent);
            
            // Source view (show original with tags)
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
            
            // Apply rendering
            setTimeout(() => {
                this.applyRendering(message.id);
            }, 100);
            
            // Auto-focus canvas
            if (this.canvasAutoFocus && message.role === 'assistant') {
                setTimeout(() => {
                    this.checkAndAutoRenderCanvas(message);
                }, 300);
            }
            
            container.scrollTop = container.scrollHeight;
        };

        
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
        // NEW: Thought tracking
        this.currentThought = null;
        this.inThoughtTag = false;
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
        const self = this;
        
        // Update timestamps every 10 seconds (for testing, change to 60000 for production)
        this.timestampInterval = setInterval(() => {
            const timestamps = document.querySelectorAll('.message-timestamp');
            console.log(`🕐 Updating ${timestamps.length} timestamps`);
            
            // Check if messages array exists
            if (!self.messages || !Array.isArray(self.messages)) {
                console.warn('⚠️ Messages array not available yet');
                return;
            }
            
            console.log(` Messages in array: ${self.messages.length}`);
            
            timestamps.forEach(el => {
                const messageEl = el.closest('.message');
                if (!messageEl) return;
                
                const messageId = messageEl.id;
                console.log(`🔍 Looking for message: ${messageId}`);
                
                const message = self.messages.find(m => m.id === messageId);
                
                if (message && message.timestamp) {
                    const newText = self.formatTimestamp(message.timestamp);
                    if (el.textContent !== newText) {
                        el.textContent = newText;
                        console.log(`🕐 Updated ${messageId}: ${newText}`);
                    }
                } else {
                    console.warn(`⚠️ Message not found: ${messageId}`);
                }
            });
        }, 60000); // 10 seconds for testing, change to 60000 for production
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
        // Clear existing highlights first
        element.querySelectorAll('.search-highlight').forEach(span => {
            span.replaceWith(document.createTextNode(span.textContent));
        });
        
        // Escape special regex characters
        const escapedQuery = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const regex = new RegExp(`(${escapedQuery})`, 'gi');
        
        const walker = document.createTreeWalker(
            element,
            NodeFilter.SHOW_TEXT,
            {
                acceptNode: function(node) {
                    // Skip if already inside a highlight
                    if (node.parentElement.classList.contains('search-highlight')) {
                        return NodeFilter.FILTER_REJECT;
                    }
                    // Skip if inside script, style, or code blocks
                    const parent = node.parentElement;
                    if (parent && (parent.tagName === 'SCRIPT' || parent.tagName === 'STYLE' || 
                                   parent.tagName === 'CODE' || parent.classList.contains('code-toolbar'))) {
                        return NodeFilter.FILTER_REJECT;
                    }
                    return regex.test(node.textContent) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
                }
            },
            false
        );
        
        const textNodes = [];
        let node;
        while (node = walker.nextNode()) {
            textNodes.push(node);
        }
        
        textNodes.forEach(textNode => {
            const text = textNode.textContent;
            if (!regex.test(text)) return;
            
            const fragment = document.createDocumentFragment();
            let lastIndex = 0;
            
            text.replace(regex, (match, p1, offset) => {
                // Add text before match
                if (offset > lastIndex) {
                    fragment.appendChild(document.createTextNode(text.slice(lastIndex, offset)));
                }
                
                // Add highlighted match
                const span = document.createElement('span');
                span.className = 'search-highlight';
                span.textContent = match;
                fragment.appendChild(span);
                
                lastIndex = offset + match.length;
            });
            
            // Add remaining text
            if (lastIndex < text.length) {
                fragment.appendChild(document.createTextNode(text.slice(lastIndex)));
            }
            
            textNode.parentNode.replaceChild(fragment, textNode);
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
    // CSS
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
    
    // Add streaming state tracker
    VeraChat.prototype.initStreamingState = function(messageId) {
        if (!this.streamingStates) {
            this.streamingStates = {};
        }
        
        this.streamingStates[messageId] = {
            processedLength: 0,
            thoughtDepth: 0,  // Track nesting level
            currentThought: '',
            accumulatedThoughts: [],
            mainContent: '',
            lastTTSPosition: 0
        };
        
        return this.streamingStates[messageId];
    };
    VeraChat.prototype.getStreamingState = function(messageId) {
        return this.streamingStates?.[messageId] || this.initStreamingState(messageId);
    };

    VeraChat.prototype.clearStreamingState = function(messageId) {
        if (this.streamingStates) {
            delete this.streamingStates[messageId];
        }
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
            
            const contentContainer = messageEl.querySelector('.message-content');
            if (!contentContainer) return;
            
            // Extract thoughts and clean content
            const { thoughtContent, mainContent, isThinking } = this.extractThoughtsByBalance(content);
            
            // Update or create thought container
            if (thoughtContent || isThinking) {
                let thoughtContainer = contentContainer.querySelector('.thought-container');
                
                if (!thoughtContainer) {
                    thoughtContainer = document.createElement('div');
                    thoughtContainer.className = 'thought-container';
                    contentContainer.insertBefore(thoughtContainer, contentContainer.firstChild);
                }
                
                const isComplete = !isThinking;
                thoughtContainer.className = isComplete ? 'thought-container complete' : 'thought-container';
                thoughtContainer.innerHTML = `
                    <div class="thought-header">
                        <span class="thought-icon">${isComplete ? '✓' : '💭'}</span>
                        <span class="thought-label">${isComplete ? 'Thought process' : 'Thinking...'}</span>
                    </div>
                    <div class="thought-content">${this.escapeHtml(thoughtContent || 'Processing...')}</div>
                `;
            }
            
            // Update main content container
            let renderedView = contentContainer.querySelector('.message-rendered');
            if (!renderedView) {
                renderedView = document.createElement('div');
                renderedView.className = 'message-rendered';
                contentContainer.appendChild(renderedView);
            }
            
            // CRITICAL: Only show mainContent (thoughts completely stripped)
            // If we're currently thinking and have no main content yet, show nothing
            if (mainContent || !isThinking) {
                renderedView.textContent = mainContent;
            } else {
                renderedView.textContent = '';  // Empty while thinking
            }
            
            // Streaming indicator
            let indicator = contentContainer.querySelector('.streaming-indicator');
            if (!indicator) {
                indicator = document.createElement('div');
                indicator.className = 'streaming-indicator';
                indicator.style.cssText = 'color: #60a5fa; font-size: 12px; margin-top: 8px; padding: 4px 8px; background: rgba(59, 130, 246, 0.0); border-radius: 4px; display: inline-block;';
                indicator.innerHTML = '<span style="display: inline-block; width: 8px; height: 8px; background: var(--accent); border-radius: 50%; margin-right: 6px;"></span>Streaming...';
                contentContainer.appendChild(indicator);
            }
            
            // Auto-scroll
            const container = document.getElementById('chatMessages');
            if (container) {
                const isScrolledToBottom = container.scrollHeight - container.clientHeight <= container.scrollTop + 50;
                if (isScrolledToBottom) {
                    container.scrollTop = container.scrollHeight;
                }
            }
        };


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
                        <button class="code-action-btn" onclick="app.execute_code(this); event.stopPropagation();" title="Execute">Execute</button>
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
        console.log('🔇 Canvas auto-focus disabled');
        return;
    }
    
    console.log('🎯 Checking for code blocks in message:', message.id);
    
    // Simple regex to find code blocks: ```language\ncode```
    const codeBlockRegex = /```(\w+)?\n([\s\S]*?)```/g;
    let match = codeBlockRegex.exec(message.content);
    
    if (match) {
        const language = (match[1] || 'text').toLowerCase();
        const code = match[2].trim();
        
        console.log(`✨ Found code block: ${language}, ${code.length} chars`);
        
        // Determine best canvas mode based on language
        const mode = this.getCanvasModeForLanguage(language);
        
        console.log(`🚀 Auto-opening in ${mode} mode`);
        this.autoRenderToCanvas(mode, code, language);
        return true;
    }
    
    console.log('ℹ️ No code blocks found');
    return false;
};
VeraChat.prototype.getCanvasModeForLanguage = function(language) {
    const modeMap = {
        // Diagrams
        'mermaid': 'diagram',
        
        // Embedded/Hardware
        'arduino': 'embedded-ide',
        'ino': 'embedded-ide',
        
        // Game engines
        'lua': 'tic80',
        
        // Web
        'html': 'preview',
        'css': 'preview',
        
        // Data
        'json': 'json',
        'csv': 'table',
        'tsv': 'table',
        
        // Documents
        'markdown': 'markdown',
        'md': 'markdown',
        
        // Code (default)
        'python': 'code',
        'javascript': 'code',
        'js': 'code',
        'typescript': 'code',
        'ts': 'code',
        'cpp': 'code',
        'c': 'code',
        'rust': 'code',
        'go': 'code',
        'java': 'code',
        'ruby': 'code',
        'php': 'code',
        'bash': 'code',
        'sh': 'code'
    };
    
    return modeMap[language] || 'code';
};

// NEW: Comprehensive content detection
VeraChat.prototype.detectSpecializedContent = function(content) {
    // Priority order for detection
    
    // 1. Mermaid diagrams (highest priority for visual content)
    if (this.containsMermaidDiagram(content)) {
        const diagram = this.extractMermaidDiagram(content);
        return { type: 'mermaid', mode: 'diagram', content: diagram, language: 'mermaid' };
    }
    
    // 2. Jupyter notebooks
    if (content.includes('"nbformat"') || content.includes('"cells"')) {
        return { type: 'jupyter', mode: 'jupyter', content: content, language: 'json' };
    }
    
    // 3. TIC-80 code
    if (this.containsTIC80Code(content)) {
        const code = this.extractTIC80Code(content);
        return { type: 'tic80', mode: 'tic80', content: code, language: 'lua' };
    }
    
    // 4. Arduino/Embedded code
    if (this.containsArduinoCode(content)) {
        const code = this.extractArduinoCode(content);
        return { type: 'arduino', mode: 'embedded-ide', content: code, language: 'arduino' };
    }
    
    // 5. HTML/JS preview
    if (this.containsHTMLPreview(content)) {
        const html = this.extractHTMLCode(content);
        return { type: 'html', mode: 'preview', content: html, language: 'html' };
    }
    
    // 6. SVG graphics
    if (content.includes('<svg') && content.includes('</svg>')) {
        const svg = this.extractSVGCode(content);
        return { type: 'svg', mode: 'preview', content: svg, language: 'html' };
    }
    
    // 7. JSON data
    if (this.containsSignificantJSON(content)) {
        const json = this.extractJSONContent(content);
        return { type: 'json', mode: 'json', content: json, language: 'json' };
    }
    
    // 8. CSV/TSV tables
    if (this.containsTableData(content)) {
        const table = this.extractTableData(content);
        return { type: 'table', mode: 'table', content: table, language: 'csv' };
    }
    
    // 9. Large code blocks (generic)
    const codeBlock = this.extractLargeCodeBlock(content);
    if (codeBlock && codeBlock.code.length > 200) {
        return { type: 'code', mode: 'code', content: codeBlock.code, language: codeBlock.language };
    }
    
    // 10. Markdown documents
    if (this.containsSignificantMarkdown(content)) {
        return { type: 'markdown', mode: 'markdown', content: content, language: 'markdown' };
    }
    
    return { type: null };
};

// Detection helper functions
VeraChat.prototype.containsMermaidDiagram = function(content) {
    return /```mermaid|```\s*\n\s*(graph|flowchart|sequenceDiagram|classDiagram|stateDiagram|erDiagram|gantt|pie)/i.test(content);
};

VeraChat.prototype.extractMermaidDiagram = function(content) {
    const match = content.match(/```(?:mermaid)?\s*\n([\s\S]*?)```/);
    if (match) return match[1].trim();
    
    // Try without code fences
    const diagramMatch = content.match(/(graph|flowchart|sequenceDiagram|classDiagram)[\s\S]*$/i);
    if (diagramMatch) return diagramMatch[0].trim();
    
    return content;
};

VeraChat.prototype.containsTIC80Code = function(content) {
    return content.includes('function TIC()') || 
           /-- title:|-- script:|-- author:/i.test(content) ||
           (content.includes('function TIC') && (content.includes('spr(') || content.includes('cls(') || content.includes('btn(')));
};

VeraChat.prototype.extractTIC80Code = function(content) {
    const match = content.match(/```(?:lua|javascript)?\s*\n([\s\S]*?)```/);
    if (match) return match[1].trim();
    return content;
};

VeraChat.prototype.containsArduinoCode = function(content) {
    return (content.includes('void setup()') || content.includes('void loop()')) &&
           (content.includes('pinMode') || content.includes('digitalWrite') || content.includes('Serial'));
};

VeraChat.prototype.extractArduinoCode = function(content) {
    const match = content.match(/```(?:arduino|cpp|c)?\s*\n([\s\S]*?)```/);
    if (match) return match[1].trim();
    return content;
};

VeraChat.prototype.containsHTMLPreview = function(content) {
    const hasHTML = /<(html|head|body|div|script|style)[\s>]/i.test(content);
    const isLarge = content.length > 100;
    return hasHTML && isLarge;
};

VeraChat.prototype.extractHTMLCode = function(content) {
    const match = content.match(/```html\s*\n([\s\S]*?)```/);
    if (match) return match[1].trim();
    return content;
};

VeraChat.prototype.extractSVGCode = function(content) {
    const match = content.match(/<svg[\s\S]*?<\/svg>/i);
    if (match) return match[0];
    return content;
};

VeraChat.prototype.containsSignificantJSON = function(content) {
    const trimmed = content.trim();
    if (!trimmed.startsWith('{') && !trimmed.startsWith('[')) return false;
    
    try {
        const parsed = JSON.parse(trimmed);
        // Must be object or array with reasonable size
        if (typeof parsed === 'object' && JSON.stringify(parsed).length > 100) {
            return true;
        }
    } catch (e) {
        return false;
    }
    return false;
};

VeraChat.prototype.extractJSONContent = function(content) {
    const match = content.match(/```json\s*\n([\s\S]*?)```/);
    if (match) return match[1].trim();
    
    // Try to extract raw JSON
    const trimmed = content.trim();
    if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
        try {
            JSON.parse(trimmed);
            return trimmed;
        } catch (e) {}
    }
    
    return content;
};

VeraChat.prototype.containsTableData = function(content) {
    const lines = content.trim().split('\n');
    if (lines.length < 3) return false;
    
    // Check for CSV-like structure
    const firstLine = lines[0];
    const commas = (firstLine.match(/,/g) || []).length;
    const tabs = (firstLine.match(/\t/g) || []).length;
    
    if (commas >= 2 || tabs >= 2) {
        // Verify other lines have similar structure
        const secondLine = lines[1];
        const secondCommas = (secondLine.match(/,/g) || []).length;
        const secondTabs = (secondLine.match(/\t/g) || []).length;
        
        return Math.abs(commas - secondCommas) <= 1 || Math.abs(tabs - secondTabs) <= 1;
    }
    
    return false;
};

VeraChat.prototype.extractTableData = function(content) {
    const match = content.match(/```(?:csv|tsv)?\s*\n([\s\S]*?)```/);
    if (match) return match[1].trim();
    return content;
};

VeraChat.prototype.extractLargeCodeBlock = function(content) {
    const match = content.match(/```(\w+)?\s*\n([\s\S]*?)```/);
    if (match) {
        return {
            language: match[1] || 'text',
            code: match[2].trim()
        };
    }
    return null;
};

VeraChat.prototype.containsSignificantMarkdown = function(content) {
    // Must have markdown formatting and be reasonably long
    const hasHeaders = /^#{1,6}\s+.+$/m.test(content);
    const hasLists = /^[\*\-\+]\s+.+$/m.test(content);
    const hasFormatting = /\*\*[^*]+\*\*|\*[^*]+\*/.test(content);
    const isLong = content.length > 300;
    
    return (hasHeaders || hasLists || hasFormatting) && isLong;
};

 VeraChat.prototype.autoRenderToCanvas = function(mode, content, language) {
    const now = Date.now();
    if (now - this.lastCanvasCheck < 2000) {
        console.log('⏳ Too soon since last canvas check, skipping');
        return;
    }
    this.lastCanvasCheck = now;
    
    console.log(`🚀 Auto-rendering to canvas: mode=${mode}, lang=${language}`);
    this.sendDirectlyToCanvas(mode, content, language);
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
                        console.log(' Loading into diagram editor');
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
                        console.log(' Loading into table viewer');
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
    // Remove any existing sidebar
    document.querySelectorAll('.message-sidebar').forEach(s => s.remove());
    
    const sidebar = document.createElement('div');
    sidebar.className = 'message-sidebar';
    sidebar.dataset.messageId = messageId;
    
    const sections = [];
    
    // NEW: Notebook section
    sections.push({
        title: 'Save to Notebook',
        icon: '',
        items: [
            { label: 'Save as Note', icon: '', action: () => this.captureMessageAsNote(messageId) },
            { label: 'Quick Save', icon: '', action: () => this.quickSaveToNotebook(message) }
        ]
    });
    
    // Canvas section - ENHANCED
    sections.push({
        title: 'Send to Canvas',
        icon: '',
        items: [
            { label: 'Auto-detect', icon: '', action: () => this.sendToCanvasAuto(message) },
            { label: 'Code Editor', icon: '', action: () => this.sendToCanvasMode(message, 'code') },
            { label: 'Markdown', icon: '', action: () => this.sendToCanvasMode(message, 'markdown') },
            { label: 'Jupyter', icon: '', action: () => this.sendToCanvasMode(message, 'jupyter') },
            { label: 'JSON Viewer', icon: '', action: () => this.sendToCanvasMode(message, 'json') },
            { label: 'Table', icon: '', action: () => this.sendToCanvasMode(message, 'table') },
            { label: 'Diagram', icon: '', action: () => this.sendToCanvasMode(message, 'diagram') },
            { label: 'Preview', icon: '', action: () => this.sendToCanvasMode(message, 'preview') },
            { label: 'Terminal', icon: '', action: () => this.sendToCanvasMode(message, 'terminal') },
            { label: 'Embedded IDE', icon: '', action: () => this.sendToCanvasMode(message, 'embedded-ide') },
            { label: 'TIC-80', icon: '', action: () => this.sendToCanvasMode(message, 'tic80') }
        ]
    });
    
    // Tools section
    if (this.availableTools && Object.keys(this.availableTools).length > 0) {
        const toolItems = Object.values(this.availableTools).slice(0, 8).map(tool => ({
            label: tool.name,
            icon: '',
            action: () => this.runToolOnMessage(message, tool.name)
        }));
        
        if (Object.keys(this.availableTools).length > 8) {
            toolItems.push({
                label: 'More tools...',
                icon: '',
                action: () => this.showAllToolsForMessage(message)
            });
        }
        
        sections.push({
            title: 'Run Tool',
            icon: '',
            items: toolItems
        });
    }
    
    // Actions section
    sections.push({
        title: 'Actions',
        icon: '',
        items: [
            { label: 'Focus in Graph', icon: '', action: () => this.focusMessageInGraph(message) },
            { label: 'Copy', icon: '', action: () => this.copyMessageContent(messageId) },
            { label: 'Star', icon: '', action: () => this.starMessage(messageId) },
            { label: 'Delete', icon: '', action: () => this.deleteMessage(messageId), className: 'danger' }
        ]
    });
    
    let menuHTML = `
        <div class="sidebar-header">
            <h3>Message Options</h3>
            <button class="sidebar-close" onclick="app.closeMessageSidebar(); event.stopPropagation();">✕</button>
        </div>
        <div class="sidebar-content">
    `;
    
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
    sidebar.innerHTML = menuHTML;
    
    // Store actions
    if (!this.menuActions) this.menuActions = {};
    sections.forEach((section, sectionIndex) => {
        section.items.forEach((item, itemIndex) => {
            const actionKey = `${messageId}_${sectionIndex}_${itemIndex}`;
            this.menuActions[actionKey] = item.action;
        });
    });
    
    // Add backdrop
    const backdrop = document.createElement('div');
    backdrop.className = 'sidebar-backdrop';
    backdrop.onclick = () => this.closeMessageSidebar();
    
    document.body.appendChild(backdrop);
    document.body.appendChild(sidebar);
    
    // Trigger slide-in animation
    setTimeout(() => {
        sidebar.classList.add('active');
        backdrop.classList.add('active');
    }, 10);
};


// NEW: Quick save to notebook without prompt
VeraChat.prototype.quickSaveToNotebook = async function(message) {
    if (!this.currentNotebook) {
        this.setControlStatus('⚠️ Select a notebook first');
        
        // Try to auto-select or create default notebook
        if (this.notebooks && this.notebooks.length > 0) {
            this.currentNotebook = this.notebooks[0];
        } else {
            this.setControlStatus('❌ No notebooks available');
            return;
        }
    }
    
    const title = `${message.role} - ${new Date(message.timestamp).toLocaleString()}`;
    
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
                        message_id: message.id,
                        role: message.role,
                        timestamp: message.timestamp
                    }
                })
            }
        );
        
        if (!response.ok) throw new Error('Failed to save');
        
        this.setControlStatus(`✅ Saved to ${this.currentNotebook.name}`);
    } catch (error) {
        console.error('Failed to quick save:', error);
        this.setControlStatus('❌ Save failed');
    }
};


VeraChat.prototype.closeMessageSidebar = function() {
    const sidebar = document.querySelector('.message-sidebar');
    const backdrop = document.querySelector('.sidebar-backdrop');
    
    if (sidebar) {
        sidebar.classList.remove('active');
        setTimeout(() => sidebar.remove(), 300);
    }
    
    if (backdrop) {
        backdrop.classList.remove('active');
        setTimeout(() => backdrop.remove(), 300);
    }
};

VeraChat.prototype.toggleMessageMenu = async function(messageId) {
    // Check if sidebar already open for this message
    const existing = document.querySelector(`.message-sidebar[data-message-id="${messageId}"]`);
    if (existing) {
        this.closeMessageSidebar();
        return;
    }
    
    // Close any open sidebar
    this.closeMessageSidebar();
    
    const message = this.messages.find(m => m.id === messageId);
    if (!message) return;
    
    await this.ensureToolsLoaded();
    this.createMessageMenu(messageId, message);
};

VeraChat.prototype.openChatSettings = function() {
    // Remove existing settings
    document.querySelectorAll('.settings-panel').forEach(p => p.remove());
    
    const panel = document.createElement('div');
    panel.className = 'settings-panel';
    
    panel.innerHTML = `
        <div class="sidebar-backdrop active"></div>
        <div class="settings-sidebar active">
            <div class="sidebar-header">
                <h3>⚙️ Chat Settings</h3>
                <button class="sidebar-close">✕</button>
            </div>
            <div class="sidebar-content">
                <div class="settings-section">
                    <h4>Display</h4>
                    <label class="setting-item">
                        <span>Theme</span>
                        <select id="theme-select">
                            <option value="dark">Dark</option>
                            <option value="light">Light</option>
                            <option value="midnight">Midnight Blue</option>
                        </select>
                    </label>
                    <label class="setting-item">
                        <span>Font Size</span>
                        <select id="font-size-select">
                            <option value="small">Small</option>
                            <option value="medium" selected>Medium</option>
                            <option value="large">Large</option>
                        </select>
                    </label>
                </div>
                
                <div class="settings-section">
                    <h4>Canvas</h4>
                    <label class="setting-item">
                        <span>Auto-focus Canvas</span>
                        <input type="checkbox" id="canvas-auto-focus-setting" 
                               ${this.canvasAutoFocus ? 'checked' : ''}>
                    </label>
                </div>
                
                <div class="settings-section">
                    <h4>Audio</h4>
                    <label class="setting-item">
                        <span>Text-to-Speech</span>
                        <input type="checkbox" id="tts-setting" 
                               ${this.ttsEnabled ? 'checked' : ''}>
                    </label>
                    ${this.ttsEnabled ? `
                    <label class="setting-item">
                        <span>TTS Speed</span>
                        <input type="range" min="0.5" max="2" step="0.1" value="1" 
                               id="tts-speed-slider">
                    </label>
                    ` : ''}
                </div>
                
                <div class="settings-section">
                    <h4>Behavior</h4>
                    <label class="setting-item">
                        <span>Auto-scroll</span>
                        <input type="checkbox" id="auto-scroll-setting" checked>
                    </label>
                    <label class="setting-item">
                        <span>Enter to Send</span>
                        <input type="checkbox" id="enter-to-send-setting" checked>
                    </label>
                </div>
                
                <div class="settings-section">
                    <h4>Data</h4>
                    <button class="settings-action-btn" id="clear-all-data-btn">
                        🗑️ Clear All Chats
                    </button>
                    <button class="settings-action-btn" id="export-all-data-btn">
                        💾 Export All Data
                    </button>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(panel);
    
    // CRITICAL FIX: Stop ALL propagation at the sidebar level
    const sidebar = panel.querySelector('.settings-sidebar');
    sidebar.addEventListener('click', (e) => {
        e.stopPropagation();
    });
    
    // Backdrop closes on click
    const backdrop = panel.querySelector('.sidebar-backdrop');
    backdrop.addEventListener('click', () => {
        this.closeSettings();
    });
    
    // Close button
    panel.querySelector('.sidebar-close').addEventListener('click', () => {
        this.closeSettings();
    });
    
    // Wire up event handlers (removed inline handlers)
    const themeSelect = document.getElementById('theme-select');
    if (themeSelect) {
        themeSelect.value = localStorage.getItem('chat-theme') || 'dark';
        themeSelect.addEventListener('change', (e) => this.changeTheme(e.target.value));
    }
    
    const fontSelect = document.getElementById('font-size-select');
    if (fontSelect) {
        fontSelect.addEventListener('change', (e) => this.changeFontSize(e.target.value));
    }
    
    const canvasAutoFocus = document.getElementById('canvas-auto-focus-setting');
    if (canvasAutoFocus) {
        canvasAutoFocus.addEventListener('change', () => this.toggleCanvasFocus());
    }
    
    const ttsToggle = document.getElementById('tts-setting');
    if (ttsToggle) {
        ttsToggle.addEventListener('change', () => this.toggleTTS());
    }
    
    const ttsSpeed = document.getElementById('tts-speed-slider');
    if (ttsSpeed) {
        ttsSpeed.addEventListener('input', (e) => this.setTTSSpeed(e.target.value));
    }
    
    const autoScroll = document.getElementById('auto-scroll-setting');
    if (autoScroll) {
        autoScroll.addEventListener('change', (e) => this.toggleAutoScroll(e.target.checked));
    }
    
    const enterToSend = document.getElementById('enter-to-send-setting');
    if (enterToSend) {
        enterToSend.addEventListener('change', (e) => this.toggleEnterToSend(e.target.checked));
    }
    
    const clearDataBtn = document.getElementById('clear-all-data-btn');
    if (clearDataBtn) {
        clearDataBtn.addEventListener('click', () => this.clearAllData());
    }
    
    const exportDataBtn = document.getElementById('export-all-data-btn');
    if (exportDataBtn) {
        exportDataBtn.addEventListener('click', () => this.exportAllData());
    }
};

VeraChat.prototype.closeSettings = function() {
    document.querySelectorAll('.settings-panel').forEach(p => {
        p.querySelector('.settings-sidebar')?.classList.remove('active');
        p.querySelector('.sidebar-backdrop')?.classList.remove('active');
        setTimeout(() => p.remove(), 300);
    });
};


VeraChat.prototype.openChatHistory = async function() {
    document.querySelectorAll('.history-panel').forEach(p => p.remove());
    
    const panel = document.createElement('div');
    panel.className = 'history-panel';
    
    panel.innerHTML = `
        <div class="sidebar-backdrop active"></div>
        <div class="history-sidebar active">
            <div class="sidebar-header">
                <h3>📜 Chat History</h3>
                <button class="sidebar-close">✕</button>
            </div>
            <div class="sidebar-content">
                <div class="history-search">
                    <input type="text" placeholder="Search sessions..." 
                           id="history-search-input">
                </div>
                <div class="history-list" id="history-list">
                    <div class="loading-spinner">Loading sessions...</div>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(panel);
    
    // CRITICAL FIX: Stop ALL propagation at the sidebar level
    const sidebar = panel.querySelector('.history-sidebar');
    sidebar.addEventListener('click', (e) => {
        e.stopPropagation();
    });
    
    // Backdrop closes on click
    const backdrop = panel.querySelector('.sidebar-backdrop');
    backdrop.addEventListener('click', () => {
        this.closeHistory();
    });
    
    // Close button
    panel.querySelector('.sidebar-close').addEventListener('click', () => {
        this.closeHistory();
    });
    
    // Wire up search
    const searchInput = document.getElementById('history-search-input');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => this.filterHistory(e.target.value));
    }
    
    this.loadChatSessions();
};

// Updated loadChatSessions to use proper event listeners
VeraChat.prototype.loadChatSessions = async function() {
    try {
        const response = await fetch('http://llm.int:8888/api/sessions');
        const data = await response.json();
        
        const historyList = document.getElementById('history-list');
        if (!historyList) return;
        
        if (!data.sessions || data.sessions.length === 0) {
            historyList.innerHTML = '<div class="no-history">No previous sessions</div>';
            return;
        }
        
        historyList.innerHTML = '';
        
        data.sessions.forEach(session => {
            const item = document.createElement('div');
            item.className = 'history-item';
            item.dataset.sessionId = session.id;
            
            item.innerHTML = `
                <div class="history-item-header">
                    <span class="history-title">${this.escapeHtml(session.title || 'Untitled Chat')}</span>
                    <span class="history-date">${this.formatTimestamp(session.created_at)}</span>
                </div>
                <div class="history-item-preview">${this.escapeHtml(session.preview || '')}</div>
                <div class="history-item-actions">
                    <button class="history-load-btn" title="Load">📂</button>
                    <button class="history-delete-btn" title="Delete">🗑️</button>
                </div>
            `;
            
            // Wire up buttons with proper event listeners
            const loadBtn = item.querySelector('.history-load-btn');
            loadBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.loadSession(session.id);
            });
            
            const deleteBtn = item.querySelector('.history-delete-btn');
            deleteBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.deleteSession(session.id);
            });
            
            historyList.appendChild(item);
        });
        
    } catch (error) {
        console.error('Failed to load sessions:', error);
        const historyList = document.getElementById('history-list');
        if (historyList) {
            historyList.innerHTML = '<div class="error-message">Failed to load history</div>';
        }
    }
};

VeraChat.prototype.filterHistory = function(query) {
    const items = document.querySelectorAll('.history-item');
    const lowerQuery = query.toLowerCase();
    
    items.forEach(item => {
        const title = item.querySelector('.history-title').textContent.toLowerCase();
        const preview = item.querySelector('.history-item-preview').textContent.toLowerCase();
        item.style.display = (title.includes(lowerQuery) || preview.includes(lowerQuery)) ? '' : 'none';
    });
};

VeraChat.prototype.closeHistory = function() {
    document.querySelectorAll('.history-panel').forEach(p => {
        p.querySelector('.history-sidebar')?.classList.remove('active');
        p.querySelector('.sidebar-backdrop')?.classList.remove('active');
        setTimeout(() => p.remove(), 300);
    });
};

// Additional helper functions for settings
VeraChat.prototype.changeTheme = function(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('chat-theme', theme);
};

VeraChat.prototype.changeFontSize = function(size) {
    document.documentElement.setAttribute('data-font-size', size);
    localStorage.setItem('chat-font-size', size);
};

VeraChat.prototype.setTTSSpeed = function(speed) {
    this.ttsSpeed = parseFloat(speed);
    localStorage.setItem('tts-speed', speed);
};

VeraChat.prototype.toggleAutoScroll = function(enabled) {
    this.autoScroll = enabled;
    localStorage.setItem('auto-scroll', enabled);
};

VeraChat.prototype.toggleEnterToSend = function(enabled) {
    this.enterToSend = enabled;
    localStorage.setItem('enter-to-send', enabled);
};

VeraChat.prototype.clearAllData = function() {
    if (!confirm('This will delete ALL chat history. Are you sure?')) return;
    
    this.messages = [];
    document.getElementById('chatMessages').innerHTML = '';
    localStorage.clear();
    this.closeSettings();
    this.addSystemMessage('All data cleared');
};

VeraChat.prototype.exportAllData = function() {
    const data = {
        messages: this.messages,
        settings: {
            theme: localStorage.getItem('chat-theme'),
            fontSize: localStorage.getItem('chat-font-size'),
            canvasAutoFocus: this.canvasAutoFocus,
            ttsEnabled: this.ttsEnabled
        },
        export_date: new Date().toISOString()
    };
    
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `vera_chat_export_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
};

// =====================================================================
// UPDATED CSS
// =====================================================================

const updatedStyles = `
/* Sliding Sidebar Menu */
.message-sidebar {
    position: fixed;
    left: -350px;
    top: 0;
    width: 350px;
    height: 100vh;
    background: var(--panel-bg, #1e293b);
    border-right: 1px solid var(--border, #334155);
    box-shadow: 2px 0 20px rgba(0, 0, 0, 0.3);
    z-index: 10001;
    transition: left 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    display: flex;
    flex-direction: column;
}

.message-sidebar.active {
    left: 0;
}

.sidebar-backdrop {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    background: rgba(0, 0, 0, 0);
    z-index: 10000;
    transition: background 0.3s ease;
    pointer-events: none;
}

.sidebar-backdrop.active {
    background: rgba(0, 0, 0, 0.5);
    pointer-events: all;
}

.sidebar-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 20px;
    border-bottom: 1px solid var(--border, #334155);
    background: var(--bg, #0f172a);
}

.sidebar-header h3 {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
    color: var(--text, #e2e8f0);
}

.sidebar-close {
    background: transparent;
    border: none;
    color: var(--text-muted, #94a3b8);
    cursor: pointer;
    font-size: 20px;
    padding: 4px 8px;
    border-radius: 4px;
    transition: all 0.2s;
}

.sidebar-close:hover {
    background: var(--panel-bg, #1e293b);
    color: var(--text, #e2e8f0);
}

.sidebar-content {
    flex: 1;
    overflow-y: auto;
    padding: 12px;
}

.menu-section {
    margin-bottom: 16px;
}

.menu-section-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    background: var(--bg, #0f172a);
    border-radius: 6px;
    margin-bottom: 8px;
}

.menu-section-icon {
    font-size: 16px;
}

.menu-section-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--text, #e2e8f0);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.menu-items {
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.menu-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 12px;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    color: var(--text, #e2e8f0);
    cursor: pointer;
    transition: all 0.2s;
    font-size: 13px;
    text-align: left;
}

.menu-item:hover {
    background: var(--bg, #0f172a);
    border-color: var(--border, #334155);
}

.menu-item.danger {
    color: #ef4444;
}

.menu-item.danger:hover {
    background: rgba(239, 68, 68, 0.1);
    border-color: #ef4444;
}

.menu-item-icon {
    font-size: 16px;
    flex-shrink: 0;
}

.menu-item-label {
    flex: 1;
}

/* Settings & History Panels */
.settings-panel, .history-sidebar {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    z-index: 100000;
    pointer-events: none;
}

.settings-panel > *, .history-panel > * {
    pointer-events: all;
}

.settings-sidebar, .history-sidebar {
    position: fixed;
    right: -400px;
    top: 0;
    width: 400px;
    height: 100vh;
    background: var(--panel-bg, #1e293b);
    border-left: 1px solid var(--border, #334155);
    box-shadow: -2px 0 20px rgba(0, 0, 0, 0.3);
    transition: right 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    display: flex;
    flex-direction: column;
}

.settings-sidebar.active, .history-sidebar.active {
    right: 0;
}

.settings-section {
    margin-bottom: 24px;
    padding: 16px;
    background: var(--bg, #0f172a);
    border-radius: 8px;
}

.settings-section h4 {
    margin: 0 0 12px 0;
    font-size: 13px;
    font-weight: 600;
    color: var(--text-muted, #94a3b8);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.setting-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 0;
    border-bottom: 1px solid var(--border, #334155);
    cursor: pointer;
}

.setting-item:last-child {
    border-bottom: none;
}

.setting-item span {
    font-size: 14px;
    color: var(--text, #e2e8f0);
}

.setting-item select, .setting-item input[type="range"] {
    background: var(--panel-bg, #1e293b);
    border: 1px solid var(--border, #334155);
    color: var(--text, #e2e8f0);
    padding: 6px 10px;
    border-radius: 4px;
    font-size: 13px;
}

.setting-item input[type="checkbox"] {
    width: 40px;
    height: 20px;
    cursor: pointer;
}

.settings-action-btn {
    width: 100%;
    padding: 10px;
    margin-top: 8px;
    background: var(--panel-bg, #1e293b);
    border: 1px solid var(--border, #334155);
    color: var(--text, #e2e8f0);
    border-radius: 6px;
    cursor: pointer;
    font-size: 13px;
    transition: all 0.2s;
}

.settings-action-btn:hover {
    background: var(--bg, #0f172a);
    border-color: var(--accent, #3b82f6);
}

/* History Styles */
.history-search {
    padding: 12px;
    border-bottom: 1px solid var(--border, #334155);
}

.history-search input {
    width: 100%;
    padding: 10px 12px;
    background: var(--bg, #0f172a);
    border: 1px solid var(--border, #334155);
    border-radius: 6px;
    color: var(--text, #e2e8f0);
    font-size: 13px;
}

.history-list {
    padding: 12px;
}

.history-item {
    padding: 12px;
    background: var(--bg, #0f172a);
    border: 1px solid var(--border, #334155);
    border-radius: 8px;
    margin-bottom: 8px;
    cursor: pointer;
    transition: all 0.2s;
}

.history-item:hover {
    border-color: var(--accent, #3b82f6);
    background: var(--panel-bg, #1e293b);
}

.history-item-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 6px;
}

.history-title {
    font-weight: 600;
    color: var(--text, #e2e8f0);
    font-size: 14px;
}

.history-date {
    font-size: 11px;
    color: var(--text-muted, #94a3b8);
}

.history-item-preview {
    font-size: 12px;
    color: var(--text-muted, #94a3b8);
    margin-bottom: 8px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.history-item-actions {
    display: flex;
    gap: 6px;
}

.history-item-actions button {
    padding: 4px 8px;
    background: var(--panel-bg, #1e293b);
    border: 1px solid var(--border, #334155);
    border-radius
      cursor: pointer;
    font-size: 14px;
    transition: all 0.2s;
}

.history-item-actions button:hover {
    border-color: var(--accent, #3b82f6);
}

.loading-spinner, .no-history, .error-message {
    padding: 40px 20px;
    text-align: center;
    color: var(--text-muted, #94a3b8);
    font-size: 14px;
}

/* Fixed Search Highlighting */
.search-highlight {
    background: rgba(251, 191, 36, 0.3);
    color: var(--text, #e2e8f0);
    padding: 2px 4px;
    border-radius: 2px;
    font-weight: 500;
    box-shadow: 0 0 0 1px rgba(251, 191, 36, 0.5);
}

/* Remove old menu styles */
.message-menu {
    display: none !important;
}
`;

// Inject updated styles
if (!document.getElementById('updated-sidebar-styles')) {
    const style = document.createElement('style');
    style.id = 'updated-sidebar-styles';
    style.textContent = updatedStyles;
    document.head.appendChild(style);
}

console.log('✅ Updated with sliding sidebar, fixed search, and real settings/history');
    
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
    
    VeraChat.prototype.execute_code = function(button) {
        // const block = button.closest('.enhanced-code-block');
        // const code = block.querySelector('code').textContent;
        
        // navigator.clipboard.writeText(code).then(() => {
        //     button.textContent = '✅';
        //     setTimeout(() => button.textContent = '📋', 2000);
        // });
    };
    // FIXED: Canvas button now properly extracts code from data attributes
    VeraChat.prototype.showCanvasModeSelector = function(button) {
        console.log('🎨 Direct send to canvas (no popup)');
        
        const block = button.closest('.enhanced-code-block');
        if (!block) {
            console.error('❌ Could not find code block');
            return;
        }
        
        const code = block.dataset.codeContent || block.querySelector('code').textContent;
        const language = block.dataset.codeLang || block.querySelector('.code-language').textContent.toLowerCase();
        
        console.log(`📝 Code extracted: lang=${language}, length=${code.length}`);
        
        // Determine best mode automatically
        const mode = this.getCanvasModeForLanguage(language);
        console.log(`🎯 Auto-selected mode: ${mode}`);
        
        // Send directly to canvas
        this.sendDirectlyToCanvas(mode, code, language);
    };
    VeraChat.prototype.sendDirectlyToCanvas = function(mode, code, language) {
    console.log(`🚀 sendDirectlyToCanvas: mode=${mode}, lang=${language}`);
    
    const canvasTab = this.tabs ? this.tabs.find(t => t.id === 'canvas') : null;
    if (!canvasTab) {
        console.error('❌ Canvas tab not found');
        this.setControlStatus('❌ Canvas not available');
        return;
    }
    
    this.setControlStatus(`🎨 Opening in ${mode} mode...`);
    
    console.log('📍 Activating canvas tab');
    this.activateTab('canvas', canvasTab.columnId);
    
    setTimeout(() => {
        console.log(`🔧 Switching to ${mode} mode and loading content`);
        
        // Switch mode
        if (typeof this.switchCanvasMode === 'function') {
            this.switchCanvasMode(mode);
        }
        
        const modeSelector = document.querySelector('#canvasMode');
        if (modeSelector) modeSelector.value = mode;
        
        // Load content
        if (typeof this.loadIntoCanvas === 'function') {
            this.loadIntoCanvas(language, code);
        } else {
            console.error('❌ loadIntoCanvas function not found');
        }
        
        this.setControlStatus(`✅ Loaded in ${mode} mode`);
        console.log('✅ Code loaded into canvas');
    }, 100);
};

    // VeraChat.prototype.sendCodeToCanvas = function(mode, button) {
    //     console.log(`🚀 sendCodeToCanvas: mode=${mode}`);
        
    //     const code = button.dataset.codeContent;
    //     const language = button.dataset.codeLanguage;
        
    //     if (!code) {
    //         console.error('❌ No code found in button dataset');
    //         return;
    //     }
        
    //     console.log(`📝 Code: lang=${language}, length=${code.length}`);
        
    //     const canvasTab = this.tabs ? this.tabs.find(t => t.id === 'canvas') : null;
    //     if (!canvasTab) {
    //         console.error('❌ Canvas tab not found');
    //         return;
    //     }
        
    //     console.log('📍 Activating canvas tab');
    //     this.activateTab('canvas', canvasTab.columnId);
        
    //     setTimeout(() => {
    //         console.log(`🔧 Switching to ${mode} mode and loading content`);
            
    //         if (typeof this.switchCanvasMode === 'function') {
    //             this.switchCanvasMode(mode);
    //         }
    //         const modeSelector = document.querySelector('#canvasMode');
    //         if (modeSelector) modeSelector.value = mode;
            
    //         if (typeof this.loadIntoCanvas === 'function') {
    //             this.loadIntoCanvas(language, code);
    //         } else {
    //             console.error('❌ loadIntoCanvas function not found');
    //         }
            
    //         console.log('✅ Code loaded into canvas');
    //     }, 100);
        
    //     document.querySelectorAll('.canvas-mode-popup').forEach(p => p.remove());
    // };
    
    VeraChat.prototype.formatTimestamp = function(timestamp) {
        // Handle both Date objects and timestamp numbers
        const date = timestamp instanceof Date ? timestamp : new Date(timestamp);
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
    
    VeraChat.prototype.extractThoughts = function(content) {
        const thoughts = [];
        let cleanContent = content;
        let isThinking = false;
        
        // Count tags
        const openCount = (content.match(/<thought>/g) || []).length;
        const closeCount = (content.match(/<\/thought>/g) || []).length;
        
        // If we have more open than close, we're still thinking
        isThinking = openCount > closeCount;
        
        // Extract all complete thought blocks
        const thoughtRegex = /<thought>([\s\S]*?)<\/thought>/g;
        let match;
        
        while ((match = thoughtRegex.exec(content)) !== null) {
            thoughts.push(match[1].trim());
        }
        
        // If thinking, also get the incomplete thought
        if (isThinking) {
            const lastOpenIndex = content.lastIndexOf('<thought>');
            if (lastOpenIndex !== -1) {
                const afterLastOpen = content.substring(lastOpenIndex + 9); // 9 = length of '<thought>'
                // Check if this content hasn't been captured in a complete block
                const incompleteThought = afterLastOpen.split('</thought>')[0].trim();
                if (incompleteThought && !thoughts.some(t => t.includes(incompleteThought))) {
                    thoughts.push(incompleteThought);
                }
            }
        }
        
        // Remove ALL thought tags from content (including malformed ones)
        cleanContent = content
            .replace(/<thought>/g, '')
            .replace(/<\/thought>/g, '')
            .trim();
        
        return { thoughts, cleanContent, isThinking };
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

// ADD: CSS Styles for thought container
const thoughtStyles = `
/* Thought Container */
.thought-container {
    background: linear-gradient(135deg, rgba(139, 92, 246, 0.1) 0%, rgba(59, 130, 246, 0.1) 100%);
    border: 1px solid rgba(139, 92, 246, 0.3);
    border-radius: 8px;
    padding: 12px;
    margin-bottom: 12px;
    font-size: 13px;
    animation: thoughtFadeIn 0.3s ease-out;
}

.thought-container.complete {
    background: linear-gradient(135deg, rgba(139, 92, 246, 0.05) 0%, rgba(59, 130, 246, 0.05) 100%);
    border-color: rgba(139, 92, 246, 0.2);
}

.thought-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
    padding-bottom: 8px;
    border-bottom: 1px solid rgba(139, 92, 246, 0.2);
}

.thought-icon {
    font-size: 16px;
    animation: thoughtPulse 2s ease-in-out infinite;
}

.thought-container.complete .thought-icon {
    animation: none;
    color: #8b5cf6;
}

.thought-label {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #a78bfa;
}

.thought-content {
    color: var(--text-muted, #94a3b8);
    line-height: 1.6;
    font-family: 'Segoe UI', system-ui, sans-serif;
    white-space: pre-wrap;
    word-wrap: break-word;
}

@keyframes thoughtFadeIn {
    from {
        opacity: 0;
        transform: translateY(-10px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

@keyframes thoughtPulse {
    0%, 100% {
        opacity: 1;
        transform: scale(1);
    }
    50% {
        opacity: 0.6;
        transform: scale(1.1);
    }
}

/* Ensure thought container appears above other content */
.message-content {
    display: flex;
    flex-direction: column;
}

.thought-container + .message-rendered {
    margin-top: 8px;
}
`;

// Inject thought styles
if (!document.getElementById('thought-container-styles')) {
    const style = document.createElement('style');
    style.id = 'thought-container-styles';
    style.textContent = thoughtStyles;
    document.head.appendChild(style);
}

})();
