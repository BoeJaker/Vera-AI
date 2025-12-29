/**
 * GraphToolExecutor Module - Enhanced with Plugin Support, Search, and Drag-and-Drop
 * Executes both Vera tools and plugins against selected graph nodes
 * Now renders in GraphInfoCard with search filtering and property drag-and-drop
 */

(function() {
    'use strict';
    
    window.GraphToolExecutor = {
        
        // Store references
        graphAddon: null,
        sessionId: null,
        apiBaseUrl: 'http://llm.int:8888',
        availableTools: [],
        availablePlugins: [],
        executionHistory: [],
        draggedProperty: null,  // Store dragged property data
        searchDebounceTimer: null,  // For debouncing search input
        propertyStore: {},  // NEW: Store properties by ID for safe drag/drop
        
        /**
         * Initialize the module
         */
        init: function(graphAddon, sessionId) {
            console.log('GraphToolExecutor.init called');
            this.graphAddon = graphAddon;
            this.sessionId = sessionId;
            
            // Load available tools and plugins
            this.loadAvailableTools();
            this.loadAvailablePlugins();
            
            console.log('GraphToolExecutor initialized for session:', sessionId);
        },
        
        /**
         * Load available tools from API
         */
        loadAvailableTools: async function() {
            try {
                // NEW: Use the dedicated tools API
                const response = await fetch(
                    `${this.apiBaseUrl}/api/tools/${this.sessionId}/list`
                );
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                
                const data = await response.json();
                this.availableTools = data.tools || [];
                
                console.log('Loaded', this.availableTools.length, 'tools');
                
            } catch (error) {
                console.error('Error loading tools:', error);
                this.availableTools = [];
            }
        },
        /**
         * Load available plugins from API
         */
        loadAvailablePlugins: async function() {
            try {
                const response = await fetch(
                    `${this.apiBaseUrl}/api/plugins/${this.sessionId}/list`
                );
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                
                const data = await response.json();
                this.availablePlugins = data || [];
                
                console.log('Loaded', this.availablePlugins.length, 'plugins');
                
            } catch (error) {
                console.error('Error loading plugins:', error);
                this.availablePlugins = [];
            }
        },
        
        /**
         * Debounced search handler to prevent re-rendering on every keystroke
         */
        handleSearchInput: function(nodeId, value) {
            // Clear existing timer
            if (this.searchDebounceTimer) {
                clearTimeout(this.searchDebounceTimer);
            }
            
            // Set new timer - only re-render after user stops typing for 300ms
            this.searchDebounceTimer = setTimeout(() => {
                this.showToolSelector(nodeId, value);
            }, 300);
        },
        
        /**
         * Show tool/plugin selection dialog for a node - RENDERS IN INFO CARD
         */
        showToolSelector: function(nodeId, searchTerm = '') {
            if (!window.GraphInfoCard) {
                alert('GraphInfoCard not available');
                return;
            }
            
            const nodeData = this.graphAddon.nodesData[nodeId];
            const nodeName = nodeData ? nodeData.display_name : nodeId;
            const nodeClassType = nodeData ? (nodeData.class_type || nodeData.labels?.[0]) : 'unknown';
            
            window.GraphInfoCard.inlineMode = true;
            window.GraphInfoCard.isExpanded = true;
            
            // Filter tools and plugins by compatibility
            const allTools = this.availableTools;
            const compatiblePlugins = this.availablePlugins.filter(plugin => 
                plugin.class_types.length === 0 || 
                plugin.class_types.includes(nodeClassType)
            );
            
            // Apply search filter
            const search = searchTerm.toLowerCase();
            const filteredTools = search ? allTools.filter(tool => 
                tool.name.toLowerCase().includes(search) ||
                (tool.description || '').toLowerCase().includes(search)
            ) : allTools;
            
            const filteredPlugins = search ? compatiblePlugins.filter(plugin =>
                (plugin.name || plugin.tool_name).toLowerCase().includes(search) ||
                (plugin.description || '').toLowerCase().includes(search)
            ) : compatiblePlugins;
            
            // Group tools by common categories
            const categories = {
                'Plugins': filteredPlugins,
                'Analysis': this.filterByNames(filteredTools, ['deep_llm', 'fast_llm', 'text_stats']),
                'Web': this.filterByNames(filteredTools, ['web_search', 'web_search_deep', 'news_search']),
                'File': this.filterByNames(filteredTools, ['read_file', 'write_file', 'list_directory']),
                'Code': this.filterByNames(filteredTools, ['python', 'bash']),
                'Data': this.filterByNames(filteredTools, ['parse_json', 'sqlite_query', 'csv_to_json']),
                'Other': []
            };
            
            // Categorize remaining tools
            const categorizedNames = new Set();
            Object.values(categories).forEach(cat => {
                if (Array.isArray(cat)) {
                    cat.forEach(item => categorizedNames.add(item.name || item.tool_name));
                }
            });
            
            categories['Other'] = filteredTools.filter(tool => !categorizedNames.has(tool.name));
            
            // Count total results
            const totalResults = Object.values(categories).reduce((sum, cat) => 
                sum + (Array.isArray(cat) ? cat.length : 0), 0
            );
            
            // Build HTML
            let toolsHtml = '';
            
            // Add search box
            toolsHtml += `
                <div style="margin-bottom: 16px; position: sticky; top: 0; background: #0f172a; z-index: 10; padding: 12px; border-radius: 8px; border: 1px solid #1e293b;">
                    <div style="position: relative;">
                        <input 
                            type="text" 
                            id="tool-search-input"
                            placeholder="🔍 Search tools and plugins..." 
                            value="${this.escapeHtml(searchTerm)}"
                            oninput="window.GraphToolExecutor.handleSearchInput('${nodeId}', this.value)"
                            style="
                                width: 100%; padding: 10px 40px 10px 12px; background: #1e293b; color: #e2e8f0;
                                border: 1px solid #334155; border-radius: 6px; font-size: 13px;
                                outline: none; transition: border-color 0.15s;
                            "
                            onfocus="this.style.borderColor='#60a5fa'"
                            onblur="this.style.borderColor='#334155'"
                        >
                        ${searchTerm ? `
                            <button 
                                onclick="window.GraphToolExecutor.showToolSelector('${nodeId}', '')"
                                style="
                                    position: absolute; right: 8px; top: 50%; transform: translateY(-50%);
                                    background: #334155; color: #94a3b8; border: none;
                                    width: 24px; height: 24px; border-radius: 4px; cursor: pointer;
                                    display: flex; align-items: center; justify-content: center; font-size: 14px;
                                    transition: all 0.15s;
                                "
                                onmouseover="this.style.background='#475569'; this.style.color='#e2e8f0'"
                                onmouseout="this.style.background='#334155'; this.style.color='#94a3b8'"
                            >×</button>
                        ` : ''}
                    </div>
                    ${search ? `
                        <div style="color: #64748b; font-size: 11px; margin-top: 6px;">
                            Found ${totalResults} result${totalResults !== 1 ? 's' : ''} for "${this.escapeHtml(searchTerm)}"
                        </div>
                    ` : ''}
                </div>
            `;
            
            // Show "no results" message if search yields nothing
            if (search && totalResults === 0) {
                toolsHtml += `
                    <div style="text-align: center; padding: 40px;">
                        <div style="font-size: 48px; margin-bottom: 12px; opacity: 0.5;">🔍</div>
                        <div style="color: #64748b; font-size: 14px; margin-bottom: 8px;">No tools or plugins found</div>
                        <div style="color: #475569; font-size: 12px;">Try a different search term</div>
                    </div>
                `;
            }
            
            // Build category sections
            for (const [category, items] of Object.entries(categories)) {
                if (!items || items.length === 0) continue;
                
                const isPlugin = category === 'Plugins';
                const icon = isPlugin ? '🔌' : '🔧';
                
                toolsHtml += `
                    <div style="margin-bottom: 16px;">
                        <div style="
                            color: #60a5fa; font-size: 11px; font-weight: 700; 
                            margin-bottom: 8px; text-transform: uppercase;
                            letter-spacing: 0.5px;
                        ">
                            ${icon} ${category}
                            ${isPlugin ? `<span style="color: #64748b; font-weight: normal; font-size: 10px; margin-left: 4px;">(${items.length} compatible)</span>` : ''}
                        </div>
                        <div style="display: flex; flex-direction: column; gap: 6px;">
                `;
                
                items.forEach(item => {
                    const name = item.name || item.tool_name;
                    const desc = item.description || 'No description';
                    const shortDesc = desc.length > 100 ? desc.substring(0, 100) + '...' : desc;
                    
                    const itemType = isPlugin ? 'plugin' : 'tool';
                    const badgeColor = isPlugin ? '#8b5cf6' : '#3b82f6';
                    
                    // Highlight search term if present
                    let displayName = this.escapeHtml(name);
                    let displayDesc = this.escapeHtml(shortDesc);
                    if (search) {
                        const regex = new RegExp(`(${this.escapeHtml(search)})`, 'gi');
                        displayName = displayName.replace(regex, '<mark style="background: #fbbf2444; color: #fbbf24; padding: 0 2px; border-radius: 2px;">$1</mark>');
                        displayDesc = displayDesc.replace(regex, '<mark style="background: #fbbf2444; color: #fbbf24; padding: 0 2px; border-radius: 2px;">$1</mark>');
                    }
                    
                    toolsHtml += `
                        <div 
                            onclick="window.GraphToolExecutor.selectItem('${nodeId}', '${this.escapeHtml(name)}', '${itemType}')" 
                            style="
                                padding: 12px;
                                background: #1e293b;
                                border: 1px solid #334155;
                                border-left: 3px solid ${badgeColor};
                                border-radius: 6px;
                                cursor: pointer;
                                transition: all 0.15s;
                            " 
                            onmouseover="this.style.background='#334155'; this.style.transform='translateX(4px)'" 
                            onmouseout="this.style.background='#1e293b'; this.style.transform='translateX(0)'">
                            <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 4px;">
                                <div style="color: #e2e8f0; font-weight: 600; font-size: 13px;">${displayName}</div>
                                <span style="
                                    padding: 2px 8px; font-size: 10px; font-weight: 600;
                                    background: ${badgeColor}22; color: ${badgeColor};
                                    border-radius: 4px; flex-shrink: 0; margin-left: 8px;
                                ">${itemType.toUpperCase()}</span>
                            </div>
                            <div style="color: #94a3b8; font-size: 11px; line-height: 1.4;">${displayDesc}</div>
                            ${isPlugin && item.class_types.length > 0 ? `
                                <div style="color: #64748b; font-size: 10px; margin-top: 4px; font-style: italic;">
                                    Compatible: ${item.class_types.join(', ')}
                                </div>
                            ` : ''}
                        </div>
                    `;
                });
                
                toolsHtml += `</div></div>`;
            }
            
            // Add reload plugins button
            if (!search) {
                toolsHtml += `
                    <div style="margin-top: 16px; padding: 14px; background: #0f172a; border-radius: 8px; border: 1px solid #1e293b;">
                        <button onclick="window.GraphToolExecutor.reloadPlugins('${nodeId}')" style="
                            width: 100%; padding: 10px; background: #8b5cf6; color: white;
                            border: none; border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 13px;
                            transition: all 0.15s;
                        " onmouseover="this.style.background='#7c3aed'" onmouseout="this.style.background='#8b5cf6'">
                            🔄 Reload Plugins
                        </button>
                        <div style="color: #64748b; font-size: 10px; margin-top: 6px; text-align: center;">
                            Refresh plugin list after changes
                        </div>
                    </div>
                `;
            }
            
            const content = `
                <div style="margin-bottom: 16px; padding: 12px; background: #0f172a; border-radius: 8px; border: 1px solid #1e293b;">
                    <div style="color: #94a3b8; font-size: 11px; margin-bottom: 4px;">Target Node</div>
                    <div style="color: #e2e8f0; font-size: 14px; font-weight: 600; margin-bottom: 4px;">
                        ${this.escapeHtml(nodeName)}
                    </div>
                    <div style="color: #64748b; font-size: 11px;">
                        Type: <span style="color: #8b5cf6;">${this.escapeHtml(nodeClassType)}</span>
                    </div>
                </div>
                
                <div style="max-height: 450px; overflow-y: auto; padding-right: 4px;">
                    ${toolsHtml}
                </div>
            `;
            
            const backAction = `window.GraphInfoCard.expandNodeInfo('${nodeId}')`;
            window.GraphInfoCard.showInlineContent('🔧 Execute Tool or Plugin', content, backAction);
            
            // Re-focus search input and restore cursor position after render
            setTimeout(() => {
                const searchInput = document.getElementById('tool-search-input');
                if (searchInput) {
                    const cursorPos = searchTerm.length; // Put cursor at end
                    searchInput.focus();
                    searchInput.setSelectionRange(cursorPos, cursorPos);
                }
            }, 50);
        },
        
        /**
         * Helper to filter tools by names
         */
        filterByNames: function(tools, names) {
            return tools.filter(tool => names.includes(tool.name));
        },
        
        /**
         * Select a tool or plugin and show input form - RENDERS IN INFO CARD
         */
        selectItem: async function(nodeId, itemName, itemType) {
            if (!window.GraphInfoCard) {
                alert('GraphInfoCard not available');
                return;
            }
            
            const nodeData = this.graphAddon.nodesData[nodeId];
            const nodeName = nodeData ? nodeData.display_name : nodeId;
            
            window.GraphInfoCard.inlineMode = true;
            window.GraphInfoCard.isExpanded = true;
            
            // Show loading state
            window.GraphInfoCard.showInlineContent(
                '🔧 Loading Schema',
                `<div style="text-align: center; padding: 40px;">
                    <div style="font-size: 48px; margin-bottom: 16px;">⚙️</div>
                    <div style="color: #60a5fa; font-size: 14px; font-weight: 600;">Loading schema...</div>
                </div>`,
                `window.GraphToolExecutor.showToolSelector('${nodeId}')`
            );
            
            try {
                // Get schema based on type
                const endpoint = itemType === 'plugin'
                    ? `${this.apiBaseUrl}/api/plugins/${this.sessionId}/plugin/${encodeURIComponent(itemName)}/schema`
                    : `${this.apiBaseUrl}/api/tools/${this.sessionId}/tool/${encodeURIComponent(itemName)}/schema`;
                
                const response = await fetch(endpoint);
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                
                const schema = await response.json();
                
                // Build input form
                this.showItemInputForm(nodeId, nodeName, itemName, itemType, schema);
                
            } catch (error) {
                console.error('Error loading schema:', error);
                window.GraphInfoCard.showInlineContent(
                    '⚠️ Error',
                    `<div style="text-align: center; padding: 30px;">
                        <div style="font-size: 48px; margin-bottom: 16px;">⚠️</div>
                        <div style="color: #ef4444; font-size: 14px; font-weight: 600; margin-bottom: 8px;">Error Loading Schema</div>
                        <div style="color: #94a3b8; font-size: 13px; margin-bottom: 20px;">${this.escapeHtml(error.message)}</div>
                        <button onclick="window.GraphToolExecutor.showToolSelector('${nodeId}')" style="
                            padding: 10px 24px; background: #3b82f6; color: white;
                            border: none; border-radius: 6px; cursor: pointer; font-weight: 600;
                        ">Back to Tools</button>
                    </div>`,
                    `window.GraphToolExecutor.showToolSelector('${nodeId}')`
                );
            }
        },

        /**
         * Show tool/plugin input form - RENDERS IN INFO CARD
         */
        showItemInputForm: function(nodeId, nodeName, itemName, itemType, schema) {
            if (!window.GraphInfoCard) {
                alert('GraphInfoCard not available');
                return;
            }
            
            const nodeData = this.graphAddon.nodesData[nodeId];
            
            window.GraphInfoCard.inlineMode = true;
            window.GraphInfoCard.isExpanded = true;
            
            const icon = itemType === 'plugin' ? '🔌' : '🔧';
            const badgeColor = itemType === 'plugin' ? '#8b5cf6' : '#3b82f6';
            
            // Clear property store and rebuild for this form
            this.propertyStore = {};
            
            // Build draggable properties section
            let propertiesHtml = '';
            let propIndex = 0;
            
            // Check if we have any properties to show (including node metadata)
            const hasNodeMetadata = nodeData && (nodeData.display_name || nodeId || nodeData.class_type);
            const hasProperties = nodeData && nodeData.properties && Object.keys(nodeData.properties).length > 0;
            
            if (hasNodeMetadata || hasProperties) {
                propertiesHtml = `
                    <div style="margin-bottom: 16px; padding: 12px; background: #0f172a; border-radius: 8px; border: 1px solid #1e293b;">
                        <div style="color: #94a3b8; font-size: 11px; font-weight: 600; margin-bottom: 8px;">
                            📋 Available Properties (Drag to Fields)
                        </div>
                        <div style="display: flex; flex-wrap: wrap; gap: 6px;">
                `;
                
                // Add node metadata as draggable properties (with special styling)
                if (nodeData) {
                    // Node Name
                    if (nodeData.display_name) {
                        const propId = `prop-${propIndex++}`;
                        this.propertyStore[propId] = { name: 'node_name', value: nodeData.display_name };
                        
                        propertiesHtml += `
                            <div 
                                draggable="true"
                                data-prop-id="${propId}"
                                ondragstart="window.GraphToolExecutor.handlePropertyDragStart(event, '${propId}')"
                                ondragend="window.GraphToolExecutor.handlePropertyDragEnd(event)"
                                style="
                                    padding: 6px 10px; background: #7c3aed22; border: 1px solid #7c3aed;
                                    border-radius: 4px; cursor: grab; font-size: 11px;
                                    display: inline-flex; align-items: center; gap: 6px;
                                    transition: all 0.15s;
                                "
                                onmouseover="this.style.background='#7c3aed33'; this.style.borderColor='#a78bfa'"
                                onmouseout="this.style.background='#7c3aed22'; this.style.borderColor='#7c3aed'"
                                title="${this.escapeHtml(nodeData.display_name)}"
                            >
                                <span style="color: #a78bfa; font-weight: 600;">node_name</span>
                                <span style="color: #94a3b8;">:</span>
                                <span style="color: #e2e8f0;">${this.escapeHtml(nodeData.display_name)}</span>
                            </div>
                        `;
                    }
                    
                    // Node ID
                    const nodeIdPropId = `prop-${propIndex++}`;
                    this.propertyStore[nodeIdPropId] = { name: 'node_id', value: nodeId };
                    
                    propertiesHtml += `
                        <div 
                            draggable="true"
                            data-prop-id="${nodeIdPropId}"
                            ondragstart="window.GraphToolExecutor.handlePropertyDragStart(event, '${nodeIdPropId}')"
                            ondragend="window.GraphToolExecutor.handlePropertyDragEnd(event)"
                            style="
                                padding: 6px 10px; background: #7c3aed22; border: 1px solid #7c3aed;
                                border-radius: 4px; cursor: grab; font-size: 11px;
                                display: inline-flex; align-items: center; gap: 6px;
                                transition: all 0.15s;
                            "
                            onmouseover="this.style.background='#7c3aed33'; this.style.borderColor='#a78bfa'"
                            onmouseout="this.style.background='#7c3aed22'; this.style.borderColor='#7c3aed'"
                            title="${this.escapeHtml(nodeId)}"
                        >
                            <span style="color: #a78bfa; font-weight: 600;">node_id</span>
                            <span style="color: #94a3b8;">:</span>
                            <span style="color: #e2e8f0;">${this.escapeHtml(nodeId.substring(0, 12))}...</span>
                        </div>
                    `;
                    
                    // Node Type/Class
                    if (nodeData.class_type || nodeData.labels?.[0]) {
                        const nodeType = nodeData.class_type || nodeData.labels?.[0];
                        const nodeTypePropId = `prop-${propIndex++}`;
                        this.propertyStore[nodeTypePropId] = { name: 'node_type', value: nodeType };
                        
                        propertiesHtml += `
                            <div 
                                draggable="true"
                                data-prop-id="${nodeTypePropId}"
                                ondragstart="window.GraphToolExecutor.handlePropertyDragStart(event, '${nodeTypePropId}')"
                                ondragend="window.GraphToolExecutor.handlePropertyDragEnd(event)"
                                style="
                                    padding: 6px 10px; background: #7c3aed22; border: 1px solid #7c3aed;
                                    border-radius: 4px; cursor: grab; font-size: 11px;
                                    display: inline-flex; align-items: center; gap: 6px;
                                    transition: all 0.15s;
                                "
                                onmouseover="this.style.background='#7c3aed33'; this.style.borderColor='#a78bfa'"
                                onmouseout="this.style.background='#7c3aed22'; this.style.borderColor='#7c3aed'"
                                title="${this.escapeHtml(nodeType)}"
                            >
                                <span style="color: #a78bfa; font-weight: 600;">node_type</span>
                                <span style="color: #94a3b8;">:</span>
                                <span style="color: #e2e8f0;">${this.escapeHtml(nodeType)}</span>
                            </div>
                        `;
                    }
                }
                
                // Add regular node properties
                if (nodeData && nodeData.properties) {
                    for (const [key, value] of Object.entries(nodeData.properties)) {
                        if (value === null || value === undefined) continue;
                        
                        // Store property in propertyStore with unique ID
                        const propId = `prop-${propIndex++}`;
                        this.propertyStore[propId] = { name: key, value: value };
                        
                        const displayValue = String(value).length > 30 
                            ? String(value).substring(0, 30) + '...' 
                            : String(value);
                        
                        propertiesHtml += `
                            <div 
                                draggable="true"
                                data-prop-id="${propId}"
                                ondragstart="window.GraphToolExecutor.handlePropertyDragStart(event, '${propId}')"
                                ondragend="window.GraphToolExecutor.handlePropertyDragEnd(event)"
                                style="
                                    padding: 6px 10px; background: #1e293b; border: 1px solid #334155;
                                    border-radius: 4px; cursor: grab; font-size: 11px;
                                    display: inline-flex; align-items: center; gap: 6px;
                                    transition: all 0.15s;
                                "
                                onmouseover="this.style.background='#334155'; this.style.borderColor='#60a5fa'"
                                onmouseout="this.style.background='#1e293b'; this.style.borderColor='#334155'"
                                title="${this.escapeHtml(String(value))}"
                            >
                                <span style="color: #60a5fa; font-weight: 600;">${this.escapeHtml(key)}</span>
                                <span style="color: #94a3b8;">:</span>
                                <span style="color: #e2e8f0;">${this.escapeHtml(displayValue)}</span>
                            </div>
                        `;
                    }
                }
                
                propertiesHtml += `
                        </div>
                        <div style="color: #64748b; font-size: 10px; margin-top: 8px; font-style: italic;">
                            💡 Drag properties onto input fields to auto-populate them
                            <span style="color: #a78bfa; margin-left: 8px;">● Node metadata</span>
                            <span style="color: #60a5fa; margin-left: 8px;">● Properties</span>
                        </div>
                    </div>
                `;
            }
            
            // Build form fields
            let formHtml = '';
            
            schema.parameters.forEach((param, index) => {
                let defaultValue = '';
                
                // Auto-populate from node properties
                if (nodeData && nodeData.properties) {
                    if (param.name === 'text' || param.name === 'query' || param.name === 'input') {
                        defaultValue = nodeData.properties.text || 
                                     nodeData.properties.body || 
                                     nodeData.properties.content || 
                                     nodeData.properties.summary || '';
                    } else if (param.name === 'node_id') {
                        defaultValue = nodeId;
                    } else if (nodeData.properties[param.name]) {
                        defaultValue = nodeData.properties[param.name];
                    }
                }
                
                // Fallback to schema default
                if (!defaultValue && param.default !== null && param.default !== undefined) {
                    defaultValue = param.default;
                }
                
                const isRequired = param.required ? ' *' : '';
                
                formHtml += `
                    <div 
                        class="form-field-container"
                        data-param-name="${this.escapeHtml(param.name)}"
                        style="
                            margin-bottom: 14px; 
                            background: #0f172a; 
                            padding: 12px; 
                            border-radius: 6px; 
                            border: 1px solid #1e293b;
                            transition: all 0.15s;
                        "
                        ondrop="window.GraphToolExecutor.handleFieldDrop(event)"
                        ondragover="window.GraphToolExecutor.handleFieldDragOver(event)"
                        ondragleave="window.GraphToolExecutor.handleFieldDragLeave(event)"
                    >
                        <label style="display: block; color: #e2e8f0; font-size: 12px; font-weight: 600; margin-bottom: 4px;">
                            ${this.escapeHtml(param.name)}${isRequired}
                        </label>
                        <div style="color: #64748b; font-size: 11px; margin-bottom: 8px; line-height: 1.3;">
                            ${this.escapeHtml(param.description || 'No description')}
                        </div>
                        ${this.renderFormField(param, defaultValue)}
                    </div>
                `;
            });
            
            const content = `
                <div style="margin-bottom: 16px; padding: 12px; background: #0f172a; border-radius: 8px; border: 1px solid #1e293b;">
                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                        <div style="font-size: 16px; font-weight: 600; color: #e2e8f0;">
                            ${icon} ${this.escapeHtml(itemName)}
                        </div>
                        <span style="
                            padding: 3px 10px; font-size: 10px; font-weight: 600;
                            background: ${badgeColor}22; color: ${badgeColor};
                            border-radius: 4px;
                        ">${itemType.toUpperCase()}</span>
                    </div>
                    <div style="color: #94a3b8; font-size: 12px; margin-bottom: 4px;">
                        On node: <strong style="color: #e2e8f0;">${this.escapeHtml(nodeName)}</strong>
                    </div>
                    <div style="color: #64748b; font-size: 11px; font-style: italic; line-height: 1.3;">
                        ${this.escapeHtml(schema.description)}
                    </div>
                </div>
                
                ${propertiesHtml}
                
                <form id="item-input-form" style="max-height: 350px; overflow-y: auto; padding-right: 4px;">
                    ${formHtml || '<div style="color: #64748b; text-align: center; padding: 20px;">No parameters required</div>'}
                </form>
                
                <div style="display: flex; gap: 8px; margin-top: 16px;">
                    <button onclick="window.GraphToolExecutor.executeItem('${nodeId}', '${this.escapeHtml(itemName).replace(/'/g, "\\'")}', '${itemType}')" style="
                        flex: 1; padding: 12px; background: ${badgeColor}; color: white;
                        border: none; border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 14px;
                        transition: all 0.15s;
                    " onmouseover="this.style.transform='translateY(-1px)'; this.style.boxShadow='0 4px 12px rgba(0,0,0,0.3)'" 
                       onmouseout="this.style.transform=''; this.style.boxShadow=''">
                        Execute ${icon}
                    </button>
                    <button onclick="window.GraphToolExecutor.showToolSelector('${nodeId}')" style="
                        padding: 12px 24px; background: #334155; color: #e2e8f0;
                        border: 1px solid #475569; border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 14px;
                    ">Back</button>
                </div>
            `;
            
            window.GraphInfoCard.showInlineContent(
                `${icon} ${this.escapeHtml(itemName)}`,
                content,
                `window.GraphToolExecutor.showToolSelector('${nodeId}')`
            );
        },
        
        /**
         * Handle drag start for property items - FIXED VERSION
         */
        handlePropertyDragStart: function(event, propId) {
            const propData = this.propertyStore[propId];
            if (!propData) {
                console.error('Property not found:', propId);
                return;
            }
            
            this.draggedProperty = propData;
            event.dataTransfer.effectAllowed = 'copy';
            event.dataTransfer.setData('text/plain', String(propData.value));
            event.target.style.opacity = '0.5';
            event.target.style.cursor = 'grabbing';
            
            console.log('Dragging property:', propData.name, '=', propData.value);
        },
        
        /**
         * Handle drag end for property items - RESET OPACITY
         */
        handlePropertyDragEnd: function(event) {
            event.target.style.opacity = '1';
            event.target.style.cursor = 'grab';
        },
        
        /**
         * Handle drag over field container
         */
        handleFieldDragOver: function(event) {
            event.preventDefault();
            event.stopPropagation();
            event.dataTransfer.dropEffect = 'copy';
            
            const container = event.currentTarget;
            container.style.borderColor = '#60a5fa';
            container.style.background = '#1e293b';
        },
        
        /**
         * Handle drag leave field container
         */
        handleFieldDragLeave: function(event) {
            // Only reset if we're actually leaving the container (not entering a child)
            if (event.currentTarget.contains(event.relatedTarget)) {
                return;
            }
            
            const container = event.currentTarget;
            container.style.borderColor = '#1e293b';
            container.style.background = '#0f172a';
        },
        
        /**
         * Handle drop on field container - FIXED VERSION
         */
        handleFieldDrop: function(event) {
            event.preventDefault();
            event.stopPropagation();
            
            const container = event.currentTarget;
            container.style.borderColor = '#1e293b';
            container.style.background = '#0f172a';
            
            if (!this.draggedProperty) {
                console.error('No dragged property found');
                return;
            }
            
            // Get param name from container
            const paramName = container.getAttribute('data-param-name');
            if (!paramName) {
                console.error('No param name found on container');
                return;
            }
            
            // Find the input field within this container
            const inputField = container.querySelector(`#param-${paramName}`);
            if (!inputField) {
                console.error('Input field not found for param:', paramName);
                return;
            }
            
            // Set the value based on input type
            const value = this.draggedProperty.value;
            if (inputField.tagName === 'SELECT') {
                inputField.value = String(value);
            } else if (inputField.type === 'number') {
                inputField.value = parseFloat(value) || 0;
            } else if (inputField.tagName === 'TEXTAREA') {
                inputField.value = String(value);
            } else {
                inputField.value = String(value);
            }
            
            // Visual feedback
            inputField.style.borderColor = '#10b981';
            inputField.style.background = '#1e293b';
            setTimeout(() => {
                inputField.style.borderColor = '#334155';
                inputField.style.background = '#1e293b';
            }, 800);
            
            console.log('✓ Dropped property', this.draggedProperty.name, 'into field', paramName, 'with value:', value);
            
            // Clear dragged property
            this.draggedProperty = null;
        },
        
        /**
         * Render appropriate form field based on parameter type
         */
        renderFormField: function(param, defaultValue) {
            const value = defaultValue ? this.escapeHtml(String(defaultValue)) : '';
            
            if (param.type === 'boolean') {
                return `
                    <select id="param-${this.escapeHtml(param.name)}" style="
                        width: 100%; padding: 10px; background: #1e293b; color: #e2e8f0;
                        border: 1px solid #334155; border-radius: 6px; font-size: 13px;
                        transition: all 0.15s;
                    ">
                        <option value="true" ${defaultValue === true ? 'selected' : ''}>True</option>
                        <option value="false" ${defaultValue === false ? 'selected' : ''}>False</option>
                    </select>
                `;
            } else if (param.type === 'integer' || param.type === 'number') {
                return `
                    <input type="number" id="param-${this.escapeHtml(param.name)}" value="${value}" style="
                        width: 100%; padding: 10px; background: #1e293b; color: #e2e8f0;
                        border: 1px solid #334155; border-radius: 6px; font-size: 13px;
                        transition: all 0.15s;
                    " ${param.required ? 'required' : ''}>
                `;
            } else if (value.length > 100) {
                return `
                    <textarea id="param-${this.escapeHtml(param.name)}" rows="6" style="
                        width: 100%; padding: 10px; background: #1e293b; color: #e2e8f0;
                        border: 1px solid #334155; border-radius: 6px; resize: vertical;
                        font-family: 'Monaco', 'Menlo', monospace; font-size: 12px; line-height: 1.4;
                        transition: all 0.15s;
                    " ${param.required ? 'required' : ''}>${value}</textarea>
                `;
            } else {
                return `
                    <input type="text" id="param-${this.escapeHtml(param.name)}" value="${value}" style="
                        width: 100%; padding: 10px; background: #1e293b; color: #e2e8f0;
                        border: 1px solid #334155; border-radius: 6px; font-size: 13px;
                        transition: all 0.15s;
                    " ${param.required ? 'required' : ''}>
                `;
            }
        },
        
        /**
         * Execute the tool or plugin with collected inputs - RENDERS IN INFO CARD
         */
  executeItem: async function(nodeId, itemName, itemType) {
        if (!window.GraphInfoCard) {
            alert('GraphInfoCard not available');
            return;
        }
        
        // Collect form data
        const form = document.getElementById('item-input-form');
        if (!form) {
            console.error('Form not found');
            return;
        }
        
        const inputs = form.querySelectorAll('input, select, textarea');
        
        const itemInput = {};
        inputs.forEach(input => {
            const paramName = input.id.replace('param-', '');
            let value = input.value;
            
            // Type conversion
            if (input.type === 'number') {
                value = parseFloat(value);
            } else if (input.tagName === 'SELECT' && (value === 'true' || value === 'false')) {
                value = value === 'true';
            }
            
            itemInput[paramName] = value;
        });
        
        const icon = itemType === 'plugin' ? '🔌' : '🔧';
        
        // Show executing state
        window.GraphInfoCard.showInlineContent(
            `${icon} Executing`,
            `<div style="text-align: center; padding: 40px;">
                <div style="font-size: 48px; margin-bottom: 16px;">⚙️</div>
                <div style="color: #60a5fa; font-size: 16px; font-weight: 600; margin-bottom: 8px;">
                    Executing ${icon} ${this.escapeHtml(itemName)}
                </div>
                <div style="color: #94a3b8; font-size: 13px;">Processing...</div>
            </div>`
        );
        
        try {
            const startTime = Date.now();
            
            // Execute via appropriate API
            let response;
            if (itemType === 'plugin') {
                // Use existing plugin API
                response = await fetch(
                    `${this.apiBaseUrl}/api/plugins/${this.sessionId}/execute`,
                    {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            node_id: nodeId,
                            plugin_name: itemName,
                            parameters: itemInput
                        })
                    }
                );
            } else {
                // NEW: Use enhanced tool execution API with node linking
                response = await fetch(
                    `${this.apiBaseUrl}/api/tools/${this.sessionId}/execute`,
                    {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            tool_name: itemName,
                            tool_input: itemInput,
                            node_id: nodeId,        // NEW: Pass node context
                            link_results: true      // NEW: Enable graph linking
                        })
                    }
                );
            }
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || `HTTP ${response.status}`);
            }
            
            const result = await response.json();
            const duration = Date.now() - startTime;
            
            // Store in execution history
            this.executionHistory.push({
                nodeId,
                itemName,
                itemType,
                input: itemInput,
                output: result.output,
                timestamp: new Date().toISOString(),
                duration,
                graphContext: result.graph_context  // NEW: Store graph linking info
            });
            
            // Show result with graph context
            this.showItemResult(nodeId, itemName, itemType, itemInput, result.output, 
                              duration, result.graph_context);
            
        } catch (error) {
            console.error('Execution error:', error);
            window.GraphInfoCard.showInlineContent(
                '❌ Execution Failed',
                `<div style="text-align: center; padding: 30px;">
                    <div style="font-size: 48px; margin-bottom: 16px;">❌</div>
                    <div style="color: #ef4444; font-size: 14px; font-weight: 600; margin-bottom: 8px;">
                        Execution Failed
                    </div>
                    <div style="color: #94a3b8; font-size: 13px; margin-bottom: 20px;">
                        ${this.escapeHtml(error.message)}
                    </div>
                    <button onclick="window.GraphToolExecutor.showToolSelector('${nodeId}')" style="
                        padding: 10px 24px; background: #3b82f6; color: white;
                        border: none; border-radius: 6px; cursor: pointer; font-weight: 600;
                    ">Try Again</button>
                </div>`,
                `window.GraphToolExecutor.showToolSelector('${nodeId}')`
            );
        }
    },
    
        
        /**
         * Show execution result - RENDERS IN INFO CARD
         */
        showItemResult: function(nodeId, itemName, itemType, input, output, duration, graphContext) {
                if (!window.GraphInfoCard) {
                    alert('GraphInfoCard not available');
                    return;
                }
                
                const nodeData = this.graphAddon.nodesData[nodeId];
                const nodeName = nodeData ? nodeData.display_name : nodeId;
                
                const icon = itemType === 'plugin' ? '🔌' : '🔧';
                const badgeColor = itemType === 'plugin' ? '#8b5cf6' : '#3b82f6';
                
                // Truncate output if very long
                let displayOutput = output;
                let truncated = false;
                if (output.length > 2000) {
                    displayOutput = output.substring(0, 2000);
                    truncated = true;
                }
                
                // Build graph context display
                let graphContextHtml = '';
                if (graphContext && graphContext.enabled) {
                    graphContextHtml = `
                        <div style="margin-bottom: 16px; padding: 12px; background: #0f172a; border-radius: 8px; border: 1px solid #1e293b;">
                            <div style="color: #60a5fa; font-size: 11px; font-weight: 600; margin-bottom: 8px;">
                                🔗 Graph Context Created
                            </div>
                            <div style="color: #94a3b8; font-size: 11px; font-family: 'Monaco', monospace;">
                                ${graphContext.links_created.map(link => 
                                    `<div style="margin-bottom: 4px;">• ${this.escapeHtml(link)}</div>`
                                ).join('')}
                            </div>
                            <div style="color: #64748b; font-size: 10px; margin-top: 8px; font-style: italic;">
                                💡 Result linked to ${this.escapeHtml(nodeName)} in knowledge graph
                            </div>
                        </div>
                    `;
                }
                
                const content = `
                    <div style="text-align: center; margin-bottom: 20px;">
                        <div style="font-size: 48px; margin-bottom: 8px;">✅</div>
                        <div style="color: #10b981; font-size: 16px; font-weight: 600; margin-bottom: 4px;">
                            Executed Successfully
                        </div>
                        <div style="color: #94a3b8; font-size: 12px;">
                            Completed in ${duration}ms
                        </div>
                    </div>
                    
                    <div style="margin-bottom: 16px; padding: 12px; background: #0f172a; border-radius: 8px; border: 1px solid #1e293b;">
                        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                            <span style="color: #e2e8f0; font-size: 14px; font-weight: 600;">${icon} ${this.escapeHtml(itemName)}</span>
                            <span style="
                                padding: 2px 8px; font-size: 10px; font-weight: 600;
                                background: ${badgeColor}22; color: ${badgeColor};
                                border-radius: 4px;
                            ">${itemType.toUpperCase()}</span>
                        </div>
                        <div style="color: #94a3b8; font-size: 12px;">
                            On node: <span style="color: #e2e8f0;">${this.escapeHtml(nodeName)}</span>
                        </div>
                    </div>
                    
                    ${graphContextHtml}
                    
                    <div style="margin-bottom: 16px;">
                        <div style="color: #94a3b8; font-size: 12px; font-weight: 600; margin-bottom: 8px;">Output</div>
                        <div style="
                            background: #0f172a; padding: 12px; border-radius: 6px;
                            border: 1px solid #1e293b; max-height: 300px; overflow-y: auto;
                            font-family: 'Monaco', 'Menlo', monospace; font-size: 12px; color: #e2e8f0;
                            white-space: pre-wrap; word-break: break-word; line-height: 1.4;
                        ">${this.escapeHtml(displayOutput)}${truncated ? '\n\n... [Output truncated at 2000 characters]' : ''}</div>
                    </div>
                    
                    <div style="display: flex; flex-direction: column; gap: 8px;">
                        ${graphContext && graphContext.execution_node_id ? `
                            <button onclick="window.GraphToolExecutor.viewExecutionInGraph('${graphContext.execution_node_id}')" style="
                                width: 100%; padding: 12px; background: #6366f1; color: white;
                                border: none; border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 14px;
                            ">🔍 View in Graph</button>
                        ` : ''}
                        <div style="display: flex; gap: 8px;">
                            <button onclick="window.GraphToolExecutor.showToolSelector('${nodeId}')" style="
                                flex: 1; padding: 10px; background: ${badgeColor}; color: white;
                                border: none; border-radius: 6px; cursor: pointer; font-weight: 600;
                            ">Run Another</button>
                            <button onclick="window.GraphInfoCard.expandNodeInfo('${nodeId}')" style="
                                flex: 1; padding: 10px; background: #334155; color: #e2e8f0;
                                border: 1px solid #475569; border-radius: 6px; cursor: pointer; font-weight: 600;
                            ">Back to Node</button>
                        </div>
                    </div>
                `;
                
                window.GraphInfoCard.showInlineContent(
                    '✅ Execution Complete',
                    content,
                    `window.GraphToolExecutor.showToolSelector('${nodeId}')`
                );
            },
        
        /**
         * Reload plugins from server - RENDERS IN INFO CARD
         */
        reloadPlugins: async function(nodeId) {
            if (!window.GraphInfoCard) {
                alert('GraphInfoCard not available');
                return;
            }
            
            window.GraphInfoCard.showInlineContent(
                '🔄 Reloading Plugins',
                `<div style="text-align: center; padding: 40px;">
                    <div style="font-size: 48px; margin-bottom: 16px;">🔄</div>
                    <div style="color: #8b5cf6; font-size: 16px; font-weight: 600;">
                        Reloading Plugins...
                    </div>
                </div>`
            );
            
            try {
                const response = await fetch(
                    `${this.apiBaseUrl}/api/plugins/${this.sessionId}/reload`,
                    { method: 'POST' }
                );
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                
                const result = await response.json();
                
                // Reload plugin list
                await this.loadAvailablePlugins();
                
                window.GraphInfoCard.showInlineContent(
                    '✅ Plugins Reloaded',
                    `<div style="text-align: center; padding: 30px;">
                        <div style="font-size: 48px; margin-bottom: 16px;">✅</div>
                        <div style="color: #10b981; font-size: 16px; font-weight: 600; margin-bottom: 8px;">
                            Plugins Reloaded
                        </div>
                        <div style="color: #94a3b8; font-size: 13px; margin-bottom: 20px;">
                            ${this.escapeHtml(result.message || 'Plugins reloaded successfully')}
                        </div>
                        <button onclick="window.GraphToolExecutor.showToolSelector('${nodeId}')" style="
                            padding: 10px 24px; background: #8b5cf6; color: white;
                            border: none; border-radius: 6px; cursor: pointer; font-weight: 600;
                        ">Back to Tools</button>
                    </div>`,
                    `window.GraphToolExecutor.showToolSelector('${nodeId}')`
                );
                
            } catch (error) {
                console.error('Error reloading plugins:', error);
                window.GraphInfoCard.showInlineContent(
                    '⚠️ Reload Failed',
                    `<div style="text-align: center; padding: 30px;">
                        <div style="font-size: 48px; margin-bottom: 16px;">⚠️</div>
                        <div style="color: #ef4444; font-size: 14px; font-weight: 600; margin-bottom: 8px;">
                            Reload Failed
                        </div>
                        <div style="color: #94a3b8; font-size: 13px; margin-bottom: 20px;">
                            ${this.escapeHtml(error.message)}
                        </div>
                        <button onclick="window.GraphToolExecutor.showToolSelector('${nodeId}')" style="
                            padding: 10px 24px; background: #3b82f6; color: white;
                            border: none; border-radius: 6px; cursor: pointer; font-weight: 600;
                        ">Back to Tools</button>
                    </div>`,
                    `window.GraphToolExecutor.showToolSelector('${nodeId}')`
                );
            }
        },
        
        /**
         * Save result to node properties
         */
        saveResultToNode: function(nodeId, itemType, output) {
            // Show success notification
            if (window.GraphInfoCard) {
                window.GraphInfoCard.showInlineContent(
                    '💾 Save Result',
                    `<div style="text-align: center; padding: 30px;">
                        <div style="font-size: 48px; margin-bottom: 16px;">💾</div>
                        <div style="color: #60a5fa; font-size: 14px; font-weight: 600; margin-bottom: 8px;">
                            Save to Node
                        </div>
                        <div style="color: #94a3b8; font-size: 13px; margin-bottom: 20px;">
                            This feature requires an API endpoint to update node properties.<br>
                            Implementation pending.
                        </div>
                        <button onclick="window.GraphInfoCard.expandNodeInfo('${nodeId}')" style="
                            padding: 10px 24px; background: #3b82f6; color: white;
                            border: none; border-radius: 6px; cursor: pointer; font-weight: 600;
                        ">Back to Node</button>
                    </div>`,
                    `window.GraphInfoCard.expandNodeInfo('${nodeId}')`
                );
            } else {
                alert(`Result from ${itemType} would be saved to node ${nodeId}\n\n(API implementation pending)`);
            }
        },
        
        /**
         * Escape HTML for safe display
         */
        escapeHtml: function(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        },
            viewExecutionInGraph: function(executionNodeId) {
        if (this.graphAddon && this.graphAddon.focusNode) {
            // Focus on the execution node in the graph
            this.graphAddon.focusNode(executionNodeId);
            
            // Optionally expand to show connected nodes
            if (this.graphAddon.expandNodeInfo) {
                this.graphAddon.expandNodeInfo(executionNodeId);
            }
        }
    },
    };
})();