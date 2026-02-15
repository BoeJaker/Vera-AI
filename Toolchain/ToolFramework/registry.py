"""
Vera Tool Framework - Registry
================================
Central registry that indexes all tools (legacy and enhanced) and provides
dynamic filtering for agents, UI, and orchestrator consumers.

The registry maintains both:
    1. The monolithic flat list (backwards compat with ToolLoader)
    2. Indexed views by category, mode, capability, and tags

Tools are registered automatically when decorated with @enhanced_tool,
or manually via registry.register() / registry.register_legacy().
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import (
    Any, Callable, Dict, List, Optional, Set, Tuple, Type, Union,
)

from langchain.tools import BaseTool
from langchain_core.tools import StructuredTool

from Vera.Toolchain.tool_framework.core import (
    ToolCapability,
    ToolCategory,
    ToolContext,
    ToolDescriptor,
    ToolMode,
    ToolUIType,
)

logger = logging.getLogger("vera.tools.registry")


class ToolRegistry:
    """
    Central tool registry with multi-dimensional indexing.
    
    Maintains full backwards compatibility with the flat `tool_list` pattern
    while adding rich querying capabilities.
    
    Usage:
        registry = ToolRegistry()
        
        # Register enhanced tool (auto from decorator)
        @enhanced_tool("my_tool", "does stuff", category=ToolCategory.NETWORK)
        def my_tool(ctx, query): ...
        registry.register(my_tool)
        
        # Register legacy LangChain tool
        registry.register_legacy(some_structured_tool)
        
        # Query
        network_tools = registry.get_by_category(ToolCategory.NETWORK)
        streaming_tools = registry.get_by_capability(ToolCapability.STREAMING)
        llm_tools = registry.get_for_agent(agent_type="security")
        all_tools = registry.get_langchain_tools()  # flat list for existing code
    """

    def __init__(self):
        # Primary storage: name → descriptor
        self._descriptors: Dict[str, ToolDescriptor] = {}
        
        # LangChain tool wrappers (for backwards compat)
        self._langchain_tools: Dict[str, BaseTool] = {}
        
        # Legacy tools that were registered without descriptors
        self._legacy_tools: Dict[str, BaseTool] = {}
        
        # Indexes (rebuilt on register/unregister)
        self._by_category: Dict[ToolCategory, Set[str]] = defaultdict(set)
        self._by_mode: Dict[ToolMode, Set[str]] = defaultdict(set)
        self._by_capability: Dict[ToolCapability, Set[str]] = defaultdict(set)
        self._by_tag: Dict[str, Set[str]] = defaultdict(set)
        
        # Service-capable tools
        self._service_tools: Set[str] = set()
        
        # UI-capable tools
        self._ui_tools: Set[str] = set()

    # ================================================================
    # REGISTRATION
    # ================================================================

    def register(self, func_or_tool: Union[Callable, BaseTool],
                 langchain_tool: Optional[BaseTool] = None,
                 descriptor: Optional[ToolDescriptor] = None):
        """
        Register a tool. Accepts:
            - A decorated function (has _tool_descriptor)
            - A LangChain BaseTool / StructuredTool
            - A function + explicit descriptor
        """
        # Case 1: Decorated function
        if callable(func_or_tool) and hasattr(func_or_tool, "_tool_descriptor"):
            desc: ToolDescriptor = func_or_tool._tool_descriptor
            self._register_descriptor(desc)
            
            # Auto-wrap as LangChain StructuredTool if not already provided
            if langchain_tool:
                self._langchain_tools[desc.name] = langchain_tool
            else:
                self._langchain_tools[desc.name] = self._wrap_as_langchain(func_or_tool, desc)
            
            logger.info(f"Registered enhanced tool: {desc.name} [{desc.category.value}]")
            return

        # Case 2: Explicit descriptor
        if descriptor:
            self._register_descriptor(descriptor)
            if langchain_tool:
                self._langchain_tools[descriptor.name] = langchain_tool
            elif callable(func_or_tool):
                self._langchain_tools[descriptor.name] = self._wrap_as_langchain(func_or_tool, descriptor)
            logger.info(f"Registered tool with descriptor: {descriptor.name}")
            return

        # Case 3: LangChain tool (legacy)
        if isinstance(func_or_tool, BaseTool):
            self.register_legacy(func_or_tool)
            return

        raise TypeError(
            f"Cannot register {type(func_or_tool)}. "
            "Use @enhanced_tool decorator, pass a ToolDescriptor, or pass a LangChain BaseTool."
        )

    def register_legacy(self, tool: BaseTool,
                        category: ToolCategory = ToolCategory.UTILITY,
                        mode: ToolMode = ToolMode.MULTIPURPOSE,
                        tags: Optional[List[str]] = None):
        """
        Register an existing LangChain tool without modification.
        Creates a minimal ToolDescriptor for indexing.
        """
        name = tool.name
        desc = ToolDescriptor(
            name=name,
            description=tool.description or "",
            category=category,
            mode=mode,
            tags=tags or [],
        )
        
        # Try to extract input schema
        if hasattr(tool, "args_schema") and tool.args_schema:
            try:
                desc.input_schema = tool.args_schema.model_json_schema()
            except Exception:
                pass
        
        self._register_descriptor(desc)
        self._langchain_tools[name] = tool
        self._legacy_tools[name] = tool
        
        logger.debug(f"Registered legacy tool: {name}")

    def register_list(self, tools: List[BaseTool],
                      category: ToolCategory = ToolCategory.UTILITY):
        """Bulk-register a list of LangChain tools (e.g. from add_*_tools)."""
        for tool in tools:
            self.register_legacy(tool, category=category)

    def unregister(self, name: str):
        """Remove a tool from the registry."""
        if name in self._descriptors:
            desc = self._descriptors.pop(name)
            self._langchain_tools.pop(name, None)
            self._legacy_tools.pop(name, None)
            self._rebuild_indexes_for_removal(name, desc)
            logger.info(f"Unregistered tool: {name}")

    # ================================================================
    # QUERYING
    # ================================================================

    def get_descriptor(self, name: str) -> Optional[ToolDescriptor]:
        """Get descriptor by tool name."""
        return self._descriptors.get(name)

    def get_langchain_tool(self, name: str) -> Optional[BaseTool]:
        """Get LangChain tool instance by name."""
        return self._langchain_tools.get(name)

    def get_langchain_tools(self) -> List[BaseTool]:
        """
        Get ALL tools as a flat list of LangChain tools.
        This is the backwards-compatible equivalent of the old ToolLoader return value.
        """
        return list(self._langchain_tools.values())

    def get_by_category(self, category: ToolCategory) -> List[BaseTool]:
        """Get tools in a specific category."""
        names = self._by_category.get(category, set())
        return [self._langchain_tools[n] for n in names if n in self._langchain_tools]

    def get_by_mode(self, mode: ToolMode) -> List[BaseTool]:
        """Get tools with a specific mode."""
        names = self._by_mode.get(mode, set())
        return [self._langchain_tools[n] for n in names if n in self._langchain_tools]

    def get_by_capability(self, capability: ToolCapability) -> List[BaseTool]:
        """Get tools with a specific capability flag."""
        names = self._by_capability.get(capability, set())
        return [self._langchain_tools[n] for n in names if n in self._langchain_tools]

    def get_by_capabilities(self, *capabilities: ToolCapability) -> List[BaseTool]:
        """Get tools that have ALL specified capabilities."""
        if not capabilities:
            return self.get_langchain_tools()
        result_names = None
        for cap in capabilities:
            cap_names = self._by_capability.get(cap, set())
            if result_names is None:
                result_names = cap_names.copy()
            else:
                result_names &= cap_names
        return [self._langchain_tools[n] for n in (result_names or set()) if n in self._langchain_tools]

    def get_by_tag(self, tag: str) -> List[BaseTool]:
        """Get tools with a specific tag."""
        names = self._by_tag.get(tag, set())
        return [self._langchain_tools[n] for n in names if n in self._langchain_tools]

    def get_by_tags(self, tags: List[str], match_all: bool = False) -> List[BaseTool]:
        """Get tools matching tags (any or all)."""
        if not tags:
            return []
        sets = [self._by_tag.get(t, set()) for t in tags]
        if match_all:
            names = set.intersection(*sets) if sets else set()
        else:
            names = set.union(*sets) if sets else set()
        return [self._langchain_tools[n] for n in names if n in self._langchain_tools]

    def get_services(self) -> List[ToolDescriptor]:
        """Get all tools that can run as services."""
        return [self._descriptors[n] for n in self._service_tools if n in self._descriptors]

    def get_ui_tools(self) -> List[ToolDescriptor]:
        """Get all tools with UI components."""
        return [self._descriptors[n] for n in self._ui_tools if n in self._descriptors]

    def get_for_agent(self, agent_type: Optional[str] = None,
                      categories: Optional[List[ToolCategory]] = None,
                      exclude_modes: Optional[List[ToolMode]] = None,
                      required_capabilities: Optional[List[ToolCapability]] = None,
                      tags: Optional[List[str]] = None) -> List[BaseTool]:
        """
        Build a dynamic tool list for an agent based on multiple criteria.
        
        Args:
            agent_type: Hint for pre-configured agent profiles (e.g. "security", "coding")
            categories: Filter by categories (OR)
            exclude_modes: Exclude tools with these modes
            required_capabilities: Require these capabilities (AND)
            tags: Filter by tags (OR)
        """
        # Start with all tool names
        candidates = set(self._descriptors.keys())

        # Agent type presets
        if agent_type:
            preset = _AGENT_TYPE_PRESETS.get(agent_type)
            if preset:
                cat_names = set()
                for cat in preset.get("categories", []):
                    cat_names |= self._by_category.get(cat, set())
                if cat_names:
                    candidates &= cat_names

        # Category filter
        if categories:
            cat_names = set()
            for cat in categories:
                cat_names |= self._by_category.get(cat, set())
            candidates &= cat_names

        # Mode exclusion (always exclude UI_ONLY for LLM agents unless specified)
        exclude = set(exclude_modes or [])
        if agent_type and agent_type != "ui":
            exclude.add(ToolMode.UI_ONLY)
            exclude.add(ToolMode.INTERNAL)
        for mode in exclude:
            mode_names = self._by_mode.get(mode, set())
            candidates -= mode_names

        # Capability requirements
        if required_capabilities:
            for cap in required_capabilities:
                cap_names = self._by_capability.get(cap, set())
                candidates &= cap_names

        # Tag filter
        if tags:
            tag_names = set()
            for t in tags:
                tag_names |= self._by_tag.get(t, set())
            candidates &= tag_names

        return [self._langchain_tools[n] for n in candidates if n in self._langchain_tools]

    def list_names(self) -> List[str]:
        """List all registered tool names."""
        return list(self._descriptors.keys())

    def list_descriptors(self) -> List[ToolDescriptor]:
        """List all descriptors."""
        return list(self._descriptors.values())

    def summary(self) -> Dict[str, Any]:
        """Registry summary for debugging/monitoring."""
        return {
            "total_tools": len(self._descriptors),
            "enhanced": len(self._descriptors) - len(self._legacy_tools),
            "legacy": len(self._legacy_tools),
            "by_category": {
                cat.value: len(names) for cat, names in self._by_category.items()
            },
            "by_mode": {
                mode.value: len(names) for mode, names in self._by_mode.items()
            },
            "services": len(self._service_tools),
            "ui_tools": len(self._ui_tools),
        }

    # ================================================================
    # INTERNAL
    # ================================================================

    def _register_descriptor(self, desc: ToolDescriptor):
        """Index a descriptor."""
        name = desc.name
        self._descriptors[name] = desc

        # Category index
        self._by_category[desc.category].add(name)

        # Mode index
        self._by_mode[desc.mode].add(name)

        # Capability indexes
        for cap in ToolCapability:
            if cap == ToolCapability.NONE:
                continue
            if desc.has_capability(cap):
                self._by_capability[cap].add(name)

        # Tag index
        for tag in desc.tags:
            self._by_tag[tag.lower()].add(name)

        # Service / UI tracking
        if desc.can_run_as_service:
            self._service_tools.add(name)
        if desc.ui_type != ToolUIType.NONE:
            self._ui_tools.add(name)

    def _rebuild_indexes_for_removal(self, name: str, desc: ToolDescriptor):
        """Remove a tool from all indexes."""
        self._by_category.get(desc.category, set()).discard(name)
        self._by_mode.get(desc.mode, set()).discard(name)
        for cap in ToolCapability:
            self._by_capability.get(cap, set()).discard(name)
        for tag in desc.tags:
            self._by_tag.get(tag.lower(), set()).discard(name)
        self._service_tools.discard(name)
        self._ui_tools.discard(name)

    def _wrap_as_langchain(self, func: Callable, desc: ToolDescriptor) -> StructuredTool:
        """Wrap an enhanced tool function as a LangChain StructuredTool."""
        from pydantic import BaseModel as PydanticBase

        # Build args schema from input_schema or function signature
        args_schema = None
        if desc.input_schema:
            # We have a JSON schema dict - LangChain needs a Pydantic class
            # For now, use a generic schema; tools with explicit input_schema
            # classes should pass them via the input_schema param
            pass

        return StructuredTool.from_function(
            func=func,
            name=desc.name,
            description=desc.description,
        )


# ============================================================================
# AGENT TYPE PRESETS
# ============================================================================

_AGENT_TYPE_PRESETS: Dict[str, Dict[str, Any]] = {
    "conversation": {
        "categories": [ToolCategory.LLM, ToolCategory.MEMORY, ToolCategory.UTILITY],
    },
    "coding": {
        "categories": [
            ToolCategory.CODING, ToolCategory.FILESYSTEM, ToolCategory.GIT,
            ToolCategory.SYSTEM, ToolCategory.UTILITY,
        ],
    },
    "security": {
        "categories": [
            ToolCategory.SECURITY, ToolCategory.NETWORK, ToolCategory.OSINT,
            ToolCategory.WEB, ToolCategory.SYSTEM,
        ],
    },
    "research": {
        "categories": [
            ToolCategory.WEB, ToolCategory.LLM, ToolCategory.MEMORY,
            ToolCategory.DATA, ToolCategory.UTILITY,
        ],
    },
    "data": {
        "categories": [
            ToolCategory.DATA, ToolCategory.DATABASE, ToolCategory.FILESYSTEM,
            ToolCategory.UTILITY,
        ],
    },
    "planning": {
        "categories": [
            ToolCategory.ORCHESTRATION, ToolCategory.MEMORY, ToolCategory.LLM,
        ],
    },
    "monitoring": {
        "categories": [
            ToolCategory.MONITORING, ToolCategory.NETWORK, ToolCategory.SYSTEM,
        ],
    },
}


# ============================================================================
# GLOBAL SINGLETON
# ============================================================================

global_registry = ToolRegistry()