import React, { useState, useEffect } from 'react';

const VeraTamagotchi = ({ state = 'idle', onClick }) => {
  const [frame, setFrame] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => setFrame(f => (f + 1) % 4), 400);
    return () => clearInterval(interval);
  }, []);

  const states = {
    idle: { color: '#60a5fa', eyes: '■ ■', mouth: '▬▬▬', bounce: false, glow: false },
    thinking: { color: '#8b5cf6', eyes: '◆ ◆', mouth: '≋≋≋', bounce: true, glow: true },
    happy: { color: '#10b981', eyes: '◠ ◠', mouth: '⌣⌣⌣', bounce: true, glow: false },
    working: { color: '#f59e0b', eyes: '▣ ▣', mouth: '━━━', bounce: false, glow: true },
    error: { color: '#ef4444', eyes: '✕ ✕', mouth: '△△△', bounce: false, glow: true },
    sleeping: { color: '#64748b', eyes: '▬ ▬', mouth: '___', bounce: false, glow: false }
  };

  const current = states[state] || states.idle;
  const size = 100;
  const y = current.bounce ? Math.sin(frame * Math.PI / 2) * 4 : 0;
  const gearRotation = frame * 90;

  return (
    <div style={{ 
      width: size, 
      height: size + 20, 
      position: 'relative',
      cursor: 'pointer'
    }} onClick={onClick}>
      <svg width={size} height={size} viewBox="0 0 100 100">
        <defs>
          <filter id="glow">
            <feGaussianBlur stdDeviation="2" result="coloredBlur"/>
            <feMerge>
              <feMergeNode in="coloredBlur"/>
              <feMergeNode in="SourceGraphic"/>
            </feMerge>
          </filter>
        </defs>

        {/* Shadow */}
        <ellipse cx="50" cy="92" rx="20" ry="6" fill="rgba(0,0,0,0.3)" />
        
        <g transform={`translate(0, ${y})`}>
          {/* Robot body - rounded rectangle */}
          <rect x="25" y="45" width="50" height="40" rx="8" fill={current.color} stroke="#1e293b" strokeWidth="2"/>
          
          {/* Chest panel */}
          <rect x="35" y="55" width="30" height="20" rx="3" fill="#1e293b" opacity="0.3"/>
          <circle cx="50" cy="65" r="4" fill={current.glow ? '#fbbf24' : '#334155'} 
            filter={current.glow ? 'url(#glow)' : ''}/>
          
          {/* Robot head - rounded square */}
          <rect x="30" y="15" width="40" height="35" rx="6" fill={current.color} stroke="#1e293b" strokeWidth="2"/>
          
          {/* Antenna with light */}
          <line x1="50" y1="8" x2="50" y2="15" stroke="#334155" strokeWidth="2"/>
          <circle cx="50" cy="6" r="3" fill={current.glow ? '#fbbf24' : '#64748b'}
            filter={current.glow ? 'url(#glow)' : ''}/>
          
          {/* Eyes - screen like */}
          <rect x="33" y="22" width="12" height="12" rx="2" fill="#0a0a0a"/>
          <rect x="55" y="22" width="12" height="12" rx="2" fill="#0a0a0a"/>
          
          {/* Eye displays - larger and brighter */}
          <text x="39" y="30" fontSize="10" textAnchor="middle" fill={current.color} fontFamily="monospace" fontWeight="bold">
            {current.eyes.split(' ')[0]}
          </text>
          <text x="61" y="30" fontSize="10" textAnchor="middle" fill={current.color} fontFamily="monospace" fontWeight="bold">
            {current.eyes.split(' ')[1]}
          </text>
          
          {/* Mouth screen - larger */}
          <rect x="35" y="38" width="30" height="8" rx="2" fill="#0a0a0a"/>
          <text x="50" y="44" fontSize="8" textAnchor="middle" fill={current.color} fontFamily="monospace" fontWeight="bold">
            {current.mouth}
          </text>
          
          {/* Shoulder rivets */}
          <circle cx="28" cy="48" r="2" fill="#334155"/>
          <circle cx="72" cy="48" r="2" fill="#334155"/>
          
          {/* Arms - mechanical */}
          <g>
            {/* Left arm */}
            <rect x="18" y="52" width="8" height="20" rx="3" fill={current.color} 
              transform={`rotate(${Math.sin(frame * Math.PI / 2) * 15} 22 52)`}/>
            <circle cx="22" cy="52" r="3" fill="#334155"/>
            <circle cx="22" cy="70" r="3" fill="#334155"/>
            
            {/* Right arm */}
            <rect x="74" y="52" width="8" height="20" rx="3" fill={current.color} 
              transform={`rotate(${-Math.sin(frame * Math.PI / 2) * 15} 78 52)`}/>
            <circle cx="78" cy="52" r="3" fill="#334155"/>
            <circle cx="78" cy="70" r="3" fill="#334155"/>
          </g>
          
          {/* Legs - treads */}
          <rect x="32" y="82" width="12" height="8" rx="4" fill={current.color} stroke="#1e293b" strokeWidth="1"/>
          <rect x="56" y="82" width="12" height="8" rx="4" fill={current.color} stroke="#1e293b" strokeWidth="1"/>
          
          {/* Tread details */}
          <line x1="34" y1="86" x2="42" y2="86" stroke="#1e293b" strokeWidth="1"/>
          <line x1="58" y1="86" x2="66" y2="86" stroke="#1e293b" strokeWidth="1"/>
          
          {/* Side gears (decorative) */}
          <g transform={`rotate(${gearRotation} 20 65)`}>
            <circle cx="20" cy="65" r="4" fill="#334155" opacity="0.5"/>
            <line x1="20" y1="61" x2="20" y2="69" stroke="#1e293b" strokeWidth="1"/>
            <line x1="16" y1="65" x2="24" y2="65" stroke="#1e293b" strokeWidth="1"/>
          </g>
          <g transform={`rotate(${-gearRotation} 80 65)`}>
            <circle cx="80" cy="65" r="4" fill="#334155" opacity="0.5"/>
            <line x1="80" y1="61" x2="80" y2="69" stroke="#1e293b" strokeWidth="1"/>
            <line x1="76" y1="65" x2="84" y2="65" stroke="#1e293b" strokeWidth="1"/>
          </g>
        </g>
      </svg>
      
      <div style={{
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        textAlign: 'center',
        fontSize: 10,
        color: current.color,
        fontWeight: 600,
        textTransform: 'uppercase',
        fontFamily: 'monospace',
        letterSpacing: 1
      }}>
        {state}
      </div>
    </div>
  );
};

export default function Demo() {
  const [state, setState] = useState('idle');
  const states = ['idle', 'thinking', 'happy', 'working', 'error', 'sleeping'];

  const cycleState = () => {
    const idx = states.indexOf(state);
    setState(states[(idx + 1) % states.length]);
  };

  return (
    <div style={{ 
      padding: 40, 
      background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
      minHeight: '100vh',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: 40
    }}>
      <div style={{ textAlign: 'center' }}>
        <h1 style={{ color: '#e2e8f0', marginBottom: 8 }}>Vera Robot Assistant</h1>
        <p style={{ color: '#94a3b8', fontSize: 14 }}>Click Vera to cycle through states</p>
      </div>

      <VeraTamagotchi state={state} onClick={cycleState} />

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'center' }}>
        {states.map(s => (
          <button
            key={s}
            onClick={() => setState(s)}
            style={{
              padding: '8px 16px',
              background: state === s ? '#3b82f6' : '#1e293b',
              border: '1px solid #334155',
              borderRadius: 6,
              color: '#e2e8f0',
              cursor: 'pointer',
              fontSize: 12,
              textTransform: 'uppercase',
              fontWeight: 600,
              transition: 'all 0.2s'
            }}
            onMouseOver={(e) => {
              if (state !== s) e.target.style.background = '#334155';
            }}
            onMouseOut={(e) => {
              if (state !== s) e.target.style.background = '#1e293b';
            }}
          >
            {s}
          </button>
        ))}
      </div>

      <div style={{ 
        background: '#1e293b', 
        padding: 20, 
        borderRadius: 8,
        border: '1px solid #334155',
        maxWidth: 400
      }}>
        <h3 style={{ color: '#60a5fa', marginBottom: 12, fontSize: 14 }}>Robot Features</h3>
        <ul style={{ 
          color: '#cbd5e1', 
          fontSize: 12, 
          lineHeight: 1.8,
          paddingLeft: 20
        }}>
          <li>Screen-based eyes and mouth</li>
          <li>Mechanical arms with joints</li>
          <li>Glowing chest indicator</li>
          <li>Rotating side gears</li>
          <li>Tank treads for mobility</li>
          <li>Antenna with status light</li>
        </ul>
      </div>
    </div>
  );
}

export default function Demo() {
  const [state, setState] = useState('idle');
  const states = ['idle', 'thinking', 'happy', 'working', 'error', 'sleeping'];

  const cycleState = () => {
    const idx = states.indexOf(state);
    setState(states[(idx + 1) % states.length]);
  };

  return (
    <div style={{ 
      padding: 40, 
      background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
      minHeight: '100vh',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: 40
    }}>
      <div style={{ textAlign: 'center' }}>
        <h1 style={{ color: '#e2e8f0', marginBottom: 8 }}>Vera Tamagotchi</h1>
        <p style={{ color: '#94a3b8', fontSize: 14 }}>Click Vera to cycle through states</p>
      </div>

      <VeraTamagotchi state={state} onClick={cycleState} />

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'center' }}>
        {states.map(s => (
          <button
            key={s}
            onClick={() => setState(s)}
            style={{
              padding: '8px 16px',
              background: state === s ? '#3b82f6' : '#1e293b',
              border: '1px solid #334155',
              borderRadius: 6,
              color: '#e2e8f0',
              cursor: 'pointer',
              fontSize: 12,
              textTransform: 'uppercase',
              fontWeight: 600,
              transition: 'all 0.2s'
            }}
            onMouseOver={(e) => {
              if (state !== s) e.target.style.background = '#334155';
            }}
            onMouseOut={(e) => {
              if (state !== s) e.target.style.background = '#1e293b';
            }}
          >
            {s}
          </button>
        ))}
      </div>

      <div style={{ 
        background: '#1e293b', 
        padding: 20, 
        borderRadius: 8,
        border: '1px solid #334155',
        maxWidth: 400
      }}>
        <h3 style={{ color: '#60a5fa', marginBottom: 12, fontSize: 14 }}>Integration Example</h3>
        <pre style={{ 
          color: '#cbd5e1', 
          fontSize: 12, 
          lineHeight: 1.6,
          overflow: 'auto'
        }}>{`<VeraTamagotchi state="thinking" />

// Update state based on activity:
setState('thinking') // Processing
setState('working')  // Active task
setState('happy')    // Success
setState('error')    // Error occurred
setState('sleeping') // Idle/inactive
setState('idle')     // Default`}</pre>
      </div>
    </div>
  );
}