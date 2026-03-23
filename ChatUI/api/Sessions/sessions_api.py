"""
vera_session_list_endpoint.py
─────────────────────────────────────────────────────────────
Drop-in FastAPI endpoints to expose active Vera sessions.

Add to your Vera FastAPI app:

    from vera_session_list_endpoint import router
    app.include_router(router)

Or paste the route functions directly into your existing router.

These endpoints let the Graph Galaxy viewer auto-detect the
active session ID without requiring manual copy-paste.
"""

from fastapi import APIRouter
from typing import Any, Dict, List
from datetime import datetime

# Import your existing session store
# Adjust import path to match your project structure
try:
    from Vera.ChatUI.api.session import sessions, get_or_create_vera
except ImportError:
    # Fallback: try common alternative paths
    try:
        from api.session import sessions, get_or_create_vera
    except ImportError:
        sessions = {}
        get_or_create_vera = None

router = APIRouter(tags=["sessions"])


@router.get("/api/sessions")
@router.get("/api/session/list")
@router.get("/api/sessions/list")
async def list_sessions() -> Dict[str, Any]:
    """
    List all active Vera sessions.
    
    Graph Galaxy calls this on connect to auto-detect the session ID.
    Returns sessions sorted newest-first.
    
    Response shape:
        {
            "sessions": [
                {"id": "sess_...", "created_at": "...", "active": true},
                ...
            ],
            "total": 1
        }
    """
    session_list = []
    
    for sid, session_data in sessions.items():
        entry: Dict[str, Any] = {"id": sid, "active": True}
        
        # Extract metadata if available (depends on your session structure)
        if isinstance(session_data, dict):
            entry["created_at"] = session_data.get("created_at", "")
            entry["model"]      = session_data.get("model", "")
        elif hasattr(session_data, "created_at"):
            entry["created_at"] = str(session_data.created_at)
        elif hasattr(session_data, "sess") and hasattr(session_data.sess, "id"):
            entry["id"] = session_data.sess.id
        
        session_list.append(entry)
    
    # Sort by created_at descending if available, else by ID descending
    session_list.sort(
        key=lambda s: s.get("created_at") or s["id"],
        reverse=True
    )
    
    return {
        "sessions": session_list,
        "total": len(session_list),
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/api/sessions/active")
@router.get("/api/session/active")
async def get_active_session() -> Dict[str, Any]:
    """
    Return the most recently created session.
    Convenience endpoint — returns just the first session ID.
    """
    if not sessions:
        return {"session_id": None, "sessions": []}
    
    # Get most recent
    all_ids = sorted(sessions.keys(), reverse=True)
    latest = all_ids[0]
    
    return {
        "session_id": latest,
        "sessions": [{"id": sid} for sid in all_ids[:5]]
    }