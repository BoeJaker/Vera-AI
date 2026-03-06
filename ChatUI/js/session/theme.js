(() => {
  // ============================================
  // VERACHAT THEME SYSTEM v2.1
  // Now includes proactiveFocus color maps for
  // full integration with ProactiveFocusStatus UI
  // ============================================

  const baseCSS = `
    :root {
      --radius-sm: 6px;
      --radius-md: 8px;
      --radius-lg: 10px;
      --radius-xl: 12px;
      --transition-fast: 0.15s ease;
      --transition-normal: 0.3s ease;
    }

    * { box-sizing: border-box; }

    body {
      height: 100vh;
      overflow: hidden;
      margin: 0;
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
    }

    ::-webkit-scrollbar { width: 8px; height: 8px; }
    ::-webkit-scrollbar-track { background: var(--bg); border-radius: 4px; }
    ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: var(--hover); }
  `;

  // ─────────────────────────────────────────────────────────────
  // proactiveFocus color map schema (all themes must define this)
  //
  //   bg          – outer wrapper background
  //   bgPanel     – panel (.pf-panel) background
  //   bgPanelHdr  – panel header background
  //   bgPanelHdrHover
  //   border      – panel borders
  //   borderSubtle
  //   text        – default text inside pf panels
  //   textMuted   – timestamps, dim labels
  //   textSecondary
  //
  //   accentThought   – thought panel dot + border + spinner
  //   accentResponse  – response panel dot + border + spinner
  //   accentFlowchart – flowchart panel dot + border
  //   accentConsole   – console panel dot
  //   accentSuccess   – step done / success lines
  //   accentError     – step failed / error lines
  //   accentWarning   – warning lines
  //   accentTool      – tool output lines
  //   accentStage     – stage bar left-border + stage name color
  //
  //   thoughtText     – thought body text
  //   responseText    – response body text
  //   planText        – planning section text
  //   stepInputText   – step input preview text
  //   stepOutputText  – step output text
  //
  //   runBorder       – active run container border
  //   runBorderDone   – completed run border
  //   runBorderFailed – failed run border
  //   runBg           – run header background
  //   runBgHover
  //   runTitle        – active run title color
  //   runTitleDone
  //   runTitleFailed
  //
  //   stepRunning     – step left-border when running
  //   stepDone        – step left-border when done
  //   stepFailed      – step left-border when failed
  //   stepBgRunning   – step row bg when running
  //   stepBgDone
  //   stepBgFailed
  //   stepTextRunning
  //   stepTextDone
  //   stepTextFailed
  //
  //   fileBadgeBg     – file badge background
  //   fileBadgeText   – file badge text
  //   fileBadgeBorder
  //
  //   sepColor        – separator line text / color
  //   sepBorder       – separator top border
  //
  //   stageBarBg      – stage bar background tint
  //   cursor          – animated cursor color
  //   spinnerThought
  //   spinnerResponse
  //   spinnerRun
  //
  //   fontFamily      – monospace font for console/step content
  // ─────────────────────────────────────────────────────────────

  const themes = {

    // ── Default Dark ─────────────────────────────────────────────
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
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
        .chat-panel, .graph-panel { box-shadow: inset 0 0 10px rgba(255,255,255,0.05); }
      `,
      graph: {
        nodeBorder: '#60a5fa', nodeBackground: '#1e293b', nodeHighlight: '#3b82f6',
        nodeFont: '#e2e8f0', nodeFontSize: 14, edgeColor: '#475569',
        edgeHighlight: '#60a5fa', background: '#0f172a',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
      },
      proactiveFocus: {
        bg:              '#0d1117',
        bgPanel:         '#0d1117',
        bgPanelHdr:      '#111827',
        bgPanelHdrHover: '#1a2333',
        border:          '#1e2d3d',
        borderSubtle:    '#0a1118',
        text:            '#94a3b8',
        textMuted:       '#1e3a5f',
        textSecondary:   '#475569',

        accentThought:   '#8b5cf6',
        accentResponse:  '#3b82f6',
        accentFlowchart: '#f59e0b',
        accentConsole:   '#94a3b8',
        accentSuccess:   '#34d399',
        accentError:     '#f87171',
        accentWarning:   '#fbbf24',
        accentTool:      '#7dd3fc',
        accentStage:     '#3b82f6',

        thoughtText:     '#c4b5fd',
        responseText:    '#e2e8f0',
        planText:        '#475569',
        stepInputText:   '#475569',
        stepOutputText:  '#34d399',

        runBorder:       '#3b82f6',
        runBorderDone:   '#1e3a5f',
        runBorderFailed: '#7f1d1d',
        runBg:           '#0f1923',
        runBgHover:      '#131f2e',
        runTitle:        '#60a5fa',
        runTitleDone:    '#64748b',
        runTitleFailed:  '#f87171',

        stepRunning:  '#3b82f6',
        stepDone:     '#059669',
        stepFailed:   '#dc2626',
        stepBgRunning:'rgba(59,130,246,.04)',
        stepBgDone:   'rgba(5,150,105,.04)',
        stepBgFailed: 'rgba(220,38,38,.04)',
        stepTextRunning: '#94a3b8',
        stepTextDone:    '#6ee7b7',
        stepTextFailed:  '#fca5a5',

        fileBadgeBg:     'rgba(16,185,129,.12)',
        fileBadgeText:   '#6ee7b7',
        fileBadgeBorder: 'rgba(16,185,129,.2)',

        sepColor:  '#2d4a6a',
        sepBorder: '#0f1923',

        stageBarBg:      'rgba(59,130,246,.07)',
        cursor:          '#60a5fa',
        spinnerThought:  '#8b5cf6',
        spinnerResponse: '#3b82f6',
        spinnerRun:      '#3b82f6',

        fontFamily: '"Monaco","Menlo","Courier New",monospace',
      },
      focusBoard: {
        // Surfaces
        bg:                 '#0f172a',
        bgSurface:          '#1e293b',
        bgSurfaceAlt:       'rgba(15,23,42,0.5)',
        bgCard:             'rgba(15,23,42,0.6)',
        bgCardForm:         'rgba(15,23,42,0.7)',
        bgCardEdit:         'rgba(15,23,42,0.8)',
        bgDropzone:         'rgba(15,23,42,0.3)',
        bgControlBar:       'rgba(15,23,42,0.5)',
        bgBtn:              'rgba(30,41,59,0.8)',
        bgBtnHover:         'rgba(59,130,246,0.2)',
        bgModal:            'linear-gradient(135deg,#1e293b 0%,#0f172a 100%)',
        // Borders
        border:             '#334155',
        borderFocus:        '#3b82f6',
        // Text
        text:               '#e2e8f0',
        textSecondary:      '#cbd5e1',
        textMuted:          '#94a3b8',
        textDimmed:         '#64748b',
        // Category accent colors
        accentIdeas:        '#8b5cf6',
        accentNextSteps:    '#f59e0b',
        accentActions:      '#3b82f6',
        accentProgress:     '#10b981',
        accentIssues:       '#ef4444',
        accentCompleted:    '#6b7280',
        accentQuestions:    '#ec4899',
        // Focus section
        focusBorder:        '#8b5cf6',
        focusBg:            'rgba(139,92,246,0.1)',
        focusBgBorder:      'rgba(139,92,246,0.3)',
        focusText:          '#a78bfa',
        // Status
        statusRunning:      '#10b981',
        statusStopped:      'rgba(107,114,128,0.5)',
        statusRunningBorder:'#10b981',
        statusStoppedBorder:'#6b7280',
        // Priority badges
        priorityHigh:       '#ef4444',
        priorityMedium:     '#f59e0b',
        priorityLow:        '#6b7280',
        // Tool pills
        toolBg:             'rgba(59,130,246,0.2)',
        toolText:           '#60a5fa',
        toolBorder:         'rgba(59,130,246,0.3)',
        // Active tab tint
        tabActiveBg:        'rgba(59,130,246,0.2)',
        tabActiveBorder:    '#3b82f6',
        tabActiveText:      '#e2e8f0',
        tabHoverBg:         'rgba(30,41,59,0.7)',
        // Drop zone highlight
        dropHighlightBorder:'#10b981',
        dropHighlightBg:    'rgba(16,185,129,0.1)',
        // Execute all button
        executeAllBg:       '#34d399',
        // New focus section
        newFocusBg:         'rgba(59,130,246,0.1)',
        newFocusBorder:     'rgba(59,130,246,0.3)',
        newFocusBtn:        '#3b82f6',
        // Similar focuses
        similarBorder:      '#8b5cf6',
        similarBadgeBg:     '#8b5cf6',
        // History/file modal tab active
        fileTabActive:      '#3b82f6',
        histTabActive:      '#8b5cf6',
        // Thought streaming
        thoughtLabel:       '#8b5cf6',
      }
    },

    // ── Render RGB ────────────────────────────────────────────────
    renderRGB: {
      name: 'Render — RGB',
      variables: {
        '--bg': '#0b0b0c',
        '--bg-surface': '#0f1113',
        '--panel-bg': '#0f1113',
        '--text': '#e6eef8',
        '--text-secondary': '#b8c7de',
        '--accent-r': '#ff2d2d',
        '--accent-g': '#2dff6a',
        '--accent-b': '#2d6aff',
        '--accent-muted': 'rgba(45,106,255,0.65)',
        '--ink': '#0a0a0a',
        '--paper': '#0f1113',
        '--border': '#ff2d2d',
        '--border-subtle': '#2dff6a',
        '--hover': '#15181b',
        '--text-inverted': '#000000',
        '--user-bg': '#2d6aff',
        '--success': '#16a34a',
        '--warning': '#f59e0b',
        '--error': '#ef4444',
        '--caret': '#2d6aff',
      },
      fonts: ['Inter:wght@400;500;600', 'Source+Code+Pro:wght@400;600'],
      css: `
        body {
          font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          background: radial-gradient(1200px 800px at 10% 10%, rgba(45,106,255,0.06), transparent 6%),
                      radial-gradient(1000px 600px at 90% 80%, rgba(255,45,45,0.03), transparent 6%),
                      var(--bg);
          color: var(--text);
        }
        .chat-panel, .graph-panel {
          background: linear-gradient(180deg, rgba(255,255,255,0.01), transparent 40%), var(--panel-bg);
          border: 1px solid var(--border);
          padding: 12px; border-radius: 8px;
          box-shadow: 0 6px 24px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.02);
        }
        .message-header, .message-avatar, .chat-message-header, .chat-message-avatar { display: none !important; }
        #chatMessages { display:flex; flex-direction:column; gap:6px; padding:8px 6px;
          font-family:'Source Code Pro',monospace; font-size:13.5px; line-height:1.45; overflow-y:auto; }
        .message { display:flex; align-items:flex-start; gap:8px; margin:0; padding:0; }
        .message-rendered { display:inline; color:var(--text); background:none; padding:0; margin:0; word-break:break-word; -webkit-text-stroke:0.25px rgba(0,0,0,0.5); text-shadow:0 1px 0 rgba(0,0,0,0.45); }
        .message.system::before { content:"# "; display:inline-block; margin-right:4px; color:var(--ink); font-family:'Source Code Pro',monospace; font-weight:600; }
        .message.assistant::before { content:"▶ "; display:inline-block; margin-right:4px; color:var(--ink); font-family:'Source Code Pro',monospace; opacity:.9; }
        .message.user::before { content:""; display:inline-block; width:10px; height:10px; border-radius:2px; margin-right:8px; box-shadow:0 0 0 2px rgba(0,0,0,0.6) inset; vertical-align:middle; background:var(--user-bg); }
        .tag.r { background:var(--accent-r); } .tag.g { background:var(--accent-g); } .tag.b { background:var(--accent-b); }
        .input-area { display:flex; align-items:center; gap:8px; padding:10px; background:linear-gradient(180deg,rgba(255,255,255,.01),rgba(255,255,255,.005)); border-top:1px solid rgba(255,255,255,.02); }
        .input-wrapper { display:flex; align-items:center; gap:8px; flex:1; background:linear-gradient(90deg,rgba(255,255,255,.01),transparent); border-radius:6px; padding:6px; border:1px dashed rgba(255,255,255,.03); }
        #messageInput { resize:none; min-height:28px; max-height:140px; width:100%; background:transparent; border:none; color:var(--text); font-family:'Source Code Pro',monospace; font-size:13px; padding:6px; outline:none; caret-color:var(--caret); }
        .input-wrapper::before { content:"λ"; color:var(--accent-b); font-weight:700; margin-right:6px; font-family:'Source Code Pro',monospace; }
        .send-btn { background:var(--accent-b); border:none; color:white; padding:6px 10px; border-radius:6px; font-weight:600; box-shadow:0 6px 18px rgba(45,106,255,0.12); }
        .send-btn:hover { transform:translateY(-1px); }
        .message-rendered::selection { background:rgba(45,106,255,0.18); color:var(--text); }
      `,
      graph: {
        nodeBorder: '#ff2d2d', nodeBackground: '#0f1113', nodeHighlight: '#2d6aff',
        nodeFont: '#e6eef8', nodeFontSize: 14, edgeColor: '#27313a',
        edgeHighlight: '#2d6aff', background: '#0b0b0c',
        fontFamily: '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
      },
      proactiveFocus: {
        bg:              '#0b0b0c',
        bgPanel:         '#0f1113',
        bgPanelHdr:      '#0d0f11',
        bgPanelHdrHover: '#121518',
        border:          '#1a1e22',
        borderSubtle:    '#0a0c0e',
        text:            '#b8c7de',
        textMuted:       '#1f2d3d',
        textSecondary:   '#2d3a48',

        accentThought:   '#ff2d2d',
        accentResponse:  '#2d6aff',
        accentFlowchart: '#2dff6a',
        accentConsole:   '#b8c7de',
        accentSuccess:   '#2dff6a',
        accentError:     '#ff2d2d',
        accentWarning:   '#f59e0b',
        accentTool:      '#2d6aff',
        accentStage:     '#2d6aff',

        thoughtText:     '#ffaaaa',
        responseText:    '#e6eef8',
        planText:        '#3a4a5a',
        stepInputText:   '#3a4a5a',
        stepOutputText:  '#2dff6a',

        runBorder:       '#2d6aff',
        runBorderDone:   '#1a2030',
        runBorderFailed: '#7f0000',
        runBg:           '#0d0f11',
        runBgHover:      '#111518',
        runTitle:        '#2d6aff',
        runTitleDone:    '#3a4a5a',
        runTitleFailed:  '#ff2d2d',

        stepRunning:  '#2d6aff',
        stepDone:     '#2dff6a',
        stepFailed:   '#ff2d2d',
        stepBgRunning:'rgba(45,106,255,.05)',
        stepBgDone:   'rgba(45,255,106,.04)',
        stepBgFailed: 'rgba(255,45,45,.04)',
        stepTextRunning: '#b8c7de',
        stepTextDone:    '#2dff6a',
        stepTextFailed:  '#ff6666',

        fileBadgeBg:     'rgba(45,255,106,.1)',
        fileBadgeText:   '#2dff6a',
        fileBadgeBorder: 'rgba(45,255,106,.25)',

        sepColor:  '#1f3050',
        sepBorder: '#0a0c0e',

        stageBarBg:      'rgba(45,106,255,.07)',
        cursor:          '#2d6aff',
        spinnerThought:  '#ff2d2d',
        spinnerResponse: '#2d6aff',
        spinnerRun:      '#2d6aff',

        fontFamily: '"Source Code Pro","Monaco","Menlo","Courier New",monospace',

      focusBoard: {
        bg:                 '#0b0b0c',
        bgSurface:          '#0f1113',
        bgSurfaceAlt:       'rgba(15,17,19,0.5)',
        bgCard:             'rgba(15,17,19,0.6)',
        bgCardForm:         'rgba(15,17,19,0.7)',
        bgCardEdit:         'rgba(15,17,19,0.8)',
        bgDropzone:         'rgba(15,17,19,0.3)',
        bgControlBar:       'rgba(15,17,19,0.5)',
        bgBtn:              'rgba(20,24,27,0.8)',
        bgBtnHover:         'rgba(45,106,255,0.2)',
        bgModal:            'linear-gradient(135deg,#0f1113 0%,#0b0b0c 100%)',
        border:             '#1a1e22',
        borderFocus:        '#2d6aff',
        text:               '#e6eef8',
        textSecondary:      '#b8c7de',
        textMuted:          '#7a8a9a',
        textDimmed:         '#3a4a5a',
        accentIdeas:        '#ff2d2d',
        accentNextSteps:    '#f59e0b',
        accentActions:      '#2d6aff',
        accentProgress:     '#2dff6a',
        accentIssues:       '#ff2d2d',
        accentCompleted:    '#3a4a5a',
        accentQuestions:    '#ff2d2d',
        focusBorder:        '#ff2d2d',
        focusBg:            'rgba(255,45,45,0.08)',
        focusBgBorder:      'rgba(255,45,45,0.25)',
        focusText:          '#ff8888',
        statusRunning:      '#2dff6a',
        statusStopped:      'rgba(58,74,90,0.5)',
        statusRunningBorder:'#2dff6a',
        statusStoppedBorder:'#3a4a5a',
        priorityHigh:       '#ff2d2d',
        priorityMedium:     '#f59e0b',
        priorityLow:        '#3a4a5a',
        toolBg:             'rgba(45,106,255,0.2)',
        toolText:           '#2d6aff',
        toolBorder:         'rgba(45,106,255,0.3)',
        tabActiveBg:        'rgba(45,106,255,0.2)',
        tabActiveBorder:    '#2d6aff',
        tabActiveText:      '#e6eef8',
        tabHoverBg:         'rgba(20,24,27,0.7)',
        dropHighlightBorder:'#2dff6a',
        dropHighlightBg:    'rgba(45,255,106,0.08)',
        executeAllBg:       '#2dff6a',
        newFocusBg:         'rgba(45,106,255,0.08)',
        newFocusBorder:     'rgba(45,106,255,0.25)',
        newFocusBtn:        '#2d6aff',
        similarBorder:      '#ff2d2d',
        similarBadgeBg:     '#ff2d2d',
        fileTabActive:      '#2d6aff',
        histTabActive:      '#ff2d2d',
        thoughtLabel:       '#ff2d2d',
      }
      }
    },

    // ── Render CMY ────────────────────────────────────────────────
    renderCMY: {
      name: 'Render — CMY',
      variables: {
        '--bg': '#080909',
        '--bg-surface': '#0e0f10',
        '--panel-bg': '#0e0f10',
        '--text': '#f2f7fb',
        '--text-secondary': '#c7d7e6',
        '--accent': '#00cfe8',
        '--accent-c': '#00cfe8',
        '--accent-m': '#ff46b0',
        '--accent-y': '#ffd100',
        '--accent-muted': 'rgba(0,207,232,0.55)',
        '--ink': '#071013',
        '--paper': '#0e0f10',
        '--border': '#ff46b0',
        '--border-subtle': '#ffd100',
        '--hover': '#ff46b0',
        '--text-inverted': '#000000',
        '--user-bg': '#ff46b0',
        '--success': '#10b981',
        '--warning': '#f59e0b',
        '--error': '#ef4444',
        '--caret': '#00cfe8',
      },
      fonts: ['Inter:wght@400;500;600', 'Source+Code+Pro:wght@400;600'],
      css: `
        body {
          font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
          background: radial-gradient(900px 600px at 15% 20%, rgba(0,207,232,0.04), transparent 6%),
                      radial-gradient(700px 500px at 85% 80%, rgba(255,70,176,0.03), transparent 6%),
                      var(--bg);
          color:var(--text);
        }
        .chat-panel, .graph-panel { background:linear-gradient(180deg,rgba(255,255,255,.01),transparent 30%),var(--panel-bg); border:1px solid var(--border); padding:12px; border-radius:8px; box-shadow:0 8px 36px rgba(0,0,0,.55),inset 0 1px 0 rgba(255,255,255,.02); }
        .message-header,.message-avatar,.chat-message-header,.chat-message-avatar { display:none !important; }
        .message-content { max-width:100%; }
        #chatMessages { display:flex; flex-direction:column; gap:8px; padding:8px 6px; font-family:'Source Code Pro',monospace; font-size:13.5px; line-height:1.45; overflow-y:auto; max-width:100%; }
        .message { display:flex; align-items:flex-start; gap:8px; margin:0; padding:0; }
        .message-rendered { display:inline; color:var(--text); padding:0; margin:0; -webkit-text-stroke:0.28px rgba(7,16,19,0.6); }
        .message.system::before { content:"# "; display:inline-block; margin-right:4px; color:var(--ink); font-family:'Source Code Pro',monospace; font-weight:700; vertical-align:baseline; }
        .message.assistant::before { content:"➤ "; display:inline-block; margin-right:4px; color:var(--ink); font-family:'Source Code Pro',monospace; opacity:.95; }
        .message.user::before { content:""; display:inline-block; width:10px; height:10px; border-radius:2px; margin-right:8px; background:var(--user-bg); box-shadow:0 0 0 2px rgba(0,0,0,.6) inset; vertical-align:middle; }
        .tag.c { background:var(--accent-c); color:var(--text-inverted); padding:2px 6px; border-radius:4px; font-weight:600; margin-right:6px; display:inline-block; }
        .tag.m { background:var(--accent-m); color:var(--text-inverted); padding:2px 6px; border-radius:4px; font-weight:600; margin-right:6px; display:inline-block; }
        .tag.y { background:var(--accent-y); color:#111; padding:2px 6px; border-radius:4px; font-weight:600; margin-right:6px; display:inline-block; }
        .input-area { display:flex; align-items:center; gap:8px; padding:10px; background:linear-gradient(90deg,rgba(255,255,255,.01),transparent); border-top:1px solid rgba(255,255,255,.02); }
        .input-wrapper { display:flex; align-items:center; gap:8px; flex:1; background:linear-gradient(180deg,rgba(255,255,255,.006),transparent); border-radius:6px; padding:6px; border:1px dashed rgba(255,255,255,.02); }
        #messageInput { resize:none; min-height:28px; max-height:140px; width:100%; background:transparent; border:none; color:var(--text); font-family:'Source Code Pro',monospace; font-size:13px; padding:6px; outline:none; caret-color:var(--caret); }
        .input-wrapper::before { content:"✦"; color:var(--accent-c); font-weight:700; margin-right:6px; font-family:'Source Code Pro',monospace; }
        .send-btn { background:var(--accent-m); border:none; color:white; padding:6px 10px; border-radius:6px; font-weight:700; box-shadow:0 6px 18px rgba(255,70,176,.12); }
        .send-btn:hover { transform:translateY(-1px); }
        .message-rendered::selection { background:rgba(0,207,232,.14); color:var(--text); }
      `,
      graph: {
        nodeBorder: '#00cfe8', nodeBackground: '#0e0f10', nodeHighlight: '#ff46b0',
        nodeFont: '#f2f7fb', nodeFontSize: 14, edgeColor: '#202428',
        edgeHighlight: '#ff46b0', background: '#080909',
        fontFamily: '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
      },
      proactiveFocus: {
        bg:              '#080909',
        bgPanel:         '#0e0f10',
        bgPanelHdr:      '#0b0c0d',
        bgPanelHdrHover: '#10121314',
        border:          '#1a1c1e',
        borderSubtle:    '#090a0b',
        text:            '#c7d7e6',
        textMuted:       '#1a2530',
        textSecondary:   '#2a3540',

        accentThought:   '#ff46b0',
        accentResponse:  '#00cfe8',
        accentFlowchart: '#ffd100',
        accentConsole:   '#c7d7e6',
        accentSuccess:   '#10b981',
        accentError:     '#ef4444',
        accentWarning:   '#ffd100',
        accentTool:      '#00cfe8',
        accentStage:     '#00cfe8',

        thoughtText:     '#ffb0d8',
        responseText:    '#f2f7fb',
        planText:        '#3a4550',
        stepInputText:   '#3a4550',
        stepOutputText:  '#10b981',

        runBorder:       '#00cfe8',
        runBorderDone:   '#1a2530',
        runBorderFailed: '#7f001d',
        runBg:           '#0b0c0d',
        runBgHover:      '#0e1012',
        runTitle:        '#00cfe8',
        runTitleDone:    '#3a4550',
        runTitleFailed:  '#ff46b0',

        stepRunning:  '#00cfe8',
        stepDone:     '#10b981',
        stepFailed:   '#ef4444',
        stepBgRunning:'rgba(0,207,232,.05)',
        stepBgDone:   'rgba(16,185,129,.04)',
        stepBgFailed: 'rgba(239,68,68,.04)',
        stepTextRunning: '#c7d7e6',
        stepTextDone:    '#10b981',
        stepTextFailed:  '#ff6688',

        fileBadgeBg:     'rgba(16,185,129,.12)',
        fileBadgeText:   '#10b981',
        fileBadgeBorder: 'rgba(16,185,129,.25)',

        sepColor:  '#1a2d3d',
        sepBorder: '#090a0b',

        stageBarBg:      'rgba(0,207,232,.07)',
        cursor:          '#00cfe8',
        spinnerThought:  '#ff46b0',
        spinnerResponse: '#00cfe8',
        spinnerRun:      '#00cfe8',

        fontFamily: '"Source Code Pro","Monaco","Menlo","Courier New",monospace',

      focusBoard: {
        bg:                 '#080909',
        bgSurface:          '#0e0f10',
        bgSurfaceAlt:       'rgba(14,15,16,0.5)',
        bgCard:             'rgba(14,15,16,0.6)',
        bgCardForm:         'rgba(14,15,16,0.7)',
        bgCardEdit:         'rgba(14,15,16,0.8)',
        bgDropzone:         'rgba(14,15,16,0.3)',
        bgControlBar:       'rgba(14,15,16,0.5)',
        bgBtn:              'rgba(18,20,22,0.8)',
        bgBtnHover:         'rgba(0,207,232,0.2)',
        bgModal:            'linear-gradient(135deg,#0e0f10 0%,#080909 100%)',
        border:             '#1a1c1e',
        borderFocus:        '#00cfe8',
        text:               '#f2f7fb',
        textSecondary:      '#c7d7e6',
        textMuted:          '#7a8a9a',
        textDimmed:         '#3a4550',
        accentIdeas:        '#ff46b0',
        accentNextSteps:    '#ffd100',
        accentActions:      '#00cfe8',
        accentProgress:     '#10b981',
        accentIssues:       '#ff46b0',
        accentCompleted:    '#3a4550',
        accentQuestions:    '#ff46b0',
        focusBorder:        '#ff46b0',
        focusBg:            'rgba(255,70,176,0.08)',
        focusBgBorder:      'rgba(255,70,176,0.25)',
        focusText:          '#ff8ad4',
        statusRunning:      '#10b981',
        statusStopped:      'rgba(58,69,80,0.5)',
        statusRunningBorder:'#10b981',
        statusStoppedBorder:'#3a4550',
        priorityHigh:       '#ff46b0',
        priorityMedium:     '#ffd100',
        priorityLow:        '#3a4550',
        toolBg:             'rgba(0,207,232,0.15)',
        toolText:           '#00cfe8',
        toolBorder:         'rgba(0,207,232,0.3)',
        tabActiveBg:        'rgba(0,207,232,0.15)',
        tabActiveBorder:    '#00cfe8',
        tabActiveText:      '#f2f7fb',
        tabHoverBg:         'rgba(18,20,22,0.7)',
        dropHighlightBorder:'#10b981',
        dropHighlightBg:    'rgba(16,185,129,0.08)',
        executeAllBg:       '#10b981',
        newFocusBg:         'rgba(0,207,232,0.08)',
        newFocusBorder:     'rgba(0,207,232,0.25)',
        newFocusBtn:        '#00cfe8',
        similarBorder:      '#ff46b0',
        similarBadgeBg:     '#ff46b0',
        fileTabActive:      '#00cfe8',
        histTabActive:      '#ff46b0',
        thoughtLabel:       '#ff46b0',
      }
      }
    },

    // ── Modern Professional ───────────────────────────────────────
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
        body { font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; font-size:14px; line-height:1.6; }
        h1,h2,h3 { color:var(--text); font-weight:600; letter-spacing:-.02em; }
        button { font-family:'Inter',sans-serif; font-weight:500; }
        button:hover { transform:translateY(-1px); }
        .message.user .message-content { background:var(--user-bg); border:none; color:white; }
        .message.assistant .message-avatar { background:linear-gradient(135deg,var(--accent) 0%,var(--hover) 100%); border:none; color:white; }
        input:focus,textarea:focus { outline:none; border-color:var(--accent); box-shadow:0 0 0 3px rgba(99,102,241,.15); }
        .send-btn:hover { box-shadow:0 4px 12px rgba(99,102,241,.3); }
        .status-success { color:var(--success); } .status-warning { color:var(--warning); } .status-error { color:var(--error); }
      `,
      graph: {
        nodeBorder: '#6366f1', nodeBackground: '#27272a', nodeHighlight: '#818cf8',
        nodeFont: '#fafafa', nodeFontSize: 13, edgeColor: '#52525b',
        edgeHighlight: '#6366f1', background: '#18181b',
        fontFamily: '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
      },
      proactiveFocus: {
        bg:              '#111114',
        bgPanel:         '#1a1a1e',
        bgPanelHdr:      '#1f1f23',
        bgPanelHdrHover: '#27272a',
        border:          '#3f3f46',
        borderSubtle:    '#2e2e33',
        text:            '#a1a1aa',
        textMuted:       '#3f3f46',
        textSecondary:   '#52525b',

        accentThought:   '#8b5cf6',
        accentResponse:  '#6366f1',
        accentFlowchart: '#f59e0b',
        accentConsole:   '#a1a1aa',
        accentSuccess:   '#22c55e',
        accentError:     '#ef4444',
        accentWarning:   '#f59e0b',
        accentTool:      '#818cf8',
        accentStage:     '#6366f1',

        thoughtText:     '#c4b5fd',
        responseText:    '#fafafa',
        planText:        '#52525b',
        stepInputText:   '#52525b',
        stepOutputText:  '#4ade80',

        runBorder:       '#6366f1',
        runBorderDone:   '#3f3f46',
        runBorderFailed: '#7f1d1d',
        runBg:           '#1a1a1e',
        runBgHover:      '#1f1f23',
        runTitle:        '#818cf8',
        runTitleDone:    '#71717a',
        runTitleFailed:  '#f87171',

        stepRunning:  '#6366f1',
        stepDone:     '#16a34a',
        stepFailed:   '#dc2626',
        stepBgRunning:'rgba(99,102,241,.05)',
        stepBgDone:   'rgba(22,163,74,.04)',
        stepBgFailed: 'rgba(220,38,38,.04)',
        stepTextRunning: '#a1a1aa',
        stepTextDone:    '#4ade80',
        stepTextFailed:  '#fca5a5',

        fileBadgeBg:     'rgba(99,102,241,.12)',
        fileBadgeText:   '#818cf8',
        fileBadgeBorder: 'rgba(99,102,241,.25)',

        sepColor:  '#3f3f46',
        sepBorder: '#27272a',

        stageBarBg:      'rgba(99,102,241,.07)',
        cursor:          '#818cf8',
        spinnerThought:  '#8b5cf6',
        spinnerResponse: '#6366f1',
        spinnerRun:      '#6366f1',

        fontFamily: '"Inter","Monaco","Menlo","Courier New",monospace',

      focusBoard: {
        bg:                 '#18181b',
        bgSurface:          '#27272a',
        bgSurfaceAlt:       'rgba(24,24,27,0.5)',
        bgCard:             'rgba(24,24,27,0.6)',
        bgCardForm:         'rgba(24,24,27,0.7)',
        bgCardEdit:         'rgba(24,24,27,0.8)',
        bgDropzone:         'rgba(24,24,27,0.3)',
        bgControlBar:       'rgba(24,24,27,0.5)',
        bgBtn:              'rgba(39,39,42,0.8)',
        bgBtnHover:         'rgba(99,102,241,0.2)',
        bgModal:            'linear-gradient(135deg,#27272a 0%,#18181b 100%)',
        border:             '#3f3f46',
        borderFocus:        '#6366f1',
        text:               '#fafafa',
        textSecondary:      '#e4e4e7',
        textMuted:          '#a1a1aa',
        textDimmed:         '#71717a',
        accentIdeas:        '#8b5cf6',
        accentNextSteps:    '#f59e0b',
        accentActions:      '#6366f1',
        accentProgress:     '#22c55e',
        accentIssues:       '#ef4444',
        accentCompleted:    '#71717a',
        accentQuestions:    '#ec4899',
        focusBorder:        '#8b5cf6',
        focusBg:            'rgba(139,92,246,0.1)',
        focusBgBorder:      'rgba(139,92,246,0.3)',
        focusText:          '#c4b5fd',
        statusRunning:      '#22c55e',
        statusStopped:      'rgba(113,113,122,0.5)',
        statusRunningBorder:'#22c55e',
        statusStoppedBorder:'#71717a',
        priorityHigh:       '#ef4444',
        priorityMedium:     '#f59e0b',
        priorityLow:        '#71717a',
        toolBg:             'rgba(99,102,241,0.2)',
        toolText:           '#818cf8',
        toolBorder:         'rgba(99,102,241,0.3)',
        tabActiveBg:        'rgba(99,102,241,0.2)',
        tabActiveBorder:    '#6366f1',
        tabActiveText:      '#fafafa',
        tabHoverBg:         'rgba(39,39,42,0.7)',
        dropHighlightBorder:'#22c55e',
        dropHighlightBg:    'rgba(34,197,94,0.1)',
        executeAllBg:       '#4ade80',
        newFocusBg:         'rgba(99,102,241,0.1)',
        newFocusBorder:     'rgba(99,102,241,0.3)',
        newFocusBtn:        '#6366f1',
        similarBorder:      '#8b5cf6',
        similarBadgeBg:     '#8b5cf6',
        fileTabActive:      '#6366f1',
        histTabActive:      '#8b5cf6',
        thoughtLabel:       '#8b5cf6',
      }
      }
    },

    // ── Terminal ──────────────────────────────────────────────────
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
        body { font-family:"Fira Code","Consolas",monospace; letter-spacing:.02em; line-height:1.4; background:var(--bg); color:var(--text); }
        button,select,input,textarea { font-family:"Fira Code",monospace; }
        .chat-panel,.graph-panel { background:black; border:1px solid var(--border); padding:8px; box-shadow:none; }
        #chatMessages { display:flex; flex-direction:column; padding:0; gap:0; font-size:13px; line-height:1.4; }
        .message { display:block; padding:0; margin:0; border:none; }
        .message-content { background:none !important; border:none !important; padding:0; margin:0; display:inline; }
        .message-header { display:none !important; }
        .message-avatar { display:none !important; }
        .message.user { display:flex; align-items:center; flex-direction:row; }
        .message.user::before { content:"$ "; color:var(--user-text); }
        .message.assistant { display:flex; align-items:center; }
        .message.assistant::before { content:"> "; color:var(--text-secondary); margin-right:.25em; }
        .message.system { display:flex; align-items:center; }
        .message.system::before { content:"# "; color:var(--border); margin-right:.25em; }
        .message.user .message-content { color:var(--user-text); }
        #messageInput { background:black; color:var(--text); border:none; border-bottom:1px solid var(--border); border-radius:0; caret-color:var(--caret); font-size:13px; }
        #messageInput::placeholder { color:#006633; }
        .send-btn { background:#002200; color:var(--text); border:1px solid var(--border); }
        .send-btn:hover { background:#003300; }
        ::-webkit-scrollbar-thumb { background:#004400; }
        @keyframes blink { 0%,50%{opacity:1}50.1%,100%{opacity:0} }
      `,
      graph: {
        nodeBorder: '#00ff66', nodeBackground: '#001100', nodeHighlight: '#00ffaa',
        nodeFont: '#00ff66', nodeFontSize: 13, edgeColor: '#00aa44',
        edgeHighlight: '#00ffaa', background: '#000000',
        fontFamily: '"Fira Code", "Courier New", monospace'
      },
      proactiveFocus: {
        bg:              '#000000',
        bgPanel:         '#010d01',
        bgPanelHdr:      '#000000',
        bgPanelHdrHover: '#001100',
        border:          '#003300',
        borderSubtle:    '#001a00',
        text:            '#00aa44',
        textMuted:       '#002200',
        textSecondary:   '#004422',

        accentThought:   '#00ffaa',
        accentResponse:  '#00ff66',
        accentFlowchart: '#00ff66',
        accentConsole:   '#00aa44',
        accentSuccess:   '#00ff66',
        accentError:     '#ff4444',
        accentWarning:   '#ffaa00',
        accentTool:      '#00ffaa',
        accentStage:     '#00ff66',

        thoughtText:     '#aaffcc',
        responseText:    '#00ff66',
        planText:        '#004422',
        stepInputText:   '#004422',
        stepOutputText:  '#00ff66',

        runBorder:       '#00ff66',
        runBorderDone:   '#003300',
        runBorderFailed: '#660000',
        runBg:           '#000000',
        runBgHover:      '#001100',
        runTitle:        '#00ff66',
        runTitleDone:    '#004422',
        runTitleFailed:  '#ff4444',

        stepRunning:  '#00ff66',
        stepDone:     '#00aa44',
        stepFailed:   '#ff2222',
        stepBgRunning:'rgba(0,255,102,.04)',
        stepBgDone:   'rgba(0,170,68,.04)',
        stepBgFailed: 'rgba(255,34,34,.04)',
        stepTextRunning: '#00aa44',
        stepTextDone:    '#00ff66',
        stepTextFailed:  '#ff4444',

        fileBadgeBg:     'rgba(0,255,102,.08)',
        fileBadgeText:   '#00ffaa',
        fileBadgeBorder: 'rgba(0,255,102,.2)',

        sepColor:  '#003300',
        sepBorder: '#001100',

        stageBarBg:      'rgba(0,255,102,.06)',
        cursor:          '#00ff66',
        spinnerThought:  '#00ffaa',
        spinnerResponse: '#00ff66',
        spinnerRun:      '#00ff66',

        fontFamily: '"Fira Code","Consolas","Courier New",monospace',

      focusBoard: {
        bg:                 '#000000',
        bgSurface:          '#001100',
        bgSurfaceAlt:       'rgba(0,17,0,0.5)',
        bgCard:             'rgba(0,17,0,0.6)',
        bgCardForm:         'rgba(0,17,0,0.7)',
        bgCardEdit:         'rgba(0,17,0,0.8)',
        bgDropzone:         'rgba(0,17,0,0.3)',
        bgControlBar:       'rgba(0,17,0,0.5)',
        bgBtn:              'rgba(0,34,0,0.8)',
        bgBtnHover:         'rgba(0,255,102,0.1)',
        bgModal:            'linear-gradient(135deg,#001100 0%,#000000 100%)',
        border:             '#003300',
        borderFocus:        '#00ff66',
        text:               '#00ff66',
        textSecondary:      '#00cc44',
        textMuted:          '#00aa44',
        textDimmed:         '#004422',
        accentIdeas:        '#00ffaa',
        accentNextSteps:    '#00ff66',
        accentActions:      '#00ff66',
        accentProgress:     '#00ff66',
        accentIssues:       '#ff4444',
        accentCompleted:    '#004422',
        accentQuestions:    '#00ffaa',
        focusBorder:        '#00ff66',
        focusBg:            'rgba(0,255,102,0.06)',
        focusBgBorder:      'rgba(0,255,102,0.2)',
        focusText:          '#00ff66',
        statusRunning:      '#00ff66',
        statusStopped:      'rgba(0,68,34,0.5)',
        statusRunningBorder:'#00ff66',
        statusStoppedBorder:'#004422',
        priorityHigh:       '#ff4444',
        priorityMedium:     '#ffaa00',
        priorityLow:        '#004422',
        toolBg:             'rgba(0,255,102,0.08)',
        toolText:           '#00ffaa',
        toolBorder:         'rgba(0,255,102,0.2)',
        tabActiveBg:        'rgba(0,255,102,0.08)',
        tabActiveBorder:    '#00ff66',
        tabActiveText:      '#00ff66',
        tabHoverBg:         'rgba(0,34,0,0.7)',
        dropHighlightBorder:'#00ff66',
        dropHighlightBg:    'rgba(0,255,102,0.06)',
        executeAllBg:       '#00aa44',
        newFocusBg:         'rgba(0,255,102,0.06)',
        newFocusBorder:     'rgba(0,255,102,0.2)',
        newFocusBtn:        '#00ff66',
        similarBorder:      '#00ffaa',
        similarBadgeBg:     '#004422',
        fileTabActive:      '#00ff66',
        histTabActive:      '#00ffaa',
        thoughtLabel:       '#00ff66',
      }
      }
    },

    // ── Dark Newspaper ────────────────────────────────────────────
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
        '--user-text': '#c9c9c9d5',
      },
      fonts: ['Playfair+Display:wght@400;700', 'Crimson+Text:wght@400;600'],
      css: `
        body { font-family:'Crimson Text',Georgia,serif; line-height:1.8; font-size:16px; text-rendering:optimizeLegibility; }
        h1,h2,h3 { font-family:'Playfair Display',serif; }
        button { font-family:'Playfair Display',serif; }
        select { font-family:'Playfair Display',serif; }
        input,textarea { font-family:'Crimson Text',serif; }
        .message-content { background:#181818; border-left:3px solid #555; font-family:'Playfair Display',serif; }
        .message.user .message-content { background:#202020; border-left-color:#666; }
        .message-header { display:none !important; }
        .message-avatar { display:none !important; }
        .message.user { display:flex; align-items:center; flex-direction:row; color:var(--user-text); }
        .message-rendered { color:var(--user-text); }
        .message.user::before { content:"U "; color:var(--user-text); }
        .message.assistant { display:flex; align-items:center; }
        .message.assistant::before { content:"V "; color:var(--text-secondary); margin-right:.25em; }
        .message.system { display:flex; align-items:center; }
        .message.system::before { content:"S "; color:var(--border); margin-right:.25em; }
        #chatMessages { display:flex; flex-direction:column; gap:20px; }
        #messageInput { background:#1a1a1a; font-family:'Crimson Text',serif; }
        .send-btn { background:#333; color:#eee; border:1px solid #444; font-family:'Playfair Display',serif; }
        .send-btn:hover { background:var(--hover); border-color:#777; }
        .tool-card { border-left:4px solid var(--accent); }
        body::before { content:""; position:fixed; top:0;left:0;right:0;bottom:0; background:url('https://www.transparenttextures.com/patterns/paper-fibers.png'); opacity:.05; pointer-events:none; z-index:9999; }
      `,
      graph: {
        nodeBorder: '#e8e6e3', nodeBackground: '#1a1a1a', nodeHighlight: '#f5f5f5',
        nodeFont: '#e8e6e3', nodeFontSize: 15, edgeColor: '#b9b9b9',
        edgeHighlight: '#e8e6e3', background: '#111111',
        fontFamily: '"Crimson Text", Georgia, serif'
      },
      proactiveFocus: {
        bg:              '#0d0d0d',
        bgPanel:         '#141414',
        bgPanelHdr:      '#111111',
        bgPanelHdrHover: '#1a1a1a',
        border:          '#333333',
        borderSubtle:    '#1a1a1a',
        text:            '#a8a6a3',
        textMuted:       '#2a2a2a',
        textSecondary:   '#444444',

        accentThought:   '#e8e6e3',
        accentResponse:  '#c8c6c3',
        accentFlowchart: '#a8a6a3',
        accentConsole:   '#888683',
        accentSuccess:   '#e8e6e3',
        accentError:     '#cc4444',
        accentWarning:   '#cc8833',
        accentTool:      '#b8b6b3',
        accentStage:     '#e8e6e3',

        thoughtText:     '#d4d2cf',
        responseText:    '#e8e6e3',
        planText:        '#555353',
        stepInputText:   '#555353',
        stepOutputText:  '#b8b6b3',

        runBorder:       '#555353',
        runBorderDone:   '#2a2a2a',
        runBorderFailed: '#660000',
        runBg:           '#111111',
        runBgHover:      '#181818',
        runTitle:        '#c8c6c3',
        runTitleDone:    '#555353',
        runTitleFailed:  '#cc4444',

        stepRunning:  '#a8a6a3',
        stepDone:     '#888683',
        stepFailed:   '#cc2222',
        stepBgRunning:'rgba(168,166,163,.04)',
        stepBgDone:   'rgba(136,134,131,.04)',
        stepBgFailed: 'rgba(204,34,34,.04)',
        stepTextRunning: '#a8a6a3',
        stepTextDone:    '#c8c6c3',
        stepTextFailed:  '#cc4444',

        fileBadgeBg:     'rgba(168,166,163,.1)',
        fileBadgeText:   '#c8c6c3',
        fileBadgeBorder: 'rgba(168,166,163,.2)',

        sepColor:  '#333333',
        sepBorder: '#1a1a1a',

        stageBarBg:      'rgba(168,166,163,.06)',
        cursor:          '#e8e6e3',
        spinnerThought:  '#e8e6e3',
        spinnerResponse: '#c8c6c3',
        spinnerRun:      '#a8a6a3',

        fontFamily: '"Crimson Text",Georgia,serif',

      focusBoard: {
        bg:                 '#111111',
        bgSurface:          '#1a1a1a',
        bgSurfaceAlt:       'rgba(17,17,17,0.5)',
        bgCard:             'rgba(17,17,17,0.6)',
        bgCardForm:         'rgba(17,17,17,0.7)',
        bgCardEdit:         'rgba(17,17,17,0.8)',
        bgDropzone:         'rgba(17,17,17,0.3)',
        bgControlBar:       'rgba(17,17,17,0.5)',
        bgBtn:              'rgba(30,30,30,0.8)',
        bgBtnHover:         'rgba(232,230,227,0.1)',
        bgModal:            'linear-gradient(135deg,#1a1a1a 0%,#111111 100%)',
        border:             '#333333',
        borderFocus:        '#e8e6e3',
        text:               '#e8e6e3',
        textSecondary:      '#c8c6c3',
        textMuted:          '#a8a6a3',
        textDimmed:         '#555353',
        accentIdeas:        '#e8e6e3',
        accentNextSteps:    '#c8a060',
        accentActions:      '#a8a6a3',
        accentProgress:     '#888683',
        accentIssues:       '#cc4444',
        accentCompleted:    '#555353',
        accentQuestions:    '#b8a6c3',
        focusBorder:        '#e8e6e3',
        focusBg:            'rgba(232,230,227,0.06)',
        focusBgBorder:      'rgba(232,230,227,0.2)',
        focusText:          '#e8e6e3',
        statusRunning:      '#888683',
        statusStopped:      'rgba(85,83,83,0.5)',
        statusRunningBorder:'#888683',
        statusStoppedBorder:'#555353',
        priorityHigh:       '#cc4444',
        priorityMedium:     '#c8a060',
        priorityLow:        '#555353',
        toolBg:             'rgba(168,166,163,0.15)',
        toolText:           '#c8c6c3',
        toolBorder:         'rgba(168,166,163,0.25)',
        tabActiveBg:        'rgba(232,230,227,0.1)',
        tabActiveBorder:    '#e8e6e3',
        tabActiveText:      '#e8e6e3',
        tabHoverBg:         'rgba(30,30,30,0.7)',
        dropHighlightBorder:'#888683',
        dropHighlightBg:    'rgba(136,134,131,0.08)',
        executeAllBg:       '#888683',
        newFocusBg:         'rgba(232,230,227,0.06)',
        newFocusBorder:     'rgba(232,230,227,0.2)',
        newFocusBtn:        '#555353',
        similarBorder:      '#e8e6e3',
        similarBadgeBg:     '#333333',
        fileTabActive:      '#888683',
        histTabActive:      '#e8e6e3',
        thoughtLabel:       '#e8e6e3',
      }
      }
    },

    // ── Bidwells Dark ─────────────────────────────────────────────
    bidwellsDark: {
      name: 'Bidwells Dark',
      variables: {
        '--bg': '#0a0f1a',
        '--bg-surface': '#111827',
        '--panel-bg': '#0d1522',
        '--text': '#dbeafe',
        '--text-secondary': '#93adc9',
        '--accent': '#1e3a8a',
        '--accent-muted': 'rgba(30, 58, 138, 0.65)',
        '--border': '#1f2c45',
        '--border-subtle': '#162032',
        '--hover': '#1e293b',
        '--text-inverted': '#ffffff',
        '--user-bg': 'linear-gradient(135deg, #1e3a8a 0%, #2848a8 100%)',
        '--success': '#22c55e',
        '--warning': '#fbbf24',
        '--error': '#ef4444'
      },
      fonts: ['Inter:wght@400;500;600'],
      css: `
        body { font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; background:var(--bg); color:var(--text); }
        .chat-panel,.graph-panel { background:var(--panel-bg); border:1px solid var(--border); box-shadow:inset 0 0 12px rgba(0,0,0,.25); }
        h1,h2,h3 { color:var(--text); font-weight:600; letter-spacing:-.02em; }
        .message.assistant .message-content { background:#111827; border:1px solid var(--border-subtle); padding:.6em .9em; border-radius:6px; }
        .message.user .message-content { background:var(--user-bg); color:var(--text-inverted); border:none; padding:.6em .9em; border-radius:6px; }
        button { background:var(--accent); color:white; border:none; padding:.5em 1.1em; border-radius:6px; font-weight:500; }
        button:hover { background:#2745a1; box-shadow:0 4px 10px rgba(30,58,138,.3); cursor:pointer; }
        input,textarea { background:#0f172a; border:1px solid var(--border); color:var(--text); }
        input:focus,textarea:focus { border-color:var(--accent); box-shadow:0 0 0 2px rgba(30,58,138,.3); outline:none; }
        .status-success{color:var(--success);} .status-warning{color:var(--warning);} .status-error{color:var(--error);}
      `,
      graph: {
        nodeBorder: '#1e3a8a', nodeBackground: '#0f172a', nodeHighlight: '#3b82f6',
        nodeFont: '#dbeafe', nodeFontSize: 14, edgeColor: '#334155',
        edgeHighlight: '#1e3a8a', background: '#0a0f1a',
        fontFamily: '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
      },
      proactiveFocus: {
        bg:              '#060c14',
        bgPanel:         '#0a1220',
        bgPanelHdr:      '#0d1522',
        bgPanelHdrHover: '#111f30',
        border:          '#1a2a40',
        borderSubtle:    '#0d1828',
        text:            '#93adc9',
        textMuted:       '#162032',
        textSecondary:   '#1f2c45',

        accentThought:   '#3b6fd4',
        accentResponse:  '#2d5abf',
        accentFlowchart: '#fbbf24',
        accentConsole:   '#93adc9',
        accentSuccess:   '#22c55e',
        accentError:     '#ef4444',
        accentWarning:   '#fbbf24',
        accentTool:      '#60a5fa',
        accentStage:     '#3b6fd4',

        thoughtText:     '#a8c8f0',
        responseText:    '#dbeafe',
        planText:        '#2a3f5f',
        stepInputText:   '#2a3f5f',
        stepOutputText:  '#4ade80',

        runBorder:       '#2d5abf',
        runBorderDone:   '#1a2a40',
        runBorderFailed: '#5f1d1d',
        runBg:           '#0a1220',
        runBgHover:      '#0d1828',
        runTitle:        '#60a5fa',
        runTitleDone:    '#3a5070',
        runTitleFailed:  '#f87171',

        stepRunning:  '#2d5abf',
        stepDone:     '#16a34a',
        stepFailed:   '#dc2626',
        stepBgRunning:'rgba(45,90,191,.05)',
        stepBgDone:   'rgba(22,163,74,.04)',
        stepBgFailed: 'rgba(220,38,38,.04)',
        stepTextRunning: '#93adc9',
        stepTextDone:    '#4ade80',
        stepTextFailed:  '#fca5a5',

        fileBadgeBg:     'rgba(59,111,212,.12)',
        fileBadgeText:   '#60a5fa',
        fileBadgeBorder: 'rgba(59,111,212,.25)',

        sepColor:  '#1a2a40',
        sepBorder: '#0a1220',

        stageBarBg:      'rgba(45,90,191,.07)',
        cursor:          '#60a5fa',
        spinnerThought:  '#3b6fd4',
        spinnerResponse: '#2d5abf',
        spinnerRun:      '#2d5abf',

        fontFamily: '"Inter","Monaco","Menlo","Courier New",monospace',

      focusBoard: {
        bg:                 '#0a0f1a',
        bgSurface:          '#111827',
        bgSurfaceAlt:       'rgba(10,15,26,0.5)',
        bgCard:             'rgba(10,15,26,0.6)',
        bgCardForm:         'rgba(10,15,26,0.7)',
        bgCardEdit:         'rgba(10,15,26,0.8)',
        bgDropzone:         'rgba(10,15,26,0.3)',
        bgControlBar:       'rgba(10,15,26,0.5)',
        bgBtn:              'rgba(17,24,39,0.8)',
        bgBtnHover:         'rgba(59,130,246,0.15)',
        bgModal:            'linear-gradient(135deg,#111827 0%,#0a0f1a 100%)',
        border:             '#1f2c45',
        borderFocus:        '#3b82f6',
        text:               '#dbeafe',
        textSecondary:      '#bdd3f0',
        textMuted:          '#93adc9',
        textDimmed:         '#3a5070',
        accentIdeas:        '#3b6fd4',
        accentNextSteps:    '#fbbf24',
        accentActions:      '#3b82f6',
        accentProgress:     '#22c55e',
        accentIssues:       '#ef4444',
        accentCompleted:    '#3a5070',
        accentQuestions:    '#60a5fa',
        focusBorder:        '#1e3a8a',
        focusBg:            'rgba(30,58,138,0.12)',
        focusBgBorder:      'rgba(30,58,138,0.35)',
        focusText:          '#93c5fd',
        statusRunning:      '#22c55e',
        statusStopped:      'rgba(58,80,112,0.5)',
        statusRunningBorder:'#22c55e',
        statusStoppedBorder:'#3a5070',
        priorityHigh:       '#ef4444',
        priorityMedium:     '#fbbf24',
        priorityLow:        '#3a5070',
        toolBg:             'rgba(59,130,246,0.15)',
        toolText:           '#60a5fa',
        toolBorder:         'rgba(59,130,246,0.25)',
        tabActiveBg:        'rgba(59,130,246,0.15)',
        tabActiveBorder:    '#3b82f6',
        tabActiveText:      '#dbeafe',
        tabHoverBg:         'rgba(17,24,39,0.7)',
        dropHighlightBorder:'#22c55e',
        dropHighlightBg:    'rgba(34,197,94,0.08)',
        executeAllBg:       '#16a34a',
        newFocusBg:         'rgba(59,130,246,0.08)',
        newFocusBorder:     'rgba(59,130,246,0.25)',
        newFocusBtn:        '#3b82f6',
        similarBorder:      '#1e3a8a',
        similarBadgeBg:     '#1e3a8a',
        fileTabActive:      '#3b82f6',
        histTabActive:      '#1e3a8a',
        thoughtLabel:       '#3b6fd4',
      }
      }
    },

    // ── Pixel Art ─────────────────────────────────────────────────
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
        body { font-family:'Press Start 2P',monospace; font-size:12px; image-rendering:pixelated; letter-spacing:.05em; }
        button,select,input,textarea { font-family:'Press Start 2P',monospace; }
        h1,h2,h3 { text-shadow:2px 2px #000; }
        .chat-panel,.graph-panel { border:2px solid var(--border); box-shadow:0 0 12px var(--accent); image-rendering:pixelated; }
        #chatMessages { font-size:12px; line-height:1.2; }
        .message-avatar { width:28px; height:28px; background:#220022; border:2px solid var(--accent); font-size:10px; text-shadow:0 0 4px var(--accent); }
        .message.assistant .message-avatar { border-color:#33ffff; color:#33ffff; text-shadow:0 0 4px #33ffff; }
        .message-content { background:rgba(0,0,0,.6); border:2px solid var(--accent); border-radius:4px; line-height:1.2; text-shadow:0 0 4px var(--text); }
        .message.user .message-content { border-color:var(--user-text); color:var(--user-text); text-shadow:0 0 4px var(--user-text); }
        #messageInput { background:#110022; border:2px solid var(--accent); font-size:11px; caret-color:var(--accent); text-transform:uppercase; }
        #messageInput::placeholder { color:#330044; }
        .send-btn { background:#220033; color:var(--accent); border:2px solid var(--accent); text-transform:uppercase; }
        .send-btn:hover { background:var(--hover); color:#fff; box-shadow:0 0 12px var(--accent); }
        #graph { background:repeating-linear-gradient(to bottom,#0d0d1a,#0d0d1a 2px,#110033 3px); image-rendering:pixelated; }
        @keyframes neonFlicker { 0%,100%{opacity:1}50%{opacity:.95}25%,75%{opacity:.97} }
        body { animation:neonFlicker .1s infinite; }
        body::before { content:""; position:fixed; top:0;left:0;right:0;bottom:0; background:repeating-linear-gradient(to bottom,rgba(255,255,255,.02) 0px,rgba(255,255,255,.02) 1px,transparent 2px); pointer-events:none; z-index:9999; image-rendering:pixelated; }
      `,
      graph: {
        nodeBorder: '#ff33cc', nodeBackground: '#1a0d2f', nodeHighlight: '#ff77ff',
        nodeFont: '#66f0ff', nodeFontSize: 11, edgeColor: '#440066',
        edgeHighlight: '#9b00ff', background: '#0d0d1a',
        fontFamily: '"Press Start 2P", monospace', nodeShape: 'box', edgeWidth: 3
      },
      proactiveFocus: {
        bg:              '#0a0a12',
        bgPanel:         '#130a22',
        bgPanelHdr:      '#1a0a2e',
        bgPanelHdrHover: '#220a3a',
        border:          '#440066',
        borderSubtle:    '#220033',
        text:            '#66f0ff',
        textMuted:       '#220033',
        textSecondary:   '#330055',

        accentThought:   '#ff33cc',
        accentResponse:  '#66f0ff',
        accentFlowchart: '#ff33cc',
        accentConsole:   '#4488aa',
        accentSuccess:   '#33ff99',
        accentError:     '#ff3333',
        accentWarning:   '#ffaa00',
        accentTool:      '#66f0ff',
        accentStage:     '#ff33cc',

        thoughtText:     '#ffaaf0',
        responseText:    '#66f0ff',
        planText:        '#2a1a44',
        stepInputText:   '#2a1a44',
        stepOutputText:  '#33ff99',

        runBorder:       '#ff33cc',
        runBorderDone:   '#330055',
        runBorderFailed: '#660000',
        runBg:           '#0d0020',
        runBgHover:      '#110033',
        runTitle:        '#ff33cc',
        runTitleDone:    '#440066',
        runTitleFailed:  '#ff3333',

        stepRunning:  '#ff33cc',
        stepDone:     '#33ff99',
        stepFailed:   '#ff3333',
        stepBgRunning:'rgba(255,51,204,.06)',
        stepBgDone:   'rgba(51,255,153,.04)',
        stepBgFailed: 'rgba(255,51,51,.04)',
        stepTextRunning: '#66f0ff',
        stepTextDone:    '#33ff99',
        stepTextFailed:  '#ff6666',

        fileBadgeBg:     'rgba(51,255,153,.1)',
        fileBadgeText:   '#33ff99',
        fileBadgeBorder: 'rgba(51,255,153,.25)',

        sepColor:  '#440066',
        sepBorder: '#1a0033',

        stageBarBg:      'rgba(255,51,204,.08)',
        cursor:          '#ff33cc',
        spinnerThought:  '#ff33cc',
        spinnerResponse: '#66f0ff',
        spinnerRun:      '#ff33cc',

        fontFamily: '"Press Start 2P",monospace',

      focusBoard: {
        bg:                 '#0d0d1a',
        bgSurface:          '#1a0d2f',
        bgSurfaceAlt:       'rgba(13,13,26,0.5)',
        bgCard:             'rgba(13,13,26,0.6)',
        bgCardForm:         'rgba(13,13,26,0.7)',
        bgCardEdit:         'rgba(13,13,26,0.8)',
        bgDropzone:         'rgba(13,13,26,0.3)',
        bgControlBar:       'rgba(13,13,26,0.5)',
        bgBtn:              'rgba(26,13,47,0.8)',
        bgBtnHover:         'rgba(255,51,204,0.15)',
        bgModal:            'linear-gradient(135deg,#1a0d2f 0%,#0d0d1a 100%)',
        border:             '#440066',
        borderFocus:        '#ff33cc',
        text:               '#66f0ff',
        textSecondary:      '#44bbdd',
        textMuted:          '#4488aa',
        textDimmed:         '#2a1a44',
        accentIdeas:        '#ff33cc',
        accentNextSteps:    '#ffaa00',
        accentActions:      '#66f0ff',
        accentProgress:     '#33ff99',
        accentIssues:       '#ff3333',
        accentCompleted:    '#2a1a44',
        accentQuestions:    '#ff33cc',
        focusBorder:        '#ff33cc',
        focusBg:            'rgba(255,51,204,0.08)',
        focusBgBorder:      'rgba(255,51,204,0.25)',
        focusText:          '#ffaaee',
        statusRunning:      '#33ff99',
        statusStopped:      'rgba(42,26,68,0.5)',
        statusRunningBorder:'#33ff99',
        statusStoppedBorder:'#2a1a44',
        priorityHigh:       '#ff3333',
        priorityMedium:     '#ffaa00',
        priorityLow:        '#2a1a44',
        toolBg:             'rgba(102,240,255,0.12)',
        toolText:           '#66f0ff',
        toolBorder:         'rgba(102,240,255,0.25)',
        tabActiveBg:        'rgba(255,51,204,0.15)',
        tabActiveBorder:    '#ff33cc',
        tabActiveText:      '#66f0ff',
        tabHoverBg:         'rgba(26,13,47,0.7)',
        dropHighlightBorder:'#33ff99',
        dropHighlightBg:    'rgba(51,255,153,0.08)',
        executeAllBg:       '#33ff99',
        newFocusBg:         'rgba(255,51,204,0.08)',
        newFocusBorder:     'rgba(255,51,204,0.25)',
        newFocusBtn:        '#ff33cc',
        similarBorder:      '#ff33cc',
        similarBadgeBg:     '#440066',
        fileTabActive:      '#66f0ff',
        histTabActive:      '#ff33cc',
        thoughtLabel:       '#ff33cc',
      }
      }
    },

    // ── Retro Gaming ──────────────────────────────────────────────
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
        header { background:var(--bg); }
        body { background:radial-gradient(circle at center,#101010 0%,#000 100%); font-family:'Press Start 2P',monospace; font-size:11px; text-transform:uppercase; image-rendering:pixelated; }
        button,select,input,textarea { font-family:'Press Start 2P',monospace; }
        .chat-panel,.graph-panel { border:2px solid var(--border); box-shadow:0 0 12px var(--accent); image-rendering:pixelated; }
        #chatMessages { font-size:12px; line-height:1.2; }
        .message-avatar { width:28px; height:28px; background:#220022; border:2px solid var(--accent); font-size:10px; text-shadow:0 0 4px var(--accent); }
        .message.assistant .message-avatar { border-color:#33ffff; color:#33ffff; text-shadow:0 0 4px #33ffff; }
        .message-content { background:rgba(0,0,0,.6); border:2px solid var(--accent); border-radius:4px; line-height:1.2; text-shadow:0 0 4px var(--text); }
        .message.user .message-content { border-color:var(--user-text); color:var(--user-text); text-shadow:0 0 4px var(--user-text); }
        .input-area { border-top:2px solid var(--border); }
        @keyframes crtFlicker { 0%,100%{opacity:1}50%{opacity:.98} }
        body { animation:crtFlicker .1s infinite; }
      `,
      graph: {
        nodeBorder: '#00ffcc', nodeBackground: '#001a1a', nodeHighlight: '#00ffff',
        nodeFont: '#00ffcc', nodeFontSize: 10, edgeColor: '#ff0077',
        edgeHighlight: '#ff33aa', background: '#000000',
        fontFamily: '"Press Start 2P", monospace', nodeShape: 'box', edgeWidth: 2
      },
      proactiveFocus: {
        bg:              '#000000',
        bgPanel:         '#000000',
        bgPanelHdr:      '#050505',
        bgPanelHdrHover: '#0a0a0a',
        border:          '#006655',
        borderSubtle:    '#003322',
        text:            '#00aa88',
        textMuted:       '#003322',
        textSecondary:   '#004433',

        accentThought:   '#ff0077',
        accentResponse:  '#00ffcc',
        accentFlowchart: '#ff3794',
        accentConsole:   '#00aa88',
        accentSuccess:   '#00ffcc',
        accentError:     '#ff0077',
        accentWarning:   '#ffaa00',
        accentTool:      '#00ffcc',
        accentStage:     '#00ffcc',

        thoughtText:     '#ff88bb',
        responseText:    '#00ffcc',
        planText:        '#004433',
        stepInputText:   '#004433',
        stepOutputText:  '#00ffcc',

        runBorder:       '#00ffcc',
        runBorderDone:   '#004433',
        runBorderFailed: '#660022',
        runBg:           '#000000',
        runBgHover:      '#001a1a',
        runTitle:        '#00ffcc',
        runTitleDone:    '#005544',
        runTitleFailed:  '#ff0077',

        stepRunning:  '#00ffcc',
        stepDone:     '#00aa88',
        stepFailed:   '#ff0077',
        stepBgRunning:'rgba(0,255,204,.04)',
        stepBgDone:   'rgba(0,170,136,.04)',
        stepBgFailed: 'rgba(255,0,119,.04)',
        stepTextRunning: '#00aa88',
        stepTextDone:    '#00ffcc',
        stepTextFailed:  '#ff3794',

        fileBadgeBg:     'rgba(0,255,204,.08)',
        fileBadgeText:   '#00ffcc',
        fileBadgeBorder: 'rgba(0,255,204,.2)',

        sepColor:  '#004433',
        sepBorder: '#002211',

        stageBarBg:      'rgba(0,255,204,.06)',
        cursor:          '#00ffcc',
        spinnerThought:  '#ff0077',
        spinnerResponse: '#00ffcc',
        spinnerRun:      '#00ffcc',

        fontFamily: '"Press Start 2P",monospace',

      focusBoard: {
        bg:                 '#000000',
        bgSurface:          '#001a1a',
        bgSurfaceAlt:       'rgba(0,26,26,0.5)',
        bgCard:             'rgba(0,26,26,0.6)',
        bgCardForm:         'rgba(0,26,26,0.7)',
        bgCardEdit:         'rgba(0,26,26,0.8)',
        bgDropzone:         'rgba(0,26,26,0.3)',
        bgControlBar:       'rgba(0,26,26,0.5)',
        bgBtn:              'rgba(0,34,0,0.8)',
        bgBtnHover:         'rgba(0,255,204,0.12)',
        bgModal:            'linear-gradient(135deg,#001a1a 0%,#000000 100%)',
        border:             '#006655',
        borderFocus:        '#00ffcc',
        text:               '#00ffcc',
        textSecondary:      '#00ccaa',
        textMuted:          '#00aa88',
        textDimmed:         '#004433',
        accentIdeas:        '#ff0077',
        accentNextSteps:    '#ffaa00',
        accentActions:      '#00ffcc',
        accentProgress:     '#00ffcc',
        accentIssues:       '#ff0077',
        accentCompleted:    '#004433',
        accentQuestions:    '#ff3794',
        focusBorder:        '#00ffcc',
        focusBg:            'rgba(0,255,204,0.06)',
        focusBgBorder:      'rgba(0,255,204,0.2)',
        focusText:          '#00ffcc',
        statusRunning:      '#00ffcc',
        statusStopped:      'rgba(0,68,51,0.5)',
        statusRunningBorder:'#00ffcc',
        statusStoppedBorder:'#004433',
        priorityHigh:       '#ff0077',
        priorityMedium:     '#ffaa00',
        priorityLow:        '#004433',
        toolBg:             'rgba(0,255,204,0.1)',
        toolText:           '#00ffcc',
        toolBorder:         'rgba(0,255,204,0.2)',
        tabActiveBg:        'rgba(0,255,204,0.1)',
        tabActiveBorder:    '#00ffcc',
        tabActiveText:      '#00ffcc',
        tabHoverBg:         'rgba(0,34,0,0.7)',
        dropHighlightBorder:'#00ffcc',
        dropHighlightBg:    'rgba(0,255,204,0.06)',
        executeAllBg:       '#00aa88',
        newFocusBg:         'rgba(0,255,204,0.06)',
        newFocusBorder:     'rgba(0,255,204,0.2)',
        newFocusBtn:        '#00ffcc',
        similarBorder:      '#ff0077',
        similarBadgeBg:     '#004433',
        fileTabActive:      '#00ffcc',
        histTabActive:      '#ff0077',
        thoughtLabel:       '#00ffcc',
      }
      }
    },

    // ── Sunset Glow ───────────────────────────────────────────────
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
        body { font-family:'Share Tech Mono','Segoe UI',sans-serif; }
        button,select,input,textarea { font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; }
        .chat-panel,.graph-panel { box-shadow:inset 0 0 10px rgba(0,0,0,.2); }
        .message-content { background:rgba(255,200,160,.1); border-left:3px solid var(--border); }
        .message.user .message-content { background:rgba(255,175,100,.2); border-left-color:var(--user-text); color:var(--user-text); }
        #messageInput:focus { border-color:var(--accent); }
      `,
      graph: {
        nodeBorder: '#ff6f61', nodeBackground: '#3e2a45', nodeHighlight: '#ffa07a',
        nodeFont: '#ffd8a8', nodeFontSize: 14, edgeColor: '#7e5a7e',
        edgeHighlight: '#a07aa0', background: '#2b1a2f',
        fontFamily: '"Share Tech Mono", monospace'
      },
      proactiveFocus: {
        bg:              '#1e1023',
        bgPanel:         '#2b1a2f',
        bgPanelHdr:      '#321e37',
        bgPanelHdrHover: '#3e2a45',
        border:          '#5e3a5e',
        borderSubtle:    '#3e1e3e',
        text:            '#ccaa88',
        textMuted:       '#3e1e3e',
        textSecondary:   '#5e3a5e',

        accentThought:   '#ff6f61',
        accentResponse:  '#ffa07a',
        accentFlowchart: '#ffb347',
        accentConsole:   '#ccaa88',
        accentSuccess:   '#88cc88',
        accentError:     '#ff6655',
        accentWarning:   '#ffb347',
        accentTool:      '#ffd8a8',
        accentStage:     '#ff6f61',

        thoughtText:     '#ffcc99',
        responseText:    '#ffd8a8',
        planText:        '#5e3a5e',
        stepInputText:   '#5e3a5e',
        stepOutputText:  '#88cc88',

        runBorder:       '#ff6f61',
        runBorderDone:   '#5e3a5e',
        runBorderFailed: '#7f1d1d',
        runBg:           '#221430',
        runBgHover:      '#2b1a2f',
        runTitle:        '#ffa07a',
        runTitleDone:    '#7e5a7e',
        runTitleFailed:  '#ff6655',

        stepRunning:  '#ff6f61',
        stepDone:     '#88aa66',
        stepFailed:   '#cc4433',
        stepBgRunning:'rgba(255,111,97,.05)',
        stepBgDone:   'rgba(136,170,102,.04)',
        stepBgFailed: 'rgba(204,68,51,.04)',
        stepTextRunning: '#ccaa88',
        stepTextDone:    '#88cc88',
        stepTextFailed:  '#ff8877',

        fileBadgeBg:     'rgba(136,170,102,.1)',
        fileBadgeText:   '#aaccaa',
        fileBadgeBorder: 'rgba(136,170,102,.2)',

        sepColor:  '#5e3a5e',
        sepBorder: '#2b1a2f',

        stageBarBg:      'rgba(255,111,97,.07)',
        cursor:          '#ffa07a',
        spinnerThought:  '#ff6f61',
        spinnerResponse: '#ffa07a',
        spinnerRun:      '#ffa07a',

        fontFamily: '"Share Tech Mono","Courier New",monospace',

      focusBoard: {
        bg:                 '#2b1a2f',
        bgSurface:          '#3e2a45',
        bgSurfaceAlt:       'rgba(43,26,47,0.5)',
        bgCard:             'rgba(43,26,47,0.6)',
        bgCardForm:         'rgba(43,26,47,0.7)',
        bgCardEdit:         'rgba(43,26,47,0.8)',
        bgDropzone:         'rgba(43,26,47,0.3)',
        bgControlBar:       'rgba(43,26,47,0.5)',
        bgBtn:              'rgba(62,42,69,0.8)',
        bgBtnHover:         'rgba(255,111,97,0.2)',
        bgModal:            'linear-gradient(135deg,#3e2a45 0%,#2b1a2f 100%)',
        border:             '#7e5a7e',
        borderFocus:        '#ff6f61',
        text:               '#ffd8a8',
        textSecondary:      '#eec898',
        textMuted:          '#ccaa88',
        textDimmed:         '#7e5a7e',
        accentIdeas:        '#ff6f61',
        accentNextSteps:    '#ffb347',
        accentActions:      '#ffa07a',
        accentProgress:     '#88cc88',
        accentIssues:       '#ff6655',
        accentCompleted:    '#7e5a7e',
        accentQuestions:    '#ffb347',
        focusBorder:        '#ff6f61',
        focusBg:            'rgba(255,111,97,0.1)',
        focusBgBorder:      'rgba(255,111,97,0.3)',
        focusText:          '#ffcc99',
        statusRunning:      '#88cc88',
        statusStopped:      'rgba(126,90,126,0.5)',
        statusRunningBorder:'#88cc88',
        statusStoppedBorder:'#7e5a7e',
        priorityHigh:       '#ff6655',
        priorityMedium:     '#ffb347',
        priorityLow:        '#7e5a7e',
        toolBg:             'rgba(255,160,122,0.15)',
        toolText:           '#ffd8a8',
        toolBorder:         'rgba(255,160,122,0.25)',
        tabActiveBg:        'rgba(255,111,97,0.2)',
        tabActiveBorder:    '#ff6f61',
        tabActiveText:      '#ffd8a8',
        tabHoverBg:         'rgba(62,42,69,0.7)',
        dropHighlightBorder:'#88cc88',
        dropHighlightBg:    'rgba(136,204,136,0.1)',
        executeAllBg:       '#88cc88',
        newFocusBg:         'rgba(255,111,97,0.08)',
        newFocusBorder:     'rgba(255,111,97,0.25)',
        newFocusBtn:        '#ff6f61',
        similarBorder:      '#ff6f61',
        similarBadgeBg:     '#5e3a5e',
        fileTabActive:      '#ffa07a',
        histTabActive:      '#ff6f61',
        thoughtLabel:       '#ff6f61',
      }
      }
    },

    // ── Rainbow Noir ──────────────────────────────────────────────
    rainbowNoir: {
      name: 'Rainbow Noir',
      variables: {
        '--bg': '#0b0b0e',
        '--bg-surface': '#141418',
        '--panel-bg': '#1d1d24',
        '--text': 'linear-gradient(90deg, #ff5555, #f1fa8c, #50fa7b, #8be9fd, #bd93f9, #ff79c6)',
        '--text-secondary': '#bbbbbb',
        '--accent': '#ff79c6',
        '--accent-muted': '#ff79c666',
        '--border': '#444',
        '--border-subtle': '#2a2a2f',
        '--hover': '#bd93f9',
        '--text-inverted': '#ffffff',
        '--user-text': 'linear-gradient(90deg, #ff9a9e, #fad0c4, #fbc2eb, #a18cd1, #84fab0, #8fd3f4)'
      },
      fonts: ['Share+Tech+Mono'],
      css: `
        body { font-family:'Share Tech Mono','Segoe UI',sans-serif; color:#ffffff; }
        button,select,input,textarea { font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; }
        .message-content,.message.user .message-content { background:rgba(255,255,255,.03); border-left:3px solid var(--border); -webkit-background-clip:text; background-clip:text; }
        .message-content { color:transparent; background-image:var(--text); }
        .message.user .message-content { color:transparent; background-image:var(--user-text); border-left-color:#ff79c6; }
        .chat-panel,.graph-panel { box-shadow:inset 0 0 12px rgba(0,0,0,.4); }
        #messageInput:focus { border-color:var(--accent); }
      `,
      graph: {
        nodeBorder: '#ff79c6', nodeBackground: '#1d1d24', nodeHighlight: '#bd93f9',
        nodeFont: '#ffffff', nodeFontSize: 14, edgeColor: '#444',
        edgeHighlight: '#ff79c6', background: '#0b0b0e',
        fontFamily: '"Share Tech Mono", monospace'
      },
      proactiveFocus: {
        bg:              '#080809',
        bgPanel:         '#111115',
        bgPanelHdr:      '#141418',
        bgPanelHdrHover: '#1a1a20',
        border:          '#2a2a35',
        borderSubtle:    '#141418',
        text:            '#bbbbbb',
        textMuted:       '#222228',
        textSecondary:   '#333340',

        accentThought:   '#bd93f9',
        accentResponse:  '#8be9fd',
        accentFlowchart: '#f1fa8c',
        accentConsole:   '#bbbbbb',
        accentSuccess:   '#50fa7b',
        accentError:     '#ff5555',
        accentWarning:   '#f1fa8c',
        accentTool:      '#8be9fd',
        accentStage:     '#ff79c6',

        thoughtText:     '#d6b8fc',
        responseText:    '#e8eeff',
        planText:        '#3a3a50',
        stepInputText:   '#3a3a50',
        stepOutputText:  '#50fa7b',

        runBorder:       '#ff79c6',
        runBorderDone:   '#2a2a35',
        runBorderFailed: '#7f1d1d',
        runBg:           '#0f0f14',
        runBgHover:      '#141418',
        runTitle:        '#ff79c6',
        runTitleDone:    '#444455',
        runTitleFailed:  '#ff5555',

        stepRunning:  '#8be9fd',
        stepDone:     '#50fa7b',
        stepFailed:   '#ff5555',
        stepBgRunning:'rgba(139,233,253,.04)',
        stepBgDone:   'rgba(80,250,123,.04)',
        stepBgFailed: 'rgba(255,85,85,.04)',
        stepTextRunning: '#bbbbbb',
        stepTextDone:    '#50fa7b',
        stepTextFailed:  '#ff7777',

        fileBadgeBg:     'rgba(80,250,123,.1)',
        fileBadgeText:   '#50fa7b',
        fileBadgeBorder: 'rgba(80,250,123,.2)',

        sepColor:  '#333344',
        sepBorder: '#111115',

        stageBarBg:      'rgba(255,121,198,.07)',
        cursor:          '#ff79c6',
        spinnerThought:  '#bd93f9',
        spinnerResponse: '#8be9fd',
        spinnerRun:      '#ff79c6',

        fontFamily: '"Share Tech Mono","Courier New",monospace',
      },
      focusBoard: {
        bg:                 '#0b0b0e',
        bgSurface:          '#1d1d24',
        bgSurfaceAlt:       'rgba(11,11,14,0.5)',
        bgCard:             'rgba(11,11,14,0.6)',
        bgCardForm:         'rgba(11,11,14,0.7)',
        bgCardEdit:         'rgba(11,11,14,0.8)',
        bgDropzone:         'rgba(11,11,14,0.3)',
        bgControlBar:       'rgba(11,11,14,0.5)',
        bgBtn:              'rgba(29,29,36,0.8)',
        bgBtnHover:         'rgba(255,121,198,0.15)',
        bgModal:            'linear-gradient(135deg,#1d1d24 0%,#0b0b0e 100%)',
        border:             '#333344',
        borderFocus:        '#ff79c6',
        text:               '#f8f8f8',
        textSecondary:      '#e0e0e0',
        textMuted:          '#bbbbbb',
        textDimmed:         '#555566',
        accentIdeas:        '#bd93f9',
        accentNextSteps:    '#f1fa8c',
        accentActions:      '#8be9fd',
        accentProgress:     '#50fa7b',
        accentIssues:       '#ff5555',
        accentCompleted:    '#555566',
        accentQuestions:    '#ff79c6',
        focusBorder:        '#bd93f9',
        focusBg:            'rgba(189,147,249,0.08)',
        focusBgBorder:      'rgba(189,147,249,0.25)',
        focusText:          '#d6b8fc',
        statusRunning:      '#50fa7b',
        statusStopped:      'rgba(85,85,102,0.5)',
        statusRunningBorder:'#50fa7b',
        statusStoppedBorder:'#555566',
        priorityHigh:       '#ff5555',
        priorityMedium:     '#f1fa8c',
        priorityLow:        '#555566',
        toolBg:             'rgba(139,233,253,0.12)',
        toolText:           '#8be9fd',
        toolBorder:         'rgba(139,233,253,0.25)',
        tabActiveBg:        'rgba(255,121,198,0.15)',
        tabActiveBorder:    '#ff79c6',
        tabActiveText:      '#f8f8f8',
        tabHoverBg:         'rgba(29,29,36,0.7)',
        dropHighlightBorder:'#50fa7b',
        dropHighlightBg:    'rgba(80,250,123,0.08)',
        executeAllBg:       '#50fa7b',
        newFocusBg:         'rgba(255,121,198,0.08)',
        newFocusBorder:     'rgba(255,121,198,0.25)',
        newFocusBtn:        '#ff79c6',
        similarBorder:      '#bd93f9',
        similarBadgeBg:     '#333344',
        fileTabActive:      '#8be9fd',
        histTabActive:      '#bd93f9',
        thoughtLabel:       '#bd93f9',
      }
    },
  };

  // ─────────────────────────────────────────────────────────────────────────────
  // Theme Manager — unchanged public API, plus _applyThemeToPfUI()
  // ─────────────────────────────────────────────────────────────────────────────
  class ThemeManager {
    constructor() {
      this.currentTheme = null;
      this.styleEl      = null;
      this.pfStyleEl    = null;   // NEW: dedicated <style> for pf CSS vars
      this.fontEl       = null;
      this.listeners    = new Set();
      this._hooked      = false;
    }

    init() {
      this.styleEl   = document.createElement('style');
      this.styleEl.setAttribute('data-theme-style', '');
      document.head.appendChild(this.styleEl);

      // Dedicated element so pf vars don't conflict with main :root block
      this.pfStyleEl = document.createElement('style');
      this.pfStyleEl.setAttribute('data-pf-theme-style', '');
      document.head.appendChild(this.pfStyleEl);

      this.fontEl    = document.createElement('link');
      this.fontEl.rel = 'stylesheet';
      document.head.appendChild(this.fontEl);

      const savedTheme = localStorage.getItem('theme') || 'default';
      this.apply(savedTheme);
      // this._watchForNetwork();
    }

    apply(themeName) {
      const theme = themes[themeName];
      if (!theme) {
        console.warn(`Theme "${themeName}" not found, using default`);
        return this.apply('default');
      }

      this.currentTheme = themeName;
      localStorage.setItem('theme', themeName);

      if (theme.fonts?.length) {
        const fontUrl = `https://fonts.googleapis.com/css2?${theme.fonts.map(f => `family=${f}`).join('&')}&display=swap`;
        this.fontEl.href = fontUrl;
      } else {
        this.fontEl.href = '';
      }

      const variablesCSS = Object.entries(theme.variables)
        .map(([k, v]) => `${k}: ${v};`).join('\n        ');

      this.styleEl.textContent = `
        :root { ${variablesCSS} }
        ${baseCSS}
        ${this._getCommonComponentCSS()}
        ${theme.css || ''}
      `;

      // Apply --pf-* variables for the ProactiveFocus UI
      this._applyThemeToPfUI(theme);

      this._applyToGraph(theme);
      this.listeners.forEach(fn => fn(themeName, theme));
      console.log(`Theme applied: ${theme.name}`);
    }

    // ── NEW: writes --pf-* custom properties into :root ──────────
    _applyThemeToPfUI(theme) {
      if (!this.pfStyleEl) return;
      const pf = theme.proactiveFocus;
      if (!pf) return;

      const vars = Object.entries(pf)
        .filter(([k]) => k !== 'fontFamily')
        .map(([k, v]) => `--pf-${k.replace(/([A-Z])/g, m => '-' + m.toLowerCase())}: ${v};`)
        .join('\n  ');

      const fontVar = pf.fontFamily ? `--pf-font-family: ${pf.fontFamily};` : '';

      this.pfStyleEl.textContent = `:root {\n  ${vars}\n  ${fontVar}\n}`;

      console.log(`PF theme vars applied for: ${theme.name}`);
    }

    _getCommonComponentCSS() {
      return `
        body { background:var(--bg); color:var(--text); }
        a { color:var(--accent); text-decoration:none; transition:color var(--transition-fast); }
        a:hover { color:var(--hover); }
        h1,h2,h3 { color:var(--accent); }
        button { color:var(--text-inverted); background:var(--accent); border:none; border-radius:var(--radius-sm); padding:8px 16px; cursor:pointer; transition:background var(--transition-fast),transform var(--transition-fast); }
        button:hover { background:var(--hover); }
        input,textarea,select { color:var(--text); background:var(--bg-surface); border:1px solid var(--border); border-radius:var(--radius-sm); padding:10px 14px; transition:border-color var(--transition-fast),box-shadow var(--transition-fast); }
        input:focus,textarea:focus,select:focus { outline:none; border-color:var(--accent); }
        .tab { background:transparent; color:var(--text-secondary); border:none; padding:10px 16px; cursor:pointer; transition:all var(--transition-fast); }
        .tab:hover { color:var(--text); background:var(--bg-surface); }
        .tab.active { background:var(--accent); color:var(--text-inverted); font-weight:bold; border-radius:var(--radius-sm); }
        .tab-content { background:var(--bg); color:var(--text); }
        .chat-panel,.graph-panel { background:var(--panel-bg); border:1px solid var(--border); border-radius:var(--radius-xl); }
        #chatMessages { background:var(--panel-bg); color:var(--text); padding:16px; display:flex; flex-direction:column; gap:12px; }
        .message { display:flex; gap:10px; align-items:flex-start; }
        .message-avatar { width:32px; height:32px; background:var(--bg-surface); border:1px solid var(--border); border-radius:var(--radius-sm); display:flex; align-items:center; justify-content:center; font-weight:600; font-size:12px; color:var(--text-secondary); flex-shrink:0; }
        .message-content { background:var(--bg-surface); color:var(--text); padding:12px 16px; border-radius:var(--radius-md); border:1px solid var(--border-subtle); line-height:1.6; max-width:85%; }
        .message.user .message-content { background:var(--user-bg,var(--accent)); border:none; color:var(--text-inverted); margin-left:auto; }
        .input-area { background:var(--panel-bg); border-top:1px solid var(--border-subtle); padding:12px 16px; }
        #messageInput { width:100%; background:var(--bg-surface); color:var(--text); border:1px solid var(--border); border-radius:var(--radius-md); padding:12px 16px; font-size:14px; resize:none; }
        #messageInput::placeholder { color:var(--text-secondary); }
        .send-btn { background:var(--accent); color:var(--text-inverted); border:none; border-radius:var(--radius-md); padding:12px 20px; font-weight:600; cursor:pointer; transition:all var(--transition-fast); }
        .send-btn:hover { background:var(--hover); }
        .tool-card,.tool-container,.toolchain-box,.memoryQuery,.focusContent,.memory-content { background:var(--panel-bg); border:1px solid var(--border); border-radius:var(--radius-md); padding:16px; transition:border-color var(--transition-fast),box-shadow var(--transition-fast); }
        .memoryQuery,.toolchain-box { border-left:4px solid var(--accent); }
        .tool-subcard { background:var(--bg); border:1px solid var(--border-subtle); border-radius:var(--radius-md); padding:12px; }
        .tool-type-filter { background:var(--bg-surface); color:var(--text); border:1px solid var(--border); border-radius:var(--radius-sm); }
        .search-result-item { background:var(--bg-surface); border:1px solid var(--border-subtle); border-radius:var(--radius-md); padding:12px; transition:border-color var(--transition-fast); }
        .graph-stats,.memory-search-container { background:var(--bg); color:var(--text); }
        .advanced-filters-content { background:var(--panel-bg); border:1px solid var(--border-subtle); border-radius:var(--radius-md); padding:16px; }
        .action-btn { color:var(--text); background:var(--bg-surface); border:1px solid var(--border); padding:8px 14px; border-radius:var(--radius-sm); transition:all var(--transition-fast); }
        .action-btn:hover { background:var(--hover); color:var(--text-inverted); }
        #graph { background:var(--bg); }
      `;
    }

    _applyToGraph(theme) {
      if (!window.network?.body?.data) return;
      const g = theme.graph;
      window.network.setOptions({
        nodes: {
          shape: g.nodeShape || 'dot', size: 25, borderWidth: 2, borderWidthSelected: 3,
          color: { border:g.nodeBorder, background:g.nodeBackground,
                   highlight:{border:g.nodeHighlight,background:g.nodeBackground},
                   hover:{border:g.nodeHighlight,background:g.nodeBackground} },
          font: { color:g.nodeFont, size:g.nodeFontSize, face:g.fontFamily }
        },
        edges: {
          width: g.edgeWidth || 2,
          color: { color:g.edgeColor, highlight:g.edgeHighlight, hover:g.edgeHighlight },
          font: { color:g.nodeFont, size:g.nodeFontSize - 2, face:g.fontFamily, strokeWidth:0 },
          smooth: { enabled:true, type:'dynamic' }
        }
      });
      window.network.body.container.style.background = g.background;
      this._batchUpdateGraphElements(theme);
    }

    _batchUpdateGraphElements(theme) {
      const g = theme.graph;
      try {
        const { nodes, edges } = window.network.body.data;
        nodes.update(nodes.get().map(n => ({
          id: n.id,
          color: { border:g.nodeBorder, background:g.nodeBackground,
                   highlight:{border:g.nodeHighlight,background:g.nodeBackground},
                   hover:{border:g.nodeHighlight,background:g.nodeBackground} },
          font: { color:g.nodeFont, size:g.nodeFontSize, face:g.fontFamily }
        })));
        edges.update(edges.get().map(e => ({
          id: e.id,
          color: { color:g.edgeColor, highlight:g.edgeHighlight, hover:g.edgeHighlight },
          font: { color:g.nodeFont, size:g.nodeFontSize - 2, face:g.fontFamily }
        })));
        console.log(`Updated ${nodes.get().length} nodes, ${edges.get().length} edges`);
      } catch(err) { console.warn('Error updating graph elements:', err); }
      window.network.redraw();
    }

    _watchForNetwork() {
      if (window.network?.body?.data) {
        this._applyToGraph(themes[this.currentTheme]);
        this._hookNetworkSetData();
        return;
      }
      let attempts = 0;
      const interval = setInterval(() => {
        attempts++;
        if (window.network?.body?.data) {
          clearInterval(interval);
          console.log(`Network ready after ${attempts} attempts`);
          this._applyToGraph(themes[this.currentTheme]);
          this._hookNetworkSetData();
        } else if (attempts >= 40) {
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
        setTimeout(() => this._applyToGraph(themes[this.currentTheme]), 100);
      };
    }

    // ── Public API ────────────────────────────────────────────────
    onChange(callback)      { this.listeners.add(callback); return () => this.listeners.delete(callback); }
    getThemes()             { return Object.entries(themes).map(([id, t]) => ({ id, name: t.name })); }
    getCurrentTheme()       { return this.currentTheme; }
    getThemeConfig(name)    { return themes[name]; }

    applyCustomGraphColors(colors) {
      if (!window.network) { console.warn('Graph network not ready'); return; }
      this._applyToGraph({
        graph: {
          nodeBorder:      colors.nodeBorder,
          nodeBackground:  colors.nodeBackground,
          nodeHighlight:   colors.nodeHighlight,
          nodeFont:        colors.nodeFont || colors.nodeBorder,
          nodeFontSize:    colors.fontSize || 14,
          edgeColor:       colors.edgeColor,
          edgeHighlight:   colors.edgeColor,
          background:      colors.background,
          fontFamily:      themes[this.currentTheme]?.graph?.fontFamily || 'sans-serif'
        }
      });
    }
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // Singleton + UI — unchanged from v2.0 except UI also re-syncs pf inputs
  // ─────────────────────────────────────────────────────────────────────────────
  const themeManager = new ThemeManager();

  VeraChat.prototype.initThemeSettings = function() {
    if (document.querySelector('#themeMenu')) return;
    themeManager.init();
    this._createThemeUI(themeManager);
  };

  VeraChat.prototype._createThemeUI = function(manager) {
    const currentTheme = manager.getCurrentTheme();
    const themeConfig  = manager.getThemeConfig(currentTheme);

    const menu = document.createElement('div');
    menu.id    = 'themeMenu';
    menu.innerHTML = `
      <style>
        #themeMenu { background:rgba(0,0,0,.9); color:#fff; padding:16px; border-radius:10px;
          font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; font-size:13px;
          width:280px; box-shadow:0 8px 32px rgba(0,0,0,.5); backdrop-filter:blur(10px); }
        #themeMenu h4 { margin:0 0 16px; font-size:16px; text-align:center;
          border-bottom:1px solid #333; padding-bottom:12px; }
        #themeMenu label { font-size:11px; opacity:.7; margin-top:10px; display:block;
          text-transform:uppercase; letter-spacing:.5px; }
        #themeMenu select,#themeMenu input,#themeMenu button { width:100%; background:#1a1a1a;
          color:#fff; border:1px solid #333; border-radius:6px; padding:8px 12px; margin-top:6px;
          font-size:13px; box-sizing:border-box; }
        #themeMenu input[type="color"] { height:36px; padding:4px; cursor:pointer; }
        #themeMenu input[type="number"] { width:80px; }
        #themeMenu button { cursor:pointer; transition:background .2s; margin-top:8px; }
        #themeMenu button:hover { background:#333; }
        #themeMenu button.primary { background:#6366f1; border-color:#6366f1; }
        #themeMenu button.primary:hover { background:#4f46e5; }
        #themeMenu .section { margin-top:16px; padding-top:12px; border-top:1px solid #222; }
        #themeMenu .section-title { font-size:11px; opacity:.5; text-transform:uppercase;
          letter-spacing:1px; margin-bottom:8px; }
        #themeMenu .row { display:flex; align-items:center; gap:8px; margin-top:8px; }
        #themeMenu .row label { flex:1; margin:0; }
        #themeMenu .row input[type="color"] { width:60px; margin:0; }
        #themeMenu.floating { position:fixed; z-index:999999; cursor:grab; resize:both; overflow:auto; }
        #themeMenu.floating.dragging { cursor:grabbing; opacity:.9; }
        #themeMenu .btn-row { display:flex; gap:8px; margin-top:12px; }
        #themeMenu .btn-row button { flex:1; margin:0; }
      </style>
      <h4>Theme Settings</h4>
      <label>Theme Preset</label>
      <select id="themeSelect">
        ${manager.getThemes().map(t =>
          `<option value="${t.id}" ${t.id === currentTheme ? 'selected' : ''}>${t.name}</option>`
        ).join('')}
      </select>
      <div class="section">
        <div class="section-title">Graph Customization</div>
        <div class="row"><label>Node Border</label>
          <input type="color" id="nodeBorderColor" value="${themeConfig?.graph?.nodeBorder || '#6366f1'}"></div>
        <div class="row"><label>Node Background</label>
          <input type="color" id="nodeBgColor" value="${themeConfig?.graph?.nodeBackground || '#27272a'}"></div>
        <div class="row"><label>Node Highlight</label>
          <input type="color" id="nodeHighlightColor" value="${themeConfig?.graph?.nodeHighlight || '#818cf8'}"></div>
        <div class="row"><label>Edge Color</label>
          <input type="color" id="edgeColor" value="${themeConfig?.graph?.edgeColor || '#52525b'}"></div>
        <div class="row"><label>Background</label>
          <input type="color" id="graphBgColor" value="${themeConfig?.graph?.background || '#18181b'}"></div>
        <label>Font Size</label>
        <input type="number" id="nodeFontSize" min="8" max="24" value="${themeConfig?.graph?.nodeFontSize || 14}">
      </div>
      <div class="btn-row">
        <button id="resetThemeBtn">🔄 Reset</button>
        <button id="applyThemeBtn" class="primary">✓ Apply</button>
      </div>
      <button id="popThemeBtn" style="margin-top:8px;">↗ Pop Out</button>
    `;

    const settingsContainer = document.getElementById('theme-settings') || document.body;
    settingsContainer.appendChild(menu);

    const selector          = menu.querySelector('#themeSelect');
    const nodeBorderInput   = menu.querySelector('#nodeBorderColor');
    const nodeBgInput       = menu.querySelector('#nodeBgColor');
    const nodeHighlightInput= menu.querySelector('#nodeHighlightColor');
    const edgeInput         = menu.querySelector('#edgeColor');
    const graphBgInput      = menu.querySelector('#graphBgColor');
    const fontSizeInput     = menu.querySelector('#nodeFontSize');
    const resetBtn          = menu.querySelector('#resetThemeBtn');
    const applyBtn          = menu.querySelector('#applyThemeBtn');
    const popBtn            = menu.querySelector('#popThemeBtn');

    const updateInputsFromTheme = (themeName) => {
      const config = manager.getThemeConfig(themeName);
      if (!config?.graph) return;
      nodeBorderInput.value    = config.graph.nodeBorder;
      nodeBgInput.value        = config.graph.nodeBackground;
      nodeHighlightInput.value = config.graph.nodeHighlight;
      edgeInput.value          = config.graph.edgeColor;
      graphBgInput.value       = config.graph.background;
      fontSizeInput.value      = config.graph.nodeFontSize;
    };

    selector.addEventListener('change', (e) => {
      manager.apply(e.target.value);
      updateInputsFromTheme(e.target.value);
    });

    applyBtn.addEventListener('click', () => {
      manager.applyCustomGraphColors({
        nodeBorder:     nodeBorderInput.value,
        nodeBackground: nodeBgInput.value,
        nodeHighlight:  nodeHighlightInput.value,
        edgeColor:      edgeInput.value,
        background:     graphBgInput.value,
        fontSize:       parseInt(fontSizeInput.value)
      });
    });

    resetBtn.addEventListener('click', () => {
      manager.apply(selector.value);
      updateInputsFromTheme(selector.value);
    });

    // Floating/docking
    let isDragging = false, offsetX = 0, offsetY = 0;
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
      menu.style.right = '20px'; menu.style.bottom = '20px';
      menu.style.left = 'auto'; menu.style.top = 'auto';
      popBtn.textContent = '↙ Dock';
    };
    const makeDocked = () => {
      settingsContainer.appendChild(menu);
      menu.classList.remove('floating');
      menu.style.cssText = '';
      popBtn.textContent = '↗ Pop Out';
    };

    popBtn.addEventListener('click', () => menu.classList.contains('floating') ? makeDocked() : makeFloating());

    menu.addEventListener('mousedown', (e) => {
      if (!menu.classList.contains('floating')) return;
      if (['INPUT','SELECT','BUTTON'].includes(e.target.tagName)) return;
      isDragging = true;
      offsetX = e.clientX - menu.getBoundingClientRect().left;
      offsetY = e.clientY - menu.getBoundingClientRect().top;
      menu.classList.add('dragging'); e.preventDefault();
    });
    document.addEventListener('mousemove', (e) => {
      if (!isDragging) return;
      menu.style.left = `${e.clientX - offsetX}px`; menu.style.top = `${e.clientY - offsetY}px`;
      menu.style.right = 'auto'; menu.style.bottom = 'auto';
    });
    document.addEventListener('mouseup', () => { isDragging = false; menu.classList.remove('dragging'); });

    manager.onChange((themeName) => {
      selector.value = themeName;
      updateInputsFromTheme(themeName);
    });
  };

  window.themeManager = themeManager;
  window.themes       = themes;
})();