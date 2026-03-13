"""
Vera Tool Framework - Fuzzy Tool Searcher
=========================================
Provides fuzzy and semantic search for the ToolRegistry. Supports:
    - Multi-term keyword search across name, description, tags, category, and capabilities
    - Incremental updates for live registry changes
    - Optional semantic search via sentence-transformers / embeddings
    - Ranked, relevance-scored results

Drop-in usage:
    from Vera.Toolchain.ToolFramework.fuzzy_search import FuzzyToolSearcher

    searcher = FuzzyToolSearcher(global_registry, enable_semantic=True)
    results = searcher.search("network security", max_results=10)
"""

"""
TODO
Expand to "capabilities" fuzzy search - not just tools but also capabilities (pre/post LLM) and their metadata
"""
from __future__ import annotations
import logging
import re
from typing import List, Tuple, Optional, Dict, Any
import heapq

from langchain.tools import BaseTool
from Vera.Toolchain.ToolFramework.registry import ToolRegistry
from Vera.Toolchain.ToolFramework.core import ToolCapability

logger = logging.getLogger("vera.tools.fuzzy_search")

# Optional semantic embedding support
try:
    from sentence_transformers import SentenceTransformer, util
    _SEMANTIC_MODEL = SentenceTransformer('all-MiniLM-L6-v2')
except ImportError:
    _SEMANTIC_MODEL = None
    logger.warning("sentence-transformers not installed. Semantic search disabled.")


class FuzzyToolSearcher:
    """
    Fuzzy and semantic search over a ToolRegistry.
    """

    def __init__(self, registry: ToolRegistry, enable_semantic: bool = False):
        self.registry = registry
        self.enable_semantic = enable_semantic and (_SEMANTIC_MODEL is not None)

        # Internal caches
        self._normalized_texts: Dict[str, str] = {}   # tool_name -> combined searchable text
        self._embeddings: Dict[str, Any] = {}         # tool_name -> semantic embedding

        # Build initial index
        self._rebuild_index()

    # ------------------------------------------------------------------------
    # Public search API
    # ------------------------------------------------------------------------

    def search(
        self,
        query: str,
        max_results: int = 20,
        min_score: float = 0.1,
        filter_categories: Optional[List[str]] = None,
    ) -> List[Tuple[BaseTool, float]]:
        """
        Perform a search over the registry.

        Args:
            query: User query string (multi-term supported)
            max_results: Maximum number of results to return
            min_score: Minimum relevance score threshold
            filter_categories: Optional list of category names to pre-filter results
        Returns:
            List of (tool, score) tuples, sorted by descending score
        """
        query_terms = self._normalize_terms(query)

        # Pre-filter tools by category if requested
        candidates = list(self._normalized_texts.keys())
        if filter_categories:
            candidates = [
                name for name in candidates
                if self.registry.get_descriptor(name).category.value in filter_categories
            ]

        scores: Dict[str, float] = {}
        for name in candidates:
            scores[name] = self._keyword_score(name, query_terms)

        # Semantic scoring
        if self.enable_semantic and candidates:
            sem_scores = self._semantic_score(query, candidates)
            for i, name in enumerate(candidates):
                scores[name] += sem_scores[i]

        # Filter by min_score and rank
        ranked = [(name, s) for name, s in scores.items() if s >= min_score]
        ranked.sort(key=lambda x: x[1], reverse=True)
        ranked = ranked[:max_results]

        return [(self.registry.get_langchain_tool(name), score) for name, score in ranked]

    # ------------------------------------------------------------------------
    # Incremental index updates
    # ------------------------------------------------------------------------

    def add_tool(self, tool: BaseTool):
        """Add a tool to the search index incrementally."""
        desc = self.registry.get_descriptor(tool.name)
        if not desc:
            return
        text = self._build_search_text(tool, desc)
        self._normalized_texts[tool.name] = text
        if self.enable_semantic:
            self._embeddings[tool.name] = _SEMANTIC_MODEL.encode([text], convert_to_tensor=True)

    def remove_tool(self, tool_name: str):
        """Remove a tool from the search index."""
        self._normalized_texts.pop(tool_name, None)
        self._embeddings.pop(tool_name, None)

    def _rebuild_index(self):
        """Rebuild the full search index from the registry."""
        self._normalized_texts.clear()
        self._embeddings.clear()
        for tool in self.registry.get_langchain_tools():
            self.add_tool(tool)

    # ------------------------------------------------------------------------
    # Internal scoring / embeddings
    # ------------------------------------------------------------------------

    def _normalize_terms(self, text: str) -> List[str]:
        return re.findall(r'\w+', text.lower())

    def _build_search_text(self, tool: BaseTool, desc) -> str:
        """Combine all searchable fields into a single lowercase string."""
        tags = " ".join(desc.tags or [])
        capabilities = " ".join([cap.name.lower() for cap in ToolCapability if desc.has_capability(cap)])
        return " ".join([tool.name, tool.description or "", tags, desc.category.value, capabilities]).lower()

    def _keyword_score(self, tool_name: str, query_terms: List[str]) -> float:
        """Heuristic keyword scoring."""
        text = self._normalized_texts.get(tool_name, "")
        score = 0.0
        for term in query_terms:
            if term in text:
                score += 1.0
        return score

    def _semantic_score(self, query: str, tool_names: List[str]) -> List[float]:
        """Compute semantic similarity scores."""
        if not self.enable_semantic:
            return [0.0] * len(tool_names)
        query_emb = _SEMANTIC_MODEL.encode([query], convert_to_tensor=True)
        embeddings = [self._embeddings[name] for name in tool_names]
        cosine_scores = util.cos_sim(query_emb, embeddings)[0].tolist()
        return cosine_scores