/**
 * ChatbotManager - Bot Configuration & Control UI
 *
 * Mirrors the SessionHistory architecture:
 * - Skeleton render → async data load
 * - Debounced state updates
 * - Event delegation via data-action attributes
 * - Progressive status polling
 *
 * USAGE in Chat.js activateTab():
 *   if (tabId === 'chatbots') {
 *       setTimeout(() => {
 *           const container = document.getElementById('chatbot-manager-container');
 *           if (container && !container._chatbotInit) {
 *               container._chatbotInit = true;
 *               const mgr = new ChatbotManager({
 *                   containerId: 'chatbot-manager-container',
 *                   apiBaseUrl: 'http://llm.int:8888/api/chatbots'
 *               });
 *               mgr.init();
 *           }
 *       }, 50);
 *   }
 *
 * And getTabContent('chatbots') should return:
 *   '<div id="chatbot-manager-container" style="height:100%;overflow-y:auto;position:relative;"></div>'
 */

class ChatbotManager {
    constructor(config = {}) {
        // ── Validate & store config ────────────────────────────────────
        // Always require a full absolute URL in production.
        // Falls back to relative only as last resort (will warn).
        const rawBase = config.apiBaseUrl || '';
        if (!rawBase) {
            console.warn('[ChatbotManager] No apiBaseUrl provided. Defaulting to http://llm.int:8888/api/chatbots');
        }
        if (rawBase && !rawBase.startsWith('http')) {
            console.warn(`[ChatbotManager] apiBaseUrl "${rawBase}" looks relative — this will fail when page is loaded from file://. Pass a full http:// URL.`);
        }

        this.config = {
            containerId:      config.containerId  || 'chatbot-manager',
            apiBaseUrl:       rawBase              || 'http://llm.int:8888/api/chatbots',
            pollInterval:     config.pollInterval  || 8000,
            onStatusChange:   config.onStatusChange || (() => {})
        };

        this.state = {
            statuses:         [],
            config:           null,
            stats:            null,
            logs:             [],
            loading:          false,
            activeTab:        'overview',
            selectedPlatform: null,
            editingPlatform:  null,
            editBuffer:       {},
            showTokens:       {},
            actionInProgress: {},
            error:            null,
            toasts:           [],
            telegramUsers:    [],
            logFilter:        null,
            notifyMessage:    '',
            notifyUserId:     ''
        };

        this.updateTimeout    = null;
        this.pollTimer        = null;
        this.container        = null;
        this.initialized      = false;
        this._toastId         = 0;
        this._listenersAttached = false;  // ← prevent duplicate listener accumulation
    }

    // ================================================================
    // INIT
    // ================================================================

    async init() {
        if (this.initialized) return;

        this.container = document.getElementById(this.config.containerId);
        if (!this.container) {
            console.error(`[ChatbotManager] Container #${this.config.containerId} not found in DOM.`);
            return;
        }

        this.initialized = true;
        ChatbotManager.injectStyles();
        this.renderSkeleton();

        await Promise.all([
            this.loadStatuses(),
            this.loadConfig(),
            this.loadStats()
        ]);

        this.startPolling();
    }

    startPolling() {
        if (this.pollTimer) clearInterval(this.pollTimer);
        this.pollTimer = setInterval(() => {
            this.loadStatuses(true);
            this.loadStats(true);
        }, this.config.pollInterval);
    }

    destroy() {
        if (this.pollTimer)    clearInterval(this.pollTimer);
        if (this.updateTimeout) clearTimeout(this.updateTimeout);
        if (this.container)   this.container.innerHTML = '';
        this.initialized = false;
    }

    // ================================================================
    // FETCH HELPER — centralises error handling & URL building
    // ================================================================

    async _fetch(path, options = {}) {
        const url = `${this.config.apiBaseUrl}${path}`;
        let res;
        try {
            res = await fetch(url, options);
        } catch (networkErr) {
            // Network-level failure (CORS, DNS, offline, etc.)
            throw new Error(`Network error reaching ${url}: ${networkErr.message}`);
        }
        if (!res.ok) {
            throw new Error(`HTTP ${res.status} from ${url}`);
        }
        return res.json();
    }

    // ================================================================
    // DATA LOADING
    // ================================================================

    async loadStatuses(silent = false) {
        if (!silent) this.setState({ loading: true });
        try {
            const data = await this._fetch('/status');
            this.setState({ statuses: Array.isArray(data) ? data : [], loading: false, error: null });
        } catch (e) {
            console.warn('[ChatbotManager] loadStatuses failed:', e.message);
            if (!silent) this.setState({ error: e.message, loading: false });
        }
    }

    async loadConfig() {
        try {
            const data = await this._fetch('/config');
            this.setState({ config: data });
        } catch (e) {
            console.warn('[ChatbotManager] loadConfig failed:', e.message);
        }
    }

    async loadStats(silent = false) {
        try {
            const data = await this._fetch('/stats/summary');
            this.setState({ stats: data });
        } catch (e) {
            if (!silent) console.warn('[ChatbotManager] loadStats failed:', e.message);
        }
    }

    async loadLogs(platform = null) {
        try {
            const params = new URLSearchParams({ limit: 60 });
            if (platform) params.append('platform', platform);
            const data = await this._fetch(`/logs/recent?${params}`);
            this.setState({ logs: data.logs || [], logFilter: platform });
        } catch (e) {
            console.warn('[ChatbotManager] loadLogs failed:', e.message);
        }
    }

    async loadTelegramUsers() {
        try {
            const data = await this._fetch('/telegram/users');
            this.setState({ telegramUsers: data.users || [] });
        } catch (e) {
            console.warn('[ChatbotManager] loadTelegramUsers failed:', e.message);
        }
    }

    // ================================================================
    // ACTIONS
    // ================================================================

    async performAction(platform, action) {
        this.setState({ actionInProgress: { ...this.state.actionInProgress, [platform]: action } });
        try {
            const data = await this._fetch('/action', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ platform, action })
            });
            this.showToast(`${platform}: ${data.status}`, 'success');
            await this.loadStatuses();
            await this.loadStats();
        } catch (e) {
            this.showToast(`Failed to ${action} ${platform}: ${e.message}`, 'error');
        } finally {
            const updated = { ...this.state.actionInProgress };
            delete updated[platform];
            this.setState({ actionInProgress: updated });
        }
    }

    async saveConfig(platform) {
        const edits = this.state.editBuffer[platform];
        if (!edits || Object.keys(edits).length === 0) {
            this.showToast('No changes to save', 'info');
            return;
        }

        this.setState({ actionInProgress: { ...this.state.actionInProgress, [`save_${platform}`]: true } });
        try {
            const data = await this._fetch('/config/update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ platform, config: edits })
            });

            const msg = data.restart_required
                ? `Saved. ⚠️ Restart required for token changes.`
                : `${platform} config saved (${(data.changes || []).length} changes)`;
            this.showToast(msg, data.restart_required ? 'warning' : 'success');

            const buf = { ...this.state.editBuffer };
            delete buf[platform];
            this.setState({ editBuffer: buf, editingPlatform: null });
            await this.loadConfig();
        } catch (e) {
            this.showToast(`Save failed: ${e.message}`, 'error');
        } finally {
            const updated = { ...this.state.actionInProgress };
            delete updated[`save_${platform}`];
            this.setState({ actionInProgress: updated });
        }
    }

    async sendTestNotification() {
        const { notifyMessage, notifyUserId } = this.state;
        if (!notifyMessage.trim()) {
            this.showToast('Enter a message first', 'warning');
            return;
        }
        try {
            const body = { platform: 'telegram', message: notifyMessage };
            if (notifyUserId) body.user_id = parseInt(notifyUserId, 10);

            const data = await this._fetch('/notify', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            this.showToast(`Notification ${data.status}`, data.status === 'sent' ? 'success' : 'error');
        } catch (e) {
            this.showToast(`Notification failed: ${e.message}`, 'error');
        }
    }

    // ================================================================
    // STATE
    // ================================================================

    setState(newState) {
        this.state = { ...this.state, ...newState };
        if (this.updateTimeout) clearTimeout(this.updateTimeout);
        this.updateTimeout = setTimeout(() => this.render(), 16);
    }

    showToast(message, type = 'info') {
        const id = ++this._toastId;
        const toasts = [...this.state.toasts, { id, message, type }];
        this.setState({ toasts });
        setTimeout(() => {
            this.setState({ toasts: this.state.toasts.filter(t => t.id !== id) });
        }, 4000);
    }

    getStatusForPlatform(platform) {
        return this.state.statuses.find(s => s.platform === platform) || {
            platform, enabled: false, running: false, connected: false
        };
    }

    getPlatformConfig(platform) {
        const cfg = this.state.config;
        if (!cfg) return {};
        return cfg[platform] || {};
    }

    // ================================================================
    // RENDER
    // ================================================================

    renderSkeleton() {
        if (!this.container) return;
        this.container.innerHTML = `
            <div class="cbm-root">
                <div class="cbm-header">
                    <div class="cbm-title-block">
                        <div class="cbm-icon">⚡</div>
                        <div>
                            <h1 class="cbm-title">Bot Control</h1>
                            <p class="cbm-subtitle">Messaging Platform Manager</p>
                        </div>
                    </div>
                    <div class="cbm-header-stats">
                        <div class="cbm-stat-pill">—</div>
                    </div>
                </div>
                <div class="cbm-tabs"></div>
                <div class="cbm-body">
                    <div class="cbm-loading-state">
                        <div class="cbm-spinner"></div>
                        <span>Connecting to bot services…</span>
                    </div>
                </div>
                <div class="cbm-toasts"></div>
            </div>
        `;
        // Attach once here — this.container persists across all re-renders
        this.attachEventListeners();
    }

    render() {
        if (!this.container) return;

        // Preserve scroll position so re-renders don't jump
        const body = this.container.querySelector('.cbm-body');
        const scrollTop = body ? body.scrollTop : 0;

        this.container.innerHTML = `
            <div class="cbm-root">
                ${this.renderHeader()}
                ${this.renderTabs()}
                <div class="cbm-body">
                    ${this.renderActiveTab()}
                </div>
                ${this.renderToasts()}
            </div>
        `;

        const newBody = this.container.querySelector('.cbm-body');
        if (newBody && scrollTop) newBody.scrollTop = scrollTop;
    }

    // ── HEADER ────────────────────────────────────────────────────────

    renderHeader() {
        const { stats, loading } = this.state;
        const active = stats ? stats.active_platforms : '—';
        const total  = stats ? stats.total_platforms  : 3;
        const users  = stats ? stats.total_registered_users : '—';

        return `
            <div class="cbm-header">
                <div class="cbm-title-block">
                    <div class="cbm-icon">⚡</div>
                    <div>
                        <h1 class="cbm-title">Bot Control</h1>
                        <p class="cbm-subtitle">Messaging Platform Manager</p>
                    </div>
                </div>
                <div class="cbm-header-stats">
                    <div class="cbm-stat-pill ${active > 0 ? 'active' : ''}">
                        <span class="cbm-stat-dot"></span>
                        ${active}/${total} Active
                    </div>
                    <div class="cbm-stat-pill">
                        👥 ${users} Users
                    </div>
                    ${this.state.error ? `<div class="cbm-stat-pill cbm-pill-error" title="${this.escapeHtml(this.state.error)}">⚠ Error</div>` : ''}
                    <button class="cbm-refresh-btn" data-action="refresh" title="Refresh">
                        ${loading ? '<span class="cbm-spin">↻</span>' : '↻'}
                    </button>
                </div>
            </div>
        `;
    }

    // ── TABS ──────────────────────────────────────────────────────────

    renderTabs() {
        const tabs = [
            { id: 'overview',  label: '⬡ Overview'  },
            { id: 'telegram',  label: '✈ Telegram'  },
            { id: 'discord',   label: '◈ Discord'   },
            { id: 'slack',     label: '# Slack'      },
            { id: 'notify',    label: '🔔 Notify'   },
            { id: 'logs',      label: '▤ Logs'       }
        ];
        return `
            <div class="cbm-tabs">
                ${tabs.map(t => `
                    <button
                        class="cbm-tab ${this.state.activeTab === t.id ? 'active' : ''}"
                        data-action="set-tab"
                        data-tab="${t.id}"
                    >${t.label}</button>
                `).join('')}
            </div>
        `;
    }

    renderActiveTab() {
        if (this.state.error && !this.state.statuses.length) {
            return this.renderErrorState();
        }
        switch (this.state.activeTab) {
            case 'overview':  return this.renderOverview();
            case 'telegram':  return this.renderPlatformPanel('telegram');
            case 'discord':   return this.renderPlatformPanel('discord');
            case 'slack':     return this.renderPlatformPanel('slack');
            case 'notify':    return this.renderNotifyPanel();
            case 'logs':      return this.renderLogsPanel();
            default:          return this.renderOverview();
        }
    }

    renderErrorState() {
        return `
            <div class="cbm-error-state">
                <div class="cbm-error-icon">⚠</div>
                <h3>Cannot reach bot services</h3>
                <p class="cbm-error-msg">${this.escapeHtml(this.state.error || 'Unknown error')}</p>
                <p class="cbm-error-url">Endpoint: <code>${this.escapeHtml(this.config.apiBaseUrl)}</code></p>
                <button class="cbm-btn cbm-btn-start" data-action="refresh">↻ Retry</button>
            </div>
        `;
    }

    // ── OVERVIEW ──────────────────────────────────────────────────────

    renderOverview() {
        const platforms = ['telegram', 'discord', 'slack'];
        return `
            <div class="cbm-overview">
                <div class="cbm-platform-grid">
                    ${platforms.map(p => this.renderPlatformCard(p)).join('')}
                </div>
                ${this.renderQuickActions()}
            </div>
        `;
    }

    renderPlatformCard(platform) {
        const status     = this.getStatusForPlatform(platform);
        const inProgress = this.state.actionInProgress[platform];

        const icons  = { telegram: '✈', discord: '◈', slack: '#' };
        const colors = { telegram: 'blue', discord: 'purple', slack: 'green' };

        const statusClass = status.connected ? 'connected' : status.running ? 'running' : 'offline';
        const statusLabel = status.connected ? 'Connected'  : status.running ? 'Starting…' : 'Offline';

        return `
            <div class="cbm-platform-card cbm-card-${colors[platform]}" data-platform="${platform}">
                <div class="cbm-card-top">
                    <div class="cbm-card-platform-icon">${icons[platform]}</div>
                    <div class="cbm-card-info">
                        <div class="cbm-card-name">${platform.charAt(0).toUpperCase() + platform.slice(1)}</div>
                        <div class="cbm-status-badge ${statusClass}">
                            <span class="cbm-status-dot"></span>
                            ${statusLabel}
                        </div>
                    </div>
                    <div class="cbm-card-toggle">
                        <label class="cbm-toggle">
                            <input
                                type="checkbox"
                                ${status.enabled ? 'checked' : ''}
                                data-action="toggle-enabled"
                                data-platform="${platform}"
                            >
                            <span class="cbm-toggle-track"></span>
                        </label>
                    </div>
                </div>

                ${status.bot_username ? `<div class="cbm-card-username">@${this.escapeHtml(status.bot_username)}</div>` : ''}

                ${platform === 'telegram' && status.running ? `
                    <div class="cbm-card-metrics">
                        <span>👥 ${status.registered_users || 0} users</span>
                        <span>📬 ${status.queued_messages  || 0} queued</span>
                    </div>
                ` : ''}

                <div class="cbm-card-actions">
                    ${!status.running ? `
                        <button class="cbm-btn cbm-btn-start"
                            data-action="bot-action" data-platform="${platform}" data-bot-action="start"
                            ${inProgress ? 'disabled' : ''}
                        >${inProgress === 'start' ? '…' : '▶ Start'}</button>
                    ` : `
                        <button class="cbm-btn cbm-btn-stop"
                            data-action="bot-action" data-platform="${platform}" data-bot-action="stop"
                            ${inProgress ? 'disabled' : ''}
                        >${inProgress === 'stop' ? '…' : '■ Stop'}</button>
                        <button class="cbm-btn cbm-btn-restart"
                            data-action="bot-action" data-platform="${platform}" data-bot-action="restart"
                            ${inProgress ? 'disabled' : ''}
                        >↻</button>
                    `}
                    <button class="cbm-btn cbm-btn-test"
                        data-action="bot-action" data-platform="${platform}" data-bot-action="test"
                        ${inProgress ? 'disabled' : ''}
                    >⚡ Test</button>
                    <button class="cbm-btn cbm-btn-config"
                        data-action="set-tab" data-tab="${platform}"
                    >⚙</button>
                </div>
            </div>
        `;
    }

    renderQuickActions() {
        return `
            <div class="cbm-quick-actions">
                <div class="cbm-quick-label">Quick Actions</div>
                <div class="cbm-quick-btn-row">
                    <button class="cbm-btn cbm-btn-start" data-action="start-all">▶ Start All</button>
                    <button class="cbm-btn cbm-btn-stop"  data-action="stop-all">■ Stop All</button>
                    <button class="cbm-btn" data-action="set-tab" data-tab="logs">▤ View Logs</button>
                    <button class="cbm-btn" data-action="refresh">↻ Refresh Status</button>
                </div>
            </div>
        `;
    }

    // ── PLATFORM CONFIG PANEL ─────────────────────────────────────────

    renderPlatformPanel(platform) {
        const status     = this.getStatusForPlatform(platform);
        const cfg        = this.getPlatformConfig(platform);
        const editing    = this.state.editingPlatform === platform;
        const buf        = this.state.editBuffer[platform] || {};
        const showToken  = this.state.showTokens[platform];
        const inProgress = this.state.actionInProgress[`save_${platform}`];
        const icons      = { telegram: '✈', discord: '◈', slack: '#' };

        return `
            <div class="cbm-platform-panel">
                <div class="cbm-panel-header">
                    <div class="cbm-panel-title">
                        <span class="cbm-panel-icon">${icons[platform]}</span>
                        ${platform.charAt(0).toUpperCase() + platform.slice(1)} Configuration
                    </div>
                    <div class="cbm-panel-status">
                        <div class="cbm-status-badge ${status.connected ? 'connected' : 'offline'}">
                            <span class="cbm-status-dot"></span>
                            ${status.connected ? 'Connected' : 'Offline'}
                        </div>
                        ${status.bot_username ? `<span class="cbm-username-tag">@${this.escapeHtml(status.bot_username)}</span>` : ''}
                    </div>
                </div>

                <div class="cbm-panel-body">
                    ${this.renderPlatformFields(platform, cfg, buf, editing, showToken)}
                </div>

                <div class="cbm-panel-footer">
                    ${editing ? `
                        <button class="cbm-btn cbm-btn-save"
                            data-action="save-config" data-platform="${platform}"
                            ${inProgress ? 'disabled' : ''}
                        >${inProgress ? '…' : '✓ Save Changes'}</button>
                        <button class="cbm-btn"
                            data-action="cancel-edit" data-platform="${platform}"
                        >✕ Cancel</button>
                    ` : `
                        <button class="cbm-btn"
                            data-action="start-edit" data-platform="${platform}"
                        >✎ Edit</button>
                    `}
                    <div class="cbm-panel-bot-actions">
                        ${!status.running ? `
                            <button class="cbm-btn cbm-btn-start"
                                data-action="bot-action" data-platform="${platform}" data-bot-action="start"
                            >▶ Start Bot</button>
                        ` : `
                            <button class="cbm-btn cbm-btn-stop"
                                data-action="bot-action" data-platform="${platform}" data-bot-action="stop"
                            >■ Stop Bot</button>
                            <button class="cbm-btn cbm-btn-restart"
                                data-action="bot-action" data-platform="${platform}" data-bot-action="restart"
                            >↻ Restart</button>
                        `}
                        <button class="cbm-btn cbm-btn-test"
                            data-action="bot-action" data-platform="${platform}" data-bot-action="test"
                        >⚡ Test Connection</button>
                    </div>
                </div>

                ${platform === 'telegram' ? this.renderTelegramUsers() : ''}
            </div>
        `;
    }

    renderPlatformFields(platform, cfg, buf, editing, showToken) {
        // Merge config with edit buffer; buffer takes priority
        const val = (key) => {
            if (buf[key] !== undefined) return buf[key];
            if (cfg[key] !== undefined) return cfg[key];
            return '';
        };
        const dis = editing ? '' : 'disabled';
        const eye = showToken ? '🙈' : '👁';
        const inputType = showToken ? 'text' : 'password';

        if (platform === 'telegram') {
            return `
                <div class="cbm-field-grid">
                    <div class="cbm-field cbm-field-full">
                        <label class="cbm-label">Bot Token</label>
                        <div class="cbm-token-row">
                            <input type="${inputType}" class="cbm-input cbm-input-token"
                                value="${this.escapeHtml(String(val('token')))}"
                                placeholder="Enter Telegram bot token…"
                                data-field="token" data-platform="${platform}" ${dis}>
                            <button class="cbm-btn cbm-btn-eye" data-action="toggle-token" data-platform="${platform}">${eye}</button>
                        </div>
                        <span class="cbm-hint">From @BotFather on Telegram</span>
                    </div>

                    <div class="cbm-field">
                        <label class="cbm-label">Enabled</label>
                        <label class="cbm-toggle">
                            <input type="checkbox" ${val('enabled') ? 'checked' : ''}
                                data-field="enabled" data-platform="${platform}" ${dis}>
                            <span class="cbm-toggle-track"></span>
                        </label>
                    </div>

                    <div class="cbm-field">
                        <label class="cbm-label">Rate Limit (seconds)</label>
                        <input type="number" class="cbm-input cbm-input-small"
                            value="${val('rate_limit_seconds') || 2}" min="0" max="60"
                            data-field="rate_limit_seconds" data-platform="${platform}" ${dis}>
                    </div>

                    <div class="cbm-field cbm-field-full">
                        <label class="cbm-label">Owner IDs</label>
                        <input type="text" class="cbm-input"
                            value="${(val('owner_ids') || []).join(', ')}"
                            placeholder="123456789, 987654321"
                            data-field="owner_ids" data-platform="${platform}" ${dis}>
                        <span class="cbm-hint">Comma-separated Telegram user IDs (message @userinfobot to find yours)</span>
                    </div>

                    <div class="cbm-field cbm-field-full">
                        <label class="cbm-label">Allowed Users</label>
                        <input type="text" class="cbm-input"
                            value="${(val('allowed_users') || []).join(', ')}"
                            placeholder="Leave empty for owners only"
                            data-field="allowed_users" data-platform="${platform}" ${dis}>
                        <span class="cbm-hint">Additional user IDs permitted to interact with the bot</span>
                    </div>

                    <div class="cbm-field">
                        <label class="cbm-label">Max Message Length</label>
                        <input type="number" class="cbm-input cbm-input-small"
                            value="${val('max_message_length') || 4000}" min="100" max="4096"
                            data-field="max_message_length" data-platform="${platform}" ${dis}>
                    </div>
                </div>
            `;
        }

        if (platform === 'discord') {
            return `
                <div class="cbm-field-grid">
                    <div class="cbm-field cbm-field-full">
                        <label class="cbm-label">Bot Token</label>
                        <div class="cbm-token-row">
                            <input type="${inputType}" class="cbm-input cbm-input-token"
                                value="${this.escapeHtml(String(val('token')))}"
                                placeholder="Enter Discord bot token…"
                                data-field="token" data-platform="${platform}" ${dis}>
                            <button class="cbm-btn cbm-btn-eye" data-action="toggle-token" data-platform="${platform}">${eye}</button>
                        </div>
                        <span class="cbm-hint">From discord.com/developers/applications → Bot</span>
                    </div>

                    <div class="cbm-field">
                        <label class="cbm-label">Enabled</label>
                        <label class="cbm-toggle">
                            <input type="checkbox" ${val('enabled') ? 'checked' : ''}
                                data-field="enabled" data-platform="${platform}" ${dis}>
                            <span class="cbm-toggle-track"></span>
                        </label>
                    </div>

                    <div class="cbm-field">
                        <label class="cbm-label">Command Prefix</label>
                        <input type="text" class="cbm-input cbm-input-small"
                            value="${this.escapeHtml(String(val('prefix') || '!'))}" maxlength="3"
                            data-field="prefix" data-platform="${platform}" ${dis}>
                    </div>

                    <div class="cbm-field">
                        <label class="cbm-label">Respond to All Messages</label>
                        <label class="cbm-toggle">
                            <input type="checkbox" ${val('respond_to_all') ? 'checked' : ''}
                                data-field="respond_to_all" data-platform="${platform}" ${dis}>
                            <span class="cbm-toggle-track"></span>
                        </label>
                    </div>

                    <div class="cbm-field cbm-field-full">
                        <label class="cbm-label">Allowed Channels</label>
                        <input type="text" class="cbm-input"
                            value="${(val('allowed_channels') || []).join(', ')}"
                            placeholder="Channel IDs (leave empty for all)"
                            data-field="allowed_channels" data-platform="${platform}" ${dis}>
                    </div>
                </div>
            `;
        }

        if (platform === 'slack') {
            return `
                <div class="cbm-field-grid">
                    <div class="cbm-field cbm-field-full">
                        <label class="cbm-label">Bot Token (xoxb-…)</label>
                        <div class="cbm-token-row">
                            <input type="${inputType}" class="cbm-input cbm-input-token"
                                value="${this.escapeHtml(String(val('bot_token')))}"
                                placeholder="xoxb-…"
                                data-field="bot_token" data-platform="${platform}" ${dis}>
                            <button class="cbm-btn cbm-btn-eye" data-action="toggle-token" data-platform="${platform}">${eye}</button>
                        </div>
                    </div>

                    <div class="cbm-field cbm-field-full">
                        <label class="cbm-label">App Token (xapp-…)</label>
                        <input type="${inputType}" class="cbm-input"
                            value="${this.escapeHtml(String(val('app_token')))}"
                            placeholder="xapp-…"
                            data-field="app_token" data-platform="${platform}" ${dis}>
                        <span class="cbm-hint">Required for Socket Mode</span>
                    </div>

                    <div class="cbm-field">
                        <label class="cbm-label">Enabled</label>
                        <label class="cbm-toggle">
                            <input type="checkbox" ${val('enabled') ? 'checked' : ''}
                                data-field="enabled" data-platform="${platform}" ${dis}>
                            <span class="cbm-toggle-track"></span>
                        </label>
                    </div>

                    <div class="cbm-field">
                        <label class="cbm-label">Respond to All</label>
                        <label class="cbm-toggle">
                            <input type="checkbox" ${val('respond_to_all') ? 'checked' : ''}
                                data-field="respond_to_all" data-platform="${platform}" ${dis}>
                            <span class="cbm-toggle-track"></span>
                        </label>
                    </div>

                    <div class="cbm-field cbm-field-full">
                        <label class="cbm-label">Allowed Channels</label>
                        <input type="text" class="cbm-input"
                            value="${(val('allowed_channels') || []).join(', ')}"
                            placeholder="Channel names or IDs"
                            data-field="allowed_channels" data-platform="${platform}" ${dis}>
                    </div>
                </div>
            `;
        }

        return '<div class="cbm-empty-row">Unknown platform</div>';
    }

    renderTelegramUsers() {
        const users = this.state.telegramUsers;
        const roleColor = { owner: 'cbm-role-owner', admin: 'cbm-role-admin', user: 'cbm-role-user' };

        if (users.length === 0) {
            return `
                <div class="cbm-users-section">
                    <div class="cbm-section-header">
                        <span>Registered Users</span>
                        <button class="cbm-btn cbm-btn-sm" data-action="load-tg-users">Load</button>
                    </div>
                    <div class="cbm-empty-row">No users loaded — click Load to fetch</div>
                </div>
            `;
        }

        return `
            <div class="cbm-users-section">
                <div class="cbm-section-header">
                    <span>Registered Users (${users.length})</span>
                    <button class="cbm-btn cbm-btn-sm" data-action="load-tg-users">↻ Refresh</button>
                </div>
                <div class="cbm-users-table">
                    <div class="cbm-users-head">
                        <span>User ID</span><span>Chat ID</span><span>Role</span><span>Actions</span>
                    </div>
                    ${users.map(u => `
                        <div class="cbm-users-row">
                            <span class="cbm-mono">${u.user_id}</span>
                            <span class="cbm-mono">${u.chat_id}</span>
                            <span class="cbm-role-badge ${roleColor[u.role] || ''}">${u.role}</span>
                            <button class="cbm-btn cbm-btn-sm"
                                data-action="notify-user" data-user-id="${u.user_id}"
                            >📬 Notify</button>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }

    // ── NOTIFY PANEL ──────────────────────────────────────────────────

    renderNotifyPanel() {
        return `
            <div class="cbm-notify-panel">
                <div class="cbm-panel-header">
                    <div class="cbm-panel-title">
                        <span class="cbm-panel-icon">🔔</span>
                        Send Notification
                    </div>
                </div>

                <div class="cbm-notify-body">
                    <div class="cbm-field">
                        <label class="cbm-label">Platform</label>
                        <div class="cbm-segmented">
                            <button class="cbm-seg active">✈ Telegram</button>
                        </div>
                        <span class="cbm-hint">Proactive notifications currently supported via Telegram</span>
                    </div>

                    <div class="cbm-field">
                        <label class="cbm-label">Target User ID (optional)</label>
                        <input type="number" class="cbm-input cbm-input-small"
                            placeholder="Leave empty to notify all owners"
                            value="${this.escapeHtml(String(this.state.notifyUserId || ''))}"
                            data-action="notify-uid-input">
                    </div>

                    <div class="cbm-field cbm-field-full">
                        <label class="cbm-label">Message</label>
                        <textarea class="cbm-textarea" rows="5"
                            placeholder="Enter your notification message…"
                            data-action="notify-msg-input"
                        >${this.escapeHtml(this.state.notifyMessage || '')}</textarea>
                        <span class="cbm-hint">Supports HTML formatting: &lt;b&gt;, &lt;i&gt;, &lt;code&gt;</span>
                    </div>

                    <div class="cbm-notify-actions">
                        <button class="cbm-btn cbm-btn-send" data-action="send-notification">
                            📬 Send Notification
                        </button>
                        <button class="cbm-btn" data-action="prefill-test">
                            Use Test Message
                        </button>
                    </div>
                </div>
            </div>
        `;
    }

    // ── LOGS PANEL ────────────────────────────────────────────────────

    renderLogsPanel() {
        const { logs, logFilter } = this.state;
        const platforms = ['all', 'telegram', 'discord', 'slack'];

        return `
            <div class="cbm-logs-panel">
                <div class="cbm-panel-header">
                    <div class="cbm-panel-title">
                        <span class="cbm-panel-icon">▤</span>
                        Bot Logs
                    </div>
                    <div class="cbm-log-filters">
                        ${platforms.map(p => `
                            <button
                                class="cbm-log-filter-btn ${(logFilter || 'all') === p ? 'active' : ''}"
                                data-action="filter-logs"
                                data-filter="${p === 'all' ? '' : p}"
                            >${p}</button>
                        `).join('')}
                        <button class="cbm-btn cbm-btn-sm" data-action="reload-logs">↻</button>
                    </div>
                </div>

                <div class="cbm-log-stream">
                    ${logs.length === 0 ? `
                        <div class="cbm-empty-logs">
                            <div class="cbm-empty-icon">▤</div>
                            No log entries found.
                            <button class="cbm-link" data-action="reload-logs">Load logs</button>
                        </div>
                    ` : logs.map(l => this.renderLogEntry(l)).join('')}
                </div>
            </div>
        `;
    }

    renderLogEntry(log) {
        const levelClass = {
            'ERROR':   'cbm-log-error',
            'WARNING': 'cbm-log-warn',
            'SUCCESS': 'cbm-log-success',
            'DEBUG':   'cbm-log-debug',
            'INFO':    'cbm-log-info'
        }[log.level] || 'cbm-log-info';

        const platformIcon = { telegram: '✈', discord: '◈', slack: '#', general: '·' }[log.platform] || '·';

        return `
            <div class="cbm-log-entry ${levelClass}">
                <span class="cbm-log-platform">${platformIcon}</span>
                <span class="cbm-log-time">${this.escapeHtml(log.timestamp || '—')}</span>
                <span class="cbm-log-level">${this.escapeHtml(log.level || '')}</span>
                <span class="cbm-log-msg">${this.escapeHtml(log.raw || '')}</span>
            </div>
        `;
    }

    // ── TOASTS ────────────────────────────────────────────────────────

    renderToasts() {
        const { toasts } = this.state;
        if (!toasts.length) return '<div class="cbm-toasts"></div>';
        return `
            <div class="cbm-toasts">
                ${toasts.map(t => `
                    <div class="cbm-toast cbm-toast-${t.type}">
                        <span>${this.escapeHtml(t.message)}</span>
                        <button class="cbm-toast-close" data-action="dismiss-toast" data-toast-id="${t.id}">✕</button>
                    </div>
                `).join('')}
            </div>
        `;
    }

    // ================================================================
    // EVENT DELEGATION
    // ================================================================

    attachEventListeners() {
        if (!this.container) return;
        if (this._listenersAttached) return;  // ← prevent stacking on every render
        this._listenersAttached = true;

        // Single delegated click listener on the outer container (never replaced by innerHTML)
        this.container.addEventListener('click', (e) => {
            const target = e.target.closest('[data-action]');
            if (!target) return;

            const action   = target.dataset.action;
            const platform = target.dataset.platform;
            const tab      = target.dataset.tab;

            switch (action) {
                case 'set-tab':
                    this.setState({ activeTab: tab });
                    if (tab === 'logs')     this.loadLogs(this.state.logFilter);
                    if (tab === 'telegram') this.loadTelegramUsers();
                    break;

                case 'refresh':
                    this.loadStatuses();
                    this.loadConfig();
                    this.loadStats();
                    break;

                case 'bot-action':
                    this.performAction(platform, target.dataset.botAction);
                    break;

                case 'start-all':
                    ['telegram', 'discord', 'slack'].forEach(p => {
                        const s = this.getStatusForPlatform(p);
                        if (s.enabled && !s.running) this.performAction(p, 'start');
                    });
                    break;

                case 'stop-all':
                    this.state.statuses.filter(s => s.running).forEach(s => {
                        this.performAction(s.platform, 'stop');
                    });
                    break;

                case 'start-edit':
                    this.setState({ editingPlatform: platform });
                    break;

                case 'cancel-edit': {
                    const buf = { ...this.state.editBuffer };
                    delete buf[platform];
                    this.setState({ editingPlatform: null, editBuffer: buf });
                    break;
                }

                case 'save-config':
                    this.saveConfig(platform);
                    break;

                case 'toggle-token': {
                    const show = { ...this.state.showTokens };
                    show[platform] = !show[platform];
                    this.setState({ showTokens: show });
                    break;
                }

                case 'load-tg-users':
                    this.loadTelegramUsers();
                    break;

                case 'notify-user':
                    this.setState({ activeTab: 'notify', notifyUserId: target.dataset.userId || '' });
                    break;

                case 'send-notification':
                    this.sendTestNotification();
                    break;

                case 'prefill-test':
                    this.setState({ notifyMessage: '🔔 Test notification from Vera Bot Manager\n\n<b>System:</b> All systems operational.' });
                    break;

                case 'filter-logs':
                    this.loadLogs(target.dataset.filter || null);
                    break;

                case 'reload-logs':
                    this.loadLogs(this.state.logFilter);
                    break;

                case 'dismiss-toast': {
                    const id = parseInt(target.dataset.toastId, 10);
                    this.setState({ toasts: this.state.toasts.filter(t => t.id !== id) });
                    break;
                }

                case 'toggle-enabled': {
                    // Checkbox in card — apply immediately without requiring edit mode
                    this._fetch('/config/update', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ platform, config: { enabled: target.checked } })
                    }).then(() => {
                        this.showToast(`${platform} ${target.checked ? 'enabled' : 'disabled'}`, 'success');
                        this.loadConfig();
                    }).catch(err => {
                        this.showToast(`Failed to update: ${err.message}`, 'error');
                    });
                    break;
                }
            }
        });

        // Input change events for config fields
        this.container.addEventListener('change', (e) => {
            const target = e.target.closest('[data-field]');
            if (!target) return;

            const field    = target.dataset.field;
            const platform = target.dataset.platform;
            if (!field || !platform) return;

            let value = target.type === 'checkbox' ? target.checked : target.value;

            // Parse array fields
            if (['owner_ids', 'allowed_users', 'allowed_channels'].includes(field)) {
                value = value.split(',')
                    .map(v => v.trim())
                    .filter(Boolean)
                    .map(v => (field !== 'allowed_channels' && !isNaN(v)) ? parseInt(v, 10) : v);
            }

            const buf = { ...this.state.editBuffer };
            buf[platform] = { ...(buf[platform] || {}), [field]: value };
            this.setState({ editBuffer: buf });
        });

        // Live input for notify panel — direct mutation to avoid re-render loop on every keystroke
        this.container.addEventListener('input', (e) => {
            const target = e.target;
            if (target.dataset.action === 'notify-msg-input') {
                this.state.notifyMessage = target.value;
            }
            if (target.dataset.action === 'notify-uid-input') {
                this.state.notifyUserId = target.value;
            }
        });
    }

    // ================================================================
    // UTILS
    // ================================================================

    escapeHtml(text) {
        const d = document.createElement('div');
        d.textContent = String(text ?? '');
        return d.innerHTML;
    }

    // ================================================================
    // STYLES (injected once into <head>)
    // ================================================================

    static injectStyles() {
        if (document.getElementById('cbm-styles')) return;
        const style = document.createElement('style');
        style.id = 'cbm-styles';
        style.textContent = ChatbotManager.STYLES;
        document.head.appendChild(style);
    }

    static get STYLES() {
        return `
        /* ── ChatbotManager — scoped to .cbm-root ── */
        .cbm-root {
            --cbm-bg:          #0d0f14;
            --cbm-surface:     #141720;
            --cbm-surface2:    #1c2030;
            --cbm-border:      #252a38;
            --cbm-text:        #e4e9f7;
            --cbm-text-muted:  #636e8f;
            --cbm-text-dim:    #414d6b;
            --cbm-blue:        #4a9eff;
            --cbm-blue-dim:    #1e3a5f;
            --cbm-purple:      #9b6dff;
            --cbm-purple-dim:  #2d1e52;
            --cbm-green:       #2ee89a;
            --cbm-green-dim:   #0d2e1f;
            --cbm-red:         #ff4a6e;
            --cbm-red-dim:     #2e1020;
            --cbm-orange:      #ff9f42;
            --cbm-orange-dim:  #2e1e0a;
            --cbm-font:        'JetBrains Mono', 'Fira Code', 'Courier New', monospace;
            --cbm-font-ui:     system-ui, 'Segoe UI', sans-serif;
            font-family: var(--cbm-font-ui);
            background: var(--cbm-bg);
            color: var(--cbm-text);
            border-radius: 16px;
            overflow: hidden;
            border: 1px solid var(--cbm-border);
            min-height: 500px;
            display: flex;
            flex-direction: column;
            position: relative;
        }

        /* Header */
        .cbm-header {
            display: flex; align-items: center; justify-content: space-between;
            padding: 18px 24px 14px;
            border-bottom: 1px solid var(--cbm-border);
            background: linear-gradient(135deg, #0d0f14 0%, #141720 100%);
            flex-shrink: 0;
        }
        .cbm-title-block { display: flex; align-items: center; gap: 14px; }
        .cbm-icon {
            width: 40px; height: 40px;
            background: linear-gradient(135deg, var(--cbm-blue), var(--cbm-purple));
            border-radius: 10px;
            display: flex; align-items: center; justify-content: center;
            font-size: 18px;
            box-shadow: 0 0 18px rgba(74,158,255,0.25);
            flex-shrink: 0;
        }
        .cbm-title  { margin: 0; font-size: 18px; font-weight: 700; letter-spacing: -0.4px; }
        .cbm-subtitle { margin: 2px 0 0; font-size: 11px; color: var(--cbm-text-muted); font-family: var(--cbm-font); }
        .cbm-header-stats { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
        .cbm-stat-pill {
            padding: 4px 10px; border-radius: 100px;
            background: var(--cbm-surface2); border: 1px solid var(--cbm-border);
            font-size: 12px; font-family: var(--cbm-font); color: var(--cbm-text-muted);
            display: flex; align-items: center; gap: 5px;
        }
        .cbm-stat-pill.active { background: var(--cbm-green-dim); border-color: var(--cbm-green); color: var(--cbm-green); }
        .cbm-pill-error { background: var(--cbm-red-dim) !important; border-color: var(--cbm-red) !important; color: var(--cbm-red) !important; cursor: help; }
        .cbm-stat-dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
        .cbm-refresh-btn {
            width: 30px; height: 30px; border-radius: 7px;
            background: var(--cbm-surface2); border: 1px solid var(--cbm-border);
            color: var(--cbm-text-muted); cursor: pointer; font-size: 15px;
            display: flex; align-items: center; justify-content: center; transition: all 0.15s;
        }
        .cbm-refresh-btn:hover { background: var(--cbm-border); color: var(--cbm-text); }
        .cbm-spin { display: inline-block; animation: cbm-spin 0.6s linear infinite; }
        @keyframes cbm-spin { to { transform: rotate(360deg); } }

        /* Tabs */
        .cbm-tabs {
            display: flex; gap: 2px; padding: 10px 16px 0;
            background: var(--cbm-surface); border-bottom: 1px solid var(--cbm-border);
            overflow-x: auto; flex-shrink: 0;
        }
        .cbm-tabs::-webkit-scrollbar { height: 3px; }
        .cbm-tabs::-webkit-scrollbar-thumb { background: var(--cbm-border); border-radius: 2px; }
        .cbm-tab {
            padding: 7px 14px; border-radius: 7px 7px 0 0;
            background: transparent; border: none; border-bottom: 2px solid transparent;
            color: var(--cbm-text-muted); cursor: pointer;
            font-size: 12px; font-weight: 500; white-space: nowrap; transition: all 0.15s;
        }
        .cbm-tab:hover { color: var(--cbm-text); background: var(--cbm-surface2); }
        .cbm-tab.active { color: var(--cbm-blue); border-bottom-color: var(--cbm-blue); }

        /* Body */
        .cbm-body { flex: 1; overflow-y: auto; background: var(--cbm-bg); }
        .cbm-body::-webkit-scrollbar { width: 6px; }
        .cbm-body::-webkit-scrollbar-thumb { background: var(--cbm-border); border-radius: 3px; }

        /* Error state */
        .cbm-error-state {
            display: flex; flex-direction: column; align-items: center; justify-content: center;
            gap: 12px; padding: 60px 20px; text-align: center;
        }
        .cbm-error-icon { font-size: 36px; color: var(--cbm-orange); }
        .cbm-error-state h3 { margin: 0; color: var(--cbm-text); }
        .cbm-error-msg { color: var(--cbm-red); font-family: var(--cbm-font); font-size: 13px; margin: 0; }
        .cbm-error-url { color: var(--cbm-text-muted); font-size: 12px; margin: 0; }
        .cbm-error-url code { color: var(--cbm-text); font-family: var(--cbm-font); }

        /* Overview */
        .cbm-overview { padding: 18px; display: flex; flex-direction: column; gap: 16px; }
        .cbm-platform-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px,1fr)); gap: 14px; }

        .cbm-platform-card {
            background: var(--cbm-surface); border: 1px solid var(--cbm-border);
            border-radius: 12px; padding: 14px;
            display: flex; flex-direction: column; gap: 10px;
            transition: border-color 0.2s, transform 0.15s;
        }
        .cbm-platform-card:hover { transform: translateY(-1px); }
        .cbm-card-blue   { border-top: 2px solid var(--cbm-blue); }
        .cbm-card-purple { border-top: 2px solid var(--cbm-purple); }
        .cbm-card-green  { border-top: 2px solid var(--cbm-green); }

        .cbm-card-top { display: flex; align-items: center; gap: 10px; }
        .cbm-card-platform-icon { font-size: 20px; width: 32px; text-align: center; flex-shrink: 0; }
        .cbm-card-info { flex: 1; min-width: 0; }
        .cbm-card-name { font-weight: 600; font-size: 14px; text-transform: capitalize; }
        .cbm-card-username { font-size: 11px; color: var(--cbm-text-muted); font-family: var(--cbm-font); }
        .cbm-card-metrics { display: flex; gap: 10px; font-size: 11px; color: var(--cbm-text-muted); font-family: var(--cbm-font); }
        .cbm-card-actions { display: flex; gap: 5px; flex-wrap: wrap; }

        /* Status badges */
        .cbm-status-badge {
            display: inline-flex; align-items: center; gap: 5px;
            padding: 2px 7px; border-radius: 100px; font-size: 11px; font-weight: 600;
        }
        .cbm-status-badge.connected { background: var(--cbm-green-dim); color: var(--cbm-green); }
        .cbm-status-badge.running   { background: var(--cbm-orange-dim); color: var(--cbm-orange); }
        .cbm-status-badge.offline   { background: var(--cbm-surface2); color: var(--cbm-text-muted); }
        .cbm-status-dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; animation: cbm-pulse 2s infinite; }
        @keyframes cbm-pulse { 0%,100%{opacity:1} 50%{opacity:0.35} }

        /* Buttons */
        .cbm-btn {
            padding: 5px 11px; border-radius: 6px; border: 1px solid var(--cbm-border);
            background: var(--cbm-surface2); color: var(--cbm-text); cursor: pointer;
            font-size: 12px; font-weight: 500; transition: all 0.15s; white-space: nowrap;
        }
        .cbm-btn:hover:not(:disabled) { background: var(--cbm-border); }
        .cbm-btn:disabled { opacity: 0.4; cursor: not-allowed; }
        .cbm-btn-start   { background: var(--cbm-green-dim);  border-color: var(--cbm-green);  color: var(--cbm-green); }
        .cbm-btn-start:hover:not(:disabled)   { background: var(--cbm-green);  color: #000; }
        .cbm-btn-stop    { background: var(--cbm-red-dim);    border-color: var(--cbm-red);    color: var(--cbm-red); }
        .cbm-btn-stop:hover:not(:disabled)    { background: var(--cbm-red);    color: #fff; }
        .cbm-btn-restart { background: var(--cbm-orange-dim); border-color: var(--cbm-orange); color: var(--cbm-orange); }
        .cbm-btn-restart:hover:not(:disabled) { background: var(--cbm-orange); color: #000; }
        .cbm-btn-test    { background: var(--cbm-blue-dim);   border-color: var(--cbm-blue);   color: var(--cbm-blue); }
        .cbm-btn-test:hover:not(:disabled)    { background: var(--cbm-blue);   color: #fff; }
        .cbm-btn-save    { background: var(--cbm-blue-dim);   border-color: var(--cbm-blue);   color: var(--cbm-blue); padding: 7px 16px; }
        .cbm-btn-save:hover:not(:disabled)    { background: var(--cbm-blue);   color: #fff; }
        .cbm-btn-send    { background: var(--cbm-blue); border-color: var(--cbm-blue); color: #fff; padding: 9px 18px; }
        .cbm-btn-send:hover:not(:disabled)    { opacity: 0.85; }
        .cbm-btn-config  { padding: 5px 9px; }
        .cbm-btn-sm      { padding: 3px 7px; font-size: 11px; }
        .cbm-btn-eye     { padding: 5px 9px; border-radius: 0 6px 6px 0; border-left: none; }
        .cbm-link { background: none; border: none; color: var(--cbm-blue); cursor: pointer; text-decoration: underline; font-size: 13px; }

        /* Toggle switch */
        .cbm-toggle { position: relative; display: inline-flex; align-items: center; cursor: pointer; }
        .cbm-toggle input { position: absolute; opacity: 0; width: 0; height: 0; }
        .cbm-toggle-track {
            width: 36px; height: 19px; border-radius: 10px;
            background: var(--cbm-surface2); border: 1px solid var(--cbm-border);
            transition: all 0.2s; position: relative;
        }
        .cbm-toggle-track::after {
            content: ''; position: absolute; top: 2px; left: 2px;
            width: 13px; height: 13px; border-radius: 50%;
            background: var(--cbm-text-muted); transition: all 0.2s;
        }
        .cbm-toggle input:checked + .cbm-toggle-track { background: var(--cbm-blue-dim); border-color: var(--cbm-blue); }
        .cbm-toggle input:checked + .cbm-toggle-track::after { background: var(--cbm-blue); left: 19px; }

        /* Quick actions */
        .cbm-quick-actions { background: var(--cbm-surface); border: 1px solid var(--cbm-border); border-radius: 10px; padding: 14px; }
        .cbm-quick-label { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: var(--cbm-text-muted); margin-bottom: 8px; }
        .cbm-quick-btn-row { display: flex; gap: 7px; flex-wrap: wrap; }

        /* Platform panel */
        .cbm-platform-panel { padding: 18px; display: flex; flex-direction: column; gap: 0; }
        .cbm-panel-header {
            display: flex; align-items: center; justify-content: space-between;
            padding-bottom: 14px; border-bottom: 1px solid var(--cbm-border); margin-bottom: 18px;
        }
        .cbm-panel-title { display: flex; align-items: center; gap: 8px; font-size: 16px; font-weight: 600; }
        .cbm-panel-icon { font-size: 18px; }
        .cbm-panel-status { display: flex; align-items: center; gap: 8px; }
        .cbm-username-tag { font-size: 11px; font-family: var(--cbm-font); color: var(--cbm-text-muted); }
        .cbm-panel-body { flex: 1; }
        .cbm-panel-footer {
            display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
            padding-top: 18px; margin-top: 18px; border-top: 1px solid var(--cbm-border);
        }
        .cbm-panel-bot-actions { display: flex; gap: 6px; margin-left: auto; flex-wrap: wrap; }

        /* Fields */
        .cbm-field-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
        .cbm-field { display: flex; flex-direction: column; gap: 5px; }
        .cbm-field-full { grid-column: 1 / -1; }
        .cbm-label { font-size: 11px; font-weight: 600; color: var(--cbm-text-muted); text-transform: uppercase; letter-spacing: 0.4px; }
        .cbm-hint  { font-size: 11px; color: var(--cbm-text-dim); font-family: var(--cbm-font); }
        .cbm-input, .cbm-textarea {
            background: var(--cbm-surface2); border: 1px solid var(--cbm-border);
            border-radius: 7px; padding: 8px 11px; color: var(--cbm-text);
            font-family: var(--cbm-font); font-size: 13px; width: 100%; box-sizing: border-box;
            transition: border-color 0.15s;
        }
        .cbm-input:focus, .cbm-textarea:focus { outline: none; border-color: var(--cbm-blue); }
        .cbm-input:disabled { color: var(--cbm-text-muted); cursor: not-allowed; opacity: 0.7; }
        .cbm-input-token { border-radius: 7px 0 0 7px; }
        .cbm-input-small { max-width: 130px; }
        .cbm-textarea { resize: vertical; min-height: 90px; }
        .cbm-token-row { display: flex; }
        .cbm-token-row .cbm-input { flex: 1; }

        /* Users table */
        .cbm-users-section { margin-top: 22px; padding-top: 18px; border-top: 1px solid var(--cbm-border); }
        .cbm-section-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; font-size: 13px; font-weight: 600; }
        .cbm-users-table { display: flex; flex-direction: column; gap: 1px; border-radius: 9px; overflow: hidden; border: 1px solid var(--cbm-border); }
        .cbm-users-head { display: grid; grid-template-columns: 1fr 1fr 90px 80px; gap: 8px; padding: 7px 11px; background: var(--cbm-surface2); font-size: 10px; font-weight: 700; text-transform: uppercase; color: var(--cbm-text-muted); }
        .cbm-users-row  { display: grid; grid-template-columns: 1fr 1fr 90px 80px; gap: 8px; padding: 9px 11px; background: var(--cbm-surface); font-size: 12px; align-items: center; }
        .cbm-users-row:hover { background: var(--cbm-surface2); }
        .cbm-mono { font-family: var(--cbm-font); }
        .cbm-empty-row { padding: 18px; text-align: center; color: var(--cbm-text-muted); font-size: 13px; }
        .cbm-role-badge { padding: 2px 7px; border-radius: 100px; font-size: 10px; font-weight: 700; text-transform: uppercase; }
        .cbm-role-owner { background: var(--cbm-purple-dim); color: var(--cbm-purple); }
        .cbm-role-admin { background: var(--cbm-blue-dim);   color: var(--cbm-blue);   }
        .cbm-role-user  { background: var(--cbm-surface2);   color: var(--cbm-text-muted); }

        /* Notify panel */
        .cbm-notify-panel { padding: 18px; }
        .cbm-notify-body { display: flex; flex-direction: column; gap: 16px; max-width: 580px; }
        .cbm-notify-actions { display: flex; gap: 8px; }
        .cbm-segmented { display: flex; gap: 4px; }
        .cbm-seg { padding: 5px 13px; border-radius: 7px; border: 1px solid var(--cbm-blue); background: var(--cbm-blue-dim); color: var(--cbm-blue); cursor: pointer; font-size: 13px; }

        /* Logs */
        .cbm-logs-panel { display: flex; flex-direction: column; }
        .cbm-logs-panel .cbm-panel-header { padding: 14px 18px 10px; border-bottom: 1px solid var(--cbm-border); margin-bottom: 0; flex-shrink: 0; }
        .cbm-log-filters { display: flex; gap: 4px; align-items: center; flex-wrap: wrap; }
        .cbm-log-filter-btn { padding: 3px 9px; border-radius: 100px; border: 1px solid var(--cbm-border); background: var(--cbm-surface2); color: var(--cbm-text-muted); cursor: pointer; font-size: 11px; font-family: var(--cbm-font); text-transform: uppercase; }
        .cbm-log-filter-btn.active { border-color: var(--cbm-blue); color: var(--cbm-blue); background: var(--cbm-blue-dim); }
        .cbm-log-stream {
            flex: 1; overflow-y: auto; font-family: var(--cbm-font); font-size: 12px;
            display: flex; flex-direction: column; gap: 1px; padding: 10px 16px;
            max-height: 500px;
        }
        .cbm-log-stream::-webkit-scrollbar { width: 5px; }
        .cbm-log-stream::-webkit-scrollbar-thumb { background: var(--cbm-border); border-radius: 3px; }
        .cbm-log-entry { display: grid; grid-template-columns: 18px 155px 65px 1fr; gap: 8px; padding: 4px 7px; border-radius: 4px; align-items: start; }
        .cbm-log-entry:hover { background: var(--cbm-surface); }
        .cbm-log-error   { background: rgba(255,74,110,0.04); }
        .cbm-log-error   .cbm-log-level { color: var(--cbm-red); }
        .cbm-log-warn    .cbm-log-level { color: var(--cbm-orange); }
        .cbm-log-success .cbm-log-level { color: var(--cbm-green); }
        .cbm-log-debug   .cbm-log-level { color: var(--cbm-text-dim); }
        .cbm-log-info    .cbm-log-level { color: var(--cbm-text-muted); }
        .cbm-log-time     { color: var(--cbm-text-dim); }
        .cbm-log-platform { text-align: center; color: var(--cbm-text-muted); }
        .cbm-log-msg      { word-break: break-all; color: var(--cbm-text); }
        .cbm-empty-logs { display: flex; flex-direction: column; align-items: center; gap: 10px; padding: 50px 20px; color: var(--cbm-text-muted); }
        .cbm-empty-icon { font-size: 28px; opacity: 0.25; }

        /* Loading */
        .cbm-loading-state { display: flex; align-items: center; justify-content: center; gap: 12px; padding: 60px; color: var(--cbm-text-muted); }
        .cbm-spinner { width: 18px; height: 18px; border-radius: 50%; border: 2px solid var(--cbm-border); border-top-color: var(--cbm-blue); animation: cbm-spin 0.7s linear infinite; }

        /* Toasts */
        .cbm-toasts { position: absolute; bottom: 14px; right: 14px; display: flex; flex-direction: column; gap: 7px; z-index: 100; max-width: 300px; pointer-events: none; }
        .cbm-toast { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 9px 13px; border-radius: 9px; font-size: 12px; animation: cbm-toast-in 0.2s ease; pointer-events: all; }
        @keyframes cbm-toast-in { from { opacity: 0; transform: translateY(6px); } }
        .cbm-toast-success { background: var(--cbm-green-dim);  border: 1px solid var(--cbm-green);  color: var(--cbm-green); }
        .cbm-toast-error   { background: var(--cbm-red-dim);    border: 1px solid var(--cbm-red);    color: var(--cbm-red); }
        .cbm-toast-warning { background: var(--cbm-orange-dim); border: 1px solid var(--cbm-orange); color: var(--cbm-orange); }
        .cbm-toast-info    { background: var(--cbm-blue-dim);   border: 1px solid var(--cbm-blue);   color: var(--cbm-blue); }
        .cbm-toast-close { background: none; border: none; color: currentColor; cursor: pointer; font-size: 13px; padding: 0; line-height: 1; }
        `;
    }
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = ChatbotManager;
}
