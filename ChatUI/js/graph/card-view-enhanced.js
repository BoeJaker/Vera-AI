/**
 * GraphCardView Enhanced - Advanced Features
 * Adds search, filters, multiple layouts, and more interactivity
 * 
 * Include this AFTER graph-card-view.js
 */

(function() {
    'use strict';
    
    if (!window.GraphCardView) {
        console.error('GraphCardView Enhanced: Base module not loaded');
        return;
    }
    
    // Extend the base GraphCardView
    const CardView = window.GraphCardView;
    
    /**
     * Enhanced features namespace
     */
    CardView.enhanced = {
        
        // Layout algorithms
        layouts: {
            hierarchical: true,
            radial: false,
            force: false,
            circular: false
        },
        
        currentLayout: 'hierarchical',
        
        // Search state
        searchResults: [],
        searchTerm: '',
        
        // Filter state
        filters: {
            labels: new Set(),
            levels: new Set(),
            properties: {}
        },
        
        activeFilters: {
            labels: new Set(),
            levels: new Set()
        },
        
        /**
         * Initialize enhanced features
         */
        init: function() {
            console.log('GraphCardView Enhanced: Initializing...');
            
            this.addEnhancedControls();
            this.addSearchPanel();
            this.addFilterPanel();
            this.addLayoutSelector();
            
            console.log('GraphCardView Enhanced: Ready');
        },
        
        /**
         * Add enhanced control panel
         */
        addEnhancedControls: function() {
            const container = CardView.container;
            if (!container) return;
            
            const panel = document.createElement('div');
            panel.id = 'card-view-enhanced-panel';
            panel.style.cssText = `
                position: absolute;
                top: 20px;
                left: 20px;
                background: var(--panel-bg);
                border: 1px solid var(--border);
                border-radius: 8px;
                padding: 16px;
                max-width: 300px;
                backdrop-filter: blur(10px);
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
                z-index: 1000;
                display: none;
            `;
            
            panel.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                    <h3 style="color: var(--text); margin: 0; font-size: 16px;">Card View Controls</h3>
                    <button onclick="window.GraphCardView.enhanced.togglePanel()" style="
                        background: none; border: none; color: var(--text-secondary);
                        cursor: pointer; font-size: 18px; padding: 0;
                    ">✕</button>
                </div>
                <div id="enhanced-controls-content"></div>
            `;
            
            container.appendChild(panel);
            
            // Toggle button
            const toggleBtn = document.createElement('button');
            toggleBtn.textContent = '⚙️ Controls';
            toggleBtn.style.cssText = `
                position: absolute;
                top: 80px;
                left: 20px;
                padding: 10px 16px;
                background: var(--panel-bg);
                border: 1px solid var(--border);
                border-radius: 6px;
                color: var(--text);
                cursor: pointer;
                font-weight: 600;
                font-size: 13px;
                z-index: 999;
                backdrop-filter: blur(10px);
            `;
            toggleBtn.onclick = () => this.togglePanel();
            
            container.appendChild(toggleBtn);
        },
        
        /**
         * Add search panel
         */
        addSearchPanel: function() {
            const container = CardView.container;
            if (!container) return;
            
            const searchPanel = document.createElement('div');
            searchPanel.id = 'card-view-search-panel';
            searchPanel.style.cssText = `
                position: absolute;
                top: 20px;
                left: 50%;
                transform: translateX(-50%);
                background: var(--panel-bg);
                border: 1px solid var(--border);
                border-radius: 8px;
                padding: 12px;
                backdrop-filter: blur(10px);
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
                z-index: 1000;
                min-width: 400px;
            `;
            
            searchPanel.innerHTML = `
                <div style="display: flex; gap: 8px; align-items: center;">
                    <input 
                        type="text" 
                        id="card-view-search-input" 
                        placeholder="Search nodes..."
                        style="
                            flex: 1;
                            padding: 8px 12px;
                            background: var(--bg);
                            border: 1px solid var(--border);
                            border-radius: 6px;
                            color: var(--text);
                            font-size: 13px;
                        "
                    >
                    <button onclick="window.GraphCardView.enhanced.search()" style="
                        padding: 8px 16px;
                        background: var(--accent);
                        border: none;
                        border-radius: 6px;
                        color: var(--text-inverted);
                        cursor: pointer;
                        font-weight: 600;
                        font-size: 13px;
                    ">🔍 Search</button>
                    <button onclick="window.GraphCardView.enhanced.clearSearch()" style="
                        padding: 8px 12px;
                        background: var(--bg-surface);
                        border: 1px solid var(--border);
                        border-radius: 6px;
                        color: var(--text);
                        cursor: pointer;
                        font-size: 13px;
                    ">✕</button>
                </div>
                <div id="card-view-search-results" style="
                    margin-top: 12px;
                    max-height: 200px;
                    overflow-y: auto;
                    display: none;
                "></div>
            `;
            
            container.appendChild(searchPanel);
            
            // Enter key handler
            const input = searchPanel.querySelector('#card-view-search-input');
            input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') this.search();
            });
            
            // Live search
            input.addEventListener('input', (e) => {
                if (e.target.value.length > 2) {
                    this.liveSearch(e.target.value);
                }
            });
        },
        
        /**
         * Add filter panel
         */
        addFilterPanel: function() {
            const container = CardView.container;
            if (!container) return;
            
            const filterPanel = document.createElement('div');
            filterPanel.id = 'card-view-filter-panel';
            filterPanel.style.cssText = `
                position: absolute;
                bottom: 20px;
                left: 20px;
                background: var(--panel-bg);
                border: 1px solid var(--border);
                border-radius: 8px;
                padding: 16px;
                max-width: 280px;
                max-height: 400px;
                overflow-y: auto;
                backdrop-filter: blur(10px);
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
                z-index: 1000;
                display: none;
            `;
            
            filterPanel.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                    <h3 style="color: var(--text); margin: 0; font-size: 14px;">Filters</h3>
                    <button onclick="window.GraphCardView.enhanced.toggleFilters()" style="
                        background: none; border: none; color: var(--text-secondary);
                        cursor: pointer; font-size: 18px; padding: 0;
                    ">✕</button>
                </div>
                <div id="card-view-filters-content">
                    <div style="margin-bottom: 16px;">
                        <div style="color: var(--text-secondary); font-size: 12px; font-weight: 600; margin-bottom: 8px;">
                            By Label
                        </div>
                        <div id="label-filters"></div>
                    </div>
                    <div>
                        <div style="color: var(--text-secondary); font-size: 12px; font-weight: 600; margin-bottom: 8px;">
                            By Level
                        </div>
                        <div id="level-filters"></div>
                    </div>
                </div>
            `;
            
            container.appendChild(filterPanel);
            
            // Toggle button
            const toggleBtn = document.createElement('button');
            toggleBtn.textContent = '🔍 Filters';
            toggleBtn.style.cssText = `
                position: absolute;
                bottom: 20px;
                left: 20px;
                padding: 10px 16px;
                background: var(--panel-bg);
                border: 1px solid var(--border);
                border-radius: 6px;
                color: var(--text);
                cursor: pointer;
                font-weight: 600;
                font-size: 13px;
                z-index: 999;
                backdrop-filter: blur(10px);
            `;
            toggleBtn.onclick = () => this.toggleFilters();
            
            container.appendChild(toggleBtn);
        },
        
        /**
         * Add layout selector
         */
        addLayoutSelector: function() {
            const container = CardView.container;
            if (!container) return;
            
            const selector = document.createElement('div');
            selector.style.cssText = `
                position: absolute;
                bottom: 20px;
                right: 20px;
                background: var(--panel-bg);
                border: 1px solid var(--border);
                border-radius: 6px;
                padding: 8px 12px;
                backdrop-filter: blur(10px);
                z-index: 999;
            `;
            
            selector.innerHTML = `
                <select id="card-view-layout-selector" style="
                    background: var(--bg);
                    border: 1px solid var(--border);
                    border-radius: 4px;
                    color: var(--text);
                    padding: 6px 10px;
                    font-size: 13px;
                    cursor: pointer;
                " onchange="window.GraphCardView.enhanced.changeLayout(this.value)">
                    <option value="hierarchical">📊 Hierarchical</option>
                    <option value="radial">🎯 Radial</option>
                    <option value="force">⚛️ Force-Directed</option>
                    <option value="circular">⭕ Circular</option>
                </select>
            `;
            
            container.appendChild(selector);
        },
        
        /**
         * Perform search
         */
        search: function() {
            const input = document.getElementById('card-view-search-input');
            if (!input) return;
            
            this.searchTerm = input.value.toLowerCase().trim();
            if (!this.searchTerm) {
                this.clearSearch();
                return;
            }
            
            this.searchResults = Array.from(CardView.nodes.values()).filter(node => {
                const searchableText = [
                    node.data.display_name,
                    ...(node.data.labels || []),
                    ...Object.values(node.data.properties || {})
                ].join(' ').toLowerCase();
                
                return searchableText.includes(this.searchTerm);
            });
            
            this.displaySearchResults();
        },
        
        /**
         * Live search as user types
         */
        liveSearch: function(term) {
            this.searchTerm = term.toLowerCase().trim();
            
            if (!this.searchTerm) {
                this.clearSearch();
                return;
            }
            
            this.searchResults = Array.from(CardView.nodes.values())
                .filter(node => {
                    const searchableText = [
                        node.data.display_name,
                        ...(node.data.labels || [])
                    ].join(' ').toLowerCase();
                    
                    return searchableText.includes(this.searchTerm);
                })
                .slice(0, 10); // Limit for performance
            
            this.displaySearchResults();
        },
        
        /**
         * Display search results
         */
        displaySearchResults: function() {
            const resultsContainer = document.getElementById('card-view-search-results');
            if (!resultsContainer) return;
            
            if (this.searchResults.length === 0) {
                resultsContainer.innerHTML = `
                    <div style="padding: 12px; text-align: center; color: var(--text-secondary); font-size: 12px;">
                        No results found
                    </div>
                `;
                resultsContainer.style.display = 'block';
                return;
            }
            
            let html = '';
            this.searchResults.forEach(node => {
                html += `
                    <div onclick="window.GraphCardView.focusNode('${node.id}')" style="
                        padding: 8px 12px;
                        background: var(--bg);
                        border: 1px solid var(--border);
                        border-radius: 6px;
                        margin-bottom: 6px;
                        cursor: pointer;
                        transition: all 0.2s;
                    " onmouseover="this.style.background='var(--hover)'" onmouseout="this.style.background='var(--bg)'">
                        <div style="color: var(--text); font-size: 13px; font-weight: 600;">
                            ${this.escapeHtml(node.data.display_name)}
                        </div>
                        ${node.data.labels && node.data.labels.length > 0 ? `
                            <div style="color: var(--text-secondary); font-size: 11px; margin-top: 4px;">
                                ${node.data.labels.slice(0, 2).join(', ')}
                            </div>
                        ` : ''}
                    </div>
                `;
            });
            
            resultsContainer.innerHTML = html;
            resultsContainer.style.display = 'block';
            
            // Highlight matching cards in view
            this.highlightSearchResults();
        },
        
        /**
         * Highlight search results in the card view
         */
        highlightSearchResults: function() {
            // Remove previous highlights
            document.querySelectorAll('.graph-card-node').forEach(card => {
                card.classList.remove('highlighted');
            });
            
            // Add highlights to matching cards
            this.searchResults.forEach(node => {
                const card = document.querySelector(`[data-node-id="${node.id}"]`);
                if (card) {
                    card.classList.add('highlighted');
                }
            });
        },
        
        /**
         * Clear search
         */
        clearSearch: function() {
            this.searchTerm = '';
            this.searchResults = [];
            
            const input = document.getElementById('card-view-search-input');
            if (input) input.value = '';
            
            const resultsContainer = document.getElementById('card-view-search-results');
            if (resultsContainer) {
                resultsContainer.style.display = 'none';
                resultsContainer.innerHTML = '';
            }
            
            // Remove highlights
            document.querySelectorAll('.graph-card-node.highlighted').forEach(card => {
                card.classList.remove('highlighted');
            });
        },
        
        /**
         * Build filter options from data
         */
        buildFilterOptions: function() {
            this.filters.labels.clear();
            this.filters.levels.clear();
            
            CardView.nodes.forEach(node => {
                // Collect labels
                if (node.data.labels) {
                    node.data.labels.forEach(label => this.filters.labels.add(label));
                }
                
                // Collect levels
                this.filters.levels.add(node.level);
            });
            
            this.renderFilterOptions();
        },
        
        /**
         * Render filter options
         */
        renderFilterOptions: function() {
            // Render label filters
            const labelFilters = document.getElementById('label-filters');
            if (labelFilters) {
                let html = '';
                Array.from(this.filters.labels).forEach(label => {
                    const checked = this.activeFilters.labels.size === 0 || 
                                   this.activeFilters.labels.has(label);
                    html += `
                        <label style="display: flex; align-items: center; margin-bottom: 6px; cursor: pointer;">
                            <input type="checkbox" ${checked ? 'checked' : ''} 
                                   onchange="window.GraphCardView.enhanced.toggleLabelFilter('${label}')"
                                   style="margin-right: 8px;">
                            <span style="color: var(--text); font-size: 12px;">${this.escapeHtml(label)}</span>
                        </label>
                    `;
                });
                labelFilters.innerHTML = html;
            }
            
            // Render level filters
            const levelFilters = document.getElementById('level-filters');
            if (levelFilters) {
                let html = '';
                Array.from(this.filters.levels).sort((a, b) => a - b).forEach(level => {
                    const checked = this.activeFilters.levels.size === 0 || 
                                   this.activeFilters.levels.has(level);
                    html += `
                        <label style="display: flex; align-items: center; margin-bottom: 6px; cursor: pointer;">
                            <input type="checkbox" ${checked ? 'checked' : ''} 
                                   onchange="window.GraphCardView.enhanced.toggleLevelFilter(${level})"
                                   style="margin-right: 8px;">
                            <span style="color: var(--text); font-size: 12px;">Level ${level}</span>
                        </label>
                    `;
                });
                levelFilters.innerHTML = html;
            }
        },
        
        /**
         * Toggle label filter
         */
        toggleLabelFilter: function(label) {
            if (this.activeFilters.labels.has(label)) {
                this.activeFilters.labels.delete(label);
            } else {
                this.activeFilters.labels.add(label);
            }
            
            this.applyFilters();
        },
        
        /**
         * Toggle level filter
         */
        toggleLevelFilter: function(level) {
            if (this.activeFilters.levels.has(level)) {
                this.activeFilters.levels.delete(level);
            } else {
                this.activeFilters.levels.add(level);
            }
            
            this.applyFilters();
        },
        
        /**
         * Apply active filters
         */
        applyFilters: function() {
            // TODO: Implement filtered rendering
            // For now, just re-render
            CardView.render();
        },
        
        /**
         * Change layout algorithm
         */
        changeLayout: function(layoutType) {
            console.log('Changing layout to:', layoutType);
            this.currentLayout = layoutType;
            
            switch(layoutType) {
                case 'hierarchical':
                    this.applyHierarchicalLayout();
                    break;
                case 'radial':
                    this.applyRadialLayout();
                    break;
                case 'force':
                    this.applyForceLayout();
                    break;
                case 'circular':
                    this.applyCircularLayout();
                    break;
            }
            
            CardView.render();
        },
        
        /**
         * Apply hierarchical layout (default)
         */
        applyHierarchicalLayout: function() {
            CardView.calculatePositions();
        },
        
        /**
         * Apply radial layout
         */
        applyRadialLayout: function() {
            const centerX = 400;
            const centerY = 300;
            const radiusPerLevel = 200;
            
            const levels = new Map();
            CardView.nodes.forEach((node, id) => {
                if (!levels.has(node.level)) {
                    levels.set(node.level, []);
                }
                levels.get(node.level).push(id);
            });
            
            levels.forEach((nodeIds, level) => {
                const radius = level * radiusPerLevel;
                const angleStep = (2 * Math.PI) / nodeIds.length;
                
                nodeIds.forEach((id, index) => {
                    const node = CardView.nodes.get(id);
                    if (!node) return;
                    
                    const angle = index * angleStep;
                    node.x = centerX + radius * Math.cos(angle) - CardView.layout.cardWidth / 2;
                    node.y = centerY + radius * Math.sin(angle) - CardView.layout.cardHeight / 2;
                });
            });
        },
        
        /**
         * Apply circular layout
         */
        applyCircularLayout: function() {
            const centerX = 500;
            const centerY = 400;
            const radius = 400;
            
            const nodes = Array.from(CardView.nodes.values());
            const angleStep = (2 * Math.PI) / nodes.length;
            
            nodes.forEach((node, index) => {
                const angle = index * angleStep;
                node.x = centerX + radius * Math.cos(angle) - CardView.layout.cardWidth / 2;
                node.y = centerY + radius * Math.sin(angle) - CardView.layout.cardHeight / 2;
            });
        },
        
        /**
         * Apply force-directed layout (simplified)
         */
        applyForceLayout: function() {
            // Simple force-directed layout simulation
            const iterations = 50;
            const k = 200; // Optimal distance
            
            for (let i = 0; i < iterations; i++) {
                // Repulsive forces between all nodes
                CardView.nodes.forEach((node1, id1) => {
                    let fx = 0, fy = 0;
                    
                    CardView.nodes.forEach((node2, id2) => {
                        if (id1 === id2) return;
                        
                        const dx = node1.x - node2.x;
                        const dy = node1.y - node2.y;
                        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                        
                        const force = k * k / dist;
                        fx += (dx / dist) * force;
                        fy += (dy / dist) * force;
                    });
                    
                    node1.x += fx * 0.01;
                    node1.y += fy * 0.01;
                });
                
                // Attractive forces for connected nodes
                CardView.edges.forEach(edge => {
                    const node1 = CardView.nodes.get(edge.from);
                    const node2 = CardView.nodes.get(edge.to);
                    
                    if (!node1 || !node2) return;
                    
                    const dx = node2.x - node1.x;
                    const dy = node2.y - node1.y;
                    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                    
                    const force = dist * dist / k;
                    const fx = (dx / dist) * force * 0.01;
                    const fy = (dy / dist) * force * 0.01;
                    
                    node1.x += fx;
                    node1.y += fy;
                    node2.x -= fx;
                    node2.y -= fy;
                });
            }
        },
        
        /**
         * Toggle enhanced panel
         */
        togglePanel: function() {
            const panel = document.getElementById('card-view-enhanced-panel');
            if (!panel) return;
            
            panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
        },
        
        /**
         * Toggle filters panel
         */
        toggleFilters: function() {
            const panel = document.getElementById('card-view-filter-panel');
            if (!panel) return;
            
            const isHidden = panel.style.display === 'none';
            panel.style.display = isHidden ? 'block' : 'none';
            
            if (isHidden) {
                this.buildFilterOptions();
            }
        },
        
        /**
         * Escape HTML
         */
        escapeHtml: function(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
    };
    
    // Auto-initialize enhanced features when card view is toggled
    const originalToggle = CardView.toggle;
    CardView.toggle = function() {
        originalToggle.call(this);
        
        if (this.active && !CardView.enhanced.initialized) {
            CardView.enhanced.init();
            CardView.enhanced.initialized = true;
        }
    };
    
    console.log('GraphCardView Enhanced: Module loaded');
    
})();