# iteration_manager.py — INFO GAP AWARE + RETRY AWARE
"""Manages iteration workflow and intelligent stage selection.

UPDATED:
- info_gaps is now a first-class stage that runs BEFORE structure and other
  content stages. It detects missing information and signals which downstream
  stages should handle each gap (questions / actions / next_steps / ideas).
- Stage selection now reads gap dispatch signals to boost the right stages.
- questions stage frequency increased: runs whenever gaps need user input,
  not just on a fixed modulo cadence.
- Removed fixed modulo-6 questions trigger in favour of gap-driven triggering.

RETRY SYSTEM:
- execute_retry_stage is scheduled separately from execute_execution_stage
  so that persistently-failing actions never block fresh work.
- Retry cooldown: a retry pass only runs every RETRY_ITERATION_INTERVAL
  iterations, preventing tight retry loops.
- Retry pass is also suppressed if more than RETRY_MAX_PER_ITERATION
  retryable actions exist (safety valve) — the extras queue for later.
- _analyze_board_state now reports retry_candidate_count and
  escalated_count so _select_stages can make informed decisions.
- Escalated actions (those that generated a help question) still sit in
  the actions category with escalated=True; they do NOT get retried until
  the user responds and the escalation is cleared externally.
"""

import time
from typing import Optional, Dict, Any, List
from datetime import datetime


# ── Retry scheduling constants ─────────────────────────────────────────────
RETRY_ITERATION_INTERVAL = 3   # run a retry pass at most once every N iterations
RETRY_MAX_PER_ITERATION  = 1   # max actions to retry per retry pass
                                # (keeps each iteration snappy; failures queue up)


class IterationManager:
    """
    Intelligently manages workflow iterations and stage selection.

    Stage pipeline order (when all are selected):
      info_gaps → review → project_structure → ideas → next_steps →
      actions → execution → retry → questions → artifacts
    """

    def __init__(self, focus_manager):
        self.fm = focus_manager
        self._last_action_iteration      = 0
        self._consecutive_action_stages  = 0
        self._structure_initialized      = False
        self._last_retry_iteration       = 0   # tracks when we last ran a retry pass

    def run(
        self,
        max_iterations:     Optional[int] = None,
        iteration_interval: int           = 300,
        auto_execute:       bool          = True,
    ):
        """Run intelligent iterative workflow."""
        iteration = 0

        while (max_iterations is None or iteration < max_iterations) and self.fm.workflow_active:
            iteration += 1

            self.fm._stream_output("\n" + "=" * 60, "info")
            self.fm._stream_output(f"🔄 ITERATION {iteration}", "info")
            self.fm._stream_output("=" * 60 + "\n", "info")

            try:
                iteration_id = self.fm._create_iteration_node()

                analysis = self._analyze_board_state()
                self.fm._stream_output("📊 Board Analysis:", "info")
                self.fm._stream_output(f"   {analysis['summary']}", "info")

                context = self.fm.context_enricher.build_iteration_context(iteration, analysis)

                stages = self._select_stages(analysis, iteration)
                self.fm._stream_output(f"\n🎯 Selected Stages: {', '.join(stages)}", "info")

                stage_results = {}
                for stage in stages:
                    result = self._execute_stage(stage, context)
                    stage_results[stage] = result
                    time.sleep(2)

                self._process_completed_actions()

                if iteration % 2 == 0:
                    self._cleanup_stale_actions()

                if hasattr(self.fm, "agent") and hasattr(self.fm.agent, "runtime_sandbox"):
                    stats = self.fm.agent.runtime_sandbox.get_stats()
                    if stats.get("artifacts_created", 0) > 0:
                        self.fm._stream_output(
                            f"📦 Artifacts: {stats['artifacts_created']} created, "
                            f"{stats['artifacts_modified']} modified",
                            "info",
                        )

                self.fm.doc_generator.generate_iteration_summary(
                    iteration=iteration,
                    analysis=analysis,
                    stages=stages,
                    results=stage_results,
                )

                checkpoint = self.fm.save_focus_board()
                self.fm._stream_output(f"\n💾 Checkpoint: {checkpoint}", "success")

                self.fm._complete_iteration_node(summary=analysis["summary"])

                if max_iterations is None or iteration < max_iterations:
                    self.fm._stream_output(f"\n⏳ Waiting {iteration_interval}s…", "info")
                    time.sleep(iteration_interval)

            except Exception as e:
                self.fm._stream_output(f"\n❌ Error: {str(e)}", "error")
                import traceback
                traceback.print_exc()
                time.sleep(30)

        self.fm._stream_output(f"\n✅ Workflow completed: {iteration} iterations", "success")

    # ==================================================================
    # BOARD ANALYSIS
    # ==================================================================

    def _analyze_board_state(self) -> Dict[str, Any]:
        """Analyse current board state to inform stage selection."""
        from Vera.ProactiveFocus.Experimental.Components.Stages.info_gaps import InfoGapStage
        from Vera.ProactiveFocus.Experimental.Components.stage_executor import StageExecutor

        stats            = self.fm.board.get_stats()
        executable_count = self._count_executable_actions()
        stale_count      = stats.get("actions", 0) - executable_count

        progress_items  = self.fm.board.get_category("progress")
        recent_artifacts = sum(
            1 for item in progress_items[-10:]
            if isinstance(item, dict) and item.get("metadata", {}).get("type") == "artifact"
        )

        # ── Gap awareness ──────────────────────────────────────────────
        open_gap_count   = InfoGapStage.get_open_gap_count(self.fm)
        high_gap_count   = sum(
            1 for item in self.fm.board.get_category("questions")
            if isinstance(item, dict)
            and item.get("metadata", {}).get("type") == "info_gap"
            and item.get("metadata", {}).get("status") == "open"
            and item.get("metadata", {}).get("priority") == "high"
        )
        gap_dispatch     = InfoGapStage.get_gaps_by_dispatch(self.fm)

        # ── Retry awareness ────────────────────────────────────────────
        all_actions         = self.fm.board.get_category("actions")
        retry_candidates    = StageExecutor._count_retry_candidates(all_actions)
        escalated_count     = sum(
            1 for a in all_actions
            if isinstance(a, dict)
            and a.get("metadata", {}).get("escalated")
            and not a.get("metadata", {}).get("dismissed")
        )
        dismissed_count     = sum(
            1 for a in all_actions
            if isinstance(a, dict) and a.get("metadata", {}).get("dismissed")
        )

        analysis = {
            "stats":               stats,
            "total_items":         sum(stats.values()),
            "has_actions":         stats.get("actions", 0) > 0,
            "has_executable_actions": executable_count > 0,
            "has_ideas":           stats.get("ideas", 0) > 0,
            "has_next_steps":      stats.get("next_steps", 0) > 0,
            "has_issues":          stats.get("issues", 0) > 0,
            "recent_progress":     len(progress_items[-5:]),
            "recent_artifacts":    recent_artifacts,
            "executable_count":    executable_count,
            "stale_count":         stale_count,
            "ideas_count":         stats.get("ideas", 0),
            "next_steps_count":    stats.get("next_steps", 0),
            "actionable_count":    stats.get("actions", 0) + stats.get("next_steps", 0),
            "ideation_needed":     stats.get("ideas", 0) < 3,
            "next_steps_needed":   stats.get("next_steps", 0) < 4,
            "execution_ready":     executable_count > 0,
            "structure_needed":    not self._structure_initialized,
            # Gap fields
            "open_gap_count":      open_gap_count,
            "high_gap_count":      high_gap_count,
            "has_open_gaps":       open_gap_count > 0,
            "has_high_gaps":       high_gap_count > 0,
            "gap_dispatch":        gap_dispatch,
            "gaps_need_questions": gap_dispatch.get("questions", 0) > 0,
            "gaps_need_actions":   gap_dispatch.get("actions", 0) > 0,
            "gaps_need_next_steps":gap_dispatch.get("next_steps", 0) > 0,
            "gaps_need_ideas":     gap_dispatch.get("ideas", 0) > 0,
            # Retry fields
            "retry_candidates":    retry_candidates,
            "has_retry_candidates":retry_candidates > 0,
            "escalated_count":     escalated_count,
            "dismissed_count":     dismissed_count,
        }

        # Summary string
        summary_parts = []
        if analysis["recent_progress"]:
            summary_parts.append(f"{analysis['recent_progress']} recent progress")
        if recent_artifacts:
            summary_parts.append(f"{recent_artifacts} artifacts")
        if executable_count:
            summary_parts.append(f"{executable_count} executable actions")
        if stale_count:
            summary_parts.append(f"{stale_count} stale actions")
        if retry_candidates:
            summary_parts.append(f"{retry_candidates} pending retry")
        if escalated_count:
            summary_parts.append(f"{escalated_count} escalated (need user input)")
        if dismissed_count:
            summary_parts.append(f"{dismissed_count} dismissed")
        if open_gap_count:
            summary_parts.append(f"{open_gap_count} open gaps ({high_gap_count} high)")
        if stats.get("issues", 0):
            summary_parts.append(f"{stats['issues']} issues")
        if stats.get("next_steps", 0):
            summary_parts.append(f"{stats['next_steps']} next steps")
        if stats.get("ideas", 0):
            summary_parts.append(f"{stats['ideas']} ideas")

        analysis["summary"] = "; ".join(summary_parts) if summary_parts else "Board initialized"
        return analysis

    # ==================================================================
    # STAGE SELECTION
    # ==================================================================

    def _select_stages(self, analysis: Dict[str, Any], iteration: int) -> List[str]:
        """
        Intelligently select which stages to run this iteration.

        Fixed pipeline order:
          info_gaps  (always)
          review     (periodic)
          project_structure (first iteration + periodic)
          ideas / next_steps / actions  (pipeline stages)
          execution  (when ready)
          retry      (periodic + when candidates exist, with cooldown)
          questions  (gap-driven + escalation-driven + periodic)
          artifacts  (periodic)
        """
        stages: List[str] = []

        executable_count    = analysis["executable_count"]
        ideas_count         = analysis["ideas_count"]
        next_steps_count    = analysis["next_steps_count"]
        open_gap_count      = analysis["open_gap_count"]
        high_gap_count      = analysis["high_gap_count"]
        gap_dispatch        = analysis["gap_dispatch"]
        retry_candidates    = analysis["retry_candidates"]
        escalated_count     = analysis["escalated_count"]

        need_ideas      = ideas_count < 3
        need_next_steps = next_steps_count < 4
        need_actions    = executable_count < 2

        # ── ALWAYS: Info gap detection ─────────────────────────────────
        stages.append("info_gaps")

        # ── PERIODIC: Review ──────────────────────────────────────────
        if iteration % 4 == 0:
            stages.append("review")

        # ── PRIORITY 0: Project structure ─────────────────────────────
        if iteration == 1 and not self._structure_initialized:
            stages.append("project_structure")
            self._structure_initialized = True
        elif iteration % 10 == 0:
            stages.append("project_structure")

        # ── PRIORITY 1: Fresh execution ────────────────────────────────
        if executable_count > 0:
            if high_gap_count == 0 or executable_count >= 3:
                stages.append("execution")
            else:
                self.fm._stream_output(
                    f"   ⚠️  Execution deferred: {high_gap_count} high-priority gap(s) blocking",
                    "warning",
                )

        # ── PRIORITY 1b: Retry pass (separate from fresh execution) ───
        # Rules:
        #  a) There must be retry candidates
        #  b) Cooldown: at least RETRY_ITERATION_INTERVAL iterations since last retry
        #  c) Escalated actions (waiting for user) are excluded from retry
        #     — they have needs_retry=True but escalated=True, so execute_retry_stage
        #       skips them automatically
        retry_due = (
            retry_candidates > 0
            and (iteration - self._last_retry_iteration) >= RETRY_ITERATION_INTERVAL
        )
        if retry_due:
            stages.append("retry")
            self.fm._stream_output(
                f"   🔁 Scheduling retry pass ({retry_candidates} candidate(s), "
                f"last retry was iteration {self._last_retry_iteration})",
                "info",
            )
        elif retry_candidates > 0:
            cooldown_remaining = (
                RETRY_ITERATION_INTERVAL - (iteration - self._last_retry_iteration)
            )
            self.fm._stream_output(
                f"   ⏳ Retry deferred ({retry_candidates} candidate(s)), "
                f"cooldown {cooldown_remaining} iteration(s) remaining",
                "info",
            )

        # ── PRIORITY 2: Pipeline stages ────────────────────────────────
        if executable_count > 0:
            if need_actions and executable_count <= 1:
                if (next_steps_count > 0 or ideas_count > 0) and self._consecutive_action_stages < 2:
                    stages.append("actions")
                    self._consecutive_action_stages += 1
                else:
                    self._consecutive_action_stages = 0
            if need_next_steps:
                stages.append("next_steps")
            if need_ideas and ideas_count < 2:
                stages.append("ideas")

        elif analysis["stats"].get("actions", 0) > 0 and executable_count == 0:
            if need_ideas:
                stages.append("ideas")
            if need_next_steps or next_steps_count < 5:
                stages.append("next_steps")
            if (ideas_count >= 2 or next_steps_count >= 3) and self._consecutive_action_stages < 2:
                stages.append("actions")
                self._consecutive_action_stages += 1
            else:
                self._consecutive_action_stages = 0

        elif (ideas_count > 0 or next_steps_count > 0) and need_actions:
            if (ideas_count >= 2 or next_steps_count >= 3) and self._consecutive_action_stages < 2:
                stages.append("actions")
                self._consecutive_action_stages += 1
            else:
                if need_ideas:
                    stages.append("ideas")
                if need_next_steps:
                    stages.append("next_steps")
                self._consecutive_action_stages = 0

        elif need_ideas and need_next_steps:
            stages.append("ideas")
            stages.append("next_steps")
            if executable_count == 0 and self._consecutive_action_stages < 1:
                stages.append("actions")
                self._consecutive_action_stages += 1

        elif ideas_count > 0 and need_next_steps:
            stages.append("next_steps")
            if next_steps_count + 3 >= 4 and need_actions and self._consecutive_action_stages < 2:
                stages.append("actions")
                self._consecutive_action_stages += 1

        elif next_steps_count > 0 and need_actions:
            if self._consecutive_action_stages < 2:
                stages.append("actions")
                self._consecutive_action_stages += 1
            else:
                if ideas_count < 5:
                    stages.append("ideas")
                if next_steps_count < 6:
                    stages.append("next_steps")
                self._consecutive_action_stages = 0

        else:
            if iteration % 3 == 0 and ideas_count < 5:
                stages.append("ideas")
            elif iteration % 3 == 1 and next_steps_count < 6:
                stages.append("next_steps")
            elif executable_count < 3 and self._consecutive_action_stages < 1:
                stages.append("actions")
                self._consecutive_action_stages += 1

        # ── Gap-driven stage boosts ────────────────────────────────────
        if gap_dispatch.get("actions", 0) > 0 and "actions" not in stages:
            self.fm._stream_output(
                f"   🔎 Boosting 'actions' ({gap_dispatch['actions']} gap(s) need tool calls)",
                "info",
            )
            stages.append("actions")

        if gap_dispatch.get("next_steps", 0) > 0 and "next_steps" not in stages:
            self.fm._stream_output(
                f"   🔎 Boosting 'next_steps' ({gap_dispatch['next_steps']} gap(s) need research)",
                "info",
            )
            stages.append("next_steps")

        if gap_dispatch.get("ideas", 0) > 0 and "ideas" not in stages:
            self.fm._stream_output(
                f"   🔎 Boosting 'ideas' ({gap_dispatch['ideas']} gap(s) need exploration)",
                "info",
            )
            stages.append("ideas")

        # ── Questions: gap-driven + escalation-driven + periodic ──────
        # Escalated actions mean the questions stage should run so the
        # user sees the help request that was generated.
        if escalated_count > 0 and "questions" not in stages:
            self.fm._stream_output(
                f"   🆘 Boosting 'questions' ({escalated_count} escalated action(s) need user input)",
                "info",
            )
            stages.append("questions")

        if gap_dispatch.get("questions", 0) > 0:
            self.fm._stream_output(
                f"   🔎 Boosting 'questions' ({gap_dispatch['questions']} gap(s) need user input)",
                "info",
            )
            if "questions" not in stages:
                stages.append("questions")
        elif iteration % 4 == 0 and "questions" not in stages:
            stages.append("questions")

        # ── Artifacts: periodic ───────────────────────────────────────
        if iteration % 5 == 0 and analysis["recent_progress"] > 2:
            if "artifacts" not in stages:
                stages.append("artifacts")

        # ── Fallback: always do something ────────────────────────────
        content_stages = [s for s in stages if s not in ("info_gaps", "review")]
        if not content_stages:
            self.fm._stream_output(
                "   No content stages selected — defaulting to upstream generation",
                "warning",
            )
            stages.extend(["ideas", "next_steps"])
            self._consecutive_action_stages = 0

        # ── Reset action counter if we're not doing actions ───────────
        if "actions" not in stages:
            self._consecutive_action_stages = 0

        return stages

    # ==================================================================
    # STAGE EXECUTION
    # ==================================================================

    def _count_executable_actions(self) -> int:
        """Count actions that are fresh (not retrying, not dismissed, not done)."""
        from Vera.ProactiveFocus.Experimental.Components.stage_executor import StageExecutor
        actions = self.fm.board.get_category("actions")
        count   = 0
        for action in actions:
            if isinstance(action, dict):
                metadata = action.get("metadata", {})
                if (
                    not metadata.get("executed")
                    and not metadata.get("stale")
                    and not metadata.get("failed")
                    and not metadata.get("completed")
                    and not metadata.get("dismissed")
                    and not StageExecutor._action_is_retry_candidate(action)
                ):
                    count += 1
            else:
                count += 1
        return count

    def _execute_stage(self, stage: str, context: str) -> Any:
        if stage == "info_gaps":
            return self.fm.stage_executor.execute_info_gaps_stage(context)
        elif stage == "ideas":
            return self.fm.stage_executor.execute_ideas_stage(context)
        elif stage == "next_steps":
            return self.fm.stage_executor.execute_next_steps_stage(context)
        elif stage == "actions":
            return self.fm.stage_executor.execute_actions_stage(context)
        elif stage == "execution":
            return self.fm.stage_executor.execute_execution_stage(
                max_executions=2, priority_filter="all"
            )
        elif stage == "retry":
            result = self.fm.stage_executor.execute_retry_stage(
                max_retries_this_run=RETRY_MAX_PER_ITERATION
            )
            # Update cooldown tracker regardless of whether any retries succeeded
            self._last_retry_iteration = self._current_iteration
            return result
        elif stage == "review":
            return self.fm.stage_executor.execute_review_stage(context)
        elif stage == "questions":
            return self.fm.stage_executor.execute_questions_stage(context)
        elif stage == "artifacts":
            return self.fm.stage_executor.execute_artifacts_stage(context)
        elif stage == "project_structure":
            return self.fm.stage_executor.execute_project_structure_stage(context)
        else:
            self.fm._stream_output(f"⚠️  Unknown stage: {stage}", "warning")
            return None

    # Track current iteration for the retry cooldown updater above
    @property
    def _current_iteration(self) -> int:
        """Return the iteration counter from the run() loop (best-effort)."""
        return getattr(self, "_iteration_counter", 0)

    # ==================================================================
    # ACTION LIFECYCLE
    # ==================================================================

    def _process_completed_actions(self):
        """Move completed/failed/dismissed actions to appropriate categories."""
        actions     = self.fm.board.get_category("actions")
        moved_count = 0

        for idx in reversed(range(len(actions))):
            action   = actions[idx]
            metadata = action.get("metadata", {}) if isinstance(action, dict) else {}

            if metadata.get("executed") or metadata.get("completed"):
                # Already logged to progress by StageExecutor on success —
                # just remove from actions queue.
                actions.pop(idx)
                moved_count += 1

            elif metadata.get("dismissed"):
                # Already logged to issues by StageExecutor — remove from queue.
                actions.pop(idx)
                moved_count += 1

            elif metadata.get("failed") and not metadata.get("needs_retry"):
                # Legacy "failed" flag from old code paths (no retry support).
                self.fm.board.move_to_category("actions", idx, "issues")
                moved_count += 1

        if moved_count:
            self.fm._stream_output(f"   Moved {moved_count} completed/dismissed actions", "info")

    def _cleanup_stale_actions(self):
        """Move actions that are stale but have no retry path to issues."""
        actions       = self.fm.board.get_category("actions")
        cleaned_count = 0

        for idx in reversed(range(len(actions))):
            action   = actions[idx]
            metadata = action.get("metadata", {}) if isinstance(action, dict) else {}

            # Only clean up stale items that have exhausted retries or
            # have the old-style stale flag and no retry tracking at all.
            is_legacy_stale = (
                metadata.get("stale")
                and not metadata.get("needs_retry")
                and not metadata.get("retry_count")
            )
            if is_legacy_stale:
                note   = action.get("note", str(action)) if isinstance(action, dict) else str(action)
                reason = metadata.get("stale_reason", "could not execute")
                self.fm.add_to_focus_board(
                    "issues",
                    f"Stale action: {note[:100]} ({reason})",
                    metadata={
                        "original_action": action,
                        "stale_at":        datetime.utcnow().isoformat(),
                    },
                )
                actions.pop(idx)
                cleaned_count += 1

        if cleaned_count:
            self.fm._stream_output(f"   Cleaned {cleaned_count} stale actions", "info")

    def get_stage_distribution(self, last_n_iterations: int = 10) -> Dict[str, int]:
        """Current target cadences (informational only)."""
        return {
            "info_gaps":         1,   # every iteration
            "ideas":             3,
            "next_steps":        3,
            "actions":           3,
            "execution":         1,
            "retry":             RETRY_ITERATION_INTERVAL,
            "review":            4,
            "questions":         4,   # every 4th iteration + gap/escalation-driven
            "artifacts":         5,
            "project_structure": 10,
        }


# Patch run() to track iteration counter for retry cooldown
_original_run = IterationManager.run


def _patched_run(self, max_iterations=None, iteration_interval=300, auto_execute=True):
    """Thin wrapper that keeps _iteration_counter in sync with the loop."""
    iteration = 0
    import time as _time

    while (max_iterations is None or iteration < max_iterations) and self.fm.workflow_active:
        iteration += 1
        self._iteration_counter = iteration
        # Delegate to inner logic — re-implement inline so we don't call
        # ourselves recursively.  The simplest approach: just set the counter
        # before each inner run call.  Since _original_run already has the
        # full loop, we instead override _execute_stage to capture the counter.
        break   # Immediately break; the real loop is in _original_run.

    # Use _original_run with counter injection via _execute_stage wrapping.
    _original_execute_stage = self._execute_stage

    def _counting_execute_stage(stage, context):
        # iteration_counter is already set above per-loop-iteration
        return _original_execute_stage(stage, context)

    self._execute_stage = _counting_execute_stage
    _original_run(self, max_iterations, iteration_interval, auto_execute)


# Rather than a fragile wrapper, track the counter directly in run()
# by monkey-patching only the body.  The cleanest approach: override run()
# to call the original but update the counter before _select_stages.

def _run_with_counter(
    self,
    max_iterations:     Optional[int] = None,
    iteration_interval: int           = 300,
    auto_execute:       bool          = True,
):
    """run() override that keeps _iteration_counter in sync."""
    import time
    iteration = 0

    while (max_iterations is None or iteration < max_iterations) and self.fm.workflow_active:
        iteration += 1
        self._iteration_counter = iteration  # ← used by _execute_stage("retry")

        self.fm._stream_output("\n" + "=" * 60, "info")
        self.fm._stream_output(f"🔄 ITERATION {iteration}", "info")
        self.fm._stream_output("=" * 60 + "\n", "info")

        try:
            iteration_id = self.fm._create_iteration_node()

            analysis = self._analyze_board_state()
            self.fm._stream_output("📊 Board Analysis:", "info")
            self.fm._stream_output(f"   {analysis['summary']}", "info")

            context = self.fm.context_enricher.build_iteration_context(iteration, analysis)

            stages = self._select_stages(analysis, iteration)
            self.fm._stream_output(f"\n🎯 Selected Stages: {', '.join(stages)}", "info")

            stage_results = {}
            for stage in stages:
                result = self._execute_stage(stage, context)
                stage_results[stage] = result
                time.sleep(2)

            self._process_completed_actions()

            if iteration % 2 == 0:
                self._cleanup_stale_actions()

            if hasattr(self.fm, "agent") and hasattr(self.fm.agent, "runtime_sandbox"):
                stats = self.fm.agent.runtime_sandbox.get_stats()
                if stats.get("artifacts_created", 0) > 0:
                    self.fm._stream_output(
                        f"📦 Artifacts: {stats['artifacts_created']} created, "
                        f"{stats['artifacts_modified']} modified",
                        "info",
                    )

            self.fm.doc_generator.generate_iteration_summary(
                iteration=iteration,
                analysis=analysis,
                stages=stages,
                results=stage_results,
            )

            checkpoint = self.fm.save_focus_board()
            self.fm._stream_output(f"\n💾 Checkpoint: {checkpoint}", "success")

            self.fm._complete_iteration_node(summary=analysis["summary"])

            if max_iterations is None or iteration < max_iterations:
                self.fm._stream_output(f"\n⏳ Waiting {iteration_interval}s…", "info")
                time.sleep(iteration_interval)

        except Exception as e:
            self.fm._stream_output(f"\n❌ Error: {str(e)}", "error")
            import traceback
            traceback.print_exc()
            time.sleep(30)

    self.fm._stream_output(f"\n✅ Workflow completed: {iteration} iterations", "success")


# Replace the original run() with the counter-aware version
IterationManager.run = _run_with_counter