"""
Info Gap Stage — STANDALONE INFORMATION GAP DETECTION & RESOLUTION
====================================================================
A dedicated stage that runs BEFORE all other content stages to identify
missing information that would block or degrade project execution, and
to resolve gaps that have since been filled.

WHY A SEPARATE STAGE:
  The questions stage was conflating two distinct concerns:
    1. Detecting what information is missing (analysis)
    2. Deciding how to fill it (dispatch)

  By separating detection into its own stage, gaps can be identified early
  and then the appropriate downstream stage (questions, actions, next_steps,
  ideas) can pick them up naturally on its next run. This creates a clean
  one-way data flow:

    info_gaps → questions   (user clarification needed)
    info_gaps → actions     (gap fillable by tool execution)
    info_gaps → next_steps  (gap fillable by research/planning)
    info_gaps → ideas       (gap reveals unexplored direction)

GAP LIFECYCLE:
  open     — gap identified, not yet addressed
  actioned — a downstream item references this gap (auto-detected)
  resolved — the board state shows the gap has been filled

BOARD REPRESENTATION:
  Gaps live on the "questions" category with metadata:
    {
      "type":        "info_gap",
      "gap_id":      "<uuid4>",
      "status":      "open" | "actioned" | "resolved",
      "priority":    "high" | "medium" | "low",
      "dispatch_to": ["questions"] | ["actions"] | ["next_steps"] | ["ideas"] | ...
      "created_at":  "<iso>",
      "resolved_at": "<iso>",   # only when resolved
      "resolution":  "<text>",  # brief note on what filled the gap
    }

RESOLUTION DETECTION:
  Each gap has a `check_hint` — a short keyword phrase extracted when the
  gap was created. The resolver looks for that phrase (or close matches)
  in: progress notes, ideas, next_steps, actions, and issues. It also
  optionally asks the LLM to judge whether the board text addresses the gap,
  using the fast_llm tier to keep it cheap.

DUPLICATE SUPPRESSION:
  Before adding a new gap, the stage checks all open gaps with a simple
  token-overlap test. If >60% of tokens match, the new gap is suppressed
  as a duplicate.

DISPATCH:
  The stage does NOT directly create questions/actions/next_steps items.
  Instead it sets `dispatch_to` on the gap metadata.  IterationManager
  reads `has_open_gaps()` and `get_gaps_by_dispatch()` and boosts the
  relevant stage(s) into the next iteration's stage list.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from Vera.ProactiveFocus.Experimental.Components.Stages.base import BaseStage, StageOutput


# ── Constants ──────────────────────────────────────────────────────────────

GAP_TYPE         = "info_gap"
STATUS_OPEN      = "open"
STATUS_ACTIONED  = "actioned"
STATUS_RESOLVED  = "resolved"

# Token-overlap ratio above which a new gap is considered a duplicate
DUPLICATE_TOKEN_OVERLAP = 0.60

# Minimum board-text coverage before we ask the LLM to confirm resolution
# (saves LLM calls for obvious resolutions)
KEYWORD_RESOLVE_THRESHOLD = 0.55

# Priority keywords that force a gap to be high priority
HIGH_PRIORITY_SIGNALS = {
    "blocked", "cannot proceed", "required", "missing critical",
    "undefined", "unknown", "unclear", "no data", "not specified",
}


class InfoGapStage(BaseStage):
    """
    Detect missing information, log gaps to the focus board, resolve
    filled gaps, and signal downstream stages about what to do next.

    This stage should run BEFORE structure, actions, next_steps, and ideas
    so that those stages have complete gap context to work from.
    """

    def __init__(self) -> None:
        super().__init__(
            name="Info Gap Detection",
            icon="🔎",
            description="Identify missing information, track gaps, and signal resolution",
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

        self._stream_output(focus_manager, "🔎 Running information gap analysis…", "info")

        board_snapshot = self._get_board_data(focus_manager)

        # ── Step 1: Resolve gaps that are now filled ───────────────────
        resolved_count = self._resolve_filled_gaps(focus_manager, board_snapshot)
        if resolved_count:
            self._stream_output(
                focus_manager,
                f"  ✅ {resolved_count} gap(s) resolved since last run",
                "success",
            )

        # ── Step 2: Mark gaps that have been actioned downstream ───────
        self._detect_actioned_gaps(focus_manager, board_snapshot)

        # ── Step 3: Identify new gaps ──────────────────────────────────
        open_gaps = self._get_open_gaps(focus_manager)
        new_gaps  = self._identify_new_gaps(focus_manager, board_snapshot, open_gaps, context)

        added = 0
        for gap in new_gaps:
            if not self._is_duplicate(gap["question"], open_gaps):
                self._add_gap_to_board(focus_manager, gap)
                open_gaps.append(gap)  # keep local list in sync for dup-check
                added += 1
                priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
                    gap["priority"], "⚪"
                )
                self._stream_output(
                    focus_manager,
                    f"  {priority_emoji} New gap [{gap['priority']}]: {gap['question'][:100]}",
                    "warning",
                )
                for dest in gap.get("dispatch_to", []):
                    self._stream_output(
                        focus_manager, f"      → dispatch to: {dest}", "info"
                    )

        # ── Step 4: Summary ───────────────────────────────────────────
        all_open  = self._get_open_gaps(focus_manager)
        high      = [g for g in all_open if g.get("priority") == "high"]
        medium    = [g for g in all_open if g.get("priority") == "medium"]
        low       = [g for g in all_open if g.get("priority") == "low"]

        self._stream_output(
            focus_manager,
            f"  📊 Gap summary: {len(all_open)} open "
            f"({len(high)} high / {len(medium)} medium / {len(low)} low), "
            f"{added} new, {resolved_count} resolved",
            "info",
        )

        # ── Step 5: Populate output metadata for IterationManager ─────
        output.metadata["open_gap_count"]     = len(all_open)
        output.metadata["high_gap_count"]     = len(high)
        output.metadata["new_gap_count"]      = added
        output.metadata["resolved_gap_count"] = resolved_count
        output.metadata["dispatch_needed"]    = self._get_dispatch_summary(all_open)

        # Telegram
        if added or resolved_count:
            self._notify_telegram(
                focus_manager,
                self._build_telegram_summary(new_gaps[:3], resolved_count, len(all_open)),
            )

        return output

    # ==================================================================
    # GAP IDENTIFICATION
    # ==================================================================

    def _identify_new_gaps(
        self,
        focus_manager,
        board:     Dict[str, Any],
        open_gaps: List[Dict],
        context:   Optional[Any],
    ) -> List[Dict]:
        """
        Ask the LLM to analyse the board and identify missing information.
        Returns a list of gap dicts (not yet added to the board).
        """
        focus        = getattr(focus_manager, "focus", "") or "Unknown project"
        board_text   = self._board_as_text(board)
        open_gap_text = "\n".join(
            f"  - [{g.get('priority','?')}] {g.get('question','')[:100]}"
            for g in open_gaps[:10]
        ) or "  (none)"

        context_block = f"\nAdditional context:\n{context}\n" if context else ""

        prompt = f"""You are analysing a project focus board to identify MISSING INFORMATION.

Project: {focus}
{context_block}
=== CURRENT BOARD STATE ===
{board_text[:3000]}

=== ALREADY OPEN INFORMATION GAPS (do NOT duplicate these) ===
{open_gap_text}

Your task: Identify up to 5 pieces of information that are MISSING and would
meaningfully unblock progress, improve decision quality, or prevent wasted work.

For each gap, decide HOW it should be filled:
  - "questions"  → needs user clarification / human input
  - "actions"    → can be discovered by a tool (file read, search, scan, API call)
  - "next_steps" → requires planning or research that doesn't fit a single tool call
  - "ideas"      → gap reveals an unexplored direction worth exploring

Respond with a JSON array (empty array if no real gaps exist):
[
  {{
    "question":    "Precise description of what information is missing",
    "priority":    "high|medium|low",
    "dispatch_to": ["questions"],
    "check_hint":  "3-5 keywords that would appear in the board if this gap were filled",
    "rationale":   "Why this gap matters right now"
  }}
]

RULES:
- Only identify gaps that are genuinely blocking or degrading project work RIGHT NOW.
- Do NOT create gaps for things already present on the board.
- Do NOT duplicate existing open gaps listed above.
- "high" priority = blocks execution or causes wasted work without it.
- "medium" priority = would meaningfully improve quality or speed.
- "low" priority = nice to have, not urgent.
- dispatch_to may contain multiple values if multiple stages could help.
- If the board is healthy and nothing is missing, return [].
"""

        try:
            response = self._stream_llm(
                focus_manager,
                focus_manager.agent.fast_llm,
                prompt,
                operation="identify_info_gaps",
            )
        except Exception as exc:
            self._stream_output(focus_manager, f"  ⚠️  Gap analysis LLM call failed: {exc}", "warning")
            return []

        return self._parse_gap_response(response)

    def _parse_gap_response(self, response: str) -> List[Dict]:
        """Parse LLM response into a list of validated gap dicts."""
        cleaned = response.strip()
        # Strip markdown fences
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            lines = lines[1:] if lines[0].startswith("```") else lines
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        parsed = None
        try:
            parsed = json.loads(cleaned)
            if not isinstance(parsed, list):
                parsed = [parsed] if isinstance(parsed, dict) else []
        except (json.JSONDecodeError, ValueError):
            m = re.search(r"\[[\s\S]*\]", cleaned)
            if m:
                try:
                    parsed = json.loads(m.group())
                except (json.JSONDecodeError, ValueError):
                    pass

        if not parsed:
            return []

        gaps = []
        valid_dispatches = {"questions", "actions", "next_steps", "ideas"}
        for item in parsed:
            if not isinstance(item, dict):
                continue
            question = (item.get("question") or "").strip()
            if not question:
                continue
            dispatch = [
                d for d in item.get("dispatch_to", ["questions"])
                if d in valid_dispatches
            ] or ["questions"]
            # check_hint and rationale may come back as lists if the LLM
            # returns keywords as an array instead of a string — coerce safely.
            raw_hint     = item.get("check_hint") or ""
            if isinstance(raw_hint, list):
                raw_hint = " ".join(str(x) for x in raw_hint)
            check_hint   = str(raw_hint).strip() or question[:60]

            raw_rationale = item.get("rationale") or ""
            if isinstance(raw_rationale, list):
                raw_rationale = " ".join(str(x) for x in raw_rationale)
            rationale     = str(raw_rationale).strip()[:200]

            gaps.append({
                "question":    question,
                "priority":    item.get("priority", "medium") if item.get("priority") in ("high", "medium", "low") else "medium",
                "dispatch_to": dispatch,
                "check_hint":  check_hint,
                "rationale":   rationale,
            })

        return gaps

    # ==================================================================
    # GAP RESOLUTION
    # ==================================================================

    def _resolve_filled_gaps(
        self,
        focus_manager,
        board: Dict[str, Any],
    ) -> int:
        """
        Check every open gap against the current board state.
        If a gap appears to be filled, mark it as resolved.

        Two-phase check:
          1. Keyword check — fast, no LLM call.
          2. LLM confirmation — only when keyword check is borderline.

        Returns the count of newly resolved gaps.
        """
        open_gaps    = self._get_open_gaps(focus_manager)
        board_text   = self._board_as_text(board).lower()
        resolved     = 0

        for gap_item in open_gaps:
            meta  = gap_item.get("metadata", {}) if isinstance(gap_item, dict) else {}
            if meta.get("status") != STATUS_OPEN:
                continue

            gap_id    = meta.get("gap_id", "")
            check_hint = meta.get("check_hint", "")
            question   = meta.get("question", gap_item.get("note", ""))

            if not check_hint and not question:
                continue

            # ── Phase 1: keyword overlap ────────────────────────────
            hint_tokens = set(re.findall(r"\b\w{3,}\b", check_hint.lower()))
            if not hint_tokens:
                hint_tokens = set(re.findall(r"\b\w{3,}\b", question.lower()))

            board_tokens = set(re.findall(r"\b\w{3,}\b", board_text))
            if hint_tokens:
                overlap = len(hint_tokens & board_tokens) / len(hint_tokens)
            else:
                overlap = 0.0

            if overlap < KEYWORD_RESOLVE_THRESHOLD:
                continue  # Clearly not filled yet

            # ── Phase 2: LLM confirmation ───────────────────────────
            # Only call LLM when keyword overlap is promising but not conclusive
            if overlap < 0.85:
                confirmed = self._llm_confirm_resolution(
                    focus_manager, question, board
                )
                if not confirmed:
                    continue

            # ── Mark as resolved ────────────────────────────────────
            self._mark_gap_resolved(
                focus_manager,
                gap_id,
                resolution=f"Covered by board content (keyword overlap {overlap:.0%})",
            )
            resolved += 1

        return resolved

    def _llm_confirm_resolution(
        self,
        focus_manager,
        question: str,
        board:    Dict[str, Any],
    ) -> bool:
        """
        Ask the fast LLM whether the board now contains an answer to
        the gap question. Returns True if confirmed resolved.
        """
        board_text = self._board_as_text(board)
        prompt = (
            f"Does the following board content contain a satisfactory answer to this question?\n\n"
            f"QUESTION: {question}\n\n"
            f"BOARD CONTENT (excerpt):\n{board_text[:2000]}\n\n"
            "Respond with exactly YES or NO."
        )
        try:
            response = ""
            for chunk in self._stream_llm_with_thought_broadcast(
                focus_manager, focus_manager.agent.fast_llm, prompt
            ):
                response += chunk
            return response.strip().upper().startswith("YES")
        except Exception:
            return False

    def _detect_actioned_gaps(
        self,
        focus_manager,
        board: Dict[str, Any],
    ) -> None:
        """
        Scan actions, next_steps, and ideas for text that references open gaps.
        Mark matched gaps as 'actioned' so the UI can show they're in progress.
        """
        open_gaps = self._get_open_gaps(focus_manager)
        if not open_gaps:
            return

        # Build a flat list of downstream item texts
        downstream_texts: List[str] = []
        for category in ("actions", "next_steps", "ideas"):
            for item in board.get(category, []):
                note = item.get("note", "") if isinstance(item, dict) else str(item)
                downstream_texts.append(note.lower())

        combined = " ".join(downstream_texts)

        for gap_item in open_gaps:
            meta = gap_item.get("metadata", {}) if isinstance(gap_item, dict) else {}
            if meta.get("status") != STATUS_OPEN:
                continue

            check_hint = meta.get("check_hint", "")
            gap_id     = meta.get("gap_id", "")
            if not check_hint or not gap_id:
                continue

            hint_tokens = set(re.findall(r"\b\w{3,}\b", check_hint.lower()))
            if not hint_tokens:
                continue

            combined_tokens = set(re.findall(r"\b\w{3,}\b", combined))
            overlap = len(hint_tokens & combined_tokens) / len(hint_tokens) if hint_tokens else 0

            if overlap >= 0.50:
                self._mark_gap_actioned(focus_manager, gap_id)

    # ==================================================================
    # BOARD GAP OPERATIONS
    # ==================================================================

    def _add_gap_to_board(self, focus_manager, gap: Dict) -> None:
        """Add a gap dict to the focus board's 'questions' category."""
        gap_id    = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        metadata  = {
            "type":        GAP_TYPE,
            "gap_id":      gap_id,
            "status":      STATUS_OPEN,
            "priority":    gap.get("priority", "medium"),
            "dispatch_to": gap.get("dispatch_to", ["questions"]),
            "check_hint":  gap.get("check_hint", ""),
            "rationale":   gap.get("rationale", ""),
            "question":    gap.get("question", ""),
            "created_at":  timestamp,
        }
        self._add_to_board(
            focus_manager,
            "questions",
            gap.get("question", ""),
            metadata=metadata,
        )

    def _mark_gap_resolved(
        self,
        focus_manager,
        gap_id:     str,
        resolution: str = "",
    ) -> bool:
        """
        Find the board item with this gap_id and update its status to resolved.
        Also adds a progress note.  Returns True if found and updated.
        """
        questions = focus_manager.board.get_category("questions")
        for item in questions:
            if not isinstance(item, dict):
                continue
            meta = item.get("metadata", {})
            if meta.get("gap_id") == gap_id and meta.get("status") == STATUS_OPEN:
                meta["status"]      = STATUS_RESOLVED
                meta["resolved_at"] = datetime.now(timezone.utc).isoformat()
                meta["resolution"]  = resolution or "Marked resolved"
                # Log to progress
                question_text = meta.get("question", item.get("note", ""))[:120]
                self._add_to_board(
                    focus_manager,
                    "progress",
                    f"[Gap resolved] {question_text}",
                    metadata={
                        "type":       "gap_resolution",
                        "gap_id":     gap_id,
                        "resolution": resolution,
                    },
                )
                return True
        return False

    def _mark_gap_actioned(self, focus_manager, gap_id: str) -> bool:
        """Mark a gap as actioned (a downstream item is addressing it)."""
        questions = focus_manager.board.get_category("questions")
        for item in questions:
            if not isinstance(item, dict):
                continue
            meta = item.get("metadata", {})
            if meta.get("gap_id") == gap_id and meta.get("status") == STATUS_OPEN:
                meta["status"]      = STATUS_ACTIONED
                meta["actioned_at"] = datetime.now(timezone.utc).isoformat()
                return True
        return False

    def _get_open_gaps(self, focus_manager) -> List[Dict]:
        """Return all board items that are open info_gaps."""
        questions = focus_manager.board.get_category("questions")
        return [
            item for item in questions
            if isinstance(item, dict)
            and item.get("metadata", {}).get("type") == GAP_TYPE
            and item.get("metadata", {}).get("status") == STATUS_OPEN
        ]

    # ==================================================================
    # DISPATCH HELPERS  (used by IterationManager)
    # ==================================================================

    @staticmethod
    def has_open_gaps(focus_manager) -> bool:
        """Quick check — True if any open info_gaps exist on the board."""
        questions = focus_manager.board.get_category("questions")
        return any(
            isinstance(item, dict)
            and item.get("metadata", {}).get("type") == GAP_TYPE
            and item.get("metadata", {}).get("status") == STATUS_OPEN
            for item in questions
        )

    @staticmethod
    def has_high_priority_gaps(focus_manager) -> bool:
        """True if any HIGH priority open gaps exist."""
        questions = focus_manager.board.get_category("questions")
        return any(
            isinstance(item, dict)
            and item.get("metadata", {}).get("type") == GAP_TYPE
            and item.get("metadata", {}).get("status") == STATUS_OPEN
            and item.get("metadata", {}).get("priority") == "high"
            for item in questions
        )

    @staticmethod
    def get_gaps_by_dispatch(focus_manager) -> Dict[str, int]:
        """
        Return a dict of {dispatch_target: count_of_open_gaps} so
        IterationManager knows which downstream stages to boost.

        Example: {"questions": 2, "actions": 1}
        """
        questions = focus_manager.board.get_category("questions")
        counts: Dict[str, int] = {}
        for item in questions:
            if not isinstance(item, dict):
                continue
            meta = item.get("metadata", {})
            if meta.get("type") != GAP_TYPE or meta.get("status") != STATUS_OPEN:
                continue
            for dest in meta.get("dispatch_to", ["questions"]):
                counts[dest] = counts.get(dest, 0) + 1
        return counts

    @staticmethod
    def get_open_gap_count(focus_manager) -> int:
        questions = focus_manager.board.get_category("questions")
        return sum(
            1 for item in questions
            if isinstance(item, dict)
            and item.get("metadata", {}).get("type") == GAP_TYPE
            and item.get("metadata", {}).get("status") == STATUS_OPEN
        )

    # ==================================================================
    # HELPERS
    # ==================================================================

    def _get_dispatch_summary(self, open_gaps: List[Dict]) -> Dict[str, int]:
        """Aggregate dispatch_to counts across all open gaps."""
        counts: Dict[str, int] = {}
        for gap in open_gaps:
            meta = gap.get("metadata", {}) if isinstance(gap, dict) else {}
            for dest in meta.get("dispatch_to", gap.get("dispatch_to", ["questions"])):
                counts[dest] = counts.get(dest, 0) + 1
        return counts

    def _board_as_text(self, board: Dict[str, Any]) -> str:
        """Flatten the board to a searchable text blob."""
        lines: List[str] = []
        for category, items in board.items():
            for item in items:
                if isinstance(item, dict):
                    note = item.get("note", "")
                    meta = item.get("metadata", {})
                    # Skip gap items themselves — we don't want them to
                    # self-resolve by appearing in the search text.
                    if isinstance(meta, dict) and meta.get("type") == GAP_TYPE:
                        continue
                    if note:
                        lines.append(f"[{category}] {note}")
                elif isinstance(item, str):
                    lines.append(f"[{category}] {item}")
        return "\n".join(lines)

    def _is_duplicate(self, question: str, open_gaps: List[Dict]) -> bool:
        """Return True if question overlaps too strongly with an existing open gap."""
        q_tokens = set(re.findall(r"\b\w{3,}\b", question.lower()))
        if not q_tokens:
            return False
        for gap in open_gaps:
            meta        = gap.get("metadata", {}) if isinstance(gap, dict) else {}
            existing_q  = meta.get("question", gap.get("note", ""))
            e_tokens    = set(re.findall(r"\b\w{3,}\b", existing_q.lower()))
            if not e_tokens:
                continue
            overlap = len(q_tokens & e_tokens) / max(len(q_tokens), len(e_tokens))
            if overlap >= DUPLICATE_TOKEN_OVERLAP:
                return True
        return False

    def _build_telegram_summary(
        self,
        new_gaps:      List[Dict],
        resolved_count: int,
        total_open:    int,
    ) -> str:
        lines = [f"{self.icon} Info Gap Update"]
        if resolved_count:
            lines.append(f"✅ {resolved_count} gap(s) resolved")
        if new_gaps:
            lines.append(f"⚠️  {len(new_gaps)} new gap(s):")
            for gap in new_gaps[:3]:
                priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
                    gap.get("priority", "medium"), "⚪"
                )
                lines.append(f"  {priority_emoji} {gap.get('question', '')[:70]}…")
        lines.append(f"📊 Total open: {total_open}")
        return "\n".join(lines)