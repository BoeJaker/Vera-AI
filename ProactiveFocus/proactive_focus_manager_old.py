import asyncio
import threading
import time
import json
import os
import re
from datetime import datetime
from typing import Optional, Callable, Dict, List, Any, Set
import psutil
from urllib.parse import urlparse
import json
import time
from datetime import datetime
from typing import Optional, Dict, List, Any
import hashlib
from pathlib import Path


class ProactiveFocusManager:
    """Enhanced with full Neo4j graph integration and resource extraction"""
    
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
        
        # Iteration and stage tracking
        self.current_iteration_id: Optional[str] = None
        self.previous_iteration_id: Optional[str] = None
        self.current_stage_id: Optional[str] = None
        self.previous_stage_id: Optional[str] = None
        self.iteration_count: int = 0
        
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
        
        # Stage tracking for WebSocket UI
        self.current_stage = None
        self.current_activity = None
        self.stage_progress = 0
        self.stage_total = 0
        self.workflow_active = False
        
        if auto_restore and hybrid_memory:
            self._restore_last_focus()
    
    # ============================================================
    # RESOURCE EXTRACTION
    # ============================================================
    
    def _extract_resources(self, text: str) -> Dict[str, List[str]]:
        """
        Extract resources from text using regex patterns.
        Returns dict with 'urls' and 'filepaths' lists.
        """
        resources = {
            'urls': [],
            'filepaths': []
        }
        
        # URL pattern - matches http/https URLs
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        urls = re.findall(url_pattern, text)
        resources['urls'] = list(set(urls))  # Deduplicate
        
        # Filepath patterns
        # Unix-style absolute paths
        unix_path_pattern = r'(?:^|[\s\'"(])(\/[\w\-\.\/]+)(?:[\s\'"\)]|$)'
        # Windows-style paths
        windows_path_pattern = r'(?:^|[\s\'"(])([A-Za-z]:\\[\w\-\.\\]+)(?:[\s\'"\)]|$)'
        # Relative paths with common extensions
        relative_path_pattern = r'(?:^|[\s\'"(])(\.{1,2}\/[\w\-\.\/]+\.(?:py|js|json|txt|md|yaml|yml|conf|sh|bat))(?:[\s\'"\)]|$)'
        
        unix_paths = [m.group(1) for m in re.finditer(unix_path_pattern, text)]
        windows_paths = [m.group(1) for m in re.finditer(windows_path_pattern, text)]
        relative_paths = [m.group(1) for m in re.finditer(relative_path_pattern, text)]
        
        all_paths = unix_paths + windows_paths + relative_paths
        resources['filepaths'] = list(set(all_paths))  # Deduplicate
        
        return resources
    
    def _create_resource_node(self, resource_uri: str, resource_type: str, source_node_id: str) -> str:
        """
        Create a resource node in the graph and link it to source.
        
        Args:
            resource_uri: The URL or filepath
            resource_type: 'url' or 'filepath'
            source_node_id: ID of the stage/node that referenced this resource
            
        Returns:
            Resource node ID
        """
        if not self.hybrid_memory:
            return None
        
        # Create stable ID for resource
        resource_hash = hashlib.md5(resource_uri.encode()).hexdigest()[:12]
        resource_id = f"resource_{resource_type}_{resource_hash}"
        
        # Extract additional metadata
        metadata = {
            "uri": resource_uri,
            "type": resource_type,
            "session_id": self.agent.sess.id if hasattr(self.agent, 'sess') else None,
            "project_id": self.project_id,
            "discovered_at": datetime.utcnow().isoformat()
        }
        
        if resource_type == 'url':
            parsed = urlparse(resource_uri)
            metadata["domain"] = parsed.netloc
            metadata["scheme"] = parsed.scheme
            metadata["path"] = parsed.path
        elif resource_type == 'filepath':
            metadata["filename"] = os.path.basename(resource_uri)
            metadata["extension"] = os.path.splitext(resource_uri)[1]
            metadata["is_absolute"] = os.path.isabs(resource_uri)
        
        # Create resource node
        self.hybrid_memory.upsert_entity(
            entity_id=resource_id,
            etype="resource",
            labels=["Resource", resource_type.upper()],
            properties=metadata
        )
        
        # Link source to resource
        self.hybrid_memory.link(
            source_node_id,
            resource_id,
            "REFERENCES",
            {"discovered_at": datetime.utcnow().isoformat()}
        )
        
        print(f"[FocusManager] Created resource node: {resource_id} ({resource_uri})")
        return resource_id
    
    def _extract_and_link_resources(self, text: str, source_node_id: str) -> Dict[str, List[str]]:
        """
        Extract resources from text and create linked nodes.
        
        Returns:
            Dict with lists of created resource node IDs
        """
        if not self.hybrid_memory or not text:
            return {'urls': [], 'filepaths': []}
        
        resources = self._extract_resources(text)
        created = {'urls': [], 'filepaths': []}
        
        # Create nodes for URLs
        for url in resources['urls']:
            try:
                resource_id = self._create_resource_node(url, 'url', source_node_id)
                if resource_id:
                    created['urls'].append(resource_id)
            except Exception as e:
                print(f"[FocusManager] Error creating URL node: {e}")
        
        # Create nodes for filepaths
        for filepath in resources['filepaths']:
            try:
                resource_id = self._create_resource_node(filepath, 'filepath', source_node_id)
                if resource_id:
                    created['filepaths'].append(resource_id)
            except Exception as e:
                print(f"[FocusManager] Error creating filepath node: {e}")
        
        if created['urls'] or created['filepaths']:
            print(f"[FocusManager] Extracted {len(created['urls'])} URLs and {len(created['filepaths'])} filepaths")
        
        return created
    
    # ============================================================
    # ITERATION AND STAGE MANAGEMENT
    # ============================================================
    
    def _create_iteration_node(self) -> str:
        """
        Create a workflow iteration node and link to previous iteration.
        
        Returns:
            Iteration node ID
        """
        if not self.hybrid_memory:
            return None
        
        self.iteration_count += 1
        iteration_id = f"iteration_{self.project_id}_{self.iteration_count}_{int(time.time())}"
        
        # Create iteration node
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
        
        # Link to project
        if self.project_id:
            self.hybrid_memory.link(
                self.project_id,
                iteration_id,
                "HAS_ITERATION",
                {"iteration_number": self.iteration_count}
            )
        
        # Link to previous iteration
        if self.previous_iteration_id:
            self.hybrid_memory.link(
                self.previous_iteration_id,
                iteration_id,
                "NEXT_ITERATION",
                {"sequence": self.iteration_count - 1}
            )
            self.hybrid_memory.link(
                iteration_id,
                self.previous_iteration_id,
                "PREVIOUS_ITERATION",
                {"sequence": self.iteration_count - 1}
            )
        
        # Link to session
        if hasattr(self.agent, 'sess') and self.agent.sess:
            self.hybrid_memory.link(
                self.agent.sess.id,
                iteration_id,
                "PERFORMED_ITERATION",
                {"timestamp": datetime.utcnow().isoformat()}
            )
        
        self.current_iteration_id = iteration_id
        print(f"[FocusManager] Created iteration node: {iteration_id} (#{self.iteration_count})")
        
        return iteration_id
    
    def _complete_iteration_node(self, summary: Optional[str] = None):
        """Mark current iteration as complete and update properties."""
        if not self.hybrid_memory or not self.current_iteration_id:
            return
        
        # Update iteration properties
        with self.hybrid_memory.graph._driver.session() as sess:
            sess.run("""
                MATCH (i:WorkflowIteration {id: $id})
                SET i.completed_at = $completed_at,
                    i.status = 'completed',
                    i.summary = $summary
                RETURN i
            """, {
                "id": self.current_iteration_id,
                "completed_at": datetime.utcnow().isoformat(),
                "summary": summary or ""
            })
        
        self.previous_iteration_id = self.current_iteration_id
        self.current_iteration_id = None
        
        print(f"[FocusManager] Completed iteration: {self.previous_iteration_id}")
    
    def _create_stage_node(self, stage_name: str, stage_type: str, activity: str = "") -> str:
        """
        Create a workflow stage node and link to previous stage and current iteration.
        
        Args:
            stage_name: Display name of stage (e.g., "Ideas Generation")
            stage_type: Type identifier (e.g., "ideas", "next_steps", "actions", "execution")
            activity: Description of what the stage is doing
            
        Returns:
            Stage node ID
        """
        if not self.hybrid_memory:
            return None
        
        stage_id = f"stage_{stage_type}_{self.current_iteration_id}_{int(time.time())}"
        
        # Create stage node
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
        
        # Link to current iteration
        if self.current_iteration_id:
            self.hybrid_memory.link(
                self.current_iteration_id,
                stage_id,
                "HAS_STAGE",
                {"stage_type": stage_type}
            )
        
        # Link to previous stage
        if self.previous_stage_id:
            self.hybrid_memory.link(
                self.previous_stage_id,
                stage_id,
                "NEXT_STAGE",
                {"stage_type": stage_type}
            )
            self.hybrid_memory.link(
                stage_id,
                self.previous_stage_id,
                "PREVIOUS_STAGE",
                {}
            )
        
        self.current_stage_id = stage_id
        print(f"[FocusManager] Created stage node: {stage_id} ({stage_name})")
        
        return stage_id
    
    def _complete_stage_node(self, output: Optional[str] = None, output_count: int = 0):
        """
        Mark current stage as complete, extract resources, and update properties.
        
        Args:
            output: Text output from the stage
            output_count: Number of items generated (ideas, steps, actions, etc.)
        """
        if not self.hybrid_memory or not self.current_stage_id:
            return
        
        # Extract and link resources from output
        resource_ids = {'urls': [], 'filepaths': []}
        if output:
            resource_ids = self._extract_and_link_resources(output, self.current_stage_id)
        
        # Update stage properties
        with self.hybrid_memory.graph._driver.session() as sess:
            sess.run("""
                MATCH (s:WorkflowStage {id: $id})
                SET s.completed_at = $completed_at,
                    s.status = 'completed',
                    s.output_count = $output_count,
                    s.resources_found = $resources_found
                RETURN s
            """, {
                "id": self.current_stage_id,
                "completed_at": datetime.utcnow().isoformat(),
                "output_count": output_count,
                "resources_found": len(resource_ids['urls']) + len(resource_ids['filepaths'])
            })
        
        # Store output in vector store for semantic search
        if output and len(output) > 50:
            self.hybrid_memory.vec.add_texts(
                collection="long_term_docs",
                ids=[f"{self.current_stage_id}_output"],
                texts=[output[:5000]],  # Limit to 5000 chars
                metadatas=[{
                    "entity_id": self.current_stage_id,
                    "type": "stage_output",
                    "iteration_id": self.current_iteration_id,
                    "session_id": self.agent.sess.id if hasattr(self.agent, 'sess') else None,
                    "project_id": self.project_id
                }]
            )
        
        self.previous_stage_id = self.current_stage_id
        self.current_stage_id = None
        
        print(f"[FocusManager] Completed stage: {self.previous_stage_id}")
    
    
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
            # Try to get the running loop
            try:
                loop = asyncio.get_running_loop()
                # If we're in an async context, schedule the broadcast
                asyncio.ensure_future(self.broadcast_to_websockets(event_type, data))
            except RuntimeError:
                # No running loop, create a new one (safe in threads)
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.broadcast_to_websockets(event_type, data))
                loop.close()
        except Exception as e:
            # Silently fail - broadcasting is not critical
            print(f"[FocusManager] Broadcast failed (non-critical): {e}")

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
        
        # Check if we already have a saved board for this focus
        existing_board = self._find_matching_focus_board(focus)
        
        if existing_board:
            print(f"[FocusManager] Found existing focus board: {existing_board['filename']}")
            # Load the existing board
            if self.load_focus_board(existing_board['filename']):
                print(f"[FocusManager] Loaded existing focus board for: {focus}")
                self._broadcast_sync("focus_changed", {
                    "focus": focus, 
                    "project_id": self.project_id,
                    "loaded_existing": True,
                    "filename": existing_board['filename']
                })
                return
        
        # No existing board found, set new focus and clear board
        old_focus = self.focus
        
        # Save current board if there was a previous focus
        if old_focus and old_focus != focus:
            print(f"[FocusManager] Saving previous focus: {old_focus}")
            self.save_focus_board()
        
        # Set new focus
        self.focus = focus
        
        # Clear the focus board for new focus
        self.focus_board = {
            "progress": [],
            "next_steps": [],
            "issues": [],
            "ideas": [],
            "actions": [],
            "completed": []
        }
        
        print(f"[FocusManager] Focus set to: {focus} (new board)")
        
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
        
        # Auto-save the new empty board
        filepath = self.save_focus_board()
        print(f"[FocusManager] Auto-saved new focus board: {filepath}")
        
        # Broadcast focus change
        self._broadcast_sync("focus_changed", {
            "focus": focus, 
            "project_id": self.project_id,
            "loaded_existing": False,
            "filepath": filepath
        })

    def _find_matching_focus_board(self, focus: str) -> Optional[Dict[str, Any]]:
        """
        Find the most recent saved focus board that matches the given focus.
        Uses fuzzy matching to handle slight variations.
        """
        if not focus:
            return None
        
        focus_lower = focus.lower().strip()
        saved_boards = self.list_saved_boards()
        
        # First try exact match
        for board in saved_boards:
            if board.get('focus', '').lower().strip() == focus_lower:
                print(f"[FocusManager] Found exact match: {board['filename']}")
                return board
        
        # Try partial match (focus text contains or is contained in saved focus)
        for board in saved_boards:
            saved_focus = board.get('focus', '').lower().strip()
            if not saved_focus:
                continue
            
            # Check if one contains the other
            if focus_lower in saved_focus or saved_focus in focus_lower:
                print(f"[FocusManager] Found partial match: {board['filename']}")
                return board
        
        print(f"[FocusManager] No matching focus board found for: {focus}")
        return None
        
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
        
    def _parse_json_response(self, response: str) -> list:
            """Parse JSON response, handling markdown code fences and other formatting."""
            # Remove markdown code fences if present
            cleaned = response.strip()
            if cleaned.startswith('```'):
                # Remove opening fence
                lines = cleaned.split('\n')
                if lines[0].startswith('```'):
                    lines = lines[1:]
                # Remove closing fence
                if lines and lines[-1].strip() == '```':
                    lines = lines[:-1]
                cleaned = '\n'.join(lines)
            
            try:
                parsed = json.loads(cleaned)
                if isinstance(parsed, list):
                    return parsed
                else:
                    return [parsed]
            except:
                # Fallback: split by newlines and filter
                lines = [line.strip() for line in cleaned.split('\n') if line.strip()]
                # Filter out lines that look like JSON artifacts
                lines = [line for line in lines if not line in ['[', ']', '{', '}']]
                return lines if lines else [response]

    def generate_ideas(self, context: Optional[str] = None) -> List[str]:
        """Generate ideas with full graph integration"""
        if not self.focus:
            return []
        
        # Create stage node
        stage_id = self._create_stage_node(
            "Ideas Generation",
            "ideas",
            "Analyzing current state and generating creative ideas"
        )
        
        self._set_stage("Ideas Generation", "Analyzing current state and generating creative ideas", 3)
        self._stream_output(f"🎯 Focus: {self.focus}", "info")
        self._stream_output("💡 Generating ideas...", "info")
        
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
        
        self._update_progress()
        self._stream_output("📝 Composing prompt...", "info")
        
        try:
            response = ""
            
            # Use universal streaming wrapper
            for chunk in self._stream_llm_with_thought_broadcast(self.agent.deep_llm, prompt):
                response += chunk
            
            self._update_progress()
            self._stream_output("✅ Ideas generated successfully", "success")
            
        except Exception as e:
            self._stream_output(f"❌ Error: {str(e)}", "error")
            response = f"Error: {str(e)}"
        
        ideas = self._parse_json_response(response)
        
        self._update_progress()
        self._stream_output(f"📊 Generated {len(ideas)} ideas", "success")
        
        # Create idea nodes and link to stage
        for idx, idea in enumerate(ideas, 1):
            idea_id = f"idea_{stage_id}_{idx}"
            
            # Create idea node
            self.hybrid_memory.upsert_entity(
                entity_id=idea_id,
                etype="idea",
                labels=["Idea", "FocusBoardItem"],
                properties={
                    "text": idea,
                    "category": "ideas",
                    "index": idx,
                    "stage_id": stage_id,
                    "iteration_id": self.current_iteration_id,
                    "project_id": self.project_id,
                    "session_id": self.agent.sess.id if hasattr(self.agent, 'sess') else None,
                    "created_at": datetime.utcnow().isoformat()
                }
            )
            
            # Link to stage
            self.hybrid_memory.link(stage_id, idea_id, "GENERATED", {"index": idx})
            
            # Add to vector store
            self.hybrid_memory.vec.add_texts(
                collection="long_term_docs",
                ids=[idea_id],
                texts=[idea],
                metadatas=[{
                    "type": "idea",
                    "stage_id": stage_id,
                    "project_id": self.project_id,
                    "session_id": self.agent.sess.id if hasattr(self.agent, 'sess') else None
                }]
            )
            
            # Extract resources from idea
            self._extract_and_link_resources(idea, idea_id)
            
            # Add to focus board
            self.add_to_focus_board("ideas", idea)
            self._stream_output(f"  {idx}. {idea[:100]}{'...' if len(idea) > 100 else ''}", "info")
        
        # Complete stage
        self._complete_stage_node(output=response, output_count=len(ideas))
        self._clear_stage()
        
        return ideas
    
    def generate_next_steps(self, context: Optional[str] = None) -> List[str]:
        """Generate next steps with full graph integration"""
        if not self.focus:
            return []
        
        # Create stage node
        stage_id = self._create_stage_node(
            "Next Steps",
            "next_steps",
            "Analyzing progress and determining next actions"
        )
        
        self._set_stage("Next Steps", "Analyzing progress and determining next actions", 3)
        self._stream_output(f"🎯 Focus: {self.focus}", "info")
        self._stream_output("→ Generating next steps...", "info")
        
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
        
        self._update_progress()
        
        try:
            response = ""
            for chunk in self._stream_llm_with_thought_broadcast(self.agent.deep_llm, prompt):
                response += chunk
            
            self._update_progress()
            self._stream_output("✅ Next steps generated", "success")
            
        except Exception as e:
            self._stream_output(f"❌ Error: {str(e)}", "error")
            response = f"Error: {str(e)}"
        
        steps = self._parse_json_response(response)
        
        self._update_progress()
        self._stream_output(f"📊 Generated {len(steps)} next steps", "success")
        
        # Create step nodes and link to stage
        for idx, step in enumerate(steps, 1):
            step_id = f"next_step_{stage_id}_{idx}"
            
            self.hybrid_memory.upsert_entity(
                entity_id=step_id,
                etype="next_step",
                labels=["NextStep", "FocusBoardItem"],
                properties={
                    "text": step,
                    "category": "next_steps",
                    "index": idx,
                    "stage_id": stage_id,
                    "iteration_id": self.current_iteration_id,
                    "project_id": self.project_id,
                    "session_id": self.agent.sess.id if hasattr(self.agent, 'sess') else None,
                    "created_at": datetime.utcnow().isoformat()
                }
            )
            
            self.hybrid_memory.link(stage_id, step_id, "GENERATED", {"index": idx})
            
            # Add to vector store
            self.hybrid_memory.vec.add_texts(
                collection="long_term_docs",
                ids=[step_id],
                texts=[step],
                metadatas=[{
                    "type": "next_step",
                    "stage_id": stage_id,
                    "project_id": self.project_id,
                    "session_id": self.agent.sess.id if hasattr(self.agent, 'sess') else None
                }]
            )
            
            # Extract resources
            self._extract_and_link_resources(step, step_id)
            
            self.add_to_focus_board("next_steps", step)
            self._stream_output(f"  {idx}. {step[:100]}{'...' if len(step) > 100 else ''}", "info")
        
        self._complete_stage_node(output=response, output_count=len(steps))
        self._clear_stage()
        
        return steps
    
    def generate_actions(self, context: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Generate high-level actionable goals for the toolchain planner to decompose.
        
        Instead of specifying which tools to use (that's the planner's job),
        this produces goal descriptions with priority and success criteria
        that get fed into the toolchain planner one-by-one.
        """
        if not self.focus:
            return []

        # Create stage node
        stage_id = self._create_stage_node(
            "Goal Planning",
            "actions",
            "Analyzing state and defining actionable goals for toolchain execution"
        )

        self._set_stage("Goal Planning", "Defining actionable goals for toolchain execution", 4)
        self._stream_output(f"🎯 Focus: {self.focus}", "info")

        # Gather available tool names for context (planner will select, not the prompt)
        available_tools = [tool.name for tool in self.agent.tools]
        self._stream_output(
            f"🔧 Available tools ({len(available_tools)}): "
            f"{', '.join(available_tools[:8])}{'...' if len(available_tools) > 8 else ''}",
            "info"
        )
        self._update_progress()

        prompt = f"""
    Project Focus: {self.focus}

    Current Focus Board State:
    - Progress: {json.dumps(self.focus_board.get('progress', [])[-5:], indent=2)}
    - Next Steps: {json.dumps(self.focus_board.get('next_steps', [])[-5:], indent=2)}
    - Issues: {json.dumps(self.focus_board.get('issues', [])[-5:], indent=2)}
    - Ideas: {json.dumps(self.focus_board.get('ideas', [])[-5:], indent=2)}

    Available Tools (for context only - do NOT specify which tools to use):
    {available_tools}

    {f"Additional Context: {context}" if context else ""}

    Generate 3-5 high-level GOALS that advance this project. Each goal should be:
    - Self-contained and achievable in a single toolchain execution
    - Described clearly enough for an AI planner to decompose into tool steps
    - Prioritized by impact

    Do NOT specify which tools to use - the toolchain planner will handle tool selection.

    Respond with a JSON array of objects, each with:
    - "goal": A clear, detailed description of what needs to be accomplished
    - "priority": "high", "medium", or "low"
    - "success_criteria": What a successful result looks like
    - "context": Any additional context the planner needs (relevant file paths, URLs, etc.)

    Example:
    [
    {{
        "goal": "Scan the project repository for any Python files with syntax errors and report findings",
        "priority": "high",
        "success_criteria": "A list of files with errors and the specific issues found",
        "context": "Repository is at /home/user/project"
    }}
    ]
    """

        self._stream_output("⚡ Generating high-level goals for toolchain planner...", "info")
        self._update_progress()

        try:
            response = ""
            for chunk in self._stream_llm_with_thought_broadcast(self.agent.deep_llm, prompt):
                response += chunk

            self._update_progress()

        except Exception as e:
            self._stream_output(f"❌ Error: {str(e)}", "error")
            response = f"Error: {str(e)}"

        # Parse goals
        try:
            goals = json.loads(response.strip().strip('```json').strip('```').strip())
            if not isinstance(goals, list):
                goals = [goals]
            # Normalize structure
            normalized = []
            for g in goals:
                if isinstance(g, str):
                    normalized.append({
                        "goal": g,
                        "priority": "medium",
                        "success_criteria": "",
                        "context": ""
                    })
                elif isinstance(g, dict):
                    normalized.append({
                        "goal": g.get("goal", g.get("description", str(g))),
                        "priority": g.get("priority", "medium"),
                        "success_criteria": g.get("success_criteria", ""),
                        "context": g.get("context", "")
                    })
                else:
                    normalized.append({
                        "goal": str(g),
                        "priority": "medium",
                        "success_criteria": "",
                        "context": ""
                    })
            goals = normalized
        except (json.JSONDecodeError, ValueError):
            # Fallback: treat entire response as a single goal
            goals = [{
                "goal": response.strip(),
                "priority": "medium",
                "success_criteria": "",
                "context": ""
            }]

        self._update_progress()
        self._stream_output(f"📊 Generated {len(goals)} goals", "success")

        # Create goal nodes and link to stage
        for idx, goal in enumerate(goals, 1):
            goal_text = goal.get("goal", "")
            priority = goal.get("priority", "medium")
            goal_id = f"goal_{stage_id}_{idx}"

            if self.hybrid_memory:
                self.hybrid_memory.upsert_entity(
                    entity_id=goal_id,
                    etype="goal",
                    labels=["Goal", "FocusBoardItem", priority.capitalize()],
                    properties={
                        "text": goal_text,
                        "category": "actions",
                        "index": idx,
                        "priority": priority,
                        "success_criteria": goal.get("success_criteria", ""),
                        "goal_context": goal.get("context", ""),
                        "stage_id": stage_id,
                        "iteration_id": self.current_iteration_id,
                        "project_id": self.project_id,
                        "session_id": self.agent.sess.id if hasattr(self.agent, 'sess') else None,
                        "created_at": datetime.utcnow().isoformat()
                    }
                )

                self.hybrid_memory.link(stage_id, goal_id, "GENERATED", {"index": idx, "priority": priority})

                # Add to vector store
                self.hybrid_memory.vec.add_texts(
                    collection="long_term_docs",
                    ids=[goal_id],
                    texts=[goal_text],
                    metadatas=[{
                        "type": "goal",
                        "priority": priority,
                        "stage_id": stage_id,
                        "project_id": self.project_id,
                        "session_id": self.agent.sess.id if hasattr(self.agent, 'sess') else None
                    }]
                )

                # Extract resources from goal text and context
                self._extract_and_link_resources(goal_text, goal_id)
                if goal.get("context"):
                    self._extract_and_link_resources(goal["context"], goal_id)

            # Store the full goal dict as metadata so execute_actions_stage can use it
            self.add_to_focus_board("actions", goal_text, metadata=goal)

            priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(priority, "⚪")
            self._stream_output(
                f"  {priority_emoji} {idx}. {goal_text[:120]}{'...' if len(goal_text) > 120 else ''}",
                "info"
            )
            if goal.get("success_criteria"):
                self._stream_output(f"     ✓ Success: {goal['success_criteria'][:100]}", "info")

        # Complete stage
        self._complete_stage_node(output=response, output_count=len(goals))
        self._clear_stage()

        return goals


    def _build_toolchain_query(self, goal: str, priority: str, 
                            success_criteria: str, goal_context: str) -> str:
        """
        Build a structured query for the toolchain planner.
        
        The planner uses this to decompose the goal into a sequence of
        tool steps with proper inputs (including multi-parameter dicts).
        """
        # Gather recent focus board state for context
        recent_progress = self.focus_board.get('progress', [])[-3:]
        recent_issues = self.focus_board.get('issues', [])[-3:]

        query = f"""Project: {self.focus}

    GOAL: {goal}

    Priority: {priority}
    {f"Success Criteria: {success_criteria}" if success_criteria else ""}
    {f"Additional Context: {goal_context}" if goal_context else ""}

    Recent Progress:
    {json.dumps([p.get('note', '') if isinstance(p, dict) else str(p) for p in recent_progress], indent=2)}

    Known Issues:
    {json.dumps([i.get('note', '') if isinstance(i, dict) else str(i) for i in recent_issues], indent=2)}

    INSTRUCTIONS FOR PLANNER:
    - Decompose this goal into concrete tool steps
    - For tools requiring multiple parameters, provide input as a JSON object
    - Use {{prev}} to reference the previous step's output
    - Use {{step_N}} to reference step N's output
    - Each step should have "tool" (tool name) and "input" (string or JSON object)
    """
        return query

    def handoff_to_toolchain(self, action: Dict[str, Any]) -> Optional[str]:
        """
        Hand off a goal to the toolchain via the orchestrator task system.
        
        Flow:
        1. Build a goal query from the action dict
        2. Submit to orchestrator as 'toolchain.execute' task
        3. The orchestrator routes to the registered task which uses the
        EnhancedMonitoredToolChainPlanner (handles multi-param tools)
        4. Track execution in graph, collect streaming results
        
        Args:
            action: Dict with 'goal'/'description', 'priority', 'success_criteria', 'context'
        
        Returns:
            Execution result string or None on failure
        """
        # Normalize the action dict
        goal = action.get('goal', action.get('description', str(action)))
        priority = action.get('priority', 'medium')
        success_criteria = action.get('success_criteria', '')
        goal_context = action.get('context', '')

        # Create execution stage node
        stage_id = self._create_stage_node(
            "Goal Execution",
            "execution",
            f"Executing: {goal[:80]}..."
        )

        self._set_stage("Goal Execution", f"Executing: {goal[:80]}...", 3)
        self._stream_output("▶️ Starting goal execution via orchestrator", "info")
        self._stream_output(f"📋 Goal: {goal}", "info")

        priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(priority, "⚪")
        self._stream_output(f"   Priority: {priority_emoji} {priority}", "info")

        if success_criteria:
            self._stream_output(f"   Success criteria: {success_criteria}", "info")

        # Build the query for the toolchain planner
        # This is what the planner receives to decompose into tool steps
        query = self._build_toolchain_query(goal, priority, success_criteria, goal_context)

        # Create execution tracking node in graph
        execution_id = None
        if self.hybrid_memory:
            execution_id = self.hybrid_memory.create_tool_execution_node(
                node_id=stage_id,
                tool_name="toolchain_orchestrated",
                metadata={
                    "executed_at": datetime.utcnow().isoformat(),
                    "goal": goal[:500],
                    "priority": priority,
                    "success_criteria": success_criteria,
                    "session_id": self.agent.sess.id if hasattr(self.agent, 'sess') else None,
                    "iteration_id": self.current_iteration_id,
                    "project_id": self.project_id
                }
            )

        result = ""
        chunk_count = 0
        start_time = time.time()
        line_buffer = ""

        def flush_line_buffer():
            nonlocal line_buffer
            if line_buffer:
                self._stream_output(f"  {line_buffer}", "info")
                line_buffer = ""

        try:
            self._stream_output("🔄 Submitting to orchestrator (toolchain.execute)...", "info")
            self._stream_output("─" * 60, "info")
            self._update_progress()

            # ── Route through orchestrator ──
            # The orchestrator dispatches to the registered 'toolchain.execute' task
            # which wraps the EnhancedMonitoredToolChainPlanner with multi-param support
            task_result = self._execute_goal_via_orchestrator(query)

            if task_result is None:
                # Orchestrator not available, fall back to direct execution
                self._stream_output("⚠️ Orchestrator unavailable, using direct toolchain", "warning")
                task_result = self._execute_goal_direct(query)

            # Process the result (may be a generator or a string)
            try:
                for chunk in task_result:
                    chunk_str = str(chunk) if not isinstance(chunk, str) else chunk
                    result += chunk_str
                    chunk_count += 1

                    for char in chunk_str:
                        if char == '\n':
                            flush_line_buffer()
                        else:
                            line_buffer += char

                    if chunk_count % 100 == 0 and line_buffer:
                        self._stream_output(f"  {line_buffer}...", "info")
                        self._stream_output(f"  📊 [{chunk_count} chunks, {len(result)} chars]", "info")

            except TypeError:
                # Not iterable - single result
                result = str(task_result) if task_result else ""

            flush_line_buffer()
            self._stream_output("─" * 60, "info")
            self._update_progress()

            duration_ms = int((time.time() - start_time) * 1000)
            self._stream_output(f"✅ Execution complete ({chunk_count} chunks, {duration_ms}ms)", "success")

            # Create result node and extract resources
            if self.hybrid_memory and execution_id:
                result_id = self.hybrid_memory.create_tool_result_node(
                    execution_id=execution_id,
                    output=result,
                    metadata={
                        "tool_name": "toolchain_orchestrated",
                        "chunks_received": chunk_count,
                        "duration_ms": duration_ms,
                        "goal": goal[:500]
                    }
                )

                resources = self._extract_and_link_resources(result, result_id)
                self._stream_output(
                    f"📊 Extracted {len(resources['urls'])} URLs and "
                    f"{len(resources['filepaths'])} filepaths",
                    "info"
                )

            # Update focus board
            self.add_to_focus_board("progress", f"Completed goal: {goal[:200]}")

            if result and result.strip():
                result_summary = result[:500] + "..." if len(result) > 500 else result
                self.add_to_focus_board("progress", f"Result: {result_summary}")

            # Check against success criteria
            if success_criteria and result:
                self._evaluate_success(goal, success_criteria, result, stage_id)

            # Complete stage
            self._complete_stage_node(output=result, output_count=1)
            self._update_progress()
            self._clear_stage()

            return result

        except Exception as e:
            flush_line_buffer()
            error_msg = f"Goal execution failed: {e}"
            self._stream_output(f"❌ {error_msg}", "error")

            self.add_to_focus_board("issues", f"Failed: {goal[:100]} - {e}")
            self._complete_stage_node(output=error_msg, output_count=0)
            self._clear_stage()

            return None


    def _execute_goal_direct(self, query: str):
        """
        Direct toolchain execution fallback.
        Uses the toolchain planner directly (still benefits from
        EnhancedMonitoredToolChainPlanner if it's been wrapped).
        """
        self._stream_output("🔄 Direct toolchain execution (no orchestrator)...", "info")

        if self.hybrid_memory:
            # Use execution tracking context if available
            execution_id = f"direct_exec_{int(time.time())}"
            try:
                execution_id = self.hybrid_memory.create_tool_execution_node(
                    node_id=execution_id,
                    tool_name="toolchain_direct",
                    metadata={
                        "executed_at": datetime.utcnow().isoformat(),
                        "session_id": self.agent.sess.id if hasattr(self.agent, 'sess') else None,
                        "project_id": self.project_id
                    }
                )

                with self.hybrid_memory.track_execution(execution_id):
                    yield from self.agent.toolchain.execute_tool_chain(query)
                return

            except Exception:
                pass

        # Bare fallback
        yield from self.agent.toolchain.execute_tool_chain(query)
            
    def _execute_goal_via_orchestrator(self, query: str):
        """
        Execute a goal query through the orchestrator task system.
        FIXED: Properly handle task IDs and poll for results
        """
        # Check if orchestrator is available
        if not hasattr(self.agent, 'orchestrator') or not self.agent.orchestrator:
            self._stream_output("⚠️ No orchestrator available", "warning")
            return None

        orchestrator = self.agent.orchestrator

        # Check if the orchestrator has task submission capability
        if hasattr(orchestrator, 'submit_task'):
            try:
                # Submit as a toolchain.execute task
                task_result = orchestrator.submit_task(
                    "toolchain.execute",
                    self.agent,
                    query,
                    expert=False
                )

                # ── FIX: Check if we got a task ID (UUID string) ──
                if isinstance(task_result, str) and len(task_result) == 36 and '-' in task_result:
                    # This is a task ID, we need to poll for results
                    self._stream_output(f"📋 Task submitted: {task_result}", "info")
                    
                    # Import task polling utilities
                    from Vera.ChatUI.api.session import toolchain_executions
                    
                    # Poll for results with streaming
                    max_wait = 300  # 5 minutes max
                    poll_interval = 0.5  # Check every 500ms
                    elapsed = 0
                    
                    while elapsed < max_wait:
                        # Check if task has results
                        if task_result in toolchain_executions:
                            execution = toolchain_executions[task_result]
                            
                            # Check if there are chunks available
                            if hasattr(execution, 'chunks') and execution.chunks:
                                # Stream accumulated chunks
                                for chunk in execution.chunks:
                                    yield chunk
                                
                                # Check if task is complete
                                if hasattr(execution, 'completed') and execution.completed:
                                    return
                            
                            # Check if there's a final result
                            if hasattr(execution, 'result'):
                                if isinstance(execution.result, str):
                                    yield execution.result
                                return
                        
                        # Wait before next poll
                        time.sleep(poll_interval)
                        elapsed += poll_interval
                    
                    # Timeout
                    self._stream_output("⚠️ Task polling timeout", "warning")
                    yield f"Task {task_result} timed out after {max_wait}s"
                    return

                # If it's iterable (generator/list), yield from it
                elif hasattr(task_result, '__iter__') or hasattr(task_result, '__next__'):
                    yield from task_result
                    return
                
                # If it's a future-like object
                elif hasattr(task_result, 'result'):
                    result = task_result.result()
                    if hasattr(result, '__iter__'):
                        yield from result
                    else:
                        yield str(result)
                    return
                
                # Direct result
                else:
                    yield str(task_result)
                    return

            except Exception as e:
                self._stream_output(f"⚠️ Orchestrator submit failed: {e}", "warning")
                return None

        elif hasattr(orchestrator, 'execute_task'):
            # Alternative: synchronous task execution
            try:
                result = orchestrator.execute_task(
                    "toolchain.execute",
                    self.agent,
                    query
                )
                
                # Same UUID check
                if isinstance(result, str) and len(result) == 36 and '-' in result:
                    self._stream_output("⚠️ Got task ID from execute_task, cannot stream", "warning")
                    yield f"Task submitted: {result} (streaming not available)"
                elif hasattr(result, '__iter__'):
                    yield from result
                else:
                    yield str(result)
                return
                
            except Exception as e:
                self._stream_output(f"⚠️ Orchestrator execute failed: {e}", "warning")
                return None

        elif hasattr(orchestrator, 'run'):
            try:
                result = orchestrator.run("toolchain.execute", query=query)
                if isinstance(result, str) and len(result) == 36 and '-' in result:
                    yield f"Task submitted: {result}"
                elif hasattr(result, '__iter__'):
                    yield from result
                else:
                    yield str(result)
                return
            except Exception as e:
                self._stream_output(f"⚠️ Orchestrator run failed: {e}", "warning")
                return None

        else:
            self._stream_output("⚠️ Orchestrator has no known execution method", "warning")
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

    def trigger_proactive_thought(self):
        """
        Manually trigger a single proactive thought generation.
        This runs in the current thread and returns the thought.
        """
        if not self.focus:
            print("[FocusManager] Cannot generate thought: No focus set")
            return None
        
        print("[FocusManager] Manually triggered proactive thought generation...")
        
        # Generate proactive thought with streaming
        proactive_thought = self._generate_proactive_thought_streaming()
        
        if proactive_thought:
            # Add to focus board
            self.add_to_focus_board("actions", proactive_thought)
            
            # Evaluate if actionable
            evaluation_prompt = f"""
            Evaluate this proactive thought: {proactive_thought}
            
            Is it actionable given the tools available and relevant to the current focus?
            Tools available: {[tool.name for tool in self.agent.tools]}
            Focus: {self.focus}
            
            If actionable, respond with 'YES'. If not, respond with 'NO' and brief reason.
            """
            
            try:
                evaluation = self.agent.fast_llm.invoke(evaluation_prompt)
                
                if evaluation.strip().lower().startswith("yes"):
                    self._broadcast_sync("proactive_executing", {"thought": proactive_thought})
                    print(f"[FocusManager] Thought deemed actionable, executing...")
                    self.execute_goal_with_vera(proactive_thought)
                else:
                    print(f"[FocusManager] Thought not actionable: {evaluation}")
                    self._broadcast_sync("proactive_thought_generated", {
                        "thought": proactive_thought,
                        "actionable": False,
                        "reason": evaluation
                    })
            except Exception as e:
                print(f"[FocusManager] Error evaluating thought: {e}")
            
            return proactive_thought
        
        return None
    
    def trigger_proactive_thought_async(self):
        """
        Trigger proactive thought generation in a background thread.
        Returns immediately without blocking.
        """
        import threading
        
        def run():
            self.trigger_proactive_thought()
        
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        print("[FocusManager] Started proactive thought generation in background")
    
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
            # Use universal streaming wrapper
            for chunk in self._stream_llm_with_thought_broadcast(self.agent.deep_llm, prompt):
                self.current_thought += chunk
                
                # Also broadcast as thought chunk for compatibility
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
            import traceback
            traceback.print_exc()
            
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
                      auto_execute: bool = True,
                      explore_frequency: int = 2,  # Explore every N iterations
                      synthesize_frequency: int = 2):  # Synthesize every N iterations
        """Enhanced iterative workflow with exploration and synthesis"""
        self.workflow_active = True
        iteration = 0

        self._stream_output("=" * 60, "info")
        self._stream_output("🚀 PROACTIVE FOCUS WORKFLOW STARTED", "success")
        self._stream_output("=" * 60, "info")
        self._stream_output(f"📋 Configuration:", "info")
        self._stream_output(f"   • Max iterations: {max_iterations or 'Infinite'}", "info")
        self._stream_output(f"   • Interval: {iteration_interval}s", "info")
        self._stream_output(f"   • Auto-execute: {auto_execute}", "info")
        self._stream_output(f"   • Exploration: Every {explore_frequency} iterations", "info")
        self._stream_output(f"   • Synthesis: Every {synthesize_frequency} iterations", "info")
        self._stream_output(f"   • Focus: {self.focus}", "info")

        has_orchestrator = hasattr(self.agent, 'orchestrator') and self.agent.orchestrator
        self._stream_output(
            f"   • Orchestrator: {'✓ available' if has_orchestrator else '✗ unavailable (direct mode)'}",
            "info"
        )
        self._stream_output("=" * 60 + "\n", "info")

        # Ensure project structure exists
        try:
            project_root = self._ensure_project_structure()
            self._stream_output(f"📁 Project directory: {project_root}", "success")
        except Exception as e:
            self._stream_output(f"⚠️ Could not create project structure: {e}", "warning")

        while (max_iterations is None or iteration < max_iterations) and self.workflow_active:
            iteration += 1

            # Create iteration node
            iteration_id = self._create_iteration_node()

            self._stream_output("\n" + "=" * 60, "info")
            self._stream_output(f"🔄 ITERATION {iteration}", "info")
            self._stream_output("=" * 60 + "\n", "info")

            try:
                # Step 1: State review
                state_summary = self._review_current_state()
                self._stream_output(f"📊 State: {state_summary}", "info")

                # Step 2: Exploratory thinking (every N iterations)
                if iteration % explore_frequency == 0:
                    self._stream_output("\n🔍 EXPLORATION PHASE", "info")
                    exploration_depth = "deep" if iteration % (explore_frequency * 2) == 0 else "medium"
                    discoveries = self.explore_and_discover(
                        context=state_summary,
                        exploration_depth=exploration_depth
                    )
                    time.sleep(2)

                # Step 3: Ideas (every 3 iterations or after exploration)
                if iteration % 3 == 0 or iteration % explore_frequency == 0:
                    self._stream_output("\n💡 Generating ideas...", "info")
                    ideas = self.generate_ideas(context=state_summary)
                    time.sleep(2)

                # Step 4: Next steps
                self._stream_output("\n→ Generating next steps...", "info")
                steps = self.generate_next_steps(context=state_summary)
                time.sleep(2)

                # Step 5: Generate goals
                self._stream_output("\n⚡ Generating goals for toolchain planner...", "info")
                goals = self.generate_actions(context=state_summary)
                time.sleep(2)

                # Step 6: Execute goals
                if auto_execute and goals:
                    self._stream_output("\n▶️ Executing high-priority goals...", "info")
                    executed = self.execute_actions_stage(max_executions=2, priority_filter="high")
                    self._stream_output(f"✅ Executed {executed} goals", "success")

                    if executed == 0:
                        self._stream_output("→ No high-priority goals, trying medium...", "info")
                        executed = self.execute_actions_stage(max_executions=1, priority_filter="medium")
                        self._stream_output(f"✅ Executed {executed} medium-priority goals", "success")

                # Step 7: Learning synthesis (every N iterations)
                if iteration % synthesize_frequency == 0:
                    self._stream_output("\n🧠 SYNTHESIS PHASE", "info")
                    synthesis = self.synthesize_learnings(lookback_iterations=synthesize_frequency)
                    time.sleep(2)

                # Step 8: Save checkpoint
                checkpoint = self.save_focus_board()
                self._stream_output(f"💾 Checkpoint saved: {checkpoint}", "success")

                # Step 9: Write iteration summary to project
                iteration_summary = self._format_iteration_summary(
                    iteration, state_summary,
                    executed_count=executed if auto_execute else 0
                )
                self._write_to_project(
                    iteration_summary,
                    "reports",
                    f"iteration_{iteration:03d}.md"
                )

                # Complete iteration
                self._complete_iteration_node(summary=state_summary)

                # Wait for next iteration
                if max_iterations is None or iteration < max_iterations:
                    self._stream_output(
                        f"\n⏳ Waiting {iteration_interval}s until next iteration...",
                        "info"
                    )
                    time.sleep(iteration_interval)

            except Exception as e:
                self._stream_output(f"\n❌ Error in iteration {iteration}: {str(e)}", "error")
                import traceback
                traceback.print_exc()

                # Mark iteration as failed
                if self.current_iteration_id and self.hybrid_memory:
                    with self.hybrid_memory.graph._driver.session() as sess:
                        sess.run("""
                            MATCH (i:WorkflowIteration {id: $id})
                            SET i.status = 'failed',
                                i.error = $error,
                                i.completed_at = $completed_at
                        """, {
                            "id": self.current_iteration_id,
                            "error": str(e),
                            "completed_at": datetime.utcnow().isoformat()
                        })

                time.sleep(30)

        self.workflow_active = False
        self._stream_output("\n" + "=" * 60, "info")
        self._stream_output(f"✅ WORKFLOW COMPLETED - {iteration} iterations", "success")
        self._stream_output("=" * 60, "info")

    def _format_iteration_summary(self, iteration: int, state_summary: str, 
                                executed_count: int = 0) -> str:
        """Format iteration summary as markdown."""
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        return f"""# Iteration {iteration} Summary

    **Timestamp:** {timestamp}
    **Project:** {self.focus}
    **State:** {state_summary}
    **Goals Executed:** {executed_count}

    ## Focus Board State

    ### Progress ({len(self.focus_board.get('progress', []))})
    {chr(10).join(f"- {p.get('note', str(p))[:100]}" for p in self.focus_board.get('progress', [])[-5:])}

    ### Next Steps ({len(self.focus_board.get('next_steps', []))})
    {chr(10).join(f"- {s.get('note', str(s))[:100]}" for s in self.focus_board.get('next_steps', [])[-5:])}

    ### Issues ({len(self.focus_board.get('issues', []))})
    {chr(10).join(f"- {i.get('note', str(i))[:100]}" for i in self.focus_board.get('issues', []))}

    ---

    *Iteration {iteration} completed*
    """
        self._stream_output("=" * 60 + "\n", "info")

        while (max_iterations is None or iteration < max_iterations) and self.workflow_active:
            iteration += 1

            # Create iteration node
            iteration_id = self._create_iteration_node()

            self._stream_output("\n" + "=" * 60, "info")
            self._stream_output(f"🔄 ITERATION {iteration}", "info")
            self._stream_output("=" * 60 + "\n", "info")

            try:
                # Step 1: State review
                state_summary = self._review_current_state()
                self._stream_output(f"📊 State: {state_summary}", "info")

                # Step 2: Ideas (every 3 iterations)
                if iteration % 3 == 0:
                    self._stream_output("\n💡 Generating ideas...", "info")
                    ideas = self.generate_ideas(context=state_summary)
                    time.sleep(2)

                # Step 3: Next steps
                self._stream_output("\n→ Generating next steps...", "info")
                steps = self.generate_next_steps(context=state_summary)
                time.sleep(2)

                # Step 4: Generate goals (not tool-specific actions)
                self._stream_output("\n⚡ Generating goals for toolchain planner...", "info")
                goals = self.generate_actions(context=state_summary)
                time.sleep(2)

                # Step 5: Execute goals via orchestrator
                if auto_execute and goals:
                    self._stream_output("\n▶️ Executing high-priority goals via orchestrator...", "info")
                    executed = self.execute_actions_stage(max_executions=2, priority_filter="high")
                    self._stream_output(f"✅ Executed {executed} goals", "success")

                    # If no high-priority goals were executed, try medium
                    if executed == 0:
                        self._stream_output("→ No high-priority goals, trying medium...", "info")
                        executed = self.execute_actions_stage(max_executions=1, priority_filter="medium")
                        self._stream_output(f"✅ Executed {executed} medium-priority goals", "success")

                # Step 6: Save checkpoint
                checkpoint = self.save_focus_board()
                self._stream_output(f"💾 Checkpoint saved: {checkpoint}", "success")

                # Complete iteration
                self._complete_iteration_node(summary=state_summary)

                # Wait for next iteration
                if max_iterations is None or iteration < max_iterations:
                    self._stream_output(
                        f"\n⏳ Waiting {iteration_interval}s until next iteration...",
                        "info"
                    )
                    time.sleep(iteration_interval)

            except Exception as e:
                self._stream_output(f"\n❌ Error in iteration {iteration}: {str(e)}", "error")
                import traceback
                traceback.print_exc()

                # Mark iteration as failed
                if self.current_iteration_id and self.hybrid_memory:
                    with self.hybrid_memory.graph._driver.session() as sess:
                        sess.run("""
                            MATCH (i:WorkflowIteration {id: $id})
                            SET i.status = 'failed',
                                i.error = $error,
                                i.completed_at = $completed_at
                        """, {
                            "id": self.current_iteration_id,
                            "error": str(e),
                            "completed_at": datetime.utcnow().isoformat()
                        })

                time.sleep(30)

        self.workflow_active = False
        self._stream_output("\n" + "=" * 60, "info")
        self._stream_output(f"✅ WORKFLOW COMPLETED - {iteration} iterations", "success")
        self._stream_output("=" * 60, "info")
        
    def iterative_workflow_old(self, max_iterations: Optional[int] = None, 
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
                        # Parse action to ensure it's a dict
                        if isinstance(action, dict):
                            action_dict = action
                        elif isinstance(action, str):
                            try:
                                # Try to parse JSON string
                                import json
                                action_dict = json.loads(action)
                            except:
                                # Create minimal action dict
                                action_dict = {
                                    'description': action,
                                    'priority': 'medium',
                                    'tools': []
                                }
                        else:
                            # Skip invalid actions
                            print(f"[FocusManager] Skipping invalid action: {type(action)}")
                            continue
                        
                        priority = action_dict.get('priority', 'medium')
                        description = action_dict.get('description', str(action_dict))
                        
                        print(f"[FocusManager] Action priority={priority}, description={description[:50]}...")
                        
                        if priority == 'high' and executed_count < 2:  # Limit to 2 per iteration
                            print(f"[FocusManager] Executing high-priority action: {description}")
                            self.handoff_to_toolchain(action_dict)
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
                import traceback
                traceback.print_exc()
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
    
    # Add individual workflow stage methods for granular control
    def generate_ideas_stage(self, context: Optional[str] = None):
        """Run just the ideas generation stage."""
        print("[FocusManager] Running ideas generation stage...")
        self._broadcast_sync("stage_started", {"stage": "ideas"})
        
        try:
            ideas = self.generate_ideas(context=context)
            self._broadcast_sync("stage_completed", {
                "stage": "ideas",
                "count": len(ideas)
            })
            return ideas
        except Exception as e:
            print(f"[FocusManager] Ideas stage error: {e}")
            self._broadcast_sync("stage_error", {"stage": "ideas", "error": str(e)})
            return []
    
    def generate_next_steps_stage(self, context: Optional[str] = None):
        """Run just the next steps generation stage."""
        print("[FocusManager] Running next steps generation stage...")
        self._broadcast_sync("stage_started", {"stage": "next_steps"})
        
        try:
            steps = self.generate_next_steps(context=context)
            self._broadcast_sync("stage_completed", {
                "stage": "next_steps",
                "count": len(steps)
            })
            return steps
        except Exception as e:
            print(f"[FocusManager] Next steps stage error: {e}")
            self._broadcast_sync("stage_error", {"stage": "next_steps", "error": str(e)})
            return []
    
    def generate_actions_stage(self, context: Optional[str] = None):
        """Run just the actions generation stage."""
        print("[FocusManager] Running actions generation stage...")
        self._broadcast_sync("stage_started", {"stage": "actions"})
        
        try:
            actions = self.generate_actions(context=context)
            self._broadcast_sync("stage_completed", {
                "stage": "actions",
                "count": len(actions)
            })
            return actions
        except Exception as e:
            print(f"[FocusManager] Actions stage error: {e}")
            self._broadcast_sync("stage_error", {"stage": "actions", "error": str(e)})
            return []
    
    def execute_actions_stage(self, max_executions: int = 2, priority_filter: str = "high"):
        """
        Execute goals from the focus board through the orchestrator.
        
        Each goal is submitted individually to the toolchain planner which:
        1. Decomposes the goal into a multi-step tool plan
        2. Executes each step (handling multi-parameter tools)
        3. Streams results back with WebSocket broadcasting
        
        Args:
            max_executions: Maximum number of goals to execute
            priority_filter: Only execute goals matching this priority ("high", "medium", "low", "all")
        
        Returns:
            Number of goals successfully executed
        """
        self._set_stage(
            "Goal Execution",
            f"Executing up to {max_executions} {priority_filter}-priority goals via orchestrator",
            max_executions + 1
        )
        self._stream_output("▶️ Starting goal execution pipeline...", "info")

        actions = self.focus_board.get("actions", [])

        if not actions:
            self._stream_output("⚠️ No goals to execute", "warning")
            self._clear_stage()
            return 0

        self._stream_output(f"Found {len(actions)} total goals in focus board", "info")
        self._update_progress()

        executed_count = 0
        skipped_count = 0

        for idx, action in enumerate(actions):
            if executed_count >= max_executions:
                remaining = len(actions) - idx
                self._stream_output(
                    f"✓ Reached max executions ({max_executions}), "
                    f"{remaining} goals remaining",
                    "success"
                )
                break

            # Check CPU before each execution
            cpu_usage = self._count_ollama_processes()
            if cpu_usage >= self.cpu_threshold:
                self._stream_output(
                    f"⚠️ CPU threshold reached ({cpu_usage:.1f}% >= {self.cpu_threshold}%), "
                    f"pausing execution",
                    "warning"
                )
                break

            try:
                # Parse the action item into a normalized goal dict
                goal_dict = self._parse_goal_item(action)
                priority = goal_dict.get('priority', 'medium')
                goal_text = goal_dict.get('goal', '')

                # Apply priority filter
                if priority_filter and priority_filter.lower() != 'all' and priority != priority_filter:
                    skipped_count += 1
                    continue

                priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(priority, "⚪")

                self._stream_output(
                    f"\n{'='*50}",
                    "info"
                )
                self._stream_output(
                    f"{priority_emoji} Goal {executed_count + 1}/{max_executions}: "
                    f"{goal_text[:150]}{'...' if len(goal_text) > 150 else ''}",
                    "info"
                )

                if goal_dict.get('success_criteria'):
                    self._stream_output(
                        f"   ✓ Success criteria: {goal_dict['success_criteria'][:100]}",
                        "info"
                    )

                # Execute via handoff (which routes through orchestrator)
                result = self.handoff_to_toolchain(goal_dict)

                if result:
                    self._stream_output(f"✅ Goal completed", "success")
                    result_preview = str(result)[:200]
                    self._stream_output(
                        f"   Result: {result_preview}{'...' if len(str(result)) > 200 else ''}",
                        "info"
                    )
                else:
                    self._stream_output(f"⚠️ Goal completed with no result", "warning")

                executed_count += 1
                self._update_progress()

            except Exception as e:
                self._stream_output(f"❌ Execution failed: {str(e)}", "error")
                import traceback
                traceback.print_exc()

        # Summary
        self._stream_output(f"\n{'='*50}", "info")
        self._stream_output(
            f"📊 Execution Summary: {executed_count}/{max_executions} goals completed, "
            f"{skipped_count} skipped (priority filter: {priority_filter})",
            "success"
        )
        self._clear_stage()

        return executed_count


    def _parse_goal_item(self, item) -> Dict[str, Any]:
        """
        Parse a focus board action item into a normalized goal dict.
        
        Handles all the messy formats that might be in the focus board:
        - Raw strings
        - Dicts with 'note' field (from add_to_focus_board)
        - Dicts with 'goal' or 'description' fields
        - JSON strings
        
        Returns:
            Dict with keys: goal, priority, success_criteria, context
        """
        default = {
            'goal': '',
            'priority': 'medium',
            'success_criteria': '',
            'context': ''
        }

        if isinstance(item, dict):
            # Check for direct goal fields
            if 'goal' in item:
                return {
                    'goal': item['goal'],
                    'priority': item.get('priority', 'medium'),
                    'success_criteria': item.get('success_criteria', ''),
                    'context': item.get('context', '')
                }

            if 'description' in item:
                return {
                    'goal': item['description'],
                    'priority': item.get('priority', 'medium'),
                    'success_criteria': item.get('success_criteria', ''),
                    'context': item.get('context', '')
                }

            # Focus board items have 'note' field
            if 'note' in item:
                note = item['note']
                metadata = item.get('metadata', {})

                # Metadata might contain the original goal dict
                if isinstance(metadata, dict) and 'goal' in metadata:
                    return {
                        'goal': metadata.get('goal', note),
                        'priority': metadata.get('priority', 'medium'),
                        'success_criteria': metadata.get('success_criteria', ''),
                        'context': metadata.get('context', '')
                    }

                # Try to parse note as JSON
                if isinstance(note, str):
                    note_clean = note.strip()
                    if note_clean.startswith('```'):
                        lines = note_clean.split('\n')
                        lines = lines[1:] if lines[0].startswith('```') else lines
                        if lines and lines[-1].strip() == '```':
                            lines = lines[:-1]
                        note_clean = '\n'.join(lines).strip()

                    try:
                        parsed = json.loads(note_clean)
                        if isinstance(parsed, dict):
                            return {
                                'goal': parsed.get('goal', parsed.get('description', note_clean)),
                                'priority': parsed.get('priority', 'medium'),
                                'success_criteria': parsed.get('success_criteria', ''),
                                'context': parsed.get('context', '')
                            }
                    except (json.JSONDecodeError, ValueError):
                        pass

                # Plain text note
                return {
                    'goal': str(note),
                    'priority': metadata.get('priority', 'medium') if isinstance(metadata, dict) else 'medium',
                    'success_criteria': '',
                    'context': ''
                }

            # Unknown dict format
            return {
                'goal': str(item),
                'priority': item.get('priority', 'medium'),
                'success_criteria': '',
                'context': ''
            }

        elif isinstance(item, str):
            # Try JSON parse
            stripped = item.strip()
            if stripped.startswith('```'):
                lines = stripped.split('\n')
                lines = lines[1:] if lines[0].startswith('```') else lines
                if lines and lines[-1].strip() == '```':
                    lines = lines[:-1]
                stripped = '\n'.join(lines).strip()

            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, dict):
                    return {
                        'goal': parsed.get('goal', parsed.get('description', stripped)),
                        'priority': parsed.get('priority', 'medium'),
                        'success_criteria': parsed.get('success_criteria', ''),
                        'context': parsed.get('context', '')
                    }
            except (json.JSONDecodeError, ValueError):
                pass

            return {
                'goal': item,
                'priority': 'medium',
                'success_criteria': '',
                'context': ''
            }

        else:
            return {
                'goal': str(item),
                'priority': 'medium',
                'success_criteria': '',
                'context': ''
            }

    
    def parseActionItem(self, item):
        """Parse an action item into a standard dict format."""
        print(f"[FocusManager] parseActionItem input type: {type(item)}")
        
        if isinstance(item, dict):
            # Already a dict, check if it has expected fields
            if 'description' in item:
                print(f"[FocusManager] Dict with description: {item.get('description', '')[:50]}")
                return {
                    'description': item.get('description', ''),
                    'tools': item.get('tools', []),
                    'priority': item.get('priority', 'medium'),
                    'metadata': item.get('metadata', {})
                }
            elif 'note' in item:
                # Try to parse note field
                note = item['note']
                print(f"[FocusManager] Dict with note field: {note[:100]}")
                
                # Remove markdown code fences if present
                if isinstance(note, str):
                    note = note.strip()
                    if note.startswith('```'):
                        lines = note.split('\n')
                        if lines[0].startswith('```'):
                            lines = lines[1:]
                        if lines and lines[-1].strip() == '```':
                            lines = lines[:-1]
                        note = '\n'.join(lines).strip()
                
                try:
                    parsed = json.loads(note)
                    print(f"[FocusManager] Parsed note as JSON: {parsed}")
                    if isinstance(parsed, dict) and 'description' in parsed:
                        return {
                            'description': parsed.get('description', ''),
                            'tools': parsed.get('tools', []),
                            'priority': parsed.get('priority', 'medium'),
                            'metadata': item.get('metadata', {})
                        }
                    elif isinstance(parsed, list) and len(parsed) > 0:
                        # If it's a list, take the first item
                        first_item = parsed[0]
                        if isinstance(first_item, dict):
                            return {
                                'description': first_item.get('description', str(first_item)),
                                'tools': first_item.get('tools', []),
                                'priority': first_item.get('priority', 'medium'),
                                'metadata': item.get('metadata', {})
                            }
                except json.JSONDecodeError as e:
                    print(f"[FocusManager] Note is not valid JSON: {e}")
                    # Treat note as plain text description
                    return {
                        'description': note,
                        'tools': [],
                        'priority': 'medium',
                        'metadata': item.get('metadata', {})
                    }
                
                # Fallback: use note as description
                return {
                    'description': note,
                    'tools': [],
                    'priority': 'medium',
                    'metadata': item.get('metadata', {})
                }
            else:
                # Convert entire dict to description
                print(f"[FocusManager] Dict without standard fields, converting to string")
                return {
                    'description': str(item),
                    'tools': [],
                    'priority': 'medium',
                    'metadata': {}
                }
                
        elif isinstance(item, str):
            print(f"[FocusManager] String item: {item[:100]}")
            
            # Remove markdown code fences
            item = item.strip()
            if item.startswith('```'):
                lines = item.split('\n')
                if lines[0].startswith('```'):
                    lines = lines[1:]
                if lines and lines[-1].strip() == '```':
                    lines = lines[:-1]
                item = '\n'.join(lines).strip()
            
            # Try to parse as JSON
            try:
                parsed = json.loads(item)
                print(f"[FocusManager] Parsed string as JSON: {type(parsed)}")
                
                if isinstance(parsed, dict):
                    return {
                        'description': parsed.get('description', str(parsed)),
                        'tools': parsed.get('tools', []),
                        'priority': parsed.get('priority', 'medium'),
                        'metadata': {}
                    }
                elif isinstance(parsed, list) and len(parsed) > 0:
                    first_item = parsed[0]
                    if isinstance(first_item, dict):
                        return {
                            'description': first_item.get('description', str(first_item)),
                            'tools': first_item.get('tools', []),
                            'priority': first_item.get('priority', 'medium'),
                            'metadata': {}
                        }
            except json.JSONDecodeError:
                print(f"[FocusManager] String is not JSON, using as plain description")
                pass
            
            # Return as simple action
            return {
                'description': item,
                'priority': 'medium',
                'tools': [],
                'metadata': {}
            }
        else:
            # Unknown type, convert to string
            print(f"[FocusManager] Unknown type {type(item)}, converting to string")
            return {
                'description': str(item),
                'priority': 'medium',
                'tools': [],
                'metadata': {}
            }
        
    def _evaluate_success(self, goal: str, success_criteria: str, result: str, stage_id: str):
        """
        Evaluate whether execution result meets the success criteria.
        Uses fast LLM for quick assessment.
        """
        try:
            eval_prompt = f"""Evaluate this execution result against the success criteria.

    Goal: {goal[:300]}
    Success Criteria: {success_criteria[:200]}
    Result (truncated): {result[:1000]}

    Did the result meet the success criteria? Respond with:
    - "YES" if criteria are met
    - "PARTIAL" if partially met
    - "NO" if not met

    Follow with a brief (1-2 sentence) explanation.
    """

            evaluation = ""
            for chunk in self._stream_llm_with_thought_broadcast(self.agent.fast_llm, eval_prompt):
                evaluation += chunk

            evaluation = evaluation.strip()

            if evaluation.upper().startswith("YES"):
                self._stream_output(f"✅ Success criteria MET: {evaluation[:100]}", "success")
                status = "met"
            elif evaluation.upper().startswith("PARTIAL"):
                self._stream_output(f"⚠️ Success criteria PARTIALLY met: {evaluation[:100]}", "warning")
                status = "partial"
            else:
                self._stream_output(f"❌ Success criteria NOT met: {evaluation[:100]}", "warning")
                self.add_to_focus_board("issues", f"Goal incomplete: {goal[:100]} - {evaluation[:200]}")
                status = "not_met"

            # Store evaluation in graph
            if self.hybrid_memory and stage_id:
                eval_id = f"eval_{stage_id}_{int(time.time())}"
                self.hybrid_memory.upsert_entity(
                    entity_id=eval_id,
                    etype="evaluation",
                    labels=["Evaluation", "SuccessCheck"],
                    properties={
                        "goal": goal[:500],
                        "success_criteria": success_criteria,
                        "evaluation": evaluation[:500],
                        "status": status,
                        "stage_id": stage_id,
                        "project_id": self.project_id,
                        "created_at": datetime.utcnow().isoformat()
                    }
                )
                self.hybrid_memory.link(stage_id, eval_id, "EVALUATED_BY", {})

        except Exception as e:
            self._stream_output(f"⚠️ Could not evaluate success criteria: {e}", "warning")

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

 
    def _set_stage(self, stage: str, activity: str = "", total_steps: int = 0):
        """Set current stage and broadcast update"""
        self.current_stage = stage
        self.current_activity = activity
        self.stage_progress = 0
        self.stage_total = total_steps
        
        print(f"[FocusManager] Stage: {stage} - {activity}")
        
        self._broadcast_sync("stage_update", {
            "stage": stage,
            "activity": activity,
            "progress": 0,
            "total": total_steps,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    def _update_progress(self, increment: int = 1):
        """Update stage progress and broadcast"""
        self.stage_progress += increment
        
        self._broadcast_sync("stage_progress", {
            "stage": self.current_stage,
            "progress": self.stage_progress,
            "total": self.stage_total,
            "percentage": (self.stage_progress / self.stage_total * 100) if self.stage_total > 0 else 0
        })
    
    def _stream_output(self, text: str, category: str = "info"):
        """Stream output text to UI"""
        self._broadcast_sync("stream_output", {
            "text": text,
            "category": category,  # info, success, warning, error
            "timestamp": datetime.utcnow().isoformat()
        })
    
    def _clear_stage(self):
        """Clear current stage"""
        self.current_stage = None
        self.current_activity = None
        self.stage_progress = 0
        self.stage_total = 0
        
        self._broadcast_sync("stage_cleared", {})

    def _stream_llm_with_thought_broadcast(self, llm, prompt: str):
        """
        Universal wrapper for LLM streaming that captures and broadcasts both:
        - LLM-level thoughts (<think> tags from reasoning models)
        - Response content
        
        This should be used by ALL generate functions.
        Thoughts are stripped from response and saved separately to memory.
        """
        response_buffer = ""
        thought_buffer = ""
        in_thought = False
        
        # Use Vera's thought polling wrapper if available
        if hasattr(self.agent, '_stream_with_thought_polling'):
            for chunk in self.agent._stream_with_thought_polling(llm, prompt):
                chunk_text = extract_chunk_text(chunk) if not isinstance(chunk, str) else chunk
                
                # Process chunk character by character to handle thought tags
                i = 0
                while i < len(chunk_text):
                    # Check for thought start
                    if chunk_text[i:i+9] == '<thought>':
                        in_thought = True
                        i += 9
                        
                        # Broadcast start of LLM thought
                        self._broadcast_sync("llm_thought_start", {
                            "timestamp": datetime.utcnow().isoformat()
                        })
                        continue
                    
                    # Check for thought end
                    if chunk_text[i:i+10] == '</thought>':
                        in_thought = False
                        i += 10
                        
                        # Broadcast end and save to memory
                        self._broadcast_sync("llm_thought_end", {
                            "timestamp": datetime.utcnow().isoformat()
                        })
                        
                        # Save thought to agent memory (NOT focus board)
                        if thought_buffer.strip() and hasattr(self.agent, 'mem'):
                            self.agent.mem.add_session_memory(
                                self.agent.sess.id,
                                thought_buffer.strip(),
                                "Thought",
                                {"source": "proactive_focus", "focus": self.focus}
                            )
                            print(f"[FocusManager] Saved thought to memory ({len(thought_buffer)} chars)")
                        
                        thought_buffer = ""  # Clear thought buffer
                        continue
                    
                    # Add character to appropriate buffer
                    if in_thought:
                        thought_buffer += chunk_text[i]
                        
                        # Broadcast thought chunk
                        self._broadcast_sync("llm_thought_chunk", {
                            "chunk": chunk_text[i],
                            "type": "llm_reasoning"
                        })
                    else:
                        response_buffer += chunk_text[i]
                        
                        # Broadcast response chunk
                        self._broadcast_sync("response_chunk", {
                            "chunk": chunk_text[i],
                            "accumulated": response_buffer
                        })
                        
                        yield chunk_text[i]
                    
                    i += 1
        
        else:
            # Fallback: Direct streaming without thought polling
            # Still try to strip thought tags if present
            for chunk in llm.stream(prompt):
                chunk_text = extract_chunk_text(chunk) if not isinstance(chunk, str) else chunk
                
                i = 0
                while i < len(chunk_text):
                    if chunk_text[i:i+9] == '<thought>':
                        in_thought = True
                        i += 9
                        continue
                    
                    if chunk_text[i:i+10] == '</thought>':
                        in_thought = False
                        i += 10
                        
                        # Save thought
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
                    else:
                        response_buffer += chunk_text[i]
                        yield chunk_text[i]
                    
                    i += 1
        
        return response_buffer
    
    def extract_chunk_text(chunk) -> str:
        """Extract text content from various chunk formats."""
        if isinstance(chunk, str):
            return chunk
        elif hasattr(chunk, 'content'):
            return chunk.content
        elif hasattr(chunk, 'text'):
            return chunk.text
        elif isinstance(chunk, dict):
            return chunk.get('content', chunk.get('text', str(chunk)))
        else:
            return str(chunk)





    # Add these methods to the ProactiveFocusManager class:

    def _ensure_project_structure(self) -> Path:
        """
        Create and return organized project directory structure.
        
        Returns:
            Path to project root directory
        """
        if not self.focus or not self.project_id:
            raise ValueError("No active focus/project")
        
        # Sanitize project name for filesystem
        safe_name = re.sub(r'[^\w\-_]', '_', self.focus)[:100]
        project_root = Path("./Output/Projects") / safe_name
        
        # Create subdirectories
        subdirs = [
            "insights",      # Exploratory discoveries and connections
            "syntheses",     # Synthesized learnings and patterns
            "reports",       # Progress reports and summaries
            "data/focus_boards",  # Focus board snapshots
            "data/graph_exports", # Graph data exports
            "logs",          # Workflow execution logs
            "resources",     # Extracted URLs and files references
            "actions"        # Action execution results
        ]
        
        for subdir in subdirs:
            (project_root / subdir).mkdir(parents=True, exist_ok=True)
        
        # Create project metadata file
        metadata_file = project_root / "project_metadata.json"
        if not metadata_file.exists():
            metadata = {
                "project_id": self.project_id,
                "focus": self.focus,
                "created_at": datetime.utcnow().isoformat(),
                "last_updated": datetime.utcnow().isoformat(),
                "iteration_count": 0
            }
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
        
        return project_root

    def _write_to_project(self, content: str, category: str, 
                        filename: Optional[str] = None,
                        append: bool = False) -> str:
        """
        Write content to organized project directory.
        
        Args:
            content: Text content to write
            category: Subdirectory (insights, syntheses, reports, logs, etc.)
            filename: Optional filename (auto-generated if None)
            append: Whether to append to existing file
            
        Returns:
            Path to written file
        """
        project_root = self._ensure_project_structure()
        
        # Generate filename if not provided
        if not filename:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            iter_suffix = f"_iter{self.iteration_count}" if self.iteration_count > 0 else ""
            filename = f"{category}_{timestamp}{iter_suffix}.md"
        
        filepath = project_root / category / filename
        
        # Write content
        mode = 'a' if append else 'w'
        with open(filepath, mode, encoding='utf-8') as f:
            if append:
                f.write("\n\n---\n\n")  # Separator for appended content
            f.write(content)
        
        # Update project metadata
        metadata_file = project_root / "project_metadata.json"
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        metadata["last_updated"] = datetime.utcnow().isoformat()
        metadata["iteration_count"] = max(metadata.get("iteration_count", 0), self.iteration_count)
        
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
        
        self._stream_output(f"📝 Wrote to: {filepath.relative_to(Path.cwd())}", "success")
        
        return str(filepath)

    def explore_and_discover(self, context: Optional[str] = None, 
                            exploration_depth: str = "deep") -> Dict[str, List[str]]:
        """
        Exploratory thought stage - wander through ideas, make connections,
        generate insights across multiple dimensions.
        
        Args:
            context: Additional context for exploration
            exploration_depth: "quick", "medium", or "deep"
            
        Returns:
            Dict with categories of discoveries: insights, connections, questions, hypotheses
        """
        if not self.focus:
            return {}
        
        # Create stage node
        stage_id = self._create_stage_node(
            "Exploratory Discovery",
            "exploration",
            "Wandering through problem space, making connections, generating insights"
        )
        
        self._set_stage("Exploratory Discovery", "Deep exploration of problem space", 5)
        self._stream_output("=" * 60, "info")
        self._stream_output("🔍 EXPLORATORY DISCOVERY STAGE", "info")
        self._stream_output("=" * 60, "info")
        self._stream_output(f"🎯 Focus: {self.focus}", "info")
        self._stream_output(f"📊 Depth: {exploration_depth}", "info")
        
        # Gather context from memory and focus board
        recent_progress = self.focus_board.get('progress', [])[-10:]
        recent_ideas = self.focus_board.get('ideas', [])[-10:]
        recent_issues = self.focus_board.get('issues', [])[-5:]
        
        # Query vector store for relevant context
        relevant_context = []
        if self.hybrid_memory:
            try:
                search_results = self.hybrid_memory.vec.search(
                    collection="long_term_docs",
                    query=self.focus,
                    limit=10,
                    filter_dict={"project_id": self.project_id}
                )
                relevant_context = [doc.get("text", "") for doc in search_results]
            except Exception as e:
                self._stream_output(f"⚠️ Could not retrieve context: {e}", "warning")
        
        self._update_progress()
        
        # Multi-faceted exploration prompt
        exploration_prompt = f"""You are in an exploratory thought phase for this project:

    PROJECT FOCUS: {self.focus}

    RECENT PROGRESS:
    {json.dumps([p.get('note', '') if isinstance(p, dict) else str(p) for p in recent_progress], indent=2)}

    CURRENT IDEAS:
    {json.dumps([i.get('note', '') if isinstance(i, dict) else str(i) for i in recent_ideas], indent=2)}

    KNOWN ISSUES:
    {json.dumps([i.get('note', '') if isinstance(i, dict) else str(i) for i in recent_issues], indent=2)}


    {f"ADDITIONAL CONTEXT: {context}" if context else ""}

    Engage in exploratory thinking across these dimensions:

    1. **INSIGHTS** - What patterns, principles, or realizations emerge?
    2. **CONNECTIONS** - What unexpected relationships or dependencies exist?
    3. **QUESTIONS** - What deep questions should we be asking?
    4. **HYPOTHESES** - What theories or approaches might be worth testing?

    Depth level: {exploration_depth}
    - "quick": 2-3 items per dimension
    - "medium": 3-5 items per dimension  
    - "deep": 5-8 items per dimension

    Think creatively and laterally. Don't just analyze what's there - imagine what could be,
    identify hidden assumptions, find analogies from other domains, question the approach itself.

    Respond with a JSON object with keys: insights, connections, questions, hypotheses
    Each should be an array of strings.
    """
        
        self._stream_output("🤔 Engaging exploratory cognition...", "info")
        self._update_progress()
        
        response = ""
        try:
            for chunk in self._stream_llm_with_thought_broadcast(self.agent.deep_llm, exploration_prompt):
                response += chunk
            
            self._update_progress()
            
        except Exception as e:
            self._stream_output(f"❌ Error: {str(e)}", "error")
            response = f"Error: {str(e)}"
        
        # Parse response
        discoveries = {
            "insights": [],
            "connections": [],
            "questions": [],
            "hypotheses": []
        }
        
        try:
            parsed = json.loads(response.strip().strip('```json').strip('```').strip())
            discoveries = {
                "insights": parsed.get("insights", []),
                "connections": parsed.get("connections", []),
                "questions": parsed.get("questions", []),
                "hypotheses": parsed.get("hypotheses", [])
            }
        except (json.JSONDecodeError, ValueError) as e:
            self._stream_output(f"⚠️ Could not parse JSON, extracting text: {e}", "warning")
            # Fallback: treat as insights
            discoveries["insights"] = [response]
        
        self._update_progress()
        
        # Process and store discoveries
        total_discoveries = sum(len(v) for v in discoveries.values())
        self._stream_output(f"\n✨ Discovered {total_discoveries} items across 4 dimensions", "success")
        
        # Create nodes and add to focus board
        for dimension, items in discoveries.items():
            if not items:
                continue
                
            self._stream_output(f"\n📌 {dimension.upper()} ({len(items)}):", "info")
            
            for idx, item in enumerate(items, 1):
                # Create discovery node
                discovery_id = f"{dimension}_{stage_id}_{idx}"
                
                if self.hybrid_memory:
                    self.hybrid_memory.upsert_entity(
                        entity_id=discovery_id,
                        etype=dimension[:-1],  # Remove 's' for singular
                        labels=["Discovery", dimension.capitalize()],
                        properties={
                            "text": item,
                            "dimension": dimension,
                            "index": idx,
                            "stage_id": stage_id,
                            "iteration_id": self.current_iteration_id,
                            "project_id": self.project_id,
                            "session_id": self.agent.sess.id if hasattr(self.agent, 'sess') else None,
                            "created_at": datetime.utcnow().isoformat()
                        }
                    )
                    
                    # Link to stage
                    self.hybrid_memory.link(stage_id, discovery_id, "DISCOVERED", {"dimension": dimension})
                    
                    # Add to vector store
                    self.hybrid_memory.vec.add_texts(
                        collection="long_term_docs",
                        ids=[discovery_id],
                        texts=[item],
                        metadatas=[{
                            "type": dimension,
                            "stage_id": stage_id,
                            "project_id": self.project_id,
                            "session_id": self.agent.sess.id if hasattr(self.agent, 'sess') else None
                        }]
                    )
                    
                    # Extract resources
                    self._extract_and_link_resources(item, discovery_id)
                
                # Add to appropriate focus board category
                if dimension == "insights":
                    self.add_to_focus_board("ideas", f"💡 INSIGHT: {item}")
                elif dimension == "connections":
                    self.add_to_focus_board("ideas", f"🔗 CONNECTION: {item}")
                elif dimension == "questions":
                    self.add_to_focus_board("ideas", f"❓ QUESTION: {item}")
                elif dimension == "hypotheses":
                    self.add_to_focus_board("next_steps", f"🧪 HYPOTHESIS: {item}")
                
                self._stream_output(f"  {idx}. {item[:120]}{'...' if len(item) > 120 else ''}", "info")
        
        # Write exploration report to project
        exploration_content = self._format_exploration_report(discoveries)
        filepath = self._write_to_project(
            exploration_content,
            "insights",
            f"exploration_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.md"
        )
        
        # Complete stage
        self._complete_stage_node(output=response, output_count=total_discoveries)
        self._update_progress()
        self._clear_stage()
        
        return discoveries

    def _format_exploration_report(self, discoveries: Dict[str, List[str]]) -> str:
        """Format exploration discoveries as markdown report."""
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        report = f"""# Exploratory Discovery Report

    **Project:** {self.focus}
    **Iteration:** {self.iteration_count}
    **Timestamp:** {timestamp}
    **Total Discoveries:** {sum(len(v) for v in discoveries.values())}

    ---

    ## 💡 Insights
    *Patterns, principles, and realizations*

    """
        
        for idx, insight in enumerate(discoveries.get("insights", []), 1):
            report += f"{idx}. {insight}\n\n"
        
        report += """
    ---

    ## 🔗 Connections
    *Unexpected relationships and dependencies*

    """
        
        for idx, connection in enumerate(discoveries.get("connections", []), 1):
            report += f"{idx}. {connection}\n\n"
        
        report += """
    ---

    ## ❓ Questions
    *Deep questions worth exploring*

    """
        
        for idx, question in enumerate(discoveries.get("questions", []), 1):
            report += f"{idx}. {question}\n\n"
        
        report += """
    ---

    ## 🧪 Hypotheses
    *Theories and approaches to test*

    """
        
        for idx, hypothesis in enumerate(discoveries.get("hypotheses", []), 1):
            report += f"{idx}. {hypothesis}\n\n"
        
        report += f"""
    ---

    *Generated by Vera Proactive Focus Manager*
    *Project ID: {self.project_id}*
    """
        
        return report

    def synthesize_learnings(self, lookback_iterations: int = 5) -> Dict[str, Any]:
        """
        Synthesis stage - review recent work, identify patterns and learnings,
        create structured knowledge artifacts.
        
        Args:
            lookback_iterations: How many iterations to analyze
            
        Returns:
            Dict with synthesis results and metadata
        """
        if not self.focus:
            return {}
        
        # Create stage node
        stage_id = self._create_stage_node(
            "Learning Synthesis",
            "synthesis",
            f"Synthesizing insights from last {lookback_iterations} iterations"
        )
        
        self._set_stage("Learning Synthesis", f"Reviewing {lookback_iterations} iterations", 4)
        self._stream_output("=" * 60, "info")
        self._stream_output("🧠 LEARNING SYNTHESIS STAGE", "info")
        self._stream_output("=" * 60, "info")
        self._stream_output(f"🎯 Focus: {self.focus}", "info")
        self._stream_output(f"📊 Analyzing last {lookback_iterations} iterations", "info")
        
        # Gather data from recent iterations
        synthesis_data = self._gather_synthesis_data(lookback_iterations)
        
        self._update_progress()
        
        # Build synthesis prompt
        synthesis_prompt = f"""You are synthesizing learnings from recent work on this project:

    PROJECT FOCUS: {self.focus}
    ITERATIONS ANALYZED: {lookback_iterations}

    RECENT PROGRESS ({len(synthesis_data['progress'])} items):
    {json.dumps(synthesis_data['progress'][:20], indent=2)}

    COMPLETED ACTIONS ({len(synthesis_data['completed'])} items):
    {json.dumps(synthesis_data['completed'][:15], indent=2)}

    PERSISTENT ISSUES ({len(synthesis_data['issues'])} items):
    {json.dumps(synthesis_data['issues'], indent=2)}

    GENERATED IDEAS ({len(synthesis_data['ideas'])} items):
    {json.dumps(synthesis_data['ideas'][:15], indent=2)}

    {f"GRAPH INSIGHTS: {synthesis_data.get('graph_insights', '')}" if synthesis_data.get('graph_insights') else ""}

    Synthesize this information into structured knowledge. Provide:

    1. **KEY_LEARNINGS**: What are the 3-5 most important things learned?
    2. **PATTERNS**: What recurring patterns or themes emerged?
    3. **OBSTACLES**: What are the main blockers or challenges?
    4. **BREAKTHROUGHS**: What worked particularly well?
    5. **STRATEGIC_INSIGHTS**: What does this tell us about the overall approach?
    6. **NEXT_FOCUS_AREAS**: What should be prioritized next based on learnings?

    Think deeply about what the data reveals. Look for:
    - What assumptions were validated or invalidated?
    - What unexpected results occurred?
    - What skills/knowledge gaps were exposed?
    - What process improvements could be made?
    - What resources or tools proved most valuable?

    Respond with a JSON object containing these six keys, each with an array of strings.
    Be specific and actionable.
    """
        
        self._stream_output("🔄 Synthesizing patterns and learnings...", "info")
        self._update_progress()
        
        response = ""
        try:
            for chunk in self._stream_llm_with_thought_broadcast(self.agent.deep_llm, synthesis_prompt):
                response += chunk
            
            self._update_progress()
            
        except Exception as e:
            self._stream_output(f"❌ Error: {str(e)}", "error")
            response = f"Error: {str(e)}"
        
        # Parse synthesis
        synthesis = {
            "key_learnings": [],
            "patterns": [],
            "obstacles": [],
            "breakthroughs": [],
            "strategic_insights": [],
            "next_focus_areas": []
        }
        
        try:
            parsed = json.loads(response.strip().strip('```json').strip('```').strip())
            synthesis = {
                "key_learnings": parsed.get("KEY_LEARNINGS", parsed.get("key_learnings", [])),
                "patterns": parsed.get("PATTERNS", parsed.get("patterns", [])),
                "obstacles": parsed.get("OBSTACLES", parsed.get("obstacles", [])),
                "breakthroughs": parsed.get("BREAKTHROUGHS", parsed.get("breakthroughs", [])),
                "strategic_insights": parsed.get("STRATEGIC_INSIGHTS", parsed.get("strategic_insights", [])),
                "next_focus_areas": parsed.get("NEXT_FOCUS_AREAS", parsed.get("next_focus_areas", []))
            }
        except (json.JSONDecodeError, ValueError) as e:
            self._stream_output(f"⚠️ Could not parse JSON: {e}", "warning")
            synthesis["key_learnings"] = [response]
        
        self._update_progress()
        
        # Display synthesis
        total_items = sum(len(v) for v in synthesis.values())
        self._stream_output(f"\n✅ Synthesized {total_items} insights", "success")
        
        for category, items in synthesis.items():
            if not items:
                continue
            
            emoji_map = {
                "key_learnings": "📚",
                "patterns": "🔄",
                "obstacles": "🚧",
                "breakthroughs": "🎯",
                "strategic_insights": "💡",
                "next_focus_areas": "→"
            }
            
            self._stream_output(f"\n{emoji_map.get(category, '•')} {category.replace('_', ' ').upper()}:", "info")
            for idx, item in enumerate(items, 1):
                self._stream_output(f"  {idx}. {item[:150]}{'...' if len(item) > 150 else ''}", "info")
                
                # Add strategic insights and next focus areas to focus board
                if category == "strategic_insights":
                    self.add_to_focus_board("ideas", f"💡 STRATEGIC: {item}")
                elif category == "next_focus_areas":
                    self.add_to_focus_board("next_steps", f"→ FOCUS: {item}")
                elif category == "obstacles":
                    self.add_to_focus_board("issues", f"🚧 {item}")
        
        # Write synthesis report
        synthesis_content = self._format_synthesis_report(synthesis, synthesis_data)
        synthesis_filepath = self._write_to_project(
            synthesis_content,
            "syntheses",
            f"synthesis_iter{self.iteration_count}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.md"
        )
        
        # Update cumulative learnings file
        cumulative_content = self._format_cumulative_learning(synthesis)
        self._write_to_project(
            cumulative_content,
            "syntheses",
            "cumulative_learnings.md",
            append=True
        )
        
        # Store in graph
        if self.hybrid_memory:
            synthesis_id = f"synthesis_{stage_id}"
            self.hybrid_memory.upsert_entity(
                entity_id=synthesis_id,
                etype="synthesis",
                labels=["Synthesis", "LearningArtifact"],
                properties={
                    "iteration": self.iteration_count,
                    "total_insights": total_items,
                    "stage_id": stage_id,
                    "project_id": self.project_id,
                    "filepath": synthesis_filepath,
                    "created_at": datetime.utcnow().isoformat()
                }
            )
            
            self.hybrid_memory.link(stage_id, synthesis_id, "PRODUCED", {})
            
            # Store full synthesis in vector store
            self.hybrid_memory.vec.add_texts(
                collection="long_term_docs",
                ids=[synthesis_id],
                texts=[synthesis_content],
                metadatas=[{
                    "type": "synthesis",
                    "iteration": self.iteration_count,
                    "project_id": self.project_id
                }]
            )
        
        # Complete stage
        self._complete_stage_node(output=response, output_count=total_items)
        self._clear_stage()
        
        return synthesis

    def _gather_synthesis_data(self, lookback_iterations: int) -> Dict[str, Any]:
        """Gather data for synthesis from recent iterations."""
        data = {
            "progress": [],
            "completed": [],
            "issues": [],
            "ideas": [],
            "graph_insights": ""
        }
        
        # Get recent items from focus board
        data["progress"] = [
            p.get('note', '') if isinstance(p, dict) else str(p)
            for p in self.focus_board.get('progress', [])[-30:]
        ]
        
        data["completed"] = [
            c.get('note', '') if isinstance(c, dict) else str(c)
            for c in self.focus_board.get('completed', [])[-20:]
        ]
        
        data["issues"] = [
            i.get('note', '') if isinstance(i, dict) else str(i)
            for i in self.focus_board.get('issues', [])
        ]
        
        data["ideas"] = [
            i.get('note', '') if isinstance(i, dict) else str(i)
            for i in self.focus_board.get('ideas', [])[-20:]
        ]
        
        # Query graph for recent iteration summaries
        if self.hybrid_memory and self.project_id:
            try:
                with self.hybrid_memory.graph._driver.session() as sess:
                    result = sess.run("""
                        MATCH (p:Project {id: $project_id})-[:HAS_ITERATION]->(i:WorkflowIteration)
                        WHERE i.status = 'completed'
                        WITH i
                        ORDER BY i.started_at DESC
                        LIMIT $limit
                        MATCH (i)-[:HAS_STAGE]->(s:WorkflowStage)
                        RETURN i.iteration_number AS iteration,
                            i.summary AS summary,
                            collect(s.stage_type) AS stages,
                            count(s) AS stage_count
                    """, project_id=self.project_id, limit=lookback_iterations)
                    
                    insights = []
                    for record in result:
                        insights.append(
                            f"Iteration {record['iteration']}: "
                            f"{record['stage_count']} stages, "
                            f"Summary: {record.get('summary', 'N/A')[:100]}"
                        )
                    
                    data["graph_insights"] = "\n".join(insights) if insights else ""
                    
            except Exception as e:
                self._stream_output(f"⚠️ Could not query graph: {e}", "warning")
        
        return data

    def _format_synthesis_report(self, synthesis: Dict[str, List[str]], 
                                data: Dict[str, Any]) -> str:
        """Format synthesis as comprehensive markdown report."""
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        report = f"""# Learning Synthesis Report

    **Project:** {self.focus}
    **Iteration:** {self.iteration_count}
    **Timestamp:** {timestamp}
    **Project ID:** {self.project_id}

    ---

    ## Executive Summary

    This synthesis covers the learnings, patterns, and insights from recent project work.
    Total insights generated: {sum(len(v) for v in synthesis.values())}

    ---

    ## 📚 Key Learnings

    """
        
        for idx, learning in enumerate(synthesis.get("key_learnings", []), 1):
            report += f"{idx}. **{learning}**\n\n"
        
        report += """
    ---

    ## 🔄 Patterns Identified

    """
        
        for idx, pattern in enumerate(synthesis.get("patterns", []), 1):
            report += f"{idx}. {pattern}\n\n"
        
        report += """
    ---

    ## 🚧 Obstacles & Challenges

    """
        
        for idx, obstacle in enumerate(synthesis.get("obstacles", []), 1):
            report += f"{idx}. {obstacle}\n\n"
        
        report += """
    ---

    ## 🎯 Breakthroughs & Wins

    """
        
        for idx, breakthrough in enumerate(synthesis.get("breakthroughs", []), 1):
            report += f"{idx}. {breakthrough}\n\n"
        
        report += """
    ---

    ## 💡 Strategic Insights

    """
        
        for idx, insight in enumerate(synthesis.get("strategic_insights", []), 1):
            report += f"{idx}. {insight}\n\n"
        
        report += """
    ---

    ## → Recommended Next Focus Areas

    """
        
        for idx, area in enumerate(synthesis.get("next_focus_areas", []), 1):
            report += f"{idx}. {area}\n\n"
        
        report += f"""
    ---

    ## Data Summary

    - **Progress Items Analyzed:** {len(data.get('progress', []))}
    - **Completed Actions:** {len(data.get('completed', []))}
    - **Active Issues:** {len(data.get('issues', []))}
    - **Ideas Generated:** {len(data.get('ideas', []))}

    ---

    *Generated by Vera Proactive Focus Manager - Synthesis Engine*
    """
        
        return report

    def _format_cumulative_learning(self, synthesis: Dict[str, List[str]]) -> str:
        """Format a concise entry for cumulative learnings log."""
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        
        entry = f"""
    ## Iteration {self.iteration_count} - {timestamp}

    **Top Learnings:**
    {chr(10).join(f"- {l}" for l in synthesis.get('key_learnings', [])[:3])}

    **Key Breakthrough:**
    {synthesis.get('breakthroughs', ['None'])[0] if synthesis.get('breakthroughs') else 'None'}

    **Next Focus:**
    {synthesis.get('next_focus_areas', ['Continue current trajectory'])[0] if synthesis.get('next_focus_areas') else 'Continue current trajectory'}

    """
        return entry