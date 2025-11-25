# session_history_api.py - Session History Management
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from concurrent.futures import ThreadPoolExecutor

from Vera.ChatUI.api.session import vera_instances, sessions, get_or_create_vera
from Vera.ChatUI.api.schemas import SessionStartResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/session", tags=["session-history"])


# ============================================================
# Request/Response Models
# ============================================================

class SessionSearchRequest(BaseModel):
    query: str = Field(..., description="Search query text")
    limit: int = Field(default=10, ge=1, le=50, description="Maximum results")
    include_messages: bool = Field(default=False, description="Include message previews")


class SessionListRequest(BaseModel):
    sort_by: str = Field(default="date", description="Sort by: date, relevance, message_count")
    sort_order: str = Field(default="desc", description="Sort order: asc, desc")
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    date_from: Optional[str] = None  # ISO format
    date_to: Optional[str] = None


class SessionSummary(BaseModel):
    session_id: str
    started_at: Optional[str] = None  # Made optional to handle missing data
    ended_at: Optional[str] = None
    message_count: int = 0
    last_activity: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None  # Made optional
    preview: Optional[str] = None  # First message preview
    relevance_score: Optional[float] = None


class SessionDetail(BaseModel):
    session_id: str
    started_at: Optional[str] = None  # Made optional
    ended_at: Optional[str] = None
    message_count: int
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None  # Made optional
    entities: List[Dict[str, Any]] = Field(default_factory=list)
    memory_items: List[Dict[str, Any]] = Field(default_factory=list)


# ============================================================
# Helper Functions
# ============================================================

async def get_session_from_memory(session_id: str) -> Optional[Dict[str, Any]]:
    """Get session details from Neo4j via Vera's memory system."""
    try:
        # Try to get from any active Vera instance
        vera = None
        if session_id in vera_instances:
            vera = vera_instances[session_id]
        else:
            # Get from any Vera instance to access shared memory
            if vera_instances:
                vera = next(iter(vera_instances.values()))
        
        if not vera or not hasattr(vera, 'mem'):
            return None
        
        # Query Neo4j for session - use correct pattern for finding memories
        with vera.mem.graph._driver.session() as neo_sess:
            result = neo_sess.run("""
                MATCH (s:Session {id: $session_id})
                OPTIONAL MATCH (e:Entity)
                WHERE e.extracted_from_session = $session_id 
                   OR (e)-[:EXTRACTED_IN]->(s)
                OPTIONAL MATCH (m)
                WHERE m.session_id = $session_id
                RETURN s, 
                       collect(DISTINCT e) as entities,
                       collect(DISTINCT m) as memories,
                       count(DISTINCT m) as message_count
            """, session_id=session_id).single()
            
            if not result:
                return None
            
            session_node = result["s"]
            entities = result["entities"] or []
            memories = result["memories"] or []
            
            # Get messages from memories
            messages = []
            for mem in memories:
                if mem and hasattr(mem, 'get'):
                    messages.append({
                        "id": mem.get("id"),
                        "text": mem.get("text"),
                        "timestamp": mem.get("created_at"),
                        "type": mem.get("type")
                    })
            
            # Sort messages by timestamp
            messages.sort(key=lambda x: x.get("timestamp", ""), reverse=False)
            
            return {
                "session_id": session_node.get("id"),
                "started_at": session_node.get("started_at") or datetime.utcnow().isoformat(),
                "ended_at": session_node.get("ended_at"),
                "metadata": session_node.get("metadata") or {},
                "message_count": result["message_count"] or 0,
                "messages": messages,
                "entities": [
                    {
                        "id": e.get("id"),
                        "text": e.get("text"),
                        "type": e.get("type"),
                        "label": list(e.labels) if hasattr(e, "labels") else []
                    }
                    for e in entities if e
                ]
            }
    except Exception as e:
        logger.error(f"Error getting session from memory: {e}", exc_info=True)
        return None


async def search_sessions_by_content(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Search across all session memories using vector similarity."""
    try:
        # Get any Vera instance to access memory
        if not vera_instances:
            return []
        
        vera = next(iter(vera_instances.values()))
        if not hasattr(vera, 'mem'):
            return []
        
        # Get all sessions from Neo4j
        with vera.mem.graph._driver.session() as neo_sess:
            result = neo_sess.run("""
                MATCH (s:Session)
                RETURN s.id as session_id, 
                       s.started_at as started_at,
                       coalesce(s.metadata, {}) as metadata
                ORDER BY coalesce(s.started_at, '') DESC
            """)
            
            all_sessions = [dict(record) for record in result]
        
        # Search each session's vector store
        session_results = []
        for session_info in all_sessions:
            sid = session_info["session_id"]
            try:
                # Search in session-specific collection
                hits = vera.mem.focus_context(sid, query, k=3)
                
                if hits:
                    # Calculate average relevance
                    avg_distance = sum(h.get("distance", 1.0) for h in hits) / len(hits)
                    relevance_score = 1.0 - avg_distance  # Convert distance to similarity
                    
                    # Get preview from best match
                    preview = hits[0].get("text", "")[:200] if hits else None
                    
                    session_results.append({
                        "session_id": sid,
                        "started_at": session_info.get("started_at") or datetime.utcnow().isoformat(),
                        "ended_at": None,
                        "metadata": session_info.get("metadata") or {},
                        "relevance_score": relevance_score,
                        "preview": preview,
                        "matched_memories": len(hits)
                    })
            except Exception as e:
                logger.warning(f"Error searching session {sid}: {e}")
                continue
        
        # Sort by relevance and limit
        session_results.sort(key=lambda x: x["relevance_score"], reverse=True)
        return session_results[:limit]
        
    except Exception as e:
        logger.error(f"Error in search_sessions_by_content: {e}", exc_info=True)
        return []


async def get_similar_sessions(session_id: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Find sessions semantically similar to the given session."""
    try:
        if not vera_instances:
            return []
        
        vera = next(iter(vera_instances.values()))
        if not hasattr(vera, 'mem'):
            return []
        
        # Get memories from the reference session
        ref_memories = vera.mem.get_session_memory(session_id)
        if not ref_memories:
            return []
        
        # Combine text from reference session
        ref_text = " ".join([m.text for m in ref_memories[:10]])  # Use first 10 memories
        
        # Search for similar sessions
        similar = await search_sessions_by_content(ref_text, limit=limit + 1)
        
        # Filter out the reference session itself
        similar = [s for s in similar if s["session_id"] != session_id]
        
        return similar[:limit]
        
    except Exception as e:
        logger.error(f"Error finding similar sessions: {e}", exc_info=True)
        return []


# ============================================================
# API Endpoints
# ============================================================

@router.get("/history", response_model=List[SessionSummary])
async def list_sessions(
    sort_by: str = Query("date", description="Sort by: date, message_count"),
    sort_order: str = Query("desc", description="asc or desc"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    date_from: Optional[str] = Query(None, description="ISO format date"),
    date_to: Optional[str] = Query(None, description="ISO format date"),
):
    """
    List all sessions with optional filtering and sorting.
    """
    try:
        # Get any Vera instance to access memory
        if not vera_instances:
            # Try to create a temporary one or return empty
            return []
        
        vera = next(iter(vera_instances.values()))
        if not hasattr(vera, 'mem'):
            return []
        
        # Build query - find memories by session_id property
        query = "MATCH (s:Session) "
        where_clauses = []
        params = {}
        
        # Date filters (only if started_at exists)
        if date_from:
            where_clauses.append("s.started_at >= $date_from")
            params["date_from"] = date_from
        if date_to:
            where_clauses.append("s.started_at <= $date_to")
            params["date_to"] = date_to
        
        if where_clauses:
            query += "WHERE " + " AND ".join(where_clauses) + " "
        
        # Count memories - look for nodes with matching session_id property
        query += """
        OPTIONAL MATCH (m)
        WHERE m.session_id = s.id
        WITH s, count(DISTINCT m) as msg_count
        WHERE msg_count > 0
        """
        
        # Sorting - handle None values
        if sort_by == "date":
            query += f"ORDER BY coalesce(s.started_at, '') {sort_order.upper()} "
        elif sort_by == "message_count":
            query += f"ORDER BY msg_count {sort_order.upper()} "
        
        # Pagination
        query += f"SKIP {offset} LIMIT {limit} "
        
        query += """
        RETURN s.id as session_id,
               s.started_at as started_at,
               coalesce(s.metadata, {}) as metadata,
               msg_count as message_count
        """
        
        with vera.mem.graph._driver.session() as neo_sess:
            result = neo_sess.run(query, params)
            
            sessions_list = []
            for record in result:
                sid = record["session_id"]
                
                # Skip if session_id is None
                if not sid:
                    continue
                
                # DISABLED: Getting previews causes excessive logging
                # Get preview from first memory
                preview = None
                # try:
                #     memories = vera.mem.get_session_memory(sid)
                #     if memories:
                #         preview = memories[0].text[:150] + "..." if len(memories[0].text) > 150 else memories[0].text
                # except Exception as e:
                #     logger.debug(f"Could not get preview for session {sid}: {e}")
                
                # Create session summary with safe defaults
                sessions_list.append(SessionSummary(
                    session_id=sid,
                    started_at=record.get("started_at") or datetime.utcnow().isoformat(),
                    ended_at=None,  # Not querying this anymore
                    message_count=record.get("message_count") or 0,
                    metadata=record.get("metadata") or {},
                    preview=preview
                ))
            
            return sessions_list
            
    except Exception as e:
        logger.error(f"Error listing sessions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}/details", response_model=SessionDetail)
async def get_session_details(session_id: str, include_all_messages: bool = Query(False)):
    """
    Get detailed information about a specific session.
    """
    try:
        session_data = await get_session_from_memory(session_id)
        
        if not session_data:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Limit messages if not requesting all
        messages = session_data["messages"]
        if not include_all_messages:
            messages = messages[-20:]  # Last 20 messages
        
        return SessionDetail(
            session_id=session_data["session_id"],
            started_at=session_data["started_at"],
            ended_at=session_data.get("ended_at"),
            message_count=session_data["message_count"],
            messages=messages,
            metadata=session_data.get("metadata", {}),
            entities=session_data.get("entities", []),
            memory_items=messages
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session details: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search", response_model=List[SessionSummary])
async def search_sessions(request: SessionSearchRequest):
    """
    Search for sessions by content using semantic similarity.
    """
    try:
        results = await search_sessions_by_content(request.query, limit=request.limit)
        
        summaries = []
        for result in results:
            summary = SessionSummary(
                session_id=result["session_id"],
                started_at=result["started_at"],
                ended_at=result.get("ended_at"),
                message_count=result.get("matched_memories", 0),
                metadata=result.get("metadata", {}),
                preview=result.get("preview"),
                relevance_score=result.get("relevance_score")
            )
            summaries.append(summary)
        
        return summaries
        
    except Exception as e:
        logger.error(f"Error searching sessions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}/similar", response_model=List[SessionSummary])
async def get_similar_sessions_endpoint(
    session_id: str,
    limit: int = Query(5, ge=1, le=20)
):
    """
    Find sessions semantically similar to the given session.
    """
    try:
        similar = await get_similar_sessions(session_id, limit=limit)
        
        summaries = []
        for result in similar:
            summary = SessionSummary(
                session_id=result["session_id"],
                started_at=result["started_at"],
                ended_at=result.get("ended_at"),
                message_count=result.get("matched_memories", 0),
                metadata=result.get("metadata", {}),
                preview=result.get("preview"),
                relevance_score=result.get("relevance_score")
            )
            summaries.append(summary)
        
        return summaries
        
    except Exception as e:
        logger.error(f"Error finding similar sessions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{session_id}/resume", response_model=SessionStartResponse)
async def resume_session(session_id: str):
    """
    Resume an existing session. Loads the session if not already active.
    """
    try:
        # Check if session exists in Neo4j
        session_data = await get_session_from_memory(session_id)
        if not session_data:
            raise HTTPException(status_code=404, detail="Session not found in history")
        
        # If already active, just return it
        if session_id in vera_instances:
            logger.info(f"Resuming active session: {session_id}")
            return SessionStartResponse(
                session_id=session_id,
                status="resumed",
                timestamp=datetime.utcnow().isoformat()
            )
        
        # Load session by creating new Vera instance with this session ID
        def create_vera_with_session():
            from Vera.vera import Vera
            vera = Vera()
            # Override the session ID to match the one we're resuming
            vera.sess.id = session_id
            return vera
        
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            vera = await loop.run_in_executor(executor, create_vera_with_session)
        
        vera_instances[session_id] = vera
        sessions[session_id] = {
            "created_at": session_data["started_at"],
            "last_activity": datetime.utcnow().isoformat(),
            "messages": session_data.get("messages", []),
            "files": {},
            "vera": vera,
            "resumed": True
        }
        
        logger.info(f"Resumed session from history: {session_id}")
        
        return SessionStartResponse(
            session_id=session_id,
            status="resumed_from_history",
            timestamp=datetime.utcnow().isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resuming session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{session_id}/archive")
async def archive_session(session_id: str):
    """
    Archive a session (mark as ended but keep in history).
    """
    try:
        if not vera_instances:
            raise HTTPException(status_code=404, detail="No active sessions")
        
        vera = next(iter(vera_instances.values()))
        if not hasattr(vera, 'mem'):
            raise HTTPException(status_code=500, detail="Memory system not available")
        
        # Mark session as ended in Neo4j
        vera.mem.end_session(session_id)
        
        # Remove from active sessions
        vera_instances.pop(session_id, None)
        sessions.pop(session_id, None)
        
        logger.info(f"Archived session: {session_id}")
        
        return {
            "status": "archived",
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error archiving session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/summary")
async def get_session_statistics():
    """
    Get overall session statistics.
    """
    try:
        if not vera_instances:
            return {
                "total_sessions": 0,
                "active_sessions": 0,
                "archived_sessions": 0
            }
        
        vera = next(iter(vera_instances.values()))
        if not hasattr(vera, 'mem'):
            raise HTTPException(status_code=500, detail="Memory system not available")
        
        with vera.mem.graph._driver.session() as neo_sess:
            result = neo_sess.run("""
                MATCH (s:Session)
                RETURN count(s) as total
            """).single()
            
            # Count active sessions from in-memory tracking
            active_count = len([s for s in sessions.values() if not s.get('ended_at')])
            
            return {
                "total_sessions": result["total"] or 0,
                "active_sessions": active_count,
                "archived_sessions": (result["total"] or 0) - active_count,
                "currently_loaded": len(vera_instances)
            }
            
    except Exception as e:
        logger.error(f"Error getting session statistics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))