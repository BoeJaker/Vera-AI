/**
 * WorkspaceBrowser - Browse sandboxed project workspaces
 * 
 * Follows the SessionHistory pattern:
 * - Class-based component with state management
 * - Lazy loading of details/file trees
 * - Debounced updates
 * - Event delegation
 * 
 * Usage:
 *   const browser = new WorkspaceBrowser({
 *       containerId: 'workspace-browser-container',
 *       apiBaseUrl: 'http://llm.int:8888/api/workspaces',
 *   });
 *   browser.init();
 */

class WorkspaceBrowser {
    constructor(config = {}) {
        this.config = {
            containerId: config.containerId || 'workspace-browser-container',
            apiBaseUrl: config.apiBaseUrl || 'http://llm.int:8888/api/workspaces',
            onOpenFile: config.onOpenFile || null,
            onOpenTerminal: config.onOpenTerminal || null,
        };

        this.state = {
            workspaces: [],
            stats: null,
            loading: false,
            initialized: false,
            filter: 'all',       // all | active | idle | archived
            sortBy: 'last_modified',
            sortOrder: 'desc',
            tagFilter: null,
            searchQuery: '',
            // Detail view
            selectedWorkspace: null,
            selectedDetail: null,
            fileTree: null,
            fileContent: null,
            activePanel: 'overview', // overview | files | board
            // Tree expansion state
            expandedDirs: new Set(),
        };

        this.container = null;
        this.updateTimer = null;
        this.initialized = false;
        this.detailCache = new Map();
    }

    // ================================================================
    // LIFECYCLE
    // ================================================================

    async init() {
        if (this.initialized) return;

        this.container = document.getElementById(this.config.containerId);
        if (!this.container) {
            console.error(`WorkspaceBrowser: container #${this.config.containerId} not found`);
            return;
        }

        this.initialized = true;
        this.renderSkeleton();
        
        // Load in parallel
        await Promise.all([
            this.loadWorkspaces(),
            this.loadStats(),
        ]);
    }

    destroy() {
        if (this.updateTimer) clearTimeout(this.updateTimer);
        if (this.container) this.container.innerHTML = '';
        this.detailCache.clear();
        this.initialized = false;
    }

    // ================================================================
    // DATA LOADING
    // ================================================================

    async loadWorkspaces() {
        this.setState({ loading: true });

        try {
            const params = new URLSearchParams({
                sort_by: this.state.sortBy,
                sort_order: this.state.sortOrder,
            });
            if (this.state.filter !== 'all') params.append('status', this.state.filter);
            if (this.state.tagFilter) params.append('tag', this.state.tagFilter);

            const resp = await fetch(`${this.config.apiBaseUrl}?${params}`);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

            const data = await resp.json();
            this.setState({ workspaces: data, loading: false, initialized: true });
        } catch (err) {
            console.error('WorkspaceBrowser: load error', err);
            this.setState({ workspaces: [], loading: false, initialized: true });
        }
    }

    async loadStats() {
        try {
            const resp = await fetch(`${this.config.apiBaseUrl}/stats/summary`);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            this.setState({ stats: data });
        } catch (err) {
            console.error('WorkspaceBrowser: stats error', err);
        }
    }

    async loadWorkspaceDetail(workspaceId) {
        if (this.state.selectedWorkspace === workspaceId && this.state.selectedDetail) {
            // Toggle off
            this.setState({ selectedWorkspace: null, selectedDetail: null, fileTree: null, fileContent: null, activePanel: 'overview' });
            return;
        }

        // Check cache
        if (this.detailCache.has(workspaceId)) {
            this.setState({
                selectedWorkspace: workspaceId,
                selectedDetail: this.detailCache.get(workspaceId),
                fileTree: null,
                fileContent: null,
                activePanel: 'overview',
            });
            return;
        }

        try {
            const resp = await fetch(`${this.config.apiBaseUrl}/${workspaceId}`);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const detail = await resp.json();

            this.detailCache.set(workspaceId, detail);
            this.setState({
                selectedWorkspace: workspaceId,
                selectedDetail: detail,
                fileTree: null,
                fileContent: null,
                activePanel: 'overview',
            });
        } catch (err) {
            console.error('WorkspaceBrowser: detail error', err);
        }
    }

    async loadFileTree(workspaceId) {
        try {
            const resp = await fetch(`${this.config.apiBaseUrl}/${workspaceId}/tree?depth=4`);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            this.setState({ fileTree: data.tree, activePanel: 'files', fileContent: null });
        } catch (err) {
            console.error('WorkspaceBrowser: tree error', err);
        }
    }

    async loadFileContent(workspaceId, filePath) {
        try {
            const resp = await fetch(`${this.config.apiBaseUrl}/${workspaceId}/file?path=${encodeURIComponent(filePath)}`);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            this.setState({ fileContent: data });
        } catch (err) {
            console.error('WorkspaceBrowser: file read error', err);
        }
    }

    async createWorkspace(name, template) {
        try {
            const resp = await fetch(this.config.apiBaseUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, template }),
            });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            await this.loadWorkspaces();
            await this.loadStats();
        } catch (err) {
            console.error('WorkspaceBrowser: create error', err);
        }
    }

    // ================================================================
    // STATE MANAGEMENT
    // ================================================================

    setState(partial) {
        Object.assign(this.state, partial);
        if (this.updateTimer) clearTimeout(this.updateTimer);
        this.updateTimer = setTimeout(() => this.render(), 16);
    }

    // ================================================================
    // RENDERING
    // ================================================================

    renderSkeleton() {
        this.container.innerHTML = `
            <div class="ws-browser">
                <div class="ws-loading">
                    <div class="ws-loading-spinner"></div>
                    <span>Discovering workspaces...</span>
                </div>
            </div>
        `;
    }

    render() {
        if (!this.container) return;

        const { workspaces, searchQuery } = this.state;

        let filtered = workspaces;
        if (searchQuery.trim()) {
            const q = searchQuery.toLowerCase();
            filtered = workspaces.filter(w =>
                w.name.toLowerCase().includes(q) ||
                (w.focus_name && w.focus_name.toLowerCase().includes(q)) ||
                (w.tags && w.tags.some(t => t.includes(q)))
            );
        }

        // Group: active first, then idle, then archived
        const active = filtered.filter(w => w.status === 'active');
        const idle = filtered.filter(w => w.status === 'idle');
        const archived = filtered.filter(w => w.status === 'archived');

        this.container.innerHTML = `
            <div class="ws-browser">
                ${this.renderHeader()}
                ${this.state.selectedWorkspace ? this.renderDetail() : ''}
                <div class="ws-list">
                    ${active.length ? `
                        <div class="ws-group">
                            <div class="ws-group-label">
                                <span class="ws-status-dot ws-dot-active"></span>
                                Active <span class="ws-group-count">${active.length}</span>
                            </div>
                            ${active.map(w => this.renderCard(w)).join('')}
                        </div>
                    ` : ''}
                    ${idle.length ? `
                        <div class="ws-group">
                            <div class="ws-group-label">
                                <span class="ws-status-dot ws-dot-idle"></span>
                                Recent <span class="ws-group-count">${idle.length}</span>
                            </div>
                            ${idle.map(w => this.renderCard(w)).join('')}
                        </div>
                    ` : ''}
                    ${archived.length ? `
                        <div class="ws-group">
                            <div class="ws-group-label">
                                <span class="ws-status-dot ws-dot-archived"></span>
                                Archived <span class="ws-group-count">${archived.length}</span>
                            </div>
                            ${archived.map(w => this.renderCard(w)).join('')}
                        </div>
                    ` : ''}
                    ${filtered.length === 0 ? `
                        <div class="ws-empty">
                            ${searchQuery ? 'No workspaces match your search' : 'No workspaces found'}
                        </div>
                    ` : ''}
                </div>
            </div>
        `;

        this.attachListeners();
    }

    renderHeader() {
        const { stats, filter, searchQuery } = this.state;

        return `
            <div class="ws-header">
                <div class="ws-header-top">
                    <div class="ws-title-group">
                        <h2 class="ws-title">Workspaces</h2>
                        ${stats ? `
                            <div class="ws-stats-row">
                                <span class="ws-stat">${stats.total_workspaces} total</span>
                                <span class="ws-stat-sep">·</span>
                                <span class="ws-stat ws-stat-active">${stats.active_workspaces} active</span>
                                <span class="ws-stat-sep">·</span>
                                <span class="ws-stat">${stats.total_size_human}</span>
                                ${stats.workspaces_with_git ? `
                                    <span class="ws-stat-sep">·</span>
                                    <span class="ws-stat">${stats.workspaces_with_git} git</span>
                                ` : ''}
                            </div>
                        ` : ''}
                    </div>
                    <div class="ws-header-actions">
                        <button class="ws-btn ws-btn-sm" data-action="refresh" title="Refresh">↻</button>
                        <button class="ws-btn ws-btn-primary ws-btn-sm" data-action="show-create">+ New</button>
                    </div>
                </div>

                <div class="ws-toolbar">
                    <div class="ws-search-box">
                        <input type="text" class="ws-search-input" placeholder="Filter workspaces..."
                               value="${this.esc(searchQuery)}" data-action="search" />
                    </div>
                    <div class="ws-filter-pills">
                        ${['all','active','idle','archived'].map(f => `
                            <button class="ws-pill ${filter === f ? 'ws-pill-active' : ''}"
                                    data-action="filter" data-value="${f}">
                                ${f === 'all' ? 'All' : f.charAt(0).toUpperCase() + f.slice(1)}
                            </button>
                        `).join('')}
                    </div>
                </div>
            </div>
        `;
    }

    renderCard(ws) {
        const isSelected = this.state.selectedWorkspace === ws.id;
        const timeSince = this.timeSince(ws.last_modified);

        return `
            <div class="ws-card ${isSelected ? 'ws-card-selected' : ''} ws-card-${ws.status}"
                 data-action="select" data-ws-id="${ws.id}">
                <div class="ws-card-main">
                    <div class="ws-card-icon">${ws.has_focus_board ? '🎯' : ws.has_git ? '📦' : '📁'}</div>
                    <div class="ws-card-body">
                        <div class="ws-card-name">
                            ${this.esc(ws.name)}
                            ${ws.focus_name ? `<span class="ws-focus-badge">${this.esc(ws.focus_name)}</span>` : ''}
                        </div>
                        <div class="ws-card-meta">
                            <span>${ws.file_count} files</span>
                            <span class="ws-meta-sep">·</span>
                            <span>${this.humanSize(ws.total_size_bytes)}</span>
                            ${timeSince ? `
                                <span class="ws-meta-sep">·</span>
                                <span>${timeSince}</span>
                            ` : ''}
                        </div>
                        ${ws.tags && ws.tags.length ? `
                            <div class="ws-card-tags">
                                ${ws.tags.map(t => `<span class="ws-tag">${t}</span>`).join('')}
                            </div>
                        ` : ''}
                    </div>
                    <div class="ws-card-chevron">${isSelected ? '▾' : '›'}</div>
                </div>
            </div>
        `;
    }

    renderDetail() {
        const detail = this.state.selectedDetail;
        if (!detail) {
            return `<div class="ws-detail"><div class="ws-detail-loading">Loading workspace...</div></div>`;
        }

        const { activePanel } = this.state;

        return `
            <div class="ws-detail">
                <div class="ws-detail-header">
                    <div class="ws-detail-title-row">
                        <h3 class="ws-detail-name">${this.esc(detail.name)}</h3>
                        <span class="ws-detail-path">${this.esc(detail.path)}</span>
                    </div>
                    <div class="ws-detail-badges">
                        ${detail.has_git ? `
                            <span class="ws-badge ws-badge-git">
                                git: ${detail.git_branch || '?'}
                                ${detail.git_status ? ` · ${detail.git_status}` : ''}
                            </span>
                        ` : ''}
                        ${detail.has_focus_board ? `<span class="ws-badge ws-badge-focus">focus board</span>` : ''}
                        <span class="ws-badge">${detail.file_count} files · ${this.humanSize(detail.total_size_bytes)}</span>
                    </div>
                </div>

                <div class="ws-detail-tabs">
                    ${['overview','files','board'].map(p => `
                        <button class="ws-detail-tab ${activePanel === p ? 'ws-tab-active' : ''}"
                                data-action="panel" data-value="${p}"
                                ${p === 'board' && !detail.has_focus_board ? 'disabled' : ''}>
                            ${{overview: '📋 Overview', files: '📂 Files', board: '🎯 Board'}[p]}
                        </button>
                    `).join('')}
                </div>

                <div class="ws-detail-content">
                    ${activePanel === 'overview' ? this.renderOverviewPanel(detail) : ''}
                    ${activePanel === 'files' ? this.renderFilesPanel() : ''}
                    ${activePanel === 'board' ? this.renderBoardPanel(detail) : ''}
                </div>
            </div>
        `;
    }

    renderOverviewPanel(detail) {
        const { recent_files = [] } = detail;

        return `
            <div class="ws-overview">
                ${recent_files.length ? `
                    <div class="ws-section">
                        <div class="ws-section-title">Recently Modified</div>
                        <div class="ws-recent-files">
                            ${recent_files.slice(0, 10).map(f => `
                                <div class="ws-recent-file" data-action="open-file" data-path="${this.esc(f.path)}">
                                    <span class="ws-file-icon">${this.fileIcon(f.extension)}</span>
                                    <span class="ws-file-name">${this.esc(f.path)}</span>
                                    <span class="ws-file-meta">${this.humanSize(f.size)} · ${this.timeSince(f.modified)}</span>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                ` : '<div class="ws-empty-section">No recent files</div>'}
            </div>
        `;
    }

    renderFilesPanel() {
        const { fileTree, fileContent } = this.state;

        if (!fileTree) {
            return `<div class="ws-files-loading">Loading file tree...</div>`;
        }

        return `
            <div class="ws-files-layout">
                <div class="ws-tree-panel">
                    <div class="ws-tree">
                        ${this.renderTreeNodes(fileTree, '')}
                    </div>
                </div>
                <div class="ws-preview-panel">
                    ${fileContent ? this.renderFilePreview(fileContent) : `
                        <div class="ws-preview-empty">Select a file to preview</div>
                    `}
                </div>
            </div>
        `;
    }

    renderTreeNodes(nodes, parentPath) {
        if (!nodes || !nodes.length) return '';

        return nodes.map(node => {
            const fullPath = parentPath ? `${parentPath}/${node.name}` : node.name;

            if (node.type === 'dir') {
                const isExpanded = this.state.expandedDirs.has(fullPath);
                return `
                    <div class="ws-tree-dir">
                        <div class="ws-tree-item ws-tree-folder ${isExpanded ? 'ws-expanded' : ''}"
                             data-action="toggle-dir" data-path="${this.esc(fullPath)}">
                            <span class="ws-tree-arrow">${isExpanded ? '▾' : '▸'}</span>
                            <span class="ws-tree-icon">📁</span>
                            <span class="ws-tree-name">${this.esc(node.name)}</span>
                        </div>
                        ${isExpanded && node.children ? `
                            <div class="ws-tree-children">
                                ${this.renderTreeNodes(node.children, fullPath)}
                            </div>
                        ` : ''}
                    </div>
                `;
            }

            const isActive = this.state.fileContent && this.state.fileContent.path === node.path;
            return `
                <div class="ws-tree-item ws-tree-file ${isActive ? 'ws-tree-active' : ''}"
                     data-action="open-file" data-path="${this.esc(node.path)}">
                    <span class="ws-tree-icon">${this.fileIcon(node.extension)}</span>
                    <span class="ws-tree-name">${this.esc(node.name)}</span>
                    <span class="ws-tree-size">${this.humanSize(node.size)}</span>
                </div>
            `;
        }).join('');
    }

    renderFilePreview(file) {
        if (file.binary) {
            return `<div class="ws-preview-binary">Binary file: ${this.esc(file.name)} (${this.humanSize(file.size)})</div>`;
        }

        return `
            <div class="ws-preview">
                <div class="ws-preview-header">
                    <span class="ws-preview-name">${this.esc(file.path)}</span>
                    <span class="ws-preview-size">${this.humanSize(file.size)}${file.truncated ? ' (truncated)' : ''}</span>
                </div>
                <pre class="ws-preview-code"><code>${this.esc(file.content || '')}</code></pre>
            </div>
        `;
    }

    renderBoardPanel(detail) {
        const board = detail.focus_board;
        if (!board) {
            return `<div class="ws-empty-section">No focus board for this workspace</div>`;
        }

        const categories = ['progress', 'actions', 'next_steps', 'ideas', 'issues'];
        const icons = { progress: '✅', actions: '⚡', next_steps: '➡️', ideas: '💡', issues: '⚠️' };

        return `
            <div class="ws-board">
                ${categories.map(cat => {
                    const items = board[cat] || [];
                    if (!items.length) return '';
                    return `
                        <div class="ws-board-section">
                            <div class="ws-board-cat-header">
                                <span>${icons[cat] || '📌'} ${cat.replace('_', ' ')}</span>
                                <span class="ws-board-count">${items.length}</span>
                            </div>
                            <div class="ws-board-items">
                                ${items.slice(0, 8).map(item => {
                                    const text = typeof item === 'string' ? item
                                        : item.note || item.description || item.goal || JSON.stringify(item).slice(0, 120);
                                    return `<div class="ws-board-item">${this.esc(text.slice(0, 200))}</div>`;
                                }).join('')}
                                ${items.length > 8 ? `<div class="ws-board-more">+${items.length - 8} more</div>` : ''}
                            </div>
                        </div>
                    `;
                }).join('')}
            </div>
        `;
    }

    // ================================================================
    // EVENT HANDLING
    // ================================================================

    attachListeners() {
        if (!this.container) return;

        this.container.addEventListener('click', (e) => {
            const target = e.target.closest('[data-action]');
            if (!target) return;

            const action = target.dataset.action;

            switch (action) {
                case 'refresh':
                    this.detailCache.clear();
                    this.loadWorkspaces();
                    this.loadStats();
                    break;

                case 'show-create':
                    this.showCreateDialog();
                    break;

                case 'filter':
                    this.setState({ filter: target.dataset.value });
                    this.loadWorkspaces();
                    break;

                case 'select':
                    this.loadWorkspaceDetail(target.dataset.wsId);
                    break;

                case 'panel': {
                    const panel = target.dataset.value;
                    this.setState({ activePanel: panel });
                    if (panel === 'files' && !this.state.fileTree) {
                        this.loadFileTree(this.state.selectedWorkspace);
                    }
                    break;
                }

                case 'toggle-dir': {
                    const path = target.dataset.path;
                    const expanded = new Set(this.state.expandedDirs);
                    if (expanded.has(path)) expanded.delete(path);
                    else expanded.add(path);
                    this.setState({ expandedDirs: expanded });
                    break;
                }

                case 'open-file':
                    this.loadFileContent(this.state.selectedWorkspace, target.dataset.path);
                    break;
            }
        });

        // Search input
        const searchInput = this.container.querySelector('[data-action="search"]');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.setState({ searchQuery: e.target.value });
            });
        }
    }

    showCreateDialog() {
        const name = prompt('Workspace name:');
        if (!name) return;

        const template = prompt('Template (empty/python/node):', 'empty') || 'empty';
        this.createWorkspace(name, template);
    }

    // ================================================================
    // UTILITIES
    // ================================================================

    esc(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = String(text);
        return div.innerHTML;
    }

    humanSize(bytes) {
        if (!bytes || bytes === 0) return '0 B';
        const units = ['B', 'KB', 'MB', 'GB'];
        let i = 0;
        let size = bytes;
        while (size >= 1024 && i < units.length - 1) { size /= 1024; i++; }
        return `${size.toFixed(i > 0 ? 1 : 0)} ${units[i]}`;
    }

    timeSince(iso) {
        if (!iso) return '';
        try {
            const ms = Date.now() - new Date(iso).getTime();
            const mins = Math.floor(ms / 60000);
            if (mins < 60) return `${mins}m ago`;
            const hrs = Math.floor(ms / 3600000);
            if (hrs < 24) return `${hrs}h ago`;
            const days = Math.floor(ms / 86400000);
            if (days < 30) return `${days}d ago`;
            return new Date(iso).toLocaleDateString();
        } catch { return ''; }
    }

    fileIcon(ext) {
        const icons = {
            '.py': '🐍', '.js': '📜', '.ts': '📘', '.jsx': '⚛️', '.tsx': '⚛️',
            '.json': '📋', '.yaml': '📋', '.yml': '📋', '.md': '📝',
            '.html': '🌐', '.css': '🎨', '.sh': '🖥️', '.sql': '🗃️',
            '.rs': '🦀', '.go': '🔵', '.java': '☕', '.rb': '💎',
            '.txt': '📄', '.log': '📄', '.env': '🔒', '.toml': '⚙️',
            '.dockerfile': '🐳',
        };
        return icons[ext] || '📄';
    }
}

// Export
if (typeof module !== 'undefined' && module.exports) {
    module.exports = WorkspaceBrowser;
}