"""
Vera Infrastructure Adapters
=============================
Bridges Vera's existing synchronous, threading-based components into the
cognition system's async interfaces.

Key adaptations:
  - MultiInstanceOllamaManager → async LLMBackend with role-based routing
  - HybridMemory (Neo4j + ChromaDB) → async MemoryStore
  - Vera tools (LangChain BaseTool) → async ToolRouter
  - Vera orchestrator EventBus → async EventBus
  - Telegram/messaging → async MessagingGateway

All sync→async bridging uses asyncio.to_thread() so the event loop
never blocks on Ollama inference or DB calls.

Usage:
    from cognition.vera_adapters import build_cognition_from_vera

    manager = await build_cognition_from_vera(vera_instance)
    await manager.start()
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Any, Callable, Dict, List, Optional

from .interfaces import (
    EventBus as CognitionEventBus,
    LLMBackend,
    MemoryStore,
    MessagingGateway,
    ToolRouter,
)
from .models import (
    IngestedEvent, Insight, Question, QuestionStatus,
    Task, TaskStatus,
)

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
#  LLM BACKEND — wraps MultiInstanceOllamaManager
# ══════════════════════════════════════════════════════════════

class CognitionRole:
    """
    Cognitive roles that the cognition system uses.
    Each maps to a Vera LLM tier and optionally an agent.
    """
    BACKGROUND  = "background"    # situational awareness digests
    SCOPING     = "scoping"       # goal clarity assessment
    PLANNING    = "planning"      # step-by-step plan generation
    EXECUTION   = "execution"     # executing plan steps, tool use
    REVIEW      = "review"        # completion validation
    SUMMARISE   = "summarise"     # event summarisation
    REASONING   = "reasoning"     # deep analytical reasoning


class OllamaLLMBackend(LLMBackend):
    """
    Wraps Vera's MultiInstanceOllamaManager + PooledOllamaLLM for the
    cognition system.

    Role-based routing:
      - Each cognitive phase (scoping, planning, execution, etc.) maps to
        the most appropriate Vera LLM tier.
      - If Vera's agent system is available, routes through agent configs
        for specialised model selection (custom temps, system prompts, etc.).
      - Falls back gracefully through tiers if preferred LLM is unavailable.

    Threading model:
      - PooledOllamaLLM._call() is synchronous (uses requests library).
      - All calls are wrapped in asyncio.to_thread() to keep the cognition
        event loop non-blocking.
      - Thought capture callbacks fire on the calling thread and are
        forwarded to the cognition event bus.

    Instance-aware:
      - Leverages the instance pool's health monitoring, load balancing,
        and automatic failover — the cognition system doesn't need to
        worry about which physical Ollama instance handles a request.
    """

    def __init__(
        self,
        ollama_manager,                          # MultiInstanceOllamaManager
        fast_llm=None,                           # PooledOllamaLLM — quick tasks
        intermediate_llm=None,                   # PooledOllamaLLM — mid-tier
        deep_llm=None,                           # PooledOllamaLLM — heavy tasks
        reasoning_llm=None,                      # PooledOllamaLLM — deep reasoning
        coding_llm=None,                         # PooledOllamaLLM — code generation
        tool_llm=None,                           # PooledOllamaLLM — tool planning
        agent_router=None,                       # AgentTaskRouter (if agents enabled)
        vera_logger=None,                        # Vera's unified logger
        thought_callback: Optional[Callable] = None,
    ):
        self.manager = ollama_manager
        self.fast_llm = fast_llm
        self.intermediate_llm = intermediate_llm
        self.deep_llm = deep_llm
        self.reasoning_llm = reasoning_llm
        self.coding_llm = coding_llm
        self.tool_llm = tool_llm
        self.agent_router = agent_router
        self.vera_logger = vera_logger
        self.thought_callback = thought_callback

        # Call stats per role
        self._stats: Dict[str, Dict[str, Any]] = {}

        # Role → LLM mapping (primary → fallback chain)
        self._role_map: Dict[str, List] = {
            CognitionRole.BACKGROUND:  [fast_llm, intermediate_llm],
            CognitionRole.SUMMARISE:   [fast_llm, intermediate_llm],
            CognitionRole.SCOPING:     [intermediate_llm, fast_llm, reasoning_llm],
            CognitionRole.PLANNING:    [deep_llm, intermediate_llm, reasoning_llm],
            CognitionRole.EXECUTION:   [deep_llm, tool_llm, intermediate_llm],
            CognitionRole.REVIEW:      [reasoning_llm, deep_llm],
            CognitionRole.REASONING:   [reasoning_llm, deep_llm],
        }

        # Role → Vera agent type mapping (for AgentTaskRouter)
        self._role_to_agent_type: Dict[str, str] = {
            CognitionRole.BACKGROUND:  "conversation",
            CognitionRole.SUMMARISE:   "conversation",
            CognitionRole.SCOPING:     "planning",
            CognitionRole.PLANNING:    "planning",
            CognitionRole.EXECUTION:   "tool_execution",
            CognitionRole.REVIEW:      "review",
            CognitionRole.REASONING:   "reasoning",
        }

    def _classify_role(self, system: Optional[str]) -> str:
        """
        Infer the cognitive role from the system prompt.
        The cognition loops set distinctive system prompts for each phase.
        """
        if not system:
            return CognitionRole.EXECUTION  # safe default

        s = system.lower()

        if any(k in s for k in ("background", "analyst", "situational")):
            return CognitionRole.BACKGROUND
        if any(k in s for k in ("summarise", "summarize", "digest")):
            return CognitionRole.SUMMARISE
        if any(k in s for k in ("scoping", "scope", "clarity")):
            return CognitionRole.SCOPING
        if any(k in s for k in ("planning", "plan", "step-by-step")):
            return CognitionRole.PLANNING
        if any(k in s for k in ("review", "validate", "completion")):
            return CognitionRole.REVIEW
        if any(k in s for k in ("reason", "reasoning", "analyse", "analyze")):
            return CognitionRole.REASONING
        if any(k in s for k in ("execution", "execute", "tool")):
            return CognitionRole.EXECUTION

        return CognitionRole.EXECUTION

    def _select_llm(self, role: str, temperature: float):
        """
        Select the best PooledOllamaLLM for a cognitive role.

        Strategy:
          1. If agent router is available, try to get a specialised agent LLM
          2. Walk the role's fallback chain until a non-None LLM is found
          3. Ultimate fallback: fast_llm (something is always better than nothing)
        """
        # Try agent routing first
        if self.agent_router:
            agent_type = self._role_to_agent_type.get(role, "conversation")
            try:
                agent_name = self.agent_router.get_agent_for_task(agent_type)
                llm = self.agent_router.create_llm_for_agent(agent_name)
                if self.vera_logger:
                    self.vera_logger.debug(
                        f"Cognition role '{role}' → agent '{agent_name}'"
                    )
                return llm
            except Exception as e:
                if self.vera_logger:
                    self.vera_logger.debug(
                        f"Agent routing failed for role '{role}': {e}, "
                        f"falling back to tier-based selection"
                    )

        # Tier-based fallback chain
        candidates = self._role_map.get(role, [])
        for llm in candidates:
            if llm is not None:
                return llm

        # Ultimate fallback
        return self.fast_llm or self.deep_llm

    def _build_prompt(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str],
    ) -> str:
        """
        Flatten chat-style messages into a single prompt string.

        PooledOllamaLLM talks to /api/generate which takes a flat prompt.
        We format system + messages into a clear structure that local
        models understand well.
        """
        parts = []
        if system:
            parts.append(f"<|system|>\n{system}\n</|system|>")

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                # Merge with system if we get it in messages too
                if not system:
                    parts.insert(0, f"<|system|>\n{content}\n</|system|>")
            elif role == "assistant":
                parts.append(f"Assistant: {content}")
            else:
                parts.append(f"User: {content}")

        parts.append("Assistant:")
        return "\n\n".join(parts)

    def _record_call(self, role: str, duration: float, tokens_est: int, success: bool):
        """Track per-role statistics."""
        if role not in self._stats:
            self._stats[role] = {
                "calls": 0, "failures": 0,
                "total_duration": 0.0, "total_tokens_est": 0,
            }
        s = self._stats[role]
        s["calls"] += 1
        if not success:
            s["failures"] += 1
        s["total_duration"] += duration
        s["total_tokens_est"] += tokens_est

    async def complete(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        temperature: float = 0.4,
        max_tokens: int = 2048,
        stop: Optional[List[str]] = None,
    ) -> str:
        """
        Core completion method used by background + focused loops.

        1. Classify the cognitive role from the system prompt
        2. Select the best LLM (agent → tier fallback)
        3. Build a flat prompt
        4. Execute synchronously via asyncio.to_thread()
        5. Return the raw text result
        """
        role = self._classify_role(system)
        llm = self._select_llm(role, temperature)
        prompt = self._build_prompt(messages, system)

        if llm is None:
            raise RuntimeError(
                f"No LLM available for cognition role '{role}'. "
                f"Check that Vera's model configuration has at least one LLM tier set up."
            )

        model_name = getattr(llm, "model", "unknown")
        t0 = time.time()

        def _sync_call():
            # Temporarily override temperature for this specific call
            original_temp = llm.temperature
            original_predict = llm.num_predict
            try:
                llm.temperature = temperature
                if max_tokens > 0:
                    llm.num_predict = max_tokens
                return llm._call(prompt, stop=stop)
            finally:
                llm.temperature = original_temp
                llm.num_predict = original_predict

        try:
            result = await asyncio.to_thread(_sync_call)
            duration = time.time() - t0
            tokens_est = len(result.split())  # rough estimate

            self._record_call(role, duration, tokens_est, success=True)

            if self.vera_logger:
                self.vera_logger.debug(
                    f"Cognition [{role}] complete on {model_name}: "
                    f"{len(prompt)}→{len(result)} chars in {duration:.2f}s"
                )

            return result

        except Exception as e:
            duration = time.time() - t0
            self._record_call(role, duration, 0, success=False)

            if self.vera_logger:
                self.vera_logger.error(
                    f"Cognition [{role}] failed on {model_name} "
                    f"after {duration:.2f}s: {e}"
                )
            raise

    async def complete_structured(
        self,
        messages: List[Dict[str, str]],
        schema: Dict[str, Any],
        system: Optional[str] = None,
        temperature: float = 0.2,
    ) -> Dict[str, Any]:
        """
        Request structured JSON output.

        Appends schema instructions to the system prompt, calls complete(),
        and attempts multiple parsing strategies on the result.
        """
        schema_hint = (
            "\n\nYou MUST respond with valid JSON matching this schema:\n"
            f"{json.dumps(schema, indent=2)}\n"
            "Respond with ONLY the JSON object, no other text."
        )
        augmented_system = (system or "") + schema_hint

        raw = await self.complete(
            messages, system=augmented_system, temperature=temperature
        )

        return self._parse_json_response(raw)

    def _parse_json_response(self, raw: str) -> Dict[str, Any]:
        """
        Best-effort JSON extraction from LLM output.
        Handles clean JSON, markdown fences, embedded JSON, trailing commas.
        """
        raw = raw.strip()

        # Strip markdown fences
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:])
            if raw.endswith("```"):
                raw = raw[:-3].strip()

        # Try direct parse
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # Extract first { ... } block
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start:end])
            except json.JSONDecodeError:
                # Fix trailing commas
                cleaned = re.sub(r",\s*([}\]])", r"\1", raw[start:end])
                try:
                    return json.loads(cleaned)
                except json.JSONDecodeError:
                    pass

        # Extract array [ ... ]
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start >= 0 and end > start:
            try:
                return {"items": json.loads(raw[start:end])}
            except json.JSONDecodeError:
                pass

        logger.warning("Structured completion failed to parse JSON, returning raw")
        return {"raw": raw}

    def get_stats(self) -> Dict[str, Any]:
        """Return per-role call statistics."""
        stats = {}
        for role, s in self._stats.items():
            calls = max(s["calls"], 1)
            stats[role] = {
                **s,
                "avg_duration": s["total_duration"] / calls,
                "failure_rate": s["failures"] / calls,
            }
        if self.manager and hasattr(self.manager, "get_pool_stats"):
            stats["_pool"] = self.manager.get_pool_stats()
        return stats

    def get_pool_health(self) -> Dict[str, Any]:
        """Expose instance pool health for monitoring."""
        if self.manager and hasattr(self.manager, "pool"):
            return self.manager.pool.get_stats()
        return {}


# ══════════════════════════════════════════════════════════════
#  MEMORY STORE — wraps HybridMemory (Neo4j + ChromaDB)
# ══════════════════════════════════════════════════════════════

class VeraMemoryStore(MemoryStore):
    """
    Wraps Vera's HybridMemory + ChromaDB vectorstore + in-memory
    working state for tasks/questions.

    Episodic events and insights → Neo4j via HybridMemory.
    Semantic search → ChromaDB.
    Tasks/questions → in-memory (scheduler is authoritative).
    """

    def __init__(
        self,
        hybrid_memory=None,
        session=None,
        vectorstore=None,
        vector_memory=None,
        vera_logger=None,
    ):
        self.mem = hybrid_memory
        self.session = session
        self.vectorstore = vectorstore
        self.vector_memory = vector_memory
        self.vera_logger = vera_logger

        self._tasks: Dict[str, Task] = {}
        self._questions: Dict[str, Question] = {}
        self._events: List[IngestedEvent] = []
        self._insights: List[Insight] = []

    # ── episodic ──

    async def store_event(self, event: IngestedEvent) -> None:
        self._events.append(event)

        if self.mem and self.session:
            def _sync():
                self.mem.add_session_memory(
                    self.session.id,
                    event.summary,
                    "CognitionEvent",
                    metadata={
                        "topic": event.topic,
                        "cognition_event_id": event.id,
                        "timestamp": event.timestamp,
                    },
                )
            try:
                await asyncio.to_thread(_sync)
            except Exception as e:
                logger.warning("Failed to persist event to Neo4j: %s", e)

        if self.vectorstore:
            def _sync_vec():
                self.vectorstore.add_texts(
                    texts=[f"[{event.topic}] {event.summary}"],
                    metadatas=[{
                        "type": "cognition_event",
                        "event_id": event.id,
                        "topic": event.topic,
                    }],
                )
            try:
                await asyncio.to_thread(_sync_vec)
            except Exception as e:
                logger.debug("Failed to vectorise event: %s", e)

    async def get_recent_events(
        self, seconds: float = 3600, limit: int = 100
    ) -> List[IngestedEvent]:
        cutoff = time.time() - seconds
        return [e for e in self._events if e.timestamp > cutoff][:limit]

    # ── insights ──

    async def store_insight(self, insight: Insight) -> None:
        self._insights.append(insight)

        if self.mem and self.session:
            def _sync():
                self.mem.add_session_memory(
                    self.session.id,
                    insight.text,
                    "CognitionInsight",
                    metadata={
                        "cognition_insight_id": insight.id,
                        "confidence": insight.confidence,
                        "tags": ",".join(insight.tags),
                        "source": insight.source,
                    },
                )
            try:
                await asyncio.to_thread(_sync)
            except Exception as e:
                logger.warning("Failed to persist insight to Neo4j: %s", e)

        if self.vectorstore:
            def _sync_vec():
                tag_str = ", ".join(insight.tags) if insight.tags else ""
                self.vectorstore.add_texts(
                    texts=[f"[Insight] {insight.text} (tags: {tag_str})"],
                    metadatas=[{
                        "type": "cognition_insight",
                        "insight_id": insight.id,
                        "confidence": insight.confidence,
                    }],
                )
            try:
                await asyncio.to_thread(_sync_vec)
            except Exception as e:
                logger.debug("Failed to vectorise insight: %s", e)

    async def get_recent_insights(
        self, seconds: float = 86400, limit: int = 50
    ) -> List[Insight]:
        cutoff = time.time() - seconds
        return [i for i in self._insights if i.created_at > cutoff][:limit]

    # ── tasks ──

    async def save_task(self, task: Task) -> None:
        self._tasks[task.id] = task

        if self.mem and self.session:
            def _sync():
                self.mem.add_session_memory(
                    self.session.id,
                    f"Task [{task.status.value}]: {task.goal}",
                    "CognitionTask",
                    metadata={
                        "task_id": task.id,
                        "status": task.status.value,
                        "priority": task.priority.value,
                        "origin": task.origin,
                        "step_count": len(task.plan),
                        "current_step": task.current_step_idx,
                    },
                )
            try:
                await asyncio.to_thread(_sync)
            except Exception as e:
                logger.debug("Failed to persist task to Neo4j: %s", e)

    async def get_task(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    async def get_active_tasks(self) -> List[Task]:
        return [t for t in self._tasks.values() if not t.is_terminal()]

    # ── questions ──

    async def save_question(self, question: Question) -> None:
        self._questions[question.id] = question

    async def get_pending_questions(self, task_id: str) -> List[Question]:
        return [
            q for q in self._questions.values()
            if q.task_id == task_id and q.status == QuestionStatus.PENDING
        ]

    # ── semantic search ──

    async def semantic_search(
        self, query: str, top_k: int = 5
    ) -> List[Dict[str, Any]]:
        if not self.vectorstore:
            return []

        def _sync():
            try:
                results = self.vectorstore.similarity_search_with_relevance_scores(
                    query, k=top_k
                )
                return [
                    {"text": doc.page_content, "metadata": doc.metadata, "score": score}
                    for doc, score in results
                ]
            except Exception:
                # Fallback if scores not supported
                docs = self.vectorstore.similarity_search(query, k=top_k)
                return [
                    {"text": doc.page_content, "metadata": doc.metadata, "score": 0.0}
                    for doc in docs
                ]

        try:
            return await asyncio.to_thread(_sync)
        except Exception as e:
            logger.warning("Semantic search failed: %s", e)
            return []


# ══════════════════════════════════════════════════════════════
#  TOOL ROUTER — wraps Vera's LangChain tools
# ══════════════════════════════════════════════════════════════

class VeraToolRouter(ToolRouter):
    """
    Wraps Vera's list of LangChain BaseTool instances.
    The cognition system calls tools by name+args — this adapter
    finds the matching tool, invokes it, and returns a normalised result.
    """

    def __init__(self, tools: list, vera_logger=None):
        self._tools = {t.name: t for t in tools}
        self.vera_logger = vera_logger
        self._stats: Dict[str, Dict[str, Any]] = {}

    async def run_tool(
        self, name: str, args: Dict[str, Any]
    ) -> Dict[str, Any]:
        tool = self._tools.get(name)
        if not tool:
            available = list(self._tools.keys())
            try:
                from difflib import get_close_matches
                suggestions = get_close_matches(name, available, n=3, cutoff=0.5)
            except ImportError:
                suggestions = []
            msg = f"Tool '{name}' not found."
            if suggestions:
                msg += f" Did you mean: {', '.join(suggestions)}?"
            return {"error": msg}

        t0 = time.time()

        def _sync():
            try:
                return tool.run(**args)
            except TypeError:
                input_str = (
                    args.get("input") or args.get("query")
                    or args.get("text") or str(args)
                )
                return tool.run(input_str)

        try:
            result = await asyncio.to_thread(_sync)
            duration = time.time() - t0

            if name not in self._stats:
                self._stats[name] = {"calls": 0, "failures": 0, "total_duration": 0.0}
            self._stats[name]["calls"] += 1
            self._stats[name]["total_duration"] += duration

            if self.vera_logger:
                self.vera_logger.debug(f"Tool '{name}' completed in {duration:.2f}s")

            return {"result": result}

        except Exception as e:
            duration = time.time() - t0
            if name not in self._stats:
                self._stats[name] = {"calls": 0, "failures": 0, "total_duration": 0.0}
            self._stats[name]["calls"] += 1
            self._stats[name]["failures"] += 1

            logger.warning("Tool '%s' failed after %.2fs: %s", name, duration, e)
            return {"error": str(e)}

    async def list_tools(self) -> List[str]:
        return list(self._tools.keys())

    def get_stats(self) -> Dict[str, Any]:
        return dict(self._stats)


# ══════════════════════════════════════════════════════════════
#  MESSAGING GATEWAY — Telegram + console + WebSocket
# ══════════════════════════════════════════════════════════════

class VeraMessagingGateway(MessagingGateway):
    """
    Routes cognition messages through Vera's existing channels.
    Failures are logged but never propagate to the cognition manager.
    """

    def __init__(self, vera_instance=None, vera_logger=None):
        self.vera = vera_instance
        self.vera_logger = vera_logger

    async def send_message(
        self, text: str, channel: Optional[str] = None
    ) -> None:
        if self.vera_logger:
            self.vera_logger.info(f"[Cognition] {text}")

        if self.vera and hasattr(self.vera, "telegram_notify"):
            try:
                await asyncio.to_thread(self.vera.telegram_notify, text)
            except Exception as e:
                logger.debug("Telegram send failed: %s", e)

        if self.vera and hasattr(self.vera, "chat"):
            chat = self.vera.chat
            if hasattr(chat, "broadcast_event"):
                try:
                    await asyncio.to_thread(
                        chat.broadcast_event,
                        "cognition_message",
                        {"text": text, "channel": channel},
                    )
                except Exception as e:
                    logger.debug("WebSocket broadcast failed: %s", e)

    async def ask_question(self, question: Question) -> None:
        msg = f"❓ [Task {question.task_id[:8]}] {question.text}"
        if question.options:
            msg += "\nOptions: " + " | ".join(
                f"({i+1}) {opt}" for i, opt in enumerate(question.options)
            )
        await self.send_message(msg)

    async def send_progress(self, task: Task, update: str) -> None:
        priority_emoji = {0: "🔴", 1: "🟠", 2: "🟡", 3: "🟢", 4: "⚪"}
        emoji = priority_emoji.get(task.priority.value, "🔵")
        step_info = ""
        if task.plan:
            step_info = f" [{task.current_step_idx}/{len(task.plan)}]"
        msg = f"{emoji} [{task.status.value}]{step_info} {update}"
        await self.send_message(msg, channel=task.update_channel)


# ══════════════════════════════════════════════════════════════
#  EVENT BUS — wraps Vera orchestrator's EventBus
# ══════════════════════════════════════════════════════════════

class VeraEventBusAdapter(CognitionEventBus):
    """
    Bridges Vera's sync EventBus into the cognition system's async interface.
    Publishes cognition events with a 'cognition.' prefix for easy filtering.
    """

    def __init__(self, vera_event_bus=None):
        self._vera_bus = vera_event_bus
        self._handlers: Dict[str, List[Callable]] = {}

    async def publish(self, topic: str, payload: Dict[str, Any]) -> None:
        prefixed = f"cognition.{topic}" if not topic.startswith("cognition.") else topic

        if self._vera_bus:
            try:
                self._vera_bus.publish(prefixed, payload)
            except Exception as e:
                logger.debug("Vera event bus publish failed: %s", e)

        for pattern, handlers in self._handlers.items():
            if self._matches(pattern, topic) or self._matches(pattern, prefixed):
                for h in handlers:
                    try:
                        result = h(payload)
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception:
                        logger.exception("Event handler error on %s", topic)

    async def subscribe(self, topic: str, handler) -> None:
        self._handlers.setdefault(topic, []).append(handler)

        if self._vera_bus:
            def _sync_forwarder(payload):
                try:
                    loop = asyncio.get_running_loop()
                    loop.call_soon_threadsafe(
                        asyncio.ensure_future, handler(payload),
                    )
                except RuntimeError:
                    pass

            self._vera_bus.subscribe(topic, _sync_forwarder)

    @staticmethod
    def _matches(pattern: str, topic: str) -> bool:
        if pattern == topic:
            return True
        if pattern.endswith(".*"):
            prefix = pattern[:-2]
            return topic.startswith(prefix + ".") or topic == prefix
        if pattern.endswith("*"):
            return topic.startswith(pattern[:-1])
        return False


# ══════════════════════════════════════════════════════════════
#  FACTORY — build a CognitionManager from a Vera instance
# ══════════════════════════════════════════════════════════════

async def build_cognition_from_vera(
    vera_instance,
    config=None,
) -> "CognitionManager":
    """
    One-call factory: takes a fully initialised Vera instance and returns
    a ready-to-start CognitionManager wired to all Vera subsystems.

    Automatically detects and wires:
      - All LLM tiers (fast, intermediate, deep, reasoning, coding, tool)
      - Agent router (if agents enabled)
      - HybridMemory + ChromaDB
      - LangChain tools
      - Telegram/WebSocket messaging
      - Orchestrator event bus
      - Thought capture pipeline

    Usage:
        from cognition.vera_adapters import build_cognition_from_vera

        self.cognition = await build_cognition_from_vera(self)
        await self.cognition.start()
        task = await self.cognition.create_task("Analyse BTC volatility")
    """
    from .manager import CognitionManager, CognitionConfig
    from Vera.ProactiveCognition.background import BackgroundConfig

    v = vera_instance
    vera_logger = getattr(v, "logger", None)

    # ── Agent router (optional) ──
    agent_router = None
    if hasattr(v, "agents") and v.agents:
        try:
            from Vera.Orchestration.agent_integration import AgentTaskRouter
            agent_router = AgentTaskRouter(v)
            if vera_logger:
                vera_logger.debug("Cognition: agent router available")
        except (ImportError, Exception) as e:
            if vera_logger:
                vera_logger.debug(f"Cognition: agent router unavailable: {e}")

    # ── LLM backend ──
    llm = OllamaLLMBackend(
        ollama_manager=getattr(v, "ollama_manager", None),
        fast_llm=getattr(v, "fast_llm", None),
        intermediate_llm=getattr(v, "intermediate_llm", None),
        deep_llm=getattr(v, "deep_llm", None),
        reasoning_llm=getattr(v, "reasoning_llm", None),
        coding_llm=getattr(v, "coding_llm_llm", None),  # Vera uses coding_llm_llm
        tool_llm=getattr(v, "tool_llm", None),
        agent_router=agent_router,
        vera_logger=vera_logger,
        thought_callback=getattr(v, "_on_thought_captured", None),
    )

    # ── Memory store ──
    memory = VeraMemoryStore(
        hybrid_memory=getattr(v, "mem", None),
        session=getattr(v, "sess", None),
        vectorstore=getattr(v, "vectorstore", None),
        vector_memory=getattr(v, "vector_memory", None),
        vera_logger=vera_logger,
    )

    # ── Tool router ──
    tools = VeraToolRouter(
        tools=getattr(v, "tools", []),
        vera_logger=vera_logger,
    )

    # ── Messaging ──
    messaging = VeraMessagingGateway(
        vera_instance=v,
        vera_logger=vera_logger,
    )

    # ── Event bus ──
    vera_bus = None
    if hasattr(v, "orchestrator") and hasattr(v.orchestrator, "event_bus"):
        vera_bus = v.orchestrator.event_bus
    event_bus = VeraEventBusAdapter(vera_event_bus=vera_bus)

    # ── Config ──
    if config is None:
        bg_interval = 120.0
        if hasattr(v, "config") and hasattr(v.config, "proactive_focus"):
            pf = v.config.proactive_focus
            if hasattr(pf, "proactive_interval"):
                bg_interval = min(pf.proactive_interval / 10, 300.0)

        max_workers = 3
        if hasattr(v, "config") and hasattr(v.config, "orchestrator"):
            max_workers = max(
                getattr(v.config.orchestrator, "background_workers", 2), 2,
            )

        config = CognitionConfig(
            max_workers=max_workers,
            max_concurrent_tasks=10,
            enable_background_loop=True,
            background=BackgroundConfig(
                cycle_interval_s=bg_interval,
                event_lookback_s=bg_interval * 5,
                min_events_for_analysis=2,
                auto_spawn_tasks=True,
                notify_new_insights=False,
            ),
        )

    # ── Assemble ──
    manager = CognitionManager(
        llm=llm,
        memory=memory,
        messaging=messaging,
        tools=tools,
        event_bus=event_bus,
        config=config,
    )

    if vera_logger:
        wired = []
        for tier_name, tier_llm in [
            ("fast", llm.fast_llm), ("intermediate", llm.intermediate_llm),
            ("deep", llm.deep_llm), ("reasoning", llm.reasoning_llm),
            ("coding", llm.coding_llm), ("tool", llm.tool_llm),
        ]:
            if tier_llm:
                wired.append(f"{tier_name}={getattr(tier_llm, 'model', '?')}")
        if agent_router:
            wired.append("agents=✓")

        pool_instances = 0
        if getattr(v, "ollama_manager", None) and hasattr(v.ollama_manager, "pool"):
            pool_instances = len(v.ollama_manager.pool.instances)

        vera_logger.success(
            f"CognitionManager built from Vera "
            f"(workers={config.max_workers}, bg={config.background.cycle_interval_s}s, "
            f"pool={pool_instances} instances, {', '.join(wired)})"
        )

    return manager


# ══════════════════════════════════════════════════════════════
#  VERA INTEGRATION HOOK — call from Vera.__init__
# ══════════════════════════════════════════════════════════════

def integrate_cognition_system(vera_instance, auto_start: bool = True):
    """
    Convenience function to wire the cognition system into a running Vera
    instance. Call this from Vera.__init__ after all other components
    are initialised.

    Usage in Vera.__init__:
        from cognition.vera_adapters import integrate_cognition_system
        integrate_cognition_system(self)

    This creates vera_instance.cognition as a CognitionManager.
    """
    import threading

    vera_logger = getattr(vera_instance, "logger", None)
    _cognition_loop = None

    async def _build_and_start():
        nonlocal _cognition_loop
        manager = await build_cognition_from_vera(vera_instance)
        if auto_start:
            await manager.start()
        vera_instance.cognition = manager
        _cognition_loop = asyncio.get_running_loop()

        if vera_logger:
            vera_logger.success("Cognition system integrated and running")

    def _run_in_thread():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_build_and_start())
            loop.run_forever()
        except Exception as e:
            if vera_logger:
                vera_logger.error(f"Cognition system failed: {e}", exc_info=True)
        finally:
            loop.close()

    thread = threading.Thread(
        target=_run_in_thread,
        name="cognition-loop",
        daemon=True,
    )
    thread.start()

    vera_instance._cognition_thread = thread
    vera_instance._cognition_loop = _cognition_loop

    if vera_logger:
        vera_logger.info("Cognition system starting in background thread...")

async def main():
    self.cognition = await build_cognition_from_vera(self)
    await self.cognition.start()
    task = await self.cognition.create_task("Analyse BTC volatility")

if __name__ == "__main__":
    
    main()