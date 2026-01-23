"""
Tool Framework Adapters - Integrate VTool with Existing Vera Code

This module provides adapters to make the VTool framework work with your
existing tools, classes, and patterns WITHOUT requiring rewrites.

Key Features:
- Wrap existing functions as VTools
- Adapt existing classes to VTool interface
- Preserve existing memory patterns
- Gradual migration support
- Backward compatibility
"""

from typing import Any, Dict, List, Optional, Iterator, Union, Type, Callable
from pydantic import BaseModel, Field, create_model
from dataclasses import dataclass
import inspect
import json
from datetime import datetime
import traceback

# Import the base framework
from tool_framework import VTool, UITool, ToolResult, ToolEntity, OutputType

# =============================================================================
# FUNCTION-TO-VTOOL ADAPTER
# =============================================================================

def function_to_vtool(
    func: Callable,
    tool_name: Optional[str] = None,
    description: Optional[str] = None,
    output_type: OutputType = OutputType.TEXT,
    create_entities: bool = True,
    entity_extractor: Optional[Callable] = None
) -> Type[VTool]:
    """
    Convert an existing function into a VTool class.
    
    Your existing function:
        def my_tool(target: str, option: int = 5) -> str:
            '''Does something'''
            result = do_work(target, option)
            return json.dumps(result)
    
    Becomes a VTool:
        MyToolVTool = function_to_vtool(
            my_tool,
            output_type=OutputType.JSON
        )
    
    Args:
        func: Your existing function
        tool_name: Tool name (defaults to function name)
        description: Tool description (defaults to docstring)
        output_type: What the tool outputs
        create_entities: Whether to auto-create entities from output
        entity_extractor: Function to extract entities from output
    
    Returns:
        VTool class that wraps your function
    """
    
    # Get function metadata
    name = tool_name or func.__name__
    desc = description or func.__doc__ or f"Tool: {name}"
    sig = inspect.signature(func)
    
    # Create Pydantic input schema from function signature
    fields = {}
    for param_name, param in sig.parameters.items():
        # Get type annotation
        param_type = param.annotation if param.annotation != inspect.Parameter.empty else str
        
        # Get default value
        if param.default != inspect.Parameter.empty:
            fields[param_name] = (param_type, Field(default=param.default, description=f"{param_name} parameter"))
        else:
            fields[param_name] = (param_type, Field(description=f"{param_name} parameter"))
    
    InputSchema = create_model(f"{name}Input", **fields)
    
    # Create VTool class
    class FunctionVTool(VTool):
        """Adapter for function-based tool"""
        
        def get_input_schema(self) -> Type[BaseModel]:
            return InputSchema
        
        def get_output_type(self) -> OutputType:
            return output_type
        
        def _execute(self, **kwargs) -> Iterator[Union[str, ToolResult]]:
            yield f"Executing {name}...\n"
            
            try:
                # Call original function
                result = func(**kwargs)
                
                # Extract entities if requested
                entities_created = []
                if create_entities and entity_extractor:
                    try:
                        entities_data = entity_extractor(result, kwargs)
                        for entity_data in entities_data:
                            entity = self.create_entity(
                                entity_data["id"],
                                entity_data["type"],
                                labels=entity_data.get("labels", []),
                                properties=entity_data.get("properties", {})
                            )
                            entities_created.append(entity)
                    except Exception as e:
                        yield f"[Warning] Entity extraction failed: {e}\n"
                
                yield f"Completed {name}\n"
                
                # Return result
                yield ToolResult(
                    success=True,
                    output=result,
                    output_type=output_type,
                    metadata={"function_name": name}
                )
                
            except Exception as e:
                error_msg = f"Function {name} failed: {str(e)}\n{traceback.format_exc()}"
                yield f"[ERROR] {error_msg}\n"
                
                yield ToolResult(
                    success=False,
                    output="",
                    output_type=output_type,
                    error=error_msg
                )
    
    FunctionVTool.__name__ = f"{name}VTool"
    FunctionVTool.__doc__ = desc
    
    return FunctionVTool


# =============================================================================
# CLASS-TO-VTOOL ADAPTER
# =============================================================================

class ClassToolAdapter(VTool):
    """
    Adapter to wrap your existing tool classes.
    
    Your existing class:
        class MyTool:
            def __init__(self, agent):
                self.agent = agent
                self.mem = agent.mem
            
            def execute(self, target: str) -> Dict:
                # Your logic
                return results
    
    Wrap it:
        class MyToolVTool(ClassToolAdapter):
            wrapped_class = MyTool
            execute_method = "execute"
            output_type = OutputType.JSON
    """
    
    wrapped_class: Type = None
    execute_method: str = "execute"
    input_schema: Optional[Type[BaseModel]] = None
    output_type: OutputType = OutputType.TEXT
    
    def __init__(self, agent):
        super().__init__(agent)
        
        # Create instance of wrapped class
        if self.wrapped_class:
            self.wrapped_instance = self.wrapped_class(agent)
        else:
            raise ValueError("wrapped_class must be set")
    
    def get_input_schema(self) -> Type[BaseModel]:
        if self.input_schema:
            return self.input_schema
        
        # Try to infer from execute method signature
        method = getattr(self.wrapped_instance, self.execute_method)
        sig = inspect.signature(method)
        
        fields = {}
        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue
            
            param_type = param.annotation if param.annotation != inspect.Parameter.empty else str
            
            if param.default != inspect.Parameter.empty:
                fields[param_name] = (param_type, Field(default=param.default))
            else:
                fields[param_name] = (param_type, Field(...))
        
        return create_model(f"{self.wrapped_class.__name__}Input", **fields)
    
    def get_output_type(self) -> OutputType:
        return self.output_type
    
    def _execute(self, **kwargs) -> Iterator[Union[str, ToolResult]]:
        yield f"Executing {self.wrapped_class.__name__}...\n"
        
        try:
            # Call wrapped class method
            method = getattr(self.wrapped_instance, self.execute_method)
            result = method(**kwargs)
            
            # If result is a generator/iterator (streaming), consume it
            if hasattr(result, '__iter__') and not isinstance(result, (str, bytes, dict, list)):
                output_parts = []
                for item in result:
                    output_parts.append(str(item))
                    yield str(item)
                
                result = ''.join(output_parts)
            
            yield ToolResult(
                success=True,
                output=result,
                output_type=self.output_type
            )
            
        except Exception as e:
            error_msg = f"{self.wrapped_class.__name__} failed: {str(e)}\n{traceback.format_exc()}"
            yield f"[ERROR] {error_msg}\n"
            
            yield ToolResult(
                success=False,
                output="",
                output_type=self.output_type,
                error=error_msg
            )


# =============================================================================
# MEMORY-AWARE ADAPTER
# =============================================================================

class MemoryAwareAdapter(VTool):
    """
    Adapter for tools that already do their own memory management.
    
    Your tool already creates entities:
        class NetworkScanner:
            def scan(self, target):
                # Creates entities directly via self.mem.upsert_entity()
                entity_id = self.mem.upsert_entity(...)
                return results
    
    Wrap it to integrate with VTool tracking:
        class NetworkScannerVTool(MemoryAwareAdapter):
            wrapped_class = NetworkScanner
            execute_method = "scan"
            
            def extract_created_entities(self, instance, result):
                # Tell VTool what entities were created
                # Access instance.created_entities or parse result
                return [
                    {"id": "ip_192_168_1_1", "type": "network_host"},
                    {"id": "ip_192_168_1_1_port_22", "type": "network_port"}
                ]
    """
    
    wrapped_class: Type = None
    execute_method: str = "execute"
    
    def __init__(self, agent):
        super().__init__(agent)
        self.wrapped_instance = self.wrapped_class(agent)
    
    def extract_created_entities(self, instance: Any, result: Any) -> List[Dict]:
        """
        Override this to tell VTool what entities your tool created.
        
        Returns list of dicts with:
            {"id": "entity_id", "type": "entity_type", "labels": [...], "properties": {...}}
        """
        return []
    
    def get_input_schema(self) -> Type[BaseModel]:
        # Infer from wrapped method
        method = getattr(self.wrapped_instance, self.execute_method)
        sig = inspect.signature(method)
        
        fields = {}
        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue
            
            param_type = param.annotation if param.annotation != inspect.Parameter.empty else str
            
            if param.default != inspect.Parameter.empty:
                fields[param_name] = (param_type, Field(default=param.default))
            else:
                fields[param_name] = (param_type, Field(...))
        
        return create_model(f"{self.wrapped_class.__name__}Input", **fields)
    
    def get_output_type(self) -> OutputType:
        return OutputType.JSON
    
    def _execute(self, **kwargs) -> Iterator[Union[str, ToolResult]]:
        yield f"Executing {self.wrapped_class.__name__}...\n"
        
        try:
            # Call wrapped method
            method = getattr(self.wrapped_instance, self.execute_method)
            result = method(**kwargs)
            
            # Handle streaming
            if hasattr(result, '__iter__') and not isinstance(result, (str, bytes, dict, list)):
                output_parts = []
                for item in result:
                    output_parts.append(str(item))
                    yield str(item)
                result = ''.join(output_parts)
            
            # Extract entities that were created
            try:
                entities_data = self.extract_created_entities(self.wrapped_instance, result)
                
                for entity_data in entities_data:
                    # Create ToolEntity to track them
                    entity = ToolEntity(
                        id=entity_data["id"],
                        type=entity_data["type"],
                        labels=entity_data.get("labels", []),
                        properties=entity_data.get("properties", {}),
                        metadata={"reused": True}  # Already created by wrapped tool
                    )
                    self.created_entities.append(entity)
                
            except Exception as e:
                yield f"[Warning] Entity extraction failed: {e}\n"
            
            yield ToolResult(
                success=True,
                output=result,
                output_type=self.get_output_type()
            )
            
        except Exception as e:
            yield ToolResult(
                success=False,
                output="",
                output_type=self.get_output_type(),
                error=str(e)
            )


# =============================================================================
# LANGCHAIN TOOL ADAPTER
# =============================================================================

def langchain_to_vtool(langchain_tool) -> Type[VTool]:
    """
    Convert a LangChain StructuredTool to VTool.
    
    Your existing LangChain tool:
        tool = StructuredTool.from_function(
            func=my_function,
            name="my_tool",
            description="Does something"
        )
    
    Convert it:
        MyToolVTool = langchain_to_vtool(tool)
    """
    
    name = langchain_tool.name
    description = langchain_tool.description
    
    # Get input schema
    if hasattr(langchain_tool, 'args_schema') and langchain_tool.args_schema:
        InputSchema = langchain_tool.args_schema
    else:
        # Create simple schema
        InputSchema = create_model(
            f"{name}Input",
            input=(str, Field(description="Input"))
        )
    
    class LangChainVTool(VTool):
        """Adapter for LangChain tool"""
        
        def get_input_schema(self) -> Type[BaseModel]:
            return InputSchema
        
        def get_output_type(self) -> OutputType:
            return OutputType.TEXT
        
        def _execute(self, **kwargs) -> Iterator[Union[str, ToolResult]]:
            yield f"Executing {name}...\n"
            
            try:
                # Call LangChain tool
                result = langchain_tool.run(kwargs)
                
                yield ToolResult(
                    success=True,
                    output=result,
                    output_type=OutputType.TEXT
                )
                
            except Exception as e:
                yield ToolResult(
                    success=False,
                    output="",
                    output_type=OutputType.TEXT,
                    error=str(e)
                )
    
    LangChainVTool.__name__ = f"{name}VTool"
    LangChainVTool.__doc__ = description
    
    return LangChainVTool


# =============================================================================
# MIXED TOOL LOADER (Works with both old and new)
# =============================================================================

class MixedToolLoader:
    """
    Tool loader that supports both legacy and VTool-based tools.
    
    Usage:
        loader = MixedToolLoader(agent)
        
        # Add legacy function
        loader.add_function(my_old_function, output_type=OutputType.JSON)
        
        # Add legacy class
        loader.add_class(MyOldClass, execute_method="run")
        
        # Add VTool
        loader.add_vtool(MyNewVTool)
        
        # Add existing LangChain tool
        loader.add_langchain(existing_langchain_tool)
        
        # Get final list
        tools = loader.get_tools()
    """
    
    def __init__(self, agent):
        self.agent = agent
        self.tools: List = []
    
    def add_function(
        self,
        func: Callable,
        tool_name: Optional[str] = None,
        output_type: OutputType = OutputType.TEXT,
        entity_extractor: Optional[Callable] = None
    ):
        """Add a function-based tool"""
        VToolClass = function_to_vtool(
            func,
            tool_name=tool_name,
            output_type=output_type,
            entity_extractor=entity_extractor
        )
        
        tool_instance = VToolClass(self.agent)
        self.tools.append(tool_instance)
        
        return tool_instance
    
    def add_class(
        self,
        cls: Type,
        execute_method: str = "execute",
        input_schema: Optional[Type[BaseModel]] = None,
        output_type: OutputType = OutputType.TEXT
    ):
        """Add a class-based tool"""
        
        class WrappedTool(ClassToolAdapter):
            wrapped_class = cls
            
        WrappedTool.execute_method = execute_method
        WrappedTool.input_schema = input_schema
        WrappedTool.output_type = output_type
        
        tool_instance = WrappedTool(self.agent)
        self.tools.append(tool_instance)
        
        return tool_instance
    
    def add_memory_aware_class(
        self,
        cls: Type,
        execute_method: str = "execute",
        entity_extractor: Optional[Callable] = None
    ):
        """Add a class that already does memory management"""
        
        class WrappedMemoryTool(MemoryAwareAdapter):
            wrapped_class = cls
        
        WrappedMemoryTool.execute_method = execute_method
        
        if entity_extractor:
            WrappedMemoryTool.extract_created_entities = lambda self, instance, result: entity_extractor(instance, result)
        
        tool_instance = WrappedMemoryTool(self.agent)
        self.tools.append(tool_instance)
        
        return tool_instance
    
    def add_vtool(self, vtool_class: Type[VTool]):
        """Add a VTool class"""
        tool_instance = vtool_class(self.agent)
        self.tools.append(tool_instance)
        return tool_instance
    
    def add_langchain(self, langchain_tool):
        """Add an existing LangChain StructuredTool"""
        VToolClass = langchain_to_vtool(langchain_tool)
        tool_instance = VToolClass(self.agent)
        self.tools.append(tool_instance)
        return tool_instance
    
    def get_tools(self) -> List[VTool]:
        """Get all tools as VTool instances"""
        return self.tools
    
    def get_langchain_tools(self) -> List:
        """Get tools as LangChain StructuredTools"""
        from tool_framework import vtool_to_langchain
        return [vtool_to_langchain(tool) for tool in self.tools]


# =============================================================================
# BACKWARD COMPATIBILITY LAYER
# =============================================================================

def preserve_existing_behavior(agent):
    """
    Add this to your agent to preserve existing behavior while gaining VTool benefits.
    
    In Vera.__init__:
        from tool_framework_adapters import preserve_existing_behavior
        preserve_existing_behavior(self)
    """
    
    # Wrap existing memory methods to integrate with VTool tracking
    original_upsert = agent.mem.upsert_entity
    
    def tracked_upsert(entity_id: str, etype: str, labels=None, properties=None):
        """Wrapped upsert that also creates ToolEntity if in execution context"""
        result = original_upsert(entity_id, etype, labels, properties)
        
        # If we're in a VTool execution context, track it
        if hasattr(agent, '_current_vtool_execution'):
            current_tool = agent._current_vtool_execution
            if current_tool:
                entity = ToolEntity(
                    id=entity_id,
                    type=etype,
                    labels=labels or [],
                    properties=properties or {},
                    metadata={"tracked_from_legacy": True}
                )
                current_tool.created_entities.append(entity)
        
        return result
    
    agent.mem.upsert_entity = tracked_upsert
    
    return agent


# =============================================================================
# MIGRATION HELPERS
# =============================================================================

def analyze_existing_tool(tool_or_func) -> Dict[str, Any]:
    """
    Analyze an existing tool/function and suggest VTool migration strategy.
    
    Usage:
        analysis = analyze_existing_tool(my_function)
        print(analysis["recommendation"])
        print(analysis["adapter_code"])
    """
    
    info = {
        "type": None,
        "name": None,
        "is_async": False,
        "has_streaming": False,
        "creates_entities": False,
        "recommendation": "",
        "adapter_code": ""
    }
    
    # Determine type
    if inspect.isfunction(tool_or_func):
        info["type"] = "function"
        info["name"] = tool_or_func.__name__
        info["is_async"] = inspect.iscoroutinefunction(tool_or_func)
        
        # Check for streaming
        source = inspect.getsource(tool_or_func)
        info["has_streaming"] = "yield" in source
        info["creates_entities"] = "upsert_entity" in source or "create_entity" in source
        
        # Recommendation
        if info["creates_entities"]:
            info["recommendation"] = "Use function_to_vtool with entity_extractor"
            info["adapter_code"] = f"""
def extract_entities(result, inputs):
    # Parse result and return entity data
    return [
        {{"id": "...", "type": "...", "labels": [], "properties": {{}}}}
    ]

{info["name"]}_vtool = function_to_vtool(
    {info["name"]},
    output_type=OutputType.JSON,  # Adjust as needed
    entity_extractor=extract_entities
)
"""
        else:
            info["recommendation"] = "Use simple function_to_vtool"
            info["adapter_code"] = f"""
{info["name"]}_vtool = function_to_vtool(
    {info["name"]},
    output_type=OutputType.TEXT  # Adjust as needed
)
"""
    
    elif inspect.isclass(tool_or_func):
        info["type"] = "class"
        info["name"] = tool_or_func.__name__
        
        # Check for common methods
        has_execute = hasattr(tool_or_func, 'execute')
        has_run = hasattr(tool_or_func, 'run')
        
        execute_method = 'execute' if has_execute else ('run' if has_run else None)
        
        if execute_method:
            info["recommendation"] = "Use ClassToolAdapter"
            info["adapter_code"] = f"""
class {info["name"]}VTool(ClassToolAdapter):
    wrapped_class = {info["name"]}
    execute_method = "{execute_method}"
    output_type = OutputType.JSON  # Adjust as needed
"""
        else:
            info["recommendation"] = "Manual VTool implementation recommended"
            info["adapter_code"] = f"""
class {info["name"]}VTool(VTool):
    def __init__(self, agent):
        super().__init__(agent)
        self.wrapped = {info["name"]}(agent)
    
    def get_input_schema(self):
        # Define input schema
        class Input(BaseModel):
            target: str = Field(description="Target")
        return Input
    
    def get_output_type(self):
        return OutputType.JSON
    
    def _execute(self, **kwargs):
        # Call wrapped class methods
        result = self.wrapped.some_method(**kwargs)
        yield ToolResult(success=True, output=result, output_type=OutputType.JSON)
"""
    
    return info


# =============================================================================
# USAGE EXAMPLES
# =============================================================================

"""
# Example 1: Convert existing function
def old_network_scan(target: str, ports: str = "1-1000") -> str:
    '''Scans network'''
    # ... existing logic ...
    return json.dumps(results)

# Wrap it:
NetworkScanVTool = function_to_vtool(
    old_network_scan,
    output_type=OutputType.JSON
)

# Use it:
tool = NetworkScanVTool(agent)
for item in tool.execute(target="192.168.1.0/24"):
    print(item)


# Example 2: Convert existing class
class OldPortScanner:
    def __init__(self, agent):
        self.agent = agent
        self.mem = agent.mem
    
    def scan(self, host: str, ports: List[int]):
        # ... existing logic ...
        return results

# Wrap it:
class PortScannerVTool(ClassToolAdapter):
    wrapped_class = OldPortScanner
    execute_method = "scan"
    output_type = OutputType.JSON


# Example 3: Memory-aware tool
class OldHostDiscovery:
    def __init__(self, agent):
        self.mem = agent.mem
        self.discovered = []
    
    def discover(self, network: str):
        for host in scan_network(network):
            entity_id = self.mem.upsert_entity(
                f"ip_{host}",
                "network_host",
                properties={"ip": host}
            )
            self.discovered.append(entity_id)
        return self.discovered

# Wrap it:
class HostDiscoveryVTool(MemoryAwareAdapter):
    wrapped_class = OldHostDiscovery
    execute_method = "discover"
    
    def extract_created_entities(self, instance, result):
        return [
            {"id": entity_id, "type": "network_host"}
            for entity_id in instance.discovered
        ]


# Example 4: Mixed tool loader
loader = MixedToolLoader(agent)

# Add all your existing tools without changing them
loader.add_function(old_network_scan, output_type=OutputType.JSON)
loader.add_class(OldPortScanner, execute_method="scan")
loader.add_memory_aware_class(OldHostDiscovery, execute_method="discover")

# Add new VTools
loader.add_vtool(NewVToolClass)

# Get unified list
tools = loader.get_langchain_tools()  # For LangChain
# or
tools = loader.get_tools()  # As VTool instances


# Example 5: Analyze existing tool
analysis = analyze_existing_tool(my_old_function)
print(analysis["recommendation"])
print(analysis["adapter_code"])
# Outputs ready-to-use adapter code!
"""