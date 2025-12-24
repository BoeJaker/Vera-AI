/**
 * GraphStyleControl Module - UNIFIED & THEME COMPATIBLE
 * Complete styling system for graph visualization
 * 
 * Features:
 * - Full theme.js integration (all CSS variables)
 * - Node & Edge filtering (working implementation)
 * - Category indicators (colored dots/badges)
 * - Node shape and style presets
 * - Label property customization
 * - Color legend system
 * - Animation controls
 * - Unified settings panel
 */

(function() {
    'use strict';
    
    window.GraphStyleControl = {
        
        // Module references
        graphAddon: null,
        
        // Style state
        settings: {
            // Color mode: 'theme', 'category', 'mixed'
            colorMode: 'category',
            
            // Category indicators
            categoryIndicator: {
                enabled: true,
                style: 'border',     // 'border', 'background', 'glow', 'badge', 'none'
                borderWidth: 4,
                size: 'medium'
            },
            
            // Node styling
            node: {
                style: 'default',    // 'minimal', 'default', 'detailed', 'card'
                shape: 'dot',
                size: 25,
                labelProperty: 'display_name',
                showLabels: true
            },
            
            // Edge styling
            edge: {
                width: 2,
                style: 'dynamic',    // 'dynamic', 'straight', 'curved'
                arrows: true,
                labelProperty: 'label',
                showLabels: true,
                colorMode: 'category',
                reverseFollows: false
            },
            
            // Animation settings
            animation: {
                enabled: true,
                nodeEntry: 'fade',
                edgeEntry: 'draw',
                duration: 800,
                stagger: 50
            },
            
            // Filter settings
            filters: {
                nodeCategories: {},  // {category: true/false}
                edgeTypes: {},       // {type: true/false}
                hideIsolatedNodes: false
            },
            
            // Color legend
            legend: {
                enabled: true,
                position: 'bottom-right',
                collapsed: false,
                showNodeColors: true,
                showEdgeColors: true
            }
        },
        
        // Category color mappings
        categoryColors: new Map(),
        edgeTypeColors: new Map(),
        
        // Color palettes
        colorPalettes: {
            vibrant: ['#ef4444', '#f59e0b', '#10b981', '#3b82f6', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16'],
            pastel: ['#fca5a5', '#fcd34d', '#86efac', '#93c5fd', '#c4b5fd', '#f9a8d4', '#67e8f9', '#bef264'],
            dark: ['#991b1b', '#92400e', '#065f46', '#1e40af', '#5b21b6', '#9f1239', '#0e7490', '#4d7c0f'],
            neon: ['#ff0080', '#00ff80', '#0080ff', '#ff8000', '#8000ff', '#00ff00', '#ff0000', '#0000ff'],
            ocean: ['#0ea5e9', '#06b6d4', '#14b8a6', '#10b981', '#22c55e', '#84cc16', '#a3e635', '#bef264'],
            sunset: ['#ef4444', '#f97316', '#f59e0b', '#eab308', '#fbbf24', '#fcd34d', '#fde047', '#fef08a']
        },
        
        currentPalette: 'vibrant',
        
        // Store original colors
        originalNodeColors: new Map(),
        originalEdgeColors: new Map(),
        
        /**
         * Initialize the module
         */
        init: function(graphAddon) {
            console.log('GraphStyleControl: Initializing (Unified & Theme Compatible)...');
            this.graphAddon = graphAddon;
            
            // Load saved settings
            this.loadSettings();
            
            // Build category color mappings
            this.buildCategoryMappings();
            
            // Create UI
            this.createSettingsPanel();
            this.createColorLegend();
            
            // Apply initial styles
            this.applyAllStyles();
            
            console.log('GraphStyleControl: Initialized');
        },
        
        /**
         * Build color mappings for categories
         */
        buildCategoryMappings: function() {
            if (!this.graphAddon || !this.graphAddon.nodesData) return;
            
            // Collect all unique node labels/types
            const nodeCategories = new Set();
            Object.values(this.graphAddon.nodesData).forEach(node => {
                if (node.labels && node.labels.length > 0) {
                    node.labels.forEach(label => nodeCategories.add(label));
                } else {
                    nodeCategories.add('Unlabeled');
                }
            });
            
            // Collect all unique edge types
            const edgeTypes = new Set();
            if (network && network.body && network.body.data) {
                network.body.data.edges.forEach(edge => {
                    const type = edge.label || edge.type || 'Connection';
                    edgeTypes.add(type);
                });
            }
            
            // Assign colors from current palette
            const palette = this.colorPalettes[this.currentPalette];
            
            Array.from(nodeCategories).forEach((category, index) => {
                if (!this.categoryColors.has(category)) {
                    this.categoryColors.set(category, palette[index % palette.length]);
                }
            });
            
            Array.from(edgeTypes).forEach((type, index) => {
                if (!this.edgeTypeColors.has(type)) {
                    this.edgeTypeColors.set(type, palette[index % palette.length]);
                }
            });
            
            // Initialize filter state (all enabled by default)
            nodeCategories.forEach(category => {
                if (!(category in this.settings.filters.nodeCategories)) {
                    this.settings.filters.nodeCategories[category] = true;
                }
            });
            
            edgeTypes.forEach(type => {
                if (!(type in this.settings.filters.edgeTypes)) {
                    this.settings.filters.edgeTypes[type] = true;
                }
            });
            
            console.log(`Mapped ${nodeCategories.size} node categories, ${edgeTypes.size} edge types`);
        },
        
        /**
         * Get color for a node based on current mode
         */
        getNodeColor: function(nodeId) {
            const nodeData = this.graphAddon.nodesData[nodeId];
            if (!nodeData) return '#3b82f6';
            
            switch (this.settings.colorMode) {
                case 'theme':
                    return this.originalNodeColors.get(nodeId) || nodeData.color || '#3b82f6';
                    
                case 'category':
                    if (nodeData.labels && nodeData.labels.length > 0) {
                        return this.categoryColors.get(nodeData.labels[0]) || '#3b82f6';
                    }
                    return this.categoryColors.get('Unlabeled') || '#64748b';
                    
                case 'mixed':
                    if (nodeData.labels && nodeData.labels.length > 0) {
                        return this.categoryColors.get(nodeData.labels[0]) || '#3b82f6';
                    }
                    return this.categoryColors.get('Unlabeled') || '#64748b';
                    
                default:
                    return '#3b82f6';
            }
        },
        
        /**
         * Get edge color based on current mode
         */
        getEdgeColor: function(edge) {
            const { colorMode } = this.settings.edge;
            
            switch (colorMode) {
                case 'source':
                    return this.getNodeColor(edge.from);
                    
                case 'target':
                    return this.getNodeColor(edge.to);
                    
                case 'gradient':
                    return this.getNodeColor(edge.from);
                    
                case 'category':
                    const type = edge.label || edge.type || 'Connection';
                    return this.edgeTypeColors.get(type) || '#94a3b8';
                    
                case 'theme':
                default:
                    return this.originalEdgeColors.get(edge.id) || '#94a3b8';
            }
        },
        
        /**
         * Apply category indicator styling to node
         */
        applyCategoryIndicator: function(nodeId, updateData) {
            if (!this.settings.categoryIndicator.enabled) {
                return updateData;
            }
            
            const color = this.getNodeColor(nodeId);
            const { style, borderWidth } = this.settings.categoryIndicator;
            
            switch (style) {
                case 'border':
                    updateData.borderWidth = borderWidth || 4;
                    updateData.color = updateData.color || {};
                    if (typeof updateData.color === 'string') {
                        updateData.color = { background: updateData.color };
                    }
                    updateData.color.border = color;
                    updateData.color.highlight = updateData.color.highlight || {};
                    updateData.color.highlight.border = this.adjustBrightness(color, 30);
                    updateData.shapeProperties = updateData.shapeProperties || {};
                    updateData.shapeProperties.borderDashes = false;
                    break;
                    
                case 'background':
                    updateData.color = {
                        background: color,
                        border: this.adjustBrightness(color, -20),
                        highlight: {
                            background: this.adjustBrightness(color, -10),
                            border: this.adjustBrightness(color, -30)
                        },
                        hover: {
                            background: this.adjustBrightness(color, -5),
                            border: this.adjustBrightness(color, -25)
                        }
                    };
                    break;
                    
                case 'glow':
                    updateData.shadow = {
                        enabled: true,
                        color: color,
                        size: 15,
                        x: 0,
                        y: 0
                    };
                    updateData.borderWidth = 2;
                    if (typeof updateData.color === 'string') {
                        updateData.color = { background: updateData.color };
                    }
                    updateData.color.border = color;
                    break;
                    
                case 'badge':
                    const nodeData = this.graphAddon.nodesData[nodeId];
                    if (nodeData && nodeData.labels && nodeData.labels[0]) {
                        const badge = `[${nodeData.labels[0].substring(0, 3).toUpperCase()}] `;
                        updateData.label = badge + (updateData.label || '');
                    }
                    updateData.borderWidth = 2;
                    updateData.color = updateData.color || {};
                    if (typeof updateData.color === 'string') {
                        updateData.color = { background: updateData.color };
                    }
                    updateData.color.border = color;
                    break;
                    
                case 'none':
                default:
                    break;
            }
            
            return updateData;
        },
        
        /**
         * Apply node style based on current settings
         */
        applyNodeStyle: function(node) {
            const nodeData = this.graphAddon.nodesData[node.id];
            if (!nodeData) return {};
            
            const updateData = { id: node.id };
            const color = this.getNodeColor(node.id);
            
            // Get base label
            let baseLabel = nodeData.display_name || node.id;
            if (this.settings.node.labelProperty !== 'display_name' && nodeData.properties) {
                baseLabel = nodeData.properties[this.settings.node.labelProperty] || baseLabel;
            }
            
            switch (this.settings.node.style) {
                case 'minimal':
                    updateData.shape = 'dot';
                    updateData.size = this.settings.node.size * 0.7;
                    updateData.label = this.settings.node.showLabels ? baseLabel : '';
                    updateData.font = {
                        color: '#ffffff',
                        size: 10
                    };
                    break;
                    
                case 'default':
                    updateData.shape = this.settings.node.shape;
                    updateData.size = this.settings.node.size;
                    updateData.label = this.settings.node.showLabels ? baseLabel : '';
                    updateData.font = {
                        color: '#ffffff',
                        size: 14
                    };
                    break;
                    
                case 'detailed':
                    updateData.shape = 'box';
                    updateData.size = this.settings.node.size * 1.2;
                    updateData.label = this.createDetailedLabel(node, baseLabel);
                    updateData.font = {
                        color: '#e2e8f0',
                        size: 12,
                        face: 'Inter, -apple-system, system-ui, sans-serif',
                        align: 'left',
                        multi: 'html',
                        bold: { 
                            color: '#ffffff', 
                            size: 14,
                            mod: 'bold'
                        }
                    };
                    updateData.widthConstraint = { minimum: 160, maximum: 220 };
                    updateData.heightConstraint = { minimum: 60 };
                    updateData.margin = 12;
                    updateData.shapeProperties = { 
                        borderRadius: 8,
                        borderDashes: false
                    };
                    break;
                    
                case 'card':
                    updateData.shape = 'box';
                    updateData.label = this.createEnhancedCardLabel(node, baseLabel);
                    updateData.font = {
                        color: '#cbd5e1',
                        size: 11,
                        face: 'Inter, -apple-system, system-ui, sans-serif',
                        align: 'left',
                        multi: 'html',
                        bold: { 
                            color: '#f1f5f9', 
                            size: 13,
                            mod: 'bold'
                        }
                    };
                    updateData.widthConstraint = { minimum: 180, maximum: 260 };
                    updateData.heightConstraint = { minimum: 80 };
                    updateData.margin = 14;
                    updateData.shapeProperties = { 
                        borderRadius: 10,
                        borderDashes: false
                    };
                    break;
            }
            
            // Apply category indicator
            this.applyCategoryIndicator(node.id, updateData);
            
            return updateData;
        },
        
        /**
         * Create detailed label
         */
        createDetailedLabel: function(node, baseLabel) {
            const nodeData = this.graphAddon.nodesData[node.id];
            if (!nodeData) return node.label;
            
            const title = baseLabel || nodeData.display_name || node.id;
            const labels = nodeData.labels || [];
            const props = nodeData.properties || {};
            
            let parts = [];
            parts.push(`<b>${this.escapeHtml(this.truncate(title, 35))}</b>`);
            
            if (labels.length > 0) {
                const badges = labels.slice(0, 2).map(l => `[${l}]`).join(' ');
                parts.push(badges);
            }
            
            const keyProps = ['text', 'body', 'content', 'summary', 'description', 'name'];
            for (const key of keyProps) {
                if (props[key] && String(props[key]).trim()) {
                    let value = String(props[key]).replace(/\n/g, ' ').trim();
                    if (value.length > 40) {
                        value = value.substring(0, 40) + '...';
                    }
                    parts.push(this.escapeHtml(value));
                    break;
                }
            }
            
            try {
                const connCount = network.getConnectedNodes(node.id).length;
                if (connCount > 0) {
                    parts.push(`${connCount} connections`);
                }
            } catch (e) {}
            
            return parts.join('\n');
        },
        
        /**
         * Create enhanced card label
         */
        createEnhancedCardLabel: function(node, baseLabel) {
            const nodeData = this.graphAddon.nodesData[node.id];
            if (!nodeData) return node.label;
            
            const title = baseLabel || nodeData.display_name || node.id;
            const labels = nodeData.labels || [];
            const props = nodeData.properties || {};
            
            let parts = [];
            parts.push(`<b>${this.escapeHtml(this.truncate(title, 28))}</b>`);
            parts.push('');
            
            if (labels.length > 0) {
                const badges = labels.slice(0, 3).map(l => `[${l}]`).join(' ');
                parts.push(badges);
            }
            
            const keyProps = ['text', 'body', 'content', 'summary', 'description'];
            for (const key of keyProps) {
                if (props[key] && String(props[key]).trim()) {
                    let value = String(props[key]).replace(/\n/g, ' ').trim();
                    if (value.length > 70) {
                        value = value.substring(0, 70) + '...';
                    }
                    parts.push('');
                    parts.push(this.escapeHtml(value));
                    break;
                }
            }
            
            const metaParts = [];
            
            try {
                const connCount = network.getConnectedNodes(node.id).length;
                if (connCount > 0) {
                    metaParts.push(`${connCount} links`);
                }
            } catch (e) {}
            
            if (props.created_at) {
                try {
                    const date = new Date(props.created_at);
                    const now = new Date();
                    const diffMs = now - date;
                    const diffMins = Math.floor(diffMs / 60000);
                    const diffHours = Math.floor(diffMs / 3600000);
                    const diffDays = Math.floor(diffMs / 86400000);
                    
                    let timeAgo;
                    if (diffMins < 1) timeAgo = 'just now';
                    else if (diffMins < 60) timeAgo = `${diffMins}m ago`;
                    else if (diffHours < 24) timeAgo = `${diffHours}h ago`;
                    else if (diffDays < 30) timeAgo = `${diffDays}d ago`;
                    else timeAgo = date.toLocaleDateString();
                    
                    metaParts.push(timeAgo);
                } catch (e) {}
            }
            
            if (props.status) {
                metaParts.push(props.status);
            } else if (props.type && !labels.includes(props.type)) {
                metaParts.push(props.type);
            }
            
            if (metaParts.length > 0) {
                parts.push('');
                parts.push('─'.repeat(25));
                parts.push(metaParts.join(' • '));
            }
            
            return parts.join('\n');
        },
        
        /**
         * Truncate text helper
         */
        truncate: function(text, maxLen) {
            if (!text) return '';
            const str = String(text);
            return str.length > maxLen ? str.substring(0, maxLen) + '...' : str;
        },
        
        /**
         * Apply edge style based on current settings
         */
        applyEdgeStyle: function(edge) {
            const updateData = { id: edge.id };
            
            // Width
            updateData.width = this.settings.edge.width;
            
            // Arrows - handle reversal for "follows" edges
            const edgeLabel = (edge.label || '').toLowerCase();
            const shouldReverse = this.settings.edge.reverseFollows && edgeLabel === 'follows';
            
            if (this.settings.edge.arrows) {
                if (shouldReverse) {
                    updateData.arrows = { 
                        from: { enabled: true, scaleFactor: 1.0 },
                        to: { enabled: false }
                    };
                } else {
                    updateData.arrows = { to: { enabled: true, scaleFactor: 1.0 } };
                }
            } else {
                updateData.arrows = { to: { enabled: false }, from: { enabled: false } };
            }
            
            // Label
            if (this.settings.edge.showLabels) {
                if (this.settings.edge.labelProperty === 'label') {
                    updateData.label = edge.label || '';
                } else if (edge[this.settings.edge.labelProperty]) {
                    updateData.label = edge[this.settings.edge.labelProperty];
                }
            } else {
                updateData.label = '';
            }
            
            // Smooth
            switch (this.settings.edge.style) {
                case 'straight':
                    updateData.smooth = { enabled: false };
                    break;
                case 'curved':
                    updateData.smooth = { enabled: true, type: 'curvedCW', roundness: 0.2 };
                    break;
                case 'dynamic':
                default:
                    updateData.smooth = { enabled: true, type: 'dynamic' };
                    break;
            }
            
            // Color based on mode
            const color = this.getEdgeColor(edge);
            updateData.color = {
                color: color,
                highlight: this.adjustBrightness(color, 20),
                hover: this.adjustBrightness(color, 15),
                opacity: 1.0
            };
            
            updateData.font = { color: '#ffffff', size: 12 };
            
            return updateData;
        },
        
        /**
         * Apply node and edge filters - WORKING IMPLEMENTATION
         */
        applyFilters: function() {
            if (!network || !network.body || !network.body.data) return;
            
            console.log('Applying node and edge filters...');
            
            const { nodeCategories, edgeTypes, hideIsolatedNodes } = this.settings.filters;
            
            // Filter nodes by category
            const visibleNodeIds = new Set();
            const nodeUpdates = [];
            
            Object.entries(this.graphAddon.nodesData).forEach(([nodeId, nodeData]) => {
                let isVisible = true;
                
                // Check category filter
                if (nodeData.labels && nodeData.labels.length > 0) {
                    isVisible = nodeData.labels.some(label => nodeCategories[label] !== false);
                } else {
                    isVisible = nodeCategories['Unlabeled'] !== false;
                }
                
                if (isVisible) {
                    visibleNodeIds.add(nodeId);
                }
                
                nodeUpdates.push({
                    id: nodeId,
                    hidden: !isVisible
                });
            });
            
            // Filter edges
            const edgeUpdates = [];
            network.body.data.edges.forEach(edge => {
                const edgeType = edge.label || edge.type || 'Connection';
                const typeVisible = edgeTypes[edgeType] !== false;
                
                // Edge is visible if its type is enabled AND both nodes are visible
                const bothNodesVisible = visibleNodeIds.has(edge.from) && visibleNodeIds.has(edge.to);
                const isVisible = typeVisible && bothNodesVisible;
                
                edgeUpdates.push({
                    id: edge.id,
                    hidden: !isVisible
                });
            });
            
            // Hide isolated nodes if requested
            if (hideIsolatedNodes) {
                const connectedNodes = new Set();
                network.body.data.edges.forEach(edge => {
                    if (!edge.hidden) {
                        connectedNodes.add(edge.from);
                        connectedNodes.add(edge.to);
                    }
                });
                
                nodeUpdates.forEach(update => {
                    if (!update.hidden && !connectedNodes.has(update.id)) {
                        update.hidden = true;
                    }
                });
            }
            
            // Apply updates
            network.body.data.nodes.update(nodeUpdates);
            network.body.data.edges.update(edgeUpdates);
            
            const visibleNodes = nodeUpdates.filter(n => !n.hidden).length;
            const visibleEdges = edgeUpdates.filter(e => !e.hidden).length;
            console.log(`Filters applied: ${visibleNodes} nodes, ${visibleEdges} edges visible`);
        },
        
        /**
         * Toggle node category filter
         */
        toggleNodeCategory: function(category, enabled) {
            this.settings.filters.nodeCategories[category] = enabled;
            this.applyFilters();
            this.saveSettings();
        },
        
        /**
         * Toggle edge type filter
         */
        toggleEdgeType: function(type, enabled) {
            this.settings.filters.edgeTypes[type] = enabled;
            this.applyFilters();
            this.saveSettings();
        },
        
        /**
         * Toggle all node categories
         */
        toggleAllNodeCategories: function(enabled) {
            Object.keys(this.settings.filters.nodeCategories).forEach(category => {
                this.settings.filters.nodeCategories[category] = enabled;
            });
            this.applyFilters();
            this.saveSettings();
        },
        
        /**
         * Toggle all edge types
         */
        toggleAllEdgeTypes: function(enabled) {
            Object.keys(this.settings.filters.edgeTypes).forEach(type => {
                this.settings.filters.edgeTypes[type] = enabled;
            });
            this.applyFilters();
            this.saveSettings();
        },
        
        /**
         * Toggle hide isolated nodes
         */
        toggleHideIsolatedNodes: function(enabled) {
            this.settings.filters.hideIsolatedNodes = enabled;
            this.applyFilters();
            this.saveSettings();
        },
        
        /**
         * Apply all styles to the graph
         */
        applyAllStyles: function() {
            if (!network || !network.body || !network.body.data) {
                console.warn('Network not ready');
                return;
            }
            
            console.log('Applying all styles...');
            
            // Store original colors if not already stored
            if (this.originalNodeColors.size === 0) {
                network.body.data.nodes.forEach(node => {
                    if (node.color && !this.originalNodeColors.has(node.id)) {
                        const colorStr = typeof node.color === 'object' 
                            ? (node.color.background || '#3b82f6')
                            : node.color;
                        this.originalNodeColors.set(node.id, colorStr);
                    }
                });
            }
            
            if (this.originalEdgeColors.size === 0) {
                network.body.data.edges.forEach(edge => {
                    if (edge.color) {
                        const colorStr = typeof edge.color === 'object'
                            ? (edge.color.color || '#94a3b8')
                            : edge.color;
                        this.originalEdgeColors.set(edge.id, colorStr);
                    }
                });
            }
            
            // Apply node styles
            const nodeUpdates = [];
            network.body.data.nodes.forEach(node => {
                nodeUpdates.push(this.applyNodeStyle(node));
            });
            network.body.data.nodes.update(nodeUpdates);
            
            // Apply edge styles
            const edgeUpdates = [];
            network.body.data.edges.forEach(edge => {
                edgeUpdates.push(this.applyEdgeStyle(edge));
            });
            network.body.data.edges.update(edgeUpdates);
            
            // Update legend
            this.updateColorLegend();
            
            // Apply filters
            this.applyFilters();
            
            // Configure physics
            this.configurePhysicsForOverlapPrevention();
            
            console.log('Styles applied');
        },
        
        /**
         * Configure physics to prevent node overlaps
         */
        configurePhysicsForOverlapPrevention: function() {
            if (!network) return;
            
            const style = this.settings.node.style;
            const needsSpacing = (style === 'card' || style === 'detailed');
            
            if (needsSpacing) {
                network.setOptions({
                    physics: {
                        enabled: true,
                        solver: 'barnesHut',
                        barnesHut: {
                            gravitationalConstant: -4000,
                            centralGravity: 0.1,
                            springLength: 300,
                            springConstant: 0.015,
                            damping: 0.95,
                            avoidOverlap: 1
                        },
                        maxVelocity: 25,
                        minVelocity: 0.5,
                        timestep: 0.3,
                        stabilization: {
                            enabled: true,
                            iterations: 200,
                            updateInterval: 10
                        }
                    }
                });
                
                console.log('Applied physics for card/detailed view');
                network.stabilize(150);
            } else {
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
                        maxVelocity: 50,
                        minVelocity: 0.75,
                        timestep: 0.5
                    }
                });
            }
        },
        
        /**
         * Manually trigger node separation
         */
        separateNodes: function() {
            if (!network) {
                console.warn('Network not initialized');
                return;
            }
            
            console.log('Forcing node separation...');
            
            network.setOptions({
                physics: {
                    enabled: true,
                    barnesHut: {
                        gravitationalConstant: -8000,
                        springLength: 400,
                        avoidOverlap: 1
                    }
                }
            });
            
            setTimeout(() => {
                this.configurePhysicsForOverlapPrevention();
                console.log('Node separation complete');
            }, 3000);
        },
        
        /**
         * Create settings panel UI - THEME COMPATIBLE
         */
        createSettingsPanel: function() {
            const settingsPanel = document.getElementById('settings-panel');
            if (!settingsPanel) return;
            
            // Populate label property options first
            this.populateLabelOptions();
            
            const styleControls = `
                <style>
                /* Theme-compatible toggle switches */
                .toggle-switch {
                    position: relative;
                    display: inline-block;
                    width: 44px;
                    height: 24px;
                }
                .toggle-switch input {
                    opacity: 0;
                    width: 0;
                    height: 0;
                }
                .toggle-slider {
                    position: absolute;
                    cursor: pointer;
                    top: 0; left: 0; right: 0; bottom: 0;
                    background-color: var(--border);
                    transition: .3s;
                    border-radius: 24px;
                }
                .toggle-slider:before {
                    position: absolute;
                    content: "";
                    height: 18px;
                    width: 18px;
                    left: 3px;
                    bottom: 3px;
                    background-color: var(--text-inverted);
                    transition: .3s;
                    border-radius: 50%;
                }
                input:checked + .toggle-slider {
                    background-color: var(--accent);
                }
                input:checked + .toggle-slider:before {
                    transform: translateX(20px);
                }
                
                /* Theme-compatible controls */
                .graph-settings-section {
                    border-bottom: 2px solid var(--border);
                    padding-bottom: 16px;
                    margin-bottom: 16px;
                }
                
                .graph-settings-title {
                    font-size: 16px;
                    color: var(--accent);
                    margin-bottom: 12px;
                    font-weight: 600;
                }
                
                .graph-setting-item {
                    margin-bottom: 12px;
                }
                
                .graph-setting-label {
                    display: block;
                    color: var(--text-secondary);
                    font-size: 12px;
                    font-weight: 600;
                    margin-bottom: 6px;
                }
                
                .graph-setting-select,
                .graph-setting-input {
                    width: 100%;
                    padding: 8px;
                    background: var(--bg-surface);
                    color: var(--text);
                    border: 1px solid var(--border);
                    border-radius: 6px;
                    font-size: 13px;
                }
                
                .graph-setting-select:focus,
                .graph-setting-input:focus {
                    outline: none;
                    border-color: var(--accent);
                }
                
                .graph-setting-hint {
                    color: var(--text-secondary);
                    font-size: 10px;
                    margin-top: 4px;
                    opacity: 0.7;
                }
                
                .graph-control-box {
                    background: var(--bg);
                    padding: 12px;
                    border-radius: 8px;
                    border: 1px solid var(--border-subtle);
                    margin-bottom: 12px;
                }
                
                .graph-control-header {
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    margin-bottom: 8px;
                }
                
                .graph-control-title {
                    color: var(--text-secondary);
                    font-size: 12px;
                    font-weight: 600;
                }
                
                .graph-btn {
                    padding: 10px;
                    background: var(--accent);
                    color: var(--text-inverted);
                    border: none;
                    border-radius: 6px;
                    cursor: pointer;
                    font-weight: 600;
                    font-size: 13px;
                    transition: all 0.2s;
                }
                
                .graph-btn:hover {
                    background: var(--hover);
                    transform: translateY(-1px);
                }
                
                .graph-btn-secondary {
                    background: var(--bg-surface);
                    color: var(--text);
                    border: 1px solid var(--border);
                }
                
                .graph-btn-secondary:hover {
                    background: var(--hover);
                }
                
                .graph-checkbox-label {
                    display: flex;
                    align-items: center;
                    margin-bottom: 6px;
                    font-size: 12px;
                    color: var(--text);
                }
                
                .graph-checkbox-label input[type="checkbox"] {
                    margin-right: 8px;
                    accent-color: var(--accent);
                }
                </style>
                
                <div class="graph-settings-section">
                    <div class="graph-settings-title">🎨 Graph Style Control</div>
                    
                    <!-- Color Mode -->
                    <div class="graph-setting-item">
                        <label class="graph-setting-label">Color Mode</label>
                        <select id="style-color-mode" class="graph-setting-select" onchange="window.GraphStyleControl.setColorMode(this.value)">
                            <option value="category">Category Colors</option>
                            <option value="theme">Theme Colors</option>
                            <option value="mixed">Mixed Mode</option>
                        </select>
                        <div class="graph-setting-hint">How nodes/edges are colored</div>
                    </div>
                    
                    <!-- Color Palette -->
                    <div class="graph-setting-item">
                        <label class="graph-setting-label">Color Palette</label>
                        <select id="style-color-palette" class="graph-setting-select" onchange="window.GraphStyleControl.setPalette(this.value)">
                            <option value="vibrant">Vibrant</option>
                            <option value="pastel">Pastel</option>
                            <option value="dark">Dark</option>
                            <option value="neon">Neon</option>
                            <option value="ocean">Ocean</option>
                            <option value="sunset">Sunset</option>
                        </select>
                    </div>
                    
                    <!-- Category Indicators -->
                    <div class="graph-control-box">
                        <div class="graph-control-header">
                            <label class="graph-control-title">Category Indicators</label>
                            <label class="toggle-switch">
                                <input type="checkbox" id="style-indicator-enabled" checked 
                                       onchange="window.GraphStyleControl.toggleIndicators(this.checked)">
                                <span class="toggle-slider"></span>
                            </label>
                        </div>
                        
                        <div id="indicator-controls">
                            <select id="style-indicator-style" class="graph-setting-select" onchange="window.GraphStyleControl.setIndicatorStyle(this.value)" style="margin-bottom: 6px;">
                                <option value="border" selected>Colored Border</option>
                                <option value="background">Colored Background</option>
                                <option value="glow">Glow Effect</option>
                                <option value="badge">Badge Prefix</option>
                                <option value="none">None</option>
                            </select>
                            
                            <div id="border-width-control" style="margin-top: 6px;">
                                <label class="graph-setting-label" style="font-size: 10px;">Border Width</label>
                                <input type="range" id="style-border-width" min="1" max="8" value="4" 
                                       oninput="document.getElementById('border-width-val').textContent = this.value; window.GraphStyleControl.setBorderWidth(parseInt(this.value));"
                                       style="width: 100%;">
                                <div style="text-align: center; color: var(--text-secondary); font-size: 10px;">
                                    <span id="border-width-val">4</span>px
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Node Styling -->
                    <div class="graph-control-box">
                        <div class="graph-control-title" style="margin-bottom: 8px;">Node Styling</div>
                        
                        <label class="graph-setting-label">Style Preset</label>
                        <select id="style-node-preset" class="graph-setting-select" onchange="window.GraphStyleControl.setNodePreset(this.value)" style="margin-bottom: 8px;">
                            <option value="minimal">Minimal</option>
                            <option value="default" selected>Default</option>
                            <option value="detailed">Detailed</option>
                            <option value="card">Card View</option>
                        </select>
                        
                        <div id="node-shape-control">
                            <label class="graph-setting-label">Shape</label>
                            <select id="style-node-shape" class="graph-setting-select" onchange="window.GraphStyleControl.setNodeShape(this.value)" style="margin-bottom: 8px;">
                                <option value="dot">Dot</option>
                                <option value="circle">Circle</option>
                                <option value="diamond">Diamond</option>
                                <option value="square">Square</option>
                                <option value="triangle">Triangle</option>
                                <option value="star">Star</option>
                                <option value="hexagon">Hexagon</option>
                            </select>
                        </div>
                        
                        <label class="graph-setting-label">Size</label>
                        <input type="range" id="style-node-size" min="10" max="50" value="25" 
                               oninput="document.getElementById('node-size-val').textContent = this.value; window.GraphStyleControl.setNodeSize(parseInt(this.value));"
                               style="width: 100%;">
                        <div style="text-align: center; color: var(--text-secondary); font-size: 10px; margin-bottom: 8px;">
                            <span id="node-size-val">25</span>px
                        </div>
                        
                        <label class="graph-setting-label">Label Property</label>
                        <select id="node-label-property" class="graph-setting-select" onchange="window.GraphStyleControl.updateNodeLabels()">
                            <option value="display_name">Display Name</option>
                            <option value="id">ID</option>
                            <option value="label">Label</option>
                        </select>
                        
                        <label class="graph-checkbox-label" style="margin-top: 8px;">
                            <input type="checkbox" id="style-node-labels" checked
                                   onchange="window.GraphStyleControl.toggleNodeLabels(this.checked)">
                            Show Labels
                        </label>
                    </div>
                    
                    <!-- Edge Styling -->
                    <div class="graph-control-box">
                        <div class="graph-control-title" style="margin-bottom: 8px;">Edge Styling</div>
                        
                        <label class="graph-setting-label">Color Mode</label>
                        <select id="style-edge-color-mode" class="graph-setting-select" onchange="window.GraphStyleControl.setEdgeColorMode(this.value)" style="margin-bottom: 8px;">
                            <option value="category">By Category/Type</option>
                            <option value="source">Match Source Node</option>
                            <option value="target">Match Target Node</option>
                            <option value="gradient">Gradient (Source→Target)</option>
                            <option value="theme">Theme Colors</option>
                        </select>
                        
                        <label class="graph-setting-label">Width</label>
                        <input type="range" id="style-edge-width" min="1" max="8" value="2" 
                               oninput="document.getElementById('edge-width-val').textContent = this.value; window.GraphStyleControl.setEdgeWidth(parseInt(this.value));"
                               style="width: 100%;">
                        <div style="text-align: center; color: var(--text-secondary); font-size: 10px; margin-bottom: 8px;">
                            <span id="edge-width-val">2</span>px
                        </div>
                        
                        <label class="graph-setting-label">Style</label>
                        <select id="style-edge-style" class="graph-setting-select" onchange="window.GraphStyleControl.setEdgeStyle(this.value)" style="margin-bottom: 8px;">
                            <option value="dynamic" selected>Dynamic</option>
                            <option value="straight">Straight</option>
                            <option value="curved">Curved</option>
                        </select>
                        
                        <label class="graph-setting-label">Label Property</label>
                        <select id="edge-label-property" class="graph-setting-select" onchange="window.GraphStyleControl.updateEdgeLabels()" style="margin-bottom: 8px;">
                            <option value="label">Label</option>
                            <option value="type">Type</option>
                            <option value="title">Title</option>
                        </select>
                        
                        <label class="graph-checkbox-label">
                            <input type="checkbox" id="style-edge-arrows" checked
                                   onchange="window.GraphStyleControl.toggleEdgeArrows(this.checked)">
                            Show Arrows
                        </label>
                        
                        <label class="graph-checkbox-label">
                            <input type="checkbox" id="style-edge-labels" checked
                                   onchange="window.GraphStyleControl.toggleEdgeLabels(this.checked)">
                            Show Labels
                        </label>
                        
                        <label class="graph-checkbox-label">
                            <input type="checkbox" id="style-reverse-follows"
                                   onchange="window.GraphStyleControl.toggleReverseFollows(this.checked)">
                            Reverse "follows" arrows
                        </label>
                    </div>
                    
                    <!-- Animation Settings -->
                    <div class="graph-control-box">
                        <div class="graph-control-header">
                            <label class="graph-control-title">Animations</label>
                            <label class="toggle-switch">
                                <input type="checkbox" id="style-animation-enabled" checked
                                       onchange="window.GraphStyleControl.toggleAnimations(this.checked)">
                                <span class="toggle-slider"></span>
                            </label>
                        </div>
                        
                        <div id="animation-controls">
                            <label class="graph-setting-label" style="font-size: 10px;">Node Entry</label>
                            <select id="style-animation-node-entry" class="graph-setting-select" onchange="window.GraphStyleControl.setAnimationNodeEntry(this.value)" style="font-size: 11px; margin-bottom: 6px;">
                                <option value="fade" selected>Fade In</option>
                                <option value="scale">Scale Up</option>
                                <option value="slide">Slide In</option>
                                <option value="none">None</option>
                            </select>
                            
                            <label class="graph-setting-label" style="font-size: 10px;">Edge Entry</label>
                            <select id="style-animation-edge-entry" class="graph-setting-select" onchange="window.GraphStyleControl.setAnimationEdgeEntry(this.value)" style="font-size: 11px;">
                                <option value="draw" selected>Draw</option>
                                <option value="fade">Fade In</option>
                                <option value="none">None</option>
                            </select>
                        </div>
                    </div>
                    
                    <!-- Filtering -->
                    <div class="graph-control-box">
                        <div class="graph-control-title" style="margin-bottom: 8px;">Filters</div>
                        
                        <button onclick="window.GraphStyleControl.showFilterPanel()" class="graph-btn graph-btn-secondary" style="width: 100%; margin-bottom: 8px;">
                            🔍 Configure Filters
                        </button>
                        
                        <label class="graph-checkbox-label">
                            <input type="checkbox" id="style-hide-isolated" 
                                   onchange="window.GraphStyleControl.toggleHideIsolatedNodes(this.checked)">
                            Hide Isolated Nodes
                        </label>
                    </div>
                    
                    <!-- Color Legend -->
                    <div class="graph-control-box">
                        <div class="graph-control-header">
                            <label class="graph-control-title">Show Color Legend</label>
                            <label class="toggle-switch">
                                <input type="checkbox" id="style-legend-enabled" checked
                                       onchange="window.GraphStyleControl.toggleLegend(this.checked)">
                                <span class="toggle-slider"></span>
                            </label>
                        </div>
                    </div>
                    
                    <!-- Apply/Reset Buttons -->
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 12px;">
                        <button onclick="window.GraphStyleControl.applyAllStyles()" class="graph-btn">Apply</button>
                        <button onclick="window.GraphStyleControl.resetToDefaults()" class="graph-btn graph-btn-secondary">Reset</button>
                    </div>
                </div>
            `;
            
            // Insert at the beginning of settings panel
            settingsPanel.insertAdjacentHTML('afterbegin', styleControls);
            
            // Sync UI with current settings
            this.syncUIWithSettings();
        },
        
        /**
         * Populate label property options dynamically
         */
        populateLabelOptions: function() {
            if (!this.graphAddon || !this.graphAddon.nodesData) return;
            
            const nodeProps = new Set(['display_name', 'id', 'label']);
            const edgeProps = new Set(['label', 'type', 'title', 'id']);
            
            // Collect node properties
            Object.values(this.graphAddon.nodesData).forEach(node => {
                if (node.properties) {
                    Object.keys(node.properties).forEach(key => nodeProps.add(key));
                }
            });
            
            // Collect edge properties
            if (network && network.body && network.body.data) {
                network.body.data.edges.forEach(edge => {
                    Object.keys(edge).forEach(key => {
                        if (key !== 'from' && key !== 'to' && key !== 'arrows') {
                            edgeProps.add(key);
                        }
                    });
                });
            }
            
            // Populate node label select
            const nodeSelect = document.getElementById('node-label-property');
            if (nodeSelect) {
                const currentValue = nodeSelect.value || 'display_name';
                nodeSelect.innerHTML = '';
                nodeProps.forEach(prop => {
                    const option = document.createElement('option');
                    option.value = prop;
                    option.textContent = prop.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                    nodeSelect.appendChild(option);
                });
                nodeSelect.value = currentValue;
            }
            
            // Populate edge label select
            const edgeSelect = document.getElementById('edge-label-property');
            if (edgeSelect) {
                const currentValue = edgeSelect.value || 'label';
                edgeSelect.innerHTML = '';
                edgeProps.forEach(prop => {
                    const option = document.createElement('option');
                    option.value = prop;
                    option.textContent = prop.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                    edgeSelect.appendChild(option);
                });
                edgeSelect.value = currentValue;
            }
        },
        
        /**
         * Update node labels based on selected property
         */
        updateNodeLabels: function() {
            if (!network || !network.body || !network.body.data) return;
            
            const property = document.getElementById('node-label-property')?.value || 'display_name';
            this.settings.node.labelProperty = property;
            
            console.log('Updating node labels to property:', property);
            
            const nodeUpdates = [];
            network.body.data.nodes.forEach(node => {
                const nodeData = this.graphAddon.nodesData[node.id];
                let newLabel = node.id;
                
                if (nodeData) {
                    if (property === 'display_name') {
                        newLabel = nodeData.display_name || node.id;
                    } else if (property === 'id') {
                        newLabel = node.id;
                    } else if (property === 'label' && nodeData.labels && nodeData.labels.length > 0) {
                        newLabel = nodeData.labels.join('\n');
                    } else if (nodeData.properties && nodeData.properties[property]) {
                        newLabel = String(nodeData.properties[property]);
                        if (newLabel.length > 50) {
                            newLabel = newLabel.substring(0, 50) + '...';
                        }
                    }
                }
                
                nodeUpdates.push({
                    id: node.id,
                    label: this.settings.node.showLabels ? newLabel : ''
                });
            });
            
            network.body.data.nodes.update(nodeUpdates);
            this.saveSettings();
        },
        
        /**
         * Update edge labels based on selected property
         */
        updateEdgeLabels: function() {
            if (!network || !network.body || !network.body.data) return;
            
            const property = document.getElementById('edge-label-property')?.value || 'label';
            this.settings.edge.labelProperty = property;
            
            console.log('Updating edge labels to property:', property);
            
            const edgeUpdates = [];
            network.body.data.edges.forEach(edge => {
                let newLabel = '';
                
                if (edge[property]) {
                    newLabel = String(edge[property]);
                    if (newLabel.length > 30) {
                        newLabel = newLabel.substring(0, 30) + '...';
                    }
                }
                
                edgeUpdates.push({
                    id: edge.id,
                    label: this.settings.edge.showLabels ? newLabel : ''
                });
            });
            
            network.body.data.edges.update(edgeUpdates);
            this.saveSettings();
        },
        
        /**
         * Sync UI controls with current settings
         */
        syncUIWithSettings: function() {
            const updates = {
                'style-color-mode': this.settings.colorMode,
                'style-color-palette': this.currentPalette,
                'style-indicator-style': this.settings.categoryIndicator.style,
                'style-node-preset': this.settings.node.style,
                'style-node-shape': this.settings.node.shape,
                'style-edge-color-mode': this.settings.edge.colorMode,
                'style-edge-style': this.settings.edge.style,
                'style-animation-node-entry': this.settings.animation.nodeEntry,
                'style-animation-edge-entry': this.settings.animation.edgeEntry
            };
            
            Object.entries(updates).forEach(([id, value]) => {
                const el = document.getElementById(id);
                if (el) el.value = value;
            });
            
            const checkboxes = {
                'style-indicator-enabled': this.settings.categoryIndicator.enabled,
                'style-edge-arrows': this.settings.edge.arrows,
                'style-edge-labels': this.settings.edge.showLabels,
                'style-node-labels': this.settings.node.showLabels,
                'style-legend-enabled': this.settings.legend.enabled,
                'style-animation-enabled': this.settings.animation.enabled
            };
            
            Object.entries(checkboxes).forEach(([id, checked]) => {
                const el = document.getElementById(id);
                if (el) el.checked = checked;
            });
            
            // Update range displays
            document.getElementById('border-width-val').textContent = this.settings.categoryIndicator.borderWidth;
            document.getElementById('node-size-val').textContent = this.settings.node.size;
            document.getElementById('edge-width-val').textContent = this.settings.edge.width;
        },
        
        /**
         * Create color legend element
         */
        createColorLegend: function() {
            const existing = document.getElementById('graph-color-legend');
            if (existing) existing.remove();
            
            const legend = document.createElement('div');
            legend.id = 'graph-color-legend';
            legend.style.cssText = `
                position: absolute;
                bottom: 80px;
                right: 20px;
                min-width: 200px;
                max-width: 300px;
                max-height: 400px;
                overflow-y: auto;
                background: var(--panel-bg);
                backdrop-filter: blur(10px);
                border: 1px solid var(--border);
                border-radius: 12px;
                padding: 16px;
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
                z-index: 9998;
                display: ${this.settings.legend.enabled ? 'block' : 'none'};
            `;
            
            const graphContainer = document.getElementById('tab-graph');
            if (graphContainer) {
                graphContainer.style.position = 'relative';
                graphContainer.appendChild(legend);
            } else {
                document.body.appendChild(legend);
            }
            
            this.updateColorLegend();
        },
        
        /**
         * Update color legend content
         */
        updateColorLegend: function() {
            const legend = document.getElementById('graph-color-legend');
            if (!legend) return;
            
            let html = `
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
                    <div style="color: var(--text); font-size: 14px; font-weight: 600;">Color Key</div>
                    <button onclick="window.GraphStyleControl.toggleLegendCollapsed()" style="
                        background: none; border: none; color: var(--text-secondary);
                        cursor: pointer; font-size: 16px; padding: 0;
                    ">${this.settings.legend.collapsed ? '▼' : '▲'}</button>
                </div>
            `;
            
            if (!this.settings.legend.collapsed) {
                // Node categories
                if (this.settings.legend.showNodeColors && this.categoryColors.size > 0) {
                    html += '<div style="margin-bottom: 12px;">';
                    html += '<div style="color: var(--text-secondary); font-size: 11px; font-weight: 600; margin-bottom: 6px;">NODE CATEGORIES</div>';
                    
                    Array.from(this.categoryColors.entries()).forEach(([category, color]) => {
                        html += `
                            <div style="display: flex; align-items: center; padding: 4px; cursor: pointer; border-radius: 4px; margin-bottom: 2px;"
                                 onmouseover="this.style.background='var(--hover)'"
                                 onmouseout="this.style.background='transparent'"
                                 onclick="window.GraphStyleControl.highlightCategory('${this.escapeHtml(category)}')">
                                <div style="width: 12px; height: 12px; background: ${color}; border-radius: 50%; margin-right: 8px; flex-shrink: 0;"></div>
                                <div style="color: var(--text); font-size: 12px; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                                    ${this.escapeHtml(category)}
                                </div>
                            </div>
                        `;
                    });
                    
                    html += '</div>';
                }
                
                // Edge types
                if (this.settings.legend.showEdgeColors && this.edgeTypeColors.size > 0) {
                    html += '<div>';
                    html += '<div style="color: var(--text-secondary); font-size: 11px; font-weight: 600; margin-bottom: 6px;">EDGE TYPES</div>';
                    
                    Array.from(this.edgeTypeColors.entries()).forEach(([type, color]) => {
                        html += `
                            <div style="display: flex; align-items: center; padding: 4px; cursor: pointer; border-radius: 4px; margin-bottom: 2px;"
                                 onmouseover="this.style.background='var(--hover)'"
                                 onmouseout="this.style.background='transparent'">
                                <div style="width: 12px; height: 2px; background: ${color}; margin-right: 8px; flex-shrink: 0;"></div>
                                <div style="color: var(--text); font-size: 12px; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                                    ${this.escapeHtml(type)}
                                </div>
                            </div>
                        `;
                    });
                    
                    html += '</div>';
                }
            }
            
            legend.innerHTML = html;
        },
        
        /**
         * Highlight nodes of a specific category
         */
        highlightCategory: function(category) {
            if (!network) return;
            
            const matchingNodes = [];
            Object.entries(this.graphAddon.nodesData).forEach(([nodeId, nodeData]) => {
                if (nodeData.labels && nodeData.labels.includes(category)) {
                    matchingNodes.push(nodeId);
                } else if (category === 'Unlabeled' && (!nodeData.labels || nodeData.labels.length === 0)) {
                    matchingNodes.push(nodeId);
                }
            });
            
            if (matchingNodes.length > 0) {
                network.selectNodes(matchingNodes);
                network.fit({
                    nodes: matchingNodes,
                    animation: { duration: 1000, easingFunction: 'easeInOutQuad' }
                });
            }
        },
        
        /**
         * Show filter configuration panel - THEME COMPATIBLE
         */
        showFilterPanel: function() {
            const panel = document.getElementById('property-panel');
            const content = document.getElementById('panel-content');
            
            if (!panel || !content) return;
            
            let html = `
                <div style="padding: 20px;">
                    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;">
                        <div style="color: var(--text); font-size: 16px; font-weight: 600;">🔍 Filters</div>
                        <button onclick="window.GraphAddon.closePanel()" style="
                            background: none; border: none; color: var(--text-secondary);
                            cursor: pointer; font-size: 20px; padding: 0;
                        ">✕</button>
                    </div>
                    
                    <!-- Node Category Filters -->
                    <div style="margin-bottom: 20px;">
                        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
                            <div style="color: var(--text-secondary); font-size: 13px; font-weight: 600;">Node Categories</div>
                            <div style="display: flex; gap: 8px;">
                                <button onclick="window.GraphStyleControl.toggleAllNodeCategories(true)" style="
                                    padding: 4px 8px; background: var(--accent); color: var(--text-inverted);
                                    border: none; border-radius: 4px; cursor: pointer; font-size: 11px;
                                ">All</button>
                                <button onclick="window.GraphStyleControl.toggleAllNodeCategories(false)" style="
                                    padding: 4px 8px; background: var(--error, #ef4444); color: var(--text-inverted);
                                    border: none; border-radius: 4px; cursor: pointer; font-size: 11px;
                                ">None</button>
                            </div>
                        </div>
                        <div id="node-category-filters" style="
                            max-height: 200px; overflow-y: auto;
                            background: var(--bg); padding: 8px; border-radius: 6px; border: 1px solid var(--border-subtle);
                        "></div>
                    </div>
                    
                    <!-- Edge Type Filters -->
                    <div style="margin-bottom: 20px;">
                        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
                            <div style="color: var(--text-secondary); font-size: 13px; font-weight: 600;">Edge Types</div>
                            <div style="display: flex; gap: 8px;">
                                <button onclick="window.GraphStyleControl.toggleAllEdgeTypes(true)" style="
                                    padding: 4px 8px; background: var(--accent); color: var(--text-inverted);
                                    border: none; border-radius: 4px; cursor: pointer; font-size: 11px;
                                ">All</button>
                                <button onclick="window.GraphStyleControl.toggleAllEdgeTypes(false)" style="
                                    padding: 4px 8px; background: var(--error, #ef4444); color: var(--text-inverted);
                                    border: none; border-radius: 4px; cursor: pointer; font-size: 11px;
                                ">None</button>
                            </div>
                        </div>
                        <div id="edge-type-filters" style="
                            max-height: 200px; overflow-y: auto;
                            background: var(--bg); padding: 8px; border-radius: 6px; border: 1px solid var(--border-subtle);
                        "></div>
                    </div>
                    
                    <button onclick="window.GraphStyleControl.applyFilters(); window.GraphAddon.closePanel();" style="
                        width: 100%; padding: 12px; background: var(--accent); color: var(--text-inverted);
                        border: none; border-radius: 6px; cursor: pointer; font-weight: 600;
                    ">Apply Filters</button>
                </div>
            `;
            
            content.innerHTML = html;
            
            // Populate node category filters
            const nodeCategoryContainer = document.getElementById('node-category-filters');
            Object.keys(this.settings.filters.nodeCategories).forEach(category => {
                const enabled = this.settings.filters.nodeCategories[category];
                const color = this.categoryColors.get(category) || '#3b82f6';
                
                const item = document.createElement('label');
                item.style.cssText = `
                    display: flex; align-items: center; padding: 6px; cursor: pointer;
                    border-radius: 4px; margin-bottom: 4px;
                `;
                item.onmouseover = function() { this.style.background = 'var(--hover)'; };
                item.onmouseout = function() { this.style.background = 'transparent'; };
                
                item.innerHTML = `
                    <input type="checkbox" ${enabled ? 'checked' : ''} 
                           onchange="window.GraphStyleControl.toggleNodeCategory('${this.escapeHtml(category)}', this.checked)"
                           style="margin-right: 8px; accent-color: var(--accent);">
                    <div style="width: 12px; height: 12px; background: ${color}; border-radius: 50%; margin-right: 8px;"></div>
                    <span style="color: var(--text); font-size: 12px;">${this.escapeHtml(category)}</span>
                `;
                
                nodeCategoryContainer.appendChild(item);
            });
            
            // Populate edge type filters
            const edgeTypeContainer = document.getElementById('edge-type-filters');
            Object.keys(this.settings.filters.edgeTypes).forEach(type => {
                const enabled = this.settings.filters.edgeTypes[type];
                const color = this.edgeTypeColors.get(type) || '#94a3b8';
                
                const item = document.createElement('label');
                item.style.cssText = `
                    display: flex; align-items: center; padding: 6px; cursor: pointer;
                    border-radius: 4px; margin-bottom: 4px;
                `;
                item.onmouseover = function() { this.style.background = 'var(--hover)'; };
                item.onmouseout = function() { this.style.background = 'transparent'; };
                
                item.innerHTML = `
                    <input type="checkbox" ${enabled ? 'checked' : ''} 
                           onchange="window.GraphStyleControl.toggleEdgeType('${this.escapeHtml(type)}', this.checked)"
                           style="margin-right: 8px; accent-color: var(--accent);">
                    <div style="width: 16px; height: 2px; background: ${color}; margin-right: 8px;"></div>
                    <span style="color: var(--text); font-size: 12px;">${this.escapeHtml(type)}</span>
                `;
                
                edgeTypeContainer.appendChild(item);
            });
            
            panel.style.display = 'flex';
        },
        
        // ============================================================
        // SETTING CHANGE HANDLERS
        // ============================================================
        
        setColorMode: function(mode) {
            this.settings.colorMode = mode;
            this.saveSettings();
            this.applyAllStyles();
        },
        
        setPalette: function(palette) {
            this.currentPalette = palette;
            this.categoryColors.clear();
            this.edgeTypeColors.clear();
            this.buildCategoryMappings();
            this.saveSettings();
            this.applyAllStyles();
        },
        
        toggleIndicators: function(enabled) {
            this.settings.categoryIndicator.enabled = enabled;
            const controls = document.getElementById('indicator-controls');
            if (controls) {
                controls.style.opacity = enabled ? '1' : '0.5';
                controls.style.pointerEvents = enabled ? 'auto' : 'none';
            }
            this.saveSettings();
            this.applyAllStyles();
        },
        
        setIndicatorStyle: function(style) {
            this.settings.categoryIndicator.style = style;
            const borderControl = document.getElementById('border-width-control');
            if (borderControl) {
                borderControl.style.display = style === 'border' ? 'block' : 'none';
            }
            this.saveSettings();
            this.applyAllStyles();
        },
        
        setBorderWidth: function(width) {
            this.settings.categoryIndicator.borderWidth = width;
            this.saveSettings();
            this.applyAllStyles();
        },
        
        setNodePreset: function(preset) {
            this.settings.node.style = preset;
            const shapeControl = document.getElementById('node-shape-control');
            if (shapeControl) {
                shapeControl.style.display = (preset === 'card' || preset === 'detailed') ? 'none' : 'block';
            }
            this.saveSettings();
            this.applyAllStyles();
            this.configurePhysicsForOverlapPrevention();
        },
        
        setNodeShape: function(shape) {
            this.settings.node.shape = shape;
            this.saveSettings();
            this.applyAllStyles();
        },
        
        setNodeSize: function(size) {
            this.settings.node.size = size;
            this.saveSettings();
            this.applyAllStyles();
        },
        
        toggleNodeLabels: function(enabled) {
            this.settings.node.showLabels = enabled;
            this.saveSettings();
            this.updateNodeLabels();
        },
        
        setEdgeColorMode: function(mode) {
            this.settings.edge.colorMode = mode;
            this.saveSettings();
            this.applyAllStyles();
            this.updateColorLegend();
        },
        
        setEdgeWidth: function(width) {
            this.settings.edge.width = width;
            this.saveSettings();
            this.applyAllStyles();
        },
        
        setEdgeStyle: function(style) {
            this.settings.edge.style = style;
            this.saveSettings();
            this.applyAllStyles();
        },
        
        toggleEdgeArrows: function(enabled) {
            this.settings.edge.arrows = enabled;
            this.saveSettings();
            this.applyAllStyles();
        },
        
        toggleEdgeLabels: function(enabled) {
            this.settings.edge.showLabels = enabled;
            this.saveSettings();
            this.updateEdgeLabels();
        },
        
        toggleReverseFollows: function(enabled) {
            this.settings.edge.reverseFollows = enabled;
            this.saveSettings();
            this.applyAllStyles();
        },
        
        toggleAnimations: function(enabled) {
            this.settings.animation.enabled = enabled;
            const controls = document.getElementById('animation-controls');
            if (controls) {
                controls.style.opacity = enabled ? '1' : '0.5';
                controls.style.pointerEvents = enabled ? 'auto' : 'none';
            }
            this.saveSettings();
        },
        
        setAnimationNodeEntry: function(style) {
            this.settings.animation.nodeEntry = style;
            this.saveSettings();
        },
        
        setAnimationEdgeEntry: function(style) {
            this.settings.animation.edgeEntry = style;
            this.saveSettings();
        },
        
        toggleLegend: function(enabled) {
            this.settings.legend.enabled = enabled;
            const legend = document.getElementById('graph-color-legend');
            if (legend) {
                legend.style.display = enabled ? 'block' : 'none';
            }
            this.saveSettings();
        },
        
        toggleLegendCollapsed: function() {
            this.settings.legend.collapsed = !this.settings.legend.collapsed;
            this.updateColorLegend();
            this.saveSettings();
        },
        
        /**
         * Reset to default settings
         */
        resetToDefaults: function() {
            this.settings = {
                colorMode: 'category',
                categoryIndicator: {
                    enabled: true,
                    style: 'border',
                    borderWidth: 4,
                    size: 'medium'
                },
                node: {
                    style: 'default',
                    shape: 'dot',
                    size: 25,
                    labelProperty: 'display_name',
                    showLabels: true
                },
                edge: {
                    width: 2,
                    style: 'dynamic',
                    arrows: true,
                    labelProperty: 'label',
                    showLabels: true,
                    colorMode: 'category',
                    reverseFollows: false
                },
                animation: {
                    enabled: true,
                    nodeEntry: 'fade',
                    edgeEntry: 'draw',
                    duration: 800,
                    stagger: 50
                },
                filters: {
                    nodeCategories: {},
                    edgeTypes: {},
                    hideIsolatedNodes: false
                },
                legend: {
                    enabled: true,
                    position: 'bottom-right',
                    collapsed: false,
                    showNodeColors: true,
                    showEdgeColors: true
                }
            };
            
            this.currentPalette = 'vibrant';
            this.categoryColors.clear();
            this.edgeTypeColors.clear();
            this.buildCategoryMappings();
            this.syncUIWithSettings();
            this.saveSettings();
            this.applyAllStyles();
        },
        
        /**
         * Save settings to localStorage
         */
        saveSettings: function() {
            try {
                localStorage.setItem('graphStyleSettings', JSON.stringify({
                    settings: this.settings,
                    palette: this.currentPalette
                }));
            } catch (e) {
                console.warn('Could not save settings:', e);
            }
        },
        
        /**
         * Load settings from localStorage
         */
        loadSettings: function() {
            try {
                const saved = localStorage.getItem('graphStyleSettings');
                if (saved) {
                    const data = JSON.parse(saved);
                    this.settings = data.settings || this.settings;
                    this.currentPalette = data.palette || this.currentPalette;
                }
            } catch (e) {
                console.warn('Could not load settings:', e);
            }
        },
        
        /**
         * Adjust color brightness
         */
        adjustBrightness: function(color, percent) {
            if (!color || !color.startsWith('#')) return color;
            
            const num = parseInt(color.replace('#', ''), 16);
            const amt = Math.round(2.55 * percent);
            const R = (num >> 16) + amt;
            const G = (num >> 8 & 0x00FF) + amt;
            const B = (num & 0x0000FF) + amt;
            
            return '#' + (0x1000000 + 
                (R < 255 ? (R < 1 ? 0 : R) : 255) * 0x10000 +
                (G < 255 ? (G < 1 ? 0 : G) : 255) * 0x100 +
                (B < 255 ? (B < 1 ? 0 : B) : 255))
                .toString(16).slice(1);
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
    
})();