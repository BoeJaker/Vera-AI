# iteration_manager.py
"""Manages iteration workflow and intelligent stage selection."""

import time
from typing import Optional, Dict, Any
from datetime import datetime


class IterationManager:
    """
    Intelligently manages workflow iterations and stage selection.
    
    Decides which stages to execute based on focus board state.
    """
    
    def __init__(self, focus_manager):
        self.fm = focus_manager
    
    def run(
        self,
        max_iterations: Optional[int] = None,
        iteration_interval: int = 300,
        auto_execute: bool = True
    ):
        """Run intelligent iterative workflow."""
        iteration = 0
        
        while (max_iterations is None or iteration < max_iterations) and self.fm.workflow_active:
            iteration += 1
            
            self.fm._stream_output("\n" + "="*60, "info")
            self.fm._stream_output(f"🔄 ITERATION {iteration}", "info")
            self.fm._stream_output("="*60 + "\n", "info")
            
            try:
                # Create iteration node
                iteration_id = self.fm._create_iteration_node()
                
                # Analyze board state
                analysis = self._analyze_board_state()
                self.fm._stream_output(f"📊 Board Analysis:", "info")
                self.fm._stream_output(f"   {analysis['summary']}", "info")
                
                # Build enriched context
                context = self.fm.context_enricher.build_iteration_context(iteration, analysis)
                
                # Decide stages to execute
                stages = self._select_stages(analysis)
                self.fm._stream_output(f"\n🎯 Selected Stages: {', '.join(stages)}", "info")
                
                # Execute selected stages
                stage_results = {}
                for stage in stages:
                    result = self._execute_stage(stage, context)
                    stage_results[stage] = result
                    time.sleep(2)
                
                # Move completed actions
                self._process_completed_actions()
                
                # Generate documentation
                self.fm.doc_generator.generate_iteration_summary(
                    iteration=iteration,
                    analysis=analysis,
                    stages=stages,
                    results=stage_results
                )
                
                # Save checkpoint
                checkpoint = self.fm.save_focus_board()
                self.fm._stream_output(f"\n💾 Checkpoint: {checkpoint}", "success")
                
                # Complete iteration
                self.fm._complete_iteration_node(summary=analysis['summary'])
                
                # Wait for next iteration
                if max_iterations is None or iteration < max_iterations:
                    self.fm._stream_output(f"\n⏳ Waiting {iteration_interval}s...", "info")
                    time.sleep(iteration_interval)
                
            except Exception as e:
                self.fm._stream_output(f"\n❌ Error: {str(e)}", "error")
                import traceback
                traceback.print_exc()
                time.sleep(30)
        
        self.fm._stream_output(f"\n✅ Workflow completed: {iteration} iterations", "success")
    
    def _analyze_board_state(self) -> Dict[str, Any]:
        """Analyze current board state to inform stage selection."""
        stats = self.fm.board.get_stats()
        
        analysis = {
            "stats": stats,
            "total_items": sum(stats.values()),
            "has_actions": stats.get("actions", 0) > 0,
            "has_ideas": stats.get("ideas", 0) > 0,
            "has_next_steps": stats.get("next_steps", 0) > 0,
            "has_issues": stats.get("issues", 0) > 0,
            "recent_progress": len(self.fm.board.get_category("progress")[-3:]),
            "actionable_count": stats.get("actions", 0) + stats.get("next_steps", 0),
            "ideation_needed": stats.get("ideas", 0) < 3 and stats.get("next_steps", 0) < 3,
            "execution_ready": stats.get("actions", 0) > 0,
        }
        
        # Generate summary
        summary_parts = []
        if analysis["recent_progress"] > 0:
            summary_parts.append(f"{analysis['recent_progress']} recent progress items")
        if stats.get("actions", 0) > 0:
            summary_parts.append(f"{stats['actions']} executable actions")
        if stats.get("issues", 0) > 0:
            summary_parts.append(f"{stats['issues']} open issues")
        if stats.get("next_steps", 0) > 0:
            summary_parts.append(f"{stats['next_steps']} next steps")
        if stats.get("ideas", 0) > 0:
            summary_parts.append(f"{stats['ideas']} ideas")
        
        analysis["summary"] = "; ".join(summary_parts) if summary_parts else "Board initialized"
        
        return analysis
        
    def _select_stages(self, analysis: Dict[str, Any]) -> list:
        """
        Intelligently select which stages to execute based on board state.
        
        FIX: Check if actions are actually executable (not stale/already executed).
        FIX: Don't select "execution" if all actions are stale or already run.
        FIX: Generate new actions if existing ones are all consumed.
        """
        stages = []
        stats = analysis["stats"]
        
        # FIX: Count truly executable actions (not stale, not already executed)
        executable_actions = self._count_executable_actions()
        
        # PRIORITY 1: Execute if we have genuinely executable actions
        if executable_actions > 0:
            stages.append("execution")
            
            # Also generate next steps if running low
            if stats.get("next_steps", 0) < 2:
                stages.append("next_steps")
        
        # PRIORITY 2: All actions consumed — generate new ones
        elif stats.get("actions", 0) > 0 and executable_actions == 0:
            # We have actions but they're all stale/executed
            # Clean them out and generate fresh ones
            stages.append("next_steps")
            stages.append("actions")
        
        # PRIORITY 3: Generate next steps if we have ideas but no steps
        elif stats.get("ideas", 0) > 0 and stats.get("next_steps", 0) == 0:
            stages.append("next_steps")
            stages.append("actions")
        
        # PRIORITY 4: Generate ideas if running low on everything
        elif analysis["ideation_needed"]:
            stages.append("ideas")
            stages.append("next_steps")
        
        # PRIORITY 5: Balanced execution (next_steps -> actions)
        else:
            if stats.get("next_steps", 0) < 5:
                stages.append("next_steps")
            stages.append("actions")
        
        # Review periodically (every 3rd iteration)
        if self.fm.iteration_count % 3 == 0:
            stages.insert(0, "review")
        
        return stages


    def _count_executable_actions(self) -> int:
        """Count actions that haven't been executed or marked stale."""
        actions = self.fm.board.get_category("actions")
        count = 0
        for action in actions:
            if isinstance(action, dict):
                metadata = action.get("metadata", {})
                if not metadata.get("executed") and not metadata.get("stale") and not metadata.get("failed"):
                    count += 1
            else:
                count += 1  # Non-dict items are assumed executable
        return count
    
    def _execute_stage(self, stage: str, context: str) -> Any:
        """Execute a specific stage.
        
        FIX: Pass priority_filter='all' to execution stage so it doesn't
        skip medium/low priority actions.
        """
        if stage == "ideas":
            return self.fm.stage_executor.execute_ideas_stage(context)
        elif stage == "next_steps":
            return self.fm.stage_executor.execute_next_steps_stage(context)
        elif stage == "actions":
            return self.fm.stage_executor.execute_actions_stage(context)
        elif stage == "execution":
            # FIX: priority_filter="all" — don't skip actions by priority
            return self.fm.stage_executor.execute_execution_stage(
                max_executions=2,
                priority_filter="all"
            )
        elif stage == "review":
            return self.fm.stage_executor.execute_review_stage(context)
        else:
            self.fm._stream_output(f"⚠️ Unknown stage: {stage}", "warning")
            return None
        

    def _process_completed_actions(self):
        """Move completed/stale actions from actions list to progress/issues.
        
        FIX: Also handle stale actions that couldn't be executed.
        """
        actions = self.fm.board.get_category("actions")
        
        for idx in reversed(range(len(actions))):
            action = actions[idx]
            metadata = action.get("metadata", {}) if isinstance(action, dict) else {}
            
            if metadata.get("executed") or metadata.get("completed"):
                if metadata.get("success", True):
                    self.fm.board.move_to_category("actions", idx, "progress")
                else:
                    self.fm.board.move_to_category("actions", idx, "issues")
            
            # FIX: Move stale actions to issues so they don't block new ones
            elif metadata.get("stale"):
                note = action.get("note", str(action)) if isinstance(action, dict) else str(action)
                reason = metadata.get("stale_reason", "could not execute")
                self.fm.add_to_focus_board("issues", f"Stale action: {note[:100]} ({reason})")
                actions.pop(idx)
