"""
Vera Tool Framework - Enhanced Loader
=======================================
EnhancedToolLoader wraps the original ToolLoader (tools.py) and registers
every tool it returns into the ToolRegistry, attaches the event bus and
service manager to the agent, and exposes a ToolContext factory.

Drop-in replacement for ToolLoader(agent).  No other files need changing.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from langchain.tools import BaseTool

from Vera.Toolchain.ToolFramework.core import (
    ToolCapability,
    ToolCategory,
    ToolContext,
    ToolMode,
)
from Vera.Toolchain.ToolFramework.registry import ToolRegistry
from Vera.Toolchain.ToolFramework.services import ServiceManager
from Vera.Toolchain.ToolFramework.events import ToolEventBus

logger = logging.getLogger("vera.tools.loader")


# ---------------------------------------------------------------------------
# Heuristic category mapping
# ---------------------------------------------------------------------------

_NAME_TO_CATEGORY: dict[str, ToolCategory] = {
    "web_search": ToolCategory.WEB,
    "web_search_deep": ToolCategory.WEB,
    "crawl_website": ToolCategory.WEB,
    "navigate_web_smart": ToolCategory.WEB,
    "news_search": ToolCategory.WEB,
    "read_file": ToolCategory.FILESYSTEM,
    "write_file": ToolCategory.FILESYSTEM,
    "list_directory": ToolCategory.FILESYSTEM,
    "search_files": ToolCategory.FILESYSTEM,
    "create_directory": ToolCategory.FILESYSTEM,
    "delete_file": ToolCategory.FILESYSTEM,
    "move_file": ToolCategory.FILESYSTEM,
    "copy_file": ToolCategory.FILESYSTEM,
    "python": ToolCategory.CODING,
    "execute_python": ToolCategory.CODING,
    "bash": ToolCategory.CODING,
    "execute_bash": ToolCategory.CODING,
    "run_code": ToolCategory.CODING,
    "codebase_search": ToolCategory.CODING,
    "codebase_map": ToolCategory.CODING,
    "sqlite_query": ToolCategory.DATABASE,
    "postgres_query": ToolCategory.DATABASE,
    "neo4j_query": ToolCategory.DATABASE,
    "git": ToolCategory.GIT,
    "git_commit": ToolCategory.GIT,
    "git_diff": ToolCategory.GIT,
    "git_log": ToolCategory.GIT,
    "nmap_scan": ToolCategory.SECURITY,
    "osint_search": ToolCategory.OSINT,
    "dorking_search": ToolCategory.OSINT,
    "vulnerability_search": ToolCategory.SECURITY,
    "web_recon": ToolCategory.SECURITY,
    "port_scan": ToolCategory.SECURITY,
    "fast_llm": ToolCategory.LLM,
    "deep_llm": ToolCategory.LLM,
    "coding_llm": ToolCategory.LLM,
    "search_memory": ToolCategory.MEMORY,
    "system_info": ToolCategory.SYSTEM,
    "process_list": ToolCategory.SYSTEM,
    "parse_json": ToolCategory.DATA,
    "parse_csv": ToolCategory.DATA,
    "format_data": ToolCategory.DATA,
    "http_request": ToolCategory.NETWORK,
    "ping": ToolCategory.NETWORK,
    "mcp_call": ToolCategory.COMMUNICATION,
    "mcp_list_tools": ToolCategory.COMMUNICATION,
    "get_time": ToolCategory.UTILITY,
    "format_time": ToolCategory.UTILITY,
    "summarise": ToolCategory.LLM,
    "translate": ToolCategory.LLM,
}

_KEYWORD_TO_CATEGORY: list[tuple[str, ToolCategory]] = [
    ("scan",    ToolCategory.SECURITY),
    ("osint",   ToolCategory.OSINT),
    ("recon",   ToolCategory.SECURITY),
    ("vuln",    ToolCategory.SECURITY),
    ("git",     ToolCategory.GIT),
    ("file",    ToolCategory.FILESYSTEM),
    ("dir",     ToolCategory.FILESYSTEM),
    ("path",    ToolCategory.FILESYSTEM),
    ("search",  ToolCategory.WEB),
    ("web",     ToolCategory.WEB),
    ("crawl",   ToolCategory.WEB),
    ("http",    ToolCategory.NETWORK),
    ("sql",     ToolCategory.DATABASE),
    ("db",      ToolCategory.DATABASE),
    ("memory",  ToolCategory.MEMORY),
    ("graph",   ToolCategory.MEMORY),
    ("llm",     ToolCategory.LLM),
    ("bash",    ToolCategory.CODING),
    ("python",  ToolCategory.CODING),
    ("code",    ToolCategory.CODING),
    ("system",  ToolCategory.SYSTEM),
    ("process", ToolCategory.SYSTEM),
    ("time",    ToolCategory.UTILITY),
    ("data",    ToolCategory.DATA),
    ("parse",   ToolCategory.DATA),
    ("mcp",     ToolCategory.COMMUNICATION),
    ("ssh",     ToolCategory.NETWORK),
    ("docker",  ToolCategory.SYSTEM),
    ("n8n",     ToolCategory.ORCHESTRATION),
]


def _infer_category(tool: BaseTool) -> ToolCategory:
    name = getattr(tool, "name", "") or ""
    if name in _NAME_TO_CATEGORY:
        return _NAME_TO_CATEGORY[name]
    name_lower = name.lower()
    for kw, cat in _KEYWORD_TO_CATEGORY:
        if kw in name_lower:
            return cat
    desc = (getattr(tool, "description", "") or "").lower()
    for kw, cat in _KEYWORD_TO_CATEGORY:
        if kw in desc:
            return cat
    return ToolCategory.UTILITY


def _infer_mode(tool: BaseTool) -> ToolMode:
    combined = (
        (getattr(tool, "name", "") or "") + " " +
        (getattr(tool, "description", "") or "")
    ).lower()
    if any(k in combined for k in ("monitor", "sensor", "watch", "daemon", "service")):
        return ToolMode.SERVICE
    if any(k in combined for k in ("ui", "dashboard", "frontend", "viewer")):
        return ToolMode.UI_ONLY
    if any(k in combined for k in ("internal", "system_only", "private")):
        return ToolMode.INTERNAL
    return ToolMode.MULTIPURPOSE


# ---------------------------------------------------------------------------
# Public loader
# ---------------------------------------------------------------------------

def EnhancedToolLoader(
    agent,
    registry: Optional[ToolRegistry] = None,
    orchestrator_event_bus=None,
    websocket_manager=None,
) -> List[BaseTool]:
    """
    Load all tools and wire up the enhanced framework.

    1. Calls ToolLoader to get the flat tool list.
    2. Registers every tool into ToolRegistry with heuristic metadata.
    3. Attaches registry / event bus / service manager to the agent.
    4. Returns the same flat List[BaseTool] the agent already expects.
    """
    from Vera.Toolchain.ToolFramework.tools import ToolLoader

    tool_list: List[BaseTool] = ToolLoader(agent)
    logger.info(f"[EnhancedToolLoader] ToolLoader returned {len(tool_list)} tools")

    reg      = registry or ToolRegistry()
    event_bus = ToolEventBus(
        orchestrator_event_bus=orchestrator_event_bus,
        websocket_manager=websocket_manager,
    )
    svc_mgr  = ServiceManager(event_bus=event_bus)

    if orchestrator_event_bus is None and hasattr(agent, "event_bus"):
        event_bus.set_orchestrator_bus(agent.event_bus)
    if websocket_manager is None and hasattr(agent, "ws_manager"):
        event_bus.set_websocket_manager(agent.ws_manager)

    for tool in tool_list:
        reg.register_legacy(tool, category=_infer_category(tool), mode=_infer_mode(tool))

    logger.info(f"[EnhancedToolLoader] Registry summary: {reg.summary()}")

    agent.tool_registry   = reg
    agent.tool_event_bus  = event_bus
    agent.service_manager = svc_mgr

    def _create_tool_context(tool_name: str) -> ToolContext:
        return ToolContext(
            agent=agent,
            memory=getattr(agent, "mem", None),
            orchestrator=getattr(agent, "orchestrator", None),
            event_bus=event_bus,
            session_id=(
                agent.sess.id
                if hasattr(agent, "sess") and hasattr(agent.sess, "id")
                else None
            ),
            tool_name=tool_name,
        )

    agent.create_tool_context = _create_tool_context
    logger.info("[EnhancedToolLoader] Framework attached to agent ✓")
    return tool_list


# ---------------------------------------------------------------------------
# Helper for @enhanced_tool functions added inside add_*_tools()
# ---------------------------------------------------------------------------
def register_enhanced_tools(
    tool_list: List[BaseTool],
    agent,
    funcs: list,
    registry: Optional[ToolRegistry] = None,
) -> None:
    from langchain_core.tools import StructuredTool as LCStructuredTool
    from Vera.Toolchain.ToolFramework.core import ToolDescriptor
    import functools

    reg: Optional[ToolRegistry] = registry or getattr(agent, "tool_registry", None)
    create_ctx = getattr(agent, "create_tool_context", None)

    for func in funcs:
        if not hasattr(func, "_tool_descriptor"):
            logger.warning(
                f"register_enhanced_tools: {func.__name__} has no _tool_descriptor"
            )
            continue

        desc: ToolDescriptor = func._tool_descriptor

        # Grab the input_schema Pydantic class from the descriptor
        schema_class = getattr(desc, "input_schema", None)

        if schema_class is None:
            logger.warning(
                f"register_enhanced_tools: '{desc.name}' has no input_schema on "
                "its ToolDescriptor. Add input_schema=YourInputModel to the "
                "@enhanced_tool / @service_tool decorator."
            )
            continue  # skip rather than explode

        # Build a clean wrapper that accepts only the schema fields, no ctx
        def _make_wrapper(f, d, ctx_factory):
            @functools.wraps(f)
            def wrapper(**kwargs):
                ctx = ctx_factory(d.name) if ctx_factory else None
                return f(ctx, **kwargs)
            return wrapper

        wrapped = _make_wrapper(func, desc, create_ctx)

        lc_tool = LCStructuredTool.from_function(
            func=wrapped,
            name=desc.name,
            description=desc.description,
            args_schema=schema_class,   # explicit schema — no sig inspection
        )
        tool_list.append(lc_tool)

        if reg is not None:
            reg.register(func, langchain_tool=lc_tool)
        else:
            logger.debug(f"register_enhanced_tools: no registry for '{desc.name}'")