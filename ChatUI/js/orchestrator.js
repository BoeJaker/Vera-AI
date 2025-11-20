(() => {
    // Orchestrator state
    VeraChat.prototype.orchestratorState = {
        currentPanel: 'dashboard',
        apiUrl: 'http://llm.int:8888/orchestrator',
        updateInterval: null,
        ws: null
    };

    // Initialize orchestrator
    VeraChat.prototype.initOrchestrator = async function() {
        console.log('Initializing orchestrator...');
        
        // Setup WebSocket
        this.setupOrchestratorWebSocket();
        
        // Start periodic updates
        this.startOrchestratorUpdates();
        
        // Initial load
        await this.refreshOrchestrator();
    };

    // Setup WebSocket connection
    VeraChat.prototype.setupOrchestratorWebSocket = function() {
        const wsUrl = this.orchestratorState.apiUrl.replace('http', 'ws') + '/ws/updates';
        
        try {
            this.orchestratorState.ws = new WebSocket(wsUrl);
            
            this.orchestratorState.ws.onopen = () => {
                console.log('Orchestrator WebSocket connected');
            };
            
            this.orchestratorState.ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleOrchestratorMessage(data);
            };
            
            this.orchestratorState.ws.onclose = () => {
                console.log('Orchestrator WebSocket closed, reconnecting...');
                setTimeout(() => this.setupOrchestratorWebSocket(), 5000);
            };
        } catch (error) {
            console.error('Failed to setup orchestrator WebSocket:', error);
        }
    };

    // Handle WebSocket messages
    VeraChat.prototype.handleOrchestratorMessage = function(data) {
        if (data.type === 'task_start' || data.type === 'task_end') {
            this.refreshDashboard();
            this.addSystemMessage(`Task ${data.type === 'task_start' ? 'started' : 'completed'}: ${data.data.name}`);
        } else if (data.type === 'status_update') {
            document.getElementById('orch-queue').textContent = data.data.queue_size;
        }
    };

    // Start periodic updates
    VeraChat.prototype.startOrchestratorUpdates = function() {
        // Clear existing interval
        if (this.orchestratorState.updateInterval) {
            clearInterval(this.orchestratorState.updateInterval);
        }
        
        // Update every 3 seconds
        this.orchestratorState.updateInterval = setInterval(() => {
            if (this.activeTab === 'orchestration') {
                this.refreshOrchestrator();
            }
        }, 3000);
    };

    // Switch orchestrator panels
    VeraChat.prototype.switchOrchPanel = function(panelName) {
        // Update nav buttons
        document.querySelectorAll('.orch-nav-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        document.querySelector(`.orch-nav-btn[data-panel="${panelName}"]`).classList.add('active');
        
        // Update panels
        document.querySelectorAll('.orch-panel').forEach(panel => {
            panel.style.display = 'none';
        });
        document.getElementById(`orch-panel-${panelName}`).style.display = 'block';
        
        this.orchestratorState.currentPanel = panelName;
        
        // Load panel-specific data
        switch(panelName) {
            case 'dashboard':
                this.refreshDashboard();
                break;
            case 'pool':
                this.refreshPoolStatus();
                break;
            case 'tasks':
                this.loadRegisteredTasks();
                this.refreshTaskHistory();
                break;
            case 'monitor':
                this.refreshSystemMetrics();
                break;
        }
    };

    // Refresh all orchestrator data
    VeraChat.prototype.refreshOrchestrator = async function() {
        await Promise.all([
            this.refreshHealth(),
            this.refreshDashboard(),
            this.refreshSystemMetrics()
        ]);
    };

    // Refresh health status
    VeraChat.prototype.refreshHealth = async function() {
        try {
            const response = await fetch(`${this.orchestratorState.apiUrl}/health`);
            const data = await response.json();
            
            const indicator = document.getElementById('orch-pool-indicator');
            const status = document.getElementById('orch-pool-status');
            
            if (data.local_pool) {
                indicator.style.background = '#22c55e';
                status.textContent = 'Running';
            } else {
                indicator.style.background = '#ef4444';
                status.textContent = 'Stopped';
            }
        } catch (error) {
            console.error('Health check failed:', error);
        }
    };

    // Refresh dashboard
    VeraChat.prototype.refreshDashboard = async function() {
        try {
            const [poolStatus, taskHistory] = await Promise.all([
                fetch(`${this.orchestratorState.apiUrl}/pool/status`).then(r => r.json()).catch(() => ({initialized: false})),
                fetch(`${this.orchestratorState.apiUrl}/tasks/history?limit=10`).then(r => r.json()).catch(() => ({history: []}))
            ]);

            if (poolStatus.initialized) {
                const utilization = poolStatus.worker_count > 0 
                    ? (poolStatus.active_workers / poolStatus.worker_count * 100).toFixed(1)
                    : 0;
                
                document.getElementById('orch-workers-active').textContent = poolStatus.active_workers;
                document.getElementById('orch-workers-total').textContent = poolStatus.worker_count;
                document.getElementById('orch-queue').textContent = poolStatus.queue_size;
                document.getElementById('orch-dash-util').textContent = `${utilization}%`;
            }

            const completedTasks = taskHistory.history.filter(t => t.status === 'completed').length;
            document.getElementById('orch-dash-completed').textContent = completedTasks;

            // Render recent tasks
            const tasksContainer = document.getElementById('orch-dash-tasks');
            if (taskHistory.history.length > 0) {
                tasksContainer.innerHTML = taskHistory.history.slice(0, 5).map(task => `
                    <div style="padding: 8px; margin-bottom: 8px; background: var(--bg); border-radius: 4px; border-left: 3px solid ${task.status === 'completed' ? 'var(--success)' : 'var(--danger)'};">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                            <span style="font-weight: 600;">${this.escapeHtml(task.name)}</span>
                            <span style="font-size: 11px; color: var(--text-muted);">${new Date(task.timestamp).toLocaleTimeString()}</span>
                        </div>
                        <div style="font-size: 11px; color: var(--text-muted);">
                            Priority: ${task.priority} • Status: ${task.status}
                        </div>
                    </div>
                `).join('');
            } else {
                tasksContainer.innerHTML = '<p style="color: var(--text-muted); text-align: center;">No recent tasks</p>';
            }
        } catch (error) {
            console.error('Dashboard refresh failed:', error);
        }
    };

    // Refresh system metrics
    VeraChat.prototype.refreshSystemMetrics = async function() {
        try {
            const response = await fetch(`${this.orchestratorState.apiUrl}/system/metrics`);
            const data = await response.json();
            const metrics = data.metrics;

            document.getElementById('orch-cpu').textContent = `${metrics.cpu_percent.toFixed(1)}%`;
            document.getElementById('orch-mon-cpu').textContent = `${metrics.cpu_percent.toFixed(1)}%`;
            document.getElementById('orch-cpu-bar').style.width = `${metrics.cpu_percent}%`;
            
            document.getElementById('orch-mon-memory').textContent = `${metrics.memory_percent.toFixed(1)}%`;
            document.getElementById('orch-memory-bar').style.width = `${metrics.memory_percent}%`;

            if (this.orchestratorState.currentPanel === 'monitor') {
                await this.refreshProcesses();
            }
        } catch (error) {
            // Silently fail
        }
    };

    // Refresh processes list
    VeraChat.prototype.refreshProcesses = async function() {
        try {
            const response = await fetch(`${this.orchestratorState.apiUrl}/system/processes`);
            const data = await response.json();
            
            document.getElementById('orch-mon-processes').textContent = data.processes.length;
            
            const container = document.getElementById('orch-processes-list');
            container.innerHTML = data.processes.slice(0, 10).map(proc => `
                <div style="padding: 8px; margin-bottom: 4px; background: var(--bg); border-radius: 4px; display: flex; justify-content: space-between;">
                    <div>
                        <div style="font-weight: 600;">${this.escapeHtml(proc.name)}</div>
                        <div style="font-size: 11px; color: var(--text-muted);">PID: ${proc.pid}</div>
                    </div>
                    <div style="text-align: right;">
                        <div>CPU: ${(proc.cpu_percent || 0).toFixed(1)}%</div>
                        <div style="font-size: 11px; color: var(--text-muted);">Mem: ${(proc.memory_percent || 0).toFixed(1)}%</div>
                    </div>
                </div>
            `).join('');
        } catch (error) {
            console.error('Failed to refresh processes:', error);
        }
    };

    // Pool management functions
    VeraChat.prototype.initializePool = async function() {
        const config = {
            worker_count: parseInt(document.getElementById('orch-worker-count').value),
            cpu_threshold: parseFloat(document.getElementById('orch-cpu-threshold').value),
            max_processes: 24,
            max_process_name: 'ollama'
        };

        try {
            const response = await fetch(`${this.orchestratorState.apiUrl}/pool/initialize`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });
            const data = await response.json();
            this.addSystemMessage(data.message);
            await this.refreshHealth();
        } catch (error) {
            this.addSystemMessage(`Failed to initialize pool: ${error.message}`);
        }
    };

    VeraChat.prototype.startPool = async function() {
        try {
            await fetch(`${this.orchestratorState.apiUrl}/pool/start`, { method: 'POST' });
            this.addSystemMessage('Pool started');
            await this.refreshHealth();
        } catch (error) {
            this.addSystemMessage(`Failed to start pool: ${error.message}`);
        }
    };

    VeraChat.prototype.stopPool = async function() {
        try {
            await fetch(`${this.orchestratorState.apiUrl}/pool/stop`, { method: 'POST' });
            this.addSystemMessage('Pool stopped');
            await this.refreshHealth();
        } catch (error) {
            this.addSystemMessage(`Failed to stop pool: ${error.message}`);
        }
    };

    VeraChat.prototype.pausePool = async function() {
        try {
            await fetch(`${this.orchestratorState.apiUrl}/pool/pause`, { method: 'POST' });
            this.addSystemMessage('Pool paused');
        } catch (error) {
            this.addSystemMessage(`Failed to pause pool: ${error.message}`);
        }
    };

    VeraChat.prototype.resumePool = async function() {
        try {
            await fetch(`${this.orchestratorState.apiUrl}/pool/resume`, { method: 'POST' });
            this.addSystemMessage('Pool resumed');
        } catch (error) {
            this.addSystemMessage(`Failed to resume pool: ${error.message}`);
        }
    };

    // Task management
    VeraChat.prototype.loadRegisteredTasks = async function() {
        try {
            const response = await fetch(`${this.orchestratorState.apiUrl}/tasks/registry`);
            const data = await response.json();
            
            const select = document.getElementById('orch-task-name');
            select.innerHTML = data.tasks.map(task => 
                `<option value="${task}">${task}</option>`
            ).join('') || '<option>No tasks registered</option>';

            const container = document.getElementById('orch-registered-tasks');
            container.innerHTML = data.tasks.map(task => 
                `<div style="padding: 8px; background: var(--accent-muted); border-radius: 4px; margin: 4px 0;">${task}</div>`
            ).join('') || '<p style="color: var(--text-muted);">No tasks registered</p>';
        } catch (error) {
            console.error('Failed to load tasks:', error);
        }
    };

    VeraChat.prototype.submitTask = async function() {
        try {
            const taskData = {
                name: document.getElementById('orch-task-name').value,
                priority: document.getElementById('orch-task-priority').value,
                labels: [],
                delay: 0,
                payload: JSON.parse(document.getElementById('orch-task-payload').value),
                context: {}
            };

            const response = await fetch(`${this.orchestratorState.apiUrl}/tasks/submit`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(taskData)
            });
            const data = await response.json();
            this.addSystemMessage(`Task submitted: ${data.task_id}`);
        } catch (error) {
            this.addSystemMessage(`Failed to submit task: ${error.message}`);
        }
    };

    VeraChat.prototype.refreshTaskHistory = async function() {
        try {
            const response = await fetch(`${this.orchestratorState.apiUrl}/tasks/history?limit=50`);
            const data = await response.json();
            
            const container = document.getElementById('orch-task-history');
            if (data.history.length > 0) {
                container.innerHTML = data.history.map(task => `
                    <div style="padding: 8px; margin-bottom: 8px; background: var(--bg); border-radius: 4px; border-left: 3px solid ${task.status === 'completed' ? 'var(--success)' : task.status === 'failed' ? 'var(--danger)' : 'var(--warning)'};">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                            <span style="font-weight: 600;">${this.escapeHtml(task.name)}</span>
                            <span style="font-size: 11px; color: var(--text-muted);">${new Date(task.timestamp).toLocaleString()}</span>
                        </div>
                        <div style="font-size: 11px; color: var(--text-muted);">
                            ID: ${task.task_id.substring(0, 8)}... • Priority: ${task.priority} • Status: ${task.status}
                        </div>
                        ${task.error ? `<div style="font-size: 11px; color: var(--danger); margin-top: 4px;">${this.escapeHtml(task.error)}</div>` : ''}
                    </div>
                `).join('');
            } else {
                container.innerHTML = '<p style="color: var(--text-muted); text-align: center;">No task history</p>';
            }
        } catch (error) {
            console.error('Failed to refresh task history:', error);
        }
    };

    VeraChat.prototype.refreshPoolStatus = async function() {
        // Pool status refresh logic
        await this.refreshHealth();
    };

    // Cleanup on tab switch
    VeraChat.prototype.cleanupOrchestrator = function() {
        if (this.orchestratorState.updateInterval) {
            clearInterval(this.orchestratorState.updateInterval);
            this.orchestratorState.updateInterval = null;
        }
    };
})();