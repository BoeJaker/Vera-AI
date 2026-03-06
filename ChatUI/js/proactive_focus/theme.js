/**
 * FocusLayoutV2 — Theme Integration Patch v2
 *
 * WHY THE PREVIOUS VERSION FAILED
 * ────────────────────────────────
 * The previous patch wrote --fb-* vars to :root via a <style> block.
 * This should work in theory, BUT:
 *
 *  1. "The included file" — if the parent app (Chat.js, main bundle, etc.)
 *     defines ANY --fb-* vars on :root or body, they can override ours
 *     because they may sit later in <head> or have equal/higher specificity.
 *
 *  2. updateFocusUI() replaces container.innerHTML wholesale on every
 *     WebSocket tick, focus change, or tab switch. Any styles applied to
 *     child elements (not the container itself) get wiped and repainted
 *     with the fallback colours embedded in the HTML strings.
 *
 * THE FIX
 * ────────
 * Two-pronged approach that is immune to both problems:
 *
 *  A) Write vars as an inline `style` attribute directly on the #tab-focus
 *     container element. Inline styles on an ANCESTOR beat any stylesheet
 *     rule, because CSS custom properties are inherited — children pick up
 *     the vars from the nearest ancestor that defines them, and an inline
 *     style has the highest possible specificity.
 *
 *  B) Monkey-patch VeraChat.prototype.updateFocusUI so that after every
 *     re-render we immediately re-stamp the inline vars onto the container.
 *     This makes theming survive every innerHTML replacement.
 *
 * USAGE
 * ─────
 *   <script src="FocusLayoutV2.js"></script>     ← defines VeraChat.prototype.*
 *   <script src="theme-system.js"></script>
 *   <script src="FocusLayoutV2.theme-patch.js">  ← this file, load last
 *   </script>
 *
 * Auto-registers if window.themeManager exists at load time.
 * Or call manually: registerFocusBoardTheme(window.themeManager)
 */

;(function () {

    // Holds the current resolved theme vars so updateFocusUI hook can re-apply
    let _currentVars = {};
    let _registered  = false;

    // ── camelToKebab  e.g. "bgSurfaceAlt" → "bg-surface-alt" ─────────────────
    function camelToKebab(str) {
        return str.replace(/([A-Z])/g, m => '-' + m.toLowerCase());
    }

    // ── Build a flat { '--fb-foo': 'value', ... } map from theme ─────────────
    function _buildVarMap(themeConfig) {
        const fb = themeConfig && themeConfig.focusBoard;
        if (!fb) return {};
        const map = {};
        for (const [key, value] of Object.entries(fb)) {
            map[`--fb-${camelToKebab(key)}`] = value;
        }
        return map;
    }

    // ── Stamp vars as inline style on #tab-focus ──────────────────────────────
    // Inline style on a parent element = highest possible inheritance source.
    // Children using var(--fb-x, fallback) will inherit from this ancestor,
    // beating any stylesheet (including anything the host app defines on :root).
    function _stampVarsOnContainer() {
        const container = document.getElementById('tab-focus');
        if (!container || Object.keys(_currentVars).length === 0) return;

        // Build the inline style string, preserving any existing non-fb styles
        const existingStyle = container.getAttribute('style') || '';
        // Strip previous --fb-* declarations we set
        const stripped = existingStyle.replace(/--fb-[^:]+:[^;]+;?\s*/g, '');
        const fbPart   = Object.entries(_currentVars)
            .map(([k, v]) => `${k}: ${v}`)
            .join('; ');
        container.setAttribute('style', `${stripped}${fbPart}`);
    }

    // ── Apply theme: store vars + stamp them ──────────────────────────────────
    function _applyFbTheme(themeConfig) {
        _currentVars = _buildVarMap(themeConfig);
        _stampVarsOnContainer();

        // Also write a :root block as a belt-and-braces fallback for modals
        // (focusBoardModal / setFocusModal are appended to <body>, not inside
        //  #tab-focus, so they need the vars available from :root)
        let el = document.getElementById('fb-theme-vars');
        if (!el) {
            el = document.createElement('style');
            el.id = 'fb-theme-vars';
            document.head.appendChild(el);
        }
        const declarations = Object.entries(_currentVars)
            .map(([k, v]) => `  ${k}: ${v} !important`)
            .join(';\n');
        el.textContent = `:root {\n${declarations};\n}`;
    }

    // ── Monkey-patch updateFocusUI ────────────────────────────────────────────
    // updateFocusUI() sets container.innerHTML which blows away any inline
    // style on child elements. But the container (#tab-focus) itself is NOT
    // replaced — its innerHTML is replaced. So our inline style on the
    // container element survives the replacement and only needs re-stamping
    // if for some reason the element itself was recreated.
    //
    // However: the inner wrapper div that updateFocusUI writes has
    //   style="padding:20px; overflow-y:auto; height:100%"
    // which could shadow vars if it's the element vars are read from.
    // Stamping on the outer #tab-focus container means vars cascade down
    // through that wrapper automatically.
    //
    // We patch it to re-stamp after every call just to be safe.
    function _patchUpdateFocusUI() {
        if (!window.VeraChat || !VeraChat.prototype.updateFocusUI) return;
        if (VeraChat.prototype.__fbThemePatchApplied) return;

        const _original = VeraChat.prototype.updateFocusUI;
        VeraChat.prototype.updateFocusUI = function (...args) {
            _original.apply(this, args);
            _stampVarsOnContainer();    // re-stamp after innerHTML replacement
        };
        VeraChat.prototype.__fbThemePatchApplied = true;
        console.log('[FocusLayoutV2 theme] updateFocusUI patched');
    }

    // ── Public entry point ────────────────────────────────────────────────────
    function registerFocusBoardTheme(themeManager) {
        if (!themeManager) {
            console.warn('[FocusLayoutV2 theme] no themeManager passed');
            return;
        }
        if (_registered) return;
        _registered = true;

        // Patch updateFocusUI if VeraChat is available now
        _patchUpdateFocusUI();

        // If VeraChat wasn't defined yet, retry once the DOM is ready
        if (!window.VeraChat) {
            document.addEventListener('DOMContentLoaded', _patchUpdateFocusUI);
        }

        // Apply current theme
        const name   = themeManager.getCurrentTheme();
        const config = themeManager.getThemeConfig(name);
        if (config) _applyFbTheme(config);

        // Subscribe to future changes
        themeManager.onChange((n, c) => _applyFbTheme(c));

        console.log('[FocusLayoutV2 theme] registered, current theme:', name);
    }

    // ── Expose ────────────────────────────────────────────────────────────────
    window.registerFocusBoardTheme  = registerFocusBoardTheme;
    window._applyFbTheme            = _applyFbTheme;      // debug
    window._stampFbVarsOnContainer  = _stampVarsOnContainer; // debug

    // Auto-register
    if (window.themeManager) {
        registerFocusBoardTheme(window.themeManager);
    }

})();