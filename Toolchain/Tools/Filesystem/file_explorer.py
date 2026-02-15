#!/usr/bin/env python3
"""
LangChain File System Navigation Tool
Author: Elite Programmer
Description: A secure tool for AI agents to navigate and interact with file systems.
"""

import os
import shutil
import stat
import fnmatch
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
import logging
from dataclasses import dataclass
from langchain.tools import BaseTool
from langchain.agents import Tool
from langchain.schema import SystemMessage
from pydantic import BaseModel, Field, validator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('FileSystemTool')

class FileOperation(Enum):
    LIST = "list"
    READ = "read"
    WRITE = "write"
    CREATE = "create"
    DELETE = "delete"
    MOVE = "move"
    COPY = "copy"
    SEARCH = "search"
    STAT = "stat"

@dataclass
class FileSystemRestrictions:
    allowed_directories: List[str]
    blocked_directories: List[str]
    allowed_file_extensions: List[str]
    blocked_file_extensions: List[str]
    max_file_size: int = 10 * 1024 * 1024  # 10MB default
    allow_recursive: bool = False
    allow_hidden_files: bool = False

class FileSystemNavigator:
    def __init__(self, restrictions: FileSystemRestrictions):
        self.restrictions = restrictions
        self.current_directory = os.path.expanduser("~")
        self.history: List[Dict[str, Any]] = []
        
    def is_path_allowed(self, path: str) -> Tuple[bool, str]:
        """Check if a path is allowed based on restrictions"""
        try:
            abs_path = os.path.abspath(os.path.expanduser(path))
            
            # Check if path is in blocked directories
            for blocked in self.restrictions.blocked_directories:
                blocked_abs = os.path.abspath(os.path.expanduser(blocked))
                if abs_path.startswith(blocked_abs):
                    return False, f"Access to {path} is blocked"
            
            # Check if path is in allowed directories
            if self.restrictions.allowed_directories:
                allowed = False
                for allowed_dir in self.restrictions.allowed_directories:
                    allowed_abs = os.path.abspath(os.path.expanduser(allowed_dir))
                    if abs_path.startswith(allowed_abs):
                        allowed = True
                        break
                if not allowed:
                    return False, f"Access to {path} is not allowed"
            
            # Check file extension if it's a file
            if os.path.isfile(abs_path):
                file_ext = os.path.splitext(abs_path)[1].lower()
                
                # Check blocked extensions
                if self.restrictions.blocked_file_extensions and file_ext in self.restrictions.blocked_file_extensions:
                    return False, f"File extension {file_ext} is blocked"
                
                # Check allowed extensions
                if (self.restrictions.allowed_file_extensions and 
                    file_ext not in self.restrictions.allowed_file_extensions):
                    return False, f"File extension {file_ext} is not allowed"
            
            # Check hidden files
            if not self.restrictions.allow_hidden_files and any(
                part.startswith('.') for part in Path(abs_path).parts
            ):
                return False, "Access to hidden files is not allowed"
                
            return True, "Path is allowed"
            
        except Exception as e:
            return False, f"Error checking path: {str(e)}"
    
    def change_directory(self, path: str) -> Dict[str, Any]:
        """Change the current working directory"""
        try:
            abs_path = os.path.abspath(os.path.expanduser(path))
            
            # Check if path is allowed
            allowed, reason = self.is_path_allowed(abs_path)
            if not allowed:
                return {"success": False, "error": reason}
            
            # Check if path exists and is a directory
            if not os.path.exists(abs_path):
                return {"success": False, "error": f"Path does not exist: {abs_path}"}
            if not os.path.isdir(abs_path):
                return {"success": False, "error": f"Not a directory: {abs_path}"}
            
            self.current_directory = abs_path
            self.history.append({
                "operation": "cd",
                "path": abs_path,
                "timestamp": os.times().elapsed
            })
            
            return {"success": True, "path": abs_path}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def list_directory(self, path: Optional[str] = None) -> Dict[str, Any]:
        """List contents of a directory"""
        try:
            target_path = path if path else self.current_directory
            abs_path = os.path.abspath(os.path.expanduser(target_path))
            
            # Check if path is allowed
            allowed, reason = self.is_path_allowed(abs_path)
            if not allowed:
                return {"success": False, "error": reason}
            
            # Check if path exists and is a directory
            if not os.path.exists(abs_path):
                return {"success": False, "error": f"Path does not exist: {abs_path}"}
            if not os.path.isdir(abs_path):
                return {"success": False, "error": f"Not a directory: {abs_path}"}
            
            # List directory contents
            items = []
            for item in os.listdir(abs_path):
                item_path = os.path.join(abs_path, item)
                item_stat = os.stat(item_path)
                
                # Skip hidden files if not allowed
                if not self.restrictions.allow_hidden_files and item.startswith('.'):
                    continue
                
                items.append({
                    "name": item,
                    "is_directory": os.path.isdir(item_path),
                    "size": item_stat.st_size if not os.path.isdir(item_path) else 0,
                    "modified": item_stat.st_mtime
                })
            
            # Sort directories first, then files
            items.sort(key=lambda x: (not x["is_directory"], x["name"].lower()))
            
            self.history.append({
                "operation": "ls",
                "path": abs_path,
                "timestamp": os.times().elapsed
            })
            
            return {
                "success": True, 
                "path": abs_path, 
                "items": items,
                "count": len(items)
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def read_file(self, path: str, max_lines: int = 100) -> Dict[str, Any]:
        """Read content from a file"""
        try:
            abs_path = os.path.abspath(os.path.expanduser(path))
            
            # Check if path is allowed
            allowed, reason = self.is_path_allowed(abs_path)
            if not allowed:
                return {"success": False, "error": reason}
            
            # Check if path exists and is a file
            if not os.path.exists(abs_path):
                return {"success": False, "error": f"File does not exist: {abs_path}"}
            if not os.path.isfile(abs_path):
                return {"success": False, "error": f"Not a file: {abs_path}"}
            
            # Check file size
            file_size = os.path.getsize(abs_path)
            if file_size > self.restrictions.max_file_size:
                return {
                    "success": False, 
                    "error": f"File too large: {file_size} bytes (max: {self.restrictions.max_file_size})"
                }
            
            # Read file content
            with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = []
                for i, line in enumerate(f):
                    if i >= max_lines:
                        lines.append("... (truncated)")
                        break
                    lines.append(line.rstrip())
            
            self.history.append({
                "operation": "read",
                "path": abs_path,
                "timestamp": os.times().elapsed,
                "lines_read": min(max_lines, len(lines))
            })
            
            return {
                "success": True,
                "path": abs_path,
                "content": "\n".join(lines),
                "total_lines": len(lines),
                "truncated": len(lines) >= max_lines
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def search_files(self, pattern: str, path: Optional[str] = None) -> Dict[str, Any]:
        """Search for files matching a pattern"""
        try:
            target_path = path if path else self.current_directory
            abs_path = os.path.abspath(os.path.expanduser(target_path))
            
            # Check if path is allowed
            allowed, reason = self.is_path_allowed(abs_path)
            if not allowed:
                return {"success": False, "error": reason}
            
            # Check if path exists and is a directory
            if not os.path.exists(abs_path):
                return {"success": False, "error": f"Path does not exist: {abs_path}"}
            if not os.path.isdir(abs_path):
                return {"success": False, "error": f"Not a directory: {abs_path}"}
            
            # Search for files
            matches = []
            for root, dirs, files in os.walk(abs_path):
                # Skip hidden directories if not allowed
                if not self.restrictions.allow_hidden_files:
                    dirs[:] = [d for d in dirs if not d.startswith('.')]
                
                for file in files:
                    # Skip hidden files if not allowed
                    if not self.restrictions.allow_hidden_files and file.startswith('.'):
                        continue
                    
                    if fnmatch.fnmatch(file, pattern):
                        file_path = os.path.join(root, file)
                        matches.append({
                            "path": file_path,
                            "size": os.path.getsize(file_path),
                            "modified": os.path.getmtime(file_path)
                        })
                
                # Limit recursion if not allowed
                if not self.restrictions.allow_recursive:
                    break
            
            self.history.append({
                "operation": "search",
                "pattern": pattern,
                "path": abs_path,
                "timestamp": os.times().elapsed,
                "matches": len(matches)
            })
            
            return {
                "success": True,
                "pattern": pattern,
                "matches": matches,
                "count": len(matches)
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}

class FileSystemNavigationInput(BaseModel):
    operation: str = Field(..., description="The file operation to perform: cd, ls, read, search")
    path: Optional[str] = Field(None, description="The path for the operation")
    pattern: Optional[str] = Field(None, description="Pattern for search operations")
    max_lines: Optional[int] = Field(100, description="Maximum lines to read from a file")

class FileSystemNavigationTool(BaseTool):
    name: str = "file_system_navigator"
    description: str = """
    Navigate and interact with the file system. 
    Operations: 
      - cd [path]: Change directory
      - ls [path]: List directory contents
      - read [path]: Read file content
      - search [pattern] [path]: Search for files matching pattern
    """
    args_schema: Any = FileSystemNavigationInput
    navigator: FileSystemNavigator
    
    def __init__(self, navigator: FileSystemNavigator):
        super().__init__()
        self.navigator = navigator
    
    def _run(self, operation: str, path: Optional[str] = None, 
             pattern: Optional[str] = None, max_lines: int = 100) -> str:
        """Execute the file system operation"""
        try:
            if operation == "cd":
                if not path:
                    return "Error: cd operation requires a path"
                result = self.navigator.change_directory(path)
            elif operation == "ls":
                result = self.navigator.list_directory(path)
            elif operation == "read":
                if not path:
                    return "Error: read operation requires a path"
                result = self.navigator.read_file(path, max_lines)
            elif operation == "search":
                if not pattern:
                    return "Error: search operation requires a pattern"
                result = self.navigator.search_files(pattern, path)
            else:
                return f"Error: Unknown operation '{operation}'"
            
            if result["success"]:
                return self._format_success_result(operation, result)
            else:
                return f"Error: {result['error']}"
                
        except Exception as e:
            return f"Error: {str(e)}"
    
    def _format_success_result(self, operation: str, result: Dict[str, Any]) -> str:
        """Format the success result for the agent"""
        if operation == "cd":
            return f"Changed directory to: {result['path']}"
        elif operation == "ls":
            items = result["items"]
            dirs = [item for item in items if item["is_directory"]]
            files = [item for item in items if not item["is_directory"]]
            
            output = f"Directory: {result['path']}\n"
            output += f"Items: {result['count']} ({len(dirs)} directories, {len(files)} files)\n\n"
            
            if dirs:
                output += "Directories:\n"
                for item in dirs:
                    output += f"  {item['name']}/\n"
            
            if files:
                output += "\nFiles:\n"
                for item in files:
                    size = self._format_file_size(item["size"])
                    output += f"  {item['name']} ({size})\n"
            
            return output
        elif operation == "read":
            output = f"File: {result['path']}\n"
            output += f"Lines: {result['total_lines']}"
            if result["truncated"]:
                output += " (truncated)"
            output += "\n\n"
            output += result["content"]
            return output
        elif operation == "search":
            output = f"Search: '{result['pattern']}' in {result.get('path', 'current directory')}\n"
            output += f"Matches: {result['count']}\n\n"
            
            for match in result["matches"][:10]:  # Limit to first 10 matches
                size = self._format_file_size(match["size"])
                output += f"- {match['path']} ({size})\n"
            
            if result["count"] > 10:
                output += f"\n... and {result['count'] - 10} more matches"
            
            return output
        else:
            return str(result)
    
    def _format_file_size(self, size: int) -> str:
        """Format file size in human-readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    
    async def _arun(self, *args, **kwargs):
        """Async version not implemented"""
        raise NotImplementedError("Async execution not supported")

# Example usage and setup
def create_file_system_tool(allowed_dirs: List[str] = None, 
                           blocked_dirs: List[str] = None) -> Tool:
    """
    Create a file system navigation tool with appropriate restrictions
    """
    if allowed_dirs is None:
        allowed_dirs = [os.path.expanduser("~/projects"), "/tmp"]
    
    if blocked_dirs is None:
        blocked_dirs = [os.path.expanduser("~/.ssh"), "/etc", "/var", "/usr", "/bin", "/sbin"]
    
    restrictions = FileSystemRestrictions(
        allowed_directories=allowed_dirs,
        blocked_directories=blocked_dirs,
        allowed_file_extensions=[".txt", ".py", ".js", ".html", ".css", ".md", ".json", ".xml", ".yaml", ".yml"],
        blocked_file_extensions=[".pem", ".key", ".crt", ".pub", ".priv", ".env", ".secret"],
        max_file_size=5 * 1024 * 1024,  # 5MB
        allow_recursive=False,
        allow_hidden_files=False
    )
    
    navigator = FileSystemNavigator(restrictions)
    tool = FileSystemNavigationTool(navigator=navigator)
    
    return Tool(
        name=tool.name,
        description=tool.description,
        func=tool._run,
        args_schema=FileSystemNavigationInput
    )

# System message for the agent
FILE_SYSTEM_AGENT_SYSTEM_MESSAGE = SystemMessage(content="""
You are an AI assistant with the ability to navigate and interact with the file system.
You have been granted limited access to specific directories for reading and exploring files.

Rules:
1. You can only access allowed directories
2. You cannot read certain file types (secrets, certificates, etc.)
3. You cannot modify or delete any files
4. You cannot access hidden files or directories
5. You cannot perform recursive operations without explicit permission

Available operations:
- cd [path]: Change current directory
- ls [path]: List directory contents
- read [path] [max_lines]: Read file content (default 100 lines)
- search [pattern] [path]: Search for files matching pattern

Always be cautious and respect file system boundaries. If an operation fails, report the error to the user.
""")

def main():
    """Example usage of the file system navigation tool"""
    tool = create_file_system_tool()
    
    # Test the tool
    print("=== Testing File System Navigation Tool ===\n")
    
    # Change to home directory
    result = tool.func(operation="cd", path="~")
    print(result + "\n")
    
    # List home directory (should be restricted)
    result = tool.func(operation="ls")
    print(result + "\n")
    
    # Change to projects directory
    result = tool.func(operation="cd", path="~/projects")
    print(result + "\n")
    
    # List projects directory
    result = tool.func(operation="ls")
    print(result + "\n")
    
    # Search for Python files
    result = tool.func(operation="search", pattern="*.py")
    print(result + "\n")

if __name__ == "__main__":
    main()