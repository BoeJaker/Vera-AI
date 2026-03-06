"""
Sandbox — Unified project-rooted execution environment.
=========================================================
Combines path enforcement (formerly SandboxEnforcer) and
bubblewrap/overlay execution (formerly SandboxRunner) into a
single class: ``ProjectSandbox``.

Design principles
-----------------
* **project_root is the single source of truth.**  All file I/O,
  tool wrapping, and command execution uses it directly.  There is
  no separate "workspace" that drifts from the real project.

* **Write-through by default.**  When bwrap/overlay is available the
  workspace IS an overlay on top of project_root — upper-layer
  writes are extracted back immediately after each ``run()`` call.
  When overlay is unavailable the fallback copies the project in and
  syncs changes back on every run.

* **Tools are wrapped once** with path validation so any LangChain
  tool that touches the filesystem is constrained to project_root.

* **No manual extraction step required.**  Callers do not need to
  call ``extract_artifacts()`` — it happens automatically.  The
  method is still public so stages that want explicit control can
  call it.

Public API
----------
    sandbox = ProjectSandbox(project_root="/home/vera/projects/foo")

    # Wrap LangChain tools with path enforcement
    safe_tools = sandbox.wrap_tools(agent.tools)

    # Run a shell command inside the sandbox (auto-syncs back)
    output = sandbox.run("python src/main.py")

    # Inspect what changed last run
    changes = sandbox.last_run_changes

    # Explicit sync (idempotent)
    extracted = sandbox.sync_to_project()

    # Cleanup temp dirs (preserves project_root)
    sandbox.cleanup()

Helper functions (module-level)
--------------------------------
    get_project_sandbox(focus_manager)  -> Optional[ProjectSandbox]
    create_sandboxed_tools(agent, project_root, tools) -> List[StructuredTool]
"""

from __future__ import annotations

import fnmatch
import os
import re
import shlex
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from langchain_core.tools import StructuredTool


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class SandboxViolation(PermissionError):
    """Raised when an operation attempts to escape the sandbox."""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class FileChange:
    """A file that was created or modified during a sandbox run."""
    path: Path          # Relative to project_root
    operation: str      # 'created' | 'modified' | 'deleted'
    size: int
    mtime: float

    def __repr__(self) -> str:
        return f"{self.operation.upper()}: {self.path} ({self.size} bytes)"


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class ProjectSandbox:
    """
    Unified sandbox that combines path-enforcement and command execution.

    Parameters
    ----------
    project_root:
        Absolute path to the project directory.  Created automatically
        if it does not exist.
    memory_mb:
        Soft memory limit for bwrap child processes (currently informational;
        rlimit-as is commented out because it breaks many Python interpreters).
    cpu_seconds:
        CPU time limit for bwrap (informational).
    exclude_dirs:
        Directory names to skip when scanning / copying.
    allow_network:
        Whether curl/wget/ssh etc. are permitted inside the sandbox.
    max_bash_timeout:
        Default timeout for ``run()``.
    blocked_extensions:
        File extensions that may not be *written* (e.g. {'.service'}).
    readonly_paths:
        Additional absolute paths that are permitted for *reading* even
        though they are outside project_root.
    debug:
        Print verbose diagnostic messages.
    """

    # ------------------------------------------------------------------
    # Constants
    # ------------------------------------------------------------------

    _BLOCKED_COMMANDS: Set[str] = {
        # System modification
        "rm -rf /", "mkfs", "dd if=", "format",
        # Privilege escalation
        "sudo", "su ", "su\n", "chmod 777 /", "chown", "passwd",
        "useradd", "usermod", "userdel",
        # Service control
        "systemctl", "service ", "init ", "shutdown", "reboot", "halt",
        # Network exfiltration / reverse shells
        "nc -l", "ncat", "/dev/tcp/", "/dev/udp/", "mkfifo",
        # System-wide package management
        "apt ", "apt-get", "dpkg ", "yum ", "dnf ", "pacman ", "snap ",
        # Cron / persistence
        "crontab", "/etc/cron",
        # Kernel modules
        "insmod", "modprobe", "rmmod",
        # Mount
        "mount ", "umount",
    }

    _BLOCKED_PATTERNS: List[str] = [
        r">\s*/etc/", r">\s*/var/", r">\s*/usr/",
        r">\s*/boot/", r">\s*/root/", r">\s*/tmp/",
        r">\s*/dev/", r">\s*~/",
        r"ln\s+-s.*/",
        r"kill\s+-9\s+1\b", r"pkill\s", r"killall\s",
        r"export\s+PATH=", r"export\s+LD_", r"export\s+HOME=",
        r"/dev/sd[a-z]", r"/dev/nvme",
        r"python[23]?\s+-c\s+.*open\s*\(",
        r"perl\s+-e", r"ruby\s+-e",
        r"curl\s+.*\|\s*(ba)?sh", r"wget\s+.*\|\s*(ba)?sh",
    ]

    _DEFAULT_READONLY: Set[str] = {
        "/usr/lib", "/usr/share", "/usr/bin",
        "/usr/local/lib", "/usr/local/bin",
    }

    _EXCLUDE_DIRS: Set[str] = {
        ".git", "__pycache__", ".venv", "venv",
        "node_modules", ".cache", "dist", "build",
        ".pytest_cache", ".mypy_cache", ".tox",
    }

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(
        self,
        project_root: str,
        *,
        memory_mb: int = 512,
        cpu_seconds: int = 60,
        exclude_dirs: Optional[List[str]] = None,
        allow_network: bool = False,
        max_bash_timeout: int = 60,
        blocked_extensions: Optional[Set[str]] = None,
        readonly_paths: Optional[Set[str]] = None,
        debug: bool = False,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.project_root.mkdir(parents=True, exist_ok=True)

        self.memory_mb = memory_mb
        self.cpu_seconds = cpu_seconds
        self.allow_network = allow_network
        self.max_bash_timeout = max_bash_timeout
        self.blocked_extensions = blocked_extensions or set()
        self.debug = debug

        self.exclude_dirs: Set[str] = self._EXCLUDE_DIRS.copy()
        if exclude_dirs:
            self.exclude_dirs.update(exclude_dirs)

        self.readonly_paths: Set[str] = self._DEFAULT_READONLY.copy()
        if readonly_paths:
            self.readonly_paths.update(readonly_paths)

        # Extend blocked commands when network is off
        self._effective_blocked = set(self._BLOCKED_COMMANDS)
        if not allow_network:
            self._effective_blocked.update({
                "curl ", "wget ", "ssh ", "scp ", "rsync ",
                "ftp ", "sftp ", "telnet ",
            })

        # Execution workspace (lazy — created on first run())
        self._base_dir: Optional[Path] = None
        self._workspace_dir: Optional[Path] = None
        self._upper_dir: Optional[Path] = None
        self._work_dir: Optional[Path] = None
        self._overlay_active: bool = False
        self._workspace_ready: bool = False

        # Change tracking
        self._snapshot: Dict[str, float] = {}   # rel_path -> mtime
        self.last_run_changes: List[FileChange] = []

        # Stats visible to callers
        self.artifacts_created: int = 0
        self.artifacts_modified: int = 0

    # ------------------------------------------------------------------
    # Public: path validation
    # ------------------------------------------------------------------

    def validate_path(self, path: str, operation: str = "access") -> str:
        """
        Resolve *path* and assert it lives inside project_root.

        Read operations may additionally reference ``readonly_paths``.
        Returns the resolved absolute path string.
        Raises ``SandboxViolation`` on escape attempt.
        """
        if not os.path.isabs(path):
            resolved = (self.project_root / path).resolve()
        else:
            resolved = Path(path).resolve()

        try:
            resolved.relative_to(self.project_root)
            return str(resolved)
        except ValueError:
            pass

        if operation == "read":
            for ro in self.readonly_paths:
                try:
                    resolved.relative_to(Path(ro).resolve())
                    return str(resolved)
                except ValueError:
                    continue

        raise SandboxViolation(
            f"[Sandbox] {operation.title()} denied: '{path}' → '{resolved}' "
            f"is outside project root '{self.project_root}'"
        )

    def validate_write_path(self, path: str) -> str:
        """Validate a path for write operations, checking blocked extensions."""
        resolved = self.validate_path(path, operation="write")
        ext = Path(resolved).suffix.lower()
        if ext in self.blocked_extensions:
            raise SandboxViolation(
                f"[Sandbox] Writing '{ext}' files is not permitted."
            )
        return resolved

    # ------------------------------------------------------------------
    # Public: bash / python / git validation
    # ------------------------------------------------------------------

    def validate_bash_command(self, command: str) -> str:
        """
        Check *command* for blocked patterns.
        Returns the command unchanged if safe; raises ``SandboxViolation``.
        """
        lower = command.lower().strip()

        for blocked in self._effective_blocked:
            if blocked in lower:
                raise SandboxViolation(
                    f"[Sandbox] Blocked command pattern: '{blocked}'"
                )

        for pattern in self._BLOCKED_PATTERNS:
            if re.search(pattern, lower):
                raise SandboxViolation(
                    f"[Sandbox] Blocked pattern in command: {command[:80]}"
                )

        for token in self._extract_path_tokens(command):
            if os.path.isabs(token):
                try:
                    self.validate_path(token, operation="access")
                except SandboxViolation:
                    raise SandboxViolation(
                        f"[Sandbox] Command references path outside sandbox: '{token}'"
                    )

        return command

    def validate_python_code(self, code: str) -> str:
        """Static analysis pass for dangerous Python patterns."""
        dangerous = [
            (r"os\.system\s*\(", "os.system()"),
            (r"subprocess\.", "subprocess module"),
            (r"shutil\.rmtree\s*\(", "shutil.rmtree()"),
            (r"open\s*\([^)]*[\"']\/((?!home).)", "file open outside /home"),
            (r"__import__\s*\(", "__import__()"),
            (r"importlib\.", "importlib"),
            (r"eval\s*\(", "eval()"),
            (r"exec\s*\(", "exec()"),
            (r"compile\s*\(", "compile()"),
        ]
        hits = [desc for pattern, desc in dangerous if re.search(pattern, code)]
        if hits:
            raise SandboxViolation(
                f"[Sandbox] Restricted Python patterns: {', '.join(hits)}"
            )
        return code

    def validate_git_path(self, repo_path: str) -> str:
        """Ensure git operations target repos within the sandbox."""
        return self.validate_path(repo_path, operation="read")

    # ------------------------------------------------------------------
    # Public: tool wrapping
    # ------------------------------------------------------------------

    def wrap_tools(self, tools: List[StructuredTool]) -> List[StructuredTool]:
        """
        Wrap bash/python/git tools with sandbox enforcement.

        read_file / write_file / edit_file / overwrite_file / list_directory /
        search_files are intentionally NOT wrapped here.  Those tools use
        FilesystemTool._get_sandbox() at call time to pick up whichever
        sandbox is active (default workspace or focus-specific project root).
        Wrapping them here would bake the current project_root into a closure
        that can never be updated, causing SandboxViolation when ActionsStage
        switches the root at runtime.

        Unknown tools pass through unchanged.
        """
        dispatch: Dict[str, Callable] = {
            "bash":   self._wrap_bash,
            "python": self._wrap_python,
            "git":    self._wrap_git,
        }
        return [
            dispatch[t.name](t) if t.name in dispatch else t
            for t in tools
        ]

    # ------------------------------------------------------------------
    # Public: command execution
    # ------------------------------------------------------------------

    def run(
        self,
        command: str,
        timeout: Optional[int] = None,
        working_dir: Optional[str] = None,
    ) -> str:
        """
        Execute *command* inside the sandbox and return combined stdout+stderr.

        The working directory defaults to project_root.
        File changes are automatically synced back to project_root after
        every call; ``last_run_changes`` is updated accordingly.
        """
        self.validate_bash_command(command)

        if working_dir:
            working_dir = self.validate_path(working_dir, operation="access")
        else:
            working_dir = str(self.project_root)

        timeout = timeout or self.max_bash_timeout

        self._ensure_workspace()

        if self._overlay_active:
            output = self._run_bwrap(command, timeout, working_dir)
        else:
            # Fallback: run directly in project_root (workspace IS project_root)
            output = self._run_direct(command, timeout, working_dir)

        # Always sync workspace → project_root and refresh tracking
        self.last_run_changes = self._sync_workspace_to_project()

        self.artifacts_created  += sum(1 for c in self.last_run_changes if c.operation == "created")
        self.artifacts_modified += sum(1 for c in self.last_run_changes if c.operation == "modified")

        return output

    # ------------------------------------------------------------------
    # Public: explicit sync / change inspection
    # ------------------------------------------------------------------

    def sync_to_project(self) -> List[FileChange]:
        """
        Explicitly sync workspace → project_root and return the changes.
        Safe to call multiple times (idempotent when nothing changed).
        """
        self.last_run_changes = self._sync_workspace_to_project()
        return self.last_run_changes

    def detect_changes(self) -> List[FileChange]:
        """
        Return the list of files that differ from the last snapshot
        without modifying the snapshot.  Useful for inspection.
        """
        return self._diff_against_snapshot(take_new_snapshot=False)

    def get_stats(self) -> Dict[str, int]:
        """Return cumulative artifact counters."""
        return {
            "artifacts_created":  self.artifacts_created,
            "artifacts_modified": self.artifacts_modified,
        }

    # ------------------------------------------------------------------
    # Public: lifecycle
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        """
        Unmount overlay (if active) and remove temp dirs.
        project_root is never touched.
        """
        if self._overlay_active and self._workspace_dir:
            try:
                subprocess.run(
                    ["umount", str(self._workspace_dir)],
                    check=False, capture_output=True, timeout=5,
                )
            except Exception as exc:
                if self.debug:
                    print(f"[Sandbox] umount warning: {exc}")

        if self._base_dir and self._base_dir.exists():
            try:
                shutil.rmtree(self._base_dir, ignore_errors=True)
            except Exception as exc:
                if self.debug:
                    print(f"[Sandbox] cleanup warning: {exc}")

        self._workspace_ready = False
        self._overlay_active = False
        self._base_dir = None
        self._workspace_dir = None
        self._upper_dir = None
        self._work_dir = None

    def ensure_ready(self) -> None:
        """
        Public alias for ``_ensure_workspace()``.

        Exists for backward-compatibility with code that previously called
        ``RuntimeSandbox.ensure_ready()`` or similar.  Calling this method
        is optional — ``run()`` calls it automatically before any command.
        """
        self._ensure_workspace()

    def set_project_root(self, new_root: str) -> None:
        """
        Change the project root at runtime (e.g. when an action stage
        picks a different working directory).

        Tears down any existing overlay workspace, updates project_root,
        and resets the snapshot baseline against the new root.
        """
        new_path = Path(new_root).resolve()
        if new_path == self.project_root:
            return
        self.cleanup()
        self.project_root = new_path
        self.project_root.mkdir(parents=True, exist_ok=True)
        self._snapshot.clear()
        if self.debug:
            print(f"[Sandbox] project_root changed → {self.project_root}")

    # ------------------------------------------------------------------
    # Workspace setup (private)
    # ------------------------------------------------------------------

    def _ensure_workspace(self) -> None:
        """Create overlay (or confirm direct mode) on first call."""
        if self._workspace_ready:
            return

        self._base_dir = Path(tempfile.mkdtemp(prefix="vera_sandbox_"))
        self._upper_dir = self._base_dir / "upper"
        self._work_dir  = self._base_dir / "work"
        self._workspace_dir = self._base_dir / "workspace"

        self._upper_dir.mkdir()
        self._work_dir.mkdir()
        self._workspace_dir.mkdir()

        mount_cmd = [
            "mount", "-t", "overlay", "overlay",
            "-o",
            (
                f"lowerdir={self.project_root},"
                f"upperdir={self._upper_dir},"
                f"workdir={self._work_dir}"
            ),
            str(self._workspace_dir),
        ]

        try:
            subprocess.run(mount_cmd, check=True, capture_output=True)
            self._overlay_active = True
            if self.debug:
                print(f"[Sandbox] Overlay mounted: {self._workspace_dir}")
        except Exception as exc:
            if self.debug:
                print(f"[Sandbox] Overlay unavailable ({exc}); using direct mode")
            # In direct mode the workspace IS project_root
            self._workspace_dir = self.project_root
            self._overlay_active = False

        # Take baseline snapshot so first sync has a reference
        self._take_snapshot()
        self._workspace_ready = True

    # ------------------------------------------------------------------
    # Snapshot / diff (private)
    # ------------------------------------------------------------------

    def _take_snapshot(self) -> None:
        """Record the current mtime of every file in project_root."""
        self._snapshot.clear()
        for filepath in self._walk_project():
            try:
                rel = str(filepath.relative_to(self.project_root))
                self._snapshot[rel] = filepath.stat().st_mtime
            except (OSError, ValueError):
                pass

    def _diff_against_snapshot(
        self, take_new_snapshot: bool = True
    ) -> List[FileChange]:
        """
        Compare current project_root state against the stored snapshot.

        When *take_new_snapshot* is True the snapshot is updated after
        the diff so subsequent calls only show *new* changes.
        """
        current: Dict[str, tuple] = {}
        for filepath in self._walk_project():
            try:
                stat = filepath.stat()
                rel = str(filepath.relative_to(self.project_root))
                current[rel] = (stat.st_mtime, stat.st_size)
            except (OSError, ValueError):
                pass

        changes: List[FileChange] = []

        for rel, (mtime, size) in current.items():
            old_mtime = self._snapshot.get(rel)
            if old_mtime is None:
                changes.append(FileChange(Path(rel), "created", size, mtime))
            elif mtime > old_mtime + 0.001:   # small epsilon for FS precision
                changes.append(FileChange(Path(rel), "modified", size, mtime))

        for rel in self._snapshot:
            if rel not in current:
                changes.append(FileChange(Path(rel), "deleted", 0, 0.0))

        if take_new_snapshot:
            self._take_snapshot()

        return changes

    # ------------------------------------------------------------------
    # Sync (private)
    # ------------------------------------------------------------------

    def _sync_workspace_to_project(self) -> List[FileChange]:
        """
        When overlay is active, copy upper-layer writes back to project_root
        and refresh the snapshot.  In direct mode just refresh the snapshot.
        """
        if self._overlay_active and self._upper_dir:
            self._copy_upper_to_project()

        return self._diff_against_snapshot(take_new_snapshot=True)

    def _copy_upper_to_project(self) -> None:
        """
        Copy every file in the overlay upper dir back to project_root.
        This is the core write-through mechanism.
        """
        if not self._upper_dir or not self._upper_dir.exists():
            return

        for root, dirs, files in os.walk(self._upper_dir):
            dirs[:] = [d for d in dirs if d not in self.exclude_dirs]
            for filename in files:
                src = Path(root) / filename
                try:
                    rel = src.relative_to(self._upper_dir)
                    dst = self.project_root / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                    if self.debug:
                        print(f"[Sandbox] synced {rel}")
                except Exception as exc:
                    if self.debug:
                        print(f"[Sandbox] sync failed for {src}: {exc}")

    # ------------------------------------------------------------------
    # Command runners (private)
    # ------------------------------------------------------------------

    def _run_bwrap(self, command: str, timeout: int, working_dir: str) -> str:
        """Run *command* inside a bubblewrap namespace."""
        # Map working_dir from project_root → workspace equivalent
        try:
            rel_cwd = Path(working_dir).relative_to(self.project_root)
            sandbox_cwd = str(self._workspace_dir / rel_cwd)
        except ValueError:
            sandbox_cwd = str(self._workspace_dir)

        bwrap_cmd = [
            "bwrap",
            "--unshare-all",
            "--new-session",
            "--die-with-parent",
            "--unshare-net",
            "--hostname", "sandbox",
            "--clearenv",
            "--setenv", "PATH", "/usr/bin:/bin",
            "--setenv", "HOME", "/home/sandbox",
            "--ro-bind", "/usr", "/usr",
            "--ro-bind", "/bin", "/bin",
            "--ro-bind", "/lib", "/lib",
            "--ro-bind", "/lib64", "/lib64",
            "--ro-bind", "/etc", "/etc",
            "--dir", "/home",
            "--tmpfs", "/tmp",
            "--proc", "/proc",
            "--dev", "/dev",
            "--bind", str(self._workspace_dir), "/workspace",
            "--chdir", sandbox_cwd.replace(str(self._workspace_dir), "/workspace"),
            "--",
            "bash", "-lc", command,
        ]

        try:
            result = subprocess.run(
                bwrap_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return f"[Sandbox] Command timed out after {timeout}s"
        except FileNotFoundError:
            # bwrap not installed — fall back to direct
            if self.debug:
                print("[Sandbox] bwrap not found, falling back to direct execution")
            return self._run_direct(command, timeout, working_dir)

    def _run_direct(self, command: str, timeout: int, working_dir: str) -> str:
        """
        Run *command* directly in *working_dir* (no namespace isolation).
        Used as a fallback when bwrap / overlay are unavailable.
        """
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=working_dir,
            )
            return result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return f"[Sandbox] Command timed out after {timeout}s"
        except Exception as exc:
            return f"[Sandbox] Execution error: {exc}"

    # ------------------------------------------------------------------
    # File walker (private)
    # ------------------------------------------------------------------

    def _walk_project(self):
        """Yield all files inside project_root, honouring exclude_dirs."""
        for root, dirs, files in os.walk(self.project_root):
            dirs[:] = [d for d in dirs if d not in self.exclude_dirs]
            for filename in files:
                yield Path(root) / filename

    # ------------------------------------------------------------------
    # Path token extraction (private)
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_path_tokens(command: str) -> List[str]:
        """Pull absolute path tokens out of a shell command string."""
        return re.findall(r"(?:^|\s|=|:)(\/[\w.\-/]+)", command)

    # ------------------------------------------------------------------
    # Tool wrapper helpers (private)
    # ------------------------------------------------------------------

    def _clone_tool(self, tool: StructuredTool, new_func: Callable) -> StructuredTool:
        return StructuredTool(
            name=tool.name,
            description=f"[Sandboxed to {self.project_root.name}] {tool.description}",
            func=new_func,
            args_schema=tool.args_schema,
            return_direct=tool.return_direct,
        )

    def _wrap_read_file(self, tool: StructuredTool) -> StructuredTool:
        original = tool.func

        @wraps(original)
        def _fn(path: str, **kw):
            return original(self.validate_path(path, "read"), **kw)

        return self._clone_tool(tool, _fn)

    def _wrap_write_file(self, tool: StructuredTool) -> StructuredTool:
        original = tool.func

        @wraps(original)
        def _fn(
            filepath: Optional[str] = None,
            path: Optional[str] = None,
            content: Optional[str] = None,
            new_content: Optional[str] = None,
            **kw,
        ):
            target = filepath or path
            validated = self.validate_write_path(target)
            if filepath is not None:
                return original(filepath=validated, content=content or new_content, **kw)
            return original(path=validated, new_content=new_content or content, **kw)

        return self._clone_tool(tool, _fn)

    def _wrap_edit_file(self, tool: StructuredTool) -> StructuredTool:
        original = tool.func

        @wraps(original)
        def _fn(path: Optional[str] = None, filepath: Optional[str] = None, **kw):
            target = path or filepath
            return original(path=self.validate_write_path(target), **kw)

        return self._clone_tool(tool, _fn)

    def _wrap_read_path(self, tool: StructuredTool) -> StructuredTool:
        original = tool.func

        @wraps(original)
        def _fn(path: str = ".", **kw):
            return original(self.validate_path(path, "read"), **kw)

        return self._clone_tool(tool, _fn)

    def _wrap_bash(self, tool: StructuredTool) -> StructuredTool:
        original   = tool.func
        init_sandbox = self  # fallback only — agent.runtime_sandbox takes priority

        @wraps(original)
        def _fn(command: str, working_dir: Optional[str] = None, **kw):
            # Resolve the *current* sandbox at call time so root changes propagate
            sb = getattr(init_sandbox, "_agent_ref", None)
            sb = getattr(sb, "runtime_sandbox", None) or init_sandbox
            sb.validate_bash_command(command)
            cwd = sb.validate_path(working_dir, "access") if working_dir else str(sb.project_root)
            result = original(command=command, working_dir=cwd, **kw)
            sb._sync_workspace_to_project()
            return result

        return self._clone_tool(tool, _fn)

    def _wrap_python(self, tool: StructuredTool) -> StructuredTool:
        original     = tool.func
        init_sandbox = self

        @wraps(original)
        def _fn(code: str, **kw):
            sb = getattr(init_sandbox, "_agent_ref", None)
            sb = getattr(sb, "runtime_sandbox", None) or init_sandbox
            sb.validate_python_code(code)
            preamble = f"import os; os.chdir({str(sb.project_root)!r})\n"
            result = original(code=preamble + code, **kw)
            sb._sync_workspace_to_project()
            return result

        return self._clone_tool(tool, _fn)

    def _wrap_git(self, tool: StructuredTool) -> StructuredTool:
        original     = tool.func
        init_sandbox = self

        @wraps(original)
        def _fn(repo_path: str = ".", command: str = "status", args: str = "", **kw):
            sb = getattr(init_sandbox, "_agent_ref", None)
            sb = getattr(sb, "runtime_sandbox", None) or init_sandbox
            validated_repo = sb.validate_git_path(repo_path)
            for token in sb._extract_path_tokens(args):
                if os.path.isabs(token):
                    sb.validate_path(token, "access")
            return original(repo_path=validated_repo, command=command, args=args, **kw)

        return self._clone_tool(tool, _fn)


# ---------------------------------------------------------------------------
# Module-level helpers  (public API used by stages / executor)
# ---------------------------------------------------------------------------

def get_project_sandbox(focus_manager) -> Optional[ProjectSandbox]:
    """
    Derive a ``ProjectSandbox`` from a ``ProactiveFocusManager``.

    Resolution order for project_root:
    1. ``focus_manager.project_root`` (explicit attribute — highest priority)
    2. Board key ``project_path`` or ``working_directory``
    3. ``~/vera_sandbox/<sanitised_focus_name>``  (auto-generated fallback)

    The sandbox is cached on ``focus_manager._sandbox``.  The cache is
    **invalidated automatically** when the resolved project_root differs
    from the cached sandbox's root — so calling this after a stage sets
    ``focus_manager.project_root`` always returns the correct sandbox.
    """
    def _resolve_root() -> Optional[str]:
        # 1. Explicit attribute
        pr = getattr(focus_manager, "project_root", None)
        if pr:
            return str(pr)
        # 2. Board state
        board_obj = getattr(focus_manager, "board", None)
        if board_obj and hasattr(board_obj, "get_all"):
            board = board_obj.get_all()
            candidate = board.get("project_path") or board.get("working_directory")
            if candidate and os.path.isdir(candidate):
                return candidate
        # 3. Auto-create from focus name
        focus = getattr(focus_manager, "focus", None)
        if focus:
            safe = re.sub(r"[^\w\-]", "_", focus.lower())
            return os.path.expanduser(f"~/vera_sandbox/{safe}")
        return None

    desired_root = _resolve_root()
    if desired_root is None:
        return None

    desired_path = Path(desired_root).resolve()

    # Check cache — invalidate if root has changed
    existing: Optional[ProjectSandbox] = getattr(focus_manager, "_sandbox", None)
    if existing is not None:
        if existing.project_root == desired_path:
            return existing  # Cache hit, same root
        # Root changed — invalidate and rebuild
        existing.cleanup()
        focus_manager._sandbox = None

    sandbox = ProjectSandbox(str(desired_path))

    # Align agent.runtime_sandbox so tools using that attribute stay in sync
    agent = getattr(focus_manager, "agent", None)
    if agent is not None:
        if hasattr(agent, "runtime_sandbox"):
            agent.runtime_sandbox = sandbox
        agent._project_sandbox = sandbox
        # Let bash/python/git closures find the agent to resolve current sandbox
        sandbox._agent_ref = agent

    focus_manager._sandbox = sandbox
    return sandbox


def create_sandboxed_tools(
    agent,
    project_root: str,
    tool_list: List[StructuredTool],
    **kwargs,
) -> List[StructuredTool]:
    """
    Convenience wrapper: build a ``ProjectSandbox`` and wrap *tool_list*.

    Any extra *kwargs* are forwarded to ``ProjectSandbox.__init__``.
    """
    sandbox = ProjectSandbox(project_root, **kwargs)
    return sandbox.wrap_tools(tool_list)


def sync_agent_sandbox(focus_manager) -> List[FileChange]:
    """
    Force a sync of the agent's sandbox workspace → project_root and
    return the list of changes.  Safe to call even if no sandbox exists
    (returns an empty list).

    Intended to be called from stages after any tool / LLM execution
    that might have written files.
    """
    sandbox: Optional[ProjectSandbox] = (
        getattr(focus_manager, "_sandbox", None)
        or get_project_sandbox(focus_manager)
    )
    if sandbox is None:
        return []
    return sandbox.sync_to_project()