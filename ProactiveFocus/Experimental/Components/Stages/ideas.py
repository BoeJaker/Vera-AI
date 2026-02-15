"""
Ideas Generation Stage
======================
Generate creative, actionable ideas to advance the project.
"""

import json
from typing import Dict, Any, Optional
from Vera.ProactiveFocus.Experimental.Components.Stages.base import BaseStage, StageOutput


class IdeasStage(BaseStage):
    """Generate creative ideas for advancing the current focus"""
    
    def __init__(self):
        super().__init__(
            name="Ideas Generation",
            icon="💡",
            description="Generate creative, actionable ideas to advance the project"
        )
    
    def execute(self, focus_manager, context: Optional[Dict[str, Any]] = None) -> StageOutput:
        """Generate ideas with full graph integration"""
        output = StageOutput()
        
        self._stream_output(focus_manager, f"Focus: {focus_manager.focus}", "info")
        self._stream_output(focus_manager, "Generating ideas...", "info")
        
        # Build prompt
        prompt = f"""
Project: {focus_manager.focus}

Current State:
{json.dumps(focus_manager.board.get_stats(), indent=2)}

{f"Context: {context}" if context else ""}

Generate 5 creative, actionable ideas to advance this project.
Focus on practical solutions and innovative approaches.
Respond with a JSON array of idea strings.
"""
        
        # Get LLM response
        try:
            response = self._stream_llm(focus_manager, focus_manager.agent.deep_llm, prompt)
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