    
# ------------------------------------------------------------------------
# GIT TOOLS
# ------------------------------------------------------------------------

from langchain_core.tools import StructuredTool
from Vera.Toolchain.schemas import GitInput
import subprocess
import os
from typing import List, Any

def sanitize_path(path: str) -> str:
    """Sanitize and validate file paths."""
    path = os.path.normpath(path)
    if path.startswith('..'):
        raise ValueError("Path traversal not allowed")
    return path


def format_json(data: Any) -> str:
    """Format data as pretty JSON."""
    try:
        return json.dumps(data, indent=2, default=str)
    except:
        return str(data)


def truncate_output(text: str, max_length: int = 5000) -> str:
    """Truncate long outputs with indication."""
    if len(text) > max_length:
        return text[:max_length] + f"\n... [truncated {len(text) - max_length} characters]"
    return text


class GitTool:

    def __init__(self, agent):
        self.agent = agent
        self.name = "GitTool"

    def git_operation(self, repo_path: str = ".", command: str = "status", args: str = "") -> str:
        """
        Execute git commands in a repository.
        Supports: status, log, diff, branch, add, commit, push, pull, etc.
        """
        try:
            repo_path = sanitize_path(repo_path)
            
            full_command = f"git -C {repo_path} {command} {args}"
            
            result = subprocess.check_output(
                full_command,
                shell=True,
                text=True,
                stderr=subprocess.STDOUT,
                timeout=30
            )
            
            return truncate_output(result)
            
        except subprocess.CalledProcessError as e:
            return f"[Git Error] {e.output}"
        except Exception as e:
            return f"[Git Error] {str(e)}"
        
def add_git_tools(tool_list: List, agent) -> List:  
    """
    Add Git tools to the tool list.

    Call this in ToolLoader():
    ```
    tool_list = add_git_tools(tool_list, self)
    ```
    """
    tools = GitTool(agent)

    tool_list.extend(
        [
        # Git Tools
        StructuredTool.from_function(
            func=tools.git_operation,
            name="git",
            description="Execute git commands: status, log, diff, branch, add, commit, push, pull.",
            args_schema=GitInput
        ),
        ]
    )
