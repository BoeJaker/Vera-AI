#!/usr/bin/env python3
"""
Enhanced Hybrid Memory System with Dynamic NLP Extraction
Two-tier (Long-term graph + Short-term session) with Chroma vectors,
Neo4j graph database, and schema-less NLP entity/relationship extraction.

New Dependencies (install via pip):
    pip install neo4j chromadb pydantic spacy sentence-transformers sklearn
    python -m spacy download en_core_web_sm

Features:
- Dynamic entity extraction without fixed schema
- Relationship extraction using dependency parsing
- Semantic clustering for entity normalization
- Optional LLM enrichment (sparse usage)
- All extractions branch from session graph
"""
from __future__ import annotations

import json
import os
import time
import hashlib
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
import inspect
import sys

from Vera.Memory.nlp import NLPExtractor  
import hashlib
import time
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
# -----------------------------
# Data models
# -----------------------------

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
    label: str  # Discovered label (e.g., PERSON, ORG, or custom)
    span: Tuple[int, int]  # Character offsets in source text
    confidence: float = 1.0
    embedding: Optional[List[float]] = None

class ExtractedRelation(BaseModel):
    """Dynamically extracted relationship"""
    head: str  # Entity text
    tail: str  # Entity text
    relation: str  # Discovered relation type
    confidence: float = 1.0
    context: str = ""  # Sentence context

# -----------------------------
# Graph (Neo4j) client
# -----------------------------

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
        labels = ":".join(["Entity"] + node.labels)
        cypher = f"""
        MERGE (n:{labels} {{id: $id}})
        SET n.type = $type,
            n += $properties
        RETURN n
        """
        with self._driver.session() as sess:
            sess.run(cypher, {
                "id": node.id,
                "type": node.type,
                "properties": node.properties,
            })

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
        cypher = """
        MATCH (a:Entity {id: $src})
        MATCH (b:Entity {id: $dst})
        MERGE (a)-[r:REL {rel: $rel}]->(b)
        SET r += $properties
        RETURN r
        """
        with self._driver.session() as sess:
            sess.run(cypher, edge.model_dump())

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
        # Simplified version without APOC
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
        """List potential starting points for subgraphs."""
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


# -----------------------------
# Chroma client wrapper
# -----------------------------

class VectorClient:
    def __init__(self, persist_dir: str, embedding_model: str = "all-MiniLM-L6-v2"):
        os.makedirs(persist_dir, exist_ok=True)
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=embedding_model
        )

    def get_collection(self, name: str):
        return self._client.get_or_create_collection(name=name, embedding_function=self._ef)

    def add_texts(self, collection: str, ids: List[str], texts: List[str], metadatas: Optional[List[Dict[str, Any]]] = None):
        logger.debug(f"[VectorClient] Adding {len(texts)} texts to collection '{collection}'")
        col = self.get_collection(collection)
        col.add(ids=ids, documents=texts, metadatas=metadatas)

    def query(self, collection: str, text: str, n_results: int = 5, where: Optional[Dict[str, Any]] = None):
        col = self.get_collection(collection)
        kwargs = {"query_texts": [text], "n_results": n_results}
        if where:
            kwargs["where"] = where
        return col.query(**kwargs)

    def delete(self, collection: str, ids: List[str]):
        col = self.get_collection(collection)
        col.delete(ids=ids)


# -----------------------------
# JSONL Archive
# -----------------------------

class Archive:
    def __init__(self, jsonl_path: Optional[str] = None):
        self.path = jsonl_path
        if self.path:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)

    def write(self, record: Dict[str, Any]):
        logger.debug(f"[Archive] Writing record to archive: {record.get('type', 'unknown')}")
        if not self.path:
            return
        record = {"ts": datetime.utcnow().isoformat(), **record}
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


# -----------------------------
# LLM Enrichment Interface (Stubs)
# -----------------------------

class LLMEnrichment:
    """
    Optional LLM enrichment for entity normalization, relationship expansion,
    and contextual metadata. Uses Ollama endpoint.
    """
    
    def __init__(self, ollama_endpoint: str = "http://localhost:11434", model: str = "mistral:7b"):
        self.endpoint = ollama_endpoint
        self.model = model
    
    def normalize_entities(self, entities: List[ExtractedEntity]) -> Dict[str, str]:
        """
        Stub: Use LLM to normalize entity variants.
        Returns mapping of {original_text: normalized_text}
        """
        # TODO: Implement LLM call to normalize entities
        # Example: "IBM" -> "International Business Machines"
        return {e.text: e.text for e in entities}
    
    def expand_relationships(self, relations: List[ExtractedRelation], context: str) -> List[ExtractedRelation]:
        """
        Stub: Use LLM to infer implicit relationships from context.
        """
        # TODO: Implement LLM call to suggest additional relations
        return relations
    
    def add_contextual_metadata(self, entity: ExtractedEntity, context: str) -> Dict[str, Any]:
        """
        Stub: Use LLM to generate descriptive metadata for entities.
        """
        # TODO: Implement LLM call to generate entity attributes
        return {"description": f"Entity: {entity.text}"}
    
    def validate_relationships(self, relations: List[ExtractedRelation]) -> List[ExtractedRelation]:
        """
        Stub: Use LLM to validate and flag inconsistent relationships.
        """
        # TODO: Implement LLM validation
        return [r for r in relations if r.confidence > 0.5]
    
    def generate_summary(self, subgraph: Dict[str, Any]) -> str:
        """
        Stub: Generate natural language summary of subgraph.
        """
        # TODO: Implement LLM summarization
        n_nodes = len(subgraph.get("nodes", []))
        n_rels = len(subgraph.get("rels", []))
        return f"Subgraph with {n_nodes} entities and {n_rels} relationships."
    
    def infer_relationships(self, entity_a: str, entity_b: str, context: str) -> Optional[str]:
        """
        Stub: Use LLM to infer relationship type between two entities.
        """
        # TODO: Implement LLM inference
        return "RELATED_TO"


# -----------------------------
# Enhanced Hybrid Memory API
# -----------------------------

class HybridMemory:
    """
    Enhanced two-tier hybrid memory with dynamic NLP extraction.
    """

    def __init__(
        self,
        neo4j_uri: str,
        neo4j_user: str,
        neo4j_password: str,
        chroma_dir: str,
        archive_jsonl: Optional[str] = None,
        enable_llm_enrichment: bool = False,
        ollama_endpoint: str = "http://localhost:11434",
    ):
        self.graph = GraphClient(neo4j_uri, neo4j_user, neo4j_password)
        self.vec = VectorClient(chroma_dir)
        self.archive = Archive(archive_jsonl)
        self.nlp = NLPExtractor()
        self.embedding_llm = "mistral:7b"
        self.previous_memory = None
        self.previous_session_id = None
        
        # Optional LLM enrichment
        self.enable_llm_enrichment = enable_llm_enrichment
        if enable_llm_enrichment:
            self.llm_enrichment = LLMEnrichment(ollama_endpoint)
        else:
            self.llm_enrichment = None

    # -------- Sessions (Tier 2) --------
    def start_session(self, session_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Session:
        sid = session_id or f"sess_{int(time.time()*1000)}"
        sess = Session(id=sid, started_at=datetime.utcnow().isoformat(), metadata=metadata or {})
        self.graph.upsert_session(sess)
        self.archive.write({"type": "session_start", "session": sess.model_dump()})
        return sess

    def end_session(self, session_id: str):
        self.graph.end_session(session_id)
        self.archive.write({"type": "session_end", "session_id": session_id})

    def add_session_memory(self, session_id: str, text: str, node_type: str, metadata: Optional[Dict[str, Any]] = None, *, labels: Optional[List[str]]=None, promote: bool = False, auto_extract: bool = True) -> MemoryItem:
        if labels is None:
            labels = [node_type.capitalize()]
        mem_id = f"mem_{int(time.time()*1000)}"
        
        item = MemoryItem(id=mem_id, text=text, metadata=metadata or {}, tier="session")
        logger.debug(f"[HybridMemory] Adding session memory {item.id} to session {session_id}")
        collection = f"session_{session_id}"
        self.vec.add_texts(collection, [item.id], [item.text], [item.metadata])
        
        node = Node(id=item.id, type=node_type, labels=labels, properties={"text": item.text, "created_at": datetime.now().isoformat(), "session_id": session_id, **item.metadata})
        self.graph.upsert_entity(node)
       
        if self.previous_memory and self.previous_session_id == session_id:
            self.link(item.id, self.previous_memory.id, "FOLLOWS", {"source": self.previous_memory.id})
        
        self.previous_session_id = session_id
        self.previous_memory = item

        # Automatic NLP extraction on every node
        if auto_extract and len(text.strip()) > 20:  # Skip very short text
            extraction = self.extract_and_link(session_id, text, auto_promote=False)
            # Link extracted entities to this memory node
            for entity in extraction.get('entities', []):
                logger.debug(entity)
                self.link(item.id, entity['id'], "MENTIONS_ENTITY")
            for relation in extraction.get('relations', []):
                logger.debug(relation)
                self.link( relation['head_id'], relation['tail_id'], relation['relation'])

        if promote:
            self.promote_session_memory_to_long_term(item)
        
        self.archive.write({"type": "session_memory", "session_id": session_id, "memory": item.model_dump()})
        return item
   
    def extract_and_link(self, session_id: str, text: str, source_node_id: Optional[str] = None, 
                    auto_promote: bool = False) -> Dict[str, Any]:
        """
        Extract entities and relationships from text, link to session graph.
        OPTIMIZED: Uses entity IDs directly from extraction, no text-based lookup needed.
        
        Args:
            session_id: Current session ID
            text: Text to analyze
            source_node_id: ID of source node (message, document) that entities came from
            auto_promote: If True, promote high-confidence extractions to long-term
            
        Returns:
            Dict with extracted entities and relationships
        """
        logger.debug(f"[HybridMemory] Extracting and linking entities/relations for session {session_id}")
        try:
            # Extract entities and relations (now with IDs!)
            logger.debug(f"Extracting from text: {text[:100]}...")
            entities, relations = self.nlp.extract_all(text)
            logger.info(f"Extracted {len(entities)} entities and {len(relations)} relations")
            # logger.info(f"Sample entities: {[(e.entity_id, e.text, e.label) for e in entities[:3]]}")
            
            # Safety check
            if not entities:
                logger.warning("No entities extracted from text")
                return {"entities": [], "relations": [], "clusters": {}}
            
            # Ensure all entities have IDs
            for entity in entities:
                if not hasattr(entity, 'entity_id') or not entity.entity_id:
                    entity.entity_id = entity.get_stable_id()
            
            # Optional LLM normalization (but don't apply to CODE_BLOCK or unique IDs)
            if self.enable_llm_enrichment and self.llm_enrichment:
                try:
                    natural_entities = [e for e in entities if e.label not in [
                        'CODE_BLOCK', 'CLASS', 'METHOD', 'FUNCTION', 'IMPORT', 'IMPORT_FROM'
                    ]]
                    if natural_entities:
                        entity_map = self.llm_enrichment.normalize_entities(natural_entities)
                    else:
                        entity_map = {}
                except Exception as e:
                    logger.warning(f"LLM normalization failed: {e}, using fallback")
                    entity_map = {}
            else:
                entity_map = {}
            
            # Cluster entities (but don't cluster code artifacts)
            try:
                non_clusterable_labels = {
                    'CODE_BLOCK', 'CLASS', 'METHOD', 'FUNCTION', 'IMPORT', 'IMPORT_FROM',
                    'URL', 'EMAIL', 'UUID', 'HASH_MD5', 'HASH_SHA1', 'HASH_SHA256',
                    'TERMINAL_COMMAND', 'FILE_PATH', 'IPV4', 'IPV6'
                }
                
                clusterable = [e for e in entities if e.label not in non_clusterable_labels]
                non_clusterable = [e for e in entities if e.label in non_clusterable_labels]
                
                if clusterable and any(e.embedding for e in clusterable):
                    clustered = self.nlp.cluster_entities(clusterable)
                else:
                    clustered = {f"cluster_{i}": [e] for i, e in enumerate(clusterable)}
                
                clusters = clustered.copy()
                for i, entity in enumerate(non_clusterable):
                    clusters[f"non_clusterable_{i}"] = [entity]
                
                logger.debug(f"Created {len(clusters)} clusters ({len(non_clusterable)} non-clusterable)")
                
            except Exception as e:
                logger.warning(f"Clustering failed: {e}, using individual entities")
                clusters = {f"cluster_{i}": [e] for i, e in enumerate(entities)}
            
            # Create entity nodes - NO LOOKUP NEEDED, use entity.entity_id directly!
            created_entities = []
            entity_id_to_object = {}  # For quick lookups if needed
            
            for cluster_id, cluster in clusters.items():
                if not cluster:
                    continue
                
                try:
                    entity = cluster[0]
                    
                    # Use normalized text for natural entities, original for code
                    if entity.label in ['CODE_BLOCK', 'CLASS', 'METHOD', 'FUNCTION', 'IMPORT', 'IMPORT_FROM']:
                        canonical = entity.text
                    else:
                        canonical = entity_map.get(entity.text, entity.text)
                        if not canonical:
                            canonical = self.nlp.normalize_entity(entity, cluster)
                    
                    if not canonical or not canonical.strip():
                        continue
                    
                    # Use the entity_id that was assigned during extraction
                    graph_entity_id = f"entity_{entity.entity_id}"
                    
                    # Store for later reference
                    entity_id_to_object[entity.entity_id] = entity
                    entity_id_to_object[graph_entity_id] = entity
                    
                    label = entity.label if hasattr(entity, 'label') else "UNKNOWN"
                    confidence = entity.confidence if hasattr(entity, 'confidence') else 0.5
                    
                    # Prepare metadata
                    metadata = {
                        "text": canonical,
                        "original_text": entity.text,
                        "confidence": confidence,
                        "extracted_from_session": session_id,
                        "variants": list(set([e.text for e in cluster if e.text])),
                        "cluster_id": cluster_id,
                        "span": entity.span,
                        "extraction_id": entity.entity_id  # Store original ID
                    }
                    
                    if source_node_id:
                        metadata["source_node_id"] = source_node_id
                    
                    if hasattr(entity, 'metadata') and entity.metadata:
                        metadata.update({
                            k: v for k, v in entity.metadata.items()
                            if k not in metadata and isinstance(v, (str, int, float, bool, list, dict))
                        })
                    
                    # Create node
                    node = Node(
                        id=graph_entity_id,
                        type="extracted_entity",
                        labels=["ExtractedEntity", label],
                        properties=metadata
                    )
                    self.graph.upsert_entity(node)
                    
                    # Link to session
                    self.graph.link_session_to_entity(session_id, graph_entity_id, "EXTRACTED_IN")
                    
                    # Link to source node if provided
                    if source_node_id:
                        source_edge = Edge(
                            src=graph_entity_id,
                            dst=source_node_id,
                            rel="EXTRACTED_FROM",
                            properties={
                                "extraction_type": label,
                                "confidence": confidence,
                                "span": entity.span
                            }
                        )
                        self.graph.upsert_edge(source_edge)
                    
                    created_entities.append({
                        "id": graph_entity_id,
                        "extraction_id": entity.entity_id,
                        "text": canonical,
                        "label": label,
                        "confidence": confidence,
                        "span": entity.span
                    })
                    
                    logger.debug(f"Created entity: {graph_entity_id} = {canonical} ({label})")
                    
                except Exception as e:
                    logger.error(f"Error creating entity from cluster {cluster_id}: {e}", exc_info=True)
                    continue
            
            logger.info(f"Created {len(created_entities)} entity nodes")
            
            # Optional LLM expansion
            if self.enable_llm_enrichment and self.llm_enrichment:
                try:
                    relations = self.llm_enrichment.expand_relationships(relations, text)
                except Exception as e:
                    logger.warning(f"LLM relation expansion failed: {e}")
            
            # Create relationship edges - USE IDs DIRECTLY!
            created_relations = []
            skipped_relations = []
            
            for idx, rel in enumerate(relations):
                try:
                    if not rel.head or not rel.tail:
                        skipped_relations.append(("empty_head_tail", rel.head, rel.tail))
                        continue
                    
                    # CRITICAL: Use the IDs that were set during extraction
                    if hasattr(rel, 'head_id') and rel.head_id:
                        head_id = f"entity_{rel.head_id}"
                    else:
                        # Fallback: find entity by text (should rarely happen now)
                        logger.warning(f"Relation missing head_id, falling back to text lookup: {rel.head}")
                        matching = [e for e in created_entities if e["text"] == rel.head or e.get("original_text") == rel.head]
                        if matching:
                            head_id = matching[0]["id"]
                        else:
                            skipped_relations.append(("missing_head_id", rel.head, rel.tail))
                            continue
                    
                    if hasattr(rel, 'tail_id') and rel.tail_id:
                        tail_id = f"entity_{rel.tail_id}"
                    else:
                        logger.warning(f"Relation missing tail_id, falling back to text lookup: {rel.tail}")
                        matching = [e for e in created_entities if e["text"] == rel.tail or e.get("original_text") == rel.tail]
                        if matching:
                            tail_id = matching[0]["id"]
                        else:
                            skipped_relations.append(("missing_tail_id", rel.head, rel.tail))
                            continue
                    
                    logger.debug(f"Relation #{idx}: {head_id} --[{rel.relation}]--> {tail_id}")
                    
                    # Create edge
                    confidence = rel.confidence if hasattr(rel, 'confidence') else 0.5
                    context = rel.context if hasattr(rel, 'context') else ""
                    relation_type = rel.relation if hasattr(rel, 'relation') else "RELATED_TO"
                    
                    edge = Edge(
                        src=head_id,
                        dst=tail_id,
                        rel=relation_type,
                        properties={
                            "confidence": confidence,
                            "context": context[:500] if context else "",
                            "extracted_from_session": session_id,
                            "head_text": rel.head,
                            "tail_text": rel.tail,
                            "metadata": rel.metadata if hasattr(rel, 'metadata') else {}
                        }
                    )
                    self.link(tail_id, head_id, relation_type, edge.properties)
                    # self.graph.upsert_edge(edge)
                    
                    created_relations.append({
                        "head": rel.head,
                        "tail": rel.tail,
                        "relation": relation_type,
                        "confidence": confidence,
                        "head_id": head_id,
                        "tail_id": tail_id
                    })
                    
                    logger.debug(f"✓ Created relation: {rel.head} --[{relation_type}]--> {rel.tail}")
                    
                except Exception as e:
                    logger.error(f"Error creating relation: {e}", exc_info=True)
                    skipped_relations.append(("error", rel.head, rel.tail))
                    continue
            
            logger.info(f"Created {len(created_relations)} relationship edges")
            if skipped_relations:
                logger.info(f"Skipped {len(skipped_relations)} relations:")
                for reason, head, tail in skipped_relations[:10]:
                    logger.info(f"  {reason}: {head} -> {tail}")
            
            # Optional promotion
            if auto_promote:
                try:
                    high_conf_entities = [e for e in entities if hasattr(e, 'confidence') and e.confidence > 0.8]
                    for entity in high_conf_entities:
                        if not entity.text or not entity.text.strip():
                            continue
                        
                        graph_entity_id = f"entity_{entity.entity_id}"
                        label = entity.label if hasattr(entity, 'label') else "UNKNOWN"
                        
                        self.vec.add_texts(
                            "long_term_docs",
                            [graph_entity_id],
                            [entity.text],
                            [{"type": "promoted_entity", "label": label}]
                        )
                    
                    logger.info(f"Promoted {len(high_conf_entities)} high-confidence entities")
                except Exception as e:
                    logger.error(f"Error during promotion: {e}", exc_info=True)
            
            # Build result
            result = {
                "entities": created_entities,
                "relations": created_relations,
                "clusters": {k: [e.text for e in v if e.text] for k, v in clusters.items()},
                "skipped_relations": len(skipped_relations),
                "source_node_id": source_node_id
            }
            
            # Archive
            try:
                self.archive.write({
                    "type": "nlp_extraction",
                    "session_id": session_id,
                    "source_node_id": source_node_id,
                    "timestamp": time.time(),
                    "extraction": result,
                    "text_length": len(text)
                })
            except Exception as e:
                logger.error(f"Error archiving extraction: {e}")
            
            return result
            
        except Exception as e:
            logger.error(f"Fatal error in extract_and_link: {e}", exc_info=True)
            return {
                "entities": [],
                "relations": [],
                "clusters": {},
                "error": str(e)
            }

    def link_to_session(self, session_id: str, entity_id: str, rel: str = "HAS_MEMORY"):
        self.graph.link_session_to_entity(session_id, entity_id, rel)

    def get_session_memory(self, session_id: str) -> List[MemoryItem]:
        collection = f"session_{session_id}"
        res = self.vec.get_collection(collection).get()
        hits = []
        if res and res.get("ids"):
            for i, item_id in enumerate(res["ids"]):
                hits.append(MemoryItem(
                    id=item_id,
                    text=res["documents"][i],
                    metadata=res["metadatas"][i] if res.get("metadatas") else {}
                ))
        return hits
    
    def list_sessions(self) -> List[Session]:
        result = []
        with self.graph._driver.session() as sess:
            rec = sess.run("MATCH (s:Session) RETURN s.id AS id, s.started_at AS started_at, s.ended_at AS ended_at, s.metadata AS metadata")
            for r in rec:
                result.append(Session(
                    id=r["id"],
                    started_at=r["started_at"],
                    ended_at=r.get("ended_at"),
                    metadata=r.get("metadata", {})
                ))
        return result
    
    def focus_context(self, session_id: str, query: str, k: int = 8) -> List[Dict[str, Any]]:
        res = self.vec.query(collection=f"session_{session_id}", text=query, n_results=k)
        hits = []
        if res and res.get("ids"):
            for i, ids in enumerate(res["ids"][0]):
                hits.append({
                    "id": ids,
                    "text": res["documents"][0][i],
                    "metadata": res["metadatas"][0][i],
                    "distance": res["distances"][0][i] if "distances" in res else None,
                })
        self.archive.write({"type": "session_focus", "session_id": session_id, "query": query, "results": hits})
        return hits
    
    # -------- Long-term (Tier 1) --------
    def upsert_entity(self, entity_id: str, etype: str, labels: Optional[List[str]] = None, properties: Optional[Dict[str, Any]] = None):
        """Upsert an entity node in the long-term graph."""
        if "source_process" not in (properties or {}):
            if properties is None:
                properties = {}
            caller_file = inspect.stack()[2].filename  # Get the file of the calling function
            properties["source_process"] = f"{os.path.basename(caller_file)}:{sys._getframe(1).f_code.co_name}"

        node = Node(id=entity_id, type=etype, labels=labels or [], properties=properties or {})
        self.graph.upsert_entity(node)
        self.archive.write({"type": "entity_upsert", "node": node.model_dump()})
        return node
    
    def link(self, src: str, dst: str, rel: str, properties: Optional[Dict[str, Any]] = None):
        # logger.info(f"[MEMORY] Linking {src} -[{rel}]-> {dst}")
        edge = Edge(src=src, dst=dst, rel=rel, properties=properties or {})
        self.graph.upsert_edge(edge)
        self.archive.write({"type": "edge_upsert", "edge": edge.model_dump()})

    def link_by_property(self, src_property: str, src_value: Any, dst_property: str, dst_value: Any, rel: str, properties: Optional[Dict[str, Any]] = None):
        """
        Link nodes based on a property value instead of explicit IDs.

        Args:
            src_property: Property name to identify the source node.
            src_value: Value of the property for the source node.
            dst_property: Property name to identify the destination node.
            dst_value: Value of the property for the destination node.
            rel: Relationship type.
            properties: Additional properties for the relationship.
        """
        logger.info(f"[MEMORY] Linking nodes where {src_property}={src_value} -[{rel}]-> {dst_property}={dst_value}")
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
                "properties": properties or {}
            })
        self.archive.write({
            "type": "edge_upsert_by_property",
            "src_property": src_property,
            "src_value": src_value,
            "dst_property": dst_property,
            "dst_value": dst_value,
            "rel": rel,
            "properties": properties or {}
        })

    def attach_document(self, entity_id: str, doc_id: str, text: str, metadata: Optional[Dict[str, Any]] = None):
        """Add unstructured content to Chroma and link it in the graph as a Document node."""
        logger.info(f"[MEMORY] Attaching document {doc_id} to entity {entity_id}")
        meta = {"entity_id": entity_id, **(metadata or {})}
        self.vec.add_texts(collection="long_term_docs", ids=[doc_id], texts=[text], metadatas=[meta])
        doc_node = Node(id=doc_id, type="document", labels=["Document"], properties=meta)
        self.graph.upsert_entity(doc_node)
        self.link(entity_id, doc_id, "HAS_DOCUMENT")
        self.archive.write({"type": "document_attach", "entity_id": entity_id, "doc_id": doc_id, "meta": meta})
        return doc_node
    
    def semantic_retrieve(self, query: str, k: int = 8, where: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        res = self.vec.query(collection="long_term_docs", text=query, n_results=k, where=where)
        hits = []
        if res and res.get("ids"):
            for i, ids in enumerate(res["ids"][0]):
                hits.append({
                    "id": ids,
                    "text": res["documents"][0][i],
                    "metadata": res["metadatas"][0][i],
                    "distance": res["distances"][0][i] if "distances" in res else None,
                })
        self.archive.write({"type": "semantic_retrieve", "query": query, "results": hits})
        return hits

    def promote_session_memory_to_long_term(self, item: MemoryItem, entity_anchor: Optional[str] = None):
        """Promote a session memory item into long-term."""
        self.vec.add_texts(
            collection="long_term_docs",
            ids=[item.id],
            texts=[item.text],
            metadatas=[{"promoted": True, **item.metadata}],
        )
        node = Node(id=item.id, type="thought", labels=["Thought", "Promoted"], properties={"promoted": True, **item.metadata, "text": item.text})
        self.graph.upsert_entity(node)
        if entity_anchor:
            self.link(entity_anchor, item.id, "HAS_THOUGHT")
        self.archive.write({"type": "promotion", "memory": item.model_dump(), "anchor": entity_anchor})

    def link_session_focus(self, session_id: str, entity_ids: List[str]):
        for eid in entity_ids:
            self.graph.link_session_to_entity(session_id, eid)
        self.archive.write({"type": "session_focus_link", "session_id": session_id, "entities": entity_ids})

    def extract_subgraph(self, seed_entity_ids, depth=2):
        """Extract subgraph around seed entities."""
        return self.graph.get_subgraph(seed_entity_ids, depth=depth)

    def store_file(self, file_path, chunk_size=1000, chunk_overlap=100):
        """Store a file in the hybrid memory system."""
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"File {file_path} not found")

        file_name = os.path.basename(file_path)
        file_id = f"file_{hash(file_path) & 0xffffffff}"

        # Create Neo4j node for metadata
        file_node = Node(id=file_id, type="file", labels=["File"], properties={"name": file_name, "path": file_path})
        self.graph.upsert_entity(file_node)

        # Read file content
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()

        # Split into chunks
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        chunks = splitter.split_text(text)

        # Add to vector store
        ids = [f"{file_id}_{i}" for i in range(len(chunks))]
        metadatas = [{"file_id": file_id, "chunk_index": i} for i in range(len(chunks))]
        self.vec.add_texts("long_term_docs", ids=ids, texts=chunks, metadatas=metadatas)

        return file_id

    def retrieve_file(self, file_id, query=None, top_k=5):
        """Retrieve file content or top relevant chunks."""
        # Get file path from Neo4j
        with self.graph._driver.session() as sess:
            rec = sess.run(
                "MATCH (n:File {id: $id}) RETURN n.path AS path",
                id=file_id
            ).single()
            if not rec:
                raise ValueError(f"No file with ID {file_id} found")
            file_path = rec["path"]
        
        # Read full file content
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            full_text = f.read()
        
        if query is None:
            return {"file_path": file_path, "full_text": full_text}
        
        # Semantic search on chunks
        hits = self.semantic_retrieve(query, k=top_k)
        relevant_chunks = [hit for hit in hits if hit["metadata"].get("file_id") == file_id]
        
        return {"file_path": file_path, "relevant_chunks": relevant_chunks}

    # -------- Cleanup --------
    def close(self):
        self.graph.close()


# -----------------------------
# Example usage
# -----------------------------

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
        enable_llm_enrichment=False  # Set to True to enable LLM enrichment
    )

    try:
        # Start a session
        print("=== Starting Session ===")
        sess = mem.start_session(metadata={"agent": "nlp_test"})
        print(f"Session ID: {sess.id}")
        
        # Add session memory with NLP extraction
        print("\n=== Testing NLP Extraction ===")
        test_text = """
        Apple Inc. announced a new partnership with Microsoft Corporation.
        Tim Cook, CEO of Apple, will meet with Satya Nadella next week.
        The collaboration focuses on AI and cloud computing technologies.
        """
        
        # Extract entities and relationships
        extraction = mem.extract_and_link(sess.id, test_text, auto_promote=False)
        print(f"\nExtracted {len(extraction['entities'])} entities:")
        for entity in extraction['entities']:
            print(f"  - {entity['text']} ({entity['label']})")
        
        print(f"\nExtracted {len(extraction['relations'])} relationships:")
        for rel in extraction['relations']:
            print(f"  - {rel['head']} --[{rel['relation']}]--> {rel['tail']}")
        
        # Add regular session memory
        print("\n=== Adding Session Memories ===")
        mem.add_session_memory(sess.id, "Researching cloud infrastructure options.", "Thought", {"topic": "research"})
        mem.add_session_memory(sess.id, "Decision: proceed with hybrid cloud approach.", "Decision", {"topic": "architecture"})
        
        # Retrieve session context
        print("\n=== Retrieving Session Context ===")
        context = mem.focus_context(sess.id, "Apple Microsoft partnership", k=3)
        for hit in context:
            print(f"  - {hit['text'][:100]}... (distance: {hit.get('distance', 'N/A')})")
        
        # Extract subgraph
        print("\n=== Extracting Subgraph ===")
        seeds = mem.graph.list_subgraph_seeds()
        if seeds['entity_ids']:
            subgraph = mem.extract_subgraph(seeds['entity_ids'][:3], depth=2)
            print(f"Subgraph: {len(subgraph['nodes'])} nodes, {len(subgraph['rels'])} relationships")
        
        # Test file storage with NLP
        print("\n=== Testing File Storage ===")
        # Create a test file
        test_file_path = "./Memory/test_doc.txt"
        os.makedirs(os.path.dirname(test_file_path), exist_ok=True)
        with open(test_file_path, "w") as f:
            f.write("This is a test document about machine learning and AI research.")
        
        file_id = mem.store_file(test_file_path)
        print(f"Stored file with ID: {file_id}")
        
        # Retrieve with semantic query
        result = mem.retrieve_file(file_id, query="machine learning", top_k=2)
        print(f"Relevant chunks: {len(result.get('relevant_chunks', []))}")
        
        # End session
        print("\n=== Ending Session ===")
        mem.end_session(sess.id)
        print("Session ended.")
        
    finally:
        mem.close()
        print("\n=== Memory system closed ===")


"""
Installation commands:
    pip install neo4j chromadb pydantic spacy sentence-transformers scikit-learn langchain langchain-community
    python -m spacy download en_core_web_sm

Docker Neo4j:
    docker run --name neo4j -p7474:7474 -p7687:7687 -d -e NEO4J_AUTH=neo4j/testpassword neo4j:5.22
    docker start neo4j
"""