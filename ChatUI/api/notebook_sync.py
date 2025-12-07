#!/usr/bin/env python3
"""
Sync Notebooks to Neo4j
========================

This script syncs all file-stored notebooks and their notes to Neo4j.
Useful when you have notebooks in files but they're not showing up in Neo4j queries.

Usage:
    python sync_to_neo4j.py [--dry-run]
"""

import json
import sys
from pathlib import Path
from neo4j import GraphDatabase
import os
from datetime import datetime

NOTEBOOKS_DIR = Path("Output/Notebooks")
GLOBAL_DIR = NOTEBOOKS_DIR / "All_Notebooks"

def get_neo4j_connection():
    """Get Neo4j connection from environment variables"""
    uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    user = os.getenv('NEO4J_USER', 'neo4j')
    password = os.getenv('NEO4J_PASSWORD', 'password')
    
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()
        return driver
    except Exception as e:
        print(f"❌ Cannot connect to Neo4j: {e}")
        print(f"   URI: {uri}")
        print(f"   User: {user}")
        print()
        print("Please set environment variables:")
        print("  export NEO4J_URI=bolt://your-neo4j:7687")
        print("  export NEO4J_USER=neo4j")
        print("  export NEO4J_PASSWORD=your-password")
        return None

def sync_notebook_to_neo4j(driver, notebook_data, dry_run=False):
    """Sync a single notebook and all its notes to Neo4j"""
    notebook_id = notebook_data['id']
    session_id = notebook_data['session_id']
    name = notebook_data.get('name', 'Untitled')
    
    print(f"\n📓 Syncing: {name} ({notebook_id[:8]}...)")
    print(f"   Session: {session_id[:20]}...")
    print(f"   Notes: {len(notebook_data.get('notes', []))}")
    
    if dry_run:
        print("   [DRY RUN - No changes made]")
        return True
    
    try:
        with driver.session() as session:
            # Create/update session node
            session.run("""
                MERGE (s:Session {id: $session_id})
                ON CREATE SET s.created_at = $now
            """, session_id=session_id, now=datetime.utcnow().isoformat())
            
            # Create/update notebook node and relationship
            session.run("""
                MATCH (s:Session {id: $session_id})
                MERGE (s)-[:HAS_NOTEBOOK]->(nb:Notebook {id: $notebook_id})
                ON CREATE SET 
                    nb.name = $name,
                    nb.description = $description,
                    nb.created_at = $created_at,
                    nb.updated_at = $updated_at
                ON MATCH SET
                    nb.name = $name,
                    nb.description = $description,
                    nb.updated_at = $updated_at
            """,
                session_id=session_id,
                notebook_id=notebook_id,
                name=notebook_data.get('name', 'Untitled'),
                description=notebook_data.get('description', ''),
                created_at=notebook_data.get('created_at', datetime.utcnow().isoformat()),
                updated_at=notebook_data.get('updated_at', datetime.utcnow().isoformat())
            )
            
            print("   ✅ Notebook synced")
            
            # Sync all notes
            notes = notebook_data.get('notes', [])
            synced_notes = 0
            
            for note in notes:
                try:
                    # Prepare metadata and source as JSON strings
                    metadata_json = json.dumps(note.get('metadata', {}))
                    source = note.get('source')
                    source_json = json.dumps(source) if source else None
                    
                    session.run("""
                        MATCH (nb:Notebook {id: $notebook_id})
                        MERGE (nb)-[:CONTAINS]->(n:Note {id: $note_id})
                        ON CREATE SET
                            n.title = $title,
                            n.content = $content,
                            n.created_at = $created_at,
                            n.updated_at = $updated_at,
                            n.source = $source,
                            n.tags = $tags,
                            n.metadata = $metadata
                        ON MATCH SET
                            n.title = $title,
                            n.content = $content,
                            n.updated_at = $updated_at,
                            n.source = $source,
                            n.tags = $tags,
                            n.metadata = $metadata
                    """,
                        notebook_id=notebook_id,
                        note_id=note['id'],
                        title=note.get('title', 'Untitled Note'),
                        content=note.get('content', ''),
                        created_at=note.get('created_at', datetime.utcnow().isoformat()),
                        updated_at=note.get('updated_at', datetime.utcnow().isoformat()),
                        source=source_json,
                        tags=note.get('tags', []),
                        metadata=metadata_json
                    )
                    synced_notes += 1
                except Exception as e:
                    print(f"   ⚠️  Failed to sync note '{note.get('title', 'Unknown')}': {e}")
            
            print(f"   ✅ Synced {synced_notes}/{len(notes)} notes")
            return True
            
    except Exception as e:
        print(f"   ❌ Error syncing notebook: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    dry_run = '--dry-run' in sys.argv
    
    print("=" * 70)
    print("📊 SYNC NOTEBOOKS TO NEO4J")
    print("=" * 70)
    
    if dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")
    
    print()
    
    # Connect to Neo4j
    print("🔌 Connecting to Neo4j...")
    driver = get_neo4j_connection()
    
    if not driver:
        print("\n❌ Cannot proceed without Neo4j connection")
        return 1
    
    print("✅ Connected to Neo4j")
    print()
    
    # Check global storage
    if not GLOBAL_DIR.exists():
        print(f"❌ Global storage directory not found: {GLOBAL_DIR}")
        print("   Run migrate_notebooks.py first to populate global storage")
        return 1
    
    # Load all notebooks from global storage
    notebook_files = list(GLOBAL_DIR.glob("*.json"))
    print(f"📁 Found {len(notebook_files)} notebooks in global storage")
    print()
    
    # Sync each notebook
    success_count = 0
    fail_count = 0
    
    for notebook_file in notebook_files:
        try:
            with open(notebook_file, 'r', encoding='utf-8') as f:
                notebook_data = json.load(f)
            
            if sync_notebook_to_neo4j(driver, notebook_data, dry_run):
                success_count += 1
            else:
                fail_count += 1
                
        except Exception as e:
            print(f"\n❌ Error loading {notebook_file.name}: {e}")
            fail_count += 1
    
    # Close connection
    driver.close()
    
    # Summary
    print()
    print("=" * 70)
    print("📊 SYNC SUMMARY")
    print("=" * 70)
    print(f"✅ Successfully synced: {success_count}")
    print(f"❌ Failed: {fail_count}")
    print(f"📓 Total: {len(notebook_files)}")
    
    if dry_run:
        print()
        print("🔍 This was a dry run. Run without --dry-run to apply changes:")
        print("   python sync_to_neo4j.py")
    
    print("=" * 70)
    
    return 0 if fail_count == 0 else 1

if __name__ == "__main__":
    exit(main())