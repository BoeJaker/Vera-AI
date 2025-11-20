class VeraRobot {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.state = 'idle';
        this.frame = 0;
        this.mouseX = 50;
        this.mouseY = 50;
        this.smoothMouseX = 50;
        this.smoothMouseY = 50;
        this.startTime = performance.now();

        // State definitions using theme-aware colors
        // Will be populated with actual theme colors
        this.states = {
            idle: { colorVar: '--accent', eyes: '■ ■', mouth: '▬▬▬', bounce: false, glow: false },
            thinking: { colorVar: '--accent-muted', eyes: '◆ ◆', mouth: '≋≋≋', bounce: true, glow: true },
            happy: { colorVar: '--success', eyes: '◠ ◠', mouth: '⌣⌣⌣', bounce: true, glow: true },
            working: { colorVar: '--warning', eyes: '▣ ▣', mouth: '━━━', bounce: false, glow: true },
            error: { colorVar: '--danger', eyes: '✕ ✕', mouth: '△△△', bounce: false, glow: true },
            sleeping: { colorVar: '--text-muted', eyes: '▬ ▬', mouth: '___', bounce: false, glow: false }
        };

        // Cache for theme colors
        this.themeColors = this.getThemeColors();

        // Listen for theme changes
        this.observeThemeChanges();

        this.bindMouseTracking();
        this.animate();
    }

    getThemeColors() {
        const root = document.documentElement;
        const styles = getComputedStyle(root);
        
        return {
            bg: styles.getPropertyValue('--bg').trim() || '#0f172a',
            panelBg: styles.getPropertyValue('--panel-bg').trim() || '#1e293b',
            text: styles.getPropertyValue('--text').trim() || '#e2e8f0',
            accent: styles.getPropertyValue('--accent').trim() || '#3b82f6',
            accentMuted: styles.getPropertyValue('--accent-muted').trim() || '#3b82f6cc',
            border: styles.getPropertyValue('--border').trim() || '#334155',
            hover: styles.getPropertyValue('--hover').trim() || '#475569',
            textMuted: styles.getPropertyValue('--text-muted').trim() || '#94a3b8',
            success: styles.getPropertyValue('--success').trim() || '#10b981',
            danger: styles.getPropertyValue('--danger').trim() || '#ef4444',
            warning: styles.getPropertyValue('--warning').trim() || '#f59e0b'
        };
    }

    getColorForState(state) {
        const colorVar = this.states[state]?.colorVar;
        if (!colorVar) return this.themeColors.accent;

        // Map CSS variable names to cached colors
        const varMap = {
            '--accent': this.themeColors.accent,
            '--accent-muted': this.themeColors.accentMuted,
            '--success': this.themeColors.success,
            '--danger': this.themeColors.danger,
            '--warning': this.themeColors.warning,
            '--text-muted': this.themeColors.textMuted
        };

        return varMap[colorVar] || this.themeColors.accent;
    }

    observeThemeChanges() {
        // Watch for changes to the style element that theme.js modifies
        const observer = new MutationObserver(() => {
            this.themeColors = this.getThemeColors();
        });

        // Observe the style tag with theme styles
        const themeStyle = document.querySelector('style[data-theme-style]');
        if (themeStyle) {
            observer.observe(themeStyle, { childList: true, characterData: true, subtree: true });
        }

        // Also observe document.documentElement for CSS variable changes
        const rootObserver = new MutationObserver(() => {
            this.themeColors = this.getThemeColors();
        });
        rootObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['style'] });

        // Fallback: poll for theme changes every second
        setInterval(() => {
            this.themeColors = this.getThemeColors();
        }, 1000);
    }

    bindMouseTracking() {
        document.addEventListener("mousemove", (e) => {
            const rect = this.container.getBoundingClientRect();
            this.mouseX = ((e.clientX - rect.left) / rect.width) * 100;
            this.mouseY = ((e.clientY - rect.top) / rect.height) * 100;
        });
    }

    setState(newState) {
        if (this.states[newState]) {
            this.state = newState;
        }
    }

    lerp(a, b, t) {
        return a + (b - a) * t;
    }

    animate() {
        const now = performance.now();
        const deltaTime = (now - this.startTime) / 1000;
        this.startTime = now;

        // Smooth mouse movement
        this.smoothMouseX = this.lerp(this.smoothMouseX, this.mouseX, 0.12);
        this.smoothMouseY = this.lerp(this.smoothMouseY, this.mouseY, 0.12);

        // Floatier frame increment
        this.frame += deltaTime * 1.5;

        this.render();
        requestAnimationFrame(() => this.animate());
    }

    render() {
        const current = this.states[this.state];
        const currentColor = this.getColorForState(this.state);

        // Smooth bounce using ease in-out sine
        const bounce = current.bounce ? Math.sin(this.frame * 2) * 3 : 0;

        // Smooth arm swing
        const armAngle = Math.sin(this.frame * 2) * 10;

        // Smooth eye tracking (limited movement)
        const eyeOffsetX = ((this.smoothMouseX - 40) / 40) * 0.03; // max ±2px
        const eyeOffsetY = ((this.smoothMouseY - 40) / 40) * 0.03; // max ±2px

        // Use theme colors for background elements
        const shadowColor = this.themeColors.bg;
        const strokeColor = this.themeColors.border;
        const antennaColor = this.themeColors.hover;
        const glowColor = current.glow ? this.themeColors.warning : this.themeColors.textMuted;
        const eyeSocketColor = this.themeColors.bg;
        const eyeColor = this.themeColors.warning;

        this.container.innerHTML = `
        <svg width="80" height="80" viewBox="0 0 100 100" style="display:block;">
            <defs>
                <filter id="bodyGlow">
                    <feGaussianBlur stdDeviation="2" result="coloredBlur"/>
                    <feMerge>
                        <feMergeNode in="coloredBlur"/>
                        <feMergeNode in="SourceGraphic"/>
                    </feMerge>
                </filter>
                <filter id="eyeGlow" x="-50%" y="-50%" width="200%" height="200%">
                    <feGaussianBlur in="SourceGraphic" stdDeviation="3" result="blur"/>
                    <feColorMatrix in="blur" type="matrix"
                        values="1 0 0 0 0
                                1 1 0 0 0
                                0 0 1 0 0
                                0 0 0 1 0" result="glowColor"/>
                    <feMerge>
                        <feMergeNode in="glowColor"/>
                        <feMergeNode in="SourceGraphic"/>
                    </feMerge>
                </filter>
            </defs>

            <!-- Shadow -->
            <ellipse cx="50" cy="92" rx="20" ry="6" fill="rgba(0,0,0,0.3)" />

            <g transform="translate(0, ${bounce.toFixed(2)})">
                <!-- Body -->
                <rect x="25" y="45" width="50" height="40" rx="8"
                    fill="${currentColor}" stroke="${strokeColor}" stroke-width="2"/>
                
                <!-- Head -->
                <rect x="30" y="15" width="40" height="35" rx="6"
                    fill="${currentColor}" stroke="${strokeColor}" stroke-width="2"/>
                
                <!-- Antenna -->
                <line x1="50" y1="8" x2="50" y2="15" stroke="${antennaColor}" stroke-width="2"/>
                <circle cx="50" cy="6" r="3"
                    fill="${glowColor}"
                    ${current.glow ? 'filter="url(#bodyGlow)"' : ''}/>

                <!-- Eye Sockets -->
                <rect x="33" y="22" width="12" height="12" rx="2" fill="${eyeSocketColor}"/>
                <rect x="55" y="22" width="12" height="12" rx="2" fill="${eyeSocketColor}"/>

                <!-- Eyes -->
                <text x="${39 + eyeOffsetX}" y="${30 + eyeOffsetY}"
                    font-size="10" text-anchor="middle"
                    fill="${eyeColor}" font-family="monospace" font-weight="bold"
                    filter="url(#eyeGlow)">
                    ${current.eyes.split(' ')[0]}
                </text>
                <text x="${61 + eyeOffsetX}" y="${30 + eyeOffsetY}"
                    font-size="10" text-anchor="middle"
                    fill="${eyeColor}" font-family="monospace" font-weight="bold"
                    filter="url(#eyeGlow)">
                    ${current.eyes.split(' ')[1]}
                </text>

                <!-- Mouth -->
                <rect x="35" y="38" width="30" height="8" rx="2" fill="${eyeSocketColor}"/>
                <text x="50" y="44" font-size="8" text-anchor="middle"
                    fill="${currentColor}" font-family="monospace" font-weight="bold">
                    ${current.mouth}
                </text>

                <!-- Arms -->
                <g>
                    <rect x="18" y="52" width="8" height="20" rx="3"
                        fill="${currentColor}"
                        transform="rotate(${armAngle.toFixed(2)} 22 52)"/>
                    <rect x="74" y="52" width="8" height="20" rx="3"
                        fill="${currentColor}"
                        transform="rotate(${-armAngle.toFixed(2)} 78 52)"/>
                </g>

                <!-- Legs -->
                <rect x="32" y="82" width="12" height="8" rx="4"
                    fill="${currentColor}" stroke="${strokeColor}" stroke-width="1"/>
                <rect x="56" y="82" width="12" height="8" rx="4"
                    fill="${currentColor}" stroke="${strokeColor}" stroke-width="1"/>
            </g>
        </svg>`;
    }
}

window.VeraRobot = VeraRobot;