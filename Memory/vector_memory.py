#!/usr/bin/env python3
# Vera/Memory/vector_backend.py
"""
VectorBackend — pluggable vector store abstraction for HybridMemory.

Implementations
---------------
ChromaUnifiedBackend   — single PersistentClient (local file store), session_id metadata filter
ChromaHttpBackend      — single HttpClient pointing at a remote Chroma server,
                         same unified collection layout as ChromaUnifiedBackend.
                         Drop-in replacement: identical API, just swap backend="chroma_http".
WeaviateBackend        — Weaviate v4 client with equivalent filtering

BackendFactory         — resolves a config dict to the correct backend instance.
MigrationManager       — migrates all records from any backend to any other backend,
                         typically used to move local filestore → Chroma server.

Both ChromaUnifiedBackend and ChromaHttpBackend satisfy the VectorBackend protocol
so HybridVectorStore can swap between them at construction time.

──────────────────────────────────────────────────────────────────────────────
Quick-start: migrate filestore → Chroma server
──────────────────────────────────────────────────────────────────────────────

    # Python API
    from Vera.Memory.vector_backend import MigrationManager, ChromaUnifiedBackend, ChromaHttpBackend
    from chromadb.utils import embedding_functions

    ef = embedding_functions.SentenceTransformerEmbeddingFunction("all-MiniLM-L6-v2")

    src = ChromaUnifiedBackend("./Memory/chroma_store", ef, "vera_memory")
    dst = ChromaHttpBackend("localhost", 8000, ef, "vera_memory")

    mgr = MigrationManager(src, dst)
    mgr.migrate()                   # migrate vera_memory
    mgr.migrate_all_collections()   # migrate both vera_memory + long_term_docs

    # CLI
    python vector_backend.py migrate \\
        --src-dir ./Memory/chroma_store \\
        --dst-host localhost \\
        --dst-port 8000 \\
        --embedding-model all-MiniLM-L6-v2 \\
        --collections vera_memory long_term_docs

──────────────────────────────────────────────────────────────────────────────
HybridMemory: switching to Chroma server
──────────────────────────────────────────────────────────────────────────────

Pass ``vector_backend="chroma_http"`` plus the new keyword args:

    mem = HybridMemory(
        ...
        vector_backend="chroma_http",
        chroma_host="my-chroma-server",
        chroma_port=8000,
        chroma_ssl=False,
        chroma_headers={"Authorization": "Bearer <token>"},  # optional
    )

Or keep ``vector_backend="chroma"`` (default) to use the local file store.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Protocol
# ─────────────────────────────────────────────────────────────────────────────

@runtime_checkable
class VectorBackend(Protocol):
    """
    Minimal interface every backend must satisfy.

    ``where`` filters follow ChromaDB's dict syntax:
        {"session_id": {"$eq": "sess_123"}}
        {"$and": [{"session_id": {"$eq": "sess_123"}}, {"type": {"$eq": "query"}}]}

    Each backend translates these to its own query language internally.
    """

    def add(
        self,
        ids: List[str],
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> None: ...

    def query(
        self,
        text: str,
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Returns list of dicts:
            [{"id": ..., "text": ..., "metadata": {...}, "distance": float}, ...]
        """
        ...

    def delete(self, ids: List[str]) -> None: ...

    def get_all(
        self, where: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Fetch all stored items, optionally filtered."""
        ...


# ─────────────────────────────────────────────────────────────────────────────
# Shared Chroma collection logic (used by both file and HTTP backends)
# ─────────────────────────────────────────────────────────────────────────────

class _ChromaCollectionMixin:
    """
    Implements add / query / delete / get_all on top of a chromadb Collection.
    Subclasses set ``self._col``, ``self._collection_name``.
    """

    def add(
        self,
        ids: List[str],
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        safe_metas = []
        for m in (metadatas or [{}] * len(ids)):
            safe = {}
            for k, v in m.items():
                if isinstance(v, list):
                    safe[k] = ",".join(str(x) for x in v)
                elif isinstance(v, dict):
                    import json
                    safe[k] = json.dumps(v)
                elif v is None:
                    safe[k] = ""
                elif isinstance(v, (str, int, float, bool)):
                    safe[k] = v
                else:
                    safe[k] = str(v)
            safe_metas.append(safe)

        self._col.upsert(ids=ids, documents=texts, metadatas=safe_metas)
        logger.debug(
            f"[{self.__class__.__name__}] upserted {len(ids)} docs "
            f"into '{self._collection_name}'"
        )

    def query(
        self,
        text: str,
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        kwargs: Dict[str, Any] = {
            "query_texts": [text],
            "n_results": n_results,
        }
        if where:
            kwargs["where"] = where

        try:
            res = self._col.query(**kwargs)
        except Exception as e:
            logger.warning(
                f"[{self.__class__.__name__}] query failed (where={where}): {e}"
            )
            return []

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

    def delete(self, ids: List[str]) -> None:
        self._col.delete(ids=ids)

    def get_all(
        self, where: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        kwargs: Dict[str, Any] = {}
        if where:
            kwargs["where"] = where
        res = self._col.get(**kwargs)
        hits = []
        if res and res.get("ids"):
            for i, doc_id in enumerate(res["ids"]):
                hits.append({
                    "id":       doc_id,
                    "text":     (res.get("documents") or [])[i] if res.get("documents") else "",
                    "metadata": (res.get("metadatas") or [])[i] if res.get("metadatas") else {},
                })
        return hits

    # ── Filter helpers ────────────────────────────────────────────────────

    @classmethod
    def session_filter(cls, session_id: str) -> Dict[str, Any]:
        return {"session_id": {"$eq": session_id}}

    @classmethod
    def type_filter(cls, node_type: str) -> Dict[str, Any]:
        return {"type": {"$eq": node_type}}

    @classmethod
    def combined_filter(cls, **kwargs) -> Dict[str, Any]:
        """
        Build a $and filter from keyword args.
        combined_filter(session_id="sess_1", type="query")
        → {"$and": [{"session_id": {"$eq": "sess_1"}}, {"type": {"$eq": "query"}}]}
        """
        clauses = [{k: {"$eq": v}} for k, v in kwargs.items() if v is not None]
        if len(clauses) == 0:
            return {}
        if len(clauses) == 1:
            return clauses[0]
        return {"$and": clauses}


# ─────────────────────────────────────────────────────────────────────────────
# Chroma unified backend — LOCAL file store  (original)
# ─────────────────────────────────────────────────────────────────────────────

class ChromaUnifiedBackend(_ChromaCollectionMixin):
    """
    Single ChromaDB **PersistentClient** with ONE collection per logical store
    (``vera_memory`` for session data, ``long_term_docs`` for promoted/long-term).

    Session scoping is achieved via metadata filtering on ``session_id``
    rather than separate per-session collections.
    """

    SESSION_COLLECTION  = "vera_memory"
    LONGTERM_COLLECTION = "long_term_docs"

    def __init__(
        self,
        persist_dir: str,
        embedding_function,
        collection_name: str = SESSION_COLLECTION,
    ):
        import chromadb

        os.makedirs(persist_dir, exist_ok=True)
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._ef = embedding_function
        self._collection_name = collection_name
        self._col = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=embedding_function,
        )
        logger.info(
            f"[ChromaUnifiedBackend] collection='{collection_name}' "
            f"persist_dir='{persist_dir}'"
        )

    @property
    def persist_dir(self) -> str:
        return self._client._path  # type: ignore[attr-defined]


# ─────────────────────────────────────────────────────────────────────────────
# Chroma HTTP backend — remote Chroma server
# ─────────────────────────────────────────────────────────────────────────────

class ChromaHttpBackend(_ChromaCollectionMixin):
    """
    Single ChromaDB **HttpClient** pointing at a Chroma server.

    Identical collection layout and metadata-filter semantics to
    ``ChromaUnifiedBackend`` — the only difference is the client type.
    All HybridVectorStore / HybridMemory code that works with the file
    backend works identically with this one.

    Parameters
    ----------
    host : str
        Chroma server hostname or IP (e.g. ``"localhost"`` or ``"chroma.internal"``).
    port : int
        Chroma HTTP port (default 8000).
    embedding_function : callable
        ChromaDB-compatible embedding function.
    collection_name : str
        Collection to use (default ``"vera_memory"``).
    ssl : bool
        Use HTTPS (default False).
    headers : dict | None
        Extra HTTP headers, e.g. ``{"Authorization": "Bearer <token>"}``.
    tenant : str
        Chroma multi-tenant tenant name (default ``"default_tenant"``).
    database : str
        Chroma database name (default ``"default_database"``).

    Example
    -------
        backend = ChromaHttpBackend(
            host="chroma.my-server.local",
            port=8000,
            embedding_function=ef,
            collection_name="vera_memory",
        )
    """

    SESSION_COLLECTION  = "vera_memory"
    LONGTERM_COLLECTION = "long_term_docs"

    def __init__(
        self,
        host: str,
        port: int,
        embedding_function,
        collection_name: str = SESSION_COLLECTION,
        ssl: bool = False,
        headers: Optional[Dict[str, str]] = None,
        tenant: str = "default_tenant",
        database: str = "default_database",
    ):
        import chromadb

        self._host = host
        self._port = port
        self._ef = embedding_function
        self._collection_name = collection_name

        client_kwargs: Dict[str, Any] = {
            "host": host,
            "port": port,
            "ssl": ssl,
        }
        if headers:
            client_kwargs["headers"] = headers

        # chromadb >= 0.5.0 supports tenant/database on HttpClient
        try:
            self._client = chromadb.HttpClient(
                **client_kwargs,
                tenant=tenant,
                database=database,
            )
        except TypeError:
            # Older chromadb versions don't have tenant/database kwargs
            self._client = chromadb.HttpClient(**client_kwargs)

        self._col = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=embedding_function,
        )
        logger.info(
            f"[ChromaHttpBackend] collection='{collection_name}' "
            f"server={'https' if ssl else 'http'}://{host}:{port}"
        )

    def heartbeat(self) -> bool:
        """Check that the Chroma server is reachable.  Returns True if alive."""
        try:
            self._client.heartbeat()
            return True
        except Exception as e:
            logger.warning(f"[ChromaHttpBackend] heartbeat failed: {e}")
            return False


# ─────────────────────────────────────────────────────────────────────────────
# Weaviate backend (v4 client)  — unchanged from original
# ─────────────────────────────────────────────────────────────────────────────

class WeaviateBackend:
    """
    Weaviate v4 backend using the ``weaviate-client>=4.0`` package.

    The schema is auto-created on first use.  All documents are stored in
    a single class (default: ``VeraMemory``) with a ``session_id`` text
    property for filtering.

    ``where`` filters (ChromaDB-style dict) are translated to Weaviate's
    Filter objects automatically by ``_translate_where``.

    pip install weaviate-client>=4.0
    """

    def __init__(
        self,
        url: str,
        embedding_function,
        class_name: str = "VeraMemory",
        api_key: Optional[str] = None,
        grpc_port: int = 50051,
    ):
        self._ef = embedding_function
        self._class_name = class_name
        self._url = url

        try:
            import weaviate
            from weaviate.classes.init import Auth

            connect_kwargs: Dict[str, Any] = {}
            if api_key:
                connect_kwargs["auth_credentials"] = Auth.api_key(api_key)

            import urllib.parse
            parsed = urllib.parse.urlparse(url)
            host = parsed.hostname or "localhost"
            http_port = parsed.port or (443 if parsed.scheme == "https" else 8080)
            secure = parsed.scheme == "https"

            self._client = weaviate.connect_to_custom(
                http_host=host,
                http_port=http_port,
                http_secure=secure,
                grpc_host=host,
                grpc_port=grpc_port,
                grpc_secure=secure,
                **connect_kwargs,
            )
            self._weaviate = weaviate

            self._ensure_schema()
            logger.info(
                f"[WeaviateBackend] Connected to {url}, class='{class_name}'"
            )

        except ImportError:
            raise ImportError(
                "weaviate-client>=4.0 is required for WeaviateBackend. "
                "Install with: pip install weaviate-client"
            )

    def _ensure_schema(self):
        from weaviate.classes.config import Configure, Property, DataType

        existing = [c.name for c in self._client.collections.list_all().values()]
        if self._class_name in existing:
            self._collection = self._client.collections.get(self._class_name)
            return

        self._collection = self._client.collections.create(
            name=self._class_name,
            vectorizer_config=Configure.Vectorizer.none(),
            properties=[
                Property(name="doc_id",     data_type=DataType.TEXT),
                Property(name="text",       data_type=DataType.TEXT),
                Property(name="session_id", data_type=DataType.TEXT),
                Property(name="node_id",    data_type=DataType.TEXT),
                Property(name="node_type",  data_type=DataType.TEXT),
                Property(name="type",       data_type=DataType.TEXT),
                Property(name="labels",     data_type=DataType.TEXT),
                Property(name="promoted",   data_type=DataType.BOOL),
                Property(name="meta_json",  data_type=DataType.TEXT),
            ],
        )
        logger.info(f"[WeaviateBackend] Created class '{self._class_name}'")

    def add(
        self,
        ids: List[str],
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        import json
        from weaviate.classes.data import DataObject

        vectors = self._ef(texts)
        metas = metadatas or [{}] * len(ids)

        objects = []
        for doc_id, text, vector, meta in zip(ids, texts, vectors, metas):
            safe_meta = _flatten_metadata(meta)
            props = {
                "doc_id":     doc_id,
                "text":       text,
                "session_id": safe_meta.get("session_id", ""),
                "node_id":    safe_meta.get("node_id", ""),
                "node_type":  safe_meta.get("type", ""),
                "type":       safe_meta.get("type", ""),
                "labels":     safe_meta.get("labels", ""),
                "promoted":   bool(safe_meta.get("promoted", False)),
                "meta_json":  json.dumps(safe_meta),
            }
            objects.append(DataObject(properties=props, vector=vector, uuid=_id_to_uuid(doc_id)))

        with self._collection.batch.dynamic() as batch:
            for obj in objects:
                batch.add_object(properties=obj.properties, vector=obj.vector, uuid=obj.uuid)

        logger.debug(f"[WeaviateBackend] upserted {len(ids)} objects")

    def query(
        self,
        text: str,
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        from weaviate.classes.query import MetadataQuery

        query_vector = self._ef([text])[0]
        weaviate_filter = self._translate_where(where) if where else None

        kwargs: Dict[str, Any] = {
            "near_vector": query_vector,
            "limit": n_results,
            "return_metadata": MetadataQuery(distance=True),
        }
        if weaviate_filter:
            kwargs["filters"] = weaviate_filter

        res = self._collection.query.near_vector(**kwargs)

        hits = []
        for obj in res.objects:
            import json
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

    def delete(self, ids: List[str]) -> None:
        for doc_id in ids:
            try:
                self._collection.data.delete_by_id(_id_to_uuid(doc_id))
            except Exception as e:
                logger.debug(f"[WeaviateBackend] delete {doc_id}: {e}")

    def get_all(
        self, where: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        import json
        weaviate_filter = self._translate_where(where) if where else None
        kwargs: Dict[str, Any] = {"limit": 10_000}
        if weaviate_filter:
            kwargs["filters"] = weaviate_filter
        res = self._collection.query.fetch_objects(**kwargs)
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
            })
        return hits

    def close(self):
        try:
            self._client.close()
        except Exception:
            pass

    def _translate_where(self, where: Dict[str, Any]):
        from weaviate.classes.query import Filter

        if "$and" in where:
            clauses = [self._translate_where(c) for c in where["$and"]]
            result = clauses[0]
            for c in clauses[1:]:
                result = result & c
            return result

        if "$or" in where:
            clauses = [self._translate_where(c) for c in where["$or"]]
            result = clauses[0]
            for c in clauses[1:]:
                result = result | c
            return result

        for field, condition in where.items():
            if not isinstance(condition, dict):
                return Filter.by_property(field).equal(condition)
            op, val = next(iter(condition.items()))
            match op:
                case "$eq":  return Filter.by_property(field).equal(val)
                case "$ne":  return Filter.by_property(field).not_equal(val)
                case "$gt":  return Filter.by_property(field).greater_than(val)
                case "$gte": return Filter.by_property(field).greater_or_equal(val)
                case "$lt":  return Filter.by_property(field).less_than(val)
                case "$lte": return Filter.by_property(field).less_or_equal(val)
                case "$in":  return Filter.by_property(field).contains_any(val)
                case _:
                    logger.warning(f"[WeaviateBackend] Unknown operator '{op}', skipping")
                    return None

        return None


# ─────────────────────────────────────────────────────────────────────────────
# BackendFactory
# ─────────────────────────────────────────────────────────────────────────────

class BackendFactory:
    """
    Resolves a config dict to a concrete backend instance.

    Supported backend types
    -----------------------
    ``"chroma"``
        Local PersistentClient (file store).
        Required config keys: ``persist_dir``
        Optional: ``collection_name``

    ``"chroma_http"``
        Remote HttpClient pointing at a Chroma server.
        Required config keys: ``host``, ``port``
        Optional: ``ssl``, ``headers``, ``collection_name``,
                  ``tenant``, ``database``

    ``"weaviate"``
        Weaviate v4 backend.
        Required config keys: ``url``
        Optional: ``api_key``, ``class_name``, ``grpc_port``

    Usage
    -----
        ef = chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction(...)

        # File store
        backend = BackendFactory.create({"type": "chroma", "persist_dir": "./chroma"}, ef)

        # Remote server
        backend = BackendFactory.create({"type": "chroma_http", "host": "localhost", "port": 8000}, ef)

        # Session + long-term pair (the normal Vera use-case)
        session_b, longterm_b = BackendFactory.create_pair(
            {"type": "chroma_http", "host": "localhost", "port": 8000},
            ef,
        )
    """

    @staticmethod
    def create(
        config: Dict[str, Any],
        embedding_function,
        collection_name: Optional[str] = None,
    ) -> VectorBackend:
        """
        Create a single backend instance from config.

        ``collection_name`` overrides the ``collection_name`` key in config.
        """
        cfg = dict(config)
        backend_type = cfg.pop("type", "chroma").lower()
        col = collection_name or cfg.pop("collection_name", None)

        if backend_type == "chroma":
            persist_dir = cfg.get("persist_dir", "./Memory/chroma_store")
            col = col or "vera_memory"
            return ChromaUnifiedBackend(persist_dir, embedding_function, col)

        elif backend_type == "chroma_http":
            host = cfg.get("host", "localhost")
            port = int(cfg.get("port", 8000))
            ssl  = bool(cfg.get("ssl", False))
            headers  = cfg.get("headers")
            tenant   = cfg.get("tenant", "default_tenant")
            database = cfg.get("database", "default_database")
            col = col or "vera_memory"
            return ChromaHttpBackend(
                host=host,
                port=port,
                embedding_function=embedding_function,
                collection_name=col,
                ssl=ssl,
                headers=headers,
                tenant=tenant,
                database=database,
            )

        elif backend_type == "weaviate":
            url       = cfg.get("url", "http://localhost:8080")
            api_key   = cfg.get("api_key")
            class_name = col or cfg.get("class_name", "VeraMemory")
            grpc_port = int(cfg.get("grpc_port", 50051))
            return WeaviateBackend(
                url=url,
                embedding_function=embedding_function,
                class_name=class_name,
                api_key=api_key,
                grpc_port=grpc_port,
            )

        else:
            raise ValueError(
                f"Unknown backend type '{backend_type}'. "
                f"Choose from: chroma, chroma_http, weaviate"
            )

    @classmethod
    def create_pair(
        cls,
        config: Dict[str, Any],
        embedding_function,
    ):
        """
        Create the standard (session_backend, longterm_backend) pair.

        For Chroma backends the two collections differ only in name.
        For Weaviate, two separate class names are used.
        """
        session_cfg  = dict(config)
        longterm_cfg = dict(config)

        backend_type = config.get("type", "chroma").lower()

        if backend_type in ("chroma", "chroma_http"):
            session_b  = cls.create(session_cfg,  embedding_function, "vera_memory")
            longterm_b = cls.create(longterm_cfg, embedding_function, "long_term_docs")

        elif backend_type == "weaviate":
            base_class = config.get("class_name", "VeraMemory")
            session_b  = cls.create({**session_cfg,  "class_name": base_class},             embedding_function)
            longterm_b = cls.create({**longterm_cfg, "class_name": f"{base_class}LongTerm"}, embedding_function)

        else:
            raise ValueError(f"Unknown backend type '{backend_type}'")

        return session_b, longterm_b


# ─────────────────────────────────────────────────────────────────────────────
# MigrationManager
# ─────────────────────────────────────────────────────────────────────────────

class MigrationManager:
    """
    Migrates all records from one VectorBackend to another.

    Typical use: move local Chroma file store → remote Chroma server.

    Features
    --------
    - Batch upsert with configurable batch size (default 200)
    - Skip IDs already present in destination (``skip_existing=True`` default)
    - Progress logging every N batches
    - Dry-run mode: counts records without writing
    - Handles both ``vera_memory`` and ``long_term_docs`` collections

    Usage
    -----
        src = ChromaUnifiedBackend("./chroma_store", ef, "vera_memory")
        dst = ChromaHttpBackend("localhost", 8000, ef, "vera_memory")

        mgr = MigrationManager(src, dst)
        result = mgr.migrate()
        # {"migrated": 1234, "skipped": 56, "errors": 0, "collection": "vera_memory"}

        # Migrate both collections at once:
        results = mgr.migrate_all_collections(
            src_persist_dir="./chroma_store",
            dst_config={"type": "chroma_http", "host": "localhost", "port": 8000},
            embedding_function=ef,
        )
    """

    def __init__(
        self,
        source: VectorBackend,
        destination: VectorBackend,
        batch_size: int = 200,
        skip_existing: bool = True,
        dry_run: bool = False,
    ):
        self.source      = source
        self.destination = destination
        self.batch_size  = batch_size
        self.skip_existing = skip_existing
        self.dry_run     = dry_run

    # ── Main migration entrypoint ─────────────────────────────────────────

    def migrate(
        self,
        where: Optional[Dict[str, Any]] = None,
        progress_every: int = 10,
    ) -> Dict[str, Any]:
        """
        Migrate all records from source → destination.

        Parameters
        ----------
        where : dict | None
            Optional filter to migrate only a subset (e.g. one session).
        progress_every : int
            Log a progress line every N batches.

        Returns
        -------
        dict with keys: migrated, skipped, errors, duration_s
        """
        logger.info(
            f"[MigrationManager] Starting migration "
            f"(dry_run={self.dry_run}, skip_existing={self.skip_existing}, "
            f"batch_size={self.batch_size})"
        )
        t0 = time.time()

        # Fetch all records from source
        all_records = self.source.get_all(where=where)
        total = len(all_records)
        logger.info(f"[MigrationManager] Source contains {total} records")

        if total == 0:
            return {"migrated": 0, "skipped": 0, "errors": 0, "duration_s": 0.0}

        # Optionally pre-fetch existing IDs from destination
        existing_ids: set = set()
        if self.skip_existing and not self.dry_run:
            logger.info("[MigrationManager] Fetching existing IDs from destination …")
            try:
                dest_records = self.destination.get_all()
                existing_ids = {r["id"] for r in dest_records}
                logger.info(f"[MigrationManager] Destination has {len(existing_ids)} existing records")
            except Exception as e:
                logger.warning(f"[MigrationManager] Could not fetch destination IDs: {e}. Proceeding without dedup.")

        migrated = 0
        skipped  = 0
        errors   = 0

        # Batch upsert
        batches = _chunk(all_records, self.batch_size)
        for batch_idx, batch in enumerate(batches):
            ids       = []
            texts     = []
            metadatas = []

            for rec in batch:
                rid = rec["id"]
                if self.skip_existing and rid in existing_ids:
                    skipped += 1
                    continue
                ids.append(rid)
                texts.append(rec["text"])
                metadatas.append(rec.get("metadata", {}))

            if not ids:
                continue

            if self.dry_run:
                migrated += len(ids)
                logger.debug(f"[MigrationManager] DRY-RUN batch {batch_idx+1}: would migrate {len(ids)} records")
                continue

            try:
                self.destination.add(ids, texts, metadatas)
                migrated += len(ids)
            except Exception as e:
                logger.error(f"[MigrationManager] Batch {batch_idx+1} failed: {e}")
                errors += len(ids)

            if (batch_idx + 1) % progress_every == 0 or (batch_idx + 1) == len(batches):
                elapsed = time.time() - t0
                logger.info(
                    f"[MigrationManager] Batch {batch_idx+1}/{len(batches)} — "
                    f"migrated={migrated} skipped={skipped} errors={errors} "
                    f"elapsed={elapsed:.1f}s"
                )

        duration = time.time() - t0
        result = {
            "migrated":   migrated,
            "skipped":    skipped,
            "errors":     errors,
            "duration_s": round(duration, 2),
        }
        logger.info(f"[MigrationManager] Complete: {result}")
        return result

    # ── Convenience: migrate both collections ─────────────────────────────

    @classmethod
    def migrate_all_collections(
        cls,
        src_persist_dir: str,
        dst_config: Dict[str, Any],
        embedding_function,
        collections: Optional[List[str]] = None,
        batch_size: int = 200,
        skip_existing: bool = True,
        dry_run: bool = False,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Migrate all standard collections from a local file store to a destination.

        Parameters
        ----------
        src_persist_dir : str
            Path to the local Chroma store directory.
        dst_config : dict
            BackendFactory config for the destination, e.g.:
            ``{"type": "chroma_http", "host": "localhost", "port": 8000}``
        embedding_function : callable
            Shared embedding function for both backends.
        collections : list[str] | None
            Collections to migrate.  Defaults to
            ``["vera_memory", "long_term_docs"]``.
        batch_size, skip_existing, dry_run : see ``migrate()``.

        Returns
        -------
        dict mapping collection name → migration result dict.
        """
        if collections is None:
            collections = ["vera_memory", "long_term_docs"]

        results: Dict[str, Dict[str, Any]] = {}

        for col in collections:
            logger.info(f"[MigrationManager] ── Migrating collection: '{col}' ──")

            src = ChromaUnifiedBackend(src_persist_dir, embedding_function, col)
            dst = BackendFactory.create(dst_config, embedding_function, col)

            mgr = cls(
                source=src,
                destination=dst,
                batch_size=batch_size,
                skip_existing=skip_existing,
                dry_run=dry_run,
            )
            result = mgr.migrate()
            result["collection"] = col
            results[col] = result

        return results

    # ── Session-scoped migration ──────────────────────────────────────────

    def migrate_session(self, session_id: str) -> Dict[str, Any]:
        """
        Migrate only the records belonging to a single session.

        Useful for incremental / selective migrations.
        """
        logger.info(f"[MigrationManager] Migrating session '{session_id}'")
        where = {"session_id": {"$eq": session_id}}
        result = self.migrate(where=where)
        result["session_id"] = session_id
        return result


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _flatten_metadata(meta: Dict[str, Any]) -> Dict[str, Any]:
    """Convert lists/dicts to strings so they're safe for any backend."""
    import json
    safe = {}
    for k, v in meta.items():
        if isinstance(v, list):
            safe[k] = ",".join(str(x) for x in v)
        elif isinstance(v, dict):
            safe[k] = json.dumps(v)
        elif v is None:
            safe[k] = ""
        else:
            safe[k] = v
    return safe


def _id_to_uuid(doc_id: str) -> str:
    """
    Deterministically convert an arbitrary string ID to a UUID v5
    so Weaviate's UUID primary key is stable across upserts.
    """
    import uuid
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, doc_id))


def _chunk(lst: List[Any], size: int) -> List[List[Any]]:
    """Split a list into batches of at most ``size`` items."""
    return [lst[i:i + size] for i in range(0, len(lst), size)]


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def _build_embedding_function(model: str):
    """
    Build a ChromaDB-compatible embedding function from a model name.

    If the name contains ':' it is treated as an Ollama model
    (``nomic-embed-text:latest``) and routed through localhost:11434.
    Otherwise it is treated as a SentenceTransformer model name.
    """
    if ":" in model:
        # Ollama model
        from langchain_community.embeddings import OllamaEmbeddings

        class _OllamaEF:
            def __init__(self, m: str):
                self._emb = OllamaEmbeddings(model=m, base_url="http://localhost:11434")
            def __call__(self, input):
                return self._emb.embed_documents(input)

        return _OllamaEF(model)
    else:
        from chromadb.utils import embedding_functions
        return embedding_functions.SentenceTransformerEmbeddingFunction(model_name=model)


def _cli_migrate(args):
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    ef = _build_embedding_function(args.embedding_model)

    dst_config: Dict[str, Any] = {
        "type": "chroma_http",
        "host": args.dst_host,
        "port": args.dst_port,
        "ssl":  args.ssl,
    }
    if args.auth_token:
        dst_config["headers"] = {"Authorization": f"Bearer {args.auth_token}"}
    if args.tenant:
        dst_config["tenant"] = args.tenant
    if args.database:
        dst_config["database"] = args.database

    collections = args.collections or ["vera_memory", "long_term_docs"]

    results = MigrationManager.migrate_all_collections(
        src_persist_dir=args.src_dir,
        dst_config=dst_config,
        embedding_function=ef,
        collections=collections,
        batch_size=args.batch_size,
        skip_existing=not args.no_skip,
        dry_run=args.dry_run,
    )

    print("\n── Migration Summary ──────────────────────────────")
    total_migrated = 0
    total_skipped  = 0
    total_errors   = 0
    for col, r in results.items():
        print(
            f"  {col:25s}  migrated={r['migrated']:6d}  "
            f"skipped={r['skipped']:6d}  errors={r['errors']:4d}  "
            f"({r['duration_s']:.1f}s)"
        )
        total_migrated += r["migrated"]
        total_skipped  += r["skipped"]
        total_errors   += r["errors"]
    print(f"  {'TOTAL':25s}  migrated={total_migrated:6d}  skipped={total_skipped:6d}  errors={total_errors:4d}")
    print("───────────────────────────────────────────────────\n")

    if total_errors > 0:
        sys.exit(1)


def _cli_heartbeat(args):
    logging.basicConfig(level=logging.WARNING)
    ef = _build_embedding_function(args.embedding_model)
    backend = ChromaHttpBackend(
        host=args.host,
        port=args.port,
        embedding_function=ef,
        ssl=args.ssl,
    )
    if backend.heartbeat():
        print(f"✓  Chroma server at {args.host}:{args.port} is alive.")
    else:
        print(f"✗  Chroma server at {args.host}:{args.port} is NOT reachable.")
        import sys
        sys.exit(1)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Vera vector backend utilities",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    # ── migrate ──────────────────────────────────────────────────────────
    m = sub.add_parser("migrate", help="Migrate local file store → Chroma server")
    m.add_argument("--src-dir",        required=True, help="Local Chroma persist directory")
    m.add_argument("--dst-host",       default="localhost")
    m.add_argument("--dst-port",       type=int, default=8000)
    m.add_argument("--ssl",            action="store_true", default=False)
    m.add_argument("--auth-token",     default=None, help="Bearer token for Chroma auth")
    m.add_argument("--tenant",         default=None)
    m.add_argument("--database",       default=None)
    m.add_argument("--collections",    nargs="+", default=None,
                   help="Collections to migrate (default: vera_memory long_term_docs)")
    m.add_argument("--embedding-model", default="all-MiniLM-L6-v2",
                   help="Embedding model.  Use 'nomic-embed-text:latest' for Ollama.")
    m.add_argument("--batch-size",     type=int, default=200)
    m.add_argument("--no-skip",        action="store_true", default=False,
                   help="Re-migrate records that already exist in destination")
    m.add_argument("--dry-run",        action="store_true", default=False,
                   help="Count records without writing to destination")
    m.set_defaults(func=_cli_migrate)

    # ── heartbeat ────────────────────────────────────────────────────────
    h = sub.add_parser("heartbeat", help="Check that a Chroma server is reachable")
    h.add_argument("--host",           default="localhost")
    h.add_argument("--port",           type=int, default=8000)
    h.add_argument("--ssl",            action="store_true", default=False)
    h.add_argument("--embedding-model", default="all-MiniLM-L6-v2")
    h.set_defaults(func=_cli_heartbeat)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()