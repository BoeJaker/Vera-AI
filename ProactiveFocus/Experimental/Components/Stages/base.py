"""
Base Stage Interface
====================
Abstract base class for all proactive focus stages.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Iterator
from dataclasses import dataclass
from datetime import datetime


@dataclass
class StageOutput:
    """Standard output from stage execution"""
    insights: List[str]
    actions: List[str]
    ideas: List[str]
    next_steps: List[str]
    issues: List[str]
    artifacts: List[Dict[str, Any]]
    questions: List[Dict[str, Any]]
    tool_calls: List[Dict[str, Any]]
    memory_refs: List[str]
    metadata: Dict[str, Any]
    
    def __init__(self):
        self.insights = []
        self.actions = []
        self.ideas = []
        self.next_steps = []
        self.issues = []
        self.artifacts = []
        self.questions = []
        self.tool_calls = []
        self.memory_refs = []
        self.metadata = {}


class BaseStage(ABC):
    """
    Base class for all proactive focus stages.
    
    Provides common infrastructure for:
    - Focus board updates
    - Memory integration
    - Tool execution
    - Telegram notifications
    - Streaming output
    """
    
    def __init__(self, name: str, icon: str, description: str):
        self.name = name
        self.icon = icon
        self.description = description
    
    @abstractmethod
    def execute(self, focus_manager, context: Optional[Dict[str, Any]] = None) -> StageOutput:
        """
        Execute the stage.
        
        Args:
            focus_manager: ProactiveFocusManager instance
            context: Optional execution context
            
        Returns:
            StageOutput: Results from stage execution
        """
        pass
    
    def should_execute(self, focus_manager) -> bool:
        """
        Determine if this stage should execute.
        
        Default: Always execute. Override for conditional stages.
        """
        return True
    
    def _stream_output(self, focus_manager, message: str, level: str = "info"):
        """Stream output to focus manager"""
        if hasattr(focus_manager, '_stream_output'):
            focus_manager._stream_output(message, level)
        else:
            print(f"[{self.name}] {message}")
    
    def _stream_llm(self, focus_manager, llm, prompt: str) -> str:
        """Stream LLM response with thought broadcasting"""
        if hasattr(focus_manager, '_stream_llm_with_thought_broadcast'):
            response = ""
            for chunk in focus_manager._stream_llm_with_thought_broadcast(llm, prompt):
                response += chunk
            return response
        else:
            # Fallback to direct LLM call
            return llm.invoke(prompt)
    
    def _add_to_board(self, focus_manager, category: str, item: str, metadata: Optional[Dict] = None):
        """Add item to focus board"""
        if hasattr(focus_manager, 'add_to_focus_board'):
            focus_manager.add_to_focus_board(category, item, metadata=metadata)
    
    def _notify_telegram(self, focus_manager, message: str) -> bool:
        """
        Send Telegram notification if bot is available.
        
        Returns:
            bool: True if sent successfully
        """
        if hasattr(focus_manager, 'agent') and hasattr(focus_manager.agent, 'telegram_notify'):
            try:
                return focus_manager.agent.telegram_notify(message)
            except Exception as e:
                self._stream_output(focus_manager, f"Telegram notification failed: {e}", "warning")
                return False
        return False
    
    def _ask_telegram_question(
        self, 
        focus_manager, 
        question: str,
        timeout: int = 300,
        options: Optional[List[str]] = None
    ) -> Optional[str]:
        """
        Ask user a question via Telegram and wait for response.
        
        Args:
            focus_manager: ProactiveFocusManager instance
            question: Question to ask
            timeout: Max wait time in seconds (default: 5 min)
            options: Optional list of suggested responses
            
        Returns:
            str: User's response, or None if timeout/unavailable
        """
        if not hasattr(focus_manager, 'agent') or not hasattr(focus_manager.agent, 'telegram_bot'):
            self._stream_output(focus_manager, "Telegram bot not available for questions", "warning")
            return None
        
        telegram_bot = focus_manager.agent.telegram_bot
        
        # Format question with options
        formatted_question = f"❓ <b>{self.name} - Question</b>\n\n{question}"
        
        if options:
            formatted_question += "\n\n<b>Suggested responses:</b>\n"
            for idx, option in enumerate(options, 1):
                formatted_question += f"{idx}. {option}\n"
        
        formatted_question += "\n<i>Reply to this message with your answer.</i>"
        
        # Import required modules
        import asyncio
        import time
        
        # Create response queue
        response_queue = asyncio.Queue()
        response_received = asyncio.Event()
        
        async def send_and_wait():
            # Send question to all owners
            sent_count = await telegram_bot.send_to_owners(formatted_question)
            
            if sent_count == 0:
                return None
            
            # Wait for response with timeout
            try:
                # Store reference to question message
                question_id = f"question_{int(time.time())}"
                
                # Create a simple response handler
                # This is a simplified version - you might want to enhance this
                # with proper message tracking
                
                start_time = time.time()
                while time.time() - start_time < timeout:
                    # Check if we have a response
                    # This is where you'd integrate with your bot's message handling
                    # For now, we'll use a simple polling approach
                    
                    await asyncio.sleep(1)
                    
                    # In a real implementation, you'd check for new messages
                    # that reply to the question message
                    
                    # Placeholder: return None after timeout
                    pass
                
                return None
                
            except asyncio.TimeoutError:
                self._stream_output(focus_manager, "Question timeout - no response received", "warning")
                return None
        
        # Run async function
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        if loop.is_running():
            # Create task in existing loop
            future = asyncio.run_coroutine_threadsafe(send_and_wait(), loop)
            return future.result(timeout=timeout + 5)
        else:
            return loop.run_until_complete(send_and_wait())
    
    def _execute_tool(self, focus_manager, tool_name: str, tool_input: Any) -> Dict[str, Any]:
        """
        Execute a tool and return results.
        
        Returns:
            Dict with 'success', 'output', and optional 'error'
        """
        if not hasattr(focus_manager, 'agent'):
            return {"success": False, "error": "No agent available"}
        
        agent = focus_manager.agent
        
        # Find tool
        tool = None
        for t in agent.tools:
            if t.name == tool_name:
                tool = t
                break
        
        if not tool:
            return {"success": False, "error": f"Tool '{tool_name}' not found"}
        
        # Execute tool
        try:
            self._stream_output(focus_manager, f"Executing tool: {tool_name}", "info")
            
            if isinstance(tool_input, dict):
                output = tool.run(**tool_input)
            else:
                output = tool.run(tool_input)
            
            self._stream_output(focus_manager, f"Tool completed: {tool_name}", "success")
            
            return {
                "success": True,
                "output": output,
                "tool": tool_name,
                "input": tool_input
            }
            
        except Exception as e:
            self._stream_output(focus_manager, f"Tool error: {e}", "error")
            return {
                "success": False,
                "error": str(e),
                "tool": tool_name,
                "input": tool_input
            }
    
    def _save_artifact(
        self, 
        focus_manager, 
        artifact_type: str,
        content: str,
        filename: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Save an artifact to the project artifacts directory.
        
        Args:
            focus_manager: ProactiveFocusManager instance
            artifact_type: Type of artifact (e.g., 'document', 'code', 'diagram')
            content: Artifact content
            filename: Optional filename (auto-generated if None)
            metadata: Optional metadata
            
        Returns:
            Dict with artifact info
        """
        import os
        from datetime import datetime
        
        # Create artifacts directory
        project_id = getattr(focus_manager, 'project_id', 'unknown_project')
        artifacts_dir = os.path.join(
            os.path.dirname(getattr(focus_manager, 'focus_boards_dir', '.')),
            project_id,
            'artifacts'
        )
        
        try:
            os.makedirs(artifacts_dir, exist_ok=True)
        except OSError as e:
            self._stream_output(focus_manager, f"Failed to create artifacts dir: {e}", "error")
            return {"success": False, "error": str(e)}
        
        # Generate filename if not provided
        if not filename:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"{artifact_type}_{timestamp}.md"
        
        filepath = os.path.join(artifacts_dir, filename)
        
        # Save artifact
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self._stream_output(focus_manager, f"Artifact saved: {filepath}", "success")
            
            return {
                "success": True,
                "filepath": filepath,
                "filename": filename,
                "artifact_type": artifact_type,
                "size": len(content),
                "metadata": metadata or {}
            }
            
        except Exception as e:
            self._stream_output(focus_manager, f"Failed to save artifact: {e}", "error")
            return {"success": False, "error": str(e)}
    
    def _query_memory(self, focus_manager, query: str, limit: int = 5) -> List[Dict]:
        """Query hybrid memory system"""
        if not hasattr(focus_manager, 'hybrid_memory') or not focus_manager.hybrid_memory:
            return []
        
        try:
            # Use memory search
            results = focus_manager.hybrid_memory.search_related_context(
                query,
                limit=limit
            )
            return results
            
        except Exception as e:
            self._stream_output(focus_manager, f"Memory query error: {e}", "warning")
            return []
    
    def __repr__(self):
        return f"{self.icon} {self.name}: {self.description}"