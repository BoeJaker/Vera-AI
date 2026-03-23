#!/usr/bin/env python3
"""
Vera/Memory/relationship_extractor.py
──────────────────────────────────────
SemanticRelationshipExtractor — produces richly typed relationships from text,
turning raw NLP dependency parses into a world-model graph.

Design goals
------------
1. **Typed relations** — "Tim Cook is CEO of Apple" → `(:Person)-[:IS_CEO_OF]->(:Org)`
   not just `(:Tim Cook)-[:RELATED_TO]->(:Apple)`.

2. **Multi-strategy** — three complementary strategies are run and merged:
   a. Pattern rules (fast, high precision for known templates)
   b. Dependency-tree traversal (medium speed, covers novel phrasings)
   c. Semantic verb mapping (verb lemma → canonical relation type)

3. **Confidence scoring** — each strategy assigns a confidence; the highest
   confidence instance wins when duplicates occur.

4. **Entity-ID aware** — relations carry `head_id` / `tail_id` so that
   `extract_and_link` can create edges without text-based lookups.

Relation taxonomy (extendable via VERB_MAP and PATTERN_RULES)
--------------------------------------------------------------
PERSON ↔ ORG:
  IS_CEO_OF, IS_CTO_OF, IS_CFO_OF, IS_FOUNDER_OF, WORKS_AT, LEADS,
  EMPLOYED_BY, ADVISES, INVESTED_IN

ORG ↔ ORG:
  ACQUIRED_BY, PARTNERED_WITH, COMPETES_WITH, SUBSIDIARY_OF,
  INVESTS_IN, MERGED_WITH, SPUN_OFF_FROM

ORG / PERSON ↔ PRODUCT / TECH:
  DEVELOPED_BY, USES, OWNS, CREATED, RELEASED, DEPLOYED

ORG / PERSON ↔ GEO:
  LOCATED_IN, HEADQUARTERED_IN, OPERATES_IN, BASED_IN

TECH ↔ TECH:
  DEPENDS_ON, INTEGRATES_WITH, EXTENDS, REPLACES, IMPLEMENTS

CAUSAL:
  CAUSED_BY, RESULTS_IN, ENABLES, PREVENTS

GENERAL (fallback):
  RELATED_TO
"""
from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Data model
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SemanticRelation:
    head: str
    tail: str
    relation: str
    confidence: float
    context: str = ""
    head_id: Optional[str] = None
    tail_id: Optional[str] = None
    strategy: str = "unknown"
    metadata: Dict[str, Any] = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# Verb → relation type mapping
# ─────────────────────────────────────────────────────────────────────────────

VERB_MAP: Dict[str, str] = {
    # Employment / leadership
    "lead":      "LEADS",
    "head":      "LEADS",
    "run":       "LEADS",
    "manage":    "MANAGES",
    "direct":    "LEADS",
    "oversee":   "OVERSEES",
    "work":      "WORKS_AT",
    "join":      "WORKS_AT",
    "hire":      "EMPLOYED_BY",
    "employ":    "EMPLOYED_BY",
    "found":     "FOUNDED",
    "co-found":  "COFOUNDED",
    "cofound":   "COFOUNDED",
    "start":     "FOUNDED",
    "establish": "FOUNDED",
    "create":    "CREATED",
    "build":     "BUILT",
    "develop":   "DEVELOPED",
    "design":    "DESIGNED",
    "invent":    "INVENTED",
    "patent":    "PATENTED",
    # Transactions / ownership
    "acquire":   "ACQUIRED",
    "buy":       "ACQUIRED",
    "purchase":  "ACQUIRED",
    "sell":      "SOLD_TO",
    "invest":    "INVESTED_IN",
    "fund":      "FUNDED",
    "back":      "FUNDED",
    "own":       "OWNS",
    "merge":     "MERGED_WITH",
    "partner":   "PARTNERED_WITH",
    "collaborate":"PARTNERED_WITH",
    "compete":   "COMPETES_WITH",
    "rival":     "COMPETES_WITH",
    # Location
    "locate":    "LOCATED_IN",
    "base":      "BASED_IN",
    "headquarter":"HEADQUARTERED_IN",
    "operate":   "OPERATES_IN",
    "expand":    "OPERATES_IN",
    # Tech
    "use":       "USES",
    "adopt":     "USES",
    "deploy":    "DEPLOYED",
    "release":   "RELEASED",
    "launch":    "RELEASED",
    "implement": "IMPLEMENTS",
    "extend":    "EXTENDS",
    "replace":   "REPLACES",
    "integrate": "INTEGRATES_WITH",
    "depend":    "DEPENDS_ON",
    "require":   "DEPENDS_ON",
    # Causal
    "cause":     "CAUSED_BY",
    "result":    "RESULTS_IN",
    "enable":    "ENABLES",
    "prevent":   "PREVENTS",
    "affect":    "AFFECTS",
    "impact":    "AFFECTS",
    # Advisory
    "advise":    "ADVISES",
    "consult":   "ADVISES",
    "mentor":    "MENTORS",
    "report":    "REPORTS_TO",
    "appoint":   "APPOINTED_TO",
    "name":      "APPOINTED_TO",
    # Communication
    "announce":  "ANNOUNCED",
    "publish":   "PUBLISHED",
    "present":   "PRESENTED",
}


# ─────────────────────────────────────────────────────────────────────────────
# High-precision pattern rules
# Each rule: (regex, relation_type, head_group, tail_group, confidence)
# ─────────────────────────────────────────────────────────────────────────────

_E = r"([A-Z][A-Za-z0-9 &.,'\-]+)"   # entity placeholder (broad)

PATTERN_RULES: List[Tuple] = [
    # ── Role / title patterns ─────────────────────────────────────────────
    # "Tim Cook, CEO of Apple"  /  "Apple CEO Tim Cook"
    (
        r"(?P<person>[A-Z][a-z]+ [A-Z][a-z]+),?\s+"
        r"(?P<title>CEO|CTO|CFO|COO|CPO|CMO|President|Chairman|Director|Founder|"
        r"Co-Founder|VP|SVP|EVP|Managing Director|General Counsel)\s+"
        r"(?:of\s+)?(?P<org>[A-Z][A-Za-z0-9 &.,'\-]+)",
        "IS_{title}_OF", "person", "org", 0.95,
    ),
    (
        r"(?P<org>[A-Z][A-Za-z0-9 &.,'\-]+)\s+"
        r"(?P<title>CEO|CTO|CFO|COO|CPO|CMO|President|Chairman|Director|Founder|"
        r"Co-Founder|VP|SVP|EVP)\s+"
        r"(?P<person>[A-Z][a-z]+ [A-Z][a-z]+)",
        "IS_{title}_OF", "person", "org", 0.95,
    ),
    # "Tim Cook is the CEO of Apple"
    (
        r"(?P<person>[A-Z][a-z]+(?: [A-Z][a-z]+)+)\s+is\s+(?:the\s+)?"
        r"(?P<title>CEO|CTO|CFO|COO|CPO|CMO|President|Chairman|"
        r"Director|Founder|Co-Founder|VP|SVP|EVP)\s+of\s+"
        r"(?P<org>[A-Z][A-Za-z0-9 &.,'\-]+)",
        "IS_{title}_OF", "person", "org", 0.97,
    ),

    # ── Employment ────────────────────────────────────────────────────────
    # "works at / joined / employed by"
    (
        r"(?P<person>[A-Z][a-z]+(?: [A-Z][a-z]+)+)\s+"
        r"(?:works?(?:\s+at)?|joined?|employed\s+by)\s+"
        r"(?P<org>[A-Z][A-Za-z0-9 &.,'\-]+)",
        "WORKS_AT", "person", "org", 0.90,
    ),

    # ── Founded ───────────────────────────────────────────────────────────
    (
        r"(?P<person>[A-Z][a-z]+(?: [A-Z][a-z]+)+)\s+"
        r"(?:founded|co-founded|cofounded|started|established|created)\s+"
        r"(?P<org>[A-Z][A-Za-z0-9 &.,'\-]+)",
        "FOUNDED", "person", "org", 0.92,
    ),
    (
        r"(?P<org>[A-Z][A-Za-z0-9 &.,'\-]+)\s+"
        r"(?:was\s+)?(?:founded|co-founded|cofounded|started|established)\s+"
        r"by\s+(?P<person>[A-Z][a-z]+(?: [A-Z][a-z]+)+)",
        "FOUNDED_BY", "org", "person", 0.92,
    ),

    # ── Acquisition ───────────────────────────────────────────────────────
    (
        r"(?P<acquirer>[A-Z][A-Za-z0-9 &.,'\-]+)\s+"
        r"(?:acquired|bought|purchased|took\s+over)\s+"
        r"(?P<acquired>[A-Z][A-Za-z0-9 &.,'\-]+)",
        "ACQUIRED", "acquirer", "acquired", 0.90,
    ),
    (
        r"(?P<acquired>[A-Z][A-Za-z0-9 &.,'\-]+)\s+"
        r"(?:was\s+)?(?:acquired|bought|purchased)\s+by\s+"
        r"(?P<acquirer>[A-Z][A-Za-z0-9 &.,'\-]+)",
        "ACQUIRED_BY", "acquired", "acquirer", 0.90,
    ),

    # ── Partnership ───────────────────────────────────────────────────────
    (
        r"(?P<org1>[A-Z][A-Za-z0-9 &.,'\-]+)\s+"
        r"(?:partnered?|collaborat\w+|teamed?\s+up)\s+"
        r"with\s+(?P<org2>[A-Z][A-Za-z0-9 &.,'\-]+)",
        "PARTNERED_WITH", "org1", "org2", 0.88,
    ),

    # ── Location ─────────────────────────────────────────────────────────
    (
        r"(?P<entity>[A-Z][A-Za-z0-9 &.,'\-]+)\s+"
        r"(?:is\s+)?(?:headquartered?|based|located)\s+in\s+"
        r"(?P<place>[A-Z][A-Za-z0-9 .,'\-]+)",
        "HEADQUARTERED_IN", "entity", "place", 0.90,
    ),

    # ── Investment ────────────────────────────────────────────────────────
    (
        r"(?P<investor>[A-Z][A-Za-z0-9 &.,'\-]+)\s+"
        r"invested?\s+in\s+"
        r"(?P<investee>[A-Z][A-Za-z0-9 &.,'\-]+)",
        "INVESTED_IN", "investor", "investee", 0.88,
    ),

    # ── Subsidiary / division ────────────────────────────────────────────
    (
        r"(?P<sub>[A-Z][A-Za-z0-9 &.,'\-]+)\s+"
        r"is\s+a\s+(?:subsidiary|division|unit|branch|arm)\s+of\s+"
        r"(?P<parent>[A-Z][A-Za-z0-9 &.,'\-]+)",
        "SUBSIDIARY_OF", "sub", "parent", 0.92,
    ),

    # ── Tech: uses / built on ────────────────────────────────────────────
    (
        r"(?P<entity>[A-Z][A-Za-z0-9 &.,'\-]+)\s+"
        r"(?:uses?|leverages?|built\s+on|based\s+on|powered\s+by)\s+"
        r"(?P<tech>[A-Z][A-Za-z0-9 &.,'\-]+)",
        "USES", "entity", "tech", 0.85,
    ),
    (
        r"(?P<tech>[A-Z][A-Za-z0-9 &.,'\-]+)\s+"
        r"(?:was\s+)?(?:developed?|built|created|designed)\s+by\s+"
        r"(?P<entity>[A-Z][A-Za-z0-9 &.,'\-]+)",
        "DEVELOPED_BY", "tech", "entity", 0.88,
    ),

    # ── Causal ───────────────────────────────────────────────────────────
    (
        r"(?P<cause>[A-Z][A-Za-z0-9 &.,'\-]+)\s+"
        r"(?:caused?|led?\s+to|resulted?\s+in|triggered?)\s+"
        r"(?P<effect>[A-Z][A-Za-z0-9 &.,'\-]+)",
        "CAUSED", "cause", "effect", 0.82,
    ),
    (
        r"(?P<effect>[A-Z][A-Za-z0-9 &.,'\-]+)\s+"
        r"(?:was\s+)?caused?\s+by\s+"
        r"(?P<cause>[A-Z][A-Za-z0-9 &.,'\-]+)",
        "CAUSED_BY", "effect", "cause", 0.82,
    ),

    # ── Competition ──────────────────────────────────────────────────────
    (
        r"(?P<org1>[A-Z][A-Za-z0-9 &.,'\-]+)\s+"
        r"(?:competes?|rivals?|faces?\s+competition\s+from)\s+"
        r"(?:with\s+)?(?P<org2>[A-Z][A-Za-z0-9 &.,'\-]+)",
        "COMPETES_WITH", "org1", "org2", 0.85,
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
# Main extractor
# ─────────────────────────────────────────────────────────────────────────────

class SemanticRelationshipExtractor:
    """
    Extract typed semantic relationships from text.

    Usage
    -----
        extractor = SemanticRelationshipExtractor()
        relations = extractor.extract(text, entity_lookup)

    Parameters
    ----------
    spacy_model : str
        spaCy model name (default "en_core_web_sm").
    min_confidence : float
        Relations below this threshold are discarded (default 0.70).
    """

    def __init__(
        self,
        spacy_model: str = "en_core_web_sm",
        min_confidence: float = 0.70,
    ):
        self.min_confidence = min_confidence
        self._nlp = None
        self._spacy_model = spacy_model

    def _get_nlp(self):
        """Lazy-load spaCy to avoid startup cost when not needed."""
        if self._nlp is None:
            import spacy
            try:
                self._nlp = spacy.load(self._spacy_model)
            except OSError:
                import os
                os.system(f"python -m spacy download {self._spacy_model}")
                self._nlp = spacy.load(self._spacy_model)
        return self._nlp

    # ─────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────

    def extract(
        self,
        text: str,
        entity_lookup: Optional[Dict[str, str]] = None,
    ) -> List[SemanticRelation]:
        """
        Extract semantic relations from text.

        Parameters
        ----------
        text : str
            Raw text to analyse.
        entity_lookup : dict | None
            Maps entity_text → canonical_id for ID assignment.
            If None, head_id / tail_id will be left empty.

        Returns
        -------
        List[SemanticRelation]  — deduplicated, confidence-sorted.
        """
        if not text or not text.strip():
            return []

        entity_lookup = entity_lookup or {}
        all_relations: List[SemanticRelation] = []

        # Strategy 1: Pattern rules (fast, high precision)
        try:
            all_relations.extend(self._pattern_extract(text, entity_lookup))
        except Exception as e:
            logger.warning(f"[RelExtractor] pattern strategy failed: {e}")

        # Strategy 2: Dependency tree (covers novel phrasings)
        try:
            all_relations.extend(self._dep_extract(text, entity_lookup))
        except Exception as e:
            logger.warning(f"[RelExtractor] dep-parse strategy failed: {e}")

        # Strategy 3: Verb-mapping on spaCy tokens
        try:
            all_relations.extend(self._verb_map_extract(text, entity_lookup))
        except Exception as e:
            logger.warning(f"[RelExtractor] verb-map strategy failed: {e}")

        # Deduplicate & filter
        relations = self._deduplicate(all_relations)
        relations = [r for r in relations if r.confidence >= self.min_confidence]
        relations.sort(key=lambda r: r.confidence, reverse=True)

        logger.debug(
            f"[RelExtractor] extracted {len(relations)} relations "
            f"from {len(text)} chars"
        )
        return relations

    # ─────────────────────────────────────────────────────────────────────
    # Strategy 1: Pattern rules
    # ─────────────────────────────────────────────────────────────────────

    def _pattern_extract(
        self, text: str, entity_lookup: Dict[str, str]
    ) -> List[SemanticRelation]:
        relations = []

        for rule in PATTERN_RULES:
            pattern, rel_template, head_grp, tail_grp, confidence = rule
            for match in re.finditer(pattern, text, re.IGNORECASE):
                groups = match.groupdict()
                head_text = groups.get(head_grp, "").strip()
                tail_text = groups.get(tail_grp, "").strip()

                if not head_text or not tail_text:
                    continue
                if len(head_text) < 2 or len(tail_text) < 2:
                    continue

                # Resolve title placeholder in relation type
                rel_type = rel_template
                if "{title}" in rel_template:
                    title = groups.get("title", "").upper().replace(" ", "_").replace("-", "_")
                    rel_type = rel_template.replace("{title}", title)

                context_start = max(0, match.start() - 60)
                context_end   = min(len(text), match.end() + 60)
                context = text[context_start:context_end].strip()

                relations.append(SemanticRelation(
                    head=head_text,
                    tail=tail_text,
                    relation=rel_type,
                    confidence=confidence,
                    context=context,
                    head_id=entity_lookup.get(head_text.lower()),
                    tail_id=entity_lookup.get(tail_text.lower()),
                    strategy="pattern",
                    metadata={"pattern": pattern[:40]},
                ))

        return relations

    # ─────────────────────────────────────────────────────────────────────
    # Strategy 2: Dependency parse
    # ─────────────────────────────────────────────────────────────────────

    def _dep_extract(
        self, text: str, entity_lookup: Dict[str, str]
    ) -> List[SemanticRelation]:
        nlp = self._get_nlp()
        doc = nlp(text)
        relations = []

        for sent in doc.sents:
            for token in sent:
                # ── Subject → Verb → Object ───────────────────────────
                if token.dep_ in ("nsubj", "nsubjpass") and token.head.pos_ == "VERB":
                    verb = token.head
                    subject = self._get_span_text(token)
                    rel_type = VERB_MAP.get(verb.lemma_.lower(), "")

                    for child in verb.children:
                        if child.dep_ in ("dobj", "attr", "pobj", "nsubjpass"):
                            obj = self._get_span_text(child)
                            if not subject or not obj or subject == obj:
                                continue

                            effective_rel = rel_type or f"{verb.lemma_.upper()}"
                            confidence = 0.80 if rel_type else 0.65

                            relations.append(SemanticRelation(
                                head=subject,
                                tail=obj,
                                relation=effective_rel,
                                confidence=confidence,
                                context=sent.text[:200],
                                head_id=entity_lookup.get(subject.lower()),
                                tail_id=entity_lookup.get(obj.lower()),
                                strategy="dep_svo",
                                metadata={"verb": verb.text, "lemma": verb.lemma_},
                            ))

                # ── Prepositional complement: entity PREP entity ──────
                if token.dep_ == "prep" and token.head.pos_ in ("NOUN", "PROPN", "VERB"):
                    prep = token.text.lower()
                    head_text = self._get_span_text(token.head)

                    for child in token.children:
                        if child.dep_ == "pobj":
                            tail_text = self._get_span_text(child)
                            if not head_text or not tail_text or head_text == tail_text:
                                continue

                            rel = self._prep_to_rel(prep)
                            if rel:
                                relations.append(SemanticRelation(
                                    head=head_text,
                                    tail=tail_text,
                                    relation=rel,
                                    confidence=0.75,
                                    context=sent.text[:200],
                                    head_id=entity_lookup.get(head_text.lower()),
                                    tail_id=entity_lookup.get(tail_text.lower()),
                                    strategy="dep_prep",
                                    metadata={"prep": prep},
                                ))

                # ── Apposition: "Tim Cook, CEO of Apple" ──────────────
                if token.dep_ == "appos":
                    head_text = self._get_span_text(token.head)
                    tail_text = self._get_span_text(token)
                    if head_text and tail_text and head_text != tail_text:
                        relations.append(SemanticRelation(
                            head=head_text,
                            tail=tail_text,
                            relation="REFERRED_AS",
                            confidence=0.75,
                            context=sent.text[:200],
                            head_id=entity_lookup.get(head_text.lower()),
                            tail_id=entity_lookup.get(tail_text.lower()),
                            strategy="dep_appos",
                        ))

        return relations

    # ─────────────────────────────────────────────────────────────────────
    # Strategy 3: Verb mapping on full token scan
    # ─────────────────────────────────────────────────────────────────────

    def _verb_map_extract(
        self, text: str, entity_lookup: Dict[str, str]
    ) -> List[SemanticRelation]:
        """
        Scan for verb tokens in VERB_MAP, find the nearest named entities
        on each side, and emit a typed relation.
        """
        nlp = self._get_nlp()
        doc = nlp(text)

        # Index named entities by token index for fast lookup
        ent_by_token: Dict[int, str] = {}
        for ent in doc.ents:
            for tok in ent:
                ent_by_token[tok.i] = ent.text

        relations = []

        for token in doc:
            if token.pos_ != "VERB":
                continue
            rel_type = VERB_MAP.get(token.lemma_.lower())
            if not rel_type:
                continue

            # Look left and right within a 10-token window for named entities
            left_ent  = self._nearest_entity_left(doc,  token.i, ent_by_token, window=10)
            right_ent = self._nearest_entity_right(doc, token.i, ent_by_token, window=10)

            if left_ent and right_ent and left_ent != right_ent:
                # Get sentence context
                sent_text = next(
                    (s.text for s in doc.sents if s.start <= token.i < s.end), ""
                )
                relations.append(SemanticRelation(
                    head=left_ent,
                    tail=right_ent,
                    relation=rel_type,
                    confidence=0.72,
                    context=sent_text[:200],
                    head_id=entity_lookup.get(left_ent.lower()),
                    tail_id=entity_lookup.get(right_ent.lower()),
                    strategy="verb_map",
                    metadata={"verb": token.text, "lemma": token.lemma_},
                ))

        return relations

    # ─────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def _get_span_text(token) -> str:
        """Return the text of a token or its noun-phrase subtree."""
        # If the token is a root or has a compound/det/amod, return full chunk
        try:
            if token.pos_ in ("NOUN", "PROPN"):
                parts = [
                    t.text for t in token.subtree
                    if t.dep_ in ("compound", "amod", "det", "ROOT")
                    or t.i == token.i
                ]
                return " ".join(parts).strip() or token.text
        except Exception:
            pass
        return token.text

    @staticmethod
    def _prep_to_rel(prep: str) -> Optional[str]:
        """Map a preposition to a relation type, if meaningful."""
        mapping = {
            "at":    "LOCATED_AT",
            "in":    "LOCATED_IN",
            "for":   "WORKS_FOR",
            "of":    "PART_OF",
            "with":  "ASSOCIATED_WITH",
            "from":  "ORIGINATES_FROM",
            "by":    "CREATED_BY",
            "about": None,
            "like":  None,
            "as":    "SERVES_AS",
        }
        return mapping.get(prep)

    @staticmethod
    def _nearest_entity_left(
        doc, token_idx: int, ent_by_token: Dict[int, str], window: int
    ) -> Optional[str]:
        for i in range(token_idx - 1, max(-1, token_idx - window - 1), -1):
            if i in ent_by_token:
                return ent_by_token[i]
        return None

    @staticmethod
    def _nearest_entity_right(
        doc, token_idx: int, ent_by_token: Dict[int, str], window: int
    ) -> Optional[str]:
        for i in range(token_idx + 1, min(len(doc), token_idx + window + 1)):
            if i in ent_by_token:
                return ent_by_token[i]
        return None

    # ─────────────────────────────────────────────────────────────────────
    # Deduplication
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def _deduplicate(relations: List[SemanticRelation]) -> List[SemanticRelation]:
        """
        Keep the highest-confidence instance of each (head, tail, relation) triple.
        Also normalise symmetric relations so (A, B, X) and (B, A, X) become one.
        """
        SYMMETRIC = {
            "PARTNERED_WITH", "COMPETES_WITH", "MERGED_WITH",
            "ASSOCIATED_WITH", "RELATED_TO",
        }

        seen: Dict[Tuple[str, str, str], SemanticRelation] = {}

        for rel in sorted(relations, key=lambda r: r.confidence, reverse=True):
            head = rel.head.strip().lower()
            tail = rel.tail.strip().lower()
            rtype = rel.relation

            # Normalise symmetric pairs so (B,A) maps to same key as (A,B)
            if rtype in SYMMETRIC and head > tail:
                head, tail = tail, head

            key = (head, tail, rtype)
            if key not in seen:
                seen[key] = rel

        return list(seen.values())