"""
Vera Toolchain - Framework Integration
========================================
Makes ToolChainPlanner registry-aware without modifying toolchain.py itself.

Provides:
  - setup_toolchain_enhanced()  →  drop-in for setup_toolchain() that also
                                   wires the tool registry into the planner
  - RegistryAwareToolChainPlanner  →  thin subclass that overrides tool lookup
                                      to use the registry when available

Usage in vera.py / agent __init__:

    # Replace:
    from Vera.Toolchain.toolchain import setup_toolchain
    setup_toolchain(self)

    # With:
    from Vera.Toolchain.toolchain_integration import setup_toolchain_enhanced
    setup_toolchain_enhanced(self)

Everything else (task registrations, orchestrator wiring, adaptive / expert /
parallel modes) works unchanged because ToolChainPlanner's public API is
preserved exactly.
"""

from __future__ import annotations

import logging
from typing import Any, Iterator, List, Optional

from Vera.Toolchain.toolchain import ToolChainPlanner, setup_toolchain

logger = logging.getLogger("vera.toolchain.integration")


class RegistryAwareToolChainPlanner(ToolChainPlanner):
    """
    ToolChainPlanner subclass that integrates with the tool framework registry.

    Additional capabilities over the base class:
      - _find_tool() checks registry first (falls back to linear scan)
      - get_tools_for_mode() returns a filtered subset via the registry
      - _run_step() injects a ToolContext into @enhanced_tool decorated functions
      - execute_tool_chain() accepts an optional agent_type kwarg to filter
        the tool list per agent profile (e.g. "security", "coding")
    """

    def __init__(self, agent: Any, tools: List[Any]) -> None:
        super().__init__(agent, tools)
        self._registry = getattr(agent, "tool_registry", None)
        if self._registry:
            logger.info(
                "[RegistryAwareToolChainPlanner] Registry attached – "
                f"{len(self._registry.list_names())} tools indexed"
            )
        else:
            logger.info(
                "[RegistryAwareToolChainPlanner] No registry on agent – "
                "falling back to linear tool scan"
            )

    # -----------------------------------------------------------------------
    # Registry-backed tool lookup
    # -----------------------------------------------------------------------

    def _find_tool(self, name: str) -> Optional[Any]:
        """
        Look up a tool by name.
        Checks the registry first for O(1) lookup; falls back to the base
        class linear scan so legacy tools without registry entries still work.
        Suppressed LLM tool names are still handled by the base class.
        """
        # Let the base class handle suppressed LLM tool names first
        from Vera.Toolchain.toolchain import _SUPPRESSED_LLM_TOOL_NAMES
        if name in _SUPPRESSED_LLM_TOOL_NAMES:
            return None  # base class will route through LLMDispatcher

        if self._registry:
            tool = self._registry.get_langchain_tool(name)
            if tool is not None:
                return tool
            # Not in registry — fall through to linear scan for any tool that
            # was added to self.tools after the registry was built.

        return super()._find_tool(name)

    # -----------------------------------------------------------------------
    # ToolContext injection for @enhanced_tool functions
    # -----------------------------------------------------------------------

    def _run_step(
        self,
        tool_name: str,
        tool_input: Any,
        step_num: int,
        outputs: dict,
        label: str = "ToolChain",
    ) -> Iterator[str]:
        """
        Extends the base _run_step to inject a ToolContext when the tool
        function carries a _tool_descriptor (i.e. was decorated with
        @enhanced_tool).  Plain LangChain tools are unaffected.
        """
        from Vera.Toolchain.toolchain import _LLM_VIRTUAL_TOOL_NAME, _SUPPRESSED_LLM_TOOL_NAMES

        # LLM virtual tool – always delegate to base class
        is_llm = (
            tool_name == _LLM_VIRTUAL_TOOL_NAME
            or tool_name in _SUPPRESSED_LLM_TOOL_NAMES
        )
        if is_llm:
            yield from super()._run_step(tool_name, tool_input, step_num, outputs, label)
            return

        # Try to find the raw handler function for enhanced tools
        lc_tool = self._find_tool(tool_name)
        if lc_tool is None:
            yield from super()._run_step(tool_name, tool_input, step_num, outputs, label)
            return

        # Check if the underlying function has a _tool_descriptor
        handler_func = getattr(lc_tool, "func", None)
        if handler_func and hasattr(handler_func, "_tool_descriptor"):
            # Inject ToolContext via the agent's factory
            create_ctx = getattr(self.agent, "create_tool_context", None)
            if create_ctx:
                ctx = create_ctx(tool_name)
                # Wrap the handler to pre-supply ctx as first positional arg
                import functools
                from Vera.Toolchain.toolchain import _resolve_input, _call_tool

                resolved = _resolve_input(tool_input, step_num, outputs)

                def _ctx_aware_call(tool_obj, inp):
                    """Call handler with ctx injected as first arg."""
                    fn = handler_func
                    if isinstance(inp, dict):
                        return fn(ctx, **inp)
                    return fn(ctx, inp)

                from Vera.Toolchain.toolchain import _extract_text
                try:
                    result = _ctx_aware_call(lc_tool, resolved)
                    if hasattr(result, "__iter__") and not isinstance(result, (str, bytes, dict)):
                        for chunk in result:
                            yield _extract_text(chunk)
                    else:
                        yield str(result)
                except Exception as exc:
                    import traceback
                    yield f"[{label}] ERROR in {tool_name}: {exc}\n{traceback.format_exc()}"
                return

        # Not enhanced – standard base class execution
        yield from super()._run_step(tool_name, tool_input, step_num, outputs, label)

    # -----------------------------------------------------------------------
    # Agent-type filtered tool list
    # -----------------------------------------------------------------------

    def get_tools_for_agent_type(self, agent_type: str) -> List[Any]:
        """
        Return a filtered tool list for the given agent type profile.
        Falls back to the full tool list if no registry is available.

        agent_type: "conversation" | "coding" | "security" |
                    "research" | "data" | "planning" | "monitoring"
        """
        if self._registry:
            filtered = self._registry.get_for_agent(agent_type=agent_type)
            if filtered:
                logger.info(
                    f"[RegistryAware] agent_type='{agent_type}' → "
                    f"{len(filtered)} tools"
                )
                return filtered
        return self.tools

    # -----------------------------------------------------------------------
    # Override execute_tool_chain to accept agent_type kwarg
    # -----------------------------------------------------------------------

    def execute_tool_chain(  # type: ignore[override]
        self,
        query: str,
        plan=None,
        mode: str = "sequential",
        strategy: str = "default",
        expert: bool = False,
        agent_type: Optional[str] = None,
        **kwargs,
    ) -> Iterator[str]:
        """
        Extended version that accepts an optional agent_type kwarg to
        temporarily swap self.tools to a filtered subset for the duration
        of the execution.

        All other kwargs are forwarded to the base class unchanged.
        """
        if agent_type and self._registry:
            filtered = self.get_tools_for_agent_type(agent_type)
            original_tools = self.tools
            self.tools = filtered
            try:
                yield from super().execute_tool_chain(
                    query, plan=plan, mode=mode, strategy=strategy,
                    expert=expert, **kwargs
                )
            finally:
                self.tools = original_tools
        else:
            yield from super().execute_tool_chain(
                query, plan=plan, mode=mode, strategy=strategy,
                expert=expert, **kwargs
            )


# ---------------------------------------------------------------------------
# Setup helper
# ---------------------------------------------------------------------------

def setup_toolchain_enhanced(vera_instance: Any) -> "RegistryAwareToolChainPlanner":
    """
    Drop-in replacement for setup_toolchain() that uses the registry-aware
    planner when the tool framework has been loaded.

    Call AFTER load_tools() / EnhancedToolLoader() so that
    vera_instance.tool_registry is already set.

    Sets up:
        vera.toolchain            – RegistryAwareToolChainPlanner
        vera.toolchain_expert     – same instance (alias)
        vera._adaptive_toolchain  – same instance (alias)

    Usage in Vera.__init__:
        # Load tools first
        from Vera.Toolchain.ToolFramework.bridge import load_tools
        self.tools = load_tools(self)

        # Then set up the toolchain
        from Vera.Toolchain.toolchain_integration import setup_toolchain_enhanced
        setup_toolchain_enhanced(self)
    """
    has_registry = hasattr(vera_instance, "tool_registry")

    if has_registry:
        planner = RegistryAwareToolChainPlanner(
            vera_instance, vera_instance.tools
        )
        logger.info("Toolchain: RegistryAwareToolChainPlanner ✓")
    else:
        # Graceful degradation — no registry yet, use the plain planner
        logger.warning(
            "setup_toolchain_enhanced: no tool_registry found on agent. "
            "Call load_tools() before setup_toolchain_enhanced(). "
            "Falling back to plain ToolChainPlanner."
        )
        planner = ToolChainPlanner(vera_instance, vera_instance.tools)

    vera_instance.toolchain = planner
    vera_instance.toolchain_expert = planner
    vera_instance._adaptive_toolchain = planner

    logger.info(
        "Toolchain initialised: sequential / adaptive / expert / parallel / hybrid"
    )
    return planner