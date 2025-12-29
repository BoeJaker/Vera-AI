"""
Vera Tool Framework with Real-time UI & Graph Broadcasting
Extends VTool with WebSocket communication and event streaming.
"""

from typing import Any, Dict, List, Optional, Iterator, Union, Type, Callable
from pydantic import BaseModel, Field
from dataclasses import dataclass, field
from enum import Enum
import json
import asyncio
from datetime import datetime
import uuid

# =============================================================================
# EVENT SYSTEM
# =============================================================================

class GraphEventType(str, Enum):
    """Types of graph events that can be broadcast"""
    ENTITY_CREATED = "entity_created"
    ENTITY_UPDATED = "entity_updated"
    RELATIONSHIP_CREATED = "relationship_created"
    EXECUTION_STARTED = "execution_started"
    EXECUTION_PROGRESS = "execution_progress"
    EXECUTION_COMPLETED = "execution_completed"
    EXECUTION_FAILED = "execution_failed"
    DATA_DISCOVERED = "data_discovered"

@dataclass
class GraphEvent:
    """Graph event for broadcasting"""
    event_type: GraphEventType
    data: Dict[str, Any]
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tool_name: str = ""
    session_id: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "data": self.data,
            "timestamp": self.timestamp,
            "event_id": self.event_id,
            "tool_name": self.tool_name,
            "session_id": self.session_id
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

class EventBroadcaster:
    """
    Manages event broadcasting to UI clients.
    Integrates with existing WebSocket infrastructure.
    """
    
    def __init__(self):
        self.listeners: List[Callable] = []
        self.event_queue: List[GraphEvent] = []
        self.max_queue_size: int = 1000
    
    def register_listener(self, callback: Callable[[GraphEvent], None]):
        """Register a callback for events"""
        self.listeners.append(callback)
    
    def unregister_listener(self, callback: Callable):
        """Unregister a callback"""
        if callback in self.listeners:
            self.listeners.remove(callback)
    
    def broadcast(self, event: GraphEvent):
        """Broadcast event to all listeners"""
        # Add to queue
        self.event_queue.append(event)
        if len(self.event_queue) > self.max_queue_size:
            self.event_queue.pop(0)
        
        # Notify listeners
        for listener in self.listeners:
            try:
                listener(event)
            except Exception as e:
                print(f"[EventBroadcaster] Listener error: {e}")
    
    def get_recent_events(self, count: int = 100) -> List[GraphEvent]:
        """Get recent events from queue"""
        return self.event_queue[-count:]

# =============================================================================
# UI DATA FORMATS
# =============================================================================

class UIComponentType(str, Enum):
    """Types of UI components that can be rendered"""
    TEXT = "text"
    TABLE = "table"
    GRAPH = "graph"
    PROGRESS = "progress"
    ENTITY_CARD = "entity_card"
    RELATIONSHIP_GRAPH = "relationship_graph"
    CODE_BLOCK = "code_block"
    ALERT = "alert"
    METRICS = "metrics"
    TIMELINE = "timeline"
    NETWORK_TOPOLOGY = "network_topology"

@dataclass
class UIComponent:
    """UI component for rendering in frontend"""
    component_type: UIComponentType
    data: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    component_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "component_type": self.component_type,
            "data": self.data,
            "metadata": self.metadata,
            "component_id": self.component_id
        }

@dataclass
class UIUpdate:
    """Update to send to UI"""
    update_type: str  # "append", "replace", "update"
    component: UIComponent
    target_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "update_type": self.update_type,
            "component": self.component.to_dict(),
            "target_id": self.target_id
        }

# =============================================================================
# ENHANCED VTOOL WITH UI SUPPORT
# =============================================================================

from tool_framework import VTool, ToolResult, ToolEntity, ToolRelationship, OutputType

class UITool(VTool):
    """
    Enhanced VTool with UI communication and graph broadcasting.
    
    Features:
    - Real-time progress updates to UI
    - Graph event broadcasting
    - Structured UI components
    - WebSocket integration
    """
    
    def __init__(self, agent):
        super().__init__(agent)
        
        # UI/Broadcasting
        self.broadcaster = getattr(agent, 'event_broadcaster', EventBroadcaster())
        self.ui_updates: List[UIUpdate] = []
        self.enable_ui = True
        self.enable_broadcasting = True
    
    # -------------------------------------------------------------------------
    # UI COMMUNICATION METHODS
    # -------------------------------------------------------------------------
    
    def send_ui_component(self, component: UIComponent, update_type: str = "append"):
        """Send a UI component to the frontend"""
        if not self.enable_ui:
            return
        
        update = UIUpdate(
            update_type=update_type,
            component=component
        )
        self.ui_updates.append(update)
        
        # Broadcast to WebSocket if available
        self._broadcast_ui_update(update)
    
    def send_progress(self, current: int, total: int, message: str = ""):
        """Send progress update"""
        self.send_ui_component(UIComponent(
            component_type=UIComponentType.PROGRESS,
            data={
                "current": current,
                "total": total,
                "percentage": (current / total * 100) if total > 0 else 0,
                "message": message
            }
        ))
    
    def send_table(self, headers: List[str], rows: List[List[Any]], title: str = ""):
        """Send table data"""
        self.send_ui_component(UIComponent(
            component_type=UIComponentType.TABLE,
            data={
                "headers": headers,
                "rows": rows,
                "title": title
            }
        ))
    
    def send_entity_card(self, entity: ToolEntity):
        """Send entity card for display"""
        self.send_ui_component(UIComponent(
            component_type=UIComponentType.ENTITY_CARD,
            data={
                "entity_id": entity.id,
                "type": entity.type,
                "labels": entity.labels,
                "properties": entity.properties,
                "metadata": entity.metadata
            }
        ))
    
    def send_graph_update(self, nodes: List[Dict], edges: List[Dict], layout: str = "force"):
        """Send graph visualization update"""
        self.send_ui_component(UIComponent(
            component_type=UIComponentType.GRAPH,
            data={
                "nodes": nodes,
                "edges": edges,
                "layout": layout
            }
        ))
    
    def send_network_topology(self, topology: Dict[str, Any]):
        """Send network topology visualization"""
        self.send_ui_component(UIComponent(
            component_type=UIComponentType.NETWORK_TOPOLOGY,
            data=topology
        ))
    
    def send_alert(self, message: str, severity: str = "info"):
        """Send alert message"""
        self.send_ui_component(UIComponent(
            component_type=UIComponentType.ALERT,
            data={
                "message": message,
                "severity": severity,
                "timestamp": datetime.now().isoformat()
            }
        ))
    
    def send_metrics(self, metrics: Dict[str, Any]):
        """Send metrics/statistics"""
        self.send_ui_component(UIComponent(
            component_type=UIComponentType.METRICS,
            data=metrics
        ))
    
    # -------------------------------------------------------------------------
    # GRAPH EVENT BROADCASTING
    # -------------------------------------------------------------------------
    
    def broadcast_event(self, event: GraphEvent):
        """Broadcast a graph event"""
        if not self.enable_broadcasting:
            return
        
        event.tool_name = self.tool_name
        event.session_id = self.sess.id if self.sess else ""
        
        self.broadcaster.broadcast(event)
    
    def _broadcast_execution_started(self, inputs: Dict[str, Any]):
        """Broadcast execution start"""
        self.broadcast_event(GraphEvent(
            event_type=GraphEventType.EXECUTION_STARTED,
            data={
                "tool_name": self.tool_name,
                "inputs": inputs,
                "execution_id": self.execution_node_id
            }
        ))
    
    def _broadcast_execution_progress(self, progress: Dict[str, Any]):
        """Broadcast execution progress"""
        self.broadcast_event(GraphEvent(
            event_type=GraphEventType.EXECUTION_PROGRESS,
            data={
                "execution_id": self.execution_node_id,
                **progress
            }
        ))
    
    def _broadcast_execution_completed(self, result: ToolResult):
        """Broadcast execution completion"""
        self.broadcast_event(GraphEvent(
            event_type=GraphEventType.EXECUTION_COMPLETED,
            data={
                "execution_id": self.execution_node_id,
                "success": result.success,
                "entities_created": len(result.entities),
                "relationships_created": len(result.relationships),
                "execution_time": result.execution_time
            }
        ))
    
    def _broadcast_ui_update(self, update: UIUpdate):
        """Broadcast UI update as event"""
        self.broadcast_event(GraphEvent(
            event_type=GraphEventType.EXECUTION_PROGRESS,
            data={
                "ui_update": update.to_dict()
            }
        ))
    
    # -------------------------------------------------------------------------
    # ENHANCED ENTITY CREATION WITH BROADCASTING
    # -------------------------------------------------------------------------
    
    def create_entity(self, entity_id: str, entity_type: str,
                     labels: Optional[List[str]] = None,
                     properties: Optional[Dict] = None,
                     metadata: Optional[Dict] = None,
                     reuse_if_exists: bool = True,
                     broadcast: bool = True) -> ToolEntity:
        """Create entity with broadcasting"""
        
        entity = super().create_entity(
            entity_id, entity_type, labels, properties, metadata, reuse_if_exists
        )
        
        if broadcast and self.enable_broadcasting:
            event_type = GraphEventType.ENTITY_UPDATED if entity.metadata.get("reused") else GraphEventType.ENTITY_CREATED
            
            self.broadcast_event(GraphEvent(
                event_type=event_type,
                data={
                    "entity_id": entity.id,
                    "entity_type": entity.type,
                    "labels": entity.labels,
                    "properties": entity.properties,
                    "reused": entity.metadata.get("reused", False)
                }
            ))
            
            # Send entity card to UI
            self.send_entity_card(entity)
        
        return entity
    
    def link_entities(self, source_id: str, target_id: str, rel_type: str,
                     properties: Optional[Dict] = None,
                     broadcast: bool = True) -> ToolRelationship:
        """Create relationship with broadcasting"""
        
        rel = super().link_entities(source_id, target_id, rel_type, properties)
        
        if broadcast and self.enable_broadcasting:
            self.broadcast_event(GraphEvent(
                event_type=GraphEventType.RELATIONSHIP_CREATED,
                data={
                    "source_id": source_id,
                    "target_id": target_id,
                    "relationship_type": rel_type,
                    "properties": properties or {}
                }
            ))
        
        return rel
    
    # -------------------------------------------------------------------------
    # ENHANCED EXECUTION WITH UI UPDATES
    # -------------------------------------------------------------------------
    
    def execute(self, **kwargs) -> Iterator[Union[str, ToolResult, UIUpdate]]:
        """Execute with UI updates"""
        
        # Broadcast execution start
        self._broadcast_execution_started(kwargs)
        
        # Call parent execute
        for item in super().execute(**kwargs):
            if isinstance(item, ToolResult):
                # Broadcast completion
                self._broadcast_execution_completed(item)
                
                # Yield all queued UI updates first
                for ui_update in self.ui_updates:
                    yield ui_update
                
                # Then yield result
                yield item
            else:
                yield item
    
    # -------------------------------------------------------------------------
    # GRAPH VISUALIZATION HELPERS
    # -------------------------------------------------------------------------
    
    def visualize_subgraph(self, entity_ids: List[str], depth: int = 1):
        """Visualize a subgraph around entities"""
        try:
            subgraph = self.mem.extract_subgraph(entity_ids, depth=depth)
            
            # Convert to UI format
            nodes = []
            for node in subgraph.get("nodes", []):
                nodes.append({
                    "id": node.get("id"),
                    "label": node.get("properties", {}).get("text", node.get("id"))[:30],
                    "type": node.get("properties", {}).get("type", "unknown"),
                    "properties": node.get("properties", {})
                })
            
            edges = []
            for rel in subgraph.get("rels", []):
                if rel:
                    edges.append({
                        "source": rel.get("start"),
                        "target": rel.get("end"),
                        "label": rel.get("properties", {}).get("rel", "RELATED"),
                        "properties": rel.get("properties", {})
                    })
            
            self.send_graph_update(nodes, edges)
            
        except Exception as e:
            self.send_alert(f"Failed to visualize graph: {str(e)}", "error")

# =============================================================================
# WEBSOCKET INTEGRATION
# =============================================================================

class ToolWebSocketManager:
    """
    Manages WebSocket connections for real-time tool updates.
    Integrates with existing Vera WebSocket infrastructure.
    """
    
    def __init__(self, broadcaster: EventBroadcaster):
        self.broadcaster = broadcaster
        self.connections: Dict[str, Any] = {}  # session_id -> websocket
        
        # Register as event listener
        self.broadcaster.register_listener(self.on_event)
    
    async def register_connection(self, session_id: str, websocket):
        """Register a WebSocket connection"""
        self.connections[session_id] = websocket
    
    async def unregister_connection(self, session_id: str):
        """Unregister a WebSocket connection"""
        if session_id in self.connections:
            del self.connections[session_id]
    
    def on_event(self, event: GraphEvent):
        """Handle broadcast event"""
        # Send to relevant WebSocket connections
        session_id = event.session_id
        
        if session_id in self.connections:
            asyncio.create_task(self._send_event(session_id, event))
    
    async def _send_event(self, session_id: str, event: GraphEvent):
        """Send event to WebSocket"""
        websocket = self.connections.get(session_id)
        if not websocket:
            return
        
        try:
            await websocket.send_text(json.dumps({
                "type": "tool_event",
                "event": event.to_dict()
            }))
        except Exception as e:
            print(f"[WebSocket] Failed to send event: {e}")

# =============================================================================
# EXAMPLE IMPLEMENTATIONS
# =============================================================================

class NetworkScanUITool(UITool):
    """
    Network scanner with real-time UI updates and broadcasting.
    Demonstrates full UI integration.
    """
    
    def get_input_schema(self):
        from pydantic import BaseModel, Field
        
        class NetworkScanInput(BaseModel):
            target: str = Field(description="Target network")
            ports: str = Field(default="1-1000", description="Port range")
        
        return NetworkScanInput
    
    def get_output_type(self):
        return OutputType.JSON
    
    def _execute(self, target: str, ports: str = "1-1000") -> Iterator:
        """Execute network scan with UI updates"""
        
        # Initial UI
        self.send_alert(f"Starting network scan of {target}", "info")
        
        # Parse targets
        from Vera.Toolchain.Tools.OSINT.network_scanning import TargetParser
        parser = TargetParser()
        targets = parser.parse(target)
        port_list = parser.parse_ports(ports)
        
        # Send initial metrics
        self.send_metrics({
            "total_targets": len(targets),
            "total_ports": len(port_list),
            "status": "scanning"
        })
        
        # Host discovery
        yield "╔═══════════════════════════════════════════════════════════╗\n"
        yield "║                   NETWORK SCAN                            ║\n"
        yield "╚═══════════════════════════════════════════════════════════╝\n\n"
        
        from Vera.Toolchain.Tools.OSINT.network_scanning import (
            HostDiscovery, PortScanner, NetworkScanConfig
        )
        
        config = NetworkScanConfig()
        discoverer = HostDiscovery(config)
        scanner = PortScanner(config)
        
        # Track discovered data
        live_hosts = []
        all_ports = []
        topology_nodes = []
        topology_edges = []
        
        # Host discovery with progress
        for idx, host_info in enumerate(discoverer.discover_live_hosts(targets), 1):
            if host_info["alive"]:
                ip = host_info["ip"]
                hostname = host_info["hostname"]
                
                live_hosts.append(ip)
                
                # Create entity with broadcast
                entity = self.create_entity(
                    entity_id=f"ip_{ip.replace('.', '_')}",
                    entity_type="network_host",
                    labels=["NetworkHost", "IP"],
                    properties={
                        "ip_address": ip,
                        "hostname": hostname,
                        "status": "up"
                    },
                    broadcast=True
                )
                
                # Add to topology
                topology_nodes.append({
                    "id": entity.id,
                    "label": ip,
                    "type": "host",
                    "status": "up"
                })
                
                # Update progress
                self.send_progress(idx, len(targets), f"Discovered {ip}")
                
                # Broadcast discovery event
                self.broadcast_event(GraphEvent(
                    event_type=GraphEventType.DATA_DISCOVERED,
                    data={
                        "discovery_type": "host",
                        "ip": ip,
                        "hostname": hostname
                    }
                ))
                
                yield f"  [✓] {ip}"
                if hostname:
                    yield f" ({hostname})"
                yield "\n"
        
        # Port scanning with live topology updates
        for host_idx, ip in enumerate(live_hosts, 1):
            ip_entity_id = f"ip_{ip.replace('.', '_')}"
            
            yield f"\n[•] Scanning {ip}...\n"
            
            for port_info in scanner.scan_host(ip, port_list):
                port_num = port_info["port"]
                
                # Create port entity
                port_entity = self.create_entity(
                    entity_id=f"{ip_entity_id}_port_{port_num}",
                    entity_type="network_port",
                    labels=["NetworkPort", "Port"],
                    properties={
                        "port_number": port_num,
                        "state": "open",
                        "service": port_info["service"]
                    },
                    broadcast=True
                )
                
                # Link entities
                self.link_entities(ip_entity_id, port_entity.id, "HAS_PORT", broadcast=True)
                
                # Add to topology
                topology_edges.append({
                    "source": ip_entity_id,
                    "target": port_entity.id,
                    "label": f":{port_num}"
                })
                
                all_ports.append({
                    "ip": ip,
                    "port": port_num,
                    "service": port_info["service"]
                })
                
                # Broadcast discovery
                self.broadcast_event(GraphEvent(
                    event_type=GraphEventType.DATA_DISCOVERED,
                    data={
                        "discovery_type": "port",
                        "ip": ip,
                        "port": port_num,
                        "service": port_info["service"]
                    }
                ))
                
                yield f"    [✓] Port {port_num}: {port_info['service']}\n"
            
            # Update topology after each host
            self.send_network_topology({
                "nodes": topology_nodes,
                "edges": topology_edges,
                "stats": {
                    "hosts": len(live_hosts),
                    "ports": len(all_ports)
                }
            })
        
        # Final summary table
        if all_ports:
            self.send_table(
                headers=["IP", "Port", "Service"],
                rows=[[p["ip"], p["port"], p["service"]] for p in all_ports],
                title="Scan Results"
            )
        
        # Final metrics
        self.send_metrics({
            "total_targets": len(targets),
            "live_hosts": len(live_hosts),
            "open_ports": len(all_ports),
            "status": "completed"
        })
        
        yield f"\n╔═══════════════════════════════════════════════════════════╗\n"
        yield f"  Live Hosts:     {len(live_hosts)}\n"
        yield f"  Open Ports:     {len(all_ports)}\n"
        yield f"╚═══════════════════════════════════════════════════════════╝\n"
        
        yield ToolResult(
            success=True,
            output={
                "live_hosts": live_hosts,
                "open_ports": all_ports
            },
            output_type=OutputType.JSON,
            metadata={
                "hosts_found": len(live_hosts),
                "ports_found": len(all_ports)
            }
        )


class CodeExecutionUITool(UITool):
    """
    Code execution with live output streaming to UI.
    """
    
    def get_input_schema(self):
        from pydantic import BaseModel, Field
        
        class CodeExecInput(BaseModel):
            code: str = Field(description="Code to execute")
            language: str = Field(default="python", description="Language")
        
        return CodeExecInput
    
    def get_output_type(self):
        return OutputType.CODE
    
    def _execute(self, code: str, language: str = "python") -> Iterator:
        """Execute code with live output"""
        
        # Send code block to UI
        self.send_ui_component(UIComponent(
            component_type=UIComponentType.CODE_BLOCK,
            data={
                "code": code,
                "language": language,
                "status": "executing"
            }
        ))
        
        self.send_alert("Executing code...", "info")
        
        import sys
        import io
        
        old_stdout = sys.stdout
        redirected = sys.stdout = io.StringIO()
        
        try:
            # Execute
            exec(code, globals())
            output = redirected.getvalue()
            
            # Send output
            self.send_ui_component(UIComponent(
                component_type=UIComponentType.CODE_BLOCK,
                data={
                    "code": code,
                    "language": language,
                    "output": output,
                    "status": "success"
                }
            ), update_type="replace")
            
            self.send_alert("Execution completed", "success")
            
            yield output
            
            yield ToolResult(
                success=True,
                output=output,
                output_type=OutputType.CODE
            )
            
        except Exception as e:
            error_msg = str(e)
            
            self.send_ui_component(UIComponent(
                component_type=UIComponentType.CODE_BLOCK,
                data={
                    "code": code,
                    "language": language,
                    "output": error_msg,
                    "status": "error"
                }
            ), update_type="replace")
            
            self.send_alert(f"Execution failed: {error_msg}", "error")
            
            yield ToolResult(
                success=False,
                output=error_msg,
                output_type=OutputType.CODE,
                error=error_msg
            )
        
        finally:
            sys.stdout = old_stdout

# =============================================================================
# INTEGRATION WITH EXISTING SYSTEM
# =============================================================================

def integrate_ui_tools(agent):
    """
    Integrate UI tools with existing Vera system.
    
    Call this during agent initialization:
    
    class Vera:
        def __init__(self):
            # ... existing setup ...
            
            # Add UI/Broadcasting support
            integrate_ui_tools(self)
    """
    
    # Add event broadcaster
    if not hasattr(agent, 'event_broadcaster'):
        agent.event_broadcaster = EventBroadcaster()
    
    # Add WebSocket manager
    if not hasattr(agent, 'tool_websocket_manager'):
        agent.tool_websocket_manager = ToolWebSocketManager(agent.event_broadcaster)
    
    print("[UITools] Integrated event broadcasting and WebSocket support")


def add_ui_tools_to_loader(tool_list: List, agent):
    """
    Add UI-enabled tools to ToolLoader.
    
    Usage in ToolLoader:
        from tool_ui_framework import add_ui_tools_to_loader
        
        add_ui_tools_to_loader(tool_list, agent)
    """
    from tool_framework import vtool_to_langchain
    
    # Ensure UI integration
    integrate_ui_tools(agent)
    
    # Add UI tools
    ui_tools = [
        NetworkScanUITool(agent),
        CodeExecutionUITool(agent),
    ]
    
    for uitool in ui_tools:
        tool_list.append(vtool_to_langchain(uitool))
    
    return tool_list

# =============================================================================
# FASTAPI INTEGRATION
# =============================================================================

"""
Add to your existing FastAPI app (ChatUI/api/session.py):
"""

from fastapi import WebSocket, WebSocketDisconnect

async def tool_websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for tool updates.
    
    Add to FastAPI router:
        @router.websocket("/ws/tools/{session_id}")
        async def tool_ws(websocket: WebSocket, session_id: str):
            await tool_websocket_endpoint(websocket, session_id)
    """
    await websocket.accept()
    
    # Get agent for session
    vera = get_vera_for_session(session_id)  # Your existing function
    
    # Register WebSocket
    await vera.tool_websocket_manager.register_connection(session_id, websocket)
    
    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()
            
            # Handle commands from client
            try:
                cmd = json.loads(data)
                if cmd.get("type") == "subscribe":
                    # Client subscribing to events
                    await websocket.send_text(json.dumps({
                        "type": "subscribed",
                        "session_id": session_id
                    }))
            except:
                pass
                
    except WebSocketDisconnect:
        await vera.tool_websocket_manager.unregister_connection(session_id)