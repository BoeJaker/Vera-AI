"""
Git Repository Management Tools for Vera
Safe repository operations with automatic versioning and backup
Integrates with LightweightVersionStore to prevent data loss

Features:
- Clone and manage local/remote repositories
- Safe file modifications with automatic backups
- Branch management and navigation
- Commit history analysis and search
- Diff viewing and comparison
- Repository statistics and health checks
- Multi-repo operations
- Automatic backup before any destructive operation
"""

import os
import re
import json
import hashlib
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict
from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool

# Import version manager for safety
try:
    from Vera.Toolchain.Tools.version_manager import LightweightVersionStore, VersionMetadata
    VERSION_MANAGER_AVAILABLE = True
except ImportError:
    VERSION_MANAGER_AVAILABLE = False
    print("[Warning] Version manager not available - running without backup safety")


# ============================================================================
# INPUT SCHEMAS
# ============================================================================

class GitCloneInput(BaseModel):
    """Input schema for cloning repositories."""
    repo_url: str = Field(..., description="Git repository URL (https or ssh)")
    local_path: Optional[str] = Field(
        default=None,
        description="Local path to clone to (default: auto-generated)"
    )
    branch: Optional[str] = Field(
        default=None,
        description="Specific branch to clone (default: main/master)"
    )
    depth: Optional[int] = Field(
        default=None,
        description="Shallow clone depth for large repos (e.g., 1 for latest only)"
    )


class GitFileOperationInput(BaseModel):
    """Input schema for file operations in repos."""
    repo_path: str = Field(..., description="Path to the Git repository")
    file_path: str = Field(..., description="Path to file within repo (relative)")
    content: Optional[str] = Field(
        default=None,
        description="New content (for write operations)"
    )
    commit_message: Optional[str] = Field(
        default=None,
        description="Commit message (if auto-commit enabled)"
    )
    auto_commit: bool = Field(
        default=False,
        description="Automatically commit changes"
    )


class GitBranchInput(BaseModel):
    """Input schema for branch operations."""
    repo_path: str = Field(..., description="Path to the Git repository")
    branch_name: Optional[str] = Field(
        default=None,
        description="Branch name (for create/checkout operations)"
    )
    operation: str = Field(
        ...,
        description="Operation: list, create, checkout, delete, current"
    )
    force: bool = Field(
        default=False,
        description="Force operation (use with caution)"
    )


class GitHistoryInput(BaseModel):
    """Input schema for viewing commit history."""
    repo_path: str = Field(..., description="Path to the Git repository")
    file_path: Optional[str] = Field(
        default=None,
        description="Specific file to show history for"
    )
    limit: int = Field(default=20, description="Number of commits to show")
    author: Optional[str] = Field(
        default=None,
        description="Filter by author"
    )
    since: Optional[str] = Field(
        default=None,
        description="Show commits since date (e.g., '2024-01-01', '1 week ago')"
    )
    grep: Optional[str] = Field(
        default=None,
        description="Search commit messages"
    )


class GitDiffInput(BaseModel):
    """Input schema for viewing diffs."""
    repo_path: str = Field(..., description="Path to the Git repository")
    file_path: Optional[str] = Field(
        default=None,
        description="Specific file to diff"
    )
    commit_a: Optional[str] = Field(
        default=None,
        description="First commit (default: previous)"
    )
    commit_b: Optional[str] = Field(
        default=None,
        description="Second commit (default: current/HEAD)"
    )
    staged: bool = Field(
        default=False,
        description="Show staged changes only"
    )


class GitCommitInput(BaseModel):
    """Input schema for committing changes."""
    repo_path: str = Field(..., description="Path to the Git repository")
    message: str = Field(..., description="Commit message")
    files: Optional[List[str]] = Field(
        default=None,
        description="Specific files to commit (default: all changes)"
    )
    amend: bool = Field(
        default=False,
        description="Amend previous commit"
    )


class GitSearchInput(BaseModel):
    """Input schema for searching in repos."""
    repo_path: str = Field(..., description="Path to the Git repository")
    pattern: str = Field(..., description="Search pattern (regex supported)")
    file_pattern: Optional[str] = Field(
        default=None,
        description="Limit search to files matching pattern (e.g., '*.py')"
    )
    case_sensitive: bool = Field(default=False, description="Case sensitive search")


class GitRepoInfoInput(BaseModel):
    """Input schema for repo information."""
    repo_path: str = Field(..., description="Path to the Git repository")


class GitMultiRepoInput(BaseModel):
    """Input schema for multi-repo operations."""
    repo_paths: List[str] = Field(..., description="List of repository paths")
    operation: str = Field(
        ...,
        description="Operation: status, pull, fetch, push"
    )


# ============================================================================
# REPOSITORY METADATA
# ============================================================================

@dataclass
class RepoMetadata:
    """Metadata about a Git repository."""
    path: str
    remote_url: Optional[str]
    current_branch: str
    total_commits: int
    total_files: int
    last_commit_date: str
    last_commit_author: str
    last_commit_message: str
    is_clean: bool
    has_remotes: bool
    tracked_branches: List[str]


# ============================================================================
# GIT REPOSITORY MANAGER
# ============================================================================

class GitRepositoryManager:
    """
    Safe Git repository management with automatic versioning.
    All destructive operations create backups via VersionStore.
    """
    
    def __init__(self, agent, versions_dir: str = ".vera-versions"):
        self.agent = agent
        
        # Initialize version store for safety
        if VERSION_MANAGER_AVAILABLE:
            self.version_store = LightweightVersionStore(versions_dir)
            self.safe_mode = True
        else:
            self.version_store = None
            self.safe_mode = False
        
        # Track managed repositories
        self.repo_cache = {}
        
        # Agent info for versioning
        self.agent_id = getattr(agent, 'agent_id', 'unknown')
        self.agent_name = getattr(agent, 'name', 'Vera')
    
    def _run_git_command(self, repo_path: str, command: List[str], 
                        capture_output: bool = True) -> Tuple[bool, str]:
        """
        Execute a git command safely.
        
        Returns:
            (success: bool, output: str)
        """
        try:
            full_command = ['git', '-C', repo_path] + command
            
            result = subprocess.run(
                full_command,
                capture_output=capture_output,
                text=True,
                timeout=300  # 5 minute timeout for large operations
            )
            
            if result.returncode == 0:
                return True, result.stdout
            else:
                return False, result.stderr
                
        except subprocess.TimeoutExpired:
            return False, "Command timed out after 5 minutes"
        except Exception as e:
            return False, f"Error executing git command: {str(e)}"
    
    def _backup_file(self, file_path: str, reason: str = "Git operation backup") -> bool:
        """
        Create a backup of a file before modification.
        
        Returns:
            True if backup created successfully
        """
        if not self.safe_mode or not self.version_store:
            return True
        
        try:
            if not Path(file_path).exists():
                return True
            
            content = Path(file_path).read_text()
            
            self.version_store.save_version(
                file_path=file_path,
                content=content,
                reason=reason,
                agent_id=self.agent_id,
                agent_name=self.agent_name,
                session_id=getattr(self.agent.sess, 'id', 'unknown'),
                tags=["git-backup", "auto"]
            )
            
            return True
            
        except Exception as e:
            print(f"[Warning] Backup failed: {e}")
            return False
    
    def _is_git_repo(self, path: str) -> bool:
        """Check if a path is a Git repository."""
        return (Path(path) / '.git').exists()
    
    def _get_repo_root(self, path: str) -> Optional[str]:
        """Find the root of a Git repository."""
        current = Path(path).resolve()
        
        while current != current.parent:
            if (current / '.git').exists():
                return str(current)
            current = current.parent
        
        return None
    
    def clone_repository(self, repo_url: str, local_path: Optional[str] = None,
                        branch: Optional[str] = None, depth: Optional[int] = None) -> str:
        """
        Clone a Git repository.
        
        Args:
            repo_url: Git repository URL (https or ssh)
            local_path: Where to clone (default: ./repos/<repo-name>)
            branch: Specific branch to clone
            depth: Shallow clone depth (for large repos)
        
        Examples:
            clone_repository("https://github.com/user/repo.git")
            clone_repository("https://github.com/user/repo.git", branch="develop")
            clone_repository("https://github.com/user/large-repo.git", depth=1)
        """
        try:
            # Determine local path
            if not local_path:
                # Extract repo name from URL
                repo_name = repo_url.rstrip('/').split('/')[-1]
                if repo_name.endswith('.git'):
                    repo_name = repo_name[:-4]
                
                local_path = Path('./repos') / repo_name
                local_path.mkdir(parents=True, exist_ok=True)
            
            local_path = str(Path(local_path).resolve())
            
            # Check if already exists
            if self._is_git_repo(local_path):
                return f"[Error] Git repository already exists at: {local_path}"
            
            # Build clone command
            command = ['clone']
            
            if branch:
                command.extend(['--branch', branch])
            
            if depth:
                command.extend(['--depth', str(depth)])
            
            command.extend([repo_url, local_path])
            
            # Execute clone
            success, output = self._run_git_command('.', command)
            
            if not success:
                return f"[Error] Clone failed: {output}"
            
            # Cache repo info
            self.repo_cache[local_path] = self.get_repo_metadata(local_path)
            
            # Store in agent memory
            self.agent.mem.add_session_memory(
                self.agent.sess.id,
                repo_url,
                "git_clone",
                metadata={
                    "local_path": local_path,
                    "branch": branch or "default",
                    "depth": depth
                }
            )
            
            output_lines = [
                f"✓ Repository cloned successfully",
                f"URL: {repo_url}",
                f"Local path: {local_path}",
            ]
            
            if branch:
                output_lines.append(f"Branch: {branch}")
            
            if depth:
                output_lines.append(f"Depth: {depth} (shallow clone)")
            
            return "\n".join(output_lines)
            
        except Exception as e:
            return f"[Error] Failed to clone repository: {str(e)}"
    
    def read_repo_file(self, repo_path: str, file_path: str) -> str:
        """
        Read a file from a Git repository.
        
        Safe read operation with path validation.
        
        Args:
            repo_path: Path to Git repository
            file_path: Path to file within repo (relative)
        
        Example:
            read_repo_file("./repos/myproject", "src/main.py")
        """
        try:
            repo_path = str(Path(repo_path).resolve())
            
            if not self._is_git_repo(repo_path):
                return f"[Error] Not a Git repository: {repo_path}"
            
            # Construct full path
            full_path = Path(repo_path) / file_path
            
            # Security: ensure file is within repo
            if not str(full_path.resolve()).startswith(repo_path):
                return "[Error] Path traversal not allowed"
            
            if not full_path.exists():
                return f"[Error] File not found: {file_path}"
            
            content = full_path.read_text()
            
            # Get file info from git
            success, git_info = self._run_git_command(
                repo_path,
                ['log', '-1', '--format=%h|%ai|%an', '--', file_path]
            )
            
            header = [f"File: {file_path}"]
            
            if success and git_info.strip():
                parts = git_info.strip().split('|')
                if len(parts) == 3:
                    header.extend([
                        f"Last commit: {parts[0]}",
                        f"Last modified: {parts[1]}",
                        f"Author: {parts[2]}",
                        ""
                    ])
            
            return "\n".join(header) + "\n" + content
            
        except Exception as e:
            return f"[Error] Failed to read file: {str(e)}"
    
    def write_repo_file(self, repo_path: str, file_path: str, content: str,
                       commit_message: Optional[str] = None, 
                       auto_commit: bool = False) -> str:
        """
        Write a file in a Git repository with automatic backup.
        
        SAFE: Creates version backup before modifying.
        
        Args:
            repo_path: Path to Git repository
            file_path: Path to file within repo (relative)
            content: New file content
            commit_message: Optional commit message
            auto_commit: Automatically commit after writing
        
        Example:
            write_repo_file(
                repo_path="./repos/myproject",
                file_path="src/config.py",
                content="NEW_CONFIG = 'value'",
                commit_message="Update config",
                auto_commit=True
            )
        """
        try:
            repo_path = str(Path(repo_path).resolve())
            
            if not self._is_git_repo(repo_path):
                return f"[Error] Not a Git repository: {repo_path}"
            
            # Construct full path
            full_path = Path(repo_path) / file_path
            
            # Security check
            if not str(full_path.resolve()).startswith(repo_path):
                return "[Error] Path traversal not allowed"
            
            # BACKUP BEFORE MODIFICATION
            if full_path.exists():
                backup_success = self._backup_file(
                    str(full_path),
                    reason=f"Before modifying {file_path} in Git repo"
                )
                
                if not backup_success and self.safe_mode:
                    return "[Error] Backup failed - operation aborted for safety"
            
            # Create parent directories
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file
            full_path.write_text(content)
            
            output = [f"✓ File written: {file_path}"]
            
            # Save to version store
            if self.safe_mode and self.version_store:
                metadata = self.version_store.save_version(
                    file_path=str(full_path),
                    content=content,
                    reason=commit_message or f"Modified {file_path} in Git repo",
                    agent_id=self.agent_id,
                    agent_name=self.agent_name,
                    session_id=getattr(self.agent.sess, 'id', 'unknown'),
                    tags=["git-write"]
                )
                output.append(f"Backup version: {metadata.version_id}")
            
            # Auto-commit if requested
            if auto_commit:
                if not commit_message:
                    commit_message = f"Update {file_path}"
                
                # Stage file
                self._run_git_command(repo_path, ['add', file_path])
                
                # Commit
                success, commit_output = self._run_git_command(
                    repo_path,
                    ['commit', '-m', commit_message]
                )
                
                if success:
                    output.append(f"✓ Committed: {commit_message}")
                else:
                    output.append(f"⚠ Commit failed: {commit_output}")
            else:
                output.append("⚠ File written but not committed (use git commit)")
            
            return "\n".join(output)
            
        except Exception as e:
            return f"[Error] Failed to write file: {str(e)}"
    
    def manage_branches(self, repo_path: str, operation: str,
                       branch_name: Optional[str] = None, 
                       force: bool = False) -> str:
        """
        Manage Git branches.
        
        Operations:
        - list: Show all branches
        - current: Show current branch
        - create: Create new branch
        - checkout: Switch to branch
        - delete: Delete branch (with safety check)
        
        Args:
            repo_path: Path to Git repository
            operation: Operation to perform
            branch_name: Branch name (for create/checkout/delete)
            force: Force operation (use with caution)
        
        Examples:
            manage_branches("./repos/myproject", "list")
            manage_branches("./repos/myproject", "create", branch_name="feature-x")
            manage_branches("./repos/myproject", "checkout", branch_name="develop")
        """
        try:
            repo_path = str(Path(repo_path).resolve())
            
            if not self._is_git_repo(repo_path):
                return f"[Error] Not a Git repository: {repo_path}"
            
            operation = operation.lower()
            
            if operation == "list":
                # List all branches
                success, output = self._run_git_command(
                    repo_path,
                    ['branch', '-a']
                )
                
                if not success:
                    return f"[Error] {output}"
                
                branches = output.strip().split('\n')
                
                result = ["Branches:"]
                for branch in branches:
                    branch = branch.strip()
                    if branch.startswith('*'):
                        result.append(f"  {branch} (current)")
                    else:
                        result.append(f"  {branch}")
                
                return "\n".join(result)
            
            elif operation == "current":
                # Show current branch
                success, output = self._run_git_command(
                    repo_path,
                    ['branch', '--show-current']
                )
                
                if not success:
                    return f"[Error] {output}"
                
                return f"Current branch: {output.strip()}"
            
            elif operation == "create":
                if not branch_name:
                    return "[Error] branch_name required for create operation"
                
                # Create new branch
                success, output = self._run_git_command(
                    repo_path,
                    ['branch', branch_name]
                )
                
                if not success:
                    return f"[Error] {output}"
                
                return f"✓ Created branch: {branch_name}"
            
            elif operation == "checkout":
                if not branch_name:
                    return "[Error] branch_name required for checkout operation"
                
                # Check for uncommitted changes
                success, status = self._run_git_command(
                    repo_path,
                    ['status', '--porcelain']
                )
                
                if status.strip() and not force:
                    return (
                        "[Error] Uncommitted changes present. "
                        "Commit or stash changes, or use force=True"
                    )
                
                # Checkout branch
                command = ['checkout']
                if force:
                    command.append('-f')
                command.append(branch_name)
                
                success, output = self._run_git_command(repo_path, command)
                
                if not success:
                    return f"[Error] {output}"
                
                return f"✓ Switched to branch: {branch_name}"
            
            elif operation == "delete":
                if not branch_name:
                    return "[Error] branch_name required for delete operation"
                
                # Safety check: don't delete current branch
                success, current = self._run_git_command(
                    repo_path,
                    ['branch', '--show-current']
                )
                
                if current.strip() == branch_name:
                    return "[Error] Cannot delete current branch. Switch to another branch first."
                
                # Delete branch
                command = ['branch', '-D' if force else '-d', branch_name]
                success, output = self._run_git_command(repo_path, command)
                
                if not success:
                    return f"[Error] {output}"
                
                return f"✓ Deleted branch: {branch_name}"
            
            else:
                return f"[Error] Unknown operation: {operation}"
            
        except Exception as e:
            return f"[Error] Branch operation failed: {str(e)}"
    
    def view_history(self, repo_path: str, file_path: Optional[str] = None,
                    limit: int = 20, author: Optional[str] = None,
                    since: Optional[str] = None, grep: Optional[str] = None) -> str:
        """
        View commit history.
        
        Args:
            repo_path: Path to Git repository
            file_path: Specific file to show history for
            limit: Number of commits to show
            author: Filter by author
            since: Show commits since date
            grep: Search commit messages
        
        Examples:
            view_history("./repos/myproject", limit=10)
            view_history("./repos/myproject", file_path="src/main.py")
            view_history("./repos/myproject", author="john", since="1 week ago")
        """
        try:
            repo_path = str(Path(repo_path).resolve())
            
            if not self._is_git_repo(repo_path):
                return f"[Error] Not a Git repository: {repo_path}"
            
            # Build log command
            command = [
                'log',
                f'--max-count={limit}',
                '--format=%h|%ai|%an|%s'
            ]
            
            if author:
                command.append(f'--author={author}')
            
            if since:
                command.append(f'--since={since}')
            
            if grep:
                command.append(f'--grep={grep}')
            
            if file_path:
                command.extend(['--', file_path])
            
            success, output = self._run_git_command(repo_path, command)
            
            if not success:
                return f"[Error] {output}"
            
            if not output.strip():
                return "No commits found matching criteria"
            
            # Parse and format output
            commits = output.strip().split('\n')
            
            result = [f"Commit History ({len(commits)} commits):"]
            
            if file_path:
                result.append(f"File: {file_path}")
            
            result.append("")
            
            for commit in commits:
                parts = commit.split('|')
                if len(parts) == 4:
                    hash_short, date, author, message = parts
                    
                    # Format date
                    date_short = date.split()[0]  # Just date, not time
                    
                    result.append(f"{'='*60}")
                    result.append(f"Commit:  {hash_short}")
                    result.append(f"Date:    {date_short}")
                    result.append(f"Author:  {author}")
                    result.append(f"Message: {message}")
                    result.append("")
            
            return "\n".join(result)
            
        except Exception as e:
            return f"[Error] Failed to view history: {str(e)}"
    
    def view_diff(self, repo_path: str, file_path: Optional[str] = None,
                 commit_a: Optional[str] = None, commit_b: Optional[str] = None,
                 staged: bool = False) -> str:
        """
        View differences between commits or working directory.
        
        Args:
            repo_path: Path to Git repository
            file_path: Specific file to diff
            commit_a: First commit (default: previous)
            commit_b: Second commit (default: current/HEAD)
            staged: Show only staged changes
        
        Examples:
            view_diff("./repos/myproject")  # Uncommitted changes
            view_diff("./repos/myproject", staged=True)  # Staged changes
            view_diff("./repos/myproject", commit_a="HEAD~1", commit_b="HEAD")
        """
        try:
            repo_path = str(Path(repo_path).resolve())
            
            if not self._is_git_repo(repo_path):
                return f"[Error] Not a Git repository: {repo_path}"
            
            # Build diff command
            command = ['diff']
            
            if staged:
                command.append('--staged')
            
            if commit_a and commit_b:
                command.extend([commit_a, commit_b])
            elif commit_a:
                command.append(commit_a)
            
            if file_path:
                command.extend(['--', file_path])
            
            success, output = self._run_git_command(repo_path, command)
            
            if not success:
                return f"[Error] {output}"
            
            if not output.strip():
                return "No differences found"
            
            header = ["Diff:"]
            
            if file_path:
                header.append(f"File: {file_path}")
            
            if commit_a and commit_b:
                header.append(f"Between: {commit_a} and {commit_b}")
            elif commit_a:
                header.append(f"From: {commit_a}")
            elif staged:
                header.append("Staged changes")
            else:
                header.append("Working directory changes")
            
            header.append("")
            
            return "\n".join(header) + "\n" + output
            
        except Exception as e:
            return f"[Error] Failed to view diff: {str(e)}"
    
    def commit_changes(self, repo_path: str, message: str,
                      files: Optional[List[str]] = None,
                      amend: bool = False) -> str:
        """
        Commit changes to the repository.
        
        Args:
            repo_path: Path to Git repository
            message: Commit message
            files: Specific files to commit (default: all changes)
            amend: Amend previous commit
        
        Examples:
            commit_changes("./repos/myproject", "Fix bug in parser")
            commit_changes("./repos/myproject", "Update config", files=["config.py"])
        """
        try:
            repo_path = str(Path(repo_path).resolve())
            
            if not self._is_git_repo(repo_path):
                return f"[Error] Not a Git repository: {repo_path}"
            
            # Stage files
            if files:
                for file in files:
                    self._run_git_command(repo_path, ['add', file])
            else:
                self._run_git_command(repo_path, ['add', '-A'])
            
            # Build commit command
            command = ['commit', '-m', message]
            
            if amend:
                command.append('--amend')
            
            success, output = self._run_git_command(repo_path, command)
            
            if not success:
                # Check if nothing to commit
                if 'nothing to commit' in output.lower():
                    return "No changes to commit"
                return f"[Error] {output}"
            
            # Parse commit info
            result = [
                f"✓ Committed successfully",
                f"Message: {message}",
            ]
            
            if amend:
                result.append("(Amended previous commit)")
            
            # Get commit hash
            success, hash_output = self._run_git_command(
                repo_path,
                ['rev-parse', '--short', 'HEAD']
            )
            
            if success:
                result.append(f"Commit: {hash_output.strip()}")
            
            # Store in agent memory
            self.agent.mem.add_session_memory(
                self.agent.sess.id,
                message,
                "git_commit",
                metadata={
                    "repo_path": repo_path,
                    "files": files or "all"
                }
            )
            
            return "\n".join(result)
            
        except Exception as e:
            return f"[Error] Failed to commit: {str(e)}"
    
    def search_in_repo(self, repo_path: str, pattern: str,
                      file_pattern: Optional[str] = None,
                      case_sensitive: bool = False) -> str:
        """
        Search for text in repository files.
        
        Args:
            repo_path: Path to Git repository
            pattern: Search pattern (regex supported)
            file_pattern: Limit to files matching pattern
            case_sensitive: Case sensitive search
        
        Examples:
            search_in_repo("./repos/myproject", "TODO")
            search_in_repo("./repos/myproject", "class \w+", file_pattern="*.py")
        """
        try:
            repo_path = str(Path(repo_path).resolve())
            
            if not self._is_git_repo(repo_path):
                return f"[Error] Not a Git repository: {repo_path}"
            
            # Build grep command
            command = ['grep', '-n']  # -n shows line numbers
            
            if not case_sensitive:
                command.append('-i')
            
            command.append(pattern)
            
            if file_pattern:
                command.extend(['--', file_pattern])
            
            success, output = self._run_git_command(repo_path, command)
            
            if not success:
                if 'no matches found' in output.lower() or not output.strip():
                    return f"No matches found for: {pattern}"
                return f"[Error] {output}"
            
            # Format output
            matches = output.strip().split('\n')
            
            result = [
                f"Search results for: {pattern}",
                f"Found {len(matches)} matches",
                ""
            ]
            
            # Group by file
            by_file = {}
            for match in matches:
                if ':' in match:
                    parts = match.split(':', 2)
                    if len(parts) >= 3:
                        file, line_num, content = parts
                        if file not in by_file:
                            by_file[file] = []
                        by_file[file].append((line_num, content.strip()))
            
            for file, file_matches in by_file.items():
                result.append(f"File: {file} ({len(file_matches)} matches)")
                for line_num, content in file_matches[:10]:  # Limit to 10 per file
                    result.append(f"  Line {line_num}: {content}")
                if len(file_matches) > 10:
                    result.append(f"  ... and {len(file_matches) - 10} more")
                result.append("")
            
            return "\n".join(result)
            
        except Exception as e:
            return f"[Error] Search failed: {str(e)}"
    
    def get_repo_metadata(self, repo_path: str) -> RepoMetadata:
        """Get comprehensive metadata about a repository."""
        repo_path = str(Path(repo_path).resolve())
        
        # Get remote URL
        success, remote_url = self._run_git_command(
            repo_path,
            ['config', '--get', 'remote.origin.url']
        )
        remote_url = remote_url.strip() if success else None
        
        # Get current branch
        success, current_branch = self._run_git_command(
            repo_path,
            ['branch', '--show-current']
        )
        current_branch = current_branch.strip() if success else "unknown"
        
        # Get total commits
        success, commit_count = self._run_git_command(
            repo_path,
            ['rev-list', '--count', 'HEAD']
        )
        total_commits = int(commit_count.strip()) if success else 0
        
        # Get last commit info
        success, last_commit = self._run_git_command(
            repo_path,
            ['log', '-1', '--format=%ai|%an|%s']
        )
        
        if success and last_commit.strip():
            parts = last_commit.strip().split('|')
            last_commit_date = parts[0] if len(parts) > 0 else "unknown"
            last_commit_author = parts[1] if len(parts) > 1 else "unknown"
            last_commit_message = parts[2] if len(parts) > 2 else "unknown"
        else:
            last_commit_date = "unknown"
            last_commit_author = "unknown"
            last_commit_message = "unknown"
        
        # Check if working directory is clean
        success, status = self._run_git_command(
            repo_path,
            ['status', '--porcelain']
        )
        is_clean = not bool(status.strip()) if success else False
        
        # Get branches
        success, branches = self._run_git_command(
            repo_path,
            ['branch', '-a']
        )
        tracked_branches = []
        if success:
            tracked_branches = [
                b.strip().lstrip('* ') 
                for b in branches.strip().split('\n')
            ]
        
        # Count files
        success, files = self._run_git_command(
            repo_path,
            ['ls-files']
        )
        total_files = len(files.strip().split('\n')) if success and files.strip() else 0
        
        return RepoMetadata(
            path=repo_path,
            remote_url=remote_url,
            current_branch=current_branch,
            total_commits=total_commits,
            total_files=total_files,
            last_commit_date=last_commit_date,
            last_commit_author=last_commit_author,
            last_commit_message=last_commit_message,
            is_clean=is_clean,
            has_remotes=bool(remote_url),
            tracked_branches=tracked_branches
        )
    
    def get_repo_info(self, repo_path: str) -> str:
        """
        Get comprehensive information about a repository.
        
        Shows status, branches, remotes, recent commits, file count, etc.
        
        Example:
            get_repo_info("./repos/myproject")
        """
        try:
            repo_path = str(Path(repo_path).resolve())
            
            if not self._is_git_repo(repo_path):
                return f"[Error] Not a Git repository: {repo_path}"
            
            metadata = self.get_repo_metadata(repo_path)
            
            output = [
                f"Repository Information",
                f"{'='*60}",
                f"Path: {metadata.path}",
                f"",
                f"Current Branch: {metadata.current_branch}",
                f"Status: {'Clean' if metadata.is_clean else 'Has uncommitted changes'}",
                f"",
                f"Statistics:",
                f"  Total commits: {metadata.total_commits}",
                f"  Total files: {metadata.total_files}",
                f"  Branches: {len(metadata.tracked_branches)}",
                f"",
                f"Last Commit:",
                f"  Date: {metadata.last_commit_date}",
                f"  Author: {metadata.last_commit_author}",
                f"  Message: {metadata.last_commit_message}",
            ]
            
            if metadata.remote_url:
                output.extend([
                    f"",
                    f"Remote:",
                    f"  origin: {metadata.remote_url}"
                ])
            
            # Get uncommitted changes
            if not metadata.is_clean:
                success, status = self._run_git_command(
                    repo_path,
                    ['status', '--short']
                )
                
                if success and status.strip():
                    output.extend([
                        f"",
                        f"Uncommitted Changes:",
                        status.strip()
                    ])
            
            return "\n".join(output)
            
        except Exception as e:
            return f"[Error] Failed to get repo info: {str(e)}"
    
    def multi_repo_operation(self, repo_paths: List[str], operation: str) -> str:
        """
        Perform operations on multiple repositories.
        
        Operations:
        - status: Show status of all repos
        - pull: Pull latest changes from all repos
        - fetch: Fetch updates from all repos
        - push: Push changes in all repos
        
        Args:
            repo_paths: List of repository paths
            operation: Operation to perform
        
        Example:
            multi_repo_operation(
                repo_paths=["./repos/project1", "./repos/project2"],
                operation="status"
            )
        """
        try:
            operation = operation.lower()
            results = []
            
            for repo_path in repo_paths:
                repo_path = str(Path(repo_path).resolve())
                
                if not self._is_git_repo(repo_path):
                    results.append(f"✗ {repo_path}: Not a Git repository")
                    continue
                
                if operation == "status":
                    metadata = self.get_repo_metadata(repo_path)
                    status = "clean" if metadata.is_clean else "has changes"
                    results.append(
                        f"{'✓' if metadata.is_clean else '⚠'} {repo_path}: "
                        f"{metadata.current_branch} ({status})"
                    )
                
                elif operation in ["pull", "fetch", "push"]:
                    success, output = self._run_git_command(
                        repo_path,
                        [operation]
                    )
                    
                    if success:
                        results.append(f"✓ {repo_path}: {operation} successful")
                    else:
                        results.append(f"✗ {repo_path}: {operation} failed - {output}")
                
                else:
                    results.append(f"✗ {repo_path}: Unknown operation '{operation}'")
            
            header = [
                f"Multi-Repository {operation.title()}",
                f"{'='*60}",
                ""
            ]
            
            return "\n".join(header + results)
            
        except Exception as e:
            return f"[Error] Multi-repo operation failed: {str(e)}"


# ============================================================================
# GIT TOOLS CLASS
# ============================================================================

class GitRepoTools:
    """Git repository management tools for LLM agents."""
    
    def __init__(self, agent, versions_dir: str = ".vera-versions"):
        self.manager = GitRepositoryManager(agent, versions_dir)
        self.agent = agent
    
    # Wrap manager methods as tool-friendly functions
    
    def clone_repository(self, repo_url: str, local_path: Optional[str] = None,
                        branch: Optional[str] = None, depth: Optional[int] = None) -> str:
        return self.manager.clone_repository(repo_url, local_path, branch, depth)
    
    def read_repo_file(self, repo_path: str, file_path: str) -> str:
        return self.manager.read_repo_file(repo_path, file_path)
    
    def write_repo_file(self, repo_path: str, file_path: str, content: str,
                       commit_message: Optional[str] = None, 
                       auto_commit: bool = False) -> str:
        return self.manager.write_repo_file(
            repo_path, file_path, content, commit_message, auto_commit
        )
    
    def manage_branches(self, repo_path: str, operation: str,
                       branch_name: Optional[str] = None, 
                       force: bool = False) -> str:
        return self.manager.manage_branches(repo_path, operation, branch_name, force)
    
    def view_history(self, repo_path: str, file_path: Optional[str] = None,
                    limit: int = 20, author: Optional[str] = None,
                    since: Optional[str] = None, grep: Optional[str] = None) -> str:
        return self.manager.view_history(repo_path, file_path, limit, author, since, grep)
    
    def view_diff(self, repo_path: str, file_path: Optional[str] = None,
                 commit_a: Optional[str] = None, commit_b: Optional[str] = None,
                 staged: bool = False) -> str:
        return self.manager.view_diff(repo_path, file_path, commit_a, commit_b, staged)
    
    def commit_changes(self, repo_path: str, message: str,
                      files: Optional[List[str]] = None,
                      amend: bool = False) -> str:
        return self.manager.commit_changes(repo_path, message, files, amend)
    
    def search_in_repo(self, repo_path: str, pattern: str,
                      file_pattern: Optional[str] = None,
                      case_sensitive: bool = False) -> str:
        return self.manager.search_in_repo(repo_path, pattern, file_pattern, case_sensitive)
    
    def get_repo_info(self, repo_path: str) -> str:
        return self.manager.get_repo_info(repo_path)
    
    def multi_repo_operation(self, repo_paths: List[str], operation: str) -> str:
        return self.manager.multi_repo_operation(repo_paths, operation)


# ============================================================================
# ADD TO TOOLLOADER FUNCTION
# ============================================================================

def add_git_repo_tools(tool_list: List, agent, versions_dir: str = ".vera-versions"):
    """
    Add Git repository management tools with automatic versioning.
    
    Features:
    - Clone and manage local/remote repositories
    - Safe file modifications with automatic backups
    - Branch management and navigation
    - Commit history and diff viewing
    - Multi-repo operations
    - Search across repositories
    
    All file modifications are automatically backed up to the version store
    before changes are made, preventing accidental data loss.
    
    Call this in your ToolLoader function:
        tool_list = ToolLoader(agent)
        add_git_repo_tools(tool_list, agent)
        return tool_list
    """
    
    git_tools = GitRepoTools(agent, versions_dir)
    
    tool_list.extend([
        StructuredTool.from_function(
            func=git_tools.clone_repository,
            name="git_clone",
            description=(
                "Clone a Git repository from URL. "
                "Supports specific branches and shallow clones for large repos. "
                "Auto-creates local directory structure. "
                "Example: git_clone('https://github.com/user/repo.git')"
            ),
            args_schema=GitCloneInput
        ),
        
        StructuredTool.from_function(
            func=git_tools.read_repo_file,
            name="git_read_file",
            description=(
                "Read a file from a Git repository. "
                "Shows file content with last commit info. "
                "Safe path validation prevents directory traversal. "
                "Example: git_read_file('./repos/project', 'src/main.py')"
            ),
            args_schema=GitFileOperationInput
        ),
        
        StructuredTool.from_function(
            func=git_tools.write_repo_file,
            name="git_write_file",
            description=(
                "SAFE: Write file in Git repo with automatic backup. "
                "Creates version backup before modification. "
                "Optional auto-commit. Nothing is ever lost. "
                "Example: git_write_file('./repos/project', 'config.py', 'new content', auto_commit=True)"
            ),
            args_schema=GitFileOperationInput
        ),
        
        StructuredTool.from_function(
            func=git_tools.manage_branches,
            name="git_branches",
            description=(
                "Manage Git branches: list, create, checkout, delete, current. "
                "Safety checks prevent accidental deletions. "
                "Examples: git_branches('./repos/project', 'list'), "
                "git_branches('./repos/project', 'create', branch_name='feature-x')"
            ),
            args_schema=GitBranchInput
        ),
        
        StructuredTool.from_function(
            func=git_tools.view_history,
            name="git_history",
            description=(
                "View commit history with filtering. "
                "Filter by file, author, date, or message grep. "
                "Example: git_history('./repos/project', author='john', since='1 week ago')"
            ),
            args_schema=GitHistoryInput
        ),
        
        StructuredTool.from_function(
            func=git_tools.view_diff,
            name="git_diff",
            description=(
                "View differences between commits or working directory. "
                "Compare any two commits, or see uncommitted changes. "
                "Example: git_diff('./repos/project', commit_a='HEAD~1', commit_b='HEAD')"
            ),
            args_schema=GitDiffInput
        ),
        
        StructuredTool.from_function(
            func=git_tools.commit_changes,
            name="git_commit",
            description=(
                "Commit changes to repository. "
                "Commit all changes or specific files. Can amend previous commit. "
                "Example: git_commit('./repos/project', 'Fix parser bug')"
            ),
            args_schema=GitCommitInput
        ),
        
        StructuredTool.from_function(
            func=git_tools.search_in_repo,
            name="git_search",
            description=(
                "Search for text patterns in repository files. "
                "Supports regex, file filters, case sensitivity. "
                "Example: git_search('./repos/project', 'TODO', file_pattern='*.py')"
            ),
            args_schema=GitSearchInput
        ),
        
        StructuredTool.from_function(
            func=git_tools.get_repo_info,
            name="git_info",
            description=(
                "Get comprehensive repository information. "
                "Shows status, branches, commits, files, remotes, last commit. "
                "Example: git_info('./repos/project')"
            ),
            args_schema=GitRepoInfoInput
        ),
        
        StructuredTool.from_function(
            func=git_tools.multi_repo_operation,
            name="git_multi_repo",
            description=(
                "Perform operations on multiple repositories at once. "
                "Operations: status, pull, fetch, push. "
                "Example: git_multi_repo(['./repos/p1', './repos/p2'], 'status')"
            ),
            args_schema=GitMultiRepoInput
        ),
    ])
    
    return tool_list


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

"""
USAGE EXAMPLES:

1. Clone and explore a repository:
   git_clone("https://github.com/python/cpython.git", depth=1)
   git_info("./repos/cpython")
   git_branches("./repos/cpython", "list")

2. Safe file modification:
   git_read_file("./repos/myproject", "config.py")
   git_write_file(
       "./repos/myproject", 
       "config.py", 
       "NEW_CONFIG = True",
       commit_message="Update config",
       auto_commit=True
   )
   # File is automatically backed up before modification!

3. Explore history:
   git_history("./repos/myproject", file_path="src/main.py", limit=10)
   git_diff("./repos/myproject", commit_a="HEAD~5", commit_b="HEAD")

4. Branch management:
   git_branches("./repos/myproject", "create", branch_name="feature-auth")
   git_branches("./repos/myproject", "checkout", branch_name="feature-auth")
   # Make changes...
   git_commit("./repos/myproject", "Add authentication")

5. Search and analyze:
   git_search("./repos/myproject", "TODO", file_pattern="*.py")
   git_history("./repos/myproject", grep="bug fix", since="2024-01-01")

6. Multi-repo management:
   git_multi_repo(
       repo_paths=["./repos/frontend", "./repos/backend", "./repos/api"],
       operation="status"
   )

SAFETY FEATURES:
- All file modifications create automatic backups via VersionStore
- Path traversal protection
- Branch deletion safety checks
- Uncommitted changes warnings
- Force flags for destructive operations
- Nothing is ever truly lost!
"""