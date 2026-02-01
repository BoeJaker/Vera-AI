# context_enricher.py
"""Builds enriched context from memory and board state."""

import json
from typing import Dict, Any, List
from datetime import datetime, timedelta


class ContextEnricher:
    """Enriches iteration context with memory queries."""
    
    def __init__(self, focus_manager):
        self.fm = focus_manager
    
    def build_iteration_context(self, iteration: int, analysis: Dict[str, Any]) -> str:
        """Build enriched context for an iteration."""
        context_parts = []
        
        # Board state summary
        context_parts.append(f"## Board State (Iteration {iteration})")
        context_parts.append(analysis['summary'])
        
        # Query project-specific memory
        if self.fm.hybrid_memory and self.fm.project_id:
            project_context = self._query_project_memory()
            if project_context:
                context_parts.append("\n## Project Memory")
                context_parts.append(project_context)
        
        # Query recent session memory
        if self.fm.hybrid_memory and hasattr(self.fm.agent, 'sess'):
            session_context = self._query_session_memory()
            if session_context:
                context_parts.append("\n## Recent Session Context")
                context_parts.append(session_context)
        
        # Recent progress
        recent_progress = self.fm.board.get_category("progress")[-5:]
        if recent_progress:
            context_parts.append("\n## Recent Progress")
            for item in recent_progress:
                note = item.get("note", "") if isinstance(item, dict) else str(item)
                context_parts.append(f"- {note}")
        
        # Outstanding issues
        issues = self.fm.board.get_category("issues")
        if issues:
            context_parts.append("\n## Outstanding Issues")
            for item in issues[:5]:
                note = item.get("note", "") if isinstance(item, dict) else str(item)
                context_parts.append(f"- {note}")
        
        return "\n".join(context_parts)
    
    def build_proactive_context(self, conversation: str, board: Dict[str, List]) -> str:
        """Build context for proactive thought generation."""
        context_parts = []
        
        if conversation:
            context_parts.append(f"Recent Conversation:\n{conversation}")
        
        context_parts.append(f"\nCurrent Board State:")
        context_parts.append(json.dumps(board, indent=2))
        
        # Query similar past work
        if self.fm.hybrid_memory:
            similar = self._query_similar_work()
            if similar:
                context_parts.append(f"\nSimilar Past Work:\n{similar}")
        
        return "\n\n".join(context_parts)
    
    def _query_project_memory(self) -> str:
        """Query project-specific memory."""
        if not self.fm.project_id:
            return ""
        
        try:
            # Query documents linked to project
            docs = self.fm.hybrid_memory.semantic_retrieve(
                query=f"project {self.fm.focus} progress achievements",
                k=5,
                where={"project_id": self.fm.project_id}
            )
            
            if not docs:
                return ""
            
            lines = []
            for doc in docs:
                text = doc.get("text", "")
                if text:
                    lines.append(f"- {text[:200]}")
            
            return "\n".join(lines) if lines else ""
            
        except Exception as e:
            print(f"[ContextEnricher] Error querying project memory: {e}")
            return ""
    
    def _query_session_memory(self) -> str:
        """Query recent session memory."""
        if not hasattr(self.fm.agent, 'sess'):
            return ""
        
        try:
            memories = self.fm.hybrid_memory.get_session_memory(self.fm.agent.sess.id)
            
            if not memories:
                return ""
            
            # Get last 10 memories
            recent = memories[-10:]
            
            lines = []
            for mem in recent:
                text = mem.text[:200] if len(mem.text) > 200 else mem.text
                lines.append(f"- {text}")
            
            return "\n".join(lines)
            
        except Exception as e:
            print(f"[ContextEnricher] Error querying session memory: {e}")
            return ""
    
    def _query_similar_work(self) -> str:
        """Query similar past work from memory."""
        try:
            # Semantic search for similar projects/work
            results = self.fm.hybrid_memory.semantic_retrieve(
                query=self.fm.focus,
                k=3
            )
            
            if not results:
                return ""
            
            lines = []
            for result in results:
                text = result.get("text", "")
                metadata = result.get("metadata", {})
                
                if text:
                    source = metadata.get("type", "unknown")
                    lines.append(f"[{source}] {text[:150]}")
            
            return "\n".join(lines) if lines else ""
            
        except Exception as e:
            print(f"[ContextEnricher] Error querying similar work: {e}")
            return ""