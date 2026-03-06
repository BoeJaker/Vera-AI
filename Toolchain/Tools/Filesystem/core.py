"""
File system tools: read, write, edit files and list/search directories.

Sandbox resolution order (most → least specific):
  1. focus_manager._sandbox   (set by ActionsStage / StageExecutor for project work)
  2. agent.runtime_sandbox    (default workspace set at Vera init)
  3. No sandbox — bare validated path only (legacy fallback, logs a warning)

This means tools transparently use whichever root is active for the current
execution context without any changes to call sites.
"""

import os
import re
from typing import List, Optional
from langchain_core.tools import StructuredTool
from Vera.Toolchain.schemas import FilePathInput, WriteFileInput, SearchFilesInput


def truncate_output(text: str, max_length: int = 5000) -> str:
    if len(text) > max_length:
        return text[:max_length] + f"\n... [truncated {len(text) - max_length} characters]"
    return text


class FilesystemTool:
    def __init__(self, agent):
        self.agent = agent

    def _get_sandbox(self):
        """
        Return whichever sandbox is active right now.

        Checks focus_manager first so that when ActionsStage sets a
        project-specific root, writes go there rather than to the default
        Vera workspace.
        """
        # 1. Focus manager sandbox (project-specific, set by stages)
        fm = getattr(self.agent, "focus_manager", None)
        if fm is not None:
            sb = getattr(fm, "_sandbox", None)
            if sb is not None:
                return sb

        # 2. Default Vera workspace sandbox
        sb = getattr(self.agent, "runtime_sandbox", None)
        if sb is not None:
            return sb

        return None

    def _validate_read(self, path: str) -> str:
        sb = self._get_sandbox()
        if sb:
            return sb.validate_path(path, operation="read")
        # Fallback: just normalise, no boundary check
        print("[FilesystemTool] WARNING: no sandbox active, path not boundary-checked")
        return os.path.abspath(path)

    def _validate_write(self, path: str) -> str:
        sb = self._get_sandbox()
        if sb:
            return sb.validate_write_path(path)
        print("[FilesystemTool] WARNING: no sandbox active, path not boundary-checked")
        return os.path.abspath(path)

    def _try_memory(self, func):
        try:
            return func()
        except Exception as e:
            print(f"[FilesystemTool] Memory operation failed (non-fatal): {e}")
            return None

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    def read_file(self, path: str) -> str:
        """Read and return the contents of a file."""
        try:
            validated = self._validate_read(path)
            if not os.path.exists(validated):
                return f"[Error] File not found: {path}"
            if not os.path.isfile(validated):
                return f"[Error] Path is not a file: {path}"
            with open(validated, "r", encoding="utf-8") as f:
                content = f.read()
            self._try_memory(lambda: self._record_file_read(validated, content))
            return truncate_output(content)
        except UnicodeDecodeError:
            return f"[Error] File is not a text file or has encoding issues: {path}"
        except Exception as e:
            return f"[Error] Failed to read file: {str(e)}"

    def write_file(self, filepath: str, content: str) -> str:
        """Write content to a file. Creates parent directories if needed."""
        try:
            validated = self._validate_write(filepath)
            os.makedirs(os.path.dirname(validated) or ".", exist_ok=True)
            with open(validated, "w", encoding="utf-8") as f:
                f.write(content)
            self._try_memory(lambda: self._record_file_write(validated, content))
            return f"Successfully wrote {len(content)} characters to {validated}"
        except Exception as e:
            return f"[Error] Failed to write file: {str(e)}"

    def edit_file(self, path: str, new_content: str, line_numbers: list = None) -> str:
        """Edit an existing file by inserting new content. Creates the file if it does not exist."""
        try:
            validated = self._validate_write(path)
            os.makedirs(os.path.dirname(validated) or ".", exist_ok=True)
            if os.path.exists(validated):
                with open(validated, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                if line_numbers is not None:
                    for line_number in sorted(line_numbers, reverse=True):
                        if 1 <= line_number <= len(lines):
                            lines.insert(line_number - 1, new_content + "\n")
                        else:
                            return f"[Error] Line number {line_number} is out of bounds."
                else:
                    lines = [new_content + "\n"]
                with open(validated, "w", encoding="utf-8") as f:
                    f.writelines(lines)
            else:
                with open(validated, "w", encoding="utf-8") as f:
                    f.write(new_content + "\n")
            return f"Successfully edited file: {validated}"
        except Exception as e:
            return f"[Error] Failed to edit file: {str(e)}"

    def overwrite_file(self, path: str, new_content: str) -> str:
        """Overwrite an existing file with new content. Creates the file if it does not exist."""
        try:
            validated = self._validate_write(path)
            os.makedirs(os.path.dirname(validated) or ".", exist_ok=True)
            with open(validated, "w", encoding="utf-8") as f:
                f.write(new_content)
            return f"Successfully overwrote file: {validated}"
        except Exception as e:
            return f"[Error] Failed to overwrite file: {str(e)}"

    def list_directory(self, path: str = ".") -> str:
        """List contents of a directory with file sizes and types."""
        try:
            validated = self._validate_read(path)
            if not os.path.exists(validated):
                return f"[Error] Directory not found: {path}"
            if not os.path.isdir(validated):
                return f"[Error] Path is not a directory: {path}"
            items = []
            for item in sorted(os.listdir(validated)):
                item_path = os.path.join(validated, item)
                if os.path.isdir(item_path):
                    items.append(f"[DIR]  {item}/")
                else:
                    size = os.path.getsize(item_path)
                    items.append(f"[FILE] {item} ({size} bytes)")
            return "\n".join(items) if items else "[Empty directory]"
        except Exception as e:
            return f"[Error] Failed to list directory: {str(e)}"

    def search_files(self, path: str, pattern: str) -> str:
        """Search for files matching a pattern recursively."""
        try:
            validated = self._validate_read(path)
            matches = []
            for root, dirs, files in os.walk(validated):
                for file in files:
                    if re.search(pattern, file) or file.endswith(pattern):
                        full_path = os.path.join(root, file)
                        size = os.path.getsize(full_path)
                        matches.append(f"{full_path} ({size} bytes)")
            return "\n".join(matches) if matches else f"No files matching '{pattern}' found"
        except Exception as e:
            return f"[Error] Failed to search files: {str(e)}"

    # ------------------------------------------------------------------
    # Memory helpers
    # ------------------------------------------------------------------

    def _record_file_read(self, path, content):
        m1 = self.agent.mem.add_session_memory(
            self.agent.sess.id, path, "file",
            metadata={"status": "active", "priority": "high"},
            labels=["File"], promote=True
        )
        m2 = self.agent.mem.attach_document(
            self.agent.sess.id, path, content,
            {"topic": "read_file", "agent": "system"}
        )
        self.agent.mem.link(m1.id, m2.id, "Read")

    def _record_file_write(self, filepath, content):
        m1 = self.agent.mem.add_session_memory(
            self.agent.sess.id, filepath, "file",
            metadata={"status": "active", "priority": "high"},
            labels=["File"], promote=True
        )
        m2 = self.agent.mem.attach_document(
            self.agent.sess.id, filepath, content,
            {"topic": "write_file", "agent": "system"}
        )
        self.agent.mem.link(m1.id, m2.id, "Written")


def add_filesystem_tools(tool_list: List, agent) -> List:
    tools = FilesystemTool(agent)
    tool_list.extend([
        StructuredTool.from_function(
            func=tools.read_file,
            name="read_file",
            description="Read and return the contents of a file. Supports text files of any format.",
            args_schema=FilePathInput,
        ),
        StructuredTool.from_function(
            func=tools.write_file,
            name="write_file",
            description="Write content to a file. Creates parent directories if needed. Overwrites existing files.",
            args_schema=WriteFileInput,
        ),
        StructuredTool.from_function(
            func=tools.edit_file,
            name="edit_file",
            description="Edit an existing file by inserting new content at specific lines. Creates the file if it does not exist.",
            args_schema=WriteFileInput,
        ),
        StructuredTool.from_function(
            func=tools.overwrite_file,
            name="overwrite_file",
            description="Overwrite an existing file with new content. Creates the file if it does not exist.",
            args_schema=WriteFileInput,
        ),
        StructuredTool.from_function(
            func=tools.list_directory,
            name="list_directory",
            description="List contents of a directory with file sizes and types.",
            args_schema=FilePathInput,
        ),
        StructuredTool.from_function(
            func=tools.search_files,
            name="search_files",
            description="Search for files matching a pattern recursively. Pattern can be a glob pattern (*.py) or regex.",
            args_schema=SearchFilesInput,
        ),
    ])
    return tool_list