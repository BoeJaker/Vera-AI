(() => {
// =====================================================================
// Enhanced Canvas Integration for VeraChat
// Features: Monaco Editor, ESP32 Simulator, Multi-Parser, Zoom/Pan
// =====================================================================

VeraChat.prototype.initCanvasTab = function () {
    const root = document.querySelector('#tab-canvas');
    if (!root) {
        console.warn('Canvas tab container not found');
        return;
    }

    root.innerHTML = '';

    // Main container
    const container = document.createElement('div');
    container.style.cssText = `
        display: flex;
        flex-direction: column;
        height: 100%;
        overflow: hidden;
        color: #e2e8f0;
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
    `;

    // Header with mode selector
    const header = document.createElement('div');
    header.style.cssText = `
        padding: 12px 16px;
        border-bottom: 1px solid #334155;
        display: flex;
        align-items: center;
        gap: 12px;
        flex-shrink: 0;
    `;
    header.innerHTML = `
        <h2>Canvas</h2>
        <select id="canvasMode" class="panel-btn" style="padding: 6px 12px;">
            <option value="code">Code Editor (Monaco)</option>
            <option value="execute">Code Execution (Multi-Language)</option>
            <option value="embedded-ide">Embedded IDE + Simulator</option>
            <option value="tic80">TIC-80 Fantasy Console</option>
            <option value="markdown">Markdown</option>
            <option value="jupyter">Jupyter Notebook</option>
            <option value="terminal">Terminal</option>
            <option value="preview">HTML/JS Preview</option>
            <option value="json">JSON Viewer</option>
            <option value="diagram">Diagram (Mermaid)</option>
            <option value="table">Data Table</option>
            <option value="diff">Diff Viewer</option>
        </select>
        <div id="instanceSelector" style="display: none; gap: 8px; align-items: center;">
            <span style="font-size: 13px; color: #94a3b8;">Instance:</span>
            <select id="instanceList" class="panel-btn" style="padding: 6px 12px;"></select>
            <span id="instanceCount" style="font-size: 13px; color: #94a3b8;"></span>
        </div>
        <button id="parseContent" class="panel-btn" style="display: none;">🔍 Parse All</button>
        <button id="clearCanvas" class="panel-btn" style="margin-left: auto;">🧹 Clear</button>
        <button id="fullscreenCanvas" class="panel-btn">⛶ Fullscreen</button>
    `;
    container.appendChild(header);

    // Content area
    const content = document.createElement('div');
    content.id = 'canvas-content';
    content.style.cssText = `
        flex: 1;
        overflow: auto;
        padding: 16px;
        position: relative;
    `;
    container.appendChild(content);

    // Control bar (mode-specific)
    const controls = document.createElement('div');
    controls.id = 'canvas-controls';
    controls.style.cssText = `
        padding: 12px 16px;
        border-top: 1px solid #334155;
        display: flex;
        gap: 8px;
        flex-shrink: 0;
        flex-wrap: wrap;
    `;
    container.appendChild(controls);

    root.appendChild(container);

    // Store references and persistent content
    this.canvas = {
        root: container,
        content,
        controls,
        mode: 'code',
        data: null,
        persistentContent: '', // Stores content across mode switches
        instances: [], // Stores parsed instances
        currentInstanceIndex: 0,
        monacoEditor: null
    };

    // Set up mode switching
    const modeSelector = header.querySelector('#canvasMode');
    modeSelector.addEventListener('change', (e) => {
        this.switchCanvasMode(e.target.value);
    });

    header.querySelector('#clearCanvas').addEventListener('click', () => {
        this.clearCanvas();
    });

    header.querySelector('#fullscreenCanvas').addEventListener('click', () => {
        this.toggleCanvasFullscreen();
    });

    header.querySelector('#parseContent').addEventListener('click', () => {
        this.parseAllInstances();
    });

    const instanceList = header.querySelector('#instanceList');
    instanceList.addEventListener('change', (e) => {
        this.switchToInstance(parseInt(e.target.value));
    });

    // Load Monaco if not already loaded
    this.loadMonaco();

    // Initialize with code editor mode
    this.switchCanvasMode('code');
};

// =====================================================================
// Monaco Editor Loader
// =====================================================================

VeraChat.prototype.loadMonaco = function() {
    if (window.monaco) return Promise.resolve();
    if (this._monacoLoading) return this._monacoLoading;

    this._monacoLoading = new Promise((resolve) => {
        const script = document.createElement('script');
        script.src = 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.45.0/min/vs/loader.min.js';
        script.onload = () => {
            require.config({ paths: { vs: 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.45.0/min/vs' }});
            require(['vs/editor/editor.main'], () => {
                this.registerMonacoLanguages();
                resolve();
            });
        };
        document.head.appendChild(script);
    });

    return this._monacoLoading;
};

VeraChat.prototype.registerMonacoLanguages = function() {
    // Register Arduino language
    monaco.languages.register({ id: 'arduino' });
    monaco.languages.setMonarchTokensProvider('arduino', {
        keywords: ['void','int','float','double','char','long','bool','pinMode','digitalWrite',
                   'digitalRead','analogRead','analogWrite','delay','HIGH','LOW','INPUT','OUTPUT',
                   'Serial','println','print','setup','loop'],
        tokenizer: {
            root: [
                [/[a-zA-Z_]\w*/, { cases: { '@keywords': 'keyword', '@default': 'identifier' } }],
                [/\d+/, 'number'],
                [/\/\/.*$/, 'comment'],
                [/\/\*/, 'comment', '@comment'],
                [/".*?"/, 'string']
            ],
            comment: [
                [/[^\/*]+/, 'comment'],
                [/\*\//, 'comment', '@pop'],
                [/[\/*]/, 'comment']
            ]
        }
    });

    // Add completions
    monaco.languages.registerCompletionItemProvider('arduino', {
        provideCompletionItems: () => {
            const suggestions = [
                { label: 'setup()', kind: monaco.languages.CompletionItemKind.Snippet, 
                  insertText: 'void setup() {\n\t$0\n}', documentation: 'Arduino setup()' },
                { label: 'loop()', kind: monaco.languages.CompletionItemKind.Snippet, 
                  insertText: 'void loop() {\n\t$0\n}', documentation: 'Arduino loop()' },
                { label:'pinMode', kind: monaco.languages.CompletionItemKind.Function, 
                  insertText:'pinMode(${1:pin}, ${2:OUTPUT});' },
                { label:'digitalWrite', kind: monaco.languages.CompletionItemKind.Function, 
                  insertText:'digitalWrite(${1:pin}, ${2:HIGH});' },
                { label:'delay', kind: monaco.languages.CompletionItemKind.Function, 
                  insertText:'delay(${1:1000});' },
            ];
            return { suggestions };
        }
    });
};

// =====================================================================
// Mode Switching with Content Persistence
// =====================================================================

VeraChat.prototype.switchCanvasMode = function(mode) {
    if (!this.canvas) this.initCanvasTab();
    
    // Save current content before switching
    this.saveCurrentContent();
    
    this.canvas.mode = mode;
    this.clearCanvas();
    
    switch(mode) {
        case 'code':
            this.initMonacoEditor();
            break;
        case 'execute':
            this.initCodeExecution();
            break;
        case 'embedded-ide':
            this.initEmbeddedIDE();
            break;
        case 'tic80':
            this.initTIC80();
            break;
        case 'markdown':
            this.initMarkdownViewer();
            break;
        case 'jupyter':
            this.initJupyterViewer();
            break;
        case 'terminal':
            this.initTerminal();
            break;
        case 'preview':
            this.initHTMLPreview();
            break;
        case 'json':
            this.initJSONViewer();
            break;
        case 'diagram':
            this.initDiagramViewer();
            break;
        case 'table':
            this.initTableViewer();
            break;
        case 'diff':
            this.initDiffViewer();
            break;
    }
    
    // Restore content after mode switch
    this.restoreContent();
};

VeraChat.prototype.saveCurrentContent = function() {
    if (!this.canvas) return;
    
    const mode = this.canvas.mode;
    let content = '';
    
    switch(mode) {
        case 'code':
            if (this.canvas.monacoEditor) {
                content = this.canvas.monacoEditor.getValue();
            }
            break;
        case 'execute':
            const execEditor = document.querySelector('#exec-monaco-container');
            if (execEditor && execEditor.monacoInstance) {
                content = execEditor.monacoInstance.getValue();
            }
            break;
        case 'embedded-ide':
            const ideEditor = document.querySelector('#ide-monaco-container');
            if (ideEditor && ideEditor.monacoInstance) {
                content = ideEditor.monacoInstance.getValue();
            }
            break;
        case 'tic80':
            const tic80Editor = document.querySelector('#tic80-monaco-container');
            if (tic80Editor && tic80Editor.monacoInstance) {
                content = tic80Editor.monacoInstance.getValue();
            }
            break;
        case 'markdown':
            const mdEditor = document.querySelector('#md-editor');
            if (mdEditor) content = mdEditor.value;
            break;
        case 'preview':
            const htmlEditor = document.querySelector('#html-editor');
            if (htmlEditor) content = htmlEditor.value;
            break;
        case 'json':
            const jsonEditor = document.querySelector('#json-editor');
            if (jsonEditor) content = jsonEditor.value;
            break;
        case 'diagram':
            const mermaidEditor = document.querySelector('#mermaid-editor');
            if (mermaidEditor) content = mermaidEditor.value;
            break;
        case 'diff':
            const diffOrig = document.querySelector('#diff-original');
            const diffMod = document.querySelector('#diff-modified');
            if (diffOrig && diffMod) {
                content = JSON.stringify({ original: diffOrig.value, modified: diffMod.value });
            }
            break;
    }
    
    if (content) {
        this.canvas.persistentContent = content;
    }
};

VeraChat.prototype.restoreContent = function() {
    if (!this.canvas || !this.canvas.persistentContent) return;
    
    const mode = this.canvas.mode;
    const content = this.canvas.persistentContent;
    
    // Small delay to ensure DOM is ready
    setTimeout(() => {
        switch(mode) {
            case 'code':
                if (this.canvas.monacoEditor) {
                    this.canvas.monacoEditor.setValue(content);
                }
                break;
            case 'execute':
                const execEditor = document.querySelector('#exec-monaco-container');
                if (execEditor && execEditor.monacoInstance) {
                    execEditor.monacoInstance.setValue(content);
                }
                break;
            case 'embedded-ide':
                const ideEditor = document.querySelector('#ide-monaco-container');
                if (ideEditor && ideEditor.monacoInstance) {
                    ideEditor.monacoInstance.setValue(content);
                }
                break;
            case 'tic80':
                const tic80Editor = document.querySelector('#tic80-monaco-container');
                if (tic80Editor && tic80Editor.monacoInstance) {
                    tic80Editor.monacoInstance.setValue(content);
                }
                break;
            case 'markdown':
                const mdEditor = document.querySelector('#md-editor');
                if (mdEditor) mdEditor.value = content;
                break;
            case 'preview':
                const htmlEditor = document.querySelector('#html-editor');
                if (htmlEditor) htmlEditor.value = content;
                break;
            case 'json':
                const jsonEditor = document.querySelector('#json-editor');
                if (jsonEditor) jsonEditor.value = content;
                break;
            case 'diagram':
                const mermaidEditor = document.querySelector('#mermaid-editor');
                if (mermaidEditor) mermaidEditor.value = content;
                break;
            case 'diff':
                try {
                    const data = JSON.parse(content);
                    const diffOrig = document.querySelector('#diff-original');
                    const diffMod = document.querySelector('#diff-modified');
                    if (diffOrig) diffOrig.value = data.original || '';
                    if (diffMod) diffMod.value = data.modified || '';
                } catch(e) {}
                break;
        }
    }, 100);
};

// =====================================================================
// Multi-Instance Parser
// =====================================================================

VeraChat.prototype.parseAllInstances = function() {
    const content = this.canvas.persistentContent;
    if (!content) return;
    
    const mode = this.canvas.mode;
    let instances = [];
    
    switch(mode) {
        case 'code':
        case 'embedded-ide':
            // Parse code blocks by function definitions, classes, or sections
            instances = this.parseCodeInstances(content);
            break;
        case 'json':
            // Parse JSON arrays or multiple objects
            instances = this.parseJSONInstances(content);
            break;
        case 'diagram':
            // Parse multiple Mermaid diagrams
            instances = this.parseMermaidInstances(content);
            break;
        case 'markdown':
            // Parse by headers or code blocks
            instances = this.parseMarkdownInstances(content);
            break;
    }
    
    if (instances.length > 1) {
        this.canvas.instances = instances;
        this.canvas.currentInstanceIndex = 0;
        this.showInstanceSelector(instances);
        this.loadInstance(0);
    } else {
        this.hideInstanceSelector();
        console.log('Only one instance found or parsing not supported for this mode');
    }
};

VeraChat.prototype.parseCodeInstances = function(content) {
    const instances = [];
    
    // Try to parse by function definitions
    const functionRegex = /(?:function|void|int|float|async\s+function)\s+(\w+)\s*\([^)]*\)\s*\{/g;
    let match;
    let lastIndex = 0;
    
    while ((match = functionRegex.exec(content)) !== null) {
        const name = match[1];
        const start = match.index;
        
        // Find matching closing brace
        let braceCount = 1;
        let end = start + match[0].length;
        while (end < content.length && braceCount > 0) {
            if (content[end] === '{') braceCount++;
            if (content[end] === '}') braceCount--;
            end++;
        }
        
        instances.push({
            name: name,
            content: content.substring(start, end),
            type: 'function',
            start, end
        });
    }
    
    // If no functions found, try splitting by comments or empty lines
    if (instances.length === 0) {
        const sections = content.split(/\n\s*\/\/\s*={3,}.*?\n/);
        sections.forEach((section, i) => {
            if (section.trim()) {
                instances.push({
                    name: `Section ${i + 1}`,
                    content: section.trim(),
                    type: 'section'
                });
            }
        });
    }
    
    return instances.length > 0 ? instances : [{ name: 'All', content, type: 'full' }];
};

VeraChat.prototype.parseJSONInstances = function(content) {
    try {
        const parsed = JSON.parse(content);
        if (Array.isArray(parsed)) {
            return parsed.map((item, i) => ({
                name: `Item ${i + 1}`,
                content: JSON.stringify(item, null, 2),
                type: 'array-item',
                data: item
            }));
        } else if (typeof parsed === 'object') {
            // Try to split by top-level keys
            return Object.keys(parsed).map(key => ({
                name: key,
                content: JSON.stringify({ [key]: parsed[key] }, null, 2),
                type: 'object-key',
                data: parsed[key]
            }));
        }
    } catch(e) {
        // Try splitting by top-level { } blocks
        const blocks = [];
        let depth = 0;
        let start = -1;
        
        for (let i = 0; i < content.length; i++) {
            if (content[i] === '{') {
                if (depth === 0) start = i;
                depth++;
            } else if (content[i] === '}') {
                depth--;
                if (depth === 0 && start >= 0) {
                    blocks.push(content.substring(start, i + 1));
                    start = -1;
                }
            }
        }
        
        if (blocks.length > 1) {
            return blocks.map((block, i) => ({
                name: `Block ${i + 1}`,
                content: block,
                type: 'json-block'
            }));
        }
    }
    
    return [{ name: 'All', content, type: 'full' }];
};

VeraChat.prototype.parseMermaidInstances = function(content) {
    // Split by diagram type keywords
    const diagramRegex = /^(graph|sequenceDiagram|classDiagram|stateDiagram|erDiagram|journey|gantt|pie|flowchart)/gm;
    const matches = [];
    let match;
    
    while ((match = diagramRegex.exec(content)) !== null) {
        matches.push({ type: match[1], index: match.index });
    }
    
    if (matches.length > 1) {
        const instances = [];
        for (let i = 0; i < matches.length; i++) {
            const start = matches[i].index;
            const end = i < matches.length - 1 ? matches[i + 1].index : content.length;
            const diagramContent = content.substring(start, end).trim();
            
            instances.push({
                name: `${matches[i].type} ${i + 1}`,
                content: diagramContent,
                type: 'diagram'
            });
        }
        return instances;
    }
    
    return [{ name: 'Diagram', content, type: 'full' }];
};

VeraChat.prototype.parseMarkdownInstances = function(content) {
    // Split by H1 or H2 headers
    const sections = content.split(/^(#{1,2}\s+.+)$/gm);
    const instances = [];
    
    for (let i = 0; i < sections.length; i += 2) {
        if (sections[i + 1]) {
            const header = sections[i + 1].replace(/^#+\s+/, '');
            const body = sections[i + 2] || '';
            instances.push({
                name: header,
                content: sections[i + 1] + '\n' + body,
                type: 'section'
            });
        }
    }
    
    return instances.length > 0 ? instances : [{ name: 'All', content, type: 'full' }];
};

VeraChat.prototype.showInstanceSelector = function(instances) {
    const selector = document.querySelector('#instanceSelector');
    const list = document.querySelector('#instanceList');
    const count = document.querySelector('#instanceCount');
    const parseBtn = document.querySelector('#parseContent');
    
    if (selector && list && count) {
        selector.style.display = 'flex';
        parseBtn.style.display = 'inline-block';
        
        list.innerHTML = '';
        instances.forEach((inst, i) => {
            const option = document.createElement('option');
            option.value = i;
            option.textContent = inst.name;
            list.appendChild(option);
        });
        
        count.textContent = `(${instances.length} found)`;
    }
};

VeraChat.prototype.hideInstanceSelector = function() {
    const selector = document.querySelector('#instanceSelector');
    if (selector) selector.style.display = 'none';
};

VeraChat.prototype.switchToInstance = function(index) {
    if (!this.canvas.instances || index < 0 || index >= this.canvas.instances.length) return;
    
    this.canvas.currentInstanceIndex = index;
    this.loadInstance(index);
};

VeraChat.prototype.loadInstance = function(index) {
    const instance = this.canvas.instances[index];
    if (!instance) return;
    
    const mode = this.canvas.mode;
    
    switch(mode) {
        case 'code':
            if (this.canvas.monacoEditor) {
                this.canvas.monacoEditor.setValue(instance.content);
            }
            break;
        case 'embedded-ide':
            const ideEditor = document.querySelector('#ide-monaco-container');
            if (ideEditor && ideEditor.monacoInstance) {
                ideEditor.monacoInstance.setValue(instance.content);
            }
            break;
        case 'json':
            const jsonEditor = document.querySelector('#json-editor');
            if (jsonEditor) {
                jsonEditor.value = instance.content;
                const parseBtn = document.querySelector('#parseJson');
                if (parseBtn) parseBtn.click();
            }
            break;
        case 'diagram':
            const mermaidEditor = document.querySelector('#mermaid-editor');
            if (mermaidEditor) {
                mermaidEditor.value = instance.content;
                const renderBtn = document.querySelector('#renderDiagram');
                if (renderBtn) renderBtn.click();
            }
            break;
        case 'markdown':
            const mdEditor = document.querySelector('#md-editor');
            if (mdEditor) {
                mdEditor.value = instance.content;
                mdEditor.dispatchEvent(new Event('input'));
            }
            break;
    }
};

// =====================================================================
// Monaco Code Editor Mode
// =====================================================================

VeraChat.prototype.initMonacoEditor = function() {
    const { content, controls } = this.canvas;
    
    // Editor container
    const editorDiv = document.createElement('div');
    editorDiv.id = 'monaco-editor-container';
    editorDiv.style.cssText = `
        width: 100%;
        height: calc(100% - 20px);
        border: 1px solid #334155;
        border-radius: 6px;
        overflow: hidden;
    `;
    content.appendChild(editorDiv);

    // Controls
    controls.innerHTML = `
        <select id="monacoLang" class="panel-btn">
            <option value="javascript">JavaScript</option>
            <option value="python">Python</option>
            <option value="arduino">Arduino</option>
            <option value="html">HTML</option>
            <option value="css">CSS</option>
            <option value="json">JSON</option>
            <option value="markdown">Markdown</option>
            <option value="sql">SQL</option>
            <option value="typescript">TypeScript</option>
            <option value="lua">Lua</option>
        </select>
        <button id="formatMonaco" class="panel-btn">✨ Format</button>
        <button id="copyMonaco" class="panel-btn">📋 Copy</button>
        <button id="downloadMonaco" class="panel-btn">💾 Download</button>
        <button id="parseMonaco" class="panel-btn">🔍 Parse All</button>
    `;

    // Create Monaco editor
    this.loadMonaco().then(() => {
        this.canvas.monacoEditor = monaco.editor.create(editorDiv, {
            value: this.canvas.persistentContent || '// Start coding...\n',
            language: 'javascript',
            theme: 'vs-dark',
            automaticLayout: true,
            minimap: { enabled: true },
            fontSize: 14,
            lineNumbers: 'on',
            roundedSelection: false,
            scrollBeyondLastLine: false,
            readOnly: false,
            cursorStyle: 'line'
        });

        // Language switcher
        controls.querySelector('#monacoLang').addEventListener('change', (e) => {
            monaco.editor.setModelLanguage(this.canvas.monacoEditor.getModel(), e.target.value);
        });

        // Format
        controls.querySelector('#formatMonaco').addEventListener('click', () => {
            this.canvas.monacoEditor.getAction('editor.action.formatDocument').run();
        });

        // Copy
        controls.querySelector('#copyMonaco').addEventListener('click', () => {
            const value = this.canvas.monacoEditor.getValue();
            navigator.clipboard.writeText(value);
            const btn = controls.querySelector('#copyMonaco');
            const orig = btn.textContent;
            btn.textContent = '✅ Copied';
            setTimeout(() => btn.textContent = orig, 1500);
        });

        // Download
        controls.querySelector('#downloadMonaco').addEventListener('click', () => {
            const lang = controls.querySelector('#monacoLang').value;
            const ext = this.getFileExtension(lang);
            const value = this.canvas.monacoEditor.getValue();
            this.downloadFile(value, `code${ext}`);
        });

        // Parse all instances
        controls.querySelector('#parseMonaco').addEventListener('click', () => {
            this.canvas.persistentContent = this.canvas.monacoEditor.getValue();
            this.parseAllInstances();
        });
    });
};

// =====================================================================
// Embedded IDE + Simulator Mode
// =====================================================================

VeraChat.prototype.initEmbeddedIDE = function() {
    const { content, controls } = this.canvas;
    
    // Split layout: editor | simulator
    const wrapper = document.createElement('div');
    wrapper.style.cssText = `
        display: grid;
        grid-template-columns: 1fr 420px;
        gap: 12px;
        height: 100%;
    `;
    
    // Left: Editor
    const editorPane = document.createElement('div');
    editorPane.style.cssText = 'display: flex; flex-direction: column; gap: 8px;';
    editorPane.innerHTML = `
        <div style="display: flex; gap: 8px; align-items: center;">
            <label style="font-size: 13px; color: #94a3b8;">Language:
                <select id="ideLang" class="panel-btn">
                    <option value="arduino">Arduino (C++)</option>
                    <option value="javascript">JavaScript</option>
                    <option value="lua">Lua (TIC-80)</option>
                </select>
            </label>
            <label style="font-size: 13px; color: #94a3b8;">Board:
                <select id="ideBoard" class="panel-btn">
                    <option value="esp32">ESP32 DevKit</option>
                    <option value="uno">Arduino UNO</option>
                </select>
            </label>
        </div>
        <div id="ide-monaco-container" style="flex: 1; border: 1px solid #334155; border-radius: 6px; overflow: hidden;"></div>
    `;
    wrapper.appendChild(editorPane);
    
    // Right: Simulator
    const simPane = document.createElement('div');
    simPane.style.cssText = 'display: flex; flex-direction: column; gap: 8px;';
    simPane.innerHTML = `
        <div style="background: var(--panel-bg); padding: 10px; border-radius: 8px; border: 1px solid #334155;">
            <div id="ideBoardName" style="color: #fff; font-weight: 600; margin-bottom: 8px;">ESP32 DevKit</div>
            <div id="ideSimBoard" style="display: grid; grid-template-columns: repeat(auto-fill, 50px); gap: 8px; max-height: 300px; overflow: auto;"></div>
        </div>
        <div style="background: #000; color: #0f0; padding: 8px; border-radius: 8px; height: 200px; overflow: auto; font-family: monospace; font-size: 13px; border: 1px solid #334155;" id="ideConsole">[Serial Monitor]</div>
    `;
    wrapper.appendChild(simPane);
    
    content.appendChild(wrapper);

    // Controls
    controls.innerHTML = `
        <button id="ideRun" class="panel-btn">▶️ Run</button>
        <button id="ideStop" class="panel-btn">⏹ Stop</button>
        <button id="ideClearConsole" class="panel-btn">🧹 Clear Console</button>
        <div style="border-left: 1px solid #334155; height: 24px; margin: 0 4px;"></div>
        <label style="font-size: 13px; color: #94a3b8; display: flex; gap: 6px; align-items: center;">
            Port:
            <select id="ideUsbPort" class="panel-btn" style="padding: 4px 8px; font-size: 13px;"></select>
        </label>
        <button id="ideRefreshPorts" class="panel-btn">🔄 Refresh</button>
        <button id="ideConnectUSB" class="panel-btn">🔌 Connect USB</button>
        <button id="ideServerMonitor" class="panel-btn">📡 Server Monitor</button>
        <div style="border-left: 1px solid #334155; height: 24px; margin: 0 4px;"></div>
        <label style="font-size: 13px; color: #94a3b8; display: flex; gap: 6px; align-items: center;">
            FQBN:
            <input id="ideFqbn" class="panel-btn" style="padding: 4px 8px; font-size: 13px; width: 200px;" placeholder="esp32:esp32:esp32">
        </label>
        <button id="ideAutoFqbn" class="panel-btn">🔍 Auto-detect</button>
        <button id="ideFlash" class="panel-btn">⚡ Upload</button>
    `;

    // Initialize Monaco for IDE
    this.loadMonaco().then(() => {
        const ideEditor = monaco.editor.create(editorPane.querySelector('#ide-monaco-container'), {
            value: this.canvas.persistentContent || `// Arduino sketch
void setup() {
  pinMode(2, OUTPUT);
  Serial.println("Setup complete");
}

void loop() {
  digitalWrite(2, HIGH);
  Serial.println("LED ON");
  delay(500);
  digitalWrite(2, LOW);
  Serial.println("LED OFF");
  delay(500);
}`,
            language: 'arduino',
            theme: 'vs-dark',
            automaticLayout: true,
            minimap: { enabled: false },
            fontSize: 14
        });
        
        // Store reference
        editorPane.querySelector('#ide-monaco-container').monacoInstance = ideEditor;
        
        // Language switcher
        editorPane.querySelector('#ideLang').addEventListener('change', (e) => {
            const lang = e.target.value === 'arduino' ? 'arduino' : e.target.value;
            monaco.editor.setModelLanguage(ideEditor.getModel(), lang);
        });
        
        // Board switcher
        editorPane.querySelector('#ideBoard').addEventListener('change', (e) => {
            this.loadIDEBoard(e.target.value);
            
            // Auto-update FQBN
            const fqbnField = controls.querySelector('#ideFqbn');
            const defaultFQBNs = {
                esp32: "esp32:esp32:esp32",
                uno: "arduino:avr:uno"
            };
            if (fqbnField) {
                fqbnField.value = defaultFQBNs[e.target.value] || '';
            }
        });
        
        // Initialize board
        this.ideState = { running: false };
        this.loadIDEBoard('esp32');
        
        // Run button
        controls.querySelector('#ideRun').addEventListener('click', () => {
            this.runIDECode(ideEditor.getValue(), editorPane.querySelector('#ideLang').value);
        });
        
        // Stop button
        controls.querySelector('#ideStop').addEventListener('click', () => {
            this.stopIDECode();
        });
        
        // Clear console
        controls.querySelector('#ideClearConsole').addEventListener('click', () => {
            document.getElementById('ideConsole').innerHTML = '[Serial Monitor]<br>';
        });
        
        // Initialize USB serial state
        this.ideSerialPort = null;
        this.ideSerialReader = null;
        this.ideWSSerial = null;
        this.ideSSESource = null;
        
        // Refresh ports
        controls.querySelector('#ideRefreshPorts').addEventListener('click', () => {
            this.ideRefreshPorts();
        });
        
        // Connect USB
        controls.querySelector('#ideConnectUSB').addEventListener('click', () => {
            this.ideConnectUSB();
        });
        
        // Server monitor
        controls.querySelector('#ideServerMonitor').addEventListener('click', () => {
            this.ideStartServerMonitor();
        });
        
        // Auto-detect FQBN
        controls.querySelector('#ideAutoFqbn').addEventListener('click', () => {
            this.ideAutoDetectFQBN();
        });
        
        // Flash/Upload
        controls.querySelector('#ideFlash').addEventListener('click', () => {
            this.ideFlashToBoard(ideEditor.getValue());
        });
        
        // Initial port refresh
        this.ideRefreshPorts();
        
        // Add info message
        if (!('serial' in navigator)) {
            this.ideLog('[INFO] Web Serial API not available. Use Chrome/Edge with HTTPS or localhost for USB support.');
        } else {
            this.ideLog('[INFO] Web Serial API available. Click "Connect USB" to access physical boards.');
        }
        
        // Set default FQBN based on board
        const boardType = editorPane.querySelector('#ideBoard').value;
        const defaultFQBNs = {
            esp32: "esp32:esp32:esp32",
            uno: "arduino:avr:uno"
        };
        controls.querySelector('#ideFqbn').value = defaultFQBNs[boardType] || '';
    });
};

VeraChat.prototype.loadIDEBoard = function(type) {
    const BOARD_MAP = {
        esp32: { 
            name: "ESP32 DevKit", 
            pins: Array.from({length:22}, (_, i) => ({id:i,type:"digital"})) 
        },
        uno: { 
            name: "Arduino UNO", 
            pins: [
                {id:0,type:"digital"},{id:1,type:"digital"},{id:2,type:"digital"},{id:3,type:"pwm"},
                {id:4,type:"digital"},{id:5,type:"pwm"},{id:6,type:"pwm"},{id:7,type:"digital"},
                {id:8,type:"digital"},{id:9,type:"pwm"},{id:10,type:"pwm"},{id:11,type:"pwm"},
                {id:12,type:"digital"},{id:13,type:"digital"},
                {id:"A0",type:"analog"},{id:"A1",type:"analog"},{id:"A2",type:"analog"},
                {id:"A3",type:"analog"},{id:"A4",type:"analog"},{id:"A5",type:"analog"}
            ] 
        }
    };
    
    const board = BOARD_MAP[type];
    document.getElementById('ideBoardName').textContent = board.name;
    
    const grid = document.getElementById('ideSimBoard');
    grid.innerHTML = '';
    
    this.IDE_SIM_STATE = {};
    board.pins.forEach(pin => {
        this.IDE_SIM_STATE[pin.id] = { mode:'INPUT', value:'LOW', type: pin.type };
        const cell = document.createElement('div');
        cell.className = `ide-pin ${pin.type} LOW`;
        cell.id = 'ide-pin' + String(pin.id);
        cell.style.cssText = `
            width: 50px; height: 50px;
            display: flex; align-items: center; justify-content: center;
            border-radius: 6px; font-weight: 600; color: white;
            background: #555; border: 1px solid #777;
            transition: 120ms;
        `;
        cell.textContent = String(pin.id);
        grid.appendChild(cell);
    });
};

VeraChat.prototype.updateIDEPin = function(pin) {
    const state = this.IDE_SIM_STATE[pin];
    const el = document.getElementById('ide-pin' + String(pin));
    if (!el) return;
    
    if (state.value === 'HIGH') {
        el.style.background = 'limegreen';
        el.style.color = 'black';
        el.style.borderColor = '#0f0';
    } else {
        el.style.background = '#444';
        el.style.color = 'white';
        el.style.borderColor = '#777';
    }
};

VeraChat.prototype.ideLog = function(msg) {
    const console = document.getElementById('ideConsole');
    if (!console) return;
    const ts = new Date().toLocaleTimeString();
    console.innerHTML += `${ts} ${this._escapeHtml(msg)}<br>`;
    console.scrollTop = console.scrollHeight;
};

VeraChat.prototype.runIDECode = async function(code, lang) {
    if (this.ideState.running) return;
    
    this.ideState.running = true;
    this.ideLog('[START] Running code...');
    
    try {
        if (lang === 'arduino') {
            // Transpile Arduino to JS
            code = this.transpileArduino(code);
        }
        
        // Create simulator API
        const pinMode = (pin, mode) => {
            if (this.IDE_SIM_STATE[pin]) this.IDE_SIM_STATE[pin].mode = mode;
            this.updateIDEPin(pin);
        };
        
        const digitalWrite = (pin, val) => {
            if (!this.IDE_SIM_STATE[pin]) return;
            this.IDE_SIM_STATE[pin].value = (val === 'HIGH' || val === 1) ? 'HIGH' : 'LOW';
            this.updateIDEPin(pin);
            this.ideLog(`Pin ${pin} = ${this.IDE_SIM_STATE[pin].value}`);
        };
        
        const digitalRead = (pin) => {
            return this.IDE_SIM_STATE[pin] && this.IDE_SIM_STATE[pin].value === 'HIGH' ? 1 : 0;
        };
        
        const analogWrite = (pin, val) => {
            if (!this.IDE_SIM_STATE[pin]) return;
            this.IDE_SIM_STATE[pin].value = val > 0 ? 'HIGH' : 'LOW';
            this.updateIDEPin(pin);
            this.ideLog(`PWM ${pin} = ${val}`);
        };
        
        const analogRead = () => Math.floor(Math.random() * 1024);
        
        const Serial = {
            print: (v) => this.ideLog(String(v)),
            println: (v) => this.ideLog(String(v))
        };
        
        const delay = (ms) => new Promise(r => setTimeout(r, ms));
        
        // Execute code
        const wrapper = `
            "use strict";
            ${code}
            return { setup, loop };
        `;
        
        const fn = new Function('pinMode','digitalWrite','digitalRead','analogWrite','analogRead','Serial','delay', wrapper);
        const prog = fn(pinMode, digitalWrite, digitalRead, analogWrite, analogRead, Serial, delay);
        
        if (typeof prog.setup === 'function') await prog.setup();
        
        if (typeof prog.loop === 'function') {
            while (this.ideState.running) {
                try {
                    await prog.loop();
                } catch(e) {
                    this.ideLog('[ERROR] ' + e);
                    break;
                }
            }
        }
    } catch(e) {
        this.ideLog('[ERROR] ' + (e.stack || e));
    }
    
    this.ideState.running = false;
    this.ideLog('[STOP] Code stopped');
};

VeraChat.prototype.stopIDECode = function() {
    this.ideState.running = false;
};

VeraChat.prototype.transpileArduino = function(code) {
    let out = String(code).replace(/\r\n/g, '\n').replace(/\r/g, '\n');
    out = out.replace(/^\s*#include[^\n]*$/mg, '// removed #include');
    out = out.replace(/\b(unsigned\s+long|unsigned\s+int|unsigned|long|int|float|double|char|bool)\s+([A-Za-z_]\w*)\s*(=)?/g,
                      (m, t, name, eq) => 'let ' + name + (eq ? ' =' : ''));
    out = out.replace(/\bvoid\s+setup\s*\(\s*\)\s*\{/g, 'async function setup(){');
    out = out.replace(/\bvoid\s+loop\s*\(\s*\)\s*\{/g, 'async function loop(){');
    out = out.replace(/\bdelay\s*\(\s*([^)]+)\s*\)\s*;/g, 'await delay($1);');
    out = out.replace(/\bHIGH\b/g, `'HIGH'`);
    out = out.replace(/\bLOW\b/g, `'LOW'`);
    out = out.replace(/\bOUTPUT\b/g, `'OUTPUT'`);
    out = out.replace(/\bINPUT\b/g, `'INPUT'`);
    out = out.replace(/\bSerial\s*\.\s*print\s*\(/g, 'Serial.print(');
    out = out.replace(/\bSerial\s*\.\s*println\s*\(/g, 'Serial.println(');
    return out;
};

// =====================================================================
// Code Execution Mode (Multi-Language)
// =====================================================================

VeraChat.prototype.initCodeExecution = function() {
    const { content, controls } = this.canvas;
    
    // Split layout: editor | output
    const wrapper = document.createElement('div');
    wrapper.style.cssText = `
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 12px;
        height: 100%;
    `;
    
    // Left: Code Editor
    const editorPane = document.createElement('div');
    editorPane.style.cssText = 'display: flex; flex-direction: column; gap: 8px;';
    editorPane.innerHTML = `
        <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
            <label style="font-size: 13px; color: #94a3b8;">Language:
                <select id="execLang" class="panel-btn">
                    <option value="python">Python</option>
                    <option value="javascript">JavaScript (Node)</option>
                    <option value="typescript">TypeScript</option>
                    <option value="cpp">C++</option>
                    <option value="c">C</option>
                    <option value="rust">Rust</option>
                    <option value="go">Go</option>
                    <option value="java">Java</option>
                    <option value="ruby">Ruby</option>
                    <option value="php">PHP</option>
                    <option value="bash">Bash</option>
                    <option value="lua">Lua</option>
                    <option value="r">R</option>
                    <option value="kotlin">Kotlin</option>
                    <option value="swift">Swift</option>
                </select>
            </label>
            <label style="font-size: 13px; color: #94a3b8; display: flex; gap: 4px; align-items: center;">
                <input type="checkbox" id="execUseDocker" checked>
                Docker Sandbox
            </label>
            <label style="font-size: 13px; color: #94a3b8; display: flex; gap: 4px; align-items: center;">
                <input type="checkbox" id="execStream" checked>
                Stream Output
            </label>
        </div>
        <div id="exec-monaco-container" style="flex: 1; border: 1px solid #334155; border-radius: 6px; overflow: hidden;"></div>
    `;
    wrapper.appendChild(editorPane);
    
    // Right: Output
    const outputPane = document.createElement('div');
    outputPane.style.cssText = 'display: flex; flex-direction: column; gap: 8px;';
    outputPane.innerHTML = `
        <div style="display: flex; gap: 8px; align-items: center;">
            <span style="font-size: 14px; font-weight: bold; color: #94a3b8;">Output</span>
            <span id="execStatus" style="font-size: 12px; color: #64748b;"></span>
        </div>
        <div id="exec-output" style="flex: 1; background: #000; color: #0f0; padding: 12px; border-radius: 8px; overflow: auto; font-family: monospace; font-size: 13px; border: 1px solid #334155; white-space: pre-wrap; word-break: break-word;">[Execution Output]
Ready to execute code in any language!

Supported: Python, JavaScript, C++, Rust, Go, Java, Ruby, PHP, Bash, Lua, R, and more.

Click "▶️ Execute" to run your code.</div>
        <div id="exec-stats" style="padding: 8px; background: var(--panel-bg); border: 1px solid #334155; border-radius: 6px; font-size: 12px; color: #94a3b8; display: none;">
            <span id="execTime"></span> | 
            <span id="execMemory"></span> | 
            <span id="execExitCode"></span>
        </div>
    `;
    wrapper.appendChild(outputPane);
    
    content.appendChild(wrapper);

    // Controls
    controls.innerHTML = `
        <button id="execRun" class="panel-btn">▶️ Execute</button>
        <button id="execStop" class="panel-btn">⏹ Stop</button>
        <button id="execClear" class="panel-btn">🧹 Clear Output</button>
        <div style="border-left: 1px solid #334155; height: 24px; margin: 0 4px;"></div>
        <input type="file" id="execUploadFile" multiple style="display: none;">
        <button id="execUpload" class="panel-btn">📁 Upload Files</button>
        <button id="execDownloadOutput" class="panel-btn">💾 Save Output</button>
        <div style="border-left: 1px solid #334155; height: 24px; margin: 0 4px;"></div>
        <button id="execSnippets" class="panel-btn">📚 Code Snippets</button>
        <button id="execHelp" class="panel-btn">❓ API Info</button>
    `;

    // Initialize Monaco for execution
    this.loadMonaco().then(() => {
        const execEditor = monaco.editor.create(editorPane.querySelector('#exec-monaco-container'), {
            value: this.canvas.persistentContent || this.getCodeSnippet('python', 'hello'),
            language: 'python',
            theme: 'vs-dark',
            automaticLayout: true,
            minimap: { enabled: false },
            fontSize: 14,
            wordWrap: 'on'
        });
        
        // Store reference
        editorPane.querySelector('#exec-monaco-container').monacoInstance = execEditor;
        this.execState = {
            running: false,
            currentProcess: null,
            uploadedFiles: []
        };
        
        // Language switcher
        editorPane.querySelector('#execLang').addEventListener('change', (e) => {
            const lang = e.target.value;
            const monacoLang = this.getMonacoLanguage(lang);
            monaco.editor.setModelLanguage(execEditor.getModel(), monacoLang);
        });
        
        // Execute button
        controls.querySelector('#execRun').addEventListener('click', () => {
            this.executeCode(
                execEditor.getValue(),
                editorPane.querySelector('#execLang').value,
                editorPane.querySelector('#execUseDocker').checked,
                editorPane.querySelector('#execStream').checked
            );
        });
        
        // Stop button
        controls.querySelector('#execStop').addEventListener('click', () => {
            this.stopExecution();
        });
        
        // Clear output
        controls.querySelector('#execClear').addEventListener('click', () => {
            document.getElementById('exec-output').innerHTML = '[Execution Output]<br>';
            document.getElementById('exec-stats').style.display = 'none';
        });
        
        // Upload files
        controls.querySelector('#execUpload').addEventListener('click', () => {
            document.getElementById('execUploadFile').click();
        });
        
        const fileInput = controls.querySelector('#execUploadFile');
        fileInput.addEventListener('change', async (e) => {
            const files = Array.from(e.target.files);
            this.execState.uploadedFiles = [];
            
            for (const file of files) {
                const content = await file.text();
                this.execState.uploadedFiles.push({
                    name: file.name,
                    content: content
                });
            }
            
            this.execLog(`[INFO] Uploaded ${files.length} file(s): ${files.map(f => f.name).join(', ')}`);
            fileInput.value = '';
        });
        
        // Download output
        controls.querySelector('#execDownloadOutput').addEventListener('click', () => {
            const output = document.getElementById('exec-output').textContent;
            this.downloadFile(output, 'execution-output.txt');
        });
        
        // Code snippets
        controls.querySelector('#execSnippets').addEventListener('click', () => {
            this.showCodeSnippets(execEditor);
        });
        
        // Help
        controls.querySelector('#execHelp').addEventListener('click', () => {
            this.showExecutionHelp();
        });
    });
};

VeraChat.prototype.getMonacoLanguage = function(lang) {
    const map = {
        'python': 'python',
        'javascript': 'javascript',
        'typescript': 'typescript',
        'cpp': 'cpp',
        'c': 'c',
        'rust': 'rust',
        'go': 'go',
        'java': 'java',
        'ruby': 'ruby',
        'php': 'php',
        'bash': 'shell',
        'lua': 'lua',
        'r': 'r',
        'kotlin': 'kotlin',
        'swift': 'swift'
    };
    return map[lang] || 'plaintext';
};

VeraChat.prototype.getCodeSnippet = function(lang, type) {
    const snippets = {
        python: {
            hello: `# Python Hello World
print("Hello, World!")

# Input and output
name = input("Enter your name: ")
print(f"Hello, {name}!")

# List comprehension
squares = [x**2 for x in range(10)]
print(f"Squares: {squares}")`,
            api: `# Python API Example
import requests
import json

# Make API request
response = requests.get('https://api.github.com/users/github')
data = response.json()

print(f"Name: {data['name']}")
print(f"Followers: {data['followers']}")`,
            file: `# Python File Operations
with open('data.txt', 'w') as f:
    f.write("Hello from Python!\\n")
    f.write("Writing to files is easy.")

with open('data.txt', 'r') as f:
    content = f.read()
    print(content)`
        },
        javascript: {
            hello: `// JavaScript (Node.js) Hello World
console.log("Hello, World!");

// Array methods
const numbers = [1, 2, 3, 4, 5];
const doubled = numbers.map(x => x * 2);
console.log("Doubled:", doubled);

// Async/await
async function fetchData() {
    console.log("Fetching data...");
    return "Data retrieved!";
}

fetchData().then(console.log);`,
            api: `// JavaScript API Example
const https = require('https');

https.get('https://api.github.com/users/github', {
    headers: { 'User-Agent': 'Node.js' }
}, (res) => {
    let data = '';
    res.on('data', chunk => data += chunk);
    res.on('end', () => {
        const user = JSON.parse(data);
        console.log(\`Name: \${user.name}\`);
        console.log(\`Followers: \${user.followers}\`);
    });
});`,
            file: `// JavaScript File Operations
const fs = require('fs');

// Write file
fs.writeFileSync('data.txt', 'Hello from Node.js!\\n');
fs.appendFileSync('data.txt', 'Writing to files is easy.');

// Read file
const content = fs.readFileSync('data.txt', 'utf8');
console.log(content);`
        },
        cpp: {
            hello: `// C++ Hello World
#include <iostream>
#include <vector>
#include <algorithm>

int main() {
    std::cout << "Hello, World!" << std::endl;
    
    // Vectors and algorithms
    std::vector<int> numbers = {5, 2, 8, 1, 9};
    std::sort(numbers.begin(), numbers.end());
    
    std::cout << "Sorted: ";
    for(int n : numbers) {
        std::cout << n << " ";
    }
    std::cout << std::endl;
    
    return 0;
}`
        },
        rust: {
            hello: `// Rust Hello World
fn main() {
    println!("Hello, World!");
    
    // Vector operations
    let numbers: Vec<i32> = vec![1, 2, 3, 4, 5];
    let doubled: Vec<i32> = numbers.iter().map(|x| x * 2).collect();
    
    println!("Doubled: {:?}", doubled);
    
    // Pattern matching
    let x = 5;
    match x {
        1..=5 => println!("Between 1 and 5"),
        _ => println!("Something else"),
    }
}`
        },
        go: {
            hello: `// Go Hello World
package main

import (
    "fmt"
    "sort"
)

func main() {
    fmt.Println("Hello, World!")
    
    // Slices
    numbers := []int{5, 2, 8, 1, 9}
    sort.Ints(numbers)
    
    fmt.Println("Sorted:", numbers)
    
    // Goroutines
    ch := make(chan string)
    go func() {
        ch <- "Message from goroutine"
    }()
    fmt.Println(<-ch)
}`
        }
    };
    
    return (snippets[lang] && snippets[lang][type]) || snippets.python.hello;
};

VeraChat.prototype.executeCode = async function(code, language, useDocker, stream) {
    if (this.execState.running) {
        this.execLog('[ERROR] Code is already running. Stop it first.');
        return;
    }
    
    this.execState.running = true;
    const output = document.getElementById('exec-output');
    const status = document.getElementById('execStatus');
    const stats = document.getElementById('exec-stats');
    
    output.innerHTML = '[Execution Started]<br>';
    status.textContent = '⏳ Running...';
    status.style.color = '#fbbf24';
    stats.style.display = 'none';
    
    const startTime = Date.now();
    
    try {
        // Prepare request
        const payload = {
            code: code,
            language: language,
            useDocker: useDocker,
            stream: stream,
            files: this.execState.uploadedFiles
        };
        
        // Choose endpoint
        const endpoint = stream ? 'http://llm.int:8888/api/execution/execute-stream' : 'http://llm.int:8888/api/execution/execute';
        
        if (stream) {
            // Use Server-Sent Events for streaming
            await this.executeWithStream(endpoint, payload, output, status);
        } else {
            // Regular execution
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const result = await response.json();
            
            // Display output
            if (result.stdout) {
                output.innerHTML += '<span style="color: #0f0;">' + this._escapeHtml(result.stdout) + '</span><br>';
            }
            
            if (result.stderr) {
                output.innerHTML += '<span style="color: #ff4444;">' + this._escapeHtml(result.stderr) + '</span><br>';
            }
            
            if (result.error) {
                output.innerHTML += '<span style="color: #ff4444;">[ERROR] ' + this._escapeHtml(result.error) + '</span><br>';
            }
            
            // Show stats
            const execTime = Date.now() - startTime;
            this.showexecutiontats(result, execTime);
        }
        
        status.textContent = '✅ Completed';
        status.style.color = '#10b981';
        
    } catch(error) {
        output.innerHTML += `<span style="color: #ff4444;">[EXECUTION ERROR] ${this._escapeHtml(error.message)}</span><br>`;
        status.textContent = '❌ Failed';
        status.style.color = '#ef4444';
        
        // Check if backend is available
        if (error.message.includes('Failed to fetch') || error.message.includes('NetworkError')) {
            output.innerHTML += '<br><span style="color: #fbbf24;">[INFO] Backend execution server not available.</span><br>';
            output.innerHTML += '<span style="color: #94a3b8;">To enable code execution, set up the backend API:</span><br>';
            output.innerHTML += '<span style="color: #94a3b8;">  - Install: Docker, Python/Node.js</span><br>';
            output.innerHTML += '<span style="color: #94a3b8;">  - Run: See "API Info" button for setup</span><br>';
        }
    } finally {
        this.execState.running = false;
        output.scrollTop = output.scrollHeight;
    }
};

VeraChat.prototype.executeWithStream = async function(endpoint, payload, outputEl, statusEl) {
    return new Promise((resolve, reject) => {
        const eventSource = new EventSource(endpoint + '?' + new URLSearchParams({
            code: payload.code,
            language: payload.language,
            useDocker: payload.useDocker
        }));
        
        eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            
            if (data.type === 'stdout') {
                outputEl.innerHTML += '<span style="color: #0f0;">' + this._escapeHtml(data.content) + '</span>';
            } else if (data.type === 'stderr') {
                outputEl.innerHTML += '<span style="color: #ff4444;">' + this._escapeHtml(data.content) + '</span>';
            } else if (data.type === 'complete') {
                eventSource.close();
                resolve(data);
            }
            
            outputEl.scrollTop = outputEl.scrollHeight;
        };
        
        eventSource.onerror = (error) => {
            eventSource.close();
            reject(new Error('Stream connection failed'));
        };
        
        this.execState.currentProcess = eventSource;
    });
};

VeraChat.prototype.stopExecution = function() {
    if (this.execState.currentProcess) {
        this.execState.currentProcess.close();
        this.execState.currentProcess = null;
    }
    
    this.execState.running = false;
    this.execLog('[STOP] Execution stopped by user');
    
    const status = document.getElementById('execStatus');
    status.textContent = '⏹ Stopped';
    status.style.color = '#64748b';
};

VeraChat.prototype.showexecutiontats = function(result, execTime) {
    const stats = document.getElementById('exec-stats');
    const timeEl = document.getElementById('execTime');
    const memoryEl = document.getElementById('execMemory');
    const exitEl = document.getElementById('execExitCode');
    
    timeEl.textContent = `Time: ${execTime}ms`;
    memoryEl.textContent = `Memory: ${result.memory || 'N/A'}`;
    exitEl.textContent = `Exit: ${result.exitCode || 0}`;
    
    stats.style.display = 'block';
};

VeraChat.prototype.execLog = function(msg) {
    const output = document.getElementById('exec-output');
    if (!output) return;
    const ts = new Date().toLocaleTimeString();
    output.innerHTML += `${ts} ${this._escapeHtml(msg)}<br>`;
    output.scrollTop = output.scrollHeight;
};

VeraChat.prototype.showCodeSnippets = function(editor) {
    const snippets = [
        { name: 'Python Hello World', lang: 'python', type: 'hello' },
        { name: 'Python API Request', lang: 'python', type: 'api' },
        { name: 'Python File I/O', lang: 'python', type: 'file' },
        { name: 'JavaScript Hello World', lang: 'javascript', type: 'hello' },
        { name: 'JavaScript API Request', lang: 'javascript', type: 'api' },
        { name: 'JavaScript File I/O', lang: 'javascript', type: 'file' },
        { name: 'C++ Hello World', lang: 'cpp', type: 'hello' },
        { name: 'Rust Hello World', lang: 'rust', type: 'hello' },
        { name: 'Go Hello World', lang: 'go', type: 'hello' }
    ];
    
    const choice = prompt(
        'Choose a code snippet:\n\n' +
        snippets.map((s, i) => `${i + 1}. ${s.name}`).join('\n') +
        '\n\nEnter number (1-' + snippets.length + '):'
    );
    
    const idx = parseInt(choice) - 1;
    if (idx >= 0 && idx < snippets.length) {
        const snippet = snippets[idx];
        editor.setValue(this.getCodeSnippet(snippet.lang, snippet.type));
        
        // Update language selector
        const langSelect = document.getElementById('execLang');
        if (langSelect) {
            langSelect.value = snippet.lang;
            monaco.editor.setModelLanguage(editor.getModel(), this.getMonacoLanguage(snippet.lang));
        }
        
        this.execLog(`[INFO] Loaded snippet: ${snippet.name}`);
    }
};

VeraChat.prototype.showExecutionHelp = function() {
    const help = `
Code Execution API Setup
========================

BACKEND REQUIREMENTS:
- Docker (for sandboxed execution)
- Python 3.8+ OR Node.js 16+
- Language runtimes (Python, Node, GCC, Rust, etc.)

API ENDPOINTS:

1. POST /execute
   - Executes code and returns result
   - Body: { code, language, useDocker, files }
   - Returns: { stdout, stderr, exitCode, memory }

2. GET /execute-stream (SSE)
   - Streams output in real-time
   - Query: ?code=...&language=...&useDocker=...
   - Events: stdout, stderr, complete

DOCKER SETUP:
\`\`\`bash
# Pull language images
docker pull python:3.11-slim
docker pull node:18-slim
docker pull gcc:latest
docker pull rust:latest

# Run with resource limits
docker run --rm -i \\
  --memory="256m" \\
  --cpus="0.5" \\
  --network=none \\
  python:3.11-slim python
\`\`\`

PYTHON BACKEND EXAMPLE:
\`\`\`python
from fastapi import FastAPI
import subprocess
import docker

app = FastAPI()

@app.post("/execute")
async def execute(request: ExecuteRequest):
    if request.useDocker:
        client = docker.from_env()
        container = client.containers.run(
            f"{request.language}:latest",
            command=["python", "-c", request.code],
            detach=True,
            mem_limit="256m",
            network_disabled=True
        )
        result = container.wait()
        stdout = container.logs(stdout=True, stderr=False)
        stderr = container.logs(stdout=False, stderr=True)
        container.remove()
        return {
            "stdout": stdout.decode(),
            "stderr": stderr.decode(),
            "exitCode": result["StatusCode"]
        }
\`\`\`

SECURITY NOTES:
- Always use Docker for untrusted code
- Limit memory, CPU, and network
- Set execution timeouts (30s default)
- Disable dangerous syscalls
- Use read-only filesystems

SUPPORTED LANGUAGES:
Python, JavaScript, TypeScript, C/C++, Rust, Go, 
Java, Ruby, PHP, Bash, Lua, R, Kotlin, Swift

More info: See GitHub repo for full backend examples
`;
    
    this.execLog(help);
    alert('API setup guide logged to console!');
};

// =====================================================================
// TIC-80 Fantasy Console Mode (FIXED)
// =====================================================================

VeraChat.prototype.initTIC80 = function() {
    const { content, controls } = this.canvas;
    
    // Split layout: editor | console/player
    const wrapper = document.createElement('div');
    wrapper.style.cssText = `
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 12px;
        height: 100%;
    `;
    
    // Left: Code Editor
    const editorPane = document.createElement('div');
    editorPane.style.cssText = 'display: flex; flex-direction: column; gap: 8px;';
    editorPane.innerHTML = `
        <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
            <label style="font-size: 13px; color: #94a3b8;">Language:
                <select id="tic80Lang" class="panel-btn">
                    <option value="lua">Lua</option>
                    <option value="javascript">JavaScript</option>
                    <option value="moonscript">MoonScript</option>
                    <option value="wren">Wren</option>
                    <option value="fennel">Fennel</option>
                </select>
            </label>
            <button id="tic80NewCart" class="panel-btn" style="font-size: 12px;">🆕 New Cart</button>
            <button id="tic80Templates" class="panel-btn" style="font-size: 12px;">📚 Templates</button>
        </div>
        <div id="tic80-monaco-container" style="flex: 1; border: 1px solid #334155; border-radius: 6px; overflow: hidden;"></div>
    `;
    wrapper.appendChild(editorPane);
    
    // Right: TIC-80 Player + Console
    const playerPane = document.createElement('div');
    playerPane.style.cssText = 'display: flex; flex-direction: column; gap: 8px;';
    playerPane.innerHTML = `
        <div style="display: flex; gap: 8px; align-items: center;">
            <span style="font-size: 14px; font-weight: bold; color: #94a3b8;">TIC-80 Console</span>
            <button id="tic80TogglePlayer" class="panel-btn" style="font-size: 12px;">🎮 Show Player</button>
        </div>
        <div id="tic80-player-wrapper" style="flex: 1; border: 1px solid #334155; border-radius: 6px; background: #000; overflow: hidden; display: none;">
            <iframe id="tic80-player" style="width: 100%; height: 100%; border: 0;" sandbox="allow-scripts allow-same-origin"></iframe>
        </div>
        <div id="tic80-console" style="flex: 1; background: #000; color: #0f0; padding: 8px; border-radius: 8px; overflow: auto; font-family: monospace; font-size: 13px; border: 1px solid #334155;">[TIC-80 Output]
Type code in the editor, then click "Run Code"
Use "Show Player" to test your game!</div>
    `;
    wrapper.appendChild(playerPane);
    
    content.appendChild(wrapper);

    // Controls
    controls.innerHTML = `
        <button id="tic80Run" class="panel-btn">▶️ Run Code</button>
        <button id="tic80Stop" class="panel-btn">⏹ Stop</button>
        <button id="tic80ClearConsole" class="panel-btn">🧹 Clear Console</button>
        <div style="border-left: 1px solid #334155; height: 24px; margin: 0 4px;"></div>
        <button id="tic80ExportCart" class="panel-btn">💾 Export .tic</button>
        <button id="tic80ImportCart" class="panel-btn">📂 Import .tic</button>
        <button id="tic80ExportCode" class="panel-btn">📄 Export Code</button>
        <div style="border-left: 1px solid #334155; height: 24px; margin: 0 4px;"></div>
        <button id="tic80OpenPlayer" class="panel-btn">🌐 Open in tic80.com</button>
        <button id="tic80Help" class="panel-btn">❓ Help</button>
        <input type="file" id="tic80ImportFile" accept=".tic,.lua,.js" style="display: none;">
    `;

    // Initialize Monaco for TIC-80
    this.loadMonaco().then(() => {
        const tic80Editor = monaco.editor.create(editorPane.querySelector('#tic80-monaco-container'), {
            value: this.canvas.persistentContent || this.getTIC80Template('lua', 'basic'),
            language: 'lua',
            theme: 'vs-dark',
            automaticLayout: true,
            minimap: { enabled: false },
            fontSize: 14,
            wordWrap: 'on',
            lineNumbers: 'on'
        });
        
        // Store reference
        editorPane.querySelector('#tic80-monaco-container').monacoInstance = tic80Editor;
        this.tic80State = {
            running: false,
            playerVisible: false,
            language: 'lua'
        };
        
        // Language switcher
        editorPane.querySelector('#tic80Lang').addEventListener('change', (e) => {
            const lang = e.target.value;
            this.tic80State.language = lang;
            const monacoLang = lang === 'lua' ? 'lua' : 
                               lang === 'javascript' ? 'javascript' : 
                               'plaintext';
            monaco.editor.setModelLanguage(tic80Editor.getModel(), monacoLang);
        });
        
        // New cart
        editorPane.querySelector('#tic80NewCart').addEventListener('click', () => {
            const lang = editorPane.querySelector('#tic80Lang').value;
            tic80Editor.setValue(this.getTIC80Template(lang, 'basic'));
            this.tic80Log('[INFO] New cartridge created');
        });
        
        // Templates
        editorPane.querySelector('#tic80Templates').addEventListener('click', () => {
            this.showTIC80Templates(tic80Editor);
        });
        
        // Toggle player
        playerPane.querySelector('#tic80TogglePlayer').addEventListener('click', () => {
            this.toggleTIC80Player();
        });
        
        // Run code
        controls.querySelector('#tic80Run').addEventListener('click', () => {
            this.runTIC80Code(tic80Editor.getValue());
        });
        
        // Stop
        controls.querySelector('#tic80Stop').addEventListener('click', () => {
            this.stopTIC80();
        });
        
        // Clear console
        controls.querySelector('#tic80ClearConsole').addEventListener('click', () => {
            document.getElementById('tic80-console').innerHTML = '[TIC-80 Output]<br>';
        });
        
        // Export cartridge
        controls.querySelector('#tic80ExportCart').addEventListener('click', () => {
            this.exportTIC80Cartridge(tic80Editor.getValue());
        });
        
        // Import cartridge
        controls.querySelector('#tic80ImportCart').addEventListener('click', () => {
            document.getElementById('tic80ImportFile').click();
        });
        
        // Export code only
        controls.querySelector('#tic80ExportCode').addEventListener('click', () => {
            const lang = editorPane.querySelector('#tic80Lang').value;
            const ext = lang === 'lua' ? '.lua' : lang === 'javascript' ? '.js' : '.txt';
            this.downloadFile(tic80Editor.getValue(), `game${ext}`);
        });
        
        // Open in tic80.com
        controls.querySelector('#tic80OpenPlayer').addEventListener('click', () => {
            this.openTIC80InBrowser(tic80Editor.getValue());
        });
        
        // Help
        controls.querySelector('#tic80Help').addEventListener('click', () => {
            this.showTIC80Help();
        });
        
        // Import file handler
        const importFile = controls.querySelector('#tic80ImportFile');
        importFile.addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file) return;
            
            try {
                const text = await file.text();
                
                // If it's a .tic file, try to extract the code section
                if (file.name.endsWith('.tic')) {
                    const code = this.extractCodeFromTIC(text);
                    tic80Editor.setValue(code || text);
                    this.tic80Log(`[INFO] Imported cartridge: ${file.name}`);
                } else {
                    // Plain code file
                    tic80Editor.setValue(text);
                    this.tic80Log(`[INFO] Imported code: ${file.name}`);
                }
                
                // Update language based on file extension
                if (file.name.endsWith('.lua')) {
                    editorPane.querySelector('#tic80Lang').value = 'lua';
                    monaco.editor.setModelLanguage(tic80Editor.getModel(), 'lua');
                } else if (file.name.endsWith('.js')) {
                    editorPane.querySelector('#tic80Lang').value = 'javascript';
                    monaco.editor.setModelLanguage(tic80Editor.getModel(), 'javascript');
                }
            } catch(err) {
                this.tic80Log('[ERROR] Failed to import: ' + err.message);
                alert('Failed to import file: ' + err.message);
            }
            
            // Reset file input
            importFile.value = '';
        });
        
        this.tic80Log('[TIC-80] Ready! Write your game code and click Run.');
    });
};

VeraChat.prototype.getTIC80Template = function(language, type) {
    const templates = {
        lua: {
            basic: `-- title:  My Game
-- author: game developer
-- desc:   short description
-- script: lua

t=0
x=96
y=24

function TIC()
 if btn(0) then y=y-1 end
 if btn(1) then y=y+1 end
 if btn(2) then x=x-1 end
 if btn(3) then x=x+1 end

 cls(13)
 spr(1+t%60//30*2,x,y,14,3,0,0,2,2)
 print("HELLO WORLD!",84,84)
 t=t+1
end`,
            sprite: `-- title:  Sprite Demo
-- author: game developer
-- script: lua

x=120
y=68

function TIC()
 if btn(0) then y=y-2 end
 if btn(1) then y=y+2 end
 if btn(2) then x=x-2 end
 if btn(3) then x=x+2 end
 
 cls(0)
 spr(0,x,y,0)
 print("Move with arrows",50,10,15)
end`,
            pixel: `-- title:  Pixel Art
-- author: game developer
-- script: lua

t=0

function TIC()
 cls(0)
 
 for i=0,15 do
  for j=0,15 do
   pix(i*8+t%8,j*8+t%8,i+j)
  end
 end
 
 print("TIC-80 Pixel Demo",50,130,15)
 t=t+1
end`
        },
        javascript: {
            basic: `// title:  My Game
// author: game developer
// desc:   short description
// script: js

var t=0;
var x=96;
var y=24;

function TIC() {
 if(btn(0)) y=y-1;
 if(btn(1)) y=y+1;
 if(btn(2)) x=x-1;
 if(btn(3)) x=x+1;

 cls(13);
 spr(1+t%60/30*2,x,y,14,3,0,0,2,2);
 print("HELLO WORLD!",84,84);
 t=t+1;
}`,
            sprite: `// title:  Sprite Demo
// author: game developer
// script: js

var x=120;
var y=68;

function TIC() {
 if(btn(0)) y=y-2;
 if(btn(1)) y=y+2;
 if(btn(2)) x=x-2;
 if(btn(3)) x=x+2;
 
 cls(0);
 spr(0,x,y,0);
 print("Move with arrows",50,10,15);
}`
        }
    };
    
    return (templates[language] && templates[language][type]) || templates.lua.basic;
};

VeraChat.prototype.tic80Log = function(msg) {
    const console = document.getElementById('tic80-console');
    if (!console) return;
    const ts = new Date().toLocaleTimeString();
    console.innerHTML += `${ts} ${this._escapeHtml(msg)}<br>`;
    console.scrollTop = console.scrollHeight;
};

VeraChat.prototype.toggleTIC80Player = function() {
    const player = document.getElementById('tic80-player-wrapper');
    const consoleEl = document.getElementById('tic80-console');
    const btn = document.getElementById('tic80TogglePlayer');
    
    if (!this.tic80State.playerVisible) {
        // Show player, hide console
        player.style.display = 'block';
        consoleEl.style.display = 'none';
        btn.textContent = '📝 Show Console';
        this.tic80State.playerVisible = true;
        
        // Load TIC-80 player if not loaded
        const iframe = document.getElementById('tic80-player');
        if (!iframe.src) {
            iframe.src = 'https://tic80.com/play';
            this.tic80Log('[INFO] Loading TIC-80 player...');
        }
    } else {
        // Show console, hide player
        player.style.display = 'none';
        consoleEl.style.display = 'block';
        btn.textContent = '🎮 Show Player';
        this.tic80State.playerVisible = false;
    }
};

VeraChat.prototype.runTIC80Code = function(code) {
    this.tic80Log('[RUN] Starting TIC-80 execution...');
    this.tic80State.running = true;
    
    // Show player
    if (!this.tic80State.playerVisible) {
        this.toggleTIC80Player();
    }
    
    const iframe = document.getElementById('tic80-player');
    const lang = document.getElementById('tic80Lang')?.value || 'lua';
    
    try {
        // Create TIC-80 runtime environment
        const runtime = this.createTIC80Runtime(code, lang);
        
        // Load runtime into iframe
        iframe.srcdoc = runtime;
        
        this.tic80Log('[OK] Code loaded into TIC-80 player');
        this.tic80Log('[INFO] Game is running at 60 FPS');
        this.tic80Log('[INFO] Use arrow keys to control');
        
    } catch(e) {
        this.tic80Log('[ERROR] Failed to run: ' + e.message);
    }
};

VeraChat.prototype.stopTIC80 = function() {
    this.tic80State.running = false;
    this.tic80Log('[STOP] Code execution stopped');
};

VeraChat.prototype.validateTIC80Code = function(code) {
    const issues = [];
    
    // Check for common mistakes
    if (!code.includes('TIC')) {
        issues.push('No TIC() function found');
    }
    
    if (code.length > 65536) {
        issues.push('Code exceeds TIC-80 size limit (64KB)');
    }
    
    // Check for undefined variables in Lua
    const undefinedPattern = /\b([a-z_][a-z0-9_]*)\s*=/gi;
    const definedPattern = /\b(local|function)\s+([a-z_][a-z0-9_]*)/gi;
    
    return issues;
};

VeraChat.prototype.exportTIC80Cartridge = function(code) {
    // Create a basic .tic cartridge structure
    // This is a simplified version - real .tic files have binary format
    const cartridge = this.createTIC80Cartridge(code);
    this.downloadFile(cartridge, 'game.tic');
    this.tic80Log('[EXPORT] Cartridge exported as game.tic');
    this.tic80Log('[INFO] Note: This is a text-based export. For full binary .tic:');
    this.tic80Log('  1. Open in tic80.com');
    this.tic80Log('  2. Use TIC-80 to save as proper .tic file');
};

VeraChat.prototype.createTIC80Cartridge = function(code) {
    // TIC-80 cartridge format (simplified text version)
    const header = `-- title:   My Game
-- author:  game developer
-- desc:    Created in VeraChat Canvas
-- script:  lua
-- input:   gamepad

`;
    return header + code;
};

VeraChat.prototype.extractCodeFromTIC = function(ticContent) {
    // Try to extract code section from .tic file
    // TIC-80 cartridges can be text or binary
    
    // If it's text format, extract everything after metadata
    const lines = ticContent.split('\n');
    let codeStart = 0;
    
    for (let i = 0; i < lines.length; i++) {
        if (lines[i].startsWith('-- script:')) {
            codeStart = i + 1;
            break;
        }
    }
    
    if (codeStart > 0) {
        return lines.slice(codeStart).join('\n');
    }
    
    // If binary format, return as-is (user will need to use TIC-80 to edit)
    return ticContent;
};

VeraChat.prototype.openTIC80InBrowser = function(code) {
    // Create a data URL or open tic80.com with code
    const encoded = encodeURIComponent(code);
    
    // Method 1: Try to use TIC-80's code parameter (if supported)
    // Method 2: Open blank window with instructions
    
    const html = `<!doctype html>
<meta charset="utf-8">
<title>TIC-80 Game</title>
<style>
  body { background: #000; color: #0f0; font-family: monospace; padding: 20px; }
  pre { background: #111; padding: 20px; border: 1px solid #0f0; overflow: auto; }
  a { color: #0ff; }
</style>
<body>
<h1>TIC-80 Game Code</h1>
<p>Copy the code below and paste it into <a href="https://tic80.com/play" target="_blank">TIC-80</a>:</p>
<ol>
  <li>Click the link above to open TIC-80</li>
  <li>Press ESC to open the console</li>
  <li>Type: <code>new lua</code> and press Enter</li>
  <li>Type: <code>load</code> to open the editor</li>
  <li>Paste your code (Ctrl+V or Cmd+V)</li>
  <li>Press ESC to return to console</li>
  <li>Type: <code>run</code> to start your game!</li>
</ol>
<h3>Your Code:</h3>
<pre id="code"></pre>
<button onclick="copyCode()" style="padding:10px 20px;background:#0f0;color:#000;border:0;font-size:16px;cursor:pointer;font-family:monospace;">📋 Copy Code</button>
<script>
document.getElementById('code').textContent = decodeURIComponent('${encoded}');
function copyCode() {
  const code = document.getElementById('code').textContent;
  navigator.clipboard.writeText(code).then(() => {
    alert('Code copied! Now paste it into TIC-80.');
  });
}
</script>
</body>`;
    
    const blob = new Blob([html], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    window.open(url, '_blank');
    
    this.tic80Log('[INFO] Opened code in new tab with instructions');
};

VeraChat.prototype.showTIC80Templates = function(editor) {
    const templates = [
        { name: 'Basic Game Loop', lang: 'lua', type: 'basic' },
        { name: 'Sprite Movement', lang: 'lua', type: 'sprite' },
        { name: 'Pixel Art Demo', lang: 'lua', type: 'pixel' },
        { name: 'JavaScript Basic', lang: 'javascript', type: 'basic' },
        { name: 'JavaScript Sprite', lang: 'javascript', type: 'sprite' }
    ];
    
    const choice = prompt(
        'Choose a template:\n\n' +
        templates.map((t, i) => `${i + 1}. ${t.name} (${t.lang})`).join('\n') +
        '\n\nEnter number (1-' + templates.length + '):'
    );
    
    const idx = parseInt(choice) - 1;
    if (idx >= 0 && idx < templates.length) {
        const template = templates[idx];
        editor.setValue(this.getTIC80Template(template.lang, template.type));
        
        // Update language selector
        const langSelect = document.getElementById('tic80Lang');
        if (langSelect) {
            langSelect.value = template.lang;
            const monacoLang = template.lang === 'lua' ? 'lua' : 
                               template.lang === 'javascript' ? 'javascript' : 
                               'plaintext';
            monaco.editor.setModelLanguage(editor.getModel(), monacoLang);
        }
        
        this.tic80Log(`[INFO] Loaded template: ${template.name}`);
    }
};

VeraChat.prototype.showTIC80Help = function() {
    const help = `
TIC-80 Quick Reference
=====================

Main Function:
  function TIC()  -- Called 60 times per second

Input:
  btn(id)        -- Check button (0-7: up,down,left,right,A,B,X,Y)
  btnp(id)       -- Button pressed (once)

Graphics:
  cls(color)     -- Clear screen
  pix(x,y,color) -- Draw pixel
  line(x0,y0,x1,y1,color) -- Draw line
  rect(x,y,w,h,color) -- Draw rectangle
  rectb(x,y,w,h,color) -- Draw rectangle border
  circ(x,y,r,color) -- Draw circle
  circb(x,y,r,color) -- Draw circle border
  spr(id,x,y,colorkey,scale,flip,rotate,w,h) -- Draw sprite
  print(text,x,y,color) -- Print text

Map:
  map(x,y,w,h,sx,sy,colorkey,scale) -- Draw map

Audio:
  music(track) -- Play music
  sfx(id,note,duration,channel,volume,speed) -- Play sound

Math:
  math.sin(x), math.cos(x), math.random(), etc.

Screen:
  240x136 pixels
  16 colors (0-15)

More: https://github.com/nesbox/TIC-80/wiki
`;
    
    this.tic80Log(help);
    alert('TIC-80 help logged to console!');
};

VeraChat.prototype.createTIC80Runtime = function(code, language) {
    // Transpile Lua to JavaScript if needed
    let jsCode = code;
    if (language === 'lua') {
        jsCode = this.transpileLuaToJS(code);
    }
    
    // Create HTML runtime with canvas and TIC-80 API
    const html = `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>TIC-80 Runtime</title>
<style>
  body { 
    margin: 0; 
    padding: 0; 
    background: #000; 
    display: flex; 
    justify-content: center; 
    align-items: center; 
    height: 100vh;
    overflow: hidden;
  }
  canvas { 
    image-rendering: pixelated;
    image-rendering: crisp-edges;
    border: 2px solid #333;
  }
  #info {
    position: absolute;
    top: 10px;
    left: 10px;
    color: #0f0;
    font-family: monospace;
    font-size: 12px;
    background: rgba(0,0,0,0.7);
    padding: 8px;
    border-radius: 4px;
  }
</style>
</head>
<body>
<canvas id="screen" width="240" height="136"></canvas>
<div id="info">TIC-80 Runtime<br>FPS: <span id="fps">60</span></div>

<script>
// TIC-80 Runtime Implementation
const canvas = document.getElementById('screen');
const ctx = canvas.getContext('2d');
const WIDTH = 240;
const HEIGHT = 136;

// Scale canvas for better visibility
canvas.style.width = '720px';
canvas.style.height = '408px';

// TIC-80 Color Palette (16 colors)
const PALETTE = [
  '#1a1c2c', '#5d275d', '#b13e53', '#ef7d57',
  '#ffcd75', '#a7f070', '#38b764', '#257179',
  '#29366f', '#3b5dc9', '#41a6f6', '#73eff7',
  '#f4f4f4', '#94b0c2', '#566c86', '#333c57'
];

// Input state
const keys = {};
const btns = [false, false, false, false, false, false, false, false];
const btnsp = [false, false, false, false, false, false, false, false];
const prevBtns = [...btns];

// Keyboard mapping
const keyMap = {
  'ArrowUp': 0, 'w': 0, 'W': 0,
  'ArrowDown': 1, 's': 1, 'S': 1,
  'ArrowLeft': 2, 'a': 2, 'A': 2,
  'ArrowRight': 3, 'd': 3, 'D': 3,
  'z': 4, 'Z': 4, 'n': 4, 'N': 4,
  'x': 5, 'X': 5, 'm': 5, 'M': 5,
  'c': 6, 'C': 6,
  'v': 7, 'V': 7
};

document.addEventListener('keydown', (e) => {
  if (keyMap[e.key] !== undefined) {
    e.preventDefault();
    btns[keyMap[e.key]] = true;
  }
});

document.addEventListener('keyup', (e) => {
  if (keyMap[e.key] !== undefined) {
    e.preventDefault();
    btns[keyMap[e.key]] = false;
  }
});

// TIC-80 API Implementation
function cls(color = 0) {
  ctx.fillStyle = PALETTE[color % 16];
  ctx.fillRect(0, 0, WIDTH, HEIGHT);
}

function pix(x, y, color) {
  if (x < 0 || x >= WIDTH || y < 0 || y >= HEIGHT) return;
  ctx.fillStyle = PALETTE[color % 16];
  ctx.fillRect(Math.floor(x), Math.floor(y), 1, 1);
}

function line(x0, y0, x1, y1, color) {
  ctx.strokeStyle = PALETTE[color % 16];
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(Math.floor(x0) + 0.5, Math.floor(y0) + 0.5);
  ctx.lineTo(Math.floor(x1) + 0.5, Math.floor(y1) + 0.5);
  ctx.stroke();
}

function rect(x, y, w, h, color) {
  ctx.fillStyle = PALETTE[color % 16];
  ctx.fillRect(Math.floor(x), Math.floor(y), Math.floor(w), Math.floor(h));
}

function rectb(x, y, w, h, color) {
  ctx.strokeStyle = PALETTE[color % 16];
  ctx.lineWidth = 1;
  ctx.strokeRect(Math.floor(x) + 0.5, Math.floor(y) + 0.5, Math.floor(w) - 1, Math.floor(h) - 1);
}

function circ(x, y, r, color) {
  ctx.fillStyle = PALETTE[color % 16];
  ctx.beginPath();
  ctx.arc(Math.floor(x), Math.floor(y), Math.floor(r), 0, Math.PI * 2);
  ctx.fill();
}

function circb(x, y, r, color) {
  ctx.strokeStyle = PALETTE[color % 16];
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.arc(Math.floor(x), Math.floor(y), Math.floor(r), 0, Math.PI * 2);
  ctx.stroke();
}

function spr(id, x, y, colorkey = -1, scale = 1, flip = 0, rotate = 0, w = 1, h = 1) {
  // Simple sprite rendering (8x8 colored squares for demo)
  const colors = [6, 12, 14, 4, 11, 9];
  const c = colors[id % colors.length];
  rect(x, y, 8 * w * scale, 8 * h * scale, c);
}

function print(text, x = 0, y = 0, color = 15, fixed = false, scale = 1) {
  ctx.fillStyle = PALETTE[color % 16];
  ctx.font = \`\${6 * scale}px monospace\`;
  ctx.fillText(String(text), Math.floor(x), Math.floor(y) + 6 * scale);
}

function btn(id) {
  return btns[id] || false;
}

function btnp(id) {
  const pressed = btns[id] && !prevBtns[id];
  return pressed;
}

// Math functions
const math = {
  sin: Math.sin,
  cos: Math.cos,
  tan: Math.tan,
  abs: Math.abs,
  floor: Math.floor,
  ceil: Math.ceil,
  sqrt: Math.sqrt,
  random: Math.random,
  min: Math.min,
  max: Math.max,
  pi: Math.PI
};

// User code
let t = 0;
let userTIC = null;

try {
  ${jsCode}
  
  // Find TIC function
  if (typeof TIC === 'function') {
    userTIC = TIC;
  } else {
    throw new Error('No TIC() function found!');
  }
} catch(e) {
  console.error('Code error:', e);
  document.getElementById('info').innerHTML = 'Error: ' + e.message;
}

// Main loop
let lastTime = performance.now();
let fps = 60;

function gameLoop() {
  // Update button press state
  for (let i = 0; i < 8; i++) {
    btnsp[i] = btns[i] && !prevBtns[i];
    prevBtns[i] = btns[i];
  }
  
  // Run user code
  if (userTIC) {
    try {
      userTIC();
    } catch(e) {
      console.error('Runtime error:', e);
      document.getElementById('info').innerHTML = 'Runtime Error: ' + e.message;
      return; // Stop execution on error
    }
  }
  
  t++;
  
  // Calculate FPS
  const now = performance.now();
  fps = Math.round(1000 / (now - lastTime));
  lastTime = now;
  document.getElementById('fps').textContent = fps;
  
  // Continue loop at 60 FPS
  setTimeout(() => requestAnimationFrame(gameLoop), 1000 / 60);
}

// Start the game
if (userTIC) {
  cls(0);
  print('Starting...', 80, 64, 15);
  setTimeout(() => requestAnimationFrame(gameLoop), 100);
} else {
  cls(0);
  print('ERROR: No TIC() function', 40, 64, 8);
}
</script>
</body>
</html>`;
    
    return html;
};

VeraChat.prototype.transpileLuaToJS = function(lua) {
    // Simple Lua to JavaScript transpiler for common TIC-80 patterns
    let js = lua;
    
    // Remove Lua comments but keep title/meta comments
    js = js.replace(/--(?! title:|-- author:|-- desc:|-- script:)([^\n]*)/g, '//$1');
    
    // Function definitions
    js = js.replace(/function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\((.*?)\)/g, 'function $1($2)');
    
    // Local variables
    js = js.replace(/\blocal\s+/g, 'let ');
    
    // For loops: for i=start,end,step do
    js = js.replace(/for\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*([^,]+),([^,\n]+)(?:,([^\n]+))?\s+do/g, 
                    'for(let $1=$2; $1<=$3; $1+=($4)||1)');
    
    // While loops
    js = js.replace(/while\s+(.+?)\s+do/g, 'while($1)');
    
    // If statements
    js = js.replace(/if\s+(.+?)\s+then/g, 'if($1)');
    js = js.replace(/\belseif\s+(.+?)\s+then/g, '} else if($1)');
    js = js.replace(/\belse\b/g, '} else {');
    
    // End statements
    js = js.replace(/\bend\b/g, '}');
    
    // Lua string concatenation
    js = js.replace(/\.\./g, '+');
    
    // Lua not equals
    js = js.replace(/~=/g, '!=');
    
    // Lua boolean operators
    js = js.replace(/\band\b/g, '&&');
    js = js.replace(/\bor\b/g, '||');
    js = js.replace(/\bnot\b/g, '!');
    
    // Math functions (math.floor -> Math.floor)
    js = js.replace(/math\.([a-z]+)/g, 'Math.$1');
    
    // Modulo operator
    js = js.replace(/\s+%\s+/g, ' % ');
    
    // Integer division
    js = js.replace(/\/\//g, '/');
    
    return js;
};

// =====================================================================
// USB Serial Port Management
// =====================================================================

VeraChat.prototype.ideRefreshPorts = async function() {
    const sel = document.getElementById('ideUsbPort');
    if (!sel) return;
    
    sel.innerHTML = '<option value="">Select a port...</option>';
    
    // Try Web Serial API
    if ('serial' in navigator) {
        try {
            const ports = await navigator.serial.getPorts();
            for (const p of ports) {
                const info = p.getInfo ? p.getInfo() : {};
                const vid = info.usbVendorId ? info.usbVendorId.toString(16).toUpperCase() : '';
                const pid = info.usbProductId ? info.usbProductId.toString(16).toUpperCase() : '';
                const label = vid ? `USB (VID:${vid} PID:${pid})` : 'USB Device';
                
                const opt = document.createElement('option');
                opt.value = JSON.stringify({ type: 'webserial', vid: info.usbVendorId, pid: info.usbProductId });
                opt.textContent = label;
                sel.appendChild(opt);
            }
        } catch(e) {
            console.warn('Web Serial enumeration failed:', e);
        }
    } else {
        this.ideLog('[WARN] Web Serial API not available. Use Chrome/Edge with HTTPS or localhost.');
    }
    
    // Try server-side ports
    try {
        const res = await fetch('http://llm.int:8888/api/execution/ports');
        if (res.ok) {
            const list = await res.json();
            for (const p of list) {
                const opt = document.createElement('option');
                opt.value = JSON.stringify({ type: 'server', device: p.device });
                opt.textContent = `${p.device} - ${p.description || 'Serial Port'}`;
                sel.appendChild(opt);
            }
        }
    } catch(e) {
        // Server not available or no /ports endpoint
    }
    
    if (sel.options.length === 1) {
        sel.innerHTML += '<option value="" disabled>No ports found</option>';
        this.ideLog('[INFO] No ports detected. Click "Connect USB" to request port access.');
    }
};

VeraChat.prototype.ideConnectUSB = async function() {
    if (!('serial' in navigator)) {
        this.ideLog('[ERROR] Web Serial API not available in this browser.');
        alert('Web Serial API not supported. Use Chrome/Edge with HTTPS or localhost.');
        return;
    }
    
    try {
        // Request port from user
        this.ideSerialPort = await navigator.serial.requestPort();
        
        // Open port
        await this.ideSerialPort.open({ baudRate: 115200 });
        
        this.ideLog('[USB] Connected to board — streaming serial data');
        
        // Start reading
        this.ideReadFromPort(this.ideSerialPort);
        
        // Try to auto-detect FQBN
        try {
            const info = this.ideSerialPort.getInfo ? this.ideSerialPort.getInfo() : {};
            if (info.usbVendorId || info.usbProductId) {
                const suggested = this.ideSuggestFQBN(info.usbVendorId, info.usbProductId);
                if (suggested) {
                    const fqbnField = document.getElementById('ideFqbn');
                    if (fqbnField) fqbnField.value = suggested;
                    this.ideLog(`[Auto-FQBN] Detected: ${suggested}`);
                }
            }
        } catch(e) {
            // Ignore auto-detect errors
        }
        
        // Refresh port list
        this.ideRefreshPorts();
        
    } catch(e) {
        this.ideLog('[USB] Connection failed: ' + e.message);
    }
};

VeraChat.prototype.ideReadFromPort = async function(serialPort) {
    if (!serialPort) return;
    
    try {
        this.ideSerialReader = serialPort.readable.getReader();
        
        while (true) {
            const { value, done } = await this.ideSerialReader.read();
            if (done) break;
            
            if (value) {
                const text = new TextDecoder().decode(value);
                // Split by lines for better formatting
                const lines = text.split(/\r?\n/);
                lines.forEach(line => {
                    if (line.trim()) this.ideLog('[HW] ' + line);
                });
            }
        }
        
        this.ideSerialReader.releaseLock();
    } catch(e) {
        this.ideLog('[USB] Read error: ' + e.message);
    }
};

VeraChat.prototype.ideAutoDetectFQBN = function() {
    const sel = document.getElementById('ideUsbPort');
    const fqbnField = document.getElementById('ideFqbn');
    
    if (!sel || !fqbnField) return;
    
    const portValue = sel.value;
    if (!portValue) {
        this.ideLog('[INFO] Select a port or connect USB first.');
        return;
    }
    
    try {
        const portData = JSON.parse(portValue);
        
        if (portData.type === 'webserial' && (portData.vid || portData.pid)) {
            const suggested = this.ideSuggestFQBN(portData.vid, portData.pid);
            if (suggested) {
                fqbnField.value = suggested;
                this.ideLog(`[Auto-FQBN] Detected: ${suggested}`);
            } else {
                this.ideLog('[Auto-FQBN] Could not determine FQBN from VID/PID.');
            }
        } else {
            // Fallback to board selector
            const boardType = document.getElementById('ideBoard')?.value || 'esp32';
            const defaultFQBNs = {
                esp32: "esp32:esp32:esp32",
                uno: "arduino:avr:uno"
            };
            fqbnField.value = defaultFQBNs[boardType] || '';
            this.ideLog(`[Auto-FQBN] Using default for ${boardType}: ${fqbnField.value}`);
        }
    } catch(e) {
        this.ideLog('[Auto-FQBN] Error: ' + e.message);
    }
};

VeraChat.prototype.ideSuggestFQBN = function(vid, pid) {
    // Convert to numbers if strings
    if (typeof vid === 'string') vid = parseInt(vid, 16);
    if (typeof pid === 'string') pid = parseInt(pid, 16);
    
    // Common VID/PID mappings
    const vendorMap = {
        0x10C4: 'esp32:esp32:esp32',  // Silicon Labs (common ESP32 USB chip)
        0x1A86: 'esp32:esp32:esp32',  // CH340 (common ESP32 USB chip)
        0x0403: 'arduino:avr:uno',    // FTDI (common Arduino)
        0x2341: 'arduino:avr:uno',    // Arduino official VID
        0x2A03: 'arduino:avr:uno',    // Arduino official VID (alternative)
    };
    
    if (vendorMap[vid]) {
        return vendorMap[vid];
    }
    
    // Fallback to board selector
    const boardType = document.getElementById('ideBoard')?.value || 'esp32';
    const defaultFQBNs = {
        esp32: "esp32:esp32:esp32",
        uno: "arduino:avr:uno"
    };
    
    return defaultFQBNs[boardType] || '';
};

VeraChat.prototype.ideFlashToBoard = async function(code) {
    const sel = document.getElementById('ideUsbPort');
    const fqbnField = document.getElementById('ideFqbn');
    
    if (!sel || !fqbnField) return;
    
    const portValue = sel.value;
    if (!portValue) {
        this.ideLog('[FLASH] Please select a port first.');
        alert('Select a port or connect USB before uploading.');
        return;
    }
    
    const fqbn = fqbnField.value.trim();
    if (!fqbn) {
        this.ideLog('[FLASH] FQBN required. Click "Auto-detect" or enter manually.');
        alert('FQBN required. Example: esp32:esp32:esp32');
        return;
    }
    
    this.ideLog('[FLASH] Starting compile and upload...');
    this.ideLog(`[FLASH] FQBN: ${fqbn}`);
    this.ideLog(`[FLASH] Port: ${portValue}`);
    
    try {
        const portData = JSON.parse(portValue);
        const devicePort = portData.device || portValue;
        
        const res = await fetch('http://llm.int:8888/api/execution/flash', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                code: code,
                fqbn: fqbn,
                port: devicePort
            })
        });
        
        if (!res.ok) {
            throw new Error(`HTTP ${res.status}: ${res.statusText}`);
        }
        
        const result = await res.json();
        
        if (result.error) {
            this.ideLog('[FLASH ERROR] ' + result.error);
            if (result.stderr) {
                this.ideLog('[STDERR] ' + result.stderr);
            }
        } else {
            this.ideLog('[FLASH SUCCESS] Upload complete!');
            if (result.stdout) {
                this.ideLog('[OUTPUT] ' + result.stdout);
            }
        }
    } catch(e) {
        this.ideLog('[FLASH ERROR] ' + e.message);
        this.ideLog('[INFO] Make sure backend server is running with /flash endpoint.');
    }
};

VeraChat.prototype.ideStartServerMonitor = function() {
    // Try WebSocket first, then SSE
    this.ideConnectWebSocket().catch(() => {
        this.ideConnectSSE();
    });
};

VeraChat.prototype.ideConnectWebSocket = async function() {
    if (this.ideWSSerial && this.ideWSSerial.readyState === WebSocket.OPEN) {
        this.ideLog('[Server Monitor] Already connected');
        return;
    }
    
    const host = window.location.origin.replace(/^http/, 'ws');
    const url = host + '/ws-serial';
    
    this.ideWSSerial = new WebSocket(url);
    
    this.ideWSSerial.onopen = () => {
        this.ideLog('[Server Monitor] Connected via WebSocket');
    };
    
    this.ideWSSerial.onmessage = (ev) => {
        this.ideLog('[SERVER] ' + ev.data);
    };
    
    this.ideWSSerial.onclose = () => {
        this.ideLog('[Server Monitor] Disconnected');
    };
    
    this.ideWSSerial.onerror = (e) => {
        throw new Error('WebSocket failed');
    };
};

VeraChat.prototype.ideConnectSSE = function() {
    if (this.ideSSESource) {
        this.ideLog('[Server Monitor] Already connected');
        return;
    }
    
    try {
        const url = '/serial-stream';
        this.ideSSESource = new EventSource(url);
        
        this.ideSSESource.onmessage = (ev) => {
            this.ideLog('[SERVER] ' + ev.data);
        };
        
        this.ideSSESource.onerror = () => {
            this.ideLog('[Server Monitor] SSE connection failed');
            this.ideSSESource = null;
        };
        
        this.ideLog('[Server Monitor] Connected via SSE');
    } catch(e) {
        this.ideLog('[Server Monitor] Not available: ' + e.message);
        this.ideLog('[INFO] Server monitor requires backend with /serial-stream endpoint.');
    }
};

// =====================================================================
// Jupyter Notebook Viewer Mode
// =====================================================================

VeraChat.prototype.initJupyterViewer = function() {
    const { content, controls } = this.canvas;
    
    const viewer = document.createElement('div');
    viewer.id = 'jupyter-viewer';
    viewer.style.cssText = 'height: 100%; overflow: auto;';
    content.appendChild(viewer);

    controls.innerHTML = `
        <input type="file" id="loadNotebook" accept=".ipynb" style="display: none;">
        <button id="loadNotebookBtn" class="panel-btn">📂 Load .ipynb</button>
        <button id="renderNotebook" class="panel-btn">🔄 Render</button>
        <button id="exportNotebookHtml" class="panel-btn">💾 Export HTML</button>
        <span id="nbStatus" style="margin-left: 12px; color: #94a3b8;"></span>
    `;

    const fileInput = controls.querySelector('#loadNotebook');
    const loadBtn = controls.querySelector('#loadNotebookBtn');
    const status = controls.querySelector('#nbStatus');

    loadBtn.addEventListener('click', () => fileInput.click());

    fileInput.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        
        try {
            const text = await file.text();
            const notebook = JSON.parse(text);
            this.canvas.data = notebook;
            this.canvas.persistentContent = text;
            status.textContent = `Loaded: ${file.name}`;
            this.renderJupyterNotebook(notebook, viewer);
        } catch(err) {
            alert('Failed to load notebook: ' + err.message);
        }
    });

    controls.querySelector('#renderNotebook').addEventListener('click', () => {
        if (this.canvas.data) {
            this.renderJupyterNotebook(this.canvas.data, viewer);
        }
    });

    controls.querySelector('#exportNotebookHtml').addEventListener('click', () => {
        if (this.canvas.data && viewer.innerHTML) {
            const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>Jupyter Notebook</title><style>body{font-family:sans-serif;max-width:900px;margin:20px auto;background:#fff;}.cell{border:1px solid #ddd;margin:10px 0;border-radius:4px;}.cell-input{background:#f7f7f7;padding:12px;border-bottom:1px solid #ddd;}.cell-output{padding:12px;}.cell-markdown{padding:12px;}code{background:#f4f4f4;padding:2px 4px;border-radius:3px;}pre{background:#f7f7f7;padding:10px;border-radius:4px;overflow-x:auto;}</style></head><body>${viewer.innerHTML}</body></html>`;
            this.downloadFile(html, 'notebook.html');
        }
    });

    viewer.innerHTML = `<div style="text-align: center; padding: 40px; color: #64748b;">Load a Jupyter notebook (.ipynb) to view it here</div>`;
};

VeraChat.prototype.renderJupyterNotebook = async function(notebook, container) {
    await this.loadPrism();
    await this.loadMarkdownLibrary();
    
    container.innerHTML = '';
    
    const header = document.createElement('div');
    header.style.cssText = `padding: 16px; background: var(--panel-bg); border-radius: 6px; margin-bottom: 16px; border: 1px solid #334155;`;
    header.innerHTML = `
        <div style="font-size: 18px; font-weight: bold; color: #60a5fa; margin-bottom: 8px;">📓 Jupyter Notebook</div>
        <div style="font-size: 13px; color: #94a3b8;">
            Format: ${notebook.nbformat}.${notebook.nbformat_minor} | 
            Kernel: ${notebook.metadata?.kernelspec?.display_name || 'Unknown'} |
            Cells: ${notebook.cells?.length || 0}
        </div>
    `;
    container.appendChild(header);

    if (!notebook.cells) {
        container.innerHTML += '<div style="padding: 20px; color: #ef4444;">Invalid notebook format</div>';
        return;
    }

    notebook.cells.forEach((cell, idx) => {
        const cellEl = document.createElement('div');
        cellEl.style.cssText = `margin-bottom: 12px; border: 1px solid #334155; border-radius: 6px; background: var(--panel-bg); overflow: hidden;`;

        const cellHeader = document.createElement('div');
        cellHeader.style.cssText = `padding: 6px 12px; background: #0f172a; font-size: 12px; color: #94a3b8; border-bottom: 1px solid #334155;`;
        cellHeader.textContent = `Cell ${idx + 1} [${cell.cell_type}]${cell.execution_count ? ` In[${cell.execution_count}]` : ''}`;
        cellEl.appendChild(cellHeader);

        const cellContent = document.createElement('div');
        cellContent.style.cssText = 'padding: 12px;';

        if (cell.cell_type === 'code') {
            const source = Array.isArray(cell.source) ? cell.source.join('') : cell.source;
            const pre = document.createElement('pre');
            pre.style.cssText = 'margin: 0 0 12px 0; background: #0f172a; padding: 12px; border-radius: 4px;';
            const code = document.createElement('code');
            code.className = 'language-python';
            code.textContent = source;
            pre.appendChild(code);
            cellContent.appendChild(pre);
            if (window.Prism) Prism.highlightElement(code);

            if (cell.outputs && cell.outputs.length > 0) {
                const outputDiv = document.createElement('div');
                outputDiv.style.cssText = `border-top: 1px solid #334155; padding-top: 12px; margin-top: 12px;`;
                
                cell.outputs.forEach(output => {
                    const outEl = document.createElement('div');
                    outEl.style.cssText = 'margin-bottom: 8px;';

                    if (output.output_type === 'stream') {
                        const text = Array.isArray(output.text) ? output.text.join('') : output.text;
                        outEl.innerHTML = `<pre style="margin:0;background:#0f172a;padding:8px;border-radius:4px;color:#10b981;"><code>${this._escapeHtml(text)}</code></pre>`;
                    } else if (output.output_type === 'execute_result' || output.output_type === 'display_data') {
                        if (output.data) {
                            if (output.data['text/html']) {
                                const html = Array.isArray(output.data['text/html']) ? output.data['text/html'].join('') : output.data['text/html'];
                                outEl.innerHTML = html;
                            } else if (output.data['image/png']) {
                                outEl.innerHTML = `<img src="data:image/png;base64,${output.data['image/png']}" style="max-width:100%;border-radius:4px;">`;
                            } else if (output.data['text/plain']) {
                                const text = Array.isArray(output.data['text/plain']) ? output.data['text/plain'].join('') : output.data['text/plain'];
                                outEl.innerHTML = `<pre style="margin:0;background:#0f172a;padding:8px;border-radius:4px;"><code>${this._escapeHtml(text)}</code></pre>`;
                            }
                        }
                    } else if (output.output_type === 'error') {
                        const traceback = output.traceback ? output.traceback.join('\n') : '';
                        outEl.innerHTML = `<pre style="margin:0;background:#450a0a;padding:8px;border-radius:4px;color:#fca5a5;"><code>${this._escapeHtml(traceback)}</code></pre>`;
                    }

                    outputDiv.appendChild(outEl);
                });

                cellContent.appendChild(outputDiv);
            }
        } else if (cell.cell_type === 'markdown') {
            const source = Array.isArray(cell.source) ? cell.source.join('') : cell.source;
            if (window.marked) {
                cellContent.innerHTML = marked.parse(source);
                cellContent.style.lineHeight = '1.6';
            } else {
                cellContent.textContent = source;
            }
        } else if (cell.cell_type === 'raw') {
            const source = Array.isArray(cell.source) ? cell.source.join('') : cell.source;
            cellContent.innerHTML = `<pre style="margin:0;background:#0f172a;padding:8px;border-radius:4px;"><code>${this._escapeHtml(source)}</code></pre>`;
        }

        cellEl.appendChild(cellContent);
        container.appendChild(cellEl);
    });
};

// =====================================================================
// Terminal Emulator Mode
// =====================================================================

VeraChat.prototype.initTerminal = function() {
    const { content, controls } = this.canvas;
    
    const terminal = document.createElement('div');
    terminal.id = 'canvas-terminal';
    terminal.style.cssText = `
        height: calc(100% - 60px); background: #0a0a0a; color: #00ff00;
        font-family: 'Courier New', monospace; padding: 12px; overflow-y: auto;
        border: 1px solid #334155; border-radius: 6px; white-space: pre-wrap; word-break: break-word;
    `;
    content.appendChild(terminal);

    const inputWrapper = document.createElement('div');
    inputWrapper.style.cssText = 'display: flex; gap: 8px; margin-top: 12px;';
    inputWrapper.innerHTML = `
        <span style="color: #00ff00;">$</span>
        <input type="text" id="terminalInput" style="flex: 1; background: #0a0a0a; color: #00ff00; border: 1px solid #334155; padding: 6px; border-radius: 4px; font-family: 'Courier New', monospace;">
    `;
    content.appendChild(inputWrapper);

    controls.innerHTML = `
        <button id="clearTerminal" class="panel-btn">🧹 Clear</button>
        <button id="terminalHelp" class="panel-btn">❓ Commands</button>
    `;

    const input = content.querySelector('#terminalInput');
    const output = terminal;

    this.terminalState = {
        history: [], historyIndex: -1, cwd: '/home/user',
        fs: {
            '/home/user': { type: 'dir', children: ['documents', 'downloads', 'projects'] },
            '/home/user/documents': { type: 'dir', children: ['notes.txt'] },
            '/home/user/downloads': { type: 'dir', children: [] },
            '/home/user/projects': { type: 'dir', children: ['app.js', 'README.md'] }
        }
    };

    const appendOutput = (text, isError = false) => {
        const line = document.createElement('div');
        line.style.color = isError ? '#ff4444' : '#00ff00';
        line.textContent = text;
        output.appendChild(line);
        output.scrollTop = output.scrollHeight;
    };

    const executeCommand = (cmd) => {
        appendOutput(`$ ${cmd}`);
        this.terminalState.history.push(cmd);
        this.terminalState.historyIndex = this.terminalState.history.length;

        const parts = cmd.trim().split(/\s+/);
        const command = parts[0];
        const args = parts.slice(1);

        switch(command) {
            case 'help':
                appendOutput('Available commands: ls, cd, pwd, echo, cat, clear, date, whoami, uname, help');
                break;
            case 'ls':
                const dir = args[0] || this.terminalState.cwd;
                const contents = this.terminalState.fs[dir];
                if (contents && contents.type === 'dir') {
                    appendOutput(contents.children.join('  '));
                } else {
                    appendOutput(`ls: cannot access '${dir}': No such file or directory`, true);
                }
                break;
            case 'pwd':
                appendOutput(this.terminalState.cwd);
                break;
            case 'cd':
                if (args[0] === '..') {
                    const parts = this.terminalState.cwd.split('/').filter(Boolean);
                    parts.pop();
                    this.terminalState.cwd = '/' + parts.join('/');
                } else if (args[0]) {
                    const newPath = args[0].startsWith('/') ? args[0] : `${this.terminalState.cwd}/${args[0]}`;
                    if (this.terminalState.fs[newPath] && this.terminalState.fs[newPath].type === 'dir') {
                        this.terminalState.cwd = newPath;
                    } else {
                        appendOutput(`cd: ${args[0]}: No such directory`, true);
                    }
                }
                break;
            case 'echo':
                appendOutput(args.join(' '));
                break;
            case 'cat':
                appendOutput(`cat: ${args[0]}: Mock file content would appear here`);
                break;
            case 'date':
                appendOutput(new Date().toString());
                break;
            case 'whoami':
                appendOutput('user');
                break;
            case 'uname':
                appendOutput('Linux canvas-terminal 5.15.0 #1 SMP x86_64 GNU/Linux');
                break;
            case 'clear':
                output.innerHTML = '';
                break;
            case '':
                break;
            default:
                appendOutput(`${command}: command not found`, true);
        }
    };

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            const cmd = input.value;
            if (cmd.trim()) executeCommand(cmd);
            input.value = '';
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            if (this.terminalState.historyIndex > 0) {
                this.terminalState.historyIndex--;
                input.value = this.terminalState.history[this.terminalState.historyIndex];
            }
        } else if (e.key === 'ArrowDown') {
            e.preventDefault();
            if (this.terminalState.historyIndex < this.terminalState.history.length - 1) {
                this.terminalState.historyIndex++;
                input.value = this.terminalState.history[this.terminalState.historyIndex];
            } else {
                this.terminalState.historyIndex = this.terminalState.history.length;
                input.value = '';
            }
        }
    });

    controls.querySelector('#clearTerminal').addEventListener('click', () => { output.innerHTML = ''; });
    controls.querySelector('#terminalHelp').addEventListener('click', () => {
        appendOutput('=== Mock Terminal Help ===');
        appendOutput('Available commands: ls, cd, pwd, echo, cat, clear, date, whoami, uname, help');
        appendOutput('Use arrow keys for command history');
    });

    appendOutput('Welcome to Canvas Terminal (Mock Mode)');
    appendOutput('Type "help" for available commands');
    appendOutput('');
};

// =====================================================================
// HTML/JS Preview Mode
// =====================================================================

VeraChat.prototype.initHTMLPreview = function() {
    const { content, controls } = this.canvas;
    
    const wrapper = document.createElement('div');
    wrapper.style.cssText = 'display: grid; grid-template-columns: 1fr 1fr; gap: 12px; height: 100%;';
    
    wrapper.innerHTML = `
        <div style="display: flex; flex-direction: column;">
            <div style="margin-bottom: 8px; font-weight: bold; color: #94a3b8;">HTML/CSS/JS</div>
            <textarea id="html-editor" style="flex: 1; resize: none; padding: 12px; border: 1px solid #334155; border-radius: 6px; background: var(--panel-bg); color: #f1f5f9; font-size: 14px; line-height: 1.5; font-family: inherit;"></textarea>
        </div>
        <div style="display: flex; flex-direction: column;">
            <div style="margin-bottom: 8px; font-weight: bold; color: #94a3b8;">Preview</div>
            <iframe id="html-preview" sandbox="allow-scripts allow-modals" style="flex: 1; border: 1px solid #334155; border-radius: 6px; background: white;"></iframe>
        </div>
    `;
    content.appendChild(wrapper);

    controls.innerHTML = `
        <button id="runPreview" class="panel-btn">▶️ Run</button>
        <button id="autoRunPreview" class="panel-btn">⚡ Auto-run</button>
        <button id="refreshPreview" class="panel-btn">🔄 Refresh</button>
    `;

    const editor = content.querySelector('#html-editor');
    const iframe = content.querySelector('#html-preview');
    let autoRun = false;

    const runPreview = () => { iframe.srcdoc = editor.value; };

    controls.querySelector('#runPreview').addEventListener('click', runPreview);
    controls.querySelector('#autoRunPreview').addEventListener('click', () => {
        autoRun = !autoRun;
        const btn = controls.querySelector('#autoRunPreview');
        btn.textContent = autoRun ? '⚡ Auto: ON' : '⚡ Auto: OFF';
        btn.style.background = autoRun ? '#10b981' : '';
    });
    controls.querySelector('#refreshPreview').addEventListener('click', () => {
        iframe.src = 'about:blank';
        setTimeout(runPreview, 100);
    });

    editor.addEventListener('input', () => { if (autoRun) runPreview(); });

    editor.value = '<!DOCTYPE html>\n<html>\n<head>\n  <title>Preview</title>\n</head>\n<body>\n  <h1>Hello World</h1>\n</body>\n</html>';
};

// =====================================================================
// JSON Viewer Mode
// =====================================================================

VeraChat.prototype.initJSONViewer = function() {
    const { content, controls } = this.canvas;
    
    const wrapper = document.createElement('div');
    wrapper.style.cssText = 'display: grid; grid-template-columns: 1fr 1fr; gap: 12px; height: 100%;';
    
    wrapper.innerHTML = `
        <div style="display: flex; flex-direction: column;">
            <div style="margin-bottom: 8px; font-weight: bold; color: #94a3b8;">JSON Input</div>
            <textarea id="json-editor" style="flex: 1; resize: none; padding: 12px; border: 1px solid #334155; border-radius: 6px; background: var(--panel-bg); color: #f1f5f9; font-size: 14px; line-height: 1.5; font-family: inherit;"></textarea>
        </div>
        <div style="display: flex; flex-direction: column;">
            <div style="margin-bottom: 8px; font-weight: bold; color: #94a3b8;">Formatted / Tree View</div>
            <div id="json-preview" style="flex: 1; border: 1px solid #334155; border-radius: 6px; background: var(--panel-bg); overflow: auto; padding: 12px;"></div>
        </div>
    `;
    content.appendChild(wrapper);

    controls.innerHTML = `
        <button id="parseJson" class="panel-btn">✨ Format</button>
        <button id="compactJson" class="panel-btn">📦 Compact</button>
        <button id="treeJson" class="panel-btn">🌳 Tree View</button>
        <button id="validateJson" class="panel-btn">✅ Validate</button>
        <button id="parseJsonInstances" class="panel-btn">🔍 Parse All</button>
    `;

    const editor = content.querySelector('#json-editor');
    const preview = content.querySelector('#json-preview');

    const parseAndFormat = () => {
        try {
            const parsed = JSON.parse(editor.value);
            preview.innerHTML = `<pre style="margin:0;"><code class="language-json">${this._escapeHtml(JSON.stringify(parsed, null, 2))}</code></pre>`;
            if (window.Prism) Prism.highlightElement(preview.querySelector('code'));
        } catch(e) {
            preview.innerHTML = `<div style="color: #ef4444;">Invalid JSON: ${e.message}</div>`;
        }
    };

    controls.querySelector('#parseJson').addEventListener('click', parseAndFormat);
    controls.querySelector('#compactJson').addEventListener('click', () => {
        try {
            const parsed = JSON.parse(editor.value);
            editor.value = JSON.stringify(parsed);
            parseAndFormat();
        } catch(e) { alert('Invalid JSON'); }
    });
    controls.querySelector('#treeJson').addEventListener('click', () => {
        try {
            const parsed = JSON.parse(editor.value);
            preview.innerHTML = this.createJSONTree(parsed);
        } catch(e) {
            preview.innerHTML = `<div style="color: #ef4444;">Invalid JSON: ${e.message}</div>`;
        }
    });
    controls.querySelector('#validateJson').addEventListener('click', () => {
        try {
            JSON.parse(editor.value);
            alert('✅ Valid JSON!');
        } catch(e) { alert('❌ Invalid JSON: ' + e.message); }
    });
    controls.querySelector('#parseJsonInstances').addEventListener('click', () => {
        this.canvas.persistentContent = editor.value;
        this.parseAllInstances();
    });
};

VeraChat.prototype.createJSONTree = function(obj, level = 0) {
    const indent = '&nbsp;&nbsp;'.repeat(level);
    let html = '';
    
    if (Array.isArray(obj)) {
        html += `${indent}<span style="color: #94a3b8;">[</span><br>`;
        obj.forEach((item, i) => {
            html += this.createJSONTree(item, level + 1);
            if (i < obj.length - 1) html += '<span style="color: #94a3b8;">,</span>';
            html += '<br>';
        });
        html += `${indent}<span style="color: #94a3b8;">]</span>`;
    } else if (typeof obj === 'object' && obj !== null) {
        html += `${indent}<span style="color: #94a3b8;">{</span><br>`;
        const entries = Object.entries(obj);
        entries.forEach(([key, value], i) => {
            html += `${indent}&nbsp;&nbsp;<span style="color: #60a5fa;">"${key}"</span>: `;
            if (typeof value === 'object') {
                html += '<br>' + this.createJSONTree(value, level + 2);
            } else {
                html += `<span style="color: ${typeof value === 'string' ? '#10b981' : '#fbbf24'};">${JSON.stringify(value)}</span>`;
            }
            if (i < entries.length - 1) html += '<span style="color: #94a3b8;">,</span>';
            html += '<br>';
        });
        html += `${indent}<span style="color: #94a3b8;">}</span>`;
    } else {
        html += `${indent}<span style="color: ${typeof obj === 'string' ? '#10b981' : '#fbbf24'};">${JSON.stringify(obj)}</span>`;
    }
    
    return html;
};

// =====================================================================
// Table Viewer Mode
// =====================================================================

VeraChat.prototype.initTableViewer = function() {
    const { content, controls } = this.canvas;
    
    content.innerHTML = `
        <div style="margin-bottom: 12px;">
            <div style="margin-bottom: 8px; font-weight: bold; color: #94a3b8;">CSV / TSV / JSON Data</div>
            <textarea id="table-data" placeholder="Paste CSV, TSV, or JSON array here..." style="width: 100%; height: 150px; resize: vertical; padding: 12px; border: 1px solid #334155; border-radius: 6px; background: var(--panel-bg); color: #f1f5f9; font-size: 14px; line-height: 1.5; font-family: inherit;"></textarea>
        </div>
        <div id="table-display" style="overflow: auto; border: 1px solid #334155; border-radius: 6px; background: var(--panel-bg);"></div>
    `;

    controls.innerHTML = `
        <select id="tableFormat" class="panel-btn">
            <option value="auto">Auto-detect</option>
            <option value="csv">CSV</option>
            <option value="tsv">TSV</option>
            <option value="json">JSON</option>
        </select>
        <button id="parseTable" class="panel-btn">📊 Parse</button>
        <button id="exportTableCsv" class="panel-btn">💾 Export CSV</button>
    `;

    const input = content.querySelector('#table-data');
    const display = content.querySelector('#table-display');
    let currentData = null;

    const parseData = () => {
        const format = controls.querySelector('#tableFormat').value;
        const text = input.value.trim();
        
        try {
            if (format === 'json' || (format === 'auto' && text.startsWith('['))) {
                currentData = JSON.parse(text);
            } else {
                const delimiter = format === 'tsv' ? '\t' : ',';
                const lines = text.split('\n');
                const headers = lines[0].split(delimiter);
                currentData = lines.slice(1).map(line => {
                    const values = line.split(delimiter);
                    return headers.reduce((obj, header, i) => {
                        obj[header.trim()] = values[i]?.trim() || '';
                        return obj;
                    }, {});
                });
            }
            renderTable(currentData);
        } catch(e) {
            display.innerHTML = `<div style="padding: 20px; color: #ef4444;">Parse error: ${e.message}</div>`;
        }
    };

    const renderTable = (data) => {
        if (!data || !data.length) return;
        
        const headers = Object.keys(data[0]);
        let html = '<table style="width: 100%; border-collapse: collapse; color: #e2e8f0;">';
        html += '<thead><tr>';
        headers.forEach(h => {
            html += `<th style="border: 1px solid #334155; padding: 8px; background: #0f172a; text-align: left;">${this._escapeHtml(h)}</th>`;
        });
        html += '</tr></thead><tbody>';
        
        data.forEach(row => {
            html += '<tr>';
            headers.forEach(h => {
                html += `<td style="border: 1px solid #334155; padding: 8px;">${this._escapeHtml(String(row[h] || ''))}</td>`;
            });
            html += '</tr>';
        });
        
        html += '</tbody></table>';
        display.innerHTML = html;
    };

    controls.querySelector('#parseTable').addEventListener('click', parseData);
    controls.querySelector('#exportTableCsv').addEventListener('click', () => {
        if (!currentData) return;
        const headers = Object.keys(currentData[0]);
        let csv = headers.join(',') + '\n';
        currentData.forEach(row => {
            csv += headers.map(h => `"${(row[h] || '').replace(/"/g, '""')}"`).join(',') + '\n';
        });
        this.downloadFile(csv, 'export.csv');
    });
};

// =====================================================================
// Diff Viewer Mode
// =====================================================================

VeraChat.prototype.initDiffViewer = function() {
    const { content, controls } = this.canvas;
    
    content.innerHTML = `
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; height: 100%;">
            <div style="display: flex; flex-direction: column;">
                <div style="margin-bottom: 8px; font-weight: bold; color: #94a3b8;">Original</div>
                <textarea id="diff-original" style="flex: 1; resize: none; padding: 12px; border: 1px solid #334155; border-radius: 6px; background: var(--panel-bg); color: #f1f5f9; font-size: 14px; line-height: 1.5; font-family: inherit;"></textarea>
            </div>
            <div style="display: flex; flex-direction: column;">
                <div style="margin-bottom: 8px; font-weight: bold; color: #94a3b8;">Modified</div>
                <textarea id="diff-modified" style="flex: 1; resize: none; padding: 12px; border: 1px solid #334155; border-radius: 6px; background: var(--panel-bg); color: #f1f5f9; font-size: 14px; line-height: 1.5; font-family: inherit;"></textarea>
            </div>
        </div>
        <div id="diff-result" style="margin-top: 12px; border: 1px solid #334155; border-radius: 6px; background: var(--panel-bg); padding: 12px; max-height: 200px; overflow: auto; display: none;"></div>
    `;

    controls.innerHTML = `
        <button id="computeDiff" class="panel-btn">🔍 Compare</button>
        <button id="clearDiff" class="panel-btn">🧹 Clear</button>
    `;

    const original = content.querySelector('#diff-original');
    const modified = content.querySelector('#diff-modified');
    const result = content.querySelector('#diff-result');

    controls.querySelector('#computeDiff').addEventListener('click', () => {
        const diff = this.simpleDiff(original.value, modified.value);
        result.innerHTML = diff;
        result.style.display = 'block';
    });

    controls.querySelector('#clearDiff').addEventListener('click', () => {
        original.value = '';
        modified.value = '';
        result.innerHTML = '';
        result.style.display = 'none';
    });
};

VeraChat.prototype.simpleDiff = function(text1, text2) {
    const lines1 = text1.split('\n');
    const lines2 = text2.split('\n');
    let html = '<pre style="margin: 0; font-family: monospace; line-height: 1.6;">';
    
    const maxLen = Math.max(lines1.length, lines2.length);
    for (let i = 0; i < maxLen; i++) {
        const line1 = lines1[i] || '';
        const line2 = lines2[i] || '';
        
        if (line1 === line2) {
            html += `<div style="color: #94a3b8;">${this._escapeHtml(line1)}</div>`;
        } else if (!line1) {
            html += `<div style="background: #14532d; color: #22c55e;">+ ${this._escapeHtml(line2)}</div>`;
        } else if (!line2) {
            html += `<div style="background: #450a0a; color: #ef4444;">- ${this._escapeHtml(line1)}</div>`;
        } else {
            html += `<div style="background: #450a0a; color: #ef4444;">- ${this._escapeHtml(line1)}</div>`;
            html += `<div style="background: #14532d; color: #22c55e;">+ ${this._escapeHtml(line2)}</div>`;
        }
    }
    
    html += '</pre>';
    return html;
};

// =====================================================================
// Diagram Viewer with Zoom and Pan
// =====================================================================

VeraChat.prototype.initDiagramViewer = function() {
    const { content, controls } = this.canvas;
    
    const wrapper = document.createElement('div');
    wrapper.style.cssText = 'display: grid; grid-template-columns: 1fr 1fr; gap: 12px; height: 100%;';
    
    wrapper.innerHTML = `
        <div style="display: flex; flex-direction: column;">
            <div style="margin-bottom: 8px; font-weight: bold; color: #94a3b8;">Mermaid Code</div>
            <textarea id="mermaid-editor" placeholder="graph TD
A[Start] --> B[End]" style="flex: 1; resize: none; padding: 12px; border: 1px solid #334155; border-radius: 6px; background: var(--panel-bg); color: #f1f5f9; font-size: 14px; line-height: 1.5; font-family: inherit;"></textarea>
        </div>
        <div style="display: flex; flex-direction: column;">
            <div style="margin-bottom: 8px; font-weight: bold; color: #94a3b8;">Diagram (Zoom/Pan Enabled)</div>
            <div id="mermaid-preview-wrapper" style="flex: 1; border: 1px solid #334155; border-radius: 6px; background: white; overflow: hidden; position: relative;">
                <div id="mermaid-preview" style="width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; transform-origin: center center; transition: transform 0.1s ease-out;"></div>
            </div>
        </div>
    `;
    content.appendChild(wrapper);

    controls.innerHTML = `
        <button id="renderDiagram" class="panel-btn">🎨 Render</button>
        <button id="zoomInDiagram" class="panel-btn">🔍+ Zoom In</button>
        <button id="zoomOutDiagram" class="panel-btn">🔍- Zoom Out</button>
        <button id="resetZoomDiagram" class="panel-btn">↺ Reset View</button>
        <button id="exportDiagramSvg" class="panel-btn">💾 Export SVG</button>
        <button id="diagramExamples" class="panel-btn">📚 Examples</button>
        <button id="parseDiagrams" class="panel-btn">🔍 Parse All</button>
    `;

    const editor = content.querySelector('#mermaid-editor');
    const preview = content.querySelector('#mermaid-preview');
    const wrapper_el = content.querySelector('#mermaid-preview-wrapper');
    
    // Zoom and pan state
    let scale = 1;
    let translateX = 0;
    let translateY = 0;
    let isDragging = false;
    let startX = 0;
    let startY = 0;

    const updateTransform = () => {
        preview.style.transform = `translate(${translateX}px, ${translateY}px) scale(${scale})`;
    };

    // Mouse wheel zoom
    wrapper_el.addEventListener('wheel', (e) => {
        e.preventDefault();
        const delta = e.deltaY > 0 ? 0.9 : 1.1;
        scale *= delta;
        scale = Math.max(0.1, Math.min(5, scale));
        updateTransform();
    });

    // Pan with mouse drag
    wrapper_el.addEventListener('mousedown', (e) => {
        if (e.button === 0) {
            isDragging = true;
            startX = e.clientX - translateX;
            startY = e.clientY - translateY;
            wrapper_el.style.cursor = 'grabbing';
        }
    });

    wrapper_el.addEventListener('mousemove', (e) => {
        if (isDragging) {
            translateX = e.clientX - startX;
            translateY = e.clientY - startY;
            updateTransform();
        }
    });

    wrapper_el.addEventListener('mouseup', () => {
        isDragging = false;
        wrapper_el.style.cursor = 'grab';
    });

    wrapper_el.addEventListener('mouseleave', () => {
        isDragging = false;
        wrapper_el.style.cursor = 'grab';
    });

    wrapper_el.style.cursor = 'grab';

    // Render button
    controls.querySelector('#renderDiagram').addEventListener('click', async () => {
        await this.loadMermaid();
        try {
            preview.innerHTML = `<div class="mermaid">${editor.value}</div>`;
            if (window.mermaid) {
                mermaid.init(undefined, preview.querySelector('.mermaid'));
            }
        } catch(e) {
            preview.innerHTML = `<div style="color: #ef4444; padding: 20px;">Diagram error: ${e.message}</div>`;
        }
    });

    // Zoom buttons
    controls.querySelector('#zoomInDiagram').addEventListener('click', () => {
        scale *= 1.2;
        scale = Math.min(5, scale);
        updateTransform();
    });

    controls.querySelector('#zoomOutDiagram').addEventListener('click', () => {
        scale *= 0.8;
        scale = Math.max(0.1, scale);
        updateTransform();
    });

    controls.querySelector('#resetZoomDiagram').addEventListener('click', () => {
        scale = 1;
        translateX = 0;
        translateY = 0;
        updateTransform();
    });

    // Export SVG
    controls.querySelector('#exportDiagramSvg').addEventListener('click', () => {
        const svg = preview.querySelector('svg');
        if (svg) {
            const svgData = new XMLSerializer().serializeToString(svg);
            this.downloadFile(svgData, 'diagram.svg');
        } else {
            alert('Render a diagram first');
        }
    });

    // Examples
    controls.querySelector('#diagramExamples').addEventListener('click', () => {
        const examples = `graph TD
    A[Start] --> B{Is it working?}
    B -->|Yes| C[Great!]
    B -->|No| D[Debug]

sequenceDiagram
    Alice->>John: Hello John!
    John-->>Alice: Hi Alice!

classDiagram
    Animal <|-- Dog
    Animal : +int age
    Dog : +bark()`;
        editor.value = examples;
    });

    // Parse all diagrams
    controls.querySelector('#parseDiagrams').addEventListener('click', () => {
        this.canvas.persistentContent = editor.value;
        this.parseAllInstances();
    });

    editor.value = this.canvas.persistentContent || 'graph TD\n    A[Start] --> B{Decision}\n    B -->|Yes| C[Success]\n    B -->|No| D[Try Again]';
};

// Keep all the other mode initializers from the original file...
// (Markdown, Jupyter, Terminal, Preview, JSON, Table, Diff)
// I'll include the key ones and helpers:

VeraChat.prototype.initMarkdownViewer = function() {
    const { content, controls } = this.canvas;
    
    const wrapper = document.createElement('div');
    wrapper.style.cssText = `display: grid; grid-template-columns: 1fr 1fr; gap: 12px; height: 100%;`;
    
    const editorPane = document.createElement('div');
    editorPane.style.cssText = `display: flex; flex-direction: column;`;
    editorPane.innerHTML = `
        <div style="margin-bottom: 8px; font-weight: bold; color: #94a3b8;">Markdown Source</div>
        <textarea id="md-editor" style="flex: 1; resize: none; padding: 12px; border: 1px solid #334155; border-radius: 6px; background: var(--panel-bg); color: #f1f5f9; font-size: 14px; line-height: 1.5; font-family: inherit;"></textarea>
    `;
    wrapper.appendChild(editorPane);
    
    const previewPane = document.createElement('div');
    previewPane.style.cssText = `display: flex; flex-direction: column;`;
    previewPane.innerHTML = `
        <div style="margin-bottom: 8px; font-weight: bold; color: #94a3b8;">Preview</div>
        <div id="md-preview" style="flex: 1; padding: 16px; border: 1px solid #334155; border-radius: 6px; background: var(--panel-bg); overflow: auto; line-height: 1.6;"></div>
    `;
    wrapper.appendChild(previewPane);
    
    content.appendChild(wrapper);

    controls.innerHTML = `
        <button id="renderMd" class="panel-btn">🔄 Render</button>
        <button id="autoRenderMd" class="panel-btn">⚡ Auto-render</button>
        <button id="exportMdHtml" class="panel-btn">💾 Export HTML</button>
        <button id="parseMd" class="panel-btn">🔍 Parse Sections</button>
    `;

    const editor = content.querySelector('#md-editor');
    const preview = content.querySelector('#md-preview');
    let autoRender = false;

    const renderMarkdown = async () => {
        const md = editor.value;
        await this.loadMarkdownLibrary();
        if (window.marked) {
            preview.innerHTML = marked.parse(md);
            preview.querySelectorAll('pre code').forEach(block => {
                if (window.Prism) Prism.highlightElement(block);
            });
        }
    };

    controls.querySelector('#renderMd').addEventListener('click', renderMarkdown);
    
    controls.querySelector('#autoRenderMd').addEventListener('click', () => {
        autoRender = !autoRender;
        const btn = controls.querySelector('#autoRenderMd');
        btn.textContent = autoRender ? '⚡ Auto: ON' : '⚡ Auto: OFF';
        btn.style.background = autoRender ? '#10b981' : '';
    });

    editor.addEventListener('input', () => {
        if (autoRender) renderMarkdown();
    });

    controls.querySelector('#exportMdHtml').addEventListener('click', async () => {
        await renderMarkdown();
        const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><style>body{font-family:sans-serif;max-width:800px;margin:40px auto;padding:20px;line-height:1.6;}code{background:#f4f4f4;padding:2px 6px;border-radius:3px;}pre{background:#f4f4f4;padding:12px;border-radius:6px;overflow-x:auto;}pre code{background:none;padding:0;}</style></head><body>${preview.innerHTML}</body></html>`;
        this.downloadFile(html, 'markdown-export.html');
    });

    controls.querySelector('#parseMd').addEventListener('click', () => {
        this.canvas.persistentContent = editor.value;
        this.parseAllInstances();
    });
};

// =====================================================================
// Helper Functions (from original)
// =====================================================================

VeraChat.prototype.clearCanvas = function() {
    if (!this.canvas) return;
    this.canvas.content.innerHTML = '';
    this.canvas.controls.innerHTML = '';
    if (this.canvas.monacoEditor) {
        this.canvas.monacoEditor.dispose();
        this.canvas.monacoEditor = null;
    }
    this.hideInstanceSelector();
};

VeraChat.prototype.toggleCanvasFullscreen = function() {
    if (!this.canvas) return;
    const root = this.canvas.root.parentElement;
    if (!document.fullscreenElement) {
        root.requestFullscreen?.();
    } else {
        document.exitFullscreen?.();
    }
};

VeraChat.prototype.getFileExtension = function(lang) {
    const exts = {
        javascript: '.js', python: '.py', html: '.html', css: '.css',
        json: '.json', markdown: '.md', sql: '.sql', bash: '.sh',
        c: '.c', cpp: '.cpp', rust: '.rs', go: '.go', arduino: '.ino',
        lua: '.lua', typescript: '.ts'
    };
    return exts[lang] || '.txt';
};

VeraChat.prototype.downloadFile = function(content, filename) {
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
};

VeraChat.prototype.loadMermaid = async function() {
    if (window.mermaid) return;
    return new Promise((resolve) => {
        const script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js';
        script.onload = () => {
            mermaid.initialize({ startOnLoad: false, theme: 'dark' });
            resolve();
        };
        document.head.appendChild(script);
    });
};

VeraChat.prototype.loadMarkdownLibrary = async function() {
    if (window.marked) return;
    return new Promise((resolve) => {
        const script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/npm/marked/marked.min.js';
        script.onload = () => resolve();
        document.head.appendChild(script);
    });
};

VeraChat.prototype.loadPrism = async function() {
    if (this._prismLoaded) return;
    if (this._prismLoading) return this._prismLoading;

    this._prismLoading = new Promise((resolve) => {
        const link = document.createElement("link");
        link.rel = "stylesheet";
        link.href = "https://unpkg.com/prismjs/themes/prism-tomorrow.css";
        document.head.appendChild(link);

        const core = document.createElement("script");
        core.src = "https://unpkg.com/prismjs/prism.js";
        core.onload = () => {
            const langs = ["javascript","python","json","markup","css","c","rust","sql","bash","lua"];
            let rem = langs.length;
            langs.forEach(l => {
                const s = document.createElement("script");
                s.src = `https://unpkg.com/prismjs/components/prism-${l}.min.js`;
                s.onload = s.onerror = () => { if (--rem === 0) { this._prismLoaded = true; resolve(); } };
                document.head.appendChild(s);
            });
        };
        document.head.appendChild(core);
    });

    return this._prismLoading;
};

VeraChat.prototype._escapeHtml = function(str) {
    if (str === undefined || str === null) return "";
    return String(str).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
};

// =====================================================================
// Message Integration
// =====================================================================

VeraChat.prototype.attachCanvasButtonsToMessage = function(messageEl, language, code, messageId=null) {
    if (!messageEl) return;
    if (messageEl.querySelector(".canvas-actions")) return;

    const actions = document.createElement("div");
    actions.className = "canvas-actions";
    actions.style.marginTop = "6px";
    actions.style.display = "flex";
    actions.style.gap = "6px";

    const showBtn = document.createElement("button");
    showBtn.className = "panel-btn";
    showBtn.textContent = "📋 Open in Canvas";
    showBtn.onclick = () => {
        const mode = this.detectCanvasMode(language, code);
        const modeSelector = document.querySelector('#canvasMode');
        if (modeSelector) modeSelector.value = mode;
        
        this.canvas.persistentContent = code;
        this.switchCanvasMode(mode);
        
        const canvasTab = document.querySelector('[data-tab="canvas"]');
        if (canvasTab) canvasTab.click();
    };
    actions.appendChild(showBtn);

    messageEl.appendChild(actions);
};

VeraChat.prototype.detectCanvasMode = function(language, code) {
    if (!language) language = this.detectLanguage(code);
    
    if (language === 'markdown' || language === 'md') return 'markdown';
    if (code.includes('"nbformat"') || code.includes('"cells"')) return 'jupyter';
    if (language === 'html' || language === 'css') return 'preview';
    if (language === 'json') return 'json';
    if (language === 'mermaid' || code.includes('graph ') || code.includes('sequenceDiagram')) return 'diagram';
    if (code.includes('function TIC') || code.includes('-- script:') || code.includes('-- title:')) return 'tic80';
    if (language === 'arduino' || code.includes('void setup()') || code.includes('void loop()')) return 'embedded-ide';
    return 'code';
};

VeraChat.prototype.detectLanguage = function(code) {
    if (code.trim().startsWith('{') || code.trim().startsWith('[')) return 'json';
    if (/^\s*(import|def|print|class|from)\s/.test(code)) return 'python';
    if (/<[a-z][\s\S]*>/i.test(code)) return 'html';
    if (code.includes('function') || code.includes('=>') || code.includes('const ')) return 'javascript';
    if (code.includes('void setup()') || code.includes('void loop()')) return 'arduino';
    if (code.includes('#include') || code.includes('int main')) return 'cpp';
    if (code.includes('SELECT') || code.includes('FROM')) return 'sql';
    return 'plaintext';
};

})();