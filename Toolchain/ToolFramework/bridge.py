"""
Vera Tool Framework - Integration Bridge
==========================================
Convenience API layer over EnhancedToolLoader.

Usage:
    from Vera.Toolchain.ToolFramework.bridge import load_tools
    agent.tools = load_tools(agent)

    # Gives the same List[BaseTool] PLUS:
    #   agent.tool_registry    → ToolRegistry
    #   agent.tool_event_bus   → ToolEventBus
    #   agent.service_manager  → ServiceManager
    #   agent.create_tool_context(tool_name) → ToolContext factory
"""

from __future__ import annotations

import logging
from typing import List, Optional

from langchain.tools import BaseTool

from Vera.Toolchain.ToolFramework.core import (
    ToolCapability, ToolCategory, ToolContext, ToolMode,
)
from Vera.Toolchain.ToolFramework.registry import ToolRegistry, global_registry
from Vera.Toolchain.ToolFramework.services import ServiceManager, ServiceState
from Vera.Toolchain.ToolFramework.events import ToolEventBus
from Vera.Toolchain.ToolFramework.loader import EnhancedToolLoader

logger = logging.getLogger("vera.tools.bridge")


# ---------------------------------------------------------------------------
# Primary entry point
# ---------------------------------------------------------------------------

def load_tools(
    agent,
    registry: Optional[ToolRegistry] = None,
    orchestrator_event_bus=None,
    websocket_manager=None,
) -> List[BaseTool]:
    """
    Load all tools with enhanced framework support.
    Drop-in replacement for ToolLoader(agent).

    Returns:
        List[BaseTool] - identical to what ToolLoader returns

    Side effects on agent:
        agent.tool_registry         → ToolRegistry
        agent.tool_event_bus        → ToolEventBus
        agent.service_manager       → ServiceManager
        agent.create_tool_context   → Callable[[str], ToolContext]
    """
    return EnhancedToolLoader(
        agent,
        registry=registry,
        orchestrator_event_bus=orchestrator_event_bus,
        websocket_manager=websocket_manager,
    )


# ---------------------------------------------------------------------------
# Filtered tool lists
# ---------------------------------------------------------------------------

def get_tools_for_agent_type(agent, agent_type: str) -> List[BaseTool]:
    """
    Get a filtered tool list for a specific agent type.
    Requires load_tools() to have been called first.

    agent_type: "conversation" | "coding" | "security" |
                "research" | "data" | "planning" | "monitoring"
    """
    if not hasattr(agent, "tool_registry"):
        logger.warning("tool_registry not found – call load_tools() first")
        return []
    return agent.tool_registry.get_for_agent(agent_type=agent_type)


def get_tools_by_capabilities(agent, *capabilities: ToolCapability) -> List[BaseTool]:
    """Get tools that have ALL specified capabilities."""
    if not hasattr(agent, "tool_registry"):
        return []
    return agent.tool_registry.get_by_capabilities(*capabilities)


def get_tools_by_category(agent, category: ToolCategory) -> List[BaseTool]:
    """Get all tools in a specific category."""
    if not hasattr(agent, "tool_registry"):
        return []
    return agent.tool_registry.get_by_category(category)


# ---------------------------------------------------------------------------
# Service management helpers
# ---------------------------------------------------------------------------

def start_tool_service(
    agent,
    tool_name: str,
    config: Optional[dict] = None,
) -> Optional[object]:
    """
    Start a registered tool as a background service.
    Requires load_tools() to have been called first.

    Returns:
        ServiceHandle or None
    """
    if not hasattr(agent, "tool_registry") or not hasattr(agent, "service_manager"):
        logger.warning("Framework not initialised – call load_tools() first")
        return None

    descriptor = agent.tool_registry.get_descriptor(tool_name)
    if not descriptor:
        logger.error(f"Tool not found: {tool_name}")
        return None

    if not descriptor.can_run_as_service:
        logger.error(f"Tool '{tool_name}' is not configured as a service")
        return None

    ctx = agent.create_tool_context(tool_name)
    return agent.service_manager.start_service(descriptor, ctx, config=config)


def stop_tool_service(agent, service_id: str, timeout: float = 10.0) -> bool:
    """Stop a running service by its service_id."""
    if not hasattr(agent, "service_manager"):
        return False
    return agent.service_manager.stop_service(service_id, timeout=timeout)


def list_running_services(agent) -> list:
    """Return status dicts for all running services."""
    if not hasattr(agent, "service_manager"):
        return []
    return agent.service_manager.list_services(state=ServiceState.RUNNING)


# ---------------------------------------------------------------------------
# UI descriptors
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Registry summary (useful for debug / monitoring endpoints)
# ---------------------------------------------------------------------------

def registry_summary(agent) -> dict:
    """Return a summary of the tool registry for debugging."""
    if not hasattr(agent, "tool_registry"):
        return {"error": "registry not initialised"}
    return agent.tool_registry.summary()