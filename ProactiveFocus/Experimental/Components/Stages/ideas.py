"""
Ideas Generation Stage - ENHANCED
==================================
Generate creative, actionable ideas with workspace awareness.

ENHANCED: Analyzes project files, recent changes, TODOs, and git status
to generate informed, context-aware ideas.
"""

import json
from typing import Dict, Any, Optional
from pathlib import Path
from Vera.ProactiveFocus.Experimental.Components.Stages.base import BaseStage, StageOutput
from Vera.Toolchain.sandbox import get_project_sandbox


class IdeasStage(BaseStage):
    """Generate creative ideas for advancing the current focus"""
    
    def __init__(self):
        super().__init__(
            name="Ideas Generation",
            icon="💡",
            description="Generate creative, actionable ideas to advance the project"
        )
    
    def execute(self, focus_manager, context: Optional[Dict[str, Any]] = None) -> StageOutput:
        """Generate ideas with full project context"""
        output = StageOutput()
        
        self._stream_output(focus_manager, f"Focus: {focus_manager.focus}", "info")
        self._stream_output(focus_manager, "Analyzing project workspace...", "info")
        
        # Get project context
        project_context = self._get_project_context(focus_manager)
        
        self._stream_output(focus_manager, "Generating context-aware ideas...", "info")
        
        # Build enriched prompt
        prompt = self._build_context_aware_prompt(focus_manager, project_context, context)
        
        # Get LLM response
        try:
            response = self._stream_llm(focus_manager, focus_manager.agent.deep_llm, prompt, operation="generate_ideas")
            self._stream_output(focus_manager, "Ideas generated", "success")
        except Exception as e:
            self._stream_output(focus_manager, f"Error: {str(e)}", "error")
            return output
        
        # Parse ideas
        ideas = self._parse_json_response(response)
        
        self._stream_output(focus_manager, f"Generated {len(ideas)} ideas", "success")
        
        # Add to board and output
        for idx, idea in enumerate(ideas, 1):
            # Add to focus board
            self._add_to_board(focus_manager, "ideas", idea)
            
            # Add to output
            output.ideas.append(idea)
            
            # Stream to console
            self._stream_output(
                focus_manager,
                f"  {idx}. {idea[:100]}{'...' if len(idea) > 100 else ''}",
                "info"
            )
        
        # Notify via Telegram if available
        if ideas:
            summary = f"{self.icon} Generated {len(ideas)} new ideas for: {focus_manager.focus}\n\n"
            summary += "\n".join(f"{i+1}. {idea[:80]}..." for i, idea in enumerate(ideas[:3]))
            if len(ideas) > 3:
                summary += f"\n...and {len(ideas) - 3} more"
            
            self._notify_telegram(focus_manager, summary)
        
        return output
    
    def _get_project_context(self, focus_manager) -> Dict[str, Any]:
        """Get project workspace context"""
        # Get project root from sandbox
        sandbox = get_project_sandbox(focus_manager)
        
        if not sandbox:
            return {"available": False}
        
        try:
            from Vera.ProactiveFocus.Experimental.Components.project_context_analyzer import ProjectContextAnalyzer
            
            project_root = Path(sandbox.project_root)
            analyzer = ProjectContextAnalyzer(project_root)
            
            # Get comprehensive context
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
        
        board_stats = focus_manager.board.get_stats()
        
        prompt_parts = [
            f"Project: {focus_manager.focus}",
            "",
            "Board State:",
            json.dumps(board_stats, indent=2),
            ""
        ]
        
        # Add project workspace context if available
        if project_context.get("available"):
            prompt_parts.extend([
                "WORKSPACE ANALYSIS:",
                ""
            ])
            
            # File statistics
            if "statistics" in project_context:
                stats = project_context["statistics"]
                prompt_parts.extend([
                    f"Project Statistics:",
                    f"- Total Files: {stats.get('total_files', 0)}",
                    f"- Total Lines of Code: {stats.get('total_lines', 0)}",
                    f"- Code Files: {stats.get('code_files', 0)}",
                    f"- Documentation Files: {stats.get('doc_files', 0)}",
                    ""
                ])
                
                if stats.get('file_types'):
                    file_types = stats['file_types']
                    # Show top 5 file types
                    sorted_types = sorted(file_types.items(), key=lambda x: x[1], reverse=True)
                    prompt_parts.append("Top File Types:")
                    for ext, count in sorted_types[:5]:
                        prompt_parts.append(f"  - {ext or 'no extension'}: {count} files")
                    prompt_parts.append("")
            
            # Recent changes
            if "recent_changes" in project_context:
                changes = project_context["recent_changes"]
                if changes:
                    prompt_parts.extend([
                        f"Recent Changes (last 24h): {len(changes)} files modified",
                        ""
                    ])
                    # Show most recent 5
                    for change in changes[:5]:
                        age = change['age_hours']
                        age_str = f"{age:.1f}h ago" if age < 24 else f"{age/24:.1f}d ago"
                        prompt_parts.append(f"  - {change['path']} ({age_str})")
                    prompt_parts.append("")
            
            # TODOs and FIXMEs
            if "todos" in project_context:
                todos = project_context["todos"]
                if todos:
                    prompt_parts.extend([
                        f"Outstanding TODOs/FIXMEs: {len(todos)}",
                        ""
                    ])
                    # Group by type
                    todo_by_type = {}
                    for todo in todos:
                        todo_type = todo['type']
                        if todo_type not in todo_by_type:
                            todo_by_type[todo_type] = []
                        todo_by_type[todo_type].append(todo)
                    
                    for todo_type, items in todo_by_type.items():
                        prompt_parts.append(f"{todo_type}s ({len(items)}):")
                        for item in items[:3]:
                            prompt_parts.append(f"  - {item['message']} ({item['file']}:{item['line']})")
                        if len(items) > 3:
                            prompt_parts.append(f"  ... and {len(items) - 3} more")
                        prompt_parts.append("")
            
            # Git status
            if "git_status" in project_context and project_context["git_status"]:
                git = project_context["git_status"]
                prompt_parts.extend([
                    f"Git Status:",
                    f"- Branch: {git.get('branch', 'unknown')}",
                    f"- Modified Files: {len(git.get('modified_files', []))}",
                    f"- Untracked Files: {len(git.get('untracked_files', []))}",
                    ""
                ])
        
        # Add additional context if provided
        if additional_context:
            prompt_parts.extend([
                "Additional Context:",
                str(additional_context),
                ""
            ])
        
        # Add instructions
        prompt_parts.extend([
            "Based on the above workspace analysis and project state, generate 5 creative, actionable ideas to advance this project.",
            "",
            "Consider:",
            "1. Files that were recently modified (might need follow-up work)",
            "2. Outstanding TODOs/FIXMEs that should be addressed",
            "3. Missing files or structure gaps identified in the analysis",
            "4. Opportunities to improve code organization or documentation",
            "5. Uncommitted changes that might need attention",
            "",
            "Focus on practical solutions and innovative approaches that are grounded in the actual project state.",
            "",
            "Respond with a JSON array of idea strings.",
            "Each idea should reference specific files or TODOs where relevant."
        ])
        
        return "\n".join(prompt_parts)
    
    def _parse_json_response(self, response: str) -> list:
        """Parse JSON response (for ideas - string arrays)"""
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