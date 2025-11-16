"""
Dynamic Tool Loading System - Refactored for Consistent Integration
Add this section to your existing tools.py file
"""
import os
import sys
import importlib.util
import inspect
import traceback
from pathlib import Path
from typing import Callable, Optional, Any, Dict, List
from functools import wraps

from pydantic import BaseModel, Field, create_model
from langchain_core.tools import StructuredTool

from Vera.Toolchain.schemas import *

project_root = Path(__file__).parent
tools_dir = project_root / "Plugins"

# ============================================================================
# TOOL DECORATOR & REGISTRY (unchanged, but included for completeness)
# ============================================================================

class ToolRegistry:
    """Global registry for decorated tools."""
    _tools: Dict[str, Dict[str, Any]] = {}
    
    @classmethod
    def register(cls, name: str, func: Callable, description: str, 
                 schema: Optional[type] = None, category: str = "general"):
        """Register a tool in the global registry."""
        cls._tools[name] = {
            "function": func,
            "description": description,
            "schema": schema,
            "category": category,
            "module": func.__module__
        }
    
    @classmethod
    def get_tool(cls, name: str) -> Optional[Dict[str, Any]]:
        """Get a tool by name."""
        return cls._tools.get(name)
    
    @classmethod
    def list_tools(cls, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all registered tools, optionally filtered by category."""
        if category:
            return [
                {"name": name, **info} 
                for name, info in cls._tools.items() 
                if info["category"] == category
            ]
        return [{"name": name, **info} for name, info in cls._tools.items()]
    
    @classmethod
    def clear(cls):
        """Clear all registered tools."""
        cls._tools.clear()


def tool(name: str = None, description: str = None, 
         schema: type = None, category: str = "general"):
    """
    Decorator to register a function as a tool.
    
    Usage:
        @tool(name="my_tool", description="Does something useful")
        def my_function(agent, param1: str, param2: int = 10):
            return f"Result: {param1} {param2}"
    
    Args:
        name: Tool name (defaults to function name)
        description: Tool description (defaults to docstring)
        schema: Pydantic model for input validation
        category: Tool category for organization
    """
    def decorator(func: Callable) -> Callable:
        tool_name = name or func.__name__
        tool_desc = description or func.__doc__ or "No description provided"
        
        # Auto-generate schema from function signature if not provided
        if schema is None:
            sig = inspect.signature(func)
            params = {}
            
            # Skip 'agent' parameter which is injected
            for param_name, param in sig.parameters.items():
                if param_name == 'agent':
                    continue
                
                # Get type annotation
                param_type = param.annotation if param.annotation != inspect.Parameter.empty else str
                
                # Get default value
                if param.default != inspect.Parameter.empty:
                    params[param_name] = (param_type, Field(default=param.default))
                else:
                    params[param_name] = (param_type, Field(...))
            
            # Create dynamic Pydantic model
            if params:
                tool_schema = create_model(
                    f"{tool_name.title()}Input",
                    **params
                )
            else:
                tool_schema = None
        else:
            tool_schema = schema
        
        # Register the tool
        ToolRegistry.register(
            name=tool_name,
            func=func,
            description=tool_desc,
            schema=tool_schema,
            category=category
        )
        
        # Add metadata to function
        func._tool_metadata = {
            "name": tool_name,
            "description": tool_desc,
            "schema": tool_schema,
            "category": category
        }
        
        return func
    
    return decorator


# ============================================================================
# DYNAMIC TOOL LOADER
# ============================================================================

class DynamicToolLoader:
    """Loads tools dynamically from Python files in a directory."""
    
    def __init__(self, agent, tools_directory: str = tools_dir):
        self.agent = agent
        self.tools_directory = Path(tools_directory)
        self.loaded_modules = {}
        
        # Create tools directory if it doesn't exist
        self.tools_directory.mkdir(exist_ok=True)
        
        # Create __init__.py if it doesn't exist
        init_file = self.tools_directory / "__init__.py"
        if not init_file.exists():
            init_file.touch()
    
    def discover_tools(self, pattern: str = "*.py") -> List[str]:
        """
        Discover all Python files in the tools directory.
        
        Returns:
            List of tool file names (without .py extension)
        """
        tool_files = []
        
        for file_path in self.tools_directory.glob(pattern):
            if file_path.name.startswith("_"):
                continue  # Skip private files
            
            if file_path.suffix == ".py":
                tool_files.append(file_path.stem)
        
        return sorted(tool_files)
    
    def load_tool_module(self, module_name: str) -> Any:
        """
        Dynamically load a Python module from the tools directory.
        
        Args:
            module_name: Name of the module (without .py)
        
        Returns:
            Loaded module object
        """
        if module_name in self.loaded_modules:
            return self.loaded_modules[module_name]
        
        module_path = self.tools_directory / f"{module_name}.py"
        
        if not module_path.exists():
            raise FileNotFoundError(f"Tool module not found: {module_path}")
        
        # Load the module
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Cache the module
        self.loaded_modules[module_name] = module
        
        return module
    
    def get_tool_function(self, module_name: str, function_name: str) -> Callable:
        """
        Get a specific function from a tool module.
        
        Args:
            module_name: Name of the tool module
            function_name: Name of the function in the module
        
        Returns:
            The function object
        """
        module = self.load_tool_module(module_name)
        
        if not hasattr(module, function_name):
            raise AttributeError(f"Function '{function_name}' not found in module '{module_name}'")
        
        func = getattr(module, function_name)
        
        if not callable(func):
            raise TypeError(f"'{function_name}' in module '{module_name}' is not callable")
        
        return func
    
    def call_tool_function(self, module_name: str, function_name: str, 
                          arguments: Dict[str, Any]) -> str:
        """
        Call a function from a tool module with arguments.
        
        Args:
            module_name: Name of the tool module
            function_name: Name of the function
            arguments: Dictionary of arguments to pass
        
        Returns:
            Function result as string
        """
        try:
            func = self.get_tool_function(module_name, function_name)
            
            # Check if function expects 'agent' parameter
            sig = inspect.signature(func)
            if 'agent' in sig.parameters:
                result = func(self.agent, **arguments)
            else:
                result = func(**arguments)
            
            return str(result)
            
        except Exception as e:
            return f"[Tool Execution Error] {str(e)}\n{traceback.format_exc()}"
    
    def list_tool_functions(self, module_name: str) -> List[Dict[str, Any]]:
        """
        List all functions in a tool module.
        
        Args:
            module_name: Name of the tool module
        
        Returns:
            List of function info dictionaries
        """
        module = self.load_tool_module(module_name)
        
        functions = []
        for name, obj in inspect.getmembers(module):
            if inspect.isfunction(obj) and not name.startswith('_'):
                # Get function signature
                sig = inspect.signature(obj)
                params = [
                    {
                        "name": param_name,
                        "type": str(param.annotation) if param.annotation != inspect.Parameter.empty else "Any",
                        "default": str(param.default) if param.default != inspect.Parameter.empty else None
                    }
                    for param_name, param in sig.parameters.items()
                    if param_name != 'agent'  # Skip agent parameter
                ]
                
                functions.append({
                    "name": name,
                    "docstring": obj.__doc__ or "No description",
                    "parameters": params,
                    "has_tool_decorator": hasattr(obj, '_tool_metadata')
                })
        
        return functions
    
def auto_load_decorated_tools(self, pattern: str = "*.py") -> List[StructuredTool]:
    """
    Automatically load all tools decorated with @tool from the tools directory.
    
    Args:
        pattern: File pattern to search for
    
    Returns:
        List of StructuredTool instances
    """
    tool_files = self.discover_tools(pattern)
    loaded_tools = []
    
    for module_name in tool_files:
        try:
            # Load the module (which will trigger decorator registration)
            self.load_tool_module(module_name)
        except Exception as e:
            print(f"[Warning] Failed to load tool module '{module_name}': {e}")
            continue
    
    # Convert registered tools to StructuredTool instances
    # FIX: Iterate over the registry items directly, not list_tools()
    for tool_name, tool_info in ToolRegistry._tools.items():  # FIXED
        try:
            func = tool_info["function"]
            
            # Wrap function to inject agent
            @wraps(func)
            def wrapped_func(*args, agent=self.agent, **kwargs):
                return func(agent, *args, **kwargs)
            
            # Create StructuredTool
            if tool_info["schema"]:
                structured_tool = StructuredTool.from_function(
                    func=wrapped_func,
                    name=tool_name,
                    description=tool_info["description"],
                    args_schema=tool_info["schema"]
                )
            else:
                structured_tool = StructuredTool.from_function(
                    func=wrapped_func,
                    name=tool_name,
                    description=tool_info["description"]
                )
            
            loaded_tools.append(structured_tool)
            
        except Exception as e:
            print(f"[Warning] Failed to create tool '{tool_name}': {e}")
            continue
    
    return loaded_tools
# ============================================================================
# DYNAMIC TOOLS CLASS (follows same pattern as other tools)
# ============================================================================

class DynamicTools:
    """Dynamic tool loading and management."""
    
    def __init__(self, agent, tools_directory: str = tools_dir):
        self.agent = agent
        self.loader = DynamicToolLoader(agent, tools_directory)
    
    def discover_custom_tools(self, pattern: str = "*") -> str:
        """
        Discover available custom tools in the tools directory.
        Returns a list of tool files and their functions.
        """
        try:
            tool_files = self.loader.discover_tools(f"{pattern}.py" if not pattern.endswith(".py") else pattern)
            
            if not tool_files:
                return f"No tools found matching pattern '{pattern}'"
            
            output = [f"Found {len(tool_files)} custom tool(s):\n"]
            
            for tool_name in tool_files:
                try:
                    functions = self.loader.list_tool_functions(tool_name)
                    output.append(f"\n📦 {tool_name}.py:")
                    
                    for func in functions:
                        decorator_mark = "🔧" if func["has_tool_decorator"] else "  "
                        output.append(f"  {decorator_mark} {func['name']}")
                        output.append(f"      {func['docstring'][:60]}")
                        
                        if func['parameters']:
                            params_str = ", ".join(
                                f"{p['name']}: {p['type']}" 
                                for p in func['parameters']
                            )
                            output.append(f"      Parameters: {params_str}")
                    
                except Exception as e:
                    output.append(f"  ⚠️  Error loading: {str(e)}")
            
            output.append("\n🔧 = Has @tool decorator (auto-loadable)")
            return "\n".join(output)
            
        except Exception as e:
            return f"[Error] {str(e)}"
    
    def call_custom_tool(self, tool_name: str, function_name: str, 
                        arguments: Dict[str, Any]) -> str:
        """
        Call a function from a custom tool file.
        
        Example:
            tool_name: "data_processing"
            function_name: "clean_csv"
            arguments: {"file_path": "data.csv", "remove_nulls": true}
        """
        try:
            result = self.loader.call_tool_function(
                tool_name, function_name, arguments
            )
            
            # Store in memory
            self.agent.mem.add_session_memory(
                self.agent.sess.id,
                f"Called {tool_name}.{function_name}",
                "custom_tool_call",
                {"tool": tool_name, "function": function_name, "args": arguments}
            )
            
            return result
            
        except Exception as e:
            return f"[Custom Tool Error] {str(e)}"
    
    def list_tool_functions(self, tool_name: str) -> str:
        """
        List all functions available in a custom tool file.
        """
        try:
            functions = self.loader.list_tool_functions(tool_name)
            
            output = [f"Functions in {tool_name}.py:\n"]
            
            for func in functions:
                output.append(f"\n📌 {func['name']}")
                output.append(f"   {func['docstring']}")
                
                if func['parameters']:
                    output.append("   Parameters:")
                    for param in func['parameters']:
                        default = f" = {param['default']}" if param['default'] else ""
                        output.append(f"     - {param['name']}: {param['type']}{default}")
                
                if func['has_tool_decorator']:
                    output.append("   🔧 Auto-loadable with @tool decorator")
            
            return "\n".join(output)
            
        except Exception as e:
            return f"[Error] {str(e)}"
    
    def reload_custom_tools(self) -> str:
        """
        Reload all custom tool modules (useful after editing tool files).
        """
        try:
            # Clear loaded modules cache
            self.loader.loaded_modules.clear()
            
            # Clear tool registry
            ToolRegistry.clear()
            
            # Reload all tools
            tools = self.loader.auto_load_decorated_tools()
            
            return f"✓ Reloaded {len(tools)} custom tools"
            
        except Exception as e:
            return f"[Reload Error] {str(e)}"


# ============================================================================
# INPUT SCHEMAS
# ============================================================================

class DiscoverToolsInput(BaseModel):
    """Input for discovering tools."""
    pattern: str = Field(default="*", description="Pattern to filter tools (e.g., 'data_*' or '*')")


class CallCustomToolInput(BaseModel):
    """Input for calling custom tools."""
    tool_name: str = Field(..., description="Name of the tool file (without .py)")
    function_name: str = Field(..., description="Function name to call")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments as key-value pairs")


class ListToolFunctionsInput(BaseModel):
    """Input for listing functions in a tool."""
    tool_name: str = Field(..., description="Name of the tool file (without .py)")


# ============================================================================
# ADD TO TOOLLOADER FUNCTION (follows same pattern as other integrations)
# ============================================================================

def add_dynamic_tools(tool_list: List, agent, tools_directory: str = tools_dir):
    """
    Add dynamic tool loading capabilities to the tool list.
    
    This enables:
    - Auto-discovery of tool files in the tools directory
    - Loading tools decorated with @tool decorator
    - Manual calling of any function from tool files
    - Runtime tool reloading for development
    
    Call this in your ToolLoader function:
        tool_list = ToolLoader(agent)
        add_dynamic_tools(tool_list, agent)
        return tool_list
    
    Args:
        tool_list: List to append tools to
        agent: Agent instance
        tools_directory: Path to tools directory (default: ./Pluigns)
    """
    
    dynamic_tools = DynamicTools(agent, tools_directory)
    
    # Add management tools
    tool_list.extend([
        StructuredTool.from_function(
            func=dynamic_tools.discover_custom_tools,
            name="discover_tools",
            description=(
                "Discover and list available custom tools in the tools directory. "
                "Shows functions and their parameters. "
                "Tools with 🔧 are auto-loaded via @tool decorator."
            ),
            args_schema=DiscoverToolsInput
        ),
        StructuredTool.from_function(
            func=dynamic_tools.call_custom_tool,
            name="call_custom_tool",
            description=(
                "Call a function from a custom tool file. "
                "Provide tool name, function name, and arguments. "
                "Use for tools not auto-loaded or for dynamic execution."
            ),
            args_schema=CallCustomToolInput
        ),
        StructuredTool.from_function(
            func=dynamic_tools.list_tool_functions,
            name="list_tool_functions",
            description=(
                "List all functions in a specific custom tool file with their parameters. "
                "Shows docstrings and whether functions are auto-loadable."
            ),
            args_schema=ListToolFunctionsInput
        ),
        StructuredTool.from_function(
            func=dynamic_tools.reload_custom_tools,
            name="reload_tools",
            description=(
                "Reload all custom tool modules. "
                "Use after editing tool files to pick up changes without restarting."
            ),
        ),
    ])
    
    # Auto-load decorated tools from tools directory
    try:
        auto_loaded = dynamic_tools.loader.auto_load_decorated_tools()
        if auto_loaded:
            print(f"[Info] Auto-loaded {len(auto_loaded)} custom tools with @tool decorator")
            tool_list.extend(auto_loaded)
    except Exception as e:
        print(f"[Warning] Failed to auto-load custom tools: {e}")
    
    return tool_list

