/**
 * GraphStateManager - Unified State & Rendering Manager
 * 
 * Single source of truth for:
 * - Active filter state (persisted across reloads)
 * - Active style settings (persisted across reloads)
 * - Incremental node/edge updates (no full redraws)
 * - Discovery mode (bypass filters for neighbor/path ops)
 *
 * Usage:
 *   // Instead of app.loadGraph():
 *   window.GraphStateManager.reload();
 *
 *   // Instead of app.addNodesToGraph():
 *   window.GraphStateManager.addNodes(nodes, edges, { discoveryMode: false });
 *
 *   // Toggle discovery mode before neighbor expansion:
 *   window.GraphStateManager.setDiscoveryMode(true);
 *   await GraphDiscovery.expandNeighbors(nodeId, 2);
 *   window.GraphStateManager.setDiscoveryMode(false);
 */

(function () {
    'use strict';

    window.GraphStateManager = {

        // ─── State ────────────────────────────────────────────────────────────
        _initialized: false,
        _discoveryMode: false,   // When true, new nodes bypass filters
        _pendingStyleApply: null,

        // Internal cache of ALL nodes/edges ever added to the graph
        // Key: node/edge id  Value: processed node/edge object
        _nodeCache: new Map(),
        _edgeCache: new Map(),

        // ─── Init ─────────────────────────────────────────────────────────────
        init: function () {
            if (this._initialized) return;
            this._initialized = true;
            console.log('GraphStateManager: Initializing...');

            // Intercept VeraChat prototype methods if app exists
            this._patchVeraChat();

            // Start polling to install traps as early as possible
            this._installTrapsWhenReady();

            // Listen for graph addon ready to apply persisted state
            window.addEventListener('graphModulesReady', () => {
                console.log('GraphStateManager: Modules ready, restoring state...');
                this._trapAdvancedFilters();
                this._shimApplyAllStyles();
                this._rehookSetData();
                this._hookThemeManager();
                this._setDefaultSessionFilter();
                this._restoreState();
            });

            console.log('GraphStateManager: Ready');
        },

        // ─── Discovery Mode ───────────────────────────────────────────────────
        /**
         * Enable/disable discovery mode.
         * In discovery mode:
         * - New nodes added via addNodes() are NOT filtered out
         * - Styling IS still applied
         * - A visual indicator marks discovery edges
         */
        setDiscoveryMode: function (enabled) {
            this._discoveryMode = enabled;
            console.log(`GraphStateManager: Discovery mode ${enabled ? 'ON' : 'OFF'}`);

            // Show/hide discovery mode indicator in UI
            this._updateDiscoveryModeIndicator(enabled);
        },

        isDiscoveryMode: function () {
            return this._discoveryMode;
        },

        // ─── Core: Reload ─────────────────────────────────────────────────────
        /**
         * Reload graph data from API WITHOUT resetting filters/styles.
         * Replaces app.loadGraph() and app.reloadGraph().
         */
        reload: async function () {
            const app = window.app;
            if (!app || !app.sessionId) {
                if (window.graphLoaderUtils) window.graphLoaderUtils.show('No session active');
                return;
            }

            if (window.graphLoaderUtils) {
                window.graphLoaderUtils.setLoading(true);
                window.graphLoaderUtils.show('Loading graph...');
            }

            try {
                const response = await fetch(`http://llm.int:8888/api/graph/session/${app.sessionId}`);
                const data = await response.json();

                const nodeCount = data.nodes.length;
                const edgeCount = data.edges.length;

                console.log(`GraphStateManager: Received ${nodeCount} nodes, ${edgeCount} edges`);

                if (nodeCount === 0 && edgeCount === 0) {
                    if (window.graphLoaderUtils) {
                        window.graphLoaderUtils.setLoading(false);
                        window.graphLoaderUtils.show('No data in graph');
                    }
                    this._updateCounters(0, 0);
                    return;
                }

                // Process nodes/edges through GraphDataLoader normalizer
                const processedNodes = await window.GraphDataLoader.processNodesInChunks(data.nodes);
                const processedEdges = await window.GraphDataLoader.processEdgesInChunks(data.edges);

                // Update caches
                processedNodes.forEach(n => this._nodeCache.set(n.id, n));
                processedEdges.forEach(e => this._edgeCache.set(e.id, e));

                // Rebuild network data without destroying filter/style state
                await this._applyToNetwork(processedNodes, processedEdges, true);

            } catch (err) {
                console.error('GraphStateManager: Reload error', err);
                if (window.graphLoaderUtils) window.graphLoaderUtils.show('Error loading graph');
            } finally {
                if (window.graphLoaderUtils) window.graphLoaderUtils.setLoading(false);
            }
        },

        // ─── Core: Add Nodes/Edges ────────────────────────────────────────────
        /**
         * Add new nodes/edges incrementally.
         * Replaces app.addNodesToGraph().
         *
         * @param {Array} rawNodes
         * @param {Array} rawEdges
         * @param {Object} opts
         *   opts.discoveryMode {boolean} - override discovery mode for this call
         *   opts.animate {boolean} - animate entry (default: auto by count)
         *   opts.focusNew {boolean} - fit view to new nodes after add
         */
        addNodes: function (rawNodes, rawEdges, opts = {}) {
            if (!rawNodes || rawNodes.length === 0) return;
            if (!window.network) {
                console.warn('GraphStateManager: Network not ready');
                return;
            }

            const isDiscovery = (opts.discoveryMode !== undefined)
                ? opts.discoveryMode
                : this._discoveryMode;

            const shouldAnimate = (opts.animate !== undefined)
                ? opts.animate
                : rawNodes.length < 200;

            // Normalize through GraphDataLoader
            const processedNodes = rawNodes.map((n, i) =>
                window.GraphDataLoader ? window.GraphDataLoader.normalizeNode(n) : n
            );
            const processedEdges = (rawEdges || []).map((e, i) =>
                window.GraphDataLoader ? window.GraphDataLoader.normalizeEdge(e, i) : e
            );

            // Apply GraphStyleControl styling to new nodes before insertion
            const styledNodes = this._applyStyleToNodes(processedNodes);
            const styledEdges = this._applyStyleToEdges(processedEdges);

            // Update caches
            styledNodes.forEach(n => this._nodeCache.set(n.id, n));
            styledEdges.forEach(e => this._edgeCache.set(e.id, e));

            // Dedup - skip nodes already in network
            const existingNodeIds = new Set(network.body.data.nodes.getIds());
            const existingEdgeIds = new Set(network.body.data.edges.getIds());

            const newNodes = styledNodes.filter(n => !existingNodeIds.has(n.id));
            const updateNodes = styledNodes.filter(n => existingNodeIds.has(n.id));
            const newEdges = styledEdges.filter(e => !existingEdgeIds.has(e.id));

            if (newNodes.length === 0 && newEdges.length === 0 && updateNodes.length === 0) {
                console.log('GraphStateManager: No new nodes/edges to add');
                return;
            }

            console.log(`GraphStateManager: Adding ${newNodes.length} nodes, ${newEdges.length} edges (discovery: ${isDiscovery})`);

            // Animate or batch insert
            if (shouldAnimate) {
                this._animatedInsert(newNodes, newEdges, updateNodes, isDiscovery, opts);
            } else {
                this._batchInsert(newNodes, newEdges, updateNodes, isDiscovery);
            }

            // Reapply filters only if NOT in discovery mode
            if (!isDiscovery) {
                this._scheduleFilterApply();
            }
        },

        // ─── Core: Apply to Network ───────────────────────────────────────────
        /**
         * Push processed nodes/edges into vis.js network.
         * Preserves and reapplies current style + filter state.
         */
        _applyToNetwork: async function (nodes, edges, isFullReplace) {
            if (!window.network) return;

            if (window.graphLoaderUtils) window.graphLoaderUtils.show('Rendering graph...');

            const nodeCount = nodes.length;

            // Apply GraphStyleControl styling before inserting
            const styledNodes = this._applyStyleToNodes(nodes);
            const styledEdges = this._applyStyleToEdges(edges);

            // Temporarily disable physics for faster rendering on large graphs
            const hadPhysics = network.physics.options.enabled;
            if (hadPhysics && nodeCount > 500) {
                network.setOptions({ physics: { enabled: false } });
            }

            if (isFullReplace) {
                // setData is fastest for full replace
                network.setData({ nodes: styledNodes, edges: styledEdges });
            } else {
                network.body.data.nodes.update(styledNodes);
                network.body.data.edges.update(styledEdges);
            }

            // Restore physics
            await new Promise(resolve => requestAnimationFrame(() => {
                if (hadPhysics && nodeCount > 500) {
                    const physicsConfig = window.GraphDataLoader
                        ? window.GraphDataLoader.getPhysicsConfig(nodeCount)
                        : { enabled: true };
                    network.setOptions({ physics: physicsConfig });
                }
                network.fit();
                resolve();
            }));

            // Restore filter state (after a frame so vis.js has settled)
            await new Promise(resolve => requestAnimationFrame(() => {
                this._restoreFilters();
                if (window.graphLoaderUtils) window.graphLoaderUtils.hide(true);
                resolve();
            }));

            this._updateCounters(nodeCount, edges.length);

            // Rebuild GraphAddon index
            this._scheduleAddonRebuild();

            // Update color legend if style control is live
            if (window.GraphStyleControl && window.GraphStyleControl.updateColorLegend) {
                window.GraphStyleControl.updateColorLegend();
            }
        },

        // ─── Styling ──────────────────────────────────────────────────────────
        /**
         * Apply current GraphStyleControl settings to a batch of nodes.
         * Falls back to default styling if GraphStyleControl isn't ready.
         */
        _applyStyleToNodes: function (nodes) {
            if (!window.GraphStyleControl || !window.GraphStyleControl.graphAddon) {
                return nodes; // GraphStyleControl not initialized yet, return as-is
            }

            const styled = [];
            let _debugLogged = false;
            nodes.forEach(node => {
                try {
                    const update = window.GraphStyleControl.applyNodeStyle(node);
                    // One-time debug: log what applyNodeStyle actually returns
                    if (!_debugLogged && update) {
                        console.log('GSM DEBUG applyNodeStyle sample return:', JSON.stringify(update).slice(0, 300));
                        _debugLogged = true;
                    }
                    styled.push(update ? { ...node, ...update } : node);
                } catch (e) {
                    console.warn('GSM: applyNodeStyle threw for node', node.id, e.message);
                    styled.push(node);
                }
            });
            return styled;
        },

        /**
         * Apply current GraphStyleControl edge settings to a batch of edges.
         */
        _applyStyleToEdges: function (edges) {
            if (!window.GraphStyleControl || !window.GraphStyleControl.graphAddon) {
                return edges;
            }

            const styled = [];
            edges.forEach(edge => {
                try {
                    const update = window.GraphStyleControl.applyEdgeStyle(edge);
                    styled.push({ ...edge, ...update });
                } catch (e) {
                    styled.push(edge);
                }
            });
            return styled;
        },

        // ─── Filter State ─────────────────────────────────────────────────────
        /**
         * Re-apply current filter state without touching style state.
         * Called after every reload or incremental add (unless discovery mode).
         */
        _restoreFilters: function () {
            // Only restore filters if something is actually active.
            // Never call applyAllFilters unless advanced filters are genuinely non-default.

            const hasAdvancedFilters = this._hasActiveAdvancedFilters();
            const hasStyleFilters = this._hasActiveStyleFilters();

            if (!hasAdvancedFilters && !hasStyleFilters) {
                // Nothing to do — all nodes should be visible
                return;
            }

            if (hasAdvancedFilters) {
                try {
                    // Rebuild originalData cache from what is currently in the network
                    const af = window.GraphAdvancedFilters;
                    af.originalData.nodes.clear();
                    af.originalData.edges.clear();
                    network.body.data.nodes.forEach(n => af.originalData.nodes.set(n.id, { ...n }));
                    network.body.data.edges.forEach(e => af.originalData.edges.set(e.id, { ...e }));
                    af.applyAllFilters();
                } catch (e) {
                    console.warn('GraphStateManager: Advanced filter restore failed', e);
                }
            } else if (hasStyleFilters && window.GraphStyleControl && window.GraphStyleControl.graphAddon) {
                try {
                    window.GraphStyleControl.applyFilters();
                } catch (e) {
                    console.warn('GraphStateManager: Style filter restore failed', e);
                }
            }
        },

        _hasActiveAdvancedFilters: function () {
            try {
                const af = window.GraphAdvancedFilters;
                if (!af || !af.filters) return false;
                const f = af.filters;

                // session mode 'all' OR 'current' = default/inactive states
                // Only truly active if explicitly set to something else (e.g. a specific session ID)
                const defaultModes = ['all', 'current', 'session', '', null, undefined];
                const sessionMode = f.session && f.session.mode;
                const sessionActive = !!(sessionMode && !defaultModes.includes(sessionMode));

                // property filters must have actual non-empty values
                const nodeProps = f.nodeProperties || {};
                const edgeProps = f.edgeProperties || {};
                const nodePropsActive = Object.keys(nodeProps).some(k => {
                    const v = nodeProps[k];
                    return v !== null && v !== undefined && v !== '' && v !== false;
                });
                const edgePropsActive = Object.keys(edgeProps).some(k => {
                    const v = edgeProps[k];
                    return v !== null && v !== undefined && v !== '' && v !== false;
                });

                const active = !!(sessionActive || nodePropsActive || edgePropsActive);
                if (active) {
                    console.log('GraphStateManager: Advanced filters ACTIVE:', { sessionActive, nodePropsActive, edgePropsActive });
                }
                return active;
            } catch (e) {
                console.warn('GraphStateManager: _hasActiveAdvancedFilters error', e);
                return false;
            }
        },

        _hasActiveStyleFilters: function () {
            if (!window.GraphStyleControl) return false;
            const f = window.GraphStyleControl.settings.filters;
            if (!f) return false;
            if (f.hideIsolatedNodes) return true;
            const nodeFiltersActive = Object.values(f.nodeCategories || {}).some(v => v === false);
            const edgeFiltersActive = Object.values(f.edgeTypes || {}).some(v => v === false);
            return nodeFiltersActive || edgeFiltersActive;
        },

        // ─── Persisted State Restore ──────────────────────────────────────────
        /**
         * Called when graphModulesReady fires.
         * Reapplies saved style + filter settings to the current network.
         */
        _restoreState: function () {
            if (!window.network) return;

            const nodeCount = network.body.data.nodes.length;
            if (nodeCount === 0) return;

            console.log(`GraphStateManager: Restoring state for ${nodeCount} nodes...`);

            // 0. Ensure shims installed
            this._shimApplyAllStyles();

            // 3. Restore filters (safe — only runs if filters are genuinely active)
            this._restoreFilters();

            // 1+2+4. Apply custom styles on top of theme — wait 150ms so theme's
            // _batchUpdateGraphElements (which runs synchronously in apply()) has settled,
            // then assert our custom styles on top.
            setTimeout(() => {
                this._assertCustomStyles();
            }, 150);

            console.log('GraphStateManager: State restored (styles will assert in 150ms)');
        },

        // Trap: intercept GraphAdvancedFilters.applyAllFilters to prevent it running
        // when no filters are actually active (i.e. after every graph reload)
        _trapAdvancedFilters: function () {
            const af = window.GraphAdvancedFilters;
            if (!af || !af.applyAllFilters) return;
            if (af._gsm_trapped) return;

            const self = this;
            const originalApplyAll = af.applyAllFilters.bind(af);

            af.applyAllFilters = function (...args) {
                // Check if network has any nodes at all - if not, block regardless
                if (window.network) {
                    const nodeCount = window.network.body.data.nodes.length;
                    if (nodeCount === 0) {
                        console.log('GraphStateManager: Blocked applyAllFilters - network has 0 nodes (still loading)');
                        return;
                    }
                }

                // Check originalData cache - if empty but network has nodes, rebuild first
                if (af.originalData) {
                    const cacheSize = af.originalData.nodes ? af.originalData.nodes.size : 0;
                    const networkSize = window.network ? window.network.body.data.nodes.length : 0;
                    if (cacheSize === 0 && networkSize > 0) {
                        console.log('GraphStateManager: Rebuilding originalData cache before applyAllFilters');
                        af.originalData.nodes = af.originalData.nodes || new Map();
                        af.originalData.edges = af.originalData.edges || new Map();
                        window.network.body.data.nodes.forEach(n => af.originalData.nodes.set(n.id, {...n}));
                        window.network.body.data.edges.forEach(e => af.originalData.edges.set(e.id, {...e}));
                    }
                }

                if (!self._hasActiveAdvancedFilters()) {
                    console.log('GraphStateManager: Blocked spurious applyAllFilters (no active filters)');
                    return;
                }
                console.log('GraphStateManager: Allowing applyAllFilters (filters active)');
                return originalApplyAll(...args);
            };

            af._gsm_trapped = true;
            console.log('GraphStateManager: GraphAdvancedFilters.applyAllFilters trapped');
        },

        // Set the session filter to default to the current session on load
        _setDefaultSessionFilter: function () {
            const af = window.GraphAdvancedFilters;
            if (!af || !af.filters) return;

            // Only set if currently in 'all' mode (don't override a user-set filter)
            const currentMode = af.filters.session && af.filters.session.mode;
            if (currentMode && currentMode !== 'all' && currentMode !== '') return;

            const sessionId = window.app && window.app.sessionId;
            if (!sessionId) {
                console.log('GraphStateManager: No session ID yet, skipping session filter default');
                return;
            }

            // Set mode to 'current' so filter shows current session nodes
            // 'current' is a special mode in GraphAdvancedFilters that means "active session"
            if (af.filters.session) {
                af.filters.session.mode = 'current';
                af.filters.session.sessionId = sessionId;
            } else {
                af.filters.session = { mode: 'current', sessionId: sessionId };
            }

            console.log('GraphStateManager: Default session filter set to current session:', sessionId);

            // Update any UI elements that reflect this (dropdowns etc.)
            const sessionModeEl = document.getElementById('session-filter-mode')
                                || document.querySelector('[data-filter="session-mode"]')
                                || document.querySelector('select[name="sessionMode"]');
            if (sessionModeEl) {
                sessionModeEl.value = 'current';
                console.log('GraphStateManager: Session filter UI updated');
            }
        },

        // Re-hook network.setData so GSM style restoration always fires AFTER
        // theme manager's hook (theme wraps setData first, we wrap it again)
        _rehookSetData: function () {
            if (!window.network || window.network._gsm_setdata_hooked) return;

            const self = this;
            const prev = window.network.setData.bind(window.network);

            window.network.setData = function (data) {
                prev(data);
                // Theme manager fires ~100ms after setData. We wait 200ms to run after it.
                setTimeout(() => {
                    console.log('GraphStateManager: Re-applying styles after setData (overriding theme)');
                    self._assertCustomStyles();
                }, 250);
            };

            window.network._gsm_setdata_hooked = true;
            console.log('GraphStateManager: setData re-hooked (fires after theme)');
        },

        // Hook themeManager.apply so we re-assert custom styles after any theme change
        _hookThemeManager: function () {
            const self = this;
            const tm = window.themeManager;
            if (!tm || tm._gsm_hooked) return;

            const origApply = tm.apply.bind(tm);
            tm.apply = function (themeName) {
                origApply(themeName);
                // Theme's _batchUpdateGraphElements fires synchronously inside apply
                // Give it a tick then re-assert our custom styles on top
                setTimeout(() => {
                    console.log('GraphStateManager: Re-asserting custom styles after theme change');
                    self._assertCustomStyles();
                }, 150);
            };

            tm._gsm_hooked = true;
            console.log('GraphStateManager: themeManager.apply hooked');
        },

        // The core: apply GraphStyleControl custom styles on top of whatever theme set
        _assertCustomStyles: function () {
            if (!window.network || !window.GraphStyleControl) return;
            if (!window.GraphStyleControl.graphAddon) return;

            const nodeCount = window.network.body.data.nodes.length;
            if (nodeCount === 0) {
                console.log('GraphStateManager: assertCustomStyles skipped - no nodes');
                return;
            }

            try {
                const gsc = window.GraphStyleControl;

                // Rebuild category mappings first
                if (gsc.buildCategoryMappings) {
                    gsc.buildCategoryMappings();
                }

                const allNodes = window.network.body.data.nodes.get();
                const allEdges = window.network.body.data.edges.get();

                const styledNodes = allNodes.map(n => {
                    try {
                        const s = gsc.applyNodeStyle(n);
                        // Merge full node + style override so vis.js gets a complete update
                        return s ? { ...n, ...s } : null;
                    } catch (e) { return null; }
                }).filter(Boolean);

                const styledEdges = allEdges.map(e => {
                    try {
                        const s = gsc.applyEdgeStyle(e);
                        return s ? { ...e, ...s } : null;
                    } catch (e) { return null; }
                }).filter(Boolean);

                if (styledNodes.length) window.network.body.data.nodes.update(styledNodes);
                if (styledEdges.length) window.network.body.data.edges.update(styledEdges);

                if (gsc.updateColorLegend) gsc.updateColorLegend();

                console.log(`GraphStateManager: Custom styles asserted on ${styledNodes.length} nodes, ${styledEdges.length} edges`);
            } catch (err) {
                console.warn('GraphStateManager: _assertCustomStyles error:', err);
            }
        },

        // Try to install traps as early as possible via polling
        _installTrapsWhenReady: function () {
            const self = this;
            let attempts = 0;
            const tryInstall = () => {
                attempts++;
                if (window.GraphAdvancedFilters && !window.GraphAdvancedFilters._gsm_trapped) {
                    self._trapAdvancedFilters();
                }
                if (window.GraphStyleControl && !window.GraphStyleControl.applyAllStyles) {
                    self._shimApplyAllStyles();
                }
                if (window.network && !window.network._gsm_setdata_hooked) {
                    self._rehookSetData();
                }
                if (window.themeManager && !window.themeManager._gsm_hooked) {
                    self._hookThemeManager();
                }
                // Keep polling until all hooks installed or we give up
                const allDone = window.GraphAdvancedFilters?._gsm_trapped
                    && window.network?._gsm_setdata_hooked
                    && window.themeManager?._gsm_hooked;
                if (!allDone && attempts < 40) {
                    setTimeout(tryInstall, 200);
                }
            };
            tryInstall();
        },

        // Shim: some older code paths call applyAllStyles — install it if missing
        _shimApplyAllStyles: function () {
            const gsc = window.GraphStyleControl;
            if (!gsc || gsc.applyAllStyles) return; // already exists, nothing to do
            if (!gsc.applyNodeStyle) return; // not ready yet

            gsc.applyAllStyles = function () {
                try {
                    if (gsc.buildCategoryMappings) gsc.buildCategoryMappings();
                    if (!window.network) return;
                    const nodes = network.body.data.nodes.get();
                    const edges = network.body.data.edges.get();
                    const styledNodes = nodes.map(n => {
                        try { return { ...n, ...gsc.applyNodeStyle(n) }; } catch (e) { return n; }
                    });
                    const styledEdges = edges.map(e => {
                        try { return { ...e, ...gsc.applyEdgeStyle(e) }; } catch (e) { return e; }
                    });
                    if (styledNodes.length) network.body.data.nodes.update(styledNodes);
                    if (styledEdges.length) network.body.data.edges.update(styledEdges);
                    if (gsc.updateColorLegend) gsc.updateColorLegend();
                    if (gsc.applyFilters) gsc.applyFilters();
                } catch (e) {
                    console.warn('GraphStyleControl.applyAllStyles shim error', e);
                }
            };
            console.log('GraphStateManager: applyAllStyles shim installed on GraphStyleControl');
        },

        // ─── Animated Insert ──────────────────────────────────────────────────
        _animatedInsert: function (newNodes, newEdges, updateNodes, isDiscovery, opts) {
            const nodesDataSet = network.body.data.nodes;
            const edgesDataSet = network.body.data.edges;

            // Get parent positions for spawning near parents
            const existingPositions = {};
            try {
                nodesDataSet.forEach(node => {
                    const pos = network.getPositions([node.id])[node.id];
                    if (pos) existingPositions[node.id] = pos;
                });
            } catch (e) { /* ok */ }

            // Build parent map from edges
            const parentMap = new Map();
            const newNodeIds = new Set(newNodes.map(n => n.id));
            newEdges.forEach(edge => {
                const isNewTo = newNodeIds.has(edge.to);
                const isNewFrom = newNodeIds.has(edge.from);
                if (isNewTo && !isNewFrom) {
                    if (!parentMap.has(edge.to)) parentMap.set(edge.to, []);
                    parentMap.get(edge.to).push(edge.from);
                } else if (isNewFrom && !isNewTo) {
                    if (!parentMap.has(edge.from)) parentMap.set(edge.from, []);
                    parentMap.get(edge.from).push(edge.to);
                }
            });

            // Disable physics during animation
            const hadPhysics = network.physics.options.enabled;
            if (hadPhysics) network.setOptions({ physics: { enabled: false } });

            // Prepare nodes with starting positions near parents
            const animNodes = newNodes.map(node => {
                const n = { ...node, value: 1, opacity: 0.05 };

                if (parentMap.has(node.id)) {
                    const parents = parentMap.get(node.id);
                    const parentPositions = parents
                        .map(pid => existingPositions[pid])
                        .filter(Boolean);
                    if (parentPositions.length > 0) {
                        const avgX = parentPositions.reduce((s, p) => s + p.x, 0) / parentPositions.length;
                        const avgY = parentPositions.reduce((s, p) => s + p.y, 0) / parentPositions.length;
                        n.x = avgX + (Math.random() - 0.5) * 40;
                        n.y = avgY + (Math.random() - 0.5) * 40;
                        n.fixed = { x: false, y: false };
                    }
                }
                return n;
            });

            // Batch add
            try { nodesDataSet.add(animNodes); } catch (e) { nodesDataSet.update(animNodes); }
            if (updateNodes.length > 0) nodesDataSet.update(updateNodes);

            // Animate growth
            const duration = 700;
            const start = performance.now();

            const animate = (now) => {
                const t = Math.min((now - start) / duration, 1);
                const ease = 1 - Math.pow(1 - t, 3);

                const updates = newNodes.map(node => ({
                    id: node.id,
                    value: 1 + ((node.size || 25) - 1) * ease,
                    opacity: 0.05 + 0.95 * ease
                }));
                nodesDataSet.update(updates);

                if (t < 1) {
                    requestAnimationFrame(animate);
                } else {
                    // Finalize sizes
                    nodesDataSet.update(newNodes.map(n => ({
                        id: n.id, value: n.size || 25, opacity: 1.0
                    })));

                    // Re-enable physics
                    if (hadPhysics) {
                        const totalNodes = nodesDataSet.length;
                        const cfg = window.GraphDataLoader
                            ? window.GraphDataLoader.getPhysicsConfig(totalNodes)
                            : { enabled: true };
                        network.setOptions({ physics: cfg });
                    }

                    // Fit to new nodes
                    if (opts.focusNew !== false) {
                        setTimeout(() => {
                            network.fit({
                                nodes: newNodes.map(n => n.id),
                                animation: { duration: 800, easingFunction: 'easeInOutQuad' }
                            });
                        }, 300);
                    }

                    // Update GraphAddon
                    this._scheduleAddonRebuild();
                }
            };
            requestAnimationFrame(animate);

            // Add edges with fade
            const animEdges = newEdges.map(e => ({ ...e, color: { opacity: 0.0 }, width: 0.1 }));
            try { edgesDataSet.add(animEdges); } catch (e) { edgesDataSet.update(animEdges); }

            setTimeout(() => {
                const edgeStart = performance.now();
                const edgeDuration = 500;
                const animateEdges = (now) => {
                    const t = Math.min((now - edgeStart) / edgeDuration, 1);
                    const ease = 1 - Math.pow(1 - t, 2);
                    edgesDataSet.update(newEdges.map(e => ({
                        id: e.id,
                        color: { opacity: ease },
                        width: 0.1 + 1.9 * ease
                    })));
                    if (t < 1) requestAnimationFrame(animateEdges);
                    else edgesDataSet.update(newEdges.map(e => ({ id: e.id, color: { opacity: 1 }, width: e.width || 2 })));
                };
                requestAnimationFrame(animateEdges);
            }, 150);

            this._updateCounters(nodesDataSet.length, edgesDataSet.length);
        },

        // ─── Batch Insert ─────────────────────────────────────────────────────
        _batchInsert: function (newNodes, newEdges, updateNodes, isDiscovery) {
            const nodesDataSet = network.body.data.nodes;
            const edgesDataSet = network.body.data.edges;

            try { nodesDataSet.add(newNodes); } catch (e) { nodesDataSet.update(newNodes); }
            if (updateNodes.length > 0) nodesDataSet.update(updateNodes);
            try { edgesDataSet.add(newEdges); } catch (e) { edgesDataSet.update(newEdges); }

            this._updateCounters(nodesDataSet.length, edgesDataSet.length);
            this._scheduleAddonRebuild();
        },

        // ─── Patch VeraChat Prototypes ─────────────────────────────────────────
        /**
         * Replace VeraChat.prototype methods with GraphStateManager equivalents.
         * Called once on init. Uses a small timeout to ensure VeraChat is defined.
         */
        _patchVeraChat: function () {
            const patch = () => {
                if (typeof VeraChat === 'undefined') return;

                const self = this;

                // Patch loadGraph
                VeraChat.prototype.loadGraph = async function () {
                    return self.reload();
                };

                // Patch reloadGraph
                VeraChat.prototype.reloadGraph = async function () {
                    return self.reload();
                };

                // Patch addNodesToGraph
                VeraChat.prototype.addNodesToGraph = function (nodes, edges) {
                    return self.addNodes(nodes, edges, { animate: nodes.length < 200 });
                };

                // Patch addNodesToGraphWithWaves — delegate to addNodes
                VeraChat.prototype.addNodesToGraphWithWaves = function (nodes, edges) {
                    return self.addNodes(nodes, edges, { animate: nodes.length < 200 });
                };

                console.log('GraphStateManager: VeraChat methods patched');
            };

            // Try immediately, then retry
            patch();
            setTimeout(patch, 500);
            setTimeout(patch, 1500);
        },

        // ─── Patch Discovery Functions ─────────────────────────────────────────
        /**
         * Wrap GraphDiscovery methods so they temporarily enable discovery mode.
         * Call this after GraphDiscovery is initialized.
         */
        patchDiscovery: function () {
            if (!window.GraphDiscovery) return;

            const self = this;
            const discoveryMethods = [
                'findHiddenRelationships',
                'expandNeighbors',
                'findSimilarNodes',
                'findPaths'
            ];

            discoveryMethods.forEach(method => {
                const original = window.GraphDiscovery[method];
                if (!original) return;

                window.GraphDiscovery[method] = async function (...args) {
                    console.log(`GraphStateManager: Discovery mode ON for ${method}`);
                    self.setDiscoveryMode(true);
                    try {
                        return await original.apply(window.GraphDiscovery, args);
                    } finally {
                        self.setDiscoveryMode(false);
                        console.log(`GraphStateManager: Discovery mode OFF after ${method}`);
                    }
                };
            });

            console.log('GraphStateManager: GraphDiscovery methods patched');
        },

        // ─── Patch CypherQuery ────────────────────────────────────────────────
        /**
         * Patch CypherQuery.updateGraph to use GraphStateManager
         * so queried results still get styled + filtered properly.
         */
        patchCypherQuery: function () {
            if (!window.CypherQuery) return;

            const self = this;

            window.CypherQuery.updateGraph = function (data, replace, fit, applyLayout) {
                const rawNodes = data.nodes || [];
                const rawEdges = data.edges || [];

                if (replace) {
                    // Full replace via GraphDataLoader but with style preserved
                    if (window.GraphDataLoader) {
                        window.GraphDataLoader.loadData(rawNodes, rawEdges, {
                            replace: true,
                            fit: fit,
                            animate: rawNodes.length < 200,
                            applyLayout: applyLayout,
                            applyTheme: false,
                            updateGraphAddon: true
                        }).then(() => {
                            // After replace, restore styles and filters
                            setTimeout(() => self._restoreState(), 200);
                        });
                    }
                } else {
                    // Incremental add
                    self.addNodes(rawNodes, rawEdges, {
                        animate: rawNodes.length < 200,
                        discoveryMode: false
                    });
                }
            };

            console.log('GraphStateManager: CypherQuery.updateGraph patched');
        },

        // ─── Helpers ──────────────────────────────────────────────────────────
        _updateCounters: function (nodes, edges) {
            const nc = document.getElementById('nodeCount');
            const ec = document.getElementById('edgeCount');
            if (nc) nc.textContent = nodes;
            if (ec) ec.textContent = edges;
        },

        _scheduleAddonRebuild: function () {
            setTimeout(() => {
                if (window.GraphAddon && window.GraphAddon.networkReady) {
                    if (window.GraphAddon.buildNodesData) window.GraphAddon.buildNodesData();
                    if (window.GraphAddon.initializeFilters) window.GraphAddon.initializeFilters();
                }
                if (window.GraphStyleControl && window.GraphStyleControl.graphAddon) {
                    window.GraphStyleControl.buildCategoryMappings();
                }
            }, 100);
        },

        _scheduleFilterApply: function () {
            if (this._pendingStyleApply) clearTimeout(this._pendingStyleApply);
            this._pendingStyleApply = setTimeout(() => {
                this._restoreFilters();
                this._pendingStyleApply = null;
            }, 200);
        },

        _updateDiscoveryModeIndicator: function (enabled) {
            let indicator = document.getElementById('gsm-discovery-indicator');

            if (!enabled) {
                if (indicator) indicator.remove();
                return;
            }

            if (!indicator) {
                indicator = document.createElement('div');
                indicator.id = 'gsm-discovery-indicator';
                indicator.style.cssText = `
                    position: fixed;
                    top: 16px;
                    left: 50%;
                    transform: translateX(-50%);
                    background: rgba(245, 158, 11, 0.95);
                    color: #000;
                    padding: 6px 20px;
                    border-radius: 20px;
                    font-size: 12px;
                    font-weight: 700;
                    z-index: 99999;
                    pointer-events: none;
                    box-shadow: 0 2px 12px rgba(245,158,11,0.4);
                    letter-spacing: 0.5px;
                `;
                document.body.appendChild(indicator);
            }

            indicator.textContent = '🔭 DISCOVERY MODE — Filters suspended';
        },

    };

    // ─── Auto-init & patch sequence ───────────────────────────────────────────
    // We need to wait until all other modules are loaded before patching.
    // Use the graphModulesReady event (fired by graph-modules-init.js).

    // Patch VeraChat immediately (it retries internally)
    window.GraphStateManager.init();

    // Patch discovery + cypher after modules are ready
    window.addEventListener('graphModulesReady', () => {
        window.GraphStateManager.patchDiscovery();
        window.GraphStateManager.patchCypherQuery();
        window.GraphStateManager._shimApplyAllStyles();
        window.GraphStateManager._trapAdvancedFilters();
    });

    // Also patch if modules were already ready (late load)
    if (window.GraphDiscovery && window.GraphDiscovery.graphAddon) {
        window.GraphStateManager.patchDiscovery();
    }
    if (window.CypherQuery && window.CypherQuery.schemaLoaded) {
        window.GraphStateManager.patchCypherQuery();
    }

    console.log('GraphStateManager: Module loaded');

    // Global safety: if graph.js or anything calls GraphStyleControl.applyAllStyles
    // before GraphStyleControl is ready, queue it instead of crashing
    const _gscProxy = new Proxy({}, {
        get(target, prop) {
            const gsc = window._realGraphStyleControl;
            if (gsc) return gsc[prop];
            // Return a no-op for any method call
            return typeof prop === 'string' ? (...args) => {
                console.warn(`GraphStateManager: GraphStyleControl.${prop} called before ready, queuing`);
                setTimeout(() => {
                    if (window.GraphStyleControl && window.GraphStyleControl[prop]) {
                        window.GraphStyleControl[prop](...args);
                    }
                }, 500);
            } : undefined;
        }
    });

    // Watch for GraphStyleControl to be defined and install shim immediately
    let _gscWatchInterval = setInterval(() => {
        if (window.GraphStyleControl && !window.GraphStyleControl._gsm_shimmed) {
            if (!window.GraphStyleControl.applyAllStyles) {
                window.GraphStateManager._shimApplyAllStyles();
            }
            window.GraphStyleControl._gsm_shimmed = true;
            clearInterval(_gscWatchInterval);
        }
    }, 100);

})();