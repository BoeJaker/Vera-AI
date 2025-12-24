/**
 * GraphInfoCard Module
 * Displays node/edge information in a stationary card instead of tooltips
 */

(function() {
    'use strict';
    
    window.GraphInfoCard = {
        
        // Store references
        graphAddon: null,
        cardElement: null,
        currentNodeId: null,
        currentEdgeId: null,
        hideTimeout: null,
        
        /**
         * Initialize the module
         */
        init: function(graphAddon) {
            console.log('GraphInfoCard.init called');
            this.graphAddon = graphAddon;
            
            // Create card element
            this.createCard();
            
            // Disable vis.js tooltips
            this.disableTooltips();
            
            // Wait for network
            this.waitForNetwork();
            
            console.log('GraphInfoCard initialized');
        },
        
        /**
         * Create the info card element
         */
        createCard: function() {
            // Remove existing card if any
            const existing = document.getElementById('graph-info-card-fixed');
            if (existing) {
                existing.remove();
            }
            
            // Create new card
            this.cardElement = document.createElement('div');
            this.cardElement.id = 'graph-info-card-fixed';
            this.cardElement.style.cssText = `
                position: fixed;
                bottom: 20px;
                right: 20px;
                width: 320px;
                max-height: 400px;
                background: linear-gradient(135deg, #1e293b 0%, #0f172a 50%);
                border: 1px solid #334155;
                border-radius: 12px;
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
                z-index: 9999;
                display: none;
                overflow: hidden;
                backdrop-filter: blur(10px);
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            `;
            
            document.body.appendChild(this.cardElement);
            
            console.log('Info card created');
        },
        
        /**
         * Disable vis.js tooltips
         */
        disableTooltips: function() {
            if (typeof network !== 'undefined') {
                // Disable tooltips in options
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
                self.showNodeInfo(params.node);
            });
            
            // Hover over edge
            network.on("hoverEdge", function(params) {
                self.showEdgeInfo(params.edge);
            });
            
            // Mouse leaves canvas
            network.on("blurNode", function() {
                self.scheduleHide();
            });
            
            network.on("blurEdge", function() {
                self.scheduleHide();
            });
            
            // Keep card visible when hovering over it
            this.cardElement.addEventListener('mouseenter', () => {
                clearTimeout(self.hideTimeout);
            });
            
            this.cardElement.addEventListener('mouseleave', () => {
                self.scheduleHide();
            });
            
            console.log('Event listeners set up');
        },
        
        /**
         * Show node information
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
                    <div style="display: flex; align-items: flex-start; gap: 12px; margin-bottom: 12px;">
                        <div style="
                            width: 8px; height: 8px; border-radius: 50%;
                            background: ${nodeData.color || '#3b82f6'};
                            margin-top: 6px; flex-shrink: 0;
                        "></div>
                        <div style="flex: 1; min-width: 0;">
                            <div style="
                                color: #e2e8f0; font-size: 15px; font-weight: 600;
                                margin-bottom: 4px; word-wrap: break-word;
                            ">${this.escapeHtml(displayName)}</div>
                            <div style="color: #64748b; font-size: 11px;">
                                ${neighborCount} connection${neighborCount !== 1 ? 's' : ''}
                            </div>
                        </div>
                    </div>
            `;
            
            // Labels
            if (labels.length > 0) {
                html += `
                    <div style="display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 12px;">
                        ${labels.slice(0, 4).map(label => `
                            <span style="
                                display: inline-block; padding: 3px 8px;
                                background: rgba(96, 165, 250, 0.15);
                                color: #60a5fa; border: 1px solid rgba(96, 165, 250, 0.3);
                                border-radius: 4px; font-size: 10px; font-weight: 600;
                            ">${this.escapeHtml(String(label))}</span>
                        `).join('')}
                        ${labels.length > 4 ? `
                            <span style="color: #64748b; font-size: 10px; padding: 3px 4px;">
                                +${labels.length - 4} more
                            </span>
                        ` : ''}
                    </div>
                `;
            }
            
            // Key properties - show first 3
            const importantProps = ['text', 'body', 'content', 'summary', 'description', 'type', 'status'];
            let propsShown = 0;
            
            html += '<div style="border-top: 1px solid #334155; padding-top: 12px;">';
            
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
                            <div style="color: #94a3b8; font-size: 10px; font-weight: 600; margin-bottom: 2px; text-transform: uppercase; letter-spacing: 0.5px;">
                                ${this.escapeHtml(key)}
                            </div>
                            <div style="color: #cbd5e1; font-size: 12px; line-height: 1.4; word-wrap: break-word;">
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
                            <div style="color: #94a3b8; font-size: 10px; font-weight: 600; margin-bottom: 2px;">
                                ${this.escapeHtml(key)}
                            </div>
                            <div style="color: #cbd5e1; font-size: 12px; line-height: 1.4; word-wrap: break-word;">
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
                    border-top: 1px solid #334155;
                    color: #64748b; font-size: 10px; text-align: center;
                ">
                    Click node for full details
                </div>
            `;
            
            html += '</div>';
            
            this.cardElement.innerHTML = html;
            this.show();
        },
        
        /**
         * Show edge information
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
                            color: #60a5fa; font-size: 14px; font-weight: 600;
                            margin-bottom: 8px; text-align: center;
                        ">
                            ${this.escapeHtml(relationship)}
                        </div>
                    </div>
                    
                    <!-- Connection flow -->
                    <div style="
                        background: rgba(15, 23, 42, 0.6);
                        border: 1px solid #334155;
                        border-radius: 8px;
                        padding: 12px;
                    ">
                        <!-- From node -->
                        <div style="margin-bottom: 8px;">
                            <div style="color: #94a3b8; font-size: 10px; font-weight: 600; margin-bottom: 4px;">
                                FROM
                            </div>
                            <div style="
                                color: #e2e8f0; font-size: 13px;
                                padding: 6px 10px;
                                background: rgba(51, 65, 85, 0.5);
                                border-radius: 4px;
                                word-wrap: break-word;
                            ">
                                ${this.escapeHtml(fromName)}
                            </div>
                        </div>
                        
                        <!-- Arrow -->
                        <div style="text-align: center; margin: 8px 0;">
                            <div style="color: #60a5fa; font-size: 20px;">↓</div>
                        </div>
                        
                        <!-- To node -->
                        <div>
                            <div style="color: #94a3b8; font-size: 10px; font-weight: 600; margin-bottom: 4px;">
                                TO
                            </div>
                            <div style="
                                color: #e2e8f0; font-size: 13px;
                                padding: 6px 10px;
                                background: rgba(51, 65, 85, 0.5);
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
                        border-top: 1px solid #334155;
                        color: #64748b; font-size: 10px; text-align: center;
                    ">
                        Click edge for full details
                    </div>
                </div>
            `;
            
            this.cardElement.innerHTML = html;
            this.show();
        },
        
        /**
         * Show the card
         */
        show: function() {
            this.cardElement.style.display = 'block';
            // Trigger reflow for animation
            void this.cardElement.offsetWidth;
            this.cardElement.style.opacity = '1';
            this.cardElement.style.transform = 'translateY(0)';
        },
        
        /**
         * Schedule hiding the card
         */
        scheduleHide: function() {
            clearTimeout(this.hideTimeout);
            this.hideTimeout = setTimeout(() => {
                this.hide();
            }, 300); // 300ms delay
        },
        
        /**
         * Hide the card
         */
        hide: function() {
            this.cardElement.style.opacity = '0';
            this.cardElement.style.transform = 'translateY(10px)';
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
         * Update card position (optional, for draggable card)
         */
        setPosition: function(position) {
            // position can be: 'bottom-right', 'bottom-left', 'top-right', 'top-left'
            const positions = {
                'bottom-right': { bottom: '20px', right: '20px', top: 'auto', left: 'auto' },
                'bottom-left': { bottom: '20px', left: '20px', top: 'auto', right: 'auto' },
                'top-right': { top: '20px', right: '20px', bottom: 'auto', left: 'auto' },
                'top-left': { top: '20px', left: '20px', bottom: 'auto', right: 'auto' }
            };
            
            const pos = positions[position] || positions['bottom-right'];
            Object.assign(this.cardElement.style, pos);
        }
    };
})();