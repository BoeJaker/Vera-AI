# iteration_manager.py — MODULAR STAGES VERSION
"""Manages iteration workflow and intelligent stage selection.

UPDATED: Now uses modular stages from Vera/ProactiveFocus/stages/
FIXED: Better stage selection to avoid getting stuck in actions
FIXED: Proper action completion and board movement
"""

import time
from typing import Optional, Dict, Any, List
from datetime import datetime


class IterationManager:
    """
    Intelligently manages workflow iterations and stage selection.
    
    Decides which stages to execute based on focus board state.
    Uses modular stage implementations from Vera/ProactiveFocus/stages/.
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
                
                # Process completed actions AFTER execution
                self._process_completed_actions()
                
                # Clean up stale actions periodically
                if iteration % 2 == 0:
                    self._cleanup_stale_actions()
                
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
        """Analyze current board state to inform stage selection.
        
        ENHANCED: Track executable vs stale actions for better decisions.
        """
        stats = self.fm.board.get_stats()
        
        # Count truly executable actions
        executable_count = self._count_executable_actions()
        stale_count = stats.get("actions", 0) - executable_count
        
        analysis = {
            "stats": stats,
            "total_items": sum(stats.values()),
            "has_actions": stats.get("actions", 0) > 0,
            "has_executable_actions": executable_count > 0,
            "has_ideas": stats.get("ideas", 0) > 0,
            "has_next_steps": stats.get("next_steps", 0) > 0,
            "has_issues": stats.get("issues", 0) > 0,
            "recent_progress": len(self.fm.board.get_category("progress")[-5:]),
            "executable_count": executable_count,
            "stale_count": stale_count,
            "ideas_count": stats.get("ideas", 0),
            "next_steps_count": stats.get("next_steps", 0),
            "actionable_count": stats.get("actions", 0) + stats.get("next_steps", 0),
            "ideation_needed": stats.get("ideas", 0) < 2,
            "next_steps_needed": stats.get("next_steps", 0) < 3,
            "execution_ready": executable_count > 0,
        }
        
        # Generate summary
        summary_parts = []
        if analysis["recent_progress"] > 0:
            summary_parts.append(f"{analysis['recent_progress']} recent progress")
        if executable_count > 0:
            summary_parts.append(f"{executable_count} executable actions")
        if stale_count > 0:
            summary_parts.append(f"{stale_count} stale actions")
        if stats.get("issues", 0) > 0:
            summary_parts.append(f"{stats['issues']} issues")
        if stats.get("next_steps", 0) > 0:
            summary_parts.append(f"{stats['next_steps']} next steps")
        if stats.get("ideas", 0) > 0:
            summary_parts.append(f"{stats['ideas']} ideas")
        
        analysis["summary"] = "; ".join(summary_parts) if summary_parts else "Board initialized"
        
        return analysis
    
    def _select_stages(self, analysis: Dict[str, Any]) -> List[str]:
        """
        Intelligently select which stages to execute based on board state.
        
        FIXED: Better flow control to avoid getting stuck in actions stage.
        Strategy: Maintain healthy pipeline (ideas → next_steps → actions → execution)
        """
        stages = []
        stats = analysis["stats"]
        executable_count = analysis["executable_count"]
        ideas_count = analysis["ideas_count"]
        next_steps_count = analysis["next_steps_count"]
        
        # Track what we need
        need_ideas = ideas_count < 2
        need_next_steps = next_steps_count < 3
        need_actions = executable_count < 2
        
        # STRATEGY 1: Execute what we have, but don't get stuck
        # Only execute if we have actions AND (ideas or next_steps to fall back to)
        if executable_count > 0:
            stages.append("execution")
            
            # Proactively generate pipeline for next iteration
            if need_next_steps:
                stages.append("next_steps")
            if need_ideas and not need_next_steps:
                # Only generate ideas if next_steps are healthy
                stages.append("ideas")
        
        # STRATEGY 2: All actions consumed - regenerate pipeline
        elif stats.get("actions", 0) > 0 and executable_count == 0:
            self.fm._stream_output("   All actions stale/executed - regenerating pipeline", "info")
            
            # Full pipeline refresh
            if need_ideas:
                stages.append("ideas")
            stages.append("next_steps")
            stages.append("actions")
        
        # STRATEGY 3: Have ideas/next_steps but no actions - generate actions
        elif (ideas_count > 0 or next_steps_count > 0) and need_actions:
            stages.append("actions")
            
            # Also top up pipeline
            if need_next_steps and ideas_count > 0:
                stages.append("next_steps")
            elif need_ideas:
                stages.append("ideas")
        
        # STRATEGY 4: Low on everything - full regeneration
        elif need_ideas and need_next_steps:
            stages.append("ideas")
            stages.append("next_steps")
            stages.append("actions")
        
        # STRATEGY 5: Have ideas but need next_steps
        elif ideas_count > 0 and need_next_steps:
            stages.append("next_steps")
            if need_actions:
                stages.append("actions")
        
        # STRATEGY 6: Have next_steps but need actions
        elif next_steps_count > 0 and need_actions:
            stages.append("actions")
        
        # STRATEGY 7: Everything healthy - maintain balance
        else:
            # Balanced maintenance
            if next_steps_count < 5:
                stages.append("next_steps")
            if executable_count < 3:
                stages.append("actions")
        
        # Review periodically (every 4th iteration)
        if self.fm.iteration_count % 4 == 0:
            stages.insert(0, "review")
        
        # Ensure we always do something
        if not stages:
            self.fm._stream_output("   No stages selected - defaulting to ideas+next_steps", "warning")
            stages = ["ideas", "next_steps"]
        
        return stages
    
    def _count_executable_actions(self) -> int:
        """Count actions that haven't been executed or marked stale.
        
        FIXED: Better metadata checking.
        """
        actions = self.fm.board.get_category("actions")
        count = 0
        
        for action in actions:
            if isinstance(action, dict):
                metadata = action.get("metadata", {})
                # Check all blocking flags
                if (not metadata.get("executed") and 
                    not metadata.get("stale") and 
                    not metadata.get("failed") and
                    not metadata.get("completed")):
                    count += 1
            else:
                # Non-dict items are assumed executable
                count += 1
        
        return count
    
    def _execute_stage(self, stage: str, context: str) -> Any:
        """Execute a specific stage using modular implementations.
        
        UPDATED: Uses stage_executor which delegates to modular stages.
        FIXED: Pass priority_filter='all' to execution.
        """
        if stage == "ideas":
            return self.fm.stage_executor.execute_ideas_stage(context)
        
        elif stage == "next_steps":
            return self.fm.stage_executor.execute_next_steps_stage(context)
        
        elif stage == "actions":
            return self.fm.stage_executor.execute_actions_stage(context)
        
        elif stage == "execution":
            # Execute all priority levels
            return self.fm.stage_executor.execute_execution_stage(
                max_executions=2,
                priority_filter="all"
            )
        
        elif stage == "review":
            return self.fm.stage_executor.execute_review_stage(context)
        
        elif stage == "questions":
            # NEW: Telegram Q&A stage
            return self.fm.stage_executor.execute_questions_stage(context)
        
        elif stage == "artifacts":
            # NEW: Document generation stage
            return self.fm.stage_executor.execute_artifacts_stage(context)
        
        else:
            self.fm._stream_output(f"⚠️ Unknown stage: {stage}", "warning")
            return None
    
    def _process_completed_actions(self):
        """Move completed/failed actions to appropriate categories.
        
        FIXED: Properly move actions to completed category in board.
        """
        actions = self.fm.board.get_category("actions")
        moved_count = 0
        
        # Process in reverse to avoid index issues
        for idx in reversed(range(len(actions))):
            action = actions[idx]
            metadata = action.get("metadata", {}) if isinstance(action, dict) else {}
            
            # Check if action is completed/executed
            if metadata.get("executed") or metadata.get("completed"):
                # Determine destination based on success
                if metadata.get("success", True):
                    self.fm.board.move_to_category("actions", idx, "progress")
                    moved_count += 1
                else:
                    self.fm.board.move_to_category("actions", idx, "issues")
                    moved_count += 1
            
            # Check if action failed
            elif metadata.get("failed"):
                self.fm.board.move_to_category("actions", idx, "issues")
                moved_count += 1
        
        if moved_count > 0:
            self.fm._stream_output(f"   Moved {moved_count} completed/failed actions", "info")
    
    def _cleanup_stale_actions(self):
        """Remove stale actions that couldn't be executed.
        
        FIXED: Move stale actions to issues instead of leaving them in actions.
        """
        actions = self.fm.board.get_category("actions")
        cleaned_count = 0
        
        # Process in reverse to avoid index issues
        for idx in reversed(range(len(actions))):
            action = actions[idx]
            metadata = action.get("metadata", {}) if isinstance(action, dict) else {}
            
            if metadata.get("stale"):
                # Extract note for issue tracking
                note = action.get("note", str(action)) if isinstance(action, dict) else str(action)
                reason = metadata.get("stale_reason", "could not execute")
                
                # Add to issues
                self.fm.add_to_focus_board(
                    "issues",
                    f"Stale action: {note[:100]} ({reason})",
                    metadata={"original_action": action, "stale_at": datetime.utcnow().isoformat()}
                )
                
                # Remove from actions
                actions.pop(idx)
                cleaned_count += 1
        
        if cleaned_count > 0:
            self.fm._stream_output(f"   Cleaned {cleaned_count} stale actions", "info")