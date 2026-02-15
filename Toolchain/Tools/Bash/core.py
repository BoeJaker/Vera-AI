
import os
import subprocess
from typing import Optional
from contextlib import contextmanager
from langchain_core.tools import StructuredTool
from Vera.Toolchain.schemas import CommandInput
import sys
import io

def sanitize_path(path: str) -> str:
    """Sanitize and validate file paths."""
    path = os.path.normpath(path)
    if path.startswith('..'):
        raise ValueError("Path traversal not allowed")
    return path

@contextmanager
def redirect_stdout():
    """Context manager for safely redirecting stdout."""
    old_stdout = sys.stdout
    redirected_output = sys.stdout = io.StringIO()
    try:
        yield redirected_output
    finally:
        sys.stdout = old_stdout

class BashTool:
    def __init__(self, agent):
        self.agent = agent
        self.name = "BashTool"

    def run_bash_command(self, command: str, working_dir: Optional[str] = None) -> str:
        """
        Execute a bash shell command and return output.
        Warning: Use with caution. Commands have full system access.
        Args:
            command: The bash command to execute.
            working_dir: The directory in which to execute the command. Defaults to None (current directory).
        """
        try:
            # Sanitize and validate the working directory if provided
            if working_dir:
                working_dir = sanitize_path(working_dir)
                if not os.path.isdir(working_dir):
                    return f"[Error] Invalid working directory: {working_dir}"

            result = subprocess.check_output(
                command,
                shell=True,
                text=True,
                stderr=subprocess.STDOUT,
                timeout=30,  # 30 second timeout
                cwd=working_dir  # Set the working directory
            )
            
            # Add to memory
            m1 = self.agent.mem.upsert_entity(
                command, "command",
                labels=["Command"],
                properties={"shell": "bash", "priority": "high", "working_dir": working_dir or "current"}
            )
            m2 = self.agent.mem.add_session_memory(
                self.agent.sess.id, command, "Command",
                {"topic": "bash_command", "agent": "system", "working_dir": working_dir or "current"}
            )
            self.agent.mem.link(m1.id, m2.id, "Executed")
            
            m3 = self.agent.mem.add_session_memory(
                self.agent.sess.id, result, "CommandOutput",
                {"topic": "bash_output", "agent": "system"}
            )
            self.agent.mem.link(m1.id, m3.id, "Output")
            
            return truncate_output(result)
            
        except subprocess.TimeoutExpired:
            return "[Error] Command timed out after 30 seconds"
        except subprocess.CalledProcessError as e:
            return f"[Error] Command failed with exit code {e.returncode}\n{e.output}"
        except Exception as e:
            return f"[Error] Failed to execute command: {str(e)}"


def add_bash_tools(tool_list: list, agent) -> list:
    """
    Add bash command execution tools to the tool list.

    Call this in ToolLoader():
    ```
    tool_list = add_bash_tools(tool_list, self)
    ```
    """
    tools = BashTool(agent)

    tool_list.extend(
        [

            StructuredTool.from_function(
                func=tools.run_bash_command,
                name="bash",
                description="Execute bash command. Returns command output. Use with caution.",
                args_schema=CommandInput
            )
        ]
    )

    return tool_list