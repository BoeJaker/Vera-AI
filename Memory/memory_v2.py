#!/usr/bin/env python3
""" 
Hybrid Memory System: Two-tier memory architecture with Neo4j graphs and Chroma vectors.

This module provides a hybrid memory system combining:
- Long-term knowledge: Neo4j graph database for structured relationships
- Semantic storage: Chroma vector database for unstructured content
- Session management: Temporary working memory with promotion capabilities
- Archive: JSONL logging for audit trails and training data

Dependencies:
    pip install neo4j chromadb pydantic langchain-community

Environment variables:
    NEO4J_URI: Neo4j connection URI (default: bolt://localhost:7687)
    NEO4J_USER: Neo4j username (default: neo4j)
    NEO4J_PASSWORD: Neo4j password (required)

    Generic Node Metadata:
        - id: Unique identifier
        - timestamp: Creation or modification time *not implemented*
        - vector: Embedding vector for semantic search *not implemented*
        - vector_id: ID in vector DB *not implemented*
        - author: Creator of the node *not implemented*
        - type: Entity type (e.g., person, project, system)
        - labels: List of labels for categorization
        - properties: Arbitrary key-value metadata

    Level 1 - Core Entities:
        - Entity: Generic entity with id, type, labels, properties
        - Session: Memory session with id, timestamps, metadata
        - Memory: Memory item with id, text, metadata, tier (session|long_term
        - Corpus: Text corpus with id, text, metadata

    Level 2 - Specialized Entities:
        - File: File entity with path, name, size, modified timestamp
        - Project: Project entity with status, priority, description
        - System: System entity with version, type, description

    Relationships:
        - RELATES: Generic relationship with type and properties
        - HAS_MEMORY: Session to Memory relationship
        - FOCUSES_ON: Session to Entity relationship
        - USES: Entity to Entity relationship
        - CONTAINS: File to Memory relationship
        - PART_OF: Entity to Project relationship
        - MANAGES: Project to System relationship
"""

import json
import logging
import os
import time
import uuid
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import chromadb
from chromadb.utils import embedding_functions
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import OllamaEmbeddings
from neo4j import GraphDatabase, Driver
from pydantic import BaseModel, Field, validator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -----------------------------
# Data Models
# -----------------------------

class Node(BaseModel):
    """Represents a graph node with ID, type, labels, and properties."""
    id: str
    type: str
    labels: List[str] = Field(default_factory=list)
    properties: Dict[str, Any] = Field(default_factory=dict)

    @validator('id')
    def validate_id(cls, v):
        if not v or not v.strip():
            raise ValueError("Node ID cannot be empty")
        return v.strip()

class Edge(BaseModel):
    """Represents a graph relationship between two nodes."""
    src: str
    dst: str
    rel: str
    properties: Dict[str, Any] = Field(default_factory=dict)

    @validator('src', 'dst', 'rel')
    def validate_non_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Edge fields cannot be empty")
        return v.strip()

class MemoryItem(BaseModel):
    """Represents a memory item with metadata and tier information."""
    id: str
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    tier: str = Field(default="session", description="session|long_term")
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class Session(BaseModel):
    """Represents a memory session with lifecycle tracking."""
    id: str
    started_at: str
    ended_at: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

# -----------------------------
# Graph Database Client
# -----------------------------

class GraphClient:
    """Neo4j graph database client with connection management and queries."""
    
    def __init__(self, uri: str, user: str, password: str):
        """Initialize Neo4j connection and create constraints."""
        self.uri = uri
        self.user = user
        self._driver: Optional[Driver] = None
        self._connect(password)
        self._ensure_constraints()

    def _connect(self, password: str) -> None:
        """Establish Neo4j connection with retry logic."""
        try:
            self._driver = GraphDatabase.driver(self.uri, auth=(self.user, password))
            # Test connection
            with self._driver.session() as session:
                session.run("RETURN 1")
            logger.info(f"Connected to Neo4j at {self.uri}")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    def _ensure_constraints(self) -> None:
        """Create database constraints and indexes."""
        constraints = [
            "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS FOR (n:Entity) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT session_id_unique IF NOT EXISTS FOR (s:Session) REQUIRE s.id IS UNIQUE",
            "CREATE INDEX entity_type_index IF NOT EXISTS FOR (n:Entity) ON (n.type)",
            "CREATE INDEX session_started_index IF NOT EXISTS FOR (s:Session) ON (s.started_at)",
        ]
        
        with self._driver.session() as session:
            for constraint in constraints:
                try:
                    session.run(constraint)
                except Exception as e:
                    logger.warning(f"Constraint creation warning: {e}")

    def close(self) -> None:
        """Close database connection."""
        if self._driver:
            self._driver.close()
            logger.info("Neo4j connection closed")

    def upsert_entity(self, node: Node) -> None:
        """Create or update an entity node."""
        labels_str = ":".join(["Entity"] + node.labels)
        cypher = f"""
        MERGE (n:{labels_str} {{id: $id}})
        SET n.type = $type,
            n.updated_at = datetime(),
            n += $properties
        RETURN n
        """
        
        with self._driver.session() as session:
            try:
                session.run(cypher, {
                    "id": node.id,
                    "type": node.type,
                    "properties": node.properties,
                })
                logger.debug(f"Upserted entity: {node.id}")
            except Exception as e:
                logger.error(f"Failed to upsert entity {node.id}: {e}")
                raise

    def upsert_session(self, session_obj: Session) -> None:
        """Create or update a session node."""
        cypher = """
        MERGE (s:Session {id: $id})
        ON CREATE SET 
            s.started_at = $started_at, 
            s.metadata = $metadata,
            s.created_at = datetime()
        ON MATCH SET 
            s.metadata = coalesce(s.metadata, {}) + $metadata,
            s.updated_at = datetime()
        RETURN s
        """
        
        with self._driver.session() as session:
            try:
                session.run(cypher, {
                    "id": session_obj.id,
                    "started_at": session_obj.started_at,
                    "metadata": session_obj.metadata or {}
                })
                logger.debug(f"Upserted session: {session_obj.id}")
            except Exception as e:
                logger.error(f"Failed to upsert session {session_obj.id}: {e}")
                raise

    def end_session(self, session_id: str) -> None:
        """Mark a session as ended."""
        cypher = """
        MATCH (s:Session {id: $id})
        SET s.ended_at = $ended_at, s.updated_at = datetime()
        RETURN s.ended_at
        """
        
        with self._driver.session() as session:
            try:
                result = session.run(cypher, {
                    "id": session_id, 
                    "ended_at": datetime.utcnow().isoformat()
                })
                if result.single():
                    logger.info(f"Ended session: {session_id}")
                else:
                    logger.warning(f"Session not found: {session_id}")
            except Exception as e:
                logger.error(f"Failed to end session {session_id}: {e}")
                raise

    def upsert_edge(self, edge: Edge) -> None:
        """Create or update a relationship between entities."""
        cypher = """
        MATCH (a:Entity {id: $src})
        MATCH (b:Entity {id: $dst})
        MERGE (a)-[r:RELATES {type: $rel}]->(b)
        SET r += $properties, r.updated_at = datetime()
        RETURN r
        """
        
        with self._driver.session() as session:
            try:
                result = session.run(cypher, edge.model_dump())
                if not result.single():
                    logger.warning(f"One or both entities not found for edge: {edge.src} -> {edge.dst}")
                else:
                    logger.debug(f"Upserted edge: {edge.src} -{edge.rel}-> {edge.dst}")
            except Exception as e:
                logger.error(f"Failed to upsert edge: {e}")
                raise

    def link_session_to_entity(self, session_id: str, entity_id: str, rel: str = "FOCUSES_ON") -> None:
        """Link a session to an entity."""
        cypher = """
        MATCH (s:Session {id: $sid})
        MATCH (e:Entity {id: $eid})
        MERGE (s)-[r:RELATES {type: $rel}]->(e)
        SET r.created_at = coalesce(r.created_at, datetime())
        RETURN r
        """
        
        with self._driver.session() as session:
            try:
                session.run(cypher, {"sid": session_id, "eid": entity_id, "rel": rel})
                logger.debug(f"Linked session {session_id} to entity {entity_id}")
            except Exception as e:
                logger.error(f"Failed to link session to entity: {e}")
                raise

    def get_subgraph(self, seed_ids: List[str], depth: int = 2) -> Dict[str, Any]:
        """Extract a subgraph starting from seed entities."""
        if not seed_ids:
            return {"nodes": [], "rels": []}

        cypher = f"""
        MATCH (n:Entity)
        WHERE n.id IN $seed_ids
        OPTIONAL MATCH path = (n)-[*1..{depth}]-(m:Entity)
        WITH collect(DISTINCT n) + collect(DISTINCT m) AS all_nodes
        UNWIND all_nodes AS node
        WITH collect(DISTINCT node) AS nodes
        MATCH (a)-[r:RELATES]-(b)
        WHERE a IN nodes AND b IN nodes
        RETURN 
            [n IN nodes | {{
                id: n.id, 
                type: n.type, 
                labels: labels(n), 
                properties: properties(n)
            }}] AS nodes,
            collect(DISTINCT {{
                src: startNode(r).id,
                dst: endNode(r).id,
                type: r.type,
                properties: properties(r)
            }}) AS rels
        """
        
        with self._driver.session() as session:
            try:
                result = session.run(cypher, {"seed_ids": seed_ids}).single()
                if result:
                    return {"nodes": result["nodes"] or [], "rels": result["rels"] or []}
                return {"nodes": [], "rels": []}
            except Exception as e:
                logger.error(f"Failed to extract subgraph: {e}")
                return {"nodes": [], "rels": []}

    def list_entities(self, entity_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all entities, optionally filtered by type."""
        where_clause = "WHERE e.type = $entity_type" if entity_type else ""
        cypher = f"""
        MATCH (e:Entity)
        {where_clause}
        RETURN e.id AS id, e.type AS type, labels(e) AS labels
        ORDER BY e.id
        """
        
        params = {"entity_type": entity_type} if entity_type else {}
        
        with self._driver.session() as session:
            try:
                results = session.run(cypher, params)
                return [dict(record) for record in results]
            except Exception as e:
                logger.error(f"Failed to list entities: {e}")
                return []

    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all sessions."""
        cypher = """
        MATCH (s:Session)
        RETURN s.id AS id, s.started_at AS started_at, s.ended_at AS ended_at
        ORDER BY s.started_at DESC
        """
        
        with self._driver.session() as session:
            try:
                results = session.run(cypher)
                return [dict(record) for record in results]
            except Exception as e:
                logger.error(f"Failed to list sessions: {e}")
                return []

# -----------------------------
# Vector Database Client
# -----------------------------

class VectorClient:
    """Chroma vector database client for semantic storage and retrieval."""
    
    def __init__(self, persist_dir: str, embedding_model: str = "all-MiniLM-L6-v2"):
        """Initialize Chroma client with persistent storage."""
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            self._client = chromadb.PersistentClient(path=str(self.persist_dir))
            self._ef = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=embedding_model
            )
            logger.info(f"Vector client initialized at {persist_dir}")
        except Exception as e:
            logger.error(f"Failed to initialize vector client: {e}")
            raise

    def get_collection(self, name: str):
        """Get or create a collection."""
        try:
            return self._client.get_or_create_collection(name=name, embedding_function=self._ef)
        except Exception as e:
            logger.error(f"Failed to get collection {name}: {e}")
            raise

    def add_texts(self, collection: str, ids: List[str], texts: List[str], 
                  metadatas: Optional[List[Dict[str, Any]]] = None) -> None:
        """Add texts to a collection."""
        if not ids or not texts or len(ids) != len(texts):
            raise ValueError("IDs and texts must be non-empty and same length")
            
        try:
            col = self.get_collection(collection)
            col.add(ids=ids, documents=texts, metadatas=metadatas)
            logger.debug(f"Added {len(texts)} texts to collection '{collection}'")
        except Exception as e:
            logger.error(f"Failed to add texts to {collection}: {e}")
            raise

    def query(self, collection: str, text: str, n_results: int = 5, 
              where: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Query a collection for similar texts."""
        try:
            col = self.get_collection(collection)
            kwargs = {"query_texts": [text], "n_results": n_results}
            if where:
                kwargs["where"] = where
            
            result = col.query(**kwargs)
            
            # Format results
            hits = []
            if result and result.get("ids") and result["ids"][0]:
                for i, doc_id in enumerate(result["ids"][0]):
                    hit = {
                        "id": doc_id,
                        "text": result["documents"][0][i],
                        "metadata": result["metadatas"][0][i] if result.get("metadatas") else {},
                    }
                    if result.get("distances"):
                        hit["distance"] = result["distances"][0][i]
                    hits.append(hit)
            
            return hits
        except Exception as e:
            logger.error(f"Failed to query collection {collection}: {e}")
            return []

    def delete(self, collection: str, ids: List[str]) -> None:
        """Delete documents from a collection."""
        try:
            col = self.get_collection(collection)
            col.delete(ids=ids)
            logger.debug(f"Deleted {len(ids)} documents from {collection}")
        except Exception as e:
            logger.error(f"Failed to delete from {collection}: {e}")
            raise

    def list_collections(self) -> List[str]:
        """List all collection names."""
        try:
            collections = self._client.list_collections()
            return [col.name for col in collections]
        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
            return []

# -----------------------------
# Archive System
# -----------------------------

class Archive:
    """JSONL-based archive for logging and audit trails."""
    
    def __init__(self, jsonl_path: Optional[str] = None):
        """Initialize archive with optional JSONL file."""
        self.path = Path(jsonl_path) if jsonl_path else None
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            logger.info(f"Archive initialized at {self.path}")

    def write(self, record: Dict[str, Any]) -> None:
        """Write a record to the archive."""
        if not self.path:
            return
            
        try:
            record = {"timestamp": datetime.utcnow().isoformat(), **record}
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        except Exception as e:
            logger.error(f"Failed to write to archive: {e}")

    def read_recent(self, n: int = 100) -> List[Dict[str, Any]]:
        """Read the most recent n records."""
        if not self.path or not self.path.exists():
            return []
            
        try:
            records = []
            with open(self.path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        records.append(json.loads(line.strip()))
            return records[-n:] if len(records) > n else records
        except Exception as e:
            logger.error(f"Failed to read archive: {e}")
            return []

# -----------------------------
# Main Hybrid Memory System
# -----------------------------

class HybridMemory:
    """
    Hybrid memory system combining graph and vector storage with session management.
    
    Features:
    - Long-term knowledge in Neo4j graph database
    - Semantic search with Chroma vector store
    - Session-based working memory
    - File storage and chunking
    - Audit logging with JSONL archive
    """

    def __init__(
        self,
        neo4j_uri: str,
        neo4j_user: str,
        neo4j_password: str,
        chroma_dir: str,
        archive_jsonl: Optional[str] = None,
        embedding_model: str = "mistral:7b",
    ):
        """Initialize the hybrid memory system."""
        self.graph = GraphClient(neo4j_uri, neo4j_user, neo4j_password)
        self.vec = VectorClient(chroma_dir)
        self.archive = Archive(archive_jsonl)
        self.embedding_model = embedding_model
        self._current_session: Optional[Session] = None
        
        logger.info("Hybrid memory system initialized")

    def close(self) -> None:
        """Clean up resources."""
        if self._current_session and not self._current_session.ended_at:
            self.end_session(self._current_session.id)
        self.graph.close()

    # -------- Session Management --------

    def start_session(self, session_id: Optional[str] = None, 
                     metadata: Optional[Dict[str, Any]] = None) -> Session:
        """Start a new memory session."""
        if not session_id:
            session_id = f"sess_{int(time.time() * 1000)}"
            
        session = Session(
            id=session_id,
            started_at=datetime.utcnow().isoformat(),
            metadata=metadata or {}
        )
        
        self.graph.upsert_session(session)
        self._current_session = session
        self.archive.write({"type": "session_start", "session": session.model_dump()})
        
        logger.info(f"Started session: {session_id}")
        return session

    def end_session(self, session_id: str) -> None:
        """End a memory session."""
        self.graph.end_session(session_id)
        if self._current_session and self._current_session.id == session_id:
            self._current_session.ended_at = datetime.utcnow().isoformat()
            self._current_session = None
        
        self.archive.write({"type": "session_end", "session_id": session_id})
        logger.info(f"Ended session: {session_id}")

    def get_current_session(self) -> Optional[Session]:
        """Get the current active session."""
        return self._current_session

    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all sessions."""
        return self.graph.list_sessions()

    # -------- Memory Operations --------

    def add_memory(self, text: str, memory_type: str = "thought", 
                  session_id: Optional[str] = None,
                  metadata: Optional[Dict[str, Any]] = None,
                  promote_to_longterm: bool = False) -> MemoryItem:
        """Add a memory item to session or long-term storage."""
        if not text.strip():
            raise ValueError("Memory text cannot be empty")
            
        # Use current session if none specified
        if not session_id and self._current_session:
            session_id = self._current_session.id
        elif not session_id:
            raise ValueError("No session specified and no current session active")

        memory_id = f"mem_{uuid.uuid4().hex[:8]}"
        memory = MemoryItem(
            id=memory_id,
            text=text,
            metadata=metadata or {},
            tier="long_term" if promote_to_longterm else "session"
        )

        # Store in vector database
        collection = "long_term_memories" if promote_to_longterm else f"session_{session_id}"
        self.vec.add_texts(collection, [memory.id], [memory.text], [memory.metadata])

        # Store in graph
        node = Node(
            id=memory.id,
            type=memory_type,
            labels=[memory_type.title(), "Memory"],
            properties={"text": memory.text, "tier": memory.tier, **memory.metadata}
        )
        self.graph.upsert_entity(node)

        # Link to session
        if not promote_to_longterm:
            self.graph.link_session_to_entity(session_id, memory.id, "HAS_MEMORY")

        self.archive.write({
            "type": "memory_add",
            "memory": memory.model_dump(),
            "session_id": session_id
        })

        logger.info(f"Added memory: {memory_id} ({'long-term' if promote_to_longterm else 'session'})")
        return memory

    def search_memories(self, query: str, session_id: Optional[str] = None,
                       long_term: bool = True, n_results: int = 5) -> List[Dict[str, Any]]:
        """Search memories using semantic similarity."""
        results = []
        
        # Search long-term memories
        if long_term:
            lt_results = self.vec.query("long_term_memories", query, n_results)
            for result in lt_results:
                result["source"] = "long_term"
            results.extend(lt_results)
        
        # Search session memories
        if session_id:
            session_results = self.vec.query(f"session_{session_id}", query, n_results)
            for result in session_results:
                result["source"] = "session"
            results.extend(session_results)
        
        # Sort by relevance (distance)
        results.sort(key=lambda x: x.get("distance", float("inf")))
        
        self.archive.write({
            "type": "memory_search",
            "query": query,
            "session_id": session_id,
            "results_count": len(results)
        })
        
        return results[:n_results]

    def promote_memory(self, memory_id: str, anchor_entity: Optional[str] = None) -> None:
        """Promote a session memory to long-term storage."""
        # This would require more complex logic to move between collections
        # For now, we'll create a new long-term memory
        logger.info(f"Memory promotion not fully implemented: {memory_id}")

    # -------- Entity Management --------

    def create_entity(self, entity_id: str, entity_type: str,
                     labels: Optional[List[str]] = None,
                     properties: Optional[Dict[str, Any]] = None) -> Node:
        """Create or update an entity in the knowledge graph."""
        node = Node(
            id=entity_id,
            type=entity_type,
            labels=labels or [],
            properties=properties or {}
        )
        
        self.graph.upsert_entity(node)
        self.archive.write({"type": "entity_create", "entity": node.model_dump()})
        
        logger.info(f"Created entity: {entity_id} ({entity_type})")
        return node

    def link_entities(self, src_id: str, dst_id: str, relationship: str,
                     properties: Optional[Dict[str, Any]] = None) -> None:
        """Create a relationship between two entities."""
        edge = Edge(src=src_id, dst=dst_id, rel=relationship, properties=properties or {})
        self.graph.upsert_edge(edge)
        self.archive.write({"type": "entity_link", "edge": edge.model_dump()})
        
        logger.info(f"Linked entities: {src_id} -{relationship}-> {dst_id}")

    def get_subgraph(self, seed_entities: List[str], depth: int = 2) -> Dict[str, Any]:
        """Extract a subgraph around seed entities."""
        subgraph = self.graph.get_subgraph(seed_entities, depth)
        self.archive.write({
            "type": "subgraph_extract",
            "seeds": seed_entities,
            "depth": depth,
            "node_count": len(subgraph.get("nodes", [])),
            "edge_count": len(subgraph.get("rels", []))
        })
        return subgraph

    def list_entities(self, entity_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """List entities, optionally filtered by type."""
        return self.graph.list_entities(entity_type)

    # -------- File Management --------

    def store_file(self, file_path: Union[str, Path], chunk_size: int = 1000,
                  chunk_overlap: int = 100) -> str:
        """Store a file in the memory system with chunking for semantic search."""
        file_path = Path(file_path)
        if not file_path.is_file():
            raise FileNotFoundError(f"File not found: {file_path}")

        file_id = f"file_{abs(hash(str(file_path))) % 1000000}"
        
        # Create file entity
        file_node = Node(
            id=file_id,
            type="file",
            labels=["File"],
            properties={
                "name": file_path.name,
                "path": str(file_path),
                "size": file_path.stat().st_size,
                "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
            }
        )
        self.graph.upsert_entity(file_node)

        # Read and chunk file content
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            raise

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        chunks = splitter.split_text(content)

        # Store chunks in vector database
        chunk_ids = [f"{file_id}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [{"file_id": file_id, "chunk_index": i} for i in range(len(chunks))]
        
        self.vec.add_texts("file_chunks", chunk_ids, chunks, metadatas)
        
        self.archive.write({
            "type": "file_store",
            "file_id": file_id,
            "path": str(file_path),
            "chunks": len(chunks)
        })
        
        logger.info(f"Stored file: {file_path.name} ({len(chunks)} chunks)")
        return file_id

    def search_files(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """Search file content using semantic similarity."""
        results = self.vec.query("file_chunks", query, n_results)
        
        self.archive.write({
            "type": "file_search",
            "query": query,
            "results_count": len(results)
        })
        
        return results

    # -------- System Status --------

    def get_stats(self) -> Dict[str, Any]:
        """Get system statistics."""
        try:
            entities = self.list_entities()
            sessions = self.list_sessions()
            collections = self.vec.list_collections()
            
            stats = {
                "entities": len(entities),
                "entity_types": len(set(e.get("type") for e in entities)),
                "sessions": len(sessions),
                "active_sessions": len([s for s in sessions if not s.get("ended_at")]),
                "collections": len(collections),
                "collection_names": collections
            }
            
            return stats
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}

# -----------------------------
# Example Usage and Testing
# -----------------------------

def main():
    """Example usage of the hybrid memory system."""
    # Configuration
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "testpassword")
    CHROMA_DIR = "./memory/chroma_store"
    ARCHIVE_PATH = "./memory/archive/memory.jsonl"

    # Initialize system
    memory = HybridMemory(
        neo4j_uri=NEO4J_URI,
        neo4j_user=NEO4J_USER,
        neo4j_password=NEO4J_PASSWORD,
        chroma_dir=CHROMA_DIR,
        archive_jsonl=ARCHIVE_PATH,
    )

    try:
        # Create some entities
        memory.create_entity("project_alpha", "project", 
                           labels=["Project"], 
                           properties={"status": "active", "priority": "high"})
        
        memory.create_entity("ai_system", "system",
                           labels=["System", "AI"],
                           properties={"version": "1.0", "type": "llm"})
        
        # Link entities
        memory.link_entities("project_alpha", "ai_system", "USES")
        
        # Start a session
        session = memory.start_session(metadata={"user": "developer", "task": "debugging"})
        print(f"Started session: {session.id}")
        
        # Add memories to session
        memory.add_memory("Investigating performance bottleneck in AI system", 
                         "observation", session.id)
        memory.add_memory("Found memory leak in vector processing", 
                         "finding", session.id)
        memory.add_memory("Applied fix using better garbage collection", 
                         "solution", session.id, promote_to_longterm=True)
        
        # Search memories
        results = memory.search_memories("performance issue", session.id)
        print(f"Found {len(results)} relevant memories")
        
        # Get subgraph
        subgraph = memory.get_subgraph(["project_alpha"])
        print(f"Subgraph: {len(subgraph['nodes'])} nodes, {len(subgraph['rels'])} relationships")
        
        # System stats
        stats = memory.get_stats()
        print(f"System stats: {stats}")
        
        # End session
        memory.end_session(session.id)
        
    except Exception as e:
        logger.error(f"Example execution failed: {e}")
    finally:
        memory.close()

if __name__ == "__main__":
    main()


# -----------------------------
# Docker Setup Commands
# -----------------------------
"""
To run Neo4j with Docker:

docker run \
  --name neo4j \
  -p7474:7474 -p7687:7687 \
  -d \
  -e NEO4J_AUTH=neo4j/testpassword \
  -e NEO4J_PLUGINS=["apoc"] \
  neo4j:5.22

docker start neo4j

Access Neo4j browser at: http://localhost:7474
Username: neo4j
Password: testpassword
"""