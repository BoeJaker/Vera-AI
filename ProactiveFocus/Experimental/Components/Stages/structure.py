"""
Project Structure Stage — SCAFFOLD-FIRST, DEPTH-FIRST, LOCK-ON-COMPLETE
========================================================================
A complete rewrite of the project structure stage with the following design:

PHASE MODEL (linear progression, never skip ahead):
  0. SCAFFOLD   — detect project intent, build full folder/file skeleton
  1. BASELINE   — write substantive baseline content for every scaffolded file
  2. DEEPEN     — expand each baseline doc to full quality (exhaust before moving on)
  3. BRANCH     — discover and create additional files the project needs
  4. MAINTAIN   — keep everything in sync as the project evolves

KEY PRINCIPLES:
  • Scaffold once, never re-scaffold unless forced.
  • Every iteration exhausts ALL available work in the current phase before
    yielding. The stage only returns when it genuinely cannot do more without
    new planning / external tools.
  • Files are LOCKED (read-only marker) once their content reaches "complete"
    quality. Locked files are never rewritten unless explicitly unlocked.
  • Audit state persists in `.vera_project.json` — successive calls are fast.
  • Each file gets a clear status: pending | writing | baseline | complete | locked
"""

from __future__ import annotations

import difflib
import json
import os
import re
import stat
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Set, Tuple

from Vera.ProactiveFocus.Experimental.Components.Stages.base import BaseStage, StageOutput
from Vera.Toolchain.sandbox import get_project_sandbox


# ---------------------------------------------------------------------------
# Types & constants
# ---------------------------------------------------------------------------

Phase = Literal["scaffold", "baseline", "deepen", "branch", "maintain"]
FileStatus = Literal["pending", "writing", "baseline", "complete", "locked", "skipped"]

PLACEHOLDER_MARKERS = (
    "[Project description]", "[Instructions]", "[Usage]", "[License]",
    "[TODO]", "[Describe", "[Chapters will be listed here]",
    "assert True", "# Dependencies\n",
)

PROTECTED_NAMES: Set[str] = {
    "README.md", "LICENSE", "Makefile", ".gitignore", ".gitattributes",
    "requirements.txt", "setup.py", "pyproject.toml", "package.json",
    "Cargo.toml", "go.mod", "go.sum", ".vera_project.json",
}

# Character thresholds for quality classification
BASELINE_THRESHOLD = 400    # chars — file has real intro content
COMPLETE_THRESHOLD = 1200   # chars — file is substantive and complete

# Similarity threshold for merge detection
SIMILARITY_THRESHOLD = 0.72

# How many files to process per call in BASELINE / DEEPEN phases.
# Set high — we want to exhaust all work each call.
BUDGET_PER_PHASE: Dict[str, int] = {
    "scaffold":  999,   # scaffold is cheap — always do all of it
    "baseline":  999,   # write all baselines in one pass if possible
    "deepen":    999,   # deepen all files before moving on
    "branch":    20,    # branch may create many new files; cap per run
    "maintain":  10,
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ManagedFile:
    """Everything the stage knows about one project file."""
    rel_path:    str
    status:      FileStatus = "pending"
    size:        int        = 0
    mtime:       float      = 0.0
    char_count:  int        = 0
    locked:      bool       = False
    # For merge candidates
    merge_into:  Optional[str] = None


@dataclass
class ScaffoldSpec:
    """Complete project scaffold: directories + seed files."""
    project_type:   str
    project_intent: str
    directories:    List[str]
    seed_files:     Dict[str, str]  # rel_path → seed content (may be empty string)
    key_deliverables: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Stage
# ---------------------------------------------------------------------------

class ProjectStructureStage(BaseStage):
    """
    Scaffold-first, depth-first, lock-on-complete project structure manager.

    Phase transitions (stored in .vera_project.json):
      scaffold  → baseline   (all scaffold files exist)
      baseline  → deepen     (all files have ≥ BASELINE_THRESHOLD chars)
      deepen    → branch     (all files have ≥ COMPLETE_THRESHOLD chars or locked)
      branch    → maintain   (no new files discovered for two consecutive runs)
    """

    PROJECT_SIGNATURES: Dict[str, Dict] = {
        "python":     {"files": ["requirements.txt", "setup.py", "pyproject.toml", "*.py"], "dirs": ["src", "tests", "venv", ".venv"]},
        "javascript": {"files": ["package.json", "*.js", "*.jsx"],       "dirs": ["node_modules", "src", "dist"]},
        "typescript": {"files": ["tsconfig.json", "*.ts", "*.tsx"],       "dirs": ["node_modules", "src", "dist"]},
        "rust":       {"files": ["Cargo.toml", "*.rs"],                   "dirs": ["src", "target"]},
        "go":         {"files": ["go.mod", "*.go"],                       "dirs": ["cmd", "pkg"]},
        "java":       {"files": ["pom.xml", "build.gradle", "*.java"],    "dirs": ["src/main", "target"]},
        "research":   {"files": ["*.md", "sources.json"],                 "dirs": ["research", "reports", "data"]},
        "guide":      {"files": ["*.md", "index.md"],                     "dirs": ["chapters", "images"]},
    }

    TEXT_EXTENSIONS: Set[str] = {
        ".py", ".js", ".jsx", ".ts", ".tsx", ".md", ".txt", ".json",
        ".yaml", ".yml", ".toml", ".ini", ".cfg", ".sh", ".html",
        ".css", ".rst", ".rs", ".go", ".java", ".c", ".cpp", ".h",
    }

    def __init__(self) -> None:
        super().__init__(
            name="Project Structure",
            icon="🏗️",
            description="Scaffold-first, depth-first project structure and content manager",
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
        ctx = self._normalise_context(context)

        sandbox = self._get_sandbox(focus_manager)
        if sandbox is None:
            self._stream_output(focus_manager, "⚠️  No project sandbox — cannot manage structure", "warning")
            output.issues.append("No sandbox configured")
            return output

        project_root = sandbox.project_root
        state        = self._load_state(project_root)

        self._stream_output(focus_manager, f"🏗️  Project root: {project_root}", "info")

        # ── Determine current phase ────────────────────────────────────
        phase: Phase = state.get("phase", "scaffold")
        self._stream_output(focus_manager, f"📍 Phase: {phase.upper()}", "info")

        # ── Run appropriate phase handler ─────────────────────────────
        handler = {
            "scaffold": self._phase_scaffold,
            "baseline": self._phase_baseline,
            "deepen":   self._phase_deepen,
            "branch":   self._phase_branch,
            "maintain": self._phase_maintain,
        }[phase]

        phase_output, new_phase = handler(focus_manager, project_root, state, ctx, output)

        # ── Phase transition ──────────────────────────────────────────
        if new_phase != phase:
            self._stream_output(
                focus_manager,
                f"\n🚀 Phase complete! Advancing: {phase.upper()} → {new_phase.upper()}",
                "success",
            )
            state["phase"] = new_phase

        # ── Persist state ─────────────────────────────────────────────
        state["last_run"]        = datetime.now(timezone.utc).isoformat()
        state["stage_version"]   = "5.0"
        self._save_state(project_root, state)

        return output

    # ==================================================================
    # PHASE 0 — SCAFFOLD
    # ==================================================================

    def _phase_scaffold(
        self,
        focus_manager,
        project_root:  Path,
        state:         Dict[str, Any],
        ctx:           Dict[str, Any],
        output:        StageOutput,
    ) -> Tuple[StageOutput, Phase]:
        """
        Detect project type + intent, then create the COMPLETE directory and file
        scaffold in one pass. Never re-scaffolds unless state is cleared.
        """
        if state.get("scaffold_complete"):
            self._stream_output(focus_manager, "✓ Scaffold already built — advancing", "success")
            return output, "baseline"

        self._stream_output(focus_manager, "🔍 Detecting project type and intent…", "info")
        spec = self._build_scaffold_spec(focus_manager, project_root, state, ctx)

        state["project_type"]     = spec.project_type
        state["project_intent"]   = spec.project_intent
        state["key_deliverables"] = spec.key_deliverables

        self._stream_output(focus_manager, f"  Type:   {spec.project_type}", "info")
        self._stream_output(focus_manager, f"  Intent: {spec.project_intent}", "info")
        if spec.key_deliverables:
            self._stream_output(focus_manager, f"  Deliverables: {', '.join(spec.key_deliverables)}", "info")

        # ── Create directories ────────────────────────────────────────
        self._stream_output(focus_manager, "\n📁 Creating directory scaffold…", "info")
        for dirname in spec.directories:
            dirpath = project_root / dirname
            if not dirpath.exists():
                dirpath.mkdir(parents=True, exist_ok=True)
                self._stream_output(focus_manager, f"  ✓ Created {dirname}/", "success")
                output.artifacts.append(dirname + "/")

        # ── Create seed files ─────────────────────────────────────────
        self._stream_output(focus_manager, "\n📄 Creating seed files…", "info")
        file_registry: Dict[str, Dict] = state.setdefault("files", {})

        for rel_path, seed_content in spec.seed_files.items():
            abs_path = project_root / rel_path
            if abs_path.exists():
                # Register existing file but don't overwrite
                if rel_path not in file_registry:
                    file_registry[rel_path] = self._make_file_record(abs_path, rel_path)
                    self._stream_output(focus_manager, f"  → Registered existing: {rel_path}", "info")
                continue

            # Ensure parent dir exists
            abs_path.parent.mkdir(parents=True, exist_ok=True)

            # Write seed content (may be empty placeholder)
            try:
                abs_path.write_text(seed_content, encoding="utf-8")
                file_registry[rel_path] = {
                    "status":     "pending",
                    "locked":     False,
                    "char_count": len(seed_content),
                    "mtime":      abs_path.stat().st_mtime,
                }
                self._stream_output(focus_manager, f"  ✓ Seeded: {rel_path}", "success")
                output.artifacts.append(rel_path)
            except Exception as exc:
                self._stream_output(focus_manager, f"  ✗ Failed to seed {rel_path}: {exc}", "warning")

        # ── Also scan for existing files not in scaffold ───────────────
        self._scan_and_register_existing(project_root, file_registry)

        state["scaffold_complete"] = True
        total_files = len(file_registry)
        self._stream_output(
            focus_manager,
            f"\n✅ Scaffold complete. {total_files} files registered.",
            "success",
        )
        return output, "baseline"

    # ==================================================================
    # PHASE 1 — BASELINE
    # ==================================================================

    def _phase_baseline(
        self,
        focus_manager,
        project_root:  Path,
        state:         Dict[str, Any],
        ctx:           Dict[str, Any],
        output:        StageOutput,
    ) -> Tuple[StageOutput, Phase]:
        """
        Write real baseline content for every pending / stub file.
        Does not advance until ALL registered text files have ≥ BASELINE_THRESHOLD chars.
        Processes every eligible file per call (exhaust before yielding).
        """
        file_registry = state.setdefault("files", {})
        project_type  = state.get("project_type", "generic")
        project_intent = state.get("project_intent", "")

        # Refresh registry with current disk state
        self._refresh_registry(project_root, file_registry)

        pending = self._files_needing_baseline(project_root, file_registry)

        if not pending:
            self._stream_output(focus_manager, "✅ All files have baseline content.", "success")
            return output, "deepen"

        self._stream_output(
            focus_manager,
            f"📝 Writing baseline content for {len(pending)} files…",
            "info",
        )

        worked = 0
        for rel_path in pending:
            rec      = file_registry[rel_path]
            abs_path = project_root / rel_path

            self._stream_output(focus_manager, f"\n  ✏️  {rel_path} ({rec.get('char_count', 0)} chars → baseline)…", "info")

            try:
                existing = abs_path.read_text(encoding="utf-8", errors="ignore") if abs_path.exists() else ""
            except Exception:
                existing = ""

            content = self._generate_content(
                focus_manager, project_type, project_intent,
                rel_path, existing, task="baseline",
                deliverables=state.get("key_deliverables", []),
            )

            if content and len(content.strip()) >= BASELINE_THRESHOLD:
                if self._write_project_file(focus_manager, rel_path, content):
                    rec["status"]     = "baseline"
                    rec["char_count"] = len(content)
                    rec["mtime"]      = (project_root / rel_path).stat().st_mtime
                    self._stream_output(
                        focus_manager,
                        f"    ✓ Baseline written ({len(content)} chars)",
                        "success",
                    )
                    output.artifacts.append(rel_path)
                    worked += 1
            else:
                self._stream_output(
                    focus_manager,
                    f"    ⚠️  Generated content too short ({len(content) if content else 0} chars) — will retry",
                    "warning",
                )

        self._stream_output(focus_manager, f"\n  Baseline pass: {worked}/{len(pending)} files written", "info")

        # Re-check — did we finish?
        self._refresh_registry(project_root, file_registry)
        remaining = self._files_needing_baseline(project_root, file_registry)
        if not remaining:
            self._stream_output(focus_manager, "✅ All baselines complete!", "success")
            return output, "deepen"

        self._stream_output(
            focus_manager,
            f"  ⏳ {len(remaining)} files still need baseline — continuing next run",
            "info",
        )
        return output, "baseline"

    # ==================================================================
    # PHASE 2 — DEEPEN
    # ==================================================================

    def _phase_deepen(
        self,
        focus_manager,
        project_root:  Path,
        state:         Dict[str, Any],
        ctx:           Dict[str, Any],
        output:        StageOutput,
    ) -> Tuple[StageOutput, Phase]:
        """
        Expand every baseline file to COMPLETE quality, then LOCK it.
        Processes ALL files that need deepening before yielding.
        """
        file_registry  = state.setdefault("files", {})
        project_type   = state.get("project_type", "generic")
        project_intent = state.get("project_intent", "")

        self._refresh_registry(project_root, file_registry)

        to_deepen = self._files_needing_deepening(project_root, file_registry)

        if not to_deepen:
            self._stream_output(focus_manager, "✅ All files complete and locked.", "success")
            return output, "branch"

        self._stream_output(
            focus_manager,
            f"🔬 Deepening {len(to_deepen)} files to completion…",
            "info",
        )

        worked = 0
        for rel_path in to_deepen:
            rec      = file_registry[rel_path]
            abs_path = project_root / rel_path

            self._stream_output(
                focus_manager,
                f"\n  📖 {rel_path} ({rec.get('char_count', 0)} chars → complete)…",
                "info",
            )

            try:
                existing = abs_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                existing = ""

            content = self._generate_content(
                focus_manager, project_type, project_intent,
                rel_path, existing, task="deepen",
                deliverables=state.get("key_deliverables", []),
            )

            if content and len(content.strip()) >= COMPLETE_THRESHOLD:
                if self._write_project_file(focus_manager, rel_path, content):
                    rec["status"]     = "complete"
                    rec["char_count"] = len(content)
                    rec["mtime"]      = abs_path.stat().st_mtime

                    # LOCK the file
                    self._lock_file(abs_path, rec)
                    self._stream_output(
                        focus_manager,
                        f"    ✅ Complete ({len(content)} chars) — LOCKED 🔒",
                        "success",
                    )
                    output.artifacts.append(rel_path)
                    worked += 1
            elif content and len(content.strip()) > rec.get("char_count", 0):
                # Partial improvement — save but don't lock yet
                if self._write_project_file(focus_manager, rel_path, content):
                    rec["char_count"] = len(content)
                    rec["mtime"]      = abs_path.stat().st_mtime
                    self._stream_output(
                        focus_manager,
                        f"    ↗  Improved ({len(content)} chars) — needs more",
                        "info",
                    )
                    worked += 1
            else:
                self._stream_output(
                    focus_manager,
                    f"    – No improvement generated for {rel_path}",
                    "warning",
                )

        self._stream_output(focus_manager, f"\n  Deepen pass: {worked}/{len(to_deepen)} files progressed", "info")

        self._refresh_registry(project_root, file_registry)
        remaining = self._files_needing_deepening(project_root, file_registry)
        if not remaining:
            self._stream_output(focus_manager, "✅ All files deepened and locked!", "success")
            return output, "branch"

        self._stream_output(
            focus_manager,
            f"  ⏳ {len(remaining)} files still need deepening",
            "info",
        )
        return output, "deepen"

    # ==================================================================
    # PHASE 3 — BRANCH
    # ==================================================================

    def _phase_branch(
        self,
        focus_manager,
        project_root:  Path,
        state:         Dict[str, Any],
        ctx:           Dict[str, Any],
        output:        StageOutput,
    ) -> Tuple[StageOutput, Phase]:
        """
        Discover additional files the project needs, create them, and loop
        back into the baseline/deepen cycle. Advances to MAINTAIN when two
        consecutive branch passes find nothing new.
        """
        file_registry  = state.setdefault("files", {})
        project_type   = state.get("project_type", "generic")
        project_intent = state.get("project_intent", "")
        branch_rounds  = state.get("branch_rounds_empty", 0)

        self._stream_output(focus_manager, "🌿 Branching — discovering additional content needs…", "info")

        new_files = self._discover_branch_files(
            focus_manager, project_root, project_type, project_intent,
            file_registry, state.get("key_deliverables", []),
        )

        if not new_files:
            branch_rounds += 1
            state["branch_rounds_empty"] = branch_rounds
            if branch_rounds >= 2:
                self._stream_output(focus_manager, "✅ No new files discovered in 2 passes — project complete!", "success")
                return output, "maintain"
            self._stream_output(
                focus_manager,
                f"  No new files this pass ({branch_rounds}/2 empty passes needed to advance)",
                "info",
            )
            return output, "branch"

        state["branch_rounds_empty"] = 0
        self._stream_output(focus_manager, f"  Found {len(new_files)} new files to create:", "info")
        for rel_path, seed in new_files.items():
            self._stream_output(focus_manager, f"    + {rel_path}", "info")

        # Create them
        created = 0
        for rel_path, seed_content in new_files.items():
            abs_path = project_root / rel_path
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                abs_path.write_text(seed_content, encoding="utf-8")
                file_registry[rel_path] = {
                    "status":     "pending",
                    "locked":     False,
                    "char_count": len(seed_content),
                    "mtime":      abs_path.stat().st_mtime,
                }
                output.artifacts.append(rel_path)
                created += 1
            except Exception as exc:
                self._stream_output(focus_manager, f"    ✗ {rel_path}: {exc}", "warning")

        self._stream_output(focus_manager, f"  ✓ Created {created} new files — cycling back to baseline", "success")
        # Reset to baseline so new files get content
        state["phase"] = "baseline"
        return output, "baseline"

    # ==================================================================
    # PHASE 4 — MAINTAIN
    # ==================================================================

    def _phase_maintain(
        self,
        focus_manager,
        project_root:  Path,
        state:         Dict[str, Any],
        ctx:           Dict[str, Any],
        output:        StageOutput,
    ) -> Tuple[StageOutput, Phase]:
        """
        Maintenance mode: detect new/changed files and handle them.
        Also check for similar/duplicate files to merge.
        """
        file_registry = state.setdefault("files", {})

        # Scan for new files not in registry
        self._scan_and_register_existing(project_root, file_registry)
        self._refresh_registry(project_root, file_registry)

        # Find any newly unlocked or modified files that regressed
        needs_work = [
            rp for rp, rec in file_registry.items()
            if not rec.get("locked")
            and rec.get("status") in ("pending", "baseline")
            and self._is_text_path(rp)
        ]

        if needs_work:
            self._stream_output(
                focus_manager,
                f"🔧 Maintenance: {len(needs_work)} files need attention — cycling to baseline",
                "info",
            )
            state["phase"] = "baseline"
            return output, "baseline"

        # Detect merge candidates
        self._detect_and_merge_similar(focus_manager, project_root, file_registry, state, output)

        self._stream_output(focus_manager, "✅ Project fully maintained.", "success")
        return output, "maintain"

    # ==================================================================
    # SCAFFOLD SPEC BUILDER  (validated, multi-pass)
    # ==================================================================

    # Minimum files that MUST appear in a spec per project type.
    # If the LLM omits any of these, the spec fails validation.
    REQUIRED_FILES_BY_TYPE: Dict[str, List[str]] = {
        "python":     ["README.md", ".gitignore", "requirements.txt"],
        "javascript": ["README.md", ".gitignore", "package.json"],
        "typescript": ["README.md", ".gitignore", "package.json", "tsconfig.json"],
        "rust":       ["README.md", ".gitignore", "Cargo.toml"],
        "go":         ["README.md", ".gitignore", "go.mod"],
        "guide":      ["README.md", ".gitignore", "index.md", "SUMMARY.md"],
        "research":   ["README.md", ".gitignore", "methodology.md", "findings.md"],
        "generic":    ["README.md", ".gitignore"],
    }

    # Minimum number of directories a scaffold must propose
    MIN_DIRECTORIES_BY_TYPE: Dict[str, int] = {
        "python": 3, "javascript": 2, "typescript": 2,
        "rust": 2,  "go": 2,         "guide": 3,
        "research": 4, "generic": 2,
    }

    def _build_scaffold_spec(
        self,
        focus_manager,
        project_root:  Path,
        state:         Dict[str, Any],
        ctx:           Dict[str, Any],
    ) -> ScaffoldSpec:
        """
        Build a validated scaffold spec with up to 3 LLM passes:

        Pass 1 — Initial generation (fast LLM, via orchestrator)
        Pass 2 — Gap-fill: if the spec is missing required elements, ask the
                 LLM to patch it (intermediate LLM)
        Pass 3 — Cross-validation: ask a separate LLM call to review the full
                 spec and flag anything that looks wrong or incomplete.

        Falls back to hard-coded defaults only if all passes fail.
        """
        file_type = self._detect_type_from_files(project_root)
        focus     = getattr(focus_manager, "focus", "") or ""
        board     = self._get_board_data(focus_manager)

        # ── Pass 1: Initial generation ────────────────────────────────
        self._stream_output(focus_manager, "  📋 Pass 1: generating scaffold spec…", "info")
        spec_data = self._scaffold_llm_call(
            focus_manager, focus, board, file_type, ctx, llm_tier="deep_llm"
        )

        if spec_data:
            project_type = spec_data.get("project_type", file_type or "generic")
            issues = self._validate_scaffold_spec(spec_data, project_type)

            if issues:
                self._stream_output(
                    focus_manager,
                    f"  ⚠️  Pass 1 spec has {len(issues)} issues: {'; '.join(issues[:3])}",
                    "warning",
                )

                # ── Pass 2: Gap-fill ──────────────────────────────────
                self._stream_output(focus_manager, "  📋 Pass 2: patching gaps…", "info")
                patched = self._scaffold_patch_call(
                    focus_manager, spec_data, issues, focus, project_type
                )
                if patched:
                    spec_data = patched
                    remaining_issues = self._validate_scaffold_spec(spec_data, project_type)
                    if remaining_issues:
                        self._stream_output(
                            focus_manager,
                            f"  ⚠️  {len(remaining_issues)} issues remain after patch",
                            "warning",
                        )
                    else:
                        self._stream_output(focus_manager, "  ✓ All gaps patched", "success")
            else:
                self._stream_output(focus_manager, "  ✓ Pass 1 spec validated", "success")

            # ── Pass 3: Cross-validation ──────────────────────────────
            self._stream_output(focus_manager, "  📋 Pass 3: cross-validating…", "info")
            spec_data = self._scaffold_cross_validate(
                focus_manager, spec_data, focus, project_type
            )

            # ── Augment with type essentials ──────────────────────────
            extras = self._type_essential_files(project_type)
            for k, v in extras.items():
                if k not in spec_data.get("seed_files", {}):
                    spec_data.setdefault("seed_files", {})[k] = v

            self._stream_output(
                focus_manager,
                f"  ✅ Scaffold spec finalised: "
                f"{len(spec_data.get('directories', []))} dirs, "
                f"{len(spec_data.get('seed_files', {}))} files",
                "success",
            )

            return ScaffoldSpec(
                project_type      = project_type,
                project_intent    = spec_data.get("project_intent", focus or ""),
                directories       = spec_data.get("directories", []),
                seed_files        = spec_data.get("seed_files", {}),
                key_deliverables  = spec_data.get("key_deliverables", []),
            )

        self._stream_output(focus_manager, "  ⚠️  All LLM passes failed — using hard defaults", "warning")
        return self._default_scaffold_spec(file_type or "generic", focus)

    # ------------------------------------------------------------------
    def _scaffold_llm_call(
        self,
        focus_manager,
        focus:     str,
        board:     Dict,
        file_type: Optional[str],
        ctx:       Dict,
        llm_tier:  str = "deep_llm",
    ) -> Optional[Dict]:
        """Single LLM call that returns a raw scaffold dict, or None on failure."""
        prompt = f"""You are planning the COMPLETE file and directory scaffold for a project.

Project Focus / Goal:
{focus}

Board state:
  Ideas:   {len(board.get('ideas', []))} items
  Actions: {len(board.get('actions', []))} items
  Notes:   {board.get('progress', [])[-5:]}

Detected file-based type hint: {file_type or 'unknown'}
{f"Additional context: {ctx.get('context_text', '')}" if ctx.get('context_text') else ""}

Design a COMPLETE, PROFESSIONAL project scaffold.
Think about what a senior developer or technical writer would produce.

Respond with JSON only — no markdown fences, no explanation:
{{
  "project_type": "guide|research|python|javascript|typescript|rust|go|documentation|generic",
  "project_intent": "One precise sentence describing what this project produces.",
  "key_deliverables": ["deliverable1", "deliverable2", "deliverable3"],
  "directories": ["dir1", "dir2/subdir"],
  "seed_files": {{
    "README.md": "# Title\\n\\nBrief intro sentence.",
    "docs/architecture.md": "",
    "src/main.py": "",
    ".gitignore": "__pycache__/\\n*.pyc\\nvenv/\\n"
  }}
}}

RULES (enforced by validator — do not skip):
- seed_files MUST contain README.md and .gitignore.
- For guide/book: include index.md, SUMMARY.md, chapters/ dir, at least 2 chapter stubs.
- For research: include methodology.md, findings.md, data/, analysis/, sources/ dirs.
- For Python: include requirements.txt, src/__init__.py, tests/__init__.py.
- For Rust: include Cargo.toml, src/main.rs or src/lib.rs.
- For Go: include go.mod, main.go or cmd/main.go.
- seed_files values may be empty string — content is written later.
- Include ALL directories and files the finished project will need.
- directories must have at least 2 entries (usually more).
"""
        try:
            # Route through orchestrator if available, else fall back to direct LLM
            response = self._orchestrator_llm_call(
                focus_manager, prompt, llm_tier=llm_tier, task_name="llm.generate"
            )
            match = re.search(r"\{[\s\S]*\}", response)
            if match:
                return json.loads(match.group())
        except Exception as exc:
            self._stream_output(focus_manager, f"    ✗ LLM call failed: {exc}", "warning")
        return None

    def _scaffold_patch_call(
        self,
        focus_manager,
        spec_data:    Dict,
        issues:       List[str],
        focus:        str,
        project_type: str,
    ) -> Optional[Dict]:
        """Ask the LLM to patch a spec that failed validation."""
        issues_text = "\n".join(f"- {i}" for i in issues)
        prompt = (
            f"The following project scaffold spec has validation issues that must be fixed.\n\n"
            f"Project: {focus}\nType: {project_type}\n\n"
            f"ISSUES TO FIX:\n{issues_text}\n\n"
            f"CURRENT SPEC:\n{json.dumps(spec_data, indent=2)[:3000]}\n\n"
            "Return the COMPLETE corrected spec as JSON only (same schema as before).\n"
            "Do NOT omit any existing correct entries — add missing ones and fix wrong ones."
        )
        try:
            response = self._orchestrator_llm_call(
                focus_manager, prompt, llm_tier="intermediate_llm", task_name="llm.generate"
            )
            match = re.search(r"\{[\s\S]*\}", response)
            if match:
                return json.loads(match.group())
        except Exception as exc:
            self._stream_output(focus_manager, f"    ✗ Patch call failed: {exc}", "warning")
        return None

    def _scaffold_cross_validate(
        self,
        focus_manager,
        spec_data:    Dict,
        focus:        str,
        project_type: str,
    ) -> Dict:
        """
        Ask a second LLM to sanity-check the spec.
        Returns the (possibly improved) spec dict.
        """
        prompt = (
            f"Review this project scaffold spec for correctness and completeness.\n"
            f"Project goal: {focus}\nType: {project_type}\n\n"
            f"SPEC:\n{json.dumps(spec_data, indent=2)[:3000]}\n\n"
            "Check for:\n"
            "- Missing essential files for this project type\n"
            "- Directories that are referenced in seed_files but not listed in directories\n"
            "- Implausible or wrong project_type given the focus\n"
            "- seed_files keys that reference non-existent parent directories\n\n"
            "Return the corrected complete spec as JSON only.\n"
            "If the spec is already correct, return it unchanged."
        )
        try:
            response = self._orchestrator_llm_call(
                focus_manager, prompt, llm_tier="deep_llm", task_name="llm.generate"
            )
            match = re.search(r"\{[\s\S]*\}", response)
            if match:
                corrected = json.loads(match.group())
                # Ensure cross-validation didn't strip things out
                if len(corrected.get("seed_files", {})) >= len(spec_data.get("seed_files", {})):
                    self._stream_output(focus_manager, "  ✓ Cross-validation passed", "success")
                    return corrected
                else:
                    self._stream_output(
                        focus_manager,
                        "  ⚠️  Cross-validation response stripped files — keeping original",
                        "warning",
                    )
        except Exception as exc:
            self._stream_output(focus_manager, f"    ✗ Cross-validation failed: {exc}", "warning")
        return spec_data

    def _validate_scaffold_spec(self, spec_data: Dict, project_type: str) -> List[str]:
        """
        Validate a scaffold spec dict.  Returns a list of human-readable issue strings.
        Empty list = spec is valid.
        """
        issues: List[str] = []
        seed_files  = spec_data.get("seed_files", {})
        directories = spec_data.get("directories", [])

        # Required files
        required = self.REQUIRED_FILES_BY_TYPE.get(project_type, self.REQUIRED_FILES_BY_TYPE["generic"])
        for req in required:
            if req not in seed_files:
                issues.append(f"Missing required file: {req}")

        # Minimum directories
        min_dirs = self.MIN_DIRECTORIES_BY_TYPE.get(project_type, 2)
        if len(directories) < min_dirs:
            issues.append(
                f"Too few directories ({len(directories)}) — expected at least {min_dirs} for {project_type}"
            )

        # Parent dirs of seed_files must be in directories list (or be root)
        dir_set = set(directories) | {""}
        for rel_path in seed_files:
            parent = str(Path(rel_path).parent)
            if parent != "." and parent not in dir_set:
                issues.append(f"Parent dir '{parent}' for file '{rel_path}' not in directories list")

        # Must have a non-empty intent
        if not spec_data.get("project_intent", "").strip():
            issues.append("Missing project_intent")

        # Must have deliverables
        if not spec_data.get("key_deliverables"):
            issues.append("Missing key_deliverables")

        # README must have actual content (not empty)
        if "README.md" in seed_files and not seed_files["README.md"].strip():
            issues.append("README.md seed content is empty — should have at least a title")

        return issues

    def _default_scaffold_spec(self, project_type: str, focus: str) -> ScaffoldSpec:
        """Fallback scaffold if LLM fails."""
        specs = {
            "guide": ScaffoldSpec(
                project_type="guide", project_intent=focus or "A comprehensive guide",
                directories=["chapters", "images", "resources", "appendix"],
                seed_files={"README.md": "", "index.md": "", "SUMMARY.md": "", ".gitignore": "*.DS_Store\n"},
            ),
            "research": ScaffoldSpec(
                project_type="research", project_intent=focus or "A research project",
                directories=["research", "reports", "data", "analysis", "sources"],
                seed_files={"README.md": "", "methodology.md": "", "findings.md": "", ".gitignore": "*.DS_Store\ndata/raw/\n"},
            ),
            "python": ScaffoldSpec(
                project_type="python", project_intent=focus or "A Python project",
                directories=["src", "tests", "docs", "scripts"],
                seed_files={"README.md": "", "requirements.txt": "# add dependencies\n",
                            "setup.py": "", "src/__init__.py": "", "tests/__init__.py": "",
                            ".gitignore": "__pycache__/\n*.pyc\nvenv/\n.env\n"},
            ),
        }
        return specs.get(project_type, ScaffoldSpec(
            project_type="generic", project_intent=focus or "A project",
            directories=["src", "docs", "tests"],
            seed_files={"README.md": "", ".gitignore": "*.DS_Store\n.env\n"},
        ))

    def _type_essential_files(self, project_type: str) -> Dict[str, str]:
        """Minimum essential files per type that must always exist."""
        essentials = {
            "python":     {"requirements.txt": "", ".gitignore": "__pycache__/\n*.pyc\nvenv/\n"},
            "javascript": {"package.json": "", ".gitignore": "node_modules/\ndist/\n"},
            "typescript": {"tsconfig.json": "", ".gitignore": "node_modules/\ndist/\n"},
            "rust":       {"Cargo.toml": "", ".gitignore": "target/\n"},
            "go":         {"go.mod": "", ".gitignore": "bin/\n"},
        }
        return essentials.get(project_type, {})

    # ==================================================================
    # ORCHESTRATOR ROUTING HELPERS
    # ==================================================================

    # Maps content_type → (orchestrator_task_name, llm_tier_fallback)
    # orchestrator_task_name is the task registered in task_registrations.py.
    # llm_tier_fallback is the attr on focus_manager.agent used if the
    # orchestrator is unavailable.
    CONTENT_TASK_MAP: Dict[str, Tuple[str, str]] = {
        "guide_chapter":  ("content.generate",  "deep_llm"),
        "research_doc":   ("content.generate",  "deep_llm"),
        "plan":           ("content.generate",  "intermediate_llm"),
        "architecture":   ("content.generate",  "intermediate_llm"),
        "documentation":  ("content.generate",  "intermediate_llm"),
        "readme":         ("content.generate",  "intermediate_llm"),
        "code":           ("content.generate",  "coding_llm"),
        "config":         ("llm.fast",          "fast_llm"),
    }

    def _orchestrator_llm_call(
        self,
        focus_manager,
        prompt:    str,
        llm_tier:  str = "deep_llm",
        task_name: str = "llm.generate",
        timeout:   float = 120.0,
    ) -> str:
        """
        Route a generation call through the orchestrator if available,
        falling back to a direct LLM call on the focus_manager agent.

        Returns the full concatenated response string.
        """
        vera = getattr(focus_manager, "vera_instance", None) \
               or getattr(focus_manager, "_vera", None)

        if vera and hasattr(vera, "orchestrator") and getattr(vera.orchestrator, "running", False):
            try:
                task_kwargs: Dict[str, Any] = {"vera_instance": vera, "prompt": prompt}

                # content.generate needs content_type and llm_type discriminators
                if task_name == "content.generate":
                    task_kwargs["content_type"] = self._llm_tier_to_content_type(llm_tier)
                elif task_name == "llm.generate":
                    task_kwargs["llm_type"] = self._llm_tier_to_llm_type(llm_tier)

                task_id = vera.orchestrator.submit_task(task_name, **task_kwargs)
                chunks: List[str] = []
                for chunk in vera.orchestrator.stream_result(task_id, timeout=timeout):
                    text = chunk if isinstance(chunk, str) else getattr(chunk, "text", str(chunk))
                    if text:
                        chunks.append(text)
                        # Broadcast to UI thought stream
                        self._broadcast_chunk(focus_manager, text)
                return "".join(chunks).strip()

            except Exception as exc:
                self._stream_output(
                    focus_manager,
                    f"    ↩  Orchestrator call failed ({exc}), falling back to direct LLM",
                    "warning",
                )

        # ── Direct fallback ───────────────────────────────────────────
        llm = (
            getattr(getattr(focus_manager, "agent", None), llm_tier, None)
            or getattr(getattr(focus_manager, "agent", None), "intermediate_llm", None)
            or getattr(getattr(focus_manager, "agent", None), "fast_llm", None)
        )
        if not llm:
            return ""

        chunks: List[str] = []
        for chunk in self._stream_llm_with_thought_broadcast(focus_manager, llm, prompt, operation=f"generate_content{llm_tier}_{task_name}"):
            if chunk:
                chunks.append(chunk)
        return "".join(chunks).strip()

    def _broadcast_chunk(self, focus_manager, text: str) -> None:
        """Push a chunk to the UI thought-stream queue if one exists."""
        vera = getattr(focus_manager, "vera_instance", None) \
               or getattr(focus_manager, "_vera", None)
        if vera and hasattr(vera, "thought_queue"):
            try:
                vera.thought_queue.put_nowait(text)
            except Exception:
                pass

    @staticmethod
    def _llm_tier_to_content_type(llm_tier: str) -> str:
        """Map an LLM tier attr name to a content.generate content_type string."""
        return {
            "deep_llm":         "research",
            "intermediate_llm": "documentation",
            "coding_llm":       "code",
            "fast_llm":         "generic",
        }.get(llm_tier, "generic")

    @staticmethod
    def _llm_tier_to_llm_type(llm_tier: str) -> str:
        """Map an LLM tier attr name to the llm.generate llm_type string."""
        return {
            "deep_llm":         "deep",
            "intermediate_llm": "intermediate",
            "coding_llm":       "deep",   # closest available
            "fast_llm":         "fast",
        }.get(llm_tier, "fast")
        
    def _broadcast_source(self, focus_manager, rel_path: str) -> None:
        """Tell the UI which file is currently being written."""
        vera = getattr(focus_manager, "vera_instance", None) \
            or getattr(focus_manager, "_vera", None)
        if vera and hasattr(vera, "broadcast_event"):
            try:
                vera.broadcast_event("llm_source_changed", {"source": rel_path})
            except Exception:
                pass
        # Also update activeCtx directly if accessible
        ws_connections = getattr(vera, "_ws_connections", []) if vera else []
        for ws in ws_connections:
            try:
                import asyncio, json
                msg = json.dumps({"type": "llm_source_changed", "data": {"source": rel_path}})
                asyncio.run_coroutine_threadsafe(ws.send_text(msg), asyncio.get_event_loop())
            except Exception:
                pass
    # ==================================================================
    # CONTENT GENERATION
    # ==================================================================

    def _generate_content(
        self,
        focus_manager,
        project_type:   str,
        project_intent: str,
        rel_path:       str,
        existing:       str,
        task:           str,    # "baseline" | "deepen"
        deliverables:   List[str],
    ) -> str:
        """
        Generate file content by routing through the orchestrator.

        Routing logic (in priority order):
          1. If vera.orchestrator is running → submit a typed task
             (content.generate with correct content_type, OR llm.coding for code files)
          2. If orchestrator unavailable → direct LLM call on the correct tier
             (deep_llm for guides/research, coding_llm for code, intermediate for docs,
              fast_llm for configs)

        The content_type → task/LLM mapping lives in CONTENT_TASK_MAP so it is
        easy to extend without touching this method.
        """
        # ── Broadcast file-level source tag to UI ──────────────────
        self._broadcast_source(focus_manager, rel_path)

        content_type = self._classify_content_type(rel_path)

        if task == "baseline":
            prompt = self._baseline_prompt(
                rel_path, existing, project_type, project_intent, content_type, deliverables
            )
        else:
            prompt = self._deepen_prompt(
                rel_path, existing, project_type, project_intent, content_type, deliverables
            )

        # Look up the orchestrator task + fallback LLM tier
        orch_task, llm_tier = self.CONTENT_TASK_MAP.get(content_type, ("content.generate", "intermediate_llm"))

        self._stream_output(
            focus_manager,
            f"    → routing via {orch_task} (tier: {llm_tier})",
            "info",
        )

        return self._orchestrator_llm_call(
            focus_manager,
            prompt,
            llm_tier=llm_tier,
            task_name=orch_task,
            timeout=180.0 if content_type in ("guide_chapter", "research_doc") else 90.0,
        )

    def _baseline_prompt(
        self,
        rel_path:       str,
        existing:       str,
        project_type:   str,
        project_intent: str,
        content_type:   str,
        deliverables:   List[str],
    ) -> str:
        del_text = "\n".join(f"- {d}" for d in deliverables) if deliverables else ""
        existing_block = f"\n\n=== EXISTING STUB ===\n{existing[:1500]}\n" if existing.strip() else ""

        instructions = {
            "guide_chapter": (
                "Write a complete chapter with:\n"
                "- Engaging introduction explaining the topic\n"
                "- 3-5 main sections with real, substantive content\n"
                "- Concrete examples and step-by-step instructions where relevant\n"
                "- Code blocks or diagrams if appropriate\n"
                "- Summary / key takeaways\n"
                "Minimum 500 words. Use proper markdown."
            ),
            "research_doc": (
                "Write a research document with:\n"
                "- Executive summary\n"
                "- Background / context\n"
                "- Methodology or approach\n"
                "- Initial findings or observations\n"
                "- Open questions / next steps\n"
                "Minimum 400 words."
            ),
            "plan": (
                "Write a technical plan/architecture document with:\n"
                "- Overview and goals\n"
                "- System components and their relationships\n"
                "- Technical decisions and rationale\n"
                "- Implementation phases\n"
                "- Success criteria\n"
                "Minimum 400 words."
            ),
            "documentation": (
                "Write clear documentation with:\n"
                "- Purpose and scope\n"
                "- Installation or setup instructions\n"
                "- Usage examples (with code if applicable)\n"
                "- Configuration options\n"
                "- Troubleshooting section\n"
                "Minimum 350 words."
            ),
            "readme": (
                "Write a high-quality README with:\n"
                "- Project title and one-line description\n"
                "- What it does and why it matters\n"
                "- Quick start / installation\n"
                "- Usage with examples\n"
                "- Project structure overview\n"
                "- Contributing and license\n"
                "Minimum 300 words. Make it compelling."
            ),
            "code": (
                "Write well-structured starter code with:\n"
                "- Module-level docstring\n"
                "- Proper imports\n"
                "- Main classes/functions with full docstrings and type hints\n"
                "- TODO comments for complex logic to implement\n"
                "- Basic error handling\n"
                "- Example usage in __main__ or comments"
            ),
        }

        return (
            f"Project: {project_intent or project_type}\n"
            f"Key deliverables:\n{del_text}\n"
            f"File: {rel_path}\n"
            f"Content type: {content_type}\n"
            f"{existing_block}\n\n"
            f"TASK: Write the BASELINE content for this file.\n\n"
            f"{instructions.get(content_type, instructions['documentation'])}\n\n"
            "CRITICAL: Output ONLY the file content. No preamble, no explanation, no markdown fences."
        )

    def _deepen_prompt(
        self,
        rel_path:       str,
        existing:       str,
        project_type:   str,
        project_intent: str,
        content_type:   str,
        deliverables:   List[str],
    ) -> str:
        del_text = "\n".join(f"- {d}" for d in deliverables) if deliverables else ""

        return (
            f"Project: {project_intent or project_type}\n"
            f"Key deliverables:\n{del_text}\n"
            f"File: {rel_path}\n\n"
            f"=== CURRENT CONTENT ({len(existing)} chars) ===\n{existing[:4000]}\n\n"
            "TASK: Rewrite this file as a DEFINITIVE, COMPLETE version.\n\n"
            "Requirements:\n"
            "- Keep all existing accurate information\n"
            "- Fill every placeholder, stub section, and TODO with real content\n"
            "- Add depth: examples, explanations, diagrams (as ASCII/mermaid), code samples\n"
            "- Make every section substantive — no hand-waving\n"
            "- For guides: 600–1200 words per chapter with real instruction\n"
            "- For research: include concrete findings, data, citations format\n"
            "- For code: all functions should have real implementations, not just pass\n"
            "- After reading this file, a user should need NOTHING ELSE for this topic\n\n"
            "CRITICAL: Output ONLY the final file content. No preamble, no explanation."
        )

    def _classify_content_type(self, rel_path: str) -> str:
        lower = rel_path.lower()
        name  = Path(rel_path).name.lower()

        if name in ("readme.md", "readme.rst"):
            return "readme"
        if any(k in lower for k in ("chapter", "walkthrough", "tutorial", "howto", "lesson")):
            return "guide_chapter"
        if any(k in lower for k in ("research", "findings", "analysis", "study")):
            return "research_doc"
        if any(k in lower for k in ("plan", "architecture", "design", "spec", "roadmap")):
            return "plan"
        if Path(rel_path).suffix.lower() in {".py", ".js", ".ts", ".rs", ".go", ".java", ".cpp"}:
            return "code"
        return "documentation"

    # ==================================================================
    # BRANCH FILE DISCOVERY
    # ==================================================================

    def _discover_branch_files(
        self,
        focus_manager,
        project_root:   Path,
        project_type:   str,
        project_intent: str,
        file_registry:  Dict[str, Any],
        deliverables:   List[str],
    ) -> Dict[str, str]:
        """
        Ask the LLM (via orchestrator) what additional files this project is missing.
        Uses fast_llm tier — this is discovery, not content generation.
        """
        existing_files = sorted(file_registry.keys())
        del_text = "\n".join(f"- {d}" for d in deliverables) if deliverables else ""

        prompt = (
            f"Project: {project_intent or project_type}\n"
            f"Key deliverables:\n{del_text}\n\n"
            f"Currently existing files:\n"
            + "\n".join(f"  - {f}" for f in existing_files)
            + "\n\n"
            "Identify up to 5 additional files this project clearly NEEDS but is MISSING.\n"
            "Focus on files that make the project more complete, professional, or useful.\n"
            "Examples: missing chapters, supporting docs, utility scripts, config files, etc.\n\n"
            "Respond with JSON only:\n"
            '{\n  "new_files": [\n'
            '    {"path": "relative/path.md", "reason": "why needed", "seed": "# Title\\n"}\n'
            '  ]\n}\n\n'
            "Return an EMPTY list if the project is genuinely complete.\n"
            "Do NOT suggest files that already exist or are very similar to existing ones."
        )

        try:
            response = self._orchestrator_llm_call(
                focus_manager, prompt, llm_tier="fast_llm", task_name="llm.generate", timeout=60.0
            )
            match = re.search(r"\{[\s\S]*\}", response)
            if match:
                data = json.loads(match.group())
                new_files: Dict[str, str] = {}
                for item in data.get("new_files", []):
                    path = item.get("path", "").strip()
                    seed = item.get("seed", "")
                    if path and path not in file_registry:
                        new_files[path] = seed
                        self._stream_output(
                            focus_manager,
                            f"    + {path}: {item.get('reason', '')}",
                            "info",
                        )
                return new_files
        except Exception as exc:
            self._stream_output(focus_manager, f"⚠️  Branch discovery failed: {exc}", "warning")

        return {}

    # ==================================================================
    # FILE LOCKING
    # ==================================================================

    def _lock_file(self, abs_path: Path, rec: Dict[str, Any]) -> None:
        """Mark file as read-only on disk and in registry."""
        try:
            current_mode = abs_path.stat().st_mode
            abs_path.chmod(current_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
        except Exception:
            pass  # Locking is best-effort
        rec["locked"] = True
        rec["status"] = "locked"
        rec["locked_at"] = datetime.now(timezone.utc).isoformat()

    def _unlock_file(self, abs_path: Path, rec: Dict[str, Any]) -> None:
        """Restore write permissions."""
        try:
            current_mode = abs_path.stat().st_mode
            abs_path.chmod(current_mode | stat.S_IWUSR | stat.S_IWGRP)
        except Exception:
            pass
        rec["locked"] = False
        rec["status"] = "complete"

    def _write_project_file_safe(self, focus_manager, project_root: Path, rel_path: str,
                                  content: str, file_registry: Dict) -> bool:
        """Write only if not locked; temporarily unlock if explicitly forced."""
        rec = file_registry.get(rel_path, {})
        if rec.get("locked"):
            self._stream_output(focus_manager, f"  🔒 {rel_path} is locked — skipping", "info")
            return False
        return self._write_project_file(focus_manager, rel_path, content)

    # ==================================================================
    # MERGE DETECTION
    # ==================================================================

    def _detect_and_merge_similar(
        self,
        focus_manager,
        project_root:  Path,
        file_registry: Dict[str, Any],
        state:         Dict[str, Any],
        output:        StageOutput,
    ) -> None:
        """Detect and merge similar files in maintenance mode."""
        history: Set[tuple] = {
            tuple(p) for p in state.get("merge_history", [])
        }

        text_files = [
            rp for rp in file_registry
            if rp.endswith((".md", ".txt", ".rst"))
            and Path(rp).name not in PROTECTED_NAMES
            and not file_registry[rp].get("locked")
        ]

        for i, path_a in enumerate(text_files):
            for path_b in text_files[i + 1:]:
                pair = tuple(sorted([path_a, path_b]))
                if pair in history:
                    continue

                name_a = Path(path_a).stem.lower()
                name_b = Path(path_b).stem.lower()
                name_sim = difflib.SequenceMatcher(None, name_a, name_b).ratio()

                if name_sim < 0.6:
                    try:
                        ca = (project_root / path_a).read_text(encoding="utf-8", errors="ignore")[:2000]
                        cb = (project_root / path_b).read_text(encoding="utf-8", errors="ignore")[:2000]
                        content_sim = difflib.SequenceMatcher(None, ca, cb).ratio()
                    except Exception:
                        continue
                    if content_sim < SIMILARITY_THRESHOLD:
                        continue

                self._stream_output(
                    focus_manager,
                    f"  🔀 Merge candidate: '{path_a}' + '{path_b}'",
                    "info",
                )
                state.setdefault("merge_history", []).append(list(pair))

    # ==================================================================
    # REGISTRY HELPERS
    # ==================================================================

    def _scan_and_register_existing(self, project_root: Path, file_registry: Dict) -> None:
        """Scan disk and register any files not already tracked."""
        if not project_root.exists():
            return

        skip_dirs = {"__pycache__", "node_modules", "venv", ".venv", "dist",
                     "build", "target", ".git"}

        for abs_path in project_root.rglob("*"):
            if not abs_path.is_file():
                continue
            parts = abs_path.relative_to(project_root).parts
            if any(p.startswith(".") and p != ".gitignore" for p in parts):
                continue
            if any(p in skip_dirs for p in parts):
                continue

            rel_str = str(abs_path.relative_to(project_root))
            if rel_str not in file_registry and abs_path.suffix.lower() in self.TEXT_EXTENSIONS:
                file_registry[rel_str] = self._make_file_record(abs_path, rel_str)

    def _refresh_registry(self, project_root: Path, file_registry: Dict) -> None:
        """Update char_count and mtime for all registered files."""
        for rel_path, rec in file_registry.items():
            abs_path = project_root / rel_path
            if not abs_path.exists():
                continue
            try:
                current_mtime = abs_path.stat().st_mtime
                if current_mtime != rec.get("mtime"):
                    content = abs_path.read_text(encoding="utf-8", errors="ignore")
                    rec["char_count"] = len(content.strip())
                    rec["mtime"]      = current_mtime
                    # Re-evaluate status if not locked
                    if not rec.get("locked"):
                        rec["status"] = self._compute_status(content, rec.get("status", "pending"))
            except Exception:
                pass

    def _make_file_record(self, abs_path: Path, rel_path: str) -> Dict[str, Any]:
        try:
            content = abs_path.read_text(encoding="utf-8", errors="ignore")
            char_count = len(content.strip())
            status = self._compute_status(content, "pending")
        except Exception:
            char_count = 0
            status = "pending"
        return {
            "status":     status,
            "locked":     False,
            "char_count": char_count,
            "mtime":      abs_path.stat().st_mtime if abs_path.exists() else 0,
        }

    def _compute_status(self, content: str, current_status: str) -> FileStatus:
        stripped = content.strip()
        char_count = len(stripped)

        if char_count == 0:
            return "pending"
        if any(m in content for m in PLACEHOLDER_MARKERS):
            return "pending"
        if char_count < BASELINE_THRESHOLD:
            return "pending"
        if char_count < COMPLETE_THRESHOLD:
            return "baseline"
        return "complete"

    def _files_needing_baseline(self, project_root: Path, file_registry: Dict) -> List[str]:
        return [
            rp for rp, rec in file_registry.items()
            if not rec.get("locked")
            and rec.get("status", "pending") == "pending"
            and self._is_text_path(rp)
            and (project_root / rp).exists()
        ]

    def _files_needing_deepening(self, project_root: Path, file_registry: Dict) -> List[str]:
        return [
            rp for rp, rec in file_registry.items()
            if not rec.get("locked")
            and rec.get("status") in ("pending", "baseline")
            and self._is_text_path(rp)
            and (project_root / rp).exists()
        ]

    def _is_text_path(self, rel_path: str) -> bool:
        return Path(rel_path).suffix.lower() in self.TEXT_EXTENSIONS

    # ==================================================================
    # PROJECT TYPE DETECTION
    # ==================================================================

    def _detect_type_from_files(self, project_root: Path) -> Optional[str]:
        if not project_root.exists():
            return None
        scores: Dict[str, int] = {}
        for ptype, patterns in self.PROJECT_SIGNATURES.items():
            score = 0
            for f in patterns.get("files", []):
                if "*" in f:
                    if list(project_root.glob(f)):
                        score += 2
                elif (project_root / f).exists():
                    score += 3
            for d in patterns.get("dirs", []):
                if (project_root / d).exists():
                    score += 1
            scores[ptype] = score
        best = max(scores, key=scores.get) if scores else None
        return best if best and scores.get(best, 0) > 0 else None

    # ==================================================================
    # STATE PERSISTENCE
    # ==================================================================

    def _load_state(self, project_root: Path) -> Dict[str, Any]:
        state_file = project_root / ".vera_project.json"
        if state_file.exists():
            try:
                return json.loads(state_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"phase": "scaffold", "files": {}}

    def _save_state(self, project_root: Path, state: Dict[str, Any]) -> None:
        state_file = project_root / ".vera_project.json"
        try:
            # Unlock state file before writing
            if state_file.exists():
                try:
                    state_file.chmod(state_file.stat().st_mode | stat.S_IWUSR)
                except Exception:
                    pass
            state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
        except Exception as exc:
            print(f"[ProjectStructureStage] Could not save state: {exc}")

    # ==================================================================
    # UTILITIES
    # ==================================================================

    def _normalise_context(self, context: Any) -> Dict[str, Any]:
        if isinstance(context, dict):
            return context
        if isinstance(context, str):
            return {"context_text": context}
        return {}

    def _get_timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat()