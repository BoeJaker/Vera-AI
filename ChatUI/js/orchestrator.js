(() => {
    // ========================================================================
    // ENHANCED ORCHESTRATOR STATE
    // ========================================================================
    
    VeraChat.prototype.orchestratorState = {
        currentPanel: 'queue', // Start on queue panel
        apiUrl: 'http://llm.int:8888/orchestrator',
        updateInterval: null,
        ws: null,
        chartData: {
            cpu: [],
            memory: [],
            queue: []
        },
        maxDataPoints: 60,
        selectedTask: null,
        taskTemplates: [],
        filterOptions: {
            status: 'all',
            taskType: 'all',
            searchText: ''
        },
        sortBy: 'time',
        sortOrder: 'desc'
    };

    // ========================================================================
    // INITIALIZATION
    // ========================================================================
    
    VeraChat.prototype.initOrchestrator = async function() {
        console.log('Initializing enhanced orchestrator UI...');
        
        // Load task templates
        await this.loadTaskTemplates();
        
        // Setup WebSocket
        this.setupOrchestratorWebSocket();
        
        // Start periodic updates
        this.startOrchestratorUpdates();
        
        // Initial load
        await this.refreshOrchestrator();
    };

    // ========================================================================
    // WEBSOCKET MANAGEMENT (Enhanced)
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
        switch(data.type) {
            case 'task_submitted':
                this.onTaskSubmitted(data.data);
                break;
            case 'task_started':
                this.onTaskStarted(data.data);
                break;
            case 'task_completed':
                this.onTaskCompleted(data.data);
                break;
            case 'task_failed':
                this.onTaskFailed(data.data);
                break;
            case 'task_cancelled':
                this.onTaskCancelled(data.data);
                break;
            case 'status_update':
                this.onStatusUpdate(data.data);
                break;
        }
    };

    VeraChat.prototype.onTaskSubmitted = function(data) {
        const taskName = data.task_name || 'unknown';
        const desc = data.description || taskName;
        this.addSystemMessage(`📋 Task submitted: ${desc}`, 'info');
        this.refreshTaskQueue();
    };

    VeraChat.prototype.onTaskStarted = function(data) {
        const taskName = data.task_name || 'unknown';
        this.addSystemMessage(`▶️ Task started: ${taskName}`, 'info');
        this.refreshTaskQueue();
        if (this.orchestratorState.currentPanel === 'workers') {
            this.refreshWorkerPools();
        }
    };

    VeraChat.prototype.onTaskCompleted = function(data) {
        const taskName = data.task_name || 'unknown';
        this.addSystemMessage(`✓ Task completed: ${taskName}`, 'success');
        this.refreshTaskQueue();
        this.refreshDashboard();
    };

    VeraChat.prototype.onTaskFailed = function(data) {
        const taskName = data.task_name || 'unknown';
        const error = data.error || 'Unknown error';
        this.addSystemMessage(`✗ Task failed: ${taskName} - ${error}`, 'error');
        this.refreshTaskQueue();
    };

    VeraChat.prototype.onTaskCancelled = function(data) {
        this.addSystemMessage(`🚫 Task cancelled: ${data.task_id.substring(0, 8)}`, 'warning');
        this.refreshTaskQueue();
    };

    VeraChat.prototype.onStatusUpdate = function(data) {
        // Update queue display
        const totalQueue = data.queue_size;
        const queueElem = document.getElementById('orch-queue');
        if (queueElem) queueElem.textContent = totalQueue;
        
        const activeElem = document.getElementById('orch-active-count');
        if (activeElem) activeElem.textContent = data.active_tasks || 0;
        
        // Update per-type queue sizes
        if (data.queue_sizes) {
            Object.entries(data.queue_sizes).forEach(([type, size]) => {
                const elem = document.getElementById(`queue-${type}`);
                if (elem) elem.textContent = size;
            });
        }
        
        this.updateChartData('queue', totalQueue);
    };

    // ========================================================================
    // TASK QUEUE MANAGEMENT
    // ========================================================================
    
    VeraChat.prototype.refreshTaskQueue = async function() {
        try {
            // Add diagnostics check
            const diagnostics = await fetch(`${this.orchestratorState.apiUrl}/diagnostics`)
                .then(r => r.json())
                .catch(() => null);
            
            if (diagnostics) {
                console.log('[Orchestrator UI] Diagnostics:', diagnostics);
                
                // Warn if tracking mismatch
                if (diagnostics.total_queued > 0 && diagnostics.tracking.active_tasks_tracked === 0) {
                    console.warn('[Orchestrator UI] WARNING: Tasks in queue but not tracked!');
                    this.addSystemMessage(
                        '⚠️ Task tracking may not be initialized. Check console for details.',
                        'warning'
                    );
                }
            }
            
            const [active, history] = await Promise.all([
                fetch(`${this.orchestratorState.apiUrl}/tasks/active`).then(r => r.json()),
                fetch(`${this.orchestratorState.apiUrl}/tasks/history?limit=50`).then(r => r.json())
            ]);
            
            console.log('[Orchestrator UI] Active tasks:', active.count, 'History:', history.total);
            
            // Show warning if no tasks but tracking seems off
            if (active.count === 0 && !active.tracking_active) {
                console.warn('[Orchestrator UI] Task tracking appears inactive');
            }
            
            this.renderTaskQueue(active.tasks, history.tasks);
        } catch (error) {
            console.error('[Orchestrator UI] Failed to refresh task queue:', error);
            this.addSystemMessage(`Failed to load task queue: ${error.message}`, 'error');
        }
    };

    VeraChat.prototype.renderTaskQueue = function(activeTasks, historyTasks) {
        const container = document.getElementById('orch-task-queue-container');
        if (!container) return;
        
        // Apply filters
        const filteredActive = this.filterTasks(activeTasks);
        const filteredHistory = this.filterTasks(historyTasks);
        
        let html = `
            <!-- Filter Controls -->
            <div style="display: flex; gap: 12px; margin-bottom: 16px; padding: 16px; background: var(--bg); border-radius: 8px;">
                <select id="queue-filter-status" onchange="app.updateTaskFilter('status', this.value)" 
                        style="padding: 8px 12px; background: var(--bg-darker); border: 1px solid var(--border); border-radius: 4px; color: var(--text);">
                    <option value="all">All Status</option>
                    <option value="queued">Queued</option>
                    <option value="running">Running</option>
                    <option value="completed">Completed</option>
                    <option value="failed">Failed</option>
                    <option value="cancelled">Cancelled</option>
                </select>
                
                <select id="queue-filter-type" onchange="app.updateTaskFilter('taskType', this.value)"
                        style="padding: 8px 12px; background: var(--bg-darker); border: 1px solid var(--border); border-radius: 4px; color: var(--text);">
                    <option value="all">All Types</option>
                    <option value="llm">LLM</option>
                    <option value="tool">Tool</option>
                    <option value="whisper">Whisper</option>
                    <option value="background">Background</option>
                    <option value="general">General</option>
                </select>
                
                <input type="text" id="queue-filter-search" placeholder="Search tasks..." 
                       oninput="app.updateTaskFilter('searchText', this.value)"
                       style="flex: 1; padding: 8px 12px; background: var(--bg-darker); border: 1px solid var(--border); border-radius: 4px; color: var(--text);">
                
                <button onclick="app.clearTaskFilters()" 
                        style="padding: 8px 16px; background: var(--bg-darker); border: 1px solid var(--border); border-radius: 4px; color: var(--text); cursor: pointer;">
                    Clear
                </button>
            </div>
            
            <!-- Active Tasks Section -->
            <div style="margin-bottom: 24px;">
                <h3 style="margin: 0 0 12px 0; display: flex; align-items: center; justify-content: space-between;">
                    <span>🔄 Active Tasks (${filteredActive.length})</span>
                    <button onclick="app.refreshTaskQueue()" 
                            style="padding: 4px 12px; font-size: 12px; background: var(--bg-darker); border: 1px solid var(--border); border-radius: 4px; cursor: pointer;">
                        Refresh
                    </button>
                </h3>
                ${filteredActive.length > 0 ? this.renderTaskList(filteredActive, true) : 
                  '<div style="text-align: center; padding: 32px; color: var(--text-muted); background: var(--bg); border-radius: 8px;">No active tasks</div>'}
            </div>
            
            <!-- Task History Section -->
            <div>
                <h3 style="margin: 0 0 12px 0; display: flex; align-items: center; justify-content: space-between;">
                    <span>📜 Task History (${filteredHistory.length})</span>
                    <select onchange="app.changeSortOrder(this.value)"
                            style="padding: 4px 8px; font-size: 12px; background: var(--bg-darker); border: 1px solid var(--border); border-radius: 4px;">
                        <option value="time-desc">Newest First</option>
                        <option value="time-asc">Oldest First</option>
                        <option value="duration-desc">Longest Duration</option>
                        <option value="duration-asc">Shortest Duration</option>
                    </select>
                </h3>
                ${filteredHistory.length > 0 ? this.renderTaskList(filteredHistory, false) : 
                  '<div style="text-align: center; padding: 32px; color: var(--text-muted); background: var(--bg); border-radius: 8px;">No task history</div>'}
            </div>
        `;
        
        container.innerHTML = html;
        
        // Restore filter values
        if (this.orchestratorState.filterOptions.status !== 'all') {
            const statusSelect = document.getElementById('queue-filter-status');
            if (statusSelect) statusSelect.value = this.orchestratorState.filterOptions.status;
        }
        if (this.orchestratorState.filterOptions.taskType !== 'all') {
            const typeSelect = document.getElementById('queue-filter-type');
            if (typeSelect) typeSelect.value = this.orchestratorState.filterOptions.taskType;
        }
        if (this.orchestratorState.filterOptions.searchText) {
            const searchInput = document.getElementById('queue-filter-search');
            if (searchInput) searchInput.value = this.orchestratorState.filterOptions.searchText;
        }
    };

    VeraChat.prototype.renderTaskList = function(tasks, isActive) {
        return `
            <div style="display: flex; flex-direction: column; gap: 8px;">
                ${tasks.map(task => this.renderTaskCard(task, isActive)).join('')}
            </div>
        `;
    };

    VeraChat.prototype.renderTaskCard = function(task, isActive) {
        const statusColors = {
            'queued': 'var(--info)',
            'running': 'var(--warning)',
            'completed': 'var(--success)',
            'failed': 'var(--danger)',
            'cancelled': 'var(--text-muted)'
        };
        
        const statusIcons = {
            'queued': '⏳',
            'running': '▶️',
            'completed': '✓',
            'failed': '✗',
            'cancelled': '🚫'
        };
        
        const status = task.status || 'unknown';
        const color = statusColors[status] || 'var(--text-muted)';
        const icon = statusIcons[status] || '•';
        
        const description = task.description || task.task_name;
        const taskId = task.task_id;
        const taskIdShort = taskId ? taskId.substring(0, 8) : 'unknown';
        
        // Calculate duration or time ago
        let timeInfo = '';
        if (task.completed_at && task.submitted_at) {
            try {
                const start = new Date(task.submitted_at);
                const end = new Date(task.completed_at);
                const duration = ((end - start) / 1000).toFixed(2);
                timeInfo = `Duration: ${duration}s`;
            } catch (e) {
                timeInfo = 'Duration: N/A';
            }
        } else if (task.submitted_at) {
            try {
                const submitted = new Date(task.submitted_at);
                const now = new Date();
                const ago = Math.floor((now - submitted) / 1000);
                if (ago < 60) timeInfo = `${ago}s ago`;
                else if (ago < 3600) timeInfo = `${Math.floor(ago / 60)}m ago`;
                else timeInfo = `${Math.floor(ago / 3600)}h ago`;
            } catch (e) {
                timeInfo = 'Time: N/A';
            }
        }
        
        return `
            <div onclick="app.showTaskDetails('${taskId}')" 
                 style="padding: 16px; background: var(--bg); border-radius: 8px; border-left: 4px solid ${color}; cursor: pointer; transition: all 0.2s;"
                 onmouseover="this.style.background='var(--bg-darker)'"
                 onmouseout="this.style.background='var(--bg)'">
                <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 8px;">
                    <div style="flex: 1;">
                        <div style="font-weight: 600; font-size: 14px; margin-bottom: 4px;">
                            ${icon} ${this.escapeHtml(description)}
                        </div>
                        <div style="font-size: 11px; color: var(--text-muted); display: flex; gap: 12px; flex-wrap: wrap;">
                            <span>ID: ${taskIdShort}</span>
                            <span>Type: ${task.task_type || 'unknown'}</span>
                            <span>${timeInfo}</span>
                            ${task.priority ? `<span>Priority: ${task.priority}</span>` : ''}
                        </div>
                    </div>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="padding: 4px 12px; border-radius: 12px; font-size: 11px; font-weight: 600; background: ${color}22; color: ${color};">
                            ${status.toUpperCase()}
                        </span>
                        ${isActive ? this.renderTaskActions(taskId, status) : ''}
                    </div>
                </div>
                ${task.error ? `<div style="font-size: 12px; color: var(--danger); margin-top: 8px;">Error: ${this.escapeHtml(task.error)}</div>` : ''}
                ${task.payload_preview ? `<details style="margin-top: 8px; font-size: 11px;"><summary style="cursor: pointer; color: var(--text-muted);">Payload</summary><pre style="margin-top: 4px; padding: 8px; background: var(--bg-darker); border-radius: 4px; overflow-x: auto;">${this.escapeHtml(task.payload_preview)}</pre></details>` : ''}
            </div>
        `;
    };

    VeraChat.prototype.renderTaskActions = function(taskId, status) {
        if (status === 'queued' || status === 'running') {
            return `
                <button onclick="event.stopPropagation(); app.cancelTask('${taskId}')" 
                        style="padding: 4px 8px; font-size: 11px; background: var(--danger); color: white; border: none; border-radius: 4px; cursor: pointer;"
                        title="Cancel task">
                    Cancel
                </button>
            `;
        } else if (status === 'failed') {
            return `
                <button onclick="event.stopPropagation(); app.retryTask('${taskId}')" 
                        style="padding: 4px 8px; font-size: 11px; background: var(--warning); color: white; border: none; border-radius: 4px; cursor: pointer;"
                        title="Retry task">
                    Retry
                </button>
            `;
        }
        return '';
    };

    VeraChat.prototype.filterTasks = function(tasks) {
        const { status, taskType, searchText } = this.orchestratorState.filterOptions;
        
        return tasks.filter(task => {
            if (status !== 'all' && task.status !== status) return false;
            if (taskType !== 'all' && task.task_type !== taskType) return false;
            if (searchText) {
                const searchLower = searchText.toLowerCase();
                const matchName = (task.task_name || '').toLowerCase().includes(searchLower);
                const matchDesc = (task.description || '').toLowerCase().includes(searchLower);
                const matchId = (task.task_id || '').toLowerCase().includes(searchLower);
                if (!matchName && !matchDesc && !matchId) return false;
            }
            return true;
        });
    };

    VeraChat.prototype.updateTaskFilter = function(filterType, value) {
        this.orchestratorState.filterOptions[filterType] = value;
        this.refreshTaskQueue();
    };

    VeraChat.prototype.clearTaskFilters = function() {
        this.orchestratorState.filterOptions = {
            status: 'all',
            taskType: 'all',
            searchText: ''
        };
        this.refreshTaskQueue();
    };

    VeraChat.prototype.changeSortOrder = function(order) {
        const [sortBy, sortOrder] = order.split('-');
        this.orchestratorState.sortBy = sortBy;
        this.orchestratorState.sortOrder = sortOrder;
        this.refreshTaskQueue();
    };

    // ========================================================================
    // TASK DETAILS MODAL
    // ========================================================================
    
    VeraChat.prototype.showTaskDetails = async function(taskId) {
        try {
            const response = await fetch(`${this.orchestratorState.apiUrl}/tasks/${taskId}/status`);
            const task = await response.json();
            
            this.orchestratorState.selectedTask = task;
            this.renderTaskDetailsModal(task);
        } catch (error) {
            this.addSystemMessage(`Failed to load task details: ${error.message}`, 'error');
        }
    };

    VeraChat.prototype.renderTaskDetailsModal = function(task) {
        const modal = document.getElementById('orch-task-details-modal');
        if (!modal) return;
        
        const statusColors = {
            'queued': 'var(--info)',
            'running': 'var(--warning)',
            'completed': 'var(--success)',
            'failed': 'var(--danger)',
            'cancelled': 'var(--text-muted)'
        };
        
        const color = statusColors[task.status] || 'var(--text-muted)';
        
        modal.innerHTML = `
            <div style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.7); display: flex; align-items: center; justify-content: center; z-index: 10000;" onclick="this.remove()">
                <div onclick="event.stopPropagation()" style="background: var(--bg-darker); padding: 24px; border-radius: 12px; max-width: 700px; max-height: 80vh; overflow-y: auto; box-shadow: 0 8px 32px rgba(0,0,0,0.3);">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                        <h2 style="margin: 0; font-size: 20px;">Task Details</h2>
                        <button onclick="this.closest('[style*=fixed]').remove()" 
                                style="padding: 8px 16px; background: var(--bg); border: 1px solid var(--border); border-radius: 4px; cursor: pointer;">
                            Close
                        </button>
                    </div>
                    
                    <div style="display: grid; gap: 16px;">
                        <div style="padding: 16px; background: var(--bg); border-radius: 8px; border-left: 4px solid ${color};">
                            <div style="font-size: 18px; font-weight: 600; margin-bottom: 8px;">
                                ${this.escapeHtml(task.description || task.task_name)}
                            </div>
                            <div style="display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px;">
                                <span style="padding: 6px 12px; background: ${color}22; color: ${color}; border-radius: 12px; font-size: 12px; font-weight: 600;">
                                    ${task.status.toUpperCase()}
                                </span>
                                <span style="padding: 6px 12px; background: var(--bg-darker); border-radius: 12px; font-size: 12px;">
                                    ${task.task_type || 'unknown'}
                                </span>
                                ${task.priority ? `<span style="padding: 6px 12px; background: var(--bg-darker); border-radius: 12px; font-size: 12px;">Priority: ${task.priority}</span>` : ''}
                            </div>
                        </div>
                        
                        <div style="padding: 16px; background: var(--bg); border-radius: 8px;">
                            <h3 style="margin: 0 0 12px 0; font-size: 14px; color: var(--text-muted);">Metadata</h3>
                            <div style="display: grid; gap: 8px; font-size: 13px;">
                                <div><strong>Task ID:</strong> ${task.task_id}</div>
                                <div><strong>Task Name:</strong> ${task.task_name}</div>
                                ${task.submitted_at ? `<div><strong>Submitted:</strong> ${new Date(task.submitted_at).toLocaleString()}</div>` : ''}
                                ${task.started_at ? `<div><strong>Started:</strong> ${new Date(task.started_at).toLocaleString()}</div>` : ''}
                                ${task.completed_at ? `<div><strong>Completed:</strong> ${new Date(task.completed_at).toLocaleString()}</div>` : ''}
                                ${task.duration ? `<div><strong>Duration:</strong> ${task.duration.toFixed(2)}s</div>` : ''}
                                ${task.worker_id ? `<div><strong>Worker:</strong> ${task.worker_id}</div>` : ''}
                                ${task.estimated_duration ? `<div><strong>Estimated Duration:</strong> ${task.estimated_duration}s</div>` : ''}
                            </div>
                        </div>
                        
                        ${task.error ? `
                            <div style="padding: 16px; background: var(--danger)22; border: 1px solid var(--danger); border-radius: 8px;">
                                <h3 style="margin: 0 0 8px 0; font-size: 14px; color: var(--danger);">Error</h3>
                                <pre style="margin: 0; font-size: 12px; white-space: pre-wrap; word-wrap: break-word;">${this.escapeHtml(task.error)}</pre>
                            </div>
                        ` : ''}
                        
                        ${task.result ? `
                            <div style="padding: 16px; background: var(--bg); border-radius: 8px;">
                                <h3 style="margin: 0 0 8px 0; font-size: 14px; color: var(--text-muted);">Result</h3>
                                <pre style="margin: 0; padding: 12px; background: var(--bg-darker); border-radius: 4px; font-size: 12px; max-height: 300px; overflow: auto;">${this.escapeHtml(JSON.stringify(task.result, null, 2))}</pre>
                            </div>
                        ` : ''}
                        
                        ${task.payload_preview ? `
                            <div style="padding: 16px; background: var(--bg); border-radius: 8px;">
                                <h3 style="margin: 0 0 8px 0; font-size: 14px; color: var(--text-muted);">Payload</h3>
                                <pre style="margin: 0; padding: 12px; background: var(--bg-darker); border-radius: 4px; font-size: 12px; max-height: 200px; overflow: auto;">${this.escapeHtml(task.payload_preview)}</pre>
                            </div>
                        ` : ''}
                    </div>
                    
                    ${task.status === 'queued' || task.status === 'running' ? `
                        <div style="margin-top: 20px; display: flex; gap: 12px;">
                            <button onclick="app.cancelTask('${task.task_id}'); this.closest('[style*=fixed]').remove();" 
                                    style="flex: 1; padding: 12px; background: var(--danger); color: white; border: none; border-radius: 6px; font-weight: 600; cursor: pointer;">
                                Cancel Task
                            </button>
                        </div>
                    ` : ''}
                    
                    ${task.status === 'failed' ? `
                        <div style="margin-top: 20px; display: flex; gap: 12px;">
                            <button onclick="app.retryTask('${task.task_id}'); this.closest('[style*=fixed]').remove();" 
                                    style="flex: 1; padding: 12px; background: var(--warning); color: white; border: none; border-radius: 6px; font-weight: 600; cursor: pointer;">
                                Retry Task
                            </button>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
    };

    // ========================================================================
    // TASK MANAGEMENT ACTIONS
    // ========================================================================
    
    VeraChat.prototype.cancelTask = async function(taskId) {
        if (!confirm('Are you sure you want to cancel this task?')) return;
        
        try {
            const response = await fetch(`${this.orchestratorState.apiUrl}/tasks/${taskId}/cancel`, {
                method: 'POST'
            });
            
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            this.addSystemMessage(`✓ Task cancelled: ${taskId.substring(0, 8)}`, 'success');
            
            await this.refreshTaskQueue();
        } catch (error) {
            this.addSystemMessage(`Failed to cancel task: ${error.message}`, 'error');
        }
    };

    VeraChat.prototype.retryTask = async function(taskId) {
        try {
            const response = await fetch(`${this.orchestratorState.apiUrl}/tasks/${taskId}/retry`, {
                method: 'POST'
            });
            
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            this.addSystemMessage(`✓ Task retried: ${data.new_task_id.substring(0, 8)}`, 'success');
            
            await this.refreshTaskQueue();
        } catch (error) {
            this.addSystemMessage(`Failed to retry task: ${error.message}`, 'error');
        }
    };

    // ========================================================================
    // TASK CREATION INTERFACE
    // ========================================================================
    
    VeraChat.prototype.loadTaskTemplates = async function() {
        try {
            const response = await fetch(`${this.orchestratorState.apiUrl}/tasks/templates`);
            const data = await response.json();
            this.orchestratorState.taskTemplates = data.templates;
        } catch (error) {
            console.error('Failed to load task templates:', error);
        }
    };

    VeraChat.prototype.renderTaskCreationPanel = function() {
        const container = document.getElementById('orch-task-creation-container');
        if (!container) return;
        
        const templates = this.orchestratorState.taskTemplates;
        
        let html = `
            <div style="display: grid; gap: 16px;">
                <!-- Template Selection -->
                <div style="padding: 20px; background: var(--bg); border-radius: 12px;">
                    <h3 style="margin: 0 0 16px 0;">Quick Task Creation</h3>
                    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 12px;">
                        ${templates.map(template => `
                            <button onclick="app.selectTaskTemplate('${template.template_id}')"
                                    style="padding: 16px; background: var(--bg-darker); border: 2px solid var(--border); border-radius: 8px; cursor: pointer; text-align: left; transition: all 0.2s;"
                                    onmouseover="this.style.borderColor='var(--accent)'"
                                    onmouseout="this.style.borderColor='var(--border)'">
                                <div style="font-weight: 600; margin-bottom: 4px;">${template.display_name}</div>
                                <div style="font-size: 11px; color: var(--text-muted);">${template.task_name}</div>
                            </button>
                        `).join('')}
                    </div>
                </div>
                
                <!-- Template Form (initially hidden) -->
                <div id="orch-template-form-container" style="display: none;"></div>
                
                <!-- Advanced Creation -->
                <div style="padding: 20px; background: var(--bg); border-radius: 12px;">
                    <h3 style="margin: 0 0 16px 0;">Advanced Task Creation</h3>
                    <div style="display: grid; gap: 12px;">
                        <div>
                            <label style="display: block; margin-bottom: 4px; font-size: 13px; color: var(--text-muted);">Task Name</label>
                            <select id="orch-advanced-task-name" style="width: 100%; padding: 10px; background: var(--bg-darker); border: 1px solid var(--border); border-radius: 6px; color: var(--text);">
                                <option value="">Select a task...</option>
                            </select>
                        </div>
                        
                        <div>
                            <label style="display: block; margin-bottom: 4px; font-size: 13px; color: var(--text-muted);">Description (Optional)</label>
                            <input type="text" id="orch-advanced-description" placeholder="Human-readable description"
                                   style="width: 100%; padding: 10px; background: var(--bg-darker); border: 1px solid var(--border); border-radius: 6px; color: var(--text);">
                        </div>
                        
                        <div>
                            <label style="display: block; margin-bottom: 4px; font-size: 13px; color: var(--text-muted);">Payload (JSON)</label>
                            <textarea id="orch-advanced-payload" rows="6" placeholder='{"key": "value"}'
                                      style="width: 100%; padding: 10px; background: var(--bg-darker); border: 1px solid var(--border); border-radius: 6px; color: var(--text); font-family: monospace; font-size: 12px;"></textarea>
                        </div>
                        
                        <button onclick="app.submitAdvancedTask()" 
                                style="padding: 12px; background: var(--accent); color: white; border: none; border-radius: 6px; font-weight: 600; cursor: pointer; font-size: 14px;">
                            Submit Task
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        container.innerHTML = html;
        
        // Populate advanced task name dropdown
        this.populateAdvancedTaskDropdown();
    };

    VeraChat.prototype.populateAdvancedTaskDropdown = async function() {
        try {
            const response = await fetch(`${this.orchestratorState.apiUrl}/tasks/registry`);
            const data = await response.json();
            
            const select = document.getElementById('orch-advanced-task-name');
            if (!select) return;
            
            select.innerHTML = '<option value="">Select a task...</option>' +
                data.tasks.map(task => 
                    `<option value="${task.name}">${task.name} (${task.type})</option>`
                ).join('');
        } catch (error) {
            console.error('Failed to load task registry:', error);
        }
    };

    VeraChat.prototype.selectTaskTemplate = function(templateId) {
        const template = this.orchestratorState.taskTemplates.find(t => t.template_id === templateId);
        if (!template) return;
        
        const container = document.getElementById('orch-template-form-container');
        if (!container) return;
        
        let html = `
            <div style="padding: 20px; background: var(--bg); border-radius: 12px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                    <h3 style="margin: 0;">${template.display_name}</h3>
                    <button onclick="document.getElementById('orch-template-form-container').style.display='none'"
                            style="padding: 4px 12px; background: var(--bg-darker); border: 1px solid var(--border); border-radius: 4px; cursor: pointer;">
                        Cancel
                    </button>
                </div>
                
                <form id="template-form-${templateId}" style="display: grid; gap: 12px;">
                    ${template.parameters.map((param, idx) => this.renderParameterInput(param, idx)).join('')}
                    
                    <button type="submit" 
                            style="padding: 12px; background: var(--success); color: white; border: none; border-radius: 6px; font-weight: 600; cursor: pointer; font-size: 14px; margin-top: 8px;">
                        Create Task
                    </button>
                </form>
            </div>
        `;
        
        container.innerHTML = html;
        container.style.display = 'block';
        
        // Add form submit handler
        document.getElementById(`template-form-${templateId}`).addEventListener('submit', (e) => {
            e.preventDefault();
            this.submitTemplateTask(template);
        });
    };

    VeraChat.prototype.renderParameterInput = function(param, idx) {
        const inputId = `param-${idx}`;
        
        let input = '';
        
        switch (param.type) {
            case 'text':
                input = `<input type="text" id="${inputId}" placeholder="${param.placeholder || ''}" ${param.default !== undefined ? `value="${param.default}"` : ''}
                               style="width: 100%; padding: 10px; background: var(--bg-darker); border: 1px solid var(--border); border-radius: 6px; color: var(--text);">`;
                break;
            case 'textarea':
                input = `<textarea id="${inputId}" rows="4" placeholder="${param.placeholder || ''}" 
                                   style="width: 100%; padding: 10px; background: var(--bg-darker); border: 1px solid var(--border); border-radius: 6px; color: var(--text);">${param.default || ''}</textarea>`;
                break;
            case 'number':
                input = `<input type="number" id="${inputId}" ${param.min !== undefined ? `min="${param.min}"` : ''} ${param.max !== undefined ? `max="${param.max}"` : ''} ${param.default !== undefined ? `value="${param.default}"` : ''}
                               style="width: 100%; padding: 10px; background: var(--bg-darker); border: 1px solid var(--border); border-radius: 6px; color: var(--text);">`;
                break;
            case 'boolean':
                input = `<input type="checkbox" id="${inputId}" ${param.default ? 'checked' : ''}
                               style="width: 20px; height: 20px; cursor: pointer;">`;
                break;
            case 'select':
                input = `<select id="${inputId}" style="width: 100%; padding: 10px; background: var(--bg-darker); border: 1px solid var(--border); border-radius: 6px; color: var(--text);">
                           ${param.options.map(opt => `<option value="${opt}" ${param.default === opt ? 'selected' : ''}>${opt}</option>`).join('')}
                         </select>`;
                break;
        }
        
        return `
            <div data-param-name="${param.name}" data-param-type="${param.type}">
                <label style="display: block; margin-bottom: 4px; font-size: 13px; color: var(--text-muted); font-weight: 600;">
                    ${param.name}
                </label>
                ${input}
            </div>
        `;
    };

    VeraChat.prototype.submitTemplateTask = async function(template) {
        const form = document.getElementById(`template-form-${template.template_id}`);
        if (!form) return;
        
        const parameters = {};
        
        template.parameters.forEach((param, idx) => {
            const input = form.querySelector(`[data-param-name="${param.name}"] input, [data-param-name="${param.name}"] select, [data-param-name="${param.name}"] textarea`);
            if (!input) return;
            
            if (param.type === 'boolean') {
                parameters[param.name] = input.checked;
            } else if (param.type === 'number') {
                parameters[param.name] = parseFloat(input.value) || 0;
            } else {
                parameters[param.name] = input.value;
            }
        });
        
        try {
            const response = await fetch(`${this.orchestratorState.apiUrl}/tasks/submit/template?template_id=${template.template_id}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    parameters: parameters,
                    description: template.display_name
                })
            });
            
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            this.addSystemMessage(`✓ Task submitted: ${data.task_id.substring(0, 8)}`, 'success');
            
            // Hide form
            document.getElementById('orch-template-form-container').style.display = 'none';
            
            // Switch to queue panel
            this.switchOrchPanel('queue');
            
            await this.refreshTaskQueue();
        } catch (error) {
            this.addSystemMessage(`Failed to submit task: ${error.message}`, 'error');
        }
    };

    VeraChat.prototype.submitAdvancedTask = async function() {
        const taskName = document.getElementById('orch-advanced-task-name')?.value;
        const description = document.getElementById('orch-advanced-description')?.value;
        const payloadText = document.getElementById('orch-advanced-payload')?.value || '{}';
        
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
        
        try {
            const response = await fetch(`${this.orchestratorState.apiUrl}/tasks/submit`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: taskName,
                    payload: payload,
                    description: description || undefined,
                    context: {}
                })
            });
            
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            this.addSystemMessage(`✓ Task submitted: ${data.task_id.substring(0, 8)}`, 'success');
            
            // Clear form
            document.getElementById('orch-advanced-task-name').value = '';
            document.getElementById('orch-advanced-description').value = '';
            document.getElementById('orch-advanced-payload').value = '';
            
            // Switch to queue panel
            this.switchOrchPanel('queue');
            
            await this.refreshTaskQueue();
        } catch (error) {
            this.addSystemMessage(`Failed to submit task: ${error.message}`, 'error');
        }
    };

    // ========================================================================
    // PANEL SWITCHING (Updated)
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
            case 'queue':
                this.refreshTaskQueue();
                break;
            case 'create':
                this.renderTaskCreationPanel();
                break;
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
                // Config panel is static
                break;
        }
    };

    // ========================================================================
    // REST OF ORIGINAL FUNCTIONS (Dashboard, Workers, etc.)
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

    VeraChat.prototype.refreshOrchestrator = async function() {
        try {
            await Promise.all([
                this.refreshHealth(),
                this.orchestratorState.currentPanel === 'queue' ? this.refreshTaskQueue() : Promise.resolve(),
                this.orchestratorState.currentPanel === 'dashboard' ? this.refreshDashboard() : Promise.resolve(),
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
                
                const activeElem = document.getElementById('orch-workers-active');
                const totalElem = document.getElementById('orch-workers-total');
                const queueElem = document.getElementById('orch-queue');
                const utilElem = document.getElementById('orch-dash-util');
                
                if (activeElem) activeElem.textContent = status.active_workers;
                if (totalElem) totalElem.textContent = status.worker_count;
                if (queueElem) queueElem.textContent = status.queue_size;
                if (utilElem) utilElem.textContent = `${utilization}%`;
                
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

            if (metrics.metrics) {
                const cpuElem = document.getElementById('orch-cpu');
                if (cpuElem) cpuElem.textContent = `${metrics.metrics.cpu_percent.toFixed(1)}%`;
                
                this.updateChartData('cpu', metrics.metrics.cpu_percent);
                this.updateChartData('memory', metrics.metrics.memory_percent);
            }
        } catch (error) {
            console.error('Dashboard refresh failed:', error);
        }
    };

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
                        
                        <div style="height: 10px; background: var(--bg-darker); border-radius: 5px; overflow: hidden; margin-bottom: 16px;">
                            <div style="height: 100%; background: ${utilizationColor}; width: ${pool.utilization}%; transition: width 0.3s ease;"></div>
                        </div>
                        
                        <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px;">
                            <button onclick="app.scaleWorkerPool('${pool.task_type}', ${pool.num_workers - 1})" 
                                    ${pool.num_workers <= 1 ? 'disabled' : ''}
                                    style="padding: 8px 16px; background: var(--danger); border: none; border-radius: 6px; color: white; cursor: pointer; font-size: 14px; font-weight: 600; transition: all 0.2s;"
                                    onmouseover="this.style.opacity='0.8'"
                                    onmouseout="this.style.opacity='1'">
                                − Remove Worker
                            </button>
                            <span style="font-weight: 600; font-size: 16px; min-width: 80px; text-align: center;">${pool.num_workers} workers</span>
                            <button onclick="app.scaleWorkerPool('${pool.task_type}', ${pool.num_workers + 1})"
                                    style="padding: 8px 16px; background: var(--success); border: none; border-radius: 6px; color: white; cursor: pointer; font-size: 14px; font-weight: 600; transition: all 0.2s;"
                                    onmouseover="this.style.opacity='0.8'"
                                    onmouseout="this.style.opacity='1'">
                                + Add Worker
                            </button>
                        </div>
                        
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
            
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            this.addSystemMessage(data.message, 'success');
            
            await this.refreshWorkerPools();
            await this.refreshDashboard();
        } catch (error) {
            this.addSystemMessage(`Failed to scale worker pool: ${error.message}`, 'error');
        }
    };

    VeraChat.prototype.loadRegisteredTasks = async function() {
        try {
            const response = await fetch(`${this.orchestratorState.apiUrl}/tasks/registry`);
            const data = await response.json();
            
            const container = document.getElementById('orch-registered-tasks');
            if (!container) return;
            
            if (!data.tasks || data.tasks.length === 0) {
                container.innerHTML = '<p style="color: var(--text-muted); text-align: center; padding: 24px;">No tasks registered</p>';
                return;
            }
            
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

    VeraChat.prototype.refreshSystemMetrics = async function() {
        try {
            const response = await fetch(`${this.orchestratorState.apiUrl}/system/metrics`);
            const data = await response.json();
            const metrics = data.metrics;

            const cpuElem = document.getElementById('orch-cpu');
            const monCpuElem = document.getElementById('orch-mon-cpu');
            const cpuBar = document.getElementById('orch-cpu-bar');
            
            if (cpuElem) cpuElem.textContent = `${metrics.cpu_percent.toFixed(1)}%`;
            if (monCpuElem) monCpuElem.textContent = `${metrics.cpu_percent.toFixed(1)}%`;
            if (cpuBar) cpuBar.style.width = `${metrics.cpu_percent}%`;
            
            const memElem = document.getElementById('orch-mon-memory');
            const memBar = document.getElementById('orch-memory-bar');
            
            if (memElem) memElem.textContent = `${metrics.memory_percent.toFixed(1)}%`;
            if (memBar) memBar.style.width = `${metrics.memory_percent}%`;

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
            
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            this.addSystemMessage(data.message, 'success');
            
            await this.refreshHealth();
            await this.refreshDashboard();
            
            this.switchOrchPanel('dashboard');
        } catch (error) {
            this.addSystemMessage(`Failed to initialize: ${error.message}`, 'error');
        }
    };

    VeraChat.prototype.startOrchestrator = async function() {
        try {
            const response = await fetch(`${this.orchestratorState.apiUrl}/start`, { method: 'POST' });
            
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
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
            
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            this.addSystemMessage('✓ Orchestrator stopped', 'success');
            await this.refreshHealth();
            await this.refreshDashboard();
        } catch (error) {
            this.addSystemMessage(`Failed to stop: ${error.message}`, 'error');
        }
    };

    VeraChat.prototype.updateChartData = function(metric, value) {
        const data = this.orchestratorState.chartData[metric];
        if (!data) return;
        
        data.push(value);
        
        if (data.length > this.orchestratorState.maxDataPoints) {
            data.shift();
        }
    };

    VeraChat.prototype.cleanupOrchestrator = function() {
        console.log('Cleaning up orchestrator UI...');
        
        this.stopOrchestratorUpdates();
        
        if (this.orchestratorState.ws) {
            this.orchestratorState.ws.close();
            this.orchestratorState.ws = null;
        }
    };

    VeraChat.prototype.escapeHtml = function(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    };

})();