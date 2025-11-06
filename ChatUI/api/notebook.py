import logging
from uuid import uuid4
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from neo4j import GraphDatabase

# ============================================================
# Models — adjust import paths to match your structure
# ============================================================
from state import vera_instances, sessions, toolchain_executions, active_toolchains, websocket_connections

from schemas import (
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
#  Notebook Endpoints
# ============================================================

# Database helper
def get_neo4j_driver():
    return GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "testpassword"))

@router.get("/{session_id}")
async def get_notebooks(session_id: str):
    """Get all notebooks for a session"""
    driver = get_neo4j_driver()
    
    with driver.session() as session:
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
                "note_count": record["note_count"]
            })
    
    driver.close()
    return {"notebooks": notebooks}

@router.post("/{session_id}/create")
async def create_notebook(session_id: str, notebook: NotebookCreate):
    """Create a new notebook"""
    driver = get_neo4j_driver()
    notebook_id = str(uuid4())
    now = datetime.utcnow().isoformat()
    
    with driver.session() as session:
        # Check if session exists
        session_check = session.run("""
            MATCH (s:Session {id: $session_id})
            RETURN s
        """, session_id=session_id)
        
        if not session_check.single():
            driver.close()
            raise HTTPException(status_code=404, detail="Session not found")
        
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
        
        record = result.single()
        if not record:
            driver.close()
            raise HTTPException(status_code=500, detail="Failed to create notebook")
        
        nb = record["nb"]
        notebook_data = {
            "id": nb["id"],
            "session_id": session_id,
            "name": nb["name"],
            "description": nb["description"],
            "created_at": nb["created_at"],
            "updated_at": nb["updated_at"],
            "note_count": 0
        }
    
    driver.close()
    return {"notebook": notebook_data}

@router.put("/{session_id}/{notebook_id}")
async def update_notebook(session_id: str, notebook_id: str, notebook: NotebookUpdate):
    """Update a notebook"""
    driver = get_neo4j_driver()
    now = datetime.utcnow().isoformat()
    
    update_fields = []
    params = {"session_id": session_id, "notebook_id": notebook_id, "now": now}
    
    if notebook.name is not None:
        update_fields.append("nb.name = $name")
        params["name"] = notebook.name
    
    if notebook.description is not None:
        update_fields.append("nb.description = $description")
        params["description"] = notebook.description
    
    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    update_fields.append("nb.updated_at = $now")
    
    with driver.session() as session:
        result = session.run(f"""
            MATCH (s:Session {{id: $session_id}})-[:HAS_NOTEBOOK]->(nb:Notebook {{id: $notebook_id}})
            SET {', '.join(update_fields)}
            RETURN nb
        """, **params)
        
        record = result.single()
        if not record:
            driver.close()
            raise HTTPException(status_code=404, detail="Notebook not found")
        
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
    return {"notebook": notebook_data}

@router.delete("/{session_id}/{notebook_id}")
async def delete_notebook(session_id: str, notebook_id: str):
    """Delete a notebook and all its notes"""
    driver = get_neo4j_driver()
    
    with driver.session() as session:
        # Count notes before deletion
        count_result = session.run("""
            MATCH (s:Session {id: $session_id})-[:HAS_NOTEBOOK]->(nb:Notebook {id: $notebook_id})
            OPTIONAL MATCH (nb)-[:CONTAINS]->(n:Note)
            RETURN count(n) as note_count
        """, session_id=session_id, notebook_id=notebook_id)
        
        count_record = count_result.single()
        if not count_record:
            driver.close()
            raise HTTPException(status_code=404, detail="Notebook not found")
        
        note_count = count_record["note_count"]
        
        # Delete notebook and its notes
        session.run("""
            MATCH (s:Session {id: $session_id})-[:HAS_NOTEBOOK]->(nb:Notebook {id: $notebook_id})
            OPTIONAL MATCH (nb)-[:CONTAINS]->(n:Note)
            DETACH DELETE nb, n
        """, session_id=session_id, notebook_id=notebook_id)
    
    driver.close()
    return {"success": True, "deleted_notes": note_count}

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
    driver = get_neo4j_driver()
    
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
        "offset": offset
    }

@router.get("/{session_id}/{notebook_id}/notes/{note_id}")
async def get_note(session_id: str, notebook_id: str, note_id: str):
    """Get a single note"""
    driver = get_neo4j_driver()
    
    with driver.session() as session:
        result = session.run("""
            MATCH (s:Session {id: $session_id})-[:HAS_NOTEBOOK]->(nb:Notebook {id: $notebook_id})
            MATCH (nb)-[:CONTAINS]->(n:Note {id: $note_id})
            RETURN n.id as id, n.title as title, n.content as content,
                   n.created_at as created_at, n.updated_at as updated_at,
                   n.source as source, n.tags as tags, n.metadata as metadata
        """, session_id=session_id, notebook_id=notebook_id, note_id=note_id)
        
        record = result.single()
        if not record:
            driver.close()
            raise HTTPException(status_code=404, detail="Note not found")
        
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
    return {"note": note}

@router.post("/{session_id}/{notebook_id}/notes/create")
async def create_note(session_id: str, notebook_id: str, note: NoteCreate):
    """Create a new note"""
    driver = get_neo4j_driver()
    note_id = str(uuid4())
    now = datetime.utcnow().isoformat()
    
    source_dict = note.source.dict() if note.source else None
    
    with driver.session() as session:
        # Check if notebook exists
        notebook_check = session.run("""
            MATCH (s:Session {id: $session_id})-[:HAS_NOTEBOOK]->(nb:Notebook {id: $notebook_id})
            RETURN nb
        """, session_id=session_id, notebook_id=notebook_id)
        
        if not notebook_check.single():
            driver.close()
            raise HTTPException(status_code=404, detail="Notebook not found")
        
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
            
            // Link to source message if applicable
            WITH n
            UNWIND CASE WHEN $source_message_id IS NOT NULL THEN [$source_message_id] ELSE [] END AS msg_id
            MATCH (m:Message {id: msg_id})
            CREATE (n)-[:CAPTURED_FROM]->(m)
            
            RETURN n
        """, notebook_id=notebook_id, note_id=note_id, title=note.title,
             content=note.content, now=now, source=source_dict,
             tags=note.tags, metadata=note.metadata,
             source_message_id=source_dict.get("message_id") if source_dict else None)
        
        record = result.single()
        if not record:
            driver.close()
            raise HTTPException(status_code=500, detail="Failed to create note")
        
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
        
        if n["source"]:
            note_data["source"] = n["source"]
    
    driver.close()
    return {"note": note_data}

@router.put("/{session_id}/{notebook_id}/notes/{note_id}/update")
async def update_note(session_id: str, notebook_id: str, note_id: str, note: NoteUpdate):
    """Update a note"""
    driver = get_neo4j_driver()
    now = datetime.utcnow().isoformat()
    
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
    
    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    update_fields.append("n.updated_at = $now")
    
    with driver.session() as session:
        result = session.run(f"""
            MATCH (s:Session {{id: $session_id}})-[:HAS_NOTEBOOK]->(nb:Notebook {{id: $notebook_id}})
            MATCH (nb)-[:CONTAINS]->(n:Note {{id: $note_id}})
            SET {', '.join(update_fields)}
            RETURN n
        """, **params)
        
        record = result.single()
        if not record:
            driver.close()
            raise HTTPException(status_code=404, detail="Note not found")
        
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
    return {"note": note_data}

@router.delete("/{session_id}/{notebook_id}/notes/{note_id}")
async def delete_note(session_id: str, notebook_id: str, note_id: str):
    """Delete a note"""
    driver = get_neo4j_driver()
    
    with driver.session() as session:
        result = session.run("""
            MATCH (s:Session {id: $session_id})-[:HAS_NOTEBOOK]->(nb:Notebook {id: $notebook_id})
            MATCH (nb)-[:CONTAINS]->(n:Note {id: $note_id})
            DETACH DELETE n
            RETURN count(n) as deleted
        """, session_id=session_id, notebook_id=notebook_id, note_id=note_id)
        
        record = result.single()
        if not record or record["deleted"] == 0:
            driver.close()
            raise HTTPException(status_code=404, detail="Note not found")
    
    driver.close()
    return {"success": True}

# ==================== SEARCH ENDPOINTS ====================

@router.post("/{session_id}/search")
async def search_notes(session_id: str, search: NoteSearch):
    """Search notes across notebooks"""
    driver = get_neo4j_driver()
    
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
            # Create excerpt with highlighted search term
            content = record["content"] or ""
            query_lower = search.query.lower()
            
            # Find the position of the search term
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
                "relevance_score": 1.0,  # Could implement proper scoring
                "matched_content": excerpt
            })
    
    driver.close()
    return {"results": results, "total": len(results)}

@router.get("/{session_id}/tags/{tag_name}")
async def get_notes_by_tag(session_id: str, tag_name: str):
    """Get all notes with a specific tag"""
    driver = get_neo4j_driver()
    
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
        "notebooks": list(notebooks_dict.values())
    }

@router.get("/{session_id}/tags")
async def get_all_tags(session_id: str):
    """Get all tags used in session notebooks"""
    driver = get_neo4j_driver()
    
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
    return {"tags": tags}

# ==================== EXPORT/IMPORT ENDPOINTS ====================

@router.get("/{session_id}/{notebook_id}/export")
async def export_notebook(session_id: str, notebook_id: str):
    """Export entire notebook as JSON"""
    driver = get_neo4j_driver()
    
    with driver.session() as session:
        # Get notebook
        nb_result = session.run("""
            MATCH (s:Session {id: $session_id})-[:HAS_NOTEBOOK]->(nb:Notebook {id: $notebook_id})
            RETURN nb
        """, session_id=session_id, notebook_id=notebook_id)
        
        nb_record = nb_result.single()
        if not nb_record:
            driver.close()
            raise HTTPException(status_code=404, detail="Notebook not found")
        
        nb = nb_record["nb"]
        
        # Get all notes
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
    
    return {
        "notebook": {
            "id": nb["id"],
            "name": nb["name"],
            "description": nb.get("description"),
            "created_at": nb["created_at"],
            "updated_at": nb["updated_at"]
        },
        "notes": notes,
        "exported_at": datetime.utcnow().isoformat()
    }