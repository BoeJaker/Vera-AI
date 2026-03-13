
from __future__ import annotations

"""
Vera Tool Framework - Core
============================
Base classes, enums, decorators, descriptors, and the ToolContext
that gives every tool uniform access to memory, orchestrator, events, and UI.

SUCCESS/FAILURE CHECKS ARE BUILT IN
-------------------------------------
Every tool call is automatically classified.  No external wrapper or extra
code is needed:

  • @enhanced_tool  — the wrapper catches exceptions and classifies the output
                      of every call via _classify_output().  Emits events on
                      the tool event bus and writes to the Vera logger.

  • ToolContext     — finish_execution_tracking() records success/failure in
                      the knowledge graph so history is queryable.  Legacy
                      tools that call it manually also get classification.

  • _classify_output() — shared heuristic: empty → EMPTY, error prefix / 
                         traceback text / known failure phrases → FAILURE,
                         otherwise → SUCCESS.

  • CallResult / CallStatus — lightweight dataclasses attached to every tool
                              invocation.  Available to callers that want to
                              inspect outcomes without parsing text.

Design Goals:
    - Every existing tool works unchanged (backwards compat)
    - New tools opt-in to capabilities via decorators
    - Tools self-describe their category, mode, UI, and capabilities
    - ToolContext is the single injection point for system services
"""

"""
TODO
Full tool output streaming

"""

import asyncio
import inspect
import logging
import re
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
# RESULT CLASSIFICATION  (built into the framework, not a separate module)
# ============================================================================

class CallStatus(Enum):
    SUCCESS = auto()   # Completed with meaningful output
    FAILURE = auto()   # Exception raised or error detected in output
    EMPTY   = auto()   # Completed without error but produced no output


@dataclass
class CallResult:
    """
    Outcome of a single tool call.

    Automatically attached to every ``@enhanced_tool`` invocation as
    ``wrapper._last_result`` and emitted to the event bus.

    Attributes
    ----------
    status:   SUCCESS | FAILURE | EMPTY
    name:     Tool name.
    output:   Collected output text (may be empty on FAILURE/EMPTY).
    error:    Exception message if status is FAILURE, else None.
    duration: Wall-clock seconds.
    chunks:   Number of yielded chunks (0 for non-streaming calls).
    """
    status:   CallStatus
    name:     str
    output:   str            = ""
    error:    Optional[str]  = None
    duration: float          = 0.0
    chunks:   int            = 0

    @property
    def ok(self) -> bool:
        return self.status == CallStatus.SUCCESS

    @property
    def failed(self) -> bool:
        return self.status in (CallStatus.FAILURE, CallStatus.EMPTY)

    def summary(self) -> str:
        icon = "✓" if self.ok else ("⚠" if self.status == CallStatus.EMPTY else "✗")
        detail = f"{len(self.output)} chars" if self.output else "no output"
        err = f" | {self.error[:80]!r}" if self.error else ""
        return (
            f"[{icon}] tool:{self.name} "
            f"status={self.status.name} {detail} "
            f"dur={self.duration:.2f}s chunks={self.chunks}{err}"
        )


# ---------------------------------------------------------------------------
# Heuristic output classifier
# ---------------------------------------------------------------------------

_FAILURE_PREFIXES = (
    "error:", "error executing", "error in",
    "traceback (most recent call last)",
    "exception:", "failed:", "tool not found",
    "tool execution failed", "invalid input",
    "connection refused", "timeout",
    "permission denied", "no route to host",
)

_FAILURE_PHRASES = (
    "pull model manifest: file does not exist",
    "context length exceeded",
    "cuda out of memory",
    "segmentation fault",
)

_TRACEBACK_RE = re.compile(
    r"traceback \(most recent call last\)"
    r"|raise \w+Error"
    r"|^\s+File \".+\", line \d+",
    re.IGNORECASE | re.MULTILINE,
)


def _classify_output(text: str) -> CallStatus:
    """
    Classify tool output text as SUCCESS, EMPTY, or FAILURE.

    Rules (in order):
      1. Empty / whitespace-only  → EMPTY
      2. Starts with error prefix → FAILURE
      3. Contains Python traceback → FAILURE
      4. Contains known failure phrase → FAILURE
      5. Otherwise               → SUCCESS
    """
    stripped = text.strip() if text else ""
    if not stripped:
        return CallStatus.EMPTY

    lower = stripped.lower()
    if any(lower.startswith(p) for p in _FAILURE_PREFIXES):
        return CallStatus.FAILURE
    if _TRACEBACK_RE.search(stripped):
        return CallStatus.FAILURE
    if any(p in lower for p in _FAILURE_PHRASES):
        return CallStatus.FAILURE
    return CallStatus.SUCCESS


def _emit_result(result: CallResult, event_bus, vera_logger) -> None:
    """
    Emit a CallResult to the event bus and unified logger.
    Never raises — classification must never break execution.
    """
    try:
        if vera_logger:
            if result.ok:
                vera_logger.debug(result.summary())
            elif result.status == CallStatus.EMPTY:
                vera_logger.warning(result.summary())
            else:
                vera_logger.error(result.summary())
    except Exception:
        pass

    try:
        if event_bus:
            channel = f"result.tool.{'success' if result.ok else 'failure'}"
            event_bus.publish(channel, {
                "name":       result.name,
                "status":     result.status.name,
                "duration":   result.duration,
                "chunks":     result.chunks,
                "error":      result.error,
                "output_len": len(result.output),
            })
    except Exception:
        pass


# ============================================================================
# ENUMS - Capability flags, categories, modes
# ============================================================================

class ToolCapability(Flag):
    """
    Bitwise-combinable capability flags.
    A tool can have multiple capabilities simultaneously.
    """
    NONE           = 0
    STREAMING      = auto()
    SERVICE        = auto()
    UI             = auto()
    ASYNC          = auto()
    MEMORY_READ    = auto()
    MEMORY_WRITE   = auto()
    GRAPH_BUILD    = auto()
    ORCHESTRATED   = auto()
    SENSOR         = auto()
    PARSER         = auto()
    HTTP_ENDPOINT  = auto()
    EVENT_EMITTER  = auto()
    EVENT_LISTENER = auto()
    IDEMPOTENT     = auto()


class ToolCategory(str, Enum):
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
    LLM_ONLY    = "llm_only"
    UI_ONLY     = "ui_only"
    MULTIPURPOSE = "multipurpose"
    ONE_SHOT    = "one_shot"
    SERVICE     = "service"
    INTERNAL    = "internal"


class ToolUIType(str, Enum):
    NONE     = "none"
    CONSOLE  = "console"
    TABLE    = "table"
    CHART    = "chart"
    FORM     = "form"
    MONITOR  = "monitor"
    MAP      = "map"
    GRAPH    = "graph"
    TERMINAL = "terminal"
    CUSTOM   = "custom"


# ============================================================================
# TOOL DESCRIPTOR
# ============================================================================

class ToolDescriptor(BaseModel):
    """Complete metadata for an enhanced tool."""
    name: str
    description: str
    version: str = "1.0.0"

    category: ToolCategory = ToolCategory.UTILITY
    mode: ToolMode = ToolMode.MULTIPURPOSE
    capabilities: int = 0
    tags: List[str] = Field(default_factory=list)

    ui_type: ToolUIType = ToolUIType.NONE
    ui_config: Dict[str, Any] = Field(default_factory=dict)

    can_run_as_service: bool = False
    service_config: Dict[str, Any] = Field(default_factory=dict)

    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None

    task_type: Optional[str] = None
    priority: Optional[str] = None
    estimated_duration: float = 5.0

    author: str = "vera"
    requires_confirmation: bool = False
    cost_hint: str = "low"

    _handler: Optional[Callable] = None
    _service_factory: Optional[Callable] = None

    class Config:
        arbitrary_types_allowed = True

    @property
    def capability_flags(self) -> ToolCapability:
        return ToolCapability(self.capabilities)

    def has_capability(self, cap: ToolCapability) -> bool:
        return bool(self.capabilities & cap.value)

    def add_capability(self, cap: ToolCapability):
        self.capabilities |= cap.value

    def to_frontend_json(self) -> Dict[str, Any]:
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
        caps = ", ".join(c.name.lower() for c in ToolCapability if self.has_capability(c))
        return (
            f"{self.name} [{self.category.value}] - {self.description}"
            f"{f' (capabilities: {caps})' if caps else ''}"
        )


# ============================================================================
# TOOL CONTEXT
# ============================================================================

class ToolContext:
    """
    Runtime context injected into enhanced tool calls.

    Provides uniform access to memory, graph, events, orchestrator, and UI.
    Proxies attribute access to the underlying agent for backwards compat.

    SUCCESS/FAILURE TRACKING
    ------------------------
    finish_execution_tracking() is the canonical place to record the outcome
    of a tool run.  It writes a result node into the knowledge graph and emits
    a CallResult event.  The @enhanced_tool wrapper calls it automatically;
    legacy tools can call it explicitly.
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
        self._agent       = agent
        self._memory      = memory
        self._orchestrator = orchestrator
        self._event_bus   = event_bus
        self.session_id   = session_id or (
            agent.sess.id if agent and hasattr(agent, "sess") else None
        )
        self.tool_name  = tool_name
        self.ui_channel = ui_channel or f"tool.{tool_name}.ui"
        self.extra      = extra or {}

        # Execution tracking
        self._execution_id: Optional[str] = None
        self._start_time:   Optional[float] = None

        # Last result (set by finish_execution_tracking)
        self.last_result: Optional[CallResult] = None

    # ---- Agent proxy ----

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        if self._agent is not None and hasattr(self._agent, name):
            return getattr(self._agent, name)
        raise AttributeError(
            f"ToolContext has no attribute '{name}' (agent proxy also failed)"
        )

    @property
    def agent(self):
        return self._agent

    # ---- Logger shortcut ----

    @property
    def _vera_logger(self):
        """Return the unified Vera logger if available."""
        return getattr(self._agent, "logger", None)

    # ---- Memory ----

    @property
    def mem(self):
        if self._memory:
            return self._memory
        if self._agent and hasattr(self._agent, "mem"):
            return self._agent.mem
        return None

    def memory_search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        if self.mem and hasattr(self.mem, "focus_context") and self.session_id:
            return self.mem.focus_context(self.session_id, query, top_k=k)
        if self._agent and hasattr(self._agent, "vectorstore"):
            docs = self._agent.vectorstore.similarity_search(query, k=k)
            return [{"text": d.page_content, "metadata": d.metadata} for d in docs]
        return []

    def memory_save(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        node_type: str = "ToolOutput",
        promote: bool = False,
    ):
        if self.mem and self.session_id:
            return self.mem.add_session_memory(
                self.session_id, text, node_type,
                metadata=metadata, promote=promote,
            )
        return None

    # ---- Graph ----

    def graph_upsert_entity(
        self,
        entity_id: str,
        etype: str,
        labels: Optional[List[str]] = None,
        props: Optional[Dict[str, Any]] = None,
    ):
        if self.mem:
            return self.mem.upsert_entity(entity_id, etype, labels=labels, properties=props)
        logger.warning("graph_upsert_entity: no memory system available")
        return None

    def graph_link(
        self,
        src: str,
        dst: str,
        rel: str,
        props: Optional[Dict[str, Any]] = None,
    ):
        if self.mem:
            return self.mem.link(src, dst, rel, properties=props)
        logger.warning("graph_link: no memory system available")
        return None

    def graph_subgraph(self, seed_ids: List[str], depth: int = 2):
        if self.mem:
            return self.mem.extract_subgraph(seed_ids, depth=depth)
        return {"nodes": [], "rels": []}

    # ---- Events ----

    def emit(self, event_type: str, data: Optional[Dict[str, Any]] = None):
        if self._event_bus:
            self._event_bus.publish(event_type, {
                "tool":       self.tool_name,
                "session_id": self.session_id,
                "timestamp":  time.time(),
                **(data or {}),
            })

    def subscribe(self, event_type: str, callback: Callable):
        if self._event_bus:
            self._event_bus.subscribe(event_type, callback)

    # ---- UI ----

    def ui_push(self, payload: Dict[str, Any]):
        self.emit(self.ui_channel, payload)

    # ---- Orchestrator ----

    def submit_task(self, task_name: str, *args, **kwargs) -> Optional[str]:
        if self._orchestrator:
            return self._orchestrator.submit_task(task_name, *args, **kwargs)
        logger.warning("submit_task: no orchestrator available")
        return None

    def wait_for_task(self, task_id: str, timeout: float = 30.0):
        if self._orchestrator:
            return self._orchestrator.wait_for_result(task_id, timeout=timeout)
        return None

    # ---- Execution tracking + result classification ----

    def start_execution_tracking(self, target_node_id: Optional[str] = None):
        """Begin tracking this tool's execution."""
        self._execution_id = f"tool_exec_{self.tool_name}_{int(time.time())}"
        self._start_time   = time.time()
        if self.mem and target_node_id:
            try:
                self.mem.create_tool_execution_node(
                    target_node_id, self.tool_name,
                    {"executed_at": time.time(), "input_summary": ""},
                )
            except Exception:
                pass
        return self._execution_id

    def finish_execution_tracking(
        self,
        output: str = "",
        success: Optional[bool] = None,
        error: Optional[str] = None,
        chunks: int = 0,
    ) -> CallResult:
        """
        Finish tracking and classify the result.

        Called automatically by the @enhanced_tool wrapper.
        Legacy tools can call this explicitly to get the same classification.

        Parameters
        ----------
        output:  Full collected output text.
        success: Override classification (None = auto-detect from text).
        error:   Error string if an exception was caught externally.
        chunks:  Streamed chunk count (for streaming tools).

        Returns
        -------
        CallResult  (also stored as self.last_result)
        """
        duration = time.time() - (self._start_time or time.time())

        # Determine status
        if error is not None:
            status = CallStatus.FAILURE
        elif success is True:
            status = CallStatus.SUCCESS
        elif success is False:
            status = CallStatus.FAILURE
        else:
            # Auto-classify from output text
            status = _classify_output(output)

        result = CallResult(
            status   = status,
            name     = self.tool_name,
            output   = output,
            error    = error,
            duration = duration,
            chunks   = chunks,
        )

        self.last_result = result

        # Record in knowledge graph
        if self.mem and self._execution_id:
            try:
                self.mem.create_tool_result_node(
                    self._execution_id,
                    output,
                    {
                        "tool_name": self.tool_name,
                        "duration_ms": duration * 1000,
                        "success":     result.ok,
                        "status":      status.name,
                        "error":       error,
                        "chunks":      chunks,
                    },
                )
            except Exception:
                pass

        # Emit to event bus + logger
        _emit_result(result, self._event_bus, self._vera_logger)

        # Reset tracking state
        self._execution_id = None
        self._start_time   = None

        return result


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

    SUCCESS/FAILURE CLASSIFICATION IS AUTOMATIC
    ---------------------------------------------
    The generated wrapper:
      1. Calls start_execution_tracking() on the injected ToolContext.
      2. Runs the tool function, collecting all yielded chunks.
      3. On normal completion: classifies the output via _classify_output()
         and calls finish_execution_tracking(output, chunks=N).
      4. On exception: calls finish_execution_tracking(error=str(exc)),
         then re-raises so callers see the original exception unchanged.

    Tools do NOT need to call finish_execution_tracking() themselves unless
    they want to record intermediate results mid-stream.
    """
    cap_value = capabilities.value if isinstance(capabilities, ToolCapability) else int(capabilities)

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
        is_generator = inspect.isgeneratorfunction(func)
        is_async_gen = inspect.isasyncgenfunction(func)
        is_async     = inspect.iscoroutinefunction(func)

        if is_generator or is_async_gen:
            descriptor.add_capability(ToolCapability.STREAMING)
        if is_async or is_async_gen:
            descriptor.add_capability(ToolCapability.ASYNC)

        func._tool_descriptor = descriptor
        descriptor._handler   = func

        if is_generator:
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Extract ToolContext from first positional arg if present
                ctx: Optional[ToolContext] = (
                    args[0] if args and isinstance(args[0], ToolContext) else None
                )
                if ctx:
                    ctx.start_execution_tracking()

                collected: List[str] = []
                chunks    = 0
                error_str: Optional[str] = None

                try:
                    for chunk in func(*args, **kwargs):
                        text = str(chunk) if chunk is not None else ""
                        collected.append(text)
                        chunks += 1
                        yield chunk  # pass-through untouched
                except Exception as exc:
                    error_str = f"{type(exc).__name__}: {exc}"
                    if ctx:
                        ctx.finish_execution_tracking(
                            output="".join(collected),
                            error=error_str,
                            chunks=chunks,
                        )
                    raise
                else:
                    if ctx:
                        ctx.finish_execution_tracking(
                            output="".join(collected),
                            chunks=chunks,
                        )

        else:
            @wraps(func)
            def wrapper(*args, **kwargs):
                ctx: Optional[ToolContext] = (
                    args[0] if args and isinstance(args[0], ToolContext) else None
                )
                if ctx:
                    ctx.start_execution_tracking()

                error_str: Optional[str] = None
                output    = ""

                try:
                    result = func(*args, **kwargs)
                    output = str(result) if result is not None else ""
                    return result
                except Exception as exc:
                    error_str = f"{type(exc).__name__}: {exc}"
                    raise
                finally:
                    if ctx:
                        ctx.finish_execution_tracking(
                            output=output,
                            error=error_str,
                        )

        wrapper._tool_descriptor = descriptor
        return wrapper

    return decorator


# ---- Convenience shortcuts (unchanged) ----

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