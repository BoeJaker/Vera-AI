#!/usr/bin/env python3
# vera_context_probe.py
"""
ContextProbe — Intelligent memory querying for Vera's context system.

v6 rewrite: advanced multi-strategy retrieval.

What was broken in v5 and why
─────────────────────────────
1.  Session vector query issued `where=None` — no session filter, so it pulled
    from the entire vera_memory collection (mixed with long-term data) and then
    separately queried with a session filter. Result: effectively only long-term
    data got surfaced.  Fix: always query with a session filter first, then fall
    back to cross-session for supplemental results.

2.  Pure cosine similarity only.  Related-but-not-similar content (e.g. asking
    about a technique when the memory stores a result, or asking about a concept
    when memory stores code using that concept) was invisible.  Fix: multi-query
    expansion + BM25-style keyword search in Neo4j + fuzzy full-text matching.

3.  Chunks returned instead of full blobs.  When a document was stored in chunks
    (store_file), the top-k vector search returned one chunk rather than the
    parent.  Fix: chunk-to-parent resolution that fetches and reassembles sibling
    chunks from the same file_id.

4.  Graph traversal was limited to session anchor IDs (nodes linked TO the
    current session).  For a fresh or sparse session this is just a handful of
    nodes.  Fix: seed graph traversal from ALL vector-hit node IDs, not just
    session anchors.

New retrieval strategies in v6
───────────────────────────────
A.  Multi-query vector expansion
    The original query is expanded into 2-3 variants (keyword-extracted
    sub-queries) before any vector search.  Each sub-query targets a different
    aspect of the question.  Results are merged by max score.

B.  Neo4j full-text keyword search  (requires index, auto-created lazily)
    `CALL db.index.fulltext.queryNodes(...)` — finds nodes whose `.text` property
    contains ANY of the query's significant tokens.  Finds results that cosine
    search misses because they are semantically distant but lexically relevant.

C.  Entity-guided recall
    Extracts named entities and key noun phrases from the query string.
    Searches Neo4j for ExtractedEntity nodes matching those terms, then walks
    their EXTRACTED_FROM/MENTIONS_ENTITY edges to find the originating memory
    nodes.  Surfaces memories you asked about by name even if rephrased.

D.  Chunk-to-parent reassembly
    When a hit's metadata contains a `file_id` or `chunk_index`, fetch ALL
    sibling chunks from Neo4j, sort by chunk_index, concatenate, and replace
    the chunk with the full text up to MAX_REASSEMBLED_CHARS.

E.  Session-vs-longterm balance
    Separate quotas for session and long-term hits prevent long-term from
    drowning out recent session context.

F.  Temporal recency boost
    Hits from the current session (matching `session_id`) get a small additive
    boost so very recent context is preferred over older cross-session matches.

All strategies contribute to a single merged, deduplicated, scored list.
Dedup and neighbour-swap logic from v5 is preserved unchanged.
"""

from __future__ import annotations

import logging
import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Tuning constants
# ─────────────────────────────────────────────────────────────────────────────

ALPHA: float = 0.55
HOP_DECAY: float = 0.6
MAX_HOPS: int = 2

HIGH_SIGNAL_RELS = frozenset({
    "MENTIONS_ENTITY", "EXTRACTED_FROM", "EXTRACTED_IN",
    "FOCUSES_ON", "FOLLOWS", "HAS_THOUGHT", "HAS_DOCUMENT",
})

GRAPH_HIT_MIN_SCORE: float = 0.12
GRAPH_TRAVERSE_LIMIT: int = 60

TYPE_SCORE_MULTIPLIER = {
    # existing
    "query":            0.65,
    "response":         1.20,
    "document":         1.10,
    "tool_output":      1.15,
    "thought":          0.75,
    # new — graph-typical node types
    "entity":           0.90,
    "extractedentity":  0.00,
    "unknown":          0.85,
    "session":          0.00,   # session nodes are structural, rarely useful verbatim
    # keyword / entity-recall sources often surface short entity names —
    # give them a slight boost so they're not penalised by length bonus
    "keyword_neo4j":    0.95,
    "entity_recall":    0.95,
}



LENGTH_BONUS_PIVOT: int   = 30
LENGTH_BONUS_MAX:   float = 0.30

SESSION_VECTOR_TYPE_CAPS: Dict[str, int] = {
    "query":    2,
    "response": 16,
    "document": 10,
}

TRIGRAM_THRESHOLD: float = 0.55
TRIGRAM_MAX_LEN:   int   = 200

NEIGHBOUR_SWAP_SCORE: float = 0.60
NEIGHBOUR_SWAP_K:     int   = 4

NEIGHBOUR_SWAP_TYPES = frozenset({
    "response", "Response", "document", "Document", "tool_output", "ToolOutput",
})

FOLLOWS_PAIR_BOOST: float = 1.25

# ── v6 new constants ──────────────────────────────────────────────────────────

# Maximum characters for chunk reassembly
MAX_REASSEMBLED_CHARS: int = 8000

# Minimum token length to treat as a keyword (avoids stop-words)
MIN_KEYWORD_LEN: int = 4

# How many keyword sub-queries to generate
EXPAND_SUBQUERY_COUNT: int = 3

# Score for full-text / keyword hits (before type+length adjustment)
KEYWORD_HIT_BASE_SCORE: float = 0.70

# Score for entity-guided recall hits
ENTITY_RECALL_BASE_SCORE: float = 0.65

# Recency boost for hits in the current session
RECENCY_BOOST: float = 0.12

# Max full-text keyword hits to fetch from Neo4j
FULLTEXT_LIMIT: int = 30

# Max entity-guided hits to fetch
ENTITY_RECALL_LIMIT: int = 20

# BM25-like IDF cap — how much a rare keyword can boost a hit
KEYWORD_BOOST_MAX: float = 0.25

# ── Session vs long-term quotas ────────────────────────────────────────────
# These cap how many hits of each source end up in ranked_hits.
# Ensures session memory isn't swamped by long-term docs.
SESSION_HIT_QUOTA:  int = 20
LONGTERM_HIT_QUOTA: int = 10

# Name of the Neo4j full-text index (created lazily)
NEO4J_FULLTEXT_INDEX = "vera_memory_fulltext"


# ─────────────────────────────────────────────────────────────────────────────
# Module-level helpers
# ─────────────────────────────────────────────────────────────────────────────

_STOP_WORDS: frozenset = frozenset({
    "the", "and", "for", "that", "this", "with", "have", "from",
    "are", "was", "were", "been", "will", "would", "could", "should",
    "what", "when", "where", "which", "who", "how", "why", "can",
    "does", "did", "has", "its", "you", "your", "my", "me", "we",
    "they", "them", "our", "their", "is", "it", "be", "do", "not",
    "also", "into", "over", "more", "just", "than", "then", "some",
})

_HTML_RE = re.compile(r'<[^>]+>')
_PUNC_RE = re.compile(r'[^\w\s]')
_WS_RE   = re.compile(r'\s+')


def _normalise(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    t = _PUNC_RE.sub("", text.lower())
    return _WS_RE.sub(" ", t).strip()


def _fingerprint(text: str) -> str:
    return _normalise(text)[:100]


def _trigrams(text: str) -> frozenset:
    t = _normalise(text)
    if len(t) < 3:
        return frozenset()
    return frozenset(t[i:i+3] for i in range(len(t) - 2))


def _word_count(text: str) -> int:
    return len(text.split()) if text else 0


def _length_bonus(text: str) -> float:
    import math
    wc = _word_count(text)
    if wc < 3:
        return -0.05
    raw = math.log2(max(1, wc) / max(1, LENGTH_BONUS_PIVOT))
    return max(-0.10, min(LENGTH_BONUS_MAX, raw * 0.12))


def _apply_type_multiplier(score: float, hit_type: str) -> float:
    mult = TYPE_SCORE_MULTIPLIER.get(hit_type.lower() if hit_type else "", 1.0)
    return min(1.0, score * mult)


def _score_hit(raw_score: float, text: str, hit_type: str) -> float:
    typed = _apply_type_multiplier(raw_score, hit_type)
    bonus = _length_bonus(text)
    return min(1.0, max(0.0, typed + bonus))

# Minimum score floor for graph-native hits so they survive quota sorting
GRAPH_HIT_SCORE_FLOOR: float = 0.45

# When a hit has no vector score, blend graph_score at full weight
GRAPH_ONLY_ALPHA: float = 0.80   # weight on graph_score when vector_score == 0


def _ensure_graph_hit_score(hit: "ScoredHit") -> "ScoredHit":
    """
    Re-compute the .score for a graph-native hit so it is competitive
    with vector hits.

    Logic:
      - If vector_score > 0 the hit was already blended in _rerank_with_graph.
      - If vector_score == 0 (pure graph hit): compute score from graph_score
        alone, weighted by GRAPH_ONLY_ALPHA, with type multiplier + length bonus.
      - Apply GRAPH_HIT_SCORE_FLOOR so the hit is never invisible.
    """
    if hit.vector_score > 0:
        # Already has a vector component — just ensure the floor
        hit.score = max(hit.score, GRAPH_HIT_SCORE_FLOOR * 0.85)
        return hit

    hit_type = hit.metadata.get("type", hit.source).lower()
    mult = TYPE_SCORE_MULTIPLIER.get(hit_type, TYPE_SCORE_MULTIPLIER.get("unknown", 0.85))

    import math
    wc = len(hit.text.split()) if hit.text else 0
    if wc < 3:
        lb = -0.05
    else:
        raw = math.log2(max(1, wc) / max(1, 30))
        lb = max(-0.10, min(0.30, raw * 0.12))

    blended = min(1.0, GRAPH_ONLY_ALPHA * hit.graph_score * mult + lb)
    hit.score = max(GRAPH_HIT_SCORE_FLOOR, blended)
    return hit



def _elapsed_ms(t0: float) -> float:
    return (time.monotonic() - t0) * 1000.0


def _extract_keywords(query: str) -> List[str]:
    """
    Extract significant keywords from a query string.
    Strips stop-words, keeps tokens >= MIN_KEYWORD_LEN.
    Returns a de-duped ordered list, longest first.
    """
    tokens = _normalise(query).split()
    seen: Set[str] = set()
    keywords: List[str] = []
    for tok in tokens:
        if len(tok) >= MIN_KEYWORD_LEN and tok not in _STOP_WORDS and tok not in seen:
            keywords.append(tok)
            seen.add(tok)
    # Sort longest first — longer tokens are more specific
    keywords.sort(key=len, reverse=True)
    return keywords[:12]


def _expand_queries(query: str) -> List[str]:
    """
    Generate sub-queries that target different aspects of the original.

    Strategy:
    1. Original query (unchanged)
    2. Keyword-only query (space-joined significant tokens)
    3. First half of keywords (topic focus)
    4. Second half of keywords (detail focus)

    These target different points in embedding space and together cover
    "related but not similar" content that a single query would miss.
    """
    queries = [query]
    kws = _extract_keywords(query)
    if not kws:
        return queries

    # Keyword-only variant
    kw_query = " ".join(kws)
    if kw_query and kw_query.lower() != query.lower()[:len(kw_query)]:
        queries.append(kw_query)

    # Split halves for long keyword lists
    if len(kws) >= 4:
        half = len(kws) // 2
        q1 = " ".join(kws[:half])
        q2 = " ".join(kws[half:])
        if q1 and q1 != kw_query:
            queries.append(q1)
        if q2 and q2 != kw_query:
            queries.append(q2)

    return list(dict.fromkeys(queries))[:EXPAND_SUBQUERY_COUNT + 1]


def _raw_hits_to_scored(
    hits: List[Dict[str, Any]], source: str
) -> List["ScoredHit"]:
    result: List[ScoredHit] = []
    for h in hits:
        text      = (h.get("text") or "").strip()
        hit_type  = h.get("metadata", {}).get("type", "").lower()
        raw_score = float(h.get("score") or (1.0 - (h.get("distance") or 0.5)))
        if not text:
            continue
        result.append(ScoredHit(
            text=text,
            score=_score_hit(raw_score, text, hit_type),
            vector_score=raw_score,
            graph_score=0.0,
            source=source,
            metadata={**h.get("metadata", {}), "id": h.get("id", "")},
        ))
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ConversationTurn:
    role: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScoredHit:
    """
    A single retrieval result with a unified relevance score.

    source values:
        "vector_session"    — ChromaDB session collection (session-filtered)
        "vector_longterm"   — ChromaDB long-term collection
        "vector_xsession"   — cross-session vector search (no filter)
        "keyword_neo4j"     — Neo4j full-text keyword search
        "entity_recall"     — entity-name guided graph recall
        "graph_traverse"    — probabilistic graph path traversal
        "graph_rerank"      — vector hit boosted by graph proximity
        "recalled_exchange" — cross-session pair recalled via hybrid stack
        "neighbour_swap"    — graph neighbour injected in place of a near-dupe
        "chunk_reassembled" — chunk merged back into its parent document
    """
    text: str
    score: float
    source: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    graph_score:  float = 0.0
    vector_score: float = 0.0
    keyword_score: float = 0.0


@dataclass
class GraphContext:
    entities:       List[Dict[str, Any]] = field(default_factory=list)
    relations:      List[Dict[str, Any]] = field(default_factory=list)
    focus_entities: List[str] = field(default_factory=list)


@dataclass
class VectorContext:
    session_hits:  List[Dict[str, Any]] = field(default_factory=list)
    longterm_hits: List[Dict[str, Any]] = field(default_factory=list)
    ranked_hits:   List[ScoredHit] = field(default_factory=list)


@dataclass
class MemoryContext:
    query:      str
    stage:      str
    history:    List[ConversationTurn] = field(default_factory=list)
    vectors:    VectorContext = field(default_factory=VectorContext)
    graph:      GraphContext  = field(default_factory=GraphContext)
    focus:      str = ""
    tool_names: List[str] = field(default_factory=list)
    session_id: str = ""
    elapsed_ms: float = 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Context profiles
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ContextProfile:
    history_turns:    int   = 0
    vector_session:   bool  = False
    vector_longterm:  bool  = False
    graph_entities:   bool  = False
    graph_traverse:   bool  = False
    graph_rerank:     bool  = False
    keyword_search:   bool  = False   # v6: Neo4j full-text search
    entity_recall:    bool  = False   # v6: entity-guided recall
    multi_query:      bool  = False   # v6: sub-query expansion
    include_focus:    bool  = False
    include_tools:    bool  = False
    vector_k:         int   = 3
    max_history_chars: Optional[int] = None
    budget_ms:        float = 2000.0


PROFILES: Dict[str, ContextProfile] = {
    "triage": ContextProfile(
        include_focus=True,
        include_tools=True,
        budget_ms=300.0,
    ),
    "preamble": ContextProfile(
        history_turns=6,
        vector_session=True,
        keyword_search=True,
        graph_rerank=True,
        include_focus=True,
        vector_k=5,
        max_history_chars=1200,
        budget_ms=1200.0,
    ),
    "general": ContextProfile(
        history_turns=8,
        vector_session=True,
        vector_longterm=True,
        keyword_search=True,
        entity_recall=True,
        graph_rerank=True,
        include_focus=True,
        vector_k=6,
        max_history_chars=2500,
        budget_ms=2000.0,
    ),
    "intermediate": ContextProfile(
        history_turns=10,
        vector_session=True,
        vector_longterm=True,
        keyword_search=True,
        entity_recall=True,
        multi_query=True,
        graph_rerank=True,
        include_focus=True,
        vector_k=8,
        max_history_chars=3500,
        budget_ms=4000.0,
    ),
    "reasoning": ContextProfile(
        history_turns=12,
        vector_session=True,
        vector_longterm=True,
        keyword_search=True,
        entity_recall=True,
        multi_query=True,
        graph_entities=True,
        graph_traverse=True,
        graph_rerank=True,
        include_focus=True,
        vector_k=10,
        max_history_chars=5000,
        budget_ms=7000.0,
    ),
    "action": ContextProfile(
        history_turns=5,
        vector_session=True,
        vector_longterm=True,
        keyword_search=True,
        graph_rerank=True,
        include_focus=True,
        vector_k=5,
        max_history_chars=1000,
        budget_ms=1000.0,
    ),
    "conclusion": ContextProfile(budget_ms=100.0),
    "coding": ContextProfile(
        history_turns=6,
        vector_session=True,
        vector_longterm=True,
        keyword_search=True,
        entity_recall=True,
        multi_query=True,
        graph_rerank=True,
        include_focus=True,
        vector_k=6,
        max_history_chars=2000,
        budget_ms=1500.0,
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# Dedup + merge
# ─────────────────────────────────────────────────────────────────────────────

def _dedup_hits(
    hits: List[ScoredHit],
) -> Tuple[List[ScoredHit], Set[str]]:
    """
    Deduplicate a list of ScoredHit objects.

    Pass 1 — exact normalised-text dedup (keep highest-scored copy).
    Pass 2 — trigram near-dupe detection for short texts.

    Returns (deduped_sorted, dupe_node_ids).
    dupe_node_ids feeds the neighbour-swap mechanism.
    """
    dupe_ids: Set[str] = set()

    # Pass 1: exact dedup
    best: Dict[str, ScoredHit] = {}
    for h in hits:
        key = _fingerprint(h.text)
        if not key:
            continue
        if key not in best or h.score > best[key].score:
            if key in best:
                old = best[key]
                nid = old.metadata.get("node_id") or old.metadata.get("id")
                if nid:
                    dupe_ids.add(str(nid))
            best[key] = h

    # Pass 2: trigram near-dupe
    deduped: List[ScoredHit] = []
    accepted_tgs: List[frozenset] = []

    for h in sorted(best.values(), key=lambda x: x.score, reverse=True):
        if len(h.text) > TRIGRAM_MAX_LEN:
            deduped.append(h)
            continue
        tg = _trigrams(h.text)
        if not tg:
            deduped.append(h)
            continue
        is_dupe = any(
            len(tg & atg) / max(len(tg | atg), 1) > TRIGRAM_THRESHOLD
            for atg in accepted_tgs
        )
        if is_dupe:
            nid = h.metadata.get("node_id") or h.metadata.get("id")
            if nid:
                dupe_ids.add(str(nid))
        else:
            deduped.append(h)
            accepted_tgs.append(tg)

    return deduped, dupe_ids


# ─────────────────────────────────────────────────────────────────────────────
# ContextProbe
# ─────────────────────────────────────────────────────────────────────────────

class ContextProbe:
    """
    Multi-strategy hybrid memory retrieval for Vera.

    Strategies (v6):
        Vector (session-filtered)   — cosine similarity within current session
        Vector (long-term)          — cosine similarity across promoted/long-term store
        Multi-query expansion       — 3 sub-queries covering different semantic facets
        Neo4j keyword search        — BM25-style full-text token matching
        Entity-guided recall        — entity name → graph walk → originating memory
        Graph heat-map traversal    — hop-scored proximity from anchor nodes
        Graph rerank                — vector hits re-scored with graph proximity
        Neighbour swap              — dupes replaced by their graph neighbours
        Chunk reassembly            — file chunks merged back into full documents
    """

    def __init__(self, vera_instance):
        self.vera = vera_instance
        self._fulltext_index_ok: Optional[bool] = None   # lazy check

    # ──────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────

    def probe(self, query: str, stage: str = "general") -> MemoryContext:
        profile = PROFILES.get(stage, PROFILES["general"])
        return self._run_profile(query, stage, profile)

    def probe_custom(
        self, query: str, profile: ContextProfile, stage: str = "custom"
    ) -> MemoryContext:
        return self._run_profile(query, stage, profile)

    # ──────────────────────────────────────────────────────────────────────
    # Core runner
    # ──────────────────────────────────────────────────────────────────────

    def _run_profile(
        self, query: str, stage: str, profile: ContextProfile
    ) -> MemoryContext:
        t0  = time.monotonic()
        ctx = MemoryContext(query=query, stage=stage)

        try:
            ctx.session_id = self.vera.sess.id
        except Exception:
            ctx.session_id = ""

        if profile.include_focus:
            ctx.focus = self._get_focus()

        if profile.include_tools:
            ctx.tool_names = self._get_tool_names()

        if self._over_budget(t0, profile.budget_ms, 50):
            ctx.elapsed_ms = _elapsed_ms(t0)
            return ctx

        # Pre-compute keyword variants once — shared across strategies
        keywords    = _extract_keywords(query)
        sub_queries = _expand_queries(query) if profile.multi_query else [query]

        # Anchor IDs for graph operations
        anchor_ids: List[str] = []
        needs_anchors = (
            profile.graph_rerank or profile.graph_traverse or profile.graph_entities
        ) and bool(ctx.session_id)

        if needs_anchors and not self._over_budget(t0, profile.budget_ms, 200):
            anchor_ids = self._get_session_anchor_ids(ctx.session_id)

        # ── Parallel workers ───────────────────────────────────────────────
        futures: Dict[str, Future] = {}

        with ThreadPoolExecutor(max_workers=6, thread_name_prefix="ctx_probe") as pool:

            if profile.history_turns > 0 and not self._over_budget(t0, profile.budget_ms, 100):
                futures["history"] = pool.submit(
                    self._get_history,
                    turns=profile.history_turns,
                    max_chars=profile.max_history_chars,
                )

            if profile.vector_session and ctx.session_id and not self._over_budget(t0, profile.budget_ms, 200):
                futures["session_vec"] = pool.submit(
                    self._query_session_vectors,
                    sub_queries=sub_queries,
                    session_id=ctx.session_id,
                    k=profile.vector_k,
                )

            if profile.vector_longterm and not self._over_budget(t0, profile.budget_ms, 300):
                futures["longterm_vec"] = pool.submit(
                    self._query_longterm_vectors,
                    sub_queries=sub_queries,
                    k=profile.vector_k,
                )

            if profile.keyword_search and not self._over_budget(t0, profile.budget_ms, 300):
                futures["keyword"] = pool.submit(
                    self._query_neo4j_keywords,
                    keywords=keywords,
                    session_id=ctx.session_id,
                )

            if profile.entity_recall and keywords and not self._over_budget(t0, profile.budget_ms, 400):
                futures["entity_recall"] = pool.submit(
                    self._entity_guided_recall,
                    keywords=keywords,
                    session_id=ctx.session_id,
                )

            if profile.graph_traverse and anchor_ids and not self._over_budget(t0, profile.budget_ms, 500):
                futures["graph_traverse"] = pool.submit(
                    self._graph_heat_map,
                    session_id=ctx.session_id,
                    anchor_ids=anchor_ids,
                    query=query,
                )

            if profile.graph_entities and ctx.session_id and not self._over_budget(t0, profile.budget_ms, 500):
                futures["graph_entities"] = pool.submit(
                    self._query_session_graph,
                    query=query,
                    session_id=ctx.session_id,
                )

            if profile.vector_longterm and not self._over_budget(t0, profile.budget_ms, 600):
                futures["past_exchanges"] = pool.submit(
                    self._recall_past_exchanges,
                    query=query,
                    k=profile.vector_k,
                    anchor_ids=anchor_ids,
                )

            deadline = t0 + profile.budget_ms / 1000.0
            session_vec_hits:  List[Dict[str, Any]] = []
            longterm_vec_hits: List[Dict[str, Any]] = []
            keyword_hits:      List[ScoredHit]      = []
            entity_hits:       List[ScoredHit]      = []
            graph_traverse_hits: List[ScoredHit]    = []
            past_exchange_hits:  List[ScoredHit]    = []

            for name, fut in futures.items():
                remaining = max(0.0, deadline - time.monotonic())
                try:
                    result = fut.result(timeout=remaining)
                    match name:
                        case "history":
                            ctx.history = result or []
                        case "session_vec":
                            session_vec_hits = result or []
                        case "longterm_vec":
                            longterm_vec_hits = result or []
                        case "keyword":
                            keyword_hits = result or []
                        case "entity_recall":
                            entity_hits = result or []
                        case "graph_traverse":
                            graph_traverse_hits = result or []
                        case "past_exchanges":
                            past_exchange_hits = result or []
                        case "graph_entities":
                            ctx.graph = result or GraphContext()
                except Exception as e:
                    logger.debug(f"[ContextProbe] worker '{name}' failed: {e}")

        ctx.vectors.session_hits  = session_vec_hits
        ctx.vectors.longterm_hits = longterm_vec_hits

        # ── Build initial scored list ──────────────────────────────────────
        all_vector_hits: List[ScoredHit] = []
        raw_for_rerank  = session_vec_hits + longterm_vec_hits

        if (
            profile.graph_rerank
            and anchor_ids
            and raw_for_rerank
            and not self._over_budget(t0, profile.budget_ms, 100)
        ):
            reranked = self._rerank_with_graph(
                hits=raw_for_rerank,
                anchor_ids=anchor_ids,
                query=query,
            )
            all_vector_hits.extend(reranked)
        else:
            all_vector_hits.extend(_raw_hits_to_scored(session_vec_hits,  "vector_session"))
            all_vector_hits.extend(_raw_hits_to_scored(longterm_vec_hits, "vector_longterm"))

        # Merge all strategy results
        all_vector_hits.extend(graph_traverse_hits)
        all_vector_hits.extend(past_exchange_hits)
        all_vector_hits.extend(keyword_hits)
        all_vector_hits.extend(entity_hits)

        # ── Chunk reassembly ───────────────────────────────────────────────
        # Do this before dedup so sibling chunks don't survive
        if not self._over_budget(t0, profile.budget_ms, 200):
            all_vector_hits = self._reassemble_chunks(all_vector_hits)

        # ── Dedup ─────────────────────────────────────────────────────────
        deduped, dupe_ids = _dedup_hits(all_vector_hits)

        # ── Neighbour swap ────────────────────────────────────────────────
        already_seen = {h.text for h in deduped}
        if dupe_ids and not self._over_budget(t0, profile.budget_ms, 150):
            swap_hits = self._fetch_neighbours_for_dupes(
                dupe_node_ids=dupe_ids,
                already_seen=already_seen,
            )
            if swap_hits:
                combined, _ = _dedup_hits(deduped + swap_hits)
                deduped = combined

        # ── Apply source quotas + type caps ────────────────────────────────
        final = _apply_quotas_and_caps(deduped, ctx.session_id)

        ctx.vectors.ranked_hits = final

        ctx.elapsed_ms = _elapsed_ms(t0)
        logger.debug(
            f"[ContextProbe] stage={stage} elapsed={ctx.elapsed_ms:.0f}ms "
            f"history={len(ctx.history)} "
            f"session_vec={len(session_vec_hits)} "
            f"longterm_vec={len(longterm_vec_hits)} "
            f"keyword={len(keyword_hits)} entity={len(entity_hits)} "
            f"graph_trav={len(graph_traverse_hits)} "
            f"ranked={len(final)} "
            f"entities={len(ctx.graph.entities)} "
            f"anchors={len(anchor_ids)} dupe_swapped={len(dupe_ids)}"
        )
        return ctx

    # ──────────────────────────────────────────────────────────────────────
    # Anchor node discovery
    # ──────────────────────────────────────────────────────────────────────

    def _get_session_anchor_ids(self, session_id: str) -> List[str]:
        try:
            cypher = """
            MATCH (s:Session {id: $sid})-[r]-(n)
            WHERE type(r) IN ['EXTRACTED_IN', 'FOCUSES_ON', 'HAS_MEMORY',
                              'PERFORMED_TOOL_EXECUTION', 'FOLLOWS']
               OR r.rel  IN ['EXTRACTED_IN', 'FOCUSES_ON', 'HAS_MEMORY',
                              'PERFORMED_TOOL_EXECUTION', 'FOLLOWS']
            RETURN DISTINCT n.id AS id
            LIMIT 80
            """
            with self.vera.mem.graph._driver.session() as neo_sess:
                result = neo_sess.run(cypher, {"sid": session_id})
                ids = [rec["id"] for rec in result if rec["id"]]
            logger.debug(f"[ContextProbe] {len(ids)} anchor nodes for {session_id}")
            return ids
        except Exception as e:
            logger.debug(f"[ContextProbe] anchor discovery failed: {e}")
            return []

    # ──────────────────────────────────────────────────────────────────────
    # Session vector query — PRIMARY retrieval, session-scoped first
    # ──────────────────────────────────────────────────────────────────────

    def _query_session_vectors(
        self,
        sub_queries: List[str],
        session_id: str,
        k: int,
    ) -> List[Dict[str, Any]]:
        """
        Session-scoped vector search with multi-query expansion.

        FIXED in v6:
          - Always queries with session_id filter FIRST (was missing in v5).
          - Runs each sub-query variant and merges by max score.
          - Applies recency boost for current-session hits.
          - Chunk reassembly happens in the caller after merge.
        """
        try:
            vec = self.vera.mem.vec
            id_to_hit: Dict[str, Dict[str, Any]] = {}

            for sq in sub_queries:
                # Session-scoped search
                session_hits = vec.query(
                    collection="vera_memory",
                    text=sq,
                    n_results=k * 6,
                    where={"session_id": {"$eq": session_id}},
                )
                for h in session_hits:
                    hid = h.get("id")
                    if not hid:
                        continue
                    text     = (h.get("text") or "").strip()
                    hit_type = h.get("metadata", {}).get("type", "").lower()
                    distance = h.get("distance") or 0.5
                    raw_s    = min(1.0, (1.0 - distance) + RECENCY_BOOST)
                    score    = _score_hit(raw_s, text, hit_type)
                    if hid not in id_to_hit or score > id_to_hit[hid]["score"]:
                        id_to_hit[hid] = {
                            **h,
                            "text":         text,
                            "score":        score,
                            "_source":      "vector_session",
                            "_recency":     True,
                        }

                # Cross-session supplement (without session filter) — lower base score
                if sq == sub_queries[0]:   # only for main query to avoid over-fetching
                    xsession_hits = vec.query(
                        collection="vera_memory",
                        text=sq,
                        n_results=k * 4,
                        where=None,
                    )
                    for h in xsession_hits:
                        hid = h.get("id")
                        if not hid or hid in id_to_hit:
                            continue   # already have this with recency boost
                        text     = (h.get("text") or "").strip()
                        hit_type = h.get("metadata", {}).get("type", "").lower()
                        raw_s    = 1.0 - (h.get("distance") or 0.5)
                        score    = _score_hit(raw_s, text, hit_type)
                        id_to_hit[hid] = {
                            **h,
                            "text":    text,
                            "score":   score,
                            "_source": "vector_xsession",
                            "_recency": False,
                        }

            if not id_to_hit:
                return []

            # Sort and return top results as plain dicts
            results = sorted(id_to_hit.values(), key=lambda x: x["score"], reverse=True)
            results = results[:k * 5]

            # Convert to the standard hit format expected by callers
            final = []
            for h in results:
                final.append({
                    "id":       h.get("id", ""),
                    "text":     h["text"],
                    "score":    h["score"],
                    "metadata": {
                        **h.get("metadata", {}),
                        "collection": "vera_memory",
                        "_source":    h.get("_source", "vector_session"),
                        "_recency":   h.get("_recency", False),
                    },
                })

            logger.debug(
                f"[ContextProbe] session_vectors: {len(id_to_hit)} unique → "
                f"{len(final)} returned  (sub_queries={len(sub_queries)})"
            )
            return final

        except Exception as e:
            logger.debug(f"[ContextProbe] session vector query failed: {e}")
            return []

    # ──────────────────────────────────────────────────────────────────────
    # Long-term vector query with multi-query expansion
    # ──────────────────────────────────────────────────────────────────────

    def _query_longterm_vectors(
        self, sub_queries: List[str], k: int
    ) -> List[Dict[str, Any]]:
        """
        Long-term semantic search across promoted/long-term docs.
        All sub-query variants are run; results merged by max score.
        """
        try:
            id_to_hit: Dict[str, Dict[str, Any]] = {}

            for sq in sub_queries:
                raw_hits = self.vera.mem.semantic_retrieve(sq, k=k * 5)
                for h in raw_hits:
                    text = (h.get("text") or "").strip()
                    hid  = h.get("id")
                    if not text or not hid:
                        continue
                    hit_type  = h.get("metadata", {}).get("type", "").lower()
                    raw_score = 1.0 - (h.get("distance") or 0.5)
                    score     = _score_hit(raw_score, text, hit_type)
                    if hid not in id_to_hit or score > id_to_hit[hid]["score"]:
                        id_to_hit[hid] = {
                            **h,
                            "text":     text,
                            "score":    score,
                            "metadata": {**h.get("metadata", {}), "collection": "long_term_docs"},
                        }

            results = sorted(id_to_hit.values(), key=lambda x: x["score"], reverse=True)
            return results[:k * 4]

        except Exception as e:
            logger.debug(f"[ContextProbe] long-term vector query failed: {e}")
            return []

    # ──────────────────────────────────────────────────────────────────────
    # Neo4j full-text keyword search  (v6 NEW)
    # ──────────────────────────────────────────────────────────────────────

    def _ensure_fulltext_index(self) -> bool:
        """
        Lazily create the full-text index on Entity.text if it doesn't exist.
        Returns True if index is usable.
        """
        if self._fulltext_index_ok is True:
            return True
        if self._fulltext_index_ok is False:
            return False
        try:
            cypher = (
                f"CALL db.index.fulltext.createNodeIndex("
                f"'{NEO4J_FULLTEXT_INDEX}', ['Entity'], ['text'], "
                f"{{analyzer: 'english'}}) YIELD name"
            )
            with self.vera.mem.graph._driver.session() as neo_sess:
                neo_sess.run(cypher)
            self._fulltext_index_ok = True
            logger.info(f"[ContextProbe] Full-text index '{NEO4J_FULLTEXT_INDEX}' created")
            return True
        except Exception as e:
            err = str(e)
            if "already exists" in err or "EquivalentSchemaRuleAlreadyExists" in err:
                self._fulltext_index_ok = True
                return True
            logger.debug(f"[ContextProbe] Full-text index creation failed: {e}")
            self._fulltext_index_ok = False
            return False

    def _query_neo4j_keywords(
        self, keywords: List[str], session_id: str
    ) -> List[ScoredHit]:
        """
        Neo4j full-text search for nodes whose .text contains query keywords.

        Uses a Lucene query: individual keywords ORed together, with a
        phrase-match bonus for the original query.  This surfaces nodes that
        share lexical content with the query but are semantically distant from
        it in embedding space (different phrasing, different domain context).

        Falls back to a manual Cypher CONTAINS scan if full-text index is
        unavailable.
        """
        if not keywords:
            return []

        # Sanitise keywords for Lucene
        safe_kws = [re.sub(r'[^a-z0-9_\-]', '', kw) for kw in keywords]
        safe_kws = [k for k in safe_kws if k]
        if not safe_kws:
            return []

        try:
            index_ok = self._ensure_fulltext_index()
            seen_fps: Set[str] = set()
            hits: List[ScoredHit] = []

            if index_ok:
                # Build a Lucene query: "keyword1 keyword2 keyword3" with AND for specificity
                # when we have many keywords, OR when few
                if len(safe_kws) >= 3:
                    lucene_query = " AND ".join(safe_kws[:6])
                else:
                    lucene_query = " OR ".join(safe_kws)

                cypher = f"""
                CALL db.index.fulltext.queryNodes('{NEO4J_FULLTEXT_INDEX}', $lq)
                YIELD node, score
                WHERE node.text IS NOT NULL AND node.text <> ''
                RETURN
                    node.id         AS node_id,
                    node.text       AS node_text,
                    coalesce(node.type, labels(node)[0], 'unknown') AS node_type,
                    node.session_id AS node_session_id,
                    node.created_at AS created_at,
                    score           AS lucene_score
                LIMIT $lim
                """
                with self.vera.mem.graph._driver.session() as neo_sess:
                    rows = neo_sess.run(cypher, {"lq": lucene_query, "lim": FULLTEXT_LIMIT * 2})
                    for rec in rows:
                        text     = (rec["node_text"] or "").strip()
                        nid      = rec["node_id"]
                        ntype    = (rec["node_type"] or "").lower()
                        n_sess   = rec["node_session_id"] or ""
                        ls       = float(rec["lucene_score"] or 1.0)

                        if not text or not nid:
                            continue
                        fp = _fingerprint(text)
                        if fp in seen_fps:
                            continue
                        seen_fps.add(fp)

                        # Normalise lucene score (often > 1.0) to [0,1]
                        norm_score = min(1.0, ls / 10.0)

                        # Keyword coverage bonus: fraction of keywords appearing in text
                        text_lower = text.lower()
                        coverage   = sum(1 for kw in safe_kws if kw in text_lower) / len(safe_kws)
                        kw_bonus   = coverage * KEYWORD_BOOST_MAX

                        # Recency bonus if current session
                        recency    = RECENCY_BOOST if n_sess == session_id else 0.0

                        raw_s  = min(1.0, KEYWORD_HIT_BASE_SCORE * norm_score + kw_bonus + recency)
                        score  = _score_hit(raw_s, text, ntype)

                        hits.append(ScoredHit(
                            text=text,
                            score=score,
                            keyword_score=raw_s,
                            vector_score=0.0,
                            graph_score=0.0,
                            source="keyword_neo4j",
                            metadata={
                                "node_id":    nid,
                                "type":       ntype,
                                "session_id": n_sess,
                                "created_at": rec["created_at"] or "",
                                "lucene_score": ls,
                                "kw_coverage":  round(coverage, 2),
                            },
                        ))

            else:
                # Fallback: manual CONTAINS scan (slower but always works)
                # Query for each keyword separately, merge
                for kw in safe_kws[:4]:
                    cypher = """
                    MATCH (n:Entity)
                    WHERE toLower(n.text) CONTAINS $kw
                      AND n.text IS NOT NULL
                    RETURN
                        n.id         AS node_id,
                        n.text       AS node_text,
                        coalesce(n.type, labels(n)[0], 'unknown') AS node_type,
                        n.session_id AS node_session_id,
                        n.created_at AS created_at
                    LIMIT $lim
                    """
                    with self.vera.mem.graph._driver.session() as neo_sess:
                        rows = neo_sess.run(cypher, {"kw": kw, "lim": FULLTEXT_LIMIT})
                        for rec in rows:
                            text  = (rec["node_text"] or "").strip()
                            nid   = rec["node_id"]
                            ntype = (rec["node_type"] or "").lower()
                            if not text or not nid:
                                continue
                            fp = _fingerprint(text)
                            if fp in seen_fps:
                                continue
                            seen_fps.add(fp)

                            n_sess  = rec["node_session_id"] or ""
                            recency = RECENCY_BOOST if n_sess == session_id else 0.0
                            raw_s   = min(1.0, KEYWORD_HIT_BASE_SCORE * 0.6 + recency)
                            score   = _score_hit(raw_s, text, ntype)

                            hits.append(ScoredHit(
                                text=text, score=score,
                                keyword_score=raw_s, vector_score=0.0, graph_score=0.0,
                                source="keyword_neo4j",
                                metadata={
                                    "node_id":    nid, "type": ntype,
                                    "session_id": n_sess,
                                    "created_at": rec["created_at"] or "",
                                    "matched_kw": kw,
                                },
                            ))

            hits.sort(key=lambda h: h.score, reverse=True)
            logger.debug(f"[ContextProbe] keyword_search: {len(hits)} hits  kws={safe_kws[:4]}")
            return hits[:FULLTEXT_LIMIT]

        except Exception as e:
            logger.debug(f"[ContextProbe] keyword search failed: {e}")
            return []

    # ──────────────────────────────────────────────────────────────────────
    # Entity-guided recall  (v6 NEW)
    # ──────────────────────────────────────────────────────────────────────

    def _entity_guided_recall(
        self, keywords: List[str], session_id: str
    ) -> List[ScoredHit]:
        """
        Find ExtractedEntity nodes whose .text matches query keywords, then
        walk their EXTRACTED_FROM / MENTIONS_ENTITY edges to the source
        memory nodes (query/response/document).

        This surfaces memories that contain relevant entities even when the
        phrasing is completely different from the current query.
        """
        if not keywords:
            return []
        try:
            # Build an OR pattern for entity text matching
            # CASE-INSENSITIVE partial matches
            cypher = """
            UNWIND $keywords AS kw
            MATCH (e:ExtractedEntity)
            WHERE toLower(e.text) CONTAINS kw
              AND e.confidence >= 0.5
            WITH e, kw

            // Walk to source memory nodes
            OPTIONAL MATCH (e)-[:EXTRACTED_FROM|MENTIONS_ENTITY*1..2]-(mem)
            WHERE mem.text IS NOT NULL
              AND coalesce(mem.type, '') IN
                  ['query','response','document','Query','Response','Document',
                   'thought','Thought','tool_output','ToolOutput']

            WITH e.text AS entity_text, e.label AS entity_label,
                 e.confidence AS entity_conf,
                 coalesce(mem, e) AS node, kw

            RETURN DISTINCT
                node.id         AS node_id,
                node.text       AS node_text,
                coalesce(node.type, labels(node)[0]) AS node_type,
                node.session_id AS node_session_id,
                node.created_at AS created_at,
                entity_text     AS entity_text,
                entity_label    AS entity_label,
                entity_conf     AS entity_conf,
                kw              AS matched_keyword
            LIMIT $lim
            """
            seen_fps: Set[str] = set()
            hits: List[ScoredHit] = []

            with self.vera.mem.graph._driver.session() as neo_sess:
                rows = neo_sess.run(cypher, {
                    "keywords": [kw[:50] for kw in keywords[:8]],
                    "lim": ENTITY_RECALL_LIMIT * 3,
                })
                for rec in rows:
                    text    = (rec["node_text"] or "").strip()
                    nid     = rec["node_id"]
                    ntype   = (rec["node_type"] or "").lower()
                    n_sess  = rec["node_session_id"] or ""
                    e_text  = rec["entity_text"] or ""
                    e_conf  = float(rec["entity_conf"] or 0.5)
                    matched = rec["matched_keyword"] or ""

                    if not text or not nid:
                        continue
                    fp = _fingerprint(text)
                    if fp in seen_fps:
                        continue
                    seen_fps.add(fp)

                    recency = RECENCY_BOOST if n_sess == session_id else 0.0
                    raw_s   = min(1.0, ENTITY_RECALL_BASE_SCORE * e_conf + recency)
                    score   = _score_hit(raw_s, text, ntype)

                    hits.append(ScoredHit(
                        text=text, score=score,
                        keyword_score=raw_s, vector_score=0.0, graph_score=e_conf,
                        source="entity_recall",
                        metadata={
                            "node_id":        nid,
                            "type":           ntype,
                            "session_id":     n_sess,
                            "created_at":     rec["created_at"] or "",
                            "entity_text":    e_text,
                            "entity_label":   rec["entity_label"] or "",
                            "entity_conf":    e_conf,
                            "matched_kw":     matched,
                        },
                    ))

            hits.sort(key=lambda h: h.score, reverse=True)
            logger.debug(f"[ContextProbe] entity_recall: {len(hits)} hits")
            return hits[:ENTITY_RECALL_LIMIT]

        except Exception as e:
            logger.debug(f"[ContextProbe] entity_guided_recall failed: {e}")
            return []

    # ──────────────────────────────────────────────────────────────────────
    # Chunk-to-parent reassembly  (v6 NEW)
    # ──────────────────────────────────────────────────────────────────────

    def _reassemble_chunks(self, hits: List[ScoredHit]) -> List[ScoredHit]:
        """
        For hits that are chunks of a larger document (metadata contains
        file_id + chunk_index), fetch all sibling chunks from Neo4j,
        sort them by chunk_index, and concatenate into a single ScoredHit
        of type "chunk_reassembled".

        Chunks are deduplicated by file_id so we don't fetch the same
        parent multiple times.  The reassembled hit inherits the highest
        score among its contributing chunks.
        """
        # Collect chunk groups
        chunk_groups: Dict[str, List[ScoredHit]] = {}  # file_id → hits
        non_chunk: List[ScoredHit] = []

        for h in hits:
            file_id = h.metadata.get("file_id")
            if file_id is not None and h.metadata.get("chunk_index") is not None:
                chunk_groups.setdefault(str(file_id), []).append(h)
            else:
                non_chunk.append(h)

        if not chunk_groups:
            return hits

        reassembled: List[ScoredHit] = list(non_chunk)

        for file_id, chunk_hits in chunk_groups.items():
            try:
                cypher = """
                MATCH (n:Entity)
                WHERE n.metadata IS NOT NULL
                  AND ANY(m IN [n] WHERE n.file_id = $fid OR
                       apoc.convert.fromJsonMap(n.metadata).file_id = $fid)
                RETURN n.id AS node_id, n.text AS node_text,
                       toInteger(n.chunk_index) AS chunk_index,
                       n.session_id AS session_id,
                       n.type AS node_type
                ORDER BY chunk_index ASC
                LIMIT 200
                """
                all_chunks: List[Tuple[int, str]] = []
                s_ids: List[str] = []

                with self.vera.mem.graph._driver.session() as neo_sess:
                    rows = neo_sess.run(cypher, {"fid": file_id})
                    for rec in rows:
                        txt = (rec["node_text"] or "").strip()
                        idx = rec["chunk_index"] if rec["chunk_index"] is not None else 0
                        if txt:
                            all_chunks.append((idx, txt))
                        if rec["session_id"]:
                            s_ids.append(rec["session_id"])

                if not all_chunks:
                    # Fall back: just include the highest-scored chunk
                    best_chunk = max(chunk_hits, key=lambda h: h.score)
                    reassembled.append(best_chunk)
                    continue

                all_chunks.sort(key=lambda x: x[0])
                full_text = "\n\n".join(t for _, t in all_chunks)
                if len(full_text) > MAX_REASSEMBLED_CHARS:
                    full_text = full_text[:MAX_REASSEMBLED_CHARS] + "…"

                best_score  = max(h.score for h in chunk_hits)
                best_source = max(chunk_hits, key=lambda h: h.score).source
                sess_id     = s_ids[0] if s_ids else ""

                reassembled.append(ScoredHit(
                    text=full_text,
                    score=min(1.0, best_score + 0.05),  # slight boost for full doc
                    vector_score=best_score,
                    graph_score=0.0,
                    source="chunk_reassembled",
                    metadata={
                        "file_id":     file_id,
                        "chunk_count": len(all_chunks),
                        "type":        "document",
                        "session_id":  sess_id,
                        "original_source": best_source,
                    },
                ))

            except Exception as e:
                logger.debug(f"[ContextProbe] chunk reassembly for {file_id} failed: {e}")
                best_chunk = max(chunk_hits, key=lambda h: h.score)
                reassembled.append(best_chunk)

        return reassembled

    # ──────────────────────────────────────────────────────────────────────
    # Graph heat-map traversal  (unchanged from v5)
    # ──────────────────────────────────────────────────────────────────────

    def _graph_heat_map(
        self,
        session_id: str,
        anchor_ids: List[str],
        query: str,
    ) -> List[ScoredHit]:
        if not anchor_ids:
            return []
        try:
            cypher = f"""
            MATCH (anchor)-[r1]-(hop1)
            WHERE anchor.id IN $anchor_ids
              AND hop1.id IS NOT NULL
              AND NOT hop1.id IN $anchor_ids
            WITH hop1,
                 CASE WHEN r1.rel IN $signal_rels OR type(r1) IN $signal_rels
                      THEN {HOP_DECAY} * 1.2
                      ELSE {HOP_DECAY}
                 END AS score1
            WITH hop1.id AS node_id,
                 coalesce(hop1.text, hop1.name, '') AS node_text,
                 coalesce(hop1.type, labels(hop1)[0], 'unknown') AS node_label,
                 hop1.session_id AS node_session_id,
                 hop1.created_at AS created_at,
                 max(score1) AS path_score

            UNION ALL

            MATCH (anchor)-[r1]-(hop1)-[r2]-(hop2)
            WHERE anchor.id IN $anchor_ids
              AND hop2.id IS NOT NULL
              AND NOT hop2.id IN $anchor_ids
            WITH hop2,
                 CASE WHEN r1.rel IN $signal_rels OR type(r1) IN $signal_rels
                      THEN {HOP_DECAY} * 1.2 ELSE {HOP_DECAY} END *
                 CASE WHEN r2.rel IN $signal_rels OR type(r2) IN $signal_rels
                      THEN {HOP_DECAY} * 1.2 ELSE {HOP_DECAY} END AS score2
            WITH hop2.id AS node_id,
                 coalesce(hop2.text, hop2.name, '') AS node_text,
                 coalesce(hop2.type, labels(hop2)[0], 'unknown') AS node_label,
                 hop2.session_id AS node_session_id,
                 hop2.created_at AS created_at,
                 max(score2) AS path_score

            WITH node_id, node_text, node_label, node_session_id, created_at,
                 max(path_score) AS path_score
            WHERE node_text <> '' AND path_score >= $min_score
            RETURN node_id, node_text, node_label, node_session_id, created_at, path_score
            ORDER BY path_score DESC
            LIMIT {GRAPH_TRAVERSE_LIMIT}
            """
            with self.vera.mem.graph._driver.session() as neo_sess:
                result = neo_sess.run(cypher, {
                    "anchor_ids": anchor_ids,
                    "signal_rels": list(HIGH_SIGNAL_RELS),
                    "min_score": GRAPH_HIT_MIN_SCORE,
                })
                hits: List[ScoredHit] = []
                for rec in result:
                    text = (rec["node_text"] or "").strip()
                    if not text:
                        continue
                    g_score    = float(rec["path_score"] or 0.0)
                    node_label = rec["node_label"] or ""
                    final      = _score_hit(g_score, text, node_label.lower())
                    hits.append(ScoredHit(
                        text=text,
                        score=final,
                        graph_score=g_score,
                        vector_score=0.0,
                        source="graph_traverse",
                        metadata={
                            "node_id":    rec["node_id"],
                            "node_label": node_label,
                            "type":       node_label.lower(),
                            "session_id": rec["node_session_id"] or "",
                            "created_at": rec["created_at"] or "",
                        },
                    ))
            logger.debug(
                f"[ContextProbe] graph_heat_map: {len(hits)} hits for {session_id}"
            )
            return hits
        except Exception as e:
            logger.debug(f"[ContextProbe] graph_heat_map failed: {e}")
            return []

    # ──────────────────────────────────────────────────────────────────────
    # Graph-proximity re-ranking of vector hits  (unchanged from v5)
    # ──────────────────────────────────────────────────────────────────────

    def _rerank_with_graph(
        self,
        hits: List[Dict[str, Any]],
        anchor_ids: List[str],
        query: str,
    ) -> List[ScoredHit]:
        if not hits or not anchor_ids:
            return _raw_hits_to_scored(hits, "vector_session")

        hit_ids = [
            h.get("id") or h.get("metadata", {}).get("id") or h.get("metadata", {}).get("node_id")
            for h in hits
        ]
        id_to_hit = {hid: h for h, hid in zip(hits, hit_ids) if hid}

        proximity_map: Dict[str, float] = {}
        if id_to_hit:
            try:
                cypher = f"""
                UNWIND $hit_ids AS hit_id
                MATCH (hit {{id: hit_id}})
                OPTIONAL MATCH path = shortestPath((hit)-[*1..{MAX_HOPS}]-(anchor))
                WHERE anchor.id IN $anchor_ids
                WITH hit_id,
                     CASE WHEN path IS NULL THEN 0.0
                          ELSE {HOP_DECAY} ^ (length(path) - 1)
                     END AS proximity
                RETURN hit_id, max(proximity) AS proximity
                """
                with self.vera.mem.graph._driver.session() as neo_sess:
                    result = neo_sess.run(cypher, {
                        "hit_ids": list(id_to_hit.keys()),
                        "anchor_ids": anchor_ids,
                    })
                    for rec in result:
                        hid  = rec["hit_id"]
                        prox = float(rec["proximity"] or 0.0)
                        if hid:
                            proximity_map[hid] = prox
            except Exception as e:
                logger.debug(f"[ContextProbe] rerank shortestPath failed: {e}")

        scored: List[ScoredHit] = []
        for h, hid in zip(hits, hit_ids):
            raw_vscore = h.get("score", 0.5)
            hit_type   = h.get("metadata", {}).get("type", "").lower()
            text       = h.get("text", "").strip()
            g_prox     = proximity_map.get(hid, 0.0) if hid else 0.0

            typed_vscore = _score_hit(raw_vscore, text, hit_type)
            combined     = ALPHA * typed_vscore + (1.0 - ALPHA) * g_prox

            # Preserve source metadata
            orig_source = h.get("metadata", {}).get("_source", "")
            source = "graph_rerank" if g_prox > 0.0 else (
                orig_source or (
                    "vector_session" if h.get("metadata", {}).get("_recency")
                    else "vector_longterm"
                )
            )
            scored.append(ScoredHit(
                text=text,
                score=min(1.0, combined),
                graph_score=g_prox,
                vector_score=typed_vscore,
                source=source,
                metadata={
                    **h.get("metadata", {}),
                    "id":         hid or "",
                    "node_id":    hid or "",
                    "graph_prox": round(g_prox, 3),
                },
            ))

        scored.sort(key=lambda x: x.score, reverse=True)
        return scored

    # ──────────────────────────────────────────────────────────────────────
    # Cross-session recall  (updated for v6: also passes sub-queries)
    # ──────────────────────────────────────────────────────────────────────

    def _recall_past_exchanges(
        self,
        query: str,
        k: int,
        anchor_ids: List[str],
    ) -> List[ScoredHit]:
        """
        Cross-session Q&A recall with FOLLOWS pair resolution.
        """
        try:
            vec = self.vera.mem.vec
            results: List[ScoredHit] = []
            seen_fps: Set[str] = set()

            raw_hits = vec.query(
                collection="vera_memory",
                text=query,
                n_results=k * 8,
                where=None,
            )

            if raw_hits and anchor_ids:
                reranked = vec.rerank_hits_by_graph_proximity(
                    hits=raw_hits,
                    anchor_node_ids=anchor_ids,
                    alpha=ALPHA,
                )
            else:
                reranked = [
                    {**h, "score": 1.0 - (h.get("distance") or 0.5), "graph_score": 0.0}
                    for h in raw_hits
                ]

            query_node_ids = [
                h["id"] for h in reranked
                if h.get("id")
                and h.get("metadata", {}).get("type", "").lower() == "query"
            ]

            follows_map: Dict[str, Dict[str, Any]] = {}
            if query_node_ids:
                follows_map = self._fetch_follows_pairs(query_node_ids)

            paired_resp_ids = {v["id"] for v in follows_map.values()}
            emitted_ids: Set[str] = set()

            for h in reranked:
                hid      = h.get("id")
                hit_type = h.get("metadata", {}).get("type", "").lower()
                text     = (h.get("text") or "").strip()
                raw_s    = float(h.get("score", 0.5))

                if not hid or not text or hid in emitted_ids:
                    continue
                if hit_type == "response" and hid in paired_resp_ids:
                    continue

                fp = _fingerprint(text)
                if fp in seen_fps:
                    continue
                seen_fps.add(fp)
                emitted_ids.add(hid)

                final_score = _score_hit(raw_s, text, hit_type)
                results.append(ScoredHit(
                    text=text,
                    score=min(1.0, final_score),
                    vector_score=float(h.get("vector_score", raw_s)),
                    graph_score=float(h.get("graph_score", 0.0)),
                    source="recalled_exchange",
                    metadata={
                        **h.get("metadata", {}),
                        "id":        hid,
                        "node_id":   hid,
                        "pair_role": hit_type,
                    },
                ))

                if hit_type == "query" and hid in follows_map:
                    resp     = follows_map[hid]
                    resp_txt = resp["text"].strip()
                    resp_fp  = _fingerprint(resp_txt)
                    if resp_fp not in seen_fps:
                        seen_fps.add(resp_fp)
                        emitted_ids.add(resp["id"])
                        resp_score = _score_hit(raw_s, resp_txt, "response")
                        resp_score = min(1.0, resp_score * FOLLOWS_PAIR_BOOST)
                        results.append(ScoredHit(
                            text=resp_txt,
                            score=resp_score,
                            vector_score=0.0,
                            graph_score=resp_score,
                            source="recalled_exchange",
                            metadata={
                                "node_id":           resp["id"],
                                "id":                resp["id"],
                                "pair_role":         "response",
                                "pair_of":           hid,
                                "follows_confirmed": True,
                            },
                        ))

            # Anchor-neighbour fallback
            if not results and anchor_ids:
                for anchor_id in anchor_ids[:5]:
                    try:
                        neighbour_hits = vec.get_node_neighbours_by_vector(
                            node_id=anchor_id, n_hops=2, k_per_hop=2,
                        )
                        for h in neighbour_hits:
                            hid  = h.get("id")
                            text = (h.get("text") or "").strip()
                            if not hid or not text:
                                continue
                            fp = _fingerprint(text)
                            if fp in seen_fps:
                                continue
                            seen_fps.add(fp)
                            hit_type  = h.get("metadata", {}).get("type", "").lower()
                            raw_score = 1.0 - (h.get("distance") or 0.5)
                            final     = _score_hit(raw_score * 0.8, text, hit_type)
                            results.append(ScoredHit(
                                text=text, score=min(1.0, final),
                                vector_score=raw_score, graph_score=0.5,
                                source="graph_rerank",
                                metadata={**h.get("metadata", {}), "id": hid, "node_id": hid},
                            ))
                    except Exception:
                        continue

            results.sort(key=lambda x: x.score, reverse=True)
            logger.debug(
                f"[ContextProbe] recall_past_exchanges: {len(results)} hits "
                f"({len(follows_map)} FOLLOWS pairs resolved)"
            )
            return results[:k * 5]

        except Exception as e:
            logger.debug(f"[ContextProbe] _recall_past_exchanges failed: {e}")
            return []

    # ──────────────────────────────────────────────────────────────────────
    # Neighbour swap  (unchanged from v5)
    # ──────────────────────────────────────────────────────────────────────

    def _fetch_neighbours_for_dupes(
        self,
        dupe_node_ids: Set[str],
        already_seen: Set[str],
    ) -> List[ScoredHit]:
        if not dupe_node_ids:
            return []
        try:
            cypher = """
            UNWIND $dupe_ids AS dupe_id
            MATCH (dupe {id: dupe_id})-[r]-(neighbour)
            WHERE (
                neighbour.type IN $accept_types
                OR toLower(labels(neighbour)[0]) IN $accept_labels
            )
            AND neighbour.text IS NOT NULL
            AND neighbour.text <> ''
            WITH dupe_id, neighbour,
                 CASE WHEN type(r) IN $signal_rels OR r.rel IN $signal_rels
                      THEN 1.2 ELSE 1.0
                 END AS edge_weight
            ORDER BY edge_weight DESC
            WITH dupe_id, collect(neighbour)[0..$k] AS neighbours
            UNWIND neighbours AS n
            RETURN DISTINCT
                n.id         AS node_id,
                n.text       AS node_text,
                n.type       AS node_type,
                n.session_id AS node_session_id,
                n.created_at AS created_at,
                labels(n)[0] AS node_label
            LIMIT 80
            """
            with self.vera.mem.graph._driver.session() as neo_sess:
                result = neo_sess.run(cypher, {
                    "dupe_ids":      list(dupe_node_ids),
                    "accept_types":  list(NEIGHBOUR_SWAP_TYPES),
                    "accept_labels": [t.lower() for t in NEIGHBOUR_SWAP_TYPES],
                    "signal_rels":   list(HIGH_SIGNAL_RELS),
                    "k":             NEIGHBOUR_SWAP_K,
                })

                hits: List[ScoredHit] = []
                seen_fps = {_fingerprint(t) for t in already_seen}

                for rec in result:
                    text = (rec["node_text"] or "").strip()
                    if not text:
                        continue
                    fp = _fingerprint(text)
                    if fp in seen_fps:
                        continue
                    seen_fps.add(fp)

                    node_type = rec["node_type"] or rec["node_label"] or ""
                    score     = _score_hit(NEIGHBOUR_SWAP_SCORE, text, node_type.lower())
                    hits.append(ScoredHit(
                        text=text,
                        score=score,
                        graph_score=score,
                        vector_score=0.0,
                        source="neighbour_swap",
                        metadata={
                            "node_id":    rec["node_id"],
                            "id":         rec["node_id"],
                            "node_label": node_type,
                            "type":       node_type.lower(),
                            "session_id": rec["node_session_id"] or "",
                            "created_at": rec["created_at"] or "",
                            "swap_origin": "near_dupe_neighbour",
                        },
                    ))

            logger.debug(
                f"[ContextProbe] _fetch_neighbours_for_dupes: "
                f"{len(dupe_node_ids)} dupes → {len(hits)} neighbours injected"
            )
            return hits

        except Exception as e:
            logger.debug(f"[ContextProbe] _fetch_neighbours_for_dupes failed: {e}")
            return []

    # ──────────────────────────────────────────────────────────────────────
    # FOLLOWS pair lookup helper  (unchanged from v5)
    # ──────────────────────────────────────────────────────────────────────

    def _fetch_follows_pairs(
        self, query_node_ids: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        if not query_node_ids:
            return {}
        try:
            cypher = """
            UNWIND $q_ids AS qid
            MATCH (r)-[:REL {rel: 'FOLLOWS'}]->(q {id: qid})
            WHERE r.type IN ['response', 'Response']
              AND r.text IS NOT NULL
            RETURN qid AS q_id, r.id AS r_id, r.text AS r_text
            """
            result_map: Dict[str, Dict[str, Any]] = {}
            with self.vera.mem.graph._driver.session() as neo_sess:
                rows = neo_sess.run(cypher, {"q_ids": query_node_ids})
                for rec in rows:
                    if rec["q_id"] and rec["r_id"] and rec["r_text"]:
                        result_map[rec["q_id"]] = {
                            "id":   rec["r_id"],
                            "text": rec["r_text"],
                        }
            return result_map
        except Exception as e:
            logger.debug(f"[ContextProbe] _fetch_follows_pairs failed: {e}")
            return {}

    # ──────────────────────────────────────────────────────────────────────
    # History retrieval  (unchanged from v5)
    # ──────────────────────────────────────────────────────────────────────

    def _get_history(
        self, turns: int, max_chars: Optional[int]
    ) -> List[ConversationTurn]:
        try:
            paired = self._get_history_from_neo4j(turns, max_chars)
            if paired:
                return paired
        except Exception as e:
            logger.debug(f"[ContextProbe] Neo4j history failed: {e}")
        try:
            return self._get_history_from_langchain(turns, max_chars)
        except Exception as e:
            logger.debug(f"[ContextProbe] LangChain history failed: {e}")
        return []

    def _get_history_from_neo4j(
        self, turns: int, max_chars: Optional[int]
    ) -> List[ConversationTurn]:
        try:
            sess_id     = self.vera.sess.id
            fetch_limit = max(turns * 4, 20)
            cypher = """
            MATCH (n:Entity)
            WHERE n.session_id = $sid
              AND n.type IN ['query', 'response', 'Query', 'Response']
              AND n.text IS NOT NULL
            RETURN n.id AS id, n.type AS type, n.text AS text,
                   n.created_at AS created_at
            ORDER BY n.id ASC
            LIMIT $lim
            """
            rows = []
            with self.vera.mem.graph._driver.session() as neo_sess:
                result = neo_sess.run(cypher, {"sid": sess_id, "lim": fetch_limit})
                rows = [
                    {
                        "id":         rec["id"] or "",
                        "type":       (rec["type"] or "").lower(),
                        "text":       (rec["text"] or "").strip(),
                        "created_at": rec["created_at"] or "",
                    }
                    for rec in result if rec["id"] and rec["text"]
                ]

            if not rows:
                return []

            pairs: List[Tuple[Dict, Dict]] = []
            pending: Optional[Dict] = None
            for row in rows:
                if row["type"] in ("query",):
                    pending = row
                elif row["type"] in ("response",) and pending is not None:
                    pairs.append((pending, row))
                    pending = None

            if not pairs:
                return []

            recent        = pairs[-turns:]
            char_budget   = max_chars or 999_999
            accumulated   = 0
            results: List[ConversationTurn] = []

            for q, r in recent:
                q_text = q["text"]
                if not q_text or accumulated + len(q_text) > char_budget:
                    break
                results.append(ConversationTurn(
                    role="User", text=q_text,
                    metadata={"id": q["id"], "created_at": q["created_at"]},
                ))
                accumulated += len(q_text)

                remaining = char_budget - accumulated
                r_text    = r["text"]
                if remaining <= 0:
                    results.append(ConversationTurn(
                        role="Response", text="[response truncated]",
                        metadata={"id": r["id"]},
                    ))
                elif len(r_text) > remaining:
                    truncated = r_text[:remaining].rsplit(" ", 1)[0]
                    results.append(ConversationTurn(
                        role="Response", text=truncated + "…",
                        metadata={"id": r["id"]},
                    ))
                    accumulated += len(truncated)
                    break
                else:
                    results.append(ConversationTurn(
                        role="Response", text=r_text,
                        metadata={"id": r["id"], "created_at": r["created_at"]},
                    ))
                    accumulated += len(r_text)

            logger.debug(
                f"[ContextProbe] Neo4j history: {len(pairs)} pairs, "
                f"{len(results)//2} emitted, {accumulated} chars"
            )
            return results

        except Exception as e:
            logger.debug(f"[ContextProbe] _get_history_from_neo4j failed: {e}")
            return []

    def _get_history_from_langchain(
        self, turns: int, max_chars: Optional[int]
    ) -> List[ConversationTurn]:
        results: List[ConversationTurn] = []
        try:
            history_obj = self.vera.memory.load_memory_variables({"input": ""})
            raw_text    = str(history_obj.get("chat_history", "")).strip()
            if not raw_text:
                return []
            messages = []
            for line in raw_text.splitlines():
                if line.startswith("Human:"):
                    messages.append(("User", line[6:].strip()))
                elif line.startswith("AI:"):
                    messages.append(("Response", line[3:].strip()))
            recent      = messages[-turns * 2:]
            char_budget = max_chars or 999_999
            accumulated = 0
            for role, text in recent:
                if accumulated + len(text) > char_budget:
                    break
                results.append(ConversationTurn(role=role, text=text))
                accumulated += len(text)
        except Exception as e:
            logger.debug(f"[ContextProbe] LangChain history failed: {e}")
        return results

    # ──────────────────────────────────────────────────────────────────────
    # Graph entity query  (enriched with session_id for Inspector)
    # ──────────────────────────────────────────────────────────────────────

    def _query_session_graph(self, query: str, session_id: str) -> GraphContext:
        gc = GraphContext()
        try:
            with self.vera.mem.graph._driver.session() as neo_sess:
                result = neo_sess.run(
                    """
                    MATCH (s:Session {id: $sid})-[:EXTRACTED_IN]-(e:ExtractedEntity)
                    WHERE e.confidence >= 0.5
                    RETURN e.text AS text, e.type AS label,
                           e.confidence AS confidence, e.id AS id,
                           e.session_id AS session_id, e.created_at AS created_at
                    ORDER BY e.confidence DESC
                    LIMIT 40
                    """,
                    {"sid": session_id},
                )
                for rec in result:
                    gc.entities.append({
                        "text":       rec["text"],
                        "label":      rec["label"],
                        "confidence": rec["confidence"],
                        "id":         rec["id"],
                        "session_id": rec.get("session_id", ""),
                        "created_at": rec.get("created_at", ""),
                    })

            with self.vera.mem.graph._driver.session() as neo_sess:
                result = neo_sess.run(
                    """
                    MATCH (s:Session {id: $sid})-[:FOCUSES_ON]->(e)
                    RETURN e.text AS text, e.type AS label
                    LIMIT 10
                    """,
                    {"sid": session_id},
                )
                for rec in result:
                    name = rec.get("text") or rec.get("label") or ""
                    if name:
                        gc.focus_entities.append(name)

        except Exception as e:
            logger.debug(f"[ContextProbe] graph entity query failed: {e}")
        return gc

    # ──────────────────────────────────────────────────────────────────────
    # Simple getters
    # ──────────────────────────────────────────────────────────────────────

    def _get_focus(self) -> str:
        try:
            focus = self.vera.focus_manager.focus
            return str(focus).strip() if focus else ""
        except Exception:
            return ""

    def _get_tool_names(self) -> List[str]:
        try:
            if hasattr(self.vera, 'tools') and self.vera.tools:
                return [t.name for t in self.vera.tools if hasattr(t, 'name')]
        except Exception:
            pass
        try:
            reg = getattr(self.vera.orchestrator, 'task_registry', {})
            return list(reg.keys())[:30]
        except Exception:
            pass
        return []

    # ──────────────────────────────────────────────────────────────────────
    # Budget helper
    # ──────────────────────────────────────────────────────────────────────

    @staticmethod
    def _over_budget(t0: float, budget_ms: float, reserve_ms: float = 0) -> bool:
        elapsed = (time.monotonic() - t0) * 1000
        return elapsed + reserve_ms >= budget_ms


# ─────────────────────────────────────────────────────────────────────────────
# Post-processing: source quotas + type caps
# ─────────────────────────────────────────────────────────────────────────────

# Per-strategy quotas (independent buckets, not shared)
_STRATEGY_QUOTAS = {
    "vector_session":    16,
    "vector_xsession":    6,
    "graph_rerank":      12,   # reranked vector hits (hybrid)
    "vector_longterm":    8,
    "chunk_reassembled":  4,
    "graph_traverse":     6,   # NEW — was sharing SESSION_HIT_QUOTA
    "keyword_neo4j":      6,   # NEW — was sharing SESSION_HIT_QUOTA
    "entity_recall":      5,   # NEW — was sharing SESSION_HIT_QUOTA
    "neighbour_swap":     4,
    "recalled_exchange":  6,
}

_DEFAULT_QUOTA = 4


def _apply_quotas_and_caps(
    hits: "list[ScoredHit]", current_session_id: str
) -> "list[ScoredHit]":
    """
    Apply per-strategy quotas and per-type caps.

    Key change from v1:
      Each strategy has its OWN quota bucket (see _STRATEGY_QUOTAS).
      This guarantees that graph_traverse / keyword_neo4j / entity_recall
      hits always appear in the final list even when vector hits are plentiful.

    Per-type caps (SESSION_VECTOR_TYPE_CAPS) are preserved unchanged to
    prevent any single node type dominating.
    """
    from collections import defaultdict

    SESSION_VECTOR_TYPE_CAPS = {
        "query":    2,
        "response": 16,
        "document": 10,
    }

    strategy_counts: dict[str, int] = defaultdict(int)
    type_counts:     dict[str, int] = defaultdict(int)
    result: list = []

    for h in hits:
        source   = h.source
        hit_type = h.metadata.get("type", "").lower() or source

        # Per-strategy quota
        quota = _STRATEGY_QUOTAS.get(source, _DEFAULT_QUOTA)
        if strategy_counts[source] >= quota:
            continue

        # Per-type cap
        cap = SESSION_VECTOR_TYPE_CAPS.get(hit_type, 9999)
        if type_counts[hit_type] >= cap:
            continue

        result.append(h)
        strategy_counts[source] += 1
        type_counts[hit_type] += 1

    return result

