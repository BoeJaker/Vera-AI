/**
 * Session History Manager - Vanilla JavaScript
 * No frameworks, no dependencies, just plain JS
 */

class SessionHistory {
    constructor(config = {}) {
        this.config = {
            containerId: config.containerId || 'session-history',
            apiBaseUrl: config.apiBaseUrl || '/api/session',
            currentSessionId: config.currentSessionId || null,
            onLoadSession: config.onLoadSession || (() => {}),
            autoRefresh: config.autoRefresh || false,
            refreshInterval: config.refreshInterval || 30000
        };

        this.state = {
            sessions: [],
            searchResults: null,
            loading: false,
            searchQuery: '',
            sortBy: 'date',
            sortOrder: 'desc',
            showFilters: false,
            dateFrom: '',
            dateTo: '',
            stats: null,
            expandedSession: null,
            similarSessions: {}
        };

        // Debounce timer for search input
        this.searchDebounceTimer = null;
        
        // Throttle detail requests to prevent browser resource exhaustion
        this.detailRequestInProgress = false;

        this.container = null;
        this.init();
    }

    init() {
        this.container = document.getElementById(this.config.containerId);
        if (!this.container) {
            console.error(`Container #${this.config.containerId} not found`);
            return;
        }

        this.render();
        this.loadSessions();
        this.loadStats();

        if (this.config.autoRefresh) {
            setInterval(() => this.loadSessions(), this.config.refreshInterval);
        }
    }

    // API Methods
    async loadSessions() {
        this.setState({ loading: true });
        try {
            const params = new URLSearchParams({
                sort_by: this.state.sortBy,
                sort_order: this.state.sortOrder,
                limit: '50'
            });

            if (this.state.dateFrom) params.append('date_from', this.state.dateFrom);
            if (this.state.dateTo) params.append('date_to', this.state.dateTo);

            const response = await fetch(`${this.config.apiBaseUrl}/history?${params}`);
            
            if (!response.ok) {
                throw new Error(`API returned ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            // Ensure data is an array
            if (!Array.isArray(data)) {
                console.warn('API returned non-array data:', data);
                this.setState({ 
                    sessions: [], 
                    searchResults: null,
                    loading: false 
                });
                return;
            }
            
            this.setState({ 
                sessions: data, 
                searchResults: null,
                loading: false 
            });
        } catch (error) {
            console.error('Error loading sessions:', error);
            this.setState({ 
                sessions: [],
                loading: false 
            });
        }
    }

    async loadStats() {
        try {
            const response = await fetch(`${this.config.apiBaseUrl}/stats/summary`);
            
            if (!response.ok) {
                throw new Error(`Stats API returned ${response.status}`);
            }
            
            const data = await response.json();
            this.setState({ stats: data });
        } catch (error) {
            console.error('Error loading stats:', error);
            this.setState({ 
                stats: { 
                    total_sessions: 0, 
                    active_sessions: 0, 
                    archived_sessions: 0 
                } 
            });
        }
    }

    async searchSessions() {
        if (!this.state.searchQuery.trim()) {
            this.loadSessions();
            return;
        }

        this.setState({ loading: true });
        try {
            const response = await fetch(`${this.config.apiBaseUrl}/search`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query: this.state.searchQuery,
                    limit: 20
                })
            });
            
            if (!response.ok) {
                throw new Error(`Search API returned ${response.status}`);
            }
            
            const data = await response.json();
            
            // Ensure data is an array
            if (!Array.isArray(data)) {
                console.warn('Search returned non-array data:', data);
                this.setState({ searchResults: [], loading: false });
                return;
            }
            
            this.setState({ searchResults: data, loading: false });
        } catch (error) {
            console.error('Error searching sessions:', error);
            this.setState({ 
                searchResults: [],
                loading: false 
            });
        }
    }

    async loadSessionDetails(sessionId) {
        // Prevent multiple simultaneous requests
        if (this.detailRequestInProgress) {
            console.log('Detail request already in progress, skipping...');
            return;
        }
        
        if (this.state.expandedSession === sessionId) {
            this.setState({ expandedSession: null });
            return;
        }

        this.detailRequestInProgress = true;
        
        try {
            const response = await fetch(`${this.config.apiBaseUrl}/${sessionId}/details`);
            
            if (!response.ok) {
                throw new Error(`API returned ${response.status}`);
            }
            
            const data = await response.json();
            
            this.setState({ expandedSession: sessionId });
            
            // Update session with details
            const sessions = this.state.sessions.map(s =>
                s.session_id === sessionId ? { ...s, details: data } : s
            );
            this.setState({ sessions });
        } catch (error) {
            console.error('Error loading session details:', error);
        } finally {
            // Always clear the flag
            this.detailRequestInProgress = false;
        }
    }

    async loadSimilarSessions(sessionId) {
        try {
            const response = await fetch(`${this.config.apiBaseUrl}/${sessionId}/similar?limit=3`);
            const data = await response.json();
            
            const similarSessions = { ...this.state.similarSessions };
            similarSessions[sessionId] = data;
            this.setState({ similarSessions });
        } catch (error) {
            console.error('Error loading similar sessions:', error);
        }
    }

    async resumeSession(sessionId) {
        try {
            const response = await fetch(`${this.config.apiBaseUrl}/${sessionId}/resume`, {
                method: 'POST'
            });
            const data = await response.json();
            
            if (data.session_id) {
                this.config.currentSessionId = data.session_id;
                this.config.onLoadSession(data.session_id);
                this.render(); // Re-render to highlight current session
            }
        } catch (error) {
            console.error('Error resuming session:', error);
        }
    }

    // Utility Methods
    setState(newState) {
        this.state = { ...this.state, ...newState };
        this.render();
    }

    formatDate(isoString) {
        if (!isoString) return 'Unknown';
        const date = new Date(isoString);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        if (diffDays < 7) return `${diffDays}d ago`;
        return date.toLocaleDateString();
    }

    // Render Methods
    render() {
        if (!this.container) return;

        const displaySessions = this.state.searchResults || this.state.sessions;

        this.container.innerHTML = `
            <div class="session-history">
                ${this.renderHeader()}
                ${this.renderSessionList(displaySessions)}
            </div>
        `;

        this.attachEventListeners();
    }

    renderHeader() {
        const { stats, searchQuery, showFilters, sortBy, sortOrder, dateFrom, dateTo } = this.state;

        return `
            <div class="sh-header">
                <h2 class="sh-title">Session History</h2>
                
                ${stats ? `
                    <div class="sh-stats">
                        <span>Total: ${stats.total_sessions || 0}</span>
                        <span>Active: ${stats.active_sessions || 0}</span>
                        <span>Loaded: ${stats.currently_loaded || 0}</span>
                    </div>
                ` : ''}

                <div class="sh-search-wrapper">
                    <input 
                        type="text" 
                        class="sh-search-input" 
                        placeholder="Search conversations..."
                        value="${searchQuery}"
                        data-action="search-input"
                    />
                    <button class="sh-search-button" data-action="search-button" title="Search">
                        🔍
                    </button>
                    ${searchQuery ? `
                        <button class="sh-clear-search" data-action="clear-search" title="Clear">✕</button>
                    ` : ''}
                </div>

                <button class="sh-filter-btn ${showFilters ? 'active' : ''}" data-action="toggle-filters">
                    🔧 Filters
                </button>

                ${showFilters ? `
                    <div class="sh-filters">
                        <div class="sh-filter-grid">
                            <div class="sh-filter-group">
                                <label>Sort By</label>
                                <select class="sh-select" data-action="sort-by">
                                    <option value="date" ${sortBy === 'date' ? 'selected' : ''}>Date</option>
                                    <option value="message_count" ${sortBy === 'message_count' ? 'selected' : ''}>Messages</option>
                                </select>
                            </div>
                            <div class="sh-filter-group">
                                <label>Order</label>
                                <select class="sh-select" data-action="sort-order">
                                    <option value="desc" ${sortOrder === 'desc' ? 'selected' : ''}>Newest First</option>
                                    <option value="asc" ${sortOrder === 'asc' ? 'selected' : ''}>Oldest First</option>
                                </select>
                            </div>
                            <div class="sh-filter-group">
                                <label>From Date</label>
                                <input type="date" class="sh-input" value="${dateFrom}" data-action="date-from" />
                            </div>
                            <div class="sh-filter-group">
                                <label>To Date</label>
                                <input type="date" class="sh-input" value="${dateTo}" data-action="date-to" />
                            </div>
                        </div>
                    </div>
                ` : ''}
            </div>
        `;
    }

    renderSessionList(sessions) {
        if (this.state.loading) {
            return '<div class="sh-loading">Loading sessions...</div>';
        }

        if (!sessions || sessions.length === 0) {
            return `
                <div class="sh-empty">
                    ${this.state.searchQuery ? 'No sessions found' : 'No sessions yet'}
                </div>
            `;
        }

        return `
            <div class="sh-session-list">
                ${sessions.map(session => this.renderSessionCard(session)).join('')}
            </div>
        `;
    }

    renderSessionCard(session) {
        const isCurrentSession = session.session_id === this.config.currentSessionId;
        const isExpanded = this.state.expandedSession === session.session_id;
        const similar = this.state.similarSessions[session.session_id];

        return `
            <div class="sh-session-card ${isCurrentSession ? 'current' : ''}" data-session-id="${session.session_id}">
                <div class="sh-card-main">
                    <div class="sh-card-content">
                        <div class="sh-card-header">
                            <span class="sh-card-time">
                                🕐 ${this.formatDate(session.started_at)}
                                ${isCurrentSession ? '<span class="sh-badge">ACTIVE</span>' : ''}
                            </span>
                        </div>
                        
                        ${session.preview ? `
                            <div class="sh-card-preview">${this.escapeHtml(session.preview)}</div>
                        ` : ''}
                        
                        <div class="sh-card-meta">
                            <span>💬 ${session.message_count || 0} messages</span>
                            ${session.relevance_score ? `
                                <span class="sh-relevance">
                                    Relevance: ${(session.relevance_score * 100).toFixed(0)}%
                                </span>
                            ` : ''}
                        </div>
                    </div>

                    <div class="sh-card-actions">
                        <button 
                            class="sh-btn sh-btn-expand" 
                            data-action="expand"
                            data-session-id="${session.session_id}"
                            title="View details"
                        >
                            ${isExpanded ? '▲' : '▼'}
                        </button>
                        ${!isCurrentSession ? `
                            <button 
                                class="sh-btn sh-btn-load" 
                                data-action="load"
                                data-session-id="${session.session_id}"
                            >
                                Load
                            </button>
                        ` : ''}
                    </div>
                </div>

                ${isExpanded && session.details ? this.renderSessionDetails(session) : ''}
            </div>
        `;
    }

    renderSessionDetails(session) {
        const details = session.details;
        const similar = this.state.similarSessions[session.session_id];

        return `
            <div class="sh-card-details">
                ${details.entities && details.entities.length > 0 ? `
                    <div class="sh-details-section">
                        <div class="sh-details-label">Key Entities</div>
                        <div class="sh-entity-tags">
                            ${details.entities.slice(0, 10).map(entity => `
                                <span class="sh-entity-tag">
                                    ${this.escapeHtml(entity.text || entity.id)}
                                </span>
                            `).join('')}
                        </div>
                    </div>
                ` : ''}

                ${details.messages && details.messages.length > 0 ? `
                    <div class="sh-details-section">
                        <div class="sh-details-label">Recent Messages</div>
                        <div class="sh-messages">
                            ${details.messages.slice(-5).map(msg => `
                                <div class="sh-message">
                                    ${this.escapeHtml((msg.text || '').substring(0, 150))}
                                    ${msg.text && msg.text.length > 150 ? '...' : ''}
                                </div>
                            `).join('')}
                        </div>
                    </div>
                ` : ''}

                <div class="sh-details-section">
                    ${!similar ? `
                        <button 
                            class="sh-btn sh-btn-similar" 
                            data-action="load-similar"
                            data-session-id="${session.session_id}"
                        >
                            Find Similar Sessions
                        </button>
                    ` : similar.length > 0 ? `
                        <div class="sh-details-label">Similar Sessions</div>
                        ${similar.map(sim => `
                            <div 
                                class="sh-similar-session" 
                                data-action="load"
                                data-session-id="${sim.session_id}"
                            >
                                <div class="sh-similar-meta">
                                    ${this.formatDate(sim.started_at)} • 
                                    ${(sim.relevance_score * 100).toFixed(0)}% similar
                                </div>
                                <div class="sh-similar-preview">
                                    ${this.escapeHtml((sim.preview || '').substring(0, 100))}...
                                </div>
                            </div>
                        `).join('')}
                    ` : ''}
                </div>
            </div>
        `;
    }

    // Event Handlers
    attachEventListeners() {
        this.container.addEventListener('click', (e) => {
            const target = e.target.closest('[data-action]');
            if (!target) return;

            const action = target.dataset.action;
            const sessionId = target.dataset.sessionId;

            switch (action) {
                case 'toggle-filters':
                    this.setState({ showFilters: !this.state.showFilters });
                    break;
                case 'search-button':
                    // Trigger search when button clicked
                    if (this.state.searchQuery.trim()) {
                        this.searchSessions();
                    }
                    break;
                case 'clear-search':
                    // Clear the search query
                    this.state.searchQuery = '';
                    this.state.searchResults = null;
                    
                    // Clear the actual input element
                    const searchInput = this.container.querySelector('[data-action="search-input"]');
                    if (searchInput) {
                        searchInput.value = '';
                    }
                    
                    // Reload sessions
                    this.loadSessions();
                    break;
                case 'expand':
                    this.loadSessionDetails(sessionId);
                    break;
                case 'load':
                    this.resumeSession(sessionId);
                    break;
                case 'load-similar':
                    this.loadSimilarSessions(sessionId);
                    break;
            }
        });

        this.container.addEventListener('change', (e) => {
            const target = e.target.closest('[data-action]');
            if (!target) return;

            const action = target.dataset.action;
            const value = target.value;

            switch (action) {
                case 'sort-by':
                    this.state.sortBy = value;
                    this.loadSessions();
                    break;
                case 'sort-order':
                    this.state.sortOrder = value;
                    this.loadSessions();
                    break;
                case 'date-from':
                    this.state.dateFrom = value;
                    this.loadSessions();
                    break;
                case 'date-to':
                    this.state.dateTo = value;
                    this.loadSessions();
                    break;
            }
        });

        this.container.addEventListener('input', (e) => {
            const target = e.target.closest('[data-action]');
            if (!target) return;

            if (target.dataset.action === 'search-input') {
                // Just update the value, don't trigger search
                this.state.searchQuery = target.value;
            }
        });

        this.container.addEventListener('keypress', (e) => {
            const target = e.target.closest('[data-action]');
            if (!target) return;

            if (target.dataset.action === 'search-input' && e.key === 'Enter') {
                this.searchSessions();
            }
        });
    }

    // Helper
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Public Methods
    setCurrentSession(sessionId) {
        this.config.currentSessionId = sessionId;
        this.render();
    }

    refresh() {
        this.loadSessions();
        this.loadStats();
    }

    destroy() {
        // Clear debounce timer
        if (this.searchDebounceTimer) {
            clearTimeout(this.searchDebounceTimer);
        }
        
        // Clear refresh interval
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }
        
        if (this.container) {
            this.container.innerHTML = '';
        }
    }
}

// Export for use in modules or direct usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SessionHistory;
}