from fastapi import APIRouter, HTTPException
from typing import Optional
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
    
    Retrieval types:
    - vector: Semantic search using embeddings
    - graph: Graph traversal from relevant nodes
    - hybrid: Combined vector + graph retrieval
    """
    if request.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(request.session_id)
    
    try:
        results = []
        
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
            
        else:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid retrieval_type: {request.retrieval_type}"
            )
        
        return MemoryQueryResponse(
            results=results,
            retrieval_type=request.retrieval_type,
            query=request.query,
            session_id=request.session_id
        )
        
    except Exception as e:
        logger.error(f"Memory query error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/hybrid-retrieve")
async def hybrid_retrieve(request: HybridRetrievalRequest):
    """
    Advanced hybrid retrieval combining vector search and graph traversal.
    Returns both semantic matches and related entities from the knowledge graph.
    """
    if request.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(request.session_id)
    
    try:
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
        seed_entity_ids = set()
        
        for hit in session_hits + long_term_hits:
            metadata = hit.get("metadata", {})
            
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
        return {
            "session_id": request.session_id,
            "query": request.query,
            "vector_results": {
                "session": session_hits,
                "long_term": long_term_hits,
                "total": len(session_hits) + len(long_term_hits)
            },
            "graph_context": graph_context,
            "seed_entities": list(seed_entity_ids),
            "retrieval_stats": {
                "k_vector": request.k_vector,
                "k_graph": request.k_graph,
                "graph_depth": request.graph_depth,
                "entities_found": len(seed_entity_ids)
            }
        }
        
    except Exception as e:
        logger.error(f"Hybrid retrieval error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


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


@router.post("/subgraph")
async def get_memory_subgraph(request: SubgraphRequest):
    """
    Extract a subgraph around specific entity IDs.
    Useful for exploring knowledge graph neighborhoods.
    """
    if request.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(request.session_id)
    
    try:
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
async def list_session_entities(session_id: str, limit: int = 50):
    """
    List all entities extracted in a session.
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    try:
        with vera.mem.graph._driver.session() as db_sess:
            result = db_sess.run("""
                MATCH (s:Session {id: $session_id})-[:EXTRACTED_IN]-(e:ExtractedEntity)
                RETURN e.id AS id, 
                       e.text AS text, 
                       e.type AS type,
                       labels(e) AS labels,
                       e.confidence AS confidence,
                       e.original_text AS original_text
                ORDER BY e.confidence DESC
                LIMIT $limit
            """, {"session_id": session_id, "limit": limit})
            
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
async def list_session_relationships(session_id: str, limit: int = 50):
    """
    List all relationships extracted in a session.
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    try:
        with vera.mem.graph._driver.session() as db_sess:
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
            
            relationships = []
            for record in result:
                relationships.append({
                    "head": record["head"],
                    "relation": record.get("relation") or record["rel_type"],
                    "tail": record["tail"],
                    "confidence": record.get("confidence", 0.0),
                    "context": record.get("context", "")[:200]
                })
            
            return {
                "session_id": session_id,
                "relationships": relationships,
                "total": len(relationships)
            }
            
    except Exception as e:
        logger.error(f"Error listing relationships: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


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
