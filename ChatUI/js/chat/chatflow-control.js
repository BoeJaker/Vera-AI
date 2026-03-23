// ============================================================
// chat-routing-controls.js  — Vera Chat Routing Controls
// ============================================================

(() => {
    'use strict';

    const MODEL_ROLES = ['fast', 'intermediate', 'deep', 'reasoning'];

    const ROUTE_DESCRIPTIONS = {
        auto:                   '<b>Auto</b> — Triage classifies complexity and picks the best route.',
        simple:                 '<b>Simple</b> — Fast model. Best for short questions and quick lookups.',
        intermediate:           '<b>Intermediate</b> — Balanced depth. Good for most queries.',
        reasoning:              '<b>Reasoning</b> — Step-by-step logical analysis.',
        complex:                '<b>Complex</b> — Deep model. Best for research and detailed explanations.',
        coding:                 '<b>Coding</b> — Optimised for code generation and debugging.',
        toolchain:              '<b>Toolchain</b> — Execute tools and actions.',
        'toolchain-parallel':   '<b>Parallel Tools</b> — Run multiple tools simultaneously.',
        'toolchain-adaptive':   '<b>Adaptive Tools</b> — Multi-step tool workflows, planned on the fly.',
        'toolchain-stepbystep': '<b>Step-by-Step</b> — Sequential tool execution with explicit steps.',
        counsel:                '<b>Counsel</b> — Multiple models deliberate on the same query.',
        model:                  '<b>Specific model</b> — Send directly to any model on the cluster. Bypasses role-based routing.',
    };

    // ── State ─────────────────────────────────────────────────────────
    function safeMode() {
        const v   = localStorage.getItem('rc-mode');
        const old = localStorage.getItem('chat-routing-mode');
        return (v && v !== 'null') ? v : (old && old !== 'null') ? old : 'auto';
    }

    const State = {
        mode:            safeMode(),
        force:           localStorage.getItem('rc-force') === 'true',
        expanded:        localStorage.getItem('rc-expanded') === 'true',
        modelOverride:   localStorage.getItem('rc-model-override') || '',
        counselMode:     localStorage.getItem('rc-counsel-mode') || 'vote',
        counselModels:   (() => {
            try { return JSON.parse(localStorage.getItem('rc-counsel-models')) || ['fast','intermediate','deep']; }
            catch { return ['fast','intermediate','deep']; }
        })(),
        // New: the raw Ollama model name chosen in "model" mode
        specificModel:   localStorage.getItem('rc-specific-model') || '',
    };

    function save(key, val) {
        State[key] = val;
        localStorage.setItem('rc-' + key, typeof val === 'object' ? JSON.stringify(val) : String(val));
    }

    function isCounsel()       { return State.mode === 'counsel'; }
    function isToolchain()     { return typeof State.mode === 'string' && State.mode.startsWith('toolchain'); }
    function isSpecificModel() { return State.mode === 'model'; }

    // ── Cluster model cache ───────────────────────────────────────────
    // Shape: [{ name, instance, size, quant, ctx }]
    let _clusterModels    = [];
    let _clusterFetched   = false;
    let _clusterFetching  = false;

    // Resolve the API base URL at runtime so the fetch works whether the page
    // is loaded via http://, https://, or directly from disk (file://).
    // Priority: explicit data-api-url attribute on the <script> tag that loaded
    // this file, then a global VeraChatConfig.apiBase, then the page origin
    // (works for http/https), then a hardcoded fallback for file:// dev loads.
    function _apiBase() {
        return 'http://llm.int:8888';
    }

    async function fetchClusterModels() {
        if (_clusterFetched || _clusterFetching) return;
        _clusterFetching = true;
        try {
            const res  = await fetch(_apiBase() + '/api/models/cluster');
            const data = await res.json();
            // data expected: { models: [{ name, instance, size, quant, ctx }] }
            _clusterModels  = Array.isArray(data.models) ? data.models : [];
            _clusterFetched = true;
        } catch (err) {
            console.warn('RC: could not fetch cluster models:', err);
            _clusterModels = [];
        } finally {
            _clusterFetching = false;
        }
    }

    // ── HTML builders ─────────────────────────────────────────────────

    function buildModelOptions(selected, includeAuto) {
        selected = selected || '';
        const opts = includeAuto ? [['', '— default —']] : [];
        MODEL_ROLES.forEach(r => opts.push([r, r.charAt(0).toUpperCase() + r.slice(1)]));
        return opts.map(([v, l]) =>
            `<option value="${v}"${v === selected ? ' selected' : ''}>${l}</option>`
        ).join('');
    }

    function buildCounselModelRows() {
        return State.counselModels.map((role, i) => `
            <div class="rc-counsel-row" data-idx="${i}">
                <select class="rc-select rc-counsel-model" data-idx="${i}">
                    ${MODEL_ROLES.map(r =>
                        `<option value="${r}"${r === role ? ' selected' : ''}>${r}</option>`
                    ).join('')}
                </select>
                <button class="rc-icon-btn rc-remove-counsel" data-idx="${i}" title="Remove">✕</button>
            </div>
        `).join('');
    }

    function buildClusterModelOptions() {
        if (!_clusterFetched) {
            return `<option value="">Loading models…</option>`;
        }
        if (_clusterModels.length === 0) {
            return `<option value="">No models found</option>`;
        }
        // Group by instance name
        const groups = {};
        _clusterModels.forEach(m => {
            const inst = m.instance || 'unknown';
            if (!groups[inst]) groups[inst] = [];
            groups[inst].push(m);
        });
        return Object.entries(groups).map(([inst, models]) => `
            <optgroup label="${inst}">
                ${models.map(m => {
                    const label = m.name + (m.size ? `  [${m.size}]` : '');
                    const sel   = m.name === State.specificModel ? ' selected' : '';
                    return `<option value="${m.name}"${sel}>${label}</option>`;
                }).join('')}
            </optgroup>
        `).join('');
    }

    function buildSpecificModelMeta() {
        if (!_clusterFetched || !State.specificModel) return '';
        const m = _clusterModels.find(x => x.name === State.specificModel);
        if (!m) return '';
        const instClass = (m.instance === 'remote' || m.instance === 'gpu') ? 'rc-badge-gpu' : 'rc-badge-cpu';
        return `
            <div class="rc-section" id="rc-model-meta">
                <span class="rc-field-label">Details</span>
                <span class="rc-badge ${instClass}">${m.instance || '?'}</span>
                ${m.size  ? `<span class="rc-badge rc-badge-neutral">${m.size}</span>` : ''}
                ${m.quant ? `<span class="rc-badge rc-badge-neutral">${m.quant}</span>` : ''}
                ${m.ctx   ? `<span class="rc-badge rc-badge-neutral">${m.ctx} ctx</span>` : ''}
            </div>
        `;
    }

    function opt(val, label, cur) {
        return `<option value="${val}"${cur === val ? ' selected' : ''}>${label}</option>`;
    }

    function buildPanel() {
        const m = State.mode;
        return `
        <div class="rc-header">
            <span class="rc-label">Route</span>
            <select id="rc-mode" class="rc-select rc-mode-select">
                <optgroup label="Auto">
                    ${opt('auto',                   'Auto',         m)}
                </optgroup>
                <optgroup label="Direct">
                    ${opt('simple',                 'Simple',        m)}
                    ${opt('intermediate',           'Intermediate',  m)}
                    ${opt('reasoning',              'Reasoning',     m)}
                    ${opt('complex',                'Complex',       m)}
                    ${opt('coding',                 'Coding',        m)}
                </optgroup>
                <optgroup label="Toolchain">
                    ${opt('toolchain',              'Toolchain',       m)}
                    ${opt('toolchain-parallel',     'Parallel',      m)}
                    ${opt('toolchain-adaptive',     'Adaptive',        m)}
                    ${opt('toolchain-stepbystep',   'Step-by-Step',    m)}
                </optgroup>
                <optgroup label="Model">
                    ${opt('model',                  'Specific model',  m)}
                </optgroup>
                <optgroup label="Counsel">
                    ${opt('counsel',                'Counsel',         m)}
                </optgroup>
            </select>
            <button id="rc-toggle" class="rc-icon-btn" title="Options">${State.expanded ? '▼' : '▶'}</button>
        </div>

        <div id="rc-body" class="rc-body" style="display:${State.expanded ? 'block' : 'none'}">

            <div class="rc-desc" id="rc-desc">${ROUTE_DESCRIPTIONS[m] || ''}</div>

            <div class="rc-section">
                <label class="rc-check-label">
                    <input type="checkbox" id="rc-force"${State.force ? ' checked' : ''}>
                    Force route (skip triage)
                </label>
            </div>

            <!-- Model override — hidden for counsel and specific-model modes -->
            <div class="rc-section" id="rc-model-override-section"
                 style="display:${isCounsel() || isSpecificModel() ? 'none' : 'flex'}">
                <label class="rc-field-label">Responding model</label>
                <select id="rc-model-override" class="rc-select">
                    ${buildModelOptions(State.modelOverride, true)}
                </select>
            </div>

            <!-- Specific model picker -->
            <div id="rc-specific-model-section"
                 style="display:${isSpecificModel() ? 'flex' : 'none'};flex-direction:column;gap:8px;">
                <div class="rc-section">
                    <label class="rc-field-label">Model</label>
                    <select id="rc-specific-model" class="rc-select">
                        ${buildClusterModelOptions()}
                    </select>
                </div>
                ${buildSpecificModelMeta()}
            </div>

            <!-- Counsel config -->
            <div id="rc-counsel-section" style="display:${isCounsel() ? 'block' : 'none'}">
                <div class="rc-section">
                    <label class="rc-field-label">Deliberation</label>
                    <select id="rc-counsel-mode" class="rc-select">
                        ${opt('vote',      'Vote — judge picks best',     State.counselMode)}
                        ${opt('synthesis', 'Synthesis — combine all',      State.counselMode)}
                        ${opt('debate',    'Debate — rebut + moderate',    State.counselMode)}
                        ${opt('race',      'Race — fastest wins',          State.counselMode)}
                    </select>
                </div>
                <div class="rc-section" style="flex-direction:column; align-items:stretch;">
                    <div class="rc-field-label-row">
                        <label class="rc-field-label">Participants</label>
                        <button id="rc-add-counsel" class="rc-text-btn">+ Add</button>
                    </div>
                    <div id="rc-counsel-models">${buildCounselModelRows()}</div>
                </div>
            </div>

        </div>`;
    }

    // ── Events ────────────────────────────────────────────────────────

    function wireEvents(root) {
        root.querySelector('#rc-mode').addEventListener('change', e => {
            save('mode', e.target.value);
            if (isSpecificModel() && !_clusterFetched) {
                // Kick off fetch and repopulate when done
                fetchClusterModels().then(() => refreshSpecificModelPicker(root));
            }
            refreshBody(root);
        });

        root.querySelector('#rc-toggle').addEventListener('click', () => {
            save('expanded', !State.expanded);
            refreshBody(root);
        });

        root.querySelector('#rc-force').addEventListener('change', e => {
            save('force', e.target.checked);
        });

        root.querySelector('#rc-model-override').addEventListener('change', e => {
            save('modelOverride', e.target.value);
        });

        // Specific model selection
        root.querySelector('#rc-specific-model').addEventListener('change', e => {
            save('specificModel', e.target.value);
            refreshModelMeta(root);
        });

        root.querySelector('#rc-counsel-mode').addEventListener('change', e => {
            save('counselMode', e.target.value);
        });

        root.querySelector('#rc-counsel-models').addEventListener('change', e => {
            const el = e.target.closest('.rc-counsel-model');
            if (!el) return;
            const updated = [...State.counselModels];
            updated[+el.dataset.idx] = el.value;
            save('counselModels', updated);
        });

        root.querySelector('#rc-counsel-models').addEventListener('click', e => {
            const btn = e.target.closest('.rc-remove-counsel');
            if (!btn) return;
            if (State.counselModels.length <= 2) return;
            const updated = State.counselModels.filter((_, i) => i !== +btn.dataset.idx);
            save('counselModels', updated);
            refreshCounselRows(root);
        });

        root.querySelector('#rc-add-counsel').addEventListener('click', () => {
            if (State.counselModels.length >= 6) return;
            save('counselModels', [...State.counselModels, 'fast']);
            refreshCounselRows(root);
        });
    }

    function refreshBody(root) {
        root.querySelector('#rc-toggle').textContent = State.expanded ? '▼' : '▶';

        const body = root.querySelector('#rc-body');
        if (body) body.style.display = State.expanded ? 'block' : 'none';

        const desc = root.querySelector('#rc-desc');
        if (desc) desc.innerHTML = ROUTE_DESCRIPTIONS[State.mode] || '';

        const overrideSection      = root.querySelector('#rc-model-override-section');
        const counselSection       = root.querySelector('#rc-counsel-section');
        const specificModelSection = root.querySelector('#rc-specific-model-section');

        if (overrideSection)      overrideSection.style.display      = (isCounsel() || isSpecificModel()) ? 'none' : 'flex';
        if (counselSection)       counselSection.style.display        = isCounsel()       ? 'block' : 'none';
        if (specificModelSection) specificModelSection.style.display  = isSpecificModel() ? 'flex'  : 'none';
    }

    function refreshSpecificModelPicker(root) {
        const sel = root.querySelector('#rc-specific-model');
        if (!sel) return;
        sel.innerHTML = buildClusterModelOptions();
        // If nothing selected yet, default to first model
        if (!State.specificModel && _clusterModels.length > 0) {
            save('specificModel', _clusterModels[0].name);
            sel.value = State.specificModel;
        }
        refreshModelMeta(root);
    }

    function refreshModelMeta(root) {
        // Remove old meta row if present
        const old = root.querySelector('#rc-model-meta');
        if (old) old.remove();
        const section = root.querySelector('#rc-specific-model-section');
        if (!section) return;
        const html = buildSpecificModelMeta();
        if (html) section.insertAdjacentHTML('beforeend', html);
    }

    function refreshCounselRows(root) {
        const c = root.querySelector('#rc-counsel-models');
        if (c) c.innerHTML = buildCounselModelRows();
    }

    // ── getRoutingConfig ──────────────────────────────────────────────

    VeraChat.prototype.getRoutingConfig = function () {
        const cfg = {
            mode:  State.mode || 'auto',
            force: !!State.force,
        };

        if (isSpecificModel()) {
            // Tell the backend to use a raw model name
            cfg.specific_model = State.specificModel || '';
            // Always force when a specific model is chosen — triage is meaningless here
            cfg.force = true;
        } else if (State.mode !== 'auto' && State.modelOverride && !isCounsel()) {
            cfg.model_override = State.modelOverride;
        }

        if (isCounsel()) {
            cfg.counsel_mode = State.counselMode || 'vote';
            cfg.models       = Array.isArray(State.counselModels)
                ? [...State.counselModels]
                : ['fast', 'intermediate', 'deep'];
        }

        return cfg;
    };

    Object.defineProperty(VeraChat.prototype, 'routingMode', {
        get() { return State.mode || 'auto'; },
        set(v) { save('mode', v || 'auto'); },
        configurable: true,
    });

    // ── Mount ─────────────────────────────────────────────────────────

    VeraChat.prototype.addRoutingControls = function () {
        document.getElementById('rc-panel')?.remove();
        document.getElementById('routing-controls')?.remove();

        const panel = document.createElement('div');
        panel.id        = 'rc-panel';
        panel.className = 'rc-panel';
        panel.innerHTML = buildPanel();

        const messageInput = document.getElementById('messageInput');
        const inputArea    = document.querySelector('.input-area');

        if (messageInput) {
            const wrapper = messageInput.closest('.message-input-wrapper') || messageInput.parentElement;
            if (wrapper?.parentElement) {
                wrapper.parentElement.insertBefore(panel, wrapper);
            } else {
                messageInput.parentElement.insertBefore(panel, messageInput);
            }
        } else if (inputArea) {
            inputArea.insertBefore(panel, inputArea.firstChild);
        } else {
            document.body.appendChild(panel);
        }

        wireEvents(panel);
        injectStyles();

        // If we're already in model mode (persisted from last session), fetch now
        if (isSpecificModel() && !_clusterFetched) {
            fetchClusterModels().then(() => refreshSpecificModelPicker(panel));
        }

        console.log('✅ Routing controls mounted, mode:', State.mode);
    };

    // ── Init hook ─────────────────────────────────────────────────────

    if (!VeraChat.prototype._rcWrapped) {
        const _orig = VeraChat.prototype.init;
        if (_orig) {
            VeraChat.prototype.init = async function (...args) {
                const r = await _orig.apply(this, args);
                setTimeout(() => this.addRoutingControls(), 400);
                return r;
            };
        }
        VeraChat.prototype._rcWrapped = true;
    }

    if (typeof app !== 'undefined' && app) {
        setTimeout(() => app.addRoutingControls?.(), 800);
    }

    // ── Styles ────────────────────────────────────────────────────────

    function injectStyles() {
        if (document.getElementById('rc-styles')) return;
        const s = document.createElement('style');
        s.id = 'rc-styles';
        s.textContent = `
        .rc-panel {
            background: var(--panel-bg, #1a2235);
            border: 1px solid var(--border, #2d3f5c);
            border-radius: 10px;
            margin-bottom: 10px;
            font-size: 13px;
            color: var(--text, #d4dff0);
            overflow: hidden;
        }
        .rc-header {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 12px;
            background: var(--bg, #0f1a2e);
        }
        .rc-label {
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 1px;
            text-transform: uppercase;
            color: var(--text-muted, #6b7fa3);
            white-space: nowrap;
        }
        .rc-mode-select { flex: 1; }
        .rc-select {
            padding: 5px 28px 5px 9px;
            background: var(--panel-bg, #1a2235);
            border: 1px solid var(--border, #2d3f5c);
            border-radius: 6px;
            color: var(--text, #d4dff0);
            font-size: 13px;
            cursor: pointer;
            appearance: none;
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='10' viewBox='0 0 10 10'%3E%3Cpath fill='%236b7fa3' d='M5 7L1 3h8z'/%3E%3C/svg%3E");
            background-repeat: no-repeat;
            background-position: right 8px center;
            width: 100%;
        }
        .rc-select:focus {
            outline: none;
            border-color: var(--accent, #3b82f6);
            box-shadow: 0 0 0 2px rgba(59,130,246,.15);
        }
        .rc-select option { background: var(--panel-bg, #1a2235); }
        .rc-icon-btn {
            flex-shrink: 0;
            width: 28px; height: 28px;
            display: flex; align-items: center; justify-content: center;
            background: transparent;
            border: 1px solid var(--border, #2d3f5c);
            border-radius: 6px;
            color: var(--text-muted, #6b7fa3);
            cursor: pointer;
            font-size: 12px;
            transition: all .15s;
            padding: 0;
        }
        .rc-icon-btn:hover {
            border-color: var(--accent, #3b82f6);
            color: var(--text, #d4dff0);
            background: var(--bg, #0f1a2e);
        }
        .rc-text-btn {
            background: transparent;
            border: 1px dashed var(--border, #2d3f5c);
            border-radius: 5px;
            color: var(--accent, #3b82f6);
            font-size: 12px;
            padding: 3px 8px;
            cursor: pointer;
            transition: all .15s;
        }
        .rc-text-btn:hover {
            background: rgba(59,130,246,.08);
            border-color: var(--accent, #3b82f6);
        }
        .rc-body {
            padding: 10px 12px 12px;
            border-top: 1px solid var(--border, #2d3f5c);
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        .rc-desc {
            font-size: 12px;
            color: var(--text-muted, #6b7fa3);
            line-height: 1.5;
            padding: 8px 10px;
            background: var(--bg, #0f1a2e);
            border-radius: 6px;
            border-left: 3px solid var(--accent, #3b82f6);
        }
        .rc-desc b { color: var(--text, #d4dff0); }
        .rc-section {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .rc-field-label {
            font-size: 11px;
            font-weight: 600;
            letter-spacing: .5px;
            text-transform: uppercase;
            color: var(--text-muted, #6b7fa3);
            white-space: nowrap;
            flex-shrink: 0;
            min-width: 100px;
        }
        .rc-field-label-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 6px;
        }
        .rc-check-label {
            display: flex;
            align-items: center;
            gap: 7px;
            cursor: pointer;
            color: var(--text, #d4dff0);
            font-size: 12px;
        }
        .rc-check-label input[type=checkbox] {
            width: 14px; height: 14px;
            accent-color: var(--accent, #3b82f6);
            cursor: pointer;
        }
        #rc-counsel-section {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        .rc-counsel-row {
            display: flex;
            align-items: center;
            gap: 6px;
            margin-bottom: 5px;
        }
        .rc-counsel-row .rc-select { flex: 1; }
        .rc-remove-counsel { width: 24px; height: 24px; font-size: 10px; }
        .rc-remove-counsel:hover { border-color: #ef4444; color: #ef4444; }

        /* ── Specific-model mode ── */
        #rc-specific-model-section {
            flex-direction: column;
            gap: 8px;
        }
        .rc-badge {
            display: inline-block;
            font-size: 10px;
            font-weight: 600;
            padding: 2px 7px;
            border-radius: 4px;
            white-space: nowrap;
        }
        .rc-badge-cpu {
            background: rgba(29,158,117,.18);
            color: #1d9e75;
            border: 1px solid rgba(29,158,117,.3);
        }
        .rc-badge-gpu {
            background: rgba(83,74,183,.18);
            color: #8b82e8;
            border: 1px solid rgba(83,74,183,.3);
        }
        .rc-badge-neutral {
            background: var(--bg, #0f1a2e);
            color: var(--text-muted, #6b7fa3);
            border: 1px solid var(--border, #2d3f5c);
        }
        `;
        document.head.appendChild(s);
    }

    console.log('🎛️ Vera Routing Controls loaded, initial mode:', State.mode);
})();