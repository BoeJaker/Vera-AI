
# ------------------------------------------------------------------------
# SYSTEM INTROSPECTION TOOLS
# ------------------------------------------------------------------------

import os
import sys
import io
from contextlib import contextmanager
from langchain_core.tools import StructuredTool
from Vera.Toolchain.schemas import EmptyInput, EnvVarInput
from typing import List, Any

def format_json(data: Any) -> str:
    """Format data as pretty JSON."""
    try:
        return json.dumps(data, indent=2, default=str)
    except:
        return str(data)

class SystemTool:
    """Tool for system introspection: environment variables, loaded modules, system info."""
    def __init__(self, agent):   
        self.agent = agent
        self.name = "SystemTool" 

    def list_python_modules(self, _: str = "") -> str:
        """List all currently loaded Python modules."""
        modules = sorted(sys.modules.keys())
        return "\n".join(modules)
    
    def get_system_info(self, _: str = "") -> str:
        """
        Get system information including OS, Python version, etc.
        """
        try:
            import platform
            
            info = {
                "os": platform.system(),
                "os_version": platform.release(),
                "architecture": platform.machine(),
                "python_version": sys.version,
                "python_executable": sys.executable,
                "cwd": os.getcwd(),
                "user": os.environ.get('USER', 'unknown')
            }
            
            return format_json(info)
            
        except Exception as e:
            return f"[Error] {str(e)}"

    
    # ------------------------------------------------------------------------
    # ENVIRONMENT & CONFIGURATION TOOLS
    # ------------------------------------------------------------------------
    
    def get_env_variable(self, var_name: str) -> str:
        """
        Get environment variable value.
        """
        value = os.environ.get(var_name)
        if value is None:
            return f"[Error] Environment variable '{var_name}' not found"
        return value
    
    def list_env_variables(self, _: str = "") -> str:
        """
        List all environment variables (sanitized for security).
        """
        # Filter out sensitive variables
        sensitive_keys = ['password', 'secret', 'key', 'token', 'api']
        
        env_vars = {}
        for key, value in os.environ.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                env_vars[key] = "[HIDDEN]"
            else:
                env_vars[key] = value
        
        return format_json(env_vars)

def add_system_tools(tool_list: List, agent) -> List:
    """Add system introspection tools to the tool list."""
    tools = SystemTool(agent)
    tool_list.extend(
        [

        # System Tools
        StructuredTool.from_function(
            func=tools.get_system_info,
            name="system_info",
            description="Get system information including OS, Python version, etc.",
            args_schema=EmptyInput 
        ),

        StructuredTool.from_function(
            func=tools.get_env_variable,
            name="get_env",
            description="Get environment variable value.",
            args_schema=EnvVarInput  
        ),

        StructuredTool.from_function(
            func=tools.list_env_variables,
            name="list_env",
            description="List all environment variables (sanitized).",
            args_schema=EmptyInput  
        ),
        StructuredTool.from_function(
            func=tools.list_python_modules,
            name="list_modules",
            description="List all currently loaded Python modules in the runtime.",
            args_schema=EmptyInput  
        ),
        ]
    )