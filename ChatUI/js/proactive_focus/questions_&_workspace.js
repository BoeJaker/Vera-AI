(() => {
    // ============================================================
    // ADDITIONAL STYLES for Questions & Workspace tabs
    // ============================================================
    const style = document.createElement('style');
    style.textContent = `
        /* ---- Questions Tab ---- */
        .q-card {
            background: rgba(15, 23, 42, 0.6);
            border-radius: 8px;
            border-left: 4px solid #8b5cf6;
            padding: 14px;
            margin-bottom: 10px;
            transition: all 0.2s;
        }
        .q-card.q-answered {
            border-left-color: #10b981;
            opacity: 0.75;
        }
        .q-card.q-pending {
            border-left-color: #f59e0b;
        }
        .q-card.q-active {
            border-left-color: #3b82f6;
            box-shadow: 0 0 0 1px rgba(59,130,246,0.3);
        }
        .q-question-text {
            color: #e2e8f0;
            font-size: 13px;
            font-weight: 600;
            margin-bottom: 8px;
            line-height: 1.5;
        }
        .q-meta {
            color: #64748b;
            font-size: 11px;
            margin-bottom: 8px;
            display: flex;
            gap: 8px;
            align-items: center;
        }
        .q-category-badge {
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 10px;
            font-weight: 700;
            text-transform: uppercase;
            background: rgba(139,92,246,0.2);
            color: #a78bfa;
            border: 1px solid rgba(139,92,246,0.3);
        }
        .q-options {
            display: flex;
            flex-direction: column;
            gap: 6px;
            margin-bottom: 10px;
        }
        .q-option-btn {
            padding: 8px 12px;
            background: rgba(30,41,59,0.8);
            border: 1px solid #334155;
            border-radius: 6px;
            color: #cbd5e1;
            font-size: 12px;
            cursor: pointer;
            text-align: left;
            transition: all 0.15s;
        }
        .q-option-btn:hover {
            background: rgba(59,130,246,0.2);
            border-color: #3b82f6;
            color: #e2e8f0;
        }
        .q-option-btn.selected {
            background: rgba(16,185,129,0.2);
            border-color: #10b981;
            color: #34d399;
        }
        .q-answer-area {
            display: flex;
            gap: 8px;
            flex-direction: column;
        }
        .q-answer-input {
            background: #1e293b;
            color: #e2e8f0;
            border: 1px solid #334155;
            border-radius: 6px;
            padding: 8px 10px;
            font-size: 13px;
            width: 100%;
            resize: vertical;
            min-height: 60px;
            font-family: inherit;
            transition: border-color 0.2s;
        }
        .q-answer-input:focus {
            outline: none;
            border-color: #3b82f6;
        }
        .q-answer-row {
            display: flex;
            gap: 6px;
        }
        .q-answered-display {
            background: rgba(16,185,129,0.1);
            border: 1px solid rgba(16,185,129,0.3);
            border-radius: 6px;
            padding: 8px 12px;
            color: #34d399;
            font-size: 12px;
            display: flex;
            align-items: start;
            gap: 8px;
        }
        .q-answered-display .q-check {
            color: #10b981;
            font-size: 14px;
            flex-shrink: 0;
        }
        .q-stage-status {
            padding: 12px 16px;
            border-radius: 8px;
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 16px;
            font-size: 13px;
        }
        .q-stage-idle { background: rgba(100,116,139,0.15); border: 1px solid #334155; color: #94a3b8; }
        .q-stage-running { background: rgba(59,130,246,0.1); border: 1px solid rgba(59,130,246,0.3); color: #60a5fa; }
        .q-stage-done { background: rgba(16,185,129,0.1); border: 1px solid rgba(16,185,129,0.3); color: #34d399; }
        .q-pulse {
            width: 8px; height: 8px; border-radius: 50%;
            background: currentColor;
            animation: pulse 1.5s infinite;
            flex-shrink: 0;
        }
        .q-progress-bar-wrap {
            height: 4px;
            background: rgba(51,65,85,0.5);
            border-radius: 2px;
            overflow: hidden;
            margin: 8px 0;
        }
        .q-progress-bar {
            height: 100%;
            background: linear-gradient(90deg, #3b82f6, #8b5cf6);
            border-radius: 2px;
            transition: width 0.3s ease;
        }

        /* ---- Workspace Tab ---- */
        .ws-browser { height: 100%; display: flex; flex-direction: column; gap: 12px; }
        .ws-loading {
            display: flex; align-items: center; justify-content: center;
            gap: 10px; padding: 60px; color: #64748b; font-size: 13px;
        }
        .ws-loading-spinner {
            width: 20px; height: 20px;
            border: 2px solid #334155;
            border-top-color: #3b82f6;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }

        .ws-header { display: flex; flex-direction: column; gap: 10px; }
        .ws-header-top {
            display: flex; justify-content: space-between; align-items: center;
        }
        .ws-title { margin: 0; color: #e2e8f0; font-size: 16px; font-weight: 700; }
        .ws-stats-row {
            display: flex; align-items: center; gap: 6px;
            margin-top: 4px; flex-wrap: wrap;
        }
        .ws-stat { color: #64748b; font-size: 11px; }
        .ws-stat-active { color: #10b981; }
        .ws-stat-sep { color: #334155; }
        .ws-header-actions { display: flex; gap: 6px; }
        .ws-toolbar { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
        .ws-search-box { flex: 1; min-width: 140px; }
        .ws-search-input {
            width: 100%; background: #1e293b; border: 1px solid #334155;
            border-radius: 6px; padding: 7px 10px; color: #e2e8f0; font-size: 12px;
        }
        .ws-search-input:focus { outline: none; border-color: #3b82f6; }
        .ws-filter-pills { display: flex; gap: 4px; }
        .ws-pill {
            padding: 5px 10px; background: rgba(30,41,59,0.6);
            border: 1px solid #334155; border-radius: 4px;
            color: #94a3b8; font-size: 11px; cursor: pointer; transition: all 0.15s;
        }
        .ws-pill:hover { border-color: #475569; color: #cbd5e1; }
        .ws-pill-active {
            background: rgba(59,130,246,0.2); border-color: #3b82f6; color: #60a5fa;
        }

        .ws-list { display: flex; flex-direction: column; gap: 8px; overflow-y: auto; flex: 1; }
        .ws-group { display: flex; flex-direction: column; gap: 4px; }
        .ws-group-label {
            display: flex; align-items: center; gap: 6px;
            color: #64748b; font-size: 11px; font-weight: 600;
            text-transform: uppercase; letter-spacing: 0.05em;
            padding: 4px 0; margin-bottom: 2px;
        }
        .ws-group-count {
            background: rgba(51,65,85,0.6); border-radius: 10px;
            padding: 1px 6px; font-size: 10px; color: #94a3b8;
        }
        .ws-status-dot { width: 6px; height: 6px; border-radius: 50%; }
        .ws-dot-active { background: #10b981; box-shadow: 0 0 4px #10b981; }
        .ws-dot-idle { background: #64748b; }
        .ws-dot-archived { background: #374151; }

        .ws-card {
            background: rgba(15,23,42,0.5); border: 1px solid #334155;
            border-radius: 8px; cursor: pointer; transition: all 0.15s;
            overflow: hidden;
        }
        .ws-card:hover { border-color: #475569; background: rgba(30,41,59,0.5); }
        .ws-card-selected { border-color: #3b82f6; background: rgba(59,130,246,0.08); }
        .ws-card-active { border-left: 3px solid #10b981; }
        .ws-card-main {
            display: flex; align-items: center; gap: 10px; padding: 12px;
        }
        .ws-card-icon { font-size: 20px; flex-shrink: 0; }
        .ws-card-body { flex: 1; min-width: 0; }
        .ws-card-name {
            color: #e2e8f0; font-size: 13px; font-weight: 600;
            display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
        }
        .ws-focus-badge {
            background: rgba(139,92,246,0.2); border: 1px solid rgba(139,92,246,0.3);
            color: #a78bfa; border-radius: 4px; padding: 1px 6px; font-size: 10px;
        }
        .ws-card-meta {
            display: flex; align-items: center; gap: 4px;
            color: #64748b; font-size: 11px; margin-top: 3px; flex-wrap: wrap;
        }
        .ws-meta-sep { color: #334155; }
        .ws-card-tags { display: flex; gap: 4px; margin-top: 5px; flex-wrap: wrap; }
        .ws-tag {
            background: rgba(51,65,85,0.6); border-radius: 3px;
            padding: 1px 5px; color: #64748b; font-size: 10px;
        }
        .ws-card-chevron { color: #475569; font-size: 16px; flex-shrink: 0; }

        .ws-empty { color: #64748b; font-size: 13px; text-align: center; padding: 30px; }
        .ws-btn {
            padding: 6px 12px; border-radius: 6px; border: 1px solid #334155;
            background: rgba(30,41,59,0.8); color: #cbd5e1; font-size: 12px;
            cursor: pointer; transition: all 0.15s;
        }
        .ws-btn:hover { border-color: #475569; color: #e2e8f0; }
        .ws-btn-sm { padding: 5px 10px; font-size: 11px; }
        .ws-btn-primary {
            background: rgba(59,130,246,0.2); border-color: #3b82f6; color: #60a5fa;
        }
        .ws-btn-primary:hover { background: rgba(59,130,246,0.3); }

        /* Detail panel */
        .ws-detail {
            background: rgba(15,23,42,0.4); border: 1px solid #334155;
            border-radius: 8px; overflow: hidden;
        }
        .ws-detail-loading {
            padding: 30px; text-align: center; color: #64748b; font-size: 13px;
        }
        .ws-detail-header { padding: 14px 16px 10px; border-bottom: 1px solid #1e293b; }
        .ws-detail-title-row { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
        .ws-detail-name { margin: 0; color: #e2e8f0; font-size: 15px; font-weight: 700; }
        .ws-detail-path { color: #475569; font-size: 11px; font-family: monospace; }
        .ws-detail-badges {
            display: flex; gap: 6px; flex-wrap: wrap; margin-top: 8px;
        }
        .ws-badge {
            padding: 3px 8px; border-radius: 4px; font-size: 11px;
            background: rgba(51,65,85,0.5); border: 1px solid #334155; color: #94a3b8;
        }
        .ws-badge-git { background: rgba(249,115,22,0.1); border-color: rgba(249,115,22,0.3); color: #fb923c; }
        .ws-badge-focus { background: rgba(139,92,246,0.1); border-color: rgba(139,92,246,0.3); color: #a78bfa; }

        .ws-detail-tabs {
            display: flex; border-bottom: 1px solid #1e293b;
            background: rgba(15,23,42,0.3);
        }
        .ws-detail-tab {
            padding: 9px 16px; background: transparent; border: none;
            border-bottom: 2px solid transparent; color: #64748b;
            font-size: 12px; font-weight: 600; cursor: pointer; transition: all 0.15s;
        }
        .ws-detail-tab:hover:not(:disabled) { color: #94a3b8; }
        .ws-detail-tab.ws-tab-active { color: #60a5fa; border-bottom-color: #3b82f6; }
        .ws-detail-tab:disabled { opacity: 0.35; cursor: not-allowed; }
        .ws-detail-content { padding: 14px; max-height: 340px; overflow-y: auto; }

        /* Overview panel */
        .ws-section-title { color: #94a3b8; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px; }
        .ws-recent-files { display: flex; flex-direction: column; gap: 3px; }
        .ws-recent-file {
            display: flex; align-items: center; gap: 8px; padding: 6px 8px;
            border-radius: 5px; cursor: pointer; transition: background 0.1s;
        }
        .ws-recent-file:hover { background: rgba(51,65,85,0.4); }
        .ws-file-icon { font-size: 13px; flex-shrink: 0; }
        .ws-file-name { color: #cbd5e1; font-size: 12px; flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .ws-file-meta { color: #475569; font-size: 10px; flex-shrink: 0; }
        .ws-empty-section { color: #64748b; font-size: 12px; text-align: center; padding: 20px; }

        /* Files panel */
        .ws-files-layout { display: flex; gap: 10px; height: 280px; }
        .ws-tree-panel { width: 200px; flex-shrink: 0; overflow-y: auto; border-right: 1px solid #1e293b; padding-right: 10px; }
        .ws-preview-panel { flex: 1; overflow: auto; }
        .ws-tree { font-size: 12px; }
        .ws-tree-item {
            display: flex; align-items: center; gap: 5px; padding: 4px 6px;
            border-radius: 4px; cursor: pointer; color: #94a3b8; transition: background 0.1s;
        }
        .ws-tree-item:hover { background: rgba(51,65,85,0.4); color: #cbd5e1; }
        .ws-tree-item.ws-tree-active { background: rgba(59,130,246,0.15); color: #60a5fa; }
        .ws-tree-folder { color: #e2e8f0; font-weight: 600; }
        .ws-tree-arrow { width: 10px; flex-shrink: 0; color: #475569; font-size: 10px; }
        .ws-tree-icon { flex-shrink: 0; }
        .ws-tree-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .ws-tree-size { color: #475569; font-size: 10px; flex-shrink: 0; }
        .ws-tree-children { margin-left: 12px; border-left: 1px solid #1e293b; }
        .ws-preview-empty {
            display: flex; align-items: center; justify-content: center;
            height: 100%; color: #475569; font-size: 12px;
        }
        .ws-preview { height: 100%; display: flex; flex-direction: column; }
        .ws-preview-header {
            display: flex; justify-content: space-between; align-items: center;
            padding: 6px 8px; background: rgba(15,23,42,0.6); border-radius: 4px 4px 0 0;
            border-bottom: 1px solid #1e293b;
        }
        .ws-preview-name { color: #94a3b8; font-size: 11px; font-family: monospace; }
        .ws-preview-size { color: #475569; font-size: 10px; }
        .ws-preview-code {
            margin: 0; padding: 10px; background: rgba(15,23,42,0.4);
            color: #cbd5e1; font-size: 11px; font-family: 'Courier New', monospace;
            overflow: auto; flex: 1; border-radius: 0 0 4px 4px; white-space: pre;
        }
        .ws-preview-binary {
            display: flex; align-items: center; justify-content: center;
            height: 100%; color: #475569; font-size: 12px;
        }
        .ws-files-loading { color: #64748b; font-size: 12px; text-align: center; padding: 30px; }

        /* Board panel */
        .ws-board { display: flex; flex-direction: column; gap: 10px; }
        .ws-board-section { }
        .ws-board-cat-header {
            display: flex; justify-content: space-between; align-items: center;
            color: #94a3b8; font-size: 11px; font-weight: 700;
            text-transform: uppercase; letter-spacing: 0.04em;
            padding-bottom: 5px; border-bottom: 1px solid #1e293b; margin-bottom: 6px;
        }
        .ws-board-count {
            background: rgba(51,65,85,0.6); border-radius: 8px;
            padding: 1px 5px; font-size: 10px; color: #64748b;
        }
        .ws-board-items { display: flex; flex-direction: column; gap: 4px; }
        .ws-board-item {
            background: rgba(15,23,42,0.5); border-left: 3px solid #334155;
            border-radius: 0 4px 4px 0; padding: 6px 8px;
            color: #cbd5e1; font-size: 11px; line-height: 1.4;
        }
        .ws-board-more { color: #475569; font-size: 11px; padding: 4px 8px; }

        /* Create dialog */
        .ws-create-overlay {
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.6); z-index: 10001;
            display: flex; align-items: center; justify-content: center;
            backdrop-filter: blur(4px);
        }
        .ws-create-modal {
            background: linear-gradient(135deg, #1e293b, #0f172a);
            border: 1px solid #334155; border-radius: 12px;
            padding: 24px; width: 90%; max-width: 420px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.5);
        }
        .ws-create-modal h3 { margin: 0 0 16px; color: #e2e8f0; font-size: 16px; }
        .ws-create-field { margin-bottom: 12px; }
        .ws-create-label { color: #94a3b8; font-size: 12px; display: block; margin-bottom: 4px; }
        .ws-create-input {
            width: 100%; background: #1e293b; border: 1px solid #334155;
            border-radius: 6px; padding: 8px 10px; color: #e2e8f0; font-size: 13px;
        }
        .ws-create-input:focus { outline: none; border-color: #3b82f6; }
        .ws-template-grid {
            display: grid; grid-template-columns: repeat(3,1fr); gap: 6px;
        }
        .ws-template-opt {
            padding: 8px; border-radius: 6px; border: 1px solid #334155;
            background: rgba(15,23,42,0.5); color: #94a3b8; font-size: 11px;
            cursor: pointer; text-align: center; transition: all 0.15s;
        }
        .ws-template-opt:hover { border-color: #475569; color: #cbd5e1; }
        .ws-template-opt.selected {
            border-color: #3b82f6; background: rgba(59,130,246,0.15); color: #60a5fa;
        }
        .ws-template-icon { font-size: 20px; display: block; margin-bottom: 3px; }
    `;
    document.head.appendChild(style);

    // ============================================================
    // HELPERS — board item → _focusQuestions schema
    // ============================================================

    /**
     * Convert a raw board questions[] item into the _focusQuestions schema.
     * Returns null for internal gap/meta items that aren't user-facing questions.
     */
    function _boardItemToQuestion(item) {
        if (!item) return null;

        if (typeof item === 'string') {
            const text = item.trim();
            if (!text) return null;
            return { question: text, category: 'general', options: [], response: null, answered_at: null, skipped: false };
        }

        if (typeof item !== 'object') return null;

        const meta = item.metadata || {};
        const type = meta.type || '';

        // Skip raw gap-detection artefacts — they are not yet user-facing questions
        if (type === 'info_gap') return null;

        // Extract question text from wherever Python stored it
        const questionText = (
            meta.question ||
            item.note ||
            item.description ||
            ''
        ).trim();

        if (!questionText) return null;

        // Derive a readable category
        let category = meta.category || 'general';
        if (type === 'promoted_gap_question') category = 'gap';
        if (type === 'action_escalation')     category = 'urgent';
        if (meta.priority === 'high')         category = 'urgent';

        return {
            question:    questionText,
            category:    category,
            options:     Array.isArray(meta.options) ? meta.options : [],
            response:    item.response    || null,
            answered_at: item.answered_at || null,
            skipped:     item.skipped     || false,
        };
    }

    /**
     * Merge board items into the existing _focusQuestions array.
     * Existing answers are preserved by matching on normalised question text.
     */
    function _mergeBoardQuestions(existing, boardItems) {
        // Build answered-state lookup from whatever is currently in _focusQuestions
        const answered = new Map();
        (existing || []).forEach(q => {
            if (q.response) {
                answered.set(q.question.trim().toLowerCase(), {
                    response:    q.response,
                    answered_at: q.answered_at,
                    skipped:     q.skipped,
                });
            }
        });

        const merged = [];
        (boardItems || []).forEach(item => {
            const q = _boardItemToQuestion(item);
            if (!q) return;
            // Re-attach any existing answer so a board refresh doesn't wipe user work
            const key = q.question.trim().toLowerCase();
            if (answered.has(key)) {
                const saved = answered.get(key);
                q.response    = saved.response;
                q.answered_at = saved.answered_at;
                q.skipped     = saved.skipped;
            }
            merged.push(q);
        });
        return merged;
    }

    // ============================================================
    // PATCH updateFocusUI to inject two more tabs
    // ============================================================

    const originalUpdateFocusUI = VeraChat.prototype.updateFocusUI;

    VeraChat.prototype.updateFocusUI = function(preserveScrollPos = null) {
        let container = document.getElementById('tab-focus');
        if (!container) return;

        this.focusBoard = this.normalizeFocusBoard(this.focusBoard);

        // ── SYNC _focusQuestions from focusBoard.questions ──────────
        // This is the core fix: the Python QuestionsStage writes to
        // board.questions[], but the UI renders from _focusQuestions.
        // We merge on every render so any path that updates focusBoard
        // (WebSocket, file load, manual refresh) automatically populates
        // the Questions tab without needing a separate API call.
        const boardQs = this.focusBoard.questions || [];
        if (boardQs.length) {
            this._focusQuestions = _mergeBoardQuestions(this._focusQuestions, boardQs);
            if (this._questionsStageStatus === 'idle') {
                this._questionsStageStatus = 'done';
            }
            if (this._activeQIdx == null || this._activeQIdx < 0) {
                this._activeQIdx = this._focusQuestions.findIndex(q => !q.response);
            }
        }
        // ────────────────────────────────────────────────────────────

        if (!this.currentFocusTab) this.currentFocusTab = 'ideas';

        let html = `
        <div style="padding: 20px; overflow-y: auto; height: 100%;">
            <!-- Control Bar -->
            <div id="focusControlBar" style="display: flex; flex-wrap: wrap; gap: 8px; justify-content: space-between; align-items: center; margin-bottom: 20px; padding: 16px; background: rgba(15, 23, 42, 0.5); border-radius: 8px; border: 1px solid #334155;">
                <div style="display: flex; flex-wrap: wrap; gap: 8px; align-items: center;">
                    ${this.currentFocus ? `
                        <button class="focus-header-btn ${this.focusRunning ? 'active' : ''}" onclick="app.${this.focusRunning ? 'stopProactiveThinking' : 'startProactiveThinking'}()">
                            ${this.focusRunning ? '⏸ Stop' : '▶ Start'}
                        </button>
                        <button class="focus-header-btn" onclick="app.triggerProactiveThought()">Think Now</button>
                    ` : ''}
                    <button class="focus-header-btn" onclick="app.showFocusBoardMenu()">Load</button>
                    <button class="focus-header-btn" onclick="app.loadFocusStatus()">Refresh</button>
                    <button class="focus-header-btn" onclick="app.saveFocusBoard()">Save</button>
                </div>
                <span class="focus-header-btn" style="pointer-events: none; background: ${this.focusRunning ? '#10b981' : 'rgba(107, 114, 128, 0.5)'}; border-color: ${this.focusRunning ? '#10b981' : '#6b7280'};">
                    ${this.focusRunning ? '● RUNNING' : '○ STOPPED'}
                </span>
            </div>
        `;

        html += this.renderFocusSection();

        // Extended tab list including Questions and Workspace
        const categories = [
            { key: 'ideas',      label: 'Ideas',      icon: '💡', color: '#8b5cf6' },
            { key: 'next_steps', label: 'Next Steps',  icon: '→',  color: '#f59e0b' },
            { key: 'actions',    label: 'Actions',     icon: '⚡', color: '#3b82f6' },
            { key: 'progress',   label: 'Progress',    icon: '✓',  color: '#10b981' },
            { key: 'issues',     label: 'Issues',      icon: '⚠',  color: '#ef4444' },
            { key: 'completed',  label: 'Completed',   icon: '✔',  color: '#6b7280' },
            { key: 'questions',  label: 'Questions',   icon: '❓',  color: '#ec4899' },
            { key: 'workspace',  label: 'Workspace',   icon: '📂',  color: '#06b6d4' },
        ];

        html += `<div style="display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 0;">`;
        categories.forEach(cat => {
            let count = 0;
            if (cat.key === 'questions') {
                count = (this._focusQuestions || []).length;
            } else if (cat.key === 'workspace') {
                count = '';
            } else if (cat.key === 'actions') {
                count = this._getExpandedActionsCount(this.focusBoard[cat.key] || []);
            } else {
                count = (this.focusBoard[cat.key] || []).length;
            }
            html += `
                <div class="focus-tab ${this.currentFocusTab === cat.key ? 'active' : ''}"
                     onclick="app.switchFocusTab('${cat.key}')"
                     style="border-left: 3px solid ${cat.color};">
                    <span>${cat.icon}</span>
                    <span>${cat.label}</span>
                    ${count !== '' ? `<span style="opacity:0.7">(${count})</span>` : ''}
                </div>`;
        });
        html += `</div>`;

        // Existing board tab contents
        const boardCategories = categories.filter(c => !['questions','workspace'].includes(c.key));
        boardCategories.forEach(cat => {
            html += this.renderTabContent(cat);
        });

        // Questions tab content
        html += this.renderQuestionsTabContent();

        // Workspace tab content
        html += this.renderWorkspaceTabContent();

        html += `</div>`;
        container.innerHTML = html;

        this.initializeDragAndDrop();
        this._initQuestionsTabListeners();
        this._initWorkspaceBrowser();

        if (preserveScrollPos !== null) container.scrollTop = preserveScrollPos;
    };

    // ============================================================
    // QUESTIONS TAB
    // ============================================================

    VeraChat.prototype._focusQuestions = [];
    VeraChat.prototype._questionsStageStatus = 'idle'; // idle | running | done
    VeraChat.prototype._activeQIdx = null;

    VeraChat.prototype.renderQuestionsTabContent = function() {
        const isActive = this.currentFocusTab === 'questions';
        const questions = this._focusQuestions || [];
        const status = this._questionsStageStatus || 'idle';

        const answered = questions.filter(q => q.response).length;
        const pending   = questions.filter(q => !q.response).length;

        let statusHtml = '';
        if (status === 'idle') {
            statusHtml = `<div class="q-stage-status q-stage-idle"><span>No active question session</span></div>`;
        } else if (status === 'running') {
            statusHtml = `
                <div class="q-stage-status q-stage-running">
                    <span class="q-pulse"></span>
                    <span>Questions stage is running — awaiting your responses</span>
                </div>`;
        } else {
            statusHtml = `
                <div class="q-stage-status q-stage-done">
                    <span>✓</span>
                    <span>${answered} of ${questions.length} answered</span>
                </div>`;
        }

        if (questions.length > 0) {
            const pct = Math.round((answered / questions.length) * 100);
            statusHtml += `
                <div class="q-progress-bar-wrap">
                    <div class="q-progress-bar" style="width:${pct}%"></div>
                </div>
            `;
        }

        let questionsHtml = '';
        if (questions.length === 0) {
            questionsHtml = `
                <div style="color:#64748b; font-size:13px; text-align:center; padding:40px; font-style:italic;">
                    No questions yet.<br>Click "Generate Questions" to have Vera analyse the current focus and ask clarifying questions.
                </div>`;
        } else {
            questions.forEach((q, idx) => {
                const isAnswered = !!q.response;
                const cardClass = isAnswered ? 'q-answered' : (this._activeQIdx === idx ? 'q-active' : 'q-pending');

                let optionsHtml = '';
                if (q.options && q.options.length && !isAnswered) {
                    optionsHtml = `<div class="q-options">`;
                    q.options.forEach((opt) => {
                        optionsHtml += `
                            <button class="q-option-btn" data-q-idx="${idx}" data-opt="${this._escQ(opt)}"
                                    onclick="app._selectQuestionOption(${idx}, '${this._escQ(opt)}')">
                                ${this._escQ(opt)}
                            </button>`;
                    });
                    optionsHtml += `</div>`;
                }

                let answerAreaHtml = '';
                if (!isAnswered) {
                    answerAreaHtml = `
                        <div class="q-answer-area">
                            ${optionsHtml}
                            <textarea class="q-answer-input" id="q-input-${idx}" placeholder="Type your answer…" rows="2"></textarea>
                            <div class="q-answer-row">
                                <button class="panel-btn" style="font-size:11px; padding:5px 12px;" onclick="app._submitQuestionAnswer(${idx})">✓ Submit</button>
                                <button class="panel-btn" style="font-size:11px; padding:5px 10px;" onclick="app._skipQuestion(${idx})">Skip</button>
                            </div>
                        </div>`;
                } else {
                    answerAreaHtml = `
                        <div class="q-answered-display">
                            <span class="q-check">✓</span>
                            <span>${this._escQ(q.response)}</span>
                        </div>
                        <div style="margin-top:6px;">
                            <button class="panel-btn" style="font-size:10px; padding:3px 8px;" onclick="app._clearQuestionAnswer(${idx})">✏️ Edit</button>
                        </div>`;
                }

                questionsHtml += `
                    <div class="q-card ${cardClass}" id="q-card-${idx}">
                        <div class="q-meta">
                            <span class="q-category-badge">${q.category || 'general'}</span>
                            <span>Q${idx + 1} of ${questions.length}</span>
                        </div>
                        <div class="q-question-text">${this._escQ(q.question)}</div>
                        ${answerAreaHtml}
                    </div>`;
            });
        }

        return `
            <div class="focus-tab-content ${isActive ? 'active' : ''}">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; flex-wrap:wrap; gap:8px;">
                    <div style="font-weight:600; color:#e2e8f0; font-size:16px;">❓ Questions & Clarification</div>
                    <div style="display:flex; gap:6px; flex-wrap:wrap;">
                        ${this.currentFocus ? `
                            <button class="panel-btn" style="font-size:11px; padding:6px 12px;" onclick="app.runQuestionsStage()">▶️ Generate</button>
                        ` : ''}
                        ${questions.length > 0 ? `
                            <button class="panel-btn" style="font-size:11px; padding:6px 12px;" onclick="app._submitAllQuestionAnswers()">📤 Submit All</button>
                            <button class="panel-btn" style="font-size:11px; padding:6px 12px;" onclick="app._clearAllQuestions()">🗑️ Clear</button>
                        ` : ''}
                    </div>
                </div>
                ${statusHtml}
                <div style="display:flex; flex-direction:column; gap:0;">
                    ${questionsHtml}
                </div>
            </div>`;
    };

    // Escape helper for question text in HTML attributes
    VeraChat.prototype._escQ = function(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    };

    VeraChat.prototype._initQuestionsTabListeners = function() {
        // Keyboard submit on q-answer-input (Enter = submit, Shift+Enter = newline)
        const inputs = document.querySelectorAll('.q-answer-input');
        inputs.forEach(input => {
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    const idx = parseInt(input.id.replace('q-input-', ''));
                    this._submitQuestionAnswer(idx);
                }
            });
        });
    };

    VeraChat.prototype._selectQuestionOption = function(idx, option) {
        const input = document.getElementById(`q-input-${idx}`);
        if (input) {
            input.value = option;
            const card = document.getElementById(`q-card-${idx}`);
            if (card) {
                card.querySelectorAll('.q-option-btn').forEach(btn => {
                    btn.classList.toggle('selected', btn.dataset.opt === option);
                });
            }
        }
    };

    VeraChat.prototype._submitQuestionAnswer = async function(idx) {
        const questions = this._focusQuestions || [];
        if (idx >= questions.length) return;

        const input = document.getElementById(`q-input-${idx}`);
        const answer = input ? input.value.trim() : '';
        if (!answer) {
            this.addSystemMessage('Please enter an answer before submitting');
            return;
        }

        questions[idx].response = answer;
        questions[idx].answered_at = new Date().toISOString();

        try {
            await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/questions/answer`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    question_index: idx,
                    question: questions[idx].question,
                    answer: answer,
                    category: questions[idx].category
                })
            });
        } catch (err) {
            console.warn('Could not post answer to backend:', err);
        }

        this._focusQuestions = questions;
        // Advance to next unanswered
        this._activeQIdx = questions.findIndex((q, i) => i > idx && !q.response);
        this.updateFocusUI();
        this.addSystemMessage(`✓ Answer submitted for Q${idx + 1}`);
    };

    VeraChat.prototype._skipQuestion = function(idx) {
        const questions = this._focusQuestions || [];
        if (idx >= questions.length) return;
        questions[idx].response = '[skipped]';
        questions[idx].skipped = true;
        this._focusQuestions = questions;
        this.updateFocusUI();
    };

    VeraChat.prototype._clearQuestionAnswer = function(idx) {
        const questions = this._focusQuestions || [];
        if (idx >= questions.length) return;
        delete questions[idx].response;
        delete questions[idx].answered_at;
        delete questions[idx].skipped;
        this._focusQuestions = questions;
        this._activeQIdx = idx;
        this.updateFocusUI();
    };

    VeraChat.prototype._submitAllQuestionAnswers = async function() {
        const questions = this._focusQuestions || [];
        const pending = questions.filter(q => !q.response);
        if (pending.length > 0) {
            const proceed = confirm(`${pending.length} question(s) still unanswered. Submit anyway?`);
            if (!proceed) return;
        }

        try {
            await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/questions/submit-all`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ questions: questions })
            });
            this.addSystemMessage(`📤 All answers submitted to the Questions Stage`);
            this._questionsStageStatus = 'done';
            this.updateFocusUI();
        } catch (err) {
            console.error('Failed to submit answers:', err);
            this.addSystemMessage('Error submitting answers');
        }
    };

    VeraChat.prototype._clearAllQuestions = function() {
        if (!confirm('Clear all questions and answers?')) return;
        this._focusQuestions = [];
        this._questionsStageStatus = 'idle';
        this._activeQIdx = null;
        this.updateFocusUI();
    };

    // Run the Questions Stage via API
    VeraChat.prototype.runQuestionsStage = async function() {
        if (!this.sessionId || !this.currentFocus) return;

        this._questionsStageStatus = 'running';
        this.updateFocusUI();
        this.addSystemMessage('❓ Generating clarifying questions…');

        try {
            const response = await fetch(`http://llm.int:8888/api/focus/${this.sessionId}/stage/questions`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({})
            });

            if (response.ok) {
                const data = await response.json();
                // Backend may return questions immediately or push via WebSocket
                if (data.questions && Array.isArray(data.questions)) {
                    this._focusQuestions = _mergeBoardQuestions(
                        this._focusQuestions,
                        data.questions.map(q => ({
                            note:     q.question || q,
                            metadata: {
                                category: q.category || 'general',
                                options:  q.options  || [],
                            }
                        }))
                    );
                    this._questionsStageStatus = 'done';
                    this._activeQIdx = this._focusQuestions.findIndex(q => !q.response);
                    this.updateFocusUI();
                    this.addSystemMessage(`❓ ${this._focusQuestions.length} questions generated`);
                }
                // If no immediate questions, board_updated WebSocket event will handle it
            }
        } catch (error) {
            console.error('Failed to run questions stage:', error);
            this._questionsStageStatus = 'idle';
            this.addSystemMessage('Error running questions stage');
            this.updateFocusUI();
        }
    };

    // Handle incoming WebSocket events for questions
    const originalHandleFocusEvent = VeraChat.prototype.handleFocusEvent;
    VeraChat.prototype.handleFocusEvent = function(data) {
        if (data.type === 'questions_generated') {
            const qs = data.data.questions || [];
            this._focusQuestions = _mergeBoardQuestions(
                this._focusQuestions,
                qs.map(q => ({
                    note:     q.question || q,
                    metadata: {
                        category: q.category || 'general',
                        options:  q.options  || [],
                    }
                }))
            );
            this._questionsStageStatus = 'done';
            this._activeQIdx = this._focusQuestions.findIndex(q => !q.response);
            const container = document.getElementById('tab-focus');
            this.updateFocusUI(container ? container.scrollTop : 0);
            this.addSystemMessage(`❓ ${qs.length} questions ready for your review`);
            return;
        }
        if (data.type === 'question_answered') {
            return;
        }
        // board_updated and focus_status are handled inside updateFocusUI via the
        // _mergeBoardQuestions call at the top — no special case needed here.
        originalHandleFocusEvent.call(this, data);
    };

    // ============================================================
    // WORKSPACE TAB
    // ============================================================

    VeraChat.prototype._ws = {
        workspaces: [],
        stats: null,
        loading: false,
        filter: 'all',
        searchQuery: '',
        selectedId: null,
        selectedDetail: null,
        activePanel: 'overview',
        fileTree: null,
        fileContent: null,
        expandedDirs: new Set(),
        detailCache: new Map(),
    };

    VeraChat.prototype.renderWorkspaceTabContent = function() {
        const isActive = this.currentFocusTab === 'workspace';
        const ws = this._ws;

        let bodyHtml = '';
        if (ws.loading && !ws.workspaces.length) {
            bodyHtml = `
                <div class="ws-loading">
                    <div class="ws-loading-spinner"></div>
                    <span>Discovering workspaces…</span>
                </div>`;
        } else {
            bodyHtml = this._renderWsBody();
        }

        return `
            <div class="focus-tab-content ${isActive ? 'active' : ''}">
                <div class="ws-browser">
                    ${this._renderWsHeader()}
                    ${ws.selectedId ? this._renderWsDetail() : ''}
                    ${bodyHtml}
                </div>
            </div>`;
    };

    VeraChat.prototype._renderWsHeader = function() {
        const ws = this._ws;
        const stats = ws.stats;
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
                                ${stats.workspaces_with_git ? `<span class="ws-stat-sep">·</span><span class="ws-stat">${stats.workspaces_with_git} git</span>` : ''}
                            </div>` : ''}
                    </div>
                    <div class="ws-header-actions">
                        <button class="ws-btn ws-btn-sm" id="ws-refresh-btn" title="Refresh">↻</button>
                        <button class="ws-btn ws-btn-primary ws-btn-sm" id="ws-create-btn">+ New</button>
                    </div>
                </div>
                <div class="ws-toolbar">
                    <div class="ws-search-box">
                        <input type="text" class="ws-search-input" id="ws-search-input"
                               placeholder="Filter workspaces…" value="${ws.searchQuery}" />
                    </div>
                    <div class="ws-filter-pills">
                        ${['all','active','idle','archived'].map(f => `
                            <button class="ws-pill ${ws.filter === f ? 'ws-pill-active' : ''}"
                                    data-ws-filter="${f}">
                                ${f.charAt(0).toUpperCase() + f.slice(1)}
                            </button>`).join('')}
                    </div>
                </div>
            </div>`;
    };

    VeraChat.prototype._renderWsBody = function() {
        const ws = this._ws;
        let items = ws.workspaces;

        if (ws.searchQuery.trim()) {
            const q = ws.searchQuery.toLowerCase();
            items = items.filter(w =>
                w.name.toLowerCase().includes(q) ||
                (w.focus_name && w.focus_name.toLowerCase().includes(q)) ||
                (w.tags && w.tags.some(t => t.includes(q)))
            );
        }

        const active   = items.filter(w => w.status === 'active');
        const idle     = items.filter(w => w.status === 'idle');
        const archived = items.filter(w => w.status === 'archived');

        if (!items.length) {
            return `<div class="ws-empty">${ws.searchQuery ? 'No workspaces match your search' : 'No workspaces found — click ↻ to refresh'}</div>`;
        }

        const renderGroup = (label, dot, list) => {
            if (!list.length) return '';
            return `
                <div class="ws-group">
                    <div class="ws-group-label">
                        <span class="ws-status-dot ${dot}"></span>
                        ${label} <span class="ws-group-count">${list.length}</span>
                    </div>
                    ${list.map(w => this._renderWsCard(w)).join('')}
                </div>`;
        };

        return `
            <div class="ws-list">
                ${renderGroup('Active',   'ws-dot-active',   active)}
                ${renderGroup('Recent',   'ws-dot-idle',     idle)}
                ${renderGroup('Archived', 'ws-dot-archived', archived)}
            </div>`;
    };

    VeraChat.prototype._renderWsCard = function(ws) {
        const isSelected = this._ws.selectedId === ws.id;
        const timeSince = this._wsTimeSince(ws.last_modified);
        const icon = ws.has_focus_board ? '🎯' : ws.has_git ? '📦' : '📁';

        return `
            <div class="ws-card ${isSelected ? 'ws-card-selected' : ''} ws-card-${ws.status}"
                 data-ws-select="${ws.id}">
                <div class="ws-card-main">
                    <div class="ws-card-icon">${icon}</div>
                    <div class="ws-card-body">
                        <div class="ws-card-name">
                            ${this.escapeHtml(ws.name)}
                            ${ws.focus_name ? `<span class="ws-focus-badge">${this.escapeHtml(ws.focus_name)}</span>` : ''}
                        </div>
                        <div class="ws-card-meta">
                            <span>${ws.file_count} files</span>
                            <span class="ws-meta-sep">·</span>
                            <span>${this._wsHumanSize(ws.total_size_bytes)}</span>
                            ${timeSince ? `<span class="ws-meta-sep">·</span><span>${timeSince}</span>` : ''}
                        </div>
                        ${ws.tags && ws.tags.length ? `
                            <div class="ws-card-tags">
                                ${ws.tags.map(t => `<span class="ws-tag">${t}</span>`).join('')}
                            </div>` : ''}
                    </div>
                    <div class="ws-card-chevron">${isSelected ? '▾' : '›'}</div>
                </div>
            </div>`;
    };

    VeraChat.prototype._renderWsDetail = function() {
        const ws = this._ws;
        const detail = ws.selectedDetail;

        if (!detail) {
            return `<div class="ws-detail"><div class="ws-detail-loading">Loading workspace…</div></div>`;
        }

        const panels = ['overview', 'files', 'board'];
        const panelLabels = { overview: '📋 Overview', files: '📂 Files', board: '🎯 Board' };

        return `
            <div class="ws-detail">
                <div class="ws-detail-header">
                    <div class="ws-detail-title-row">
                        <h3 class="ws-detail-name">${this.escapeHtml(detail.name)}</h3>
                        <span class="ws-detail-path">${this.escapeHtml(detail.path)}</span>
                    </div>
                    <div class="ws-detail-badges">
                        ${detail.has_git ? `<span class="ws-badge ws-badge-git">git: ${detail.git_branch || '?'}${detail.git_status ? ' · ' + detail.git_status : ''}</span>` : ''}
                        ${detail.has_focus_board ? `<span class="ws-badge ws-badge-focus">focus board</span>` : ''}
                        <span class="ws-badge">${detail.file_count} files · ${this._wsHumanSize(detail.total_size_bytes)}</span>
                    </div>
                </div>
                <div class="ws-detail-tabs">
                    ${panels.map(p => `
                        <button class="ws-detail-tab ${ws.activePanel === p ? 'ws-tab-active' : ''}"
                                data-ws-panel="${p}"
                                ${p === 'board' && !detail.has_focus_board ? 'disabled' : ''}>
                            ${panelLabels[p]}
                        </button>`).join('')}
                </div>
                <div class="ws-detail-content">
                    ${ws.activePanel === 'overview' ? this._renderWsOverview(detail) : ''}
                    ${ws.activePanel === 'files'    ? this._renderWsFiles()          : ''}
                    ${ws.activePanel === 'board'    ? this._renderWsBoard(detail)    : ''}
                </div>
            </div>`;
    };

    VeraChat.prototype._renderWsOverview = function(detail) {
        const files = detail.recent_files || [];
        if (!files.length) return `<div class="ws-empty-section">No recent files</div>`;
        return `
            <div class="ws-overview">
                <div class="ws-section-title">Recently Modified</div>
                <div class="ws-recent-files">
                    ${files.slice(0, 12).map(f => `
                        <div class="ws-recent-file" data-ws-open-file="${this._escQ(f.path)}">
                            <span class="ws-file-icon">${this._wsFileIcon(f.extension)}</span>
                            <span class="ws-file-name">${this.escapeHtml(f.path)}</span>
                            <span class="ws-file-meta">${this._wsHumanSize(f.size)} · ${this._wsTimeSince(f.modified)}</span>
                        </div>`).join('')}
                </div>
            </div>`;
    };

    VeraChat.prototype._renderWsFiles = function() {
        const ws = this._ws;
        if (!ws.fileTree) {
            return `<div class="ws-files-loading">Loading file tree…</div>`;
        }
        return `
            <div class="ws-files-layout">
                <div class="ws-tree-panel">
                    <div class="ws-tree">
                        ${this._renderWsTreeNodes(ws.fileTree, '')}
                    </div>
                </div>
                <div class="ws-preview-panel">
                    ${ws.fileContent ? this._renderWsFilePreview(ws.fileContent) : `
                        <div class="ws-preview-empty">Select a file to preview</div>`}
                </div>
            </div>`;
    };

    VeraChat.prototype._renderWsTreeNodes = function(nodes, parentPath) {
        if (!nodes || !nodes.length) return '';
        const ws = this._ws;
        return nodes.map(node => {
            const fullPath = parentPath ? `${parentPath}/${node.name}` : node.name;
            if (node.type === 'dir') {
                const isExpanded = ws.expandedDirs.has(fullPath);
                return `
                    <div class="ws-tree-dir">
                        <div class="ws-tree-item ws-tree-folder" data-ws-toggle-dir="${this._escQ(fullPath)}">
                            <span class="ws-tree-arrow">${isExpanded ? '▾' : '▸'}</span>
                            <span class="ws-tree-icon">📁</span>
                            <span class="ws-tree-name">${this.escapeHtml(node.name)}</span>
                        </div>
                        ${isExpanded && node.children ? `
                            <div class="ws-tree-children">
                                ${this._renderWsTreeNodes(node.children, fullPath)}
                            </div>` : ''}
                    </div>`;
            }
            const isActive = ws.fileContent && ws.fileContent.path === node.path;
            return `
                <div class="ws-tree-item ws-tree-file ${isActive ? 'ws-tree-active' : ''}"
                     data-ws-open-file="${this._escQ(node.path)}">
                    <span class="ws-tree-icon">${this._wsFileIcon(node.extension)}</span>
                    <span class="ws-tree-name">${this.escapeHtml(node.name)}</span>
                    <span class="ws-tree-size">${this._wsHumanSize(node.size)}</span>
                </div>`;
        }).join('');
    };

    VeraChat.prototype._renderWsFilePreview = function(file) {
        if (file.binary) {
            return `<div class="ws-preview-binary">Binary: ${this.escapeHtml(file.name)} (${this._wsHumanSize(file.size)})</div>`;
        }
        return `
            <div class="ws-preview">
                <div class="ws-preview-header">
                    <span class="ws-preview-name">${this.escapeHtml(file.path)}</span>
                    <span class="ws-preview-size">${this._wsHumanSize(file.size)}${file.truncated ? ' (truncated)' : ''}</span>
                </div>
                <pre class="ws-preview-code"><code>${this.escapeHtml(file.content || '')}</code></pre>
            </div>`;
    };

    VeraChat.prototype._renderWsBoard = function(detail) {
        const board = detail.focus_board;
        if (!board) return `<div class="ws-empty-section">No focus board found</div>`;
        const categories = ['progress','actions','next_steps','ideas','issues'];
        const icons = { progress:'✅', actions:'⚡', next_steps:'➡️', ideas:'💡', issues:'⚠️' };
        return `
            <div class="ws-board">
                ${categories.map(cat => {
                    const items = board[cat] || [];
                    if (!items.length) return '';
                    return `
                        <div class="ws-board-section">
                            <div class="ws-board-cat-header">
                                <span>${icons[cat]||'📌'} ${cat.replace('_', ' ')}</span>
                                <span class="ws-board-count">${items.length}</span>
                            </div>
                            <div class="ws-board-items">
                                ${items.slice(0,8).map(item => {
                                    const text = typeof item === 'string' ? item
                                        : item.note || item.description || JSON.stringify(item).slice(0, 120);
                                    return `<div class="ws-board-item">${this.escapeHtml(String(text).slice(0,200))}</div>`;
                                }).join('')}
                                ${items.length > 8 ? `<div class="ws-board-more">+${items.length-8} more</div>` : ''}
                            </div>
                        </div>`;
                }).join('')}
            </div>`;
    };

    // Workspace data loading
    VeraChat.prototype._wsLoadWorkspaces = async function() {
        const ws = this._ws;
        ws.loading = true;
        this.updateFocusUI();

        try {
            const params = new URLSearchParams({ sort_by: 'last_modified', sort_order: 'desc' });
            if (ws.filter !== 'all') params.append('status', ws.filter);
            const resp = await fetch(`http://llm.int:8888/api/workspaces?${params}`);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            ws.workspaces = await resp.json();
        } catch (err) {
            console.error('WorkspaceTab: load error', err);
            ws.workspaces = [];
        }

        ws.loading = false;
        this.updateFocusUI();
    };

    VeraChat.prototype._wsLoadStats = async function() {
        try {
            const resp = await fetch(`http://llm.int:8888/api/workspaces/stats/summary`);
            if (resp.ok) this._ws.stats = await resp.json();
        } catch (err) { /* non-fatal */ }
        this.updateFocusUI();
    };

    VeraChat.prototype._wsLoadDetail = async function(id) {
        const ws = this._ws;
        if (ws.selectedId === id && ws.selectedDetail) {
            // Toggle off
            ws.selectedId = null;
            ws.selectedDetail = null;
            ws.fileTree = null;
            ws.fileContent = null;
            ws.activePanel = 'overview';
            this.updateFocusUI();
            return;
        }

        ws.selectedId = id;
        ws.selectedDetail = null;
        ws.fileTree = null;
        ws.fileContent = null;
        ws.activePanel = 'overview';
        this.updateFocusUI();

        if (ws.detailCache.has(id)) {
            ws.selectedDetail = ws.detailCache.get(id);
            this.updateFocusUI();
            return;
        }

        try {
            const resp = await fetch(`http://llm.int:8888/api/workspaces/${id}`);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            ws.selectedDetail = await resp.json();
            ws.detailCache.set(id, ws.selectedDetail);
        } catch (err) {
            console.error('WorkspaceTab: detail error', err);
        }
        this.updateFocusUI();
    };

    VeraChat.prototype._wsLoadFileTree = async function(id) {
        this._ws.activePanel = 'files';
        this._ws.fileTree = null;
        this.updateFocusUI();

        try {
            const resp = await fetch(`http://llm.int:8888/api/workspaces/${id}/tree?depth=4`);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            this._ws.fileTree = data.tree;
        } catch (err) {
            console.error('WorkspaceTab: tree error', err);
        }
        this.updateFocusUI();
    };

    VeraChat.prototype._wsLoadFile = async function(id, path) {
        try {
            const resp = await fetch(`http://llm.int:8888/api/workspaces/${id}/file?path=${encodeURIComponent(path)}`);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            this._ws.fileContent = await resp.json();
        } catch (err) {
            console.error('WorkspaceTab: file read error', err);
        }
        this.updateFocusUI();
    };

    VeraChat.prototype._wsCreateWorkspace = async function(name, template) {
        try {
            const resp = await fetch(`http://llm.int:8888/api/workspaces`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, template })
            });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            this.addSystemMessage(`📂 Workspace "${name}" created`);
            this._ws.detailCache.clear();
            await this._wsLoadWorkspaces();
            await this._wsLoadStats();
        } catch (err) {
            console.error('WorkspaceTab: create error', err);
            this.addSystemMessage('Error creating workspace');
        }
    };

    VeraChat.prototype._wsShowCreateDialog = function() {
        const existing = document.getElementById('ws-create-overlay');
        if (existing) existing.remove();

        const overlay = document.createElement('div');
        overlay.id = 'ws-create-overlay';
        overlay.className = 'ws-create-overlay';

        let selectedTemplate = 'empty';
        const templates = [
            { id: 'empty',  icon: '📄', label: 'Empty'  },
            { id: 'python', icon: '🐍', label: 'Python' },
            { id: 'node',   icon: '📦', label: 'Node'   },
        ];

        overlay.innerHTML = `
            <div class="ws-create-modal">
                <h3>📂 Create Workspace</h3>
                <div class="ws-create-field">
                    <label class="ws-create-label">Name</label>
                    <input id="ws-create-name" class="ws-create-input" placeholder="my-project" />
                </div>
                <div class="ws-create-field">
                    <label class="ws-create-label">Template</label>
                    <div class="ws-template-grid">
                        ${templates.map(t => `
                            <div class="ws-template-opt ${t.id === 'empty' ? 'selected' : ''}"
                                 data-tpl="${t.id}">
                                <span class="ws-template-icon">${t.icon}</span>
                                ${t.label}
                            </div>`).join('')}
                    </div>
                </div>
                <div style="display:flex; gap:8px; margin-top:16px;">
                    <button class="ws-btn ws-btn-primary" style="flex:1; padding:8px;" id="ws-create-confirm">✓ Create</button>
                    <button class="ws-btn" style="padding:8px;" id="ws-create-cancel">Cancel</button>
                </div>
            </div>`;

        document.body.appendChild(overlay);

        overlay.querySelectorAll('.ws-template-opt').forEach(opt => {
            opt.addEventListener('click', () => {
                overlay.querySelectorAll('.ws-template-opt').forEach(o => o.classList.remove('selected'));
                opt.classList.add('selected');
                selectedTemplate = opt.dataset.tpl;
            });
        });

        document.getElementById('ws-create-confirm').addEventListener('click', () => {
            const name = document.getElementById('ws-create-name').value.trim();
            if (!name) { alert('Please enter a name'); return; }
            overlay.remove();
            this._wsCreateWorkspace(name, selectedTemplate);
        });

        document.getElementById('ws-create-cancel').addEventListener('click', () => overlay.remove());
        overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });

        setTimeout(() => document.getElementById('ws-create-name').focus(), 100);
    };

    // Initialize workspace browser when tab renders
    VeraChat.prototype._initWorkspaceBrowser = function() {
        if (this.currentFocusTab !== 'workspace') return;

        if (!this._ws.workspaces.length && !this._ws.loading) {
            this._wsLoadWorkspaces();
            this._wsLoadStats();
        }

        const container = document.getElementById('tab-focus');
        if (!container) return;

        if (container._wsListenerAttached) return;
        container._wsListenerAttached = true;

        container.addEventListener('click', (e) => {
            if (this.currentFocusTab !== 'workspace') return;

            const t = e.target.closest('[data-ws-select]');
            if (t) { this._wsLoadDetail(t.dataset.wsSelect); return; }

            const fp = e.target.closest('[data-ws-filter]');
            if (fp) {
                this._ws.filter = fp.dataset.wsFilter;
                this._wsLoadWorkspaces();
                return;
            }

            const panel = e.target.closest('[data-ws-panel]');
            if (panel) {
                const p = panel.dataset.wsPanel;
                if (p === 'files' && !this._ws.fileTree) {
                    this._wsLoadFileTree(this._ws.selectedId);
                } else {
                    this._ws.activePanel = p;
                    this.updateFocusUI();
                }
                return;
            }

            const toggleDir = e.target.closest('[data-ws-toggle-dir]');
            if (toggleDir) {
                const path = toggleDir.dataset.wsToggleDir;
                const expanded = new Set(this._ws.expandedDirs);
                if (expanded.has(path)) expanded.delete(path); else expanded.add(path);
                this._ws.expandedDirs = expanded;
                this.updateFocusUI();
                return;
            }

            const openFile = e.target.closest('[data-ws-open-file]');
            if (openFile) {
                this._wsLoadFile(this._ws.selectedId, openFile.dataset.wsOpenFile);
                return;
            }

            if (e.target.id === 'ws-refresh-btn') {
                this._ws.detailCache.clear();
                this._wsLoadWorkspaces();
                this._wsLoadStats();
                return;
            }
            if (e.target.id === 'ws-create-btn') {
                this._wsShowCreateDialog();
                return;
            }
        });

        const searchInput = container.querySelector('#ws-search-input');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this._ws.searchQuery = e.target.value;
                this.updateFocusUI();
            });
        }
    };

    // ============================================================
    // WORKSPACE UTILITIES
    // ============================================================

    VeraChat.prototype._wsHumanSize = function(bytes) {
        if (!bytes) return '0 B';
        const units = ['B','KB','MB','GB'];
        let i = 0, s = bytes;
        while (s >= 1024 && i < units.length - 1) { s /= 1024; i++; }
        return `${s.toFixed(i > 0 ? 1 : 0)} ${units[i]}`;
    };

    VeraChat.prototype._wsTimeSince = function(iso) {
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
    };

    VeraChat.prototype._wsFileIcon = function(ext) {
        const icons = {
            '.py':'🐍', '.js':'📜', '.ts':'📘', '.jsx':'⚛️', '.tsx':'⚛️',
            '.json':'📋', '.yaml':'📋', '.yml':'📋', '.md':'📝',
            '.html':'🌐', '.css':'🎨', '.sh':'🖥️', '.sql':'🗃️',
            '.rs':'🦀', '.go':'🔵', '.java':'☕', '.rb':'💎',
            '.txt':'📄', '.log':'📄', '.env':'🔒', '.toml':'⚙️',
        };
        return icons[ext] || '📄';
    };

})();