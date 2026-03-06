"""
Toolchain Task Registrations
==============================
All toolchain orchestrator tasks in one file.

Previously split across:
  - toolchain_tasks_enhanced.py  (STEP_BY_STEP / PARALLEL / ADAPTIVE modes
                                   via EnhancedToolChainPlanner)
  - toolchain_tasks_adaptive.py  (ADAPTIVE mode via AdaptiveToolChainPlanner)

Now all modes route through the single unified ToolChainPlanner exposed on
``vera_instance.toolchain`` (set up by ``setup_toolchain()`` in vera.py).

Task name → mode mapping
  toolchain.execute              sequential  (default, existing wiring)
  toolchain.execute.adaptive     adaptive    (step-by-step, feeds output back)
  toolchain.execute.parallel     parallel    (concurrent independent branches)
  toolchain.execute.expert       expert      (5-stage domain-expert pipeline)
  toolchain.execute.hybrid       hybrid      (expert → sequential fallback)
  toolchain.plan                 —           (plan only, no execution)
"""

from Vera.Orchestration.orchestration import task, TaskType, Priority
from Vera.Logging.logging import LogContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _planner(vera_instance):
    """
    Return the unified ToolChainPlanner from the vera instance.
    If it has not been set up yet (e.g. during tests) create it on demand.
    """
    if not hasattr(vera_instance, "toolchain") or vera_instance.toolchain is None:
        from Vera.Toolchain.toolchain import setup_toolchain
        setup_toolchain(vera_instance)
    return vera_instance.toolchain


def _extract_chunk_text(chunk) -> str:
    """Normalise any chunk type to a plain string."""
    if chunk is None:
        return ""
    if isinstance(chunk, str):
        return chunk
    if isinstance(chunk, dict):
        for key in ("text", "content", "message", "data", "output", "delta"):
            if key in chunk and chunk[key] is not None:
                return str(chunk[key])
        return str(chunk)
    for attr in ("text", "content"):
        val = getattr(chunk, attr, None)
        if val is not None:
            return str(val)
    return str(chunk)


def _run_task(vera_instance, query, mode, task_name, extra_kwargs=None):
    """
    Shared generator body for all toolchain tasks.
    Handles logging, timing, error reporting, and streaming.

    Args:
        vera_instance: The running Vera agent.
        query:         User goal / request string.
        mode:          ExecutionMode string ("sequential", "adaptive", etc.)
        task_name:     Task identifier for log context.
        extra_kwargs:  Extra kwargs forwarded to execute_tool_chain.

    Yields:
        str chunks.
    """
    logger  = getattr(vera_instance, "logger", None)
    context = LogContext(extra={
        "component": "task",
        "task":         task_name,
        "mode":         mode,
        "query_length": len(query),
        **(extra_kwargs or {}),
    })

    if logger:
        logger.info(f"🔧 Toolchain [{mode}] starting", context=context)
        logger.start_timer(task_name)

    planner    = _planner(vera_instance)
    chunk_count = 0

    try:
        for chunk in planner.execute_tool_chain(
            query,
            mode=mode,
            **(extra_kwargs or {}),
        ):
            text = _extract_chunk_text(chunk)
            chunk_count += 1
            yield text

        if logger:
            duration = logger.stop_timer(task_name, context=context)
            logger.success(
                f"Toolchain [{mode}] complete | {chunk_count} chunks",
                context=LogContext(extra={
                    **context.extra,
                    "chunk_count": chunk_count,
                    "duration":    duration,
                }),
            )

    except Exception as exc:
        if logger:
            duration = logger.stop_timer(task_name, context=context)
            logger.error(
                f"Toolchain [{mode}] failed: {type(exc).__name__}: {exc}",
                exc_info=True,
                context=LogContext(extra={
                    **context.extra,
                    "chunk_count": chunk_count,
                    "duration":    duration,
                    "error":       str(exc),
                }),
            )
        yield f"\n[ Toolchain ] ✗ Error ({mode}): {exc}\n"
        raise


# ---------------------------------------------------------------------------
# Sequential  (default)
# ---------------------------------------------------------------------------

@task(
    "toolchain.execute",
    task_type=TaskType.TOOL,
    priority=Priority.HIGH,
    estimated_duration=60.0,
)
def toolchain_execute(vera_instance, query: str, plan=None, strategy: str = "default"):
    """
    Sequential toolchain execution (default mode).

    Plans all steps up-front, then executes them in order.
    Includes error recovery and goal-check replanning.

    Args:
        query:    The task to accomplish.
        plan:     Optional pre-built plan list (skips planning phase).
        strategy: Hint string ("default", "comprehensive", etc.).
                  Maps to a mode via ToolChainPlanner._STRATEGY_TO_MODE.
    """
    yield from _run_task(
        vera_instance, query,
        mode="sequential",
        task_name="toolchain.execute",
        extra_kwargs={"plan": plan, "strategy": strategy},
    )


# ---------------------------------------------------------------------------
# Adaptive  (step-by-step, feeds output back into next planning decision)
# ---------------------------------------------------------------------------

@task(
    "toolchain.execute_adaptive",      # legacy name kept for backward compat
    task_type=TaskType.TOOL,
    priority=Priority.HIGH,
    estimated_duration=60.0,
)
def toolchain_execute_adaptive(vera_instance, query: str, max_steps: int = 20):
    """
    Adaptive step-by-step toolchain execution.

    Plans one tool at a time, feeding each output back into the next
    planning decision.  Terminates when the LLM returns DONE or max_steps
    is reached.

    Args:
        query:     The task to accomplish.
        max_steps: Hard cap on iterations (default 20).
    """
    yield from _run_task(
        vera_instance, query,
        mode="adaptive",
        task_name="toolchain.execute_adaptive",
        extra_kwargs={"max_steps": max_steps},
    )


# Also register under the newer dot-separated name for consistency
@task(
    "toolchain.execute.adaptive",
    task_type=TaskType.TOOL,
    priority=Priority.HIGH,
    estimated_duration=60.0,
)
def toolchain_execute_adaptive_dotted(vera_instance, query: str, max_steps: int = 20):
    """Alias of toolchain.execute_adaptive (dot-separated naming convention)."""
    yield from _run_task(
        vera_instance, query,
        mode="adaptive",
        task_name="toolchain.execute.adaptive",
        extra_kwargs={"max_steps": max_steps},
    )


# ---------------------------------------------------------------------------
# Parallel  (concurrent independent branches)
# ---------------------------------------------------------------------------

@task(
    "toolchain.execute.parallel",
    task_type=TaskType.TOOL,
    priority=Priority.HIGH,
    estimated_duration=45.0,
)
def toolchain_execute_parallel(vera_instance, query: str, max_workers: int = 6):
    """
    Parallel toolchain execution.

    Analyses the plan for dependency-free steps and runs them concurrently
    using a thread pool.  Falls back to sequential within dependent groups.

    Args:
        query:       The task to accomplish.
        max_workers: Thread pool size (default 6).
    """
    yield from _run_task(
        vera_instance, query,
        mode="parallel",
        task_name="toolchain.execute.parallel",
        extra_kwargs={"max_workers": max_workers},
    )


# ---------------------------------------------------------------------------
# Expert  (5-stage domain-expert pipeline)
# ---------------------------------------------------------------------------

@task(
    "toolchain.execute.expert",
    task_type=TaskType.TOOL,
    priority=Priority.HIGH,
    estimated_duration=90.0,
)
def toolchain_execute_expert(vera_instance, query: str):
    """
    Expert toolchain execution (5-stage domain pipeline).

    Stages:
      1. Domain triage   – identifies relevant technical domains
      2. Tool filtering  – narrows tool list to domain-relevant tools
      3. Expert planning – plans via tool-agent router (tool list always visible)
      4. Validation      – corrects any hallucinated tool names
      5. Execution       – runs the validated plan with streaming output

    Args:
        query: The task to accomplish.
    """
    yield from _run_task(
        vera_instance, query,
        mode="expert",
        task_name="toolchain.execute.expert",
    )


# ---------------------------------------------------------------------------
# Hybrid  (expert → sequential fallback)
# ---------------------------------------------------------------------------

@task(
    "toolchain.execute.hybrid",
    task_type=TaskType.TOOL,
    priority=Priority.HIGH,
    estimated_duration=75.0,
)
def toolchain_execute_hybrid(vera_instance, query: str):
    """
    Hybrid toolchain execution.

    Attempts expert mode first.  If expert mode produces errors, falls
    back automatically to sequential execution.

    Args:
        query: The task to accomplish.
    """
    yield from _run_task(
        vera_instance, query,
        mode="hybrid",
        task_name="toolchain.execute.hybrid",
    )


# ---------------------------------------------------------------------------
# Plan-only  (returns plan without executing)
# ---------------------------------------------------------------------------

@task(
    "toolchain.plan",
    task_type=TaskType.TOOL,
    priority=Priority.NORMAL,
    estimated_duration=10.0,
)
def toolchain_plan(vera_instance, query: str):
    """
    Generate a sequential execution plan without running it.

    Streams planning thoughts as they arrive, then yields the final plan
    as a JSON string.  Useful for previewing what the toolchain would do.

    Args:
        query: The task to plan for.

    Yields:
        str chunks (planning thoughts + final JSON plan).
    """
    import json

    logger  = getattr(vera_instance, "logger", None)
    context = LogContext(extra={
        "component":    "task",
        "task":         "toolchain.plan",
        "query_length": len(query),
    })

    if logger:
        logger.info("📋 Toolchain planning (no execution)", context=context)
        logger.start_timer("toolchain.plan")

    planner     = _planner(vera_instance)
    chunk_count = 0
    final_plan  = None

    try:
        for item in planner.plan_tool_chain(query):
            chunk_count += 1
            if isinstance(item, list):
                # This is the final plan object yielded at the end of the generator
                final_plan = item
                yield "\n[ Toolchain Plan ]\n"
                yield json.dumps(final_plan, indent=2, default=str)
                yield "\n"
            else:
                yield _extract_chunk_text(item)

        if logger:
            step_count = len(final_plan) if final_plan else 0
            duration   = logger.stop_timer("toolchain.plan", context=context)
            logger.success(
                f"Planning complete | {step_count} steps | {chunk_count} chunks",
                context=LogContext(extra={
                    **context.extra,
                    "step_count":  step_count,
                    "chunk_count": chunk_count,
                    "duration":    duration,
                }),
            )

    except Exception as exc:
        if logger:
            duration = logger.stop_timer("toolchain.plan", context=context)
            logger.error(
                f"Planning failed: {type(exc).__name__}: {exc}",
                exc_info=True,
                context=LogContext(extra={
                    **context.extra,
                    "duration": duration,
                    "error":    str(exc),
                }),
            )
        yield f"\n[ Toolchain ] ✗ Planning error: {exc}\n"
        raise