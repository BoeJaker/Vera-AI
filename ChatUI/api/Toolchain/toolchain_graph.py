"""
Backend API Integration for Tool-to-Graph Framework

Add these endpoints and modifications to your FastAPI application.
This enables real-time graph updates from tool execution.

REQUIREMENTS:
    pip install fastapi websockets

INTEGRATION STEPS:
    1. Import this module in your main FastAPI app
    2. Include the router: app.include_router(tool_graph_router)
    3. Add WebSocket manager to app state
    4. Update existing tool execution endpoints
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, List, Any, Optional
from pydantic import BaseModel
import asyncio
import logging
import json

from tool_graph_integration import (
    process_tool_graph_output,
    broadcast_graph_update,
    extract_graph_data
)

logger = logging.getLogger(__name__)

# ============================================================================
# WEBSOCKET MANAGER
# ============================================================================

class WebSocketManager:
    """
    Manages WebSocket connections for real-time graph updates.
    
    Usage in main app:
        ws_manager = WebSocketManager()
        app.state.websocket_manager = ws_manager
    """
    
    def __init__(self):
        # session_id -> list of WebSocket connections
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, session_id: str):
        """Register a new WebSocket connection."""
        await websocket.accept()
        
        async with self.lock:
            if session_id not in self.active_connections:
                self.active_connections[session_id] = []
            self.active_connections[session_id].append(websocket)
        
        logger.info(f"WebSocket connected for session {session_id}")
    
    async def disconnect(self, websocket: WebSocket, session_id: str):
        """Unregister a WebSocket connection."""
        async with self.lock:
            if session_id in self.active_connections:
                if websocket in self.active_connections[session_id]:
                    self.active_connections[session_id].remove(websocket)
                
                # Clean up empty session lists
                if not self.active_connections[session_id]:
                    del self.active_connections[session_id]
        
        logger.info(f"WebSocket disconnected for session {session_id}")
    
    async def broadcast_to_session(self, session_id: str, message: dict):
        """Broadcast message to all connections in a session."""
        if session_id not in self.active_connections:
            logger.debug(f"No active connections for session {session_id}")
            return
        
        # Create a copy of connections to avoid modification during iteration
        connections = self.active_connections[session_id].copy()
        
        disconnected = []
        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error sending to WebSocket: {e}")
                disconnected.append(connection)
        
        # Clean up disconnected sockets
        for connection in disconnected:
            await self.disconnect(connection, session_id)
    
    async def broadcast_to_all(self, message: dict):
        """Broadcast message to all active connections."""
        for session_id in list(self.active_connections.keys()):
            await self.broadcast_to_session(session_id, message)


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class ToolExecutionRequest(BaseModel):
    """Request model for tool execution."""
    tool_name: str
    tool_input: Dict[str, Any]
    node_id: Optional[str] = None  # Optional source node


class PluginExecutionRequest(BaseModel):
    """Request model for plugin execution."""
    plugin_name: str
    node_id: str
    parameters: Dict[str, Any]


class GraphUpdateResponse(BaseModel):
    """Response model for tool execution with graph updates."""
    output: str
    success: bool
    entities_created: int
    relationships_created: int
    execution_time_ms: float


# ============================================================================
# API ROUTER
# ============================================================================

tool_graph_router = APIRouter(prefix="/api", tags=["tool-graph"])


@tool_graph_router.websocket("/ws/graph/{session_id}")
async def websocket_graph_updates(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time graph updates.
    
    Client connects to this endpoint and receives graph_update messages
    whenever tools create new entities or relationships.
    
    Message format:
        {
            "type": "graph_update",
            "session_id": "...",
            "data": {
                "nodes": [...],
                "edges": [...]
            },
            "timestamp": "2025-01-..."
        }
    """
    manager: WebSocketManager = websocket.app.state.websocket_manager
    await manager.connect(websocket, session_id)
    
    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
            "message": "Graph updates WebSocket connected"
        })
        
        # Keep connection alive and handle incoming messages
        while True:
            # Receive messages (for ping/pong, etc.)
            data = await websocket.receive_text()
            
            # Handle ping
            if data == "ping":
                await websocket.send_text("pong")
    
    except WebSocketDisconnect:
        await manager.disconnect(websocket, session_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await manager.disconnect(websocket, session_id)


@tool_graph_router.post("/toolchain/{session_id}/execute-tool-enhanced")
async def execute_tool_with_graph_integration(
    session_id: str,
    request: ToolExecutionRequest,
    # Inject dependencies from your app
    # agent = Depends(get_agent),
    # ws_manager: WebSocketManager = Depends(get_ws_manager)
):
    """
    Enhanced tool execution endpoint with graph integration.
    
    This endpoint:
    1. Executes the tool
    2. Extracts graph data from the result
    3. Stores entities/relationships in memory
    4. Broadcasts updates to WebSocket clients
    
    Replace your existing /execute-tool endpoint with this one,
    or modify your existing endpoint to use process_tool_graph_output().
    """
    import time
    from fastapi import Request
    
    # Get dependencies (adjust based on your app structure)
    try:
        # Example - adjust to your dependency injection pattern
        agent = request.app.state.agents.get(session_id)
        ws_manager = request.app.state.websocket_manager
        
        if not agent:
            raise HTTPException(status_code=404, detail="Session not found")
        
        start_time = time.time()
        
        # Execute tool (adjust to your tool execution method)
        tool_name = request.tool_name
        tool_input = request.tool_input
        
        # Add node_id to tool input if provided
        if request.node_id:
            tool_input['node_id'] = request.node_id
        
        # Execute tool
        tool_result = agent.execute_tool(tool_name, tool_input)
        
        # Process graph outputs
        entities, relationships = process_tool_graph_output(
            tool_result,
            session_id,
            agent.mem,
            link_to_session=True
        )
        
        # Broadcast to WebSocket clients
        if entities or relationships:
            await broadcast_graph_update(
                session_id,
                entities,
                relationships,
                ws_manager
            )
        
        execution_time = (time.time() - start_time) * 1000
        
        # Extract text output
        if isinstance(tool_result, str):
            try:
                data = json.loads(tool_result)
                text_output = data.get("output", tool_result)
            except:
                text_output = tool_result
        else:
            text_output = str(tool_result)
        
        return GraphUpdateResponse(
            output=text_output,
            success=True,
            entities_created=len(entities),
            relationships_created=len(relationships),
            execution_time_ms=execution_time
        )
    
    except Exception as e:
        logger.error(f"Tool execution error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@tool_graph_router.post("/plugins/{session_id}/execute-enhanced")
async def execute_plugin_with_graph_integration(
    session_id: str,
    request: PluginExecutionRequest,
):
    """
    Enhanced plugin execution with graph integration.
    
    Similar to tool execution but for plugins.
    """
    import time
    from fastapi import Request
    
    try:
        agent = request.app.state.agents.get(session_id)
        ws_manager = request.app.state.websocket_manager
        
        if not agent:
            raise HTTPException(status_code=404, detail="Session not found")
        
        start_time = time.time()
        
        # Execute plugin
        plugin_result = agent.plugin_manager.execute_plugin(
            request.plugin_name,
            request.node_id,
            request.parameters
        )
        
        # Process graph outputs
        entities, relationships = process_tool_graph_output(
            plugin_result,
            session_id,
            agent.mem,
            link_to_session=True
        )
        
        # Broadcast updates
        if entities or relationships:
            await broadcast_graph_update(
                session_id,
                entities,
                relationships,
                ws_manager
            )
        
        execution_time = (time.time() - start_time) * 1000
        
        # Extract text output
        if isinstance(plugin_result, str):
            try:
                data = json.loads(plugin_result)
                text_output = data.get("output", plugin_result)
            except:
                text_output = plugin_result
        else:
            text_output = str(plugin_result)
        
        return GraphUpdateResponse(
            output=text_output,
            success=True,
            entities_created=len(entities),
            relationships_created=len(relationships),
            execution_time_ms=execution_time
        )
    
    except Exception as e:
        logger.error(f"Plugin execution error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@tool_graph_router.post("/graph/{session_id}/manual-add")
async def manual_add_entities(
    session_id: str,
    entities: List[Dict[str, Any]],
    relationships: List[Dict[str, Any]]
):
    """
    Manually add entities and relationships to the graph.
    
    Useful for tools that can't use the ToolGraphOutput wrapper
    or for external integrations.
    """
    from fastapi import Request
    
    try:
        agent = request.app.state.agents.get(session_id)
        ws_manager = request.app.state.websocket_manager
        
        if not agent:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Build fake tool result with graph data
        fake_result = {
            "output": "Manual entity addition",
            "__graph_data__": {
                "entities": entities,
                "relationships": relationships
            }
        }
        
        # Process through standard pipeline
        stored_entities, stored_relationships = process_tool_graph_output(
            fake_result,
            session_id,
            agent.mem,
            link_to_session=True
        )
        
        # Broadcast
        if stored_entities or stored_relationships:
            await broadcast_graph_update(
                session_id,
                stored_entities,
                stored_relationships,
                ws_manager
            )
        
        return {
            "success": True,
            "entities_added": len(stored_entities),
            "relationships_added": len(stored_relationships)
        }
    
    except Exception as e:
        logger.error(f"Manual add error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# INTEGRATION HELPER
# ============================================================================

def setup_tool_graph_integration(app):
    """
    Setup tool-graph integration in your FastAPI app.
    
    Call this in your main app initialization:
    
        from backend_api_integration import setup_tool_graph_integration
        
        app = FastAPI()
        setup_tool_graph_integration(app)
    """
    # Create WebSocket manager
    ws_manager = WebSocketManager()
    app.state.websocket_manager = ws_manager
    
    # Include router
    app.include_router(tool_graph_router)
    
    logger.info("Tool-Graph integration setup complete")
    logger.info("  - WebSocket endpoint: /api/ws/graph/{session_id}")
    logger.info("  - Enhanced tool endpoint: /api/toolchain/{session_id}/execute-tool-enhanced")
    logger.info("  - Enhanced plugin endpoint: /api/plugins/{session_id}/execute-enhanced")


# ============================================================================
# EXAMPLE: MODIFY EXISTING ENDPOINT
# ============================================================================

"""
If you want to modify your existing endpoint instead of replacing it:

@app.post("/api/toolchain/{session_id}/execute-tool")
async def execute_tool(session_id: str, tool_name: str, tool_input: str):
    # Your existing logic
    agent = get_agent(session_id)
    result = agent.execute_tool(tool_name, json.loads(tool_input))
    
    # ADD THIS: Process graph outputs
    entities, relationships = process_tool_graph_output(
        result, session_id, agent.mem
    )
    
    # ADD THIS: Broadcast to WebSocket clients
    if entities or relationships:
        ws_manager = app.state.websocket_manager
        await broadcast_graph_update(
            session_id, entities, relationships, ws_manager
        )
    
    # Return existing response
    return {"output": result}
"""


# ============================================================================
# TESTING
# ============================================================================

async def test_websocket_integration():
    """
    Test WebSocket manager functionality.
    """
    print("Testing WebSocket Manager")
    print("=" * 60)
    
    manager = WebSocketManager()
    
    # Test 1: Connection tracking
    print("\n✓ Test 1: WebSocket manager created")
    assert len(manager.active_connections) == 0
    
    # Test 2: Broadcast to empty session
    await manager.broadcast_to_session("test_session", {"test": "message"})
    print("✓ Test 2: Broadcast to empty session (no errors)")
    
    print("\n" + "=" * 60)
    print("WebSocket manager tests passed!")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_websocket_integration())