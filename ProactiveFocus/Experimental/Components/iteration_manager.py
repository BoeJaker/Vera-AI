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
        
        Priority logic:
        1. If executable actions exist -> prioritize execution
        2. If actions but no next_steps -> generate next_steps
        3. If next_steps but few ideas -> generate ideas
        4. If stuck (few of everything) -> generate ideas + next_steps
        5. Otherwise -> balanced approach
        """
        stages = []
        stats = analysis["stats"]
        
        # PRIORITY 1: Execute if we have actions
        if stats.get("actions", 0) > 0:
            stages.append("execution")
            
            # Also generate next steps if running low
            if stats.get("next_steps", 0) < 2:
                stages.append("next_steps")
        
        # PRIORITY 2: Generate next steps if we have ideas but no steps
        elif stats.get("ideas", 0) > 0 and stats.get("next_steps", 0) == 0:
            stages.append("next_steps")
            stages.append("actions")
        
        # PRIORITY 3: Generate ideas if running low on everything
        elif analysis["ideation_needed"]:
            stages.append("ideas")
            stages.append("next_steps")
        
        # PRIORITY 4: Balanced execution (next_steps -> actions)
        else:
            if stats.get("next_steps", 0) < 5:
                stages.append("next_steps")
            stages.append("actions")
        
        # Always check for review stage periodically
        if self.fm.iteration_count % 3 == 0:
            stages.insert(0, "review")
        
        return stages
    
    def _execute_stage(self, stage: str, context: str) -> Any:
        """Execute a specific stage."""
        if stage == "ideas":
            return self.fm.stage_executor.execute_ideas_stage(context)
        elif stage == "next_steps":
            return self.fm.stage_executor.execute_next_steps_stage(context)
        elif stage == "actions":
            return self.fm.stage_executor.execute_actions_stage(context)
        elif stage == "execution":
            return self.fm.stage_executor.execute_execution_stage(max_executions=2)
        elif stage == "review":
            return self.fm.stage_executor.execute_review_stage(context)
        else:
            self.fm._stream_output(f"⚠️ Unknown stage: {stage}", "warning")
            return None
    
    def _process_completed_actions(self):
        """Move completed actions from actions list to progress/issues."""
        actions = self.fm.board.get_category("actions")
        
        for idx in reversed(range(len(actions))):
            action = actions[idx]
            note = action.get("note", "") if isinstance(action, dict) else str(action)
            
            # Check if action has execution metadata indicating completion
            metadata = action.get("metadata", {}) if isinstance(action, dict) else {}
            
            if metadata.get("executed") or metadata.get("completed"):
                # Move to progress if successful
                if metadata.get("success", True):
                    self.fm.board.move_to_category("actions", idx, "progress")
                else:
                    self.fm.board.move_to_category("actions", idx, "issues")