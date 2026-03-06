/**
 * ChatbotManager — Theme Integration Patch v3
 *
 * WHY PREVIOUS VERSIONS FAILED
 * ─────────────────────────────
 * ChatbotManager.injectStyles() defines all --cbm-* vars inside .cbm-root {}
 * in a <style id="cbm-styles"> element. It is called lazily at init() time,
 * which is AFTER this patch runs on load. Same selector (.cbm-root) + later
 * position in <head> = cbm-styles always wins the cascade.
 *
 * THE FIX
 * ────────
 * CSS custom properties respect !important. Declaring:
 *   .cbm-root { --cbm-bg: #000 !important; }
 * beats any other .cbm-root { --cbm-bg: ... } regardless of source order.
 * No monkey-patching, no DOM reordering needed — just !important on every var.
 *
 * USAGE
 * ─────
 *   <script src="ChatbotManager.js"></script>
 *   <script src="theme-system.js"></script>
 *   <script src="ChatbotManager.theme-patch.js"></script>
 *
 * Auto-registers if window.themeManager already exists.
 * Or call manually: ChatbotManager.registerWithThemeManager(window.themeManager)
 */

;(function () {

    // ── Per-theme accent colour maps ──────────────────────────────────────────
    // Only accent/semantic values that have no direct base-theme equivalent.
    // Surface vars (bg, surface, border, text) are read from themeConfig.variables.
    const CBM_THEME_MAPS = {
        default:       { blue:'#3b82f6', blueDim:'rgba(59,130,246,.18)',  purple:'#8b5cf6', purpleDim:'rgba(139,92,246,.14)', green:'#10b981', greenDim:'rgba(16,185,129,.18)',  red:'#ef4444', redDim:'rgba(239,68,68,.14)',  orange:'#f59e0b', orangeDim:'rgba(245,158,11,.18)',  font:'"JetBrains Mono","Fira Code","Courier New",monospace',        text:'#e2e8f0' },
        renderRGB:     { blue:'#2d6aff', blueDim:'rgba(45,106,255,.18)',  purple:'#ff2d2d', purpleDim:'rgba(255,45,45,.14)',  green:'#2dff6a', greenDim:'rgba(45,255,106,.14)',  red:'#ff2d2d', redDim:'rgba(255,45,45,.14)', orange:'#f59e0b', orangeDim:'rgba(245,158,11,.18)',  font:'"Source Code Pro","Monaco","Menlo","Courier New",monospace',  text:'#e6eef8' },
        renderCMY:     { blue:'#00cfe8', blueDim:'rgba(0,207,232,.18)',   purple:'#ff46b0', purpleDim:'rgba(255,70,176,.14)', green:'#10b981', greenDim:'rgba(16,185,129,.14)',  red:'#ff46b0', redDim:'rgba(255,70,176,.14)',orange:'#ffd100', orangeDim:'rgba(255,209,0,.18)',   font:'"Source Code Pro","Monaco","Menlo","Courier New",monospace',  text:'#f2f7fb' },
        modernPro:     { blue:'#6366f1', blueDim:'rgba(99,102,241,.18)',  purple:'#8b5cf6', purpleDim:'rgba(139,92,246,.14)', green:'#22c55e', greenDim:'rgba(34,197,94,.15)',   red:'#ef4444', redDim:'rgba(239,68,68,.14)', orange:'#f59e0b', orangeDim:'rgba(245,158,11,.18)',  font:'"Inter","Monaco","Menlo","Courier New",monospace',            text:'#fafafa'  },
        terminal:      { blue:'#00ff66', blueDim:'rgba(0,255,102,.14)',   purple:'#00ffaa', purpleDim:'rgba(0,255,170,.1)',   green:'#00ff66', greenDim:'rgba(0,255,102,.1)',    red:'#ff4444', redDim:'rgba(255,68,68,.14)', orange:'#ffaa00', orangeDim:'rgba(255,170,0,.14)',   font:'"Fira Code","Consolas","Courier New",monospace',              text:'#00ff66' },
        darkNewspaper: { blue:'#c8c6c3', blueDim:'rgba(200,198,195,.12)',purple:'#e8e6e3', purpleDim:'rgba(232,230,227,.1)',  green:'#888683', greenDim:'rgba(136,134,131,.12)',red:'#cc4444',  redDim:'rgba(204,68,68,.12)', orange:'#c8a060', orangeDim:'rgba(200,160,96,.14)',  font:'"Crimson Text",Georgia,serif',                                text:'#e8e6e3' },
        bidwellsDark:  { blue:'#3b82f6', blueDim:'rgba(59,130,246,.15)',  purple:'#3b6fd4', purpleDim:'rgba(59,111,212,.12)',green:'#22c55e',  greenDim:'rgba(34,197,94,.12)',  red:'#ef4444',  redDim:'rgba(239,68,68,.12)', orange:'#fbbf24', orangeDim:'rgba(251,191,36,.15)',  font:'"Inter","Monaco","Menlo","Courier New",monospace',            text:'#dbeafe' },
        pixelArt:      { blue:'#66f0ff', blueDim:'rgba(102,240,255,.14)', purple:'#ff33cc', purpleDim:'rgba(255,51,204,.12)', green:'#33ff99', greenDim:'rgba(51,255,153,.12)', red:'#ff3333', redDim:'rgba(255,51,51,.12)', orange:'#ffaa00', orangeDim:'rgba(255,170,0,.14)',   font:'"Press Start 2P",monospace',                                  text:'#66f0ff' },
        retroGaming:   { blue:'#00ffcc', blueDim:'rgba(0,255,204,.12)',   purple:'#ff0077', purpleDim:'rgba(255,0,119,.1)',   green:'#00ffcc', greenDim:'rgba(0,255,204,.1)',    red:'#ff0077', redDim:'rgba(255,0,119,.12)', orange:'#ffaa00', orangeDim:'rgba(255,170,0,.12)',   font:'"Press Start 2P",monospace',                                  text:'#00ffcc' },
        sunsetGlow:    { blue:'#ffa07a', blueDim:'rgba(255,160,122,.15)', purple:'#ff6f61', purpleDim:'rgba(255,111,97,.12)', green:'#88cc88', greenDim:'rgba(136,204,136,.12)',red:'#ff6655',  redDim:'rgba(255,102,85,.12)',orange:'#ffb347', orangeDim:'rgba(255,179,71,.15)',  font:'"Share Tech Mono","Courier New",monospace',                   text:'#ffd8a8' },
        rainbowNoir:   { blue:'#8be9fd', blueDim:'rgba(139,233,253,.14)', purple:'#bd93f9', purpleDim:'rgba(189,147,249,.12)',green:'#50fa7b', greenDim:'rgba(80,250,123,.12)',  red:'#ff5555', redDim:'rgba(255,85,85,.12)', orange:'#f1fa8c', orangeDim:'rgba(241,250,140,.12)', font:'"Share Tech Mono","Courier New",monospace',                   text:'#f8f8f8' },
    };

    // ── Build CSS with !important on every custom property ────────────────────
    function _buildCss(themeName, themeConfig) {
        const m    = CBM_THEME_MAPS[themeName] || CBM_THEME_MAPS['default'];
        const vars = themeConfig.variables || {};

        // rainbowNoir --text is a gradient — use solid fallback from map
        const rawText = vars['--text'] || '';
        const textVal = rawText.startsWith('linear-gradient') ? m.text : (rawText || m.text);

        // Every declaration gets !important so we beat cbm-styles regardless of load order
        return `.cbm-root {
    --cbm-bg:          ${vars['--bg']            || '#0d0f14'}     !important;
    --cbm-surface:     ${vars['--bg-surface']     || '#141720'}     !important;
    --cbm-surface2:    ${vars['--panel-bg']       || '#1c2030'}     !important;
    --cbm-border:      ${vars['--border']         || '#252a38'}     !important;
    --cbm-text:        ${textVal}                                   !important;
    --cbm-text-muted:  ${vars['--text-secondary'] || '#636e8f'}     !important;
    --cbm-text-dim:    ${vars['--border-subtle']  || '#414d6b'}     !important;
    --cbm-font-ui:     system-ui,"Segoe UI",sans-serif             !important;
    --cbm-blue:        ${m.blue}                                    !important;
    --cbm-blue-dim:    ${m.blueDim}                                 !important;
    --cbm-purple:      ${m.purple}                                  !important;
    --cbm-purple-dim:  ${m.purpleDim}                               !important;
    --cbm-green:       ${m.green}                                   !important;
    --cbm-green-dim:   ${m.greenDim}                                !important;
    --cbm-red:         ${m.red}                                     !important;
    --cbm-red-dim:     ${m.redDim}                                  !important;
    --cbm-orange:      ${m.orange}                                  !important;
    --cbm-orange-dim:  ${m.orangeDim}                               !important;
    --cbm-font:        ${m.font}                                    !important;
}`;
    }

    // ── Write / update the theme style block ──────────────────────────────────
    function _applyCbmTheme(themeName, themeConfig) {
        let el = document.getElementById('cbm-theme-vars');
        if (!el) {
            el = document.createElement('style');
            el.id = 'cbm-theme-vars';
            document.head.appendChild(el);
        }
        el.textContent = _buildCss(themeName, themeConfig);
    }

    // ── Public registration ───────────────────────────────────────────────────
    ChatbotManager.registerWithThemeManager = function (themeManager) {
        if (!themeManager) {
            console.warn('[ChatbotManager theme] no themeManager passed');
            return;
        }
        const name   = themeManager.getCurrentTheme();
        const config = themeManager.getThemeConfig(name);
        if (config) _applyCbmTheme(name, config);

        themeManager.onChange((n, c) => _applyCbmTheme(n, c));
        console.log('[ChatbotManager theme] registered, current:', name);
    };

    // Debug helpers
    ChatbotManager.CBM_THEME_MAPS = CBM_THEME_MAPS;
    ChatbotManager._applyCbmTheme = _applyCbmTheme;

    // Auto-register
    if (window.themeManager) {
        ChatbotManager.registerWithThemeManager(window.themeManager);
    }

})();