# session_api.py - Improved version
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

from Vera.ChatUI.api.Orchestrator import orchestrator_api
import threading

# Orchestrator initialization tracking
_orchestrator_connected = False
_orchestrator_connect_lock = threading.Lock()
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
# Session Management with Improved Resilience
# ============================================================

async def get_session_lock(session_id: str) -> asyncio.Lock:
    """Get or create a lock for a specific session."""
    async with _global_lock:
        if session_id not in session_locks:
            session_locks[session_id] = asyncio.Lock()
        return session_locks[session_id]

async def validate_session(session_id: str) -> Dict[str, Any]:
    """
    Comprehensive session validation and health check.
    Returns session status with details about what's available.
    """
    status = {
        "exists": False,
        "has_vera": False,
        "has_session_data": False,
        "has_toolchain": False,
        "is_healthy": False,
        "issues": []
    }
    
    # Check if Vera instance exists
    if session_id in vera_instances:
        status["has_vera"] = True
        vera = vera_instances[session_id]
        
        # Verify Vera is properly initialized
        if not hasattr(vera, 'sess'):
            status["issues"].append("Vera instance missing session object")
        elif vera.sess.id != session_id:
            status["issues"].append(f"Session ID mismatch: {vera.sess.id} != {session_id}")
    else:
        status["issues"].append("No Vera instance found")
    
    # Check if session data exists
    if session_id in sessions:
        status["has_session_data"] = True
        session_data = sessions[session_id]
        
        # Verify session data integrity
        required_keys = ["created_at", "last_activity", "messages", "files", "vera"]
        missing_keys = [k for k in required_keys if k not in session_data]
        if missing_keys:
            status["issues"].append(f"Session data missing keys: {missing_keys}")
    else:
        status["issues"].append("No session data found")
    
    # Check if toolchain is configured
    if session_id in toolchain_executions:
        status["has_toolchain"] = True
    
    # Overall health check
    status["exists"] = status["has_vera"] or status["has_session_data"]
    status["is_healthy"] = (
        status["has_vera"] and 
        status["has_session_data"] and 
        len(status["issues"]) == 0
    )
    
    return status

async def repair_session(session_id: str) -> bool:
    """
    Attempt to repair a partially broken session.
    Returns True if repair was successful.
    """
    logger.info(f"Attempting to repair session {session_id}")
    status = await validate_session(session_id)
    
    if status["is_healthy"]:
        logger.info(f"Session {session_id} is already healthy")
        return True
    
    if not status["exists"]:
        logger.error(f"Cannot repair non-existent session {session_id}")
        return False
    
    repaired = False
    
    # Repair missing session data
    if status["has_vera"] and not status["has_session_data"]:
        logger.info(f"Recreating session data for {session_id}")
        vera = vera_instances[session_id]
        sessions[session_id] = {
            "created_at": datetime.utcnow().isoformat(),
            "last_activity": datetime.utcnow().isoformat(),
            "messages": [],
            "files": {},
            "vera": vera
        }
        repaired = True
    
    # Repair missing Vera instance (if we somehow have data but no Vera)
    if status["has_session_data"] and not status["has_vera"]:
        logger.warning(f"Session {session_id} has data but no Vera instance - cannot fully repair")
        # We can't recreate Vera without losing state, so mark as unrepairable
        return False
    
    # Repair missing toolchain monitoring
    if status["has_vera"] and not status["has_toolchain"]:
        logger.info(f"Recreating toolchain monitoring for {session_id}")
        toolchain_executions[session_id] = {}
        
        vera = vera_instances[session_id]
        if hasattr(vera, 'toolchain'):
            from Vera.ChatUI.api.Toolchain.toolchain_monitor_wrapper import EnhancedMonitoredToolChainPlanner
            if not isinstance(vera.toolchain, EnhancedMonitoredToolChainPlanner):
                original_toolchain = vera.toolchain
                vera.toolchain = EnhancedMonitoredToolChainPlanner(original_toolchain, session_id)
                logger.info(f"Wrapped toolchain with monitoring for session {session_id}")
        repaired = True
    
    # Verify repair was successful
    final_status = await validate_session(session_id)
    if final_status["is_healthy"]:
        logger.info(f"Successfully repaired session {session_id}")
        return True
    else:
        logger.warning(f"Session {session_id} repair incomplete. Issues: {final_status['issues']}")
        return repaired

def get_or_create_vera(session_id: str) -> Vera:
    """Get existing Vera instance or raise error with helpful message."""
    if session_id not in vera_instances:
        logger.error(f"Vera instance not found for session {session_id}")
        raise HTTPException(
            status_code=404, 
            detail="Session not found or expired. Please start a new session."
        )
    
    # Verify session integrity
    vera = vera_instances[session_id]
    if not hasattr(vera, 'sess') or vera.sess.id != session_id:
        logger.error(f"Session {session_id} has corrupted Vera instance")
        raise HTTPException(
            status_code=500,
            detail="Session data corrupted. Please start a new session."
        )
    
    logger.debug(f"Retrieved Vera instance for session: {session_id}")
    return vera

def get_orchestrator_for_session(session_id: str):
    """
    Get Vera's orchestrator and configure it for this session.
    
    The orchestrator is shared across all sessions (created by first Vera instance),
    but each task receives its session-specific Vera instance.
    
    Returns:
        Orchestrator instance configured for this session
        
    Raises:
        HTTPException if session or orchestrator not available
    """
    # Ensure session exists
    if session_id not in vera_instances:
        raise HTTPException(
            status_code=404,
            detail="Session not found. Please start a session first."
        )
    
    # Ensure orchestrator is connected
    if not _orchestrator_connected or not orchestrator_api.state.orchestrator:
        raise HTTPException(
            status_code=503,
            detail="Orchestrator not connected. This should have been connected on first session creation."
        )
    
    # Get this session's Vera instance
    vera = vera_instances[session_id]
    
    # Update orchestrator API state to use this session's Vera
    # (for tasks that don't get vera_instance passed explicitly)
    orchestrator_api.state.vera_instance = vera
    
    logger.debug(f"Orchestrator configured for session {session_id}")
    
    # Return the orchestrator (it's the same instance for all sessions)
    return orchestrator_api.state.orchestrator

@router.post("/start", response_model=SessionStartResponse)
async def start_session(resume_session_id: Optional[str] = None):
    """
    Start a new chat session or resume an existing one.
    
    Args:
        resume_session_id: Optional session ID to resume instead of creating new
    """
    global _orchestrator_connected
    
    try:
        # ... [all your existing resume logic stays the same] ...
        
        # Create new session
        logger.info("Creating new session")
        
        # Create Vera instance in thread pool
        def create_vera():
            return Vera()
        
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            vera = await loop.run_in_executor(executor, create_vera)

        session_id = vera.sess.id
        
        # Get lock for this new session
        lock = await get_session_lock(session_id)
        
        async with lock:
            # Double-check session doesn't already exist (race condition guard)
            if session_id in vera_instances or session_id in sessions:
                logger.warning(f"Session {session_id} was created concurrently, using existing")
                return SessionStartResponse(
                    session_id=session_id,
                    status="existing",
                    timestamp=datetime.utcnow().isoformat()
                )
            
            # Store Vera instance
            vera_instances[session_id] = vera
            
            # Create session data
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
                from Vera.ChatUI.api.Toolchain.toolchain_monitor_wrapper import EnhancedMonitoredToolChainPlanner
                original_toolchain = vera.toolchain
                vera.toolchain = EnhancedMonitoredToolChainPlanner(original_toolchain, session_id)
                logger.info(f"Wrapped toolchain with monitoring for session {session_id}")
            
            # ============================================================
            # CONNECT VERA'S ORCHESTRATOR TO API (FIRST SESSION ONLY)
            # ============================================================
            with _orchestrator_connect_lock:
                if not _orchestrator_connected:
                    try:
                        logger.info("[Orchestrator] Connecting Vera's orchestrator to API...")
                        
                        # Vera already created an orchestrator in __init__
                        # Just connect it to the API state and setup tracking
                        orchestrator_api.state.orchestrator = vera.orchestrator
                        orchestrator_api.state.vera_instance = vera
                        
                        # Setup tracking hooks
                        orchestrator_api.setup_orchestrator_tracking(vera.orchestrator)
                        
                        # Get stats
                        stats = vera.orchestrator.get_stats()
                        total_workers = sum(
                            pool.get("num_workers", 0)
                            for pool in stats.get("worker_pools", {}).values()
                        )
                        registered_tasks = len(list(vera.orchestrator.registry._tasks.keys())) if hasattr(vera.orchestrator.registry, '_tasks') else 0
                        
                        logger.info("[Orchestrator] ✓ Connected to Vera's orchestrator")
                        logger.info(f"[Orchestrator]   - Total workers: {total_workers}")
                        logger.info(f"[Orchestrator]   - Status: {'Running' if vera.orchestrator.running else 'Stopped'}")
                        logger.info(f"[Orchestrator]   - Registered tasks: {registered_tasks}")
                        logger.info(f"[Orchestrator]   - Task tracking: enabled")
                        
                        _orchestrator_connected = True
                        
                    except Exception as e:
                        logger.error(f"[Orchestrator] Failed to connect: {e}", exc_info=True)
                        # Don't fail session creation if orchestrator connection fails
                        # Mark as attempted to avoid repeated failures
                        _orchestrator_connected = True
            
            logger.info(f"Created new session: {session_id}")
            
            return SessionStartResponse(
                session_id=session_id,
                status="started",
                timestamp=datetime.utcnow().isoformat()
            )
            
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Session start error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to start session: {str(e)}")
    
@router.get("/{session_id}/status")
async def get_session_status(session_id: str):
    """Check if a session exists and get detailed health status."""
    status = await validate_session(session_id)
    
    if not status["exists"]:
        return {
            "exists": False,
            "session_id": session_id,
            **status
        }
    
    session = sessions.get(session_id, {})
    
    # Update last activity if session is healthy
    if status["is_healthy"] and session:
        session["last_activity"] = datetime.utcnow().isoformat()
    
    return {
        "exists": True,
        "session_id": session_id,
        "created_at": session.get("created_at"),
        "last_activity": session.get("last_activity"),
        "message_count": len(session.get("messages", [])),
        "websocket_connections": len(websocket_connections.get(session_id, [])),
        **status
    }

@router.post("/{session_id}/repair")
async def repair_session_endpoint(session_id: str):
    """Attempt to repair a partially broken session."""
    status = await validate_session(session_id)
    
    if status["is_healthy"]:
        return {
            "status": "healthy",
            "session_id": session_id,
            "message": "Session is already healthy, no repair needed"
        }
    
    if not status["exists"]:
        raise HTTPException(
            status_code=404,
            detail="Session does not exist, cannot repair"
        )
    
    success = await repair_session(session_id)
    
    if success:
        return {
            "status": "repaired",
            "session_id": session_id,
            "message": "Session successfully repaired"
        }
    else:
        final_status = await validate_session(session_id)
        raise HTTPException(
            status_code=500,
            detail=f"Session repair failed. Issues: {final_status['issues']}"
        )
    
@router.get("/orchestrator/status")
async def get_orchestrator_status():
    """Check orchestrator connection status"""
    from Vera.ChatUI.api.Orchestrator import orchestrator_api
    
    is_connected = _orchestrator_connected
    has_orchestrator = orchestrator_api.state.orchestrator is not None
    is_running = orchestrator_api.state.orchestrator.running if has_orchestrator else False
    
    response = {
        "connected": is_connected,
        "exists": has_orchestrator,
        "running": is_running,
        "ready": is_connected and has_orchestrator and is_running
    }
    
    if has_orchestrator and is_running:
        stats = orchestrator_api.state.orchestrator.get_stats()
        response["stats"] = {
            "total_workers": sum(
                pool.get("num_workers", 0) 
                for pool in stats.get("worker_pools", {}).values()
            ),
            "queue_size": sum(stats.get("queue_sizes", {}).values()),
            "registered_tasks": len(list(orchestrator_api.state.orchestrator.registry._tasks.keys()))
        }
    
    return response

@router.post("/{session_id}/end")
async def end_session(session_id: str):
    """End a chat session and cleanup resources."""
    if session_id not in sessions and session_id not in vera_instances:
        raise HTTPException(status_code=404, detail="Session not found")
    
    lock = await get_session_lock(session_id)
    async with lock:
        # Close all websockets for this session
        if session_id in websocket_connections:
            for ws in websocket_connections[session_id][:]:  # Copy list to avoid modification during iteration
                try:
                    await ws.close()
                except Exception as e:
                    logger.warning(f"Error closing websocket: {e}")
        
        # Cleanup all resources
        vera_instances.pop(session_id, None)
        sessions.pop(session_id, None)
        toolchain_executions.pop(session_id, None)
        active_toolchains.pop(session_id, None)
        websocket_connections.pop(session_id, None)
    
    # Cleanup the lock itself (after releasing it)
    async with _global_lock:
        session_locks.pop(session_id, None)
    
    logger.info(f"Ended session: {session_id}")
    return {"status": "ended", "session_id": session_id}

# ============================================================
# WebSocket Handler with Reconnection Support
# ============================================================

@router.websocket("/{session_id}/ws")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time communication with reconnection support."""
    await websocket.accept()
    
    # Validate session exists
    status = await validate_session(session_id)
    
    if not status["exists"]:
        await websocket.send_json({
            "type": "error",
            "message": "Session not found or expired",
            "session_id": session_id
        })
        await websocket.close()
        return
    
    # If session has issues, try to repair
    if not status["is_healthy"]:
        logger.warning(f"WebSocket connecting to unhealthy session {session_id}, attempting repair")
        if await repair_session(session_id):
            logger.info(f"Successfully repaired session {session_id} for WebSocket connection")
        else:
            await websocket.send_json({
                "type": "error",
                "message": "Session is corrupted and cannot be repaired",
                "session_id": session_id,
                "issues": status["issues"]
            })
            await websocket.close()
            return
    
    # Register this websocket
    websocket_connections[session_id].append(websocket)
    logger.info(f"WebSocket connected for session {session_id} (total: {len(websocket_connections[session_id])})")
    
    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "message": "WebSocket connection established"
        })
        
        # Keep connection alive and handle messages
        while True:
            try:
                data = await websocket.receive_json()
                
                # Handle different message types
                if data.get("type") == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                elif data.get("type") == "status":
                    # Send session status
                    session_status = await validate_session(session_id)
                    await websocket.send_json({
                        "type": "status",
                        "session_id": session_id,
                        **session_status,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                elif data.get("type") == "health_check":
                    # Perform health check and send result
                    session_status = await validate_session(session_id)
                    await websocket.send_json({
                        "type": "health_check_response",
                        **session_status,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                
                # Update last activity
                if session_id in sessions:
                    sessions[session_id]["last_activity"] = datetime.utcnow().isoformat()
                    
            except Exception as e:
                logger.error(f"Error processing WebSocket message: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                })
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}", exc_info=True)
    finally:
        # Cleanup on disconnect
        if websocket in websocket_connections.get(session_id, []):
            websocket_connections[session_id].remove(websocket)
            logger.info(f"Removed WebSocket for session {session_id} (remaining: {len(websocket_connections[session_id])})")

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
            
            for session_id, session_data in list(sessions.items()):
                try:
                    last_activity = datetime.fromisoformat(session_data["last_activity"])
                    # 2 hour timeout, but only if no active websocket connections
                    is_expired = now - last_activity > timedelta(hours=2)
                    has_connections = len(websocket_connections.get(session_id, [])) > 0
                    
                    if is_expired and not has_connections:
                        expired.append(session_id)
                except Exception as e:
                    logger.error(f"Error checking expiry for session {session_id}: {e}")
            
            for session_id in expired:
                logger.info(f"Cleaning up expired session: {session_id}")
                try:
                    await end_session(session_id)
                except Exception as e:
                    logger.error(f"Error cleaning up session {session_id}: {e}")
                    
        except Exception as e:
            logger.error(f"Error in cleanup task: {e}", exc_info=True)

# Start cleanup task when app starts
@router.on_event("startup")
async def startup_event():
    asyncio.create_task(cleanup_expired_sessions())
    logger.info("Session cleanup task started")