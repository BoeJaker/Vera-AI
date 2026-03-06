#!/usr/bin/env python3
"""
ProjectAssistant API
====================
FastAPI router that exposes the ProjectAssistant over HTTP/SSE.
Mount into the existing Vera FastAPI app:

    from Vera.ProjectAssistant.api import build_router
    app.include_router(build_router(vera_instance, project_root="/path/to/project"))

Endpoints
---------
POST /assistant/chat          – streaming SSE conversation
GET  /assistant/board         – current board snapshot (JSON)
GET  /assistant/tree          – project directory tree (text)
GET  /assistant/stats         – file index stats (JSON)
POST /assistant/stage/{name}  – trigger a ProactiveFocus stage
POST /assistant/board/add     – add an item to the board
POST /assistant/rescan        – re-index the project files
GET  /assistant/search        – search codebase (query param: q)
"""

import json
import asyncio
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from Vera.ProactiveFocus.assistant import ProjectAssistant


# ── Request / response models ─────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class BoardAddRequest(BaseModel):
    category: str
    text: str
    metadata: Optional[Dict[str, Any]] = None


class StageRequest(BaseModel):
    context: Optional[str] = ""


# ── Router factory ────────────────────────────────────────────────────────────

def build_router(
    vera_instance,
    project_root: str,
    max_file_size_kb: int = 128,
    prefix: str = "/assistant",
) -> APIRouter:
    """
    Build and return the FastAPI router.
    Call once at startup and include into the main app.
    """
    assistant = ProjectAssistant(
        vera_instance=vera_instance,
        project_root=project_root,
        max_file_size_kb=max_file_size_kb,
    )

    router = APIRouter(prefix=prefix, tags=["project-assistant"])

    # ── /chat ─────────────────────────────────────────────────────────────────

    @router.post("/chat")
    async def chat(req: ChatRequest):
        """
        Server-Sent Events stream.
        Each event is a JSON object: {"chunk": "..."} or {"done": true}.
        """
        def generate():
            try:
                for chunk in assistant.chat(req.message):
                    payload = json.dumps({"chunk": chunk})
                    yield f"data: {payload}\n\n"
            except Exception as exc:
                payload = json.dumps({"error": str(exc)})
                yield f"data: {payload}\n\n"
            yield "data: " + json.dumps({"done": True}) + "\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    # ── /board ────────────────────────────────────────────────────────────────

    @router.get("/board")
    async def get_board():
        snapshot = assistant.get_board_snapshot()
        focus = assistant.board.focus if assistant.board else None
        return JSONResponse({"focus": focus, "board": snapshot})

    @router.post("/board/add")
    async def board_add(req: BoardAddRequest):
        ok = assistant.add_to_board(req.category, req.text, req.metadata)
        return JSONResponse({"ok": ok})

    # ── /tree ─────────────────────────────────────────────────────────────────

    @router.get("/tree")
    async def get_tree():
        return JSONResponse({"tree": assistant.scanner.tree(max_depth=6)})

    # ── /stats ────────────────────────────────────────────────────────────────

    @router.get("/stats")
    async def get_stats():
        return JSONResponse(assistant.scanner.summary_stats())

    # ── /search ───────────────────────────────────────────────────────────────

    @router.get("/search")
    async def search(q: str = Query(..., description="Search keyword")):
        hits = assistant.scanner.search(q, max_results=30)
        return JSONResponse({
            "query": q,
            "results": [
                {"file": h[0], "line": h[1], "text": h[2]}
                for h in hits
            ],
        })

    # ── /stage/{name} ────────────────────────────────────────────────────────

    @router.post("/stage/{stage_name}")
    async def trigger_stage(stage_name: str, req: StageRequest = StageRequest()):
        result = assistant.trigger_stage(stage_name, context=req.context or "")
        return JSONResponse({"stage": stage_name, "result": result})

    # ── /rescan ───────────────────────────────────────────────────────────────

    @router.post("/rescan")
    async def rescan():
        assistant.rescan()
        return JSONResponse({"ok": True, "files": assistant.scanner.summary_stats()["total_files"]})

    return router