"""
Next Steps Stage
================
Generate actionable next steps based on current progress and issues.
"""

import json
from typing import Dict, Any, Optional
from Vera.ProactiveFocus.Experimental.Components.Stages.base import BaseStage, StageOutput


class NextStepsStage(BaseStage):
    """Generate specific, actionable next steps"""
    
    def __init__(self):
        super().__init__(
            name="Next Steps",
            icon="🎯",
            description="Determine actionable next steps"
        )
    
    def execute(self, focus_manager, context: Optional[Dict[str, Any]] = None) -> StageOutput:
        """Generate next steps with context awareness"""
        output = StageOutput()
        
        self._stream_output(focus_manager, "Analyzing current state...", "info")
        self._stream_output(focus_manager, "Determining next steps...", "info")
        
        # Build prompt with rich context
        prompt = f"""
Project: {focus_manager.focus}

Current State:
- Progress: {json.dumps(focus_manager.board.get_category('progress')[-5:], indent=2)}
- Issues: {json.dumps(focus_manager.board.get_category('issues'), indent=2)}
- Ideas: {json.dumps(focus_manager.board.get_category('ideas'), indent=2)}
- Actions: {json.dumps(focus_manager.board.get_category('actions'), indent=2)}

{f"Context: {context}" if context else ""}

Generate 5 specific, actionable next steps to advance this project.
Consider current progress, outstanding issues, and available ideas.
Each step should be:
1. Concrete and actionable
2. Build on current progress
3. Address known issues
4. Be achievable in the near term

Respond with a JSON array of step strings.
"""
        
        # Get LLM response
        try:
            response = self._stream_llm(focus_manager, focus_manager.agent.deep_llm, prompt)
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
            priority_steps = self._prioritize_steps(focus_manager, steps)
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
    
    def _prioritize_steps(self, focus_manager, steps: list) -> list:
        """Use LLM to prioritize steps"""
        
        prompt = f"""
Project: {focus_manager.focus}

Next Steps:
{json.dumps(steps, indent=2)}

Prioritize these steps based on:
1. Impact on project progress
2. Urgency and time-sensitivity
3. Dependencies (what must come first)
4. Resource availability

Return the steps re-ordered by priority (highest first) as a JSON array.
"""
        
        try:
            response = self._stream_llm(focus_manager, focus_manager.agent.fast_llm, prompt)
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