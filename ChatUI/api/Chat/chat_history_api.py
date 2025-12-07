# session_history_api.py - Session History Management
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
    
    # Pattern: sess_{timestamp}
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
    
    # Try to extract from session_id first
    if session_id:
        ts_ms = extract_timestamp_from_session_id(session_id)
        if ts_ms:
            return ts_ms / 1000.0  # Convert to seconds
    
    # Try started_at
    started_at = session_data.get('started_at')
    if started_at:
        try:
            dt = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
            return dt.timestamp()
        except (ValueError, AttributeError):
            pass
    
    # Try created_at
    created_at = session_data.get('created_at')
    if created_at:
        try:
            dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            return dt.timestamp()
        except (ValueError, AttributeError):
            pass
    
    # Fallback to current time
    return datetime.utcnow().timestamp()


def session_id_to_iso_timestamp(session_id: str) -> Optional[str]:
    """
    Convert session_id timestamp to ISO format string.
    Returns None if extraction fails.
    """
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
                if not mem:
                    continue
                
                # Memory nodes have different property structures
                # Try multiple common property names for the content
                text_content = None
                
                # Try different property names
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
                
                # Get all properties from the node to debug
                properties = {}
                if hasattr(mem, 'items'):
                    properties = dict(mem.items())
                elif hasattr(mem, '_properties'):
                    properties = mem._properties
                
                # Fallback: try to get any text-like property
                if not text_content and properties:
                    for key, value in properties.items():
                        if isinstance(value, str) and len(value) > 10 and key not in ['id', 'type', 'session_id']:
                            text_content = value
                            break
                
                # Skip if we couldn't find any content
                if not text_content:
                    logger.debug(f"Could not extract text from memory node: {properties}")
                    continue
                
                messages.append({
                    "id": properties.get("id", "unknown"),
                    "text": text_content,
                    "timestamp": properties.get("created_at") or properties.get("timestamp"),
                    "type": properties.get("type", "message"),
                    "role": properties.get("role")  # Include role if present
                })
            
            # Sort messages by timestamp
            messages.sort(key=lambda x: x.get("timestamp", ""), reverse=False)
            
            # Extract timestamp from session_id or use fallback
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
    Search across all session memories using vector similarity.
    
    With 20,000+ sessions, we MUST use a global collection approach.
    This function attempts to use a global collection, or builds one if needed.
    """
    try:
        # Get any Vera instance to access memory
        if not vera_instances:
            return []
        
        vera = next(iter(vera_instances.values()))
        if not hasattr(vera, 'mem'):
            return []
        
        # STRATEGY 1: Try to use a global collection if it exists
        # This should be the primary method for production use
        global_collection_name = "global_memory_search"
        
        try:
            # Check if global collection exists
            collection = vera.mem.client.get_collection(global_collection_name)
            
            logger.info(f"Using global collection for search: {global_collection_name}")
            
            # Search the global collection
            results = collection.query(
                query_texts=[query],
                n_results=min(limit * 10, 100),  # Get more results to group by session
                include=['documents', 'distances', 'metadatas']
            )
            
            # Group results by session_id
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
            
            # Calculate session-level relevance scores
            session_results = []
            for session_id, matches in session_matches.items():
                avg_distance = sum(matches['distances']) / len(matches['distances'])
                relevance_score = 1.0 - min(avg_distance, 1.0)
                
                # Get preview from best match (first one, since results are sorted by distance)
                preview = matches['documents'][0][:200] if matches['documents'] else None
                
                session_results.append({
                    'session_id': session_id,
                    'relevance_score': relevance_score,
                    'preview': preview,
                    'matched_memories': matches['count']
                })
            
            # Get session metadata from Neo4j
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
                
                # Enrich session results with metadata
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
            
            # Sort by relevance
            session_results.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
            
            logger.info(f"Global search found {len(session_results)} sessions with matches")
            
            return session_results[:limit]
            
        except Exception as e:
            logger.warning(f"Global collection not available or error: {e}")
            logger.info("Falling back to Neo4j full-text search...")
        
        # STRATEGY 2: Use Neo4j full-text search if available
        # This is much faster than vector search across 20k sessions
        try:
            session_results = await search_sessions_via_neo4j(vera, query, limit)
            if session_results:
                return session_results
        except Exception as e:
            logger.warning(f"Neo4j full-text search failed: {e}")
        
        # STRATEGY 3: Emergency fallback - search only recent sessions
        logger.warning("Using emergency fallback: searching only 50 most recent sessions")
        return await search_recent_sessions_only(vera, query, limit)
        
    except Exception as e:
        logger.error(f"Error in search_sessions_by_content: {e}", exc_info=True)
        return []


async def search_sessions_via_neo4j(vera, query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Use Neo4j's built-in text search capabilities to find sessions.
    This is much faster than vector search for 20k+ sessions.
    """
    try:
        with vera.mem.graph._driver.session() as neo_sess:
            # Search for nodes that contain the query text
            # This uses case-insensitive pattern matching
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
                    'relevance_score': min(1.0, record.get('match_count', 1) / 10.0),  # Normalize
                    'preview': preview,
                    'matched_memories': record.get('match_count', 0)
                })
            
            logger.info(f"Neo4j text search found {len(session_results)} sessions")
            return session_results[:limit]
            
    except Exception as e:
        logger.error(f"Error in Neo4j search: {e}", exc_info=True)
        return []


async def search_recent_sessions_only(vera, query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Emergency fallback: Only search the 50 most recent sessions.
    This prevents resource exhaustion but limits search scope.
    """
    try:
        max_sessions = 50
        logger.warning(f"PERFORMANCE WARNING: Searching only {max_sessions} most recent sessions out of 20,000+")
        logger.warning("To search all sessions efficiently, you need to:")
        logger.warning("1. Create a global ChromaDB collection with all memories")
        logger.warning("2. Or enable Neo4j full-text indexes on memory nodes")
        
        with vera.mem.graph._driver.session() as neo_sess:
            result = neo_sess.run("""
                MATCH (s:Session)
                OPTIONAL MATCH (m)
                WHERE m.session_id = s.id
                WITH s, count(DISTINCT m) as msg_count
                WHERE msg_count > 0
                RETURN s.id as session_id, 
                       s.started_at as started_at,
                       coalesce(s.metadata, {}) as metadata
                ORDER BY coalesce(s.started_at, '') DESC
                LIMIT $limit
            """, limit=max_sessions)
            
            recent_sessions = [dict(record) for record in result]
        
        # Search sessions concurrently in small batches
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
        logger.error(f"Error in emergency fallback search: {e}", exc_info=True)
        return []


async def search_single_session(vera, session_info: Dict[str, Any], query: str, query_embedding=None) -> Optional[Dict[str, Any]]:
    """Search a single session - designed to be run concurrently."""
    sid = session_info["session_id"]
    
    try:
        # Use ThreadPoolExecutor for the blocking ChromaDB call
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
        
        # Calculate average relevance
        avg_distance = sum(h.get("distance", 1.0) for h in hits) / len(hits)
        relevance_score = 1.0 - avg_distance
        
        # Only return if relevance is reasonable
        if relevance_score < 0.3:
            return None
        
        # Get preview from best match
        preview = hits[0].get("text", "")[:200] if hits else None
        
        # Get started_at with fallback
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
                
                # Get started_at with fallback to session_id timestamp
                started_at = record.get("started_at")
                if not started_at:
                    started_at = session_id_to_iso_timestamp(sid)
                if not started_at:
                    started_at = datetime.utcnow().isoformat()
                
                # DISABLED: Getting previews causes excessive logging
                # Get preview from first memory
                preview = None
                
                # Create session summary with safe defaults
                sessions_list.append({
                    "session_id": sid,
                    "started_at": started_at,
                    "ended_at": None,
                    "message_count": record.get("message_count") or 0,
                    "metadata": record.get("metadata") or {},
                    "preview": preview
                })
            
            # Sort using the timestamp extraction function
            if sort_by == "date":
                sessions_list.sort(
                    key=get_session_sort_timestamp,
                    reverse=(sort_order == "desc")
                )
            elif sort_by == "message_count":
                sessions_list.sort(
                    key=lambda x: x.get("message_count", 0),
                    reverse=(sort_order == "desc")
                )
            
            # Apply pagination after sorting
            total = len(sessions_list)
            sessions_list = sessions_list[offset:offset + limit]
            
            # Convert to SessionSummary models
            return [SessionSummary(**s) for s in sessions_list]
            
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


@router.get("/{session_id}/debug")
async def debug_session_structure(session_id: str):
    """
    Debug endpoint to see the actual structure of memory nodes.
    Use this to understand what properties are available.
    """
    try:
        if not vera_instances:
            raise HTTPException(status_code=404, detail="No active Vera instances")
        
        vera = next(iter(vera_instances.values()))
        if not hasattr(vera, 'mem'):
            raise HTTPException(status_code=500, detail="Memory system not available")
        
        with vera.mem.graph._driver.session() as neo_sess:
            # Get a sample of memory nodes
            result = neo_sess.run("""
                MATCH (m)
                WHERE m.session_id = $session_id
                RETURN m
                LIMIT 5
            """, session_id=session_id)
            
            sample_nodes = []
            for record in result:
                node = record["m"]
                
                # Extract all properties
                properties = {}
                if hasattr(node, 'items'):
                    properties = dict(node.items())
                elif hasattr(node, '_properties'):
                    properties = node._properties
                else:
                    properties = {"error": "Could not extract properties"}
                
                # Get labels
                labels = list(node.labels) if hasattr(node, 'labels') else []
                
                sample_nodes.append({
                    "labels": labels,
                    "properties": properties,
                    "property_keys": list(properties.keys())
                })
            
            return {
                "session_id": session_id,
                "sample_memory_nodes": sample_nodes,
                "note": "Use this to determine which property contains the message text"
            }
            
    except Exception as e:
        logger.error(f"Error debugging session structure: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))