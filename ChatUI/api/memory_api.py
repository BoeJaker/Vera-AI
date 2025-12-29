from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict, Any
import logging

from Vera.ChatUI.api.schemas import (
    MemoryQueryRequest,
    MemoryQueryResponse,
    HybridRetrievalRequest,
    EntityExtractionRequest,
    EntityExtractionResponse,
    SubgraphRequest
)

from Vera.ChatUI.api.session import vera_instances, sessions, toolchain_executions, active_toolchains, websocket_connections
from Vera.ChatUI.api.session import get_or_create_vera

# ============================================================
# Logging setup
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# Router setup
# ============================================================
router = APIRouter(prefix="/api/memory", tags=["memory"])

# ============================================================
# Memory Endpoints 
# ============================================================

@router.post("/query", response_model=MemoryQueryResponse)
async def query_memory(request: MemoryQueryRequest):
    """
    Query memory using vector, graph, or hybrid retrieval.
    FIXED: Properly handles all retrieval types with fallbacks
    """
    if request.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(request.session_id)
    
    try:
        results = []
        k = request.k or 50
        
        if request.retrieval_type == "vector":
            # Session memory search
            try:
                session_results = vera.mem.focus_context(
                    request.session_id, 
                    request.query, 
                    k=k
                )
                results.extend(normalize_results(session_results, "session"))
            except Exception as e:
                logger.error(f"Session vector search failed: {e}")
            
            # Long-term memory search
            try:
                long_term_results = vera.mem.semantic_retrieve(
                    request.query,
                    k=k,
                    where=build_chroma_filters(request.filters) if request.filters else None
                )
                results.extend(normalize_results(long_term_results, "long_term"))
            except Exception as e:
                logger.error(f"Long-term vector search failed: {e}")
                
        elif request.retrieval_type == "graph":
            # Graph-based search
            results = await search_graph_mode(vera, request.session_id, request.query, k)
            
        elif request.retrieval_type == "hybrid":
            # Hybrid search combining all sources
            results = await hybrid_search(vera, request.session_id, request.query, k, request.filters)
            
        else:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid retrieval_type: {request.retrieval_type}"
            )
        
        # Apply filters if provided
        if request.filters:
            results = apply_filters(results, request.filters)
        
        # Deduplicate by id
        seen = set()
        unique_results = []
        for r in results:
            if r.get("id") not in seen:
                seen.add(r["id"])
                unique_results.append(r)
        
        return MemoryQueryResponse(
            results=unique_results,
            retrieval_type=request.retrieval_type,
            query=request.query,
            session_id=request.session_id,
            total_results=len(unique_results)
        )
        
    except Exception as e:
        logger.error(f"Memory query error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/hybrid-retrieve")
async def hybrid_retrieve(request: HybridRetrievalRequest):
    """
    Advanced hybrid retrieval combining vector and graph.
    FIXED: Better error handling and result normalization
    """
    if request.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(request.session_id)
    
    try:
        k_vector = request.k_vector or 50
        k_graph = request.k_graph or 25
        
        # Vector results
        session_hits = []
        long_term_hits = []
        
        try:
            session_hits = vera.mem.focus_context(
                request.session_id,
                request.query,
                k=k_vector
            )
        except Exception as e:
            logger.error(f"Session vector search failed: {e}")
        
        try:
            long_term_hits = vera.mem.semantic_retrieve(
                request.query,
                k=k_vector,
                where=build_chroma_filters(request.filters) if request.filters else None
            )
        except Exception as e:
            logger.error(f"Long-term vector search failed: {e}")
        
        # Extract entity seeds from vector results
        seed_entity_ids = set()
        
        for hit in session_hits + long_term_hits:
            metadata = hit.get("metadata", {})
            
            if "entity_ids" in metadata:
                if isinstance(metadata["entity_ids"], list):
                    seed_entity_ids.update(metadata["entity_ids"])
                else:
                    seed_entity_ids.add(metadata["entity_ids"])
            
            if metadata.get("type") == "extracted_entity":
                seed_entity_ids.add(hit["id"])
        
        # Get graph context
        graph_context = None
        if seed_entity_ids and request.include_entities:
            try:
                seed_list = list(seed_entity_ids)[:k_graph]
                graph_context = vera.mem.extract_subgraph(
                    seed_list,
                    depth=request.graph_depth
                )
            except Exception as e:
                logger.error(f"Subgraph extraction failed: {e}")
                graph_context = {"nodes": [], "rels": []}
        
        return {
            "session_id": request.session_id,
            "query": request.query,
            "vector_results": {
                "session": normalize_results(session_hits, "session"),
                "long_term": normalize_results(long_term_hits, "long_term"),
                "total": len(session_hits) + len(long_term_hits)
            },
            "graph_context": graph_context,
            "seed_entities": list(seed_entity_ids),
            "retrieval_stats": {
                "k_vector": k_vector,
                "k_graph": k_graph,
                "graph_depth": request.graph_depth,
                "entities_found": len(seed_entity_ids),
                "graph_nodes": len(graph_context.get("nodes", [])) if graph_context else 0,
                "graph_relationships": len(graph_context.get("rels", [])) if graph_context else 0
            }
        }
        
    except Exception as e:
        logger.error(f"Hybrid retrieval error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/subgraph")
async def get_memory_subgraph(request: SubgraphRequest):
    """
    Extract a subgraph around specific entity IDs.
    FIXED: Better error handling and empty result handling
    """
    if request.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(request.session_id)
    
    try:
        if not request.seed_entity_ids:
            return {
                "session_id": request.session_id,
                "seed_entity_ids": [],
                "depth": request.depth,
                "subgraph": {"nodes": [], "rels": []},
                "stats": {"nodes": 0, "relationships": 0}
            }
        
        subgraph = vera.mem.extract_subgraph(
            request.seed_entity_ids,
            depth=request.depth
        )
        
        return {
            "session_id": request.session_id,
            "seed_entity_ids": request.seed_entity_ids,
            "depth": request.depth,
            "subgraph": subgraph,
            "stats": {
                "nodes": len(subgraph.get("nodes", [])),
                "relationships": len(subgraph.get("rels", []))
            }
        }
        
    except Exception as e:
        logger.error(f"Subgraph extraction error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}/entities")
async def list_session_entities(
    session_id: str,
    limit: Optional[int] = Query(50),
    search: Optional[str] = Query(None),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    entity_types: Optional[List[str]] = Query(None)
):
    """
    List all entities extracted in a session.
    FIXED: Added search and filtering
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    try:
        with vera.mem.graph._driver.session() as db_sess:
            cypher = """
                MATCH (s:Session {id: $session_id})-[:EXTRACTED_IN]-(e:ExtractedEntity)
                WHERE e.confidence >= $min_confidence
            """
            
            params = {
                "session_id": session_id,
                "min_confidence": min_confidence,
                "limit": limit
            }
            
            # Add search filter
            if search:
                cypher += " AND (e.text CONTAINS $search OR e.id CONTAINS $search)"
                params["search"] = search
            
            # Add entity type filter
            if entity_types:
                cypher += " AND any(label IN labels(e) WHERE label IN $entity_types)"
                params["entity_types"] = entity_types
            
            cypher += """
                RETURN e.id AS id, 
                       e.text AS text, 
                       e.type AS type,
                       labels(e) AS labels,
                       e.confidence AS confidence,
                       e.original_text AS original_text
                ORDER BY e.confidence DESC
                LIMIT $limit
            """
            
            result = db_sess.run(cypher, params)
            
            entities = []
            for record in result:
                entities.append({
                    "id": record["id"],
                    "text": record["text"],
                    "type": record["type"],
                    "labels": record["labels"],
                    "confidence": record.get("confidence", 0.0),
                    "original_text": record.get("original_text")
                })
            
            return {
                "session_id": session_id,
                "entities": entities,
                "total": len(entities)
            }
            
    except Exception as e:
        logger.error(f"Error listing entities: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}/relationships")
async def list_session_relationships(
    session_id: str,
    limit: Optional[int] = Query(50),
    search: Optional[str] = Query(None),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0)
):
    """
    List all relationships extracted in a session.
    FIXED: Better query structure and search
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    try:
        with vera.mem.graph._driver.session() as db_sess:
            cypher = """
                MATCH (s:Session {id: $session_id})-[:EXTRACTED_IN]-(e1:ExtractedEntity)
                MATCH (e1)-[r:REL]->(e2:ExtractedEntity)
                WHERE r.extracted_from_session = $session_id
                  AND r.confidence >= $min_confidence
            """
            
            params = {
                "session_id": session_id,
                "min_confidence": min_confidence,
                "limit": limit
            }
            
            if search:
                cypher += """ AND (
                    e1.text CONTAINS $search OR 
                    e2.text CONTAINS $search OR 
                    r.rel CONTAINS $search
                )"""
                params["search"] = search
            
            cypher += """
                RETURN e1.text AS head, 
                       r.rel AS relation,
                       e2.text AS tail, 
                       r.confidence AS confidence,
                       r.context AS context,
                       r AS properties
                ORDER BY r.confidence DESC
                LIMIT $limit
            """
            
            result = db_sess.run(cypher, params)
            
            relationships = []
            for record in result:
                relationships.append({
                    "head": record["head"],
                    "relation": record["relation"],
                    "tail": record["tail"],
                    "confidence": record.get("confidence", 0.0),
                    "context": record.get("context", "")
                })
            
            return {
                "session_id": session_id,
                "relationships": relationships,
                "total": len(relationships)
            }
            
    except Exception as e:
        logger.error(f"Error listing relationships: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Helper Functions
# ============================================================

def normalize_results(results: List[Dict[str, Any]], source: str) -> List[Dict[str, Any]]:
    """Normalize results to consistent format"""
    normalized = []
    for r in results:
        normalized.append({
            "id": r.get("id", ""),
            "text": r.get("text", r.get("document", "")),
            "type": r.get("metadata", {}).get("type", "memory"),
            "source": source,
            "confidence": r.get("confidence", 1.0 - r.get("distance", 0.0)),
            "distance": r.get("distance"),
            "metadata": r.get("metadata", {}),
            "displayText": r.get("text", r.get("document", ""))[:200]
        })
    return normalized


async def search_graph_mode(vera, session_id: str, query: str, k: int) -> List[Dict[str, Any]]:
    """
    Enhanced graph search that actually works
    """
    results = []
    
    try:
        # First, get some vector hits to find relevant entities
        vector_hits = vera.mem.focus_context(session_id, query, k=min(10, k))
        
        # Extract entity IDs
        seed_ids = set()
        for hit in vector_hits:
            metadata = hit.get("metadata", {})
            if "entity_ids" in metadata:
                if isinstance(metadata["entity_ids"], list):
                    seed_ids.update(metadata["entity_ids"])
                else:
                    seed_ids.add(metadata["entity_ids"])
        
        # If we found seed IDs, get subgraph
        if seed_ids:
            subgraph = vera.mem.extract_subgraph(list(seed_ids)[:20], depth=2)
            
            # Convert nodes to results
            for node in subgraph.get("nodes", []):
                results.append({
                    "id": node["id"],
                    "type": "graph_node",
                    "text": node.get("properties", {}).get("text", node["id"]),
                    "source": "graph",
                    "confidence": node.get("properties", {}).get("confidence", 1.0),
                    "metadata": node.get("properties", {}),
                    "labels": node.get("labels", []),
                    "displayText": node.get("properties", {}).get("text", node["id"])[:200]
                })
            
            # Convert relationships to results
            for rel in subgraph.get("rels", []):
                if rel.get("start") and rel.get("end"):
                    results.append({
                        "id": f"{rel['start']}-{rel['end']}",
                        "type": "relationship",
                        "head": rel["start"],
                        "tail": rel["end"],
                        "relation": rel.get("type", "RELATED_TO"),
                        "source": "graph",
                        "confidence": rel.get("properties", {}).get("confidence", 1.0),
                        "metadata": rel.get("properties", {}),
                        "displayText": f"{rel['start']} → {rel['end']}"
                    })
        
        # If no seeds found, search graph directly
        if not results:
            with vera.mem.graph._driver.session() as db_sess:
                cypher = """
                    MATCH (e:ExtractedEntity)
                    WHERE e.text CONTAINS $query OR e.id CONTAINS $query
                    RETURN e.id AS id, e.text AS text, e.type AS type,
                           labels(e) AS labels, e AS properties
                    LIMIT $k
                """
                rec = db_sess.run(cypher, {"query": query, "k": k})
                
                for record in rec:
                    results.append({
                        "id": record["id"],
                        "type": "graph_node",
                        "text": record["text"],
                        "source": "graph",
                        "confidence": 1.0,
                        "labels": record["labels"],
                        "metadata": dict(record["properties"]),
                        "displayText": record["text"][:200]
                    })
        
    except Exception as e:
        logger.error(f"Graph search failed: {e}")
    
    return results


async def hybrid_search(vera, session_id: str, query: str, k: int, filters: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    True hybrid search combining all sources
    """
    all_results = []
    
    # Vector search - session
    try:
        session_hits = vera.mem.focus_context(session_id, query, k=k)
        all_results.extend(normalize_results(session_hits, "session"))
    except Exception as e:
        logger.error(f"Session search failed: {e}")
    
    # Vector search - long term
    try:
        long_term_hits = vera.mem.semantic_retrieve(
            query, 
            k=k,
            where=build_chroma_filters(filters) if filters else None
        )
        all_results.extend(normalize_results(long_term_hits, "long_term"))
    except Exception as e:
        logger.error(f"Long-term search failed: {e}")
    
    # Graph search
    try:
        graph_results = await search_graph_mode(vera, session_id, query, k)
        all_results.extend(graph_results)
    except Exception as e:
        logger.error(f"Graph search failed: {e}")
    
    return all_results


def build_chroma_filters(filters: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Build Chroma-compatible filter dictionary"""
    if not filters:
        return None
    
    chroma_filters = {}
    
    if filters.get("minConfidence", 0) > 0:
        chroma_filters["confidence"] = {"$gte": filters["minConfidence"]}
    
    if filters.get("entityTypes"):
        chroma_filters["type"] = {"$in": filters["entityTypes"]}
    
    return chroma_filters if chroma_filters else None


def apply_filters(results: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Apply filtering to results"""
    filtered = results
    
    if filters.get("minConfidence", 0) > 0:
        min_conf = filters["minConfidence"]
        filtered = [r for r in filtered if r.get("confidence", 0) >= min_conf]
    
    if filters.get("entityTypes"):
        types = set(filters["entityTypes"])
        filtered = [r for r in filtered if 
            r.get("type") in types or 
            any(label in types for label in r.get("labels", []))
        ]
    
    return filtered



# Add this helper function before the chat endpoints
async def get_enhanced_context(vera, session_id: str, message: str, k: int = 5) -> Dict[str, Any]:
    """
    Get enhanced context using hybrid retrieval for chat responses.
    """
    try:
        # Session-specific vector retrieval
        session_context = vera.mem.focus_context(session_id, message, k=k)
        
        # Long-term semantic retrieval
        long_term_context = vera.mem.semantic_retrieve(message, k=k)
        
        # Extract entity IDs for graph context
        entity_ids = set()
        for hit in session_context + long_term_context:
            metadata = hit.get("metadata", {})
            if "entity_ids" in metadata:
                entity_ids.update(metadata["entity_ids"])
            if metadata.get("type") == "extracted_entity":
                entity_ids.add(hit["id"])
        
        # Get graph context if entities found
        graph_context = None
        if entity_ids:
            graph_context = vera.mem.extract_subgraph(list(entity_ids)[:3], depth=1)
        
        return {
            "session_context": session_context,
            "long_term_context": long_term_context,
            "graph_context": graph_context,
            "entity_ids": list(entity_ids)
        }
    except Exception as e:
        logger.error(f"Error getting enhanced context: {e}")
        return {
            "session_context": [],
            "long_term_context": [],
            "graph_context": None,
            "entity_ids": []
        }

@router.post("/vector-content")
async def get_vector_content(request: Dict[str, Any]):
    """
    Fetch vector store content for specific node IDs.
    Returns the full text stored in vector collections.
    """
    node_ids = request.get("node_ids", [])
    session_id = request.get("session_id")
    
    logger.info(f"=== Vector Content Request ===")
    logger.info(f"Requested node_ids: {node_ids}")
    logger.info(f"Session ID: {session_id}")
    
    if not node_ids:
        return {"content": {}, "debug": "No node IDs provided"}
    
    try:
        vera = None
        if session_id and session_id in sessions:
            vera = get_or_create_vera(session_id)
            logger.info(f"Using session {session_id}")
        else:
            # Get any vera instance
            for sid in sessions:
                vera = get_or_create_vera(sid)
                logger.info(f"Using fallback session {sid}")
                break
        
        if not vera:
            logger.error("No active session available")
            return {"content": {}, "error": "No active session", "debug": "No vera instance"}
        
        content = {}
        debug_info = {
            "collections_checked": [],
            "collections_found": [],
            "ids_checked": node_ids,
            "ids_found": [],
            "errors": []
        }
        
        # Check session collections first (all sessions)
        all_session_ids = list(sessions.keys())
        logger.info(f"Checking {len(all_session_ids)} session collections")
        
        for sid in all_session_ids:
            try:
                collection_name = f"session_{sid}"
                debug_info["collections_checked"].append(collection_name)
                
                col = vera.mem.vec.get_collection(collection_name)
                
                # First, check what's in the collection
                all_items = col.get()
                logger.info(f"Collection '{collection_name}' has {len(all_items.get('ids', []))} items")
                logger.debug(f"Sample IDs in collection: {all_items.get('ids', [])[:5]}")
                
                # Try to get our specific IDs
                result = col.get(ids=node_ids)
                
                logger.info(f"Query result for {collection_name}: {len(result.get('ids', []))} matches")
                
                if result and result.get("ids"):
                    debug_info["collections_found"].append(collection_name)
                    for i, nid in enumerate(result["ids"]):
                        if nid not in content:  # Don't overwrite if found in earlier session
                            text = result["documents"][i] if result.get("documents") else ""
                            metadata = result["metadatas"][i] if result.get("metadatas") else {}
                            
                            content[nid] = {
                                "text": text,
                                "metadata": metadata,
                                "source": f"session_{sid}"
                            }
                            debug_info["ids_found"].append(nid)
                            
                            logger.info(f"✓ Found content for {nid}: {len(text)} chars from {collection_name}")
                            
            except Exception as e:
                error_msg = f"Session collection {sid} error: {str(e)}"
                logger.error(error_msg, exc_info=True)
                debug_info["errors"].append(error_msg)
                continue
        
        # Check long-term collection
        try:
            collection_name = "long_term_docs"
            debug_info["collections_checked"].append(collection_name)
            
            long_term_col = vera.mem.vec.get_collection(collection_name)
            
            # Check what's in the collection
            all_items = long_term_col.get()
            logger.info(f"Long-term collection has {len(all_items.get('ids', []))} items")
            logger.debug(f"Sample IDs in long-term: {all_items.get('ids', [])[:5]}")
            
            result = long_term_col.get(ids=node_ids)
            
            logger.info(f"Query result for long-term: {len(result.get('ids', []))} matches")
            
            if result and result.get("ids"):
                debug_info["collections_found"].append(collection_name)
                for i, nid in enumerate(result["ids"]):
                    if nid not in content:  # Don't overwrite session data
                        text = result["documents"][i] if result.get("documents") else ""
                        metadata = result["metadatas"][i] if result.get("metadatas") else {}
                        
                        content[nid] = {
                            "text": text,
                            "metadata": metadata,
                            "source": "long_term"
                        }
                        debug_info["ids_found"].append(nid)
                        
                        logger.info(f"✓ Found content for {nid}: {len(text)} chars from long-term")
                        
        except Exception as e:
            error_msg = f"Long-term collection error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            debug_info["errors"].append(error_msg)
        
        logger.info(f"=== Vector Content Summary ===")
        logger.info(f"Found content for {len(content)} out of {len(node_ids)} requested nodes")
        logger.info(f"Collections checked: {debug_info['collections_checked']}")
        logger.info(f"Collections with data: {debug_info['collections_found']}")
        
        return {
            "content": content,
            "found_count": len(content),
            "requested_count": len(node_ids),
            "debug": debug_info
        }
        
    except Exception as e:
        logger.error(f"Error fetching vector content: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/vector-debug/{session_id}")
async def debug_vector_store(session_id: str):
    """
    Debug endpoint to see what's actually in the vector stores.
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    try:
        debug_info = {}
        
        # Check session collection
        session_collection = f"session_{session_id}"
        try:
            col = vera.mem.vec.get_collection(session_collection)
            all_items = col.get()
            
            debug_info[session_collection] = {
                "count": len(all_items.get("ids", [])),
                "sample_ids": all_items.get("ids", [])[:10],
                "sample_texts": [t[:100] + "..." if len(t) > 100 else t 
                               for t in all_items.get("documents", [])[:3]]
            }
        except Exception as e:
            debug_info[session_collection] = {"error": str(e)}
        
        # Check long-term collection
        try:
            long_term_col = vera.mem.vec.get_collection("long_term_docs")
            all_items = long_term_col.get()
            
            debug_info["long_term_docs"] = {
                "count": len(all_items.get("ids", [])),
                "sample_ids": all_items.get("ids", [])[:10],
                "sample_texts": [t[:100] + "..." if len(t) > 100 else t 
                               for t in all_items.get("documents", [])[:3]]
            }
        except Exception as e:
            debug_info["long_term_docs"] = {"error": str(e)}
        
        return debug_info
        
    except Exception as e:
        logger.error(f"Debug error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))