"""
Vera Tool Framework - Standardized Tool Implementation
Provides base classes and utilities for creating interoperable, memory-aware tools.

Features:
- Automatic memory entity creation and linking
- Streaming and non-streaming support
- Type-based tool interoperability
- Standardized input/output handling
- Hierarchical result linking (like network scanner)
- Tool chaining support (like toolchain)
"""

from typing import Any, Dict, List, Optional, Iterator, Union, Type, TypeVar, Generic
from pydantic import BaseModel, Field, create_model
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from enum import Enum
import json
import time
import traceback
from datetime import datetime
from langchain.tools import StructuredTool

# =============================================================================
# TYPE DEFINITIONS
# =============================================================================

class OutputType(str, Enum):
    """Standard output types for tool interoperability"""
    TEXT = "text"
    JSON = "json"
    IP_LIST = "ip_list"
    PORT_LIST = "port_list"
    SERVICE_LIST = "service_list"
    VULNERABILITY_LIST = "vulnerability_list"
    FILE_PATH = "file_path"
    URL = "url"
    ENTITY_ID = "entity_id"
    SUBGRAPH = "subgraph"
    SEARCH_RESULTS = "search_results"
    CODE = "code"
    COMMAND_OUTPUT = "command_output"

T = TypeVar('T')

# =============================================================================
# RESULT CLASSES
# =============================================================================

@dataclass
class ToolEntity:
    """Represents an entity created/discovered by a tool"""
    id: str
    type: str
    labels: List[str] = field(default_factory=list)
    properties: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ToolRelationship:
    """Represents a relationship between entities"""
    source_id: str
    target_id: str
    rel_type: str
    properties: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ToolResult:
    """Standardized tool execution result"""
    
    # Core result data
    success: bool
    output: Any
    output_type: OutputType
    
    # Memory artifacts
    entities: List[ToolEntity] = field(default_factory=list)
    relationships: List[ToolRelationship] = field(default_factory=list)
    
    # Metadata
    tool_name: str = ""
    execution_time: float = 0.0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # For chaining
    intermediate_results: Dict[str, Any] = field(default_factory=dict)
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps({
            "success": self.success,
            "output": self.output,
            "output_type": self.output_type,
            "tool_name": self.tool_name,
            "execution_time": self.execution_time,
            "error": self.error,
            "entities_created": len(self.entities),
            "relationships_created": len(self.relationships),
            "metadata": self.metadata
        }, indent=2, default=str)
    
    def get_entity_ids(self) -> List[str]:
        """Get all created entity IDs"""
        return [e.id for e in self.entities]
    
    def get_output_for_chaining(self) -> Any:
        """Get output formatted for chaining to next tool"""
        if self.output_type == OutputType.ENTITY_ID:
            return self.get_entity_ids()[0] if self.entities else None
        elif self.output_type in [OutputType.IP_LIST, OutputType.PORT_LIST]:
            return self.output
        else:
            return str(self.output)

# =============================================================================
# BASE TOOL CLASS
# =============================================================================

class VTool(ABC, Generic[T]):
    """
    Base class for all Vera tools.
    
    Provides:
    - Automatic memory operations
    - Streaming support
    - Entity creation and linking
    - Standardized error handling
    - Tool chaining support
    """
    
    def __init__(self, agent):
        """
        Initialize tool with agent reference.
        
        Args:
            agent: Vera agent instance with .mem, .sess, etc.
        """
        self.agent = agent
        self.mem = agent.mem
        self.sess = agent.sess
        
        # Tool metadata
        self.tool_name = self.__class__.__name__
        self.execution_node_id: Optional[str] = None
        
        # Track created entities
        self.created_entities: List[ToolEntity] = []
        self.created_relationships: List[ToolRelationship] = []
        
        # Timing
        self.start_time: float = 0.0
    
    # -------------------------------------------------------------------------
    # ABSTRACT METHODS - Implement these in subclasses
    # -------------------------------------------------------------------------
    
    @abstractmethod
    def _execute(self, **kwargs) -> Iterator[Union[str, ToolResult]]:
        """
        Execute the tool logic.
        
        Must yield:
        - Strings for streaming output
        - Final ToolResult at the end
        
        Example:
            yield "Processing...\n"
            yield f"Found {count} results\n"
            yield ToolResult(
                success=True,
                output=results,
                output_type=OutputType.JSON
            )
        """
        pass
    
    @abstractmethod
    def get_input_schema(self) -> Type[BaseModel]:
        """Return Pydantic model for tool inputs"""
        pass
    
    @abstractmethod
    def get_output_type(self) -> OutputType:
        """Return the output type this tool produces"""
        pass
    
    # -------------------------------------------------------------------------
    # TOOL EXECUTION
    # -------------------------------------------------------------------------
    
    def execute(self, **kwargs) -> Iterator[Union[str, ToolResult]]:
        """
        Execute tool with automatic memory management.
        
        Wraps _execute with:
        - Execution tracking
        - Memory operations
        - Error handling
        - Timing
        """
        self.start_time = time.time()
        self.created_entities = []
        self.created_relationships = []
        
        try:
            # Initialize execution context
            self._initialize_execution(**kwargs)
            
            # Execute tool logic (yields strings and final ToolResult)
            result = None
            for item in self._execute(**kwargs):
                if isinstance(item, ToolResult):
                    result = item
                    # Don't yield yet - we need to process it first
                else:
                    # Stream intermediate output
                    yield item
            
            # Process final result
            if result is None:
                result = ToolResult(
                    success=False,
                    output="Tool did not return a result",
                    output_type=self.get_output_type(),
                    error="Missing result"
                )
            
            # Add metadata
            result.tool_name = self.tool_name
            result.execution_time = time.time() - self.start_time
            result.entities = self.created_entities
            result.relationships = self.created_relationships
            
            # Store in memory
            self._finalize_execution(result, **kwargs)
            
            # Yield final result
            yield result
            
        except Exception as e:
            error_msg = f"Tool execution failed: {str(e)}\n{traceback.format_exc()}"
            
            result = ToolResult(
                success=False,
                output="",
                output_type=self.get_output_type(),
                tool_name=self.tool_name,
                execution_time=time.time() - self.start_time,
                error=error_msg
            )
            
            yield f"[ERROR] {error_msg}\n"
            yield result
    
    # -------------------------------------------------------------------------
    # MEMORY OPERATIONS
    # -------------------------------------------------------------------------
    
    def _initialize_execution(self, **kwargs):
        """Initialize execution tracking in memory"""
        # Create execution node (like NetworkMapper._initialize_scan)
        exec_mem = self.mem.add_session_memory(
            self.sess.id,
            json.dumps(kwargs, default=str),
            f"{self.tool_name}_execution",
            metadata={
                "tool": self.tool_name,
                "started_at": datetime.now().isoformat(),
                "inputs": kwargs
            }
        )
        
        self.execution_node_id = exec_mem.id
        
        # Link to toolchain step if in toolchain context
        if hasattr(self.agent, 'toolchain'):
            if hasattr(self.agent.toolchain, 'current_plan_id'):
                plan_id = self.agent.toolchain.current_plan_id
                step_num = getattr(self.agent.toolchain, 'current_step_num', 0)
                step_node_id = f"step_{plan_id}_{step_num}"
                
                try:
                    self.mem.link(step_node_id, self.execution_node_id, "EXECUTES")
                except:
                    pass
    
    def _finalize_execution(self, result: ToolResult, **kwargs):
        """Finalize execution and store all results in memory"""
        # Create all discovered entities in graph
        for entity in result.entities:
            try:
                self.mem.upsert_entity(
                    entity.id,
                    entity.type,
                    labels=entity.labels,
                    properties=entity.properties
                )
                
                # Link to execution
                if self.execution_node_id:
                    self.mem.link(
                        self.execution_node_id,
                        entity.id,
                        "CREATED",
                        entity.metadata
                    )
            except Exception as e:
                print(f"[Warning] Failed to create entity {entity.id}: {e}")
        
        # Create all relationships
        for rel in result.relationships:
            try:
                self.mem.link(
                    rel.source_id,
                    rel.target_id,
                    rel.rel_type,
                    rel.properties
                )
            except Exception as e:
                print(f"[Warning] Failed to create relationship: {e}")
        
        # Store result as document
        if result.success and result.output:
            output_str = str(result.output)
            if len(output_str) > 100:  # Only store substantial output
                self.mem.attach_document(
                    self.sess.id,
                    f"{self.tool_name}_output",
                    output_str,
                    {
                        "tool": self.tool_name,
                        "output_type": result.output_type,
                        "execution_id": self.execution_node_id
                    }
                )
        
        # Update execution node with results
        try:
            with self.mem.graph._driver.session() as sess:
                sess.run("""
                    MATCH (exec {id: $exec_id})
                    SET exec.success = $success,
                        exec.execution_time = $exec_time,
                        exec.entities_created = $entity_count,
                        exec.completed_at = $completed_at
                """, {
                    "exec_id": self.execution_node_id,
                    "success": result.success,
                    "exec_time": result.execution_time,
                    "entity_count": len(result.entities),
                    "completed_at": datetime.now().isoformat()
                })
        except:
            pass
    
    # -------------------------------------------------------------------------
    # ENTITY CREATION HELPERS
    # -------------------------------------------------------------------------
    
    def create_entity(self, entity_id: str, entity_type: str,
                     labels: Optional[List[str]] = None,
                     properties: Optional[Dict] = None,
                     metadata: Optional[Dict] = None,
                     reuse_if_exists: bool = True) -> ToolEntity:
        """
        Create an entity and track it.
        
        Args:
            entity_id: Unique entity identifier
            entity_type: Entity type
            labels: Neo4j labels
            properties: Entity properties
            metadata: Metadata for linking
            reuse_if_exists: If True, reuse existing entity
        
        Returns:
            ToolEntity instance
        """
        entity = ToolEntity(
            id=entity_id,
            type=entity_type,
            labels=labels or [entity_type],
            properties=properties or {},
            metadata=metadata or {}
        )
        
        # Check if already exists
        if reuse_if_exists:
            try:
                subgraph = self.mem.extract_subgraph([entity_id], depth=0)
                if any(n.get("id") == entity_id for n in subgraph.get("nodes", [])):
                    # Entity exists - just track it
                    entity.metadata["reused"] = True
                    self.created_entities.append(entity)
                    return entity
            except:
                pass
        
        # New entity
        entity.properties["created_at"] = datetime.now().isoformat()
        entity.properties["created_by"] = self.tool_name
        
        self.created_entities.append(entity)
        return entity
    
    def link_entities(self, source_id: str, target_id: str, rel_type: str,
                     properties: Optional[Dict] = None) -> ToolRelationship:
        """
        Create a relationship between entities.
        
        Args:
            source_id: Source entity ID
            target_id: Target entity ID  
            rel_type: Relationship type
            properties: Relationship properties
        
        Returns:
            ToolRelationship instance
        """
        rel = ToolRelationship(
            source_id=source_id,
            target_id=target_id,
            rel_type=rel_type,
            properties=properties or {}
        )
        
        self.created_relationships.append(rel)
        return rel
    
    # -------------------------------------------------------------------------
    # UTILITY METHODS
    # -------------------------------------------------------------------------
    
    def format_output(self, data: Any, truncate: int = 5000) -> str:
        """Format output for display"""
        if isinstance(data, (dict, list)):
            output = json.dumps(data, indent=2, default=str)
        else:
            output = str(data)
        
        if len(output) > truncate:
            return output[:truncate] + f"\n... [truncated {len(output) - truncate} characters]"
        return output
    
    def get_description(self) -> str:
        """Get tool description (override in subclass for custom description)"""
        return f"{self.tool_name}: {self.__doc__ or 'No description'}"

# =============================================================================
# TOOL CHAINING SUPPORT
# =============================================================================

class ToolChain:
    """
    Manages tool chaining based on input/output types.
    """
    
    def __init__(self, agent):
        self.agent = agent
        self.tools: Dict[str, VTool] = {}
        self.type_producers: Dict[OutputType, List[str]] = {}
        self.type_consumers: Dict[OutputType, List[str]] = {}
    
    def register_tool(self, tool: VTool):
        """Register a tool for chaining"""
        self.tools[tool.tool_name] = tool
        
        # Track what types this tool produces
        output_type = tool.get_output_type()
        if output_type not in self.type_producers:
            self.type_producers[output_type] = []
        self.type_producers[output_type].append(tool.tool_name)
        
        # Track what types this tool consumes (from input schema)
        # This would require analyzing the input schema
        # For now, we'll do this manually or via hints
    
    def find_compatible_tools(self, output_type: OutputType) -> List[str]:
        """Find tools that can consume this output type"""
        return self.type_consumers.get(output_type, [])
    
    def find_producer_tools(self, output_type: OutputType) -> List[str]:
        """Find tools that produce this output type"""
        return self.type_producers.get(output_type, [])
    
    def can_chain(self, tool1_name: str, tool2_name: str) -> bool:
        """Check if tool1 output can feed into tool2 input"""
        if tool1_name not in self.tools or tool2_name not in self.tools:
            return False
        
        tool1_output = self.tools[tool1_name].get_output_type()
        # Would need to check tool2 input requirements
        # For now, simplified
        return tool2_name in self.type_consumers.get(tool1_output, [])
