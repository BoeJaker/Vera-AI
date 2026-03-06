"""
Project Context Analyzer
=========================
Scans project workspace to provide context for stage execution.
Enables stages to see what's been done, what exists, and what could be improved.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from datetime import datetime
from collections import defaultdict


class ProjectContextAnalyzer:
    """
    Analyzes project workspace to provide rich context for AI stages.
    
    Features:
    - File tree scanning with filters
    - Recent file changes detection
    - Code/content statistics
    - TODO/FIXME extraction
    - Git status integration
    - Recent artifact tracking
    """
    
    def __init__(self, project_root: Path, exclude_patterns: Optional[Set[str]] = None):
        self.project_root = Path(project_root).resolve()
        
        self.exclude_patterns = exclude_patterns or {
            '.git', '__pycache__', 'node_modules', '.venv', 'venv',
            'dist', 'build', '.cache', '.pytest_cache', '.mypy_cache',
            '*.pyc', '*.pyo', '*.so', '*.dylib', '*.egg-info'
        }
    
    def get_full_context(
        self,
        include_file_tree: bool = True,
        include_recent_changes: bool = True,
        include_todos: bool = True,
        include_stats: bool = True,
        max_files_to_scan: int = 200
    ) -> Dict[str, Any]:
        """
        Get comprehensive project context.
        
        Returns rich dictionary with all available context.
        """
        context = {
            "project_root": str(self.project_root),
            "analyzed_at": datetime.utcnow().isoformat()
        }
        
        if include_file_tree:
            context["file_tree"] = self.get_file_tree(max_depth=3)
        
        if include_recent_changes:
            context["recent_changes"] = self.get_recent_file_changes(hours=24)
        
        if include_stats:
            context["statistics"] = self.get_project_statistics(max_files=max_files_to_scan)
        
        if include_todos:
            context["todos"] = self.extract_todos_and_fixmes(max_files=max_files_to_scan)
        
        # Git status if available
        context["git_status"] = self.get_git_status()
        
        return context
    
    def get_file_tree(self, max_depth: int = 3) -> Dict[str, Any]:
        """
        Get project file tree structure.
        
        Returns hierarchical structure showing directories and files.
        """
        def build_tree(path: Path, current_depth: int = 0) -> Dict[str, Any]:
            if current_depth >= max_depth:
                return {"name": path.name, "type": "truncated"}
            
            if not path.exists():
                return {}
            
            if path.is_file():
                return {
                    "name": path.name,
                    "type": "file",
                    "size": path.stat().st_size,
                    "modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat()
                }
            
            # Directory
            children = []
            try:
                for item in sorted(path.iterdir()):
                    # Skip excluded
                    if self._should_exclude(item):
                        continue
                    
                    child_node = build_tree(item, current_depth + 1)
                    if child_node:
                        children.append(child_node)
            except PermissionError:
                pass
            
            return {
                "name": path.name,
                "type": "directory",
                "children": children
            }
        
        tree = build_tree(self.project_root)
        return tree
    
    def get_recent_file_changes(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get files modified in the last N hours.
        
        Returns list of changed files with metadata.
        """
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(hours=hours)
        cutoff_timestamp = cutoff.timestamp()
        
        changes = []
        
        for filepath in self._scan_files():
            try:
                stat = filepath.stat()
                if stat.st_mtime > cutoff_timestamp:
                    changes.append({
                        "path": str(filepath.relative_to(self.project_root)),
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "age_hours": (datetime.now().timestamp() - stat.st_mtime) / 3600
                    })
            except (OSError, ValueError):
                continue
        
        # Sort by most recent first
        changes.sort(key=lambda x: x['age_hours'])
        
        return changes
    
    def get_project_statistics(self, max_files: int = 200) -> Dict[str, Any]:
        """
        Get project-wide statistics.
        
        Returns metrics about file types, sizes, counts, etc.
        """
        stats = {
            "total_files": 0,
            "total_size": 0,
            "file_types": defaultdict(int),
            "largest_files": [],
            "total_lines": 0,
            "code_files": 0,
            "doc_files": 0
        }
        
        file_sizes = []
        
        for filepath in self._scan_files(max_files=max_files):
            try:
                stat = filepath.stat()
                
                stats["total_files"] += 1
                stats["total_size"] += stat.st_size
                
                # Track extension
                ext = filepath.suffix.lower()
                stats["file_types"][ext] += 1
                
                # Track size
                file_sizes.append((filepath, stat.st_size))
                
                # Count lines for text files
                if self._is_text_file(filepath):
                    try:
                        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                            lines = len(f.readlines())
                            stats["total_lines"] += lines
                            
                            if self._is_code_file(filepath):
                                stats["code_files"] += 1
                            elif self._is_doc_file(filepath):
                                stats["doc_files"] += 1
                    except Exception:
                        pass
            except (OSError, ValueError):
                continue
        
        # Get largest files
        file_sizes.sort(key=lambda x: x[1], reverse=True)
        stats["largest_files"] = [
            {
                "path": str(f.relative_to(self.project_root)),
                "size": s
            }
            for f, s in file_sizes[:10]
        ]
        
        # Convert defaultdict to regular dict
        stats["file_types"] = dict(stats["file_types"])
        
        return stats
    
    def extract_todos_and_fixmes(self, max_files: int = 200) -> List[Dict[str, Any]]:
        """
        Extract TODO and FIXME comments from code.
        
        Returns list of todos with file location.
        """
        todos = []
        
        import re
        todo_pattern = re.compile(r'#\s*(TODO|FIXME|XXX|HACK|NOTE):\s*(.+)$', re.IGNORECASE)
        
        for filepath in self._scan_files(max_files=max_files):
            if not self._is_text_file(filepath):
                continue
            
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    for line_num, line in enumerate(f, 1):
                        match = todo_pattern.search(line)
                        if match:
                            todos.append({
                                "type": match.group(1).upper(),
                                "message": match.group(2).strip(),
                                "file": str(filepath.relative_to(self.project_root)),
                                "line": line_num
                            })
            except Exception:
                continue
        
        return todos
    
    def get_git_status(self) -> Optional[Dict[str, Any]]:
        """
        Get git repository status if available.
        
        Returns branch, uncommitted changes, etc.
        """
        git_dir = self.project_root / '.git'
        if not git_dir.exists():
            return None
        
        try:
            import subprocess
            
            # Get current branch
            branch = subprocess.check_output(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                cwd=self.project_root,
                text=True,
                stderr=subprocess.DEVNULL
            ).strip()
            
            # Get status
            status = subprocess.check_output(
                ['git', 'status', '--short'],
                cwd=self.project_root,
                text=True,
                stderr=subprocess.DEVNULL
            )
            
            # Parse status
            modified = []
            untracked = []
            for line in status.split('\n'):
                if line.startswith(' M'):
                    modified.append(line[3:])
                elif line.startswith('??'):
                    untracked.append(line[3:])
            
            return {
                "branch": branch,
                "modified_files": modified,
                "untracked_files": untracked,
                "has_changes": bool(modified or untracked)
            }
        except Exception:
            return None
    
    def get_file_content(self, relative_path: str, max_lines: int = 100) -> Optional[str]:
        """
        Get content of a specific file (for detailed inspection).
        
        Returns file content or None if not found/readable.
        """
        filepath = self.project_root / relative_path
        
        if not filepath.exists() or not filepath.is_file():
            return None
        
        if not self._is_text_file(filepath):
            return f"[Binary file: {filepath.suffix}]"
        
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                
                if len(lines) <= max_lines:
                    return ''.join(lines)
                else:
                    # Truncate
                    return ''.join(lines[:max_lines]) + f"\n... [{len(lines) - max_lines} more lines]"
        except Exception as e:
            return f"[Error reading file: {e}]"
    
    def search_files(self, pattern: str, max_results: int = 20) -> List[Dict[str, Any]]:
        """
        Search for files matching a pattern (name or content).
        
        Returns list of matching files with context.
        """
        import re
        results = []
        
        pattern_re = re.compile(pattern, re.IGNORECASE)
        
        for filepath in self._scan_files():
            # Check filename
            if pattern_re.search(filepath.name):
                results.append({
                    "path": str(filepath.relative_to(self.project_root)),
                    "match_type": "filename",
                    "size": filepath.stat().st_size
                })
                
                if len(results) >= max_results:
                    break
                continue
            
            # Check content (text files only)
            if self._is_text_file(filepath):
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        if pattern_re.search(content):
                            # Find matching line
                            for line_num, line in enumerate(content.split('\n'), 1):
                                if pattern_re.search(line):
                                    results.append({
                                        "path": str(filepath.relative_to(self.project_root)),
                                        "match_type": "content",
                                        "line": line_num,
                                        "snippet": line.strip()[:100]
                                    })
                                    break
                            
                            if len(results) >= max_results:
                                break
                except Exception:
                    continue
        
        return results
    
    def _scan_files(self, max_files: Optional[int] = None) -> List[Path]:
        """Internal: Scan all files in project (with exclusions)"""
        files = []
        count = 0
        
        for root, dirs, filenames in os.walk(self.project_root):
            # Filter directories
            dirs[:] = [d for d in dirs if not self._should_exclude(Path(root) / d)]
            
            for filename in filenames:
                filepath = Path(root) / filename
                
                if self._should_exclude(filepath):
                    continue
                
                files.append(filepath)
                count += 1
                
                if max_files and count >= max_files:
                    return files
        
        return files
    
    def _should_exclude(self, path: Path) -> bool:
        """Check if path should be excluded"""
        name = path.name
        
        # Check exact matches
        if name in self.exclude_patterns:
            return True
        
        # Check wildcard patterns
        for pattern in self.exclude_patterns:
            if '*' in pattern:
                import fnmatch
                if fnmatch.fnmatch(name, pattern):
                    return True
        
        return False
    
    def _is_text_file(self, filepath: Path) -> bool:
        """Check if file is likely text (for content reading)"""
        text_extensions = {
            '.py', '.js', '.jsx', '.ts', '.tsx', '.md', '.txt', '.json',
            '.yaml', '.yml', '.toml', '.ini', '.conf', '.cfg', '.sh',
            '.bash', '.html', '.css', '.xml', '.sql', '.rs', '.go',
            '.java', '.c', '.cpp', '.h', '.hpp', '.cs', '.rb', '.php'
        }
        
        return filepath.suffix.lower() in text_extensions
    
    def _is_code_file(self, filepath: Path) -> bool:
        """Check if file is source code"""
        code_extensions = {
            '.py', '.js', '.jsx', '.ts', '.tsx', '.rs', '.go',
            '.java', '.c', '.cpp', '.h', '.hpp', '.cs', '.rb', '.php'
        }
        return filepath.suffix.lower() in code_extensions
    
    def _is_doc_file(self, filepath: Path) -> bool:
        """Check if file is documentation"""
        doc_extensions = {'.md', '.txt', '.rst', '.adoc'}
        return filepath.suffix.lower() in doc_extensions