(() => {
  // ============================================
  // VERACHAT THEME SYSTEM v2.0
  // ============================================

  // --- Base CSS (shared across all themes) ---
  const baseCSS = `
    :root {
      --radius-sm: 6px;
      --radius-md: 8px;
      --radius-lg: 10px;
      --radius-xl: 12px;
      --transition-fast: 0.15s ease;
      --transition-normal: 0.3s ease;
    }

    * {
      box-sizing: border-box;
    }

    body {
      height: 100vh;
      overflow: hidden;
      margin: 0;
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
    }

    /* Scrollbar defaults */
    ::-webkit-scrollbar { width: 8px; height: 8px; }
    ::-webkit-scrollbar-track { background: var(--bg); border-radius: 4px; }
    ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: var(--hover); }
  `;

  // --- Theme Definitions ---
  const themes = {
    default: {
      name: 'Default Dark',
      variables: {
        '--bg': '#0f172a',
        '--bg-surface': '#0f172a',
        '--panel-bg': '#1e293b',
        '--text': '#e2e8f0',
        '--text-secondary': '#94a3b8',
        '--accent': '#3b82f6',
        '--accent-muted': '#3b82f6cc',
        '--border': '#334155',
        '--border-subtle': '#2d3a4f',
        '--hover': '#475569',
        '--text-inverted': '#000000',
        '--user-bg': '#1e3a8a',
      },
      fonts: [],
      css: `
        body {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        }
        
        .chat-panel, .graph-panel {
          box-shadow: inset 0 0 10px rgba(255,255,255,0.05);
        }
      `,
      graph: {
        nodeBorder: '#60a5fa',
        nodeBackground: '#1e293b',
        nodeHighlight: '#3b82f6',
        nodeFont: '#e2e8f0',
        nodeFontSize: 14,
        edgeColor: '#475569',
        edgeHighlight: '#60a5fa',
        background: '#0f172a',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
      }
    },

    modernPro: {
      name: 'Modern Professional',
      variables: {
        '--bg': '#18181b',
        '--bg-surface': '#27272a',
        '--panel-bg': '#1f1f23',
        '--text': '#fafafa',
        '--text-secondary': '#a1a1aa',
        '--accent': '#6366f1',
        '--accent-muted': '#6366f1cc',
        '--border': '#3f3f46',
        '--border-subtle': '#2e2e33',
        '--hover': '#4f46e5',
        '--text-inverted': '#ffffff',
        '--success': '#22c55e',
        '--warning': '#f59e0b',
        '--error': '#ef4444',
        '--user-bg': 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)',
      },
      fonts: ['Inter:wght@400;500;600'],
      css: `
        body {
          font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          font-size: 14px;
          line-height: 1.6;
        }

        h1, h2, h3 { 
          color: var(--text);
          font-weight: 600;
          letter-spacing: -0.02em;
        }

        button {
          font-family: 'Inter', sans-serif;
          font-weight: 500;
        }

        button:hover {
          transform: translateY(-1px);
        }

        .message.user .message-content {
          background: var(--user-bg);
          border: none;
          color: white;
        }

        .message.assistant .message-avatar {
          background: linear-gradient(135deg, var(--accent) 0%, var(--hover) 100%);
          border: none;
          color: white;
        }

        input:focus, textarea:focus {
          outline: none;
          border-color: var(--accent);
          box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15);
        }

        .send-btn:hover {
          box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
        }

        .tool-card:hover {
          border-color: var(--border);
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        }

        .search-result-item:hover {
          border-color: var(--accent);
        }

        /* Status indicators */
        .status-success { color: var(--success); }
        .status-warning { color: var(--warning); }
        .status-error { color: var(--error); }
      `,
      graph: {
        nodeBorder: '#6366f1',
        nodeBackground: '#27272a',
        nodeHighlight: '#818cf8',
        nodeFont: '#fafafa',
        nodeFontSize: 13,
        edgeColor: '#52525b',
        edgeHighlight: '#6366f1',
        background: '#18181b',
        fontFamily: '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
      }
    },

    terminal: {
      name: 'Terminal',
      variables: {
        '--bg': '#000000',
        '--bg-surface': '#000000',
        '--panel-bg': '#000000',
        '--text': '#00ff66',
        '--text-secondary': '#00aa44',
        '--accent': '#00ff66',
        '--accent-muted': '#00ff66b0',
        '--border': '#00aa44',
        '--border-subtle': '#004422',
        '--hover': '#003300',
        '--text-inverted': '#000000',
        '--user-text': '#00ffaa',
        '--caret': '#00ff66',
      },
      fonts: [],
      css: `
        body {
          font-family: "Fira Code", "Consolas", monospace;
          letter-spacing: 0.02em;
          line-height: 1.4;
        }

        button, select, input, textarea {
          font-family: "Fira Code", monospace;
        }

        .chat-panel, .graph-panel {
          box-shadow: none;
          font-family: "Fira Code", monospace;
          font-size: 13px;
        }

        #chatMessages {
          display: block;
          white-space: pre-wrap;
          font-family: "Fira Code", monospace;
          font-size: 13px;
          line-height: 1.4;
        }

        .message {
          display: block;
          margin: 0;
          padding: 0;
        }

        .message-content {
          display: inline;
          background: none !important;
          border: none !important;
          padding: 0;
          margin: 0;
          font-family: "Fira Code", monospace;
          font-size: 13px;
        }

        .message.user .message-content {
          color: var(--user-text);
        }

        #messageInput {
          font-family: "Fira Code", monospace;
          font-size: 13px;
          caret-color: var(--caret);
        }

        #messageInput::placeholder {
          color: #006633;
        }

        .send-btn {
          background: #002200;
          color: var(--text);
          border: 1px solid var(--border);
          text-transform: uppercase;
        }

        .send-btn:hover {
          background: #003300;
        }

        ::-webkit-scrollbar-thumb { background: #004400; }

        @keyframes blink {
          0%, 50% { opacity: 1; }
          50.1%, 100% { opacity: 0; }
        }
      `,
      graph: {
        nodeBorder: '#00ff66',
        nodeBackground: '#001100',
        nodeHighlight: '#00ffaa',
        nodeFont: '#00ff66',
        nodeFontSize: 13,
        edgeColor: '#00aa44',
        edgeHighlight: '#00ffaa',
        background: '#000000',
        fontFamily: '"Fira Code", "Courier New", monospace'
      }
    },

    darkNewspaper: {
      name: 'Dark Newspaper',
      variables: {
        '--bg': '#111111',
        '--bg-surface': '#111111',
        '--panel-bg': '#141414',
        '--text': '#e8e6e3',
        '--text-secondary': '#a8a6a3',
        '--accent': '#f5f5f5',
        '--accent-muted': '#f5f5f5d5',
        '--border': '#333333',
        '--border-subtle': '#222222',
        '--hover': '#555555',
        '--text-inverted': '#000000',
      },
      fonts: ['Playfair+Display:wght@400;700', 'Crimson+Text:wght@400;600'],
      css: `
        body {
          font-family: 'Crimson Text', Georgia, serif;
          line-height: 1.8;
          font-size: 16px;
          text-rendering: optimizeLegibility;
        }

        h1, h2, h3 { 
          font-family: 'Playfair Display', serif;
        }

        button {
          font-family: 'Playfair Display', serif;
        }

        select {
          font-family: 'Playfair Display', serif;
        }

        input, textarea {
          font-family: 'Crimson Text', serif;
        }

        .message-content {
          background: #181818;
          border-left: 3px solid #555;
          font-family: 'Playfair Display', serif;
        }

        .message.user .message-content {
          background: #202020;
          border-left-color: #666;
        }

        #chatMessages {
          display: flex;
          flex-direction: column;
          gap: 20px;
        }

        #messageInput {
          background: #1a1a1a;
          font-family: 'Crimson Text', serif;
        }

        .send-btn {
          background: #333;
          color: #eee;
          border: 1px solid #444;
          font-family: 'Playfair Display', serif;
        }

        .send-btn:hover {
          background: var(--hover);
          border-color: #777;
        }

        .tool-card {
          border-left: 4px solid var(--accent);
        }

        body::before {
          content: "";
          position: fixed;
          top: 0; left: 0; right: 0; bottom: 0;
          background: url('https://www.transparenttextures.com/patterns/paper-fibers.png');
          opacity: 0.05;
          pointer-events: none;
          z-index: 9999;
        }
      `,
      graph: {
        nodeBorder: '#e8e6e3',
        nodeBackground: '#1a1a1a',
        nodeHighlight: '#f5f5f5',
        nodeFont: '#e8e6e3',
        nodeFontSize: 15,
        edgeColor: '#b9b9b9',
        edgeHighlight: '#e8e6e3',
        background: '#111111',
        fontFamily: '"Crimson Text", Georgia, serif'
      }
    },

    pixelArt: {
      name: 'Pixel Art',
      variables: {
        '--bg': '#0d0d1a',
        '--bg-surface': '#2a2a55',
        '--panel-bg': '#29144b',
        '--text': '#66f0ff',
        '--text-secondary': '#4488aa',
        '--accent': '#ff33cc',
        '--accent-muted': '#ff33ccad',
        '--border': '#440066',
        '--border-subtle': '#330055',
        '--hover': '#9b00ff',
        '--text-inverted': '#000000',
        '--user-text': '#ff77ff',
      },
      fonts: ['Press+Start+2P'],
      css: `
        body {
          font-family: 'Press Start 2P', monospace;
          font-size: 12px;
          image-rendering: pixelated;
          letter-spacing: 0.05em;
        }

        button, select, input, textarea {
          font-family: 'Press Start 2P', monospace;
        }

        h1, h2, h3 {
          text-shadow: 2px 2px #000;
        }

        .chat-panel, .graph-panel {
          border: 2px solid var(--border);
          box-shadow: 0 0 12px var(--accent);
          image-rendering: pixelated;
        }

        #chatMessages {
          font-size: 12px;
          line-height: 1.2;
        }

        .message-avatar {
          width: 28px;
          height: 28px;
          background: #220022;
          border: 2px solid var(--accent);
          font-size: 10px;
          text-shadow: 0 0 4px var(--accent);
        }

        .message.assistant .message-avatar {
          border-color: #33ffff;
          color: #33ffff;
          text-shadow: 0 0 4px #33ffff;
        }

        .message-content {
          background: rgba(0,0,0,0.6);
          border: 2px solid var(--accent);
          border-radius: 4px;
          line-height: 1.2;
          text-shadow: 0 0 4px var(--text);
        }

        .message.user .message-content {
          border-color: var(--user-text);
          color: var(--user-text);
          text-shadow: 0 0 4px var(--user-text);
        }

        #messageInput {
          background: #110022;
          border: 2px solid var(--accent);
          font-size: 11px;
          caret-color: var(--accent);
          text-transform: uppercase;
        }

        #messageInput::placeholder {
          color: #330044;
        }

        .send-btn {
          background: #220033;
          color: var(--accent);
          border: 2px solid var(--accent);
          text-transform: uppercase;
        }

        .send-btn:hover {
          background: var(--hover);
          color: #fff;
          box-shadow: 0 0 12px var(--accent);
        }

        #graph {
          background: repeating-linear-gradient(
            to bottom,
            #0d0d1a,
            #0d0d1a 2px,
            #110033 3px
          );
          image-rendering: pixelated;
        }

        @keyframes neonFlicker {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.95; }
          25%, 75% { opacity: 0.97; }
        }

        body {
          animation: neonFlicker 0.1s infinite;
        }

        body::before {
          content: "";
          position: fixed;
          top: 0; left: 0; right: 0; bottom: 0;
          background: repeating-linear-gradient(
            to bottom,
            rgba(255,255,255,0.02) 0px,
            rgba(255,255,255,0.02) 1px,
            transparent 2px
          );
          pointer-events: none;
          z-index: 9999;
          image-rendering: pixelated;
        }
      `,
      graph: {
        nodeBorder: '#ff33cc',
        nodeBackground: '#1a0d2f',
        nodeHighlight: '#ff77ff',
        nodeFont: '#66f0ff',
        nodeFontSize: 11,
        edgeColor: '#440066',
        edgeHighlight: '#9b00ff',
        background: '#0d0d1a',
        fontFamily: '"Press Start 2P", monospace',
        nodeShape: 'box',
        edgeWidth: 3
      }
    },

    retroGaming: {
      name: 'Retro Gaming',
      variables: {
        '--bg': '#000000',
        '--bg-surface': '#000000',
        '--panel-bg': '#000000',
        '--text': '#00ffcc',
        '--text-secondary': '#00aa88',
        '--accent': '#ff0077',
        '--accent-muted': '#ca4a86b4',
        '--border': '#00ffcc',
        '--border-subtle': '#007766',
        '--hover': '#ff3794',
        '--text-inverted': '#ff0077',
        '--user-text': '#ff3794',
      },
      fonts: ['Press+Start+2P'],
      css: `
        header {
          background: var(--bg);
        }

        body {
          background: radial-gradient(circle at center, #101010 0%, #000 100%);
          font-family: 'Press Start 2P', monospace;
          font-size: 11px;
          text-transform: uppercase;
          image-rendering: pixelated;
        }

        button, select, input, textarea {
          font-family: 'Press Start 2P', monospace;
        }

        .chat-panel, .graph-panel {
          border: 2px solid var(--border);
          box-shadow: 0 0 12px var(--accent);
          image-rendering: pixelated;
        }

        #chatMessages {
          font-size: 12px;
          line-height: 1.2;
        }

        .message-avatar {
          width: 28px;
          height: 28px;
          background: #220022;
          border: 2px solid var(--accent);
          font-size: 10px;
          text-shadow: 0 0 4px var(--accent);
        }

        .message.assistant .message-avatar {
          border-color: #33ffff;
          color: #33ffff;
          text-shadow: 0 0 4px #33ffff;
        }

        .message-content {
          background: rgba(0,0,0,0.6);
          border: 2px solid var(--accent);
          border-radius: 4px;
          line-height: 1.2;
          text-shadow: 0 0 4px var(--text);
        }

        .message.user .message-content {
          border-color: var(--user-text);
          color: var(--user-text);
          text-shadow: 0 0 4px var(--user-text);
        }

        .input-area {
          border-top: 2px solid var(--border);
        }

        @keyframes crtFlicker {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.98; }
        }

        body {
          animation: crtFlicker 0.1s infinite;
        }
      `,
      graph: {
        nodeBorder: '#00ffcc',
        nodeBackground: '#001a1a',
        nodeHighlight: '#00ffff',
        nodeFont: '#00ffcc',
        nodeFontSize: 10,
        edgeColor: '#ff0077',
        edgeHighlight: '#ff33aa',
        background: '#000000',
        fontFamily: '"Press Start 2P", monospace',
        nodeShape: 'box',
        edgeWidth: 2
      }
    },

    sunsetGlow: {
      name: 'Sunset Glow',
      variables: {
        '--bg': '#2b1a2f',
        '--bg-surface': '#3e2a45',
        '--panel-bg': '#593964',
        '--text': '#ffd8a8',
        '--text-secondary': '#ccaa88',
        '--accent': '#ff6f61',
        '--accent-muted': '#ff6f61cc',
        '--border': '#7e5a7e',
        '--border-subtle': '#5e3a5e',
        '--hover': '#ffa07a',
        '--text-inverted': '#ffffff',
        '--user-text': '#ffb347',
      },
      fonts: ['Share+Tech+Mono'],
      css: `
        body {
          font-family: 'Share Tech Mono', 'Segoe UI', sans-serif;
        }

        button, select, input, textarea {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        }

        .chat-panel, .graph-panel {
          box-shadow: inset 0 0 10px rgba(0,0,0,0.2);
        }

        .message-content {
          background: rgba(255, 200, 160, 0.1);
          border-left: 3px solid var(--border);
        }

        .message.user .message-content {
          background: rgba(255, 175, 100, 0.2);
          border-left-color: var(--user-text);
          color: var(--user-text);
        }

        #messageInput:focus {
          border-color: var(--accent);
        }
      `,
      graph: {
        nodeBorder: '#ff6f61',
        nodeBackground: '#3e2a45',
        nodeHighlight: '#ffa07a',
        nodeFont: '#ffd8a8',
        nodeFontSize: 14,
        edgeColor: '#7e5a7e',
        edgeHighlight: '#a07aa0',
        background: '#2b1a2f',
        fontFamily: '"Share Tech Mono", monospace'
      }
    },
    rainbowNoir: {
      name: 'Rainbow Noir',
      variables: {
        '--bg': '#0b0b0e',
        '--bg-surface': '#141418',
        '--panel-bg': '#1d1d24',

        /* Text uses bright rainbow terminal vibes */
        '--text': 'linear-gradient(90deg, #ff5555, #f1fa8c, #50fa7b, #8be9fd, #bd93f9, #ff79c6)',
        '--text-secondary': '#bbbbbb',

        /* Rainbow accents for UI elements */
        '--accent': '#ff79c6',
        '--accent-muted': '#ff79c666',

        '--border': '#444',
        '--border-subtle': '#2a2a2f',
        '--hover': '#bd93f9',
        '--text-inverted': '#ffffff',

        /* User-message text in rainbow gradient */
        '--user-text': 'linear-gradient(90deg, #ff9a9e, #fad0c4, #fbc2eb, #a18cd1, #84fab0, #8fd3f4)'
      },

      fonts: ['Share+Tech+Mono'],

      css: `
        body {
          font-family: 'Share Tech Mono', 'Segoe UI', sans-serif;
          color: #ffffff;
        }

        button, select, input, textarea {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        }

        /* Rainbow text effect */
        .message-content, .message.user .message-content {
          background: rgba(255, 255, 255, 0.03);
          border-left: 3px solid var(--border);
          -webkit-background-clip: text;
          background-clip: text;
        }

        .message-content {
          color: transparent;
          background-image: var(--text);
        }

        .message.user .message-content {
          color: transparent;
          background-image: var(--user-text);
          border-left-color: #ff79c6;
        }

        .chat-panel, .graph-panel {
          box-shadow: inset 0 0 12px rgba(0,0,0,0.4);
        }

        #messageInput:focus {
          border-color: var(--accent);
        }
      `,

      graph: {
        nodeBorder: '#ff79c6',
        nodeBackground: '#1d1d24',
        nodeHighlight: '#bd93f9',
        nodeFont: '#ffffff',
        nodeFontSize: 14,
        edgeColor: '#444',
        edgeHighlight: '#ff79c6',
        background: '#0b0b0e',
        fontFamily: '"Share Tech Mono", monospace'
      }
    }

  };

  // --- Theme Manager Class ---
  class ThemeManager {
    constructor() {
      this.currentTheme = null;
      this.styleEl = null;
      this.fontEl = null;
      this.listeners = new Set();
      this._hooked = false;
    }

    init() {
      // Create style element for theme CSS
      this.styleEl = document.createElement('style');
      this.styleEl.setAttribute('data-theme-style', '');
      document.head.appendChild(this.styleEl);

      // Create link element for Google Fonts
      this.fontEl = document.createElement('link');
      this.fontEl.rel = 'stylesheet';
      document.head.appendChild(this.fontEl);

      // Load saved theme or default
      const savedTheme = localStorage.getItem('theme') || 'default';
      this.apply(savedTheme);

      // Watch for network ready to apply graph theme
      this._watchForNetwork();
    }

    apply(themeName) {
      const theme = themes[themeName];
      if (!theme) {
        console.warn(`Theme "${themeName}" not found, using default`);
        return this.apply('default');
      }

      this.currentTheme = themeName;
      localStorage.setItem('theme', themeName);

      // Load Google Fonts if needed
      if (theme.fonts?.length) {
        const fontUrl = `https://fonts.googleapis.com/css2?${theme.fonts.map(f => `family=${f}`).join('&')}&display=swap`;
        this.fontEl.href = fontUrl;
      } else {
        this.fontEl.href = '';
      }

      // Build and apply CSS
      const variablesCSS = Object.entries(theme.variables)
        .map(([key, value]) => `${key}: ${value};`)
        .join('\n        ');

      this.styleEl.textContent = `
        :root {
          ${variablesCSS}
        }
        ${baseCSS}
        ${this._getCommonComponentCSS()}
        ${theme.css || ''}
      `;

      // Apply to graph if available
      this._applyToGraph(theme);

      // Notify listeners
      this.listeners.forEach(fn => fn(themeName, theme));

      console.log(`Theme applied: ${theme.name}`);
    }

    _getCommonComponentCSS() {
      return `
        /* === Base Elements === */
        body {
          background: var(--bg);
          color: var(--text);
        }

        a { 
          color: var(--accent); 
          text-decoration: none;
          transition: color var(--transition-fast);
        }
        a:hover { color: var(--hover); }

        h1, h2, h3 { color: var(--accent); }

        /* === Form Elements === */
        button {
          color: var(--text-inverted);
          background: var(--accent);
          border: none;
          border-radius: var(--radius-sm);
          padding: 8px 16px;
          cursor: pointer;
          transition: background var(--transition-fast), transform var(--transition-fast);
        }
        button:hover { background: var(--hover); }

        input, textarea, select {
          color: var(--text);
          background: var(--bg-surface);
          border: 1px solid var(--border);
          border-radius: var(--radius-sm);
          padding: 10px 14px;
          transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
        }

        input:focus, textarea:focus, select:focus {
          outline: none;
          border-color: var(--accent);
        }

        /* === Tabs === */
        .tab {
          background: transparent;
          color: var(--text-secondary);
          border: none;
          padding: 10px 16px;
          cursor: pointer;
          transition: all var(--transition-fast);
        }
        .tab:hover {
          color: var(--text);
          background: var(--bg-surface);
        }
        .tab.active {
          background: var(--accent);
          color: var(--text-inverted);
          font-weight: bold;
          border-radius: var(--radius-sm);
        }
        .tab-content {
          background: var(--bg);
          color: var(--text);
        }

        /* === Panels === */
        .chat-panel, .graph-panel {
          background: var(--panel-bg);
          border: 1px solid var(--border);
          border-radius: var(--radius-xl);
        }

        /* === Messages === */
        #chatMessages {
          background: var(--panel-bg);
          color: var(--text);
          padding: 16px;
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .message {
          display: flex;
          gap: 10px;
          align-items: flex-start;
        }

        .message-avatar {
          width: 32px;
          height: 32px;
          background: var(--bg-surface);
          border: 1px solid var(--border);
          border-radius: var(--radius-sm);
          display: flex;
          align-items: center;
          justify-content: center;
          font-weight: 600;
          font-size: 12px;
          color: var(--text-secondary);
          flex-shrink: 0;
        }

        .message-content {
          background: var(--bg-surface);
          color: var(--text);
          padding: 12px 16px;
          border-radius: var(--radius-md);
          border: 1px solid var(--border-subtle);
          line-height: 1.6;
          max-width: 85%;
        }

        .message.user .message-content {
          background: var(--user-bg, var(--accent));
          border: none;
          color: var(--text-inverted);
          margin-left: auto;
        }

        /* === Input Area === */
        .input-area {
          background: var(--panel-bg);
          border-top: 1px solid var(--border-subtle);
          padding: 12px 16px;
        }

        #messageInput {
          width: 100%;
          background: var(--bg-surface);
          color: var(--text);
          border: 1px solid var(--border);
          border-radius: var(--radius-md);
          padding: 12px 16px;
          font-size: 14px;
          resize: none;
        }

        #messageInput::placeholder {
          color: var(--text-secondary);
        }

        .send-btn {
          background: var(--accent);
          color: var(--text-inverted);
          border: none;
          border-radius: var(--radius-md);
          padding: 12px 20px;
          font-weight: 600;
          cursor: pointer;
          transition: all var(--transition-fast);
        }
        .send-btn:hover {
          background: var(--hover);
        }

        /* === Cards & Containers === */
        .tool-card,
        .tool-container,
        .toolchain-box,
        .memoryQuery,
        .focusContent,
        .memory-content {
          background: var(--panel-bg);
          border: 1px solid var(--border);
          border-radius: var(--radius-md);
          padding: 16px;
          transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
        }

        .memoryQuery,
        .toolchain-box {
          border-left: 4px solid var(--accent);
        }

        .tool-subcard {
          background: var(--bg);
          border: 1px solid var(--border-subtle);
          border-radius: var(--radius-md);
          padding: 12px;
        }

        .tool-type-filter {
          background: var(--bg-surface);
          color: var(--text);
          border: 1px solid var(--border);
          border-radius: var(--radius-sm);
        }

        .search-result-item {
          background: var(--bg-surface);
          border: 1px solid var(--border-subtle);
          border-radius: var(--radius-md);
          padding: 12px;
          transition: border-color var(--transition-fast);
        }

        /* === Utilities === */
        .graph-stats,
        .memory-search-container {
          background: var(--bg);
          color: var(--text);
        }

        .advanced-filters-content {
          background: var(--panel-bg);
          border: 1px solid var(--border-subtle);
          border-radius: var(--radius-md);
          padding: 16px;
        }

        .action-btn {
          color: var(--text);
          background: var(--bg-surface);
          border: 1px solid var(--border);
          padding: 8px 14px;
          border-radius: var(--radius-sm);
          transition: all var(--transition-fast);
        }
        .action-btn:hover {
          background: var(--hover);
          color: var(--text-inverted);
        }

        #graph {
          background: var(--bg);
        }
      `;
    }

    _applyToGraph(theme) {
      if (!window.network?.body?.data) return;

      const g = theme.graph;

      // Set network options
      window.network.setOptions({
        nodes: {
          shape: g.nodeShape || 'dot',
          size: 25,
          borderWidth: 2,
          borderWidthSelected: 3,
          color: {
            border: g.nodeBorder,
            background: g.nodeBackground,
            highlight: { border: g.nodeHighlight, background: g.nodeBackground },
            hover: { border: g.nodeHighlight, background: g.nodeBackground }
          },
          font: { 
            color: g.nodeFont, 
            size: g.nodeFontSize, 
            face: g.fontFamily 
          }
        },
        edges: {
          width: g.edgeWidth || 2,
          color: {
            color: g.edgeColor,
            highlight: g.edgeHighlight,
            hover: g.edgeHighlight
          },
          font: { 
            color: g.nodeFont, 
            size: g.nodeFontSize - 2, 
            face: g.fontFamily,
            strokeWidth: 0
          },
          smooth: { enabled: true, type: 'dynamic' }
        }
      });

      // Update container background
      window.network.body.container.style.background = g.background;

      // Batch update existing elements
      this._batchUpdateGraphElements(theme);
    }

    _batchUpdateGraphElements(theme) {
      const g = theme.graph;
      
      try {
        const { nodes, edges } = window.network.body.data;

        // Update all nodes
        const nodeUpdates = nodes.get().map(n => ({
          id: n.id,
          color: {
            border: g.nodeBorder,
            background: g.nodeBackground,
            highlight: { border: g.nodeHighlight, background: g.nodeBackground },
            hover: { border: g.nodeHighlight, background: g.nodeBackground }
          },
          font: { color: g.nodeFont, size: g.nodeFontSize, face: g.fontFamily }
        }));
        nodes.update(nodeUpdates);

        // Update all edges
        const edgeUpdates = edges.get().map(e => ({
          id: e.id,
          color: { 
            color: g.edgeColor, 
            highlight: g.edgeHighlight, 
            hover: g.edgeHighlight 
          },
          font: { color: g.nodeFont, size: g.nodeFontSize - 2, face: g.fontFamily }
        }));
        edges.update(edgeUpdates);

        console.log(`Updated ${nodeUpdates.length} nodes, ${edgeUpdates.length} edges`);
      } catch (err) {
        console.warn('Error updating graph elements:', err);
      }

      window.network.redraw();
    }

    _watchForNetwork() {
      // Check if already ready
      if (window.network?.body?.data) {
        this._applyToGraph(themes[this.currentTheme]);
        this._hookNetworkSetData();
        return;
      }

      // Poll for network availability
      let attempts = 0;
      const maxAttempts = 40; // 20 seconds

      const interval = setInterval(() => {
        attempts++;
        
        if (window.network?.body?.data) {
          clearInterval(interval);
          console.log(`Network ready after ${attempts} attempts`);
          this._applyToGraph(themes[this.currentTheme]);
          this._hookNetworkSetData();
        } else if (attempts >= maxAttempts) {
          clearInterval(interval);
          console.warn('Network not ready after maximum attempts');
        }
      }, 500);
    }

    _hookNetworkSetData() {
      if (!window.network || this._hooked) return;
      this._hooked = true;

      const original = window.network.setData.bind(window.network);
      window.network.setData = (data) => {
        original(data);
        // Reapply theme after data changes
        setTimeout(() => {
          this._applyToGraph(themes[this.currentTheme]);
        }, 100);
      };
    }

    // --- Public API ---

    onChange(callback) {
      this.listeners.add(callback);
      return () => this.listeners.delete(callback);
    }

    getThemes() {
      return Object.entries(themes).map(([id, t]) => ({ 
        id, 
        name: t.name 
      }));
    }

    getCurrentTheme() {
      return this.currentTheme;
    }

    getThemeConfig(name) {
      return themes[name];
    }

    applyCustomGraphColors(colors) {
      if (!window.network) {
        console.warn('Graph network not ready');
        return;
      }

      const customTheme = {
        graph: {
          nodeBorder: colors.nodeBorder,
          nodeBackground: colors.nodeBackground,
          nodeHighlight: colors.nodeHighlight,
          nodeFont: colors.nodeFont || colors.nodeBorder,
          nodeFontSize: colors.fontSize || 14,
          edgeColor: colors.edgeColor,
          edgeHighlight: colors.edgeColor,
          background: colors.background,
          fontFamily: themes[this.currentTheme]?.graph?.fontFamily || 'sans-serif'
        }
      };

      this._applyToGraph(customTheme);
    }
  }

  // --- Create singleton instance ---
  const themeManager = new ThemeManager();

  // --- Theme Settings UI ---
  VeraChat.prototype.initThemeSettings = function() {
    if (document.querySelector('#themeMenu')) return;

    themeManager.init();
    this._createThemeUI(themeManager);
  };

  VeraChat.prototype._createThemeUI = function(manager) {
    const currentTheme = manager.getCurrentTheme();
    const themeConfig = manager.getThemeConfig(currentTheme);

    // Create menu container
    const menu = document.createElement('div');
    menu.id = 'themeMenu';

    menu.innerHTML = `
      <style>
        #themeMenu {
          background: rgba(0, 0, 0, 0.9);
          color: #fff;
          padding: 16px;
          border-radius: 10px;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          font-size: 13px;
          width: 280px;
          box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
          backdrop-filter: blur(10px);
        }

        #themeMenu h4 {
          margin: 0 0 16px 0;
          font-size: 16px;
          text-align: center;
          border-bottom: 1px solid #333;
          padding-bottom: 12px;
        }

        #themeMenu label {
          font-size: 11px;
          opacity: 0.7;
          margin-top: 10px;
          display: block;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        #themeMenu select,
        #themeMenu input,
        #themeMenu button {
          width: 100%;
          background: #1a1a1a;
          color: #fff;
          border: 1px solid #333;
          border-radius: 6px;
          padding: 8px 12px;
          margin-top: 6px;
          font-size: 13px;
          box-sizing: border-box;
        }

        #themeMenu input[type="color"] {
          height: 36px;
          padding: 4px;
          cursor: pointer;
        }

        #themeMenu input[type="number"] {
          width: 80px;
        }

        #themeMenu button {
          cursor: pointer;
          transition: background 0.2s;
          margin-top: 8px;
        }

        #themeMenu button:hover {
          background: #333;
        }

        #themeMenu button.primary {
          background: #6366f1;
          border-color: #6366f1;
        }

        #themeMenu button.primary:hover {
          background: #4f46e5;
        }

        #themeMenu .section {
          margin-top: 16px;
          padding-top: 12px;
          border-top: 1px solid #222;
        }

        #themeMenu .section-title {
          font-size: 11px;
          opacity: 0.5;
          text-transform: uppercase;
          letter-spacing: 1px;
          margin-bottom: 8px;
        }

        #themeMenu .row {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-top: 8px;
        }

        #themeMenu .row label {
          flex: 1;
          margin: 0;
        }

        #themeMenu .row input[type="color"] {
          width: 60px;
          margin: 0;
        }

        #themeMenu.floating {
          position: fixed;
          z-index: 999999;
          cursor: grab;
          resize: both;
          overflow: auto;
        }

        #themeMenu.floating.dragging {
          cursor: grabbing;
          opacity: 0.9;
        }

        #themeMenu .btn-row {
          display: flex;
          gap: 8px;
          margin-top: 12px;
        }

        #themeMenu .btn-row button {
          flex: 1;
          margin: 0;
        }
      </style>

      <h4>🎨 Theme Settings</h4>

      <label>Theme Preset</label>
      <select id="themeSelect">
        ${manager.getThemes().map(t => 
          `<option value="${t.id}" ${t.id === currentTheme ? 'selected' : ''}>${t.name}</option>`
        ).join('')}
      </select>

      <div class="section">
        <div class="section-title">Graph Customization</div>
        
        <div class="row">
          <label>Node Border</label>
          <input type="color" id="nodeBorderColor" value="${themeConfig?.graph?.nodeBorder || '#6366f1'}">
        </div>
        
        <div class="row">
          <label>Node Background</label>
          <input type="color" id="nodeBgColor" value="${themeConfig?.graph?.nodeBackground || '#27272a'}">
        </div>
        
        <div class="row">
          <label>Node Highlight</label>
          <input type="color" id="nodeHighlightColor" value="${themeConfig?.graph?.nodeHighlight || '#818cf8'}">
        </div>
        
        <div class="row">
          <label>Edge Color</label>
          <input type="color" id="edgeColor" value="${themeConfig?.graph?.edgeColor || '#52525b'}">
        </div>
        
        <div class="row">
          <label>Background</label>
          <input type="color" id="graphBgColor" value="${themeConfig?.graph?.background || '#18181b'}">
        </div>

        <label>Font Size</label>
        <input type="number" id="nodeFontSize" min="8" max="24" value="${themeConfig?.graph?.nodeFontSize || 14}">
      </div>

      <div class="btn-row">
        <button id="resetThemeBtn">🔄 Reset</button>
        <button id="applyThemeBtn" class="primary">✓ Apply</button>
      </div>
      
      <button id="popThemeBtn" style="margin-top: 8px;">↗ Pop Out</button>
    `;

    // Add to container
    const settingsContainer = document.getElementById('theme-settings') || document.body;
    settingsContainer.appendChild(menu);

    // Get references
    const selector = menu.querySelector('#themeSelect');
    const nodeBorderInput = menu.querySelector('#nodeBorderColor');
    const nodeBgInput = menu.querySelector('#nodeBgColor');
    const nodeHighlightInput = menu.querySelector('#nodeHighlightColor');
    const edgeInput = menu.querySelector('#edgeColor');
    const graphBgInput = menu.querySelector('#graphBgColor');
    const fontSizeInput = menu.querySelector('#nodeFontSize');
    const resetBtn = menu.querySelector('#resetThemeBtn');
    const applyBtn = menu.querySelector('#applyThemeBtn');
    const popBtn = menu.querySelector('#popThemeBtn');

    // Update inputs when theme changes
    const updateInputsFromTheme = (themeName) => {
      const config = manager.getThemeConfig(themeName);
      if (!config?.graph) return;

      nodeBorderInput.value = config.graph.nodeBorder;
      nodeBgInput.value = config.graph.nodeBackground;
      nodeHighlightInput.value = config.graph.nodeHighlight;
      edgeInput.value = config.graph.edgeColor;
      graphBgInput.value = config.graph.background;
      fontSizeInput.value = config.graph.nodeFontSize;
    };

    // Theme select change
    selector.addEventListener('change', (e) => {
      manager.apply(e.target.value);
      updateInputsFromTheme(e.target.value);
    });

    // Apply custom colors
    applyBtn.addEventListener('click', () => {
      manager.applyCustomGraphColors({
        nodeBorder: nodeBorderInput.value,
        nodeBackground: nodeBgInput.value,
        nodeHighlight: nodeHighlightInput.value,
        edgeColor: edgeInput.value,
        background: graphBgInput.value,
        fontSize: parseInt(fontSizeInput.value)
      });
    });

    // Reset to preset
    resetBtn.addEventListener('click', () => {
      manager.apply(selector.value);
      updateInputsFromTheme(selector.value);
    });

    // Floating/docking functionality
    let isDragging = false;
    let offsetX = 0;
    let offsetY = 0;

    // Ensure floating widgets container exists
    let overlay = document.getElementById('floating-widgets');
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.id = 'floating-widgets';
      overlay.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:999999;';
      document.body.appendChild(overlay);
    }

    const makeFloating = () => {
      overlay.appendChild(menu);
      menu.classList.add('floating');
      menu.style.pointerEvents = 'auto';
      menu.style.right = '20px';
      menu.style.bottom = '20px';
      menu.style.left = 'auto';
      menu.style.top = 'auto';
      popBtn.textContent = '↙ Dock';
    };

    const makeDocked = () => {
      settingsContainer.appendChild(menu);
      menu.classList.remove('floating');
      menu.style.cssText = '';
      popBtn.textContent = '↗ Pop Out';
    };

    popBtn.addEventListener('click', () => {
      menu.classList.contains('floating') ? makeDocked() : makeFloating();
    });

    // Drag handlers
    menu.addEventListener('mousedown', (e) => {
      if (!menu.classList.contains('floating')) return;
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT' || e.target.tagName === 'BUTTON') return;

      isDragging = true;
      offsetX = e.clientX - menu.getBoundingClientRect().left;
      offsetY = e.clientY - menu.getBoundingClientRect().top;
      menu.classList.add('dragging');
      e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
      if (!isDragging) return;
      menu.style.left = `${e.clientX - offsetX}px`;
      menu.style.top = `${e.clientY - offsetY}px`;
      menu.style.right = 'auto';
      menu.style.bottom = 'auto';
    });

    document.addEventListener('mouseup', () => {
      isDragging = false;
      menu.classList.remove('dragging');
    });

    // Listen for theme changes to update inputs
    manager.onChange((themeName) => {
      selector.value = themeName;
      updateInputsFromTheme(themeName);
    });
  };

  // --- Export ---
  window.themeManager = themeManager;
  window.themes = themes;
})();