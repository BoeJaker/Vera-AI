// =====================================================================
// GraphChatIntegration - Initialization and Wiring
// =====================================================================
// This script wires GraphChatIntegration into the existing VeraChat system
// =====================================================================

(function() {
    'use strict';
    
    console.log('🔌 Initializing GraphChatIntegration wiring...');
    
    // Wait for both VeraChat and network to be ready
    const initIntegration = () => {
        if (typeof VeraChat === 'undefined') {
            console.log('⏳ Waiting for VeraChat...');
            setTimeout(initIntegration, 500);
            return;
        }
        
        if (typeof network === 'undefined' || !network.body) {
            console.log('⏳ Waiting for network...');
            setTimeout(initIntegration, 500);
            return;
        }
        
        if (typeof window.GraphChatIntegration === 'undefined') {
            console.log('❌ GraphChatIntegration module not loaded!');
            return;
        }
        
        console.log('✅ All dependencies ready, initializing integration');
        
        // Initialize the integration
        window.GraphChatIntegration.init(app, network);
        
        // Hook into VeraChat's sendMessage to auto-append context
        wireMessageIntercept();
        
        // Add keyboard shortcut for toggling context
        addKeyboardShortcuts();
        
        console.log('✅ GraphChatIntegration fully wired');
    };
    
    // ================================================================
    // Message Intercept
    // ================================================================
    
    const wireMessageIntercept = () => {
        if (!VeraChat.prototype._originalSendMessage) {
            console.log('💾 Backing up original sendMessage');
            VeraChat.prototype._originalSendMessage = VeraChat.prototype.sendMessage;
        }
        
        VeraChat.prototype.sendMessage = async function() {
            const input = document.getElementById('messageInput');
            let message = input.value.trim();
            
            if (!message || this.processing) return;
            
            // Check if user wants to include graph context
            const shouldIncludeContext = window.GraphChatIntegration.contextMode !== 'none';
            
            if (shouldIncludeContext) {
                const contextData = window.GraphChatIntegration.getContextData();
                
                if (contextData && contextData.nodes.length > 0) {
                    // Show context indicator
                    const contextIndicator = document.createElement('div');
                    contextIndicator.className = 'context-indicator';
                    contextIndicator.style.cssText = `
                        position: fixed;
                        bottom: 80px;
                        left: 50%;
                        transform: translateX(-50%);
                        background: rgba(59, 130, 246, 0.95);
                        color: white;
                        padding: 8px 16px;
                        border-radius: 20px;
                        font-size: 12px;
                        font-weight: 600;
                        z-index: 10000;
                        animation: slideInUp 0.3s ease;
                        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
                    `;
                    contextIndicator.innerHTML = `
                        📊 Including ${contextData.nodes.length} node${contextData.nodes.length !== 1 ? 's' : ''} 
                        from graph (${window.GraphChatIntegration.contextMode} mode)
                    `;
                    document.body.appendChild(contextIndicator);
                    
                    setTimeout(() => {
                        contextIndicator.style.animation = 'slideOutDown 0.3s ease';
                        setTimeout(() => contextIndicator.remove(), 300);
                    }, 2000);
                    
                    // Append context to message
                    const contextText = window.GraphChatIntegration.formatContextAsText(contextData);
                    message = message + '\n\n---\n' + contextText;
                    
                    // Temporarily set input value (will be cleared after send)
                    input.value = message;
                }
            }
            
            // Call original sendMessage
            return this._originalSendMessage.call(this);
        };
        
        console.log('✅ Message intercept installed');
    };
    
    // ================================================================
    // Keyboard Shortcuts
    // ================================================================
    
    const addKeyboardShortcuts = () => {
        document.addEventListener('keydown', (e) => {
            // Ctrl/Cmd + G = Toggle graph context panel
            if ((e.ctrlKey || e.metaKey) && e.key === 'g') {
                e.preventDefault();
                window.GraphChatIntegration.toggleContextPanel();
            }
            
            // Ctrl/Cmd + Shift + S = Quick summarize selected
            if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'S') {
                e.preventDefault();
                window.GraphChatIntegration.insertGraphQuery('summarize');
            }
            
            // Ctrl/Cmd + Shift + A = Quick analyze relationships
            if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'A') {
                e.preventDefault();
                window.GraphChatIntegration.insertGraphQuery('analyze');
            }
            
            // Ctrl/Cmd + Shift + P = Preview context
            if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'P') {
                e.preventDefault();
                window.GraphChatIntegration.previewContext();
            }
        });
        
        console.log('✅ Keyboard shortcuts added');
        console.log('   Ctrl/Cmd + G: Toggle context panel');
        console.log('   Ctrl/Cmd + Shift + S: Quick summarize');
        console.log('   Ctrl/Cmd + Shift + A: Quick analyze');
        console.log('   Ctrl/Cmd + Shift + P: Preview context');
    };
    
    // ================================================================
    // Additional CSS Animations
    // ================================================================
    
    const addAnimations = () => {
        const style = document.createElement('style');
        style.textContent = `
            @keyframes slideInUp {
                from { transform: translate(-50%, 100px); opacity: 0; }
                to { transform: translate(-50%, 0); opacity: 1; }
            }
            
            @keyframes slideOutDown {
                from { transform: translate(-50%, 0); opacity: 1; }
                to { transform: translate(-50%, 100px); opacity: 0; }
            }
            
            .context-indicator {
                display: flex;
                align-items: center;
                gap: 8px;
            }
        `;
        document.head.appendChild(style);
    };
    
    addAnimations();
    
    // ================================================================
    // Helper: Add context toggle to message input area
    // ================================================================
    
    const addContextToggleToInput = () => {
        setTimeout(() => {
            const chatSection = document.getElementById('chat-section');
            if (!chatSection) return;
            
            const inputArea = chatSection.querySelector('.input-area') || 
                             chatSection.querySelector('[style*="display: flex"]');
            
            if (!inputArea) return;
            
            // Add quick toggle button next to send button
            const toggleBtn = document.createElement('button');
            toggleBtn.id = 'quick-context-toggle';
            toggleBtn.className = 'quick-context-toggle';
            toggleBtn.title = 'Toggle graph context (Ctrl+G)';
            toggleBtn.innerHTML = `
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="2"/>
                    <circle cx="12" cy="5" r="2"/>
                    <circle cx="19" cy="12" r="2"/>
                    <circle cx="5" cy="12" r="2"/>
                    <path d="M12 7v3m0 4v3m-5-5h3m4 0h3"/>
                </svg>
            `;
            toggleBtn.style.cssText = `
                padding: 10px;
                background: var(--panel-bg, #1e293b);
                border: 1px solid var(--border, #334155);
                border-radius: 6px;
                color: var(--text-muted, #94a3b8);
                cursor: pointer;
                transition: all 0.2s;
                display: flex;
                align-items: center;
                justify-content: center;
            `;
            
            toggleBtn.onclick = () => {
                window.GraphChatIntegration.toggleContextPanel();
                updateToggleButton();
            };
            
            const updateToggleButton = () => {
                const panel = document.getElementById('graph-context-panel');
                const isExpanded = panel && !panel.classList.contains('collapsed');
                const mode = window.GraphChatIntegration.contextMode;
                
                if (mode !== 'none' && isExpanded) {
                    toggleBtn.style.background = 'var(--accent, #3b82f6)';
                    toggleBtn.style.borderColor = 'var(--accent, #3b82f6)';
                    toggleBtn.style.color = 'white';
                } else {
                    toggleBtn.style.background = 'var(--panel-bg, #1e293b)';
                    toggleBtn.style.borderColor = 'var(--border, #334155)';
                    toggleBtn.style.color = 'var(--text-muted, #94a3b8)';
                }
            };
            
            // Insert before send button
            const sendBtn = document.getElementById('sendBtn');
            if (sendBtn && sendBtn.parentElement === inputArea) {
                inputArea.insertBefore(toggleBtn, sendBtn);
            } else {
                inputArea.appendChild(toggleBtn);
            }
            
            console.log('✅ Quick context toggle added to input area');
            
            // Update button state periodically
            setInterval(updateToggleButton, 1000);
        }, 1000);
    };
    
    // Start initialization
    initIntegration();
    addContextToggleToInput();
    
    console.log('🚀 GraphChatIntegration wiring complete');
    
})();