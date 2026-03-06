# board_manager.py — FIXED VERSION
"""Focus board data structure and persistence."""

import json
import os
import re
from datetime import datetime
from typing import Optional, Dict, List, Any
from pathlib import Path


class FocusBoard:
    """Manages focus board state and persistence."""
    
    def __init__(self, boards_dir: str = "./Output/Projects/focus_boards"):
        self.boards_dir = boards_dir
        os.makedirs(boards_dir, exist_ok=True)
        
        self.focus_board = {
            "progress": [],
            "next_steps": [],
            "issues": [],
            "ideas": [],
            "actions": [],
            "completed": [],
            "questions": []
        }
    
    def add_item(self, category: str, note: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Add item to category."""
        if category not in self.board:
            self.board[category] = []
        
        item = {
            "note": note,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }
        
        self.board[category].append(item)
        return item
    
    def move_to_completed(self, category: str, index: int):
        """Move item to completed."""
        if category in self.board and 0 <= index < len(self.board[category]):
            item = self.board[category].pop(index)
            item["completed_at"] = datetime.utcnow().isoformat()
            item["original_category"] = category
            self.board["completed"].append(item)
    
    def move_to_category(self, from_category: str, index: int, to_category: str):
        """Move item between categories."""
        if from_category in self.board and 0 <= index < len(self.board[from_category]):
            if to_category not in self.board:
                self.board[to_category] = []
            item = self.board[from_category].pop(index)
            item["moved_from"] = from_category
            item["moved_at"] = datetime.utcnow().isoformat()
            self.board[to_category].append(item)
    
    def get_all(self) -> Dict[str, List]:
        """Get entire board."""
        return self.board
    
    def get_category(self, category: str) -> List[Dict[str, Any]]:
        """Get items in category."""
        return self.board.get(category, [])
    
    def get_stats(self) -> Dict[str, int]:
        """Get board statistics."""
        return {
            category: len(items)
            for category, items in self.board.items()
        }
    
    def consolidate(self):
        """Remove duplicates and archive old completed items."""
        for category in self.board:
            if not self.board[category]:
                continue
            
            # Deduplicate by note text
            seen = set()
            unique = []
            for item in reversed(self.board[category]):
                note = item.get("note", "") if isinstance(item, dict) else str(item)
                if note not in seen:
                    seen.add(note)
                    unique.append(item)
            
            self.board[category] = list(reversed(unique))
        
        # Keep last 20 completed items
        if len(self.board.get("completed", [])) > 20:
            self.board["completed"] = self.board["completed"][-20:]
    
    @staticmethod
    def _sanitize_filename(text: str, max_length: int = 50) -> str:
        """
        FIX: Robust filename sanitization that avoids empty/garbage names.
        
        Issues this fixes:
        - Windows 8.3 short names (PG79DN~7) caused by special chars or long paths
        - Empty strings from aggressive regex
        - Names that are all underscores
        """
        if not text:
            return "unnamed_board"
        
        # Replace common separators with underscores
        safe = text.strip()
        safe = re.sub(r'[\s\-/\\:]+', '_', safe)
        
        # Remove anything that's not alphanumeric, underscore, or dash
        safe = re.sub(r'[^\w\-]', '', safe)
        
        # Collapse multiple underscores
        safe = re.sub(r'_+', '_', safe)
        
        # Strip leading/trailing underscores
        safe = safe.strip('_')
        
        # Truncate
        safe = safe[:max_length]
        
        # Final safety check
        if not safe or safe == '_':
            return "unnamed_board"
        
        return safe
    
    def save(
        self,
        focus: str,
        project_id: str,
        agent=None,
        filename: Optional[str] = None
    ) -> Optional[str]:
        """Save board to file.
        
        FIX: Better filename generation and None guards.
        """
        # FIX: Guard against None focus
        if not focus:
            print("[FocusBoard] Cannot save: no focus provided")
            return None
        
        if not filename:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            # FIX: Use robust sanitizer instead of simple regex
            safe_focus = self._sanitize_filename(focus)
            filename = f"{safe_focus}_{timestamp}.json"
        
        # FIX: Ensure directory exists (handles race conditions)
        os.makedirs(self.boards_dir, exist_ok=True)
        
        filepath = os.path.join(self.boards_dir, filename)
        
        # FIX: Resolve to absolute path to avoid Windows short name issues
        filepath = str(Path(filepath).resolve())
        
        data = {
            "focus": focus,
            "project_id": project_id,
            "created_at": datetime.utcnow().isoformat(),
            "board": self.board,
            "metadata": {
                "session_id": agent.sess.id if agent and hasattr(agent, 'sess') else None
            }
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"[FocusBoard] Saved: {filepath}")
        return filepath
    
    def load(self, filename: str) -> Optional[Dict[str, Any]]:
        """Load board from file.
        
        FIX: Try multiple path strategies to find the file.
        """
        # Try direct path first
        filepath = os.path.join(self.boards_dir, filename)
        
        # FIX: Also try resolved path (handles Windows short names)
        if not os.path.exists(filepath):
            try:
                filepath = str(Path(filepath).resolve())
            except Exception:
                pass
        
        # FIX: Also try just the filename in case it's already a full path
        if not os.path.exists(filepath) and os.path.exists(filename):
            filepath = filename
        
        if not os.path.exists(filepath):
            print(f"[FocusBoard] File not found: {filepath}")
            return None
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # FIX: Validate board structure
            loaded_board = data.get("board", {})
            
            # Ensure all expected categories exist
            for category in ["progress", "next_steps", "issues", "ideas", "actions", "completed", "questions"]:
                if category not in loaded_board:
                    loaded_board[category] = []
            
            self.board = loaded_board
            
            print(f"[FocusBoard] Loaded: {filepath}")
            print(f"[FocusBoard] Focus: {data.get('focus')}")
            print(f"[FocusBoard] Items: {sum(len(v) for v in self.board.values())}")
            
            return data
            
        except json.JSONDecodeError as e:
            print(f"[FocusBoard] Invalid JSON in {filepath}: {e}")
            return None
        except Exception as e:
            print(f"[FocusBoard] Error loading {filepath}: {e}")
            return None
    
    def set_focus(
        self,
        focus: str,
        project_name: Optional[str],
        create_project: bool,
        hybrid_memory,
        agent
    ) -> Optional[str]:
        """Set focus and handle project linking.
        
        FIX: This method is no longer called by the manager.
        The manager handles focus setting directly to keep state in sync.
        Kept for standalone FocusBoard usage.
        """
        # Check for existing board
        existing = self._find_matching_board(focus)
        if existing:
            loaded = self.load(existing['filename'])
            if loaded:
                return loaded.get('project_id')
        
        # Clear board for new focus
        self.focus_board = {
            "progress": [],
            "next_steps": [],
            "issues": [],
            "ideas": [],
            "actions": [],
            "completed": [],
            "questions": []
        }
        
        # Create project in memory
        project_id = None
        if hybrid_memory and (project_name or create_project):
            project_name = project_name or focus
            # FIX: Sanitize project name
            safe_name = re.sub(r'[^\w\-_ ]', '', project_name).strip()
            if not safe_name:
                safe_name = "unnamed_project"
            project_id = f"project_{safe_name.lower().replace(' ', '_')}"
            
            hybrid_memory.upsert_entity(
                entity_id=project_id,
                etype="project",
                labels=["Project"],
                properties={
                    "name": project_name,
                    "description": focus,
                    "created_at": datetime.utcnow().isoformat(),
                    "status": "active"
                }
            )
            
            if hasattr(agent, 'sess') and agent.sess:
                hybrid_memory.link_session_focus(agent.sess.id, [project_id])
        
        return project_id
    
    def _find_matching_board(self, focus: str) -> Optional[Dict[str, Any]]:
        """Find matching saved board.
        
        FIX: Better error handling and logging.
        """
        if not focus:
            return None
        
        focus_lower = focus.lower().strip()
        
        try:
            if not os.path.exists(self.boards_dir):
                return None
            
            for filename in os.listdir(self.boards_dir):
                if not filename.endswith('.json'):
                    continue
                
                filepath = os.path.join(self.boards_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    saved_focus = data.get('focus', '').lower().strip()
                    
                    if not saved_focus:
                        continue
                    
                    # Exact match
                    if saved_focus == focus_lower:
                        print(f"[FocusBoard] Exact match: {filename}")
                        return {
                            "filename": filename,
                            "focus": data.get('focus'),
                            "project_id": data.get('project_id'),
                            "created_at": data.get('created_at')
                        }
                    
                    # Partial match (one contains the other)
                    if focus_lower in saved_focus or saved_focus in focus_lower:
                        print(f"[FocusBoard] Partial match: {filename}")
                        return {
                            "filename": filename,
                            "focus": data.get('focus'),
                            "project_id": data.get('project_id'),
                            "created_at": data.get('created_at')
                        }
                except Exception as e:
                    print(f"[FocusBoard] Error reading {filename}: {e}")
                    continue
        except Exception as e:
            print(f"[FocusBoard] Error scanning boards dir: {e}")
        
        return None
    
    def restore_from_memory(self, hybrid_memory) -> Optional[Dict[str, Any]]:
        """Restore most recent focus from memory.
        
        FIX: Handle NULL description AND name fields in Neo4j.
        """
        if not hybrid_memory:
            return None
        
        try:
            with hybrid_memory.graph._driver.session() as sess:
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
                    return None
                
                project_id = result["project_id"]
                description = result["description"]
                name = result["name"]
                focus = description or name  # Could still be None
                
                # FIX: Don't return a result with None focus
                if not focus:
                    print(f"[FocusBoard] Project {project_id} has no name or description, skipping restore")
                    return None
                
                print(f"[FocusBoard] Restored from memory: {focus} ({project_id})")
                
                # Try to find and load a matching board file
                matching = self._find_matching_board(focus)
                if matching:
                    loaded = self.load(matching['filename'])
                    if loaded:
                        return loaded
                
                return {
                    "project_id": project_id,
                    "focus": focus
                }
        except Exception as e:
            print(f"[FocusBoard] Error restoring: {e}")
            return None