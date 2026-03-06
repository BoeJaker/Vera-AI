"""
BaseStage — Foundation for all ProactiveFocus workflow stages.
==============================================================
Provides:
- Streaming output to the UI (console + WebSocket)
- LLM helpers (stream + thought broadcast)
- Focus-board helpers
- Tool execution with chunked streaming
- Artifact saving to project directory
- Memory querying
- Telegram notifications (send + ask with response waiting)
- Unified sandbox helpers — every stage can call
  ``self._sync_sandbox(fm)`` after tool or command execution
  and trust that writes reach project_root immediately.

v3.3 CHANGES:
- _set_llm_source now broadcasts 'llm_source_changed' via WebSocket
  so the UI can split response entries when the operation changes.
- _stream_llm broadcasts response_start with explicit source before
  streaming begins, and response_end when complete.
"""

from __future__ import annotations

import asyncio
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from Vera.Toolchain.sandbox import (
    FileChange,
    ProjectSandbox,
    get_project_sandbox,
    sync_agent_sandbox,
)


# ---------------------------------------------------------------------------
# Stage output container
# ---------------------------------------------------------------------------

@dataclass
class StageOutput:
    """Structured result from a stage execution."""

    # Core content buckets
    insights:    List[str]            = field(default_factory=list)
    ideas:       List[Any]            = field(default_factory=list)
    actions:     List[Any]            = field(default_factory=list)
    next_steps:  List[Any]            = field(default_factory=list)
    issues:      List[str]            = field(default_factory=list)
    questions:   List[Dict[str, Any]] = field(default_factory=list)
    artifacts:   List[Any]            = field(default_factory=list)  # str paths or dicts

    # Execution tracking
    tool_calls:  List[Dict[str, Any]] = field(default_factory=list)
    memory_refs: List[str]            = field(default_factory=list)
    metadata:    Dict[str, Any]       = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Level -> colour mapping (used for console + WebSocket)
# ---------------------------------------------------------------------------

_LEVEL_COLOURS: Dict[str, str] = {
    "info":    "blue",
    "success": "green",
    "warning": "yellow",
    "error":   "red",
    "tool":    "cyan",
}


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class BaseStage(ABC):
    """
    Abstract base for all ProactiveFocus stages.

    Concrete stages must implement ``execute(focus_manager, context)``
    and call ``super().__init__(name, icon, description)``.
    """

    def __init__(self, name: str, icon: str = "🔧", description: str = "") -> None:
        self.name        = name
        self.icon        = icon
        self.description = description

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def execute(
        self,
        focus_manager,
        context: Optional[Dict[str, Any]] = None,
    ) -> StageOutput:
        """Run the stage and return a StageOutput."""

    def should_execute(self, focus_manager) -> bool:
        """
        Gate check before execution.

        Default: always True.  Override for conditional stages.
        """
        return True

    # ------------------------------------------------------------------
    # Streaming output  (console + WebSocket, colour-aware)
    # ------------------------------------------------------------------

    def _stream_output(
        self,
        focus_manager,
        message: str,
        level: str = "info",
        end: str = "\n",
    ) -> None:
        """
        Push *message* to every available output channel on the focus manager.

        Channels tried (all optional):
        - focus_manager._stream_output(message, level)
        - focus_manager._stream_to_console(message, color=..., end=...)
        - focus_manager._stream_to_websocket({...})

        Falls back to print() when none of the above exist.
        """
        colour = _LEVEL_COLOURS.get(level, "white")

        # Primary: unified focus-manager stream
        primary = getattr(focus_manager, "_stream_output", None)
        if callable(primary):
            primary(message, level)

        # Secondary: explicit console stream
        console = getattr(focus_manager, "_stream_to_console", None)
        if callable(console):
            console(message, color=colour, end=end)

        # Tertiary: WebSocket push
        ws = getattr(focus_manager, "_stream_to_websocket", None)
        if callable(ws):
            ws({
                "type":    "stage_output",
                "level":   level,
                "message": message,
                "stage":   self.name,
            })

        # Last resort
        if not any([callable(primary), callable(console), callable(ws)]):
            print(f"[{self.name}] [{level.upper()}] {message}", end=end)

    # ------------------------------------------------------------------
    # LLM helpers
    # ------------------------------------------------------------------

    def _stream_llm(self, focus_manager, llm, prompt: str, operation: str = "") -> str:
        """
        Stream prompt through llm and return full response string.

        Args:
            focus_manager: Focus manager instance
            llm: LLM instance
            prompt: Prompt string
            operation: Human-readable label for what this LLM call is doing,
                    e.g. "Generate Actions", "Structure Plan", "Next Steps".
                    Passed as 'source' to thought broadcast events so the UI
                    can group thoughts by operation.
        """
        # Build source label: "StageName › Operation" or just "StageName"
        source = f"{self.name} › {operation}" if operation else self.name

        # Set source hint on focus_manager AND broadcast to UI
        self._set_llm_source(focus_manager, source)

        # Signal response start with explicit source so the UI creates
        # a properly labelled entry BEFORE chunks arrive.
        self._broadcast_response_start(focus_manager, source)

        broadcaster = getattr(focus_manager, "_stream_llm_with_thought_broadcast", None)
        if callable(broadcaster):
            import inspect
            sig = inspect.signature(broadcaster)
            chunks = []
            try:
                if "source" in sig.parameters:
                    for chunk in broadcaster(llm, prompt, source=source):
                        if chunk:
                            chunks.append(chunk)
                else:
                    for chunk in broadcaster(llm, prompt):
                        if chunk:
                            chunks.append(chunk)
            except Exception as exc:
                self._stream_output(focus_manager, f"LLM stream error: {exc}", "error")
            result = "".join(chunks)
            self._broadcast_response_end(focus_manager)
            self._clear_llm_source(focus_manager)
            return result

        try:
            response = llm.invoke(prompt)
            content = response.content if hasattr(response, "content") else str(response)
            # Broadcast the full response as a single chunk
            self._broadcast_response_chunk(focus_manager, content)
            self._broadcast_response_end(focus_manager)
            return content
        except Exception as exc:
            self._stream_output(focus_manager, f"LLM error: {exc}", "error")
            self._broadcast_response_end(focus_manager)
            return ""
        finally:
            self._clear_llm_source(focus_manager)

    def _set_llm_source(self, focus_manager, source: str) -> None:
        """
        Store the current LLM operation source on focus_manager so
        _stream_llm_with_thought_broadcast can embed it in thought events.

        v3.3: Also broadcasts 'llm_source_changed' to WebSocket so the
        UI can split response/thought entries when the operation changes.
        """
        try:
            focus_manager._current_llm_source = source
        except Exception:
            pass

        # Broadcast source change to WebSocket
        ws = getattr(focus_manager, "_stream_to_websocket", None)
        if callable(ws):
            try:
                ws({
                    "type":   "llm_source_changed",
                    "source": source,
                    "stage":  self.name,
                })
            except Exception:
                pass

        # Also update via _broadcast_sync if available
        broadcast = getattr(focus_manager, "_broadcast_sync", None)
        if callable(broadcast):
            try:
                broadcast("llm_source_changed", {"source": source, "stage": self.name})
            except Exception:
                pass

    def _clear_llm_source(self, focus_manager) -> None:
        try:
            focus_manager._current_llm_source = None
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Response broadcast helpers (v3.3)
    # ------------------------------------------------------------------

    def _broadcast_response_start(self, focus_manager, source: str) -> None:
        """Signal the start of a new LLM response stream to the UI."""
        ws = getattr(focus_manager, "_stream_to_websocket", None)
        if callable(ws):
            try:
                ws({
                    "type":      "response_start",
                    "source":    source,
                    "stage":     self.name,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                })
            except Exception:
                pass

        broadcast = getattr(focus_manager, "_broadcast_sync", None)
        if callable(broadcast):
            try:
                broadcast("response_start", {
                    "source":    source,
                    "stage":     self.name,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                })
            except Exception:
                pass

    def _broadcast_response_chunk(self, focus_manager, chunk: str) -> None:
        """Send a response chunk to the UI."""
        ws = getattr(focus_manager, "_stream_to_websocket", None)
        if callable(ws):
            try:
                ws({"type": "response_chunk", "chunk": chunk})
            except Exception:
                pass

        broadcast = getattr(focus_manager, "_broadcast_sync", None)
        if callable(broadcast):
            try:
                broadcast("response_chunk", {"chunk": chunk})
            except Exception:
                pass

    def _broadcast_response_end(self, focus_manager) -> None:
        """Signal the end of the current LLM response stream."""
        ws = getattr(focus_manager, "_stream_to_websocket", None)
        if callable(ws):
            try:
                ws({"type": "response_end"})
            except Exception:
                pass

        broadcast = getattr(focus_manager, "_broadcast_sync", None)
        if callable(broadcast):
            try:
                broadcast("response_end", {})
            except Exception:
                pass

    def _stream_llm_with_thought_broadcast(
        self,
        focus_manager,
        llm,
        prompt: str,
        operation: str = ""
    ) -> Iterator[str]:
        """
        Yield chunks from *llm* for *prompt*, broadcasting thoughts to UI.

        Delegates to focus_manager._stream_llm_with_thought_broadcast
        when available; otherwise yields the full response as one chunk.
        """
        broadcaster = getattr(focus_manager, "_stream_llm_with_thought_broadcast", None)
        if callable(broadcaster):
            yield from broadcaster(llm, prompt)
        else:
            response = self._stream_llm(focus_manager, llm, prompt, operation=operation)
            if response:
                yield response

    # ------------------------------------------------------------------
    # Focus-board helpers
    # ------------------------------------------------------------------

    def _add_to_board(
        self,
        focus_manager,
        category: str,
        item: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add *item* to *category* on the focus board."""
        adder = getattr(focus_manager, "add_to_focus_board", None)
        if callable(adder):
            adder(category, item, metadata=metadata)

    def _get_board_data(self, focus_manager) -> Dict[str, Any]:
        """Return the full board state dictionary."""
        board = getattr(focus_manager, "board", None)
        if board and hasattr(board, "get_all"):
            return board.get_all()
        return {}

    # ------------------------------------------------------------------
    # Tool execution  (streaming output, chunked)
    # ------------------------------------------------------------------

    def _execute_tool(
        self,
        focus_manager,
        tool_name: str,
        tool_input: Any,
        chunk_size: int = 500,
    ) -> Dict[str, Any]:
        """
        Find *tool_name* in the agent's tool list, run it, and stream
        its output back to the UI in chunks.

        Returns a result dict with keys: success, output, tool, input, error.
        """
        if not hasattr(focus_manager, "agent"):
            return {"success": False, "error": "No agent available"}

        tool = next(
            (t for t in focus_manager.agent.tools if t.name == tool_name),
            None,
        )
        if tool is None:
            self._stream_output(focus_manager, f"Tool not found: {tool_name}", "error")
            return {"success": False, "error": f"Tool '{tool_name}' not found"}

        try:
            self._stream_output(focus_manager, f"Executing: {tool_name}", "tool")

            output = (
                tool.run(**tool_input)
                if isinstance(tool_input, dict)
                else tool.run(tool_input)
            )

            if output:
                output_str = str(output)
                if len(output_str) > chunk_size:
                    for i in range(0, len(output_str), chunk_size):
                        self._stream_output(
                            focus_manager, output_str[i:i + chunk_size], "tool"
                        )
                else:
                    self._stream_output(focus_manager, output_str, "tool")

            self._stream_output(focus_manager, f"{tool_name} complete", "success")
            return {"success": True, "output": output, "tool": tool_name, "input": tool_input}

        except Exception as exc:
            self._stream_output(focus_manager, f"{tool_name} failed: {exc}", "error")
            return {"success": False, "error": str(exc), "tool": tool_name, "input": tool_input}

    # ------------------------------------------------------------------
    # Artifact saving
    # ------------------------------------------------------------------

    def _save_artifact(
        self,
        focus_manager,
        artifact_type: str,
        content: str,
        filename: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Save *content* as an artifact inside the project directory.

        Resolution order for the artifacts directory:
        1. sandbox.project_root / "artifacts"  (preferred - sandbox-safe)
        2. <focus_boards_dir>/../<project_id>/artifacts  (legacy fallback)

        Returns a dict with: success, filepath, filename, artifact_type, size, metadata.
        """
        sandbox = self._get_sandbox(focus_manager)
        if sandbox:
            if not filename:
                ts       = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                filename = f"{artifact_type}_{ts}.md"
            rel_path = f"artifacts/{filename}"
            ok = self._write_project_file(focus_manager, rel_path, content)
            if ok:
                full_path = str(sandbox.project_root / rel_path)
                self._stream_output(focus_manager, f"Artifact saved: {full_path}", "success")
                return {
                    "success":       True,
                    "filepath":      full_path,
                    "filename":      filename,
                    "artifact_type": artifact_type,
                    "size":          len(content),
                    "metadata":      metadata or {},
                }
            return {"success": False, "error": "Sandbox write failed"}

        project_id    = getattr(focus_manager, "project_id", "unknown_project")
        boards_dir    = getattr(focus_manager, "focus_boards_dir", ".")
        artifacts_dir = os.path.join(os.path.dirname(boards_dir), project_id, "artifacts")

        try:
            os.makedirs(artifacts_dir, exist_ok=True)
        except OSError as exc:
            self._stream_output(focus_manager, f"Failed to create artifacts dir: {exc}", "error")
            return {"success": False, "error": str(exc)}

        if not filename:
            ts       = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"{artifact_type}_{ts}.md"

        filepath = os.path.join(artifacts_dir, filename)
        try:
            with open(filepath, "w", encoding="utf-8") as fh:
                fh.write(content)
            self._stream_output(focus_manager, f"Artifact saved: {filepath}", "success")
            return {
                "success":       True,
                "filepath":      filepath,
                "filename":      filename,
                "artifact_type": artifact_type,
                "size":          len(content),
                "metadata":      metadata or {},
            }
        except Exception as exc:
            self._stream_output(focus_manager, f"Failed to save artifact: {exc}", "error")
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # Memory querying
    # ------------------------------------------------------------------

    def _query_memory(
        self,
        focus_manager,
        query: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Search the hybrid memory system for context related to *query*.

        Returns an empty list when memory is unavailable or the query fails.
        """
        memory = getattr(focus_manager, "hybrid_memory", None)
        if not memory:
            return []
        try:
            return memory.search_related_context(query, limit=limit) or []
        except Exception as exc:
            self._stream_output(focus_manager, f"Memory query error: {exc}", "warning")
            return []

    # ------------------------------------------------------------------
    # Telegram - fire-and-forget notification
    # ------------------------------------------------------------------

    def _notify_telegram(self, focus_manager, message: str) -> bool:
        """
        Send *message* via Telegram.

        Tries agent.telegram_notify(message) first (simple callable),
        then agent.telegram_notifier.send_message(message) (notifier object).

        Returns True if the message was dispatched, False otherwise.
        """
        agent = getattr(focus_manager, "agent", None)
        if agent is None:
            return False

        notify_fn = getattr(agent, "telegram_notify", None)
        if callable(notify_fn):
            try:
                return bool(notify_fn(message))
            except Exception as exc:
                self._stream_output(focus_manager, f"Telegram notify failed: {exc}", "warning")
                return False

        notifier = getattr(agent, "telegram_notifier", None)
        if notifier and hasattr(notifier, "send_message"):
            try:
                notifier.send_message(message)
                return True
            except Exception as exc:
                self._stream_output(focus_manager, f"Telegram notify failed: {exc}", "warning")
                return False

        return False

    # ------------------------------------------------------------------
    # Telegram - ask a question and wait for a reply
    # ------------------------------------------------------------------

    def _ask_telegram_question(
        self,
        focus_manager,
        question: str,
        timeout: int = 300,
        options: Optional[List[str]] = None,
    ) -> Optional[str]:
        """
        Send *question* to all Telegram owners and wait up to *timeout*
        seconds for a reply.

        *options* is an optional list of suggested responses shown to the user.

        Returns the reply string, or None on timeout / unavailability.
        """
        agent        = getattr(focus_manager, "agent", None)
        telegram_bot = getattr(agent, "telegram_bot", None) if agent else None

        if telegram_bot is None:
            self._stream_output(focus_manager, "Telegram bot not available for questions", "warning")
            return None

        formatted = f"<b>{self.name} - Question</b>\n\n{question}"
        if options:
            formatted += "\n\n<b>Suggested responses:</b>\n"
            for idx, opt in enumerate(options, 1):
                formatted += f"{idx}. {opt}\n"
        formatted += "\n<i>Reply to this message with your answer.</i>"

        async def _send_and_wait() -> Optional[str]:
            sent = await telegram_bot.send_to_owners(formatted)
            if not sent:
                return None

            wait_fn = getattr(telegram_bot, "wait_for_reply", None)
            if callable(wait_fn):
                try:
                    return await asyncio.wait_for(wait_fn(), timeout=timeout)
                except asyncio.TimeoutError:
                    self._stream_output(
                        focus_manager, "Telegram question timed out - no response", "warning"
                    )
                    return None

            deadline = time.time() + timeout
            check_fn = getattr(telegram_bot, "get_latest_reply", None)
            while time.time() < deadline:
                await asyncio.sleep(1)
                if callable(check_fn):
                    reply = check_fn()
                    if reply:
                        return reply
            return None

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            future = asyncio.run_coroutine_threadsafe(_send_and_wait(), loop)
            try:
                return future.result(timeout=timeout + 5)
            except Exception:
                return None
        else:
            return loop.run_until_complete(_send_and_wait())

    # ------------------------------------------------------------------
    # Sandbox helpers
    # ------------------------------------------------------------------

    def _get_sandbox(self, focus_manager) -> Optional[ProjectSandbox]:
        """
        Return the ProjectSandbox for this focus_manager, creating it
        lazily if needed.  Returns None only when no project context exists.
        """
        return get_project_sandbox(focus_manager)

    def _sync_sandbox(self, focus_manager) -> List[FileChange]:
        """
        Synchronise the sandbox workspace -> project_root.

        Returns the list of FileChange objects for this sync cycle and
        logs a summary to the UI.  Safe to call repeatedly - it is a no-op
        when nothing has changed.
        """
        changes = sync_agent_sandbox(focus_manager)
        if changes:
            created  = sum(1 for c in changes if c.operation == "created")
            modified = sum(1 for c in changes if c.operation == "modified")
            parts: List[str] = []
            if created:
                parts.append(f"{created} created")
            if modified:
                parts.append(f"{modified} modified")
            if parts:
                self._stream_output(
                    focus_manager,
                    f"Synced to project: {', '.join(parts)}",
                    "success",
                )
        return changes

    def _run_in_sandbox(
        self,
        focus_manager,
        command: str,
        timeout: Optional[int] = None,
    ) -> str:
        """
        Run a shell *command* inside the sandbox and return its output.

        Automatically syncs results to project_root after the command exits.
        Returns an empty string when no sandbox is available.
        """
        sandbox = self._get_sandbox(focus_manager)
        if sandbox is None:
            self._stream_output(
                focus_manager,
                "Cannot run command - no sandbox configured",
                "warning",
            )
            return ""
        return sandbox.run(command, timeout=timeout)

    def _write_project_file(
        self,
        focus_manager,
        relative_path: str,
        content: str,
    ) -> bool:
        """
        Write *content* to *relative_path* inside project_root.

        The path is validated through the sandbox before writing so a
        misbehaving LLM cannot escape the project directory.
        Returns True on success, False on failure.
        """
        sandbox = self._get_sandbox(focus_manager)
        if sandbox is None:
            self._stream_output(
                focus_manager,
                "Cannot write file - no sandbox configured",
                "warning",
            )
            return False
        try:
            validated = sandbox.validate_write_path(relative_path)
            target    = Path(validated)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return True
        except Exception as exc:
            self._stream_output(focus_manager, f"File write failed: {exc}", "warning")
            return False

    # ------------------------------------------------------------------
    # Misc helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_timestamp() -> str:
        return datetime.utcnow().isoformat() + "Z"

    def __repr__(self) -> str:
        return f"{self.icon} {self.name}: {self.description}"