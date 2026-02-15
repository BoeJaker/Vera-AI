# stage_executor.py — CLEAN MODULAR VERSION
"""
Executes individual workflow stages using modular implementations.

All stages (Ideas, Next Steps, Actions, Questions, Artifacts) are implemented
as modular classes in Vera/ProactiveFocus/Experimental/Components/Stages/

Only Execution and Review stages remain here due to complex orchestrator integration.
"""

import json
import re
import time
from typing import Optional, List, Dict, Any
from datetime import datetime

# Direct imports - no fallback, no conditionals
from Vera.ProactiveFocus.Experimental.Components.Stages.ideas import IdeasStage
from Vera.ProactiveFocus.Experimental.Components.Stages.questions import QuestionsStage
from Vera.ProactiveFocus.Experimental.Components.Stages.next_steps import NextStepsStage
from Vera.ProactiveFocus.Experimental.Components.Stages.actions import ActionsStage
from Vera.ProactiveFocus.Experimental.Components.Stages.artifacts import ArtifactsStage


class StageExecutor:
    """Executes individual workflow stages with graph integration.
    
    All manager state (hybrid_memory, agent, focus, project_id, etc.)
    is accessed via self.fm (the parent ProactiveFocusManager).
    """
    
    def __init__(self, focus_manager):
        self.fm = focus_manager
        
        # Initialize modular stage instances
        self._ideas_stage = IdeasStage()
        self._questions_stage = QuestionsStage()
        self._next_steps_stage = NextStepsStage()
        self._actions_stage = ActionsStage()
        self._artifacts_stage = ArtifactsStage()
        
        print("[StageExecutor] Initialized with modular stages")
    
    # ============================================================
    # MODULAR STAGES (Direct delegation - no fallbacks)
    # ============================================================
    
    def execute_ideas_stage(self, context=None):
        """Generate ideas - delegates to IdeasStage."""
        output = self._ideas_stage.execute(self.fm, context)
        return output.ideas  # Return list for backward compatibility
    
    def execute_next_steps_stage(self, context=None):
        """Generate next steps - delegates to NextStepsStage."""
        output = self._next_steps_stage.execute(self.fm, context)
        return output.next_steps  # Return list for backward compatibility
    
    def execute_actions_stage(self, context=None):
        """Generate actions - delegates to ActionsStage."""
        output = self._actions_stage.execute(self.fm, context)
        return output.actions  # Return list for backward compatibility
    
    def execute_questions_stage(self, context=None):
        """Ask questions via Telegram - delegates to QuestionsStage."""
        return self._questions_stage.execute(self.fm, context)
    
    def execute_artifacts_stage(self, context=None):
        """Generate artifacts - delegates to ArtifactsStage."""
        return self._artifacts_stage.execute(self.fm, context)
    
    # ============================================================
    # EXECUTION STAGE (Complex orchestrator integration)
    # ============================================================
    
    def execute_execution_stage(self, max_executions=2, priority_filter="all"):
        """Execute actions/goals from the focus board."""
        self.fm._set_stage(
            "Goal Execution",
            f"Executing up to {max_executions} {priority_filter}-priority goals",
            max_executions + 1
        )
        self.fm._stream_output("Starting goal execution pipeline...", "info")
        
        actions = self.fm.board.get_category("actions")
        
        if not actions:
            self.fm._stream_output("No actions to execute", "warning")
            self.fm._clear_stage()
            return 0
        
        self.fm._stream_output(f"Found {len(actions)} total actions in focus board", "info")
        self.fm._update_progress()
        
        executed_count = 0
        skipped_count = 0
        
        for idx, action in enumerate(actions):
            if executed_count >= max_executions:
                remaining = len(actions) - idx
                self.fm._stream_output(
                    f"Reached max executions ({max_executions}), {remaining} remaining", "success")
                break
            
            # Parse into normalized goal dict
            goal_dict = self._parse_goal_item(action)
            priority = goal_dict.get('priority', 'medium')
            goal_text = goal_dict.get('goal', goal_dict.get('description', ''))
            
            # Skip already-executed or stale actions
            metadata = action.get('metadata', {}) if isinstance(action, dict) else {}
            if metadata.get('executed') or metadata.get('stale') or metadata.get('failed'):
                continue
            
            # Apply priority filter
            if priority_filter != 'all' and priority != priority_filter:
                skipped_count += 1
                continue
            
            priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(priority, "⚪")
            
            self.fm._stream_output(f"\n{'='*50}", "info")
            self.fm._stream_output(
                f"{priority_emoji} Goal {executed_count + 1}/{max_executions}: "
                f"{goal_text[:150]}{'...' if len(goal_text) > 150 else ''}", "info")
            
            if goal_dict.get('success_criteria'):
                self.fm._stream_output(
                    f"   Success criteria: {goal_dict['success_criteria'][:100]}", "info")
            
            # Route through handoff_to_toolchain
            try:
                result = self.handoff_to_toolchain(goal_dict)
                
                if result:
                    self.fm._stream_output("Goal completed", "success")
                    self.fm._stream_output(f"   Result: {str(result)[:200]}", "info")
                else:
                    self.fm._stream_output("Goal completed with no result", "warning")
                
                # Mark action as executed
                if isinstance(action, dict):
                    if 'metadata' not in action:
                        action['metadata'] = {}
                    action['metadata']['executed'] = True
                    action['metadata']['success'] = bool(result)
                    action['metadata']['executed_at'] = datetime.utcnow().isoformat()
                
                executed_count += 1
                self.fm._update_progress()
                
            except Exception as e:
                self.fm._stream_output(f"Execution failed: {str(e)}", "error")
                import traceback
                traceback.print_exc()
                
                if isinstance(action, dict):
                    if 'metadata' not in action:
                        action['metadata'] = {}
                    action['metadata']['failed'] = True
                    action['metadata']['error'] = str(e)
        
        # Mark remaining as stale if nothing executed
        if executed_count == 0 and actions:
            self.fm._stream_output("No actions could be executed — marking as stale", "warning")
            for action in actions:
                if isinstance(action, dict):
                    meta = action.get('metadata', {})
                    if not meta.get('executed') and not meta.get('stale') and not meta.get('failed'):
                        if 'metadata' not in action:
                            action['metadata'] = {}
                        action['metadata']['stale'] = True
                        action['metadata']['stale_reason'] = "execution_failed"
        
        self.fm._stream_output(f"\n{'='*50}", "info")
        self.fm._stream_output(
            f"Execution Summary: {executed_count}/{max_executions} completed, "
            f"{skipped_count} skipped (filter: {priority_filter})", "success")
        self.fm._clear_stage()
        return executed_count
    
    # ============================================================
    # REVIEW STAGE (File saving logic)
    # ============================================================
    
    def execute_review_stage(self, context=None):
        """Review current project state and generate summary."""
        self.fm._set_stage("Review", "Analyzing project state", 2)
        
        prompt = f"""
        Project: {self.fm.focus}
        
        Complete Board State:
        {json.dumps(self.fm.board.get_all(), indent=2)}
        
        Statistics:
        {json.dumps(self.fm.board.get_stats(), indent=2)}
        
        {f"Additional Context: {context}" if context else ""}
        
        Provide a comprehensive review of the project:
        1. Overall progress assessment
        2. Key achievements
        3. Outstanding challenges
        4. Recommended focus areas
        5. Next priorities
        
        Write in clear, professional prose.
        """
        
        self.fm._update_progress()
        
        try:
            response = ""
            for chunk in self.fm._stream_llm_with_thought_broadcast(self.fm.agent.deep_llm, prompt):
                response += chunk
            self.fm._update_progress()
            self.fm._stream_output("Review complete", "success")
        except Exception as e:
            response = f"Error: {str(e)}"
        
        # Save review to focus board
        if response and not response.startswith("Error:"):
            review_summary = response[:300] + "..." if len(response) > 300 else response
            self.fm.add_to_focus_board("progress", f"[Review] {review_summary}", metadata={
                "type": "review", "full_review_length": len(response),
                "timestamp": datetime.utcnow().isoformat()})
        
        # Save full review to project documentation folder
        if response and not response.startswith("Error:"):
            self._save_review_to_file(response)
        
        self.fm._clear_stage()
        return response
    
    # ============================================================
    # TOOLCHAIN HANDOFF
    # ============================================================
    
    def handoff_to_toolchain(self, action):
        """Hand off a goal to the toolchain via the orchestrator."""
        goal = action.get('goal', action.get('description', str(action)))
        priority = action.get('priority', 'medium')
        success_criteria = action.get('success_criteria', '')
        goal_context = action.get('context', '')
        
        stage_id = self.fm._create_stage_node(
            "Goal Execution", "execution", f"Executing: {goal[:80]}...")
        
        self.fm._set_stage("Goal Execution", f"Executing: {goal[:80]}...", 3)
        self.fm._stream_output("Starting goal execution via orchestrator", "info")
        self.fm._stream_output(f"Goal: {goal}", "info")
        
        priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(priority, "⚪")
        self.fm._stream_output(f"   Priority: {priority_emoji} {priority}", "info")
        
        if success_criteria:
            self.fm._stream_output(f"   Success criteria: {success_criteria}", "info")
        
        query = self._build_toolchain_query(goal, priority, success_criteria, goal_context)
        
        # Create execution tracking node
        execution_id = None
        if self.fm.hybrid_memory:
            try:
                execution_id = self.fm.hybrid_memory.create_tool_execution_node(
                    node_id=stage_id, tool_name="toolchain_orchestrated",
                    metadata={"executed_at": datetime.utcnow().isoformat(),
                              "goal": goal[:500], "priority": priority,
                              "success_criteria": success_criteria,
                              "session_id": self.fm.agent.sess.id if hasattr(self.fm.agent, 'sess') else None,
                              "iteration_id": self.fm.current_iteration_id,
                              "project_id": self.fm.project_id})
            except Exception as e:
                print(f"[StageExecutor] Could not create execution node: {e}")
        
        result = ""
        chunk_count = 0
        start_time = time.time()
        line_buffer = ""
        
        def flush_line_buffer():
            nonlocal line_buffer
            if line_buffer:
                self.fm._stream_output(f"  {line_buffer}", "info")
                line_buffer = ""
        
        try:
            self.fm._stream_output("Submitting to orchestrator...", "info")
            self.fm._update_progress()
            
            task_result = self._execute_goal_via_orchestrator(query)
            
            if task_result is None:
                self.fm._stream_output("Orchestrator unavailable, using direct toolchain", "warning")
                task_result = self._execute_goal_direct(query)
            
            try:
                for chunk in task_result:
                    chunk_str = str(chunk) if not isinstance(chunk, str) else chunk
                    result += chunk_str
                    chunk_count += 1
                    for char in chunk_str:
                        if char == '\n':
                            flush_line_buffer()
                        else:
                            line_buffer += char
                    if chunk_count % 100 == 0 and line_buffer:
                        self.fm._stream_output(f"  {line_buffer}...", "info")
            except TypeError:
                result = str(task_result) if task_result else ""
            
            flush_line_buffer()
            self.fm._update_progress()
            
            duration_ms = int((time.time() - start_time) * 1000)
            self.fm._stream_output(f"Execution complete ({chunk_count} chunks, {duration_ms}ms)", "success")
            
            # Create result node
            if self.fm.hybrid_memory and execution_id:
                try:
                    self.fm.hybrid_memory.create_tool_result_node(
                        execution_id=execution_id, output=result,
                        metadata={"tool_name": "toolchain_orchestrated",
                                  "chunks_received": chunk_count, "duration_ms": duration_ms,
                                  "goal": goal[:500]})
                except Exception as e:
                    print(f"[StageExecutor] Error creating result node: {e}")
            
            self.fm.add_to_focus_board("progress", f"Completed goal: {goal[:200]}")
            if result and result.strip():
                result_summary = result[:500] + "..." if len(result) > 500 else result
                self.fm.add_to_focus_board("progress", f"Result: {result_summary}")
            
            if success_criteria and result:
                self._evaluate_success(goal, success_criteria, result, stage_id)
            
            self.fm._complete_stage_node(output=result, output_count=1)
            self.fm._update_progress()
            self.fm._clear_stage()
            return result
            
        except Exception as e:
            flush_line_buffer()
            error_msg = f"Goal execution failed: {e}"
            self.fm._stream_output(f"{error_msg}", "error")
            self.fm.add_to_focus_board("issues", f"Failed: {goal[:100]} - {e}")
            self.fm._complete_stage_node(output=error_msg, output_count=0)
            self.fm._clear_stage()
            return None
    
    # ============================================================
    # HELPER METHODS
    # ============================================================
    
    def _build_toolchain_query(self, goal, priority, success_criteria, goal_context):
        """Build a structured query for the toolchain planner."""
        recent_progress = self.fm.board.get_category('progress')[-3:]
        recent_issues = self.fm.board.get_category('issues')[-3:]
        
        progress_notes = [p.get('note', '') if isinstance(p, dict) else str(p) for p in recent_progress]
        issue_notes = [i.get('note', '') if isinstance(i, dict) else str(i) for i in recent_issues]
        
        return f"""Project: {self.fm.focus}

GOAL: {goal}

Priority: {priority}
{f"Success Criteria: {success_criteria}" if success_criteria else ""}
{f"Additional Context: {goal_context}" if goal_context else ""}

Recent Progress:
{json.dumps(progress_notes, indent=2)}

Known Issues:
{json.dumps(issue_notes, indent=2)}

INSTRUCTIONS FOR PLANNER:
- Decompose this goal into concrete tool steps
- For tools requiring multiple parameters, provide input as a JSON object
- Use {{prev}} to reference the previous step's output
- Use {{step_N}} to reference step N's output
- Each step should have "tool" (tool name) and "input" (string or JSON object)
"""
    
    def _execute_goal_via_orchestrator(self, query):
        """Execute via orchestrator. Returns iterable or None."""
        if not hasattr(self.fm.agent, 'orchestrator') or not self.fm.agent.orchestrator:
            return None
        
        orchestrator = self.fm.agent.orchestrator
        
        if hasattr(orchestrator, 'submit_task'):
            try:
                task_result = orchestrator.submit_task(
                    "toolchain.execute", self.fm.agent, query, expert=False)
                
                if isinstance(task_result, str) and len(task_result) == 36 and '-' in task_result:
                    self.fm._stream_output(f"Task submitted: {task_result}", "info")
                    try:
                        from Vera.ChatUI.api.session import toolchain_executions
                    except ImportError:
                        return [f"Task submitted: {task_result}"]
                    
                    max_wait, poll_interval, elapsed, results = 300, 0.5, 0, []
                    while elapsed < max_wait:
                        if task_result in toolchain_executions:
                            execution = toolchain_executions[task_result]
                            if hasattr(execution, 'chunks') and execution.chunks:
                                results.extend(execution.chunks)
                                if hasattr(execution, 'completed') and execution.completed:
                                    return results
                            if hasattr(execution, 'result'):
                                if isinstance(execution.result, str):
                                    results.append(execution.result)
                                return results
                        time.sleep(poll_interval)
                        elapsed += poll_interval
                    results.append(f"Task {task_result} timed out")
                    return results
                
                elif hasattr(task_result, '__iter__') or hasattr(task_result, '__next__'):
                    return task_result
                elif hasattr(task_result, 'result'):
                    r = task_result.result()
                    return r if hasattr(r, '__iter__') else [str(r)]
                else:
                    return [str(task_result)]
            except Exception as e:
                self.fm._stream_output(f"Orchestrator submit failed: {e}", "warning")
                return None
        
        elif hasattr(orchestrator, 'execute_task'):
            try:
                r = orchestrator.execute_task("toolchain.execute", self.fm.agent, query)
                return r if hasattr(r, '__iter__') else [str(r)]
            except Exception as e:
                self.fm._stream_output(f"Orchestrator execute failed: {e}", "warning")
                return None
        
        elif hasattr(orchestrator, 'run'):
            try:
                r = orchestrator.run("toolchain.execute", query=query)
                return r if hasattr(r, '__iter__') else [str(r)]
            except Exception as e:
                self.fm._stream_output(f"Orchestrator run failed: {e}", "warning")
                return None
        
        return None
    
    def _execute_goal_direct(self, query):
        """Direct toolchain execution fallback."""
        self.fm._stream_output("Direct toolchain execution...", "info")
        
        if self.fm.hybrid_memory:
            execution_id = f"direct_exec_{int(time.time())}"
            try:
                execution_id = self.fm.hybrid_memory.create_tool_execution_node(
                    node_id=execution_id, tool_name="toolchain_direct",
                    metadata={"executed_at": datetime.utcnow().isoformat(),
                              "session_id": self.fm.agent.sess.id if hasattr(self.fm.agent, 'sess') else None,
                              "project_id": self.fm.project_id})
                with self.fm.hybrid_memory.track_execution(execution_id):
                    yield from self.fm.agent.toolchain.execute_tool_chain(query)
                return
            except Exception:
                pass
        
        yield from self.fm.agent.toolchain.execute_tool_chain(query)
    
    def _evaluate_success(self, goal, success_criteria, result, stage_id):
        """Evaluate whether execution result meets success criteria."""
        try:
            eval_prompt = f"""Evaluate this execution result against the success criteria.

Goal: {goal[:300]}
Success Criteria: {success_criteria[:200]}
Result (truncated): {result[:1000]}

Did the result meet the success criteria? Respond with:
- "YES" if criteria are met
- "PARTIAL" if partially met
- "NO" if not met

Follow with a brief (1-2 sentence) explanation.
"""
            evaluation = ""
            for chunk in self.fm._stream_llm_with_thought_broadcast(self.fm.agent.fast_llm, eval_prompt):
                evaluation += chunk
            
            evaluation = evaluation.strip()
            
            if evaluation.upper().startswith("YES"):
                self.fm._stream_output(f"Success criteria MET: {evaluation[:100]}", "success")
                status = "met"
            elif evaluation.upper().startswith("PARTIAL"):
                self.fm._stream_output(f"Success criteria PARTIALLY met: {evaluation[:100]}", "warning")
                status = "partial"
            else:
                self.fm._stream_output(f"Success criteria NOT met: {evaluation[:100]}", "warning")
                self.fm.add_to_focus_board("issues", f"Goal incomplete: {goal[:100]} - {evaluation[:200]}")
                status = "not_met"
            
            if self.fm.hybrid_memory and stage_id:
                eval_id = f"eval_{stage_id}_{int(time.time())}"
                self.fm.hybrid_memory.upsert_entity(
                    entity_id=eval_id, etype="evaluation",
                    labels=["Evaluation", "SuccessCheck"],
                    properties={"goal": goal[:500], "success_criteria": success_criteria,
                                "evaluation": evaluation[:500], "status": status,
                                "stage_id": stage_id, "project_id": self.fm.project_id,
                                "created_at": datetime.utcnow().isoformat()})
                self.fm.hybrid_memory.link(stage_id, eval_id, "EVALUATED_BY", {})
        except Exception as e:
            self.fm._stream_output(f"Could not evaluate success criteria: {e}", "warning")
    
    def _parse_goal_item(self, item):
        """Parse a focus board action item into a normalized goal dict."""
        if isinstance(item, dict):
            if 'goal' in item:
                return {'goal': item['goal'], 'priority': item.get('priority', 'medium'),
                        'success_criteria': item.get('success_criteria', ''), 'context': item.get('context', '')}
            if 'description' in item:
                return {'goal': item['description'], 'priority': item.get('priority', 'medium'),
                        'success_criteria': item.get('success_criteria', ''), 'context': item.get('context', '')}
            if 'note' in item:
                note = item['note']
                metadata = item.get('metadata', {})
                if isinstance(metadata, dict):
                    if metadata.get('goal'):
                        return {'goal': metadata['goal'], 'priority': metadata.get('priority', 'medium'),
                                'success_criteria': metadata.get('success_criteria', ''),
                                'context': metadata.get('context', '')}
                    if metadata.get('description'):
                        return {'goal': metadata['description'], 'priority': metadata.get('priority', 'medium'),
                                'success_criteria': metadata.get('success_criteria', ''),
                                'context': metadata.get('context', '')}
                if isinstance(note, str):
                    try:
                        parsed = json.loads(note.strip().strip('```json').strip('```').strip())
                        if isinstance(parsed, dict):
                            return {'goal': parsed.get('goal', parsed.get('description', note)),
                                    'priority': parsed.get('priority', 'medium'),
                                    'success_criteria': parsed.get('success_criteria', ''),
                                    'context': parsed.get('context', '')}
                    except (json.JSONDecodeError, ValueError):
                        pass
                return {'goal': str(note),
                        'priority': metadata.get('priority', 'medium') if isinstance(metadata, dict) else 'medium',
                        'success_criteria': metadata.get('success_criteria', '') if isinstance(metadata, dict) else '',
                        'context': ''}
            return {'goal': str(item), 'priority': item.get('priority', 'medium'),
                    'success_criteria': '', 'context': ''}
        
        elif isinstance(item, str):
            try:
                parsed = json.loads(item.strip().strip('```json').strip('```').strip())
                if isinstance(parsed, dict):
                    return {'goal': parsed.get('goal', parsed.get('description', item)),
                            'priority': parsed.get('priority', 'medium'),
                            'success_criteria': parsed.get('success_criteria', ''),
                            'context': parsed.get('context', '')}
            except (json.JSONDecodeError, ValueError):
                pass
            return {'goal': item, 'priority': 'medium', 'success_criteria': '', 'context': ''}
        
        return {'goal': str(item), 'priority': 'medium', 'success_criteria': '', 'context': ''}
    
    def _save_review_to_file(self, review_text):
        """Save review to project documentation folder."""
        import os
        project_id = self.fm.project_id or "unknown_project"
        
        base_dir = os.path.join(os.path.dirname(self.fm.focus_boards_dir), project_id, "reviews")
        alt_dir = os.path.join(self.fm.focus_boards_dir, "reviews")
        
        review_dir = base_dir
        try:
            os.makedirs(review_dir, exist_ok=True)
        except OSError:
            review_dir = alt_dir
            try:
                os.makedirs(review_dir, exist_ok=True)
            except OSError as e:
                print(f"[StageExecutor] Cannot create review directory: {e}")
                return
        
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(review_dir, f"review_{timestamp}.md")
        
        md_content = f"""# Project Review — {self.fm.focus or 'Unknown Focus'}
**Date:** {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}  
**Project ID:** {project_id}  

---

{review_text}

---

## Board Snapshot

**Statistics:** {json.dumps(self.fm.board.get_stats(), indent=2)}
"""
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(md_content)
            print(f"[StageExecutor] Review saved to: {filepath}")
            self.fm._stream_output(f"Review saved: {filepath}", "info")
        except Exception as e:
            print(f"[StageExecutor] Failed to save review: {e}")