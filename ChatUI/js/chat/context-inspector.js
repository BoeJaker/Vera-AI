// =====================================================================
// Vera Context Inspector — Pre-send editing & post-response inspection
// Integrates with ContextProbe v6 / ContextBuilder backend
//
// v6: ranked_hits primary view, source badges, graph-sub pills
// v7: "Prompt" tab — live render_preview showing exactly which hits
//     reach each ContextBuilder section (pairs / notes / graph),
//     which are dropped by headroom or section caps, and controls
//     to tune all caps live without touching Python.
// =====================================================================

(() => {

// ─────────────────────────────────────────────────────────────────────────────
// State
// ─────────────────────────────────────────────────────────────────────────────

const CI = {
    pendingContext: null,
    pendingEdits: {
        history: null,
        vectors: null,
        focus: null,
        addedContext: '',
        excludeHistory: false,
        excludeVectors: false,
        excludeGraph: false,
    },
    lastResponseContext: null,
    renderPreview: null,       // v7: cached render_preview response
    renderFetching: false,     // v7: loading state for Prompt tab
    renderPromptExpanded: false,

    panelOpen: false,
    activeTab: 'context',
    fetchingContext: false,
    showRawBuckets: false,

    profile: localStorage.getItem('ci-profile') || 'reasoning',
    historyTurns: parseInt(localStorage.getItem('ci-history-turns') || '10'),
    vectorK: parseInt(localStorage.getItem('ci-vector-k') || '6'),
    enableVectorSession:  localStorage.getItem('ci-vec-session')  !== 'false',
    enableVectorLongterm: localStorage.getItem('ci-vec-longterm') !== 'false',
    enableGraph:          localStorage.getItem('ci-graph')        !== 'false',
    autoFetchContext:     localStorage.getItem('ci-auto-fetch')   !== 'false',

    // v7 render config (mirrors RenderConfig on API)
    rc: {
        headroom_multiplier: parseInt(localStorage.getItem('ci-rc-headroom') || '5'),
        max_pairs:           parseInt(localStorage.getItem('ci-rc-pairs')    || '3'),
        max_others:          parseInt(localStorage.getItem('ci-rc-others')   || '5'),
        max_graph:           parseInt(localStorage.getItem('ci-rc-graph')    || '8'),
        q_snippet_chars:     parseInt(localStorage.getItem('ci-rc-qsnip')   || '300'),
        a_snippet_chars:     parseInt(localStorage.getItem('ci-rc-asnip')   || '600'),
        note_snippet_chars:  parseInt(localStorage.getItem('ci-rc-nsnip')   || '400'),
        graph_snippet_chars: parseInt(localStorage.getItem('ci-rc-gsnip')   || '400'),
        debug_badges:        localStorage.getItem('ci-rc-debug') === 'true',
    },
};

// ─────────────────────────────────────────────────────────────────────────────
// Source metadata
// ─────────────────────────────────────────────────────────────────────────────

const SOURCE_META = {
    vector_session:    { label: 'session',        color: '#3b82f6', graphSub: false },
    vector_xsession:   { label: 'x-session',      color: '#60a5fa', graphSub: false },
    graph_rerank:      { label: 'graph rerank',   color: '#8b5cf6', graphSub: true  },
    vector_longterm:   { label: 'long-term',      color: '#0ea5e9', graphSub: false },
    chunk_reassembled: { label: 'reassembled',    color: '#f59e0b', graphSub: true  },
    graph_traverse:    { label: 'graph traverse', color: '#10b981', graphSub: true  },
    keyword_neo4j:     { label: 'keyword',        color: '#06b6d4', graphSub: true  },
    entity_recall:     { label: 'entity recall',  color: '#34d399', graphSub: true  },
    neighbour_swap:    { label: 'neighbour ⇄',    color: '#a78bfa', graphSub: true  },
    recalled_exchange: { label: 'recalled',       color: '#818cf8', graphSub: true  },
};

const BUCKET_META = {
    pair_q:          { label: 'Q (pair)',    color: '#3b82f6' },
    pair_a:          { label: 'A (pair)',    color: '#60a5fa' },
    note:            { label: 'note',        color: '#f59e0b' },
    graph:           { label: 'graph',       color: '#10b981' },
    dropped_cap:     { label: 'dropped/cap', color: '#ef4444' },
    dropped_headroom:{ label: 'dropped/hd',  color: '#f97316' },
};

function srcMeta(source) {
    return SOURCE_META[source] || { label: source || 'unknown', color: '#64748b', graphSub: false };
}

// ─────────────────────────────────────────────────────────────────────────────
// Backend API calls
// ─────────────────────────────────────────────────────────────────────────────

const API_BASE = 'http://llm.int:8888';

async function fetchContextPreview(sessionId, query) {
    CI.fetchingContext = true;
    updateFetchIndicator(true);
    try {
        const res = await fetch(`${API_BASE}/api/context/preview`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: sessionId, query,
                profile: CI.profile,
                history_turns: CI.historyTurns,
                vector_k: CI.vectorK,
                vector_session: CI.enableVectorSession,
                vector_longterm: CI.enableVectorLongterm,
                graph_entities: CI.enableGraph,
            }),
        });
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
        const data = await res.json();
        CI.pendingContext = data;
        resetEdits();
        return data;
    } catch (err) {
        console.warn('[ContextInspector] Preview fetch failed:', err.message);
        CI.pendingContext = null;
        return null;
    } finally {
        CI.fetchingContext = false;
        updateFetchIndicator(false);
    }
}

async function fetchRenderPreview(sessionId, query) {
    CI.renderFetching = true;
    try {
        const res = await fetch(`${API_BASE}/api/context/render_preview`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: sessionId, query,
                stage: CI.profile,
                history_turns: CI.historyTurns,
                vector_k: CI.vectorK,
                vector_session: CI.enableVectorSession,
                vector_longterm: CI.enableVectorLongterm,
                graph_entities: CI.enableGraph,
                render_config: CI.rc,
            }),
        });
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
        CI.renderPreview = await res.json();
    } catch (err) {
        console.warn('[ContextInspector] Render preview fetch failed:', err.message);
        CI.renderPreview = null;
    } finally {
        CI.renderFetching = false;
    }
}

async function fetchMemoryBrowser(sessionId, query = '') {
    try {
        const params = new URLSearchParams({ session_id: sessionId });
        if (query) params.set('query', query);
        const res = await fetch(`${API_BASE}/api/context/memory?${params}`);
        if (!res.ok) throw new Error(res.statusText);
        return await res.json();
    } catch (err) {
        console.warn('[ContextInspector] Memory fetch failed:', err.message);
        return null;
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Edit helpers
// ─────────────────────────────────────────────────────────────────────────────

function resetEdits() {
    CI.pendingEdits = {
        history: null, vectors: null, focus: null,
        addedContext: '', excludeHistory: false,
        excludeVectors: false, excludeGraph: false,
    };
}

function buildContextOverride() {
    if (!CI.pendingContext && !CI.pendingEdits.addedContext) return null;
    const override = {
        profile: CI.profile,
        history_turns: CI.historyTurns,
        vector_k: CI.vectorK,
        vector_session: CI.enableVectorSession && !CI.pendingEdits.excludeVectors,
        vector_longterm: CI.enableVectorLongterm && !CI.pendingEdits.excludeVectors,
        graph_entities: CI.enableGraph && !CI.pendingEdits.excludeGraph,
    };
    if (CI.pendingEdits.history !== null)  override.history_override = CI.pendingEdits.history;
    if (CI.pendingEdits.vectors !== null)  override.vectors_override  = CI.pendingEdits.vectors;
    if (CI.pendingEdits.focus   !== null)  override.focus_override    = CI.pendingEdits.focus;
    if (CI.pendingEdits.addedContext)      override.injected_context   = CI.pendingEdits.addedContext;
    if (CI.pendingEdits.excludeHistory)    override.history_turns = 0;
    return override;
}

// ─────────────────────────────────────────────────────────────────────────────
// Patch VeraChat.sendMessage
// ─────────────────────────────────────────────────────────────────────────────

(function patchSendMessage() {
    const _orig = VeraChat.prototype.sendMessage;
    VeraChat.prototype.sendMessage = async function () {
        const input = document.getElementById('messageInput');
        const query = (input?.value || '').trim();
        if (query && (CI.panelOpen || CI.autoFetchContext)) {
            const override = buildContextOverride();
            if (override) this._pendingContextOverride = override;
        }
        return _orig.call(this);
    };
    const _origWS = VeraChat.prototype.sendMessageViaWebSocket;
    VeraChat.prototype.sendMessageViaWebSocket = async function (message) {
        if (this._pendingContextOverride) {
            const override = this._pendingContextOverride;
            this._pendingContextOverride = null;
            if (!this.websocket || this.websocket.readyState !== WebSocket.OPEN) return false;
            try {
                this.websocket.send(JSON.stringify({
                    message, files: Object.keys(this.files || {}),
                    routing: this.getRoutingConfig ? this.getRoutingConfig() : {},
                    context_override: override,
                }));
                return true;
            } catch (e) { console.error('WS send error:', e); return false; }
        }
        return _origWS.call(this, message);
    };
})();

(function patchHandleWS() {
    const _orig = VeraChat.prototype.handleWebSocketMessage;
    VeraChat.prototype.handleWebSocketMessage = function (data) {
        if (data.type === 'complete' && data.context_used) {
            CI.lastResponseContext = data.context_used;
            if (CI.panelOpen) renderPanel();
        }
        return _orig.call(this, data);
    };
})();

// ─────────────────────────────────────────────────────────────────────────────
// Auto-fetch on typing
// ─────────────────────────────────────────────────────────────────────────────

let _debounceTimer = null;

function installInputListener() {
    const input = document.getElementById('messageInput');
    if (!input) return;
    input.addEventListener('input', () => {
        if (!CI.autoFetchContext && !CI.panelOpen) return;
        clearTimeout(_debounceTimer);
        _debounceTimer = setTimeout(async () => {
            const query = input.value.trim();
            if (!query || query.length < 3) return;
            const app = window.app;
            if (!app?.sessionId) return;
            await fetchContextPreview(app.sessionId, query);
            // Auto-refresh render preview if Prompt tab is active
            if (CI.panelOpen && CI.activeTab === 'prompt') {
                await fetchRenderPreview(app.sessionId, query);
            }
            if (CI.panelOpen) renderPanel();
        }, 600);
    });
}

// ─────────────────────────────────────────────────────────────────────────────
// Fetch indicator
// ─────────────────────────────────────────────────────────────────────────────

function updateFetchIndicator(active) {
    let el = document.getElementById('ci-fetch-indicator');
    if (!el) {
        el = document.createElement('div');
        el.id = 'ci-fetch-indicator';
        el.style.cssText = `position:absolute;right:52px;bottom:12px;width:8px;height:8px;border-radius:50%;
            background:var(--accent,#3b82f6);opacity:0;transition:opacity 0.2s;
            animation:ci-pulse 1s ease-in-out infinite;pointer-events:none;z-index:10;`;
        const wrap = document.querySelector('.input-area,.chat-input-container,#messageInput')?.parentElement;
        if (wrap) { wrap.style.position = 'relative'; wrap.appendChild(el); }
    }
    el.style.opacity = active ? '1' : '0';
}

// ─────────────────────────────────────────────────────────────────────────────
// Panel toggle button
// ─────────────────────────────────────────────────────────────────────────────

function installPanelButton() {
    const controlGroup = document.querySelector('.ucb-toolbar');
    if (!controlGroup || document.getElementById('ci-panel-btn')) return;
    const btn = document.createElement('button');
    btn.id = 'ci-panel-btn';
    btn.className = 'ctrl-btn';
    btn.title = 'Context Inspector';
    btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M12 2L2 7l10 5 10-5-10-5z"/>
        <path d="M2 17l10 5 10-5"/>
        <path d="M2 12l10 5 10-5"/>
    </svg>`;
    btn.onclick = () => togglePanel();
    const divider = controlGroup.querySelector('.ctrl-divider');
    if (divider) controlGroup.insertBefore(btn, divider.nextSibling);
    else controlGroup.appendChild(btn);
}

// ─────────────────────────────────────────────────────────────────────────────
// Panel core
// ─────────────────────────────────────────────────────────────────────────────

function togglePanel() {
    CI.panelOpen = !CI.panelOpen;
    document.getElementById('ci-panel-btn')?.classList.toggle('active', CI.panelOpen);
    if (CI.panelOpen) {
        createPanel();
        const query = document.getElementById('messageInput')?.value?.trim();
        if (query && query.length > 2) {
            fetchContextPreview(window.app?.sessionId, query).then(() => renderPanel());
        } else {
            renderPanel();
        }
    } else {
        destroyPanel();
    }
}

function createPanel() {
    if (document.getElementById('ci-panel')) return;
    const panel = document.createElement('div');
    panel.id = 'ci-panel';
    panel.className = 'ci-panel';
    document.body.appendChild(panel);
}

function destroyPanel() {
    const panel = document.getElementById('ci-panel');
    if (panel) { panel.classList.add('ci-panel--closing'); setTimeout(() => panel.remove(), 280); }
}

function renderPanel() {
    const panel = document.getElementById('ci-panel');
    if (!panel) return;
    panel.innerHTML = `
        <div class="ci-header">
            <div class="ci-title">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M12 2L2 7l10 5 10-5-10-5z"/>
                    <path d="M2 17l10 5 10-5"/>
                    <path d="M2 12l10 5 10-5"/>
                </svg>
                Context Inspector
            </div>
            <div class="ci-tabs">
                <button class="ci-tab ${CI.activeTab==='context'?'ci-tab--active':''}" onclick="CI_setTab('context')">Context</button>
                <button class="ci-tab ${CI.activeTab==='prompt'?'ci-tab--active':''}"  onclick="CI_setTab('prompt')">Prompt</button>
                <button class="ci-tab ${CI.activeTab==='memory'?'ci-tab--active':''}"  onclick="CI_setTab('memory')">Memory</button>
                <button class="ci-tab ${CI.activeTab==='settings'?'ci-tab--active':''}" onclick="CI_setTab('settings')">Controls</button>
            </div>
            <button class="ci-close" onclick="CI_close()">✕</button>
        </div>
        <div class="ci-body">
            ${CI.activeTab==='context'  ? renderContextTab()  : ''}
            ${CI.activeTab==='prompt'   ? renderPromptTab()   : ''}
            ${CI.activeTab==='memory'   ? renderMemoryTab()   : ''}
            ${CI.activeTab==='settings' ? renderSettingsTab() : ''}
        </div>
    `;
}

// ─────────────────────────────────────────────────────────────────────────────
// Context tab
// ─────────────────────────────────────────────────────────────────────────────

function renderContextTab() {
    const ctx = CI.pendingContext;
    const lastCtx = CI.lastResponseContext;
    let html = '';

    html += `<div class="ci-section">
        <div class="ci-section-header">
            <span class="ci-section-label">⬆ Pre-send Context</span>
            ${CI.fetchingContext ? `<span class="ci-fetching">fetching…</span>` : ''}
            <button class="ci-refresh-btn" onclick="CI_refreshContext()" title="Re-fetch">↻</button>
        </div>`;
    if (!ctx && !CI.fetchingContext) {
        html += `<div class="ci-empty">No context fetched yet.<br>Type a message to preview.</div>`;
    } else if (ctx) {
        html += renderEditableContext(ctx);
    }
    html += `</div>`;

    html += `<div class="ci-section">
        <div class="ci-section-header"><span class="ci-section-label">➕ Inject Context</span></div>
        <div class="ci-inject-wrap">
            <textarea id="ci-inject-textarea" class="ci-inject-area"
                placeholder="Add extra context, instructions, or documents…"
                oninput="CI_updateInjected(this.value)"
            >${escHtml(CI.pendingEdits.addedContext)}</textarea>
        </div>
    </div>`;

    if (lastCtx) {
        html += `<div class="ci-section">
            <div class="ci-section-header"><span class="ci-section-label">⬇ Last Response — Context Used</span></div>
            ${renderReadonlyContext(lastCtx)}
        </div>`;
    }

    return html;
}

function renderEditableContext(ctx) {
    let html = '';

    // Focus
    const focus = CI.pendingEdits.focus !== null ? CI.pendingEdits.focus : (ctx.focus || '');
    html += `<div class="ci-field">
        <label class="ci-label">Focus ${ctx.focus ? '' : '<span class="ci-badge ci-badge--empty">empty</span>'}</label>
        <input class="ci-input" value="${escHtml(focus)}" oninput="CI_editFocus(this.value)" placeholder="No focus set">
    </div>`;

    // History
    const historyItems = CI.pendingEdits.history !== null ? CI.pendingEdits.history : (ctx.history || []);
    html += `<div class="ci-field">
        <div class="ci-label-row">
            <label class="ci-label">History <span class="ci-badge">${historyItems.length} turns</span></label>
            <label class="ci-toggle-label">
                <input type="checkbox" ${CI.pendingEdits.excludeHistory ? 'checked' : ''}
                       onchange="CI_toggleExclude('history',this.checked)"> exclude
            </label>
        </div>
        <div class="ci-history-list ${CI.pendingEdits.excludeHistory ? 'ci-excluded' : ''}">
            ${historyItems.length === 0
                ? '<div class="ci-empty-item">No history</div>'
                : historyItems.map((turn, i) => `
                    <div class="ci-history-item" data-index="${i}">
                        <span class="ci-role ci-role--${(turn.role||'system').toLowerCase()}">${escHtml(turn.role||'System')}</span>
                        <span class="ci-turn-text" contenteditable="true"
                              onblur="CI_editHistory(${i},this.innerText)">${escHtml(turn.text||'')}</span>
                        <button class="ci-remove-btn" onclick="CI_removeHistory(${i})" title="Remove">✕</button>
                    </div>`).join('')
            }
        </div>
    </div>`;

    // Ranked hits
    const rankedHits = ctx.vectors?.ranked_hits || [];
    const graphSubCount = rankedHits.filter(h => srcMeta(h.source).graphSub).length;
    html += `<div class="ci-field">
        <div class="ci-label-row">
            <label class="ci-label">
                Memory Hits <span class="ci-badge">${rankedHits.length}</span>
                ${graphSubCount > 0
                    ? `<span class="ci-badge ci-badge--graph" title="${graphSubCount} hits substituted from graph strategies">⇄ ${graphSubCount} graph</span>`
                    : ''}
            </label>
            <label class="ci-toggle-label">
                <input type="checkbox" ${CI.pendingEdits.excludeVectors ? 'checked' : ''}
                       onchange="CI_toggleExclude('vectors',this.checked)"> exclude
            </label>
        </div>
        <div class="ci-ranked-list ${CI.pendingEdits.excludeVectors ? 'ci-excluded' : ''}">
            ${rankedHits.length === 0
                ? '<div class="ci-empty-item">No ranked hits</div>'
                : rankedHits.map((h, i) => {
                    const sm = srcMeta(h.source);
                    return `<div class="ci-ranked-item ${sm.graphSub ? 'ci-ranked-item--graph' : ''}">
                        <div class="ci-ranked-meta">
                            <span class="ci-source-badge" style="background:${sm.color}22;color:${sm.color};border-color:${sm.color}55">${sm.label}</span>
                            ${sm.graphSub ? `<span class="ci-graph-sub-pill">⇄ graph sub</span>` : ''}
                            <span class="ci-ranked-score">${((h.score||0)*100).toFixed(0)}%</span>
                            ${h.vector_score > 0 ? `<span class="ci-score-detail">v:${((h.vector_score||0)*100).toFixed(0)}%</span>` : ''}
                            ${h.graph_score  > 0 ? `<span class="ci-score-detail" style="color:#10b981">g:${((h.graph_score||0)*100).toFixed(0)}%</span>` : ''}
                            <button class="ci-remove-btn" onclick="CI_removeRanked(${i})" title="Exclude">✕</button>
                        </div>
                        <div class="ci-ranked-text">${escHtml((h.text||'').substring(0,160))}${(h.text||'').length>160?'…':''}</div>
                    </div>`;
                }).join('')
            }
        </div>
    </div>`;

    // Raw buckets
    const sessionCount  = (ctx.vectors?.session_hits  || []).length;
    const longtermCount = (ctx.vectors?.longterm_hits || []).length;
    if (sessionCount + longtermCount > 0) {
        html += `<div class="ci-field">
            <div class="ci-label-row">
                <label class="ci-label" style="cursor:pointer" onclick="CI_toggleRawBuckets()">
                    Raw Buckets <span class="ci-badge">${sessionCount} session / ${longtermCount} long-term</span>
                    <span style="opacity:.5;font-size:9px">${CI.showRawBuckets ? '▲' : '▼'}</span>
                </label>
            </div>
            ${CI.showRawBuckets ? `
            <div class="ci-vector-list">
                ${(ctx.vectors.session_hits||[]).map(h => `
                    <div class="ci-vector-item">
                        <div class="ci-source-badge" style="background:#3b82f622;color:#3b82f6;border-color:#3b82f655">session</div>
                        <div class="ci-vector-score">${((h.score||0)*100).toFixed(0)}%</div>
                        <div class="ci-vector-text">${escHtml((h.text||'').substring(0,120))}…</div>
                    </div>`).join('')}
                ${(ctx.vectors.longterm_hits||[]).map(h => `
                    <div class="ci-vector-item">
                        <div class="ci-source-badge" style="background:#0ea5e922;color:#0ea5e9;border-color:#0ea5e955">long-term</div>
                        <div class="ci-vector-score">${((h.score||0)*100).toFixed(0)}%</div>
                        <div class="ci-vector-text">${escHtml((h.text||'').substring(0,120))}…</div>
                    </div>`).join('')}
            </div>` : ''}
        </div>`;
    }

    // Graph entities
    if (ctx.graph?.entities?.length > 0 || ctx.graph?.focus_entities?.length > 0) {
        html += `<div class="ci-field">
            <div class="ci-label-row">
                <label class="ci-label">Graph Entities <span class="ci-badge">${ctx.graph.entities.length}</span></label>
                <label class="ci-toggle-label">
                    <input type="checkbox" ${CI.pendingEdits.excludeGraph ? 'checked' : ''}
                           onchange="CI_toggleExclude('graph',this.checked)"> exclude
                </label>
            </div>
            <div class="ci-entity-list ${CI.pendingEdits.excludeGraph ? 'ci-excluded' : ''}">
                ${(ctx.graph.focus_entities||[]).map(e => `<span class="ci-entity ci-entity--focus">${escHtml(e)}</span>`).join('')}
                ${(ctx.graph.entities||[]).slice(0,12).map(e => `<span class="ci-entity" title="${escHtml(e.label||'')}">${escHtml(e.text||'')}</span>`).join('')}
            </div>
        </div>`;
    }

    if (ctx.elapsed_ms) {
        html += `<div class="ci-timing">Fetched in ${ctx.elapsed_ms.toFixed(0)}ms — profile: <strong>${ctx.stage||CI.profile}</strong></div>`;
    }
    return html;
}

function renderReadonlyContext(ctx) {
    let html = '<div class="ci-readonly">';
    if (ctx.focus) html += `<div class="ci-ro-field"><span class="ci-ro-label">Focus</span> ${escHtml(ctx.focus)}</div>`;
    if (ctx.history?.length) {
        html += `<div class="ci-ro-field"><span class="ci-ro-label">History (${ctx.history.length} turns)</span>
            <div class="ci-ro-history">
            ${ctx.history.map(t => `<div class="ci-ro-turn"><em>${escHtml(t.role)}:</em> ${escHtml((t.text||'').substring(0,120))}${(t.text||'').length>120?'…':''}</div>`).join('')}
            </div></div>`;
    }
    const ranked = ctx.vectors?.ranked_hits || [];
    const vecs   = ranked.length ? ranked : [...(ctx.vectors?.session_hits||[]),...(ctx.vectors?.longterm_hits||[])];
    if (vecs.length) {
        const graphSubCount = ranked.filter(h => srcMeta(h.source).graphSub).length;
        html += `<div class="ci-ro-field">
            <span class="ci-ro-label">Memory hits (${vecs.length}) ${graphSubCount > 0 ? `<span class="ci-badge ci-badge--graph">⇄ ${graphSubCount} graph</span>` : ''}</span>
            ${vecs.slice(0,5).map(h => {
                const sm = srcMeta(h.source);
                return `<div class="ci-ro-vec">
                    <span class="ci-source-badge" style="background:${sm.color}22;color:${sm.color};border-color:${sm.color}55;font-size:8px">${sm.label}</span>
                    ${((h.score||0)*100).toFixed(0)}% — ${escHtml((h.text||'').substring(0,90))}…
                </div>`;
            }).join('')}
        </div>`;
    }
    if (ctx.elapsed_ms) html += `<div class="ci-timing">Retrieved in ${ctx.elapsed_ms.toFixed(0)}ms</div>`;
    html += '</div>';
    return html;
}

// ─────────────────────────────────────────────────────────────────────────────
// Prompt tab (v7)
// ─────────────────────────────────────────────────────────────────────────────

function renderPromptTab() {
    const rp = CI.renderPreview;
    let html = '';

    // ── Cap controls ─────────────────────────────────────────────────────────
    html += `<div class="ci-section">
        <div class="ci-section-header">
            <span class="ci-section-label">Render Caps</span>
            <button class="ci-refresh-btn" onclick="CI_refreshRenderPreview()" title="Re-run">↻</button>
            ${CI.renderFetching ? `<span class="ci-fetching">rendering…</span>` : ''}
        </div>
        <div class="ci-caps-grid">
            ${rcSlider('headroom_multiplier','Headroom ×', 1, 20)}
            ${rcSlider('max_pairs',          'Max pairs',  0, 20)}
            ${rcSlider('max_others',         'Max notes',  0, 20)}
            ${rcSlider('max_graph',          'Max graph',  0, 30)}
        </div>
        <div class="ci-caps-adv" id="ci-caps-adv" style="display:none">
            ${rcSlider('q_snippet_chars',    'Q snippet chars',    50, 2000, 50)}
            ${rcSlider('a_snippet_chars',    'A snippet chars',    50, 4000, 50)}
            ${rcSlider('note_snippet_chars', 'Note snippet chars', 50, 2000, 50)}
            ${rcSlider('graph_snippet_chars','Graph snippet chars',50, 2000, 50)}
            <label class="ci-toggle-row" style="padding:4px 10px">
                <span style="font-size:11px;color:var(--text-muted,#94a3b8)">Debug badges in prompt</span>
                <input type="checkbox" ${CI.rc.debug_badges?'checked':''} onchange="CI_setRc('debug_badges',this.checked)">
            </label>
        </div>
        <div style="padding:4px 10px">
            <button class="ci-action-btn" style="font-size:10px;padding:3px 8px"
                    onclick="document.getElementById('ci-caps-adv').style.display=document.getElementById('ci-caps-adv').style.display==='none'?'block':'none'">
                ⚙ advanced…
            </button>
        </div>
    </div>`;

    if (!rp && !CI.renderFetching) {
        const q = document.getElementById('messageInput')?.value?.trim() || '';
        html += `<div class="ci-section">
            <div class="ci-empty">
                ${q ? `<button class="ci-action-btn" onclick="CI_refreshRenderPreview()">▶ Run render preview</button>` : 'Type a message, then click ▶ to see what the builder renders.'}
            </div>
        </div>`;
        return html;
    }

    if (!rp) return html;

    // ── Funnel summary ────────────────────────────────────────────────────────
    const totalUsed   = rp.sections.reduce((s, sec) => s + sec.hits_used.length,    0);
    const totalDropped= rp.sections.reduce((s, sec) => s + sec.hits_dropped.length, 0);
    const pct = rp.ranked_hits_fed > 0 ? Math.round(totalUsed / rp.ranked_hits_fed * 100) : 0;

    html += `<div class="ci-section">
        <div class="ci-section-header"><span class="ci-section-label">Funnel</span>
            <span style="font-size:10px;color:var(--text-muted,#64748b);margin-left:auto">${rp.elapsed_ms?.toFixed(0)}ms</span>
        </div>
        <div class="ci-funnel">
            <div class="ci-funnel-row">
                <span class="ci-funnel-label">Probe fetched</span>
                <span class="ci-funnel-val">${rp.ranked_hits_total}</span>
                <div class="ci-funnel-bar"><div style="width:100%;background:#3b82f6;height:6px;border-radius:3px"></div></div>
            </div>
            <div class="ci-funnel-row">
                <span class="ci-funnel-label">Fed to builder</span>
                <span class="ci-funnel-val">${rp.ranked_hits_fed}</span>
                <div class="ci-funnel-bar"><div style="width:${rp.ranked_hits_total>0?Math.round(rp.ranked_hits_fed/rp.ranked_hits_total*100):0}%;background:#8b5cf6;height:6px;border-radius:3px"></div></div>
            </div>
            ${rp.ranked_hits_dropped_headroom > 0 ? `
            <div class="ci-funnel-row ci-funnel-row--warn">
                <span class="ci-funnel-label">⚠ Dropped (headroom)</span>
                <span class="ci-funnel-val ci-funnel-val--warn">${rp.ranked_hits_dropped_headroom}</span>
                <div class="ci-funnel-bar"><div style="width:${Math.round(rp.ranked_hits_dropped_headroom/rp.ranked_hits_total*100)}%;background:#f97316;height:6px;border-radius:3px"></div></div>
            </div>` : ''}
            <div class="ci-funnel-row">
                <span class="ci-funnel-label">Rendered (all sections)</span>
                <span class="ci-funnel-val" style="color:#34d399">${totalUsed}</span>
                <div class="ci-funnel-bar"><div style="width:${pct}%;background:#10b981;height:6px;border-radius:3px"></div></div>
            </div>
            ${totalDropped > 0 ? `
            <div class="ci-funnel-row ci-funnel-row--warn">
                <span class="ci-funnel-label">⚠ Dropped (section caps)</span>
                <span class="ci-funnel-val ci-funnel-val--warn">${totalDropped}</span>
                <div class="ci-funnel-bar"><div style="width:${rp.ranked_hits_fed>0?Math.round(totalDropped/rp.ranked_hits_fed*100):0}%;background:#ef4444;height:6px;border-radius:3px"></div></div>
            </div>` : ''}
        </div>
    </div>`;

    // ── Per-section breakdown ─────────────────────────────────────────────────
    const SECTION_ICONS = { pairs:'💬', notes:'📄', graph:'🕸' };
    for (const sec of rp.sections) {
        const icon    = SECTION_ICONS[sec.section_name] || '▪';
        const dropCnt = sec.hits_dropped.length;
        const useCnt  = sec.hits_used.length;
        const capPct  = sec.cap_applied > 0 ? Math.round(useCnt / sec.cap_applied * 100) : 100;

        html += `<div class="ci-section">
            <div class="ci-section-header">
                <span class="ci-section-label">${icon} ${sec.section_name}</span>
                <span class="ci-sec-stat" style="color:#34d399">${useCnt} used</span>
                ${dropCnt > 0 ? `<span class="ci-sec-stat ci-sec-stat--warn">▼ ${dropCnt} dropped</span>` : ''}
                <span class="ci-sec-stat" style="opacity:.5">cap: ${sec.cap_applied}</span>
            </div>`;

        // Cap fill bar
        html += `<div style="padding:4px 10px 2px">
            <div class="ci-cap-bar-track">
                <div class="ci-cap-bar-fill" style="width:${capPct}%"></div>
                ${dropCnt>0?`<div class="ci-cap-bar-overflow" style="width:${Math.min(100,Math.round(dropCnt/sec.cap_applied*100))}%"></div>`:''}
            </div>
            <div style="font-size:9px;color:var(--text-muted,#475569);margin-top:2px">${useCnt}/${sec.cap_applied} cap slots used${dropCnt>0?` · ${dropCnt} beyond cap`:''}</div>
        </div>`;

        // Used hits
        if (sec.hits_used.length > 0) {
            html += `<div class="ci-sec-hits">`;
            for (const h of sec.hits_used) {
                const sm  = srcMeta(h.source);
                const bm  = BUCKET_META[h.bucket] || {};
                html += `<div class="ci-sec-hit ci-sec-hit--used">
                    <div class="ci-sec-hit-meta">
                        <span class="ci-source-badge" style="background:${sm.color}22;color:${sm.color};border-color:${sm.color}55">${sm.label}</span>
                        <span style="font-size:9px;padding:1px 4px;background:${(bm.color||'#64748b')}22;color:${bm.color||'#64748b'};border-radius:3px">${bm.label||h.bucket}</span>
                        <span class="ci-ranked-score">${((h.score||0)*100).toFixed(0)}%</span>
                    </div>
                    <div class="ci-ranked-text">${escHtml((h.text||'').substring(0,140))}${(h.text||'').length>140?'…':''}</div>
                </div>`;
            }
            html += `</div>`;
        }

        // Dropped hits
        if (sec.hits_dropped.length > 0) {
            html += `<div class="ci-sec-dropped-label">dropped (${sec.hits_dropped.length})</div>
            <div class="ci-sec-hits">`;
            for (const h of sec.hits_dropped) {
                const sm = srcMeta(h.source);
                html += `<div class="ci-sec-hit ci-sec-hit--dropped">
                    <div class="ci-sec-hit-meta">
                        <span class="ci-source-badge" style="background:${sm.color}22;color:${sm.color};border-color:${sm.color}55;opacity:.6">${sm.label}</span>
                        <span style="font-size:9px;color:#ef4444;opacity:.8">${escHtml(h.drop_reason)}</span>
                        <span class="ci-ranked-score" style="opacity:.5">${((h.score||0)*100).toFixed(0)}%</span>
                    </div>
                    <div class="ci-ranked-text" style="opacity:.5">${escHtml((h.text||'').substring(0,120))}${(h.text||'').length>120?'…':''}</div>
                </div>`;
            }
            html += `</div>`;
        }

        // Rendered text (collapsible)
        if (sec.rendered_text.trim()) {
            const secId = `ci-rendered-${sec.section_name}`;
            html += `<div style="padding:4px 10px">
                <button class="ci-action-btn" style="font-size:10px;padding:2px 7px"
                        onclick="const el=document.getElementById('${secId}');el.style.display=el.style.display==='none'?'block':'none'">
                    ≡ rendered text
                </button>
            </div>
            <pre id="${secId}" class="ci-rendered-pre" style="display:none">${escHtml(sec.rendered_text)}</pre>`;
        }

        html += `</div>`;
    }

    // Full prompt toggle
    html += `<div class="ci-section">
        <div class="ci-section-header">
            <span class="ci-section-label">Full Prompt</span>
            <button class="ci-refresh-btn" onclick="CI_toggleFullPrompt()">
                ${CI.renderPromptExpanded ? '▲' : '▼'}
            </button>
        </div>
        ${CI.renderPromptExpanded
            ? `<pre class="ci-rendered-pre ci-rendered-pre--full">${escHtml(rp.full_prompt||'')}</pre>`
            : `<div style="padding:6px 10px;font-size:10px;color:var(--text-muted,#64748b)">${(rp.full_prompt||'').length} chars — click ▼ to expand</div>`
        }
    </div>`;

    return html;
}

function rcSlider(key, label, min, max, step = 1) {
    const val = CI.rc[key];
    const id  = `ci-rc-${key}`;
    return `<label class="ci-label" style="grid-column:1">${label}</label>
    <div class="ci-slider-row" style="grid-column:2">
        <input type="range" min="${min}" max="${max}" step="${step}" value="${val}"
               oninput="CI_setRc('${key}',${step===1?'parseInt':'parseFloat'}(this.value));document.getElementById('${id}').textContent=this.value">
        <span id="${id}" class="ci-slider-val">${val}</span>
    </div>`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Memory browser tab
// ─────────────────────────────────────────────────────────────────────────────

function renderMemoryTab() {
    return `<div class="ci-section">
        <div class="ci-section-header"><span class="ci-section-label">Memory Browser</span></div>
        <div class="ci-mem-search">
            <input class="ci-input" id="ci-mem-query" placeholder="Search memory…"
                   onkeydown="if(event.key==='Enter')CI_browseMemory()">
            <button class="ci-action-btn" onclick="CI_browseMemory()">Search</button>
        </div>
        <div id="ci-mem-results" class="ci-mem-results">
            <div class="ci-empty">Enter a query to search memory.</div>
        </div>
    </div>`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Settings tab
// ─────────────────────────────────────────────────────────────────────────────

function renderSettingsTab() {
    const profiles = ['triage','preamble','general','intermediate','reasoning','action','coding','conclusion'];
    return `
        <div class="ci-section">
            <div class="ci-section-header"><span class="ci-section-label">Context Profile</span></div>
            <div class="ci-settings-grid">
                <label class="ci-label">Stage profile</label>
                <select class="ci-select" onchange="CI_setSetting('profile',this.value)">
                    ${profiles.map(p=>`<option value="${p}" ${CI.profile===p?'selected':''}>${p}</option>`).join('')}
                </select>
                <label class="ci-label">History turns</label>
                <div class="ci-slider-row">
                    <input type="range" min="0" max="12" value="${CI.historyTurns}"
                           oninput="CI_setSetting('historyTurns',parseInt(this.value));document.getElementById('ci-ht-val').textContent=this.value">
                    <span id="ci-ht-val" class="ci-slider-val">${CI.historyTurns}</span>
                </div>
                <label class="ci-label">Vector k</label>
                <div class="ci-slider-row">
                    <input type="range" min="1" max="20" value="${CI.vectorK}"
                           oninput="CI_setSetting('vectorK',parseInt(this.value));document.getElementById('ci-vk-val').textContent=this.value">
                    <span id="ci-vk-val" class="ci-slider-val">${CI.vectorK}</span>
                </div>
            </div>
        </div>

        <div class="ci-section">
            <div class="ci-section-header"><span class="ci-section-label">Memory Sources</span></div>
            <div class="ci-toggles">
                ${ciToggle('enableVectorSession',  CI.enableVectorSession,  'Session vectors')}
                ${ciToggle('enableVectorLongterm', CI.enableVectorLongterm, 'Long-term vectors')}
                ${ciToggle('enableGraph',          CI.enableGraph,          'Graph entities + traversal')}
                ${ciToggle('autoFetchContext',     CI.autoFetchContext,     'Auto-fetch while typing')}
            </div>
        </div>

        <div class="ci-section">
            <div class="ci-section-header"><span class="ci-section-label">Display</span></div>
            <div class="ci-toggles">
                ${ciToggle('showRawBuckets', CI.showRawBuckets, 'Show raw session/longterm buckets')}
            </div>
        </div>

        <div class="ci-section">
            <div class="ci-section-header"><span class="ci-section-label">Actions</span></div>
            <div class="ci-action-row">
                <button class="ci-action-btn" onclick="CI_refreshContext()">↻ Re-fetch</button>
                <button class="ci-action-btn" onclick="CI_clearEdits()">✕ Clear edits</button>
                <button class="ci-action-btn ci-action-btn--danger" onclick="CI_purgeMemory()">🗑 Purge session</button>
            </div>
        </div>

        <div class="ci-section">
            <div class="ci-section-header"><span class="ci-section-label">v6 Graph substitution legend</span></div>
            <div class="ci-legend-grid">
                ${Object.entries(SOURCE_META).map(([k,v])=>`
                    <span class="ci-source-badge" style="background:${v.color}22;color:${v.color};border-color:${v.color}55">${v.label}</span>
                    <span style="font-size:10px;color:var(--text-muted,#64748b)">${v.graphSub?'⇄ graph sub':'vector'}</span>
                `).join('')}
            </div>
        </div>`;
}

function ciToggle(key, value, label) {
    return `<label class="ci-toggle-row">
        <span>${label}</span>
        <input type="checkbox" ${value?'checked':''} onchange="CI_setSetting('${key}',this.checked)">
    </label>`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Global action handlers
// ─────────────────────────────────────────────────────────────────────────────

window.CI_setTab = (tab) => {
    CI.activeTab = tab;
    // Auto-run render preview when switching to Prompt tab if we have a query
    if (tab === 'prompt' && !CI.renderPreview && !CI.renderFetching) {
        const q = document.getElementById('messageInput')?.value?.trim() || '';
        if (q) {
            fetchRenderPreview(window.app?.sessionId, q).then(() => renderPanel());
            return;
        }
    }
    renderPanel();
};

window.CI_close = () => togglePanel();

window.CI_refreshContext = async () => {
    const query = document.getElementById('messageInput')?.value?.trim() || '';
    if (!query) { renderPanel(); return; }
    await fetchContextPreview(window.app?.sessionId, query);
    renderPanel();
};

window.CI_refreshRenderPreview = async () => {
    const query = document.getElementById('messageInput')?.value?.trim() || '';
    if (!query) return;
    renderPanel(); // show loading state immediately
    await fetchRenderPreview(window.app?.sessionId, query);
    renderPanel();
};

window.CI_setRc = (key, value) => {
    CI.rc[key] = value;
    const storageKeys = {
        headroom_multiplier: 'ci-rc-headroom', max_pairs: 'ci-rc-pairs',
        max_others: 'ci-rc-others', max_graph: 'ci-rc-graph',
        q_snippet_chars: 'ci-rc-qsnip', a_snippet_chars: 'ci-rc-asnip',
        note_snippet_chars: 'ci-rc-nsnip', graph_snippet_chars: 'ci-rc-gsnip',
        debug_badges: 'ci-rc-debug',
    };
    if (storageKeys[key]) localStorage.setItem(storageKeys[key], value);
    // Debounce re-fetch: don't hammer the server on every slider tick
    clearTimeout(window._ciRcDebounce);
    window._ciRcDebounce = setTimeout(() => {
        const q = document.getElementById('messageInput')?.value?.trim() || '';
        if (q) fetchRenderPreview(window.app?.sessionId, q).then(() => renderPanel());
    }, 400);
    renderPanel(); // update slider display immediately
};

window.CI_toggleFullPrompt = () => { CI.renderPromptExpanded = !CI.renderPromptExpanded; renderPanel(); };

window.CI_updateInjected = (val) => { CI.pendingEdits.addedContext = val; };
window.CI_editFocus      = (val) => { CI.pendingEdits.focus = val; };

window.CI_editHistory = (index, text) => {
    if (!CI.pendingEdits.history)
        CI.pendingEdits.history = [...(CI.pendingContext?.history || [])];
    if (CI.pendingEdits.history[index])
        CI.pendingEdits.history[index] = { ...CI.pendingEdits.history[index], text };
};

window.CI_removeHistory = (index) => {
    if (!CI.pendingEdits.history)
        CI.pendingEdits.history = [...(CI.pendingContext?.history || [])];
    CI.pendingEdits.history.splice(index, 1);
    renderPanel();
};

window.CI_removeRanked = (index) => {
    const ctx = CI.pendingContext;
    if (!ctx?.vectors?.ranked_hits) return;
    if (!CI.pendingEdits.vectors)
        CI.pendingEdits.vectors = [...(ctx.vectors.ranked_hits || [])];
    CI.pendingEdits.vectors.splice(index, 1);
    ctx.vectors.ranked_hits = CI.pendingEdits.vectors;
    renderPanel();
};

window.CI_toggleExclude = (type, excluded) => {
    if (type === 'history') CI.pendingEdits.excludeHistory = excluded;
    if (type === 'vectors') CI.pendingEdits.excludeVectors = excluded;
    if (type === 'graph')   CI.pendingEdits.excludeGraph   = excluded;
    renderPanel();
};

window.CI_toggleRawBuckets = () => { CI.showRawBuckets = !CI.showRawBuckets; renderPanel(); };

window.CI_setSetting = (key, value) => {
    CI[key] = value;
    const storageMap = {
        profile:'ci-profile', historyTurns:'ci-history-turns', vectorK:'ci-vector-k',
        enableVectorSession:'ci-vec-session', enableVectorLongterm:'ci-vec-longterm',
        enableGraph:'ci-graph', autoFetchContext:'ci-auto-fetch',
    };
    if (storageMap[key]) localStorage.setItem(storageMap[key], value);
    renderPanel();
};

window.CI_clearEdits = () => {
    resetEdits();
    renderPanel();
    window.app?.setControlStatus?.('Context edits cleared');
};

window.CI_browseMemory = async () => {
    const query   = document.getElementById('ci-mem-query')?.value?.trim() || '';
    const results = document.getElementById('ci-mem-results');
    if (results) results.innerHTML = '<div class="ci-empty">Loading…</div>';
    const data = await fetchMemoryBrowser(window.app?.sessionId, query);
    if (!data || !results) return;
    if (!data.items?.length) { results.innerHTML = '<div class="ci-empty">No results found.</div>'; return; }
    results.innerHTML = data.items.map(item => `
        <div class="ci-mem-item">
            <div class="ci-mem-meta">
                <span class="ci-badge">${escHtml(item.type||'unknown')}</span>
                <span class="ci-mem-score">${item.score!=null?(item.score*100).toFixed(0)+'%':''}</span>
                <span class="ci-mem-time">${item.created_at?new Date(item.created_at).toLocaleTimeString():''}</span>
                <button class="ci-remove-btn" onclick="CI_pinMemory('${item.id}')" title="Inject">📌</button>
            </div>
            <div class="ci-mem-text">${escHtml((item.text||'').substring(0,240))}${(item.text||'').length>240?'…':''}</div>
        </div>`).join('');
};

window.CI_pinMemory = (id) => { window.app?.setControlStatus?.('📌 Use the inject box to add context'); };

window.CI_purgeMemory = async () => {
    if (!confirm('Purge all session memory? This cannot be undone.')) return;
    try {
        const res = await fetch(`${API_BASE}/api/context/memory/purge`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: window.app?.sessionId }),
        });
        if (res.ok) { CI.pendingContext = null; renderPanel(); window.app?.setControlStatus?.('🗑 Session memory purged'); }
    } catch (e) { window.app?.setControlStatus?.('❌ Purge failed'); }
};

// ─────────────────────────────────────────────────────────────────────────────
// Utility
// ─────────────────────────────────────────────────────────────────────────────

function escHtml(str) {
    if (!str) return '';
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ─────────────────────────────────────────────────────────────────────────────
// CSS
// ─────────────────────────────────────────────────────────────────────────────

const styles = `
/* ── Panel shell ── */
.ci-panel{position:fixed;top:0;right:0;width:380px;height:100vh;z-index:9500;display:flex;flex-direction:column;background:var(--bg,#0f172a);border-left:1px solid var(--border,#1e293b);box-shadow:-4px 0 24px rgba(0,0,0,.4);overflow:hidden;animation:ci-slide-in .25s cubic-bezier(.4,0,.2,1);font-size:12px;color:var(--text,#e2e8f0)}
.ci-panel--closing{animation:ci-slide-out .25s cubic-bezier(.4,0,.2,1) forwards}
@keyframes ci-slide-in{from{transform:translateX(100%);opacity:0}to{transform:translateX(0);opacity:1}}
@keyframes ci-slide-out{from{transform:translateX(0);opacity:1}to{transform:translateX(100%);opacity:0}}
@keyframes ci-pulse{0%,100%{opacity:.4;transform:scale(.85)}50%{opacity:1;transform:scale(1.15)}}

/* ── Header ── */
.ci-header{display:flex;align-items:center;gap:8px;padding:8px 10px;border-bottom:1px solid var(--border,#1e293b);background:var(--panel-bg,#1e293b);flex-shrink:0}
.ci-title{display:flex;align-items:center;gap:6px;font-size:11px;font-weight:600;color:var(--text-muted,#94a3b8);text-transform:uppercase;letter-spacing:.6px;white-space:nowrap}
.ci-tabs{display:flex;gap:2px;flex:1;justify-content:center}
.ci-tab{padding:3px 8px;background:transparent;border:1px solid transparent;border-radius:4px;color:var(--text-muted,#94a3b8);cursor:pointer;font-size:10px;transition:all .15s}
.ci-tab:hover{color:var(--text,#e2e8f0);background:rgba(255,255,255,.05)}
.ci-tab--active{color:var(--text,#e2e8f0);background:var(--panel-bg,#1e293b);border-color:var(--border,#334155)}
.ci-close{background:transparent;border:none;color:var(--text-muted,#94a3b8);cursor:pointer;font-size:14px;padding:2px 6px;border-radius:3px;transition:all .15s;flex-shrink:0}
.ci-close:hover{color:var(--text,#e2e8f0);background:rgba(255,255,255,.07)}

/* ── Body ── */
.ci-body{flex:1;overflow-y:auto;padding:10px;display:flex;flex-direction:column;gap:12px}
.ci-body::-webkit-scrollbar{width:4px}.ci-body::-webkit-scrollbar-track{background:transparent}.ci-body::-webkit-scrollbar-thumb{background:var(--border,#334155);border-radius:2px}

/* ── Sections ── */
.ci-section{border:1px solid var(--border,#1e293b);border-radius:6px;overflow:hidden}
.ci-section-header{display:flex;align-items:center;gap:6px;padding:6px 10px;background:var(--panel-bg,#1e293b);border-bottom:1px solid var(--border,#1e293b)}
.ci-section-label{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;color:var(--text-muted,#64748b);flex:1}
.ci-fetching{font-size:10px;color:var(--accent,#3b82f6);animation:ci-pulse 1.2s ease-in-out infinite}
.ci-refresh-btn{background:transparent;border:none;color:var(--text-muted,#64748b);cursor:pointer;font-size:14px;padding:0 4px;transition:color .15s}
.ci-refresh-btn:hover{color:var(--text,#e2e8f0)}

/* ── Fields ── */
.ci-field{padding:8px 10px;border-bottom:1px solid var(--border,#0f172a)}.ci-field:last-child{border-bottom:none}
.ci-label{font-size:10px;font-weight:600;color:var(--text-muted,#64748b);text-transform:uppercase;letter-spacing:.5px;display:flex;align-items:center;gap:6px;margin-bottom:5px}
.ci-label-row{display:flex;align-items:center;justify-content:space-between;margin-bottom:5px}
.ci-toggle-label{display:flex;align-items:center;gap:4px;font-size:10px;color:var(--text-muted,#64748b);cursor:pointer}

/* ── Source badge ── */
.ci-source-badge{padding:1px 5px;border:1px solid;border-radius:3px;font-size:9px;font-weight:600;white-space:nowrap}
.ci-graph-sub-pill{font-size:8px;padding:1px 4px;background:rgba(16,185,129,.12);color:#10b981;border:1px solid rgba(16,185,129,.3);border-radius:8px;white-space:nowrap}
.ci-badge--graph{background:rgba(16,185,129,.12)!important;color:#10b981!important;border-color:rgba(16,185,129,.3)!important}

/* ── Ranked hits list ── */
.ci-ranked-list{display:flex;flex-direction:column;gap:4px;max-height:280px;overflow-y:auto;border-radius:4px;background:var(--bg,#0f172a);padding:4px}
.ci-ranked-list::-webkit-scrollbar{width:3px}.ci-ranked-list::-webkit-scrollbar-thumb{background:var(--border,#1e293b)}
.ci-ranked-item{padding:6px 8px;border-radius:4px;background:var(--panel-bg,#1e293b);border:1px solid transparent;transition:border-color .15s}
.ci-ranked-item--graph{border-color:rgba(16,185,129,.2)}
.ci-ranked-meta{display:flex;align-items:center;gap:5px;flex-wrap:wrap;margin-bottom:3px}
.ci-ranked-score{font-size:10px;font-weight:700;color:#34d399;margin-left:auto}
.ci-score-detail{font-size:9px;opacity:.65}
.ci-ranked-text{font-size:11px;color:var(--text-muted,#94a3b8);line-height:1.4;word-break:break-word}

/* ── Vector buckets ── */
.ci-vector-list{display:flex;flex-direction:column;gap:4px;max-height:180px;overflow-y:auto;border-radius:4px;background:var(--bg,#0f172a);padding:4px}
.ci-vector-list::-webkit-scrollbar{width:3px}.ci-vector-list::-webkit-scrollbar-thumb{background:var(--border,#1e293b)}
.ci-vector-item{display:flex;align-items:flex-start;gap:6px;padding:5px 6px;border-radius:4px;background:var(--panel-bg,#1e293b)}
.ci-vector-score{font-size:10px;font-weight:700;color:#34d399;flex-shrink:0;margin-top:1px;min-width:30px}
.ci-vector-text{flex:1;font-size:11px;color:var(--text-muted,#94a3b8);line-height:1.4;word-break:break-word}

/* ── History list ── */
.ci-history-list{display:flex;flex-direction:column;gap:4px;max-height:200px;overflow-y:auto;border-radius:4px;background:var(--bg,#0f172a);padding:4px}
.ci-history-item{display:flex;align-items:flex-start;gap:6px;padding:4px 6px;border-radius:4px;background:var(--panel-bg,#1e293b);transition:background .15s}
.ci-role{font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;padding:2px 5px;border-radius:3px;flex-shrink:0;margin-top:2px}
.ci-role--user,.ci-role--query,.ci-role--human{background:rgba(59,130,246,.15);color:#60a5fa;border:1px solid rgba(59,130,246,.3)}
.ci-role--vera,.ci-role--assistant,.ci-role--response{background:rgba(139,92,246,.15);color:#a78bfa;border:1px solid rgba(139,92,246,.3)}
.ci-role--system{background:rgba(100,116,139,.15);color:#94a3b8;border:1px solid rgba(100,116,139,.3)}
.ci-turn-text{flex:1;font-size:11px;color:var(--text,#cbd5e1);line-height:1.5;outline:none;cursor:text;padding:1px 3px;border-radius:2px;transition:background .15s;word-break:break-word}
.ci-turn-text:focus{background:rgba(59,130,246,.1);box-shadow:inset 0 0 0 1px rgba(59,130,246,.3)}

/* ── Entity list ── */
.ci-entity-list{display:flex;flex-wrap:wrap;gap:4px;padding:4px;background:var(--bg,#0f172a);border-radius:4px}
.ci-entity{padding:2px 7px;background:rgba(100,116,139,.15);border:1px solid rgba(100,116,139,.25);border-radius:10px;font-size:10px;color:var(--text-muted,#94a3b8)}
.ci-entity--focus{background:rgba(251,191,36,.12);border-color:rgba(251,191,36,.35);color:#fbbf24}

/* ── Legend grid ── */
.ci-legend-grid{display:grid;grid-template-columns:auto 1fr;gap:4px 10px;padding:8px 10px;align-items:center}

/* ── Prompt tab — funnel ── */
.ci-funnel{padding:8px 10px;display:flex;flex-direction:column;gap:5px}
.ci-funnel-row{display:grid;grid-template-columns:140px 28px 1fr;align-items:center;gap:6px}
.ci-funnel-row--warn{}
.ci-funnel-label{font-size:10px;color:var(--text-muted,#94a3b8)}
.ci-funnel-val{font-size:10px;font-weight:700;color:var(--text,#cbd5e1);text-align:right}
.ci-funnel-val--warn{color:#f97316}
.ci-funnel-bar{height:6px;background:rgba(255,255,255,.06);border-radius:3px;overflow:hidden}

/* ── Prompt tab — cap controls ── */
.ci-caps-grid{display:grid;grid-template-columns:auto 1fr;align-items:center;gap:6px 10px;padding:8px 10px}
.ci-caps-adv{padding:0 10px 8px;border-top:1px solid var(--border,#1e293b);display:grid;grid-template-columns:auto 1fr;align-items:center;gap:6px 10px}

/* ── Prompt tab — section hits ── */
.ci-sec-stat{font-size:9px;padding:1px 5px;border-radius:3px;background:rgba(255,255,255,.05)}
.ci-sec-stat--warn{color:#ef4444}
.ci-cap-bar-track{height:7px;background:rgba(255,255,255,.06);border-radius:4px;overflow:hidden;position:relative;display:flex}
.ci-cap-bar-fill{height:100%;background:#10b981;border-radius:4px;transition:width .3s}
.ci-cap-bar-overflow{height:100%;background:#ef4444;border-radius:4px;margin-left:2px}
.ci-sec-hits{display:flex;flex-direction:column;gap:3px;padding:4px 8px;background:var(--bg,#0f172a)}
.ci-sec-hit{padding:5px 7px;border-radius:4px;border-left:2px solid transparent}
.ci-sec-hit--used{background:var(--panel-bg,#1e293b);border-left-color:#10b981}
.ci-sec-hit--dropped{background:rgba(239,68,68,.05);border-left-color:#ef444466;opacity:.8}
.ci-sec-hit-meta{display:flex;align-items:center;gap:5px;flex-wrap:wrap;margin-bottom:2px}
.ci-sec-dropped-label{font-size:9px;color:#ef4444;padding:3px 10px 1px;text-transform:uppercase;letter-spacing:.5px}
.ci-rendered-pre{margin:0;padding:8px 10px;font-size:10px;font-family:monospace;color:var(--text-muted,#94a3b8);background:var(--bg,#0f172a);white-space:pre-wrap;word-break:break-word;border-top:1px solid var(--border,#1e293b);max-height:200px;overflow-y:auto;line-height:1.5}
.ci-rendered-pre--full{max-height:none}

/* ── Misc ── */
.ci-input{width:100%;padding:5px 8px;background:var(--bg,#0f172a);border:1px solid var(--border,#1e293b);border-radius:4px;color:var(--text,#e2e8f0);font-size:12px;box-sizing:border-box;outline:none;transition:border-color .15s}.ci-input:focus{border-color:var(--accent,#3b82f6)}
.ci-badge{padding:1px 5px;background:var(--bg,#0f172a);border:1px solid var(--border,#1e293b);border-radius:9px;font-size:10px;color:var(--text-muted,#64748b);font-weight:500}
.ci-badge--empty{border-color:#ef444450;color:#ef4444}
.ci-remove-btn{background:transparent;border:none;color:var(--text-muted,#475569);cursor:pointer;font-size:11px;padding:2px;border-radius:3px;transition:all .15s;flex-shrink:0;line-height:1}
.ci-remove-btn:hover{color:#ef4444;background:rgba(239,68,68,.1)}
.ci-excluded{opacity:.35;pointer-events:none}
.ci-inject-wrap{padding:8px 10px}
.ci-inject-area{width:100%;min-height:72px;max-height:180px;padding:7px 9px;background:var(--bg,#0f172a);border:1px solid var(--border,#1e293b);border-radius:5px;color:var(--text,#e2e8f0);font-size:12px;font-family:inherit;line-height:1.5;resize:vertical;outline:none;box-sizing:border-box;transition:border-color .15s}.ci-inject-area:focus{border-color:var(--accent,#3b82f6)}.ci-inject-area::placeholder{color:var(--text-muted,#475569)}
.ci-timing{padding:5px 10px;font-size:10px;color:var(--text-muted,#475569);border-top:1px solid var(--border,#0f172a);background:var(--panel-bg,#1e293b)}
.ci-readonly{padding:8px 10px;display:flex;flex-direction:column;gap:6px}
.ci-ro-field{font-size:11px;color:var(--text-muted,#94a3b8)}
.ci-ro-label{display:inline-flex;align-items:center;gap:5px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:var(--text-muted,#64748b);margin-bottom:3px}
.ci-ro-history{display:flex;flex-direction:column;gap:3px;margin-top:3px}
.ci-ro-turn{padding:3px 6px;background:var(--bg,#0f172a);border-radius:3px;font-size:11px;color:var(--text,#cbd5e1);line-height:1.4}
.ci-ro-vec{display:flex;align-items:center;gap:5px;padding:3px 6px;background:var(--bg,#0f172a);border-radius:3px;font-size:10px;color:var(--text-muted,#94a3b8);margin-top:2px}
.ci-empty{padding:16px 10px;text-align:center;color:var(--text-muted,#475569);font-size:11px;line-height:1.5}
.ci-empty-item{padding:6px;font-size:11px;color:var(--text-muted,#475569);font-style:italic}
.ci-settings-grid{display:grid;grid-template-columns:auto 1fr;align-items:center;gap:8px 12px;padding:8px 10px}
.ci-select{padding:5px 8px;background:var(--bg,#0f172a);border:1px solid var(--border,#1e293b);border-radius:4px;color:var(--text,#e2e8f0);font-size:12px;outline:none;cursor:pointer}.ci-select:focus{border-color:var(--accent,#3b82f6)}
.ci-slider-row{display:flex;align-items:center;gap:8px}.ci-slider-row input{flex:1;accent-color:var(--accent,#3b82f6)}
.ci-slider-val{font-size:11px;font-weight:700;color:var(--accent,#3b82f6);min-width:28px;text-align:center}
.ci-toggles{display:flex;flex-direction:column;gap:0;padding:0 2px}
.ci-toggle-row{display:flex;align-items:center;justify-content:space-between;padding:7px 10px;border-bottom:1px solid var(--border,#0f172a);cursor:pointer;transition:background .1s}.ci-toggle-row:last-child{border-bottom:none}.ci-toggle-row:hover{background:rgba(255,255,255,.03)}.ci-toggle-row span{font-size:12px;color:var(--text,#cbd5e1)}.ci-toggle-row input[type=checkbox]{accent-color:var(--accent,#3b82f6)}
.ci-mem-search{display:flex;gap:6px;padding:8px 10px;border-bottom:1px solid var(--border,#0f172a)}.ci-mem-search .ci-input{flex:1}
.ci-mem-results{max-height:400px;overflow-y:auto;padding:6px;display:flex;flex-direction:column;gap:4px}
.ci-mem-item{padding:7px 9px;background:var(--panel-bg,#1e293b);border-radius:5px;border:1px solid var(--border,#1e293b)}
.ci-mem-meta{display:flex;align-items:center;gap:6px;margin-bottom:4px}
.ci-mem-score{font-size:10px;font-weight:700;color:#34d399}.ci-mem-time{font-size:10px;color:var(--text-muted,#475569);flex:1;text-align:right}
.ci-mem-text{font-size:11px;color:var(--text-muted,#94a3b8);line-height:1.5;word-break:break-word}
.ci-action-row{display:flex;flex-wrap:wrap;gap:6px;padding:8px 10px}
.ci-action-btn{padding:5px 10px;background:var(--bg,#0f172a);border:1px solid var(--border,#1e293b);border-radius:4px;color:var(--text,#e2e8f0);font-size:11px;cursor:pointer;transition:all .15s}.ci-action-btn:hover{border-color:var(--accent,#3b82f6);color:var(--accent,#3b82f6)}.ci-action-btn--danger:hover{border-color:#ef4444;color:#ef4444}
`;

if (!document.getElementById('ci-styles')) {
    const el = document.createElement('style');
    el.id = 'ci-styles';
    el.textContent = styles;
    document.head.appendChild(el);
}

// ─────────────────────────────────────────────────────────────────────────────
// Bootstrap
// ─────────────────────────────────────────────────────────────────────────────

function bootstrap() {
    const tryInstall = setInterval(() => {
        if (document.querySelector('.control-group-sleek')) {
            clearInterval(tryInstall);
            installPanelButton();
            installInputListener();
            console.log('✅ Context Inspector v7 installed');
        }
    }, 200);
}

window._CI = CI;
window.fetchContextPreview = fetchContextPreview;
bootstrap();

})();