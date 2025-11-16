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