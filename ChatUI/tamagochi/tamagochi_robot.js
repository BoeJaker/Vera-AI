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

        this.states = {
            idle: { color: '#60a5fa', eyes: '■ ■', mouth: '▬▬▬', bounce: false, glow: false },
            thinking: { color: '#8b5cf6', eyes: '◆ ◆', mouth: '≋≋≋', bounce: true, glow: true },
            happy: { color: '#10b981', eyes: '◠ ◠', mouth: '⌣⌣⌣', bounce: true, glow: true },
            working: { color: '#f59e0b', eyes: '▣ ▣', mouth: '━━━', bounce: false, glow: true },
            error: { color: '#ef4444', eyes: '✕ ✕', mouth: '△△△', bounce: false, glow: true },
            sleeping: { color: '#64748b', eyes: '▬ ▬', mouth: '___', bounce: false, glow: false }
        };

        this.bindMouseTracking();
        this.animate();
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

        // Smooth bounce using ease in-out sine
        const bounce = current.bounce ? Math.sin(this.frame * 2) * 3 : 0;

        // Smooth arm swing
        const armAngle = Math.sin(this.frame * 2) * 10;

        // Smooth eye tracking (limited movement)
        const eyeOffsetX = ((this.smoothMouseX - 40) / 40) * 0.03; // max ±2px
        const eyeOffsetY = ((this.smoothMouseY - 40) / 40) * 0.03; // max ±2px


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

            <ellipse cx="50" cy="92" rx="20" ry="6" fill="rgba(0,0,0,0.3)" />

            <g transform="translate(0, ${bounce.toFixed(2)})">
                <rect x="25" y="45" width="50" height="40" rx="8"
                    fill="${current.color}" stroke="#1e293b" stroke-width="2"/>
                <rect x="30" y="15" width="40" height="35" rx="6"
                    fill="${current.color}" stroke="#1e293b" stroke-width="2"/>
                <line x1="50" y1="8" x2="50" y2="15" stroke="#334155" stroke-width="2"/>
                <circle cx="50" cy="6" r="3"
                    fill="${current.glow ? '#fbbf24' : '#64748b'}"
                    ${current.glow ? 'filter="url(#bodyGlow)"' : ''}/>

                <rect x="33" y="22" width="12" height="12" rx="2" fill="#0a0a0a"/>
                <rect x="55" y="22" width="12" height="12" rx="2" fill="#0a0a0a"/>

                <text x="${39 + eyeOffsetX}" y="${30 + eyeOffsetY}"
                    font-size="10" text-anchor="middle"
                    fill="#fef08a" font-family="monospace" font-weight="bold"
                    filter="url(#eyeGlow)">
                    ${current.eyes.split(' ')[0]}
                </text>
                <text x="${61 + eyeOffsetX}" y="${30 + eyeOffsetY}"
                    font-size="10" text-anchor="middle"
                    fill="#fef08a" font-family="monospace" font-weight="bold"
                    filter="url(#eyeGlow)">
                    ${current.eyes.split(' ')[1]}
                </text>

                <rect x="35" y="38" width="30" height="8" rx="2" fill="#0a0a0a"/>
                <text x="50" y="44" font-size="8" text-anchor="middle"
                    fill="${current.color}" font-family="monospace" font-weight="bold">
                    ${current.mouth}
                </text>

                <g>
                    <rect x="18" y="52" width="8" height="20" rx="3"
                        fill="${current.color}"
                        transform="rotate(${armAngle.toFixed(2)} 22 52)"/>
                    <rect x="74" y="52" width="8" height="20" rx="3"
                        fill="${current.color}"
                        transform="rotate(${-armAngle.toFixed(2)} 78 52)"/>
                </g>

                <rect x="32" y="82" width="12" height="8" rx="4"
                    fill="${current.color}" stroke="#1e293b" stroke-width="1"/>
                <rect x="56" y="82" width="12" height="8" rx="4"
                    fill="${current.color}" stroke="#1e293b" stroke-width="1"/>
            </g>
        </svg>`;
    }
}

window.VeraRobot = VeraRobot;
