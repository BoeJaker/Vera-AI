/**
 * VeraChat Startup Loader
 * Shows full-page GraphLoader animation during initial connection
 */

(() => {
    // Create and show the startup overlay immediately
    function createStartupOverlay() {
        // Create overlay container
        const overlay = document.createElement('div');
        overlay.id = 'vera-startup-overlay';
        overlay.innerHTML = `
            <style>
                #vera-startup-overlay {
                    position: fixed;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    background: var(--bg, #0f172a);
                    z-index: 100000;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    transition: opacity 0.5s ease, visibility 0.5s ease;
                }
                
                #vera-startup-overlay.hidden {
                    opacity: 0;
                    visibility: hidden;
                    pointer-events: none;
                }
                
                #vera-startup-overlay .startup-content {
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    gap: 20px;
                }
                
                #vera-startup-overlay .startup-title {
                    font-size: 28px;
                    font-weight: 300;
                    color: var(--text, #e2e8f0);
                    letter-spacing: 4px;
                    text-transform: uppercase;
                    margin-bottom: 10px;
                    opacity: 0;
                    animation: fadeInTitle 1s ease 0.5s forwards;
                }
                
                #vera-startup-overlay .startup-subtitle {
                    font-size: 12px;
                    color: var(--text, #94a3b8);
                    opacity: 0.6;
                    letter-spacing: 2px;
                    margin-top: -10px;
                }
                
                @keyframes fadeInTitle {
                    to { opacity: 1; }
                }
                
                #vera-startup-loader {
                    width: 350px;
                    height: 350px;
                }
            </style>
            
            <div class="startup-content">
                <div class="startup-title">Vera</div>
                <div class="startup-subtitle">Knowledge Assistant</div>
                <div id="vera-startup-loader"></div>
            </div>
        `;
        
        document.body.appendChild(overlay);
        
        // Initialize GraphLoader in the startup container
        if (typeof GraphLoader !== 'undefined') {
            window.startupLoader = new GraphLoader('#vera-startup-loader', {
                nodeCount: 16,
                baseRadius: 100,
                rotationSpeed: 0.003,
                text: 'Connecting',
                introDuration: 2.5,
                width: 350,
                height: 350,
                showProgress: true
            });
            window.startupLoader.show('Connecting');
        } else {
            console.warn('GraphLoader not found - showing basic loading');
            document.getElementById('vera-startup-loader').innerHTML = `
                <div style="text-align: center; color: var(--text, #94a3b8);">
                    <div style="font-size: 24px; margin-bottom: 16px;">⟳</div>
                    <div>Connecting...</div>
                </div>
            `;
        }
        
        return overlay;
    }
    
    // Update the startup loader text
    window.updateStartupStatus = function(message) {
        if (window.startupLoader) {
            window.startupLoader.setText(message);
        }
    };
    
    // Hide the startup overlay with smooth transition
    window.hideStartupOverlay = function() {
        const overlay = document.getElementById('vera-startup-overlay');
        if (overlay) {
            // Fade out
            overlay.classList.add('hidden');
            
            // Remove from DOM after transition
            setTimeout(() => {
                if (window.startupLoader) {
                    window.startupLoader.destroy();
                    window.startupLoader = null;
                }
                overlay.remove();
            }, 500);
        }
    };
    
    // Check if startup should be shown (not already connected)
    window.showStartupOverlay = function() {
        if (!document.getElementById('vera-startup-overlay')) {
            createStartupOverlay();
        }
    };
    
    // Auto-create on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', createStartupOverlay);
    } else {
        createStartupOverlay();
    }
})();