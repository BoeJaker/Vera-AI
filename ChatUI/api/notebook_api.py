import logging
import json
import os
from pathlib import Path
from uuid import uuid4
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError

# ============================================================
# Models — adjust import paths to match your structure
# ============================================================
from Vera.ChatUI.api.session import vera_instances, sessions, toolchain_executions, active_toolchains, websocket_connections

from Vera.ChatUI.api.schemas import (
    NotebookCreate,
    NotebookUpdate,
    NoteCreate,
    NoteUpdate,
    NoteSearch,
)

# ============================================================
# Logging setup
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# Router setup
# ============================================================
router = APIRouter(prefix="/api/notebooks", tags=["notebooks"])

# ============================================================
# Storage Configuration - ENHANCED
# ============================================================
NOTEBOOKS_DIR = Path("Output/Notebooks")
NOTEBOOKS_DIR.mkdir(parents=True, exist_ok=True)

# Global notebooks directory (session-independent)
GLOBAL_NOTEBOOKS_DIR = NOTEBOOKS_DIR / "All_Notebooks"
GLOBAL_NOTEBOOKS_DIR.mkdir(parents=True, exist_ok=True)

# Markdown exports directory
MARKDOWN_EXPORTS_DIR = NOTEBOOKS_DIR / "Markdown_Exports"
MARKDOWN_EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Track Neo4j availability
neo4j_available = None

# ============================================================
# Database helper with connection testing
# ============================================================
def get_neo4j_driver():
    """Get Neo4j driver with connection validation"""
    global neo4j_available
    
    try:
        driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "testpassword"))
        # Test connection
        with driver.session() as session:
            session.run("RETURN 1")
        neo4j_available = True
        return driver
    except (ServiceUnavailable, AuthError, Exception) as e:
        logger.warning(f"Neo4j unavailable, using file storage: {e}")
        neo4j_available = False
        return None

def ensure_neo4j_constraints(driver):
    """Create Neo4j constraints and indexes if they don't exist"""
    if not driver:
        return
    
    try:
        with driver.session() as session:
            # Create constraints
            try:
                session.run("CREATE CONSTRAINT session_id IF NOT EXISTS FOR (s:Session) REQUIRE s.id IS UNIQUE")
                session.run("CREATE CONSTRAINT notebook_id IF NOT EXISTS FOR (nb:Notebook) REQUIRE nb.id IS UNIQUE")
                session.run("CREATE CONSTRAINT note_id IF NOT EXISTS FOR (n:Note) REQUIRE n.id IS UNIQUE")
            except Exception as e:
                logger.debug(f"Constraints may already exist: {e}")
    except Exception as e:
        logger.error(f"Failed to create Neo4j constraints: {e}")

# ============================================================
# Session-Specific File Storage Helpers
# ============================================================
def get_session_notebook_dir(session_id: str) -> Path:
    """Get or create directory for session notebooks"""
    session_dir = NOTEBOOKS_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir

def load_notebook_from_file(session_id: str, notebook_id: str) -> Optional[Dict[str, Any]]:
    """Load notebook data from JSON file"""
    notebook_file = get_session_notebook_dir(session_id) / f"{notebook_id}.json"
    if not notebook_file.exists():
        return None
    
    try:
        with open(notebook_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load notebook {notebook_id}: {e}")
        return None

def save_notebook_to_file(session_id: str, notebook_data: Dict[str, Any]):
    """Save notebook data to JSON file"""
    notebook_file = get_session_notebook_dir(session_id) / f"{notebook_data['id']}.json"
    try:
        with open(notebook_file, 'w', encoding='utf-8') as f:
            json.dump(notebook_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to save notebook {notebook_data['id']}: {e}")
        raise

def delete_notebook_file(session_id: str, notebook_id: str):
    """Delete notebook file"""
    notebook_file = get_session_notebook_dir(session_id) / f"{notebook_id}.json"
    if notebook_file.exists():
        notebook_file.unlink()

def list_session_notebooks(session_id: str) -> List[Dict[str, Any]]:
    """List all notebooks for a session from files"""
    session_dir = get_session_notebook_dir(session_id)
    notebooks = []
    
    for notebook_file in session_dir.glob("*.json"):
        try:
            with open(notebook_file, 'r', encoding='utf-8') as f:
                notebook = json.load(f)
                notebooks.append(notebook)
        except Exception as e:
            logger.error(f"Failed to load {notebook_file}: {e}")
    
    return sorted(notebooks, key=lambda x: x.get('created_at', ''), reverse=True)

# ============================================================
# Global Storage Helpers (Session-Independent) - NEW
# ============================================================

def save_to_global_storage(notebook_data: Dict[str, Any]):
    """Save notebook to global storage (session-independent)"""
    try:
        # Save as JSON
        global_file = GLOBAL_NOTEBOOKS_DIR / f"{notebook_data['id']}.json"
        with open(global_file, 'w', encoding='utf-8') as f:
            json.dump(notebook_data, f, indent=2, ensure_ascii=False)
        
        # Also save as markdown for easy reading
        export_notebook_as_markdown(notebook_data)
        
        logger.info(f"Saved notebook {notebook_data['id']} to global storage")
    except Exception as e:
        logger.error(f"Failed to save to global storage: {e}")

def load_from_global_storage(notebook_id: str) -> Optional[Dict[str, Any]]:
    """Load notebook from global storage"""
    global_file = GLOBAL_NOTEBOOKS_DIR / f"{notebook_id}.json"
    if not global_file.exists():
        return None
    
    try:
        with open(global_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load from global storage: {e}")
        return None

def delete_from_global_storage(notebook_id: str):
    """Delete notebook from global storage"""
    global_file = GLOBAL_NOTEBOOKS_DIR / f"{notebook_id}.json"
    markdown_file = None
    
    # Find and delete markdown file
    for md_file in MARKDOWN_EXPORTS_DIR.glob(f"*_{notebook_id[:8]}.md"):
        markdown_file = md_file
        break
    
    if global_file.exists():
        global_file.unlink()
    if markdown_file and markdown_file.exists():
        markdown_file.unlink()

def list_all_notebooks() -> List[Dict[str, Any]]:
    """List all notebooks across all sessions from global storage"""
    notebooks = []
    
    for notebook_file in GLOBAL_NOTEBOOKS_DIR.glob("*.json"):
        try:
            with open(notebook_file, 'r', encoding='utf-8') as f:
                notebook = json.load(f)
                notebooks.append(notebook)
        except Exception as e:
            logger.error(f"Failed to load {notebook_file}: {e}")
    
    return sorted(notebooks, key=lambda x: x.get('updated_at', ''), reverse=True)

def export_notebook_as_markdown(notebook_data: Dict[str, Any]):
    """Export notebook as markdown file"""
    try:
        notebook_name = notebook_data.get('name', 'Untitled')
        safe_name = "".join(c for c in notebook_name if c.isalnum() or c in (' ', '-', '_')).strip()
        markdown_file = MARKDOWN_EXPORTS_DIR / f"{safe_name}_{notebook_data['id'][:8]}.md"
        
        with open(markdown_file, 'w', encoding='utf-8') as f:
            # Write header
            f.write(f"# {notebook_name}\n\n")
            
            if notebook_data.get('description'):
                f.write(f"**Description:** {notebook_data['description']}\n\n")
            
            f.write(f"**Created:** {notebook_data.get('created_at', 'Unknown')}\n")
            f.write(f"**Updated:** {notebook_data.get('updated_at', 'Unknown')}\n")
            f.write(f"**Session ID:** {notebook_data.get('session_id', 'Unknown')}\n")
            f.write(f"**Notebook ID:** {notebook_data.get('id', 'Unknown')}\n\n")
            f.write("---\n\n")
            
            # Write notes
            notes = notebook_data.get('notes', [])
            if notes:
                f.write(f"## Notes ({len(notes)})\n\n")
                
                for i, note in enumerate(notes, 1):
                    f.write(f"### {i}. {note.get('title', 'Untitled Note')}\n\n")
                    
                    # Metadata
                    f.write(f"- **Created:** {note.get('created_at', 'Unknown')}\n")
                    f.write(f"- **Updated:** {note.get('updated_at', 'Unknown')}\n")
                    
                    if note.get('tags'):
                        tags = ', '.join(note['tags'])
                        f.write(f"- **Tags:** {tags}\n")
                    
                    if note.get('source'):
                        f.write(f"- **Source:** {note['source'].get('type', 'Unknown')}\n")
                    
                    f.write("\n")
                    
                    # Content
                    content = note.get('content', '')
                    f.write(f"{content}\n\n")
                    f.write("---\n\n")
            else:
                f.write("*No notes in this notebook*\n\n")
        
        logger.info(f"Exported notebook as markdown: {markdown_file}")
    except Exception as e:
        logger.error(f"Failed to export markdown: {e}")

# ============================================================
# Hybrid Storage Functions - ENHANCED
# ============================================================

def get_notebooks_hybrid(session_id: str, include_all_sessions: bool = False) -> List[Dict[str, Any]]:
    """Get notebooks from Neo4j or file storage"""
    
    # If include_all_sessions, return from global storage
    if include_all_sessions:
        return list_all_notebooks()
    
    driver = get_neo4j_driver()
    
    if driver:
        try:
            ensure_neo4j_constraints(driver)
            with driver.session() as session:
                # Ensure session exists
                session.run("""
                    MERGE (s:Session {id: $session_id})
                    ON CREATE SET s.created_at = $now
                """, session_id=session_id, now=datetime.utcnow().isoformat())
                
                result = session.run("""
                    MATCH (s:Session {id: $session_id})-[:HAS_NOTEBOOK]->(nb:Notebook)
                    OPTIONAL MATCH (nb)-[:CONTAINS]->(n:Note)
                    WITH nb, count(n) as note_count
                    RETURN nb.id as id, nb.name as name, nb.description as description,
                           nb.created_at as created_at, nb.updated_at as updated_at,
                           note_count
                    ORDER BY nb.created_at DESC
                """, session_id=session_id)
                
                notebooks = []
                for record in result:
                    notebooks.append({
                        "id": record["id"],
                        "session_id": session_id,
                        "name": record["name"],
                        "description": record["description"],
                        "created_at": record["created_at"],
                        "updated_at": record["updated_at"],
                        "note_count": record["note_count"],
                        "notes": []
                    })
            driver.close()
            return notebooks
        except Exception as e:
            logger.error(f"Neo4j error, falling back to file storage: {e}")
            if driver:
                driver.close()
    
    # Fallback to file storage
    return list_session_notebooks(session_id)

def create_notebook_hybrid(session_id: str, notebook: NotebookCreate) -> Dict[str, Any]:
    """Create notebook in Neo4j or file storage"""
    notebook_id = str(uuid4())
    now = datetime.utcnow().isoformat()
    
    notebook_data = {
        "id": notebook_id,
        "session_id": session_id,
        "name": notebook.name,
        "description": notebook.description,
        "created_at": now,
        "updated_at": now,
        "note_count": 0,
        "notes": []
    }
    
    driver = get_neo4j_driver()
    
    if driver:
        try:
            ensure_neo4j_constraints(driver)
            with driver.session() as session:
                # Ensure session exists
                session.run("""
                    MERGE (s:Session {id: $session_id})
                    ON CREATE SET s.created_at = $now
                """, session_id=session_id, now=now)
                
                # Create notebook
                result = session.run("""
                    MATCH (s:Session {id: $session_id})
                    CREATE (nb:Notebook {
                        id: $notebook_id,
                        name: $name,
                        description: $description,
                        created_at: $now,
                        updated_at: $now
                    })
                    CREATE (s)-[:HAS_NOTEBOOK]->(nb)
                    RETURN nb
                """, session_id=session_id, notebook_id=notebook_id, 
                     name=notebook.name, description=notebook.description, now=now)
                
                if result.single():
                    driver.close()
                    # Save to session-specific file
                    save_notebook_to_file(session_id, notebook_data)
                    # Save to global storage
                    save_to_global_storage(notebook_data)
                    return notebook_data
        except Exception as e:
            logger.error(f"Neo4j error during create, using file storage: {e}")
        finally:
            if driver:
                driver.close()
    
    # Fallback to file storage
    save_notebook_to_file(session_id, notebook_data)
    save_to_global_storage(notebook_data)
    return notebook_data

def update_notebook_hybrid(session_id: str, notebook_id: str, notebook: NotebookUpdate) -> Dict[str, Any]:
    """Update notebook in Neo4j or file storage"""
    now = datetime.utcnow().isoformat()
    driver = get_neo4j_driver()
    
    if driver:
        try:
            update_fields = []
            params = {"session_id": session_id, "notebook_id": notebook_id, "now": now}
            
            if notebook.name is not None:
                update_fields.append("nb.name = $name")
                params["name"] = notebook.name
            
            if notebook.description is not None:
                update_fields.append("nb.description = $description")
                params["description"] = notebook.description
            
            if update_fields:
                update_fields.append("nb.updated_at = $now")
                
                with driver.session() as session:
                    result = session.run(f"""
                        MATCH (s:Session {{id: $session_id}})-[:HAS_NOTEBOOK]->(nb:Notebook {{id: $notebook_id}})
                        SET {', '.join(update_fields)}
                        RETURN nb
                    """, **params)
                    
                    record = result.single()
                    if record:
                        nb = record["nb"]
                        notebook_data = {
                            "id": nb["id"],
                            "session_id": session_id,
                            "name": nb["name"],
                            "description": nb["description"],
                            "created_at": nb["created_at"],
                            "updated_at": nb["updated_at"]
                        }
                        driver.close()
                        # Update file backup
                        existing = load_notebook_from_file(session_id, notebook_id)
                        if existing:
                            existing.update(notebook_data)
                            save_notebook_to_file(session_id, existing)
                            save_to_global_storage(existing)
                        return notebook_data
        except Exception as e:
            logger.error(f"Neo4j error during update, using file storage: {e}")
        finally:
            if driver:
                driver.close()
    
    # Fallback to file storage
    existing = load_notebook_from_file(session_id, notebook_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Notebook not found")
    
    if notebook.name is not None:
        existing["name"] = notebook.name
    if notebook.description is not None:
        existing["description"] = notebook.description
    existing["updated_at"] = now
    
    save_notebook_to_file(session_id, existing)
    save_to_global_storage(existing)
    return existing

def delete_notebook_hybrid(session_id: str, notebook_id: str) -> Dict[str, Any]:
    """Delete notebook from Neo4j and file storage"""
    driver = get_neo4j_driver()
    note_count = 0
    
    if driver:
        try:
            with driver.session() as session:
                # Count notes
                count_result = session.run("""
                    MATCH (s:Session {id: $session_id})-[:HAS_NOTEBOOK]->(nb:Notebook {id: $notebook_id})
                    OPTIONAL MATCH (nb)-[:CONTAINS]->(n:Note)
                    RETURN count(n) as note_count
                """, session_id=session_id, notebook_id=notebook_id)
                
                count_record = count_result.single()
                if count_record:
                    note_count = count_record["note_count"]
                    
                    # Delete
                    session.run("""
                        MATCH (s:Session {id: $session_id})-[:HAS_NOTEBOOK]->(nb:Notebook {id: $notebook_id})
                        OPTIONAL MATCH (nb)-[:CONTAINS]->(n:Note)
                        DETACH DELETE nb, n
                    """, session_id=session_id, notebook_id=notebook_id)
        except Exception as e:
            logger.error(f"Neo4j error during delete: {e}")
        finally:
            if driver:
                driver.close()
    
    # Delete from all storage
    try:
        delete_notebook_file(session_id, notebook_id)
        delete_from_global_storage(notebook_id)
    except Exception as e:
        logger.error(f"Failed to delete notebook files: {e}")
    
    return {"success": True, "deleted_notes": note_count}

# ============================================================
# Notebook Endpoints - ENHANCED
# ============================================================

@router.get("/{session_id}")
async def get_notebooks(session_id: str, all_sessions: bool = False):
    """Get all notebooks for a session or across all sessions"""
    try:
        notebooks = get_notebooks_hybrid(session_id, include_all_sessions=all_sessions)
        return {
            "notebooks": notebooks,
            "storage_type": "neo4j" if neo4j_available else "file",
            "all_sessions": all_sessions
        }
    except Exception as e:
        logger.error(f"Failed to get notebooks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/global/list")
async def get_all_notebooks_global():
    """Get all notebooks across all sessions (global view)"""
    try:
        notebooks = list_all_notebooks()
        
        # Group by session for better organization
        by_session = {}
        for nb in notebooks:
            session_id = nb.get('session_id', 'unknown')
            if session_id not in by_session:
                by_session[session_id] = []
            by_session[session_id].append(nb)
        
        return {
            "notebooks": notebooks,
            "by_session": by_session,
            "total": len(notebooks),
            "sessions": len(by_session)
        }
    except Exception as e:
        logger.error(f"Failed to get global notebooks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{session_id}/create")
async def create_notebook(session_id: str, notebook: NotebookCreate):
    """Create a new notebook"""
    try:
        notebook_data = create_notebook_hybrid(session_id, notebook)
        return {
            "notebook": notebook_data,
            "storage_type": "neo4j" if neo4j_available else "file"
        }
    except Exception as e:
        logger.error(f"Failed to create notebook: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{session_id}/{notebook_id}")
async def update_notebook(session_id: str, notebook_id: str, notebook: NotebookUpdate):
    """Update a notebook"""
    try:
        notebook_data = update_notebook_hybrid(session_id, notebook_id, notebook)
        return {
            "notebook": notebook_data,
            "storage_type": "neo4j" if neo4j_available else "file"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update notebook: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{session_id}/{notebook_id}")
async def delete_notebook(session_id: str, notebook_id: str):
    """Delete a notebook and all its notes"""
    try:
        result = delete_notebook_hybrid(session_id, notebook_id)
        return result
    except Exception as e:
        logger.error(f"Failed to delete notebook: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== NOTE ENDPOINTS ====================

@router.get("/{session_id}/{notebook_id}/notes")
async def get_notes(
    session_id: str, 
    notebook_id: str,
    sort_by: str = "created_at",
    order: str = "desc",
    limit: int = 50,
    offset: int = 0
):
    """Get all notes in a notebook"""
    # Try Neo4j first
    driver = get_neo4j_driver()
    
    if driver:
        try:
            valid_sort_fields = ["created_at", "updated_at", "title"]
            if sort_by not in valid_sort_fields:
                sort_by = "created_at"
            
            order_clause = "DESC" if order.lower() == "desc" else "ASC"
            
            with driver.session() as session:
                result = session.run(f"""
                    MATCH (s:Session {{id: $session_id}})-[:HAS_NOTEBOOK]->(nb:Notebook {{id: $notebook_id}})
                    MATCH (nb)-[:CONTAINS]->(n:Note)
                    RETURN n.id as id, n.title as title, n.content as content,
                           n.created_at as created_at, n.updated_at as updated_at,
                           n.source as source, n.tags as tags, n.metadata as metadata
                    ORDER BY n.{sort_by} {order_clause}
                    SKIP $offset
                    LIMIT $limit
                """, session_id=session_id, notebook_id=notebook_id, 
                     offset=offset, limit=limit)
                
                notes = []
                for record in result:
                    note = {
                        "id": record["id"],
                        "notebook_id": notebook_id,
                        "title": record["title"],
                        "content": record["content"],
                        "created_at": record["created_at"],
                        "updated_at": record["updated_at"],
                        "tags": record["tags"] or [],
                        "metadata": record["metadata"] or {}
                    }
                    
                    if record["source"]:
                        note["source"] = record["source"]
                    
                    notes.append(note)
                
                # Get total count
                count_result = session.run("""
                    MATCH (nb:Notebook {id: $notebook_id})-[:CONTAINS]->(n:Note)
                    RETURN count(n) as total
                """, notebook_id=notebook_id)
                
                total = count_result.single()["total"]
                
            driver.close()
            return {
                "notes": notes,
                "total": total,
                "limit": limit,
                "offset": offset,
                "storage_type": "neo4j"
            }
        except Exception as e:
            logger.error(f"Neo4j error, falling back to file storage: {e}")
            if driver:
                driver.close()
    
    # Fallback to file storage
    notebook_data = load_notebook_from_file(session_id, notebook_id)
    if not notebook_data:
        # Try global storage
        notebook_data = load_from_global_storage(notebook_id)
        if not notebook_data:
            raise HTTPException(status_code=404, detail="Notebook not found")
    
    notes = notebook_data.get("notes", [])
    
    # Sort notes
    reverse = order.lower() == "desc"
    if sort_by == "title":
        notes.sort(key=lambda x: x.get("title", ""), reverse=reverse)
    elif sort_by == "updated_at":
        notes.sort(key=lambda x: x.get("updated_at", ""), reverse=reverse)
    else:  # created_at
        notes.sort(key=lambda x: x.get("created_at", ""), reverse=reverse)
    
    # Paginate
    total = len(notes)
    notes = notes[offset:offset + limit]
    
    return {
        "notes": notes,
        "total": total,
        "limit": limit,
        "offset": offset,
        "storage_type": "file"
    }

@router.get("/{session_id}/{notebook_id}/notes/{note_id}")
async def get_note(session_id: str, notebook_id: str, note_id: str):
    """Get a single note"""
    driver = get_neo4j_driver()
    
    if driver:
        try:
            with driver.session() as session:
                result = session.run("""
                    MATCH (s:Session {id: $session_id})-[:HAS_NOTEBOOK]->(nb:Notebook {id: $notebook_id})
                    MATCH (nb)-[:CONTAINS]->(n:Note {id: $note_id})
                    RETURN n.id as id, n.title as title, n.content as content,
                           n.created_at as created_at, n.updated_at as updated_at,
                           n.source as source, n.tags as tags, n.metadata as metadata
                """, session_id=session_id, notebook_id=notebook_id, note_id=note_id)
                
                record = result.single()
                if record:
                    note = {
                        "id": record["id"],
                        "notebook_id": notebook_id,
                        "title": record["title"],
                        "content": record["content"],
                        "created_at": record["created_at"],
                        "updated_at": record["updated_at"],
                        "tags": record["tags"] or [],
                        "metadata": record["metadata"] or {}
                    }
                    
                    if record["source"]:
                        note["source"] = record["source"]
                    
                    driver.close()
                    return {"note": note, "storage_type": "neo4j"}
        except Exception as e:
            logger.error(f"Neo4j error: {e}")
        finally:
            if driver:
                driver.close()
    
    # Fallback to file storage
    notebook_data = load_notebook_from_file(session_id, notebook_id)
    if not notebook_data:
        notebook_data = load_from_global_storage(notebook_id)
        if not notebook_data:
            raise HTTPException(status_code=404, detail="Notebook not found")
    
    note = next((n for n in notebook_data.get("notes", []) if n["id"] == note_id), None)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    return {"note": note, "storage_type": "file"}

@router.post("/{session_id}/{notebook_id}/notes/create")
async def create_note(session_id: str, notebook_id: str, note: NoteCreate):
    """Create a new note"""
    note_id = str(uuid4())
    now = datetime.utcnow().isoformat()
    
    source_dict = note.source.dict() if note.source else None
    
    note_data = {
        "id": note_id,
        "notebook_id": notebook_id,
        "title": note.title,
        "content": note.content,
        "created_at": now,
        "updated_at": now,
        "tags": note.tags or [],
        "metadata": note.metadata or {}
    }
    
    if source_dict:
        note_data["source"] = source_dict
    
    driver = get_neo4j_driver()
    
    if driver:
        try:
            with driver.session() as session:
                # Check if notebook exists
                notebook_check = session.run("""
                    MATCH (s:Session {id: $session_id})-[:HAS_NOTEBOOK]->(nb:Notebook {id: $notebook_id})
                    RETURN nb
                """, session_id=session_id, notebook_id=notebook_id)
                
                if notebook_check.single():
                    # Create note
                    result = session.run("""
                        MATCH (nb:Notebook {id: $notebook_id})
                        CREATE (n:Note {
                            id: $note_id,
                            title: $title,
                            content: $content,
                            created_at: $now,
                            updated_at: $now,
                            source: $source,
                            tags: $tags,
                            metadata: $metadata
                        })
                        CREATE (nb)-[:CONTAINS]->(n)
                        RETURN n
                    """, notebook_id=notebook_id, note_id=note_id, title=note.title,
                         content=note.content, now=now, source=source_dict,
                         tags=note.tags, metadata=note.metadata)
                    
                    if result.single():
                        driver.close()
                        # Update file backup
                        notebook_data = load_notebook_from_file(session_id, notebook_id)
                        if notebook_data:
                            notebook_data.setdefault("notes", []).append(note_data)
                            notebook_data["note_count"] = len(notebook_data["notes"])
                            save_notebook_to_file(session_id, notebook_data)
                            save_to_global_storage(notebook_data)
                        return {"note": note_data, "storage_type": "neo4j"}
        except Exception as e:
            logger.error(f"Neo4j error during note create: {e}")
        finally:
            if driver:
                driver.close()
    
    # Fallback to file storage
    notebook_data = load_notebook_from_file(session_id, notebook_id)
    if not notebook_data:
        raise HTTPException(status_code=404, detail="Notebook not found")
    
    notebook_data.setdefault("notes", []).append(note_data)
    notebook_data["note_count"] = len(notebook_data["notes"])
    save_notebook_to_file(session_id, notebook_data)
    save_to_global_storage(notebook_data)
    
    return {"note": note_data, "storage_type": "file"}

@router.put("/{session_id}/{notebook_id}/notes/{note_id}/update")
async def update_note(session_id: str, notebook_id: str, note_id: str, note: NoteUpdate):
    """Update a note"""
    now = datetime.utcnow().isoformat()
    driver = get_neo4j_driver()
    
    if driver:
        try:
            update_fields = []
            params = {
                "session_id": session_id,
                "notebook_id": notebook_id,
                "note_id": note_id,
                "now": now
            }
            
            if note.title is not None:
                update_fields.append("n.title = $title")
                params["title"] = note.title
            
            if note.content is not None:
                update_fields.append("n.content = $content")
                params["content"] = note.content
            
            if note.tags is not None:
                update_fields.append("n.tags = $tags")
                params["tags"] = note.tags
            
            if note.metadata is not None:
                update_fields.append("n.metadata = $metadata")
                params["metadata"] = note.metadata
            
            if update_fields:
                update_fields.append("n.updated_at = $now")
                
                with driver.session() as session:
                    result = session.run(f"""
                        MATCH (s:Session {{id: $session_id}})-[:HAS_NOTEBOOK]->(nb:Notebook {{id: $notebook_id}})
                        MATCH (nb)-[:CONTAINS]->(n:Note {{id: $note_id}})
                        SET {', '.join(update_fields)}
                        RETURN n
                    """, **params)
                    
                    record = result.single()
                    if record:
                        n = record["n"]
                        note_data = {
                            "id": n["id"],
                            "notebook_id": notebook_id,
                            "title": n["title"],
                            "content": n["content"],
                            "created_at": n["created_at"],
                            "updated_at": n["updated_at"],
                            "tags": n["tags"] or [],
                            "metadata": n["metadata"] or {}
                        }
                        
                        if n.get("source"):
                            note_data["source"] = n["source"]
                        
                        driver.close()
                        # Update file backup
                        notebook_data = load_notebook_from_file(session_id, notebook_id)
                        if notebook_data:
                            for i, existing_note in enumerate(notebook_data.get("notes", [])):
                                if existing_note["id"] == note_id:
                                    notebook_data["notes"][i] = note_data
                                    break
                            save_notebook_to_file(session_id, notebook_data)
                            save_to_global_storage(notebook_data)
                        return {"note": note_data, "storage_type": "neo4j"}
        except Exception as e:
            logger.error(f"Neo4j error during note update: {e}")
        finally:
            if driver:
                driver.close()
    
    # Fallback to file storage
    notebook_data = load_notebook_from_file(session_id, notebook_id)
    if not notebook_data:
        raise HTTPException(status_code=404, detail="Notebook not found")
    
    for existing_note in notebook_data.get("notes", []):
        if existing_note["id"] == note_id:
            if note.title is not None:
                existing_note["title"] = note.title
            if note.content is not None:
                existing_note["content"] = note.content
            if note.tags is not None:
                existing_note["tags"] = note.tags
            if note.metadata is not None:
                existing_note["metadata"] = note.metadata
            existing_note["updated_at"] = now
            
            save_notebook_to_file(session_id, notebook_data)
            save_to_global_storage(notebook_data)
            return {"note": existing_note, "storage_type": "file"}
    
    raise HTTPException(status_code=404, detail="Note not found")

@router.delete("/{session_id}/{notebook_id}/notes/{note_id}")
async def delete_note(session_id: str, notebook_id: str, note_id: str):
    """Delete a note"""
    driver = get_neo4j_driver()
    
    if driver:
        try:
            with driver.session() as session:
                result = session.run("""
                    MATCH (s:Session {id: $session_id})-[:HAS_NOTEBOOK]->(nb:Notebook {id: $notebook_id})
                    MATCH (nb)-[:CONTAINS]->(n:Note {id: $note_id})
                    DETACH DELETE n
                    RETURN count(n) as deleted
                """, session_id=session_id, notebook_id=notebook_id, note_id=note_id)
                
                record = result.single()
                if record and record["deleted"] > 0:
                    driver.close()
                    # Update file backup
                    notebook_data = load_notebook_from_file(session_id, notebook_id)
                    if notebook_data:
                        notebook_data["notes"] = [n for n in notebook_data.get("notes", []) if n["id"] != note_id]
                        notebook_data["note_count"] = len(notebook_data["notes"])
                        save_notebook_to_file(session_id, notebook_data)
                        save_to_global_storage(notebook_data)
                    return {"success": True, "storage_type": "neo4j"}
        except Exception as e:
            logger.error(f"Neo4j error during note delete: {e}")
        finally:
            if driver:
                driver.close()
    
    # Fallback to file storage
    notebook_data = load_notebook_from_file(session_id, notebook_id)
    if not notebook_data:
        raise HTTPException(status_code=404, detail="Notebook not found")
    
    initial_count = len(notebook_data.get("notes", []))
    notebook_data["notes"] = [n for n in notebook_data.get("notes", []) if n["id"] != note_id]
    
    if len(notebook_data["notes"]) == initial_count:
        raise HTTPException(status_code=404, detail="Note not found")
    
    notebook_data["note_count"] = len(notebook_data["notes"])
    save_notebook_to_file(session_id, notebook_data)
    save_to_global_storage(notebook_data)
    
    return {"success": True, "storage_type": "file"}

# ==================== SEARCH ENDPOINTS ====================

@router.post("/{session_id}/search")
async def search_notes(session_id: str, search: NoteSearch):
    """Search notes across notebooks"""
    driver = get_neo4j_driver()
    
    if driver:
        try:
            # Build query filters
            where_clauses = ["toLower(n.title) CONTAINS toLower($query) OR toLower(n.content) CONTAINS toLower($query)"]
            params = {"session_id": session_id, "query": search.query}
            
            if search.notebook_ids:
                where_clauses.append("nb.id IN $notebook_ids")
                params["notebook_ids"] = search.notebook_ids
            
            if search.tags:
                where_clauses.append("ANY(tag IN $tags WHERE tag IN n.tags)")
                params["tags"] = search.tags
            
            if search.source_type:
                where_clauses.append("n.source.type = $source_type")
                params["source_type"] = search.source_type
            
            if search.date_from:
                where_clauses.append("n.created_at >= $date_from")
                params["date_from"] = search.date_from
            
            if search.date_to:
                where_clauses.append("n.created_at <= $date_to")
                params["date_to"] = search.date_to
            
            where_clause = " AND ".join(where_clauses)
            
            with driver.session() as session:
                result = session.run(f"""
                    MATCH (s:Session {{id: $session_id}})-[:HAS_NOTEBOOK]->(nb:Notebook)
                    MATCH (nb)-[:CONTAINS]->(n:Note)
                    WHERE {where_clause}
                    RETURN n.id as id, n.title as title, n.content as content,
                           n.created_at as created_at, n.updated_at as updated_at,
                           n.source as source, n.tags as tags, n.metadata as metadata,
                           nb.id as notebook_id, nb.name as notebook_name
                    ORDER BY n.updated_at DESC
                    LIMIT 50
                """, **params)
                
                results = []
                for record in result:
                    content = record["content"] or ""
                    query_lower = search.query.lower()
                    content_lower = content.lower()
                    pos = content_lower.find(query_lower)
                    
                    if pos != -1:
                        start = max(0, pos - 50)
                        end = min(len(content), pos + len(search.query) + 50)
                        excerpt = "..." + content[start:end] + "..."
                    else:
                        excerpt = content[:100] + "..." if len(content) > 100 else content
                    
                    results.append({
                        "note": {
                            "id": record["id"],
                            "notebook_id": record["notebook_id"],
                            "title": record["title"],
                            "content": record["content"],
                            "created_at": record["created_at"],
                            "updated_at": record["updated_at"],
                            "tags": record["tags"] or [],
                            "metadata": record["metadata"] or {},
                            "source": record["source"]
                        },
                        "notebook": {
                            "id": record["notebook_id"],
                            "name": record["notebook_name"]
                        },
                        "relevance_score": 1.0,
                        "matched_content": excerpt
                    })
            
            driver.close()
            return {"results": results, "total": len(results), "storage_type": "neo4j"}
        except Exception as e:
            logger.error(f"Neo4j search error: {e}")
            if driver:
                driver.close()
    
    # Fallback to file storage search
    all_notebooks = list_session_notebooks(session_id)
    results = []
    query_lower = search.query.lower()
    
    for notebook_data in all_notebooks:
        if search.notebook_ids and notebook_data["id"] not in search.notebook_ids:
            continue
        
        for note in notebook_data.get("notes", []):
            title_lower = (note.get("title") or "").lower()
            content_lower = (note.get("content") or "").lower()
            
            if query_lower in title_lower or query_lower in content_lower:
                # Apply additional filters
                if search.tags and not any(tag in note.get("tags", []) for tag in search.tags):
                    continue
                if search.source_type and note.get("source", {}).get("type") != search.source_type:
                    continue
                if search.date_from and note.get("created_at", "") < search.date_from:
                    continue
                if search.date_to and note.get("created_at", "") > search.date_to:
                    continue
                
                # Create excerpt
                content = note.get("content", "")
                pos = content_lower.find(query_lower)
                if pos != -1:
                    start = max(0, pos - 50)
                    end = min(len(content), pos + len(search.query) + 50)
                    excerpt = "..." + content[start:end] + "..."
                else:
                    excerpt = content[:100] + "..." if len(content) > 100 else content
                
                results.append({
                    "note": note,
                    "notebook": {
                        "id": notebook_data["id"],
                        "name": notebook_data["name"]
                    },
                    "relevance_score": 1.0,
                    "matched_content": excerpt
                })
    
    results.sort(key=lambda x: x["note"].get("updated_at", ""), reverse=True)
    results = results[:50]
    
    return {"results": results, "total": len(results), "storage_type": "file"}

@router.get("/{session_id}/tags/{tag_name}")
async def get_notes_by_tag(session_id: str, tag_name: str):
    """Get all notes with a specific tag"""
    driver = get_neo4j_driver()
    
    if driver:
        try:
            with driver.session() as session:
                result = session.run("""
                    MATCH (s:Session {id: $session_id})-[:HAS_NOTEBOOK]->(nb:Notebook)
                    MATCH (nb)-[:CONTAINS]->(n:Note)
                    WHERE $tag_name IN n.tags
                    RETURN n, nb
                    ORDER BY n.updated_at DESC
                """, session_id=session_id, tag_name=tag_name)
                
                notes = []
                notebooks_dict = {}
                
                for record in result:
                    n = record["n"]
                    nb = record["nb"]
                    
                    notes.append({
                        "id": n["id"],
                        "notebook_id": nb["id"],
                        "title": n["title"],
                        "content": n["content"],
                        "created_at": n["created_at"],
                        "updated_at": n["updated_at"],
                        "tags": n["tags"] or [],
                        "metadata": n["metadata"] or {}
                    })
                    
                    if nb["id"] not in notebooks_dict:
                        notebooks_dict[nb["id"]] = {
                            "id": nb["id"],
                            "name": nb["name"]
                        }
            
            driver.close()
            return {
                "notes": notes,
                "notebooks": list(notebooks_dict.values()),
                "storage_type": "neo4j"
            }
        except Exception as e:
            logger.error(f"Neo4j tag search error: {e}")
            if driver:
                driver.close()
    
    # Fallback to file storage
    all_notebooks = list_session_notebooks(session_id)
    notes = []
    notebooks_dict = {}
    
    for notebook_data in all_notebooks:
        for note in notebook_data.get("notes", []):
            if tag_name in note.get("tags", []):
                notes.append({
                    "id": note["id"],
                    "notebook_id": notebook_data["id"],
                    "title": note["title"],
                    "content": note["content"],
                    "created_at": note["created_at"],
                    "updated_at": note["updated_at"],
                    "tags": note["tags"],
                    "metadata": note["metadata"]
                })
                
                if notebook_data["id"] not in notebooks_dict:
                    notebooks_dict[notebook_data["id"]] = {
                        "id": notebook_data["id"],
                        "name": notebook_data["name"]
                    }
    
    notes.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    
    return {
        "notes": notes,
        "notebooks": list(notebooks_dict.values()),
        "storage_type": "file"
    }

@router.get("/{session_id}/tags")
async def get_all_tags(session_id: str):
    """Get all tags used in session notebooks"""
    driver = get_neo4j_driver()
    
    if driver:
        try:
            with driver.session() as session:
                result = session.run("""
                    MATCH (s:Session {id: $session_id})-[:HAS_NOTEBOOK]->(nb:Notebook)
                    MATCH (nb)-[:CONTAINS]->(n:Note)
                    UNWIND n.tags as tag
                    WITH tag, count(*) as usage_count
                    RETURN tag, usage_count
                    ORDER BY usage_count DESC
                """, session_id=session_id)
                
                tags = [{"tag": record["tag"], "count": record["usage_count"]} 
                        for record in result]
            
            driver.close()
            return {"tags": tags, "storage_type": "neo4j"}
        except Exception as e:
            logger.error(f"Neo4j tags error: {e}")
            if driver:
                driver.close()
    
    # Fallback to file storage
    all_notebooks = list_session_notebooks(session_id)
    tag_counts = {}
    
    for notebook_data in all_notebooks:
        for note in notebook_data.get("notes", []):
            for tag in note.get("tags", []):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
    
    tags = [{"tag": tag, "count": count} for tag, count in tag_counts.items()]
    tags.sort(key=lambda x: x["count"], reverse=True)
    
    return {"tags": tags, "storage_type": "file"}

# ==================== EXPORT/IMPORT ENDPOINTS - ENHANCED ====================

@router.get("/{session_id}/{notebook_id}/export")
async def export_notebook(session_id: str, notebook_id: str):
    """Export entire notebook as JSON"""
    # Always use file storage for export (most reliable)
    notebook_data = load_notebook_from_file(session_id, notebook_id)
    
    if not notebook_data:
        # Try global storage
        notebook_data = load_from_global_storage(notebook_id)
    
    if not notebook_data:
        # Try Neo4j if file not found
        driver = get_neo4j_driver()
        if driver:
            try:
                with driver.session() as session:
                    nb_result = session.run("""
                        MATCH (s:Session {id: $session_id})-[:HAS_NOTEBOOK]->(nb:Notebook {id: $notebook_id})
                        RETURN nb
                    """, session_id=session_id, notebook_id=notebook_id)
                    
                    nb_record = nb_result.single()
                    if not nb_record:
                        raise HTTPException(status_code=404, detail="Notebook not found")
                    
                    nb = nb_record["nb"]
                    
                    notes_result = session.run("""
                        MATCH (nb:Notebook {id: $notebook_id})-[:CONTAINS]->(n:Note)
                        RETURN n
                        ORDER BY n.created_at ASC
                    """, notebook_id=notebook_id)
                    
                    notes = []
                    for record in notes_result:
                        n = record["n"]
                        notes.append({
                            "id": n["id"],
                            "title": n["title"],
                            "content": n["content"],
                            "created_at": n["created_at"],
                            "updated_at": n["updated_at"],
                            "tags": n["tags"] or [],
                            "metadata": n["metadata"] or {},
                            "source": n.get("source")
                        })
                
                driver.close()
                
                notebook_data = {
                    "id": nb["id"],
                    "session_id": session_id,
                    "name": nb["name"],
                    "description": nb.get("description"),
                    "created_at": nb["created_at"],
                    "updated_at": nb["updated_at"],
                    "notes": notes
                }
            except Exception as e:
                logger.error(f"Export error: {e}")
                raise HTTPException(status_code=404, detail="Notebook not found")
            finally:
                if driver:
                    driver.close()
    
    return {
        "notebook": {
            "id": notebook_data["id"],
            "name": notebook_data["name"],
            "description": notebook_data.get("description"),
            "created_at": notebook_data["created_at"],
            "updated_at": notebook_data["updated_at"]
        },
        "notes": notebook_data.get("notes", []),
        "exported_at": datetime.utcnow().isoformat()
    }

@router.post("/{session_id}/{notebook_id}/export-markdown")
async def export_notebook_markdown(session_id: str, notebook_id: str):
    """Export notebook as markdown"""
    try:
        # Load notebook with all notes
        notebook_data = load_notebook_from_file(session_id, notebook_id)
        if not notebook_data:
            notebook_data = load_from_global_storage(notebook_id)
        
        if not notebook_data:
            raise HTTPException(status_code=404, detail="Notebook not found")
        
        export_notebook_as_markdown(notebook_data)
        
        return {
            "success": True,
            "message": f"Exported to {MARKDOWN_EXPORTS_DIR}"
        }
    except Exception as e:
        logger.error(f"Failed to export markdown: {e}")
        raise HTTPException(status_code=500, detail=str(e))