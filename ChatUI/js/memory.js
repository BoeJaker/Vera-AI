(() => {
    // ============================================================
    // Memory Integration Module
    // Adds memory query, entity extraction, and graph integration
    // ============================================================

    // Add CSS for dropdown menus
    const style = document.createElement('style');
    style.textContent = `
        .result-menu-item:hover {
            background: #334155;
        }
        .result-dropdown-menu {
            animation: slideDown 0.2s ease;
        }
        @keyframes slideDown {
            from {
                opacity: 0;
                transform: translateY(-10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
    `;
    document.head.appendChild(style);

    // Query memory with different retrieval modes
    VeraChat.prototype.queryMemory = async function(query, retrievalType = 'hybrid', k = 5) {
        if (!this.sessionId) return;
            
        try {
            const response = await fetch('http://llm.int:8888/api/memory/query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    query: query,
                    k: k,
                    retrieval_type: retrievalType,
                    filters: null
                })
            });
            
            const data = await response.json();
            this.memoryQueryResults = data;
            this.updateMemoryUI();
            return data;
        } catch (error) {
            console.error('Memory query error:', error);
            this.addSystemMessage(`Memory query failed: ${error.message}`);
        }
    };

    // Advanced hybrid retrieval
    VeraChat.prototype.hybridRetrieve = async function(query, kVector = 5, kGraph = 3, graphDepth = 2) {
        if (!this.sessionId) return;
        
        try {
            const response = await fetch('http://llm.int:8888/api/memory/hybrid-retrieve', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    query: query,
                    k_vector: kVector,
                    k_graph: kGraph,
                    graph_depth: graphDepth,
                    include_entities: true,
                    filters: null
                })
            });
            
            const data = await response.json();
            this.memoryQueryResults = data;
            this.updateMemoryUI();
            return data;
        } catch (error) {
            console.error('Hybrid retrieval error:', error);
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

    // Visualize subgraph in network
    VeraChat.prototype.visualizeSubgraph = function(subgraph) {
        if (!this.networkInstance) return;
        
        const nodes = subgraph.nodes.map(n => ({
            id: n.id,
            label: n.properties?.text?.substring(0, 30) || n.id,
            title: JSON.stringify(n.properties, null, 2),
            color: n.properties?.type === 'extracted_entity' ? '#10b93a' : '#3b82f6',
            size: 30
        }));
        
        const edges = subgraph.rels.map((r, idx) => ({
            id: `subgraph-edge-${idx}`,
            from: r.start,
            to: r.end,
            label: r.type || r.properties?.rel,
            color: { color: '#f59e0b', highlight: '#fbbf24' },
            width: 3
        }));
        
        // Highlight these nodes/edges in the existing graph
        this.networkInstance.selectNodes(nodes.map(n => n.id));
        
        // Or switch to subgraph view
        this.switchTab('graph');
        setTimeout(() => {
            this.networkInstance.fit({
                nodes: nodes.map(n => n.id),
                animation: true
            });
        }, 100);
    };

    // Update memory UI
    VeraChat.prototype.updateMemoryUI = function() {
        const container = document.getElementById('memory-content');
        if (!container || this.activeTab !== 'memory') return;
        
        let html = `
            <div style="display: flex; flex-direction: column; gap: 20px;">
                <!-- Memory Query Section -->
                <div class="memoryQuery" style="border-radius: 8px; padding: 16px;">
                    <h3 style="margin-bottom: 12px; font-size: 16px;">🔍 Memory Query</h3>
                    <div style="display: flex; gap: 8px; margin-bottom: 12px;">
                        <input 
                            type="text" 
                            id="memory-query-input" 
                            placeholder="Search memories..." 
                            style="flex: 1; padding: 10px; border: 1px solid #334155; color: #e2e8f0; border-radius: 6px;"
                        >
                        <select 
                            id="memory-retrieval-type" 
                            style="padding: 10px; border: 1px solid #334155; color: #e2e8f0; border-radius: 6px;"
                        >
                            <option value="hybrid">Hybrid</option>
                            <option value="vector">Vector</option>
                            <option value="graph">Graph</option>
                        </select>
                        <button 
                            class="panel-btn" 
                            onclick="app.performMemoryQuery()"
                            style="padding: 10px 20px; font-size: 14px;"
                        >
                            Search
                        </button>
                    </div>
                    
                    ${this.memoryQueryResults ? this.renderMemoryQueryResults() : '<p style="color: #94a3b8; font-size: 13px;">No query results yet</p>'}
                </div>
                
                <!-- Entity Extraction Section -->
                <div class="memoryQuery" style="border-radius: 8px; padding: 16px;">
                    <h3 style="margin-bottom: 12px; font-size: 16px;">🧠 Entity Extraction</h3>
                    <div style="display: flex; gap: 8px; margin-bottom: 12px;">
                        <textarea 
                            id="entity-extract-input" 
                            placeholder="Enter text to extract entities..." 
                            rows="3"
                            style="flex: 1; padding: 10px; border: 1px solid #334155; color: #e2e8f0; border-radius: 6px; resize: vertical;"
                        ></textarea>
                    </div>
                    <div style="display: flex; gap: 8px; align-items: center;">
                        <label style="display: flex; align-items: center; gap: 8px; color: #cbd5e1; font-size: 13px;">
                            <input type="checkbox" id="auto-promote-checkbox">
                            Auto-promote high-confidence entities
                        </label>
                        <button 
                            class="panel-btn" 
                            onclick="app.performEntityExtraction()"
                            style="margin-left: auto; padding: 10px 20px;"
                        >
                            Extract
                        </button>
                    </div>
                </div>
                
                <!-- Session Entities Section -->
                <div class="memoryQuery" style=" border-radius: 8px; padding: 16px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                        <h3 style="margin: 0; font-size: 16px;">📦 Session Entities (${this.memoryEntities.length})</h3>
                        <button class="panel-btn" onclick="app.loadSessionEntities()">🔄 Refresh</button>
                    </div>
                    
                    ${this.renderEntitiesList()}
                </div>
                
                <!-- Session Relationships Section -->
                <div class="memoryQuery" style="border-radius: 8px; padding: 16px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                        <h3 style="margin: 0; font-size: 16px;">🔗 Session Relationships (${this.memoryRelationships.length})</h3>
                        <button class="panel-btn" onclick="app.loadSessionRelationships()">🔄 Refresh</button>
                    </div>
                    
                    ${this.renderRelationshipsList()}
                </div>
            </div>
        `;
        
        container.innerHTML = html;
    };

    // Render memory query results
    VeraChat.prototype.renderMemoryQueryResults = function() {
        if (!this.memoryQueryResults) return '';
        
        // Handle different result formats
        if (this.memoryQueryResults.results) {
            // Simple query results
            const results = this.memoryQueryResults.results;
            if (results.length === 0) {
                return '<p style="color: #94a3b8; font-size: 13px;">No results found</p>';
            }
            
            let html = '<div style="display: flex; flex-direction: column; gap: 8px; max-height: 400px; overflow-y: auto;">';
            results.forEach((result, idx) => {
                const resultData = JSON.stringify(result).replace(/"/g, '&quot;');
                html += `
                    <div style="background: #0f172a; padding: 12px; border-radius: 6px; border-left: 3px solid #3b82f6; position: relative;">
                        <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 8px;">
                            <div style="flex: 1;">
                                <div style="color: #e2e8f0; font-size: 13px; margin-bottom: 4px;">${this.escapeHtml(result.text || result.id)}</div>
                                ${result.distance ? `<div style="color: #94a3b8; font-size: 11px;">Distance: ${result.distance.toFixed(3)}</div>` : ''}
                            </div>
                            <div class="result-menu-btn" style="position: relative;">
                                <button 
                                    class="panel-btn" 
                                    onclick="app.toggleResultMenu(event, ${idx})"
                                    style="padding: 4px 8px; font-size: 11px;"
                                >
                                    ⋮
                                </button>
                                <div id="result-menu-${idx}" class="result-dropdown-menu" style="display: none; position: absolute; right: 0; top: 100%; background: #1e293b; border: 1px solid #334155; border-radius: 4px; min-width: 180px; z-index: 1000; box-shadow: 0 4px 12px rgba(0,0,0,0.3);">
                                    <div class="result-menu-item" onclick="app.viewResultDetails('${result.id}')" style="padding: 8px 12px; cursor: pointer; color: #cbd5e1; font-size: 12px; border-bottom: 1px solid #334155;">
                                        📄 View Details
                                    </div>
                                    <div class="result-menu-item" onclick="app.focusInGraph('${result.id}')" style="padding: 8px 12px; cursor: pointer; color: #cbd5e1; font-size: 12px; border-bottom: 1px solid #334155;">
                                        🎯 Focus in Graph
                                    </div>
                                    <div class="result-menu-item" onclick="app.loadResultSubgraph('${result.id}')" style="padding: 8px 12px; cursor: pointer; color: #cbd5e1; font-size: 12px; border-bottom: 1px solid #334155;">
                                        🗺️ Load Subgraph
                                    </div>
                                    ${result.metadata?.session_id ? `
                                        <div class="result-menu-item" onclick="app.loadSessionInGraph('${result.metadata.session_id}')" style="padding: 8px 12px; cursor: pointer; color: #cbd5e1; font-size: 12px; border-bottom: 1px solid #334155;">
                                            📊 Load Session Graph
                                        </div>
                                    ` : ''}
                                    <div class="result-menu-item" onclick="app.extractFromResult('${result.id}', \`${this.escapeHtml(result.text || '')}\`)" style="padding: 8px 12px; cursor: pointer; color: #cbd5e1; font-size: 12px; border-bottom: 1px solid #334155;">
                                        🧠 Extract Entities
                                    </div>
                                    <div class="result-menu-item" onclick="app.copyResultText(\`${this.escapeHtml(result.text || '')}\`)" style="padding: 8px 12px; cursor: pointer; color: #cbd5e1; font-size: 12px;">
                                        📋 Copy Text
                                    </div>
                                </div>
                            </div>
                        </div>
                        ${result.metadata ? `
                            <div style="color: #64748b; font-size: 11px; margin-top: 4px;">
                                ${Object.entries(result.metadata).slice(0, 3).map(([k, v]) => 
                                    `<span style="margin-right: 12px;"><strong>${k}:</strong> ${String(v).substring(0, 30)}</span>`
                                ).join('')}
                            </div>
                        ` : ''}
                    </div>
                `;
            });
            html += '</div>';
            return html;
        } else if (this.memoryQueryResults.vector_results) {
            // Hybrid retrieval results
            const session = this.memoryQueryResults.vector_results.session || [];
            const longTerm = this.memoryQueryResults.vector_results.long_term || [];
            const graphContext = this.memoryQueryResults.graph_context;
            
            let html = `
                <div style="display: flex; flex-direction: column; gap: 16px;">
                    <div>
                        <div style="color: #60a5fa; font-weight: 600; margin-bottom: 8px; font-size: 13px;">Session Results (${session.length})</div>
                        <div style="display: flex; flex-direction: column; gap: 6px; max-height: 200px; overflow-y: auto;">
            `;
            
            session.forEach((result, idx) => {
                html += `
                    <div style="background: #0f172a; padding: 10px; border-radius: 4px; border-left: 3px solid #8b5cf6; position: relative;">
                        <div style="display: flex; justify-content: space-between; align-items: start;">
                            <div style="color: #cbd5e1; font-size: 12px; flex: 1;">${this.escapeHtml(result.text?.substring(0, 150) || result.id)}...</div>
                            <button 
                                class="panel-btn" 
                                onclick="app.toggleResultMenu(event, 'session-${idx}')"
                                style="padding: 2px 6px; font-size: 11px; margin-left: 8px;"
                            >
                                ⋮
                            </button>
                            <div id="result-menu-session-${idx}" class="result-dropdown-menu" style="display: none; position: absolute; right: 0; top: 20px; background: #1e293b; border: 1px solid #334155; border-radius: 4px; min-width: 180px; z-index: 1000; box-shadow: 0 4px 12px rgba(0,0,0,0.3);">
                                <div class="result-menu-item" onclick="app.viewResultDetails('${result.id}')" style="padding: 8px 12px; cursor: pointer; color: #cbd5e1; font-size: 12px; border-bottom: 1px solid #334155;">📄 View Details</div>
                                <div class="result-menu-item" onclick="app.focusInGraph('${result.id}')" style="padding: 8px 12px; cursor: pointer; color: #cbd5e1; font-size: 12px; border-bottom: 1px solid #334155;">🎯 Focus in Graph</div>
                                <div class="result-menu-item" onclick="app.loadResultSubgraph('${result.id}')" style="padding: 8px 12px; cursor: pointer; color: #cbd5e1; font-size: 12px;">🗺️ Load Subgraph</div>
                            </div>
                        </div>
                    </div>
                `;
            });
            
            html += `
                        </div>
                    </div>
                    
                    <div>
                        <div style="color: #10b981; font-weight: 600; margin-bottom: 8px; font-size: 13px;">Long-term Results (${longTerm.length})</div>
                        <div style="display: flex; flex-direction: column; gap: 6px; max-height: 200px; overflow-y: auto;">
            `;
            
            longTerm.forEach((result, idx) => {
                html += `
                    <div style="background: #0f172a; padding: 10px; border-radius: 4px; border-left: 3px solid #10b981; position: relative;">
                        <div style="display: flex; justify-content: space-between; align-items: start;">
                            <div style="color: #cbd5e1; font-size: 12px; flex: 1;">${this.escapeHtml(result.text?.substring(0, 150) || result.id)}...</div>
                            <button 
                                class="panel-btn" 
                                onclick="app.toggleResultMenu(event, 'longterm-${idx}')"
                                style="padding: 2px 6px; font-size: 11px; margin-left: 8px;"
                            >
                                ⋮
                            </button>
                            <div id="result-menu-longterm-${idx}" class="result-dropdown-menu" style="display: none; position: absolute; right: 0; top: 20px; background: #1e293b; border: 1px solid #334155; border-radius: 4px; min-width: 180px; z-index: 1000; box-shadow: 0 4px 12px rgba(0,0,0,0.3);">
                                <div class="result-menu-item" onclick="app.viewResultDetails('${result.id}')" style="padding: 8px 12px; cursor: pointer; color: #cbd5e1; font-size: 12px; border-bottom: 1px solid #334155;">📄 View Details</div>
                                <div class="result-menu-item" onclick="app.focusInGraph('${result.id}')" style="padding: 8px 12px; cursor: pointer; color: #cbd5e1; font-size: 12px; border-bottom: 1px solid #334155;">🎯 Focus in Graph</div>
                                <div class="result-menu-item" onclick="app.loadResultSubgraph('${result.id}')" style="padding: 8px 12px; cursor: pointer; color: #cbd5e1; font-size: 12px;">🗺️ Load Subgraph</div>
                            </div>
                        </div>
                    </div>
                `;
            });
            
            html += `
                        </div>
                    </div>
            `;
            
            if (graphContext) {
                const nodeCount = graphContext.nodes?.length || 0;
                const relCount = graphContext.rels?.length || 0;
                html += `
                    <div>
                        <div style="color: #f59e0b; font-weight: 600; margin-bottom: 8px; font-size: 13px;">
                            Graph Context (${nodeCount} nodes, ${relCount} relationships)
                        </div>
                        <button 
                            class="panel-btn" 
                            onclick="app.visualizeSubgraph(${JSON.stringify(graphContext).replace(/"/g, '&quot;')})"
                        >
                            📊 Visualize in Graph
                        </button>
                    </div>
                `;
            }
            
            html += '</div>';
            return html;
        }
        
        return '<p style="color: #94a3b8;">Unknown result format</p>';
    };

    // Render entities list
    VeraChat.prototype.renderEntitiesList = function() {
        if (this.memoryEntities.length === 0) {
            return '<p style="color: #94a3b8; font-size: 13px;">No entities extracted yet</p>';
        }
        
        let html = '<div style="display: flex; flex-direction: column; gap: 8px; max-height: 400px; overflow-y: auto;">';
        
        this.memoryEntities.forEach(entity => {
            const confidenceColor = entity.confidence > 0.8 ? '#10b981' : 
                                entity.confidence > 0.5 ? '#f59e0b' : '#ef4444';
            
            html += `
                <div class="memoryQuery" style=" padding: 12px; border-radius: 6px; border-left: 3px solid ${confidenceColor};">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 6px;">
                        <div style="color: #e2e8f0; font-weight: 600; font-size: 13px;">${this.escapeHtml(entity.text)}</div>
                        <div style="display: flex; gap: 8px; align-items: center;">
                            <span style="font-size: 11px; color: #94a3b8;">${(entity.confidence * 100).toFixed(0)}%</span>
                            <button 
                                class="panel-btn" 
                                onclick="app.focusOnEntity('${entity.id}')"
                                style="padding: 4px 8px; font-size: 11px;"
                            >
                                🎯 Focus
                            </button>
                        </div>
                    </div>
                    <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                        ${entity.labels?.map(label => 
                            `<span class="label-badge" style="font-size: 10px;">${label}</span>`
                        ).join('') || ''}
                    </div>
                </div>
            `;
        });
        
        html += '</div>';
        return html;
    };

    // Render relationships list
    VeraChat.prototype.renderRelationshipsList = function() {
        if (this.memoryRelationships.length === 0) {
            return '<p style="color: #94a3b8; font-size: 13px;">No relationships extracted yet</p>';
        }
        
        let html = '<div style="display: flex; flex-direction: column; gap: 8px; max-height: 400px; overflow-y: auto;">';
        
        this.memoryRelationships.forEach(rel => {
            html += `
                <div class="memoryQuery" style="padding: 12px; border-radius: 6px; border-left: 3px solid #3b82f6;">
                    <div style="color: #e2e8f0; font-size: 13px; margin-bottom: 6px;">
                        <span style="color: #60a5fa;">${this.escapeHtml(rel.head)}</span>
                        <span style="color: #94a3b8; margin: 0 8px;">—[${this.escapeHtml(rel.relation)}]→</span>
                        <span style="color: #a78bfa;">${this.escapeHtml(rel.tail)}</span>
                    </div>
                    ${rel.context ? `
                        <div style="color: #64748b; font-size: 11px; margin-top: 6px; font-style: italic;">
                            "${this.escapeHtml(rel.context.substring(0, 100))}..."
                        </div>
                    ` : ''}
                    ${rel.confidence ? `
                        <div style="color: #94a3b8; font-size: 11px; margin-top: 4px;">
                            Confidence: ${(rel.confidence * 100).toFixed(0)}%
                        </div>
                    ` : ''}
                </div>
            `;
        });
        
        html += '</div>';
        return html;
    };

    // Helper: Perform memory query
    VeraChat.prototype.performMemoryQuery = async function() {
        const input = document.getElementById('memory-query-input');
        const typeSelect = document.getElementById('memory-retrieval-type');
        
        const query = input.value.trim();
        const retrievalType = typeSelect.value;
        
        if (!query) return;
        
        if (retrievalType === 'hybrid') {
            await this.hybridRetrieve(query, 20, 3, 2);
        } else {
            await this.queryMemory(query, retrievalType, 20);
        }
    };

    // Helper: Perform entity extraction
    VeraChat.prototype.performEntityExtraction = async function() {
        const input = document.getElementById('entity-extract-input');
        const autoPromote = document.getElementById('auto-promote-checkbox').checked;
        
        const text = input.value.trim();
        if (!text) return;
        
        await this.extractEntities(text, autoPromote);
        input.value = '';
        
        // Reload entities list
        await this.loadSessionEntities();
        await this.loadSessionRelationships();
    };

    // Helper: Focus on entity in graph
    VeraChat.prototype.focusOnEntity = async function(entityId) {
        // Get subgraph around this entity
        await this.getMemorySubgraph([entityId], 2);
    };

    // Load memory data when tab opens
    VeraChat.prototype.loadMemoryData = async function() {
        await Promise.all([
            this.loadSessionEntities(),
            this.loadSessionRelationships()
        ]);
        this.updateMemoryUI();
    };

    // ============================================================
    // Result Menu Actions
    // ============================================================

    // Toggle dropdown menu for result items
    VeraChat.prototype.toggleResultMenu = function(event, menuId) {
        event.stopPropagation();
        
        // Close all other menus
        document.querySelectorAll('.result-dropdown-menu').forEach(menu => {
            if (menu.id !== `result-menu-${menuId}`) {
                menu.style.display = 'none';
            }
        });
        
        // Toggle this menu
        const menu = document.getElementById(`result-menu-${menuId}`);
        if (menu) {
            menu.style.display = menu.style.display === 'none' ? 'block' : 'none';
        }
    };

    // Close menus when clicking outside
    document.addEventListener('click', function(event) {
        if (!event.target.closest('.result-menu-btn')) {
            document.querySelectorAll('.result-dropdown-menu').forEach(menu => {
                menu.style.display = 'none';
            });
        }
    });

    // View detailed information about a result
    VeraChat.prototype.viewResultDetails = async function(resultId) {
        const panel = document.getElementById('property-panel');
        const content = document.getElementById('panel-content');
        
        // Show loading state
        panel.classList.add('active');
        content.innerHTML = '<div style="padding: 20px; color: #94a3b8;">Loading details...</div>';
        
        try {
            // Try to get node details from graph
            if (window.GraphAddon && window.GraphAddon.nodesData[resultId]) {
                window.GraphAddon.showNodeDetails(resultId, true);
            } else {
                // Fallback: fetch from API or show basic info
                const response = await fetch(`http://llm.int:8888/api/graph/session/${this.sessionId}`);
                const data = await response.json();
                
                const node = data.nodes.find(n => n.id === resultId);
                if (node) {
                    this.displayNodeDetails(node);
                } else {
                    content.innerHTML = `
                        <div style="padding: 20px;">
                            <h3 style="color: #60a5fa; margin-bottom: 12px;">Result: ${resultId}</h3>
                            <p style="color: #94a3b8;">Node not found in current graph view.</p>
                            <button class="panel-btn" onclick="app.loadResultSubgraph('${resultId}')" style="margin-top: 12px;">
                                Load Subgraph
                            </button>
                        </div>
                    `;
                }
            }
        } catch (error) {
            console.error('Error viewing result details:', error);
            content.innerHTML = `
                <div style="padding: 20px;">
                    <h3 style="color: #ef4444;">Error</h3>
                    <p style="color: #94a3b8;">${error.message}</p>
                </div>
            `;
        }
        
        // Close dropdown menu
        document.querySelectorAll('.result-dropdown-menu').forEach(menu => {
            menu.style.display = 'none';
        });
    };

    // Display node details in property panel
    VeraChat.prototype.displayNodeDetails = function(node) {
        const content = document.getElementById('panel-content');
        
        let html = `
            <div style="padding: 16px;">
                <div class="section">
                    <div class="section-title">Node Information</div>
                    <div class="property">
                        <span class="property-key">ID:</span> ${node.id}
                    </div>
                    <div class="property">
                        <span class="property-key">Type:</span> ${node.type || 'N/A'}
                    </div>
                </div>
                
                <div class="section">
                    <div class="section-title">Labels</div>
                    <div>
                        ${node.labels?.map(label => 
                            `<span class="label-badge">${label}</span>`
                        ).join('') || '<span style="color: #64748b;">No labels</span>'}
                    </div>
                </div>
                
                ${node.properties ? `
                    <div class="section">
                        <div class="section-title">Properties</div>
                        ${Object.entries(node.properties).map(([key, value]) => `
                            <div class="property">
                                <span class="property-key">${key}:</span> 
                                ${typeof value === 'string' && value.length > 100 
                                    ? value.substring(0, 100) + '...' 
                                    : String(value)}
                            </div>
                        `).join('')}
                    </div>
                ` : ''}
                
                <div class="section">
                    <div class="section-title">Actions</div>
                    <button class="panel-btn" onclick="app.focusInGraph('${node.id}')" style="margin-right: 8px; margin-bottom: 8px;">
                        🎯 Focus in Graph
                    </button>
                    <button class="panel-btn" onclick="app.loadResultSubgraph('${node.id}')" style="margin-right: 8px; margin-bottom: 8px;">
                        🗺️ Load Subgraph
                    </button>
                    ${node.properties?.text ? `
                        <button class="panel-btn" onclick="app.extractFromResult('${node.id}', \`${this.escapeHtml(node.properties.text)}\`)" style="margin-bottom: 8px;">
                            🧠 Extract Entities
                        </button>
                    ` : ''}
                </div>
            </div>
        `;
        
        content.innerHTML = html;
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
                // Add subgraph to existing graph
                const newNodes = data.subgraph.nodes.map(n => ({
                    id: n.id,
                    label: n.properties?.text?.substring(0, 30) || n.id,
                    title: JSON.stringify(n.properties, null, 2),
                    color: n.properties?.type === 'extracted_entity' ? '#10b93a' : '#3b82f6',
                    size: 30,
                    properties: n.properties
                }));
                
                const newEdges = data.subgraph.rels.map((r, idx) => ({
                    id: `subgraph-edge-${nodeId}-${idx}`,
                    from: r.start,
                    to: r.end,
                    label: r.type || r.properties?.rel,
                    color: { color: '#f59e0b', highlight: '#fbbf24' },
                    width: 3
                }));
                
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
                // Update network data
                const nodes = data.nodes.map(n => ({
                    id: n.id,
                    label: n.label,
                    title: n.title,
                    properties: n.properties,
                    type: n.type || n.labels,
                    color: n.color || '#3b82f6',
                    size: n.size || 25
                }));
                
                const edges = data.edges.map(e => ({
                    id: e.id || `${e.from}-${e.to}`,
                    from: e.from,
                    to: e.to,
                    label: e.label,
                    title: e.label
                }));
                
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

    // Copy result text to clipboard
    VeraChat.prototype.copyResultText = function(text) {
        navigator.clipboard.writeText(text).then(() => {
            this.addSystemMessage('Text copied to clipboard');
        }).catch(err => {
            console.error('Failed to copy text:', err);
            this.addSystemMessage('Failed to copy text');
        });
        
        // Close dropdown menu
        document.querySelectorAll('.result-dropdown-menu').forEach(menu => {
            menu.style.display = 'none';
        });
    };

})();