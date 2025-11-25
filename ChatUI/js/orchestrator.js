(() => {
    // ========================================================================
    // ORCHESTRATOR STATE
    // ========================================================================
    
    VeraChat.prototype.orchestratorState = {
        currentPanel: 'dashboard',
        apiUrl: 'http://llm.int:8888/orchestrator',
        updateInterval: null,
        ws: null,
        chartData: {
            cpu: [],
            memory: [],
            queue: []
        },
        maxDataPoints: 60
    };

    // ========================================================================
    // INITIALIZATION
    // ========================================================================
    
    VeraChat.prototype.initOrchestrator = async function() {
        console.log('Initializing orchestrator UI...');
        
        // Setup WebSocket
        this.setupOrchestratorWebSocket();
        
        // Start periodic updates
        this.startOrchestratorUpdates();
        
        // Initial load
        await this.refreshOrchestrator();
    };

    // ========================================================================
    // WEBSOCKET MANAGEMENT
    // ========================================================================
    
    VeraChat.prototype.setupOrchestratorWebSocket = function() {
        const wsUrl = this.orchestratorState.apiUrl.replace('http', 'ws') + '/ws/updates';
        
        try {
            this.orchestratorState.ws = new WebSocket(wsUrl);
            
            this.orchestratorState.ws.onopen = () => {
                console.log('Orchestrator WebSocket connected');
                this.addSystemMessage('Orchestrator WebSocket connected', 'success');
            };
            
            this.orchestratorState.ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleOrchestratorMessage(data);
            };
            
            this.orchestratorState.ws.onclose = () => {
                console.log('Orchestrator WebSocket closed, reconnecting...');
                setTimeout(() => this.setupOrchestratorWebSocket(), 5000);
            };
            
            this.orchestratorState.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
            };
        } catch (error) {
            console.error('Failed to setup orchestrator WebSocket:', error);
        }
    };

    VeraChat.prototype.handleOrchestratorMessage = function(data) {
        if (data.type === 'task_completed') {
            this.refreshDashboard();
            const taskName = data.data.task_name || 'unknown';
            this.addSystemMessage(`✓ Task completed: ${taskName}`, 'success');
            
            // Refresh worker pools if on that panel
            if (this.orchestratorState.currentPanel === 'workers') {
                this.refreshWorkerPools();
            }
        } 
        else if (data.type === 'task_failed') {
            this.refreshDashboard();
            const taskName = data.data.task_name || 'unknown';
            const error = data.data.error || 'Unknown error';
            this.addSystemMessage(`✗ Task failed: ${taskName} - ${error}`, 'error');
            
            if (this.orchestratorState.currentPanel === 'workers') {
                this.refreshWorkerPools();
            }
        } 
        else if (data.type === 'status_update') {
            // Update queue display
            const totalQueue = data.data.queue_size;
            const queueElem = document.getElementById('orch-queue');
            if (queueElem) queueElem.textContent = totalQueue;
            
            // Update per-type queue sizes
            if (data.data.queue_sizes) {
                Object.entries(data.data.queue_sizes).forEach(([type, size]) => {
                    const elem = document.getElementById(`queue-${type}`);
                    if (elem) elem.textContent = size;
                });
            }
            
            // Update chart data
            this.updateChartData('queue', totalQueue);
        }
    };

    // ========================================================================
    // PERIODIC UPDATES
    // ========================================================================
    
    VeraChat.prototype.startOrchestratorUpdates = function() {
        if (this.orchestratorState.updateInterval) {
            clearInterval(this.orchestratorState.updateInterval);
        }
        
        this.orchestratorState.updateInterval = setInterval(() => {
            if (this.activeTab === 'orchestration') {
                this.refreshOrchestrator();
            }
        }, 3000);
    };

    VeraChat.prototype.stopOrchestratorUpdates = function() {
        if (this.orchestratorState.updateInterval) {
            clearInterval(this.orchestratorState.updateInterval);
            this.orchestratorState.updateInterval = null;
        }
    };

    // ========================================================================
    // PANEL SWITCHING
    // ========================================================================
    
    VeraChat.prototype.switchOrchPanel = function(panelName) {
        // Update navigation buttons
        document.querySelectorAll('.orch-nav-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        const activeBtn = document.querySelector(`.orch-nav-btn[data-panel="${panelName}"]`);
        if (activeBtn) activeBtn.classList.add('active');
        
        // Update panels
        document.querySelectorAll('.orch-panel').forEach(panel => {
            panel.style.display = 'none';
        });
        const activePanel = document.getElementById(`orch-panel-${panelName}`);
        if (activePanel) activePanel.style.display = 'block';
        
        this.orchestratorState.currentPanel = panelName;
        
        // Load panel-specific data
        switch(panelName) {
            case 'dashboard':
                this.refreshDashboard();
                break;
            case 'workers':
                this.refreshWorkerPools();
                break;
            case 'tasks':
                this.loadRegisteredTasks();
                break;
            case 'monitor':
                this.refreshSystemMetrics();
                break;
            case 'config':
                // Config panel is static, no refresh needed
                break;
        }
    };

    // ========================================================================
    // DATA REFRESH
    // ========================================================================
    
    VeraChat.prototype.refreshOrchestrator = async function() {
        try {
            await Promise.all([
                this.refreshHealth(),
                this.refreshDashboard(),
                this.refreshSystemMetrics()
            ]);
        } catch (error) {
            console.error('Failed to refresh orchestrator:', error);
        }
    };

    VeraChat.prototype.refreshHealth = async function() {
        try {
            const response = await fetch(`${this.orchestratorState.apiUrl}/health`);
            const data = await response.json();
            
            const indicator = document.getElementById('orch-pool-indicator');
            const status = document.getElementById('orch-pool-status');
            
            if (data.orchestrator_running) {
                if (indicator) indicator.style.background = '#22c55e';
                if (status) status.textContent = 'Running';
            } else {
                if (indicator) indicator.style.background = '#ef4444';
                if (status) status.textContent = 'Stopped';
            }
            
            // Update registered tasks count
            const tasksCountElem = document.getElementById('orch-tasks-count');
            if (tasksCountElem) {
                tasksCountElem.textContent = data.registered_tasks || 0;
            }
        } catch (error) {
            console.error('Health check failed:', error);
        }
    };

    VeraChat.prototype.refreshDashboard = async function() {
        try {
            const [status, metrics] = await Promise.all([
                fetch(`${this.orchestratorState.apiUrl}/status`).then(r => r.json()).catch(() => ({initialized: false})),
                fetch(`${this.orchestratorState.apiUrl}/system/metrics`).then(r => r.json()).catch(() => ({metrics: {}}))
            ]);

            if (status.initialized) {
                const utilization = status.worker_count > 0 
                    ? (status.active_workers / status.worker_count * 100).toFixed(1)
                    : 0;
                
                // Update worker counts
                const activeElem = document.getElementById('orch-workers-active');
                const totalElem = document.getElementById('orch-workers-total');
                const queueElem = document.getElementById('orch-queue');
                const utilElem = document.getElementById('orch-dash-util');
                
                if (activeElem) activeElem.textContent = status.active_workers;
                if (totalElem) totalElem.textContent = status.worker_count;
                if (queueElem) queueElem.textContent = status.queue_size;
                if (utilElem) utilElem.textContent = `${utilization}%`;
                
                // Update queue breakdown by type
                if (status.queue_sizes) {
                    let queueHtml = '<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 8px; margin-top: 12px;">';
                    Object.entries(status.queue_sizes).forEach(([type, size]) => {
                        const color = size > 5 ? 'var(--danger)' : size > 2 ? 'var(--warning)' : 'var(--success)';
                        queueHtml += `
                            <div style="padding: 12px; background: var(--bg-darker); border-radius: 6px; border-left: 3px solid ${color};">
                                <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">${type}</div>
                                <div style="font-size: 24px; font-weight: 600;" id="queue-${type}">${size}</div>
                            </div>
                        `;
                    });
                    queueHtml += '</div>';
                    
                    const queueContainer = document.getElementById('orch-queue-breakdown');
                    if (queueContainer) queueContainer.innerHTML = queueHtml;
                }
            }

            // Update CPU/Memory
            if (metrics.metrics) {
                const cpuElem = document.getElementById('orch-cpu');
                if (cpuElem) cpuElem.textContent = `${metrics.metrics.cpu_percent.toFixed(1)}%`;
                
                // Update chart data
                this.updateChartData('cpu', metrics.metrics.cpu_percent);
                this.updateChartData('memory', metrics.metrics.memory_percent);
            }
        } catch (error) {
            console.error('Dashboard refresh failed:', error);
        }
    };

    // ========================================================================
    // WORKER POOL MANAGEMENT
    // ========================================================================
    
    VeraChat.prototype.refreshWorkerPools = async function() {
        try {
            const response = await fetch(`${this.orchestratorState.apiUrl}/workers/pools`);
            const data = await response.json();
            
            const container = document.getElementById('orch-worker-pools-list');
            if (!container) return;
            
            if (!data.pools || data.pools.length === 0) {
                container.innerHTML = `
                    <div style="text-align: center; padding: 48px; color: var(--text-muted);">
                        <div style="font-size: 48px; margin-bottom: 16px;">⚙️</div>
                        <h3 style="margin: 0 0 8px 0;">No Worker Pools</h3>
                        <p style="margin: 0;">Initialize the orchestrator from the Configuration panel to get started.</p>
                    </div>
                `;
                return;
            }
            
            container.innerHTML = data.pools.map(pool => {
                const utilizationColor = pool.utilization > 80 ? 'var(--danger)' : 
                                        pool.utilization > 50 ? 'var(--warning)' : 
                                        'var(--success)';
                
                return `
                    <div style="padding: 20px; margin-bottom: 16px; background: var(--bg); border-radius: 12px; border-left: 4px solid ${utilizationColor}; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                            <div>
                                <h3 style="margin: 0 0 4px 0; font-size: 18px; font-weight: 600;">${pool.task_type}</h3>
                                <div style="font-size: 13px; color: var(--text-muted);">
                                    ${pool.active_workers}/${pool.num_workers} active • ${pool.idle_workers} idle • ${pool.queue_size} queued
                                </div>
                            </div>
                            <div style="text-align: right;">
                                <div style="font-size: 32px; font-weight: 700; color: ${utilizationColor};">
                                    ${pool.utilization}%
                                </div>
                                <div style="font-size: 11px; color: var(--text-muted); text-transform: uppercase;">utilization</div>
                            </div>
                        </div>
                        
                        <!-- Progress bar -->
                        <div style="height: 10px; background: var(--bg-darker); border-radius: 5px; overflow: hidden; margin-bottom: 16px;">
                            <div style="height: 100%; background: ${utilizationColor}; width: ${pool.utilization}%; transition: width 0.3s ease;"></div>
                        </div>
                        
                        <!-- Worker scaling controls -->
                        <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px;">
                            <button onclick="veraChat.scaleWorkerPool('${pool.task_type}', ${pool.num_workers - 1})" 
                                    ${pool.num_workers <= 1 ? 'disabled' : ''}
                                    style="padding: 8px 16px; background: var(--danger); border: none; border-radius: 6px; color: white; cursor: pointer; font-size: 14px; font-weight: 600; transition: all 0.2s;"
                                    onmouseover="this.style.opacity='0.8'"
                                    onmouseout="this.style.opacity='1'">
                                − Remove Worker
                            </button>
                            <span style="font-weight: 600; font-size: 16px; min-width: 80px; text-align: center;">${pool.num_workers} workers</span>
                            <button onclick="veraChat.scaleWorkerPool('${pool.task_type}', ${pool.num_workers + 1})"
                                    style="padding: 8px 16px; background: var(--success); border: none; border-radius: 6px; color: white; cursor: pointer; font-size: 14px; font-weight: 600; transition: all 0.2s;"
                                    onmouseover="this.style.opacity='0.8'"
                                    onmouseout="this.style.opacity='1'">
                                + Add Worker
                            </button>
                        </div>
                        
                        <!-- Worker details -->
                        ${pool.workers && pool.workers.length > 0 ? `
                            <details style="margin-top: 16px;">
                                <summary style="cursor: pointer; font-size: 13px; color: var(--text-muted); font-weight: 600; padding: 8px; background: var(--bg-darker); border-radius: 4px;">
                                    Worker Details (${pool.workers.length})
                                </summary>
                                <div style="margin-top: 12px; padding: 12px; background: var(--bg-darker); border-radius: 8px;">
                                    ${pool.workers.map(w => `
                                        <div style="padding: 8px; margin-bottom: 8px; background: var(--bg); border-radius: 4px; display: flex; justify-content: space-between; align-items: center;">
                                            <div>
                                                <div style="font-weight: 600; font-size: 13px;">${w.worker_id}</div>
                                                ${w.tasks_completed ? `<div style="font-size: 11px; color: var(--text-muted);">${w.tasks_completed} tasks completed</div>` : ''}
                                            </div>
                                            <span style="padding: 4px 12px; border-radius: 12px; font-size: 11px; font-weight: 600; ${w.current_task ? 'background: var(--success); color: white;' : 'background: var(--bg-darker); color: var(--text-muted);'}">
                                                ${w.current_task ? `⚡ ${w.current_task.substring(0, 8)}...` : '💤 Idle'}
                                            </span>
                                        </div>
                                    `).join('')}
                                </div>
                            </details>
                        ` : ''}
                    </div>
                `;
            }).join('');
        } catch (error) {
            console.error('Failed to refresh worker pools:', error);
        }
    };

    VeraChat.prototype.scaleWorkerPool = async function(taskType, numWorkers) {
        if (numWorkers < 0) {
            this.addSystemMessage('Cannot have negative workers', 'error');
            return;
        }
        
        try {
            const response = await fetch(`${this.orchestratorState.apiUrl}/workers/scale`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    task_type: taskType,
                    num_workers: numWorkers
                })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const data = await response.json();
            this.addSystemMessage(data.message, 'success');
            
            // Refresh worker pools display immediately
            await this.refreshWorkerPools();
            
            // Also refresh dashboard
            await this.refreshDashboard();
        } catch (error) {
            this.addSystemMessage(`Failed to scale worker pool: ${error.message}`, 'error');
        }
    };

    // ========================================================================
    // TASK MANAGEMENT
    // ========================================================================
    
    VeraChat.prototype.loadRegisteredTasks = async function() {
        try {
            const response = await fetch(`${this.orchestratorState.apiUrl}/tasks/registry`);
            const data = await response.json();
            
            // Update task dropdown
            const select = document.getElementById('orch-task-name');
            if (select) {
                select.innerHTML = data.tasks.map(task => 
                    `<option value="${task.name}">${task.name} ${task.type ? `(${task.type})` : ''}</option>`
                ).join('') || '<option>No tasks registered</option>';
            }

            // Update registered tasks display
            const container = document.getElementById('orch-registered-tasks');
            if (!container) return;
            
            if (!data.tasks || data.tasks.length === 0) {
                container.innerHTML = '<p style="color: var(--text-muted); text-align: center; padding: 24px;">No tasks registered</p>';
                return;
            }
            
            // Group tasks by type
            const tasksByType = {};
            data.tasks.forEach(task => {
                const type = task.type || 'unknown';
                if (!tasksByType[type]) tasksByType[type] = [];
                tasksByType[type].push(task);
            });
            
            let html = '';
            Object.entries(tasksByType).forEach(([type, tasks]) => {
                const typeColors = {
                    'llm': 'var(--accent)',
                    'tool': 'var(--success)',
                    'whisper': 'var(--warning)',
                    'background': 'var(--info)',
                    'general': 'var(--text-muted)'
                };
                const color = typeColors[type.toLowerCase()] || 'var(--text-muted)';
                
                html += `
                    <div style="margin-bottom: 20px;">
                        <h4 style="margin: 0 0 12px 0; font-size: 12px; text-transform: uppercase; color: ${color}; font-weight: 700; display: flex; align-items: center;">
                            <span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: ${color}; margin-right: 8px;"></span>
                            ${type} (${tasks.length})
                        </h4>
                        ${tasks.map(task => `
                            <div style="padding: 12px; background: var(--bg); border-radius: 6px; margin: 6px 0; border-left: 3px solid ${color};">
                                <div style="font-weight: 600; font-size: 13px; margin-bottom: 4px;">${task.name}</div>
                                ${task.estimated_duration || task.requires_gpu ? `
                                    <div style="font-size: 11px; color: var(--text-muted); display: flex; gap: 12px;">
                                        ${task.estimated_duration ? `<span>⏱️ ~${task.estimated_duration}s</span>` : ''}
                                        ${task.requires_gpu ? `<span>🎮 GPU</span>` : ''}
                                        ${task.priority ? `<span>📌 ${task.priority}</span>` : ''}
                                    </div>
                                ` : ''}
                            </div>
                        `).join('')}
                    </div>
                `;
            });
            
            container.innerHTML = html;
        } catch (error) {
            console.error('Failed to load tasks:', error);
        }
    };

    VeraChat.prototype.submitTask = async function() {
        try {
            const taskName = document.getElementById('orch-task-name')?.value;
            const payloadText = document.getElementById('orch-task-payload')?.value || '{}';
            
            if (!taskName) {
                this.addSystemMessage('Please select a task', 'error');
                return;
            }
            
            let payload;
            try {
                payload = JSON.parse(payloadText);
            } catch (e) {
                this.addSystemMessage('Invalid JSON payload', 'error');
                return;
            }
            
            const taskData = {
                name: taskName,
                payload: payload,
                context: {}
            };

            const response = await fetch(`${this.orchestratorState.apiUrl}/tasks/submit`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(taskData)
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const data = await response.json();
            this.addSystemMessage(`✓ Task submitted: ${data.task_id.substring(0, 8)}...`, 'success');
            
            // Refresh dashboard to show new task in queue
            await this.refreshDashboard();
        } catch (error) {
            this.addSystemMessage(`Failed to submit task: ${error.message}`, 'error');
        }
    };

    // ========================================================================
    // SYSTEM MONITORING
    // ========================================================================
    
    VeraChat.prototype.refreshSystemMetrics = async function() {
        try {
            const response = await fetch(`${this.orchestratorState.apiUrl}/system/metrics`);
            const data = await response.json();
            const metrics = data.metrics;

            // Update CPU
            const cpuElem = document.getElementById('orch-cpu');
            const monCpuElem = document.getElementById('orch-mon-cpu');
            const cpuBar = document.getElementById('orch-cpu-bar');
            
            if (cpuElem) cpuElem.textContent = `${metrics.cpu_percent.toFixed(1)}%`;
            if (monCpuElem) monCpuElem.textContent = `${metrics.cpu_percent.toFixed(1)}%`;
            if (cpuBar) cpuBar.style.width = `${metrics.cpu_percent}%`;
            
            // Update Memory
            const memElem = document.getElementById('orch-mon-memory');
            const memBar = document.getElementById('orch-memory-bar');
            
            if (memElem) memElem.textContent = `${metrics.memory_percent.toFixed(1)}%`;
            if (memBar) memBar.style.width = `${metrics.memory_percent}%`;

            // Refresh processes if on monitor panel
            if (this.orchestratorState.currentPanel === 'monitor') {
                await this.refreshProcesses();
            }
        } catch (error) {
            // Silently fail for metrics
        }
    };

    VeraChat.prototype.refreshProcesses = async function() {
        try {
            const response = await fetch(`${this.orchestratorState.apiUrl}/system/processes`);
            const data = await response.json();
            
            const countElem = document.getElementById('orch-mon-processes');
            if (countElem) countElem.textContent = data.processes.length;
            
            const container = document.getElementById('orch-processes-list');
            if (!container) return;
            
            if (!data.processes || data.processes.length === 0) {
                container.innerHTML = '<p style="color: var(--text-muted); text-align: center; padding: 24px;">No active processes</p>';
                return;
            }
            
            container.innerHTML = data.processes.slice(0, 15).map(proc => {
                const cpuColor = proc.cpu_percent > 50 ? 'var(--danger)' : proc.cpu_percent > 25 ? 'var(--warning)' : 'var(--success)';
                return `
                    <div style="padding: 12px; margin-bottom: 8px; background: var(--bg); border-radius: 6px; display: flex; justify-content: space-between; align-items: center; border-left: 3px solid ${cpuColor};">
                        <div>
                            <div style="font-weight: 600; font-size: 13px;">${this.escapeHtml(proc.name)}</div>
                            <div style="font-size: 11px; color: var(--text-muted);">PID: ${proc.pid}</div>
                        </div>
                        <div style="text-align: right;">
                            <div style="font-weight: 600; color: ${cpuColor};">CPU: ${(proc.cpu_percent || 0).toFixed(1)}%</div>
                            <div style="font-size: 11px; color: var(--text-muted);">Mem: ${(proc.memory_percent || 0).toFixed(1)}%</div>
                        </div>
                    </div>
                `;
            }).join('');
        } catch (error) {
            console.error('Failed to refresh processes:', error);
        }
    };

    // ========================================================================
    // ORCHESTRATOR CONTROL
    // ========================================================================
    
    VeraChat.prototype.initializeOrchestrator = async function() {
        const config = {
            llm_workers: parseInt(document.getElementById('orch-llm-workers')?.value) || 3,
            tool_workers: parseInt(document.getElementById('orch-tool-workers')?.value) || 4,
            whisper_workers: parseInt(document.getElementById('orch-whisper-workers')?.value) || 1,
            background_workers: parseInt(document.getElementById('orch-bg-workers')?.value) || 2,
            general_workers: parseInt(document.getElementById('orch-gen-workers')?.value) || 2,
            cpu_threshold: parseFloat(document.getElementById('orch-cpu-threshold')?.value) || 75.0
        };

        try {
            this.addSystemMessage('Initializing orchestrator...', 'info');
            
            const response = await fetch(`${this.orchestratorState.apiUrl}/initialize`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const data = await response.json();
            this.addSystemMessage(data.message, 'success');
            
            await this.refreshHealth();
            await this.refreshDashboard();
            
            // Switch to dashboard to see results
            this.switchOrchPanel('dashboard');
        } catch (error) {
            this.addSystemMessage(`Failed to initialize: ${error.message}`, 'error');
        }
    };

    VeraChat.prototype.startOrchestrator = async function() {
        try {
            const response = await fetch(`${this.orchestratorState.apiUrl}/start`, { method: 'POST' });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            this.addSystemMessage('✓ Orchestrator started', 'success');
            await this.refreshHealth();
            await this.refreshDashboard();
        } catch (error) {
            this.addSystemMessage(`Failed to start: ${error.message}`, 'error');
        }
    };

    VeraChat.prototype.stopOrchestrator = async function() {
        try {
            const response = await fetch(`${this.orchestratorState.apiUrl}/stop`, { method: 'POST' });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            this.addSystemMessage('✓ Orchestrator stopped', 'success');
            await this.refreshHealth();
            await this.refreshDashboard();
        } catch (error) {
            this.addSystemMessage(`Failed to stop: ${error.message}`, 'error');
        }
    };

    // ========================================================================
    // CHART DATA MANAGEMENT
    // ========================================================================
    
    VeraChat.prototype.updateChartData = function(metric, value) {
        const data = this.orchestratorState.chartData[metric];
        if (!data) return;
        
        data.push(value);
        
        // Keep only recent data points
        if (data.length > this.orchestratorState.maxDataPoints) {
            data.shift();
        }
    };

    // ========================================================================
    // CLEANUP
    // ========================================================================
    
    VeraChat.prototype.cleanupOrchestrator = function() {
        console.log('Cleaning up orchestrator UI...');
        
        // Stop updates
        this.stopOrchestratorUpdates();
        
        // Close WebSocket
        if (this.orchestratorState.ws) {
            this.orchestratorState.ws.close();
            this.orchestratorState.ws = null;
        }
    };

    // ========================================================================
    // UTILITY FUNCTIONS
    // ========================================================================
    
    VeraChat.prototype.escapeHtml = function(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    };

})();