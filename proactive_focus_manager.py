

import asyncio
import threading
import time
import json
import os
from datetime import datetime
from typing import Optional, Callable, Dict, List, Any
import psutil
import re


class ProactiveFocusManager:
    """Enhanced with streaming support, WebSocket broadcasting, and hybrid memory integration"""
    
    def __init__(
        self,
        agent,
        hybrid_memory=None,
        proactive_interval: int = 60*10,
        cpu_threshold: float = 70.0,
        focus_boards_dir: str = "./Configuration/focus_boards",
        auto_restore: bool = True
    ):
        self.agent = agent
        self.hybrid_memory = hybrid_memory
        self.focus: Optional[str] = None
        self.project_id: Optional[str] = None  # Link to project entity
        self.focus_board = {
            "progress": [],
            "next_steps": [],
            "issues": [],
            "ideas": [],
            "actions": [],
            "completed": []
        }
        self.proactive_interval = proactive_interval
        self.cpu_threshold = cpu_threshold
        self.running = False
        self.thread = None
        self.latest_conversation = ""
        self.proactive_callback: Optional[Callable[[str], None]] = None
        self.pause_event = threading.Event()
        self._websockets = []
        self.current_thought = ""
        self.thought_streaming = False
        self.focus_boards_dir = focus_boards_dir
        os.makedirs(focus_boards_dir, exist_ok=True)
        
        # Auto-restore last focus from graph
        if auto_restore and hybrid_memory:
            self._restore_last_focus()
    
    async def broadcast_to_websockets(self, event_type: str, data: dict):
        """Broadcast updates to all connected WebSockets."""
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
            except Exception as e:
                print(f"[FocusManager] Failed to send to websocket: {e}")
                disconnected.append(websocket)
        
        for ws in disconnected:
            self._websockets.remove(ws)
    
    def _broadcast_sync(self, event_type: str, data: dict):
        """Synchronous wrapper for broadcasting from non-async context."""
        if not self._websockets:
            return
        
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.broadcast_to_websockets(event_type, data))
            loop.close()
        except Exception as e:
            print(f"[FocusManager] Broadcast error: {e}")
    
    @staticmethod
    def _sanitize_metadata(metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Sanitize metadata for ChromaDB by removing None values and converting 
        unsupported types to strings.
        """
        if not metadata:
            return {}
        
        sanitized = {}
        for key, value in metadata.items():
            # Skip None values
            if value is None:
                continue
            
            # Convert supported types
            if isinstance(value, (bool, int, float, str)):
                sanitized[key] = value
            # Convert lists and dicts to JSON strings
            elif isinstance(value, (list, dict)):
                sanitized[key] = json.dumps(value)
            # Convert everything else to string
            else:
                sanitized[key] = str(value)
        
        return sanitized
    
    def _restore_last_focus(self):
        """Restore the most recent focus and focus board from hybrid memory."""
        if not self.hybrid_memory:
            return
        
        try:
            print("[FocusManager] Searching for last focus in graph...")
            
            # Query Neo4j for most recent project with focus board
            with self.hybrid_memory.graph._driver.session() as sess:
                # Find most recent active project
                result = sess.run("""
                    MATCH (p:Project)
                    WHERE p.status = 'active' OR p.status IS NULL
                    RETURN p.id AS project_id, 
                           p.name AS name, 
                           p.description AS description,
                           p.created_at AS created_at
                    ORDER BY p.created_at DESC
                    LIMIT 1
                """).single()
                
                if not result:
                    print("[FocusManager] No previous project found")
                    return
                
                self.project_id = result["project_id"]
                self.focus = result["description"] or result["name"]
                
                print(f"[FocusManager] Restored project: {self.project_id}")
                print(f"[FocusManager] Restored focus: {self.focus}")
                
                # Reconstruct focus board from graph
                self._reconstruct_focus_board_from_graph()
                
                # Try to load most recent board snapshot
                board_result = sess.run("""
                    MATCH (p:Project {id: $project_id})-[:HAS_DOCUMENT]->(d:Document)
                    WHERE d.type = 'focus_board_snapshot'
                    RETURN d.id AS doc_id
                    ORDER BY d.created_at DESC
                    LIMIT 1
                """, project_id=self.project_id).single()
                
                if board_result:
                    # Retrieve document from vector store
                    doc_id = board_result["doc_id"]
                    docs = self.hybrid_memory.vec.get_collection("long_term_docs").get(
                        ids=[doc_id]
                    )
                    
                    if docs and docs.get("documents"):
                        board_data = json.loads(docs["documents"][0])
                        # Merge with current board (graph data takes precedence for newer items)
                        self._merge_focus_boards(board_data.get("board", {}))
                        print(f"[FocusManager] Loaded board snapshot: {doc_id}")
                
                self._broadcast_sync("focus_restored", {
                    "focus": self.focus,
                    "project_id": self.project_id,
                    "board": self.focus_board
                })
                
        except Exception as e:
            print(f"[FocusManager] Error restoring focus: {e}")
    
    def _reconstruct_focus_board_from_graph(self):
        """Reconstruct focus board from graph entities linked to current project."""
        if not self.project_id or not self.hybrid_memory:
            return
        
        try:
            with self.hybrid_memory.graph._driver.session() as sess:
                # Get all focus items linked to project
                result = sess.run("""
                    MATCH (p:Project {id: $project_id})-[r:REL]->(item:FocusItem)
                    RETURN item.category AS category,
                           item.note AS note,
                           item.created_at AS timestamp,
                           item AS props,
                           r.rel AS rel_type
                    ORDER BY item.created_at ASC
                """, project_id=self.project_id)
                
                for record in result:
                    category = record["category"]
                    if category and category in self.focus_board:
                        item = {
                            "note": record["note"],
                            "timestamp": record["timestamp"],
                            "metadata": dict(record["props"])
                        }
                        self.focus_board[category].append(item)
                
                print(f"[FocusManager] Reconstructed focus board with {sum(len(v) for v in self.focus_board.values())} items")
                
        except Exception as e:
            print(f"[FocusManager] Error reconstructing focus board: {e}")
    
    def _merge_focus_boards(self, snapshot_board: Dict[str, List]):
        """Merge snapshot board with current board, keeping newer items."""
        for category, items in snapshot_board.items():
            if category not in self.focus_board:
                self.focus_board[category] = items
            else:
                # Create set of existing notes to avoid duplicates
                existing_notes = {item.get("note") for item in self.focus_board[category]}
                
                # Add items from snapshot that aren't already present
                for item in items:
                    if item.get("note") not in existing_notes:
                        self.focus_board[category].append(item)
        
        print("[FocusManager] Merged snapshot with current board")
    
    def set_focus(self, focus: str, project_name: Optional[str] = None, create_project: bool = True):
        """Set focus and optionally link to a project in hybrid memory."""
        self.focus = focus
        print(f"[FocusManager] Focus set to: {focus}")
        
        # Create or link to project in hybrid memory
        if self.hybrid_memory and (project_name or create_project):
            project_name = project_name or focus
            self.project_id = self._ensure_project(project_name, focus)
            print(f"[FocusManager] Linked to project: {self.project_id}")
        
        # Store in agent memory with sanitized metadata
        metadata = {"topic": "focus"}
        if self.project_id:
            metadata["project_id"] = self.project_id
        
        self.agent.mem.add_session_memory(
            self.agent.sess.id, 
            f"[FocusManager] Focus set to: {focus}", 
            "Thought", 
            metadata
        )
        
        # Broadcast focus change
        self._broadcast_sync("focus_changed", {
            "focus": focus, 
            "project_id": self.project_id
        })
    
    def _ensure_project(self, project_name: str, description: str) -> str:
        """Create or retrieve a project entity in hybrid memory."""
        project_id = f"project_{project_name.lower().replace(' ', '_')}"
        
        # Create project node
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
        
        # Link to current session
        if hasattr(self.agent, 'sess') and self.agent.sess:
            self.hybrid_memory.link_session_focus(
                self.agent.sess.id, 
                [project_id]
            )
        
        return project_id
    
    def clear_focus(self):
        """Clear focus and save current state."""
        if self.focus:
            self.save_focus_board()
        
        self.focus = None
        self.project_id = None
        self.stop()
        print("[FocusManager] Focus cleared")
        
        self._broadcast_sync("focus_cleared", {})
    
    def add_to_focus_board(self, category: str, note: str, metadata: Optional[Dict[str, Any]] = None):
        """Add item to focus board with optional metadata."""
        if category not in self.focus_board:
            self.focus_board[category] = []
        
        item = {
            "note": note,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }
        
        self.focus_board[category].append(item)
        
        # Store in hybrid memory if available
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
                    **item["metadata"]
                }
            )
            self.hybrid_memory.link(self.project_id, item_id, f"HAS_{category.upper()}")
        
        # Broadcast board update
        self._broadcast_sync("board_updated", {
            "category": category,
            "item": item,
            "focus_board": self.focus_board
        })
        
        print(f"[FocusManager] Added to {category}: {note}")
    
    def update_focus_board_item(self, category: str, index: int, new_note: str, 
                               new_metadata: Optional[Dict[str, Any]] = None):
        """Update an existing focus board item."""
        if category in self.focus_board and 0 <= index < len(self.focus_board[category]):
            old_item = self.focus_board[category][index]
            self.focus_board[category][index] = {
                "note": new_note,
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": new_metadata or old_item.get("metadata", {}),
                "previous_note": old_item.get("note")
            }
            
            self._broadcast_sync("board_item_updated", {
                "category": category,
                "index": index,
                "item": self.focus_board[category][index]
            })
            
            print(f"[FocusManager] Updated {category}[{index}]")
    
    def move_to_completed(self, category: str, index: int):
        """Move an item from one category to completed."""
        if category in self.focus_board and 0 <= index < len(self.focus_board[category]):
            item = self.focus_board[category].pop(index)
            item["completed_at"] = datetime.utcnow().isoformat()
            item["original_category"] = category
            self.focus_board["completed"].append(item)
            
            self._broadcast_sync("item_completed", {
                "category": category,
                "item": item
            })
            
            print(f"[FocusManager] Moved {category}[{index}] to completed")
    
    def save_focus_board(self, filename: Optional[str] = None) -> str:
        """Save focus board to file and hybrid memory."""
        if not self.focus:
            print("[FocusManager] No active focus to save")
            return None
        
        # Generate filename
        if not filename:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            safe_focus = re.sub(r'[^\w\-_]', '_', self.focus)[:50]
            filename = f"{safe_focus}_{timestamp}.json"
        
        filepath = os.path.join(self.focus_boards_dir, filename)
        
        # Prepare data
        board_data = {
            "focus": self.focus,
            "project_id": self.project_id,
            "created_at": datetime.utcnow().isoformat(),
            "board": self.focus_board,
            "metadata": {
                "session_id": self.agent.sess.id if hasattr(self.agent, 'sess') else None
            }
        }
        
        # Save to file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(board_data, f, indent=2, ensure_ascii=False)
        
        print(f"[FocusManager] Saved focus board to: {filepath}")
        
        # Save to hybrid memory
        if self.hybrid_memory and self.project_id:
            doc_id = f"focus_board_{self.project_id}_{int(time.time()*1000)}"
            self.hybrid_memory.attach_document(
                entity_id=self.project_id,
                doc_id=doc_id,
                text=json.dumps(board_data, indent=2),
                metadata={
                    "type": "focus_board_snapshot",
                    "filepath": filepath,
                    "focus": self.focus
                }
            )
            print(f"[FocusManager] Saved to hybrid memory: {doc_id}")
        
        self._broadcast_sync("board_saved", {"filepath": filepath})
        
        return filepath
    
    def load_focus_board(self, filename: str) -> bool:
        """Load focus board from file."""
        filepath = os.path.join(self.focus_boards_dir, filename)
        
        if not os.path.exists(filepath):
            print(f"[FocusManager] Focus board not found: {filepath}")
            return False
        
        with open(filepath, 'r', encoding='utf-8') as f:
            board_data = json.load(f)
        
        self.focus = board_data.get("focus")
        self.project_id = board_data.get("project_id")
        self.focus_board = board_data.get("board", {})
        
        print(f"[FocusManager] Loaded focus board from: {filepath}")
        self._broadcast_sync("board_loaded", {"filepath": filepath, "focus": self.focus})
        
        return True
    
    def list_saved_boards(self) -> List[Dict[str, Any]]:
        """List all saved focus boards."""
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
    
    def generate_ideas(self, context: Optional[str] = None) -> List[str]:
        """Use LLM to generate ideas for the current focus."""
        if not self.focus:
            return []
        
        prompt = f"""
        Project Focus: {self.focus}
        
        Current Focus Board:
        - Progress: {json.dumps(self.focus_board.get('progress', []), indent=2)}
        - Next Steps: {json.dumps(self.focus_board.get('next_steps', []), indent=2)}
        - Issues: {json.dumps(self.focus_board.get('issues', []), indent=2)}
        - Ideas: {json.dumps(self.focus_board.get('ideas', []), indent=2)}
        
        {f"Additional Context: {context}" if context else ""}
        
        Generate 5 creative and actionable ideas to advance this project.
        Focus on practical solutions and innovative approaches.
        Respond with a JSON array of idea strings.
        """
        
        self.thought_streaming = True
        self.current_thought = ""
        
        self._broadcast_sync("idea_generation_started", {"focus": self.focus})
        self._broadcast_sync("thought_generation_started",  {"focus": self.focus})
        try:
            response = ""
            for chunk in self.agent.deep_llm.stream(prompt):
                self.current_thought += chunk
                response += chunk
                
                self._broadcast_sync("thought_chunk", {
                    "chunk": chunk,
                    "current_thought": self.current_thought
                })
            
            self.thought_streaming = False
            self._broadcast_sync("idea_generation_completed", {"response": response})
            
        except Exception as e:
            self.thought_streaming = False
            response = f"Error streaming ideas response: {str(e)}"
            self._broadcast_sync("idea_generation_error", {"error": str(e)})
        
        # Parse response
        try:
            ideas = json.loads(response)
            if not isinstance(ideas, list):
                ideas = [response]
        except:
            # Fallback: split by newlines
            ideas = [line.strip() for line in response.split('\n') if line.strip()]
        
        # Add to focus board
        for idea in ideas:
            self.add_to_focus_board("ideas", idea)
        
        return ideas
    
    def generate_next_steps(self, context: Optional[str] = None) -> List[str]:
        """Use LLM to generate next steps based on current state."""
        if not self.focus:
            return []
        
        prompt = f"""
        Project Focus: {self.focus}
        
        Current State:
        - Progress: {json.dumps(self.focus_board.get('progress', []), indent=2)}
        - Issues: {json.dumps(self.focus_board.get('issues', []), indent=2)}
        - Ideas: {json.dumps(self.focus_board.get('ideas', []), indent=2)}
        
        {f"Additional Context: {context}" if context else ""}
        
        Generate 5 specific, actionable next steps to move this project forward.
        Consider current progress and outstanding issues.
        Respond with a JSON array of step strings.
        """
        self._broadcast_sync("idea_generation_started", {"focus": self.focus})
        self._broadcast_sync("thought_generation_started",  {"focus": self.focus})
        try:
            response = ""
            for chunk in self.agent.deep_llm.stream(prompt):
                self.current_thought += chunk
                response += chunk
                
                self._broadcast_sync("thought_chunk", {
                    "chunk": chunk,
                    "current_thought": self.current_thought
                })
            
            self.thought_streaming = False
            self._broadcast_sync("idea_generation_completed", {"response": response})
            
        except Exception as e:
            self.thought_streaming = False
            response = f"Error streaming ideas response: {str(e)}"
            self._broadcast_sync("idea_generation_error", {"error": str(e)})
        
        try:
            steps = json.loads(response)
            if not isinstance(steps, list):
                steps = [response]
        except:
            steps = [line.strip() for line in response.split('\n') if line.strip()]
        
        for step in steps:
            self.add_to_focus_board("next_steps", step)
        
        return steps
    
    def generate_actions(self, context: Optional[str] = None) -> List[Dict[str, Any]]:
        """Use LLM to generate executable actions with tool suggestions."""
        if not self.focus:
            return []
        
        available_tools = [tool.name for tool in self.agent.tools]
        
        prompt = f"""
        Project Focus: {self.focus}
        
        Focus Board State:
        {json.dumps(self.focus_board, indent=2)}
        
        Available Tools: {available_tools}
        
        {f"Additional Context: {context}" if context else ""}
        
        Generate 3-5 executable actions that can be performed using the available tools.
        Each action should include:
        - description: What needs to be done
        - tools: Which tools to use (from available list)
        - priority: high, medium, or low
        
        Respond with a JSON array of action objects.
        """
        self._broadcast_sync("idea_generation_started", {"focus": self.focus})
        self._broadcast_sync("thought_generation_started",  {"focus": self.focus})
        try:
            response = ""
            for chunk in self.agent.deep_llm.stream(prompt):
                self.current_thought += chunk
                response += chunk
                
                self._broadcast_sync("thought_chunk", {
                    "chunk": chunk,
                    "current_thought": self.current_thought
                })
            
            self.thought_streaming = False
            self._broadcast_sync("idea_generation_completed", {"response": response})
            
        except Exception as e:
            self.thought_streaming = False
            response = f"Error streaming ideas response: {str(e)}"
            self._broadcast_sync("idea_generation_error", {"error": str(e)})
        
        try:
            actions = json.loads(response)
            if not isinstance(actions, list):
                actions = [{"description": response, "tools": [], "priority": "medium"}]
        except:
            actions = [{"description": response, "tools": [], "priority": "medium"}]
        
        for action in actions:
            self.add_to_focus_board("actions", json.dumps(action), 
                                   metadata=action)
        
        return actions
    
    def handoff_to_toolchain(self, action: Dict[str, Any]):
        """Hand off an action to the ToolChainPlanner for decomposition and execution."""
        print(f"[FocusManager] Handing off to toolchain: {action.get('description')}")
        
        # Build query for toolchain
        query = f"""
        Project: {self.focus}
        Action: {action.get('description')}
        Suggested Tools: {action.get('tools', [])}
        Priority: {action.get('priority', 'medium')}
        
        Context:
        - Current Progress: {json.dumps(self.focus_board.get('progress', [])[-3:], indent=2)}
        - Related Issues: {json.dumps(self.focus_board.get('issues', [])[-3:], indent=2)}
        """
        
        self._broadcast_sync("toolchain_handoff", {
            "action": action,
            "query": query
        })
        
        # Execute via toolchain
        try:
            result = ""
            for chunk in self.agent.toolchain.execute_tool_chain(query):
                result += str(chunk)
            
            # Update focus board with results
            self.add_to_focus_board("progress", 
                                   f"Completed: {action.get('description')}")
            
            if result:
                self.add_to_focus_board("progress", 
                                       f"Result: {result[:500]}")
            
            return result
            
        except Exception as e:
            error_msg = f"Toolchain execution failed: {e}"
            print(f"[FocusManager] {error_msg}")
            self.add_to_focus_board("issues", error_msg)
            return None
    
    def update_latest_conversation(self, conversation: str):
        self.latest_conversation = conversation
    
    def start(self):
        if not self.running and self.focus:
            self.running = True
            self.thread = threading.Thread(target=self._run_proactive_loop, daemon=True)
            self.thread.start()
            
            self._broadcast_sync("focus_started", {"focus": self.focus})
    
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
            self.thread = None
        
        self._broadcast_sync("focus_stopped", {})
    
    def _count_ollama_processes(self):
        """Get total system CPU usage."""
        return psutil.cpu_percent(interval=0.1)
    
    def _run_proactive_loop(self):
        print("[FocusManager] Proactive loop started")
        
        self._broadcast_sync("proactive_loop_started", {"interval": self.proactive_interval})
        
        while self.running:
            cpu_usage = self._count_ollama_processes()
            if cpu_usage >= self.cpu_threshold:
                print(f"[FocusManager] High CPU usage ({cpu_usage:.1f}%) — pausing...")
                self._broadcast_sync("proactive_paused", {
                    "reason": "high_cpu_usage",
                    "cpu_usage": cpu_usage,
                    "threshold": self.cpu_threshold
                })
                
                self.pause_event.clear()
                while self.running and self._count_ollama_processes() >= self.cpu_threshold:
                    time.sleep(2)
                
                print("[FocusManager] CPU usage dropped — resuming...")
                self._broadcast_sync("proactive_resumed", {
                    "cpu_usage": self._count_ollama_processes()
                })
                self.pause_event.set()
            
            self.pause_event.wait()
            
            # Generate proactive thought with streaming
            proactive_thought = self._generate_proactive_thought_streaming()
            
            if proactive_thought:
                if self.proactive_callback:
                    self.proactive_callback(proactive_thought)
                
                self.add_to_focus_board("actions", proactive_thought)
                
                # Evaluate if actionable
                evaluation_prompt = f"""
                Evaluate this proactive thought: {proactive_thought}
                
                Is it actionable given the tools available and relevant to the current focus?
                Tools available: {[tool.name for tool in self.agent.tools]}
                Focus: {self.focus}
                
                If actionable, respond with 'YES'. If not, respond with 'NO' and brief reason.
                """
                evaluation = self.agent.fast_llm.invoke(evaluation_prompt)
                
                if evaluation.strip().lower().startswith("yes"):
                    self._broadcast_sync("proactive_executing", {"thought": proactive_thought})
                    self.execute_goal_with_vera(proactive_thought)
            
            time.sleep(self.proactive_interval)
    
    def _generate_proactive_thought_streaming(self) -> Optional[str]:
        """Generate proactive thought with streaming support."""
        print("[FocusManager] Generating proactive thought (streaming)...")
        
        if not self.focus:
            return None
        
        self.thought_streaming = True
        self.current_thought = ""
        
        self._broadcast_sync("thought_generation_started", {"focus": self.focus})
        
        prompt = f"""
        You are assisting with the project: {self.focus}
        
        Recent conversation/context:
        {self.latest_conversation}
        
        Focus board state:
        {json.dumps(self.focus_board, indent=2)}
        
        Suggest the most valuable immediate action or next step to advance the project.
        Focus on concrete, practical actions or investigations.
        """
        
        try:
            for chunk in self.agent.deep_llm.stream(prompt):
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
            print(f"[FocusManager] Error generating proactive thought: {e}")
            self._broadcast_sync("thought_error", {"error": str(e)})
            self.thought_streaming = False
            return None
    
    def execute_goal_with_vera(self, goal: str):
        """Instruct Vera to achieve the goal using tools if needed and log results."""
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
                
                if isinstance(result, dict):
                    if "next_steps" in result:
                        for step in result["next_steps"]:
                            self.add_to_focus_board("next_steps", step)
                    if "issues" in result:
                        for issue in result["issues"]:
                            self.add_to_focus_board("issues", issue)
                    if "ideas" in result:
                        for idea in result["ideas"]:
                            self.add_to_focus_board("ideas", idea)
                
                self._broadcast_sync("goal_execution_completed", {
                    "goal": goal,
                    "result": result[:500]
                })
                
                print(f"[FocusManager] Logged results to focus board.")
        
        except Exception as e:
            print(f"[FocusManager] Failed to execute goal with Vera: {e}")
            self.add_to_focus_board("issues", f"Execution failed for '{goal}': {e}")
            self._broadcast_sync("goal_execution_failed", {
                "goal": goal,
                "error": str(e)
            })
    
    def iterative_workflow(self, max_iterations: Optional[int] = None, 
                          iteration_interval: int = 300,
                          auto_execute: bool = True):
        """
        Continuous iterative workflow that updates and executes the focus board.
        
        Args:
            max_iterations: Maximum number of iterations (None = infinite)
            iteration_interval: Seconds between iterations (default 5 minutes)
            auto_execute: Whether to automatically execute generated actions
        """
        iteration = 0
        print(f"[FocusManager] Starting iterative workflow (max_iterations={max_iterations})")
        
        self._broadcast_sync("workflow_started", {
            "max_iterations": max_iterations,
            "iteration_interval": iteration_interval,
            "auto_execute": auto_execute
        })
        
        while max_iterations is None or iteration < max_iterations:
            iteration += 1
            print(f"\n{'='*60}")
            print(f"[FocusManager] Iteration {iteration}")
            print(f"{'='*60}\n")
            
            try:
                # Step 1: Review current state
                state_summary = self._review_current_state()
                print(f"[FocusManager] State: {state_summary}")
                
                # Step 2: Generate ideas if needed (sparse - every 3 iterations)
                if iteration % 3 == 0:
                    print("[FocusManager] Generating new ideas...")
                    ideas = self.generate_ideas(context=state_summary)
                    print(f"[FocusManager] Generated {len(ideas)} ideas")
                
                # Step 3: Generate next steps based on current progress
                print("[FocusManager] Generating next steps...")
                steps = self.generate_next_steps(context=state_summary)
                print(f"[FocusManager] Generated {len(steps)} next steps")
                
                # Step 4: Generate executable actions
                print("[FocusManager] Generating actions...")
                actions = self.generate_actions(context=state_summary)
                print(f"[FocusManager] Generated {len(actions)} actions")
                
                # Step 5: Execute high-priority actions if auto_execute enabled
                if auto_execute and actions:
                    executed_count = 0
                    for action in actions:
                        if isinstance(action, dict):
                            priority = action.get('priority', 'medium')
                            if priority == 'high' and executed_count < 2:  # Limit to 2 per iteration
                                print(f"[FocusManager] Executing high-priority action...")
                                self.handoff_to_toolchain(action)
                                executed_count += 1
                        
                        # Check CPU before next execution
                        cpu_usage = self._count_ollama_processes()
                        if cpu_usage >= self.cpu_threshold:
                            print(f"[FocusManager] CPU threshold reached ({cpu_usage:.1f}%), pausing execution")
                            break
                    
                    print(f"[FocusManager] Executed {executed_count} actions this iteration")
                
                # Step 6: Prune completed items and consolidate board
                self._consolidate_focus_board()
                
                # Step 7: Save checkpoint
                checkpoint_file = self.save_focus_board()
                print(f"[FocusManager] Saved checkpoint: {checkpoint_file}")
                
                # Broadcast iteration complete
                self._broadcast_sync("workflow_iteration_complete", {
                    "iteration": iteration,
                    "state": state_summary,
                    "checkpoint": checkpoint_file
                })
                
                # Wait for next iteration
                if max_iterations is None or iteration < max_iterations:
                    print(f"[FocusManager] Waiting {iteration_interval}s until next iteration...")
                    time.sleep(iteration_interval)
                
            except Exception as e:
                print(f"[FocusManager] Error in iteration {iteration}: {e}")
                self.add_to_focus_board("issues", f"Workflow error in iteration {iteration}: {e}")
                
                # Broadcast error
                self._broadcast_sync("workflow_error", {
                    "iteration": iteration,
                    "error": str(e)
                })
                
                # Continue after brief pause
                time.sleep(30)
        
        print(f"\n[FocusManager] Iterative workflow completed after {iteration} iterations")
        self._broadcast_sync("workflow_completed", {"total_iterations": iteration})
    
    def _review_current_state(self) -> str:
        """Review and summarize current focus board state."""
        total_items = sum(len(v) for v in self.focus_board.values())
        
        state = {
            "total_items": total_items,
            "progress_count": len(self.focus_board.get("progress", [])),
            "next_steps_count": len(self.focus_board.get("next_steps", [])),
            "issues_count": len(self.focus_board.get("issues", [])),
            "ideas_count": len(self.focus_board.get("ideas", [])),
            "actions_count": len(self.focus_board.get("actions", [])),
            "completed_count": len(self.focus_board.get("completed", []))
        }
        
        # Generate text summary
        summary_parts = []
        if state["progress_count"] > 0:
            recent_progress = self.focus_board["progress"][-3:]
            summary_parts.append(f"Recent progress: {[p.get('note', '') for p in recent_progress]}")
        
        if state["issues_count"] > 0:
            summary_parts.append(f"{state['issues_count']} open issues")
        
        if state["next_steps_count"] > 0:
            summary_parts.append(f"{state['next_steps_count']} next steps pending")
        
        summary = "; ".join(summary_parts) if summary_parts else "Board initialized"
        
        return summary
    
    def _consolidate_focus_board(self):
        """Consolidate focus board by removing duplicates and archiving old completed items."""
        # Remove duplicate notes in each category (keep most recent)
        for category in self.focus_board:
            if not self.focus_board[category]:
                continue
            
            seen = set()
            unique_items = []
            
            # Iterate in reverse to keep most recent
            for item in reversed(self.focus_board[category]):
                note = item.get("note", "") if isinstance(item, dict) else str(item)
                if note not in seen:
                    seen.add(note)
                    unique_items.append(item)
            
            self.focus_board[category] = list(reversed(unique_items))
        
        # Archive old completed items (keep last 20)
        if len(self.focus_board.get("completed", [])) > 20:
            archived = self.focus_board["completed"][:-20]
            self.focus_board["completed"] = self.focus_board["completed"][-20:]
            
            print(f"[FocusManager] Archived {len(archived)} old completed items")
            
            # Store in hybrid memory if available
            if self.hybrid_memory and self.project_id:
                archive_id = f"completed_archive_{self.project_id}_{int(time.time())}"
                self.hybrid_memory.attach_document(
                    entity_id=self.project_id,
                    doc_id=archive_id,
                    text=json.dumps(archived, indent=2),
                    metadata={"type": "completed_items_archive"}
                )
    
    def start_workflow_thread(self, max_iterations: Optional[int] = None,
                             iteration_interval: int = 300,
                             auto_execute: bool = True):
        """Start iterative workflow in a background thread."""
        if hasattr(self, 'workflow_thread') and self.workflow_thread and self.workflow_thread.is_alive():
            print("[FocusManager] Workflow already running")
            return
        
        self.workflow_thread = threading.Thread(
            target=self.iterative_workflow,
            args=(max_iterations, iteration_interval, auto_execute),
            daemon=True
        )
        self.workflow_thread.start()
        print("[FocusManager] Workflow thread started")


def get_active_ollama_threads():
    """Return active Ollama threads with non-zero CPU usage."""
    active_threads = []
    total_cpu = 0.0

    for proc in psutil.process_iter(attrs=["pid", "name", "cmdline"]):
        try:
            if "ollama" in (proc.info["name"] or "").lower() or any("ollama" in (part or "").lower() for part in proc.info["cmdline"] or []):
                for thread in proc.threads():
                    thread_cpu = proc.cpu_percent(interval=0.1) / proc.num_threads() if proc.num_threads() else 0
                    if thread_cpu > 0:
                        active_threads.append({
                            "pid": proc.pid,
                            "tid": thread.id,
                            "cpu": thread_cpu
                        })
                        total_cpu += thread_cpu
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    print("Active Ollama Threads")
    print("---------------------")
    for t in active_threads:
        print(f"PID: {t['pid']}, TID: {t['tid']}, CPU: {t['cpu']:.2f}%")
    print("---------------------")
    print(f"Total active threads: {len(active_threads)} | Total active CPU: {total_cpu:.2f}%")

    return active_threads


def get_ollama_cpu_load_and_count():
    """Calculate total CPU load and count of threads for all Ollama models."""
    total_cpu = 0.0
    total_threads = 0
    model_processes = {}

    for proc in psutil.process_iter(attrs=["pid", "name", "cmdline", "cpu_percent", "num_threads"]):
        try:
            name = proc.info["name"] or ""
            cmdline = proc.info["cmdline"] or []
            cpu = proc.info["cpu_percent"]
            threads = proc.info["num_threads"]

            if "ollama" in name.lower() or any("ollama" in part.lower() for part in cmdline):
                total_cpu += cpu
                total_threads += threads

                model_name = None
                for part in cmdline:
                    if re.match(r"^[a-zA-Z0-9_\-:]+$", part) and ":" in part:
                        model_name = part
                        break

                if not model_name:
                    model_name = "unknown"

                model_processes.setdefault(model_name, {"cpu": 0.0, "threads": 0})
                model_processes[model_name]["cpu"] += cpu
                model_processes[model_name]["threads"] += threads

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    print("Ollama CPU Load Report")
    print("----------------------")
    for model, stats in model_processes.items():
        print(f"{model} -> CPU: {stats['cpu']:.2f}%, Threads: {stats['threads']}")
    print("----------------------")
    print(f"TOTAL -> CPU: {total_cpu:.2f}%, Threads: {total_threads}")

    return total_cpu, total_threads, model_processes
