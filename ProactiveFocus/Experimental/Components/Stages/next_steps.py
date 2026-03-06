"""
Next Steps Stage - ENHANCED
============================
Generate actionable next steps with workspace awareness.

ENHANCED: Analyzes incomplete work, recent changes, test coverage gaps,
and documentation needs to suggest informed next steps.
"""

import json
from typing import Dict, Any, Optional
from pathlib import Path
from Vera.ProactiveFocus.Experimental.Components.Stages.base import BaseStage, StageOutput
from Vera.Toolchain.sandbox import get_project_sandbox


class NextStepsStage(BaseStage):
    """Generate specific, actionable next steps"""
    
    def __init__(self):
        super().__init__(
            name="Next Steps",
            icon="🎯",
            description="Determine actionable next steps"
        )
    
    def execute(self, focus_manager, context: Optional[Dict[str, Any]] = None) -> StageOutput:
        """Generate next steps with workspace context awareness"""
        output = StageOutput()
        
        self._stream_output(focus_manager, "Analyzing current state...", "info")
        
        # Get project context
        project_context = self._get_project_context(focus_manager)
        
        self._stream_output(focus_manager, "Determining next steps...", "info")
        
        # Build enriched prompt
        prompt = self._build_context_aware_prompt(focus_manager, project_context, context)
        
        # Get LLM response
        try:
            response = self._stream_llm(focus_manager, focus_manager.agent.deep_llm, prompt, operation="generate_next_steps")
            self._stream_output(focus_manager, "Next steps generated", "success")
        except Exception as e:
            self._stream_output(focus_manager, f"Error: {str(e)}", "error")
            return output
        
        # Parse next steps
        steps = self._parse_json_response(response)
        
        self._stream_output(focus_manager, f"Generated {len(steps)} next steps", "success")
        
        # Add to board and output
        for idx, step in enumerate(steps, 1):
            # Add to focus board
            self._add_to_board(focus_manager, "next_steps", step)
            
            # Add to output
            output.next_steps.append(step)
            
            # Stream to console
            self._stream_output(
                focus_manager,
                f"  {idx}. {step[:100]}{'...' if len(step) > 100 else ''}",
                "info"
            )
        
        # Prioritize steps if we have many
        if len(steps) > 3:
            priority_steps = self._prioritize_steps(focus_manager, steps, project_context)
            if priority_steps:
                output.metadata['prioritized_steps'] = priority_steps
                
                self._stream_output(focus_manager, "\nPrioritized top 3:", "info")
                for idx, step in enumerate(priority_steps[:3], 1):
                    self._stream_output(
                        focus_manager,
                        f"  🔥 {idx}. {step[:100]}",
                        "info"
                    )
        
        # Notify via Telegram if available
        if steps:
            summary = f"{self.icon} Next Steps for: {focus_manager.focus}\n\n"
            summary += "\n".join(f"{i+1}. {step[:80]}..." for i, step in enumerate(steps[:3]))
            if len(steps) > 3:
                summary += f"\n...and {len(steps) - 3} more"
            
            self._notify_telegram(focus_manager, summary)
        
        return output
    
    def _get_project_context(self, focus_manager) -> Dict[str, Any]:
        """Get project workspace context"""
        sandbox = get_project_sandbox(focus_manager)
        
        if not sandbox:
            return {"available": False}
        
        try:
            from Vera.ProactiveFocus.Experimental.Components.project_context_analyzer import ProjectContextAnalyzer
            
            project_root = Path(sandbox.project_root)
            analyzer = ProjectContextAnalyzer(project_root)
            
            context = analyzer.get_full_context(
                include_file_tree=True,
                include_recent_changes=True,
                include_todos=True,
                include_stats=True,
                max_files_to_scan=100
            )
            
            context["available"] = True
            return context
            
        except Exception as e:
            self._stream_output(
                focus_manager,
                f"⚠️  Could not analyze workspace: {e}",
                "warning"
            )
            return {"available": False, "error": str(e)}
    
    def _build_context_aware_prompt(
        self,
        focus_manager,
        project_context: Dict[str, Any],
        additional_context: Optional[str]
    ) -> str:
        """Build prompt with rich project context"""
        
        board = focus_manager.board.get_all()
        
        prompt_parts = [
            f"Project: {focus_manager.focus}",
            "",
            "Current Board State:",
            f"- Progress: {len(board.get('progress', []))} items",
            f"- Issues: {len(board.get('issues', []))} items",
            f"- Ideas: {len(board.get('ideas', []))} items",
            f"- Actions: {len(board.get('actions', []))} items",
            ""
        ]
        
        # Recent progress
        recent_progress = board.get('progress', [])[-5:]
        if recent_progress:
            prompt_parts.append("Recent Progress:")
            for item in recent_progress:
                note = item.get('note', '') if isinstance(item, dict) else str(item)
                prompt_parts.append(f"  - {note[:100]}")
            prompt_parts.append("")
        
        # Outstanding issues
        issues = board.get('issues', [])
        if issues:
            prompt_parts.append(f"Outstanding Issues ({len(issues)}):")
            for item in issues[:5]:
                note = item.get('note', '') if isinstance(item, dict) else str(item)
                prompt_parts.append(f"  - {note[:100]}")
            prompt_parts.append("")
        
        # Workspace context
        if project_context.get("available"):
            prompt_parts.extend([
                "WORKSPACE ANALYSIS:",
                ""
            ])
            
            # Incomplete work indicators
            incomplete_work = []
            
            # Recent changes that might need follow-up
            if "recent_changes" in project_context:
                changes = project_context["recent_changes"]
                if changes:
                    incomplete_work.append(f"Recently Modified Files ({len(changes)}):")
                    for change in changes[:5]:
                        age_str = f"{change['age_hours']:.1f}h ago"
                        incomplete_work.append(f"  - {change['path']} (modified {age_str})")
            
            # TODOs that need addressing
            if "todos" in project_context:
                todos = project_context["todos"]
                if todos:
                    # Group by priority
                    fixmes = [t for t in todos if t['type'] == 'FIXME']
                    todos_only = [t for t in todos if t['type'] == 'TODO']
                    
                    if fixmes:
                        incomplete_work.append("")
                        incomplete_work.append(f"Critical FIXMEs ({len(fixmes)}):")
                        for item in fixmes[:5]:
                            incomplete_work.append(f"  - {item['file']}:{item['line']} - {item['message'][:80]}")
                    
                    if todos_only:
                        incomplete_work.append("")
                        incomplete_work.append(f"Outstanding TODOs ({len(todos_only)}):")
                        for item in todos_only[:5]:
                            incomplete_work.append(f"  - {item['file']}:{item['line']} - {item['message'][:80]}")
            
            # Git uncommitted changes
            if "git_status" in project_context and project_context["git_status"]:
                git = project_context["git_status"]
                if git.get('modified_files') or git.get('untracked_files'):
                    incomplete_work.append("")
                    incomplete_work.append(f"Uncommitted Changes:")
                    incomplete_work.append(f"  - Branch: {git.get('branch', 'unknown')}")
                    if git.get('modified_files'):
                        incomplete_work.append(f"  - Modified: {', '.join(git['modified_files'][:3])}")
                    if git.get('untracked_files'):
                        incomplete_work.append(f"  - Untracked: {len(git['untracked_files'])} files")
            
            # Test coverage gaps (infer from file patterns)
            if "statistics" in project_context:
                stats = project_context["statistics"]
                code_files = stats.get('code_files', 0)
                
                # Look for test files
                file_types = stats.get('file_types', {})
                test_indicators = sum(
                    count for ext, count in file_types.items() 
                    if 'test' in ext.lower()
                )
                
                if code_files > 0 and test_indicators < code_files * 0.3:
                    incomplete_work.append("")
                    incomplete_work.append(f"Test Coverage:")
                    incomplete_work.append(f"  - Code Files: {code_files}")
                    incomplete_work.append(f"  - Test Files: ~{test_indicators}")
                    incomplete_work.append(f"  ⚠️  Appears to be under-tested")
            
            # Documentation gaps
            if "statistics" in project_context:
                stats = project_context["statistics"]
                code_files = stats.get('code_files', 0)
                doc_files = stats.get('doc_files', 0)
                
                if code_files > 5 and doc_files < 2:
                    incomplete_work.append("")
                    incomplete_work.append(f"Documentation:")
                    incomplete_work.append(f"  - Code Files: {code_files}")
                    incomplete_work.append(f"  - Doc Files: {doc_files}")
                    incomplete_work.append(f"  ⚠️  May need more documentation")
            
            prompt_parts.extend(incomplete_work)
            prompt_parts.append("")
        
        # Add additional context
        if additional_context:
            prompt_parts.extend([
                "Additional Context:",
                str(additional_context),
                ""
            ])
        
        # Instructions
        prompt_parts.extend([
            "Based on the workspace analysis and current state, generate 5 specific, actionable next steps.",
            "",
            "Prioritize steps that:",
            "1. Create productive output, materially advancing toward the goal",
            "2. Complete recently started work (recently modified files)",
            "3. Resolve outstanding issues from the board",
            "4. Fill identified gaps",
            "5. Address critical FIXMEs and high-priority TODOs"
            "",
            "DO NOT Prioritize steps that:",
            "1. Maintain documentation and test coverage",
            "2. Address non-critical TODOs or low-impact issues",
            "3. Perform general cleanup or refactoring without a clear output",
            "4. Do not advance the project toward the current focus",
            "",
            "Each step should be:",
            "- Concrete and actionable (reference specific files/lines when relevant)",
            "- Build on current progress",
            "- Address known issues or incomplete work",
            "- Achievable in the near term",
            "",
            "Respond with a JSON array of step strings."
        ])
        
        return "\n".join(prompt_parts)
    
    def _prioritize_steps(
        self,
        focus_manager,
        steps: list,
        project_context: Dict[str, Any]
    ) -> list:
        """Use LLM to prioritize steps with workspace context"""
        
        # Build context summary for prioritization
        context_summary = []
        
        if project_context.get("available"):
            if "todos" in project_context:
                todos = project_context["todos"]
                fixmes = [t for t in todos if t['type'] == 'FIXME']
                if fixmes:
                    context_summary.append(f"- {len(fixmes)} critical FIXMEs need attention")
            
            if "recent_changes" in project_context:
                changes = project_context["recent_changes"]
                if changes:
                    context_summary.append(f"- {len(changes)} files modified in last 24h")
            
            if "git_status" in project_context and project_context["git_status"]:
                git = project_context["git_status"]
                if git.get('modified_files'):
                    context_summary.append(f"- {len(git['modified_files'])} uncommitted changes")
        
        prompt = f"""
Project: {focus_manager.focus}

Workspace Context:
{chr(10).join(context_summary) if context_summary else "No specific context"}

Next Steps to Prioritize:
{json.dumps(steps, indent=2)}

Prioritize these steps based on:
1. **Urgency** - FIXMEs and critical issues first
2. **Impact** - Steps that unblock other work
3. **Continuity** - Complete recently started work
4. **Dependencies** - What must come first

Return the steps re-ordered by priority (highest first) as a JSON array.
"""
        
        try:
            response = self._stream_llm(focus_manager, focus_manager.agent.fast_llm, prompt, operation="prioritize_next_steps")
            prioritized = self._parse_json_response(response)
            return prioritized if prioritized else steps
        except Exception as e:
            self._stream_output(focus_manager, f"Could not prioritize steps: {e}", "warning")
            return steps
    
    def _parse_json_response(self, response: str) -> list:
        """Parse JSON response (for next steps - string arrays)"""
        cleaned = response.strip()
        
        # Remove markdown fences
        if cleaned.startswith('```'):
            lines = cleaned.split('\n')
            if lines[0].startswith('```'):
                lines = lines[1:]
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            cleaned = '\n'.join(lines)
        
        # Try JSON parse
        try:
            parsed = json.loads(cleaned)
            return parsed if isinstance(parsed, list) else [parsed]
        except:
            # Fallback: split by lines
            lines = [line.strip() for line in cleaned.split('\n') if line.strip()]
            return lines if lines else [response]