# session_api.py - Enhanced version
import asyncio
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List, Optional
from collections import defaultdict
import uuid

from Vera.vera import Vera
from Vera.ChatUI.api.schemas import SessionStartResponse 

# ============================================================
# Global storage with locks
# ============================================================
vera_instances: Dict[str, Vera] = {}
sessions: Dict[str, Dict[str, Any]] = {}
session_locks: Dict[str, asyncio.Lock] = {}
_global_lock = asyncio.Lock()

# Toolchain monitoring
toolchain_executions: Dict[str, Dict[str, Any]] = defaultdict(dict)
active_toolchains: Dict[str, str] = {}
websocket_connections: Dict[str, List[WebSocket]] = defaultdict(list)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/session", tags=["session"])

# ============================================================
# Session Management with Deduplication
# ============================================================

async def get_session_lock(session_id: str) -> asyncio.Lock:
    """Get or create a lock for a specific session."""
    async with _global_lock:
        if session_id not in session_locks:
            session_locks[session_id] = asyncio.Lock()
        return session_locks[session_id]

def get_or_create_vera(session_id: str) -> Vera:
    """Get existing Vera instance or raise error."""
    if session_id not in vera_instances:
        logger.error(f"Vera instance not found for session {session_id}")
        raise HTTPException(
            status_code=404, 
            detail="Session not found or expired. Please start a new session."
        )
    else:
        print(f"SessionID found: {session_id}")
    return vera_instances[session_id]

@router.post("/start", response_model=SessionStartResponse)
async def start_session(resume_session_id: Optional[str] = None):
    """
    Start a new chat session or resume an existing one.
    
    Args:
        resume_session_id: Optional session ID to resume instead of creating new
    """
    try:
        # Check if we should resume an existing session
        if resume_session_id and resume_session_id in vera_instances:
            logger.info(f"Resuming existing session: {resume_session_id}")
            return SessionStartResponse(
                session_id=resume_session_id,
                status="resumed",
                timestamp=datetime.utcnow().isoformat()
            )
        
        # while True:
        #     session_id = str(uuid.uuid4())
        #     if session_id not in sessions:
        #         break
        # lock = await get_session_lock(session_id)

        # async with lock:
        #     # Double-check session doesn't exist
        #     if session_id in vera_instances:
        #         logger.warning(f"Session {session_id} already exists, returning existing")
        #         return SessionStartResponse(
        #             session_id=session_id,
        #             status="existing",
        #             timestamp=datetime.utcnow().isoformat()
        #         )
        
        # Create Vera instance in thread pool
        def create_vera():
            return Vera()
        
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            vera = await loop.run_in_executor(executor, create_vera)

        session_id = vera.sess.id
        vera_instances[session_id] = vera
        
        # vera.sess.id = session_id
        # vera_instances[session_id] = vera
            
        sessions[session_id] = {
            "created_at": datetime.utcnow().isoformat(),
            "last_activity": datetime.utcnow().isoformat(),
            "messages": [],
            "files": {},
            "vera": vera
        }
        
        # Initialize toolchain storage
        toolchain_executions[session_id] = {}
        
        # Wrap toolchain with monitoring
        if hasattr(vera, 'toolchain'):
            from Vera.ChatUI.api.Toolchain.toolchain_api import MonitoredToolChainPlanner
            # from Vera.ChatUI.api.Toolchain.toolchain_monitor_wrapper import EnhancedMonitoredToolChainPlanner
            original_toolchain = vera.toolchain
            vera.toolchain = MonitoredToolChainPlanner(original_toolchain, session_id)
            # vera.toolchain = EnhancedMonitoredToolChainPlanner(vera.toolchain, session_id)
            print(f"[Monitoring] Wrapped toolchain for {session_id}")
            logger.info(f"Wrapped toolchain with monitoring for session {session_id}")
        
        logger.info(f"Created new session: {session_id}")
        
        return SessionStartResponse(
            session_id=session_id,
            status="started",
            timestamp=datetime.utcnow().isoformat()
        )
            
    except Exception as e:
        logger.error(f"Session start error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to start session: {str(e)}")

@router.get("/{session_id}/status")
async def get_session_status(session_id: str):
    """Check if a session exists and is valid."""
    if session_id not in sessions:
        return {"exists": False, "session_id": session_id}
    
    session = sessions[session_id]
    # Update last activity
    session["last_activity"] = datetime.utcnow().isoformat()
    
    return {
        "exists": True,
        "session_id": session_id,
        "created_at": session["created_at"],
        "last_activity": session["last_activity"],
        "message_count": len(session["messages"])
    }

@router.post("/{session_id}/end")
async def end_session(session_id: str):
    """End a chat session and cleanup resources."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    lock = await get_session_lock(session_id)
    async with lock:
        # Close all websockets for this session
        if session_id in websocket_connections:
            for ws in websocket_connections[session_id]:
                try:
                    await ws.close()
                except:
                    pass
        
        # Cleanup all resources
        vera_instances.pop(session_id, None)
        sessions.pop(session_id, None)
        toolchain_executions.pop(session_id, None)
        active_toolchains.pop(session_id, None)
        websocket_connections.pop(session_id, None)
        session_locks.pop(session_id, None)
    
    logger.info(f"Ended session: {session_id}")
    return {"status": "ended", "session_id": session_id}

# ============================================================
# WebSocket Handler (CRITICAL - This was missing!)
# ============================================================

@router.websocket("/{session_id}/ws")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time communication."""
    await websocket.accept()
    
    # Validate session exists
    if session_id not in sessions:
        await websocket.send_json({
            "type": "error",
            "message": "Session not found or expired"
        })
        await websocket.close()
        return
    
    # Register this websocket
    websocket_connections[session_id].append(websocket)
    logger.info(f"WebSocket connected for session {session_id}")
    
    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Keep connection alive and handle messages
        while True:
            data = await websocket.receive_json()
            
            # Handle different message types
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            elif data.get("type") == "status":
                # Send session status
                await websocket.send_json({
                    "type": "status",
                    "session_id": session_id,
                    "active": True
                })
            
            # Update last activity
            if session_id in sessions:
                sessions[session_id]["last_activity"] = datetime.utcnow().isoformat()
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")
    finally:
        # Cleanup on disconnect
        if websocket in websocket_connections[session_id]:
            websocket_connections[session_id].remove(websocket)

# ============================================================
# Session Cleanup Task
# ============================================================

async def cleanup_expired_sessions():
    """Periodically cleanup expired sessions."""
    while True:
        try:
            await asyncio.sleep(300)  # Check every 5 minutes
            
            now = datetime.utcnow()
            expired = []
            
            for session_id, session_data in sessions.items():
                last_activity = datetime.fromisoformat(session_data["last_activity"])
                if now - last_activity > timedelta(hours=2):  # 2 hour timeout
                    expired.append(session_id)
            
            for session_id in expired:
                logger.info(f"Cleaning up expired session: {session_id}")
                try:
                    await end_session(session_id)
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"Error in cleanup task: {e}")

# Start cleanup task when app starts
@router.on_event("startup")
async def startup_event():
    asyncio.create_task(cleanup_expired_sessions())

