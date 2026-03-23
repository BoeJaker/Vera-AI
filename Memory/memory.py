#!/usr/bin/env python3
"""
Enhanced Hybrid Memory System with Dynamic NLP Extraction  [PATCHED]
Two-tier (Long-term graph + Short-term session) with unified vector store,
Neo4j graph database, and schema-less NLP entity/relationship extraction.

Patch summary vs original memory.py
-------------------------------------
1. VectorClient class REMOVED — replaced by HybridVectorStore (hybrid_vector_store.py)
   which provides:
     • Single unified "vera_memory" collection (no more per-session collections)
     • Embeddings written back to Neo4j nodes as properties (graph+vector bridge)
     • Pluggable backend: "chroma" (default, zero-dependency change) or "weaviate"
     • Full backward-compat shim: get_collection(), session_ prefix routing all work

2. HybridMemory.__init__ gains four new optional kwargs (all have safe defaults):
     vector_backend, weaviate_url, weaviate_api_key, weaviate_class,
     write_embeddings_to_graph
   Existing callers that pass nothing new continue to work identically.

3. add_session_memory: two extra metadata keys written per item:
     "session_id" → enables unified-collection session filtering
     "node_id"    → enables query_near_node() in HybridVectorStore

4. VectorClient alias exported at module level for any import that used it.

Everything else is identical to the original.

New Dependencies (install via pip):
    pip install neo4j chromadb pydantic spacy sentence-transformers sklearn
    python -m spacy download en_core_web_sm
    # optional Weaviate support:
    pip install weaviate-client>=4.0
"""
from __future__ import annotations

import json
import os
import time
import hashlib
import inspect
import sys
import re
import threading
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Set
from collections import defaultdict

from neo4j import GraphDatabase, Driver
import chromadb
from chromadb.utils import embedding_functions
from pydantic import BaseModel, Field

# NLP dependencies
import spacy
from sentence_transformers import SentenceTransformer
from sklearn.cluster import DBSCAN
import numpy as np

# Langchain for text splitting and embeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import OllamaEmbeddings

try:
    from Vera.Memory.nlp import NLPExtractor
except ImportError:
    from Memory.nlp import NLPExtractor

# ── PATCH: import HybridVectorStore; VectorClient alias keeps old imports working
try:
    from Vera.Memory.hybrid_memory import HybridVectorStore, VectorClient
except ImportError:
    from Memory.hybrid_memory import HybridVectorStore, VectorClient

try:
    from Vera.Memory.entity_resolver import EntityResolver
    from Vera.Memory.relationship_builder import SemanticRelationshipExtractor
except ImportError:
    from Memory.entity_resolver import EntityResolver
    from Memory.relationship_builder import SemanticRelationshipExtractor
 
 

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


# =============================================================================
# Utilities
# =============================================================================

def sanitize_for_nlp(text: str) -> str:
    """Normalize unicode punctuation that breaks code parsers."""
    replacements = {
        '\u2013': '-',
        '\u2014': '--',
        '\u2018': "'",
        '\u2019': "'",
        '\u201c': '"',
        '\u201d': '"',
        '\u2026': '...',
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    return text


# =============================================================================
# Cluster-aware embedding function
# =============================================================================

class OllamaClusterEmbeddingFunction:
    """
    ChromaDB-compatible embedding function that routes ALL embedding requests
    through MultiInstanceOllamaManager — never localhost.
    """

    def __init__(self, ollama_manager, model: str = "nomic-embed-text:latest"):
        self.ollama_manager = ollama_manager
        self.model = model
        self._embeddings = None
        self._lock = threading.Lock()

    def _get_embeddings(self):
        if self._embeddings is None:
            with self._lock:
                if self._embeddings is None:
                    logger.info(
                        f"[OllamaClusterEmbeddingFunction] Initialising embeddings "
                        f"model '{self.model}' via ollama_manager"
                    )
                    self._embeddings = self.ollama_manager.create_embeddings(
                        model=self.model
                    )
        return self._embeddings

    def __call__(self, input: List[str]) -> List[List[float]]:
        embeddings = self._get_embeddings()
        try:
            result = embeddings.embed_documents(input)
            logger.debug(
                f"[OllamaClusterEmbeddingFunction] Embedded {len(input)} text(s) "
                f"→ {len(result[0])} dims each"
            )
            return result
        except Exception as e:
            logger.error(
                f"[OllamaClusterEmbeddingFunction] embed_documents failed "
                f"for {len(input)} text(s): {e}"
            )
            raise


# =============================================================================
# Data models
# =============================================================================

class Node(BaseModel):
    id: str
    type: str
    labels: List[str] = Field(default_factory=list)
    properties: Dict[str, Any] = Field(default_factory=dict)


class Edge(BaseModel):
    src: str
    dst: str
    rel: str
    properties: Dict[str, Any] = Field(default_factory=dict)


class MemoryItem(BaseModel):
    id: str
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    tier: str = Field(default="session", description="session|long_term")


class Session(BaseModel):
    id: str
    started_at: str
    ended_at: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExtractedEntity(BaseModel):
    """Dynamically extracted entity"""
    text: str
    label: str
    span: Tuple[int, int]
    confidence: float = 1.0
    embedding: Optional[List[float]] = None


class ExtractedRelation(BaseModel):
    """Dynamically extracted relationship"""
    head: str
    tail: str
    relation: str
    confidence: float = 1.0
    context: str = ""


# =============================================================================
# Graph (Neo4j) client
# =============================================================================

class GraphClient:
    def __init__(self, uri: str, user: str, password: str):
        self._driver: Driver = GraphDatabase.driver(uri, auth=(user, password))
        self._ensure_indexes()

    def close(self):
        self._driver.close()

    def _ensure_indexes(self):
        cypher_stmts = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Entity) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (s:Session) REQUIRE s.id IS UNIQUE",
            "CREATE INDEX IF NOT EXISTS FOR (n:Entity) ON (n.type)",
        ]
        with self._driver.session() as sess:
            for stmt in cypher_stmts:
                sess.run(stmt)

    def upsert_entity(self, node: Node):
        logger.debug(f"[GraphClient] Upserting entity: {node.id} of type {node.type}")
        if node.properties is None:
            node.properties = {}
        if "created_at" not in (node.properties or {}):
            node.properties["created_at"] = datetime.utcnow().isoformat()

        labels = ["Entity"] + [l for l in node.labels if l != "Entity"]
        labels_str = ":".join(labels)

        cypher = f"""
        MERGE (n:Entity {{id: $id}})
        SET n:{labels_str}
        SET n.type = $type,
            n += $properties
        RETURN n
        """

        with self._driver.session() as sess:
            try:
                result = sess.execute_write(
                    lambda tx: tx.run(cypher, {
                        "id": node.id,
                        "type": node.type,
                        "properties": node.properties,
                    }).single()
                )
                logger.debug(f"[GraphClient] Upsert result: {result}")
                return result
            except Exception as e:
                logger.error(f"[GraphClient] Upsert failed for {node.id}: {e}")
                raise

    def upsert_session(self, session: Session):
        logger.debug(f"[GraphClient] Upserting session: {session.id}")
        cypher = """
        MERGE (s:Session {id: $id})
        ON CREATE SET s.started_at = $started_at, s.metadata = $metadata
        ON MATCH SET s.metadata = coalesce(s.metadata, {}) + $metadata
        RETURN s
        """
        with self._driver.session() as sess:
            sess.run(cypher, {
                "id": session.id,
                "started_at": session.started_at,
                "metadata": session.metadata or {}
            })

    def end_session(self, session_id: str):
        cypher = """
        MATCH (s:Session {id: $id})
        SET s.ended_at = $ended_at
        RETURN s
        """
        with self._driver.session() as sess:
            sess.run(cypher, {"id": session_id, "ended_at": datetime.utcnow().isoformat()})

    def upsert_edge(self, edge: Edge):
        logger.debug(f"[GraphClient] Upserting edge: {edge.src} -[{edge.rel}]-> {edge.dst}")

        safe_props = {}
        for k, v in (edge.properties or {}).items():
            if isinstance(v, dict):
                safe_props[k] = json.dumps(v)
            elif isinstance(v, (str, int, float, bool, list)) or v is None:
                safe_props[k] = v
            else:
                safe_props[k] = str(v)

        cypher = """
        MATCH (a:Entity {id: $src})
        MATCH (b:Entity {id: $dst})
        MERGE (a)-[r:REL {rel: $rel}]->(b)
        SET r += $properties
        RETURN r
        """
        with self._driver.session() as sess:
            result = sess.execute_write(
                lambda tx: tx.run(cypher, {
                    "src": edge.src,
                    "dst": edge.dst,
                    "rel": edge.rel,
                    "properties": safe_props
                }).single()
            )
        logger.debug(f"[GraphClient] Edge upsert result: {result}")
        return result

    def link_session_to_entity(self, session_id: str, entity_id: str, rel: str = "FOCUSES_ON"):
        logger.debug(f"[GraphClient] Linking session {session_id} to entity {entity_id} with relation {rel}")
        cypher = """
        MATCH (s:Session {id: $sid})
        MATCH (e:Entity {id: $eid})
        MERGE (s)-[r:REL {rel: $rel}]->(e)
        RETURN r
        """
        with self._driver.session() as sess:
            sess.run(cypher, {"sid": session_id, "eid": entity_id, "rel": rel})

    def get_subgraph(self, seed_ids: List[str], depth: int = 2) -> Dict[str, Any]:
        cypher = f"""
        MATCH (n:Entity)
        WHERE n.id IN $seed_ids
        OPTIONAL MATCH (n)-[r*1..{depth}]-(m)
        RETURN collect(distinct n) AS nodes,
               collect(distinct r) AS rels,
               collect(distinct m) AS neighbors
        """
        with self._driver.session() as sess:
            rec = sess.run(cypher, {"seed_ids": seed_ids}).single()
            nodes = (rec["nodes"] or []) + (rec["neighbors"] or [])
            rels = rec["rels"] or []

            node_list = []
            for n in nodes:
                if n is None:
                    continue
                node_list.append({
                    "id": n.get("id"),
                    "labels": list(n.labels) if hasattr(n, "labels") else [],
                    "properties": dict(n)
                })

            rel_list = []
            for path_rels in rels:
                if path_rels is None:
                    continue
                for r in path_rels:
                    if r is None:
                        continue
                    rel_list.append({
                        "type": getattr(r, "type", None),
                        "start": getattr(r.start_node, "get", lambda x: None)("id") if hasattr(r, "start_node") else None,
                        "end": getattr(r.end_node, "get", lambda x: None)("id") if hasattr(r, "end_node") else None,
                        "properties": dict(r.items()) if hasattr(r, "items") else {}
                    })

            return {"nodes": node_list, "rels": rel_list}

    def list_subgraph_seeds(self) -> Dict[str, List[str]]:
        result = {}
        with self._driver.session() as sess:
            rec = sess.run("""
                MATCH (e:Entity)
                RETURN DISTINCT e.id AS id, e.type AS type
                UNION
                MATCH (s:Session)
                RETURN DISTINCT s.id AS id, 'session' AS type
            """)
            entity_ids = []
            entity_types = set()
            for r in rec:
                entity_ids.append(r["id"])
                entity_types.add(r["type"])

            rec = sess.run("MATCH (s:Session) RETURN DISTINCT s.id AS id")
            session_ids = [r["id"] for r in rec]

            result["entity_ids"] = entity_ids
            result["entity_types"] = list(entity_types)
            result["sessions"] = session_ids

        return result


# =============================================================================
# JSONL Archive
# =============================================================================

class Archive:
    def __init__(self, jsonl_path: Optional[str] = None):
        self.path = jsonl_path
        if self.path:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)

    def write(self, record: Dict[str, Any]):
        pass


# =============================================================================
# LLM Enrichment Interface (Stubs)
# =============================================================================

class LLMEnrichment:
    def __init__(self, ollama_endpoint: str = "http://localhost:11434", model: str = "mistral:7b"):
        self.endpoint = ollama_endpoint
        self.model = model

    def normalize_entities(self, entities: List[ExtractedEntity]) -> Dict[str, str]:
        return {e.text: e.text for e in entities}

    def expand_relationships(self, relations: List[ExtractedRelation], context: str) -> List[ExtractedRelation]:
        return relations

    def add_contextual_metadata(self, entity: ExtractedEntity, context: str) -> Dict[str, Any]:
        return {"description": f"Entity: {entity.text}"}

    def validate_relationships(self, relations: List[ExtractedRelation]) -> List[ExtractedRelation]:
        return [r for r in relations if r.confidence > 0.5]

    def generate_summary(self, subgraph: Dict[str, Any]) -> str:
        n_nodes = len(subgraph.get("nodes", []))
        n_rels = len(subgraph.get("rels", []))
        return f"Subgraph with {n_nodes} entities and {n_rels} relationships."

    def infer_relationships(self, entity_a: str, entity_b: str, context: str) -> Optional[str]:
        return "RELATED_TO"


# =============================================================================
# Enhanced Hybrid Memory API
# =============================================================================

class HybridMemory:
    """
    Enhanced two-tier hybrid memory with dynamic NLP extraction.

    PATCH: VectorClient replaced by HybridVectorStore.
    -------------------------------------------------------
    New optional __init__ parameters (all have safe defaults — existing
    callers that pass nothing new continue to work identically):

      vector_backend : "chroma" (default) | "weaviate"
          Select the vector store backend.

      weaviate_url : str  (default "http://localhost:8080")
          Weaviate endpoint — only used when vector_backend="weaviate".
          Requires: pip install weaviate-client>=4.0

      weaviate_api_key : str | None
          Optional Weaviate API key.

      weaviate_class : str  (default "VeraMemory")
          Weaviate class name for memory documents.

      write_embeddings_to_graph : bool  (default True)
          When True, every stored document's embedding vector is written
          back to the matching Neo4j node as node.embedding.  This bridges
          vector-space and graph-space:
            • ContextProbe can re-rank graph hits by cosine similarity
            • query_near_node() finds docs similar to any graph node
            • Neo4j 5.11+ vector index can do ANN queries purely in Cypher

    Embedding routing (unchanged from original):
        Pass ollama_manager + embedding_model to route through the cluster.
        Falls back to local SentenceTransformer if ollama_manager is None.
    """

    def __init__(
        self,
        neo4j_uri: str,
        neo4j_user: str,
        neo4j_password: str,
        chroma_dir: str,
        archive_jsonl: Optional[str] = None,
        enable_llm_enrichment: bool = False,
        ollama_manager=None,
        ollama_endpoint: str = "http://localhost:11434",
        embedding_model: str = "nomic-embed-text:latest",
        orchestrator=None,
        # ── vector backend selection ──────────────────────────────────────
        vector_backend: str = "chroma",          # "chroma" | "chroma_http" | "weaviate"
        # chroma_http options (used when vector_backend="chroma_http")
        chroma_host: str = "localhost",
        chroma_port: int = 8000,
        chroma_ssl: bool = False,
        chroma_headers=None,                     # Dict[str, str] | None
        chroma_tenant: str = "default_tenant",
        chroma_database: str = "default_database",
        # weaviate options (used when vector_backend="weaviate")
        weaviate_url: str = "http://localhost:8080",
        weaviate_api_key=None,
        weaviate_class: str = "VeraMemory",
        write_embeddings_to_graph: bool = True,
        entity_merge_threshold: float = 0.92,
        min_relation_confidence: float = 0.70,
    ):
        # ------------------------------------------------------------------
        # Graph client
        # ------------------------------------------------------------------
        self.graph = GraphClient(neo4j_uri, neo4j_user, neo4j_password)

        # ------------------------------------------------------------------
        # Embedding function
        # ------------------------------------------------------------------
        self.ollama_manager = ollama_manager
        self.embedding_model = embedding_model

        if ollama_manager is not None:
            ef_for_vec = OllamaClusterEmbeddingFunction(
                ollama_manager=ollama_manager,
                model=embedding_model,
            )
            logger.info(
                f"[HybridMemory] Cluster embeddings enabled: model='{embedding_model}' "
                f"via ollama_manager "
                f"({len(ollama_manager.pool.instances)} instance(s))"
            )
        else:
            logger.warning(
                "[HybridMemory] No ollama_manager provided — "
                "falling back to local SentenceTransformer embeddings. "
                "Pass ollama_manager to use the cluster."
            )
            safe_hf_model = (
                embedding_model
                if ":" not in embedding_model
                else "all-MiniLM-L6-v2"
            )
            if ":" in embedding_model:
                logger.warning(
                    f"[HybridMemory] embedding_model='{embedding_model}' contains ':' "
                    f"but no ollama_manager was supplied. "
                    f"Substituting '{safe_hf_model}' for SentenceTransformer fallback."
                )
            ef_for_vec = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=safe_hf_model
            )

        # ------------------------------------------------------------------
        # PATCH: HybridVectorStore replaces VectorClient
        #
        # Key differences:
        #   • Single "vera_memory" collection, session scoped by metadata filter
        #   • graph_driver wired in → embeddings written to Neo4j nodes
        #   • Supports "weaviate" backend via vector_backend param
        #   • get_collection() shim preserves backward compat for all callers
        # ------------------------------------------------------------------
        self.vec = HybridVectorStore(
                persist_dir=chroma_dir,
                embedding_function=ef_for_vec,
                graph_driver=self.graph._driver,
                backend=vector_backend,
                # chroma_http
                chroma_host=chroma_host,
                chroma_port=chroma_port,
                chroma_ssl=chroma_ssl,
                chroma_headers=chroma_headers,
                chroma_tenant=chroma_tenant,
                chroma_database=chroma_database,
                # weaviate
                weaviate_url=weaviate_url,
                weaviate_api_key=weaviate_api_key,
                weaviate_class=weaviate_class,
                write_embeddings_to_graph=write_embeddings_to_graph,
            )
        logger.info(
            f"[HybridMemory] VectorStore backend='{vector_backend}' "
            f"write_embeddings_to_graph={write_embeddings_to_graph}"
        )

        # ------------------------------------------------------------------
        # Other components (unchanged)
        # ------------------------------------------------------------------
        self.archive = Archive(archive_jsonl)
        self.nlp = NLPExtractor()

        self.embedding_llm = embedding_model

        self.previous_memory: Optional[MemoryItem] = None
        self.previous_session_id: Optional[str] = None

        self.enable_llm_enrichment = enable_llm_enrichment
        if enable_llm_enrichment:
            self.llm_enrichment = LLMEnrichment(ollama_endpoint)
        else:
            self.llm_enrichment = None

        self._execution_context = threading.local()
        self._execution_context.current_execution_id = None
        self._execution_context.tracked_nodes = set()

        self.orchestrator = orchestrator
        self.use_orchestrated_encoding = orchestrator is not None

        self._init_resolution_components(entity_merge_threshold, min_relation_confidence)

        if self.use_orchestrated_encoding:
            logger.info("[HybridMemory] Orchestrated encoding enabled (GPU-optimized)")
        else:
            logger.info("[HybridMemory] Direct encoding mode (no orchestrator)")

        logger.debug("[HybridMemory] Execution context tracking initialized")

    def _init_resolution_components(
        self,
        entity_merge_threshold: float,
        min_relation_confidence: float,
    ):
        """
        Called from __init__ to wire in the new components.
        Extracted as a helper so the patch is minimal and easy to apply.
        """
        self._resolver = EntityResolver(
            graph_driver=self.graph._driver,
            embedding_function=self.vec._ef,          # reuse the same ef
            merge_threshold=entity_merge_threshold,
            candidate_limit=50,
        )
        self._rel_extractor = SemanticRelationshipExtractor(
            min_confidence=min_relation_confidence,
        )
        logger.info(
            f"[HybridMemory] EntityResolver merge_threshold={entity_merge_threshold}, "
            f"SemanticRelationshipExtractor min_confidence={min_relation_confidence}"
        )
    
    # ------------------------------------------------------------------
    # Encoding helpers (unchanged)
    # ------------------------------------------------------------------

    def _encode_text_for_vector_store(
        self, text: str, metadata: Optional[Dict[str, Any]] = None
    ):
        if self.use_orchestrated_encoding:
            logger.debug(f"[HybridMemory] Encoding via orchestrator: {len(text)} chars")
            try:
                from Vera.Orchestration.orchestration import TaskStatus
                task_id = self.orchestrator.submit_task(
                    'memory.encode_text',
                    vera_instance=self._get_vera_instance(),
                    text=text,
                    metadata=metadata,
                )
                result_obj = self.orchestrator.wait_for_result(task_id, timeout=30.0)
                if result_obj and result_obj.status == TaskStatus.COMPLETED:
                    return result_obj.result['embedding']
                error_msg = result_obj.error if result_obj else "Task timed out"
                logger.warning(
                    f"[HybridMemory] Orchestrated encoding failed: {error_msg}, "
                    f"falling back to direct"
                )
                return self._encode_text_direct(text)
            except Exception as e:
                logger.warning(
                    f"[HybridMemory] Orchestrated encoding error: {e}, falling back to direct"
                )
                return self._encode_text_direct(text)
        else:
            return self._encode_text_direct(text)

    def _encode_text_direct(self, text: str) -> List[float]:
        if self.ollama_manager is not None:
            embeddings = self.ollama_manager.create_embeddings(model=self.embedding_model)
            return embeddings.embed_query(text)

        logger.error(
            "[HybridMemory] _encode_text_direct: no ollama_manager available, "
            "falling back to localhost:11434.  "
            "This should NOT happen in production — pass ollama_manager at init."
        )
        embeddings = OllamaEmbeddings(
            model=self.embedding_llm,
            base_url="http://localhost:11434",
        )
        return embeddings.embed_query(text)

    def _get_vera_instance(self):
        if not hasattr(self, '_vera_ref'):
            raise RuntimeError("Vera instance reference not set on HybridMemory")
        return self._vera_ref

    def set_vera_instance(self, vera_instance):
        self._vera_ref = vera_instance
        logger.debug("[HybridMemory] Vera instance reference set")

    # ------------------------------------------------------------------
    # Orchestrated extraction (unchanged)
    # ------------------------------------------------------------------

    def extract_and_link_orchestrated(
        self,
        session_id: str,
        text: str,
        source_node_id: Optional[str] = None,
        auto_promote: bool = False,
    ):
        if self.use_orchestrated_encoding:
            logger.debug(
                f"[HybridMemory] Entity extraction via orchestrator: {len(text)} chars"
            )
            try:
                from Vera.Orchestration.orchestration import TaskStatus
                task_id = self.orchestrator.submit_task(
                    'memory.extract_entities',
                    vera_instance=self._get_vera_instance(),
                    session_id=session_id,
                    text=text,
                    source_node_id=source_node_id,
                    auto_promote=auto_promote,
                )
                result_obj = self.orchestrator.wait_for_result(task_id, timeout=60.0)
                if result_obj and result_obj.status == TaskStatus.COMPLETED:
                    return result_obj.result
                logger.warning("[HybridMemory] Orchestrated extraction failed, falling back")
                return self.extract_and_link(session_id, text, source_node_id, auto_promote)
            except Exception as e:
                logger.warning(
                    f"[HybridMemory] Orchestrated extraction error: {e}, falling back"
                )
                return self.extract_and_link(session_id, text, source_node_id, auto_promote)
        else:
            return self.extract_and_link(session_id, text, source_node_id, auto_promote)

    # ------------------------------------------------------------------
    # Sessions (Tier 2)
    # ------------------------------------------------------------------

    def start_session(
        self,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Session:
        sid = session_id or f"sess_{int(time.time() * 1000)}"
        sess = Session(
            id=sid,
            started_at=datetime.utcnow().isoformat(),
            metadata=metadata or {},
        )
        self.graph.upsert_session(sess)
        self.archive.write({"type": "session_start", "session": sess.model_dump()})
        return sess

    def end_session(self, session_id: str):
        self.graph.end_session(session_id)
        self.archive.write({"type": "session_end", "session_id": session_id})

    def add_session_memory(
        self,
        session_id: str,
        text: str,
        node_type: str,
        metadata: Optional[Dict[str, Any]] = None,
        *,
        labels: Optional[List[str]] = None,
        promote: bool = False,
        auto_extract: bool = True,
    ) -> MemoryItem:
        
        if self.previous_session_id != session_id:
            self._resolver.flush_cache()   # PATCH: clear cross-session cache

        if labels is None:
            labels = [node_type.capitalize()]
        mem_id = f"mem_{int(time.time() * 1000)}"

        item_metadata = metadata or {}
        item_metadata["type"] = node_type
        item_metadata["labels"] = labels
        # PATCH: these two keys enable unified-collection filtering and
        # query_near_node() — the only change in this method.
        item_metadata["session_id"] = session_id
        item_metadata["node_id"] = mem_id

        item = MemoryItem(id=mem_id, text=text, metadata=item_metadata, tier="session")
        logger.debug(
            f"[HybridMemory] Adding session memory {item.id} to session {session_id}"
        )
        # PATCH: collection name "session_{session_id}" still works —
        # HybridVectorStore._effective_where() translates it to a metadata
        # filter on the unified "vera_memory" collection automatically.
        collection = f"session_{session_id}"

        chroma_metadata = dict(item.metadata)
        if "labels" in chroma_metadata and isinstance(chroma_metadata["labels"], list):
            chroma_metadata["labels"] = ",".join(chroma_metadata["labels"])

        self.vec.add_texts(collection, [item.id], [item.text], [chroma_metadata])

        node = Node(
            id=item.id,
            type=node_type,
            labels=labels,
            properties={
                "text": item.text,
                "created_at": datetime.now().isoformat(),
                "session_id": session_id,
                **item.metadata,
            },
        )
        self.graph.upsert_entity(node)
        self._track_node_creation(item.id)

        if self.previous_memory and self.previous_session_id == session_id:
            self.link(
                item.id,
                self.previous_memory.id,
                "FOLLOWS",
                {"source": self.previous_memory.id},
            )

        self.previous_session_id = session_id
        self.previous_memory = item

        if auto_extract and len(text.strip()) > 20:
            extraction = self.extract_and_link(session_id, text, auto_promote=False)
            for entity in extraction.get('entities', []):
                logger.debug(entity)
                self.link(item.id, entity['id'], "MENTIONS_ENTITY")
            for relation in extraction.get('relations', []):
                logger.debug(relation)
                self.link(relation['head_id'], relation['tail_id'], relation['relation'])

        if promote:
            self.promote_session_memory_to_long_term(item)

        self.archive.write(
            {
                "type": "session_memory",
                "session_id": session_id,
                "memory": item.model_dump(),
            }
        )
        return item


    def extract_and_link(
        self,
        session_id: str,
        text: str,
        source_node_id=None,
        auto_promote: bool = False,
    ) -> dict:
        """
        Extract entities and relationships from text, link to session graph.
    
        Changes vs original
        -------------------
        - Entities are UPSERTED via EntityResolver (stable IDs + fuzzy merge).
        Near-duplicate entities across sessions converge to the same node.
        - SemanticRelationshipExtractor produces typed world-model relations
        (IS_CEO_OF, WORKS_AT, ACQUIRED_BY, …) from all three strategies
        (pattern rules, dep-parse, verb-map).
        - Original NLP relations (SVO / co-occurrence) are still included but
        marked strategy="nlp_basic" and given lower confidence weight.
        - All edges use resolved canonical IDs — zero text-based lookups.
        """
        logger.debug(
            f"[HybridMemory] extract_and_link session={session_id} "
            f"text_len={len(text)}"
        )
        try:
            text = sanitize_for_nlp(text)
    
            # ── Step 1: NLP entity + basic relation extraction ─────────────────
            entities_raw, basic_relations_raw = self.nlp.extract_all(text)
            logger.info(
                f"[HybridMemory] NLP raw: {len(entities_raw)} entities, "
                f"{len(basic_relations_raw)} basic relations"
            )
    
            if not entities_raw:
                logger.warning("[HybridMemory] No entities extracted")
                return {"entities": [], "relations": [], "clusters": {}}
    
            # Ensure every entity has a stable entity_id
            for entity in entities_raw:
                if not getattr(entity, "entity_id", None):
                    entity.entity_id = entity.get_stable_id()
    
            # ── Step 2: Cluster entities ──────────────────────────────────────
            non_clusterable_labels = {
                'CODE_BLOCK', 'CLASS', 'METHOD', 'FUNCTION', 'IMPORT', 'IMPORT_FROM',
                'URL', 'EMAIL', 'UUID', 'HASH_MD5', 'HASH_SHA1', 'HASH_SHA256',
                'TERMINAL_COMMAND', 'FILE_PATH', 'IPV4', 'IPV6',
            }
            clusterable   = [e for e in entities_raw if e.label not in non_clusterable_labels]
            unclusterable = [e for e in entities_raw if e.label in non_clusterable_labels]
    
            try:
                clusters = (
                    self.nlp.cluster_entities(clusterable)
                    if clusterable and any(e.embedding for e in clusterable)
                    else {f"cluster_{i}": [e] for i, e in enumerate(clusterable)}
                )
            except Exception as exc:
                logger.warning(f"[HybridMemory] Clustering failed: {exc}")
                clusters = {f"cluster_{i}": [e] for i, e in enumerate(clusterable)}
    
            for i, entity in enumerate(unclusterable):
                clusters[f"nc_{i}"] = [entity]
    
            # ── Step 3: Resolve + upsert canonical entity nodes ───────────────
            created_entities = []
            # entity_text_lower → canonical_id  (for relation ID assignment)
            text_to_canon_id: dict[str, str] = {}
            # original extraction_id → canonical_id
            extraction_id_to_canon: dict[str, str] = {}
    
            for cluster_id, cluster in clusters.items():
                if not cluster:
                    continue
                try:
                    resolved = self._resolver.resolve_cluster(cluster, session_id)
                    if not resolved:
                        continue
    
                    canon_id   = resolved["canonical_id"]
                    canon_text = resolved["canonical_text"]
                    label      = resolved["label"]
                    confidence = resolved["confidence"]
                    variants   = resolved["variants"]
                    was_merged = resolved["was_merged"]
    
                    if not canon_text or not canon_text.strip():
                        continue
    
                    # Build properties for the node
                    meta: dict = {
                        "text":                   canon_text,
                        "confidence":             confidence,
                        "session_id":             session_id,
                        "extracted_from_session": session_id,
                        "variants":               variants,
                        "cluster_id":             cluster_id,
                        "last_seen":              datetime.now().isoformat(),
                        "seen_count":             1,
                    }
                    if source_node_id:
                        meta["source_node_id"] = source_node_id
    
                    # Merge or create the graph node
                    node = Node(
                        id=canon_id,
                        type="extracted_entity",
                        labels=["ExtractedEntity", label],
                        properties=meta,
                    )
                    # graph.upsert_entity does MERGE — safe to call on existing nodes
                    self.graph.upsert_entity(node)
                    self.graph.link_session_to_entity(
                        session_id, canon_id, "EXTRACTED_IN"
                    )
    
                    if source_node_id:
                        self.graph.upsert_edge(Edge(
                            src=canon_id,
                            dst=source_node_id,
                            rel="EXTRACTED_FROM",
                            properties={
                                "extraction_type": label,
                                "confidence":      confidence,
                            },
                        ))
    
                    # Map all variant texts to canonical ID for relation linking
                    for var_text in variants:
                        text_to_canon_id[var_text.lower()] = canon_id
    
                    # Also map all extraction IDs from the cluster
                    for ent in cluster:
                        extraction_id_to_canon[ent.entity_id] = canon_id
    
                    created_entities.append({
                        "id":           canon_id,
                        "text":         canon_text,
                        "label":        label,
                        "confidence":   confidence,
                        "was_merged":   was_merged,
                        "variants":     variants,
                    })
                    logger.debug(
                        f"[HybridMemory] entity {'merged' if was_merged else 'created'}: "
                        f"{canon_id} = '{canon_text}' ({label})"
                    )
    
                except Exception as exc:
                    logger.error(
                        f"[HybridMemory] entity resolve error cluster={cluster_id}: {exc}",
                        exc_info=True,
                    )
                    continue
    
            logger.info(
                f"[HybridMemory] {len(created_entities)} entity nodes "
                f"({'merged/upserted' if any(e['was_merged'] for e in created_entities) else 'created'})"
            )
    
            # ── Step 4: Semantic relationship extraction ───────────────────────
            semantic_relations = self._rel_extractor.extract(text, text_to_canon_id)
            logger.info(
                f"[HybridMemory] SemanticRelExtractor: {len(semantic_relations)} relations"
            )
    
            # ── Step 5: Merge with basic NLP relations ─────────────────────────
            # Convert basic NLP relations into a unified format
            all_relation_specs = []
    
            for rel in semantic_relations:
                # Prefer IDs from resolver lookup, fall back to entity_lookup
                head_id = (
                    rel.head_id
                    or text_to_canon_id.get(rel.head.lower())
                )
                tail_id = (
                    rel.tail_id
                    or text_to_canon_id.get(rel.tail.lower())
                )
                if head_id and tail_id and head_id != tail_id:
                    all_relation_specs.append({
                        "head_id":   head_id,
                        "tail_id":   tail_id,
                        "head":      rel.head,
                        "tail":      rel.tail,
                        "relation":  rel.relation,
                        "confidence": rel.confidence,
                        "context":   rel.context,
                        "strategy":  rel.strategy,
                    })
    
            # Basic NLP relations (SVO, co-occurrence) — lower weight
            for rel in basic_relations_raw:
                if not rel.head or not rel.tail:
                    continue
    
                if hasattr(rel, "head_id") and rel.head_id:
                    head_id = extraction_id_to_canon.get(rel.head_id, f"entity_{rel.head_id}")
                else:
                    head_id = text_to_canon_id.get(rel.head.lower())
    
                if hasattr(rel, "tail_id") and rel.tail_id:
                    tail_id = extraction_id_to_canon.get(rel.tail_id, f"entity_{rel.tail_id}")
                else:
                    tail_id = text_to_canon_id.get(rel.tail.lower())
    
                if head_id and tail_id and head_id != tail_id:
                    all_relation_specs.append({
                        "head_id":   head_id,
                        "tail_id":   tail_id,
                        "head":      rel.head,
                        "tail":      rel.tail,
                        "relation":  getattr(rel, "relation", "RELATED_TO"),
                        "confidence": getattr(rel, "confidence", 0.60),
                        "context":   getattr(rel, "context", "")[:300],
                        "strategy":  "nlp_basic",
                    })
    
            # ── Step 6: Deduplicate relations and write edges ──────────────────
            # Keep highest-confidence instance of each (head_id, tail_id, relation)
            seen_triples: dict[tuple, dict] = {}
            for spec in all_relation_specs:
                key = (spec["head_id"], spec["tail_id"], spec["relation"])
                if key not in seen_triples or spec["confidence"] > seen_triples[key]["confidence"]:
                    seen_triples[key] = spec
    
            created_relations = []
            skipped = 0
    
            for spec in seen_triples.values():
                try:
                    self.link(
                        spec["head_id"],
                        spec["tail_id"],
                        spec["relation"],
                        {
                            "confidence":             spec["confidence"],
                            "context":                spec.get("context", "")[:300],
                            "extracted_from_session": session_id,
                            "head_text":              spec["head"],
                            "tail_text":              spec["tail"],
                            "strategy":               spec.get("strategy", "unknown"),
                        },
                    )
                    created_relations.append({
                        "head":      spec["head"],
                        "tail":      spec["tail"],
                        "relation":  spec["relation"],
                        "confidence": spec["confidence"],
                        "head_id":   spec["head_id"],
                        "tail_id":   spec["tail_id"],
                        "strategy":  spec.get("strategy", "unknown"),
                    })
                    logger.debug(
                        f"[HybridMemory] ✓ {spec['head']} "
                        f"--[{spec['relation']}]--> {spec['tail']} "
                        f"(conf={spec['confidence']:.2f}, strat={spec.get('strategy','')})"
                    )
                except Exception as exc:
                    logger.warning(f"[HybridMemory] edge write failed: {exc}")
                    skipped += 1
    
            logger.info(
                f"[HybridMemory] {len(created_relations)} relation edges written, "
                f"{skipped} skipped"
            )
    
            # ── Step 7: Optional promotion ─────────────────────────────────────
            if auto_promote:
                try:
                    high_conf = [
                        e for e in entities_raw
                        if getattr(e, "confidence", 0) > 0.8
                    ]
                    for entity in high_conf:
                        if not entity.text or not entity.text.strip():
                            continue
                        canon_id = extraction_id_to_canon.get(entity.entity_id)
                        if not canon_id:
                            continue
                        self.vec.add_texts(
                            "long_term_docs",
                            [canon_id],
                            [entity.text],
                            [{"type": "promoted_entity", "label": entity.label}],
                        )
                    logger.info(f"[HybridMemory] promoted {len(high_conf)} high-confidence entities")
                except Exception as exc:
                    logger.error(f"[HybridMemory] promotion error: {exc}", exc_info=True)
    
            result = {
                "entities":          created_entities,
                "relations":         created_relations,
                "clusters":          {k: [e.text for e in v if e.text] for k, v in clusters.items()},
                "skipped_relations": skipped,
                "source_node_id":    source_node_id,
            }
    
            try:
                self.archive.write({
                    "type":          "nlp_extraction",
                    "session_id":    session_id,
                    "source_node_id": source_node_id,
                    "timestamp":     time.time(),
                    "extraction":    result,
                    "text_length":   len(text),
                })
            except Exception as exc:
                logger.error(f"[HybridMemory] archive write failed: {exc}")
    
            return result
    
        except Exception as exc:
            logger.error(f"[HybridMemory] fatal error in extract_and_link: {exc}", exc_info=True)
            return {"entities": [], "relations": [], "clusters": {}, "error": str(exc)}
    
    

    def link_to_session(self, session_id: str, entity_id: str, rel: str = "HAS_MEMORY"):
        self.graph.link_session_to_entity(session_id, entity_id, rel)

    def get_session_memory(self, session_id: str) -> List[MemoryItem]:
        # PATCH: get_collection() returns a _CollectionShim that routes to the
        # unified store with a session_id filter — identical behaviour to original.
        collection = f"session_{session_id}"
        res = self.vec.get_collection(collection).get()
        hits = []
        if res and res.get("ids"):
            for i, item_id in enumerate(res["ids"]):
                hits.append(MemoryItem(
                    id=item_id,
                    text=res["documents"][i],
                    metadata=res["metadatas"][i] if res.get("metadatas") else {},
                ))
        return hits

    def list_sessions(self) -> List[Session]:
        result = []
        with self.graph._driver.session() as sess:
            rec = sess.run(
                "MATCH (s:Session) RETURN s.id AS id, s.started_at AS started_at, "
                "s.ended_at AS ended_at, s.metadata AS metadata"
            )
            for r in rec:
                result.append(Session(
                    id=r["id"],
                    started_at=r["started_at"],
                    ended_at=r.get("ended_at"),
                    metadata=r.get("metadata", {}),
                ))
        return result

    def focus_context(
        self, session_id: str, query: str, k: int = 8
    ) -> List[Dict[str, Any]]:
        # PATCH: collection name "session_{sid}" is automatically scoped by
        # HybridVectorStore._effective_where() — no change to call site.
        res = self.vec.query(
            collection=f"session_{session_id}", text=query, n_results=k
        )
        # vec.query now returns List[dict] directly (not ChromaDB response dict)
        hits = res if isinstance(res, list) else []
        self.archive.write({
            "type": "session_focus",
            "session_id": session_id,
            "query": query,
            "results": hits,
        })
        return hits

    # ------------------------------------------------------------------
    # Long-term (Tier 1)
    # ------------------------------------------------------------------

    def upsert_entity(
        self,
        entity_id: str,
        etype: str,
        labels: Optional[List[str]] = None,
        properties: Optional[Dict[str, Any]] = None,
    ):
        if "source_process" not in (properties or {}):
            if properties is None:
                properties = {}
            caller_file = inspect.stack()[2].filename
            properties["source_process"] = (
                f"{os.path.basename(caller_file)}:{sys._getframe(1).f_code.co_name}"
            )

        node = Node(
            id=entity_id,
            type=etype,
            labels=labels or [],
            properties=properties or {},
        )
        self.graph.upsert_entity(node)
        self._track_node_creation(entity_id)
        self.archive.write({"type": "entity_upsert", "node": node.model_dump()})
        return node

    def link(
        self,
        src: str,
        dst: str,
        rel: str,
        properties: Optional[Dict[str, Any]] = None,
    ):
        edge = Edge(src=src, dst=dst, rel=rel, properties=properties or {})
        self.graph.upsert_edge(edge)
        self.archive.write({"type": "edge_upsert", "edge": edge.model_dump()})

    def link_by_property(
        self,
        src_property: str,
        src_value: Any,
        dst_property: str,
        dst_value: Any,
        rel: str,
        properties: Optional[Dict[str, Any]] = None,
    ):
        logger.info(
            f"[MEMORY] Linking nodes where {src_property}={src_value} "
            f"-[{rel}]-> {dst_property}={dst_value}"
        )
        cypher = f"""
        MATCH (src {{ {src_property}: $src_value }})
        MATCH (dst {{ {dst_property}: $dst_value }})
        MERGE (src)-[r:REL {{rel: $rel}}]->(dst)
        SET r += $properties
        RETURN r
        """
        with self.graph._driver.session() as sess:
            sess.run(cypher, {
                "src_value": src_value,
                "dst_value": dst_value,
                "rel": rel,
                "properties": properties or {},
            })
        self.archive.write({
            "type": "edge_upsert_by_property",
            "src_property": src_property,
            "src_value": src_value,
            "dst_property": dst_property,
            "dst_value": dst_value,
            "rel": rel,
            "properties": properties or {},
        })

    def attach_document(
        self,
        entity_id: str,
        doc_id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        logger.info(f"[MEMORY] Attaching document {doc_id} to entity {entity_id}")
        meta = {"entity_id": entity_id, "node_id": doc_id, **(metadata or {})}
        self.vec.add_texts(
            collection="long_term_docs",
            ids=[doc_id],
            texts=[text],
            metadatas=[meta],
        )
        doc_node = Node(
            id=doc_id,
            type="document",
            labels=["Document"],
            properties=meta,
        )
        self.graph.upsert_entity(doc_node)
        self.link(entity_id, doc_id, "HAS_DOCUMENT")
        self.archive.write({
            "type": "document_attach",
            "entity_id": entity_id,
            "doc_id": doc_id,
            "meta": meta,
        })
        self._track_node_creation(doc_id)
        return doc_node

    def semantic_retrieve(
        self,
        query: str,
        k: int = 8,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        hits = self.vec.query(
            collection="long_term_docs", text=query, n_results=k, where=where
        )
        self.archive.write({
            "type": "semantic_retrieve",
            "query": query,
            "results": hits,
        })
        return hits

    def promote_session_memory_to_long_term(
        self,
        item: MemoryItem,
        entity_anchor: Optional[str] = None,
    ):
        chroma_metadata = {"promoted": True, "node_id": item.id, **item.metadata}
        if "labels" in chroma_metadata and isinstance(chroma_metadata["labels"], list):
            chroma_metadata["labels"] = ",".join(chroma_metadata["labels"])

        self.vec.add_texts(
            collection="long_term_docs",
            ids=[item.id],
            texts=[item.text],
            metadatas=[chroma_metadata],
        )

        original_type = item.metadata.get("type", "thought")
        original_labels = item.metadata.get("labels", [original_type.capitalize()])
        if isinstance(original_labels, str):
            original_labels = [l.strip() for l in original_labels.split(",")]
        labels = list(set(original_labels + ["Promoted"]))

        node = Node(
            id=item.id,
            type=original_type,
            labels=labels,
            properties={"promoted": True, **item.metadata, "text": item.text},
        )
        self.graph.upsert_entity(node)

        if entity_anchor:
            self.link(entity_anchor, item.id, "HAS_THOUGHT")
        self.archive.write({
            "type": "promotion",
            "memory": item.model_dump(),
            "anchor": entity_anchor,
        })

    def link_session_focus(self, session_id: str, entity_ids: List[str]):
        for eid in entity_ids:
            self.graph.link_session_to_entity(session_id, eid)
        self.archive.write({
            "type": "session_focus_link",
            "session_id": session_id,
            "entities": entity_ids,
        })

    def extract_subgraph(self, seed_entity_ids, depth: int = 2):
        return self.graph.get_subgraph(seed_entity_ids, depth=depth)

    def store_file(self, file_path: str, chunk_size: int = 1000, chunk_overlap: int = 100):
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"File {file_path} not found")

        file_name = os.path.basename(file_path)
        file_id = f"file_{hash(file_path) & 0xffffffff}"

        file_node = Node(
            id=file_id,
            type="file",
            labels=["File"],
            properties={"name": file_name, "path": file_path},
        )
        self.graph.upsert_entity(file_node)

        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, chunk_overlap=chunk_overlap
        )
        chunks = splitter.split_text(text)

        ids = [f"{file_id}_{i}" for i in range(len(chunks))]
        metadatas = [
            {"file_id": file_id, "chunk_index": i, "node_id": f"{file_id}_{i}"}
            for i in range(len(chunks))
        ]
        self.vec.add_texts("long_term_docs", ids=ids, texts=chunks, metadatas=metadatas)

        return file_id

    def retrieve_file(self, file_id: str, query: Optional[str] = None, top_k: int = 5):
        with self.graph._driver.session() as sess:
            rec = sess.run(
                "MATCH (n:File {id: $id}) RETURN n.path AS path", id=file_id
            ).single()
            if not rec:
                raise ValueError(f"No file with ID {file_id} found")
            file_path = rec["path"]

        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            full_text = f.read()

        if query is None:
            return {"file_path": file_path, "full_text": full_text}

        hits = self.semantic_retrieve(query, k=top_k)
        relevant_chunks = [
            hit for hit in hits if hit["metadata"].get("file_id") == file_id
        ]
        return {"file_path": file_path, "relevant_chunks": relevant_chunks}

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def close(self):
        self.graph.close()

    # ------------------------------------------------------------------
    # Session node helpers (unchanged)
    # ------------------------------------------------------------------

    def get_or_create_session_node(self, session_id: str) -> Node:
        logger.debug(f"[HybridMemory] Getting/creating session node: {session_id}")
        with self.graph._driver.session() as sess:
            result = sess.run(
                "MATCH (s:Session {id: $id}) RETURN s", {"id": session_id}
            )
            record = result.single()
            if record:
                s = record["s"]
                return Node(
                    id=s.get("id"),
                    type="session",
                    labels=["Session"],
                    properties=dict(s),
                )

        session = self.start_session(session_id=session_id)
        return Node(
            id=session.id,
            type="session",
            labels=["Session"],
            properties={
                "started_at": session.started_at,
                "metadata": session.metadata,
            },
        )

    def get_session_node_id(self, session_id: str) -> str:
        self.get_or_create_session_node(session_id)
        return session_id

    def link_session_to_execution(
        self,
        session_id: str,
        execution_id: str,
        rel: str = "PERFORMED_TOOL_EXECUTION",
    ):
        logger.debug(
            f"[HybridMemory] Linking session {session_id} to execution {execution_id}"
        )
        cypher = """
        MATCH (s:Session {id: $sid})
        MATCH (e:ToolExecution {id: $eid})
        MERGE (s)-[r:REL {rel: $rel}]->(e)
        SET r.timestamp = $timestamp
        RETURN r
        """
        with self.graph._driver.session() as sess:
            sess.run(cypher, {
                "sid": session_id,
                "eid": execution_id,
                "rel": rel,
                "timestamp": datetime.utcnow().isoformat(),
            })

    def get_node_by_id(self, node_id: str) -> Optional[Node]:
        with self.graph._driver.session() as sess:
            result = sess.run(
                "MATCH (n {id: $id}) RETURN n, labels(n) as labels",
                {"id": node_id},
            )
            record = result.single()
            if not record:
                return None
            n = record["n"]
            labels = record["labels"]
            node_type = n.get("type", labels[0] if labels else "unknown")
            return Node(
                id=n.get("id"),
                type=node_type,
                labels=labels,
                properties=dict(n),
            )

    def node_exists(self, node_id: str) -> bool:
        with self.graph._driver.session() as sess:
            result = sess.run(
                "MATCH (n {id: $id}) RETURN count(n) as count", {"id": node_id}
            )
            record = result.single()
            return record["count"] > 0 if record else False

    # ------------------------------------------------------------------
    # Tool execution tracking (unchanged)
    # ------------------------------------------------------------------

    def get_tool_executions_for_node(
        self, node_id: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        logger.debug(
            f"[HybridMemory] Getting tool executions for node: {node_id}"
        )
        cypher = """
        MATCH (node {id: $node_id})-[r:TOOL_EXECUTED]->(exec:ToolExecution)
        OPTIONAL MATCH (exec)-[:PRODUCED]->(result:ToolResult)
        RETURN exec, result, r
        ORDER BY exec.executed_at DESC
        LIMIT $limit
        """
        executions = []
        with self.graph._driver.session() as sess:
            result = sess.run(cypher, {"node_id": node_id, "limit": limit})
            for record in result:
                exec_node = record["exec"]
                result_node = record.get("result")
                execution_data = {
                    "execution_id": exec_node.get("id"),
                    "tool_name": exec_node.get("tool_name"),
                    "executed_at": exec_node.get("executed_at"),
                    "duration_ms": exec_node.get("duration_ms"),
                    "success": exec_node.get("success", True),
                    "input_summary": exec_node.get("input_summary"),
                }
                if result_node:
                    execution_data["result"] = {
                        "result_id": result_node.get("id"),
                        "output_preview": result_node.get("output_preview"),
                        "output_length": result_node.get("output_length"),
                    }
                executions.append(execution_data)
        return executions

    def get_execution_result(self, execution_id: str) -> Optional[Dict[str, Any]]:
        logger.debug(f"[HybridMemory] Getting execution result: {execution_id}")
        cypher = """
        MATCH (exec:ToolExecution {id: $exec_id})-[:PRODUCED]->(result:ToolResult)
        OPTIONAL MATCH (result)-[:FULL_OUTPUT]->(doc)
        RETURN exec, result, doc
        """
        with self.graph._driver.session() as sess:
            result = sess.run(cypher, {"exec_id": execution_id})
            record = result.single()
            if not record:
                return None
            exec_node = record["exec"]
            result_node = record["result"]
            doc_node = record.get("doc")
            full_output = result_node.get("output_preview", "")
            if doc_node:
                full_output = doc_node.get("content", full_output)
            return {
                "execution_id": execution_id,
                "tool_name": exec_node.get("tool_name"),
                "target_node": exec_node.get("target_node"),
                "executed_at": exec_node.get("executed_at"),
                "duration_ms": exec_node.get("duration_ms"),
                "success": exec_node.get("success", True),
                "input": exec_node.get("input_summary"),
                "output": full_output,
                "output_length": result_node.get("output_length"),
            }

    def create_tool_execution_node(
        self,
        node_id: str,
        tool_name: str,
        metadata: Dict[str, Any],
    ) -> str:
        execution_id = (
            f"tool_exec_{node_id}_{tool_name}_{int(datetime.now().timestamp())}"
        )
        exec_node = Node(
            id=execution_id,
            type="tool_execution",
            labels=["ToolExecution", tool_name],
            properties={
                "tool_name": tool_name,
                "target_node": node_id,
                "executed_at": metadata.get("executed_at"),
                "duration_ms": metadata.get("duration_ms"),
                "success": metadata.get("success", True),
                "input_summary": str(metadata.get("input", ""))[:500],
            },
        )
        self.upsert_entity(exec_node.id, exec_node.type, exec_node.labels, exec_node.properties)
        self.link(
            node_id,
            execution_id,
            "TOOL_EXECUTED",
            {"tool": tool_name, "timestamp": metadata.get("executed_at")},
        )
        return execution_id

    def create_tool_result_node(
        self,
        execution_id: str,
        output: str,
        metadata: Dict[str, Any],
    ) -> str:
        result_id = f"{execution_id}_result"
        output_preview = output[:1000] if len(output) > 1000 else output

        result_node = Node(
            id=result_id,
            type="tool_result",
            labels=["ToolResult", "Output"],
            properties={
                "tool_name": metadata.get("tool_name"),
                "output_preview": output_preview,
                "output_length": len(output),
                "created_at": datetime.now().isoformat(),
            },
        )
        self.upsert_entity(
            result_node.id, result_node.type, result_node.labels, result_node.properties
        )
        self.link(
            execution_id,
            result_id,
            "PRODUCED",
            {"output_length": len(output), "truncated": len(output) > 1000},
        )

        if len(output) > 500:
            doc_id = f"{result_id}_full_output"
            doc_node = self.attach_document(
                result_id,
                doc_id,
                output,
                {
                    "tool": metadata.get("tool_name"),
                    "execution_id": execution_id,
                    "type": "tool_output",
                },
            )
            self.link(result_id, doc_node.id, "FULL_OUTPUT", {"source": "tool_execution"})

        return result_id

    # ------------------------------------------------------------------
    # Execution context tracking (unchanged)
    # ------------------------------------------------------------------

    @contextmanager
    def track_execution(self, execution_id: str):
        previous_execution_id = getattr(
            self._execution_context, 'current_execution_id', None
        )
        previous_tracked = getattr(self._execution_context, 'tracked_nodes', set())

        self._execution_context.current_execution_id = execution_id
        self._execution_context.tracked_nodes = set()

        logger.debug(
            f"[ExecutionTracking] Started tracking for execution: {execution_id}"
        )

        try:
            yield self._execution_context.tracked_nodes
        finally:
            tracked = self._execution_context.tracked_nodes.copy()

            if execution_id and tracked:
                logger.info(
                    f"[ExecutionTracking] Linking {len(tracked)} nodes to {execution_id}"
                )
                for node_id in tracked:
                    try:
                        self.link(
                            execution_id,
                            node_id,
                            "CREATED_NODE",
                            {
                                "created_during_execution": True,
                                "timestamp": datetime.now().isoformat(),
                            },
                        )
                    except Exception as e:
                        logger.warning(f"Failed to link {node_id} to execution: {e}")

            self._execution_context.current_execution_id = previous_execution_id
            self._execution_context.tracked_nodes = previous_tracked

            logger.debug(
                f"[ExecutionTracking] Finished tracking for execution: "
                f"{execution_id} ({len(tracked)} nodes)"
            )

    def _track_node_creation(self, node_id: str):
        execution_id = getattr(self._execution_context, 'current_execution_id', None)
        if execution_id:
            tracked_nodes = getattr(self._execution_context, 'tracked_nodes', None)
            if tracked_nodes is not None:
                tracked_nodes.add(node_id)
                logger.debug(
                    f"[ExecutionTracking] Tracked node creation: {node_id} "
                    f"(execution: {execution_id})"
                )

    def get_execution_created_nodes(self, execution_id: str) -> List[Dict[str, Any]]:
        logger.debug(
            f"[HybridMemory] Getting nodes created by execution: {execution_id}"
        )
        cypher = """
        MATCH (exec:ToolExecution {id: $exec_id})-[:CREATED_NODE]->(node)
        RETURN node, labels(node) as labels
        ORDER BY node.created_at
        """
        nodes = []
        with self.graph._driver.session() as sess:
            result = sess.run(cypher, {"exec_id": execution_id})
            for record in result:
                node = record["node"]
                labels = record["labels"]
                nodes.append({
                    "id": node.get("id"),
                    "type": node.get("type"),
                    "labels": labels,
                    "properties": dict(node),
                })
        return nodes


# =============================================================================
# Smoke-test (unchanged from original, updated HybridMemory call to show
# new optional params — existing call without them also works fine)
# =============================================================================

if __name__ == "__main__":
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "testpassword")
    CHROMA_DIR = "./Memory/chroma_store"
    ARCHIVE_PATH = "./Memory/archive/memory_archive.jsonl"

    mem = HybridMemory(
        neo4j_uri=NEO4J_URI,
        neo4j_user=NEO4J_USER,
        neo4j_password=NEO4J_PASSWORD,
        chroma_dir=CHROMA_DIR,
        archive_jsonl=ARCHIVE_PATH,
        ollama_manager=None,
        embedding_model="all-MiniLM-L6-v2",
        enable_llm_enrichment=False,
        # New params — all optional, shown here for documentation:
        vector_backend="chroma",           # switch to "weaviate" to use Weaviate
        write_embeddings_to_graph=True,    # False to skip graph embedding writeback
    )

    try:
        print("=== Starting Session ===")
        sess = mem.start_session(metadata={"agent": "nlp_test"})
        print(f"Session ID: {sess.id}")

        print("\n=== Testing NLP Extraction ===")
        test_text = """
        Apple Inc. announced a new partnership with Microsoft Corporation.
        Tim Cook, CEO of Apple, will meet with Satya Nadella next week.
        The collaboration focuses on AI and cloud computing technologies.
        """

        extraction = mem.extract_and_link(sess.id, test_text, auto_promote=False)
        print(f"\nExtracted {len(extraction['entities'])} entities:")
        for entity in extraction['entities']:
            print(f"  - {entity['text']} ({entity['label']})")

        print(f"\nExtracted {len(extraction['relations'])} relationships:")
        for rel in extraction['relations']:
            print(f"  - {rel['head']} --[{rel['relation']}]--> {rel['tail']}")

        print("\n=== Adding Session Memories ===")
        mem.add_session_memory(
            sess.id, "Researching cloud infrastructure options.", "Thought",
            {"topic": "research"},
        )
        mem.add_session_memory(
            sess.id, "Decision: proceed with hybrid cloud approach.", "Decision",
            {"topic": "architecture"},
        )

        print("\n=== Retrieving Session Context ===")
        context = mem.focus_context(sess.id, "Apple Microsoft partnership", k=3)
        for hit in context:
            print(f"  - {hit['text'][:100]}... (distance: {hit.get('distance', 'N/A')})")

        print("\n=== Extracting Subgraph ===")
        seeds = mem.graph.list_subgraph_seeds()
        if seeds['entity_ids']:
            subgraph = mem.extract_subgraph(seeds['entity_ids'][:3], depth=2)
            print(
                f"Subgraph: {len(subgraph['nodes'])} nodes, "
                f"{len(subgraph['rels'])} relationships"
            )

        print("\n=== Ending Session ===")
        mem.end_session(sess.id)
        print("Session ended.")

    finally:
        mem.close()
        print("\n=== Memory system closed ===")

"""
  # ── USAGE EXAMPLES ───────────────────────────────────────────────────────

    # 1. Local file store (default — no change required for existing callers)
    mem = HybridMemory(
        neo4j_uri=NEO4J_URI,
        neo4j_user=NEO4J_USER,
        neo4j_password=NEO4J_PASSWORD,
        chroma_dir="./Memory/chroma_store",
    )

    # 2. Remote Chroma server
    mem = HybridMemory(
        neo4j_uri=NEO4J_URI,
        neo4j_user=NEO4J_USER,
        neo4j_password=NEO4J_PASSWORD,
        chroma_dir="./Memory/chroma_store",   # still used for fallback path
        vector_backend="chroma_http",
        chroma_host="my-chroma-server",
        chroma_port=8000,
        # chroma_ssl=True,                    # uncomment for HTTPS
        # chroma_headers={"Authorization": "Bearer <token>"},
    )

    # 3. Weaviate 
    mem = HybridMemory(
        neo4j_uri=NEO4J_URI,
        neo4j_user=NEO4J_USER,
        neo4j_password=NEO4J_PASSWORD,
        chroma_dir="./Memory/chroma_store",
        vector_backend="weaviate",
        weaviate_url="http://weaviate.internal:8080",
    )
"""