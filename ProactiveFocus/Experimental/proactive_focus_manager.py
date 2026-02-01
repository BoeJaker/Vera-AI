# proactive_focus_manager.py
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

from .Components.board_manager import FocusBoard
from .Components.iteration_manager import IterationManager
from .Components.stage_executor import StageExecutor
from .Components.context_manager import ContextEnricher
from .Components.documentation_writer import DocumentationGenerator
from .Components.resource_extractor import ResourceExtractor


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
        proactive_interval: int = 60*10,
        cpu_threshold: float = 70.0,
        focus_boards_dir: str = "./Output/projects/focus_boards",
        auto_restore: bool = True
    ):
        self.agent = agent
        self.hybrid_memory = hybrid_memory
        self.focus: Optional[str] = None
        self.project_id: Optional[str] = None
        
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
    # PUBLIC API - Maintains backward compatibility
    # ============================================================
    
    def set_focus(self, focus: str, project_name: Optional[str] = None, create_project: bool = True):
        """Set focus and optionally link to a project."""
        self.focus = focus
        self.project_id = self.board.set_focus(
            focus, 
            project_name, 
            create_project, 
            self.hybrid_memory,
            self.agent
        )
        
        # Create project documentation directory
        if self.project_id:
            self.doc_generator.ensure_project_dir(self.project_id, focus)
        
        self._broadcast_sync("focus_changed", {
            "focus": focus,
            "project_id": self.project_id
        })
    
    def clear_focus(self):
        """Clear focus and save current state."""
        if self.focus:
            self.board.save()
        
        self.focus = None
        self.project_id = None
        self.stop()
        
        self._broadcast_sync("focus_cleared", {})
    
    def add_to_focus_board(self, category: str, note: str, metadata: Optional[Dict[str, Any]] = None):
        """Add item to focus board."""
        item = self.board.add_item(category, note, metadata)
        
        # Link to graph if available
        if self.hybrid_memory and self.project_id:
            item_id = f"focus_item_{category}_{int(time.time()*1000)}"
            self.hybrid_memory.upsert_entity(
                entity_id=item_id,
                etype="focus_item",
                labels=["FocusItem", category.capitalize()],
                properties={
                    "category": category,
                    "note": note,
                    "project_id": self.project_id,
                    **item.get("metadata", {})
                }
            )
            self.hybrid_memory.link(self.project_id, item_id, f"HAS_{category.upper()}")
        
        self._broadcast_sync("board_updated", {
            "category": category,
            "item": item,
            "focus_board": self.board.get_all()
        })
    
    def save_focus_board(self, filename: Optional[str] = None) -> str:
        """Save focus board to file and hybrid memory."""
        filepath = self.board.save(
            self.focus,
            self.project_id,
            self.agent,
            filename
        )
        
        # Save to hybrid memory
        if self.hybrid_memory and self.project_id and filepath:
            doc_id = f"focus_board_{self.project_id}_{int(time.time()*1000)}"
            self.hybrid_memory.attach_document(
                entity_id=self.project_id,
                doc_id=doc_id,
                text=json.dumps(self.board.get_all(), indent=2),
                metadata={
                    "type": "focus_board_snapshot",
                    "filepath": filepath,
                    "focus": self.focus
                }
            )
        
        self._broadcast_sync("board_saved", {"filepath": filepath})
        return filepath
    
    def load_focus_board(self, filename: str) -> bool:
        """Load focus board from file."""
        result = self.board.load(filename)
        if result:
            self.focus = result.get("focus")
            self.project_id = result.get("project_id")
            self._broadcast_sync("board_loaded", {
                "filepath": filename,
                "focus": self.focus
            })
        return bool(result)
    
    def start(self):
        """Start proactive background loop."""
        if not self.running and self.focus:
            self.running = True
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
        """
        Main iterative workflow with intelligent stage selection.
        Drop-in replacement with enhanced logic.
        """
        self.workflow_active = True
        
        self._stream_output("="*60, "info")
        self._stream_output("🚀 INTELLIGENT PROACTIVE WORKFLOW STARTED", "success")
        self._stream_output("="*60, "info")
        self._stream_output(f"📋 Configuration:", "info")
        self._stream_output(f"   • Max iterations: {max_iterations or 'Infinite'}", "info")
        self._stream_output(f"   • Interval: {iteration_interval}s", "info")
        self._stream_output(f"   • Auto-execute: {auto_execute}", "info")
        self._stream_output(f"   • Focus: {self.focus}", "info")
        self._stream_output("="*60 + "\n", "info")
        
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
        """Restore most recent focus from memory."""
        result = self.board.restore_from_memory(self.hybrid_memory)
        if result:
            self.focus = result.get("focus")
            self.project_id = result.get("project_id")
            
            self._broadcast_sync("focus_restored", {
                "focus": self.focus,
                "project_id": self.project_id,
                "board": self.board.get_all()
            })
    
    def _run_proactive_loop(self):
        """Background proactive loop."""
        print("[FocusManager] Proactive loop started")
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
                
                while self.running and psutil.cpu_percent() >= self.cpu_threshold:
                    time.sleep(2)
                
                print("[FocusManager] CPU dropped - resuming...")
                self._broadcast_sync("proactive_resumed", {})
            
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
            self.board.get_all()
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
        else:
            stream_fn = llm.stream
        
        for chunk in stream_fn(llm, prompt) if hasattr(self.agent, '_stream_with_thought_polling') else stream_fn(prompt):
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
    # GRAPH INTEGRATION (delegated to components)
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