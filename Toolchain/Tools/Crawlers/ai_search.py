"""
AI-Guided Search Tool - Vera Toolchain
Provides autonomous, goal-directed web research controlled by an LLM.

The tool accepts a high-level research goal, distils it into a structured
"objective vector", then iteratively searches/scrapes the web until a
sufficient evidence base is gathered.  A final synthesis pass converts the
raw findings into a coherent report aligned with the original goal.

Usage in tools.py:
    from Vera.Toolchain.Tools.ai_search import add_ai_search_tool
    add_ai_search_tool(tool_list, agent)

Architecture:
    1. ObjectiveVector   — structured research plan built from the raw goal
    2. ResearchState     — accumulating evidence across search iterations
    3. AISearchOrchestrator — drives the search loop, calls LLM for decisions
    4. ai_guided_search  — public StructuredTool entry-point
"""

import re
import json
import asyncio
import traceback
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import requests
from langchain_core.tools import StructuredTool
from duckduckgo_search import DDGS
from pydantic import BaseModel, Field

# Reuse the scraping helper from web_search so we don't duplicate Playwright logic
from Vera.Toolchain.Tools.web_search import WebSearchTools


# ============================================================================
# SCHEMAS
# ============================================================================

class AISearchInput(BaseModel):
    """Input schema for the ai_guided_search tool."""

    goal: str = Field(
        ...,
        description=(
            "High-level research goal or task.  Examples: "
            "'Research the latest advancements in AI and produce a report', "
            "'Check Reddit for trending topics I can make videos about', "
            "'Find the best open-source vector databases and compare them'."
        ),
    )
    max_iterations: int = Field(
        default=4,
        ge=1,
        le=10,
        description="Maximum search-and-evaluate rounds before forcing synthesis (1–10).",
    )
    max_sources_per_iter: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Number of URLs to scrape per iteration (1–10).",
    )
    output_format: str = Field(
        default="report",
        description=(
            "Desired output format.  One of: "
            "'report' (structured markdown report), "
            "'bullets' (concise bullet-point summary), "
            "'raw' (all findings, minimal synthesis)."
        ),
    )


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class ObjectiveVector:
    """
    A structured decomposition of the user's raw goal into everything the
    search loop needs to operate autonomously.

    Fields
    ------
    raw_goal        : original user string, preserved verbatim
    synthesis_prompt: the *optimal LLM prompt* to produce the final output
                      from accumulated evidence — the core "objective vector"
    search_queries  : ordered list of search queries to execute first
    target_sites    : optional list of specific domains/URLs to prioritise
    success_criteria: human-readable conditions that define "enough" research
    output_format   : mirrors AISearchInput.output_format
    domain_hints    : keywords that indicate a result is highly relevant
    avoid_keywords  : keywords that indicate a result is off-topic
    """

    raw_goal: str
    synthesis_prompt: str
    search_queries: List[str]
    target_sites: List[str]
    success_criteria: str
    output_format: str
    domain_hints: List[str]
    avoid_keywords: List[str]

    @classmethod
    def from_llm_json(cls, raw_goal: str, data: Dict, output_format: str) -> "ObjectiveVector":
        """Construct from the dict returned by the planning LLM call."""
        return cls(
            raw_goal=raw_goal,
            synthesis_prompt=data.get("synthesis_prompt", raw_goal),
            search_queries=data.get("search_queries", [raw_goal]),
            target_sites=data.get("target_sites", []),
            success_criteria=data.get("success_criteria", "Sufficient information gathered."),
            output_format=output_format,
            domain_hints=data.get("domain_hints", []),
            avoid_keywords=data.get("avoid_keywords", []),
        )

    def to_context_block(self) -> str:
        """Serialise to a compact string for inclusion in LLM prompts."""
        return (
            f"GOAL: {self.raw_goal}\n"
            f"SUCCESS CRITERIA: {self.success_criteria}\n"
            f"DOMAIN HINTS: {', '.join(self.domain_hints) or 'none'}\n"
            f"AVOID: {', '.join(self.avoid_keywords) or 'none'}"
        )


@dataclass
class SourceRecord:
    """A single scraped source with relevance metadata."""

    url: str
    title: str
    snippet: str
    content: str
    links: List[Dict[str, str]]
    relevance_score: float = 0.0   # 0.0–1.0, set by evaluator
    iteration: int = 0


@dataclass
class ResearchState:
    """
    Mutable accumulator that grows across search iterations.

    Tracks which queries/URLs have been visited so the loop never repeats
    work, and stores all accepted source records for final synthesis.
    """

    objective: ObjectiveVector
    sources: List[SourceRecord] = field(default_factory=list)
    visited_urls: set = field(default_factory=set)
    executed_queries: List[str] = field(default_factory=list)
    iteration: int = 0
    sufficient: bool = False
    evaluator_notes: List[str] = field(default_factory=list)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def add_source(self, record: SourceRecord) -> None:
        if record.url not in self.visited_urls:
            self.sources.append(record)
            self.visited_urls.add(record.url)

    def evidence_summary(self, max_chars: int = 6000) -> str:
        """
        Compact serialisation of all gathered evidence for inclusion in
        LLM evaluation/synthesis prompts.  Truncates if needed so we stay
        inside model context limits.
        """
        lines = []
        budget = max_chars
        for i, src in enumerate(self.sources, 1):
            header = f"\n--- SOURCE {i} (relevance={src.relevance_score:.2f}) ---\n"
            header += f"Title: {src.title}\nURL: {src.url}\n"
            body_chunk = src.content[:800]  # per-source cap
            entry = header + body_chunk
            if budget - len(entry) < 0:
                lines.append("\n[... additional sources truncated for context ...]")
                break
            lines.append(entry)
            budget -= len(entry)
        return "\n".join(lines) if lines else "[No evidence gathered yet]"

    def high_relevance_sources(self, threshold: float = 0.6) -> List[SourceRecord]:
        return [s for s in self.sources if s.relevance_score >= threshold]


# ============================================================================
# LLM INTERFACE
# ============================================================================

class LLMClient:
    """
    Thin wrapper that tries Ollama first (local, consistent with Vera's stack)
    then falls back to the Anthropic Messages API.

    Both code-paths accept a plain string prompt and return a plain string.
    """

    OLLAMA_URL = "http://localhost:11434/api/generate"
    ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, ollama_model: str = "mistral", anthropic_model: str = "claude-sonnet-4-20250514"):
        self.ollama_model = ollama_model
        self.anthropic_model = anthropic_model

    # ── Ollama ────────────────────────────────────────────────────────────────

    def _call_ollama(self, prompt: str, system: str = "") -> str:
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        payload = {
            "model": self.ollama_model,
            "prompt": full_prompt,
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 2048},
        }
        resp = requests.post(self.OLLAMA_URL, json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json().get("response", "").strip()

    # ── Anthropic ─────────────────────────────────────────────────────────────

    def _call_anthropic(self, prompt: str, system: str = "") -> str:
        headers = {"Content-Type": "application/json"}
        body: Dict[str, Any] = {
            "model": self.anthropic_model,
            "max_tokens": 2048,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            body["system"] = system
        resp = requests.post(self.ANTHROPIC_URL, headers=headers, json=body, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        return data["content"][0]["text"].strip()

    # ── Public interface ──────────────────────────────────────────────────────

    def call(self, prompt: str, system: str = "", force_backend: Optional[str] = None) -> str:
        """
        Call an LLM.  Tries Ollama unless force_backend='anthropic'.
        Falls back to Anthropic automatically if Ollama is unavailable.
        """
        if force_backend == "anthropic":
            return self._call_anthropic(prompt, system)

        try:
            return self._call_ollama(prompt, system)
        except Exception:
            # Ollama not running or model unavailable — fall back silently
            return self._call_anthropic(prompt, system)

    def call_json(self, prompt: str, system: str = "") -> Dict:
        """
        Call the LLM and parse the response as JSON.
        Strips markdown code fences before parsing.
        Returns an empty dict on parse failure.
        """
        raw = self.call(prompt, system)
        # Strip ```json ... ``` fences if present
        cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
        cleaned = re.sub(r"\s*```$", "", cleaned.strip(), flags=re.MULTILINE)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Last-ditch: try to extract the first {...} block
            match = re.search(r"\{[\s\S]*\}", cleaned)
            if match:
                try:
                    return json.loads(match.group())
                except Exception:
                    pass
            return {}


# ============================================================================
# OBJECTIVE VECTOR BUILDER
# ============================================================================

_PLANNER_SYSTEM = """You are a research planning assistant.  Your job is to
decompose a user's research goal into a precise, structured JSON plan that will
guide an autonomous web-search agent.

You MUST respond with ONLY valid JSON — no prose, no markdown fences.

The JSON object must contain exactly these keys:

{
  "synthesis_prompt": "<The single best LLM prompt to synthesise all gathered
                        evidence into the desired output.  Write it as if you
                        are instructing another LLM that has the evidence in
                        front of it.  Be specific about tone, structure, and
                        depth.>",

  "search_queries":   ["<query 1>", "<query 2>", ...],
                       // 3–6 diverse search queries that together cover the
                       // goal from different angles.  Order most important
                       // first.  Include at least one site-specific query if
                       // a particular platform is mentioned (e.g. Reddit).

  "target_sites":     ["<domain or URL>", ...],
                       // Specific sites to prioritise.  Empty list if none.

  "success_criteria": "<One or two sentences describing what 'enough research'
                        looks like for this goal.>",

  "domain_hints":     ["<keyword>", ...],
                       // 4–8 keywords/phrases that indicate a search result
                       // is highly relevant to the goal.

  "avoid_keywords":   ["<keyword>", ...]
                       // 2–4 keywords that flag an off-topic or low-quality
                       // result (e.g. 'sponsored', 'advertisement').
}
"""

def build_objective_vector(goal: str, output_format: str, llm: LLMClient) -> ObjectiveVector:
    """
    Ask the LLM to decompose `goal` into a structured ObjectiveVector.
    Falls back to a simple heuristic plan if the LLM call fails.
    """
    prompt = (
        f"Research goal: {goal}\n\n"
        f"Output format requested: {output_format}\n\n"
        "Produce the JSON research plan as described in your instructions."
    )

    data = llm.call_json(prompt, system=_PLANNER_SYSTEM)

    if not data or "synthesis_prompt" not in data:
        # Heuristic fallback — good enough to proceed
        data = {
            "synthesis_prompt": (
                f"Using only the evidence provided, produce a {output_format} "
                f"that fully addresses this goal: {goal}"
            ),
            "search_queries": [goal, f"{goal} latest", f"{goal} overview"],
            "target_sites": [],
            "success_criteria": "At least 5 relevant sources with substantive content.",
            "domain_hints": goal.lower().split()[:6],
            "avoid_keywords": ["sponsored", "advertisement", "buy now"],
        }

    return ObjectiveVector.from_llm_json(goal, data, output_format)


# ============================================================================
# SEARCH ORCHESTRATOR
# ============================================================================

_EVALUATOR_SYSTEM = """You are a research quality evaluator for an autonomous
web-search agent.  You will be given:
  1. The research objective and success criteria
  2. A summary of all evidence gathered so far
  3. The current iteration number and maximum allowed

Respond with ONLY valid JSON — no prose, no markdown fences:

{
  "sufficient":        true | false,
  "reasoning":         "<one sentence explaining your verdict>",
  "relevance_scores":  {"<url>": <0.0–1.0>, ...},
  "follow_up_queries": ["<query>", ...],
  "gaps":              "<brief description of what is still missing, or 'none'>"
}

Set "sufficient" to true only when the success criteria are genuinely met.
"follow_up_queries" should contain 1–3 new queries that would fill the
identified gaps (empty list if sufficient=true).
"""

_RELEVANCE_SYSTEM = """You are scoring the relevance of a single web page to a
research goal.  Respond with ONLY valid JSON:
{
  "score": <0.0–1.0>,
  "reason": "<one short sentence>"
}
Score 0.0 = completely off-topic, 1.0 = directly answers the goal.
"""


class AISearchOrchestrator:
    """
    Drives the iterative research loop.

    Loop
    ----
    For each iteration:
      1. Pick the next batch of search queries from the objective
      2. Run DuckDuckGo text search (cheap, fast, no Playwright needed)
      3. Scrape each result page for full content + links
      4. Score relevance of each page
      5. Ask the evaluator LLM: sufficient yet?
         - If yes → break
         - If no  → add follow-up queries, continue
    After the loop: synthesise all evidence into the final output.
    """

    def __init__(self, agent, llm: LLMClient):
        self.agent = agent
        self.llm = llm
        # Reuse the existing scraping infrastructure from WebSearchTools
        self._web_tools = WebSearchTools(agent)

    # ── Event loop helper ────────────────────────────────────────────────────

    def _get_loop(self) -> asyncio.AbstractEventLoop:
        try:
            return asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop

    # ── DuckDuckGo search (non-Playwright, faster for bulk querying) ─────────

    def _ddg_search(self, query: str, max_results: int) -> List[Dict[str, str]]:
        try:
            with DDGS() as ddgs:
                return list(ddgs.text(query, region="us-en", max_results=max_results))
        except Exception as e:
            return []

    # ── Relevance scoring ────────────────────────────────────────────────────

    def _score_relevance(self, state: ResearchState, url: str, title: str, content: str) -> float:
        """
        Ask the LLM to score how relevant a page is to the research objective.
        Returns a float 0.0–1.0.  Falls back to a keyword-heuristic on failure.
        """
        prompt = (
            f"Research goal: {state.objective.raw_goal}\n"
            f"Page title: {title}\n"
            f"Page content (first 600 chars): {content[:600]}\n\n"
            "Score the relevance of this page to the research goal."
        )
        data = self.llm.call_json(prompt, system=_RELEVANCE_SYSTEM)
        score = data.get("score")

        if isinstance(score, (int, float)) and 0.0 <= float(score) <= 1.0:
            return float(score)

        # Keyword heuristic fallback
        text_lower = (title + " " + content).lower()
        hits = sum(1 for kw in state.objective.domain_hints if kw.lower() in text_lower)
        avoids = sum(1 for kw in state.objective.avoid_keywords if kw.lower() in text_lower)
        return min(1.0, max(0.0, (hits * 0.2) - (avoids * 0.3)))

    # ── Evaluator ────────────────────────────────────────────────────────────

    def _evaluate_sufficiency(
        self, state: ResearchState, max_iterations: int
    ) -> Tuple[bool, List[str], str]:
        """
        Ask the evaluator LLM whether the accumulated evidence meets the
        success criteria.

        Returns (sufficient: bool, follow_up_queries: list, gaps: str).
        """
        prompt = (
            f"{state.objective.to_context_block()}\n\n"
            f"Iteration: {state.iteration} / {max_iterations}\n\n"
            f"Evidence gathered so far:\n{state.evidence_summary(max_chars=4000)}\n\n"
            "Evaluate whether the research goal has been sufficiently addressed."
        )
        data = self.llm.call_json(prompt, system=_EVALUATOR_SYSTEM)

        sufficient = bool(data.get("sufficient", False))
        follow_up = data.get("follow_up_queries", [])
        gaps = data.get("gaps", "unknown")
        reasoning = data.get("reasoning", "")

        note = f"Iter {state.iteration}: sufficient={sufficient}. {reasoning} Gaps: {gaps}"
        state.evaluator_notes.append(note)

        return sufficient, follow_up, gaps

    # ── Synthesis ────────────────────────────────────────────────────────────

    def _synthesise(self, state: ResearchState) -> str:
        """
        Call the LLM one final time to produce the user-facing output.
        Uses the synthesis_prompt from the objective vector.
        """
        evidence = state.evidence_summary(max_chars=8000)
        sources_list = "\n".join(
            f"  [{i}] {s.title} — {s.url}"
            for i, s in enumerate(state.sources, 1)
        )

        prompt = (
            f"{state.objective.synthesis_prompt}\n\n"
            f"=== EVIDENCE BASE ({len(state.sources)} sources) ===\n"
            f"{evidence}\n\n"
            f"=== SOURCE INDEX ===\n{sources_list}"
        )

        return self.llm.call(prompt, system=(
            "You are a senior research analyst.  Produce the requested output "
            "using ONLY the evidence provided.  Cite sources by their index number "
            "[1], [2], etc.  Be accurate, well-structured, and thorough."
        ))

    # ── Main research loop ────────────────────────────────────────────────────

    def run(
        self,
        state: ResearchState,
        max_iterations: int,
        max_sources_per_iter: int,
    ) -> str:
        """
        Execute the full research loop and return the synthesised output string.

        Iteration structure
        -------------------
        1. Pop the next pending query (seeded from objective vector; extended
           by the evaluator's follow-up suggestions)
        2. Run DuckDuckGo, collect result URLs
        3. Scrape each URL with _scrape_url_with_links
        4. Score relevance; add high-relevance sources to state
        5. Evaluate sufficiency → if done, break; else add follow-ups
        6. After loop: synthesise
        """
        loop = self._get_loop()

        # Work-queue of queries: start with the objective's pre-planned queries
        pending_queries: List[str] = list(state.objective.search_queries)

        while state.iteration < max_iterations and not state.sufficient:
            state.iteration += 1

            if not pending_queries:
                break  # Nothing left to search

            query = pending_queries.pop(0)

            # Skip if we've already run this query
            if query in state.executed_queries:
                continue
            state.executed_queries.append(query)

            # ── Step 1: search ───────────────────────────────────────────────
            ddg_results = self._ddg_search(query, max_results=max_sources_per_iter)

            if not ddg_results:
                continue

            # ── Step 2: scrape + score ────────────────────────────────────────
            for r in ddg_results:
                url = r.get("href", "")
                title = r.get("title", "No title")
                snippet = r.get("body", "")

                if not url or url in state.visited_urls:
                    continue

                # Scrape full page content and in-body links
                try:
                    scraped = loop.run_until_complete(
                        self._web_tools._scrape_url_with_links(url, max_content=2000)
                    )
                except Exception:
                    scraped = {"text": snippet, "links": []}

                content = scraped.get("text", snippet)
                links = scraped.get("links", [])

                # Score relevance
                score = self._score_relevance(state, url, title, content)

                record = SourceRecord(
                    url=url,
                    title=title,
                    snippet=snippet,
                    content=content,
                    links=links,
                    relevance_score=score,
                    iteration=state.iteration,
                )
                state.add_source(record)

            # ── Step 3: evaluate sufficiency ──────────────────────────────────
            sufficient, follow_ups, gaps = self._evaluate_sufficiency(state, max_iterations)
            state.sufficient = sufficient

            # Queue follow-up queries for the next iteration
            for fq in follow_ups:
                if fq not in state.executed_queries and fq not in pending_queries:
                    pending_queries.append(fq)

        # ── Synthesis ──────────────────────────────────────────────────────────
        return self._synthesise(state)


# ============================================================================
# PUBLIC TOOL FUNCTION
# ============================================================================

class AIGuidedSearchTool:
    """Wrapper that exposes ai_guided_search as a StructuredTool."""

    def __init__(self, agent):
        self.agent = agent
        self.llm = LLMClient()

    def ai_guided_search(
        self,
        goal: str,
        max_iterations: int = 4,
        max_sources_per_iter: int = 5,
        output_format: str = "report",
    ) -> str:
        """
        Autonomous AI-guided web research.

        Accepts a high-level goal (e.g. "Research the latest advancements in
        AI and produce a report" or "Check Reddit for trending video topics"),
        builds a structured objective vector, then iteratively searches and
        scrapes the web until sufficient evidence is gathered.  Finally
        synthesises everything into the requested output format.

        output_format: 'report' | 'bullets' | 'raw'
        """
        try:
            # ── 1. Build objective vector ─────────────────────────────────────
            objective = build_objective_vector(goal, output_format, self.llm)

            # Persist the research session to the knowledge graph
            session_entity = self.agent.mem.add_session_memory(
                self.agent.sess.id,
                goal,
                "ai_guided_search",
                metadata={
                    "type": "ai_guided_search",
                    "output_format": output_format,
                    "queries_planned": len(objective.search_queries),
                    "synthesis_prompt": objective.synthesis_prompt[:200],
                },
            )

            # ── 2. Initialise research state ──────────────────────────────────
            state = ResearchState(objective=objective)

            # ── 3. Run the research loop ──────────────────────────────────────
            orchestrator = AISearchOrchestrator(self.agent, self.llm)
            synthesis = orchestrator.run(
                state,
                max_iterations=max_iterations,
                max_sources_per_iter=max_sources_per_iter,
            )

            # ── 4. Persist sources to knowledge graph ─────────────────────────
            for src in state.sources:
                src_entity = self.agent.mem.upsert_entity(
                    src.url,
                    "ai_research_source",
                    properties={
                        "title": src.title,
                        "relevance": src.relevance_score,
                        "iteration": src.iteration,
                        "preview": src.content[:300],
                    },
                    labels=["AIResearchSource"],
                )
                self.agent.mem.link(session_entity.id, src_entity.id, "FOUND")

            # ── 5. Build metadata footer ──────────────────────────────────────
            high_rel = state.high_relevance_sources(threshold=0.6)
            footer_lines = [
                "",
                "─" * 60,
                f"🔍 AI Research Summary",
                f"   Goal: {goal}",
                f"   Iterations: {state.iteration} / {max_iterations}",
                f"   Sources scraped: {len(state.sources)}",
                f"   High-relevance sources (≥0.6): {len(high_rel)}",
                f"   Queries executed: {', '.join(state.executed_queries)}",
            ]
            if state.evaluator_notes:
                footer_lines.append(f"   Evaluator notes:")
                for note in state.evaluator_notes:
                    footer_lines.append(f"     • {note}")
            footer_lines.append("─" * 60)

            return synthesis + "\n" + "\n".join(footer_lines)

        except Exception as e:
            return (
                f"[AI Search Error] {str(e)}\n\n"
                f"Traceback:\n{traceback.format_exc()}"
            )


# ============================================================================
# TOOL LOADER INTEGRATION
# ============================================================================

def add_ai_search_tool(tool_list: List, agent) -> List:
    """
    Add the ai_guided_search tool to the Vera tool list.

    Call this in ToolLoader() alongside add_web_search_tools():
        from Vera.Toolchain.Tools.ai_search import add_ai_search_tool
        add_ai_search_tool(tool_list, agent)
    """
    tool = AIGuidedSearchTool(agent)

    tool_list.append(
        StructuredTool.from_function(
            func=tool.ai_guided_search,
            name="ai_guided_search",
            description=(
                "Autonomous AI-guided web research.  Accepts a high-level goal "
                "and iteratively searches/scrapes the web until sufficient evidence "
                "is gathered, then synthesises a final output.  Best for complex "
                "research tasks, trend analysis, or any goal that requires multiple "
                "rounds of searching.  "
                "output_format: 'report' | 'bullets' | 'raw'."
            ),
            args_schema=AISearchInput,
        )
    )

    return tool_list