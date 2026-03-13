"""
Toolchain Monitor Wrapper
==========================
Wraps the unified ToolChainPlanner with WebSocket broadcast monitoring.

Supports:
  - sequential:  plan upfront → execute in order → flowchart renders all steps at once
  - adaptive:    plan one step at a time → flowchart renders each step as it appears
  - parallel:    identify independent branches → flowchart renders branched paths
  - expert/hybrid: like sequential with richer stage info

WebSocket event catalogue
--------------------------
execution_started   { execution_id, query, mode, strategy }
plan                { plan, total_steps }              ← full plan (sequential/expert)
step_discovered     { step_number, tool_name, input, mode:"adaptive" }  ← adaptive live step
step_input_updated  { step_number, input, mode }       ← adaptive: real input resolved on separate line
step_started        { step_number, tool_name, execution_id }
step_output         { step_number, chunk }
step_completed      { step_number, output }
step_failed         { step_number, error }
execution_completed { execution_id }
execution_failed    { error, execution_id }
parallel_branches   { branches: [[step,...], ...] }    ← parallel branch layout
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional, Tuple

logger = logging.getLogger(__name__)

from Vera.ChatUI.api.session import (
    active_toolchains,
    sessions,
    toolchain_executions,
    websocket_connections,
)

# ============================================================================
# EVENT LOOP CAPTURE
# ============================================================================

_main_loop: Optional[asyncio.AbstractEventLoop] = None


def set_main_loop() -> None:
    global _main_loop
    try:
        _main_loop = asyncio.get_event_loop()
        logger.info(f"[Monitor] Captured main event loop: {id(_main_loop)}")
    except RuntimeError as exc:
        logger.warning(f"[Monitor] Could not capture main event loop: {exc}")


def get_main_loop() -> Optional[asyncio.AbstractEventLoop]:
    return _main_loop


# ============================================================================
# THREAD-SAFE BROADCAST
# ============================================================================

def schedule_broadcast(
    session_id: str,
    event_type: str,
    data: Dict[str, Any],
) -> None:
    async def _broadcast() -> None:
        connections = websocket_connections.get(session_id, [])
        if not connections:
            return
        payload = {
            "type":      event_type,
            "data":      data,
            "timestamp": datetime.utcnow().isoformat(),
        }
        disconnected = []
        for ws in connections:
            try:
                await ws.send_json(payload)
            except Exception as exc:
                logger.warning(f"[Monitor] WebSocket send failed: {exc}")
                disconnected.append(ws)
        for ws in disconnected:
            try:
                connections.remove(ws)
            except ValueError:
                pass

    loop = _main_loop
    if loop and not loop.is_closed():
        try:
            asyncio.run_coroutine_threadsafe(_broadcast(), loop)
        except Exception as exc:
            logger.error(f"[Monitor] Failed to schedule broadcast '{event_type}': {exc}")
    else:
        logger.warning(
            f"[Monitor] Main loop not available for event '{event_type}' "
            f"(session={session_id}). Call set_main_loop() at startup."
        )


# ============================================================================
# STEP BOUNDARY PARSING
# ============================================================================

_STEP_RE = re.compile(
    r"\[(?:ToolChain|Adaptive|Parallel|Expert)\]\s+Step\s+(\d+)\s*[→:]\s*([^\s({\n]+)",
    re.IGNORECASE,
)

# Matches the planning announcement line:
#   [Adaptive] Step 3: web_search
#   [Adaptive] Planning step 3: web_search input: ...
_ADAPTIVE_PLAN_RE = re.compile(
    r"\[Adaptive\]\s+(?:Planning\s+)?[Ss]tep\s+(\d+)\s*[→:]\s*([^\s({\n]+)"
    r"(?:\s+input:\s*(.+))?",
    re.IGNORECASE,
)

# Matches the SEPARATE input line that _execute_adaptive emits after the
# step announcement:
#   [Adaptive] Input: {"query": "..."}
#   [Adaptive] Input: some string value
_ADAPTIVE_INPUT_RE = re.compile(
    r"\[Adaptive\]\s+Input:\s*(.+)",
    re.IGNORECASE,
)

# Matches the output preview line that _execute_adaptive emits after
# collecting tool output:
#   [Adaptive] Output:\n<preview text>
# The actual output content follows the header on the next line(s).
_ADAPTIVE_OUTPUT_RE = re.compile(
    r"^\[Adaptive\]\s+Output:\s*\n?(.*)",
    re.IGNORECASE | re.DOTALL,
)

# Parallel mode emits branch grouping information.
# e.g. "[Parallel] Branch 1: steps 1,2,3"
_PARALLEL_BRANCH_RE = re.compile(
    r"\[Parallel\]\s+Branch\s+(\d+)\s*[:\s]+steps?\s+([\d,\s]+)",
    re.IGNORECASE,
)

_ERROR_PREFIXES = (
    "[ToolChain] ERROR",
    "[Adaptive] Planning error",
    "[ERROR]",
    "ERROR: tool",
)

# Adaptive DONE signal
_ADAPTIVE_DONE_RE = re.compile(r"\[Adaptive\]\s+DONE", re.IGNORECASE)


def _parse_step_start(chunk: str) -> Optional[Tuple[int, str]]:
    m = _STEP_RE.search(chunk)
    if m:
        return int(m.group(1)), m.group(2).strip()
    return None


def _parse_adaptive_plan_line(chunk: str) -> Optional[Tuple[int, str, str]]:
    """Return (step_num, tool_name, raw_input) if this chunk announces an adaptive step."""
    m = _ADAPTIVE_PLAN_RE.search(chunk)
    if m:
        step_num   = int(m.group(1))
        tool_name  = m.group(2).strip()
        raw_input  = (m.group(3) or "").strip()
        return step_num, tool_name, raw_input
    return None


def _parse_adaptive_input_line(chunk: str) -> Optional[Any]:
    """
    Return the parsed input value if this chunk is the separate
    '[Adaptive] Input: ...' line, else None.
    Attempts JSON decode; falls back to raw string.
    """
    m = _ADAPTIVE_INPUT_RE.search(chunk)
    if not m:
        return None
    raw = m.group(1).strip()
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return raw


def _parse_adaptive_output_line(chunk: str) -> Optional[str]:
    """
    Return the clean output content if this chunk is the
    '[Adaptive] Output:\\n<preview>' line emitted by _execute_adaptive,
    else None.  Strips the '[Adaptive] Output:' header so the JS
    receives clean tool output without the label prefix.
    """
    m = _ADAPTIVE_OUTPUT_RE.match(chunk)
    if not m:
        return None
    return m.group(1).strip()


def _parse_parallel_branch(chunk: str) -> Optional[Tuple[int, List[int]]]:
    """Return (branch_num, [step_ids]) if chunk declares a parallel branch."""
    m = _PARALLEL_BRANCH_RE.search(chunk)
    if m:
        branch_num = int(m.group(1))
        step_ids   = [int(s.strip()) for s in m.group(2).split(",") if s.strip()]
        return branch_num, step_ids
    return None


def _is_step_error(chunk: str) -> bool:
    return any(chunk.startswith(p) for p in _ERROR_PREFIXES)


def _is_adaptive_done(chunk: str) -> bool:
    return bool(_ADAPTIVE_DONE_RE.search(chunk))


# ============================================================================
# MONITORED WRAPPER
# ============================================================================

class MonitoredToolChainPlanner:
    """
    Transparent wrapper around the unified ToolChainPlanner.

    Key additions
    -------------
    * **Adaptive mode** — fires ``step_discovered`` for each new step, and
      ``step_input_updated`` when the resolved input arrives on its own
      ``[Adaptive] Input: ...`` line (which _execute_adaptive emits as a
      separate chunk after the step announcement).

    * **Parallel mode** — relays ``parallel_branches`` events for swim-lane
      rendering.

    * **Mode tag on every event** — the ``mode`` field is included in every
      event so the JS widget can switch rendering strategy without guessing.
    """

    def __init__(self, planner: Any, session_id: str) -> None:
        self._planner   = planner
        self.session_id = session_id
        self.agent      = planner.agent
        self.tools      = planner.tools
        self.execution_id: Optional[str] = None

    # ------------------------------------------------------------------
    # plan_tool_chain  (unchanged behaviour, added mode tag)
    # ------------------------------------------------------------------

    def plan_tool_chain(self, query: str, history_context: str = "") -> Iterator[Any]:
        schedule_broadcast(self.session_id, "status", {"status": "planning"})
        for item in self._planner.plan_tool_chain(query, history_context):
            if isinstance(item, list):
                self._update_execution_plan(item)
                schedule_broadcast(
                    self.session_id, "plan",
                    {"plan": item, "total_steps": len(item), "mode": "sequential"},
                )
            else:
                schedule_broadcast(
                    self.session_id, "plan_chunk",
                    {"chunk": item if isinstance(item, str) else str(item)},
                )
            yield item

    # ------------------------------------------------------------------
    # execute_tool_chain  (main entry point)
    # ------------------------------------------------------------------

    def execute_tool_chain(
        self,
        query: str,
        plan:     Optional[Any] = None,
        mode:     str = "sequential",
        strategy: str = "default",
        expert:   bool = False,
        **kwargs,
    ) -> Iterator[str]:

        self.execution_id = self._create_execution(query, mode)

        schedule_broadcast(
            self.session_id, "execution_started",
            {
                "execution_id": self.execution_id,
                "query":        query,
                "mode":         mode,
                "strategy":     strategy,
            },
        )

        # Resolve effective mode (mirrors ToolChainPlanner logic)
        resolved_mode = mode
        if expert:
            resolved_mode = "expert"
        elif mode == "sequential":
            resolved_mode = self._planner._STRATEGY_TO_MODE.get(
                strategy.lower(), "sequential"
            )

        if resolved_mode == "adaptive":
            yield from self._run_adaptive(query, **kwargs)
            return

        if resolved_mode == "parallel":
            yield from self._run_parallel(query, plan=plan, **kwargs)
            return

        yield from self._run_sequential(
            query, plan=plan, mode=mode,
            strategy=strategy, expert=expert, **kwargs,
        )

    # ------------------------------------------------------------------
    # ADAPTIVE executor
    # ------------------------------------------------------------------

    def _run_adaptive(self, query: str, max_steps: int = 20, **kwargs) -> Iterator[str]:
        """
        Run the adaptive planner, firing ``step_discovered`` events in
        real-time as each step is planned.

        _execute_adaptive() emits the step announcement and its resolved
        input as TWO separate chunks:

            "[Adaptive] Step 2: web_search\\n"
            "[Adaptive] Input: {\"query\": \"...\"}\n"

        We catch both.  The first fires ``step_discovered`` (input may be
        empty at this point).  The second fires ``step_input_updated`` so
        the JS can retroactively patch the already-rendered node and detail
        panel entry.
        """
        schedule_broadcast(self.session_id, "status", {"status": "executing"})

        current_step: Optional[int]  = None
        current_tool: Optional[str]  = None
        step_chunks:  List[str]      = []
        discovered_steps: set        = set()
        _last_discovered_step: Optional[int] = None   # tracks most recent step for Input line

        try:
            for chunk in self._planner.execute_tool_chain(
                query, mode="adaptive", max_steps=max_steps, **kwargs
            ):
                # ── Detect adaptive planning announcement ──────────────────
                adaptive_info = _parse_adaptive_plan_line(chunk)
                if adaptive_info:
                    step_num, tool_name, raw_input = adaptive_info
                    _last_discovered_step = step_num
                    if step_num not in discovered_steps:
                        discovered_steps.add(step_num)
                        self._add_step(step_num, tool_name, raw_input)
                        schedule_broadcast(
                            self.session_id, "step_discovered",
                            {
                                "step_number": step_num,
                                "tool_name":   tool_name,
                                "input":       raw_input,
                                "mode":        "adaptive",
                            },
                        )
                    yield chunk
                    continue

                # ── Detect the separate "[Adaptive] Input: ..." line ───────
                input_val = _parse_adaptive_input_line(chunk)
                if input_val is not None and _last_discovered_step is not None:
                    self._patch_step_input(_last_discovered_step, input_val)
                    schedule_broadcast(
                        self.session_id, "step_input_updated",
                        {
                            "step_number": _last_discovered_step,
                            "input":       input_val,
                            "mode":        "adaptive",
                        },
                    )
                    yield chunk
                    continue

                # ── Detect execution start (step_started) ─────────────────
                step_info = _parse_step_start(chunk)
                if step_info:
                    # Flush previous step
                    if current_step is not None:
                        output = "".join(step_chunks)
                        self._complete_step(current_step, output)
                        schedule_broadcast(
                            self.session_id, "step_completed",
                            {
                                "step_number": current_step,
                                "output":      output[:500],
                                "mode":        "adaptive",
                            },
                        )
                    current_step, current_tool = step_info
                    _last_discovered_step = current_step
                    step_chunks = []
                    # Ensure step record exists (may already exist from step_discovered)
                    if current_step not in discovered_steps:
                        discovered_steps.add(current_step)
                        self._add_step(current_step, current_tool, "")
                        schedule_broadcast(
                            self.session_id, "step_discovered",
                            {
                                "step_number": current_step,
                                "tool_name":   current_tool,
                                "input":       "",
                                "mode":        "adaptive",
                            },
                        )
                    schedule_broadcast(
                        self.session_id, "step_started",
                        {
                            "step_number":  current_step,
                            "tool_name":    current_tool,
                            "execution_id": self.execution_id,
                            "mode":         "adaptive",
                        },
                    )
                    yield chunk
                    continue

                # ── Detect errors ─────────────────────────────────────────
                if current_step is not None and _is_step_error(chunk):
                    step_chunks.append(chunk)
                    output = "".join(step_chunks)
                    self._fail_step(current_step, output)
                    schedule_broadcast(
                        self.session_id, "step_failed",
                        {
                            "step_number": current_step,
                            "error":       chunk.strip(),
                            "mode":        "adaptive",
                        },
                    )
                    current_step = None
                    current_tool = None
                    step_chunks  = []
                    yield chunk
                    continue

                # ── Detect "[Adaptive] Output:\n<preview>" ────────────────
                # _execute_adaptive collects all tool output then emits it as
                # one chunk with this header.  We strip the header, broadcast
                # the clean output, and complete the step right here — the
                # output div must be shown BEFORE writing (step_started may
                # not have fired if the step was very fast), so we call
                # updateStepStatus-equivalent ordering: started → output → completed.
                output_text = _parse_adaptive_output_line(chunk)
                if output_text is not None and current_step is not None:
                    # Ensure the output div is visible by firing step_started
                    # if it hasn't been fired yet for this step
                    schedule_broadcast(
                        self.session_id, "step_started",
                        {
                            "step_number":  current_step,
                            "tool_name":    current_tool or "",
                            "execution_id": self.execution_id,
                            "mode":         "adaptive",
                        },
                    )
                    # Broadcast the clean output (no "[Adaptive] Output:" prefix)
                    schedule_broadcast(
                        self.session_id, "step_output",
                        {"step_number": current_step, "chunk": output_text, "mode": "adaptive"},
                    )
                    # Complete the step with the clean output
                    self._complete_step(current_step, output_text)
                    schedule_broadcast(
                        self.session_id, "step_completed",
                        {
                            "step_number": current_step,
                            "output":      output_text[:500],
                            "mode":        "adaptive",
                        },
                    )
                    step_chunks  = []
                    current_step = None
                    current_tool = None
                    yield chunk
                    continue

                # ── DONE signal ───────────────────────────────────────────
                if _is_adaptive_done(chunk):
                    if current_step is not None and step_chunks:
                        output = "".join(step_chunks)
                        self._complete_step(current_step, output)
                        schedule_broadcast(
                            self.session_id, "step_completed",
                            {
                                "step_number": current_step,
                                "output":      output[:500],
                                "mode":        "adaptive",
                            },
                        )
                    yield chunk
                    continue

                # ── Normal output chunk ───────────────────────────────────
                if current_step is not None:
                    step_chunks.append(chunk)
                    schedule_broadcast(
                        self.session_id, "step_output",
                        {"step_number": current_step, "chunk": chunk, "mode": "adaptive"},
                    )
                yield chunk

            # Flush final step
            if current_step is not None and step_chunks:
                output = "".join(step_chunks)
                self._complete_step(current_step, output)
                schedule_broadcast(
                    self.session_id, "step_completed",
                    {
                        "step_number": current_step,
                        "output":      output[:500],
                        "mode":        "adaptive",
                    },
                )

            self._finish_execution("completed")
            schedule_broadcast(
                self.session_id, "execution_completed",
                {"execution_id": self.execution_id, "mode": "adaptive"},
            )

        except Exception as exc:
            logger.error(f"[Monitor/adaptive] error: {exc}", exc_info=True)
            self._finish_execution("failed", str(exc))
            schedule_broadcast(
                self.session_id, "execution_failed",
                {"error": str(exc), "execution_id": self.execution_id},
            )
            raise

    # ------------------------------------------------------------------
    # PARALLEL executor
    # ------------------------------------------------------------------

    def _run_parallel(
        self, query: str, plan: Optional[Any] = None, **kwargs
    ) -> Iterator[str]:
        """
        Run the parallel planner.  Detects branch declarations and fires
        ``parallel_branches`` so the flowchart can draw swim-lanes.
        """
        # Pre-plan if needed
        if plan is None:
            schedule_broadcast(self.session_id, "status", {"status": "planning"})
            intercepted_plan: Optional[List[Dict]] = None
            for item in self._planner.plan_tool_chain(query):
                if isinstance(item, list):
                    intercepted_plan = item
                    self._update_execution_plan(item)
                    schedule_broadcast(
                        self.session_id, "plan",
                        {"plan": item, "total_steps": len(item), "mode": "parallel"},
                    )
                else:
                    chunk = item if isinstance(item, str) else str(item)
                    schedule_broadcast(self.session_id, "plan_chunk", {"chunk": chunk})
                    yield chunk
            if intercepted_plan is None:
                self._finish_execution("failed", "Planning produced no plan")
                schedule_broadcast(self.session_id, "execution_failed",
                                   {"error": "Planning produced no plan"})
                return
            plan = intercepted_plan

        schedule_broadcast(self.session_id, "status", {"status": "executing"})

        # Collect branch groupings from execution output
        branches: Dict[int, List[int]] = {}
        current_step: Optional[int] = None
        current_tool: Optional[str] = None
        step_chunks:  List[str]     = []

        try:
            for chunk in self._planner.execute_tool_chain(
                query, plan=plan, mode="parallel", **kwargs
            ):
                # ── Branch declaration ─────────────────────────────────────
                branch_info = _parse_parallel_branch(chunk)
                if branch_info:
                    branch_num, step_ids = branch_info
                    branches[branch_num] = step_ids
                    # Build the full branch list and broadcast
                    branch_list = [branches[b] for b in sorted(branches)]
                    schedule_broadcast(
                        self.session_id, "parallel_branches",
                        {"branches": branch_list, "mode": "parallel"},
                    )
                    yield chunk
                    continue

                # ── Step start ────────────────────────────────────────────
                step_info = _parse_step_start(chunk)
                if step_info:
                    if current_step is not None:
                        output = "".join(step_chunks)
                        self._complete_step(current_step, output)
                        schedule_broadcast(
                            self.session_id, "step_completed",
                            {
                                "step_number": current_step,
                                "output":      output[:500],
                                "mode":        "parallel",
                            },
                        )
                    current_step, current_tool = step_info
                    step_chunks = []
                    self._add_step(current_step, current_tool, "")
                    schedule_broadcast(
                        self.session_id, "step_started",
                        {
                            "step_number":  current_step,
                            "tool_name":    current_tool,
                            "execution_id": self.execution_id,
                            "mode":         "parallel",
                        },
                    )
                    yield chunk
                    continue

                # ── Error ─────────────────────────────────────────────────
                if current_step is not None and _is_step_error(chunk):
                    step_chunks.append(chunk)
                    output = "".join(step_chunks)
                    self._fail_step(current_step, output)
                    schedule_broadcast(
                        self.session_id, "step_failed",
                        {
                            "step_number": current_step,
                            "error":       chunk.strip(),
                            "mode":        "parallel",
                        },
                    )
                    current_step = None
                    step_chunks  = []
                    yield chunk
                    continue

                # ── Output chunk ──────────────────────────────────────────
                if current_step is not None:
                    step_chunks.append(chunk)
                    schedule_broadcast(
                        self.session_id, "step_output",
                        {"step_number": current_step, "chunk": chunk, "mode": "parallel"},
                    )
                yield chunk

            # Flush final
            if current_step is not None and step_chunks:
                output = "".join(step_chunks)
                self._complete_step(current_step, output)
                schedule_broadcast(
                    self.session_id, "step_completed",
                    {
                        "step_number": current_step,
                        "output":      output[:500],
                        "mode":        "parallel",
                    },
                )

            self._finish_execution("completed")
            schedule_broadcast(
                self.session_id, "execution_completed",
                {"execution_id": self.execution_id, "mode": "parallel"},
            )

        except Exception as exc:
            logger.error(f"[Monitor/parallel] error: {exc}", exc_info=True)
            self._finish_execution("failed", str(exc))
            schedule_broadcast(
                self.session_id, "execution_failed",
                {"error": str(exc), "execution_id": self.execution_id},
            )
            raise

    # ------------------------------------------------------------------
    # SEQUENTIAL / EXPERT / HYBRID executor
    # ------------------------------------------------------------------

    def _run_sequential(
        self,
        query:    str,
        plan:     Optional[Any] = None,
        mode:     str = "sequential",
        strategy: str = "default",
        expert:   bool = False,
        **kwargs,
    ) -> Iterator[str]:
        if plan is None:
            schedule_broadcast(self.session_id, "status", {"status": "planning"})
            intercepted_plan: Optional[List[Dict]] = None
            for item in self._planner.plan_tool_chain(query):
                if isinstance(item, list):
                    intercepted_plan = item
                    self._update_execution_plan(item)
                    schedule_broadcast(
                        self.session_id, "plan",
                        {"plan": item, "total_steps": len(item), "mode": mode},
                    )
                else:
                    chunk = item if isinstance(item, str) else str(item)
                    schedule_broadcast(self.session_id, "plan_chunk", {"chunk": chunk})
                    yield chunk
            if intercepted_plan is None:
                self._finish_execution("failed", "Planning produced no plan")
                schedule_broadcast(self.session_id, "execution_failed",
                                   {"error": "Planning produced no plan"})
                return
            plan = intercepted_plan

        schedule_broadcast(self.session_id, "status", {"status": "executing"})

        current_step: Optional[int] = None
        current_tool: Optional[str] = None
        step_chunks:  List[str]     = []

        try:
            for chunk in self._planner.execute_tool_chain(
                query, plan=plan, mode=mode,
                strategy=strategy, expert=expert, **kwargs,
            ):
                step_info = _parse_step_start(chunk)
                if step_info:
                    if current_step is not None:
                        output = "".join(step_chunks)
                        self._complete_step(current_step, output)
                        schedule_broadcast(
                            self.session_id, "step_completed",
                            {"step_number": current_step, "output": output[:500], "mode": mode},
                        )
                    current_step, current_tool = step_info
                    step_chunks = []
                    self._add_step(current_step, current_tool, "")
                    schedule_broadcast(
                        self.session_id, "step_started",
                        {
                            "step_number":  current_step,
                            "tool_name":    current_tool,
                            "execution_id": self.execution_id,
                            "mode":         mode,
                        },
                    )
                    yield chunk
                    continue

                if current_step is not None and _is_step_error(chunk):
                    step_chunks.append(chunk)
                    output = "".join(step_chunks)
                    self._fail_step(current_step, output)
                    schedule_broadcast(
                        self.session_id, "step_failed",
                        {"step_number": current_step, "error": chunk.strip(), "mode": mode},
                    )
                    current_step = None
                    step_chunks  = []
                    yield chunk
                    continue

                if current_step is not None:
                    step_chunks.append(chunk)
                    schedule_broadcast(
                        self.session_id, "step_output",
                        {"step_number": current_step, "chunk": chunk, "mode": mode},
                    )
                yield chunk

            if current_step is not None and step_chunks:
                output = "".join(step_chunks)
                self._complete_step(current_step, output)
                schedule_broadcast(
                    self.session_id, "step_completed",
                    {"step_number": current_step, "output": output[:500], "mode": mode},
                )

            self._finish_execution("completed")
            schedule_broadcast(
                self.session_id, "execution_completed",
                {"execution_id": self.execution_id, "mode": mode},
            )

        except Exception as exc:
            logger.error(f"[Monitor/sequential] error: {exc}", exc_info=True)
            self._finish_execution("failed", str(exc))
            schedule_broadcast(
                self.session_id, "execution_failed",
                {"error": str(exc), "execution_id": self.execution_id},
            )
            raise

    # ------------------------------------------------------------------
    # Backward-compat alias
    # ------------------------------------------------------------------

    def execute_adaptive(self, query: str, max_steps: int = 20) -> Iterator[str]:
        yield from self.execute_tool_chain(query, mode="adaptive", max_steps=max_steps)

    # ------------------------------------------------------------------
    # Attribute delegation
    # ------------------------------------------------------------------

    def __getattr__(self, name: str) -> Any:
        return getattr(self._planner, name)

    # ------------------------------------------------------------------
    # Execution state helpers
    # ------------------------------------------------------------------

    def _create_execution(self, query: str, mode: str = "sequential") -> str:
        eid = str(uuid.uuid4())
        toolchain_executions.setdefault(self.session_id, {})[eid] = {
            "execution_id":    eid,
            "session_id":      self.session_id,
            "query":           query,
            "mode":            mode,
            "plan":            [],
            "steps":           [],
            "status":          "planning",
            "start_time":      datetime.utcnow().isoformat(),
            "end_time":        None,
            "total_steps":     0,
            "completed_steps": 0,
            "final_result":    None,
        }
        active_toolchains[self.session_id] = eid
        return eid

    def _update_execution_plan(self, plan: List[Dict]) -> None:
        rec = toolchain_executions.get(self.session_id, {}).get(self.execution_id)
        if rec is not None:
            rec["plan"]        = plan
            rec["total_steps"] = len(plan)
            rec["status"]      = "executing"

    def _add_step(self, step_num: int, tool_name: str, tool_input: Any) -> None:
        rec = toolchain_executions.get(self.session_id, {}).get(self.execution_id)
        if rec is None:
            return
        # Don't duplicate
        if any(s["step_number"] == step_num for s in rec["steps"]):
            return
        input_str = (
            json.dumps(tool_input, indent=2)
            if isinstance(tool_input, dict)
            else str(tool_input)
        )
        rec["steps"].append({
            "step_number": step_num,
            "tool_name":   tool_name,
            "tool_input":  input_str,
            "tool_output": None,
            "status":      "running",
            "start_time":  datetime.utcnow().isoformat(),
            "end_time":    None,
            "error":       None,
        })
        rec["total_steps"] = max(rec["total_steps"], step_num)

    def _patch_step_input(self, step_num: int, input_val: Any) -> None:
        """
        Retroactively update the tool_input field for a step that was
        initially discovered with an empty input because the resolved
        input arrived on a separate '[Adaptive] Input: ...' line.
        """
        rec = toolchain_executions.get(self.session_id, {}).get(self.execution_id)
        if rec is None:
            return
        for step in rec["steps"]:
            if step["step_number"] == step_num:
                step["tool_input"] = (
                    json.dumps(input_val, indent=2)
                    if isinstance(input_val, dict)
                    else str(input_val)
                )
                break

    def _complete_step(self, step_num: int, output: str) -> None:
        self._update_step(step_num, output=output, status="completed")

    def _fail_step(self, step_num: int, error: str) -> None:
        self._update_step(step_num, error=error, status="failed")

    def _update_step(
        self, step_num: int,
        output: Optional[str] = None,
        error:  Optional[str] = None,
        status: str = "completed",
    ) -> None:
        rec = toolchain_executions.get(self.session_id, {}).get(self.execution_id)
        if rec is None:
            return
        for step in rec["steps"]:
            if step["step_number"] == step_num:
                if output is not None:
                    step["tool_output"] = output
                if error is not None:
                    step["error"] = error
                step["status"]   = status
                step["end_time"] = datetime.utcnow().isoformat()
                if status == "completed":
                    rec["completed_steps"] += 1
                break

    def _finish_execution(self, status: str, error: Optional[str] = None) -> None:
        rec = toolchain_executions.get(self.session_id, {}).get(self.execution_id)
        if rec is None:
            return
        rec["status"]   = status
        rec["end_time"] = datetime.utcnow().isoformat()
        if error:
            rec["error"] = error
        active_toolchains.pop(self.session_id, None)


# ============================================================================
# INTEGRATION HELPERS
# ============================================================================

def wrap_toolchain_with_monitoring(vera_instance: Any, session_id: str) -> Any:
    """
    Wrap vera_instance.toolchain with WebSocket monitoring.
    Safe to call multiple times — won't double-wrap.
    """
    if isinstance(vera_instance.toolchain, MonitoredToolChainPlanner):
        return vera_instance

    vera_instance.toolchain           = MonitoredToolChainPlanner(
        vera_instance.toolchain, session_id
    )
    vera_instance.toolchain_expert    = vera_instance.toolchain
    vera_instance._adaptive_toolchain = vera_instance.toolchain

    logger.info(f"[Monitor] Toolchain wrapped for session {session_id}")
    return vera_instance


# Backward-compat alias
EnhancedMonitoredToolChainPlanner = MonitoredToolChainPlanner