"""
Vera Tool Framework - Integration Bridge
==========================================
This module bridges the existing ToolLoader (tools.py) with the enhanced
tool framework. It does NOT replace tools.py - it wraps it.

Usage:
    # Instead of:
    #   from Vera.Toolchain.tools import ToolLoader
    #   agent.tools = ToolLoader(agent)
    
    # Use:
    from Vera.Toolchain.tool_framework.bridge import load_tools
    agent.tools = load_tools(agent)
    
    # This gives you the same List[BaseTool] PLUS:
    #   agent.tool_registry    → ToolRegistry (query by category, capability, etc.)
    #   agent.tool_event_bus   → ToolEventBus (tool events, UI updates)
    #   agent.service_manager  → ServiceManager (background service lifecycle)
    #   agent.create_tool_context(tool_name) → ToolContext factory

Or use EnhancedToolLoader directly if you prefer the function-call style.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from langchain.tools import BaseTool

from Vera.Toolchain.tool_framework.core import (
    ToolCapability, ToolCategory, ToolContext, ToolMode,
)
from Vera.Toolchain.tool_framework.registry import ToolRegistry, global_registry
from Vera.Toolchain.tool_framework.services import ServiceManager
from Vera.Toolchain.tool_framework.events import ToolEventBus
from Vera.Toolchain.tool_framework.loader import EnhancedToolLoader

logger = logging.getLogger("vera.tools.bridge")


def load_tools(agent, registry: Optional[ToolRegistry] = None) -> List[BaseTool]:
    """
    Load all tools with enhanced framework support.
    Drop-in replacement for ToolLoader(agent).
    
    Returns:
        List[BaseTool] - identical to what ToolLoader returns
    
    Side effects:
        Sets agent.tool_registry, agent.tool_event_bus,
        agent.service_manager, agent.create_tool_context
    """
    return EnhancedToolLoader(agent, registry=registry)


def get_tools_for_agent_type(agent, agent_type: str) -> List[BaseTool]:
    """
    Get a filtered tool list for a specific agent type.
    
    Requires load_tools() to have been called first.
    
    Args:
        agent: Vera agent instance
        agent_type: One of "conversation", "coding", "security",
                    "research", "data", "planning", "monitoring"
    
    Returns:
        Filtered List[BaseTool]
    """
    if not hasattr(agent, "tool_registry"):
        logger.warning("tool_registry not found on agent - call load_tools() first")
        return []
    
    return agent.tool_registry.get_for_agent(agent_type=agent_type)


def get_tools_by_capabilities(agent, *capabilities: ToolCapability) -> List[BaseTool]:
    """Get tools that have ALL specified capabilities."""
    if not hasattr(agent, "tool_registry"):
        return []
    return agent.tool_registry.get_by_capabilities(*capabilities)


def start_tool_service(agent, tool_name: str, config: Optional[dict] = None):
    """
    Start a tool as a background service.
    
    Requires load_tools() to have been called first.
    
    Args:
        agent: Vera agent instance
        tool_name: Name of the tool to start as service
        config: Service configuration dict
    
    Returns:
        ServiceHandle or None
    """
    if not hasattr(agent, "tool_registry") or not hasattr(agent, "service_manager"):
        logger.warning("Framework not initialized - call load_tools() first")
        return None
    
    descriptor = agent.tool_registry.get_descriptor(tool_name)
    if not descriptor:
        logger.error(f"Tool not found: {tool_name}")
        return None
    
    if not descriptor.can_run_as_service:
        logger.error(f"Tool '{tool_name}' cannot run as a service")
        return None
    
    ctx = agent.create_tool_context(tool_name)
    return agent.service_manager.start_service(descriptor, ctx, config=config)


def get_ui_descriptors(agent) -> List[dict]:
    """
    Get UI descriptors for all tools that have UI components.
    Frontend calls this to know what UI to render.
    
    Returns:
        List of JSON-serialisable UI descriptor dicts
    """
    if not hasattr(agent, "tool_registry"):
        return []
    
    ui_tools = agent.tool_registry.get_ui_tools()
    result = []
    for desc in ui_tools:
        ui_data = desc.to_frontend_json()
        if desc.ui_config:
            ui_data["ui_config"] = desc.ui_config
        result.append(ui_data)
    return result