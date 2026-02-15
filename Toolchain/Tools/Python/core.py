   
import traceback
from contextlib import redirect_stdout
from contextlib import contextmanager
from langchain_core.tools import StructuredTool
from Vera.Toolchain.schemas import PythonInput
from typing import List, Any
import sys
import io

def truncate_output(text: str, max_length: int = 5000) -> str:
    """Truncate long outputs with indication."""
    if len(text) > max_length:
        return text[:max_length] + f"\n... [truncated {len(text) - max_length} characters]"
    return text

@contextmanager
def redirect_stdout():
    """Context manager for safely redirecting stdout."""
    old_stdout = sys.stdout
    redirected_output = sys.stdout = io.StringIO()
    try:
        yield redirected_output
    finally:
        sys.stdout = old_stdout

class PythonTool:

    def __init__(self, agent):
        self.agent = agent
        self.name = "PythonTool"

    def run_python(self, code: str) -> str:
        """
        Execute Python code in a controlled environment.
        Use print() to output results. Both eval and exec are supported.
        """
        try:
            with redirect_stdout() as redirected_output:
                local_vars = {}
                
                try:
                    # Try eval first for expressions
                    result = eval(code, globals(), local_vars)
                    if result is not None:
                        print(result)
                except SyntaxError:
                    # Fall back to exec for statements
                    exec(code, globals(), local_vars)
                
                output = redirected_output.getvalue()
            
            # Add to memory
            m1 = self.agent.mem.upsert_entity(
                code, "python",
                labels=["Python"],
                properties={"language": "python", "priority": "high"}
            )
            m2 = self.agent.mem.add_session_memory(
                self.agent.sess.id, code, "Python",
                {"topic": "python_execution", "agent": "system"}
            )
            self.agent.mem.link(m1.id, m2.id, "Executed")
            
            if output:
                m3 = self.agent.mem.add_session_memory(
                    self.agent.sess.id, output, "PythonOutput",
                    {"topic": "python_result", "agent": "system"}
                )
                self.agent.mem.link(m1.id, m3.id, "Output")
            
            return truncate_output(output.strip() or "[No output]")
            
        except Exception as e:
            error_trace = traceback.format_exc()
            return f"[Python Error]\n{truncate_output(error_trace)}"

def add_python_tools(tool_list: List, agent) -> List:
    """
    Add Python execution tools to the tool list.

    Call this in ToolLoader():
    ```
    tool_list = add_python_tools(tool_list, self)
    ```
    """
    tools = PythonTool(agent)

    tool_list.extend(
        [
            StructuredTool.from_function(
                func=tools.run_python,
                name="python",
                description="Execute Python code. Use print() for output. Supports both expressions and statements.",
                args_schema=PythonInput
            )
        ]
    )