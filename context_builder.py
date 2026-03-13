#!/usr/bin/env python3
# vera_context_builder.py
from __future__ import annotations
"""
ContextBuilder — Formats MemoryContext into ready-to-send LLM prompts.

Works in two modes:
  1. Auto (recommended): calls ContextProbe internally for a given stage name.
  2. Manual: accepts a pre-built MemoryContext for callers that want to share
     a single probe result across multiple prompt builds.

Public surface:
    builder = ContextBuilder(vera_instance)

    # One-shot: probe + build
    prompt = builder.build(query, stage="preamble")
    prompt = builder.build(query, stage="reasoning", preamble="opening text…")

    # Reuse a pre-fetched context (avoids second memory round-trip)
    ctx    = builder.probe.probe(query, stage="general")
    prompt = builder.build_from_context(ctx, stage="general")

v2 change:
    _render_vectors now reads ctx.vectors.ranked_hits (the unified, graph-
    proximity-boosted list) when available, falling back to the raw
    session_hits / longterm_hits lists for backward compatibility.
    Source badges (🔵 vector / 🟢 graph / 🔶 reranked) can be optionally
    shown in debug builds via VERA_CONTEXT_DEBUG env var.
"""
"""
TODO
Integrate a skills loader and capability search
When a request comes in context surrounding useful built-in capabilities can be added to context capabilities include, skills, tools, agents, tasks, etc. 
Skills are a special category of capabilities that are more static and general-purpose than tools or agents. They represent the underlying knowledge and expertise of the system in various domains. For example, a skill could be "RICS compliance" or "Regular Expressions". These skills can be loaded into context when relevant to the user's query, providing the LLM with additional information and guidance on how to handle specific tasks.
Skills can be guidance on a particular task like "RICS compliance" or "Regular Expressions" loaded only when needed
Skills can be developed from learnings from the hybrid store
Add meta context for each neo4j/vector result who wrote it, when, and why (what query) and if it has negative or positive feedback, to help the LLM evaluate provinence relevance and reliability of each result. This could be a short "provenance" string like "User note from 2024-05-01" or "Graph node added during reasoning step". This would help the LLM weigh different pieces of context appropriately based on their source and recency.
"""
"""
Context Areas
Identity / style
Capabilities - Skills, tools, agents, etc.
Current date/time (for temporal awareness)
Current focus
Tools available
Relevant history
Relevant vector memory hits
Relevant graph entities
"""


import datetime
import logging
import os
from typing import Optional

from Vera.Memory.context_probe import ContextProbe, MemoryContext, ScoredHit

logger = logging.getLogger(__name__)

# Set VERA_CONTEXT_DEBUG=1 to see source badges in rendered context sections.
_DEBUG_BADGES = os.environ.get("VERA_CONTEXT_DEBUG", "0") == "1"

_SOURCE_BADGE = {
    "vector_session":    "🔵",
    "vector_longterm":   "🔷",
    "graph_traverse":    "🟢",
    "graph_rerank":      "🔶",
    "recalled_exchange": "🟣",
}


# ─────────────────────────────────────────────────────────────────────────────
# Identity / style
# ─────────────────────────────────────────────────────────────────────────────

VERA_IDENTITY = (
    "You are Vera, a locally-running personal AI assistant. You are composed of, and have access to, many LLM and ML models."
    "You are direct, capable, and concise. "
    "You prefer to act over explaining how you would act. "
    "You address the user as a technical peer."
)

VERA_STYLE = (
    "Response style:\n"
    "- Be well rounded and precise — no padding or filler.\n"
    "- Use markdown only when it genuinely aids readability.\n"
    # "- If executing a task, confirm in one sentence then proceed.\n"
    "- If uncertain, say so briefly rather than speculating at length."
)

VERA_CAPABILITIES = (
    "Capabilities:\n"
    "- You can access and process information from multiple sources.\n"
    "- You can are provided with recalled relevant past interactions and information effectively.\n"
    "- You can perform complex reasoning and problem-solving tasks.\n"
    "- You can generate human-like text in various styles and formats.\n"
    "- You can execute commands and interact with the user's environment."
    "- You can learn and adapt based on user interactions and feedback."
    "- You can manage and utilize tools and resources effectively to assist the user."
    "- You can maintain context and continuity across interactions to provide a cohesive user experience."
    "- You can handle multiple tasks and queries simultaneously, prioritizing them based on user needs and preferences."
    "- You can provide explanations and justifications for your actions and decisions when appropriate, while still being concise."
    "- You can think in the background while waiting for user input, preparing information or solutions proactively to enhance understanding/context, responsiveness and efficiency."
)

_S_IDENTITY     = "identity"
_S_STYLE        = "style"
_S_CAPABILITIES = "capabilities"
_S_DATETIME     = "datetime"
_S_FOCUS        = "focus"
_S_TOOLS        = "tools"
_S_HISTORY      = "history"
_S_VECTORS      = "vectors"
_S_GRAPH        = "graph"
_S_FRAME        = "frame"


# ─────────────────────────────────────────────────────────────────────────────
# Stage → section inclusion map
# ─────────────────────────────────────────────────────────────────────────────

STAGE_SECTIONS = {
    "triage": [
        _S_DATETIME,
        _S_CAPABILITIES,
        # _S_FOCUS,
        # _S_TOOLS,
        _S_FRAME,
    ],
    "preamble": [
        _S_IDENTITY,
        _S_STYLE,
        _S_CAPABILITIES,
        _S_DATETIME,
        _S_FOCUS,
        _S_HISTORY,
        _S_VECTORS,
        _S_GRAPH,
        _S_FRAME,
    ],
    "general": [
        _S_IDENTITY,
        _S_STYLE,
        _S_CAPABILITIES,
        _S_DATETIME,
        _S_FOCUS,
        _S_HISTORY,
        _S_VECTORS,
        _S_GRAPH,
        _S_FRAME,
    ],
    "intermediate": [
        _S_IDENTITY,
        _S_STYLE,
        _S_CAPABILITIES,
        _S_DATETIME,
        _S_FOCUS,
        _S_HISTORY,
        _S_VECTORS,
        _S_GRAPH,
        _S_FRAME,
    ],
    "reasoning": [
        _S_IDENTITY,
        _S_STYLE,
        _S_CAPABILITIES,
        _S_DATETIME,
        _S_FOCUS,
        _S_HISTORY,
        _S_VECTORS,
        _S_GRAPH,
        _S_FRAME,
    ],
    "action": [
        _S_CAPABILITIES,
        _S_DATETIME,
        _S_FOCUS,
        _S_HISTORY,
        _S_VECTORS,
        _S_GRAPH,
        _S_FRAME,
    ],
    "coding": [
        _S_IDENTITY,
        _S_STYLE,
        _S_DATETIME,
        _S_FOCUS,
        _S_HISTORY,  
        _S_VECTORS,   
        _S_GRAPH,
        _S_FRAME,
    ],
    "conclusion": [
        _S_FRAME,
    ],
    "continuation": [
        _S_IDENTITY,
        _S_STYLE,
        _S_CAPABILITIES,
        _S_DATETIME,
        _S_FOCUS,
        _S_HISTORY,
        _S_VECTORS,
        _S_GRAPH,
        _S_FRAME,
    ],
}

_GRAPH_SOURCES = frozenset({
    "graph_traverse",
    "graph_rerank",
    "keyword_neo4j",
    "entity_recall",
    "neighbour_swap",
    "chunk_reassembled",
    "recalled_exchange",
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

# ─────────────────────────────────────────────────────────────────────────────
# ContextBuilder
# ─────────────────────────────────────────────────────────────────────────────

class ContextBuilder:
    """
    Assembles LLM prompts with the right level of context for each stage.

    Owns a ContextProbe instance (accessible as builder.probe) so callers
    can share a single memory fetch across multiple build calls if needed.
    """

    def __init__(self, vera_instance):
        self.vera = vera_instance
        self.probe = ContextProbe(vera_instance)

    # ──────────────────────────────────────────────────────────────────────
    # Primary API
    # ──────────────────────────────────────────────────────────────────────

    def build(self, query: str, stage: str = "general", preamble: str = "") -> str:
        """
        Probe memory for the given stage and return a formatted prompt.
        """
        mem_ctx = self.probe.probe(query, stage=stage)
        return self.build_from_context(mem_ctx, stage=stage, preamble=preamble)

    def build_from_context(
        self,
        mem_ctx: MemoryContext,
        stage: str = "general",
        preamble: str = "",
    ) -> str:
        """
        Format a pre-built MemoryContext into a prompt string.
        """
        sections = STAGE_SECTIONS.get(stage, STAGE_SECTIONS["general"])
        parts = []

        for section in sections:
            rendered = self._render_section(section, mem_ctx, stage, preamble)
            if rendered:
                parts.append(rendered)

        return "\n\n".join(parts)

    # ──────────────────────────────────────────────────────────────────────
    # Section renderers
    # ──────────────────────────────────────────────────────────────────────

    def _render_section(
        self, section: str, ctx: MemoryContext, stage: str, preamble: str
    ) -> str:
        try:
            match section:
                case s if s == _S_IDENTITY:
                    return self._render_identity()
                case s if s == _S_STYLE:
                    return VERA_STYLE
                case s if s == _S_DATETIME:
                    return f"Date/time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"
                case s if s == _S_FOCUS:
                    return self._render_focus(ctx)
                case s if s == _S_TOOLS:
                    return self._render_tools(ctx)
                case s if s == _S_HISTORY:
                    return self._render_history(ctx)
                case s if s == _S_VECTORS:
                    return self._render_vectors(ctx)
                case s if s == _S_GRAPH:
                    return self._render_graph(ctx)
                case s if s == _S_FRAME:
                    return self._render_frame(stage, ctx.query, preamble)
        except Exception as e:
            logger.debug(f"[ContextBuilder] Section '{section}' failed: {e}")
        return ""

    def _render_identity(self) -> str:
        try:
            cfg = self.vera.agents.get_agent_for_model("triage-agent")
            if cfg and getattr(cfg, "description", None):
                return f"You are Vera. {cfg.description}"
        except Exception:
            pass
        return VERA_IDENTITY

    @staticmethod
    def _render_focus(ctx: MemoryContext) -> str:
        return f"Current focus: {ctx.focus}" if ctx.focus else ""

    @staticmethod
    def _render_tools(ctx: MemoryContext) -> str:
        if not ctx.tool_names:
            return ""
        return "Available capabilities: " + ", ".join(ctx.tool_names)

    @staticmethod
    def _render_history(ctx: MemoryContext) -> str:
        if not ctx.history:
            return ""
        lines = []
        for turn in ctx.history:
            prefix = "User" if turn.role.lower() in ("user", "query", "human") else "Vera"
            lines.append(f"{prefix}: {turn.text}")
        return "--- Recent conversation ---\n" + "\n".join(lines)

    @staticmethod
    def _render_vectors(ctx: "MemoryContext") -> str:
        """
        Replacement for ContextBuilder._render_vectors.

        Renders three subsections:
        1. Relevant past exchanges  — (query, response) pairs, score-sorted
        2. Relevant notes           — documents, tool_outputs, other non-conv hits
        3. Graph context            — graph_traverse / keyword / entity hits
                                        (were previously buried in "others" at cap 5)

        Graph hits now get their own subsection with a higher cap (max_graph=8)
        and a distinct label showing their retrieval source, so they are never
        silently dropped.
        """
        _SOURCE_BADGE = {
            "vector_session":    "🔵",
            "vector_longterm":   "🔷",
            "graph_traverse":    "🟢",
            "graph_rerank":      "🔶",
            "recalled_exchange": "🟣",
            "keyword_neo4j":     "🔍",
            "entity_recall":     "🏷",
            "neighbour_swap":    "↔",
            "chunk_reassembled": "📄",
        }

        import os
        _DEBUG_BADGES = os.environ.get("VERA_CONTEXT_DEBUG", "0") == "1"

        # ── Collect ranked hits ──────────────────────────────────────────────
        if ctx.vectors.ranked_hits:
            top_n    = 5 if ctx.stage == "reasoning" else 4
            headroom = top_n * 5
            raw_list = [
                {
                    "id":       h.metadata.get("id", "") or "",
                    "text":     h.text,
                    "score":    h.score,
                    "metadata": h.metadata,
                    "source":   h.source,
                }
                for h in ctx.vectors.ranked_hits[:headroom]
            ]
        else:
            raw_list = []
            for h in (ctx.vectors.session_hits + ctx.vectors.longterm_hits):
                if h.get("text", "").strip():
                    raw_list.append(h)

        if not raw_list:
            return ""

        def _type(h) -> str:
            return h.get("metadata", {}).get("type", "").lower()

        def _source(h) -> str:
            return h.get("source", h.get("metadata", {}).get("collection", ""))

        # Split into three buckets
        conv        = [h for h in raw_list if _type(h) in ("query", "response")]
        graph_hits  = [h for h in raw_list
                    if _type(h) not in ("query", "response")
                    and _source(h) in _GRAPH_SOURCES]
        doc_notes   = [h for h in raw_list
                    if _type(h) not in ("query", "response")
                    and _source(h) not in _GRAPH_SOURCES]

        lines = []

        # ── 1. Conversational pairs ──────────────────────────────────────────
        conv_by_id  = {h.get("id", ""): h for h in conv if h.get("id")}
        conv_sorted = sorted(conv_by_id.values(), key=lambda h: h.get("id", ""))
        id_order    = [h.get("id", "") for h in conv_sorted]

        pairs_seen: set = set()
        pairs: list = []

        for h in conv:
            hid   = h.get("id", "")
            htype = _type(h)
            if hid in pairs_seen:
                continue

            if htype == "query":
                pairs_seen.add(hid)
                try:
                    pos   = id_order.index(hid)
                    rid   = id_order[pos + 1] if pos + 1 < len(id_order) else None
                    r_hit = conv_by_id.get(rid) if rid else None
                    if r_hit and _type(r_hit) == "response":
                        pairs_seen.add(rid)
                    else:
                        r_hit = None
                except (ValueError, IndexError):
                    r_hit = None
                pairs.append((h, r_hit, h.get("score", 0.0)))

            elif htype == "response":
                pairs_seen.add(hid)
                try:
                    pos   = id_order.index(hid)
                    qid   = id_order[pos - 1] if pos - 1 >= 0 else None
                    q_hit = conv_by_id.get(qid) if qid else None
                    if q_hit and _type(q_hit) == "query" and qid not in pairs_seen:
                        pairs_seen.add(qid)
                    else:
                        q_hit = None
                except (ValueError, IndexError):
                    q_hit = None
                if q_hit:
                    pairs.append((q_hit, h, h.get("score", 0.0)))
                else:
                    doc_notes.insert(0, h)   # orphan response → doc notes

        shown_texts: set = set()
        max_pairs = 5 if ctx.stage == "reasoning" else 3

        if pairs:
            lines.append("--- Relevant past exchanges ---")
            for q_hit, r_hit, score in pairs[:max_pairs]:
                q_text = q_hit.get("text", "").strip()
                q_snip = q_text[:300] + ("…" if len(q_text) > 300 else "")
                shown_texts.add(q_text)

                if _DEBUG_BADGES:
                    src   = q_hit.get("source", "")
                    badge = _SOURCE_BADGE.get(src, "⬜")
                    lines.append(f"Q{badge}[{score:.2f}]: {q_snip}")
                else:
                    lines.append(f"Q: {q_snip}")

                if r_hit:
                    r_text = r_hit.get("text", "").strip()
                    r_snip = r_text[:600] + ("…" if len(r_text) > 600 else "")
                    shown_texts.add(r_text)
                    lines.append(f"A: {r_snip}")
                else:
                    lines.append("A: [no recorded response]")

                lines.append("")

        # ── 2. Document / tool_output notes ─────────────────────────────────
        seen_other: dict = {}
        for h in doc_notes:
            t = h.get("text", "").strip()
            s = h.get("score", 0.0)
            if t and t not in shown_texts and (t not in seen_other or s > seen_other[t][1]):
                seen_other[t] = (h, s)

        max_others = 5
        top_others = sorted(seen_other.values(), key=lambda x: x[1], reverse=True)[:max_others]

        if top_others:
            header = "--- Relevant notes ---" if pairs else "--- Relevant memory ---"
            lines.append(header)
            for h, _ in top_others:
                text    = h.get("text", "").strip()
                snippet = text[:400] + ("…" if len(text) > 400 else "")
                shown_texts.add(text)
                if _DEBUG_BADGES:
                    src   = _source(h)
                    badge = _SOURCE_BADGE.get(src, "⬜")
                    lines.append(f"• {badge} {snippet}")
                else:
                    lines.append(f"• {snippet}")
            lines.append("")

        # ── 3. Graph context (NEW subsection) ────────────────────────────────
        seen_graph: dict = {}
        for h in graph_hits:
            t = h.get("text", "").strip()
            s = h.get("score", 0.0)
            if t and t not in shown_texts and (t not in seen_graph or s > seen_graph[t][1]):
                seen_graph[t] = (h, s)

        max_graph = 8
        top_graph = sorted(seen_graph.values(), key=lambda x: x[1], reverse=True)[:max_graph]

        if top_graph:
            lines.append("--- Graph context ---")
            for h, score in top_graph:
                text    = h.get("text", "").strip()
                snippet = text[:400] + ("…" if len(text) > 400 else "")
                src     = _source(h)
                label   = _GRAPH_SOURCE_LABELS.get(src, src)
                if _DEBUG_BADGES:
                    badge = _SOURCE_BADGE.get(src, "⬜")
                    lines.append(f"• {badge}[{score:.2f}] ({label}): {snippet}")
                else:
                    lines.append(f"• ({label}): {snippet}")

        return "\n".join(lines).rstrip()


    @staticmethod
    def _render_graph(ctx: MemoryContext) -> str:
        """
        Render structured graph entities.

        v2: also surfaces top graph-traversal hits that aren't already
        covered by the vectors section (source="graph_traverse" only).
        These provide extra entities that were reachable in the graph but
        not in the top-k vector results.
        """
        parts = []

        # ── Standard entity section ────────────────────────────────────────
        if ctx.graph.entities or ctx.graph.focus_entities:
            parts.append("--- Known entities (this session) ---")

            if ctx.graph.focus_entities:
                parts.append("Focus entities: " + ", ".join(ctx.graph.focus_entities[:8]))

            if ctx.graph.entities:
                by_label: dict[str, list[str]] = {}
                for e in ctx.graph.entities:
                    label = e.get("label", "?")
                    text  = e.get("text", "")
                    if text:
                        by_label.setdefault(label, []).append(text)

                for label, texts in list(by_label.items())[:14]:
                    parts.append(f"{label}: {', '.join(texts[:12])}")

        # ── Graph-traversal hits not already in vectors section ────────────
        traverse_only = [
            h for h in ctx.vectors.ranked_hits
            if h.source == "graph_traverse" and h.score >= 0.2
        ][:8]

        if traverse_only:
            parts.append("--- Graph-adjacent context ---")
            for hit in traverse_only:
                node_label = hit.metadata.get("node_label", "")
                snippet = hit.text[:240] + ("…" if len(hit.text) > 240 else "")
                parts.append(f"• [{node_label}] {snippet}")

        return "\n".join(parts) if parts else ""

    @staticmethod
    def _render_frame(stage: str, query: str, preamble: str) -> str:
        match stage:
            case "triage":
                return f"Query: {query}"

            case "preamble":
                return (
                    "The user has just sent a message. Provide a brief, natural opening "
                    "response. If the request clearly requires tool use or action, "
                    "acknowledge it in ONE sentence only — the action system will continue.\n\n"
                    f"User: {query}\nVera:"
                )

            case "action":
                return (
                    "You are about to execute an action for the following request. "
                    "Confirm what you are doing in ONE sentence, then proceed.\n\n"
                    f"User: {query}\nVera:"
                )

            case "reasoning":
                return (
                    "Apply careful, step-by-step reasoning to fully answer the following. "
                    "Show your reasoning.\n\n"
                    f"User: {query}\nVera:"
                )

            case "coding":
                return f"You are an expert programmer that provides well constructed solutions that approach the problem with care and precision. You document your code with comments thoroughly. Provide complete, working code for:\n\nUser: {query}\nVera:"

            case "conclusion":
                body = preamble[:1500] + ("…" if len(preamble) > 1500 else "")
                return (
                    f"Write a concise 2–3 sentence conclusion for this interaction.\n\n"
                    f"Original query: {query}\n\nResponse so far:\n{body}\n\nConclusion:"
                )

            case "continuation":
                intro = f"Opening already provided:\n{preamble}\n\n" if preamble else ""
                return (
                    f"{intro}Now continue with a complete, detailed answer.\n\n"
                    f"User: {query}\nVera:"
                )

            case _:
                return f"User: {query}\nVera:"