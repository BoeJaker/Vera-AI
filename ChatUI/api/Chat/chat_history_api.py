# session_history_api_optimized.py - OPTIMIZED Session History Management
import asyncio
import logging
import re
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
# Utility Functions
# ============================================================

def extract_timestamp_from_session_id(session_id: str) -> Optional[int]:
    """
    Extract timestamp from session_id like 'sess_1764359943042'.
    Returns timestamp in milliseconds or None if not found.
    """
    if not session_id:
        return None
    
    match = re.match(r'sess_(\d+)', session_id)
    if match:
        try:
            return int(match.group(1))
        except (ValueError, IndexError):
            return None
    return None


def get_session_sort_timestamp(session_data: Dict[str, Any]) -> float:
    """
    Get the best available timestamp for sorting a session.
    Priority:
    1. Timestamp from session_id (sess_1764359943042)
    2. started_at field
    3. created_at field
    4. Current time (fallback)
    
    Returns timestamp as float (seconds since epoch)
    """
    session_id = session_data.get('session_id')
    
    if session_id:
        ts_ms = extract_timestamp_from_session_id(session_id)
        if ts_ms:
            return ts_ms / 1000.0
    
    started_at = session_data.get('started_at')
    if started_at:
        try:
            dt = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
            return dt.timestamp()
        except (ValueError, AttributeError):
            pass
    
    created_at = session_data.get('created_at')
    if created_at:
        try:
            dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            return dt.timestamp()
        except (ValueError, AttributeError):
            pass
    
    return datetime.utcnow().timestamp()


def session_id_to_iso_timestamp(session_id: str) -> Optional[str]:
    """Convert session_id timestamp to ISO format string."""
    ts_ms = extract_timestamp_from_session_id(session_id)
    if ts_ms:
        try:
            dt = datetime.fromtimestamp(ts_ms / 1000.0)
            return dt.isoformat()
        except (ValueError, OSError):
            return None
    return None


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
    date_from: Optional[str] = None
    date_to: Optional[str] = None


class SessionSummary(BaseModel):
    session_id: str
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    message_count: int = 0
    last_activity: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    preview: Optional[str] = None
    relevance_score: Optional[float] = None


class SessionDetail(BaseModel):
    session_id: str
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    message_count: int
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None
    entities: List[Dict[str, Any]] = Field(default_factory=list)
    memory_items: List[Dict[str, Any]] = Field(default_factory=list)


# ============================================================
# Helper Functions
# ============================================================

async def get_session_from_memory(session_id: str) -> Optional[Dict[str, Any]]:
    """Get session details from Neo4j via Vera's memory system."""
    try:
        vera = None
        if session_id in vera_instances:
            vera = vera_instances[session_id]
        else:
            if vera_instances:
                vera = next(iter(vera_instances.values()))
        
        if not vera or not hasattr(vera, 'mem'):
            return None
        
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
            
            messages = []
            for mem in memories:
                if not mem:
                    continue
                
                text_content = None
                
                if hasattr(mem, 'get'):
                    text_content = (
                        mem.get("text") or 
                        mem.get("content") or 
                        mem.get("message") or
                        mem.get("data")
                    )
                elif hasattr(mem, '__getitem__'):
                    try:
                        text_content = (
                            mem.get("text") or 
                            mem.get("content") or 
                            mem.get("message") or
                            mem.get("data")
                        )
                    except:
                        pass
                
                properties = {}
                if hasattr(mem, 'items'):
                    properties = dict(mem.items())
                elif hasattr(mem, '_properties'):
                    properties = mem._properties
                
                if not text_content and properties:
                    for key, value in properties.items():
                        if isinstance(value, str) and len(value) > 10 and key not in ['id', 'type', 'session_id']:
                            text_content = value
                            break
                
                if not text_content:
                    logger.debug(f"Could not extract text from memory node: {properties}")
                    continue
                
                messages.append({
                    "id": properties.get("id", "unknown"),
                    "text": text_content,
                    "timestamp": properties.get("created_at") or properties.get("timestamp"),
                    "type": properties.get("type", "message"),
                    "role": properties.get("role")
                })
            
            messages.sort(key=lambda x: x.get("timestamp", ""), reverse=False)
            
            started_at = session_node.get("started_at")
            if not started_at:
                started_at = session_id_to_iso_timestamp(session_id)
            if not started_at:
                started_at = datetime.utcnow().isoformat()
            
            return {
                "session_id": session_node.get("id"),
                "started_at": started_at,
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
    """
    OPTIMIZED: Search across sessions using best available method.
    Priority:
    1. Global ChromaDB collection (if available)
    2. Neo4j full-text search
    3. Recent sessions fallback
    """
    try:
        if not vera_instances:
            return []
        
        vera = next(iter(vera_instances.values()))
        if not hasattr(vera, 'mem'):
            return []
        
        # STRATEGY 1: Try global collection
        global_collection_name = "global_memory_search"
        
        try:
            collection = vera.mem.client.get_collection(global_collection_name)
            logger.info(f"Using global collection for search: {global_collection_name}")
            
            results = collection.query(
                query_texts=[query],
                n_results=min(limit * 10, 100),
                include=['documents', 'distances', 'metadatas']
            )
            
            session_matches = {}
            
            if results and results.get('ids') and len(results['ids'][0]) > 0:
                for i, doc_id in enumerate(results['ids'][0]):
                    metadata = results['metadatas'][0][i] if results.get('metadatas') else {}
                    session_id = metadata.get('session_id')
                    
                    if not session_id:
                        continue
                    
                    distance = results['distances'][0][i]
                    document = results['documents'][0][i] if results.get('documents') else ""
                    
                    if session_id not in session_matches:
                        session_matches[session_id] = {
                            'distances': [],
                            'documents': [],
                            'count': 0
                        }
                    
                    session_matches[session_id]['distances'].append(distance)
                    session_matches[session_id]['documents'].append(document)
                    session_matches[session_id]['count'] += 1
            
            session_results = []
            for session_id, matches in session_matches.items():
                avg_distance = sum(matches['distances']) / len(matches['distances'])
                relevance_score = 1.0 - min(avg_distance, 1.0)
                
                preview = matches['documents'][0][:200] if matches['documents'] else None
                
                session_results.append({
                    'session_id': session_id,
                    'relevance_score': relevance_score,
                    'preview': preview,
                    'matched_memories': matches['count']
                })
            
            if session_results:
                session_ids = [s['session_id'] for s in session_results]
                
                with vera.mem.graph._driver.session() as neo_sess:
                    result = neo_sess.run("""
                        MATCH (s:Session)
                        WHERE s.id IN $session_ids
                        RETURN s.id as session_id,
                               s.started_at as started_at,
                               coalesce(s.metadata, {}) as metadata
                    """, session_ids=session_ids)
                    
                    session_metadata = {r['session_id']: dict(r) for r in result}
                
                for session in session_results:
                    sid = session['session_id']
                    if sid in session_metadata:
                        meta = session_metadata[sid]
                        started_at = meta.get('started_at')
                        if not started_at:
                            started_at = session_id_to_iso_timestamp(sid)
                        if not started_at:
                            started_at = datetime.utcnow().isoformat()
                        
                        session.update({
                            'started_at': started_at,
                            'ended_at': None,
                            'metadata': meta.get('metadata') or {}
                        })
            
            session_results.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
            
            logger.info(f"Global search found {len(session_results)} sessions")
            return session_results[:limit]
            
        except Exception as e:
            logger.warning(f"Global collection not available: {e}")
            logger.info("Falling back to Neo4j full-text search...")
        
        # STRATEGY 2: Neo4j full-text search
        try:
            session_results = await search_sessions_via_neo4j(vera, query, limit)
            if session_results:
                return session_results
        except Exception as e:
            logger.warning(f"Neo4j search failed: {e}")
        
        # STRATEGY 3: Emergency fallback
        logger.warning("Using emergency fallback: searching recent sessions only")
        return await search_recent_sessions_only(vera, query, limit)
        
    except Exception as e:
        logger.error(f"Error in search_sessions_by_content: {e}", exc_info=True)
        return []


async def search_sessions_via_neo4j(vera, query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Use Neo4j text search - much faster than vector search."""
    try:
        with vera.mem.graph._driver.session() as neo_sess:
            result = neo_sess.run("""
                MATCH (m)
                WHERE m.session_id IS NOT NULL 
                  AND (
                    toLower(m.text) CONTAINS toLower($query)
                    OR toLower(m.content) CONTAINS toLower($query)
                  )
                WITH m.session_id as session_id, 
                     collect(m.text)[0] as preview,
                     count(*) as match_count
                ORDER BY match_count DESC
                LIMIT $limit
                
                MATCH (s:Session {id: session_id})
                RETURN session_id,
                       s.started_at as started_at,
                       coalesce(s.metadata, {}) as metadata,
                       preview,
                       match_count
            """, query=query, limit=limit * 2)
            
            session_results = []
            for record in result:
                sid = record['session_id']
                started_at = record.get('started_at')
                if not started_at:
                    started_at = session_id_to_iso_timestamp(sid)
                if not started_at:
                    started_at = datetime.utcnow().isoformat()
                
                preview = record.get('preview', '')[:200] if record.get('preview') else None
                
                session_results.append({
                    'session_id': sid,
                    'started_at': started_at,
                    'ended_at': None,
                    'metadata': record.get('metadata') or {},
                    'relevance_score': min(1.0, record.get('match_count', 1) / 10.0),
                    'preview': preview,
                    'matched_memories': record.get('match_count', 0)
                })
            
            logger.info(f"Neo4j search found {len(session_results)} sessions")
            return session_results[:limit]
            
    except Exception as e:
        logger.error(f"Neo4j search error: {e}", exc_info=True)
        return []


async def search_recent_sessions_only(vera, query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Emergency fallback: Search only recent sessions."""
    max_sessions = 50
    logger.warning(f"Searching only {max_sessions} recent sessions (performance limitation)")
    
    try:
        with vera.mem.graph._driver.session() as neo_sess:
            # FIXED: Don't count messages, just get recent sessions
            result = neo_sess.run("""
                MATCH (s:Session)
                RETURN s.id as session_id, 
                       s.started_at as started_at,
                       coalesce(s.metadata, {}) as metadata
                ORDER BY s.started_at DESC
                LIMIT $limit
            """, limit=max_sessions)
            
            recent_sessions = [dict(record) for record in result]
        
        session_results = []
        batch_size = 5
        
        for i in range(0, len(recent_sessions), batch_size):
            batch = recent_sessions[i:i + batch_size]
            tasks = [search_single_session(vera, s, query, None) for s in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in batch_results:
                if result and not isinstance(result, Exception):
                    session_results.append(result)
        
        session_results.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        return session_results[:limit]
        
    except Exception as e:
        logger.error(f"Emergency fallback error: {e}", exc_info=True)
        return []


async def search_single_session(vera, session_info: Dict[str, Any], query: str, query_embedding=None) -> Optional[Dict[str, Any]]:
    """Search a single session."""
    sid = session_info["session_id"]
    
    try:
        loop = asyncio.get_event_loop()
        
        def blocking_search():
            try:
                return vera.mem.focus_context(sid, query, k=3)
            except Exception as e:
                logger.debug(f"Error searching session {sid}: {e}")
                return None
        
        with ThreadPoolExecutor(max_workers=1) as executor:
            hits = await loop.run_in_executor(executor, blocking_search)
        
        if not hits:
            return None
        
        avg_distance = sum(h.get("distance", 1.0) for h in hits) / len(hits)
        relevance_score = 1.0 - avg_distance
        
        if relevance_score < 0.3:
            return None
        
        preview = hits[0].get("text", "")[:200] if hits else None
        
        started_at = session_info.get("started_at")
        if not started_at:
            started_at = session_id_to_iso_timestamp(sid)
        if not started_at:
            started_at = datetime.utcnow().isoformat()
        
        return {
            "session_id": sid,
            "started_at": started_at,
            "ended_at": None,
            "metadata": session_info.get("metadata") or {},
            "relevance_score": relevance_score,
            "preview": preview,
            "matched_memories": len(hits)
        }
        
    except Exception as e:
        logger.debug(f"Exception searching session {sid}: {e}")
        return None


async def get_similar_sessions(session_id: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Find sessions semantically similar to the given session."""
    try:
        if not vera_instances:
            return []
        
        vera = next(iter(vera_instances.values()))
        if not hasattr(vera, 'mem'):
            return []
        
        ref_memories = vera.mem.get_session_memory(session_id)
        if not ref_memories:
            return []
        
        ref_text = " ".join([m.text for m in ref_memories[:10]])
        
        similar = await search_sessions_by_content(ref_text, limit=limit + 1)
        similar = [s for s in similar if s["session_id"] != session_id]
        
        return similar[:limit]
        
    except Exception as e:
        logger.error(f"Error finding similar sessions: {e}", exc_info=True)
        return []


# ============================================================
# API Endpoints - OPTIMIZED
# ============================================================

@router.get("/history", response_model=List[SessionSummary])
async def list_sessions(
    sort_by: str = Query("date", description="Sort by: date, message_count"),
    sort_order: str = Query("desc", description="asc or desc"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    date_from: Optional[str] = Query(None, description="ISO format date"),
    date_to: Optional[str] = Query(None, description="ISO format date"),
    include_previews: bool = Query(False, description="EXPENSIVE: Fetch previews")
):
    """
    ULTRA-OPTIMIZED: Returns sessions WITHOUT counting messages.
    Message counting is done lazily on the frontend.
    """
    import time
    start_time = time.time()
    
    try:
        if not vera_instances:
            logger.info("No vera instances available")
            return []
        
        vera = next(iter(vera_instances.values()))
        if not hasattr(vera, 'mem'):
            logger.info("No memory system available")
            return []
        
        # ULTRA-FAST: Just get session nodes, NO message counting
        query = "MATCH (s:Session) "
        where_clauses = []
        params = {}
        
        if date_from:
            where_clauses.append("s.started_at >= $date_from")
            params["date_from"] = date_from
        if date_to:
            where_clauses.append("s.started_at <= $date_to")
            params["date_to"] = date_to
        
        if where_clauses:
            query += "WHERE " + " AND ".join(where_clauses) + " "
        
        # NO message counting - just return sessions
        # SKIP and LIMIT for pagination
        query += """
        RETURN s.id as session_id,
               s.started_at as started_at,
               coalesce(s.metadata, {}) as metadata
        ORDER BY s.started_at DESC
        SKIP $offset
        LIMIT $limit
        """
        
        params["offset"] = offset
        params["limit"] = limit
        
        query_start = time.time()
        logger.info(f"Executing ULTRA-FAST session query (no message count)")
        
        with vera.mem.graph._driver.session() as neo_sess:
            result = neo_sess.run(query, params)
            
            query_time = time.time() - query_start
            logger.info(f"Query execution time: {query_time:.3f}s")
            
            process_start = time.time()
            sessions_list = []
            for record in result:
                sid = record["session_id"]
                
                if not sid:
                    continue
                
                started_at = record.get("started_at")
                if not started_at:
                    started_at = session_id_to_iso_timestamp(sid)
                if not started_at:
                    started_at = datetime.utcnow().isoformat()
                
                sessions_list.append({
                    "session_id": sid,
                    "started_at": started_at,
                    "ended_at": None,
                    "message_count": 0,  # Default to 0, load lazily if needed
                    "metadata": record.get("metadata") or {},
                    "preview": None
                })
            
            process_time = time.time() - process_start
            logger.info(f"Processing time: {process_time:.3f}s")
            
            total_time = time.time() - start_time
            logger.info(f"TOTAL TIME: {total_time:.3f}s - Returned {len(sessions_list)} sessions")
            
            return [SessionSummary(**s) for s in sessions_list]
            
    except Exception as e:
        logger.error(f"Error listing sessions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}/details", response_model=SessionDetail)
async def get_session_details(session_id: str, include_all_messages: bool = Query(False)):
    """Get detailed information about a specific session."""
    try:
        session_data = await get_session_from_memory(session_id)
        
        if not session_data:
            raise HTTPException(status_code=404, detail="Session not found")
        
        messages = session_data["messages"]
        if not include_all_messages:
            messages = messages[-20:]
        
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
    """Search for sessions by content using semantic similarity."""
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
    """Find sessions semantically similar to the given session."""
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
    """Resume an existing session."""
    try:
        session_data = await get_session_from_memory(session_id)
        if not session_data:
            raise HTTPException(status_code=404, detail="Session not found in history")
        
        if session_id in vera_instances:
            logger.info(f"Resuming active session: {session_id}")
            return SessionStartResponse(
                session_id=session_id,
                status="resumed",
                timestamp=datetime.utcnow().isoformat()
            )
        
        def create_vera_with_session():
            from Vera.vera import Vera
            vera = Vera()
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
    """Archive a session."""
    try:
        if not vera_instances:
            raise HTTPException(status_code=404, detail="No active sessions")
        
        vera = next(iter(vera_instances.values()))
        if not hasattr(vera, 'mem'):
            raise HTTPException(status_code=500, detail="Memory system not available")
        
        vera.mem.end_session(session_id)
        
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
    """Get overall session statistics."""
    try:
        if not vera_instances:
            return {
                "total_sessions": 0,
                "active_sessions": 0,
                "archived_sessions": 0,
                "currently_loaded": 0
            }
        
        vera = next(iter(vera_instances.values()))
        if not hasattr(vera, 'mem'):
            raise HTTPException(status_code=500, detail="Memory system not available")
        
        with vera.mem.graph._driver.session() as neo_sess:
            result = neo_sess.run("""
                MATCH (s:Session)
                RETURN count(s) as total
            """).single()
            
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


@router.get("/{session_id}/debug")
async def debug_session_structure(session_id: str):
    """Debug endpoint to see memory node structure."""
    try:
        if not vera_instances:
            raise HTTPException(status_code=404, detail="No active Vera instances")
        
        vera = next(iter(vera_instances.values()))
        if not hasattr(vera, 'mem'):
            raise HTTPException(status_code=500, detail="Memory system not available")
        
        with vera.mem.graph._driver.session() as neo_sess:
            result = neo_sess.run("""
                MATCH (m)
                WHERE m.session_id = $session_id
                RETURN m
                LIMIT 5
            """, session_id=session_id)
            
            sample_nodes = []
            for record in result:
                node = record["m"]
                
                properties = {}
                if hasattr(node, 'items'):
                    properties = dict(node.items())
                elif hasattr(node, '_properties'):
                    properties = node._properties
                else:
                    properties = {"error": "Could not extract properties"}
                
                labels = list(node.labels) if hasattr(node, 'labels') else []
                
                sample_nodes.append({
                    "labels": labels,
                    "properties": properties,
                    "property_keys": list(properties.keys())
                })
            
            return {
                "session_id": session_id,
                "sample_memory_nodes": sample_nodes,
                "note": "Use this to determine message text property"
            }
            
    except Exception as e:
        logger.error(f"Error debugging session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))