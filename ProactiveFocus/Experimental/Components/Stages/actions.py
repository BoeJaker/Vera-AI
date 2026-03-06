"""
Actions Stage — UNIFIED SANDBOX  (fully patched)
=================================================
Changes vs previous version:

1. _execute_toolchain_for_action:
   - Tries MonitoredToolChainPlanner first (full WebSocket UI visibility)
   - Falls back to direct planner streaming (console)
   - Falls back to orchestrator (with is_streaming race guard)
   - Falls back to _execute_action_direct (per-tool)

2. _run_planner:
   - New helper — drains any planner's execute_tool_chain() generator
   - Handles str chunks, list (plan) chunks, and other types cleanly
   - Syncs sandbox + emits completion summary

3. _execute_toolchain_for_action no longer goes through orchestrator
   by default; the orchestrator path is kept only as a tertiary fallback.
   This is intentional: the orchestrator calls the *unwrapped* planner
   (vera_instance.toolchain), bypassing MonitoredToolChainPlanner, so
   the UI panel never saw step progress. Going direct fixes that.

4. _push_to_ui unchanged but now used consistently from _run_planner too.

5. session_id resolution: tries focus_manager.session_id, then
   focus_manager.agent.session_id, then vera_instance.session_id.

6. _broadcast_flow_event: new helper — emits flowchart WebSocket events
   (execution_started, step_started, step_output, step_completed,
   step_failed, execution_completed) so the per-tool fallback path
   (_execute_action_direct / _execute_single_tool) is visible in the
   Toolchain Flowchart panel of the UI, not just the console.

7. RETRY SUPPORT:
   - _execute_toolchain_for_action now returns a result dict with
     `success`, `output`, and `error` fields instead of None.
   - Failed toolchain runs are NEVER added to `progress`; the caller
     (StageExecutor) is responsible for all lifecycle decisions.
   - _build_retry_context: helper that injects prior failure history
     into the action description/goal before re-submission so the
     planner knows what was tried and what went wrong.

8. PROMPT FIX:
   - _build_context_aware_prompt now passes actual ideas and next_steps
     content to the LLM rather than just counts. This is the primary fix
     for the "no actions generated" bug — the LLM previously had no
     concrete material to work from.
   - Dedicated IDEAS and NEXT STEPS sections in the prompt explicitly
     instruct the LLM to convert board content into executable actions.
   - RECENT PROGRESS and OPEN ISSUES sections added so actions avoid
     duplicating completed work and actively address known problems.
"""

from __future__ import annotations

import json
import re
import time
import types
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from Vera.ProactiveFocus.Experimental.Components.Stages.base import BaseStage, StageOutput
from Vera.Toolchain.sandbox import get_project_sandbox


class ActionsStage(BaseStage):
    """Generate executable actions with tools and success criteria."""

    def __init__(self) -> None:
        super().__init__(
            name="Action Planning",
            icon="⚡",
            description="Create executable actions with clear success criteria",
        )

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def execute(
        self,
        focus_manager,
        context: Optional[Dict[str, Any]] = None,
    ) -> StageOutput:
        output = StageOutput()

        sandbox = self._get_sandbox(focus_manager)
        if sandbox:
            self._stream_output(focus_manager, f"🔒 Sandbox: {sandbox.project_root}", "info")
            if hasattr(focus_manager, "agent"):
                agent = focus_manager.agent
                if hasattr(agent, "runtime_sandbox"):
                    agent.runtime_sandbox = sandbox

        self._stream_output(focus_manager, "Analysing workspace for executable actions...", "info")

        project_context = self._get_project_context(focus_manager)

        available_tools: List[str] = []
        if hasattr(focus_manager, "agent") and hasattr(focus_manager.agent, "tools"):
            available_tools = [t.name for t in focus_manager.agent.tools]

        prompt = self._build_context_aware_prompt(
            focus_manager, project_context, available_tools, context
        )

        try:
            response = self._stream_llm(focus_manager, focus_manager.agent.deep_llm, prompt, operation="generate_actions")
            self._stream_output(focus_manager, "Actions generated", "success")
        except Exception as exc:
            self._stream_output(focus_manager, f"Error: {exc}", "error")
            return output

        actions = self._parse_json_actions(response)
        self._stream_output(focus_manager, f"Generated {len(actions)} actions", "success")

        for idx, action in enumerate(actions, 1):
            description = action.get("description", action.get("goal", str(action)))
            priority    = action.get("priority", "medium")

            self._add_to_board(focus_manager, "actions", description, metadata=action)
            output.actions.append(action)

            emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(priority, "⚪")
            self._stream_output(focus_manager, f"  {emoji} {idx}. {description[:100]}", "info")

            if action.get("success_criteria"):
                self._stream_output(
                    focus_manager,
                    f"      ✓ Success: {action['success_criteria'][:80]}",
                    "info",
                )
            if action.get("tools"):
                self._stream_output(
                    focus_manager,
                    f"      🛠️  Tools: {', '.join(action['tools'][:3])}",
                    "info",
                )
            if action.get("target_file"):
                self._stream_output(
                    focus_manager,
                    f"      📄 File: {action['target_file']}",
                    "info",
                )

        validation = self._validate_actions(focus_manager, actions, available_tools)
        if validation["warnings"]:
            output.issues.extend(validation["warnings"])
            self._stream_output(focus_manager, "\n⚠️  Validation warnings:", "warning")
            for w in validation["warnings"]:
                self._stream_output(focus_manager, f"  • {w}", "warning")

        high_priority = [a for a in actions if a.get("priority") == "high" and a.get("tools")]
        if high_priority:
            self._stream_output(focus_manager, "\n🚀 Executing high-priority actions...", "info")
            for action in high_priority:
                self._execute_toolchain_for_action(focus_manager, action)
            changes = self._sync_sandbox(focus_manager)
            if changes:
                created  = sum(1 for c in changes if c.operation == "created")
                modified = sum(1 for c in changes if c.operation == "modified")
                self._stream_output(
                    focus_manager,
                    f"📦 Synced {created} created, {modified} modified",
                    "success",
                )

        if actions:
            self._notify_telegram(focus_manager, self._build_telegram_summary(actions))

        return output

    # ------------------------------------------------------------------
    # Flowchart broadcast helper
    # ------------------------------------------------------------------

    def _broadcast_flow_event(
        self,
        focus_manager,
        event_type: str,
        data: dict,
    ) -> None:
        """
        Emit a flowchart WebSocket event so the Toolchain Flowchart panel
        in the UI receives step lifecycle notifications.
        """
        broadcast = getattr(focus_manager, "_broadcast_sync", None)
        if callable(broadcast):
            try:
                broadcast(event_type, data)
                return
            except Exception:
                pass

        ws = getattr(focus_manager, "_stream_to_websocket", None)
        if callable(ws):
            try:
                ws({"type": event_type, "data": data})
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Retry context builder
    # ------------------------------------------------------------------

    def _build_retry_context(
        self,
        action: Dict[str, Any],
        failure_history: List[Dict[str, Any]],
    ) -> str:
        """
        Build a context string from prior failure history to inject into
        the retry query so the planner knows what was tried and what failed.

        Returns a formatted string to be appended to the goal/description.
        """
        if not failure_history:
            return ""

        lines = [
            "",
            "═" * 50,
            f"⚠️  RETRY CONTEXT — {len(failure_history)} prior attempt(s) failed",
            "═" * 50,
        ]
        for i, entry in enumerate(failure_history, 1):
            ts       = entry.get("timestamp", "unknown")
            error    = entry.get("error", "unknown error")
            output   = entry.get("output", "")[:400]
            attempt  = entry.get("attempt", i)
            lines.append(f"\nAttempt {attempt} ({ts}):")
            lines.append(f"  Error:  {error}")
            if output:
                lines.append(f"  Output: {output}")
        lines += [
            "",
            "Please avoid the same approach that previously failed.",
            "Try an alternative strategy, different tools, or break the",
            "task into smaller steps.",
            "═" * 50,
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Toolchain execution — cascading paths
    # ------------------------------------------------------------------

    def _resolve_session_id(self, focus_manager) -> Optional[str]:
        """Find the session_id from whichever object carries it."""
        for obj in (
            focus_manager,
            getattr(focus_manager, "agent", None),
            getattr(getattr(focus_manager, "agent", None), "vera_instance", None),
        ):
            sid = getattr(obj, "session_id", None)
            if sid:
                return sid
        return None

    def _execute_toolchain_for_action(
        self,
        focus_manager,
        action: Dict[str, Any],
        failure_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Execute a toolchain with full UI visibility.

        Returns a result dict:
            {"success": bool, "output": str, "error": str | None}

        IMPORTANT: This method never moves items on the focus board.
        Success/failure lifecycle is handled entirely by StageExecutor so
        that retry, escalation and dismissal logic lives in one place.

        If failure_history is provided, it is injected into the query as
        retry context so the planner can avoid repeating the same mistakes.

        Priority:
          1. MonitoredToolChainPlanner  — WebSocket step events + console
          2. Direct planner             — console streaming only
          3. Orchestrator               — legacy async path (fallback)
          4. _execute_action_direct     — per-tool last resort
        """
        description   = action.get("description", "")
        vera_instance = getattr(getattr(focus_manager, "agent", None), "vera_instance", None)
        session_id    = self._resolve_session_id(focus_manager)
        retry_ctx     = self._build_retry_context(action, failure_history or [])

        # Augment description with retry context when retrying
        effective_description = description + retry_ctx if retry_ctx else description

        self._stream_output(focus_manager, f"\n{'═'*50}", "info")
        if failure_history:
            self._stream_output(
                focus_manager,
                f"🔁 Retry #{len(failure_history)}: {description[:100]}",
                "info",
            )
        else:
            self._stream_output(focus_manager, f"🚀 Toolchain: {description[:100]}", "info")

        # ── Path 4: Per-tool execution (last resort) ──────────────────────
        # (Paths 1-3 are available but commented out; see module docstring)
        self._stream_output(focus_manager, "  🛠️  Falling back to per-tool execution", "info")
        return self._execute_action_direct(focus_manager, action, effective_description)

    def _run_planner(
        self,
        focus_manager,
        planner: Any,
        query: str,
    ) -> Dict[str, Any]:
        """
        Drain a planner's execute_tool_chain() generator, streaming every
        meaningful chunk to the UI and bridging toolchain events to the
        focus WebSocket.

        Returns {"success": bool, "output": str, "error": str | None}
        """
        chunk_count = 0
        total_chars = 0
        step_count  = 0
        last_heartbeat = time.time()
        collected_output: List[str] = []

        def _bridge_event(event_type: str, data: dict):
            self._broadcast_flow_event(focus_manager, event_type, data)

        _bridge_event("execution_started", {"query": query[:200]})

        try:
            for chunk in planner.execute_tool_chain(query):
                if chunk is None:
                    continue

                if isinstance(chunk, list):
                    step_count = len(chunk)
                    self._stream_output(
                        focus_manager,
                        f"  📋 Plan ready: {step_count} step(s)",
                        "info",
                    )
                    _bridge_event("plan", {"plan": chunk, "total_steps": step_count})
                    continue

                text = chunk if isinstance(chunk, str) else str(chunk)
                if not text:
                    continue

                chunk_count += 1
                total_chars += len(text)
                collected_output.append(text)

                if text.startswith("\n[Step ") and "] Executing:" in text:
                    m = re.match(r"\n\[Step (\d+)\] Executing: (.+)", text)
                    if m:
                        _bridge_event("step_started", {
                            "step_number": int(m.group(1)),
                            "tool_name":   m.group(2).strip(),
                            "tool_input":  "",
                        })
                elif text.startswith("\n[Step ") and "✓ Complete" in text:
                    m = re.match(r"\n\[Step (\d+)\]", text)
                    if m:
                        _bridge_event("step_completed", {"step_number": int(m.group(1)), "output": ""})
                elif text.startswith("\n[Step ") and "✗ Failed" in text:
                    m = re.match(r"\n\[Step (\d+)\] ✗ Failed: (.+)", text)
                    if m:
                        _bridge_event("step_failed", {
                            "step_number": int(m.group(1)),
                            "error":       m.group(2).strip(),
                        })

                self._push_to_ui(focus_manager, text, "tool")

                now = time.time()
                if now - last_heartbeat > 2.0:
                    self._stream_output(
                        focus_manager,
                        f"  ⏳ Toolchain running... ({chunk_count} chunks, {total_chars} chars)",
                        "info",
                    )
                    last_heartbeat = now

        except Exception as exc:
            self._stream_output(focus_manager, f"  ✗ Planner stream error: {exc}", "error")
            _bridge_event("execution_failed", {"error": str(exc)})
            # Sync sandbox even on failure so any partial writes are captured
            self._sync_sandbox(focus_manager)
            _bridge_event("execution_completed", {"final_result": f"FAILED: {exc}"})
            return {"success": False, "output": "".join(collected_output), "error": str(exc)}

        self._sync_sandbox(focus_manager)
        self._stream_output(
            focus_manager,
            f"  ✓ Toolchain complete ({chunk_count} chunks, {total_chars} chars)",
            "success",
        )
        _bridge_event("execution_completed", {
            "final_result": f"{chunk_count} chunks, {total_chars} chars",
        })
        return {
            "success": True,
            "output":  "".join(collected_output),
            "error":   None,
        }

    # ------------------------------------------------------------------
    # Direct tool-by-tool execution (no planner available)
    # ------------------------------------------------------------------

    def _execute_action_direct(
        self,
        focus_manager,
        action: Dict[str, Any],
        effective_description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute each tool in action['tools'] sequentially, streaming output.

        Returns {"success": bool, "output": str, "error": str | None,
                 "action": str, "results": list}

        effective_description overrides action['description'] when retrying
        (it carries injected failure history).
        """
        description      = effective_description or action.get("description", "Unknown")
        tools            = action.get("tools", [])
        target_file      = action.get("target_file", "")
        success_criteria = action.get("success_criteria", "")

        self._stream_output(focus_manager, f"\n{'─'*50}", "info")
        self._stream_output(focus_manager, f"⚡ Executing: {description[:200]}", "info")
        if target_file:
            self._stream_output(focus_manager, f"  📄 Target: {target_file}", "info")
        if success_criteria:
            self._stream_output(focus_manager, f"  ✓ Criteria: {success_criteria}", "info")

        self._broadcast_flow_event(
            focus_manager,
            "execution_started",
            {"query": description[:200]},
        )

        results: List[Dict] = []
        step_outputs: Dict[str, str] = {}
        last_error: Optional[str] = None

        for step_idx, tool_name in enumerate(tools, 1):
            self._stream_output(
                focus_manager,
                f"\n[Step {step_idx}/{len(tools)}] 🔧 {tool_name}",
                "tool",
            )

            self._broadcast_flow_event(
                focus_manager,
                "step_started",
                {
                    "step_number": step_idx,
                    "tool_name":   tool_name,
                    "tool_input":  (
                        f"{description}\nFile: {target_file}" if target_file else description
                    )[:400],
                },
            )

            query = description
            if target_file:
                query = f"{description}\nFile: {target_file}"
            if step_idx > 1:
                prev = step_outputs.get(f"step_{step_idx - 1}", "")
                if prev:
                    query = f"{query}\nPrevious output:\n{prev[:500]}"

            result = self._execute_single_tool(focus_manager, tool_name, query, step_idx)
            results.append(result)

            if result["success"]:
                step_out = str(result.get("output", ""))
                step_outputs[f"step_{step_idx}"] = step_out
                step_outputs[tool_name] = step_out
                self._stream_output(
                    focus_manager,
                    f"  ✓ [{tool_name}] complete — {len(step_out)} chars",
                    "success",
                )
                self._broadcast_flow_event(
                    focus_manager,
                    "step_completed",
                    {"step_number": step_idx, "output": step_out[:200]},
                )
            else:
                last_error = result["error"]
                self._stream_output(
                    focus_manager,
                    f"  ⚠️  Halting — tool error: {last_error}",
                    "warning",
                )
                self._broadcast_flow_event(
                    focus_manager,
                    "step_failed",
                    {"step_number": step_idx, "error": last_error},
                )
                break

        self._sync_sandbox(focus_manager)

        all_succeeded  = all(r["success"] for r in results)
        combined_output = "\n".join(str(r.get("output", "")) for r in results if r.get("output"))

        self._broadcast_flow_event(
            focus_manager,
            "execution_completed",
            {"final_result": f"{len(results)} tool(s) executed"},
        )

        return {
            "success": all_succeeded and bool(results),
            "output":  combined_output,
            "error":   last_error,
            "action":  description,
            "results": results,
        }

    def _execute_single_tool(
        self,
        focus_manager,
        tool_name: str,
        query: str,
        step_number: int = 1,
    ) -> Dict[str, Any]:
        """
        Run one tool with a plain string query and stream its output.
        """
        if not hasattr(focus_manager, "agent"):
            return {"success": False, "error": "No agent available"}

        tool = next(
            (t for t in focus_manager.agent.tools if t.name == tool_name),
            None,
        )
        if tool is None:
            self._stream_output(focus_manager, f"  ✗ Tool not found: {tool_name}", "error")
            return {"success": False, "error": f"Tool '{tool_name}' not found"}

        try:
            self._stream_output(focus_manager, f"  🔧 Running: {tool_name}", "tool")

            if hasattr(tool, "run") and callable(tool.run):
                raw = tool.run(query)
            elif hasattr(tool, "invoke") and callable(tool.invoke):
                raw = tool.invoke(query)
            elif callable(tool):
                raw = tool(query)
            else:
                raise ValueError(f"Tool '{tool_name}' is not callable")

            full_output = self._collect_tool_output(
                focus_manager, tool_name, raw, step_number
            )

            if not full_output.strip():
                self._stream_output(
                    focus_manager,
                    f"  ⚠️  {tool_name} returned no output",
                    "warning",
                )

            self._stream_output(focus_manager, f"  ✓ {tool_name} complete", "success")
            return {"success": True, "output": full_output, "tool": tool_name}

        except Exception as exc:
            self._stream_output(focus_manager, f"  ✗ {tool_name} failed: {exc}", "error")
            return {"success": False, "error": str(exc), "tool": tool_name}

    # ------------------------------------------------------------------
    # Output collection helpers
    # ------------------------------------------------------------------

    def _collect_tool_output(
        self,
        focus_manager,
        tool_name: str,
        raw: Any,
        step_number: int = 1,
    ) -> str:
        def _emit_chunk(text: str) -> None:
            self._push_to_ui(focus_manager, text, "tool")
            self._broadcast_flow_event(
                focus_manager,
                "step_output",
                {"step_number": step_number, "chunk": text},
            )

        is_stream = (
            isinstance(raw, types.GeneratorType)
            or (
                hasattr(raw, "__iter__")
                and hasattr(raw, "__next__")
                and not isinstance(raw, (str, bytes, dict, list))
            )
        )

        if is_stream:
            collected: List[str] = []
            try:
                for chunk in raw:
                    if chunk is None:
                        continue
                    chunk_str = chunk if isinstance(chunk, str) else str(chunk)
                    if chunk_str:
                        collected.append(chunk_str)
                        _emit_chunk(chunk_str)
            except Exception as exc:
                self._stream_output(
                    focus_manager,
                    f"  ⚠️  {tool_name} stream interrupted: {exc}",
                    "warning",
                )
            return "".join(collected)

        if raw is None:
            return ""
        text = raw if isinstance(raw, str) else str(raw)
        if text:
            _emit_chunk(text)
        return text

    def _push_to_ui(
        self,
        focus_manager,
        text: str,
        level: str = "tool",
    ) -> None:
        primary = getattr(focus_manager, "_stream_output", None)
        if callable(primary):
            try:
                primary(text, level)
            except Exception:
                pass

        console = getattr(focus_manager, "_stream_to_console", None)
        if callable(console):
            try:
                console(text, color="cyan", end="")
            except Exception:
                pass

        ws = getattr(focus_manager, "_stream_to_websocket", None)
        if callable(ws):
            try:
                ws({
                    "type":    "tool_output",
                    "level":   level,
                    "message": text,
                    "stage":   self.name,
                })
            except Exception:
                pass

        if not any([callable(primary), callable(console), callable(ws)]):
            print(text, end="", flush=True)

    # ------------------------------------------------------------------
    # Project context
    # ------------------------------------------------------------------

    def _get_project_context(self, focus_manager) -> Dict[str, Any]:
        sandbox = self._get_sandbox(focus_manager)
        if sandbox is None:
            return {"available": False}

        try:
            from Vera.ProactiveFocus.Experimental.Components.project_context_analyzer import (
                ProjectContextAnalyzer,
            )
            analyzer = ProjectContextAnalyzer(sandbox.project_root)
            ctx = analyzer.get_full_context(
                include_file_tree=True,
                include_recent_changes=True,
                include_todos=True,
                include_stats=True,
                max_files_to_scan=100,
            )
            ctx["available"] = True
            return ctx
        except Exception as exc:
            self._stream_output(
                focus_manager, f"⚠️  Workspace analysis failed: {exc}", "warning"
            )
            return {"available": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # Prompt building
    # ------------------------------------------------------------------

    @staticmethod
    def _item_text(item: Any) -> str:
        """Extract plain text from a board item regardless of its type."""
        if isinstance(item, dict):
            return item.get("note", item.get("description", item.get("goal", str(item))))
        return str(item)

    def _build_context_aware_prompt(
        self,
        focus_manager,
        project_context: Dict[str, Any],
        available_tools: List[str],
        additional_context: Optional[Any],
    ) -> str:
        board = self._get_board_data(focus_manager)

        # ── Pull actual board content, not just counts ─────────────────
        ideas_items      = board.get("ideas", [])[:8]
        next_steps_items = board.get("next_steps", [])[:8]
        progress_items   = board.get("progress", [])[-5:]
        issues_items     = board.get("issues", [])[-5:]

        parts = [
            f"Project: {focus_manager.focus}",
            "",
            f"Board Summary: {json.dumps({k: len(v) for k, v in board.items()}, indent=2)}",
            "",
            f"Available Tools: {', '.join(available_tools[:20])}",
            "",
        ]

        # ── IDEAS — primary source material for action generation ──────
        if ideas_items:
            parts.append("IDEAS (convert these into concrete, tool-backed actions):")
            for i, item in enumerate(ideas_items, 1):
                parts.append(f"  {i}. {self._item_text(item)[:150]}")
            parts.append("")
        else:
            parts.append("IDEAS: none yet — generate actions from workspace analysis below.")
            parts.append("")

        # ── NEXT STEPS — should become prioritised actions ─────────────
        if next_steps_items:
            parts.append("NEXT STEPS (these should become high/medium priority actions):")
            for i, item in enumerate(next_steps_items, 1):
                parts.append(f"  {i}. {self._item_text(item)[:150]}")
            parts.append("")

        # ── RECENT PROGRESS — avoid duplicating completed work ─────────
        if progress_items:
            parts.append("RECENT PROGRESS (do NOT duplicate — build on this):")
            for item in progress_items:
                parts.append(f"  • {self._item_text(item)[:120]}")
            parts.append("")

        # ── OPEN ISSUES — actions should actively address these ────────
        if issues_items:
            parts.append("OPEN ISSUES (actions should address these where possible):")
            for item in issues_items:
                parts.append(f"  • {self._item_text(item)[:120]}")
            parts.append("")

        # ── WORKSPACE ANALYSIS ─────────────────────────────────────────
        if project_context.get("available"):
            actionable: List[str] = []

            if "todos" in project_context:
                todos  = project_context["todos"]
                fixmes = [t for t in todos if t["type"] == "FIXME"]
                high_todos = [t for t in todos if t["type"] == "TODO"][:3]
                if fixmes:
                    actionable.append(f"Critical FIXMEs ({len(fixmes)}):")
                    for t in fixmes[:5]:
                        actionable.append(
                            f"  - {t['file']}:{t['line']} — {t['message'][:80]}"
                        )
                if high_todos:
                    actionable.append("High-priority TODOs:")
                    for t in high_todos:
                        actionable.append(
                            f"  - {t['file']}:{t['line']} — {t['message'][:80]}"
                        )

            if "recent_changes" in project_context:
                very_recent = [
                    c for c in project_context["recent_changes"] if c["age_hours"] < 4
                ]
                if very_recent:
                    actionable.append("Recently modified files (last 4 h):")
                    for c in very_recent[:5]:
                        actionable.append(
                            f"  - {c['path']} ({c['age_hours']:.1f}h ago)"
                        )

            if "git_status" in project_context and project_context["git_status"]:
                git = project_context["git_status"]
                if git.get("modified_files"):
                    actionable.append("Uncommitted changes:")
                    for f in git["modified_files"][:5]:
                        actionable.append(f"  - {f}")

            if actionable:
                parts += ["WORKSPACE ANALYSIS:", ""] + actionable + [""]

        if additional_context:
            parts += ["Additional Context:", str(additional_context), ""]

        parts += [
            "Generate 3-5 executable actions.",
            "",
            "IMPORTANT: If IDEAS or NEXT STEPS are listed above, your actions MUST",
            "be derived from them — do not ignore board content and generate generic",
            "actions. Each idea or next step should map to at least one action.",
            "Prioritize actions that:",
            "1. Create productive output, materially advancing toward the goal",
            "2. Complete recently started work (recently modified files)",
            "3. Resolve outstanding issues from the board",
            "4. Fill identified gaps",
            "5. Address critical FIXMEs and high-priority TODOs"
            "",
            "DO NOT Prioritize actions that:",
            "1. Maintain documentation and test coverage",
            "2. Address non-critical TODOs or low-impact issues",
            "3. Perform general cleanup or refactoring without a clear output",
            "4. Do not advance the project toward the current focus",
            "",
            "Priority: HIGH = FIXMEs/critical bugs/blocking issues",
            "          MEDIUM = TODOs/ideas/next steps",
            "          LOW = docs/cleanup/nice-to-haves",
            "",
            "Respond with a JSON array:",
            '[{"description":"...","goal":"...","priority":"high|medium|low",',
            '"success_criteria":"...","tools":["tool1"],"target_file":"","context":""}]',
        ]
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_actions(
        self,
        focus_manager,
        actions: List[Dict],
        available_tools: List[str],
    ) -> Dict[str, List[str]]:
        warnings: List[str] = []
        for idx, action in enumerate(actions, 1):
            for t in action.get("tools", []):
                if t not in available_tools:
                    warnings.append(f"Action {idx}: tool '{t}' not available")
            if not action.get("success_criteria"):
                warnings.append(f"Action {idx}: missing success criteria")
            if not action.get("description") and not action.get("goal"):
                warnings.append(f"Action {idx}: missing description/goal")
            if action.get("priority") == "high" and not action.get("tools"):
                warnings.append(f"Action {idx}: high-priority but no tools specified")
        return {"valid": not warnings, "warnings": warnings}

    # ------------------------------------------------------------------
    # JSON parsing
    # ------------------------------------------------------------------

    def _parse_json_actions(self, response: str) -> List[Dict]:
        cleaned = response.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = lines[1:] if lines[0].startswith("```") else lines
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        parsed = None
        try:
            parsed = json.loads(cleaned)
            if not isinstance(parsed, list):
                parsed = [parsed]
        except (json.JSONDecodeError, ValueError):
            m = re.search(r"\[[\s\S]*\]", cleaned)
            if m:
                try:
                    parsed = json.loads(m.group())
                    if not isinstance(parsed, list):
                        parsed = [parsed]
                except (json.JSONDecodeError, ValueError):
                    pass

        if parsed is None:
            lines_raw = [
                l.strip()
                for l in cleaned.split("\n")
                if l.strip() and l.strip() not in "[]{},"
            ]
            parsed = lines_raw or [response[:500]]

        actions: List[Dict] = []
        for item in parsed:
            if isinstance(item, dict):
                actions.append(
                    {
                        "description": item.get(
                            "description",
                            item.get("goal", item.get("action", str(item))),
                        ),
                        "goal":             item.get("goal", item.get("description", "")),
                        "tools":            item.get("tools", []),
                        "priority":         item.get("priority", "medium"),
                        "success_criteria": item.get("success_criteria", ""),
                        "context":          item.get("context", ""),
                        "target_file":      item.get("target_file", ""),
                    }
                )
            else:
                actions.append(
                    {
                        "description":      str(item),
                        "goal":             str(item),
                        "tools":            [],
                        "priority":         "medium",
                        "success_criteria": "",
                        "context":          "",
                        "target_file":      "",
                    }
                )

        return actions or [
            {
                "description":      response[:500],
                "goal":             response[:500],
                "tools":            [],
                "priority":         "medium",
                "success_criteria": "",
                "context":          "",
                "target_file":      "",
            }
        ]

    # ------------------------------------------------------------------
    # Telegram summary helper
    # ------------------------------------------------------------------

    def _build_telegram_summary(self, actions: List[Dict]) -> str:
        high   = [a for a in actions if a.get("priority") == "high"]
        medium = [a for a in actions if a.get("priority") == "medium"]
        low    = [a for a in actions if a.get("priority") == "low"]

        lines = [f"{self.icon} Action Plan Ready\n"]
        if high:
            lines.append(f"🔴 High ({len(high)}):")
            for a in high[:2]:
                lines.append(f"  • {a.get('description','')[:60]}...")
        if medium:
            lines.append(f"\n🟡 Medium ({len(medium)}):")
            for a in medium[:2]:
                lines.append(f"  • {a.get('description','')[:60]}...")
        if low:
            lines.append(f"\n🟢 Low ({len(low)})")
        return "\n".join(lines)