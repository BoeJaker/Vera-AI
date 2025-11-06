
(() => {
  // --- Define themes ---
  const themes = {
  default: {
    css:`
    :root {
      --bg: #0f172a;
      --bg-surface: #0f172a;
      --panel-bg: #1e293b;
      --text: #e2e8f0;
      --accent: #3b82f6;
      --border: #334155;
      --hover: #475569;
    }
    
    robot: {
      color: '#3b8200';
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
    button {
      color: var(--text-inverted);
    }
    select {
      color: var(--text-inverted);
    }
    input{
      color: var(--text-inverted);
      background: var(--bg-surface);
    }
    textarea{
      color: var(--text-inverted);
      background: var(--bg-surface);
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
    .tool-card{
    background: var(--panel-bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px;
    }
    .tool-subcard{
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px;
    }
    .tool-container{
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

    .message.user .message-content {
      background: #1e3a8a;
    }

    .send-btn {
      background: var(--accent);
      color: white;
    }

    #messageInput {
      background: var(--panel-bg);
      color: var(--text);
      border: 1px solid var(--border);
    }

    ::-webkit-scrollbar-thumb { background: var(--border); }

    .toolchain-box {
        background: var(--panel-bg);
        color: var(--text);
        border-radius: 8px;
        padding: 16px;
        border-left: 4px solid var(--accent);
    }
    `,
    graph: {
      nodeBorder: '#3b82f6',
      nodeBackground: '#1e293b',
      nodeFont: '#e2e8f0',
      edgeColor: '#334155',
      background: '#0f172a'
    }
    
  },
  terminal: {
  css:`
    :root {
      --bg: #000;
      --bg-surface: #000;
      --text: #00ff66;
      --user-text: #00ffaa;
      --panel-bg: #000;
      --border: #00aa44;
      --accent: #00ff66;
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
    }
    select {
      font-family: "Fira Code", monospace;
      color: var(--text-inverted);
    }
    input{
      font-family: "Fira Code", monospace;
      color: var(--text-inverted);
      background: var(--bg-surface);
    }
    textarea{
      font-family: "Fira Code", monospace;
      color: var(--text-inverted);
      background: var(--bg-surface);
    }
    
    .tab.active {
        background: var(--accent);
        color: var(--text-inverted);
        font-weight: bold;
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
    .tool-card{
      background: var(--panel-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px;
    }
    .tool-subcard{
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px;
    }
    .tool-container{
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
  `,  
    graph: {
      nodeBorder: '#00ff66',
      nodeBackground: '#000000',
      nodeFont: '#00ff66',
      edgeColor: '#00aa44',
      background: '#000000'
    }
  },

  darkNewspaper: {
    css:  `
    :root {
      --bg: #111;
      --bg-surface: #111;
      --panel-bg: #141414;
      --text: #e8e6e3;
      --accent: #f5f5f5;
      --border: #333;
      --hover: #555;
      --text-inverted: #000000;
    }

    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&family=Crimson+Text:wght@400;600&display=swap');

    body {
      background: var(--bg);
      color: var(--text);
      font-family: 'Crimson Text', serif;
      line-height: 1.8;
      font-size: 16px;
      text-rendering: optimizeLegibility;
    }

    h1, h2, h3 { color: var(--accent); }

    .tab.active {
    background: var(--accent);
    color: var(--text-inverted);
    font-weight: bold;
    }

    button {
      font-family: 'Playfair Display', serif;
      color: var(--text-inverted);
    }
    select {
      font-family: 'Playfair Display', serif;
      color: var(--text-inverted);
    }
    input{
      font-family: 'Crimson Text', serif;
      color: var(--text-inverted);
      background: var(--bg-surface);
    }
    textarea{
      font-family: 'Crimson Text', serif;
      color: var(--text-inverted);
      background: var(--bg-surface);
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
    .tool-card{
      background: var(--panel-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px;
    }
    .tool-subcard{
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px;
    }
    .tool-container{
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

  `,
    graph: {
      nodeBorder: '#3b82f6',
      nodeBackground: '#1e293b',
      nodeFont: '#e2e8f0',
      edgeColor: '#334155',
      background: '#0f172a'
    }
},
  pixelArt: {
    css:`
    @import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap');

    :root {
        --bg: #0d0d1a;           /* Dark night city background */
        --bg-surface: #0d0d1a; 
        --panel-bg: #1a0d2f;     /* Panel background for chat and graph */
        --text: #66f0ff;         /* Neon cyan text */
        --accent: #ff33cc;       /* Neon pink accent */
        --hover: #9b00ff;        /* Hover effects */
        --border: #440066;       /* Panel borders */
        --user-text: #ff77ff;    /* User messages neon pink */
    }

    @import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap');

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
    }
    select {
      font-family: 'Press Start 2P', monospace;
      color: var(--text-inverted);
    }
    input{
      font-family: 'Press Start 2P', monospace;
      color: var(--text-inverted);
      background: var(--bg-surface);
    }
    textarea{
      font-family: 'Press Start 2P', monospace;
      color: var(--text-inverted);
      background: var(--bg-surface);
    }
    a {
        color: var(--accent);
        text-decoration: underline;
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
    .tool-card{
      background: var(--panel-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px;
    }
    .tool-subcard{
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px;
    }
    .tool-container{
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

    /* Neon flicker animation for the body */
    @keyframes neonFlicker {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.95; }
      25%, 75% { opacity: 0.97; }
    }
    body {
      animation: neonFlicker 0.1s infinite;
    }

    /* Scanline overlay for pixel effect */
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
        nodeBorder: '#66f0ff',
        nodeBackground: '#0d0d1a',
        nodeFont: '#66f0ff',
        edgeColor: '#440066',
        background: '#0d0d1a'
    }
  },
retroGaming: {
    css:`
    @import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap');

    :root {
      --bg: #000;
      --bg-surface: #000; 
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
      letter-spacing: 0.05em;
      text-transform: uppercase;
      image-rendering: pixelated;
    }
    button {
      font-family: 'Press Start 2P', monospace;
      color: var(--text-inverted);
    }
    select {
      font-family: 'Press Start 2P', monospace;
      color: var(--text-inverted);
    }
    input{
      font-family: 'Press Start 2P', monospace;
      color: var(--text-inverted);
      background: var(--bg-surface);
    }
    textarea{
      font-family: 'Press Start 2P', monospace;
      color: var(--text-inverted);
      background: var(--bg-surface);
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
    .tool-card{
        background: var(--panel-bg);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 12px;
    }
    .tool-subcard{
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px;
    }
    .tool-container{
    background: var(--panel-bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px;
    }
    .chat-panel, .graph-panel {
      background: var(--bg);
      border: 2px solid var(--border);
      box-shadow: inset 0 0 8px var(--border);
    }

    #chatMessages {
      background: var(--bg);
      color: var(--text);
    }

    .message-avatar {
      background: #111;
      border: 2px solid var(--border);
      color: var(--text);
      box-shadow: 0 0 8px var(--border);
    }

    .message.assistant .message-avatar {
      border-color: var(--accent);
      color: var(--accent);
      box-shadow: 0 0 8px var(--accent);
    }

    .message-content {
      background: rgba(0, 0, 0, 0.7);
      border: 2px solid var(--border);
      color: var(--text);
    }

    .message.user .message-content {
      border-color: var(--accent);
      color: var(--accent);
    }

    #messageInput {
      background: var(--panel-bg);
      color: var(--text);
      border: 2px solid var(--border);
      font-family: 'Press Start 2P', monospace;
    }

    .send-btn {
      background: var(--panel-bg);
      color: var(--accent);
      border: 2px solid var(--accent);
      font-family: 'Press Start 2P', monospace;
    }

    #graph {
      background: repeating-linear-gradient(to bottom, #000, #000 2px, #001010 3px);
    }

    /* CRT flicker */
    @keyframes crtFlicker {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.98; }
      25%, 75% { opacity: 0.99; }
    }

    body { animation: crtFlicker 0.1s infinite; }

    body::before {
      content: "";
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: repeating-linear-gradient(to bottom, rgba(0,0,0,0.1) 0px, rgba(0,0,0,0.1) 1px, transparent 2px);
      pointer-events: none;
      z-index: 9999;
    }
  `,
    graph: {
        nodeBorder: '#00ffcc',
        nodeBackground: '#000000',
        nodeFont: '#00ffcc',

        edgeColor: '#ff0077',
        background: '#000000'
    }
},
  
sunsetGlow: {
    css:`
    @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
    :root {
        --bg: #2b1a2f;          /* Deep purple background */
        --bg-surface: #3e2a45;  /* Slightly lighter panels */
        --panel-bg: #593964ff;    
        --text: #ffd8a8;        /* Warm light text */
        --accent: #ff6f61;      /* Sunset orange highlights */
        --hover: #ffa07a;       /* Lighter hover effect */
        --border: #7e5a7e;      /* Soft purple borders */
        --user-text: #ffb347;   /* Golden user messages */
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
      font-family:  -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      color: var(--text-inverted);
    }
    select {
      font-family:  -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      color: var(--text-inverted);
    }
    input{
      font-family:  -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      color: var(--text-inverted);
      background: var(--bg-surface);
    }
    textarea{
      font-family:  -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      color: var(--text-inverted);
      background: var(--bg-surface);
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

    .tool-card{
      background: var(--panel-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px;
    }
    .tool-subcard{
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px;
    }
    .tool-container{
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
`,
    graph: {
        nodeBorder: '#ff6f61',
        nodeBackground: '#3e2a45',
        nodeFont: '#ffd8a8',
        edgeColor: '#7e5a7e',
        background: '#2b1a2f'
    }
}
};

  // // --- Create style tag ---
  // const styleEl = document.createElement("style");
  // document.head.appendChild(styleEl);

  // // --- Load saved theme ---
  // const saved = localStorage.getItem("theme") || "default";
  // styleEl.textContent = themes[saved].css;

  // // --- Create floating menu ---
  // const menu = document.createElement("div");
  // menu.innerHTML = `
  //   <style>
  //     #themeMenu {
  //       position: fixed;
  //       bottom: 1rem;
  //       right: 1rem;
  //       background: rgba(0,0,0,0.6);
  //       color: white;
  //       padding: 0.5rem 0.8rem;
  //       border-radius: 0.5rem;
  //       font-family: sans-serif;
  //       font-size: 0.9rem;
  //       z-index: 9999;
  //       transition: all 0.3s;
  //     }
  //     #themeMenu select {
  //       background: #222;
  //       color: white;
  //       border: 1px solid #444;
  //       border-radius: 0.3rem;
  //       padding: 0.2rem;
  //     }
  //     #themeMenu:hover { background: rgba(0,0,0,0.8); }
  //     #themeMenu h4 {
  //       margin: 0;
  //       font-size: 0.8rem;
  //       text-transform: uppercase;
  //       opacity: 0.7;
  //     }
  //   </style>
  //   <div id="themeMenu">
  //     <h4>Style</h4>
  //     <select id="themeSelect">
  //       ${Object.keys(themes)
  //         .map(t => `<option value="${t}" ${t===saved?"selected":""}>${t}</option>`)
  //         .join("")}
  //     </select>
  //   </div>
  // `;
  // document.body.appendChild(menu);

  // --- Handle theme switching ---
  
  // const selector = menu.querySelector("#themeSelect");

//   selector.addEventListener("change", e => {
//     const val = e.target.value;
//     styleEl.textContent = themes[val].css;
//     localStorage.setItem("theme", val);
//   });

//   selector.addEventListener("change", e => {
//   const val = e.target.value;
//   styleEl.textContent = themes[val].css;
//   localStorage.setItem("theme", val);

//   // Update vis.js network colors
//   if (this.networkInstance) {
//     const theme = themes[val].graph;

//     this.networkInstance.setOptions({
//       nodes: { color: { border: theme.nodeBorder, background: theme.nodeBackground } },
//       edges: { color: theme.edgeColor, font: { color: theme.nodeFont } }
//     });
    
//     this.networkInstance.body.container.style.background = theme.background;
//   }
// });

  // --- Create style tag ---
  const styleEl = document.createElement("style");
  document.head.appendChild(styleEl);

  // --- Load saved theme ---
  const saved = localStorage.getItem("theme") || "default";
  styleEl.textContent = themes[saved].css;

  // --- Create floating menu ---
  const menu = document.createElement("div");
  menu.innerHTML = `
    <style>
      #themeMenu { position: fixed; bottom:1rem; right:1rem; background: rgba(0,0,0,0.6); color:white; padding:0.5rem 0.8rem; border-radius:0.5rem; font-family:sans-serif; font-size:0.9rem; z-index:9999; }
      #themeMenu select,input { background:#222;color:white;border:1px solid #444;border-radius:0.3rem;padding:0.2rem;margin-top:0.2rem; font-size:0.9rem;}
      #themeMenu label{font-size:0.8rem;opacity:0.7;margin-right:0.2rem;}
      #themeMenu div.row{margin-top:0.3rem;}
      #themeMenu button{margin-top:0.3rem; padding:0.3rem 0.5rem; background:#444; color:white; border:none; border-radius:0.3rem; cursor:pointer;}
    </style>
    <div id="themeMenu">
      <h4>Theme</h4>
      <select id="themeSelect">${Object.keys(themes).map(t=>`<option value="${t}" ${t===saved?"selected":""}>${t}</option>`).join("")}</select>
      <div class="row"><label>Accent:</label><input type="color" id="accentColor" value="${themes[saved].graph.nodeBorder}"></div>
      <div class="row"><label>Panel BG:</label><input type="color" id="panelColor" value="${themes[saved].graph.background}"></div>
      <div class="row"><label>Node Border:</label><input type="color" id="nodeBorderColor" value="${themes[saved].graph.nodeBorder}"></div>
      <div class="row"><label>Node Background:</label><input type="color" id="nodeBgColor" value="${themes[saved].graph.nodeBackground}"></div>
      <div class="row"><label>Edge Color:</label><input type="color" id="edgeColor" value="${themes[saved].graph.edgeColor}"></div>
      <div class="row"><label>Node Font:</label><input type="color" id="nodeFontColor" value="${themes[saved].graph.nodeFont}"></div>
      <button id="resetThemeBtn">Reset to Theme Default</button>
    </div>
  `;
  document.body.appendChild(menu);

  // --- Theme select handler ---
  const selector = menu.querySelector("#themeSelect");
  const accentInput = menu.querySelector("#accentColor");
  const panelInput = menu.querySelector("#panelColor");
  const nodeBorderInput = menu.querySelector("#nodeBorderColor");
  const nodeBgInput = menu.querySelector("#nodeBgColor");
  const edgeInput = menu.querySelector("#edgeColor");
  const nodeFontInput = menu.querySelector("#nodeFontColor");
  const resetBtn = menu.querySelector("#resetThemeBtn");

  const applyTheme = (themeName) => {
    const theme = themes[themeName];
    styleEl.textContent = theme.css;
    localStorage.setItem("theme", themeName);

    // Update Vis.js network
    if(window.network){
      window.network.setOptions({
        nodes:{
          color:{ border: nodeBorderInput.value, background: nodeBgInput.value }
        },
        edges:{
          color: edgeInput.value,
          font:{ color: nodeFontInput.value }
        }
      });
      window.network.body.container.style.background = panelInput.value;
    }
  };

  selector.addEventListener("change", e=>{
    const themeName = e.target.value;
    const theme = themes[themeName];
    accentInput.value = theme.graph.nodeBorder;
    panelInput.value = theme.graph.background;
    nodeBorderInput.value = theme.graph.nodeBorder;
    nodeBgInput.value = theme.graph.nodeBackground;
    edgeInput.value = theme.graph.edgeColor;
    nodeFontInput.value = theme.graph.nodeFont;
    applyTheme(themeName);
  });

  // --- Color inputs ---
  accentInput.addEventListener("input", e=>{ document.documentElement.style.setProperty("--accent", e.target.value); applyTheme(selector.value); });
  panelInput.addEventListener("input", e=>{ document.documentElement.style.setProperty("--panel-bg", e.target.value); if(window.network) window.network.body.container.style.background = e.target.value; });
  nodeBorderInput.addEventListener("input", e=>{ if(window.network) window.network.setOptions({nodes:{color:{border:e.target.value}}}); });
  nodeBgInput.addEventListener("input", e=>{ if(window.network) window.network.setOptions({nodes:{color:{background:e.target.value}}}); });
  edgeInput.addEventListener("input", e=>{ if(window.network) window.network.setOptions({edges:{color:e.target.value}}); });
  nodeFontInput.addEventListener("input", e=>{ if(window.network) window.network.setOptions({edges:{font:{color:e.target.value}}}); });

  // --- Reset button ---
  resetBtn.addEventListener("click", ()=>{
    const themeName = selector.value;
    const theme = themes[themeName];
    accentInput.value = theme.graph.nodeBorder;
    panelInput.value = theme.graph.background;
    nodeBorderInput.value = theme.graph.nodeBorder;
    nodeBgInput.value = theme.graph.nodeBackground;
    edgeInput.value = theme.graph.edgeColor;
    nodeFontInput.value = theme.graph.nodeFont;

    document.documentElement.style.setProperty("--accent", theme.graph.nodeBorder);
    document.documentElement.style.setProperty("--panel-bg", theme.graph.background);

    if(window.network){
      window.network.setOptions({
        nodes:{ color:{ border: theme.graph.nodeBorder, background: theme.graph.nodeBackground } },
        edges:{ color: theme.graph.edgeColor, font:{ color: theme.graph.nodeFont } }
      });
      window.network.body.container.style.background = theme.graph.background;
    }
  });
})();