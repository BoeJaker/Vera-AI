"""
Questions Stage — GAP-AWARE, SIMPLIFIED
=========================================
Now that information gap detection lives in InfoGapStage, this stage has
one job: generate clarifying questions for the user.

Changes vs previous version:
  - Removed gap detection entirely (now in InfoGapStage)
  - Reads open info_gaps from the board and converts gap items tagged
    dispatch_to=["questions"] into properly formatted user-facing questions
  - Skips generating duplicate questions for gaps already present
  - Still generates organic questions from board state for cases where
    the gap stage hasn't run yet or new context has appeared
  - Hard cap of MAX_UNANSWERED_QUESTIONS unanswered questions at any time
  - Answered questions (metadata.status == "answered") are preserved on the
    board and excluded from the unanswered cap count
  - Tightened duplicate detection: lower token-overlap threshold + semantic
    prefix/suffix normalisation to catch near-identical phrasings
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from Vera.ProactiveFocus.Experimental.Components.Stages.base import BaseStage, StageOutput

_GAP_TYPE             = "info_gap"
_STATUS_OPEN          = "open"
_STATUS_ACTIONED      = "actioned"
_STATUS_ANSWERED      = "answered"

# Maximum number of *unanswered* questions allowed on the board at any time.
MAX_UNANSWERED_QUESTIONS = 10

# Token-overlap ratio required to call two questions duplicates.
# Lowered from 0.60 → 0.45 so near-paraphrases are caught earlier.
_DUPLICATE_OVERLAP = 0.45

# Additional short stopwords ignored during overlap scoring so that
# questions differing only in filler words aren't considered unique.
_STOPWORDS: Set[str] = {
    "what", "which", "how", "why", "when", "where", "who", "whose",
    "the", "this", "that", "these", "those", "your", "you", "are",
    "is", "was", "were", "will", "would", "should", "could", "can",
    "any", "all", "and", "for", "with", "about", "have", "has",
    "need", "needs", "want", "wants", "use", "uses", "do", "does",
    "there", "here", "it", "its", "be", "been", "being", "more",
    "plan", "plans", "currently", "current", "specific", "please",
    "provide", "describe", "explain", "tell", "give",
}


class QuestionsStage(BaseStage):
    """
    Generate clarifying questions for the user.

    Sources (in priority order):
      1. Open info_gap items tagged dispatch_to=["questions"] — converted
         directly into board question items so the user sees them.
      2. Organic questions generated from board analysis for gaps and
         ambiguities not already captured by InfoGapStage.

    Constraints:
      - At most MAX_UNANSWERED_QUESTIONS unanswered questions on the board
        at any time.  The stage will not add new questions once that limit
        is reached.
      - Answered questions (metadata.status == "answered") are never removed
        by this stage and do not count toward the cap.
      - Duplicate detection uses a tightened token-overlap threshold and
        normalises common question prefixes before comparison.
    """

    def __init__(self) -> None:
        super().__init__(
            name="Questions",
            icon="❓",
            description="Surface clarifying questions and gap-driven queries for user input",
        )

    # ==================================================================
    # ENTRY POINT
    # ==================================================================

    def execute(
        self,
        focus_manager,
        context: Optional[Any] = None,
    ) -> StageOutput:
        output = StageOutput()

        self._stream_output(focus_manager, "❓ Generating clarifying questions…", "info")

        # ── How many unanswered slots remain? ──────────────────────────
        unanswered_count = self._count_unanswered(focus_manager)
        slots_available  = MAX_UNANSWERED_QUESTIONS - unanswered_count

        if slots_available <= 0:
            self._stream_output(
                focus_manager,
                f"  ⏸  Board already has {unanswered_count} unanswered question(s) "
                f"(cap: {MAX_UNANSWERED_QUESTIONS}). Skipping question generation.",
                "info",
            )
            return output

        self._stream_output(
            focus_manager,
            f"  📊 {unanswered_count} unanswered question(s) on board "
            f"({slots_available} slot(s) available)",
            "info",
        )

        # ── Step 1: Promote gap items tagged for user clarification ────
        promoted = self._promote_gap_questions(focus_manager, slots_available)
        if promoted:
            self._stream_output(
                focus_manager,
                f"  📌 Promoted {len(promoted)} info-gap question(s) for user input:",
                "info",
            )
            for q in promoted:
                self._stream_output(focus_manager, f"    ❓ {q[:100]}", "info")
                output.next_steps.append(q)
            slots_available -= len(promoted)

        # ── Step 2: Generate organic questions from board state ────────
        added = 0
        if slots_available > 0:
            existing_questions = self._get_existing_question_texts(focus_manager)
            organic = self._generate_organic_questions(
                focus_manager, context, existing_questions, max_questions=slots_available
            )

            for q in organic:
                if slots_available <= 0:
                    break
                if not self._is_duplicate_of_existing(q, existing_questions):
                    self._add_to_board(focus_manager, "questions", q)
                    existing_questions.append(q)
                    output.next_steps.append(q)
                    self._stream_output(focus_manager, f"  💬 {q[:100]}", "info")
                    added += 1
                    slots_available -= 1

        total = len(promoted) + added
        self._stream_output(
            focus_manager,
            f"  Generated {total} question(s) ({len(promoted)} from gaps, {added} organic). "
            f"Unanswered total: {unanswered_count + total}/{MAX_UNANSWERED_QUESTIONS}",
            "success",
        )

        if total:
            self._notify_telegram(
                focus_manager,
                self._build_telegram_summary(promoted, organic[:added] if slots_available >= 0 else []),
            )

        return output

    # ==================================================================
    # UNANSWERED COUNT
    # ==================================================================

    def _count_unanswered(self, focus_manager) -> int:
        """
        Count questions on the board that have NOT been answered.

        A question is considered answered when its metadata contains
        ``status == "answered"``.  Items without a status field are
        treated as unanswered.
        """
        questions = focus_manager.board.get_category("questions")
        count = 0
        for item in questions:
            if isinstance(item, dict):
                status = item.get("metadata", {}).get("status", "")
                if status != _STATUS_ANSWERED:
                    count += 1
            else:
                # Plain string items are always unanswered
                count += 1
        return count

    # ==================================================================
    # GAP PROMOTION
    # ==================================================================

    def _promote_gap_questions(
        self, focus_manager, slots_available: int
    ) -> List[str]:
        """
        Find open info_gap items with dispatch_to containing "questions"
        and ensure they appear as plain question text on the board.

        Respects the slots_available limit.
        Returns the list of question texts promoted.
        """
        questions_category = focus_manager.board.get_category("questions")

        # Build a set of existing non-gap question texts to avoid duplication
        existing_texts: List[str] = [
            item.get("metadata", {}).get("question", item.get("note", ""))
            for item in questions_category
            if isinstance(item, dict)
            and item.get("metadata", {}).get("type") != _GAP_TYPE
        ]

        promoted: List[str] = []

        for item in questions_category:
            if slots_available <= 0:
                break
            if not isinstance(item, dict):
                continue
            meta = item.get("metadata", {})
            if meta.get("type") != _GAP_TYPE:
                continue
            if meta.get("status") not in (_STATUS_OPEN, _STATUS_ACTIONED):
                continue
            if "questions" not in meta.get("dispatch_to", []):
                continue

            question_text = meta.get("question", item.get("note", "")).strip()
            if not question_text:
                continue

            if self._is_duplicate_of_existing(question_text, existing_texts):
                self._stream_output(
                    focus_manager,
                    f"  ⚡ Skipping near-duplicate gap question: {question_text[:80]}",
                    "info",
                )
                continue

            rationale  = meta.get("rationale", "")
            full_text  = (
                f"{question_text} [{rationale}]" if rationale else question_text
            )
            self._add_to_board(
                focus_manager,
                "questions",
                full_text,
                metadata={
                    "type":     "promoted_gap_question",
                    "gap_id":   meta.get("gap_id", ""),
                    "priority": meta.get("priority", "medium"),
                    "source":   "info_gap_stage",
                    "status":   _STATUS_OPEN,
                },
            )
            promoted.append(question_text)
            existing_texts.append(question_text)
            slots_available -= 1

        return promoted

    # ==================================================================
    # ORGANIC QUESTION GENERATION
    # ==================================================================

    def _generate_organic_questions(
        self,
        focus_manager,
        context:            Optional[Any],
        existing_questions: List[str],
        max_questions:      int = 5,
    ) -> List[str]:
        """
        Ask the LLM for additional clarifying questions beyond the gap items.
        Uses fast_llm — this is a low-stakes generation task.

        ``max_questions`` caps how many the LLM is asked to generate so the
        prompt stays honest about available capacity.
        """
        board      = self._get_board_data(focus_manager)
        focus      = getattr(focus_manager, "focus", "") or "Unknown project"
        board_text = self._board_as_text(board)

        existing_block = (
            "\n".join(f"  - {q[:120]}" for q in existing_questions[:15])
            or "  (none yet)"
        )

        context_block = f"\nAdditional context:\n{context}\n" if context else ""

        prompt = f"""You are reviewing a project focus board to identify clarifying questions
that need USER input (not tool calls or automated research).

Project: {focus}
{context_block}
=== BOARD STATE ===
{board_text[:2500]}

=== QUESTIONS ALREADY ON THE BOARD — DO NOT DUPLICATE OR PARAPHRASE THESE ===
{existing_block}

Generate up to {max_questions} NEW clarifying questions that:
  - Require human judgment, preference, or authority to answer
  - Would materially affect decisions or prioritisation
  - Are NOT answerable by running a tool or reading a file
  - Are COMPLETELY DISTINCT from every question already listed above
    (avoid rephrasing the same underlying question in different words)
  - Are specific and actionable, not vague catch-alls

If there are already enough questions to proceed, return an empty array.

IMPORTANT: Return ONLY a JSON array of question strings. No commentary.
["Question 1?", "Question 2?"]
"""

        try:
            response = self._stream_llm(
                focus_manager,
                focus_manager.agent.fast_llm,
                prompt,
                operation="generate_questions",
            )
            return self._parse_json_list(response)
        except Exception as exc:
            self._stream_output(
                focus_manager,
                f"  ⚠️  Question generation failed: {exc}",
                "warning",
            )
            return []

    # ==================================================================
    # HELPERS
    # ==================================================================

    def _get_existing_question_texts(self, focus_manager) -> List[str]:
        """Return all existing question text strings from the board (answered or not)."""
        questions = focus_manager.board.get_category("questions")
        texts: List[str] = []
        for item in questions:
            if isinstance(item, dict):
                meta = item.get("metadata", {})
                text = meta.get("question", item.get("note", ""))
            else:
                text = str(item)
            if text:
                texts.append(text)
        return texts

    # ------------------------------------------------------------------
    # Duplicate detection — tightened
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_question(text: str) -> str:
        """
        Strip common question-stem prefixes and trailing punctuation so
        that "What is your deployment target?" and
        "Could you tell me your deployment target?" produce near-identical
        token sets.
        """
        # Lowercase
        t = text.lower().strip().rstrip("?. ")

        # Remove leading filler phrases
        filler_re = re.compile(
            r"^(can you|could you|would you|please|do you know|"
            r"what is|what are|what's|how do|how does|have you|"
            r"tell me|let me know|i'd like to know|i need to know)\s+",
            re.IGNORECASE,
        )
        for _ in range(3):  # apply up to 3 times for stacked phrases
            t = filler_re.sub("", t).strip()

        return t

    def _tokenise(self, text: str) -> Set[str]:
        """Return meaningful tokens from a question string."""
        normalised = self._normalise_question(text)
        tokens = set(re.findall(r"\b\w{3,}\b", normalised))
        return tokens - _STOPWORDS

    def _is_duplicate_of_existing(self, question: str, existing: List[str]) -> bool:
        """
        Return True if ``question`` is semantically close enough to any
        item in ``existing`` to be considered a duplicate.

        Uses token-Jaccard overlap after normalisation.  Threshold is
        _DUPLICATE_OVERLAP (default 0.45 — tighter than the old 0.60).
        """
        q_tokens = self._tokenise(question)
        if not q_tokens:
            return False

        for existing_q in existing:
            e_tokens = self._tokenise(existing_q)
            if not e_tokens:
                continue
            intersection = len(q_tokens & e_tokens)
            union        = len(q_tokens | e_tokens)
            overlap      = intersection / union if union else 0.0
            if overlap >= _DUPLICATE_OVERLAP:
                return True

        return False

    # ------------------------------------------------------------------
    # Board helpers
    # ------------------------------------------------------------------

    def _board_as_text(self, board: Dict[str, Any]) -> str:
        lines: List[str] = []
        for category, items in board.items():
            for item in items:
                if isinstance(item, dict):
                    meta = item.get("metadata", {})
                    if isinstance(meta, dict) and meta.get("type") == _GAP_TYPE:
                        continue
                    note = item.get("note", "")
                    if note:
                        lines.append(f"[{category}] {note}")
                elif isinstance(item, str):
                    lines.append(f"[{category}] {item}")
        return "\n".join(lines)

    def _parse_json_list(self, response: str) -> List[str]:
        cleaned = response.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            lines = lines[1:] if lines[0].startswith("```") else lines
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except (json.JSONDecodeError, ValueError):
            m = re.search(r"\[[\s\S]*?\]", cleaned)
            if m:
                try:
                    parsed = json.loads(m.group())
                    if isinstance(parsed, list):
                        return [str(x).strip() for x in parsed if str(x).strip()]
                except (json.JSONDecodeError, ValueError):
                    pass
        return [
            line.lstrip("•-*0123456789. ").strip().strip('"')
            for line in cleaned.splitlines()
            if line.strip() and line.strip() not in ("[]", "")
        ]

    def _build_telegram_summary(self, promoted: List[str], organic: List[str]) -> str:
        lines = [f"{self.icon} Questions Ready"]
        if promoted:
            lines.append(f"\n📌 From info gaps ({len(promoted)}):")
            for q in promoted[:2]:
                lines.append(f"  • {q[:70]}…")
        if organic:
            lines.append(f"\n💬 New questions ({len(organic)}):")
            for q in organic[:2]:
                lines.append(f"  • {q[:70]}…")
        return "\n".join(lines)