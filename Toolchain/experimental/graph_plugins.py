"""
Graph Plugin Manager for Vera
Loads graph-specific plugins and exposes them as LangChain tools.

Dynamically reloads plugins if they change.
- GraphPluginBase: Base class for all graph plugins
- GraphPluginManager: Loads and manages plugins
- add_graph_plugin_tools(): Integrates with Vera's tool system
"""

import importlib
import importlib.util
import os
import sys
import glob
import inspect
import threading
import traceback
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Type, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool

# ============================================================================
# PLUGIN BASE CLASSES
# ============================================================================

class NodeType(str, Enum):
    """Standard node types for graph operations."""
    ENTITY = "Entity"
    CONCEPT = "Concept"
    DOCUMENT = "Document"
    CODE = "Code"
    TASK = "Task"
    MEMORY = "Memory"
    SESSION = "Session"
    TOOL_RESULT = "ToolResult"
    ANY = "*"  # Matches any type


@dataclass
class PluginResult:
    """Standardized result from plugin execution."""
    success: bool
    data: Any = None
    error: Optional[str] = None
    nodes_created: List[str] = field(default_factory=list)
    nodes_modified: List[str] = field(default_factory=list)
    relationships_created: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "nodes_created": self.nodes_created,
            "nodes_modified": self.nodes_modified,
            "relationships_created": self.relationships_created,
            "metadata": self.metadata
        }
    
    def __str__(self) -> str:
        if not self.success:
            return f"[Plugin Error] {self.error}"
        
        parts = []
        if self.data:
            parts.append(str(self.data))
        if self.nodes_created:
            parts.append(f"Created {len(self.nodes_created)} nodes")
        if self.relationships_created:
            parts.append(f"Created {len(self.relationships_created)} relationships")
        
        return "\n".join(parts) if parts else "[Success - no output]"


class GraphPluginBase(ABC):
    """
    Base class for all graph plugins.
    
    Plugins extend Neo4j graph capabilities with specialized operations.
    Each plugin declares which node types it operates on and provides
    an execute method that performs the graph operation.
    
    Example:
        class EntityExtractor(GraphPluginBase):
            @staticmethod
            def name() -> str:
                return "entity_extractor"
            
            @staticmethod
            def description() -> str:
                return "Extract entities from text and add to graph"
            
            @staticmethod
            def node_types() -> List[NodeType]:
                return [NodeType.DOCUMENT, NodeType.MEMORY]
            
            def execute(self, node_id: str, **kwargs) -> PluginResult:
                # Extract entities and create nodes/relationships
                ...
    """
    
    def __init__(self, graph_manager, memory_manager=None, agent=None):
        """
        Initialize plugin with graph access.
        
        Args:
            graph_manager: Neo4j graph manager instance
            memory_manager: Optional memory system for context
            agent: Optional agent instance for LLM access
        """
        self.graph = graph_manager
        self.memory = memory_manager
        self.agent = agent
        self._initialized = True
    
    @staticmethod
    @abstractmethod
    def name() -> str:
        """Unique identifier for this plugin."""
        raise NotImplementedError
    
    @staticmethod
    @abstractmethod
    def description() -> str:
        """Human-readable description of plugin functionality."""
        raise NotImplementedError
    
    @staticmethod
    @abstractmethod
    def node_types() -> List[NodeType]:
        """List of node types this plugin can operate on."""
        raise NotImplementedError
    
    @staticmethod
    def input_schema() -> Optional[Type[BaseModel]]:
        """
        Optional Pydantic schema for plugin inputs.
        Override to provide structured input validation.
        """
        return None
    
    @staticmethod
    def requires_llm() -> bool:
        """Whether this plugin needs LLM access."""
        return False
    
    @abstractmethod
    def execute(self, node_id: Optional[str] = None, **kwargs) -> PluginResult:
        """
        Execute the plugin operation.
        
        Args:
            node_id: Optional target node ID
            **kwargs: Additional parameters
        
        Returns:
            PluginResult with operation outcome
        """
        raise NotImplementedError
    
    def validate(self) -> bool:
        """
        Validate plugin is properly configured.
        Override for custom validation logic.
        """
        return self._initialized and self.graph is not None
    
    # Helper methods for common graph operations
    
    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a node by ID from the graph."""
        try:
            result = self.graph.driver.execute_query(
                "MATCH (n) WHERE elementId(n) = $id RETURN n",
                {"id": node_id}
            )
            if result.records:
                return dict(result.records[0]["n"])
            return None
        except Exception:
            return None
    
    def create_node(self, labels: List[str], properties: Dict[str, Any]) -> Optional[str]:
        """Create a new node and return its ID."""
        try:
            labels_str = ":".join(labels)
            result = self.graph.driver.execute_query(
                f"CREATE (n:{labels_str} $props) RETURN elementId(n) as id",
                {"props": properties}
            )
            if result.records:
                return result.records[0]["id"]
            return None
        except Exception:
            return None
    
    def create_relationship(self, from_id: str, to_id: str, 
                           rel_type: str, properties: Dict[str, Any] = None) -> bool:
        """Create a relationship between two nodes."""
        try:
            props = properties or {}
            self.graph.driver.execute_query(
                f"""
                MATCH (a), (b) 
                WHERE elementId(a) = $from_id AND elementId(b) = $to_id
                CREATE (a)-[r:{rel_type} $props]->(b)
                """,
                {"from_id": from_id, "to_id": to_id, "props": props}
            )
            return True
        except Exception:
            return False
    
    def update_node(self, node_id: str, properties: Dict[str, Any]) -> bool:
        """Update properties on an existing node."""
        try:
            self.graph.driver.execute_query(
                "MATCH (n) WHERE elementId(n) = $id SET n += $props",
                {"id": node_id, "props": properties}
            )
            return True
        except Exception:
            return False
    
    def run_cypher(self, query: str, params: Dict[str, Any] = None) -> List[Dict]:
        """Execute arbitrary Cypher query."""
        try:
            result = self.graph.driver.execute_query(query, params or {})
            return [dict(record) for record in result.records]
        except Exception as e:
            return [{"error": str(e)}]


# ============================================================================
# PLUGIN MANAGER
# ============================================================================

class PluginChangeHandler(FileSystemEventHandler):
    """Watches plugin directory for changes."""
    
    def __init__(self, manager: 'GraphPluginManager'):
        self.manager = manager
    
    def on_modified(self, event):
        if event.src_path.endswith(".py"):
            module_name = os.path.splitext(os.path.basename(event.src_path))[0]
            self.manager.reload_plugin(module_name)
    
    def on_created(self, event):
        if event.src_path.endswith(".py"):
            self.manager.load_plugin(event.src_path)


class GraphPluginManager:
    """
    Manages graph plugins with hot-reloading support.
    
    Loads plugins from a directory, watches for changes,
    and provides methods to execute plugins as tools.
    """
    
    def __init__(self, graph_manager, memory_manager=None, agent=None,
                 plugins_dir: str = "graph_plugins"):
        """
        Initialize plugin manager.
        
        Args:
            graph_manager: Neo4j graph manager
            memory_manager: Optional memory system
            agent: Optional agent for LLM access
            plugins_dir: Directory to load plugins from
        """
        self.graph_manager = graph_manager
        self.memory_manager = memory_manager
        self.agent = agent
        self.plugins_dir = plugins_dir
        
        # Plugin storage
        self.plugins: Dict[str, GraphPluginBase] = {}
        self.plugin_modules: Dict[str, Any] = {}
        self.actions_by_type: Dict[str, List[Dict[str, str]]] = {}
        
        # Watcher
        self._observer: Optional[Observer] = None
        self._watcher_thread: Optional[threading.Thread] = None
        self._running = False
        
        # Logging callback
        self.log_callback: Optional[Callable[[str, str], None]] = None
    
    def _log(self, message: str, level: str = "info"):
        """Log a message using callback or print."""
        if self.log_callback:
            self.log_callback(message, level)
        else:
            prefix = {"error": "❌", "ok": "✓", "info": "ℹ"}.get(level, "•")
            print(f"{prefix} {message}")
    
    def start(self, watch: bool = True):
        """
        Start the plugin manager.
        
        Args:
            watch: Whether to watch for file changes
        """
        # Ensure plugins directory exists
        os.makedirs(self.plugins_dir, exist_ok=True)
        
        # Load all plugins
        self.load_all_plugins()
        
        # Start watcher if requested
        if watch:
            self.start_watcher()
        
        self._running = True
        self._log(f"Plugin manager started with {len(self.plugins)} plugins", "ok")
    
    def stop(self):
        """Stop the plugin manager and cleanup."""
        self._running = False
        
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=2)
            self._observer = None
        
        self._log("Plugin manager stopped", "info")
    
    def load_all_plugins(self):
        """Load all plugins from the plugins directory."""
        pattern = os.path.join(self.plugins_dir, "*.py")
        
        for filepath in glob.glob(pattern):
            if os.path.basename(filepath).startswith("_"):
                continue  # Skip __init__.py, etc.
            self.load_plugin(filepath)
        
        self._rebuild_action_index()
    
    def load_plugin(self, filepath: str) -> bool:
        """
        Load a single plugin from file.
        
        Args:
            filepath: Path to plugin Python file
        
        Returns:
            True if plugin loaded successfully
        """
        module_name = os.path.splitext(os.path.basename(filepath))[0]
        
        try:
            # Load module
            spec = importlib.util.spec_from_file_location(
                f"graph_plugins.{module_name}", filepath
            )
            module = importlib.util.module_from_spec(spec)
            sys.modules[f"graph_plugins.{module_name}"] = module
            spec.loader.exec_module(module)
            
            # Find plugin classes
            loaded_any = False
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and 
                    issubclass(obj, GraphPluginBase) and 
                    obj != GraphPluginBase):
                    
                    try:
                        # Instantiate plugin
                        instance = obj(
                            self.graph_manager,
                            self.memory_manager,
                            self.agent
                        )
                        
                        plugin_name = instance.name()
                        self.plugins[plugin_name] = instance
                        self.plugin_modules[plugin_name] = module
                        
                        self._log(f"Loaded plugin: {plugin_name}", "ok")
                        loaded_any = True
                        
                    except Exception as e:
                        self._log(f"Error instantiating {name}: {e}", "error")
            
            if loaded_any:
                self._rebuild_action_index()
            
            return loaded_any
            
        except Exception as e:
            self._log(f"Error loading {module_name}: {e}", "error")
            return False
    
    def reload_plugin(self, module_name: str):
        """Reload a plugin module."""
        # Find plugins from this module
        to_remove = [
            name for name, plugin in self.plugins.items()
            if self.plugin_modules.get(name).__name__.endswith(module_name)
        ]
        
        # Remove old plugins
        for name in to_remove:
            del self.plugins[name]
            del self.plugin_modules[name]
            self._log(f"Unloaded plugin: {name}", "info")
        
        # Reload
        filepath = os.path.join(self.plugins_dir, f"{module_name}.py")
        if os.path.exists(filepath):
            self.load_plugin(filepath)
    
    def unload_plugin(self, plugin_name: str):
        """Unload a specific plugin."""
        if plugin_name in self.plugins:
            del self.plugins[plugin_name]
            if plugin_name in self.plugin_modules:
                del self.plugin_modules[plugin_name]
            self._rebuild_action_index()
            self._log(f"Unloaded plugin: {plugin_name}", "info")
    
    def _rebuild_action_index(self):
        """Rebuild the node_type -> plugins index."""
        self.actions_by_type.clear()
        
        for name, plugin in self.plugins.items():
            for node_type in plugin.node_types():
                type_key = node_type.value if isinstance(node_type, NodeType) else str(node_type)
                
                if type_key not in self.actions_by_type:
                    self.actions_by_type[type_key] = []
                
                self.actions_by_type[type_key].append({
                    "id": name,
                    "name": name,
                    "description": plugin.description()
                })
    
    def start_watcher(self):
        """Start watching the plugins directory for changes."""
        if self._observer:
            return
        
        self._observer = Observer()
        handler = PluginChangeHandler(self)
        self._observer.schedule(handler, self.plugins_dir, recursive=False)
        
        self._watcher_thread = threading.Thread(
            target=self._observer.start,
            daemon=True
        )
        self._watcher_thread.start()
        
        self._log(f"Watching {self.plugins_dir} for changes", "info")
    
    # Plugin execution methods
    
    def execute(self, plugin_name: str, node_id: Optional[str] = None, 
                **kwargs) -> PluginResult:
        """
        Execute a plugin by name.
        
        Args:
            plugin_name: Name of plugin to execute
            node_id: Optional target node ID
            **kwargs: Additional arguments for plugin
        
        Returns:
            PluginResult with execution outcome
        """
        if plugin_name not in self.plugins:
            return PluginResult(
                success=False,
                error=f"Plugin not found: {plugin_name}"
            )
        
        plugin = self.plugins[plugin_name]
        
        # Validate plugin
        if not plugin.validate():
            return PluginResult(
                success=False,
                error=f"Plugin validation failed: {plugin_name}"
            )
        
        # Check LLM requirement
        if plugin.requires_llm() and not self.agent:
            return PluginResult(
                success=False,
                error=f"Plugin {plugin_name} requires LLM but agent not available"
            )
        
        try:
            return plugin.execute(node_id=node_id, **kwargs)
        except Exception as e:
            return PluginResult(
                success=False,
                error=f"Plugin execution error: {str(e)}\n{traceback.format_exc()}"
            )
    
    def get_plugins_for_type(self, node_type: str) -> List[str]:
        """Get list of plugin names that can operate on a node type."""
        plugins = self.actions_by_type.get(node_type, [])
        plugins.extend(self.actions_by_type.get("*", []))  # Include wildcard plugins
        return [p["id"] for p in plugins]
    
    def list_plugins(self) -> List[Dict[str, Any]]:
        """List all loaded plugins with metadata."""
        return [
            {
                "name": name,
                "description": plugin.description(),
                "node_types": [t.value if isinstance(t, NodeType) else str(t) 
                              for t in plugin.node_types()],
                "requires_llm": plugin.requires_llm(),
                "has_schema": plugin.input_schema() is not None
            }
            for name, plugin in self.plugins.items()
        ]
    
    def run_all_on_node(self, node_id: str, node_type: str) -> List[PluginResult]:
        """
        Run all applicable plugins on a node.
        
        Args:
            node_id: Target node ID
            node_type: Node's type/label
        
        Returns:
            List of results from each plugin
        """
        results = []
        
        for plugin_name in self.get_plugins_for_type(node_type):
            result = self.execute(plugin_name, node_id=node_id)
            results.append(result)
        
        return results


# ============================================================================
# LANGCHAIN TOOL INTEGRATION
# ============================================================================

class GraphPluginInput(BaseModel):
    """Input schema for graph plugin tool."""
    plugin_name: str = Field(description="Name of the plugin to execute")
    node_id: Optional[str] = Field(None, description="Target node ID (optional)")
    params: Optional[str] = Field(None, description="JSON string of additional parameters")


class ListPluginsInput(BaseModel):
    """Input schema for listing plugins."""
    node_type: Optional[str] = Field(None, description="Filter by node type")


def create_plugin_tool_wrapper(manager: GraphPluginManager, agent=None):
    """Create tool wrapper functions for plugin execution."""
    
    def execute_graph_plugin(plugin_name: str, node_id: Optional[str] = None,
                            params: Optional[str] = None) -> str:
        """
        Execute a graph plugin to perform specialized Neo4j operations.
        
        Graph plugins extend the knowledge graph with:
        - Entity extraction and linking
        - Relationship inference
        - Node enrichment
        - Pattern detection
        - Custom graph algorithms
        
        Args:
            plugin_name: Name of the plugin to run
            node_id: Optional target node ID
            params: Optional JSON string of additional parameters
        
        Returns:
            Result of plugin execution
        """
        import json as json_lib
        
        kwargs = {}
        if params:
            try:
                kwargs = json_lib.loads(params)
            except:
                return f"[Error] Invalid JSON in params: {params}"
        
        result = manager.execute(plugin_name, node_id=node_id, **kwargs)
        
        # Store in agent memory if available
        if agent and hasattr(agent, 'mem'):
            agent.mem.add_session_memory(
                agent.sess.id,
                plugin_name,
                "graph_plugin_execution",
                metadata={
                    "plugin": plugin_name,
                    "node_id": node_id,
                    "success": result.success
                }
            )
        
        return str(result)
    
    def list_graph_plugins(node_type: Optional[str] = None) -> str:
        """
        List available graph plugins.
        
        Args:
            node_type: Optional filter by node type
        
        Returns:
            Formatted list of plugins
        """
        plugins = manager.list_plugins()
        
        if node_type:
            plugins = [p for p in plugins if node_type in p["node_types"] or "*" in p["node_types"]]
        
        if not plugins:
            return "No plugins available" + (f" for type {node_type}" if node_type else "")
        
        output = ["Available Graph Plugins:"]
        for p in plugins:
            types = ", ".join(p["node_types"])
            llm = " [requires LLM]" if p["requires_llm"] else ""
            output.append(f"\n• {p['name']}{llm}")
            output.append(f"  {p['description']}")
            output.append(f"  Node types: {types}")
        
        return "\n".join(output)
    
    return execute_graph_plugin, list_graph_plugins


def add_graph_plugin_tools(tool_list: List, agent, manager: GraphPluginManager):
    """
    Add graph plugin tools to Vera's tool list.
    
    Call this in ToolLoader:
        manager = GraphPluginManager(graph_manager, memory, agent, "graph_plugins")
        manager.start()
        add_graph_plugin_tools(tool_list, agent, manager)
    """
    
    execute_fn, list_fn = create_plugin_tool_wrapper(manager, agent)
    
    tool_list.extend([
        StructuredTool.from_function(
            func=execute_fn,
            name="graph_plugin",
            description=(
                "Execute a graph plugin for specialized Neo4j operations. "
                "Plugins can extract entities, infer relationships, enrich nodes, "
                "detect patterns, or run custom graph algorithms. "
                "Use list_graph_plugins first to see available plugins."
            ),
            args_schema=GraphPluginInput
        ),
        StructuredTool.from_function(
            func=list_fn,
            name="list_graph_plugins",
            description=(
                "List available graph plugins. "
                "Optionally filter by node type to see relevant plugins."
            ),
            args_schema=ListPluginsInput
        ),
    ])
    
    return tool_list


# ============================================================================
# EXAMPLE PLUGIN TEMPLATE
# ============================================================================

EXAMPLE_PLUGIN = '''"""
Example Graph Plugin - Entity Extractor

Save this as: graph_plugins/entity_extractor.py
"""

from graph_plugin_manager import GraphPluginBase, PluginResult, NodeType
from typing import List, Optional
from pydantic import BaseModel, Field


class EntityExtractorInput(BaseModel):
    """Input schema for entity extraction."""
    text: Optional[str] = Field(None, description="Text to extract from (if no node_id)")
    entity_types: Optional[List[str]] = Field(
        None, 
        description="Types of entities to extract (person, org, location, etc.)"
    )


class EntityExtractor(GraphPluginBase):
    """Extract named entities from text and add to knowledge graph."""
    
    @staticmethod
    def name() -> str:
        return "entity_extractor"
    
    @staticmethod
    def description() -> str:
        return "Extract named entities (people, organizations, locations) from text and add to graph"
    
    @staticmethod
    def node_types() -> List[NodeType]:
        return [NodeType.DOCUMENT, NodeType.MEMORY, NodeType.ANY]
    
    @staticmethod
    def input_schema():
        return EntityExtractorInput
    
    @staticmethod
    def requires_llm() -> bool:
        return True
    
    def execute(self, node_id: Optional[str] = None, **kwargs) -> PluginResult:
        """Extract entities and create graph nodes/relationships."""
        
        # Get text to process
        text = kwargs.get("text")
        
        if not text and node_id:
            node = self.get_node(node_id)
            if node:
                text = node.get("content") or node.get("text") or node.get("body")
        
        if not text:
            return PluginResult(
                success=False,
                error="No text provided and could not extract from node"
            )
        
        # Use LLM to extract entities
        entity_types = kwargs.get("entity_types", ["person", "organization", "location"])
        
        prompt = f"""Extract named entities from the following text.
Return a JSON array of objects with 'name', 'type', and 'context' fields.
Only extract these types: {', '.join(entity_types)}

Text:
{text[:2000]}

Return ONLY valid JSON, no other text."""

        try:
            # Stream from agent's LLM
            result = ""
            for chunk in self.agent.stream_llm_with_memory(
                self.agent.fast_llm, prompt, long_term=False, short_term=False
            ):
                result += chunk if isinstance(chunk, str) else str(chunk)
            
            # Parse response
            import json
            import re
            
            # Clean markdown if present
            result = re.sub(r'```json\s*', '', result)
            result = re.sub(r'```\s*', '', result)
            
            entities = json.loads(result.strip())
            
            # Create nodes and relationships
            nodes_created = []
            rels_created = []
            
            for entity in entities:
                # Create entity node
                entity_id = self.create_node(
                    labels=["Entity", entity["type"].title()],
                    properties={
                        "name": entity["name"],
                        "type": entity["type"],
                        "context": entity.get("context", ""),
                        "extracted_from": node_id,
                        "created_at": str(datetime.now())
                    }
                )
                
                if entity_id:
                    nodes_created.append(entity_id)
                    
                    # Link to source node if provided
                    if node_id:
                        if self.create_relationship(
                            node_id, entity_id, 
                            "MENTIONS",
                            {"context": entity.get("context", "")}
                        ):
                            rels_created.append(f"{node_id}-MENTIONS->{entity_id}")
            
            return PluginResult(
                success=True,
                data=f"Extracted {len(entities)} entities: {[e['name'] for e in entities]}",
                nodes_created=nodes_created,
                relationships_created=rels_created,
                metadata={"entities": entities}
            )
            
        except Exception as e:
            return PluginResult(
                success=False,
                error=f"Entity extraction failed: {str(e)}"
            )
'''


def create_example_plugin(plugins_dir: str = "graph_plugins"):
    """Create example plugin file."""
    from pathlib import Path
    
    plugins_path = Path(plugins_dir)
    plugins_path.mkdir(exist_ok=True)
    
    example_file = plugins_path / "entity_extractor.py"
    
    if not example_file.exists():
        example_file.write_text(EXAMPLE_PLUGIN)
        print(f"✓ Created example plugin: {example_file}")
        return str(example_file)
    
    return None


# ============================================================================
# QUICK START
# ============================================================================

if __name__ == "__main__":
    # Demo usage
    print("Graph Plugin Manager for Vera")
    print("=" * 40)
    print("\nTo use in Vera:")
    print("""
from graph_plugin_manager import (
    GraphPluginManager,
    add_graph_plugin_tools,
    create_example_plugin
)

# In your agent initialization:
plugin_manager = GraphPluginManager(
    graph_manager=your_graph_manager,
    memory_manager=your_memory,
    agent=self,
    plugins_dir="graph_plugins"
)
plugin_manager.start()

# In ToolLoader:
add_graph_plugin_tools(tool_list, agent, plugin_manager)

# Create example plugin:
create_example_plugin("graph_plugins")
""")
    
    # Create example
    create_example_plugin()