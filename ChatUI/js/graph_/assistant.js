/**
 * GraphAIAssistant Module
 * AI-powered graph interaction with prompt templates and tool orchestration
 * Now renders in GraphInfoCard
 */

(function() {
    'use strict';
    
    window.GraphAIAssistant = {
        
        /**
         * Prompt template categories
         */
        promptTemplates: {
            analysis: [
                {
                    name: 'Summarize Graph',
                    icon: '📊',
                    description: 'Get a comprehensive summary of the graph structure',
                    template: `Analyze this knowledge graph and provide a comprehensive summary.

**Graph Overview:**
- Total nodes: {nodeCount}
- Total edges: {edgeCount}
- Node types: {nodeTypes}

**Sample nodes:**
{nodeSample}

Please provide:
1. Overall structure and organization
2. Main themes and topics
3. Key entities and their importance
4. Notable patterns or clusters
5. Potential gaps or areas for expansion`
                },
                {
                    name: 'Find Key Nodes',
                    icon: '⭐',
                    description: 'Identify the most important or central nodes',
                    template: `Identify the most important nodes in this knowledge graph.

**Graph data:**
- {nodeCount} nodes
- {edgeCount} edges

**Nodes with connections:**
{nodeSample}

Please identify and rank:
1. Highly connected hub nodes
2. Bridge nodes connecting different clusters
3. Nodes with rich content/properties
4. Nodes that appear central to the domain

For each important node, explain why it's significant.`
                },
                {
                    name: 'Explain Relationships',
                    icon: '🔗',
                    description: 'Understand how entities are connected',
                    template: `Explain the relationship patterns in this knowledge graph.

**Graph structure:**
- Nodes: {nodeCount}
- Edges: {edgeCount}
- Relationship types: {edgeTypes}

**Sample relationships:**
{edgeSample}

Please analyze:
1. Common relationship types and their meanings
2. Interesting connection patterns
3. Relationship directionality and implications
4. Missing or unexpected relationships
5. How relationships form the graph structure`
                },
                {
                    name: 'Detect Communities',
                    icon: '👥',
                    description: 'Find groups of related nodes',
                    template: `Identify distinct communities or clusters in this knowledge graph.

**Graph data:**
{nodeSample}

**Relationships:**
{edgeSample}

Please identify:
1. Distinct groups or communities of related nodes
2. The theme or topic of each community
3. Key nodes in each community
4. How communities relate to each other
5. Isolated or weakly connected nodes`
                },
                {
                    name: 'Find Patterns',
                    icon: '🔍',
                    description: 'Discover interesting patterns and insights',
                    template: `Discover patterns and interesting insights in this knowledge graph.

**Graph overview:**
- {nodeCount} nodes
- {edgeCount} edges

**Data sample:**
{nodeSample}

Look for:
1. Recurring patterns in node properties
2. Common connection structures
3. Temporal patterns (if timestamps exist)
4. Anomalies or outliers
5. Potential correlations between properties`
                }
            ],
            
            discovery: [
                {
                    name: 'Suggest Connections',
                    icon: '💡',
                    description: 'Find potential missing relationships',
                    template: `Suggest potential new connections in this knowledge graph.

**Current graph:**
- {nodeCount} nodes
- {edgeCount} edges

**Sample nodes:**
{nodeSample}

Based on the content and properties of nodes, suggest:
1. Missing relationships that should logically exist
2. Implicit connections based on shared properties
3. Relationships that would add value
4. Nodes that should be connected but aren't

For each suggestion, explain the reasoning.`
                },
                {
                    name: 'Identify Gaps',
                    icon: '🕳️',
                    description: 'Find missing information or entities',
                    template: `Identify gaps and missing information in this knowledge graph.

**Current coverage:**
{nodeSample}

Please identify:
1. Important entities that appear to be missing
2. Underrepresented topics or areas
3. Nodes with incomplete information
4. Relationships that seem absent
5. Suggestions for what to add to make the graph more complete`
                },
                {
                    name: 'Recommend Expansions',
                    icon: '🌱',
                    description: 'Suggest how to grow the graph',
                    template: `Recommend ways to expand and enrich this knowledge graph.

**Current state:**
- {nodeCount} nodes covering: {nodeTypes}
- {edgeCount} relationships

**Sample content:**
{nodeSample}

Recommend:
1. New node types to add
2. Additional relationship types
3. Properties to add to existing nodes
4. Related domains to explore
5. Specific entities that would be valuable additions

Prioritize recommendations by potential value.`
                },
                {
                    name: 'Generate Questions',
                    icon: '❓',
                    description: 'Create questions that the graph could answer',
                    template: `Generate interesting questions that this knowledge graph could help answer.

**Graph content:**
{nodeSample}

**Relationships:**
{edgeSample}

Generate:
1. Questions the graph can currently answer
2. Questions it's close to answering (with minor additions)
3. Questions it should be able to answer but can't yet
4. Surprising or non-obvious questions to explore
5. Research questions this graph could inform

Make questions specific and actionable.`
                }
            ],
            
            quality: [
                {
                    name: 'Check Data Quality',
                    icon: '✅',
                    description: 'Assess graph data quality',
                    template: `Assess the data quality of this knowledge graph.

**Graph data:**
{nodeSample}

Evaluate:
1. Completeness: Are nodes fully described?
2. Consistency: Are naming and properties consistent?
3. Accuracy: Do relationships make sense?
4. Redundancy: Are there duplicate or near-duplicate nodes?
5. Standards: Is there a clear schema or structure?

Provide specific examples of quality issues found.`
                },
                {
                    name: 'Suggest Cleanup',
                    icon: '🧹',
                    description: 'Identify cleanup and maintenance tasks',
                    template: `Suggest cleanup and maintenance tasks for this knowledge graph.

**Current state:**
- {nodeCount} nodes
- {edgeCount} edges

**Sample data:**
{nodeSample}

Suggest:
1. Nodes that could be merged or deduplicated
2. Inconsistent naming or formatting to fix
3. Properties that should be standardized
4. Orphaned or disconnected nodes to review
5. Relationships that should be verified or updated`
                },
                {
                    name: 'Validate Structure',
                    icon: '🔬',
                    description: 'Check if graph structure makes sense',
                    template: `Validate the structure and organization of this knowledge graph.

**Structure:**
{nodeSample}

**Relationships:**
{edgeSample}

Check:
1. Do node types make sense for the domain?
2. Are relationships logical and well-defined?
3. Is the hierarchy (if any) appropriate?
4. Are there structural antipatterns?
5. Does the structure support the intended use cases?

Provide recommendations for structural improvements.`
                }
            ],
            
            custom: [
                {
                    name: 'Custom Analysis',
                    icon: '🎯',
                    description: 'Ask your own question about the graph',
                    template: `{customQuery}

**Graph context:**
- {nodeCount} nodes
- {edgeCount} edges

**Sample data:**
{nodeSample}

Please analyze and respond to the query above.`
                }
            ]
        },
        
        /**
         * Tool orchestration templates
         */
        orchestrationTemplates: [
            {
                name: 'Auto-Analyze with Tools',
                icon: '🤖',
                description: 'Let AI choose and run the best tools for analysis',
                template: `I need you to analyze this knowledge graph using the available tools. Choose the most appropriate tools and execute them to provide comprehensive insights.

**Graph Overview:**
- {nodeCount} nodes
- {edgeCount} edges
- Node types: {nodeTypes}

**Available Tools:**
{toolsList}

**Your task:**
1. Review the graph data
2. Determine which tools would provide the most value
3. Execute those tools in the optimal order
4. Synthesize the results into actionable insights

**Sample data:**
{nodeSample}

Please proceed with your analysis.`
            },
            {
                name: 'Multi-Tool Research',
                icon: '🔬',
                description: 'Run multiple tools for deep analysis',
                template: `Perform a comprehensive multi-tool research analysis on this knowledge graph.

**Research Goal:** {researchGoal}

**Graph Data:**
- {nodeCount} nodes
- {edgeCount} edges

**Available Tools:**
{toolsList}

**Instructions:**
1. Use multiple tools to gather different perspectives
2. Execute tools that complement each other
3. Look for patterns across tool results
4. Synthesize findings into a coherent analysis
5. Highlight surprising or counterintuitive discoveries

Proceed with your research.`
            },
            {
                name: 'Tool Recommendation',
                icon: '💭',
                description: 'Ask AI which tools to use for a specific task',
                template: `I want to: {userGoal}

**Available Tools:**
{toolsList}

**Graph Context:**
- {nodeCount} nodes of types: {nodeTypes}
- {edgeCount} relationships

Which tools should I use to accomplish this goal? Please:
1. Recommend specific tools and explain why
2. Suggest the order of execution
3. Explain what each tool will contribute
4. Note any tool combinations that work well together
5. Warn about any limitations or prerequisites

Don't execute yet - just provide recommendations.`
            },
            {
                name: 'Guided Tool Workflow',
                icon: '📋',
                description: 'Step-by-step tool execution with AI guidance',
                template: `Guide me through a tool-based workflow to: {workflowGoal}

**Current Graph:**
- {nodeCount} nodes
- {edgeCount} edges

**Available Tools:**
{toolsList}

Please:
1. Suggest the first tool to run and why
2. After I run it, analyze the results
3. Recommend the next tool based on what we learned
4. Continue iteratively until we achieve the goal
5. Summarize findings at each step

Let's start - what's the first tool I should run?`
            },
            {
                name: 'Comparative Tool Analysis',
                icon: '⚖️',
                description: 'Run tools and compare their insights',
                template: `Run multiple analysis tools and compare their insights on this graph.

**Graph:**
{nodeSample}

**Tools to compare:**
{selectedTools}

For each tool:
1. Execute it on the graph data
2. Summarize its key findings
3. Note its unique insights

Then compare:
- Where do tools agree?
- Where do they differ?
- Which tool provided the most value?
- What do we learn from combining them?

Proceed with the analysis.`
            }
        ],
        
        /**
         * Initialize module
         */
        init: function() {
            console.log('GraphAIAssistant initialized');
            console.log('  Prompt templates:', Object.values(this.promptTemplates).flat().length);
            console.log('  Orchestration templates:', this.orchestrationTemplates.length);
        },
        
        /**
         * Show main AI assistant menu - RENDERS IN INFO CARD
         */
        showAssistantMenu: function() {
            if (!window.GraphInfoCard) {
                alert('GraphInfoCard not available');
                return;
            }
            
            window.GraphInfoCard.inlineMode = true;
            window.GraphInfoCard.isExpanded = true;
            
            const content = `
                <div style="color: #94a3b8; font-size: 13px; margin-bottom: 16px; line-height: 1.5;">
                    Interact with your graph using AI prompts and tool orchestration
                </div>
                
                <!-- Assistant Options -->
                <div style="display: flex; flex-direction: column; gap: 10px;">
                    
                    <button onclick="window.GraphAIAssistant.showPromptCategory('analysis')" 
                        style="padding: 14px; background: #1e293b; color: #e2e8f0; border: 1px solid #334155; border-radius: 8px; cursor: pointer; text-align: left; transition: all 0.15s;"
                        onmouseover="this.style.background='#334155'; this.style.borderColor='#475569'; this.style.transform='translateX(4px)'" 
                        onmouseout="this.style.background='#1e293b'; this.style.borderColor='#334155'; this.style.transform='translateX(0)'">
                        <div style="font-size: 20px; margin-bottom: 6px;">📊</div>
                        <div style="font-weight: 600; font-size: 14px; margin-bottom: 3px;">Graph Analysis</div>
                        <div style="font-size: 11px; color: #94a3b8;">Summarize, analyze patterns, find key nodes</div>
                    </button>
                    
                    <button onclick="window.GraphAIAssistant.showPromptCategory('discovery')" 
                        style="padding: 14px; background: #1e293b; color: #e2e8f0; border: 1px solid #334155; border-radius: 8px; cursor: pointer; text-align: left; transition: all 0.15s;"
                        onmouseover="this.style.background='#334155'; this.style.borderColor='#475569'; this.style.transform='translateX(4px)'" 
                        onmouseout="this.style.background='#1e293b'; this.style.borderColor='#334155'; this.style.transform='translateX(0)'">
                        <div style="font-size: 20px; margin-bottom: 6px;">💡</div>
                        <div style="font-weight: 600; font-size: 14px; margin-bottom: 3px;">Discovery & Insights</div>
                        <div style="font-size: 11px; color: #94a3b8;">Suggest connections, identify gaps, expand graph</div>
                    </button>
                    
                    <button onclick="window.GraphAIAssistant.showPromptCategory('quality')" 
                        style="padding: 14px; background: #1e293b; color: #e2e8f0; border: 1px solid #334155; border-radius: 8px; cursor: pointer; text-align: left; transition: all 0.15s;"
                        onmouseover="this.style.background='#334155'; this.style.borderColor='#475569'; this.style.transform='translateX(4px)'" 
                        onmouseout="this.style.background='#1e293b'; this.style.borderColor='#334155'; this.style.transform='translateX(0)'">
                        <div style="font-size: 20px; margin-bottom: 6px;">✅</div>
                        <div style="font-weight: 600; font-size: 14px; margin-bottom: 3px;">Quality & Maintenance</div>
                        <div style="font-size: 11px; color: #94a3b8;">Check quality, cleanup, validate structure</div>
                    </button>
                    
                    <button onclick="window.GraphAIAssistant.showToolOrchestration()" 
                        style="padding: 14px; background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); color: white; border: none; border-radius: 8px; cursor: pointer; text-align: left; transition: all 0.15s;"
                        onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 4px 12px rgba(59, 130, 246, 0.4)'" 
                        onmouseout="this.style.transform=''; this.style.boxShadow=''">
                        <div style="font-size: 20px; margin-bottom: 6px;">🤖</div>
                        <div style="font-weight: 600; font-size: 14px; margin-bottom: 3px;">AI Tool Orchestration</div>
                        <div style="font-size: 11px; opacity: 0.95;">Let AI choose and run tools automatically</div>
                    </button>
                    
                    <button onclick="window.GraphAIAssistant.showCustomPrompt()" 
                        style="padding: 14px; background: #1e293b; color: #e2e8f0; border: 1px solid #334155; border-radius: 8px; cursor: pointer; text-align: left; transition: all 0.15s;"
                        onmouseover="this.style.background='#334155'; this.style.borderColor='#475569'; this.style.transform='translateX(4px)'" 
                        onmouseout="this.style.background='#1e293b'; this.style.borderColor='#334155'; this.style.transform='translateX(0)'">
                        <div style="font-size: 20px; margin-bottom: 6px;">🎯</div>
                        <div style="font-weight: 600; font-size: 14px; margin-bottom: 3px;">Custom Query</div>
                        <div style="font-size: 11px; color: #94a3b8;">Ask your own question about the graph</div>
                    </button>
                </div>
            `;
            
            window.GraphInfoCard.showInlineContent(
                '🤖 AI Graph Assistant',
                content,
                'window.GraphInfoCard.collapse()'
            );
        },
        
        /**
         * Show prompts for a category - RENDERS IN INFO CARD
         */
        showPromptCategory: function(category) {
            if (!window.GraphInfoCard) {
                alert('GraphInfoCard not available');
                return;
            }
            
            const prompts = this.promptTemplates[category] || [];
            const categoryNames = {
                analysis: 'Graph Analysis',
                discovery: 'Discovery & Insights',
                quality: 'Quality & Maintenance',
                custom: 'Custom Query'
            };
            
            window.GraphInfoCard.inlineMode = true;
            window.GraphInfoCard.isExpanded = true;
            
            const content = `
                <div style="color: #94a3b8; font-size: 13px; margin-bottom: 16px;">
                    Select a prompt template to use
                </div>
                
                <!-- Prompt Templates -->
                <div style="display: flex; flex-direction: column; gap: 8px; max-height: 450px; overflow-y: auto;">
                    ${prompts.map((prompt, idx) => `
                        <div class="prompt-template" 
                            onclick="window.GraphAIAssistant.executePromptTemplate('${category}', ${idx})"
                            style="padding: 12px; background: #1e293b; border: 1px solid #334155; border-radius: 8px; cursor: pointer; transition: all 0.15s;"
                            onmouseover="this.style.background='#334155'; this.style.borderColor='#475569'; this.style.transform='translateX(4px)'" 
                            onmouseout="this.style.background='#1e293b'; this.style.borderColor='#334155'; this.style.transform='translateX(0)'">
                            <div style="display: flex; align-items: start; gap: 12px;">
                                <div style="font-size: 24px; flex-shrink: 0;">${prompt.icon}</div>
                                <div style="flex: 1; min-width: 0;">
                                    <div style="font-weight: 600; color: #e2e8f0; margin-bottom: 4px; font-size: 13px;">
                                        ${this.escapeHtml(prompt.name)}
                                    </div>
                                    <div style="font-size: 11px; color: #94a3b8; line-height: 1.4;">
                                        ${this.escapeHtml(prompt.description)}
                                    </div>
                                </div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
            
            window.GraphInfoCard.showInlineContent(
                categoryNames[category] || category,
                content,
                'window.GraphAIAssistant.showAssistantMenu()'
            );
        },
        
        /**
         * Show tool orchestration menu - RENDERS IN INFO CARD
         */
        showToolOrchestration: function() {
            if (!window.GraphInfoCard) {
                alert('GraphInfoCard not available');
                return;
            }
            
            window.GraphInfoCard.inlineMode = true;
            window.GraphInfoCard.isExpanded = true;
            
            const content = `
                <div style="color: #94a3b8; font-size: 13px; margin-bottom: 16px;">
                    Let AI decide which tools to use and execute them
                </div>
                
                <!-- Orchestration Templates -->
                <div style="display: flex; flex-direction: column; gap: 8px;">
                    ${this.orchestrationTemplates.map((template, idx) => `
                        <div class="orchestration-template" 
                            onclick="window.GraphAIAssistant.executeOrchestrationTemplate(${idx})"
                            style="padding: 14px; background: #1e293b; border: 1px solid #334155; border-radius: 8px; cursor: pointer; transition: all 0.15s;"
                            onmouseover="this.style.background='#334155'; this.style.borderColor='#475569'; this.style.transform='translateX(4px)'" 
                            onmouseout="this.style.background='#1e293b'; this.style.borderColor='#334155'; this.style.transform='translateX(0)'">
                            <div style="display: flex; align-items: start; gap: 12px;">
                                <div style="font-size: 24px; flex-shrink: 0;">${template.icon}</div>
                                <div style="flex: 1; min-width: 0;">
                                    <div style="font-weight: 600; color: #e2e8f0; margin-bottom: 4px; font-size: 14px;">
                                        ${this.escapeHtml(template.name)}
                                    </div>
                                    <div style="font-size: 11px; color: #94a3b8; line-height: 1.4;">
                                        ${this.escapeHtml(template.description)}
                                    </div>
                                </div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
            
            window.GraphInfoCard.showInlineContent(
                '🤖 AI Tool Orchestration',
                content,
                'window.GraphAIAssistant.showAssistantMenu()'
            );
        },
        
        /**
         * Show custom prompt input - RENDERS IN INFO CARD
         */
        showCustomPrompt: function() {
            if (!window.GraphInfoCard) {
                alert('GraphInfoCard not available');
                return;
            }
            
            window.GraphInfoCard.inlineMode = true;
            window.GraphInfoCard.isExpanded = true;
            
            const content = `
                <div style="color: #94a3b8; font-size: 13px; margin-bottom: 16px;">
                    Ask your own question about the graph
                </div>
                
                <div style="margin-bottom: 16px;">
                    <label style="display: block; color: #94a3b8; font-size: 13px; font-weight: 600; margin-bottom: 8px;">Your Question</label>
                    <textarea id="custom-prompt-input" 
                        placeholder="What would you like to know about this graph?"
                        rows="6"
                        style="width: 100%; padding: 12px; background: #1e293b; color: #e2e8f0; border: 1px solid #334155; border-radius: 8px; resize: vertical; font-family: inherit; font-size: 13px; line-height: 1.5;"
                    ></textarea>
                </div>
                
                <div style="margin-bottom: 20px;">
                    <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; padding: 10px; background: #1e293b; border-radius: 6px; border: 1px solid #334155;">
                        <input type="checkbox" id="include-graph-context" checked style="width: 16px; height: 16px;">
                        <span style="color: #e2e8f0; font-size: 13px;">Include graph data in context</span>
                    </label>
                </div>
                
                <div style="display: flex; gap: 8px;">
                    <button onclick="window.GraphAIAssistant.executeCustomPrompt()" style="
                        flex: 1; padding: 12px;
                        background: #3b82f6; color: white; border: none;
                        border-radius: 8px; cursor: pointer; font-weight: 600; font-size: 14px;
                    ">Ask AI</button>
                    <button onclick="window.GraphAIAssistant.showAssistantMenu()" style="
                        padding: 12px 24px;
                        background: #334155; color: #e2e8f0; border: 1px solid #475569;
                        border-radius: 8px; cursor: pointer; font-weight: 600; font-size: 14px;
                    ">Back</button>
                </div>
            `;
            
            window.GraphInfoCard.showInlineContent(
                '🎯 Custom Query',
                content,
                'window.GraphAIAssistant.showAssistantMenu()'
            );
            
            setTimeout(() => {
                const input = document.getElementById('custom-prompt-input');
                if (input) input.focus();
            }, 150);
        },
        
        /**
         * Execute a prompt template
         */
        executePromptTemplate: function(category, index) {
            const template = this.promptTemplates[category][index];
            if (!template) return;
            
            const prompt = this.buildPromptFromTemplate(template.template);
            this.sendToChat(prompt);
        },
        
        /**
         * Execute orchestration template
         */
        executeOrchestrationTemplate: function(index) {
            const template = this.orchestrationTemplates[index];
            if (!template) return;
            
            // Check if template needs additional input
            if (template.template.includes('{researchGoal}') || 
                template.template.includes('{userGoal}') ||
                template.template.includes('{workflowGoal}')) {
                this.showOrchestrationInput(template, index);
            } else {
                const prompt = this.buildPromptFromTemplate(template.template);
                this.sendToChat(prompt);
            }
        },
        
        /**
         * Show orchestration input dialog - RENDERS IN INFO CARD
         */
        showOrchestrationInput: function(template, index) {
            if (!window.GraphInfoCard) {
                alert('GraphInfoCard not available');
                return;
            }
            
            window.GraphInfoCard.inlineMode = true;
            window.GraphInfoCard.isExpanded = true;
            
            const placeholders = {
                '{researchGoal}': 'What do you want to research?',
                '{userGoal}': 'What do you want to accomplish?',
                '{workflowGoal}': 'What is your workflow goal?'
            };
            
            const neededInput = Object.keys(placeholders).find(p => template.template.includes(p));
            const placeholder = placeholders[neededInput] || 'Enter your goal';
            
            const content = `
                <div style="color: #94a3b8; font-size: 13px; margin-bottom: 16px; line-height: 1.5;">
                    ${this.escapeHtml(template.description)}
                </div>
                
                <div style="margin-bottom: 16px;">
                    <label style="display: block; color: #94a3b8; font-size: 13px; font-weight: 600; margin-bottom: 8px;">
                        ${placeholder}
                    </label>
                    <textarea id="orchestration-input" 
                        placeholder="${placeholder}"
                        rows="4"
                        style="width: 100%; padding: 12px; background: #1e293b; color: #e2e8f0; border: 1px solid #334155; border-radius: 8px; resize: vertical; font-family: inherit; font-size: 13px; line-height: 1.5;"
                    ></textarea>
                </div>
                
                <div style="display: flex; gap: 8px;">
                    <button onclick="window.GraphAIAssistant.executeOrchestrationWithInput(${index}, '${neededInput}')" style="
                        flex: 1; padding: 12px;
                        background: #3b82f6; color: white; border: none;
                        border-radius: 8px; cursor: pointer; font-weight: 600; font-size: 14px;
                    ">Execute</button>
                    <button onclick="window.GraphAIAssistant.showToolOrchestration()" style="
                        padding: 12px 24px;
                        background: #334155; color: #e2e8f0; border: 1px solid #475569;
                        border-radius: 8px; cursor: pointer; font-weight: 600; font-size: 14px;
                    ">Back</button>
                </div>
            `;
            
            window.GraphInfoCard.showInlineContent(
                `${template.icon} ${this.escapeHtml(template.name)}`,
                content,
                'window.GraphAIAssistant.showToolOrchestration()'
            );
            
            setTimeout(() => {
                const input = document.getElementById('orchestration-input');
                if (input) input.focus();
            }, 150);
        },
        
        /**
         * Execute orchestration with user input
         */
        executeOrchestrationWithInput: function(index, placeholder) {
            const input = document.getElementById('orchestration-input');
            if (!input) return;
            
            const value = input.value.trim();
            if (!value) {
                alert('Please enter a value');
                return;
            }
            
            const template = this.orchestrationTemplates[index];
            if (!template) return;
            
            let promptTemplate = template.template.replace(placeholder, value);
            const prompt = this.buildPromptFromTemplate(promptTemplate);
            this.sendToChat(prompt);
        },
        
        /**
         * Execute custom prompt
         */
        executeCustomPrompt: function() {
            const queryInput = document.getElementById('custom-prompt-input');
            const contextCheckbox = document.getElementById('include-graph-context');
            
            if (!queryInput) return;
            
            const query = queryInput.value.trim();
            const includeContext = contextCheckbox ? contextCheckbox.checked : true;
            
            if (!query) {
                alert('Please enter a question');
                return;
            }
            
            let prompt = query;
            
            if (includeContext) {
                const template = this.promptTemplates.custom[0];
                prompt = this.buildPromptFromTemplate(template.template.replace('{customQuery}', query));
            }
            
            this.sendToChat(prompt);
        },
        
        /**
         * Build prompt from template with graph data
         */
        buildPromptFromTemplate: function(template) {
            const graphData = this.getGraphData();
            
            let prompt = template;
            
            // Replace placeholders
            prompt = prompt.replace(/{nodeCount}/g, graphData.nodeCount);
            prompt = prompt.replace(/{edgeCount}/g, graphData.edgeCount);
            prompt = prompt.replace(/{nodeTypes}/g, graphData.nodeTypes.join(', '));
            prompt = prompt.replace(/{edgeTypes}/g, graphData.edgeTypes.join(', '));
            prompt = prompt.replace(/{nodeSample}/g, graphData.nodeSample);
            prompt = prompt.replace(/{edgeSample}/g, graphData.edgeSample);
            prompt = prompt.replace(/{toolsList}/g, graphData.toolsList);
            prompt = prompt.replace(/{selectedTools}/g, graphData.selectedTools || 'All available tools');
            
            return prompt;
        },
        
        /**
         * Get graph data for prompts
         */
        getGraphData: function() {
            const nodes = network.body.data.nodes.get();
            const edges = network.body.data.edges.get();
            
            // Get node types
            const nodeTypes = [...new Set(nodes.map(n => n.type || n.label || 'Unknown'))];
            
            // Get edge types
            const edgeTypes = [...new Set(edges.map(e => e.label || 'CONNECTED'))];
            
            // Sample nodes (up to 10)
            const sampleNodes = nodes.slice(0, 10).map(n => {
                const props = n.properties || {};
                const propsStr = Object.entries(props).slice(0, 3)
                    .map(([k, v]) => `${k}: ${String(v).substring(0, 50)}`)
                    .join(', ');
                return `- ${n.label || n.id}${propsStr ? ` (${propsStr})` : ''}`;
            }).join('\n');
            
            // Sample edges (up to 10)
            const sampleEdges = edges.slice(0, 10).map(e => {
                const fromNode = nodes.find(n => n.id === e.from);
                const toNode = nodes.find(n => n.id === e.to);
                return `- ${fromNode?.label || e.from} ${e.label || '→'} ${toNode?.label || e.to}`;
            }).join('\n');
            
            // Get tools list from GraphCanvasMenu if available
            const tools = window.GraphCanvasMenu?.availableTools || [];
            const toolsList = tools.map(t => `- ${t.name}: ${t.description || 'No description'}`).join('\n');
            
            return {
                nodeCount: nodes.length,
                edgeCount: edges.length,
                nodeTypes,
                edgeTypes,
                nodeSample: sampleNodes || 'No nodes available',
                edgeSample: sampleEdges || 'No edges available',
                toolsList: toolsList || 'No tools available'
            };
        },
        
        /**
         * Send prompt to chat
         */
        sendToChat: function(prompt, autoSend = false) {
            // Close the info card
            if (window.GraphInfoCard) {
                window.GraphInfoCard.collapse();
            }
            
            const chatInput = document.getElementById('messageInput');
            if (chatInput) {
                chatInput.value = prompt;
                chatInput.focus();
                
                const chatSection = document.getElementById('chatMessages');
                if (chatSection) {
                    chatSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                }
                
                if (autoSend) {
                    const sendButton = document.querySelector('#chat-section button[type="submit"]');
                    if (sendButton) {
                        setTimeout(() => sendButton.click(), 100);
                    }
                }
                
                this.showToast('Prompt ready - review and send');
            } else {
                console.warn('Chat input not found');
                alert('Chat interface not found. Here is your prompt:\n\n' + prompt);
            }
        },
        
        /**
         * Show toast notification
         */
        showToast: function(message) {
            document.querySelectorAll('.ai-assistant-toast').forEach(t => t.remove());
            
            const toast = document.createElement('div');
            toast.className = 'ai-assistant-toast';
            toast.textContent = message;
            toast.style.cssText = `
                position: fixed; top: 20px; right: 20px; z-index: 10000;
                background: #1e293b; color: #e2e8f0; padding: 12px 20px;
                border-radius: 6px; border: 1px solid #334155;
                box-shadow: 0 4px 12px rgba(0,0,0,0.3);
                transition: opacity 0.3s;
            `;
            document.body.appendChild(toast);
            
            setTimeout(() => {
                toast.style.opacity = '0';
                setTimeout(() => toast.remove(), 300);
            }, 2000);
        },
        
        /**
         * Escape HTML
         */
        escapeHtml: function(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
    };
    
    // Initialize on load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => window.GraphAIAssistant.init());
    } else {
        window.GraphAIAssistant.init();
    }
    
})();