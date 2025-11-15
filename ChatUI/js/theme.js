(() => {
  // --- Define themes with comprehensive graph styling ---
  const themes = {
    default: {
      css: `
        :root {
          --bg: #0f172a;
          --bg-surface: #0f172a;
          --panel-bg: #1e293b;
          --text: #e2e8f0;
          --accent: #3b82f6;
          --border: #334155;
          --hover: #475569;
          --text-inverted: #000000;
        }
        
        body {
          background: var(--bg);
          color: var(--text);
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          height: 100vh;
          overflow: hidden;
        }

        a { color: var(--accent); }
        h1, h2, h3 { color: var(--accent); }
        button { color: var(--text-inverted); }
        select { color: var(--text-inverted); }
        input { color: var(--text-inverted); background: var(--bg-surface); }
        textarea { color: var(--text-inverted); background: var(--bg-surface); }

        .tab.active {
          background: var(--accent);
          color: var(--text-inverted);
          font-weight: bold;
        }
<<<<<<< HEAD

=======
        .tab-content {
          background: var(--bg);
          color: var(--text-inverted);
          font-weight: bold;
        }
>>>>>>> dev-vera-ollama-fixed
        .memoryQuery {
          background: var(--panel-bg);
          border-radius: 8px;
          padding: 16px;
          border-left: 4px solid var(--accent);
        }

        .focusContent {
          background: var(--panel-bg);
          border-radius: 8px;
          padding: 16px;
        }

        .tool-card {
          background: var(--panel-bg);
          border: 1px solid var(--border);
          border-radius: 8px;
          padding: 12px;
        }

        .tool-subcard {
          background: var(--bg);
          border: 1px solid var(--border);
          border-radius: 8px;
          padding: 12px;
        }

        .tool-container {
          background: var(--panel-bg);
          border: 1px solid var(--border);
          border-radius: 8px;
          padding: 12px;
        }

        .chat-panel, .graph-panel {
          background: var(--panel-bg);
          border-color: var(--border);
          box-shadow: inset 0 0 10px rgba(255,255,255,0.05);
        }

        #chatMessages { 
          background: var(--panel-bg); 
          color: var(--text); 
        }
        
        .message-content { 
          background: var(--bg); 
          color: var(--text); 
          padding: 12px 16px; 
          border-radius: 8px; 
        }
        
        .message.user .message-content { background: #1e3a8a; }
        .send-btn { background: var(--accent); color: white; }
        #messageInput { background: var(--panel-bg); color: var(--text); border: 1px solid var(--border); }
        ::-webkit-scrollbar-thumb { background: var(--border); }
        
        .toolchain-box {
          background: var(--panel-bg);
          color: var(--text);
          border-radius: 8px;
          padding: 16px;
          border-left: 4px solid var(--accent);
        }
<<<<<<< HEAD
=======
        .graph-stats{
            background: var(--bg);
            color: var(--text);
        }
        .memory-search-container{
            background: var(--bg);
        }
        .advanced-filters-content{
          background: var(--panel-bg);
        }
        .action-btn{
          color: var(--text)
        }
>>>>>>> dev-vera-ollama-fixed
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
    
    terminal: {
      css: `
        :root {
          --bg: #000;
          --bg-surface: #000;
          --text: #00ff66;
          --user-text: #00ffaa;
          --panel-bg: #000;
          --border: #00aa44;
          --accent: #00ff66;
<<<<<<< HEAD
=======
          --accent-muted: #00ff66b0 ;
>>>>>>> dev-vera-ollama-fixed
          --caret: #00ff66;
          --text-inverted: #000000;
        }

        body {
          background: var(--bg);
          color: var(--text);
          font-family: "Fira Code", monospace;
          letter-spacing: 0.02em;
          line-height: 1.4;
        }

        h1, h2, h3 { color: var(--accent); }
        
        button {
          font-family: "Fira Code", monospace;
          color: var(--text-inverted);
          background: var(--panel-bg)
        }
        select {
          font-family: "Fira Code", monospace;
<<<<<<< HEAD
=======
          background: var(--bg);
>>>>>>> dev-vera-ollama-fixed
          color: var(--text-inverted);
        }
        input {
          font-family: "Fira Code", monospace;
          color: var(--text-inverted);
          background: var(--bg-surface);
        }
        textarea {
          font-family: "Fira Code", monospace;
          color: var(--text-inverted);
          background: var(--bg-surface);
        }
        
        .tab.active {
          background: var(--accent);
          color: var(--text-inverted);
          font-weight: bold;
        }
<<<<<<< HEAD
        
=======
        .tab-content {
          background: var(--bg);
          color: var(--text-inverted);
          font-weight: bold;
        }
>>>>>>> dev-vera-ollama-fixed
        .memoryQuery {
          background: var(--panel-bg);
          border-radius: 8px;
          padding: 16px;
          border-left: 4px solid var(--accent);
        }
        
        .focusContent {
          background: var(--panel-bg);
          border-radius: 8px;
          padding: 16px;
        }
        
        .tool-card {
          background: var(--panel-bg);
          border: 1px solid var(--border);
          border-radius: 8px;
          padding: 12px;
        }
        
        .tool-subcard {
          background: var(--bg);
          border: 1px solid var(--border);
          border-radius: 8px;
          padding: 12px;
        }
        
        .tool-container {
          background: var(--panel-bg);
          border: 1px solid var(--border);
          border-radius: 8px;
          padding: 12px;
        }
        memory-content{
          background: var(--panel-bg);
          border: 1px solid var(--border);
          border-radius: 8px;
          padding: 12px;
        }
        .chat-panel, .graph-panel {
          background: var(--panel-bg);
          border: 1px solid var(--border);
          box-shadow: none;
          padding: 12px;
          font-family: "Fira Code", monospace;
          font-size: 13px;
        }

        #chatMessages {
          background: var(--panel-bg);
          color: var(--text);
          display: block;
          white-space: pre-wrap;
          font-family: "Fira Code", monospace;
          font-size: 13px;
          line-height: 1.4;
          padding: 12px;
          overflow-y: auto;
          max-height: 100%;
        }

        .message {
          display: block;
          margin: 0;
          padding: 0;
        }

        .message.user .message-content {
          color: var(--user-text);
        }

        .message-content {
          display: inline;
          background: none !important;
          border: none;
          padding: 0;
          margin: 0;
          font-family: "Fira Code", monospace;
          font-size: 13px;
          line-height: 1.4;
        }

        .input-area {
          background: var(--panel-bg);
          border-top: 1px solid var(--border);
          padding: 8px;
        }

        #messageInput {
          width: 100%;
          background: var(--panel-bg);
          color: var(--text);
          border: 1px solid var(--border);
          font-family: "Fira Code", monospace;
          font-size: 13px;
          caret-color: var(--caret);
          resize: none;
          padding: 6px 8px;
        }

        #messageInput::placeholder {
          color: #006633;
        }

        .send-btn {
          background: #002200;
          color: var(--text);
          border: 1px solid var(--border);
          font-family: "Fira Code", monospace;
          padding: 6px 12px;
          text-transform: uppercase;
        }

        .send-btn:hover {
          background: #003300;
        }

        #graph { background: var(--panel-bg); }

        ::-webkit-scrollbar-thumb { background: #004400; }

        @keyframes blink {
          0%, 50% { opacity: 1; }
          50.1%, 100% { opacity: 0; }
        }

        #messageInput:focus::after {
          content: "_";
          display: inline-block;
          animation: blink 1s infinite;
          color: var(--caret);
        }
        
        .toolchain-box {
          background: var(--panel-bg);
          color: var(--text);
          border-radius: 8px;
          padding: 16px;
          border-left: 4px solid var(--accent);
        }
        .tool-type-filter{
          background: var(--panel-bg)
          color: var(--text)
        }
<<<<<<< HEAD
=======
        
        .search-result-item{
          background: var(--panel-bg)
        }
        .graph-stats{
            background: var(--bg);
            color: var(--text);
        }
        .memory-search-container{
            background: var(--bg);
        }
        .advanced-filters-content{
          background: var(--panel-bg);
        }
        .action-btn{
          color: var(--text)
        }
>>>>>>> dev-vera-ollama-fixed
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
      css: `
        @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&family=Crimson+Text:wght@400;600&display=swap');
        
        :root {
          --bg: #111;
          --bg-surface: #111;
          --panel-bg: #141414;
          --text: #e8e6e3;
          --accent: #f5f5f5;
<<<<<<< HEAD
=======
          --accent-muted: #f5f5f5d5;
>>>>>>> dev-vera-ollama-fixed
          --border: #333;
          --hover: #555;
          --text-inverted: #000000;
        }

        body {
          background: var(--bg);
          color: var(--text);
          font-family: 'Crimson Text', serif;
          line-height: 1.8;
          font-size: 16px;
          text-rendering: optimizeLegibility;
        }

        h1, h2, h3 { 
          color: var(--accent); 
          font-family: 'Playfair Display', serif;
        }

        .tab.active {
          background: var(--accent);
          color: var(--text-inverted);
          font-weight: bold;
        }
<<<<<<< HEAD

        button {
          font-family: 'Playfair Display', serif;
          color: var(--text-inverted);
          background: var(--panel-bg)
        }
        
        select {
          font-family: 'Playfair Display', serif;
          color: var(--text-inverted);
        }
        
        input {
          font-family: 'Crimson Text', serif;
          color: var(--text-inverted);
          background: var(--bg-surface);
        }
        
        textarea {
          font-family: 'Crimson Text', serif;
          color: var(--text-inverted);
          background: var(--bg-surface);
        }
        memory-content{
          background: var(--panel-bg);
          border-radius: 8px;
          padding: 16px;
        }
        .memoryQuery {
          background: var(--panel-bg);
          border-radius: 8px;
          padding: 16px;
          border-left: 4px solid var(--accent);
        }
        
        .focusContent {
          background: var(--panel-bg);
          border-radius: 8px;
          padding: 16px;
        }
        
        .tool-card {
          background: var(--panel-bg);
          border: 1px solid var(--border);
          border-radius: 8px;
          padding: 12px;
          border-left: 4px solid var(--accent);
        }
        
        .tool-subcard {
          background: var(--bg);
          border: 1px solid var(--border);
          border-radius: 8px;
          padding: 12px;
        }
        
        .tool-container {
          background: var(--panel-bg);
          border: 1px solid var(--border);
          border-radius: 8px;
          padding: 12px;
        }
        
        .chat-panel, .graph-panel {
          background: var(--bg);
          border: 1px solid var(--border);
          box-shadow: inset 0 0 10px rgba(255,255,255,0.05);
        }

        #chatMessages {
          background: var(--bg);
          color: var(--text);
          display: flex;
          flex-direction: column;
          gap: 20px;
        }

        .message-content {
          background: #181818;
          color: var(--text);
          border-left: 3px solid #555;
          padding: 14px 18px;
          font-family: 'Playfair Display', serif;
        }

        .message.user .message-content {
          background: #202020;
          border-left-color: #666;
        }

        #messageInput {
          background: #1a1a1a;
          color: #f0f0f0;
          border: 1px solid #333;
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

        body::before {
          content: "";
          position: fixed;
          top: 0; left: 0; right: 0; bottom: 0;
          background: url('https://www.transparenttextures.com/patterns/paper-fibers.png');
          opacity: 0.05;
          pointer-events: none;
          z-index: 9999;
        }
        
        .toolchain-box {
          background: var(--panel-bg);
          color: var(--text);
          border-radius: 8px;
          padding: 16px;
          border-left: 4px solid var(--accent);
        }
        .tool-type-filter{
          background: var(--panel-bg)
          color: var(--text)
        }
      `,
      graph: {
        nodeBorder: '#e8e6e3',
        nodeBackground: '#1a1a1a',
        nodeHighlight: '#f5f5f5',
        nodeFont: '#e8e6e3',
        nodeFontSize: 15,
        edgeColor: '#b9b9b9ff',
        edgeHighlight: '#e8e6e3',
        background: '#111111',
        fontFamily: '"Crimson Text", "Georgia", serif'
      }
    },

    pixelArt: {
      css: `
        @import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap');

        :root {
          --bg: #0d0d1a;
          --bg-surface: #0d0d1a;
          --panel-bg: #1a0d2f;
          --text: #66f0ff;
          --accent: #ff33cc;
          --hover: #9b00ff;
          --border: #440066;
          --user-text: #ff77ff;
          --text-inverted: #000000;
        }

        body {
          background: var(--bg);
          color: var(--text);
          font-family: 'Press Start 2P', monospace;
          font-size: 12px;
          image-rendering: pixelated;
          letter-spacing: 0.05em;
          transition: background 0.3s, color 0.3s;
        }

        h1, h2, h3 {
          color: var(--accent);
          text-shadow: 2px 2px #000;
        }
        
        button {
          font-family: 'Press Start 2P', monospace;
          color: var(--text-inverted);
          background: var(--panel-bg)
        }
        
        select {
          font-family: 'Press Start 2P', monospace;
          color: var(--text-inverted);
        }
        
        input {
          font-family: 'Press Start 2P', monospace;
          color: var(--text-inverted);
          background: var(--bg-surface);
        }
        
        textarea {
          font-family: 'Press Start 2P', monospace;
          color: var(--text-inverted);
          background: var(--bg-surface);
        }
        
        a {
          color: var(--accent);
          text-decoration: underline;
        }
        
        .tab.active {
          background: var(--accent);
          color: var(--text-inverted);
          font-weight: bold;
        }
        memory-content{
=======
        .tab-content {
          background: var(--bg);
          color: var(--text-inverted);
          font-weight: bold;
        }
        button {
          font-family: 'Playfair Display', serif;
          color: var(--text-inverted);
          background: var(--panel-bg)
        }
        
        select {
          font-family: 'Playfair Display', serif;
          background: var(--bg);
          color: var(--text-inverted);
        }
        
        input {
          font-family: 'Crimson Text', serif;
          color: var(--text-inverted);
          background: var(--bg-surface);
        }
        
        textarea {
          font-family: 'Crimson Text', serif;
          color: var(--text-inverted);
          background: var(--bg-surface);
        }
        memory-content{
          background: var(--panel-bg);
          border-radius: 8px;
          padding: 16px;
        }
        .memoryQuery {
          background: var(--panel-bg);
          border-radius: 8px;
          padding: 16px;
          border-left: 4px solid var(--accent);
        }
        
        .focusContent {
          background: var(--panel-bg);
          border-radius: 8px;
          padding: 16px;
        }
        
        .tool-card {
          background: var(--panel-bg);
          border: 1px solid var(--border);
          border-radius: 8px;
          padding: 12px;
          border-left: 4px solid var(--accent);
        }
        
        .tool-subcard {
          background: var(--bg);
          border: 1px solid var(--border);
          border-radius: 8px;
          padding: 12px;
        }
        
        .tool-container {
          background: var(--panel-bg);
          border: 1px solid var(--border);
          border-radius: 8px;
          padding: 12px;
        }
        
        .chat-panel, .graph-panel {
          background: var(--bg);
          border: 1px solid var(--border);
          box-shadow: inset 0 0 10px rgba(255,255,255,0.05);
        }

        #chatMessages {
          background: var(--bg);
          color: var(--text);
          display: flex;
          flex-direction: column;
          gap: 20px;
        }

        .message-content {
          background: #181818;
          color: var(--text);
          border-left: 3px solid #555;
          padding: 14px 18px;
          font-family: 'Playfair Display', serif;
        }

        .message.user .message-content {
          background: #202020;
          border-left-color: #666;
        }

        #messageInput {
          background: #1a1a1a;
          color: #f0f0f0;
          border: 1px solid #333;
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

        body::before {
          content: "";
          position: fixed;
          top: 0; left: 0; right: 0; bottom: 0;
          background: url('https://www.transparenttextures.com/patterns/paper-fibers.png');
          opacity: 0.05;
          pointer-events: none;
          z-index: 9999;
        }
        
        .toolchain-box {
          background: var(--panel-bg);
          color: var(--text);
          border-radius: 8px;
          padding: 16px;
          border-left: 4px solid var(--accent);
        }
        .tool-type-filter{
          background: var(--panel-bg)
          color: var(--text)
        }
        .search-result-item{
          background: var(--panel-bg)
        }
        .graph-stats{
            background: var(--bg);
            color: var(--text);
        }
        .memory-search-container{
            background: var(--bg);
        }
        .advanced-filters-content{
          background: var(--panel-bg);
        }
        .action-btn{
          color: var(--text)
        }
      `,
      graph: {
        nodeBorder: '#e8e6e3',
        nodeBackground: '#1a1a1a',
        nodeHighlight: '#f5f5f5',
        nodeFont: '#e8e6e3',
        nodeFontSize: 15,
        edgeColor: '#b9b9b9ff',
        edgeHighlight: '#e8e6e3',
        background: '#111111',
        fontFamily: '"Crimson Text", "Georgia", serif'
      }
    },

    pixelArt: {
      css: `
        @import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap');

        :root {
          --bg: #0d0d1a;
          --bg-surface: #2a2a55ff;
          --panel-bg: #29144bff;
          --text: #66f0ff;
          --accent: #ff33cc;
          --accent-muted: #ff33ccad;
          --hover: #9b00ff;
          --border: #440066;
          --user-text: #ff77ff;
          --text-inverted: #000000;
        }

        body {
          background: var(--bg);
          color: var(--text);
          font-family: 'Press Start 2P', monospace;
          font-size: 12px;
          image-rendering: pixelated;
          letter-spacing: 0.05em;
          transition: background 0.3s, color 0.3s;
        }

        h1, h2, h3 {
          color: var(--accent);
          text-shadow: 2px 2px #000;
        }
        
        button {
          font-family: 'Press Start 2P', monospace;
          color: var(--text-inverted);
          background: var(--panel-bg)
        }
        
        select {
          font-family: 'Press Start 2P', monospace;
          background: var(--bg);
          color: var(--text-inverted);
        }
        
        input {
          font-family: 'Press Start 2P', monospace;
          color: var(--text-inverted);
          background: var(--bg-surface);
        }
        
        textarea {
          font-family: 'Press Start 2P', monospace;
          color: var(--text-inverted);
          background: var(--bg-surface);
        }
        
        a {
          color: var(--accent);
          text-decoration: underline;
        }
        
        .tab.active {
          background: var(--accent);
          color: var(--text-inverted);
          font-weight: bold;
        }
        memory-content{
          background: var(--panel-bg);
          border-radius: 8px;
          padding: 16px;
        }
        .memoryQuery {
          background: var(--panel-bg);
          border-radius: 8px;
          padding: 16px;
          border-left: 4px solid var(--accent);
        }

        .focusContent {
>>>>>>> dev-vera-ollama-fixed
          background: var(--panel-bg);
          border-radius: 8px;
          padding: 16px;
        }
<<<<<<< HEAD
        .memoryQuery {
          background: var(--panel-bg);
          border-radius: 8px;
          padding: 16px;
          border-left: 4px solid var(--accent);
        }

        .focusContent {
          background: var(--panel-bg);
          border-radius: 8px;
          padding: 16px;
        }
        
        .tool-card {
          background: var(--panel-bg);
          border: 1px solid var(--border);
          border-radius: 8px;
          padding: 12px;
        }
        
        .tool-subcard {
          background: var(--bg);
          border: 1px solid var(--border);
          border-radius: 8px;
          padding: 12px;
        }
        
        .tool-container {
          background: var(--panel-bg);
          border: 1px solid var(--border);
          border-radius: 8px;
          padding: 12px;
        }
        
        .chat-panel, .graph-panel {
          background: var(--bg);
          border: 2px solid var(--border);
          box-shadow: 0 0 12px var(--accent);
          padding: 12px;
          overflow: hidden;
          image-rendering: pixelated;
        }

        #chatMessages {
          background: var(--bg);
          color: var(--text);
          padding: 16px;
          display: flex;
          flex-direction: column;
          gap: 12px;
          overflow-y: auto;
          font-size: 12px;
          line-height: 1.2;
        }

        .message {
          display: flex;
          gap: 8px;
          align-items: flex-start;
        }

        .message-avatar {
          width: 28px;
          height: 28px;
          background: #220022;
          border: 2px solid var(--accent);
          color: var(--accent);
          font-size: 10px;
          display: flex;
          align-items: center;
          justify-content: center;
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
          color: var(--text);
          padding: 10px 12px;
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
          background: var(--panel-bg);
          border-top: 2px solid var(--border);
          padding: 10px;
        }

        #messageInput {
          width: 100%;
          background: #110022;
          color: var(--text);
          border: 2px solid var(--accent);
          font-family: 'Press Start 2P', monospace;
          padding: 10px;
          font-size: 11px;
          resize: none;
          outline: none;
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
          font-family: 'Press Start 2P', monospace;
          text-transform: uppercase;
          padding: 10px 16px;
          cursor: pointer;
          transition: all 0.2s ease;
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

        ::-webkit-scrollbar {
          width: 8px;
        }

        ::-webkit-scrollbar-thumb {
          background: var(--accent);
          border-radius: 2px;
        }

        @keyframes neonFlicker {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.95; }
          25%, 75% { opacity: 0.97; }
        }
        
        body {
          animation: neonFlicker 0.1s infinite;
        }

=======
        
        .tool-card {
          background: var(--panel-bg);
          border: 1px solid var(--border);
          border-radius: 8px;
          padding: 12px;
        }
        
        .tool-subcard {
          background: var(--bg);
          border: 1px solid var(--border);
          border-radius: 8px;
          padding: 12px;
        }
        
        .tool-container {
          background: var(--panel-bg);
          border: 1px solid var(--border);
          border-radius: 8px;
          padding: 12px;
        }
        
        .chat-panel, .graph-panel {
          background: var(--bg);
          border: 2px solid var(--border);
          box-shadow: 0 0 12px var(--accent);
          padding: 12px;
          overflow: hidden;
          image-rendering: pixelated;
        }

        #chatMessages {
          background: var(--bg);
          color: var(--text);
          padding: 16px;
          display: flex;
          flex-direction: column;
          gap: 12px;
          overflow-y: auto;
          font-size: 12px;
          line-height: 1.2;
        }

        .message {
          display: flex;
          gap: 8px;
          align-items: flex-start;
        }

        .message-avatar {
          width: 28px;
          height: 28px;
          background: #220022;
          border: 2px solid var(--accent);
          color: var(--accent);
          font-size: 10px;
          display: flex;
          align-items: center;
          justify-content: center;
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
          color: var(--text);
          padding: 10px 12px;
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
          background: var(--panel-bg);
          border-top: 2px solid var(--border);
          padding: 10px;
        }

        #messageInput {
          width: 100%;
          background: #110022;
          color: var(--text);
          border: 2px solid var(--accent);
          font-family: 'Press Start 2P', monospace;
          padding: 10px;
          font-size: 11px;
          resize: none;
          outline: none;
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
          font-family: 'Press Start 2P', monospace;
          text-transform: uppercase;
          padding: 10px 16px;
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .send-btn:hover {
          background: var(--hover);
          color: #fff;
          box-shadow: 0 0 12px var(--accent);
        }
        .tab-content {
          background: var(--bg);
          color: var(--text-inverted);
          font-weight: bold;
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

        ::-webkit-scrollbar {
          width: 8px;
        }

        ::-webkit-scrollbar-thumb {
          background: var(--accent);
          border-radius: 2px;
        }

        @keyframes neonFlicker {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.95; }
          25%, 75% { opacity: 0.97; }
        }
        
        body {
          animation: neonFlicker 0.1s infinite;
        }

>>>>>>> dev-vera-ollama-fixed
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
        
        .toolchain-box {
          background: var(--panel-bg);
          color: var(--text);
          border-radius: 8px;
          padding: 16px;
          border-left: 4px solid var(--accent);
        }
        .tool-type-filter{
          background: var(--panel-bg)
          color: var(--text)
        }
<<<<<<< HEAD
=======
        .search-result-item{
          background: var(--panel-bg)
        }
        .graph-stats{
            background: var(--bg);
            color: var(--text);
        }
        .memory-search-container{
            background: var(--bg);
        }
        .advanced-filters-content{
          background: var(--panel-bg);
        }  
        .action-btn{
          color: var(--text)
        } 
>>>>>>> dev-vera-ollama-fixed
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
      css: `
        @import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap');

        :root {
          --bg: #000;
<<<<<<< HEAD
          --panel-bg: #000;
          --text: #00ffcc;
          --accent: #ff0077;
          --border: #00ffcc;
        }

        body {
          background: radial-gradient(circle at center, #101010 0%, #000 100%);
          color: var(--text);
          font-family: 'Press Start 2P', monospace;
          font-size: 11px;
          text-transform: uppercase;
          image-rendering: pixelated;
        }
        button{
          font-family: 'Press Start 2P', monospace;
          background: var(--panel-bg)
        }
        .message-content {
          background: rgba(0, 0, 0, 0.7);
          border: 2px solid var(--border);
=======
          --bg-surface: #000;
          --panel-bg: #000;
          --text: #00ffcc;
          --accent: #ff0077;
          --accent-muted: #ca4a86b4;
          --hover: #ff3794ff;
          --border: #00ffcc;
          --user-text: #ff3794ff;
          --text-inverted: #ff0077;
        }
        header{
          background: var(--bg)
        }
        body {
          background: radial-gradient(circle at center, #101010 0%, #000 100%);
          color: var(--text);
          font-family: 'Press Start 2P', monospace;
          font-size: 11px;
          text-transform: uppercase;
          image-rendering: pixelated;
        }

        button {
          font-family: 'Press Start 2P', monospace;
          color: var(--text-inverted);
          background: var(--panel-bg)
        }
        
        select {
          font-family: 'Press Start 2P', monospace;
          background: var(--bg);
          color: var(--text-inverted);
        }
        
        input {
          font-family: 'Press Start 2P', monospace;
          color: var(--text-inverted);
          background: var(--bg-surface);
        }
        
        textarea {
          font-family: 'Press Start 2P', monospace;
          color: var(--text-inverted);
          background: var(--bg-surface);
        }
        
        a {
          color: var(--accent);
          text-decoration: underline;
        }
        
        .tab.active {
          background: var(--accent);
          color: var(--text-inverted);
          font-weight: bold;
        }
        .tab-content {
          background: var(--bg);
          color: var(--text-inverted);
          font-weight: bold;
        }
        memory-content{
          background: var(--panel-bg);
          border-radius: 8px;
          padding: 16px;
        }
        .memoryQuery {
          background: var(--panel-bg);
          border-radius: 8px;
          padding: 16px;
          border-left: 4px solid var(--accent);
        }

        .focusContent {
          background: var(--panel-bg);
          border-radius: 8px;
          padding: 16px;
        }
        
        .tool-card {
          background: var(--panel-bg);
          border: 1px solid var(--border);
          border-radius: 8px;
          padding: 12px;
        }
        
        .tool-subcard {
          background: var(--bg);
          border: 1px solid var(--border);
          border-radius: 8px;
          padding: 12px;
        }
        
        .tool-container {
          background: var(--panel-bg);
          border: 1px solid var(--border);
          border-radius: 8px;
          padding: 12px;
        }
        
        .chat-panel, .graph-panel {
          background: var(--bg);
          border: 2px solid var(--border);
          box-shadow: 0 0 12px var(--accent);
          padding: 12px;
          overflow: hidden;
          image-rendering: pixelated;
        }

        #chatMessages {
          background: var(--bg);
          color: var(--text);
          padding: 16px;
          display: flex;
          flex-direction: column;
          gap: 12px;
          overflow-y: auto;
          font-size: 12px;
          line-height: 1.2;
        }

        .message {
          display: flex;
          gap: 8px;
          align-items: flex-start;
        }

        .message-avatar {
          width: 28px;
          height: 28px;
          background: #220022;
          border: 2px solid var(--accent);
          color: var(--accent);
          font-size: 10px;
          display: flex;
          align-items: center;
          justify-content: center;
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
          color: var(--text);
          padding: 10px 12px;
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
          background: var(--panel-bg);
          border-top: 2px solid var(--border);
          padding: 10px;
>>>>>>> dev-vera-ollama-fixed
        }
        memory-content{
          background: var(--panel-bg);
          border-radius: 8px;
          padding: 16px;
        }
        @keyframes crtFlicker {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.98; }
        }
        body { animation: crtFlicker 0.1s infinite; }
        .tool-type-filter{
          background: var(--panel-bg)
          color: var(--text)
        }
        .tool-type-filter{
          background: var(--panel-bg)
          color: var(--text)
        }
<<<<<<< HEAD
=======
        .search-result-item{
          background: var(--panel-bg)
        }
        .graph-stats{
            background: var(--bg);
            color: var(--text);
        }
        .memory-search-container{
            background: var(--bg);
        }
        .advanced-filters-content{
          background: var(--panel-bg);
        }
        .action-btn{
          color: var(--text)
        }
>>>>>>> dev-vera-ollama-fixed
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
      css: `
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        
        :root {
          --bg: #2b1a2f;
          --bg-surface: #3e2a45;
          --panel-bg: #593964;
          --text: #ffd8a8;
          --accent: #ff6f61;
<<<<<<< HEAD
          --hover: #ffa07a;
          --border: #7e5a7e;
          --user-text: #ffb347;
          --text-inverted: #000000;
=======
          --accent-muted: #ff6f61;
          --hover: #ffa07a;
          --border: #7e5a7e;
          --user-text: #ffb347;
          --text-inverted: #ffffffff;
>>>>>>> dev-vera-ollama-fixed
        }

        body {
          background: var(--bg);
          color: var(--text);
          font-family: 'Share Tech Mono', 'Segoe UI', sans-serif;
          height: 100vh;
          overflow: hidden;
          transition: background 0.3s, color 0.3s;
        }

        a { color: var(--accent); }

        h1, h2, h3 { color: var(--accent); }

        button {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          color: var(--text-inverted);
          background: var(--panel-bg)
        }
        
        select {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
<<<<<<< HEAD
=======
          background: var(--bg);
>>>>>>> dev-vera-ollama-fixed
          color: var(--text-inverted);
        }
        
        input {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          color: var(--text-inverted);
          background: var(--bg-surface);
        }
        
        textarea {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          color: var(--text-inverted);
          background: var(--bg-surface);
        }

        .tab.active {
          background: var(--accent);
          color: var(--text-inverted);
          font-weight: bold;
        }
        memory-content{
          background: var(--panel-bg);
          border-radius: 8px;
          padding: 16px;
        }
        .memoryQuery {
          background: var(--panel-bg);
          border-radius: 8px;
          padding: 16px;
          border-left: 4px solid var(--accent);
        }
        
        .focusContent {
          background: var(--panel-bg);
          border-radius: 8px;
          padding: 16px;
        }

        .tool-card {
          background: var(--panel-bg);
          border: 1px solid var(--border);
          border-radius: 8px;
          padding: 12px;
        }
        
        .tool-subcard {
          background: var(--bg);
          border: 1px solid var(--border);
          border-radius: 8px;
          padding: 12px;
        }
        
        .tool-container {
          background: var(--panel-bg);
          border: 1px solid var(--border);
          border-radius: 8px;
          padding: 12px;
        }
        
        .chat-panel, .graph-panel {
          background: var(--bg);
          border: 1px solid var(--border);
          box-shadow: inset 0 0 10px rgba(0,0,0,0.2);
        }

        #chatMessages {
          background: var(--bg);
          color: var(--text);
        }

        .message-content {
          background: rgba(255, 200, 160, 0.1);
          color: var(--text);
          padding: 12px 16px;
          border-radius: 8px;
          border-left: 3px solid var(--border);
        }

        .message.user .message-content {
          background: rgba(255, 175, 100, 0.2);
          border-left-color: var(--user-text);
          color: var(--user-text);
        }

        .send-btn {
          background: var(--accent);
          color: white;
          border-radius: 6px;
        }

        #messageInput {
          background: var(--panel-bg);
          color: var(--text);
          border: 1px solid var(--border);
          transition: border 0.2s;
        }

        #messageInput:focus {
          border-color: var(--accent);
        }

        ::-webkit-scrollbar-thumb { 
          background: var(--border); 
        }

        .chat-panel, .graph-panel, #messageInput {
          transition: background 0.3s, color 0.3s, border 0.3s;
        }
        
        .toolchain-box {
          background: var(--panel-bg);
          color: var(--text);
          border-radius: 8px;
          padding: 16px;
          border-left: 4px solid var(--accent);
        }
        .tool-type-filter{
          background: var(--panel-bg)
          color: var(--text)
        }
<<<<<<< HEAD
=======
        .search-result-item{
          background: var(--panel-bg)
        }
        .graph-stats{
            background: var(--bg);
            color: var(--text);
        }
        .memory-search-container{
            background: var(--bg);
        }
        .advanced-filters-content{
          background: var(--panel-bg);
        }
        .action-btn{
          color: var(--text)
        }
>>>>>>> dev-vera-ollama-fixed
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
    }
  };

  // --- Apply theme to graph ---
  const applyThemeToGraph = (themeName) => {
    if (!window.network) {
      console.log('Network not ready, will retry...');
      return;
    }
    
    const theme = themes[themeName];
    if (!theme) return;

    const graphConfig = theme.graph;

    console.log('Applying theme to graph:', themeName, graphConfig);

    // Update network options
    window.network.setOptions({
      nodes: {
        shape: graphConfig.nodeShape || 'dot',
        size: 25,
        color: {
          border: graphConfig.nodeBorder,
          background: graphConfig.nodeBackground,
          highlight: {
            border: graphConfig.nodeHighlight,
            background: graphConfig.nodeBackground
          },
          hover: {
            border: graphConfig.nodeHighlight,
            background: graphConfig.nodeBackground
          }
        },
        font: {
          color: graphConfig.nodeFont,
          size: graphConfig.nodeFontSize,
          face: graphConfig.fontFamily
        },
        borderWidth: 2,
        borderWidthSelected: 3
      },
      edges: {
        color: {
          color: graphConfig.edgeColor,
          highlight: graphConfig.edgeHighlight,
          hover: graphConfig.edgeHighlight
        },
        width: graphConfig.edgeWidth || 2,
        font: {
          color: graphConfig.nodeFont,
          size: graphConfig.nodeFontSize - 2,
          face: graphConfig.fontFamily,
          strokeWidth: 0
        },
        smooth: {
          enabled: true,
          type: 'dynamic'
        }
      }
    });

    // Update background
    window.network.body.container.style.background = graphConfig.background;

    // Update existing nodes to use theme colors
    try {
      const nodes = window.network.body.data.nodes.get();
      const nodeUpdates = nodes.map(node => ({
        id: node.id,
        color: {
          border: graphConfig.nodeBorder,
          background: graphConfig.nodeBackground,
          highlight: {
            border: graphConfig.nodeHighlight,
            background: graphConfig.nodeBackground
          },
          hover: {
            border: graphConfig.nodeHighlight,
            background: graphConfig.nodeBackground
          }
        },
        font: {
          color: graphConfig.nodeFont,
          size: graphConfig.nodeFontSize,
          face: graphConfig.fontFamily
        }
      }));
      
      window.network.body.data.nodes.update(nodeUpdates);
      console.log(`Updated ${nodeUpdates.length} nodes`);
    } catch (e) {
      console.warn('Error updating nodes:', e);
    }

    // Update edges
    try {
      const edges = window.network.body.data.edges.get();
      const edgeUpdates = edges.map(edge => ({
        id: edge.id,
        color: {
          color: graphConfig.edgeColor,
          highlight: graphConfig.edgeHighlight,
          hover: graphConfig.edgeHighlight
        },
        width: graphConfig.edgeWidth || 2,
        font: {
          color: graphConfig.nodeFont,
          size: graphConfig.nodeFontSize - 2,
          face: graphConfig.fontFamily
        }
      }));
      
      window.network.body.data.edges.update(edgeUpdates);
      console.log(`Updated ${edgeUpdates.length} edges`);
    } catch (e) {
      console.warn('Error updating edges:', e);
    }

    window.network.redraw();
  };

  // --- Apply custom colors to graph ---
  const applyCustomColorsToGraph = (colors) => {
    if (!window.network) return;

    console.log('Applying custom colors:', colors);

    window.network.setOptions({
      nodes: {
        color: {
          border: colors.nodeBorder,
          background: colors.nodeBackground,
          highlight: {
            border: colors.nodeHighlight,
            background: colors.nodeBackground
          },
          hover: {
            border: colors.nodeHighlight,
            background: colors.nodeBackground
          }
        },
        font: {
          color: colors.nodeFont,
          size: colors.fontSize
        }
      },
      edges: {
        color: {
          color: colors.edgeColor,
          highlight: colors.edgeColor,
          hover: colors.edgeColor
        },
        font: {
          color: colors.nodeFont,
          size: colors.fontSize - 2
        }
      }
    });

    window.network.body.container.style.background = colors.background;

    // Update all nodes
    try {
      const nodes = window.network.body.data.nodes.get();
      const nodeUpdates = nodes.map(node => ({
        id: node.id,
        color: {
          border: colors.nodeBorder,
          background: colors.nodeBackground,
          highlight: {
            border: colors.nodeHighlight,
            background: colors.nodeBackground
          }
        },
        font: {
          color: colors.nodeFont,
          size: colors.fontSize
        }
      }));
      window.network.body.data.nodes.update(nodeUpdates);
    } catch (e) {
      console.warn('Error updating nodes:', e);
    }

    // Update all edges
    try {
      const edges = window.network.body.data.edges.get();
      const edgeUpdates = edges.map(edge => ({
        id: edge.id,
        color: {
          color: colors.edgeColor,
          highlight: colors.edgeColor,
          hover: colors.edgeColor
        },
        font: {
          color: colors.nodeFont,
          size: colors.fontSize - 2
        }
      }));
      window.network.body.data.edges.update(edgeUpdates);
    } catch (e) {
      console.warn('Error updating edges:', e);
    }

    window.network.redraw();
  };

  // --- Initialize theme settings ---
  VeraChat.prototype.initThemeSettings = function () {
    if (document.querySelector("#themeMenu")) return;

    const savedTheme = localStorage.getItem("theme") || "default";

    // Create style element
    const styleEl = document.querySelector('style[data-theme-style]') || document.createElement("style");
    styleEl.setAttribute("data-theme-style", "");
    document.head.appendChild(styleEl);
    if (themes[savedTheme]) {
      styleEl.textContent = themes[savedTheme].css;
    } else {
      console.warn(`Theme "${savedTheme}" not found. Falling back to default theme.`);
      styleEl.textContent = themes["default"].css;
    }

    // Create menu
    const menu = document.createElement("div");
    menu.id = "themeMenu";

    menu.innerHTML = `
      <style>
        #themeMenu {
          background: rgba(0,0,0,0.85);
          color: white;
          padding: 1rem;
          border-radius: 0.6rem;
          font-family: sans-serif;
          font-size: 0.9rem;
          width: 16rem;
          box-shadow: 0 4px 20px rgba(0,0,0,0.5);
        }
        #themeMenu select, #themeMenu input, #themeMenu button {
          background: #222;
          color: white;
          border: 1px solid #444;
          border-radius: 0.3rem;
          padding: 0.4rem;
          margin-top: 0.3rem;
          font-size: 0.85rem;
          width: 100%;
          box-sizing: border-box;
        }
        #themeMenu button:hover { background: #333; cursor: pointer; }
        #themeMenu label { font-size: 0.75rem; opacity: 0.8; margin-top: 0.5rem; display: block; }
        #themeMenu .row { margin-top: 0.5rem; }
        #themeMenu.floating {
          position: fixed;
          z-index: 999999;
          resize: both;
          overflow: auto;
          cursor: grab;
        }
        #themeMenu.dragging { opacity: 0.8; cursor: grabbing; }
        #themeMenu h4 {
          margin: 0 0 0.8rem 0;
          font-size: 1.1rem;
          text-align: center;
          border-bottom: 1px solid #444;
          padding-bottom: 0.5rem;
        }
        #themeMenu .section {
          margin-top: 1rem;
          padding-top: 0.8rem;
          border-top: 1px solid #333;
        }
        #themeMenu .section-title {
          font-size: 0.8rem;
          opacity: 0.6;
          text-transform: uppercase;
          margin-bottom: 0.5rem;
        }
      </style>

      <h4>🎨 Theme Settings</h4>
      
      <label>Theme Preset</label>
      <select id="themeSelect">${Object.keys(themes)
        .map(t => `<option value="${t}" ${t === savedTheme ? "selected" : ""}>${t}</option>`)
        .join("")}</select>

      <div class="section">
        <div class="section-title">Graph Colors</div>
        <div class="row"><label>Node Border:</label><input type="color" id="nodeBorderColor"></div>
        <div class="row"><label>Node Background:</label><input type="color" id="nodeBgColor"></div>
        <div class="row"><label>Node Highlight:</label><input type="color" id="nodeHighlightColor"></div>
        <div class="row"><label>Edge Color:</label><input type="color" id="edgeColor"></div>
        <div class="row"><label>Background:</label><input type="color" id="graphBgColor"></div>
      </div>

      <div class="section">
        <div class="section-title">Typography</div>
        <div class="row"><label>Node Font Size:</label><input type="number" id="nodeFontSize" min="8" max="24" value="14"></div>
      </div>

      <button id="resetThemeBtn">🔄 Reset to Preset</button>
      <button id="applyThemeBtn">✓ Apply to Graph</button>
      <button id="popThemeBtn">↗ Pop Out</button>
    `;

    const settingsContainer = document.getElementById("theme-settings") || document.body;
    settingsContainer.appendChild(menu);

    // References
    const selector = menu.querySelector("#themeSelect");
    const nodeBorderInput = menu.querySelector("#nodeBorderColor");
    const nodeBgInput = menu.querySelector("#nodeBgColor");
    const nodeHighlightInput = menu.querySelector("#nodeHighlightColor");
    const edgeInput = menu.querySelector("#edgeColor");
    const graphBgInput = menu.querySelector("#graphBgColor");
    const nodeFontSizeInput = menu.querySelector("#nodeFontSize");
    const resetBtn = menu.querySelector("#resetThemeBtn");
    const applyBtn = menu.querySelector("#applyThemeBtn");
    const popBtn = menu.querySelector("#popThemeBtn");

    // Drag functionality
    let isDragging = false, offsetX = 0, offsetY = 0;
    menu.addEventListener("mousedown", e => {
      if (!menu.classList.contains("floating")) return;
      isDragging = true;
      offsetX = e.clientX - menu.getBoundingClientRect().left;
      offsetY = e.clientY - menu.getBoundingClientRect().top;
      menu.classList.add("dragging");
      e.preventDefault();
    });
    document.addEventListener("mousemove", e => {
      if (!isDragging) return;
      menu.style.left = `${e.clientX - offsetX}px`;
      menu.style.top = `${e.clientY - offsetY}px`;
    });
    document.addEventListener("mouseup", () => {
      isDragging = false;
      menu.classList.remove("dragging");
    });

    // Floating/docking
    const overlay = document.getElementById("floating-widgets") || (() => {
      const d = document.createElement("div");
      d.id = "floating-widgets";
      d.style.cssText = "position:fixed;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:999999;";
      document.body.appendChild(d);
      return d;
    })();

    const makeFloating = () => {
      if (!menu.classList.contains("floating")) {
        overlay.appendChild(menu);
        menu.classList.add("floating");
        menu.style.pointerEvents = "auto";
        menu.style.right = "1rem";
        menu.style.bottom = "1rem";
        popBtn.textContent = "↙ Dock Back";
      }
    };

    const makeDocked = () => {
      if (menu.classList.contains("floating")) {
        settingsContainer.appendChild(menu);
        menu.classList.remove("floating");
        menu.style.cssText = "";
        popBtn.textContent = "↗ Pop Out";
      }
    };

    popBtn.addEventListener("click", () => {
      menu.classList.contains("floating") ? makeDocked() : makeFloating();
    });

    // Update inputs from theme
    const updateInputsFromTheme = (themeName) => {
      const theme = themes[themeName];
      if (!theme) return;
      
      nodeBorderInput.value = theme.graph.nodeBorder;
      nodeBgInput.value = theme.graph.nodeBackground;
      nodeHighlightInput.value = theme.graph.nodeHighlight;
      edgeInput.value = theme.graph.edgeColor;
      graphBgInput.value = theme.graph.background;
      nodeFontSizeInput.value = theme.graph.nodeFontSize;
    };

    // Apply theme
    const applyTheme = (themeName) => {
      const theme = themes[themeName];
      if (!theme) return;
      
      styleEl.textContent = theme.css;
      localStorage.setItem("theme", themeName);
      updateInputsFromTheme(themeName);
      applyThemeToGraph(themeName);
    };

    // Event listeners
    selector.addEventListener("change", e => {
      applyTheme(e.target.value);
    });

    applyBtn.addEventListener("click", () => {
      if (!window.network) {
        alert('Graph network not ready yet');
        return;
      }
      
      const customColors = {
        nodeBorder: nodeBorderInput.value,
        nodeBackground: nodeBgInput.value,
        nodeHighlight: nodeHighlightInput.value,
        edgeColor: edgeInput.value,
        background: graphBgInput.value,
        nodeFont: nodeBorderInput.value, // Use border color for font
        fontSize: parseInt(nodeFontSizeInput.value)
      };
      
      applyCustomColorsToGraph(customColors);
    });

    resetBtn.addEventListener("click", () => {
      applyTheme(selector.value);
    });

    // Initial application
    updateInputsFromTheme(savedTheme);
    applyTheme(savedTheme);

    // Monitor for network ready and apply theme
    let checkAttempts = 0;
    const maxAttempts = 40; // 20 seconds max
    
    const checkAndApplyTheme = () => {
      if (window.network && window.network.body && window.network.body.data) {
        console.log('Network detected, applying theme...');
        applyThemeToGraph(savedTheme);
        return true;
      }
      return false;
    };

    // Try to apply immediately
    if (!checkAndApplyTheme()) {
      // If not ready, poll for network
      const networkInterval = setInterval(() => {
        checkAttempts++;
        
        if (checkAndApplyTheme()) {
          clearInterval(networkInterval);
          console.log('Theme applied after', checkAttempts, 'attempts');
        } else if (checkAttempts >= maxAttempts) {
          clearInterval(networkInterval);
          console.warn('Network not ready after maximum attempts');
        }
      }, 500);
    }

    // Also listen for network data changes (when graph is loaded/updated)
    const originalSetData = window.network ? window.network.setData : null;
    if (window.network && typeof window.network.setData === 'function') {
      const originalFunc = window.network.setData.bind(window.network);
      window.network.setData = function(data) {
        originalFunc(data);
        // Apply theme after data is set
        setTimeout(() => {
          const currentTheme = localStorage.getItem("theme") || "default";
          console.log('Graph data changed, reapplying theme:', currentTheme);
          applyThemeToGraph(currentTheme);
        }, 100);
      };
    }
  };
    const savedTheme = localStorage.getItem("theme") || "default";

    // Create style element
    const styleEl = document.querySelector('style[data-theme-style]') || document.createElement("style");
    styleEl.setAttribute("data-theme-style", "");
    document.head.appendChild(styleEl);
    if (themes[savedTheme]) {
      styleEl.textContent = themes[savedTheme].css;
    } else {
      console.warn(`Theme "${savedTheme}" not found. Falling back to default theme.`);
      styleEl.textContent = themes["default"].css;
    }

  // Export for use
  window.applyThemeToGraph = applyThemeToGraph;
  window.themes = themes;
})();