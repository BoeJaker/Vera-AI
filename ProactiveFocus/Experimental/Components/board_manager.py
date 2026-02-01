# focus_board.py
"""Focus board data structure and persistence."""

import json
import os
import re
from datetime import datetime
from typing import Optional, Dict, List, Any
from pathlib import Path


class FocusBoard:
    """Manages focus board state and persistence."""
    
    def __init__(self, boards_dir: str = "./Output/projects/focus_boards"):
        self.boards_dir = boards_dir
        os.makedirs(boards_dir, exist_ok=True)
        
        self.board = {
            "progress": [],
            "next_steps": [],
            "issues": [],
            "ideas": [],
            "actions": [],
            "completed": []
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
    
    def save(
        self,
        focus: str,
        project_id: str,
        agent=None,
        filename: Optional[str] = None
    ) -> str:
        """Save board to file."""
        if not filename:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            safe_focus = re.sub(r'[^\w\-_]', '_', focus)[:50]
            filename = f"{safe_focus}_{timestamp}.json"
        
        filepath = os.path.join(self.boards_dir, filename)
        
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
        
        return filepath
    
    def load(self, filename: str) -> Optional[Dict[str, Any]]:
        """Load board from file."""
        filepath = os.path.join(self.boards_dir, filename)
        
        if not os.path.exists(filepath):
            return None
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.board = data.get("board", self.board)
        return data
    
    def set_focus(
        self,
        focus: str,
        project_name: Optional[str],
        create_project: bool,
        hybrid_memory,
        agent
    ) -> Optional[str]:
        """Set focus and handle project linking."""
        # Check for existing board
        existing = self._find_matching_board(focus)
        if existing:
            self.load(existing['filename'])
            return existing.get('project_id')
        
        # Clear board for new focus
        self.board = {
            "progress": [],
            "next_steps": [],
            "issues": [],
            "ideas": [],
            "actions": [],
            "completed": []
        }
        
        # Create project in memory
        project_id = None
        if hybrid_memory and (project_name or create_project):
            project_name = project_name or focus
            project_id = f"project_{project_name.lower().replace(' ', '_')}"
            
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
        """Find matching saved board."""
        focus_lower = focus.lower().strip()
        
        for filename in os.listdir(self.boards_dir):
            if not filename.endswith('.json'):
                continue
            
            filepath = os.path.join(self.boards_dir, filename)
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                
                saved_focus = data.get('focus', '').lower().strip()
                
                if saved_focus == focus_lower or focus_lower in saved_focus or saved_focus in focus_lower:
                    return {
                        "filename": filename,
                        "focus": data.get('focus'),
                        "project_id": data.get('project_id')
                    }
            except Exception:
                continue
        
        return None
    
    def restore_from_memory(self, hybrid_memory) -> Optional[Dict[str, Any]]:
        """Restore most recent focus from memory."""
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
                
                return {
                    "project_id": result["project_id"],
                    "focus": result["description"] or result["name"]
                }
        except Exception as e:
            print(f"[FocusBoard] Error restoring: {e}")
            return None