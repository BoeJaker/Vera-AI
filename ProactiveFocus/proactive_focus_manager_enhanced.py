import asyncio
import threading
import time
import json
import os
from datetime import datetime, time as dt_time
from typing import Optional, Callable, Dict, List, Any, Set
from enum import Enum
import psutil
import re


class BackgroundMode(Enum):
    """Background thinking modes"""
    OFF = "off"  # No background thinking
    MANUAL = "manual"  # Only on manual trigger
    SCHEDULED = "scheduled"  # Run on schedule
    CONTINUOUS = "continuous"  # Run continuously with interval


class EntityReference:
    """Reference to a Neo4j entity (session, notebook, folder, etc.)"""
    def __init__(self, entity_id: str, entity_type: str, name: str, metadata: Optional[Dict] = None):
        self.entity_id = entity_id
        self.entity_type = entity_type  # 'session', 'notebook', 'folder', 'document', etc.
        self.name = name
        self.metadata = metadata or {}
        self.content_summary: Optional[str] = None
        
    def to_dict(self) -> Dict:
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "name": self.name,
            "metadata": self.metadata,
            "content_summary": self.content_summary
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'EntityReference':
        ref = cls(
            entity_id=data["entity_id"],
            entity_type=data["entity_type"],
            name=data["name"],
            metadata=data.get("metadata", {})
        )
        ref.content_summary = data.get("content_summary")
        return ref


class FocusBoardItem:
    """Enhanced focus board item with entity references and content"""
    def __init__(self, note: str, metadata: Optional[Dict] = None):
        self.note = note
        self.timestamp = datetime.utcnow().isoformat()
        self.metadata = metadata or {}
        self.entity_refs: List[EntityReference] = []
        self.tool_suggestions: List[str] = []
        self.execution_history: List[Dict] = []
        
    def add_entity_ref(self, ref: EntityReference):
        """Add an entity reference to this item"""
        self.entity_refs.append(ref)
        
    def add_tool_suggestion(self, tool_name: str, reason: str = ""):
        """Add a suggested tool for this item"""
        self.tool_suggestions.append({
            "tool": tool_name,
            "reason": reason,
            "suggested_at": datetime.utcnow().isoformat()
        })
        
    def add_execution(self, tool_name: str, result: str, success: bool = True):
        """Record tool execution"""
        self.execution_history.append({
            "tool": tool_name,
            "result": result,
            "success": success,
            "executed_at": datetime.utcnow().isoformat()
        })
        
    def to_dict(self) -> Dict:
        return {
            "note": self.note,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
            "entity_refs": [ref.to_dict() for ref in self.entity_refs],
            "tool_suggestions": self.tool_suggestions,
            "execution_history": self.execution_history
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'FocusBoardItem':
        item = cls(
            note=data["note"],
            metadata=data.get("metadata", {})
        )
        item.timestamp = data.get("timestamp", item.timestamp)
        item.entity_refs = [
            EntityReference.from_dict(ref) 
            for ref in data.get("entity_refs", [])
        ]
        item.tool_suggestions = data.get("tool_suggestions", [])
        item.execution_history = data.get("execution_history", [])
        return item


class ProactiveFocusManager:
    """Enhanced with entity references, tool integration, and better background control"""
    
    def __init__(
        self,
        agent,
        hybrid_memory=None,
        proactive_interval: int = 60*10,
        cpu_threshold: float = 70.0,
        focus_boards_dir: str = "./Output/projects/focus_boards",
        auto_restore: bool = True,
        background_mode: BackgroundMode = BackgroundMode.MANUAL,
        schedule_start_time: Optional[str] = None,  # "09:00"
        schedule_end_time: Optional[str] = None,  # "17:00"
    ):
        self.agent = agent
        self.hybrid_memory = hybrid_memory
        self.focus: Optional[str] = None
        self.project_id: Optional[str] = None
        
        # Enhanced focus board with FocusBoardItem objects
        self.focus_board: Dict[str, List[FocusBoardItem]] = {
            "progress": [],
            "next_steps": [],
            "issues": [],
            "ideas": [],
            "actions": [],
            "completed": []
        }
        
        # Background thinking control
        self.background_mode = background_mode
        self.proactive_interval = proactive_interval
        self.schedule_start_time = self._parse_time(schedule_start_time) if schedule_start_time else None
        self.schedule_end_time = self._parse_time(schedule_end_time) if schedule_end_time else None
        self.cpu_threshold = cpu_threshold
        self.running = False
        self.thread = None
        self.pause_event = threading.Event()
        self.pause_event.set()  # Start unpaused
        
        # State tracking
        self.latest_conversation = ""
        self.proactive_callback: Optional[Callable[[str], None]] = None
        self._websockets = []
        self.current_thought = ""
        self.thought_streaming = False
        
        # Entity reference caching
        self._entity_cache: Dict[str, EntityReference] = {}
        self._related_sessions: Set[str] = set()
        self._related_notebooks: Set[str] = set()
        self._related_folders: Set[str] = set()
        
        # Tool tracking
        self._available_tools: List[str] = []
        self._tool_usage_history: List[Dict] = []
        
        self.focus_boards_dir = focus_boards_dir
        os.makedirs(focus_boards_dir, exist_ok=True)
        
        if auto_restore and hybrid_memory:
            self._restore_last_focus()
    
    # ============================================================
    # BACKGROUND CONTROL METHODS
    # ============================================================
    
    def _parse_time(self, time_str: str) -> dt_time:
        """Parse time string like '09:00' to datetime.time"""
        try:
            hour, minute = map(int, time_str.split(':'))
            return dt_time(hour=hour, minute=minute)
        except:
            return None
    
    def set_background_mode(self, mode: BackgroundMode, 
                           interval: Optional[int] = None,
                           start_time: Optional[str] = None,
                           end_time: Optional[str] = None):
        """
        Configure background thinking mode.
        
        Args:
            mode: BackgroundMode enum value
            interval: Seconds between thoughts (for scheduled/continuous)
            start_time: Start time for scheduled mode (e.g., "09:00")
            end_time: End time for scheduled mode (e.g., "17:00")
        """
        old_mode = self.background_mode
        self.background_mode = mode
        
        if interval:
            self.proactive_interval = interval
        
        if start_time:
            self.schedule_start_time = self._parse_time(start_time)
        
        if end_time:
            self.schedule_end_time = self._parse_time(end_time)
        
        print(f"[FocusManager] Background mode changed: {old_mode.value} -> {mode.value}")
        
        # Stop thread if switching to OFF or MANUAL
        if mode in [BackgroundMode.OFF, BackgroundMode.MANUAL]:
            if self.running:
                self.stop()
        
        # Start thread if switching to SCHEDULED or CONTINUOUS
        elif mode in [BackgroundMode.SCHEDULED, BackgroundMode.CONTINUOUS]:
            if not self.running and self.focus:
                self.start()
        
        self._broadcast_sync("background_mode_changed", {
            "mode": mode.value,
            "interval": self.proactive_interval,
            "start_time": start_time,
            "end_time": end_time
        })
    
    def pause_background(self):
        """Temporarily pause background thinking (can be resumed)"""
        self.pause_event.clear()
        print("[FocusManager] Background thinking paused")
        self._broadcast_sync("background_paused", {})
    
    def resume_background(self):
        """Resume paused background thinking"""
        self.pause_event.set()
        print("[FocusManager] Background thinking resumed")
        self._broadcast_sync("background_resumed", {})
    
    def is_within_schedule(self) -> bool:
        """Check if current time is within scheduled hours"""
        if not self.schedule_start_time or not self.schedule_end_time:
            return True  # No schedule restrictions
        
        current_time = datetime.now().time()
        return self.schedule_start_time <= current_time <= self.schedule_end_time
    
    def get_next_scheduled_run(self) -> Optional[datetime]:
        """Calculate next scheduled run time"""
        if self.background_mode == BackgroundMode.OFF:
            return None
        
        if self.background_mode == BackgroundMode.MANUAL:
            return None
        
        now = datetime.now()
        
        if self.background_mode == BackgroundMode.CONTINUOUS:
            return now + timedelta(seconds=self.proactive_interval)
        
        if self.background_mode == BackgroundMode.SCHEDULED:
            if not self.is_within_schedule():
                # Calculate next start time
                next_start = datetime.combine(now.date(), self.schedule_start_time)
                if next_start < now:
                    next_start = datetime.combine(
                        now.date() + timedelta(days=1), 
                        self.schedule_start_time
                    )
                return next_start
            else:
                return now + timedelta(seconds=self.proactive_interval)
        
        return None
    
    # ============================================================
    # ENTITY REFERENCE METHODS
    # ============================================================
    
    def discover_related_entities(self) -> Dict[str, List[EntityReference]]:
        """
        Discover entities related to current focus from Neo4j graph.
        Returns dict of entity_type -> [EntityReference]
        """
        if not self.hybrid_memory or not self.project_id:
            return {}
        
        discovered = {
            "sessions": [],
            "notebooks": [],
            "folders": [],
            "documents": [],
            "entities": []
        }
        
        try:
            with self.hybrid_memory.graph._driver.session() as sess:
                # Find related sessions
                result = sess.run("""
                    MATCH (p:Project {id: $project_id})-[:RELATES_TO]-(s:Session)
                    RETURN s.id AS id, s.name AS name, s.created_at AS created
                    ORDER BY s.created_at DESC
                    LIMIT 10
                """, project_id=self.project_id)
                
                for record in result:
                    ref = EntityReference(
                        entity_id=record["id"],
                        entity_type="session",
                        name=record["name"] or record["id"],
                        metadata={"created_at": record["created"]}
                    )
                    discovered["sessions"].append(ref)
                    self._related_sessions.add(record["id"])
                
                # Find related notebooks
                result = sess.run("""
                    MATCH (p:Project {id: $project_id})-[:HAS_NOTEBOOK]-(n:Notebook)
                    RETURN n.id AS id, n.name AS name, n.created_at AS created
                    ORDER BY n.created_at DESC
                    LIMIT 10
                """, project_id=self.project_id)
                
                for record in result:
                    ref = EntityReference(
                        entity_id=record["id"],
                        entity_type="notebook",
                        name=record["name"] or record["id"],
                        metadata={"created_at": record["created"]}
                    )
                    discovered["notebooks"].append(ref)
                    self._related_notebooks.add(record["id"])
                
                # Find related folders/directories
                result = sess.run("""
                    MATCH (p:Project {id: $project_id})-[:HAS_FOLDER]-(f:Folder)
                    RETURN f.id AS id, f.path AS path, f.name AS name
                    ORDER BY f.name
                    LIMIT 20
                """, project_id=self.project_id)
                
                for record in result:
                    ref = EntityReference(
                        entity_id=record["id"],
                        entity_type="folder",
                        name=record["name"] or record["path"],
                        metadata={"path": record["path"]}
                    )
                    discovered["folders"].append(ref)
                    self._related_folders.add(record["id"])
                
                # Find related documents
                result = sess.run("""
                    MATCH (p:Project {id: $project_id})-[:HAS_DOCUMENT]-(d:Document)
                    RETURN d.id AS id, d.name AS name, d.type AS type, d.created_at AS created
                    ORDER BY d.created_at DESC
                    LIMIT 20
                """, project_id=self.project_id)
                
                for record in result:
                    ref = EntityReference(
                        entity_id=record["id"],
                        entity_type="document",
                        name=record["name"] or record["id"],
                        metadata={
                            "type": record["type"],
                            "created_at": record["created"]
                        }
                    )
                    discovered["documents"].append(ref)
                
                # Find other related entities
                result = sess.run("""
                    MATCH (p:Project {id: $project_id})-[r]-(e)
                    WHERE NOT e:Session AND NOT e:Notebook AND NOT e:Folder AND NOT e:Document
                    RETURN DISTINCT labels(e) AS labels, e.id AS id, e.name AS name
                    LIMIT 20
                """, project_id=self.project_id)
                
                for record in result:
                    entity_type = record["labels"][0] if record["labels"] else "Unknown"
                    ref = EntityReference(
                        entity_id=record["id"],
                        entity_type=entity_type.lower(),
                        name=record["name"] or record["id"]
                    )
                    discovered["entities"].append(ref)
            
            print(f"[FocusManager] Discovered {sum(len(v) for v in discovered.values())} related entities")
            
            # Cache the references
            for entity_list in discovered.values():
                for ref in entity_list:
                    self._entity_cache[ref.entity_id] = ref
            
            return discovered
            
        except Exception as e:
            print(f"[FocusManager] Error discovering entities: {e}")
            return discovered
    
    def get_entity_content(self, entity_ref: EntityReference, max_length: int = 500) -> Optional[str]:
        """
        Retrieve content/summary for an entity reference.
        """
        if not self.hybrid_memory:
            return None
        
        try:
            if entity_ref.entity_type == "document":
                # Get from vector store
                docs = self.hybrid_memory.vec.get_collection("long_term_docs").get(
                    ids=[entity_ref.entity_id]
                )
                if docs and docs.get("documents"):
                    content = docs["documents"][0]
                    return content[:max_length] + "..." if len(content) > max_length else content
            
            elif entity_ref.entity_type == "notebook":
                # Get notebook content from graph
                with self.hybrid_memory.graph._driver.session() as sess:
                    result = sess.run("""
                        MATCH (n:Notebook {id: $id})-[:HAS_ENTRY]->(e:NotebookEntry)
                        RETURN e.content AS content
                        ORDER BY e.created_at DESC
                        LIMIT 5
                    """, id=entity_ref.entity_id).data()
                    
                    if result:
                        entries = [r["content"] for r in result if r.get("content")]
                        combined = "\n\n".join(entries)
                        return combined[:max_length] + "..." if len(combined) > max_length else combined
            
            elif entity_ref.entity_type == "session":
                # Get recent session messages
                result = self.hybrid_memory.semantic_search(
                    f"session:{entity_ref.entity_id}",
                    k=5,
                    filters={"session_id": entity_ref.entity_id}
                )
                if result:
                    content = "\n".join([r["text"] for r in result])
                    return content[:max_length] + "..." if len(content) > max_length else content
            
            return None
            
        except Exception as e:
            print(f"[FocusManager] Error getting entity content: {e}")
            return None
    
    def enrich_item_with_entities(self, item: FocusBoardItem, auto_discover: bool = True):
        """
        Enrich a focus board item with relevant entity references.
        Can auto-discover entities or use cached ones.
        """
        if auto_discover:
            discovered = self.discover_related_entities()
            
            # Add most relevant entities based on item content
            keywords = item.note.lower().split()
            
            # Check sessions
            for ref in discovered.get("sessions", []):
                if any(kw in ref.name.lower() for kw in keywords):
                    item.add_entity_ref(ref)
            
            # Check notebooks
            for ref in discovered.get("notebooks", []):
                if any(kw in ref.name.lower() for kw in keywords):
                    item.add_entity_ref(ref)
                    # Optionally fetch content summary
                    content = self.get_entity_content(ref, max_length=200)
                    if content:
                        ref.content_summary = content
            
            # Check documents
            for ref in discovered.get("documents", [])[:3]:  # Limit to 3 most recent
                item.add_entity_ref(ref)
        
        else:
            # Use cached entity references
            for entity_id, ref in self._entity_cache.items():
                if any(kw in ref.name.lower() for kw in item.note.lower().split()):
                    item.add_entity_ref(ref)
    
    # ============================================================
    # TOOL INTEGRATION METHODS
    # ============================================================
    
    def refresh_available_tools(self):
        """Refresh list of available tools from agent"""
        if hasattr(self.agent, 'tools'):
            self._available_tools = [tool.name for tool in self.agent.tools]
            print(f"[FocusManager] Refreshed {len(self._available_tools)} available tools")
        
        if hasattr(self.agent, 'toolchain') and hasattr(self.agent.toolchain, 'tools'):
            toolchain_tools = [tool.name for tool in self.agent.toolchain.tools]
            self._available_tools.extend([t for t in toolchain_tools if t not in self._available_tools])
            print(f"[FocusManager] Total tools: {len(self._available_tools)}")
    
    def suggest_tools_for_item(self, item: FocusBoardItem) -> List[Dict[str, str]]:
        """
        Use LLM to suggest relevant tools for a focus board item.
        """
        if not self._available_tools:
            self.refresh_available_tools()
        
        if not self._available_tools:
            return []
        
        prompt = f"""
        Task: {item.note}
        
        Available Tools:
        {', '.join(self._available_tools)}
        
        Which tools would be most helpful for this task? Suggest 1-3 tools and briefly explain why each would be useful.
        
        Respond with JSON array: [{{"tool": "tool_name", "reason": "why it's useful"}}]
        """
        
        try:
            response = self.agent.fast_llm.invoke(prompt)
            suggestions = json.loads(response)
            
            for suggestion in suggestions:
                item.add_tool_suggestion(suggestion["tool"], suggestion["reason"])
            
            return suggestions
            
        except Exception as e:
            print(f"[FocusManager] Error suggesting tools: {e}")
            return []
    
    def execute_tool_for_item(self, item: FocusBoardItem, tool_name: str, 
                             tool_input: Optional[Dict] = None) -> Optional[str]:
        """
        Execute a specific tool for a focus board item.
        """
        if tool_name not in self._available_tools:
            print(f"[FocusManager] Tool not available: {tool_name}")
            return None
        
        try:
            # Find the tool
            tool = None
            if hasattr(self.agent, 'tools'):
                tool = next((t for t in self.agent.tools if t.name == tool_name), None)
            
            if not tool and hasattr(self.agent, 'toolchain'):
                tool = next((t for t in self.agent.toolchain.tools if t.name == tool_name), None)
            
            if not tool:
                print(f"[FocusManager] Could not find tool: {tool_name}")
                return None
            
            # Prepare input
            if tool_input is None:
                tool_input = {"query": item.note}
            
            # Execute tool
            print(f"[FocusManager] Executing tool {tool_name} for: {item.note[:50]}...")
            result = tool.invoke(tool_input)
            
            # Record execution
            item.add_execution(tool_name, str(result)[:500], success=True)
            
            self._tool_usage_history.append({
                "tool": tool_name,
                "item_note": item.note,
                "result_preview": str(result)[:200],
                "timestamp": datetime.utcnow().isoformat(),
                "success": True
            })
            
            return str(result)
            
        except Exception as e:
            print(f"[FocusManager] Tool execution error: {e}")
            item.add_execution(tool_name, str(e), success=False)
            self._tool_usage_history.append({
                "tool": tool_name,
                "item_note": item.note,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
                "success": False
            })
            return None
    
    # ============================================================
    # ENHANCED GENERATION METHODS
    # ============================================================
    
    def generate_ideas(self, context: Optional[str] = None) -> List[FocusBoardItem]:
        """Generate ideas with entity references and tool suggestions"""
        if not self.focus:
            return []
        
        # Discover related entities
        entities = self.discover_related_entities()
        entity_context = self._format_entity_context(entities)
        
        prompt = f"""
        Project Focus: {self.focus}
        
        Related Resources:
        {entity_context}
        
        Current Focus Board:
        - Progress: {self._summarize_category('progress')}
        - Next Steps: {self._summarize_category('next_steps')}
        - Issues: {self._summarize_category('issues')}
        
        {f"Additional Context: {context}" if context else ""}
        
        Generate 5 creative and actionable ideas to advance this project.
        Consider the related resources available.
        Focus on practical solutions and innovative approaches.
        
        Respond with a JSON array of idea strings.
        """
        
        self.thought_streaming = True
        self._broadcast_sync("idea_generation_started", {"focus": self.focus})
        
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
            
            ideas = self._parse_json_response(response)
            result_items = []
            
            for idea_text in ideas:
                item = FocusBoardItem(idea_text)
                
                # Enrich with entity references
                self.enrich_item_with_entities(item, auto_discover=False)
                
                # Add to focus board
                self.focus_board["ideas"].append(item)
                result_items.append(item)
                
                # Store in agent memory
                self.agent.mem.add_session_memory(
                    self.agent.sess.id, 
                    idea_text, 
                    "Idea", 
                    {
                        "focus": self.focus, 
                        "source": "ProactiveFocusManager",
                        "entity_refs": [ref.entity_id for ref in item.entity_refs]
                    }
                )
            
            self._broadcast_sync("idea_generation_completed", {
                "count": len(result_items)
            })
            
            return result_items
            
        except Exception as e:
            self.thought_streaming = False
            print(f"[FocusManager] Error generating ideas: {e}")
            return []
    
    def _format_entity_context(self, entities: Dict[str, List[EntityReference]]) -> str:
        """Format entity references for LLM context"""
        lines = []
        
        for entity_type, refs in entities.items():
            if refs:
                lines.append(f"\n{entity_type.capitalize()}:")
                for ref in refs[:5]:  # Limit to 5 per type
                    lines.append(f"  - {ref.name} (id: {ref.entity_id})")
                    if ref.content_summary:
                        lines.append(f"    Summary: {ref.content_summary[:100]}...")
        
        return "\n".join(lines) if lines else "No related resources found"
    
    def _summarize_category(self, category: str, max_items: int = 3) -> str:
        """Summarize a focus board category for context"""
        items = self.focus_board.get(category, [])
        if not items:
            return "None"
        
        summaries = []
        for item in items[-max_items:]:
            summary = item.note[:100]
            if item.entity_refs:
                summary += f" [refs: {len(item.entity_refs)}]"
            summaries.append(summary)
        
        return "; ".join(summaries)
    
    # ============================================================
    # MODIFIED PROACTIVE LOOP
    # ============================================================
    
    def _run_proactive_loop(self):
        """Enhanced proactive loop with better control"""
        print(f"[FocusManager] Proactive loop started (mode: {self.background_mode.value})")
        
        self._broadcast_sync("proactive_loop_started", {
            "mode": self.background_mode.value,
            "interval": self.proactive_interval
        })
        
        while self.running:
            # Check if background thinking is enabled
            if self.background_mode == BackgroundMode.OFF:
                print("[FocusManager] Background mode is OFF, exiting loop")
                break
            
            if self.background_mode == BackgroundMode.MANUAL:
                print("[FocusManager] Background mode is MANUAL, exiting loop")
                break
            
            # Check schedule if in SCHEDULED mode
            if self.background_mode == BackgroundMode.SCHEDULED:
                if not self.is_within_schedule():
                    next_run = self.get_next_scheduled_run()
                    if next_run:
                        wait_seconds = (next_run - datetime.now()).total_seconds()
                        print(f"[FocusManager] Outside schedule, waiting {wait_seconds/60:.1f} minutes")
                        time.sleep(min(wait_seconds, 60))  # Check every minute
                        continue
            
            # Check CPU usage
            cpu_usage = self._count_ollama_processes()
            if cpu_usage >= self.cpu_threshold:
                print(f"[FocusManager] High CPU ({cpu_usage:.1f}%), pausing...")
                self._broadcast_sync("proactive_paused", {
                    "reason": "high_cpu",
                    "cpu_usage": cpu_usage
                })
                
                while self.running and self._count_ollama_processes() >= self.cpu_threshold:
                    time.sleep(5)
                
                print("[FocusManager] CPU normal, resuming...")
                self._broadcast_sync("proactive_resumed", {})
            
            # Wait for pause event
            self.pause_event.wait()
            
            # Generate proactive thought
            try:
                proactive_thought = self._generate_proactive_thought_streaming()
                
                if proactive_thought and self.proactive_callback:
                    self.proactive_callback(proactive_thought)
                
            except Exception as e:
                print(f"[FocusManager] Error in proactive thought: {e}")
            
            # Wait for next iteration
            time.sleep(self.proactive_interval)
        
        print("[FocusManager] Proactive loop ended")
        self._broadcast_sync("proactive_loop_stopped", {})
    
    # ============================================================
    # SERIALIZATION WITH ENHANCED DATA
    # ============================================================
    
    def _serialize_focus_board(self) -> Dict:
        """Serialize focus board including entity references"""
        serialized = {}
        
        for category, items in self.focus_board.items():
            serialized[category] = [item.to_dict() for item in items]
        
        return serialized
    
    def _deserialize_focus_board(self, data: Dict):
        """Deserialize focus board from saved data"""
        for category, items in data.items():
            if category not in self.focus_board:
                self.focus_board[category] = []
            
            for item_data in items:
                if isinstance(item_data, dict) and "note" in item_data:
                    item = FocusBoardItem.from_dict(item_data)
                    self.focus_board[category].append(item)
                else:
                    # Legacy format - just a string or simple dict
                    note = item_data.get("note", str(item_data)) if isinstance(item_data, dict) else str(item_data)
                    item = FocusBoardItem(note)
                    self.focus_board[category].append(item)
    
    def save_focus_board(self, filename: Optional[str] = None) -> str:
        """Save enhanced focus board with entity references"""
        if not self.focus:
            print("[FocusManager] No active focus to save")
            return None
        
        if not filename:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            safe_focus = re.sub(r'[^\w\-_]', '_', self.focus)[:50]
            filename = f"{safe_focus}_{timestamp}.json"
        
        filepath = os.path.join(self.focus_boards_dir, filename)
        
        board_data = {
            "focus": self.focus,
            "project_id": self.project_id,
            "created_at": datetime.utcnow().isoformat(),
            "board": self._serialize_focus_board(),
            "related_entities": {
                "sessions": list(self._related_sessions),
                "notebooks": list(self._related_notebooks),
                "folders": list(self._related_folders)
            },
            "tool_usage_history": self._tool_usage_history[-20:],  # Last 20
            "background_config": {
                "mode": self.background_mode.value,
                "interval": self.proactive_interval,
                "schedule_start": str(self.schedule_start_time) if self.schedule_start_time else None,
                "schedule_end": str(self.schedule_end_time) if self.schedule_end_time else None
            },
            "metadata": {
                "session_id": self.agent.sess.id if hasattr(self.agent, 'sess') else None
            }
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(board_data, f, indent=2, ensure_ascii=False)
        
        print(f"[FocusManager] Saved enhanced focus board to: {filepath}")
        
        # Also save to hybrid memory
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
        
        return filepath
    
    def load_focus_board(self, filename: str) -> bool:
        """Load enhanced focus board with entity references"""
        filepath = os.path.join(self.focus_boards_dir, filename)
        
        if not os.path.exists(filepath):
            print(f"[FocusManager] Focus board not found: {filepath}")
            return False
        
        with open(filepath, 'r', encoding='utf-8') as f:
            board_data = json.load(f)
        
        self.focus = board_data.get("focus")
        self.project_id = board_data.get("project_id")
        
        # Deserialize board
        self._deserialize_focus_board(board_data.get("board", {}))
        
        # Restore related entities
        related = board_data.get("related_entities", {})
        self._related_sessions = set(related.get("sessions", []))
        self._related_notebooks = set(related.get("notebooks", []))
        self._related_folders = set(related.get("folders", []))
        
        # Restore tool history
        self._tool_usage_history = board_data.get("tool_usage_history", [])
        
        # Restore background config
        bg_config = board_data.get("background_config", {})
        if bg_config:
            mode_str = bg_config.get("mode", "manual")
            self.background_mode = BackgroundMode(mode_str)
            self.proactive_interval = bg_config.get("interval", self.proactive_interval)
            
            if bg_config.get("schedule_start"):
                self.schedule_start_time = self._parse_time(bg_config["schedule_start"])
            if bg_config.get("schedule_end"):
                self.schedule_end_time = self._parse_time(bg_config["schedule_end"])
        
        print(f"[FocusManager] Loaded enhanced focus board from: {filepath}")
        self._broadcast_sync("board_loaded", {"filepath": filepath, "focus": self.focus})
        
        return True
    
    # ============================================================
    # UTILITY METHODS (keep existing ones)
    # ============================================================
    
    def _count_ollama_processes(self):
        """Get total system CPU usage."""
        return psutil.cpu_percent(interval=0.1)
    
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
            try:
                loop = asyncio.get_running_loop()
                asyncio.ensure_future(self.broadcast_to_websockets(event_type, data))
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.broadcast_to_websockets(event_type, data))
                loop.close()
        except Exception as e:
            print(f"[FocusManager] Broadcast failed (non-critical): {e}")
    
    @staticmethod
    def _parse_json_response(response: str) -> list:
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
            return parsed if isinstance(parsed, list) else [parsed]
        except:
            lines = [line.strip() for line in cleaned.split('\n') if line.strip()]
            lines = [line for line in lines if line not in ['[', ']', '{', '}']]
            return lines if lines else [response]

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
            