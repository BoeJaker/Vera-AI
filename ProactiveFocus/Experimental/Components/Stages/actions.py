"""
Actions Stage
=============
Generate executable actions/goals with proper metadata.
"""

import json
import re
from typing import Dict, Any, Optional, List
from Vera.ProactiveFocus.Experimental.Components.Stages.base import BaseStage, StageOutput


class ActionsStage(BaseStage):
    """Generate executable actions with tools and success criteria"""
    
    def __init__(self):
        super().__init__(
            name="Action Planning",
            icon="⚡",
            description="Create executable actions with clear success criteria"
        )
    
    def execute(self, focus_manager, context: Optional[Dict[str, Any]] = None) -> StageOutput:
        """Generate executable actions/goals"""
        output = StageOutput()
        
        self._stream_output(focus_manager, "Planning executable actions...", "info")
        
        # Get available tools
        available_tools = []
        if hasattr(focus_manager, 'agent') and hasattr(focus_manager.agent, 'tools'):
            available_tools = [tool.name for tool in focus_manager.agent.tools]
        
        # Build prompt
        prompt = f"""
Project: {focus_manager.focus}

Board State:
{json.dumps(focus_manager.board.get_all(), indent=2)}

Available Tools: {available_tools[:20]}  # Limit for context

{f"Context: {context}" if context else ""}

Generate 3-5 executable actions using available tools.

Each action should include:
- **description**: What to do (clear, actionable)
- **goal**: The desired outcome
- **priority**: high, medium, or low
- **success_criteria**: What a successful result looks like
- **tools**: Suggested tools to use (from available tools)
- **context**: Any additional context needed

Focus on actions that can actually be executed with the available tools.

Respond with JSON array of action objects:
[
  {{
    "description": "Action description",
    "goal": "Desired outcome",
    "priority": "high|medium|low",
    "success_criteria": "Success criteria",
    "tools": ["tool1", "tool2"],
    "context": "Additional context"
  }}
]
"""
        
        # Get LLM response
        try:
            response = self._stream_llm(focus_manager, focus_manager.agent.deep_llm, prompt)
            self._stream_output(focus_manager, "Actions generated", "success")
        except Exception as e:
            self._stream_output(focus_manager, f"Error: {str(e)}", "error")
            return output
        
        # Parse actions
        actions = self._parse_json_actions(response)
        
        self._stream_output(focus_manager, f"Generated {len(actions)} actions", "success")
        
        # Add to board and output
        for idx, action in enumerate(actions, 1):
            description = action.get("description", action.get("goal", str(action)))
            priority = action.get("priority", "medium")
            
            # Add to focus board with full metadata
            self._add_to_board(
                focus_manager,
                "actions",
                description,
                metadata=action
            )
            
            # Add to output
            output.actions.append(action)
            
            # Stream to console with priority indicator
            emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(priority, "⚪")
            self._stream_output(
                focus_manager,
                f"  {emoji} {idx}. {description[:100]}",
                "info"
            )
            
            # Show success criteria if present
            if action.get('success_criteria'):
                self._stream_output(
                    focus_manager,
                    f"      ✓ Success: {action['success_criteria'][:80]}",
                    "info"
                )
            
            # Show tools if present
            if action.get('tools'):
                tools_str = ", ".join(action['tools'][:3])
                self._stream_output(
                    focus_manager,
                    f"      🛠️  Tools: {tools_str}",
                    "info"
                )
        
        # Validate actions against available tools
        validation = self._validate_actions(focus_manager, actions, available_tools)
        if validation['warnings']:
            output.issues.extend(validation['warnings'])
            
            self._stream_output(focus_manager, "\n⚠️  Validation Warnings:", "warning")
            for warning in validation['warnings']:
                self._stream_output(focus_manager, f"  • {warning}", "warning")
        
        # Notify via Telegram
        if actions:
            summary = f"{self.icon} Action Plan Ready\n\n"
            
            # Group by priority
            high_priority = [a for a in actions if a.get('priority') == 'high']
            medium_priority = [a for a in actions if a.get('priority') == 'medium']
            low_priority = [a for a in actions if a.get('priority') == 'low']
            
            if high_priority:
                summary += f"🔴 High Priority ({len(high_priority)}):\n"
                for action in high_priority[:2]:
                    summary += f"  • {action.get('description', '')[:60]}...\n"
            
            if medium_priority:
                summary += f"\n🟡 Medium Priority ({len(medium_priority)}):\n"
                for action in medium_priority[:2]:
                    summary += f"  • {action.get('description', '')[:60]}...\n"
            
            if low_priority:
                summary += f"\n🟢 Low Priority ({len(low_priority)})"
            
            self._notify_telegram(focus_manager, summary)
        
        return output
    
    def _validate_actions(self, focus_manager, actions: List[Dict], available_tools: List[str]) -> Dict:
        """Validate actions against available tools"""
        warnings = []
        
        for idx, action in enumerate(actions, 1):
            # Check if suggested tools exist
            suggested_tools = action.get('tools', [])
            
            for tool in suggested_tools:
                if tool not in available_tools:
                    warnings.append(
                        f"Action {idx}: Tool '{tool}' not available"
                    )
            
            # Check if action has clear success criteria
            if not action.get('success_criteria'):
                warnings.append(
                    f"Action {idx}: Missing success criteria"
                )
            
            # Check if action has clear description or goal
            if not action.get('description') and not action.get('goal'):
                warnings.append(
                    f"Action {idx}: Missing description/goal"
                )
        
        return {
            'valid': len(warnings) == 0,
            'warnings': warnings
        }
    
    def _parse_json_actions(self, response: str) -> List[Dict]:
        """Parse JSON action objects from LLM response"""
        cleaned = response.strip()
        
        # Remove markdown fences
        if cleaned.startswith('```'):
            lines = cleaned.split('\n')
            if lines[0].startswith('```'):
                lines = lines[1:]
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            cleaned = '\n'.join(lines).strip()
        
        # Try direct JSON parse
        parsed = None
        try:
            parsed = json.loads(cleaned)
            if not isinstance(parsed, list):
                parsed = [parsed]
        except (json.JSONDecodeError, ValueError):
            # Try to extract JSON array
            array_match = re.search(r'\[[\s\S]*\]', cleaned)
            if array_match:
                try:
                    parsed = json.loads(array_match.group())
                    if not isinstance(parsed, list):
                        parsed = [parsed]
                except (json.JSONDecodeError, ValueError):
                    pass
        
        # Fallback: split by lines
        if parsed is None:
            lines = [l.strip() for l in cleaned.split('\n') 
                    if l.strip() and l.strip() not in '[]{}']
            parsed = lines if lines else [response[:500]]
        
        # Normalize to proper action dicts
        actions = []
        for item in parsed:
            if isinstance(item, dict):
                # Already a dict - normalize fields
                actions.append({
                    "description": item.get("description", item.get("goal", item.get("action", str(item)))),
                    "goal": item.get("goal", item.get("description", "")),
                    "tools": item.get("tools", []),
                    "priority": item.get("priority", "medium"),
                    "success_criteria": item.get("success_criteria", ""),
                    "context": item.get("context", "")
                })
            elif isinstance(item, str):
                # String - create minimal dict
                actions.append({
                    "description": item,
                    "goal": item,
                    "tools": [],
                    "priority": "medium",
                    "success_criteria": "",
                    "context": ""
                })
            else:
                # Unknown type - convert to string
                actions.append({
                    "description": str(item),
                    "goal": str(item),
                    "tools": [],
                    "priority": "medium",
                    "success_criteria": "",
                    "context": ""
                })
        
        # Fallback if nothing parsed
        if not actions:
            actions = [{
                "description": response[:500],
                "goal": response[:500],
                "tools": [],
                "priority": "medium",
                "success_criteria": "",
                "context": ""
            }]
        
        return actions