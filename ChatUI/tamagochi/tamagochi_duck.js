import React, { useState, useEffect } from 'react';

const VeraTamagotchi = ({ state = 'idle', onClick }) => {
  const [frame, setFrame] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => setFrame(f => (f + 1) % 4), 500);
    return () => clearInterval(interval);
  }, []);

  const states = {
    idle: { color: '#60a5fa', eyes: '• •', mouth: '‿', bounce: false },
    thinking: { color: '#8b5cf6', eyes: '◉ ◉', mouth: '○', bounce: true },
    happy: { color: '#10b981', eyes: '^ ^', mouth: '‿', bounce: true },
    working: { color: '#f59e0b', eyes: '◐ ◑', mouth: '‿', bounce: false },
    error: { color: '#ef4444', eyes: '× ×', mouth: '△', bounce: false },
    sleeping: { color: '#64748b', eyes: '- -', mouth: '‿', bounce: false }
  };

  const current = states[state] || states.idle;
  const size = 80;
  const y = current.bounce ? Math.sin(frame * Math.PI / 2) * 3 : 0;

  return (
    <div style={{ 
      width: size, 
      height: size, 
      position: 'relative',
      cursor: 'pointer'
    }} onClick={onClick}>
      <svg width={size} height={size} viewBox="0 0 100 100">
        <ellipse cx="50" cy="90" rx="25" ry="8" fill="rgba(0,0,0,0.2)" />
        
        <g transform={`translate(0, ${y})`}>
          <rect x="20" y="40" width="60" height="45" rx="25" fill={current.color} />
          <circle cx="50" cy="35" r="30" fill={current.color} />
          
          <text x="50" y="35" fontSize="20" textAnchor="middle" fill="#fff" fontFamily="monospace">
            {current.eyes}
          </text>
          <text x="50" y="55" fontSize="16" textAnchor="middle" fill="#fff">
            {current.mouth}
          </text>
          
          <line x1="50" y1="5" x2="50" y2="15" stroke={current.color} strokeWidth="3" strokeLinecap="round" />
          <circle cx="50" cy="5" r="4" fill="#fbbf24" />
          
          <ellipse cx="15" cy="60" rx="8" ry="15" fill={current.color} 
            transform={`rotate(${frame * 10 - 20} 15 60)`} />
          <ellipse cx="85" cy="60" rx="8" ry="15" fill={current.color} 
            transform={`rotate(${-frame * 10 + 20} 85 60)`} />
        </g>
      </svg>
      
      <div style={{
        position: 'absolute',
        bottom: -20,
        left: 0,
        right: 0,
        textAlign: 'center',
        fontSize: 11,
        color: current.color,
        fontWeight: 600,
        textTransform: 'uppercase'
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