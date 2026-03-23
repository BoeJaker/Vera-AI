#!/usr/bin/env python3
"""
Vera/Memory/entity_resolver.py
──────────────────────────────
EntityResolver — deduplication, canonical-form selection, and fuzzy merging
for NLP-extracted entities.

Responsibilities
----------------
1. **Exact resolution** — stable content-hash IDs mean the same entity text
   at different positions maps to the same graph node.  No duplicates for
   "Apple Inc." across sessions.

2. **Fuzzy merge** — entities whose embeddings are within `merge_threshold`
   cosine distance (default 0.92) of an existing Neo4j node are merged into
   that node rather than creating a new one.  Variant text is appended to
   `node.variants`.

3. **Canonical selection** — when multiple cluster members compete, the
   resolver picks the best canonical form: longest high-confidence entity
   that is not a pronoun or stopword.

4. **Type coercion** — PERSON nodes won't be merged with ORG nodes even if
   embeddings are close.  Label families are checked before merge is allowed.

Public API
----------
    resolver = EntityResolver(graph_driver, embedding_function)

    # Resolve a single entity — returns (canonical_id, was_merged)
    canon_id, merged = resolver.resolve(entity_text, entity_label, embedding)

    # Resolve a whole cluster at once — returns resolved canonical dict
    result = resolver.resolve_cluster(cluster_entities)

    # Force-merge two existing nodes (moves all edges)
    resolver.merge_nodes(keep_id, discard_id)
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── label families ── entities from different families are never merged ──────
_LABEL_FAMILIES: Dict[str, str] = {
    # People
    "PERSON":   "person",
    "SPEAKER":  "person",
    # Organisations
    "ORG":      "org",
    "COMPANY":  "org",
    "PRODUCT":  "product",
    # Geo
    "GPE":      "geo",
    "LOC":      "geo",
    "FACILITY": "geo",
    # Tech / code
    "CLASS":       "code",
    "METHOD":      "code",
    "FUNCTION":    "code",
    "IMPORT":      "code",
    "IMPORT_FROM": "code",
    "CODE_BLOCK":  "code",
    # Temporal
    "DATE":       "temporal",
    "DATE_RANGE": "temporal",
    "TIME":       "temporal",
    # Misc identifiers — never merge
    "URL":       "identifier",
    "EMAIL":     "identifier",
    "UUID":      "identifier",
    "IPV4":      "identifier",
    "IPV6":      "identifier",
    "HASH_MD5":  "identifier",
    "HASH_SHA1": "identifier",
    "HASH_SHA256": "identifier",
}

_NEVER_MERGE_FAMILIES = {"identifier", "code", "temporal"}

# Stopwords / pronouns that should never become canonical
_BAD_CANONICAL = frozenset({
    "he", "she", "it", "they", "we", "i", "you", "him", "her", "them",
    "his", "its", "our", "their", "this", "that", "these", "those",
    "who", "which", "what", "a", "an", "the",
})


def _stable_id(text: str, label: str) -> str:
    """Deterministic entity ID from normalised text + label."""
    key = f"{label.upper()}:{text.lower().strip()}"
    return "entity_" + hashlib.md5(key.encode()).hexdigest()[:12]


def _cosine(a: List[float], b: List[float]) -> float:
    try:
        import numpy as np
        va, vb = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
        denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
        return float(np.dot(va, vb) / denom) if denom > 0 else 0.0
    except ImportError:
        dot = sum(x * y for x, y in zip(a, b))
        na  = sum(x * x for x in a) ** 0.5
        nb  = sum(x * x for x in b) ** 0.5
        return dot / (na * nb) if na * nb > 0 else 0.0


class EntityResolver:
    """
    Resolve NLP-extracted entities against the Neo4j graph.

    Parameters
    ----------
    graph_driver : neo4j.Driver
        Live Neo4j driver — used for all graph reads/writes.
    embedding_function : callable
        Accepts List[str], returns List[List[float]].
        Used to embed candidate entities for fuzzy matching.
    merge_threshold : float
        Cosine similarity above which two entity embeddings are considered
        the same entity (default 0.92 — tight; lower to merge more aggressively).
    candidate_limit : int
        Max Neo4j nodes to pull for each fuzzy lookup (default 50).
    """

    def __init__(
        self,
        graph_driver,
        embedding_function,
        merge_threshold: float = 0.92,
        candidate_limit: int = 50,
    ):
        self._driver    = graph_driver
        self._ef        = embedding_function
        self._threshold = merge_threshold
        self._limit     = candidate_limit

        # In-process cache: stable_id → canonical_id
        # Avoids repeated Neo4j round-trips within a single extract_and_link call
        self._cache: Dict[str, str] = {}

    # ─────────────────────────────────────────────────────────────────────
    # Primary API
    # ─────────────────────────────────────────────────────────────────────

    def resolve(
        self,
        text: str,
        label: str,
        embedding: Optional[List[float]] = None,
        session_id: Optional[str] = None,
    ) -> Tuple[str, bool]:
        """
        Resolve a single entity.

        Returns
        -------
        (canonical_id, was_merged)
            canonical_id  — ID of the node to upsert into (may be existing).
            was_merged    — True if this entity matched an existing node.
        """
        stable = _stable_id(text, label)

        # 1. In-process cache hit
        if stable in self._cache:
            return self._cache[stable], True

        # 2. Exact graph hit (same stable ID already exists)
        if self._node_exists(stable):
            self._cache[stable] = stable
            self._append_variant(stable, text, session_id)
            return stable, True

        # 3. Skip fuzzy for families that must never merge
        family = _LABEL_FAMILIES.get(label.upper(), "generic")
        if family in _NEVER_MERGE_FAMILIES:
            self._cache[stable] = stable
            return stable, False

        # 4. Fuzzy match against existing nodes of same label family
        if embedding:
            match_id = self._fuzzy_match(embedding, label, family)
            if match_id:
                self._cache[stable] = match_id
                self._append_variant(match_id, text, session_id)
                logger.debug(
                    f"[EntityResolver] fuzzy-merged '{text}' ({label}) → {match_id}"
                )
                return match_id, True

        # 5. No match — new entity
        self._cache[stable] = stable
        return stable, False

    def resolve_cluster(
        self,
        cluster_entities: List[Any],
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Resolve a whole entity cluster.  Picks the best canonical text from
        the cluster, resolves against the graph, returns a dict suitable for
        Node construction.

        Returns
        -------
        {
            "canonical_id":   str,
            "canonical_text": str,
            "label":          str,
            "confidence":     float,
            "variants":       List[str],
            "was_merged":     bool,
        }
        """
        if not cluster_entities:
            return {}

        # Pick best canonical text from cluster
        canonical_entity = self._best_canonical(cluster_entities)
        text      = canonical_entity.text
        label     = canonical_entity.label
        embedding = canonical_entity.embedding
        confidence = getattr(canonical_entity, "confidence", 0.8)

        all_variants = list({e.text for e in cluster_entities if e.text and e.text.strip()})

        canon_id, was_merged = self.resolve(text, label, embedding, session_id)

        return {
            "canonical_id":   canon_id,
            "canonical_text": text,
            "label":          label,
            "confidence":     confidence,
            "variants":       all_variants,
            "was_merged":     was_merged,
            "embedding":      embedding,
        }

    def merge_nodes(self, keep_id: str, discard_id: str) -> None:
        """
        Merge discard_id into keep_id:
        - All edges of discard_id are re-pointed to keep_id
        - Variants from discard_id are appended to keep_id
        - discard_id node is deleted
        """
        if keep_id == discard_id:
            return

        logger.info(f"[EntityResolver] Merging node {discard_id} → {keep_id}")
        cypher_redirect = """
        MATCH (discard {id: $discard_id})
        MATCH (keep    {id: $keep_id})

        // Copy variants
        SET keep.variants = apoc.coll.toSet(
            coalesce(keep.variants, []) + coalesce(discard.variants, [])
        )

        // Move outgoing edges
        WITH discard, keep
        OPTIONAL MATCH (discard)-[r]->(target)
        WHERE target.id <> $keep_id
        CALL apoc.refactor.from(r, keep) YIELD input RETURN count(input)
        """
        # Simpler version without APOC (moves edges manually):
        cypher_no_apoc = """
        MATCH (d {id: $discard_id})-[r:REL]->(t)
        MATCH (k {id: $keep_id})
        WHERE t.id <> $keep_id
        MERGE (k)-[r2:REL {rel: r.rel}]->(t)
        SET r2 += r
        DELETE r
        """
        cypher_in = """
        MATCH (s)-[r:REL]->(d {id: $discard_id})
        MATCH (k {id: $keep_id})
        WHERE s.id <> $keep_id
        MERGE (s)-[r2:REL {rel: r.rel}]->(k)
        SET r2 += r
        DELETE r
        """
        cypher_variants = """
        MATCH (d {id: $discard_id}), (k {id: $keep_id})
        SET k.variants = k.variants + coalesce(d.variants, [d.text])
        DELETE d
        """
        with self._driver.session() as sess:
            sess.run(cypher_no_apoc, {"discard_id": discard_id, "keep_id": keep_id})
            sess.run(cypher_in,      {"discard_id": discard_id, "keep_id": keep_id})
            sess.run(cypher_variants,{"discard_id": discard_id, "keep_id": keep_id})

        # Evict from cache
        self._cache = {k: v for k, v in self._cache.items() if v != discard_id}

    # ─────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────────────

    def _node_exists(self, node_id: str) -> bool:
        with self._driver.session() as sess:
            rec = sess.run(
                "MATCH (n {id: $id}) RETURN count(n) AS c", {"id": node_id}
            ).single()
            return bool(rec and rec["c"] > 0)

    def _append_variant(
        self, node_id: str, variant_text: str, session_id: Optional[str]
    ) -> None:
        cypher = """
        MATCH (n {id: $id})
        SET n.variants = apoc.coll.toSet(
            coalesce(n.variants, []) + [$variant]
        ),
        n.last_seen = $ts
        """
        # Fallback without APOC
        cypher_no_apoc = """
        MATCH (n {id: $id})
        WITH n, coalesce(n.variants, []) AS existing
        SET n.variants = CASE WHEN $variant IN existing THEN existing
                              ELSE existing + [$variant] END,
            n.last_seen = $ts,
            n.seen_count = coalesce(n.seen_count, 0) + 1
        """
        params = {
            "id": node_id, "variant": variant_text,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        try:
            with self._driver.session() as sess:
                sess.run(cypher_no_apoc, params)
        except Exception as e:
            logger.debug(f"[EntityResolver] _append_variant: {e}")

    def _fuzzy_match(
        self,
        embedding: List[float],
        label: str,
        family: str,
    ) -> Optional[str]:
        """
        Pull candidate nodes of the same label family from Neo4j
        and return the ID of the one with the highest cosine similarity
        above `_threshold`, or None.
        """
        # Fetch candidates: nodes of same family that have an embedding
        candidates = self._fetch_candidates(label, family)
        if not candidates:
            return None

        best_id    = None
        best_score = self._threshold  # must beat this

        for cand in candidates:
            cand_emb = cand.get("embedding")
            if not cand_emb:
                continue
            score = _cosine(embedding, list(cand_emb))
            if score > best_score:
                best_score = score
                best_id    = cand["id"]

        return best_id

    def _fetch_candidates(
        self, label: str, family: str
    ) -> List[Dict[str, Any]]:
        """
        Return up to `_limit` nodes that share the same label family
        and have an embedding stored.
        """
        # Map family → list of labels to match
        family_labels = [k for k, v in _LABEL_FAMILIES.items() if v == family]
        if not family_labels:
            family_labels = [label]

        # Build a label-in-list filter
        cypher = """
        MATCH (n:ExtractedEntity)
        WHERE n.embedding IS NOT NULL
          AND ANY(lbl IN $labels WHERE lbl IN labels(n))
        RETURN n.id AS id, n.embedding AS embedding
        LIMIT $limit
        """
        try:
            with self._driver.session() as sess:
                result = sess.run(
                    cypher,
                    {"labels": family_labels, "limit": self._limit},
                )
                return [{"id": r["id"], "embedding": list(r["embedding"])}
                        for r in result if r["id"] and r["embedding"]]
        except Exception as e:
            logger.debug(f"[EntityResolver] _fetch_candidates: {e}")
            return []

    def _best_canonical(self, entities: List[Any]) -> Any:
        """
        Pick the best canonical entity from a cluster:
        - Exclude pronouns / stopwords
        - Prefer highest confidence
        - Prefer longer text as tiebreaker
        """
        candidates = [
            e for e in entities
            if e.text and e.text.strip().lower() not in _BAD_CANONICAL
        ]
        if not candidates:
            return entities[0]

        return max(
            candidates,
            key=lambda e: (getattr(e, "confidence", 0.5), len(e.text)),
        )

    def flush_cache(self) -> None:
        """Clear the in-process resolution cache (call between unrelated sessions)."""
        self._cache.clear()