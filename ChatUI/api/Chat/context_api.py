#!/usr/bin/env python3
# vera_context_api.py
"""
FastAPI routes for the Context Inspector UI.

Endpoints:
    POST /api/context/preview        — run ContextProbe and return structured result
    POST /api/context/render_preview — run ContextBuilder and return per-section breakdown
    POST /api/context/node_neighbours — expand a graph node (for Memory Graph Explorer)
    GET  /api/context/memory         — browse / search session memory
    POST /api/context/memory/purge   — clear session memory

v6: ranked_hits with source / vector_score / graph_score / keyword_score.
v7: render_preview shows exactly which ranked_hits reach each ContextBuilder
    section (pairs / notes / graph) vs which are dropped by headroom/cap,
    with live-tunable RenderConfig knobs.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(tags=["context"])


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic models
# ─────────────────────────────────────────────────────────────────────────────

class ContextPreviewRequest(BaseModel):
    session_id: str
    query: str
    profile: str = "general"
    history_turns: int = Field(default=6, ge=0, le=20)
    vector_k: int = Field(default=3, ge=1, le=20)
    vector_session: bool = True
    vector_longterm: bool = False
    graph_entities: bool = False


class RenderConfig(BaseModel):
    """
    Tuning knobs for ContextBuilder._render_vectors.
    Sent in a render_preview request to override defaults for that call only.
    """
    headroom_multiplier: int  = Field(default=5,   ge=1,  le=20,
        description="ranked_hits[:top_n * multiplier] fed to renderer")
    max_pairs:           int  = Field(default=3,   ge=0,  le=20,
        description="Max Q/A pair blocks emitted")
    max_others:          int  = Field(default=5,   ge=0,  le=20,
        description="Max document / note bullets emitted")
    max_graph:           int  = Field(default=8,   ge=0,  le=30,
        description="Max graph-context bullets emitted")
    q_snippet_chars:     int  = Field(default=300, ge=50, le=2000)
    a_snippet_chars:     int  = Field(default=600, ge=50, le=4000)
    note_snippet_chars:  int  = Field(default=400, ge=50, le=2000)
    graph_snippet_chars: int  = Field(default=400, ge=50, le=2000)
    debug_badges:        bool = False


class RenderPreviewRequest(BaseModel):
    session_id: str
    query: str
    profile: str = "general"
    stage: str   = "general"
    history_turns: int = Field(default=6,  ge=0, le=20)
    vector_k:      int = Field(default=6,  ge=1, le=20)
    vector_session:  bool = True
    vector_longterm: bool = True
    graph_entities:  bool = True
    render_config: RenderConfig = Field(default_factory=RenderConfig)


class NodeNeighboursRequest(BaseModel):
    node_id: str
    query: str = ""
    session_id: str = ""
    n_hops: int = Field(default=2, ge=1, le=3)
    k_per_hop: int = Field(default=8, ge=1, le=20)


class PurgeRequest(BaseModel):
    session_id: str


class ConversationTurnOut(BaseModel):
    role: str
    text: str
    metadata: Dict[str, Any] = {}


class VectorHitOut(BaseModel):
    id: str = ""
    text: str
    score: float
    vector_score: float = 0.0
    graph_score: float = 0.0
    keyword_score: float = 0.0
    source: str = ""
    metadata: Dict[str, Any] = {}


class GraphEntityOut(BaseModel):
    text: str
    label: str = ""
    confidence: float = 0.0
    id: str = ""


class GraphContextOut(BaseModel):
    entities: List[GraphEntityOut] = []
    relations: List[Dict[str, Any]] = []
    focus_entities: List[str] = []


class VectorContextOut(BaseModel):
    session_hits: List[VectorHitOut] = []
    longterm_hits: List[VectorHitOut] = []
    ranked_hits: List[VectorHitOut] = []


class ContextPreviewResponse(BaseModel):
    query: str
    stage: str
    session_id: str
    focus: str = ""
    tool_names: List[str] = []
    history: List[ConversationTurnOut] = []
    vectors: VectorContextOut = VectorContextOut()
    graph: GraphContextOut = GraphContextOut()
    elapsed_ms: float = 0.0


# ── Render preview models ──────────────────────────────────────────────────

class RenderedHitOut(BaseModel):
    """A single ranked_hit annotated with render outcome."""
    id: str = ""
    text: str
    score: float
    source: str = ""
    bucket: str = ""
    # "pair_q" | "pair_a" | "note" | "graph" | "dropped_headroom" | "dropped_cap"
    drop_reason: str = ""


class RenderSectionOut(BaseModel):
    section_name: str          # "pairs" | "notes" | "graph"
    rendered_text: str         # actual text that will go to the LLM
    hits_used:    List[RenderedHitOut] = []
    hits_dropped: List[RenderedHitOut] = []
    cap_applied:  int = 0
    fetched_total: int = 0


class RenderPreviewResponse(BaseModel):
    query: str
    stage: str
    session_id: str
    full_prompt: str
    sections: List[RenderSectionOut] = []
    ranked_hits_total:   int = 0
    ranked_hits_fed:     int = 0
    ranked_hits_dropped_headroom: int = 0
    render_config: RenderConfig = Field(default_factory=RenderConfig)
    elapsed_ms: float = 0.0


class MemoryItem(BaseModel):
    id: str = ""
    type: str = "unknown"
    text: str
    score: Optional[float] = None
    created_at: Optional[str] = None
    metadata: Dict[str, Any] = {}


class MemoryBrowseResponse(BaseModel):
    items: List[MemoryItem]
    total: int
    query: str


class NodeNeighbourOut(BaseModel):
    id: str
    text: str
    type: str = ""
    score: float = 0.35
    rel: str = ""
    properties: Dict[str, Any] = {}


class NodeNeighboursResponse(BaseModel):
    source_node_id: str
    nodes: List[NodeNeighbourOut]


# ─────────────────────────────────────────────────────────────────────────────
# Dependency
# ─────────────────────────────────────────────────────────────────────────────

def _get_vera(session_id: str):
    from Vera.ChatUI.api.session import get_or_create_vera, sessions
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return get_or_create_vera(session_id)


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/context/preview
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/api/context/preview", response_model=ContextPreviewResponse)
async def context_preview(req: ContextPreviewRequest):
    vera = _get_vera(req.session_id)
    try:
        from Vera.Memory.context_probe import ContextProbe, ContextProfile

        profile = ContextProfile(
            history_turns=req.history_turns,
            vector_session=req.vector_session,
            vector_longterm=req.vector_longterm,
            graph_entities=req.graph_entities,
            include_focus=True,
            include_tools=False,
            vector_k=req.vector_k,
            budget_ms=3000.0,
            graph_rerank=True,
            graph_traverse=req.graph_entities,
            keyword_search=True,
            entity_recall=True,
            multi_query=(req.profile in ("reasoning", "intermediate", "coding")),
        )
        probe = ContextProbe(vera)
        ctx = probe.probe_custom(req.query, profile=profile, stage=req.profile)

        def _hit_to_out(h) -> VectorHitOut:
            if isinstance(h, dict):
                meta = h.get("metadata", {})
                return VectorHitOut(
                    id=h.get("id","") or meta.get("node_id","") or meta.get("id",""),
                    text=h.get("text",""), score=float(h.get("score",0.5)),
                    vector_score=float(h.get("vector_score",0.0)),
                    graph_score=float(h.get("graph_score",0.0)),
                    keyword_score=float(h.get("keyword_score",0.0)),
                    source=h.get("source","") or meta.get("_source",""),
                    metadata=meta,
                )
            return VectorHitOut(
                id=h.metadata.get("node_id","") or h.metadata.get("id",""),
                text=h.text, score=h.score,
                vector_score=h.vector_score, graph_score=h.graph_score,
                keyword_score=getattr(h,"keyword_score",0.0),
                source=h.source, metadata=h.metadata,
            )

        return ContextPreviewResponse(
            query=ctx.query, stage=ctx.stage, session_id=ctx.session_id,
            focus=ctx.focus, tool_names=ctx.tool_names,
            history=[ConversationTurnOut(role=t.role, text=t.text, metadata=t.metadata) for t in ctx.history],
            vectors=VectorContextOut(
                session_hits=[_hit_to_out(h) for h in ctx.vectors.session_hits],
                longterm_hits=[_hit_to_out(h) for h in ctx.vectors.longterm_hits],
                ranked_hits=[_hit_to_out(h) for h in ctx.vectors.ranked_hits],
            ),
            graph=GraphContextOut(
                entities=[GraphEntityOut(text=e.get("text",""), label=e.get("label",""), confidence=e.get("confidence",0.0), id=e.get("id","")) for e in ctx.graph.entities],
                focus_entities=ctx.graph.focus_entities,
            ),
            elapsed_ms=ctx.elapsed_ms,
        )
    except Exception as e:
        logger.exception(f"[context/preview] {req.session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/context/render_preview
# ─────────────────────────────────────────────────────────────────────────────

_GRAPH_SOURCES = frozenset({
    "graph_traverse","graph_rerank","keyword_neo4j",
    "entity_recall","neighbour_swap","chunk_reassembled","recalled_exchange",
})
_GRAPH_SOURCE_LABELS = {
    "graph_traverse":    "graph",
    "graph_rerank":      "graph+vec",
    "keyword_neo4j":     "keyword",
    "entity_recall":     "entity",
    "neighbour_swap":    "neighbour",
    "chunk_reassembled": "doc (reassembled)",
    "recalled_exchange": "past exchange",
}
_SOURCE_BADGE = {
    "vector_session":"🔵","vector_longterm":"🔷","graph_traverse":"🟢",
    "graph_rerank":"🔶","recalled_exchange":"🟣","keyword_neo4j":"🔍",
    "entity_recall":"🏷","neighbour_swap":"↔","chunk_reassembled":"📄",
}


@router.post("/api/context/render_preview", response_model=RenderPreviewResponse)
async def context_render_preview(req: RenderPreviewRequest):
    """
    Run ContextProbe + replicate ContextBuilder._render_vectors with full
    traceability. Returns per-section breakdowns of which ranked_hits were
    actually rendered vs dropped by headroom or caps.
    """
    import time
    t0 = time.monotonic()
    vera = _get_vera(req.session_id)

    try:
        from Vera.Memory.context_probe import ContextProbe, ContextProfile
        from Vera.Memory.context_builder import ContextBuilder

        profile = ContextProfile(
            history_turns=req.history_turns,
            vector_session=req.vector_session,
            vector_longterm=req.vector_longterm,
            graph_entities=req.graph_entities,
            include_focus=True, include_tools=True,
            vector_k=req.vector_k, budget_ms=4000.0,
            graph_rerank=True, graph_traverse=req.graph_entities,
            keyword_search=True, entity_recall=True,
            multi_query=(req.stage in ("reasoning","intermediate","coding")),
        )
        probe = ContextProbe(vera)
        ctx   = probe.probe_custom(req.query, profile=profile, stage=req.stage)
        rc    = req.render_config

        def _type(h: dict) -> str:
            return h.get("metadata", {}).get("type", "").lower()

        def _source(h: dict) -> str:
            return h.get("source", h.get("metadata", {}).get("collection", ""))

        def _hid(h: dict) -> str:
            return h.get("id","") or h.get("metadata",{}).get("node_id","") or ""

        def _rout(h: dict, bucket: str, reason: str = "") -> RenderedHitOut:
            return RenderedHitOut(
                id=_hid(h), text=h.get("text",""),
                score=h.get("score",0.0), source=_source(h),
                bucket=bucket, drop_reason=reason,
            )

        # Headroom slice
        top_n    = 5 if req.stage == "reasoning" else 4
        headroom = top_n * rc.headroom_multiplier
        total    = len(ctx.vectors.ranked_hits)

        if ctx.vectors.ranked_hits:
            raw_list = [
                {"id": h.metadata.get("id",""), "text": h.text, "score": h.score,
                 "metadata": h.metadata, "source": h.source}
                for h in ctx.vectors.ranked_hits[:headroom]
            ]
        else:
            raw_list = [h for h in (ctx.vectors.session_hits + ctx.vectors.longterm_hits)
                        if isinstance(h, dict) and h.get("text","").strip()]

        # Hits beyond headroom → dropped_headroom
        beyond: List[RenderedHitOut] = []
        if ctx.vectors.ranked_hits and len(ctx.vectors.ranked_hits) > headroom:
            for h in ctx.vectors.ranked_hits[headroom:]:
                beyond.append(RenderedHitOut(
                    id=h.metadata.get("id","") or h.metadata.get("node_id",""),
                    text=h.text, score=h.score, source=h.source,
                    bucket="dropped_headroom",
                    drop_reason=f"beyond headroom ({headroom})",
                ))

        # Split buckets
        conv       = [h for h in raw_list if _type(h) in ("query","response")]
        graph_hits = [h for h in raw_list if _type(h) not in ("query","response") and _source(h) in _GRAPH_SOURCES]
        doc_notes  = [h for h in raw_list if _type(h) not in ("query","response") and _source(h) not in _GRAPH_SOURCES]

        # ── Pairs section ────────────────────────────────────────────────────
        conv_by_id  = {_hid(h): h for h in conv if _hid(h)}
        id_order    = [_hid(h) for h in sorted(conv_by_id.values(), key=lambda h: _hid(h))]
        pairs_seen: set = set()
        pairs: list = []

        for h in conv:
            hid = _hid(h); htype = _type(h)
            if hid in pairs_seen: continue
            if htype == "query":
                pairs_seen.add(hid)
                try:
                    pos = id_order.index(hid)
                    rid = id_order[pos+1] if pos+1 < len(id_order) else None
                    r_hit = conv_by_id.get(rid) if rid else None
                    if r_hit and _type(r_hit) == "response": pairs_seen.add(rid)
                    else: r_hit = None
                except (ValueError, IndexError): r_hit = None
                pairs.append((h, r_hit, h.get("score",0.0)))
            elif htype == "response":
                pairs_seen.add(hid)
                try:
                    pos = id_order.index(hid)
                    qid = id_order[pos-1] if pos-1 >= 0 else None
                    q_hit = conv_by_id.get(qid) if qid else None
                    if q_hit and _type(q_hit) == "query" and qid not in pairs_seen:
                        pairs_seen.add(qid)
                    else: q_hit = None
                except (ValueError, IndexError): q_hit = None
                if q_hit: pairs.append((q_hit, h, h.get("score",0.0)))
                else: doc_notes.insert(0, h)

        shown_texts: set = set()
        pairs_lines: List[str] = []
        pairs_used: List[RenderedHitOut] = []
        pairs_dropped: List[RenderedHitOut] = []

        if pairs:
            pairs_lines.append("--- Relevant past exchanges ---")
            for i, (q_hit, r_hit, score) in enumerate(pairs):
                q_text = q_hit.get("text","").strip()
                if i < rc.max_pairs:
                    q_snip = q_text[:rc.q_snippet_chars] + ("…" if len(q_text) > rc.q_snippet_chars else "")
                    shown_texts.add(q_text)
                    if rc.debug_badges:
                        pairs_lines.append(f"Q{_SOURCE_BADGE.get(_source(q_hit),'⬜')}[{score:.2f}]: {q_snip}")
                    else:
                        pairs_lines.append(f"Q: {q_snip}")
                    if r_hit:
                        r_text = r_hit.get("text","").strip()
                        r_snip = r_text[:rc.a_snippet_chars] + ("…" if len(r_text) > rc.a_snippet_chars else "")
                        shown_texts.add(r_text)
                        pairs_lines.append(f"A: {r_snip}")
                    else:
                        pairs_lines.append("A: [no recorded response]")
                    pairs_lines.append("")
                    pairs_used.append(_rout(q_hit, "pair_q"))
                    if r_hit: pairs_used.append(_rout(r_hit, "pair_a"))
                else:
                    pairs_dropped.append(_rout(q_hit, "dropped_cap", f"pairs cap ({rc.max_pairs})"))
                    if r_hit: pairs_dropped.append(_rout(r_hit, "dropped_cap", f"pairs cap ({rc.max_pairs})"))

        # ── Notes section ────────────────────────────────────────────────────
        seen_other: dict = {}
        for h in doc_notes:
            t = h.get("text","").strip(); s = h.get("score",0.0)
            if t and t not in shown_texts and (t not in seen_other or s > seen_other[t][1]):
                seen_other[t] = (h, s)

        top_others = sorted(seen_other.values(), key=lambda x: x[1], reverse=True)
        notes_lines: List[str] = []
        notes_used: List[RenderedHitOut] = []
        notes_dropped: List[RenderedHitOut] = []

        if top_others:
            notes_lines.append("--- Relevant notes ---" if pairs else "--- Relevant memory ---")
            for i, (h, _) in enumerate(top_others):
                text = h.get("text","").strip()
                if i < rc.max_others:
                    snippet = text[:rc.note_snippet_chars] + ("…" if len(text) > rc.note_snippet_chars else "")
                    shown_texts.add(text)
                    notes_lines.append(f"• {_SOURCE_BADGE.get(_source(h),'⬜')} {snippet}" if rc.debug_badges else f"• {snippet}")
                    notes_used.append(_rout(h, "note"))
                else:
                    notes_dropped.append(_rout(h, "dropped_cap", f"notes cap ({rc.max_others})"))

        # ── Graph section ────────────────────────────────────────────────────
        seen_graph: dict = {}
        for h in graph_hits:
            t = h.get("text","").strip(); s = h.get("score",0.0)
            if t and t not in shown_texts and (t not in seen_graph or s > seen_graph[t][1]):
                seen_graph[t] = (h, s)

        top_graph = sorted(seen_graph.values(), key=lambda x: x[1], reverse=True)
        graph_lines: List[str] = []
        graph_used: List[RenderedHitOut] = []
        graph_dropped: List[RenderedHitOut] = []

        if top_graph:
            graph_lines.append("--- Graph context ---")
            for i, (h, score) in enumerate(top_graph):
                text = h.get("text","").strip()
                src  = _source(h)
                if i < rc.max_graph:
                    snippet = text[:rc.graph_snippet_chars] + ("…" if len(text) > rc.graph_snippet_chars else "")
                    label   = _GRAPH_SOURCE_LABELS.get(src, src)
                    graph_lines.append(
                        f"• {_SOURCE_BADGE.get(src,'⬜')}[{score:.2f}] ({label}): {snippet}"
                        if rc.debug_badges else f"• ({label}): {snippet}")
                    graph_used.append(_rout(h, "graph"))
                else:
                    graph_dropped.append(_rout(h, "dropped_cap", f"graph cap ({rc.max_graph})"))

        # ── Full prompt via ContextBuilder ───────────────────────────────────
        try:
            builder     = ContextBuilder(vera)
            full_prompt = builder.build_from_context(ctx, stage=req.stage)
        except Exception as e:
            logger.debug(f"[render_preview] ContextBuilder failed: {e}")
            full_prompt = "\n\n".join(filter(None, [
                "\n".join(pairs_lines),
                "\n".join(notes_lines),
                "\n".join(graph_lines),
            ]))

        sections: List[RenderSectionOut] = [
            RenderSectionOut(
                section_name="pairs",
                rendered_text="\n".join(pairs_lines),
                hits_used=pairs_used,
                hits_dropped=pairs_dropped,
                cap_applied=rc.max_pairs,
                fetched_total=len(pairs),
            ),
            RenderSectionOut(
                section_name="notes",
                rendered_text="\n".join(notes_lines),
                hits_used=notes_used,
                hits_dropped=notes_dropped,
                cap_applied=rc.max_others,
                fetched_total=len(top_others),
            ),
            RenderSectionOut(
                section_name="graph",
                rendered_text="\n".join(graph_lines),
                hits_used=graph_used,
                hits_dropped=graph_dropped + beyond,
                cap_applied=rc.max_graph,
                fetched_total=len(top_graph),
            ),
        ]

        return RenderPreviewResponse(
            query=req.query, stage=req.stage, session_id=req.session_id,
            full_prompt=full_prompt, sections=sections,
            ranked_hits_total=total,
            ranked_hits_fed=len(raw_list),
            ranked_hits_dropped_headroom=len(beyond),
            render_config=rc,
            elapsed_ms=(time.monotonic() - t0) * 1000,
        )

    except Exception as e:
        logger.exception(f"[context/render_preview] {req.session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/context/node_neighbours
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/api/context/node_neighbours", response_model=NodeNeighboursResponse)
async def node_neighbours(req: NodeNeighboursRequest):
    vera = _get_vera(req.session_id) if req.session_id else None
    try:
        nodes: List[NodeNeighbourOut] = []
        seen_ids: set = set()

        if vera:
            cypher = f"""
            MATCH (src {{id: $node_id}})
            CALL apoc.path.subgraphNodes(src, {{maxLevel: $n_hops, limit: {req.n_hops * req.k_per_hop * 4}}}) YIELD node
            WHERE node.id <> $node_id AND node.text IS NOT NULL AND node.text <> ''
            WITH node, coalesce(node.type, labels(node)[0], 'unknown') AS node_type
            RETURN node.id AS node_id, node.text AS node_text, node_type,
                   node.session_id AS node_session_id, node.confidence AS confidence,
                   properties(node) AS props
            LIMIT {req.n_hops * req.k_per_hop}
            """
            with vera.mem.graph._driver.session() as neo_sess:
                raw_rows = [dict(r) for r in neo_sess.run(cypher, {"node_id": req.node_id, "n_hops": req.n_hops})]

            score_map: Dict[str, float] = {}
            if req.query:
                try:
                    candidate_ids = [r["node_id"] for r in raw_rows if r.get("node_id")]
                    if candidate_ids:
                        vec_hits = vera.mem.vec.query(collection="vera_memory", text=req.query,
                                                       n_results=min(50, len(candidate_ids) * 2), where=None)
                        for h in vec_hits:
                            hid = h.get("id")
                            if hid and hid in candidate_ids:
                                score_map[hid] = 1.0 - (h.get("distance") or 0.5)
                except Exception as e:
                    logger.debug(f"[node_neighbours] re-scoring failed: {e}")

            for r in raw_rows:
                nid = r.get("node_id"); txt = (r.get("node_text") or "").strip()
                if not nid or not txt or nid in seen_ids: continue
                seen_ids.add(nid)
                score = score_map.get(nid, float(r.get("confidence") or 0.35))
                props = dict(r.get("props") or {}); props.pop("text", None)
                nodes.append(NodeNeighbourOut(
                    id=nid, text=txt, type=(r.get("node_type") or "entity").lower(),
                    score=min(1.0, max(0.0, score)), rel="", properties=props,
                ))

            nodes.sort(key=lambda n: n.score, reverse=True)
            nodes = nodes[:req.k_per_hop * req.n_hops]

        return NodeNeighboursResponse(source_node_id=req.node_id, nodes=nodes)
    except Exception as e:
        logger.exception(f"[node_neighbours] {req.node_id}: {e}")
        return NodeNeighboursResponse(source_node_id=req.node_id, nodes=[])


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/context/memory
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/api/context/memory", response_model=MemoryBrowseResponse)
async def context_memory_browse(session_id: str, query: str = "", limit: int = 60):
    vera = _get_vera(session_id)
    try:
        items: List[MemoryItem] = []

        if query.strip():
            try:
                for h in vera.mem.focus_context(session_id, query, k=limit // 2):
                    items.append(MemoryItem(id=h.get("id",""), type=h.get("metadata",{}).get("type","session"),
                        text=h.get("text",""), score=1.0-(h.get("distance") or 0.5),
                        created_at=h.get("metadata",{}).get("created_at"), metadata=h.get("metadata",{})))
            except Exception as e: logger.debug(f"Session vector search failed: {e}")
            try:
                for h in vera.mem.semantic_retrieve(query, k=limit // 2):
                    items.append(MemoryItem(id=h.get("id",""), type=h.get("metadata",{}).get("type","longterm"),
                        text=h.get("text",""), score=1.0-(h.get("distance") or 0.5),
                        created_at=h.get("metadata",{}).get("created_at"), metadata=h.get("metadata",{})))
            except Exception as e: logger.debug(f"Long-term vector search failed: {e}")
            seen: Dict[str, MemoryItem] = {}
            for item in items:
                key = item.text[:100]
                if key not in seen or (item.score or 0) > (seen[key].score or 0): seen[key] = item
            items = sorted(seen.values(), key=lambda x: x.score or 0, reverse=True)
        else:
            try:
                with vera.mem.graph._driver.session() as neo_sess:
                    for rec in neo_sess.run(
                        "MATCH (s:Session {id:$sid})-[:INCLUDES|:EXTRACTED_IN|:RELATES_TO]-(n) WHERE n.text IS NOT NULL "
                        "RETURN n.id AS id, labels(n)[0] AS type, n.text AS text, n.created_at AS created_at "
                        "ORDER BY n.created_at DESC LIMIT $lim",
                        {"sid": session_id, "lim": limit}):
                        items.append(MemoryItem(id=rec.get("id") or "", type=rec.get("type") or "node",
                            text=rec.get("text") or "", created_at=str(rec.get("created_at")) if rec.get("created_at") else None))
            except Exception as e: logger.debug(f"Neo4j browse failed: {e}")
            if not items:
                try:
                    all_docs = vera.mem.chroma_session.get(where={"session_id": session_id}, limit=limit, include=["documents","metadatas"])
                    for doc, meta, doc_id in zip(all_docs.get("documents") or [], all_docs.get("metadatas") or [], all_docs.get("ids") or []):
                        items.append(MemoryItem(id=doc_id, type=(meta or {}).get("type","vector"),
                            text=doc or "", created_at=(meta or {}).get("created_at"), metadata=meta or {}))
                except Exception as e: logger.debug(f"ChromaDB list failed: {e}")

        return MemoryBrowseResponse(items=items[:limit], total=len(items), query=query)
    except Exception as e:
        logger.exception(f"[context/memory] {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/context/memory/purge
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/api/context/memory/purge")
async def context_memory_purge(req: PurgeRequest):
    vera = _get_vera(req.session_id)
    errors = []
    try:
        with vera.mem.graph._driver.session() as neo_sess:
            neo_sess.run(
                "MATCH (s:Session {id:$sid}) OPTIONAL MATCH (s)-[*1..3]-(n) WHERE NOT n:Session DETACH DELETE n WITH s DETACH DELETE s",
                {"sid": req.session_id})
    except Exception as e: errors.append(f"Neo4j: {e}")
    try:
        existing = vera.mem.chroma_session.get(where={"session_id": req.session_id}, include=[])
        ids = existing.get("ids") or []
        if ids: vera.mem.chroma_session.delete(ids=ids)
    except Exception as e: errors.append(f"ChromaDB: {e}")
    if errors: return {"status": "partial", "errors": errors}
    return {"status": "purged", "session_id": req.session_id}

# ─────────────────────────────────────────────────────────────────────────────
# WebSocket integration note
# ─────────────────────────────────────────────────────────────────────────────
#
# In your websocket_chat handler (vera_chat.py), read context_override from
# the incoming message and pass it through to your run pipeline:
#
#   message_data = json.loads(data)
#   context_override = message_data.get("context_override")
#
#   gen = vera.async_run(
#       message,
#       routing_hints=routing_config,
#       context_override=context_override,
#   )
#
# In vera's run pipeline, if context_override is present:
#
#   if context_override:
#       from Vera.Memory.context_probe import ContextProfile
#       profile = ContextProfile(
#           history_turns=context_override.get("history_turns", 6),
#           vector_session=context_override.get("vector_session", True),
#           vector_longterm=context_override.get("vector_longterm", False),
#           graph_entities=context_override.get("graph_entities", False),
#           vector_k=context_override.get("vector_k", 3),
#           include_focus=True,
#           include_tools=True,
#           budget_ms=3000.0,
#           graph_rerank=True,
#           keyword_search=True,
#           entity_recall=True,
#       )
#       ctx = probe.probe_custom(query, profile=profile, stage=stage)
#
#       if "history_override" in context_override:
#           ctx.history = [
#               ConversationTurn(role=t["role"], text=t["text"])
#               for t in context_override["history_override"]
#           ]
#       if "focus_override" in context_override:
#           ctx.focus = context_override["focus_override"]
#       if "injected_context" in context_override:
#           from Vera.Memory.context_probe import ConversationTurn
#           ctx.history.insert(0, ConversationTurn(
#               role="System",
#               text=f"[Injected context]\n{context_override['injected_context']}"
#           ))
#
#   # Return ranked_hits in context_used so the UI reflects graph substitutions:
#   await websocket.send_json({
#       "type": "complete",
#       "context_used": {
#           "focus": ctx.focus,
#           "history": [{"role": t.role, "text": t.text} for t in ctx.history],
#           "vectors": {
#               "session_hits":  ctx.vectors.session_hits,
#               "longterm_hits": ctx.vectors.longterm_hits,
#               "ranked_hits": [
#                   {
#                       "id":            h.metadata.get("node_id","") or h.metadata.get("id",""),
#                       "text":          h.text,
#                       "score":         h.score,
#                       "vector_score":  h.vector_score,
#                       "graph_score":   h.graph_score,
#                       "keyword_score": getattr(h, "keyword_score", 0.0),
#                       "source":        h.source,
#                       "metadata":      h.metadata,
#                   }
#                   for h in ctx.vectors.ranked_hits
#               ],
#           },
#           "graph": {
#               "entities":       ctx.graph.entities,
#               "focus_entities": ctx.graph.focus_entities,
#           },
#           "elapsed_ms": ctx.elapsed_ms,
#       },
#       "timestamp": datetime.utcnow().isoformat(),
#   })