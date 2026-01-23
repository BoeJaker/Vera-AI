/**
 * GraphCardView - Pure HTML/CSS/JS Hierarchical Card Visualization
 * NO external graph libraries - 100% HTML, CSS, and JavaScript
 * 
 * Features:
 * - Pure HTML/CSS edge rendering (no SVG)
 * - Working pan/zoom with mouse drag
 * - Hierarchical tree layout
 * - Interactive cards with full node details
 * - Expand/collapse nodes
 * - Theme compatible
 */

(function() {
    'use strict';
    
    window.GraphCardView = {
        // State
        active: false,
        container: null,
        canvas: null,
        cardsContainer: null,
        edgesContainer: null,
        
        // Data
        nodes: new Map(),
        edges: [],
        hierarchy: null,
        expandedNodes: new Set(),
        focusedNode: null,
        
        // Layout
        layout: {
            cardWidth: 280,
            cardHeight: 180,
            horizontalGap: 120,  // Space between cards horizontally
            verticalGap: 150,    // Increased for better routing zones
            rootX: 400,
            rootY: 80
        },
        
        // Viewport for pan/zoom
        viewport: {
            scale: 1,
            translateX: 0,
            translateY: 0,
            isDragging: false,
            dragStartX: 0,
            dragStartY: 0,
            startTranslateX: 0,
            startTranslateY: 0
        },
        
        /**
         * Initialize the card view
         */
        init: function() {
            console.log('GraphCardView: Initializing (Pure HTML/CSS)...');
            
            this.createContainer();
            // this.addToggleButton();
            this.setupEventListeners();
            
            console.log('GraphCardView: Initialized');
        },
        
        /**
         * Create the main container with canvas for panning
         */
        createContainer: function() {
            const graphContainer = document.getElementById('graph');
            if (!graphContainer) {
                console.error('GraphCardView: Graph container not found');
                return;
            }
            
            // Main container (overlay over graph)
            this.container = document.createElement('div');
            this.container.id = 'graph-card-view';
            this.container.style.cssText = `
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: var(--bg);
                display: none;
                overflow: hidden;
                z-index: 1;
                cursor: grab;
            `;
            
            // Canvas - the pannable/zoomable area
            this.canvas = document.createElement('div');
            this.canvas.id = 'card-view-canvas';
            this.canvas.style.cssText = `
                position: absolute;
                top: 0;
                left: 0;
                width: 10000px;
                height: 10000px;
                transform-origin: 0 0;
                transition: transform 0.05s linear;
            `;
            
            // Edges container (behind cards)
            this.edgesContainer = document.createElement('div');
            this.edgesContainer.id = 'card-view-edges';
            this.edgesContainer.style.cssText = `
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                pointer-events: none;
                z-index: 1;
            `;
            this.canvas.appendChild(this.edgesContainer);
            
            // Cards container (on top of edges)
            this.cardsContainer = document.createElement('div');
            this.cardsContainer.id = 'card-view-cards';
            this.cardsContainer.style.cssText = `
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                z-index: 2;
            `;
            this.canvas.appendChild(this.cardsContainer);
            
            this.container.appendChild(this.canvas);
            
            // Add control buttons
            this.createControls();
            
            graphContainer.appendChild(this.container);
        },
        
        /**
         * Create control buttons overlay
         */
        createControls: function() {
            const controls = document.createElement('div');
            controls.style.cssText = `
                position: absolute;
                top: 20px;
                right: 20px;
                display: flex;
                flex-direction: column;
                gap: 8px;
                z-index: 1000;
                pointer-events: auto;
            `;
            
            const buttonStyle = `
                padding: 10px 16px;
                background: var(--panel-bg);
                border: 1px solid var(--border);
                border-radius: 6px;
                color: var(--text);
                cursor: pointer;
                font-weight: 600;
                font-size: 13px;
                backdrop-filter: blur(10px);
                transition: all 0.2s;
            `;
            
            // Zoom controls
            const zoomIn = document.createElement('button');
            zoomIn.textContent = '🔍 +';
            zoomIn.style.cssText = buttonStyle;
            zoomIn.onclick = (e) => {
                e.stopPropagation();
                this.zoom(1.2);
            };
            
            const zoomOut = document.createElement('button');
            zoomOut.textContent = '🔍 −';
            zoomOut.style.cssText = buttonStyle;
            zoomOut.onclick = (e) => {
                e.stopPropagation();
                this.zoom(0.8);
            };
            
            const zoomReset = document.createElement('button');
            zoomReset.textContent = '⊙ Reset';
            zoomReset.style.cssText = buttonStyle;
            zoomReset.onclick = (e) => {
                e.stopPropagation();
                this.resetViewport();
            };
            
            const expandAll = document.createElement('button');
            expandAll.textContent = '⊕ Expand';
            expandAll.style.cssText = buttonStyle;
            expandAll.onclick = (e) => {
                e.stopPropagation();
                this.expandAll();
            };
            
            const collapseAll = document.createElement('button');
            collapseAll.textContent = '⊖ Collapse';
            collapseAll.style.cssText = buttonStyle;
            collapseAll.onclick = (e) => {
                e.stopPropagation();
                this.collapseAll();
            };
            
            const refresh = document.createElement('button');
            refresh.textContent = '↻ Refresh';
            refresh.style.cssText = buttonStyle;
            refresh.onclick = (e) => {
                e.stopPropagation();
                this.refresh();
            };
            
            controls.appendChild(zoomIn);
            controls.appendChild(zoomOut);
            controls.appendChild(zoomReset);
            controls.appendChild(document.createElement('div')); // Spacer
            controls.appendChild(expandAll);
            controls.appendChild(collapseAll);
            controls.appendChild(document.createElement('div')); // Spacer
            controls.appendChild(refresh);
            
            this.container.appendChild(controls);
        },
        
        /**
         * Add toggle button
         */
        addToggleButton: function() {
            const graphContainer = document.getElementById('graph');
            if (!graphContainer) return;
            
            const toggleBtn = document.createElement('button');
            toggleBtn.id = 'toggle-card-view-btn';
            toggleBtn.textContent = '📋 Card View';
            toggleBtn.style.cssText = `
                position: absolute;
                top: 20px;
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
                transition: all 0.2s;
            `;
            
            toggleBtn.onclick = () => this.toggle();
            
            graphContainer.appendChild(toggleBtn);
        },
        
        /**
         * Setup event listeners for pan/zoom
         */
        setupEventListeners: function() {
            const self = this;
            
            // Pan with mouse drag - more reliable detection
            this.container.addEventListener('mousedown', function(e) {
                // Start drag unless clicking on a card or button
                const isCard = e.target.closest('.graph-card-node');
                const isButton = e.target.closest('button');
                
                if (!isCard && !isButton) {
                    self.viewport.isDragging = true;
                    self.viewport.dragStartX = e.clientX;
                    self.viewport.dragStartY = e.clientY;
                    self.viewport.startTranslateX = self.viewport.translateX;
                    self.viewport.startTranslateY = self.viewport.translateY;
                    self.container.style.cursor = 'grabbing';
                    e.preventDefault();
                }
            });
            
            document.addEventListener('mousemove', function(e) {
                if (self.viewport.isDragging) {
                    const dx = e.clientX - self.viewport.dragStartX;
                    const dy = e.clientY - self.viewport.dragStartY;
                    
                    self.viewport.translateX = self.viewport.startTranslateX + dx;
                    self.viewport.translateY = self.viewport.startTranslateY + dy;
                    
                    self.updateCanvasTransform();
                    
                    // Add dragging class for visual feedback
                    self.container.classList.add('dragging');
                    
                    e.preventDefault();
                    e.stopPropagation();
                }
            });
            
            document.addEventListener('mouseup', function(e) {
                if (self.viewport.isDragging) {
                    self.viewport.isDragging = false;
                    self.container.style.cursor = 'grab';
                    self.container.classList.remove('dragging');
                }
            });
            
            // Zoom with mouse wheel - zoom toward cursor!
            // Also handle trackpad horizontal scroll
            this.container.addEventListener('wheel', function(e) {
                // Check if this is horizontal scrolling (trackpad swipe or Shift+wheel)
                const isHorizontalScroll = Math.abs(e.deltaX) > Math.abs(e.deltaY) || e.shiftKey;
                
                if (isHorizontalScroll) {
                    // Pan horizontally
                    e.preventDefault();
                    const deltaX = e.deltaX || e.deltaY; // Use deltaY if Shift is held
                    self.viewport.translateX -= deltaX;
                    self.updateCanvasTransform();
                } else {
                    // Zoom at cursor
                    e.preventDefault();
                    
                    // Get mouse position relative to container
                    const rect = self.container.getBoundingClientRect();
                    const mouseX = e.clientX - rect.left;
                    const mouseY = e.clientY - rect.top;
                    
                    const zoomFactor = e.deltaY > 0 ? 0.9 : 1.1;
                    self.zoomAtPoint(mouseX, mouseY, zoomFactor);
                }
            }, { passive: false });
            
            // Arrow key panning - only when hovering and no input focused
            this.containerHovered = false;
            
            this.container.addEventListener('mouseenter', () => {
                this.containerHovered = true;
                // Add visual hint that keyboard controls are active
                this.container.style.outline = '2px solid var(--accent, rgba(96, 165, 250, 0.3))';
                this.container.style.outlineOffset = '-2px';
            });
            
            this.container.addEventListener('mouseleave', () => {
                this.containerHovered = false;
                // Remove visual hint
                this.container.style.outline = 'none';
            });
            
            document.addEventListener('keydown', function(e) {
                // Only handle keys if:
                // 1. Card view is active
                // 2. Mouse is over the card view
                // 3. No input element has focus
                if (!self.active || !self.containerHovered) return;
                
                // Check if an input element has focus
                const activeElement = document.activeElement;
                const isInputFocused = activeElement && (
                    activeElement.tagName === 'INPUT' ||
                    activeElement.tagName === 'TEXTAREA' ||
                    activeElement.tagName === 'SELECT' ||
                    activeElement.isContentEditable
                );
                
                if (isInputFocused) return;
                
                const panSpeed = 50;
                let handled = false;
                
                switch(e.key) {
                    case 'ArrowLeft':
                        self.viewport.translateX += panSpeed;
                        handled = true;
                        break;
                    case 'ArrowRight':
                        self.viewport.translateX -= panSpeed;
                        handled = true;
                        break;
                    case 'ArrowUp':
                        self.viewport.translateY += panSpeed;
                        handled = true;
                        break;
                    case 'ArrowDown':
                        self.viewport.translateY -= panSpeed;
                        handled = true;
                        break;
                    case 'Escape':
                        self.toggle();
                        handled = true;
                        break;
                    case '+':
                    case '=':
                        // Zoom in at center
                        const centerX = self.container.clientWidth / 2;
                        const centerY = self.container.clientHeight / 2;
                        self.zoomAtPoint(centerX, centerY, 1.2);
                        handled = true;
                        break;
                    case '-':
                    case '_':
                        // Zoom out at center
                        const cX = self.container.clientWidth / 2;
                        const cY = self.container.clientHeight / 2;
                        self.zoomAtPoint(cX, cY, 0.8);
                        handled = true;
                        break;
                    case '0':
                        self.resetViewport();
                        handled = true;
                        break;
                }
                
                if (handled) {
                    self.updateCanvasTransform();
                    e.preventDefault();
                }
            });
        },
        
        /**
         * Update canvas transform for pan/zoom
         */
        updateCanvasTransform: function() {
            if (!this.canvas) return;
            
            this.canvas.style.transform = 
                `translate(${this.viewport.translateX}px, ${this.viewport.translateY}px) scale(${this.viewport.scale})`;
        },
        
        /**
         * Zoom at a specific point (cursor position)
         */
        zoomAtPoint: function(pointX, pointY, factor) {
            const oldScale = this.viewport.scale;
            const newScale = Math.max(0.1, Math.min(3, oldScale * factor));
            
            if (newScale === oldScale) return;
            
            // Calculate the point in canvas coordinates before zoom
            const canvasX = (pointX - this.viewport.translateX) / oldScale;
            const canvasY = (pointY - this.viewport.translateY) / oldScale;
            
            // Update scale
            this.viewport.scale = newScale;
            
            // Calculate new translation to keep the point under the cursor
            this.viewport.translateX = pointX - canvasX * newScale;
            this.viewport.translateY = pointY - canvasY * newScale;
            
            this.updateCanvasTransform();
        },
        
        /**
         * Zoom the viewport (legacy method - now zooms at center)
         */
        zoom: function(factor) {
            const centerX = this.container.clientWidth / 2;
            const centerY = this.container.clientHeight / 2;
            this.zoomAtPoint(centerX, centerY, factor);
        },
        
        /**
         * Reset viewport to initial state
         */
        resetViewport: function() {
            this.viewport.scale = 1;
            this.viewport.translateX = 0;
            this.viewport.translateY = 0;
            
            this.updateCanvasTransform();
        },
        
        /**
         * Toggle between graph and card view
         */
        toggle: function() {
            if (!this.container) {
                console.error('GraphCardView: Container not initialized');
                return;
            }
            
            this.active = !this.active;
            
            const graphCanvas = document.querySelector('#graph canvas');
            const toggleBtn = document.getElementById('toggle-card-view-btn');
            
            if (this.active) {
                // Show card view
                if (graphCanvas) graphCanvas.style.display = 'none';
                this.container.style.display = 'block';
                if (toggleBtn) toggleBtn.textContent = '🕸️ Graph View';
                
                this.loadData();
                this.render();
            } else {
                // Show graph view
                if (graphCanvas) graphCanvas.style.display = 'block';
                this.container.style.display = 'none';
                if (toggleBtn) toggleBtn.textContent = '📋 Card View';
            }
        },
        
        /**
         * Load data from GraphAddon
         */
        loadData: function() {
            console.log('GraphCardView: Loading data...');
            
            if (!window.GraphAddon || !window.GraphAddon.nodesData) {
                console.error('GraphCardView: GraphAddon not available');
                return;
            }
            
            this.nodes.clear();
            this.edges = [];
            this.expandedNodes.clear();
            
            // Load nodes
            Object.entries(window.GraphAddon.nodesData).forEach(([id, data]) => {
                this.nodes.set(id, {
                    id: id,
                    data: data,
                    children: [],
                    parents: [],
                    x: 0,
                    y: 0,
                    level: 0
                });
            });
            
            // Load edges
            if (window.network && window.network.body && window.network.body.data) {
                const edges = window.network.body.data.edges.get();
                edges.forEach(edge => {
                    this.edges.push({
                        from: edge.from,
                        to: edge.to,
                        label: edge.label || edge.type || ''
                    });
                    
                    const fromNode = this.nodes.get(edge.from);
                    const toNode = this.nodes.get(edge.to);
                    
                    if (fromNode && toNode) {
                        fromNode.children.push(edge.to);
                        toNode.parents.push(edge.from);
                    }
                });
            }
            
            console.log(`GraphCardView: Loaded ${this.nodes.size} nodes, ${this.edges.length} edges`);
            
            this.buildHierarchy();
        },
        
        /**
         * Build hierarchical layout
         */
        buildHierarchy: function() {
            console.log('GraphCardView: Building hierarchy...');
            
            // Find root nodes
            const roots = [];
            this.nodes.forEach((node, id) => {
                if (node.parents.length === 0) {
                    roots.push(id);
                }
            });
            
            if (roots.length === 0) {
                const sorted = Array.from(this.nodes.values())
                    .sort((a, b) => b.children.length - a.children.length);
                roots.push(sorted[0].id);
            }
            
            console.log(`GraphCardView: Found ${roots.length} root nodes`);
            
            // Build tree with BFS
            const visited = new Set();
            const queue = roots.map(id => ({ id, level: 0 }));
            
            while (queue.length > 0) {
                const { id, level } = queue.shift();
                
                if (visited.has(id)) continue;
                visited.add(id);
                
                const node = this.nodes.get(id);
                if (!node) continue;
                
                node.level = level;
                
                node.children.forEach(childId => {
                    if (!visited.has(childId)) {
                        queue.push({ id: childId, level: level + 1 });
                    }
                });
            }
            
            // Handle unvisited nodes
            this.nodes.forEach((node, id) => {
                if (!visited.has(id)) {
                    const maxParentLevel = Math.max(0, ...node.parents.map(pid => {
                        const parent = this.nodes.get(pid);
                        return parent ? parent.level : -1;
                    }));
                    node.level = maxParentLevel + 1;
                }
            });
            
            this.calculatePositions();
            
            // Auto-expand first level
            roots.forEach(rootId => {
                this.expandedNodes.add(rootId);
            });
        },
        
        /**
         * Calculate node positions
         */
        calculatePositions: function() {
            const levels = new Map();
            this.nodes.forEach((node, id) => {
                if (!levels.has(node.level)) {
                    levels.set(node.level, []);
                }
                levels.get(node.level).push(id);
            });
            
            levels.forEach((nodeIds, level) => {
                const y = this.layout.rootY + level * (this.layout.cardHeight + this.layout.verticalGap);
                const totalWidth = nodeIds.length * (this.layout.cardWidth + this.layout.horizontalGap);
                let startX = this.layout.rootX;
                
                nodeIds.forEach((id, index) => {
                    const node = this.nodes.get(id);
                    if (!node) return;
                    
                    node.x = startX + index * (this.layout.cardWidth + this.layout.horizontalGap);
                    node.y = y;
                });
            });
        },
        
        /**
         * Render the card view
         */
        render: function() {
            console.log('GraphCardView: Rendering...');
            
            this.cardsContainer.innerHTML = '';
            this.edgesContainer.innerHTML = '';
            
            const visibleNodes = this.getVisibleNodes();
            
            // Render edges first (behind cards)
            this.renderEdges(visibleNodes);
            
            // Render cards
            this.renderCards(visibleNodes);
        },
        
        /**
         * Get visible nodes
         */
        getVisibleNodes: function() {
            const visible = new Set();
            
            this.nodes.forEach((node, id) => {
                if (node.level === 0) {
                    visible.add(id);
                }
            });
            
            this.expandedNodes.forEach(nodeId => {
                visible.add(nodeId);
                const node = this.nodes.get(nodeId);
                if (node) {
                    node.children.forEach(childId => visible.add(childId));
                }
            });
            
            return Array.from(visible);
        },
        
        /**
         * Render edges with per-level offset tracking and collision avoidance
         */
        renderEdges: function(visibleNodeIds) {
            const visibleSet = new Set(visibleNodeIds);
            
            // Collect all edges to render
            const edgesToRender = [];
            this.edges.forEach(edge => {
                if (!visibleSet.has(edge.from) || !visibleSet.has(edge.to)) {
                    return;
                }
                
                const parent = this.nodes.get(edge.from);
                const child = this.nodes.get(edge.to);
                if (!parent || !child) return;
                
                edgesToRender.push({
                    parent,
                    child,
                    label: edge.label,
                    parentId: edge.from,
                    childId: edge.to,
                    levelPair: `${parent.level}-${child.level}` // Track level transition
                });
            });
            
            // Group by level pair to reset offsets per layer
            const edgesByLevelPair = new Map();
            edgesToRender.forEach(edge => {
                if (!edgesByLevelPair.has(edge.levelPair)) {
                    edgesByLevelPair.set(edge.levelPair, []);
                }
                edgesByLevelPair.get(edge.levelPair).push(edge);
            });
            
            // Also group by parent for fan calculation
            const edgesByParent = new Map();
            edgesToRender.forEach(edge => {
                if (!edgesByParent.has(edge.parentId)) {
                    edgesByParent.set(edge.parentId, []);
                }
                edgesByParent.get(edge.parentId).push(edge);
            });
            
            // Assign fan indices
            edgesByParent.forEach(edges => {
                edges.forEach((edge, index) => {
                    edge.fanIndex = index;
                    edge.fanTotal = edges.length;
                });
            });
            
            // Render each level pair with its own offset counter
            edgesByLevelPair.forEach((edges, levelPair) => {
                // Calculate dynamic spacing based on number of edges
                const numEdges = edges.length;
                
                // Get parent and child for this level pair to calculate available space
                const sampleEdge = edges[0];
                const verticalGap = sampleEdge.child.y - (sampleEdge.parent.y + this.layout.cardHeight);
                
                // Use middle portion of gap for routing (leaving buffers top and bottom)
                const safeZoneHeight = verticalGap * 0.4; // 40% of gap for routing
                
                // Calculate spacing that fits all edges without overlap
                // Minimum 8px, maximum 15px spacing
                const spacing = Math.max(8, Math.min(15, safeZoneHeight / Math.max(1, numEdges - 1)));
                
                edges.forEach((edge, index) => {
                    const routingOffset = index * spacing;
                    this.createSmartEdge(edge, routingOffset, verticalGap);
                });
            });
        },
        
        /**
         * Create edge with smart routing that avoids backtracking and crossings
         */
        createSmartEdge: function(edgeInfo, routingOffset, verticalGap) {
            const { parent, child, label, fanIndex, fanTotal } = edgeInfo;
            
            // Calculate card centers
            const parentCenterX = parent.x + this.layout.cardWidth / 2;
            const parentBottomY = parent.y + this.layout.cardHeight;
            const childCenterX = child.x + this.layout.cardWidth / 2;
            const childTopY = child.y;
            
            // Calculate actual vertical gap if not provided
            const actualVerticalGap = verticalGap || (childTopY - parentBottomY);
            
            // Calculate routing level in the SPACE BETWEEN cards
            const routingZoneStart = parentBottomY + (actualVerticalGap * 0.3);
            const routingY = routingZoneStart + routingOffset;
            
            // Generate UNIQUE vertical offset for each edge using prime number multiplication
            // This ensures better distribution without modulo wrapping
            const uniqueIndex = Math.floor(routingOffset);
            const verticalOffset = ((uniqueIndex * 11) % 60) - 30; // Range: -30 to +30
            
            // Calculate parent and child connection points with vertical offset
            const parentConnectionX = parentCenterX + verticalOffset;
            const childConnectionX = childCenterX + verticalOffset;
            
            // Calculate fan position for siblings
            let fanX = parentCenterX;
            if (fanTotal > 1) {
                const maxFanSpread = Math.min(80, fanTotal * 15);
                const fanOffsetX = (fanIndex - (fanTotal - 1) / 2) * (maxFanSpread / (fanTotal - 1));
                fanX = parentCenterX + fanOffsetX;
            }
            
            // SMART ROUTING: Determine path that avoids backtracking
            // Check the overall direction of travel
            const parentToChild = childConnectionX - parentConnectionX;
            const movingRight = parentToChild > 0;
            const movingLeft = parentToChild < 0;
            const movingStraight = Math.abs(parentToChild) < 5;
            
            // Check if fan routing would cause backtracking
            const parentToFan = fanX - parentConnectionX;
            const fanToChild = childConnectionX - fanX;
            
            // Detect backtracking: if we go right then left, or left then right
            const fanCausesBacktrack = (
                (parentToFan > 5 && fanToChild < -5) ||  // Right then left
                (parentToFan < -5 && fanToChild > 5)      // Left then right
            );
            
            // Choose routing strategy
            let routingPathX;
            if (fanTotal === 1 || fanCausesBacktrack || movingStraight) {
                // Direct routing - use midpoint
                routingPathX = (parentConnectionX + childConnectionX) / 2;
            } else {
                // Fan routing won't cause backtrack - use it
                routingPathX = fanX;
            }
            
            // Check for node collisions
            const adjustedRoutingY = this.avoidNodeCollisions(
                routingY,
                Math.min(parentConnectionX, childConnectionX, routingPathX),
                Math.max(parentConnectionX, childConnectionX, routingPathX),
                parent.level,
                child.level
            );
            
            // Build path segments - optimized to avoid backtracking
            const segments = [];
            
            // SEGMENT 1: Vertical down from parent
            segments.push({
                type: 'vertical',
                x: parentConnectionX,
                y1: parentBottomY,
                y2: adjustedRoutingY,
                color: 'var(--border)'
            });
            
            // SEGMENT 2 & 3: Smart horizontal routing
            // Sort X positions to always move monotonically
            const xPositions = [parentConnectionX, routingPathX, childConnectionX].sort((a, b) => a - b);
            
            // Only create segments that move us forward (no backtracking)
            let currentX = parentConnectionX;
            
            for (let i = 0; i < xPositions.length; i++) {
                const nextX = xPositions[i];
                
                // Skip if this is our current position
                if (Math.abs(nextX - currentX) < 3) continue;
                
                // Check if this position is in our path
                const isInPath = (nextX === parentConnectionX || nextX === routingPathX || nextX === childConnectionX);
                
                if (isInPath && Math.abs(nextX - currentX) >= 3) {
                    segments.push({
                        type: 'horizontal',
                        x1: currentX,
                        x2: nextX,
                        y: adjustedRoutingY,
                        color: 'var(--border)'
                    });
                    currentX = nextX;
                }
            }
            
            // Make sure we end at child position
            if (Math.abs(currentX - childConnectionX) >= 3) {
                segments.push({
                    type: 'horizontal',
                    x1: currentX,
                    x2: childConnectionX,
                    y: adjustedRoutingY,
                    color: 'var(--border)'
                });
            }
            
            // SEGMENT 4: Vertical up to child
            segments.push({
                type: 'vertical',
                x: childConnectionX,
                y1: adjustedRoutingY,
                y2: childTopY,
                color: 'var(--border)'
            });
            
            // Render segments
            const elements = [];
            segments.forEach(seg => {
                const el = this.createSegment(seg);
                if (el) {
                    this.edgesContainer.appendChild(el);
                    elements.push(el);
                }
            });
            
            // Add arrow at child center
            const arrow = this.createArrow(childConnectionX, childTopY);
            this.edgesContainer.appendChild(arrow);
            elements.push(arrow);
            
            // Add label
            if (label) {
                const labelEl = this.createLabel(label, (parentCenterX + childCenterX) / 2, adjustedRoutingY);
                this.edgesContainer.appendChild(labelEl);
            }
            
            // Add interactivity
            this.makeEdgeInteractive(elements);
        },
        
        /**
         * Avoid routing through nodes
         */
        avoidNodeCollisions: function(routingY, minX, maxX, parentLevel, childLevel) {
            let adjustedY = routingY;
            let collisionFound = false;
            
            // Check all nodes between parent and child levels
            this.nodes.forEach((node, id) => {
                // Only check nodes in levels between parent and child
                if (node.level <= parentLevel || node.level >= childLevel) {
                    return;
                }
                
                // Check if routing line would pass through this node
                const nodeLeft = node.x;
                const nodeRight = node.x + this.layout.cardWidth;
                const nodeTop = node.y;
                const nodeBottom = node.y + this.layout.cardHeight;
                
                // Check horizontal overlap
                const horizontalOverlap = (maxX >= nodeLeft && minX <= nodeRight);
                
                // Check vertical overlap
                const verticalOverlap = (routingY >= nodeTop && routingY <= nodeBottom);
                
                if (horizontalOverlap && verticalOverlap) {
                    collisionFound = true;
                    // Route below the node with some padding
                    adjustedY = Math.max(adjustedY, nodeBottom + 15);
                }
            });
            
            return adjustedY;
        },
        
        /**
         * Create a line segment
         */
        createSegment: function(seg) {
            const el = document.createElement('div');
            el.className = seg.type === 'vertical' ? 'edge-line edge-vertical' : 'edge-line edge-horizontal';
            
            if (seg.type === 'vertical') {
                const height = Math.abs(seg.y2 - seg.y1);
                const top = Math.min(seg.y1, seg.y2);
                
                el.style.cssText = `
                    position: absolute;
                    left: ${seg.x - 1.5}px;
                    top: ${top}px;
                    width: 3px;
                    height: ${height}px;
                    background: ${seg.color};
                    opacity: 0.7;
                    transition: all 0.2s;
                    box-shadow: 0 0 4px rgba(0,0,0,0.3);
                `;
            } else {
                const width = Math.abs(seg.x2 - seg.x1);
                const left = Math.min(seg.x1, seg.x2);
                
                if (width < 1) return null; // Skip zero-width segments
                
                el.style.cssText = `
                    position: absolute;
                    left: ${left}px;
                    top: ${seg.y - 1.5}px;
                    width: ${width}px;
                    height: 3px;
                    background: ${seg.color};
                    opacity: 0.7;
                    transition: all 0.2s;
                    box-shadow: 0 0 4px rgba(0,0,0,0.3);
                `;
            }
            
            return el;
        },
        
        /**
         * Create arrow pointing down
         */
        createArrow: function(x, y) {
            const arrow = document.createElement('div');
            arrow.className = 'edge-arrow';
            arrow.style.cssText = `
                position: absolute;
                left: ${x - 5}px;
                top: ${y - 10}px;
                width: 0;
                height: 0;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 10px solid var(--border);
                opacity: 0.7;
                transition: all 0.2s;
                filter: drop-shadow(0 2px 3px rgba(0,0,0,0.3));
            `;
            return arrow;
        },
        
        /**
         * Create edge label
         */
        createLabel: function(text, x, y) {
            const label = document.createElement('div');
            label.textContent = text;
            label.style.cssText = `
                position: absolute;
                left: ${x - 35}px;
                top: ${y - 14}px;
                padding: 3px 8px;
                background: var(--bg);
                border: 1px solid var(--border);
                border-radius: 4px;
                color: var(--text-secondary);
                font-size: 10px;
                font-weight: 600;
                white-space: nowrap;
                pointer-events: none;
                z-index: 10;
                box-shadow: 0 2px 4px rgba(0,0,0,0.2);
            `;
            return label;
        },
        
        /**
         * Make edge interactive with hover effects
         */
        makeEdgeInteractive: function(elements) {
            // Create wider invisible hover zones
            const hoverZones = [];
            
            elements.forEach(el => {
                if (!el.classList || !el.classList.contains('edge-line')) return;
                
                const zone = document.createElement('div');
                const isVertical = el.classList.contains('edge-vertical');
                
                if (isVertical) {
                    const left = parseFloat(el.style.left);
                    const top = parseFloat(el.style.top);
                    const height = parseFloat(el.style.height);
                    
                    zone.style.cssText = `
                        position: absolute;
                        left: ${left - 12}px;
                        top: ${top}px;
                        width: 28px;
                        height: ${height}px;
                        background: transparent;
                        pointer-events: auto;
                        cursor: pointer;
                    `;
                } else {
                    const left = parseFloat(el.style.left);
                    const top = parseFloat(el.style.top);
                    const width = parseFloat(el.style.width);
                    
                    zone.style.cssText = `
                        position: absolute;
                        left: ${left}px;
                        top: ${top - 12}px;
                        width: ${width}px;
                        height: 28px;
                        background: transparent;
                        pointer-events: auto;
                        cursor: pointer;
                    `;
                }
                
                this.edgesContainer.appendChild(zone);
                hoverZones.push(zone);
            });
            
            // Highlight entire edge on hover
            const highlight = (active) => {
                elements.forEach(el => {
                    if (!el.style) return;
                    
                    if (active) {
                        el.style.opacity = '1';
                        el.style.background = 'var(--accent)';
                        el.style.boxShadow = '0 0 8px var(--accent)';
                        if (el.style.borderTop) {
                            el.style.borderTopColor = 'var(--accent)';
                            el.style.filter = 'drop-shadow(0 2px 8px var(--accent))';
                        }
                    } else {
                        el.style.opacity = '0.7';
                        el.style.background = 'var(--border)';
                        el.style.boxShadow = '0 0 4px rgba(0,0,0,0.3)';
                        if (el.style.borderTop) {
                            el.style.borderTopColor = 'var(--border)';
                            el.style.filter = 'drop-shadow(0 2px 3px rgba(0,0,0,0.3))';
                        }
                    }
                });
            };
            
            // Add hover listeners
            [...elements, ...hoverZones].forEach(el => {
                el.addEventListener('mouseenter', () => highlight(true));
                el.addEventListener('mouseleave', () => highlight(false));
            });
        },
        
        /**
         * Render cards
         */
        renderCards: function(visibleNodeIds) {
            visibleNodeIds.forEach(nodeId => {
                const node = this.nodes.get(nodeId);
                if (!node) return;
                
                const card = this.createCard(node);
                this.cardsContainer.appendChild(card);
            });
        },
        
        /**
         * Create a node card
         */
        createCard: function(node) {
            const isExpanded = this.expandedNodes.has(node.id);
            const hasChildren = node.children.length > 0;
            
            const card = document.createElement('div');
            card.className = 'graph-card-node';
            card.dataset.nodeId = node.id;
            card.style.cssText = `
                position: absolute;
                left: ${node.x}px;
                top: ${node.y}px;
                width: ${this.layout.cardWidth}px;
                min-height: ${this.layout.cardHeight}px;
                background: var(--panel-bg);
                border: 2px solid ${node.data.color || 'var(--border)'};
                border-radius: 8px;
                padding: 14px;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
                cursor: pointer;
                transition: all 0.2s;
                backdrop-filter: blur(10px);
                pointer-events: auto;
            `;
            
            // Header
            const header = document.createElement('div');
            header.style.cssText = `
                display: flex;
                align-items: flex-start;
                justify-content: space-between;
                margin-bottom: 10px;
            `;
            
            const title = document.createElement('div');
            title.style.cssText = `
                color: var(--text);
                font-size: 14px;
                font-weight: 600;
                flex: 1;
                word-wrap: break-word;
                line-height: 1.3;
            `;
            title.textContent = node.data.display_name || node.id;
            
            const expandBtn = document.createElement('div');
            if (hasChildren) {
                expandBtn.style.cssText = `
                    color: var(--text-secondary);
                    font-size: 20px;
                    cursor: pointer;
                    padding: 0 4px;
                    margin-left: 8px;
                    flex-shrink: 0;
                `;
                expandBtn.textContent = isExpanded ? '−' : '+';
                expandBtn.onclick = (e) => {
                    e.stopPropagation();
                    this.toggleExpand(node.id);
                };
            }
            
            header.appendChild(title);
            header.appendChild(expandBtn);
            card.appendChild(header);
            
            // Labels
            if (node.data.labels && node.data.labels.length > 0) {
                const labels = document.createElement('div');
                labels.style.cssText = `
                    display: flex;
                    flex-wrap: wrap;
                    gap: 4px;
                    margin-bottom: 10px;
                `;
                
                node.data.labels.slice(0, 3).forEach(label => {
                    const badge = document.createElement('span');
                    badge.style.cssText = `
                        display: inline-block;
                        padding: 2px 6px;
                        background: var(--accent-bg, rgba(96, 165, 250, 0.15));
                        border: 1px solid var(--accent-border, rgba(96, 165, 250, 0.4));
                        border-radius: 3px;
                        color: var(--accent);
                        font-size: 10px;
                        font-weight: 600;
                    `;
                    badge.textContent = label;
                    labels.appendChild(badge);
                });
                
                card.appendChild(labels);
            }
            
            // Properties preview
            const props = node.data.properties || {};
            const importantProps = ['text', 'body', 'content', 'summary', 'description'];
            let previewText = '';
            
            for (const key of importantProps) {
                if (props[key]) {
                    previewText = String(props[key]);
                    break;
                }
            }
            
            if (previewText) {
                const preview = document.createElement('div');
                preview.style.cssText = `
                    color: var(--text-secondary);
                    font-size: 11px;
                    line-height: 1.5;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    display: -webkit-box;
                    -webkit-line-clamp: 3;
                    -webkit-box-orient: vertical;
                    margin-bottom: 10px;
                `;
                preview.textContent = previewText.substring(0, 150);
                card.appendChild(preview);
            }
            
            // Footer
            const footer = document.createElement('div');
            footer.style.cssText = `
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding-top: 10px;
                border-top: 1px solid var(--border);
                color: var(--text-secondary);
                font-size: 10px;
            `;
            
            footer.innerHTML = `
                <span>${node.children.length} children</span>
                <span>${node.parents.length} parents</span>
                <span>L${node.level}</span>
            `;
            
            card.appendChild(footer);
            
            // Click handler
            card.onclick = (e) => {
                if (e.target !== expandBtn) {
                    this.focusNode(node.id);
                }
            };
            
            // Hover effects
            card.onmouseenter = () => {
                card.style.transform = 'translateY(-2px)';
                card.style.boxShadow = '0 8px 24px rgba(0, 0, 0, 0.4)';
            };
            
            card.onmouseleave = () => {
                card.style.transform = 'translateY(0)';
                card.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.3)';
            };
            
            return card;
        },
        
        /**
         * Toggle node expansion
         */
        toggleExpand: function(nodeId) {
            if (this.expandedNodes.has(nodeId)) {
                this.expandedNodes.delete(nodeId);
            } else {
                this.expandedNodes.add(nodeId);
            }
            
            this.render();
        },
        
        /**
         * Focus on a node
         */
        focusNode: function(nodeId) {
            this.focusedNode = nodeId;
            
            // Show in GraphInfoCard if available
            if (window.GraphInfoCard && window.GraphInfoCard.expandNodeInfo) {
                window.GraphInfoCard.expandNodeInfo(nodeId);
            }
            
            // Center on node
            const node = this.nodes.get(nodeId);
            if (node) {
                const centerX = this.container.clientWidth / 2;
                const centerY = this.container.clientHeight / 2;
                
                this.viewport.translateX = centerX - (node.x + this.layout.cardWidth / 2) * this.viewport.scale;
                this.viewport.translateY = centerY - (node.y + this.layout.cardHeight / 2) * this.viewport.scale;
                
                this.updateCanvasTransform();
            }
            
            // Ensure expanded
            if (!this.expandedNodes.has(nodeId)) {
                this.expandedNodes.add(nodeId);
                this.render();
            }
        },
        
        /**
         * Expand all nodes
         */
        expandAll: function() {
            this.nodes.forEach((node, id) => {
                if (node.children.length > 0) {
                    this.expandedNodes.add(id);
                }
            });
            
            this.render();
        },
        
        /**
         * Collapse all nodes
         */
        collapseAll: function() {
            this.expandedNodes.clear();
            
            this.nodes.forEach((node, id) => {
                if (node.level === 0) {
                    this.expandedNodes.add(id);
                }
            });
            
            this.render();
        },
        
        /**
         * Refresh the view
         */
        refresh: function() {
            this.loadData();
            this.render();
            this.resetViewport();
        }
    };
    
    // Auto-initialize when GraphAddon is ready
    window.addEventListener('graphAddonReady', () => {
        window.GraphCardView.init();
    });
    
})();