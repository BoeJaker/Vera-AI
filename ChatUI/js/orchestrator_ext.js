(() => {
    // ========================================================================
    // EXTENDED ORCHESTRATOR STATE
    // ========================================================================
    
    VeraChat.prototype.orchestratorExtState = {
        infraApiUrl: 'http://llm.int:8888/orchestrator/infrastructure',
        externalApiUrl: 'http://llm.int:8888/orchestrator/external',
        selectedResource: null,
        selectedProvider: null,
        resourceUpdateInterval: null,
        costUpdateInterval: null
    };

    // ========================================================================
    // EXTENDED PANEL SWITCHING
    // ========================================================================
    
    const originalSwitchOrchPanel = VeraChat.prototype.switchOrchPanel;
    VeraChat.prototype.switchOrchPanel = function(panelName) {
        originalSwitchOrchPanel.call(this, panelName);
        
        // Load extended panel data
        switch(panelName) {
            case 'infrastructure':
                this.refreshInfrastructure();
                this.startResourceUpdates();
                break;
            case 'external':
                this.refreshExternalAPIs();
                this.startCostUpdates();
                break;
            default:
                this.stopResourceUpdates();
                this.stopCostUpdates();
                break;
        }
    };

    // ========================================================================
    // INFRASTRUCTURE MANAGEMENT
    // ========================================================================
    
    VeraChat.prototype.refreshInfrastructure = async function() {
        await Promise.all([
            this.refreshInfrastructureHealth(),
            this.refreshInfrastructureStats(),
            this.refreshResourcesList()
        ]);
    };

    VeraChat.prototype.refreshInfrastructureHealth = async function() {
        try {
            const response = await fetch(`${this.orchestratorExtState.infraApiUrl}/health`);
            const data = await response.json();
            
            const indicator = document.getElementById('infra-indicator');
            const dockerStatus = document.getElementById('infra-docker-status');
            const proxmoxStatus = document.getElementById('infra-proxmox-status');
            
            if (indicator) {
                indicator.style.background = data.status === 'healthy' ? '#22c55e' : '#ef4444';
            }
            
            if (dockerStatus) {
                dockerStatus.textContent = data.docker_available ? '✓ Available' : '✗ Unavailable';
                dockerStatus.style.color = data.docker_available ? 'var(--success)' : 'var(--text-muted)';
            }
            
            if (proxmoxStatus) {
                proxmoxStatus.textContent = data.proxmox_available ? '✓ Available' : '✗ Unavailable';
                proxmoxStatus.style.color = data.proxmox_available ? 'var(--success)' : 'var(--text-muted)';
            }
        } catch (error) {
            console.error('Infrastructure health check failed:', error);
        }
    };

    VeraChat.prototype.refreshInfrastructureStats = async function() {
        try {
            const response = await fetch(`${this.orchestratorExtState.infraApiUrl}/stats`);
            const data = await response.json();
            
            if (!data.initialized) {
                document.getElementById('infra-stats')?.innerHTML = `
                    <div style="text-align: center; padding: 24px; color: var(--text-muted);">
                        <p>Infrastructure not initialized</p>
                    </div>
                `;
                return;
            }
            
            // Update stat cards
            document.getElementById('infra-total-resources')?.textContent = data.total_resources || 0;
            document.getElementById('infra-available-resources')?.textContent = data.available_resources || 0;
            document.getElementById('infra-in-use-resources')?.textContent = data.in_use_resources || 0;
            document.getElementById('infra-tasks-executed')?.textContent = data.tasks_executed || 0;
            
            // Update capacity display
            const capacityHtml = `
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-top: 16px;">
                    <div style="padding: 16px; background: var(--bg); border-radius: 8px; border-left: 3px solid var(--accent);">
                        <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">CPU CORES</div>
                        <div style="font-size: 24px; font-weight: 600;">${data.available_capacity?.cpu_cores || 0}/${data.total_capacity?.cpu_cores || 0}</div>
                    </div>
                    <div style="padding: 16px; background: var(--bg); border-radius: 8px; border-left: 3px solid var(--success);">
                        <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">MEMORY (GB)</div>
                        <div style="font-size: 24px; font-weight: 600;">${((data.available_capacity?.memory_mb || 0) / 1024).toFixed(1)}/${((data.total_capacity?.memory_mb || 0) / 1024).toFixed(1)}</div>
                    </div>
                    <div style="padding: 16px; background: var(--bg); border-radius: 8px; border-left: 3px solid var(--warning);">
                        <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">DISK (GB)</div>
                        <div style="font-size: 24px; font-weight: 600;">${data.available_capacity?.disk_gb || 0}/${data.total_capacity?.disk_gb || 0}</div>
                    </div>
                    <div style="padding: 16px; background: var(--bg); border-radius: 8px; border-left: 3px solid var(--danger);">
                        <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">GPUs</div>
                        <div style="font-size: 24px; font-weight: 600;">${data.available_capacity?.gpu_count || 0}/${data.total_capacity?.gpu_count || 0}</div>
                    </div>
                </div>
            `;
            
            const capacityContainer = document.getElementById('infra-capacity');
            if (capacityContainer) capacityContainer.innerHTML = capacityHtml;
            
        } catch (error) {
            console.error('Failed to refresh infrastructure stats:', error);
        }
    };

    VeraChat.prototype.refreshResourcesList = async function() {
        try {
            const response = await fetch(`${this.orchestratorExtState.infraApiUrl}/resources`);
            const data = await response.json();
            
            const container = document.getElementById('infra-resources-list');
            if (!container) return;
            
            if (!data || data.length === 0) {
                container.innerHTML = `
                    <div style="text-align: center; padding: 48px; color: var(--text-muted);">
                        <div style="font-size: 48px; margin-bottom: 16px;">📦</div>
                        <h3 style="margin: 0 0 8px 0;">No Resources</h3>
                        <p style="margin: 0;">Provision Docker containers or Proxmox VMs to get started.</p>
                    </div>
                `;
                return;
            }
            
            // Group by type
            const grouped = {};
            data.forEach(resource => {
                const type = resource.resource_type;
                if (!grouped[type]) grouped[type] = [];
                grouped[type].push(resource);
            });
            
            let html = '';
            Object.entries(grouped).forEach(([type, resources]) => {
                const typeIcons = {
                    'docker_container': '🐳',
                    'proxmox_vm': '💻',
                    'proxmox_lxc': '📦'
                };
                const icon = typeIcons[type] || '⚙️';
                
                html += `
                    <div style="margin-bottom: 24px;">
                        <h3 style="margin: 0 0 12px 0; font-size: 14px; text-transform: uppercase; font-weight: 700; display: flex; align-items: center;">
                            <span style="font-size: 20px; margin-right: 8px;">${icon}</span>
                            ${type.replace(/_/g, ' ')} (${resources.length})
                        </h3>
                        ${resources.map(r => this.renderResource(r)).join('')}
                    </div>
                `;
            });
            
            container.innerHTML = html;
            
        } catch (error) {
            console.error('Failed to refresh resources list:', error);
        }
    };

    VeraChat.prototype.renderResource = function(resource) {
        const statusColors = {
            'available': 'var(--success)',
            'allocated': 'var(--warning)',
            'in_use': 'var(--info)',
            'error': 'var(--danger)',
            'stopping': 'var(--text-muted)'
        };
        const color = statusColors[resource.status] || 'var(--text-muted)';
        
        const idleTime = resource.last_used ? Math.floor((Date.now() / 1000) - resource.last_used) : 0;
        const idleText = idleTime > 0 ? `${Math.floor(idleTime / 60)}m ${idleTime % 60}s idle` : 'Active';
        
        return `
            <div style="padding: 16px; margin-bottom: 12px; background: var(--bg); border-radius: 8px; border-left: 4px solid ${color};">
                <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 12px;">
                    <div style="flex: 1;">
                        <div style="font-weight: 600; font-size: 14px; margin-bottom: 4px;">${resource.resource_id}</div>
                        <div style="font-size: 11px; color: var(--text-muted);">
                            ${resource.spec.cpu_cores} CPU • ${resource.spec.memory_mb}MB RAM • ${resource.spec.disk_gb}GB disk
                            ${resource.spec.gpu_count > 0 ? `• ${resource.spec.gpu_count} GPU` : ''}
                        </div>
                        ${resource.current_task_id ? `
                            <div style="margin-top: 8px; padding: 4px 8px; background: var(--bg-darker); border-radius: 4px; display: inline-block; font-size: 11px;">
                                ⚡ Task: ${resource.current_task_id.substring(0, 12)}...
                            </div>
                        ` : ''}
                    </div>
                    <div style="text-align: right;">
                        <span style="display: inline-block; padding: 4px 12px; border-radius: 12px; font-size: 11px; font-weight: 600; background: ${color}; color: white;">
                            ${resource.status.toUpperCase()}
                        </span>
                        <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">
                            ${resource.total_tasks} tasks • ${idleText}
                        </div>
                    </div>
                </div>
                
                <div style="display: flex; gap: 8px; margin-top: 12px;">
                    <button onclick="veraChat.viewResourceDetails('${resource.resource_id}')"
                            style="flex: 1; padding: 8px; background: var(--accent); border: none; border-radius: 6px; color: white; cursor: pointer; font-size: 12px; font-weight: 600;">
                        📊 Details
                    </button>
                    <button onclick="veraChat.executeInResource('${resource.resource_id}')"
                            style="flex: 1; padding: 8px; background: var(--success); border: none; border-radius: 6px; color: white; cursor: pointer; font-size: 12px; font-weight: 600;">
                        ▶️ Execute
                    </button>
                    <button onclick="veraChat.deleteResource('${resource.resource_id}')"
                            style="flex: 1; padding: 8px; background: var(--danger); border: none; border-radius: 6px; color: white; cursor: pointer; font-size: 12px; font-weight: 600;">
                        🗑️ Delete
                    </button>
                </div>
            </div>
        `;
    };

    VeraChat.prototype.provisionDockerContainer = async function() {
        const cpuCores = parseFloat(document.getElementById('docker-cpu')?.value) || 2;
        const memoryMb = parseInt(document.getElementById('docker-memory')?.value) || 2048;
        const diskGb = parseInt(document.getElementById('docker-disk')?.value) || 20;
        const image = document.getElementById('docker-image')?.value || 'python:3.11-slim';
        const taskType = document.getElementById('docker-task-type')?.value;
        
        try {
            this.addSystemMessage('Provisioning Docker container...', 'info');
            
            const response = await fetch(`${this.orchestratorExtState.infraApiUrl}/resources/docker/provision`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    spec: {
                        cpu_cores: cpuCores,
                        memory_mb: memoryMb,
                        disk_gb: diskGb,
                        gpu_count: 0
                    },
                    image: image,
                    task_type: taskType || undefined
                })
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || `HTTP ${response.status}`);
            }
            
            const data = await response.json();
            this.addSystemMessage(`✓ Container provisioned: ${data.resource_id}`, 'success');
            
            await this.refreshInfrastructure();
            
        } catch (error) {
            this.addSystemMessage(`Failed to provision: ${error.message}`, 'error');
        }
    };

    VeraChat.prototype.viewResourceDetails = async function(resourceId) {
        try {
            const response = await fetch(`${this.orchestratorExtState.infraApiUrl}/resources/${resourceId}`);
            const data = await response.json();
            
            let detailsHtml = `
                <div style="padding: 20px;">
                    <h3 style="margin: 0 0 16px 0; font-size: 16px; font-weight: 600;">Resource Details</h3>
                    
                    <div style="margin-bottom: 16px;">
                        <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">RESOURCE ID</div>
                        <div style="font-weight: 600;">${data.resource_id}</div>
                    </div>
                    
                    <div style="margin-bottom: 16px;">
                        <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">STATUS</div>
                        <div style="font-weight: 600; text-transform: uppercase;">${data.status}</div>
                    </div>
                    
                    <div style="margin-bottom: 16px;">
                        <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">SPECIFICATIONS</div>
                        <div style="font-size: 13px;">
                            ${data.spec.cpu_cores} CPU cores<br>
                            ${data.spec.memory_mb} MB RAM<br>
                            ${data.spec.disk_gb} GB disk<br>
                            ${data.spec.gpu_count} GPUs
                        </div>
                    </div>
                    
                    ${data.runtime_stats && Object.keys(data.runtime_stats).length > 0 ? `
                        <div style="margin-bottom: 16px;">
                            <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 8px;">RUNTIME STATS</div>
                            <div style="padding: 12px; background: var(--bg-darker); border-radius: 6px; font-size: 12px;">
                                ${data.runtime_stats.cpu_percent !== undefined ? `CPU: ${data.runtime_stats.cpu_percent.toFixed(1)}%<br>` : ''}
                                ${data.runtime_stats.memory_usage_mb !== undefined ? `Memory: ${data.runtime_stats.memory_usage_mb.toFixed(1)} MB<br>` : ''}
                                ${data.runtime_stats.memory_percent !== undefined ? `Memory %: ${data.runtime_stats.memory_percent.toFixed(1)}%<br>` : ''}
                            </div>
                        </div>
                    ` : ''}
                    
                    <div style="margin-bottom: 16px;">
                        <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">USAGE</div>
                        <div style="font-size: 13px;">
                            Total tasks completed: ${data.total_tasks}<br>
                            Created: ${new Date(data.created_at * 1000).toLocaleString()}<br>
                            Last used: ${new Date(data.last_used * 1000).toLocaleString()}
                        </div>
                    </div>
                </div>
            `;
            
            // Show in modal or panel
            const modal = document.getElementById('resource-details-modal');
            if (modal) {
                modal.innerHTML = detailsHtml;
                modal.style.display = 'block';
            } else {
                // Create temporary modal
                const tempModal = document.createElement('div');
                tempModal.style.cssText = 'position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); background: var(--bg-darker); border-radius: 12px; box-shadow: 0 8px 32px rgba(0,0,0,0.3); z-index: 10000; max-width: 500px; width: 90%;';
                tempModal.innerHTML = detailsHtml + `
                    <div style="padding: 0 20px 20px;">
                        <button onclick="this.parentElement.parentElement.remove()" 
                                style="width: 100%; padding: 12px; background: var(--accent); border: none; border-radius: 6px; color: white; cursor: pointer; font-weight: 600;">
                            Close
                        </button>
                    </div>
                `;
                document.body.appendChild(tempModal);
            }
            
        } catch (error) {
            this.addSystemMessage(`Failed to get details: ${error.message}`, 'error');
        }
    };

    VeraChat.prototype.executeInResource = async function(resourceId) {
        const command = prompt('Enter command to execute:', 'python --version');
        if (!command) return;
        
        try {
            this.addSystemMessage(`Executing: ${command}`, 'info');
            
            const response = await fetch(`${this.orchestratorExtState.infraApiUrl}/resources/${resourceId}/execute`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ command: command })
            });
            
            const data = await response.json();
            
            if (data.status === 'success') {
                this.addSystemMessage(`✓ Exit code: ${data.exit_code}\nOutput:\n${data.output}`, 'success');
            } else {
                this.addSystemMessage(`✗ Execution failed: ${data.output}`, 'error');
            }
            
        } catch (error) {
            this.addSystemMessage(`Failed to execute: ${error.message}`, 'error');
        }
    };

    VeraChat.prototype.deleteResource = async function(resourceId) {
        if (!confirm(`Delete resource ${resourceId}?`)) return;
        
        try {
            const response = await fetch(`${this.orchestratorExtState.infraApiUrl}/resources/${resourceId}`, {
                method: 'DELETE'
            });
            
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            this.addSystemMessage(`✓ Resource deleted: ${resourceId}`, 'success');
            await this.refreshInfrastructure();
            
        } catch (error) {
            this.addSystemMessage(`Failed to delete: ${error.message}`, 'error');
        }
    };

    VeraChat.prototype.cleanupIdleResources = async function() {
        const maxIdleSeconds = parseInt(document.getElementById('cleanup-idle-time')?.value) || 300;
        
        try {
            this.addSystemMessage('Cleaning up idle resources...', 'info');
            
            const response = await fetch(`${this.orchestratorExtState.infraApiUrl}/resources/cleanup`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ max_idle_seconds: maxIdleSeconds })
            });
            
            const data = await response.json();
            this.addSystemMessage(data.message, 'success');
            
            await this.refreshInfrastructure();
            
        } catch (error) {
            this.addSystemMessage(`Cleanup failed: ${error.message}`, 'error');
        }
    };

    // ========================================================================
    // EXTERNAL API MANAGEMENT
    // ========================================================================
    
    VeraChat.prototype.refreshExternalAPIs = async function() {
        await Promise.all([
            this.refreshExternalHealth(),
            this.refreshProviders(),
            this.refreshExternalStats()
        ]);
    };

    VeraChat.prototype.refreshExternalHealth = async function() {
        try {
            const response = await fetch(`${this.orchestratorExtState.externalApiUrl}/health`);
            const data = await response.json();
            
            const indicator = document.getElementById('external-indicator');
            const providersCount = document.getElementById('external-providers-count');
            
            if (indicator) {
                indicator.style.background = data.status === 'healthy' ? '#22c55e' : '#ef4444';
            }
            
            if (providersCount) {
                providersCount.textContent = data.providers_available || 0;
            }
            
        } catch (error) {
            console.error('External API health check failed:', error);
        }
    };

    VeraChat.prototype.refreshProviders = async function() {
        try {
            const response = await fetch(`${this.orchestratorExtState.externalApiUrl}/providers`);
            const data = await response.json();
            
            const container = document.getElementById('external-providers-list');
            if (!container) return;
            
            if (!data.providers || data.providers.length === 0) {
                container.innerHTML = `
                    <div style="text-align: center; padding: 48px; color: var(--text-muted);">
                        <div style="font-size: 48px; margin-bottom: 16px;">🔌</div>
                        <h3 style="margin: 0 0 8px 0;">No Providers Configured</h3>
                        <p style="margin: 0;">Initialize external APIs to connect to LLM providers and cloud compute.</p>
                    </div>
                `;
                return;
            }
            
            // Group by type
            const llmProviders = data.providers.filter(p => p.type === 'llm');
            const computeProviders = data.providers.filter(p => p.type === 'compute');
            
            let html = '';
            
            if (llmProviders.length > 0) {
                html += `
                    <div style="margin-bottom: 24px;">
                        <h3 style="margin: 0 0 12px 0; font-size: 14px; text-transform: uppercase; font-weight: 700; color: var(--accent);">
                            🤖 LLM PROVIDERS (${llmProviders.length})
                        </h3>
                        ${llmProviders.map(p => this.renderProvider(p)).join('')}
                    </div>
                `;
            }
            
            if (computeProviders.length > 0) {
                html += `
                    <div style="margin-bottom: 24px;">
                        <h3 style="margin: 0 0 12px 0; font-size: 14px; text-transform: uppercase; font-weight: 700; color: var(--success);">
                            ☁️ COMPUTE PROVIDERS (${computeProviders.length})
                        </h3>
                        ${computeProviders.map(p => this.renderProvider(p)).join('')}
                    </div>
                `;
            }
            
            container.innerHTML = html;
            
        } catch (error) {
            console.error('Failed to refresh providers:', error);
        }
    };

    VeraChat.prototype.renderProvider = function(provider) {
        const providerIcons = {
            'openai': '🟢',
            'anthropic': '🔵',
            'google': '🔴',
            'aws_lambda': '🟠',
            'runpod': '🟣'
        };
        const icon = providerIcons[provider.provider] || '⚪';
        
        return `
            <div style="padding: 16px; margin-bottom: 12px; background: var(--bg); border-radius: 8px; border-left: 4px solid var(--accent);">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <span style="font-size: 24px;">${icon}</span>
                        <div>
                            <div style="font-weight: 600; font-size: 14px; text-transform: capitalize;">${provider.provider.replace(/_/g, ' ')}</div>
                            <div style="font-size: 11px; color: var(--text-muted);">${provider.type.toUpperCase()}</div>
                        </div>
                    </div>
                    <span style="padding: 4px 12px; border-radius: 12px; font-size: 11px; font-weight: 600; background: var(--success); color: white;">
                        ✓ INITIALIZED
                    </span>
                </div>
                
                <div style="display: flex; gap: 8px;">
                    <button onclick="veraChat.viewProviderStats('${provider.provider}')"
                            style="flex: 1; padding: 8px; background: var(--accent); border: none; border-radius: 6px; color: white; cursor: pointer; font-size: 12px; font-weight: 600;">
                        📊 Stats
                    </button>
                    ${provider.type === 'llm' ? `
                        <button onclick="veraChat.testLLMProvider('${provider.provider}')"
                                style="flex: 1; padding: 8px; background: var(--success); border: none; border-radius: 6px; color: white; cursor: pointer; font-size: 12px; font-weight: 600;">
                            🧪 Test
                        </button>
                    ` : ''}
                </div>
            </div>
        `;
    };

    VeraChat.prototype.refreshExternalStats = async function() {
        try {
            const [statsResponse, costResponse, tokenResponse] = await Promise.all([
                fetch(`${this.orchestratorExtState.externalApiUrl}/stats`),
                fetch(`${this.orchestratorExtState.externalApiUrl}/stats/cost/summary`),
                fetch(`${this.orchestratorExtState.externalApiUrl}/stats/tokens/summary`)
            ]);
            
            const stats = await statsResponse.json();
            const cost = await costResponse.json();
            const tokens = await tokenResponse.json();
            
            // Update cost display
            document.getElementById('external-total-cost')?.textContent = `$${cost.total_cost.toFixed(2)}`;
            
            // Update token display
            const totalTokens = tokens.total_tokens || 0;
            document.getElementById('external-total-tokens')?.textContent = totalTokens.toLocaleString();
            
            // Update requests display
            const totalRequests = stats.total_requests || 0;
            document.getElementById('external-total-requests')?.textContent = totalRequests;
            
            // Cost breakdown chart
            if (cost.by_provider && Object.keys(cost.by_provider).length > 0) {
                const costHtml = `
                    <div style="margin-top: 16px;">
                        <h4 style="font-size: 12px; text-transform: uppercase; color: var(--text-muted); margin: 0 0 12px 0;">Cost by Provider</h4>
                        ${Object.entries(cost.by_provider).map(([provider, providerCost]) => {
                            const percentage = cost.total_cost > 0 ? (providerCost / cost.total_cost * 100) : 0;
                            return `
                                <div style="margin-bottom: 12px;">
                                    <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 4px;">
                                        <span style="text-transform: capitalize;">${provider.replace(/_/g, ' ')}</span>
                                        <span style="font-weight: 600;">$${providerCost.toFixed(2)} (${percentage.toFixed(1)}%)</span>
                                    </div>
                                    <div style="height: 8px; background: var(--bg-darker); border-radius: 4px; overflow: hidden;">
                                        <div style="height: 100%; background: var(--accent); width: ${percentage}%; transition: width 0.3s;"></div>
                                    </div>
                                </div>
                            `;
                        }).join('')}
                    </div>
                `;
                
                const costContainer = document.getElementById('external-cost-breakdown');
                if (costContainer) costContainer.innerHTML = costHtml;
            }
            
        } catch (error) {
            console.error('Failed to refresh external stats:', error);
        }
    };

    VeraChat.prototype.viewProviderStats = async function(provider) {
        try {
            const response = await fetch(`${this.orchestratorExtState.externalApiUrl}/stats/${provider}`);
            const data = await response.json();
            
            const statsHtml = `
                <div style="padding: 20px;">
                    <h3 style="margin: 0 0 16px 0; font-size: 16px; font-weight: 600; text-transform: capitalize;">
                        ${data.provider.replace(/_/g, ' ')} Statistics
                    </h3>
                    
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px;">
                        <div style="padding: 12px; background: var(--bg-darker); border-radius: 6px;">
                            <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">TOTAL REQUESTS</div>
                            <div style="font-size: 20px; font-weight: 600;">${data.total_requests}</div>
                        </div>
                        <div style="padding: 12px; background: var(--bg-darker); border-radius: 6px;">
                            <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">SUCCESS RATE</div>
                            <div style="font-size: 20px; font-weight: 600; color: ${data.success_rate > 0.9 ? 'var(--success)' : 'var(--warning)'};">
                                ${(data.success_rate * 100).toFixed(1)}%
                            </div>
                        </div>
                        <div style="padding: 12px; background: var(--bg-darker); border-radius: 6px;">
                            <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">TOTAL COST</div>
                            <div style="font-size: 20px; font-weight: 600;">$${data.total_cost_usd.toFixed(2)}</div>
                        </div>
                        <div style="padding: 12px; background: var(--bg-darker); border-radius: 6px;">
                            <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">AVG LATENCY</div>
                            <div style="font-size: 20px; font-weight: 600;">${data.avg_latency_ms.toFixed(0)}ms</div>
                        </div>
                    </div>
                    
                    ${data.total_tokens_in || data.total_tokens_out ? `
                        <div style="margin-bottom: 16px;">
                            <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 8px;">TOKEN USAGE</div>
                            <div style="padding: 12px; background: var(--bg-darker); border-radius: 6px; font-size: 12px;">
                                Input: ${data.total_tokens_in.toLocaleString()}<br>
                                Output: ${data.total_tokens_out.toLocaleString()}<br>
                                Total: ${(data.total_tokens_in + data.total_tokens_out).toLocaleString()}
                            </div>
                        </div>
                    ` : ''}
                    
                    <div style="margin-bottom: 16px;">
                        <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 8px;">STATUS</div>
                        <div style="padding: 12px; background: var(--bg-darker); border-radius: 6px; font-size: 12px;">
                            Successful: ${data.successful_requests}<br>
                            Failed: ${data.failed_requests}
                        </div>
                    </div>
                </div>
            `;
            
            // Show in modal
            const tempModal = document.createElement('div');
            tempModal.style.cssText = 'position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); background: var(--bg-darker); border-radius: 12px; box-shadow: 0 8px 32px rgba(0,0,0,0.3); z-index: 10000; max-width: 500px; width: 90%;';
            tempModal.innerHTML = statsHtml + `
                <div style="padding: 0 20px 20px;">
                    <button onclick="this.parentElement.parentElement.remove()" 
                            style="width: 100%; padding: 12px; background: var(--accent); border: none; border-radius: 6px; color: white; cursor: pointer; font-weight: 600;">
                        Close
                    </button>
                </div>
            `;
            document.body.appendChild(tempModal);
            
        } catch (error) {
            this.addSystemMessage(`Failed to get stats: ${error.message}`, 'error');
        }
    };

    VeraChat.prototype.testLLMProvider = async function(provider) {
        const prompt = prompt('Enter test prompt:', 'Hello! How are you?');
        if (!prompt) return;
        
        try {
            this.addSystemMessage(`Testing ${provider}...`, 'info');
            
            const response = await fetch(`${this.orchestratorExtState.externalApiUrl}/execute`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    provider: provider,
                    task_name: 'llm.test',
                    prompt: prompt
                })
            });
            
            const data = await response.json();
            
            if (data.status === 'success') {
                this.addSystemMessage(
                    `✓ ${provider} test successful\nResponse: ${data.result}\n` +
                    `Cost: $${data.cost_usd?.toFixed(4) || 0} | Tokens: ${data.tokens_in || 0}→${data.tokens_out || 0}`,
                    'success'
                );
                
                await this.refreshExternalStats();
            } else {
                this.addSystemMessage(`✗ Test failed: ${data.error || 'Unknown error'}`, 'error');
            }
            
        } catch (error) {
            this.addSystemMessage(`Test failed: ${error.message}`, 'error');
        }
    };

    // ========================================================================
    // PERIODIC UPDATES
    // ========================================================================
    
    VeraChat.prototype.startResourceUpdates = function() {
        if (this.orchestratorExtState.resourceUpdateInterval) {
            clearInterval(this.orchestratorExtState.resourceUpdateInterval);
        }
        
        this.orchestratorExtState.resourceUpdateInterval = setInterval(() => {
            if (this.orchestratorState.currentPanel === 'infrastructure') {
                this.refreshResourcesList();
                this.refreshInfrastructureStats();
            }
        }, 5000);
    };

    VeraChat.prototype.stopResourceUpdates = function() {
        if (this.orchestratorExtState.resourceUpdateInterval) {
            clearInterval(this.orchestratorExtState.resourceUpdateInterval);
            this.orchestratorExtState.resourceUpdateInterval = null;
        }
    };

    VeraChat.prototype.startCostUpdates = function() {
        if (this.orchestratorExtState.costUpdateInterval) {
            clearInterval(this.orchestratorExtState.costUpdateInterval);
        }
        
        this.orchestratorExtState.costUpdateInterval = setInterval(() => {
            if (this.orchestratorState.currentPanel === 'external') {
                this.refreshExternalStats();
            }
        }, 10000);
    };

    VeraChat.prototype.stopCostUpdates = function() {
        if (this.orchestratorExtState.costUpdateInterval) {
            clearInterval(this.orchestratorExtState.costUpdateInterval);
            this.orchestratorExtState.costUpdateInterval = null;
        }
    };

    // ========================================================================
    // CLEANUP EXTENSION
    // ========================================================================
    
    const originalCleanupOrchestrator = VeraChat.prototype.cleanupOrchestrator;
    VeraChat.prototype.cleanupOrchestrator = function() {
        originalCleanupOrchestrator.call(this);
        
        this.stopResourceUpdates();
        this.stopCostUpdates();
    };

    console.log('Orchestrator UI extensions loaded');

})();