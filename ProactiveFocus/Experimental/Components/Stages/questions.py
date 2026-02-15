"""
Questions Stage - Enhanced with Integrated Bot Support
======================================================
Ask clarifying questions to the user about the current goal.
Uses Telegram bot that's initialized with Vera.
"""

import json
from typing import Dict, Any, Optional, List
from Vera.ProactiveFocus.Experimental.Components.Stages.base import BaseStage, StageOutput


class QuestionsStage(BaseStage):
    """Ask clarifying questions to better understand the goal"""
    
    def __init__(self):
        super().__init__(
            name="Questions & Clarification",
            icon="❓",
            description="Ask clarifying questions to better understand the goal"
        )
    
    def should_execute(self, focus_manager) -> bool:
        """
        Only execute if Telegram bot is available and goal seems unclear
        
        Now checks vera.telegram_bot instead of searching for it
        """
        # Check if Telegram is available via Vera instance
        if not hasattr(focus_manager, 'agent'):
            return False
        
        vera = focus_manager.agent
        
        # Check if bot is initialized
        if not hasattr(vera, 'telegram_bot') or not vera.telegram_bot:
            self._stream_output(
                focus_manager,
                "Telegram bot not available - enable in vera_config.yaml",
                "warning"
            )
            return False
        
        # Check if we need clarification
        board_state = focus_manager.board.get_all()
        
        # Execute if:
        # - Few issues logged (might need clarification)
        # - Many ideas but few actions (need to narrow focus)
        # - Recent progress is unclear
        
        issues = len(board_state.get('issues', []))
        ideas = len(board_state.get('ideas', []))
        actions = len(board_state.get('actions', []))
        
        return issues > 0 or (ideas > 5 and actions < 2)
    
    def execute(self, focus_manager, context: Optional[Dict[str, Any]] = None) -> StageOutput:
        """Generate and ask clarifying questions"""
        output = StageOutput()
        
        # Access Vera instance
        vera = focus_manager.agent
        telegram = vera.telegram_bot
        
        self._stream_output(focus_manager, "Analyzing current understanding...", "info")
        
        # Generate questions using LLM
        questions = self._generate_questions(focus_manager)
        
        if not questions:
            self._stream_output(focus_manager, "No questions needed at this time", "info")
            return output
        
        self._stream_output(focus_manager, f"Generated {len(questions)} questions", "success")
        
        # Notify start of Q&A session
        import asyncio
        loop = asyncio.get_event_loop()
        
        session_intro = f"{self.icon} Starting Q&A Session\n\n"
        session_intro += f"Focus: {focus_manager.focus}\n"
        session_intro += f"Questions: {len(questions)}\n\n"
        session_intro += "Please respond to each question..."
        
        loop.run_until_complete(telegram.send_to_owners(session_intro))
        
        # Ask each question via Telegram
        for idx, question_data in enumerate(questions, 1):
            question_text = question_data['question']
            
            self._stream_output(
                focus_manager,
                f"Question {idx}/{len(questions)}: {question_text}",
                "info"
            )
            
            # Format question for Telegram
            tg_message = f"❓ Question {idx}/{len(questions)}\n\n"
            tg_message += f"{question_text}\n\n"
            
            # Add options if available
            if question_data.get('options'):
                tg_message += "Suggested options:\n"
                for opt_idx, option in enumerate(question_data['options'], 1):
                    tg_message += f"{opt_idx}. {option}\n"
                tg_message += "\nOr provide your own answer..."
            
            # Send question
            loop.run_until_complete(telegram.send_to_owners(tg_message))
            
            # Wait for response
            response = self._wait_for_telegram_response(
                focus_manager,
                telegram,
                timeout=300  # 5 minutes
            )
            
            # Store question and response
            question_record = {
                "question": question_data['question'],
                "category": question_data.get('category', 'general'),
                "response": response,
                "timestamp": self._get_timestamp()
            }
            
            output.questions.append(question_record)
            
            if response:
                self._stream_output(
                    focus_manager,
                    f"Response received: {response[:100]}...",
                    "success"
                )
                
                # Add to focus board
                self._add_to_board(
                    focus_manager,
                    "progress",
                    f"[Q&A] {question_data['question'][:50]}... → {response[:50]}...",
                    metadata=question_record
                )
                
                # Process response
                self._process_response(focus_manager, question_data, response, output)
                
                # Acknowledge via Telegram
                ack = f"✓ Answer recorded:\n{response[:200]}"
                if len(response) > 200:
                    ack += "..."
                loop.run_until_complete(telegram.send_to_owners(ack))
                
            else:
                self._stream_output(
                    focus_manager,
                    "No response received (timeout)",
                    "warning"
                )
                
                # Add to issues
                self._add_to_board(
                    focus_manager,
                    "issues",
                    f"Unanswered question: {question_data['question'][:80]}..."
                )
        
        # Summary notification
        answered = sum(1 for q in output.questions if q.get('response'))
        summary = f"{self.icon} Q&A Session Complete\n\n"
        summary += f"Asked {len(questions)} questions\n"
        summary += f"Received {answered} responses\n\n"
        
        if answered > 0:
            summary += "Key insights:\n"
            for insight in output.insights[:3]:
                summary += f"• {insight[:80]}...\n"
        
        loop.run_until_complete(telegram.send_to_owners(summary))
        
        return output
    
    def _wait_for_telegram_response(
        self,
        focus_manager,
        telegram,
        timeout: int = 300
    ) -> Optional[str]:
        """
        Wait for user response via Telegram
        
        This is a simplified implementation - in production you'd want:
        1. Message queue/handler in TelegramBot
        2. Proper async/await handling
        3. User session tracking
        """
        import asyncio
        import time
        
        # Get owner IDs
        from Vera.ChatBots.telegram_bot import SecurityConfig
        owner_ids = SecurityConfig.OWNERS
        
        if not owner_ids:
            self._stream_output(focus_manager, "No Telegram owners configured", "error")
            return None
        
        # Wait for response with polling
        # In production, this should use proper message handlers
        start_time = time.time()
        
        self._stream_output(
            focus_manager,
            f"Waiting for Telegram response (timeout: {timeout}s)...",
            "info"
        )
        
        # Simple polling approach (replace with proper message handler)
        while time.time() - start_time < timeout:
            # Check if telegram bot has any pending messages
            # This is a placeholder - implement proper message queue
            
            # For now, just wait and return None (implement properly)
            time.sleep(5)
            
            # TODO: Implement actual message retrieval
            # response = telegram.get_latest_message_from_owner()
            # if response:
            #     return response
        
        return None  # Timeout
    
    def _generate_questions(self, focus_manager) -> List[Dict[str, Any]]:
        """Generate relevant questions using LLM"""
        
        board_state = focus_manager.board.get_all()
        
        prompt = f"""
Project Focus: {focus_manager.focus}

Current Board State:
{json.dumps(board_state, indent=2)}

Analyze the current state and generate 2-3 clarifying questions that would help:
1. Better understand the goal
2. Identify priorities
3. Resolve ambiguities
4. Gather missing requirements

For each question, also suggest 2-3 possible answer options if applicable.

Respond with JSON array of objects with this structure:
[
  {{
    "question": "The question to ask",
    "category": "goal|priority|requirement|constraint",
    "options": ["Option 1", "Option 2", "Option 3"]  // optional
  }}
]

Focus on high-value questions that will significantly improve project direction.
"""
        
        try:
            response = self._stream_llm(focus_manager, focus_manager.agent.deep_llm, prompt)
            
            # Parse JSON response
            questions = self._parse_json_response(response)
            
            # Validate structure
            validated = []
            for q in questions:
                if isinstance(q, dict) and 'question' in q:
                    validated.append({
                        'question': q['question'],
                        'category': q.get('category', 'general'),
                        'options': q.get('options', [])
                    })
                elif isinstance(q, str):
                    validated.append({
                        'question': q,
                        'category': 'general',
                        'options': []
                    })
            
            return validated[:3]  # Max 3 questions
            
        except Exception as e:
            self._stream_output(focus_manager, f"Failed to generate questions: {e}", "error")
            return []
    
    def _process_response(
        self,
        focus_manager,
        question_data: Dict,
        response: str,
        output: StageOutput
    ):
        """Process user response and extract actionable items"""
        
        category = question_data.get('category', 'general')
        
        # Add insights based on category
        if category == 'goal':
            output.insights.append(f"Goal clarification: {response[:100]}")
            
        elif category == 'priority':
            output.next_steps.append(f"Priority identified: {response[:100]}")
            
        elif category == 'requirement':
            output.actions.append({
                "description": f"Address requirement: {response[:100]}",
                "priority": "high",
                "success_criteria": "Requirement met based on user input"
            })
        
        # Use LLM to extract actionable items from response
        extraction_prompt = f"""
Question: {question_data['question']}
User Response: {response}

Extract any actionable items, insights, or next steps from this response.
Respond with JSON:
{{
  "insights": ["insight 1", "insight 2"],
  "actions": ["action 1", "action 2"],
  "next_steps": ["step 1", "step 2"]
}}
"""
        
        try:
            extraction = self._stream_llm(focus_manager, focus_manager.agent.fast_llm, extraction_prompt)
            parsed = self._parse_json_response(extraction)
            
            if isinstance(parsed, dict):
                output.insights.extend(parsed.get('insights', []))
                
                for action in parsed.get('actions', []):
                    if isinstance(action, str):
                        output.actions.append({
                            "description": action,
                            "priority": "medium",
                            "context": f"From user response to: {question_data['question'][:50]}..."
                        })
                    else:
                        output.actions.append(action)
                
                output.next_steps.extend(parsed.get('next_steps', []))
                
        except Exception as e:
            self._stream_output(focus_manager, f"Failed to extract actionable items: {e}", "warning")
    
    def _parse_json_response(self, response: str):
        """Parse JSON response with fallbacks"""
        cleaned = response.strip()
        
        # Remove markdown fences
        if cleaned.startswith('```'):
            lines = cleaned.split('\n')
            if lines[0].startswith('```'):
                lines = lines[1:]
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            cleaned = '\n'.join(lines)
        
        try:
            return json.loads(cleaned)
        except:
            return []
    
    def _get_timestamp(self) -> str:
        """Get current timestamp"""
        from datetime import datetime
        return datetime.utcnow().isoformat()


# Example usage in ProactiveFocusManager:
"""
# In your ProactiveFocusManager or stage orchestrator:

def run_questions_stage(self):
    stage = QuestionsStage()
    
    # Check if should execute
    if not stage.should_execute(self):
        print("Questions stage skipped - Telegram not available or not needed")
        return
    
    # Execute stage
    output = stage.execute(self)
    
    # Process results
    for question_record in output.questions:
        print(f"Q: {question_record['question']}")
        print(f"A: {question_record['response']}")
    
    for insight in output.insights:
        print(f"Insight: {insight}")
    
    for action in output.actions:
        print(f"Action: {action['description']}")
"""