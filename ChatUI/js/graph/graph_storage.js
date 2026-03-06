/**
 * GraphStorage Module
 * Save and restore complete graph views: nodes, edges, positions, styles, filters, zoom
 * Integrated with GraphInfoCard for inline display
 */

(() => {
    'use strict';

    // ─── Core Storage Utilities ───────────────────────────────────────────────

    window.graphStorageUtils = {

        /**
         * Capture the full current graph state
         */
        captureState: function() {
            if (!window.network) {
                throw new Error('No network available');
            }

            const net = window.network;

            // Node positions + full data
            const allNodes = net.body.data.nodes.get();
            const positions = net.getPositions();

            const nodes = allNodes.map(node => ({
                ...node,
                x: positions[node.id]?.x ?? node.x,
                y: positions[node.id]?.y ?? node.y,
            }));

            // Edges
            const edges = net.body.data.edges.get();

            // Viewport
            const viewPosition = net.getViewPosition();
            const scale = net.getScale();

            // Physics options
            const physicsEnabled = net.physics?.options?.enabled ?? true;

            // Style state from GraphStyleControl
            let styleState = null;
            if (window.GraphStyleControl) {
                try {
                    styleState = {
                        nodeColorMode: GraphStyleControl.nodeColorMode,
                        nodeSizeMode: GraphStyleControl.nodeSizeMode,
                        edgeColorMode: GraphStyleControl.edgeColorMode,
                        categoryColors: { ...(GraphStyleControl.categoryColors || {}) },
                        sessionViewEnabled: GraphStyleControl.sessionViewEnabled,
                        sessionViewMode: GraphStyleControl.sessionViewMode,
                    };
                } catch (e) {
                    console.warn('GraphStorage: Could not capture style state', e);
                }
            }

            // Filter state from GraphAdvancedFilters
            let filterState = null;
            if (window.GraphAdvancedFilters?.filters) {
                try {
                    filterState = JSON.parse(JSON.stringify(GraphAdvancedFilters.filters));
                } catch (e) {
                    console.warn('GraphStorage: Could not capture filter state', e);
                }
            }

            // Network options (edges smooth, node font, etc.)
            let networkOptions = null;
            try {
                networkOptions = {
                    edges: {
                        smooth: net.body.options?.edges?.smooth,
                        width: net.body.options?.edges?.width,
                    },
                    nodes: {
                        font: net.body.options?.nodes?.font,
                        size: net.body.options?.nodes?.size,
                    },
                };
            } catch (e) {}

            return {
                version: 2,
                timestamp: Date.now(),
                sessionId: window.app?.sessionId || null,
                nodes,
                edges,
                viewport: { x: viewPosition.x, y: viewPosition.y, scale },
                physicsEnabled,
                styleState,
                filterState,
                networkOptions,
                meta: {
                    nodeCount: nodes.length,
                    edgeCount: edges.length,
                },
            };
        },

        /**
         * Save state to localStorage
         */
        saveToLocal: function(name) {
            if (!name || !name.trim()) throw new Error('Name required');
            const key = 'graphview_' + name.trim();
            const state = this.captureState();
            state.name = name.trim();
            localStorage.setItem(key, JSON.stringify(state));
            console.log(`GraphStorage: Saved "${name}" (${state.meta.nodeCount} nodes, ${state.meta.edgeCount} edges)`);
            return state;
        },

        /**
         * Load state from localStorage
         */
        loadFromLocal: function(name) {
            const key = 'graphview_' + name;
            const raw = localStorage.getItem(key);
            if (!raw) throw new Error(`No saved graph found: "${name}"`);
            return JSON.parse(raw);
        },

        /**
         * List all saved graphs
         */
        listSaved: function() {
            return Object.keys(localStorage)
                .filter(k => k.startsWith('graphview_'))
                .map(k => {
                    try {
                        const data = JSON.parse(localStorage.getItem(k));
                        return {
                            key: k,
                            name: data.name || k.replace('graphview_', ''),
                            timestamp: data.timestamp || 0,
                            nodeCount: data.meta?.nodeCount || 0,
                            edgeCount: data.meta?.edgeCount || 0,
                            sessionId: data.sessionId || null,
                        };
                    } catch (e) {
                        return {
                            key: k,
                            name: k.replace('graphview_', ''),
                            timestamp: 0,
                            nodeCount: 0,
                            edgeCount: 0,
                        };
                    }
                })
                .sort((a, b) => b.timestamp - a.timestamp);
        },

        /**
         * Delete a saved graph
         */
        deleteSaved: function(name) {
            localStorage.removeItem('graphview_' + name);
        },

        /**
         * Restore a graph state into the live network
         */
        restoreState: function(state) {
            if (!window.network) throw new Error('No network available');
            if (!state || !state.nodes) throw new Error('Invalid state');

            const net = window.network;

            // 1. Disable physics for controlled restore
            net.setOptions({ physics: { enabled: false } });

            // 2. Load nodes + edges
            net.setData({
                nodes: state.nodes,
                edges: state.edges,
            });

            // 3. Restore positions explicitly (setData may not preserve them)
            const posUpdates = state.nodes
                .filter(n => n.x !== undefined && n.y !== undefined)
                .map(n => ({ id: n.id, x: n.x, y: n.y }));

            if (posUpdates.length > 0) {
                net.body.data.nodes.update(posUpdates);
            }

            // 4. Restore viewport
            if (state.viewport) {
                setTimeout(() => {
                    net.moveTo({
                        position: { x: state.viewport.x, y: state.viewport.y },
                        scale: state.viewport.scale,
                        animation: { duration: 600, easingFunction: 'easeInOutQuad' },
                    });
                }, 50);
            }

            // 5. Restore physics state
            setTimeout(() => {
                net.setOptions({ physics: { enabled: state.physicsEnabled ?? true } });
            }, 100);

            // 6. Restore styles
            if (state.styleState && window.GraphStyleControl) {
                try {
                    const gsc = GraphStyleControl;
                    if (state.styleState.categoryColors) {
                        gsc.categoryColors = { ...state.styleState.categoryColors };
                    }
                    if (state.styleState.nodeColorMode !== undefined) {
                        gsc.nodeColorMode = state.styleState.nodeColorMode;
                    }
                    if (state.styleState.nodeSizeMode !== undefined) {
                        gsc.nodeSizeMode = state.styleState.nodeSizeMode;
                    }
                    setTimeout(() => {
                        if (gsc.applyAllStyles) gsc.applyAllStyles();
                    }, 200);
                } catch (e) {
                    console.warn('GraphStorage: Style restore failed', e);
                }
            }

            // 7. Restore filters
            if (state.filterState && window.GraphAdvancedFilters) {
                try {
                    GraphAdvancedFilters.filters = JSON.parse(JSON.stringify(state.filterState));
                    setTimeout(() => {
                        if (GraphAdvancedFilters.applyAllFilters) {
                            GraphAdvancedFilters.applyAllFilters();
                        }
                    }, 300);
                } catch (e) {
                    console.warn('GraphStorage: Filter restore failed', e);
                }
            }

            // 8. Update GraphAddon data
            if (window.GraphAddon?.networkReady) {
                setTimeout(() => {
                    if (GraphAddon.buildNodesData) GraphAddon.buildNodesData();
                    if (GraphAddon.initializeFilters) GraphAddon.initializeFilters();
                }, 400);
            }

            // 9. Update counters
            const nodeCountEl = document.getElementById('nodeCount');
            const edgeCountEl = document.getElementById('edgeCount');
            if (nodeCountEl) nodeCountEl.textContent = state.nodes.length;
            if (edgeCountEl) edgeCountEl.textContent = state.edges.length;

            // 10. Fire event for GraphStateManager
            setTimeout(() => {
                window.dispatchEvent(new CustomEvent('graphModulesReady'));
            }, 500);

            console.log(`GraphStorage: Restored "${state.name}" (${state.nodes.length} nodes)`);
        },

        /**
         * Export state as downloadable JSON file
         */
        exportToFile: function(name) {
            const state = this.captureState();
            state.name = name || 'graph_export';
            const blob = new Blob([JSON.stringify(state, null, 2)], { type: 'application/json' });
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = `${state.name}_${new Date().toISOString().slice(0, 10)}.json`;
            link.click();
        },

        /**
         * Import state from JSON file
         */
        importFromFile: function(callback) {
            const input = document.createElement('input');
            input.type = 'file';
            input.accept = '.json';
            input.onchange = (e) => {
                const file = e.target.files[0];
                if (!file) return;
                const reader = new FileReader();
                reader.onload = (ev) => {
                    try {
                        const state = JSON.parse(ev.target.result);
                        if (callback) callback(null, state);
                    } catch (err) {
                        if (callback) callback(err, null);
                    }
                };
                reader.readAsText(file);
            };
            input.click();
        },

        /**
         * Format timestamp for display
         */
        formatTime: function(ts) {
            if (!ts) return 'Unknown';
            const d = new Date(ts);
            const now = new Date();
            const diffMs = now - d;
            const diffMins = Math.floor(diffMs / 60000);
            const diffHours = Math.floor(diffMs / 3600000);
            const diffDays = Math.floor(diffMs / 86400000);

            if (diffMins < 1) return 'Just now';
            if (diffMins < 60) return `${diffMins}m ago`;
            if (diffHours < 24) return `${diffHours}h ago`;
            if (diffDays < 7) return `${diffDays}d ago`;
            return d.toLocaleDateString();
        },
    };

    // ─── GraphInfoCard Integration ────────────────────────────────────────────

    window.GraphStorageCard = {

        _saveName: '',

        /**
         * Show storage panel inside GraphInfoCard
         */
        showInCard: function() {
            if (!window.GraphInfoCard) {
                console.error('GraphInfoCard not available');
                return;
            }

            const saved = graphStorageUtils.listSaved();
            const content = this._buildMainContent(saved);

            window.GraphInfoCard.inlineMode = true;
            window.GraphInfoCard.isExpanded = true;
            window.GraphInfoCard.showInlineContent('💾 Graph Storage', content);

            // Focus name input after render
            setTimeout(() => {
                const input = document.getElementById('gs-save-name');
                if (input) input.focus();
            }, 100);
        },

        /**
         * Build the main storage panel HTML
         */
        _buildMainContent: function(saved) {
            const isEmpty = saved.length === 0;

            return `
            <div style="display: flex; flex-direction: column; gap: 0;">

                <!-- SAVE SECTION -->
                <div style="
                    background: rgba(16, 185, 129, 0.08);
                    border: 1px solid rgba(16, 185, 129, 0.25);
                    border-radius: 10px;
                    padding: 14px;
                    margin-bottom: 14px;
                ">
                    <div style="
                        color: #10b981;
                        font-size: 11px;
                        font-weight: 700;
                        text-transform: uppercase;
                        letter-spacing: 0.8px;
                        margin-bottom: 10px;
                    ">Save Current View</div>

                    <div style="display: flex; gap: 8px; align-items: center;">
                        <input
                            id="gs-save-name"
                            type="text"
                            placeholder="View name..."
                            autocomplete="off"
                            style="
                                flex: 1;
                                padding: 9px 12px;
                                background: #0f172a;
                                color: #e2e8f0;
                                border: 1px solid #334155;
                                border-radius: 7px;
                                font-size: 13px;
                                outline: none;
                            "
                            onfocus="this.style.borderColor='#10b981'"
                            onblur="this.style.borderColor='#334155'"
                            onkeydown="if(event.key==='Enter') window.GraphStorageCard._doSave()"
                        >
                        <button
                            onclick="window.GraphStorageCard._doSave()"
                            style="
                                padding: 9px 14px;
                                background: #10b981;
                                color: #fff;
                                border: none;
                                border-radius: 7px;
                                cursor: pointer;
                                font-size: 13px;
                                font-weight: 600;
                                white-space: nowrap;
                            "
                            onmouseover="this.style.background='#059669'"
                            onmouseout="this.style.background='#10b981'"
                        >💾 Save</button>
                    </div>

                    <!-- Import from file -->
                    <div style="margin-top: 8px; text-align: right;">
                        <button
                            onclick="window.GraphStorageCard._doImport()"
                            style="
                                padding: 5px 10px;
                                background: transparent;
                                color: #64748b;
                                border: 1px solid #334155;
                                border-radius: 5px;
                                cursor: pointer;
                                font-size: 11px;
                            "
                            onmouseover="this.style.color='#94a3b8'; this.style.borderColor='#475569'"
                            onmouseout="this.style.color='#64748b'; this.style.borderColor='#334155'"
                        >📂 Import from file</button>
                    </div>
                </div>

                <!-- SAVED VIEWS LIST -->
                <div>
                    <div style="
                        display: flex;
                        align-items: center;
                        justify-content: space-between;
                        margin-bottom: 10px;
                    ">
                        <div style="
                            color: #94a3b8;
                            font-size: 11px;
                            font-weight: 700;
                            text-transform: uppercase;
                            letter-spacing: 0.8px;
                        ">Saved Views</div>
                        <div style="color: #475569; font-size: 11px;">
                            ${saved.length} saved
                        </div>
                    </div>

                    <div id="gs-saved-list" style="
                        display: flex;
                        flex-direction: column;
                        gap: 8px;
                        max-height: 340px;
                        overflow-y: auto;
                        padding-right: 2px;
                    ">
                        ${isEmpty
                            ? `<div style="
                                text-align: center;
                                padding: 40px 20px;
                                color: #475569;
                                font-size: 13px;
                            ">
                                <div style="font-size: 32px; margin-bottom: 10px; opacity: 0.4;">🗂️</div>
                                No saved views yet.<br>
                                <span style="font-size: 12px; color: #334155;">Save your current graph above.</span>
                            </div>`
                            : saved.map(s => this._buildSavedItem(s)).join('')
                        }
                    </div>
                </div>

            </div>
            `;
        },

        /**
         * Build HTML for a single saved view row
         */
        _buildSavedItem: function(s) {
            const timeStr = graphStorageUtils.formatTime(s.timestamp);
            const safeKey = s.name.replace(/'/g, "\\'");

            return `
            <div
                id="gs-item-${CSS.escape(s.name)}"
                style="
                    background: #0f172a;
                    border: 1px solid #1e293b;
                    border-radius: 9px;
                    padding: 12px 14px;
                    transition: border-color 0.15s;
                "
                onmouseover="this.style.borderColor='#334155'"
                onmouseout="this.style.borderColor='#1e293b'"
            >
                <!-- Top row: name + badges -->
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px; flex-wrap: wrap;">
                    <div style="
                        color: #e2e8f0;
                        font-size: 13px;
                        font-weight: 600;
                        flex: 1;
                        min-width: 0;
                        white-space: nowrap;
                        overflow: hidden;
                        text-overflow: ellipsis;
                    " title="${this._esc(s.name)}">${this._esc(s.name)}</div>
                    <span style="
                        padding: 2px 7px;
                        background: rgba(96, 165, 250, 0.15);
                        color: #60a5fa;
                        border-radius: 10px;
                        font-size: 10px;
                        white-space: nowrap;
                    ">${s.nodeCount}n · ${s.edgeCount}e</span>
                </div>

                <!-- Time -->
                <div style="color: #475569; font-size: 11px; margin-bottom: 10px;">${timeStr}</div>

                <!-- Action buttons -->
                <div style="display: flex; gap: 6px;">
                    <button
                        onclick="window.GraphStorageCard._doLoad('${safeKey}')"
                        style="
                            flex: 1;
                            padding: 7px;
                            background: #3b82f6;
                            color: #fff;
                            border: none;
                            border-radius: 6px;
                            cursor: pointer;
                            font-size: 12px;
                            font-weight: 600;
                        "
                        onmouseover="this.style.background='#2563eb'"
                        onmouseout="this.style.background='#3b82f6'"
                    >↩ Load</button>

                    <button
                        onclick="window.GraphStorageCard._doOverwrite('${safeKey}')"
                        style="
                            padding: 7px 10px;
                            background: transparent;
                            color: #94a3b8;
                            border: 1px solid #334155;
                            border-radius: 6px;
                            cursor: pointer;
                            font-size: 12px;
                        "
                        onmouseover="this.style.color='#e2e8f0'; this.style.borderColor='#475569'"
                        onmouseout="this.style.color='#94a3b8'; this.style.borderColor='#334155'"
                        title="Overwrite with current graph"
                    >↑ Update</button>

                    <button
                        onclick="window.GraphStorageCard._doExportOne('${safeKey}')"
                        style="
                            padding: 7px 10px;
                            background: transparent;
                            color: #94a3b8;
                            border: 1px solid #334155;
                            border-radius: 6px;
                            cursor: pointer;
                            font-size: 12px;
                        "
                        onmouseover="this.style.color='#e2e8f0'; this.style.borderColor='#475569'"
                        onmouseout="this.style.color='#94a3b8'; this.style.borderColor='#334155'"
                        title="Export as JSON file"
                    >⬇</button>

                    <button
                        onclick="window.GraphStorageCard._doDelete('${safeKey}')"
                        style="
                            padding: 7px 10px;
                            background: transparent;
                            color: #ef4444;
                            border: 1px solid rgba(239, 68, 68, 0.3);
                            border-radius: 6px;
                            cursor: pointer;
                            font-size: 12px;
                        "
                        onmouseover="this.style.background='rgba(239,68,68,0.1)'"
                        onmouseout="this.style.background='transparent'"
                        title="Delete this view"
                    >✕</button>
                </div>
            </div>
            `;
        },

        /**
         * Save current state with name from input
         */
        _doSave: function() {
            const input = document.getElementById('gs-save-name');
            const name = input ? input.value.trim() : '';
            if (!name) {
                this._flash(input, '#ef4444');
                return;
            }

            try {
                graphStorageUtils.saveToLocal(name);
                if (input) input.value = '';
                this._toast(`✓ Saved "${name}"`);
                this._refreshList();
            } catch (e) {
                this._toast(`✗ Save failed: ${e.message}`, true);
            }
        },

        /**
         * Load a saved view
         */
        _doLoad: function(name) {
            try {
                const state = graphStorageUtils.loadFromLocal(name);
                graphStorageUtils.restoreState(state);
                this._toast(`✓ Loaded "${name}"`);
                // Stay open so user can switch views easily
            } catch (e) {
                this._toast(`✗ Load failed: ${e.message}`, true);
            }
        },

        /**
         * Overwrite existing save with current graph
         */
        _doOverwrite: function(name) {
            try {
                graphStorageUtils.saveToLocal(name);
                this._toast(`✓ Updated "${name}"`);
                this._refreshList();
            } catch (e) {
                this._toast(`✗ Update failed: ${e.message}`, true);
            }
        },

        /**
         * Export one saved view to file
         */
        _doExportOne: function(name) {
            try {
                const state = graphStorageUtils.loadFromLocal(name);
                const blob = new Blob([JSON.stringify(state, null, 2)], { type: 'application/json' });
                const link = document.createElement('a');
                link.href = URL.createObjectURL(blob);
                link.download = `${name}_${new Date().toISOString().slice(0, 10)}.json`;
                link.click();
                this._toast(`⬇ Exporting "${name}"`);
            } catch (e) {
                this._toast(`✗ Export failed: ${e.message}`, true);
            }
        },

        /**
         * Delete a saved view
         */
        _doDelete: function(name) {
            graphStorageUtils.deleteSaved(name);
            this._toast(`Deleted "${name}"`);
            this._refreshList();
        },

        /**
         * Import from JSON file
         */
        _doImport: function() {
            graphStorageUtils.importFromFile((err, state) => {
                if (err) {
                    this._toast(`✗ Import failed: ${err.message}`, true);
                    return;
                }
                if (!state || !state.nodes) {
                    this._toast('✗ Invalid graph file', true);
                    return;
                }

                // Save it locally first
                const importName = state.name || `imported_${Date.now()}`;
                const key = 'graphview_' + importName;
                localStorage.setItem(key, JSON.stringify({ ...state, name: importName }));

                this._toast(`✓ Imported "${importName}"`);
                this._refreshList();

                // Ask if they want to restore it now
                setTimeout(() => {
                    if (confirm(`Restore imported graph "${importName}" now?`)) {
                        graphStorageUtils.restoreState(state);
                    }
                }, 200);
            });
        },

        /**
         * Refresh the list without full re-render
         */
        _refreshList: function() {
            const container = document.getElementById('gs-saved-list');
            if (!container) {
                // Full re-render if list container gone
                this.showInCard();
                return;
            }

            const saved = graphStorageUtils.listSaved();

            if (saved.length === 0) {
                container.innerHTML = `
                    <div style="
                        text-align: center;
                        padding: 40px 20px;
                        color: #475569;
                        font-size: 13px;
                    ">
                        <div style="font-size: 32px; margin-bottom: 10px; opacity: 0.4;">🗂️</div>
                        No saved views yet.
                    </div>
                `;
            } else {
                container.innerHTML = saved.map(s => this._buildSavedItem(s)).join('');
            }
        },

        /**
         * Flash an input red briefly on error
         */
        _flash: function(el, color) {
            if (!el) return;
            el.style.borderColor = color;
            el.focus();
            setTimeout(() => { el.style.borderColor = '#334155'; }, 1000);
        },

        /**
         * Show toast notification inside the card area
         */
        _toast: function(msg, isError = false) {
            // Remove any existing toast
            document.querySelectorAll('.gs-toast').forEach(t => t.remove());

            const toast = document.createElement('div');
            toast.className = 'gs-toast';
            toast.textContent = msg;
            toast.style.cssText = `
                position: fixed;
                bottom: 24px;
                left: 50%;
                transform: translateX(-50%);
                z-index: 99999;
                padding: 10px 20px;
                background: ${isError ? '#7f1d1d' : '#064e3b'};
                color: ${isError ? '#fca5a5' : '#6ee7b7'};
                border: 1px solid ${isError ? '#ef4444' : '#10b981'};
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
                box-shadow: 0 4px 20px rgba(0,0,0,0.4);
                pointer-events: none;
                transition: opacity 0.3s;
            `;
            document.body.appendChild(toast);
            setTimeout(() => {
                toast.style.opacity = '0';
                setTimeout(() => toast.remove(), 300);
            }, 2200);
        },

        /**
         * Safe HTML escape
         */
        _esc: function(text) {
            const d = document.createElement('div');
            d.textContent = String(text);
            return d.innerHTML;
        },
    };

    // ─── Convenience global opener ────────────────────────────────────────────

    window.showGraphStorageMenu = function() {
        window.GraphStorageCard.showInCard();
    };

    console.log('GraphStorage module loaded');
})();