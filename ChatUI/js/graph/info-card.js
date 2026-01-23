/**
 * GraphInfoCard Module - THEME COMPATIBLE
 * Displays node/edge information in a stationary card instead of tooltips
 * Card expands on click to show full details
 * Includes fixed hover preview at bottom and inline action panels
 * Width scales with graph container (compact: 17%, expanded: 32%)
 */

(function() {
    'use strict';
    
    window.GraphInfoCard = {
        
        // Store references
        graphAddon: null,
        cardElement: null,
        hoverPreviewElement: null,
        currentNodeId: null,
        currentEdgeId: null,
        hideTimeout: null,
        isExpanded: false,
        inlineMode: false, // When showing inline dialogs
        
        // Dynamic sizing
        graphContainer: null,
        resizeObserver: null,
        
        /**
         * Initialize the module
         */
        init: function(graphAddon) {
            console.log('GraphInfoCard.init called');
            this.graphAddon = graphAddon;
            
            // Get graph container reference
            this.graphContainer = document.getElementById('graph');
            
            // Create card element
            this.createCard();
            
            // Disable vis.js tooltips
            this.disableTooltips();
            
            // Wait for network
            this.waitForNetwork();
            
            // Setup resize observer for dynamic width
            this.setupResizeObserver();
            
            // Setup keyboard listeners
            this.setupKeyboardListeners();
            
            console.log('GraphInfoCard initialized');
        },
        
        /**
         * Setup keyboard event listeners
         */
        setupKeyboardListeners: function() {
            const self = this;
            
            document.addEventListener('keydown', function(e) {
                // Escape key - close if expanded or in inline mode
                if (e.key === 'Escape' || e.keyCode === 27) {
                    if (self.isExpanded || self.inlineMode) {
                        console.log('Escape pressed, collapsing card');
                        self.collapse();
                    }
                }
            });
        },
        
        /**
         * Setup resize observer for dynamic card sizing
         */
        setupResizeObserver: function() {
            if (!this.graphContainer) return;
            
            this.resizeObserver = new ResizeObserver(() => {
                this.updateCardWidth();
            });
            
            this.resizeObserver.observe(this.graphContainer);
            
            // Initial size update
            this.updateCardWidth();
        },
        
        /**
         * Update card width based on graph container size
         */
        updateCardWidth: function() {
            if (!this.cardElement || !this.graphContainer) return;
            
            const graphWidth = this.graphContainer.offsetWidth;
            
            if (this.isExpanded || this.inlineMode) {
                // Expanded: 32% of graph width, min 320px, max 600px
                const expandedWidth = Math.min(600, Math.max(320, graphWidth * 0.32));
                this.cardElement.style.width = expandedWidth + 'px';
                
                // Also update hover preview
                if (this.hoverPreviewElement) {
                    this.hoverPreviewElement.style.width = expandedWidth + 'px';
                }
            } else {
                // Compact: 17% of graph width, min 220px, max 340px
                const compactWidth = Math.min(340, Math.max(220, graphWidth * 0.17));
                this.cardElement.style.width = compactWidth + 'px';
            }
        },
        
        /**
         * Create the info card element - THEME COMPATIBLE
         */
        createCard: function() {
            // Remove existing card if any
            const existing = document.getElementById('graph-info-card-fixed');
            if (existing) {
                existing.remove();
            }
            
            if (!this.graphContainer) {
                console.error('Graph container not found');
                return;
            }
            
            // Ensure graph container has position relative for absolute positioning
            if (window.getComputedStyle(this.graphContainer).position === 'static') {
                this.graphContainer.style.position = 'relative';
            }
            
            // Create new card
            this.cardElement = document.createElement('div');
            this.cardElement.id = 'graph-info-card-fixed';
            this.cardElement.style.cssText = `
                position: absolute;
                bottom: 20px;
                right: 20px;
                width: 320px;
                max-height: 400px;
                background: var(--panel-bg);
                border: 1px solid var(--border);
                border-radius: 12px;
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
                z-index: 9999;
                display: none;
                overflow-y: auto;
                backdrop-filter: blur(10px);
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            `;
            
            // Create hover preview element (appears at bottom when expanded)
            this.hoverPreviewElement = document.createElement('div');
            this.hoverPreviewElement.id = 'graph-hover-preview';
            this.hoverPreviewElement.style.cssText = `
                position: absolute;
                bottom: 0;
                right: 20px;
                width: 520px;
                max-height: 180px;
                border: 1px solid var(--border);
                border-bottom: none;
                border-radius: 12px 12px 0 0;
                background: var(--panel-bg);
                box-shadow: 0 -4px 16px rgba(0, 0, 0, 0.3);
                z-index: 10000;
                display: none;
                overflow-y: auto;
                backdrop-filter: blur(10px);
                transform: translateY(100%);
                transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            `;
            
            // Append to graph container
            this.graphContainer.appendChild(this.cardElement);
            this.graphContainer.appendChild(this.hoverPreviewElement);
            
            console.log('Info card created and attached to graph container');
        },
        
        /**
         * Disable vis.js tooltips
         */
        disableTooltips: function() {
            if (typeof network !== 'undefined') {
                network.setOptions({
                    nodes: {
                        title: undefined
                    },
                    edges: {
                        title: undefined
                    },
                    interaction: {
                        tooltipDelay: 999999999,
                        hideEdgesOnDrag: false,
                        hideEdgesOnZoom: false
                    }
                });
                
                console.log('Tooltips disabled');
            }
        },
        
        /**
         * Wait for network to be ready
         */
        waitForNetwork: function() {
            if (typeof network !== 'undefined' && network.body && network.body.data) {
                this.setupEventListeners();
            } else {
                setTimeout(() => this.waitForNetwork(), 500);
            }
        },
        
        /**
         * Setup network event listeners
         */
        setupEventListeners: function() {
            const self = this;
            
            // Hover over node
            network.on("hoverNode", function(params) {
                if (!self.isExpanded) {
                    // Compact mode - show in main card
                    self.showNodeInfo(params.node);
                } else if (!self.inlineMode) {
                    // Expanded mode - show in bottom preview
                    self.showHoverPreview(params.node);
                }
            });
            
            // Hover over edge
            network.on("hoverEdge", function(params) {
                if (!self.isExpanded) {
                    self.showEdgeInfo(params.edge);
                }
            });
            
            // Mouse leaves canvas
            network.on("blurNode", function() {
                if (!self.isExpanded) {
                    self.scheduleHide();
                } else {
                    self.hideHoverPreview();
                }
            });
            
            network.on("blurEdge", function() {
                if (!self.isExpanded) {
                    self.scheduleHide();
                }
            });
            
            // Click on node - EXPAND THE CARD
            network.on("selectNode", function(params) {
                if (params.nodes.length > 0 && !self.inlineMode) {
                    const nodeId = params.nodes[0];
                    console.log('Node selected, checking if collapsed:', nodeId);
                    
                    // Check if this is a collapsed node
                    const node = network.body.data.nodes.get(nodeId);
                    if (node && node._isCollapsed && window.GraphAdvancedFilters) {
                        console.log('Collapsed node selected, showing expanded info');
                        const html = window.GraphAdvancedFilters.getExpandedCollapsedNodeInfo(nodeId, node);
                        self.isExpanded = true;
                        self.inlineMode = false;
                        self.currentNodeId = nodeId;
                        self.currentEdgeId = null;
                        self.updateCardWidth();
                        self.cardElement.style.position = 'absolute';
                        self.cardElement.style.maxHeight = '80vh';
                        self.cardElement.style.bottom = '20px';
                        self.cardElement.style.right = '20px';
                        self.cardElement.style.top = 'auto';
                        self.cardElement.style.transform = 'none';
                        self.cardElement.style.background = 'var(--panel-bg)';
                        self.cardElement.innerHTML = html;
                        self.show();
                    } else {
                        console.log('Regular node selected, expanding:', nodeId);
                        self.expandNodeInfo(nodeId);
                    }
                }
            });
            
            // Canvas click handler - improved for better collapse detection
            network.on("click", function(params) {
                console.log('Network click event:', {
                    nodes: params.nodes,
                    edges: params.edges,
                    pointer: params.pointer,
                    isExpanded: self.isExpanded,
                    inlineMode: self.inlineMode
                });
                
                if (params.nodes.length > 0 && !self.inlineMode) {
                    // Node clicked - expand it
                    console.log('Node clicked, expanding:', params.nodes[0]);
                    self.expandNodeInfo(params.nodes[0]);
                } else if (params.edges.length > 0 && !self.inlineMode) {
                    // Edge clicked - expand it
                    console.log('Edge clicked, expanding:', params.edges[0]);
                    self.expandEdgeInfo(params.edges[0]);
                } else if (params.nodes.length === 0 && params.edges.length === 0) {
                    // Canvas clicked (empty space) - collapse if expanded
                    console.log('Canvas (empty space) clicked');
                    if (self.isExpanded || self.inlineMode) {
                        console.log('Collapsing card due to canvas click');
                        self.collapse();
                    }
                }
            });
            
            // Keep card visible when hovering over it
            this.cardElement.addEventListener('mouseenter', () => {
                clearTimeout(self.hideTimeout);
            });
            
            this.cardElement.addEventListener('mouseleave', () => {
                if (!self.isExpanded) {
                    self.scheduleHide();
                }
            });
            
            // Prevent clicks inside the card from propagating to the network
            this.cardElement.addEventListener('click', (e) => {
                e.stopPropagation();
                
                // Don't expand if clicking a button, already expanded, or in inline mode
                if (e.target.tagName === 'BUTTON' || self.isExpanded || self.inlineMode) {
                    return;
                }
                
                if (self.currentNodeId) {
                    self.expandNodeInfo(self.currentNodeId);
                } else if (self.currentEdgeId) {
                    self.expandEdgeInfo(self.currentEdgeId);
                }
            });
            
            // Also prevent clicks on hover preview from propagating
            this.hoverPreviewElement.addEventListener('click', (e) => {
                e.stopPropagation();
            });
            
            console.log('Event listeners set up');
        },
        
        /**
         * Show node information (compact hover view) - THEME COMPATIBLE
         */
        showNodeInfo: function(nodeId) {
            clearTimeout(this.hideTimeout);
            
            this.currentNodeId = nodeId;
            this.currentEdgeId = null;
            
            if (!this.graphAddon || !this.graphAddon.nodesData) {
                return;
            }
            
            const nodeData = this.graphAddon.nodesData[nodeId];
            if (!nodeData) {
                return;
            }
            
            const displayName = nodeData.display_name || nodeId;
            const labels = nodeData.labels || [];
            const properties = nodeData.properties || {};
            
            // Get neighbor count
            let neighborCount = 0;
            try {
                neighborCount = network.getConnectedNodes(nodeId).length;
            } catch (e) {
                // Silent fail
            }
            
            // Build content
            let html = `
                <div style="padding: 16px;">
                    <!-- Header -->
                    <div style="margin-bottom: 12px;">
                        <div style="
                            color: var(--text); font-size: 15px; font-weight: 600;
                            margin-bottom: 6px; word-wrap: break-word;
                        ">${this.escapeHtml(displayName)}</div>
                        
                        <!-- Connection count and labels inline -->
                        <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                            <div style="color: var(--text-secondary); font-size: 11px;">
                                ${neighborCount} connection${neighborCount !== 1 ? 's' : ''}
                            </div>
                            ${labels.length > 0 ? `
                                <div style="display: flex; flex-wrap: wrap; gap: 4px;">
                                    ${labels.slice(0, 5).map(label => `
                                        <span style="
                                            display: inline-block; padding: 2px 6px;
                                            color: var(--accent); background: var(--accent-bg, rgba(96, 165, 250, 0.15));
                                            border: 1px solid var(--accent-border, rgba(96, 165, 250, 0.4));
                                            border-radius: 3px; font-size: 9px; font-weight: 600;
                                        ">${this.escapeHtml(String(label))}</span>
                                    `).join('')}
                                    ${labels.length > 5 ? `
                                        <span style="color: var(--text-secondary); font-size: 9px; padding: 2px 4px;">
                                            +${labels.length - 5}
                                        </span>
                                    ` : ''}
                                </div>
                            ` : ''}
                        </div>
                    </div>
            `;
            
            // Key properties - show first 3
            const importantProps = ['text', 'body', 'content', 'summary', 'description', 'type', 'status'];
            let propsShown = 0;
            
            html += '<div style="border-top: 1px solid var(--border); padding-top: 12px;">';
            
            for (const key of importantProps) {
                if (propsShown >= 3) break;
                
                if (properties[key]) {
                    let value = String(properties[key]);
                    
                    // Truncate long values
                    if (value.length > 100) {
                        value = value.substring(0, 100) + '...';
                    }
                    
                    html += `
                        <div style="margin-bottom: 8px;">
                            <div style="color: var(--text-secondary); font-size: 10px; font-weight: 600; margin-bottom: 2px; text-transform: uppercase; letter-spacing: 0.5px;">
                                ${this.escapeHtml(key)}
                            </div>
                            <div style="color: var(--text); font-size: 12px; line-height: 1.4; word-wrap: break-word;">
                                ${this.escapeHtml(value)}
                            </div>
                        </div>
                    `;
                    propsShown++;
                }
            }
            
            // If no important props, show first 3 of any properties
            if (propsShown === 0) {
                const allProps = Object.entries(properties).slice(0, 3);
                allProps.forEach(([key, value]) => {
                    let val = String(value);
                    if (val.length > 100) {
                        val = val.substring(0, 100) + '...';
                    }
                    
                    html += `
                        <div style="margin-bottom: 8px;">
                            <div style="color: var(--text-secondary); font-size: 10px; font-weight: 600; margin-bottom: 2px;">
                                ${this.escapeHtml(key)}
                            </div>
                            <div style="color: var(--text); font-size: 12px; line-height: 1.4; word-wrap: break-word;">
                                ${this.escapeHtml(val)}
                            </div>
                        </div>
                    `;
                });
            }
            
            html += '</div>';
            
            // Footer - click hint
            html += `
                <div style="
                    margin-top: 12px; padding-top: 12px;
                    border-top: 1px solid var(--border);
                    color: var(--text-secondary); font-size: 10px; text-align: center;
                    cursor: pointer;
                ">
                    Click for full details
                </div>
            `;
            
            html += '</div>';
            
            this.cardElement.innerHTML = html;
            this.show();
        },
        
        /**
         * Show hover preview at bottom (when expanded) - THEME COMPATIBLE
         */
        showHoverPreview: function(nodeId) {
            if (!this.graphAddon || !this.graphAddon.nodesData) {
                return;
            }
            
            const nodeData = this.graphAddon.nodesData[nodeId];
            if (!nodeData || nodeId === this.currentNodeId) {
                return; // Don't show preview for the currently expanded node
            }
            
            const displayName = nodeData.display_name || nodeId;
            const labels = nodeData.labels || [];
            const properties = nodeData.properties || {};
            
            let neighborCount = 0;
            try {
                neighborCount = network.getConnectedNodes(nodeId).length;
            } catch (e) {}
            
            let html = `
                <div style="padding: 12px; border-bottom: 1px solid var(--border);">
                    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                        <div style="color: var(--text-secondary); font-size: 10px; font-weight: 600; text-transform: uppercase;">
                            Hovering
                        </div>
                        <div style="color: var(--text-secondary); font-size: 10px;">
                            ${neighborCount} connection${neighborCount !== 1 ? 's' : ''}
                        </div>
                    </div>
                    <div style="color: var(--text); font-size: 14px; font-weight: 600; margin-bottom: 6px;">
                        ${this.escapeHtml(displayName)}
                    </div>
            `;
            
            if (labels.length > 0) {
                html += `
                    <div style="display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 8px;">
                        ${labels.slice(0, 3).map(label => `
                            <span style="
                                display: inline-block; padding: 2px 6px;
                                color: var(--accent); border: 1px solid var(--accent-border, rgba(96, 165, 250, 0.3));
                                border-radius: 3px; font-size: 9px; font-weight: 600;
                            ">${this.escapeHtml(String(label))}</span>
                        `).join('')}
                    </div>
                `;
            }
            
            // Show one key property
            const importantProps = ['text', 'body', 'content', 'summary', 'description'];
            for (const key of importantProps) {
                if (properties[key]) {
                    let value = String(properties[key]);
                    if (value.length > 80) {
                        value = value.substring(0, 80) + '...';
                    }
                    html += `
                        <div style="color: var(--text); font-size: 11px; line-height: 1.3;">
                            ${this.escapeHtml(value)}
                        </div>
                    `;
                    break;
                }
            }
            
            html += '</div>';
            
            this.hoverPreviewElement.innerHTML = html;
            this.hoverPreviewElement.style.display = 'block';
            // Trigger reflow
            void this.hoverPreviewElement.offsetWidth;
            this.hoverPreviewElement.style.transform = 'translateY(0)';
        },
        
        /**
         * Hide hover preview
         */
        hideHoverPreview: function() {
            this.hoverPreviewElement.style.transform = 'translateY(100%)';
            setTimeout(() => {
                this.hoverPreviewElement.style.display = 'none';
            }, 300);
        },
        

        /**
         * Expand node info to show ALL details with integrated context menu - THEME COMPATIBLE
         */
        expandNodeInfo: async function(nodeId) {
            this.isExpanded = true;
            this.inlineMode = false;
            this.currentNodeId = nodeId;
            this.currentEdgeId = null;
            
            if (!this.graphAddon || !this.graphAddon.nodesData) {
                return;
            }
            
            const nodeData = this.graphAddon.nodesData[nodeId];
            if (!nodeData) {
                return;
            }
            
            await this.renderExpandedView(nodeId, nodeData);
        },
        
        /**
         * Show inline content (generic method for canvas menu dialogs) - THEME COMPATIBLE
         */
        showInlineContent: function(title, content, backAction = null) {
            this.inlineMode = true;
            this.isExpanded = true;
            
            // Update card width for expanded state
            this.updateCardWidth();
            
            // Ensure card is in expanded position and VISIBLE
            this.cardElement.style.position = 'absolute';
            this.cardElement.style.maxHeight = '80vh';
            this.cardElement.style.bottom = '20px';
            this.cardElement.style.right = '20px';
            this.cardElement.style.top = 'auto';
            this.cardElement.style.transform = 'none';
            this.cardElement.style.display = 'block';  // CRITICAL: Make it visible
            this.cardElement.style.opacity = '1';      // CRITICAL: Make it opaque
            this.cardElement.style.background = 'var(--panel-bg)';
            
            const backButton = backAction 
                ? `<button onclick="${backAction}" style="
                    background: none; border: none; color: var(--text-secondary);
                    cursor: pointer; font-size: 20px; padding: 0;
                    width: 28px; height: 28px;
                " title="Back">←</button>`
                : `<button onclick="window.GraphInfoCard.collapse()" style="
                    background: none; border: none; color: var(--text-secondary);
                    cursor: pointer; font-size: 20px; padding: 0;
                    width: 28px; height: 28px;
                " title="Close">✕</button>`;
            
            this.cardElement.innerHTML = `
                <div style="padding: 20px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                        <div style="color: var(--text); font-size: 18px; font-weight: 600;">
                            ${title}
                        </div>
                        ${backButton}
                    </div>
                    ${content}
                </div>
            `;
        },
        

        /**
         * Render expanded view with vector content - THEME COMPATIBLE
         */
        renderExpandedView: async function(nodeId, nodeData) {
            const displayName = nodeData.display_name || nodeId;
            const labels = nodeData.labels || [];
            const properties = nodeData.properties || {};
            
            // Get neighbor count
            let neighborCount = 0;
            try {
                neighborCount = network.getConnectedNodes(nodeId).length;
            } catch (e) {}
            
            // Update card width for expanded state
            this.updateCardWidth();
            
            // Better positioning - absolute to graph container
            this.cardElement.style.position = 'absolute';
            this.cardElement.style.maxHeight = '80vh';
            this.cardElement.style.bottom = '20px';
            this.cardElement.style.right = '20px';
            this.cardElement.style.top = 'auto';
            this.cardElement.style.transform = 'none';
            this.cardElement.style.background = 'var(--panel-bg)';
            
            // Show loading state first
            this.cardElement.innerHTML = `
                <div style="padding: 20px; text-align: center;">
                    <div style="color: var(--text-secondary); margin-bottom: 12px;">Loading vector content...</div>
                    <div class="spinner"></div>
                </div>
            `;
            this.show();
            
            // Fetch vector content
            let vectorContent = null;
            try {
                // Determine the correct API base URL
                let apiUrl;
                if (window.location.protocol === 'file:') {
                    // If opened as file://, assume default server
                    apiUrl = 'http://llm.int:8888/api/memory/vector-content';
                    console.warn('Page opened via file://, using default API URL:', apiUrl);
                } else {
                    // Use current origin
                    apiUrl = `${window.location.origin}/api/memory/vector-content`;
                }
                
                console.log('Fetching vector content from:', apiUrl, 'for node:', nodeId);
                
                const response = await fetch(apiUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    },
                    body: JSON.stringify({
                        node_ids: [nodeId],
                        session_id: window.GraphAddon?.currentSessionId || null
                    })
                });
                
                if (!response.ok) {
                    const errorText = await response.text();
                    console.error('Vector content fetch failed:', response.status, errorText);
                    throw new Error(`HTTP ${response.status}: ${errorText}`);
                }
                
                const data = await response.json();
                console.log('Vector API response:', data);
                
                if (data.content && data.content[nodeId]) {
                    vectorContent = data.content[nodeId];
                    console.log('✓ Vector content found:', {
                        text_length: vectorContent.text?.length,
                        source: vectorContent.source,
                        metadata: vectorContent.metadata
                    });
                } else {
                    console.log('No vector content found for node:', nodeId, 'in response:', data);
                }
            } catch (e) {
                console.error('Failed to fetch vector content:', e);
                // Continue rendering without vector content
            }
            // Build expanded content
            let html = `
                <div style="padding: 20px;">
                    <!-- Header with close button -->
                    <div style="display: flex; align-items: flex-start; gap: 12px; margin-bottom: 16px;">
                        <div style="flex: 1; min-width: 0;">
                            <div style="
                                color: var(--text); font-size: 18px; font-weight: 600;
                                margin-bottom: 6px; word-wrap: break-word;
                            ">${this.escapeHtml(displayName)}</div>
                            
                            <!-- Connection count, ID, and labels inline -->
                            <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 4px;">
                                <div style="color: var(--text-secondary); font-size: 12px;">
                                    ${neighborCount} connection${neighborCount !== 1 ? 's' : ''}
                                </div>
                                <div style="color: var(--text-secondary); font-size: 12px;">•</div>
                                <div style="color: var(--text-secondary); font-size: 12px;">
                                    ID: ${this.escapeHtml(String(nodeId))}
                                </div>
                            </div>
                            
                            <!-- Labels on next line if present -->
                            ${labels.length > 0 ? `
                                <div style="display: flex; flex-wrap: wrap; gap: 4px; margin-top: 6px;">
                                    ${labels.map(label => `
                                        <span style="
                                            display: inline-block; padding: 3px 8px;
                                            color: var(--accent); background: var(--accent-bg, rgba(96, 165, 250, 0.15));
                                            border: 1px solid var(--accent-border, rgba(96, 165, 250, 0.4));
                                            border-radius: 4px; font-size: 10px; font-weight: 600;
                                        ">${this.escapeHtml(String(label))}</span>
                                    `).join('')}
                                </div>
                            ` : ''}
                        </div>
                        <button onclick="window.GraphInfoCard.collapse()" style="
                            background: none; border: none; color: var(--text-secondary);
                            cursor: pointer; font-size: 20px; padding: 0;
                            width: 28px; height: 28px; display: flex; align-items: center; justify-content: center;
                            flex-shrink: 0;
                        " title="Collapse">✕</button>
                    </div>
            `;
            
            // Vector Content Section - PRIORITY DISPLAY
            if (vectorContent && vectorContent.text) {
                const fullText = vectorContent.text;
                const isLong = fullText.length > 500;
                
                html += `
                    <div style="margin-bottom: 16px;">
                        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                            <div style="color: var(--text-secondary); font-size: 12px; font-weight: 600;">
                                📄 Full Content
                            </div>
                            <div style="color: var(--text-secondary); font-size: 10px;">
                                ${fullText.length} chars • ${vectorContent.source}
                            </div>
                        </div>
                        <div style="
                            background: var(--bg); 
                            padding: 12px; 
                            border-radius: 6px; 
                            border: 1px solid var(--border-subtle);
                            ${isLong ? 'max-height: 300px; overflow-y: auto;' : ''}
                        ">
                            <pre style="
                                color: var(--text); 
                                font-size: 12px; 
                                margin: 0; 
                                white-space: pre-wrap;
                                word-wrap: break-word;
                                line-height: 1.5;
                                font-family: 'Courier New', monospace;
                            ">${this.escapeHtml(fullText)}</pre>
                        </div>
                    </div>
                `;
            } else {
                // Show notice if no vector content found
                html += `
                    <div style="
                        margin-bottom: 16px; 
                        padding: 12px; 
                        background: var(--bg-surface);
                        border: 1px solid var(--border-subtle);
                        border-radius: 6px;
                        text-align: center;
                    ">
                        <div style="color: var(--text-secondary); font-size: 11px;">
                            ℹ️ No vector content found for this node
                        </div>
                    </div>
                `;
            }
            
            // ALL Properties with better compact layout
            html += '<div style="margin-bottom: 16px;">';
            html += '<div style="color: var(--text-secondary); font-size: 12px; font-weight: 600; margin-bottom: 8px;">Properties</div>';
            
            const propEntries = Object.entries(properties);
            if (propEntries.length > 0) {
                propEntries.forEach(([key, value]) => {
                    // Skip displaying 'text' property if we already showed vector content
                    if (key === 'text' && vectorContent && vectorContent.text) {
                        return;
                    }
                    
                    let val = String(value);
                    const isLong = val.length > 200;
                    
                    html += `
                        <div style="margin-bottom: 8px; background: var(--bg); padding: 8px; border-radius: 6px; border: 1px solid var(--border-subtle);">
                            <div style="color: var(--text-secondary); font-size: 10px; font-weight: 600; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.5px;">
                                ${this.escapeHtml(key)}
                            </div>
                            <div style="
                                color: var(--text); font-size: 12px; line-height: 1.4; 
                                word-break: break-word; text-align: left;
                                ${isLong ? 'max-height: 120px; overflow-y: auto;' : ''}
                            ">
                                ${this.escapeHtml(val)}
                            </div>
                        </div>
                    `;
                });
            } else {
                html += '<div style="color: var(--text-secondary); font-size: 13px; text-align: center; padding: 12px;">No properties</div>';
            }
            
            html += '</div>';
            
            // Neighbors section
            html += '<div style="margin-bottom: 16px;">';
            html += '<div style="color: var(--text-secondary); font-size: 12px; font-weight: 600; margin-bottom: 8px;">Neighbors</div>';
            
            const neighbors = this.getNeighbors(nodeId);
            if (neighbors.length > 0) {
                const maxNeighbors = 20;
                neighbors.slice(0, maxNeighbors).forEach(neighbor => {
                    const borderColor = neighbor.color || 'var(--accent)';
                    html += `
                        <div onclick="window.GraphInfoCard.focusAndExpand('${this.escapeHtml(String(neighbor.id))}')" style="
                            padding: 8px; margin-bottom: 6px;
                            background: var(--bg); border-left: 3px solid ${borderColor};
                            border-radius: 4px; cursor: pointer;
                            transition: background 0.2s;
                        " onmouseover="this.style.background='var(--hover)'" onmouseout="this.style.background='var(--bg)'">
                            <div style="color: var(--text); font-size: 12px; font-weight: 500; margin-bottom: 2px;">
                                ${this.escapeHtml(neighbor.name)}
                            </div>
                            <div style="color: var(--text-secondary); font-size: 10px;">
                                ${this.escapeHtml(neighbor.relationship)}
                            </div>
                        </div>
                    `;
                });
                
                if (neighbors.length > maxNeighbors) {
                    html += `<div style="text-align:center; font-style:italic; color: var(--text-secondary); margin-top:6px; font-size: 10px;">Showing first ${maxNeighbors} of ${neighbors.length} neighbors</div>`;
                }
            } else {
                html += '<div style="text-align:center; font-style:italic; color: var(--text-secondary); padding: 10px; font-size: 12px;">No neighbors</div>';
            }
            
            html += '</div>';
            
            // Actions section with integrated context menu
            // In the Actions section, replace with this:
            html += `
                <div style="border-top: 1px solid var(--border); padding-top: 16px;">
                    <div style="color: var(--text-secondary); font-size: 12px; font-weight: 600; margin-bottom: 12px;">Actions</div>
                    
                    <!-- Primary Actions -->
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 12px;">
                        ${this.renderActionButton('🛠️ Execute Tool', `
                                window.GraphToolExecutor.showToolSelector('${nodeId}'); 
                        `, 'var(--success, #10b981)')}
                        
                        ${this.renderActionButton('💬 Ask Vera', `
                            if(window.GraphContextMenu) {
                                window.GraphContextMenu.handleAskVera('${nodeId}', '${this.escapeHtml(displayName).replace(/'/g, "\\'")}', ${JSON.stringify(nodeData).replace(/'/g, "\\'")});
                            }
                        `, 'var(--accent)')}
                    </div>
                    
                    <!-- Graph Controls -->
                    <div style="margin-bottom: 12px;">
                        <div style="color: var(--text-secondary); font-size: 10px; font-weight: 600; margin-bottom: 6px; text-transform: uppercase;">Graph Controls</div>
                        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 6px;">
                            ${this.renderSmallActionButton('🎨 Style', `
                                if(window.GraphStyleControl) {
                                    window.GraphStyleControl.showInCard('${nodeId}');
                                }
                            `)}
                            ${this.renderSmallActionButton('🔬 Filters', `
                                if(window.GraphAdvancedFilters) {
                                    window.GraphAdvancedFilters.showInCard('${nodeId}');
                                }
                            `)}
                            ${this.renderSmallActionButton('⚡ Query', `
                                if(window.CypherQuery) {
                                    window.CypherQuery.showInCard('${nodeId}');
                                }
                            `)}
                        </div>
                    </div>
                    
                    <!-- AI Assistant Button -->
                    <div style="margin-bottom: 12px;">
                        ${this.renderActionButton('🤖 AI Assistant', `
                            if(window.GraphAIAssistant) {
                                window.GraphAIAssistant.showAssistantMenu();
                            }
                        `, 'var(--accent)')}
                    </div>
                    
                    <!-- Discovery Actions -->
                    <div style="margin-bottom: 12px;">
                        <div style="color: var(--text-secondary); font-size: 10px; font-weight: 600; margin-bottom: 6px; text-transform: uppercase;">Discovery</div>
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px;">
                            ${this.renderSmallActionButton('🔎 Expand', `window.GraphInfoCard.showExpandDialog('${nodeId}')`)}
                            ${this.renderSmallActionButton('🔗 Hidden Links', `
                                if(window.GraphDiscovery) {
                                    window.GraphDiscovery.findHiddenRelationships('${nodeId}');
                                }
                            `)}
                            ${this.renderSmallActionButton('👥 Similar', `
                                if(window.GraphDiscovery) {
                                    window.GraphDiscovery.findSimilarNodes('${nodeId}');
                                }
                            `)}
                            ${this.renderSmallActionButton('🛤️ Find Paths', `
                                if(window.GraphDiscovery) {
                                    window.GraphDiscovery.showPathFinder('${nodeId}');
                                }
                            `)}
                        </div>
                    </div>
                    
                    <!-- View Actions -->
                    <div style="margin-bottom: 12px;">
                        <div style="color: var(--text-secondary); font-size: 10px; font-weight: 600; margin-bottom: 6px; text-transform: uppercase;">View</div>
                        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 6px;">
                            ${this.renderSmallActionButton('🗺️ Subgraph', `
                                window.GraphAddon.extractSubgraph('${nodeId}');
                            `)}
                            ${this.renderSmallActionButton('🎯 Focus', `
                                network.selectNodes(['${nodeId}']); 
                                network.fit({nodes: ['${nodeId}'], animation: true});
                            `)}
                            ${this.renderSmallActionButton('🔍 Select All', `
                                network.selectNodes(network.getConnectedNodes('${nodeId}').concat(['${nodeId}']));
                            `)}
                        </div>
                    </div>
                </div>
            `;
            
            html += '</div>';
            
            this.cardElement.innerHTML = html;
            this.show();
        },
        /**
         * Show expand dialog inline - THEME COMPATIBLE
         */
        showExpandDialog: function(nodeId) {
            this.inlineMode = true;
            this.isExpanded = true;
            
            // Update card width for expanded state
            this.updateCardWidth();
            
            // Ensure proper positioning and visibility
            this.cardElement.style.position = 'absolute';
            this.cardElement.style.maxHeight = '80vh';
            this.cardElement.style.bottom = '20px';
            this.cardElement.style.right = '20px';
            this.cardElement.style.top = 'auto';
            this.cardElement.style.transform = 'none';
            this.cardElement.style.display = 'block';
            this.cardElement.style.opacity = '1';
            this.cardElement.style.background = 'var(--panel-bg)';
            
            const nodeData = this.graphAddon.nodesData[nodeId];
            const nodeName = nodeData ? nodeData.display_name : nodeId;
            
            this.cardElement.innerHTML = `
                <div style="padding: 20px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                        <div style="color: var(--text); font-size: 18px; font-weight: 600;">
                            🔎 Expand Neighbors
                        </div>
                        <button onclick="window.GraphInfoCard.expandNodeInfo('${nodeId}')" style="
                            background: none; border: none; color: var(--text-secondary);
                            cursor: pointer; font-size: 20px; padding: 0;
                            width: 28px; height: 28px;
                        " title="Back">←</button>
                    </div>
                    
                    <div style="color: var(--text-secondary); font-size: 13px; margin-bottom: 16px;">
                        Expand connections for: <strong style="color: var(--text);">${this.escapeHtml(nodeName)}</strong>
                    </div>
                    
                    <div style="background: var(--bg); padding: 16px; border-radius: 8px; border: 1px solid var(--border-subtle);">
                        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
                            <label style="color: var(--text-secondary); font-size: 13px; font-weight: 600;">Depth (Hops)</label>
                            <input 
                                type="number" 
                                id="expand-depth-input" 
                                value="2" 
                                min="1" 
                                max="10"
                                style="
                                    width: 60px; padding: 6px 10px;
                                    background: var(--bg-surface); color: var(--text);
                                    border: 1px solid var(--border); border-radius: 6px;
                                    font-size: 14px; font-weight: 600; text-align: center;
                                "
                                oninput="document.getElementById('expand-depth-slider').value = this.value"
                            >
                        </div>
                        
                        <input 
                            type="range" 
                            id="expand-depth-slider" 
                            value="2" 
                            min="1" 
                            max="10" 
                            step="1"
                            style="
                                width: 100%; height: 8px;
                                background: linear-gradient(to right, var(--accent) 0%, var(--accent) 100%);
                                border-radius: 4px; outline: none;
                            "
                            oninput="document.getElementById('expand-depth-input').value = this.value"
                        >
                        
                        <div style="display: flex; justify-content: space-between; margin-top: 8px; color: var(--text-secondary); font-size: 11px;">
                            <span>1 hop</span>
                            <span>5 hops</span>
                            <span>10 hops</span>
                        </div>
                        
                        <div style="margin-top: 16px; padding: 12px; background: var(--accent-bg, rgba(59, 130, 246, 0.1)); border-radius: 6px; border: 1px solid var(--accent-border, rgba(59, 130, 246, 0.2));">
                            <div style="color: var(--accent); font-size: 11px; font-weight: 600; margin-bottom: 4px;">💡 Tip</div>
                            <div style="color: var(--text-secondary); font-size: 11px; line-height: 1.4;">
                                Higher depths find more connections but may take longer. Start with 2-3 hops for best results.
                            </div>
                        </div>
                    </div>
                    
                    <div style="display: flex; gap: 8px; margin-top: 20px;">
                        <button onclick="
                            const depth = parseInt(document.getElementById('expand-depth-input').value);
                            if(window.GraphDiscovery) {
                                window.GraphDiscovery.expandNeighbors('${nodeId}', depth);
                            }
                            window.GraphInfoCard.expandNodeInfo('${nodeId}');
                        " style="
                            flex: 1; padding: 12px;
                            background: var(--accent); color: var(--text-inverted); border: none;
                            border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 14px;
                        ">Expand</button>
                        <button onclick="window.GraphInfoCard.expandNodeInfo('${nodeId}')" style="
                            padding: 12px 24px;
                            background: var(--bg-surface); color: var(--text); border: 1px solid var(--border);
                            border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 14px;
                        ">Cancel</button>
                    </div>
                </div>
            `;
        },
        
        /**
         * Helper to render action button - THEME COMPATIBLE
         */
        renderActionButton: function(label, onclick, color = 'var(--accent)') {
            return `
                <button onclick="${onclick}" style="
                    width: 100%; padding: 10px;
                    background: ${color}; color: var(--text-inverted);
                    border: none; border-radius: 6px; cursor: pointer;
                    font-weight: 600; font-size: 13px;
                ">${label}</button>
            `;
        },
        
        /**
         * Helper to render small action button - THEME COMPATIBLE
         */
        renderSmallActionButton: function(label, onclick) {
            return `
                <button onclick="${onclick}" style="
                    width: 100%; padding: 8px;
                    background: var(--bg-surface); color: var(--text);
                    border: 1px solid var(--border); border-radius: 4px; cursor: pointer;
                    font-weight: 600; font-size: 11px;
                ">${label}</button>
            `;
        },
        
        /**
         * Get neighbors with relationship info
         */
        getNeighbors: function(nodeId) {
            const neighbors = [];
            try {
                const connectedEdges = network.getConnectedEdges(nodeId);
                
                connectedEdges.forEach(edgeId => {
                    const edge = network.body.data.edges.get(edgeId);
                    if (!edge) return;
                    
                    const neighborId = edge.from === nodeId ? edge.to : edge.from;
                    const neighborNode = this.graphAddon.nodesData[neighborId];
                    
                    if (neighborNode) {
                        const edgeLabel = edge.label || edge.type || 'connected';
                        const direction = edge.from === nodeId ? '→' : '←';
                        neighbors.push({
                            id: neighborId,
                            name: neighborNode.display_name || neighborId,
                            relationship: `${direction} ${edgeLabel}`,
                            color: neighborNode.color
                        });
                    }
                });
            } catch (e) {
                console.error('GraphInfoCard: Get neighbors error:', e);
            }
            
            return neighbors;
        },
        
        /**
         * Render vector content - THEME COMPATIBLE
         */
        renderVectorContent: function(nodeId) {
            if (!this.graphAddon.vectorData || !this.graphAddon.vectorData[nodeId]) {
                return null;
            }
            
            const vectorContent = this.graphAddon.vectorData[nodeId];
            
            try {
                const content = typeof vectorContent === 'string' 
                    ? vectorContent 
                    : JSON.stringify(vectorContent, null, 2);
                
                const truncated = content.length > 500 
                    ? content.substring(0, 500) + '...' 
                    : content;
                
                return `
                    <div style="
                        background: var(--bg); 
                        padding: 10px; 
                        border-radius: 6px; 
                        border: 1px solid var(--border-subtle);
                        max-height: 120px;
                        overflow-y: auto;
                    ">
                        <pre style="
                            color: var(--text); 
                            font-size: 11px; 
                            margin: 0; 
                            white-space: pre-wrap;
                            word-wrap: break-word;
                        ">${this.escapeHtml(truncated)}</pre>
                    </div>
                `;
            } catch (e) {
                return null;
            }
        },
        
        /**
         * Focus and expand a node (for neighbor clicks)
         */
        focusAndExpand: function(nodeId) {
            network.selectNodes([nodeId]);
            network.fit({
                nodes: [nodeId],
                animation: { duration: 500, easingFunction: 'easeInOutQuad' }
            });
            
            // Delay expansion slightly for smooth animation
            setTimeout(() => {
                this.expandNodeInfo(nodeId);
            }, 300);
        },
        
        /**
         * Show edge information (compact) - THEME COMPATIBLE
         */
        showEdgeInfo: function(edgeId) {
            clearTimeout(this.hideTimeout);
            
            this.currentNodeId = null;
            this.currentEdgeId = edgeId;
            
            let edge;
            try {
                edge = network.body.data.edges.get(edgeId);
            } catch (e) {
                return;
            }
            
            if (!edge) return;
            
            const fromNode = this.graphAddon.nodesData[edge.from];
            const toNode = this.graphAddon.nodesData[edge.to];
            const relationship = edge.label || edge.type || 'Connection';
            
            const fromName = fromNode ? fromNode.display_name : edge.from;
            const toName = toNode ? toNode.display_name : edge.to;
            
            let html = `
                <div style="padding: 16px;">
                    <!-- Header -->
                    <div style="margin-bottom: 12px;">
                        <div style="
                            color: var(--accent); font-size: 14px; font-weight: 600;
                            margin-bottom: 8px; text-align: center;
                        ">
                            ${this.escapeHtml(relationship)}
                        </div>
                    </div>
                    
                    <!-- Connection flow -->
                    <div style="
                        border: 1px solid var(--border);
                        border-radius: 8px;
                        padding: 12px;
                    ">
                        <!-- From node -->
                        <div style="margin-bottom: 8px;">
                            <div style="color: var(--text-secondary); font-size: 10px; font-weight: 600; margin-bottom: 4px;">
                                FROM
                            </div>
                            <div style="
                                color: var(--text); font-size: 13px;
                                padding: 6px 10px;
                                border-radius: 4px;
                                word-wrap: break-word;
                            ">
                                ${this.escapeHtml(fromName)}
                            </div>
                        </div>
                        
                        <!-- Arrow -->
                        <div style="text-align: center; margin: 8px 0;">
                            <div style="color: var(--accent); font-size: 20px;">↓</div>
                        </div>
                        
                        <!-- To node -->
                        <div>
                            <div style="color: var(--text-secondary); font-size: 10px; font-weight: 600; margin-bottom: 4px;">
                                TO
                            </div>
                            <div style="
                                color: var(--text); font-size: 13px;
                                padding: 6px 10px;
                                border-radius: 4px;
                                word-wrap: break-word;
                            ">
                                ${this.escapeHtml(toName)}
                            </div>
                        </div>
                    </div>
                    
                    <!-- Footer -->
                    <div style="
                        margin-top: 12px; padding-top: 12px;
                        border-top: 1px solid var(--border);
                        color: var(--text-secondary); font-size: 10px; text-align: center;
                        cursor: pointer;
                    ">
                        Click for full details
                    </div>
                </div>
            `;
            
            this.cardElement.innerHTML = html;
            this.show();
        },
        
        /**
         * Expand edge info to show ALL details - THEME COMPATIBLE
         */
        expandEdgeInfo: function(edgeId) {
            this.isExpanded = true;
            this.inlineMode = false;
            this.currentNodeId = null;
            this.currentEdgeId = edgeId;
            
            let edge;
            try {
                edge = network.body.data.edges.get(edgeId);
            } catch (e) {
                return;
            }
            
            if (!edge) return;
            
            const fromNode = this.graphAddon.nodesData[edge.from];
            const toNode = this.graphAddon.nodesData[edge.to];
            const relationship = edge.label || edge.type || 'Connection';
            
            const fromName = fromNode ? fromNode.display_name : edge.from;
            const toName = toNode ? toNode.display_name : edge.to;
            
            // Update card width for expanded state
            this.updateCardWidth();
            
            // Better positioning - absolute to graph container
            this.cardElement.style.position = 'absolute';
            this.cardElement.style.maxHeight = '80vh';
            this.cardElement.style.bottom = '20px';
            this.cardElement.style.right = '20px';
            this.cardElement.style.top = 'auto';
            this.cardElement.style.transform = 'none';
            this.cardElement.style.background = 'var(--panel-bg)';
            
            let html = `
                <div style="padding: 20px;">
                    <!-- Header with close -->
                    <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 16px;">
                        <div style="color: var(--accent); font-size: 18px; font-weight: 600;">
                            ${this.escapeHtml(relationship)}
                        </div>
                        <button onclick="window.GraphInfoCard.collapse()" style="
                            background: none; border: none; color: var(--text-secondary);
                            cursor: pointer; font-size: 20px; padding: 0;
                            width: 28px; height: 28px;
                        " title="Collapse">✕</button>
                    </div>
                    
                    <!-- Connection details -->
                    <div style="background: var(--bg); padding: 16px; border-radius: 8px; border: 1px solid var(--border-subtle); margin-bottom: 16px;">
                        <div style="margin-bottom: 12px;">
                            <div style="color: var(--text-secondary); font-size: 11px; font-weight: 600; margin-bottom: 6px;">FROM</div>
                            <div style="color: var(--text); font-size: 14px; word-wrap: break-word;">${this.escapeHtml(fromName)}</div>
                        </div>
                        
                        <div style="text-align: center; margin: 12px 0;">
                            <div style="color: var(--accent); font-size: 24px;">↓</div>
                        </div>
                        
                        <div>
                            <div style="color: var(--text-secondary); font-size: 11px; font-weight: 600; margin-bottom: 6px;">TO</div>
                            <div style="color: var(--text); font-size: 14px; word-wrap: break-word;">${this.escapeHtml(toName)}</div>
                        </div>
                    </div>
                    
                    <!-- Edge properties -->
                    ${edge.properties && Object.keys(edge.properties).length > 0 ? `
                        <div style="margin-bottom: 16px;">
                            <div style="color: var(--text-secondary); font-size: 12px; font-weight: 600; margin-bottom: 8px;">Properties</div>
                            ${Object.entries(edge.properties).map(([key, value]) => `
                                <div style="margin-bottom: 8px; background: var(--bg); padding: 10px; border-radius: 6px; border: 1px solid var(--border-subtle);">
                                    <div style="color: var(--text-secondary); font-size: 11px; font-weight: 600; margin-bottom: 4px;">${this.escapeHtml(key)}</div>
                                    <div style="color: var(--text); font-size: 13px; word-wrap: break-word;">${this.escapeHtml(String(value))}</div>
                                </div>
                            `).join('')}
                        </div>
                    ` : ''}
                    
                    <!-- Actions -->
                    <div style="border-top: 1px solid var(--border); padding-top: 16px;">
                        <div style="color: var(--text-secondary); font-size: 12px; font-weight: 600; margin-bottom: 12px;">Actions</div>
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                            <button onclick="window.GraphInfoCard.focusAndExpand('${edge.from}');" style="
                                padding: 12px; background: var(--bg-surface); color: var(--text);
                                border: 1px solid var(--border); border-radius: 6px; cursor: pointer; font-weight: 600;
                                font-size: 13px;
                            ">→ View From</button>
                            
                            <button onclick="window.GraphInfoCard.focusAndExpand('${edge.to}');" style="
                                padding: 12px; background: var(--bg-surface); color: var(--text);
                                border: 1px solid var(--border); border-radius: 6px; cursor: pointer; font-weight: 600;
                                font-size: 13px;
                            ">→ View To</button>
                        </div>
                    </div>
                </div>
            `;
            
            this.cardElement.innerHTML = html;
            this.show();
        },
        
        /**
         * Collapse back to compact view or hide
         */
        collapse: function() {
            console.log('GraphInfoCard.collapse() called');
            this.isExpanded = false;
            this.inlineMode = false;
            
            // Hide hover preview
            this.hideHoverPreview();
            
            // Update card width for compact state
            this.updateCardWidth();
            
            // Restore compact position
            this.cardElement.style.position = 'absolute';
            this.cardElement.style.maxHeight = '400px';
            this.cardElement.style.bottom = '20px';
            this.cardElement.style.right = '20px';
            this.cardElement.style.top = 'auto';
            this.cardElement.style.transform = 'none';
            this.cardElement.style.background = 'var(--panel-bg)';
            
            // Hide the card
            this.hide();
        },
        
        /**
         * Show the card
         */
        show: function() {
            this.cardElement.style.display = 'block';
            // Trigger reflow for animation
            void this.cardElement.offsetWidth;
            this.cardElement.style.opacity = '1';
        },
        
        /**
         * Schedule hiding the card
         */
        scheduleHide: function() {
            clearTimeout(this.hideTimeout);
            this.hideTimeout = setTimeout(() => {
                this.hide();
            }, 300);
        },
        
        /**
         * Hide the card
         */
        hide: function() {
            this.cardElement.style.opacity = '0';
            setTimeout(() => {
                this.cardElement.style.display = 'none';
            }, 300);
        },
        
        /**
         * Escape HTML for safe display
         */
        escapeHtml: function(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        },
        
        /**
         * Cleanup on destroy
         */
        destroy: function() {
            if (this.resizeObserver) {
                this.resizeObserver.disconnect();
            }
            if (this.cardElement) {
                this.cardElement.remove();
            }
            if (this.hoverPreviewElement) {
                this.hoverPreviewElement.remove();
            }
        }
    };
})();