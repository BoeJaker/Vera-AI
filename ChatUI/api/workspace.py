# workspace_api.py - Workspace Browser API
"""
Browse sandboxed project workspaces and focus board directories.

Follows the same pattern as session_history_api_optimized.py:
- FastAPI router with prefix
- Pydantic models
- Async endpoints
- Integration with Vera memory/focus systems

Endpoints:
    GET  /api/workspaces                - List all workspaces
    GET  /api/workspaces/{id}           - Get workspace details
    GET  /api/workspaces/{id}/tree      - Get file tree
    GET  /api/workspaces/{id}/file      - Read a file
    GET  /api/workspaces/{id}/board     - Get focus board state
    POST /api/workspaces                - Create new workspace
    DELETE /api/workspaces/{id}         - Archive workspace
    GET  /api/workspaces/stats/summary  - Aggregate stats
"""

import os
import time
import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


# ============================================================
# Configuration
# ============================================================

# Default locations where workspaces live
WORKSPACE_ROOTS = [
    os.path.expanduser("~/vera_sandbox"),       # Auto-created sandboxes
    os.path.expanduser("~/vera_projects"),       # Explicit projects
]

# Focus board storage
FOCUS_BOARDS_DIR = os.path.expanduser("~/.vera/focus_boards")

# Max file size we'll return inline (bytes)
MAX_FILE_READ_SIZE = 512 * 1024  # 512KB

# Extensions considered safe to preview
TEXT_EXTENSIONS = {
    '.py', '.js', '.ts', '.jsx', '.tsx', '.json', '.yaml', '.yml',
    '.md', '.txt', '.html', '.css', '.sh', '.bash', '.toml', '.cfg',
    '.ini', '.env', '.conf', '.xml', '.csv', '.sql', '.rs', '.go',
    '.java', '.c', '.h', '.cpp', '.hpp', '.rb', '.lua', '.r',
    '.dockerfile', '.gitignore', '.editorconfig', '.log',
}


# ============================================================
# Models
# ============================================================

class WorkspaceSummary(BaseModel):
    id: str = Field(..., description="URL-safe workspace identifier")
    name: str = Field(..., description="Human-readable name")
    path: str = Field(..., description="Absolute filesystem path")
    status: str = Field(default="idle", description="active|idle|archived")
    created_at: Optional[str] = None
    last_modified: Optional[str] = None
    file_count: int = 0
    total_size_bytes: int = 0
    has_git: bool = False
    has_focus_board: bool = False
    focus_name: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class WorkspaceDetail(BaseModel):
    id: str
    name: str
    path: str
    status: str = "idle"
    created_at: Optional[str] = None
    last_modified: Optional[str] = None
    file_count: int = 0
    total_size_bytes: int = 0
    has_git: bool = False
    git_branch: Optional[str] = None
    git_status: Optional[str] = None
    has_focus_board: bool = False
    focus_board: Optional[Dict[str, Any]] = None
    recent_files: List[Dict[str, Any]] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


class FileTreeNode(BaseModel):
    name: str
    path: str  # Relative to workspace root
    type: str  # "file" | "dir"
    size: int = 0
    modified: Optional[str] = None
    children: Optional[List["FileTreeNode"]] = None
    extension: Optional[str] = None


class FileContent(BaseModel):
    path: str
    name: str
    size: int
    extension: str
    content: Optional[str] = None
    binary: bool = False
    truncated: bool = False
    mime_hint: Optional[str] = None


class CreateWorkspaceRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    template: Optional[str] = None  # "python", "node", "empty"


class WorkspaceStats(BaseModel):
    total_workspaces: int = 0
    active_workspaces: int = 0
    total_files: int = 0
    total_size_bytes: int = 0
    total_size_human: str = "0 B"
    workspaces_with_git: int = 0
    workspaces_with_focus: int = 0


# ============================================================
# Helpers
# ============================================================

def safe_id(name: str) -> str:
    """Convert a workspace name/path to a URL-safe ID."""
    return re.sub(r'[^\w\-]', '_', name.lower()).strip('_')


def human_size(size_bytes: int) -> str:
    """Format bytes as human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if abs(size_bytes) < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def get_dir_stats(path: Path, max_depth: int = 5) -> tuple:
    """Get file count and total size for a directory. Non-recursive beyond max_depth."""
    file_count = 0
    total_size = 0
    
    try:
        for item in path.rglob('*'):
            # Skip hidden dirs and common junk
            parts = item.relative_to(path).parts
            if any(p.startswith('.') or p in ('node_modules', '__pycache__', '.git', 'venv') for p in parts):
                if not (len(parts) == 1 and parts[0] == '.git'):
                    continue
            if len(parts) > max_depth:
                continue
            if item.is_file():
                file_count += 1
                try:
                    total_size += item.stat().st_size
                except OSError:
                    pass
    except (PermissionError, OSError):
        pass
    
    return file_count, total_size


def get_git_info(workspace_path: Path) -> Dict[str, Any]:
    """Get git branch and short status."""
    import subprocess
    
    git_dir = workspace_path / '.git'
    if not git_dir.exists():
        return {"has_git": False}
    
    info = {"has_git": True, "branch": None, "status": None}
    
    try:
        result = subprocess.run(
            ['git', '-C', str(workspace_path), 'branch', '--show-current'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            info["branch"] = result.stdout.strip()
    except Exception:
        pass
    
    try:
        result = subprocess.run(
            ['git', '-C', str(workspace_path), 'status', '--porcelain'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            lines = [l for l in lines if l.strip()]
            if not lines:
                info["status"] = "clean"
            else:
                info["status"] = f"{len(lines)} changed"
    except Exception:
        pass
    
    return info


def find_focus_board(workspace_name: str) -> Optional[Dict[str, Any]]:
    """Look for a focus board matching this workspace."""
    if not os.path.isdir(FOCUS_BOARDS_DIR):
        return None
    
    # Check for board file matching workspace name
    safe_name = safe_id(workspace_name)
    
    for filename in os.listdir(FOCUS_BOARDS_DIR):
        if not filename.endswith('.json'):
            continue
        
        name_part = filename.rsplit('.', 1)[0].lower()
        if safe_name in name_part or workspace_name.lower() in name_part:
            board_path = os.path.join(FOCUS_BOARDS_DIR, filename)
            try:
                with open(board_path, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
    
    # Also check inside workspace for .vera/focus_board.json
    return None


def discover_workspaces() -> List[Dict[str, Any]]:
    """Discover all workspaces from configured root directories."""
    workspaces = []
    seen_paths = set()
    
    for root in WORKSPACE_ROOTS:
        root_path = Path(root)
        if not root_path.exists():
            continue
        
        for item in sorted(root_path.iterdir()):
            if not item.is_dir():
                continue
            if item.name.startswith('.'):
                continue
            
            abs_path = str(item.resolve())
            if abs_path in seen_paths:
                continue
            seen_paths.add(abs_path)
            
            workspaces.append(scan_workspace(item))
    
    # Also check focus boards dir for workspaces referenced there
    if os.path.isdir(FOCUS_BOARDS_DIR):
        for filename in os.listdir(FOCUS_BOARDS_DIR):
            if not filename.endswith('.json'):
                continue
            board_path = os.path.join(FOCUS_BOARDS_DIR, filename)
            try:
                with open(board_path, 'r') as f:
                    board = json.load(f)
                wp = board.get('project_path') or board.get('working_directory')
                if wp and os.path.isdir(wp) and wp not in seen_paths:
                    seen_paths.add(wp)
                    ws = scan_workspace(Path(wp))
                    ws['focus_name'] = board.get('focus') or filename.rsplit('.', 1)[0]
                    ws['has_focus_board'] = True
                    workspaces.append(ws)
            except (json.JSONDecodeError, IOError, KeyError):
                pass
    
    return workspaces


def scan_workspace(path: Path) -> Dict[str, Any]:
    """Scan a single workspace directory for metadata."""
    try:
        stat = path.stat()
        created = datetime.fromtimestamp(stat.st_ctime).isoformat()
        modified = datetime.fromtimestamp(stat.st_mtime).isoformat()
    except OSError:
        created = None
        modified = None
    
    file_count, total_size = get_dir_stats(path)
    git_info = get_git_info(path)
    board = find_focus_board(path.name)
    
    # Determine activity status
    status = "idle"
    if modified:
        try:
            mod_dt = datetime.fromisoformat(modified)
            if datetime.now() - mod_dt < timedelta(hours=1):
                status = "active"
            elif datetime.now() - mod_dt > timedelta(days=30):
                status = "archived"
        except ValueError:
            pass
    
    # Build tags from contents
    tags = []
    if (path / 'requirements.txt').exists() or (path / 'setup.py').exists():
        tags.append('python')
    if (path / 'package.json').exists():
        tags.append('node')
    if (path / 'Cargo.toml').exists():
        tags.append('rust')
    if (path / 'Dockerfile').exists():
        tags.append('docker')
    if (path / '.vera').exists() or board:
        tags.append('vera')
    if git_info['has_git']:
        tags.append('git')
    
    # Check for internal focus board file
    internal_board_path = path / '.vera' / 'focus_board.json'
    has_fb = board is not None or internal_board_path.exists()
    
    return {
        "id": safe_id(path.name),
        "name": path.name,
        "path": str(path.resolve()),
        "status": status,
        "created_at": created,
        "last_modified": modified,
        "file_count": file_count,
        "total_size_bytes": total_size,
        "has_git": git_info['has_git'],
        "has_focus_board": has_fb,
        "focus_name": None,
        "tags": tags,
        # Extras for detail view
        "_git_info": git_info,
        "_board": board,
    }


def build_file_tree(root: Path, max_depth: int = 3, current_depth: int = 0) -> List[Dict]:
    """Build a file tree structure."""
    if current_depth >= max_depth:
        return []
    
    items = []
    try:
        entries = sorted(root.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except (PermissionError, OSError):
        return []
    
    for entry in entries:
        # Skip hidden and junk
        if entry.name.startswith('.') and entry.name not in ('.env', '.gitignore', '.editorconfig'):
            continue
        if entry.name in ('node_modules', '__pycache__', 'venv', '.venv', '.tox'):
            continue
        
        try:
            stat = entry.stat()
        except OSError:
            continue
        
        node = {
            "name": entry.name,
            "path": str(entry.relative_to(root)),
            "type": "dir" if entry.is_dir() else "file",
            "size": stat.st_size if entry.is_file() else 0,
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "extension": entry.suffix.lower() if entry.is_file() else None,
        }
        
        if entry.is_dir():
            node["children"] = build_file_tree(entry, max_depth, current_depth + 1)
        
        items.append(node)
    
    return items


def get_recently_modified_files(root: Path, limit: int = 10) -> List[Dict]:
    """Get the most recently modified files in a workspace."""
    files = []
    
    try:
        for item in root.rglob('*'):
            if not item.is_file():
                continue
            parts = item.relative_to(root).parts
            if any(p.startswith('.') or p in ('node_modules', '__pycache__', 'venv') for p in parts):
                continue
            try:
                stat = item.stat()
                files.append({
                    "name": item.name,
                    "path": str(item.relative_to(root)),
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "extension": item.suffix.lower(),
                })
            except OSError:
                continue
    except (PermissionError, OSError):
        pass
    
    files.sort(key=lambda f: f['modified'], reverse=True)
    return files[:limit]


# ============================================================
# Endpoints
# ============================================================

@router.get("", response_model=List[WorkspaceSummary])
async def list_workspaces(
    status: Optional[str] = Query(None, description="Filter: active|idle|archived"),
    sort_by: str = Query("last_modified", description="Sort: last_modified|name|size"),
    sort_order: str = Query("desc", description="asc|desc"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
):
    """List all discovered workspaces."""
    start = time.time()
    
    try:
        workspaces = discover_workspaces()
        
        # Filter
        if status:
            workspaces = [w for w in workspaces if w['status'] == status]
        if tag:
            workspaces = [w for w in workspaces if tag in w.get('tags', [])]
        
        # Sort
        reverse = sort_order == "desc"
        if sort_by == "name":
            workspaces.sort(key=lambda w: w['name'].lower(), reverse=reverse)
        elif sort_by == "size":
            workspaces.sort(key=lambda w: w['total_size_bytes'], reverse=reverse)
        else:  # last_modified
            workspaces.sort(
                key=lambda w: w.get('last_modified') or '1970-01-01',
                reverse=reverse
            )
        
        logger.info(f"Listed {len(workspaces)} workspaces in {time.time()-start:.3f}s")
        
        return [
            WorkspaceSummary(**{k: v for k, v in w.items() if not k.startswith('_')})
            for w in workspaces
        ]
    
    except Exception as e:
        logger.error(f"Error listing workspaces: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/summary", response_model=WorkspaceStats)
async def get_workspace_stats():
    """Aggregate stats across all workspaces."""
    try:
        workspaces = discover_workspaces()
        
        total_files = sum(w['file_count'] for w in workspaces)
        total_size = sum(w['total_size_bytes'] for w in workspaces)
        
        return WorkspaceStats(
            total_workspaces=len(workspaces),
            active_workspaces=sum(1 for w in workspaces if w['status'] == 'active'),
            total_files=total_files,
            total_size_bytes=total_size,
            total_size_human=human_size(total_size),
            workspaces_with_git=sum(1 for w in workspaces if w['has_git']),
            workspaces_with_focus=sum(1 for w in workspaces if w['has_focus_board']),
        )
    except Exception as e:
        logger.error(f"Error getting workspace stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{workspace_id}", response_model=WorkspaceDetail)
async def get_workspace_detail(workspace_id: str):
    """Get detailed information about a workspace."""
    try:
        workspaces = discover_workspaces()
        ws = next((w for w in workspaces if w['id'] == workspace_id), None)
        
        if not ws:
            raise HTTPException(status_code=404, detail="Workspace not found")
        
        ws_path = Path(ws['path'])
        git_info = ws.get('_git_info', {})
        
        # Load focus board
        focus_board = ws.get('_board')
        if not focus_board:
            internal = ws_path / '.vera' / 'focus_board.json'
            if internal.exists():
                try:
                    with open(internal, 'r') as f:
                        focus_board = json.load(f)
                except (json.JSONDecodeError, IOError):
                    pass
        
        recent_files = get_recently_modified_files(ws_path, limit=15)
        
        return WorkspaceDetail(
            id=ws['id'],
            name=ws['name'],
            path=ws['path'],
            status=ws['status'],
            created_at=ws.get('created_at'),
            last_modified=ws.get('last_modified'),
            file_count=ws['file_count'],
            total_size_bytes=ws['total_size_bytes'],
            has_git=git_info.get('has_git', False),
            git_branch=git_info.get('branch'),
            git_status=git_info.get('status'),
            has_focus_board=focus_board is not None,
            focus_board=focus_board,
            recent_files=recent_files,
            tags=ws.get('tags', []),
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting workspace detail: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{workspace_id}/tree")
async def get_workspace_tree(
    workspace_id: str,
    depth: int = Query(3, ge=1, le=6),
):
    """Get file tree for a workspace."""
    try:
        workspaces = discover_workspaces()
        ws = next((w for w in workspaces if w['id'] == workspace_id), None)
        
        if not ws:
            raise HTTPException(status_code=404, detail="Workspace not found")
        
        tree = build_file_tree(Path(ws['path']), max_depth=depth)
        return {"workspace_id": workspace_id, "tree": tree}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error building file tree: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{workspace_id}/file")
async def read_workspace_file(
    workspace_id: str,
    path: str = Query(..., description="Relative path within workspace"),
):
    """Read a file from a workspace (text files only, size-limited)."""
    try:
        workspaces = discover_workspaces()
        ws = next((w for w in workspaces if w['id'] == workspace_id), None)
        
        if not ws:
            raise HTTPException(status_code=404, detail="Workspace not found")
        
        ws_root = Path(ws['path'])
        file_path = (ws_root / path).resolve()
        
        # Security: ensure file is within workspace
        try:
            file_path.relative_to(ws_root.resolve())
        except ValueError:
            raise HTTPException(status_code=403, detail="Path escapes workspace boundary")
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        if not file_path.is_file():
            raise HTTPException(status_code=400, detail="Path is not a file")
        
        stat = file_path.stat()
        ext = file_path.suffix.lower()
        
        result = FileContent(
            path=path,
            name=file_path.name,
            size=stat.st_size,
            extension=ext,
        )
        
        if ext not in TEXT_EXTENSIONS:
            result.binary = True
            result.mime_hint = "application/octet-stream"
            return result
        
        if stat.st_size > MAX_FILE_READ_SIZE:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                result.content = f.read(MAX_FILE_READ_SIZE)
            result.truncated = True
        else:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                result.content = f.read()
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reading file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{workspace_id}/board")
async def get_workspace_board(workspace_id: str):
    """Get the focus board state for a workspace."""
    try:
        workspaces = discover_workspaces()
        ws = next((w for w in workspaces if w['id'] == workspace_id), None)
        
        if not ws:
            raise HTTPException(status_code=404, detail="Workspace not found")
        
        board = ws.get('_board')
        if not board:
            ws_path = Path(ws['path'])
            internal = ws_path / '.vera' / 'focus_board.json'
            if internal.exists():
                with open(internal, 'r') as f:
                    board = json.load(f)
        
        if not board:
            return {"workspace_id": workspace_id, "board": None, "message": "No focus board found"}
        
        return {"workspace_id": workspace_id, "board": board}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting board: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=WorkspaceSummary)
async def create_workspace(request: CreateWorkspaceRequest):
    """Create a new workspace directory."""
    try:
        # Use first writable root
        root = Path(WORKSPACE_ROOTS[0])
        root.mkdir(parents=True, exist_ok=True)
        
        ws_name = re.sub(r'[^\w\-\.]', '_', request.name)
        ws_path = root / ws_name
        
        if ws_path.exists():
            raise HTTPException(status_code=409, detail="Workspace already exists")
        
        ws_path.mkdir(parents=True)
        
        # Create .vera metadata dir
        vera_dir = ws_path / '.vera'
        vera_dir.mkdir()
        
        meta = {
            "name": request.name,
            "description": request.description,
            "created_at": datetime.utcnow().isoformat(),
            "template": request.template,
        }
        with open(vera_dir / 'workspace.json', 'w') as f:
            json.dump(meta, f, indent=2)
        
        # Apply template
        if request.template == 'python':
            (ws_path / 'src').mkdir()
            (ws_path / 'tests').mkdir()
            (ws_path / 'requirements.txt').touch()
            (ws_path / 'README.md').write_text(f"# {request.name}\n\n{request.description or ''}\n")
        elif request.template == 'node':
            pkg = {"name": ws_name, "version": "0.1.0", "private": True}
            (ws_path / 'package.json').write_text(json.dumps(pkg, indent=2))
            (ws_path / 'src').mkdir()
            (ws_path / 'README.md').write_text(f"# {request.name}\n\n{request.description or ''}\n")
        else:
            (ws_path / 'README.md').write_text(f"# {request.name}\n\n{request.description or ''}\n")
        
        ws = scan_workspace(ws_path)
        return WorkspaceSummary(**{k: v for k, v in ws.items() if not k.startswith('_')})
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating workspace: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{workspace_id}")
async def archive_workspace(workspace_id: str):
    """Mark a workspace as archived (does NOT delete files)."""
    try:
        workspaces = discover_workspaces()
        ws = next((w for w in workspaces if w['id'] == workspace_id), None)
        
        if not ws:
            raise HTTPException(status_code=404, detail="Workspace not found")
        
        ws_path = Path(ws['path'])
        vera_dir = ws_path / '.vera'
        vera_dir.mkdir(exist_ok=True)
        
        archive_meta = {
            "archived": True,
            "archived_at": datetime.utcnow().isoformat(),
        }
        
        meta_path = vera_dir / 'workspace.json'
        if meta_path.exists():
            with open(meta_path, 'r') as f:
                existing = json.load(f)
            existing.update(archive_meta)
        else:
            existing = archive_meta
        
        with open(meta_path, 'w') as f:
            json.dump(existing, f, indent=2)
        
        return {
            "status": "archived",
            "workspace_id": workspace_id,
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error archiving workspace: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))