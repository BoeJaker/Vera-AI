import logging
import numpy as np
from fastapi import APIRouter, FastAPI, HTTPException
from typing import List

# ============================================================
# Application imports — adjust to your structure
# ============================================================
from Vera.ChatUI.api.session import vera_instances, sessions, toolchain_executions, active_toolchains, websocket_connections, get_or_create_vera
from Vera.ChatUI.api.schemas import VectorStoreRequest  # if defined elsewhere

# ============================================================
# Logging setup
# ============================================================
logger = logging.getLogger(__name__)


# ============================================================
# Router setup
# ============================================================
router = APIRouter(prefix="/api/vectorstore", tags=["vectorstore"])

# ============================================================
# Vector Store Endpoints
# ============================================================
@router.get("/{session_id}/stats")
async def get_vectorstore_stats(session_id: str):
    """Get statistics about the vector store for a session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    try:
        index = vera.mem.vector_store.index
        total_vectors = index.ntotal if hasattr(index, 'ntotal') else 0
        dimension = index.d if hasattr(index, 'd') else 0
        
        return {
            "session_id": session_id,
            "total_vectors": total_vectors,
            "dimension": dimension
        }
        
    except Exception as e:
        logger.error(f"Vector store stats error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{session_id}/get_similar")
async def get_similar_vectors(session_id: str, request: VectorStoreRequest):
    """Get similar vectors from the vector store."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    try:
        index = vera.mem.vector_store.index
        query_vector = request.vector
        top_k = request.top_k
        
        if not hasattr(index, 'search'):
            raise HTTPException(status_code=500, detail="Vector store does not support search")
        
        D, I = index.search(np.array([query_vector], dtype='float32'), top_k)
        
        results = []
        for dist, idx in zip(D[0], I[0]):
            if idx == -1:
                continue
            results.append({
                "index": int(idx),
                "distance": float(dist)
            })
        
        return {
            "session_id": session_id,
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Vector store search error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{session_id}/get_collection")
async def get_vectorstore_collection(session_id: str):
    """Get vector store collection details."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    
    try:
        collection = vera.mem.vector_store.collection
        
        return {
            "session_id": session_id,
            "collection_name": collection.name if hasattr(collection, 'name') else "default",
            "metadata": collection.metadata if hasattr(collection, 'metadata') else {}
        }
        
    except Exception as e:
        logger.error(f"Vector store collection error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
