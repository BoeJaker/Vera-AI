"""
Vera Unified ToolChain Planner
================================
Single, clean implementation that unifies all prior variants:

  • Sequential    – classic batch plan → execute (original toolchain.py)
  • Adaptive      – plan one step at a time, feed output into next decision
                    (was adaptive_toolchain.py / AdaptiveToolChainPlanner)
  • Expert        – 5-stage domain-expert pipeline with tool-agent routing
                    (was chain_of_experts.py; now routes through AgentTaskRouter
                     so the tool-agent's baked-in tool list is always used)
  • Parallel      – detect independent steps and run them concurrently

Public interface (unchanged – orchestrator tasks bind to these):
  vera.toolchain.execute_tool_chain(query, plan=None, mode="sequential")
  vera.toolchain.plan_tool_chain(query)                # generator

Execution modes (passed as ``mode`` kwarg):
  "sequential"  – default, compatible with existing orchestrator wiring
  "adaptive"    – step-by-step, re-plans after each tool output
  "expert"      – 5-stage domain expert pipeline
  "parallel"    – auto-detects independent steps and runs them concurrently
  "hybrid"      – tries expert first, falls back to sequential on error

The class is a drop-in replacement:  just swap the import in vera.py.
"""

from __future__ import annotations

import ast
import hashlib
import json
import logging
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Generator, Iterator, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS
# ============================================================================

class ExecutionMode(str, Enum):
    SEQUENTIAL = "sequential"
    ADAPTIVE   = "adaptive"
    EXPERT     = "expert"
    PARALLEL   = "parallel"
    HYBRID     = "hybrid"


class Domain(str, Enum):
    WEB_DEVELOPMENT      = "web_development"
    BACKEND_DEVELOPMENT  = "backend_development"
    DATABASE             = "database"
    DEVOPS               = "devops"
    SECURITY             = "security"
    NETWORKING           = "networking"
    DATA_ANALYSIS        = "data_analysis"
    MACHINE_LEARNING     = "machine_learning"
    DATA_ENGINEERING     = "data_engineering"
    RESEARCH             = "research"
    WRITING              = "writing"
    DOCUMENTATION        = "documentation"
    FILE_OPERATIONS      = "file_operations"
    CODE_EXECUTION       = "code_execution"
    SYSTEM_ADMINISTRATION = "system_administration"
    API_INTEGRATION      = "api_integration"
    WEB_SCRAPING         = "web_scraping"
    OSINT                = "osint"
    PENETRATION_TESTING  = "penetration_testing"
    VULNERABILITY_ANALYSIS = "vulnerability_analysis"
    BASH                 = "bash"
    PYTHON               = "python"
    GENERAL              = "general"


# ============================================================================
# UTILITIES
# ============================================================================

def _extract_text(chunk: Any) -> str:
    """Safely extract a string from any chunk type an LLM might yield."""
    if chunk is None:
        return ""
    if isinstance(chunk, str):
        return chunk
    if isinstance(chunk, dict):
        for key in ("text", "content", "message", "data", "output", "delta"):
            if key in chunk and chunk[key] is not None:
                val = chunk[key]
                return str(val) if not isinstance(val, str) else val
        return str(chunk)
    for attr in ("text", "content"):
        val = getattr(chunk, attr, None)
        if val is not None:
            return str(val)
    return str(chunk)


def _clean_json(text: str) -> str:
    """Strip markdown fences and surrounding whitespace from LLM JSON output."""
    text = text.strip()
    for fence in ("```json", "```"):
        if text.startswith(fence):
            text = text[len(fence):].strip()
            break
    if text.endswith("```"):
        text = text[:-3].strip()
    return text


def _extract_json(text: str) -> Optional[Any]:
    """
    Robustly extract the first JSON value from LLM output.
    Handles fenced blocks, inline preambles, and nested braces.
    """
    if not text:
        return None

    # 1. Direct parse
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # 2. Fenced block
    import re
    fenced = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError:
            pass

    # 3. Walk character by character to find the first complete JSON object/array
    for start_char, end_char in (("{", "}"), ("[", "]")):
        start = text.find(start_char)
        if start == -1:
            continue
        depth = 0
        for i, ch in enumerate(text[start:], start):
            if ch == start_char:
                depth += 1
            elif ch == end_char:
                depth -= 1
                if depth == 0:
                    candidate = text[start:i + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        pass
                    break

    return None


def _resolve_placeholders(value: Any, step_num: int, outputs: Dict[str, str]) -> Any:
    """
    Replace {prev} and {step_N} tokens in any string value.
    Non-string values are passed through unchanged.
    """
    if not isinstance(value, str):
        return value
    if "{prev}" in value:
        prev = outputs.get(f"step_{step_num - 1}", "")
        value = value.replace("{prev}", str(prev))
    for i in range(1, step_num):
        placeholder = f"{{step_{i}}}"
        if placeholder in value:
            value = value.replace(placeholder, str(outputs.get(f"step_{i}", "")))
    return value


def _resolve_input(raw_input: Any, step_num: int, outputs: Dict[str, str]) -> Any:
    """
    Resolve placeholders in both dict and string inputs, then attempt
    to parse string inputs that look like JSON/Python dicts.
    """
    if isinstance(raw_input, dict):
        return {k: _resolve_placeholders(v, step_num, outputs) for k, v in raw_input.items()}

    resolved = _resolve_placeholders(str(raw_input), step_num, outputs)
    stripped = resolved.strip()

    # Try to coerce JSON-looking strings into dicts so multi-param tools work
    if (stripped.startswith("{") and stripped.endswith("}")) or \
       (stripped.startswith("[") and stripped.endswith("]")):
        for parser in (json.loads, ast.literal_eval):
            try:
                parsed = parser(stripped)
                if isinstance(parsed, dict):
                    return parsed
            except (ValueError, SyntaxError, json.JSONDecodeError):
                pass

    return resolved


def _call_tool(tool: Any, tool_input: Any) -> Iterator[str]:
    """
    Invoke a tool (streaming or not) and yield string chunks.
    Handles run / invoke / func / callable variants.
    """
    for attr in ("run", "invoke", "func"):
        func = getattr(tool, attr, None)
        if callable(func):
            break
    else:
        if callable(tool):
            func = tool
        else:
            raise ValueError(f"Tool '{tool.name}' is not callable")

    try:
        if isinstance(tool_input, dict):
            result = func(**tool_input)
        else:
            result = func(tool_input)
    except TypeError as exc:
        import inspect
        sig = inspect.signature(func)
        raise TypeError(
            f"Argument mismatch for '{tool.name}': {exc}\n"
            f"Signature: {sig}\n"
            f"Input: {tool_input!r}"
        ) from exc

    # Streaming result
    if hasattr(result, "__iter__") and not isinstance(result, (str, bytes, dict)):
        for chunk in result:
            yield _extract_text(chunk)
    else:
        yield str(result)


# ============================================================================
# TOOL-DOMAIN REGISTRY  (used by Expert mode)
# ============================================================================

_DEFAULT_DOMAIN_MAP: Dict[str, List[str]] = {
    "read_file":              ["file_operations"],
    "write_file":             ["file_operations"],
    "list_directory":         ["file_operations"],
    "search_files":           ["file_operations"],
    "python":                 ["code_execution", "data_analysis"],
    "bash":                   ["system_administration", "devops"],
    "web_search":             ["research", "web_scraping"],
    "news_search":            ["research"],
    "web_search_deep":        ["research", "web_scraping"],
    "crawl_website":          ["web_scraping", "research"],
    "navigate_web_smart":     ["research", "web_scraping"],
    "http_request":           ["api_integration", "web_development"],
    "sqlite_query":           ["database", "data_analysis"],
    "postgres_query":         ["database", "data_engineering"],
    "nmap_scan":              ["security", "networking", "osint"],
    "vulnerability_search":   ["security", "vulnerability_analysis"],
    "osint_search":           ["osint", "research"],
    "dorking_search":         ["osint", "research"],
    "git":                    ["devops", "backend_development"],
    "search_memory":          ["general"],
}


# ============================================================================
# LLM DISPATCHER
# ============================================================================
#
# The planner should never call fast_llm / deep_llm / etc. directly.
# Instead it uses a single virtual tool name "llm" and declares intent
# via a "mode" field.  The dispatcher resolves the right LLM at runtime.
#
# Planner step syntax:
#   {"tool": "llm", "input": {"prompt": "...", "mode": "code",
#                              "context": "{prev}"}}   ← context is optional
#
# All raw LLM tool names are suppressed from the visible tool list so
# the low-temp planning LLM cannot accidentally call them directly.
# ============================================================================

_LLM_VIRTUAL_TOOL_NAME = "llm"

# Tool names from LLMTool (tools.py) that the planner must NOT call directly.
# The planner uses {"tool": "llm", "input": {"prompt": ..., "mode": ...}} instead.
# At dispatch time the right underlying tool is selected by mode.
_SUPPRESSED_LLM_TOOL_NAMES: Set[str] = {
    "fast_llm", "deep_llm", "coding_llm",
}

# mode → the tool name registered in vera.tools (from LLMTool / add_llm_tools)
# These names must match the `name=` passed to StructuredTool.from_function()
# in tools.py exactly.
_LLM_MODE_TO_TOOL: Dict[str, str] = {
    "fast":     "fast_llm",    # fast_llm_query  – quick tasks, summaries
    "analyse":  "deep_llm",    # deep_llm_query  – structured reasoning
    "reason":   "deep_llm",    # deep_llm_query  – logical inference
    "creative": "deep_llm",    # deep_llm_query  – prose, essays, marketing
    "code":     "coding_llm",  # coding_llm_query – code gen, debug, review
    "document": "deep_llm",    # deep_llm_query  – READMEs, API docs, reports
}

# Fallback tool name order when the preferred tool is not in vera.tools
_LLM_TOOL_FALLBACK_ORDER = ["coding_llm", "deep_llm", "fast_llm"]

# Injected into every planning prompt so the planner knows to use the
# virtual "llm" tool rather than the underlying tool names directly.
_LLM_TOOL_HINT = """\

SPECIAL TOOL — "llm"
  ONLY use this tool for steps that SYNTHESISE, WRITE, or TRANSFORM data
  that has already been collected by other tools.

  NEVER use "llm" as a substitute for a real tool that can fetch, search,
  or execute — the llm tool has no internet access and no ability to run
  code.  Always use the appropriate real tool first:
    • Need current information / facts?       → web_search or news_search
    • Need to crawl a page?                   → crawl_website
    • Need to run code?                       → python or bash
    • Need to read/write a file?              → read_file / write_file
    • Need to query a database?               → sqlite_query / postgres_query

  Use "llm" ONLY as a final synthesis / formatting step AFTER real tools
  have gathered the raw information:
    ✓  web_search → llm (summarise results)
    ✓  python     → llm (explain the output)
    ✗  llm alone for any task that requires fresh data or computation

  Do NOT use fast_llm / deep_llm / coding_llm directly — use "llm" instead.

  Input must be a JSON object:
    {"prompt":  "<full instructions for the LLM>",
     "mode":    "<see modes below>",
     "context": "<optional: prior step output to prepend to prompt>"}

  Modes:
    "fast"      Quick summaries, simple transforms, short answers
    "analyse"   Synthesise and interpret data already provided in context
    "reason"    Multi-step logical chains on data already gathered
    "creative"  Blog posts, essays, marketing copy — after research is done
    "code"      Write / review code based on a clear spec
    "document"  Technical docs, READMEs — after content is assembled

  Correct examples:
    Step 1: {"tool": "web_search",  "input": "latest AI breakthroughs 2025"}
    Step 2: {"tool": "llm", "input": {"prompt": "Summarise these results into a report:", "context": "{prev}", "mode": "analyse"}}

    Step 1: {"tool": "python", "input": "import pandas as pd; ..."}
    Step 2: {"tool": "llm", "input": {"prompt": "Explain what this output means:", "context": "{prev}", "mode": "fast"}}

  Incorrect (llm has no internet — this will produce hallucinated output):
    {"tool": "llm", "input": {"prompt": "Research the latest AI news", "mode": "analyse"}}
"""


class LLMDispatcher:
    """
    Intercepts {"tool": "llm", "input": {"prompt": ..., "mode": ..., "context": ...}}
    plan steps and delegates to the matching registered LLM tool in vera.tools.

    Delegation to the existing fast_llm / deep_llm / coding_llm StructuredTools
    (defined in tools.py / LLMTool) means all their built-in behaviour is
    preserved: orchestrator routing, memory storage, and fallback handling.

    The dispatcher's only responsibilities are:
      1. Parse mode + context from the virtual tool input.
      2. Prepend context to the prompt if provided.
      3. Look up the right named tool from vera.tools.
      4. Call it via the shared _call_tool helper.
    """

    def __init__(self, tools: List[Any]) -> None:
        # Indexed at construction time for O(1) lookup.
        self._tool_index: Dict[str, Any] = {
            getattr(t, "name", ""): t
            for t in tools
            if getattr(t, "name", None)
        }

    def _resolve_tool(self, mode: str) -> Any:
        """
        Return the registered tool object for the requested mode.
        Walks _LLM_TOOL_FALLBACK_ORDER if the preferred tool is absent.
        """
        preferred_name = _LLM_MODE_TO_TOOL.get(mode.lower(), "fast_llm")
        tool = self._tool_index.get(preferred_name)
        if tool is not None:
            return tool, preferred_name

        logger.warning(
            f"LLMDispatcher: tool '{preferred_name}' not registered, "
            f"trying fallbacks: {_LLM_TOOL_FALLBACK_ORDER}"
        )
        for name in _LLM_TOOL_FALLBACK_ORDER:
            tool = self._tool_index.get(name)
            if tool is not None:
                logger.info(f"LLMDispatcher: using '{name}' as fallback for mode='{mode}'")
                return tool, name

        raise RuntimeError(
            f"LLMDispatcher: no LLM tool available for mode='{mode}'. "
            f"Ensure add_llm_tools() has been called in ToolLoader. "
            f"Tried: {preferred_name}, {_LLM_TOOL_FALLBACK_ORDER}"
        )

    def _build_query(self, tool_input: Any) -> Tuple[str, str]:
        """
        Parse tool_input → (query_string, mode).

        Accepts:
          dict  {"prompt": "...", "mode": "code", "context": "..."}
          str   treated as the full prompt, mode defaults to "fast"

        Context (if provided) is prepended to prompt so the underlying
        tool receives a single, self-contained query string — matching
        exactly how fast_llm_query / deep_llm_query / coding_llm_query
        expect to be called (single `query` arg).
        """
        if isinstance(tool_input, dict):
            prompt  = str(tool_input.get("prompt", "")).strip()
            mode    = str(tool_input.get("mode", "fast")).lower()
            context = str(tool_input.get("context", "")).strip()
        else:
            prompt  = str(tool_input).strip()
            mode    = "fast"
            context = ""

        if not prompt:
            raise ValueError("LLMDispatcher: 'prompt' is required in llm tool input")

        query = f"{context}\n\n{prompt}" if context else prompt
        return query, mode

    def dispatch(self, tool_input: Any) -> Iterator[str]:
        """
        Build the query, select the right tool, call it, yield chunks.
        All orchestrator routing, memory storage, and error handling
        happens inside the delegated tool — nothing is duplicated here.
        """
        query, mode = self._build_query(tool_input)
        tool, tool_name = self._resolve_tool(mode)

        logger.info(
            f"LLMDispatcher: mode='{mode}' → tool='{tool_name}' | "
            f"query_len={len(query)}"
        )

        # The LLM tools accept a single positional string arg ("query").
        yield from _call_tool(tool, query)


class _ToolDomainRegistry:
    """Lightweight mapping of tool names → domains."""

    def __init__(self) -> None:
        self._map: Dict[str, Set[str]] = {}
        for tool_name, domains in _DEFAULT_DOMAIN_MAP.items():
            self._map[tool_name] = set(domains)

    def register(self, tool_name: str, domains: List[str]) -> None:
        self._map[tool_name] = set(domains)

    def domains_for(self, tool_name: str) -> Set[str]:
        return self._map.get(tool_name, {"general"})

    def tools_for_domains(self, domains: Set[str]) -> List[str]:
        result = set()
        for tool_name, tool_domains in self._map.items():
            if tool_domains & domains:
                result.add(tool_name)
        return list(result)


# ============================================================================
# ADAPTIVE PLANNING PROMPTS
# ============================================================================

_ADAPTIVE_SYSTEM = """\
You are a precise tool-orchestration planner.

Given an original query and the history of tool calls already made, decide
the SINGLE best next tool to call.

CRITICAL: Output a single raw JSON object only. No markdown, no fences, no
text before or after. First character must be '{'. Last character must be '}'.

To invoke a tool:
  {"tool": "<name>", "input": <string or object>}

When the goal is fully achieved:
  {"tool": "DONE", "summary": "<brief summary of what was accomplished>"}

Rules:
- Never repeat a call that already produced the needed information.
- Use the most targeted tool; do not over-engineer.
- Only use tool names from the provided list.
"""

_ADAPTIVE_USER = """\
Original query:
{query}

Tool history so far ({n} step(s)):
{history}

Available tools:
{tool_names}

What is the single best next step? Respond with JSON only.
"""


# ============================================================================
# MAIN CLASS
# ============================================================================

class ToolChainPlanner:
    """
    Unified toolchain planner.  A single instance exposes all execution modes
    through one entry point:  ``execute_tool_chain(query, mode=...)``.

    Instantiation mirrors the original signature so vera.py needs no changes:
        self.toolchain = ToolChainPlanner(self, self.tools)
    """

    def __init__(self, agent: Any, tools: List[Any]) -> None:
        self.agent   = agent
        self.tools   = tools
        self.history = agent.buffer_memory.load_memory_variables({}).get(
            "chat_history", []
        )
        self._domain_registry = _ToolDomainRegistry()
        self._llm_dispatcher  = LLMDispatcher(tools)

        # Agent router (optional – used by expert & planning LLM selection)
        self._router: Optional[Any] = None
        if hasattr(agent, "agents") and agent.agents:
            try:
                from Vera.Orchestration.agent_integration import AgentTaskRouter
                self._router = AgentTaskRouter(agent)
                logger.debug("ToolChainPlanner: agent router available")
            except Exception as exc:
                logger.warning(f"ToolChainPlanner: agent router unavailable – {exc}")

    # ------------------------------------------------------------------
    # ROUTER HELPERS
    # ------------------------------------------------------------------

    def _get_planning_llm(self) -> Tuple[Any, bool]:
        """
        Return (llm, tools_already_in_system_prompt).

        Primary path  : AgentTaskRouter → tool-agent
                        (tool list baked into its system prompt at build time)
                        → (llm, True)  — do NOT inject tool list again.

        Fallback path : vera.tool_llm directly
                        → (llm, False) — caller MUST inject the tool list.
        """
        if self._router:
            try:
                agent_name = self._router.get_agent_for_task("tool_execution")
                llm = self._router.create_llm_for_agent(agent_name)
                logger.debug(f"Planning LLM: tool-agent '{agent_name}'")
                return llm, True
            except Exception as exc:
                logger.warning(f"Agent router failed, using tool_llm fallback: {exc}")
        return self.agent.tool_llm, False

    def _format_tool_list(self) -> str:
        """
        Compact tool list for injection into fallback planning prompts.
        Suppressed LLM tool names are excluded; the single "llm" virtual
        tool is prepended so the planner sees exactly one LLM entry.
        """
        lines = ["  llm                            Route any generation task to the best LLM (see hint below)"]
        for t in self.tools:
            name = getattr(t, "name", None)
            if not name or name in _SUPPRESSED_LLM_TOOL_NAMES:
                continue
            desc = getattr(t, "description", "")
            if len(desc) > 80:
                desc = desc[:77] + "..."
            lines.append(f"  {name:<30} {desc}")
        return "\n".join(lines)

    def _inject_tool_list_if_needed(self, prompt: str, agent_has_tools: bool) -> str:
        """
        Append the filtered tool list (fallback path only) AND the LLM
        dispatcher hint (always — both paths need it so the planner knows
        to use {"tool": "llm", ...} for any generation step).
        """
        result = prompt
        if not agent_has_tools:
            result = (
                result
                + "\n\nAVAILABLE TOOLS (use ONLY these exact names):\n"
                + self._format_tool_list()
                + "\n\nDo NOT invent tool names not listed above."
            )
        result = result + "\n\n" + _LLM_TOOL_HINT
        return result

    def _stream_llm(self, llm: Any, prompt: str) -> Iterator[str]:
        """Stream text chunks from any LLM, normalising chunk types."""
        if hasattr(self.agent, "stream_llm"):
            for chunk in self.agent.stream_llm(llm, prompt):
                yield _extract_text(chunk)
        else:
            yield str(llm.invoke(prompt))

    # ------------------------------------------------------------------
    # MEMORY HELPERS
    # ------------------------------------------------------------------

    def _save_step(self, step_num: int, tool_name: str, result: str) -> None:
        try:
            self.agent.mem.add_session_memory(
                self.agent.sess.id,
                f"Step {step_num} – {tool_name}\n{result}",
                "Step",
                {"topic": "step", "author": "toolchain",
                 "toolchain_step": step_num, "tool": tool_name},
            )
            self.agent.save_to_memory(f"Step {step_num} – {tool_name}", result)
        except Exception as exc:
            logger.warning(f"Could not save step to memory: {exc}")

    def _save_plan(self, plan: Any, plan_id: str, label: str = "Plan") -> None:
        try:
            import os
            os.makedirs("./Configuration", exist_ok=True)
            with open("./Configuration/last_tool_plan.json", "w", encoding="utf-8") as fh:
                json.dump(plan, fh, indent=2)
            self.agent.mem.add_session_memory(
                self.agent.sess.id,
                json.dumps(plan, default=str),
                label,
                {"topic": "plan", "plan_id": plan_id},
                promote=True,
            )
        except Exception as exc:
            logger.warning(f"Could not save plan: {exc}")

    # ------------------------------------------------------------------
    # TOOL LOOKUP
    # ------------------------------------------------------------------

    def _find_tool(self, name: str) -> Optional[Any]:
        """
        Look up a real tool by name.  Returns None for suppressed LLM tool
        names so callers fall through to _run_step's dispatcher branch.
        """
        if name in _SUPPRESSED_LLM_TOOL_NAMES:
            return None
        return next((t for t in self.tools if getattr(t, "name", None) == name), None)

    def _run_step(
        self,
        tool_name: str,
        tool_input: Any,
        step_num: int,
        outputs: Dict[str, str],
        label: str = "ToolChain",
    ) -> Iterator[str]:
        """
        Single authoritative step executor used by all mode-executors.

        Handles in order:
          1. Virtual "llm" tool  → LLMDispatcher
          2. Suppressed LLM names used anyway  → LLMDispatcher (with warning)
          3. Real registered tools  → _call_tool
          4. Unknown tool name  → error chunk
        """
        resolved = _resolve_input(tool_input, step_num, outputs)

        # ── 1 & 2: Virtual / suppressed LLM tool ─────────────────────
        is_llm = (
            tool_name == _LLM_VIRTUAL_TOOL_NAME
            or tool_name in _SUPPRESSED_LLM_TOOL_NAMES
        )
        if is_llm:
            if tool_name != _LLM_VIRTUAL_TOOL_NAME:
                logger.warning(
                    f"[{label}] Planner used suppressed tool '{tool_name}' – "
                    f"routing through LLMDispatcher as mode='fast'."
                )
                # Coerce to dispatcher format
                if isinstance(resolved, str):
                    resolved = {"prompt": resolved, "mode": "fast"}
                elif isinstance(resolved, dict) and "mode" not in resolved:
                    resolved = {**resolved, "mode": "fast"}

            mode = resolved.get("mode", "fast") if isinstance(resolved, dict) else "fast"
            logger.info(f"[{label}] LLM dispatch → mode='{mode}'")
            yield from self._llm_dispatcher.dispatch(resolved)
            return

        # ── 3: Real tool ──────────────────────────────────────────────
        tool_obj = self._find_tool(tool_name)
        if tool_obj is not None:
            yield from _call_tool(tool_obj, resolved)
            return

        # ── 4: Unknown ────────────────────────────────────────────────
        msg = f"[{label}] ERROR: tool '{tool_name}' not found.\n"
        logger.error(msg.strip())
        yield msg

    # ------------------------------------------------------------------
    # PUBLIC ENTRY POINT
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # PLAN GENERATOR  (kept for backward compat; yields chunks then plan)
    # ------------------------------------------------------------------

    def plan_tool_chain(
        self, query: str, history_context: str = ""
    ) -> Iterator[Any]:
        """
        Generate a sequential plan.
        Yields text chunks while planning, then yields the final plan list.
        """
        llm, agent_has_tools = self._get_planning_llm()

        base_prompt = (
            f"You are a rigorous system planner. "
            f"Generate ONLY a JSON array describing tool invocations.\n\n"
            f"Query: {query}\n\n"
            f"Context: {history_context}\n\n"
            f"Return a JSON array where each element has:\n"
            f'  {{"tool": "<name>", "input": <string or object>}}\n\n'
            f"No commentary, no markdown, no prose."
        )
        prompt = self._inject_tool_list_if_needed(base_prompt, agent_has_tools)

        raw = ""
        for chunk in self._stream_llm(llm, prompt):
            yield chunk
            raw += chunk

        plan = _extract_json(_clean_json(raw))
        if plan is None:
            raise ValueError(f"Planning produced no valid JSON.\n\nRaw output:\n{raw}")

        if isinstance(plan, dict):
            plan = [plan]
        if not isinstance(plan, list) or not all(isinstance(s, dict) for s in plan):
            raise ValueError(f"Unexpected plan format: {plan!r}")

        plan_id = hashlib.sha256(
            f"{time.time()}_{json.dumps(plan)}".encode()
        ).hexdigest()
        self._save_plan(plan, plan_id)

        yield plan

    # ==================================================================
    # SEQUENTIAL EXECUTOR  (original core)
    # ==================================================================

    def _execute_sequential(
        self,
        query: str,
        plan: Optional[Any] = None,
        _depth: int = 0,          # internal recursion guard
        **_kwargs,
    ) -> Iterator[str]:
        """
        Classic batch-plan → execute.
        Yields streaming text throughout.

        _depth prevents infinite replanning loops:
          0  = first call  → may trigger one recovery + one goal-check retry
          1  = recovery / retry call  → executes plan only, no further replanning
        """
        # ── 1. Plan ──────────────────────────────────────────────────
        if plan is None:
            gen = self.plan_tool_chain(query)
            tool_plan: Optional[List[Dict]] = None
            for item in gen:
                if isinstance(item, list):
                    tool_plan = item
                else:
                    yield _extract_text(item)
            if tool_plan is None:
                yield "[ToolChain] ERROR: no plan was generated.\n"
                return
        else:
            tool_plan = plan if isinstance(plan, list) else [plan]

        logger.info(f"[Sequential] Plan (depth={_depth}): {json.dumps(tool_plan, indent=2)}")

        # ── 2. Execute ───────────────────────────────────────────────
        outputs: Dict[str, str] = {}
        errors  = False

        for step_num, step in enumerate(tool_plan, 1):
            tool_name  = step.get("tool", "")
            raw_input  = step.get("input", "")

            yield f"[ToolChain] Step {step_num} → {tool_name}\n"
            logger.info(f"[Sequential] Step {step_num}: {tool_name}")

            collected: List[str] = []
            try:
                for chunk in self._run_step(tool_name, raw_input, step_num, outputs):
                    yield chunk
                    collected.append(chunk)
                result = "".join(collected)
                if "[ToolChain] ERROR" in result or "ERROR: tool" in result:
                    errors = True
            except Exception as exc:
                result = f"[ToolChain] ERROR in {tool_name}: {exc}\n{traceback.format_exc()}"
                yield result
                errors = True

            outputs[f"step_{step_num}"] = result
            outputs[tool_name]          = result
            self._save_step(step_num, tool_name, result)
            logger.debug(f"[Sequential] Step {step_num} result preview: {result[:200]}")

        # ── 3. Error recovery — only on first call, only once ────────
        if errors and _depth == 0:
            yield "\n[ToolChain] Errors detected – attempting recovery plan…\n"
            recovery_context = json.dumps(outputs, indent=2, default=str)
            recovery_gen = self.plan_tool_chain(
                f"Recover and complete: {query}",
                history_context=recovery_context,
            )
            recovery_plan: Optional[List[Dict]] = None
            for item in recovery_gen:
                if isinstance(item, list):
                    recovery_plan = item
                else:
                    yield _extract_text(item)
            if recovery_plan:
                yield from self._execute_sequential(query, plan=recovery_plan, _depth=1)
                return

        # ── 4. Goal check — only on first call, strict yes/no ────────
        if _depth == 0:
            final_result = outputs.get(f"step_{len(tool_plan)}", "")
            review_prompt = (
                f"Query: {query}\n"
                f"Final result:\n{final_result[:2000]}\n\n"
                f"Does this fully answer the query?\n"
                f"Reply with a single word: YES or NO"
            )
            try:
                review = str(self.agent.fast_llm.invoke(review_prompt)).strip().upper()
                logger.info(f"[Sequential] Goal-check response: {review!r}")
                # Only replan if the first word is clearly NO
                goal_met = not review.startswith("NO")
            except Exception as exc:
                logger.warning(f"[Sequential] Goal-check failed: {exc} – assuming goal met")
                goal_met = True

            if not goal_met:
                yield "\n[ToolChain] Goal not fully met – replanning once…\n"
                retry_gen = self.plan_tool_chain(
                    f"Complete the following goal more thoroughly. Original query: {query}",
                    history_context=json.dumps(outputs, indent=2, default=str),
                )
                retry_plan: Optional[List[Dict]] = None
                for item in retry_gen:
                    if isinstance(item, list):
                        retry_plan = item
                    else:
                        yield _extract_text(item)
                if retry_plan:
                    yield from self._execute_sequential(query, plan=retry_plan, _depth=1)

    # ==================================================================
    # ADAPTIVE EXECUTOR  (from adaptive_toolchain.py)
    # ==================================================================

    def _plan_next_adaptive_step(
        self, query: str, history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Ask the LLM for exactly one next tool invocation (or DONE).
        Always routes through the agent router so the tool list is available.
        """
        llm, agent_has_tools = self._get_planning_llm()

        tool_names = ", ".join(
            t.name for t in self.tools if hasattr(t, "name")
        )
        history_text = "\n".join(
            f"Step {i + 1}:\n"
            f"  tool  : {h['tool']}\n"
            f"  input : {json.dumps(h['input'], default=str)[:400]}\n"
            f"  output: {str(h['output'])[:800]}"
            for i, h in enumerate(history)
        ) or "(none yet)"

        user_section = _ADAPTIVE_USER.format(
            query=query,
            n=len(history),
            history=history_text,
            tool_names=tool_names,
        )
        prompt = _ADAPTIVE_SYSTEM + "\n\n" + user_section
        # Even on fallback path, tool names are embedded in the user section
        # above so we don't need the full tool-list injection here.

        raw = "".join(self._stream_llm(llm, prompt))
        step = _extract_json(raw)

        if not isinstance(step, dict) or "tool" not in step:
            raise ValueError(
                f"LLM returned invalid JSON for adaptive step.\nRaw:\n{raw}"
            )
        return step

    def _execute_adaptive(
        self,
        query: str,
        max_steps: int = 20,
        **_kwargs,
    ) -> Iterator[str]:
        """
        Adaptive step-by-step execution.
        Plans one step, executes it, feeds the result back into the next
        planning decision.  Terminates when the LLM returns {"tool":"DONE"}.
        """
        history: List[Dict[str, Any]] = []
        step_num = 0

        yield f"[Adaptive] Starting: {query[:120]}\n"

        while step_num < max_steps:
            step_num += 1
            yield f"\n[Adaptive] ── Planning step {step_num} ──\n"

            try:
                step = self._plan_next_adaptive_step(query, history)
            except Exception as exc:
                yield f"[Adaptive] Planning error: {exc}\n"
                break

            tool_name  = step.get("tool", "")
            tool_input = step.get("input", "")

            if tool_name.upper() == "DONE":
                summary = step.get("summary", "(no summary)")
                yield f"\n[Adaptive] ✓ Goal achieved after {step_num - 1} step(s).\n"
                yield f"[Adaptive] Summary: {summary}\n"
                self._save_adaptive_plan(query, history, summary)
                return

            yield f"[Adaptive] Step {step_num}: {tool_name}\n"
            yield f"[Adaptive] Input: {json.dumps(tool_input, default=str)[:300]}\n"

            history_outputs = {f"step_{i+1}": h["output"] for i, h in enumerate(history)}
            collected: List[str] = []
            try:
                for chunk in self._run_step(tool_name, tool_input, step_num, history_outputs, "Adaptive"):
                    collected.append(chunk)
                output = "".join(collected)
            except Exception as exc:
                output = f"[ERROR] {tool_name}: {exc}\n{traceback.format_exc()}"

            preview = output[:600] + ("…" if len(output) > 600 else "")
            yield f"[Adaptive] Output:\n{preview}\n"

            history.append({
                "step": step_num, "tool": tool_name,
                "input": tool_input, "output": output,
            })
            self._save_step(step_num, tool_name, output)

        # Max steps reached
        yield f"\n[Adaptive] ⚠ Reached max_steps ({max_steps}).\n"
        yield "[Adaptive] Generating partial summary…\n"
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
        self._save_adaptive_plan(query, history, partial_summary)

    def _save_adaptive_plan(
        self, query: str, history: List[Dict], summary: str
    ) -> None:
        plan_id = hashlib.sha256(
            f"{time.time()}_{query}".encode()
        ).hexdigest()[:16]
        try:
            self.agent.mem.add_session_memory(
                self.agent.sess.id,
                json.dumps({
                    "query": query, "steps": history,
                    "summary": summary, "plan_id": plan_id,
                }, default=str),
                "AdaptivePlan",
                {"topic": "adaptive_plan", "plan_id": plan_id},
                promote=True,
            )
        except Exception as exc:
            logger.warning(f"Could not save adaptive plan: {exc}")

    # ==================================================================
    # PARALLEL EXECUTOR
    # ==================================================================

    def _analyse_dependencies(
        self, plan: List[Dict]
    ) -> Dict[int, Set[int]]:
        """Return {step_index: set_of_step_indices_it_depends_on}."""
        deps: Dict[int, Set[int]] = {}
        for i, step in enumerate(plan):
            step_deps: Set[int] = set()
            tool_input = str(step.get("input", ""))
            if "{prev}" in tool_input and i > 0:
                step_deps.add(i - 1)
            for j in range(i):
                if f"{{step_{j + 1}}}" in tool_input:
                    step_deps.add(j)
            deps[i] = step_deps
        return deps

    def _find_parallel_groups(
        self, plan: List[Dict]
    ) -> List[List[int]]:
        """
        Topological sort that groups steps that can run concurrently.
        Returns a list of groups; steps within a group have no inter-dependencies.
        """
        deps    = self._analyse_dependencies(plan)
        groups: List[List[int]] = []
        done:   Set[int] = set()

        while len(done) < len(plan):
            ready = [
                i for i in range(len(plan))
                if i not in done and deps[i].issubset(done)
            ]
            if not ready:
                break
            groups.append(ready)
            done.update(ready)

        return groups

    def _execute_step_sync(
        self,
        step: Dict,
        step_num: int,
        outputs: Dict[str, str],
    ) -> str:
        """Execute one step synchronously (for thread pool workers)."""
        tool_name  = step.get("tool", "")
        tool_input = step.get("input", "")
        return "".join(self._run_step(tool_name, tool_input, step_num, outputs, "Parallel"))

    def _execute_parallel(
        self,
        query: str,
        plan: Optional[Any] = None,
        max_workers: int = 6,
        **_kwargs,
    ) -> Iterator[str]:
        """
        Build a plan then execute independent steps concurrently.
        Falls back to sequential within each dependency group when needed.
        """
        if plan is None:
            gen = self.plan_tool_chain(query)
            tool_plan: Optional[List[Dict]] = None
            for item in gen:
                if isinstance(item, list):
                    tool_plan = item
                else:
                    yield _extract_text(item)
            if tool_plan is None:
                yield "[Parallel] ERROR: no plan generated.\n"
                return
        else:
            tool_plan = plan if isinstance(plan, list) else [plan]

        groups  = self._find_parallel_groups(tool_plan)
        outputs: Dict[str, str] = {}

        parallel_count = sum(1 for g in groups if len(g) > 1)
        if parallel_count:
            yield (
                f"\n[Parallel] {parallel_count} concurrent group(s) detected "
                f"across {len(tool_plan)} steps.\n"
            )

        for group_idx, group in enumerate(groups, 1):
            if len(group) == 1:
                # Single step – run inline to preserve streaming
                idx        = group[0]
                step_num   = idx + 1
                step       = tool_plan[idx]
                tool_name  = step.get("tool", "")
                tool_input = step.get("input", "")

                yield f"[Parallel] Step {step_num}: {tool_name}\n"
                collected: List[str] = []
                try:
                    for chunk in self._run_step(tool_name, tool_input, step_num, outputs, "Parallel"):
                        yield chunk
                        collected.append(chunk)
                    result = "".join(collected)
                except Exception as exc:
                    result = f"[ERROR] {tool_name}: {exc}"
                    yield result + "\n"
                outputs[f"step_{step_num}"] = result
                outputs[tool_name]          = result
                self._save_step(step_num, tool_name, result)

            else:
                # Multiple independent steps – run concurrently
                yield (
                    f"\n[Parallel] Group {group_idx}: "
                    f"running {len(group)} steps concurrently "
                    f"({', '.join(str(i + 1) for i in group)})\n"
                )
                futures: Dict[Any, Tuple[int, Dict]] = {}
                workers = min(max_workers, len(group))
                # Snapshot outputs for workers (they all read the same prior state)
                outputs_snapshot = dict(outputs)

                with ThreadPoolExecutor(max_workers=workers) as pool:
                    for idx in group:
                        step_num = idx + 1
                        step     = tool_plan[idx]
                        future   = pool.submit(
                            self._execute_step_sync,
                            step, step_num, outputs_snapshot,
                        )
                        futures[future] = (step_num, step)

                    completed = 0
                    for future in as_completed(futures):
                        step_num, step = futures[future]
                        tool_name = step.get("tool", "")
                        completed += 1
                        try:
                            result = future.result()
                            yield (
                                f"  ✓ Step {step_num} ({tool_name}) complete "
                                f"[{completed}/{len(group)}]\n"
                            )
                        except Exception as exc:
                            result = f"[ERROR] {tool_name}: {exc}"
                            yield f"  ✗ Step {step_num} ({tool_name}) failed: {exc}\n"

                        outputs[f"step_{step_num}"] = result
                        outputs[tool_name]          = result
                        self._save_step(step_num, tool_name, result)

                yield f"[Parallel] Group {group_idx} complete.\n"

        final_result = outputs.get(f"step_{len(tool_plan)}", "")
        yield f"\n[Parallel] Done.\n{final_result}\n"

    # ==================================================================
    # EXPERT EXECUTOR  (5-stage pipeline)
    # ==================================================================

    # ── Stage 1: Domain triage ─────────────────────────────────────

    def _expert_select_domains(
        self, query: str
    ) -> Tuple[Iterator[str], Dict]:
        """
        Ask fast_llm to identify relevant domains for the query.
        Returns (chunk_iterator, analysis_dict).
        We run this eagerly and buffer the chunks so callers can yield them.
        """
        domain_values = ", ".join(d.value for d in Domain)
        prompt = (
            f"Analyze this task and select relevant technical domains.\n\n"
            f"Available domains: {domain_values}\n\n"
            f"Task: {query}\n\n"
            f"Respond in JSON only:\n"
            f'{{"primary_domains": ["domain1"], "secondary_domains": ["domain2"], '
            f'"complexity": "simple|moderate|complex", "reasoning": "..."}}'
        )
        raw = ""
        chunks: List[str] = []
        for chunk in self._stream_llm(self.agent.fast_llm, prompt):
            chunks.append(chunk)
            raw += chunk

        result = _extract_json(_clean_json(raw)) or {}
        primary   = [
            d for d in result.get("primary_domains", [])
            if d in Domain._value2member_map_
        ]
        secondary = [
            d for d in result.get("secondary_domains", [])
            if d in Domain._value2member_map_
        ]
        analysis = {
            "primary":   primary,
            "secondary": secondary,
            "all":       list(set(primary + secondary)) or ["general"],
            "complexity": result.get("complexity", "simple"),
            "reasoning":  result.get("reasoning", ""),
        }
        return iter(chunks), analysis

    # ── Stage 2: Filter tools to domain ────────────────────────────

    def _expert_filter_tools(self, domains: List[str]) -> List[Any]:
        """Return tool objects relevant to the given domains."""
        relevant_names = set(
            self._domain_registry.tools_for_domains(set(domains))
        )
        # Always include general tools
        relevant_names |= set(
            self._domain_registry.tools_for_domains({"general"})
        )
        filtered = [
            t for t in self.tools
            if getattr(t, "name", None) in relevant_names
        ]
        # Fallback: if nothing matched, use all tools
        return filtered if filtered else self.tools

    # ── Stage 3 & 4: Expert planning (via tool-agent) ──────────────

    def _expert_plan(
        self,
        query: str,
        domains: List[str],
        filtered_tools: List[Any],
    ) -> Tuple[Iterator[str], Optional[List[Dict]]]:
        """
        Ask the tool-agent (via router) to create a domain-focused plan.
        The tool-agent already has the full tool list in its system prompt,
        so we only need to pass the domain context and filtered tool names.
        """
        llm, agent_has_tools = self._get_planning_llm()

        filtered_names = [
            getattr(t, "name", "") for t in filtered_tools if getattr(t, "name", None)
        ]
        tool_summary = ", ".join(filtered_names[:40])

        base_prompt = (
            f"You are a domain expert for: {', '.join(domains)}\n\n"
            f"Task: {query}\n\n"
            f"Preferred tools for these domains: {tool_summary}\n\n"
            f"Create a step-by-step plan. Each step uses ONE tool.\n"
            f"Reference previous results with {{prev}} or {{step_N}}.\n\n"
            f"Return ONLY a JSON array:\n"
            f'[{{"tool": "<name>", "input": "<value>", "reasoning": "<why>"}}]'
        )
        prompt = self._inject_tool_list_if_needed(base_prompt, agent_has_tools)

        raw = ""
        chunks: List[str] = []
        for chunk in self._stream_llm(llm, prompt):
            chunks.append(chunk)
            raw += chunk

        plan = _extract_json(_clean_json(raw))
        if isinstance(plan, dict):
            plan = [plan]
        if not isinstance(plan, list):
            plan = None

        return iter(chunks), plan

    # ── Stage 5: Execute with domain tools ─────────────────────────

    def _execute_expert(
        self, query: str, **_kwargs
    ) -> Iterator[str]:
        """
        Full 5-stage expert pipeline:
          1. Domain triage
          2. Tool filtering
          3. Expert planning (via tool-agent router)
          4. Tool-specialist input validation (inline)
          5. Execution
        """
        yield "\n[Expert] ── Stage 1: Domain Triage ──\n"
        chunk_iter, analysis = self._expert_select_domains(query)
        yield from chunk_iter

        domains    = analysis["all"]
        complexity = analysis["complexity"]
        reasoning  = analysis["reasoning"]
        yield (
            f"\n[Expert] Domains: {domains} | "
            f"Complexity: {complexity}\n"
            f"[Expert] Reasoning: {reasoning}\n"
        )

        yield "\n[Expert] ── Stage 2: Tool Filtering ──\n"
        filtered_tools = self._expert_filter_tools(domains)
        yield f"[Expert] {len(filtered_tools)} domain-relevant tools selected.\n"

        yield "\n[Expert] ── Stage 3: Expert Planning ──\n"
        chunk_iter, tool_plan = self._expert_plan(query, domains, filtered_tools)
        yield from chunk_iter

        if not tool_plan:
            yield "[Expert] ERROR: planning produced no valid plan. Falling back to sequential.\n"
            yield from self._execute_sequential(query)
            return

        plan_id = hashlib.sha256(
            f"{time.time()}_{json.dumps(tool_plan)}".encode()
        ).hexdigest()
        self._save_plan(tool_plan, plan_id, label="ExpertPlan")
        yield f"\n[Expert] Plan: {len(tool_plan)} steps.\n"

        yield "\n[Expert] ── Stages 4 & 5: Validation & Execution ──\n"
        outputs: Dict[str, str] = {}

        for step_num, step in enumerate(tool_plan, 1):
            tool_name  = step.get("tool", "")
            raw_input  = step.get("input", "")
            reasoning  = step.get("reasoning", "")
            tool_input = _resolve_input(raw_input, step_num, outputs)

            yield f"\n[Expert] Step {step_num}: {tool_name}"
            if reasoning:
                yield f"  ({reasoning})"
            yield "\n"

            # Stage 4 inline: the "llm" virtual tool is handled transparently by
            # _run_step.  Only validate non-llm tool names here.
            is_llm_step = (
                tool_name == _LLM_VIRTUAL_TOOL_NAME
                or tool_name in _SUPPRESSED_LLM_TOOL_NAMES
            )
            if not is_llm_step and self._find_tool(tool_name) is None:
                yield f"[Expert] WARNING: '{tool_name}' not found. Attempting correction…\n"
                corrected = self._expert_correct_tool_name(tool_name, filtered_tools, query, step)
                if corrected:
                    tool_name = getattr(corrected, "name", tool_name)
                    yield f"[Expert] Corrected to: {tool_name}\n"
                else:
                    result = f"[ERROR] Tool '{tool_name}' not found and could not be corrected."
                    yield result + "\n"
                    outputs[f"step_{step_num}"] = result
                    continue

            collected: List[str] = []
            try:
                for chunk in self._run_step(tool_name, tool_input, step_num, outputs, "Expert"):
                    yield chunk
                    collected.append(chunk)
                result = "".join(collected)
            except Exception as exc:
                result = f"[ERROR] {tool_name}: {exc}\n{traceback.format_exc()}"
                yield result

            outputs[f"step_{step_num}"] = result
            outputs[tool_name]          = result
            self._save_step(step_num, tool_name, result)

        yield "\n[Expert] ✓ Pipeline complete.\n"

    def _expert_correct_tool_name(
        self,
        bad_name: str,
        filtered_tools: List[Any],
        query: str,
        step: Dict,
    ) -> Optional[Any]:
        """
        When the plan names a hallucinated tool, ask the LLM to pick the
        closest real one from the filtered list.
        """
        real_names = [getattr(t, "name", "") for t in filtered_tools]
        prompt = (
            f"The plan requested a tool called '{bad_name}' which does not exist.\n"
            f"Available tools: {', '.join(real_names)}\n"
            f"Step goal: {step.get('reasoning', step.get('input', ''))}\n"
            f"Which tool is the best substitute? Reply with ONLY the tool name, nothing else."
        )
        correction = self.agent.fast_llm.invoke(prompt)
        corrected_name = str(correction).strip().split()[0]
        return self._find_tool(corrected_name)

    # ==================================================================
    # HYBRID EXECUTOR
    # ==================================================================

    def _execute_hybrid(
        self, query: str, plan: Optional[Any] = None, **kwargs
    ) -> Iterator[str]:
        """
        Try expert mode first; fall back to sequential on any failure.
        """
        yield "[Hybrid] Attempting expert mode…\n"
        try:
            expert_chunks: List[str] = []
            expert_failed = False
            for chunk in self._execute_expert(query, **kwargs):
                expert_chunks.append(chunk)
                if "[ERROR]" in chunk:
                    expert_failed = True
            if expert_failed:
                raise RuntimeError("Expert mode reported errors.")
            yield from iter(expert_chunks)
        except Exception as exc:
            yield f"[Hybrid] Expert mode failed ({exc}). Falling back to sequential.\n"
            safe_kwargs = {k: v for k, v in kwargs.items() if k != "_depth"}
            yield from self._execute_sequential(query, plan=plan, **safe_kwargs)

    # ==================================================================
    # COMPATIBILITY ALIASES & HELPERS
    # ==================================================================

    # Mapping from the old "strategy" kwarg used by task_registrations
    # (doc 4 / toolchain.execute task) onto our ExecutionMode values.
    _STRATEGY_TO_MODE: Dict[str, str] = {
        "default":       "sequential",
        "static":        "sequential",
        "quick":         "sequential",
        "comprehensive": "sequential",
        "exploratory":   "parallel",
        "multipath":     "parallel",
        "dynamic":       "adaptive",
        "adaptive":      "adaptive",
        "expert":        "expert",
        "hybrid":        "hybrid",
        "parallel":      "parallel",
        "concurrent":    "parallel",
    }

    def execute_adaptive(
        self, query: str, max_steps: int = 20
    ) -> Iterator[str]:
        """
        Public alias kept for backward compat with:
            vera._adaptive_toolchain.execute_adaptive(query, max_steps=N)
        The orchestrator task ``toolchain.execute_adaptive`` calls this.
        """
        yield from self._execute_adaptive(query, max_steps=max_steps)

    # Override execute_tool_chain to transparently handle the legacy
    # ``strategy`` and ``expert`` kwargs that the orchestrator task passes.
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
        Main entry point.  Yields streaming string chunks.

        Legacy kwargs supported for orchestrator task compatibility:
          strategy – maps to a mode (see _STRATEGY_TO_MODE)
          expert   – if True, forces mode="expert"
        """
        # Resolve mode: explicit > expert flag > strategy mapping
        if expert:
            resolved_mode = "expert"
        elif mode != "sequential":
            # Caller explicitly passed a non-default mode
            resolved_mode = mode
        else:
            resolved_mode = self._STRATEGY_TO_MODE.get(
                strategy.lower(), "sequential"
            )

        try:
            em = ExecutionMode(resolved_mode)
        except ValueError:
            logger.warning(
                f"Unknown mode '{resolved_mode}', defaulting to sequential."
            )
            em = ExecutionMode.SEQUENTIAL

        if em == ExecutionMode.ADAPTIVE:
            yield from self._execute_adaptive(
                query, max_steps=kwargs.get("max_steps", 20)
            )
        elif em == ExecutionMode.EXPERT:
            yield from self._execute_expert(query, **kwargs)
        elif em == ExecutionMode.PARALLEL:
            yield from self._execute_parallel(
                query, plan, max_workers=kwargs.get("max_workers", 6)
            )
        elif em == ExecutionMode.HYBRID:
            yield from self._execute_hybrid(query, plan, **kwargs)
        else:
            yield from self._execute_sequential(query, plan, **kwargs)


# ============================================================================
# VERA INTEGRATION HELPER
# ============================================================================

def setup_toolchain(vera_instance: Any) -> "ToolChainPlanner":
    """
    Drop-in replacement for however vera.py previously set up toolchain objects.

    Usage in Vera.__init__:
        from Vera.Toolchain.toolchain import setup_toolchain
        setup_toolchain(self)

    Sets up:
        vera.toolchain          – unified ToolChainPlanner (default mode: sequential)
        vera.toolchain_expert   – same instance, convenience alias for expert calls
        vera._adaptive_toolchain – same instance, alias for adaptive task compat
    """
    planner = ToolChainPlanner(vera_instance, vera_instance.tools)

    vera_instance.toolchain           = planner
    vera_instance.toolchain_expert    = planner   # orchestrator uses this for expert=True
    vera_instance._adaptive_toolchain = planner   # adaptive task uses execute_adaptive()

    logger.info(
        "Toolchain initialised: sequential / adaptive / expert / parallel / hybrid"
    )
    return planner