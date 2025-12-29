#!/usr/bin/env python3
"""
External Resources Manager for Proactive Focus
==============================================
Handles integration of external resources into focus board:
- URLs
- Local file paths
- Folders
- Neo4j memories
- ChromaDB memories
- Notebooks (filesystem + Neo4j)

Features:
- Resource validation and metadata extraction
- Automatic linking to focus board entities
- Content extraction and summarization
- Resource monitoring and updates
"""

import os
import json
import hashlib
from pathlib import Path
from typing import Optional, Dict, List, Any, Union
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import logging
import requests
from urllib.parse import urlparse
import mimetypes

logger = logging.getLogger(__name__)


class ResourceType(Enum):
    """Types of external resources"""
    URL = "url"
    FILE = "file"
    FOLDER = "folder"
    NEO4J_MEMORY = "neo4j_memory"
    CHROMA_MEMORY = "chroma_memory"
    NOTEBOOK = "notebook"
    

@dataclass
class ResourceMetadata:
    """Metadata for external resource"""
    resource_id: str
    resource_type: ResourceType
    uri: str  # Universal resource identifier
    title: str
    description: str = ""
    
    # Type-specific metadata
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    created_at: Optional[str] = None
    modified_at: Optional[str] = None
    
    # Access metadata
    accessible: bool = True
    last_checked: Optional[str] = None
    error_message: Optional[str] = None
    
    # Content preview
    content_preview: Optional[str] = None
    content_hash: Optional[str] = None
    
    # Additional metadata
    tags: List[str] = field(default_factory=list)
    custom_metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['resource_type'] = self.resource_type.value
        return data


class URLResource:
    """Handler for URL resources"""
    
    @staticmethod
    def validate(url: str) -> bool:
        """Validate URL"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False
    
    @staticmethod
    def extract_metadata(url: str) -> ResourceMetadata:
        """Extract metadata from URL"""
        resource_id = f"url_{hashlib.md5(url.encode()).hexdigest()[:12]}"
        
        try:
            # Try to fetch headers
            response = requests.head(url, timeout=5, allow_redirects=True)
            
            title = url
            mime_type = response.headers.get('Content-Type', '').split(';')[0]
            file_size = int(response.headers.get('Content-Length', 0))
            modified = response.headers.get('Last-Modified')
            
            # Try to get title from HTML
            if 'text/html' in mime_type:
                try:
                    html_response = requests.get(url, timeout=10)
                    html = html_response.text
                    
                    # Simple title extraction
                    import re
                    title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
                    if title_match:
                        title = title_match.group(1).strip()
                except:
                    pass
            
            return ResourceMetadata(
                resource_id=resource_id,
                resource_type=ResourceType.URL,
                uri=url,
                title=title,
                mime_type=mime_type,
                file_size=file_size if file_size > 0 else None,
                modified_at=modified,
                last_checked=datetime.now().isoformat(),
                accessible=True
            )
            
        except Exception as e:
            logger.warning(f"Failed to fetch URL metadata: {e}")
            
            return ResourceMetadata(
                resource_id=resource_id,
                resource_type=ResourceType.URL,
                uri=url,
                title=url,
                last_checked=datetime.now().isoformat(),
                accessible=False,
                error_message=str(e)
            )


class FileResource:
    """Handler for local file resources"""
    
    @staticmethod
    def validate(path: str) -> bool:
        """Validate file path"""
        return os.path.isfile(path)
    
    @staticmethod
    def extract_metadata(path: str) -> ResourceMetadata:
        """Extract metadata from file"""
        path_obj = Path(path)
        resource_id = f"file_{hashlib.md5(str(path_obj.absolute()).encode()).hexdigest()[:12]}"
        
        try:
            stats = path_obj.stat()
            mime_type, _ = mimetypes.guess_type(str(path_obj))
            
            # Get content preview for text files
            content_preview = None
            content_hash = None
            
            if mime_type and mime_type.startswith('text/'):
                try:
                    with open(path_obj, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read(1000)  # First 1000 chars
                        content_preview = content
                        
                    # Calculate hash of full file
                    with open(path_obj, 'rb') as f:
                        content_hash = hashlib.md5(f.read()).hexdigest()
                except:
                    pass
            
            return ResourceMetadata(
                resource_id=resource_id,
                resource_type=ResourceType.FILE,
                uri=str(path_obj.absolute()),
                title=path_obj.name,
                description=f"File: {path_obj.name}",
                file_size=stats.st_size,
                mime_type=mime_type,
                created_at=datetime.fromtimestamp(stats.st_ctime).isoformat(),
                modified_at=datetime.fromtimestamp(stats.st_mtime).isoformat(),
                last_checked=datetime.now().isoformat(),
                accessible=True,
                content_preview=content_preview,
                content_hash=content_hash
            )
            
        except Exception as e:
            logger.warning(f"Failed to extract file metadata: {e}")
            
            return ResourceMetadata(
                resource_id=resource_id,
                resource_type=ResourceType.FILE,
                uri=str(path_obj.absolute()),
                title=path_obj.name,
                last_checked=datetime.now().isoformat(),
                accessible=False,
                error_message=str(e)
            )


class FolderResource:
    """Handler for folder resources"""
    
    @staticmethod
    def validate(path: str) -> bool:
        """Validate folder path"""
        return os.path.isdir(path)
    
    @staticmethod
    def extract_metadata(path: str) -> ResourceMetadata:
        """Extract metadata from folder"""
        path_obj = Path(path)
        resource_id = f"folder_{hashlib.md5(str(path_obj.absolute()).encode()).hexdigest()[:12]}"
        
        try:
            # Count files
            file_count = 0
            total_size = 0
            
            for item in path_obj.rglob('*'):
                if item.is_file():
                    file_count += 1
                    try:
                        total_size += item.stat().st_size
                    except:
                        pass
            
            return ResourceMetadata(
                resource_id=resource_id,
                resource_type=ResourceType.FOLDER,
                uri=str(path_obj.absolute()),
                title=path_obj.name,
                description=f"Folder with {file_count} files",
                file_size=total_size,
                last_checked=datetime.now().isoformat(),
                accessible=True,
                custom_metadata={'file_count': file_count}
            )
            
        except Exception as e:
            logger.warning(f"Failed to extract folder metadata: {e}")
            
            return ResourceMetadata(
                resource_id=resource_id,
                resource_type=ResourceType.FOLDER,
                uri=str(path_obj.absolute()),
                title=path_obj.name,
                last_checked=datetime.now().isoformat(),
                accessible=False,
                error_message=str(e)
            )


class NotebookResource:
    """Handler for notebook resources"""
    
    NOTEBOOKS_DIR = "./Output/Notebooks"
    
    @staticmethod
    def get_notebook_path(session_id: str, notebook_id: str) -> Path:
        """Get path to notebook file"""
        return Path(NotebookResource.NOTEBOOKS_DIR) / session_id / f"{notebook_id}.json"
    
    @staticmethod
    def list_notebooks(session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List available notebooks"""
        notebooks = []
        base_path = Path(NotebookResource.NOTEBOOKS_DIR)
        
        if not base_path.exists():
            return notebooks
        
        if session_id:
            # List notebooks for specific session
            session_path = base_path / session_id
            if session_path.exists():
                for notebook_file in session_path.glob('*.json'):
                    try:
                        with open(notebook_file, 'r') as f:
                            data = json.load(f)
                            notebooks.append({
                                'id': data['id'],
                                'session_id': data['session_id'],
                                'name': data['name'],
                                'description': data.get('description', ''),
                                'note_count': data.get('note_count', 0),
                                'path': str(notebook_file)
                            })
                    except Exception as e:
                        logger.warning(f"Failed to load notebook {notebook_file}: {e}")
        else:
            # List all notebooks across sessions
            for session_dir in base_path.iterdir():
                if session_dir.is_dir():
                    for notebook_file in session_dir.glob('*.json'):
                        try:
                            with open(notebook_file, 'r') as f:
                                data = json.load(f)
                                notebooks.append({
                                    'id': data['id'],
                                    'session_id': data['session_id'],
                                    'name': data['name'],
                                    'description': data.get('description', ''),
                                    'note_count': data.get('note_count', 0),
                                    'path': str(notebook_file)
                                })
                        except Exception as e:
                            logger.warning(f"Failed to load notebook {notebook_file}: {e}")
        
        return notebooks
    
    @staticmethod
    def extract_metadata(notebook_path: str) -> ResourceMetadata:
        """Extract metadata from notebook file"""
        path_obj = Path(notebook_path)
        
        try:
            with open(path_obj, 'r') as f:
                data = json.load(f)
            
            resource_id = f"notebook_{data['id']}"
            
            # Collect note previews
            notes_preview = []
            for note in data.get('notes', [])[:3]:  # First 3 notes
                notes_preview.append(f"• {note.get('title', 'Untitled')}: {note.get('content', '')[:100]}")
            
            content_preview = "\n".join(notes_preview) if notes_preview else "Empty notebook"
            
            return ResourceMetadata(
                resource_id=resource_id,
                resource_type=ResourceType.NOTEBOOK,
                uri=str(path_obj.absolute()),
                title=data.get('name', 'Untitled Notebook'),
                description=data.get('description', ''),
                created_at=data.get('created_at'),
                modified_at=data.get('updated_at'),
                last_checked=datetime.now().isoformat(),
                accessible=True,
                content_preview=content_preview,
                custom_metadata={
                    'session_id': data.get('session_id'),
                    'note_count': data.get('note_count', 0),
                    'notebook_id': data['id']
                }
            )
            
        except Exception as e:
            logger.warning(f"Failed to extract notebook metadata: {e}")
            
            return ResourceMetadata(
                resource_id=f"notebook_{path_obj.stem}",
                resource_type=ResourceType.NOTEBOOK,
                uri=str(path_obj.absolute()),
                title=path_obj.stem,
                last_checked=datetime.now().isoformat(),
                accessible=False,
                error_message=str(e)
            )


class MemoryResource:
    """Handler for memory resources (Neo4j and ChromaDB)"""
    
    @staticmethod
    def extract_neo4j_metadata(
        memory_id: str,
        hybrid_memory,
        entity_type: Optional[str] = None
    ) -> ResourceMetadata:
        """Extract metadata from Neo4j memory entity"""
        try:
            # Query Neo4j for entity
            with hybrid_memory.graph._driver.session() as sess:
                if entity_type:
                    result = sess.run(
                        f"MATCH (n:{entity_type} {{id: $id}}) RETURN n",
                        {"id": memory_id}
                    ).single()
                else:
                    result = sess.run(
                        "MATCH (n {id: $id}) RETURN n",
                        {"id": memory_id}
                    ).single()
                
                if not result:
                    raise ValueError(f"Memory entity not found: {memory_id}")
                
                node = result["n"]
                props = dict(node)
                labels = list(node.labels)
                
                # Extract text content
                content = props.get('text', props.get('content', props.get('description', '')))
                
                return ResourceMetadata(
                    resource_id=f"neo4j_{memory_id}",
                    resource_type=ResourceType.NEO4J_MEMORY,
                    uri=f"neo4j://{memory_id}",
                    title=props.get('title', props.get('name', memory_id)),
                    description=content[:200] if content else "",
                    created_at=props.get('created_at'),
                    modified_at=props.get('updated_at'),
                    last_checked=datetime.now().isoformat(),
                    accessible=True,
                    content_preview=content[:500] if content else None,
                    tags=labels,
                    custom_metadata={
                        'entity_type': labels[0] if labels else 'Unknown',
                        'properties': {k: v for k, v in props.items() if isinstance(v, (str, int, float, bool))}
                    }
                )
        
        except Exception as e:
            logger.warning(f"Failed to extract Neo4j metadata: {e}")
            
            return ResourceMetadata(
                resource_id=f"neo4j_{memory_id}",
                resource_type=ResourceType.NEO4J_MEMORY,
                uri=f"neo4j://{memory_id}",
                title=memory_id,
                last_checked=datetime.now().isoformat(),
                accessible=False,
                error_message=str(e)
            )
    
    @staticmethod
    def extract_chroma_metadata(
        doc_id: str,
        collection_name: str,
        hybrid_memory
    ) -> ResourceMetadata:
        """Extract metadata from ChromaDB document"""
        try:
            collection = hybrid_memory.vec.get_collection(collection_name)
            result = collection.get(ids=[doc_id])
            
            if not result or not result.get('ids'):
                raise ValueError(f"Document not found: {doc_id}")
            
            text = result['documents'][0]
            metadata = result['metadatas'][0] if result.get('metadatas') else {}
            
            return ResourceMetadata(
                resource_id=f"chroma_{collection_name}_{doc_id}",
                resource_type=ResourceType.CHROMA_MEMORY,
                uri=f"chroma://{collection_name}/{doc_id}",
                title=metadata.get('title', doc_id),
                description=text[:200],
                last_checked=datetime.now().isoformat(),
                accessible=True,
                content_preview=text[:500],
                tags=[collection_name],
                custom_metadata=metadata
            )
        
        except Exception as e:
            logger.warning(f"Failed to extract ChromaDB metadata: {e}")
            
            return ResourceMetadata(
                resource_id=f"chroma_{collection_name}_{doc_id}",
                resource_type=ResourceType.CHROMA_MEMORY,
                uri=f"chroma://{collection_name}/{doc_id}",
                title=doc_id,
                last_checked=datetime.now().isoformat(),
                accessible=False,
                error_message=str(e)
            )


class ExternalResourceManager:
    """Main manager for external resources in focus board"""
    
    def __init__(self, hybrid_memory=None):
        self.hybrid_memory = hybrid_memory
        self.resources: Dict[str, ResourceMetadata] = {}
    
    def add_resource(
        self,
        uri: str,
        resource_type: Optional[ResourceType] = None,
        **kwargs
    ) -> ResourceMetadata:
        """Add external resource and extract metadata"""
        
        # Auto-detect resource type if not specified
        if resource_type is None:
            resource_type = self._detect_resource_type(uri)
        
        # Extract metadata based on type
        if resource_type == ResourceType.URL:
            metadata = URLResource.extract_metadata(uri)
        
        elif resource_type == ResourceType.FILE:
            metadata = FileResource.extract_metadata(uri)
        
        elif resource_type == ResourceType.FOLDER:
            metadata = FolderResource.extract_metadata(uri)
        
        elif resource_type == ResourceType.NOTEBOOK:
            metadata = NotebookResource.extract_metadata(uri)
        
        elif resource_type == ResourceType.NEO4J_MEMORY:
            if not self.hybrid_memory:
                raise ValueError("Hybrid memory required for Neo4j resources")
            metadata = MemoryResource.extract_neo4j_metadata(
                uri,
                self.hybrid_memory,
                kwargs.get('entity_type')
            )
        
        elif resource_type == ResourceType.CHROMA_MEMORY:
            if not self.hybrid_memory:
                raise ValueError("Hybrid memory required for ChromaDB resources")
            metadata = MemoryResource.extract_chroma_metadata(
                uri,
                kwargs.get('collection_name', 'long_term_docs'),
                self.hybrid_memory
            )
        
        else:
            raise ValueError(f"Unsupported resource type: {resource_type}")
        
        # Store resource
        self.resources[metadata.resource_id] = metadata
        
        logger.info(f"Added resource: {metadata.resource_id} ({metadata.resource_type.value})")
        
        return metadata
    
    def _detect_resource_type(self, uri: str) -> ResourceType:
        """Auto-detect resource type from URI"""
        if uri.startswith(('http://', 'https://')):
            return ResourceType.URL
        
        elif uri.startswith('neo4j://'):
            return ResourceType.NEO4J_MEMORY
        
        elif uri.startswith('chroma://'):
            return ResourceType.CHROMA_MEMORY
        
        elif os.path.isfile(uri):
            # Check if it's a notebook
            if uri.endswith('.json') and '/Notebooks/' in uri:
                return ResourceType.NOTEBOOK
            return ResourceType.FILE
        
        elif os.path.isdir(uri):
            return ResourceType.FOLDER
        
        else:
            raise ValueError(f"Could not detect resource type for: {uri}")
    
    def get_resource(self, resource_id: str) -> Optional[ResourceMetadata]:
        """Get resource metadata"""
        return self.resources.get(resource_id)
    
    def list_resources(
        self,
        resource_type: Optional[ResourceType] = None
    ) -> List[ResourceMetadata]:
        """List all resources, optionally filtered by type"""
        if resource_type:
            return [r for r in self.resources.values() if r.resource_type == resource_type]
        return list(self.resources.values())
    
    def refresh_metadata(self, resource_id: str) -> ResourceMetadata:
        """Refresh metadata for a resource"""
        resource = self.resources.get(resource_id)
        if not resource:
            raise ValueError(f"Resource not found: {resource_id}")
        
        # Re-extract metadata
        updated = self.add_resource(resource.uri, resource.resource_type)
        return updated
    
    def link_to_focus_board(
        self,
        resource_id: str,
        focus_board_category: str,
        focus_manager
    ) -> Dict[str, Any]:
        """Link resource to focus board"""
        resource = self.resources.get(resource_id)
        if not resource:
            raise ValueError(f"Resource not found: {resource_id}")
        
        # Create focus board item with resource reference
        item = {
            "note": f"Resource: {resource.title}",
            "timestamp": datetime.now().isoformat(),
            "metadata": {
                "resource_id": resource.resource_id,
                "resource_type": resource.resource_type.value,
                "resource_uri": resource.uri,
                "resource_preview": resource.content_preview
            }
        }
        
        # Add to focus board
        focus_manager.focus_board[focus_board_category].append(item)
        
        logger.info(f"Linked resource {resource_id} to focus board ({focus_board_category})")
        
        return item


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    manager = ExternalResourceManager()
    
    # Add URL
    url_meta = manager.add_resource("https://github.com/anthropics/anthropic-sdk-python")
    print(f"\nURL Resource: {url_meta.title}")
    print(f"  Accessible: {url_meta.accessible}")
    
    # Add file
    if os.path.exists("./README.md"):
        file_meta = manager.add_resource("./README.md")
        print(f"\nFile Resource: {file_meta.title}")
        print(f"  Size: {file_meta.file_size} bytes")
        print(f"  Preview: {file_meta.content_preview[:100] if file_meta.content_preview else 'N/A'}")
    
    # List notebooks
    notebooks = NotebookResource.list_notebooks()
    print(f"\nFound {len(notebooks)} notebooks")
    for nb in notebooks[:3]:
        print(f"  - {nb['name']} ({nb['note_count']} notes)")
    
    # List all resources
    print(f"\nAll resources ({len(manager.list_resources())}):")
    for res in manager.list_resources():
        print(f"  - [{res.resource_type.value}] {res.title}")