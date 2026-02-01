# resource_extractor.py
"""Extracts and links resources (URLs, filepaths) from text."""

import re
import os
import hashlib
from urllib.parse import urlparse
from typing import Dict, List, Optional
from datetime import datetime


class ResourceExtractor:
    """Extracts resources from text and creates graph nodes."""
    
    def __init__(self, hybrid_memory):
        self.memory = hybrid_memory
    
    def extract_and_link(self, text: str, source_node_id: str) -> Dict[str, List[str]]:
        """Extract resources and create linked nodes."""
        if not self.memory or not text:
            return {'urls': [], 'filepaths': []}
        
        resources = self._extract_resources(text)
        created = {'urls': [], 'filepaths': []}
        
        # Create URL nodes
        for url in resources['urls']:
            try:
                resource_id = self._create_resource_node(url, 'url', source_node_id)
                if resource_id:
                    created['urls'].append(resource_id)
            except Exception as e:
                print(f"[ResourceExtractor] Error creating URL node: {e}")
        
        # Create filepath nodes
        for filepath in resources['filepaths']:
            try:
                resource_id = self._create_resource_node(filepath, 'filepath', source_node_id)
                if resource_id:
                    created['filepaths'].append(resource_id)
            except Exception as e:
                print(f"[ResourceExtractor] Error creating filepath node: {e}")
        
        return created
    
    def _extract_resources(self, text: str) -> Dict[str, List[str]]:
        """Extract resources using regex."""
        resources = {
            'urls': [],
            'filepaths': []
        }
        
        # URL pattern
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        urls = re.findall(url_pattern, text)
        resources['urls'] = list(set(urls))
        
        # Filepath patterns
        unix_path = r'(?:^|[\s\'"(])(\/[\w\-\.\/]+)(?:[\s\'"\)]|$)'
        windows_path = r'(?:^|[\s\'"(])([A-Za-z]:\\[\w\-\.\\]+)(?:[\s\'"\)]|$)'
        relative_path = r'(?:^|[\s\'"(])(\.{1,2}\/[\w\-\.\/]+\.(?:py|js|json|txt|md|yaml|yml|conf|sh|bat))(?:[\s\'"\)]|$)'
        
        unix_paths = [m.group(1) for m in re.finditer(unix_path, text)]
        windows_paths = [m.group(1) for m in re.finditer(windows_path, text)]
        relative_paths = [m.group(1) for m in re.finditer(relative_path, text)]
        
        all_paths = unix_paths + windows_paths + relative_paths
        resources['filepaths'] = list(set(all_paths))
        
        return resources
    
    def _create_resource_node(
        self,
        resource_uri: str,
        resource_type: str,
        source_node_id: str
    ) -> Optional[str]:
        """Create resource node and link to source."""
        resource_hash = hashlib.md5(resource_uri.encode()).hexdigest()[:12]
        resource_id = f"resource_{resource_type}_{resource_hash}"
        
        metadata = {
            "uri": resource_uri,
            "type": resource_type,
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
        
        # Create node
        self.memory.upsert_entity(
            entity_id=resource_id,
            etype="resource",
            labels=["Resource", resource_type.upper()],
            properties=metadata
        )
        
        # Link to source
        self.memory.link(
            source_node_id,
            resource_id,
            "REFERENCES",
            {"discovered_at": datetime.utcnow().isoformat()}
        )
        
        return resource_id