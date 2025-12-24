/**
 * Cypher Query Panel v3 - Fixed ID Conflicts
 * 
 * All IDs prefixed with 'cypher-' to avoid conflicts with main tab system
 */

(function() {
    'use strict';

    window.CypherQuery = {
        panelOpen: false,
        mode: 'builder',
        schema: null,
        schemaLoaded: false,
        queryHistory: [],
        savedQueries: [],
        maxHistory: 50,
        currentResults: null,
        
        // Builder state
        builder: {
            nodeLabel: '',
            nodeFilters: [],
            dateEnabled: false,
            dateFrom: '',
            dateTo: '',
            datePreset: '',
            includeRelationships: false,
            relationshipType: '',
            relationshipDirection: 'any',
            relationshipDepth: 1,
            targetNodeLabel: '',
            targetFilters: [],
            returnType: 'nodes',
            orderBy: '',
            orderDirection: 'DESC',
            limit: 100
        },
        
        // Layout state
        layout: {
            mode: 'force',
            groupBy: 'type',
            timelineProperty: 'created_at',
            physicsEnabled: true,
            stabilized: false
        },
        
        // Operators
        operators: [
            { value: '=', label: 'equals' },
            { value: '<>', label: 'not equals' },
            { value: 'CONTAINS', label: 'contains' },
            { value: 'STARTS WITH', label: 'starts with' },
            { value: 'ENDS WITH', label: 'ends with' },
            { value: '>', label: 'greater than' },
            { value: '<', label: 'less than' },
            { value: '>=', label: 'greater or equal' },
            { value: '<=', label: 'less or equal' },
            { value: 'IS NOT NULL', label: 'exists' },
            { value: 'IS NULL', label: 'not exists' },
            { value: '=~', label: 'regex' }
        ],
        
        // Date presets
        datePresets: [
            { value: 'today', label: 'Today' },
            { value: 'yesterday', label: 'Yesterday' },
            { value: 'last7', label: 'Last 7 days' },
            { value: 'last30', label: 'Last 30 days' },
            { value: 'thisWeek', label: 'This week' },
            { value: 'lastWeek', label: 'Last week' },
            { value: 'thisMonth', label: 'This month' },
            { value: 'lastMonth', label: 'Last month' },
            { value: 'custom', label: 'Custom range' }
        ],
        
        // Templates
        templates: [
            { name: "All Nodes", query: "MATCH (n) RETURN n LIMIT 100" },
            { name: "Recent Activity", query: "MATCH (n) WHERE n.created_at IS NOT NULL RETURN n ORDER BY n.created_at DESC LIMIT 100" },
            { name: "Hub Nodes", query: "MATCH (n) WITH n, size((n)--()) as deg WHERE deg > 3 RETURN n, deg ORDER BY deg DESC LIMIT 50" },
            { name: "Orphans", query: "MATCH (n) WHERE NOT (n)--() RETURN n LIMIT 100" },
            { name: "Full Subgraph", query: "MATCH (n)-[r]-(m) RETURN n, r, m LIMIT 200" }
        ],
        
        /**
         * Initialize
         */
        init: function() {
            this.loadSavedQueries();
            this.loadHistory();
            this.createUI();
            this.setupEventListeners();
            console.log('CypherQuery v3 initialized');
        },
        
        /**
         * Create UI
         */
        createUI: function() {
            if (document.getElementById('cypher-panel')) return;
            
            const panel = document.createElement('div');
            panel.id = 'cypher-panel';
            panel.className = 'cypher-panel';
            panel.innerHTML = `
                <div class="cypher-header">
                    <div class="cypher-title">
                        Query Builder
                    </div>
                    <div class="cypher-header-btns">
                        <button id="cypher-btn-refresh-schema" class="hdr-btn" title="Refresh Schema">🔄</button>
                        <button id="cypher-btn-stats" class="hdr-btn" title="Stats">📊</button>
                        <button id="cypher-btn-close" class="hdr-btn" title="Close">✕</button>
                    </div>
                </div>
                
                <!-- Tabs -->
                <div class="cypher-tabs">
                    <button class="cypher-tab-btn active" data-cypher-tab="builder">🔧 Build</button>
                    <button class="cypher-tab-btn" data-cypher-tab="layout">📐 Layout</button>
                    <button class="cypher-tab-btn" data-cypher-tab="editor">✏️ Raw</button>
                </div>
                
                <div class="cypher-body">
                    <!-- Builder Tab -->
                    <div id="cypher-tab-builder" class="cypher-tab-content active">
                        ${this.renderBuilderTab()}
                    </div>
                    
                    <!-- Layout Tab -->
                    <div id="cypher-tab-layout" class="cypher-tab-content">
                        ${this.renderLayoutTab()}
                    </div>
                    
                    <!-- Editor Tab -->
                    <div id="cypher-tab-editor" class="cypher-tab-content">
                        ${this.renderEditorTab()}
                    </div>
                    
                    <!-- Query Preview -->
                    <div class="query-preview-box">
                        <div class="preview-hdr">
                            <span>Generated Query</span>
                            <button id="cypher-btn-copy" class="tiny-btn" title="Copy">📋</button>
                        </div>
                        <pre id="cypher-query-preview"></pre>
                    </div>
                    
                    <!-- Execute -->
                    <div class="execute-section">
                        <div class="exec-options">
                            <label><input type="checkbox" id="cypher-opt-replace" checked> Replace</label>
                            <label><input type="checkbox" id="cypher-opt-fit"> Fit view</label>
                            <label><input type="checkbox" id="cypher-opt-apply-layout" checked> Apply layout</label>
                        </div>
                        <button id="cypher-btn-execute" class="btn-execute">▶ Execute</button>
                    </div>
                    
                    <!-- Results -->
                    <div id="cypher-results-box" class="results-box" style="display:none">
                        <div class="results-hdr">
                            <span>Results</span>
                            <button id="cypher-btn-clear-results" class="tiny-btn">✕</button>
                        </div>
                        <div id="cypher-results-content"></div>
                    </div>
                    
                    <!-- Collapsibles -->
                    <details class="detail-section">
                        <summary>📁 Templates</summary>
                        <div id="cypher-templates-container"></div>
                    </details>
                    <details class="detail-section">
                        <summary>🕐 History</summary>
                        <div id="cypher-history-container"></div>
                    </details>
                    <details class="detail-section">
                        <summary>⭐ Saved</summary>
                        <div id="cypher-saved-container"></div>
                    </details>
                </div>
                
                <div id="cypher-loading-overlay" class="loading-overlay">
                    <div class="spinner"></div>
                    <div id="cypher-loading-text">Loading...</div>
                </div>
            `;
            
            document.body.appendChild(panel);
            // this.createToggleButton();
            this.populateTemplates();
            this.renderHistory();
            this.renderSaved();
            this.loadSchema();
            this.updatePreview();
        },
        
        /**
         * Render builder tab
         */
        renderBuilderTab: function() {
            return `
                <!-- Node Selection -->
                <div class="section-box">
                    <div class="section-title">🔵 Source Nodes</div>
                    <div class="section-body">
                        <div class="field">
                            <label>Label</label>
                            <select id="cypher-node-label" class="field-select">
                                <option value="">Any</option>
                            </select>
                        </div>
                        
                        <!-- Filters -->
                        <div class="filters-area">
                            <div class="filters-hdr">
                                <span>Filters</span>
                                <button id="cypher-btn-add-filter" class="btn-add">+ Add</button>
                            </div>
                            <div id="cypher-node-filters"></div>
                        </div>
                    </div>
                </div>
                
                <!-- Date Range -->
                <div class="section-box">
                    <div class="section-title">
                        <label class="section-toggle">
                            <input type="checkbox" id="cypher-date-enabled">
                            <span>Date Range</span>
                        </label>
                    </div>
                    <div id="cypher-date-content" class="section-body collapsed">
                        <div class="field">
                            <label>Preset</label>
                            <select id="cypher-date-preset" class="field-select">
                                <option value="">Select...</option>
                                ${this.datePresets.map(p => `<option value="${p.value}">${p.label}</option>`).join('')}
                            </select>
                        </div>
                        <div id="cypher-custom-date-range" class="date-range-fields" style="display:none">
                            <div class="field half">
                                <label>From</label>
                                <input type="datetime-local" id="cypher-date-from" class="field-input">
                            </div>
                            <div class="field half">
                                <label>To</label>
                                <input type="datetime-local" id="cypher-date-to" class="field-input">
                            </div>
                        </div>
                        <div class="date-quick-btns">
                            <button class="date-quick" data-hours="1">1h</button>
                            <button class="date-quick" data-hours="6">6h</button>
                            <button class="date-quick" data-hours="24">24h</button>
                            <button class="date-quick" data-hours="72">3d</button>
                            <button class="date-quick" data-hours="168">7d</button>
                        </div>
                    </div>
                </div>
                
                <!-- Relationships -->
                <div class="section-box">
                    <div class="section-title">
                        <label class="section-toggle">
                            <input type="checkbox" id="cypher-rels-enabled">
                            <span>Relationships</span>
                        </label>
                    </div>
                    <div id="cypher-rels-content" class="section-body collapsed">
                        <div class="field">
                            <label>Type</label>
                            <select id="cypher-rel-type" class="field-select">
                                <option value="">Any</option>
                            </select>
                        </div>
                        <div class="field">
                            <label>Direction</label>
                            <div class="dir-buttons">
                                <button class="dir-btn" data-dir="outgoing">→</button>
                                <button class="dir-btn active" data-dir="any">↔</button>
                                <button class="dir-btn" data-dir="incoming">←</button>
                            </div>
                        </div>
                        <div class="field">
                            <label>Depth: <span id="cypher-depth-val">1</span></label>
                            <input type="range" id="cypher-rel-depth" min="1" max="5" value="1">
                        </div>
                        <div class="subsection">
                            <div class="subsection-title">Target Node</div>
                            <div class="field">
                                <label>Label</label>
                                <select id="cypher-target-label" class="field-select">
                                    <option value="">Any</option>
                                </select>
                            </div>
                            <div class="filters-area">
                                <div class="filters-hdr">
                                    <span>Target Filters</span>
                                    <button id="cypher-btn-add-target-filter" class="btn-add">+ Add</button>
                                </div>
                                <div id="cypher-target-filters"></div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Return Options -->
                <div class="section-box">
                    <div class="section-title">Return</div>
                    <div class="section-body">
                        <div class="field">
                            <label>Return</label>
                            <select id="cypher-return-type" class="field-select">
                                <option value="nodes">Nodes only</option>
                                <option value="subgraph">Nodes & Relationships</option>
                                <option value="paths">Full Paths</option>
                                <option value="count">Count only</option>
                            </select>
                        </div>
                        <div class="field">
                            <label>Order by</label>
                            <div class="order-row">
                                <select id="cypher-order-by" class="field-select">
                                    <option value="">None</option>
                                    <option value="n.created_at">Created date</option>
                                    <option value="n.id">ID</option>
                                    <option value="n.text">Text</option>
                                    <option value="n.name">Name</option>
                                    <option value="degree">Connections</option>
                                </select>
                                <button id="cypher-order-dir-btn" class="order-dir">↓</button>
                            </div>
                        </div>
                        <div class="field">
                            <label>Limit</label>
                            <input type="number" id="cypher-limit-input" class="field-input" value="100" min="1" max="5000">
                        </div>
                    </div>
                </div>
                
                <!-- Quick Actions -->
                <div class="quick-actions">
                    <button class="quick-btn" data-quick="all">All</button>
                    <button class="quick-btn" data-quick="recent">Recent</button>
                    <button class="quick-btn" data-quick="hubs">Hubs</button>
                    <button class="quick-btn" data-quick="orphans">Orphans</button>
                    <button class="quick-btn" data-quick="last-hour">Last Hour</button>
                </div>
            `;
        },
        
        /**
         * Render layout tab
         */
        renderLayoutTab: function() {
            return `
                <div class="section-box">
                    <div class="section-title">📐 Layout Mode</div>
                    <div class="section-body">
                        <div class="layout-modes">
                            <button class="layout-btn active" data-layout="force" title="Force-directed">
                                <span class="layout-icon">🕸️</span>
                                <span>Force</span>
                            </button>
                            <button class="layout-btn" data-layout="timeline" title="Timeline by date">
                                <span class="layout-icon">📅</span>
                                <span>Timeline</span>
                            </button>
                            <button class="layout-btn" data-layout="hierarchical" title="Hierarchical tree">
                                <span class="layout-icon">🌳</span>
                                <span>Tree</span>
                            </button>
                            <button class="layout-btn" data-layout="grouped" title="Group by property">
                                <span class="layout-icon">📦</span>
                                <span>Grouped</span>
                            </button>
                            <button class="layout-btn" data-layout="circular" title="Circular layout">
                                <span class="layout-icon">⭕</span>
                                <span>Circular</span>
                            </button>
                        </div>
                    </div>
                </div>
                
                <!-- Timeline Options -->
                <div id="cypher-timeline-options" class="section-box" style="display:none">
                    <div class="section-title">📅 Timeline Settings</div>
                    <div class="section-body">
                        <div class="field">
                            <label>Time Property</label>
                            <select id="cypher-timeline-property" class="field-select">
                                <option value="created_at">created_at</option>
                                <option value="updated_at">updated_at</option>
                                <option value="timestamp">timestamp</option>
                            </select>
                        </div>
                        <div class="field">
                            <label>Orientation</label>
                            <div class="toggle-btns">
                                <button class="toggle-btn active" data-orient="horizontal">Horizontal</button>
                                <button class="toggle-btn" data-orient="vertical">Vertical</button>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Grouped Options -->
                <div id="cypher-grouped-options" class="section-box" style="display:none">
                    <div class="section-title">📦 Grouping Settings</div>
                    <div class="section-body">
                        <div class="field">
                            <label>Group By</label>
                            <select id="cypher-group-by" class="field-select">
                                <option value="type">Type</option>
                                <option value="label">Label</option>
                                <option value="session_id">Session</option>
                            </select>
                        </div>
                        <div class="field">
                            <label>
                                <input type="checkbox" id="cypher-show-group-boxes" checked>
                                Show group boundaries
                            </label>
                        </div>
                    </div>
                </div>
                
                <!-- Physics Settings -->
                <div class="section-box">
                    <div class="section-title">⚙️ Physics & Performance</div>
                    <div class="section-body">
                        <div class="field">
                            <label>
                                <input type="checkbox" id="cypher-physics-enabled" checked>
                                Enable physics simulation
                            </label>
                        </div>
                        <div class="field">
                            <label>Gravity: <span id="cypher-gravity-val">-2000</span></label>
                            <input type="range" id="cypher-gravity-slider" min="-8000" max="-500" value="-2000">
                        </div>
                        <div class="field">
                            <label>Spring Length: <span id="cypher-spring-val">200</span></label>
                            <input type="range" id="cypher-spring-slider" min="50" max="500" value="200">
                        </div>
                        <div class="field">
                            <label>Damping: <span id="cypher-damping-val">0.9</span></label>
                            <input type="range" id="cypher-damping-slider" min="0.1" max="1" step="0.05" value="0.9">
                        </div>
                        <div class="physics-actions">
                            <button id="cypher-btn-stabilize" class="action-btn">⚡ Quick Stabilize</button>
                            <button id="cypher-btn-freeze" class="action-btn">❄️ Freeze</button>
                            <button id="cypher-btn-unfreeze" class="action-btn">🔥 Unfreeze</button>
                        </div>
                    </div>
                </div>
                
                <!-- Layout Actions -->
                <div class="section-box">
                    <div class="section-title">🎬 Actions</div>
                    <div class="section-body">
                        <div class="layout-actions">
                            <button id="cypher-btn-apply-layout" class="action-btn primary">Apply Layout</button>
                            <button id="cypher-btn-fit-view" class="action-btn">Fit to View</button>
                            <button id="cypher-btn-reset-layout" class="action-btn">Reset</button>
                        </div>
                    </div>
                </div>
            `;
        },
        
        /**
         * Render editor tab
         */
        renderEditorTab: function() {
            return `
                <div class="editor-box">
                    <div class="editor-toolbar">
                        <button id="cypher-btn-format" class="tool-btn" title="Format">⚙️</button>
                        <button id="cypher-btn-clear-editor" class="tool-btn" title="Clear">🗑️</button>
                        <button id="cypher-btn-save-query" class="tool-btn" title="Save">💾</button>
                    </div>
                    <div class="editor-wrapper">
                        <div id="cypher-line-nums" class="line-nums"></div>
                        <textarea id="cypher-editor" placeholder="MATCH (n) RETURN n LIMIT 100" spellcheck="false"></textarea>
                    </div>
                </div>
            `;
        },
        
        /**
         * Create toggle button
         */
        createToggleButton: function() {
            let container = document.getElementById('cypher-toggle-container');
            if (!container) {
                container = document.createElement('div');
                container.id = 'cypher-toggle-container';
                document.body.appendChild(container);
            }
            
            if (!document.getElementById('cypher-toggle-btn')) {
                const btn = document.createElement('button');
                btn.id = 'cypher-toggle-btn';
                btn.innerHTML = '⚡';
                btn.title = 'Query Builder (Ctrl+Shift+C)';
                btn.onclick = () => this.togglePanel();
                container.appendChild(btn);
            }
            
            // Keyboard shortcuts
            document.addEventListener('keydown', (e) => {
                if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === 'c') {
                    e.preventDefault();
                    this.togglePanel();
                }
                if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && this.panelOpen) {
                    e.preventDefault();
                    this.executeQuery();
                }
            });
        },
        
        /**
         * Setup event listeners
         */
        setupEventListeners: function() {
            const self = this;
            
            // Header buttons
            this.on('cypher-btn-close', 'click', () => self.togglePanel());
            this.on('cypher-btn-refresh-schema', 'click', () => self.loadSchema(true));
            this.on('cypher-btn-stats', 'click', () => self.showStats());
            
            // Tabs
            document.querySelectorAll('.cypher-tab-btn').forEach(btn => {
                btn.addEventListener('click', () => self.switchTab(btn.dataset.cypherTab));
            });
            
            // Builder controls
            this.on('cypher-node-label', 'change', () => self.updateBuilder());
            this.on('cypher-btn-add-filter', 'click', () => self.addFilter('cypher-node-filters'));
            this.on('cypher-btn-add-target-filter', 'click', () => self.addFilter('cypher-target-filters'));
            
            // Date controls
            this.on('cypher-date-enabled', 'change', (e) => {
                document.getElementById('cypher-date-content').classList.toggle('collapsed', !e.target.checked);
                self.builder.dateEnabled = e.target.checked;
                self.updateBuilder();
            });
            this.on('cypher-date-preset', 'change', (e) => self.applyDatePreset(e.target.value));
            
            document.querySelectorAll('.date-quick').forEach(btn => {
                btn.addEventListener('click', () => {
                    const hours = parseInt(btn.dataset.hours);
                    self.setDateRange(hours);
                });
            });
            
            // Relationships
            this.on('cypher-rels-enabled', 'change', (e) => {
                document.getElementById('cypher-rels-content').classList.toggle('collapsed', !e.target.checked);
                self.builder.includeRelationships = e.target.checked;
                self.updateBuilder();
            });
            this.on('cypher-rel-type', 'change', () => self.updateBuilder());
            this.on('cypher-rel-depth', 'input', (e) => {
                document.getElementById('cypher-depth-val').textContent = e.target.value;
                self.builder.relationshipDepth = parseInt(e.target.value);
                self.updateBuilder();
            });
            this.on('cypher-target-label', 'change', () => self.updateBuilder());
            
            document.querySelectorAll('.dir-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    document.querySelectorAll('.dir-btn').forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    self.builder.relationshipDirection = btn.dataset.dir;
                    self.updateBuilder();
                });
            });
            
            // Return options
            this.on('cypher-return-type', 'change', () => self.updateBuilder());
            this.on('cypher-order-by', 'change', () => self.updateBuilder());
            this.on('cypher-order-dir-btn', 'click', () => {
                self.builder.orderDirection = self.builder.orderDirection === 'DESC' ? 'ASC' : 'DESC';
                document.getElementById('cypher-order-dir-btn').textContent = self.builder.orderDirection === 'DESC' ? '↓' : '↑';
                self.updateBuilder();
            });
            this.on('cypher-limit-input', 'change', () => self.updateBuilder());
            
            // Quick actions
            document.querySelectorAll('.quick-btn').forEach(btn => {
                btn.addEventListener('click', () => self.applyQuickAction(btn.dataset.quick));
            });
            
            // Layout controls
            document.querySelectorAll('.layout-btn').forEach(btn => {
                btn.addEventListener('click', () => self.setLayoutMode(btn.dataset.layout));
            });
            
            // Physics controls
            this.on('cypher-physics-enabled', 'change', (e) => self.togglePhysics(e.target.checked));
            this.on('cypher-gravity-slider', 'input', (e) => self.updatePhysics('gravity', e.target.value));
            this.on('cypher-spring-slider', 'input', (e) => self.updatePhysics('spring', e.target.value));
            this.on('cypher-damping-slider', 'input', (e) => self.updatePhysics('damping', e.target.value));
            
            this.on('cypher-btn-stabilize', 'click', () => self.quickStabilize());
            this.on('cypher-btn-freeze', 'click', () => self.freezeGraph());
            this.on('cypher-btn-unfreeze', 'click', () => self.unfreezeGraph());
            this.on('cypher-btn-apply-layout', 'click', () => self.applyCurrentLayout());
            this.on('cypher-btn-fit-view', 'click', () => self.fitView());
            this.on('cypher-btn-reset-layout', 'click', () => self.resetLayout());
            
            // Group/timeline options
            this.on('cypher-group-by', 'change', () => { self.layout.groupBy = document.getElementById('cypher-group-by').value; });
            this.on('cypher-timeline-property', 'change', () => { self.layout.timelineProperty = document.getElementById('cypher-timeline-property').value; });
            
            // Execute
            this.on('cypher-btn-execute', 'click', () => self.executeQuery());
            this.on('cypher-btn-copy', 'click', () => self.copyQuery());
            this.on('cypher-btn-clear-results', 'click', () => { document.getElementById('cypher-results-box').style.display = 'none'; });
            
            // Editor
            const editor = document.getElementById('cypher-editor');
            if (editor) {
                editor.addEventListener('input', () => {
                    self.updateLineNumbers();
                    self.updatePreview();
                });
                editor.addEventListener('keydown', (e) => {
                    if (e.key === 'Tab') {
                        e.preventDefault();
                        const start = editor.selectionStart;
                        editor.value = editor.value.substring(0, start) + '  ' + editor.value.substring(editor.selectionEnd);
                        editor.selectionStart = editor.selectionEnd = start + 2;
                    }
                });
            }
            
            this.on('cypher-btn-format', 'click', () => self.formatQuery());
            this.on('cypher-btn-clear-editor', 'click', () => {
                document.getElementById('cypher-editor').value = '';
                self.updateLineNumbers();
            });
            this.on('cypher-btn-save-query', 'click', () => self.saveCurrentQuery());
            
            this.updateLineNumbers();
        },
        
        /**
         * Helper to add listener
         */
        on: function(id, event, handler) {
            const el = document.getElementById(id);
            if (el) el.addEventListener(event, handler);
        },
        
        /**
         * Toggle panel
         */
        togglePanel: function() {
            this.panelOpen = !this.panelOpen;
            document.getElementById('cypher-panel').classList.toggle('open', this.panelOpen);
            if (this.panelOpen && !this.schemaLoaded) this.loadSchema();
        },
        
        /**
         * Switch tab
         */
        switchTab: function(tab) {
            document.querySelectorAll('.cypher-tab-btn').forEach(b => b.classList.toggle('active', b.dataset.cypherTab === tab));
            document.querySelectorAll('.cypher-tab-content').forEach(c => c.classList.toggle('active', c.id === `cypher-tab-${tab}`));
            this.mode = tab === 'editor' ? 'editor' : 'builder';
            
            if (tab === 'editor') {
                document.getElementById('cypher-editor').value = this.buildQuery();
                this.updateLineNumbers();
            }
        },
        
        /**
         * Load schema
         */
        loadSchema: async function(force = false) {
            if (this.schemaLoaded && !force) return;
            
            this.showLoading(true, 'Loading schema...');
            
            try {
                const response = await fetch('http://llm.int:8888/api/graph/schema');
                const data = await response.json();
                
                this.schema = data;
                this.schemaLoaded = true;
                
                this.populateSelect('cypher-node-label', data.labels || []);
                this.populateSelect('cypher-target-label', data.labels || []);
                this.populateSelect('cypher-rel-type', data.relationship_types || []);
                
                // Add properties to group-by
                const groupBy = document.getElementById('cypher-group-by');
                if (groupBy && data.property_keys) {
                    data.property_keys.slice(0, 15).forEach(p => {
                        if (!['type', 'label', 'session_id'].includes(p)) {
                            const opt = document.createElement('option');
                            opt.value = p;
                            opt.textContent = p;
                            groupBy.appendChild(opt);
                        }
                    });
                }
                
                this.notify('Schema loaded', 'success');
            } catch (e) {
                console.error('Schema load error:', e);
                this.notify('Failed to load schema', 'error');
            } finally {
                this.showLoading(false);
            }
        },
        
        /**
         * Populate select
         */
        populateSelect: function(id, options) {
            const select = document.getElementById(id);
            if (!select) return;
            const current = select.value;
            select.innerHTML = '<option value="">Any</option>';
            options.forEach(opt => {
                const o = document.createElement('option');
                o.value = opt;
                o.textContent = opt;
                select.appendChild(o);
            });
            if (current) select.value = current;
        },
        
        /**
         * Add filter row
         */
        addFilter: function(containerId) {
            const container = document.getElementById(containerId);
            if (!container) return;
            
            const props = this.schema?.property_keys || ['id', 'text', 'name', 'type', 'created_at'];
            const id = `cypher-filter-${Date.now()}`;
            
            const row = document.createElement('div');
            row.className = 'filter-row';
            row.id = id;
            row.innerHTML = `
                <select class="filter-prop">
                    <option value="">Property</option>
                    ${props.map(p => `<option value="${p}">${p}</option>`).join('')}
                </select>
                <select class="filter-op">
                    ${this.operators.map(o => `<option value="${o.value}">${o.label}</option>`).join('')}
                </select>
                <input type="text" class="filter-val" placeholder="Value">
                <button class="filter-del" data-id="${id}">✕</button>
            `;
            
            container.appendChild(row);
            
            row.querySelector('.filter-del').addEventListener('click', () => {
                row.remove();
                this.updateBuilder();
            });
            
            row.querySelectorAll('select, input').forEach(el => {
                el.addEventListener('change', () => this.updateBuilder());
                el.addEventListener('input', () => this.updateBuilder());
            });
        },
        
        /**
         * Get filters from container
         */
        getFilters: function(containerId) {
            const container = document.getElementById(containerId);
            if (!container) return [];
            
            const filters = [];
            container.querySelectorAll('.filter-row').forEach(row => {
                const prop = row.querySelector('.filter-prop')?.value;
                const op = row.querySelector('.filter-op')?.value;
                const val = row.querySelector('.filter-val')?.value;
                if (prop && op) filters.push({ prop, op, val });
            });
            return filters;
        },
        
        /**
         * Apply date preset
         */
        applyDatePreset: function(preset) {
            const customRange = document.getElementById('cypher-custom-date-range');
            
            if (preset === 'custom') {
                customRange.style.display = 'flex';
                this.builder.datePreset = 'custom';
                return;
            }
            
            customRange.style.display = 'none';
            this.builder.datePreset = preset;
            
            const now = new Date();
            let from, to = now;
            
            switch (preset) {
                case 'today':
                    from = new Date(now.getFullYear(), now.getMonth(), now.getDate());
                    break;
                case 'yesterday':
                    from = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1);
                    to = new Date(now.getFullYear(), now.getMonth(), now.getDate());
                    break;
                case 'last7':
                    from = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
                    break;
                case 'last30':
                    from = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
                    break;
                case 'thisWeek':
                    const dayOfWeek = now.getDay();
                    from = new Date(now.getTime() - dayOfWeek * 24 * 60 * 60 * 1000);
                    from.setHours(0, 0, 0, 0);
                    break;
                case 'lastWeek':
                    const currentDay = now.getDay();
                    const startOfThisWeek = new Date(now.getTime() - currentDay * 24 * 60 * 60 * 1000);
                    from = new Date(startOfThisWeek.getTime() - 7 * 24 * 60 * 60 * 1000);
                    to = startOfThisWeek;
                    break;
                case 'thisMonth':
                    from = new Date(now.getFullYear(), now.getMonth(), 1);
                    break;
                case 'lastMonth':
                    from = new Date(now.getFullYear(), now.getMonth() - 1, 1);
                    to = new Date(now.getFullYear(), now.getMonth(), 1);
                    break;
                default:
                    return;
            }
            
            this.builder.dateFrom = from.toISOString();
            this.builder.dateTo = to.toISOString();
            this.updateBuilder();
        },
        
        /**
         * Set date range by hours
         */
        setDateRange: function(hours) {
            const now = new Date();
            const from = new Date(now.getTime() - hours * 60 * 60 * 1000);
            
            this.builder.dateEnabled = true;
            document.getElementById('cypher-date-enabled').checked = true;
            document.getElementById('cypher-date-content').classList.remove('collapsed');
            
            this.builder.dateFrom = from.toISOString();
            this.builder.dateTo = now.toISOString();
            document.getElementById('cypher-date-preset').value = '';
            document.getElementById('cypher-custom-date-range').style.display = 'flex';
            document.getElementById('cypher-date-from').value = from.toISOString().slice(0, 16);
            document.getElementById('cypher-date-to').value = now.toISOString().slice(0, 16);
            
            this.updateBuilder();
        },
        
        /**
         * Apply quick action
         */
        applyQuickAction: function(action) {
            this.resetBuilder();
            
            switch (action) {
                case 'all':
                    break;
                case 'recent':
                    this.builder.orderBy = 'n.created_at';
                    this.builder.orderDirection = 'DESC';
                    break;
                case 'hubs':
                    this.builder.orderBy = 'degree';
                    this.builder.orderDirection = 'DESC';
                    this.builder.limit = 50;
                    break;
                case 'orphans':
                    this.builder.returnType = 'orphans';
                    break;
                case 'last-hour':
                    this.setDateRange(1);
                    return;
            }
            
            this.syncUIFromBuilder();
            this.updateBuilder();
        },
        
        /**
         * Reset builder
         */
        resetBuilder: function() {
            this.builder = {
                nodeLabel: '',
                nodeFilters: [],
                dateEnabled: false,
                dateFrom: '',
                dateTo: '',
                datePreset: '',
                includeRelationships: false,
                relationshipType: '',
                relationshipDirection: 'any',
                relationshipDepth: 1,
                targetNodeLabel: '',
                targetFilters: [],
                returnType: 'nodes',
                orderBy: '',
                orderDirection: 'DESC',
                limit: 100
            };
        },
        
        /**
         * Sync UI from builder state
         */
        syncUIFromBuilder: function() {
            const b = this.builder;
            document.getElementById('cypher-node-label').value = b.nodeLabel;
            document.getElementById('cypher-date-enabled').checked = b.dateEnabled;
            document.getElementById('cypher-date-content').classList.toggle('collapsed', !b.dateEnabled);
            document.getElementById('cypher-rels-enabled').checked = b.includeRelationships;
            document.getElementById('cypher-rels-content').classList.toggle('collapsed', !b.includeRelationships);
            document.getElementById('cypher-rel-type').value = b.relationshipType;
            document.getElementById('cypher-rel-depth').value = b.relationshipDepth;
            document.getElementById('cypher-depth-val').textContent = b.relationshipDepth;
            document.getElementById('cypher-target-label').value = b.targetNodeLabel;
            document.getElementById('cypher-return-type').value = b.returnType === 'orphans' ? 'nodes' : b.returnType;
            document.getElementById('cypher-order-by').value = b.orderBy;
            document.getElementById('cypher-order-dir-btn').textContent = b.orderDirection === 'DESC' ? '↓' : '↑';
            document.getElementById('cypher-limit-input').value = b.limit;
            
            document.querySelectorAll('.dir-btn').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.dir === b.relationshipDirection);
            });
            
            document.getElementById('cypher-node-filters').innerHTML = '';
            document.getElementById('cypher-target-filters').innerHTML = '';
        },
        
        /**
         * Update builder state from UI
         */
        updateBuilder: function() {
            const b = this.builder;
            b.nodeLabel = document.getElementById('cypher-node-label')?.value || '';
            b.nodeFilters = this.getFilters('cypher-node-filters');
            b.relationshipType = document.getElementById('cypher-rel-type')?.value || '';
            b.targetNodeLabel = document.getElementById('cypher-target-label')?.value || '';
            b.targetFilters = this.getFilters('cypher-target-filters');
            b.returnType = document.getElementById('cypher-return-type')?.value || 'nodes';
            b.orderBy = document.getElementById('cypher-order-by')?.value || '';
            b.limit = parseInt(document.getElementById('cypher-limit-input')?.value) || 100;
            
            // Custom date range
            if (b.datePreset === 'custom') {
                const fromEl = document.getElementById('cypher-date-from');
                const toEl = document.getElementById('cypher-date-to');
                if (fromEl?.value) b.dateFrom = new Date(fromEl.value).toISOString();
                if (toEl?.value) b.dateTo = new Date(toEl.value).toISOString();
            }
            
            this.updatePreview();
        },
        
        /**
         * Build Cypher query
         */
        buildQuery: function() {
            if (this.mode === 'editor') {
                return document.getElementById('cypher-editor')?.value || '';
            }
            
            const b = this.builder;
            let query = '';
            
            // Orphan nodes
            if (b.returnType === 'orphans') {
                query = `MATCH (n${b.nodeLabel ? ':' + this.esc(b.nodeLabel) : ''})\nWHERE NOT (n)--()`;
                query += this.buildFilters(b.nodeFilters, 'n', true);
                if (b.dateEnabled && b.dateFrom) {
                    query += `\n  AND n.created_at >= datetime('${b.dateFrom}')`;
                    if (b.dateTo) query += `\n  AND n.created_at <= datetime('${b.dateTo}')`;
                }
                query += `\nRETURN n\nLIMIT ${b.limit}`;
                return query;
            }
            
            // Regular query
            let matchClause = 'MATCH ';
            const nodePattern = `(n${b.nodeLabel ? ':' + this.esc(b.nodeLabel) : ''})`;
            
            if (b.includeRelationships) {
                const relType = b.relationshipType ? ':' + this.esc(b.relationshipType) : '';
                const depth = b.relationshipDepth > 1 ? `*1..${b.relationshipDepth}` : '';
                const targetLabel = b.targetNodeLabel ? ':' + this.esc(b.targetNodeLabel) : '';
                
                let relPattern;
                if (b.relationshipDirection === 'outgoing') {
                    relPattern = `-[r${relType}${depth}]->(m${targetLabel})`;
                } else if (b.relationshipDirection === 'incoming') {
                    relPattern = `<-[r${relType}${depth}]-(m${targetLabel})`;
                } else {
                    relPattern = `-[r${relType}${depth}]-(m${targetLabel})`;
                }
                
                if (b.returnType === 'paths') {
                    matchClause += `path = ${nodePattern}${relPattern}`;
                } else {
                    matchClause += `${nodePattern}${relPattern}`;
                }
            } else {
                matchClause += nodePattern;
            }
            
            query = matchClause;
            
            // WHERE clause
            let hasWhere = false;
            
            if (b.nodeFilters.length > 0) {
                query += this.buildFilters(b.nodeFilters, 'n', hasWhere);
                hasWhere = true;
            }
            
            // Date filter
            if (b.dateEnabled && b.dateFrom) {
                query += (hasWhere ? '\n  AND ' : '\nWHERE ') + `n.created_at >= datetime('${b.dateFrom}')`;
                hasWhere = true;
                if (b.dateTo) {
                    query += `\n  AND n.created_at <= datetime('${b.dateTo}')`;
                }
            }
            
            if (b.includeRelationships && b.targetFilters.length > 0) {
                query += this.buildFilters(b.targetFilters, 'm', hasWhere);
                hasWhere = true;
            }
            
            // Degree ordering
            if (b.orderBy === 'degree') {
                query += '\nWITH n, size((n)--()) as degree';
                if (b.includeRelationships) {
                    query = query.replace('WITH n,', 'WITH n, r, m,');
                }
            }
            
            // RETURN
            query += '\nRETURN ';
            switch (b.returnType) {
                case 'count':
                    query += 'count(n) as count';
                    break;
                case 'paths':
                    query += 'path';
                    break;
                case 'subgraph':
                    query += b.includeRelationships ? 'n, r, m' : 'n';
                    break;
                default:
                    if (b.orderBy === 'degree') {
                        query += 'n, degree';
                    } else {
                        query += b.includeRelationships ? 'n, r, m' : 'n';
                    }
            }
            
            // ORDER BY
            if (b.orderBy && b.returnType !== 'count') {
                query += `\nORDER BY ${b.orderBy} ${b.orderDirection}`;
            }
            
            // LIMIT
            if (b.returnType !== 'count') {
                query += `\nLIMIT ${b.limit}`;
            }
            
            return query;
        },
        
        /**
         * Build filter clause
         */
        buildFilters: function(filters, nodeVar, hasWhere) {
            if (filters.length === 0) return '';
            
            const conditions = filters.map(f => {
                const prop = `${nodeVar}.${f.prop}`;
                
                if (f.op === 'IS NOT NULL') return `${prop} IS NOT NULL`;
                if (f.op === 'IS NULL') return `${prop} IS NULL`;
                if (f.op === 'CONTAINS') return `toLower(${prop}) CONTAINS toLower('${this.escStr(f.val)}')`;
                if (f.op === 'STARTS WITH' || f.op === 'ENDS WITH') return `${prop} ${f.op} '${this.escStr(f.val)}'`;
                if (f.op === '=~') return `${prop} =~ '${this.escStr(f.val)}'`;
                
                const num = parseFloat(f.val);
                const val = !isNaN(num) && isFinite(num) ? num : `'${this.escStr(f.val)}'`;
                return `${prop} ${f.op} ${val}`;
            });
            
            return (hasWhere ? '\n  AND ' : '\nWHERE ') + conditions.join('\n  AND ');
        },
        
        esc: function(label) {
            return /^[a-zA-Z_][a-zA-Z0-9_]*$/.test(label) ? label : '`' + label.replace(/`/g, '``') + '`';
        },
        
        escStr: function(s) {
            return String(s).replace(/\\/g, '\\\\').replace(/'/g, "\\'");
        },
        
        /**
         * Update preview
         */
        updatePreview: function() {
            const preview = document.getElementById('cypher-query-preview');
            if (preview) preview.textContent = this.buildQuery();
        },
        
        /**
         * Copy query
         */
        copyQuery: function() {
            navigator.clipboard.writeText(this.buildQuery()).then(() => this.notify('Copied!', 'success'));
        },
        
        /**
         * Execute query
         */
        executeQuery: async function() {
            const query = this.buildQuery();
            if (!query.trim()) {
                this.notify('No query', 'warning');
                return;
            }
            
            const replace = document.getElementById('cypher-opt-replace')?.checked ?? true;
            const fit = document.getElementById('cypher-opt-fit')?.checked ?? false;
            const applyLayout = document.getElementById('cypher-opt-apply-layout')?.checked ?? true;
            
            this.showLoading(true, 'Executing...');
            
            try {
                const response = await fetch('http://llm.int:8888/api/graph/cypher', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query, parameters: {}, limit: this.builder.limit })
                });
                
                const data = await response.json();
                
                if (!data.success) {
                    this.showError(data.error || 'Query failed');
                    return;
                }
                
                this.currentResults = data;
                this.addToHistory(query, data);
                this.showResults(data);
                
                if (data.nodes.length > 0 || data.edges.length > 0) {
                    this.updateGraph(data, replace, fit, applyLayout);
                    this.notify(`${data.nodes.length} nodes, ${data.edges.length} edges`, 'success');
                } else {
                    this.notify('No results', 'info');
                }
                
            } catch (e) {
                console.error('Query error:', e);
                this.showError(e.message);
            } finally {
                this.showLoading(false);
            }
        },
        
        /**
         * Update graph with results
         */
        updateGraph: function(data, replace, fit, applyLayout) {
            if (!window.network) return;
            
            try {
                const nodes = data.nodes.map(n => ({
                    id: n.id,
                    label: n.label || n.id,
                    title: n.title || n.label,
                    color: n.color || '#3b82f6',
                    size: n.size || 25,
                    properties: n.properties,
                    type: n.label,
                    created_at: n.properties?.created_at
                }));
                
                const edges = data.edges.map((e, idx) => ({
                    id: e.id || `edge_${e.from}_${e.to}_${idx}`,
                    from: e.from,
                    to: e.to,
                    label: e.label,
                    title: e.label
                }));
                
                if (replace) {
                    network.body.data.nodes.clear();
                    network.body.data.edges.clear();
                }
                
                const existingNodes = new Set(network.body.data.nodes.getIds());
                const existingEdges = new Set(network.body.data.edges.getIds());
                
                const newNodes = nodes.filter(n => !existingNodes.has(n.id));
                const newEdges = edges.filter(e => !existingEdges.has(e.id));
                
                if (newNodes.length) network.body.data.nodes.add(newNodes);
                if (newEdges.length) network.body.data.edges.add(newEdges);
                
                // Apply layout if enabled
                if (applyLayout) {
                    setTimeout(() => this.applyCurrentLayout(), 100);
                }
                
                // Update GraphAddon
                if (window.GraphAddon) {
                    setTimeout(() => {
                        window.GraphAddon.buildNodesData();
                        window.GraphAddon.initializeFilters();
                    }, 300);
                }
                
                // Update counts
                const nodeCount = document.getElementById('nodeCount');
                const edgeCount = document.getElementById('edgeCount');
                if (nodeCount) nodeCount.textContent = network.body.data.nodes.length;
                if (edgeCount) edgeCount.textContent = network.body.data.edges.length;
                
                if (fit) setTimeout(() => this.fitView(), 500);
                
                // Hide loader
                if (window.graphLoaderUtils) window.graphLoaderUtils.hide(true);
                
                // Apply theme
                // if (window.applyThemeToGraph) setTimeout(() => window.applyThemeToGraph(), 500);
                
            } catch (e) {
                console.error('Graph update error:', e);
            }
        },
        
        // ==========================================
        // LAYOUT FUNCTIONS
        // ==========================================
        
        /**
         * Set layout mode
         */
        setLayoutMode: function(mode) {
            this.layout.mode = mode;
            
            document.querySelectorAll('.layout-btn').forEach(b => b.classList.toggle('active', b.dataset.layout === mode));
            
            // Show/hide options
            document.getElementById('cypher-timeline-options').style.display = mode === 'timeline' ? 'block' : 'none';
            document.getElementById('cypher-grouped-options').style.display = mode === 'grouped' ? 'block' : 'none';
        },
        
        /**
         * Apply current layout
         */
        applyCurrentLayout: function() {
            if (!window.network) return;
            
            const nodes = network.body.data.nodes.get();
            if (nodes.length === 0) return;
            
            // First, configure optimized physics
            this.configureOptimizedPhysics();
            
            switch (this.layout.mode) {
                case 'timeline':
                    this.applyTimelineLayout(nodes);
                    break;
                case 'hierarchical':
                    this.applyHierarchicalLayout();
                    break;
                case 'grouped':
                    this.applyGroupedLayout(nodes);
                    break;
                case 'circular':
                    this.applyCircularLayout(nodes);
                    break;
                default:
                    this.applyForceLayout();
            }
        },
        
        /**
         * Configure optimized physics for faster settling
         */
        configureOptimizedPhysics: function() {
            if (!window.network) return;
            
            network.setOptions({
                physics: {
                    enabled: true,
                    solver: 'barnesHut',
                    barnesHut: {
                        gravitationalConstant: -2000,
                        centralGravity: 0.3,
                        springLength: 150,
                        springConstant: 0.04,
                        damping: 0.9,
                        avoidOverlap: 0.5
                    },
                    stabilization: {
                        enabled: true,
                        iterations: 100,
                        updateInterval: 25,
                        fit: true
                    },
                    maxVelocity: 50,
                    minVelocity: 0.75,
                    timestep: 0.5
                }
            });
        },
        
        /**
         * Apply timeline layout
         */
        applyTimelineLayout: function(nodes) {
            const prop = this.layout.timelineProperty;
            
            // Sort nodes by time
            const sortedNodes = nodes.filter(n => {
                const props = n.properties || {};
                return props[prop] || n[prop];
            }).sort((a, b) => {
                const aTime = new Date(a.properties?.[prop] || a[prop] || 0).getTime();
                const bTime = new Date(b.properties?.[prop] || b[prop] || 0).getTime();
                return aTime - bTime;
            });
            
            const noTimeNodes = nodes.filter(n => {
                const props = n.properties || {};
                return !(props[prop] || n[prop]);
            });
            
            if (sortedNodes.length === 0) {
                this.notify('No nodes with timestamp found', 'warning');
                return;
            }
            
            const container = document.getElementById('graph');
            const width = container?.clientWidth || 1200;
            const height = container?.clientHeight || 600;
            
            // Disable physics for positioning
            network.setOptions({ physics: { enabled: false } });
            
            const updates = [];
            const spacing = Math.max(150, width / (sortedNodes.length + 1));
            
            sortedNodes.forEach((node, i) => {
                updates.push({
                    id: node.id,
                    x: spacing * (i + 1) - width / 2,
                    y: (Math.random() - 0.5) * 200
                });
            });
            
            // Place nodes without timestamps below
            noTimeNodes.forEach((node, i) => {
                updates.push({
                    id: node.id,
                    x: (i % 10) * 100 - 450,
                    y: height / 2 - 100
                });
            });
            
            network.body.data.nodes.update(updates);
            
            setTimeout(() => {
                network.fit({ animation: { duration: 500 } });
            }, 100);
            
            this.notify('Timeline layout applied', 'success');
        },
        
        /**
         * Apply hierarchical layout
         */
        applyHierarchicalLayout: function() {
            network.setOptions({
                layout: {
                    hierarchical: {
                        enabled: true,
                        direction: 'UD',
                        sortMethod: 'directed',
                        nodeSpacing: 150,
                        levelSeparation: 150,
                        treeSpacing: 200
                    }
                },
                physics: {
                    enabled: false
                }
            });
            
            setTimeout(() => {
                network.fit({ animation: { duration: 500 } });
                setTimeout(() => {
                    network.setOptions({ layout: { hierarchical: { enabled: false } } });
                }, 100);
            }, 500);
            
            this.notify('Hierarchical layout applied', 'success');
        },
        
        /**
         * Apply grouped layout
         */
        applyGroupedLayout: function(nodes) {
            const groupProp = this.layout.groupBy;
            
            // Group nodes
            const groups = {};
            nodes.forEach(n => {
                const props = n.properties || {};
                const groupVal = props[groupProp] || n[groupProp] || n.type || 'Other';
                if (!groups[groupVal]) groups[groupVal] = [];
                groups[groupVal].push(n);
            });
            
            const groupNames = Object.keys(groups);
            const container = document.getElementById('graph');
            const width = container?.clientWidth || 1200;
            const height = container?.clientHeight || 600;
            
            // Disable physics for positioning
            network.setOptions({ physics: { enabled: false } });
            
            const updates = [];
            const groupCount = groupNames.length;
            const cols = Math.ceil(Math.sqrt(groupCount));
            const cellWidth = width / cols;
            const cellHeight = height / Math.ceil(groupCount / cols);
            
            groupNames.forEach((groupName, gi) => {
                const col = gi % cols;
                const row = Math.floor(gi / cols);
                const centerX = col * cellWidth + cellWidth / 2 - width / 2;
                const centerY = row * cellHeight + cellHeight / 2 - height / 2;
                
                const groupNodes = groups[groupName];
                const nodeCount = groupNodes.length;
                const radius = Math.min(cellWidth, cellHeight) * 0.35;
                
                groupNodes.forEach((node, ni) => {
                    const angle = (2 * Math.PI * ni) / nodeCount;
                    const r = nodeCount > 1 ? radius * (0.5 + Math.random() * 0.5) : 0;
                    updates.push({
                        id: node.id,
                        x: centerX + r * Math.cos(angle),
                        y: centerY + r * Math.sin(angle)
                    });
                });
            });
            
            network.body.data.nodes.update(updates);
            
            setTimeout(() => {
                network.fit({ animation: { duration: 500 } });
            }, 100);
            
            this.notify(`Grouped by ${groupProp} (${groupCount} groups)`, 'success');
        },
        
        /**
         * Apply circular layout
         */
        applyCircularLayout: function(nodes) {
            network.setOptions({ physics: { enabled: false } });
            
            const count = nodes.length;
            const radius = Math.max(200, count * 20);
            
            const updates = nodes.map((node, i) => {
                const angle = (2 * Math.PI * i) / count;
                return {
                    id: node.id,
                    x: radius * Math.cos(angle),
                    y: radius * Math.sin(angle)
                };
            });
            
            network.body.data.nodes.update(updates);
            
            setTimeout(() => {
                network.fit({ animation: { duration: 500 } });
            }, 100);
            
            this.notify('Circular layout applied', 'success');
        },
        
        /**
         * Apply force-directed layout
         */
        applyForceLayout: function() {
            this.configureOptimizedPhysics();
            network.setOptions({ layout: { hierarchical: { enabled: false } } });
            this.quickStabilize();
        },
        
        /**
         * Quick stabilize
         */
        quickStabilize: function() {
            if (!window.network) return;
            
            this.notify('Stabilizing...', 'info');
            
            network.setOptions({
                physics: {
                    enabled: true,
                    stabilization: {
                        enabled: true,
                        iterations: 150,
                        updateInterval: 10
                    }
                }
            });
            
            network.stabilize(150);
            
            network.once('stabilizationIterationsDone', () => {
                network.setOptions({
                    physics: {
                        stabilization: { enabled: false },
                        barnesHut: {
                            gravitationalConstant: -1500,
                            springConstant: 0.02,
                            damping: 0.95
                        }
                    }
                });
                this.notify('Stabilized', 'success');
            });
        },
        
        /**
         * Toggle physics
         */
        togglePhysics: function(enabled) {
            if (!window.network) return;
            network.setOptions({ physics: { enabled } });
            this.layout.physicsEnabled = enabled;
        },
        
        /**
         * Update physics settings
         */
        updatePhysics: function(param, value) {
            if (!window.network) return;
            
            const val = parseFloat(value);
            
            switch (param) {
                case 'gravity':
                    document.getElementById('cypher-gravity-val').textContent = val;
                    network.setOptions({ physics: { barnesHut: { gravitationalConstant: val } } });
                    break;
                case 'spring':
                    document.getElementById('cypher-spring-val').textContent = val;
                    network.setOptions({ physics: { barnesHut: { springLength: val } } });
                    break;
                case 'damping':
                    document.getElementById('cypher-damping-val').textContent = val.toFixed(2);
                    network.setOptions({ physics: { barnesHut: { damping: val } } });
                    break;
            }
        },
        
        /**
         * Freeze graph
         */
        freezeGraph: function() {
            if (!window.network) return;
            network.setOptions({ physics: { enabled: false } });
            document.getElementById('cypher-physics-enabled').checked = false;
            this.notify('Graph frozen', 'info');
        },
        
        /**
         * Unfreeze graph
         */
        unfreezeGraph: function() {
            if (!window.network) return;
            network.setOptions({ physics: { enabled: true } });
            document.getElementById('cypher-physics-enabled').checked = true;
            this.notify('Graph unfrozen', 'info');
        },
        
        /**
         * Fit view
         */
        fitView: function() {
            if (window.network) {
                network.fit({ animation: { duration: 500, easingFunction: 'easeInOutQuad' } });
            }
        },
        
        /**
         * Reset layout
         */
        resetLayout: function() {
            this.setLayoutMode('force');
            this.applyForceLayout();
        },
        
        // ==========================================
        // UI HELPERS
        // ==========================================
        
        showResults: function(data) {
            const box = document.getElementById('cypher-results-box');
            const content = document.getElementById('cypher-results-content');
            if (!box || !content) return;
            
            box.style.display = 'block';
            content.innerHTML = `
                <div class="results-stats">
                    <span><b>${data.stats.node_count || 0}</b> nodes</span>
                    <span><b>${data.stats.edge_count || 0}</b> edges</span>
                    <span><b>${data.stats.result_count || 0}</b> records</span>
                </div>
            `;
        },
        
        showStats: async function() {
            this.showLoading(true, 'Loading stats...');
            try {
                const response = await fetch('http://llm.int:8888/api/graph/stats');
                const data = await response.json();
                
                const box = document.getElementById('cypher-results-box');
                const content = document.getElementById('cypher-results-content');
                box.style.display = 'block';
                
                content.innerHTML = `
                    <div class="stats-display">
                        <div class="stat-big"><b>${(data.total_nodes || 0).toLocaleString()}</b> nodes</div>
                        <div class="stat-big"><b>${(data.total_relationships || 0).toLocaleString()}</b> relationships</div>
                        <div class="stat-section">
                            <b>By Type:</b>
                            ${Object.entries(data.nodes_by_type || {}).slice(0, 8).map(([t, c]) => 
                                `<div class="stat-row"><span>${t}</span><span>${c}</span></div>`
                            ).join('')}
                        </div>
                    </div>
                `;
            } catch (e) {
                this.notify('Failed to load stats', 'error');
            } finally {
                this.showLoading(false);
            }
        },
        
        formatQuery: function() {
            const editor = document.getElementById('cypher-editor');
            if (!editor) return;
            
            let q = editor.value;
            ['MATCH', 'WHERE', 'RETURN', 'ORDER BY', 'LIMIT', 'WITH', 'AND', 'OR'].forEach(kw => {
                q = q.replace(new RegExp(`\\s+${kw}\\s+`, 'gi'), `\n${kw} `);
            });
            editor.value = q.trim();
            this.updateLineNumbers();
        },
        
        updateLineNumbers: function() {
            const editor = document.getElementById('cypher-editor');
            const nums = document.getElementById('cypher-line-nums');
            if (!editor || !nums) return;
            
            const lines = editor.value.split('\n');
            nums.innerHTML = lines.map((_, i) => `<div>${i + 1}</div>`).join('');
        },
        
        // History & Saved
        addToHistory: function(query, result) {
            this.queryHistory.unshift({
                query,
                timestamp: new Date().toISOString(),
                nodes: result?.stats?.node_count || 0,
                edges: result?.stats?.edge_count || 0
            });
            if (this.queryHistory.length > this.maxHistory) {
                this.queryHistory = this.queryHistory.slice(0, this.maxHistory);
            }
            try { localStorage.setItem('cypher_history', JSON.stringify(this.queryHistory)); } catch(e) {}
            this.renderHistory();
        },
        
        renderHistory: function() {
            const container = document.getElementById('cypher-history-container');
            if (!container) return;
            
            if (this.queryHistory.length === 0) {
                container.innerHTML = '<div class="empty-msg">No history</div>';
                return;
            }
            
            container.innerHTML = this.queryHistory.slice(0, 10).map((h, i) => `
                <div class="list-item" data-idx="${i}">
                    <div class="item-text">${this.escHtml(h.query.substring(0, 40))}...</div>
                    <div class="item-meta">${h.nodes}n / ${h.edges}e</div>
                </div>
            `).join('');
            
            container.querySelectorAll('.list-item').forEach(item => {
                item.addEventListener('click', () => {
                    const h = this.queryHistory[parseInt(item.dataset.idx)];
                    if (h) {
                        this.switchTab('editor');
                        document.getElementById('cypher-editor').value = h.query;
                        this.updateLineNumbers();
                        this.updatePreview();
                    }
                });
            });
        },
        
        populateTemplates: function() {
            const container = document.getElementById('cypher-templates-container');
            if (!container) return;
            
            container.innerHTML = this.templates.map((t, i) => `
                <div class="list-item" data-idx="${i}">
                    <div class="item-text">${t.name}</div>
                </div>
            `).join('');
            
            container.querySelectorAll('.list-item').forEach(item => {
                item.addEventListener('click', () => {
                    const t = this.templates[parseInt(item.dataset.idx)];
                    if (t) {
                        this.switchTab('editor');
                        document.getElementById('cypher-editor').value = t.query;
                        this.updateLineNumbers();
                        this.updatePreview();
                    }
                });
            });
        },
        
        saveCurrentQuery: function() {
            const query = this.buildQuery();
            if (!query) return;
            const name = prompt('Save as:');
            if (!name) return;
            this.savedQueries.push({ name, query });
            try { localStorage.setItem('cypher_saved', JSON.stringify(this.savedQueries)); } catch(e) {}
            this.renderSaved();
            this.notify('Saved', 'success');
        },
        
        renderSaved: function() {
            const container = document.getElementById('cypher-saved-container');
            if (!container) return;
            
            if (this.savedQueries.length === 0) {
                container.innerHTML = '<div class="empty-msg">No saved queries</div>';
                return;
            }
            
            container.innerHTML = this.savedQueries.map((s, i) => `
                <div class="list-item saved-item">
                    <div class="item-text" data-idx="${i}">${this.escHtml(s.name)}</div>
                    <button class="del-btn" data-idx="${i}">✕</button>
                </div>
            `).join('');
            
            container.querySelectorAll('.item-text').forEach(el => {
                el.addEventListener('click', () => {
                    const s = this.savedQueries[parseInt(el.dataset.idx)];
                    if (s) {
                        this.switchTab('editor');
                        document.getElementById('cypher-editor').value = s.query;
                        this.updateLineNumbers();
                        this.updatePreview();
                    }
                });
            });
            
            container.querySelectorAll('.del-btn').forEach(el => {
                el.addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.savedQueries.splice(parseInt(el.dataset.idx), 1);
                    try { localStorage.setItem('cypher_saved', JSON.stringify(this.savedQueries)); } catch(e) {}
                    this.renderSaved();
                });
            });
        },
        
        loadSavedQueries: function() {
            try { this.savedQueries = JSON.parse(localStorage.getItem('cypher_saved') || '[]'); } catch(e) {}
        },
        
        loadHistory: function() {
            try { this.queryHistory = JSON.parse(localStorage.getItem('cypher_history') || '[]'); } catch(e) {}
        },
        
        showLoading: function(show, text = 'Loading...') {
            const el = document.getElementById('cypher-loading-overlay');
            if (el) {
                el.style.display = show ? 'flex' : 'none';
                document.getElementById('cypher-loading-text').textContent = text;
            }
        },
        
        showError: function(msg) {
            this.notify(msg, 'error');
        },
        
        notify: function(msg, type = 'info') {
            document.querySelectorAll('.cypher-toast').forEach(t => t.remove());
            
            const toast = document.createElement('div');
            toast.className = `cypher-toast ${type}`;
            toast.textContent = msg;
            document.body.appendChild(toast);
            
            setTimeout(() => toast.classList.add('show'), 10);
            setTimeout(() => {
                toast.classList.remove('show');
                setTimeout(() => toast.remove(), 300);
            }, 3000);
        },
        
        escHtml: function(s) {
            const div = document.createElement('div');
            div.textContent = String(s);
            return div.innerHTML;
        }
    };
    
    // Init
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => CypherQuery.init());
    } else {
        CypherQuery.init();
    }
})();