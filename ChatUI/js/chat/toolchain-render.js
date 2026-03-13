// =====================================================================
// Toolchain Flowchart — v4
// Fixes vs v3:
//   1. Adaptive INPUT: a second regex captures the separate
//      "[Adaptive] Input: ..." line and patches the already-rendered node.
//   2. Adaptive OUTPUT: a live output preview is shown directly on the
//      flow node so it's visible without opening the detail panel.
//      The detail panel output div is also unhidden as soon as the first
//      chunk arrives (not waiting for step_started to fire).
//   3. step_input_updated event added so the monitor can push the
//      resolved input after step_discovered fires.
// =====================================================================

(() => {
    console.log('🔧 Loading Toolchain Flowchart (v4 — adaptive input+output fix)...');

    // =====================================================================
    // Wrap handleToolchainEvent
    // =====================================================================

    if (!VeraChat.prototype._originalHandleToolchainEvent) {
        VeraChat.prototype._originalHandleToolchainEvent = VeraChat.prototype.handleToolchainEvent;
    }

    VeraChat.prototype.handleToolchainEvent = function(data) {
        if (this._originalHandleToolchainEvent) {
            this._originalHandleToolchainEvent.call(this, data);
        }
        this.updateFlowchart(data);
    };

    // =====================================================================
    // Per-execution state
    // =====================================================================

    VeraChat.prototype._fcState = VeraChat.prototype._fcState || {};

    function getState(self, execId) {
        if (!self._fcState[execId]) {
            self._fcState[execId] = {
                mode:          'sequential',
                plan:          [],
                discovered:    new Set(),
                branches:      null,
                branchApplied: false,
                stepCount:     0,
            };
        }
        return self._fcState[execId];
    }

    // =====================================================================
    // Master dispatcher
    // =====================================================================

    VeraChat.prototype.updateFlowchart = function(data) {
        if (!this.currentExecution) return;
        const execId = this.currentExecution.execution_id;
        const st     = getState(this, execId);
        const mode   = (data.data && data.data.mode) || st.mode;

        switch (data.type) {

            case 'plan': {
                st.mode = mode;
                st.plan = data.data.plan || [];
                if (mode !== 'adaptive') {
                    this.injectFlowchart(execId, st.plan, mode);
                }
                break;
            }

            case 'step_discovered': {
                st.mode = 'adaptive';
                const stepNum = data.data.step_number;
                if (st.discovered.has(stepNum)) break;
                st.discovered.add(stepNum);
                st.stepCount++;

                const stepDef = {
                    tool:  data.data.tool_name || 'unknown',
                    input: data.data.input     || '',
                };
                st.plan.push(stepDef);

                if (!document.getElementById(`flowchart-${execId}`)) {
                    this.injectAdaptiveShell(execId);
                }
                this.appendAdaptiveStep(execId, stepNum, stepDef);
                break;
            }

            // ★ NEW: monitor sends this after resolving the real input
            case 'step_input_updated': {
                const idx   = data.data.step_number - 1;
                const input = data.data.input;
                this.updateStepInput(execId, idx, input);
                break;
            }

            case 'parallel_branches': {
                st.mode     = 'parallel';
                st.branches = data.data.branches;
                if (!st.branchApplied && document.getElementById(`flowchart-${execId}`)) {
                    this.applyParallelLayout(execId, st.branches, st.plan);
                    st.branchApplied = true;
                } else if (!st.branchApplied) {
                    st._pendingBranches = true;
                }
                break;
            }

            case 'step_started': {
                const idx = data.data.step_number - 1;
                this.updateStepStatus(execId, idx, 'running');
                break;
            }

            case 'step_output': {
                const idx = data.data.step_number - 1;
                this.appendStepOutput(execId, idx, data.data.chunk);
                break;
            }

            case 'step_completed': {
                const idx = data.data.step_number - 1;
                this.updateStepStatus(execId, idx, 'completed');
                // Freeze the live preview text on the node
                this._freezeNodePreview(execId, idx);
                break;
            }

            case 'step_failed': {
                const idx = data.data.step_number - 1;
                this.updateStepStatus(execId, idx, 'failed');
                if (data.data.error) {
                    this.setStepError(execId, idx, data.data.error);
                }
                break;
            }

            case 'execution_completed':
                this.updateGlobalStatus(execId, 'completed');
                break;
            case 'execution_failed':
                this.updateGlobalStatus(execId, 'failed');
                break;
        }
    };

    // =====================================================================
    // Sequential injection
    // =====================================================================

    VeraChat.prototype.injectFlowchart = function(execId, plan, mode) {
        if (!plan || plan.length === 0) return;
        if (document.getElementById(`flowchart-${execId}`)) return;

        const html = this.buildFlowchartHTML(execId, plan, mode || 'sequential');
        const contentDiv = this._getContentDiv();
        if (!contentDiv) return;

        contentDiv.insertAdjacentHTML('beforeend', '\n\n' + html);
        console.log(`✅ Flowchart injected [${mode}] — ${plan.length} steps`);

        const st = getState(this, execId);
        if (st._pendingBranches && st.branches) {
            this.applyParallelLayout(execId, st.branches, plan);
            st.branchApplied = true;
        }
    };

    // =====================================================================
    // Adaptive shell
    // =====================================================================

    VeraChat.prototype.injectAdaptiveShell = function(execId) {
        if (document.getElementById(`flowchart-${execId}`)) return;

        const html = `
            <div class="toolchain-flowchart-widget fc-adaptive" id="flowchart-${execId}">
                <div class="flowchart-header">
                    <span class="flowchart-icon">🤖</span>
                    <span class="flowchart-title">Adaptive Toolchain</span>
                    <span class="flowchart-count" id="count-${execId}">discovering…</span>
                    <span class="flowchart-status fc-status-adaptive" id="global-status-${execId}">ADAPTIVE</span>
                </div>
                <div class="flowchart-body">
                    <div class="flow-nodes" id="nodes-${execId}">
                        <div class="flow-row">
                            <div class="flow-node flow-start">Start</div>
                        </div>
                        <div class="flow-row" id="start-arrow-${execId}">
                            <div class="flow-arrow flow-arrow-pulse">↓</div>
                        </div>
                        <div class="flow-row" id="end-row-${execId}" style="display:none">
                            <div class="flow-node flow-end">Complete</div>
                        </div>
                    </div>
                </div>
                <div class="flowchart-details" id="details-panel-${execId}">
                    <button class="flowchart-toggle-btn"
                            onclick="this.parentElement.classList.toggle('expanded')">
                        <span class="toggle-icon">▼</span> Step Details
                    </button>
                    <div class="flowchart-details-content">
                        <div class="step-details-list" id="detail-list-${execId}"></div>
                    </div>
                </div>
            </div>`;

        const contentDiv = this._getContentDiv();
        if (!contentDiv) return;
        contentDiv.insertAdjacentHTML('beforeend', '\n\n' + html);
        console.log('✅ Adaptive flowchart shell injected');
    };

    // =====================================================================
    // Append a single adaptive step node
    // =====================================================================

    VeraChat.prototype.appendAdaptiveStep = function(execId, stepNum, stepDef) {
        const nodesEl      = document.getElementById(`nodes-${execId}`);
        const endRowEl     = document.getElementById(`end-row-${execId}`);
        const detailListEl = document.getElementById(`detail-list-${execId}`);
        const countEl      = document.getElementById(`count-${execId}`);
        if (!nodesEl) return;

        const arrayIndex   = stepNum - 1;
        const toolName     = this.escapeHtml(stepDef.tool || 'unknown');
        const inputPreview = this._inputPreview(stepDef.input);
        const inputDisplay = this._inputDisplay(stepDef.input);

        // ── Flow node ──────────────────────────────────────────────────
        const nodeHtml = `
            <div class="flow-row fc-adaptive-row" id="row-${execId}-${arrayIndex}"
                 style="animation: nodeSlideIn 0.35s ease forwards">
                <div class="flow-node flow-step"
                     id="step-node-${execId}-${arrayIndex}"
                     data-step="${arrayIndex}"
                     data-status="pending">
                    <div class="step-number">Step ${stepNum}</div>
                    <div class="step-tool">${toolName}</div>
                    <div class="step-input-preview" id="node-input-${execId}-${arrayIndex}">${inputPreview}</div>
                    <div class="step-status" id="status-${execId}-${arrayIndex}">
                        <span class="status-icon">🔍</span>
                        <span class="status-text">Discovered</span>
                    </div>
                    <!-- ★ Live output preview shown directly on the node -->
                    <div class="node-output-preview" id="node-output-${execId}-${arrayIndex}" style="display:none">
                        <div class="node-output-label">Output</div>
                        <pre class="node-output-pre"></pre>
                    </div>
                </div>
            </div>
            <div class="flow-row fc-adaptive-arrow-row" id="arrow-${execId}-${arrayIndex}">
                <div class="flow-arrow flow-arrow-pulse">↓</div>
            </div>`;

        if (endRowEl) {
            endRowEl.insertAdjacentHTML('beforebegin', nodeHtml);
        } else {
            nodesEl.insertAdjacentHTML('beforeend', nodeHtml);
        }

        // ── Detail panel entry ─────────────────────────────────────────
        if (detailListEl) {
            const detailHtml = `
                <div class="step-detail" id="detail-${execId}-${arrayIndex}">
                    <div class="detail-header">
                        <span class="detail-number">Step ${stepNum}</span>
                        <span class="detail-tool">${toolName}</span>
                        <span class="detail-badge detail-badge-adaptive">adaptive</span>
                    </div>
                    <div class="detail-input" id="detail-input-${execId}-${arrayIndex}">
                        <strong>Input:</strong>
                        <pre id="detail-input-pre-${execId}-${arrayIndex}">${this.escapeHtml(inputDisplay)}</pre>
                    </div>
                    <div class="detail-output" id="output-${execId}-${arrayIndex}" style="display:none">
                        <strong>Output:</strong>
                        <pre class="output-pre"></pre>
                    </div>
                    <div class="detail-error" id="error-${execId}-${arrayIndex}" style="display:none">
                        <strong>Error:</strong>
                        <pre class="error-pre"></pre>
                    </div>
                </div>`;
            detailListEl.insertAdjacentHTML('beforeend', detailHtml);
        }

        if (countEl) countEl.textContent = `${stepNum} step${stepNum !== 1 ? 's' : ''}`;

        const startArrow = document.getElementById(`start-arrow-${execId}`);
        if (startArrow) startArrow.querySelector('.flow-arrow').classList.remove('flow-arrow-pulse');

        console.log(`🔍 Adaptive step ${stepNum} (${stepDef.tool}) appended`);
    };

    // =====================================================================
    // ★ NEW: patch the input on a node AFTER step_discovered
    //   Called when step_input_updated arrives (monitor sends resolved input)
    // =====================================================================

    VeraChat.prototype.updateStepInput = function(execId, stepIndex, input) {
        // Update the node's input preview chip
        const nodeInputEl = document.getElementById(`node-input-${execId}-${stepIndex}`);
        if (nodeInputEl) {
            nodeInputEl.textContent = this._inputPreview(input);
        }
        // Update the detail panel pre block
        const detailInputPre = document.getElementById(`detail-input-pre-${execId}-${stepIndex}`);
        if (detailInputPre) {
            detailInputPre.textContent = this._inputDisplay(input);
        }
    };

    // =====================================================================
    // appendStepOutput  ★ now also writes to the live node preview
    // =====================================================================

    VeraChat.prototype.appendStepOutput = function(execId, stepIndex, chunk) {
        // ── Detail panel output (existing) ────────────────────────────
        const outputSection = document.getElementById(`output-${execId}-${stepIndex}`);
        if (outputSection) {
            // Unhide as soon as first chunk arrives — don't wait for step_started
            outputSection.style.display = 'block';
            const outputPre = outputSection.querySelector('.output-pre');
            if (outputPre) {
                outputPre.textContent += chunk;
                outputPre.scrollTop   = outputPre.scrollHeight;
            }
        }

        // ── ★ Live node preview ────────────────────────────────────────
        const nodeOutput = document.getElementById(`node-output-${execId}-${stepIndex}`);
        if (nodeOutput) {
            nodeOutput.style.display = 'block';
            const pre = nodeOutput.querySelector('.node-output-pre');
            if (pre) {
                pre.textContent += chunk;
                // Trim to last 300 chars so the node doesn't grow unbounded
                if (pre.textContent.length > 300) {
                    pre.textContent = '…' + pre.textContent.slice(-280);
                }
            }
        }
    };

    // =====================================================================
    // ★ Freeze node preview on completion (swap live pre for a clean summary)
    // =====================================================================

    VeraChat.prototype._freezeNodePreview = function(execId, stepIndex) {
        const nodeOutput = document.getElementById(`node-output-${execId}-${stepIndex}`);
        if (!nodeOutput) return;
        const pre = nodeOutput.querySelector('.node-output-pre');
        if (!pre || !pre.textContent) return;
        // Add a "done" CSS class so we can dim the pulsing border
        nodeOutput.classList.add('node-output-done');
    };

    // =====================================================================
    // Parallel layout
    // =====================================================================

    VeraChat.prototype.applyParallelLayout = function(execId, branches, plan) {
        const nodesEl = document.getElementById(`nodes-${execId}`);
        if (!nodesEl) return;

        const countEl = document.getElementById(`count-${execId}`);
        if (countEl) countEl.textContent = `${plan.length} steps · ${branches.length} branches`;

        const statusEl = document.getElementById(`global-status-${execId}`);
        if (statusEl) {
            statusEl.textContent = 'PARALLEL';
            statusEl.className   = 'flowchart-status fc-status-parallel';
        }

        let lanesHtml = `
            <div class="flow-row">
                <div class="flow-node flow-start">Start</div>
            </div>
            <div class="flow-row"><div class="flow-arrow">↓</div></div>
            <div class="flow-parallel-container">`;

        branches.forEach((branchSteps, bi) => {
            lanesHtml += `<div class="flow-lane">
                <div class="flow-lane-header">Branch ${bi + 1}</div>`;
            branchSteps.forEach((sn, pos) => {
                const arrayIndex   = sn - 1;
                const step         = plan[arrayIndex] || {};
                const toolName     = this.escapeHtml(step.tool || 'unknown');
                const inputPreview = this._inputPreview(step.input || '');
                lanesHtml += `
                    <div class="flow-node flow-step"
                         id="step-node-${execId}-${arrayIndex}"
                         data-step="${arrayIndex}"
                         data-status="pending">
                        <div class="step-number">Step ${sn}</div>
                        <div class="step-tool">${toolName}</div>
                        <div class="step-input-preview" id="node-input-${execId}-${arrayIndex}">${inputPreview}</div>
                        <div class="step-status" id="status-${execId}-${arrayIndex}">
                            <span class="status-icon">⏸️</span>
                            <span class="status-text">Pending</span>
                        </div>
                        <div class="node-output-preview" id="node-output-${execId}-${arrayIndex}" style="display:none">
                            <div class="node-output-label">Output</div>
                            <pre class="node-output-pre"></pre>
                        </div>
                    </div>`;
                if (pos < branchSteps.length - 1) {
                    lanesHtml += `<div class="flow-arrow">↓</div>`;
                }
            });
            lanesHtml += `</div>`;
        });

        lanesHtml += `</div>
            <div class="flow-row"><div class="flow-arrow">↓</div></div>
            <div class="flow-row"><div class="flow-node flow-end">Complete</div></div>`;

        nodesEl.innerHTML = lanesHtml;
        console.log(`✅ Parallel layout applied — ${branches.length} branches`);
    };

    // =====================================================================
    // Sequential flowchart HTML builder  ★ adds node-output-preview divs
    // =====================================================================

    VeraChat.prototype.buildFlowchartHTML = function(execId, plan, mode) {
        const modeBadgeLabel = {
            sequential: 'SEQUENTIAL', expert: 'EXPERT',
            hybrid: 'HYBRID', parallel: 'PARALLEL',
        }[mode] || 'EXECUTING';

        const modeStatusClass = {
            sequential: 'fc-status-sequential', expert: 'fc-status-expert',
            hybrid: 'fc-status-hybrid', parallel: 'fc-status-parallel',
        }[mode] || 'fc-status-sequential';

        const modeIcon = { sequential: '🔧', expert: '🎓', hybrid: '⚡', parallel: '⚙️' }[mode] || '🔧';

        const stepsHtml = plan.map((step, index) => {
            const toolName     = this.escapeHtml(step.tool || 'unknown');
            const inputPreview = this._inputPreview(step.input);
            return `
                <div class="flow-row">
                    <div class="flow-node flow-step"
                         id="step-node-${execId}-${index}"
                         data-step="${index}"
                         data-status="pending">
                        <div class="step-number">Step ${index + 1}</div>
                        <div class="step-tool">${toolName}</div>
                        <div class="step-input-preview" id="node-input-${execId}-${index}">${inputPreview}</div>
                        <div class="step-status" id="status-${execId}-${index}">
                            <span class="status-icon">⏸️</span>
                            <span class="status-text">Pending</span>
                        </div>
                        <!-- ★ Live output preview on the node -->
                        <div class="node-output-preview" id="node-output-${execId}-${index}" style="display:none">
                            <div class="node-output-label">Output</div>
                            <pre class="node-output-pre"></pre>
                        </div>
                    </div>
                </div>
                ${index < plan.length - 1
                    ? `<div class="flow-row"><div class="flow-arrow">↓</div></div>`
                    : ''}`;
        }).join('');

        const detailsHtml = plan.map((step, index) => {
            const toolName    = this.escapeHtml(step.tool || 'unknown');
            const inputDisplay = this._inputDisplay(step.input);
            return `
                <div class="step-detail" id="detail-${execId}-${index}">
                    <div class="detail-header">
                        <span class="detail-number">Step ${index + 1}</span>
                        <span class="detail-tool">${toolName}</span>
                    </div>
                    <div class="detail-input">
                        <strong>Input:</strong>
                        <pre id="detail-input-pre-${execId}-${index}">${this.escapeHtml(inputDisplay)}</pre>
                    </div>
                    <div class="detail-output" id="output-${execId}-${index}" style="display:none">
                        <strong>Output:</strong>
                        <pre class="output-pre"></pre>
                    </div>
                    <div class="detail-error" id="error-${execId}-${index}" style="display:none">
                        <strong>Error:</strong>
                        <pre class="error-pre"></pre>
                    </div>
                </div>`;
        }).join('');

        return `
            <div class="toolchain-flowchart-widget" id="flowchart-${execId}">
                <div class="flowchart-header">
                    <span class="flowchart-icon">${modeIcon}</span>
                    <span class="flowchart-title">Toolchain Execution</span>
                    <span class="flowchart-count" id="count-${execId}">${plan.length} steps</span>
                    <span class="flowchart-status ${modeStatusClass}"
                          id="global-status-${execId}">${modeBadgeLabel}</span>
                </div>
                <div class="flowchart-body">
                    <div class="flow-nodes" id="nodes-${execId}">
                        <div class="flow-row">
                            <div class="flow-node flow-start">Start</div>
                        </div>
                        <div class="flow-row"><div class="flow-arrow">↓</div></div>
                        ${stepsHtml}
                        <div class="flow-row"><div class="flow-arrow">↓</div></div>
                        <div class="flow-row">
                            <div class="flow-node flow-end">Complete</div>
                        </div>
                    </div>
                </div>
                <div class="flowchart-details">
                    <button class="flowchart-toggle-btn"
                            onclick="this.parentElement.classList.toggle('expanded')">
                        <span class="toggle-icon">▼</span> Step Details
                    </button>
                    <div class="flowchart-details-content">
                        <div class="step-details-list" id="detail-list-${execId}">
                            ${detailsHtml}
                        </div>
                    </div>
                </div>
            </div>`;
    };

    // =====================================================================
    // updateStepStatus  (output section unhidden here for step_started too)
    // =====================================================================

    VeraChat.prototype.updateStepStatus = function(execId, stepIndex, status) {
        const stepNode = document.getElementById(`step-node-${execId}-${stepIndex}`);
        if (!stepNode) {
            console.warn(`⚠️ Step node not found: step-node-${execId}-${stepIndex}`);
            return;
        }
        stepNode.dataset.status = status;

        const statusEl = document.getElementById(`status-${execId}-${stepIndex}`);
        if (statusEl) {
            const cfg = {
                pending:   { icon: '⏸️', text: 'Pending' },
                running:   { icon: '⏳', text: 'Running' },
                completed: { icon: '✅', text: 'Done' },
                failed:    { icon: '❌', text: 'Failed' },
            }[status] || { icon: '⏸️', text: 'Pending' };
            statusEl.innerHTML = `
                <span class="status-icon">${cfg.icon}</span>
                <span class="status-text">${cfg.text}</span>`;
        }

        // Unhide detail-panel output section on running or completed
        if (status === 'running' || status === 'completed') {
            const outputSection = document.getElementById(`output-${execId}-${stepIndex}`);
            if (outputSection) outputSection.style.display = 'block';
        }

        if (status === 'completed' || status === 'failed') {
            const st = getState(this, execId);
            if (st && st.mode === 'adaptive') {
                const globalStatus = document.getElementById(`global-status-${execId}`);
                if (globalStatus && globalStatus.textContent === 'COMPLETED') {
                    this._showEndNode(execId);
                }
            }
        }
    };

    VeraChat.prototype.setStepError = function(execId, stepIndex, error) {
        const errorSection = document.getElementById(`error-${execId}-${stepIndex}`);
        if (errorSection) {
            errorSection.style.display = 'block';
            const errorPre = errorSection.querySelector('.error-pre');
            if (errorPre) errorPre.textContent = error;
        }
    };

    VeraChat.prototype.updateGlobalStatus = function(execId, status) {
        const statusEl = document.getElementById(`global-status-${execId}`);
        if (statusEl) {
            statusEl.textContent = status.toUpperCase();
            statusEl.className   = `flowchart-status status-${status}`;
        }
        if (status === 'completed') this._showEndNode(execId);
    };

    VeraChat.prototype._showEndNode = function(execId) {
        const endRow = document.getElementById(`end-row-${execId}`);
        if (endRow) {
            endRow.style.display = '';
            endRow.style.animation = 'nodeSlideIn 0.35s ease forwards';
        }
        const adaptiveArrows = document.querySelectorAll(`#nodes-${execId} .fc-adaptive-arrow-row`);
        const last = adaptiveArrows[adaptiveArrows.length - 1];
        if (last) last.remove();
    };

    // =====================================================================
    // Helper — find current assistant message content div
    // =====================================================================

    VeraChat.prototype._getContentDiv = function() {
        const messages = document.querySelectorAll('.message.assistant');
        if (!messages.length) return null;
        const last = messages[messages.length - 1];
        return (
            last.querySelector('.message-content') ||
            last.querySelector('.content') ||
            last.querySelector('[class*="content"]')
        );
    };

    // =====================================================================
    // Input formatting helpers
    // =====================================================================

    VeraChat.prototype._inputPreview = function(input) {
        if (typeof input === 'object' && input !== null) {
            const entries = Object.entries(input);
            if (!entries.length)    return '{}';
            if (entries.length === 1) {
                const [k, v] = entries[0];
                return this.escapeHtml(`${k}: ${this.truncate(String(v), 40)}`);
            }
            return `{${entries.length} params}`;
        }
        return this.escapeHtml(this.truncate(String(input || ''), 50));
    };

    VeraChat.prototype._inputDisplay = function(input) {
        if (typeof input === 'object' && input !== null) {
            return JSON.stringify(input, null, 2);
        }
        return String(input || '');
    };

    VeraChat.prototype.truncate = function(text, maxLen) {
        if (!text) return '';
        text = String(text);
        return text.length <= maxLen ? text : text.substring(0, maxLen) + '…';
    };

    VeraChat.prototype.escapeHtml = VeraChat.prototype.escapeHtml || function(str) {
        const div = document.createElement('div');
        div.appendChild(document.createTextNode(str));
        return div.innerHTML;
    };

    // =====================================================================
    // Styles  (adds node-output-preview styles)
    // =====================================================================

    const styles = `
    /* ── Base widget ─────────────────────────────────────────────────── */
    .toolchain-flowchart-widget {
        margin: 16px 0;
        background: var(--panel-bg, #1e293b);
        border: 2px solid var(--accent, #3b82f6);
        border-radius: 8px;
        overflow: hidden;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }

    /* ── Header ──────────────────────────────────────────────────────── */
    .flowchart-header {
        display: flex; align-items: center; gap: 12px;
        padding: 12px 16px;
        background: linear-gradient(135deg, var(--panel-bg, #3b82f6), var(--bg));
        color: white;
    }
    .flowchart-icon  { font-size: 20px; }
    .flowchart-title { font-size: 15px; font-weight: 600; flex: 1; }
    .flowchart-count { font-size: 12px; padding: 4px 10px; background: rgba(255,255,255,.2); border-radius: 12px; font-weight: 500; }
    .flowchart-status {
        font-size: 11px; padding: 4px 10px; border-radius: 12px;
        font-weight: 600; text-transform: uppercase;
    }
    .fc-status-sequential { background: rgba(59,130,246,.35); }
    .fc-status-adaptive   { background: rgba(16,185,129,.35); animation: pulse 2s infinite; }
    .fc-status-parallel   { background: rgba(168,85,247,.35); }
    .fc-status-expert     { background: rgba(245,158,11,.35); }
    .fc-status-hybrid     { background: rgba(239,68,68,.35); }
    .status-completed     { background: rgba(16,185,129,.3); }
    .status-failed        { background: rgba(239,68,68,.3); }

    @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.55} }

    /* ── Body ────────────────────────────────────────────────────────── */
    .flowchart-body {
        padding: 24px 16px;
        background: var(--bg, #0f172a);
        overflow-x: auto;
    }
    .flow-nodes {
        display: flex; flex-direction: column;
        align-items: center; gap: 0; min-width: 0;
    }
    .flow-row { display: flex; justify-content: center; width: 100%; }

    /* ── Nodes ───────────────────────────────────────────────────────── */
    .flow-node {
        padding: 12px 20px; border-radius: 8px; text-align: center;
        font-size: 14px; box-shadow: 0 2px 8px rgba(0,0,0,.3);
        min-width: 200px; max-width: 560px; transition: all .3s;
    }
    .flow-start, .flow-end {
        background: linear-gradient(135deg,#10b981,#059669);
        color: white; padding: 10px 24px; border-radius: 20px;
        font-weight: 600; min-width: 120px;
    }
    .flow-step {
        background: var(--panel-bg, #1e293b);
        border: 2px solid #64748b;
        color: var(--text, #e2e8f0);
    }
    .flow-step[data-status="pending"]   { border-color:#64748b; opacity:.7; }
    .flow-step[data-status="running"]   {
        border-color:#3b82f6;
        box-shadow:0 0 20px rgba(59,130,246,.5);
        animation:pulse-border 1.5s infinite;
    }
    .flow-step[data-status="completed"] {
        border-color:#10b981;
        background:linear-gradient(135deg,#1e293b,#064e3b);
    }
    .flow-step[data-status="failed"]    {
        border-color:#ef4444;
        background:linear-gradient(135deg,#1e293b,#7f1d1d);
    }

    @keyframes pulse-border {
        0%,100% { box-shadow:0 0 20px rgba(59,130,246,.5); }
        50%      { box-shadow:0 0 30px rgba(59,130,246,.8); }
    }

    .step-number       { font-size:10px; text-transform:uppercase; color:var(--accent,#3b82f6); font-weight:600; margin-bottom:4px; }
    .step-tool         { font-size:16px; font-weight:600; margin-bottom:6px; font-family:monospace; }
    .step-input-preview { font-size:12px; color:var(--text-muted,#94a3b8); margin-bottom:8px; }
    .step-status       { font-size:11px; padding:4px 8px; background:rgba(0,0,0,.3); border-radius:4px; display:inline-flex; align-items:center; gap:4px; }
    .status-icon       { font-size:13px; }
    .status-text       { font-weight:500; }

    /* ── ★ Node live output preview ──────────────────────────────────── */
    .node-output-preview {
        margin-top: 10px;
        border-top: 1px solid rgba(255,255,255,.1);
        padding-top: 8px;
        text-align: left;
    }
    .node-output-label {
        font-size: 10px;
        text-transform: uppercase;
        color: #10b981;
        font-weight: 600;
        margin-bottom: 4px;
        letter-spacing: .04em;
    }
    .node-output-pre {
        margin: 0;
        font-family: monospace;
        font-size: 11px;
        color: #a7f3d0;
        white-space: pre-wrap;
        word-break: break-all;
        max-height: 80px;
        overflow-y: auto;
        background: rgba(0,0,0,.25);
        padding: 6px 8px;
        border-radius: 4px;
        border-left: 2px solid #10b981;
    }
    .node-output-done .node-output-pre {
        border-left-color: #059669;
        color: #6ee7b7;
    }

    /* ── Arrows ──────────────────────────────────────────────────────── */
    .flow-arrow { color:var(--accent,#3b82f6); font-size:24px; line-height:1; padding:4px 0; font-weight:bold; }
    .flow-arrow-pulse { animation:pulse 1.4s infinite; }

    @keyframes nodeSlideIn {
        from { opacity:0; transform:translateY(-12px); }
        to   { opacity:1; transform:translateY(0); }
    }

    /* ── Parallel swim-lanes ─────────────────────────────────────────── */
    .flow-parallel-container {
        display: flex; flex-direction: row; gap: 16px;
        justify-content: center; align-items: flex-start;
        width: 100%; padding: 8px 0; overflow-x: auto;
    }
    .flow-lane {
        display: flex; flex-direction: column; align-items: center;
        gap: 0; flex: 1; min-width: 160px; max-width: 260px;
        background: rgba(168,85,247,.06);
        border: 1px solid rgba(168,85,247,.25);
        border-radius: 8px; padding: 12px 8px;
    }
    .flow-lane-header {
        font-size: 11px; font-weight: 700; text-transform: uppercase;
        color: rgba(168,85,247,.9); letter-spacing: .06em; margin-bottom: 10px;
    }
    .flow-lane .flow-node { min-width: 140px; max-width: 240px; width: 100%; }
    .flow-lane .flow-arrow { font-size: 18px; }

    /* ── Detail panel ────────────────────────────────────────────────── */
    .flowchart-details        { border-top:1px solid var(--border,#334155); background:var(--panel-bg,#1e293b); }
    .flowchart-toggle-btn     {
        width:100%; padding:12px 16px; background:transparent; border:none;
        color:var(--text,#e2e8f0); cursor:pointer; font-size:13px; font-weight:500;
        display:flex; align-items:center; gap:8px; transition:background .2s; text-align:left;
    }
    .flowchart-toggle-btn:hover { background:var(--bg,#0f172a); }
    .toggle-icon { transition:transform .2s; }
    .flowchart-details.expanded .toggle-icon { transform:rotate(180deg); }
    .flowchart-details-content { max-height:0; overflow:hidden; transition:max-height .3s ease; }
    .flowchart-details.expanded .flowchart-details-content { max-height:3000px; padding:16px; }

    .step-details-list { display:flex; flex-direction:column; gap:12px; }
    .step-detail {
        padding:12px; background:var(--bg,#0f172a);
        border:1px solid var(--border,#334155); border-radius:6px;
    }
    .detail-header { display:flex; align-items:center; gap:12px; margin-bottom:8px; }
    .detail-number {
        font-size:11px; font-weight:600; padding:3px 8px;
        background:var(--accent,#3b82f6); color:white;
        border-radius:4px; text-transform:uppercase;
    }
    .detail-tool  { font-size:14px; font-weight:600; font-family:monospace; }
    .detail-badge {
        font-size:10px; font-weight:700; padding:2px 7px;
        border-radius:10px; text-transform:uppercase; letter-spacing:.04em;
    }
    .detail-badge-adaptive { background:rgba(16,185,129,.25); color:#10b981; }

    .detail-input strong,
    .detail-output strong,
    .detail-error strong { color:var(--text,#e2e8f0); font-size:12px; text-transform:uppercase; display:block; margin-bottom:6px; }

    .detail-input pre,
    .detail-output pre,
    .detail-error pre {
        margin:0; padding:8px 12px;
        background:var(--panel-bg,#1e293b);
        border:1px solid var(--border,#334155);
        border-radius:4px; font-family:monospace; font-size:12px;
        white-space:pre-wrap; word-wrap:break-word;
        max-height:200px; overflow-y:auto; overflow-x:auto; max-width:100%;
    }
    .detail-output { margin-top:12px; padding-top:12px; border-top:1px solid var(--border,#334155); }
    .output-pre    { color:#10b981; border-left:3px solid #10b981; }
    .detail-error  { margin-top:12px; padding-top:12px; border-top:1px solid var(--border,#334155); }
    .error-pre     { color:#ef4444; border-left:3px solid #ef4444; background:rgba(239,68,68,.1); }

    @media (max-width:768px) {
        .flow-node { min-width:140px; max-width:92%; }
        .flow-lane { min-width:130px; }
    }
    `;

    if (!document.getElementById('toolchain-flowchart-styles')) {
        const style = document.createElement('style');
        style.id          = 'toolchain-flowchart-styles';
        style.textContent = styles;
        document.head.appendChild(style);
    }

    console.log('✅ Toolchain Flowchart v4 loaded');
    console.log('   adaptive input+output fix applied');
})();