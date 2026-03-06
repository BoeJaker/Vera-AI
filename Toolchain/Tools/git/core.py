# git_tools.py — FIXED VERSION
"""
Git tools with sandbox-aware path resolution.

Uses SandboxEnforcer (path validation) approach, NOT runtime_sandbox containers.
This keeps git operations consistent with filesystem/bash tools.

The sandbox ensures:
- repo_path resolves within the project root
- args containing absolute paths are validated
- No operations outside the project boundary
"""

from langchain_core.tools import StructuredTool
from Vera.Toolchain.schemas import GitInput
import subprocess
import os
import json
from typing import List, Any, Optional
from pathlib import Path


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

    def _resolve_repo_path(self, repo_path: str = ".") -> str:
        """
        Resolve repo_path to an actual directory.
        
        If repo_path is relative, it stays relative (will use cwd).
        If absolute, validate it exists.
        Sanitizes against path traversal.
        """
        repo_path = sanitize_path(repo_path)
        
        if os.path.isabs(repo_path):
            if not os.path.isdir(repo_path):
                raise ValueError(f"Repository path does not exist: {repo_path}")
            return repo_path
        
        # For relative paths, resolve against cwd
        resolved = os.path.abspath(repo_path)
        if not os.path.isdir(resolved):
            raise ValueError(f"Repository path does not exist: {resolved}")
        return resolved

    def git_operation(self, repo_path: str = ".", command: str = "status", args: str = "") -> str:
        """
        Execute git commands in a repository.
        
        When sandboxed (via SandboxEnforcer.wrap_tools), repo_path is
        validated to be within the project root automatically.
        
        Args:
            repo_path: Path to git repository (default: current directory)
            command: Git command (status, log, diff, add, commit, etc.)
            args: Additional arguments for the command
        
        Returns:
            Command output or error message
        """
        try:
            resolved = self._resolve_repo_path(repo_path)
            
            # Build and execute git command
            # Use -C to set the repo directory so git finds .git
            full_command = f"git -C '{resolved}' {command} {args}"
            
            result = subprocess.run(
                full_command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            output = result.stdout
            if result.stderr:
                # Git sends some normal output to stderr (e.g., progress)
                # Only prepend if there's an actual error
                if result.returncode != 0:
                    output = result.stderr + "\n" + output
                else:
                    # Append stderr info (like branch tracking) but don't alarm
                    output = output + result.stderr
            
            if result.returncode != 0 and not output.strip():
                output = f"[Git] Command exited with code {result.returncode}"
            
            return truncate_output(output.strip())
            
        except ValueError as e:
            return f"[Git Error] {str(e)}"
        except subprocess.TimeoutExpired:
            return f"[Git Error] Command timed out after 30 seconds"
        except subprocess.CalledProcessError as e:
            return f"[Git Error] {e.output}"
        except Exception as e:
            return f"[Git Error] {str(e)}"


def add_git_tools(tool_list: List, agent) -> List:  
    """
    Add Git tools to the tool list.
    
    When used with SandboxEnforcer.wrap_tools(), the repo_path parameter
    is automatically validated against the project sandbox boundary.

    Call this in ToolLoader():
    ```
    tool_list = add_git_tools(tool_list, agent)
    ```
    """
    tools = GitTool(agent)

    tool_list.extend([
        StructuredTool.from_function(
            func=tools.git_operation,
            name="git",
            description=(
                "Execute git commands in the project repository."
                "\n\nCommon commands:"
                "\n- git(command='status') - Show working tree status"
                "\n- git(command='log', args='--oneline -5') - Show recent commits"
                "\n- git(command='diff') - Show unstaged changes"
                "\n- git(command='add', args='file.py') - Stage file"
                "\n- git(command='commit', args='-m \"message\"') - Commit changes"
                "\n- git(command='branch') - List branches"
                "\n- git(command='pull') - Pull from remote"
            ),
            args_schema=GitInput
        ),
    ])
    
    return tool_list