"""
Lightweight File Versioning System for LLM
Tracks file changes with metadata, using diffs for minimal overhead
Git-aware but completely separate from Git history
"""

import os
import sqlite3
import hashlib
import difflib
import json
import gzip
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict
from pydantic import BaseModel, Field
from langchain_core.tools import tool, StructuredTool
from Vera.Toolchain.schemas import *

# ============================================================================
# INPUT SCHEMAS
# ============================================================================

class VersionedFileWriteInput(BaseModel):
    """Input schema for versioned file writes."""
    file_path: str = Field(..., description="Path to the file to write/modify")
    content: str = Field(..., description="New content for the file")
    reason: str = Field(..., description="Reason for this change")
    tags: Optional[List[str]] = Field(
        default=None,
        description="Optional tags for categorizing this change"
    )


class VersionedFileReadInput(BaseModel):
    """Input schema for reading versioned files."""
    file_path: str = Field(..., description="Path to the file to read")
    version_id: Optional[str] = Field(
        default=None,
        description="Specific version ID to read (default: latest)"
    )


class FileHistoryQueryInput(BaseModel):
    """Input schema for querying file history."""
    file_path: Optional[str] = Field(
        default=None,
        description="Specific file path (or None for all files)"
    )
    limit: int = Field(default=20, description="Number of versions to show")
    tags: Optional[List[str]] = Field(
        default=None,
        description="Filter by tags"
    )
    agent_id: Optional[str] = Field(
        default=None,
        description="Filter by agent ID"
    )


class FileDiffInput(BaseModel):
    """Input schema for viewing diffs."""
    file_path: str = Field(..., description="Path to the file")
    version_a: Optional[str] = Field(
        default=None,
        description="First version ID (default: previous)"
    )
    version_b: Optional[str] = Field(
        default=None,
        description="Second version ID (default: current)"
    )


class FileRevertInput(BaseModel):
    """Input schema for reverting files."""
    file_path: str = Field(..., description="Path to the file")
    version_id: str = Field(..., description="Version ID to revert to")
    reason: str = Field(
        default="Reverted to previous version",
        description="Reason for reverting"
    )


# ============================================================================
# VERSION METADATA
# ============================================================================

@dataclass
class VersionMetadata:
    """Metadata for a file version."""
    version_id: str
    file_path: str
    timestamp: str
    agent_id: str
    agent_name: str
    session_id: str
    reason: str
    tags: List[str]
    size_bytes: int
    hash_sha256: str
    parent_version: Optional[str]
    is_creation: bool
    diff_size: int


# ============================================================================
# LIGHTWEIGHT VERSION STORE
# ============================================================================

class LightweightVersionStore:
    """
    Minimal-overhead versioning system using diffs and SQLite.
    Stores only changes (diffs) rather than full file copies.
    """
    
    def __init__(self, versions_dir: str = ".vera-versions"):
        self.versions_dir = Path(versions_dir)
        self.versions_dir.mkdir(exist_ok=True)
        
        # SQLite database for metadata
        self.db_path = self.versions_dir / "versions.db"
        self._init_database()
        
        # Diffs directory (compressed)
        self.diffs_dir = self.versions_dir / "diffs"
        self.diffs_dir.mkdir(exist_ok=True)
        
        # Check if in Git repo
        self.git_root = self._find_git_root()
        
        # Create .gitignore for versions directory
        gitignore = self.versions_dir / ".gitignore"
        if not gitignore.exists():
            gitignore.write_text("*\n!.gitignore\n")
    
    def _find_git_root(self) -> Optional[Path]:
        """Find Git repository root if it exists."""
        current = Path.cwd()
        while current != current.parent:
            if (current / ".git").exists():
                return current
            current = current.parent
        return None
    
    def _init_database(self):
        """Initialize SQLite database for version metadata."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS versions (
                    version_id TEXT PRIMARY KEY,
                    file_path TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    agent_name TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    tags TEXT,
                    size_bytes INTEGER,
                    hash_sha256 TEXT,
                    parent_version TEXT,
                    is_creation BOOLEAN,
                    diff_size INTEGER
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_file_path 
                ON versions(file_path)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON versions(timestamp DESC)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_agent 
                ON versions(agent_id)
            """)
            
            conn.commit()
    
    def _generate_version_id(self, file_path: str, content: str, timestamp: str) -> str:
        """Generate unique version ID."""
        data = f"{file_path}:{timestamp}:{content[:100]}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def _compute_file_hash(self, content: str) -> str:
        """Compute SHA256 hash of file content."""
        return hashlib.sha256(content.encode()).hexdigest()
    
    def _store_diff(self, version_id: str, old_content: str, new_content: str) -> int:
        """
        Store compressed diff between old and new content.
        Returns size of compressed diff in bytes.
        """
        # Generate unified diff
        old_lines = old_content.splitlines(keepends=True) if old_content else []
        new_lines = new_content.splitlines(keepends=True)
        
        diff = list(difflib.unified_diff(
            old_lines, 
            new_lines,
            lineterm='',
            n=3  # Context lines
        ))
        
        diff_text = '\n'.join(diff)
        
        # Compress and store
        diff_path = self.diffs_dir / f"{version_id}.diff.gz"
        compressed = gzip.compress(diff_text.encode())
        diff_path.write_bytes(compressed)
        
        return len(compressed)
    
    def _store_full_content(self, version_id: str, content: str) -> int:
        """
        Store full content (compressed) for first version.
        Returns size of compressed content in bytes.
        """
        content_path = self.diffs_dir / f"{version_id}.full.gz"
        compressed = gzip.compress(content.encode())
        content_path.write_bytes(compressed)
        return len(compressed)
    
    def _read_diff(self, version_id: str) -> str:
        """Read and decompress a diff."""
        diff_path = self.diffs_dir / f"{version_id}.diff.gz"
        if diff_path.exists():
            compressed = diff_path.read_bytes()
            return gzip.decompress(compressed).decode()
        return ""
    
    def _read_full_content(self, version_id: str) -> str:
        """Read and decompress full content."""
        content_path = self.diffs_dir / f"{version_id}.full.gz"
        if content_path.exists():
            compressed = content_path.read_bytes()
            return gzip.decompress(compressed).decode()
        return ""
    
    def _apply_diff(self, original: str, diff_text: str) -> str:
        """Apply a unified diff to original content."""
        if not diff_text:
            return original
        
        original_lines = original.splitlines(keepends=True)
        diff_lines = diff_text.splitlines()
        
        # Parse and apply diff
        # This is a simplified implementation
        # For production, you might want to use a proper patch library
        
        result = []
        i = 0
        
        for line in diff_lines:
            if line.startswith('+++') or line.startswith('---'):
                continue
            elif line.startswith('@@'):
                # Parse hunk header
                continue
            elif line.startswith('-'):
                # Line removed - skip in original
                i += 1
            elif line.startswith('+'):
                # Line added - add to result
                result.append(line[1:] + '\n')
            else:
                # Context line - keep from original
                if i < len(original_lines):
                    result.append(original_lines[i])
                    i += 1
        
        return ''.join(result)
    
    def save_version(self, file_path: str, content: str, reason: str,
                    agent_id: str, agent_name: str, session_id: str,
                    tags: List[str] = None) -> VersionMetadata:
        """
        Save a new version of a file.
        
        Args:
            file_path: Path to the file
            content: New content
            reason: Reason for the change
            agent_id: ID of the agent making the change
            agent_name: Name of the agent
            session_id: Current session ID
            tags: Optional tags
        
        Returns:
            VersionMetadata for the new version
        """
        timestamp = datetime.now().isoformat()
        version_id = self._generate_version_id(file_path, content, timestamp)
        file_hash = self._compute_file_hash(content)
        
        # Get previous version
        parent_version = None
        old_content = ""
        is_creation = True
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT version_id FROM versions WHERE file_path = ? ORDER BY timestamp DESC LIMIT 1",
                (file_path,)
            )
            row = cursor.fetchone()
            if row:
                parent_version = row[0]
                is_creation = False
                
                # Reconstruct old content
                old_content = self.reconstruct_version(file_path, parent_version)
        
        # Store diff or full content
        if is_creation:
            diff_size = self._store_full_content(version_id, content)
        else:
            diff_size = self._store_diff(version_id, old_content, content)
        
        # Save metadata
        metadata = VersionMetadata(
            version_id=version_id,
            file_path=file_path,
            timestamp=timestamp,
            agent_id=agent_id,
            agent_name=agent_name,
            session_id=session_id,
            reason=reason,
            tags=tags or [],
            size_bytes=len(content.encode()),
            hash_sha256=file_hash,
            parent_version=parent_version,
            is_creation=is_creation,
            diff_size=diff_size
        )
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO versions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metadata.version_id,
                metadata.file_path,
                metadata.timestamp,
                metadata.agent_id,
                metadata.agent_name,
                metadata.session_id,
                metadata.reason,
                json.dumps(metadata.tags),
                metadata.size_bytes,
                metadata.hash_sha256,
                metadata.parent_version,
                metadata.is_creation,
                metadata.diff_size
            ))
            conn.commit()
        
        return metadata
    
    def get_version_metadata(self, version_id: str) -> Optional[VersionMetadata]:
        """Get metadata for a specific version."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM versions WHERE version_id = ?",
                (version_id,)
            )
            row = cursor.fetchone()
            
            if row:
                return VersionMetadata(
                    version_id=row['version_id'],
                    file_path=row['file_path'],
                    timestamp=row['timestamp'],
                    agent_id=row['agent_id'],
                    agent_name=row['agent_name'],
                    session_id=row['session_id'],
                    reason=row['reason'],
                    tags=json.loads(row['tags']),
                    size_bytes=row['size_bytes'],
                    hash_sha256=row['hash_sha256'],
                    parent_version=row['parent_version'],
                    is_creation=bool(row['is_creation']),
                    diff_size=row['diff_size']
                )
        return None
    
    def get_file_history(self, file_path: Optional[str] = None, 
                        limit: int = 20, tags: List[str] = None,
                        agent_id: str = None) -> List[VersionMetadata]:
        """Get version history for a file or all files."""
        query = "SELECT * FROM versions WHERE 1=1"
        params = []
        
        if file_path:
            query += " AND file_path = ?"
            params.append(file_path)
        
        if agent_id:
            query += " AND agent_id = ?"
            params.append(agent_id)
        
        if tags:
            # Simple tag filtering (could be optimized)
            query += " AND tags LIKE ?"
            params.append(f"%{tags[0]}%")
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        versions = []
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            
            for row in cursor:
                versions.append(VersionMetadata(
                    version_id=row['version_id'],
                    file_path=row['file_path'],
                    timestamp=row['timestamp'],
                    agent_id=row['agent_id'],
                    agent_name=row['agent_name'],
                    session_id=row['session_id'],
                    reason=row['reason'],
                    tags=json.loads(row['tags']),
                    size_bytes=row['size_bytes'],
                    hash_sha256=row['hash_sha256'],
                    parent_version=row['parent_version'],
                    is_creation=bool(row['is_creation']),
                    diff_size=row['diff_size']
                ))
        
        return versions
    
    def reconstruct_version(self, file_path: str, version_id: str = None) -> str:
        """
        Reconstruct a file at a specific version by applying diffs.
        
        Args:
            file_path: Path to the file
            version_id: Version to reconstruct (default: latest)
        
        Returns:
            File content at that version
        """
        # Get version chain
        if not version_id:
            # Get latest version
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT version_id FROM versions WHERE file_path = ? ORDER BY timestamp DESC LIMIT 1",
                    (file_path,)
                )
                row = cursor.fetchone()
                if not row:
                    return ""
                version_id = row[0]
        
        # Build chain from version to creation
        chain = []
        current = version_id
        
        while current:
            metadata = self.get_version_metadata(current)
            if not metadata:
                break
            
            chain.append(metadata)
            
            if metadata.is_creation:
                break
            
            current = metadata.parent_version
        
        # Reverse chain to go from creation to target
        chain.reverse()
        
        # Reconstruct content
        content = ""
        
        for i, version in enumerate(chain):
            if version.is_creation:
                # First version - read full content
                content = self._read_full_content(version.version_id)
            else:
                # Apply diff
                diff_text = self._read_diff(version.version_id)
                if diff_text:
                    content = self._apply_diff(content, diff_text)
        
        return content
    
    def compute_diff(self, file_path: str, version_a: str = None, 
                    version_b: str = None) -> str:
        """
        Compute diff between two versions.
        
        Args:
            file_path: Path to file
            version_a: First version (default: previous)
            version_b: Second version (default: current)
        
        Returns:
            Unified diff as string
        """
        # Get versions
        if not version_b:
            # Get latest
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT version_id FROM versions WHERE file_path = ? ORDER BY timestamp DESC LIMIT 1",
                    (file_path,)
                )
                row = cursor.fetchone()
                if row:
                    version_b = row[0]
        
        if not version_a:
            # Get previous to version_b
            metadata_b = self.get_version_metadata(version_b)
            if metadata_b and metadata_b.parent_version:
                version_a = metadata_b.parent_version
        
        # Reconstruct both versions
        content_a = self.reconstruct_version(file_path, version_a) if version_a else ""
        content_b = self.reconstruct_version(file_path, version_b) if version_b else ""
        
        # Generate diff
        diff = difflib.unified_diff(
            content_a.splitlines(keepends=True),
            content_b.splitlines(keepends=True),
            fromfile=f"{file_path} ({version_a or 'none'})",
            tofile=f"{file_path} ({version_b or 'current'})",
            lineterm=''
        )
        
        return '\n'.join(diff)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the version store."""
        with sqlite3.connect(self.db_path) as conn:
            # Total versions
            total_versions = conn.execute("SELECT COUNT(*) FROM versions").fetchone()[0]
            
            # Total files tracked
            total_files = conn.execute(
                "SELECT COUNT(DISTINCT file_path) FROM versions"
            ).fetchone()[0]
            
            # Total storage used (diffs)
            total_diff_size = conn.execute(
                "SELECT SUM(diff_size) FROM versions"
            ).fetchone()[0] or 0
            
            # Total original size
            total_original_size = conn.execute(
                "SELECT SUM(size_bytes) FROM versions"
            ).fetchone()[0] or 0
            
            # Most edited files
            cursor = conn.execute("""
                SELECT file_path, COUNT(*) as edits 
                FROM versions 
                GROUP BY file_path 
                ORDER BY edits DESC 
                LIMIT 5
            """)
            most_edited = [{"file": row[0], "edits": row[1]} for row in cursor]
        
        return {
            "total_versions": total_versions,
            "total_files": total_files,
            "storage_used_bytes": total_diff_size,
            "storage_saved_bytes": total_original_size - total_diff_size,
            "compression_ratio": f"{(total_diff_size / total_original_size * 100):.1f}%" if total_original_size > 0 else "0%",
            "most_edited_files": most_edited
        }


# ============================================================================
# VERSIONED FILE TOOLS
# ============================================================================

class VersionedFileTools:
    """Tools for versioned file operations."""
    
    def __init__(self, agent, versions_dir: str = ".vera-versions"):
        self.agent = agent
        self.store = LightweightVersionStore(versions_dir)
        
        # Get agent info
        self.agent_id = getattr(agent, 'agent_id', 'unknown')
        self.agent_name = getattr(agent, 'name', 'Vera')
    
    def write_versioned_file(self, file_path: str, content: str, 
                            reason: str, tags: Optional[List[str]] = None) -> str:
        """
        Write a file with automatic versioning.
        
        This creates a new version of the file with full metadata tracking.
        All changes are recorded with reason, timestamp, and agent information.
        
        Args:
            file_path: Path to the file to write
            content: New file content
            reason: Reason for this change (e.g., "Fixed bug in parser", "Added error handling")
            tags: Optional tags for categorizing (e.g., ["bugfix", "critical"])
        
        The system automatically:
        - Creates a compressed diff from previous version
        - Records metadata (timestamp, agent, reason)
        - Enables future rollback to any version
        - Maintains minimal storage overhead
        
        Example:
            write_versioned_file(
                file_path="./config.json",
                content='{"api_key": "new_key"}',
                reason="Updated API key for production",
                tags=["config", "production"]
            )
        """
        try:
            # Resolve path
            file_path = str(Path(file_path).resolve())
            
            # Save version
            metadata = self.store.save_version(
                file_path=file_path,
                content=content,
                reason=reason,
                agent_id=self.agent_id,
                agent_name=self.agent_name,
                session_id=getattr(self.agent.sess, 'id', 'unknown'),
                tags=tags
            )
            
            # Write actual file
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            Path(file_path).write_text(content)
            
            # Store in agent memory
            self.agent.mem.add_session_memory(
                self.agent.sess.id,
                file_path,
                "versioned_file_write",
                metadata={
                    "version_id": metadata.version_id,
                    "reason": reason,
                    "size": metadata.size_bytes
                }
            )
            
            output = [
                f"✓ File saved: {file_path}",
                f"Version ID: {metadata.version_id}",
                f"Reason: {reason}",
                f"Size: {metadata.size_bytes} bytes",
                f"Diff storage: {metadata.diff_size} bytes",
                f"Compression: {(metadata.diff_size / metadata.size_bytes * 100):.1f}%" if metadata.size_bytes > 0 else "New file"
            ]
            
            if metadata.parent_version:
                output.append(f"Previous version: {metadata.parent_version}")
            
            if tags:
                output.append(f"Tags: {', '.join(tags)}")
            
            return "\n".join(output)
            
        except Exception as e:
            return f"[Error] Failed to save versioned file: {str(e)}"
    
    def read_versioned_file(self, file_path: str, version_id: Optional[str] = None) -> str:
        """
        Read a file at a specific version.
        
        Args:
            file_path: Path to the file
            version_id: Specific version ID to read (default: latest/current)
        
        If no version_id is provided, reads the current file.
        If version_id is provided, reconstructs that historical version.
        
        Example:
            # Read current version
            read_versioned_file("./config.json")
            
            # Read specific historical version
            read_versioned_file("./config.json", version_id="a1b2c3d4")
        """
        try:
            file_path = str(Path(file_path).resolve())
            
            if version_id:
                # Reconstruct historical version
                content = self.store.reconstruct_version(file_path, version_id)
                
                if not content:
                    return f"[Error] Version not found: {version_id}"
                
                metadata = self.store.get_version_metadata(version_id)
                
                output = [
                    f"File: {file_path}",
                    f"Version: {version_id}",
                    f"Timestamp: {metadata.timestamp}",
                    f"Reason: {metadata.reason}",
                    f"Agent: {metadata.agent_name}",
                    f"\n--- Content ---\n",
                    content
                ]
                
                return "\n".join(output)
            else:
                # Read current file
                if not Path(file_path).exists():
                    return f"[Error] File not found: {file_path}"
                
                content = Path(file_path).read_text()
                return content
            
        except Exception as e:
            return f"[Error] Failed to read file: {str(e)}"
    
    def query_file_history(self, file_path: Optional[str] = None, 
                          limit: int = 20, tags: Optional[List[str]] = None,
                          agent_id: Optional[str] = None) -> str:
        """
        Query version history for files.
        
        Args:
            file_path: Specific file to query (None for all files)
            limit: Number of versions to show
            tags: Filter by tags
            agent_id: Filter by agent ID
        
        Shows a log of all changes with metadata.
        
        Example:
            # Show history for specific file
            query_file_history(file_path="./config.json", limit=10)
            
            # Show all changes by current agent
            query_file_history(agent_id="vera-001", limit=50)
            
            # Show all changes with "bugfix" tag
            query_file_history(tags=["bugfix"])
        """
        try:
            if file_path:
                file_path = str(Path(file_path).resolve())
            
            versions = self.store.get_file_history(
                file_path=file_path,
                limit=limit,
                tags=tags,
                agent_id=agent_id
            )
            
            if not versions:
                return "No version history found"
            
            output = [f"Version History ({len(versions)} versions):\n"]
            
            for v in versions:
                timestamp_short = v.timestamp.split('T')[0] + ' ' + v.timestamp.split('T')[1][:8]
                
                output.append(f"{'='*60}")
                output.append(f"Version: {v.version_id}")
                output.append(f"File: {v.file_path}")
                output.append(f"Time: {timestamp_short}")
                output.append(f"Agent: {v.agent_name} ({v.agent_id})")
                output.append(f"Reason: {v.reason}")
                
                if v.tags:
                    output.append(f"Tags: {', '.join(v.tags)}")
                
                output.append(f"Size: {v.size_bytes} bytes (diff: {v.diff_size} bytes)")
                
                if v.parent_version:
                    output.append(f"Parent: {v.parent_version}")
                else:
                    output.append("(Initial version)")
                
                output.append("")
            
            return "\n".join(output)
            
        except Exception as e:
            return f"[Error] Failed to query history: {str(e)}"
    
    def view_file_diff(self, file_path: str, version_a: Optional[str] = None,
                      version_b: Optional[str] = None) -> str:
        """
        View differences between two versions of a file.
        
        Args:
            file_path: Path to the file
            version_a: First version ID (default: previous)
            version_b: Second version ID (default: current)
        
        Shows a unified diff highlighting changes.
        
        Example:
            # Compare current with previous
            view_file_diff("./config.json")
            
            # Compare two specific versions
            view_file_diff("./config.json", version_a="abc123", version_b="def456")
        """
        try:
            file_path = str(Path(file_path).resolve())
            
            diff = self.store.compute_diff(file_path, version_a, version_b)
            
            if not diff:
                return "No differences found"
            
            output = [
                f"Diff for: {file_path}",
                f"From: {version_a or 'previous'}",
                f"To: {version_b or 'current'}",
                "",
                diff
            ]
            
            return "\n".join(output)
            
        except Exception as e:
            return f"[Error] Failed to compute diff: {str(e)}"
    
    def revert_file(self, file_path: str, version_id: str, 
                   reason: str = "Reverted to previous version") -> str:
        """
        Revert a file to a previous version.
        
        This creates a NEW version with the content from the specified old version.
        The revert itself is versioned, so nothing is ever truly lost.
        
        Args:
            file_path: Path to the file
            version_id: Version ID to revert to
            reason: Reason for reverting
        
        Example:
            revert_file(
                file_path="./config.json",
                version_id="a1b2c3d4",
                reason="Reverting bad API key change"
            )
        """
        try:
            file_path = str(Path(file_path).resolve())
            
            # Reconstruct old version
            old_content = self.store.reconstruct_version(file_path, version_id)
            
            if not old_content:
                return f"[Error] Version not found: {version_id}"
            
            old_metadata = self.store.get_version_metadata(version_id)
            
            # Save as new version
            new_metadata = self.store.save_version(
                file_path=file_path,
                content=old_content,
                reason=f"{reason} (reverted to {version_id})",
                agent_id=self.agent_id,
                agent_name=self.agent_name,
                session_id=getattr(self.agent.sess, 'id', 'unknown'),
                tags=["revert"]
            )
            
            # Write file
            Path(file_path).write_text(old_content)
            
            output = [
                f"✓ File reverted: {file_path}",
                f"Reverted to: {version_id}",
                f"  Timestamp: {old_metadata.timestamp}",
                f"  Reason: {old_metadata.reason}",
                f"\nNew version: {new_metadata.version_id}",
                f"Revert reason: {reason}"
            ]
            
            return "\n".join(output)
            
        except Exception as e:
            return f"[Error] Failed to revert file: {str(e)}"
    
    def get_version_stats(self) -> str:
        """
        Get statistics about the versioning system.
        
        Shows storage usage, compression ratios, most edited files, etc.
        """
        try:
            stats = self.store.get_stats()
            
            output = [
                "Version Store Statistics:",
                "",
                f"Total versions: {stats['total_versions']}",
                f"Files tracked: {stats['total_files']}",
                f"Storage used: {stats['storage_used_bytes']:,} bytes",
                f"Storage saved: {stats['storage_saved_bytes']:,} bytes",
                f"Compression ratio: {stats['compression_ratio']}",
                "",
                "Most edited files:"
            ]
            
            for item in stats['most_edited_files']:
                output.append(f"  {item['file']}: {item['edits']} edits")
            
            return "\n".join(output)
            
        except Exception as e:
            return f"[Error] Failed to get stats: {str(e)}"


# ============================================================================
# ADD TO TOOLLOADER FUNCTION
# ============================================================================

def add_versioned_file_tools(tool_list: List, agent, versions_dir: str = ".vera-versions"):
    """
    Add lightweight file versioning tools to the tool list.
    
    Provides Git-like versioning for LLM file operations with:
    - Automatic version tracking with metadata
    - Diff-based storage for minimal overhead
    - Complete history with reasons and timestamps
    - Revert capabilities
    - Agent and session tracking
    
    Call this in your ToolLoader function:
        tool_list = ToolLoader(agent)
        add_versioned_file_tools(tool_list, agent)
        return tool_list
    
    Storage is completely separate from Git and uses compressed diffs.
    """
    
    versioned_tools = VersionedFileTools(agent, versions_dir)
    
    tool_list.extend([
        StructuredTool.from_function(
            func=versioned_tools.write_versioned_file,
            name="write_versioned_file",
            description=(
                "Write a file with automatic versioning. "
                "Creates compressed diff from previous version, records metadata "
                "(timestamp, agent, reason, tags). Enables rollback to any version. "
                "Use this instead of regular file writes when you want version control."
            ),
            args_schema=VersionedFileWriteInput
        ),
        
        StructuredTool.from_function(
            func=versioned_tools.read_versioned_file,
            name="read_versioned_file",
            description=(
                "Read a file at current or historical version. "
                "Can reconstruct any past version by version ID. "
                "Useful for reviewing changes or comparing versions."
            ),
            args_schema=VersionedFileReadInput
        ),
        
        StructuredTool.from_function(
            func=versioned_tools.query_file_history,
            name="query_file_history",
            description=(
                "Query version history for files. "
                "Shows log of changes with timestamps, reasons, agents. "
                "Filter by file, tags, or agent. Like 'git log' but for versioned files."
            ),
            args_schema=FileHistoryQueryInput
        ),
        
        StructuredTool.from_function(
            func=versioned_tools.view_file_diff,
            name="view_file_diff",
            description=(
                "View unified diff between two versions. "
                "Compare current with previous, or any two specific versions. "
                "Shows exactly what changed. Like 'git diff'."
            ),
            args_schema=FileDiffInput
        ),
        
        StructuredTool.from_function(
            func=versioned_tools.revert_file,
            name="revert_file",
            description=(
                "Revert file to a previous version. "
                "Creates new version with old content - nothing is lost. "
                "The revert itself is tracked. Like 'git revert'."
            ),
            args_schema=FileRevertInput
        ),
        
        StructuredTool.from_function(
            func=versioned_tools.get_version_stats,
            name="get_version_stats",
            description=(
                "Get statistics about the versioning system. "
                "Shows storage usage, compression ratios, most edited files. "
                "Useful for monitoring system overhead."
            ),
        ),
    ])
    
    return tool_list

"""
Enhanced Rollback System for Versioned Files
Makes rolling back changes intuitive and easy
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
import json

# ============================================================================
# ADDITIONAL INPUT SCHEMAS FOR EASY ROLLBACK
# ============================================================================

class QuickRollbackInput(BaseModel):
    """Input for quick rollback operations."""
    file_path: str = Field(..., description="Path to the file")
    steps_back: int = Field(
        default=1,
        description="Number of versions to go back (1 = previous version)"
    )
    reason: str = Field(
        default="Quick rollback",
        description="Reason for rollback"
    )


class TimeBasedRollbackInput(BaseModel):
    """Input for time-based rollback."""
    file_path: str = Field(..., description="Path to the file")
    target_time: str = Field(
        ...,
        description="Target time (e.g., '2024-01-15 14:30', 'yesterday', '2 hours ago')"
    )
    reason: str = Field(
        default="Time-based rollback",
        description="Reason for rollback"
    )


class SessionRollbackInput(BaseModel):
    """Input for session-based rollback."""
    session_id: Optional[str] = Field(
        default=None,
        description="Session ID to rollback (default: current session)"
    )
    file_path: Optional[str] = Field(
        default=None,
        description="Specific file (default: all files from session)"
    )
    reason: str = Field(
        default="Session rollback",
        description="Reason for rollback"
    )


class BulkRollbackInput(BaseModel):
    """Input for bulk rollback operations."""
    file_paths: List[str] = Field(..., description="List of files to rollback")
    target_version_ids: Optional[Dict[str, str]] = Field(
        default=None,
        description="Map of file_path to version_id (default: previous for all)"
    )
    reason: str = Field(
        default="Bulk rollback",
        description="Reason for rollback"
    )


class RollbackPreviewInput(BaseModel):
    """Input for previewing rollback changes."""
    file_path: str = Field(..., description="Path to the file")
    target_version: Optional[str] = Field(
        default=None,
        description="Target version ID (default: previous)"
    )


class TagBasedRollbackInput(BaseModel):
    """Input for rolling back files by tag."""
    tags: List[str] = Field(..., description="Tags to filter by")
    before_timestamp: str = Field(
        ...,
        description="Rollback changes made after this timestamp"
    )
    reason: str = Field(
        default="Tag-based rollback",
        description="Reason for rollback"
    )


# ============================================================================
# ENHANCED ROLLBACK SYSTEM
# ============================================================================

class EnhancedRollbackSystem:
    """Enhanced rollback capabilities for easy version management."""
    
    def __init__(self, store: 'LightweightVersionStore', agent):
        self.store = store
        self.agent = agent
        self.agent_id = getattr(agent, 'agent_id', 'unknown')
        self.agent_name = getattr(agent, 'name', 'Vera')
    
    def _parse_relative_time(self, time_str: str) -> datetime:
        """Parse relative time strings like 'yesterday', '2 hours ago'."""
        now = datetime.now()
        time_str = time_str.lower().strip()
        
        if time_str == "yesterday":
            return now - timedelta(days=1)
        elif time_str == "today":
            return now.replace(hour=0, minute=0, second=0)
        elif "hour" in time_str:
            # Parse "2 hours ago", "3 hour ago"
            parts = time_str.split()
            if len(parts) >= 2 and parts[0].isdigit():
                hours = int(parts[0])
                return now - timedelta(hours=hours)
        elif "minute" in time_str:
            parts = time_str.split()
            if len(parts) >= 2 and parts[0].isdigit():
                minutes = int(parts[0])
                return now - timedelta(minutes=minutes)
        elif "day" in time_str:
            parts = time_str.split()
            if len(parts) >= 2 and parts[0].isdigit():
                days = int(parts[0])
                return now - timedelta(days=days)
        elif "week" in time_str:
            parts = time_str.split()
            if len(parts) >= 2 and parts[0].isdigit():
                weeks = int(parts[0])
                return now - timedelta(weeks=weeks)
        else:
            # Try parsing as ISO format
            try:
                return datetime.fromisoformat(time_str.replace(' ', 'T'))
            except:
                # Try parsing as simple date/time
                try:
                    return datetime.strptime(time_str, "%Y-%m-%d %H:%M")
                except:
                    try:
                        return datetime.strptime(time_str, "%Y-%m-%d")
                    except:
                        return now
        
        return now
    
    def quick_rollback(self, file_path: str, steps_back: int = 1, 
                      reason: str = "Quick rollback") -> str:
        """
        Quick rollback - go back N versions.
        
        This is the easiest way to undo changes.
        
        Args:
            file_path: File to rollback
            steps_back: Number of versions to go back (1 = undo last change)
            reason: Reason for rollback
        
        Examples:
            quick_rollback("config.json", 1)  # Undo last change
            quick_rollback("config.json", 3)  # Go back 3 versions
        """
        file_path = str(Path(file_path).resolve())
        
        # Get version history
        versions = self.store.get_file_history(file_path=file_path, limit=steps_back + 1)
        
        if len(versions) <= steps_back:
            return f"[Error] Cannot go back {steps_back} versions. Only {len(versions)-1} previous versions exist."
        
        # Target version is at index steps_back (0 is current)
        target_version = versions[steps_back]
        
        # Get current version for comparison
        current_version = versions[0]
        
        # Reconstruct target content
        target_content = self.store.reconstruct_version(file_path, target_version.version_id)
        
        # Save as new version
        new_metadata = self.store.save_version(
            file_path=file_path,
            content=target_content,
            reason=f"{reason} (rolled back {steps_back} version{'s' if steps_back > 1 else ''})",
            agent_id=self.agent_id,
            agent_name=self.agent_name,
            session_id=getattr(self.agent.sess, 'id', 'unknown'),
            tags=["rollback", "quick"]
        )
        
        # Write file
        Path(file_path).write_text(target_content)
        
        output = [
            f"✓ Quick rollback completed: {file_path}",
            f"Rolled back: {steps_back} version{'s' if steps_back > 1 else ''}",
            "",
            f"From version:",
            f"  ID: {current_version.version_id}",
            f"  Time: {current_version.timestamp}",
            f"  Reason: {current_version.reason}",
            "",
            f"To version:",
            f"  ID: {target_version.version_id}",
            f"  Time: {target_version.timestamp}",
            f"  Reason: {target_version.reason}",
            "",
            f"New version ID: {new_metadata.version_id}"
        ]
        
        return "\n".join(output)
    
    def time_based_rollback(self, file_path: str, target_time: str,
                           reason: str = "Time-based rollback") -> str:
        """
        Rollback to how the file was at a specific time.
        
        Supports natural language like "yesterday", "2 hours ago", etc.
        
        Args:
            file_path: File to rollback
            target_time: Target time (various formats supported)
            reason: Reason for rollback
        
        Examples:
            time_based_rollback("config.json", "yesterday")
            time_based_rollback("config.json", "2 hours ago")
            time_based_rollback("config.json", "2024-01-15 14:30")
        """
        file_path = str(Path(file_path).resolve())
        
        # Parse target time
        target_dt = self._parse_relative_time(target_time)
        target_iso = target_dt.isoformat()
        
        # Get all versions
        versions = self.store.get_file_history(file_path=file_path, limit=1000)
        
        # Find closest version before target time
        target_version = None
        for version in reversed(versions):  # Start from oldest
            if version.timestamp <= target_iso:
                target_version = version
        
        if not target_version:
            return f"[Error] No version found before {target_time} ({target_iso})"
        
        # Reconstruct target content
        target_content = self.store.reconstruct_version(file_path, target_version.version_id)
        
        # Save as new version
        new_metadata = self.store.save_version(
            file_path=file_path,
            content=target_content,
            reason=f"{reason} (to {target_time})",
            agent_id=self.agent_id,
            agent_name=self.agent_name,
            session_id=getattr(self.agent.sess, 'id', 'unknown'),
            tags=["rollback", "time-based"]
        )
        
        # Write file
        Path(file_path).write_text(target_content)
        
        output = [
            f"✓ Time-based rollback completed: {file_path}",
            f"Target time: {target_time}",
            f"Actual version: {target_version.timestamp}",
            "",
            f"Restored version:",
            f"  ID: {target_version.version_id}",
            f"  Reason: {target_version.reason}",
            f"  Agent: {target_version.agent_name}",
            "",
            f"New version ID: {new_metadata.version_id}"
        ]
        
        return "\n".join(output)
    
    def session_rollback(self, session_id: Optional[str] = None,
                        file_path: Optional[str] = None,
                        reason: str = "Session rollback") -> str:
        """
        Rollback all changes made in a session.
        
        Useful for undoing a batch of related changes.
        
        Args:
            session_id: Session to rollback (default: current session)
            file_path: Specific file (default: all files modified in session)
            reason: Reason for rollback
        
        Examples:
            session_rollback()  # Undo everything in current session
            session_rollback(file_path="config.json")  # Undo config.json changes in current session
            session_rollback(session_id="sess_123")  # Undo specific session
        """
        if not session_id:
            session_id = getattr(self.agent.sess, 'id', 'unknown')
        
        # Get all versions from this session
        versions = self.store.get_file_history(limit=1000)
        session_versions = [v for v in versions if v.session_id == session_id]
        
        if file_path:
            file_path = str(Path(file_path).resolve())
            session_versions = [v for v in session_versions if v.file_path == file_path]
        
        if not session_versions:
            return f"[Error] No versions found for session: {session_id}"
        
        # Group by file
        files_to_rollback = {}
        for version in session_versions:
            if version.file_path not in files_to_rollback:
                files_to_rollback[version.file_path] = []
            files_to_rollback[version.file_path].append(version)
        
        results = []
        rolled_back_count = 0
        
        for fpath, file_versions in files_to_rollback.items():
            # Get the version just before the first session change
            oldest_session_version = file_versions[-1]  # Last in list (oldest)
            
            if oldest_session_version.parent_version:
                # Rollback to parent
                target_content = self.store.reconstruct_version(
                    fpath, 
                    oldest_session_version.parent_version
                )
                
                # Save new version
                new_metadata = self.store.save_version(
                    file_path=fpath,
                    content=target_content,
                    reason=f"{reason} (session {session_id})",
                    agent_id=self.agent_id,
                    agent_name=self.agent_name,
                    session_id=getattr(self.agent.sess, 'id', 'unknown'),
                    tags=["rollback", "session"]
                )
                
                # Write file
                Path(fpath).write_text(target_content)
                
                results.append(f"  ✓ {fpath} (rolled back {len(file_versions)} changes)")
                rolled_back_count += 1
            else:
                results.append(f"  ⚠ {fpath} (was created in this session, not rolled back)")
        
        output = [
            f"✓ Session rollback completed",
            f"Session ID: {session_id}",
            f"Files rolled back: {rolled_back_count}",
            "",
            "Results:"
        ] + results
        
        return "\n".join(output)
    
    def bulk_rollback(self, file_paths: List[str], 
                     target_version_ids: Optional[Dict[str, str]] = None,
                     reason: str = "Bulk rollback") -> str:
        """
        Rollback multiple files at once.
        
        Args:
            file_paths: List of files to rollback
            target_version_ids: Optional map of file to specific version
            reason: Reason for rollback
        
        Example:
            bulk_rollback(
                file_paths=["config.json", "settings.py", "database.sql"],
                reason="Reverting failed deployment"
            )
        """
        results = []
        success_count = 0
        
        for fpath in file_paths:
            try:
                fpath = str(Path(fpath).resolve())
                
                # Get target version
                if target_version_ids and fpath in target_version_ids:
                    target_version_id = target_version_ids[fpath]
                else:
                    # Use previous version
                    versions = self.store.get_file_history(file_path=fpath, limit=2)
                    if len(versions) < 2:
                        results.append(f"  ⚠ {fpath}: No previous version")
                        continue
                    target_version_id = versions[1].version_id
                
                # Reconstruct content
                target_content = self.store.reconstruct_version(fpath, target_version_id)
                
                # Save new version
                new_metadata = self.store.save_version(
                    file_path=fpath,
                    content=target_content,
                    reason=f"{reason} (bulk operation)",
                    agent_id=self.agent_id,
                    agent_name=self.agent_name,
                    session_id=getattr(self.agent.sess, 'id', 'unknown'),
                    tags=["rollback", "bulk"]
                )
                
                # Write file
                Path(fpath).write_text(target_content)
                
                results.append(f"  ✓ {fpath}")
                success_count += 1
                
            except Exception as e:
                results.append(f"  ✗ {fpath}: {str(e)}")
        
        output = [
            f"✓ Bulk rollback completed",
            f"Successfully rolled back: {success_count}/{len(file_paths)}",
            "",
            "Results:"
        ] + results
        
        return "\n".join(output)
    
    def preview_rollback(self, file_path: str, target_version: Optional[str] = None) -> str:
        """
        Preview what would change if you rollback.
        
        Shows diff without actually making changes.
        
        Args:
            file_path: File to preview
            target_version: Target version (default: previous)
        
        Example:
            preview_rollback("config.json")  # Preview undoing last change
        """
        file_path = str(Path(file_path).resolve())
        
        # Get current content
        if not Path(file_path).exists():
            return f"[Error] File not found: {file_path}"
        
        current_content = Path(file_path).read_text()
        
        # Get target version
        if not target_version:
            versions = self.store.get_file_history(file_path=file_path, limit=2)
            if len(versions) < 2:
                return "[Error] No previous version to preview"
            target_version = versions[1].version_id
        
        # Reconstruct target content
        target_content = self.store.reconstruct_version(file_path, target_version)
        
        # Generate diff
        import difflib
        diff = difflib.unified_diff(
            current_content.splitlines(keepends=True),
            target_content.splitlines(keepends=True),
            fromfile=f"{file_path} (current)",
            tofile=f"{file_path} (after rollback)",
            lineterm=''
        )
        
        diff_text = '\n'.join(diff)
        
        # Get metadata
        metadata = self.store.get_version_metadata(target_version)
        
        output = [
            f"Rollback Preview: {file_path}",
            f"",
            f"Would rollback to:",
            f"  Version: {target_version}",
            f"  Time: {metadata.timestamp}",
            f"  Reason: {metadata.reason}",
            f"  Agent: {metadata.agent_name}",
            "",
            "Changes that would be undone:",
            "",
            diff_text if diff_text else "No changes (files are identical)"
        ]
        
        return "\n".join(output)
    
    def tag_based_rollback(self, tags: List[str], before_timestamp: str,
                          reason: str = "Tag-based rollback") -> str:
        """
        Rollback all files with specific tags modified after a timestamp.
        
        Useful for rolling back themed changes (e.g., all "experiment" changes).
        
        Args:
            tags: Tags to filter by
            before_timestamp: Rollback changes made after this time
            reason: Reason for rollback
        
        Example:
            tag_based_rollback(
                tags=["experiment"],
                before_timestamp="yesterday",
                reason="Reverting failed experiment"
            )
        """
        # Parse timestamp
        cutoff_dt = self._parse_relative_time(before_timestamp)
        cutoff_iso = cutoff_dt.isoformat()
        
        # Get all versions with these tags after cutoff
        all_versions = self.store.get_file_history(tags=tags, limit=1000)
        affected_versions = [v for v in all_versions if v.timestamp > cutoff_iso]
        
        if not affected_versions:
            return f"[Error] No versions found with tags {tags} after {before_timestamp}"
        
        # Group by file
        files_to_rollback = {}
        for version in affected_versions:
            if version.file_path not in files_to_rollback:
                files_to_rollback[version.file_path] = []
            files_to_rollback[version.file_path].append(version)
        
        results = []
        success_count = 0
        
        for fpath, file_versions in files_to_rollback.items():
            try:
                # Find version just before cutoff
                oldest_affected = file_versions[-1]
                
                if oldest_affected.parent_version:
                    target_content = self.store.reconstruct_version(
                        fpath,
                        oldest_affected.parent_version
                    )
                    
                    # Save new version
                    new_metadata = self.store.save_version(
                        file_path=fpath,
                        content=target_content,
                        reason=f"{reason} (tags: {', '.join(tags)})",
                        agent_id=self.agent_id,
                        agent_name=self.agent_name,
                        session_id=getattr(self.agent.sess, 'id', 'unknown'),
                        tags=["rollback", "tag-based"]
                    )
                    
                    # Write file
                    Path(fpath).write_text(target_content)
                    
                    results.append(f"  ✓ {fpath} ({len(file_versions)} changes)")
                    success_count += 1
                else:
                    results.append(f"  ⚠ {fpath} (created after cutoff)")
                    
            except Exception as e:
                results.append(f"  ✗ {fpath}: {str(e)}")
        
        output = [
            f"✓ Tag-based rollback completed",
            f"Tags: {', '.join(tags)}",
            f"Cutoff: {before_timestamp} ({cutoff_iso})",
            f"Files rolled back: {success_count}",
            "",
            "Results:"
        ] + results
        
        return "\n".join(output)
    
    def undo_last_change(self, file_path: str) -> str:
        """
        Ultra-quick undo - just reverts the last change.
        
        This is the fastest way to undo a mistake.
        
        Example:
            undo_last_change("config.json")
        """
        return self.quick_rollback(file_path, steps_back=1, reason="Undo last change")


# ============================================================================
# UPDATE VERSIONED FILE TOOLS CLASS
# ============================================================================

def enhance_versioned_file_tools(tool_list: List, agent, versions_dir: str = ".vera-versions"):
    """
    Add enhanced rollback capabilities to versioned file tools.
    
    Call this INSTEAD of add_versioned_file_tools, or call it after to add rollback tools.
    """
    from Vera.Toolchain.tools import VersionedFileTools, LightweightVersionStore
    
    versioned_tools = VersionedFileTools(agent, versions_dir)
    rollback_system = EnhancedRollbackSystem(versioned_tools.store, agent)
    
    # Add base versioning tools
    tool_list.extend([
        StructuredTool.from_function(
            func=versioned_tools.write_versioned_file,
            name="write_versioned_file",
            description=(
                "Write a file with automatic versioning. "
                "Creates compressed diff, records metadata. Easy to rollback later."
            ),
            args_schema=VersionedFileWriteInput
        ),
        
        StructuredTool.from_function(
            func=versioned_tools.read_versioned_file,
            name="read_versioned_file",
            description="Read current or historical version of a file.",
            args_schema=VersionedFileReadInput
        ),
        
        StructuredTool.from_function(
            func=versioned_tools.query_file_history,
            name="query_file_history",
            description="View version history log with timestamps, reasons, agents.",
            args_schema=FileHistoryQueryInput
        ),
        
        StructuredTool.from_function(
            func=versioned_tools.view_file_diff,
            name="view_file_diff",
            description="View diff between versions. See exactly what changed.",
            args_schema=FileDiffInput
        ),
        
        StructuredTool.from_function(
            func=versioned_tools.get_version_stats,
            name="get_version_stats",
            description="Get versioning system statistics and storage usage.",
        ),
    ])
    
    # Add enhanced rollback tools
    tool_list.extend([
        StructuredTool.from_function(
            func=rollback_system.undo_last_change,
            name="undo_last_change",
            description=(
                "FASTEST WAY TO UNDO: Instantly reverts last change to a file. "
                "Use when you made a mistake and want to quickly undo it. "
                "Example: undo_last_change('config.json')"
            ),
            args_schema=VersionedFileReadInput
        ),
        
        StructuredTool.from_function(
            func=rollback_system.quick_rollback,
            name="quick_rollback",
            description=(
                "Quick rollback: Go back N versions. "
                "steps_back=1 undoes last change, steps_back=3 goes back 3 versions. "
                "Simple and intuitive. Example: quick_rollback('file.py', 2)"
            ),
            args_schema=QuickRollbackInput
        ),
        
        StructuredTool.from_function(
            func=rollback_system.time_based_rollback,
            name="time_based_rollback",
            description=(
                "Rollback to how file was at specific time. "
                "Supports natural language: 'yesterday', '2 hours ago', '2024-01-15'. "
                "Example: time_based_rollback('config.json', 'yesterday')"
            ),
            args_schema=TimeBasedRollbackInput
        ),
        
        StructuredTool.from_function(
            func=rollback_system.session_rollback,
            name="session_rollback",
            description=(
                "Rollback all changes from a session. "
                "Undo everything you did in current or specific session. "
                "Example: session_rollback() undoes all current session changes"
            ),
            args_schema=SessionRollbackInput
        ),
        
        StructuredTool.from_function(
            func=rollback_system.bulk_rollback,
            name="bulk_rollback",
            description=(
                "Rollback multiple files at once. "
                "Efficient for rolling back related changes across many files. "
                "Example: bulk_rollback(['file1.py', 'file2.py', 'config.json'])"
            ),
            args_schema=BulkRollbackInput
        ),
        
        StructuredTool.from_function(
            func=rollback_system.preview_rollback,
            name="preview_rollback",
            description=(
                "Preview rollback WITHOUT making changes. "
                "See what would change before actually rolling back. "
                "Safe way to check before undoing. Example: preview_rollback('config.json')"
            ),
            args_schema=RollbackPreviewInput
        ),
        
        StructuredTool.from_function(
            func=rollback_system.tag_based_rollback,
            name="tag_based_rollback",
            description=(
                "Rollback files by tags. "
                "Undo all changes with specific tags after a timestamp. "
                "Example: tag_based_rollback(['experiment'], 'yesterday')"
            ),
            args_schema=TagBasedRollbackInput
        ),
    ])
    
    return tool_list


# Update the main add function
def add_versioned_file_tools(tool_list: List, agent, versions_dir: str = ".vera-versions"):
    """
    Add complete versioned file system with easy rollback.
    
    Includes:
    - Automatic versioning with metadata
    - Multiple rollback methods (quick, time-based, session, bulk)
    - Preview before rollback
    - Undo last change (fastest)
    - Minimal storage overhead
    """
    return enhance_versioned_file_tools(tool_list, agent, versions_dir)