// =====================================================================
// Vera Unified Control Bar v2
// Consolidates: control bar, voice bar, routing controls, graph context,
//               chat history, chat settings into ONE bar with flyout panels.
// Also integrates: Context Inspector (CI) + Memory Graph Explorer (MG)
//                  + per-message action buttons
// Drop-in replacement — overwrites the relevant prototype methods.
//
// v7 changes:
//  • Ctx / Graph toolbar buttons are direct toggles (no flyout) — the
//    full-height standalone CI / MG panels are the canonical UI.
//  • _ucbBuildCIPanel removed (was a cramped flyout duplicate).
//  • _ucbSyncState tracks CI.activeTab for Prompt-tab awareness.
//  • CI_refreshRenderPreview exposed on the CI button context menu.
// =====================================================================

(() => {
'use strict';

const API_BASE = 'http://llm.int:8888';

// ─── tiny pub/sub so panels can close each other ────────────────────────────
const PanelBus = {
    _current: null,
    open(id) {
        if (this._current && this._current !== id) {
            document.getElementById(this._current)?.classList.remove('ucb-panel--open');
            document.querySelector(`[data-panel="${this._current}"]`)?.classList.remove('ucb-btn--active');
        }
        this._current = id;
    },
    close() { this._current = null; }
};

// ─────────────────────────────────────────────────────────────────────────────
// UCB – Unified Control Bar
// ─────────────────────────────────────────────────────────────────────────────

VeraChat.prototype._buildUnifiedControlBar = function () {
    if (document.getElementById('ucb-root')) return;

    const root = document.createElement('div');
    root.id = 'ucb-root';
    root.innerHTML = `
        <div class="ucb-toolbar" id="ucb-toolbar">

            <!-- left cluster -->
            <div class="ucb-cluster ucb-cluster--left">
                <button class="ucb-btn" id="ucb-canvas-btn"
                        data-tooltip="Canvas auto-focus"
                        onclick="app._ucbToggleCanvas()">
                    ${icons.canvas}
                </button>
                <span class="ucb-divider"></span>
                <button class="ucb-btn" id="ucb-stt-btn"
                        data-tooltip="Voice input (STT)"
                        onclick="app._ucbToggleSTT()">
                    ${icons.mic}
                    <span class="ucb-vad"><i></i><i></i><i></i><i></i><i></i></span>
                </button>
                <button class="ucb-btn" id="ucb-tts-btn"
                        data-tooltip="Voice output (TTS)"
                        onclick="app._ucbToggleTTS()">
                    ${icons.speaker}
                </button>
                <button class="ucb-btn ucb-btn--danger" id="ucb-stop-btn"
                        data-tooltip="Stop speaking"
                        onclick="app._voice?.stopSpeaking()">
                    ${icons.stop}
                </button>
                <button class="ucb-btn ucb-btn--panel" data-panel="ucb-panel-voice"
                        data-tooltip="Voice settings"
                        onclick="app._ucbTogglePanel('ucb-panel-voice', this)">
                    ${icons.gear} <span class="ucb-label">Voice</span>${icons.chevron}
                </button>
                <span class="ucb-divider"></span>
                <button class="ucb-btn ucb-btn--panel" data-panel="ucb-panel-route"
                        data-tooltip="Routing / model"
                        onclick="app._ucbTogglePanel('ucb-panel-route', this)">
                    ${icons.route} <span class="ucb-label" id="ucb-route-label">Auto</span>${icons.chevron}
                </button>
                <span class="ucb-divider"></span>
                <button class="ucb-btn ucb-btn--panel" data-panel="ucb-panel-graph"
                        data-tooltip="Graph context"
                        onclick="app._ucbTogglePanel('ucb-panel-graph', this)">
                    ${icons.graph} <span class="ucb-label" id="ucb-graph-badge">0</span>${icons.chevron}
                </button>
            </div>

            <!-- centre – search -->
            <div class="ucb-search-wrap">
                <span class="ucb-search-icon">${icons.search}</span>
                <input id="ucb-search" class="ucb-search" placeholder="Search chat…"
                       oninput="app.searchChat(this.value)">
                <button class="ucb-search-clear" onclick="app.clearSearch()" style="display:none">✕</button>
            </div>

            <!-- right cluster -->
            <div class="ucb-cluster ucb-cluster--right">
                <span class="ucb-status" id="ucb-status"></span>

                <!-- Context Inspector — direct toggle (opens full-height side panel) -->
                <button class="ucb-btn ucb-btn--ci" id="ucb-ci-btn"
                        data-tooltip="Context Inspector (Ctx+Prompt+Memory)"
                        onclick="app._ucbToggleCI()">
                    ${icons.layers} <span class="ucb-label" id="ucb-ci-label">Ctx</span>
                </button>

                <!-- Memory Graph — direct toggle (opens floating canvas window) -->
                <button class="ucb-btn ucb-btn--mg" id="ucb-mg-btn"
                        data-tooltip="Memory Graph Explorer"
                        onclick="app._ucbToggleMG()">
                    ${icons.graphNode} <span class="ucb-label">Graph</span>
                </button>

                <span class="ucb-divider"></span>
                <button class="ucb-btn" data-tooltip="Upload file"
                        onclick="app.openFileUpload()">
                    ${icons.attach}
                </button>
                <button class="ucb-btn ucb-btn--panel" data-panel="ucb-panel-history"
                        data-tooltip="Session history"
                        onclick="app._ucbTogglePanel('ucb-panel-history', this)">
                    ${icons.history} <span class="ucb-label">History</span>${icons.chevron}
                </button>
                <button class="ucb-btn ucb-btn--panel" data-panel="ucb-panel-settings"
                        data-tooltip="Chat settings"
                        onclick="app._ucbTogglePanel('ucb-panel-settings', this)">
                    ${icons.settings} <span class="ucb-label">Settings</span>${icons.chevron}
                </button>
                <button class="ucb-btn ucb-btn--danger" data-tooltip="Clear chat"
                        onclick="app.clearChat()">
                    ${icons.trash}
                </button>
                <button class="ucb-btn" data-tooltip="Export chat"
                        onclick="app.exportChat()">
                    ${icons.download}
                </button>
            </div>
        </div>
    `;

    const chatContainer = document.getElementById('tab-chat');
    const messages = chatContainer?.querySelector('#chatMessages');
    if (messages) chatContainer.insertBefore(root, messages);
    else (chatContainer || document.body).appendChild(root);

    // ── panels live on document.body so they escape any overflow:hidden ──
    const panelHost = document.createElement('div');
    panelHost.id = 'ucb-panel-host';
    panelHost.innerHTML = `
        <div class="ucb-panel" id="ucb-panel-voice">
            <div class="ucb-panel-inner" id="ucb-voice-panel-body"></div>
        </div>
        <div class="ucb-panel" id="ucb-panel-route">
            <div class="ucb-panel-inner" id="ucb-route-panel-body"></div>
        </div>
        <div class="ucb-panel" id="ucb-panel-graph">
            <div class="ucb-panel-inner" id="ucb-graph-panel-body"></div>
        </div>
        <div class="ucb-panel" id="ucb-panel-history">
            <div class="ucb-panel-inner" id="ucb-history-panel-body"></div>
        </div>
        <div class="ucb-panel" id="ucb-panel-settings">
            <div class="ucb-panel-inner" id="ucb-settings-panel-body"></div>
        </div>
        <div class="ucb-backdrop" id="ucb-backdrop" onclick="app._ucbCloseAll()"></div>
    `;
    document.body.appendChild(panelHost);

    _injectCSS();
    this._ucbSyncState();

    root.querySelectorAll('[data-tooltip]').forEach(el => {
        el.addEventListener('mouseenter', () => _showTooltip(el));
        el.addEventListener('mouseleave', _hideTooltip);
    });

    window.addEventListener('scroll', () => this._ucbCloseAll(), { passive: true });
    window.addEventListener('resize', () => this._ucbCloseAll(), { passive: true });

    // Start per-message observer
    this._ucbStartMessageObserver();

    // Patch CI/MG module globals — retry until both modules have loaded
    const _patchInterval = setInterval(() => {
        this._ucbPatchModules();
        const ciReady = !!window._CI?.toggle;
        const mgReady = !!window._MG?.openWith;
        if (ciReady && mgReady) clearInterval(_patchInterval);
    }, 300);
    setTimeout(() => clearInterval(_patchInterval), 15000);

    console.log('[UCB] Unified control bar mounted');
};

// ─── panel toggle ─────────────────────────────────────────────────────────────
VeraChat.prototype._ucbTogglePanel = function (panelId, triggerBtn) {
    const panel = document.getElementById(panelId);
    const btn   = triggerBtn || document.querySelector(`[data-panel="${panelId}"]`);
    const isOpen = panel.classList.contains('ucb-panel--open');

    this._ucbCloseAll();

    if (!isOpen) {
        const PANEL_W  = 360;
        const GAP      = 6;
        const vw       = window.innerWidth;
        const vh       = window.innerHeight;
        const r        = btn.getBoundingClientRect();
        const top      = r.bottom + GAP;
        let left = r.left;
        if (left + PANEL_W > vw - 8) left = Math.max(8, r.right - PANEL_W);

        panel.style.top    = top  + 'px';
        panel.style.left   = left + 'px';
        panel.style.width  = PANEL_W + 'px';
        panel.style.maxHeight = (vh - top - 16) + 'px';

        panel.classList.add('ucb-panel--open');
        btn.classList.add('ucb-btn--active');
        document.getElementById('ucb-backdrop').classList.add('ucb-backdrop--active');
        PanelBus.open(panelId);

        const builders = {
            'ucb-panel-voice':    '_ucbBuildVoicePanel',
            'ucb-panel-route':    '_ucbBuildRoutePanel',
            'ucb-panel-graph':    '_ucbBuildGraphPanel',
            'ucb-panel-history':  '_ucbBuildHistoryPanel',
            'ucb-panel-settings': '_ucbBuildSettingsPanel',
        };
        const fn = builders[panelId];
        if (fn && this[fn]) this[fn]();
    }
};

VeraChat.prototype._ucbCloseAll = function () {
    document.querySelectorAll('.ucb-panel--open').forEach(p => p.classList.remove('ucb-panel--open'));
    document.querySelectorAll('.ucb-btn--active').forEach(b => b.classList.remove('ucb-btn--active'));
    document.getElementById('ucb-backdrop')?.classList.remove('ucb-backdrop--active');
    PanelBus.close();
};

// ─── state sync ───────────────────────────────────────────────────────────────
VeraChat.prototype._ucbSyncState = function () {
    document.getElementById('ucb-canvas-btn')
        ?.classList.toggle('ucb-btn--on', !!this.canvasAutoFocus);

    const v = this._voice;
    document.getElementById('ucb-stt-btn')?.classList.toggle('ucb-btn--on', v?.sttActive);
    document.getElementById('ucb-tts-btn')?.classList.toggle('ucb-btn--on', v?.ttsActive);
    document.getElementById('ucb-stop-btn').style.opacity = v?.ttsSpeaking ? '1' : '0.35';

    const rc = this._ucbRouteState?.mode || 'auto';
    const routeNames = { auto:'Auto', simple:'Fast', intermediate:'Balanced', reasoning:'Reason',
                         complex:'Deep', coding:'Code', toolchain:'Tools',
                         'toolchain-parallel':'Parallel', 'toolchain-adaptive':'Adaptive',
                         'toolchain-stepbystep':'Steps', counsel:'Counsel' };
    const lbl = document.getElementById('ucb-route-label');
    if (lbl) lbl.textContent = routeNames[rc] || rc;

    const badge = document.getElementById('ucb-graph-badge');
    if (badge && window.GraphChatIntegration) {
        badge.textContent = window.GraphChatIntegration.getContextNodeCount?.() ?? '—';
    }

    // CI button — show active tab name when open
    const ciBtn   = document.getElementById('ucb-ci-btn');
    const ciLabel = document.getElementById('ucb-ci-label');
    const ciOpen  = !!window._CI?.panelOpen;
    ciBtn?.classList.toggle('ucb-btn--on', ciOpen);
    if (ciLabel) {
        if (ciOpen && window._CI?.activeTab && window._CI.activeTab !== 'context') {
            const tabNames = { prompt:'Prompt', memory:'Mem', settings:'Ctrl' };
            ciLabel.textContent = tabNames[window._CI.activeTab] || 'Ctx';
        } else {
            ciLabel.textContent = 'Ctx';
        }
    }

    // MG button
    document.getElementById('ucb-mg-btn')?.classList.toggle('ucb-btn--on', !!window._MG?.open);
};

// ─── canvas toggle ────────────────────────────────────────────────────────────
VeraChat.prototype._ucbToggleCanvas = function () {
    this.canvasAutoFocus = !this.canvasAutoFocus;
    localStorage.setItem('canvas-auto-focus', this.canvasAutoFocus);
    this._ucbSyncState();
    this.setControlStatus(this.canvasAutoFocus ? '🎯 Canvas auto-focus on' : '⏸️ Canvas auto-focus off');
};

// ─── STT / TTS ────────────────────────────────────────────────────────────────
VeraChat.prototype._ucbToggleSTT = function () {
    this._voice ? this._voice.toggleSTT() : this.toggleSTT?.();
    setTimeout(() => this._ucbSyncState(), 100);
};
VeraChat.prototype._ucbToggleTTS = function () {
    this._voice ? this._voice.toggleTTS() : this.toggleTTS?.();
    setTimeout(() => this._ucbSyncState(), 100);
};

// ─── CI toggle — opens / closes the full-height standalone CI panel ───────────
// The CI panel has tabs: Context | Prompt | Memory | Controls
// Clicking the UCB Ctx button toggles it; right-click → jump to Prompt tab.
VeraChat.prototype._ucbToggleCI = function (targetTab) {
    const ci = window._CI;
    if (!ci) { this.setControlStatus('⏳ Context Inspector not ready', 2000); return; }

    if (targetTab && ci.panelOpen && ci.activeTab !== targetTab) {
        // Already open — just switch tab
        window.CI_setTab?.(targetTab);
        this._ucbSyncState();
        return;
    }

    if (ci.toggle) {
        ci.toggle();
    } else if (document.getElementById('ci-panel-btn')) {
        document.getElementById('ci-panel-btn').click();
    } else {
        // Manual toggle fallback
        ci.panelOpen = !ci.panelOpen;
        if (ci.panelOpen) {
            if (!document.getElementById('ci-panel')) {
                const p = document.createElement('div');
                p.id = 'ci-panel'; p.className = 'ci-panel';
                document.body.appendChild(p);
            }
            window.CI_refreshContext?.();
        } else {
            const p = document.getElementById('ci-panel');
            if (p) { p.classList.add('ci-panel--closing'); setTimeout(() => p.remove(), 280); }
        }
    }

    // After toggle, optionally switch to requested tab
    if (targetTab) {
        setTimeout(() => {
            if (window._CI?.panelOpen) window.CI_setTab?.(targetTab);
            this._ucbSyncState();
        }, 80);
    } else {
        setTimeout(() => this._ucbSyncState(), 80);
    }
};

// ─── MG toggle ────────────────────────────────────────────────────────────────
VeraChat.prototype._ucbToggleMG = function () {
    if (window._MG?.open) {
        window.MG_close?.();
    } else if (window._MG?.openWith) {
        const ctx  = window._CI?.pendingContext;
        const q    = document.getElementById('messageInput')?.value?.trim() || '';
        const sid  = window.app?.sessionId || this.sessionId || '';
        window._MG.openWith(ctx ? { ...ctx, _query: q, _sessionId: sid } : null);
    } else if (document.getElementById('mg-open-btn')) {
        document.getElementById('mg-open-btn').click();
    } else {
        this.setControlStatus('⏳ Memory Graph not ready', 2000);
    }
    setTimeout(() => this._ucbSyncState(), 100);
};

// ─── Module shim ─────────────────────────────────────────────────────────────
VeraChat.prototype._ucbPatchModules = function () {
    // CI: expose togglePanel as window._CI.toggle
    if (window._CI && !window._CI.toggle) {
        window._CI.toggle = function () {
            window._CI.panelOpen = !window._CI.panelOpen;
            const btn = document.getElementById('ci-panel-btn');
            if (btn) { btn.click(); window._CI.panelOpen = !window._CI.panelOpen; return; }
            if (window._CI.panelOpen) {
                if (!document.getElementById('ci-panel')) {
                    const p = document.createElement('div');
                    p.id = 'ci-panel'; p.className = 'ci-panel';
                    document.body.appendChild(p);
                }
                window.CI_refreshContext?.();
            } else {
                const p = document.getElementById('ci-panel');
                if (p) { p.classList.add('ci-panel--closing'); setTimeout(() => p.remove(), 280); }
            }
        };
        console.log('[UCB] CI.toggle shim installed');
    }

    // MG: expose openWith on window._MG
    if (window._MG && !window._MG.openWith) {
        window._MG.openWith = function (data) {
            if (!window._MG.open) {
                const btn = document.getElementById('mg-open-btn');
                if (btn) {
                    btn.click();
                    if (data) setTimeout(() => window._MG.debugIngest?.(data), 200);
                    return;
                }
                window._MG._pendingOpen = data;
                console.warn('[UCB] MG openWith: mg-open-btn not found, will retry');
                return;
            }
            if (data) window._MG.debugIngest?.(data);
        };
        console.log('[UCB] MG.openWith shim installed');
    }

    // Fix module bootstrap selectors
    const toolbar = document.getElementById('ucb-toolbar');
    if (toolbar && !toolbar.classList.contains('control-group-sleek')) {
        toolbar.classList.add('control-group-sleek');
        console.log('[UCB] Added .control-group-sleek alias to toolbar');
    }
};

// ─────────────────────────────────────────────────────────────────────────────
// Per-message action buttons
// ─────────────────────────────────────────────────────────────────────────────

const MSG_ACTION_CLASS = 'vera-msg-actions';

VeraChat.prototype._ucbInjectMessageActions = function (msgEl) {
    if (msgEl.querySelector(`.${MSG_ACTION_CLASS}`)) return;

    const isUser = msgEl.classList.contains('user-message')
                || msgEl.dataset.role === 'user'
                || !!msgEl.querySelector('.user-bubble, .msg-user');

    const isAssistant = msgEl.classList.contains('assistant-message')
                     || msgEl.classList.contains('vera-message')
                     || msgEl.dataset.role === 'assistant'
                     || !!msgEl.querySelector('.assistant-bubble, .msg-assistant');

    if (!isUser && !isAssistant) return;

    const bar = document.createElement('div');
    bar.className = MSG_ACTION_CLASS;

    const textEl = msgEl.querySelector('.message-content, .msg-text, .bubble-text, .markdown')
                || msgEl;
    const rawText = (textEl?.innerText || msgEl.innerText || '').trim();

    if (isAssistant) {
        bar.innerHTML = `
            <button class="vma-btn" data-action="context" title="Show context used for this response">
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
                Context
            </button>
            <button class="vma-btn" data-action="prompt" title="See render breakdown in Prompt tab">
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/></svg>
                Prompt
            </button>
            <button class="vma-btn" data-action="graph" title="Visualise memory graph for this response">
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="5" r="2"/><circle cx="4" cy="19" r="2"/><circle cx="20" cy="19" r="2"/><line x1="12" y1="7" x2="4.8" y2="17"/><line x1="12" y1="7" x2="19.2" y2="17"/><line x1="6.2" y1="19" x2="17.8" y2="19"/></svg>
                Graph
            </button>
            <button class="vma-btn" data-action="copy" title="Copy response text">
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                Copy
            </button>
            <button class="vma-btn" data-action="explore" title="Pre-fill input with a follow-up about this message">
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/><line x1="11" y1="8" x2="11" y2="14"/><line x1="8" y1="11" x2="14" y2="11"/></svg>
                Explore
            </button>`;
    } else {
        bar.innerHTML = `
            <button class="vma-btn" data-action="copy" title="Copy message">
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                Copy
            </button>
            <button class="vma-btn" data-action="resend" title="Edit and re-send this message">
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/></svg>
                Resend
            </button>`;
    }

    bar.dataset.text   = rawText.slice(0, 4000);
    bar.dataset.role   = isAssistant ? 'assistant' : 'user';
    const nodeId = msgEl.dataset.nodeId || msgEl.dataset.messageId || null;
    if (nodeId) bar.dataset.nodeId = nodeId;

    bar.addEventListener('click', (e) => this._ucbHandleMessageAction(e));
    msgEl.appendChild(bar);
};

VeraChat.prototype._ucbHandleMessageAction = async function (e) {
    const btn    = e.target.closest('[data-action]');
    if (!btn) return;
    const bar    = btn.closest(`.${MSG_ACTION_CLASS}`);
    const action = btn.dataset.action;
    const text   = bar.dataset.text || '';
    const nodeId = bar.dataset.nodeId;

    switch (action) {
        case 'copy': {
            await navigator.clipboard.writeText(text).catch(() => {});
            const orig = btn.innerHTML;
            btn.textContent = '✓ Copied';
            setTimeout(() => { btn.innerHTML = orig; }, 1800);
            break;
        }
        case 'context':
            this._ucbShowMsgContextPanel(bar, text, nodeId);
            break;
        case 'prompt':
            // Open CI on Prompt tab — pre-seeds with query from this message
            this._ucbOpenPromptForMessage(text);
            break;
        case 'graph':
            this._ucbShowMsgGraph(text, nodeId);
            break;
        case 'explore': {
            const input = document.getElementById('messageInput');
            if (input) {
                const snippet = text.slice(0, 120).replace(/\n/g, ' ');
                input.value = `Regarding your response ("${snippet}…") — `;
                input.focus();
                input.selectionStart = input.selectionEnd = input.value.length;
            }
            break;
        }
        case 'resend': {
            const input = document.getElementById('messageInput');
            if (input) {
                input.value = text;
                input.focus();
                input.selectionStart = input.selectionEnd = input.value.length;
            }
            break;
        }
    }
};

// ─── Open CI on Prompt tab for a specific message ────────────────────────────
// Seeds the render preview with the message text as query, then opens the
// Prompt tab so the user can see exactly what the builder rendered.
VeraChat.prototype._ucbOpenPromptForMessage = async function (text) {
    const sid = this.sessionId || window.app?.sessionId;
    const query = text.slice(0, 300);

    // Open CI if not open, switch to Prompt tab
    this._ucbToggleCI('prompt');

    // Fetch context preview first (Prompt tab needs ranked_hits from CI state)
    if (window.fetchContextPreview && sid) {
        await window.fetchContextPreview(sid, query);
    }

    // Now trigger render preview
    if (window.CI_refreshRenderPreview) {
        // Temporarily override the messageInput value so the render hits use this query
        const input = document.getElementById('messageInput');
        const origVal = input?.value;
        if (input) input.value = query;
        await window.CI_refreshRenderPreview();
        // Restore original input
        if (input && origVal !== undefined) input.value = origVal;
    }
};

// ─── Message Context Panel ────────────────────────────────────────────────────

VeraChat.prototype._ucbShowMsgContextPanel = async function (barEl, text, nodeId) {
    document.getElementById('vera-msg-ctx-panel')?.remove();

    const panel = document.createElement('div');
    panel.id = 'vera-msg-ctx-panel';
    panel.innerHTML = `
        <div class="vmcp-header">
            <span class="vmcp-title">
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
                Message Context
            </span>
            <button class="vmcp-close" onclick="document.getElementById('vera-msg-ctx-panel')?.remove()">✕</button>
        </div>
        <div class="vmcp-body" id="vmcp-body">
            <div class="vmcp-loading"><div class="vmcp-spinner"></div>Fetching…</div>
        </div>`;
    document.body.appendChild(panel);

    const barR = barEl.getBoundingClientRect();
    const panW = 340, panH = 480;
    const vw = window.innerWidth, vh = window.innerHeight;
    let left = barR.left, top = barR.bottom + 6;
    if (left + panW > vw - 8) left = Math.max(8, vw - panW - 8);
    if (top  + panH > vh - 8) top  = Math.max(8, barR.top - panH - 6);
    panel.style.left = left + 'px';
    panel.style.top  = top  + 'px';

    const outside = (ev) => {
        if (!panel.contains(ev.target)) { panel.remove(); document.removeEventListener('mousedown', outside); }
    };
    setTimeout(() => document.addEventListener('mousedown', outside), 100);

    const sid = this.sessionId || window.app?.sessionId;
    let result = null;

    if (nodeId) {
        try {
            const r = await fetch(`${API_BASE}/api/context/node_neighbours`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ node_id: nodeId, session_id: sid, n_hops: 1, k_per_hop: 5 }),
            });
            if (r.ok) result = { type: 'neighbours', data: await r.json() };
        } catch {}
    }

    if (!result) {
        try {
            const r = await fetch(`${API_BASE}/api/context/preview`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: sid, query: text.slice(0, 400),
                                       profile: 'general', history_turns: 4, vector_k: 5 }),
            });
            if (r.ok) result = { type: 'preview', data: await r.json() };
        } catch {}
    }

    const body = document.getElementById('vmcp-body');
    if (!body) return;

    if (!result) {
        body.innerHTML = `<div class="vmcp-empty">Backend unavailable or no context found.</div>`;
        return;
    }

    const { type, data } = result;

    if (type === 'neighbours' && data.nodes?.length) {
        window._vmcp_nodes = data.nodes;
        body.innerHTML = `
            <div class="vmcp-section-label">Related Nodes (${data.nodes.length})</div>
            <div class="vmcp-node-list">
                ${data.nodes.map(n => `
                    <div class="vmcp-node" onclick="window.MG_expand?.('${n.id}')">
                        <span class="vmcp-node-type">${_escH(n.type || 'node')}</span>
                        <span class="vmcp-node-text">${_escH((n.text || n.id || '').slice(0, 120))}</span>
                        ${n.score ? `<span class="vmcp-node-score">${(n.score*100).toFixed(0)}%</span>` : ''}
                    </div>`).join('')}
            </div>
            <div class="vmcp-actions">
                <button class="vmcp-btn" onclick="app._ucbGraphNodes(window._vmcp_nodes)">◌ Open in Graph</button>
            </div>`;
        return;
    }

    if (type === 'preview' && data) {
        window._vmcp_data = data;
        const vecs  = [...(data.vectors?.ranked_hits||[]),
                       ...(data.vectors?.session_hits||[]),
                       ...(data.vectors?.longterm_hits||[])];
        const ents  = data.graph?.entities || [];
        const focus = data.graph?.focus_entities || [];
        const hist  = data.history || [];

        body.innerHTML = `
            ${focus.length ? `
            <div class="vmcp-section-label">Focus</div>
            <div class="vmcp-tags">${focus.map(f=>`<span class="vmcp-tag vmcp-tag--focus">${_escH(f)}</span>`).join('')}</div>` : ''}

            <div class="vmcp-section-label">Semantic Hits (${vecs.length})</div>
            <div class="vmcp-vec-list">
                ${!vecs.length ? '<div class="vmcp-empty">None</div>' : vecs.slice(0,6).map(v=>`
                    <div class="vmcp-vec">
                        <span class="vmcp-vec-score">${((v.score||0)*100).toFixed(0)}%</span>
                        <span class="vmcp-vec-text">${_escH((v.text||'').slice(0,100))}</span>
                    </div>`).join('')}
            </div>

            ${ents.length ? `
            <div class="vmcp-section-label">Graph Entities (${ents.length})</div>
            <div class="vmcp-tags">
                ${ents.slice(0,10).map(e=>`<span class="vmcp-tag">${_escH(e.text||e)}</span>`).join('')}
                ${ents.length > 10 ? `<span class="vmcp-tag vmcp-tag--more">+${ents.length-10}</span>` : ''}
            </div>` : ''}

            <div class="vmcp-section-label">History (${hist.length} turns)</div>
            <div class="vmcp-hist-list">
                ${!hist.length ? '<div class="vmcp-empty">None</div>' : hist.map(h=>`
                    <div class="vmcp-hist-turn">
                        <span class="vmcp-hist-role vmcp-role-${(h.role||'').toLowerCase()}">${_escH(h.role||'?')}</span>
                        <span class="vmcp-hist-text">${_escH((h.text||'').slice(0,90))}</span>
                    </div>`).join('')}
            </div>

            ${data.elapsed_ms ? `<div class="vmcp-timing">${data.elapsed_ms.toFixed(0)}ms · ${_escH(data.stage||'general')}</div>` : ''}

            <div class="vmcp-actions">
                <button class="vmcp-btn" onclick="app._ucbPushToCI(window._vmcp_data)">Open in Inspector</button>
                <button class="vmcp-btn" onclick="app._ucbPushToGraph(window._vmcp_data)">Open in Graph</button>
                <button class="vmcp-btn" onclick="app._ucbOpenPromptForMessage(window._vmcp_data.query||'')">▶ Prompt tab</button>
            </div>`;
    }
};

VeraChat.prototype._ucbGraphNodes = function (nodes) {
    const fakeCtx = {
        vectors: { ranked_hits: nodes.map(n => ({ text: n.text||n.id, score: n.score||0.5, metadata: n })) },
        graph: { entities: [], focus_entities: [] }, history: [],
        _query: '', _sessionId: this.sessionId,
    };
    window._MG?.debugIngest?.(fakeCtx);
};

VeraChat.prototype._ucbPushToCI = function (data) {
    if (!data || !window._CI) return;
    window._CI.pendingContext = data;
    if (!window._CI.panelOpen) {
        document.getElementById('ci-panel-btn')?.click();
    } else if (typeof renderPanel === 'function') {
        renderPanel();
    }
};

VeraChat.prototype._ucbPushToGraph = function (data) {
    if (data) {
        data._sessionId = this.sessionId || window.app?.sessionId;
        window._MG?.debugIngest?.(data);
    }
};

VeraChat.prototype._ucbShowMsgGraph = function (text, nodeId) {
    if (!document.getElementById('mg-win')) {
        document.getElementById('mg-open-btn')?.click();
    }

    const sid = this.sessionId || window.app?.sessionId;
    fetch(`${API_BASE}/api/context/preview`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sid, query: text.slice(0, 400),
                               profile: 'general', history_turns: 4, vector_k: 6 }),
    })
    .then(r => r.ok ? r.json() : null)
    .then(data => {
        if (data) { data._query = text.slice(0, 80); data._sessionId = sid; }
        setTimeout(() => {
            window._MG?.debugIngest?.(data || { vectors:{ranked_hits:[]}, graph:{entities:[],focus_entities:[]}, history:[] });
        }, 150);
    })
    .catch(() => {});
};

// ─── Message observer ─────────────────────────────────────────────────────────
VeraChat.prototype._ucbStartMessageObserver = function () {
    const MSG_SELECTORS = [
        '.message-row', '.chat-message', '.msg-bubble',
        '.user-message', '.assistant-message', '.vera-message',
        '[data-role="user"]', '[data-role="assistant"]',
        '.message', '.chat-turn',
    ];

    const scanRoot = (root) => {
        root.querySelectorAll(MSG_SELECTORS.join(',')).forEach(el => this._ucbInjectMessageActions(el));
        if (root.matches?.(MSG_SELECTORS.join(','))) this._ucbInjectMessageActions(root);
    };

    const observer = new MutationObserver(mutations => {
        for (const m of mutations)
            for (const node of m.addedNodes)
                if (node.nodeType === 1) scanRoot(node);
    });

    const chatArea = document.getElementById('chatMessages')
                  || document.querySelector('.chat-messages, .messages-list, #tab-chat');
    if (chatArea) {
        observer.observe(chatArea, { childList: true, subtree: true });
        scanRoot(chatArea);
    }
};

// ─────────────────────────────────────────────────────────────────────────────
// VOICE panel builder
// ─────────────────────────────────────────────────────────────────────────────
VeraChat.prototype._ucbBuildVoicePanel = function () {
    const body = document.getElementById('ucb-voice-panel-body');
    if (!body) return;

    const ctrl = this._voice;
    if (!ctrl) { body.innerHTML = `<div class="ucb-empty">Voice module not loaded.</div>`; return; }

    const c  = ctrl.cfg;
    const bs = ctrl.backend;

    if (!bs.checked) ctrl._checkBackend().then(() => this._ucbBuildVoicePanel());

    const sttStatus = bs.checked ? (bs.stt ? '✅ Whisper available' : '❌ Whisper unavailable') : '…checking';
    const ttsStatus = bs.checked ? (bs.tts ? '✅ Remote available' : '❌ Remote unavailable') : '…checking';

    body.innerHTML = `
        <div class="ucb-phead">
            <div class="ucb-phead-status">
                <span class="${bs.stt ? 'ok' : 'na'}">STT ${sttStatus}</span>
                <span class="${bs.tts ? 'ok' : 'na'}">TTS ${ttsStatus}</span>
                <button class="ucb-link" onclick="app._ucbRecheckVoice()">↻ Recheck</button>
            </div>
        </div>
        <div class="ucb-pgroup">
            <div class="ucb-pgroup-label">Speech Input</div>
            <label class="ucb-row">Engine
                <select class="ucb-sel" id="vp-stt-mode">
                    <option value="browser" ${c.sttMode==='browser'?'selected':''}>Browser (Web Speech)</option>
                    <option value="whisper" ${c.sttMode==='whisper'?'selected':''}>Whisper (backend)</option>
                </select>
            </label>
            <div id="vp-whisper-rows" style="display:${c.sttMode==='whisper'?'contents':'none'}">
                <label class="ucb-row">Endpoint <input class="ucb-inp" id="vp-wep" value="${c.whisperEndpoint}"></label>
                <label class="ucb-row">Model
                    <select class="ucb-sel" id="vp-wmodel">
                        ${['tiny','base','small','medium','large'].map(m=>`<option value="${m}" ${c.whisperModel===m?'selected':''}>${m}</option>`).join('')}
                    </select>
                </label>
                <label class="ucb-row">Language <input class="ucb-inp ucb-inp--sm" id="vp-wlang" value="${c.whisperLanguage}"></label>
            </div>
            <label class="ucb-row">Auto-send after silence <input type="checkbox" id="vp-autosend" ${c.autoSendAfterSilence?'checked':''}></label>
            <label class="ucb-row">Silence timeout (ms) <input type="number" class="ucb-inp ucb-inp--sm" id="vp-sil" value="${c.silenceMs}" min="300" max="5000" step="100"></label>
            <label class="ucb-row">Interrupt TTS on speech <input type="checkbox" id="vp-interrupt" ${c.interruptOnSpeech?'checked':''}></label>
        </div>
        <div class="ucb-pgroup">
            <div class="ucb-pgroup-label">Voice Output</div>
            <label class="ucb-row">Engine
                <select class="ucb-sel" id="vp-tts-mode">
                    <option value="browser" ${c.ttsMode==='browser'?'selected':''}>Browser (Web Speech)</option>
                    <option value="remote"  ${c.ttsMode==='remote' ?'selected':''}>Remote endpoint</option>
                </select>
            </label>
            <div id="vp-remote-rows" style="display:${c.ttsMode==='remote'?'contents':'none'}">
                <label class="ucb-row">TTS Endpoint <input class="ucb-inp" id="vp-rep" value="${c.remoteTtsEndpoint}"></label>
                <label class="ucb-row">Voice <input class="ucb-inp ucb-inp--sm" id="vp-rvoice" value="${c.remoteTtsVoice}"></label>
                <label class="ucb-row">Format
                    <select class="ucb-sel" id="vp-rfmt">
                        ${['wav','mp3','ogg'].map(f=>`<option value="${f}" ${c.remoteTtsFormat===f?'selected':''}>${f.toUpperCase()}</option>`).join('')}
                    </select>
                </label>
            </div>
            <label class="ucb-row">Rate
                <div class="ucb-slider-row">
                    <input type="range" id="vp-rate" min="0.5" max="2" step="0.05" value="${c.ttsRate}">
                    <span id="vp-rate-val">${Number(c.ttsRate).toFixed(2)}×</span>
                </div>
            </label>
            <label class="ucb-row">Volume
                <div class="ucb-slider-row">
                    <input type="range" id="vp-vol" min="0" max="1" step="0.05" value="${c.audioGain}">
                    <span id="vp-vol-val">${Math.round(c.audioGain*100)}%</span>
                </div>
            </label>
            <label class="ucb-row">Noise suppression <input type="checkbox" id="vp-noise" ${c.noiseSuppression?'checked':''}></label>
        </div>
        <div class="ucb-pactions">
            <button class="ucb-pbtn" onclick="app._ucbVoiceTest()">🔊 Test TTS</button>
            <button class="ucb-pbtn ucb-pbtn--primary" onclick="app._ucbVoiceSave()">Save</button>
        </div>`;

    body.querySelector('#vp-rate').oninput = e => body.querySelector('#vp-rate-val').textContent = Number(e.target.value).toFixed(2)+'×';
    body.querySelector('#vp-vol').oninput  = e => body.querySelector('#vp-vol-val').textContent  = Math.round(e.target.value*100)+'%';
    body.querySelector('#vp-stt-mode').onchange = e => body.querySelector('#vp-whisper-rows').style.display = e.target.value==='whisper'?'contents':'none';
    body.querySelector('#vp-tts-mode').onchange = e => body.querySelector('#vp-remote-rows').style.display  = e.target.value==='remote' ?'contents':'none';
};

VeraChat.prototype._ucbRecheckVoice = async function () {
    const ctrl = this._voice; if (!ctrl) return;
    ctrl.backend.checked = false;
    document.getElementById('ucb-voice-panel-body').innerHTML = '<div class="ucb-empty">Checking backend…</div>';
    await ctrl._checkBackend();
    this._ucbBuildVoicePanel();
};

VeraChat.prototype._ucbVoiceTest = function () {
    const v = this._voice; if (!v) return;
    v.ttsActive = true; v._updateUI?.(); v._speakBrowser('Vera voice output is working.');
};

VeraChat.prototype._ucbVoiceSave = function () {
    const ctrl = this._voice; if (!ctrl) return;
    const q = id => document.getElementById(id);
    const rate = parseFloat(q('vp-rate').value);
    localStorage.setItem('vera-tts-rate', String(rate));
    ctrl.saveCfg({
        sttMode: q('vp-stt-mode').value,
        whisperEndpoint:   q('vp-wep')?.value    || ctrl.cfg.whisperEndpoint,
        whisperModel:      q('vp-wmodel')?.value || ctrl.cfg.whisperModel,
        whisperLanguage:   q('vp-wlang')?.value  || ctrl.cfg.whisperLanguage,
        ttsMode:           q('vp-tts-mode').value,
        remoteTtsEndpoint: q('vp-rep')?.value    || ctrl.cfg.remoteTtsEndpoint,
        remoteTtsVoice:    q('vp-rvoice')?.value || ctrl.cfg.remoteTtsVoice,
        remoteTtsFormat:   q('vp-rfmt')?.value   || ctrl.cfg.remoteTtsFormat,
        ttsRate:           rate,
        audioGain:         parseFloat(q('vp-vol').value),
        autoSendAfterSilence: q('vp-autosend').checked,
        silenceMs:         parseInt(q('vp-sil').value),
        interruptOnSpeech: q('vp-interrupt').checked,
        noiseSuppression:  q('vp-noise').checked,
    });
    this._ucbCloseAll();
    this.setControlStatus('✅ Voice settings saved', 2000);
};

// ─────────────────────────────────────────────────────────────────────────────
// ROUTE panel
// ─────────────────────────────────────────────────────────────────────────────

const ROUTE_DESCRIPTIONS = {
    auto:                   '🤖 <b>Auto</b> — Triage classifies and picks the best route.',
    simple:                 '⚡ <b>Simple</b> — Fast model. Short questions.',
    intermediate:           '📊 <b>Intermediate</b> — Balanced depth.',
    reasoning:              '🧠 <b>Reasoning</b> — Step-by-step analysis.',
    complex:                '🔬 <b>Complex</b> — Deep research mode.',
    coding:                 '💻 <b>Coding</b> — Code generation & debug.',
    toolchain:              '🔧 <b>Toolchain</b> — Execute tools.',
    'toolchain-parallel':   '⚡🔧 <b>Parallel</b> — Multiple tools at once.',
    'toolchain-adaptive':   '🎯 <b>Adaptive</b> — Dynamic multi-step tools.',
    'toolchain-stepbystep': '📋 <b>Step-by-Step</b> — Sequential tools.',
    counsel:                '👥 <b>Counsel</b> — Multiple models deliberate.',
};
const MODEL_ROLES = ['fast','intermediate','deep','reasoning'];

VeraChat.prototype._ucbBuildRoutePanel = function () {
    const body = document.getElementById('ucb-route-panel-body');
    if (!body) return;

    const mode          = localStorage.getItem('rc-mode') || 'auto';
    const force         = localStorage.getItem('rc-force') === 'true';
    const modelOverride = localStorage.getItem('rc-model-override') || '';
    const counselMode   = localStorage.getItem('rc-counsel-mode') || 'vote';
    let counselModels;
    try { counselModels = JSON.parse(localStorage.getItem('rc-counsel-models')) || ['fast','intermediate','deep']; }
    catch { counselModels = ['fast','intermediate','deep']; }

    const isCounsel = mode === 'counsel';
    const opt = (v, l) => `<option value="${v}"${mode===v?' selected':''}>${l}</option>`;
    const counselRows = counselModels.map((role,i)=>`
        <div class="ucb-counsel-row" data-idx="${i}">
            <select class="ucb-sel ucb-sel--sm" data-ci="${i}">
                ${MODEL_ROLES.map(r=>`<option value="${r}"${r===role?' selected':''}>${r}</option>`).join('')}
            </select>
            <button class="ucb-icon-btn ucb-danger" data-ci-remove="${i}" title="Remove">✕</button>
        </div>`).join('');

    body.innerHTML = `
        <div class="ucb-pgroup">
            <div class="ucb-pgroup-label">Route mode</div>
            <select class="ucb-sel ucb-sel--full" id="rp-mode">
                <optgroup label="Auto">${opt('auto','🤖 Auto')}</optgroup>
                <optgroup label="Direct">${opt('simple','⚡ Simple')}${opt('intermediate','📊 Intermediate')}${opt('reasoning','🧠 Reasoning')}${opt('complex','🔬 Complex')}${opt('coding','💻 Coding')}</optgroup>
                <optgroup label="Toolchain">${opt('toolchain','🔧 Toolchain')}${opt('toolchain-parallel','⚡🔧 Parallel')}${opt('toolchain-adaptive','🎯 Adaptive')}${opt('toolchain-stepbystep','📋 Step-by-Step')}</optgroup>
                <optgroup label="Counsel">${opt('counsel','👥 Counsel')}</optgroup>
            </select>
            <div class="ucb-desc" id="rp-desc">${ROUTE_DESCRIPTIONS[mode]||''}</div>
        </div>
        <label class="ucb-row">Force route (skip triage) <input type="checkbox" id="rp-force" ${force?'checked':''}></label>
        <div id="rp-model-section" style="display:${isCounsel?'none':'flex'}" class="ucb-row">
            Responding model
            <select class="ucb-sel ucb-sel--sm" id="rp-model">
                <option value="">— default —</option>
                ${MODEL_ROLES.map(r=>`<option value="${r}"${r===modelOverride?' selected':''}>${r}</option>`).join('')}
            </select>
        </div>
        <div id="rp-counsel-section" style="display:${isCounsel?'block':'none'}">
            <div class="ucb-pgroup-label">Deliberation</div>
            <select class="ucb-sel ucb-sel--full" id="rp-cmode">
                <option value="vote"      ${counselMode==='vote'     ?'selected':''}>⚖️ Vote — judge picks best</option>
                <option value="synthesis" ${counselMode==='synthesis'?'selected':''}>🔀 Synthesis — combine all</option>
                <option value="debate"    ${counselMode==='debate'   ?'selected':''}>⚔️ Debate — rebut + moderate</option>
                <option value="race"      ${counselMode==='race'     ?'selected':''}>🏁 Race — fastest wins</option>
            </select>
            <div class="ucb-pgroup-label" style="margin-top:10px">Participants
                <button class="ucb-link" id="rp-add-counsel">+ Add</button>
            </div>
            <div id="rp-counsel-rows">${counselRows}</div>
        </div>
        <div class="ucb-pactions">
            <button class="ucb-pbtn ucb-pbtn--primary" onclick="app._ucbRouteSave()">Apply</button>
        </div>`;

    const modeEl = body.querySelector('#rp-mode');
    modeEl.onchange = () => {
        const v = modeEl.value;
        body.querySelector('#rp-desc').innerHTML = ROUTE_DESCRIPTIONS[v]||'';
        body.querySelector('#rp-model-section').style.display   = v==='counsel'?'none':'flex';
        body.querySelector('#rp-counsel-section').style.display = v==='counsel'?'block':'none';
    };
    body.querySelector('#rp-add-counsel').onclick = () => {
        const rows = body.querySelector('#rp-counsel-rows');
        const idx  = rows.children.length; if (idx >= 6) return;
        const div  = document.createElement('div');
        div.className = 'ucb-counsel-row'; div.dataset.idx = idx;
        div.innerHTML = `<select class="ucb-sel ucb-sel--sm" data-ci="${idx}">${MODEL_ROLES.map(r=>`<option value="${r}">${r}</option>`).join('')}</select><button class="ucb-icon-btn ucb-danger" data-ci-remove="${idx}" title="Remove">✕</button>`;
        rows.appendChild(div);
    };
    body.querySelector('#rp-counsel-rows').addEventListener('click', e => {
        const btn = e.target.closest('[data-ci-remove]'); if (!btn) return;
        const rows = body.querySelector('#rp-counsel-rows');
        if (rows.children.length <= 2) return;
        btn.closest('.ucb-counsel-row').remove();
    });
};

VeraChat.prototype._ucbRouteSave = function () {
    const q = id => document.getElementById(id);
    const mode = q('rp-mode').value;

    localStorage.setItem('rc-mode',           mode);
    localStorage.setItem('rc-force',          q('rp-force').checked);
    localStorage.setItem('rc-model-override', q('rp-model')?.value || '');
    localStorage.setItem('rc-counsel-mode',   q('rp-cmode')?.value || 'vote');
    const counselRows = document.querySelectorAll('#rp-counsel-rows .ucb-counsel-row');
    localStorage.setItem('rc-counsel-models', JSON.stringify(
        Array.from(counselRows).map(row => row.querySelector('select')?.value || 'fast')
    ));

    const rcMode  = document.querySelector('#rc-panel #rc-mode');
    const rcForce = document.querySelector('#rc-panel #rc-force');
    const rcModel = document.querySelector('#rc-panel #rc-model-override');
    const rcCMode = document.querySelector('#rc-panel #rc-counsel-mode');

    if (rcMode)  { rcMode.value = mode; rcMode.dispatchEvent(new Event('change', { bubbles: true })); }
    if (rcForce) { rcForce.checked = q('rp-force').checked; rcForce.dispatchEvent(new Event('change', { bubbles: true })); }
    if (rcModel && q('rp-model')) { rcModel.value = q('rp-model').value; rcModel.dispatchEvent(new Event('change', { bubbles: true })); }
    if (rcCMode && q('rp-cmode')) { rcCMode.value = q('rp-cmode').value; rcCMode.dispatchEvent(new Event('change', { bubbles: true })); }

    const rcCounselModels = document.querySelectorAll('#rc-panel .rc-counsel-model');
    const ucbModels = Array.from(counselRows).map(row => row.querySelector('select')?.value || 'fast');
    rcCounselModels.forEach((sel, i) => {
        if (ucbModels[i]) { sel.value = ucbModels[i]; sel.dispatchEvent(new Event('change', { bubbles: true })); }
    });

    this._ucbSyncState();
    this._ucbCloseAll();
    this.setControlStatus(`🎯 Route: ${mode}`, 2000);
};

// ─────────────────────────────────────────────────────────────────────────────
// GRAPH CONTEXT panel
// ─────────────────────────────────────────────────────────────────────────────
VeraChat.prototype._ucbBuildGraphPanel = function () {
    const body = document.getElementById('ucb-graph-panel-body');
    if (!body) return;
    const gci = window.GraphChatIntegration;
    if (!gci) { body.innerHTML = `<div class="ucb-empty">Graph module not loaded.</div>`; return; }

    const mode  = gci.contextMode || 'selected';
    const stats = gci.graphStats || {};
    const modeBtn = (v,l) => `<button class="ucb-mode-btn ${mode===v?'ucb-mode-btn--on':''}" onclick="window.GraphChatIntegration.setContextMode('${v}'); app._ucbBuildGraphPanel()">${l}</button>`;

    body.innerHTML = `
        <div class="ucb-pgroup">
            <div class="ucb-pgroup-label">Include in queries</div>
            <div class="ucb-mode-row">
                ${modeBtn('selected','Selected')}${modeBtn('visible','Visible')}${modeBtn('all','All')}${modeBtn('none','None')}
            </div>
        </div>
        <div class="ucb-pgroup">
            <div class="ucb-pgroup-label">Options</div>
            <label class="ucb-row">Node properties <input type="checkbox" ${gci.includeProperties?'checked':''} onchange="window.GraphChatIntegration.toggleOption('properties',this.checked)"></label>
            <label class="ucb-row">Relationships <input type="checkbox" ${gci.includeRelationships?'checked':''} onchange="window.GraphChatIntegration.toggleOption('relationships',this.checked)"></label>
            <label class="ucb-row">Auto-include neighbours <input type="checkbox" ${gci.autoIncludeNeighbors?'checked':''} onchange="window.GraphChatIntegration.toggleOption('neighbors',this.checked)"></label>
        </div>
        <div class="ucb-pgroup ucb-pgroup--stats">
            <div class="ucb-stat"><span>${stats.selectedNodes||0}</span>Selected</div>
            <div class="ucb-stat"><span>${stats.visibleNodes||0}</span>Visible</div>
            <div class="ucb-stat"><span>${stats.totalNodes||0}</span>Total</div>
        </div>
        <div class="ucb-pgroup">
            <div class="ucb-pgroup-label">Quick queries</div>
            <div class="ucb-quick-grid">
                ${['summarize','analyze','patterns','suggest'].map(q=>`
                    <button class="ucb-quick-btn" onclick="window.GraphChatIntegration.insertGraphQuery('${q}'); app._ucbCloseAll()">
                        ${q.charAt(0).toUpperCase()+q.slice(1)}
                    </button>`).join('')}
            </div>
        </div>
        <div class="ucb-pactions">
            <button class="ucb-pbtn" onclick="window.GraphChatIntegration.previewContext()">👁 Preview</button>
            <button class="ucb-pbtn" onclick="window.GraphChatIntegration.copyContextToClipboard()">📋 Copy</button>
        </div>`;
};

// ─────────────────────────────────────────────────────────────────────────────
// HISTORY panel
// ─────────────────────────────────────────────────────────────────────────────
VeraChat.prototype._ucbBuildHistoryPanel = async function () {
    const body = document.getElementById('ucb-history-panel-body');
    if (!body) return;
    body.innerHTML = `
        <div class="ucb-pgroup">
            <input class="ucb-inp" id="ucb-hist-search" placeholder="Search sessions…">
        </div>
        <div class="ucb-hist-list" id="ucb-hist-list">
            <div class="ucb-empty">Loading…</div>
        </div>`;
    document.getElementById('ucb-hist-search').oninput = e => this._ucbFilterHistory(e.target.value);
    await this._ucbLoadHistory();
};

VeraChat.prototype._ucbLoadHistory = async function () {
    const list = document.getElementById('ucb-hist-list'); if (!list) return;
    try {
        const r = await fetch(`${API_BASE}/api/sessions`);
        if (!r.ok) throw new Error(r.status);
        const data = await r.json();
        const sessions = data.sessions || [];
        if (!sessions.length) { list.innerHTML = `<div class="ucb-empty">No previous sessions.</div>`; return; }
        this._ucbHistSessions = sessions;
        this._ucbRenderHistoryList(sessions);
    } catch (e) {
        list.innerHTML = `<div class="ucb-empty ucb-error">Failed to load: ${e.message}</div>`;
    }
};

VeraChat.prototype._ucbRenderHistoryList = function (sessions) {
    const list = document.getElementById('ucb-hist-list'); if (!list) return;
    list.innerHTML = sessions.map(s => {
        const isCurrent = s.id === this.sessionId;
        const d  = s.created_at ? new Date(s.created_at) : null;
        const ts = d ? this.formatTimestamp(d.getTime()) : '—';
        return `
            <div class="ucb-hist-item ${isCurrent?'ucb-hist-item--current':''}" data-sid="${s.id}">
                <div class="ucb-hist-meta">
                    <span class="ucb-hist-title">${this.escapeHtml(s.title||'Untitled')}</span>
                    ${isCurrent?'<span class="ucb-badge">ACTIVE</span>':''}
                </div>
                <div class="ucb-hist-sub">${ts} · ${s.message_count||0} msgs</div>
                ${s.preview?`<div class="ucb-hist-preview">${this.escapeHtml((s.preview||'').slice(0,100))}</div>`:''}
                <div class="ucb-hist-actions">
                    ${!isCurrent?`<button class="ucb-pbtn ucb-pbtn--xs" onclick="app._ucbLoadSession('${s.id}')">Load</button>`:''}
                    <button class="ucb-pbtn ucb-pbtn--xs ucb-pbtn--danger" onclick="app._ucbDeleteSession('${s.id}')">Delete</button>
                </div>
            </div>`;
    }).join('');
};

VeraChat.prototype._ucbFilterHistory = function (q) {
    const lq = q.toLowerCase();
    document.querySelectorAll('.ucb-hist-item').forEach(el => {
        el.style.display = el.textContent.toLowerCase().includes(lq) ? '' : 'none';
    });
};

VeraChat.prototype._ucbLoadSession = async function (sessionId) {
    try {
        const r = await fetch(`${API_BASE}/api/sessions/${sessionId}/resume`, { method:'POST' });
        const d = await r.json();
        if (d.session_id) { this.sessionId = d.session_id; this._ucbCloseAll(); this.setControlStatus('✅ Session loaded', 2000); }
    } catch (e) { this.setControlStatus(`❌ Load failed: ${e.message}`); }
};

VeraChat.prototype._ucbDeleteSession = async function (sessionId) {
    if (!confirm('Delete this session?')) return;
    try {
        await fetch(`${API_BASE}/api/sessions/${sessionId}`, { method:'DELETE' });
        await this._ucbLoadHistory();
    } catch (e) { this.setControlStatus(`❌ Delete failed: ${e.message}`); }
};

// ─────────────────────────────────────────────────────────────────────────────
// SETTINGS panel
// ─────────────────────────────────────────────────────────────────────────────
VeraChat.prototype._ucbBuildSettingsPanel = function () {
    const body = document.getElementById('ucb-settings-panel-body'); if (!body) return;
    const theme    = localStorage.getItem('chat-theme') || 'dark';
    const fontSize = localStorage.getItem('chat-font-size') || 'medium';
    const ttsRate  = parseFloat(localStorage.getItem('vera-tts-rate') || '1');

    body.innerHTML = `
        <div class="ucb-pgroup">
            <div class="ucb-pgroup-label">Display</div>
            <label class="ucb-row">Theme
                <select class="ucb-sel ucb-sel--sm" onchange="app.changeTheme(this.value)">
                    <option value="dark"     ${theme==='dark'    ?'selected':''}>Dark</option>
                    <option value="light"    ${theme==='light'   ?'selected':''}>Light</option>
                    <option value="midnight" ${theme==='midnight'?'selected':''}>Midnight</option>
                </select>
            </label>
            <label class="ucb-row">Font size
                <select class="ucb-sel ucb-sel--sm" onchange="app.changeFontSize(this.value)">
                    <option value="small"  ${fontSize==='small' ?'selected':''}>Small</option>
                    <option value="medium" ${fontSize==='medium'?'selected':''}>Medium</option>
                    <option value="large"  ${fontSize==='large' ?'selected':''}>Large</option>
                </select>
            </label>
        </div>
        <div class="ucb-pgroup">
            <div class="ucb-pgroup-label">Behaviour</div>
            <label class="ucb-row">Canvas auto-focus <input type="checkbox" ${this.canvasAutoFocus?'checked':''} onchange="app._ucbToggleCanvas()"></label>
            <label class="ucb-row">Auto-scroll <input type="checkbox" ${localStorage.getItem('auto-scroll')!=='false'?'checked':''} onchange="localStorage.setItem('auto-scroll',this.checked)"></label>
            <label class="ucb-row">Enter to send <input type="checkbox" ${localStorage.getItem('enter-to-send')!=='false'?'checked':''} onchange="localStorage.setItem('enter-to-send',this.checked)"></label>
        </div>
        <div class="ucb-pgroup">
            <div class="ucb-pgroup-label">TTS rate</div>
            <div class="ucb-slider-row">
                <input type="range" id="sp-tts-rate" min="0.5" max="2" step="0.05" value="${ttsRate}">
                <span id="sp-tts-rate-val">${ttsRate.toFixed(2)}×</span>
            </div>
        </div>
        <div class="ucb-pgroup">
            <div class="ucb-pgroup-label">Data</div>
            <div class="ucb-pactions" style="flex-direction:column;gap:6px">
                <button class="ucb-pbtn" onclick="app.exportAllData?.() || app.exportChat()">💾 Export all</button>
                <button class="ucb-pbtn ucb-pbtn--danger" onclick="app.clearAllData?.() || app.clearChat()">🗑️ Clear all chats</button>
            </div>
        </div>`;

    body.querySelector('#sp-tts-rate').oninput = e => {
        const v = parseFloat(e.target.value);
        body.querySelector('#sp-tts-rate-val').textContent = v.toFixed(2)+'×';
        localStorage.setItem('vera-tts-rate', v);
        if (this._voice) this._voice.cfg.ttsRate = v;
    };
};

// ─────────────────────────────────────────────────────────────────────────────
// Override setControlStatus
// ─────────────────────────────────────────────────────────────────────────────
const _origSetStatus = VeraChat.prototype.setControlStatus;
VeraChat.prototype.setControlStatus = function (message, duration = 3000) {
    _origSetStatus?.call(this, message, duration);
    const el = document.getElementById('ucb-status'); if (!el) return;
    el.textContent = message;
    el.style.opacity = '1';
    if (duration > 0) setTimeout(() => { el.style.opacity = '0'; }, duration);
};

// ─────────────────────────────────────────────────────────────────────────────
// Suppress legacy bars
// ─────────────────────────────────────────────────────────────────────────────

const LEGACY_IDS = new Set([
    'vera-voice-bar', 'vera-control-bar', 'vera-chat-controls',
    'chat-control-bar', 'control-bar',
    'chat-toolbar', 'vera-toolbar', 'vera-top-bar', 'vera-bar',
    'message-controls', 'chat-controls', 'input-controls',
]);
const LEGACY_CLASSES = [
    'graph-context-panel', 'voice-bar', 'settings-panel', 'history-panel',
    'chat-control-bar', 'vera-control-bar', 'control-bar-row',
    'routing-controls', 'route-controls',
];

(function _suppressLegacyCSS() {
    if (document.getElementById('ucb-suppress-css')) return;
    const ids  = [...LEGACY_IDS].map(id => `#${id}`).join(',\n        ');
    const cls  = LEGACY_CLASSES.map(c => `.${c}`).join(',\n        ');
    const s    = document.createElement('style');
    s.id       = 'ucb-suppress-css';
    s.textContent = `${ids},\n        ${cls} { display: none !important; }`;
    document.head.prepend(s);
})();

function _killLegacyEl(el) {
    if (!el || !el.id && !el.classList) return;
    if (el.id === 'ucb-root' || el.closest?.('#ucb-root, #ucb-panel-host')) return;
    if (el.id === 'rc-panel') return;
    if (LEGACY_IDS.has(el.id)) { el.style.setProperty('display','none','important'); return; }
    for (const cls of LEGACY_CLASSES) {
        if (el.classList?.contains(cls)) { el.style.setProperty('display','none','important'); return; }
    }
}
(function _suppressLegacyObserver() {
    const obs = new MutationObserver(mutations => {
        for (const m of mutations)
            for (const node of m.addedNodes)
                if (node.nodeType === 1) { _killLegacyEl(node); node.querySelectorAll?.('*').forEach(_killLegacyEl); }
    });
    obs.observe(document.documentElement, { childList: true, subtree: true });
})();

VeraChat.prototype._ucbKillBar = function (idOrClass) {
    if (idOrClass.startsWith('.')) {
        LEGACY_CLASSES.push(idOrClass.slice(1));
        document.querySelectorAll(idOrClass).forEach(el => el.style.setProperty('display','none','important'));
    } else {
        LEGACY_IDS.add(idOrClass);
        const el = document.getElementById(idOrClass);
        if (el) el.style.setProperty('display','none','important');
    }
    const s = document.getElementById('ucb-suppress-css');
    if (s) {
        const ids = [...LEGACY_IDS].map(id => `#${id}`).join(',\n        ');
        const cls = LEGACY_CLASSES.map(c => `.${c}`).join(',\n        ');
        s.textContent = `${ids},\n        ${cls} { display: none !important; }`;
    }
    console.log('[UCB] Killed', idOrClass);
};

// ─────────────────────────────────────────────────────────────────────────────
// Wire into initModernFeatures
// ─────────────────────────────────────────────────────────────────────────────
const _origInit = VeraChat.prototype.initModernFeatures;
VeraChat.prototype.initModernFeatures = function () {
    if (_origInit) _origInit.call(this);
    document.querySelectorAll(
        [...LEGACY_IDS].map(id=>`#${id}`).concat(LEGACY_CLASSES.map(c=>`.${c}`)).join(',')
    ).forEach(el => { if (!el.closest('#ucb-root, #ucb-panel-host')) el.style.setProperty('display','none','important'); });

    Promise.resolve().then(() => {
        this._buildUnifiedControlBar();
        setInterval(() => this._ucbSyncState(), 1000);
    });
};

const _origAddRC = VeraChat.prototype.addRoutingControls;
VeraChat.prototype.addRoutingControls = function () {
    if (_origAddRC) _origAddRC.call(this);
    const rcPanel = document.getElementById('rc-panel');
    if (rcPanel) {
        rcPanel.style.cssText = 'position:absolute!important;width:1px!important;height:1px!important;overflow:hidden!important;opacity:0!important;pointer-events:none!important;';
    }
    this._ucbRouteState = { mode: localStorage.getItem('rc-mode') || 'auto' };
};

['addVoiceBar', 'buildVoiceBar', 'initVoiceBar', 'addControlBar', 'buildControlBar'].forEach(fn => {
    if (typeof VeraChat.prototype[fn] === 'function') {
        VeraChat.prototype[fn] = function () { /* suppressed — UCB owns this surface */ };
    }
});

// ─────────────────────────────────────────────────────────────────────────────
// Patch sendMessageViaWebSocket
// ─────────────────────────────────────────────────────────────────────────────
const _origSendWS = VeraChat.prototype.sendMessageViaWebSocket;
VeraChat.prototype.sendMessageViaWebSocket = function (message, options) {
    let routeOverride;
    if (typeof this.getRoutingConfig === 'function') {
        const cfg = this.getRoutingConfig();
        routeOverride = {
            route_mode:     cfg.mode,
            force_route:    cfg.force || undefined,
            model_override: cfg.model_override || undefined,
            counsel_mode:   cfg.counsel_mode || undefined,
            counsel_models: cfg.models || undefined,
        };
    } else {
        const mode    = localStorage.getItem('rc-mode') || 'auto';
        const force   = localStorage.getItem('rc-force') === 'true';
        const model   = localStorage.getItem('rc-model-override') || '';
        const counsel = localStorage.getItem('rc-counsel-mode') || 'vote';
        let counselModels;
        try { counselModels = JSON.parse(localStorage.getItem('rc-counsel-models')); } catch { counselModels = null; }
        routeOverride = {
            route_mode:     mode,
            force_route:    force || undefined,
            model_override: model || undefined,
            counsel_mode:   mode === 'counsel' ? counsel : undefined,
            counsel_models: mode === 'counsel' && counselModels ? counselModels : undefined,
        };
    }

    Object.keys(routeOverride).forEach(k => routeOverride[k] === undefined && delete routeOverride[k]);
    const mergedOptions = Object.assign({}, options || {}, routeOverride);

    if (_origSendWS) return _origSendWS.call(this, message, mergedOptions);
    console.warn('[UCB] sendMessageViaWebSocket original not found');
};

// ─────────────────────────────────────────────────────────────────────────────
// Tooltip helpers
// ─────────────────────────────────────────────────────────────────────────────
let _ttEl = null;
function _showTooltip(el) {
    _hideTooltip();
    const text = el.dataset.tooltip; if (!text) return;
    _ttEl = document.createElement('div');
    _ttEl.className = 'ucb-tooltip'; _ttEl.textContent = text;
    document.body.appendChild(_ttEl);
    const r = el.getBoundingClientRect();
    _ttEl.style.left = r.left + r.width/2 - _ttEl.offsetWidth/2 + 'px';
    _ttEl.style.top  = r.bottom + 6 + 'px';
}
function _hideTooltip() { _ttEl?.remove(); _ttEl = null; }

// ─────────────────────────────────────────────────────────────────────────────
// Utility
// ─────────────────────────────────────────────────────────────────────────────
function _escH(s) {
    return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ─────────────────────────────────────────────────────────────────────────────
// Icon SVG set
// ─────────────────────────────────────────────────────────────────────────────
const icons = {
    canvas:   `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="12" cy="12" r="3"/></svg>`,
    mic:      `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>`,
    speaker:  `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 5L6 9H2v6h4l5 4V5z"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>`,
    stop:     `<svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor"><rect x="5" y="5" width="14" height="14" rx="2"/></svg>`,
    gear:     `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/></svg>`,
    route:    `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="6" cy="19" r="3"/><circle cx="18" cy="5" r="3"/><path d="M6 16V9a6 6 0 0 1 6-6h2M18 8v7a6 6 0 0 1-6 6H10"/></svg>`,
    graph:    `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="2"/><circle cx="12" cy="5" r="2"/><circle cx="19" cy="12" r="2"/><circle cx="5" cy="12" r="2"/><path d="M12 7v3m0 4v3m-5-5h3m4 0h3"/></svg>`,
    search:   `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>`,
    attach:   `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>`,
    history:  `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/></svg>`,
    settings: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/></svg>`,
    trash:    `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>`,
    download: `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>`,
    chevron:  `<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" class="ucb-chevron"><polyline points="6 9 12 15 18 9"/></svg>`,
    layers:   `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>`,
    graphNode:`<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="5" r="2.2"/><circle cx="4" cy="19" r="2.2"/><circle cx="20" cy="19" r="2.2"/><line x1="12" y1="7.2" x2="4.8" y2="17"/><line x1="12" y1="7.2" x2="19.2" y2="17"/><line x1="6.2" y1="19" x2="17.8" y2="19"/></svg>`,
};

// ─────────────────────────────────────────────────────────────────────────────
// CSS
// ─────────────────────────────────────────────────────────────────────────────
function _injectCSS() {
    if (document.getElementById('ucb-css')) return;
    const s = document.createElement('style');
    s.id = 'ucb-css';
    s.textContent = `
/* ── reset ── */
#ucb-root *, #ucb-root *::before, #ucb-root *::after { box-sizing: border-box; }

/* ── toolbar ── */
.ucb-toolbar {
    display: flex; align-items: center; gap: 8px; padding: 4px 10px;
    background: var(--panel-bg, #1e293b); border-bottom: 1px solid var(--border, #334155);
    min-height: 36px; flex-shrink: 0; width: 100%; position: relative; z-index: 200;
}
.ucb-cluster { display: flex; align-items: center; gap: 3px; }
.ucb-cluster--right { margin-left: auto; }
.ucb-divider { width: 1px; height: 18px; background: var(--border, #334155); margin: 0 3px; flex-shrink: 0; }

/* ── buttons ── */
.ucb-btn {
    display: inline-flex; align-items: center; gap: 4px; padding: 4px 7px;
    background: transparent; border: 1px solid transparent; border-radius: 5px;
    color: var(--text-muted, #94a3b8); cursor: pointer; font-size: 11px; font-weight: 500;
    line-height: 1; transition: background .12s, color .12s, border-color .12s;
    white-space: nowrap; user-select: none; position: relative;
}
.ucb-btn:hover { background: var(--bg, #0f172a); border-color: var(--border, #334155); color: var(--text, #e2e8f0); }
.ucb-btn--on   { background: var(--accent, #3b82f6) !important; border-color: var(--accent, #3b82f6) !important; color: #fff !important; }
.ucb-btn--active { background: var(--bg, #0f172a); border-color: var(--accent, #3b82f6); color: var(--accent, #3b82f6); }
.ucb-btn--active .ucb-chevron { transform: rotate(180deg); }
.ucb-btn--danger { color: #ef4444; }
.ucb-btn--danger:hover { background: rgba(239,68,68,.1); border-color: #ef4444; color:#ef4444; }
.ucb-btn--panel { gap: 5px; }
/* CI and MG direct-toggle buttons — slightly distinct accent on hover */
.ucb-btn--ci:hover, .ucb-btn--ci.ucb-btn--on { border-color: #8b5cf6 !important; }
.ucb-btn--ci.ucb-btn--on { background: #8b5cf6 !important; }
.ucb-btn--mg:hover, .ucb-btn--mg.ucb-btn--on { border-color: #10b981 !important; }
.ucb-btn--mg.ucb-btn--on { background: #10b981 !important; }
.ucb-label { font-size: 11px; }
.ucb-chevron { transition: transform .15s; }

/* VAD bars */
.ucb-vad { display: inline-flex; align-items: center; gap: 1.5px; height: 12px; opacity: .3; transition: opacity .2s; }
.ucb-btn--on .ucb-vad { opacity: 1; }
.ucb-vad i { display: block; width: 2px; height: 3px; background: currentColor; border-radius: 1px; }
.ucb-btn--on .ucb-vad i { animation: ucbVad .35s ease-in-out infinite alternate; }
.ucb-vad i:nth-child(1){animation-delay:0s}.ucb-vad i:nth-child(2){animation-delay:.07s}
.ucb-vad i:nth-child(3){animation-delay:.14s}.ucb-vad i:nth-child(4){animation-delay:.07s}
.ucb-vad i:nth-child(5){animation-delay:0s}
@keyframes ucbVad { from{height:2px} to{height:12px} }

/* ── search ── */
.ucb-search-wrap { flex: 1; max-width: 280px; position: relative; display: flex; align-items: center; }
.ucb-search-icon { position: absolute; left: 9px; color: var(--text-muted, #94a3b8); pointer-events: none; display: flex; }
.ucb-search {
    width: 100%; padding: 5px 28px 5px 30px; background: var(--bg, #0f172a);
    border: 1px solid var(--border, #334155); border-radius: 5px;
    color: var(--text, #e2e8f0); font-size: 12px; outline: none; transition: border-color .15s;
}
.ucb-search:focus { border-color: var(--accent, #3b82f6); }
.ucb-search-clear { position: absolute; right: 7px; background: none; border: none; color: var(--text-muted, #94a3b8); cursor: pointer; font-size: 13px; padding: 1px 3px; border-radius: 3px; }
.ucb-search-clear:hover { color: var(--text, #e2e8f0); }

/* ── status ── */
.ucb-status { font-size: 11px; color: var(--accent, #3b82f6); font-weight: 500; white-space: nowrap; opacity: 0; transition: opacity .2s; max-width: 180px; overflow: hidden; text-overflow: ellipsis; }

/* ── backdrop ── */
.ucb-backdrop { display: none; position: fixed; inset: 0; z-index: 9990; background: transparent; }
.ucb-backdrop--active { display: block; }

/* ── flyout panels ── */
#ucb-panel-host { position: fixed; top: 0; left: 0; z-index: 9990; pointer-events: none; }
#ucb-panel-host > * { pointer-events: all; }
.ucb-panel { display: none; position: fixed; background: var(--panel-bg, #1e293b); border: 1px solid var(--border, #334155); border-radius: 8px; box-shadow: 0 12px 40px rgba(0,0,0,.55); z-index: 9995; overflow: hidden; animation: ucbSlideIn .15s ease; }
.ucb-panel--open { display: block; }
@keyframes ucbSlideIn { from{opacity:0;transform:translateY(-6px)} to{opacity:1;transform:translateY(0)} }
.ucb-panel-inner { padding: 14px; overflow-y: auto; height: 100%; max-height: inherit; display: flex; flex-direction: column; gap: 12px; }

/* ── panel internals ── */
.ucb-phead { font-size: 11px; color: var(--text-muted, #94a3b8); }
.ucb-phead-status { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.ucb-phead-status .ok { color: #4ade80; } .ucb-phead-status .na { color: #f87171; }
.ucb-pgroup { display: flex; flex-direction: column; gap: 6px; padding-bottom: 12px; border-bottom: 1px solid rgba(51,65,85,.6); }
.ucb-pgroup:last-child { border-bottom: none; padding-bottom: 0; }
.ucb-pgroup--stats { flex-direction: row; gap: 8px; }
.ucb-stat { flex:1; display:flex; flex-direction:column; align-items:center; padding:8px; background:var(--bg,#0f172a); border-radius:6px; font-size:10px; color:var(--text-muted,#94a3b8); text-transform:uppercase; letter-spacing:.5px; }
.ucb-stat span { font-size:18px; font-weight:700; color:var(--accent,#3b82f6); }
.ucb-pgroup-label { font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:.7px; color:var(--accent,#3b82f6); display:flex; align-items:center; justify-content:space-between; }
.ucb-row { display:flex; align-items:center; justify-content:space-between; gap:8px; font-size:12px; color:var(--text,#e2e8f0); padding:4px 0; }
.ucb-row input[type=checkbox] { width:14px; height:14px; cursor:pointer; accent-color:var(--accent,#3b82f6); }
.ucb-sel { background:var(--bg,#0f172a); border:1px solid var(--border,#334155); border-radius:4px; color:var(--text,#e2e8f0); padding:4px 6px; font-size:12px; cursor:pointer; }
.ucb-sel:focus { outline:none; border-color:var(--accent,#3b82f6); }
.ucb-sel--full { width:100%; } .ucb-sel--sm { max-width:130px; }
.ucb-inp { background:var(--bg,#0f172a); border:1px solid var(--border,#334155); border-radius:4px; color:var(--text,#e2e8f0); padding:5px 8px; font-size:12px; flex:1; min-width:0; }
.ucb-inp:focus { outline:none; border-color:var(--accent,#3b82f6); }
.ucb-inp--sm { max-width:80px; }
.ucb-slider-row { display:flex; align-items:center; gap:8px; }
.ucb-slider-row input[type=range] { flex:1; }
.ucb-slider-row span { font-size:11px; color:var(--text-muted,#94a3b8); min-width:34px; }
.ucb-desc { font-size:12px; color:var(--text-muted,#94a3b8); line-height:1.5; padding:8px 10px; background:var(--bg,#0f172a); border-radius:5px; border-left:3px solid var(--accent,#3b82f6); margin-top:4px; }
.ucb-desc b { color:var(--text,#e2e8f0); }
.ucb-mode-row { display:flex; gap:5px; flex-wrap:wrap; }
.ucb-mode-btn { flex:1; min-width:60px; padding:6px 8px; background:var(--bg,#0f172a); border:1px solid var(--border,#334155); color:var(--text,#e2e8f0); border-radius:5px; font-size:12px; font-weight:600; cursor:pointer; transition:all .15s; }
.ucb-mode-btn:hover { border-color:var(--accent,#3b82f6); }
.ucb-mode-btn--on { background:var(--accent,#3b82f6) !important; border-color:var(--accent,#3b82f6) !important; color:#fff !important; }
.ucb-quick-grid { display:grid; grid-template-columns:1fr 1fr; gap:5px; }
.ucb-quick-btn { padding:8px; background:var(--bg,#0f172a); border:1px solid var(--border,#334155); color:var(--text,#e2e8f0); border-radius:5px; font-size:12px; cursor:pointer; transition:all .15s; text-align:left; }
.ucb-quick-btn:hover { border-color:var(--accent,#3b82f6); background:var(--panel-bg,#1e293b); }
.ucb-counsel-row { display:flex; align-items:center; gap:6px; margin-bottom:4px; }
.ucb-counsel-row .ucb-sel { flex:1; }
.ucb-pactions { display:flex; gap:6px; justify-content:flex-end; padding-top:4px; }
.ucb-pbtn { padding:6px 13px; border-radius:5px; font-size:12px; cursor:pointer; background:transparent; border:1px solid var(--border,#334155); color:var(--text-muted,#94a3b8); transition:all .15s; }
.ucb-pbtn:hover { border-color:var(--accent,#3b82f6); color:var(--text,#e2e8f0); }
.ucb-pbtn--primary { background:var(--accent,#3b82f6) !important; border-color:var(--accent,#3b82f6) !important; color:#fff !important; font-weight:600; }
.ucb-pbtn--primary:hover { background:var(--accent-hover,#2563eb) !important; }
.ucb-pbtn--danger { color:#ef4444 !important; border-color:rgba(239,68,68,.4) !important; }
.ucb-pbtn--danger:hover { background:rgba(239,68,68,.1) !important; }
.ucb-pbtn--xs { padding:3px 8px; font-size:11px; }
.ucb-icon-btn { display:inline-flex; align-items:center; justify-content:center; width:24px; height:24px; background:transparent; border:1px solid var(--border,#334155); border-radius:4px; color:var(--text-muted,#94a3b8); cursor:pointer; font-size:11px; transition:all .15s; padding:0; }
.ucb-icon-btn:hover { border-color:var(--accent,#3b82f6); color:var(--text,#e2e8f0); }
.ucb-danger:hover { border-color:#ef4444 !important; color:#ef4444 !important; }
.ucb-link { background:none; border:none; color:var(--accent,#3b82f6); font-size:12px; cursor:pointer; padding:0; }
.ucb-link:hover { text-decoration:underline; }
.ucb-badge { background:var(--accent,#3b82f6); color:#fff; border-radius:10px; padding:1px 6px; font-size:10px; font-weight:700; }
.ucb-empty { padding:20px; text-align:center; color:var(--text-muted,#94a3b8); font-size:13px; }
.ucb-error { color:#ef4444 !important; }

/* ── history list ── */
.ucb-hist-list { display:flex; flex-direction:column; gap:6px; max-height:420px; overflow-y:auto; }
.ucb-hist-item { padding:10px 12px; background:var(--bg,#0f172a); border:1px solid var(--border,#334155); border-radius:7px; transition:all .15s; }
.ucb-hist-item:hover { border-color:var(--accent,#3b82f6); }
.ucb-hist-item--current { border-color:var(--accent,#3b82f6); background:rgba(59,130,246,.05); }
.ucb-hist-meta { display:flex; align-items:center; gap:6px; margin-bottom:3px; }
.ucb-hist-title { font-size:13px; font-weight:600; color:var(--text,#e2e8f0); flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.ucb-hist-sub { font-size:11px; color:var(--text-muted,#94a3b8); margin-bottom:4px; }
.ucb-hist-preview { font-size:12px; color:var(--text-muted,#94a3b8); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; margin-bottom:6px; }
.ucb-hist-actions { display:flex; gap:5px; }

/* ── tooltip ── */
.ucb-tooltip { position:fixed; background:#0f172a; color:#e2e8f0; border:1px solid #334155; border-radius:4px; padding:4px 8px; font-size:11px; white-space:nowrap; pointer-events:none; z-index:99999; box-shadow:0 4px 12px rgba(0,0,0,.4); }

/* ── hide legacy panels (not rc-panel — routing module needs its DOM alive) ── */
#vera-voice-bar, #vera-control-bar, #vera-chat-controls,
#chat-control-bar, #control-bar,
.graph-context-panel, .voice-bar, .settings-panel, .history-panel
{ display: none !important; }

/* ── CI/MG own buttons hidden — UCB is the surface ── */
#ci-panel-btn, #mg-open-btn { display: none !important; }

/* ═══════════════════════════════════════════
   PER-MESSAGE ACTION BAR
   ═══════════════════════════════════════════ */
.vera-msg-actions {
    display: flex; align-items: center; gap: 3px;
    padding: 4px 4px 2px; opacity: 0;
    transition: opacity 0.18s ease; flex-wrap: wrap;
}
.message-row:hover .vera-msg-actions,
.chat-message:hover .vera-msg-actions,
.msg-bubble:hover .vera-msg-actions,
.user-message:hover .vera-msg-actions,
.assistant-message:hover .vera-msg-actions,
.vera-message:hover .vera-msg-actions,
.message:hover .vera-msg-actions,
.chat-turn:hover .vera-msg-actions,
[data-role]:hover .vera-msg-actions { opacity: 1; }

.vma-btn {
    display: inline-flex; align-items: center; gap: 3px;
    padding: 3px 7px; background: transparent;
    border: 1px solid var(--border, #334155); border-radius: 4px;
    color: var(--text-muted, #64748b); cursor: pointer;
    font-size: 10px; font-weight: 500; font-family: inherit;
    line-height: 1; transition: all 0.12s; white-space: nowrap; user-select: none;
}
.vma-btn:hover { background: var(--panel-bg, #1e293b); border-color: var(--accent, #3b82f6); color: var(--text, #e2e8f0); }
.vma-btn[data-action="prompt"]:hover { border-color: #8b5cf6; color: #a78bfa; }
.vma-btn svg { flex-shrink: 0; }

/* ═══════════════════════════════════════════
   MESSAGE CONTEXT PANEL
   ═══════════════════════════════════════════ */
#vera-msg-ctx-panel {
    position: fixed; width: 340px; max-height: 520px; z-index: 9800;
    background: var(--bg, #0f172a); border: 1px solid var(--border, #1e293b);
    border-radius: 9px; box-shadow: 0 16px 50px rgba(0,0,0,.7), 0 0 0 1px rgba(59,130,246,.08);
    display: flex; flex-direction: column; overflow: hidden;
    font-size: 12px; color: var(--text, #e2e8f0);
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    animation: vmcp-in 0.18s cubic-bezier(.34,1.4,.64,1);
}
@keyframes vmcp-in { from{opacity:0;transform:translateY(-8px) scale(.97)} to{opacity:1;transform:none} }

.vmcp-header { display:flex; align-items:center; padding:8px 10px; background:var(--panel-bg,#1e293b); border-bottom:1px solid var(--border,#1e293b); flex-shrink:0; gap:6px; }
.vmcp-title { display:flex; align-items:center; gap:5px; font-size:10px; font-weight:700; letter-spacing:.8px; text-transform:uppercase; color:var(--text-muted,#64748b); flex:1; }
.vmcp-close { background:transparent; border:none; color:var(--text-muted,#475569); cursor:pointer; font-size:13px; padding:1px 4px; border-radius:3px; line-height:1; transition:all .15s; }
.vmcp-close:hover { color:var(--text,#e2e8f0); background:rgba(255,255,255,.06); }

.vmcp-body { flex:1; overflow-y:auto; padding:10px; display:flex; flex-direction:column; gap:8px; }
.vmcp-body::-webkit-scrollbar { width:3px; }
.vmcp-body::-webkit-scrollbar-thumb { background:var(--border,#1e293b); border-radius:2px; }

.vmcp-loading { display:flex; align-items:center; gap:8px; padding:20px; color:var(--text-muted,#64748b); font-size:12px; justify-content:center; }
.vmcp-spinner { width:14px; height:14px; border:2px solid var(--border,#334155); border-top-color:var(--accent,#3b82f6); border-radius:50%; animation:vmcp-spin .7s linear infinite; flex-shrink:0; }
@keyframes vmcp-spin { to{transform:rotate(360deg)} }

.vmcp-empty { padding:16px; text-align:center; color:var(--text-muted,#475569); font-size:11px; line-height:1.5; }
.vmcp-section-label { font-size:9px; font-weight:700; text-transform:uppercase; letter-spacing:.8px; color:var(--accent,#3b82f6); margin-bottom:4px; margin-top:4px; }

.vmcp-vec-list { display:flex; flex-direction:column; gap:3px; }
.vmcp-vec { display:flex; align-items:flex-start; gap:6px; padding:5px 7px; background:var(--panel-bg,#1e293b); border-radius:4px; border:1px solid transparent; transition:border-color .15s; }
.vmcp-vec:hover { border-color:var(--border,#334155); }
.vmcp-vec-score { font-size:10px; font-weight:700; color:#34d399; flex-shrink:0; min-width:28px; }
.vmcp-vec-text  { font-size:11px; color:var(--text-muted,#94a3b8); line-height:1.4; word-break:break-word; }

.vmcp-tags { display:flex; flex-wrap:wrap; gap:4px; }
.vmcp-tag { padding:2px 7px; background:rgba(100,116,139,.12); border:1px solid rgba(100,116,139,.2); border-radius:10px; font-size:10px; color:var(--text-muted,#94a3b8); }
.vmcp-tag--focus { background:rgba(251,191,36,.1); border-color:rgba(251,191,36,.3); color:#fbbf24; }
.vmcp-tag--more  { background:transparent; border-style:dashed; }

.vmcp-hist-list { display:flex; flex-direction:column; gap:3px; }
.vmcp-hist-turn { display:flex; align-items:flex-start; gap:6px; padding:3px 5px; }
.vmcp-hist-role { font-size:9px; font-weight:700; text-transform:uppercase; padding:2px 5px; border-radius:3px; flex-shrink:0; margin-top:1px; }
.vmcp-role-user,.vmcp-role-query   { background:rgba(59,130,246,.12); color:#60a5fa; }
.vmcp-role-vera,.vmcp-role-assistant { background:rgba(139,92,246,.12); color:#a78bfa; }
.vmcp-role-system { background:rgba(100,116,139,.12); color:#94a3b8; }
.vmcp-hist-text { font-size:11px; color:var(--text-muted,#94a3b8); line-height:1.4; }

.vmcp-node-list { display:flex; flex-direction:column; gap:3px; }
.vmcp-node { display:flex; align-items:flex-start; gap:6px; padding:5px 7px; background:var(--panel-bg,#1e293b); border-radius:4px; border:1px solid transparent; cursor:pointer; transition:all .15s; }
.vmcp-node:hover { border-color:var(--accent,#3b82f6); }
.vmcp-node-type  { font-size:9px; font-weight:700; color:#10b981; flex-shrink:0; text-transform:uppercase; min-width:40px; }
.vmcp-node-text  { font-size:11px; color:var(--text-muted,#94a3b8); flex:1; word-break:break-word; }
.vmcp-node-score { font-size:10px; color:#34d399; flex-shrink:0; }

.vmcp-timing { font-size:9px; color:var(--text-muted,#334155); padding:4px 0 0; border-top:1px solid var(--border,#0f172a); margin-top:4px; }
.vmcp-actions { display:flex; gap:5px; padding-top:4px; flex-wrap:wrap; }
.vmcp-btn { padding:5px 10px; background:transparent; border:1px solid var(--border,#1e293b); border-radius:4px; color:var(--text-muted,#94a3b8); font-size:10px; font-family:inherit; cursor:pointer; transition:all .15s; }
.vmcp-btn:hover { border-color:var(--accent,#3b82f6); color:var(--accent,#3b82f6); }
`;
    document.head.appendChild(s);
}

console.log('[UCB] Module parsed — v2 with CI/MG direct-toggle');
})();