(() => {
    // ============================================================
    // FOCUS LAYOUT V2 — v2.3  (theme-integrated)
    //
    // Changes from v2.2:
    // - All hardcoded hex/rgba colours in the stylesheet replaced
    //   with var(--vera-*) CSS custom properties written by the
    //   Vera theme system (ThemeManager).  No other changes.
    // - Fallback values keep the original default-dark palette so
    //   the component still renders correctly if ThemeManager is
    //   absent or hasn't run yet.
    // - JS logic is 100% identical to v2.2.
    // ============================================================

    document.getElementById('focus-layout-v2-styles')?.remove();

    const layoutStyle = document.createElement('style');
    layoutStyle.id = 'focus-layout-v2-styles';
    layoutStyle.textContent = `
        /* ═══ LAYOUT SHELL ════════════════════════════════════════ */
        #focus-layout-v2 {
            display: flex;
            flex-direction: column;
            height: 100%;
            overflow: hidden;
            font-family: var(--vera-font, 'SF Mono','Cascadia Code','Fira Code','JetBrains Mono',monospace);
            position: relative;
            transition: background .3s ease, color .3s ease;
        }

        /* ── Control bar ── */
        #fl2-control-bar {
            display: flex; flex-wrap: wrap; gap: 6px;
            justify-content: space-between; align-items: center;
            padding: 8px 12px;
            background: linear-gradient(180deg, var(--vera-bg, rgba(13,17,23,.97)), var(--vera-surface, rgba(15,23,42,.92)));
            border-bottom: 1px solid var(--vera-border, #1e2d3d);
            flex-shrink: 0; z-index: 10;
        }
        #fl2-control-bar .fl2-btn-group {
            display: flex; flex-wrap: wrap; gap: 5px; align-items: center;
        }
        .fl2-ctrl-btn {
            padding: 5px 11px;
            background: var(--vera-surface2, rgba(30,41,59,.7));
            border: 1px solid var(--vera-border, #283548); border-radius: 5px;
            color: var(--vera-text-muted, #8b9cb8); font-size: 11px; font-weight: 600;
            cursor: pointer; transition: all .15s;
            font-family: inherit; letter-spacing: .02em; white-space: nowrap;
        }
        .fl2-ctrl-btn:hover {
            background: var(--vera-blue-tint, rgba(59,130,246,.15));
            border-color: var(--vera-blue-dim, #3b6fd4);
            color: var(--vera-text, #c8d6e5);
        }
        .fl2-ctrl-btn.active {
            background: var(--vera-green-tint, rgba(16,185,129,.25));
            border-color: var(--vera-green, #10b981);
            color: var(--vera-green, #6ee7b7);
        }
        .fl2-ctrl-btn.danger:hover {
            background: var(--vera-red-tint, rgba(239,68,68,.15));
            border-color: var(--vera-red, #ef4444);
            color: var(--vera-red, #fca5a5);
        }
        .fl2-status-pill {
            padding: 4px 10px; border-radius: 4px;
            font-size: 10px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase;
        }
        .fl2-status-pill.running {
            background: var(--vera-green-tint, rgba(16,185,129,.2));
            color: var(--vera-green, #6ee7b7);
            border: 1px solid var(--vera-green-tint, rgba(16,185,129,.3));
        }
        .fl2-status-pill.stopped {
            background: var(--vera-surface2, rgba(107,114,128,.2));
            color: var(--vera-text-muted, #6b7280);
            border: 1px solid var(--vera-border, rgba(107,114,128,.3));
        }

        /* ── Focus bar ── */
        #fl2-focus-bar {
            display: flex; align-items: center; gap: 10px;
            padding: 7px 14px;
            background: var(--vera-purple-tint, rgba(139,92,246,.06));
            border-bottom: 1px solid var(--vera-purple-tint, rgba(139,92,246,.15));
            border-left: 3px solid var(--vera-purple, #8b5cf6);
            flex-shrink: 0;
        }
        #fl2-focus-bar .fl2-focus-label {
            color: var(--vera-text-muted, #64748b); font-size: 10px; font-weight: 700;
            letter-spacing: .1em; text-transform: uppercase;
        }
        #fl2-focus-bar .fl2-focus-text {
            color: var(--vera-purple, #a78bfa); font-size: 14px; font-weight: 700;
            flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
        }
        #fl2-focus-bar .fl2-focus-actions { display:flex; gap:5px; flex-shrink:0; }

        /* ═══ MAIN SPLIT ═══════════════════════════════════════════ */
        #fl2-split {
            display: flex; flex: 1; overflow: hidden;
            min-height: 0; position: relative;
        }

        /* ── Left: Status monitor ── */
        #fl2-left {
            width: 320px; min-width: 200px; max-width: 600px;
            display: flex; flex-direction: column;
            background: var(--vera-bg, rgba(10,14,20,.6));
            overflow-y: auto; flex-shrink: 0;
        }
        #fl2-left.fl2-left-hidden { display: none; }

        #fl2-left-header {
            display: flex; align-items: center; justify-content: space-between;
            padding: 7px 10px;
            background: var(--vera-surface, rgba(17,24,39,.9));
            border-bottom: 1px solid var(--vera-border, #1e2d3d);
            position: sticky; top: 0; z-index: 5; flex-shrink: 0;
        }
        #fl2-left-header .fl2-section-title {
            font-size: 10px; font-weight: 700;
            letter-spacing: .1em; text-transform: uppercase;
            color: var(--vera-text-muted, #475569); white-space: nowrap;
        }
        .fl2-left-toggle {
            background: none; border: 1px solid var(--vera-border, #283548);
            color: var(--vera-text-muted, #64748b); font-size: 11px; padding: 2px 7px;
            border-radius: 4px; cursor: pointer; font-family: inherit;
        }
        .fl2-left-toggle:hover {
            background: var(--vera-blue-tint, rgba(59,130,246,.1));
            border-color: var(--vera-blue-dim, #3b6fd4);
            color: var(--vera-blue, #93c5fd);
        }

        /* Panels inside left column */
        #fl2-left .pf-panel {
            border-radius: 0; border-left: none; border-right: none;
            margin-bottom: 0; border-bottom: 1px solid var(--vera-bg, #0f1923);
        }

        /* ── Resize handle ── */
        #fl2-resize-handle {
            width: 5px; flex-shrink: 0; cursor: col-resize;
            background: transparent;
            border-right: 1px solid var(--vera-border, #1e2d3d);
            position: relative; z-index: 20; transition: background .15s;
        }
        #fl2-resize-handle:hover,
        #fl2-resize-handle.dragging {
            background: var(--vera-blue-tint, rgba(59,130,246,.35));
            border-right-color: var(--vera-blue, #3b82f6);
        }

        /* ── Right: Focus board — three states ── */
        #fl2-right { flex:1; display:flex; flex-direction:column; overflow:hidden; min-width:0; }

        /* State 1 — sidebar: vertical icon tabs only */
        #fl2-right.fl2-sidebar {
            width: 48px; min-width: 48px; max-width: 48px; flex: none;
        }
        #fl2-right.fl2-sidebar #fl2-tab-bar {
            flex-direction: column; border-bottom: none;
            border-right: 1px solid var(--vera-border, #1e2d3d);
            overflow-x: visible; overflow-y: auto; height: 100%;
            width: 48px;
        }
        #fl2-right.fl2-sidebar .fl2-tab {
            padding: 10px 0; width: 48px;
            justify-content: center; flex-direction: column;
            gap: 2px; margin-bottom: 0;
            border-bottom: none; border-right: 2px solid transparent;
            border-left: none;
        }
        #fl2-right.fl2-sidebar .fl2-tab .fl2-tab-label { display: none; }
        #fl2-right.fl2-sidebar .fl2-tab .fl2-tab-dot   { display: none; }
        #fl2-right.fl2-sidebar .fl2-tab .fl2-tab-icon  { font-size: 15px; }
        #fl2-right.fl2-sidebar .fl2-tab .fl2-tab-count { font-size: 9px !important; color: var(--vera-text-dim, #374151); }
        #fl2-right.fl2-sidebar .fl2-tab.active { border-right-color: var(--vera-blue, #3b82f6); border-bottom: none; }
        #fl2-right.fl2-sidebar .fl2-tab.active .fl2-tab-count { color: var(--vera-blue, #60a5fa); }
        #fl2-right.fl2-sidebar #fl2-tab-content { display: none; }

        /* State 2 — fully hidden */
        #fl2-right.fl2-hidden { display: none; }

        /* Floating restore button (visible when board is hidden) */
        #fl2-restore-btn {
            display: none;
            position: absolute; right: 0; top: 0; bottom: 0;
            z-index: 50; width: 22px;
            background: var(--vera-surface, rgba(15,23,42,.92));
            border: none; border-left: 1px solid var(--vera-blue, #3b82f6);
            color: var(--vera-blue, #60a5fa); font-size: 10px; font-weight: 700;
            cursor: pointer; writing-mode: vertical-rl;
            text-orientation: mixed; letter-spacing: .1em;
            padding: 12px 0;
            transition: background .15s;
        }
        #fl2-restore-btn:hover {
            background: var(--vera-blue-tint, rgba(59,130,246,.2));
            color: var(--vera-blue, #93c5fd);
        }
        #fl2-split.board-hidden #fl2-restore-btn { display: block; }

        /* ── Tab bar ── */
        #fl2-tab-bar {
            display: flex; border-bottom: 2px solid var(--vera-border, #1e2d3d);
            background: var(--vera-surface, rgba(15,23,42,.5));
            flex-shrink: 0; overflow-x: auto; scrollbar-width: none;
        }
        #fl2-tab-bar::-webkit-scrollbar { display: none; }
        .fl2-tab {
            padding: 7px 12px; background: transparent;
            border: none; border-bottom: 2px solid transparent;
            color: var(--vera-text-muted, #64748b); font-size: 11.5px; font-weight: 600;
            cursor: pointer; transition: all .15s;
            display: flex; align-items: center; gap: 4px;
            white-space: nowrap; margin-bottom: -2px; font-family: inherit;
        }
        .fl2-tab:hover {
            color: var(--vera-text-muted, #94a3b8);
            background: var(--vera-surface2, rgba(30,41,59,.4));
        }
        .fl2-tab.active {
            color: var(--vera-text, #e2e8f0);
            border-bottom-color: var(--vera-blue, #3b82f6);
            background: var(--vera-blue-tint, rgba(59,130,246,.06));
        }
        .fl2-tab .fl2-tab-count { font-size:10px; color: var(--vera-text-dim, #374151); font-weight:400; }
        .fl2-tab.active .fl2-tab-count { color: var(--vera-blue, #60a5fa); }
        .fl2-tab .fl2-tab-dot { width:6px; height:6px; border-radius:50%; flex-shrink:0; }

        /* ── Tab content area ── */
        #fl2-tab-content { flex:1; overflow-y:auto; padding:14px; min-height:0; }

        /* ── Board items ── */
        .fl2-cat-header {
            display:flex; justify-content:space-between; align-items:center;
            margin-bottom:12px; flex-wrap:wrap; gap:6px;
        }
        .fl2-cat-title {
            font-weight:700; color: var(--vera-text, #c8d6e5); font-size:14px;
            display:flex; align-items:center; gap:6px;
        }
        .fl2-cat-actions { display:flex; gap:5px; flex-wrap:wrap; }
        .fl2-board-item {
            padding: 12px; border-radius: 6px;
            background: var(--vera-surface, rgba(15,23,42,.55));
            border-left: 3px solid var(--vera-text-dim, #334155);
            margin-bottom: 8px; transition: background .15s, transform .1s;
        }
        .fl2-board-item:hover {
            background: var(--vera-surface2, rgba(15,23,42,.75));
            transform: translateX(1px);
        }
        .fl2-board-item .fl2-item-text {
            color: var(--vera-text, #c8d6e5); font-size:12.5px;
            line-height:1.5; word-wrap:break-word; white-space:pre-wrap;
        }
        .fl2-board-item .fl2-item-meta { display:flex; gap:5px; margin-top:8px; flex-wrap:wrap; }
        .fl2-board-item .fl2-item-ts { color: var(--vera-text-dim, #374151); font-size:10px; }
        .fl2-priority-badge {
            padding:2px 7px; border-radius:3px; font-size:9px; font-weight:700;
            letter-spacing:.06em; text-transform:uppercase; color:white; flex-shrink:0;
        }
        .fl2-priority-badge.high   { background: var(--vera-red, #dc2626); }
        .fl2-priority-badge.medium { background: var(--vera-orange, #d97706); }
        .fl2-priority-badge.low    { background: var(--vera-text-dim, #4b5563); }
        .fl2-tool-tag {
            padding:2px 7px;
            background: var(--vera-blue-tint, rgba(59,130,246,.12));
            color: var(--vera-blue, #60a5fa);
            border-radius:3px; font-size:10px;
            border: 1px solid var(--vera-blue-tint, rgba(59,130,246,.2));
        }
        .fl2-item-btn {
            padding:3px 7px; background: var(--vera-surface2, rgba(30,41,59,.6));
            border: 1px solid var(--vera-border, #1e2d3d); border-radius:3px;
            color: var(--vera-text-muted, #64748b); font-size:10px; cursor:pointer;
            transition:all .12s; font-family:inherit;
        }
        .fl2-item-btn:hover {
            background: var(--vera-blue-tint, rgba(59,130,246,.15));
            border-color: var(--vera-blue-dim, #3b6fd4);
            color: var(--vera-blue, #93c5fd);
        }
        .fl2-item-btn.execute { border-color: var(--vera-green-tint, rgba(16,185,129,.3)); }
        .fl2-item-btn.execute:hover {
            background: var(--vera-green-tint, rgba(16,185,129,.15));
            color: var(--vera-green, #6ee7b7);
        }
        .fl2-empty-state {
            color: var(--vera-text-dim, #334155); font-size:12px;
            font-style:italic; text-align:center; padding:40px 20px;
        }

        /* ── Add form ── */
        .fl2-add-form {
            display:none; margin-bottom:14px; padding:14px;
            background: var(--vera-bg, rgba(10,14,20,.6));
            border-radius:6px; border: 1px solid var(--vera-border, #1e2d3d);
        }
        .fl2-add-form.visible { display:block; }
        .fl2-input, .fl2-textarea, .fl2-select {
            background: var(--vera-bg, #0d1117);
            color: var(--vera-text, #c8d6e5);
            border: 1px solid var(--vera-border, #1e2d3d);
            padding:8px 10px; border-radius:4px; font-size:12px;
            width:100%; font-family:inherit; transition:border-color .15s;
        }
        .fl2-input:focus, .fl2-textarea:focus, .fl2-select:focus {
            outline:none; border-color: var(--vera-blue-dim, #3b6fd4);
        }
        .fl2-textarea { resize:vertical; min-height:60px; }

        /* ═══ QUESTIONS — ensure the inner content fills the tab ═══ */
        .fl2-questions-inner { display:block; }

        /* ═══ WORKSPACE ════════════════════════════════════════════ */
        .fl2-ws-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill,minmax(230px,1fr));
            gap: 10px;
        }
        .fl2-ws-card {
            background: var(--vera-surface, rgba(15,23,42,.55));
            border: 1px solid var(--vera-border, #1e2d3d);
            border-radius:6px; padding:12px; cursor:pointer;
            transition:all .15s; min-width:0; overflow:hidden;
        }
        .fl2-ws-card:hover {
            border-color: var(--vera-blue-dim, #3b6fd4);
            background: var(--vera-surface2, rgba(15,23,42,.75));
            transform:translateY(-1px);
        }
        .fl2-ws-card .ws-name {
            color: var(--vera-text, #c8d6e5); font-weight:700; font-size:13px; margin-bottom:4px;
            display:flex; align-items:center; gap:6px; word-break:break-word;
        }
        .fl2-ws-card .ws-path {
            color: var(--vera-text-dim, #334155); font-size:10px; margin-bottom:6px;
            overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
        }
        .fl2-ws-card .ws-stats {
            display:flex; gap:8px; font-size:10px;
            color: var(--vera-text-muted, #475569); flex-wrap:wrap;
        }
        .fl2-ws-card .ws-tags {
            display:flex; gap:4px; flex-wrap:wrap; margin-top:6px;
        }
        .fl2-ws-tag {
            padding: 2px 6px;
            background: var(--vera-blue-tint, rgba(59,130,246,.1));
            color: var(--vera-blue, #60a5fa);
            border-radius: 3px; font-size: 9px; font-weight: 600;
            border: 1px solid var(--vera-blue-tint, rgba(59,130,246,.15));
            word-break: break-all; overflow-wrap: anywhere;
            white-space: normal; max-width: 100%;
            display: inline-block; line-height: 1.3;
        }
        /* tag type overrides — these use fixed accent colours intentionally */
        .fl2-ws-tag.git    { color: var(--vera-orange, #f97316); background:rgba(249,115,22,.1);  border-color:rgba(249,115,22,.15); }
        .fl2-ws-tag.docker { color: var(--vera-cyan, #06b6d4);   background:rgba(6,182,212,.1);   border-color:rgba(6,182,212,.15); }
        .fl2-ws-tag.vera   { color: var(--vera-purple, #a78bfa); background: var(--vera-purple-tint, rgba(167,139,250,.1)); border-color: var(--vera-purple-tint, rgba(167,139,250,.15)); }
        .fl2-ws-tag.python { color: var(--vera-yellow, #fbbf24); background:rgba(251,191,36,.1);  border-color:rgba(251,191,36,.15); }
        .fl2-ws-tag.node   { color: var(--vera-green, #34d399);  background: var(--vera-green-tint, rgba(52,211,153,.1)); border-color: var(--vera-green-tint, rgba(52,211,153,.15)); }

        .fl2-ws-status { display:inline-block; width:7px; height:7px; border-radius:50%; flex-shrink:0; }
        .fl2-ws-status.active   { background: var(--vera-green, #10b981); box-shadow:0 0 6px var(--vera-green-tint, rgba(16,185,129,.4)); }
        .fl2-ws-status.idle     { background: var(--vera-text-muted, #475569); }
        .fl2-ws-status.archived { background: var(--vera-text-dim, #374151); }

        .fl2-ws-detail {
            background: var(--vera-bg, rgba(10,14,20,.6));
            border: 1px solid var(--vera-border, #1e2d3d);
            border-radius:6px; padding:14px; margin-bottom:12px;
        }
        .fl2-ws-detail-header {
            display:flex; justify-content:space-between; align-items:flex-start;
            margin-bottom:10px; flex-wrap:wrap; gap:8px;
        }
        .fl2-ws-tree-item {
            padding:3px 0; font-size:11px; color: var(--vera-text-muted, #64748b);
            display:flex; align-items:center; gap:4px; min-width:0;
        }
        .fl2-ws-tree-item.dir { color: var(--vera-blue, #60a5fa); font-weight:600; }
        .fl2-ws-tree-item .ws-file-size { color: var(--vera-text-dim, #334155); font-size:9px; margin-left:auto; flex-shrink:0; }
        .fl2-ws-tree-item > span:nth-child(2) {
            overflow:hidden; text-overflow:ellipsis; white-space:nowrap; flex:1; min-width:0;
        }

        /* ═══ RESPONSIVE ═══════════════════════════════════════════ */
        @media (max-width:860px) {
            #fl2-split { flex-direction:column; }
            #fl2-left { width:100%!important; max-width:100%!important; min-width:100%!important; max-height:220px; border-right:none; border-bottom:1px solid var(--vera-border, #1e2d3d); }
            #fl2-resize-handle { display:none; }
            #fl2-right.fl2-sidebar { width:100%!important; min-width:100%!important; max-width:100%!important; }
            #fl2-right.fl2-sidebar #fl2-tab-bar { flex-direction:row; height:auto; border-right:none; border-bottom:2px solid var(--vera-border, #1e2d3d); width:auto; }
        }
    `;
    document.head.appendChild(layoutStyle);

    // ════════════════════════════════════════════════════════════
    // STATE
    // ════════════════════════════════════════════════════════════

    if (VeraChat.prototype._fl2BoardState === undefined) VeraChat.prototype._fl2BoardState = 0;

    // ════════════════════════════════════════════════════════════
    // updateFocusUI
    // ════════════════════════════════════════════════════════════

    VeraChat.prototype.updateFocusUI = function(preserveScrollPos = null) {
        const container = document.getElementById('tab-focus');
        if (!container) return;

        this.focusBoard = this.normalizeFocusBoard(this.focusBoard);
        if (!this.currentFocusTab) this.currentFocusTab = 'ideas';

        // Sync questions from board data
        const boardQs = this.focusBoard.questions || [];
        if (boardQs.length && typeof this._mergeBoardQuestionsInline === 'function') {
            this._focusQuestions = this._mergeBoardQuestionsInline(this._focusQuestions, boardQs);
            if (!this._questionsStageStatus || this._questionsStageStatus === 'idle')
                this._questionsStageStatus = 'done';
        }

        const oldContent = document.getElementById('fl2-tab-content');
        const scrollBefore = oldContent ? oldContent.scrollTop : (preserveScrollPos || 0);

        const boardClass = ['','fl2-sidebar','fl2-hidden'][this._fl2BoardState] || '';
        const splitClass = this._fl2BoardState === 2 ? 'board-hidden' : '';

        container.innerHTML = `
            <div id="focus-layout-v2">
                ${this._fl2ControlBar()}
                ${this._fl2FocusBar()}
                <div id="fl2-split" class="${splitClass}">
                    <div id="fl2-left">
                        <div id="fl2-left-header">
                            <span class="fl2-section-title">📡 Monitor</span>
                            <button class="fl2-left-toggle" onclick="app._pfClearAll()">Clear</button>
                        </div>
                        <div id="pf-status-panels"></div>
                    </div>
                    <div id="fl2-resize-handle" title="Drag to resize"></div>
                    <div id="fl2-right" class="${boardClass}">
                        ${this._fl2TabBar()}
                        <div id="fl2-tab-content">
                            ${this._fl2BoardState === 0 ? this._fl2TabContent() : ''}
                        </div>
                    </div>
                    ${this._fl2BoardState === 2 ? `
                        <button id="fl2-restore-btn" onclick="app._fl2SetBoardState(0)"
                                title="Restore focus board">◀ Board</button>` : ''}
                </div>
            </div>`;

        const newContent = document.getElementById('fl2-tab-content');
        if (newContent) newContent.scrollTop = scrollBefore;

        this.initializeDragAndDrop?.();
        this._initQuestionsTabListeners?.();
        this._initWorkspaceBrowser?.();

        setTimeout(() => {
            this._fl2InitStatusPanels();
            this._fl2AttachResizeHandle();
        }, 0);
    };

    // ════════════════════════════════════════════════════════════
    // THREE-STATE BOARD COLLAPSE
    // ════════════════════════════════════════════════════════════

    VeraChat.prototype._fl2SetBoardState = function(state) {
        this._fl2BoardState = state;
        this.updateFocusUI();
    };

    // Override switchFocusTab — clicking a sidebar tab expands to full
    const _origSwitch = VeraChat.prototype.switchFocusTab;
    VeraChat.prototype.switchFocusTab = function(tab) {
        this.currentFocusTab = tab;
        if (this._fl2BoardState !== 0) this._fl2BoardState = 0;
        this.updateFocusUI();
    };

    // ════════════════════════════════════════════════════════════
    // DRAG-TO-RESIZE
    // ════════════════════════════════════════════════════════════

    VeraChat.prototype._fl2AttachResizeHandle = function() {
        const handle = document.getElementById('fl2-resize-handle');
        const left   = document.getElementById('fl2-left');
        if (!handle || !left) return;

        let startX = 0, startW = 0, dragging = false;

        const onMove = (e) => {
            if (!dragging) return;
            const newW = Math.max(200, Math.min(600, startW + (e.clientX - startX)));
            left.style.width = `${newW}px`;
        };
        const onUp = () => {
            if (!dragging) return;
            dragging = false;
            handle.classList.remove('dragging');
            document.removeEventListener('mousemove', onMove);
            document.removeEventListener('mouseup', onUp);
            document.body.style.userSelect = '';
            document.body.style.cursor = '';
        };

        handle.addEventListener('mousedown', (e) => {
            e.preventDefault();
            dragging = true; startX = e.clientX; startW = left.offsetWidth;
            handle.classList.add('dragging');
            document.body.style.userSelect = 'none';
            document.body.style.cursor = 'col-resize';
            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup', onUp);
        });
    };

    // ════════════════════════════════════════════════════════════
    // CONTROL BAR
    // ════════════════════════════════════════════════════════════

    VeraChat.prototype._fl2ControlBar = function() {
        const running = this.focusRunning;
        const s = this._fl2BoardState;
        const cycleLabel  = s === 0 ? '◂ Sidebar' : '☰ Expand';
        const cycleState  = s === 0 ? 1 : 0;

        return `
        <div id="fl2-control-bar">
            <div class="fl2-btn-group">
                ${this.currentFocus ? `
                    <button class="fl2-ctrl-btn ${running?'active':''}"
                            onclick="app.${running?'stopProactiveThinking':'startProactiveThinking'}()">
                        ${running ? '⏸ Stop' : '▶ Start'}
                    </button>
                    <button class="fl2-ctrl-btn" onclick="app.triggerProactiveThought()">Think Now</button>
                ` : ''}
                <button class="fl2-ctrl-btn" onclick="app.showFocusBoardMenu()">Load</button>
                <button class="fl2-ctrl-btn" onclick="app.saveFocusBoard()">Save</button>
                <button class="fl2-ctrl-btn" onclick="app.loadFocusStatus()">↻</button>
                ${s !== 2 ? `<button class="fl2-ctrl-btn" onclick="app._fl2SetBoardState(${cycleState})">${cycleLabel}</button>` : ''}
                ${s === 1 ? `<button class="fl2-ctrl-btn danger" onclick="app._fl2SetBoardState(2)" title="Hide board">✕ Board</button>` : ''}
            </div>
            <span class="fl2-status-pill ${running?'running':'stopped'}">
                ${running ? '● Running' : '○ Stopped'}
            </span>
        </div>`;
    };

    // ════════════════════════════════════════════════════════════
    // FOCUS BAR
    // ════════════════════════════════════════════════════════════

    VeraChat.prototype._fl2FocusBar = function() {
        if (!this.currentFocus) return `
            <div id="fl2-focus-bar" style="border-left-color:var(--vera-text-dim,#334155);">
                <span class="fl2-focus-label">Focus</span>
                <span class="fl2-focus-text" style="color:var(--vera-text-muted,#475569);font-style:italic;">No focus set</span>
                <div class="fl2-focus-actions">
                    <button class="fl2-ctrl-btn" onclick="app.showSetFocusDialog()">✏ Set</button>
                </div>
            </div>`;
        return `
        <div id="fl2-focus-bar">
            <span class="fl2-focus-label">Focus</span>
            <span class="fl2-focus-text">${this.escapeHtml(this.currentFocus)}</span>
            <div class="fl2-focus-actions">
                <button class="fl2-ctrl-btn" onclick="app.showSetFocusDialog()">✏</button>
                <button class="fl2-ctrl-btn danger" onclick="app.clearFocus()">✕</button>
            </div>
        </div>`;
    };

    // ════════════════════════════════════════════════════════════
    // TAB BAR
    // ════════════════════════════════════════════════════════════

    VeraChat.prototype._fl2TabBar = function() {
        // Tab dot colours use CSS vars where there's a direct mapping;
        // per-tab accent colours (orange for next_steps, pink for questions, etc.)
        // are passed as inline style since they're semantic, not theme-sensitive.
        const cats = [
            { key:'ideas',      label:'Ideas',     icon:'💡', color:'var(--vera-purple,#8b5cf6)' },
            { key:'next_steps', label:'Next Steps', icon:'→',  color:'var(--vera-orange,#f59e0b)' },
            { key:'actions',    label:'Actions',    icon:'⚡', color:'var(--vera-blue,#3b82f6)' },
            { key:'progress',   label:'Progress',   icon:'✓',  color:'var(--vera-green,#10b981)' },
            { key:'issues',     label:'Issues',     icon:'⚠',  color:'var(--vera-red,#ef4444)' },
            { key:'completed',  label:'Done',       icon:'✔',  color:'var(--vera-text-dim,#4b5563)' },
            { key:'questions',  label:'Questions',  icon:'❓', color:'var(--vera-pink,#ec4899)' },
            { key:'workspace',  label:'Workspaces', icon:'📂', color:'var(--vera-cyan,#06b6d4)' },
        ];
        return `<div id="fl2-tab-bar">${cats.map(c => {
            const items = this.focusBoard[c.key] || [];
            let count;
            if      (c.key === 'questions') count = (this._focusQuestions||[]).length;
            else if (c.key === 'workspace') count = '';
            else if (c.key === 'actions')   count = this._getExpandedActionsCount?.(items) ?? items.length;
            else                            count = items.length;
            const active = this.currentFocusTab === c.key;
            return `
                <button class="fl2-tab ${active?'active':''}" onclick="app.switchFocusTab('${c.key}')">
                    <span class="fl2-tab-dot" style="background:${c.color};"></span>
                    <span class="fl2-tab-icon">${c.icon}</span>
                    <span class="fl2-tab-label">${c.label}</span>
                    ${count!==''?`<span class="fl2-tab-count">${count}</span>`:''}
                </button>`;
        }).join('')}</div>`;
    };

    // ════════════════════════════════════════════════════════════
    // TAB CONTENT DISPATCH
    // ════════════════════════════════════════════════════════════

    VeraChat.prototype._fl2TabContent = function() {
        const tab = this.currentFocusTab;
        if (tab === 'workspace') return this._fl2WorkspaceTab();
        if (tab === 'questions') {
            if (typeof this.renderQuestionsTabContent === 'function') {
                return this.renderQuestionsTabContent()
                    .replace(
                        /class="focus-tab-content[^"]*"/,
                        'class="fl2-questions-inner" style="display:block!important;"'
                    );
            }
            return `<div class="fl2-empty-state">Questions module not loaded.</div>`;
        }
        return this._fl2BoardTab(tab);
    };

    // ════════════════════════════════════════════════════════════
    // BOARD TAB
    // ════════════════════════════════════════════════════════════

    VeraChat.prototype._fl2BoardTab = function(catKey) {
        const catMeta = {
            ideas:     { label:'Ideas',     icon:'💡', color:'var(--vera-purple,#8b5cf6)' },
            next_steps:{ label:'Next Steps',icon:'→',  color:'var(--vera-orange,#f59e0b)' },
            actions:   { label:'Actions',   icon:'⚡', color:'var(--vera-blue,#3b82f6)' },
            progress:  { label:'Progress',  icon:'✓',  color:'var(--vera-green,#10b981)' },
            issues:    { label:'Issues',    icon:'⚠',  color:'var(--vera-red,#ef4444)' },
            completed: { label:'Done',      icon:'✔',  color:'var(--vera-text-dim,#4b5563)' },
        };
        const meta = catMeta[catKey] || catMeta.ideas;
        let items = this.focusBoard[catKey] || [];

        if (catKey === 'actions') {
            const expanded = [];
            items.forEach(item => expanded.push(...(this.expandActionArray?.(item) || [item])));
            items = expanded;
            this.focusBoard[catKey] = expanded;
        }

        const stageMap = { ideas:'runIdeasStage', next_steps:'runNextStepsStage', actions:'runActionsStage' };
        const hasStage = ['ideas','next_steps','actions'].includes(catKey);

        let html = `
        <div class="fl2-cat-header">
            <div class="fl2-cat-title"><span>${meta.icon}</span> ${meta.label}</div>
            <div class="fl2-cat-actions">
                ${hasStage && this.currentFocus && stageMap[catKey]
                    ? `<button class="fl2-item-btn" onclick="app.${stageMap[catKey]}()">▶ Generate</button>` : ''}
                ${catKey==='actions' && this.currentFocus
                    ? `<button class="fl2-item-btn execute" onclick="app.runExecuteStage()">🚀 Execute All</button>` : ''}
                <button class="fl2-item-btn" onclick="app.showAddItemForm('${catKey}')">+ Add</button>
                ${items.length ? `<button class="fl2-item-btn" onclick="app.clearCategory('${catKey}')">🗑 Clear</button>` : ''}
            </div>
        </div>
        <div id="add-item-form-${catKey}" class="fl2-add-form">
            ${catKey === 'actions' ? this._fl2ActionForm(catKey) : this._fl2GenericForm(catKey)}
        </div>
        <div id="category-items-${catKey}" class="drop-zone" data-category="${catKey}">`;

        if (!items.length) {
            html += `<div class="fl2-empty-state">No ${meta.label.toLowerCase()} yet.</div>`;
        } else if (catKey === 'actions') {
            items.forEach((item, idx) => { html += this._fl2ActionItem(item, idx, meta.color, catKey); });
        } else {
            items.forEach((item, idx) => { html += this._fl2GenericItem(item, idx, catKey, meta.color); });
        }
        return html + `</div>`;
    };

    VeraChat.prototype._fl2ActionItem = function(item, idx, color, cat) {
        const a = this.parseActionItem?.(item) || { description:String(item), tools:[], priority:'medium' };
        return `
        <div id="item-${cat}-${idx}" class="fl2-board-item draggable-item" draggable="true"
             data-category="${cat}" data-index="${idx}"
             ondragstart="app.handleDragStart(event)" ondragend="app.handleDragEnd(event)"
             style="border-left-color:${color};">
            <div style="display:flex;justify-content:space-between;align-items:start;gap:10px;margin-bottom:6px;">
                <div class="fl2-item-text" style="flex:1;">${this.escapeHtml(a.description)}</div>
                <span class="fl2-priority-badge ${a.priority}">${a.priority}</span>
            </div>
            ${a.tools.length ? `<div style="display:flex;gap:4px;flex-wrap:wrap;margin-bottom:6px;">
                ${a.tools.map(t=>`<span class="fl2-tool-tag">🔧 ${this.escapeHtml(t)}</span>`).join('')}
            </div>` : ''}
            <div class="fl2-item-meta">
                <button class="fl2-item-btn execute" onclick="app.executeActionDirectly(${idx})">▶ Run</button>
                <button class="fl2-item-btn" onclick="app.editBoardItem('${cat}',${idx})">✏</button>
                <button class="fl2-item-btn" onclick="app.deleteBoardItem('${cat}',${idx})">🗑</button>
                <button class="fl2-item-btn" onclick="app.moveToCompleted('${cat}',${idx})">✓ Done</button>
            </div>
        </div>`;
    };

    VeraChat.prototype._fl2GenericItem = function(item, idx, cat, color) {
        const p = this.parseGenericItem?.(item) || { text:String(item), timestamp:null };
        const drag = cat === 'next_steps';
        return `
        <div id="item-${cat}-${idx}" class="fl2-board-item ${drag?'draggable-item':''}"
             ${drag?'draggable="true"':''} data-category="${cat}" data-index="${idx}"
             ${drag?'ondragstart="app.handleDragStart(event)" ondragend="app.handleDragEnd(event)"':''}
             style="border-left-color:${color};">
            <div style="display:flex;justify-content:space-between;align-items:start;">
                <div class="fl2-item-text" style="flex:1;">${this.escapeHtml(p.text)}</div>
                <div style="display:flex;gap:3px;margin-left:10px;flex-shrink:0;">
                    <button class="fl2-item-btn" onclick="app.editBoardItem('${cat}',${idx})">✏</button>
                    <button class="fl2-item-btn" onclick="app.deleteBoardItem('${cat}',${idx})">🗑</button>
                    ${cat!=='completed'?`<button class="fl2-item-btn" onclick="app.moveToCompleted('${cat}',${idx})">✓</button>`:''}
                </div>
            </div>
            ${p.timestamp?`<div class="fl2-item-ts">${new Date(p.timestamp).toLocaleString()}</div>`:''}
        </div>`;
    };

    VeraChat.prototype._fl2ActionForm = function(cat) {
        return `<div style="display:flex;flex-direction:column;gap:8px;">
            <input type="text" id="action-desc-${cat}" placeholder="Action description…" class="fl2-input">
            <select id="action-priority-${cat}" class="fl2-select">
                <option value="high">High Priority</option>
                <option value="medium" selected>Medium Priority</option>
                <option value="low">Low Priority</option>
            </select>
            <div style="display:flex;gap:6px;">
                <button class="fl2-ctrl-btn" style="flex:1;" onclick="app.submitActionForm('${cat}')">✓ Add</button>
                <button class="fl2-ctrl-btn" onclick="app.hideAddItemForm('${cat}')">✕</button>
            </div>
        </div>`;
    };
    VeraChat.prototype._fl2GenericForm = function(cat) {
        return `<div style="display:flex;flex-direction:column;gap:8px;">
            <textarea id="item-text-${cat}" placeholder="Enter text…" rows="3" class="fl2-textarea"></textarea>
            <div style="display:flex;gap:6px;">
                <button class="fl2-ctrl-btn" style="flex:1;" onclick="app.submitGenericForm('${cat}')">✓ Add</button>
                <button class="fl2-ctrl-btn" onclick="app.hideAddItemForm('${cat}')">✕</button>
            </div>
        </div>`;
    };

    VeraChat.prototype.showAddItemForm = function(cat) {
        const f = document.getElementById(`add-item-form-${cat}`);
        if (!f) return;
        f.classList.add('visible');
        const inp = cat === 'actions'
            ? document.getElementById(`action-desc-${cat}`)
            : document.getElementById(`item-text-${cat}`);
        if (inp) setTimeout(() => inp.focus(), 80);
    };
    VeraChat.prototype.hideAddItemForm = function(cat) {
        document.getElementById(`add-item-form-${cat}`)?.classList.remove('visible');
    };

    // ════════════════════════════════════════════════════════════
    // QUESTIONS HELPER
    // ════════════════════════════════════════════════════════════

    VeraChat.prototype._mergeBoardQuestionsInline = function(existing, boardItems) {
        const saved = new Map();
        (existing||[]).forEach(q => {
            if (q?.response)
                saved.set((q.question||'').trim().toLowerCase(),
                    { response:q.response, answered_at:q.answered_at, skipped:q.skipped });
        });
        const out = [];
        (boardItems||[]).forEach(item => {
            if (!item) return;
            let q;
            if (typeof item === 'string') {
                if (!item.trim()) return;
                q = { question:item.trim(), category:'general', options:[], response:null, answered_at:null, skipped:false };
            } else {
                const m = item.metadata || {};
                if ((m.type||'') === 'info_gap') return;
                const text = (m.question||item.note||item.description||'').trim();
                if (!text) return;
                q = { question:text, category:m.category||'general',
                      options:Array.isArray(m.options)?m.options:[],
                      response:item.response||null, answered_at:item.answered_at||null,
                      skipped:item.skipped||false };
            }
            const key = q.question.trim().toLowerCase();
            if (saved.has(key)) Object.assign(q, saved.get(key));
            out.push(q);
        });
        return out;
    };

    // ════════════════════════════════════════════════════════════
    // WORKSPACE TAB
    // ════════════════════════════════════════════════════════════

    VeraChat.prototype._fl2WorkspaceTab = function() {
        if (!this._wsCache) { this._fl2LoadWorkspaces(); return `<div class="fl2-empty-state">Loading…</div>`; }
        if (this._wsDetailView) return this._fl2WorkspaceDetail(this._wsDetailView);

        const ws = this._wsCache;
        const tagClass = t => ['git','docker','vera','python','node'].includes(t)?t:'';

        let html = `
        <div class="fl2-cat-header">
            <div class="fl2-cat-title">📂 Workspaces</div>
            <div class="fl2-cat-actions">
                <button class="fl2-item-btn" onclick="app._fl2RefreshWorkspaces()">↻</button>
                <button class="fl2-item-btn" onclick="app._fl2CreateWorkspace()">+ New</button>
            </div>
        </div>`;

        if (this._wsStats) {
            const s = this._wsStats;
            html += `<div style="display:flex;gap:12px;margin-bottom:12px;font-size:11px;color:var(--vera-text-muted,#475569);flex-wrap:wrap;">
                <span>📊 ${s.total_workspaces||0}</span>
                <span>📁 ${s.total_files||s.total_file_count||0} files</span>
                ${s.total_size_human?`<span>💾 ${s.total_size_human}</span>`:''}
                ${s.workspaces_with_git?`<span>🔀 ${s.workspaces_with_git}</span>`:''}
                ${s.workspaces_with_focus?`<span>🎯 ${s.workspaces_with_focus}</span>`:''}
            </div>`;
        }

        if (!ws.length) return html + `<div class="fl2-empty-state">No workspaces found.</div>`;

        html += `<div class="fl2-ws-grid">`;
        ws.forEach(w => {
            const tags = w.tags || [];
            html += `
            <div class="fl2-ws-card" onclick="app._fl2OpenWorkspace('${this.escapeHtml(String(w.id))}')">
                <div class="ws-name">
                    <span class="fl2-ws-status ${w.status||'idle'}"></span>
                    ${this.escapeHtml(w.name)}
                    ${w.has_focus_board?'<span style="font-size:10px;flex-shrink:0;">🎯</span>':''}
                </div>
                <div class="ws-path">${this.escapeHtml(w.path||'')}</div>
                <div class="ws-stats">
                    <span>📄 ${w.file_count||0}</span>
                    <span>💾 ${this._fl2HumanSize(w.total_size_bytes||0)}</span>
                    ${w.has_git?'<span>🔀 git</span>':''}
                </div>
                ${tags.length?`<div class="ws-tags">${tags.map(t=>`<span class="fl2-ws-tag ${tagClass(t)}">${this.escapeHtml(t)}</span>`).join('')}</div>`:''}
            </div>`;
        });
        return html + `</div>`;
    };

    VeraChat.prototype._fl2HumanSize = function(b) {
        if (!b) return '0 B';
        for (const u of ['B','KB','MB','GB']) {
            if (Math.abs(b)<1024) return `${b.toFixed(u==='B'?0:1)} ${u}`;
            b/=1024;
        }
        return `${b.toFixed(1)} TB`;
    };

    VeraChat.prototype._fl2LoadWorkspaces = async function() {
        try {
            const [r1,r2] = await Promise.all([
                fetch('http://llm.int:8888/api/workspaces'),
                fetch('http://llm.int:8888/api/workspaces/stats/summary'),
            ]);
            this._wsCache = await r1.json();
            this._wsStats = await r2.json();
        } catch(e) { console.error('[fl2] ws load', e); this._wsCache = []; }
        this.updateFocusUI();
    };

    VeraChat.prototype._fl2RefreshWorkspaces = function() {
        this._wsCache = null; this._wsDetailView = null;
        this._fl2LoadWorkspaces();
    };

    VeraChat.prototype._fl2OpenWorkspace = async function(id) {
        try {
            const [r1,r2] = await Promise.all([
                fetch(`http://llm.int:8888/api/workspaces/${id}`),
                fetch(`http://llm.int:8888/api/workspaces/${id}/tree?depth=3`),
            ]);
            const d = await r1.json();
            d._tree = (await r2.json()).tree;
            this._wsDetailView = d;
            this.updateFocusUI();
        } catch(e) { console.error('[fl2] ws detail',e); }
    };

    VeraChat.prototype._fl2WorkspaceDetail = function(ws) {
        const tagClass = t => ['git','docker','vera','python','node'].includes(t)?t:'';
        const tags = ws.tags||[];
        return `
        <div class="fl2-ws-detail">
            <div class="fl2-ws-detail-header">
                <div style="min-width:0;">
                    <div style="color:var(--vera-text,#c8d6e5);font-weight:700;font-size:15px;margin-bottom:3px;word-break:break-word;">
                        <span class="fl2-ws-status ${ws.status||'idle'}" style="display:inline-block;margin-right:6px;"></span>
                        ${this.escapeHtml(ws.name)}
                    </div>
                    <div style="color:var(--vera-text-muted,#475569);font-size:11px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${this.escapeHtml(ws.path||'')}</div>
                    ${tags.length?`<div style="display:flex;gap:4px;flex-wrap:wrap;margin-top:5px;">
                        ${tags.map(t=>`<span class="fl2-ws-tag ${tagClass(t)}">${this.escapeHtml(t)}</span>`).join('')}
                    </div>`:''}
                </div>
                <div style="display:flex;gap:5px;flex-shrink:0;">
                    <button class="fl2-ctrl-btn" onclick="app._wsDetailView=null;app.updateFocusUI();">← Back</button>
                    ${ws.has_focus_board?`<button class="fl2-ctrl-btn" onclick="app._fl2LoadWsFocusBoard('${this.escapeHtml(String(ws.id))}')">🎯 Board</button>`:''}
                </div>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:11px;margin-bottom:12px;">
                <div style="color:var(--vera-text-muted,#64748b);">Files: <span style="color:var(--vera-text,#c8d6e5);">${ws.file_count||0}</span></div>
                <div style="color:var(--vera-text-muted,#64748b);">Size: <span style="color:var(--vera-text,#c8d6e5);">${this._fl2HumanSize(ws.total_size_bytes||0)}</span></div>
                ${ws.has_git?`
                    <div style="color:var(--vera-text-muted,#64748b);">Branch: <span style="color:var(--vera-orange,#f97316);">${this.escapeHtml(ws.git_branch||'—')}</span></div>
                    <div style="color:var(--vera-text-muted,#64748b);">Status: <span style="color:var(--vera-text,#c8d6e5);">${this.escapeHtml(ws.git_status||'—')}</span></div>`:''}
                <div style="color:var(--vera-text-muted,#64748b);">Modified: <span style="color:var(--vera-text,#c8d6e5);">${ws.last_modified?new Date(ws.last_modified).toLocaleDateString():'—'}</span></div>
            </div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px;">
            <div>
                <div class="fl2-cat-title" style="margin-bottom:7px;font-size:12px;">📁 File Tree</div>
                <div style="background:var(--vera-bg,rgba(10,14,20,.6));border:1px solid var(--vera-border,#1e2d3d);border-radius:6px;padding:8px;max-height:260px;overflow-y:auto;">
                    ${this._fl2RenderTree(ws._tree||[],0,String(ws.id))}
                </div>
            </div>
            <div>
                <div class="fl2-cat-title" style="margin-bottom:7px;font-size:12px;">🕑 Recent Files</div>
                <div style="background:var(--vera-bg,rgba(10,14,20,.6));border:1px solid var(--vera-border,#1e2d3d);border-radius:6px;padding:8px;max-height:260px;overflow-y:auto;">
                    ${(ws.recent_files||[]).slice(0,10).map(f=>`
                        <div class="fl2-ws-tree-item" style="cursor:pointer;"
                             onclick="app._fl2ViewFile('${this.escapeHtml(String(ws.id))}','${this.escapeHtml(f.path)}')">
                            <span style="flex-shrink:0;">📄</span>
                            <span>${this.escapeHtml(f.path)}</span>
                            <span class="ws-file-size">${this._fl2HumanSize(f.size||0)}</span>
                        </div>`).join('')||`<div style="color:var(--vera-text-dim,#334155);font-size:11px;">None</div>`}
                </div>
            </div>
        </div>
        ${ws.focus_board?`
        <div>
            <div class="fl2-cat-title" style="margin-bottom:7px;font-size:12px;">🎯 Focus Board</div>
            <div style="background:var(--vera-bg,rgba(10,14,20,.6));border:1px solid var(--vera-border,#1e2d3d);border-radius:6px;padding:10px;">
                ${Object.entries(ws.focus_board).map(([cat,items])=>{
                    if(!Array.isArray(items)||!items.length) return '';
                    return `<div style="margin-bottom:8px;">
                        <div style="color:var(--vera-text-muted,#64748b);font-size:10px;font-weight:700;text-transform:uppercase;margin-bottom:3px;">${cat}</div>
                        ${items.slice(0,5).map(it=>`<div style="color:var(--vera-text-muted,#94a3b8);font-size:11px;padding:2px 0;">• ${this.escapeHtml(
                            (typeof it==='string'?it:(it.note||it.description||JSON.stringify(it))).substring(0,100))
                        }</div>`).join('')}
                        ${items.length>5?`<div style="color:var(--vera-text-dim,#334155);font-size:10px;">+${items.length-5} more</div>`:''}
                    </div>`;
                }).join('')}
            </div>
        </div>`:''}`;
    };

    VeraChat.prototype._fl2RenderTree = function(nodes, depth, wsId) {
        if (!nodes?.length) return `<div style="color:var(--vera-text-dim,#334155);font-size:11px;">Empty</div>`;
        return nodes.map(n => {
            const pad = depth*14;
            if (n.type==='dir') return `
                <div class="fl2-ws-tree-item dir" style="padding-left:${pad}px;">
                    <span style="flex-shrink:0;">📁</span><span>${this.escapeHtml(n.name)}</span>
                </div>
                ${n.children?this._fl2RenderTree(n.children,depth+1,wsId):''}`;
            return `
                <div class="fl2-ws-tree-item" style="padding-left:${pad}px;cursor:pointer;"
                     onclick="app._fl2ViewFile('${this.escapeHtml(wsId)}','${this.escapeHtml(n.path||n.name)}')">
                    <span style="flex-shrink:0;">📄</span>
                    <span>${this.escapeHtml(n.name)}</span>
                    <span class="ws-file-size">${this._fl2HumanSize(n.size||0)}</span>
                </div>`;
        }).join('');
    };

    VeraChat.prototype._fl2ViewFile = async function(wsId, path) {
        try {
            const data = await (await fetch(`http://llm.int:8888/api/workspaces/${wsId}/file?path=${encodeURIComponent(path)}`)).json();
            const m = document.createElement('div');
            m.style.cssText='position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.7);display:flex;justify-content:center;align-items:center;z-index:10000;backdrop-filter:blur(4px);';
            m.onclick=e=>{if(e.target===m)m.remove();};
            const b=document.createElement('div');
            b.style.cssText=`background:var(--vera-bg,#0d1117);border:1px solid var(--vera-border,#1e2d3d);border-radius:8px;max-width:820px;width:95%;max-height:85vh;display:flex;flex-direction:column;box-shadow:0 20px 60px rgba(0,0,0,.6);`;
            b.innerHTML=`
                <div style="display:flex;justify-content:space-between;align-items:center;padding:10px 14px;border-bottom:1px solid var(--vera-border,#1e2d3d);background:var(--vera-surface,rgba(17,24,39,.8));flex-shrink:0;">
                    <div>
                        <div style="color:var(--vera-text,#c8d6e5);font-weight:700;font-size:13px;">${this.escapeHtml(data.name||path)}</div>
                        <div style="color:var(--vera-text-dim,#334155);font-size:10px;">${this.escapeHtml(path)} · ${this._fl2HumanSize(data.size||0)}</div>
                    </div>
                    <button onclick="this.closest('[style*=fixed]').remove()" style="background:none;border:none;color:var(--vera-text-muted,#64748b);font-size:18px;cursor:pointer;">✕</button>
                </div>
                <pre style="flex:1;overflow:auto;margin:0;padding:14px;color:var(--vera-text,#c8d6e5);font-size:12px;line-height:1.6;font-family:var(--vera-font,'SF Mono',monospace);background:var(--vera-bg,#0d1117);white-space:pre-wrap;word-break:break-all;">${
                    data.binary?`<i style="color:var(--vera-text-muted,#64748b);">Binary</i>`:this.escapeHtml(data.content||'')
                }${data.truncated?`\n\n<span style="color:var(--vera-orange,#f59e0b);">… truncated</span>`:''}</pre>`;
            m.appendChild(b); document.body.appendChild(m);
        } catch(e){console.error('[fl2] view file',e);}
    };

    VeraChat.prototype._fl2CreateWorkspace = async function() {
        const name = prompt('Workspace name:'); if(!name) return;
        const tpl  = prompt('Template (python/node/empty):','empty')||'empty';
        try {
            await fetch('http://llm.int:8888/api/workspaces',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,template:tpl})});
            this.addSystemMessage?.(`✓ Created: ${name}`);
            this._fl2RefreshWorkspaces();
        } catch(e){console.error('[fl2] create',e);}
    };

    VeraChat.prototype._fl2LoadWsFocusBoard = async function(id) {
        try {
            const data = await (await fetch(`http://llm.int:8888/api/workspaces/${id}/board`)).json();
            if(data.board){
                this.focusBoard = this.normalizeFocusBoard?.(data.board.focus_board||data.board)||data.board;
                this.currentFocus = data.board.focus||this.currentFocus;
                this.currentFocusTab = 'ideas';
                this.updateFocusUI();
                this.addSystemMessage?.('🎯 Loaded focus board from workspace');
            }
        } catch(e){console.error('[fl2] load board',e);}
    };

    // ════════════════════════════════════════════════════════════
    // STATUS PANELS
    // ════════════════════════════════════════════════════════════

    VeraChat.prototype._fl2InitStatusPanels = function() {
        const target = document.getElementById('pf-status-panels');
        if (!target) return;
        this.initProactiveFocusStatusUI_inTarget?.(target);
    };

    console.log('[FocusLayoutV2] v2.3 loaded — theme-integrated via --vera-* CSS vars');
})();

