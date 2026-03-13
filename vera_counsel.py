#!/usr/bin/env python3
# Vera/Chat/counsel.py - Counsel Mode Execution

"""
Counsel Mode: Multiple models/instances deliberate on the same query.

Modes:
  race       — fastest response wins, streamed immediately
  vote       — all models respond, judge selects best, full response shown
  synthesis  — all models respond, synthesiser combines into unified answer
  debate     — models respond, then rebut each other, judge concludes

Bug fixes vs previous version:
  - Thread count tracked separately from queue reads (fixes double-run)
  - Full responses shown — no truncation in display or judge prompts
  - Debate mode fully implemented
  - Model override support: pass model_overrides={'fast': 'gemma3:12b'} etc.
"""

import threading
import queue
import time
import re
from typing import Iterator, List, Optional, Dict, Any, Tuple
from queue import Empty

from Vera.Logging.logging import LogContext


def _text(chunk) -> str:
    if hasattr(chunk, 'text'):   return chunk.text
    if hasattr(chunk, 'content'): return chunk.content
    if isinstance(chunk, str):    return chunk
    return str(chunk)


# ─────────────────────────────────────────────────────────────────────────────

class CounselExecutor:
    """Executes counsel mode with multiple models or instances."""

    def __init__(self, vera_instance, logger):
        self.vera   = vera_instance
        self.logger = logger

    # ──────────────────────────────────────────────────────────────────────
    # Public entry point
    # ──────────────────────────────────────────────────────────────────────

    def execute(
        self,
        query: str,
        mode: str = 'vote',
        models: Optional[List[str]] = None,
        instances: Optional[List[str]] = None,
        model_overrides: Optional[Dict[str, str]] = None,
        context: Optional[LogContext] = None,
    ) -> Iterator[str]:
        """
        Execute counsel mode.

        Args:
            query:           User query.
            mode:            'race' | 'vote' | 'synthesis' | 'debate'
            models:          Model role names, e.g. ['fast', 'intermediate', 'deep']
            instances:       Ollama instance specs, e.g. ['gpu1:gemma3:12b']
            model_overrides: Override which Ollama model serves each role,
                             e.g. {'fast': 'gemma3:4b', 'deep': 'gemma3:27b'}
            context:         Logging context.
        """
        models         = models or ['fast', 'intermediate', 'deep']
        model_overrides = model_overrides or {}

        rq = queue.Queue()

        if instances:
            threads = self._launch_instance_threads(instances, query, rq, context)
            n_expected = len(threads)
        else:
            threads = self._launch_model_threads(models, query, rq, context, model_overrides)
            n_expected = len(threads)

        self.logger.info(
            f"🏛️ Counsel [{mode}] — {n_expected} participants: {models if not instances else instances}",
            context=context,
        )

        match mode:
            case 'race':
                yield from self._mode_race(rq, n_expected, context)
            case 'synthesis':
                yield from self._mode_synthesis(rq, n_expected, query, context)
            case 'vote':
                yield from self._mode_vote(rq, n_expected, query, context)
            case 'debate':
                yield from self._mode_debate(rq, n_expected, query, context)
            case _:
                yield f"\n[Counsel] Unknown mode '{mode}', falling back to vote\n\n"
                yield from self._mode_vote(rq, n_expected, query, context)

    # ──────────────────────────────────────────────────────────────────────
    # Thread launchers
    # ──────────────────────────────────────────────────────────────────────

    def _get_llm_for_role(self, role: str, override: Optional[str] = None):
        """
        Return the LLM object for a role, respecting any model override.
        If override is set, create a fresh OllamaLLM pointing at that model.
        """
        if override:
            try:
                return self.vera.ollama_manager.create_llm(
                    model=override,
                    temperature=0.7,
                )
            except Exception as e:
                self.logger.warning(f"[Counsel] Override model '{override}' failed: {e}, using default")

        role_map = {
            'fast':         lambda: self.vera.fast_llm,
            'intermediate': lambda: getattr(self.vera, 'intermediate_llm', self.vera.fast_llm),
            'deep':         lambda: self.vera.deep_llm,
            'reasoning':    lambda: self.vera.reasoning_llm,
        }
        return role_map.get(role, lambda: self.vera.fast_llm)()

    def _launch_model_threads(
        self,
        model_types: List[str],
        query: str,
        rq: queue.Queue,
        context: Optional[LogContext],
        model_overrides: Dict[str, str],
    ) -> List[threading.Thread]:

        def run(role: str, llm, label: str):
            try:
                self.logger.debug(f"[Counsel] {label} starting…", context=context)
                t0 = time.time()
                response = "".join(_text(c) for c in self.vera.stream_llm(llm, query))
                elapsed  = time.time() - t0
                rq.put((label, response, elapsed))
                self.logger.success(f"[Counsel] {label} done in {elapsed:.2f}s ({len(response)} chars)", context=context)
            except Exception as e:
                self.logger.error(f"[Counsel] {label} failed: {e}", context=context)
                rq.put((label, f"[Error: {e}]", 0.0))

        threads = []
        seen: Dict[str, int] = {}
        for role in model_types:
            seen[role] = seen.get(role, 0) + 1
            count = seen[role]
            label = role.title() + (f" #{count}" if model_types.count(role) > 1 else "")
            override = model_overrides.get(role)
            llm = self._get_llm_for_role(role, override)
            t = threading.Thread(target=run, args=(role, llm, label), daemon=True)
            t.start()
            threads.append(t)
        return threads

    def _launch_instance_threads(
        self,
        instance_specs: List[str],
        query: str,
        rq: queue.Queue,
        context: Optional[LogContext],
    ) -> List[threading.Thread]:

        def run(spec: str, label: str):
            try:
                instance, _, model = spec.partition(':')
                model = model or getattr(self.vera.selected_models, 'fast_llm', 'gemma2')
                llm = self.vera.ollama_manager.create_llm_with_routing(
                    model=model,
                    routing_mode='manual',
                    selected_instances=[instance],
                    temperature=0.7,
                )
                t0 = time.time()
                response = "".join(_text(c) for c in self.vera.stream_llm(llm, query))
                elapsed  = time.time() - t0
                rq.put((label, response, elapsed))
            except Exception as e:
                self.logger.error(f"[Counsel] {spec} failed: {e}", context=context)
                rq.put((spec, f"[Error: {e}]", 0.0))

        threads = []
        for spec in instance_specs:
            instance = spec.split(':')[0]
            label = spec
            t = threading.Thread(target=run, args=(spec, label), daemon=True)
            t.start()
            threads.append(t)
        return threads

    # ──────────────────────────────────────────────────────────────────────
    # Collect helpers
    # ──────────────────────────────────────────────────────────────────────

    def _collect_all(
        self,
        rq: queue.Queue,
        n_expected: int,
        timeout_per: float = 180.0,
    ) -> List[Tuple[str, str, float]]:
        """
        Wait for exactly n_expected results.
        Uses n_expected (not thread list) so we never over- or under-read.
        """
        results = []
        deadline = time.time() + timeout_per
        while len(results) < n_expected:
            remaining = deadline - time.time()
            if remaining <= 0:
                self.logger.warning(f"[Counsel] Timed out waiting — got {len(results)}/{n_expected}")
                break
            try:
                item = rq.get(timeout=min(remaining, 5.0))
                results.append(item)
            except Empty:
                pass
        return results

    def _divider(self, label: str) -> str:
        return f"\n\n{'─' * 60}\n**{label}**\n{'─' * 60}\n\n"

    # ──────────────────────────────────────────────────────────────────────
    # Mode: Race
    # ──────────────────────────────────────────────────────────────────────

    def _mode_race(self, rq: queue.Queue, n_expected: int, context: Optional[LogContext]) -> Iterator[str]:
        """Fastest response wins — yield as soon as first arrives."""
        try:
            label, response, elapsed = rq.get(timeout=180.0)
        except Empty:
            yield "\n[Counsel/Race] All participants timed out.\n"
            return

        self.logger.success(f"🏆 [Counsel/Race] Winner: {label} ({elapsed:.2f}s)", context=context)
        yield self._divider(f"🏆 {label}  —  {elapsed:.2f}s")
        yield response

    # ──────────────────────────────────────────────────────────────────────
    # Mode: Vote
    # ──────────────────────────────────────────────────────────────────────

    def _mode_vote(self, rq: queue.Queue, n_expected: int, query: str, context: Optional[LogContext]) -> Iterator[str]:
        """All models answer; judge selects the best full response."""
        results = self._collect_all(rq, n_expected)
        if not results:
            yield "\n[Counsel/Vote] No responses received.\n"; return
        if len(results) == 1:
            label, response, elapsed = results[0]
            yield self._divider(f"{label}  —  {elapsed:.2f}s (sole response)")
            yield response
            return

        # Show all candidates in full
        yield f"\n**Counsel Mode: Vote** — {len(results)} candidates\n"
        for idx, (label, response, elapsed) in enumerate(results, 1):
            yield self._divider(f"Candidate {idx}: {label}  —  {elapsed:.2f}s")
            yield response

        # Build judge prompt with FULL responses (no truncation)
        judge_prompt = (
            f"You are an impartial judge selecting the BEST response to this query.\n\n"
            f"Query: {query}\n\n"
        )
        for idx, (label, response, _) in enumerate(results, 1):
            judge_prompt += f"---\nCandidate {idx} ({label}):\n{response}\n\n"
        judge_prompt += (
            f"Evaluate on: accuracy, completeness, clarity, relevance, practical value.\n"
            f"Respond with ONLY: \"Candidate N: <one-sentence reason>\"\n"
            f"N must be a number from 1 to {len(results)}."
        )

        yield self._divider("⚖️ Judging…")
        vote_text = ""
        for chunk in self.vera.stream_llm(self.vera.fast_llm, judge_prompt):
            t = _text(chunk); vote_text += t; yield t

        # Parse winner
        m = re.search(r'Candidate\s+(\d+)', vote_text, re.IGNORECASE)
        if m:
            idx = int(m.group(1)) - 1
            if 0 <= idx < len(results):
                label, response, elapsed = results[idx]
                self.logger.success(f"🏆 [Counsel/Vote] Winner: Candidate {idx+1} ({label})", context=context)
                yield self._divider(f"🏆 Selected: {label}")
                yield response
                return

        # Fallback
        label, response, elapsed = results[0]
        yield self._divider(f"🏆 Selected (fallback): {label}")
        yield response

    # ──────────────────────────────────────────────────────────────────────
    # Mode: Synthesis
    # ──────────────────────────────────────────────────────────────────────

    def _mode_synthesis(self, rq: queue.Queue, n_expected: int, query: str, context: Optional[LogContext]) -> Iterator[str]:
        """All models answer; synthesiser combines into a single unified response."""
        results = self._collect_all(rq, n_expected)
        if not results:
            yield "\n[Counsel/Synthesis] No responses received.\n"; return

        # Show all in full
        yield f"\n**Counsel Mode: Synthesis** — {len(results)} perspectives\n"
        for label, response, elapsed in results:
            yield self._divider(f"{label}  —  {elapsed:.2f}s")
            yield response

        # Build synthesis prompt with full content
        synth_prompt = (
            f"You are synthesising multiple AI perspectives into a single, definitive answer.\n\n"
            f"Original query: {query}\n\n"
        )
        for label, response, _ in results:
            synth_prompt += f"---\n**{label}**:\n{response}\n\n"
        synth_prompt += (
            "Write a unified synthesis that:\n"
            "1. Integrates the strongest insights from each perspective\n"
            "2. Resolves any contradictions clearly\n"
            "3. Highlights points of strong agreement\n"
            "4. Is concise, complete, and directly answers the original query\n\n"
            "Do not reference 'Candidate X' or 'perspective' — write as a single authoritative response."
        )

        yield self._divider("🔀 Synthesising…")
        for chunk in self.vera.stream_llm(self.vera.fast_llm, synth_prompt):
            yield _text(chunk)

    # ──────────────────────────────────────────────────────────────────────
    # Mode: Debate
    # ──────────────────────────────────────────────────────────────────────

    def _mode_debate(self, rq: queue.Queue, n_expected: int, query: str, context: Optional[LogContext]) -> Iterator[str]:
        """
        Structured debate:
          Round 1 — each model gives their initial position
          Round 2 — each model sees the others' positions and rebuts
          Conclusion — a moderator synthesises and gives a final verdict
        """
        results = self._collect_all(rq, n_expected)
        if not results:
            yield "\n[Counsel/Debate] No responses received.\n"; return

        yield f"\n**Counsel Mode: Debate** — {len(results)} participants\n"

        # ── Round 1: Initial positions ───────────────────────────────────
        yield self._divider("📣 Round 1: Initial Positions")
        for label, response, elapsed in results:
            yield self._divider(f"{label}  ({elapsed:.2f}s)")
            yield response

        # ── Round 2: Rebuttals ───────────────────────────────────────────
        yield self._divider("⚔️ Round 2: Rebuttals")
        rebuttals: List[Tuple[str, str]] = []

        # Each participant sees everyone else's position and rebuts
        for i, (label, response, _) in enumerate(results):
            others = "\n\n".join(
                f"**{other_label}** said:\n{other_resp}"
                for j, (other_label, other_resp, _) in enumerate(results)
                if j != i
            )
            rebuttal_prompt = (
                f"You are {label} in a structured debate about:\n{query}\n\n"
                f"Your initial position was:\n{response}\n\n"
                f"The other participants said:\n{others}\n\n"
                f"Write a focused rebuttal (3–6 sentences). "
                f"Defend your position where you're confident, concede any valid points, "
                f"and challenge any weak or incorrect claims."
            )

            # Pick the LLM that matches this label (use fast as fallback)
            rebuttal_llm = self.vera.fast_llm
            label_lower = label.lower()
            if 'intermediate' in label_lower:
                rebuttal_llm = getattr(self.vera, 'intermediate_llm', self.vera.fast_llm)
            elif 'deep' in label_lower or 'complex' in label_lower:
                rebuttal_llm = self.vera.deep_llm
            elif 'reasoning' in label_lower:
                rebuttal_llm = self.vera.reasoning_llm

            yield self._divider(f"{label} rebuts")
            rebuttal_text = ""
            for chunk in self.vera.stream_llm(rebuttal_llm, rebuttal_prompt):
                t = _text(chunk); rebuttal_text += t; yield t
            rebuttals.append((label, rebuttal_text))

        # ── Conclusion: Moderator verdict ────────────────────────────────
        yield self._divider("🎙️ Moderator Conclusion")

        all_positions = "\n\n".join(
            f"**{label}** (initial):\n{resp}\n\n**{label}** (rebuttal):\n{reb}"
            for (label, resp, _), (_, reb) in zip(results, rebuttals)
        )
        conclusion_prompt = (
            f"You are a neutral moderator concluding a structured debate about:\n{query}\n\n"
            f"Here is the full debate:\n{all_positions}\n\n"
            f"Write a moderator conclusion that:\n"
            f"1. Summarises each participant's core argument in 1 sentence\n"
            f"2. Identifies the strongest argument and explains why\n"
            f"3. Notes any genuinely unresolved tensions\n"
            f"4. Gives a clear, actionable final answer to the original query\n\n"
            f"Be direct and authoritative."
        )

        for chunk in self.vera.stream_llm(self.vera.fast_llm, conclusion_prompt):
            yield _text(chunk)