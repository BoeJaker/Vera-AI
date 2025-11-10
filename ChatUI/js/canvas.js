
(() => {
// --------------------- Canvas integration for VeraChat ---------------------
VeraChat.prototype.initCanvasTab = function () {
    // Try to locate the canvas tab container
    const root = document.querySelector('#tab-canvas');
    if (!root) {
        console.warn('Canvas tab container not found');
        return;
    }

    // Clear any previous content
    root.innerHTML = '';

    // Create container
    const container = document.createElement('div');
    container.style.cssText = `
        display: flex;
        flex-direction: column;
        height: 100%;
        overflow: hidden;
        background: #0f172a;
        color: #e2e8f0;
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
})();