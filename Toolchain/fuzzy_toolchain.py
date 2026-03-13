"""
Vera Fuzzy ToolChain Planner
============================
Extends ToolChainPlanner with fuzzy / semantic tool resolution so the LLM
planner can name tools loosely (or even describe what it wants to do) and
FuzzyToolSearcher will resolve the closest real registered tool at plan time.

Two planning modes are added (``mode`` kwarg):

  "fuzzy_oneshot"   – Ask the LLM for a full JSON plan in one shot.
                      Every tool name in the plan is fuzzy-resolved before
                      execution begins.  Best for well-scoped queries where
                      the entire sequence is predictable upfront.

  "fuzzy_stepwise"  – Plans and executes one step at a time (like adaptive),
                      but each step's tool name is fuzzy-resolved before the
                      tool is called.  Best for exploratory or ambiguous
                      queries where each step's outcome should inform the next.

Both modes tolerate vague or descriptive tool names from the planner, e.g.:
    "search the web"  →  web_search
    "run python code" →  python
    "scan network"    →  nmap_scan

Public interface (backward compatible — drop-in alongside ToolChainPlanner):

    from Vera.Toolchain.fuzzy_toolchain import FuzzyToolChainPlanner

    # In vera.py / setup_toolchain:
    planner = FuzzyToolChainPlanner(vera_instance, vera_instance.tools,
                                     registry=vera_instance.tool_registry)
    vera_instance.toolchain = planner

    # Usage:
    for chunk in planner.execute_tool_chain(query, mode="fuzzy_oneshot"):
        ...
    for chunk in planner.execute_tool_chain(query, mode="fuzzy_stepwise"):
        ...

If no ToolRegistry is provided the planner falls back to exact-match lookup
(i.e. identical behaviour to the base ToolChainPlanner).
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import traceback
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple

from Vera.Toolchain.toolchain import (
    ToolChainPlanner,
    ExecutionMode,
    _extract_text,
    _extract_json,
    _clean_json,
    _resolve_input,
    _LLM_VIRTUAL_TOOL_NAME,
    _SUPPRESSED_LLM_TOOL_NAMES,
    _LLM_TOOL_HINT,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Execution mode constants (extend the parent enum values)
# ---------------------------------------------------------------------------

FUZZY_ONESHOT  = "fuzzy_oneshot"
FUZZY_STEPWISE = "fuzzy_stepwise"


# ---------------------------------------------------------------------------
# Planning prompt fragments
# ---------------------------------------------------------------------------

_FUZZY_PLAN_SYSTEM = """\
You are a tool-orchestration planner.  Your tool names do NOT need to be exact —
a fuzzy resolver will match them to the closest real tool at execution time.

You MAY describe what each step should do instead of guessing the exact tool name,
for example:
    "search the web for X"  instead of  "web_search"
    "run a python script"   instead of  "python"
    "scan for open ports"   instead of  "nmap_scan"

Return ONLY a raw JSON array — no markdown, no fences, no prose.
First character must be '['. Last character must be ']'.

Each element:
  {"tool": "<name or description>", "input": <string or object>, "reasoning": "<why>"}

Reference prior step outputs with {prev} or {step_N}.
"""

_FUZZY_ONESHOT_USER = """\
Task: {query}

Available tool categories / hints (exact names not required):
{tool_hints}

{llm_hint}

Produce a full step-by-step JSON plan now.
"""

_FUZZY_STEPWISE_SYSTEM = """\
You are a precise tool-orchestration planner.

Given an original query and the history of tool calls already made, decide
the SINGLE best next step.  Your tool name does NOT need to be exact —
describe what you want to do and the fuzzy resolver will pick the right tool.

CRITICAL: Output a single raw JSON object only. No markdown, no fences, no
text before or after. First character must be '{'. Last character must be '}'.

To invoke a tool:
  {"tool": "<name or description>", "input": <string or object>, "reasoning": "<why>"}

When the goal is fully achieved:
  {"tool": "DONE", "summary": "<brief summary of what was accomplished>"}

Rules:
- Never repeat a step whose output already satisfies the need.
- Prefer specific, targeted steps.
- Use "llm" (not fast_llm/deep_llm/coding_llm) for any synthesis/generation step.
"""

_FUZZY_STEPWISE_USER = """\
Original query: {query}

Tool history so far ({n} step(s)):
{history}

Tool categories / hints:
{tool_hints}

{llm_hint}

What is the single best next step? Respond with JSON only.
"""


# ---------------------------------------------------------------------------
# Fuzzy planner
# ---------------------------------------------------------------------------

class FuzzyToolChainPlanner(ToolChainPlanner):
    """
    ToolChainPlanner extended with fuzzy tool resolution.

    Extra constructor arg:
        registry  – a ToolRegistry instance that owns a FuzzyToolSearcher.
                    If omitted, falls back to exact-match lookup only.
        fuzzy_threshold – minimum relevance score accepted from FuzzyToolSearcher
                    (default 0.3).  Lower = more permissive matching.
    """

    def __init__(
        self,
        agent: Any,
        tools: List[Any],
        registry: Optional[Any] = None,
        fuzzy_threshold: float = 0.3,
    ) -> None:
        super().__init__(agent, tools)
        self._registry        = registry
        self._fuzzy_threshold = fuzzy_threshold
        self._searcher        = self._build_searcher(registry)

    # ------------------------------------------------------------------
    # Searcher setup
    # ------------------------------------------------------------------

    def _build_searcher(self, registry: Optional[Any]) -> Optional[Any]:
        if registry is None:
            return None
        try:
            from Vera.Toolchain.ToolFramework.fuzzy_search import FuzzyToolSearcher
            enable_semantic = getattr(registry, "enable_semantic_search", False)
            searcher = FuzzyToolSearcher(registry, enable_semantic=enable_semantic)
            logger.info(
                f"FuzzyToolChainPlanner: FuzzyToolSearcher ready "
                f"(semantic={'on' if enable_semantic else 'off'})"
            )
            return searcher
        except Exception as exc:
            logger.warning(
                f"FuzzyToolChainPlanner: could not build FuzzyToolSearcher — {exc}. "
                f"Falling back to exact-match tool lookup."
            )
            return None

    # ------------------------------------------------------------------
    # Fuzzy tool resolution
    # ------------------------------------------------------------------

    def _resolve_tool_fuzzy(
        self, name_or_desc: str, context_hint: str = ""
    ) -> Tuple[Optional[Any], str, float]:
        """
        Try to find the best matching real tool for a potentially vague name.

        Resolution order:
          1. Exact name match (fast path, no searcher needed)
          2. FuzzyToolSearcher keyword + optional semantic search
          3. None if nothing found above threshold

        Returns:
            (tool_object | None, resolved_name, confidence_score)
            confidence_score is 1.0 for exact matches, 0.0 if not found.
        """
        # 1. Exact match (handles "llm" virtual and suppressed names too)
        exact = self._find_tool(name_or_desc)
        if exact is not None:
            return exact, name_or_desc, 1.0

        # Virtual/suppressed LLM tools bypass fuzzy search
        if (
            name_or_desc == _LLM_VIRTUAL_TOOL_NAME
            or name_or_desc in _SUPPRESSED_LLM_TOOL_NAMES
        ):
            return None, name_or_desc, 1.0  # handled by dispatcher

        # 2. Fuzzy search
        if self._searcher is not None:
            query = f"{name_or_desc} {context_hint}".strip()
            try:
                results = self._searcher.search(
                    query,
                    max_results=3,
                    min_score=self._fuzzy_threshold,
                )
                if results:
                    best_tool, best_score = results[0]
                    resolved_name = getattr(best_tool, "name", name_or_desc)
                    logger.info(
                        f"[FuzzyResolve] '{name_or_desc}' → '{resolved_name}' "
                        f"(score={best_score:.3f})"
                    )
                    return best_tool, resolved_name, best_score
            except Exception as exc:
                logger.warning(f"[FuzzyResolve] Search error for '{name_or_desc}': {exc}")

        # 3. Not found
        return None, name_or_desc, 0.0

    def _resolve_plan_tools(
        self, plan: List[Dict]
    ) -> Tuple[List[Dict], List[str]]:
        """
        Walk a plan list and fuzzy-resolve every tool name in place.

        Returns:
            (resolved_plan, warnings)
        """
        resolved_plan: List[Dict] = []
        warnings: List[str] = []

        for step in plan:
            raw_name = step.get("tool", "")
            reasoning = step.get("reasoning", "")

            tool_obj, resolved_name, score = self._resolve_tool_fuzzy(
                raw_name, context_hint=reasoning
            )

            new_step = dict(step)
            new_step["tool"] = resolved_name

            if raw_name != resolved_name:
                msg = (
                    f"  fuzzy: '{raw_name}' → '{resolved_name}' (score={score:.2f})"
                )
                warnings.append(msg)
                logger.debug(f"[FuzzyResolve] {msg.strip()}")

            elif tool_obj is None and raw_name not in (
                _LLM_VIRTUAL_TOOL_NAME, "DONE"
            ) and raw_name not in _SUPPRESSED_LLM_TOOL_NAMES:
                msg = f"  fuzzy: '{raw_name}' — no match found (score=0.00)"
                warnings.append(msg)
                logger.warning(f"[FuzzyResolve] {msg.strip()}")

            resolved_plan.append(new_step)

        return resolved_plan, warnings

    # ------------------------------------------------------------------
    # Tool hint summary (for planning prompts)
    # ------------------------------------------------------------------

    def _build_tool_hints(self, max_tools: int = 40) -> str:
        """
        Build a compact tool summary for injection into planning prompts.
        Groups by domain when the registry is available; otherwise lists names.
        """
        if self._searcher is not None and self._registry is not None:
            try:
                lines: List[str] = []
                seen: Set[str] = set()
                for tool in self._registry.get_langchain_tools():
                    name = getattr(tool, "name", "")
                    desc = getattr(tool, "description", "")
                    if name in seen or name in _SUPPRESSED_LLM_TOOL_NAMES:
                        continue
                    seen.add(name)
                    short_desc = desc[:70] + "…" if len(desc) > 70 else desc
                    lines.append(f"  {name:<30} {short_desc}")
                    if len(lines) >= max_tools:
                        break
                return "\n".join(lines)
            except Exception:
                pass

        # Fallback: use self.tools list (same as base class)
        return self._format_tool_list()

    # ------------------------------------------------------------------
    # ONE-SHOT FUZZY EXECUTOR
    # ------------------------------------------------------------------

    def _execute_fuzzy_oneshot(
        self,
        query: str,
        **_kwargs,
    ) -> Iterator[str]:
        """
        Plan the entire chain in one LLM call, fuzzy-resolve all tool names,
        then execute sequentially.
        """
        yield f"[FuzzyOneShot] Planning: {query[:120]}\n"

        # ── 1. Build plan ────────────────────────────────────────────
        llm, agent_has_tools = self._get_planning_llm()

        tool_hints = self._build_tool_hints()
        llm_hint   = _LLM_TOOL_HINT if not agent_has_tools else ""

        prompt = (
            _FUZZY_PLAN_SYSTEM
            + "\n\n"
            + _FUZZY_ONESHOT_USER.format(
                query=query,
                tool_hints=tool_hints,
                llm_hint=llm_hint,
            )
        )

        raw   = ""
        yield "[FuzzyOneShot] Generating plan…\n"
        for chunk in self._stream_llm(llm, prompt):
            raw += chunk
            # Don't forward raw planning JSON to the user — it's noisy

        plan = _extract_json(_clean_json(raw))
        if plan is None:
            yield (
                "[FuzzyOneShot] ERROR: planner returned no valid JSON.\n"
                f"Raw output:\n{raw}\n"
            )
            return

        if isinstance(plan, dict):
            plan = [plan]
        if not isinstance(plan, list):
            yield f"[FuzzyOneShot] ERROR: unexpected plan format: {plan!r}\n"
            return

        yield f"[FuzzyOneShot] Raw plan: {len(plan)} step(s).\n"

        # ── 2. Fuzzy-resolve all tool names ──────────────────────────
        yield "[FuzzyOneShot] Resolving tool names…\n"
        resolved_plan, warnings = self._resolve_plan_tools(plan)

        if warnings:
            yield "[FuzzyOneShot] Tool name resolutions:\n"
            for w in warnings:
                yield f"{w}\n"

        # Display resolved plan summary
        for i, step in enumerate(resolved_plan, 1):
            reasoning = step.get("reasoning", "")
            reason_str = f"  ({reasoning})" if reasoning else ""
            yield f"  Step {i}: {step['tool']}{reason_str}\n"

        # ── 3. Save plan ─────────────────────────────────────────────
        plan_id = hashlib.sha256(
            f"{time.time()}_{json.dumps(resolved_plan)}".encode()
        ).hexdigest()[:16]
        self._save_plan(resolved_plan, plan_id, label="FuzzyOneShotPlan")

        # ── 4. Execute ───────────────────────────────────────────────
        yield "\n[FuzzyOneShot] Executing…\n"
        outputs: Dict[str, str] = {}
        errors = False

        for step_num, step in enumerate(resolved_plan, 1):
            tool_name  = step.get("tool", "")
            raw_input  = step.get("input", "")
            reasoning  = step.get("reasoning", "")

            reason_str = f" ({reasoning})" if reasoning else ""
            yield f"\n[FuzzyOneShot] Step {step_num} → {tool_name}{reason_str}\n"

            collected: List[str] = []
            try:
                for chunk in self._run_step(
                    tool_name, raw_input, step_num, outputs, "FuzzyOneShot"
                ):
                    yield chunk
                    collected.append(chunk)
                result = "".join(collected)
                if "[FuzzyOneShot] ERROR" in result or "ERROR: tool" in result:
                    errors = True
            except Exception as exc:
                result = (
                    f"[FuzzyOneShot] ERROR in {tool_name}: {exc}\n"
                    f"{traceback.format_exc()}"
                )
                yield result
                errors = True

            outputs[f"step_{step_num}"] = result
            outputs[tool_name]          = result
            self._save_step(step_num, tool_name, result)

        status = "⚠ completed with errors" if errors else "✓ complete"
        yield f"\n[FuzzyOneShot] {status} ({len(resolved_plan)} steps).\n"

    # ------------------------------------------------------------------
    # STEP-WISE FUZZY EXECUTOR
    # ------------------------------------------------------------------

    def _plan_next_fuzzy_step(
        self,
        query: str,
        history: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Ask the LLM for the single best next step, allowing vague tool names.
        """
        llm, _ = self._get_planning_llm()

        tool_hints = self._build_tool_hints()
        history_text = "\n".join(
            f"Step {i + 1}:\n"
            f"  tool  : {h['tool']}\n"
            f"  input : {json.dumps(h['input'], default=str)[:400]}\n"
            f"  output: {str(h['output'])[:600]}"
            for i, h in enumerate(history)
        ) or "(none yet)"

        prompt = (
            _FUZZY_STEPWISE_SYSTEM
            + "\n\n"
            + _FUZZY_STEPWISE_USER.format(
                query=query,
                n=len(history),
                history=history_text,
                tool_hints=tool_hints,
                llm_hint=_LLM_TOOL_HINT,
            )
        )

        raw  = "".join(self._stream_llm(llm, prompt))
        step = _extract_json(raw)

        if not isinstance(step, dict) or "tool" not in step:
            raise ValueError(
                f"LLM returned invalid JSON for fuzzy step.\nRaw:\n{raw}"
            )
        return step

    def _execute_fuzzy_stepwise(
        self,
        query: str,
        max_steps: int = 20,
        **_kwargs,
    ) -> Iterator[str]:
        """
        Step-by-step adaptive planning with fuzzy tool resolution before
        each tool call.  Plans one step, fuzzy-resolves its tool name,
        executes, then feeds the result into the next planning decision.
        """
        history: List[Dict[str, Any]] = []
        step_num = 0

        yield f"[FuzzyStepwise] Starting: {query[:120]}\n"

        while step_num < max_steps:
            step_num += 1
            yield f"\n[FuzzyStepwise] ── Planning step {step_num} ──\n"

            # Plan
            try:
                step = self._plan_next_fuzzy_step(query, history)
            except Exception as exc:
                yield f"[FuzzyStepwise] Planning error: {exc}\n"
                break

            raw_tool   = step.get("tool", "")
            tool_input = step.get("input", "")
            reasoning  = step.get("reasoning", "")

            # Termination check before fuzzy resolution
            if raw_tool.upper() == "DONE":
                summary = step.get("summary", "(no summary)")
                yield f"\n[FuzzyStepwise] ✓ Goal achieved after {step_num - 1} step(s).\n"
                yield f"[FuzzyStepwise] Summary: {summary}\n"
                self._save_fuzzy_stepwise_plan(query, history, summary)
                return

            # Fuzzy-resolve the tool name for this step
            tool_obj, resolved_name, score = self._resolve_tool_fuzzy(
                raw_tool, context_hint=reasoning
            )

            if raw_tool != resolved_name:
                yield (
                    f"[FuzzyStepwise] '{raw_tool}' → '{resolved_name}' "
                    f"(score={score:.2f})\n"
                )
            elif tool_obj is None and resolved_name not in (
                _LLM_VIRTUAL_TOOL_NAME, "DONE"
            ) and resolved_name not in _SUPPRESSED_LLM_TOOL_NAMES:
                yield (
                    f"[FuzzyStepwise] WARNING: could not resolve '{raw_tool}' "
                    f"(score={score:.2f}) — step will likely fail.\n"
                )

            reason_str = f" ({reasoning})" if reasoning else ""
            yield f"[FuzzyStepwise] Step {step_num}: {resolved_name}{reason_str}\n"
            yield f"[FuzzyStepwise] Input: {json.dumps(tool_input, default=str)[:300]}\n"

            # Execute
            history_outputs = {
                f"step_{i + 1}": h["output"] for i, h in enumerate(history)
            }
            collected: List[str] = []
            try:
                for chunk in self._run_step(
                    resolved_name, tool_input, step_num,
                    history_outputs, "FuzzyStepwise"
                ):
                    collected.append(chunk)
                output = "".join(collected)
            except Exception as exc:
                output = (
                    f"[ERROR] {resolved_name}: {exc}\n{traceback.format_exc()}"
                )

            preview = output[:600] + ("…" if len(output) > 600 else "")
            yield f"[FuzzyStepwise] Output:\n{preview}\n"

            history.append({
                "step":     step_num,
                "tool":     resolved_name,
                "raw_tool": raw_tool,
                "input":    tool_input,
                "output":   output,
            })
            self._save_step(step_num, resolved_name, output)

        # Max steps reached
        yield f"\n[FuzzyStepwise] ⚠ Reached max_steps ({max_steps}).\n"
        summary_prompt = (
            f"User asked: {query}\n\n"
            f"We executed {step_num} steps but did not fully complete.\n"
            f"Steps:\n"
            + "\n".join(
                f"  {h['step']}. {h['tool']} → {str(h['output'])[:200]}"
                for h in history
            )
            + "\n\nWrite a concise summary of what was achieved and what remains."
        )
        partial_summary = ""
        for chunk in self._stream_llm(self.agent.fast_llm, summary_prompt):
            partial_summary += chunk
            yield chunk
        self._save_fuzzy_stepwise_plan(query, history, partial_summary)

    def _save_fuzzy_stepwise_plan(
        self,
        query: str,
        history: List[Dict],
        summary: str,
    ) -> None:
        plan_id = hashlib.sha256(
            f"{time.time()}_{query}".encode()
        ).hexdigest()[:16]
        try:
            self.agent.mem.add_session_memory(
                self.agent.sess.id,
                json.dumps(
                    {
                        "query":   query,
                        "steps":   history,
                        "summary": summary,
                        "plan_id": plan_id,
                    },
                    default=str,
                ),
                "FuzzyStepwisePlan",
                {"topic": "fuzzy_stepwise_plan", "plan_id": plan_id},
                promote=True,
            )
        except Exception as exc:
            logger.warning(f"Could not save fuzzy stepwise plan: {exc}")

    # ------------------------------------------------------------------
    # execute_tool_chain  (override to add fuzzy modes)
    # ------------------------------------------------------------------

    def execute_tool_chain(  # type: ignore[override]
        self,
        query: str,
        plan: Optional[Any] = None,
        mode: str = "sequential",
        strategy: str = "default",
        expert: bool = False,
        **kwargs,
    ) -> Iterator[str]:
        """
        Extends the base execute_tool_chain with two new modes:

            mode="fuzzy_oneshot"   – one-shot plan + fuzzy resolution + execution
            mode="fuzzy_stepwise"  – adaptive step-by-step with per-step fuzzy resolution

        All other modes delegate to the parent implementation unchanged.

        ``strategy`` aliases added:
            "fuzzy"          → fuzzy_oneshot
            "fuzzy_oneshot"  → fuzzy_oneshot
            "fuzzy_step"     → fuzzy_stepwise
            "fuzzy_stepwise" → fuzzy_stepwise
        """
        # Map any new strategy aliases
        _EXTRA_STRATEGY_MAP: Dict[str, str] = {
            "fuzzy":          FUZZY_ONESHOT,
            "fuzzy_oneshot":  FUZZY_ONESHOT,
            "fuzzy_one_shot": FUZZY_ONESHOT,
            "fuzzy_step":     FUZZY_STEPWISE,
            "fuzzy_stepwise": FUZZY_STEPWISE,
            "fuzzy_adaptive": FUZZY_STEPWISE,
        }

        # Resolve mode (expert flag > explicit mode > strategy alias > base map)
        if expert:
            resolved = "expert"
        elif mode in (FUZZY_ONESHOT, FUZZY_STEPWISE):
            resolved = mode
        elif mode != "sequential":
            resolved = mode
        else:
            resolved = _EXTRA_STRATEGY_MAP.get(
                strategy.lower(),
                self._STRATEGY_TO_MODE.get(strategy.lower(), "sequential"),
            )

        if resolved == FUZZY_ONESHOT:
            yield from self._execute_fuzzy_oneshot(query, **kwargs)
        elif resolved == FUZZY_STEPWISE:
            yield from self._execute_fuzzy_stepwise(
                query, max_steps=kwargs.get("max_steps", 20)
            )
        else:
            # All other modes handled by base class
            yield from super().execute_tool_chain(
                query, plan=plan, mode=resolved,
                strategy=strategy, expert=expert, **kwargs
            )


# ---------------------------------------------------------------------------
# Vera integration helper (extends base setup_toolchain)
# ---------------------------------------------------------------------------

def setup_fuzzy_toolchain(
    vera_instance: Any,
    registry: Optional[Any] = None,
    fuzzy_threshold: float = 0.3,
) -> "FuzzyToolChainPlanner":
    """
    Drop-in replacement for setup_toolchain() that wires up the fuzzy planner.

    Usage in Vera.__init__:
        from Vera.Toolchain.fuzzy_toolchain import setup_fuzzy_toolchain
        setup_fuzzy_toolchain(self, registry=self.tool_registry)

    Sets up:
        vera.toolchain           – FuzzyToolChainPlanner (all modes available)
        vera.toolchain_expert    – same instance
        vera._adaptive_toolchain – same instance (execute_adaptive compat alias)

    Args:
        vera_instance    – the Vera agent instance
        registry         – ToolRegistry (optional; enables fuzzy search)
        fuzzy_threshold  – minimum FuzzyToolSearcher score (default 0.3)
    """
    planner = FuzzyToolChainPlanner(
        vera_instance,
        vera_instance.tools,
        registry=registry,
        fuzzy_threshold=fuzzy_threshold,
    )

    vera_instance.toolchain           = planner
    vera_instance.toolchain_expert    = planner
    vera_instance._adaptive_toolchain = planner

    logger.info(
        "FuzzyToolchain initialised: "
        "sequential / adaptive / expert / parallel / hybrid / "
        "fuzzy_oneshot / fuzzy_stepwise"
    )
    return planner

    """
    Drop-in wiring — swap setup_toolchain for setup_fuzzy_toolchain:
        from Vera.Toolchain.fuzzy_toolchain import setup_fuzzy_toolchain
        setup_fuzzy_toolchain(self, registry=self.tool_registry, fuzzy_threshold=0.3)
    Or call directly:
        for chunk in vera.toolchain.execute_tool_chain(query, mode="fuzzy_stepwise"):
    If no ToolRegistry is provided the planner silently degrades to exact-match only — same behaviour as the base class.
    """