/**
 * GraphAdvancedFilters Module
 * Advanced filtering and collapsing for graph visualization
 * 
 * Features:
 * - Property-based filtering for nodes and edges
 * - Collapse nodes/edges with identical properties
 * - Session filtering with multiple view modes
 * - Integration with existing GraphStyleControl
 */

(function() {
    'use strict';
    
    window.GraphAdvancedFilters = {
        
        // Module references
        graphAddon: null,
        styleControl: null,
        
        // Collapse click handler flag
        _collapseClickHandlerSet: false,
        
        // Filter state
        filters: {
            // Session filter
            session: {
                mode: 'all',  // 'all', 'session-only', 'inferred', 'hybrid', 'direct-only', 'session-recent', 'time-range'
                selectedSessionId: null,
                availableSessions: []
            },
            
            // Time range filter
            timeRange: {
                enabled: false,
                startTime: null,  // timestamp
                endTime: null,    // timestamp
                propertyName: 'created_at',  // or 'updated_at', 'timestamp', etc.
                minTime: null,    // discovered min
                maxTime: null     // discovered max
            },
            
            // Node property filters
            nodeProperties: {
                // { propertyName: { operator: 'equals'|'contains'|'exists', value: any, enabled: true } }
            },
            
            // Edge property filters
            edgeProperties: {
                // { propertyName: { operator: 'equals'|'contains'|'exists', value: any, enabled: true } }
            },
            
            // Collapse settings
            collapse: {
                nodes: {
                    enabled: false,
                    groupBy: [],  // Array of property names to group by
                    collapsed: new Map()  // Map<groupKey, {representativeId, memberIds[]}>
                },
                edges: {
                    enabled: false,
                    groupBy: [],  // Array of property names to group by
                    collapsed: new Map()  // Map<groupKey, {representativeId, memberIds[]}>
                }
            }
        },
        
        // Original data cache (before any filtering/collapsing)
        originalData: {
            nodes: new Map(),
            edges: new Map()
        },
        
        // Available properties for filtering
        availableProperties: {
            nodes: new Set(),
            edges: new Set()
        },
        
        /**
         * Initialize the module
         */
        init: function(graphAddon, styleControl) {
            console.log('GraphAdvancedFilters: Initializing...');
            this.graphAddon = graphAddon;
            this.styleControl = styleControl;
            
            // Load saved filters
            this.loadFilters();
            
            // Create UI first (empty)
            this.createFilterUI();
            
            // Discover data (will retry if needed)
            this.refreshDiscovery();
            
            console.log('GraphAdvancedFilters: Initialized');
        },
        
        /**
         * Refresh data discovery - call this after graph data loads
         */
        refreshDiscovery: function() {
            console.log('GraphAdvancedFilters: Discovering properties and sessions...');
            
            // Discover available properties
            this.discoverProperties();
            
            // Discover sessions
            this.discoverSessions();
            
            // Discover time range
            this.discoverTimeRange();
            
            // Update UI with discovered data
            this.populateSessionSelector();
            this.populateTimePropertySelector();
            this.syncUI();
            
            // Update status display
            this.updateDiscoveryStatus();
            
            console.log('GraphAdvancedFilters: Discovery complete');
            console.log(`  - Node properties: ${this.availableProperties.nodes.size}`);
            console.log(`  - Edge properties: ${this.availableProperties.edges.size}`);
            console.log(`  - Sessions: ${this.filters.session.availableSessions.length}`);
            console.log(`  - Time range: ${this.filters.timeRange.minTime ? 'found' : 'not found'}`);
        },
        
        /**
         * Update discovery status display
         */
        updateDiscoveryStatus: function() {
            const nodePropCount = document.getElementById('node-props-count');
            const edgePropCount = document.getElementById('edge-props-count');
            const sessionsCount = document.getElementById('sessions-count');
            
            if (nodePropCount) {
                nodePropCount.textContent = this.availableProperties.nodes.size;
                nodePropCount.style.color = this.availableProperties.nodes.size > 0 ? 'var(--accent)' : 'var(--error)';
            }
            
            if (edgePropCount) {
                edgePropCount.textContent = this.availableProperties.edges.size;
                edgePropCount.style.color = this.availableProperties.edges.size > 0 ? 'var(--accent)' : 'var(--error)';
            }
            
            if (sessionsCount) {
                sessionsCount.textContent = this.filters.session.availableSessions.length;
                sessionsCount.style.color = this.filters.session.availableSessions.length > 0 ? 'var(--accent)' : 'var(--text-secondary)';
            }
        },
        
        /**
         * Discover all available node and edge properties
         */
        discoverProperties: function() {
            // Clear existing
            this.availableProperties.nodes.clear();
            this.availableProperties.edges.clear();
            
            // Always add common node fields
            ['id', 'labels', 'display_name'].forEach(key => {
                this.availableProperties.nodes.add(key);
            });
            
            // Discover from GraphAddon nodesData
            if (this.graphAddon && this.graphAddon.nodesData) {
                const nodeCount = Object.keys(this.graphAddon.nodesData).length;
                console.log(`Discovering from ${nodeCount} nodes in GraphAddon.nodesData`);
                
                Object.values(this.graphAddon.nodesData).forEach(node => {
                    if (node.properties) {
                        Object.keys(node.properties).forEach(key => {
                            this.availableProperties.nodes.add(key);
                        });
                    }
                });
            }
            
            // Also check network nodes for additional properties
            if (typeof network !== 'undefined' && network.body && network.body.data && network.body.data.nodes) {
                const networkNodeCount = network.body.data.nodes.length;
                console.log(`Discovering from ${networkNodeCount} nodes in network`);
                
                network.body.data.nodes.forEach(node => {
                    Object.keys(node).forEach(key => {
                        if (!['x', 'y', 'color', 'font', 'size', 'shape', 'hidden'].includes(key)) {
                            this.availableProperties.nodes.add(key);
                        }
                    });
                });
            }
            
            // Always add common edge fields
            ['id', 'label', 'type', 'title'].forEach(key => {
                this.availableProperties.edges.add(key);
            });
            
            // Discover edge properties from network
            if (typeof network !== 'undefined' && network.body && network.body.data && network.body.data.edges) {
                const edgeCount = network.body.data.edges.length;
                console.log(`Discovering from ${edgeCount} edges in network`);
                
                network.body.data.edges.forEach(edge => {
                    Object.keys(edge).forEach(key => {
                        if (!['from', 'to', 'arrows', 'color', 'font', 'width', 'smooth', 'hidden'].includes(key)) {
                            this.availableProperties.edges.add(key);
                        }
                    });
                });
            }
            
            console.log(`Discovered properties:`, {
                nodes: Array.from(this.availableProperties.nodes),
                edges: Array.from(this.availableProperties.edges)
            });
        },
        
        /**
         * Discover available sessions from node properties
         */
        discoverSessions: function() {
            const sessions = new Set();
            
            // Check GraphAddon nodesData
            if (this.graphAddon && this.graphAddon.nodesData) {
                Object.values(this.graphAddon.nodesData).forEach(node => {
                    if (node.properties) {
                        // Check common session property names
                        const sessionId = node.properties.session_id || 
                                        node.properties.sessionId || 
                                        node.properties.session ||
                                        node.properties.SESSION_ID;
                        if (sessionId) {
                            sessions.add(String(sessionId));
                        }
                    }
                });
            }
            
            // Also check network nodes directly
            if (typeof network !== 'undefined' && network.body && network.body.data && network.body.data.nodes) {
                network.body.data.nodes.forEach(node => {
                    const sessionId = node.session_id || 
                                    node.sessionId || 
                                    node.session ||
                                    node.SESSION_ID;
                    if (sessionId) {
                        sessions.add(String(sessionId));
                    }
                });
            }
            
            this.filters.session.availableSessions = Array.from(sessions).sort();
            console.log(`Discovered ${sessions.size} sessions:`, this.filters.session.availableSessions);
        },
        
        /**
         * Discover time range from node properties
         */
        discoverTimeRange: function() {
            // Ensure timeRange object exists
            if (!this.filters.timeRange) {
                this.filters.timeRange = {
                    enabled: false,
                    startTime: null,
                    endTime: null,
                    propertyName: 'created_at',
                    minTime: null,
                    maxTime: null
                };
            }
            
            const timeProps = ['created_at', 'updated_at', 'timestamp', 'created', 'updated', 'time'];
            let minTime = Infinity;
            let maxTime = -Infinity;
            let foundProp = null;
            
            // Check GraphAddon nodesData
            if (this.graphAddon && this.graphAddon.nodesData) {
                Object.values(this.graphAddon.nodesData).forEach(node => {
                    if (node.properties) {
                        for (const prop of timeProps) {
                            if (node.properties[prop]) {
                                const timeValue = this.parseTimeValue(node.properties[prop]);
                                if (timeValue) {
                                    if (!foundProp) foundProp = prop;
                                    minTime = Math.min(minTime, timeValue);
                                    maxTime = Math.max(maxTime, timeValue);
                                }
                            }
                        }
                    }
                });
            }
            
            // Also check network nodes
            if (typeof network !== 'undefined' && network.body && network.body.data && network.body.data.nodes) {
                network.body.data.nodes.forEach(node => {
                    for (const prop of timeProps) {
                        if (node[prop]) {
                            const timeValue = this.parseTimeValue(node[prop]);
                            if (timeValue) {
                                if (!foundProp) foundProp = prop;
                                minTime = Math.min(minTime, timeValue);
                                maxTime = Math.max(maxTime, timeValue);
                            }
                        }
                    }
                });
            }
            
            if (minTime !== Infinity) {
                this.filters.timeRange.minTime = minTime;
                this.filters.timeRange.maxTime = maxTime;
                if (foundProp) {
                    this.filters.timeRange.propertyName = foundProp;
                }
                
                // Initialize range to full span
                if (!this.filters.timeRange.startTime) {
                    this.filters.timeRange.startTime = minTime;
                }
                if (!this.filters.timeRange.endTime) {
                    this.filters.timeRange.endTime = maxTime;
                }
                
                console.log(`Discovered time range: ${new Date(minTime).toISOString()} to ${new Date(maxTime).toISOString()}`);
            }
        },
        
        /**
         * Parse time value from various formats
         */
        parseTimeValue: function(value) {
            if (!value) return null;
            
            // Already a number (timestamp)
            if (typeof value === 'number') {
                return value;
            }
            
            // String - try to parse
            if (typeof value === 'string') {
                const parsed = Date.parse(value);
                if (!isNaN(parsed)) {
                    return parsed;
                }
            }
            
            return null;
        },
        
        /**
         * Create advanced filter UI
         */
        createFilterUI: function() {
            const settingsPanel = document.getElementById('settings-panel');
            if (!settingsPanel) return;
            
            const filterControls = `
                <style>
                /* Advanced Filter Styles */
                .adv-filter-section {
                    border-bottom: 2px solid var(--border);
                    padding-bottom: 16px;
                    margin-bottom: 16px;
                }
                
                .adv-filter-title {
                    font-size: 16px;
                    color: var(--accent);
                    margin-bottom: 12px;
                    font-weight: 600;
                    display: flex;
                    align-items: center;
                    gap: 8px;
                }
                
                .adv-filter-box {
                    background: var(--bg);
                    padding: 12px;
                    border-radius: 8px;
                    border: 1px solid var(--border-subtle);
                    margin-bottom: 12px;
                }
                
                .adv-filter-item {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    margin-bottom: 8px;
                    padding: 8px;
                    background: var(--bg-surface);
                    border-radius: 6px;
                    border: 1px solid var(--border-subtle);
                }
                
                .adv-filter-item-compact {
                    display: grid;
                    grid-template-columns: 1fr auto;
                    gap: 6px;
                    align-items: center;
                }
                
                .adv-filter-badge {
                    display: inline-block;
                    padding: 4px 8px;
                    background: var(--accent);
                    color: var(--text-inverted);
                    border-radius: 12px;
                    font-size: 10px;
                    font-weight: 600;
                }
                
                .adv-filter-remove-btn {
                    background: var(--error, #ef4444);
                    color: var(--text-inverted);
                    border: none;
                    border-radius: 4px;
                    padding: 4px 8px;
                    cursor: pointer;
                    font-size: 11px;
                }
                
                .adv-filter-add-btn {
                    background: var(--accent);
                    color: var(--text-inverted);
                    border: none;
                    border-radius: 6px;
                    padding: 8px 12px;
                    cursor: pointer;
                    font-weight: 600;
                    font-size: 12px;
                    width: 100%;
                }
                
                .adv-collapse-group {
                    background: var(--hover);
                    padding: 8px;
                    border-radius: 6px;
                    margin-bottom: 6px;
                    border-left: 3px solid var(--accent);
                }
                
                .adv-collapse-count {
                    background: var(--accent);
                    color: var(--text-inverted);
                    padding: 2px 6px;
                    border-radius: 10px;
                    font-size: 10px;
                    font-weight: 600;
                }
                </style>
                
                <div class="adv-filter-section">
                    <div class="adv-filter-title">
                        🔬 Advanced Filters
                    </div>
                    
                    <!-- Session Filter -->
                    <div class="adv-filter-box">
                        <div style="color: var(--text-secondary); font-size: 12px; font-weight: 600; margin-bottom: 8px;">
                            Session Filter
                        </div>
                        
                        <select id="adv-session-mode" class="graph-setting-select" 
                                onchange="window.GraphAdvancedFilters.setSessionMode(this.value)"
                                style="margin-bottom: 8px;">
                            <option value="all">All Nodes</option>
                            <option value="session-only">Session Only</option>
                            <option value="session-recent">Session + Recent</option>
                            <option value="inferred">Inferred Relationships (INF_REL)</option>
                            <option value="hybrid">Session + Inferred</option>
                            <option value="direct-only">Direct Connections Only</option>
                            <option value="time-range">Time Range</option>
                        </select>
                        
                        <div id="session-selector-container" style="display: none;">
                            <label class="graph-setting-label" style="font-size: 11px; margin-bottom: 4px;">
                                Select Session
                            </label>
                            <select id="adv-session-id" class="graph-setting-select"
                                    onchange="window.GraphAdvancedFilters.setSessionId(this.value)">
                                <option value="">-- Select Session --</option>
                            </select>
                        </div>
                        
                        <div id="time-range-container" style="display: none; margin-top: 12px;">
                            <div style="margin-bottom: 8px;">
                                <label class="graph-setting-label" style="font-size: 11px;">Time Property</label>
                                <select id="adv-time-property" class="graph-setting-select"
                                        onchange="window.GraphAdvancedFilters.setTimeProperty(this.value)">
                                    <option value="created_at">created_at</option>
                                    <option value="updated_at">updated_at</option>
                                    <option value="timestamp">timestamp</option>
                                </select>
                            </div>
                            
                            <div style="background: var(--bg); padding: 12px; border-radius: 6px; margin-bottom: 8px;">
                                <div style="font-size: 10px; color: var(--text-secondary); margin-bottom: 8px;">
                                    Time Range
                                </div>
                                
                                <div style="margin-bottom: 12px;">
                                    <div style="font-size: 10px; color: var(--text-secondary); margin-bottom: 4px;">
                                        Start: <span id="time-start-display">--</span>
                                    </div>
                                    <input type="range" id="time-start-slider" min="0" max="100" value="0" 
                                           style="width: 100%;"
                                           oninput="window.GraphAdvancedFilters.handleSliderInput(this, 'start', event)"
                                           onchange="window.GraphAdvancedFilters.applyAllFilters()">
                                </div>
                                
                                <div style="margin-bottom: 12px;">
                                    <div style="font-size: 10px; color: var(--text-secondary); margin-bottom: 4px;">
                                        End: <span id="time-end-display">--</span>
                                    </div>
                                    <input type="range" id="time-end-slider" min="0" max="100" value="100"
                                           style="width: 100%;"
                                           oninput="window.GraphAdvancedFilters.handleSliderInput(this, 'end', event)"
                                           onchange="window.GraphAdvancedFilters.applyAllFilters()">
                                </div>
                                
                                <div style="font-size: 10px; color: var(--text-secondary); text-align: center; margin-top: 8px; padding-top: 8px; border-top: 1px solid var(--border-subtle);">
                                    💡 Hold Ctrl to move entire range
                                </div>
                            </div>
                            
                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px;">
                                <button onclick="window.GraphAdvancedFilters.resetTimeRange()" 
                                        class="graph-btn graph-btn-secondary" style="font-size: 11px; padding: 6px;">
                                    Reset
                                </button>
                                <button onclick="window.GraphAdvancedFilters.setTimeRangeToLast24h()" 
                                        class="graph-btn graph-btn-secondary" style="font-size: 11px; padding: 6px;">
                                    Last 24h
                                </button>
                            </div>
                        </div>
                        
                        <div id="session-stats" style="margin-top: 8px; font-size: 11px; color: var(--text-secondary);">
                        </div>
                    </div>
                    
                    <!-- Node Property Filters -->
                    <div class="adv-filter-box">
                        <div style="color: var(--text-secondary); font-size: 12px; font-weight: 600; margin-bottom: 8px;">
                            Node Property Filters
                        </div>
                        
                        <div id="node-property-filters-list"></div>
                        
                        <button class="adv-filter-add-btn" 
                                onclick="window.GraphAdvancedFilters.showAddPropertyFilter('node')">
                            + Add Node Filter
                        </button>
                    </div>
                    
                    <!-- Edge Property Filters -->
                    <div class="adv-filter-box">
                        <div style="color: var(--text-secondary); font-size: 12px; font-weight: 600; margin-bottom: 8px;">
                            Edge Property Filters
                        </div>
                        
                        <div id="edge-property-filters-list"></div>
                        
                        <button class="adv-filter-add-btn"
                                onclick="window.GraphAdvancedFilters.showAddPropertyFilter('edge')">
                            + Add Edge Filter
                        </button>
                    </div>
                    
                    <!-- Node Collapse -->
                    <div class="adv-filter-box">
                        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                            <div style="color: var(--text-secondary); font-size: 12px; font-weight: 600;">
                                Collapse Nodes
                            </div>
                            <label class="toggle-switch">
                                <input type="checkbox" id="adv-collapse-nodes-enabled"
                                       onchange="window.GraphAdvancedFilters.toggleNodeCollapse(this.checked)">
                                <span class="toggle-slider"></span>
                            </label>
                        </div>
                        
                        <div id="node-collapse-controls" style="opacity: 0.5; pointer-events: none;">
                            <label class="graph-setting-label" style="font-size: 11px;">
                                Group By Properties
                            </label>
                            <div id="node-collapse-properties" style="margin-bottom: 8px;"></div>
                            
                            <button class="adv-filter-add-btn"
                                    onclick="window.GraphAdvancedFilters.addCollapseProperty('node')">
                                + Add Property
                            </button>
                            
                            <div id="node-collapse-stats" style="margin-top: 8px; font-size: 11px; color: var(--text-secondary);">
                            </div>
                        </div>
                    </div>
                    
                    <!-- Edge Collapse -->
                    <div class="adv-filter-box">
                        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                            <div style="color: var(--text-secondary); font-size: 12px; font-weight: 600;">
                                Collapse Edges
                            </div>
                            <label class="toggle-switch">
                                <input type="checkbox" id="adv-collapse-edges-enabled"
                                       onchange="window.GraphAdvancedFilters.toggleEdgeCollapse(this.checked)">
                                <span class="toggle-slider"></span>
                            </label>
                        </div>
                        
                        <div id="edge-collapse-controls" style="opacity: 0.5; pointer-events: none;">
                            <label class="graph-setting-label" style="font-size: 11px;">
                                Group By Properties
                            </label>
                            <div id="edge-collapse-properties" style="margin-bottom: 8px;"></div>
                            
                            <button class="adv-filter-add-btn"
                                    onclick="window.GraphAdvancedFilters.addCollapseProperty('edge')">
                                + Add Property
                            </button>
                            
                            <div id="edge-collapse-stats" style="margin-top: 8px; font-size: 11px; color: var(--text-secondary);">
                            </div>
                        </div>
                    </div>
                    
                    <!-- Action Buttons -->
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 12px;">
                        <button onclick="window.GraphAdvancedFilters.applyAllFilters()" class="graph-btn">
                            Apply Filters
                        </button>
                        <button onclick="window.GraphAdvancedFilters.clearAllFilters()" class="graph-btn graph-btn-secondary">
                            Clear All
                        </button>
                    </div>
                    
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 8px;">
                        <button onclick="window.GraphAdvancedFilters.expandAllCollapsed()" class="graph-btn graph-btn-secondary">
                            Expand All
                        </button>
                        <button onclick="window.GraphAdvancedFilters.exportFilteredView()" class="graph-btn graph-btn-secondary">
                            Export View
                        </button>
                    </div>
                    
                    <div style="margin-top: 8px;">
                        <button onclick="window.GraphAdvancedFilters.refreshDiscovery()" class="graph-btn graph-btn-secondary" style="width: 100%;">
                            🔄 Refresh Properties
                        </button>
                        <div id="adv-filter-discovery-status" style="font-size: 10px; color: var(--text-secondary); margin-top: 6px; padding: 6px; background: var(--bg); border-radius: 4px; text-align: left;">
                            <div>📊 Discovered:</div>
                            <div style="margin-left: 8px;">
                                • <span id="node-props-count">0</span> node properties
                            </div>
                            <div style="margin-left: 8px;">
                                • <span id="edge-props-count">0</span> edge properties
                            </div>
                            <div style="margin-left: 8px;">
                                • <span id="sessions-count">0</span> sessions
                            </div>
                        </div>
                    </div>
                </div>
            `;
            
            // Find where to insert (after Graph Style Control section)
            const styleSection = settingsPanel.querySelector('.graph-settings-section');
            if (styleSection) {
                styleSection.insertAdjacentHTML('afterend', filterControls);
            } else {
                settingsPanel.insertAdjacentHTML('afterbegin', filterControls);
            }
            
            // Populate session selector
            this.populateSessionSelector();
            
            // Sync UI with current state
            this.syncUI();
        },
        
        /**
         * Populate session selector dropdown
         */
        populateSessionSelector: function() {
            const selector = document.getElementById('adv-session-id');
            if (!selector) return;
            
            selector.innerHTML = '<option value="">-- Select Session --</option>';
            this.filters.session.availableSessions.forEach(sessionId => {
                const option = document.createElement('option');
                option.value = sessionId;
                option.textContent = sessionId;
                selector.appendChild(option);
            });
        },
        
        /**
         * Set session filter mode
         */
        setSessionMode: function(mode) {
            this.filters.session.mode = mode;
            
            const sessionContainer = document.getElementById('session-selector-container');
            const timeContainer = document.getElementById('time-range-container');
            
            if (sessionContainer) {
                const needsSession = ['session-only', 'session-recent', 'hybrid', 'direct-only'].includes(mode);
                sessionContainer.style.display = needsSession ? 'block' : 'none';
            }
            
            if (timeContainer) {
                timeContainer.style.display = (mode === 'time-range') ? 'block' : 'none';
            }
            
            this.saveFilters();
            this.updateSessionStats();
        },
        
        /**
         * Populate time property selector
         */
        populateTimePropertySelector: function() {
            const selector = document.getElementById('adv-time-property');
            if (!selector) return;
            
            const timeProps = Array.from(this.availableProperties.nodes).filter(prop => 
                prop.includes('time') || prop.includes('date') || prop.includes('created') || prop.includes('updated')
            );
            
            if (timeProps.length > 0) {
                selector.innerHTML = timeProps.map(prop => 
                    `<option value="${prop}">${prop}</option>`
                ).join('');
                
                if (this.filters.timeRange.propertyName && timeProps.includes(this.filters.timeRange.propertyName)) {
                    selector.value = this.filters.timeRange.propertyName;
                }
            }
        },
        
        /**
         * Set time property for filtering
         */
        setTimeProperty: function(propertyName) {
            this.filters.timeRange.propertyName = propertyName;
            
            // Re-discover time range for this property
            this.discoverTimeRange();
            this.updateTimeSliders();
            this.saveFilters();
        },
        
        /**
         * Handle slider input with Ctrl key detection
         */
        handleSliderInput: function(slider, type, event) {
            const isCtrlHeld = event && (event.ctrlKey || event.metaKey);
            
            if (type === 'start') {
                this.updateTimeStart(slider.value, isCtrlHeld);
            } else {
                this.updateTimeEnd(slider.value, isCtrlHeld);
            }
        },
        
        /**
         * Update time range start
         */
        updateTimeStart: function(value, isCtrlHeld) {
            const { minTime, maxTime, endTime } = this.filters.timeRange;
            if (minTime === null || maxTime === null) return;
            
            const range = maxTime - minTime;
            const newStart = minTime + (range * value / 100);
            
            // Hold Ctrl to move entire range
            if (isCtrlHeld && endTime) {
                const currentWidth = endTime - this.filters.timeRange.startTime;
                this.filters.timeRange.startTime = newStart;
                this.filters.timeRange.endTime = Math.min(newStart + currentWidth, maxTime);
                
                // Update end slider too
                const endSlider = document.getElementById('time-end-slider');
                if (endSlider) {
                    const endPercent = ((this.filters.timeRange.endTime - minTime) / range) * 100;
                    endSlider.value = endPercent;
                }
            } else {
                this.filters.timeRange.startTime = Math.min(newStart, endTime || maxTime);
            }
            
            this.updateTimeDisplay();
        },
        
        /**
         * Update time range end
         */
        updateTimeEnd: function(value, isCtrlHeld) {
            const { minTime, maxTime, startTime } = this.filters.timeRange;
            if (minTime === null || maxTime === null) return;
            
            const range = maxTime - minTime;
            const newEnd = minTime + (range * value / 100);
            
            // Hold Ctrl to move entire range
            if (isCtrlHeld && startTime) {
                const currentWidth = this.filters.timeRange.endTime - startTime;
                this.filters.timeRange.endTime = newEnd;
                this.filters.timeRange.startTime = Math.max(newEnd - currentWidth, minTime);
                
                // Update start slider too
                const startSlider = document.getElementById('time-start-slider');
                if (startSlider) {
                    const startPercent = ((this.filters.timeRange.startTime - minTime) / range) * 100;
                    startSlider.value = startPercent;
                }
            } else {
                this.filters.timeRange.endTime = Math.max(newEnd, startTime || minTime);
            }
            
            this.updateTimeDisplay();
        },
        
        /**
         * Update time display labels
         */
        updateTimeDisplay: function() {
            const startDisplay = document.getElementById('time-start-display');
            const endDisplay = document.getElementById('time-end-display');
            
            if (startDisplay && this.filters.timeRange.startTime) {
                startDisplay.textContent = new Date(this.filters.timeRange.startTime).toLocaleString();
            }
            
            if (endDisplay && this.filters.timeRange.endTime) {
                endDisplay.textContent = new Date(this.filters.timeRange.endTime).toLocaleString();
            }
        },
        
        /**
         * Update time sliders to match current range
         */
        updateTimeSliders: function() {
            const { minTime, maxTime, startTime, endTime } = this.filters.timeRange;
            if (minTime === null || maxTime === null) return;
            
            const range = maxTime - minTime;
            
            const startSlider = document.getElementById('time-start-slider');
            const endSlider = document.getElementById('time-end-slider');
            
            if (startSlider && startTime) {
                const startPercent = ((startTime - minTime) / range) * 100;
                startSlider.value = startPercent;
            }
            
            if (endSlider && endTime) {
                const endPercent = ((endTime - minTime) / range) * 100;
                endSlider.value = endPercent;
            }
            
            this.updateTimeDisplay();
        },
        
        /**
         * Reset time range to full span
         */
        resetTimeRange: function() {
            this.filters.timeRange.startTime = this.filters.timeRange.minTime;
            this.filters.timeRange.endTime = this.filters.timeRange.maxTime;
            this.updateTimeSliders();
            this.saveFilters();
        },
        
        /**
         * Set time range to last 24 hours
         */
        setTimeRangeToLast24h: function() {
            const now = this.filters.timeRange.maxTime || Date.now();
            const oneDayAgo = now - (24 * 60 * 60 * 1000);
            
            this.filters.timeRange.startTime = Math.max(oneDayAgo, this.filters.timeRange.minTime);
            this.filters.timeRange.endTime = this.filters.timeRange.maxTime;
            this.updateTimeSliders();
            this.saveFilters();
        },
        
        /**
         * Set selected session ID
         */
        setSessionId: function(sessionId) {
            this.filters.session.selectedSessionId = sessionId || null;
            this.saveFilters();
            this.updateSessionStats();
        },
        
        /**
         * Update session filter statistics
         */
        updateSessionStats: function() {
            const stats = document.getElementById('session-stats');
            if (!stats) return;
            
            const mode = this.filters.session.mode;
            const sessionId = this.filters.session.selectedSessionId;
            
            if (mode === 'all') {
                stats.textContent = 'Showing all nodes and edges';
                return;
            }
            
            if (!sessionId) {
                stats.textContent = 'Please select a session';
                return;
            }
            
            // Count nodes/edges in session
            let nodeCount = 0;
            let edgeCount = 0;
            
            Object.values(this.graphAddon.nodesData).forEach(node => {
                const nodeSessionId = node.properties?.session_id || 
                                     node.properties?.sessionId || 
                                     node.properties?.session;
                
                if (nodeSessionId === sessionId) {
                    nodeCount++;
                }
            });
            
            stats.textContent = `${nodeCount} nodes in session "${sessionId}"`;
        },
        
        /**
         * Ensure property panel exists
         */
        ensurePropertyPanel: function() {
            let panel = document.getElementById('adv-filter-property-panel');
            if (!panel) {
                panel = document.createElement('div');
                panel.id = 'adv-filter-property-panel';
                panel.style.cssText = `
                    display: none;
                    position: fixed;
                    top: 0;
                    right: 0;
                    width: 400px;
                    height: 100vh;
                    background: var(--bg-surface);
                    border-left: 1px solid var(--border);
                    box-shadow: -4px 0 20px rgba(0, 0, 0, 0.5);
                    z-index: 10000;
                    flex-direction: column;
                    overflow-y: auto;
                `;
                document.body.appendChild(panel);
            }
            return panel;
        },
        
        /**
         * Close property panel
         */
        closePropertyPanel: function() {
            const panel = document.getElementById('adv-filter-property-panel');
            if (panel) {
                panel.style.display = 'none';
            }
        },
        
        /**
         * Show dialog to add property filter
         */
        showAddPropertyFilter: function(type) {
            const panel = this.ensurePropertyPanel();
            
            console.log('Opening property filter dialog for:', type);
            
            const properties = type === 'node' 
                ? Array.from(this.availableProperties.nodes)
                : Array.from(this.availableProperties.edges);
            
            console.log(`Found ${properties.length} ${type} properties:`, properties);
            
            let propertiesHTML;
            if (properties.length === 0) {
                propertiesHTML = `
                    <div style="text-align: center; padding: 20px; color: var(--text-secondary);">
                        <div style="font-size: 14px; margin-bottom: 12px;">⚠️ No properties discovered</div>
                        <div style="font-size: 11px; margin-bottom: 16px;">
                            Make sure your graph data is loaded, then click "Refresh Properties"
                        </div>
                        <button onclick="window.GraphAdvancedFilters.refreshDiscovery(); window.GraphAdvancedFilters.closePropertyPanel();" 
                                class="graph-btn" style="width: 100%;">
                            🔄 Refresh Properties
                        </button>
                    </div>
                `;
            } else {
                propertiesHTML = `
                    <div style="margin-bottom: 12px;">
                        <label class="graph-setting-label">Property</label>
                        <select id="filter-property-name" class="graph-setting-select" 
                                onchange="window.GraphAdvancedFilters.updateFilterValueOptions('${type}')">
                            ${properties.map(prop => `<option value="${this.escapeHtml(prop)}">${this.escapeHtml(prop)}</option>`).join('')}
                        </select>
                    </div>
                    
                    <div style="margin-bottom: 12px;">
                        <label class="graph-setting-label">Operator</label>
                        <select id="filter-operator" class="graph-setting-select"
                                onchange="window.GraphAdvancedFilters.updateFilterValueMode()">
                            <option value="equals">Equals</option>
                            <option value="contains">Contains</option>
                            <option value="regex">Regex Match</option>
                            <option value="exists">Exists</option>
                            <option value="not-exists">Does Not Exist</option>
                            <option value="greater">Greater Than</option>
                            <option value="less">Less Than</option>
                        </select>
                    </div>
                    
                    <div id="filter-value-container" style="margin-bottom: 16px;">
                        <label class="graph-setting-label">Value</label>
                        <div style="display: flex; gap: 6px; margin-bottom: 6px;">
                            <select id="filter-value-select" class="graph-setting-select" 
                                    style="flex: 1;"
                                    onchange="window.GraphAdvancedFilters.onFilterValueSelected()">
                                <option value="">-- Select or type below --</option>
                            </select>
                        </div>
                        <input type="text" id="filter-value-input" class="graph-setting-input" 
                               placeholder="Or enter custom value / regex">
                    </div>
                    
                    <button onclick="window.GraphAdvancedFilters.addPropertyFilter('${type}')" 
                            class="graph-btn" style="width: 100%;">
                        Add Filter
                    </button>
                `;
            }
            
            let html = `
                <div style="padding: 20px;">
                    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;">
                        <div style="color: var(--text); font-size: 16px; font-weight: 600;">
                            Add ${type === 'node' ? 'Node' : 'Edge'} Property Filter
                        </div>
                        <button onclick="window.GraphAdvancedFilters.closePropertyPanel()" style="
                            background: none; border: none; color: var(--text-secondary);
                            cursor: pointer; font-size: 20px; padding: 0;
                        ">✕</button>
                    </div>
                    
                    ${propertiesHTML}
                </div>
            `;
            
            panel.innerHTML = html;
            panel.style.display = 'flex';
            
            // Initialize value options for first property
            if (properties.length > 0) {
                this.updateFilterValueOptions(type);
            }
            
            // Set up operator change handler
            this.updateFilterValueMode();
        },
        
        /**
         * Update filter value options based on selected property
         */
        updateFilterValueOptions: function(type) {
            const propertyName = document.getElementById('filter-property-name')?.value;
            const valueSelect = document.getElementById('filter-value-select');
            
            if (!propertyName || !valueSelect) return;
            
            // Get unique values for this property
            const values = new Set();
            
            if (type === 'node') {
                Object.values(this.graphAddon.nodesData || {}).forEach(node => {
                    let value;
                    if (node.properties && propertyName in node.properties) {
                        value = node.properties[propertyName];
                    } else if (propertyName in node) {
                        value = node[propertyName];
                    } else if (propertyName === 'labels' && node.labels) {
                        value = node.labels.join(',');
                    }
                    
                    if (value !== undefined && value !== null) {
                        values.add(String(value));
                    }
                });
            } else {
                if (typeof network !== 'undefined' && network.body && network.body.data) {
                    network.body.data.edges.forEach(edge => {
                        if (propertyName in edge) {
                            const value = edge[propertyName];
                            if (value !== undefined && value !== null) {
                                values.add(String(value));
                            }
                        }
                    });
                }
            }
            
            // Populate dropdown
            valueSelect.innerHTML = '<option value="">-- Select or type below --</option>';
            
            // Sort and limit to prevent huge dropdowns
            const sortedValues = Array.from(values).sort().slice(0, 100);
            sortedValues.forEach(value => {
                const displayValue = value.length > 50 ? value.substring(0, 50) + '...' : value;
                const option = document.createElement('option');
                option.value = value;
                option.textContent = displayValue;
                valueSelect.appendChild(option);
            });
            
            if (sortedValues.length === 100) {
                const option = document.createElement('option');
                option.disabled = true;
                option.textContent = `... (${values.size - 100} more)`;
                valueSelect.appendChild(option);
            }
            
            console.log(`Found ${values.size} unique values for ${propertyName}`);
        },
        
        /**
         * When value selected from dropdown, copy to input
         */
        onFilterValueSelected: function() {
            const select = document.getElementById('filter-value-select');
            const input = document.getElementById('filter-value-input');
            
            if (select && input && select.value) {
                input.value = select.value;
            }
        },
        
        /**
         * Update filter value mode based on operator
         */
        updateFilterValueMode: function() {
            const operator = document.getElementById('filter-operator')?.value;
            const valueContainer = document.getElementById('filter-value-container');
            
            if (!valueContainer) return;
            
            const needsValue = !['exists', 'not-exists'].includes(operator);
            valueContainer.style.display = needsValue ? 'block' : 'none';
            
            // Update placeholder for regex
            const input = document.getElementById('filter-value-input');
            if (input && operator === 'regex') {
                input.placeholder = 'Enter regex pattern (e.g., ^test.*$)';
            } else if (input) {
                input.placeholder = 'Or enter custom value';
            }
        },
        
        /**
         * Add property filter
         */
        addPropertyFilter: function(type) {
            const propertyName = document.getElementById('filter-property-name')?.value;
            const operator = document.getElementById('filter-operator')?.value;
            const value = document.getElementById('filter-value-input')?.value;  // Changed to -input
            
            if (!propertyName) {
                console.warn('No property name selected');
                return;
            }
            
            const filterKey = `${propertyName}_${Date.now()}`;
            const filterDef = {
                propertyName,
                operator,
                value,
                enabled: true
            };
            
            if (type === 'node') {
                this.filters.nodeProperties[filterKey] = filterDef;
                console.log('Added node filter:', filterDef);
            } else {
                this.filters.edgeProperties[filterKey] = filterDef;
                console.log('Added edge filter:', filterDef);
            }
            
            this.saveFilters();
            this.syncUI();
            
            // Close panel
            this.closePropertyPanel();
        },
        
        /**
         * Remove property filter
         */
        removePropertyFilter: function(type, filterKey) {
            if (type === 'node') {
                delete this.filters.nodeProperties[filterKey];
            } else {
                delete this.filters.edgeProperties[filterKey];
            }
            
            this.saveFilters();
            this.syncUI();
        },
        
        /**
         * Toggle property filter enabled state
         */
        togglePropertyFilter: function(type, filterKey, enabled) {
            const filter = type === 'node' 
                ? this.filters.nodeProperties[filterKey]
                : this.filters.edgeProperties[filterKey];
            
            if (filter) {
                filter.enabled = enabled;
                this.saveFilters();
            }
        },
        
        /**
         * Toggle node collapse
         */
        toggleNodeCollapse: function(enabled) {
            this.filters.collapse.nodes.enabled = enabled;
            
            const controls = document.getElementById('node-collapse-controls');
            if (controls) {
                controls.style.opacity = enabled ? '1' : '0.5';
                controls.style.pointerEvents = enabled ? 'auto' : 'none';
            }
            
            if (!enabled) {
                // Clean up when disabling
                this.cleanupCollapsedNodes();
            }
            
            this.saveFilters();
        },
        
        /**
         * Toggle edge collapse
         */
        toggleEdgeCollapse: function(enabled) {
            this.filters.collapse.edges.enabled = enabled;
            
            const controls = document.getElementById('edge-collapse-controls');
            if (controls) {
                controls.style.opacity = enabled ? '1' : '0.5';
                controls.style.pointerEvents = enabled ? 'auto' : 'none';
            }
            
            this.saveFilters();
        },
        
        /**
         * Add collapse property
         */
        addCollapseProperty: function(type) {
            const panel = this.ensurePropertyPanel();
            
            console.log('Opening collapse property dialog for:', type);
            
            const properties = type === 'node'
                ? Array.from(this.availableProperties.nodes)
                : Array.from(this.availableProperties.edges);
            
            const existingProps = type === 'node'
                ? this.filters.collapse.nodes.groupBy
                : this.filters.collapse.edges.groupBy;
            
            // Filter out already selected properties
            const availableProps = properties.filter(p => !existingProps.includes(p));
            
            console.log(`Found ${availableProps.length} available properties for collapse`);
            
            let contentHTML;
            if (availableProps.length === 0 && properties.length === 0) {
                contentHTML = `
                    <div style="text-align: center; padding: 20px; color: var(--text-secondary);">
                        <div style="font-size: 14px; margin-bottom: 12px;">⚠️ No properties discovered</div>
                        <div style="font-size: 11px; margin-bottom: 16px;">
                            Make sure your graph data is loaded, then click "Refresh Properties"
                        </div>
                        <button onclick="window.GraphAdvancedFilters.refreshDiscovery(); window.GraphAdvancedFilters.closePropertyPanel();" 
                                class="graph-btn" style="width: 100%;">
                            🔄 Refresh Properties
                        </button>
                    </div>
                `;
            } else if (availableProps.length === 0) {
                contentHTML = `
                    <div style="text-align: center; padding: 20px; color: var(--text-secondary);">
                        <div style="font-size: 14px; margin-bottom: 12px;">All properties already added</div>
                        <div style="font-size: 11px; margin-bottom: 16px;">
                            Remove existing properties to add different ones
                        </div>
                        <button onclick="window.GraphAdvancedFilters.closePropertyPanel();" 
                                class="graph-btn graph-btn-secondary" style="width: 100%;">
                            Close
                        </button>
                    </div>
                `;
            } else {
                contentHTML = `
                    <div style="margin-bottom: 16px;">
                        <label class="graph-setting-label">Property</label>
                        <select id="collapse-property-name" class="graph-setting-select">
                            ${availableProps.map(prop => `<option value="${this.escapeHtml(prop)}">${this.escapeHtml(prop)}</option>`).join('')}
                        </select>
                    </div>
                    
                    <div style="color: var(--text-secondary); font-size: 11px; margin-bottom: 16px;">
                        ${type === 'node' ? 'Nodes' : 'Edges'} with the same value for this property will be grouped together.
                    </div>
                    
                    <button onclick="window.GraphAdvancedFilters.confirmAddCollapseProperty('${type}')"
                            class="graph-btn" style="width: 100%;">
                        Add Property
                    </button>
                `;
            }
            
            let html = `
                <div style="padding: 20px;">
                    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;">
                        <div style="color: var(--text); font-size: 16px; font-weight: 600;">
                            Add Collapse Property
                        </div>
                        <button onclick="window.GraphAdvancedFilters.closePropertyPanel()" style="
                            background: none; border: none; color: var(--text-secondary);
                            cursor: pointer; font-size: 20px; padding: 0;
                        ">✕</button>
                    </div>
                    
                    ${contentHTML}
                </div>
            `;
            
            panel.innerHTML = html;
            panel.style.display = 'flex';
        },
        
        /**
         * Confirm add collapse property
         */
        confirmAddCollapseProperty: function(type) {
            const propertyName = document.getElementById('collapse-property-name')?.value;
            
            if (!propertyName) {
                console.warn('No property selected');
                return;
            }
            
            if (type === 'node') {
                if (!this.filters.collapse.nodes.groupBy.includes(propertyName)) {
                    this.filters.collapse.nodes.groupBy.push(propertyName);
                    console.log('Added node collapse property:', propertyName);
                }
            } else {
                if (!this.filters.collapse.edges.groupBy.includes(propertyName)) {
                    this.filters.collapse.edges.groupBy.push(propertyName);
                    console.log('Added edge collapse property:', propertyName);
                }
            }
            
            // Clean up since grouping has changed
            this.cleanupCollapsedNodes();
            
            this.saveFilters();
            this.syncUI();
            
            // Close panel
            this.closePropertyPanel();
        },
        
        /**
         * Remove collapse property
         */
        removeCollapseProperty: function(type, propertyName) {
            if (type === 'node') {
                this.filters.collapse.nodes.groupBy = 
                    this.filters.collapse.nodes.groupBy.filter(p => p !== propertyName);
            } else {
                this.filters.collapse.edges.groupBy = 
                    this.filters.collapse.edges.groupBy.filter(p => p !== propertyName);
            }
            
            // Clean up since grouping has changed
            this.cleanupCollapsedNodes();
            
            this.saveFilters();
            this.syncUI();
        },
        
        /**
         * Apply all filters and collapse operations
         */
        applyAllFilters: function() {
            if (!network || !network.body || !network.body.data) return;
            
            console.log('Applying advanced filters...');
            
            // Cache original data if not already cached
            if (this.originalData.nodes.size === 0) {
                network.body.data.nodes.forEach(node => {
                    this.originalData.nodes.set(node.id, { ...node });
                });
            }
            if (this.originalData.edges.size === 0) {
                network.body.data.edges.forEach(edge => {
                    this.originalData.edges.set(edge.id, { ...edge });
                });
            }
            
            // Apply session filter
            const sessionFiltered = this.applySessionFilter();
            
            // Apply property filters
            const propertyFiltered = this.applyPropertyFilters(sessionFiltered);
            
            // Apply collapse operations
            const { nodes: finalNodes, edges: finalEdges } = this.applyCollapseOperations(propertyFiltered);
            
            // Update network
            const nodeUpdates = Array.from(this.originalData.nodes.values()).map(node => ({
                id: node.id,
                hidden: !finalNodes.has(node.id)
            }));
            
            const edgeUpdates = Array.from(this.originalData.edges.values()).map(edge => ({
                id: edge.id,
                hidden: !finalEdges.has(edge.id)
            }));
            
            network.body.data.nodes.update(nodeUpdates);
            network.body.data.edges.update(edgeUpdates);
            
            // Update stats
            this.updateFilterStats(finalNodes.size, finalEdges.size);
            
            console.log(`Filters applied: ${finalNodes.size} nodes, ${finalEdges.size} edges visible`);
        },
        
        /**
         * Apply session filter
         */
        applySessionFilter: function() {
            const { mode, selectedSessionId } = this.filters.session;
            
            const visibleNodes = new Set();
            const visibleEdges = new Set();
            
            if (mode === 'all') {
                // Show all
                this.originalData.nodes.forEach((node, id) => visibleNodes.add(id));
                this.originalData.edges.forEach((edge, id) => visibleEdges.add(id));
                return { nodes: visibleNodes, edges: visibleEdges };
            }
            
            if (mode === 'time-range') {
                // Filter by time range
                return this.applyTimeRangeFilter();
            }
            
            if (!selectedSessionId && mode !== 'inferred') {
                // Need a session selected for these modes
                this.originalData.nodes.forEach((node, id) => visibleNodes.add(id));
                this.originalData.edges.forEach((edge, id) => visibleEdges.add(id));
                return { nodes: visibleNodes, edges: visibleEdges };
            }
            
            // Find nodes in session
            const sessionNodes = new Set();
            Object.entries(this.graphAddon.nodesData).forEach(([nodeId, nodeData]) => {
                const nodeSessionId = nodeData.properties?.session_id ||
                                     nodeData.properties?.sessionId ||
                                     nodeData.properties?.session;
                
                if (nodeSessionId === selectedSessionId) {
                    sessionNodes.add(nodeId);
                }
            });
            
            if (mode === 'session-only') {
                // Only nodes in session
                sessionNodes.forEach(id => visibleNodes.add(id));
                
                // Only edges between session nodes
                this.originalData.edges.forEach((edge, id) => {
                    if (sessionNodes.has(edge.from) && sessionNodes.has(edge.to)) {
                        visibleEdges.add(id);
                    }
                });
            } else if (mode === 'session-recent') {
                // Session nodes + recent nodes
                const recentNodes = this.getRecentNodes();
                
                sessionNodes.forEach(id => visibleNodes.add(id));
                recentNodes.forEach(id => visibleNodes.add(id));
                
                // Edges between any visible nodes
                this.originalData.edges.forEach((edge, id) => {
                    if (visibleNodes.has(edge.from) && visibleNodes.has(edge.to)) {
                        visibleEdges.add(id);
                    }
                });
            } else if (mode === 'inferred') {
                // Nodes with INF_REL edges
                const inferredNodes = new Set();
                this.originalData.edges.forEach(edge => {
                    if ((edge.label || '').includes('INF_REL') || 
                        (edge.type || '').includes('INF_REL')) {
                        inferredNodes.add(edge.from);
                        inferredNodes.add(edge.to);
                        visibleEdges.add(edge.id);
                    }
                });
                
                inferredNodes.forEach(id => visibleNodes.add(id));
            } else if (mode === 'hybrid') {
                // Session nodes + inferred relationships
                sessionNodes.forEach(id => visibleNodes.add(id));
                
                this.originalData.edges.forEach((edge, id) => {
                    const isSessionEdge = sessionNodes.has(edge.from) && sessionNodes.has(edge.to);
                    const isInferred = (edge.label || '').includes('INF_REL') || 
                                      (edge.type || '').includes('INF_REL');
                    
                    if (isSessionEdge || isInferred) {
                        visibleEdges.add(id);
                        visibleNodes.add(edge.from);
                        visibleNodes.add(edge.to);
                    }
                });
            } else if (mode === 'direct-only') {
                // Direct connections from session nodes
                sessionNodes.forEach(id => visibleNodes.add(id));
                
                this.originalData.edges.forEach((edge, id) => {
                    if (sessionNodes.has(edge.from) || sessionNodes.has(edge.to)) {
                        visibleEdges.add(id);
                        visibleNodes.add(edge.from);
                        visibleNodes.add(edge.to);
                    }
                });
            }
            
            return { nodes: visibleNodes, edges: visibleEdges };
        },
        
        /**
         * Get recent nodes based on timestamp
         */
        getRecentNodes: function() {
            const recentNodes = new Set();
            const now = Date.now();
            const oneDayAgo = now - (24 * 60 * 60 * 1000);  // Default to last 24h
            
            const timeProps = ['created_at', 'updated_at', 'timestamp', 'created', 'updated'];
            
            Object.entries(this.graphAddon.nodesData).forEach(([nodeId, nodeData]) => {
                if (nodeData.properties) {
                    for (const prop of timeProps) {
                        if (nodeData.properties[prop]) {
                            const timeValue = this.parseTimeValue(nodeData.properties[prop]);
                            if (timeValue && timeValue >= oneDayAgo) {
                                recentNodes.add(nodeId);
                                break;
                            }
                        }
                    }
                }
            });
            
            return recentNodes;
        },
        
        /**
         * Apply time range filter
         */
        applyTimeRangeFilter: function() {
            const visibleNodes = new Set();
            const visibleEdges = new Set();
            
            const { startTime, endTime, propertyName } = this.filters.timeRange;
            
            if (startTime === null || endTime === null) {
                // No time range set, show all
                this.originalData.nodes.forEach((node, id) => visibleNodes.add(id));
                this.originalData.edges.forEach((edge, id) => visibleEdges.add(id));
                return { nodes: visibleNodes, edges: visibleEdges };
            }
            
            // Filter nodes by time
            Object.entries(this.graphAddon.nodesData).forEach(([nodeId, nodeData]) => {
                let nodeTime = null;
                
                if (nodeData.properties && nodeData.properties[propertyName]) {
                    nodeTime = this.parseTimeValue(nodeData.properties[propertyName]);
                }
                
                if (nodeTime && nodeTime >= startTime && nodeTime <= endTime) {
                    visibleNodes.add(nodeId);
                }
            });
            
            // Include edges between visible nodes
            this.originalData.edges.forEach((edge, id) => {
                if (visibleNodes.has(edge.from) && visibleNodes.has(edge.to)) {
                    visibleEdges.add(id);
                }
            });
            
            return { nodes: visibleNodes, edges: visibleEdges };
        },
        
        /**
         * Apply property filters
         */
        applyPropertyFilters: function({ nodes, edges }) {
            const filteredNodes = new Set(nodes);
            const filteredEdges = new Set(edges);
            
            // Apply node property filters
            Object.entries(this.filters.nodeProperties).forEach(([key, filter]) => {
                if (!filter.enabled) return;
                
                filteredNodes.forEach(nodeId => {
                    const nodeData = this.graphAddon.nodesData[nodeId];
                    if (!this.matchesFilter(nodeData, filter)) {
                        filteredNodes.delete(nodeId);
                    }
                });
            });
            
            // Apply edge property filters
            Object.entries(this.filters.edgeProperties).forEach(([key, filter]) => {
                if (!filter.enabled) return;
                
                filteredEdges.forEach(edgeId => {
                    const edge = this.originalData.edges.get(edgeId);
                    if (!this.matchesFilter(edge, filter)) {
                        filteredEdges.delete(edgeId);
                    }
                });
            });
            
            // Remove edges with hidden nodes
            filteredEdges.forEach(edgeId => {
                const edge = this.originalData.edges.get(edgeId);
                if (!filteredNodes.has(edge.from) || !filteredNodes.has(edge.to)) {
                    filteredEdges.delete(edgeId);
                }
            });
            
            return { nodes: filteredNodes, edges: filteredEdges };
        },
        
        /**
         * Check if item matches filter
         */
        matchesFilter: function(item, filter) {
            if (!item) return false;
            
            const { propertyName, operator, value } = filter;
            let itemValue;
            
            // Get property value
            if (item.properties && propertyName in item.properties) {
                itemValue = item.properties[propertyName];
            } else if (propertyName in item) {
                itemValue = item[propertyName];
            } else if (propertyName === 'labels' && item.labels) {
                itemValue = item.labels.join(',');
            }
            
            // Apply operator
            switch (operator) {
                case 'exists':
                    return itemValue !== undefined && itemValue !== null;
                case 'not-exists':
                    return itemValue === undefined || itemValue === null;
                case 'equals':
                    return String(itemValue) === String(value);
                case 'contains':
                    return String(itemValue).toLowerCase().includes(String(value).toLowerCase());
                case 'regex':
                    try {
                        const regex = new RegExp(value);
                        return regex.test(String(itemValue));
                    } catch (e) {
                        console.warn('Invalid regex:', value, e);
                        return false;
                    }
                case 'greater':
                    return Number(itemValue) > Number(value);
                case 'less':
                    return Number(itemValue) < Number(value);
                default:
                    return true;
            }
        },
        
        /**
         * Clean up all collapsed nodes and edges - restore to original state
         */
        cleanupCollapsedNodes: function() {
            console.log('Cleaning up all collapsed nodes...');
            
            // Find and remove all representative nodes
            const representativeNodesToRemove = [];
            const collapsedEdgesToRemove = [];
            const constituentNodesToRestore = new Set();
            
            try {
                // Find all collapsed nodes and edges
                network.body.data.nodes.forEach(node => {
                    if (node._isCollapsed) {
                        representativeNodesToRemove.push(node.id);
                        // Collect constituent IDs to restore
                        if (node._constituentIds) {
                            node._constituentIds.forEach(id => constituentNodesToRestore.add(id));
                        }
                    }
                });
                
                network.body.data.edges.forEach(edge => {
                    if (edge._isCollapsedEdge) {
                        collapsedEdgesToRemove.push(edge.id);
                    }
                });
                
                // Remove representative nodes
                if (representativeNodesToRemove.length > 0) {
                    network.body.data.nodes.remove(representativeNodesToRemove);
                    console.log(`Removed ${representativeNodesToRemove.length} representative nodes`);
                }
                
                // Remove collapsed edges
                if (collapsedEdgesToRemove.length > 0) {
                    network.body.data.edges.remove(collapsedEdgesToRemove);
                    console.log(`Removed ${collapsedEdgesToRemove.length} collapsed edges`);
                }
                
                // Restore constituent nodes (unhide them)
                if (constituentNodesToRestore.size > 0) {
                    const nodesToRestore = Array.from(constituentNodesToRestore).map(id => ({
                        id: id,
                        hidden: false
                    }));
                    network.body.data.nodes.update(nodesToRestore);
                    console.log(`Restored ${nodesToRestore.length} constituent nodes`);
                }
                
            } catch (e) {
                console.warn('Error during cleanup:', e);
            }
            
            // Clear the collapsed state
            this.filters.collapse.nodes.collapsed.clear();
            this.filters.collapse.edges.collapsed.clear();
            
            console.log('Cleanup complete');
        },
        
        /**
         * Apply collapse operations
         */
        applyCollapseOperations: function({ nodes, edges }) {
            let resultNodes = new Set(nodes);
            let resultEdges = new Set(edges);
            
            // ALWAYS cleanup existing collapsed nodes first
            this.cleanupCollapsedNodes();
            
            // Collapse nodes
            if (this.filters.collapse.nodes.enabled && this.filters.collapse.nodes.groupBy.length > 0) {
                const { nodes: collapsedNodes, groups } = this.collapseNodes(resultNodes);
                
                // Hide original nodes that were collapsed
                groups.forEach((group, key) => {
                    group.memberIds.forEach(nodeId => {
                        resultNodes.delete(nodeId);  // Remove from visible set
                    });
                    resultNodes.add(group.representativeId);  // Add representative
                });
                
                this.filters.collapse.nodes.collapsed = groups;
            } else {
                this.filters.collapse.nodes.collapsed.clear();
            }
            
            // Collapse edges
            if (this.filters.collapse.edges.enabled && this.filters.collapse.edges.groupBy.length > 0) {
                const { edges: collapsedEdges, groups } = this.collapseEdges(resultEdges, resultNodes);
                resultEdges = collapsedEdges;
                this.filters.collapse.edges.collapsed = groups;
            } else {
                this.filters.collapse.edges.collapsed.clear();
            }
            
            this.updateCollapseStats();
            
            return { nodes: resultNodes, edges: resultEdges };
        },
        
        /**
         * Remove all collapsed representative nodes
         */
        removeAllCollapsedNodes: function() {
            if (!network || !network.body || !network.body.data) return;
            
            const nodesToRemove = [];
            network.body.data.nodes.forEach(node => {
                if (node._isCollapsed) {
                    nodesToRemove.push(node.id);
                }
            });
            
            if (nodesToRemove.length > 0) {
                console.log(`Removing ${nodesToRemove.length} collapsed nodes`);
                network.body.data.nodes.remove(nodesToRemove);
            }
        },
        
        /**
         * Collapse nodes with identical properties
         */
        collapseNodes: function(visibleNodes) {
            const groupBy = this.filters.collapse.nodes.groupBy;
            const groups = new Map();
            
            // Group nodes by property values
            visibleNodes.forEach(nodeId => {
                const nodeData = this.graphAddon.nodesData[nodeId];
                if (!nodeData) return;
                
                // Create group key from properties
                const keyParts = groupBy.map(prop => {
                    if (nodeData.properties && prop in nodeData.properties) {
                        return String(nodeData.properties[prop]);
                    } else if (prop in nodeData) {
                        if (prop === 'labels' && Array.isArray(nodeData[prop])) {
                            return nodeData[prop].join(',');
                        }
                        return String(nodeData[prop]);
                    }
                    return 'null';
                });
                
                const groupKey = keyParts.join('|');
                
                if (!groups.has(groupKey)) {
                    groups.set(groupKey, []);
                }
                
                groups.get(groupKey).push(nodeId);
            });
            
            console.log(`Grouped ${visibleNodes.size} nodes into ${groups.size} groups`);
            
            const collapsedNodes = new Set();
            const representativeMap = new Map();
            
            // Create representative nodes for multi-member groups
            groups.forEach((memberIds, groupKey) => {
                if (memberIds.length === 1) {
                    // Single node, keep as-is
                    collapsedNodes.add(memberIds[0]);
                } else {
                    // Create representative node
                    const repId = `collapsed_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
                    
                    // Pick first node as basis
                    const firstNode = this.graphAddon.nodesData[memberIds[0]];
                    
                    // Collect constituent node data for GraphInfoCard
                    const constituentData = memberIds.map(id => {
                        const nodeData = this.graphAddon.nodesData[id];
                        return {
                            id: id,
                            display_name: nodeData?.display_name || id,
                            labels: nodeData?.labels || [],
                            properties: nodeData?.properties || {}
                        };
                    });
                    
                    // Create representative node data
                    const repNodeData = {
                        id: repId,
                        label: this.createCollapsedLabel(memberIds, groupKey, groupBy),
                        shape: 'hexagon',  // Different shape for collapsed nodes
                        size: 35,
                        color: {
                            background: '#f59e0b',
                            border: '#d97706',
                            highlight: {
                                background: '#fbbf24',
                                border: '#f59e0b'
                            }
                        },
                        borderWidth: 3,
                        font: {
                            color: '#ffffff',
                            size: 14,
                            bold: true
                        },
                        // Store collapse metadata
                        _isCollapsed: true,
                        _constituentIds: memberIds,
                        _constituentData: constituentData,
                        _groupKey: groupKey,
                        _groupBy: [...groupBy],
                        // Copy some properties from first node
                        _baseProperties: firstNode.properties || {}
                    };
                    
                    // Add to network
                    try {
                        network.body.data.nodes.add(repNodeData);
                        console.log(`Created representative node ${repId} for ${memberIds.length} nodes`);
                    } catch (e) {
                        console.warn('Could not add representative node:', e);
                    }
                    
                    // Reroute edges from constituent nodes to representative
                    this.rerouteEdgesToRepresentative(memberIds, repId);
                    
                    collapsedNodes.add(repId);
                    representativeMap.set(groupKey, {
                        representativeId: repId,
                        memberIds: memberIds
                    });
                }
            });
            
            // Set up click handler for expanding collapsed nodes
            if (!this._collapseClickHandlerSet) {
                const self = this;
                
                // Click handler for Ctrl+click expansion
                network.on('click', (params) => {
                    if (params.nodes.length > 0) {
                        const nodeId = params.nodes[0];
                        const node = network.body.data.nodes.get(nodeId);
                        
                        if (node && node._isCollapsed) {
                            // Check for Ctrl/Cmd key in various event structures
                            const event = params.event;
                            const isCtrlHeld = event && (
                                event.ctrlKey ||
                                event.metaKey ||
                                (event.srcEvent && (event.srcEvent.ctrlKey || event.srcEvent.metaKey))
                            );
                            
                            if (isCtrlHeld) {
                                console.log('Ctrl+click on collapsed node, expanding constituents');
                                self.expandCollapsedNode(nodeId, node);
                                
                                // Prevent further propagation
                                if (event.preventDefault) event.preventDefault();
                                if (event.stopPropagation) event.stopPropagation();
                                return false;
                            }
                            // Regular click - let it pass through to GraphInfoCard
                            // But mark the node so GraphInfoCard knows it's collapsed
                        }
                    }
                });
                
                // Hover handler - show in GraphInfoCard
                network.on('hoverNode', (params) => {
                    const node = network.body.data.nodes.get(params.node);
                    if (node && node._isCollapsed) {
                        // Show collapsed node details in info card
                        // Only if not expanded and not in inline mode
                        if (window.GraphInfoCard && !window.GraphInfoCard.isExpanded && !window.GraphInfoCard.inlineMode) {
                            self.showCollapsedNodeInCard(params.node, node);
                        }
                    }
                });
                
                this._collapseClickHandlerSet = true;
            }
            
            return { nodes: collapsedNodes, groups: representativeMap };
        },
        
        /**
         * Create label for collapsed node
         */
        createCollapsedLabel: function(memberIds, groupKey, groupBy) {
            const parts = groupKey.split('|');
            const labels = [];
            
            groupBy.forEach((prop, idx) => {
                if (parts[idx] && parts[idx] !== 'null') {
                    labels.push(`${prop}: ${parts[idx]}`);
                }
            });
            
            const labelText = labels.length > 0 ? labels.join('\n') : 'Collapsed Group';
            return `${labelText}\n\n[${memberIds.length} nodes]`;
        },
        
        /**
         * Create tooltip for collapsed node
         */
        createCollapsedTooltip: function(repNode) {
            const constituentIds = repNode._constituentIds || [];
            const groupBy = repNode._groupBy || [];
            
            let tooltip = `<div style="max-width: 300px;">`;
            tooltip += `<strong>Collapsed Group (${constituentIds.length} nodes)</strong><br><br>`;
            tooltip += `<strong>Grouped by:</strong> ${groupBy.join(', ')}<br><br>`;
            tooltip += `<strong>Click to expand</strong><br><br>`;
            tooltip += `<strong>Constituent Nodes:</strong><br>`;
            
            constituentIds.slice(0, 10).forEach(nodeId => {
                const nodeData = this.graphAddon.nodesData[nodeId];
                if (nodeData) {
                    const name = nodeData.display_name || nodeData.id || nodeId;
                    tooltip += `• ${name.substring(0, 40)}<br>`;
                }
            });
            
            if (constituentIds.length > 10) {
                tooltip += `... and ${constituentIds.length - 10} more<br>`;
            }
            
            tooltip += `</div>`;
            return tooltip;
        },
        
        /**
         * Expand a collapsed node
         */
        expandCollapsedNode: function(repId, repNode) {
            console.log('Expanding collapsed node:', repId);
            
            const constituentIds = repNode._constituentIds || [];
            const originalEdges = repNode._originalEdges || [];
            
            if (constituentIds.length === 0) {
                console.warn('No constituent IDs found');
                return;
            }
            
            // Remove all collapsed edges connected to this representative
            const collapsedEdgesToRemove = [];
            try {
                network.body.data.edges.forEach(edge => {
                    if (edge._isCollapsedEdge && edge._representativeId === repId) {
                        collapsedEdgesToRemove.push(edge.id);
                    }
                });
                
                if (collapsedEdgesToRemove.length > 0) {
                    network.body.data.edges.remove(collapsedEdgesToRemove);
                    console.log(`Removed ${collapsedEdgesToRemove.length} collapsed edges`);
                }
            } catch (e) {
                console.warn('Error removing collapsed edges:', e);
            }
            
            // Restore original edges
            if (originalEdges.length > 0) {
                try {
                    // Filter to only edges that still make sense (both nodes exist)
                    const edgesToRestore = originalEdges.filter(edge => {
                        const fromExists = network.body.data.nodes.get(edge.from) || constituentIds.includes(edge.from);
                        const toExists = network.body.data.nodes.get(edge.to) || constituentIds.includes(edge.to);
                        return fromExists && toExists;
                    });
                    
                    if (edgesToRestore.length > 0) {
                        network.body.data.edges.add(edgesToRestore);
                        console.log(`Restored ${edgesToRestore.length} original edges`);
                    }
                } catch (e) {
                    console.warn('Error restoring edges:', e);
                }
            }
            
            // Show all constituent nodes (they should already exist, just update to not hidden)
            const nodeUpdates = constituentIds.map(nodeId => ({
                id: nodeId,
                hidden: false
            }));
            
            try {
                network.body.data.nodes.update(nodeUpdates);
                console.log(`Restored ${nodeUpdates.length} constituent nodes`);
            } catch (e) {
                console.warn('Error updating constituent nodes:', e);
            }
            
            // Remove representative node
            try {
                network.body.data.nodes.remove(repId);
                console.log(`Removed representative node ${repId}`);
            } catch (e) {
                console.warn('Could not remove representative node:', e);
            }
            
            // Update collapsed set
            this.filters.collapse.nodes.collapsed.forEach((group, key) => {
                if (group.representativeId === repId) {
                    this.filters.collapse.nodes.collapsed.delete(key);
                }
            });
            
            this.updateCollapseStats();
        },
        
        /**
         * Reroute edges from constituent nodes to representative node
         */
        rerouteEdgesToRepresentative: function(constituentIds, representativeId) {
            if (!network || !network.body || !network.body.data) return;
            
            const edgesToAdd = [];
            const originalEdges = [];  // Store original edges for restoration
            const edgeMap = new Map(); // Track unique edges by key
            
            console.log(`Rerouting edges for ${constituentIds.length} constituent nodes to ${representativeId}`);
            
            // Find all edges connected to constituent nodes
            constituentIds.forEach(constituentId => {
                try {
                    const connectedEdges = network.getConnectedEdges(constituentId);
                    
                    connectedEdges.forEach(edgeId => {
                        const edge = network.body.data.edges.get(edgeId);
                        if (!edge) return;
                        
                        // Store original edge data for later restoration
                        originalEdges.push({
                            id: edge.id,
                            from: edge.from,
                            to: edge.to,
                            label: edge.label,
                            type: edge.type,
                            color: edge.color,
                            width: edge.width,
                            arrows: edge.arrows,
                            properties: edge.properties
                        });
                        
                        // Determine if this edge connects to a non-constituent node
                        const otherNode = edge.from === constituentId ? edge.to : edge.from;
                        
                        if (!constituentIds.includes(otherNode)) {
                            // This edge connects to outside the group
                            // Create a new edge from representative to other node
                            const newFrom = edge.from === constituentId ? representativeId : edge.from;
                            const newTo = edge.to === constituentId ? representativeId : edge.to;
                            
                            // Create unique key to prevent duplicate edges
                            const edgeKey = `${newFrom}_${edge.label || edge.type || 'connected'}_${newTo}`;
                            
                            if (!edgeMap.has(edgeKey)) {
                                const newEdge = {
                                    id: `collapsed_edge_${representativeId}_${Math.random().toString(36).substr(2, 9)}`,
                                    from: newFrom,
                                    to: newTo,
                                    label: edge.label || edge.type || '',
                                    color: edge.color || {color: '#f59e0b'},
                                    width: Math.max(2, (edge.width || 2)),
                                    arrows: edge.arrows || {to: {enabled: true}},
                                    _isCollapsedEdge: true,
                                    _originalEdgeIds: [edge.id],
                                    _representativeId: representativeId,
                                    _constituentCount: 1
                                };
                                
                                edgeMap.set(edgeKey, newEdge);
                                edgesToAdd.push(newEdge);
                            } else {
                                // Edge already exists, increase width to show multiple connections
                                const existingEdge = edgeMap.get(edgeKey);
                                existingEdge.width = Math.min(8, existingEdge.width + 0.5);
                                existingEdge._originalEdgeIds.push(edge.id);
                                existingEdge._constituentCount++;
                            }
                        }
                        // Note: We don't remove edges here, let the visibility filter handle it
                    });
                } catch (e) {
                    console.warn('Error processing edges for node:', constituentId, e);
                }
            });
            
            // Store original edges on the representative node for restoration
            const repNode = network.body.data.nodes.get(representativeId);
            if (repNode) {
                repNode._originalEdges = originalEdges;
                network.body.data.nodes.update(repNode);
            }
            
            // Add all new collapsed edges
            if (edgesToAdd.length > 0) {
                try {
                    network.body.data.edges.add(edgesToAdd);
                    console.log(`Added ${edgesToAdd.length} collapsed edges for representative ${representativeId}`);
                } catch (e) {
                    console.warn('Could not add collapsed edges:', e);
                }
            }
        },
        
        /**
         * Show collapsed node info in GraphInfoCard (on hover)
         */
        showCollapsedNodeInCard: function(nodeId, nodeData) {
            if (!window.GraphInfoCard || !window.GraphInfoCard.showInlineContent) {
                console.warn('GraphInfoCard not available');
                return;
            }
            
            const constituentData = nodeData._constituentData || [];
            const groupBy = nodeData._groupBy || [];
            const groupKey = nodeData._groupKey || '';
            
            // Build custom content for GraphInfoCard
            const parts = groupKey.split('|');
            const groupLabels = groupBy.map((prop, idx) => {
                if (parts[idx] && parts[idx] !== 'null') {
                    return `${prop}: ${parts[idx]}`;
                }
                return null;
            }).filter(Boolean);
            
            // Use GraphInfoCard's showInlineContent or create custom display
            const groupName = groupLabels.length > 0 ? groupLabels.join(', ') : 'Collapsed Group';
            
            // Create summary for hover - will be more detailed than tooltip
            let html = `
                <div style="color: var(--text-secondary); font-size: 11px; margin-bottom: 8px;">
                    Collapsed Group (${constituentData.length} nodes)
                </div>
                <div style="color: var(--text); font-size: 15px; font-weight: 600; margin-bottom: 12px;">
                    ${this.escapeHtml(groupName)}
                </div>
            `;
            
            // Show constituent nodes
            html += '<div style="margin-bottom: 12px;">';
            html += '<div style="color: var(--text-secondary); font-size: 11px; font-weight: 600; margin-bottom: 6px;">Constituent Nodes</div>';
            
            constituentData.slice(0, 5).forEach(node => {
                html += `
                    <div style="
                        padding: 8px; margin-bottom: 4px;
                        background: var(--bg); border-radius: 4px;
                        border: 1px solid var(--border-subtle);
                    ">
                        <div style="color: var(--text); font-size: 12px; font-weight: 500; margin-bottom: 2px;">
                            ${this.escapeHtml(node.display_name)}
                        </div>
                        ${node.labels && node.labels.length > 0 ? `
                            <div style="display: flex; gap: 4px; flex-wrap: wrap; margin-top: 4px;">
                                ${node.labels.slice(0, 3).map(label => `
                                    <span style="
                                        font-size: 9px; padding: 2px 6px;
                                        background: var(--accent-bg, rgba(59, 130, 246, 0.15));
                                        border: 1px solid var(--accent-border, rgba(59, 130, 246, 0.3));
                                        border-radius: 3px; color: var(--accent);
                                    ">${this.escapeHtml(String(label))}</span>
                                `).join('')}
                            </div>
                        ` : ''}
                    </div>
                `;
            });
            
            if (constituentData.length > 5) {
                html += `
                    <div style="text-align: center; color: var(--text-secondary); font-size: 10px; margin-top: 6px;">
                        ... and ${constituentData.length - 5} more
                    </div>
                `;
            }
            
            html += '</div>';
            
            html += `
                <div style="
                    border-top: 1px solid var(--border); padding-top: 12px; margin-top: 12px;
                    color: var(--text-secondary); font-size: 10px; text-align: center;
                ">
                    <div>Click for full details</div>
                    <div style="margin-top: 4px;">Ctrl+Click to expand constituents</div>
                </div>
            `;
            
            // Update GraphInfoCard directly if it's in compact mode
            if (window.GraphInfoCard.cardElement && !window.GraphInfoCard.isExpanded) {
                window.GraphInfoCard.currentNodeId = nodeId;
                window.GraphInfoCard.currentEdgeId = null;
                window.GraphInfoCard.cardElement.innerHTML = `<div style="padding: 16px;">${html}</div>`;
                window.GraphInfoCard.show();
            }
        },
        
        /**
         * Get expanded view of collapsed node (for GraphInfoCard click)
         */
        getExpandedCollapsedNodeInfo: function(nodeId, nodeData) {
            const constituentData = nodeData._constituentData || [];
            const groupBy = nodeData._groupBy || [];
            const groupKey = nodeData._groupKey || '';
            
            // Build parts for the group name
            const parts = groupKey.split('|');
            const groupLabels = groupBy.map((prop, idx) => {
                if (parts[idx] && parts[idx] !== 'null') {
                    return `${prop}: ${parts[idx]}`;
                }
                return null;
            }).filter(Boolean);
            
            const groupName = groupLabels.length > 0 ? groupLabels.join(', ') : 'Collapsed Group';
            
            // Build expanded HTML
            let html = `
                <div style="padding: 20px;">
                    <!-- Header with close button -->
                    <div style="display: flex; align-items: flex-start; gap: 12px; margin-bottom: 16px;">
                        <div style="flex: 1; min-width: 0;">
                            <div style="
                                color: var(--text); font-size: 18px; font-weight: 600;
                                margin-bottom: 6px; word-wrap: break-word;
                            ">${this.escapeHtml(groupName)}</div>
                            
                            <div style="color: var(--text-secondary); font-size: 12px; margin-bottom: 4px;">
                                Collapsed Group • ${constituentData.length} nodes
                            </div>
                            
                            <div style="color: var(--text-secondary); font-size: 11px;">
                                Grouped by: ${groupBy.join(', ')}
                            </div>
                        </div>
                        <button onclick="window.GraphInfoCard.collapse()" style="
                            background: none; border: none; color: var(--text-secondary);
                            cursor: pointer; font-size: 20px; padding: 0;
                            width: 28px; height: 28px; display: flex; align-items: center; justify-content: center;
                            flex-shrink: 0;
                        " title="Collapse">✕</button>
                    </div>
                    
                    <!-- All Constituent Nodes -->
                    <div style="margin-bottom: 16px;">
                        <div style="color: var(--text-secondary); font-size: 12px; font-weight: 600; margin-bottom: 8px;">
                            All Constituent Nodes
                        </div>
                        <div style="max-height: 400px; overflow-y: auto;">
            `;
            
            constituentData.forEach(node => {
                html += `
                    <div onclick="
                        window.GraphAdvancedFilters.expandCollapsedNode('${nodeId}', network.body.data.nodes.get('${nodeId}'));
                        window.GraphInfoCard.focusAndExpand('${node.id}');
                    " style="
                        padding: 10px; margin-bottom: 6px;
                        background: var(--bg); border-radius: 4px;
                        border: 1px solid var(--border-subtle);
                        cursor: pointer;
                        transition: background 0.2s;
                    " onmouseover="this.style.background='var(--hover)'" onmouseout="this.style.background='var(--bg)'">
                        <div style="color: var(--text); font-size: 13px; font-weight: 500; margin-bottom: 4px;">
                            ${this.escapeHtml(node.display_name)}
                        </div>
                        ${node.labels && node.labels.length > 0 ? `
                            <div style="display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 6px;">
                                ${node.labels.map(label => `
                                    <span style="
                                        font-size: 9px; padding: 2px 6px;
                                        background: var(--accent-bg, rgba(59, 130, 246, 0.15));
                                        border: 1px solid var(--accent-border, rgba(59, 130, 246, 0.3));
                                        border-radius: 3px; color: var(--accent);
                                    ">${this.escapeHtml(String(label))}</span>
                                `).join('')}
                            </div>
                        ` : ''}
                        ${Object.keys(node.properties).length > 0 ? `
                            <div style="color: var(--text-secondary); font-size: 10px;">
                                ${Object.keys(node.properties).length} properties
                            </div>
                        ` : ''}
                    </div>
                `;
            });
            
            html += `
                        </div>
                    </div>
                    
                    <!-- Actions -->
                    <div style="border-top: 1px solid var(--border); padding-top: 16px;">
                        <button onclick="
                            window.GraphAdvancedFilters.expandCollapsedNode('${nodeId}', network.body.data.nodes.get('${nodeId}'));
                            window.GraphInfoCard.collapse();
                        " style="
                            width: 100%; padding: 12px;
                            background: var(--accent); color: var(--text-inverted);
                            border: none; border-radius: 6px; cursor: pointer;
                            font-weight: 600; font-size: 14px;
                        ">Expand All Constituents</button>
                    </div>
                </div>
            `;
            
            return html;
        },
        
        /**
         * Collapse edges with identical properties
         */
        collapseEdges: function(visibleEdges, visibleNodes) {
            const groupBy = this.filters.collapse.edges.groupBy;
            const groups = new Map();
            
            // Group edges
            visibleEdges.forEach(edgeId => {
                const edge = this.originalData.edges.get(edgeId);
                if (!edge || !visibleNodes.has(edge.from) || !visibleNodes.has(edge.to)) return;
                
                // Create group key (include from/to to group parallel edges)
                const keyParts = [edge.from, edge.to];
                groupBy.forEach(prop => {
                    if (prop in edge) {
                        keyParts.push(String(edge[prop]));
                    } else {
                        keyParts.push('null');
                    }
                });
                
                const groupKey = keyParts.join('|');
                
                if (!groups.has(groupKey)) {
                    groups.set(groupKey, {
                        representativeId: edgeId,
                        memberIds: []
                    });
                }
                
                groups.get(groupKey).memberIds.push(edgeId);
            });
            
            // Keep only representatives
            const collapsedEdges = new Set();
            groups.forEach((group, key) => {
                collapsedEdges.add(group.representativeId);
                
                // Update representative to show count
                if (group.memberIds.length > 1) {
                    const edge = network.body.data.edges.get(group.representativeId);
                    if (edge) {
                        const baseLabel = edge.label || '';
                        network.body.data.edges.update({
                            id: group.representativeId,
                            label: `${baseLabel} (×${group.memberIds.length})`,
                            width: Math.min(edge.width * 1.5, 8),
                            color: {
                                ...edge.color,
                                color: '#f59e0b'
                            }
                        });
                    }
                }
            });
            
            return { edges: collapsedEdges, groups };
        },
        
        /**
         * Expand all collapsed nodes and edges
         */
        expandAllCollapsed: function() {
            console.log('Expanding all collapsed nodes...');
            
            // Collect all representative nodes
            const representativeNodes = [];
            try {
                network.body.data.nodes.forEach(node => {
                    if (node._isCollapsed) {
                        representativeNodes.push(node);
                    }
                });
            } catch (e) {
                console.warn('Error finding representative nodes:', e);
            }
            
            console.log(`Found ${representativeNodes.length} collapsed nodes to expand`);
            
            // Expand each one
            representativeNodes.forEach(repNode => {
                this.expandCollapsedNode(repNode.id, repNode);
            });
            
            // Also clear the collapsed map
            this.filters.collapse.nodes.collapsed.clear();
            this.filters.collapse.edges.collapsed.clear();
            
            // Reset collapse settings in UI
            const nodeCheckbox = document.getElementById('adv-collapse-nodes-enabled');
            const edgeCheckbox = document.getElementById('adv-collapse-edges-enabled');
            
            if (nodeCheckbox) nodeCheckbox.checked = false;
            if (edgeCheckbox) edgeCheckbox.checked = false;
            
            this.filters.collapse.nodes.enabled = false;
            this.filters.collapse.edges.enabled = false;
            
            this.updateCollapseStats();
            
            console.log('All collapsed nodes expanded');
        },
        
        /**
         * Clear all filters
         */
        clearAllFilters: function() {
            this.filters = {
                session: {
                    mode: 'all',
                    selectedSessionId: null,
                    availableSessions: this.filters.session.availableSessions
                },
                nodeProperties: {},
                edgeProperties: {},
                collapse: {
                    nodes: { enabled: false, groupBy: [], collapsed: new Map() },
                    edges: { enabled: false, groupBy: [], collapsed: new Map() }
                }
            };
            
            this.saveFilters();
            this.syncUI();
            this.applyAllFilters();
        },
        
        /**
         * Export filtered view
         */
        exportFilteredView: function() {
            if (!network || !network.body || !network.body.data) return;
            
            const visibleNodes = [];
            const visibleEdges = [];
            
            network.body.data.nodes.forEach(node => {
                if (!node.hidden) {
                    visibleNodes.push(this.graphAddon.nodesData[node.id]);
                }
            });
            
            network.body.data.edges.forEach(edge => {
                if (!edge.hidden) {
                    visibleEdges.push({ ...edge });
                }
            });
            
            const exportData = {
                nodes: visibleNodes,
                edges: visibleEdges,
                filters: this.filters,
                timestamp: new Date().toISOString()
            };
            
            const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `filtered-graph-${Date.now()}.json`;
            a.click();
            URL.revokeObjectURL(url);
            
            console.log('Exported filtered view:', visibleNodes.length, 'nodes,', visibleEdges.length, 'edges');
        },
        
        /**
         * Update filter statistics
         */
        updateFilterStats: function(nodeCount, edgeCount) {
            // Could add a stats display element if desired
            console.log(`Filter stats: ${nodeCount} nodes, ${edgeCount} edges`);
        },
        
        /**
         * Update collapse statistics
         */
        updateCollapseStats: function() {
            const nodeStats = document.getElementById('node-collapse-stats');
            if (nodeStats && this.filters.collapse.nodes.collapsed.size > 0) {
                const totalGroups = this.filters.collapse.nodes.collapsed.size;
                let totalMembers = 0;
                this.filters.collapse.nodes.collapsed.forEach(group => {
                    totalMembers += group.memberIds.length;
                });
                nodeStats.textContent = `${totalGroups} groups, ${totalMembers} nodes`;
            } else if (nodeStats) {
                nodeStats.textContent = '';
            }
            
            const edgeStats = document.getElementById('edge-collapse-stats');
            if (edgeStats && this.filters.collapse.edges.collapsed.size > 0) {
                const totalGroups = this.filters.collapse.edges.collapsed.size;
                let totalMembers = 0;
                this.filters.collapse.edges.collapsed.forEach(group => {
                    totalMembers += group.memberIds.length;
                });
                edgeStats.textContent = `${totalGroups} groups, ${totalMembers} edges`;
            } else if (edgeStats) {
                edgeStats.textContent = '';
            }
        },
        
        /**
         * Sync UI with current filter state
         */
        syncUI: function() {
            // Session mode
            const sessionMode = document.getElementById('adv-session-mode');
            if (sessionMode) {
                sessionMode.value = this.filters.session.mode;
            }
            
            const sessionId = document.getElementById('adv-session-id');
            if (sessionId && this.filters.session.selectedSessionId) {
                sessionId.value = this.filters.session.selectedSessionId;
            }
            
            // Update session selector visibility
            const sessionContainer = document.getElementById('session-selector-container');
            if (sessionContainer) {
                const needsSession = ['session-only', 'session-recent', 'hybrid', 'direct-only'].includes(this.filters.session.mode);
                sessionContainer.style.display = needsSession ? 'block' : 'none';
            }
            
            // Update time range visibility
            const timeContainer = document.getElementById('time-range-container');
            if (timeContainer) {
                timeContainer.style.display = (this.filters.session.mode === 'time-range') ? 'block' : 'none';
            }
            
            // Initialize time sliders
            if (this.filters.timeRange.minTime !== null) {
                this.updateTimeSliders();
            }
            
            // Render property filters
            this.renderPropertyFilters('node');
            this.renderPropertyFilters('edge');
            
            // Render collapse properties
            this.renderCollapseProperties('node');
            this.renderCollapseProperties('edge');
            
            // Update stats
            this.updateSessionStats();
        },
        
        /**
         * Render property filter list
         */
        renderPropertyFilters: function(type) {
            const container = document.getElementById(`${type}-property-filters-list`);
            if (!container) return;
            
            const filters = type === 'node' 
                ? this.filters.nodeProperties
                : this.filters.edgeProperties;
            
            if (Object.keys(filters).length === 0) {
                container.innerHTML = '<div style="text-align: center; color: var(--text-secondary); font-size: 11px; padding: 8px;">No filters</div>';
                return;
            }
            
            container.innerHTML = '';
            
            Object.entries(filters).forEach(([key, filter]) => {
                const item = document.createElement('div');
                item.className = 'adv-filter-item';
                
                const operatorText = {
                    'equals': '=',
                    'contains': '⊃',
                    'regex': '~/~',
                    'exists': '✓',
                    'not-exists': '✗',
                    'greater': '>',
                    'less': '<'
                }[filter.operator] || filter.operator;
                
                const valueDisplay = (filter.operator === 'exists' || filter.operator === 'not-exists')
                    ? ''
                    : `: ${filter.value}`;
                
                item.innerHTML = `
                    <input type="checkbox" ${filter.enabled ? 'checked' : ''}
                           onchange="window.GraphAdvancedFilters.togglePropertyFilter('${type}', '${key}', this.checked)"
                           style="margin-right: 8px; accent-color: var(--accent);">
                    <div style="flex: 1; font-size: 11px; color: var(--text);">
                        <span class="adv-filter-badge">${filter.propertyName}</span>
                        <span style="color: var(--text-secondary);"> ${operatorText}${valueDisplay}</span>
                    </div>
                    <button class="adv-filter-remove-btn"
                            onclick="window.GraphAdvancedFilters.removePropertyFilter('${type}', '${key}')">
                        ✕
                    </button>
                `;
                
                container.appendChild(item);
            });
        },
        
        /**
         * Render collapse properties
         */
        renderCollapseProperties: function(type) {
            const container = document.getElementById(`${type}-collapse-properties`);
            if (!container) return;
            
            const properties = type === 'node'
                ? this.filters.collapse.nodes.groupBy
                : this.filters.collapse.edges.groupBy;
            
            if (properties.length === 0) {
                container.innerHTML = '<div style="text-align: center; color: var(--text-secondary); font-size: 11px; padding: 8px;">No properties</div>';
                return;
            }
            
            container.innerHTML = '';
            
            properties.forEach(prop => {
                const item = document.createElement('div');
                item.className = 'adv-filter-item adv-filter-item-compact';
                
                item.innerHTML = `
                    <span class="adv-filter-badge">${prop}</span>
                    <button class="adv-filter-remove-btn"
                            onclick="window.GraphAdvancedFilters.removeCollapseProperty('${type}', '${prop}')">
                        ✕
                    </button>
                `;
                
                container.appendChild(item);
            });
        },
        
        /**
         * Save filters to localStorage
         */
        saveFilters: function() {
            try {
                // Convert Maps to objects for JSON serialization
                const saveData = {
                    ...this.filters,
                    collapse: {
                        nodes: {
                            ...this.filters.collapse.nodes,
                            collapsed: Array.from(this.filters.collapse.nodes.collapsed.entries())
                        },
                        edges: {
                            ...this.filters.collapse.edges,
                            collapsed: Array.from(this.filters.collapse.edges.collapsed.entries())
                        }
                    }
                };
                
                localStorage.setItem('graphAdvancedFilters', JSON.stringify(saveData));
            } catch (e) {
                console.warn('Could not save filters:', e);
            }
        },
        
        /**
         * Load filters from localStorage
         */
        loadFilters: function() {
            try {
                const saved = localStorage.getItem('graphAdvancedFilters');
                if (saved) {
                    const data = JSON.parse(saved);
                    
                    // Restore basic filters (merge to preserve defaults)
                    if (data.session) {
                        this.filters.session = Object.assign({}, this.filters.session, data.session);
                    }
                    
                    // Restore timeRange (merge to preserve defaults)
                    if (data.timeRange) {
                        this.filters.timeRange = Object.assign({}, this.filters.timeRange, data.timeRange);
                    }
                    
                    this.filters.nodeProperties = data.nodeProperties || {};
                    this.filters.edgeProperties = data.edgeProperties || {};
                    
                    // Restore collapse settings
                    if (data.collapse) {
                        if (data.collapse.nodes) {
                            this.filters.collapse.nodes.enabled = data.collapse.nodes.enabled || false;
                            this.filters.collapse.nodes.groupBy = data.collapse.nodes.groupBy || [];
                            this.filters.collapse.nodes.collapsed = new Map(data.collapse.nodes.collapsed || []);
                        }
                        if (data.collapse.edges) {
                            this.filters.collapse.edges.enabled = data.collapse.edges.enabled || false;
                            this.filters.collapse.edges.groupBy = data.collapse.edges.groupBy || [];
                            this.filters.collapse.edges.collapsed = new Map(data.collapse.edges.collapsed || []);
                        }
                    }
                    
                    console.log('Filters loaded from localStorage');
                }
            } catch (e) {
                console.warn('Could not load filters:', e);
                // Ensure timeRange exists even if loading fails
                if (!this.filters.timeRange) {
                    this.filters.timeRange = {
                        enabled: false,
                        startTime: null,
                        endTime: null,
                        propertyName: 'created_at',
                        minTime: null,
                        maxTime: null
                    };
                }
            }
        },
        
        /**
         * Escape HTML for safe display
         */
        escapeHtml: function(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
    };
    
})();