"""
GraphPlugin-to-Tool Bridge
Converts PluginManager plugins into LangChain tools for seamless integration
"""

from langchain.tools import StructuredTool
from pydantic import BaseModel, Field, create_model
from typing import List, Dict, Any, Optional
import inspect
import json


class PluginToolBridge:
    """Bridge between PluginManager and LangChain Tools system."""
    
    def __init__(self, plugin_manager, agent):
        """
        Initialize the bridge.
        
        Args:
            plugin_manager: PluginManager instance
            agent: Agent instance (for memory integration)
        """
        self.plugin_manager = plugin_manager
        self.agent = agent
        
    def create_plugin_schema(self, plugin_name: str, plugin_instance) -> type[BaseModel]:
        """
        Create a Pydantic schema for a plugin based on its execute method signature.
        
        Args:
            plugin_name: Name of the plugin
            plugin_instance: Plugin instance
            
        Returns:
            Pydantic model class for the plugin's parameters
        """
        # Get execute method signature
        execute_method = plugin_instance.execute
        sig = inspect.signature(execute_method)
        
        # Build field definitions
        fields = {}
        for param_name, param in sig.parameters.items():
            # Skip 'self' parameter
            if param_name == 'self':
                continue
                
            # Determine field type
            param_type = param.annotation if param.annotation != inspect.Parameter.empty else str
            
            # Determine if required
            has_default = param.default != inspect.Parameter.empty
            default_value = param.default if has_default else ...
            
            # Create field with description
            field_kwargs = {
                'description': f'Parameter for {plugin_name}'
            }
            
            if has_default:
                fields[param_name] = (param_type, default_value)
            else:
                fields[param_name] = (param_type, Field(..., **field_kwargs))
        
        # If no parameters detected, create a simple schema with node_id
        if not fields:
            fields = {
                'node_id': (str, Field(..., description='Target node ID')),
                'args': (Optional[str], Field(None, description='Additional arguments as JSON string'))
            }
        
        # Create dynamic Pydantic model
        schema_name = f"{plugin_name}Input"
        return create_model(schema_name, **fields)
    
    def create_plugin_tool_wrapper(self, plugin_name: str, plugin_instance) -> callable:
        """
        Create a wrapper function that executes a plugin with memory integration.
        
        Args:
            plugin_name: Name of the plugin
            plugin_instance: Plugin instance
            
        Returns:
            Wrapper function
        """
        def plugin_wrapper(**kwargs) -> str:
            """Execute plugin and integrate with agent memory."""
            try:
                # Extract node_id from kwargs
                node_id = kwargs.get('node_id')
                
                # If args is a JSON string, parse it
                if 'args' in kwargs and isinstance(kwargs['args'], str):
                    try:
                        args_dict = json.loads(kwargs['args'])
                        kwargs.update(args_dict)
                    except:
                        pass
                
                # Set target node on plugin
                if node_id:
                    plugin_instance.target = node_id
                
                # Execute plugin
                result = plugin_instance.execute(**kwargs)
                
                # Store in agent memory
                if hasattr(self.agent, 'mem') and node_id:
                    self.agent.mem.add_session_memory(
                        self.agent.sess.id,
                        f"Plugin: {plugin_name} on node: {node_id}",
                        "plugin_execution",
                        metadata={
                            "plugin": plugin_name,
                            "node_id": node_id,
                            "success": True
                        }
                    )
                
                # Format output
                if plugin_instance.output:
                    output = plugin_instance.output
                    if isinstance(output, dict):
                        output = json.dumps(output, indent=2, default=str)
                    elif not isinstance(output, str):
                        output = str(output)
                    return output
                elif result:
                    if isinstance(result, dict):
                        return json.dumps(result, indent=2, default=str)
                    return str(result)
                else:
                    return f"Plugin {plugin_name} executed successfully (no output)"
                
            except Exception as e:
                error_msg = f"[Plugin Error: {plugin_name}] {str(e)}"
                
                # Store error in memory
                if hasattr(self.agent, 'mem') and kwargs.get('node_id'):
                    self.agent.mem.add_session_memory(
                        self.agent.sess.id,
                        error_msg,
                        "plugin_error",
                        metadata={
                            "plugin": plugin_name,
                            "node_id": kwargs.get('node_id'),
                            "success": False
                        }
                    )
                
                return error_msg
        
        # Set function name for better tool identification
        plugin_wrapper.__name__ = f"plugin_{plugin_name}"
        
        return plugin_wrapper
    
    def convert_plugins_to_tools(self) -> List[StructuredTool]:
        """
        Convert all loaded plugins to LangChain tools.
        
        Returns:
            List of StructuredTool instances
        """
        tools = []
        
        for plugin_name, plugin_instance in self.plugin_manager.plugins.items():
            try:
                # Get plugin description
                description = plugin_instance.description() if hasattr(plugin_instance, 'description') else f"Execute {plugin_name} plugin"
                
                # Add class types to description
                if hasattr(plugin_instance, 'class_types'):
                    class_types = plugin_instance.class_types()
                    if class_types:
                        description += f" (Compatible with: {', '.join(class_types)})"
                
                # Create schema
                schema = self.create_plugin_schema(plugin_name, plugin_instance)
                
                # Create wrapper function
                wrapper = self.create_plugin_tool_wrapper(plugin_name, plugin_instance)
                
                # Create tool
                tool = StructuredTool.from_function(
                    func=wrapper,
                    name=f"plugin_{plugin_name}",
                    description=description,
                    args_schema=schema
                )
                
                tools.append(tool)
                
                print(f"✓ Converted plugin to tool: {plugin_name}")
                
            except Exception as e:
                print(f"✗ Failed to convert plugin {plugin_name}: {str(e)}")
                continue
        
        return tools
    
    def get_plugin_metadata(self) -> List[Dict[str, Any]]:
        """
        Get metadata for all plugins (for UI display).
        
        Returns:
            List of plugin metadata dictionaries
        """
        metadata = []
        
        for plugin_name, plugin_instance in self.plugin_manager.plugins.items():
            try:
                plugin_info = {
                    'name': plugin_name,
                    'tool_name': f"plugin_{plugin_name}",
                    'description': plugin_instance.description() if hasattr(plugin_instance, 'description') else f"Execute {plugin_name}",
                    'class_types': plugin_instance.class_types() if hasattr(plugin_instance, 'class_types') else [],
                    'output_type': plugin_instance.output_type(plugin_instance) if hasattr(plugin_instance, 'output_type') else 'unknown',
                    'category': 'plugin'
                }
                
                metadata.append(plugin_info)
                
            except Exception as e:
                print(f"Error getting metadata for {plugin_name}: {str(e)}")
                continue
        
        return metadata


def add_plugin_tools(tool_list: List, agent):
    """
    Add all plugins as tools to the tool list.
    
    Args:
        tool_list: Existing list of tools
        agent: Agent instance with plugin_manager attribute
        
    Returns:
        Updated tool list
    """
    if not hasattr(agent, 'plugin_manager'):
        print("[Info] No plugin manager found on agent")
        return tool_list
    
    try:
        bridge = PluginToolBridge(agent.plugin_manager, agent)
        plugin_tools = bridge.convert_plugins_to_tools()
        
        tool_list.extend(plugin_tools)
        
        print(f"✓ Added {len(plugin_tools)} plugins as tools")
        
    except Exception as e:
        print(f"[Warning] Failed to load plugin tools: {str(e)}")
    
    return tool_list