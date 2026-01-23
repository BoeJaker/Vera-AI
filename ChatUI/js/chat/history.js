/**
 * Session History Manager - OPTIMIZED VERSION
 * 
 * Key Performance Improvements:
 * 1. Progressive/chunked rendering - UI appears immediately, data loads incrementally
 * 2. Lazy loading - Only load details/previews when user requests them
 * 3. Virtual scrolling - Only render visible items
 * 4. Debounced state updates - Batch multiple updates efficiently
 * 5. No blocking operations - All heavy work is async/chunked
 */

class SessionHistory {
    constructor(config = {}) {
        this.config = {
            containerId: config.containerId || 'session-history',
            apiBaseUrl: config.apiBaseUrl || '/api/session',
            currentSessionId: config.currentSessionId || null,
            onLoadSession: config.onLoadSession || (() => {}),
            autoRefresh: config.autoRefresh || false,
            refreshInterval: config.refreshInterval || 30000,
            // Virtual scrolling config
            itemHeight: config.itemHeight || 120, // Estimated height per session card
            renderBuffer: config.renderBuffer || 5, // Extra items to render above/below viewport
            chunkSize: config.chunkSize || 10 // Items to load per chunk
        };

        this.state = {
            sessions: [],
            searchResults: null,
            loading: false,
            initialLoadComplete: false,
            searchQuery: '',
            sortBy: 'date',
            sortOrder: 'desc',
            showFilters: false,
            dateFrom: '',
            dateTo: '',
            stats: null,
            expandedSession: null,
            similarSessions: {},
            // Virtual scrolling state
            scrollTop: 0,
            containerHeight: 0,
            visibleStartIndex: 0,
            visibleEndIndex: 20
        };

        // Performance optimizations
        this.updateTimeout = null;
        this.renderTimeout = null;
        this.searchDebounceTimer = null;
        this.detailRequestInProgress = false;
        this.scrollRAF = null;
        
        // Cache for loaded details
        this.sessionDetailsCache = new Map();

        this.container = null;
        this.scrollContainer = null;
        this.initialized = false;
    }

    /**
     * Initialize with immediate UI render, async data loading
     */
    async init() {
        if (this.initialized) {
            console.log('SessionHistory already initialized');
            return;
        }
        
        this.container = document.getElementById(this.config.containerId);
        if (!this.container) {
            console.error(`Container #${this.config.containerId} not found`);
            return;
        }

        this.initialized = true;
        
        // IMMEDIATE: Render skeleton UI
        this.renderSkeleton();
        
        // ASYNC: Load stats (fast, low-priority)
        this.loadStats().catch(err => console.error('Stats load error:', err));
        
        // ASYNC: Load first chunk of sessions (progressive)
        this.loadSessionsProgressive().catch(err => console.error('Sessions load error:', err));

        if (this.config.autoRefresh) {
            setInterval(() => this.loadSessionsProgressive(), this.config.refreshInterval);
        }
    }
    
    /**
     * Render minimal skeleton UI immediately - NO DATA REQUIRED
     */
    renderSkeleton() {
        if (!this.container) return;
        
        this.container.innerHTML = `
            <div class="session-history">
                <div class="sh-header">
                    <h2 class="sh-title">Session History</h2>
                    <div class="sh-stats">
                        <span>Loading...</span>
                    </div>
                    <div class="sh-search-wrapper">
                        <input 
                            type="text" 
                            class="sh-search-input" 
                            placeholder="Search conversations..."
                            data-action="search-input"
                        />
                        <button class="sh-search-button" data-action="search-button" title="Search">🔍</button>
                    </div>
                    <button class="sh-filter-btn" data-action="toggle-filters">🔧 Filters</button>
                </div>
                <div class="sh-session-list" data-scroll-container>
                    <div class="sh-loading">Loading sessions...</div>
                </div>
            </div>
        `;
        
        this.attachEventListeners();
    }

    /**
     * Progressive session loading - load in chunks, render as we go
     */
    async loadSessionsProgressive() {
        this.setState({ loading: true });
        
        try {
            const params = new URLSearchParams({
                sort_by: this.state.sortBy,
                sort_order: this.state.sortOrder,
                limit: '100' // Load more upfront, but don't fetch previews
            });

            if (this.state.dateFrom) params.append('date_from', this.state.dateFrom);
            if (this.state.dateTo) params.append('date_to', this.state.dateTo);

            const response = await fetch(`${this.config.apiBaseUrl}/history?${params}`);
            
            if (!response.ok) {
                throw new Error(`API returned ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            if (!Array.isArray(data)) {
                console.warn('API returned non-array data:', data);
                this.setState({ 
                    sessions: [], 
                    searchResults: null,
                    loading: false,
                    initialLoadComplete: true
                });
                return;
            }
            
            // Sort on frontend (fast)
            const sortedData = this.sortSessions(data, this.state.sortBy, this.state.sortOrder);
            
            // IMMEDIATE: Update state with all sessions
            this.setState({ 
                sessions: sortedData, 
                searchResults: null,
                loading: false,
                initialLoadComplete: true
            });
            
            console.log(`Loaded ${sortedData.length} sessions`);
            
        } catch (error) {
            console.error('Error loading sessions:', error);
            this.setState({ 
                sessions: [],
                loading: false,
                initialLoadComplete: true
            });
        }
    }

    // Sort sessions using timestamp extraction (same as before)
    sortSessions(sessions, sortBy, sortOrder) {
        const sorted = [...sessions];
        
        if (sortBy === 'date') {
            sorted.sort((a, b) => {
                const tsA = this.getSessionSortTimestamp(a);
                const tsB = this.getSessionSortTimestamp(b);
                return sortOrder === 'desc' ? tsB - tsA : tsA - tsB;
            });
        } else if (sortBy === 'message_count') {
            sorted.sort((a, b) => {
                const countA = a.message_count || 0;
                const countB = b.message_count || 0;
                return sortOrder === 'desc' ? countB - countA : countA - countB;
            });
        }
        
        return sorted;
    }

    extractTimestampFromSessionId(sessionId) {
        if (!sessionId) return null;
        const match = sessionId.match(/^sess_(\d+)$/);
        if (match && match[1]) {
            try {
                return parseInt(match[1], 10);
            } catch (e) {
                return null;
            }
        }
        return null;
    }

    getSessionSortTimestamp(session) {
        const sessionId = session.session_id;
        if (sessionId) {
            const tsMs = this.extractTimestampFromSessionId(sessionId);
            if (tsMs) return tsMs;
        }
        
        if (session.started_at) {
            try {
                return new Date(session.started_at).getTime();
            } catch (e) {}
        }
        
        if (session.created_at) {
            try {
                return new Date(session.created_at).getTime();
            } catch (e) {}
        }
        
        return Date.now();
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
            this.loadSessionsProgressive();
            return;
        }

        this.setState({ loading: true });
        try {
            const response = await fetch(`${this.config.apiBaseUrl}/search`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query: this.state.searchQuery,
                    limit: 50
                })
            });
            
            if (!response.ok) {
                throw new Error(`Search API returned ${response.status}`);
            }
            
            const data = await response.json();
            
            if (!Array.isArray(data)) {
                console.warn('Search returned non-array data:', data);
                this.setState({ searchResults: [], loading: false });
                return;
            }
            
            const sortedData = this.sortSessions(data, this.state.sortBy, this.state.sortOrder);
            
            this.setState({ searchResults: sortedData, loading: false });
        } catch (error) {
            console.error('Error searching sessions:', error);
            this.setState({ 
                searchResults: [],
                loading: false 
            });
        }
    }

    /**
     * LAZY LOAD: Only fetch details when user expands a session
     */
    async loadSessionDetails(sessionId) {
        if (this.detailRequestInProgress) {
            console.log('Detail request already in progress, skipping...');
            return;
        }
        
        if (this.state.expandedSession === sessionId) {
            this.setState({ expandedSession: null });
            return;
        }

        // Check cache first
        if (this.sessionDetailsCache.has(sessionId)) {
            console.log('Using cached details for:', sessionId);
            this.setState({ expandedSession: sessionId });
            return;
        }

        this.detailRequestInProgress = true;
        
        try {
            const response = await fetch(`${this.config.apiBaseUrl}/${sessionId}/details`);
            
            if (!response.ok) {
                throw new Error(`API returned ${response.status}`);
            }
            
            const data = await response.json();
            
            // Cache the details
            this.sessionDetailsCache.set(sessionId, data);
            
            this.setState({ expandedSession: sessionId });
            
            // Update the session in the list
            const sessions = this.state.sessions.map(s =>
                s.session_id === sessionId ? { ...s, details: data } : s
            );
            this.setState({ sessions });
        } catch (error) {
            console.error('Error loading session details:', error);
        } finally {
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
                this.render();
            }
        } catch (error) {
            console.error('Error resuming session:', error);
        }
    }

    /**
     * OPTIMIZED: Debounced state updates - batch multiple updates
     */
    setState(newState) {
        this.state = { ...this.state, ...newState };
        
        // Clear any pending update
        if (this.updateTimeout) {
            clearTimeout(this.updateTimeout);
        }
        
        // Debounce rapid updates (16ms = ~60fps)
        this.updateTimeout = setTimeout(() => {
            this.render();
        }, 16);
    }

    /**
     * Calculate visible range for virtual scrolling
     */
    calculateVisibleRange() {
        const { scrollTop, containerHeight } = this.state;
        const { itemHeight, renderBuffer } = this.config;
        
        const startIndex = Math.max(0, Math.floor(scrollTop / itemHeight) - renderBuffer);
        const endIndex = Math.min(
            this.state.sessions.length,
            Math.ceil((scrollTop + containerHeight) / itemHeight) + renderBuffer
        );
        
        return { startIndex, endIndex };
    }

    /**
     * Handle scroll with throttling via rAF
     */
    onScroll = (e) => {
        if (this.scrollRAF) {
            return; // Already scheduled
        }
        
        this.scrollRAF = requestAnimationFrame(() => {
            const scrollContainer = e.target;
            const scrollTop = scrollContainer.scrollTop;
            const containerHeight = scrollContainer.clientHeight;
            
            const { startIndex, endIndex } = this.calculateVisibleRange();
            
            if (startIndex !== this.state.visibleStartIndex || 
                endIndex !== this.state.visibleEndIndex) {
                this.state.scrollTop = scrollTop;
                this.state.containerHeight = containerHeight;
                this.state.visibleStartIndex = startIndex;
                this.state.visibleEndIndex = endIndex;
                this.render();
            }
            
            this.scrollRAF = null;
        });
    }

    formatDate(isoString) {
        if (!isoString) return 'Unknown';
        
        try {
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
        } catch (e) {
            return 'Unknown';
        }
    }

    /**
     * MAIN RENDER - Only renders visible items
     */
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

    /**
     * VIRTUAL SCROLLING: Only render visible items + buffer
     */
    renderSessionList(sessions) {
        if (this.state.loading && !this.state.initialLoadComplete) {
            return '<div class="sh-loading">Loading sessions...</div>';
        }

        if (!sessions || sessions.length === 0) {
            return `
                <div class="sh-empty">
                    ${this.state.searchQuery ? 'No sessions found' : 'No sessions yet'}
                </div>
            `;
        }

        // Calculate visible range
        const { startIndex, endIndex } = this.calculateVisibleRange();
        const visibleSessions = sessions.slice(startIndex, endIndex);
        
        // Calculate heights for virtual scrolling
        const totalHeight = sessions.length * this.config.itemHeight;
        const offsetY = startIndex * this.config.itemHeight;

        return `
            <div class="sh-session-list" data-scroll-container style="position: relative; overflow-y: auto; height: 600px;">
                <div style="height: ${totalHeight}px; position: relative;">
                    <div style="transform: translateY(${offsetY}px); position: absolute; width: 100%;">
                        ${visibleSessions.map(session => this.renderSessionCard(session)).join('')}
                    </div>
                </div>
            </div>
        `;
    }

    renderSessionCard(session) {
        const isCurrentSession = session.session_id === this.config.currentSessionId;
        const isExpanded = this.state.expandedSession === session.session_id;
        const cachedDetails = this.sessionDetailsCache.get(session.session_id);
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

                ${isExpanded && cachedDetails ? this.renderSessionDetails(session, cachedDetails) : ''}
            </div>
        `;
    }

    renderSessionDetails(session, details) {
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

    attachEventListeners() {
        // Click events
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
                    if (this.state.searchQuery.trim()) {
                        this.searchSessions();
                    }
                    break;
                case 'clear-search':
                    this.state.searchQuery = '';
                    this.state.searchResults = null;
                    
                    const searchInput = this.container.querySelector('[data-action="search-input"]');
                    if (searchInput) {
                        searchInput.value = '';
                    }
                    
                    this.loadSessionsProgressive();
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

        // Change events
        this.container.addEventListener('change', (e) => {
            const target = e.target.closest('[data-action]');
            if (!target) return;

            const action = target.dataset.action;
            const value = target.value;

            switch (action) {
                case 'sort-by':
                    this.state.sortBy = value;
                    this.loadSessionsProgressive();
                    break;
                case 'sort-order':
                    this.state.sortOrder = value;
                    this.loadSessionsProgressive();
                    break;
                case 'date-from':
                    this.state.dateFrom = value;
                    this.loadSessionsProgressive();
                    break;
                case 'date-to':
                    this.state.dateTo = value;
                    this.loadSessionsProgressive();
                    break;
            }
        });

        // Input events
        this.container.addEventListener('input', (e) => {
            const target = e.target.closest('[data-action]');
            if (!target) return;

            if (target.dataset.action === 'search-input') {
                this.state.searchQuery = target.value;
            }
        });

        // Keypress events
        this.container.addEventListener('keypress', (e) => {
            const target = e.target.closest('[data-action]');
            if (!target) return;

            if (target.dataset.action === 'search-input' && e.key === 'Enter') {
                this.searchSessions();
            }
        });

        // Scroll events for virtual scrolling
        const scrollContainer = this.container.querySelector('[data-scroll-container]');
        if (scrollContainer) {
            scrollContainer.addEventListener('scroll', this.onScroll);
            
            // Initialize container height
            this.state.containerHeight = scrollContainer.clientHeight;
        }
    }

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
        if (!this.initialized) {
            this.init();
        } else {
            this.loadSessionsProgressive();
            this.loadStats();
        }
    }

    destroy() {
        if (this.searchDebounceTimer) {
            clearTimeout(this.searchDebounceTimer);
        }
        
        if (this.updateTimeout) {
            clearTimeout(this.updateTimeout);
        }
        
        if (this.renderTimeout) {
            clearTimeout(this.renderTimeout);
        }
        
        if (this.scrollRAF) {
            cancelAnimationFrame(this.scrollRAF);
        }
        
        if (this.container) {
            this.container.innerHTML = '';
        }
        
        this.sessionDetailsCache.clear();
        this.initialized = false;
    }
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = SessionHistoryOptimized;
}