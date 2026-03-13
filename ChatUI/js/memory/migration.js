(() => {
    // ============================================================
    // Chroma Migration Management Panel
    // Adds a "Migration" section to the memory tab for moving
    // data between local file store and remote Chroma server.
    // Uses the same CSS variable theme system as the memory UI.
    // ============================================================

    const style = document.createElement('style');
    style.textContent = `
        /* ── Migration Panel Shell ── */
        .migration-panel {
            border: 1px solid var(--border);
            border-radius: 10px;
            overflow: hidden;
            margin-top: 16px;
        }

        .migration-panel-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 14px 18px;
            background: var(--panel-bg);
            cursor: pointer;
            user-select: none;
            gap: 12px;
        }

        .migration-panel-header:hover {
            background: var(--hover);
        }

        .migration-panel-title {
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 14px;
            font-weight: 600;
            color: var(--text);
            letter-spacing: 0.2px;
        }

        .migration-panel-title .icon {
            font-size: 17px;
        }

        .migration-panel-chevron {
            color: var(--text-dim);
            font-size: 12px;
            transition: transform 0.25s ease;
        }

        .migration-panel-chevron.open {
            transform: rotate(180deg);
        }

        .migration-panel-body {
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.35s ease;
        }

        .migration-panel-body.open {
            max-height: 1400px;
        }

        .migration-panel-inner {
            padding: 18px;
            display: flex;
            flex-direction: column;
            gap: 18px;
            border-top: 1px solid var(--border);
        }

        /* ── Two-column endpoint layout ── */
        .migration-endpoints {
            display: grid;
            grid-template-columns: 1fr auto 1fr;
            gap: 12px;
            align-items: start;
        }

        .endpoint-card {
            background: var(--panel-bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 14px 16px;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }

        .endpoint-card.active-source {
            border-color: var(--accent);
        }

        .endpoint-card-title {
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            color: var(--text-muted);
            margin-bottom: 2px;
        }

        .endpoint-type-toggle {
            display: flex;
            gap: 4px;
            background: var(--bg);
            padding: 3px;
            border-radius: 6px;
        }

        .endpoint-type-btn {
            flex: 1;
            padding: 6px 0;
            border: none;
            background: transparent;
            color: var(--text-muted);
            border-radius: 4px;
            font-size: 12px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.15s;
        }

        .endpoint-type-btn:hover {
            color: var(--text);
        }

        .endpoint-type-btn.active {
            background: var(--accent);
            color: #fff;
        }

        .endpoint-field {
            display: flex;
            flex-direction: column;
            gap: 5px;
        }

        .endpoint-field label {
            font-size: 11px;
            color: var(--text-dim);
            font-weight: 500;
        }

        .endpoint-field input,
        .endpoint-field select {
            padding: 7px 10px;
            background: var(--bg);
            border: 1px solid var(--border);
            border-radius: 5px;
            color: var(--text);
            font-size: 13px;
            transition: border-color 0.15s;
            width: 100%;
            box-sizing: border-box;
        }

        .endpoint-field input:focus,
        .endpoint-field select:focus {
            outline: none;
            border-color: var(--accent);
        }

        .endpoint-field input::placeholder {
            color: var(--text-dim);
            opacity: 0.6;
        }

        .endpoint-status {
            display: flex;
            align-items: center;
            gap: 7px;
            font-size: 12px;
            padding: 6px 10px;
            border-radius: 5px;
            background: var(--bg);
            min-height: 32px;
        }

        .endpoint-status .dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            flex-shrink: 0;
            background: var(--text-dim);
        }

        .endpoint-status.ok .dot    { background: var(--success, #22c55e); }
        .endpoint-status.err .dot   { background: var(--danger,  #ef4444); }
        .endpoint-status.checking .dot {
            background: var(--warning, #f59e0b);
            animation: pulse-dot 0.9s ease-in-out infinite;
        }

        @keyframes pulse-dot {
            0%, 100% { opacity: 1; }
            50%       { opacity: 0.3; }
        }

        .endpoint-status-text {
            color: var(--text-muted);
            font-size: 11px;
            flex: 1;
        }

        .btn-check {
            padding: 5px 12px;
            background: var(--panel-bg);
            border: 1px solid var(--border);
            color: var(--text-muted);
            border-radius: 5px;
            cursor: pointer;
            font-size: 11px;
            font-weight: 500;
            transition: all 0.15s;
        }

        .btn-check:hover {
            border-color: var(--accent);
            color: var(--text);
        }

        /* Direction arrow */
        .migration-direction {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 6px;
            padding-top: 52px;
        }

        .direction-arrow {
            font-size: 22px;
            color: var(--accent);
            line-height: 1;
        }

        .btn-swap {
            padding: 5px 12px;
            background: var(--panel-bg);
            border: 1px solid var(--border);
            color: var(--text-muted);
            border-radius: 5px;
            cursor: pointer;
            font-size: 11px;
            font-weight: 600;
            transition: all 0.15s;
            white-space: nowrap;
        }

        .btn-swap:hover {
            border-color: var(--accent);
            color: var(--text);
        }

        /* ── Migration Options ── */
        .migration-options {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 10px;
            background: var(--panel-bg);
            border-radius: 8px;
            padding: 14px 16px;
        }

        .migration-option {
            display: flex;
            flex-direction: column;
            gap: 5px;
        }

        .migration-option label {
            font-size: 11px;
            color: var(--text-dim);
            font-weight: 500;
        }

        .migration-option input[type="number"],
        .migration-option select {
            padding: 7px 10px;
            background: var(--bg);
            border: 1px solid var(--border);
            border-radius: 5px;
            color: var(--text);
            font-size: 13px;
            width: 100%;
            box-sizing: border-box;
        }

        .migration-option input[type="number"]:focus,
        .migration-option select:focus {
            outline: none;
            border-color: var(--accent);
        }

        .migration-checkbox-row {
            display: flex;
            align-items: center;
            gap: 8px;
            padding-top: 6px;
            cursor: pointer;
        }

        .migration-checkbox-row input[type="checkbox"] {
            width: 14px;
            height: 14px;
            accent-color: var(--accent);
            cursor: pointer;
        }

        .migration-checkbox-row span {
            font-size: 12px;
            color: var(--text-muted);
        }

        /* ── Collection Picker ── */
        .collection-picker {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }

        .collection-chip {
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 5px 12px;
            background: var(--panel-bg);
            border: 1px solid var(--border);
            border-radius: 20px;
            font-size: 12px;
            color: var(--text-muted);
            cursor: pointer;
            transition: all 0.15s;
            user-select: none;
        }

        .collection-chip:hover {
            border-color: var(--accent);
            color: var(--text);
        }

        .collection-chip.selected {
            background: var(--accent);
            border-color: var(--accent);
            color: #fff;
        }

        .collection-chip .chip-check {
            font-size: 10px;
        }

        /* ── Action Row ── */
        .migration-actions {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            align-items: center;
        }

        .btn-migrate {
            padding: 10px 24px;
            background: var(--accent);
            border: none;
            color: #fff;
            border-radius: 7px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            transition: opacity 0.15s;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .btn-migrate:hover:not(:disabled) {
            opacity: 0.85;
        }

        .btn-migrate:disabled {
            opacity: 0.45;
            cursor: not-allowed;
        }

        .btn-dry-run {
            padding: 10px 20px;
            background: var(--panel-bg);
            border: 1px solid var(--border);
            color: var(--text);
            border-radius: 7px;
            font-size: 13px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.15s;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .btn-dry-run:hover:not(:disabled) {
            border-color: var(--accent);
        }

        .btn-dry-run:disabled {
            opacity: 0.45;
            cursor: not-allowed;
        }

        /* ── Progress Area ── */
        .migration-progress {
            display: none;
            flex-direction: column;
            gap: 10px;
        }

        .migration-progress.visible {
            display: flex;
        }

        .progress-bar-wrap {
            background: var(--panel-bg);
            border-radius: 6px;
            height: 8px;
            overflow: hidden;
        }

        .progress-bar-fill {
            height: 100%;
            background: var(--accent);
            border-radius: 6px;
            transition: width 0.3s ease;
            width: 0%;
        }

        .progress-bar-fill.indeterminate {
            width: 35%;
            animation: slide-indeterminate 1.4s ease-in-out infinite;
        }

        @keyframes slide-indeterminate {
            0%   { transform: translateX(-150%); }
            100% { transform: translateX(400%); }
        }

        .progress-stats {
            display: flex;
            gap: 16px;
            flex-wrap: wrap;
        }

        .progress-stat {
            display: flex;
            flex-direction: column;
            gap: 2px;
        }

        .progress-stat-label {
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 0.6px;
            color: var(--text-dim);
        }

        .progress-stat-value {
            font-size: 18px;
            font-weight: 700;
            color: var(--text);
            font-variant-numeric: tabular-nums;
        }

        .progress-stat-value.green { color: var(--success, #22c55e); }
        .progress-stat-value.yellow { color: var(--warning, #f59e0b); }
        .progress-stat-value.red { color: var(--danger, #ef4444); }

        /* ── Log ── */
        .migration-log {
            background: var(--bg);
            border: 1px solid var(--border);
            border-radius: 7px;
            padding: 12px 14px;
            max-height: 180px;
            overflow-y: auto;
            font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
            font-size: 11.5px;
            line-height: 1.65;
        }

        .log-line {
            display: flex;
            gap: 10px;
            padding: 1px 0;
        }

        .log-time {
            color: var(--text-dim);
            flex-shrink: 0;
            font-size: 10.5px;
            margin-top: 1px;
        }

        .log-line.info  .log-msg { color: var(--text-muted); }
        .log-line.ok    .log-msg { color: var(--success, #22c55e); }
        .log-line.warn  .log-msg { color: var(--warning, #f59e0b); }
        .log-line.error .log-msg { color: var(--danger, #ef4444); }
        .log-line.dim   .log-msg { color: var(--text-dim); }

        /* ── Result Banner ── */
        .migration-result-banner {
            display: none;
            padding: 12px 16px;
            border-radius: 7px;
            font-size: 13px;
            font-weight: 500;
            gap: 10px;
            align-items: center;
        }

        .migration-result-banner.visible {
            display: flex;
        }

        .migration-result-banner.success {
            background: color-mix(in srgb, var(--success, #22c55e) 12%, transparent);
            border: 1px solid color-mix(in srgb, var(--success, #22c55e) 35%, transparent);
            color: var(--success, #22c55e);
        }

        .migration-result-banner.partial {
            background: color-mix(in srgb, var(--warning, #f59e0b) 12%, transparent);
            border: 1px solid color-mix(in srgb, var(--warning, #f59e0b) 35%, transparent);
            color: var(--warning, #f59e0b);
        }

        .migration-result-banner.failed {
            background: color-mix(in srgb, var(--danger, #ef4444) 12%, transparent);
            border: 1px solid color-mix(in srgb, var(--danger, #ef4444) 35%, transparent);
            color: var(--danger, #ef4444);
        }
    `;
    document.head.appendChild(style);


    // ============================================================
    // State
    // ============================================================

    VeraChat.prototype.migrationState = {
        open: false,
        running: false,

        // Endpoint configs
        local: {
            type: 'local',
            persist_dir: './Memory/chroma_store',
        },
        remote: {
            type: 'remote',
            host: '',
            port: 8000,
            ssl: false,
            auth_token: '',
            tenant: 'default_tenant',
            database: 'default_database',
        },

        // Which is source / dest
        direction: 'local_to_remote',   // 'local_to_remote' | 'remote_to_local'

        // Options
        collections: ['vera_memory', 'long_term_docs'],
        selectedCollections: ['vera_memory', 'long_term_docs'],
        batchSize: 200,
        skipExisting: true,
        embeddingModel: 'nomic-embed-text:latest',

        // Connectivity
        localStatus: 'unknown',     // 'unknown' | 'checking' | 'ok' | 'err'
        remoteStatus: 'unknown',

        // Live progress (fed by SSE or polling)
        progress: { migrated: 0, skipped: 0, errors: 0, total: 0, duration_s: 0 },
        log: [],
        lastResult: null,
    };


    // ============================================================
    // Render
    // ============================================================

    VeraChat.prototype.renderMigrationPanel = function() {
        const s = this.migrationState;
        const src = s.direction === 'local_to_remote' ? 'local' : 'remote';
        const dst = s.direction === 'local_to_remote' ? 'remote' : 'local';

        const endpointCard = (side) => {
            const cfg = s[side];
            const isLocal = side === 'local';
            const status  = isLocal ? s.localStatus : s.remoteStatus;

            const statusHtml = {
                unknown:  `<span class="endpoint-status-text">Not checked</span>`,
                checking: `<span class="endpoint-status-text">Checking…</span>`,
                ok:       `<span class="endpoint-status-text">Reachable</span>`,
                err:      `<span class="endpoint-status-text">Unreachable</span>`,
            }[status] || '';

            return `
                <div class="endpoint-card ${s.direction === side + '_to_' + (side === 'local' ? 'remote' : 'local') ? 'active-source' : ''}"
                     id="migration-endpoint-${side}">
                    <div class="endpoint-card-title">${side === src ? '⬆ Source' : '⬇ Destination'} · ${isLocal ? 'Local' : 'Remote'}</div>

                    ${isLocal ? `
                        <div class="endpoint-field">
                            <label>Persist Directory</label>
                            <input type="text"
                                   id="mig-local-dir"
                                   value="${this.escapeHtml(cfg.persist_dir)}"
                                   placeholder="./Memory/chroma_store"
                                   onchange="app.migrationState.local.persist_dir = this.value">
                        </div>
                    ` : `
                        <div class="endpoint-field">
                            <label>Host</label>
                            <input type="text"
                                   id="mig-remote-host"
                                   value="${this.escapeHtml(cfg.host)}"
                                   placeholder="chroma.my-server.local"
                                   onchange="app.migrationState.remote.host = this.value">
                        </div>
                        <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px;">
                            <div class="endpoint-field">
                                <label>Port</label>
                                <input type="number"
                                       value="${cfg.port}"
                                       min="1" max="65535"
                                       onchange="app.migrationState.remote.port = parseInt(this.value)">
                            </div>
                            <div class="endpoint-field">
                                <label>Protocol</label>
                                <select onchange="app.migrationState.remote.ssl = this.value === 'https'">
                                    <option value="http" ${!cfg.ssl ? 'selected' : ''}>HTTP</option>
                                    <option value="https" ${cfg.ssl ? 'selected' : ''}>HTTPS</option>
                                </select>
                            </div>
                        </div>
                        <div class="endpoint-field">
                            <label>Bearer Token (optional)</label>
                            <input type="password"
                                   value="${this.escapeHtml(cfg.auth_token)}"
                                   placeholder="Leave blank if unauthenticated"
                                   onchange="app.migrationState.remote.auth_token = this.value">
                        </div>
                        <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px;">
                            <div class="endpoint-field">
                                <label>Tenant</label>
                                <input type="text"
                                       value="${this.escapeHtml(cfg.tenant)}"
                                       placeholder="default_tenant"
                                       onchange="app.migrationState.remote.tenant = this.value">
                            </div>
                            <div class="endpoint-field">
                                <label>Database</label>
                                <input type="text"
                                       value="${this.escapeHtml(cfg.database)}"
                                       placeholder="default_database"
                                       onchange="app.migrationState.remote.database = this.value">
                            </div>
                        </div>
                    `}

                    <div class="endpoint-status ${status === 'ok' ? 'ok' : status === 'err' ? 'err' : status === 'checking' ? 'checking' : ''}">
                        <div class="dot"></div>
                        ${statusHtml}
                        <button class="btn-check" onclick="app.checkEndpoint('${side}')">Ping</button>
                    </div>
                </div>
            `;
        };

        const progress = s.progress;
        const pct = progress.total > 0 ? Math.round((progress.migrated + progress.skipped + progress.errors) / progress.total * 100) : 0;

        const logHtml = s.log.slice(-80).map(entry =>
            `<div class="log-line ${entry.level}">
                <span class="log-time">${entry.time}</span>
                <span class="log-msg">${this.escapeHtml(entry.msg)}</span>
            </div>`
        ).join('');

        const banner = s.lastResult;
        let bannerClass = '', bannerText = '';
        if (banner) {
            if (banner.errors === 0) {
                bannerClass = 'success';
                bannerText = `✓ Migration complete — ${banner.migrated} records migrated, ${banner.skipped} skipped, ${banner.duration_s}s`;
            } else if (banner.migrated > 0) {
                bannerClass = 'partial';
                bannerText = `⚠ Completed with errors — ${banner.migrated} migrated, ${banner.errors} errors`;
            } else {
                bannerClass = 'failed';
                bannerText = `✕ Migration failed — ${banner.errors} errors`;
            }
        }

        return `
            <div class="migration-panel" id="migration-panel">

                <!-- Header / toggle -->
                <div class="migration-panel-header" onclick="app.toggleMigrationPanel()">
                    <div class="migration-panel-title">
                        <span class="icon">⇄</span>
                        Chroma Migration
                        <span style="font-size:11px; font-weight:400; color:var(--text-dim);">
                            Local file store ↔ Remote server
                        </span>
                    </div>
                    <span class="migration-panel-chevron ${s.open ? 'open' : ''}">▼</span>
                </div>

                <!-- Body -->
                <div class="migration-panel-body ${s.open ? 'open' : ''}">
                    <div class="migration-panel-inner">

                        <!-- Endpoints -->
                        <div class="migration-endpoints">
                            ${endpointCard('local')}

                            <div class="migration-direction">
                                <div class="direction-arrow">
                                    ${s.direction === 'local_to_remote' ? '→' : '←'}
                                </div>
                                <button class="btn-swap" onclick="app.swapMigrationDirection()" title="Swap source and destination">
                                    ⇄ Swap
                                </button>
                            </div>

                            ${endpointCard('remote')}
                        </div>

                        <!-- Collections -->
                        <div>
                            <div style="font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.7px; color:var(--text-dim); margin-bottom:8px;">
                                Collections to migrate
                            </div>
                            <div class="collection-picker">
                                ${s.collections.map(col => {
                                    const sel = s.selectedCollections.includes(col);
                                    return `<div class="collection-chip ${sel ? 'selected' : ''}"
                                                 onclick="app.toggleMigrationCollection('${col}')">
                                                <span class="chip-check">${sel ? '✓' : '+'}</span>
                                                ${col}
                                            </div>`;
                                }).join('')}
                            </div>
                        </div>

                        <!-- Options -->
                        <div class="migration-options">
                            <div class="migration-option">
                                <label>Batch Size</label>
                                <input type="number" value="${s.batchSize}" min="10" max="2000"
                                       onchange="app.migrationState.batchSize = parseInt(this.value)">
                            </div>
                            <div class="migration-option">
                                <label>Embedding Model</label>
                                <input type="text" value="${this.escapeHtml(s.embeddingModel)}"
                                       placeholder="nomic-embed-text:latest"
                                       onchange="app.migrationState.embeddingModel = this.value">
                            </div>
                            <div class="migration-option">
                                <label style="visibility:hidden;">Space</label>
                                <label class="migration-checkbox-row">
                                    <input type="checkbox" ${s.skipExisting ? 'checked' : ''}
                                           onchange="app.migrationState.skipExisting = this.checked">
                                    <span>Skip existing records</span>
                                </label>
                            </div>
                        </div>

                        <!-- Result Banner -->
                        <div class="migration-result-banner ${banner ? 'visible ' + bannerClass : ''}"
                             id="migration-result-banner">
                            ${bannerText}
                        </div>

                        <!-- Actions -->
                        <div class="migration-actions">
                            <button class="btn-migrate" id="btn-start-migration"
                                    onclick="app.startMigration(false)"
                                    ${s.running ? 'disabled' : ''}>
                                ${s.running ? '⏳ Running…' : '⬆ Migrate'}
                            </button>
                            <button class="btn-dry-run" id="btn-dry-run"
                                    onclick="app.startMigration(true)"
                                    ${s.running ? 'disabled' : ''}>
                                🔍 Dry Run
                            </button>
                            <button class="btn-check" onclick="app.clearMigrationLog()"
                                    style="margin-left:auto;">
                                Clear Log
                            </button>
                        </div>

                        <!-- Progress -->
                        <div class="migration-progress ${s.running || s.log.length > 0 ? 'visible' : ''}"
                             id="migration-progress">

                            <div class="progress-bar-wrap">
                                <div class="progress-bar-fill ${s.running && progress.total === 0 ? 'indeterminate' : ''}"
                                     style="width: ${s.running && progress.total === 0 ? '' : pct + '%'}">
                                </div>
                            </div>

                            <div class="progress-stats">
                                <div class="progress-stat">
                                    <span class="progress-stat-label">Migrated</span>
                                    <span class="progress-stat-value green">${progress.migrated}</span>
                                </div>
                                <div class="progress-stat">
                                    <span class="progress-stat-label">Skipped</span>
                                    <span class="progress-stat-value yellow">${progress.skipped}</span>
                                </div>
                                <div class="progress-stat">
                                    <span class="progress-stat-label">Errors</span>
                                    <span class="progress-stat-value red">${progress.errors}</span>
                                </div>
                                ${progress.total > 0 ? `
                                <div class="progress-stat">
                                    <span class="progress-stat-label">Total</span>
                                    <span class="progress-stat-value">${progress.total}</span>
                                </div>
                                <div class="progress-stat">
                                    <span class="progress-stat-label">Time</span>
                                    <span class="progress-stat-value">${progress.duration_s}s</span>
                                </div>` : ''}
                            </div>

                            <!-- Log -->
                            <div class="migration-log" id="migration-log">
                                ${logHtml || '<span style="color:var(--text-dim);font-size:11px;">Waiting for output…</span>'}
                            </div>
                        </div>

                    </div>
                </div>
            </div>
        `;
    };


    // ============================================================
    // Panel toggling
    // ============================================================

    VeraChat.prototype.toggleMigrationPanel = function() {
        this.migrationState.open = !this.migrationState.open;
        this._refreshMigrationPanel();
    };

    VeraChat.prototype._refreshMigrationPanel = function() {
        const el = document.getElementById('migration-panel');
        if (el) {
            el.outerHTML = this.renderMigrationPanel();
        }
    };


    // ============================================================
    // Endpoint controls
    // ============================================================

    VeraChat.prototype.swapMigrationDirection = function() {
        this.migrationState.direction =
            this.migrationState.direction === 'local_to_remote'
                ? 'remote_to_local'
                : 'local_to_remote';
        this._refreshMigrationPanel();
    };

    VeraChat.prototype.toggleMigrationCollection = function(col) {
        const cols = this.migrationState.selectedCollections;
        const idx = cols.indexOf(col);
        if (idx === -1) { cols.push(col); } else { cols.splice(idx, 1); }
        this._refreshMigrationPanel();
    };

    VeraChat.prototype.checkEndpoint = async function(side) {
        const s = this.migrationState;
        if (side === 'local') {
            s.localStatus = 'checking';
        } else {
            s.remoteStatus = 'checking';
        }
        this._refreshMigrationPanel();

        try {
            const payload = side === 'local'
                ? { type: 'local', persist_dir: s.local.persist_dir }
                : {
                    type: 'remote',
                    host: s.remote.host,
                    port: s.remote.port,
                    ssl:  s.remote.ssl,
                    auth_token: s.remote.auth_token || null,
                    tenant:     s.remote.tenant,
                    database:   s.remote.database,
                };

            const resp = await fetch('http://llm.int:8888/api/memory/chroma/ping', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });

            const data = await resp.json();
            if (side === 'local') {
                s.localStatus  = data.ok ? 'ok' : 'err';
            } else {
                s.remoteStatus = data.ok ? 'ok' : 'err';
            }
            this._addMigrationLog(
                data.ok ? 'ok' : 'warn',
                `${side} endpoint: ${data.ok ? 'reachable' : (data.detail || 'unreachable')}`
            );
        } catch (err) {
            if (side === 'local') { s.localStatus  = 'err'; }
            else                  { s.remoteStatus = 'err'; }
            this._addMigrationLog('error', `Ping failed (${side}): ${err.message}`);
        }

        this._refreshMigrationPanel();
    };


    // ============================================================
    // Migration execution
    // ============================================================

    VeraChat.prototype.startMigration = async function(dryRun = false) {
        const s = this.migrationState;
        if (s.running) return;
        if (s.selectedCollections.length === 0) {
            this._addMigrationLog('warn', 'No collections selected.');
            this._refreshMigrationPanel();
            return;
        }
        if (!s.remote.host && s.direction !== 'local_to_remote') {
            // If direction is remote_to_local, we need a host
        }
        if (!s.remote.host) {
            this._addMigrationLog('warn', 'Remote host is required.');
            this._refreshMigrationPanel();
            return;
        }

        s.running = true;
        s.progress = { migrated: 0, skipped: 0, errors: 0, total: 0, duration_s: 0 };
        s.lastResult = null;
        this._addMigrationLog('info', `${dryRun ? '[DRY RUN] ' : ''}Starting migration…`);
        this._addMigrationLog('dim',  `Direction: ${s.direction.replace('_', ' → ')}`);
        this._addMigrationLog('dim',  `Collections: ${s.selectedCollections.join(', ')}`);
        this._refreshMigrationPanel();

        const payload = {
            direction:            s.direction,
            local_persist_dir:    s.local.persist_dir,
            remote_host:          s.remote.host,
            remote_port:          s.remote.port,
            remote_ssl:           s.remote.ssl,
            remote_auth_token:    s.remote.auth_token || null,
            remote_tenant:        s.remote.tenant,
            remote_database:      s.remote.database,
            collections:          s.selectedCollections,
            batch_size:           s.batchSize,
            skip_existing:        s.skipExisting,
            embedding_model:      s.embeddingModel,
            dry_run:              dryRun,
        };

        try {
            // ── Try SSE streaming first; fall back to a plain POST ──
            const supportsSSE = typeof EventSource !== 'undefined';
            if (supportsSSE) {
                await this._runMigrationSSE(payload);
            } else {
                await this._runMigrationPost(payload);
            }
        } catch (err) {
            this._addMigrationLog('error', `Unexpected error: ${err.message}`);
            s.running = false;
            this._refreshMigrationPanel();
        }
    };

    /**
     * SSE-based migration — receives progress events as the server
     * processes each batch.  Expects:
     *   data: {"type":"progress","migrated":N,"skipped":M,"errors":E,"total":T}
     *   data: {"type":"log","level":"info","msg":"..."}
     *   data: {"type":"done","migrated":N,...,"duration_s":X}
     */
    VeraChat.prototype._runMigrationSSE = async function(payload) {
        const s = this.migrationState;

        // POST to kick off the job and get a job_id, then open SSE stream
        let jobId;
        try {
            const resp = await fetch('http://llm.int:8888/api/memory/chroma/migrate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            const data = await resp.json();
            if (data.job_id) {
                jobId = data.job_id;
            } else if (data.error) {
                throw new Error(data.error);
            } else {
                // Server returned a final result directly (sync mode)
                this._handleMigrationResult(data);
                return;
            }
        } catch (err) {
            this._addMigrationLog('warn', `SSE init failed, falling back to polling: ${err.message}`);
            await this._runMigrationPost(payload);
            return;
        }

        // Open SSE stream
        const es = new EventSource(`http://llm.int:8888/api/memory/chroma/migrate/stream/${jobId}`);
        const self = this;

        es.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                switch (msg.type) {
                    case 'progress':
                        s.progress = {
                            migrated:   msg.migrated   ?? s.progress.migrated,
                            skipped:    msg.skipped    ?? s.progress.skipped,
                            errors:     msg.errors     ?? s.progress.errors,
                            total:      msg.total      ?? s.progress.total,
                            duration_s: msg.duration_s ?? s.progress.duration_s,
                        };
                        break;
                    case 'log':
                        self._addMigrationLog(msg.level || 'info', msg.msg || '');
                        break;
                    case 'done':
                        es.close();
                        self._handleMigrationResult(msg);
                        return;
                    case 'error':
                        self._addMigrationLog('error', msg.msg || 'Unknown error');
                        es.close();
                        s.running = false;
                        break;
                }
                self._refreshMigrationPanel();
            } catch (e) {
                console.warn('[Migration SSE] Parse error:', e);
            }
        };

        es.onerror = () => {
            es.close();
            self._addMigrationLog('warn', 'SSE connection lost — migration may still be running server-side.');
            s.running = false;
            self._refreshMigrationPanel();
        };
    };

    /**
     * Plain POST fallback — sends the whole migration job synchronously.
     * Less live feedback but works without SSE support.
     */
    VeraChat.prototype._runMigrationPost = async function(payload) {
        const s = this.migrationState;
        this._addMigrationLog('info', 'Running in synchronous mode (no live progress)…');

        try {
            const resp = await fetch('http://llm.int:8888/api/memory/chroma/migrate/sync', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });

            if (!resp.ok) {
                const text = await resp.text();
                throw new Error(`HTTP ${resp.status}: ${text}`);
            }

            const data = await resp.json();
            this._handleMigrationResult(data);
        } catch (err) {
            this._addMigrationLog('error', err.message);
            s.running = false;
            this._refreshMigrationPanel();
        }
    };

    VeraChat.prototype._handleMigrationResult = function(data) {
        const s = this.migrationState;
        s.running = false;

        // data may be a per-collection dict {"vera_memory": {...}, "long_term_docs": {...}}
        // or a flat result for a single collection
        if (data.vera_memory || data.long_term_docs) {
            let totalMigrated = 0, totalSkipped = 0, totalErrors = 0, totalDuration = 0;
            for (const [col, res] of Object.entries(data)) {
                if (typeof res !== 'object') continue;
                totalMigrated  += res.migrated  || 0;
                totalSkipped   += res.skipped   || 0;
                totalErrors    += res.errors    || 0;
                totalDuration  += res.duration_s || 0;
                this._addMigrationLog(
                    res.errors > 0 ? 'warn' : 'ok',
                    `[${col}] migrated=${res.migrated} skipped=${res.skipped} errors=${res.errors} (${res.duration_s}s)`
                );
            }
            s.progress = { migrated: totalMigrated, skipped: totalSkipped, errors: totalErrors, total: totalMigrated + totalSkipped + totalErrors, duration_s: Math.round(totalDuration) };
            s.lastResult = { migrated: totalMigrated, skipped: totalSkipped, errors: totalErrors, duration_s: Math.round(totalDuration) };
        } else {
            s.progress.migrated  = data.migrated  || 0;
            s.progress.skipped   = data.skipped   || 0;
            s.progress.errors    = data.errors    || 0;
            s.progress.duration_s = data.duration_s || 0;
            s.lastResult = data;
            this._addMigrationLog(
                data.errors > 0 ? 'warn' : 'ok',
                `Done — migrated=${data.migrated} skipped=${data.skipped} errors=${data.errors} (${data.duration_s}s)`
            );
        }

        this._refreshMigrationPanel();
    };


    // ============================================================
    // Log helpers
    // ============================================================

    VeraChat.prototype._addMigrationLog = function(level, msg) {
        const now = new Date();
        const time = now.toTimeString().slice(0, 8);
        this.migrationState.log.push({ level, msg, time });

        // Update live log element if panel is open
        const logEl = document.getElementById('migration-log');
        if (logEl) {
            const line = document.createElement('div');
            line.className = `log-line ${level}`;
            line.innerHTML = `<span class="log-time">${time}</span><span class="log-msg">${this.escapeHtml(msg)}</span>`;
            logEl.appendChild(line);
            logEl.scrollTop = logEl.scrollHeight;
        }
    };

    VeraChat.prototype.clearMigrationLog = function() {
        this.migrationState.log = [];
        this.migrationState.lastResult = null;
        this.migrationState.progress = { migrated: 0, skipped: 0, errors: 0, total: 0, duration_s: 0 };
        this._refreshMigrationPanel();
    };


    // ============================================================
    // Hook into updateMemoryUI to append migration panel
    // ============================================================

    const _origUpdateMemoryUI = VeraChat.prototype.updateMemoryUI;
    VeraChat.prototype.updateMemoryUI = function() {
        _origUpdateMemoryUI.call(this);

        const container = document.getElementById('memory-content');
        if (!container) return;

        // Append migration panel below the search + results
        const migrationEl = document.createElement('div');
        migrationEl.innerHTML = this.renderMigrationPanel();
        container.appendChild(migrationEl.firstElementChild);
    };


    // ============================================================
    // Backend API additions needed (reference)
    // ============================================================
    /*
     * The migration panel calls these three API endpoints.
     * Add them to your FastAPI router (Vera/API/memory_routes.py or similar):
     *
     * POST /api/memory/chroma/ping
     *   Body: { type: "local"|"remote", persist_dir?, host?, port?, ssl?, auth_token?, tenant?, database? }
     *   Response: { ok: bool, detail?: str }
     *   Implementation: try ChromaUnifiedBackend or ChromaHttpBackend.heartbeat()
     *
     * POST /api/memory/chroma/migrate          ← async, returns job_id for SSE
     *   POST /api/memory/chroma/migrate/sync   ← synchronous, returns result directly
     *   Body: {
     *     direction: "local_to_remote"|"remote_to_local",
     *     local_persist_dir, remote_host, remote_port, remote_ssl,
     *     remote_auth_token, remote_tenant, remote_database,
     *     collections: str[], batch_size, skip_existing,
     *     embedding_model, dry_run
     *   }
     *   Response (sync / done event): { migrated, skipped, errors, duration_s }
     *                              or { vera_memory: {...}, long_term_docs: {...} }
     *
     * GET /api/memory/chroma/migrate/stream/{job_id}   ← SSE endpoint
     *   Emits: progress | log | done | error events as JSON
     *
     * Example FastAPI implementation sketch:
     *
     *   from Vera.Memory.vector_backend import (
     *       ChromaUnifiedBackend, ChromaHttpBackend, MigrationManager,
     *       BackendFactory, _build_embedding_function
     *   )
     *
     *   @router.post("/chroma/ping")
     *   async def chroma_ping(body: PingRequest):
     *       try:
     *           if body.type == "local":
     *               ef = _build_embedding_function(body.embedding_model or "all-MiniLM-L6-v2")
     *               backend = ChromaUnifiedBackend(body.persist_dir, ef)
     *               backend._col.count()  # cheap check
     *           else:
     *               ef = _build_embedding_function(body.embedding_model or "all-MiniLM-L6-v2")
     *               backend = ChromaHttpBackend(body.host, body.port, ef, ssl=body.ssl,
     *                                           headers={"Authorization": f"Bearer {body.auth_token}"} if body.auth_token else None)
     *               backend.heartbeat()
     *           return {"ok": True}
     *       except Exception as e:
     *           return {"ok": False, "detail": str(e)}
     *
     *   @router.post("/chroma/migrate/sync")
     *   async def chroma_migrate_sync(body: MigrateRequest):
     *       ef = _build_embedding_function(body.embedding_model)
     *       dst_cfg = {"type": "chroma_http", "host": body.remote_host, ...}
     *       src_cfg = {"type": "chroma", "persist_dir": body.local_persist_dir}
     *       if body.direction == "remote_to_local":
     *           src_cfg, dst_cfg = dst_cfg, src_cfg
     *       return MigrationManager.migrate_all_collections(
     *           src_persist_dir=..., dst_config=dst_cfg, embedding_function=ef,
     *           collections=body.collections, batch_size=body.batch_size,
     *           skip_existing=body.skip_existing, dry_run=body.dry_run
     *       )
     */

    console.log('[VeraChat] Chroma migration panel loaded.');
})();