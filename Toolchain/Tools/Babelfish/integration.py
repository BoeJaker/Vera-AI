"""
Integration of Babelfish and WebServer tools into the existing tools.py framework
Add this section to your tools.py file
"""

from typing import Literal, Union
import threading

# ============================================================================
# BABELFISH INPUT SCHEMAS
# ============================================================================

class BabelfishProtocolInput(BaseModel):
    """Input schema for Babelfish protocol operations."""
    protocol: Literal["http", "ws", "mqtt", "tcp", "udp", "smtp"] = Field(
        ..., description="Protocol to use: http, ws, mqtt, tcp, udp, smtp"
    )
    action: str = Field(..., description="Action to perform (protocol-specific)")
    params: Dict[str, Any] = Field(
        default_factory=dict, 
        description="Protocol-specific parameters"
    )


class BabelfishHandleInput(BaseModel):
    """Input schema for Babelfish handle operations."""
    action: Literal["handles/list", "handles/read", "handles/close"] = Field(
        ..., description="Handle operation: list, read, or close"
    )
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters: {kind: str, handle: str, max_items: int}"
    )


class WebServerInput(BaseModel):
    """Input schema for WebServer operations."""
    action: Literal["start", "add_static", "add_dynamic", "remove_route", "list_routes"] = Field(
        ..., description="WebServer action to perform"
    )
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Action-specific parameters"
    )


# ============================================================================
# BABELFISH TOOLS CLASS
# ============================================================================

class BabelfishTools:
    """Wrapper for Babelfish multi-protocol communication tools."""
    
    def __init__(self, agent):
        self.agent = agent
        
        # Import Babelfish components (lazy to avoid import errors)
        try:
            from babelfish_module import BabelFishTool, WebServerTool
            self.babelfish = BabelFishTool()
            self.webserver = WebServerTool()
            self.available = True
        except ImportError:
            self.babelfish = None
            self.webserver = None
            self.available = False
            print("[Warning] Babelfish module not available")
    
    def protocol_communicate(self, protocol: str, action: str, params: Dict[str, Any]) -> str:
        """
        Universal protocol communication via Babelfish.
        
        Supported protocols:
        - http: HTTP/HTTPS requests
        - ws: WebSocket connections (persistent)
        - mqtt: MQTT pub/sub messaging
        - tcp: Raw TCP sockets (client/server)
        - udp: UDP datagrams (client/server)
        - smtp: Email sending via SMTP
        
        Common actions by protocol:
        
        HTTP:
        - action: "request" (implied)
        - params: {method: "GET|POST|PUT|DELETE", url: str, headers: dict, 
                  data: str, json: dict, timeout: int, verify: bool}
        
        WebSocket:
        - action: "open" -> returns handle
        - params: {url: str, headers: dict, subprotocols: list}
        - action: "send" -> params: {url: str, message: str}
        
        MQTT:
        - action: "connect" -> returns handle
        - params: {host: str, port: int, username: str, password: str, 
                  subscribe: [topics], tls: dict}
        - action: "publish" -> params: {handle: str, topic: str, payload: str, qos: int}
        - action: "subscribe" -> params: {handle: str, topics: list}
        - action: "disconnect" -> params: {handle: str}
        
        TCP:
        - action: "send" -> params: {host: str, port: int, data: str, data_b64: str}
        - action: "listen" -> returns handle, params: {host: str, port: int}
        - action: "close" -> params: {handle: str}
        
        UDP:
        - action: "send" -> params: {host: str, port: int, data: str, expect_response: bool}
        - action: "listen" -> returns handle, params: {host: str, port: int}
        - action: "close" -> params: {handle: str}
        
        SMTP:
        - action: "send" -> params: {host: str, port: int, from_addr: str, 
                  to_addrs: list, message: str, username: str, password: str, tls: bool}
        
        Returns JSON result: {"ok": bool, "data": any, "error": str}
        """
        if not self.available:
            return json.dumps({"ok": False, "error": "Babelfish not available"})
        
        try:
            query = {
                "protocol": protocol,
                "action": action,
                "params": params
            }
            
            result = self.babelfish._run(query)
            
            # Store in agent memory
            self.agent.mem.add_session_memory(
                self.agent.sess.id,
                f"{protocol}:{action}",
                "babelfish_action",
                metadata={
                    "protocol": protocol,
                    "action": action,
                    "params_keys": list(params.keys())
                }
            )
            
            return result
            
        except Exception as e:
            return json.dumps({
                "ok": False,
                "error": f"Babelfish error: {str(e)}"
            })
    
    def handle_operations(self, action: str, params: Dict[str, Any]) -> str:
        """
        Manage Babelfish connection handles.
        
        Actions:
        - handles/list: List active handles
          params: {kind: "ws|mqtt|tcp|udp"} (optional filter)
        
        - handles/read: Read queued messages from a handle
          params: {handle: str, max_items: int}
          Returns messages that arrived on persistent connections
        
        - handles/close: Close a handle and clean up
          params: {handle: str}
        
        Handles are used for persistent connections (WebSocket, MQTT, TCP/UDP listeners).
        After opening such a connection, use the returned handle ID to read messages
        or perform additional operations.
        """
        if not self.available:
            return json.dumps({"ok": False, "error": "Babelfish not available"})
        
        try:
            query = {
                "action": action,
                "params": params
            }
            
            result = self.babelfish._run(query)
            
            # Store in memory
            self.agent.mem.add_session_memory(
                self.agent.sess.id,
                action,
                "babelfish_handle_op",
                metadata={"action": action}
            )
            
            return result
            
        except Exception as e:
            return json.dumps({
                "ok": False,
                "error": f"Handle operation error: {str(e)}"
            })
    
    def webserver_control(self, action: str, params: Dict[str, Any]) -> str:
        """
        Control a dynamic FastAPI web server.
        
        Actions:
        
        - start: Start the web server
          params: {host: "0.0.0.0", port: 8000, log_level: "info"}
          Returns: {status: "started", url: "http://host:port"}
        
        - add_static: Mount a static file directory
          params: {route: "/static", folder: "/path/to/folder"}
          Serves files from folder at the specified route
        
        - add_dynamic: Create a dynamic endpoint
          params: {
              route: "/api/endpoint",
              method: "GET|POST|PUT|DELETE",
              handler: {
                  type: "json|text|file|python",
                  
                  # For type="json":
                  body: {json: "response"}
                  
                  # For type="text":
                  text: "response text"
                  
                  # For type="file":
                  path: "/path/to/file"
                  
                  # For type="python":
                  code: "return {'dynamic': 'response'}"
              }
          }
        
        - remove_route: Remove a route (marks as removed, FastAPI limitation)
          params: {route: "/api/endpoint"}
        
        - list_routes: List all registered routes
          params: {}
        
        Use this to create temporary APIs, serve files, or test endpoints.
        The server runs in a background thread.
        """
        if not self.available:
            return json.dumps({"ok": False, "error": "WebServer not available"})
        
        try:
            query = {
                "action": action,
                "params": params
            }
            
            result = self.webserver._run(query)
            
            # Store in memory
            self.agent.mem.add_session_memory(
                self.agent.sess.id,
                action,
                "webserver_action",
                metadata={
                    "action": action,
                    "route": params.get("route", "")
                }
            )
            
            return result
            
        except Exception as e:
            return json.dumps({
                "ok": False,
                "error": f"WebServer error: {str(e)}"
            })


# ============================================================================
# ADVANCED BABELFISH INTEGRATION (HTTP/3, WebRTC)
# ============================================================================

class AdvancedBabelfishTools:
    """
    Advanced Babelfish carriers: HTTP/3 (QUIC) and WebRTC.
    Requires: pip install aioquic aiortc
    """
    
    def __init__(self, agent):
        self.agent = agent
        
        try:
            from babelfish_advanced import Babelfish
            self.bf = Babelfish()
            self.available = True
        except ImportError:
            self.bf = None
            self.available = False
            print("[Warning] Advanced Babelfish (QUIC/WebRTC) not available")
    
    def quic_http3_request(self, url: str, method: str = "GET", 
                          headers: Optional[Dict[str, str]] = None,
                          body: Optional[str] = None) -> str:
        """
        Make HTTP/3 request over QUIC.
        
        HTTP/3 provides:
        - Faster connection establishment (0-RTT)
        - Better multiplexing than HTTP/2
        - Improved loss recovery
        - Better mobile performance
        
        Args:
            url: Target URL (must be https://)
            method: HTTP method (GET, POST, PUT, DELETE)
            headers: Optional HTTP headers
            body: Optional request body
        
        Returns JSON with received headers and data.
        """
        if not self.available:
            return json.dumps({"ok": False, "error": "HTTP/3 not available"})
        
        try:
            params = {
                "url": url,
                "method": method,
                "headers": headers or {},
            }
            if body:
                params["body"] = body
            
            handle_id = self.bf.open("http3", params)
            
            # Read response
            import time
            time.sleep(0.5)  # Allow time for response
            messages = self.bf.receive(handle_id, max_items=100)
            
            self.bf.close(handle_id)
            
            # Store in memory
            self.agent.mem.add_session_memory(
                self.agent.sess.id,
                url,
                "http3_request",
                metadata={"method": method, "url": url}
            )
            
            return json.dumps({
                "ok": True,
                "data": {
                    "handle": handle_id,
                    "messages": messages
                }
            })
            
        except Exception as e:
            return json.dumps({
                "ok": False,
                "error": f"HTTP/3 error: {str(e)}"
            })
    
    def webrtc_connect(self, role: str = "offer",
                      stun: Optional[str] = None,
                      turn: Optional[str] = None,
                      turn_username: Optional[str] = None,
                      turn_password: Optional[str] = None,
                      label: str = "datachannel") -> str:
        """
        Establish WebRTC DataChannel connection.
        
        WebRTC provides:
        - Peer-to-peer communication
        - NAT traversal via STUN/TURN
        - Encrypted data channels
        - Low latency real-time communication
        
        Args:
            role: "offer" (initiator) or "answer" (responder)
            stun: STUN server URL (e.g., "stun:stun.l.google.com:19302")
            turn: TURN server URL for NAT traversal
            turn_username: TURN authentication username
            turn_password: TURN authentication password
            label: DataChannel label
        
        Note: Requires signaling mechanism (WebSocket, HTTP, etc.)
        You must implement send_signal and wait_signal callbacks.
        
        Returns handle ID for sending/receiving data.
        """
        if not self.available:
            return json.dumps({"ok": False, "error": "WebRTC not available"})
        
        try:
            # This is a scaffold - you need to provide signaling
            return json.dumps({
                "ok": False,
                "error": "WebRTC requires custom signaling implementation. See documentation.",
                "hint": "Provide send_signal and wait_signal callbacks in params"
            })
            
        except Exception as e:
            return json.dumps({
                "ok": False,
                "error": f"WebRTC error: {str(e)}"
            })


# ============================================================================
# ADD TO TOOLLOADER FUNCTION
# ============================================================================

def add_babelfish_tools(tool_list: List, agent):
    """
    Add Babelfish multi-protocol communication tools.
    Call this in your ToolLoader function:
    
    tool_list = ToolLoader(agent)
    add_babelfish_tools(tool_list, agent)
    return tool_list
    """
    
    bf_tools = BabelfishTools(agent)
    
    if not bf_tools.available:
        print("[Info] Babelfish tools not loaded - module not available")
        return tool_list
    
    # Main Babelfish protocol tool
    tool_list.append(
        StructuredTool.from_function(
            func=bf_tools.protocol_communicate,
            name="babelfish",
            description=(
                "Universal multi-protocol communication tool. "
                "Supports HTTP/HTTPS, WebSocket, MQTT, TCP, UDP, SMTP. "
                "Enables persistent connections with handles, pub/sub messaging, "
                "socket servers, email sending, and more. "
                "Returns JSON: {ok: bool, data: any, error: str}"
            ),
            args_schema=BabelfishProtocolInput
        )
    )
    
    # Handle management tool
    tool_list.append(
        StructuredTool.from_function(
            func=bf_tools.handle_operations,
            name="babelfish_handles",
            description=(
                "Manage Babelfish connection handles. "
                "List active connections, read queued messages from persistent connections "
                "(WebSocket, MQTT, TCP/UDP listeners), or close handles. "
                "Essential for working with bidirectional protocols."
            ),
            args_schema=BabelfishHandleInput
        )
    )
    
    # WebServer tool
    tool_list.append(
        StructuredTool.from_function(
            func=bf_tools.webserver_control,
            name="webserver",
            description=(
                "Control a dynamic FastAPI web server. "
                "Start server, mount static directories, create dynamic endpoints "
                "(JSON, text, file, Python handlers), remove routes, list routes. "
                "Useful for creating temporary APIs, serving files, or testing. "
                "Server runs in background thread."
            ),
            args_schema=WebServerInput
        )
    )
    
    # Advanced tools (HTTP/3, WebRTC)
    adv_tools = AdvancedBabelfishTools(agent)
    
    if adv_tools.available:
        tool_list.extend([
            StructuredTool.from_function(
                func=adv_tools.quic_http3_request,
                name="http3_request",
                description=(
                    "Make HTTP/3 request over QUIC protocol. "
                    "Faster than HTTP/2, better multiplexing, 0-RTT connection. "
                    "Ideal for modern APIs and mobile networks."
                ),
                args_schema=HTTPInput
            ),
            StructuredTool.from_function(
                func=adv_tools.webrtc_connect,
                name="webrtc_connect",
                description=(
                    "Establish WebRTC DataChannel for peer-to-peer communication. "
                    "Supports STUN/TURN for NAT traversal, encrypted channels, "
                    "low-latency real-time data transfer. Requires signaling setup."
                ),
                args_schema=SearchInput  # Reuse for basic params
            ),
        ])
    
    return tool_list


# ============================================================================
# SAVE BABELFISH AS SEPARATE MODULE
# ============================================================================

def save_babelfish_module(output_path: str = "./babelfish_module.py"):
    """
    Helper to save the Babelfish code as a separate importable module.
    Copy the Babelfish code from your document into this file.
    """
    babelfish_code = '''
# Copy the entire Babelfish code from your document here
# This should include:
# - BabelFishTool class
# - WebServerTool class
# - All supporting classes and imports
'''
    
    with open(output_path, 'w') as f:
        f.write(babelfish_code)
    
    return f"✓ Saved Babelfish module to {output_path}"


# Required dependencies for Babelfish (add to requirements.txt):
# fastapi>=0.104.0
# uvicorn>=0.24.0
# websockets>=12.0
# paho-mqtt>=1.6.1
# requests>=2.31.0
# # Optional for advanced features:
# aioquic>=0.9.21
# aiortc>=1.6.0