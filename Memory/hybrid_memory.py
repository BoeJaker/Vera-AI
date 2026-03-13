#!/usr/bin/env python3
# Vera/Memory/hybrid_vector_store.py
"""
HybridVectorStore — unified vector+graph bridge for Vera's memory system.

Changes vs previous version
----------------------------
- ``backend`` now accepts ``"chroma_http"`` in addition to ``"chroma"`` and
  ``"weaviate"``.  Pass ``chroma_host`` / ``chroma_port`` (and optionally
  ``chroma_ssl``, ``chroma_headers``, ``chroma_tenant``, ``chroma_database``)
  to connect to a remote Chroma server.

- Backend construction is now delegated to ``BackendFactory.create_pair()``,
  which de-duplicates the per-backend init logic and keeps this file focused
  on the routing / graph-bridging layer.

- All existing callers that pass ``backend="chroma"`` (or nothing) continue
  to work identically — no migration required on their end.

New HybridMemory usage (chroma_http)
--------------------------------------
    mem = HybridMemory(
        ...
        vector_memory="chroma_http",
        chroma_host="my-chroma-server",
        chroma_port=8000,
        chroma_ssl=False,
        chroma_headers={"Authorization": "Bearer <token>"},   # optional
    )
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _cosine_similarity(a: List[float], b: List[float]) -> float:
    try:
        import numpy as np
        va, vb = np.array(a, dtype=float), np.array(b, dtype=float)
        denom = np.linalg.norm(va) * np.linalg.norm(vb)
        return float(np.dot(va, vb) / denom) if denom > 0 else 0.0
    except ImportError:
        dot = sum(x * y for x, y in zip(a, b))
        na  = sum(x * x for x in a) ** 0.5
        nb  = sum(x * x for x in b) ** 0.5
        return dot / (na * nb) if na * nb > 0 else 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Backward-compat shim for old get_collection() callers
# ─────────────────────────────────────────────────────────────────────────────

class _CollectionShim:
    """
    Thin adapter so code that did ``self.vec.get_collection(name).query(...)``
    or ``get_collection(name).get()`` still works.
    """

    def __init__(self, store: "HybridVectorStore", logical_name: str):
        self._store = store
        self._name  = logical_name

    def _where(self) -> Optional[Dict[str, Any]]:
        if self._name.startswith("session_"):
            sid = self._name[len("session_"):]
            return {"session_id": {"$eq": sid}}
        return None

    def add(
        self,
        ids: List[str],
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ):
        self._store.add_texts(self._name, ids, documents, metadatas)

    def upsert(
        self,
        ids: List[str],
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ):
        self._store.add_texts(self._name, ids, documents, metadatas)

    def query(
        self,
        query_texts: List[str],
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        effective_where = where or self._where()
        text = query_texts[0] if query_texts else ""
        hits = self._store.query(self._name, text, n_results=n_results, where=effective_where)
        return {
            "ids":       [[h["id"]   for h in hits]],
            "documents": [[h["text"] for h in hits]],
            "metadatas": [[h.get("metadata", {}) for h in hits]],
            "distances": [[h.get("distance")     for h in hits]],
        }

    def get(
        self,
        where: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        effective_where = where or self._where()
        hits = self._store._backend.get_all(where=effective_where)
        return {
            "ids":       [h["id"]   for h in hits],
            "documents": [h["text"] for h in hits],
            "metadatas": [h.get("metadata", {}) for h in hits],
        }

    def delete(self, ids: List[str]):
        self._store._backend.delete(ids)


# ─────────────────────────────────────────────────────────────────────────────
# HybridVectorStore
# ─────────────────────────────────────────────────────────────────────────────

class HybridVectorStore:
    """
    Unified vector store with Neo4j write-back.

    Parameters
    ----------
    persist_dir : str
        Directory for local ChromaDB (ignored for chroma_http / weaviate).
    embedding_function : callable
        ChromaDB-compatible embedding function OR any callable that accepts
        List[str] and returns List[List[float]].
    graph_driver : neo4j.Driver | None
        If provided, embeddings are written back to Neo4j nodes.
    backend : "chroma" | "chroma_http" | "weaviate"
        Which backend to use.  Default ``"chroma"`` (local file store).
    chroma_host : str
        Remote Chroma server host.  Required when backend="chroma_http".
    chroma_port : int
        Remote Chroma server port (default 8000).
    chroma_ssl : bool
        Use HTTPS for remote Chroma (default False).
    chroma_headers : dict | None
        Extra HTTP headers for remote Chroma (e.g. auth token).
    chroma_tenant : str
        Chroma multi-tenant tenant (default "default_tenant").
    chroma_database : str
        Chroma database name (default "default_database").
    weaviate_url : str
        Weaviate endpoint URL.  Required when backend="weaviate".
    weaviate_api_key : str | None
        Optional Weaviate API key.
    weaviate_class : str
        Weaviate class name (default "VeraMemory").
    write_embeddings_to_graph : bool
        Whether to write vector embeddings back to Neo4j nodes (default True).
    """

    _SESSION_COL  = "vera_memory"
    _LONGTERM_COL = "long_term_docs"

    def __init__(
        self,
        persist_dir: str,
        embedding_function,
        graph_driver=None,
        backend: str = "chroma",
        # chroma_http options
        chroma_host: str = "localhost",
        chroma_port: int = 8000,
        chroma_ssl: bool = False,
        chroma_headers: Optional[Dict[str, str]] = None,
        chroma_tenant: str = "default_tenant",
        chroma_database: str = "default_database",
        # weaviate options
        weaviate_url: str = "http://localhost:8080",
        weaviate_api_key: Optional[str] = None,
        weaviate_class: str = "VeraMemory",
        write_embeddings_to_graph: bool = True,
    ):
        self._ef = embedding_function
        self._graph_driver = graph_driver
        self._write_embeddings = write_embeddings_to_graph and graph_driver is not None
        self._backend_name = backend

        # ── Build backend pair via BackendFactory ──────────────────────────
        from Vera.Memory.vector_memory import BackendFactory  # type: ignore

        if backend == "chroma":
            cfg = {"type": "chroma", "persist_dir": persist_dir}

        elif backend == "chroma_http":
            cfg = {
                "type":     "chroma_http",
                "host":     chroma_host,
                "port":     chroma_port,
                "ssl":      chroma_ssl,
                "tenant":   chroma_tenant,
                "database": chroma_database,
            }
            if chroma_headers:
                cfg["headers"] = chroma_headers

        elif backend == "weaviate":
            cfg = {
                "type":       "weaviate",
                "url":        weaviate_url,
                "api_key":    weaviate_api_key,
                "class_name": weaviate_class,
            }

        else:
            raise ValueError(
                f"[HybridVectorStore] Unknown backend '{backend}'. "
                f"Choose from: chroma, chroma_http, weaviate"
            )

        self._backend, self._lt_backend = BackendFactory.create_pair(cfg, embedding_function)

        logger.info(
            f"[HybridVectorStore] backend='{backend}' "
            f"graph_writeback={'enabled' if self._write_embeddings else 'disabled'}"
        )

    # ──────────────────────────────────────────────────────────────────────
    # Routing helpers
    # ──────────────────────────────────────────────────────────────────────

    def _route(self, collection: str):
        if (
            collection == "long_term_docs"
            or collection.startswith("long_term_")
            or collection.startswith("promoted_")
        ):
            return self._lt_backend
        return self._backend

    def _effective_where(
        self, collection: str, extra_where: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        if collection.startswith("session_"):
            sid = collection[len("session_"):]
            session_filter: Dict[str, Any] = {"session_id": {"$eq": sid}}
            if extra_where:
                return {"$and": [session_filter, extra_where]}
            return session_filter
        return extra_where

    # ──────────────────────────────────────────────────────────────────────
    # Core API
    # ──────────────────────────────────────────────────────────────────────

    def add_texts(
        self,
        collection: str,
        ids: List[str],
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        metas = [dict(m) if m else {} for m in (metadatas or [{}] * len(ids))]

        if collection.startswith("session_"):
            sid = collection[len("session_"):]
            for m in metas:
                m.setdefault("session_id", sid)
                m.setdefault("collection", "vera_memory")
        else:
            for m in metas:
                m.setdefault("collection", collection)

        self._route(collection).add(ids, texts, metas)

        if self._write_embeddings:
            threading.Thread(
                target=self._write_embeddings_to_graph,
                args=(ids, texts, metas),
                daemon=True,
                name="vec_graph_writeback",
            ).start()

    def query(
        self,
        collection: str,
        text: str,
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        effective = self._effective_where(collection, where)
        return self._route(collection).query(text, n_results=n_results, where=effective)

    def delete(self, collection: str, ids: List[str]) -> None:
        self._route(collection).delete(ids)

    # ──────────────────────────────────────────────────────────────────────
    # Backward-compat: get_collection() shim
    # ──────────────────────────────────────────────────────────────────────

    def get_collection(self, name: str) -> _CollectionShim:
        return _CollectionShim(self, name)

    # ──────────────────────────────────────────────────────────────────────
    # Graph-aware lookups  (unchanged)
    # ──────────────────────────────────────────────────────────────────────

    def query_near_node(
        self,
        node_id: str,
        n_results: int = 5,
        collection: str = "vera_memory",
        session_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if not self._graph_driver:
            return []

        node_embedding = self._get_node_embedding(node_id)
        if not node_embedding:
            return []

        backend = self._route(collection)
        where = self._effective_where(collection, None)
        if session_id:
            sess_filter: Dict[str, Any] = {"session_id": {"$eq": session_id}}
            where = {"$and": [sess_filter, where]} if where else sess_filter

        return self._query_by_vector(backend, node_embedding, n_results, where)

    def get_node_neighbours_by_vector(
        self,
        node_id: str,
        n_hops: int = 2,
        k_per_hop: int = 3,
        session_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if not self._graph_driver:
            return []

        neighbour_ids = self._get_graph_neighbours(node_id, n_hops)
        if not neighbour_ids:
            return []

        seen_doc_ids: set = set()
        all_hits: List[Dict[str, Any]] = []

        for nid in neighbour_ids[:20]:
            hits = self.query_near_node(nid, n_results=k_per_hop, session_id=session_id)
            for h in hits:
                if h["id"] not in seen_doc_ids:
                    seen_doc_ids.add(h["id"])
                    all_hits.append(h)

        all_hits.sort(key=lambda x: x.get("distance") or 1.0)
        return all_hits

    def rerank_hits_by_graph_proximity(
        self,
        hits: List[Dict[str, Any]],
        anchor_node_ids: List[str],
        alpha: float = 0.55,
    ) -> List[Dict[str, Any]]:
        if not self._graph_driver or not anchor_node_ids:
            return hits

        anchor_embeddings: Dict[str, List[float]] = {}
        for aid in anchor_node_ids:
            emb = self._get_node_embedding(aid)
            if emb:
                anchor_embeddings[aid] = emb

        if not anchor_embeddings:
            return hits

        scored: List[Dict[str, Any]] = []
        for h in hits:
            node_id = h.get("metadata", {}).get("node_id") or h.get("id")
            node_emb = self._get_node_embedding(node_id) if node_id else None

            v_score = 1.0 - (h.get("distance") or 0.5)

            if node_emb and anchor_embeddings:
                g_score = max(
                    _cosine_similarity(node_emb, ae)
                    for ae in anchor_embeddings.values()
                )
                combined = alpha * v_score + (1.0 - alpha) * g_score
            else:
                combined = v_score
                g_score  = 0.0

            scored.append({**h, "score": combined, "vector_score": v_score, "graph_score": g_score})

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored

    # ──────────────────────────────────────────────────────────────────────
    # Graph write-back  (fire-and-forget daemon thread)
    # ──────────────────────────────────────────────────────────────────────

    def _write_embeddings_to_graph(
        self,
        ids: List[str],
        texts: List[str],
        metadatas: List[Dict[str, Any]],
    ) -> None:
        if not self._graph_driver:
            return

        try:
            vectors = self._ef(texts)
        except Exception as e:
            logger.warning(f"[HybridVectorStore] embedding for graph writeback failed: {e}")
            return

        cypher = """
        UNWIND $rows AS row
        MATCH (n {id: row.node_id})
        SET n.embedding      = row.embedding,
            n.embedding_dim  = row.dim,
            n.embedding_text = row.text
        """

        rows = []
        for doc_id, text, meta, vec in zip(ids, texts, metadatas, vectors):
            node_id = meta.get("node_id") or meta.get("id") or doc_id
            rows.append({"node_id": node_id, "embedding": vec, "dim": len(vec), "text": text[:500]})

        try:
            with self._graph_driver.session() as sess:
                result = sess.run(cypher, {"rows": rows})
                summary = result.consume()
                logger.debug(
                    f"[HybridVectorStore] graph writeback: "
                    f"{summary.counters.properties_set} properties set for {len(rows)} nodes"
                )
        except Exception as e:
            logger.debug(f"[HybridVectorStore] graph writeback failed: {e}")

    # ──────────────────────────────────────────────────────────────────────
    # Neo4j vector helpers
    # ──────────────────────────────────────────────────────────────────────

    def _get_node_embedding(self, node_id: str) -> Optional[List[float]]:
        if not self._graph_driver or not node_id:
            return None
        try:
            with self._graph_driver.session() as sess:
                rec = sess.run(
                    "MATCH (n {id: $id}) RETURN n.embedding AS emb LIMIT 1",
                    {"id": node_id},
                ).single()
                if rec and rec["emb"]:
                    return list(rec["emb"])
        except Exception as e:
            logger.debug(f"[HybridVectorStore] get_node_embedding({node_id}): {e}")
        return None

    def _get_graph_neighbours(self, node_id: str, n_hops: int) -> List[str]:
        if not self._graph_driver:
            return []
        try:
            cypher = f"""
            MATCH (start {{id: $id}})-[*1..{n_hops}]-(neighbour)
            WHERE neighbour.id IS NOT NULL
              AND neighbour.embedding IS NOT NULL
            RETURN DISTINCT neighbour.id AS nid
            LIMIT 40
            """
            with self._graph_driver.session() as sess:
                result = sess.run(cypher, {"id": node_id})
                return [rec["nid"] for rec in result if rec["nid"]]
        except Exception as e:
            logger.debug(f"[HybridVectorStore] get_graph_neighbours: {e}")
            return []

    def _query_by_vector(
        self,
        backend,
        vector: List[float],
        n_results: int,
        where: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        from Vera.Memory.vector_memory import ChromaUnifiedBackend, ChromaHttpBackend  # type: ignore

        # Both Chroma backends expose ._col directly — use query_embeddings
        if isinstance(backend, (ChromaUnifiedBackend, ChromaHttpBackend)):
            kwargs: Dict[str, Any] = {
                "query_embeddings": [vector],
                "n_results": n_results,
            }
            if where:
                kwargs["where"] = where
            try:
                res = backend._col.query(**kwargs)
                hits = []
                if res and res.get("ids"):
                    for i, doc_id in enumerate(res["ids"][0]):
                        hits.append({
                            "id":       doc_id,
                            "text":     res["documents"][0][i],
                            "metadata": (res.get("metadatas") or [[]])[0][i] if res.get("metadatas") else {},
                            "distance": (res.get("distances") or [[None]])[0][i],
                        })
                return hits
            except Exception as e:
                logger.debug(f"[HybridVectorStore] query_by_vector (chroma): {e}")
                return []

        # WeaviateBackend
        try:
            from Vera.Memory.vector_memory import WeaviateBackend  # type: ignore
            if isinstance(backend, WeaviateBackend):
                from weaviate.classes.query import MetadataQuery
                weaviate_filter = backend._translate_where(where) if where else None
                kwargs_w: Dict[str, Any] = {
                    "near_vector":     vector,
                    "limit":           n_results,
                    "return_metadata": MetadataQuery(distance=True),
                }
                if weaviate_filter:
                    kwargs_w["filters"] = weaviate_filter
                res = backend._collection.query.near_vector(**kwargs_w)
                hits = []
                for obj in res.objects:
                    raw_meta = {}
                    try:
                        raw_meta = json.loads(obj.properties.get("meta_json", "{}"))
                    except Exception:
                        pass
                    hits.append({
                        "id":       obj.properties.get("doc_id", str(obj.uuid)),
                        "text":     obj.properties.get("text", ""),
                        "metadata": raw_meta,
                        "distance": obj.metadata.distance if obj.metadata else None,
                    })
                return hits
        except Exception as e:
            logger.debug(f"[HybridVectorStore] query_by_vector (weaviate): {e}")

        return []

    # ──────────────────────────────────────────────────────────────────────
    # Neo4j vector index helpers  (unchanged)
    # ──────────────────────────────────────────────────────────────────────

    def create_neo4j_vector_index(
        self,
        label: str = "Entity",
        property_name: str = "embedding",
        dimensions: int = 768,
        similarity: str = "cosine",
    ) -> None:
        if not self._graph_driver:
            logger.warning("[HybridVectorStore] No graph driver — cannot create vector index")
            return

        index_name = f"{label.lower()}_{property_name}_idx"
        cypher = f"""
        CREATE VECTOR INDEX `{index_name}` IF NOT EXISTS
        FOR (n:{label})
        ON (n.{property_name})
        OPTIONS {{
            indexConfig: {{
                `vector.dimensions`: {dimensions},
                `vector.similarity_function`: '{similarity}'
            }}
        }}
        """
        try:
            with self._graph_driver.session() as sess:
                sess.run(cypher)
            logger.info(
                f"[HybridVectorStore] Neo4j vector index '{index_name}' created "
                f"(label={label}, dims={dimensions}, similarity={similarity})"
            )
        except Exception as e:
            logger.warning(f"[HybridVectorStore] Could not create vector index: {e}")

    def query_neo4j_vector_index(
        self,
        query_text: str,
        index_name: str,
        k: int = 10,
    ) -> List[Dict[str, Any]]:
        if not self._graph_driver:
            return []

        try:
            query_vec = self._ef([query_text])[0]
        except Exception as e:
            logger.warning(f"[HybridVectorStore] embedding for neo4j query failed: {e}")
            return []

        cypher = """
        CALL db.index.vector.queryNodes($index_name, $k, $vec)
        YIELD node, score
        RETURN node.id AS node_id,
               coalesce(node.type, labels(node)[0]) AS node_type,
               coalesce(node.text, node.name, '') AS text,
               score
        """
        try:
            with self._graph_driver.session() as sess:
                result = sess.run(cypher, {"index_name": index_name, "k": k, "vec": query_vec})
                hits = [
                    {"node_id": rec["node_id"], "node_type": rec["node_type"],
                     "text": rec["text"], "score": rec["score"]}
                    for rec in result
                ]
            logger.debug(f"[HybridVectorStore] neo4j vector index '{index_name}': {len(hits)} hits")
            return hits
        except Exception as e:
            logger.debug(f"[HybridVectorStore] neo4j vector index query failed: {e}")
            return []


# ─────────────────────────────────────────────────────────────────────────────
# Backward-compat alias
# ─────────────────────────────────────────────────────────────────────────────

VectorClient = HybridVectorStore