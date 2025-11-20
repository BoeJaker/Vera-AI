(() => {
    // ============================================================
    // Enhanced Memory Integration Module - THEME-AWARE
    // Advanced search, filtering, and detailed result viewing
    // Now uses CSS variables from theme.js
    // ============================================================

    // Add comprehensive CSS using theme variables
    const style = document.createElement('style');
    style.textContent = `
        .memory-search-container {
            display: flex;
            flex-direction: column;
            gap: 16px;
            padding: 16px;
            background: var(--bg);
            border-radius: 8px;
            margin-bottom: 16px;
        }
        
        .search-input-row {
            display: flex;
            gap: 8px;
            align-items: stretch;
        }
        
        .search-input-wrapper {
            flex: 1;
            position: relative;
        }
        
        .search-input {
            width: 100%;
            padding: 12px 40px 12px 16px;
            background: var(--panel-bg);
            border: 2px solid var(--border);
            border-radius: 8px;
            color: var(--text);
            font-size: 14px;
            transition: all 0.2s;
        }
        
        .search-input:focus {
            outline: none;
            border-color: var(--accent);
            box-shadow: 0 0 0 3px var(--accent-muted);
        }
        
        .search-clear-btn {
            position: absolute;
            right: 8px;
            top: 50%;
            transform: translateY(-50%);
            background: transparent;
            border: none;
            color: var(--text-dim);
            cursor: pointer;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 16px;
        }
        
        .search-clear-btn:hover {
            background: var(--border);
            color: var(--text);
        }
        
        .search-controls {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            align-items: center;
        }
        
        .search-mode-group {
            display: flex;
            gap: 4px;
            background: var(--panel-bg);
            padding: 4px;
            border-radius: 6px;
        }
        
        .search-mode-btn {
            padding: 8px 16px;
            border: none;
            background: transparent;
            color: var(--text-muted);
            cursor: pointer;
            border-radius: 4px;
            font-size: 13px;
            font-weight: 500;
            transition: all 0.2s;
        }
        
        .search-mode-btn:hover {
            background: var(--hover);
            color: var(--text);
        }
        
        .search-mode-btn.active {
            background: var(--accent);
            color: white;
        }
        
        .filter-section {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }
        
        .filter-group {
            display: flex;
            gap: 4px;
            align-items: center;
            background: var(--panel-bg);
            padding: 4px 12px;
            border-radius: 6px;
        }
        
        .filter-label {
            color: var(--text-muted);
            font-size: 12px;
            font-weight: 500;
        }
        
        .filter-select {
            background: transparent;
            border: none;
            color: var(--text);
            font-size: 13px;
            cursor: pointer;
            padding: 4px 8px;
            border-radius: 4px;
        }
        
        .filter-select:hover {
            background: var(--border);
        }
        
        .filter-input {
            background: transparent;
            border: 1px solid var(--border);
            color: var(--text);
            font-size: 13px;
            padding: 4px 8px;
            border-radius: 4px;
            width: 100px;
        }
        
        .results-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 16px;
            background: var(--panel-bg);
            border-radius: 8px;
            margin-bottom: 12px;
        }
        
        .results-title {
            color: var(--text);
            font-weight: 600;
            font-size: 14px;
        }
        
        .results-stats {
            color: var(--text-muted);
            font-size: 12px;
        }
        
        .results-actions {
            display: flex;
            gap: 8px;
        }
        
        .result-card {
            background: var(--bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            margin-bottom: 12px;
            overflow: hidden;
            transition: all 0.2s;
        }
        
        .result-card:hover {
            border-color: var(--accent);
            box-shadow: 0 4px 12px var(--accent-muted);
        }
        
        .result-card.expanded {
            border-color: var(--accent);
        }
        
        .result-header {
            display: flex;
            justify-content: space-between;
            align-items: start;
            padding: 16px;
            cursor: pointer;
            gap: 12px;
        }
        
        .result-content {
            flex: 1;
            min-width: 0;
        }
        
        .result-type-badge {
            display: inline-block;
            padding: 2px 8px;
            background: var(--panel-bg);
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            color: var(--accent);
            margin-bottom: 8px;
        }
        
        .result-text {
            color: var(--text);
            font-size: 14px;
            line-height: 1.5;
            margin-bottom: 8px;
        }
        
        .result-text.truncated {
            display: -webkit-box;
            -webkit-line-clamp: 3;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }
        
        .result-metadata {
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            color: var(--text-dim);
            font-size: 11px;
        }
        
        .result-metadata-item {
            display: flex;
            gap: 4px;
        }
        
        .result-metadata-key {
            color: var(--text-muted);
            font-weight: 600;
        }
        
        .result-actions-btn {
            display: flex;
            gap: 4px;
            align-items: center;
        }
        
        .expand-btn {
            background: transparent;
            border: none;
            color: var(--text-dim);
            cursor: pointer;
            padding: 4px;
            border-radius: 4px;
            font-size: 18px;
            transition: all 0.2s;
            width: 32px;
            height: 32px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .expand-btn:hover {
            background: var(--panel-bg);
            color: var(--text);
        }
        
        .expand-btn.expanded {
            transform: rotate(180deg);
            color: var(--accent);
        }
        
        .result-details {
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.3s ease;
        }
        
        .result-details.expanded {
            max-height: 2000px;
        }
        
        .result-details-content {
            padding: 0 16px 16px 16px;
            border-top: 1px solid var(--border);
        }
        
        .detail-section {
            margin-top: 16px;
        }
        
        .detail-section-title {
            color: var(--text-muted);
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            margin-bottom: 8px;
            letter-spacing: 0.5px;
        }
        
        .detail-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 12px;
        }
        
        .detail-item {
            background: var(--panel-bg);
            padding: 12px;
            border-radius: 6px;
        }
        
        .detail-item-label {
            color: var(--text-dim);
            font-size: 11px;
            margin-bottom: 4px;
        }
        
        .detail-item-value {
            color: var(--text);
            font-size: 13px;
            word-break: break-word;
        }
        
        .detail-actions {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            margin-top: 12px;
        }
        
        .action-btn {
            padding: 8px 16px;
            background: var(--panel-bg);
            border: 1px solid var(--border);
            color: var(--text);
            border-radius: 6px;
            cursor: pointer;
            font-size: 12px;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        
        .action-btn:hover {
            background: var(--hover);
            border-color: var(--accent);
        }
        
        .action-btn.primary {
            background: var(--accent);
            color: white;
            border-color: var(--accent);
        }
        
        .action-btn.primary:hover {
            background: var(--hover);
        }
          
        .loading-spinner {
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 40px;
            color: var(--text-dim);
        }
        
        .spinner {
            width: 40px;
            height: 40px;
            border: 4px solid var(--border);
            border-top-color: var(--accent);
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: var(--text-dim);
        }
        
        .empty-state-icon {
            font-size: 48px;
            margin-bottom: 16px;
            opacity: 0.5;
        }
        
        .empty-state-title {
            font-size: 16px;
            font-weight: 600;
            margin-bottom: 8px;
            color: var(--text-muted);
        }
        
        .empty-state-text {
            font-size: 14px;
            line-height: 1.5;
        }
        
        .pagination {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 8px;
            margin-top: 16px;
            padding: 16px;
        }
        
        .pagination-btn {
            padding: 8px 16px;
            background: var(--panel-bg);
            border: 1px solid var(--border);
            color: var(--text);
            border-radius: 6px;
            cursor: pointer;
            font-size: 13px;
            transition: all 0.2s;
        }
        
        .pagination-btn:hover:not(:disabled) {
            background: var(--border);
            border-color: var(--accent);
        }
        
        .pagination-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        .pagination-info {
            color: var(--text-muted);
            font-size: 13px;
            padding: 0 16px;
        }
        
        .advanced-filters-toggle {
            padding: 8px 16px;
            background: var(--panel-bg);
            border: 1px solid var(--border);
            color: var(--text-muted);
            border-radius: 6px;
            cursor: pointer;
            font-size: 12px;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        
        .advanced-filters-toggle:hover {
            background: var(--hover);
            border-color: var(--accent);
            color: var(--text);
        }

        .advanced-filters {
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.3s ease;
        }
        
        .advanced-filters.expanded {
            max-height: 500px;
        }
        
        .advanced-filters-content {
            background: var(--panel-bg);
            padding: 16px;
            border-radius: 8px;
            margin-top: 12px;
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 16px;
        }
        
        .filter-field {
            display: flex;
            flex-direction: column;
            gap: 6px;
        }
        
        .filter-field-label {
            color: var(--text-muted);
            font-size: 12px;
            font-weight: 600;
        }
        
        .filter-field-input {
            padding: 8px 12px;
            background: var(--bg);
            border: 1px solid var(--border);
            color: var(--text);
            border-radius: 6px;
            font-size: 13px;
        }
        
        .filter-field-input:focus {
            outline: none;
            border-color: var(--accent);
        }
        
        .label-badge {
            display: inline-block;
            padding: 4px 12px;
            background: var(--accent-muted);
            color: var(--text);
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
        }
    `;
    document.head.appendChild(style);

    // ============================================================
    // State Management
    // ============================================================
    
    VeraChat.prototype.memoryState = {
        searchMode: 'hybrid', // 'vector', 'graph', 'hybrid', 'session'
        searchQuery: '',
        currentResults: [],
        expandedResults: new Set(),
        filters: {
            limit: 50,
            minConfidence: 0,
            entityTypes: [],
            dateFrom: null,
            dateTo: null,
            sessionId: null,
        },
        pagination: {
            page: 1,
            pageSize: 20,
            total: 0
        },
        loading: false,
        advancedFiltersExpanded: false
    };

    // ============================================================
    // Search Functions
    // ============================================================
VeraChat.prototype.performMemorySearch = async function() {
    const query = this.memoryState.searchQuery.trim();
    
    // Session mode doesn't require query
    if (!query && this.memoryState.searchMode !== 'session') {
        this.addSystemMessage('Please enter a search query');
        return;
    }

    this.memoryState.loading = true;
    this.memoryState.currentResults = [];
    this.updateMemoryUI();

    try {
        const filters = this.buildSearchFilters();
        let results = [];

        switch (this.memoryState.searchMode) {
            case 'vector':
                results = await this.searchVector(query, filters);
                break;
            case 'graph':
                results = await this.searchGraph(query, filters);
                break;
            case 'hybrid':
                results = await this.searchHybrid(query, filters);
                break;
            case 'session':
                results = await this.searchSession(query, filters);
                break;
        }

        console.log(`Search returned ${results.length} results`);
        
        this.memoryState.currentResults = results;
        this.memoryState.pagination.total = results.length;
        this.memoryState.pagination.page = 1;

        if (results.length === 0) {
            this.addSystemMessage('No results found. Try adjusting your search query or filters.');
        } else {
            this.addSystemMessage(`Found ${results.length} results`);
        }

    } catch (error) {
        console.error('Search error:', error);
        this.addSystemMessage(`Search failed: ${error.message}`);
    } finally {
        this.memoryState.loading = false;
        this.updateMemoryUI();
    }
};

VeraChat.prototype.searchVector = async function(query, filters) {
    try {
        const response = await fetch('http://llm.int:8888/api/memory/query', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: this.sessionId,
                query: query,
                k: filters.limit || 50,
                retrieval_type: 'vector',
                filters: {
                    minConfidence: filters.minConfidence,
                    entityTypes: filters.entityTypes
                }
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        console.log('Vector search response:', data);
        
        return this.normalizeResults(data.results || [], 'vector');
    } catch (error) {
        console.error('Vector search error:', error);
        this.addSystemMessage(`Vector search failed: ${error.message}`);
        return [];
    }
};

VeraChat.prototype.searchGraph = async function(query, filters) {
    try {
        const response = await fetch('http://llm.int:8888/api/memory/query', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: this.sessionId,
                query: query,
                k: filters.limit || 50,
                retrieval_type: 'graph',
                filters: {
                    minConfidence: filters.minConfidence,
                    entityTypes: filters.entityTypes
                }
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        console.log('Graph search response:', data);
        
        return this.normalizeResults(data.results || [], 'graph');
    } catch (error) {
        console.error('Graph search error:', error);
        this.addSystemMessage(`Graph search failed: ${error.message}`);
        return [];
    }
};

VeraChat.prototype.searchHybrid = async function(query, filters) {
    try {
        const response = await fetch('http://llm.int:8888/api/memory/hybrid-retrieve', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: this.sessionId,
                query: query,
                k_vector: Math.floor((filters.limit || 50) / 2),
                k_graph: Math.floor((filters.limit || 50) / 4),
                graph_depth: 2,
                include_entities: true,
                filters: {
                    minConfidence: filters.minConfidence,
                    entityTypes: filters.entityTypes
                }
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        console.log('Hybrid search response:', data);
        
        // Combine session and long-term results
        const sessionResults = data.vector_results?.session || [];
        const longTermResults = data.vector_results?.long_term || [];
        
        let combined = [
            ...sessionResults,
            ...longTermResults
        ];
        
        // Add graph nodes as results
        if (data.graph_context && data.graph_context.nodes) {
            const graphResults = data.graph_context.nodes.map(node => ({
                id: node.id,
                type: 'graph_node',
                source: 'graph',
                text: node.properties?.text || node.id,
                displayText: node.properties?.text || node.id,
                metadata: node.properties || {},
                labels: node.labels || [],
                confidence: node.properties?.confidence || 1.0
            }));
            combined = [...combined, ...graphResults];
        }
        
        // Add graph relationships as results
        if (data.graph_context && data.graph_context.rels) {
            const relResults = data.graph_context.rels.map(rel => ({
                id: `${rel.start}-${rel.end}`,
                type: 'relationship',
                source: 'graph',
                head: rel.start,
                tail: rel.end,
                relation: rel.type || rel.properties?.rel || 'RELATED_TO',
                displayText: `${rel.start} → ${rel.end}`,
                metadata: rel.properties || {},
                confidence: rel.properties?.confidence || 1.0
            }));
            combined = [...combined, ...relResults];
        }
        
        return combined;
    } catch (error) {
        console.error('Hybrid search error:', error);
        this.addSystemMessage(`Hybrid search failed: ${error.message}`);
        return [];
    }
};

VeraChat.prototype.searchSession = async function(query, filters) {
    try {
        // Get entities
        const entityParams = new URLSearchParams({
            limit: filters.limit || 50,
            min_confidence: filters.minConfidence || 0
        });
        
        if (query) {
            entityParams.append('search', query);
        }
        
        if (filters.entityTypes && filters.entityTypes.length > 0) {
            filters.entityTypes.forEach(type => {
                entityParams.append('entity_types', type);
            });
        }
        
        const entityResponse = await fetch(
            `http://llm.int:8888/api/memory/${this.sessionId}/entities?${entityParams}`
        );
        
        if (!entityResponse.ok) {
            throw new Error(`Entities fetch failed: ${entityResponse.status}`);
        }
        
        const entitiesData = await entityResponse.json();
        
        // Get relationships
        const relParams = new URLSearchParams({
            limit: filters.limit || 50,
            min_confidence: filters.minConfidence || 0
        });
        
        if (query) {
            relParams.append('search', query);
        }
        
        const relResponse = await fetch(
            `http://llm.int:8888/api/memory/${this.sessionId}/relationships?${relParams}`
        );
        
        if (!relResponse.ok) {
            throw new Error(`Relationships fetch failed: ${relResponse.status}`);
        }
        
        const relData = await relResponse.json();
        
        console.log('Session search:', {
            entities: entitiesData.entities?.length || 0,
            relationships: relData.relationships?.length || 0
        });
        
        let results = [
            ...(entitiesData.entities || []).map(e => ({
                ...e,
                source: 'session_entity',
                displayText: e.text,
                type: e.type || 'entity'
            })),
            ...(relData.relationships || []).map(r => ({
                ...r,
                source: 'session_relationship',
                displayText: `${r.head} → ${r.tail}`,
                id: `${r.head}-${r.relation}-${r.tail}`,
                type: 'relationship'
            }))
        ];
        
        return results;
    } catch (error) {
        console.error('Session search error:', error);
        this.addSystemMessage(`Session search failed: ${error.message}`);
        return [];
    }
};

VeraChat.prototype.normalizeResults = function(results, source) {
    if (!Array.isArray(results)) {
        console.warn('normalizeResults received non-array:', results);
        return [];
    }
    
    return results.map(result => {
        // Ensure we have basic fields
        const normalized = {
            id: result.id || `unknown-${Math.random()}`,
            source: result.source || source,
            type: result.type || 'unknown',
            confidence: result.confidence || (result.distance ? (1 - result.distance) : 1.0)
        };
        
        // Handle text/displayText
        if (result.displayText) {
            normalized.displayText = result.displayText;
            normalized.text = result.text || result.displayText;
        } else if (result.text) {
            normalized.text = result.text;
            normalized.displayText = result.text;
        } else if (result.head && result.tail) {
            normalized.displayText = `${result.head} → ${result.tail}`;
            normalized.text = normalized.displayText;
        } else {
            normalized.displayText = result.id;
            normalized.text = result.id;
        }
        
        // Copy over other fields
        normalized.metadata = result.metadata || {};
        normalized.labels = result.labels || [];
        
        // Relationship-specific fields
        if (result.head) normalized.head = result.head;
        if (result.tail) normalized.tail = result.tail;
        if (result.relation) normalized.relation = result.relation;
        if (result.context) normalized.context = result.context;
        
        return normalized;
    });
};
    // ============================================================
    // Add normalization helper functions
    // ============================================================

    /**
     * Normalize node data to match standard graph format
     * This ensures nodes from memory search match the format used by loadGraph()
     */
    VeraChat.prototype.normalizeGraphNode = function(node) {
        return {
            id: node.id,
            label: node.label || (node.properties?.text?.substring(0, 30)) || node.id,
            title: node.title || (node.properties?.text) || node.id,
            properties: node.properties || {},
            type: node.type || node.labels || [],
            color: node.color || '#3b82f6',
            size: node.size || 25
        };
    };

    /**
     * Normalize edge data to match standard graph format
     * This ensures edges from memory search match the format used by loadGraph()
     */
    VeraChat.prototype.normalizeGraphEdge = function(edge, index = 0) {
        return {
            id: edge.id || `edge_${edge.from || edge.start}_${edge.to || edge.end}_${index}`,
            from: edge.from || edge.start,
            to: edge.to || edge.end,
            label: edge.label || edge.type || (edge.properties?.rel) || 'RELATED_TO',
            title: edge.title || edge.label || edge.type || (edge.properties?.rel) || 'RELATED_TO'
        };
    };
VeraChat.prototype.buildSearchFilters = function() {
    return {
        limit: this.memoryState.filters.limit,
        minConfidence: this.memoryState.filters.minConfidence,
        entityTypes: this.memoryState.filters.entityTypes,
        dateFrom: this.memoryState.filters.dateFrom,
        dateTo: this.memoryState.filters.dateTo
    };
};

// Add debug logging
VeraChat.prototype.debugSearch = async function() {
    console.log('=== Search Debug ===');
    console.log('Session ID:', this.sessionId);
    console.log('Search mode:', this.memoryState.searchMode);
    console.log('Query:', this.memoryState.searchQuery);
    console.log('Filters:', this.memoryState.filters);
    
    // Test API connectivity
    try {
        const response = await fetch(`http://llm.int:8888/api/memory/${this.sessionId}/entities?limit=1`);
        console.log('API Status:', response.status);
        const data = await response.json();
        console.log('API Response:', data);
    } catch (error) {
        console.error('API Error:', error);
    }
};
    VeraChat.prototype.buildSearchFilters = function() {
        return {
            limit: this.memoryState.filters.limit,
            minConfidence: this.memoryState.filters.minConfidence,
            entityTypes: this.memoryState.filters.entityTypes,
            dateFrom: this.memoryState.filters.dateFrom,
            dateTo: this.memoryState.filters.dateTo
        };
    };

    VeraChat.prototype.buildVectorFilters = function(filters) {
        const vectorFilters = {};
        
        if (filters.minConfidence > 0) {
            vectorFilters.confidence = { $gte: filters.minConfidence };
        }
        
        if (filters.entityTypes.length > 0) {
            vectorFilters.type = { $in: filters.entityTypes };
        }
        
        return Object.keys(vectorFilters).length > 0 ? vectorFilters : null;
    };

    VeraChat.prototype.buildGraphFilters = function(filters) {
        // Graph-specific filters can be added here
        return this.buildVectorFilters(filters);
    };

    // ============================================================
    // UI Rendering
    // ============================================================

    VeraChat.prototype.updateMemoryUI = function() {
        const container = document.getElementById('memory-content');
        if (!container) {
            console.warn('Memory content container not found');
            return;
        }
        
        // Initialize state if needed
        if (!this.memoryState) {
            this.memoryState = {
                searchMode: 'hybrid',
                searchQuery: '',
                currentResults: [],
                expandedResults: new Set(),
                filters: {
                    limit: 50,
                    minConfidence: 0,
                    entityTypes: [],
                    dateFrom: null,
                    dateTo: null,
                    sessionId: null,
                },
                pagination: {
                    page: 1,
                    pageSize: 20,
                    total: 0
                },
                loading: false,
                advancedFiltersExpanded: false
            };
        }

        const state = this.memoryState;
        
        const html = `
            <div style="display: flex; flex-direction: column; gap: 16px;">
                <!-- Search Container -->
                <div class="memory-search-container">
                    <!-- Search Input -->
                    <div class="search-input-row">
                        <div class="search-input-wrapper">
                            <input 
                                type="text" 
                                class="search-input"
                                id="memory-search-input"
                                placeholder="Search memory, entities, relationships..."
                                value="${this.escapeHtml(state.searchQuery)}"
                                onkeypress="if(event.key==='Enter') app.performMemorySearch()"
                            >
                            <button 
                                class="search-clear-btn" 
                                onclick="app.clearMemorySearch()"
                                style="display: ${state.searchQuery ? 'block' : 'none'}"
                            >
                                ✕
                            </button>
                        </div>
                        <button 
                            class="action-btn primary" 
                            onclick="app.performMemorySearch()"
                            style="padding: 12px 24px;"
                        >
                            🔍 Search
                        </button>
                    </div>
                    
                    <!-- Search Mode Selection -->
                    <div class="search-controls">
                        <div class="search-mode-group">
                            <button 
                                class="search-mode-btn ${state.searchMode === 'hybrid' ? 'active' : ''}"
                                onclick="app.setSearchMode('hybrid')"
                            >
                                Hybrid
                            </button>
                            <button 
                                class="search-mode-btn ${state.searchMode === 'vector' ? 'active' : ''}"
                                onclick="app.setSearchMode('vector')"
                            >
                                Vector
                            </button>
                            <button 
                                class="search-mode-btn ${state.searchMode === 'graph' ? 'active' : ''}"
                                onclick="app.setSearchMode('graph')"
                            >
                                Graph
                            </button>
                            <button 
                                class="search-mode-btn ${state.searchMode === 'session' ? 'active' : ''}"
                                onclick="app.setSearchMode('session')"
                            >
                                Session
                            </button>
                        </div>
                        
                        <button 
                            class="advanced-filters-toggle"
                            onclick="app.toggleAdvancedFilters()"
                        >
                            ${state.advancedFiltersExpanded ? '▼' : '▶'} Advanced Filters
                        </button>
                    </div>
                    
                    <!-- Advanced Filters -->
                    <div class="advanced-filters ${state.advancedFiltersExpanded ? 'expanded' : ''}">
                        <div class="advanced-filters-content">
                            <div class="filter-field">
                                <label class="filter-field-label">Result Limit</label>
                                <input 
                                    type="number" 
                                    class="filter-field-input"
                                    value="${state.filters.limit}"
                                    onchange="app.updateFilter('limit', parseInt(this.value))"
                                    min="1"
                                    max="500"
                                >
                            </div>
                            
                            <div class="filter-field">
                                <label class="filter-field-label">Min Confidence</label>
                                <input 
                                    type="range" 
                                    class="filter-field-input"
                                    value="${state.filters.minConfidence}"
                                    onchange="app.updateFilter('minConfidence', parseFloat(this.value))"
                                    min="0"
                                    max="1"
                                    step="0.1"
                                    style="width: 100%;"
                                >
                                <span style="color: var(--text-muted); font-size: 11px;">${(state.filters.minConfidence * 100).toFixed(0)}%</span>
                            </div>
                            
                            <div class="filter-field">
                                <label class="filter-field-label">Entity Types</label>
                                <select 
                                    class="filter-field-input"
                                    onchange="app.updateFilter('entityTypes', Array.from(this.selectedOptions).map(o => o.value))"
                                    multiple
                                    style="height: 80px;"
                                >
                                    <option value="PERSON">Person</option>
                                    <option value="ORG">Organization</option>
                                    <option value="GPE">Location</option>
                                    <option value="DATE">Date</option>
                                    <option value="EVENT">Event</option>
                                    <option value="PRODUCT">Product</option>
                                    <option value="CODE_BLOCK">Code Block</option>
                                    <option value="CLASS">Class</option>
                                    <option value="METHOD">Method</option>
                                    <option value="FUNCTION">Function</option>
                                </select>
                            </div>
                            
                            <div class="filter-field">
                                <label class="filter-field-label">Date From</label>
                                <input 
                                    type="date" 
                                    class="filter-field-input"
                                    value="${state.filters.dateFrom || ''}"
                                    onchange="app.updateFilter('dateFrom', this.value)"
                                >
                            </div>
                            
                            <div class="filter-field">
                                <label class="filter-field-label">Date To</label>
                                <input 
                                    type="date" 
                                    class="filter-field-input"
                                    value="${state.filters.dateTo || ''}"
                                    onchange="app.updateFilter('dateTo', this.value)"
                                >
                            </div>
                            
                            <div class="filter-field">
                                <button 
                                    class="action-btn"
                                    onclick="app.resetFilters()"
                                    style="width: 100%; margin-top: 20px;"
                                >
                                    🔄 Reset Filters
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Results -->
                ${this.renderMemoryResults()}
            </div>
        `;

        container.innerHTML = html;
    };

    VeraChat.prototype.renderMemoryResults = function() {
        const state = this.memoryState;
        
        if (state.loading) {
            return `
                <div class="loading-spinner">
                    <div class="spinner"></div>
                </div>
            `;
        }
        
        if (state.currentResults.length === 0) {
            return `
                <div class="empty-state">
                    <div class="empty-state-icon">🔍</div>
                    <div class="empty-state-title">No Results Found</div>
                    <div class="empty-state-text">
                        ${state.searchQuery 
                            ? 'Try adjusting your search query or filters' 
                            : 'Enter a search query to get started'}
                    </div>
                </div>
            `;
        }
        
        // Pagination
        const { page, pageSize } = state.pagination;
        const startIdx = (page - 1) * pageSize;
        const endIdx = Math.min(startIdx + pageSize, state.currentResults.length);
        const paginatedResults = state.currentResults.slice(startIdx, endIdx);
        const totalPages = Math.ceil(state.currentResults.length / pageSize);
        
        let html = `
            <div class="results-header">
                <div class="results-title">
                    Search Results
                </div>
                <div class="results-stats">
                    ${state.currentResults.length} results found
                    ${state.searchMode !== 'session' ? `(${state.searchMode} search)` : ''}
                </div>
                <div class="results-actions">
                    <button class="action-btn" onclick="app.exportResults()">
                        💾 Export
                    </button>
                    <button class="action-btn" onclick="app.expandAllResults()">
                        📖 Expand All
                    </button>
                    <button class="action-btn" onclick="app.collapseAllResults()">
                        📕 Collapse All
                    </button>
                </div>
            </div>
            
            <!-- Result Cards -->
            <div style="display: flex; flex-direction: column; gap: 12px;">
                ${paginatedResults.map((result, idx) => this.renderResultCard(result, startIdx + idx)).join('')}
            </div>
            
            <!-- Pagination Controls -->
            ${totalPages > 1 ? `
                <div class="pagination">
                    <button 
                        class="pagination-btn"
                        onclick="app.goToPage(${page - 1})"
                        ${page === 1 ? 'disabled' : ''}
                    >
                        ← Previous
                    </button>
                    <div class="pagination-info">
                        Page ${page} of ${totalPages} (${startIdx + 1}-${endIdx} of ${state.currentResults.length})
                    </div>
                    <button 
                        class="pagination-btn"
                        onclick="app.goToPage(${page + 1})"
                        ${page === totalPages ? 'disabled' : ''}
                    >
                        Next →
                    </button>
                </div>
            ` : ''}
        `;
        
        return html;
    };

    VeraChat.prototype.renderResultCard = function(result, index) {
        const isExpanded = this.memoryState.expandedResults.has(result.id);
        
        // Theme-aware confidence colors using getComputedStyle
        let confidenceColor = 'var(--text-muted)';
        if (result.confidence !== undefined) {
            if (result.confidence > 0.8) confidenceColor = 'var(--success)';
            else if (result.confidence > 0.5) confidenceColor = 'var(--warning)';
            else confidenceColor = 'var(--danger)';
        }
        
        return `
            <div class="result-card ${isExpanded ? 'expanded' : ''}" id="result-${result.id}">
                <div class="result-header" onclick="app.toggleResultExpansion('${result.id}')">
                    <div class="result-content">
                        <span class="result-type-badge" style="background: ${this.getSourceColor(result.source)};">
                            ${this.getSourceIcon(result.source)} ${result.source || 'unknown'}
                        </span>
                        <div class="result-text ${isExpanded ? '' : 'truncated'}">
                            ${this.escapeHtml(result.displayText || result.text || result.id || 'No content')}
                        </div>
                        <div class="result-metadata">
                            ${result.type ? `
                                <div class="result-metadata-item">
                                    <span class="result-metadata-key">Type:</span>
                                    <span>${this.escapeHtml(result.type)}</span>
                                </div>
                            ` : ''}
                            ${result.confidence !== undefined ? `
                                <div class="result-metadata-item">
                                    <span class="result-metadata-key">Confidence:</span>
                                    <span style="color: ${confidenceColor};">${(result.confidence * 100).toFixed(1)}%</span>
                                </div>
                            ` : ''}
                            ${result.distance !== undefined ? `
                                <div class="result-metadata-item">
                                    <span class="result-metadata-key">Distance:</span>
                                    <span>${result.distance.toFixed(3)}</span>
                                </div>
                            ` : ''}
                            ${result.labels && result.labels.length > 0 ? `
                                <div class="result-metadata-item">
                                    <span class="result-metadata-key">Labels:</span>
                                    <span>${result.labels.slice(0, 3).join(', ')}</span>
                                </div>
                            ` : ''}
                        </div>
                    </div>
                    <div class="result-actions-btn">
                        <button class="expand-btn ${isExpanded ? 'expanded' : ''}" onclick="event.stopPropagation(); app.toggleResultExpansion('${result.id}')">
                            ▼
                        </button>
                    </div>
                </div>
                
                <div class="result-details ${isExpanded ? 'expanded' : ''}">
                    <div class="result-details-content">
                        ${this.renderResultDetails(result)}
                    </div>
                </div>
            </div>
        `;
    };

    VeraChat.prototype.renderResultDetails = function(result) {
        let html = '';
        
        // Full Text Section
        if (result.text || result.displayText) {
            html += `
                <div class="detail-section">
                    <div class="detail-section-title">Full Text</div>
                    <div style="background: var(--panel-bg); padding: 16px; border-radius: 6px; color: var(--text); line-height: 1.6; white-space: pre-wrap; word-break: break-word;">
                        ${this.escapeHtml(result.text || result.displayText || '')}
                    </div>
                </div>
            `;
        }
        
        // Relationship Details (for relationship type results)
        if (result.head && result.tail && result.relation) {
            html += `
                <div class="detail-section">
                    <div class="detail-section-title">Relationship</div>
                    <div style="background: var(--panel-bg); padding: 16px; border-radius: 6px;">
                        <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
                            <div style="background: var(--accent); color: white; padding: 8px 16px; border-radius: 6px; font-weight: 600;">
                                ${this.escapeHtml(result.head)}
                            </div>
                            <div style="color: var(--text-muted); font-weight: 600;">
                                —[ ${this.escapeHtml(result.relation)} ]→
                            </div>
                            <div style="background: var(--accent-muted); color: white; padding: 8px 16px; border-radius: 6px; font-weight: 600;">
                                ${this.escapeHtml(result.tail)}
                            </div>
                        </div>
                        ${result.context ? `
                            <div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); color: var(--text-muted); font-style: italic; font-size: 13px;">
                                Context: "${this.escapeHtml(result.context)}"
                            </div>
                        ` : ''}
                    </div>
                </div>
            `;
        }
        
        // Metadata Section
        if (result.metadata && Object.keys(result.metadata).length > 0) {
            const metadataEntries = Object.entries(result.metadata)
                .filter(([key, value]) => value !== null && value !== undefined);
            
            if (metadataEntries.length > 0) {
                html += `
                    <div class="detail-section">
                        <div class="detail-section-title">Metadata</div>
                        <div class="detail-grid">
                            ${metadataEntries.map(([key, value]) => {
                                let displayValue = value;
                                if (typeof value === 'object') {
                                    displayValue = JSON.stringify(value, null, 2);
                                } else if (typeof value === 'string' && value.length > 100) {
                                    displayValue = value.substring(0, 100) + '...';
                                } else {
                                    displayValue = String(value);
                                }
                                
                                return `
                                    <div class="detail-item">
                                        <div class="detail-item-label">${this.escapeHtml(key)}</div>
                                        <div class="detail-item-value">${this.escapeHtml(displayValue)}</div>
                                    </div>
                                `;
                            }).join('')}
                        </div>
                    </div>
                `;
            }
        }
        
        // Properties Section (for graph nodes)
        if (result.properties && Object.keys(result.properties).length > 0) {
            const propEntries = Object.entries(result.properties)
                .filter(([key, value]) => !['text'].includes(key) && value !== null);
            
            if (propEntries.length > 0) {
                html += `
                    <div class="detail-section">
                        <div class="detail-section-title">Properties</div>
                        <div class="detail-grid">
                            ${propEntries.map(([key, value]) => {
                                let displayValue = value;
                                if (typeof value === 'object') {
                                    displayValue = JSON.stringify(value, null, 2);
                                } else if (typeof value === 'string' && value.length > 100) {
                                    displayValue = value.substring(0, 100) + '...';
                                } else {
                                    displayValue = String(value);
                                }
                                
                                return `
                                    <div class="detail-item">
                                        <div class="detail-item-label">${this.escapeHtml(key)}</div>
                                        <div class="detail-item-value">${this.escapeHtml(displayValue)}</div>
                                    </div>
                                `;
                            }).join('')}
                        </div>
                    </div>
                `;
            }
        }
        
        // Labels Section
        if (result.labels && result.labels.length > 0) {
            html += `
                <div class="detail-section">
                    <div class="detail-section-title">Labels</div>
                    <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                        ${result.labels.map(label => 
                            `<span class="label-badge">${this.escapeHtml(label)}</span>`
                        ).join('')}
                    </div>
                </div>
            `;
        }
        
        // Actions Section
        html += `
            <div class="detail-section">
                <div class="detail-section-title">Actions</div>
                <div class="detail-actions">
                    <button class="action-btn" onclick="app.focusInGraph('${result.id}')">
                        Focus in Graph
                    </button>
                    <button class="action-btn" onclick="app.loadResultSubgraph('${result.id}')">
                        Load Subgraph
                    </button>
                    ${result.text ? `
                        <button class="action-btn" onclick="app.extractFromResult('${result.id}', \`${this.escapeHtml(result.text).replace(/`/g, '\\`')}\`)">
                            Extract Entities
                        </button>
                    ` : ''}
                    <button class="action-btn" onclick="app.copyToClipboard('${result.id}')">
                        Copy to Clipboard
                    </button>
                    ${result.metadata?.session_id && result.metadata.session_id !== this.sessionId ? `
                        <button class="action-btn" onclick="app.loadSessionInGraph('${result.metadata.session_id}')">
                            Load Session Graph
                        </button>
                    ` : ''}
                    <button class="action-btn" onclick="app.promoteResult('${result.id}')">
                        Promote to Long-term
                    </button>
                    <button class="action-btn" onclick="app.viewResultJSON('${result.id}')">
                        View JSON
                    </button>
                </div>
            </div>
        `;
        
        return html;
    };
    // Load subgraph around a result node

    VeraChat.prototype.loadResultSubgraph = async function(nodeId) {
        try {
            this.addSystemMessage(`Loading subgraph around ${nodeId}...`);
            
            // Get subgraph from API
            const response = await fetch('http://llm.int:8888/api/memory/subgraph', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    seed_entity_ids: [nodeId],
                    depth: 2
                })
            });
            
            const data = await response.json();
            
            if (data.subgraph && data.subgraph.nodes) {
                // Use normalized format for nodes
                const newNodes = data.subgraph.nodes.map(n => 
                    this.normalizeGraphNode({
                        id: n.id,
                        label: n.properties?.text?.substring(0, 30) || n.id,
                        title: n.properties?.text || n.id,
                        properties: n.properties,
                        type: n.labels,
                        // Use different color for extracted entities
                        color: n.properties?.type === 'extracted_entity' ? '#10b981' : '#3b82f6',
                        size: 25
                    })
                );
                
                // Use normalized format for edges
                const newEdges = data.subgraph.rels.map((r, idx) => 
                    this.normalizeGraphEdge({
                        from: r.start,
                        to: r.end,
                        label: r.type || r.properties?.rel,
                        properties: r.properties
                    }, idx)
                );
                
                // Update network data
                this.networkInstance.body.data.nodes.update(newNodes);
                this.networkInstance.body.data.edges.update(newEdges);
                
                // Switch to graph tab and focus
                this.switchTab('graph');
                setTimeout(() => {
                    this.networkInstance.fit({
                        nodes: newNodes.map(n => n.id),
                        animation: true
                    });
                }, 100);
                
                this.addSystemMessage(`Loaded subgraph: ${newNodes.length} nodes, ${newEdges.length} edges`);
            } else {
                this.addSystemMessage('No subgraph data found');
            }
        } catch (error) {
            console.error('Error loading subgraph:', error);
            this.addSystemMessage(`Error loading subgraph: ${error.message}`);
        }
        
        // Close dropdown menu
        document.querySelectorAll('.result-dropdown-menu').forEach(menu => {
            menu.style.display = 'none';
        });
    };


    // Load entire session graph
 
    VeraChat.prototype.loadSessionInGraph = async function(sessionId) {
        try {
            this.addSystemMessage(`Loading session ${sessionId.substring(0, 8)}... graph...`);
            
            const response = await fetch(`http://llm.int:8888/api/graph/session/${sessionId}`);
            const data = await response.json();
            
            if (data.nodes && data.edges) {
                // Use normalized format for nodes
                const nodes = data.nodes.map(n => this.normalizeGraphNode(n));
                
                // Use normalized format for edges
                const edges = data.edges.map((e, index) => this.normalizeGraphEdge(e, index));
                
                // Update network data
                this.networkInstance.body.data.nodes.update(nodes);
                this.networkInstance.body.data.edges.update(edges);
                
                // Switch to graph tab
                this.switchTab('graph');
                setTimeout(() => {
                    this.networkInstance.fit();
                }, 100);
                
                this.addSystemMessage(`Loaded session graph: ${nodes.length} nodes, ${edges.length} edges`);
                
                // Update graph stats
                document.getElementById('nodeCount').textContent = nodes.length;
                document.getElementById('edgeCount').textContent = edges.length;
            }
        } catch (error) {
            console.error('Error loading session graph:', error);
            this.addSystemMessage(`Error loading session: ${error.message}`);
        }
        
        // Close dropdown menu
        document.querySelectorAll('.result-dropdown-menu').forEach(menu => {
            menu.style.display = 'none';
        });
    };



    // ============================================================
    // Helper Functions
    // ============================================================

    VeraChat.prototype.getSourceColor = function(source) {
        // Return theme-aware colors
        const colors = {
            'vector': 'var(--accent)',
            'graph': 'var(--accent-muted)',
            'hybrid': 'var(--accent)',
            'session': 'var(--success)',
            'long_term': 'var(--warning)',
            'entity': 'var(--accent)',
            'relationship': 'var(--accent-muted)',
            'graph_node': 'var(--accent-muted)',
            'session_entity': 'var(--success)',
            'session_relationship': 'var(--success)'
        };
        return colors[source] || 'var(--text-dim)';
    };

    VeraChat.prototype.getSourceIcon = function(source) {
        const icons = {
            'vector': '📊',
            'graph': '🕸️',
            'hybrid': '🔀',
            'session': '📝',
            'long_term': '💾',
            'entity': '🏷️',
            'relationship': '🔗',
            'graph_node': '⬢',
            'session_entity': '🏷️',
            'session_relationship': '🔗'
        };
        return icons[source] || '📌';
    };

    // ============================================================
    // UI Interaction Functions
    // ============================================================

    VeraChat.prototype.setSearchMode = function(mode) {
        this.memoryState.searchMode = mode;
        this.updateMemoryUI();
    };

    VeraChat.prototype.clearMemorySearch = function() {
        this.memoryState.searchQuery = '';
        this.memoryState.currentResults = [];
        this.memoryState.expandedResults.clear();
        this.updateMemoryUI();
    };

    VeraChat.prototype.toggleAdvancedFilters = function() {
        this.memoryState.advancedFiltersExpanded = !this.memoryState.advancedFiltersExpanded;
        this.updateMemoryUI();
    };

    VeraChat.prototype.updateFilter = function(filterName, value) {
        this.memoryState.filters[filterName] = value;
        // Auto-search when filters change
        if (this.memoryState.currentResults.length > 0) {
            this.performMemorySearch();
        }
    };

    VeraChat.prototype.resetFilters = function() {
        this.memoryState.filters = {
            limit: 50,
            minConfidence: 0,
            entityTypes: [],
            dateFrom: null,
            dateTo: null,
            sessionId: null,
        };
        this.updateMemoryUI();
    };

    VeraChat.prototype.toggleResultExpansion = function(resultId) {
        if (this.memoryState.expandedResults.has(resultId)) {
            this.memoryState.expandedResults.delete(resultId);
        } else {
            this.memoryState.expandedResults.add(resultId);
        }
        this.updateMemoryUI();
    };

    VeraChat.prototype.expandAllResults = function() {
        const { page, pageSize } = this.memoryState.pagination;
        const startIdx = (page - 1) * pageSize;
        const endIdx = Math.min(startIdx + pageSize, this.memoryState.currentResults.length);
        const paginatedResults = this.memoryState.currentResults.slice(startIdx, endIdx);
        
        paginatedResults.forEach(result => {
            this.memoryState.expandedResults.add(result.id);
        });
        this.updateMemoryUI();
    };

    VeraChat.prototype.collapseAllResults = function() {
        this.memoryState.expandedResults.clear();
        this.updateMemoryUI();
    };

    VeraChat.prototype.goToPage = function(pageNumber) {
        const totalPages = Math.ceil(this.memoryState.currentResults.length / this.memoryState.pagination.pageSize);
        if (pageNumber >= 1 && pageNumber <= totalPages) {
            this.memoryState.pagination.page = pageNumber;
            this.memoryState.expandedResults.clear(); // Collapse all when changing pages
            this.updateMemoryUI();
            
            // Scroll to top of results
            const memoryContent = document.getElementById('memory-content');
            if (memoryContent) {
                memoryContent.scrollTop = 0;
            }
        }
    };

    VeraChat.prototype.exportResults = function() {
        const results = this.memoryState.currentResults;
        const blob = new Blob([JSON.stringify(results, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `memory_search_results_${Date.now()}.json`;
        a.click();
        URL.revokeObjectURL(url);
        this.addSystemMessage('Results exported successfully');
    };

    VeraChat.prototype.copyToClipboard = async function(resultId) {
        const result = this.memoryState.currentResults.find(r => r.id === resultId);
        if (!result) return;
        
        const textToCopy = result.text || result.displayText || JSON.stringify(result, null, 2);
        
        try {
            await navigator.clipboard.writeText(textToCopy);
            this.addSystemMessage('Copied to clipboard');
        } catch (err) {
            console.error('Failed to copy:', err);
            this.addSystemMessage('Failed to copy to clipboard');
        }
    };

    VeraChat.prototype.promoteResult = async function(resultId) {
        const result = this.memoryState.currentResults.find(r => r.id === resultId);
        if (!result) return;
        
        try {
            const response = await fetch(`http://llm.int:8888/api/memory/${this.sessionId}/promote`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    memory_id: resultId,
                    entity_anchor: null
                })
            });
            
            if (response.ok) {
                this.addSystemMessage('Result promoted to long-term memory');
            } else {
                throw new Error('Promotion failed');
            }
        } catch (error) {
            console.error('Promotion error:', error);
            this.addSystemMessage('Failed to promote result');
        }
    };
    
     // Focus on a specific node in the graph
    VeraChat.prototype.focusInGraph = async function(nodeId) {
        if (!this.networkInstance) {
            this.addSystemMessage('Graph not initialized');
            return;
        }
        
        // Switch to graph tab
        this.switchTab('graph');
        
        // Wait for tab switch animation
        await new Promise(resolve => setTimeout(resolve, 100));
        
        // Check if node exists in current graph
        const node = this.networkInstance.body.data.nodes.get(nodeId);
        
        if (node) {
            // Node exists, focus on it
            this.networkInstance.selectNodes([nodeId]);
            this.networkInstance.focus(nodeId, {
                scale: 1.5,
                animation: {
                    duration: 1000,
                    easingFunction: 'easeInOutQuad'
                }
            });
            
            // Show node details
            if (window.GraphAddon && window.GraphAddon.showNodeDetails) {
                window.GraphAddon.showNodeDetails(nodeId, true);
            }
        } else {
            // Node not in current graph, load its subgraph
            this.addSystemMessage(`Node ${nodeId} not in current view. Loading subgraph...`);
            await this.loadResultSubgraph(nodeId);
        }
        
        // Close dropdown menu
        document.querySelectorAll('.result-dropdown-menu').forEach(menu => {
            menu.style.display = 'none';
        });
    };

    // Extract entities from result text
    VeraChat.prototype.extractFromResult = async function(resultId, text) {
        // Close dropdown menu
        document.querySelectorAll('.result-dropdown-menu').forEach(menu => {
            menu.style.display = 'none';
        });
        
        if (!text || text.length < 10) {
            this.addSystemMessage('Text too short for extraction');
            return;
        }
        
        this.addSystemMessage(`Extracting entities from result ${resultId}...`);
        
        try {
            const response = await fetch('http://llm.int:8888/api/memory/extract-entities', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    text: text,
                    auto_promote: false,
                    source_node_id: resultId
                })
            });
            
            const data = await response.json();
            this.addSystemMessage(`Extracted ${data.entities.length} entities and ${data.relations.length} relationships`);
            
            // Reload graph and memory data
            await Promise.all([
                this.loadGraph(),
                this.loadSessionEntities(),
                this.loadSessionRelationships()
            ]);
        } catch (error) {
            console.error('Error extracting entities:', error);
            this.addSystemMessage(`Extraction failed: ${error.message}`);
        }
    };


    // Extract entities from text
    VeraChat.prototype.extractEntities = async function(text, autoPromote = false) {
        if (!this.sessionId) return;
        
        try {
            const response = await fetch('http://llm.int:8888/api/memory/extract-entities', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    text: text,
                    auto_promote: autoPromote,
                    source_node_id: null
                })
            });
            
            const data = await response.json();
            this.addSystemMessage(`Extracted ${data.entities.length} entities and ${data.relations.length} relationships`);
            
            // Reload graph to show new entities
            await this.loadGraph();
            return data;
        } catch (error) {
            console.error('Entity extraction error:', error);
        }
    };

    // Load session entities
    VeraChat.prototype.loadSessionEntities = async function() {
        if (!this.sessionId) return;
        
        try {
            const response = await fetch(`http://llm.int:8888/api/memory/${this.sessionId}/entities`);
            const data = await response.json();
            this.memoryEntities = data.entities;
            this.updateMemoryUI();
        } catch (error) {
            console.error('Failed to load entities:', error);
        }
    };

    // Load session relationships
    VeraChat.prototype.loadSessionRelationships = async function() {
        if (!this.sessionId) return;
        
        try {
            const response = await fetch(`http://llm.int:8888/api/memory/${this.sessionId}/relationships`);
            const data = await response.json();
            this.memoryRelationships = data.relationships;
            this.updateMemoryUI();
        } catch (error) {
            console.error('Failed to load relationships:', error);
        }
    };

    // Get subgraph around entities
    VeraChat.prototype.getMemorySubgraph = async function(entityIds, depth = 2) {
        if (!this.sessionId) return;
        
        try {
            const response = await fetch('http://llm.int:8888/api/memory/subgraph', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    seed_entity_ids: entityIds,
                    depth: depth
                })
            });
            
            const data = await response.json();
            
            // Visualize subgraph
            if (data.subgraph && this.networkInstance) {
                this.visualizeSubgraph(data.subgraph);
            }
            
            return data;
        } catch (error) {
            console.error('Subgraph retrieval error:', error);
        }
    };

    // Promote memory to long-term
    VeraChat.prototype.promoteMemory = async function(memoryId, entityAnchor = null) {
        if (!this.sessionId) return;
        
        try {
            const response = await fetch(`http://llm.int:8888/api/memory/${this.sessionId}/promote`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    memory_id: memoryId,
                    entity_anchor: entityAnchor
                })
            });
            
            const data = await response.json();
            this.addSystemMessage(`Memory promoted to long-term storage`);
            return data;
        } catch (error) {
            console.error('Memory promotion error:', error);
        }
    };
    VeraChat.prototype.viewResultJSON = function(resultId) {
        const result = this.memoryState.currentResults.find(r => r.id === resultId);
        if (!result) return;
        
        const panel = document.getElementById('property-panel');
        const content = document.getElementById('panel-content');
        
        panel.classList.add('active');
        content.innerHTML = `
            <div style="padding: 16px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                    <h3 style="color: var(--accent); margin: 0;">Result JSON</h3>
                    <button class="panel-btn" onclick="app.copyToClipboard('${resultId}')">
                        📋 Copy
                    </button>
                </div>
                <pre style="background: var(--bg); padding: 16px; border-radius: 6px; color: var(--text); overflow-x: auto; font-size: 12px; line-height: 1.5;">${this.escapeHtml(JSON.stringify(result, null, 2))}</pre>
            </div>
        `;
    };

    // ============================================================
    // Event Listeners
    // ============================================================

    // Update search query on input
    document.addEventListener('input', function(event) {
        if (event.target.id === 'memory-search-input') {
            app.memoryState.searchQuery = event.target.value;
        }
    });

    // ============================================================
    // Initialization and Setup
    // ============================================================
    
    // Initialize memory state if it doesn't exist
    if (!VeraChat.prototype.memoryState) {
        VeraChat.prototype.memoryState = {
            searchMode: 'hybrid',
            searchQuery: '',
            currentResults: [],
            expandedResults: new Set(),
            filters: {
                limit: 50,
                minConfidence: 0,
                entityTypes: [],
                dateFrom: null,
                dateTo: null,
                sessionId: null,
            },
            pagination: {
                page: 1,
                pageSize: 20,
                total: 0
            },
            loading: false,
            advancedFiltersExpanded: false
        };
    }

    // Manual initialization function for testing
    VeraChat.prototype.initializeMemoryUI = function() {
        console.log('Initializing enhanced memory UI...');
        
        // Ensure state exists
        if (!this.memoryState) {
            this.memoryState = {
                searchMode: 'hybrid',
                searchQuery: '',
                currentResults: [],
                expandedResults: new Set(),
                filters: {
                    limit: 50,
                    minConfidence: 0,
                    entityTypes: [],
                    dateFrom: null,
                    dateTo: null,
                    sessionId: null,
                },
                pagination: {
                    page: 1,
                    pageSize: 20,
                    total: 0
                },
                loading: false,
                advancedFiltersExpanded: false
            };
        }
        
        // Check if container exists
        const container = document.getElementById('memory-content');
        if (container) {
            console.log('Memory content container found, rendering UI...');
            this.updateMemoryUI();
        } else {
            console.warn('Memory content container not found. Make sure you\'re on the memory tab.');
        }
    };

    // Hook into existing tab switching
    const originalSwitchTab = VeraChat.prototype.switchTab;
    VeraChat.prototype.switchTab = function(tab) {
        if (originalSwitchTab) {
            originalSwitchTab.call(this, tab);
        }
        
        if (tab === 'memory') {
            // Small delay to ensure DOM is ready
            setTimeout(() => {
                this.updateMemoryUI();
            }, 50);
        }
    };

    // Also hook into the original loadMemoryData if it exists
    const originalLoadMemoryData = VeraChat.prototype.loadMemoryData;
    VeraChat.prototype.loadMemoryData = async function() {
        if (originalLoadMemoryData) {
            await originalLoadMemoryData.call(this);
        }
        this.updateMemoryUI();
    };

    // Initialize on load if memory tab is already active
    if (window.app && window.app.activeTab === 'memory') {
        setTimeout(() => {
            window.app.updateMemoryUI();
        }, 100);
    }
    
    console.log('Enhanced memory UI module loaded (THEME-AWARE). Call app.initializeMemoryUI() to manually initialize.');

})();