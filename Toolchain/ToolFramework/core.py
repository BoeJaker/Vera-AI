"""
Vera Tool Framework - Core
============================
Base classes, enums, decorators, descriptors, and the ToolContext
that gives every tool uniform access to memory, orchestrator, events, and UI.

Design Goals:
    - Every existing tool works unchanged (backwards compat)
    - New tools opt-in to capabilities via decorators
    - Tools self-describe their category, mode, UI, and capabilities
    - ToolContext is the single injection point for system services
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, Flag, auto
from functools import wraps
from typing import (
    Any, Callable, Dict, Iterator, List, Optional, Set, Type, Union,
)

from pydantic import BaseModel, Field

logger = logging.getLogger("vera.tools.core")


# ============================================================================
# ENUMS - Capability flags, categories, modes
# ============================================================================

class ToolCapability(Flag):
    """
    Bitwise-combinable capability flags.
    A tool can have multiple capabilities simultaneously.
    
    Example:
        caps = ToolCapability.STREAMING | ToolCapability.SERVICE | ToolCapability.UI
    """
    NONE          = 0
    STREAMING     = auto()   # Can yield/stream output chunks
    SERVICE       = auto()   # Can run as a long-lived background service
    UI            = auto()   # Has associated UI component(s)
    ASYNC         = auto()   # Native async support
    MEMORY_READ   = auto()   # Reads from memory/graph
    MEMORY_WRITE  = auto()   # Writes to memory/graph
    GRAPH_BUILD   = auto()   # Builds knowledge graph structures
    ORCHESTRATED  = auto()   # Runs through the orchestrator task system
    SENSOR        = auto()   # Produces continuous data (monitor/sensor pattern)
    PARSER        = auto()   # Transforms/parses data
    HTTP_ENDPOINT = auto()   # Exposes an HTTP endpoint
    EVENT_EMITTER = auto()   # Emits events to the event bus
    EVENT_LISTENER = auto()  # Listens for events from the event bus
    IDEMPOTENT    = auto()   # Safe to retry / call multiple times


class ToolCategory(str, Enum):
    """
    Primary functional category.
    Used for agent-facing tool list filtering.
    """
    FILESYSTEM    = "filesystem"
    NETWORK       = "network"
    SECURITY      = "security"
    CODING        = "coding"
    DATA          = "data"
    LLM           = "llm"
    MEMORY        = "memory"
    WEB           = "web"
    SYSTEM        = "system"
    COMMUNICATION = "communication"
    MONITORING    = "monitoring"
    UTILITY       = "utility"
    ORCHESTRATION = "orchestration"
    OSINT         = "osint"
    DATABASE      = "database"
    GIT           = "git"
    CUSTOM        = "custom"


class ToolMode(str, Enum):
    """
    How / by whom a tool is intended to be invoked.
    Controls visibility in different interfaces.
    """
    LLM_ONLY      = "llm_only"       # Only callable by agents/LLMs
    UI_ONLY        = "ui_only"        # Only surfaced in the frontend
    MULTIPURPOSE   = "multipurpose"   # Both LLM and UI
    ONE_SHOT       = "one_shot"       # Single invocation, no follow-up
    SERVICE        = "service"        # Long-running background process
    INTERNAL       = "internal"       # System-internal, not user-facing


class ToolUIType(str, Enum):
    """Pre-built UI component types that the frontend can render."""
    NONE          = "none"
    CONSOLE       = "console"         # Streaming log/output console
    TABLE         = "table"           # Tabular data display
    CHART         = "chart"           # Chart/graph visualisation
    FORM          = "form"            # Dynamic input form from schema
    MONITOR       = "monitor"         # Live status dashboard
    MAP           = "map"             # Network/geo map
    GRAPH         = "graph"           # Knowledge graph visualiser
    TERMINAL      = "terminal"        # Interactive terminal
    CUSTOM        = "custom"          # Custom React/HTML component


# ============================================================================
# TOOL DESCRIPTOR - Complete metadata model for a tool
# ============================================================================

class ToolDescriptor(BaseModel):
    """
    Complete metadata for an enhanced tool.
    Attached to every tool function via the `_tool_descriptor` attribute.
    Serialisable to JSON for frontend consumption and agent introspection.
    """
    # Identity
    name: str
    description: str
    version: str = "1.0.0"

    # Classification
    category: ToolCategory = ToolCategory.UTILITY
    mode: ToolMode = ToolMode.MULTIPURPOSE
    capabilities: int = 0  # ToolCapability flags stored as int for serialisation
    tags: List[str] = Field(default_factory=list)

    # UI
    ui_type: ToolUIType = ToolUIType.NONE
    ui_config: Dict[str, Any] = Field(default_factory=dict)

    # Service
    can_run_as_service: bool = False
    service_config: Dict[str, Any] = Field(default_factory=dict)

    # Schema (auto-populated from Pydantic input model or function sig)
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None

    # Orchestrator
    task_type: Optional[str] = None          # Maps to TaskType value
    priority: Optional[str] = None           # Maps to Priority value
    estimated_duration: float = 5.0

    # Metadata
    author: str = "vera"
    requires_confirmation: bool = False      # Ask user before executing
    cost_hint: str = "low"                   # low | medium | high | gpu
    
    # Runtime (not serialised to frontend)
    _handler: Optional[Callable] = None
    _service_factory: Optional[Callable] = None

    class Config:
        arbitrary_types_allowed = True
        # Exclude private fields from serialisation
        json_schema_extra = {
            "exclude": {"_handler", "_service_factory"}
        }

    # ---- Capability helpers ----

    @property
    def capability_flags(self) -> ToolCapability:
        return ToolCapability(self.capabilities)

    def has_capability(self, cap: ToolCapability) -> bool:
        return bool(self.capabilities & cap.value)

    def add_capability(self, cap: ToolCapability):
        self.capabilities |= cap.value

    # ---- Serialisation ----

    def to_frontend_json(self) -> Dict[str, Any]:
        """Subset of metadata safe/useful for the frontend."""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "mode": self.mode.value,
            "capabilities": [c.name for c in ToolCapability if self.has_capability(c)],
            "tags": self.tags,
            "ui_type": self.ui_type.value,
            "ui_config": self.ui_config,
            "can_run_as_service": self.can_run_as_service,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "cost_hint": self.cost_hint,
            "requires_confirmation": self.requires_confirmation,
        }

    def to_agent_summary(self) -> str:
        """One-line summary for agent tool lists."""
        caps = ", ".join(c.name.lower() for c in ToolCapability if self.has_capability(c))
        return (
            f"{self.name} [{self.category.value}] - {self.description}"
            f"{f' (capabilities: {caps})' if caps else ''}"
        )


# ============================================================================
# TOOL CONTEXT - Injected into enhanced tools at call time
# ============================================================================

class ToolContext:
    """
    Runtime context injected into enhanced tool calls.
    Provides uniform access to Vera subsystems without tight coupling.

    Tools receive this as their first argument (similar to how existing tools
    receive `agent`). Legacy tools that accept `agent` still work because
    ToolContext wraps the agent and proxies attribute access.
    
    Usage inside a tool:
        def my_tool(ctx: ToolContext, query: str):
            # Memory
            results = ctx.memory_search(query)
            ctx.memory_save("found something", {"key": "val"})
            
            # Graph
            ctx.graph_upsert_entity("entity_1", "TypeA", props={"x": 1})
            ctx.graph_link("entity_1", "entity_2", "RELATES_TO")
            
            # Events
            ctx.emit("tool.progress", {"percent": 50})
            
            # Orchestrator
            task_id = ctx.submit_task("llm.fast", prompt="summarise this")
            
            # UI updates
            ctx.ui_push({"type": "log", "text": "scanning port 80..."})
            
            # Streaming
            yield "partial result 1"
            yield "partial result 2"
    """

    def __init__(
        self,
        agent=None,
        *,
        memory=None,
        orchestrator=None,
        event_bus=None,
        session_id: Optional[str] = None,
        tool_name: str = "",
        ui_channel: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ):
        self._agent = agent
        self._memory = memory
        self._orchestrator = orchestrator
        self._event_bus = event_bus
        self.session_id = session_id or (agent.sess.id if agent and hasattr(agent, "sess") else None)
        self.tool_name = tool_name
        self.ui_channel = ui_channel or f"tool.{tool_name}.ui"
        self.extra = extra or {}
        self._execution_id: Optional[str] = None
        self._start_time: Optional[float] = None

    # ---- Agent proxy (backwards compat) ----

    def __getattr__(self, name: str):
        """Proxy attribute access to underlying agent for backwards compat."""
        if name.startswith("_"):
            raise AttributeError(name)
        if self._agent is not None and hasattr(self._agent, name):
            return getattr(self._agent, name)
        raise AttributeError(f"ToolContext has no attribute '{name}' (agent proxy also failed)")

    @property
    def agent(self):
        """Direct access to the wrapped agent."""
        return self._agent

    # ---- Memory ----

    @property
    def mem(self):
        """HybridMemory instance."""
        if self._memory:
            return self._memory
        if self._agent and hasattr(self._agent, "mem"):
            return self._agent.mem
        return None

    def memory_search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Search vector + graph memory."""
        if self.mem and hasattr(self.mem, "focus_context") and self.session_id:
            return self.mem.focus_context(self.session_id, query, top_k=k)
        if self._agent and hasattr(self._agent, "vectorstore"):
            docs = self._agent.vectorstore.similarity_search(query, k=k)
            return [{"text": d.page_content, "metadata": d.metadata} for d in docs]
        return []

    def memory_save(self, text: str, metadata: Optional[Dict[str, Any]] = None,
                    node_type: str = "ToolOutput", promote: bool = False):
        """Save text to session memory with optional graph promotion."""
        if self.mem and self.session_id:
            return self.mem.add_session_memory(
                self.session_id, text, node_type,
                metadata=metadata, promote=promote,
            )
        return None

    # ---- Graph ----

    def graph_upsert_entity(self, entity_id: str, etype: str,
                            labels: Optional[List[str]] = None,
                            props: Optional[Dict[str, Any]] = None):
        """Upsert an entity in the knowledge graph."""
        if self.mem:
            return self.mem.upsert_entity(entity_id, etype, labels=labels, properties=props)
        logger.warning("graph_upsert_entity: no memory system available")
        return None

    def graph_link(self, src: str, dst: str, rel: str,
                   props: Optional[Dict[str, Any]] = None):
        """Create a relationship in the knowledge graph."""
        if self.mem:
            return self.mem.link(src, dst, rel, properties=props)
        logger.warning("graph_link: no memory system available")
        return None

    def graph_subgraph(self, seed_ids: List[str], depth: int = 2):
        """Extract subgraph around seed entities."""
        if self.mem:
            return self.mem.extract_subgraph(seed_ids, depth=depth)
        return {"nodes": [], "rels": []}

    # ---- Events ----

    def emit(self, event_type: str, data: Optional[Dict[str, Any]] = None):
        """Emit an event to the tool event bus."""
        if self._event_bus:
            self._event_bus.publish(event_type, {
                "tool": self.tool_name,
                "session_id": self.session_id,
                "timestamp": time.time(),
                **(data or {}),
            })

    def subscribe(self, event_type: str, callback: Callable):
        """Subscribe to events."""
        if self._event_bus:
            self._event_bus.subscribe(event_type, callback)

    # ---- UI ----

    def ui_push(self, payload: Dict[str, Any]):
        """
        Push a UI update to the frontend via the event bus.
        The frontend listens on the tool's UI channel.
        
        Common payload shapes:
            {"type": "log",    "text": "...", "level": "info"}
            {"type": "data",   "rows": [...], "columns": [...]}
            {"type": "status", "state": "running", "progress": 0.5}
            {"type": "chart",  "series": [...]}
            {"type": "clear"}
        """
        self.emit(self.ui_channel, payload)

    # ---- Orchestrator ----

    def submit_task(self, task_name: str, *args, **kwargs) -> Optional[str]:
        """Submit a task to the orchestrator."""
        if self._orchestrator:
            return self._orchestrator.submit_task(task_name, *args, **kwargs)
        logger.warning("submit_task: no orchestrator available")
        return None

    def wait_for_task(self, task_id: str, timeout: float = 30.0):
        """Wait for an orchestrator task result."""
        if self._orchestrator:
            return self._orchestrator.wait_for_result(task_id, timeout=timeout)
        return None

    # ---- Execution tracking ----

    def start_execution_tracking(self, target_node_id: Optional[str] = None):
        """Begin tracking graph nodes created during this tool execution."""
        self._execution_id = f"tool_exec_{self.tool_name}_{int(time.time())}"
        self._start_time = time.time()
        if self.mem and target_node_id:
            self.mem.create_tool_execution_node(
                target_node_id, self.tool_name,
                {"executed_at": time.time(), "input_summary": ""},
            )
        return self._execution_id

    def finish_execution_tracking(self, output: str = "", success: bool = True):
        """Finish tracking and record result."""
        if self.mem and self._execution_id:
            duration_ms = (time.time() - (self._start_time or time.time())) * 1000
            self.mem.create_tool_result_node(
                self._execution_id, output,
                {
                    "tool_name": self.tool_name,
                    "duration_ms": duration_ms,
                    "success": success,
                },
            )
        self._execution_id = None
        self._start_time = None


# ============================================================================
# DECORATORS
# ============================================================================

def enhanced_tool(
    name: str,
    description: str,
    *,
    category: ToolCategory = ToolCategory.UTILITY,
    mode: ToolMode = ToolMode.MULTIPURPOSE,
    capabilities: Union[ToolCapability, int] = ToolCapability.NONE,
    tags: Optional[List[str]] = None,
    ui_type: ToolUIType = ToolUIType.NONE,
    ui_config: Optional[Dict[str, Any]] = None,
    can_run_as_service: bool = False,
    service_config: Optional[Dict[str, Any]] = None,
    input_schema: Optional[Type[BaseModel]] = None,
    output_schema: Optional[Type[BaseModel]] = None,
    task_type: Optional[str] = None,
    priority: Optional[str] = None,
    estimated_duration: float = 5.0,
    requires_confirmation: bool = False,
    cost_hint: str = "low",
    version: str = "1.0.0",
    author: str = "vera",
):
    """
    Universal decorator for enhanced Vera tools.
    
    The decorated function receives a ToolContext as first arg (or `agent`
    for backwards compat). It may return a value or yield chunks.

    Usage:
        @enhanced_tool(
            "port_scanner",
            "Scan ports on a target host",
            category=ToolCategory.SECURITY,
            mode=ToolMode.MULTIPURPOSE,
            capabilities=ToolCapability.STREAMING | ToolCapability.SERVICE | ToolCapability.UI,
            ui_type=ToolUIType.CONSOLE,
            can_run_as_service=True,
            tags=["network", "scanning", "security"],
        )
        def port_scanner(ctx: ToolContext, target: str, ports: str = "1-1024"):
            for port in parse_ports(ports):
                result = scan(target, port)
                ctx.ui_push({"type": "log", "text": f"Port {port}: {result}"})
                ctx.graph_upsert_entity(f"port_{port}", "NetworkPort", props={"state": result})
                yield f"Port {port}: {result}"
    """
    # Normalise capability flags
    cap_value = capabilities.value if isinstance(capabilities, ToolCapability) else int(capabilities)

    # Auto-infer capabilities
    if can_run_as_service:
        cap_value |= ToolCapability.SERVICE.value
    if ui_type != ToolUIType.NONE:
        cap_value |= ToolCapability.UI.value

    descriptor = ToolDescriptor(
        name=name,
        description=description,
        version=version,
        category=category,
        mode=mode,
        capabilities=cap_value,
        tags=tags or [],
        ui_type=ui_type,
        ui_config=ui_config or {},
        can_run_as_service=can_run_as_service,
        service_config=service_config or {},
        input_schema=input_schema.model_json_schema() if input_schema else None,
        output_schema=output_schema.model_json_schema() if output_schema else None,
        task_type=task_type,
        priority=priority,
        estimated_duration=estimated_duration,
        requires_confirmation=requires_confirmation,
        cost_hint=cost_hint,
        author=author,
    )

    def decorator(func: Callable) -> Callable:
        # Auto-detect streaming
        if inspect.isgeneratorfunction(func) or inspect.isasyncgenfunction(func):
            descriptor.add_capability(ToolCapability.STREAMING)
        if inspect.iscoroutinefunction(func) or inspect.isasyncgenfunction(func):
            descriptor.add_capability(ToolCapability.ASYNC)

        # Attach descriptor
        func._tool_descriptor = descriptor
        descriptor._handler = func

        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        wrapper._tool_descriptor = descriptor
        return wrapper

    return decorator


# ---- Convenience shortcuts ----

def service_tool(name: str, description: str, **kwargs):
    """Shortcut for tools that run as background services."""
    kwargs.setdefault("mode", ToolMode.SERVICE)
    kwargs.setdefault("can_run_as_service", True)
    kwargs.setdefault("capabilities", ToolCapability.SERVICE | ToolCapability.STREAMING)
    kwargs.setdefault("ui_type", ToolUIType.MONITOR)
    return enhanced_tool(name, description, **kwargs)


def ui_tool(name: str, description: str, **kwargs):
    """Shortcut for UI-only tools."""
    kwargs.setdefault("mode", ToolMode.UI_ONLY)
    kwargs.setdefault("ui_type", ToolUIType.CONSOLE)
    return enhanced_tool(name, description, **kwargs)


def sensor_tool(name: str, description: str, **kwargs):
    """Shortcut for sensor/monitor pattern tools."""
    kwargs.setdefault("mode", ToolMode.SERVICE)
    kwargs.setdefault("can_run_as_service", True)
    kwargs.setdefault("capabilities",
        ToolCapability.SENSOR | ToolCapability.STREAMING |
        ToolCapability.SERVICE | ToolCapability.EVENT_EMITTER | ToolCapability.UI
    )
    kwargs.setdefault("ui_type", ToolUIType.MONITOR)
    return enhanced_tool(name, description, **kwargs)