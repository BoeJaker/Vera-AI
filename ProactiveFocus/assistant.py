#!/usr/bin/env python3
"""
ProjectAssistant
================
A conversational agent with full project visibility that can:

  - Scan the entire project tree and read any file
  - View and edit the ProactiveFocus board
  - Trigger any ProactiveFocus stage (ideas, next_steps, actions, questions,
    info_gaps, execution, review, etc.)
  - Make direct file edits or create new files
  - Route every LLM call through the Vera orchestrator (Ollama)

Architecture
------------
- ProjectAssistant          main class; owns the conversation loop
- ProjectScanner            walks the filesystem, caches file contents
- BoardBridge               thin wrapper over ProactiveFocusManager
- AssistantTaskRegistry     registers orchestrator tasks used exclusively
                            by the assistant
- ConversationHistory       rolling context window manager

Usage
-----
    from Vera.ProjectAssistant.project_assistant import ProjectAssistant

    assistant = ProjectAssistant(
        vera_instance=vera,
        project_root="/home/boejaker/langchain/app",
        max_file_size_kb=128,
    )

    # Streaming conversation
    for chunk in assistant.chat("What info gaps are blocking the toolchain work?"):
        print(chunk, end="", flush=True)

    # Direct stage trigger
    assistant.trigger_stage("info_gaps")
    assistant.trigger_stage("ideas", context="focus on WebSocket performance")
"""

import os
import json
import time
import threading
import fnmatch
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple
from dataclasses import dataclass, field

# ── Vera imports (all optional-guarded so the module is importable standalone)
try:
    from Vera.Orchestration.orchestration import task, TaskType, Priority
    from Vera.Logging.logging import LogContext
    VERA_AVAILABLE = True
except ImportError:
    VERA_AVAILABLE = False
    def task(*a, **kw):          # minimal no-op decorator
        def dec(fn): return fn
        return dec
    class TaskType:
        LLM = "llm"
        GENERAL = "general"
    class Priority:
        HIGH = 1
        NORMAL = 2
    class LogContext:
        def __init__(self, **kw): self.extra = kw.get("extra", {})

# ── Stage imports (graceful – not every stage may exist yet)
_STAGE_IMPORTS: Dict[str, str] = {
    "info_gaps":   "Vera.ProactiveFocus.Experimental.Components.Stages.info_gaps.InfoGapStage",
    "ideas":       "Vera.ProactiveFocus.Experimental.Components.Stages.ideas.IdeasStage",
    "next_steps":  "Vera.ProactiveFocus.Experimental.Components.Stages.next_steps.NextStepsStage",
    "actions":     "Vera.ProactiveFocus.Experimental.Components.Stages.actions.ActionsStage",
    "questions":   "Vera.ProactiveFocus.Experimental.Components.Stages.questions.QuestionsStage",
    "review":      "Vera.ProactiveFocus.Experimental.Components.Stages.review.ReviewStage",
    "execution":   "Vera.ProactiveFocus.Experimental.Components.Stages.execution.ExecutionStage",
    "artifacts":   "Vera.ProactiveFocus.Experimental.Components.Stages.artifacts.ArtifactsStage",
}


def _import_stage(name: str):
    """Dynamically import a stage class; return None if unavailable."""
    dotpath = _STAGE_IMPORTS.get(name)
    if not dotpath:
        return None
    module_path, cls_name = dotpath.rsplit(".", 1)
    try:
        import importlib
        module = importlib.import_module(module_path)
        return getattr(module, cls_name)
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# PROJECT SCANNER
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class FileEntry:
    path: str          # relative to project_root
    abs_path: str
    size_bytes: int
    extension: str
    content: Optional[str] = None   # populated on demand


DEFAULT_IGNORE = [
    "__pycache__", "*.pyc", ".git", ".mypy_cache", ".ruff_cache",
    "node_modules", ".venv", "venv", "*.egg-info", "dist", "build",
    ".DS_Store", "*.lock", "*.log",
]


class ProjectScanner:
    """
    Walks the project directory and provides fast file access.

    Files are indexed on construction; content is loaded lazily and cached
    up to `max_file_size_kb` kilobytes per file.
    """

    def __init__(
        self,
        root: str,
        ignore_patterns: Optional[List[str]] = None,
        max_file_size_kb: int = 128,
    ):
        self.root = Path(root).resolve()
        self.ignore_patterns = (ignore_patterns or []) + DEFAULT_IGNORE
        self.max_bytes = max_file_size_kb * 1024
        self._index: Dict[str, FileEntry] = {}   # rel_path → FileEntry
        self._scan_time: float = 0.0
        self._lock = threading.Lock()
        self.scan()

    # ── public ────────────────────────────────────────────────────────────

    def scan(self):
        """(Re)index all files under root."""
        index: Dict[str, FileEntry] = {}
        for abs_path in self.root.rglob("*"):
            if abs_path.is_file() and not self._ignored(abs_path):
                rel = str(abs_path.relative_to(self.root))
                index[rel] = FileEntry(
                    path=rel,
                    abs_path=str(abs_path),
                    size_bytes=abs_path.stat().st_size,
                    extension=abs_path.suffix.lower(),
                )
        with self._lock:
            self._index = index
            self._scan_time = time.time()

    def tree(self, max_depth: int = 6, show_size: bool = False) -> str:
        """Return a compact directory tree string."""
        lines: List[str] = [str(self.root)]
        seen_dirs: set = set()

        with self._lock:
            entries = sorted(self._index.keys())

        for rel in entries:
            parts = rel.split(os.sep)
            if len(parts) > max_depth:
                continue
            # add intermediate dirs
            for depth in range(1, len(parts)):
                dir_key = os.sep.join(parts[:depth])
                if dir_key not in seen_dirs:
                    seen_dirs.add(dir_key)
                    indent = "  " * (depth - 1) + "├── "
                    lines.append(f"{indent}{parts[depth - 1]}/")
            indent = "  " * (len(parts) - 1) + "└── "
            fname = parts[-1]
            if show_size:
                sz = self._index[rel].size_bytes
                fname += f"  ({sz:,} B)"
            lines.append(f"{indent}{fname}")

        return "\n".join(lines)

    def read(self, rel_path: str) -> Optional[str]:
        """Return file content (cached, size-limited)."""
        with self._lock:
            entry = self._index.get(rel_path)
        if not entry:
            # try fuzzy match
            entry = self._fuzzy(rel_path)
        if not entry:
            return None
        if entry.content is not None:
            return entry.content
        if entry.size_bytes > self.max_bytes:
            return f"[File too large to read: {entry.size_bytes:,} B > {self.max_bytes:,} B limit]"
        try:
            text = Path(entry.abs_path).read_text(errors="replace")
            entry.content = text
            return text
        except Exception as exc:
            return f"[Error reading file: {exc}]"

    def write(self, rel_path: str, content: str) -> bool:
        """Write content to a file (creates parents if needed). Returns success."""
        abs_path = self.root / rel_path
        try:
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            abs_path.write_text(content)
            # invalidate cache
            with self._lock:
                if rel_path in self._index:
                    self._index[rel_path].content = None
                    self._index[rel_path].size_bytes = abs_path.stat().st_size
                else:
                    self._index[rel_path] = FileEntry(
                        path=rel_path,
                        abs_path=str(abs_path),
                        size_bytes=abs_path.stat().st_size,
                        extension=Path(rel_path).suffix.lower(),
                    )
            return True
        except Exception:
            return False

    def search(self, query: str, extensions: Optional[List[str]] = None, max_results: int = 20) -> List[Tuple[str, int, str]]:
        """
        Grep-style search.  Returns list of (rel_path, line_no, line_text).
        """
        query_lower = query.lower()
        results: List[Tuple[str, int, str]] = []

        with self._lock:
            candidates = list(self._index.keys())

        for rel in candidates:
            entry = self._index.get(rel)
            if not entry:
                continue
            if extensions and entry.extension not in extensions:
                continue
            content = self.read(rel)
            if not content or isinstance(content, str) and content.startswith("["):
                continue
            for i, line in enumerate(content.splitlines(), 1):
                if query_lower in line.lower():
                    results.append((rel, i, line.rstrip()))
                    if len(results) >= max_results:
                        return results
        return results

    def summary_stats(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._index)
            exts: Dict[str, int] = {}
            for e in self._index.values():
                exts[e.extension] = exts.get(e.extension, 0) + 1
        return {"total_files": total, "by_extension": exts}

    # ── private ───────────────────────────────────────────────────────────

    def _ignored(self, path: Path) -> bool:
        name = path.name
        parts = path.parts
        for pattern in self.ignore_patterns:
            if fnmatch.fnmatch(name, pattern):
                return True
            for part in parts:
                if fnmatch.fnmatch(part, pattern):
                    return True
        return False

    def _fuzzy(self, query: str) -> Optional[FileEntry]:
        """Find best matching file by suffix or basename."""
        q = query.lower().replace("/", os.sep).replace("\\", os.sep)
        with self._lock:
            keys = list(self._index.keys())
        for key in keys:
            if key.lower().endswith(q) or key.lower() == q:
                return self._index[key]
        # basename match
        base = os.path.basename(q)
        for key in keys:
            if os.path.basename(key).lower() == base:
                return self._index[key]
        return None


# ══════════════════════════════════════════════════════════════════════════════
# BOARD BRIDGE
# ══════════════════════════════════════════════════════════════════════════════

class BoardBridge:
    """
    Thin, safe wrapper over ProactiveFocusManager's focus board.
    All mutations go through the manager's own methods so existing
    persistence / locking logic is preserved.
    """

    def __init__(self, focus_manager):
        self.fm = focus_manager

    # ── read ──────────────────────────────────────────────────────────────

    def snapshot(self) -> Dict[str, List[Dict]]:
        """Return current board state as a plain dict."""
        board = getattr(self.fm, "focus_board", {})
        # Deep-copy the relevant parts so we don't hold references
        return {
            cat: list(items)
            for cat, items in board.items()
        }

    def format_for_prompt(self, max_items_per_cat: int = 8) -> str:
        """Return a compact, LLM-readable board summary."""
        lines: List[str] = []
        board = self.snapshot()
        for cat, items in board.items():
            if not items:
                continue
            lines.append(f"### {cat.upper()}")
            for item in items[:max_items_per_cat]:
                text = item.get("text", item.get("content", str(item)))
                status = item.get("metadata", {}).get("status", "")
                priority = item.get("metadata", {}).get("priority", "")
                badge = ""
                if status:
                    badge += f" [{status}]"
                if priority:
                    badge += f" [{priority}]"
                lines.append(f"  • {text[:120]}{badge}")
            if len(items) > max_items_per_cat:
                lines.append(f"  … and {len(items) - max_items_per_cat} more")
        return "\n".join(lines) if lines else "(board is empty)"

    # ── write ─────────────────────────────────────────────────────────────

    def add(self, category: str, text: str, metadata: Optional[Dict] = None) -> bool:
        try:
            self.fm.add_to_focus_board(category, text, metadata or {})
            return True
        except Exception:
            return False

    def remove_by_text(self, category: str, text_fragment: str) -> int:
        """Remove items whose text contains `text_fragment`. Returns count removed."""
        removed = 0
        board = getattr(self.fm, "focus_board", {})
        items = board.get(category, [])
        keep = []
        for item in items:
            t = item.get("text", item.get("content", ""))
            if text_fragment.lower() in t.lower():
                removed += 1
            else:
                keep.append(item)
        board[category] = keep
        return removed

    def update_item_status(self, category: str, text_fragment: str, new_status: str) -> int:
        """Set status on matching items. Returns count updated."""
        updated = 0
        board = getattr(self.fm, "focus_board", {})
        for item in board.get(category, []):
            t = item.get("text", item.get("content", ""))
            if text_fragment.lower() in t.lower():
                item.setdefault("metadata", {})["status"] = new_status
                updated += 1
        return updated

    @property
    def focus(self) -> Optional[str]:
        return getattr(self.fm, "focus", None)

    def set_focus(self, new_focus: str):
        self.fm.set_focus(new_focus)


# ══════════════════════════════════════════════════════════════════════════════
# CONVERSATION HISTORY
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Turn:
    role: str    # "user" | "assistant" | "system"
    content: str
    timestamp: float = field(default_factory=time.time)


class ConversationHistory:
    """Rolling conversation context, token-budget aware (rough char estimate)."""

    def __init__(self, max_chars: int = 12_000):
        self.turns: List[Turn] = []
        self.max_chars = max_chars

    def add(self, role: str, content: str):
        self.turns.append(Turn(role=role, content=content))
        self._trim()

    def _trim(self):
        while self._total_chars() > self.max_chars and len(self.turns) > 2:
            self.turns.pop(0)

    def _total_chars(self) -> int:
        return sum(len(t.content) for t in self.turns)

    def format_for_prompt(self) -> str:
        parts: List[str] = []
        for t in self.turns:
            label = {"user": "User", "assistant": "Assistant", "system": "System"}.get(t.role, t.role)
            parts.append(f"{label}: {t.content}")
        return "\n\n".join(parts)

    def last_n(self, n: int) -> List[Turn]:
        return self.turns[-n:]


# ══════════════════════════════════════════════════════════════════════════════
# INTENT PARSER
# ══════════════════════════════════════════════════════════════════════════════

class IntentParser:
    """
    Lightweight rule-based intent detection so we can dispatch certain
    commands without a round-trip LLM call, and supply the LLM with a hint
    for everything else.
    """

    STAGE_KEYWORDS = {
        "info_gaps":  ["info gap", "information gap", "missing info", "what's missing"],
        "ideas":      ["generate ideas", "brainstorm", "new ideas"],
        "next_steps": ["next steps", "what next", "plan next"],
        "actions":    ["generate actions", "run actions", "execute actions"],
        "questions":  ["generate questions", "ask questions"],
        "review":     ["run review", "review stage", "review board"],
        "execution":  ["run execution", "execute stage", "run the executor"],
        "artifacts":  ["generate artifacts", "create artifacts"],
    }

    FILE_READ_PATTERNS = [
        "show me", "read", "open", "view", "what's in", "contents of",
        "look at", "display",
    ]
    FILE_WRITE_PATTERNS = [
        "write to", "update file", "edit file", "create file",
        "save to", "write file",
    ]
    BOARD_PATTERNS = [
        "show board", "what's on the board", "focus board", "board state",
        "show the board",
    ]
    SEARCH_PATTERNS = [
        "search for", "find in code", "grep", "where is", "find all",
        "locate",
    ]
    TREE_PATTERNS = [
        "show tree", "project structure", "file structure", "directory",
        "list files",
    ]

    def parse(self, message: str) -> Dict[str, Any]:
        ml = message.lower()

        # Stage triggers
        for stage, keywords in self.STAGE_KEYWORDS.items():
            if any(kw in ml for kw in keywords):
                return {"intent": "trigger_stage", "stage": stage}

        # Board
        if any(p in ml for p in self.BOARD_PATTERNS):
            return {"intent": "show_board"}

        # Tree
        if any(p in ml for p in self.TREE_PATTERNS):
            return {"intent": "show_tree"}

        # Search
        if any(p in ml for p in self.SEARCH_PATTERNS):
            return {"intent": "search", "query": message}

        # File read
        if any(p in ml for p in self.FILE_READ_PATTERNS):
            return {"intent": "read_file", "query": message}

        # File write
        if any(p in ml for p in self.FILE_WRITE_PATTERNS):
            return {"intent": "write_file", "query": message}

        return {"intent": "chat"}


# ══════════════════════════════════════════════════════════════════════════════
# ORCHESTRATOR TASK REGISTRATIONS
# ══════════════════════════════════════════════════════════════════════════════

def _register_assistant_tasks():
    """Register tasks used by ProjectAssistant with the global registry."""
    if not VERA_AVAILABLE:
        return

    @task(
        "assistant.chat",
        task_type=TaskType.LLM,
        priority=Priority.HIGH,
        estimated_duration=15.0,
    )
    def assistant_chat(vera_instance, prompt: str):
        """
        Core chat task – routes through the agent router exactly like other
        LLM tasks, falling back to fast_llm.
        """
        from Vera.Orchestration.orchestration import registry
        router = None
        try:
            from Vera.Orchestration.agent_integration import AgentTaskRouter
            if hasattr(vera_instance, "agents") and vera_instance.agents:
                router = AgentTaskRouter(vera_instance)
        except ImportError:
            pass

        if router:
            try:
                agent_name = router.get_agent_for_task("conversation")
                llm = router.create_llm_for_agent(agent_name)
                for chunk in vera_instance._stream_with_thought_polling(llm, prompt):
                    yield chunk if isinstance(chunk, str) else (
                        chunk.text if hasattr(chunk, "text") else str(chunk)
                    )
                return
            except Exception:
                pass

        # Fallback
        for chunk in vera_instance._stream_with_thought_polling(
            vera_instance.fast_llm, prompt
        ):
            yield chunk if isinstance(chunk, str) else (
                chunk.text if hasattr(chunk, "text") else str(chunk)
            )

    @task(
        "assistant.stage_trigger",
        task_type=TaskType.GENERAL,
        priority=Priority.NORMAL,
        estimated_duration=20.0,
    )
    def assistant_stage_trigger(vera_instance, stage_name: str, context: str = ""):
        """Run a single ProactiveFocus stage and return its output."""
        StageClass = _import_stage(stage_name)
        if StageClass is None:
            return {"error": f"Stage '{stage_name}' not found or not importable"}

        fm = getattr(vera_instance, "focus_manager", None)
        if fm is None:
            return {"error": "No focus_manager on vera_instance"}

        try:
            stage = StageClass(vera_instance, fm)
            # Stages expose execute(context) or run(context) – try both
            exec_fn = getattr(stage, "execute", None) or getattr(stage, "run", None)
            if exec_fn is None:
                return {"error": f"Stage '{stage_name}' has no execute/run method"}
            result = exec_fn(context=context or fm.focus or "")
            return {"status": "ok", "stage": stage_name, "result": result}
        except Exception as exc:
            return {"error": str(exc), "stage": stage_name}


_register_assistant_tasks()


# ══════════════════════════════════════════════════════════════════════════════
# PROJECT ASSISTANT
# ══════════════════════════════════════════════════════════════════════════════

class ProjectAssistant:
    """
    Conversational project assistant with full filesystem + board visibility.

    Parameters
    ----------
    vera_instance
        Live Vera instance (needs orchestrator, focus_manager, fast_llm).
    project_root : str
        Absolute path to the project being assisted.
    max_file_size_kb : int
        Largest file that will be read into prompts.
    max_context_files : int
        Max number of files included in a single prompt's context.
    name : str
        Persona name shown to the LLM.
    """

    SYSTEM_PROMPT_TEMPLATE = """You are {name}, an intelligent project assistant with complete access to the Vera project.

## Your Capabilities
- Read any file in the project (ask for path or describe what you need)
- View the ProactiveFocus board at any time
- Trigger ProactiveFocus stages: info_gaps, ideas, next_steps, actions, questions, review, execution, artifacts
- Add, remove, or update items on the focus board
- Write or update project files
- Search the codebase by keyword

## Project Root
{project_root}

## Current Focus
{focus}

## Focus Board (current state)
{board_summary}

## Project Stats
{stats}

## Conversation Guidelines
- Be direct and technical; this is a developer context
- When triggering a stage, explain what you're doing and why
- When reading files, quote relevant portions rather than the whole file
- Suggest concrete next actions based on board state
- If unsure which file the user means, ask for clarification or list candidates

## Available Stages
info_gaps · ideas · next_steps · actions · questions · review · execution · artifacts
"""

    def __init__(
        self,
        vera_instance,
        project_root: str,
        max_file_size_kb: int = 128,
        max_context_files: int = 3,
        name: str = "Vera Project Assistant",
        ignore_patterns: Optional[List[str]] = None,
    ):
        self.vera = vera_instance
        self.name = name
        self.max_context_files = max_context_files

        self.scanner = ProjectScanner(
            root=project_root,
            max_file_size_kb=max_file_size_kb,
            ignore_patterns=ignore_patterns,
        )

        fm = getattr(vera_instance, "focus_manager", None)
        self.board = BoardBridge(fm) if fm else None
        self.history = ConversationHistory(max_chars=14_000)
        self.parser = IntentParser()
        self.logger = getattr(vera_instance, "logger", None)

        # Injected file contexts for the current turn
        self._turn_files: List[Tuple[str, str]] = []

    # ── public API ────────────────────────────────────────────────────────

    def chat(self, user_message: str) -> Iterator[str]:
        """
        Main entry-point.  Streams assistant response chunks.
        Handles fast-path intents without an LLM round-trip where possible.
        """
        self._turn_files = []
        self.history.add("user", user_message)

        intent = self.parser.parse(user_message)

        # ── Fast-path: board snapshot ──────────────────────────────────
        if intent["intent"] == "show_board":
            response = self._show_board()
            self.history.add("assistant", response)
            yield response
            return

        # ── Fast-path: project tree ────────────────────────────────────
        if intent["intent"] == "show_tree":
            response = self._show_tree()
            self.history.add("assistant", response)
            yield response
            return

        # ── Fast-path: stage trigger ───────────────────────────────────
        if intent["intent"] == "trigger_stage":
            stage = intent["stage"]
            yield f"Triggering **{stage}** stage…\n\n"
            result_text = ""
            for chunk in self._run_stage_streaming(stage):
                yield chunk
                result_text += chunk
            self.history.add("assistant", f"[Triggered {stage} stage]\n\n{result_text}")
            return

        # ── Fast-path: search ──────────────────────────────────────────
        if intent["intent"] == "search":
            response = self._handle_search(user_message)
            self.history.add("assistant", response)
            yield response
            return

        # ── Full LLM path ──────────────────────────────────────────────
        prompt = self._build_prompt(user_message, intent)
        full_response = ""

        for chunk in self._stream_llm(prompt):
            yield chunk
            full_response += chunk

        # Parse any action instructions the LLM returned
        self._execute_llm_actions(full_response)
        self.history.add("assistant", full_response)

    def trigger_stage(self, stage_name: str, context: str = "") -> Dict[str, Any]:
        """
        Programmatically trigger a ProactiveFocus stage.
        Returns the stage result dict.
        """
        if VERA_AVAILABLE and hasattr(self.vera, "orchestrator"):
            try:
                task_id = self.vera.orchestrator.submit_task(
                    "assistant.stage_trigger",
                    vera_instance=self.vera,
                    stage_name=stage_name,
                    context=context,
                )
                result = self.vera.orchestrator.wait_for_result(task_id, timeout=60.0)
                return result.result if result else {"error": "timeout"}
            except Exception as exc:
                return {"error": str(exc)}
        else:
            # Direct execution fallback
            StageClass = _import_stage(stage_name)
            if not StageClass:
                return {"error": f"Stage '{stage_name}' not found"}
            fm = getattr(self.vera, "focus_manager", None)
            stage = StageClass(self.vera, fm)
            exec_fn = getattr(stage, "execute", None) or getattr(stage, "run", None)
            if not exec_fn:
                return {"error": "No execute/run method"}
            return exec_fn(context=context)

    def read_file(self, rel_path: str) -> Optional[str]:
        """Return file content by relative path (or fuzzy match)."""
        return self.scanner.read(rel_path)

    def write_file(self, rel_path: str, content: str) -> bool:
        """Write (or overwrite) a project file."""
        return self.scanner.write(rel_path, content)

    def add_to_board(self, category: str, text: str, metadata: Optional[Dict] = None) -> bool:
        if self.board is None:
            return False
        return self.board.add(category, text, metadata)

    def get_board_snapshot(self) -> Dict[str, List[Dict]]:
        if self.board is None:
            return {}
        return self.board.snapshot()

    def rescan(self):
        """Force a fresh filesystem scan (call after external changes)."""
        self.scanner.scan()

    # ── prompt building ───────────────────────────────────────────────────

    def _build_system_prompt(self) -> str:
        stats = self.scanner.summary_stats()
        stats_str = (
            f"{stats['total_files']} files  |  "
            + "  ".join(f"{ext or 'no-ext'}: {n}" for ext, n in
                        sorted(stats["by_extension"].items(), key=lambda x: -x[1])[:8])
        )
        board_summary = self.board.format_for_prompt() if self.board else "(no board)"
        focus = (self.board.focus if self.board else None) or "none"

        return self.SYSTEM_PROMPT_TEMPLATE.format(
            name=self.name,
            project_root=str(self.scanner.root),
            focus=focus,
            board_summary=board_summary,
            stats=stats_str,
        )

    def _build_prompt(self, user_message: str, intent: Dict[str, Any]) -> str:
        """Construct the full prompt sent to the LLM."""
        sections: List[str] = [self._build_system_prompt()]

        # Inject file contents if the message references files
        file_context = self._gather_file_context(user_message)
        if file_context:
            sections.append("## Relevant File Contents\n" + file_context)

        # Conversation history
        hist = self.history.format_for_prompt()
        if hist:
            sections.append("## Conversation History\n" + hist)

        sections.append(f"User: {user_message}")
        sections.append("Assistant:")

        return "\n\n".join(sections)

    def _gather_file_context(self, message: str) -> str:
        """
        Heuristically find files the user is asking about and include
        their content in the prompt context.
        """
        results: List[str] = []
        ml = message.lower()

        with self.scanner._lock:
            all_keys = list(self.scanner._index.keys())

        # Check if any file names appear in the message
        mentioned: List[str] = []
        for key in all_keys:
            basename = os.path.basename(key)
            if basename.lower() in ml or key.lower() in ml:
                mentioned.append(key)

        # Also do keyword search for Python/relevant files
        if not mentioned and ("def " in ml or "class " in ml or "import " in ml):
            search_hits = self.scanner.search(
                message.split()[-1],  # last word as keyword
                extensions=[".py"],
                max_results=3,
            )
            mentioned = list(dict.fromkeys(h[0] for h in search_hits))

        for rel in mentioned[: self.max_context_files]:
            content = self.scanner.read(rel)
            if content:
                # Trim very long files
                if len(content) > 6000:
                    content = content[:6000] + "\n… [truncated]"
                results.append(f"### {rel}\n```\n{content}\n```")
                self._turn_files.append((rel, content))

        return "\n\n".join(results)

    # ── LLM streaming ─────────────────────────────────────────────────────

    def _stream_llm(self, prompt: str) -> Iterator[str]:
        """Stream from orchestrator → assistant.chat task."""
        if VERA_AVAILABLE and hasattr(self.vera, "orchestrator") and self.vera.orchestrator.running:
            try:
                task_id = self.vera.orchestrator.submit_task(
                    "assistant.chat",
                    vera_instance=self.vera,
                    prompt=prompt,
                )
                for chunk in self.vera.orchestrator.stream_result(task_id, timeout=90.0):
                    yield chunk if isinstance(chunk, str) else (
                        chunk.text if hasattr(chunk, "text") else str(chunk)
                    )
                return
            except Exception as exc:
                yield f"\n[Orchestrator error: {exc}. Falling back to direct LLM]\n"

        # Direct fallback
        llm = getattr(self.vera, "fast_llm", None)
        if llm is None:
            yield "[Error: no LLM available]"
            return
        stream_fn = getattr(self.vera, "stream_llm", None)
        if stream_fn:
            for chunk in stream_fn(llm, prompt):
                yield chunk if isinstance(chunk, str) else (
                    chunk.text if hasattr(chunk, "text") else str(chunk)
                )
        else:
            for chunk in llm.stream(prompt):
                yield chunk if isinstance(chunk, str) else (
                    chunk.text if hasattr(chunk, "text") else str(chunk)
                )

    # ── stage streaming ───────────────────────────────────────────────────

    def _run_stage_streaming(self, stage_name: str) -> Iterator[str]:
        """
        Run a stage and stream progress.  Since stages are not generators,
        we run them synchronously and yield status + result.
        """
        yield f"Running **{stage_name}**…\n"

        # Try orchestrator task (non-streaming, but returns result)
        if VERA_AVAILABLE and hasattr(self.vera, "orchestrator") and self.vera.orchestrator.running:
            try:
                task_id = self.vera.orchestrator.submit_task(
                    "assistant.stage_trigger",
                    vera_instance=self.vera,
                    stage_name=stage_name,
                    context=getattr(self.board, "focus", "") or "",
                )
                result_obj = self.vera.orchestrator.wait_for_result(task_id, timeout=60.0)
                result = result_obj.result if result_obj else {"error": "timeout"}
            except Exception as exc:
                result = {"error": str(exc)}
        else:
            result = self.trigger_stage(stage_name)

        if isinstance(result, dict) and "error" in result:
            yield f"⚠️  Stage error: {result['error']}\n"
        else:
            # Format result nicely
            yield self._format_stage_result(stage_name, result)

        # Always refresh board state after stage run
        if self.board:
            yield "\n**Board updated.**\n"
            yield self.board.format_for_prompt()

    def _format_stage_result(self, stage_name: str, result: Any) -> str:
        if result is None:
            return f"Stage **{stage_name}** completed (no output).\n"
        if isinstance(result, dict):
            lines = [f"Stage **{stage_name}** completed:\n"]
            for k, v in result.items():
                if k in ("error",):
                    continue
                if isinstance(v, list):
                    lines.append(f"  **{k}** ({len(v)} items)")
                    for item in v[:5]:
                        t = item.get("text", item.get("content", str(item))) if isinstance(item, dict) else str(item)
                        lines.append(f"    • {t[:100]}")
                else:
                    lines.append(f"  **{k}**: {str(v)[:200]}")
            return "\n".join(lines) + "\n"
        return f"Stage **{stage_name}** result:\n{str(result)[:500]}\n"

    # ── fast-path handlers ────────────────────────────────────────────────

    def _show_board(self) -> str:
        if self.board is None:
            return "No focus board available (no focus_manager on vera instance)."
        focus = self.board.focus or "none"
        board_text = self.board.format_for_prompt(max_items_per_cat=12)
        return f"## Focus Board\n**Current focus:** {focus}\n\n{board_text}"

    def _show_tree(self) -> str:
        tree = self.scanner.tree(max_depth=5)
        stats = self.scanner.summary_stats()
        return (
            f"## Project Structure\n"
            f"Root: `{self.scanner.root}`  |  {stats['total_files']} files\n\n"
            f"```\n{tree}\n```"
        )

    def _handle_search(self, message: str) -> str:
        # Extract the search term (everything after the search keyword)
        import re
        for pattern in [r"search (?:for )?(.+)", r"find (?:in code )?(.+)", r"grep (.+)", r"where is (.+)"]:
            m = re.search(pattern, message, re.I)
            if m:
                query = m.group(1).strip().strip('"\'')
                hits = self.scanner.search(query, max_results=15)
                if not hits:
                    return f"No results found for `{query}`."
                lines = [f"## Search Results for `{query}`\n"]
                for rel, lineno, line_text in hits:
                    lines.append(f"**{rel}:{lineno}**  `{line_text.strip()}`")
                return "\n".join(lines)
        return "Please specify what to search for."

    # ── action parsing ────────────────────────────────────────────────────

    def _execute_llm_actions(self, response: str):
        """
        Scan assistant response for structured action tags and execute them.

        Supported tags (case-insensitive):
            [WRITE_FILE: path/to/file]
            <content>…</content>

            [ADD_TO_BOARD: category | text]
            [TRIGGER_STAGE: stage_name]
        """
        import re

        # File writes
        for m in re.finditer(
            r"\[WRITE_FILE:\s*(.+?)\]\s*<content>(.*?)</content>",
            response, re.DOTALL | re.IGNORECASE,
        ):
            rel_path = m.group(1).strip()
            content = m.group(2).strip()
            ok = self.scanner.write(rel_path, content)
            if self.logger:
                msg = f"File write {'OK' if ok else 'FAILED'}: {rel_path}"
                self.logger.info(msg, context=LogContext(extra={"component": "project_assistant"}))

        # Board additions
        for m in re.finditer(
            r"\[ADD_TO_BOARD:\s*(.+?)\|(.+?)\]",
            response, re.IGNORECASE,
        ):
            cat = m.group(1).strip()
            text = m.group(2).strip()
            if self.board:
                self.board.add(cat, text)

        # Stage triggers
        for m in re.finditer(
            r"\[TRIGGER_STAGE:\s*(\w+)\]",
            response, re.IGNORECASE,
        ):
            stage = m.group(1).strip()
            threading.Thread(
                target=self.trigger_stage,
                args=(stage,),
                daemon=True,
            ).start()