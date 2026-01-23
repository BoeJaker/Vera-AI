// New UI components for capabilities and monitoring

interface CapabilityButtonProps {
  entity_id: string;
  capabilities: Capability[];
  onActivate: (capability: Capability) => void;
}

export const CapabilityButtons: React.FC<CapabilityButtonProps> = ({
  entity_id,
  capabilities,
  onActivate
}) => (
  <div className="capability-buttons">
    <h4>Available Capabilities</h4>
    {capabilities.map(cap => (
      <button
        key={cap.capability_type}
        onClick={() => onActivate(cap)}
        className={`capability-btn capability-${cap.status}`}
      >
        {getCapabilityIcon(cap.capability_type)}
        {cap.capability_type}
      </button>
    ))}
  </div>
);

// SSH Terminal Component
interface SSHTerminalProps {
  entity_id: string;
  capability: Capability;
}

export const SSHTerminal: React.FC<SSHTerminalProps> = ({
  entity_id,
  capability
}) => {
  const [output, setOutput] = useState<string[]>([]);
  const [input, setInput] = useState('');
  
  const sendCommand = async (cmd: string) => {
    // Call ExecuteCommandAction tool via API
    const response = await fetch('/api/tools/execute_command', {
      method: 'POST',
      body: JSON.stringify({
        entity_id,
        command: cmd,
        ...capability.config
      })
    });
    
    const result = await response.json();
    setOutput(prev => [...prev, `$ ${cmd}`, result.output]);
  };
  
  return (
    <div className="ssh-terminal">
      <div className="terminal-header">
        SSH Terminal: {entity_id}
      </div>
      <div className="terminal-output">
        {output.map((line, i) => (
          <div key={i}>{line}</div>
        ))}
      </div>
      <div className="terminal-input">
        <span>$ </span>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyPress={e => {
            if (e.key === 'Enter') {
              sendCommand(input);
              setInput('');
            }
          }}
        />
      </div>
    </div>
  );
};

// Monitoring Dashboard
interface MonitoringDashboardProps {
  jobs: MonitoringJob[];
}

export const MonitoringDashboard: React.FC<MonitoringDashboardProps> = ({
  jobs
}) => {
  const { lastMessage } = useWebSocket('/ws/tools/session_id');
  const [metrics, setMetrics] = useState<Map<string, any>>(new Map());
  
  useEffect(() => {
    if (!lastMessage) return;
    
    const msg = JSON.parse(lastMessage.data);
    if (msg.type === 'tool_event' && 
        msg.event.event_type === 'execution_progress') {
      const data = msg.event.data;
      if (data.job_id) {
        setMetrics(prev => new Map(prev).set(data.job_id, data.metrics));
      }
    }
  }, [lastMessage]);
  
  return (
    <div className="monitoring-dashboard">
      <h3>Active Monitoring Jobs</h3>
      {jobs.map(job => (
        <div key={job.job_id} className="monitoring-job">
          <div className="job-header">
            <span>{job.entity_id}</span>
            <span className={`status-${job.status}`}>{job.status}</span>
          </div>
          <div className="job-metrics">
            {metrics.get(job.job_id) && (
              <MetricsDisplay metrics={metrics.get(job.job_id)} />
            )}
          </div>
          <div className="job-controls">
            <button onClick={() => stopMonitoring(job.job_id)}>Stop</button>
          </div>
        </div>
      ))}
    </div>
  );
};