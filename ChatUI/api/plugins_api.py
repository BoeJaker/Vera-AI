"""
Plugin API Endpoints
Add these to your FastAPI application to expose plugin operations
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import json

# Create router
router = APIRouter(prefix="/api/plugins", tags=["plugins"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class PluginInfo(BaseModel):
    """Plugin information model."""
    name: str
    tool_name: str
    description: str
    class_types: List[str]
    output_type: str
    category: str = "plugin"


class PluginExecutionRequest(BaseModel):
    """Plugin execution request model."""
    node_id: str
    plugin_name: str
    parameters: Dict[str, Any] = {}


class PluginExecutionResponse(BaseModel):
    """Plugin execution response model."""
    success: bool
    output: str
    error: Optional[str] = None
    plugin_name: str
    node_id: str


class PluginSchema(BaseModel):
    """Plugin parameter schema model."""
    name: str
    description: str
    parameters: List[Dict[str, Any]]


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_plugin_manager(session_id: str):
    """Get plugin manager for a session."""
    # This should be adapted to your session management system
    # Replace with your actual session lookup logic
    from Vera.ChatUI.api.session import get_session_status
    
    session = get_session_status(session_id)
    if not session or not hasattr(session, 'vera'):
        raise HTTPException(status_code=404, detail="Session not found")
    
    if not hasattr(session.vera, 'plugin_manager'):
        raise HTTPException(status_code=404, detail="Plugin manager not available")
    
    return session.vera.plugin_manager


def get_agent(session_id: str):
    """Get agent instance for a session."""
    from Vera.ChatUI.api.session import get_session_status
    
    session = get_session_status(session_id)
    if not session or not hasattr(session, 'vera'):
        raise HTTPException(status_code=404, detail="Session not found")
    
    return session.vera


# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.get("/{session_id}/list", response_model=List[PluginInfo])
async def list_plugins(session_id: str):
    """
    List all available plugins for a session.
    
    Returns plugin metadata including name, description, compatible class types.
    """
    try:
        agent = get_agent(session_id)
        plugin_manager = agent.plugin_manager
        
        if not plugin_manager:
            return []
        
        # Get plugin metadata
        from Vera.Toolchain.plugin_tool_bridge import PluginToolBridge
        bridge = PluginToolBridge(plugin_manager, agent)
        metadata = bridge.get_plugin_metadata()
        
        return metadata
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing plugins: {str(e)}")


@router.get("/{session_id}/plugin/{plugin_name}/schema", response_model=PluginSchema)
async def get_plugin_schema(session_id: str, plugin_name: str):
    """
    Get parameter schema for a specific plugin.
    
    Returns the plugin's expected parameters with types and descriptions.
    """
    try:
        agent = get_agent(session_id)
        plugin_manager = agent.plugin_manager
        
        if not plugin_manager:
            raise HTTPException(status_code=404, detail="Plugin manager not available")
        
        # Check if plugin exists
        if plugin_name not in plugin_manager.plugins:
            raise HTTPException(status_code=404, detail=f"Plugin '{plugin_name}' not found")
        
        plugin_instance = plugin_manager.plugins[plugin_name]
        
        # Get execute method signature
        import inspect
        sig = inspect.signature(plugin_instance.execute)
        
        # Build parameter list
        parameters = []
        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue
            
            param_type = param.annotation if param.annotation != inspect.Parameter.empty else 'string'
            if param_type != 'string':
                param_type = param_type.__name__
            
            has_default = param.default != inspect.Parameter.empty
            
            parameters.append({
                'name': param_name,
                'type': param_type,
                'required': not has_default,
                'default': param.default if has_default else None,
                'description': f'Parameter for {plugin_name}'
            })
        
        # If no parameters, add default ones
        if not parameters:
            parameters = [
                {
                    'name': 'node_id',
                    'type': 'string',
                    'required': True,
                    'default': None,
                    'description': 'Target node ID'
                },
                {
                    'name': 'args',
                    'type': 'string',
                    'required': False,
                    'default': None,
                    'description': 'Additional arguments as JSON string'
                }
            ]
        
        description = plugin_instance.description() if hasattr(plugin_instance, 'description') else f"Execute {plugin_name} plugin"
        
        return {
            'name': plugin_name,
            'description': description,
            'parameters': parameters
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting plugin schema: {str(e)}")


@router.post("/{session_id}/execute", response_model=PluginExecutionResponse)
async def execute_plugin(session_id: str, request: PluginExecutionRequest):
    """
    Execute a plugin on a specific node.
    
    Executes the plugin with provided parameters and returns the result.
    """
    try:
        agent = get_agent(session_id)
        plugin_manager = agent.plugin_manager
        
        if not plugin_manager:
            raise HTTPException(status_code=404, detail="Plugin manager not available")
        
        # Check if plugin exists
        if request.plugin_name not in plugin_manager.plugins:
            raise HTTPException(status_code=404, detail=f"Plugin '{request.plugin_name}' not found")
        
        plugin_instance = plugin_manager.plugins[request.plugin_name]
        
        # Set target node
        plugin_instance.target = request.node_id
        
        # Execute plugin
        try:
            result = plugin_instance.execute(**request.parameters)
            
            # Get output
            output = ""
            if plugin_instance.output:
                output = plugin_instance.output
                if isinstance(output, dict):
                    output = json.dumps(output, indent=2, default=str)
                elif not isinstance(output, str):
                    output = str(output)
            elif result:
                if isinstance(result, dict):
                    output = json.dumps(result, indent=2, default=str)
                else:
                    output = str(result)
            else:
                output = f"Plugin {request.plugin_name} executed successfully (no output)"
            
            # Store in agent memory
            if hasattr(agent, 'mem'):
                agent.mem.add_session_memory(
                    agent.sess.id,
                    f"Plugin: {request.plugin_name} on node: {request.node_id}",
                    "plugin_execution",
                    metadata={
                        "plugin": request.plugin_name,
                        "node_id": request.node_id,
                        "success": True,
                        "parameters": request.parameters
                    }
                )
            
            return {
                'success': True,
                'output': output,
                'error': None,
                'plugin_name': request.plugin_name,
                'node_id': request.node_id
            }
            
        except Exception as e:
            error_msg = f"Plugin execution error: {str(e)}"
            
            # Store error in memory
            if hasattr(agent, 'mem'):
                agent.mem.add_session_memory(
                    agent.sess.id,
                    error_msg,
                    "plugin_error",
                    metadata={
                        "plugin": request.plugin_name,
                        "node_id": request.node_id,
                        "success": False
                    }
                )
            
            return {
                'success': False,
                'output': '',
                'error': error_msg,
                'plugin_name': request.plugin_name,
                'node_id': request.node_id
            }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error executing plugin: {str(e)}")


@router.get("/{session_id}/compatible/{class_type}", response_model=List[PluginInfo])
async def get_compatible_plugins(session_id: str, class_type: str):
    """
    Get plugins compatible with a specific node class type.
    
    Filters plugins by their compatible class_types.
    """
    try:
        agent = get_agent(session_id)
        plugin_manager = agent.plugin_manager
        
        if not plugin_manager:
            return []
        
        # Get all plugins
        from Vera.Toolchain.plugin_tool_bridge import PluginToolBridge
        bridge = PluginToolBridge(plugin_manager, agent)
        all_metadata = bridge.get_plugin_metadata()
        
        # Filter by class type
        compatible = [
            p for p in all_metadata 
            if class_type in p['class_types'] or not p['class_types']  # Include universal plugins
        ]
        
        return compatible
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting compatible plugins: {str(e)}")


@router.post("/{session_id}/reload")
async def reload_plugins(session_id: str):
    """
    Reload all plugins from the plugins directory.
    
    Useful for development when plugins are modified.
    """
    try:
        agent = get_agent(session_id)
        plugin_manager = agent.plugin_manager
        
        if not plugin_manager:
            raise HTTPException(status_code=404, detail="Plugin manager not available")
        
        # Reload plugins
        plugin_manager.load_plugins('plugins')
        
        # Update tools
        agent.toolkit = ToolLoader(agent)
        
        return {
            'success': True,
            'message': f'Reloaded {len(plugin_manager.plugins)} plugins',
            'plugins': list(plugin_manager.plugins.keys())
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reloading plugins: {str(e)}")


# ============================================================================
# INTEGRATION INSTRUCTIONS
# ============================================================================
"""
To integrate these endpoints into your FastAPI app:

1. In your main FastAPI application file (e.g., app.py or main.py):

   from fastapi import FastAPI
   from plugin_api import router
   
   app = FastAPI()
   
   # Include the plugin router
   app.include_router(router)

2. Make sure you have a session management system that can retrieve
   agent instances by session_id. Update the get_agent() and 
   get_plugin_manager() functions to match your implementation.

3. If your session manager is different, modify:
   - get_session() import path
   - session.vera attribute access
   - Any other session-specific logic

Example session manager integration:

   # In your session_manager.py
   sessions = {}
   
   def get_session(session_id: str):
       return sessions.get(session_id)
   
   def create_session(session_id: str, vera_instance):
       sessions[session_id] = type('Session', (), {'vera': vera_instance})()
       return sessions[session_id]
"""