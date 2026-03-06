(() => {
    // ============================================================
    // PROACTIVE FOCUS STATUS UI — v3.7
    //
    // Changes vs v3.6:
    // - Added guards throughout so the standalone shell is NEVER
    //   built when FocusLayoutV2 (#focus-layout-v2) is active.
    // - updateFocusUI hook skips initProactiveFocusStatusUI when
    //   V2 layout is present (V2 manages panels via _fl2InitStatusPanels).
    // - MutationObserver also respects the V2 guard.
    // - All colors via --pf-* CSS custom properties (unchanged from v3.6).
    // ============================================================

    function _esc(str) {
        return String(str ?? '')
            .replace(/&/g,'&amp;').replace(/</g,'&lt;')
            .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }
    function _nearBottom(el, threshold=80) {
        if (!el) return true;
        return el.scrollHeight - el.scrollTop - el.clientHeight < threshold;
    }
    function _scrollToBottom(el) { if (el) el.scrollTop = el.scrollHeight; }
    function _smartScroll(id) {
        const el = typeof id === 'string' ? document.getElementById(id) : id;
        if (el && !el._userScrollLocked) _scrollToBottom(el);
    }
    function _ts(d) {
        return new Date(d || Date.now()).toLocaleTimeString('en-US',
            {hour12:false,hour:'2-digit',minute:'2-digit',second:'2-digit'});
    }

    function _extractFilePath(text) {
        if (!text) return null;
        const m = text.match(/(?:^|[\s"'`,(])([~/.]?\/[\w.\-/]+\.\w{1,8})(?:[\s"'`,:)]|$)/m);
        if (m) return m[1];
        const j = text.match(/"(?:path|file|filename|target|output_path)"\s*:\s*"([^"]{3,120})"/);
        if (j) return j[1];
        return null;
    }
    function _fileLabel(path) {
        if (!path) return null;
        const parts = path.split('/').filter(Boolean);
        return parts.length > 1 ? parts.slice(-2).join('/') : parts[0];
    }
    function _buildLabel(ctx) {
        if (!ctx) return 'LLM';
        if (ctx.source) return ctx.source;
        if (ctx.tool) {
            const fp = _extractFilePath(ctx.toolInput || '');
            return fp ? `${ctx.tool} › ${_fileLabel(fp)}` : ctx.tool;
        }
        if (ctx.stageActivity && ctx.stageActivity !== ctx.stage)
            return `${ctx.stage || ''} › ${ctx.stageActivity}`.replace(/^›\s*/,'');
        return ctx.stage || 'LLM';
    }

    // ── Helper: is V2 layout currently active? ───────────────────
    function _v2Active() {
        return !!document.getElementById('focus-layout-v2');
    }

    // ── Singleton state ──────────────────────────────────────────
    if (!VeraChat.prototype._pfState) {
        VeraChat.prototype._pfState = {
            consoleOpen:   true,
            thoughtOpen:   true,
            responseOpen:  true,
            flowchartOpen: true,

            currentStage:    null,
            stageActivity:   null,
            stageProgress:   0,
            stageTotal:      0,

            activeCtx: {
                stage: null, stageActivity: null, iteration: null,
                stepNum: null, tool: null, toolInput: null, source: null,
            },

            consoleNodes:    [],
            thoughtHistory:  [],
            responseHistory: [],

            flowRuns:     [],
            activeRunId:  null,
            _runCounter:  0,

            inLLMThought:  false,
            inLLMResponse: false,

            pendingEvents: [],
        };
    }
    const ST = () => VeraChat.prototype._pfState;

    // ── CSS — all colors via --pf-* custom properties ────────────
    function _injectStyles() {
        if (document.getElementById('pf-v37-styles')) return;
        // Remove older style versions
        ['pf-v36-styles','pf-v35-styles','pf-v34-styles','pf-v33-styles','pf-v32-styles'].forEach(id => {
            document.getElementById(id)?.remove();
        });
        const s = document.createElement('style');
        s.id = 'pf-v37-styles';
        s.textContent = `
        /* ── Animations ─────────────────────────────────────────── */
        @keyframes pf-spin  { to { transform:rotate(360deg); } }
        @keyframes pf-pulse { 0%,100%{opacity:1}50%{opacity:.3} }

        #proactiveFocusStatus * { box-sizing:border-box; }

        /* ── Outer wrapper ──────────────────────────────────────── */
        #proactiveFocusStatus {
            background: linear-gradient(180deg, var(--pf-bg, #0d1117), var(--pf-bg, #0f172a));
            border-bottom: 1px solid var(--pf-border, #1e2d3d);
        }

        /* ── Panels ─────────────────────────────────────────────── */
        .pf-panel {
            background: var(--pf-bg-panel, #0d1117);
            border: 1px solid var(--pf-border, #1e2d3d);
            border-radius: 8px;
            overflow: hidden;
            margin-bottom: 8px;
        }
        .pf-panel-hdr {
            display: flex; align-items: center; justify-content: space-between;
            padding: 6px 12px;
            background: var(--pf-bg-panel-hdr, #111827);
            border-bottom: 1px solid var(--pf-border, #1e2d3d);
            cursor: pointer; user-select: none;
        }
        .pf-panel-hdr:hover { background: var(--pf-bg-panel-hdr-hover, #1a2333); }
        .pf-panel-title {
            display: flex; align-items: center; gap: 7px;
            font-size: 11px; font-weight: 700; letter-spacing: .06em;
            text-transform: uppercase;
            color: var(--pf-text, #64748b);
        }
        .pf-dot  { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
        .pf-count {
            font-size: 10px; color: var(--pf-text-secondary, #374151);
            margin-left: 4px; font-weight: 400; text-transform: none; letter-spacing: 0;
        }
        .pf-chevron { font-size: 10px; color: var(--pf-text-secondary, #374151); flex-shrink: 0; }
        .pf-panel-body {
            overflow-y: auto;
            font-family: var(--pf-font-family, "Monaco","Menlo","Courier New",monospace);
            font-size: 12px; line-height: 1.5;
        }
        .pf-panel-body.collapsed { display: none !important; }

        /* ── Entry chrome ────────────────────────────────────────── */
        .pf-entry { border-bottom: 1px solid var(--pf-border-subtle, #0a1118); }
        .pf-entry:last-child { border-bottom: none; }
        .pf-entry-hdr {
            display: flex; align-items: flex-start; gap: 6px;
            padding: 6px 12px 4px; cursor: pointer; user-select: none;
        }
        .pf-entry-hdr:hover { background: rgba(255,255,255,.025); }
        .pf-entry-chev { font-size: 9px; flex-shrink: 0; margin-top: 3px; }
        .pf-label-block { flex: 1; min-width: 0; }
        .pf-pill {
            display: inline-block; font-size: 8px; font-weight: 700;
            letter-spacing: .07em; text-transform: uppercase;
            padding: 1px 5px; border-radius: 3px; margin-bottom: 2px;
            background: rgba(255,255,255,.05);
            color: var(--pf-text-secondary, #475569);
            max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
        }
        .pf-main-lbl {
            font-size: 11px; font-weight: 700;
            overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 100%;
        }
        .pf-file-badge {
            display: inline-flex; align-items: center; gap: 4px;
            font-size: 9px; padding: 1px 6px; border-radius: 3px;
            background: var(--pf-file-badge-bg, rgba(16,185,129,.12));
            color: var(--pf-file-badge-text, #6ee7b7);
            border: 1px solid var(--pf-file-badge-border, rgba(16,185,129,.2));
            margin-top: 2px;
            overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 100%;
        }
        .pf-entry-meta {
            display: flex; align-items: center; gap: 5px;
            flex-shrink: 0; margin-left: auto;
        }
        .pf-entry-ts  { font-size: 9px; color: var(--pf-text-muted, #1e3a5f); }
        .pf-entry-st  { font-size: 10px; }
        .pf-entry-body { padding: 0 12px 8px 26px; }
        .pf-entry-body.collapsed { display: none; }

        /* ── Thought entries ─────────────────────────────────────── */
        .pf-thought-entry { border-left: 3px solid color-mix(in srgb, var(--pf-accent-thought, #8b5cf6) 35%, transparent); }
        .pf-thought-entry.active {
            border-left-color: var(--pf-accent-thought, #8b5cf6);
            background: color-mix(in srgb, var(--pf-accent-thought, #8b5cf6) 5%, transparent);
        }
        .pf-thought-entry .pf-main-lbl { color: var(--pf-accent-thought, #a78bfa); }
        .pf-thought-entry .pf-entry-chev { color: color-mix(in srgb, var(--pf-accent-thought, #8b5cf6) 70%, transparent); }
        .pf-thought-content {
            color: var(--pf-thought-text, #c4b5fd);
            white-space: pre-wrap; font-size: 11px;
        }

        /* ── Response entries ────────────────────────────────────── */
        .pf-response-entry { border-left: 3px solid color-mix(in srgb, var(--pf-accent-response, #3b82f6) 35%, transparent); }
        .pf-response-entry.active {
            border-left-color: var(--pf-accent-response, #3b82f6);
            background: color-mix(in srgb, var(--pf-accent-response, #3b82f6) 5%, transparent);
        }
        .pf-response-entry .pf-main-lbl { color: var(--pf-accent-response, #60a5fa); }
        .pf-response-entry .pf-entry-chev { color: color-mix(in srgb, var(--pf-accent-response, #3b82f6) 70%, transparent); }
        .pf-response-content {
            color: var(--pf-response-text, #e2e8f0);
            white-space: pre-wrap; font-size: 12px;
        }

        /* ── Run containers ──────────────────────────────────────── */
        .pf-run {
            border: 1px solid var(--pf-run-border-done, #1e3a5f);
            border-radius: 6px; margin: 6px 8px; overflow: hidden;
        }
        .pf-run.active  { border-color: var(--pf-run-border, #3b82f6); }
        .pf-run.done    { border-color: var(--pf-run-border-done, #1e3a5f); }
        .pf-run.failed  { border-color: var(--pf-run-border-failed, #7f1d1d); }

        .pf-run-hdr {
            display: flex; align-items: center; gap: 7px;
            padding: 5px 10px;
            background: var(--pf-run-bg, #0f1923);
            cursor: pointer; user-select: none;
        }
        .pf-run-hdr:hover { background: var(--pf-run-bg-hover, #131f2e); }
        .pf-run-title {
            font-size: 11px; font-weight: 700;
            color: var(--pf-run-title, #60a5fa);
            flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
        }
        .pf-run.done   .pf-run-title { color: var(--pf-run-title-done, #64748b); }
        .pf-run.failed .pf-run-title { color: var(--pf-run-title-failed, #f87171); }
        .pf-run-ts   { font-size: 9px; color: var(--pf-text-muted, #1e3a5f); flex-shrink: 0; }
        .pf-run-chev { font-size: 9px; color: var(--pf-text-secondary, #374151); flex-shrink: 0; }
        .pf-run-body { padding: 0; }
        .pf-run-body.collapsed { display: none; }

        /* Planning block inside a run */
        .pf-run-plan {
            padding: 4px 10px 4px 14px;
            border-bottom: 1px solid var(--pf-border-subtle, #0a1118);
        }
        .pf-run-plan-lbl {
            font-size: 9px; font-weight: 700; letter-spacing: .07em;
            text-transform: uppercase;
            color: var(--pf-text-secondary, #374151);
            margin-bottom: 2px;
        }
        .pf-run-plan-txt {
            color: var(--pf-plan-text, #475569);
            white-space: pre-wrap; font-size: 10px;
            max-height: 120px; overflow-y: auto;
        }

        /* ── Step entries ────────────────────────────────────────── */
        .pf-step-entry {
            border-left: 3px solid var(--pf-border, #1e293b);
            border-bottom: 1px solid var(--pf-border-subtle, #0a1118);
        }
        .pf-step-entry:last-child { border-bottom: none; }

        .pf-step-entry.running {
            border-left-color: var(--pf-step-running, #3b82f6);
            background: var(--pf-step-bg-running, rgba(59,130,246,.04));
        }
        .pf-step-entry.done {
            border-left-color: var(--pf-step-done, #059669);
            background: var(--pf-step-bg-done, rgba(5,150,105,.04));
        }
        .pf-step-entry.failed {
            border-left-color: var(--pf-step-failed, #dc2626);
            background: var(--pf-step-bg-failed, rgba(220,38,38,.04));
        }
        .pf-step-entry          .pf-main-lbl { color: var(--pf-step-text-running, #94a3b8); }
        .pf-step-entry.done     .pf-main-lbl { color: var(--pf-step-text-done, #6ee7b7); }
        .pf-step-entry.failed   .pf-main-lbl { color: var(--pf-step-text-failed, #fca5a5); }
        .pf-step-entry .pf-entry-chev { color: var(--pf-border, #334155); }

        .pf-step-input {
            padding: 3px 6px; margin-bottom: 4px;
            background: rgba(0,0,0,.25); border-radius: 3px;
            color: var(--pf-step-input-text, #475569);
            font-size: 10px; white-space: pre-wrap;
            word-break: break-all; max-height: 55px; overflow-y: auto;
        }
        .pf-step-output { color: var(--pf-step-output-text, #34d399); white-space: pre-wrap; font-size: 11px; }
        .pf-step-error  { color: var(--pf-accent-error, #f87171); font-size: 11px; margin-top: 4px; }

        /* ── Console lines ───────────────────────────────────────── */
        .pf-line { margin: 1px 0; padding: 2px 5px; border-radius: 3px; word-break: break-word; }
        .pf-line.info    { color: var(--pf-text, #94a3b8); }
        .pf-line.success { color: var(--pf-accent-success, #34d399); background: color-mix(in srgb, var(--pf-accent-success, #34d399) 7%, transparent); font-weight: 600; }
        .pf-line.warning { color: var(--pf-accent-warning, #fbbf24); background: color-mix(in srgb, var(--pf-accent-warning, #fbbf24) 7%, transparent); }
        .pf-line.error   { color: var(--pf-accent-error, #f87171); background: color-mix(in srgb, var(--pf-accent-error, #f87171) 7%, transparent); font-weight: 600; }
        .pf-line.tool    { color: var(--pf-accent-tool, #7dd3fc); }
        .pf-ts-i { color: var(--pf-text-muted, #2d3f52); font-size: 10px; margin-right: 4px; }

        .pf-sep {
            display: flex; align-items: center; gap: 6px;
            padding: 3px 5px; margin: 2px 0;
            font-size: 9px; font-weight: 700; letter-spacing: .07em;
            text-transform: uppercase;
            color: var(--pf-sep-color, #2d4a6a);
            border-top: 1px solid var(--pf-sep-border, #0f1923);
        }

        /* ── Spinners & cursors ──────────────────────────────────── */
        .pf-spinner {
            display: inline-block; width: 9px; height: 9px;
            border: 1.5px solid currentColor; border-top-color: transparent;
            border-radius: 50%; animation: pf-spin .7s linear infinite; flex-shrink: 0;
        }
        .pf-cursor {
            display: inline-block; width: 2px; height: 11px;
            background: var(--pf-cursor, #60a5fa);
            margin-left: 1px; vertical-align: middle;
            animation: pf-pulse .8s ease-in-out infinite;
        }

        /* ── Stage bar ───────────────────────────────────────────── */
        #pf-stage-bar {
            display: none; padding: 8px 12px;
            background: var(--pf-stage-bar-bg, rgba(59,130,246,.07));
            border-left: 3px solid var(--pf-accent-stage, #3b82f6);
            border-radius: 6px; margin-bottom: 8px;
        }
        .pf-sb-row { display: flex; align-items: center; gap: 8px; margin-bottom: 3px; }
        #pf-stage-name { color: var(--pf-accent-stage, #60a5fa); font-weight: 700; font-size: 13px; }
        #pf-stage-act  { color: var(--pf-text-secondary, #64748b); font-size: 11px; }
        #pf-stage-iter { color: var(--pf-text-secondary, #374151); font-size: 10px; margin-left: 4px; }
        #pf-prog-wrap {
            display: none; height: 3px;
            background: rgba(0,0,0,.3); border-radius: 2px; overflow: hidden; margin-top: 3px;
        }
        #pf-prog-fill {
            height: 100%; width: 0%;
            background: linear-gradient(90deg, var(--pf-accent-response, #3b82f6), var(--pf-accent-thought, #8b5cf6));
            transition: width .3s;
        }

        /* ── Spinner color helpers ───────────────────────────────── */
        .pf-spin-thought  { color: var(--pf-spinner-thought, #8b5cf6); }
        .pf-spin-response { color: var(--pf-spinner-response, #3b82f6); }
        .pf-spin-run      { color: var(--pf-spinner-run, #3b82f6); }

        /* ── Success / done / failed inline colors ───────────────── */
        .pf-icon-done   { color: var(--pf-accent-success, #10b981); font-weight: 700; }
        .pf-icon-failed { color: var(--pf-accent-error, #f87171);   font-weight: 700; }
        `;
        document.head.appendChild(s);
    }

    // ── Shell (standalone mode only — not used when V2 layout active) ──
    VeraChat.prototype._buildPfShell = function(focusTab) {
        const wrap = document.createElement('div');
        wrap.id = 'proactiveFocusStatus';
        wrap.style.cssText = `
            position:sticky; top:0; z-index:100;
            border-bottom:1px solid var(--pf-border,#1e2d3d);
            padding:8px 12px 6px;
        `;
        const btn = (lbl, fn, extra='') =>
            `<button onclick="${fn}" style="font-size:10px;padding:2px 7px;cursor:pointer;${extra}">${lbl}</button>`;
        wrap.innerHTML = `
            <div id="pf-stage-bar">
                <div class="pf-sb-row">
                    <div class="pf-spinner pf-spin-run"></div>
                    <span id="pf-stage-name"></span>
                    <span id="pf-stage-act"></span>
                    <span id="pf-stage-iter"></span>
                    <div style="margin-left:auto;display:flex;gap:4px;">
                        ${btn('📜','app._pfToggle("console")')}
                        ${btn('🧠','app._pfToggle("thought")')}
                        ${btn('💬','app._pfToggle("response")')}
                        ${btn('🔀','app._pfToggle("flowchart")')}
                    </div>
                </div>
                <div id="pf-prog-wrap"><div id="pf-prog-fill"></div></div>
            </div>
            <div id="pf-toolbar" style="display:flex;gap:5px;flex-wrap:wrap;margin-bottom:7px;">
                ${btn('📜 Console','app._pfToggle("console")')}
                ${btn('🧠 Thought','app._pfToggle("thought")')}
                ${btn('💬 Response','app._pfToggle("response")')}
                ${btn('🔀 Flowchart','app._pfToggle("flowchart")')}
                ${btn('🗑 Clear','app._pfClearAll()','margin-left:auto;')}
            </div>
            ${this._pfMkPanel('console',   '📜 Live Console',        'var(--pf-accent-console,#94a3b8)', 'max-height:200px;padding:5px 7px;')}
            ${this._pfMkPanel('thought',   '🧠 LLM Reasoning',       'var(--pf-accent-thought,#8b5cf6)', 'max-height:280px;padding:0;')}
            ${this._pfMkPanel('response',  '💬 LLM Response',        'var(--pf-accent-response,#3b82f6)', 'max-height:280px;padding:0;')}
            ${this._pfMkPanel('flowchart', '🔀 Toolchain Flowchart', 'var(--pf-accent-flowchart,#f59e0b)', 'max-height:420px;padding:0;')}
        `;
        focusTab.insertBefore(wrap, focusTab.firstChild);
        this._pfAttachScrollLocks();
    };

    // ── Attach scroll-lock listeners to all panel bodies ─────────
    VeraChat.prototype._pfAttachScrollLocks = function() {
        ['pf-console-body','pf-thought-body','pf-response-body','pf-flowchart-body'].forEach(id => {
            const el = document.getElementById(id);
            if (!el) return;
            el._userScrollLocked = false;
            el.addEventListener('scroll', () => { el._userScrollLocked = !_nearBottom(el); }, {passive:true});
        });
    };

    VeraChat.prototype._pfMkPanel = function(name, title, dotColor, bodyStyle) {
        return `
        <div class="pf-panel" id="pf-${name}-panel">
            <div class="pf-panel-hdr" onclick="app._pfToggle('${name}')">
                <div class="pf-panel-title">
                    <div class="pf-dot" style="background:${dotColor};"></div>
                    ${title}
                    <span class="pf-count" id="pf-${name}-count"></span>
                </div>
                <span class="pf-chevron" id="pf-${name}-chev">▾</span>
            </div>
            <div class="pf-panel-body" id="pf-${name}-body" style="${bodyStyle}"></div>
        </div>`;
    };

    VeraChat.prototype._pfToggle = function(name) {
        const panel = document.getElementById(`pf-${name}-panel`);
        const body  = document.getElementById(`pf-${name}-body`);
        const chev  = document.getElementById(`pf-${name}-chev`);
        if (!body) return;
        if (panel) panel.style.display = '';
        const isCollapsed = body.classList.toggle('collapsed');
        ST()[`${name}Open`] = !isCollapsed;
        if (chev) chev.textContent = isCollapsed ? '▸' : '▾';
        if (!isCollapsed) setTimeout(() => _scrollToBottom(body), 40);
    };
    VeraChat.prototype.togglePfPanel = function(n) { this._pfToggle(n); };

    VeraChat.prototype._pfClearAll = function() {
        const st = ST();
        Object.assign(st, {
            consoleNodes:[], thoughtHistory:[], responseHistory:[],
            flowRuns:[], activeRunId:null, _runCounter:0,
            inLLMThought:false, inLLMResponse:false,
            activeCtx:{ stage:null, stageActivity:null, iteration:null,
                         stepNum:null, tool:null, toolInput:null, source:null },
        });
        ['console','thought','response','flowchart'].forEach(n => {
            const b = document.getElementById(`pf-${n}-body`);
            if (b) b.innerHTML = '';
            const c = document.getElementById(`pf-${n}-count`);
            if (c) c.textContent = '';
        });
    };
    VeraChat.prototype.clearAllPfPanels = function() { this._pfClearAll(); };

    // ── Init — standalone mode ────────────────────────────────────
    // Only builds #proactiveFocusStatus when V2 layout is NOT active.
    // When V2 IS active, panels are managed by _fl2InitStatusPanels →
    // initProactiveFocusStatusUI_inTarget.
    VeraChat.prototype.initProactiveFocusStatusUI = function() {
        // Guard: if V2 layout is present, do nothing here.
        if (_v2Active()) return;

        const ft = document.getElementById('tab-focus');
        if (!ft) return;
        _injectStyles();
        if (!document.getElementById('proactiveFocusStatus')) {
            this._buildPfShell(ft);
            this._pfRestoreState();
            const st = ST();
            const pending = [...st.pendingEvents];
            st.pendingEvents = [];
            pending.forEach(ev => this.handleFocusEvent(ev));
        }
    };

    // ── Init — V2 in-target mode ──────────────────────────────────
    // Called by focus_layout_v2.js → _fl2InitStatusPanels.
    // Builds panels directly into the provided container element.
    VeraChat.prototype.initProactiveFocusStatusUI_inTarget = function(target) {
        if (!target) return;
        _injectStyles();

        target.innerHTML = `
            <div id="pf-stage-bar" style="margin:8px;border-radius:6px;">
                <div class="pf-sb-row">
                    <div class="pf-spinner pf-spin-run"></div>
                    <span id="pf-stage-name"></span>
                    <span id="pf-stage-act"></span>
                    <span id="pf-stage-iter"></span>
                </div>
                <div id="pf-prog-wrap"><div id="pf-prog-fill"></div></div>
            </div>
            ${this._pfMkPanel('console',   '📜 Console',    'var(--pf-accent-console,#94a3b8)', 'max-height:180px;padding:5px 7px;')}
            ${this._pfMkPanel('thought',   '🧠 Reasoning',  'var(--pf-accent-thought,#8b5cf6)', 'max-height:220px;padding:0;')}
            ${this._pfMkPanel('response',  '💬 Response',   'var(--pf-accent-response,#3b82f6)', 'max-height:220px;padding:0;')}
            ${this._pfMkPanel('flowchart', '🔀 Toolchain',  'var(--pf-accent-flowchart,#f59e0b)', 'max-height:280px;padding:0;')}
        `;

        this._pfAttachScrollLocks();
        this._pfRestoreState();

        // Flush any pending events
        const st = ST();
        const pending = [...st.pendingEvents];
        st.pendingEvents = [];
        pending.forEach(ev => this.handleFocusEvent(ev));
    };

    VeraChat.prototype._pfRestoreState = function() {
        const st = ST();
        ['console','thought','response','flowchart'].forEach(n => {
            const body = document.getElementById(`pf-${n}-body`);
            const chev = document.getElementById(`pf-${n}-chev`);
            if (!body) return;
            if (!st[`${n}Open`]) { body.classList.add('collapsed'); if (chev) chev.textContent='▸'; }
        });
        const cb = document.getElementById('pf-console-body');
        if (cb) st.consoleNodes.forEach(n => cb.appendChild(n.cloneNode(true)));
        st.thoughtHistory.forEach((e,i)  => this._pfRenderThought(e, i));
        st.responseHistory.forEach((e,i) => this._pfRenderResponse(e, i));
        st.flowRuns.forEach(run          => this._pfRenderRun(run));
        const _cnt = (id, arr) => { const el=document.getElementById(id); if(el&&arr.length) el.textContent=`(${arr.length})`; };
        _cnt('pf-thought-count',   st.thoughtHistory);
        _cnt('pf-response-count',  st.responseHistory);
        _cnt('pf-flowchart-count', st.flowRuns);
        if (st.currentStage) this.updateStageStatus({
            stage:st.currentStage, activity:st.stageActivity,
            progress:st.stageProgress, total:st.stageTotal,
        });
    };

    // ── Context helpers ──────────────────────────────────────────
    function _snap() { return Object.assign({}, ST().activeCtx); }
    function _resolveSource(explicitSource) {
        const ctx = ST().activeCtx;
        return explicitSource || ctx.source || ctx.stageActivity || ctx.stage || null;
    }

    // ── Stage bar ────────────────────────────────────────────────
    VeraChat.prototype.updateStageStatus = function(data) {
        const st = ST();
        st.currentStage  = data.stage;
        st.stageActivity = data.activity || '';
        st.stageProgress = data.progress || 0;
        st.stageTotal    = data.total    || 0;
        st.activeCtx.stage         = data.stage;
        st.activeCtx.stageActivity = data.activity || '';
        st.activeCtx.source = null;
        const bar = document.getElementById('pf-stage-bar');
        const tb  = document.getElementById('pf-toolbar');
        if (bar) bar.style.display = 'block';
        if (tb)  tb.style.display  = 'none';
        const icons = {'Ideas Generation':'💡','Next Steps':'→','Action Planning':'⚡',
                       'Action Execution':'▶️','State Review':'📊','Saving':'💾','Project Structure':'🏗️'};
        const nm = document.getElementById('pf-stage-name');
        const ac = document.getElementById('pf-stage-act');
        if (nm) nm.textContent = `${icons[data.stage]||'🔄'} ${data.stage}`;
        if (ac) ac.textContent = data.activity || '';
        const pw = document.getElementById('pf-prog-wrap');
        const pf = document.getElementById('pf-prog-fill');
        if (data.total > 0 && pw) {
            pw.style.display = 'block';
            if (pf) pf.style.width = `${Math.round((data.progress/data.total)*100)}%`;
        }
    };
    VeraChat.prototype.updateStageProgress = function(data) {
        const pf = document.getElementById('pf-prog-fill');
        if (pf) pf.style.width = `${Math.round(data.percentage||0)}%`;
    };
    VeraChat.prototype.clearStage = function() {
        const st = ST();
        st.currentStage = st.stageActivity = null;
        st.stageProgress = st.stageTotal = 0;
        const bar = document.getElementById('pf-stage-bar');
        const tb  = document.getElementById('pf-toolbar');
        if (bar) bar.style.display = 'none';
        if (tb)  tb.style.display  = 'flex';
    };

    // ── Console ──────────────────────────────────────────────────
    VeraChat.prototype.addStreamOutput = function(text, category='info') {
        const st = ST();
        const el = document.createElement('div');
        el.className = `pf-line ${category}`;
        el.innerHTML = `<span class="pf-ts-i">[${_ts()}]</span>${_esc(text)}`;
        st.consoleNodes.push(el.cloneNode(true));
        if (st.consoleNodes.length > 600) st.consoleNodes.shift();
        const body = document.getElementById('pf-console-body');
        if (body) {
            body.appendChild(el);
            while (body.children.length > 600) body.removeChild(body.firstChild);
            _smartScroll('pf-console-body');
        }
    };
    VeraChat.prototype._pfSep = function(label, icon='◈') {
        const st = ST();
        const el = document.createElement('div');
        el.className = 'pf-sep';
        el.innerHTML = `<span>${icon}</span>${_esc(label)}`;
        st.consoleNodes.push(el.cloneNode(true));
        const body = document.getElementById('pf-console-body');
        if (body) { body.appendChild(el); _smartScroll('pf-console-body'); }
    };

    // ── Entry header builder ─────────────────────────────────────
    function _mkHdr(label, pill, filePath, statusId, statusHtml, ts) {
        const pillHtml = pill     ? `<div class="pf-pill">${_esc(pill)}</div>` : '';
        const fileHtml = filePath ? `<div class="pf-file-badge">📄 ${_esc(_fileLabel(filePath)||filePath)}</div>` : '';
        return `
            <div class="pf-entry-hdr" onclick="(function(el){
                var b=el.parentElement.querySelector('.pf-entry-body');
                b.classList.toggle('collapsed');
                el.querySelector('.pf-entry-chev').textContent=b.classList.contains('collapsed')?'▸':'▾';
            })(this)">
                <span class="pf-entry-chev">▾</span>
                <div class="pf-label-block">
                    ${pillHtml}
                    <div class="pf-main-lbl">${_esc(label)}</div>
                    ${fileHtml}
                </div>
                <div class="pf-entry-meta">
                    <span class="pf-entry-ts">${_esc(ts)}</span>
                    <span class="pf-entry-st" id="${statusId}">${statusHtml}</span>
                </div>
            </div>`;
    }

    const _doneHtml   = '<span class="pf-icon-done">✓</span>';
    const _failedHtml = '<span class="pf-icon-failed">✕</span>';
    const _spinThought  = '<span class="pf-spinner pf-spin-thought"></span>';
    const _spinResponse = '<span class="pf-spinner pf-spin-response"></span>'
                        + '<span class="pf-cursor" style="margin-left:3px;"></span>';
    const _spinRun    = '<span class="pf-spinner pf-spin-run"></span>';

    // ══════════════════════════════════════════════════════════════
    // THOUGHT
    // ══════════════════════════════════════════════════════════════

    VeraChat.prototype.startLLMThought = function(timestamp, source) {
        const st  = ST();
        const ctx = _snap();
        const effectiveSource = _resolveSource(source) || 'Reasoning';
        ctx.source = effectiveSource;
        const last = st.thoughtHistory[st.thoughtHistory.length - 1];
        if (last && !last.done && last.ctx.source === effectiveSource) {
            st.inLLMThought = true; return;
        }
        const pill = [ctx.iteration != null ? `iter ${ctx.iteration}` : null, ctx.stage].filter(Boolean).join(' › ');
        const entry = { ctx, ts:_ts(timestamp), label:effectiveSource, pill, buffer:'', done:false, filePath:null };
        st.thoughtHistory.push(entry);
        st.inLLMThought = true;
        const idx = st.thoughtHistory.length - 1;
        this._pfRenderThought(entry, idx);
        const cnt = document.getElementById('pf-thought-count');
        if (cnt) cnt.textContent = `(${st.thoughtHistory.length})`;
        const body = document.getElementById('pf-thought-body');
        if (body?.classList.contains('collapsed')) this._pfToggle('thought');
    };
    VeraChat.prototype._pfRenderThought = function(entry, idx) {
        const body = document.getElementById('pf-thought-body');
        if (!body) return;
        const statusId = `pf-th-st-${idx}`;
        const wrap = document.createElement('div');
        wrap.className = 'pf-entry pf-thought-entry' + (entry.done ? '' : ' active');
        wrap.id = `pf-th-${idx}`;
        wrap.innerHTML = _mkHdr(entry.label, entry.pill, entry.filePath, statusId,
            entry.done ? _doneHtml : _spinThought, entry.ts)
            + `<div class="pf-entry-body"><div class="pf-thought-content" id="pf-th-txt-${idx}">${_esc(entry.buffer)}</div></div>`;
        body.appendChild(wrap);
        _smartScroll('pf-thought-body');
    };
    VeraChat.prototype.appendLLMThought = function(chunk) {
        const st = ST();
        if (!st.inLLMThought) this.startLLMThought(null, null);
        const idx = st.thoughtHistory.length - 1;
        if (idx < 0) return;
        st.thoughtHistory[idx].buffer += chunk;
        const el = document.getElementById(`pf-th-txt-${idx}`);
        if (el) el.textContent = st.thoughtHistory[idx].buffer;
        _smartScroll('pf-thought-body');
    };
    VeraChat.prototype.completeLLMThought = function() {
        const st = ST();
        st.inLLMThought = false;
        const idx = st.thoughtHistory.length - 1;
        if (idx < 0) return;
        const entry = st.thoughtHistory[idx];
        entry.done = true;
        entry.filePath = _extractFilePath(entry.buffer);
        document.getElementById(`pf-th-${idx}`)?.classList.remove('active');
        const s = document.getElementById(`pf-th-st-${idx}`);
        if (s) s.innerHTML = _doneHtml;
        if (entry.filePath) {
            const lbl = document.querySelector(`#pf-th-${idx} .pf-label-block`);
            if (lbl && !lbl.querySelector('.pf-file-badge')) {
                const b = document.createElement('div');
                b.className = 'pf-file-badge';
                b.textContent = `📄 ${_fileLabel(entry.filePath)||entry.filePath}`;
                lbl.appendChild(b);
            }
        }
    };

    // ══════════════════════════════════════════════════════════════
    // RESPONSE
    // ══════════════════════════════════════════════════════════════

    VeraChat.prototype.startLLMResponse = function(timestamp, source) {
        const st  = ST();
        const ctx = _snap();
        const effectiveSource = _resolveSource(source) || 'Response';
        ctx.source = effectiveSource;
        const last = st.responseHistory[st.responseHistory.length - 1];
        if (last && !last.done && last.ctx.source === effectiveSource) {
            st.inLLMResponse = true; return;
        }
        if (last && !last.done) this.completeLLMResponse();
        const fp    = _extractFilePath(ctx.toolInput || '');
        const label = fp ? `${effectiveSource} › ${_fileLabel(fp)}` : effectiveSource;
        const pill  = [ctx.iteration != null ? `iter ${ctx.iteration}` : null, ctx.stage].filter(Boolean).join(' › ');
        const entry = { ctx, ts:_ts(timestamp), label, pill, buffer:'', done:false, filePath:fp };
        st.responseHistory.push(entry);
        st.inLLMResponse = true;
        const idx = st.responseHistory.length - 1;
        this._pfRenderResponse(entry, idx);
        const cnt = document.getElementById('pf-response-count');
        if (cnt) cnt.textContent = `(${st.responseHistory.length})`;
        const body = document.getElementById('pf-response-body');
        if (body?.classList.contains('collapsed')) this._pfToggle('response');
    };
    VeraChat.prototype._pfRenderResponse = function(entry, idx) {
        const body = document.getElementById('pf-response-body');
        if (!body) return;
        const statusId = `pf-re-st-${idx}`;
        const wrap = document.createElement('div');
        wrap.className = 'pf-entry pf-response-entry' + (entry.done ? '' : ' active');
        wrap.id = `pf-re-${idx}`;
        wrap.innerHTML = _mkHdr(entry.label, entry.pill, entry.filePath, statusId,
            entry.done ? _doneHtml : _spinResponse, entry.ts)
            + `<div class="pf-entry-body"><div class="pf-response-content" id="pf-re-txt-${idx}">${_esc(entry.buffer)}</div></div>`;
        body.appendChild(wrap);
        _smartScroll('pf-response-body');
    };
    VeraChat.prototype.appendLLMResponse = function(chunk) {
        const st = ST();
        if (st.inLLMResponse) {
            const idx = st.responseHistory.length - 1;
            if (idx >= 0) {
                const cur = st.responseHistory[idx];
                const cs  = _resolveSource(null);
                if (cs && cur.ctx.source && cs !== cur.ctx.source && !cur.done) {
                    this.completeLLMResponse();
                    this.startLLMResponse(null, cs);
                }
            }
        }
        if (!st.inLLMResponse) this.startLLMResponse(null, null);
        const idx = st.responseHistory.length - 1;
        if (idx < 0) return;
        st.responseHistory[idx].buffer += chunk;
        const el = document.getElementById(`pf-re-txt-${idx}`);
        if (el) el.textContent = st.responseHistory[idx].buffer;
        _smartScroll('pf-response-body');
    };
    VeraChat.prototype.completeLLMResponse = function() {
        const st = ST();
        st.inLLMResponse = false;
        const idx = st.responseHistory.length - 1;
        if (idx < 0) return;
        const entry = st.responseHistory[idx];
        if (entry.done) return;
        entry.done = true;
        if (!entry.filePath) entry.filePath = _extractFilePath(entry.buffer);
        document.getElementById(`pf-re-${idx}`)?.classList.remove('active');
        const s = document.getElementById(`pf-re-st-${idx}`);
        if (s) s.innerHTML = _doneHtml;
        if (entry.filePath) {
            const fl  = _fileLabel(entry.filePath);
            const lbl = document.querySelector(`#pf-re-${idx} .pf-main-lbl`);
            const base = entry.ctx.source || entry.ctx.stageActivity || entry.ctx.stage || 'Response';
            if (lbl && fl) lbl.textContent = `${base} › ${fl}`;
            const block = document.querySelector(`#pf-re-${idx} .pf-label-block`);
            if (block && !block.querySelector('.pf-file-badge')) {
                const b = document.createElement('div');
                b.className = 'pf-file-badge';
                b.textContent = `📄 ${entry.filePath}`;
                block.appendChild(b);
            }
        }
    };

    // ══════════════════════════════════════════════════════════════
    // FLOWCHART
    // ══════════════════════════════════════════════════════════════

    VeraChat.prototype._pfStartRun = function(query) {
        const st = ST();
        st._runCounter = (st._runCounter || 0) + 1;
        const runId = `run-${st._runCounter}`;
        const ts    = _ts();

        st.flowRuns.forEach(r => {
            if (!r.done) {
                r.done = true;
                const prevBody = document.getElementById(`pf-run-body-${r.id}`);
                const prevHdr  = document.getElementById(`pf-run-hdr-${r.id}`);
                if (prevBody) prevBody.classList.add('collapsed');
                if (prevHdr)  prevHdr.querySelector('.pf-run-chev').textContent = '▸';
                const prevEl = document.getElementById(`pf-run-${r.id}`);
                if (prevEl) { prevEl.classList.remove('active'); prevEl.classList.add('done'); }
            }
        });

        const run = {
            id:         runId,
            label:      query ? query.slice(0, 80) : 'Toolchain run',
            ts,
            steps:      {},
            stepOrder:  [],
            planBuffer: '',
            done:       false,
        };
        st.flowRuns.push(run);
        st.activeRunId = runId;

        const cnt = document.getElementById('pf-flowchart-count');
        if (cnt) cnt.textContent = `(${st.flowRuns.length})`;

        this._pfRenderRun(run);

        const panel = document.getElementById('pf-flowchart-panel');
        const body  = document.getElementById('pf-flowchart-body');
        if (panel) panel.style.display = '';
        if (body && body.classList.contains('collapsed')) {
            body.classList.remove('collapsed');
            const ch = document.getElementById('pf-flowchart-chev');
            if (ch) ch.textContent = '▾';
            st.flowchartOpen = true;
        }

        return run;
    };

    VeraChat.prototype._pfRenderRun = function(run) {
        const panelBody = document.getElementById('pf-flowchart-body');
        if (!panelBody) return;

        document.getElementById(`pf-run-${run.id}`)?.remove();

        const statusHtml = run.done ? '<span style="font-size:10px;" class="pf-icon-done">done</span>' : _spinRun;

        const wrap = document.createElement('div');
        wrap.id = `pf-run-${run.id}`;
        wrap.className = `pf-run ${run.done ? 'done' : 'active'}`;

        wrap.innerHTML = `
            <div class="pf-run-hdr" id="pf-run-hdr-${run.id}" onclick="(function(el){
                var b=document.getElementById('pf-run-body-${run.id}');
                b.classList.toggle('collapsed');
                el.querySelector('.pf-run-chev').textContent=b.classList.contains('collapsed')?'▸':'▾';
            })(this)">
                <span class="pf-run-chev">▾</span>
                <span class="pf-run-title" title="${_esc(run.label)}">⚙ ${_esc(run.label)}</span>
                <span class="pf-run-ts">${_esc(run.ts)}</span>
                <span id="pf-run-st-${run.id}" style="margin-left:4px;">${statusHtml}</span>
            </div>
            <div class="pf-run-body" id="pf-run-body-${run.id}">
                <div class="pf-run-plan" id="pf-run-plan-${run.id}" style="${run.planBuffer?'':'display:none'}">
                    <div class="pf-run-plan-lbl">📋 Planning</div>
                    <div class="pf-run-plan-txt" id="pf-run-plan-txt-${run.id}">${_esc(run.planBuffer)}</div>
                </div>
            </div>`;

        panelBody.appendChild(wrap);
        run.stepOrder.forEach(n => this._pfRenderStep(run, run.steps[n]));
        _smartScroll('pf-flowchart-body');
    };

    VeraChat.prototype._pfActiveRun = function() {
        const st = ST();
        if (!st.activeRunId) return null;
        return st.flowRuns.find(r => r.id === st.activeRunId) || null;
    };

    VeraChat.prototype._pfRenderStep = function(run, step) {
        const runBody = document.getElementById(`pf-run-body-${run.id}`);
        if (!runBody) return;

        const domId = `pf-run-${run.id}-step-${step.num}`;
        document.getElementById(domId)?.remove();

        const st  = ST();
        const ctx = {
            stage:st.currentStage, stageActivity:st.stageActivity,
            tool:step.tool, toolInput:step.input,
        };
        const label = _buildLabel(ctx);
        const pill  = st.currentStage || '';
        const fp    = _extractFilePath(step.input);

        const statusHtml = {
            running: _spinRun,
            done:    _doneHtml,
            failed:  _failedHtml,
        };

        const pillHtml = pill ? `<div class="pf-pill">${_esc(pill)}</div>` : '';
        const fileHtml = fp   ? `<div class="pf-file-badge">📄 ${_esc(_fileLabel(fp)||fp)}</div>` : '';

        const wrap = document.createElement('div');
        wrap.id = domId;
        wrap.className = `pf-step-entry ${step.status}`;
        wrap.innerHTML = `
            <div class="pf-entry-hdr" onclick="(function(el){
                var b=el.parentElement.querySelector('.pf-entry-body');
                b.classList.toggle('collapsed');
                el.querySelector('.pf-entry-chev').textContent=b.classList.contains('collapsed')?'▸':'▾';
            })(this)">
                <span class="pf-entry-chev">▾</span>
                <div class="pf-label-block">
                    ${pillHtml}
                    <div class="pf-main-lbl">Step ${step.num} › ${_esc(label)}</div>
                    ${fileHtml}
                </div>
                <div class="pf-entry-meta">
                    <span class="pf-entry-ts">${_esc(step.ts)}</span>
                    <span class="pf-entry-st" id="${domId}-st">${statusHtml[step.status]||'○'}</span>
                </div>
            </div>
            <div class="pf-entry-body">
                <div class="pf-step-input">${_esc((step.input||'').slice(0,400))}${(step.input||'').length>400?'\n…':''}</div>
                <div class="pf-step-output" id="${domId}-out">${_esc(step.outputBuffer)}</div>
                <div class="pf-step-error"  id="${domId}-err" style="${step.error?'':'display:none'}">${_esc(step.error||'')}</div>
            </div>`;

        runBody.appendChild(wrap);
        _smartScroll('pf-flowchart-body');
    };

    VeraChat.prototype.flowchartStepStarted = function(data) {
        const st  = ST();
        const num = data.step_number;
        st.activeCtx.stepNum   = num;
        st.activeCtx.tool      = data.tool_name || '?';
        st.activeCtx.toolInput = data.tool_input || '';

        const run = this._pfActiveRun();
        if (!run) return;

        const step = {
            num,
            tool:         data.tool_name || '?',
            input:        data.tool_input || '',
            outputBuffer: '',
            status:       'running',
            error:        null,
            ts:           _ts(),
        };
        run.steps[num] = step;
        if (!run.stepOrder.includes(num)) run.stepOrder.push(num);

        this._pfRenderStep(run, step);

        const fp  = _extractFilePath(data.tool_input || '');
        const lbl = fp ? `${data.tool_name} › ${_fileLabel(fp)}` : data.tool_name;
        this._pfSep(`Step ${num} › ${lbl}`, '▶');
    };

    VeraChat.prototype.flowchartStepOutput = function(data) {
        const chunk = String(data.chunk ?? '');
        if (!chunk) return;

        const run = this._pfActiveRun();

        if (!data.step_number || data.step_number === 0) {
            if (run) {
                run.planBuffer += chunk;
                const planEl = document.getElementById(`pf-run-plan-${run.id}`);
                const txtEl  = document.getElementById(`pf-run-plan-txt-${run.id}`);
                if (planEl) planEl.style.display = '';
                if (txtEl)  txtEl.appendChild(document.createTextNode(chunk));
                _smartScroll('pf-flowchart-body');
            }
            return;
        }

        const num = data.step_number;
        if (!run) return;
        if (run.steps[num]) run.steps[num].outputBuffer += chunk;
        const domId = `pf-run-${run.id}-step-${num}`;
        const el = document.getElementById(`${domId}-out`);
        if (el) { el.appendChild(document.createTextNode(chunk)); _smartScroll('pf-flowchart-body'); }
    };

    VeraChat.prototype.flowchartStepDone = function(stepNum, status='done', error=null) {
        const st  = ST();
        const run = this._pfActiveRun();
        if (!run) return;

        if (run.steps[stepNum]) {
            run.steps[stepNum].status = status;
            run.steps[stepNum].error  = error;
        }
        if (st.activeCtx.stepNum === stepNum) {
            st.activeCtx.stepNum = st.activeCtx.tool = st.activeCtx.toolInput = null;
        }

        const domId = `pf-run-${run.id}-step-${stepNum}`;
        const wrap  = document.getElementById(domId);
        const stat  = document.getElementById(`${domId}-st`);
        const errEl = document.getElementById(`${domId}-err`);

        if (wrap) { wrap.classList.remove('running','done','failed'); wrap.classList.add(status === 'done' ? 'done' : 'failed'); }
        if (stat) stat.innerHTML = status === 'done' ? _doneHtml : _failedHtml;
        if (errEl && error) { errEl.style.display=''; errEl.textContent=`✕ ${error}`; }
    };

    VeraChat.prototype._pfCompleteRun = function(status='done') {
        const run = this._pfActiveRun();
        if (!run) return;
        run.done = true;
        const wrap = document.getElementById(`pf-run-${run.id}`);
        const stEl = document.getElementById(`pf-run-st-${run.id}`);
        if (wrap) { wrap.classList.remove('active'); wrap.classList.add(status === 'failed' ? 'failed' : 'done'); }
        if (stEl) stEl.innerHTML = status === 'failed'
            ? `<span class="pf-icon-failed" style="font-size:10px;">✕ failed</span>`
            : `<span class="pf-icon-done" style="font-size:10px;">✓ done</span>`;
    };

    VeraChat.prototype.clearFlowchart = function() {
        const st = ST();
        st.flowRuns   = [];
        st.activeRunId = null;
        st._runCounter = 0;
        st.activeCtx.stepNum = st.activeCtx.tool = st.activeCtx.toolInput = null;
        const b = document.getElementById('pf-flowchart-body');
        if (b) b.innerHTML = '';
        const c = document.getElementById('pf-flowchart-count');
        if (c) c.textContent = '';
    };

    // ══════════════════════════════════════════════════════════════
    // WebSocket event router
    // ══════════════════════════════════════════════════════════════
    const _origHandle = VeraChat.prototype.handleFocusEvent;
    VeraChat.prototype.handleFocusEvent = function(ev) {
        // If panels aren't in the DOM yet, buffer the event.
        if (!document.getElementById('pf-console-body')) {
            ST().pendingEvents.push(ev);
            if (_origHandle) _origHandle.call(this, ev);
            return;
        }
        if (_origHandle) _origHandle.call(this, ev);

        const d  = ev.data || {};
        const st = ST();

        switch (ev.type) {
            case 'stage_update':
                this.updateStageStatus(d);
                this._pfSep(`${d.stage}${d.activity?' › '+d.activity:''}`, '◈');
                break;
            case 'stage_progress': this.updateStageProgress(d); break;
            case 'stage_cleared':  this.clearStage();           break;

            case 'workflow_iteration_start':
            case 'workflow_iteration_complete': {
                if (d.iteration != null) {
                    st.activeCtx.iteration = d.iteration;
                    const il = document.getElementById('pf-stage-iter');
                    if (il) il.textContent = `· iter ${d.iteration}`;
                }
                if (ev.type === 'workflow_iteration_complete')
                    this.addStreamOutput(`✅ Iteration ${d.iteration} complete`, 'success');
                break;
            }

            case 'stream_output': this.addStreamOutput(d.text, d.category || 'info'); break;
            case 'tool_output':   this.addStreamOutput(d.message || d.text || String(d), 'tool'); break;
            case 'stage_output':  this.addStreamOutput(d.message || d.text || String(d), d.level || 'info'); break;

            case 'llm_source_changed': st.activeCtx.source = d.source || null; break;

            case 'llm_thought_start': this.startLLMThought(d.timestamp, d.source || null); break;
            case 'llm_thought_chunk': this.appendLLMThought(d.chunk);  break;
            case 'llm_thought_end':   this.completeLLMThought();        break;

            case 'response_start': this.startLLMResponse(d.timestamp, d.source || null); break;
            case 'response_chunk': this.appendLLMResponse(d.chunk);  break;
            case 'response_end':   this.completeLLMResponse();        break;

            case 'flowchart_clear':
                this.clearFlowchart();
                this.addStreamOutput('🧹 Flowchart cleared', 'info');
                break;

            case 'execution_started':
                this._pfStartRun(d.query || d.goal || '');
                this.addStreamOutput('🚀 Toolchain started', 'success');
                this._pfSep('Toolchain execution', '⚙');
                break;

            case 'step_started':
                this.flowchartStepStarted(d);
                this.addStreamOutput(`▶ Step ${d.step_number}: ${d.tool_name}`, 'info');
                break;

            case 'step_output': this.flowchartStepOutput(d); break;

            case 'step_completed':
                this.flowchartStepDone(d.step_number, 'done');
                this.addStreamOutput(`✓ Step ${d.step_number} complete`, 'success');
                break;
            case 'step_failed':
                this.flowchartStepDone(d.step_number, 'failed', d.error);
                this.addStreamOutput(`✕ Step ${d.step_number} failed: ${d.error}`, 'error');
                break;

            case 'execution_completed':
                this._pfCompleteRun('done');
                this.addStreamOutput('🏁 Toolchain complete', 'success');
                break;
            case 'execution_failed':
                this._pfCompleteRun('failed');
                this.addStreamOutput(`❌ Execution failed: ${d.error}`, 'error');
                break;

            case 'workflow_started':
                st.activeCtx.iteration = null;
                this.addStreamOutput('🚀 Workflow started', 'success');
                this._pfSep('Workflow started', '🚀');
                break;
            case 'workflow_completed':
                this.addStreamOutput(`🏁 Workflow completed — ${d.total_iterations} iterations`, 'success');
                this.clearStage();
                break;
            case 'workflow_error':
                this.addStreamOutput(`❌ Workflow error: ${d.error}`, 'error');
                break;
        }
    };

    // ── Auto-init hook ────────────────────────────────────────────
    // Only triggers standalone shell init when V2 layout is NOT active.
    const _origUpdateFocusUI = VeraChat.prototype.updateFocusUI;
    VeraChat.prototype.updateFocusUI = function(p) {
        if (_origUpdateFocusUI) _origUpdateFocusUI.call(this, p);
        // V2 layout calls _fl2InitStatusPanels itself — don't double-init.
        if (!_v2Active()) {
            setTimeout(() => this.initProactiveFocusStatusUI(), 0);
        }
    };

    // ── MutationObserver — standalone only ───────────────────────
    if (typeof MutationObserver !== 'undefined') {
        const ft = document.getElementById('tab-focus');
        if (ft) {
            new MutationObserver(ms => ms.forEach(m => {
                if (m.type === 'attributes' && !m.target.classList.contains('hidden')) {
                    // Only act in standalone mode
                    if (!_v2Active()) {
                        window.app?.initProactiveFocusStatusUI?.();
                    }
                }
            })).observe(ft, {attributes:true, attributeFilter:['class','style']});
        }
    }

    VeraChat.prototype.stopWorkflow = async function() {
        if (!this.sessionId || !confirm('Stop the current workflow?')) return;
        try {
            await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/workflow/stop`, {method:'POST'});
            this.addStreamOutput('⏹️ Stop requested', 'warning');
        } catch(e) { this.addStreamOutput(`Failed to stop: ${e.message}`, 'error'); }
    };

    VeraChat.prototype.toggleStreamConsole = function() { this._pfToggle('console'); };
    VeraChat.prototype.clearStreamConsole  = function() {
        ST().consoleNodes=[];
        const b = document.getElementById('pf-console-body');
        if (b) b.innerHTML='';
    };

    console.log('[ProactiveFocusUI] v3.7 loaded — V2 layout aware, standalone shell suppressed when #focus-layout-v2 present');
})();