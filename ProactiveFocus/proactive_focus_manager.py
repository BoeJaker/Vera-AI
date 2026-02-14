# proactive_focus_manager.py — FIXED VERSION
# Changes marked with # FIX: comments
import asyncio
import threading
import time
import json
import os
import re
from datetime import datetime
from typing import Optional, Callable, Dict, List, Any, Set
import psutil
from pathlib import Path

from Vera.ProactiveFocus.Experimental.Components.board_manager import FocusBoard
from Vera.ProactiveFocus.Experimental.Components.iteration_manager import IterationManager
from Vera.ProactiveFocus.Experimental.Components.stage_executor import StageExecutor
from Vera.ProactiveFocus.Experimental.Components.context_manager import ContextEnricher
from Vera.ProactiveFocus.Experimental.Components.documentation_writer import DocumentationGenerator
from Vera.ProactiveFocus.Experimental.Components.resource_extractor import ResourceExtractor


class ProactiveFocusManager:
    """
    Enhanced modular focus manager with intelligent stage selection.
    
    Drop-in replacement with the same public API, but internally refactored
    into specialized components.
    """
    
    def __init__(
        self,
        agent,
        hybrid_memory=None,
        proactive_interval: int = 1,
        cpu_threshold: float = 70.0,
        focus_boards_dir: str = "./Output/Projects/focus_boards",
        auto_restore: bool = True
    ):
        self.agent = agent
        self.hybrid_memory = hybrid_memory
        self.focus: Optional[str] = None
        self.project_id: Optional[str] = None
        
        # FIX: Store focus_boards_dir on self for API backward compatibility
        # (the delete endpoint accesses fm.focus_boards_dir directly)
        self.focus_boards_dir = focus_boards_dir
        
        # Core components
        self.board = FocusBoard(focus_boards_dir)
        self.iteration_manager = IterationManager(self)
        self.stage_executor = StageExecutor(self)
        self.context_enricher = ContextEnricher(self)
        self.doc_generator = DocumentationGenerator(self)
        self.resource_extractor = ResourceExtractor(hybrid_memory)
        
        # Settings
        self.proactive_interval = proactive_interval
        self.cpu_threshold = cpu_threshold
        self.running = False
        self.thread = None
        self.latest_conversation = ""
        self.proactive_callback: Optional[Callable[[str], None]] = None
        self.pause_event = threading.Event()
        self.pause_event.set()  # FIX: Start un-paused (set = not paused)
        
        # WebSocket streaming
        self._websockets = []
        self.current_thought = ""
        self.thought_streaming = False
        
        # Stage tracking for UI
        self.current_stage = None
        self.current_activity = None
        self.stage_progress = 0
        self.stage_total = 0
        self.workflow_active = False
        
        # Graph integration
        self.current_iteration_id: Optional[str] = None
        self.previous_iteration_id: Optional[str] = None
        self.current_stage_id: Optional[str] = None
        self.previous_stage_id: Optional[str] = None
        self.iteration_count: int = 0
        
        if auto_restore and hybrid_memory:
            self._restore_last_focus()
    
    # ============================================================
    # FIX: BACKWARD COMPATIBILITY PROPERTY
    # The API accesses fm.focus_board everywhere. This property
    # delegates to self.board.board so existing API code works.
    # ============================================================
    
    @property
    def focus_board(self) -> Dict[str, List]:
        """Backward-compatible access to focus board data.
        
        The API (focus.py) accesses fm.focus_board in ~15 endpoints.
        The refactored code stores data in self.board.board.
        This property bridges the two.
        """
        return self.board.board
    
    @focus_board.setter
    def focus_board(self, value: Dict[str, List]):
        """Allow direct assignment for backward compatibility.
        
        The API does things like:
            fm.focus_board[category] = []
            fm.focus_board = {"progress": [], ...}
        """
        self.board.board = value
    
    # ============================================================
    # FIX: MISSING METHOD DELEGATIONS
    # The API calls these directly on the focus manager.
    # ============================================================
    
    def list_saved_boards(self) -> List[Dict[str, Any]]:
        """List all saved focus boards. Delegated to board component.
        
        Called by: GET /{session_id}/boards/list
                   GET /{session_id}/similar
        """
        boards = []
        for filename in os.listdir(self.focus_boards_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(self.focus_boards_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    boards.append({
                        "filename": filename,
                        "focus": data.get("focus"),
                        "created_at": data.get("created_at"),
                        "project_id": data.get("project_id")
                    })
                except Exception as e:
                    print(f"[FocusManager] Error reading {filename}: {e}")
        
        return sorted(boards, key=lambda x: x.get("created_at", ""), reverse=True)
    
    def _find_matching_focus_board(self, focus: str) -> Optional[Dict[str, Any]]:
        """Find matching saved board. Delegated to board component.
        
        Called by: POST /{session_id}/load-by-focus
                   POST /{session_id}/set (in the set_focus function body)
        """
        return self.board._find_matching_board(focus)
    
    def generate_ideas_stage(self, context: Optional[str] = None) -> List[str]:
        """Run ideas generation stage.
        
        Called by: POST /{session_id}/stage/ideas
        """
        print("[FocusManager] Running ideas generation stage...")
        self._broadcast_sync("stage_started", {"stage": "ideas"})
        try:
            ideas = self.generate_ideas(context=context)
            self._broadcast_sync("stage_completed", {"stage": "ideas", "count": len(ideas)})
            return ideas
        except Exception as e:
            print(f"[FocusManager] Ideas stage error: {e}")
            self._broadcast_sync("stage_error", {"stage": "ideas", "error": str(e)})
            return []
    
    def generate_next_steps_stage(self, context: Optional[str] = None) -> List[str]:
        """Run next steps generation stage.
        
        Called by: POST /{session_id}/stage/next_steps
        """
        print("[FocusManager] Running next steps generation stage...")
        self._broadcast_sync("stage_started", {"stage": "next_steps"})
        try:
            steps = self.generate_next_steps(context=context)
            self._broadcast_sync("stage_completed", {"stage": "next_steps", "count": len(steps)})
            return steps
        except Exception as e:
            print(f"[FocusManager] Next steps stage error: {e}")
            self._broadcast_sync("stage_error", {"stage": "next_steps", "error": str(e)})
            return []
    
    def generate_actions_stage(self, context: Optional[str] = None) -> List[Dict[str, Any]]:
        """Run actions generation stage.
        
        Called by: POST /{session_id}/stage/actions
        """
        print("[FocusManager] Running actions generation stage...")
        self._broadcast_sync("stage_started", {"stage": "actions"})
        try:
            actions = self.generate_actions(context=context)
            self._broadcast_sync("stage_completed", {"stage": "actions", "count": len(actions)})
            return actions
        except Exception as e:
            print(f"[FocusManager] Actions stage error: {e}")
            self._broadcast_sync("stage_error", {"stage": "actions", "error": str(e)})
            return []
    
    def handoff_to_toolchain(self, action: Dict[str, Any]) -> Optional[str]:
        """Hand off action to toolchain. Delegated to stage executor.
        
        Called by: POST /{session_id}/action/execute
        """
        return self.stage_executor.handoff_to_toolchain(action)
    
    def trigger_proactive_thought(self) -> Optional[str]:
        """Manually trigger a proactive thought.
        
        Called by: trigger_proactive_thought_async()
        """
        if not self.focus:
            print("[FocusManager] Cannot generate thought: No focus set")
            return None
        
        print("[FocusManager] Manually triggered proactive thought generation...")
        thought = self._generate_proactive_thought_streaming()
        
        if thought:
            self.add_to_focus_board("actions", thought)
            
            # Evaluate if actionable
            try:
                evaluation_prompt = f"""
                Evaluate this proactive thought: {thought}
                Is it actionable given the tools available and relevant to the current focus?
                Tools available: {[tool.name for tool in self.agent.tools]}
                Focus: {self.focus}
                If actionable, respond with 'YES'. If not, respond with 'NO' and brief reason.
                """
                evaluation = self.agent.fast_llm.invoke(evaluation_prompt)
                
                if evaluation.strip().lower().startswith("yes"):
                    self._broadcast_sync("proactive_executing", {"thought": thought})
                    self._execute_goal_with_vera(thought)
                else:
                    self._broadcast_sync("proactive_thought_generated", {
                        "thought": thought, "actionable": False, "reason": evaluation
                    })
            except Exception as e:
                print(f"[FocusManager] Error evaluating thought: {e}")
        
        return thought
    
    def trigger_proactive_thought_async(self):
        """Trigger proactive thought in background thread.
        
        Called by: POST /{session_id}/trigger
        """
        thread = threading.Thread(target=self.trigger_proactive_thought, daemon=True)
        thread.start()
        print("[FocusManager] Started proactive thought generation in background")
    
    def update_latest_conversation(self, conversation: str):
        """Update latest conversation context."""
        self.latest_conversation = conversation
    
    def _execute_goal_with_vera(self, goal: str):
        """Execute goal using toolchain."""
        try:
            print(f"[FocusManager] Sending goal to Vera: {goal}")
            self._broadcast_sync("goal_execution_started", {"goal": goal})
            
            result = ""
            for chunk in self.agent.toolchain.execute_tool_chain(
                f"Goal: {goal}\n\nFocus: {self.focus}\n\nStatus: {json.dumps(self.focus_board)}"
            ):
                result += str(chunk)
            
            if result:
                self.add_to_focus_board("progress", f"Executed goal: {goal}")
                self.add_to_focus_board("progress", f"Result: {result}")
                self._broadcast_sync("goal_execution_completed", {
                    "goal": goal, "result": result[:500]
                })
        except Exception as e:
            print(f"[FocusManager] Failed to execute goal: {e}")
            self.add_to_focus_board("issues", f"Execution failed for '{goal}': {e}")
            self._broadcast_sync("goal_execution_failed", {"goal": goal, "error": str(e)})
    
    # ============================================================
    # PUBLIC API - Maintains backward compatibility
    # ============================================================
    
    def set_focus(self, focus: str, project_name: Optional[str] = None, create_project: bool = True):
        """Set focus and optionally link to a project.
        
        FIX: Ensure self.focus is always synced after board operations,
        and that save receives a valid focus string.
        """
        # FIX: Check for existing board FIRST, before clearing anything
        existing_board = self.board._find_matching_board(focus)
        
        if existing_board:
            print(f"[FocusManager] Found existing focus board: {existing_board['filename']}")
            loaded = self.board.load(existing_board['filename'])
            if loaded:
                # FIX: Sync manager state FROM the loaded data
                self.focus = loaded.get("focus", focus)  # Use loaded focus, fallback to input
                self.project_id = loaded.get("project_id")
                
                print(f"[FocusManager] Loaded existing board. Focus: {self.focus}, Project: {self.project_id}")
                
                self._broadcast_sync("focus_changed", {
                    "focus": self.focus,
                    "project_id": self.project_id,
                    "loaded_existing": True,
                    "filename": existing_board['filename']
                })
                return
        
        # No existing board — save old one if needed, then set new
        old_focus = self.focus
        if old_focus and old_focus != focus:
            print(f"[FocusManager] Saving previous focus board: {old_focus}")
            self.save_focus_board()
        
        # FIX: Set focus on manager BEFORE any operations that need it
        self.focus = focus
        
        # Clear the board for new focus
        self.board.board = {
            "progress": [],
            "next_steps": [],
            "issues": [],
            "ideas": [],
            "actions": [],
            "completed": []
        }
        
        print(f"[FocusManager] Focus set to: {focus} (new board)")
        
        # Create project in hybrid memory
        self.project_id = None
        if self.hybrid_memory and (project_name or create_project):
            project_name = project_name or focus
            self.project_id = self._ensure_project(project_name, focus)
            print(f"[FocusManager] Linked to project: {self.project_id}")
        
        # Create project documentation directory
        if self.project_id:
            try:
                self.doc_generator.ensure_project_dir(self.project_id, focus)
            except Exception as e:
                print(f"[FocusManager] Could not create project dir: {e}")
        
        # Store in agent memory
        metadata = {"topic": "focus"}
        if self.project_id:
            metadata["project_id"] = self.project_id
        
        try:
            self.agent.mem.add_session_memory(
                self.agent.sess.id,
                f"[FocusManager] Focus set to: {focus}",
                "Thought",
                metadata
            )
        except Exception as e:
            print(f"[FocusManager] Could not store in agent memory: {e}")
        
        # Auto-save the new board
        # FIX: self.focus is guaranteed non-None here
        filepath = self.save_focus_board()
        print(f"[FocusManager] Auto-saved new focus board: {filepath}")
        
        self._broadcast_sync("focus_changed", {
            "focus": self.focus,
            "project_id": self.project_id,
            "loaded_existing": False,
            "filepath": filepath
        })
    
    def _ensure_project(self, project_name: str, description: str) -> str:
        """Create or retrieve a project entity in hybrid memory.
        
        FIX: Query for existing project by name FIRST to avoid
        ConstraintValidationFailed on (name, type) uniqueness.
        """
        safe_name = re.sub(r'[^\w\-_ ]', '', project_name).strip()
        if not safe_name:
            safe_name = "unnamed_project"
        
        # FIX: Check if project already exists by name (the constraint key)
        existing_id = None
        try:
            with self.hybrid_memory.graph._driver.session() as sess:
                result = sess.run("""
                    MATCH (p:Entity)
                    WHERE p.name = $name AND p.type = 'project'
                    RETURN p.id AS id
                    LIMIT 1
                """, {"name": project_name}).single()
                
                if result:
                    existing_id = result["id"]
                    print(f"[FocusManager] Found existing project node: {existing_id}")
        except Exception as e:
            print(f"[FocusManager] Error checking for existing project: {e}")
        
        # Use existing ID or generate new one
        project_id = existing_id or f"project_{safe_name.lower().replace(' ', '_')}"
        
        try:
            self.hybrid_memory.upsert_entity(
                entity_id=project_id,
                etype="project",
                labels=["Project"],
                properties={
                    "name": project_name,
                    "description": description,
                    "created_at": datetime.utcnow().isoformat(),
                    "status": "active"
                }
            )
        except Exception as e:
            # FIX: If upsert still fails, just reuse the existing project
            print(f"[FocusManager] Upsert failed, reusing existing project: {e}")
            if not existing_id:
                try:
                    with self.hybrid_memory.graph._driver.session() as sess:
                        result = sess.run("""
                            MATCH (p:Entity)
                            WHERE p.name = $name AND p.type = 'project'
                            RETURN p.id AS id
                            LIMIT 1
                        """, {"name": project_name}).single()
                        if result:
                            project_id = result["id"]
                except Exception:
                    pass
        
        if hasattr(self.agent, 'sess') and self.agent.sess:
            try:
                self.hybrid_memory.link_session_focus(
                    self.agent.sess.id,
                    [project_id]
                )
            except Exception as e:
                print(f"[FocusManager] Error linking session to project: {e}")
        
        return project_id
    
    def clear_focus(self):
        """Clear focus and save current state."""
        if self.focus:
            self.save_focus_board()
        
        self.focus = None
        self.project_id = None
        self.stop()
        
        self._broadcast_sync("focus_cleared", {})
    
    def add_to_focus_board(self, category: str, note: str, metadata: Optional[Dict[str, Any]] = None):
        """Add item to focus board."""
        item = self.board.add_item(category, note, metadata)
        
        # Link to graph if available
        if self.hybrid_memory and self.project_id:
            try:
                item_id = f"focus_item_{category}_{int(time.time()*1000)}"
                self.hybrid_memory.upsert_entity(
                    entity_id=item_id,
                    etype="focus_item",
                    labels=["FocusItem", category.capitalize()],
                    properties={
                        "category": category,
                        "note": note,
                        "project_id": self.project_id,
                        **(metadata or {})
                    }
                )
                self.hybrid_memory.link(self.project_id, item_id, f"HAS_{category.upper()}")
            except Exception as e:
                print(f"[FocusManager] Error linking to graph: {e}")
        
        self._broadcast_sync("board_updated", {
            "category": category,
            "item": item,
            "focus_board": self.focus_board  # FIX: uses property
        })
    
    def update_focus_board_item(self, category: str, index: int, new_note: str,
                                new_metadata: Optional[Dict[str, Any]] = None):
        """Update existing focus board item."""
        items = self.board.get_category(category)
        if 0 <= index < len(items):
            old_item = items[index]
            items[index] = {
                "note": new_note,
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": new_metadata or old_item.get("metadata", {}),
                "previous_note": old_item.get("note")
            }
            self._broadcast_sync("board_item_updated", {
                "category": category, "index": index, "item": items[index]
            })
    
    def move_to_completed(self, category: str, index: int):
        """Move item to completed."""
        self.board.move_to_completed(category, index)
        self._broadcast_sync("item_completed", {"category": category})
    
    def save_focus_board(self, filename: Optional[str] = None) -> str:
        """Save focus board to file and hybrid memory.
        
        FIX: Guard against self.focus being None (prevents garbage filenames).
        """
        if not self.focus:
            print("[FocusManager] No active focus to save")
            return None
        
        filepath = self.board.save(
            self.focus,
            self.project_id,
            self.agent,
            filename
        )
        
        # Save to hybrid memory
        if self.hybrid_memory and self.project_id and filepath:
            try:
                doc_id = f"focus_board_{self.project_id}_{int(time.time()*1000)}"
                self.hybrid_memory.attach_document(
                    entity_id=self.project_id,
                    doc_id=doc_id,
                    text=json.dumps(self.focus_board, indent=2),
                    metadata={
                        "type": "focus_board_snapshot",
                        "filepath": filepath,
                        "focus": self.focus
                    }
                )
            except Exception as e:
                print(f"[FocusManager] Error saving to hybrid memory: {e}")
        
        self._broadcast_sync("board_saved", {"filepath": filepath})
        return filepath
    
    def load_focus_board(self, filename: str) -> bool:
        """Load focus board from file.
        
        FIX: Properly sync self.focus and self.project_id from loaded data,
        and broadcast the full board state so the UI can render it.
        """
        result = self.board.load(filename)
        if result:
            # FIX: Sync ALL manager state from loaded data
            self.focus = result.get("focus")
            self.project_id = result.get("project_id")
            
            print(f"[FocusManager] Loaded board. Focus: {self.focus}, Project: {self.project_id}")
            print(f"[FocusManager] Board categories: {list(self.focus_board.keys())}")
            print(f"[FocusManager] Board items: {sum(len(v) for v in self.focus_board.values())}")
            
            # FIX: Broadcast with focus_board data so UI receives it
            self._broadcast_sync("board_loaded", {
                "filepath": filename,
                "focus": self.focus,
                "focus_board": self.focus_board,  # FIX: Include board data
                "project_id": self.project_id
            })
            return True
        return False
    
    def start(self):
        """Start proactive background loop."""
        if not self.running and self.focus:
            self.running = True
            self.pause_event.set()  # FIX: Ensure not paused on start
            self.thread = threading.Thread(target=self._run_proactive_loop, daemon=True)
            self.thread.start()
            self._broadcast_sync("focus_started", {"focus": self.focus})
    
    def stop(self):
        """Stop proactive background loop."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
            self.thread = None
        self._broadcast_sync("focus_stopped", {})
    
    def iterative_workflow(
        self, 
        max_iterations: Optional[int] = None,
        iteration_interval: int = 300,
        auto_execute: bool = True
    ):
        """Main iterative workflow with intelligent stage selection."""
        self.workflow_active = True
        
        self._stream_output("="*60, "info")
        self._stream_output("🚀 INTELLIGENT PROACTIVE WORKFLOW STARTED", "success")
        self._stream_output("="*60, "info")
        self._stream_output(f"   • Focus: {self.focus}", "info")
        self._stream_output(f"   • Project: {self.project_id}", "info")
        self._stream_output(f"   • Max iterations: {max_iterations or 'Infinite'}", "info")
        self._stream_output(f"   • Interval: {iteration_interval}s", "info")
        self._stream_output(f"   • Auto-execute: {auto_execute}", "info")
        self._stream_output("="*60 + "\n", "info")
        
        # FIX: Verify focus is set before starting workflow
        if not self.focus:
            self._stream_output("❌ Cannot start workflow: No focus set!", "error")
            self.workflow_active = False
            return
        
        try:
            self.iteration_manager.run(
                max_iterations=max_iterations,
                iteration_interval=iteration_interval,
                auto_execute=auto_execute
            )
        finally:
            self.workflow_active = False
    
    def start_workflow_thread(
        self,
        max_iterations: Optional[int] = None,
        iteration_interval: int = 300,
        auto_execute: bool = True
    ):
        """Start iterative workflow in background thread."""
        if hasattr(self, 'workflow_thread') and self.workflow_thread and self.workflow_thread.is_alive():
            print("[FocusManager] Workflow already running")
            return
        
        # FIX: Log what focus is active when starting
        print(f"[FocusManager] Starting workflow thread with focus: {self.focus}")
        
        self.workflow_thread = threading.Thread(
            target=self.iterative_workflow,
            args=(max_iterations, iteration_interval, auto_execute),
            daemon=True
        )
        self.workflow_thread.start()
    
    # Individual stage methods (backward compatibility)
    def generate_ideas(self, context: Optional[str] = None) -> List[str]:
        return self.stage_executor.execute_ideas_stage(context)
    
    def generate_next_steps(self, context: Optional[str] = None) -> List[str]:
        return self.stage_executor.execute_next_steps_stage(context)
    
    def generate_actions(self, context: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.stage_executor.execute_actions_stage(context)
    
    def execute_actions_stage(self, max_executions: int = 2, priority_filter: str = "high"):
        return self.stage_executor.execute_execution_stage(max_executions, priority_filter)
    
    # ============================================================
    # INTERNAL HELPERS
    # ============================================================
    
    def _restore_last_focus(self):
        """Restore most recent focus from memory.
        
        FIX: Don't set self.focus if restored value is None.
        """
        result = self.board.restore_from_memory(self.hybrid_memory)
        if result:
            restored_focus = result.get("focus")
            restored_project = result.get("project_id")
            
            # FIX: Only restore if we got a valid focus string
            if not restored_focus:
                print(f"[FocusManager] Restored focus is None/empty, skipping restore")
                return
            
            # Only restore if we don't already have a focus set
            if not self.focus:
                self.focus = restored_focus
                self.project_id = restored_project
                print(f"[FocusManager] Restored focus: {self.focus}")
                print(f"[FocusManager] Restored project: {self.project_id}")
                
                self._broadcast_sync("focus_restored", {
                    "focus": self.focus,
                    "project_id": self.project_id,
                    "board": self.focus_board
                })
            else:
                print(f"[FocusManager] Focus already set ({self.focus}), skipping restore")
    
    def _run_proactive_loop(self):
        """Background proactive loop."""
        print(f"[FocusManager] Proactive loop started (focus: {self.focus})")
        self._broadcast_sync("proactive_loop_started", {"interval": self.proactive_interval})
        
        while self.running:
            # Check CPU
            cpu_usage = psutil.cpu_percent(interval=0.1)
            if cpu_usage >= self.cpu_threshold:
                print(f"[FocusManager] High CPU ({cpu_usage:.1f}%) - pausing...")
                self._broadcast_sync("proactive_paused", {
                    "reason": "high_cpu_usage",
                    "cpu_usage": cpu_usage
                })
                
                self.pause_event.clear()
                while self.running and psutil.cpu_percent() >= self.cpu_threshold:
                    time.sleep(2)
                
                print("[FocusManager] CPU dropped - resuming...")
                self._broadcast_sync("proactive_resumed", {})
                self.pause_event.set()
            
            self.pause_event.wait()
            
            # Generate proactive thought
            thought = self._generate_proactive_thought_streaming()
            
            if thought and self.proactive_callback:
                self.proactive_callback(thought)
            
            time.sleep(self.proactive_interval)
    
    def _generate_proactive_thought_streaming(self) -> Optional[str]:
        """Generate proactive thought with streaming."""
        if not self.focus:
            return None
        
        self.thought_streaming = True
        self.current_thought = ""
        self._broadcast_sync("thought_generation_started", {"focus": self.focus})
        
        # Get enriched context
        context = self.context_enricher.build_proactive_context(
            self.latest_conversation,
            self.focus_board  # FIX: uses property
        )
        
        prompt = f"""
        You are assisting with: {self.focus}
        
        {context}
        
        Suggest the most valuable immediate action to advance the project.
        Focus on concrete, practical next steps.
        """
        
        try:
            for chunk in self._stream_llm_with_thought_broadcast(self.agent.deep_llm, prompt):
                self.current_thought += chunk
                self._broadcast_sync("thought_chunk", {
                    "chunk": chunk,
                    "current_thought": self.current_thought
                })
            
            thought = self.current_thought.strip()
            self._broadcast_sync("thought_completed", {"thought": thought})
            self.thought_streaming = False
            return thought
            
        except Exception as e:
            print(f"[FocusManager] Error generating thought: {e}")
            self._broadcast_sync("thought_error", {"error": str(e)})
            self.thought_streaming = False
            return None
    
    # ============================================================
    # UI/STREAMING HELPERS
    # ============================================================
    
    async def broadcast_to_websockets(self, event_type: str, data: dict):
        """Broadcast to connected WebSockets."""
        if not self._websockets:
            return
        
        disconnected = []
        message = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        for websocket in self._websockets:
            try:
                await websocket.send_json(message)
            except Exception:
                disconnected.append(websocket)
        
        for ws in disconnected:
            self._websockets.remove(ws)
    
    def _broadcast_sync(self, event_type: str, data: dict):
        """Synchronous broadcast wrapper."""
        if not self._websockets:
            return
        
        try:
            try:
                loop = asyncio.get_running_loop()
                asyncio.ensure_future(self.broadcast_to_websockets(event_type, data))
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.broadcast_to_websockets(event_type, data))
                loop.close()
        except Exception as e:
            print(f"[FocusManager] Broadcast failed: {e}")
    
    def _set_stage(self, stage: str, activity: str = "", total_steps: int = 0):
        """Set current stage."""
        self.current_stage = stage
        self.current_activity = activity
        self.stage_progress = 0
        self.stage_total = total_steps
        
        self._broadcast_sync("stage_update", {
            "stage": stage,
            "activity": activity,
            "progress": 0,
            "total": total_steps
        })
    
    def _update_progress(self, increment: int = 1):
        """Update stage progress."""
        self.stage_progress += increment
        
        self._broadcast_sync("stage_progress", {
            "stage": self.current_stage,
            "progress": self.stage_progress,
            "total": self.stage_total,
            "percentage": (self.stage_progress / self.stage_total * 100) if self.stage_total > 0 else 0
        })
    
    def _stream_output(self, text: str, category: str = "info"):
        """Stream output to UI."""
        self._broadcast_sync("stream_output", {
            "text": text,
            "category": category,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    def _clear_stage(self):
        """Clear current stage."""
        self.current_stage = None
        self.current_activity = None
        self.stage_progress = 0
        self.stage_total = 0
        self._broadcast_sync("stage_cleared", {})
    
    def _stream_llm_with_thought_broadcast(self, llm, prompt: str):
        """Universal LLM streaming with thought extraction."""
        response_buffer = ""
        thought_buffer = ""
        in_thought = False
        
        if hasattr(self.agent, '_stream_with_thought_polling'):
            stream_fn = self.agent._stream_with_thought_polling
            stream_iter = stream_fn(llm, prompt)
        else:
            stream_iter = llm.stream(prompt)
        
        for chunk in stream_iter:
            chunk_text = self._extract_chunk_text(chunk)
            
            i = 0
            while i < len(chunk_text):
                if chunk_text[i:i+9] == '<thought>':
                    in_thought = True
                    i += 9
                    self._broadcast_sync("llm_thought_start", {})
                    continue
                
                if chunk_text[i:i+10] == '</thought>':
                    in_thought = False
                    i += 10
                    self._broadcast_sync("llm_thought_end", {})
                    
                    if thought_buffer.strip() and hasattr(self.agent, 'mem'):
                        self.agent.mem.add_session_memory(
                            self.agent.sess.id,
                            thought_buffer.strip(),
                            "Thought",
                            {"source": "proactive_focus", "focus": self.focus}
                        )
                    thought_buffer = ""
                    continue
                
                if in_thought:
                    thought_buffer += chunk_text[i]
                    self._broadcast_sync("llm_thought_chunk", {"chunk": chunk_text[i]})
                else:
                    response_buffer += chunk_text[i]
                    self._broadcast_sync("response_chunk", {
                        "chunk": chunk_text[i],
                        "accumulated": response_buffer
                    })
                    yield chunk_text[i]
                
                i += 1
        
        return response_buffer
    
    def _extract_chunk_text(self, chunk) -> str:
        """Extract text from various chunk formats."""
        if isinstance(chunk, str):
            return chunk
        elif hasattr(chunk, 'content'):
            return chunk.content
        elif hasattr(chunk, 'text'):
            return chunk.text
        elif isinstance(chunk, dict):
            return chunk.get('content', chunk.get('text', str(chunk)))
        return str(chunk)
    
    # ============================================================
    # GRAPH INTEGRATION
    # ============================================================
    
    def _create_iteration_node(self) -> str:
        """Create iteration node in graph."""
        if not self.hybrid_memory:
            return None
        
        self.iteration_count += 1
        iteration_id = f"iteration_{self.project_id}_{self.iteration_count}_{int(time.time())}"
        
        self.hybrid_memory.upsert_entity(
            entity_id=iteration_id,
            etype="workflow_iteration",
            labels=["WorkflowIteration", "FocusIteration"],
            properties={
                "iteration_number": self.iteration_count,
                "project_id": self.project_id,
                "focus": self.focus,
                "session_id": self.agent.sess.id if hasattr(self.agent, 'sess') else None,
                "started_at": datetime.utcnow().isoformat(),
                "status": "in_progress"
            }
        )
        
        if self.project_id:
            self.hybrid_memory.link(
                self.project_id,
                iteration_id,
                "HAS_ITERATION",
                {"iteration_number": self.iteration_count}
            )
        
        if self.previous_iteration_id:
            self.hybrid_memory.link(
                self.previous_iteration_id,
                iteration_id,
                "NEXT_ITERATION",
                {"sequence": self.iteration_count - 1}
            )
        
        self.current_iteration_id = iteration_id
        return iteration_id
    
    def _complete_iteration_node(self, summary: Optional[str] = None):
        """Mark iteration as complete."""
        if not self.hybrid_memory or not self.current_iteration_id:
            return
        
        with self.hybrid_memory.graph._driver.session() as sess:
            sess.run("""
                MATCH (i:WorkflowIteration {id: $id})
                SET i.completed_at = $completed_at,
                    i.status = 'completed',
                    i.summary = $summary
            """, {
                "id": self.current_iteration_id,
                "completed_at": datetime.utcnow().isoformat(),
                "summary": summary or ""
            })
        
        self.previous_iteration_id = self.current_iteration_id
        self.current_iteration_id = None
    
    def _create_stage_node(self, stage_name: str, stage_type: str, activity: str = "") -> str:
        """Create a workflow stage node."""
        if not self.hybrid_memory:
            return None
        
        stage_id = f"stage_{stage_type}_{self.current_iteration_id}_{int(time.time())}"
        
        self.hybrid_memory.upsert_entity(
            entity_id=stage_id,
            etype="workflow_stage",
            labels=["WorkflowStage", stage_type.capitalize()],
            properties={
                "stage_name": stage_name,
                "stage_type": stage_type,
                "activity": activity,
                "iteration_id": self.current_iteration_id,
                "project_id": self.project_id,
                "focus": self.focus,
                "session_id": self.agent.sess.id if hasattr(self.agent, 'sess') else None,
                "started_at": datetime.utcnow().isoformat(),
                "status": "in_progress"
            }
        )
        
        if self.current_iteration_id:
            self.hybrid_memory.link(
                self.current_iteration_id,
                stage_id,
                "HAS_STAGE",
                {"stage_type": stage_type}
            )
        
        if self.previous_stage_id:
            self.hybrid_memory.link(
                self.previous_stage_id,
                stage_id,
                "NEXT_STAGE",
                {"stage_type": stage_type}
            )
        
        self.current_stage_id = stage_id
        return stage_id
    
    def _complete_stage_node(self, output: Optional[str] = None, output_count: int = 0):
        """Mark stage as complete."""
        if not self.hybrid_memory or not self.current_stage_id:
            return
        
        # Extract resources from output
        if output:
            self.resource_extractor.extract_and_link(output, self.current_stage_id)
        
        with self.hybrid_memory.graph._driver.session() as sess:
            sess.run("""
                MATCH (s:WorkflowStage {id: $id})
                SET s.completed_at = $completed_at,
                    s.status = 'completed',
                    s.output_count = $output_count
            """, {
                "id": self.current_stage_id,
                "completed_at": datetime.utcnow().isoformat(),
                "output_count": output_count
            })
        
        self.previous_stage_id = self.current_stage_id
        self.current_stage_id = None
    
    # ============================================================
    # HELPER: Parse JSON responses from LLM
    # ============================================================
    
    def _parse_json_response(self, response: str) -> list:
        """Parse JSON response, handling markdown code fences."""
        cleaned = response.strip()
        if cleaned.startswith('```'):
            lines = cleaned.split('\n')
            if lines[0].startswith('```'):
                lines = lines[1:]
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            cleaned = '\n'.join(lines)
        
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, list):
                return parsed
            else:
                return [parsed]
        except Exception:
            lines = [line.strip() for line in cleaned.split('\n') if line.strip()]
            lines = [line for line in lines if line not in ['[', ']', '{', '}']]
            return lines if lines else [response]