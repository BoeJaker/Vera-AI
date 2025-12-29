// frontend/src/components/ToolUI.tsx
import React, { useEffect, useState, useRef } from 'react';
import { useWebSocket } from './hooks/useWebSocket';

// Types
interface GraphEvent {
  event_type: string;
  data: any;
  timestamp: number;
  event_id: string;
  tool_name: string;
  session_id: string;
}

interface UIComponent {
  component_type: string;
  data: any;
  metadata: any;
  component_id: string;
}

interface UIUpdate {
  update_type: 'append' | 'replace' | 'update';
  component: UIComponent;
  target_id?: string;
}

// Component Registry
const ComponentRegistry = {
  text: TextComponent,
  table: TableComponent,
  graph: GraphComponent,
  progress: ProgressComponent,
  entity_card: EntityCardComponent,
  code_block: CodeBlockComponent,
  alert: AlertComponent,
  metrics: MetricsComponent,
  network_topology: NetworkTopologyComponent,
};

// Main Tool UI Container
export const ToolUIContainer: React.FC<{ sessionId: string }> = ({ sessionId }) => {
  const [components, setComponents] = useState<UIComponent[]>([]);
  const [events, setEvents] = useState<GraphEvent[]>([]);
  const containerRef = useRef<HTMLDivElement>(null);
  
  // WebSocket connection
  const { lastMessage, sendMessage } = useWebSocket(
    `/ws/tools/${sessionId}`
  );
  
  useEffect(() => {
    if (!lastMessage) return;
    
    try {
      const message = JSON.parse(lastMessage.data);
      
      if (message.type === 'tool_event') {
        const event = message.event as GraphEvent;
        handleEvent(event);
      }
    } catch (e) {
      console.error('Failed to parse WebSocket message:', e);
    }
  }, [lastMessage]);
  
  const handleEvent = (event: GraphEvent) => {
    // Add to event log
    setEvents(prev => [...prev, event]);
    
    // Handle UI updates
    if (event.data.ui_update) {
      const update = event.data.ui_update as UIUpdate;
      handleUIUpdate(update);
    }
    
    // Handle graph events
    switch (event.event_type) {
      case 'entity_created':
      case 'entity_updated':
        handleEntityEvent(event);
        break;
      case 'relationship_created':
        handleRelationshipEvent(event);
        break;
      case 'data_discovered':
        handleDiscoveryEvent(event);
        break;
    }
  };
  
  const handleUIUpdate = (update: UIUpdate) => {
    switch (update.update_type) {
      case 'append':
        setComponents(prev => [...prev, update.component]);
        break;
      case 'replace':
        setComponents(prev => 
          prev.map(c => 
            c.component_id === update.target_id ? update.component : c
          )
        );
        break;
      case 'update':
        setComponents(prev => 
          prev.map(c => 
            c.component_id === update.target_id 
              ? { ...c, data: { ...c.data, ...update.component.data } }
              : c
          )
        );
        break;
    }
    
    // Auto-scroll to bottom
    setTimeout(() => {
      if (containerRef.current) {
        containerRef.current.scrollTop = containerRef.current.scrollHeight;
      }
    }, 100);
  };
  
  const handleEntityEvent = (event: GraphEvent) => {
    // Show toast notification
    showToast(
      `${event.event_type === 'entity_created' ? 'Created' : 'Updated'}: ${event.data.entity_id}`,
      'info'
    );
  };
  
  const handleRelationshipEvent = (event: GraphEvent) => {
    showToast(
      `Linked ${event.data.source_id} → ${event.data.target_id}`,
      'info'
    );
  };
  
  const handleDiscoveryEvent = (event: GraphEvent) => {
    const { discovery_type, ...data } = event.data;
    showToast(
      `Discovered ${discovery_type}: ${JSON.stringify(data)}`,
      'success'
    );
  };
  
  return (
    <div className="tool-ui-container" ref={containerRef}>
      {components.map((component, idx) => {
        const Component = ComponentRegistry[component.component_type as keyof typeof ComponentRegistry];
        if (!Component) return null;
        
        return <Component key={component.component_id} {...component.data} />;
      })}
      
      {/* Event log toggle */}
      <EventLog events={events} />
    </div>
  );
};

// Individual Components

const ProgressComponent: React.FC<any> = ({ current, total, percentage, message }) => (
  <div className="progress-component">
    <div className="progress-bar">
      <div 
        className="progress-fill" 
        style={{ width: `${percentage}%` }}
      />
    </div>
    <div className="progress-text">
      {message || `${current} / ${total} (${percentage.toFixed(1)}%)`}
    </div>
  </div>
);

const TableComponent: React.FC<any> = ({ headers, rows, title }) => (
  <div className="table-component">
    {title && <h3>{title}</h3>}
    <table>
      <thead>
        <tr>
          {headers.map((h: string, i: number) => <th key={i}>{h}</th>)}
        </tr>
      </thead>
      <tbody>
        {rows.map((row: any[], i: number) => (
          <tr key={i}>
            {row.map((cell, j) => <td key={j}>{cell}</td>)}
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);

const EntityCardComponent: React.FC<any> = ({ entity_id, type, labels, properties }) => (
  <div className="entity-card">
    <div className="entity-header">
      <span className="entity-id">{entity_id}</span>
      <span className="entity-type">{type}</span>
    </div>
    <div className="entity-labels">
      {labels.map((label: string) => (
        <span key={label} className="label">{label}</span>
      ))}
    </div>
    <div className="entity-properties">
      {Object.entries(properties).map(([key, value]) => (
        <div key={key} className="property">
          <span className="key">{key}:</span>
          <span className="value">{JSON.stringify(value)}</span>
        </div>
      ))}
    </div>
  </div>
);

const NetworkTopologyComponent: React.FC<any> = ({ nodes, edges, stats }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  
  useEffect(() => {
    if (!canvasRef.current) return;
    
    // Use D3 or similar for visualization
    renderNetworkTopology(canvasRef.current, nodes, edges);
  }, [nodes, edges]);
  
  return (
    <div className="network-topology">
      <div className="topology-stats">
        <span>Hosts: {stats.hosts}</span>
        <span>Ports: {stats.ports}</span>
      </div>
      <canvas ref={canvasRef} width={800} height={600} />
    </div>
  );
};

const CodeBlockComponent: React.FC<any> = ({ code, language, output, status }) => (
  <div className={`code-block status-${status}`}>
    <div className="code-header">
      <span className="language">{language}</span>
      <span className={`status status-${status}`}>{status}</span>
    </div>
    <pre className="code">
      <code>{code}</code>
    </pre>
    {output && (
      <div className="output">
        <div className="output-header">Output:</div>
        <pre>{output}</pre>
      </div>
    )}
  </div>
);

const AlertComponent: React.FC<any> = ({ message, severity, timestamp }) => (
  <div className={`alert alert-${severity}`}>
    <span className="icon">{getAlertIcon(severity)}</span>
    <span className="message">{message}</span>
    <span className="timestamp">{new Date(timestamp).toLocaleTimeString()}</span>
  </div>
);

const MetricsComponent: React.FC<any> = (metrics) => (
  <div className="metrics">
    {Object.entries(metrics).map(([key, value]) => (
      <div key={key} className="metric">
        <span className="metric-label">{key}:</span>
        <span className="metric-value">{value as any}</span>
      </div>
    ))}
  </div>
);

// Event Log Component
const EventLog: React.FC<{ events: GraphEvent[] }> = ({ events }) => {
  const [expanded, setExpanded] = useState(false);
  
  return (
    <div className="event-log">
      <button onClick={() => setExpanded(!expanded)}>
        {expanded ? 'Hide' : 'Show'} Event Log ({events.length})
      </button>
      
      {expanded && (
        <div className="event-list">
          {events.slice(-50).reverse().map(event => (
            <div key={event.event_id} className="event-item">
              <span className="event-type">{event.event_type}</span>
              <span className="tool-name">{event.tool_name}</span>
              <span className="timestamp">
                {new Date(event.timestamp * 1000).toLocaleTimeString()}
              </span>
              <pre className="event-data">{JSON.stringify(event.data, null, 2)}</pre>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// Helper functions
function getAlertIcon(severity: string): string {
  switch (severity) {
    case 'error': return '❌';
    case 'warning': return '⚠️';
    case 'success': return '✅';
    default: return 'ℹ️';
  }
}

function showToast(message: string, type: string) {
  // Implement toast notification
  console.log(`[${type}] ${message}`);
}

function renderNetworkTopology(canvas: HTMLCanvasElement, nodes: any[], edges: any[]) {
  // Implement D3 or custom network visualization
  // This is a placeholder
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  
  // Simple visualization
  nodes.forEach((node, i) => {
    const x = 100 + (i % 5) * 150;
    const y = 100 + Math.floor(i / 5) * 150;
    
    ctx.beginPath();
    ctx.arc(x, y, 20, 0, 2 * Math.PI);
    ctx.fillStyle = node.status === 'up' ? '#4CAF50' : '#999';
    ctx.fill();
    ctx.strokeStyle = '#333';
    ctx.stroke();
    
    ctx.fillStyle = '#000';
    ctx.fillText(node.label, x - 20, y + 40);
  });
}