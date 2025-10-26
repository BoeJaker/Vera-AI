class VeraRobot {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.state = 'idle';
        this.frame = 0;
        this.mouseX = 50;
        this.mouseY = 50;

        this.states = {
            idle: { color: '#60a5fa', eyes: '■ ■', mouth: '▬▬▬', bounce: false, glow: false },
            thinking: { color: '#8b5cf6', eyes: '◆ ◆', mouth: '≋≋≋', bounce: true, glow: true },
            happy: { color: '#10b981', eyes: '◠ ◠', mouth: '⌣⌣⌣', bounce: true, glow: true },
            working: { color: '#f59e0b', eyes: '▣ ▣', mouth: '━━━', bounce: false, glow: true },
            error: { color: '#ef4444', eyes: '✕ ✕', mouth: '△△△', bounce: false, glow: true },
            sleeping: { color: '#64748b', eyes: '▬ ▬', mouth: '___', bounce: false, glow: false }
        };

        this.init();
        this.bindMouseTracking();
    }

    bindMouseTracking() {
        document.addEventListener("mousemove", (e) => {
            const rect = this.container.getBoundingClientRect();
            this.mouseX = ((e.clientX - rect.left) / rect.width) * 100;
            this.mouseY = ((e.clientY - rect.top) / rect.height) * 100;
            this.render();
        });
    }

    init() {
        if (!this.container) {
            console.error("Vera Robot container not found");
            return;
        }

        this.render();
        setInterval(() => {
            this.frame = (this.frame + 1) % 4;
            this.render();
        }, 400);
    }

    setState(newState) {
        if (this.states[newState]) {
            this.state = newState;
            this.render();
        }
    }

    render() {
        const current = this.states[this.state];
        const y = current.bounce ? Math.sin(this.frame * Math.PI / 2) * 4 : 0;
        const gearRotation = this.frame * 90;

        // Make the eyes move *slightly* toward the mouse (small offset)
        const eyeOffsetX = ((this.mouseX - 50) / 50) * 0.05; // reduced range
        const eyeOffsetY = ((this.mouseY - 50) / 50) * 0.05;

        this.container.innerHTML = `
        <svg width="80" height="80" viewBox="0 0 100 100" style="display:block;">
            <defs>
                <!-- Body glow -->
                <filter id="bodyGlow">
                    <feGaussianBlur stdDeviation="2" result="coloredBlur"/>
                    <feMerge>
                        <feMergeNode in="coloredBlur"/>
                        <feMergeNode in="SourceGraphic"/>
                    </feMerge>
                </filter>

                <!-- Eye glow (stronger, color-tinted blur) -->
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

            <g transform="translate(0, ${y})">
                <!-- Body -->
                <rect x="25" y="45" width="50" height="40" rx="8"
                    fill="${current.color}" stroke="#1e293b" stroke-width="2"/>

                <!-- Head -->
                <rect x="30" y="15" width="40" height="35" rx="6"
                    fill="${current.color}" stroke="#1e293b" stroke-width="2"/>

                <!-- Antenna -->
                <line x1="50" y1="8" x2="50" y2="15" stroke="#334155" stroke-width="2"/>
                <circle cx="50" cy="6" r="3"
                    fill="${current.glow ? '#fbbf24' : '#64748b'}"
                    ${current.glow ? 'filter="url(#bodyGlow)"' : ''}/>

                <!-- Eye sockets -->
                <rect x="33" y="22" width="12" height="12" rx="2" fill="#0a0a0a"/>
                <rect x="55" y="22" width="12" height="12" rx="2" fill="#0a0a0a"/>

                <!-- Eyes (with glow and tracking) -->
                <text x="${39 + eyeOffsetX}" y="${30 + eyeOffsetY}"
                    font-size="10" text-anchor="middle"
                    fill="#fef08a"
                    font-family="monospace" font-weight="bold"
                    filter="url(#eyeGlow)">
                    ${current.eyes.split(' ')[0]}
                </text>
                <text x="${61 + eyeOffsetX}" y="${30 + eyeOffsetY}"
                    font-size="10" text-anchor="middle"
                    fill="#fef08a"
                    font-family="monospace" font-weight="bold"
                    filter="url(#eyeGlow)">
                    ${current.eyes.split(' ')[1]}
                </text>

                <!-- Mouth -->
                <rect x="35" y="38" width="30" height="8" rx="2" fill="#0a0a0a"/>
                <text x="50" y="44" font-size="8" text-anchor="middle"
                    fill="${current.color}" font-family="monospace" font-weight="bold">
                    ${current.mouth}
                </text>

                <!-- Arms and joints -->
                <circle cx="28" cy="48" r="2" fill="#334155"/>
                <circle cx="72" cy="48" r="2" fill="#334155"/>

                <g>
                    <rect x="18" y="52" width="8" height="20" rx="3"
                        fill="${current.color}"
                        transform="rotate(${Math.sin(this.frame * Math.PI / 2) * 15} 22 52)"/>
                    <circle cx="22" cy="52" r="3" fill="#334155"/>
                    <circle cx="22" cy="70" r="3" fill="#334155"/>

                    <rect x="74" y="52" width="8" height="20" rx="3"
                        fill="${current.color}"
                        transform="rotate(${-Math.sin(this.frame * Math.PI / 2) * 15} 78 52)"/>
                    <circle cx="78" cy="52" r="3" fill="#334155"/>
                    <circle cx="78" cy="70" r="3" fill="#334155"/>
                </g>

                <!-- Legs -->
                <rect x="32" y="82" width="12" height="8" rx="4"
                    fill="${current.color}" stroke="#1e293b" stroke-width="1"/>
                <rect x="56" y="82" width="12" height="8" rx="4"
                    fill="${current.color}" stroke="#1e293b" stroke-width="1"/>
            </g>
        </svg>`;
    }
}

window.VeraRobot = VeraRobot;
