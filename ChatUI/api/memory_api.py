<<<<<<< HEAD
from fastapi import APIRouter, HTTPException
from typing import Optional
=======
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict, Any
>>>>>>> dev-vera-ollama-fixed
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
<<<<<<< HEAD
    
    Retrieval types:
    - vector: Semantic search using embeddings
    - graph: Graph traversal from relevant nodes
    - hybrid: Combined vector + graph retrieval
=======
    FIXED: Properly handles all retrieval types with fallbacks
>>>>>>> dev-vera-ollama-fixed
    """
    if request.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(request.session_id)
    
    try:
        results = []
<<<<<<< HEAD
        
        if request.retrieval_type == "vector":
            # Pure vector retrieval from session memory
            vector_results = vera.mem.focus_context(
                request.session_id, 
                request.query, 
                k=request.k
            )
            results = vector_results
            
        elif request.retrieval_type == "graph":
            # Graph-based retrieval
            # First, find relevant entities via vector search
            vector_hits = vera.mem.focus_context(
                request.session_id, 
                request.query, 
                k=3
            )
            
            # Extract entity IDs from hits
            seed_ids = []
            for hit in vector_hits:
                # Look for linked entities in metadata
                if "entity_ids" in hit.get("metadata", {}):
                    seed_ids.extend(hit["metadata"]["entity_ids"])
            
            if seed_ids:
                # Get subgraph around these entities
                subgraph = vera.mem.extract_subgraph(seed_ids[:5], depth=2)
                results = [{
                    "type": "subgraph",
                    "nodes": subgraph["nodes"],
                    "relationships": subgraph["rels"]
                }]
            else:
                results = []
                
        elif request.retrieval_type == "hybrid":
            # Hybrid retrieval: vector + graph
            vector_results = vera.mem.focus_context(
                request.session_id, 
                request.query, 
                k=request.k
            )
            
            # Get long-term semantic results too
            long_term_results = vera.mem.semantic_retrieve(
                request.query,
                k=request.k,
                where=request.filters
            )
            
            # Combine and deduplicate
            seen_ids = set()
            combined = []
            
            for result in vector_results + long_term_results:
                if result["id"] not in seen_ids:
                    seen_ids.add(result["id"])
                    combined.append(result)
            
            results = combined[:request.k]
=======
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
>>>>>>> dev-vera-ollama-fixed
            
        else:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid retrieval_type: {request.retrieval_type}"
            )
        
<<<<<<< HEAD
        return MemoryQueryResponse(
            results=results,
            retrieval_type=request.retrieval_type,
            query=request.query,
            session_id=request.session_id
=======
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
>>>>>>> dev-vera-ollama-fixed
        )
        
    except Exception as e:
        logger.error(f"Memory query error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/hybrid-retrieve")
async def hybrid_retrieve(request: HybridRetrievalRequest):
    """
<<<<<<< HEAD
    Advanced hybrid retrieval combining vector search and graph traversal.
    Returns both semantic matches and related entities from the knowledge graph.
=======
    Advanced hybrid retrieval combining vector and graph.
    FIXED: Better error handling and result normalization
>>>>>>> dev-vera-ollama-fixed
    """
    if request.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(request.session_id)
    
    try:
<<<<<<< HEAD
        # Step 1: Vector retrieval from session context
        session_hits = vera.mem.focus_context(
            request.session_id,
            request.query,
            k=request.k_vector
        )
        
        # Step 2: Vector retrieval from long-term memory
        long_term_hits = vera.mem.semantic_retrieve(
            request.query,
            k=request.k_vector,
            where=request.filters
        )
        
        # Step 3: Extract entity IDs for graph traversal
=======
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
>>>>>>> dev-vera-ollama-fixed
        seed_entity_ids = set()
        
        for hit in session_hits + long_term_hits:
            metadata = hit.get("metadata", {})
            
<<<<<<< HEAD
            # Check for linked entities
            if "entity_ids" in metadata:
                seed_entity_ids.update(metadata["entity_ids"])
            
            # If hit itself is an entity
            if metadata.get("type") == "extracted_entity":
                seed_entity_ids.add(hit["id"])
        
        # Step 4: Graph traversal around seed entities
        graph_context = None
        if seed_entity_ids and request.include_entities:
            seed_list = list(seed_entity_ids)[:request.k_graph]
            graph_context = vera.mem.extract_subgraph(
                seed_list,
                depth=request.graph_depth
            )
        
        # Step 5: Combine results
=======
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
        
>>>>>>> dev-vera-ollama-fixed
        return {
            "session_id": request.session_id,
            "query": request.query,
            "vector_results": {
<<<<<<< HEAD
                "session": session_hits,
                "long_term": long_term_hits,
=======
                "session": normalize_results(session_hits, "session"),
                "long_term": normalize_results(long_term_hits, "long_term"),
>>>>>>> dev-vera-ollama-fixed
                "total": len(session_hits) + len(long_term_hits)
            },
            "graph_context": graph_context,
            "seed_entities": list(seed_entity_ids),
            "retrieval_stats": {
<<<<<<< HEAD
                "k_vector": request.k_vector,
                "k_graph": request.k_graph,
                "graph_depth": request.graph_depth,
                "entities_found": len(seed_entity_ids)
=======
                "k_vector": k_vector,
                "k_graph": k_graph,
                "graph_depth": request.graph_depth,
                "entities_found": len(seed_entity_ids),
                "graph_nodes": len(graph_context.get("nodes", [])) if graph_context else 0,
                "graph_relationships": len(graph_context.get("rels", [])) if graph_context else 0
>>>>>>> dev-vera-ollama-fixed
            }
        }
        
    except Exception as e:
        logger.error(f"Hybrid retrieval error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


<<<<<<< HEAD
@router.post("/extract-entities", response_model=EntityExtractionResponse)
async def extract_entities(request: EntityExtractionRequest):
    """
    Extract entities and relationships from text using NLP.
    Links extracted entities to the session graph.
    """
    if request.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(request.session_id)
    
    try:
        extraction = vera.mem.extract_and_link(
            request.session_id,
            request.text,
            source_node_id=request.source_node_id,
            auto_promote=request.auto_promote
        )
        
        return EntityExtractionResponse(
            entities=extraction.get("entities", []),
            relations=extraction.get("relations", []),
            clusters=extraction.get("clusters", {}),
            session_id=request.session_id
        )
        
    except Exception as e:
        logger.error(f"Entity extraction error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


=======
>>>>>>> dev-vera-ollama-fixed
@router.post("/subgraph")
async def get_memory_subgraph(request: SubgraphRequest):
    """
    Extract a subgraph around specific entity IDs.
<<<<<<< HEAD
    Useful for exploring knowledge graph neighborhoods.
=======
    FIXED: Better error handling and empty result handling
>>>>>>> dev-vera-ollama-fixed
    """
    if request.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(request.session_id)
    
    try:
<<<<<<< HEAD
=======
        if not request.seed_entity_ids:
            return {
                "session_id": request.session_id,
                "seed_entity_ids": [],
                "depth": request.depth,
                "subgraph": {"nodes": [], "rels": []},
                "stats": {"nodes": 0, "relationships": 0}
            }
        
>>>>>>> dev-vera-ollama-fixed
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
<<<<<<< HEAD
async def list_session_entities(session_id: str, limit: int = 50):
    """
    List all entities extracted in a session.
=======
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
>>>>>>> dev-vera-ollama-fixed
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    try:
        with vera.mem.graph._driver.session() as db_sess:
<<<<<<< HEAD
            result = db_sess.run("""
                MATCH (s:Session {id: $session_id})-[:EXTRACTED_IN]-(e:ExtractedEntity)
=======
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
>>>>>>> dev-vera-ollama-fixed
                RETURN e.id AS id, 
                       e.text AS text, 
                       e.type AS type,
                       labels(e) AS labels,
                       e.confidence AS confidence,
                       e.original_text AS original_text
                ORDER BY e.confidence DESC
                LIMIT $limit
<<<<<<< HEAD
            """, {"session_id": session_id, "limit": limit})
=======
            """
            
            result = db_sess.run(cypher, params)
>>>>>>> dev-vera-ollama-fixed
            
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
<<<<<<< HEAD
async def list_session_relationships(session_id: str, limit: int = 50):
    """
    List all relationships extracted in a session.
=======
async def list_session_relationships(
    session_id: str,
    limit: Optional[int] = Query(50),
    search: Optional[str] = Query(None),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0)
):
    """
    List all relationships extracted in a session.
    FIXED: Better query structure and search
>>>>>>> dev-vera-ollama-fixed
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    try:
        with vera.mem.graph._driver.session() as db_sess:
<<<<<<< HEAD
            result = db_sess.run("""
                MATCH (s:Session {id: $session_id})-[:EXTRACTED_IN]-(e1:ExtractedEntity)
                MATCH (e1)-[r:REL]->(e2:ExtractedEntity)
                WHERE r.extracted_from_session = $session_id
                RETURN e1.text AS head,
                       type(r) AS rel_type,
                       r.rel AS relation,
                       e2.text AS tail,
                       r.confidence AS confidence,
                       r.context AS context
                ORDER BY r.confidence DESC
                LIMIT $limit
            """, {"session_id": session_id, "limit": limit})
=======
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
>>>>>>> dev-vera-ollama-fixed
            
            relationships = []
            for record in result:
                relationships.append({
                    "head": record["head"],
<<<<<<< HEAD
                    "relation": record.get("relation") or record["rel_type"],
                    "tail": record["tail"],
                    "confidence": record.get("confidence", 0.0),
                    "context": record.get("context", "")[:200]
=======
                    "relation": record["relation"],
                    "tail": record["tail"],
                    "confidence": record.get("confidence", 0.0),
                    "context": record.get("context", "")
>>>>>>> dev-vera-ollama-fixed
                })
            
            return {
                "session_id": session_id,
                "relationships": relationships,
                "total": len(relationships)
            }
            
    except Exception as e:
        logger.error(f"Error listing relationships: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


<<<<<<< HEAD
@router.post("/{session_id}/promote")
async def promote_memory(session_id: str, memory_id: str, entity_anchor: Optional[str] = None):
    """
    Promote a session memory item to long-term storage.
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    try:
        # Get the memory item
        memories = vera.mem.get_session_memory(session_id)
        memory = next((m for m in memories if m.id == memory_id), None)
        
        if not memory:
            raise HTTPException(status_code=404, detail="Memory item not found")
        
        # Promote to long-term
        vera.mem.promote_session_memory_to_long_term(memory, entity_anchor)
        
        return {
            "status": "promoted",
            "memory_id": memory_id,
            "session_id": session_id,
            "entity_anchor": entity_anchor
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Memory promotion error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
=======
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
>>>>>>> dev-vera-ollama-fixed
