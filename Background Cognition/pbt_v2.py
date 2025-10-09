#!/usr/bin/env python3
""" 
Proactive Focus Manager with advanced control and monitoring
"""
import json
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Callable
from enum import Enum
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import uuid


class FocusState(Enum):
    INACTIVE = "inactive"
    STARTING = "starting"
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPING = "stopping"


class ActionPriority(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class ActionStatus(Enum):
    PENDING = "pending"
    EVALUATING = "evaluating"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ProactiveAction:
    id: str
    thought: str
    priority: ActionPriority
    status: ActionStatus
    created_at: datetime
    category: str
    context: Dict[str, Any]
    evaluation_score: Optional[float] = None
    execution_result: Optional[str] = None
    execution_time: Optional[float] = None
    error: Optional[str] = None
    approved_by: Optional[str] = None  # "auto" or user ID
    
    def to_dict(self):
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        data['priority'] = self.priority.value
        data['status'] = self.status.value
        return data


@dataclass
class FocusMetrics:
    total_thoughts: int = 0
    approved_actions: int = 0
    rejected_actions: int = 0
    completed_actions: int = 0
    failed_actions: int = 0
    avg_evaluation_score: float = 0.0
    avg_execution_time: float = 0.0
    last_activity: Optional[datetime] = None
    
    def to_dict(self):
        data = asdict(self)
        data['last_activity'] = self.last_activity.isoformat() if self.last_activity else None
        return data


class ContextProvider:
    """Base class for context providers"""
    def __init__(self, name: str):
        self.name = name
        
    def collect(self) -> Dict[str, Any]:
        raise NotImplementedError


class ConversationProvider(ContextProvider):
    def __init__(self, conversation_getter: Callable[[], str]):
        super().__init__("conversation")
        self.conversation_getter = conversation_getter
        
    def collect(self) -> Dict[str, Any]:
        return {"latest_conversation": self.conversation_getter()}


class FocusBoardProvider(ContextProvider):
    def __init__(self, focus_board_getter: Callable[[], Dict]):
        super().__init__("focus_board")
        self.focus_board_getter = focus_board_getter
        
    def collect(self) -> Dict[str, Any]:
        return {"focus_board": self.focus_board_getter()}


class SystemStatsProvider(ContextProvider):
    def __init__(self, pool_getter: Callable):
        super().__init__("system_stats")
        self.pool_getter = pool_getter
        
    def collect(self) -> Dict[str, Any]:
        try:
            pool = self.pool_getter()
            if pool:
                return {
                    "queue_size": pool._q.qsize(),
                    "active_workers": len([t for t in pool._threads if t.is_alive()]),
                    "worker_count": pool.worker_count
                }
        except Exception:
            pass
        return {"system_stats": "unavailable"}


class EnhancedProactiveFocusManager:
    """Enhanced autonomous background cognition with granular control"""
    
    def __init__(
        self,
        agent,
        pool,
        proactive_interval: float = 300.0,  # 5 minutes default
        system_label_llm: str = "llm",
        system_label_exec: str = "exec",
        proactive_callback: Optional[Callable[[str], None]] = None,
        auto_approve: bool = False,
        max_concurrent_actions: int = 3,
    ) -> None:
        self.agent = agent
        self.pool = pool
        self.proactive_interval = proactive_interval
        self.system_label_llm = system_label_llm
        self.system_label_exec = system_label_exec
        self.proactive_callback = proactive_callback
        self.auto_approve = auto_approve
        self.max_concurrent_actions = max_concurrent_actions
        
        # Core state
        self.focus: Optional[str] = None
        self.focus_description: str = ""
        self.focus_goals: List[str] = []
        self.state = FocusState.INACTIVE
        self.focus_board: Dict[str, List[str]] = {
            "progress": [],
            "next_steps": [],
            "issues": [],
            "ideas": [],
            "actions": [],
            "insights": [],
            "blockers": [],
            "completed": []
        }
        
        # Enhanced tracking
        self.action_history: deque[ProactiveAction] = deque(maxlen=1000)
        self.pending_actions: Dict[str, ProactiveAction] = {}
        self.active_executions: Dict[str, ProactiveAction] = {}
        self.metrics = FocusMetrics()
        
        # Configuration
        self.config = {
            "thought_generation": {
                "creativity_weight": 0.7,
                "feasibility_weight": 0.8,
                "relevance_weight": 0.9,
                "min_evaluation_score": 0.6
            },
            "execution": {
                "timeout": 300,  # 5 minutes
                "retry_attempts": 2,
                "safety_checks": True
            },
            "focus_board": {
                "max_items_per_category": 50,
                "auto_archive_after_days": 7
            }
        }
        
        # Context and providers
        self.latest_conversation: str = ""
        self.context_providers: List[ContextProvider] = [
            ConversationProvider(lambda: self.latest_conversation),
            FocusBoardProvider(lambda: self.focus_board.copy()),
            SystemStatsProvider(lambda: self.pool)
        ]
        
        # Threading and lifecycle
        self._running = False
        self._ticker_task_id: Optional[str] = None
        self._lock = threading.RLock()
        
        # Event callbacks
        self.event_callbacks: Dict[str, List[Callable]] = defaultdict(list)
        
        # Set conservative defaults
        self.pool.set_concurrency_limit(self.system_label_llm, 2)
        self.pool.set_concurrency_limit(self.system_label_exec, 1)

    # Configuration Management
    def update_config(self, section: str, key: str, value: Any) -> None:
        """Update configuration value"""
        with self._lock:
            if section in self.config:
                self.config[section][key] = value
                self._emit_event("config_updated", {"section": section, "key": key, "value": value})

    def get_config(self) -> Dict[str, Any]:
        """Get current configuration"""
        with self._lock:
            return self.config.copy()

    # Event System
    def on(self, event: str, callback: Callable) -> None:
        """Register event callback"""
        self.event_callbacks[event].append(callback)

    def _emit_event(self, event: str, data: Any = None) -> None:
        """Emit event to callbacks"""
        for callback in self.event_callbacks[event]:
            try:
                callback(data)
            except Exception as e:
                self.add_to_focus_board("issues", f"Event callback error: {e}")

    # Focus Management
    def set_focus(self, focus: str, description: str = "", goals: List[str] = None) -> None:
        """Set project focus with enhanced metadata"""
        with self._lock:
            old_focus = self.focus
            self.focus = focus
            self.focus_description = description
            self.focus_goals = goals or []
            
            # Clear old focus board if focus changed significantly
            if old_focus and old_focus != focus:
                self._archive_focus_board(old_focus)
                
            self.add_to_focus_board("actions", f"Focus updated: {focus}")
            self._emit_event("focus_changed", {
                "old_focus": old_focus,
                "new_focus": focus,
                "description": description,
                "goals": self.focus_goals
            })
            
            try:
                if hasattr(self.agent, 'mem') and hasattr(self.agent, 'sess'):
                    self.agent.mem.add_session_memory(
                        self.agent.sess.id, 
                        f"[FocusManager] Focus set to: {focus} - {description}", 
                        "Thought", 
                        {"topic": "focus", "goals": self.focus_goals}
                    )
            except Exception:
                pass

    def add_focus_goal(self, goal: str) -> None:
        """Add a goal to the current focus"""
        with self._lock:
            if goal not in self.focus_goals:
                self.focus_goals.append(goal)
                self.add_to_focus_board("next_steps", f"Goal added: {goal}")
                self._emit_event("goal_added", {"goal": goal})

    def remove_focus_goal(self, goal: str) -> None:
        """Remove a goal from the current focus"""
        with self._lock:
            if goal in self.focus_goals:
                self.focus_goals.remove(goal)
                self.add_to_focus_board("completed", f"Goal completed: {goal}")
                self._emit_event("goal_removed", {"goal": goal})

    def clear_focus(self) -> None:
        """Clear current focus and stop manager"""
        with self._lock:
            old_focus = self.focus
            self.focus = None
            self.focus_description = ""
            self.focus_goals = []
            self.stop()
            self._emit_event("focus_cleared", {"old_focus": old_focus})

    # Focus Board Management
    def add_to_focus_board(self, category: str, note: str, metadata: Dict[str, Any] = None) -> str:
        """Add note to focus board with metadata"""
        with self._lock:
            if category not in self.focus_board:
                self.focus_board[category] = []
                
            timestamp = datetime.now().strftime("%H:%M:%S")
            full_note = f"[{timestamp}] {note}"
            
            if metadata:
                full_note += f" {json.dumps(metadata, ensure_ascii=False)}"
                
            self.focus_board[category].append(full_note)
            
            # Limit items per category
            max_items = self.config["focus_board"]["max_items_per_category"]
            if len(self.focus_board[category]) > max_items:
                self.focus_board[category] = self.focus_board[category][-max_items:]
                
            self._emit_event("focus_board_updated", {
                "category": category,
                "note": note,
                "metadata": metadata
            })
            
            return full_note

    def clear_focus_board_category(self, category: str) -> None:
        """Clear a specific category in the focus board"""
        with self._lock:
            if category in self.focus_board:
                cleared_count = len(self.focus_board[category])
                self.focus_board[category] = []
                self._emit_event("category_cleared", {"category": category, "count": cleared_count})

    def _archive_focus_board(self, focus: str) -> None:
        """Archive current focus board"""
        # Implementation would save to persistent storage
        pass

    # Context Providers
    def add_provider(self, provider: ContextProvider) -> None:
        """Add context provider"""
        with self._lock:
            self.context_providers.append(provider)
            self._emit_event("provider_added", {"name": provider.name})

    def remove_provider(self, provider_name: str) -> bool:
        """Remove context provider by name"""
        with self._lock:
            for i, provider in enumerate(self.context_providers):
                if provider.name == provider_name:
                    del self.context_providers[i]
                    self._emit_event("provider_removed", {"name": provider_name})
                    return True
            return False

    def update_latest_conversation(self, text: str) -> None:
        """Update conversation context"""
        self.latest_conversation = text
        self._emit_event("conversation_updated", {"text": text[:200]})

    # Lifecycle Management
    def start(self) -> None:
        """Start the proactive focus manager"""
        with self._lock:
            if self._running or not self.focus:
                return
                
            self.state = FocusState.STARTING
            self._running = True
            self._schedule_tick(0.0)
            self.state = FocusState.ACTIVE
            
            self.add_to_focus_board("actions", "Proactive manager started")
            self._emit_event("manager_started", {"focus": self.focus})

    def stop(self) -> None:
        """Stop the proactive focus manager"""
        with self._lock:
            if not self._running:
                return
                
            self.state = FocusState.STOPPING
            self._running = False
            
            # Cancel pending ticker
            if self._ticker_task_id:
                # Note: In real implementation, you'd cancel the scheduled task
                self._ticker_task_id = None
                
            self.state = FocusState.INACTIVE
            self.add_to_focus_board("actions", "Proactive manager stopped")
            self._emit_event("manager_stopped", {})

    def pause(self) -> None:
        """Pause the manager temporarily"""
        with self._lock:
            if self.state == FocusState.ACTIVE:
                self.state = FocusState.PAUSED
                self.add_to_focus_board("actions", "Manager paused")
                self._emit_event("manager_paused", {})

    def resume(self) -> None:
        """Resume from paused state"""
        with self._lock:
            if self.state == FocusState.PAUSED:
                self.state = FocusState.ACTIVE
                self._schedule_tick(0.0)
                self.add_to_focus_board("actions", "Manager resumed")
                self._emit_event("manager_resumed", {})

    def set_interval(self, interval: float) -> None:
        """Update proactive interval"""
        with self._lock:
            self.proactive_interval = max(30.0, interval)  # Minimum 30 seconds
            self._emit_event("interval_changed", {"interval": self.proactive_interval})

    # Action Management
    def get_pending_actions(self) -> List[ProactiveAction]:
        """Get all pending actions awaiting approval"""
        with self._lock:
            return list(self.pending_actions.values())

    def approve_action(self, action_id: str, approved_by: str = "user") -> bool:
        """Approve a pending action for execution"""
        with self._lock:
            if action_id in self.pending_actions:
                action = self.pending_actions[action_id]
                action.status = ActionStatus.APPROVED
                action.approved_by = approved_by
                
                # Move to execution queue
                del self.pending_actions[action_id]
                self._execute_action(action)
                
                self.metrics.approved_actions += 1
                self._emit_event("action_approved", {"action_id": action_id, "approved_by": approved_by})
                return True
            return False

    def reject_action(self, action_id: str, reason: str = "") -> bool:
        """Reject a pending action"""
        with self._lock:
            if action_id in self.pending_actions:
                action = self.pending_actions[action_id]
                action.status = ActionStatus.REJECTED
                action.error = reason
                
                # Move to history
                del self.pending_actions[action_id]
                self.action_history.append(action)
                
                self.metrics.rejected_actions += 1
                self.add_to_focus_board("issues", f"Action rejected: {action.thought[:100]} - {reason}")
                self._emit_event("action_rejected", {"action_id": action_id, "reason": reason})
                return True
            return False

    def get_action_history(self, limit: int = 50) -> List[ProactiveAction]:
        """Get recent action history"""
        with self._lock:
            return list(self.action_history)[-limit:]

    def get_active_executions(self) -> List[ProactiveAction]:
        """Get currently executing actions"""
        with self._lock:
            return list(self.active_executions.values())

    # Core Processing Logic
    def _schedule_tick(self, delay: float) -> None:
        """Schedule next proactive tick"""
        if not self._running or self.state != FocusState.ACTIVE:
            return
            
        self._ticker_task_id = self.pool.submit(
            self._tick,
            priority=Priority.LOW,
            delay=delay,
            name="proactive.tick",
            labels=(self.system_label_llm,),
        )

    def _collect_context(self) -> Dict[str, Any]:
        """Collect context from all providers"""
        ctx = {
            "focus": self.focus,
            "focus_description": self.focus_description,
            "focus_goals": self.focus_goals,
            "timestamp": datetime.now().isoformat(),
            "state": self.state.value,
            "metrics": self.metrics.to_dict(),
            "pending_count": len(self.pending_actions),
            "executing_count": len(self.active_executions)
        }
        
        for provider in self.context_providers:
            try:
                provider_ctx = provider.collect()
                ctx.update(provider_ctx)
            except Exception as e:
                self.add_to_focus_board("issues", f"Context provider {provider.name} failed: {e}")
                
        return ctx

    def _tick(self) -> None:
        """Main proactive processing tick"""
        try:
            if self.state != FocusState.ACTIVE:
                return
                
            ctx = self._collect_context()
            
            # Generate proactive thought
            self.pool.submit(
                self._generate_and_evaluate,
                ctx,
                priority=Priority.NORMAL,
                name="proactive.generate",
                labels=(self.system_label_llm,)
            )
            
            # Schedule next tick
            self._schedule_tick(self.proactive_interval)
            
        except Exception as e:
            self.add_to_focus_board("issues", f"Tick error: {e}")

    def _generate_and_evaluate(self, ctx: Dict[str, Any]) -> None:
        """Generate and evaluate proactive thought"""
        try:
            if not self.focus:
                return
                
            thought = self._generate_proactive_thought(ctx)
            if not thought:
                return
                
            # Create action object
            action = ProactiveAction(
                id=str(uuid.uuid4()),
                thought=thought,
                priority=self._determine_priority(thought, ctx),
                status=ActionStatus.EVALUATING,
                created_at=datetime.now(),
                category=self._categorize_action(thought),
                context={"focus": self.focus, "goals": self.focus_goals}
            )
            
            # Evaluate actionability
            is_actionable, score = self._evaluate_action(action, ctx)
            action.evaluation_score = score
            
            if is_actionable and score >= self.config["thought_generation"]["min_evaluation_score"]:
                action.status = ActionStatus.PENDING if not self.auto_approve else ActionStatus.APPROVED
                
                if self.auto_approve:
                    action.approved_by = "auto"
                    self._execute_action(action)
                else:
                    self.pending_actions[action.id] = action
                    self.add_to_focus_board("next_steps", f"Action pending approval: {thought[:100]}")
                    self._emit_event("action_pending", {"action": action.to_dict()})
            else:
                action.status = ActionStatus.REJECTED
                action.error = f"Low evaluation score: {score:.2f}"
                self.action_history.append(action)
                self.add_to_focus_board("issues", f"Action rejected (score {score:.2f}): {thought[:100]}")
                
            self.metrics.total_thoughts += 1
            self.metrics.last_activity = datetime.now()
            
            # Callback for generated thought
            if self.proactive_callback:
                try:
                    self.proactive_callback(thought)
                except Exception:
                    pass
                    
        except Exception as e:
            self.add_to_focus_board("issues", f"Generation error: {e}")

    def _generate_proactive_thought(self, ctx: Dict[str, Any]) -> Optional[str]:
        """Generate a proactive thought using LLM"""
        config = self.config["thought_generation"]
        
        prompt = f"""You are an autonomous background co-pilot for a project.

PROJECT CONTEXT:
- Focus: {ctx.get('focus', 'Not set')}
- Description: {ctx.get('focus_description', 'None')}
- Goals: {', '.join(ctx.get('focus_goals', []))}

CURRENT STATE:
- Recent conversation: {ctx.get('latest_conversation', 'None')[-500:]}
- Focus board status: {json.dumps(ctx.get('focus_board', {}), ensure_ascii=False)[-1000:]}
- System stats: {ctx.get('system_stats', 'Unknown')}
- Pending actions: {ctx.get('pending_count', 0)}
- Active executions: {ctx.get('executing_count', 0)}

TASK: Generate ONE concrete, immediately actionable step that:
1. Directly advances the project focus and goals
2. Can be executed with available tools
3. Is specific and measurable
4. Considers current system state and recent activity

WEIGHTS:
- Creativity: {config['creativity_weight']}
- Feasibility: {config['feasibility_weight']} 
- Relevance: {config['relevance_weight']}

Return only the action as a single clear sentence. Focus on high-impact, unblocking steps.
"""

        try:
            response = self.agent.deep_llm.predict(prompt)
            return (response or "").strip()[:500]  # Limit length
        except Exception as e:
            self.add_to_focus_board("issues", f"LLM generate failed: {e}")
            return None

    def _evaluate_action(self, action: ProactiveAction, ctx: Dict[str, Any]) -> Tuple[bool, float]:
        """Evaluate if action is worth executing"""
        tools = [getattr(t, "name", str(t)) for t in getattr(self.agent, "tools", [])]
        
        eval_prompt = f"""Evaluate this proposed action for execution:

PROPOSAL: {action.thought}
PROJECT FOCUS: {self.focus}
AVAILABLE TOOLS: {tools}
CURRENT STATE: {json.dumps(ctx.get('focus_board', {}), ensure_ascii=False)[-500:]}

Score this proposal on a scale of 0.0 to 1.0 considering:
1. Feasibility with available tools (0-1)
2. Relevance to project focus (0-1) 
3. Potential impact/value (0-1)
4. Safety and appropriateness (0-1)
5. Timing appropriateness (0-1)

Respond with: SCORE: X.X
Then explain your reasoning briefly.
"""

        try:
            response = self.agent.fast_llm.invoke(eval_prompt)
            response_str = str(response).strip()
            
            # Extract score
            score = 0.0
            if "SCORE:" in response_str.upper():
                score_part = response_str.upper().split("SCORE:")[1].split()[0]
                try:
                    score = float(score_part)
                except ValueError:
                    score = 0.0
                    
            is_actionable = score >= self.config["thought_generation"]["min_evaluation_score"]
            return is_actionable, score
            
        except Exception as e:
            self.add_to_focus_board("issues", f"LLM evaluate failed: {e}")
            return False, 0.0

    def _determine_priority(self, thought: str, ctx: Dict[str, Any]) -> ActionPriority:
        """Determine action priority based on content"""
        thought_lower = thought.lower()
        
        if any(word in thought_lower for word in ["urgent", "critical", "error", "failure", "block"]):
            return ActionPriority.CRITICAL
        elif any(word in thought_lower for word in ["important", "priority", "deadline", "issue"]):
            return ActionPriority.HIGH
        elif any(word in thought_lower for word in ["optimize", "improve", "enhance", "refactor"]):
            return ActionPriority.LOW
        else:
            return ActionPriority.NORMAL

    def _categorize_action(self, thought: str) -> str:
        """Categorize the action type"""
        thought_lower = thought.lower()
        
        if any(word in thought_lower for word in ["fix", "debug", "error", "issue"]):
            return "troubleshooting"
        elif any(word in thought_lower for word in ["test", "verify", "check", "validate"]):
            return "testing"
        elif any(word in thought_lower for word in ["document", "write", "record", "log"]):
            return "documentation"
        elif any(word in thought_lower for word in ["optimize", "improve", "refactor", "enhance"]):
            return "optimization"
        elif any(word in thought_lower for word in ["create", "build", "implement", "develop"]):
            return "development"
        else:
            return "general"

    def _execute_action(self, action: ProactiveAction) -> None:
        """Execute an approved action"""
        if len(self.active_executions) >= self.max_concurrent_actions:
            # Queue for later
            self.add_to_focus_board("issues", f"Max concurrent actions reached, queuing: {action.thought[:100]}")
            return
            
        action.status = ActionStatus.EXECUTING
        self.active_executions[action.id] = action
        
        self.pool.submit(
            self._execute_goal_with_tracking,
            action,
            priority=Priority.HIGH if action.priority in [ActionPriority.CRITICAL, ActionPriority.HIGH] else Priority.NORMAL,
            name=f"proactive.execute.{action.id[:8]}",
            labels=(self.system_label_exec,)
        )

    def _execute_goal_with_tracking(self, action: ProactiveAction) -> None:
        """Execute goal with comprehensive tracking"""
        start_time = time.time()
        
        try:
            payload = f"""Goal: {action.thought}
Focus: {self.focus}
Context: {json.dumps(action.context, ensure_ascii=False)}
Priority: {action.priority.value}
Status: {json.dumps(self.focus_board, ensure_ascii=False)[-2000:]}"""

            result_parts = []
            for chunk in self.agent.toolchain.execute_tool_chain(payload):
                result_parts.append(str(chunk))
                
            result_str = "".join(result_parts)
            execution_time = time.time() - start_time
            
            # Update action
            action.status = ActionStatus.COMPLETED
            action.execution_result = result_str[:2000]  # Limit size
            action.execution_time = execution_time
            
            # Update metrics
            self.metrics.completed_actions += 1
            if action.execution_time:
                # Update running average
                total_time = self.metrics.avg_execution_time * max(1, self.metrics.completed_actions - 1)
                self.metrics.avg_execution_time = (total_time + execution_time) / self.metrics.completed_actions
            
            # Add to focus board
            self.add_to_focus_board("progress", f"Completed: {action.thought}")
            if result_str:
                self.add_to_focus_board("progress", f"Result: {result_str[:300]}...")
                
            self._emit_event("action_completed", {"action": action.to_dict()})
            
        except Exception as e:
            execution_time = time.time() - start_time
            action.status = ActionStatus.FAILED
            action.error = str(e)
            action.execution_time = execution_time
            
            self.metrics.failed_actions += 1
            self.add_to_focus_board("issues", f"Execution failed for '{action.thought}': {e}")
            self._emit_event("action_failed", {"action": action.to_dict(), "error": str(e)})
            
        finally:
            # Clean up
            if action.id in self.active_executions:
                del self.active_executions[action.id]
            self.action_history.append(action)

    # Status and Metrics
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive status"""
        with self._lock:
            return {
                "state": self.state.value,
                "focus": self.focus,
                "focus_description": self.focus_description,
                "focus_goals": self.focus_goals,
                "interval": self.proactive_interval,
                "auto_approve": self.auto_approve,
                "max_concurrent": self.max_concurrent_actions,
                "metrics": self.metrics.to_dict(),
                "pending_actions": len(self.pending_actions),
                "active_executions": len(self.active_executions),
                "providers": [p.name for p in self.context_providers],
                "focus_board_sizes": {k: len(v) for k, v in self.focus_board.items()},
                "last_tick": self._ticker_task_id is not None
            }

    def get_metrics(self) -> FocusMetrics:
        """Get current metrics"""
        with self._lock:
            return self.metrics

    def reset_metrics(self) -> None:
        """Reset metrics counters"""
        with self._lock:
            self.metrics = FocusMetrics()
            self._emit_event("metrics_reset", {})

    # Utility methods
    def relate_to_focus(self, user_input: str, response: str) -> str:
        """Add focus context to responses"""
        if not self.focus:
            return response
            
        pending_count = len(self.pending_actions)
        active_count = len(self.active_executions)
        
        focus_reminder = f"\n[Focus: {self.focus}"
        if pending_count > 0:
            focus_reminder += f", {pending_count} actions pending approval"
        if active_count > 0:
            focus_reminder += f", {active_count} executing"
        focus_reminder += "]"
        
        return response + focus_reminder