# stage_executor.py
"""Executes individual workflow stages."""

import json
from typing import Optional, List, Dict, Any
from datetime import datetime


class StageExecutor:
    """Executes individual workflow stages with graph integration."""
    
    def __init__(self, focus_manager):
        self.fm = focus_manager
    
    def execute_ideas_stage(self, context: Optional[str] = None) -> List[str]:
        """Generate ideas with full graph integration."""
        stage_id = self._create_stage_node("Ideas Generation", "ideas")
        
        self.fm._set_stage("Ideas Generation", "Analyzing and generating creative ideas", 3)
        self.fm._stream_output(f"🎯 Focus: {self.fm.focus}", "info")
        self.fm._stream_output("💡 Generating ideas...", "info")
        
        prompt = f"""
        Project: {self.fm.focus}
        
        Current State:
        {json.dumps(self.fm.board.get_stats(), indent=2)}
        
        {f"Context: {context}" if context else ""}
        
        Generate 5 creative, actionable ideas to advance this project.
        Focus on practical solutions and innovative approaches.
        Respond with a JSON array of idea strings.
        """
        
        self.fm._update_progress()
        
        try:
            response = ""
            for chunk in self.fm._stream_llm_with_thought_broadcast(self.fm.agent.deep_llm, prompt):
                response += chunk
            
            self.fm._update_progress()
            self.fm._stream_output("✅ Ideas generated", "success")
            
        except Exception as e:
            self.fm._stream_output(f"❌ Error: {str(e)}", "error")
            response = f"Error: {str(e)}"
        
        ideas = self._parse_json_response(response)
        
        self.fm._update_progress()
        self.fm._stream_output(f"📊 Generated {len(ideas)} ideas", "success")
        
        # Create nodes and link
        for idx, idea in enumerate(ideas, 1):
            if self.fm.hybrid_memory:
                idea_id = f"idea_{stage_id}_{idx}"
                self.fm.hybrid_memory.upsert_entity(
                    entity_id=idea_id,
                    etype="idea",
                    labels=["Idea", "FocusBoardItem"],
                    properties={
                        "text": idea,
                        "category": "ideas",
                        "index": idx,
                        "stage_id": stage_id,
                        "project_id": self.fm.project_id,
                        "created_at": datetime.utcnow().isoformat()
                    }
                )
                self.fm.hybrid_memory.link(stage_id, idea_id, "GENERATED", {"index": idx})
            
            self.fm.add_to_focus_board("ideas", idea)
            self.fm._stream_output(f"  {idx}. {idea[:100]}{'...' if len(idea) > 100 else ''}", "info")
        
        self._complete_stage_node(stage_id, response, len(ideas))
        self.fm._clear_stage()
        
        return ideas
    
    def execute_next_steps_stage(self, context: Optional[str] = None) -> List[str]:
        """Generate next steps."""
        stage_id = self._create_stage_node("Next Steps", "next_steps")
        
        self.fm._set_stage("Next Steps", "Determining actionable next steps", 3)
        
        prompt = f"""
        Project: {self.fm.focus}
        
        Current State:
        - Progress: {json.dumps(self.fm.board.get_category('progress')[-5:], indent=2)}
        - Issues: {json.dumps(self.fm.board.get_category('issues'), indent=2)}
        - Ideas: {json.dumps(self.fm.board.get_category('ideas'), indent=2)}
        
        {f"Context: {context}" if context else ""}
        
        Generate 5 specific, actionable next steps.
        Consider current progress and outstanding issues.
        Respond with a JSON array of step strings.
        """
        
        self.fm._update_progress()
        
        try:
            response = ""
            for chunk in self.fm._stream_llm_with_thought_broadcast(self.fm.agent.deep_llm, prompt):
                response += chunk
            
            self.fm._update_progress()
            
        except Exception as e:
            self.fm._stream_output(f"❌ Error: {str(e)}", "error")
            response = f"Error: {str(e)}"
        
        steps = self._parse_json_response(response)
        
        for idx, step in enumerate(steps, 1):
            if self.fm.hybrid_memory:
                step_id = f"next_step_{stage_id}_{idx}"
                self.fm.hybrid_memory.upsert_entity(
                    entity_id=step_id,
                    etype="next_step",
                    labels=["NextStep", "FocusBoardItem"],
                    properties={
                        "text": step,
                        "category": "next_steps",
                        "index": idx,
                        "stage_id": stage_id,
                        "project_id": self.fm.project_id,
                        "created_at": datetime.utcnow().isoformat()
                    }
                )
                self.fm.hybrid_memory.link(stage_id, step_id, "GENERATED", {"index": idx})
            
            self.fm.add_to_focus_board("next_steps", step)
            self.fm._stream_output(f"  {idx}. {step[:100]}", "info")
        
        self._complete_stage_node(stage_id, response, len(steps))
        self.fm._clear_stage()
        
        return steps
    
    def execute_actions_stage(self, context: Optional[str] = None) -> List[Dict[str, Any]]:
        """Generate executable actions."""
        stage_id = self._create_stage_node("Action Planning", "actions")
        
        self.fm._set_stage("Action Planning", "Creating executable actions", 4)
        
        available_tools = [tool.name for tool in self.fm.agent.tools]
        
        prompt = f"""
        Project: {self.fm.focus}
        
        Board State:
        {json.dumps(self.fm.board.get_all(), indent=2)}
        
        Available Tools: {available_tools}
        
        {f"Context: {context}" if context else ""}
        
        Generate 3-5 executable actions using available tools.
        Each action should include:
        - description: What to do
        - tools: Which tools to use
        - priority: high, medium, or low
        
        Respond with JSON array of action objects.
        """
        
        self.fm._update_progress()
        
        try:
            response = ""
            for chunk in self.fm._stream_llm_with_thought_broadcast(self.fm.agent.deep_llm, prompt):
                response += chunk
            
            self.fm._update_progress()
            
        except Exception as e:
            response = f"Error: {str(e)}"
        
        try:
            actions = json.loads(response)
            if not isinstance(actions, list):
                actions = [{"description": response, "tools": [], "priority": "medium"}]
        except:
            actions = [{"description": response, "tools": [], "priority": "medium"}]
        
        for idx, action in enumerate(actions, 1):
            description = action.get("description", str(action))
            priority = action.get("priority", "medium")
            
            if self.fm.hybrid_memory:
                action_id = f"action_{stage_id}_{idx}"
                self.fm.hybrid_memory.upsert_entity(
                    entity_id=action_id,
                    etype="action",
                    labels=["Action", "FocusBoardItem", priority.capitalize()],
                    properties={
                        "text": description,
                        "priority": priority,
                        "stage_id": stage_id,
                        "project_id": self.fm.project_id,
                        "created_at": datetime.utcnow().isoformat()
                    }
                )
                self.fm.hybrid_memory.link(stage_id, action_id, "GENERATED", {"priority": priority})
            
            self.fm.add_to_focus_board("actions", description, metadata=action)
            
            emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(priority, "⚪")
            self.fm._stream_output(f"  {emoji} {idx}. {description[:100]}", "info")
        
        self._complete_stage_node(stage_id, response, len(actions))
        self.fm._clear_stage()
        
        return actions
    
    def execute_execution_stage(self, max_executions: int = 2, priority_filter: str = "high") -> int:
        """Execute actions from board."""
        self.fm._set_stage("Execution", f"Executing {priority_filter} priority actions", max_executions + 1)
        
        actions = self.fm.board.get_category("actions")
        
        if not actions:
            self.fm._stream_output("⚠️ No actions to execute", "warning")
            self.fm._clear_stage()
            return 0
        
        executed_count = 0
        
        for idx, action in enumerate(actions):
            if executed_count >= max_executions:
                break
            
            action_dict = self._parse_action(action)
            priority = action_dict.get('priority', 'medium')
            
            if priority_filter != 'all' and priority != priority_filter:
                continue
            
            description = action_dict.get('description', '')
            
            self.fm._stream_output(f"\n▶️ Executing action {executed_count + 1}/{max_executions}:", "info")
            self.fm._stream_output(f"   {description[:150]}", "info")
            
            # Create execution stage
            exec_stage_id = self._create_stage_node(
                "Action Execution",
                "execution",
                f"Executing: {description[:50]}"
            )
            
            result = self._execute_via_toolchain(action_dict, exec_stage_id)
            
            # Mark action as executed
            action_dict['metadata'] = action_dict.get('metadata', {})
            action_dict['metadata']['executed'] = True
            action_dict['metadata']['success'] = bool(result)
            action_dict['metadata']['executed_at'] = datetime.utcnow().isoformat()
            
            executed_count += 1
            self.fm._update_progress()
        
        self.fm._clear_stage()
        return executed_count
    
    def execute_review_stage(self, context: Optional[str] = None) -> str:
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
            self.fm._stream_output("✅ Review complete", "success")
            
        except Exception as e:
            response = f"Error: {str(e)}"
        
        self.fm._clear_stage()
        return response
    
    def _create_stage_node(self, stage_name: str, stage_type: str, activity: str = "") -> Optional[str]:
        """Create stage node in graph."""
        if not self.fm.hybrid_memory:
            return None
        
        stage_id = f"stage_{stage_type}_{self.fm.current_iteration_id}_{int(datetime.now().timestamp())}"
        
        self.fm.hybrid_memory.upsert_entity(
            entity_id=stage_id,
            etype="workflow_stage",
            labels=["WorkflowStage", stage_type.capitalize()],
            properties={
                "stage_name": stage_name,
                "stage_type": stage_type,
                "activity": activity,
                "iteration_id": self.fm.current_iteration_id,
                "project_id": self.fm.project_id,
                "started_at": datetime.utcnow().isoformat(),
                "status": "in_progress"
            }
        )
        
        if self.fm.current_iteration_id:
            self.fm.hybrid_memory.link(
                self.fm.current_iteration_id,
                stage_id,
                "HAS_STAGE",
                {"stage_type": stage_type}
            )
        
        self.fm.current_stage_id = stage_id
        return stage_id
    
    def _complete_stage_node(self, stage_id: str, output: str, output_count: int):
        """Mark stage as complete."""
        if not self.fm.hybrid_memory or not stage_id:
            return
        
        with self.fm.hybrid_memory.graph._driver.session() as sess:
            sess.run("""
                MATCH (s:WorkflowStage {id: $id})
                SET s.completed_at = $completed_at,
                    s.status = 'completed',
                    s.output_count = $output_count
            """, {
                "id": stage_id,
                "completed_at": datetime.utcnow().isoformat(),
                "output_count": output_count
            })
        
        self.fm.previous_stage_id = stage_id
        self.fm.current_stage_id = None
    
    def _execute_via_toolchain(self, action: Dict[str, Any], stage_id: str) -> Optional[str]:
        """Execute action via toolchain."""
        description = action.get('description', str(action))
        
        query = f"""
Project: {self.fm.focus}
Action: {description}
Suggested Tools: {action.get('tools', [])}
Priority: {action.get('priority', 'medium')}
"""
        
        result = ""
        try:
            if self.fm.hybrid_memory and stage_id:
                execution_id = self.fm.hybrid_memory.create_tool_execution_node(
                    node_id=stage_id,
                    tool_name="toolchain",
                    metadata={
                        "executed_at": datetime.utcnow().isoformat(),
                        "input": description[:500]
                    }
                )
                
                with self.fm.hybrid_memory.track_execution(execution_id):
                    for chunk in self.fm.agent.toolchain.execute_tool_chain(query):
                        result += str(chunk)
                
                if result:
                    self.fm.hybrid_memory.create_tool_result_node(
                        execution_id=execution_id,
                        output=result,
                        metadata={"tool_name": "toolchain"}
                    )
            else:
                for chunk in self.fm.agent.toolchain.execute_tool_chain(query):
                    result += str(chunk)
            
            self.fm.add_to_focus_board("progress", f"Completed: {description}")
            return result
            
        except Exception as e:
            self.fm._stream_output(f"❌ Execution failed: {e}", "error")
            self.fm.add_to_focus_board("issues", f"Failed: {description} - {e}")
            return None
    
    def _parse_action(self, action) -> Dict[str, Any]:
        """Parse action item to dict."""
        if isinstance(action, dict):
            if 'description' in action:
                return action
            elif 'note' in action:
                note = action['note']
                try:
                    parsed = json.loads(note)
                    if isinstance(parsed, dict):
                        return parsed
                except:
                    pass
                return {
                    'description': note,
                    'priority': 'medium',
                    'tools': [],
                    'metadata': action.get('metadata', {})
                }
        
        return {
            'description': str(action),
            'priority': 'medium',
            'tools': [],
            'metadata': {}
        }
    
    def _parse_json_response(self, response: str) -> list:
        """Parse JSON response."""
        cleaned = response.strip()
        if cleaned.startswith('```'):
            lines = cleaned.split('\n')
            if lines[0].startswith('```'):
                lines = lines[1:]
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            cleaned = '\n'.join(lines)
        
        try:
            parsed = json.loads(cleaned)
            return parsed if isinstance(parsed, list) else [parsed]
        except:
            lines = [line.strip() for line in cleaned.split('\n') if line.strip()]
            return lines if lines else [response]