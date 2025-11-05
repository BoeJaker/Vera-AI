# ============================================================
# Imports
# ============================================================
import asyncio
import logging
from datetime import datetime
from fastapi import FastAPI, HTTPException
from concurrent.futures import ThreadPoolExecutor
from vera import Vera
from toolchain import MonitoredToolChainPlanner
from your_project.models.session import SessionStartResponse 

from state import vera_instances, sessions, toolchain_executions, active_toolchains, websocket_connections

# ============================================================
# Globals / storage
# ============================================================
logger = logging.getLogger(__name__)
app = FastAPI()

# ============================================================
# Session Management
# ============================================================
def get_or_create_vera(session_id: str) -> Vera:
    """Get or create a Vera instance for a session."""
    if session_id not in vera_instances:
        logger.warning(f"Vera instance not found for session {session_id}, creating new one")
        raise HTTPException(
            status_code=400, 
            detail="Session not properly initialized. Please start a new session."
        )
    return vera_instances[session_id]

@app.post("/api/session/start", response_model=SessionStartResponse)
async def start_session():
    """Start a new chat session."""
    try:
        from concurrent.futures import ThreadPoolExecutor
        
        def create_vera():
            return Vera()
        
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            vera = await loop.run_in_executor(executor, create_vera)
        
        session_id = vera.sess.id
        vera_instances[session_id] = vera
        
        sessions[session_id] = {
            "created_at": datetime.utcnow().isoformat(),
            "messages": [],
            "files": {},
            "vera": vera
        }
        
        # Initialize toolchain storage for this session
        toolchain_executions[session_id] = {}
        
        # IMPORTANT: Wrap Vera's toolchain with monitoring
        if hasattr(vera, 'toolchain'):
            original_toolchain = vera.toolchain
            vera.toolchain = MonitoredToolChainPlanner(original_toolchain, session_id)
            logger.info(f"Wrapped toolchain with monitoring for session {session_id}")
        
        logger.info(f"Started session: {session_id}")
        
        return SessionStartResponse(
            session_id=session_id,
            status="started",
            timestamp=datetime.utcnow().isoformat()
        )
    except Exception as e:
        logger.error(f"Session start error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start session: {str(e)}")


@app.post("/api/session/{session_id}/end")
async def end_session(session_id: str):
    """End a chat session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Cleanup
    vera_instances.pop(session_id, None)
    sessions.pop(session_id, None)
    toolchain_executions.pop(session_id, None)
    active_toolchains.pop(session_id, None)
    
    return {"status": "ended", "session_id": session_id}
