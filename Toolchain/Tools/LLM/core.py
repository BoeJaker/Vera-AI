# ------------------------------------------------------------------------
# LLM INTERACTION TOOLS
# ------------------------------------------------------------------------

from langchain_core.tools import StructuredTool
from Vera.Toolchain.schemas import LLMQueryInput
from typing import List

class LLMTool:
    """Tool for interacting with LLMs: fast queries for quick tasks and deep queries for
    complex reasoning."""

    def __init__(self, agent):
        self.agent = agent
        self.name = "LLMTool"

    def fast_llm_query(self, query: str) -> str:
        """
        Query a fast LLM for quick tasks like summarization, simple analysis.
        Best for: creative writing, text review, summarization, combining text.
        Note: Fast but can be less accurate than deep LLM.
        """
        try:
            result = ""
            use_orchestrator = hasattr(self.agent, 'orchestrator') and self.agent.orchestrator and self.agent.orchestrator.running
            
            if use_orchestrator:
                try:
                    # Use orchestrator for task execution
                    task_id = self.agent.orchestrator.submit_task(
                        "llm.fast",
                        vera_instance=self.agent,
                        prompt=query
                    )
                    
                    for chunk in self.agent.orchestrator.stream_result(task_id, timeout=30.0):
                        chunk_text = chunk if isinstance(chunk, str) else str(chunk)
                        result += chunk_text
                
                except Exception as e:
                    # Fallback to direct LLM call
                    for chunk in self.agent.stream_llm_with_memory(
                        self.agent.fast_llm, query, long_term=False, short_term=True
                    ):
                        text = chunk if isinstance(chunk, str) else str(chunk)
                        result += text
            else:
                # No orchestrator - direct call
                for chunk in self.agent.stream_llm_with_memory(
                    self.agent.fast_llm, query, long_term=False, short_term=True
                ):
                    text = chunk if isinstance(chunk, str) else str(chunk)
                    result += text
            
            # Store in memory
            self.agent.mem.add_session_memory(
                self.agent.sess.id, result, "Answer", 
                {"topic": "fast_llm", "agent": self.agent.selected_models.fast_llm}  # Changed to attribute access
            )
            return result
        except Exception as e:
            return f"[Fast LLM Error] {str(e)}"

    def deep_llm_query(self, query: str) -> str:
        """
        Query a deep LLM for complex reasoning and detailed analysis.
        Best for: complex reasoning, detailed analysis, accuracy-critical tasks.
        Note: Slower but more accurate than fast LLM.
        """
        try:
            result = ""
            use_orchestrator = hasattr(self.agent, 'orchestrator') and self.agent.orchestrator and self.agent.orchestrator.running
            
            if use_orchestrator:
                try:
                    # Use orchestrator for task execution
                    task_id = self.agent.orchestrator.submit_task(
                        "llm.deep",
                        vera_instance=self.agent,
                        prompt=query
                    )
                    
                    for chunk in self.agent.orchestrator.stream_result(task_id, timeout=60.0):
                        chunk_text = chunk if isinstance(chunk, str) else str(chunk)
                        result += chunk_text
                
                except Exception as e:
                    # Fallback to direct LLM call
                    for chunk in self.agent.stream_llm_with_memory(
                        self.agent.deep_llm, query, long_term=True, short_term=True
                    ):
                        text = chunk if isinstance(chunk, str) else str(chunk)
                        result += text
            else:
                # No orchestrator - direct call
                for chunk in self.agent.stream_llm_with_memory(
                    self.agent.deep_llm, query, long_term=True, short_term=True
                ):
                    text = chunk if isinstance(chunk, str) else str(chunk)
                    result += text
            
            # Store in memory
            self.agent.mem.add_session_memory(
                self.agent.sess.id, result, "Answer",
                {"topic": "deep_llm", "agent": self.agent.selected_models.deep_llm}  # Changed to attribute access
            )
            return result
        except Exception as e:
            return f"[Deep LLM Error] {str(e)}"

def add_llm_tools(tool_list: List, agent) -> List:
    """
    Add LLM interaction tools to the tool list.

    Call this in ToolLoader():
    ```
    tool_list = add_llm_tools(tool_list, self)
    ```
    """
    tools = LLMTool(agent)

    tool_list.extend(
        [
            StructuredTool.from_function(
                func=tools.fast_llm_query,
                name="fast_llm",
                description=(
                    "Query a fast LLM for quick tasks like summarization, simple analysis. "
                    "Best for: creative writing, text review, summarization, combining text. "
                    "Note: Fast but can be less accurate than deep LLM."
                ),
                args_schema=LLMQueryInput
            ),
            StructuredTool.from_function(
                func=tools.deep_llm_query,
                name="deep_llm",
                description=(
                    "Query a deep LLM for complex reasoning and detailed analysis. "
                    "Best for: complex reasoning, detailed analysis, accuracy-critical tasks. "
                    "Note: Slower but more accurate than fast LLM."
                ),
                args_schema=LLMQueryInput
            )
        ]
    )

    return tool_list
 