"""
ide_router.py — FastAPI router for Vera IDE
────────────────────────────────────────────
Endpoints:
  GET  /ide-api/models                  probe Ollama instances, return model lists
  GET  /ide-api/ollama/{key}/tags       model list proxy  (no CORS)
  POST /ide-api/ollama/{key}/chat       streaming/blocking chat proxy (no CORS)

  GET  /ide-api/fs/roots                allowed root dirs + workspaces
  GET  /ide-api/fs/browse?path=         single-level dir listing for folder picker
  GET  /ide-api/fs/list?path=           flat listing for editor file tree
  GET  /ide-api/fs/read?path=           read file content
  POST /ide-api/fs/write                write file
  POST /ide-api/fs/delete               delete file or dir
  POST /ide-api/fs/move                 rename/move
  POST /ide-api/fs/mkdir                create directory

  POST /ide-api/workspace/create        create blank workspace + optional template
  GET  /ide-api/workspace/list          list workspaces

Mount in your FastAPI app:
    from Vera.ChatUI.ide_router import router as ide_router
    app.include_router(ide_router)
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import time
from pathlib import Path
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

router = APIRouter(prefix="/ide-api")

# ══════════════════════════════════════════════════════════════════
#  Ollama instance config
# ══════════════════════════════════════════════════════════════════

_DEFAULT_INSTANCES = [
    {"name": "Thinker", "host": "192.168.0.247", "port": 11435, "tier": "thinker"},
    {"name": "Writer",  "host": "192.168.0.250", "port": 11435, "tier": "writer"},
    {"name": "Analyst", "host": "192.168.0.246", "port": 11436, "tier": "analyst"},
]

_INSTANCE_MAP: dict[str, str] = {}   # name.lower() → base_url


def _load_instances() -> list[dict]:
    global _INSTANCE_MAP
    raw = os.environ.get("IDE_OLLAMA_INSTANCES", "")
    if raw:
        try:
            insts = json.loads(raw)
            _INSTANCE_MAP = {i["name"].lower(): f"http://{i['host']}:{i['port']}" for i in insts}
            return insts
        except Exception:
            pass
    try:
        from Vera.ChatUI.researcher_api import instances as _ri  # type: ignore
        insts = [{"name": i.name, "host": i.host, "port": i.port,
                  "tier": i.tier.value, "model": i.model, "enabled": i.enabled}
                 for i in _ri]
        _INSTANCE_MAP = {i["name"].lower(): f"http://{i['host']}:{i['port']}" for i in insts}
        return insts
    except Exception:
        pass
    insts = list(_DEFAULT_INSTANCES)
    _INSTANCE_MAP = {i["name"].lower(): f"http://{i['host']}:{i['port']}" for i in insts}
    return insts


def _resolve_endpoint(key: str) -> str:
    """Resolve a key (name, tier, or full URL) to a base URL."""
    if key.startswith("http"):
        return key.rstrip("/")
    _load_instances()
    lower = key.lower()
    if lower in _INSTANCE_MAP:
        return _INSTANCE_MAP[lower]
    for inst in _DEFAULT_INSTANCES:
        if inst.get("tier", "").lower() == lower:
            return f"http://{inst['host']}:{inst['port']}"
    raise HTTPException(404, f"Unknown instance/tier: {key!r}")


# ══════════════════════════════════════════════════════════════════
#  Ollama proxy  (all browser→Ollama calls route through here)
# ══════════════════════════════════════════════════════════════════

@router.get("/ollama/{key}/tags")
async def ollama_tags(key: str):
    base = _resolve_endpoint(key)
    async with httpx.AsyncClient(timeout=8.0) as c:
        try:
            r = await c.get(f"{base}/api/tags")
            return JSONResponse(content=r.json(), status_code=r.status_code)
        except httpx.ConnectError:
            raise HTTPException(503, f"Cannot reach {base}")
        except Exception as e:
            raise HTTPException(502, str(e))


@router.post("/ollama/{key}/chat")
async def ollama_chat(key: str, request: Request):
    """
    Forward chat requests to Ollama server-side.
    Handles both stream:true (NDJSON) and stream:false (JSON).
    Because this runs on the server, the browser never makes a
    cross-origin request to Ollama — CORS is irrelevant.
    """
    base = _resolve_endpoint(key)
    body = await request.body()
    try:
        streaming = json.loads(body).get("stream", True)
    except Exception:
        streaming = True

    if streaming:
        async def _stream():
            async with httpx.AsyncClient(timeout=None) as c:
                try:
                    async with c.stream("POST", f"{base}/api/chat",
                                        content=body,
                                        headers={"Content-Type": "application/json"}) as resp:
                        async for chunk in resp.aiter_bytes():
                            yield chunk
                except httpx.ConnectError as e:
                    yield json.dumps({"error": f"Cannot reach {base}: {e}"}).encode()
                except Exception as e:
                    yield json.dumps({"error": str(e)}).encode()

        return StreamingResponse(_stream(), media_type="application/x-ndjson")

    async with httpx.AsyncClient(timeout=300.0) as c:
        try:
            r = await c.post(f"{base}/api/chat", content=body,
                             headers={"Content-Type": "application/json"})
            return JSONResponse(content=r.json(), status_code=r.status_code)
        except httpx.ConnectError:
            raise HTTPException(503, f"Cannot reach {base}")
        except Exception as e:
            raise HTTPException(502, str(e))


# ══════════════════════════════════════════════════════════════════
#  /models  — probe all instances
# ══════════════════════════════════════════════════════════════════

@router.get("/models")
async def ide_models():
    instances = _load_instances()

    async def probe(inst: dict) -> dict:
        base = f"http://{inst['host']}:{inst['port']}"
        result = {"instance": inst["name"], "tier": inst["tier"], "host": base,
                  "current_model": inst.get("model", ""), "available": [],
                  "enabled": inst.get("enabled", True), "reachable": False}
        if not result["enabled"]:
            return result
        try:
            async with httpx.AsyncClient(timeout=5.0) as c:
                r = await c.get(f"{base}/api/tags")
                if r.status_code == 200:
                    models = [m["name"] for m in r.json().get("models", [])]
                    result.update(available=models, reachable=True)
                    if not result["current_model"] and models:
                        result["current_model"] = models[0]
        except Exception:
            pass
        return result

    return list(await asyncio.gather(*[probe(i) for i in instances]))


# ══════════════════════════════════════════════════════════════════
#  File system config + helpers
# ══════════════════════════════════════════════════════════════════

_env_roots = os.environ.get("IDE_ROOTS", "")
ALLOWED_ROOTS: list[Path] = (
    [Path(p).resolve() for p in _env_roots.split(":") if p]
    if _env_roots
    else [Path.home(), Path("/projects"), Path("/opt"), Path.cwd()]
)

WORKSPACES_DIR = Path(os.environ.get("IDE_WORKSPACES",
                                      str(Path.home() / "ide-workspaces")))

IGNORED = {
    ".git", "node_modules", "__pycache__", ".DS_Store", "dist", "build",
    ".next", ".venv", "venv", ".cache", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", ".eggs",
}

TEXT_EXTS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".htm", ".css",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env",
    ".md", ".txt", ".rst", ".sh", ".bash", ".zsh", ".fish",
    ".rs", ".go", ".java", ".c", ".cpp", ".h", ".hpp", ".cs",
    ".rb", ".php", ".swift", ".kt", ".scala", ".r", ".sql",
    ".vue", ".svelte", ".graphql", ".proto", ".tf", ".hcl",
    ".xml", ".svg", ".csv", ".tsv", ".log", ".lock",
    ".gitignore", ".gitattributes", ".editorconfig",
}


def resolve_safe(path_str: str) -> Path:
    p = Path(path_str).resolve()
    try:
        p.relative_to(WORKSPACES_DIR.resolve())
        return p
    except ValueError:
        pass
    for root in ALLOWED_ROOTS:
        try:
            p.relative_to(root.resolve())
            return p
        except ValueError:
            continue
    raise HTTPException(403, f"Path not within allowed roots: {path_str}")


def _is_ignored(name: str) -> bool:
    return name.startswith(".") or name in IGNORED


def _is_text(path: Path) -> bool:
    return path.suffix.lower() in TEXT_EXTS or path.suffix == ""


# ══════════════════════════════════════════════════════════════════
#  Folder picker browser  (single-level, drives the picker modal)
# ══════════════════════════════════════════════════════════════════

@router.get("/fs/roots")
def fs_roots():
    roots = []
    for r in ALLOWED_ROOTS:
        if r.exists():
            roots.append({"path": str(r), "name": r.name or str(r), "kind": "root"})
    # Workspaces appear as a separate group
    ws_root = WORKSPACES_DIR
    if ws_root.exists():
        for ws in sorted(ws_root.iterdir()):
            if ws.is_dir() and not _is_ignored(ws.name):
                roots.append({"path": str(ws), "name": ws.name,
                               "kind": "workspace", "workspace": True})
    return {"roots": roots, "workspaces_dir": str(ws_root)}


@router.get("/fs/browse")
def fs_browse(path: str):
    """
    Single-level listing for the folder picker UI.
    Returns dirs + files with metadata; also returns parent path and breadcrumbs.
    """
    p = resolve_safe(path)
    if not p.exists():
        raise HTTPException(404, "Path not found")
    if not p.is_dir():
        raise HTTPException(400, "Not a directory")

    entries = []
    try:
        for item in sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
            if _is_ignored(item.name):
                continue
            if item.is_dir():
                try:
                    child_count = sum(1 for c in item.iterdir() if not _is_ignored(c.name))
                except PermissionError:
                    child_count = 0
                entries.append({"name": item.name, "path": str(item),
                                 "kind": "directory", "child_count": child_count})
            else:
                entries.append({"name": item.name, "path": str(item), "kind": "file",
                                 "size": item.stat().st_size, "readable": _is_text(item)})
    except PermissionError:
        raise HTTPException(403, "Permission denied")

    # Build breadcrumb trail
    crumbs: list[dict] = []
    for root in ALLOWED_ROOTS + [WORKSPACES_DIR]:
        try:
            rel = p.relative_to(root.resolve())
            crumbs = [{"name": root.name or str(root), "path": str(root)}]
            acc = root.resolve()
            for part in rel.parts:
                acc = acc / part
                crumbs.append({"name": part, "path": str(acc)})
            break
        except ValueError:
            continue
    if not crumbs:
        crumbs = [{"name": p.name, "path": str(p)}]

    return {
        "path":    str(p),
        "parent":  str(p.parent) if str(p.parent) != str(p) else None,
        "crumbs":  crumbs,
        "entries": entries,
    }


# ══════════════════════════════════════════════════════════════════
#  File tree listing  (for editor sidebar, flat recursive)
# ══════════════════════════════════════════════════════════════════

@router.get("/fs/list")
def fs_list(path: str):
    p = resolve_safe(path)
    if not p.exists():
        raise HTTPException(404, "Path not found")
    if not p.is_dir():
        raise HTTPException(400, "Not a directory")

    entries = []
    try:
        for item in sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
            if _is_ignored(item.name):
                continue
            entries.append({
                "name":     item.name,
                "path":     str(item),
                "kind":     "directory" if item.is_dir() else "file",
                "size":     item.stat().st_size if item.is_file() else 0,
                "readable": _is_text(item) if item.is_file() else True,
            })
    except PermissionError:
        raise HTTPException(403, "Permission denied")

    return {"path": str(p), "entries": entries}


# ══════════════════════════════════════════════════════════════════
#  Read / write / delete / move / mkdir
# ══════════════════════════════════════════════════════════════════

@router.get("/fs/read")
def fs_read(path: str):
    p = resolve_safe(path)
    if not p.exists():
        raise HTTPException(404, "File not found")
    if not p.is_file():
        raise HTTPException(400, "Not a file")
    if not _is_text(p):
        raise HTTPException(415, "Binary file — not readable as text")
    try:
        return {"path": str(p), "content": p.read_text(encoding="utf-8", errors="replace"),
                "size": p.stat().st_size}
    except PermissionError:
        raise HTTPException(403, "Permission denied")


class WriteBody(BaseModel):
    path: str
    content: str

@router.post("/fs/write")
def fs_write(body: WriteBody):
    p = resolve_safe(body.path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body.content, encoding="utf-8")
        return {"ok": True, "path": str(p), "size": p.stat().st_size}
    except PermissionError:
        raise HTTPException(403, "Permission denied")
    except Exception as e:
        raise HTTPException(500, str(e))


class DeleteBody(BaseModel):
    path: str

@router.post("/fs/delete")
def fs_delete(body: DeleteBody):
    p = resolve_safe(body.path)
    if not p.exists():
        raise HTTPException(404, "Not found")
    try:
        shutil.rmtree(p) if p.is_dir() else p.unlink()
        return {"ok": True}
    except PermissionError:
        raise HTTPException(403, "Permission denied")


class MoveBody(BaseModel):
    src: str
    dst: str

@router.post("/fs/move")
def fs_move(body: MoveBody):
    src = resolve_safe(body.src)
    dst = resolve_safe(body.dst)
    if not src.exists():
        raise HTTPException(404, "Source not found")
    src.rename(dst)
    return {"ok": True, "path": str(dst)}


class MkdirBody(BaseModel):
    path: str

@router.post("/fs/mkdir")
def fs_mkdir(body: MkdirBody):
    p = resolve_safe(body.path)
    p.mkdir(parents=True, exist_ok=True)
    return {"ok": True, "path": str(p)}


# ══════════════════════════════════════════════════════════════════
#  Workspace creation
# ══════════════════════════════════════════════════════════════════

WORKSPACE_TEMPLATES: dict[str, dict[str, str]] = {
    "blank": {},
    "python": {
        "main.py":          "#!/usr/bin/env python3\n\n\ndef main():\n    pass\n\n\nif __name__ == \"__main__\":\n    main()\n",
        "requirements.txt": "# dependencies\n",
        "README.md":        "# Project\n\n```bash\npip install -r requirements.txt\npython main.py\n```\n",
        ".gitignore":       "__pycache__/\n*.py[cod]\n.venv/\nvenv/\n.env\n",
    },
    "node": {
        "index.js":     '"use strict";\n\nconsole.log("hello");\n',
        "package.json": '{\n  "name": "project",\n  "version": "1.0.0",\n  "scripts": { "start": "node index.js" }\n}\n',
        "README.md":    "# Project\n\n```bash\nnpm install\nnpm start\n```\n",
        ".gitignore":   "node_modules/\ndist/\n.env\n",
    },
    "web": {
        "index.html": '<!DOCTYPE html>\n<html lang="en">\n<head>\n  <meta charset="UTF-8">\n  <title>Project</title>\n  <link rel="stylesheet" href="style.css">\n</head>\n<body>\n  <h1>Hello</h1>\n  <script src="main.js"></script>\n</body>\n</html>\n',
        "style.css":  "*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }\nbody { font-family: system-ui, sans-serif; padding: 2rem; }\n",
        "main.js":    '"use strict";\n\nconsole.log("ready");\n',
        "README.md":  "# Web Project\n\nOpen `index.html` in a browser.\n",
    },
    "fastapi": {
        "main.py":          'from fastapi import FastAPI\nfrom fastapi.middleware.cors import CORSMiddleware\n\napp = FastAPI()\napp.add_middleware(CORSMiddleware, allow_origins=["*"],\n                   allow_methods=["*"], allow_headers=["*"])\n\n\n@app.get("/")\ndef root():\n    return {"status": "ok"}\n',
        "requirements.txt": "fastapi\nuvicorn[standard]\nhttpx\n",
        "README.md":        "# FastAPI Project\n\n```bash\npip install -r requirements.txt\nuvicorn main:app --reload\n```\n",
        ".gitignore":       "__pycache__/\n.venv/\nvenv/\n.env\n",
    },
}


class WorkspaceCreateBody(BaseModel):
    name: str
    template: str = "blank"
    base_path: Optional[str] = None   # None → use WORKSPACES_DIR


@router.post("/workspace/create")
def workspace_create(body: WorkspaceCreateBody):
    safe_name = "".join(c if c.isalnum() or c in "-_. " else "_"
                        for c in body.name).strip()
    if not safe_name:
        raise HTTPException(400, "Invalid workspace name")

    base = resolve_safe(body.base_path) if body.base_path else WORKSPACES_DIR
    base.mkdir(parents=True, exist_ok=True)

    ws_path = base / safe_name
    if ws_path.exists():
        ws_path = base / f"{safe_name}-{int(time.time())}"
    ws_path.mkdir(parents=True)

    template = WORKSPACE_TEMPLATES.get(body.template, {})
    for rel, content in template.items():
        target = ws_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    return {"ok": True, "path": str(ws_path), "name": ws_path.name,
            "template": body.template, "files": list(template.keys())}


@router.get("/workspace/list")
def workspace_list():
    WORKSPACES_DIR.mkdir(parents=True, exist_ok=True)
    workspaces = []
    for item in sorted(WORKSPACES_DIR.iterdir(), key=lambda x: -x.stat().st_mtime):
        if item.is_dir() and not _is_ignored(item.name):
            files = [f.name for f in sorted(item.iterdir()) if f.is_file()][:6]
            workspaces.append({"name": item.name, "path": str(item),
                                "files": files, "mtime": item.stat().st_mtime})
    return {"workspaces": workspaces, "base": str(WORKSPACES_DIR)}