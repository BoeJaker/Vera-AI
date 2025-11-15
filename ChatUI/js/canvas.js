<<<<<<< HEAD

(() => {
// --------------------- Canvas integration for VeraChat ---------------------
VeraChat.prototype.initCanvasTab = function () {
    // Try to locate the canvas tab container
=======
(() => {
// =====================================================================
// Enhanced Canvas Integration for VeraChat
// Supports: Jupyter Notebooks, Markdown, Terminal, Code, and more
// =====================================================================

VeraChat.prototype.initCanvasTab = function () {
>>>>>>> dev-vera-ollama-fixed
    const root = document.querySelector('#tab-canvas');
    if (!root) {
        console.warn('Canvas tab container not found');
        return;
    }

<<<<<<< HEAD
    // Clear any previous content
    root.innerHTML = '';

    // Create container
=======
    root.innerHTML = '';

    // Main container
>>>>>>> dev-vera-ollama-fixed
    const container = document.createElement('div');
    container.style.cssText = `
        display: flex;
        flex-direction: column;
        height: 100%;
        overflow: hidden;
        background: #0f172a;
        color: #e2e8f0;
<<<<<<< HEAD
        border-radius: 8px;
        padding: 16px;
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
    `;

    // Header
    const header = document.createElement('div');
    header.textContent = '🧩 Canvas Playground';
    header.style.cssText = `
        font-size: 18px;
        margin-bottom: 12px;
        color: #60a5fa;
    `;
    container.appendChild(header);

    // Textarea for code input
    const editor = document.createElement('textarea');
    editor.placeholder = 'Paste or write code here...';
    editor.style.cssText = `
        flex: 1;
        width: 100%;
=======
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
    `;

    // Header with mode selector
    const header = document.createElement('div');
    header.style.cssText = `
        padding: 12px 16px;
        background: #1e293b;
        border-bottom: 1px solid #334155;
        display: flex;
        align-items: center;
        gap: 12px;
        flex-shrink: 0;
    `;
    header.innerHTML = `
        <span style="font-size: 18px; color: #60a5fa;">🧩 Canvas</span>
        <select id="canvasMode" class="panel-btn" style="padding: 6px 12px;">
            <option value="code">Code Editor</option>
            <option value="markdown">Markdown</option>
            <option value="jupyter">Jupyter Notebook</option>
            <option value="terminal">Terminal</option>
            <option value="preview">HTML/JS Preview</option>
            <option value="json">JSON Viewer</option>
            <option value="diagram">Diagram (Mermaid)</option>
            <option value="table">Data Table</option>
            <option value="diff">Diff Viewer</option>
        </select>
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
        background: #1e293b;
        border-top: 1px solid #334155;
        display: flex;
        gap: 8px;
        flex-shrink: 0;
    `;
    container.appendChild(controls);

    root.appendChild(container);

    // Store references
    this.canvas = {
        root: container,
        content,
        controls,
        mode: 'code',
        data: null
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

    // Initialize with code editor mode
    this.switchCanvasMode('code');
};

// =====================================================================
// Mode Switching
// =====================================================================

VeraChat.prototype.switchCanvasMode = function(mode) {
    if (!this.canvas) this.initCanvasTab();
    
    this.canvas.mode = mode;
    this.clearCanvas();
    
    switch(mode) {
        case 'code':
            this.initCodeEditor();
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
};

// =====================================================================
// Code Editor Mode
// =====================================================================

VeraChat.prototype.initCodeEditor = function() {
    const { content, controls } = this.canvas;
    
    // Editor
    const editor = document.createElement('textarea');
    editor.id = 'canvas-editor';
    editor.placeholder = 'Paste or write code here...';
    editor.style.cssText = `
        width: 100%;
        height: calc(100% - 60px);
>>>>>>> dev-vera-ollama-fixed
        resize: none;
        padding: 12px;
        border: 1px solid #334155;
        border-radius: 6px;
        background: #1e293b;
        color: #f1f5f9;
        font-size: 14px;
        line-height: 1.5;
        font-family: inherit;
    `;
<<<<<<< HEAD
    container.appendChild(editor);

    // Preview area
    const preview = document.createElement('pre');
    preview.className = 'canvas-preview hljs';
    preview.style.cssText = `
        flex: 1;
        overflow-y: auto;
        background: #1e293b;
        border-radius: 6px;
        margin-top: 12px;
        padding: 12px;
        white-space: pre-wrap;
        word-break: break-word;
    `;
    container.appendChild(preview);

    // Control bar
    const controls = document.createElement('div');
    controls.style.cssText = `
        margin-top: 12px;
        display: flex;
        gap: 8px;
        justify-content: flex-end;
    `;
    controls.innerHTML = `
        <button id="runCanvasCode" class="panel-btn">▶️ Run</button>
        <button id="formatCanvasJSON" class="panel-btn">🧾 Format JSON</button>
        <button id="clearCanvas" class="panel-btn">🧹 Clear</button>
    `;
    container.appendChild(controls);

    // Append to root
    root.appendChild(container);

    // === Logic ===
    const runBtn = container.querySelector('#runCanvasCode');
    const formatBtn = container.querySelector('#formatCanvasJSON');
    const clearBtn = container.querySelector('#clearCanvas');

    // Handle syntax highlighting dynamically
    const updatePreview = () => {
        const code = editor.value;
        const lang = detectLanguage(code);
        preview.innerHTML = `<code class="${lang}">${escapeHTML(code)}</code>`;
        if (window.hljs) hljs.highlightElement(preview.querySelector('code'));
    };

    runBtn.onclick = updatePreview;
    clearBtn.onclick = () => {
        editor.value = '';
        preview.innerHTML = '';
    };

    formatBtn.onclick = () => {
        try {
            const json = JSON.parse(editor.value);
            editor.value = JSON.stringify(json, null, 2);
            updatePreview();
        } catch {
            alert('Invalid JSON!');
        }
    };

    updatePreview();

    // Helper: Simple language detection
    function detectLanguage(code) {
        if (code.trim().startsWith('{')) return 'json';
        if (/^\s*(import|def|print|class)\s/.test(code)) return 'python';
        if (/<[a-z][\s\S]*>/i.test(code)) return 'html';
        if (code.includes('function') || code.includes('=>')) return 'javascript';
        if (code.includes('#include') || code.includes('int main')) return 'cpp';
        return 'plaintext';
    }

    // Helper: Escape HTML
    function escapeHTML(str) {
        return str.replace(/[&<>'"]/g, tag => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
        }[tag]));
    }
};

// detect code fence or raw JSON
VeraChat.prototype._detectCanvasBlock = function(text) {
  if (!text) return null;
  // markdown fence
  const fenceMatch = text.match(/```([\w+-]*)\n([\s\S]*?)\n```/);
  if (fenceMatch) {
    const lang = (fenceMatch[1] || "text").toLowerCase();
    return { lang, code: fenceMatch[2] };
  }
  // raw JSON
  try {
    JSON.parse(text);
    return { lang: "json", code: text };
  } catch (e) {}
  return null;
};

// lazy-load Prism and language components
VeraChat.prototype._loadPrism = async function() {
  if (this._prismLoaded) return;
  if (this._prismLoading) return this._prismLoading;

  this._prismLoading = new Promise((resolve, reject) => {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "https://unpkg.com/prismjs/themes/prism-tomorrow.css";
    document.head.appendChild(link);

    const core = document.createElement("script");
    core.src = "https://unpkg.com/prismjs/prism.js";
    core.onload = () => {
      const langs = ["javascript","python","json","markup","css","c","rust"];
      let rem = langs.length;
      langs.forEach(l => {
        const s = document.createElement("script");
        s.src = `https://unpkg.com/prismjs/components/prism-${l}.min.js`;
        s.onload = () => { if (--rem === 0) { this._prismLoaded = true; resolve(); } };
        s.onerror = () => { if (--rem === 0) { this._prismLoaded = true; resolve(); } };
        document.head.appendChild(s);
      });
    };
    core.onerror = (e) => reject(e);
    document.head.appendChild(core);
  });

  return this._prismLoading;
};

// clear the canvas preview
VeraChat.prototype.clearCanvas = function() {
  if (!this.canvasPreview) this.canvasPreview = document.getElementById("tab-canvas-preview");
  if (this.canvasPreview) this.canvasPreview.innerHTML = "";
};

// show plain text as code
VeraChat.prototype.renderTextAsCode = async function(text) {
  await this._loadPrism();
  this.clearCanvas();
  const pre = document.createElement("pre");
  const codeEl = document.createElement("code");
  codeEl.className = "language-text";
  codeEl.textContent = text;
  pre.appendChild(codeEl);
  this.canvasPreview.appendChild(pre);
  if (window.Prism) Prism.highlightElement(codeEl);
};

// primary renderer
VeraChat.prototype.renderCanvasBlock = async function(language, code) {
  if (!this.canvasPreview) this.initCanvasTab();
  await this._loadPrism();

  language = (language || "text").toLowerCase();
  this.clearCanvas();

  // HTML / CSS / JS preview sandboxed
  if (["html","markup","css","js","javascript"].includes(language)) {
    const iframe = document.createElement("iframe");
    iframe.style.width = "100%";
    iframe.style.height = "480px";
    iframe.style.border = "1px solid #333";
    // sandbox restricts capabilities; allow-scripts so small examples can run
    iframe.setAttribute("sandbox", "allow-scripts allow-modals");
    if (language === "css") {
      iframe.srcdoc = `<html><head><style>${this._escapeHtml(code)}</style></head><body><div style="padding:12px;">CSS preview</div></body></html>`;
    } else if (language === "js" || language === "javascript") {
      iframe.srcdoc = `<html><head></head><body><div id="root" style="padding:12px;"></div><script>try{${code}}catch(e){document.body.innerText='JS error: '+e}</script></body></html>`;
    } else {
      // html/markup
      iframe.srcdoc = code;
    }
    this.canvasPreview.appendChild(iframe);

    // show source below
    const srcWrap = document.createElement("div");
    srcWrap.style.marginTop = "8px";
    srcWrap.innerHTML = `<details open><summary>Source (${language})</summary><pre><code class="language-${language}"></code></pre></details>`;
    srcWrap.querySelector("code").textContent = code;
    this.canvasPreview.appendChild(srcWrap);
    if (window.Prism) Prism.highlightElement(srcWrap.querySelector("code"));
    return;
  }

  // JSON view: raw / pretty / cards
  if (language === "json") {
    this.clearCanvas();
    let parsed = null;
    try { parsed = JSON.parse(code); } catch (e) { /* invalid JSON */ }

    const toolbar = document.createElement("div");
    toolbar.style.display = "flex";
    toolbar.style.gap = "6px";
    toolbar.style.marginBottom = "6px";
    toolbar.innerHTML = `<button id="jsonRawBtn" class="panel-btn">Raw</button><button id="jsonPrettyBtn" class="panel-btn">Pretty</button><button id="jsonCardsBtn" class="panel-btn">Cards</button> <span style="opacity:.8;margin-left:6px">${parsed ? "Parsed JSON" : "Invalid JSON"}</span>`;
    this.canvasPreview.appendChild(toolbar);

    const display = document.createElement("div");
    display.style.minHeight = "100px";
    this.canvasPreview.appendChild(display);

    const renderRaw = () => {
      display.innerHTML = `<pre><code class="language-json"></code></pre>`;
      display.querySelector("code").textContent = code;
      if (window.Prism) Prism.highlightElement(display.querySelector("code"));
    };

    const renderPretty = () => {
      if (!parsed) return renderRaw();
      display.innerHTML = `<pre><code class="language-json"></code></pre>`;
      display.querySelector("code").textContent = JSON.stringify(parsed, null, 2);
      if (window.Prism) Prism.highlightElement(display.querySelector("code"));
    };

    const renderCards = () => {
      if (!parsed || typeof parsed !== "object") return renderPretty();
      display.innerHTML = "";
      const grid = document.createElement("div");
      grid.style.display = "grid";
      grid.style.gridTemplateColumns = "repeat(auto-fill,minmax(220px,1fr))";
      grid.style.gap = "8px";

      if (Array.isArray(parsed)) {
        parsed.forEach((item, idx) => {
          const card = document.createElement("div");
          card.style.background = "#0f172a";
          card.style.border = "1px solid #24303f";
          card.style.padding = "8px";
          card.style.borderRadius = "6px";
          card.innerHTML = `<strong>#${idx}</strong><pre style="white-space:pre-wrap;margin:6px 0 0 0;color:#cbd5e1">${this._escapeHtml(JSON.stringify(item, null, 2))}</pre>`;
          grid.appendChild(card);
        });
      } else {
        Object.entries(parsed).forEach(([k,v]) => {
          const card = document.createElement("div");
          card.style.background = "#0f172a";
          card.style.border = "1px solid #24303f";
          card.style.padding = "8px";
          card.style.borderRadius = "6px";
          card.innerHTML = `<strong>${this._escapeHtml(k)}</strong><div style="font-size:12px;margin-top:6px;white-space:pre-wrap;color:#cbd5e1">${this._escapeHtml(JSON.stringify(v, null, 2))}</div>`;
          grid.appendChild(card);
        });
      }
      display.appendChild(grid);
    };

    toolbar.querySelector("#jsonRawBtn").addEventListener("click", renderRaw);
    toolbar.querySelector("#jsonPrettyBtn").addEventListener("click", renderPretty);
    toolbar.querySelector("#jsonCardsBtn").addEventListener("click", renderCards);

    (parsed ? renderCards : renderRaw)();
    return;
  }

  // Fallback: syntax-highlighted code
  const pre = document.createElement("pre");
  const codeEl = document.createElement("code");
  codeEl.className = `language-${language}`;
  codeEl.textContent = code;
  pre.appendChild(codeEl);
  this.canvasPreview.appendChild(pre);
  if (window.Prism) Prism.highlightElement(codeEl);
};

// helper to attach buttons beneath a message element (call after rendering a message)
VeraChat.prototype.attachCanvasButtonsToMessage = function(messageEl, language, code, messageId=null) {
  if (!messageEl) return;
  // prevent duplicates
  if (messageEl.querySelector(".canvas-actions")) return;

  const actions = document.createElement("div");
  actions.className = "canvas-actions";
  actions.style.marginTop = "6px";
  actions.style.display = "flex";
  actions.style.gap = "6px";

  const showBtn = document.createElement("button");
  showBtn.className = "panel-btn";
  showBtn.textContent = "Show in Canvas";
  showBtn.onclick = () => this.renderCanvasBlock(language, code);
  actions.appendChild(showBtn);

  const saveBtn = document.createElement("button");
  saveBtn.className = "panel-btn";
  saveBtn.textContent = "Save to Notebook";
  saveBtn.onclick = async () => {
    // prefer using your captureMessageAsNote if messageId exists
    try {
      if (messageId && typeof this.captureMessageAsNote === "function") {
        await this.captureMessageAsNote(messageId);
        saveBtn.textContent = "Saved";
        setTimeout(()=>saveBtn.textContent = "Save to Notebook", 1200);
        return;
      }
      // otherwise create simple note entry using existing createNote/createNotebook if needed
      if (this.sessionId && typeof this.createNote === "function" && this.currentNotebook) {
        // create note in current notebook with this code as content
        const title = `Snippet ${new Date().toLocaleString()}`;
        // temporary approach: create via fetch directly or leverage your createNote API
        const resp = await fetch(`http://llm.int:8888/api/notebooks/${this.sessionId}/${this.currentNotebook.id}/notes/create`, {
          method: "POST",
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({ title, content: code })
        });
        if (resp.ok) {
          saveBtn.textContent = "Saved";
          setTimeout(()=>saveBtn.textContent = "Save to Notebook", 1200);
        } else {
          console.error("Failed saving snippet to notebook");
        }
        return;
      }

      // fallback: save into localStorage
      const key = "vera-canvas-snippets";
      const arr = JSON.parse(localStorage.getItem(key) || "[]");
      arr.push({ language, code, saved_at: new Date().toISOString() });
      localStorage.setItem(key, JSON.stringify(arr));
      saveBtn.textContent = "Saved";
      setTimeout(()=>saveBtn.textContent = "Save to Notebook", 1200);
    } catch (err) {
      console.error("Save to notebook failed", err);
    }
  };
  actions.appendChild(saveBtn);

  messageEl.appendChild(actions);
};

// convenience wrapper to render codeblock string detected earlier
VeraChat.prototype.showCodeBlockInCanvas = function(markdownBlock, messageEl=null, messageId=null) {
  // markdownBlock should be {lang, code}
  if (!markdownBlock) return;
  this.attachCanvasButtonsToMessage(messageEl, markdownBlock.lang, markdownBlock.code, messageId);
  // optionally auto-open in canvas
  this.renderCanvasBlock(markdownBlock.lang, markdownBlock.code);
};

// small helper
VeraChat.prototype._escapeHtml = function(str) {
  if (str === undefined || str === null) return "";
  return String(str).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
};

// --------------------- End Canvas integration ---------------------
=======
    content.appendChild(editor);

    // Preview area
    const preview = document.createElement('div');
    preview.id = 'code-preview';
    preview.style.cssText = `
        margin-top: 12px;
        background: #1e293b;
        border-radius: 6px;
        padding: 12px;
        border: 1px solid #334155;
        max-height: 300px;
        overflow: auto;
    `;
    content.appendChild(preview);

    // Controls
    controls.innerHTML = `
        <select id="codeLang" class="panel-btn">
            <option value="auto">Auto-detect</option>
            <option value="javascript">JavaScript</option>
            <option value="python">Python</option>
            <option value="html">HTML</option>
            <option value="css">CSS</option>
            <option value="json">JSON</option>
            <option value="markdown">Markdown</option>
            <option value="sql">SQL</option>
            <option value="bash">Bash</option>
            <option value="c">C</option>
            <option value="cpp">C++</option>
            <option value="rust">Rust</option>
            <option value="go">Go</option>
        </select>
        <button id="runCode" class="panel-btn">▶️ Highlight</button>
        <button id="formatCode" class="panel-btn">✨ Format</button>
        <button id="copyCode" class="panel-btn">📋 Copy</button>
        <button id="downloadCode" class="panel-btn">💾 Download</button>
    `;

    // Event handlers
    controls.querySelector('#runCode').addEventListener('click', async () => {
        const code = editor.value;
        const lang = controls.querySelector('#codeLang').value;
        await this.highlightCode(code, lang === 'auto' ? null : lang, preview);
    });

    controls.querySelector('#formatCode').addEventListener('click', () => {
        const lang = controls.querySelector('#codeLang').value;
        if (lang === 'json') {
            try {
                const parsed = JSON.parse(editor.value);
                editor.value = JSON.stringify(parsed, null, 2);
            } catch(e) {
                alert('Invalid JSON');
            }
        } else if (lang === 'javascript') {
            // Basic JS formatting
            editor.value = this.formatJS(editor.value);
        }
    });

    controls.querySelector('#copyCode').addEventListener('click', () => {
        navigator.clipboard.writeText(editor.value);
        const btn = controls.querySelector('#copyCode');
        const orig = btn.textContent;
        btn.textContent = '✅ Copied';
        setTimeout(() => btn.textContent = orig, 1500);
    });

    controls.querySelector('#downloadCode').addEventListener('click', () => {
        const lang = controls.querySelector('#codeLang').value;
        const ext = this.getFileExtension(lang);
        this.downloadFile(editor.value, `code${ext}`);
    });
};

// =====================================================================
// Markdown Viewer Mode
// =====================================================================

VeraChat.prototype.initMarkdownViewer = function() {
    const { content, controls } = this.canvas;
    
    // Split view: editor and preview
    const wrapper = document.createElement('div');
    wrapper.style.cssText = `
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 12px;
        height: 100%;
    `;
    
    // Editor
    const editorPane = document.createElement('div');
    editorPane.style.cssText = `display: flex; flex-direction: column;`;
    editorPane.innerHTML = `
        <div style="margin-bottom: 8px; font-weight: bold; color: #94a3b8;">Markdown Source</div>
        <textarea id="md-editor" style="flex: 1; resize: none; padding: 12px; border: 1px solid #334155; border-radius: 6px; background: #1e293b; color: #f1f5f9; font-size: 14px; line-height: 1.5; font-family: inherit;"></textarea>
    `;
    wrapper.appendChild(editorPane);
    
    // Preview
    const previewPane = document.createElement('div');
    previewPane.style.cssText = `display: flex; flex-direction: column;`;
    previewPane.innerHTML = `
        <div style="margin-bottom: 8px; font-weight: bold; color: #94a3b8;">Preview</div>
        <div id="md-preview" style="flex: 1; padding: 16px; border: 1px solid #334155; border-radius: 6px; background: #1e293b; overflow: auto; line-height: 1.6;"></div>
    `;
    wrapper.appendChild(previewPane);
    
    content.appendChild(wrapper);

    // Controls
    controls.innerHTML = `
        <button id="renderMd" class="panel-btn">🔄 Render</button>
        <button id="autoRenderMd" class="panel-btn">⚡ Auto-render</button>
        <button id="exportMdHtml" class="panel-btn">💾 Export HTML</button>
        <button id="exportMdPdf" class="panel-btn">📄 Export PDF</button>
    `;

    const editor = content.querySelector('#md-editor');
    const preview = content.querySelector('#md-preview');
    let autoRender = false;

    const renderMarkdown = async () => {
        const md = editor.value;
        await this.loadMarkdownLibrary();
        if (window.marked) {
            preview.innerHTML = marked.parse(md);
            // Apply syntax highlighting to code blocks
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

    controls.querySelector('#exportMdPdf').addEventListener('click', () => {
        alert('PDF export requires server-side rendering. Use the HTML export and convert with a browser or tool.');
    });
};

// =====================================================================
// Jupyter Notebook Viewer Mode
// =====================================================================

VeraChat.prototype.initJupyterViewer = function() {
    const { content, controls } = this.canvas;
    
    // Notebook viewer
    const viewer = document.createElement('div');
    viewer.id = 'jupyter-viewer';
    viewer.style.cssText = `
        height: 100%;
        overflow: auto;
    `;
    content.appendChild(viewer);

    // Controls
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
    
    // Notebook metadata
    const header = document.createElement('div');
    header.style.cssText = `
        padding: 16px;
        background: #1e293b;
        border-radius: 6px;
        margin-bottom: 16px;
        border: 1px solid #334155;
    `;
    header.innerHTML = `
        <div style="font-size: 18px; font-weight: bold; color: #60a5fa; margin-bottom: 8px;">
            📓 Jupyter Notebook
        </div>
        <div style="font-size: 13px; color: #94a3b8;">
            Format: ${notebook.nbformat}.${notebook.nbformat_minor} | 
            Kernel: ${notebook.metadata?.kernelspec?.display_name || 'Unknown'} |
            Cells: ${notebook.cells?.length || 0}
        </div>
    `;
    container.appendChild(header);

    // Render cells
    if (!notebook.cells) {
        container.innerHTML += '<div style="padding: 20px; color: #ef4444;">Invalid notebook format</div>';
        return;
    }

    notebook.cells.forEach((cell, idx) => {
        const cellEl = document.createElement('div');
        cellEl.style.cssText = `
            margin-bottom: 12px;
            border: 1px solid #334155;
            border-radius: 6px;
            background: #1e293b;
            overflow: hidden;
        `;

        // Cell header
        const cellHeader = document.createElement('div');
        cellHeader.style.cssText = `
            padding: 6px 12px;
            background: #0f172a;
            font-size: 12px;
            color: #94a3b8;
            border-bottom: 1px solid #334155;
        `;
        cellHeader.textContent = `Cell ${idx + 1} [${cell.cell_type}]${cell.execution_count ? ` In[${cell.execution_count}]` : ''}`;
        cellEl.appendChild(cellHeader);

        // Cell content
        const cellContent = document.createElement('div');
        cellContent.style.cssText = 'padding: 12px;';

        if (cell.cell_type === 'code') {
            // Source code
            const source = Array.isArray(cell.source) ? cell.source.join('') : cell.source;
            const pre = document.createElement('pre');
            pre.style.cssText = 'margin: 0 0 12px 0; background: #0f172a; padding: 12px; border-radius: 4px;';
            const code = document.createElement('code');
            code.className = 'language-python';
            code.textContent = source;
            pre.appendChild(code);
            cellContent.appendChild(pre);
            if (window.Prism) Prism.highlightElement(code);

            // Outputs
            if (cell.outputs && cell.outputs.length > 0) {
                const outputDiv = document.createElement('div');
                outputDiv.style.cssText = `
                    border-top: 1px solid #334155;
                    padding-top: 12px;
                    margin-top: 12px;
                `;
                
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
    
    // Terminal output area
    const terminal = document.createElement('div');
    terminal.id = 'canvas-terminal';
    terminal.style.cssText = `
        height: calc(100% - 60px);
        background: #0a0a0a;
        color: #00ff00;
        font-family: 'Courier New', monospace;
        padding: 12px;
        overflow-y: auto;
        border: 1px solid #334155;
        border-radius: 6px;
        white-space: pre-wrap;
        word-break: break-word;
    `;
    content.appendChild(terminal);

    // Command input
    const inputWrapper = document.createElement('div');
    inputWrapper.style.cssText = `
        display: flex;
        gap: 8px;
        margin-top: 12px;
    `;
    inputWrapper.innerHTML = `
        <span style="color: #00ff00;">$</span>
        <input type="text" id="terminalInput" style="flex: 1; background: #0a0a0a; color: #00ff00; border: 1px solid #334155; padding: 6px; border-radius: 4px; font-family: 'Courier New', monospace;">
    `;
    content.appendChild(inputWrapper);

    // Controls
    controls.innerHTML = `
        <button id="clearTerminal" class="panel-btn">🧹 Clear</button>
        <button id="terminalHelp" class="panel-btn">❓ Commands</button>
        <select id="terminalMode" class="panel-btn">
            <option value="mock">Mock Terminal</option>
            <option value="log">Log Viewer</option>
        </select>
    `;

    const input = content.querySelector('#terminalInput');
    const output = terminal;

    // Mock terminal state
    this.terminalState = {
        history: [],
        historyIndex: -1,
        cwd: '/home/user',
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
            if (cmd.trim()) {
                executeCommand(cmd);
            }
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

    controls.querySelector('#clearTerminal').addEventListener('click', () => {
        output.innerHTML = '';
    });

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
// Additional Mode Initializers (Preview, JSON, etc.)
// =====================================================================

VeraChat.prototype.initHTMLPreview = function() {
    const { content, controls } = this.canvas;
    
    // Split editor and preview
    const wrapper = document.createElement('div');
    wrapper.style.cssText = 'display: grid; grid-template-columns: 1fr 1fr; gap: 12px; height: 100%;';
    
    wrapper.innerHTML = `
        <div style="display: flex; flex-direction: column;">
            <div style="margin-bottom: 8px; font-weight: bold; color: #94a3b8;">HTML/CSS/JS</div>
            <textarea id="html-editor" style="flex: 1; resize: none; padding: 12px; border: 1px solid #334155; border-radius: 6px; background: #1e293b; color: #f1f5f9; font-size: 14px; line-height: 1.5; font-family: inherit;"></textarea>
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

    const runPreview = () => {
        iframe.srcdoc = editor.value;
    };

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

    editor.addEventListener('input', () => {
        if (autoRun) runPreview();
    });

    editor.value = '<!DOCTYPE html>\n<html>\n<head>\n  <title>Preview</title>\n</head>\n<body>\n  <h1>Hello World</h1>\n</body>\n</html>';
};

VeraChat.prototype.initJSONViewer = function() {
    const { content, controls } = this.canvas;
    
    const wrapper = document.createElement('div');
    wrapper.style.cssText = 'display: grid; grid-template-columns: 1fr 1fr; gap: 12px; height: 100%;';
    
    wrapper.innerHTML = `
        <div style="display: flex; flex-direction: column;">
            <div style="margin-bottom: 8px; font-weight: bold; color: #94a3b8;">JSON Input</div>
            <textarea id="json-editor" style="flex: 1; resize: none; padding: 12px; border: 1px solid #334155; border-radius: 6px; background: #1e293b; color: #f1f5f9; font-size: 14px; line-height: 1.5; font-family: inherit;"></textarea>
        </div>
        <div style="display: flex; flex-direction: column;">
            <div style="margin-bottom: 8px; font-weight: bold; color: #94a3b8;">Formatted / Tree View</div>
            <div id="json-preview" style="flex: 1; border: 1px solid #334155; border-radius: 6px; background: #1e293b; overflow: auto; padding: 12px;"></div>
        </div>
    `;
    content.appendChild(wrapper);

    controls.innerHTML = `
        <button id="parseJson" class="panel-btn">✨ Format</button>
        <button id="compactJson" class="panel-btn">📦 Compact</button>
        <button id="treeJson" class="panel-btn">🌳 Tree View</button>
        <button id="validateJson" class="panel-btn">✅ Validate</button>
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

    controls.querySelector('#parseJson').addEventListener('click', () => {
        parseAndFormat();
    });

    controls.querySelector('#compactJson').addEventListener('click', () => {
        try {
            const parsed = JSON.parse(editor.value);
            editor.value = JSON.stringify(parsed);
            parseAndFormat();
        } catch(e) {
            alert('Invalid JSON');
        }
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
        } catch(e) {
            alert('❌ Invalid JSON: ' + e.message);
        }
    });
};

VeraChat.prototype.initDiagramViewer = function() {
    const { content, controls } = this.canvas;
    
    const wrapper = document.createElement('div');
    wrapper.style.cssText = 'display: grid; grid-template-columns: 1fr 1fr; gap: 12px; height: 100%;';
    
    wrapper.innerHTML = `
        <div style="display: flex; flex-direction: column;">
            <div style="margin-bottom: 8px; font-weight: bold; color: #94a3b8;">Mermaid Code</div>
            <textarea id="mermaid-editor" placeholder="graph TD\nA[Start] --> B[End]" style="flex: 1; resize: none; padding: 12px; border: 1px solid #334155; border-radius: 6px; background: #1e293b; color: #f1f5f9; font-size: 14px; line-height: 1.5; font-family: inherit;"></textarea>
        </div>
        <div style="display: flex; flex-direction: column;">
            <div style="margin-bottom: 8px; font-weight: bold; color: #94a3b8;">Diagram</div>
            <div id="mermaid-preview" style="flex: 1; border: 1px solid #334155; border-radius: 6px; background: white; overflow: auto; padding: 12px; display: flex; align-items: center; justify-content: center;"></div>
        </div>
    `;
    content.appendChild(wrapper);

    controls.innerHTML = `
        <button id="renderDiagram" class="panel-btn">🎨 Render</button>
        <button id="exportDiagramSvg" class="panel-btn">💾 Export SVG</button>
        <button id="diagramExamples" class="panel-btn">📚 Examples</button>
    `;

    const editor = content.querySelector('#mermaid-editor');
    const preview = content.querySelector('#mermaid-preview');

    controls.querySelector('#renderDiagram').addEventListener('click', async () => {
        await this.loadMermaid();
        try {
            preview.innerHTML = `<div class="mermaid">${editor.value}</div>`;
            if (window.mermaid) {
                mermaid.init(undefined, preview.querySelector('.mermaid'));
            }
        } catch(e) {
            preview.innerHTML = `<div style="color: #ef4444;">Diagram error: ${e.message}</div>`;
        }
    });

    controls.querySelector('#diagramExamples').addEventListener('click', () => {
        const examples = `
Examples:

Flowchart:
graph TD
A[Start] --> B{Is it working?}
B -->|Yes| C[Great!]
B -->|No| D[Debug]

Sequence:
sequenceDiagram
Alice->>John: Hello John!
John-->>Alice: Hi Alice!

Class:
classDiagram
Animal <|-- Dog
Animal : +int age
Dog : +bark()
        `.trim();
        editor.value = examples;
    });

    editor.value = 'graph TD\n    A[Start] --> B{Decision}\n    B -->|Yes| C[Success]\n    B -->|No| D[Try Again]';
};

VeraChat.prototype.initTableViewer = function() {
    const { content, controls } = this.canvas;
    
    content.innerHTML = `
        <div style="margin-bottom: 12px;">
            <div style="margin-bottom: 8px; font-weight: bold; color: #94a3b8;">CSV / TSV / JSON Data</div>
            <textarea id="table-data" placeholder="Paste CSV, TSV, or JSON array here..." style="width: 100%; height: 150px; resize: vertical; padding: 12px; border: 1px solid #334155; border-radius: 6px; background: #1e293b; color: #f1f5f9; font-size: 14px; line-height: 1.5; font-family: inherit;"></textarea>
        </div>
        <div id="table-display" style="overflow: auto; border: 1px solid #334155; border-radius: 6px; background: #1e293b;"></div>
    `;

    controls.innerHTML = `
        <select id="tableFormat" class="panel-btn">
            <option value="auto">Auto-detect</option>
            <option value="csv">CSV</option>
            <option value="tsv">TSV</option>
            <option value="json">JSON</option>
        </select>
        <button id="parseTable" class="panel-btn">📊 Parse</button>
        <button id="sortTable" class="panel-btn">⬆️ Sort</button>
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
};

VeraChat.prototype.initDiffViewer = function() {
    const { content, controls } = this.canvas;
    
    content.innerHTML = `
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; height: 100%;">
            <div style="display: flex; flex-direction: column;">
                <div style="margin-bottom: 8px; font-weight: bold; color: #94a3b8;">Original</div>
                <textarea id="diff-original" style="flex: 1; resize: none; padding: 12px; border: 1px solid #334155; border-radius: 6px; background: #1e293b; color: #f1f5f9; font-size: 14px; line-height: 1.5; font-family: inherit;"></textarea>
            </div>
            <div style="display: flex; flex-direction: column;">
                <div style="margin-bottom: 8px; font-weight: bold; color: #94a3b8;">Modified</div>
                <textarea id="diff-modified" style="flex: 1; resize: none; padding: 12px; border: 1px solid #334155; border-radius: 6px; background: #1e293b; color: #f1f5f9; font-size: 14px; line-height: 1.5; font-family: inherit;"></textarea>
            </div>
        </div>
        <div id="diff-result" style="margin-top: 12px; border: 1px solid #334155; border-radius: 6px; background: #1e293b; padding: 12px; max-height: 200px; overflow: auto; display: none;"></div>
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

// =====================================================================
// Helper Functions
// =====================================================================

VeraChat.prototype.clearCanvas = function() {
    if (!this.canvas) return;
    this.canvas.content.innerHTML = '';
    this.canvas.controls.innerHTML = '';
    this.canvas.data = null;
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

VeraChat.prototype.highlightCode = async function(code, lang, target) {
    await this.loadPrism();
    if (!lang) lang = this.detectLanguage(code);
    target.innerHTML = `<pre style="margin:0;"><code class="language-${lang}">${this._escapeHtml(code)}</code></pre>`;
    if (window.Prism) Prism.highlightElement(target.querySelector('code'));
};

VeraChat.prototype.detectLanguage = function(code) {
    if (code.trim().startsWith('{') || code.trim().startsWith('[')) return 'json';
    if (/^\s*(import|def|print|class|from)\s/.test(code)) return 'python';
    if (/<[a-z][\s\S]*>/i.test(code)) return 'html';
    if (code.includes('function') || code.includes('=>') || code.includes('const ')) return 'javascript';
    if (code.includes('#include') || code.includes('int main')) return 'cpp';
    if (code.includes('SELECT') || code.includes('FROM')) return 'sql';
    return 'plaintext';
};

VeraChat.prototype.getFileExtension = function(lang) {
    const exts = {
        javascript: '.js', python: '.py', html: '.html', css: '.css',
        json: '.json', markdown: '.md', sql: '.sql', bash: '.sh',
        c: '.c', cpp: '.cpp', rust: '.rs', go: '.go'
    };
    return exts[lang] || '.txt';
};

VeraChat.prototype.formatJS = function(code) {
    // Basic JS formatting (indentation)
    return code; // Simplified - full formatter would require library
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

// Library loaders
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
            const langs = ["javascript","python","json","markup","css","c","rust","sql","bash"];
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

VeraChat.prototype.loadMarkdownLibrary = async function() {
    if (window.marked) return;
    return new Promise((resolve) => {
        const script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/npm/marked/marked.min.js';
        script.onload = () => resolve();
        document.head.appendChild(script);
    });
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

VeraChat.prototype._escapeHtml = function(str) {
    if (str === undefined || str === null) return "";
    return String(str).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
};

// =====================================================================
// Enhanced Message Integration
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
        // Auto-switch to appropriate mode
        const mode = this.detectCanvasMode(language, code);
        const modeSelector = document.querySelector('#canvasMode');
        if (modeSelector) modeSelector.value = mode;
        this.switchCanvasMode(mode);
        
        // Load content
        this.loadIntoCanvas(language, code);
        
        // Switch to canvas tab
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
    return 'code';
};

VeraChat.prototype.loadIntoCanvas = function(language, code) {
    if (!this.canvas) this.initCanvasTab();
    
    const mode = this.canvas.mode;
    
    switch(mode) {
        case 'code':
            const editor = document.querySelector('#canvas-editor');
            if (editor) editor.value = code;
            break;
        case 'markdown':
            const mdEditor = document.querySelector('#md-editor');
            if (mdEditor) {
                mdEditor.value = code;
                mdEditor.dispatchEvent(new Event('input'));
            }
            break;
        case 'jupyter':
            try {
                const notebook = JSON.parse(code);
                this.canvas.data = notebook;
                const viewer = document.querySelector('#jupyter-viewer');
                if (viewer) this.renderJupyterNotebook(notebook, viewer);
            } catch(e) {
                console.error('Failed to parse notebook', e);
            }
            break;
        case 'preview':
            const htmlEditor = document.querySelector('#html-editor');
            if (htmlEditor) htmlEditor.value = code;
            break;
        case 'json':
            const jsonEditor = document.querySelector('#json-editor');
            if (jsonEditor) {
                jsonEditor.value = code;
                const parseBtn = document.querySelector('#parseJson');
                if (parseBtn) parseBtn.click();
            }
            break;
        case 'diagram':
            const mermaidEditor = document.querySelector('#mermaid-editor');
            if (mermaidEditor) {
                mermaidEditor.value = code;
                const renderBtn = document.querySelector('#renderDiagram');
                if (renderBtn) renderBtn.click();
            }
            break;
    }
};

// =====================================================================
// End Enhanced Canvas Integration
// =====================================================================
>>>>>>> dev-vera-ollama-fixed
})();