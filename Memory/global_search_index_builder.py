#!/usr/bin/env python3
"""
Build Global Search Index for Session History

This script creates a global ChromaDB collection containing all memories
from all sessions, enabling fast cross-session search.

Run this once to build the index, then run periodically to update it.
"""

import logging
from datetime import datetime
from Vera.vera import Vera
import Vera.Memory.memory as memory
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def build_global_search_index():
    """Build or update the global search index."""
    
    logger.info("Initializing Vera instance...")
    vera = Vera()
    vector_client = memory.VectorClient(vera.chroma_path)
    if not hasattr(vera, 'mem'):
        logger.error("Vera memory system not available")
        return
    
    # Collection name for global search
    global_collection_name = "global_memory_search"
    
    logger.info(f"Building global collection: {global_collection_name}")
    
    # Get or create the global collection
    try:
        collection = vector_client.get_collection(global_collection_name)
        logger.info(f"Found existing collection with {collection.count()} items")
        
        # Option: Clear and rebuild
        # vera.mem.client.delete_collection(global_collection_name)
        # collection = vera.mem.client.create_collection(global_collection_name)
        # logger.info("Cleared existing collection for rebuild")
        
    except Exception as e:
        logger.info(f"Creating new collection: {e}")
        collection = vector_client.create_collection(global_collection_name)
    
    # Get all sessions from Neo4j
    logger.info("Fetching all sessions from Neo4j...")
    
    with vera.mem.graph._driver.session() as neo_sess:
        result = neo_sess.run("""
            MATCH (s:Session)
            OPTIONAL MATCH (m)
            WHERE m.session_id = s.id
            WITH s, count(DISTINCT m) as msg_count
            WHERE msg_count > 0
            RETURN s.id as session_id, msg_count
            ORDER BY s.id
        """)
        
        all_sessions = [dict(record) for record in result]
    
    logger.info(f"Found {len(all_sessions)} sessions to index")
    
    # Process each session
    total_memories = 0
    batch_size = 100
    
    documents_batch = []
    metadatas_batch = []
    ids_batch = []
    
    for idx, session_info in enumerate(all_sessions):
        session_id = session_info['session_id']
        
        try:
            # Get the session-specific collection
            session_collection_name = f"session_{session_id}"
            
            try:
                session_collection = vera.mem.client.get_collection(session_collection_name)
            except:
                logger.debug(f"Session collection not found: {session_collection_name}")
                continue
            
            # Get all documents from this session
            session_data = session_collection.get(
                include=['documents', 'metadatas', 'embeddings']
            )
            
            if not session_data or not session_data.get('ids'):
                continue
            
            # Add to global collection batch
            for i, doc_id in enumerate(session_data['ids']):
                # Create unique global ID
                global_id = f"{session_id}_{doc_id}"
                
                # Get metadata and add session_id
                metadata = session_data['metadatas'][i] if session_data.get('metadatas') else {}
                metadata['session_id'] = session_id
                
                documents_batch.append(session_data['documents'][i])
                metadatas_batch.append(metadata)
                ids_batch.append(global_id)
                
                # Add batch when it reaches batch_size
                if len(documents_batch) >= batch_size:
                    collection.add(
                        documents=documents_batch,
                        metadatas=metadatas_batch,
                        ids=ids_batch
                    )
                    total_memories += len(documents_batch)
                    
                    documents_batch = []
                    metadatas_batch = []
                    ids_batch = []
            
            if (idx + 1) % 100 == 0:
                logger.info(f"Processed {idx + 1}/{len(all_sessions)} sessions, indexed {total_memories} memories")
        
        except Exception as e:
            logger.error(f"Error processing session {session_id}: {e}")
            continue
    
    # Add remaining batch
    if documents_batch:
        collection.add(
            documents=documents_batch,
            metadatas=metadatas_batch,
            ids=ids_batch
        )
        total_memories += len(documents_batch)
    
    logger.info(f"✅ Global index built successfully!")
    logger.info(f"   Total sessions indexed: {len(all_sessions)}")
    logger.info(f"   Total memories indexed: {total_memories}")
    logger.info(f"   Collection size: {collection.count()}")
    
    # Test the index
    logger.info("\nTesting search functionality...")
    test_results = collection.query(
        query_texts=["test query"],
        n_results=5
    )
    logger.info(f"Test search returned {len(test_results['ids'][0])} results")


if __name__ == "__main__":
    try:
        build_global_search_index()
    except KeyboardInterrupt:
        logger.info("\nBuild interrupted by user")
    except Exception as e:
        logger.error(f"Build failed: {e}", exc_info=True)