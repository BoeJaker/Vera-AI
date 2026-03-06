"""
StageExecutor — UNIFIED SANDBOX
================================
Executes individual workflow stages.

All tool execution, file I/O, and command execution is constrained to
``project_root`` through the unified ``ProjectSandbox``.  There is no
longer a separate ``SandboxRunner`` / ``SandboxEnforcer`` split — the
single ``ProjectSandbox`` handles both path enforcement and command
execution, and always writes results directly to ``project_root``.

Key changes vs previous version
---------------------------------
* ``_get_sandbox()`` returns a ``ProjectSandbox`` (not SandboxEnforcer).
* Sandbox is cached on ``focus_manager._sandbox`` — one instance per
  focus_manager, shared by all stages and the executor.
* Tool wrapping and bwrap execution share the same root so there is
  no workspace drift.
* ``_extract_artifacts_from_runtime_sandbox()`` is replaced by
  ``sandbox.sync_to_project()`` which is a no-op when nothing changed.

Orchestrator streaming fixes
-----------------------------
* ``_stream_from_orchestrator`` now uses a per-chunk inactivity timeout
  rather than a fixed total deadline.  The deadline resets every time a
  chunk arrives, so long-running tools (e.g. analyze_local_codebase) no
  longer time out mid-stream.
* The orchestrator streaming path now emits the same flowchart WebSocket
  events (execution_started, step_started, step_output, step_completed,
  step_failed, execution_completed) that _run_planner emits, so the
  Toolchain Flowchart panel is populated regardless of which path runs.

Info gap changes
----------------
* InfoGapStage is now imported and wired as ``execute_info_gaps_stage``.
* The stage runs before all content stages (enforced by IterationManager).

Retry / failure lifecycle  (NEW)
----------------------------------
The following constants control retry behaviour:
  ACTION_MAX_RETRIES   — how many times to retry before escalating (default 3)
  ACTION_ESCALATE_AT   — after this many failures, generate a help question (default 3)
  ACTION_DISMISS_AT    — after this many failures, auto-dismiss to issues (default 4)

Lifecycle states stored in action["metadata"]:
  retry_count      (int)   — number of failed attempts so far
  needs_retry      (bool)  — set after a failure; cleared when the retry runs
  retried_at       (str)   — ISO timestamp of the most recent retry dispatch
  failure_history  (list)  — [{attempt, error, output, timestamp}, ...]
  escalated        (bool)  — True once a help question has been generated
  dismissed        (bool)  — True once the action has been moved to issues

Rules:
  • Succeeded            → metadata["executed"] = True, moved to progress ✅
  • Failed, retry_count < ACTION_ESCALATE_AT
                         → metadata["needs_retry"] = True, stays in actions ⏳
                           (IterationManager schedules it in a later iteration)
  • Failed, retry_count == ACTION_ESCALATE_AT (and not yet escalated)
                         → question added to board asking for help 🆘
                           metadata["escalated"] = True, needs_retry = True
  • Failed, retry_count >= ACTION_DISMISS_AT
                         → moved to issues with full failure history ❌
                           metadata["dismissed"] = True

execute_retry_stage() is the dedicated method for retrying failed actions.
It is called by IterationManager with a cooldown to avoid tight retry loops.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Modular stage implementations
from Vera.ProactiveFocus.Experimental.Components.Stages.ideas       import IdeasStage
from Vera.ProactiveFocus.Experimental.Components.Stages.questions   import QuestionsStage
from Vera.ProactiveFocus.Experimental.Components.Stages.next_steps  import NextStepsStage
from Vera.ProactiveFocus.Experimental.Components.Stages.actions     import ActionsStage
from Vera.ProactiveFocus.Experimental.Components.Stages.artifacts   import ArtifactsStage
from Vera.ProactiveFocus.Experimental.Components.Stages.structure   import ProjectStructureStage
from Vera.ProactiveFocus.Experimental.Components.Stages.info_gaps   import InfoGapStage
# Unified sandbox
from Vera.Toolchain.sandbox import (
    ProjectSandbox,
    SandboxViolation,
    get_project_sandbox,
    sync_agent_sandbox,
)

_LEVEL_COLOURS: Dict[str, str] = {
    "info":    "blue",
    "success": "green",
    "warning": "yellow",
    "error":   "red",
    "tool":    "cyan",
}

_ORCHESTRATOR_CHUNK_TIMEOUT = 60.0   # seconds of silence before giving up

# ── Retry constants ────────────────────────────────────────────────────────
ACTION_MAX_RETRIES  = 3   # maximum times to retry before we stop trying
ACTION_ESCALATE_AT  = 3   # generate a help question after this many failures
ACTION_DISMISS_AT   = 4   # auto-dismiss to issues after this many failures


class StageExecutor:
    """
    Executes individual workflow stages with full graph integration.

    All manager state is accessed via ``self.fm``
    (the parent ``ProactiveFocusManager``).

    The unified ``ProjectSandbox`` is lazily initialised on first use and
    cached on ``focus_manager._sandbox``.
    """

    def __init__(self, focus_manager) -> None:
        self.fm = focus_manager

        self._info_gaps_stage         = InfoGapStage()
        self._ideas_stage             = IdeasStage()
        self._questions_stage         = QuestionsStage()
        self._next_steps_stage        = NextStepsStage()
        self._actions_stage           = ActionsStage()
        self._artifacts_stage         = ArtifactsStage()
        self._project_structure_stage = ProjectStructureStage()

        print("[StageExecutor] Initialised with modular stages + unified ProjectSandbox")

    def _stream_output(
        self,
        focus_manager,
        message: str,
        level:   str = "info",
        end:     str = "\n",
    ) -> None:
        colour  = _LEVEL_COLOURS.get(level, "white")
        primary = getattr(focus_manager, "_stream_output", None)
        if callable(primary):
            primary(message, level)
        console = getattr(focus_manager, "_stream_to_console", None)
        if callable(console):
            console(message, color=colour, end=end)
        ws = getattr(focus_manager, "_stream_to_websocket", None)
        if callable(ws):
            ws({"type": "stage_output", "level": level, "message": message})
        if not any([callable(primary), callable(console), callable(ws)]):
            print(f"[{level.upper()}] {message}", end=end)

    # ------------------------------------------------------------------
    # Flowchart broadcast helper
    # ------------------------------------------------------------------

    def _broadcast_flow_event(self, event_type: str, data: dict) -> None:
        broadcast = getattr(self.fm, "_broadcast_sync", None)
        if callable(broadcast):
            try:
                broadcast(event_type, data)
                return
            except Exception:
                pass
        ws = getattr(self.fm, "_stream_to_websocket", None)
        if callable(ws):
            try:
                ws({"type": event_type, "data": data})
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Sandbox access
    # ------------------------------------------------------------------

    def _get_sandbox(self) -> Optional[ProjectSandbox]:
        sandbox = get_project_sandbox(self.fm)
        if sandbox:
            if not getattr(self.fm, "_sandbox_tools_wrapped", False):
                self._wrap_agent_tools(sandbox)
                self.fm._sandbox_tools_wrapped = True
        return sandbox

    def _wrap_agent_tools(self, sandbox: ProjectSandbox) -> None:
        if not hasattr(self.fm, "agent") or not hasattr(self.fm.agent, "tools"):
            return
        self.fm.agent.tools = sandbox.wrap_tools(self.fm.agent.tools)
        self.fm._stream_output(
            f"🔒 {len(self.fm.agent.tools)} tools sandboxed to {sandbox.project_root}", "info"
        )

    def _sync_sandbox(self) -> List:
        return sync_agent_sandbox(self.fm)

    def invalidate_sandbox_cache(self) -> None:
        if hasattr(self.fm, "_sandbox"):
            sandbox: Optional[ProjectSandbox] = self.fm._sandbox
            if sandbox:
                sandbox.cleanup()
            del self.fm._sandbox
        self.fm._sandbox_tools_wrapped = False

    # ------------------------------------------------------------------
    # Modular stage delegation
    # ------------------------------------------------------------------

    def execute_info_gaps_stage(self, context=None):
        """
        Run information gap detection and resolution.
        Should be called before all content stages each iteration.
        """
        result = self._info_gaps_stage.execute(self.fm, context)
        return result

    def execute_ideas_stage(self, context=None):
        output = self._ideas_stage.execute(self.fm, context)
        self._sync_sandbox()
        return output.ideas

    def execute_next_steps_stage(self, context=None):
        output = self._next_steps_stage.execute(self.fm, context)
        self._sync_sandbox()
        return output.next_steps

    def execute_actions_stage(self, context=None):
        output = self._actions_stage.execute(self.fm, context)
        self._sync_sandbox()
        return output.actions

    def execute_questions_stage(self, context=None):
        result = self._questions_stage.execute(self.fm, context)
        self._sync_sandbox()
        return result

    def execute_artifacts_stage(self, context=None):
        result = self._artifacts_stage.execute(self.fm, context)
        self._sync_sandbox()
        return result

    def execute_project_structure_stage(self, context=None):
        result = self._project_structure_stage.execute(self.fm, context)
        self._sync_sandbox()
        return result

    # ------------------------------------------------------------------
    # Retry metadata helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_retry_count(action: Dict[str, Any]) -> int:
        """Return the number of previous failed attempts for this action."""
        meta = action.get("metadata", {}) if isinstance(action, dict) else {}
        return int(meta.get("retry_count", 0))

    @staticmethod
    def _get_failure_history(action: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Return the list of prior failure records."""
        meta = action.get("metadata", {}) if isinstance(action, dict) else {}
        return list(meta.get("failure_history", []))

    def _record_failure(
        self,
        action: Dict[str, Any],
        error:  str,
        output: str = "",
    ) -> None:
        """
        Append a failure entry to the action's metadata and increment
        retry_count.  Sets needs_retry=True so IterationManager picks it up.
        Does NOT move the action to any other board category.
        """
        if not isinstance(action, dict):
            return

        action.setdefault("metadata", {})
        meta = action["metadata"]

        retry_count  = int(meta.get("retry_count", 0)) + 1
        history      = list(meta.get("failure_history", []))

        history.append({
            "attempt":   retry_count,
            "error":     error,
            "output":    output[:1000],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        meta.update({
            "retry_count":     retry_count,
            "failure_history": history,
            "needs_retry":     retry_count < ACTION_DISMISS_AT,
            "last_error":      error,
            "last_failed_at":  datetime.now(timezone.utc).isoformat(),
            # Ensure previous success flags are cleared
            "executed":        False,
            "success":         False,
        })

        description = action.get("note", action.get("description", action.get("goal", "?")))
        self.fm._stream_output(
            f"  📋 Failure recorded (attempt {retry_count}/{ACTION_DISMISS_AT}): "
            f"{description[:80]}",
            "warning",
        )

    def _record_success(self, action: Dict[str, Any], output: str = "") -> None:
        """Mark an action as successfully executed."""
        if not isinstance(action, dict):
            return
        action.setdefault("metadata", {})
        action["metadata"].update({
            "executed":      True,
            "success":       True,
            "needs_retry":   False,
            "executed_at":   datetime.now(timezone.utc).isoformat(),
            "final_output":  output[:500],
        })

    def _should_escalate(self, action: Dict[str, Any]) -> bool:
        """True if this action has just hit the escalation threshold."""
        meta = action.get("metadata", {}) if isinstance(action, dict) else {}
        return (
            int(meta.get("retry_count", 0)) >= ACTION_ESCALATE_AT
            and not meta.get("escalated", False)
            and not meta.get("dismissed", False)
        )

    def _should_dismiss(self, action: Dict[str, Any]) -> bool:
        """True if this action has exhausted all retries and must be dismissed."""
        meta = action.get("metadata", {}) if isinstance(action, dict) else {}
        return (
            int(meta.get("retry_count", 0)) >= ACTION_DISMISS_AT
            and not meta.get("dismissed", False)
        )

    def _escalate_to_question(self, action: Dict[str, Any]) -> None:
        """
        Generate a board question asking the user for help with a
        persistently failing action.  Also marks the action as escalated
        so we don't repeat the question every iteration.
        """
        if not isinstance(action, dict):
            return

        description = action.get("note", action.get("description", action.get("goal", "?")))
        history     = self._get_failure_history(action)
        retry_count = self._get_retry_count(action)

        # Build a concise error summary
        errors = "; ".join(
            e.get("error", "unknown")[:80] for e in history[-2:]
        )

        question = (
            f"Action '{description[:80]}' has failed {retry_count} time(s) "
            f"and needs help. Latest errors: {errors}. "
            f"Should I try a different approach, skip this task, or do you "
            f"have additional context that might help?"
        )

        self.fm._stream_output(
            f"\n🆘 Escalating to questions board after {retry_count} failures: "
            f"{description[:80]}",
            "warning",
        )

        self.fm.add_to_focus_board(
            "questions",
            question,
            metadata={
                "type":             "action_escalation",
                "source_action":    description[:200],
                "retry_count":      retry_count,
                "failure_summary":  errors,
                "priority":         "high",
                "requires_user":    True,
                "created_at":       datetime.now(timezone.utc).isoformat(),
            },
        )

        action["metadata"]["escalated"]    = True
        action["metadata"]["escalated_at"] = datetime.now(timezone.utc).isoformat()

    def _dismiss_action(self, action: Dict[str, Any]) -> None:
        """
        Move a permanently-failed action from actions → issues with a
        comprehensive failure report.  Sets metadata["dismissed"] = True
        so it is not retried again.
        """
        if not isinstance(action, dict):
            return

        description = action.get("note", action.get("description", action.get("goal", "?")))
        history     = self._get_failure_history(action)
        retry_count = self._get_retry_count(action)

        failure_summary = json.dumps(
            [
                {
                    "attempt":   e.get("attempt"),
                    "error":     e.get("error", "")[:200],
                    "timestamp": e.get("timestamp", ""),
                }
                for e in history
            ],
            indent=2,
        )

        issue_note = (
            f"[Auto-dismissed] Action failed {retry_count} time(s) and was "
            f"removed from the queue: {description[:150]}"
        )

        self.fm._stream_output(
            f"\n❌ Dismissing action after {retry_count} failed attempts: {description[:80]}",
            "error",
        )

        self.fm.add_to_focus_board(
            "issues",
            issue_note,
            metadata={
                "type":            "dismissed_action",
                "original_action": description[:400],
                "retry_count":     retry_count,
                "failure_history": history,
                "failure_summary": failure_summary,
                "dismissed_at":    datetime.now(timezone.utc).isoformat(),
                "requires_review": True,
            },
        )

        action["metadata"]["dismissed"]    = True
        action["metadata"]["needs_retry"]  = False
        action["metadata"]["dismissed_at"] = datetime.now(timezone.utc).isoformat()

    # ------------------------------------------------------------------
    # Execution stage
    # ------------------------------------------------------------------

    def execute_execution_stage(
        self,
        max_executions: int = 2,
        priority_filter: str = "all",
    ) -> int:
        self.fm._set_stage(
            "Goal Execution",
            f"Executing up to {max_executions} {priority_filter}-priority goals",
            max_executions + 1,
        )
        self.fm._stream_output("Starting goal execution pipeline...", "info")

        sandbox = self._get_sandbox()
        if sandbox is None:
            self.fm._stream_output(
                "🚫 Execution blocked: no sandbox configured. "
                "Set project_root or working_directory before executing actions.",
                "error",
            )
            self.fm._clear_stage()
            return 0

        self.fm._stream_output(f"🔒 Sandbox: {sandbox.project_root}", "info")

        actions = self.fm.board.get_category("actions")
        if not actions:
            self.fm._stream_output("No actions to execute", "warning")
            self.fm._clear_stage()
            return 0

        # Filter to only fresh (non-retry, non-failed, non-dismissed) actions
        # so that retries are handled exclusively by execute_retry_stage().
        fresh_actions = [
            a for a in actions
            if isinstance(a, dict) and not self._action_is_retry_candidate(a)
            and not a.get("metadata", {}).get("dismissed")
            and not a.get("metadata", {}).get("executed")
        ]

        self.fm._stream_output(
            f"Found {len(actions)} actions ({len(fresh_actions)} fresh, "
            f"{len(actions) - len(fresh_actions)} pending retry/dismissed/done)",
            "info",
        )
        self.fm._update_progress()

        executed_count = 0
        skipped_count  = 0
        total_changes: List = []

        for idx, action in enumerate(fresh_actions):
            if executed_count >= max_executions:
                self.fm._stream_output(
                    f"Reached max executions ({max_executions}), "
                    f"{len(fresh_actions) - idx} remaining",
                    "success",
                )
                break

            goal_dict = self._parse_goal_item(action)
            priority  = goal_dict.get("priority", "medium")
            goal_text = goal_dict.get("goal", goal_dict.get("description", ""))

            if priority_filter != "all" and priority != priority_filter:
                skipped_count += 1
                continue

            emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(priority, "⚪")
            self.fm._stream_output(f"\n{'='*50}", "info")
            self.fm._stream_output(
                f"{emoji} Goal {executed_count+1}/{max_executions}: "
                f"{goal_text[:150]}{'...' if len(goal_text) > 150 else ''}",
                "info",
            )

            try:
                result  = self.handoff_to_toolchain(goal_dict)
                changes = self._sync_sandbox()
                total_changes.extend(changes)

                if changes:
                    created  = sum(1 for c in changes if c.operation == "created")
                    modified = sum(1 for c in changes if c.operation == "modified")
                    self.fm._stream_output(
                        f"📦 Synced: {created} created, {modified} modified", "info"
                    )

                if result:
                    # ── SUCCESS ───────────────────────────────────────
                    self._record_success(action, output=str(result)[:500])
                    self.fm.add_to_focus_board(
                        "progress",
                        f"✅ Completed: {goal_text[:150]}",
                        metadata={
                            "type":            "executed_action",
                            "original_action": goal_text[:400],
                            "executed_at":     datetime.now(timezone.utc).isoformat(),
                            "changes_synced":  len(changes),
                        },
                    )
                else:
                    # ── FAILURE (no result / empty result) ────────────
                    self._handle_action_failure(
                        action,
                        error="Toolchain returned no result",
                        output="",
                    )

                executed_count += 1
                self.fm._update_progress()

            except SandboxViolation as exc:
                self.fm._stream_output(f"🚫 Sandbox blocked: {exc}", "error")
                self._handle_action_failure(
                    action,
                    error=f"Sandbox violation: {exc}",
                    output="",
                )

            except Exception as exc:
                self.fm._stream_output(f"Execution failed: {exc}", "error")
                import traceback
                traceback.print_exc()
                self._handle_action_failure(action, error=str(exc), output="")

        if executed_count == 0 and fresh_actions:
            self.fm._stream_output("No actions executed — marking as needs_retry", "warning")
            for action in fresh_actions[:max_executions]:
                if isinstance(action, dict):
                    meta = action.get("metadata", {})
                    if not meta.get("executed") and not meta.get("dismissed"):
                        self._handle_action_failure(
                            action,
                            error="execution_stage_produced_no_result",
                            output="",
                        )

        self.fm._stream_output(f"\n{'='*50}", "info")
        self.fm._stream_output(
            f"Execution summary: {executed_count}/{max_executions} completed, "
            f"{skipped_count} skipped (filter: {priority_filter})",
            "success",
        )
        if total_changes:
            created  = sum(1 for c in total_changes if c.operation == "created")
            modified = sum(1 for c in total_changes if c.operation == "modified")
            self.fm._stream_output(
                f"📦 Total synced: {created} created, {modified} modified", "success"
            )

        self.fm._clear_stage()
        return executed_count

    # ------------------------------------------------------------------
    # Retry stage  (NEW)
    # ------------------------------------------------------------------

    def execute_retry_stage(self, max_retries_this_run: int = 1) -> int:
        """
        Attempt to re-execute actions that previously failed.

        Deliberately limited to max_retries_this_run per call so that a
        single persistent failure can't monopolise a whole iteration.

        Each retried action receives its full failure_history as context
        so the toolchain can avoid repeating the same mistakes.

        Returns the number of actions that succeeded on retry.
        """
        self.fm._set_stage(
            "Retry Execution",
            f"Retrying up to {max_retries_this_run} previously-failed action(s)",
            max_retries_this_run + 1,
        )

        sandbox = self._get_sandbox()
        if sandbox is None:
            self.fm._stream_output(
                "🚫 Retry blocked: no sandbox configured.", "error"
            )
            self.fm._clear_stage()
            return 0

        actions    = self.fm.board.get_category("actions")
        candidates = [
            a for a in actions
            if isinstance(a, dict) and self._action_is_retry_candidate(a)
        ]

        if not candidates:
            self.fm._stream_output("No actions pending retry.", "info")
            self.fm._clear_stage()
            return 0

        self.fm._stream_output(
            f"🔁 {len(candidates)} action(s) pending retry (running {max_retries_this_run})",
            "info",
        )

        succeeded = 0

        for action in candidates[:max_retries_this_run]:
            if self._should_dismiss(action):
                self._dismiss_action(action)
                continue

            goal_dict       = self._parse_goal_item(action)
            goal_text       = goal_dict.get("goal", goal_dict.get("description", ""))
            failure_history = self._get_failure_history(action)
            retry_count     = self._get_retry_count(action)

            self.fm._stream_output(
                f"\n🔁 Retry attempt {retry_count + 1}/{ACTION_MAX_RETRIES}: "
                f"{goal_text[:100]}",
                "info",
            )

            # Mark that a retry is in progress (prevents duplicate scheduling)
            action["metadata"]["needs_retry"]  = False
            action["metadata"]["retried_at"]   = datetime.now(timezone.utc).isoformat()

            try:
                result = self.handoff_to_toolchain(
                    goal_dict,
                    failure_history=failure_history,
                )
                changes = self._sync_sandbox()

                if result:
                    # ── RETRY SUCCEEDED ───────────────────────────────
                    self._record_success(action, output=str(result)[:500])
                    self.fm._stream_output(
                        f"  ✅ Retry succeeded: {goal_text[:80]}", "success"
                    )
                    self.fm.add_to_focus_board(
                        "progress",
                        f"✅ Completed (after {retry_count + 1} attempt(s)): {goal_text[:150]}",
                        metadata={
                            "type":            "retried_action",
                            "original_action": goal_text[:400],
                            "retry_count":     retry_count + 1,
                            "executed_at":     datetime.now(timezone.utc).isoformat(),
                            "changes_synced":  len(changes),
                        },
                    )
                    succeeded += 1
                else:
                    self._handle_action_failure(
                        action,
                        error="Retry toolchain returned no result",
                        output="",
                    )

            except SandboxViolation as exc:
                self._handle_action_failure(
                    action, error=f"Sandbox violation: {exc}", output=""
                )
            except Exception as exc:
                import traceback
                traceback.print_exc()
                self._handle_action_failure(action, error=str(exc), output="")

        self.fm._stream_output(
            f"\n🔁 Retry stage complete: {succeeded}/{min(len(candidates), max_retries_this_run)} "
            f"succeeded",
            "success" if succeeded else "warning",
        )
        self.fm._clear_stage()
        return succeeded

    # ------------------------------------------------------------------
    # Shared failure handler
    # ------------------------------------------------------------------

    def _handle_action_failure(
        self,
        action: Dict[str, Any],
        error:  str,
        output: str = "",
    ) -> None:
        """
        Central failure handler called by both execute_execution_stage and
        execute_retry_stage.  Applies the retry/escalate/dismiss ladder.

        Never adds the action to the `progress` category.
        Never removes it from the `actions` category (IterationManager's job).
        """
        self._record_failure(action, error=error, output=output)

        description = action.get("note", action.get("description", action.get("goal", "?")))

        if self._should_dismiss(action):
            self._dismiss_action(action)
        elif self._should_escalate(action):
            self._escalate_to_question(action)
        else:
            retry_count = self._get_retry_count(action)
            remaining   = ACTION_DISMISS_AT - retry_count
            self.fm._stream_output(
                f"  ⏳ Will retry later ({remaining} attempt(s) remaining): "
                f"{description[:80]}",
                "warning",
            )

    # ------------------------------------------------------------------
    # Retry candidate detection
    # ------------------------------------------------------------------

    @staticmethod
    def _action_is_retry_candidate(action: Dict[str, Any]) -> bool:
        """
        Return True if this action needs a retry pass.
        Excluded from the normal execution queue; picked up by execute_retry_stage.
        """
        meta = action.get("metadata", {}) if isinstance(action, dict) else {}
        return (
            bool(meta.get("needs_retry"))
            and not meta.get("dismissed")
            and not meta.get("executed")
        )

    @staticmethod
    def _count_retry_candidates(actions: List[Any]) -> int:
        return sum(
            1 for a in actions
            if isinstance(a, dict) and StageExecutor._action_is_retry_candidate(a)
        )

    # ------------------------------------------------------------------
    # Review stage
    # ------------------------------------------------------------------

    def execute_review_stage(self, context=None) -> str:
        self.fm._set_stage("Review", "Analysing project state", 2)

        prompt = f"""
Project: {self.fm.focus}

Complete Board State:
{json.dumps(self.fm.board.get_all(), indent=2)}

Statistics:
{json.dumps(self.fm.board.get_stats(), indent=2)}

{f"Additional Context: {context}" if context else ""}

Provide a comprehensive review:
1. Overall progress assessment
2. Key achievements
3. Outstanding challenges
4. Recommended focus areas
5. Next priorities
"""
        self.fm._update_progress()
        response = ""
        try:
            for chunk in self.fm._stream_llm_with_thought_broadcast(self.fm.agent.deep_llm, prompt):
                response += chunk
            self.fm._update_progress()
            self.fm._stream_output("Review complete", "success")
        except Exception as exc:
            response = f"Error: {exc}"

        if response and not response.startswith("Error:"):
            summary = response[:300] + "..." if len(response) > 300 else response
            self.fm.add_to_focus_board("progress", f"[Review] {summary}", metadata={
                "type":               "review",
                "full_review_length": len(response),
                "timestamp":          datetime.now(timezone.utc).isoformat(),
            })
            self._save_review_to_file(response)

        self.fm._clear_stage()
        return response

    # ------------------------------------------------------------------
    # Toolchain handoff
    # ------------------------------------------------------------------

    def handoff_to_toolchain(
        self,
        action: Dict[str, Any],
        failure_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[str]:
        """
        Hand an action off to the toolchain for execution.

        failure_history, when provided, is injected into the query so the
        planner knows what was already tried.
        """
        import traceback

        goal             = action.get("goal", action.get("description", str(action)))
        priority         = action.get("priority", "medium")
        success_criteria = action.get("success_criteria", "")
        goal_context     = action.get("context", "")

        self.fm._stream_output("▶️ Starting goal execution", "info")
        self.fm._stream_output(f"📋 Goal: {goal}", "info")

        priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(priority, "⚪")
        self.fm._stream_output(f"   Priority: {priority_emoji} {priority}", "info")

        if success_criteria:
            self.fm._stream_output(f"   Success criteria: {success_criteria}", "info")

        if failure_history:
            self.fm._stream_output(
                f"   🔁 Retry context: {len(failure_history)} prior failure(s)", "info"
            )

        query = self._build_toolchain_query(
            goal, priority, success_criteria, goal_context, failure_history
        )

        hybrid_memory = getattr(self.fm, "hybrid_memory", None)
        if hybrid_memory and hasattr(hybrid_memory, "create_tool_execution_node"):
            try:
                hybrid_memory.create_tool_execution_node(
                    node_id=f"exec_{int(time.time())}",
                    tool_name="toolchain_orchestrated",
                    metadata={
                        "executed_at": datetime.now(timezone.utc).isoformat(),
                        "goal":        goal[:500],
                        "priority":    priority,
                        "is_retry":    bool(failure_history),
                    },
                )
            except Exception:
                pass

        result      = ""
        chunk_count = 0
        start_time  = time.time()

        self.fm._stream_output("─" * 50, "info")

        try:
            chunk_generator     = self._execute_goal_via_orchestrator(query)
            is_orchestrator_gen = chunk_generator is not None

            if chunk_generator is None:
                self.fm._stream_output("⚠️ Falling back to direct toolchain execution", "warning")
                chunk_generator     = self._execute_goal_direct(query)
                is_orchestrator_gen = False

            if chunk_generator is None:
                self.fm._stream_output("❌ No execution method available", "error")
                return None

            line_buffer = ""

            for chunk in chunk_generator:
                chunk_str    = str(chunk) if not isinstance(chunk, str) else chunk
                result      += chunk_str
                chunk_count += 1

                if is_orchestrator_gen:
                    continue

                line_buffer += chunk_str
                while "\n" in line_buffer:
                    line, line_buffer = line_buffer.split("\n", 1)
                    if line.strip():
                        self.fm._stream_output(f"  {line}", "info")

                if chunk_count % 20 == 0 and line_buffer.strip():
                    self.fm._stream_output(f"  {line_buffer}", "info")
                    line_buffer = ""

            if not is_orchestrator_gen and line_buffer.strip():
                self.fm._stream_output(f"  {line_buffer}", "info")

        except TimeoutError as e:
            self.fm._stream_output(f"⏱️ Toolchain execution timed out: {e}", "error")
        except Exception as e:
            self.fm._stream_output(f"❌ Toolchain execution error: {e}", "error")
            traceback.print_exc()

        elapsed = time.time() - start_time
        self.fm._stream_output("─" * 50, "info")
        self.fm._stream_output(
            f"✅ Execution complete: {chunk_count} chunks, {len(result)} chars, {elapsed:.1f}s",
            "success",
        )

        self.fm._update_progress()
        return result if result.strip() else None

    # ------------------------------------------------------------------
    # Orchestrator dispatch
    # ------------------------------------------------------------------

    def _execute_goal_via_orchestrator(self, query: str):
        import traceback
        import queue
        import threading

        orchestrator = getattr(self.fm.agent, "orchestrator", None)

        if not orchestrator or not getattr(orchestrator, "running", False):
            self.fm._stream_output("⚠️ Orchestrator not available or not running", "warning")
            return None

        vera_instance = self.fm.agent

        try:
            task_id = orchestrator.submit_task(
                "toolchain.execute",
                vera_instance=vera_instance,
                query=query,
                expert=False,
            )

            self.fm._stream_output(f"📋 Orchestrator task submitted: {task_id[:12]}…", "info")
            self._broadcast_flow_event("flowchart_clear", {})
            self._broadcast_flow_event("execution_started", {"query": query[:200]})

            executor = self

            def _stream_from_orchestrator():
                chunk_count  = 0
                total_chars  = 0
                last_chunk_t = time.time()
                q: queue.Queue = queue.Queue()
                _SENTINEL      = object()

                def _producer():
                    try:
                        for chunk in orchestrator.stream_result(task_id, timeout=3600.0):
                            q.put(chunk)
                    except Exception as exc:
                        q.put(exc)
                    finally:
                        q.put(_SENTINEL)

                t = threading.Thread(target=_producer, daemon=True)
                t.start()

                while True:
                    try:
                        item = q.get(timeout=_ORCHESTRATOR_CHUNK_TIMEOUT)
                    except queue.Empty:
                        executor.fm._stream_output(
                            f"⏱️ Orchestrator stream: no chunk for "
                            f"{_ORCHESTRATOR_CHUNK_TIMEOUT:.0f}s — giving up ({chunk_count} chunks)",
                            "warning",
                        )
                        executor._broadcast_flow_event(
                            "execution_failed",
                            {"error": f"Inactivity timeout after {_ORCHESTRATOR_CHUNK_TIMEOUT:.0f}s"},
                        )
                        return

                    if item is _SENTINEL:
                        break

                    if isinstance(item, Exception):
                        executor.fm._stream_output(f"❌ Orchestrator stream error: {item}", "error")
                        executor._broadcast_flow_event("execution_failed", {"error": str(item)})
                        return

                    last_chunk_t = time.time()
                    chunk_str    = item if isinstance(item, str) else str(item)
                    chunk_count += 1
                    total_chars += len(chunk_str)

                    if "\n[Step " in chunk_str or chunk_str.startswith("[Step "):
                        for line in chunk_str.splitlines():
                            line = line.strip()
                            m = re.match(r"\[Step (\d+)\] Executing: (.+)", line)
                            if m:
                                executor._broadcast_flow_event("step_started", {
                                    "step_number": int(m.group(1)),
                                    "tool_name":   m.group(2).strip(),
                                    "tool_input":  "",
                                })
                                continue
                            m = re.match(r"\[Step (\d+)\].*✓", line)
                            if m:
                                executor._broadcast_flow_event("step_completed", {
                                    "step_number": int(m.group(1)), "output": "",
                                })
                                continue
                            m = re.match(r"\[Step (\d+)\].*✗ Failed: (.+)", line)
                            if m:
                                executor._broadcast_flow_event("step_failed", {
                                    "step_number": int(m.group(1)),
                                    "error":       m.group(2).strip(),
                                })
                                continue
                            if line:
                                executor._broadcast_flow_event("step_output", {
                                    "step_number": 0, "chunk": line,
                                })
                    else:
                        if chunk_str.strip():
                            executor._broadcast_flow_event("step_output", {
                                "step_number": 0, "chunk": chunk_str,
                            })

                    yield chunk_str

                executor.fm._stream_output(
                    f"✅ Orchestrator stream complete ({chunk_count} chunks, {total_chars} chars)",
                    "info",
                )
                executor._broadcast_flow_event("execution_completed", {
                    "final_result": f"{chunk_count} chunks, {total_chars} chars",
                })

            return _stream_from_orchestrator()

        except Exception as e:
            self.fm._stream_output(f"⚠️ Orchestrator submit failed: {e}", "warning")
            traceback.print_exc()
            return None

    def _execute_goal_direct(self, query: str):
        import traceback

        toolchain = getattr(self.fm.agent, "toolchain", None)
        if not toolchain:
            self.fm._stream_output("❌ No toolchain available", "error")
            return None

        executor = self

        def _stream_from_toolchain():
            chunk_count = 0
            try:
                for chunk in toolchain.execute_tool_chain(query):
                    chunk_str    = str(chunk) if not isinstance(chunk, str) else chunk
                    chunk_count += 1
                    yield chunk_str
            except Exception as e:
                executor.fm._stream_output(f"❌ Direct toolchain error: {e}", "error")
                traceback.print_exc()
            executor.fm._stream_output(
                f"✅ Direct toolchain complete ({chunk_count} chunks)", "info"
            )

        return _stream_from_toolchain()

    # ------------------------------------------------------------------
    # Query building
    # ------------------------------------------------------------------

    def _build_toolchain_query(
        self,
        goal:             str,
        priority:         str,
        success_criteria: str,
        goal_context:     str,
        failure_history:  Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        recent_progress = self.fm.board.get_category("progress")[-3:]
        recent_issues   = self.fm.board.get_category("issues")[-3:]

        progress_notes = [
            p.get("note", "") if isinstance(p, dict) else str(p)
            for p in recent_progress
        ]
        issue_notes = [
            i.get("note", "") if isinstance(i, dict) else str(i)
            for i in recent_issues
        ]

        sandbox      = self._get_sandbox()
        sandbox_note = (
            f"\nSANDBOX: All file paths must be relative to {sandbox.project_root}\n"
            if sandbox else ""
        )

        # ── Inject retry context ──────────────────────────────────────
        retry_block = ""
        if failure_history:
            retry_lines = [
                "",
                "═" * 50,
                f"⚠️  RETRY — {len(failure_history)} prior attempt(s) failed for this goal",
                "Please use a DIFFERENT approach than what was tried before.",
                "═" * 50,
            ]
            for entry in failure_history:
                attempt   = entry.get("attempt", "?")
                error     = entry.get("error", "unknown")[:200]
                output    = entry.get("output", "")[:300]
                ts        = entry.get("timestamp", "")
                retry_lines.append(f"\nAttempt {attempt} ({ts}):")
                retry_lines.append(f"  Error:  {error}")
                if output:
                    retry_lines.append(f"  Output: {output}")
            retry_lines += [
                "",
                "Strategies to try:",
                "  • Break the goal into smaller, more targeted steps",
                "  • Use different tools than previously attempted",
                "  • Add intermediate verification steps",
                "  • Try a read-first approach before writing",
                "═" * 50,
                "",
            ]
            retry_block = "\n".join(retry_lines)

        return (
            f"Project: {self.fm.focus}\n\n"
            f"GOAL: {goal}\n\n"
            f"Priority: {priority}\n"
            f"{f'Success Criteria: {success_criteria}' if success_criteria else ''}\n"
            f"{f'Context: {goal_context}' if goal_context else ''}\n"
            f"{sandbox_note}"
            f"{retry_block}"
            f"Recent Progress:\n{json.dumps(progress_notes, indent=2)}\n\n"
            f"Known Issues:\n{json.dumps(issue_notes, indent=2)}\n\n"
            "Decompose this goal into concrete tool steps. "
            "ALL file paths must be relative to the project root.\n"
        )

    # ------------------------------------------------------------------
    # Success evaluation
    # ------------------------------------------------------------------

    def _evaluate_success(
        self,
        goal:             str,
        success_criteria: str,
        result:           str,
        stage_id:         str,
    ) -> None:
        try:
            prompt = (
                f"Goal: {goal[:300]}\n"
                f"Success Criteria: {success_criteria[:200]}\n"
                f"Result (truncated): {result[:1000]}\n\n"
                "Did the result meet the success criteria?\n"
                "Respond: YES / PARTIAL / NO — then one sentence explanation.\n"
            )
            evaluation = ""
            for chunk in self.fm._stream_llm_with_thought_broadcast(self.fm.agent.fast_llm, prompt):
                evaluation += chunk
            evaluation = evaluation.strip()

            upper = evaluation.upper()
            if upper.startswith("YES"):
                self.fm._stream_output(f"Success criteria MET: {evaluation[:100]}", "success")
                status = "met"
            elif upper.startswith("PARTIAL"):
                self.fm._stream_output(f"Criteria PARTIALLY met: {evaluation[:100]}", "warning")
                status = "partial"
            else:
                self.fm._stream_output(f"Criteria NOT met: {evaluation[:100]}", "warning")
                self.fm.add_to_focus_board(
                    "issues", f"Goal incomplete: {goal[:100]} - {evaluation[:200]}"
                )
                status = "not_met"

            if self.fm.hybrid_memory and stage_id:
                eval_id = f"eval_{stage_id}_{int(time.time())}"
                self.fm.hybrid_memory.upsert_entity(
                    entity_id=eval_id,
                    etype="evaluation",
                    labels=["Evaluation", "SuccessCheck"],
                    properties={
                        "goal":             goal[:500],
                        "success_criteria": success_criteria,
                        "evaluation":       evaluation[:500],
                        "status":           status,
                        "stage_id":         stage_id,
                        "project_id":       self.fm.project_id,
                        "created_at":       datetime.now(timezone.utc).isoformat(),
                    },
                )
                self.fm.hybrid_memory.link(stage_id, eval_id, "EVALUATED_BY", {})
        except Exception as exc:
            self.fm._stream_output(f"Could not evaluate success: {exc}", "warning")

    # ------------------------------------------------------------------
    # Goal item parser
    # ------------------------------------------------------------------

    def _parse_goal_item(self, item: Any) -> Dict[str, Any]:
        _empty = {"goal": "", "priority": "medium", "success_criteria": "", "context": ""}

        def _from_dict(d: Dict) -> Dict:
            text = d.get("goal") or d.get("description") or d.get("note") or str(d)
            meta = d.get("metadata", {})
            if isinstance(meta, dict):
                text = meta.get("goal") or meta.get("description") or text
            return {
                "goal":             text,
                "priority":         d.get("priority", meta.get("priority", "medium") if isinstance(meta, dict) else "medium"),
                "success_criteria": d.get("success_criteria", meta.get("success_criteria", "") if isinstance(meta, dict) else ""),
                "context":          d.get("context", ""),
            }

        if isinstance(item, dict):
            return _from_dict(item)

        if isinstance(item, str):
            try:
                parsed = json.loads(item.strip().strip("```json").strip("```").strip())
                if isinstance(parsed, dict):
                    return _from_dict(parsed)
            except (json.JSONDecodeError, ValueError):
                pass
            return {**_empty, "goal": item}

        return {**_empty, "goal": str(item)}

    # ------------------------------------------------------------------
    # Review file saver
    # ------------------------------------------------------------------

    def _save_review_to_file(self, review_text: str) -> None:
        sandbox = self._get_sandbox()
        if sandbox is None:
            return

        timestamp  = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        rel_path   = f"reviews/review_{timestamp}.md"
        project_id = self.fm.project_id or "unknown_project"

        content = (
            f"# Project Review — {self.fm.focus or 'Unknown'}\n"
            f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}  \n"
            f"**Project ID:** {project_id}  \n\n---\n\n"
            f"{review_text}\n\n---\n\n"
            f"## Board Snapshot\n\n"
            f"**Statistics:** {json.dumps(self.fm.board.get_stats(), indent=2)}\n"
        )

        try:
            from pathlib import Path
            target = sandbox.project_root / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            self.fm._stream_output(f"Review saved: {rel_path}", "info")
        except Exception as exc:
            print(f"[StageExecutor] Failed to save review: {exc}")